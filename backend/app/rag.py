import json
import logging
import re
import time
from dataclasses import dataclass, field

from .config import get_settings
from .embeddings import rerank
from .retrieval import Passage, has_evidence, search

log = logging.getLogger(__name__)

REFUSAL = "The uploaded documents don't contain enough information to answer this."

SYSTEM_PROMPT = """You answer questions strictly from numbered source passages taken from the user's PDFs.

Rules:
- Use only facts stated in the passages. Do not use outside knowledge, even if you are confident.
- Every sentence that states a fact must end with one or more citations in square brackets referring to passage numbers, e.g. "... was 4.2% [2]." or "[1][3]".
- If the passages do not contain the information needed to answer, set "answerable" to false and leave "answer" empty. Partial evidence is fine: answer what is supported and say what is missing.
- Be concise and direct. No preamble, no restating the question. Use short paragraphs or a list where it helps.
- Quote exact figures, names and dates as written in the passages.

Respond with a single JSON object and nothing else:
{"answerable": true|false, "answer": "<markdown answer with [n] citations>"}"""


@dataclass
class Citation:
    n: int
    document_id: str
    filename: str
    title: str | None
    page: int
    snippet: str
    boxes: list
    score: float | None


@dataclass
class Answer:
    question: str
    answer: str
    answerable: bool
    citations: list[Citation] = field(default_factory=list)
    passages: list[dict] = field(default_factory=list)
    mode: str = "llm"
    timings_ms: dict = field(default_factory=dict)
    refusal_reason: str | None = None


def _format_context(passages: list[Passage]) -> str:
    parts = []
    for i, p in enumerate(passages, 1):
        parts.append(f"[{i}] (source: {p.filename}, page {p.page_no})\n{p.text}")
    return "\n\n".join(parts)


def _call_llm(question: str, passages: list[Passage]) -> str:
    s = get_settings()
    user = f"Passages:\n\n{_format_context(passages)}\n\nQuestion: {question}"
    provider = s.resolved_provider
    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url, timeout=s.llm_timeout_s)
        resp = client.chat.completions.create(
            model=s.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""
    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=s.anthropic_api_key, timeout=s.llm_timeout_s)
        resp = client.messages.create(
            model=s.anthropic_model,
            max_tokens=1024,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}, {"role": "assistant", "content": "{"}],
        )
        return "{" + "".join(b.text for b in resp.content if b.type == "text")
    raise RuntimeError(f"Unknown LLM provider: {provider}")


def _parse(raw: str) -> tuple[bool, str]:
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return False, ""
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return False, ""
    return bool(data.get("answerable")), str(data.get("answer") or "").strip()


_CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _renumber(answer: str, passages: list[Passage]) -> tuple[str, list[Citation]]:
    """Keep only citations that point at real passages and renumber them 1..k
    in order of first appearance."""
    mapping: dict[int, int] = {}
    cites: list[Citation] = []

    def sub(m: re.Match) -> str:
        out = []
        for raw in m.group(1).split(","):
            idx = int(raw.strip())
            if not 1 <= idx <= len(passages):
                continue
            if idx not in mapping:
                p = passages[idx - 1]
                mapping[idx] = len(mapping) + 1
                cites.append(
                    Citation(
                        n=mapping[idx],
                        document_id=p.document_id,
                        filename=p.filename,
                        title=p.title,
                        page=p.page_no,
                        snippet=p.text,
                        boxes=p.boxes,
                        score=p.rerank_score,
                    )
                )
            out.append(f"[{mapping[idx]}]")
        return "".join(dict.fromkeys(out))

    text = _CITE.sub(sub, answer)
    # A dropped marker (fabricated source) can leave a space before punctuation.
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    return text.strip(), cites


_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_HEADING = re.compile(r"^(\d+(\.\d+)*\.?\s+)?[A-Z][\w &/,'-]{0,60}$")


def _sentences(line: str) -> list[str]:
    return [s.strip() for s in _SENT.split(line) if len(s.strip()) >= 12]


def _is_heading(line: str) -> bool:
    return bool(_HEADING.match(line)) and not any(c.isdigit() for c in line[3:])


def _is_table_row(line: str) -> bool:
    return len(line) <= 90 and any(c.isdigit() for c in line)


def _units(text: str) -> list[str]:
    """Split a chunk into quotable units.

    Paragraphs become sentences and headings are dropped. A run of adjacent
    short numeric lines is kept together instead, because a table row such as
    "$318m $297m +7.1%" means nothing without the header line above it.
    """
    units: list[str] = []
    rows: list[str] = []

    def flush_rows() -> None:
        if not rows:
            return
        if len(rows) > 1:
            units.append(" ".join(rows))
        else:
            # A lone short line is just a sentence that contains a number.
            units.extend(_sentences(rows[0]))
        rows.clear()

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line or _is_heading(line):
            continue
        if _is_table_row(line):
            rows.append(line)
            continue
        flush_rows()
        units.extend(_sentences(line))
    flush_rows()
    return units


def _extractive(question: str, passages: list[Passage]) -> tuple[bool, str]:
    """No-LLM fallback: quote the best-supported sentences verbatim, cited.
    Cannot synthesise or reason, so it is deliberately conservative."""
    candidates: list[tuple[int, str]] = []
    for i, p in enumerate(passages[:4], 1):
        candidates.extend((i, u) for u in _units(p.text))
    if not candidates:
        return False, ""
    scores = rerank(question, [c[1] for c in candidates])
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    best = ranked[0][0]
    floor = get_settings().extractive_min_score
    if best < floor:
        return False, ""
    picked = [c for s, c in ranked[:3] if s >= max(floor, best - 2.5)]
    return True, "\n\n".join(f"{sent} [{i}]" for i, sent in picked)


def answer_question(question: str, document_ids: list[str] | None = None) -> Answer:
    s = get_settings()
    t0 = time.perf_counter()
    passages = search(question, document_ids)
    t1 = time.perf_counter()

    debug = [
        {
            "document_id": p.document_id,
            "filename": p.filename,
            "page": p.page_no,
            "similarity": round(p.similarity, 4),
            "rerank_score": None if p.rerank_score is None else round(p.rerank_score, 3),
            "text": p.text,
        }
        for p in passages
    ]
    mode = "extractive" if s.resolved_provider == "extractive" else "llm"
    result = Answer(question=question, answer=REFUSAL, answerable=False, passages=debug, mode=mode)

    if not has_evidence(passages):
        result.refusal_reason = "no_relevant_passages"
        result.timings_ms = {"retrieval": round((t1 - t0) * 1000)}
        return result

    if mode == "extractive":
        answerable, text = _extractive(question, passages)
    else:
        try:
            answerable, text = _parse(_call_llm(question, passages))
        except Exception as exc:
            log.exception("LLM call failed")
            raise RuntimeError(f"Language model request failed: {exc}") from exc
    t2 = time.perf_counter()
    result.timings_ms = {"retrieval": round((t1 - t0) * 1000), "generation": round((t2 - t1) * 1000)}

    if not answerable or not text:
        result.refusal_reason = "model_found_no_support"
        return result

    text, cites = _renumber(text, passages)
    if not cites:
        # An answer with no verifiable source is treated as unsupported.
        result.refusal_reason = "answer_had_no_citations"
        return result

    result.answer, result.answerable, result.citations = text, True, cites
    return result

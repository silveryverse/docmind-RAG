"""Evaluate retrieval and answer quality on the synthetic corpus.

    python -m eval.run_eval                 # retrieval + answers
    python -m eval.run_eval --retrieval-only

Retrieval metrics (answerable questions only):
    hit@1 / hit@3 / hit@k  - a gold page appears in the top results
    MRR                    - mean reciprocal rank of the first gold page

Answer metrics:
    answer accuracy  - answered, and contains every required fact
    citation accuracy - at least one cited page is a gold page
    citation precision - share of all citations that point at a gold page
    refusal recall    - unanswerable questions correctly refused
    false refusals    - answerable questions wrongly refused
"""

import argparse
import json
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.db import connection, init_db
from app.ingest import ingest_file_sync
from app.rag import answer_question
from app.retrieval import has_evidence, search

HERE = Path(__file__).resolve().parent


def _norm(s: str) -> str:
    return s.lower().replace("\u2011", "-").replace("\u2013", "-")


def contains_all(answer: str, required: list) -> bool:
    text = _norm(answer)
    for item in required:
        options = item if isinstance(item, list) else [item]
        if not any(_norm(o) in text for o in options):
            return False
    return True


def ensure_corpus() -> dict[str, str]:
    corpus = HERE / "corpus"
    if not corpus.exists() or not list(corpus.glob("*.pdf")):
        from eval import build_corpus

        build_corpus.main()
    ids = {}
    for pdf in sorted(corpus.glob("*.pdf")):
        ids[pdf.name] = ingest_file_sync(pdf)
    with connection() as conn:
        rows = conn.execute("SELECT filename, status, error FROM documents WHERE id = ANY(%s::uuid[])",
                            (list(ids.values()),)).fetchall()
    for r in rows:
        if r["status"] != "ready":
            sys.exit(f"{r['filename']} failed to ingest: {r['error']}")
    return ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrieval-only", action="store_true")
    ap.add_argument("--only", help="comma-separated question ids")
    ap.add_argument("--out", default=str(HERE / "results.json"))
    args = ap.parse_args()

    init_db()
    ids = ensure_corpus()
    scope = list(ids.values())
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    if args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]

    s = get_settings()
    k = s.top_k
    rows = []
    for q in questions:
        gold = {(q["doc"], p) for p in q["pages"]}
        t0 = time.perf_counter()
        passages = search(q["question"], scope)
        ranks = [i for i, p in enumerate(passages, 1) if (p.filename, p.page_no) in gold]
        row = {
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "answerable": q["type"] != "unanswerable",
            "first_gold_rank": ranks[0] if ranks else None,
            "gate_pass": has_evidence(passages),
            "top": [
                {"doc": p.filename, "page": p.page_no, "sim": round(p.similarity, 3),
                 "rerank": None if p.rerank_score is None else round(p.rerank_score, 2)}
                for p in passages[:3]
            ],
            "retrieval_ms": round((time.perf_counter() - t0) * 1000),
        }
        if not args.retrieval_only:
            res = answer_question(q["question"], scope)
            cited = {(c.filename, c.page) for c in res.citations}
            row.update(
                answered=res.answerable,
                answer=res.answer,
                refusal_reason=res.refusal_reason,
                cited=sorted(f"{d}#p{p}" for d, p in cited),
                cites_gold=bool(cited & gold),
                cite_precision=(len(cited & gold) / len(cited)) if cited else None,
                correct=res.answerable and contains_all(res.answer, q.get("answer_contains", [])),
                mode=res.mode,
            )
        rows.append(row)
        status = ""
        if not args.retrieval_only:
            if row["answerable"]:
                status = "OK " if row["correct"] and row["cites_gold"] else ("REF" if not row["answered"] else "BAD")
            else:
                status = "OK " if not row["answered"] else "BAD"
        print(f"{status} {q['id']:6} rank={row['first_gold_rank']!s:4} gate={'y' if row['gate_pass'] else 'n'} "
              f"top={row['top'][0]['doc'][:12] if row['top'] else '-'}#p{row['top'][0]['page'] if row['top'] else '-'} "
              f"rr={row['top'][0]['rerank'] if row['top'] else '-'}")

    ans = [r for r in rows if r["answerable"]]
    unans = [r for r in rows if not r["answerable"]]

    def pct(n, d):
        return round(100 * n / d, 1) if d else None

    summary = {
        "settings": {"embed_model": s.embed_model, "rerank": s.rerank_enabled and s.rerank_model,
                     "top_k": k, "llm": s.resolved_provider,
                     "min_rerank_score": s.min_rerank_score},
        "n_questions": len(rows),
        "retrieval": {
            "hit@1": pct(sum(r["first_gold_rank"] == 1 for r in ans), len(ans)),
            "hit@3": pct(sum(bool(r["first_gold_rank"]) and r["first_gold_rank"] <= 3 for r in ans), len(ans)),
            f"hit@{k}": pct(sum(r["first_gold_rank"] is not None for r in ans), len(ans)),
            "mrr": round(sum(1 / r["first_gold_rank"] for r in ans if r["first_gold_rank"]) / len(ans), 3) if ans else None,
            "evidence_gate_pass_answerable": pct(sum(r["gate_pass"] for r in ans), len(ans)),
            "evidence_gate_block_unanswerable": pct(sum(not r["gate_pass"] for r in unans), len(unans)),
        },
    }
    if not args.retrieval_only:
        summary["answers"] = {
            "answer_accuracy": pct(sum(r["correct"] for r in ans), len(ans)),
            "citation_accuracy": pct(sum(r["cites_gold"] for r in ans if r["answered"]),
                                     sum(r["answered"] for r in ans)),
            "citation_precision": pct(sum(r["cite_precision"] for r in ans if r["cite_precision"] is not None),
                                      sum(r["cite_precision"] is not None for r in ans)),
            "false_refusal_rate": pct(sum(not r["answered"] for r in ans), len(ans)),
            "refusal_recall": pct(sum(not r["answered"] for r in unans), len(unans)),
        }
        by_type: dict[str, list] = {}
        for r in ans:
            by_type.setdefault(r["type"], []).append(r["correct"])
        summary["answer_accuracy_by_type"] = {t: pct(sum(v), len(v)) for t, v in sorted(by_type.items())}

    Path(args.out).write_text(json.dumps({"summary": summary, "results": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

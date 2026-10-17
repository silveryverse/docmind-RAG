"""Page-bounded chunking.

Chunks never span pages, so every chunk maps to exactly one citable page.
Blocks are packed greedily up to a target size; oversized blocks are split on
sentence boundaries. A short tail is merged into the previous chunk.
"""

import re
from dataclasses import dataclass, field

from .pdf import Block, PageContent

_SENT_SPLIT = re.compile(r"(?<=[.!?;:])\s+(?=[A-Z0-9(\"'])")


@dataclass
class Chunk:
    page_no: int
    ord: int
    text: str
    boxes: list[tuple[float, float, float, float]] = field(default_factory=list)


def _split_block(block: Block, max_chars: int) -> list[Block]:
    if len(block.text) <= max_chars:
        return [block]
    sentences = _SENT_SPLIT.split(block.text)
    parts, cur = [], ""
    for s in sentences:
        while len(s) > max_chars:  # pathological: no sentence breaks
            cut = s.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(s[:cut].strip())
            s = s[cut:].strip()
        if cur and len(cur) + 1 + len(s) > max_chars:
            parts.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        parts.append(cur)
    return [Block(p, block.box) for p in parts]


def chunk_pages(pages: list[PageContent], target: int, max_chars: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        page_chunks: list[Chunk] = []
        cur_text: list[str] = []
        cur_boxes: list[tuple] = []

        def flush():
            if cur_text:
                page_chunks.append(Chunk(page.page_no, 0, "\n".join(cur_text), list(cur_boxes)))
                cur_text.clear()
                cur_boxes.clear()

        for raw in page.blocks:
            for block in _split_block(raw, max_chars):
                size = sum(len(t) + 1 for t in cur_text)
                if cur_text and (size + len(block.text) > max_chars or size >= target):
                    flush()
                cur_text.append(block.text)
                if block.box not in cur_boxes:
                    cur_boxes.append(block.box)
        flush()

        if len(page_chunks) > 1 and len(page_chunks[-1].text) < target // 4:
            tail = page_chunks.pop()
            prev = page_chunks[-1]
            prev.text = f"{prev.text}\n{tail.text}"
            prev.boxes.extend(b for b in tail.boxes if b not in prev.boxes)

        chunks.extend(page_chunks)

    for i, c in enumerate(chunks):
        c.ord = i
    return chunks

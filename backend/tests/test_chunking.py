from app.chunking import chunk_pages
from app.pdf import Block, PageContent

import pytest


def page(n: int, texts: list[str]) -> PageContent:
    blocks = [Block(t, (0.1, 0.1 + i * 0.05, 0.9, 0.14 + i * 0.05)) for i, t in enumerate(texts)]
    return PageContent(n, 595, 842, False, blocks)


def test_chunks_never_span_pages():
    pages = [page(i, [f"Page {i} sentence " * 12]) for i in (1, 2, 3)]
    chunks = chunk_pages(pages, target=200, max_chars=300)
    # One block per page, each under the max, so exactly one chunk per page.
    assert len(chunks) == 3
    assert {c.page_no for c in chunks} == {1, 2, 3}

    split = chunk_pages([page(i, [f"Page {i} sentence " * 40]) for i in (1, 2)], target=200, max_chars=300)
    assert len(split) > 2
    assert {c.page_no for c in split} == {1, 2}


def test_chunk_size_respects_max():
    long = "Alpha beta gamma delta epsilon zeta eta theta iota kappa. " * 40
    chunks = chunk_pages([page(1, [long])], target=300, max_chars=400)
    # A single oversized block is split on sentence boundaries.
    assert all(len(c.text) <= 400 for c in chunks)
    assert len(chunks) > 1


def test_blocks_are_joined_with_newlines_and_keep_boxes():
    pages = [page(1, ["First paragraph.", "Second paragraph."])]
    chunk = chunk_pages(pages, target=500, max_chars=800)[0]
    assert chunk.text == "First paragraph.\nSecond paragraph."
    assert chunk.boxes == [
        (0.1, 0.1, 0.9, 0.14),
        pytest.approx([0.1, 0.15, 0.9, 0.19], abs=1e-9),
    ]


def test_tiny_tail_is_merged_into_previous_chunk():
    pages = [page(1, ["A " * 200, "tail."])]
    chunks = chunk_pages(pages, target=500, max_chars=550)
    assert len(chunks) == 1
    assert chunks[0].text.endswith("tail.")


def test_ordinals_are_sequential_across_pages():
    pages = [page(1, ["one " * 100]), page(2, ["two " * 100])]
    chunks = chunk_pages(pages, target=200, max_chars=300)
    assert [c.ord for c in chunks] == list(range(len(chunks)))

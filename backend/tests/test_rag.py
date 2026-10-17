import json

from app.rag import _parse, _renumber, _units, REFUSAL
from app.retrieval import Passage


def passage(text: str, page: int = 1, doc: str = "d1") -> Passage:
    return Passage(
        chunk_id=page,
        document_id=doc,
        filename="doc.pdf",
        title="Doc",
        page_no=page,
        text=text,
        boxes=[],
        similarity=0.7,
        rerank_score=2.0,
    )


def test_parse_extracts_json_from_fenced_output():
    raw = 'Here you go:\n```json\n{"answerable": true, "answer": "It rose [1]."}\n```'
    assert _parse(raw) == (True, "It rose [1].")


def test_parse_handles_garbage():
    assert _parse("no json here") == (False, "")


def test_renumber_keeps_only_valid_citations_and_orders_them():
    passages = [passage("first", 1), passage("second", 2)]
    text, cites = _renumber("B is true [2] and A is true [1]; C is unknown [9].", passages)
    # The fabricated [9] is removed rather than shown as a source.
    assert text == "B is true [1] and A is true [2]; C is unknown."
    assert [c.n for c in cites] == [1, 2]
    assert [c.page for c in cites] == [2, 1]  # renumbered by first appearance


def test_renumber_merges_grouped_markers_and_drops_duplicates():
    text, cites = _renumber("Facts [1, 2] and again [1].", [passage("a"), passage("b")])
    assert text == "Facts [1][2] and again [1]."
    assert len(cites) == 2


def test_renumber_returns_no_citations_when_all_invalid():
    text, cites = _renumber("Unsupported claim [7].", [passage("a")])
    assert cites == []
    assert text == "Unsupported claim."


def test_units_drops_headings_and_splits_sentences():
    chunk = "3. Siting the Outdoor Unit\nKeep 600 mm clear. Do not block the fan."
    units = _units(chunk)
    assert "3. Siting the Outdoor Unit" not in units
    assert "Keep 600 mm clear." in units


def test_refusal_message_is_stable():
    assert "don't contain enough information" in REFUSAL


def test_citation_roundtrip_json_is_serialisable():
    _, cites = _renumber("Answer [1].", [passage("quoted text")])
    payload = json.dumps([c.__dict__ for c in cites])
    assert "quoted text" in payload

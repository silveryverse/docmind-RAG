"""Guard the OpenAI dependency floor and the answer path's API surface.

The vendor update removed the ``spend_control`` request field, removed the
``/agents/sessions`` endpoints and changed the ``/moderations`` response into a
``oneOf``. DocMind only calls ``chat.completions.create``, so it was not using
any of the removed surface. Keep it that way and keep the SDK floor at the
newest published release.

This test is stdlib-only so it runs even when the optional OpenAI SDK and the
rest of the backend dependencies are not installed.
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REQUIREMENTS = BACKEND / "requirements.txt"
RAG = BACKEND / "app" / "rag.py"

# Newest published openai release at the time of this update.
OPENAI_FLOOR = "3.57.0"

REMOVED_API_SURFACE = ("spend_control", "/agents/sessions", "/moderations")


def _version_tuple(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version)
    return tuple(int(part) for part in parts) or (0,)


def _declared_openai_floor() -> str:
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        match = re.match(
            r"^openai(?:\[[^\]]*\])?\s*>=\s*([0-9][^,;\s]*)",
            line,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
    return ""


def test_openai_floor_and_answer_path_match_removed_api_surface():
    floor = _declared_openai_floor()
    assert floor, "openai must remain a direct dependency"
    assert _version_tuple(floor) >= _version_tuple(OPENAI_FLOOR), (
        f"openai>={floor} is below the newest published release "
        f"({OPENAI_FLOOR})"
    )

    source = RAG.read_text(encoding="utf-8")
    assert "chat.completions.create" in source
    for removed in REMOVED_API_SURFACE:
        assert removed not in source, f"answer path must not use removed OpenAI API: {removed}"

"""Guard the OpenAI SDK floor after the Assistants API removal.

The vendor spec update removed the ``/assistants``, ``/conversations``,
``/audio/translations`` and ``/evals`` endpoints, and dropped the ``auto``
enum values from the Assistants response-format and chunking-strategy
schemas. DocMind never used that surface: its only OpenAI call is
``client.chat.completions.create`` with a ``json_object`` response format,
which the update leaves alone. Keep it that way and keep the SDK floor at the
release that carries the update.

This test is stdlib-only so it runs even when the optional OpenAI SDK and the
rest of the backend dependencies are not installed.
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REQUIREMENTS = BACKEND / "requirements.txt"
RAG = BACKEND / "app" / "rag.py"

# Newest published openai release carrying the Assistants API removal.
OPENAI_FLOOR = "3.59.0"

REMOVED_HTTP_SURFACE = (
    "/assistants",
    "/conversations",
    "/audio/translations",
    "/evals",
)

REMOVED_SDK_SURFACE = (
    "client.beta.assistants",
    "client.conversations",
    "client.evals",
    "client.audio.translations",
)


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


def test_answer_path_uses_chat_completions_after_assistants_removal():
    floor = _declared_openai_floor()
    assert floor, "openai must remain a direct dependency"
    assert _version_tuple(floor) >= _version_tuple(OPENAI_FLOOR), (
        f"openai>={floor} predates the Assistants API removal "
        f"({OPENAI_FLOOR})"
    )

    source = RAG.read_text(encoding="utf-8")
    assert "chat.completions.create" in source, (
        "the answer path must use the surviving chat completions endpoint"
    )
    assert re.search(
        r'response_format\s*=\s*\{\s*"type"\s*:\s*"json_object"\s*\}',
        source,
    ), "the answer path must keep requesting a JSON object response"
    for removed in REMOVED_HTTP_SURFACE + REMOVED_SDK_SURFACE:
        assert removed not in source, (
            f"answer path must not use the removed OpenAI API: {removed}"
        )

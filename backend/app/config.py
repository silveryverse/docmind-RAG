from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # If unset, an embedded PostgreSQL (with pgvector) is started under data_dir/pg.
    database_url: str | None = None
    data_dir: Path = BACKEND_DIR / "data"
    max_upload_mb: int = 50

    # Ingestion
    ocr_min_chars: int = 40  # pages with less extractable text than this are OCR'd
    ocr_dpi: int = 150  # first-pass DPI; adjusted per page from measured line height
    chunk_target_chars: int = 550
    chunk_max_chars: int = 850

    # Retrieval
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    rerank_enabled: bool = True
    candidates: int = 24
    top_k: int = 6
    # Evidence gate: below these scores the question is refused without calling the LLM.
    # Off-topic questions score around -11 with the MiniLM cross-encoder; weakly
    # phrased but answerable ones can dip to about -5.
    min_rerank_score: float = -7.0
    min_vector_similarity: float = 0.55
    # Extractive (no-LLM) mode only: a single sentence must score at least this
    # with the cross-encoder to be quoted. Stricter than the passage gate,
    # because a passage can be on-topic without any sentence answering.
    extractive_min_score: float = 2.0

    # LLM. provider: auto | openai | anthropic | extractive
    llm_provider: str = "auto"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    llm_timeout_s: float = 60.0

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def resolved_provider(self) -> str:
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.openai_api_key:
            return "openai"
        if self.anthropic_api_key:
            return "anthropic"
        return "extractive"


@lru_cache
def get_settings() -> Settings:
    return Settings()

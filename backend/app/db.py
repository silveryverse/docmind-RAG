import json
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings

log = logging.getLogger(__name__)

_pool: ConnectionPool | None = None
_embedded = None

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          uuid PRIMARY KEY,
    filename    text NOT NULL,
    title       text,
    sha256      text NOT NULL UNIQUE,
    file_path   text NOT NULL,
    size_bytes  bigint NOT NULL,
    status      text NOT NULL DEFAULT 'queued',
    progress    text,
    error       text,
    page_count  int NOT NULL DEFAULT 0,
    ocr_pages   int NOT NULL DEFAULT 0,
    chunk_count int NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    ready_at    timestamptz
);

CREATE TABLE IF NOT EXISTS pages (
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no     int  NOT NULL,
    width       real NOT NULL,
    height      real NOT NULL,
    ocr         boolean NOT NULL DEFAULT false,
    text        text NOT NULL,
    PRIMARY KEY (document_id, page_no)
);

CREATE TABLE IF NOT EXISTS chunks (
    id          bigserial PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no     int  NOT NULL,
    ord         int  NOT NULL,
    text        text NOT NULL,
    boxes       jsonb NOT NULL DEFAULT '[]',
    embedding   vector({dim}) NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);

CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (document_id, page_no);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
"""


def _embedded_log_path(pg_dir: Path) -> Path:
    """pgserver's log file, kept beside the data directory rather than in it."""
    return pg_dir.parent / "pg.log"


def _keep_pgserver_log_outside_pgdata(pg_dir: Path) -> None:
    """Point pgserver's log file somewhere other than the data directory.

    pgserver hard-codes its log to ``<pgdata>/log`` and hands that path to
    ``pg_ctl -l``, so the postmaster's stderr is redirected there. After an
    unclean shutdown Postgres has to fsync every file in the data directory
    while recovering, and on Windows it cannot open that log file because
    pg_ctl still holds it open: recovery then sits in a 30-second retry loop
    and ``pg_ctl start`` reports a timeout even though the server is starting
    normally. Writing the log outside the data directory removes the lock
    conflict, and stops recovery from having to fsync a log file that only
    ever grows.

    ``self.log`` is a plain attribute assigned inside ``PostgresServer.__init__``
    before the server starts, so a property that ignores the assignment and
    returns an external path is the least invasive way to relocate it.
    """
    import pgserver

    log_path = _embedded_log_path(pg_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cls = pgserver.PostgresServer
    if cls.__dict__.get("_docmind_external_log") == log_path:
        return
    cls.log = property(lambda self: log_path, lambda self, value: None)
    cls._docmind_external_log = log_path


def _pid_alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    # os.kill() on Windows terminates the process rather than testing it.
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def _prune_dead_handle_pids(pg_dir: Path) -> None:
    """Forget process ids left behind by a killed run.

    pgserver stops the server once the last handle exits, so a pid belonging
    to a process that no longer exists keeps that list non-empty forever: the
    embedded server is never shut down cleanly, which is exactly what makes
    the next start pay for crash recovery.
    """
    path = pg_dir / ".handle_pids.json"
    if not path.exists():
        return
    try:
        pids = json.loads(path.read_text() or "[]")
    except (OSError, ValueError):
        return
    if not isinstance(pids, list):
        return
    alive = [pid for pid in pids if isinstance(pid, int) and _pid_alive(pid)]
    if alive != pids:
        try:
            path.write_text(json.dumps(alive))
        except OSError:
            pass


def _start_embedded(pg_dir: Path) -> "object":
    """Start, or reconnect to, the embedded PostgreSQL server.

    ``pg_ctl start`` is only given 10 seconds, and crash recovery can outlast
    that; retrying finds the postmaster already running and returns at once.
    """
    import pgserver

    pg_dir.mkdir(parents=True, exist_ok=True)
    _keep_pgserver_log_outside_pgdata(pg_dir)
    _prune_dead_handle_pids(pg_dir)

    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            # cleanup_mode="stop" stops the server when the last handle exits
            # but keeps the data directory, so documents survive a restart.
            server = pgserver.get_server(pg_dir, cleanup_mode="stop")
            server.get_uri()  # fails loudly if the handle is half-built
            return server
        except Exception as exc:  # noqa: BLE001 - re-raised below with guidance
            last = exc
            # A constructor that raised leaves a half-initialised handle in
            # pgserver's cache, and get_server() would hand that same broken
            # object back on the next call, so drop it before retrying.
            pgserver.PostgresServer._instances.pop(pg_dir.resolve(), None)
            log.warning(
                "Embedded PostgreSQL did not come up on attempt %d/3 (%s); retrying in %ds",
                attempt, exc.__class__.__name__, 4,
            )
            time.sleep(4)
    raise RuntimeError(
        f"Could not start the embedded PostgreSQL in {pg_dir} after 3 attempts. "
        "Leftover postgres processes can block crash recovery: stop any running "
        "postgres processes and try again, or set DATABASE_URL to an existing "
        "PostgreSQL instance."
    ) from last


def _resolve_url() -> str:
    global _embedded
    settings = get_settings()
    if settings.database_url:
        return settings.database_url

    pg_dir = settings.data_dir / "pg"
    log.info("DATABASE_URL not set; using embedded PostgreSQL in %s", pg_dir)
    _embedded = _start_embedded(pg_dir)
    return _embedded.get_uri()


def _configure(conn: psycopg.Connection) -> None:
    register_vector(conn)


def init_db() -> None:
    global _pool
    if _pool is not None:
        return
    url = _resolve_url()
    settings = get_settings()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(SCHEMA.format(dim=settings.embed_dim))
    _pool = ConnectionPool(
        url,
        min_size=1,
        max_size=8,
        configure=_configure,
        kwargs={"row_factory": dict_row},
        open=True,
    )


def close_db() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection():
    if _pool is None:
        init_db()
    assert _pool is not None
    with _pool.connection() as conn:
        yield conn

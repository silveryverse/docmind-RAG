"""Small admin CLI.

    python manage.py ingest path/to/file.pdf [...]
    python manage.py reindex          # re-run parsing/chunking/embedding for every document
    python manage.py ask "question"
    python manage.py db-url           # print the connection string (embedded or configured)
"""

import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.db import connection, init_db


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    init_db()

    if cmd == "ingest":
        from app.ingest import ingest_file_sync

        for p in args:
            print(ingest_file_sync(Path(p)), p)
    elif cmd == "reindex":
        from app.ingest import process

        with connection() as conn:
            rows = conn.execute("SELECT id, filename FROM documents ORDER BY created_at").fetchall()
        for r in rows:
            process(str(r["id"]))
            print("reindexed", r["filename"])
    elif cmd == "ask":
        from app.rag import answer_question

        res = asdict(answer_question(" ".join(args)))
        res.pop("passages")
        for c in res["citations"]:
            c.pop("boxes")
        print(json.dumps(res, indent=2, default=str))
    elif cmd == "db-url":
        from app import db

        print(db._embedded.get_uri() if db._embedded else "configured DATABASE_URL")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

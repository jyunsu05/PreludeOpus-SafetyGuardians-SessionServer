from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .db import DB_PATH


def create_backup(source: Path, destination_dir: Path) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"database not found: {source}")

    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = destination_dir / f"sessions-{stamp}.db"

    with closing(sqlite3.connect(source)) as source_conn, closing(sqlite3.connect(destination)) as backup_conn:
        source_conn.backup(backup_conn)
        result = backup_conn.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise RuntimeError(f"backup integrity check failed: {result}")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent SQLite session backup")
    parser.add_argument("--source", type=Path, default=DB_PATH)
    parser.add_argument("--destination", type=Path, default=Path("backups"))
    args = parser.parse_args()
    print(create_backup(args.source, args.destination))


if __name__ == "__main__":
    main()

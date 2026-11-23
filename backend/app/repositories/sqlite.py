from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any


class SQLiteRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        with self._transaction() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS edit_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    operation TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _transaction(self):
        with closing(self._connect()) as connection:
            with connection:
                yield connection

    def save_session(self, session_id: str, job_id: str, revision: int, status: str, config: dict[str, Any], metadata: dict[str, Any], now: str) -> None:
        with self.lock, self._transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, job_id, revision, status, json.dumps(config, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), now, now),
            )

    def update_session(self, session_id: str, revision: int, status: str, config: dict[str, Any], metadata: dict[str, Any], now: str) -> None:
        with self.lock, self._transaction() as connection:
            connection.execute(
                "UPDATE sessions SET revision=?, status=?, config_json=?, metadata_json=?, updated_at=? WHERE id=?",
                (revision, status, json.dumps(config, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), now, session_id),
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.lock, self._transaction() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["config"] = json.loads(result.pop("config_json"))
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def append_history(self, session_id: str, revision: int, operation: str, payload: dict[str, Any], now: str) -> None:
        with self.lock, self._transaction() as connection:
            connection.execute(
                "INSERT INTO edit_history(session_id, revision, operation, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, revision, operation, json.dumps(payload, ensure_ascii=False), now),
            )

    def history(self, session_id: str) -> list[dict[str, Any]]:
        with self.lock, self._transaction() as connection:
            rows = connection.execute("SELECT revision, operation, payload_json, created_at FROM edit_history WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

"""SQLite persistence for searches and offers."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS searches (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              cv_preview TEXT NOT NULL,
              matches_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS offers (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              search_id INTEGER NOT NULL,
              remoteok_id TEXT,
              position TEXT,
              company TEXT,
              apply_url TEXT NOT NULL,
              affinity REAL,
              why_json TEXT,
              FOREIGN KEY(search_id) REFERENCES searches(id)
            );
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def save_search(self, cv_text: str, matches: list[dict[str, Any]]) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO searches(cv_preview, matches_count) VALUES (?, ?)",
                (cv_text[:500], len(matches)),
            )
            sid = int(cur.lastrowid)
            for m in matches:
                c.execute(
                    "INSERT INTO offers(search_id, remoteok_id, position, company, apply_url, affinity, why_json) VALUES (?,?,?,?,?,?,?)",
                    (sid, str(m.get("id")), m.get("position"), m.get("company"), m.get("apply_url"), m.get("affinity"), json.dumps(m.get("why") or {}, ensure_ascii=False)),
                )
            c.commit()
            return sid

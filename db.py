"""Guardar resultados sin copiar el texto del CV."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as conn, conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS searches (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              cv_preview TEXT NOT NULL DEFAULT '',
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

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def save_search(self, matches: list[dict]) -> int:
        with closing(self._conn()) as conn, conn:
            sid = conn.execute(
                "INSERT INTO searches(cv_preview, matches_count) VALUES ('', ?)",
                (len(matches),),
            ).lastrowid
            for job in matches:
                conn.execute(
                    "INSERT INTO offers(search_id,remoteok_id,position,company,apply_url,affinity,why_json) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        sid,
                        str(job.get("id")),
                        job.get("position"),
                        job.get("company"),
                        job["apply_url"],
                        job.get("affinity"),
                        json.dumps(job.get("why") or {}, ensure_ascii=False),
                    ),
                )
        return int(sid)

    def clear_cv_previews(self) -> int:
        with closing(self._conn()) as conn, conn:
            return conn.execute("UPDATE searches SET cv_preview='' WHERE cv_preview<>''").rowcount

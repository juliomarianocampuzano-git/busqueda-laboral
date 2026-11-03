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
            CREATE TABLE IF NOT EXISTS applications (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              position TEXT NOT NULL,
              company TEXT NOT NULL DEFAULT '',
              apply_url TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'guardada',
              notes TEXT NOT NULL DEFAULT ''
            );
            CREATE UNIQUE INDEX IF NOT EXISTS applications_url
              ON applications(apply_url) WHERE apply_url <> '';
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

    # ---------- postulaciones ----------
    def _application(self, conn, app_id: int) -> dict | None:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        return dict(row) if row else None

    def list_applications(self) -> list[dict]:
        with closing(self._conn()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM applications ORDER BY updated_at DESC, id DESC")
            return [dict(row) for row in rows]

    def add_application(self, position: str, company: str, apply_url: str) -> tuple[dict, bool]:
        """Guardar un aviso. Si el enlace ya estaba guardado, devuelve el existente."""
        with closing(self._conn()) as conn, conn:
            if apply_url:
                found = conn.execute(
                    "SELECT id FROM applications WHERE apply_url = ?", (apply_url,)
                ).fetchone()
                if found:
                    return self._application(conn, found[0]), False
            app_id = conn.execute(
                "INSERT INTO applications(position, company, apply_url) VALUES (?, ?, ?)",
                (position, company, apply_url),
            ).lastrowid
            return self._application(conn, app_id), True

    def update_application(self, app_id: int, changes: dict) -> dict | None:
        fields = {key: changes[key] for key in ("status", "notes") if key in changes}
        with closing(self._conn()) as conn, conn:
            if fields:
                sets = ", ".join(f"{key} = ?" for key in fields)
                conn.execute(
                    f"UPDATE applications SET {sets}, updated_at = datetime('now') WHERE id = ?",
                    (*fields.values(), app_id),
                )
            return self._application(conn, app_id)

    def delete_application(self, app_id: int) -> bool:
        with closing(self._conn()) as conn, conn:
            return conn.execute("DELETE FROM applications WHERE id = ?", (app_id,)).rowcount > 0

    def clear_cv_previews(self) -> int:
        with closing(self._conn()) as conn, conn:
            return conn.execute("UPDATE searches SET cv_preview='' WHERE cv_preview<>''").rowcount

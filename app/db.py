"""수집한 글 제목을 SQLite에 쌓는다."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def to_public(row: dict) -> dict:
    return {
        "id": row["id"],
        "source": row["source"],
        "externalId": row["external_id"],
        "title": row["title"],
        "excerpt": row.get("excerpt") or "",
        "author": row.get("author") or "익명",
        "company": row.get("company") or "",
        "ip": row.get("ip") or "",
        "badge": row.get("badge") or "",
        "url": row["url"],
        "postedLabel": row.get("posted_label") or "",
        "postedAt": row.get("posted_at") or "",
        "views": row.get("views"),
        "recommends": row.get("recommends"),
        "comments": row.get("comments"),
        "firstSeenAt": row["first_seen_at"],
        "isSeed": bool(row.get("is_seed")),
    }


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA busy_timeout=5000;
                CREATE TABLE IF NOT EXISTS posts (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  source TEXT NOT NULL,
                  external_id TEXT NOT NULL,
                  title TEXT NOT NULL,
                  excerpt TEXT,
                  author TEXT,
                  company TEXT,
                  ip TEXT,
                  badge TEXT,
                  url TEXT NOT NULL,
                  posted_label TEXT,
                  posted_at TEXT,
                  views INTEGER,
                  recommends INTEGER,
                  comments INTEGER,
                  first_seen_at TEXT NOT NULL,
                  is_seed INTEGER NOT NULL DEFAULT 0,
                  UNIQUE(source, external_id)
                );
                CREATE INDEX IF NOT EXISTS idx_posts_source ON posts(source);
                CREATE INDEX IF NOT EXISTS idx_posts_seen ON posts(first_seen_at);
                CREATE TABLE IF NOT EXISTS meta (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                );
                """
            )
            self.conn.commit()

    def set_meta_once(self, key: str, value: str) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO NOTHING",
                (key, value),
            )
            self.conn.commit()

    def get_meta(self, key: str) -> str | None:
        with self.lock:
            row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else row["value"]

    def count(self, *, source: str | None = None, since: str | None = None, live_only: bool = False) -> int:
        clauses: list[str] = []
        params: list[object] = []
        if source:
            clauses.append("source = ?")
            params.append(source)
        if since:
            clauses.append("first_seen_at >= ?")
            params.append(since)
        if live_only:
            clauses.append("is_seed = 0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.lock:
            row = self.conn.execute(f"SELECT COUNT(*) AS n FROM posts {where}", params).fetchone()
        return int(row["n"])

    def insert_new(self, posts: list[dict], *, is_seed: bool) -> list[dict]:
        now = utc_now()
        inserted: list[dict] = []
        with self.lock:
            try:
                for post in posts:
                    cur = self.conn.execute(
                        """
                        INSERT OR IGNORE INTO posts (
                          source, external_id, title, excerpt, author, company, ip, badge,
                          url, posted_label, posted_at, views, recommends, comments,
                          first_seen_at, is_seed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            post["source"],
                            post["external_id"],
                            post["title"],
                            post.get("excerpt") or "",
                            post.get("author") or "",
                            post.get("company") or "",
                            post.get("ip") or "",
                            post.get("badge") or "",
                            post["url"],
                            post.get("posted_label") or "",
                            post.get("posted_at") or "",
                            post.get("views"),
                            post.get("recommends"),
                            post.get("comments"),
                            now,
                            1 if is_seed else 0,
                        ),
                    )
                    if cur.rowcount:
                        row = dict(post)
                        row["id"] = cur.lastrowid
                        row["first_seen_at"] = now
                        row["is_seed"] = 1 if is_seed else 0
                        inserted.append(row)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
        return inserted

    def count_query(self, *, q: str = "", source: str = "") -> int:
        clauses, params = self._filters(q, source)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.lock:
            row = self.conn.execute(f"SELECT COUNT(*) AS n FROM posts {where}", params).fetchone()
        return int(row["n"])

    def list_posts(
        self,
        *,
        q: str = "",
        source: str = "",
        limit: int = 120,
        before_id: int | None = None,
        after_id: int | None = None,
    ) -> list[dict]:
        clauses, params = self._filters(q, source)
        order = "DESC"
        if before_id is not None:
            clauses.append("id < ?")
            params.append(before_id)
        if after_id is not None:
            clauses.append("id > ?")
            params.append(after_id)
            order = "ASC"
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit = max(1, min(int(limit), 300))
        params.append(limit)
        with self.lock:
            rows = self.conn.execute(
                f"SELECT * FROM posts {where} ORDER BY id {order} LIMIT ?",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def _filters(self, q: str, source: str) -> tuple[list[str], list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if q:
            escaped = q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{escaped}%"
            clauses.append(
                "("
                "LOWER(title) LIKE ? ESCAPE '\\' OR LOWER(excerpt) LIKE ? ESCAPE '\\' "
                "OR LOWER(author) LIKE ? ESCAPE '\\' OR LOWER(company) LIKE ? ESCAPE '\\'"
                ")"
            )
            params.extend([like, like, like, like])
        if source in {"dc", "blind"}:
            clauses.append("source = ?")
            params.append(source)
        return clauses, params

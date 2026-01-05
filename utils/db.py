import csv
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from flask import current_app, g


def _database_path() -> Path:
    """Resolve the SQLite path, favoring explicit env overrides."""

    path_override = os.getenv("DATABASE_PATH", "").strip()
    if path_override:
        return Path(path_override).expanduser()

    instance_path = Path(current_app.instance_path)
    db_name = os.getenv("DATABASE_NAME", "gra.sqlite3").strip() or "gra.sqlite3"
    return instance_path / db_name


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = _database_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_: Optional[BaseException] = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_all(query: str, params: Iterable[Any] | None = None) -> list[sqlite3.Row]:
    db = get_db()
    cur = db.execute(query, params or [])
    rows = cur.fetchall()
    cur.close()
    return rows


def query_one(query: str, params: Iterable[Any] | None = None) -> Optional[sqlite3.Row]:
    db = get_db()
    cur = db.execute(query, params or [])
    row = cur.fetchone()
    cur.close()
    return row


def execute(query: str, params: Iterable[Any] | None = None) -> int:
    db = get_db()
    cur = db.execute(query, params or [])
    db.commit()
    lastrowid = cur.lastrowid
    cur.close()
    return lastrowid


def init_db() -> None:
    db = get_db()
    with closing(db.cursor()) as cursor:
        # posts
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            excerpt TEXT NOT NULL,
            content TEXT NOT NULL,
            cover_url TEXT,
            tags TEXT,
            published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            publish_date TEXT,
            meta_title TEXT,
            meta_description TEXT,
            hero_kicker TEXT,
            hero_style TEXT,
            highlight_quote TEXT,
            summary_points TEXT,
            cta_label TEXT,
            cta_url TEXT,
            featured INTEGER NOT NULL DEFAULT 0
        )
        """)

        # post likes (one like per user per post enforced by UNIQUE constraint)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS post_likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(post_id, user_id),
            FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_post_likes_post_id ON post_likes(post_id)")

        # contact messages  ✅ separate execute
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT
        )
        """)

        db.commit()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            site_name TEXT NOT NULL,
            site_description TEXT NOT NULL,
            base_url TEXT NOT NULL
        )
        """)

        cursor.execute("""
        INSERT OR IGNORE INTO settings (id, site_name, site_description, base_url)
        VALUES (1, 'Grand River Analytics',
                'Independent equity research across financials, technology, and consumer sectors.',
                'https://example.com')
        """)

        db.commit()

    seed_posts()


def ensure_post_columns(db: sqlite3.Connection) -> None:
    desired_columns = {
        "meta_title": "TEXT",
        "meta_description": "TEXT",
        "hero_kicker": "TEXT",
        "hero_style": "TEXT",
        "highlight_quote": "TEXT",
        "summary_points": "TEXT",
        "cta_label": "TEXT",
        "cta_url": "TEXT",
        "featured": "INTEGER NOT NULL DEFAULT 0",
    }
    existing_cursor = db.execute("PRAGMA table_info(posts)")
    existing_columns = {row[1] for row in existing_cursor.fetchall()}
    existing_cursor.close()
    for column, definition in desired_columns.items():
        if column not in existing_columns:
            db.execute(f"ALTER TABLE posts ADD COLUMN {column} {definition}")
    db.commit()


def seed_posts() -> None:
    existing = query_one("SELECT COUNT(*) as count FROM posts")
    if existing and existing["count"] > 0:
        db = get_db()
        ensure_post_columns(db)
        return

    now = datetime.utcnow().isoformat()
    execute(
        """
        INSERT INTO posts (title, slug, excerpt, content, cover_url, tags, published, created_at, updated_at, publish_date, featured)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 1)
        """,
        (
            "Welcome to Grand River Analytics",
            "welcome-to-grand-river-analytics",
            "Independent equity research built by students.",
            "<p>Start here.</p>",
            "",
            "Intro,Research",
            now,
            now,
            now,
        ),
    )

    db = get_db()
    ensure_post_columns(db)


def backup_posts_to_csv(output_path: str | None = None) -> str:
    rows = query_all("SELECT * FROM posts ORDER BY created_at DESC")
    if output_path is None:
        output_path = os.path.join(current_app.instance_path, "posts_backup.csv")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if rows:
            writer.writerow(rows[0].keys())
            for row in rows:
                writer.writerow([row[key] for key in row.keys()])

    return output_path

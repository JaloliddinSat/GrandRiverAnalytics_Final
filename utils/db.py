import csv
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from flask import current_app, g


def _database_path() -> Path:
    url_override = os.getenv("DATABASE_URL", "").strip()
    if url_override.lower().startswith("sqlite:///"):
        candidate = url_override.split("sqlite:///", 1)[1]
        if candidate:
            return Path(candidate)
    path_override = os.getenv("DATABASE_PATH", "").strip()
    if path_override:
        return Path(path_override)
    database_name = os.getenv("DATABASE", "grandriver.db")
    if current_app:
        return Path(current_app.instance_path) / database_name
    return Path(database_name)


def _backup_csv_path() -> Path:
    override = os.getenv("POSTS_BACKUP_CSV", "").strip()
    if override:
        return Path(override)
    database_dir = _database_path().parent
    return database_dir / "posts_backup.csv"


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = _database_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
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
        cursor.execute(
            """
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
            """
        )
        ensure_post_columns(db)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                site_name TEXT NOT NULL,
                site_description TEXT NOT NULL,
                base_url TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            INSERT OR IGNORE INTO settings (id, site_name, site_description, base_url)
            VALUES (1, 'Grand River Analytics', 'Independent equity research across financials, technology, and consumer sectors.', 'https://example.com')
            """
        )
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
        return

    now = datetime.utcnow().isoformat()
    posts = [
        {
            "title": "AAPL: Services Momentum and Valuation Floors",
            "slug": "aapl-services-momentum",
            "excerpt": "Assessing how Apple's services mix and installed base durability create valuation support despite cyclical hardware headwinds.",
            "content": "<p>Apple's services momentum continues to offset hardware volatility while management leans on ecosystem stickiness...</p>",
            "cover_url": "https://images.unsplash.com/photo-1520607162513-77705c0f0d4a?auto=format&fit=crop&w=1200&q=80",
            "tags": "Large-Cap, Tech",
            "published": 1,
            "publish_date": "2024-01-15T12:00:00Z",
            "hero_kicker": "Deep Dive",
            "hero_style": "midnight",
            "highlight_quote": "Services mix has widened Apple's defensibility, underpinning floor valuation multiples.",
            "summary_points": "Services ARR now >$100B\nHardware elasticity contained by trade-in programs",
            "cta_label": "Read full thesis",
            "cta_url": "/post/aapl-services-momentum",
            "featured": 1,
        },
        {
            "title": "JPM: NII Trajectory and Credit Normalization",
            "slug": "jpm-nii-trajectory",
            "excerpt": "Parsing JPMorgan's net interest income outlook alongside reserve releases as consumer credit normalizes.",
            "content": "<p>JPMorgan's guidance implies manageable NII compression as deposit betas rise and card delinquencies revert toward historical levels...</p>",
            "cover_url": "https://images.unsplash.com/photo-1454165205744-3b78555e5572?auto=format&fit=crop&w=1200&q=80",
            "tags": "Large-Cap, Financials",
            "published": 1,
            "publish_date": "2024-01-22T12:00:00Z",
            "hero_kicker": "Banking",
            "hero_style": "slate",
            "summary_points": "Deposit mix shifting to interest-bearing\nCredit normalization manageable vs reserves",
        },
        {
            "title": "MSFT: Copilot Monetization Pathways",
            "slug": "msft-copilot-monetization",
            "excerpt": "Examining Microsoft's early traction with Copilot SKUs and the multi-year revenue opportunity.",
            "content": "<p>Microsoft's AI positioning remains differentiated as enterprise pilots convert to paid commitments and attach rates expand across the Microsoft 365 base...</p>",
            "cover_url": "https://images.unsplash.com/photo-1517430816045-df4b7de11d1d?auto=format&fit=crop&w=1200&q=80",
            "tags": "Large-Cap, Tech",
            "published": 1,
            "publish_date": "2024-02-01T12:00:00Z",
            "hero_kicker": "Software",
            "summary_points": "Copilot ARPU uplift still in early innings\nAzure AI services accelerating cloud growth",
        },
        {
            "title": "XOM: Capex Discipline vs. Price Deck",
            "slug": "xom-capex-discipline",
            "excerpt": "Evaluating Exxon Mobil's capital allocation against a volatile crude price deck and shareholder returns.",
            "content": "<p>Exxon Mobil's capital discipline anchors free cash flow resilience with upstream mix shifting toward low breakeven barrels...</p>",
            "cover_url": "https://images.unsplash.com/photo-1509395176047-4a66953fd231?auto=format&fit=crop&w=1200&q=80",
            "tags": "Energy, Large-Cap",
            "published": 1,
            "publish_date": "2024-02-08T12:00:00Z",
            "hero_kicker": "Energy",
            "hero_style": "midnight",
        },
        {
            "title": "COST: Traffic Resilience and Mix",
            "slug": "cost-traffic-resilience",
            "excerpt": "Understanding Costco's traffic resilience as mix shifts toward services and higher-margin categories.",
            "content": "<p>Costco continues to drive strong traffic growth as membership economics fund investments in price leadership and ancillary services expansion...</p>",
            "cover_url": "https://images.unsplash.com/photo-1515169067865-5387ec356754?auto=format&fit=crop&w=1200&q=80",
            "tags": "Consumer, Large-Cap",
            "published": 1,
            "publish_date": "2024-02-15T12:00:00Z",
            "hero_kicker": "Consumer",
            "hero_style": "slate",
        },
    ]

    for post in posts:
        execute(
            """
            INSERT INTO posts (
                title,
                slug,
                excerpt,
                content,
                cover_url,
                tags,
                published,
                created_at,
                updated_at,
                publish_date,
                meta_title,
                meta_description,
                hero_kicker,
                hero_style,
                highlight_quote,
                summary_points,
                cta_label,
                cta_url,
                featured
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post["title"],
                post["slug"],
                post["excerpt"],
                post["content"],
                post["cover_url"],
                post["tags"],
                post["published"],
                now,
                now,
                post["publish_date"],
                post.get("meta_title"),
                post.get("meta_description"),
                post.get("hero_kicker"),
                post.get("hero_style"),
                post.get("highlight_quote"),
                post.get("summary_points"),
                post.get("cta_label"),
                post.get("cta_url"),
                post.get("featured", 0),
            ),
        )

    get_db().commit()
    backup_posts_to_csv()


def backup_posts_to_csv() -> None:
    try:
        rows = query_all(
            """
            SELECT id, title, slug, excerpt, content, cover_url, tags, published, created_at, updated_at,
                   publish_date, meta_title, meta_description, hero_kicker, hero_style, highlight_quote,
                   summary_points, cta_label, cta_url, featured
            FROM posts
            ORDER BY id
            """
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        if current_app:
            current_app.logger.exception("Unable to fetch posts for CSV backup: %s", exc)
        return

    csv_path = _backup_csv_path()
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "title",
        "slug",
        "excerpt",
        "content",
        "cover_url",
        "tags",
        "published",
        "created_at",
        "updated_at",
        "publish_date",
        "meta_title",
        "meta_description",
        "hero_kicker",
        "hero_style",
        "highlight_quote",
        "summary_points",
        "cta_label",
        "cta_url",
        "featured",
    ]

    try:
        with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                row_dict = dict(row)
                writer.writerow({field: row_dict.get(field) for field in fieldnames})
    except Exception as exc:  # pragma: no cover - defensive logging
        if current_app:
            current_app.logger.exception("Unable to write posts CSV backup: %s", exc)

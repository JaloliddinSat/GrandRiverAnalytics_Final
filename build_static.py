"""Static site generator for Netlify deployments."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from flask import Response

from app import create_app
from utils.db import query_all

OUTPUT_DIR = Path(os.getenv("NETLIFY_PUBLISH_DIR", "netlify_build"))


def ensure_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_response(path: str, response: Response) -> None:
    destination = OUTPUT_DIR / path.lstrip("/")
    if path.endswith("/") and not path.endswith("//"):
        destination = destination / "index.html"
    ensure_directory(destination)
    destination.write_bytes(response.get_data())


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def export_routes() -> None:
    app = create_app()
    with app.app_context():
        client = app.test_client()
        clean_output_dir()

        static_src = Path(app.static_folder or "static")
        shutil.copytree(static_src, OUTPUT_DIR / "static")

        published_posts = query_all(
            "SELECT slug FROM posts WHERE published = 1 ORDER BY COALESCE(publish_date, created_at) DESC"
        )
        post_slugs = [row["slug"] for row in published_posts]

        routes = [
            "/",
            "/blog",
            "/team",
            "/contact",
            "/admin-unavailable/",
            "/rss.xml",
            "/sitemap.xml",
            "/robots.txt",
        ]

        total_posts = len(post_slugs)
        page_size = 10
        total_pages = (total_posts + page_size - 1) // page_size
        for page in range(2, total_pages + 1):
            routes.append(f"/blog?{urlencode({'page': page})}")

        for slug in post_slugs:
            routes.append(f"/post/{slug}")

        for route in routes:
            response = client.get(route)
            if response.status_code >= 400:
                raise RuntimeError(f"Failed to render {route}: {response.status_code}")

            if route.startswith("/blog?"):
                query = parse_qs(route.partition("?")[2])
                page = query.get("page", ["1"])[0]
                target = f"/blog/page/{page}/"
            elif route.startswith("/post/"):
                target = f"{route}/"
            else:
                if route.endswith(".xml") or route.endswith(".txt"):
                    target = route
                elif route.endswith("/"):
                    target = route
                else:
                    target = f"{route}/"

            write_response(target, response)

        headers_lines: list[str] = []
        header_map = {
            "/rss.xml": {"Content-Type": "application/rss+xml"},
            "/sitemap.xml": {"Content-Type": "application/xml"},
            "/robots.txt": {"Content-Type": "text/plain"},
        }
        for path, values in header_map.items():
            headers_lines.append(path)
            headers_lines.extend(f"  {key}: {value}" for key, value in values.items())
            headers_lines.append("")
        (OUTPUT_DIR / "_headers").write_text("\n".join(headers_lines).strip() + "\n")


if __name__ == "__main__":
    export_routes()

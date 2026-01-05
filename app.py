from __future__ import annotations
from flask import redirect, url_for

import json
import math
import os
import re
import secrets
import sqlite3
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from utils import seo
from utils.auth import (
    csrf_protect,
    ensure_admin_password,
    generate_csrf_token,
    login_required,
    verify_password,
)
from utils.db import (
    backup_posts_to_csv,
    close_db,
    execute,
    get_db,
    init_db,
    query_all,
    query_one,
)
from utils.emailer import send_contact_email


load_dotenv()


def _resolve_secret_key_path(instance_path: str) -> str:
    explicit_path = os.getenv("SECRET_KEY_PATH", "").strip()
    if explicit_path:
        return explicit_path
    return os.path.join(instance_path, "secret_key.txt")


def _ensure_secret_key(instance_path: str) -> str:
    key_path = _resolve_secret_key_path(instance_path)
    try:
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        if os.path.exists(key_path):
            with open(key_path, "r", encoding="utf-8") as fh:
                existing = fh.read().strip()
                if existing:
                    return existing
        generated = secrets.token_urlsafe(64)
        with open(key_path, "w", encoding="utf-8") as fh:
            fh.write(generated)
        return generated
    except OSError:
        return secrets.token_urlsafe(64)


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    os.makedirs(app.instance_path, exist_ok=True)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or _ensure_secret_key(app.instance_path)
    app.config["BASE_URL"] = os.getenv("BASE_URL", "https://example.com").rstrip("/")
    app.config["TINYMCE_API_KEY"] = os.getenv("TINYMCE_API_KEY", "").strip()
    app.config["ADOBE_TYPEKIT_ID"] = os.getenv("ADOBE_TYPEKIT_ID", "").strip()

    max_form_mb_raw = os.getenv("MAX_FORM_MEMORY_MB")
    if max_form_mb_raw is not None:
        max_form_mb = max_form_mb_raw.strip()
        if max_form_mb:
            try:
                parsed_mb = float(max_form_mb)
                max_form_bytes = int(parsed_mb * 1024 * 1024)
            except ValueError:
                app.logger.warning("MAX_FORM_MEMORY_MB is not a number; ignoring override.")
                max_form_bytes = 0
        else:
            max_form_bytes = 0
    else:
        max_form_bytes = 0

    # Always set these keys so request.max_content_length has a safe default.
    if max_form_bytes and max_form_bytes > 0:
        app.config["MAX_FORM_MEMORY_SIZE"] = max_form_bytes
        app.config["MAX_CONTENT_LENGTH"] = max_form_bytes
    else:
        app.config["MAX_FORM_MEMORY_SIZE"] = None
        app.config["MAX_CONTENT_LENGTH"] = None

    admin_hash, used_default_password = ensure_admin_password()
    app.config["ADMIN_PASSWORD_HASH"] = admin_hash

    @app.before_request
    def before_request() -> None:  # type: ignore[override]
        g.settings = get_settings()
        csrf_protect()

        uid = request.cookies.get("gra_uid")
        if not uid:
            uid = secrets.token_urlsafe(16)
            g._set_gra_uid = uid  # type: ignore[attr-defined]
        g.anon_user_id = uid  # type: ignore[attr-defined]

    @app.after_request
    def persist_anon_user_id(response: Response) -> Response:  # type: ignore[override]
        uid = getattr(g, "_set_gra_uid", None)
        if uid:
            response.set_cookie(
                "gra_uid",
                uid,
                max_age=60 * 60 * 24 * 365 * 2,
                httponly=True,
                samesite="Lax",
                secure=request.is_secure,
            )
        return response

    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()
        if used_default_password:
            app.logger.warning("ADMIN_PASSWORD not set. Using default development password.")

    register_routes(app)
    register_filters(app)
    register_context_processors(app)

    return app


def get_settings() -> dict[str, Any]:
    if hasattr(g, "_settings"):
        return g._settings  # type: ignore[attr-defined]
    row = query_one("SELECT site_name, site_description, base_url FROM settings WHERE id = 1")
    if row:
        settings = dict(row)
    else:
        settings = {
            "site_name": "Grand River Analytics",
            "site_description": "Independent student-led equity research and investment insights.",
            "base_url": os.getenv("BASE_URL", "https://example.com").rstrip("/"),
        }
    settings["base_url"] = (settings.get("base_url") or "").rstrip("/") or os.getenv("BASE_URL", "https://example.com").rstrip("/")
    g._settings = settings  # type: ignore[attr-defined]
    return settings


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"[\s_-]+", "-", value)
    return value.strip("-")


def normalize_hero_style(value: str | None) -> str:
    allowed = {"light", "slate", "midnight"}
    if not value:
        return "light"
    normalized = value.strip().lower()
    return normalized if normalized in allowed else "light"


def serialize_post(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        data = dict(row)
    else:
        data = {key: row[key] for key in row.keys()}
    data["hero_style"] = normalize_hero_style(data.get("hero_style"))
    return data


def resolve_tinymce_assets() -> tuple[str, str]:
    tinymce_api_key = os.getenv("TINYMCE_API_KEY", "").strip()
    if tinymce_api_key:
        return "https://cdn.tiny.cloud/1/{}/tinymce/6/tinymce.min.js".format(tinymce_api_key), tinymce_api_key
    return "", ""


def resolve_adobe_fonts_url() -> str:
    kit_id = os.getenv("ADOBE_TYPEKIT_ID", "").strip()
    if kit_id:
        return f"https://use.typekit.net/{kit_id}.css"
    return ""


def register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        settings = get_settings()
        tinymce_script, tinymce_api_key = resolve_tinymce_assets()
        return {
            "settings": settings,
            "current_year": datetime.utcnow().year,
            "base_url": settings.get("base_url", app.config["BASE_URL"]),
            "csrf_token": generate_csrf_token,
            "nav_active": lambda name: "aria-current=\"page\"" if request.endpoint == name else "",
            "tinymce_script_url": tinymce_script,
            "tinymce_api_key": tinymce_api_key,
            "adobe_fonts_url": resolve_adobe_fonts_url(),
        }


def register_filters(app: Flask) -> None:
    @app.template_filter("format_date")
    def format_date(value: str | None) -> str:
        if not value:
            return ""
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.strftime("%B %d, %Y")
        except ValueError:
            return value

    @app.template_filter("tag_list")
    def tag_list(value: str | None) -> list[str]:
        if not value:
            return []
        return [t.strip() for t in value.split(",") if t.strip()]


def estimate_read_time(content: str) -> int:
    if not content:
        return 1
    words = len(re.findall(r"\w+", content))
    return max(1, math.ceil(words / 200))


def register_routes(app: Flask) -> None:
    @app.route("/")
    def home() -> str:
        settings = get_settings()
        posts = [
            serialize_post(row)
            for row in query_all(
                """
                SELECT * FROM posts
                WHERE published = 1
                ORDER BY featured DESC, COALESCE(publish_date, created_at) DESC
                LIMIT 6
                """
            )
        ]
        canonical = settings["base_url"].rstrip("/")
        meta = seo.build_meta(
            title=settings["site_name"],
            description=settings["site_description"],
            canonical=canonical,
            image_url=f"{request.host_url.rstrip('/')}/static/img/logo.svg",
        )
        breadcrumbs = seo.jsonld_breadcrumbs(settings["base_url"], [("Home", "/")])
        org_json = seo.jsonld_organization(
            settings["base_url"],
            settings["site_name"],
            settings["site_description"],
            f"{request.host_url.rstrip('/')}/static/img/logo.svg",
        )
        website_json = seo.jsonld_website_search(settings["base_url"])
        return render_template(
            "home.html",
            posts=posts,
            meta=meta,
            breadcrumbs=breadcrumbs,
            org_json=org_json,
            website_json=website_json,
        )

    @app.route("/blog")
    def blog_index() -> Response:
        return redirect(url_for("reports_index"), code=301)

    @app.route("/reports")
    def reports_index() -> str:
        settings = get_settings()
        posts = [
            serialize_post(row)
            for row in query_all(
                """
                SELECT * FROM posts
                WHERE published = 1
                ORDER BY COALESCE(publish_date, created_at) DESC
                """
            )
        ]

        all_tags = set()
        for post in posts:
            for tag in (post.get("tags") or "").split(","):
                cleaned = tag.strip()
                if cleaned:
                    all_tags.add(cleaned)

        canonical = f"{settings['base_url']}/reports"
        meta = seo.build_meta(
            title=f"Reports · {settings['site_name']}",
            description="Browse research reports and long-form equity writeups.",
            canonical=canonical,
        )
        breadcrumbs = seo.jsonld_breadcrumbs(settings["base_url"], [("Home", "/"), ("Reports", "/reports")])
        website_json = seo.jsonld_website_search(settings["base_url"])

        page = request.args.get("page", "1").strip()
        try:
            page_num = max(1, int(page))
        except ValueError:
            page_num = 1
        per_page = 9
        total_count = len(posts)
        total_pages = max(1, math.ceil(total_count / per_page))
        page_num = min(page_num, total_pages)

        start = (page_num - 1) * per_page
        end = start + per_page
        paginated_posts = posts[start:end]
        prev_url = url_for("reports_index", page=page_num - 1) if page_num > 1 else None
        next_url = url_for("reports_index", page=page_num + 1) if page_num < total_pages else None

        return render_template(
            "reports.html",
            posts=paginated_posts,
            total_pages=total_pages,
            meta=meta,
            breadcrumbs=breadcrumbs,
            website_json=website_json,
            all_tags=sorted(all_tags),
            prev_url=prev_url,
            next_url=next_url,
        )

    @app.route("/post/<slug>")
    def post_detail(slug: str) -> str:
        row = query_one("SELECT * FROM posts WHERE slug = ?", (slug,))
        if not row:
            abort(404)
        post = serialize_post(row)
        if not post.get("published") and not session.get("admin_authenticated"):
            abort(404)
        settings = get_settings()
        canonical = f"{settings['base_url']}/post/{post['slug']}"
        meta_title = post.get("meta_title") or post["title"]
        meta_description = post.get("meta_description") or post.get("excerpt") or settings["site_description"]

        meta = seo.build_meta(
            title=f"{meta_title} · {settings['site_name']}",
            description=meta_description,
            canonical=canonical,
            image_url=post.get("cover_url"),
            og_type="article",
        )
        breadcrumbs = seo.jsonld_breadcrumbs(
            settings["base_url"],
            [("Home", "/"), ("Reports", "/reports"), (post["title"], f"/post/{post['slug']}")],
        )
        website_json = seo.jsonld_website_search(settings["base_url"])
        blog_json = seo.jsonld_blogposting(settings["base_url"], post, settings["site_name"], settings["site_description"])
        read_time = estimate_read_time(post.get("content", ""))
        summary_points = [point.strip() for point in (post.get("summary_points") or "").splitlines() if point.strip()]
        hero_style = normalize_hero_style(post.get("hero_style"))

        like_count_row = query_one("SELECT COUNT(*) as count FROM post_likes WHERE post_id = ?", (row["id"],))
        like_count = int(like_count_row["count"]) if like_count_row else 0
        liked = bool(query_one("SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?", (row["id"], g.anon_user_id)))

        more_posts = [
            serialize_post(p)
            for p in query_all(
                """
                SELECT * FROM posts
                WHERE published = 1 AND slug != ?
                ORDER BY COALESCE(publish_date, created_at) DESC
                LIMIT 3
                """,
                (post["slug"],),
            )
        ]

        return render_template(
            "post.html",
            post=post,
            meta=meta,
            breadcrumbs=breadcrumbs,
            website_json=website_json,
            blog_json=blog_json,
            read_time=read_time,
            more_posts=more_posts,
            summary_points=summary_points,
            hero_style=hero_style,
            like_count=like_count,
            liked=liked,
            preview=False,
        )

    @app.route("/api/post/<slug>/like", methods=["POST"])
    def post_like_api(slug: str) -> Response:
        row = query_one("SELECT id, slug FROM posts WHERE slug = ?", (slug,))
        if not row:
            abort(404)

        action = (request.form.get("action") or "toggle").strip().lower()
        post_id = int(row["id"])
        user_id = getattr(g, "anon_user_id", None)
        if not user_id:
            abort(Response("Missing user id", status=400))

        currently_liked = bool(query_one(
            "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
            (post_id, user_id),
        ))
        if action == "toggle":
            action = "unlike" if currently_liked else "like"

        db = get_db()
        liked = currently_liked

        if action == "like":
            try:
                db.execute(
                    "INSERT INTO post_likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
                    (post_id, user_id, f"{datetime.utcnow().isoformat()}Z"),
                )
                db.commit()
            except sqlite3.IntegrityError:
                # Already liked (unique constraint); treat as idempotent.
                pass
            liked = True
        elif action == "unlike":
            db.execute("DELETE FROM post_likes WHERE post_id = ? AND user_id = ?", (post_id, user_id))
            db.commit()
            liked = False
        else:
            abort(Response("Invalid action", status=400))

        count_row = query_one("SELECT COUNT(*) as count FROM post_likes WHERE post_id = ?", (post_id,))
        count = int(count_row["count"]) if count_row else 0

        return jsonify({"liked": liked, "count": count})

    @app.route("/team")
    def team() -> str:
        settings = get_settings()
        canonical = f"{settings['base_url']}/team"
        meta = seo.build_meta(
            title=f"Team · {settings['site_name']}",
            description="Meet the sector specialists behind our research.",
            canonical=canonical,
        )
        breadcrumbs = seo.jsonld_breadcrumbs(settings["base_url"], [("Home", "/"), ("Team", "/team")])
        website_json = seo.jsonld_website_search(settings["base_url"])
        return render_template(
            "team.html",
            meta=meta,
            breadcrumbs=breadcrumbs,
            website_json=website_json,
        )

    @app.route("/contact", methods=["GET", "POST"])
    def contact() -> str:
        settings = get_settings()
        canonical = f"{settings['base_url'].rstrip('/')}/contact"

        meta = seo.build_meta(
            title=f"Contact · {settings['site_name']}",
            description="Get in touch with Grand River Analytics.",
            canonical=canonical,
            image_url=None,
        )

        breadcrumbs = seo.jsonld_breadcrumbs(
            settings["base_url"],
            [("Home", "/"), ("Contact", "/contact")],
        )

        website_json = seo.jsonld_website_search(settings["base_url"])

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            message = request.form.get("message", "").strip()

            if not name or not email or not message:
                flash("Please fill out all fields.", "error")
            else:
                ip = request.headers.get("X-Forwarded-For", request.remote_addr)
                user_agent = request.headers.get("User-Agent", "")
                now = datetime.utcnow().isoformat()

                execute(
                    """
                    INSERT INTO contact_messages (name, email, message, created_at, ip, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (name, email, message, now, ip, user_agent),
                )

                try:
                    send_contact_email(name, email, message)
                except Exception:
                    app.logger.exception("Failed sending contact email.")
                flash("Thanks — we received your message.", "success")
                return redirect(url_for("contact"))

        return render_template(
            "contact.html",
            meta=meta,
            breadcrumbs=breadcrumbs,
            website_json=website_json,
        )

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login() -> str:
        settings = get_settings()
        canonical = f"{settings['base_url']}/admin/login"
        meta = seo.build_meta(
            title=f"Admin Login · {settings['site_name']}",
            description="Login to manage posts.",
            canonical=canonical,
        )
        breadcrumbs = seo.jsonld_breadcrumbs(settings["base_url"], [("Home", "/"), ("Admin", "/admin"), ("Login", "/admin/login")])
        website_json = seo.jsonld_website_search(settings["base_url"])

        if request.method == "POST":
            password = request.form.get("password", "")
            if verify_password(password, current_app_password_hash(app)):
                session["admin_authenticated"] = True
                flash("Logged in.", "success")
                return redirect(url_for("admin_dashboard"))
            flash("Incorrect password.", "error")

        return render_template(
            "admin/login.html",
            meta=meta,
            breadcrumbs=breadcrumbs,
            website_json=website_json,
        )

    # --- rest of your file unchanged below (admin routes, save handlers, etc.) ---

    @app.route("/admin/preview/<int:post_id>")
    @login_required
    def admin_preview(post_id: int) -> str:
        row = query_one("SELECT * FROM posts WHERE id = ?", (post_id,))
        if not row:
            abort(404)
        post = serialize_post(row)
        settings = get_settings()
        canonical = f"{settings['base_url']}/post/{post['slug']}"
        meta_title = post.get("meta_title") or post["title"]
        meta_description = post.get("meta_description") or post.get("excerpt") or settings["site_description"]
        meta = seo.build_meta(
            title=f"Preview · {meta_title} · {settings['site_name']}",
            description=meta_description,
            canonical=canonical,
            image_url=post.get("cover_url"),
            og_type="article",
        )
        breadcrumbs = seo.jsonld_breadcrumbs(
            settings["base_url"],
            [
                ("Home", "/"),
                ("Blog", "/blog"),
                (post["title"], f"/post/{post['slug']}")
            ],
        )
        website_json = seo.jsonld_website_search(settings["base_url"])
        blog_json = seo.jsonld_blogposting(settings["base_url"], post, settings["site_name"], settings["site_description"])
        read_time = estimate_read_time(post.get("content", ""))
        summary_points = [point.strip() for point in (post.get("summary_points") or "").splitlines() if point.strip()]
        hero_style = normalize_hero_style(post.get("hero_style"))

        like_count_row = query_one("SELECT COUNT(*) as count FROM post_likes WHERE post_id = ?", (row["id"],))
        like_count = int(like_count_row["count"]) if like_count_row else 0
        liked = bool(query_one("SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?", (row["id"], g.anon_user_id)))

        more_posts = [
            serialize_post(p)
            for p in query_all(
                """
                SELECT * FROM posts
                WHERE published = 1 AND slug != ?
                ORDER BY COALESCE(publish_date, created_at) DESC
                LIMIT 3
                """,
                (post["slug"],),
            )
        ]
        return render_template(
            "post.html",
            post=post,
            meta=meta,
            breadcrumbs=breadcrumbs,
            website_json=website_json,
            blog_json=blog_json,
            read_time=read_time,
            more_posts=more_posts,
            summary_points=summary_points,
            hero_style=hero_style,
            like_count=like_count,
            liked=liked,
            preview=True,
        )


def current_app_password_hash(app: Flask) -> str:
    # Helper for admin_login; matches your existing approach
    return app.config.get("ADMIN_PASSWORD_HASH", "")


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

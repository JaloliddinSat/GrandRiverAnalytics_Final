from __future__ import annotations

import math
import os
import re
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
from utils.db import close_db, execute, init_db, query_all, query_one

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", os.urandom(24))
    app.config["BASE_URL"] = os.getenv("BASE_URL", "http://localhost:5000")
    admin_hash, used_default_password = ensure_admin_password()
    app.config["ADMIN_PASSWORD_HASH"] = admin_hash

    os.makedirs(app.instance_path, exist_ok=True)

    @app.before_request
    def before_request() -> None:  # type: ignore[override]
        g.settings = get_settings()
        csrf_protect()

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
            "site_description": "Independent equity research across financials, technology, and consumer sectors.",
            "base_url": os.getenv("BASE_URL", "http://localhost:5000"),
        }
    g._settings = settings  # type: ignore[attr-defined]
    return settings


def register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        settings = get_settings()
        return {
            "settings": settings,
            "current_year": datetime.utcnow().year,
            "base_url": settings.get("base_url", app.config["BASE_URL"]),
            "csrf_token": generate_csrf_token,
            "nav_active": lambda name: "aria-current=\"page\"" if request.endpoint == name else "",
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
        return [tag.strip() for tag in value.split(",") if tag.strip()]


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"[\s_-]+", "-", value)
    return value.strip("-")


def serialize_post(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    return {key: row[key] for key in row.keys()}


def estimate_read_time(html: str) -> int:
    text = re.sub(r"<[^>]+>", " ", html)
    word_count = len(text.split())
    return max(1, math.ceil(word_count / 200))


def register_routes(app: Flask) -> None:
    @app.route("/")
    def home() -> str:
        posts = [serialize_post(row) for row in query_all(
            "SELECT * FROM posts WHERE published = 1 ORDER BY COALESCE(publish_date, created_at) DESC LIMIT 6"
        )]
        settings = get_settings()
        canonical = f"{settings['base_url']}"
        meta = seo.build_meta(
            title=f"{settings['site_name']} · Independent Equity Research",
            description=settings["site_description"],
            canonical=canonical,
            image_url=posts[0].get("cover_url") if posts else None,
        )
        breadcrumbs = seo.jsonld_breadcrumbs(settings["base_url"], [("Home", "/")])
        org_json = seo.jsonld_org(
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
    def blog_index() -> str:
        page = max(1, int(request.args.get("page", 1)))
        per_page = 10
        offset = (page - 1) * per_page
        posts = [
            serialize_post(row)
            for row in query_all(
                """
                SELECT * FROM posts
                WHERE published = 1
                ORDER BY COALESCE(publish_date, created_at) DESC
                LIMIT ? OFFSET ?
                """,
                (per_page, offset),
            )
        ]
        total_row = query_one("SELECT COUNT(*) as count FROM posts WHERE published = 1")
        total = total_row["count"] if total_row else 0
        total_pages = max(1, math.ceil(total / per_page))
        settings = get_settings()
        canonical = f"{settings['base_url']}/blog"
        if page > 1:
            canonical += f"?page={page}"
        meta = seo.build_meta(
            title=f"Blog · {settings['site_name']}",
            description="Stock write-ups and sector notes from Grand River Analytics.",
            canonical=canonical,
        )
        all_tags = set()
        for post in query_all("SELECT tags FROM posts WHERE published = 1"):
            for tag in (post["tags"] or "").split(","):
                tag = tag.strip()
                if tag:
                    all_tags.add(tag)
        breadcrumbs = seo.jsonld_breadcrumbs(settings["base_url"], [("Home", "/"), ("Blog", "/blog")])
        website_json = seo.jsonld_website_search(settings["base_url"])
        prev_url = url_for("blog_index", page=page - 1) if page > 1 else None
        next_url = url_for("blog_index", page=page + 1) if page < total_pages else None
        return render_template(
            "blog_index.html",
            posts=posts,
            page=page,
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
        meta = seo.build_meta(
            title=f"{post['title']} · {settings['site_name']}",
            description=post.get("excerpt", settings["site_description"]),
            canonical=canonical,
            image_url=post.get("cover_url"),
            og_type="article",
        )
        breadcrumbs = seo.jsonld_breadcrumbs(
            settings["base_url"],
            [("Home", "/"), ("Blog", "/blog"), (post["title"], f"/post/{post['slug']}")],
        )
        website_json = seo.jsonld_website_search(settings["base_url"])
        blog_json = seo.jsonld_blogposting(settings["base_url"], post, settings["site_name"], settings["site_description"])
        read_time = estimate_read_time(post.get("content", ""))
        more_posts = [
            serialize_post(p)
            for p in query_all(
                """
                SELECT * FROM posts
                WHERE published = 1 AND slug != ?
                ORDER BY COALESCE(publish_date, created_at) DESC
                LIMIT 3
                """,
                (slug,),
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
        )

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
        team_members = [
            {
                "name": "Alex Morgan",
                "title": "Founder & Lead Analyst",
                "bio": "Covers U.S. financials with a focus on bank asset sensitivity and fintech disruption.",
                "photo": url_for("static", filename="img/team/alex-morgan.svg"),
                "linkedin": "https://www.linkedin.com/",
            },
            {
                "name": "Priya Desai",
                "title": "Technology Strategist",
                "bio": "Analyzes enterprise software and AI monetization frameworks across hyperscalers.",
                "photo": url_for("static", filename="img/team/priya-desai.svg"),
                "linkedin": "https://www.linkedin.com/",
            },
            {
                "name": "Ethan Clarke",
                "title": "Energy & Industrials Analyst",
                "bio": "Frames upstream capital allocation and energy transition implications for integrated majors.",
                "photo": url_for("static", filename="img/team/ethan-clarke.svg"),
                "linkedin": "https://www.linkedin.com/",
            },
        ]
        return render_template(
            "team.html",
            meta=meta,
            breadcrumbs=breadcrumbs,
            website_json=website_json,
            team_members=team_members,
        )

    @app.route("/contact", methods=["GET", "POST"])
    def contact() -> str:
        settings = get_settings()
        canonical = f"{settings['base_url']}/contact"
        meta = seo.build_meta(
            title=f"Contact · {settings['site_name']}",
            description="Connect with the Grand River Analytics team for research access and inquiries.",
            canonical=canonical,
        )
        breadcrumbs = seo.jsonld_breadcrumbs(settings["base_url"], [("Home", "/"), ("Contact", "/contact")])
        website_json = seo.jsonld_website_search(settings["base_url"])
        success = False
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            message = request.form.get("message", "").strip()
            honeypot = request.form.get("website", "").strip()
            if honeypot:
                abort(400)
            if not name or not email or not message:
                flash("All fields are required.", "error")
            else:
                app.logger.info("Contact form submitted by %s <%s>\n%s", name, email, message)
                # TODO: integrate SMTP provider for outbound email delivery.
                flash("Thanks for reaching out. We'll be in touch soon.", "success")
                success = True
        return render_template(
            "contact.html",
            meta=meta,
            breadcrumbs=breadcrumbs,
            website_json=website_json,
            success=success,
        )

    @app.route("/admin-unavailable/")
    def admin_unavailable() -> str:
        settings = get_settings()
        canonical = f"{settings['base_url']}/admin-unavailable/"
        meta = seo.build_meta(
            title=f"Admin Offline · {settings['site_name']}",
            description="The static Netlify deployment exposes only the public site. Run the Flask app on Python-capable hosting to edit posts.",
            canonical=canonical,
        )
        breadcrumbs = seo.jsonld_breadcrumbs(
            settings["base_url"], [("Home", "/"), ("Admin", "/admin-unavailable/")]
        )
        return render_template(
            "admin_unavailable.html",
            meta=meta,
            breadcrumbs=breadcrumbs,
            website_json=seo.jsonld_website_search(settings["base_url"]),
        )

    @app.route("/rss.xml")
    def rss_feed() -> Response:
        settings = get_settings()
        posts = [
            serialize_post(row)
            for row in query_all(
                "SELECT * FROM posts WHERE published = 1 ORDER BY COALESCE(publish_date, created_at) DESC LIMIT 15"
            )
        ]
        xml_items = []
        for post in posts:
            link = f"{settings['base_url']}/post/{post['slug']}"
            publish_date = post.get("publish_date") or post.get("created_at")
            xml_items.append(
                f"""
                <item>
                    <title>{post['title']}</title>
                    <link>{link}</link>
                    <guid>{link}</guid>
                    <pubDate>{publish_date}</pubDate>
                    <description><![CDATA[{post['excerpt']}]]></description>
                </item>
                """
            )
        rss = f"""<?xml version='1.0' encoding='UTF-8'?>
        <rss version='2.0'>
            <channel>
                <title>{settings['site_name']}</title>
                <link>{settings['base_url']}</link>
                <description>{settings['site_description']}</description>
                {''.join(xml_items)}
            </channel>
        </rss>"""
        return Response(rss, mimetype="application/rss+xml")

    @app.route("/sitemap.xml")
    def sitemap() -> Response:
        settings = get_settings()
        urls = [
            {"loc": settings["base_url"] + path, "lastmod": datetime.utcnow().date().isoformat()}
            for path in ["/", "/team", "/contact", "/blog"]
        ]
        for post in query_all("SELECT slug, updated_at FROM posts WHERE published = 1"):
            urls.append(
                {
                    "loc": f"{settings['base_url']}/post/{post['slug']}",
                    "lastmod": (post["updated_at"] or datetime.utcnow().isoformat())[:10],
                }
            )
        xml_urls = [
            f"<url><loc>{url['loc']}</loc><lastmod>{url['lastmod']}</lastmod></url>"
            for url in urls
        ]
        xml = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
            + "".join(xml_urls)
            + "</urlset>"
        )
        return Response(xml, mimetype="application/xml")

    @app.route("/robots.txt")
    def robots() -> Response:
        settings = get_settings()
        content = f"User-agent: *\nAllow: /\nSitemap: {settings['base_url']}/sitemap.xml\n"
        return Response(content, mimetype="text/plain")

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login() -> str:
        if session.get("admin_authenticated"):
            return redirect(url_for("admin_dashboard"))
        error = None
        if request.method == "POST":
            password = request.form.get("password", "")
            if verify_password(password, app.config["ADMIN_PASSWORD_HASH"]):
                session["admin_authenticated"] = True
                flash("Welcome back.", "success")
                return redirect(url_for("admin_dashboard"))
            error = "Invalid credentials."
            flash(error, "error")
        meta = seo.build_meta(
            title="Admin Login",
            description="Secure login for Grand River Analytics.",
            canonical=f"{get_settings()['base_url']}/admin/login",
        )
        return render_template("admin_login.html", error=error, meta=meta)

    @app.route("/admin/logout")
    def admin_logout() -> Response:
        session.pop("admin_authenticated", None)
        flash("You have been logged out.", "success")
        return redirect(url_for("admin_login"))

    @app.route("/admin")
    @login_required
    def admin_dashboard() -> str:
        posts = [
            serialize_post(row)
            for row in query_all(
                "SELECT * FROM posts ORDER BY COALESCE(publish_date, created_at) DESC"
            )
        ]
        meta = seo.build_meta(
            title="Admin Dashboard",
            description="Manage research posts.",
            canonical=f"{get_settings()['base_url']}/admin",
        )
        return render_template("admin_dashboard.html", posts=posts, meta=meta)

    @app.route("/admin/new", methods=["GET", "POST"])
    @login_required
    def admin_new() -> str:
        if request.method == "POST":
            return handle_post_save()
        meta = seo.build_meta(
            title="New Post",
            description="Create a research post.",
            canonical=f"{get_settings()['base_url']}/admin/new",
        )
        return render_template("admin_edit.html", meta=meta, post=None, mode="new")

    @app.route("/admin/edit/<int:post_id>", methods=["GET", "POST"])
    @login_required
    def admin_edit(post_id: int) -> str:
        row = query_one("SELECT * FROM posts WHERE id = ?", (post_id,))
        if not row:
            abort(404)
        post = serialize_post(row)
        if request.method == "POST":
            return handle_post_save(post)
        meta = seo.build_meta(
            title=f"Edit {post['title']}",
            description="Edit research post.",
            canonical=f"{get_settings()['base_url']}/admin/edit/{post_id}",
        )
        return render_template("admin_edit.html", meta=meta, post=post, mode="edit")

    @app.route("/admin/delete/<int:post_id>", methods=["POST"])
    @login_required
    def admin_delete(post_id: int) -> Response:
        execute("DELETE FROM posts WHERE id = ?", (post_id,))
        flash("Post deleted.", "success")
        return redirect(url_for("admin_dashboard"))

    def handle_post_save(existing: dict[str, Any] | None = None):
        title = request.form.get("title", "").strip()
        slug_input = request.form.get("slug", "").strip()
        excerpt = request.form.get("excerpt", "").strip()
        content = request.form.get("content", "").strip()
        cover_url = request.form.get("cover_url", "").strip()
        tags = ", ".join([tag.strip() for tag in request.form.get("tags", "").split(",") if tag.strip()])
        publish_date = request.form.get("publish_date") or datetime.utcnow().isoformat()
        publish_state = request.form.get("action") == "publish"

        if not title or not excerpt or not content:
            flash("Title, excerpt, and content are required.", "error")
            return redirect(request.url)

        slug = slugify(slug_input or title)
        if not slug:
            flash("Unable to generate a slug. Please adjust the title.", "error")
            return redirect(request.url)
        other = query_one(
            "SELECT id FROM posts WHERE slug = ? AND id != ?",
            (slug, existing["id"] if existing else 0),
        )
        if other:
            flash("Slug already in use.", "error")
            return redirect(request.url)

        now = datetime.utcnow().isoformat()
        if existing:
            execute(
                """
                UPDATE posts SET title = ?, slug = ?, excerpt = ?, content = ?, cover_url = ?, tags = ?,
                    published = ?, updated_at = ?, publish_date = ? WHERE id = ?
                """,
                (
                    title,
                    slug,
                    excerpt,
                    content,
                    cover_url or None,
                    tags or None,
                    1 if publish_state else 0,
                    now,
                    publish_date,
                    existing["id"],
                ),
            )
            flash("Post updated.", "success")
            return redirect(url_for("admin_edit", post_id=existing["id"]))
        new_id = execute(
            """
            INSERT INTO posts (title, slug, excerpt, content, cover_url, tags, published, created_at, updated_at, publish_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                slug,
                excerpt,
                content,
                cover_url or None,
                tags or None,
                1 if publish_state else 0,
                now,
                now,
                publish_date,
            ),
        )
        flash("Post created.", "success")
        return redirect(url_for("admin_edit", post_id=new_id))

    @app.route("/health")
    def health() -> Response:
        return jsonify({"status": "ok"})


def main() -> None:
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)


if __name__ == "__main__":
    main()

# Grand River Analytics

Grand River Analytics is a minimalist Flask-based publishing platform for equity research write-ups. It delivers clean editorial templates, production-ready SEO, and a lightweight admin console for drafting and publishing content.

## Features

- Flask + SQLite stack with seed content for five sample posts
- Secure single-user admin with hashed password, CSRF protection, and TinyMCE editing
- SEO-friendly templates with canonical tags, Open Graph, Twitter cards, and JSON-LD (Organization, WebSite, Breadcrumb, BlogPosting)
- RSS feed, XML sitemap, and robots.txt
- Accessible, responsive front-end with vanilla CSS/JS and system font stack
- Client-side search and tag filtering for the blog index
- Contact form with honeypot protection and server-side validation (logging stub for email delivery)
- Smoke tests that exercise primary routes and XML feeds

## Quick start

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt  # or `poetry install` if you prefer
   ```

2. **Configure environment variables**

   Copy `.env.example` to `.env` and update values:

   ```bash
   cp .env.example .env
   ```

   - `SECRET_KEY`: Flask session secret
   - `ADMIN_PASSWORD` or `ADMIN_PASSWORD_HASH`: admin credentials (defaults to `researchadmin` if unset — change for production)
   - `BASE_URL`: canonical site URL (e.g., `https://research.example.com`)
   - `DATABASE`: optional custom database filename

3. **Run the application**

   ```bash
   python app.py
   ```

   The server binds to `0.0.0.0` and uses `$PORT` if defined (defaults to `5000`).

4. **Log into the admin**

   Visit `http://localhost:5000/admin/login` and authenticate with the configured password. From there you can create, edit, and publish posts.

## Testing

Run the smoke suite with `pytest`:

```bash
pytest tests_smoke.py
```

The tests instantiate the Flask app, hit key routes, and validate RSS/Sitemap responses.

## Deployment notes

- SQLite is used by default for simplicity. To switch to another backend (e.g., MySQL), update `DATABASE` to point at your DSN and adjust the connection logic inside `utils/db.py` accordingly.
- Static assets live under `static/` and can be served by your front-end proxy/CDN.
- For Replit, ensure the Run button executes `python app.py` (the default in this repo).
- TinyMCE loads from its CDN. If deploying to a restricted network, host the asset internally or allowlist the domain.
- Replace placeholder logos and imagery under `static/img/` with brand-specific assets.

### Deploying the public site to Netlify

Netlify’s CDN only serves static files, so this repository includes a lightweight exporter that renders the Flask routes into HTML during the build.

1. Confirm `BASE_URL` in `.env` points at your Netlify URL (for example `https://grandriveranalytics.netlify.app`).
2. Commit `netlify.toml` and `build_static.py` (already present in this repo).
3. Connect the repository in Netlify. The dashboard will read the build settings from `netlify.toml`:
   - **Build command:** `pip install -r requirements.txt && python build_static.py`
   - **Publish directory:** `netlify_build`
4. Deploy. The generated site includes all public pages, RSS, sitemap, robots.txt, and post detail pages. The contact form is configured with `data-netlify` so submissions continue to work via Netlify Forms.

> **Note:** The publishing/admin interface requires the live Flask application and a writable database. On Netlify the `/admin` routes are redirected to a notice explaining that admin editing is unavailable on the static build. Host the dynamic app on infrastructure that supports Python (Render, Fly.io, Railway, etc.) when you need authoring capabilities.

## Project structure

```
app.py                # Flask application and routes
utils/                # Database access, auth helpers, SEO utilities
static/               # CSS, JS, and image assets
templates/            # Jinja2 templates for public/admin views
migrations/           # Placeholder directory for future schema migrations
tests_smoke.py        # Smoke tests covering primary routes
```

## License

Released under the MIT License. See `LICENSE` (add your license terms as needed).

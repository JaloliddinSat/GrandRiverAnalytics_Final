# Grand River Analytics

Grand River Analytics is a minimalist Flask-based publishing platform for equity research write-ups. It delivers clean editorial templates, production-ready SEO, and a lightweight admin console for drafting and publishing content.

## Features

- Flask + SQLite stack with seed content for five sample posts
- Secure single-user admin with hashed password, CSRF protection, and TinyMCE editing
- Editorial admin extras: live slug syncing, save-and-preview workflow, duplication, featured flags, and hero styling controls
- TinyMCE editing surface with inline image support for charts and exhibits
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

### Authoring research posts

- **Content & metadata** – Every post captures title, slug, excerpt, TinyMCE-rendered body content, optional cover image, publish date, and tags.
- **Display controls** – Choose a hero theme (light, slate, midnight), add an optional kicker, highlight quote, summary bullet list, and call-to-action button to tailor the article layout.
- **SEO overrides** – Provide custom meta title/description per post when you need search-friendly copy distinct from the on-page heading.
- **Featured placement** – Toggle the “Feature on home page” checkbox to spotlight a report in the home page carousel and add a badge on the blog index.
- **Preview & duplication** – Use “Save & preview” for an instant draft preview in a new tab, and duplicate any entry from the dashboard to jumpstart variant write-ups.
- **Inline charts** – Use the TinyMCE image button or paste screenshots directly into the editor. Images are stored inline with the report so they render exactly where you place them.

## Testing

Run the smoke suite with `pytest`:

```bash
pytest tests_smoke.py
```

The tests instantiate the Flask app, hit key routes, and validate RSS/Sitemap responses.

## Deployment notes

- SQLite is used by default for simplicity. To switch to another backend (e.g., MySQL), update `DATABASE_URL` to point at your DSN and adjust the connection logic inside `utils/db.py` accordingly. When staying on SQLite in production, set `DATABASE_PATH` (or `DATABASE_URL`) to a location on persistent storage and optionally `REPORTS_CSV_PATH` to control where the automatic CSV export is written. If you do not set `SECRET_KEY`, the app now generates one and stores it alongside `DATABASE_PATH` (or in the instance folder) so multiple workers can validate sessions consistently.
- Static assets live under `static/` and can be served by your front-end proxy/CDN.
- For Replit, ensure the Run button executes `python app.py` (the default in this repo).
- If you paste large inline images via TinyMCE, set `MAX_FORM_MEMORY_MB` to the desired limit in MB (or leave it blank/`0` to remove the cap) to raise the payload allowance for form submissions.
- TinyMCE loads from its CDN. Provide a `TINYMCE_API_KEY` (string or JSON web key) to use the official Tiny Cloud script, or leave it blank to fall back to the open-source jsDelivr mirror. You can also point to a fully self-hosted bundle with `TINYMCE_SCRIPT_URL`.
- To enable the Adelle Sans Thin typography, supply either `ADOBE_FONTS_KIT_ID` (for your Typekit project ID) or a direct `ADOBE_FONTS_URL`. Leaving both blank falls back to the system font stack.
- Replace placeholder logos and imagery under `static/img/` with brand-specific assets.

### Deploying on Render (dynamic hosting)

Render’s Python services provide the always-on environment needed for the admin tools and TinyMCE editing.

1. Commit the included `render.yaml` blueprint (already present in this repository).
2. Create a new **Blueprint** on Render pointing at the GitHub repository. Render will read `render.yaml` and provision a free web service.
3. During setup, supply environment variables for `SECRET_KEY`, `ADMIN_PASSWORD`, and update `BASE_URL` to your Render domain (e.g., `https://grand-river-analytics.onrender.com`). Add `TINYMCE_API_KEY` (plain string or Tiny-provided JSON key) if you want to load the editor from Tiny Cloud, or set `TINYMCE_SCRIPT_URL` to a custom bundle. If you prefer the app to manage the key, leave `SECRET_KEY` blank and it will write a stable value next to `DATABASE_PATH` (for example `/var/data/secret_key.txt`).
4. Deploy. Render runs `pip install -r requirements.txt` and launches the site via `gunicorn app:app` (matching the provided `Procfile`).
5. Render provisions a persistent disk as defined in `render.yaml`. The service stores the SQLite file at `/var/data/grandriver.db` and mirrors every change into `/var/data/reports_backup.csv`. Adjust `DATABASE_PATH` and `REPORTS_CSV_PATH` if you mount a different location. Increase `MAX_FORM_MEMORY_MB` (or leave it unset/`0` to remove the limit) if you expect authors to paste very large inline charts so Render’s request parser accepts the payload.

### Optional: Static export to Netlify

If you still need a static snapshot (for example, as a CDN edge cache), the project ships with `build_static.py` and `netlify.toml`.

1. Confirm `BASE_URL` in `.env` points at your Netlify URL (for example `https://grandriveranalytics.netlify.app`).
2. Connect the repository in Netlify. The dashboard will read the build settings from `netlify.toml`:
   - **Build command:** `pip install -r requirements.txt && python build_static.py`
   - **Publish directory:** `netlify_build`
3. Deploy. The generated site includes all public pages, RSS, sitemap, robots.txt, and post detail pages. The contact form is configured with `data-netlify` so submissions continue to work via Netlify Forms.

> **Note:** Static exports are read-only and redirect `/admin` to an informational notice. Use Render (or another Python host) when you need to author or edit content.

### Deploying on Fly.io

Use the provided `Dockerfile` and `fly.toml` to deploy the dynamic app to Fly.io. The config is the standard Nomad-style `[[services]]` layout that the dashboard, the web “Deploy to Fly” button, and `fly deploy` all expect, so Fly can prepare the deployment plan without trying to generate a temporary manifest file. A `[[mounts]]` block attaches a `data` volume at `/data` so the SQLite database and CSV backup live on persistent storage.

1. Install the Fly CLI and run `fly auth login`.
2. Update the `app` value in `fly.toml` to match your Fly application name and adjust `primary_region` if needed.
3. Provision the volume once (for example `fly volumes create data --size 1 --region ord`) so `/data` persists between deploys.
4. Set the required secrets (for example `SECRET_KEY`, `ADMIN_PASSWORD`, and `BASE_URL`) with `fly secrets set`.
5. Deploy from the repository root:

   ```bash
   fly deploy
   ```

The Dockerfile builds a lightweight Python 3.11 image, installs `requirements.txt`, and starts the site with `gunicorn` bound to port `8080`. The `fly.toml` `[[services]]` block proxies ports 80/443 to the internal port 8080 and is compatible with Fly Launch planners so no manifest is required. `DATABASE_PATH` and `REPORTS_CSV_PATH` default to `/data` inside Fly, and the app auto-detects the `/data` defaults when `FLY_APP_NAME` is present.

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

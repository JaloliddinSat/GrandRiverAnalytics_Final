import functools
import os
import secrets
import time
from typing import Callable, Tuple

from flask import Response, abort, flash, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

CSRF_SESSION_KEY = "_csrf_token"
CSRF_TIMESTAMP_KEY = "_csrf_ts"
CSRF_TTL_SECONDS = 60 * 60


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    return check_password_hash(stored_hash, password)


def ensure_admin_password() -> Tuple[str, bool]:
    raw_password = os.getenv("ADMIN_PASSWORD", "").strip()
    if raw_password:
        return hash_password(raw_password), False
    default_password = "researchadmin"
    return hash_password(default_password), True


def generate_csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
        session[CSRF_TIMESTAMP_KEY] = int(time.time())
    return token


def validate_csrf_token() -> bool:
    # Accept CSRF token from:
    # 1) form field (standard HTML forms)
    # 2) header X-CSRF-Token (fetch/AJAX)
    # 3) JSON body field csrf_token (fetch/AJAX)
    sent_token = request.form.get("csrf_token")

    if not sent_token:
        sent_token = request.headers.get("X-CSRF-Token")

    if not sent_token:
        payload = request.get_json(silent=True) or {}
        if isinstance(payload, dict):
            sent_token = payload.get("csrf_token")

    session_token = session.get(CSRF_SESSION_KEY)
    issued_at = session.get(CSRF_TIMESTAMP_KEY, 0)

    if not sent_token or not session_token:
        return False
    if sent_token != session_token:
        return False
    if int(time.time()) - int(issued_at) > CSRF_TTL_SECONDS:
        return False
    return True


def csrf_protect() -> None:
    if request.method in {"POST", "PUT", "DELETE"} and not validate_csrf_token():
        flash("Your session expired. Please try again.", "error")
        abort(Response("Invalid CSRF token", status=400))


def login_required(view: Callable) -> Callable:
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("admin_authenticated"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("admin_login"))
        return view(**kwargs)

    return wrapped_view

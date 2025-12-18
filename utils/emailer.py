# utils/emailer.py

import os
import logging

logger = logging.getLogger(__name__)


def send_contact_email(name: str, email: str, message: str) -> bool:
    """
    Sends a contact-form notification email via Resend.

    Returns:
      True  -> email sent successfully
      False -> email not sent (missing config, SDK missing, API error, etc.)
    """
    # Read env vars at runtime (NOT at import time) so missing secrets won't crash the app.
    api_key = os.getenv("RESEND_API_KEY")
    to_email = os.getenv("CONTACT_TO_EMAIL")
    from_email = os.getenv("CONTACT_FROM_EMAIL")

    # If you want this to be optional in production, just return False when not configured.
    # This prevents Fly from crashing on boot due to missing secrets.
    if not api_key or not to_email or not from_email:
        logger.warning(
            "Contact email not sent: missing env vars. "
            "Need RESEND_API_KEY, CONTACT_TO_EMAIL, CONTACT_FROM_EMAIL."
        )
        return False

    # Import the SDK only when needed (also prevents boot crash if dependency isn't installed
    # unless the route is actually used).
    try:
        import resend  # type: ignore
    except Exception as e:
        logger.exception("Resend SDK not installed or failed to import: %s", e)
        return False

    try:
        resend.api_key = api_key

        subject = f"New contact message from {name}"
        html = f"""
        <h2>New Contact Message</h2>
        <p><b>Name:</b> {escape_html(name)}</p>
        <p><b>Email:</b> {escape_html(email)}</p>
        <p><b>Message:</b></p>
        <pre style="white-space: pre-wrap; font-family: inherit;">{escape_html(message)}</pre>
        """

        resend.Emails.send(
            {
                "from": from_email,
                "to": to_email,
                "subject": subject,
                "html": html,
                # Optional: makes reply go to the user who submitted the form
                "reply_to": email,
            }
        )
        return True

    except Exception as e:
        # Never crash the app because an email failed
        logger.exception("Failed to send contact email via Resend: %s", e)
        return False


def escape_html(s: str) -> str:
    """
    Minimal HTML escaping to avoid breaking HTML email formatting.
    """
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

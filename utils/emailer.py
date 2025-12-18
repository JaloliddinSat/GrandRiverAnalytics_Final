# utils/emailer.py

import os
import logging

logger = logging.getLogger(__name__)


def escape_html(s: str) -> str:
    """Minimal HTML escaping for safe email rendering."""
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


def send_contact_email(name: str, email: str, message: str) -> bool:
    """
    Sends a contact-form notification email via Resend.

    Returns:
      True  -> email sent successfully
      False -> email not sent (missing config, SDK missing, API error, etc.)
    """
    api_key = os.getenv("RESEND_API_KEY")
    to_email = os.getenv("CONTACT_TO_EMAIL")
    from_email = os.getenv("CONTACT_FROM_EMAIL")

    if not api_key or not to_email or not from_email:
        logger.warning(
            "Contact email not sent (missing env). "
            "RESEND_API_KEY=%s CONTACT_TO_EMAIL=%s CONTACT_FROM_EMAIL=%s",
            bool(api_key),
            bool(to_email),
            bool(from_email),
        )
        return False

    try:
        import resend  # type: ignore
    except Exception:
        logger.exception("Resend SDK import failed (is 'resend' installed?)")
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

        resp = resend.Emails.send(
            {
                "from": from_email,
                "to": to_email,
                "subject": subject,
                "html": html,
                "reply_to": email,
            }
        )

        logger.info("Resend send_contact_email success: %s", resp)
        return True

    except Exception:
        logger.exception("Resend send_contact_email failed")
        return False

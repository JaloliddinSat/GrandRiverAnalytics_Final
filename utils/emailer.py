import os
import requests

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
CONTACT_TO_EMAIL = os.getenv("CONTACT_TO_EMAIL")  # your inbox
CONTACT_FROM_EMAIL = os.getenv("CONTACT_FROM_EMAIL")  # must be verified on Resend, e.g. "GRA <hello@grandriveranalytics.ca>"

def send_contact_email(name: str, email: str, message: str) -> None:
    if not (RESEND_API_KEY and CONTACT_TO_EMAIL and CONTACT_FROM_EMAIL):
        # If not configured, just skip emailing (DB still stores it)
        return

    subject = f"New contact form submission — {name}"
    text = f"""New contact form submission:

Name: {name}
Email: {email}

Message:
{message}
"""

    r = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": CONTACT_FROM_EMAIL,
            "to": [CONTACT_TO_EMAIL],
            "subject": subject,
            "text": text,
            "reply_to": email,  # makes replying easy
        },
        timeout=10,
    )

    # If email fails, we still keep the DB record.
    r.raise_for_status()

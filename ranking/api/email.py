"""Email delivery. `console` prints the message (dev); `smtp` sends it."""
from __future__ import annotations

import smtplib
import sys
from email.message import EmailMessage

from .settings import Settings


class Mailer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sent: list[dict] = []  # kept for tests / console backend

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})
        if self.settings.email_backend == "console":
            print(f"\n--- email to {to} ---\n{subject}\n\n{body}\n--- end ---\n", file=sys.stderr)
            return
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.settings.email_from, to, subject
        msg.set_content(body)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as smtp:
            smtp.starttls()
            if self.settings.smtp_user:
                smtp.login(self.settings.smtp_user, self.settings.smtp_password)
            smtp.send_message(msg)

    def magic_link(self, to: str, name: str, url: str, invite: bool) -> None:
        if invite:
            subject = "You're invited"
            body = (f"{name},\n\nYou've been invited to rank the hardest boulders in the world.\n\n"
                    f"Sign in here (link valid for {self.settings.magic_link_ttl_minutes} minutes):\n{url}\n")
        else:
            subject = "Your sign-in link"
            body = f"{name},\n\nSign in here (valid for {self.settings.magic_link_ttl_minutes} minutes):\n{url}\n"
        self.send(to, subject, body)

    def welcome(self, to: str, name: str, base_url: str) -> None:
        body = (
            f"{name},\n\n"
            "You're in. Welcome to The List.\n\n"
            "Getting started takes a few minutes:\n\n"
            f"  1. Tick what you've climbed (and, if you like, what you've tried):\n     {base_url}/ticks\n\n"
            f"  2. Answer a few quick questions - which was harder for you?\n     {base_url}/compare\n\n"
            "  3. After ten answers the list unlocks.\n\n"
            "Your individual answers are private. Your own ordering is private too unless you choose\n"
            "to make it public from your profile.\n\n"
            f"Sign in any time by requesting a link at {base_url}\n"
        )
        self.send(to, "Welcome to The List", body)

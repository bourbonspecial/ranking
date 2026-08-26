from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# Always admins, regardless of environment. Others can be promoted from the admin panel
# or listed in RANKING_ADMIN_EMAILS.
DEFAULT_ADMIN_EMAILS = ["remknowles@gmail.com", "alexander.gradenegger@gmail.com"]


@dataclass
class Settings:
    db_path: Path | None = None               # None -> data/local.sqlite (created from seed)
    base_url: str = "http://localhost:8000"
    email_backend: str = "console"            # console | smtp
    email_from: str = "ranking@localhost"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    admin_emails: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_EMAILS))  # admins; provisioned on first login
    magic_link_ttl_minutes: int = 30
    session_ttl_days: int = 90
    recompute_debounce_seconds: float = 20.0
    attempt_weight: float = 0.4               # weight of a comparison involving a problem only attempted
    cookie_secure: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        return cls(
            db_path=Path(e("RANKING_DB")) if e("RANKING_DB") else None,
            base_url=e("RANKING_BASE_URL", "http://localhost:8000").rstrip("/"),
            email_backend=e("RANKING_EMAIL_BACKEND", "console"),
            email_from=e("RANKING_EMAIL_FROM", "ranking@localhost"),
            smtp_host=e("RANKING_SMTP_HOST", "localhost"),
            smtp_port=int(e("RANKING_SMTP_PORT", "587")),
            smtp_user=e("RANKING_SMTP_USER", ""),
            smtp_password=e("RANKING_SMTP_PASSWORD", ""),
            admin_emails=sorted({*DEFAULT_ADMIN_EMAILS,
                                 *[x.strip().lower() for x in e("RANKING_ADMIN_EMAILS", "").split(",") if x.strip()]}),
            recompute_debounce_seconds=float(e("RANKING_RECOMPUTE_DEBOUNCE", "20")),
            attempt_weight=float(e("RANKING_ATTEMPT_WEIGHT", "0.4")),
            cookie_secure=e("RANKING_COOKIE_SECURE", "0") == "1",
        )

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# Always admins, regardless of environment. Others can be promoted from the admin panel
# or listed in RANKING_ADMIN_EMAILS.
DEFAULT_ADMIN_EMAILS = ["remknowles@gmail.com", "alexander.gradenegger@gmail.com"]


@dataclass(frozen=True)
class RateLimit:
    """At most `requests` in any sliding window of `window_seconds`."""
    requests: int
    window_seconds: float

    @classmethod
    def from_env(cls, prefix: str, requests: int, window_seconds: float) -> "RateLimit":
        e = os.environ.get
        return cls(int(e(f"{prefix}_RATE_LIMIT", str(requests))),
                   float(e(f"{prefix}_RATE_WINDOW", str(window_seconds))))


# name -> default. Names are what routes pass to `rate_limited(...)`.
DEFAULT_RATE_LIMITS = {
    "magic_link": RateLimit(5, 900.0),    # per IP, and per email (silently dropped)
    "invite": RateLimit(10, 3600.0),      # per IP and per email
    "suggestion": RateLimit(5, 3600.0),   # per member
}


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
    magic_link_ttl_minutes: int = 60
    session_ttl_days: int = 90
    rate_limits: dict[str, RateLimit] = field(default_factory=lambda: dict(DEFAULT_RATE_LIMITS))
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
            rate_limits={name: RateLimit.from_env(f"RANKING_{name.upper()}", d.requests, d.window_seconds)
                         for name, d in DEFAULT_RATE_LIMITS.items()},
            recompute_debounce_seconds=float(e("RANKING_RECOMPUTE_DEBOUNCE", "20")),
            attempt_weight=float(e("RANKING_ATTEMPT_WEIGHT", "0.4")),
            cookie_secure=e("RANKING_COOKIE_SECURE", "0") == "1",
        )

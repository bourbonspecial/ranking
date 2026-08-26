"""Magic-link authentication and cookie sessions."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import ClimberRow, MagicLinkRow, SessionRow
from .deps import get_db, get_settings
from .settings import Settings

COOKIE = "ranking_session"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_magic_link(s: Session, settings: Settings, climber: ClimberRow) -> str:
    token = secrets.token_urlsafe(32)
    s.add(MagicLinkRow(token_hash=_hash(token), climber_id=climber.id,
                       expires_at=_now() + timedelta(minutes=settings.magic_link_ttl_minutes)))
    s.flush()
    return f"{settings.base_url}/api/auth/callback?token={token}"


def consume_magic_link(s: Session, token: str) -> tuple[ClimberRow, bool]:
    """Returns (climber, activated) - activated is True the first time an invited climber signs in."""
    row = s.get(MagicLinkRow, _hash(token))
    if row is None or row.used_at is not None or row.expires_at < _now():
        raise HTTPException(400, "This sign-in link is invalid or has expired.")
    climber = s.get(ClimberRow, row.climber_id)
    if climber is None or climber.status == "deactivated":
        raise HTTPException(403, "Account is not active.")
    row.used_at = _now()
    activated = climber.status == "invited"
    if activated:
        climber.status = "active"
    s.flush()
    return climber, activated


def create_session(s: Session, settings: Settings, climber: ClimberRow) -> str:
    token = secrets.token_urlsafe(32)
    s.add(SessionRow(token_hash=_hash(token), climber_id=climber.id,
                     expires_at=_now() + timedelta(days=settings.session_ttl_days)))
    s.flush()
    return token


def destroy_session(s: Session, token: str | None) -> None:
    if token:
        row = s.get(SessionRow, _hash(token))
        if row:
            s.delete(row)
            s.flush()


def optional_climber(request: Request, s: Session = Depends(get_db)) -> ClimberRow | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = s.get(SessionRow, _hash(token))
    if row is None or row.expires_at < _now():
        return None
    climber = s.get(ClimberRow, row.climber_id)
    if climber is None or climber.status != "active":
        return None
    return climber


def current_climber(climber: ClimberRow | None = Depends(optional_climber)) -> ClimberRow:
    if climber is None:
        raise HTTPException(401, "Sign in required.")
    return climber


def current_admin(climber: ClimberRow = Depends(current_climber)) -> ClimberRow:
    if not climber.is_admin:
        raise HTTPException(403, "Admin only.")
    return climber

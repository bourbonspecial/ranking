from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..db import LOCAL_DB, REPO_ROOT, create_schema, init_local_db, make_session_factory
from ..sync import ClimbingHistoryClient
from .email import Mailer
from .rate_limit import SlidingWindowRateLimiter
from .recompute import Recomputer
from .routes import admin, member, public
from .settings import DEFAULT_RATE_LIMITS, Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    db_path: Path = settings.db_path or init_local_db()
    create_schema(db_path)  # idempotent: applies _ADDED_COLUMNS to an explicitly configured RANKING_DB too
    session_factory = make_session_factory(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.recomputer.shutdown()

    _ensure_admins(session_factory, settings.admin_emails)

    app = FastAPI(title="Boulder Ranking", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.mailer = Mailer(settings)
    # Tests swap in a fake; None means sync is unavailable and its endpoints answer 503.
    app.state.ch_client = ClimbingHistoryClient(settings.ch_api_base, settings.ch_api_key) if settings.ch_api_key else None
    app.state.limiters = {name: SlidingWindowRateLimiter(rl.requests, rl.window_seconds)
                          for name, rl in {**DEFAULT_RATE_LIMITS, **settings.rate_limits}.items()}
    app.state.recomputer = Recomputer(session_factory, settings.recompute_debounce_seconds, settings.attempt_weight)
    app.include_router(public)
    app.include_router(member)
    app.include_router(admin)
    mount_frontend(app)
    return app


FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


def mount_frontend(app: FastAPI, dist: Path = FRONTEND_DIST) -> None:
    """Serve the built SPA; unknown non-API paths fall back to index.html."""
    if not (dist / "index.html").exists():
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = dist / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


def _ensure_admins(session_factory, emails: list[str]) -> None:
    """Configured admin emails are admins even if their account predates the config."""
    from sqlalchemy import select
    from ..db import ClimberRow
    if not emails:
        return
    with session_factory() as s:
        for c in s.scalars(select(ClimberRow).where(ClimberRow.email.in_(emails))):
            if not c.is_admin:
                c.is_admin = True
        s.commit()

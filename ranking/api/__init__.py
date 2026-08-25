from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from ..db import LOCAL_DB, init_local_db, make_session_factory
from .email import Mailer
from .recompute import Recomputer
from .routes import admin, member, public
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    db_path: Path = settings.db_path or init_local_db()
    session_factory = make_session_factory(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.recomputer.shutdown()

    app = FastAPI(title="Boulder Ranking", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.mailer = Mailer(settings)
    app.state.recomputer = Recomputer(session_factory, settings.recompute_debounce_seconds)
    app.include_router(public)
    app.include_router(member)
    app.include_router(admin)
    return app

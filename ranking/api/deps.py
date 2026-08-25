from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session


def get_settings(request: Request):
    return request.app.state.settings


def get_mailer(request: Request):
    return request.app.state.mailer


def get_recomputer(request: Request):
    return request.app.state.recomputer


def get_db(request: Request):
    s: Session = request.app.state.session_factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()

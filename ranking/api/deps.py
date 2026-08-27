from __future__ import annotations

from collections.abc import Callable, Iterable

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session


def get_settings(request: Request):
    return request.app.state.settings


def get_mailer(request: Request):
    return request.app.state.mailer


def get_ch_client(request: Request):
    client = request.app.state.ch_client
    if client is None:
        raise HTTPException(503, "Importing from climbing-history.org is not enabled on this server.")
    return client


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


def client_ip(request: Request) -> str:
    # uvicorn's ProxyHeadersMiddleware rewrites request.client from X-Forwarded-For
    # for trusted proxies (loopback by default), so nginx must set that header.
    return request.client.host if request.client else "unknown"


def rate_limited(name: str) -> Callable[[Request], Callable[[Iterable[str]], int | None]]:
    """Dependency giving a `consume(keys)` for the named limiter. `consume` returns
    Retry-After seconds when any key is exhausted; `check(keys)` raises 429 instead;
    `refund(keys)` gives a token back when the limited action didn't happen."""
    def dep(request: Request):
        limiter = request.app.state.limiters[name]

        def check(keys: Iterable[str]) -> None:
            retry_after = limiter.consume(keys)
            if retry_after is not None:
                raise HTTPException(429, "Too many requests. Try again later.",
                                    headers={"Retry-After": str(retry_after)})
        check.consume = limiter.consume
        check.refund = limiter.refund
        return check
    return dep

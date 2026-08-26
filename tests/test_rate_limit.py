from fastapi.testclient import TestClient

from ranking.api import create_app
from ranking.api.rate_limit import SlidingWindowRateLimiter
from ranking.api.settings import RateLimit, Settings
from ranking.db import PROBLEMS_CSV
from ranking.importer import build_seed_db


def test_sliding_window_limits_every_key_and_recovers():
    now = [100.0]
    limiter = SlidingWindowRateLimiter(2, 60, clock=lambda: now[0])

    assert limiter.consume(("ip:a", "email:x")) is None
    assert limiter.consume(("ip:a", "email:x")) is None
    assert limiter.consume(("ip:b", "email:x")) == 60  # email is limited across IPs
    assert limiter.consume(("ip:a", "email:y")) == 60  # IP is limited across emails

    now[0] += 60
    assert limiter.consume(("ip:a", "email:x")) is None


def test_public_endpoints_return_429_with_retry_after(tmp_path):
    db = tmp_path / "t.sqlite"
    build_seed_db(PROBLEMS_CSV, db)
    app = create_app(Settings(
        db_path=db,
        admin_emails=[],
        rate_limits={"magic_link": RateLimit(2, 60), "invite": RateLimit(2, 60), "suggestion": RateLimit(5, 60)},
    ))
    client = TestClient(app)

    for _ in range(2):
        assert client.post("/api/auth/request-link", json={"email": "member@example.com"}).status_code == 202
    limited = client.post("/api/auth/request-link", json={"email": "other@example.com"})
    assert limited.status_code == 429 and limited.headers["retry-after"] == "60"

    for n in range(2):
        assert client.post("/api/invite-requests", json={
            "name": "Climber", "email": f"climber{n}@example.com", "note": "",
        }).status_code == 202
    limited = client.post("/api/invite-requests", json={
        "name": "Climber", "email": "climber2@example.com", "note": "",
    })
    assert limited.status_code == 429 and limited.headers["retry-after"] == "60"


def test_magic_link_per_email_cap_is_silent(tmp_path):
    """Someone hammering a member's address must not lock them out with a 429 (or learn
    they are a member); the address just stops receiving mail for the window."""
    db = tmp_path / "t.sqlite"
    build_seed_db(PROBLEMS_CSV, db)
    app = create_app(Settings(db_path=db, admin_emails=["admin@example.com"],
                              rate_limits={"magic_link": RateLimit(2, 60), "invite": RateLimit(2, 60),
                                           "suggestion": RateLimit(5, 60)}))
    client = TestClient(app)
    sent_before = len(app.state.mailer.sent)
    for _ in range(3):
        # TestClient always presents the same IP, so drive the email bucket only
        app.state.limiters["magic_link"]._events.pop("ip:testclient", None)
        assert client.post("/api/auth/request-link", json={"email": "admin@example.com"}).status_code == 202
    assert len(app.state.mailer.sent) == sent_before + 2  # third request was dropped silently

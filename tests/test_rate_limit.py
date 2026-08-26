from fastapi.testclient import TestClient

from ranking.api import create_app
from ranking.api.rate_limit import SlidingWindowRateLimiter
from ranking.api.settings import Settings
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
        magic_link_rate_limit_requests=2,
        magic_link_rate_limit_window_seconds=60,
        invite_rate_limit_requests=2,
        invite_rate_limit_window_seconds=60,
    ))
    client = TestClient(app)

    for _ in range(2):
        assert client.post("/api/auth/request-link", json={"email": "member@example.com"}).status_code == 202
    limited = client.post("/api/auth/request-link", json={"email": "member@example.com"})
    assert limited.status_code == 429 and limited.headers["retry-after"] == "60"

    for n in range(2):
        assert client.post("/api/invite-requests", json={
            "name": "Climber", "email": f"climber{n}@example.com", "note": "",
        }).status_code == 202
    limited = client.post("/api/invite-requests", json={
        "name": "Climber", "email": "climber2@example.com", "note": "",
    })
    assert limited.status_code == 429 and limited.headers["retry-after"] == "60"

import re

import pytest
from fastapi.testclient import TestClient

from ranking.api import create_app
from ranking.api.settings import Settings
from ranking.db import PROBLEMS_CSV
from ranking.importer import build_seed_db


@pytest.fixture
def app(tmp_path):
    db = tmp_path / "t.sqlite"
    build_seed_db(PROBLEMS_CSV, db)
    return create_app(Settings(db_path=db, admin_emails=["admin@example.com"], recompute_debounce_seconds=0))


@pytest.fixture
def anon(app):
    return TestClient(app, base_url="http://localhost:8000", follow_redirects=False)


def sign_in(app, email):
    """Request a link, pull it out of the console mailer, follow it. Returns a logged-in client."""
    client = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    r = client.post("/api/auth/request-link", json={"email": email})
    assert r.status_code == 202
    body = app.state.mailer.sent[-1]["body"]
    url = re.search(r"http://\S+", body).group(0)
    r = client.get(url)
    assert r.status_code == 303
    assert "ranking_session" in r.cookies
    return client


@pytest.fixture
def admin(app):
    return sign_in(app, "admin@example.com")


def test_unauthenticated_is_rejected(anon):
    assert anon.get("/api/problems").status_code == 401
    assert anon.get("/api/me").json() is None


def test_unknown_email_gets_no_link(app, anon):
    n = len(app.state.mailer.sent)
    assert anon.post("/api/auth/request-link", json={"email": "nobody@example.com"}).status_code == 202
    assert len(app.state.mailer.sent) == n


def test_bad_token_rejected(anon):
    assert anon.get("/api/auth/callback?token=nope").status_code == 400


def test_invite_request_then_admin_invite_then_member_flow(app, anon, admin):
    # 1. stranger requests an invite
    r = anon.post("/api/invite-requests", json={"name": "Nalle", "email": "nalle@example.com", "note": "Burden"})
    assert r.status_code == 202
    assert anon.post("/api/auth/request-link", json={"email": "nalle@example.com"}).status_code == 202
    assert app.state.mailer.sent[-1]["to"] != "nalle@example.com"  # not yet invited: no link

    # 2. admin sees and approves the request
    reqs = admin.get("/api/admin/climbers", params={"status": "requested"}).json()
    assert [c["email"] for c in reqs] == ["nalle@example.com"]
    r = admin.post(f"/api/admin/climbers/{reqs[0]['id']}/invite")
    assert r.json()["status"] == "invited"
    assert app.state.mailer.sent[-1]["subject"] == "You're invited"

    # 3. member follows the invite link and is active
    nalle = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    url = re.search(r"http://\S+", app.state.mailer.sent[-1]["body"]).group(0)
    assert nalle.get(url).status_code == 303
    assert nalle.get(url).status_code == 400  # single use
    me = nalle.get("/api/me").json()
    assert me["status"] == "active" and me["is_admin"] is False
    assert nalle.get("/api/admin/climbers").status_code == 403

    # 4. ticks, pairs, comparisons, gate
    problems = nalle.get("/api/problems").json()
    assert len(problems) == 85
    ids = [p["id"] for p in problems[:5]]
    tried = problems[20]["id"]
    prog = nalle.put("/api/me/ascents", json={"done": ids, "tried": [tried]}).json()
    assert prog == {"n_done": 5, "n_tried": 1, "n_done_pairs": 10, "n_done_answered": 0,
                    "n_attempt_pairs": 5, "n_attempt_answered": 0,
                    "ranking_unlocked": False, "ranking_required": 10}
    assert nalle.get("/api/me/ascents").json() == {"done": sorted(ids), "tried": [tried]}
    assert nalle.get("/api/ranking").status_code == 403

    pairs = nalle.get("/api/me/pairs", params={"limit": 3}).json()
    assert len(pairs) == 3 and all(p["kind"] == "done" for p in pairs)
    all_pairs = nalle.get("/api/me/pairs").json()
    assert [p["kind"] for p in all_pairs] == ["done"] * 10 + ["attempt"] * 5
    for pr in all_pairs[:10]:
        r = nalle.post("/api/me/comparisons", json={"problem_a": pr["problem_a"]["id"],
                                                    "problem_b": pr["problem_b"]["id"], "verdict": "A_HARDER"})
        assert r.status_code == 200
    assert r.json()["ranking_unlocked"] is True
    remaining = nalle.get("/api/me/pairs").json()
    assert len(remaining) == 5 and all(p["kind"] == "attempt" for p in remaining)
    r = nalle.post("/api/me/comparisons", json={"problem_a": tried, "problem_b": ids[0], "verdict": "A_HARDER"})
    assert r.json()["n_attempt_answered"] == 1
    mine = nalle.get("/api/me/comparisons").json()
    assert len(mine) == 11 and sum(c["kind"] == "attempt" for c in mine) == 1

    # revise one
    r = nalle.post("/api/me/comparisons", json={"problem_a": ids[0], "problem_b": ids[1], "verdict": "SIMILAR"})
    assert r.status_code == 200
    assert len(nalle.get("/api/me/comparisons").json()) == 11

    # 5. ranking (recompute ran synchronously with debounce=0)
    rk = nalle.get("/api/ranking").json()
    assert rk["algorithm"] == "bradley_terry" and len(rk["rows"]) == 85 and rk["n_comparisons"] == 10
    assert rk["include_attempts"] is False and rk["attempt_weight"] is None
    with_att = nalle.get("/api/ranking", params={"include_attempts": "true"}).json()
    assert with_att["n_comparisons"] == 11 and with_att["attempt_weight"] == 0.4
    assert rk["rows"][0]["rank"] == 1
    assert nalle.get("/api/ranking", params={"algo": "elo"}).json()["algorithm"] == "elo"
    assert nalle.get("/api/ranking", params={"algo": "bogus"}).status_code == 400

    mine = nalle.get("/api/me/ranking").json()
    assert len(mine) == 6 and all(row["global_rank"] is not None for row in mine)
    assert sum(row["status"] == "tried" for row in mine) == 1

    # bad inputs
    assert nalle.post("/api/me/comparisons", json={"problem_a": ids[0], "problem_b": ids[0], "verdict": "SIMILAR"}).status_code == 400
    assert nalle.post("/api/me/comparisons", json={"problem_a": ids[0], "problem_b": 80, "verdict": "SIMILAR"}).status_code == 400
    assert nalle.put("/api/me/ascents", json={"done": [99999]}).status_code == 400


def test_admin_direct_invite_and_reject(app, admin):
    r = admin.post("/api/admin/invite", json={"name": "Aidan", "email": "aidan@example.com"})
    assert r.status_code == 200 and r.json()["status"] == "invited"
    cid = r.json()["id"]
    assert admin.post(f"/api/admin/climbers/{cid}/reject").json()["status"] == "deactivated"
    assert admin.post("/api/admin/recompute").json() == {"ok": True}
    # admin can see the ranking without the gate
    assert admin.get("/api/ranking").status_code == 200

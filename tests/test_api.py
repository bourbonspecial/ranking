import re

import pytest
from fastapi.testclient import TestClient

from ranking.api import create_app
from ranking.api.email import Mailer
from ranking.api.settings import RateLimit, Settings
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


def test_sign_in_email_explains_single_use_and_expiry(app, anon):
    anon.post("/api/auth/request-link", json={"email": "admin@example.com"})
    mail = app.state.mailer.sent[-1]
    assert mail["subject"] == "Your sign-in link for The List"
    assert "works once" in mail["body"] and "expires in 1 hour" in mail["body"]
    assert "Already a member" in mail["body"] and app.state.settings.base_url in mail["body"]


def test_invite_email_is_distinct_from_sign_in_email(app, admin):
    admin.post("/api/admin/invite", json={"name": "Nalle", "email": "nalle@example.com"})
    mail = app.state.mailer.sent[-1]
    assert mail["subject"] == "You're in: your invitation to The List"
    assert "has been accepted" in mail["body"] and "works once" in mail["body"]
    assert "http://" in mail["body"]


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
    assert app.state.mailer.sent[-1]["subject"] == "You're in: your invitation to The List"

    # 3. member follows the invite link and is active
    nalle = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    url = re.search(r"http://\S+", app.state.mailer.sent[-1]["body"]).group(0)
    n_sent = len(app.state.mailer.sent)
    assert nalle.get(url).status_code == 303
    welcome = app.state.mailer.sent[-1]
    assert len(app.state.mailer.sent) == n_sent + 1 and welcome["subject"] == "Welcome to The List"
    assert welcome["to"] == "nalle@example.com" and "/compare" in welcome["body"]
    assert nalle.get(url).status_code == 400  # single use
    # signing in again later does not re-send the welcome
    nalle.post("/api/auth/request-link", json={"email": "nalle@example.com"})
    again = re.search(r"http://\S+", app.state.mailer.sent[-1]["body"]).group(0)
    n_sent = len(app.state.mailer.sent)
    assert nalle.get(again).status_code == 303
    assert len(app.state.mailer.sent) == n_sent
    me = nalle.get("/api/me").json()
    assert me["status"] == "active" and me["is_admin"] is False
    assert nalle.get("/api/admin/climbers").status_code == 403

    # 4. ticks, pairs, comparisons, gate
    problems = nalle.get("/api/problems").json()
    assert len(problems) == 433
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
    assert rk["algorithm"] == "bradley_terry" and len(rk["rows"]) == 433 and rk["n_comparisons"] == 10
    assert rk["include_attempts"] is False and rk["attempt_weight"] is None
    with_att = nalle.get("/api/ranking", params={"include_attempts": "true"}).json()
    assert with_att["n_comparisons"] == 11 and with_att["attempt_weight"] == 0.4
    assert rk["rows"][0]["rank"] == 1
    top = rk["rows"][0]
    assert top["seed_rating"] in (1500.0, 1750.0, 2000.0, 2250.0)
    assert abs(top["delta"] - (top["rating"] - top["seed_rating"])) < 0.11
    assert all(r["delta"] == 0 for r in rk["rows"] if r["n_comparisons"] == 0)
    assert nalle.get("/api/ranking", params={"algo": "elo"}).json()["algorithm"] == "elo"
    assert nalle.get("/api/ranking", params={"algo": "bogus"}).status_code == 400

    assert rk["stats"] == {"n_problems": 433, "n_with_data": 5, "n_members": 2, "n_voters": 1,
                           "n_comparisons_total": 11}

    mine = nalle.get("/api/me/ranking").json()
    assert len(mine) == 6 and all(row["global_rank"] is not None for row in mine)
    assert sum(row["status"] == "tried" for row in mine) == 1

    # 6. public profile is opt-in
    cid = nalle.get("/api/me").json()["id"]
    assert anon.get(f"/api/climbers/{cid}/public").status_code == 404
    assert nalle.patch("/api/me", json={"public_profile": True}).json()["public_profile"] is True
    pub = anon.get(f"/api/climbers/{cid}/public").json()
    assert pub["name"] == "Nalle" and len(pub["ranking"]) == 6 and len(pub["comparisons"]) == 11
    assert nalle.patch("/api/me", json={"public_profile": False}).json()["public_profile"] is False
    assert anon.get(f"/api/climbers/{cid}/public").status_code == 404

    # bad inputs
    assert nalle.post("/api/me/comparisons", json={"problem_a": ids[0], "problem_b": ids[0], "verdict": "SIMILAR"}).status_code == 400
    assert nalle.post("/api/me/comparisons", json={"problem_a": ids[0], "problem_b": 80, "verdict": "SIMILAR"}).status_code == 400
    assert nalle.put("/api/me/ascents", json={"done": [99999]}).status_code == 400


def test_test_users_are_excluded_from_global_ranking(app, admin):
    r = admin.post("/api/admin/invite", json={"name": "Tester", "email": "tester@example.com"})
    cid = r.json()["id"]
    tester = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    tester.get(re.search(r"http://\S+", app.state.mailer.sent[-1]["body"]).group(0))
    ids = [p["id"] for p in tester.get("/api/problems").json()[:3]]
    tester.put("/api/me/ascents", json={"done": ids})
    for a, b in [(ids[0], ids[1]), (ids[0], ids[2]), (ids[1], ids[2])]:
        tester.post("/api/me/comparisons", json={"problem_a": a, "problem_b": b, "verdict": "A_HARDER"})
    assert admin.get("/api/ranking").json()["n_comparisons"] == 3

    r = admin.post(f"/api/admin/climbers/{cid}/test")
    assert r.json()["is_test"] is True
    rk = admin.get("/api/ranking").json()
    assert rk["n_comparisons"] == 0 and rk["stats"]["n_voters"] == 0 and rk["stats"]["n_comparisons_total"] == 0
    # they still get their own ordering, and see the flag on /me
    assert len(tester.get("/api/me/ranking").json()) == 3
    assert tester.get("/api/me/ranking").json()[0]["n_comparisons"] == 2
    assert tester.get("/api/me").json()["is_test"] is True

    assert admin.post(f"/api/admin/climbers/{cid}/test", params={"value": "false"}).json()["is_test"] is False
    assert admin.get("/api/ranking").json()["n_comparisons"] == 3


def test_ascent_status_change_recomputes_global_ranking(app, admin):
    admin.post("/api/admin/invite", json={"name": "Alex", "email": "alex@example.com"})
    climber = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    climber.get(re.search(r"http://\S+", app.state.mailer.sent[-1]["body"]).group(0))
    ids = [p["id"] for p in climber.get("/api/problems").json()[:3]]

    climber.put("/api/me/ascents", json={"done": ids[:2], "tried": [ids[2]]})
    climber.post("/api/me/comparisons", json={
        "problem_a": ids[0], "problem_b": ids[2], "verdict": "A_HARDER",
    })
    assert admin.get("/api/ranking").json()["n_comparisons"] == 0
    assert admin.get("/api/ranking", params={"include_attempts": "true"}).json()["n_comparisons"] == 1

    # Promoting the tried problem to done makes the existing comparison full-weight
    # and eligible for the default ranking without requiring an admin recompute.
    climber.put("/api/me/ascents", json={"done": ids, "tried": []})
    assert admin.get("/api/ranking").json()["n_comparisons"] == 1


def test_admin_direct_invite_and_reject(app, admin):
    r = admin.post("/api/admin/invite", json={"name": "Aidan", "email": "aidan@example.com"})
    assert r.status_code == 200 and r.json()["status"] == "invited"
    cid = r.json()["id"]
    assert admin.post(f"/api/admin/climbers/{cid}/reject").json()["status"] == "deactivated"
    assert admin.post("/api/admin/recompute").json() == {"ok": True}
    # admin can see the ranking without the gate
    assert admin.get("/api/ranking").status_code == 200


def test_default_admins_and_startup_promotion(tmp_path):
    from ranking import repo
    from ranking.api.settings import DEFAULT_ADMIN_EMAILS
    from ranking.db import make_session_factory
    db = tmp_path / "t.sqlite"
    build_seed_db(PROBLEMS_CSV, db)
    # an account that existed before it was configured as admin
    with make_session_factory(db)() as s:
        repo.add_climber(s, "Rem", DEFAULT_ADMIN_EMAILS[0], status="active", is_admin=False)
        s.commit()
    settings = Settings(db_path=db, recompute_debounce_seconds=0)
    assert set(DEFAULT_ADMIN_EMAILS) <= set(settings.admin_emails)
    app = create_app(settings)
    with make_session_factory(db)() as s:
        assert repo.get_climber_by_email(s, DEFAULT_ADMIN_EMAILS[0]).is_admin is True
    # the other default admin can sign in without an invite and arrives as admin
    client = sign_in(app, DEFAULT_ADMIN_EMAILS[1])
    assert client.get("/api/me").json()["is_admin"] is True


def test_missing_boulder_suggestion_emails_admins(app, admin):
    body = {"name": "Return of the Sleepwalker", "crag": "Red Rocks", "country": "USA",
            "grade": "9A", "fa_name": "Daniel Woods", "fa_date": "2021-03",
            "note": "not on the list yet"}
    r = admin.post("/api/problem-suggestions", json=body)
    assert r.status_code == 202
    sent = app.state.mailer.sent[-1]
    assert sent["to"] == "admin@example.com"
    assert "Return of the Sleepwalker" in sent["subject"]
    assert "Daniel Woods" in sent["body"] and "admin@example.com" in sent["body"]

    # a grade the scale doesn't know is rejected, and so is a duplicate of an existing problem
    assert admin.post("/api/problem-suggestions", json={**body, "grade": "7A"}).status_code == 422
    existing = admin.get("/api/problems").json()[0]
    dupe = {**body, "name": existing["name"].lower(), "crag": existing["crag"].upper()}
    assert admin.post("/api/problem-suggestions", json=dupe).status_code == 409


def test_suggestions_are_rate_limited(app):
    settings = Settings(db_path=app.state.settings.db_path, admin_emails=["admin@example.com"],
                        recompute_debounce_seconds=0, rate_limits={"suggestion": RateLimit(1, 3600)})
    client = sign_in(create_app(settings), "admin@example.com")
    body = {"name": "One", "grade": "8C"}
    assert client.post("/api/problem-suggestions", json=body).status_code == 202
    r = client.post("/api/problem-suggestions", json={**body, "name": "Two"})
    assert r.status_code == 429 and r.headers["Retry-After"]


def test_suggestion_input_is_cleaned(app, admin):
    # blank names are rejected before anything is emailed
    assert admin.post("/api/problem-suggestions", json={"name": "   ", "grade": "8C"}).status_code == 422
    # header injection via newlines is neutralised, and the grade is normalised
    r = admin.post("/api/problem-suggestions", json={"name": "Foo\nBcc: x@y.z", "grade": " 9a "})
    assert r.status_code == 202
    sent = app.state.mailer.sent[-1]
    assert "\n" not in sent["subject"] and "Bcc: x@y.z" in sent["subject"]
    assert "9A" in sent["body"]


def test_failed_suggestion_email_refunds_the_token(app):
    settings = Settings(db_path=app.state.settings.db_path, admin_emails=["admin@example.com"],
                        recompute_debounce_seconds=0, rate_limits={"suggestion": RateLimit(1, 3600)})
    a = create_app(settings)
    client = sign_in(a, "admin@example.com")

    def boom(*args, **kwargs):
        raise ConnectionRefusedError("smtp down")
    a.state.mailer.problem_suggestion = boom
    r = client.post("/api/problem-suggestions", json={"name": "One", "grade": "8C"})
    assert r.status_code == 503
    a.state.mailer.problem_suggestion = Mailer(settings).problem_suggestion
    assert client.post("/api/problem-suggestions", json={"name": "One", "grade": "8C"}).status_code == 202


def test_admin_can_view_any_members_profile(app, admin):
    admin.post("/api/admin/invite", json={"name": "Alex", "email": "alex@example.com"})
    alex = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    alex.get(re.search(r"http://\S+", app.state.mailer.sent[-1]["body"]).group(0))
    ids = [p["id"] for p in alex.get("/api/problems").json()[:3]]
    alex.put("/api/me/ascents", json={"done": ids[:2], "tried": [ids[2]]})
    alex.post("/api/me/comparisons", json={"problem_a": ids[0], "problem_b": ids[1], "verdict": "A_HARDER"})
    alex_id = alex.get("/api/me").json()["id"]

    # the profile is private to everyone else...
    assert alex.get(f"/api/climbers/{alex_id}/public").status_code == 404
    assert alex.get(f"/api/admin/climbers/{alex_id}/profile").status_code == 403
    # ...but an admin sees ascents, answers and the personal ordering
    r = admin.get(f"/api/admin/climbers/{alex_id}/profile")
    assert r.status_code == 200
    d = r.json()
    assert d["email"] == "alex@example.com" and d["status"] == "active" and d["public_profile"] is False
    assert d["n_done"] == 2 and d["n_tried"] == 1 and d["n_comparisons"] == 1
    assert {row["problem"]["id"] for row in d["ranking"]} == set(ids)
    assert d["comparisons"][0]["verdict"] == "A_HARDER" and d["updated_at"] == d["comparisons"][0]["updated_at"]
    assert admin.get("/api/admin/climbers/9999/profile").status_code == 404


def test_invite_can_mark_a_test_user_up_front(app, admin, anon):
    r = admin.post("/api/admin/invite", json={"name": "Tess", "email": "tess@example.com", "is_test": True})
    assert r.status_code == 200 and r.json()["is_test"] is True and r.json()["status"] == "invited"

    anon.post("/api/invite-requests", json={"name": "Rob", "email": "rob@example.com", "note": ""})
    rob = next(c for c in admin.get("/api/admin/climbers").json() if c["email"] == "rob@example.com")
    assert rob["is_test"] is False
    r = admin.post(f"/api/admin/climbers/{rob['id']}/invite", params={"test": "true"})
    assert r.status_code == 200 and r.json()["is_test"] is True
    # a plain resend leaves the flag alone
    assert admin.post(f"/api/admin/climbers/{rob['id']}/invite").json()["is_test"] is True

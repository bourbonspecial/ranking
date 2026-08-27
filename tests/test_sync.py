"""Importing ascents from climbing-history.org, against a fake client."""
import pytest
from fastapi.testclient import TestClient

from ranking.api import create_app
from ranking.api.settings import Settings
from ranking.db import PROBLEMS_CSV
from ranking.importer import build_seed_db
from ranking.sync import SyncError, is_hard, norm, norm_grade
from tests.test_api import sign_in

CLIMBERS = [{"climber_id": 467, "climber_uuid": "u-467", "climber_name": "Nalle Hukkataival",
             "climber_url": "https://climbing-history.org/climber/467/nalle", "hard_boulder_count": 12}]


def ascent(climb_id, name, grade, crag=None, successful=True, date="2016-10-24", **extra):
    return {"ascent_id": climb_id * 10, "climb_id": climb_id, "climb_name": name, "grade": grade,
            "crag_name": crag, "successful": successful, "ascent_style": "Worked" if successful else "Did not finish",
            "ascent_dt_start": None, "ascent_dt_end": date, "climb_url": f"https://climbing-history.org/climb/{climb_id}/x", **extra}


class FakeCH:
    def __init__(self):
        self.ascents = [
            ascent(1, "Burden of Dreams", "9A", "Lappnor"),
            ascent(2, "soudain seul", "9A", "Coquibus Rumont", successful=False),   # case differs
            ascent(2, "soudain seul", "9A", "Coquibus Rumont", successful=False, date="2022-01-01"),
            ascent(3, "Return of the Sleepwalker", "9A", None),                    # crag missing: name-only
            ascent(4, "Made Up Hard Thing", "8C+", "Nowhere"),                      # hard, not on our list
            ascent(5, "Warm Up", "8B", "Lappnor"),                                  # too easy, ignored
        ]
        self.boulders = [
            {"climb_id": 1, "climb_name": "Burden of Dreams", "grade": "9A", "crag_name": "Lappnor", "climb_url": "https://climbing-history.org/climb/1/bod"},
            {"climb_id": 4, "climb_name": "Made Up Hard Thing", "grade": "8C+", "crag_name": "Nowhere", "climb_url": ""},
        ]
        self.fail = False

    def _check(self):
        if self.fail:
            raise SyncError("climbing-history.org answered 503")

    def search_climbers(self, q):
        self._check(); return [c for c in CLIMBERS if q.lower() in c["climber_name"].lower()]

    def climber_boulders(self, climber_id):
        self._check(); return self.ascents if climber_id == 467 else []

    def hard_boulders(self):
        self._check(); return self.boulders


@pytest.fixture
def app(tmp_path):
    db = tmp_path / "t.sqlite"
    build_seed_db(PROBLEMS_CSV, db)
    a = create_app(Settings(db_path=db, admin_emails=["admin@example.com"], recompute_debounce_seconds=0))
    a.state.ch_client = FakeCH()
    return a


@pytest.fixture
def member(app):
    admin = sign_in(app, "admin@example.com")
    admin.post("/api/admin/invite", json={"name": "Nalle", "email": "nalle@example.com"})
    return sign_in(app, "nalle@example.com")


def test_normalisation():
    assert norm("  Soudain Seul! ") == norm("soudain-seul") == "soudain seul"
    assert norm("Ephyra") == norm("Éphyra")
    assert norm_grade("8C+/9A") == "8C+" and norm_grade("8c (hard)") == "8C" and norm_grade(None) == ""
    assert is_hard("8C") and is_hard("9B") and is_hard("8C/8C+") and not is_hard("8B+") and not is_hard(None)


def test_search_is_proxied_and_advertised(app, member):
    assert member.get("/api/me").json()["sync_sources"] == ["climbing_history"]
    r = member.get("/api/me/sync/climbing-history/climbers", params={"q": "nalle"})
    assert r.status_code == 200 and r.json()[0]["climber_id"] == 467 and "climber_uuid" not in r.json()[0]
    assert member.get("/api/me/sync/climbing-history/climbers", params={"q": "n"}).status_code == 422


def test_preview_matches_by_name_and_reports_the_rest(app, member):
    burden = next(p["id"] for p in member.get("/api/problems").json() if p["name"] == "Burden of Dreams")
    member.put("/api/me/ascents", json={"done": [], "tried": [burden]})  # already ticked as tried here
    r = member.get("/api/me/sync/climbing-history/climbers/467/preview")
    assert r.status_code == 200
    d = r.json()
    by_name = {m["problem"]["name"]: m for m in d["matched"]}
    assert set(by_name) == {"Burden of Dreams", "Soudain Seul", "Return of the Sleepwalker"}
    assert by_name["Burden of Dreams"]["status"] == "done" and by_name["Burden of Dreams"]["current"] == "tried"
    assert by_name["Soudain Seul"]["status"] == "tried" and by_name["Soudain Seul"]["current"] is None
    assert [u["climb_name"] for u in d["unmatched"]] == ["Made Up Hard Thing"]
    assert d["n_skipped"] == 1
    # nothing was written: the member applies the preview through PUT /me/ascents
    assert member.get("/api/me/ascents").json() == {"done": [], "tried": [burden]}
    assert by_name["Soudain Seul"]["date"] == "2022-01-01"  # latest attempt
    assert by_name["Burden of Dreams"]["date"] == "2016-10-24"


def test_preview_for_unknown_climber_is_empty(member):
    d = member.get("/api/me/sync/climbing-history/climbers/999/preview").json()
    assert d == {"matched": [], "unmatched": [], "n_skipped": 0}


def test_upstream_failure_is_a_502(app, member):
    app.state.ch_client.fail = True
    assert member.get("/api/me/sync/climbing-history/climbers", params={"q": "nalle"}).status_code == 502
    assert member.get("/api/me/sync/climbing-history/climbers/467/preview").status_code == 502


def test_sync_disabled_without_a_key(app, member):
    app.state.ch_client = None
    assert member.get("/api/me").json()["sync_sources"] == []
    assert member.get("/api/me/sync/climbing-history/climbers", params={"q": "nalle"}).status_code == 503


def test_admin_backfill_links_ids_then_preview_joins_by_id(app, member):
    admin = sign_in(app, "admin@example.com")
    assert member.post("/api/admin/sync/climbing-history/backfill").status_code == 403
    r = admin.post("/api/admin/sync/climbing-history/backfill")
    assert r.status_code == 200
    d = r.json()
    assert d["linked"] == 1
    assert [u["climb_name"] for u in d["unmatched_theirs"]] == ["Made Up Hard Thing"]
    assert any(p["name"] == "Soudain Seul" for p in d["unmatched_ours"])
    # once linked, a renamed climb still matches through its id
    app.state.ch_client.ascents = [ascent(1, "Burden Of Dreams (sit start)", "9A", "Lappnor")]
    d = member.get("/api/me/sync/climbing-history/climbers/467/preview").json()
    assert [m["problem"]["name"] for m in d["matched"]] == ["Burden of Dreams"]
    # idempotent
    assert admin.post("/api/admin/sync/climbing-history/backfill").json()["linked"] == 0

from datetime import datetime, timedelta

import pytest

from ranking import Verdict
from ranking import repo
from ranking.db import PROBLEMS_CSV, create_schema, init_local_db, make_session_factory
from ranking.importer import build_seed_db, import_problems, parse_first_ascent, read_problems_csv


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "t.sqlite"
    build_seed_db(PROBLEMS_CSV, path)
    return make_session_factory(path)


def test_parse_first_ascent():
    assert parse_first_ascent("Nalle Hukkataival (24th Oct 2016)") == ("Nalle Hukkataival", "24th Oct 2016")
    assert parse_first_ascent("Charles Albert (Before 29th Mar 2026)") == ("Charles Albert", "Before 29th Mar 2026")
    assert parse_first_ascent("") == ("", "")


def test_csv_import_has_all_rows():
    rows = read_problems_csv()
    assert len(rows) == 433
    assert {r["seed_grade"] for r in rows} == {"8C", "8C+", "9A", "9A+"}


def test_init_local_copies_seed(tmp_path):
    seed, local = tmp_path / "seed.sqlite", tmp_path / "local.sqlite"
    build_seed_db(PROBLEMS_CSV, seed)
    init_local_db(seed, local)
    assert local.exists()
    with make_session_factory(local)() as s:
        assert len(repo.all_problems(s)) == 433


def test_full_flow(db):
    with db() as s:
        problems = repo.all_problems(s)
        ids = [int(p.id) for p in problems[:4]]
        me = repo.add_climber(s, "Me", "ME@example.com")
        tried_id = int(problems[10].id)
        repo.set_ascents(s, me.id, ids, [tried_id])
        assert len(repo.ticked_problems(s, me.id)) == 5
        assert len(repo.ticked_problems(s, me.id, "done")) == 4

        ok, made, need = repo.can_view_ranking(s, me.id)
        assert (ok, made, need) == (False, 0, 6)

        q = repo.next_pairs(s, me.id)
        assert len(q) == 10                      # 6 done pairs + 4 attempt pairs
        assert [k for _, _, k in q] == ["done"] * 6 + ["attempt"] * 4

        # attempt comparison is weighted, excluded from done-only view, and doesn't count for the gate
        repo.record_comparison(s, me.id, tried_id, ids[0], Verdict.A_HARDER)
        assert repo.all_comparisons(s, include_attempts=False) == []
        assert repo.all_comparisons(s, attempt_weight=0.4)[0].weight == 0.4
        assert repo.progress(s, me.id)["n_attempt_answered"] == 1
        assert repo.can_view_ranking(s, me.id)[1] == 0

        t = datetime(2026, 8, 1)
        repo.record_comparison(s, me.id, ids[1], ids[0], Verdict.A_HARDER, t)          # ids[1] harder
        repo.record_comparison(s, me.id, ids[0], ids[1], Verdict.A_HARDER, t + timedelta(minutes=1))  # revised: ids[0] harder
        rows = [r for r, kind in repo.climber_comparisons(s, me.id) if kind == "done"]
        assert len(rows) == 1
        assert rows[0].verdict == "A_HARDER" and rows[0].problem_a == ids[0]
        assert len(repo.next_pairs(s, me.id)) == 8

        # promoting the tried problem to done promotes its comparison
        repo.set_ascents(s, me.id, ids + [tried_id], [])
        assert len(repo.all_comparisons(s, include_attempts=False)) == 2
        repo.set_ascents(s, me.id, ids, [tried_id])

        with pytest.raises(ValueError):
            repo.record_comparison(s, me.id, ids[0], int(problems[50].id), Verdict.SIMILAR)

        runs = repo.recompute_all(s)
        assert len(runs) == 6
        ranking = repo.latest_ranking(s, "bradley_terry")
        assert len(ranking) == 433
        assert repo.latest_run(s, "bradley_terry", True).n_comparisons == 2
        assert repo.latest_run(s, "bradley_terry", False).n_comparisons == 1
        assert ranking[0][0].rank == 1
        by_pid = {prob.id: snap for snap, prob in ranking}
        assert by_pid[ids[0]].rating > by_pid[ids[1]].rating or problems[0].seed_grade > problems[1].seed_grade

        mine = repo.personal(s, me.id)
        assert len(mine.ratings) == 5

        # removing a problem removes comparisons involving it
        repo.set_ascents(s, me.id, ids[1:], [])
        assert repo.climber_comparisons(s, me.id) == []


def test_import_upserts_without_disturbing_existing_rows(tmp_path):
    db = tmp_path / "t.sqlite"
    build_seed_db(PROBLEMS_CSV, db)
    with make_session_factory(db)() as s:
        first = repo.all_problems(s)[0]
    # importing the same file again adds nothing, refreshes everything, keeps ids
    added, updated = import_problems(PROBLEMS_CSV, db)
    assert (added, updated) == (0, 433)
    with make_session_factory(db)() as s:
        assert repo.all_problems(s)[0] == first

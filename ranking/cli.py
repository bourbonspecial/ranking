"""CLI: rank a CSV of comparisons, or run the simulator.

    ranking rank problems.csv comparisons.csv [--algo bradley_terry|elo|win_rate] [--prior-sd 100]
    ranking simulate [--problems N] [--climbers N] [--seed S] [--prior-sd 100]

    ranking db build-seed          rebuild data/seed.sqlite from data/hardest_problems.csv
    ranking db init [--force]      copy seed -> data/local.sqlite (gitignored)
    ranking db import [CSV] [--db PATH]   upsert problems from CSV into an existing db (default: local)
    ranking recompute [--db PATH]  fit every algorithm and store a snapshot
    ranking list [--algo A] [--db PATH]   print the latest stored ranking
    ranking serve [--host H] [--port P] [--reload]   run the API (env: RANKING_* see api/settings.py)
    ranking admin EMAIL [--name NAME]     create/promote an active admin in the local db

problems.csv columns:    id,name,seed_grade[,area,country,ascent_count]
comparisons.csv columns: climber_id,problem_a,problem_b,verdict[,created_at]
  verdict is one of A_HARDER, SIMILAR, B_HARDER; created_at is ISO-8601.
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime

from .bradley_terry import BradleyTerryConfig, fit_bradley_terry
from .confidence import confidence_tier
from .elo import EloConfig, replay_elo
from .models import Comparison, Problem, Verdict, latest_comparisons
from .result import RankingResult
from .winrate import win_rate


def load_problems(path: str) -> list[Problem]:
    with open(path, newline="") as f:
        return [
            Problem(
                id=r["id"], name=r.get("name", r["id"]), seed_grade=r["seed_grade"],
                area=r.get("area", ""), country=r.get("country", ""),
                ascent_count=int(r.get("ascent_count") or 0),
            )
            for r in csv.DictReader(f)
        ]


def load_comparisons(path: str) -> list[Comparison]:
    out = []
    with open(path, newline="") as f:
        for i, r in enumerate(csv.DictReader(f)):
            ts = r.get("created_at")
            created = datetime.fromisoformat(ts) if ts else datetime(2000, 1, 1) + __import__("datetime").timedelta(seconds=i)
            out.append(Comparison(r["climber_id"], r["problem_a"], r["problem_b"], Verdict(r["verdict"]), created))
    return out


def run(problems, comparisons, algo: str, prior_sd: float, k: float) -> RankingResult:
    comparisons = latest_comparisons(comparisons)
    if algo == "bradley_terry":
        return fit_bradley_terry(problems, comparisons, BradleyTerryConfig(prior_sd=prior_sd))
    if algo == "elo":
        return replay_elo(problems, comparisons, EloConfig(k=k))
    if algo == "win_rate":
        return win_rate(problems, comparisons)
    raise SystemExit(f"unknown algorithm {algo}")


def print_result(result: RankingResult, out=sys.stdout) -> None:
    w = csv.writer(out)
    w.writerow(["rank", "problem_id", "name", "seed_grade", "rating", "uncertainty",
                "n_comparisons", "n_climbers", "confidence"])
    for row in result.to_rows():
        w.writerow([row["rank"], row["problem_id"], row["name"], row["seed_grade"], row["rating"],
                    row["uncertainty"], row["n_comparisons"], row["n_climbers"],
                    confidence_tier(row["n_comparisons"], row["n_climbers"])])


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="ranking", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("rank")
    r.add_argument("problems")
    r.add_argument("comparisons")
    r.add_argument("--algo", default="bradley_terry", choices=["bradley_terry", "elo", "win_rate"])
    r.add_argument("--prior-sd", type=float, default=100.0)
    r.add_argument("--k", type=float, default=32.0)

    s = sub.add_parser("simulate")
    s.add_argument("--problems", type=int, default=120)
    s.add_argument("--climbers", type=int, default=40)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--prior-sd", type=float, default=100.0)
    s.add_argument("--k", type=float, default=32.0)
    s.add_argument("--fraction", type=float, default=1.0, help="fraction of possible pairs each climber answers")

    d = sub.add_parser("db")
    dsub = d.add_subparsers(dest="dbcmd", required=True)
    dsub.add_parser("build-seed")
    di = dsub.add_parser("init")
    di.add_argument("--force", action="store_true", help="overwrite an existing local db")
    dm = dsub.add_parser("import")
    dm.add_argument("csv", nargs="?", default=None)
    dm.add_argument("--db", default=None)

    rc = sub.add_parser("recompute")
    rc.add_argument("--db", default=None)
    rc.add_argument("--attempt-weight", type=float, default=0.4)

    ls = sub.add_parser("list")
    ls.add_argument("--algo", default="bradley_terry", choices=["bradley_terry", "elo", "win_rate"])
    ls.add_argument("--include-attempts", action="store_true")
    ls.add_argument("--db", default=None)

    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--reload", action="store_true")

    ad = sub.add_parser("admin")
    ad.add_argument("email")
    ad.add_argument("--name", default=None)
    ad.add_argument("--db", default=None)

    a = p.parse_args(argv)
    if a.cmd == "serve":
        import uvicorn
        uvicorn.run("ranking.api.main:app", host=a.host, port=a.port, reload=a.reload)
    elif a.cmd == "admin":
        from pathlib import Path
        from .db import init_local_db, make_session_factory
        from . import repo
        db_path = Path(a.db) if a.db else init_local_db()
        with make_session_factory(db_path)() as s:
            c = repo.get_climber_by_email(s, a.email)
            if c is None:
                c = repo.add_climber(s, a.name or a.email.split("@")[0], a.email, status="active", is_admin=True)
            else:
                c.is_admin, c.status = True, "active"
                if a.name:
                    c.name = a.name
            s.commit()
            print(f"admin: {c.name} <{c.email}> (id {c.id})")
    elif a.cmd == "db":
        from pathlib import Path
        from .db import LOCAL_DB, PROBLEMS_CSV, SEED_DB, init_local_db
        from .importer import build_seed_db, import_problems
        if a.dbcmd == "build-seed":
            n = build_seed_db()
            print(f"wrote {n} problems to {SEED_DB}")
        elif a.dbcmd == "import":
            db_path = Path(a.db) if a.db else init_local_db()
            added, updated = import_problems(Path(a.csv) if a.csv else PROBLEMS_CSV, db_path)
            print(f"{db_path}: {added} added, {updated} updated")
        else:
            existed = LOCAL_DB.exists()
            path = init_local_db(force=a.force)
            print(("kept existing " if existed and not a.force else "created ") + str(path))
    elif a.cmd in ("recompute", "list"):
        from pathlib import Path
        from .db import LOCAL_DB, init_local_db, make_session_factory
        from . import repo
        db_path = Path(a.db) if a.db else init_local_db()
        with make_session_factory(db_path)() as s:
            if a.cmd == "recompute":
                runs = repo.recompute_all(s, a.attempt_weight)
                for (algo, inc), run in runs.items():
                    print(f"{algo}{' +attempts' if inc else ''}: run {run.id}, {run.n_comparisons} comparisons")
            else:
                rows = repo.latest_ranking(s, a.algo, a.include_attempts)
                if not rows:
                    raise SystemExit("no stored ranking; run `ranking recompute` first")
                w = csv.writer(sys.stdout)
                w.writerow(["rank", "id", "name", "crag", "grade", "rating", "uncertainty", "n_comparisons", "n_climbers", "confidence"])
                for snap, prob in rows:
                    w.writerow([snap.rank, prob.id, prob.name, prob.crag, prob.current_grade, round(snap.rating, 1),
                                None if snap.uncertainty is None else round(snap.uncertainty, 1),
                                snap.n_comparisons, snap.n_climbers, confidence_tier(snap.n_comparisons, snap.n_climbers)])
    elif a.cmd == "rank":
        print_result(run(load_problems(a.problems), load_comparisons(a.comparisons), a.algo, a.prior_sd, a.k))
    else:
        from .simulate import SimConfig, simulate, spearman, kendall_tau
        world = simulate(SimConfig(n_problems=a.problems, n_climbers=a.climbers, seed=a.seed,
                                   fraction_of_pairs_answered=a.fraction))
        truth = world.true_order()
        seed_order = sorted(world.problems, key=lambda q: (-__import__("ranking.scale", fromlist=["x"]).grade_to_rating(q.seed_grade), q.id))
        print(f"{len(world.problems)} problems, {len(world.ticks)} climbers, {len(world.comparisons)} comparisons")
        print(f"{'algorithm':<16}{'spearman':>10}{'kendall':>10}")
        print(f"{'grade seed only':<16}{spearman(truth, [q.id for q in seed_order]):>10.3f}{kendall_tau(truth, [q.id for q in seed_order]):>10.3f}")
        for algo in ["bradley_terry", "elo", "win_rate"]:
            res = run(world.problems, world.comparisons, algo, a.prior_sd, a.k)
            print(f"{algo:<16}{spearman(truth, res.order()):>10.3f}{kendall_tau(truth, res.order()):>10.3f}")


if __name__ == "__main__":
    main()

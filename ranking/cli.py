"""CLI: rank a CSV of comparisons, or run the simulator.

    ranking rank problems.csv comparisons.csv [--algo bradley_terry|elo|win_rate] [--prior-sd 100]
    ranking simulate [--problems N] [--climbers N] [--seed S] [--prior-sd 100]

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

    a = p.parse_args(argv)
    if a.cmd == "rank":
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

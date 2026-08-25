"""Naive baseline: fraction of comparisons a problem was judged harder in.

Ties count as half. Problems with no comparisons get 0.5. Reported on a
0-1000 scale so it can sit in the same table as the others without being
mistaken for an Elo number. Useful only as a sanity check against the
model-based rankings.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence

from .confidence import confidence
from .models import Comparison, Problem, Verdict
from .result import ProblemRating, RankingResult


def win_rate(problems: Sequence[Problem], comparisons: Iterable[Comparison]) -> RankingResult:
    comparisons = list(comparisons)
    wins: dict[str, float] = defaultdict(float)
    games: dict[str, int] = defaultdict(int)
    for c in comparisons:
        games[c.problem_a] += 1
        games[c.problem_b] += 1
        if c.verdict is Verdict.A_HARDER:
            wins[c.problem_a] += 1
        elif c.verdict is Verdict.B_HARDER:
            wins[c.problem_b] += 1
        else:
            wins[c.problem_a] += 0.5
            wins[c.problem_b] += 0.5
    conf = confidence(comparisons)
    ratings = [
        ProblemRating(
            problem_id=p.id, name=p.name, seed_grade=p.seed_grade,
            rating=1000.0 * (wins[p.id] / games[p.id] if games[p.id] else 0.5),
            uncertainty=None,
            n_comparisons=conf.get(p.id, (0, 0))[0], n_climbers=conf.get(p.id, (0, 0))[1],
        )
        for p in problems
    ]
    return RankingResult("win_rate", ratings, {"n_comparisons": len(comparisons)})

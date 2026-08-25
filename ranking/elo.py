"""Sequential Elo, replayed over comparisons in chronological order.

Kept as the familiar reference point. Order-dependent by construction,
so it is replayed from scratch each time rather than updated in place.
Ties are scored 0.5 each.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .confidence import confidence
from .models import Comparison, Problem, Verdict
from .result import ProblemRating, RankingResult
from .scale import grade_to_rating


@dataclass
class EloConfig:
    k: float = 32.0


def expected_score(r_a: float, r_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))


def replay_elo(
    problems: Sequence[Problem],
    comparisons: Iterable[Comparison],
    config: EloConfig | None = None,
) -> RankingResult:
    config = config or EloConfig()
    comparisons = sorted(comparisons, key=lambda c: (c.created_at, c.key))
    rating = {p.id: grade_to_rating(p.seed_grade) for p in problems}
    for c in comparisons:
        a, b = c.problem_a, c.problem_b
        s_a = {Verdict.A_HARDER: 1.0, Verdict.B_HARDER: 0.0, Verdict.SIMILAR: 0.5}[c.verdict]
        e_a = expected_score(rating[a], rating[b])
        delta = config.k * (s_a - e_a)
        rating[a] += delta
        rating[b] -= delta
    conf = confidence(comparisons)
    ratings = [
        ProblemRating(
            problem_id=p.id, name=p.name, seed_grade=p.seed_grade,
            rating=rating[p.id], uncertainty=None,
            n_comparisons=conf.get(p.id, (0, 0))[0], n_climbers=conf.get(p.id, (0, 0))[1],
        )
        for p in problems
    ]
    return RankingResult("elo", ratings, {"k": config.k, "n_comparisons": len(comparisons)})

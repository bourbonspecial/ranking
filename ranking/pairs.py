"""Pair selection for the compare flow.

Given a climber's ticked problems and what has already been compared,
return the unanswered pairs ordered so that the most informative come
first: pairs involving problems with few known ascents (rare problems)
and few comparisons already in the system.
"""
from __future__ import annotations

from itertools import combinations
from typing import Iterable, Sequence

from .confidence import confidence
from .models import Comparison, Problem


def pair_queue(
    climber_id: str,
    ticked: Sequence[Problem],
    all_comparisons: Iterable[Comparison],
    ascent_weight: float = 1.0,
    comparison_weight: float = 1.0,
    tried: Iterable[str] = (),
) -> list[tuple[str, str]]:
    """Unanswered pairs, most informative first.

    `tried` is the subset of `ticked` ids the climber has attempted but not
    climbed. Pairs of two climbed problems always come first, then pairs with
    one attempted problem, then pairs of two attempted problems.
    """
    all_comparisons = list(all_comparisons)
    tried = set(tried)
    answered = {c.pair for c in all_comparisons if c.climber_id == climber_id}
    conf = confidence(all_comparisons)
    by_id = {p.id: p for p in ticked}

    def scarcity(pid: str) -> float:
        n_asc = by_id[pid].ascent_count
        n_cmp = conf.get(pid, (0, 0))[0]
        # lower score = scarcer = show earlier
        return ascent_weight * n_asc + comparison_weight * n_cmp

    candidates = [
        tuple(sorted((a.id, b.id)))
        for a, b in combinations(ticked, 2)
        if tuple(sorted((a.id, b.id))) not in answered
    ]
    def n_tried(pr) -> int:
        return (pr[0] in tried) + (pr[1] in tried)

    candidates.sort(key=lambda pr: (n_tried(pr), min(scarcity(pr[0]), scarcity(pr[1])),
                                    scarcity(pr[0]) + scarcity(pr[1]), pr))
    return candidates


def pair_kind(pair: tuple[str, str], tried: set[str]) -> str:
    return "attempt" if (pair[0] in tried or pair[1] in tried) else "done"


def max_pairs(n_ticked: int) -> int:
    return n_ticked * (n_ticked - 1) // 2


def ranking_gate_threshold(n_ticked: int, required: int = 10) -> int:
    return min(required, max_pairs(n_ticked))

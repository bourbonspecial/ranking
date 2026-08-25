"""Per-problem data-volume measures used for the confidence indicator."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import Comparison


def confidence(comparisons: Iterable[Comparison]) -> dict[str, tuple[int, int]]:
    """Return {problem_id: (n_comparisons, n_distinct_climbers)}."""
    n_comp: dict[str, int] = defaultdict(int)
    climbers: dict[str, set[str]] = defaultdict(set)
    for c in comparisons:
        for p in c.pair:
            n_comp[p] += 1
            climbers[p].add(c.climber_id)
    return {p: (n_comp[p], len(climbers[p])) for p in n_comp}


def confidence_tier(n_comparisons: int, n_climbers: int) -> str:
    if n_comparisons == 0:
        return "none"
    if n_climbers >= 5 and n_comparisons >= 15:
        return "high"
    if n_climbers >= 2 and n_comparisons >= 5:
        return "medium"
    return "low"

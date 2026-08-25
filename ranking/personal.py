"""Per-climber ranking: the same Bradley-Terry model fitted to one
climber's comparisons only, over the problems they have ticked.

A weak prior is still needed so that a climber who has only compared some
of their ticks gets a finite answer for the rest; those simply sit at
their grade seed with high uncertainty.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from .bradley_terry import BradleyTerryConfig, fit_bradley_terry
from .models import Comparison, Problem
from .result import RankingResult


def personal_ranking(
    climber_id: str,
    ticked: Sequence[Problem],
    comparisons: Iterable[Comparison],
    config: BradleyTerryConfig | None = None,
) -> RankingResult:
    ticked_ids = {p.id for p in ticked}
    mine = [
        c for c in comparisons
        if c.climber_id == climber_id and c.problem_a in ticked_ids and c.problem_b in ticked_ids
    ]
    config = config or BradleyTerryConfig(prior_sd=400.0, fit_tie_param=False)
    result = fit_bradley_terry(ticked, mine, config)
    result.algorithm = "personal_bradley_terry"
    result.params["climber_id"] = climber_id
    return result

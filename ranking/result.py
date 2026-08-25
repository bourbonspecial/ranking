from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


def _natural(pid: str):
    return (0, int(pid), "") if pid.isdigit() else (1, 0, pid)


@dataclass
class ProblemRating:
    problem_id: str
    rating: float
    uncertainty: float | None  # standard deviation on the rating scale, if the model gives one
    n_comparisons: int
    n_climbers: int
    seed_grade: str | None = None
    name: str | None = None
    rank: int | None = None


@dataclass
class RankingResult:
    algorithm: str
    ratings: list[ProblemRating]
    params: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.ratings.sort(key=lambda r: (-r.rating, _natural(r.problem_id)))
        for i, r in enumerate(self.ratings, start=1):
            r.rank = i

    def by_id(self) -> dict[str, ProblemRating]:
        return {r.problem_id: r for r in self.ratings}

    def order(self) -> list[str]:
        return [r.problem_id for r in self.ratings]

    def rating_of(self, problem_id: str) -> float:
        return self.by_id()[problem_id].rating

    def to_rows(self) -> Iterable[dict]:
        for r in self.ratings:
            yield {
                "rank": r.rank,
                "problem_id": r.problem_id,
                "name": r.name,
                "seed_grade": r.seed_grade,
                "rating": round(r.rating, 1),
                "uncertainty": None if r.uncertainty is None else round(r.uncertainty, 1),
                "n_comparisons": r.n_comparisons,
                "n_climbers": r.n_climbers,
            }

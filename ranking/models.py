from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable


class Verdict(str, Enum):
    A_HARDER = "A_HARDER"
    SIMILAR = "SIMILAR"
    B_HARDER = "B_HARDER"

    def flipped(self) -> "Verdict":
        if self is Verdict.A_HARDER:
            return Verdict.B_HARDER
        if self is Verdict.B_HARDER:
            return Verdict.A_HARDER
        return Verdict.SIMILAR


@dataclass(frozen=True)
class Problem:
    id: str
    name: str
    seed_grade: str
    area: str = ""
    country: str = ""
    ascent_count: int = 0


@dataclass(frozen=True)
class Comparison:
    """One climber's opinion on one pair.

    Stored canonically with problem_a < problem_b so that the same pair
    always has the same key regardless of which was shown on the left.
    """
    climber_id: str
    problem_a: str
    problem_b: str
    verdict: Verdict
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    weight: float = 1.0  # 1.0 = both problems climbed; < 1 when either was only attempted

    def __post_init__(self) -> None:
        if self.problem_a == self.problem_b:
            raise ValueError("cannot compare a problem with itself")
        if not 0 < self.weight <= 1:
            raise ValueError("weight must be in (0, 1]")
        if self.problem_a > self.problem_b:
            a, b = self.problem_a, self.problem_b
            object.__setattr__(self, "problem_a", b)
            object.__setattr__(self, "problem_b", a)
            object.__setattr__(self, "verdict", self.verdict.flipped())

    @property
    def pair(self) -> tuple[str, str]:
        return (self.problem_a, self.problem_b)

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.climber_id, self.problem_a, self.problem_b)

    @property
    def harder(self) -> str | None:
        if self.verdict is Verdict.A_HARDER:
            return self.problem_a
        if self.verdict is Verdict.B_HARDER:
            return self.problem_b
        return None


def latest_comparisons(comparisons: Iterable[Comparison]) -> list[Comparison]:
    """Keep only the most recent comparison per (climber, pair).

    A climber may revise an answer; only their latest opinion counts.
    Output is sorted by created_at so sequential algorithms (Elo) see
    a stable, chronological order.
    """
    latest: dict[tuple[str, str, str], Comparison] = {}
    for c in comparisons:
        prev = latest.get(c.key)
        if prev is None or c.created_at >= prev.created_at:
            latest[c.key] = c
    return sorted(latest.values(), key=lambda c: (c.created_at, c.key))

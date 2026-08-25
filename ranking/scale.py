"""Rating scale shared by every algorithm.

Ratings are reported on an Elo-like scale so they are comparable across
algorithms. Internally Bradley-Terry works in log-strength (theta); the
conversion is the standard Elo one: a 400 point gap is 10:1 odds.
"""
from __future__ import annotations

import math

GRADE_SEED: dict[str, float] = {
    "8C": 1500.0,
    "8C+": 1750.0,
    "9A": 2000.0,
    "9A+": 2250.0,
}

BASE_RATING = 1500.0
THETA_PER_RATING = math.log(10) / 400.0  # theta = (rating - base) * this


def grade_to_rating(grade: str) -> float:
    try:
        return GRADE_SEED[grade.upper()]
    except KeyError:
        raise ValueError(f"unknown grade {grade!r}; known: {sorted(GRADE_SEED)}") from None


def rating_to_theta(rating: float) -> float:
    return (rating - BASE_RATING) * THETA_PER_RATING


def theta_to_rating(theta: float) -> float:
    return BASE_RATING + theta / THETA_PER_RATING

from datetime import datetime, timedelta

import pytest

from ranking import Comparison, Problem, Verdict


@pytest.fixture
def problems():
    return [
        Problem("a", "Alpha", "8C"),
        Problem("b", "Bravo", "8C"),
        Problem("c", "Charlie", "8C+"),
        Problem("d", "Delta", "9A"),
    ]


def make(climber, a, b, v, minute=0):
    return Comparison(climber, a, b, v, datetime(2026, 1, 1) + timedelta(minutes=minute))

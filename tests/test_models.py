from datetime import datetime, timedelta

import pytest

from ranking import Comparison, Verdict, latest_comparisons
from conftest import make


def test_canonical_ordering_flips_verdict():
    c = Comparison("x", "b", "a", Verdict.A_HARDER)
    assert c.pair == ("a", "b")
    assert c.verdict is Verdict.B_HARDER
    assert c.harder == "b"


def test_similar_is_symmetric():
    c = Comparison("x", "b", "a", Verdict.SIMILAR)
    assert c.verdict is Verdict.SIMILAR
    assert c.harder is None


def test_self_comparison_rejected():
    with pytest.raises(ValueError):
        Comparison("x", "a", "a", Verdict.SIMILAR)


def test_latest_comparisons_keeps_most_recent_per_climber_pair():
    old = make("x", "a", "b", Verdict.A_HARDER, 0)
    new = make("x", "b", "a", Verdict.A_HARDER, 5)  # revised: now b harder
    other = make("y", "a", "b", Verdict.SIMILAR, 1)
    out = latest_comparisons([new, old, other])
    assert len(out) == 2
    mine = [c for c in out if c.climber_id == "x"][0]
    assert mine.verdict is Verdict.B_HARDER
    assert out == sorted(out, key=lambda c: c.created_at)

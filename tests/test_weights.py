from ranking import Comparison, EloConfig, Verdict, fit_bradley_terry, replay_elo, win_rate
from ranking.pairs import pair_queue, pair_kind
from ranking import Problem
from conftest import make
import pytest


def weighted(climber, a, b, v, minute, w):
    c = make(climber, a, b, v, minute)
    return Comparison(c.climber_id, c.problem_a, c.problem_b, c.verdict, c.created_at, weight=w)


def test_weight_validation():
    with pytest.raises(ValueError):
        weighted("x", "a", "b", Verdict.A_HARDER, 0, 0.0)
    with pytest.raises(ValueError):
        weighted("x", "a", "b", Verdict.A_HARDER, 0, 1.5)


def test_bt_lower_weight_moves_less(problems):
    full = [make(f"c{i}", "a", "b", Verdict.A_HARDER, i) for i in range(10)]
    light = [weighted(f"c{i}", "a", "b", Verdict.A_HARDER, i, 0.4) for i in range(10)]
    gap_full = fit_bradley_terry(problems, full).rating_of("a") - fit_bradley_terry(problems, full).rating_of("b")
    gap_light = fit_bradley_terry(problems, light).rating_of("a") - fit_bradley_terry(problems, light).rating_of("b")
    assert 0 < gap_light < gap_full
    # 10 comparisons at weight 0.4 == 4 comparisons at weight 1
    four = [make(f"c{i}", "a", "b", Verdict.A_HARDER, i) for i in range(4)]
    r4 = fit_bradley_terry(problems, four)
    assert abs((r4.rating_of("a") - r4.rating_of("b")) - gap_light) < 1e-3


def test_elo_scales_k(problems):
    r = replay_elo(problems, [weighted("x", "a", "b", Verdict.A_HARDER, 0, 0.5)], EloConfig(k=32))
    assert r.rating_of("a") == 1508.0


def test_winrate_weighted(problems):
    r = win_rate(problems, [make("x", "a", "b", Verdict.A_HARDER, 0),
                            weighted("y", "b", "a", Verdict.A_HARDER, 1, 0.5)])
    # a: 1 win of 1.5 games
    assert abs(r.rating_of("a") - 1000 * (1 / 1.5)) < 1e-9


def test_pair_queue_done_first():
    ticked = [Problem("d1", "", "8C+", ascent_count=1), Problem("d2", "", "8C+", ascent_count=1),
              Problem("t1", "", "8C+", ascent_count=1)]
    q = pair_queue("me", ticked, [], tried=["t1"])
    assert q[0] == ("d1", "d2")
    assert pair_kind(q[0], {"t1"}) == "done"
    assert all(pair_kind(pr, {"t1"}) == "attempt" for pr in q[1:])

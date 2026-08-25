from ranking import EloConfig, Verdict, replay_elo, win_rate
from conftest import make


def test_elo_zero_sum_and_direction(problems):
    comps = [make("x", "a", "b", Verdict.A_HARDER)]
    res = replay_elo(problems, comps, EloConfig(k=32))
    assert res.rating_of("a") == 1516.0
    assert res.rating_of("b") == 1484.0


def test_elo_tie_between_unequal_moves_towards_each_other(problems):
    res = replay_elo(problems, [make("x", "a", "d", Verdict.SIMILAR)])
    assert res.rating_of("a") > 1500 and res.rating_of("d") < 2000


def test_elo_is_replayed_in_time_order(problems):
    late = make("x", "a", "b", Verdict.A_HARDER, 10)
    early = make("y", "a", "b", Verdict.B_HARDER, 0)
    assert replay_elo(problems, [late, early]).ratings == replay_elo(problems, [early, late]).ratings


def test_win_rate(problems):
    comps = [make("x", "a", "b", Verdict.A_HARDER), make("y", "a", "b", Verdict.SIMILAR)]
    res = win_rate(problems, comps)
    assert res.rating_of("a") == 750.0
    assert res.rating_of("b") == 250.0
    assert res.rating_of("d") == 500.0

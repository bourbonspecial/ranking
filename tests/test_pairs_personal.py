from ranking import Problem, Verdict
from ranking.pairs import max_pairs, pair_queue, ranking_gate_threshold
from ranking.personal import personal_ranking
from conftest import make


def test_pair_queue_excludes_answered_and_prefers_rare():
    ticked = [
        Problem("common", "C", "8C", ascent_count=50),
        Problem("rare", "R", "8C", ascent_count=1),
        Problem("mid", "M", "8C+", ascent_count=10),
    ]
    answered = [make("me", "common", "mid", Verdict.A_HARDER)]
    q = pair_queue("me", ticked, answered)
    assert ("common", "mid") not in q
    assert len(q) == 2
    assert all("rare" in pr for pr in q)
    # the pair with the least-compared partner comes first: mid has 1 comparison, common has 1,
    # ascent counts break it: mid (10) before common (50)
    assert q[0] == ("mid", "rare")


def test_gate_threshold():
    assert max_pairs(5) == 10
    assert ranking_gate_threshold(3) == 3
    assert ranking_gate_threshold(20) == 10
    assert ranking_gate_threshold(2) == 1


def test_personal_ranking_uses_only_own_votes(problems):
    comps = [
        make("me", "a", "d", Verdict.A_HARDER, 0),
        make("other", "d", "a", Verdict.A_HARDER, 1),
        make("other", "d", "a", Verdict.A_HARDER, 2),
    ]
    res = personal_ranking("me", problems, comps)
    assert res.params["n_comparisons"] == 1
    assert res.rating_of("a") > 1500 and res.rating_of("d") < 2000

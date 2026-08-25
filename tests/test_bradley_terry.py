import numpy as np

from ranking import BradleyTerryConfig, Verdict, fit_bradley_terry, grade_to_rating
from ranking.bradley_terry import _neg_log_post
from conftest import make


def test_no_data_returns_grade_seeds(problems):
    res = fit_bradley_terry(problems, [])
    for r in res.ratings:
        assert r.rating == grade_to_rating(r.seed_grade)
        assert r.n_comparisons == 0
        assert r.uncertainty is not None and r.uncertainty > 0


def test_consistent_votes_reorder_problems(problems):
    # everyone says the 8C "a" is harder than the 9A "d"
    comps = [make(f"c{i}", "a", "d", Verdict.A_HARDER, i) for i in range(30)]
    res = fit_bradley_terry(problems, comps, BradleyTerryConfig(prior_sd=200))
    assert res.rating_of("a") > res.rating_of("d")


def test_prior_fades_with_data(problems):
    weak, strong = [], []
    for n in (2, 10, 50):
        comps = [make(f"c{i}", "a", "d", Verdict.A_HARDER, i) for i in range(n)]
        res = fit_bradley_terry(problems, comps)
        gap = res.rating_of("a") - res.rating_of("d")
        strong.append(gap)
    assert strong[0] < strong[1] < strong[2]


def test_uncertainty_shrinks_with_data(problems):
    u = []
    for n in (0, 5, 40):
        comps = [make(f"c{i}", "a", "b", Verdict.SIMILAR if i % 2 else Verdict.A_HARDER, i) for i in range(n)]
        res = fit_bradley_terry(problems, comps)
        u.append(res.by_id()["a"].uncertainty)
    assert u[0] > u[1] > u[2]
    # untouched problem keeps prior uncertainty
    assert abs(res.by_id()["d"].uncertainty - 100.0) < 1e-6


def test_ties_pull_ratings_together(problems):
    comps = [make(f"c{i}", "a", "d", Verdict.SIMILAR, i) for i in range(40)]
    res = fit_bradley_terry(problems, comps)
    assert abs(res.rating_of("a") - res.rating_of("d")) < 250  # seeds are 500 apart


def test_gradient_matches_finite_differences():
    rng = np.random.default_rng(1)
    n = 5
    ia = rng.integers(0, n, 40); ib = (ia + rng.integers(1, n, 40)) % n
    y = rng.integers(0, 3, 40)
    mu = rng.normal(0, 1, n); pv = 0.8
    x = np.concatenate([rng.normal(0, 1, n), [np.log(0.7)]])
    f0, g = _neg_log_post(x, ia, ib, y, mu, pv, n, True, 0.5)
    eps = 1e-6
    for k in range(n + 1):
        e = np.zeros(n + 1); e[k] = eps
        fd = (_neg_log_post(x + e, ia, ib, y, mu, pv, n, True, 0.5)[0]
              - _neg_log_post(x - e, ia, ib, y, mu, pv, n, True, 0.5)[0]) / (2 * eps)
        assert abs(fd - g[k]) < 1e-5


def test_result_is_ranked(problems):
    res = fit_bradley_terry(problems, [])
    assert [r.rank for r in res.ratings] == [1, 2, 3, 4]
    assert res.order()[0] == "d"

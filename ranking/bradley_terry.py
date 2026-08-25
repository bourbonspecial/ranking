"""Bradley-Terry model with ties (Davidson 1970) and a grade-based prior.

Model, for problems i, j with log-strengths theta_i, theta_j and tie
parameter nu > 0:

    P(i harder)  = e^theta_i / D
    P(j harder)  = e^theta_j / D
    P(similar)   = nu * e^((theta_i+theta_j)/2) / D
    D            = e^theta_i + e^theta_j + nu * e^((theta_i+theta_j)/2)

Prior: theta_i ~ Normal(seed_i, sigma^2) where seed_i is the grade seed on
the theta scale. The prior is what keeps problems with no data at their
grade rating; as comparisons accumulate the likelihood dominates and the
seed becomes irrelevant. `prior_sd` (on the rating scale) controls how fast.

Fitted by MAP with L-BFGS. Uncertainty from the diagonal of the inverse
Hessian at the optimum (Laplace approximation).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from scipy.optimize import minimize

from .confidence import confidence
from .models import Comparison, Problem, Verdict
from .result import ProblemRating, RankingResult
from .scale import grade_to_rating, rating_to_theta, theta_to_rating, THETA_PER_RATING


@dataclass
class BradleyTerryConfig:
    prior_sd: float = 100.0      # rating points; larger = weaker pull towards grade seed.
                                 # 100 ~= the seed is outweighed after ~12 comparisons; best on the simulator.
    fit_tie_param: bool = True   # learn nu from data; else use fixed_nu
    fixed_nu: float = 0.5
    min_nu: float = 1e-3
    max_nu: float = 5.0
    # weak prior on log(nu) so a run of all-ties (or no ties) cannot send nu to a bound
    log_nu_prior_mean: float = -0.7   # ~ nu = 0.5
    log_nu_prior_sd: float = 1.5


def _encode(problems: Sequence[Problem], comparisons: Iterable[Comparison]):
    index = {p.id: k for k, p in enumerate(problems)}
    ia, ib, y, w = [], [], [], []
    for c in comparisons:
        if c.problem_a not in index or c.problem_b not in index:
            raise KeyError(f"comparison references unknown problem: {c.pair}")
        ia.append(index[c.problem_a])
        ib.append(index[c.problem_b])
        y.append({Verdict.A_HARDER: 0, Verdict.B_HARDER: 1, Verdict.SIMILAR: 2}[c.verdict])
        w.append(c.weight)
    return (index, np.array(ia, dtype=int), np.array(ib, dtype=int), np.array(y, dtype=int),
            np.array(w, dtype=float))


def _neg_log_post(params, ia, ib, y, w, mu, prior_var, n, fit_nu, fixed_nu, nu_mu=-0.7, nu_var=2.25):
    theta = params[:n]
    log_nu = params[n] if fit_nu else np.log(fixed_nu)
    ta, tb = theta[ia], theta[ib]
    mid = 0.5 * (ta + tb) + log_nu
    # log D via logsumexp of (ta, tb, mid)
    m = np.maximum(np.maximum(ta, tb), mid)
    ea, eb, em = np.exp(ta - m), np.exp(tb - m), np.exp(mid - m)
    D = ea + eb + em
    logD = m + np.log(D)
    chosen = np.where(y == 0, ta, np.where(y == 1, tb, mid))
    nll = np.sum(w * (logD - chosen))
    nlp = 0.5 * np.sum((theta - mu) ** 2 / prior_var)

    # gradient
    pa, pb, pm = ea / D, eb / D, em / D
    g_theta = np.zeros(n)
    # d(logD)/d ta = pa + 0.5 pm ; d/d tb = pb + 0.5 pm
    ga = w * (pa + 0.5 * pm - np.where(y == 0, 1.0, np.where(y == 2, 0.5, 0.0)))
    gb = w * (pb + 0.5 * pm - np.where(y == 1, 1.0, np.where(y == 2, 0.5, 0.0)))
    np.add.at(g_theta, ia, ga)
    np.add.at(g_theta, ib, gb)
    g_theta += (theta - mu) / prior_var
    if fit_nu:
        nlp += 0.5 * (log_nu - nu_mu) ** 2 / nu_var
        g_nu = np.sum(w * (pm - (y == 2))) + (log_nu - nu_mu) / nu_var
        grad = np.concatenate([g_theta, [g_nu]])
    else:
        grad = g_theta
    return nll + nlp, grad


def _hessian_theta(theta, log_nu, ia, ib, w, prior_var, n):
    """Hessian of the negative log posterior w.r.t. theta only (nu held fixed)."""
    ta, tb = theta[ia], theta[ib]
    mid = 0.5 * (ta + tb) + log_nu
    m = np.maximum(np.maximum(ta, tb), mid)
    ea, eb, em = np.exp(ta - m), np.exp(tb - m), np.exp(mid - m)
    D = ea + eb + em
    pa, pb, pm = ea / D, eb / D, em / D
    # second derivatives of logD (log-sum-exp of linear functions)
    # let u = (1, 0, .5), v = (0, 1, .5) be d(ta,tb,mid)/d(ta), d/d(tb)
    Ea = pa + 0.5 * pm          # E[u]
    Eb = pb + 0.5 * pm          # E[v]
    Euu = pa + 0.25 * pm        # E[u^2]
    Evv = pb + 0.25 * pm
    Euv = 0.25 * pm
    haa = w * (Euu - Ea * Ea)
    hbb = w * (Evv - Eb * Eb)
    hab = w * (Euv - Ea * Eb)
    H = np.zeros((n, n))
    np.add.at(H, (ia, ia), haa)
    np.add.at(H, (ib, ib), hbb)
    np.add.at(H, (ia, ib), hab)
    np.add.at(H, (ib, ia), hab)
    H[np.diag_indices(n)] += 1.0 / prior_var
    return H


def fit_bradley_terry(
    problems: Sequence[Problem],
    comparisons: Iterable[Comparison],
    config: BradleyTerryConfig | None = None,
) -> RankingResult:
    config = config or BradleyTerryConfig()
    comparisons = list(comparisons)
    n = len(problems)
    index, ia, ib, y, w = _encode(problems, comparisons)

    mu = np.array([rating_to_theta(grade_to_rating(p.seed_grade)) for p in problems])
    prior_var = (config.prior_sd * THETA_PER_RATING) ** 2

    x0 = mu.copy()
    if config.fit_tie_param:
        x0 = np.concatenate([x0, [np.log(config.fixed_nu)]])
    bounds = [(None, None)] * n + ([(np.log(config.min_nu), np.log(config.max_nu))] if config.fit_tie_param else [])

    if len(comparisons) == 0:
        theta, log_nu = mu, np.log(config.fixed_nu)
    else:
        res = minimize(
            _neg_log_post, x0, jac=True, method="L-BFGS-B", bounds=bounds,
            args=(ia, ib, y, w, mu, prior_var, n, config.fit_tie_param, config.fixed_nu,
                  config.log_nu_prior_mean, config.log_nu_prior_sd ** 2),
            options={"maxiter": 5000},
        )
        theta = res.x[:n]
        log_nu = res.x[n] if config.fit_tie_param else np.log(config.fixed_nu)

    H = _hessian_theta(theta, log_nu, ia, ib, w, prior_var, n)
    cov_diag = np.diag(np.linalg.inv(H))
    sd_rating = np.sqrt(np.maximum(cov_diag, 0)) / THETA_PER_RATING

    conf = confidence(comparisons)
    ratings = []
    for p in problems:
        k = index[p.id]
        n_c, n_cl = conf.get(p.id, (0, 0))
        ratings.append(ProblemRating(
            problem_id=p.id, name=p.name, seed_grade=p.seed_grade,
            rating=float(theta_to_rating(theta[k])),
            uncertainty=float(sd_rating[k]),
            n_comparisons=n_c, n_climbers=n_cl,
        ))
    return RankingResult(
        algorithm="bradley_terry",
        ratings=ratings,
        params={"prior_sd": config.prior_sd, "nu": float(np.exp(log_nu)),
                "n_comparisons": len(comparisons)},
    )

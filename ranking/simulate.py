"""Synthetic world for testing and tuning the ranking algorithms.

Each problem has a hidden true difficulty on the rating scale. Its seed
grade is derived from that difficulty with deliberate noise, so some
problems are "mis-graded" relative to their true difficulty - exactly the
situation the system is meant to expose.

Each climber has a strength, a tick list drawn from problems around and
below their strength (biased towards well-known problems), a personal bias
per problem (style fit) and per-answer noise. Their verdict on a pair is
'similar' if the perceived gap is below their tie threshold.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from .models import Comparison, Problem, Verdict
from .scale import GRADE_SEED


@dataclass
class SimConfig:
    n_problems: int = 120
    n_climbers: int = 40
    seed: int = 0
    # true difficulty spread
    difficulty_min: float = 1400.0
    difficulty_max: float = 2350.0
    grade_noise_sd: float = 90.0        # how badly seed grades reflect true difficulty
    # climbers
    style_bias_sd: float = 80.0         # per (climber, problem) persistent bias
    answer_noise_sd: float = 40.0       # per-answer noise
    tie_threshold: float = 50.0         # perceived gap below which they say "similar"
    ticks_min: int = 2
    ticks_max: int = 30
    fraction_of_pairs_answered: float = 1.0


@dataclass
class SimWorld:
    problems: list[Problem]
    true_difficulty: dict[str, float]
    ticks: dict[str, list[str]]
    comparisons: list[Comparison]
    config: SimConfig = field(repr=False, default_factory=SimConfig)

    def true_order(self) -> list[str]:
        return sorted(self.true_difficulty, key=lambda p: -self.true_difficulty[p])


def _grade_for(difficulty: float) -> str:
    # nearest seed grade by rating, boundaries half way between seeds
    grades = sorted(GRADE_SEED.items(), key=lambda kv: kv[1])
    best = grades[0][0]
    for g, r in grades:
        if difficulty >= r - 125.0:
            best = g
    return best


def simulate(config: SimConfig | None = None) -> SimWorld:
    cfg = config or SimConfig()
    rng = np.random.default_rng(cfg.seed)

    # problems: more easy ones than hard ones (roughly exponential fall-off)
    u = rng.random(cfg.n_problems)
    diffs = cfg.difficulty_min + (cfg.difficulty_max - cfg.difficulty_min) * (u ** 2.0)
    popularity = np.exp(-(diffs - cfg.difficulty_min) / 300.0) * rng.lognormal(0, 0.7, cfg.n_problems)
    ascents = np.maximum(1, np.round(popularity * 30)).astype(int)

    problems, true_difficulty = [], {}
    for k in range(cfg.n_problems):
        pid = f"p{k:03d}"
        graded = diffs[k] + rng.normal(0, cfg.grade_noise_sd)
        problems.append(Problem(id=pid, name=f"Problem {k}", seed_grade=_grade_for(graded),
                                ascent_count=int(ascents[k])))
        true_difficulty[pid] = float(diffs[k])

    t0 = datetime(2026, 1, 1)
    ticks: dict[str, list[str]] = {}
    comparisons: list[Comparison] = []
    for c in range(cfg.n_climbers):
        cid = f"c{c:03d}"
        strength = rng.uniform(cfg.difficulty_min + 100, cfg.difficulty_max)
        n_ticks = int(rng.integers(cfg.ticks_min, cfg.ticks_max + 1))
        # prefer problems below strength and popular ones
        w = np.exp(-np.maximum(0, diffs - strength) / 60.0) * popularity
        w /= w.sum()
        n_ticks = min(n_ticks, int((w > 1e-9).sum()))
        chosen = rng.choice(cfg.n_problems, size=n_ticks, replace=False, p=w)
        tick_ids = [problems[k].id for k in chosen]
        ticks[cid] = tick_ids

        bias = {pid: rng.normal(0, cfg.style_bias_sd) for pid in tick_ids}
        perceived = {pid: true_difficulty[pid] + bias[pid] for pid in tick_ids}
        pairs = [(a, b) for i, a in enumerate(tick_ids) for b in tick_ids[i + 1:]]
        rng.shuffle(pairs)
        n_answer = int(round(len(pairs) * cfg.fraction_of_pairs_answered))
        for i, (a, b) in enumerate(pairs[:n_answer]):
            gap = (perceived[a] - perceived[b]) + rng.normal(0, cfg.answer_noise_sd)
            if abs(gap) < cfg.tie_threshold:
                v = Verdict.SIMILAR
            elif gap > 0:
                v = Verdict.A_HARDER
            else:
                v = Verdict.B_HARDER
            comparisons.append(Comparison(cid, a, b, v, t0 + timedelta(minutes=len(comparisons))))
    return SimWorld(problems, true_difficulty, ticks, comparisons, cfg)


def spearman(order_a: list[str], order_b: list[str]) -> float:
    ra = {p: i for i, p in enumerate(order_a)}
    rb = {p: i for i, p in enumerate(order_b)}
    common = [p for p in order_a if p in rb]
    if len(common) < 2:
        return float("nan")
    x = np.array([ra[p] for p in common], dtype=float)
    y = np.array([rb[p] for p in common], dtype=float)
    return float(np.corrcoef(x, y)[0, 1])


def kendall_tau(order_a: list[str], order_b: list[str]) -> float:
    from scipy.stats import kendalltau
    ra = {p: i for i, p in enumerate(order_a)}
    rb = {p: i for i, p in enumerate(order_b)}
    common = [p for p in order_a if p in rb]
    return float(kendalltau([ra[p] for p in common], [rb[p] for p in common]).statistic)

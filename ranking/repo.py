"""Repository layer: everything the API and CLI do to the database.

Converts between ORM rows and the plain engine types in ranking.models,
so the rating algorithms never touch SQLAlchemy.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import select
from sqlalchemy.orm import Session

from .bradley_terry import BradleyTerryConfig, fit_bradley_terry
from .db import (
    AscentRow, ClimberRow, ComparisonHistoryRow, ComparisonRow, ProblemRow,
    RatingRunRow, RatingSnapshotRow,
)
from .elo import EloConfig, replay_elo
from .models import Comparison, Problem, Verdict
from .pairs import pair_queue, ranking_gate_threshold
from .personal import personal_ranking
from .result import RankingResult
from .winrate import win_rate

ALGORITHMS = ("bradley_terry", "elo", "win_rate")


# ---- conversions -----------------------------------------------------------

def to_problem(row: ProblemRow) -> Problem:
    return Problem(id=str(row.id), name=row.name, seed_grade=row.seed_grade,
                   area=row.crag, country=row.country, ascent_count=row.ascent_count)


def to_comparison(row: ComparisonRow) -> Comparison:
    return Comparison(str(row.climber_id), str(row.problem_a), str(row.problem_b),
                      Verdict(row.verdict), row.updated_at)


# ---- problems ---------------------------------------------------------------

def all_problems(s: Session) -> list[Problem]:
    return [to_problem(r) for r in s.scalars(select(ProblemRow).order_by(ProblemRow.id))]


def get_problem(s: Session, problem_id: int) -> ProblemRow | None:
    return s.get(ProblemRow, problem_id)


# ---- climbers & ascents -----------------------------------------------------

def add_climber(s: Session, name: str, email: str, status: str = "active",
                is_admin: bool = False, request_note: str = "") -> ClimberRow:
    c = ClimberRow(name=name, email=email.lower().strip(), status=status,
                   is_admin=is_admin, request_note=request_note)
    s.add(c)
    s.flush()
    return c


def get_climber_by_email(s: Session, email: str) -> ClimberRow | None:
    return s.scalar(select(ClimberRow).where(ClimberRow.email == email.lower().strip()))


def set_ascents(s: Session, climber_id: int, problem_ids: list[int]) -> None:
    """Replace the climber's tick list. Comparisons on un-ticked problems are removed."""
    want = set(problem_ids)
    have = {a.problem_id for a in s.scalars(select(AscentRow).where(AscentRow.climber_id == climber_id))}
    for pid in have - want:
        s.query(AscentRow).filter_by(climber_id=climber_id, problem_id=pid).delete()
        s.query(ComparisonRow).filter(
            ComparisonRow.climber_id == climber_id,
            (ComparisonRow.problem_a == pid) | (ComparisonRow.problem_b == pid),
        ).delete(synchronize_session=False)
    for pid in want - have:
        s.add(AscentRow(climber_id=climber_id, problem_id=pid))
    s.flush()


def ticked_problems(s: Session, climber_id: int) -> list[Problem]:
    rows = s.scalars(
        select(ProblemRow).join(AscentRow, AscentRow.problem_id == ProblemRow.id)
        .where(AscentRow.climber_id == climber_id).order_by(ProblemRow.id)
    )
    return [to_problem(r) for r in rows]


# ---- comparisons ------------------------------------------------------------

def record_comparison(s: Session, climber_id: int, problem_a: int, problem_b: int,
                      verdict: Verdict, at: datetime | None = None) -> ComparisonRow:
    """Upsert the climber's opinion on a pair and append to history."""
    at = at or _utcnow()
    canon = Comparison(str(climber_id), str(problem_a), str(problem_b), verdict, at)
    a, b = int(canon.problem_a), int(canon.problem_b)
    ticked = {p.id for p in ticked_problems(s, climber_id)}
    if canon.problem_a not in ticked or canon.problem_b not in ticked:
        raise ValueError("climber has not ticked both problems")
    row = s.scalar(select(ComparisonRow).where(
        ComparisonRow.climber_id == climber_id, ComparisonRow.problem_a == a, ComparisonRow.problem_b == b))
    if row is None:
        row = ComparisonRow(climber_id=climber_id, problem_a=a, problem_b=b,
                            verdict=canon.verdict.value, created_at=at, updated_at=at)
        s.add(row)
    else:
        row.verdict = canon.verdict.value
        row.updated_at = at
    s.add(ComparisonHistoryRow(climber_id=climber_id, problem_a=a, problem_b=b,
                               verdict=canon.verdict.value, recorded_at=at))
    s.flush()
    return row


def all_comparisons(s: Session) -> list[Comparison]:
    rows = s.scalars(select(ComparisonRow).order_by(ComparisonRow.updated_at, ComparisonRow.id))
    return [to_comparison(r) for r in rows]


def climber_comparisons(s: Session, climber_id: int) -> list[ComparisonRow]:
    return list(s.scalars(select(ComparisonRow).where(ComparisonRow.climber_id == climber_id)
                          .order_by(ComparisonRow.updated_at.desc())))


def next_pairs(s: Session, climber_id: int, limit: int | None = None) -> list[tuple[Problem, Problem]]:
    ticked = ticked_problems(s, climber_id)
    by_id = {p.id: p for p in ticked}
    q = pair_queue(str(climber_id), ticked, all_comparisons(s))
    if limit is not None:
        q = q[:limit]
    return [(by_id[a], by_id[b]) for a, b in q]


def can_view_ranking(s: Session, climber_id: int) -> tuple[bool, int, int]:
    """(allowed, comparisons made, comparisons required)."""
    n_ticked = len(ticked_problems(s, climber_id))
    made = len(climber_comparisons(s, climber_id))
    need = ranking_gate_threshold(n_ticked)
    return made >= need, made, need


# ---- ratings ----------------------------------------------------------------

def compute(s: Session, algorithm: str) -> RankingResult:
    problems, comps = all_problems(s), all_comparisons(s)
    if algorithm == "bradley_terry":
        return fit_bradley_terry(problems, comps, BradleyTerryConfig())
    if algorithm == "elo":
        return replay_elo(problems, comps, EloConfig())
    if algorithm == "win_rate":
        return win_rate(problems, comps)
    raise ValueError(f"unknown algorithm {algorithm}")


def store_run(s: Session, result: RankingResult) -> RatingRunRow:
    run = RatingRunRow(algorithm=result.algorithm, n_comparisons=result.params.get("n_comparisons", 0),
                       params_json=json.dumps(result.params, default=str))
    s.add(run)
    s.flush()
    s.add_all(RatingSnapshotRow(
        run_id=run.id, problem_id=int(r.problem_id), rank=r.rank, rating=r.rating,
        uncertainty=r.uncertainty, n_comparisons=r.n_comparisons, n_climbers=r.n_climbers,
    ) for r in result.ratings)
    s.flush()
    return run


def recompute_all(s: Session) -> dict[str, RatingRunRow]:
    runs = {a: store_run(s, compute(s, a)) for a in ALGORITHMS}
    s.commit()
    return runs


def latest_run(s: Session, algorithm: str) -> RatingRunRow | None:
    return s.scalar(select(RatingRunRow).where(RatingRunRow.algorithm == algorithm)
                    .order_by(RatingRunRow.computed_at.desc(), RatingRunRow.id.desc()).limit(1))


def latest_ranking(s: Session, algorithm: str = "bradley_terry") -> list[tuple[RatingSnapshotRow, ProblemRow]]:
    run = latest_run(s, algorithm)
    if run is None:
        return []
    rows = s.execute(
        select(RatingSnapshotRow, ProblemRow).join(ProblemRow, ProblemRow.id == RatingSnapshotRow.problem_id)
        .where(RatingSnapshotRow.run_id == run.id).order_by(RatingSnapshotRow.rank)
    )
    return [(snap, prob) for snap, prob in rows]


def personal(s: Session, climber_id: int) -> RankingResult:
    return personal_ranking(str(climber_id), ticked_problems(s, climber_id), all_comparisons(s))

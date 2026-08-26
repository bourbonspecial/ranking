"""Repository layer: everything the API and CLI do to the database.

Converts between ORM rows and the plain engine types in ranking.models,
so the rating algorithms never touch SQLAlchemy.

Ascents have a status: "done" (climbed) or "tried" (attempted, not climbed).
A comparison's weight is derived here, at read time, from the statuses of
its two problems for that climber: 1.0 if both are done, else
`attempt_weight`. So if a climber later sends a problem they had only
tried, their old comparisons involving it are promoted automatically.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .bradley_terry import BradleyTerryConfig, fit_bradley_terry
from .db import (
    ASCENT_DONE, ASCENT_TRIED, AscentRow, ClimberRow, ComparisonHistoryRow, ComparisonRow,
    ProblemRow, RatingRunRow, RatingSnapshotRow,
)
from .elo import EloConfig, replay_elo
from .models import Comparison, Problem, Verdict
from .pairs import pair_kind, pair_queue, ranking_gate_threshold
from .personal import personal_ranking
from .result import RankingResult
from .winrate import win_rate

ALGORITHMS = ("bradley_terry", "elo", "win_rate")
DEFAULT_ATTEMPT_WEIGHT = 0.4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---- conversions -----------------------------------------------------------

def to_problem(row: ProblemRow) -> Problem:
    return Problem(id=str(row.id), name=row.name, seed_grade=row.seed_grade,
                   area=row.crag, country=row.country, ascent_count=row.ascent_count)


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


def admin_emails(s: Session) -> list[str]:
    """Active admins, for notifications that need a human to act on them."""
    return sorted(s.scalars(select(ClimberRow.email)
                            .where(ClimberRow.is_admin == True, ClimberRow.status == "active")))  # noqa: E712


def ascent_statuses(s: Session, climber_id: int) -> dict[int, str]:
    """{problem_id: "done" | "tried"} for one climber."""
    rows = s.scalars(select(AscentRow).where(AscentRow.climber_id == climber_id))
    return {a.problem_id: a.status for a in rows}


def set_ascents(s: Session, climber_id: int, done: list[int], tried: list[int] = ()) -> bool:
    """Replace the climber's list. A problem in both lists counts as done.

    Problems removed entirely take their comparisons with them; a change of
    status keeps comparisons (their weight is derived at read time).
    Returns True if anything changed (callers then owe the ranking a recompute).
    Raises ValueError for unknown problem ids.
    """
    want = {pid: ASCENT_TRIED for pid in tried}
    want.update({pid: ASCENT_DONE for pid in done})
    if want:
        known = set(s.scalars(select(ProblemRow.id).where(ProblemRow.id.in_(want))))
        if bad := set(want) - known:
            raise ValueError(f"unknown problem ids: {sorted(bad)}")
    have = {a.problem_id: a for a in s.scalars(select(AscentRow).where(AscentRow.climber_id == climber_id))}
    changed = False
    for pid in set(have) - set(want):
        s.delete(have[pid])
        s.query(ComparisonRow).filter(
            ComparisonRow.climber_id == climber_id,
            (ComparisonRow.problem_a == pid) | (ComparisonRow.problem_b == pid),
        ).delete(synchronize_session=False)
        changed = True
    for pid, status in want.items():
        if pid not in have:
            s.add(AscentRow(climber_id=climber_id, problem_id=pid, status=status))
            changed = True
        elif have[pid].status != status:
            have[pid].status = status
            changed = True
    s.flush()
    return changed


def ticked_problems(s: Session, climber_id: int, status: str | None = None) -> list[Problem]:
    q = (select(ProblemRow).join(AscentRow, AscentRow.problem_id == ProblemRow.id)
         .where(AscentRow.climber_id == climber_id).order_by(ProblemRow.id))
    if status is not None:
        q = q.where(AscentRow.status == status)
    return [to_problem(r) for r in s.scalars(q)]


# ---- comparisons ------------------------------------------------------------

def record_comparison(s: Session, climber_id: int, problem_a: int, problem_b: int,
                      verdict: Verdict, at: datetime | None = None) -> ComparisonRow:
    """Upsert the climber's opinion on a pair and append to history."""
    at = at or _utcnow()
    canon = Comparison(str(climber_id), str(problem_a), str(problem_b), verdict, at)
    a, b = int(canon.problem_a), int(canon.problem_b)
    statuses = ascent_statuses(s, climber_id)
    if a not in statuses or b not in statuses:
        raise ValueError("both problems must be on your list (climbed or tried)")
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


def _all_statuses(s: Session) -> dict[tuple[int, int], str]:
    return {(a.climber_id, a.problem_id): a.status for a in s.scalars(select(AscentRow))}


def comparison_kind(row: ComparisonRow, statuses: dict[tuple[int, int], str]) -> str:
    both_done = (statuses.get((row.climber_id, row.problem_a)) == ASCENT_DONE
                 and statuses.get((row.climber_id, row.problem_b)) == ASCENT_DONE)
    return "done" if both_done else "attempt"


def test_climber_ids(s: Session) -> set[int]:
    return set(s.scalars(select(ClimberRow.id).where(ClimberRow.is_test == True)))  # noqa: E712


def all_comparisons(s: Session, include_attempts: bool = True,
                    attempt_weight: float = DEFAULT_ATTEMPT_WEIGHT,
                    exclude_test: bool = True) -> list[Comparison]:
    """Live comparisons as engine objects, weighted by ascent status.

    Test climbers' comparisons are excluded by default so they never reach
    the global ranking; pass exclude_test=False for a climber's own view.
    """
    statuses = _all_statuses(s)
    skip = test_climber_ids(s) if exclude_test else set()
    out = []
    for r in s.scalars(select(ComparisonRow).order_by(ComparisonRow.updated_at, ComparisonRow.id)):
        if r.climber_id in skip:
            continue
        kind = comparison_kind(r, statuses)
        if kind == "attempt" and not include_attempts:
            continue
        out.append(Comparison(str(r.climber_id), str(r.problem_a), str(r.problem_b), Verdict(r.verdict),
                              r.updated_at, weight=1.0 if kind == "done" else attempt_weight))
    return out


def climber_comparisons(s: Session, climber_id: int) -> list[tuple[ComparisonRow, str]]:
    """(row, kind) for one climber, newest first."""
    statuses = _all_statuses(s)
    rows = s.scalars(select(ComparisonRow).where(ComparisonRow.climber_id == climber_id)
                     .order_by(ComparisonRow.updated_at.desc()))
    return [(r, comparison_kind(r, statuses)) for r in rows]


def next_pairs(s: Session, climber_id: int, limit: int | None = None) -> list[tuple[Problem, Problem, str]]:
    """Unanswered pairs for the compare flow: (a, b, "done" | "attempt"), done pairs first."""
    ticked = ticked_problems(s, climber_id)
    by_id = {p.id: p for p in ticked}
    tried = {str(pid) for pid, st in ascent_statuses(s, climber_id).items() if st == ASCENT_TRIED}
    q = pair_queue(str(climber_id), ticked, all_comparisons(s), tried=tried)
    if limit is not None:
        q = q[:limit]
    return [(by_id[a], by_id[b], pair_kind((a, b), tried)) for a, b in q]


def progress(s: Session, climber_id: int) -> dict:
    """Counts for the compare flow and the ranking gate.

    The gate only counts comparisons between two climbed problems: you unlock
    the list by comparing things you've done, not things you've tried.
    """
    statuses = ascent_statuses(s, climber_id)
    n_done = sum(1 for st in statuses.values() if st == ASCENT_DONE)
    n_tried = len(statuses) - n_done
    n_done_pairs = n_done * (n_done - 1) // 2
    n_all_pairs = len(statuses) * (len(statuses) - 1) // 2
    kinds = [k for _, k in climber_comparisons(s, climber_id)]
    done_answered = kinds.count("done")
    attempt_answered = kinds.count("attempt")
    required = ranking_gate_threshold(n_done)
    return {
        "n_done": n_done, "n_tried": n_tried,
        "n_done_pairs": n_done_pairs, "n_done_answered": done_answered,
        "n_attempt_pairs": n_all_pairs - n_done_pairs, "n_attempt_answered": attempt_answered,
        "ranking_required": required, "ranking_unlocked": done_answered >= required,
    }


def can_view_ranking(s: Session, climber_id: int) -> tuple[bool, int, int]:
    """(allowed, done comparisons made, comparisons required)."""
    p = progress(s, climber_id)
    return p["ranking_unlocked"], p["n_done_answered"], p["ranking_required"]


# ---- ratings ----------------------------------------------------------------

def compute(s: Session, algorithm: str, include_attempts: bool = False,
            attempt_weight: float = DEFAULT_ATTEMPT_WEIGHT) -> RankingResult:
    problems = all_problems(s)
    comps = all_comparisons(s, include_attempts=include_attempts, attempt_weight=attempt_weight)
    if algorithm == "bradley_terry":
        result = fit_bradley_terry(problems, comps, BradleyTerryConfig())
    elif algorithm == "elo":
        result = replay_elo(problems, comps, EloConfig())
    elif algorithm == "win_rate":
        result = win_rate(problems, comps)
    else:
        raise ValueError(f"unknown algorithm {algorithm}")
    result.params["include_attempts"] = include_attempts
    result.params["attempt_weight"] = attempt_weight if include_attempts else None
    return result


def store_run(s: Session, result: RankingResult) -> RatingRunRow:
    run = RatingRunRow(algorithm=result.algorithm, include_attempts=bool(result.params.get("include_attempts")),
                       n_comparisons=result.params.get("n_comparisons", 0),
                       params_json=json.dumps(result.params, default=str))
    s.add(run)
    s.flush()
    s.add_all(RatingSnapshotRow(
        run_id=run.id, problem_id=int(r.problem_id), rank=r.rank, rating=r.rating,
        uncertainty=r.uncertainty, n_comparisons=r.n_comparisons, n_climbers=r.n_climbers,
    ) for r in result.ratings)
    s.flush()
    return run


def recompute_all(s: Session, attempt_weight: float = DEFAULT_ATTEMPT_WEIGHT) -> dict[tuple[str, bool], RatingRunRow]:
    """Every algorithm, with and without attempt comparisons."""
    runs = {}
    for algo in ALGORITHMS:
        for include in (False, True):
            runs[(algo, include)] = store_run(s, compute(s, algo, include, attempt_weight))
    s.commit()
    return runs


def latest_run(s: Session, algorithm: str, include_attempts: bool = False) -> RatingRunRow | None:
    return s.scalar(select(RatingRunRow)
                    .where(RatingRunRow.algorithm == algorithm, RatingRunRow.include_attempts == include_attempts)
                    .order_by(RatingRunRow.computed_at.desc(), RatingRunRow.id.desc()).limit(1))


def latest_ranking(s: Session, algorithm: str = "bradley_terry",
                   include_attempts: bool = False) -> list[tuple[RatingSnapshotRow, ProblemRow]]:
    run = latest_run(s, algorithm, include_attempts)
    if run is None:
        return []
    rows = s.execute(
        select(RatingSnapshotRow, ProblemRow).join(ProblemRow, ProblemRow.id == RatingSnapshotRow.problem_id)
        .where(RatingSnapshotRow.run_id == run.id).order_by(RatingSnapshotRow.rank)
    )
    return [(snap, prob) for snap, prob in rows]


def personal(s: Session, climber_id: int, attempt_weight: float = DEFAULT_ATTEMPT_WEIGHT) -> RankingResult:
    return personal_ranking(str(climber_id), ticked_problems(s, climber_id),
                            all_comparisons(s, include_attempts=True, attempt_weight=attempt_weight,
                                            exclude_test=False))

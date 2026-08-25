from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from ..models import Verdict


class ProblemOut(BaseModel):
    id: int
    name: str
    crag: str
    country: str
    grade: str
    fa_name: str
    fa_date: str
    ascent_count: int


class ClimberOut(BaseModel):
    id: int
    name: str
    email: str
    status: str
    is_admin: bool
    n_ascents: int = 0
    n_comparisons: int = 0


class InviteRequestIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    note: str = Field(default="", max_length=2000)


class EmailIn(BaseModel):
    email: EmailStr


class InviteIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr


class AscentsIn(BaseModel):
    problem_ids: list[int]


class ComparisonIn(BaseModel):
    problem_a: int
    problem_b: int
    verdict: Verdict


class ComparisonOut(BaseModel):
    problem_a: ProblemOut
    problem_b: ProblemOut
    verdict: Verdict
    updated_at: str


class PairOut(BaseModel):
    problem_a: ProblemOut
    problem_b: ProblemOut


class ProgressOut(BaseModel):
    n_ticked: int
    n_possible_pairs: int
    n_answered: int
    ranking_unlocked: bool
    ranking_required: int


class RankingRowOut(BaseModel):
    rank: int
    problem: ProblemOut
    rating: float
    uncertainty: float | None
    n_comparisons: int
    n_climbers: int
    confidence: str
    seed_grade: str


class RankingOut(BaseModel):
    algorithm: str
    computed_at: str | None
    n_comparisons: int
    rows: list[RankingRowOut]


class PersonalRowOut(BaseModel):
    rank: int
    problem: ProblemOut
    rating: float
    global_rank: int | None
    n_comparisons: int

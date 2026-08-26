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
    request_note: str = ""
    public_profile: bool = False


class MeUpdateIn(BaseModel):
    public_profile: bool | None = None


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
    done: list[int] = Field(default_factory=list)   # climbed
    tried: list[int] = Field(default_factory=list)  # attempted, not climbed


class AscentsOut(BaseModel):
    done: list[int]
    tried: list[int]


class ComparisonIn(BaseModel):
    problem_a: int
    problem_b: int
    verdict: Verdict


class ComparisonOut(BaseModel):
    problem_a: ProblemOut
    problem_b: ProblemOut
    verdict: Verdict
    updated_at: str
    kind: str  # "done" | "attempt"


class PairOut(BaseModel):
    problem_a: ProblemOut
    problem_b: ProblemOut
    kind: str  # "done" (both climbed) | "attempt" (at least one only tried)
    status_a: str
    status_b: str


class ProgressOut(BaseModel):
    n_done: int
    n_tried: int
    n_done_pairs: int
    n_done_answered: int
    n_attempt_pairs: int
    n_attempt_answered: int
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


class RankingStatsOut(BaseModel):
    n_problems: int
    n_with_data: int          # problems with at least one comparison in this variant
    n_members: int            # active members
    n_voters: int             # members with at least one comparison
    n_comparisons_total: int  # all live comparisons regardless of variant


class RankingOut(BaseModel):
    algorithm: str
    include_attempts: bool
    attempt_weight: float | None
    computed_at: str | None
    n_comparisons: int
    stats: RankingStatsOut
    rows: list[RankingRowOut]


class PublicProfileOut(BaseModel):
    name: str
    n_done: int
    n_tried: int
    n_comparisons: int
    ranking: list["PersonalRowOut"]
    comparisons: list["ComparisonOut"]


class PersonalRowOut(BaseModel):
    rank: int
    problem: ProblemOut
    status: str  # "done" | "tried"
    rating: float
    global_rank: int | None
    n_comparisons: int

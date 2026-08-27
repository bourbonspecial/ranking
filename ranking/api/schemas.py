from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from ..models import Verdict
from ..scale import grade_to_rating

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _clean(v: str) -> str:
    """Single-line text: strip control characters (incl. CR/LF) and surrounding whitespace."""
    return _CONTROL.sub(" ", v).strip()


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
    is_test: bool = False


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


class ProblemSuggestionIn(BaseModel):
    """A member reporting a boulder that is missing from the list."""
    name: str = Field(max_length=120)
    crag: str = Field(default="", max_length=120)
    country: str = Field(default="", max_length=120)
    grade: str = Field(max_length=10)
    fa_name: str = Field(default="", max_length=120)
    fa_date: str = Field(default="", max_length=40)
    note: str = Field(default="", max_length=2000)

    @field_validator("name", "crag", "country", "fa_name", "fa_date", mode="after")
    @classmethod
    def _single_line(cls, v: str) -> str:
        return _clean(v)

    @field_validator("name", mode="after")
    @classmethod
    def _name_required(cls, v: str) -> str:
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("note", mode="after")
    @classmethod
    def _strip_note(cls, v: str) -> str:
        return v.strip()

    @field_validator("grade", mode="after")
    @classmethod
    def _known_grade(cls, v: str) -> str:
        grade_to_rating(v.strip())  # raises ValueError listing the known grades
        return v.strip().upper()


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
    seed_rating: float   # where the problem started (from its grade)
    delta: float         # rating - seed_rating; > 0 has moved up, < 0 down


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


class AdminProfileOut(PublicProfileOut):
    """Everything on a public profile plus account details; admins only, regardless of
    whether the member has made their profile public."""
    id: int
    email: str
    status: str
    is_admin: bool
    is_test: bool
    public_profile: bool
    updated_at: str | None  # most recent answer, if any


class PersonalRowOut(BaseModel):
    rank: int
    problem: ProblemOut
    status: str  # "done" | "tried"
    rating: float
    global_rank: int | None
    n_comparisons: int

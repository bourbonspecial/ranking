"""SQLite persistence.

Two database files live in data/:
  seed.sqlite   - committed. Problems imported from data/hardest_problems.csv,
                  no climbers or comparisons. Rebuilt with `ranking db build-seed`.
  local.sqlite  - gitignored. Copied from seed on first `ranking db init`;
                  this is what you run against locally.

Schema is created with metadata.create_all for now; Alembic can be added
once the schema settles.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
from pathlib import Path

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
    create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
SEED_DB = DATA_DIR / "seed.sqlite"
LOCAL_DB = DATA_DIR / "local.sqlite"
PROBLEMS_CSV = DATA_DIR / "hardest_problems_8c.csv"


class Base(DeclarativeBase):
    pass


class ProblemRow(Base):
    __tablename__ = "problems"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    seed_grade: Mapped[str] = mapped_column(String, nullable=False)
    current_grade: Mapped[str] = mapped_column(String, nullable=False)
    crag: Mapped[str] = mapped_column(String, default="")
    country: Mapped[str] = mapped_column(String, default="")
    fa_name: Mapped[str] = mapped_column(String, default="")
    fa_date: Mapped[str] = mapped_column(String, default="")
    ascent_count: Mapped[int] = mapped_column(Integer, default=0)
    ch_url: Mapped[str] = mapped_column(String, default="")
    ch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # climbing-history.org climb id, for sync
    __table_args__ = (UniqueConstraint("name", "crag", name="uq_problem_name_crag"),)

    @property
    def public_id(self) -> str:
        return str(self.id)


class ClimberRow(Base):
    __tablename__ = "climbers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String, default="requested")  # requested | invited | active | deactivated
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    public_profile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")  # comparisons excluded from the global ranking
    # Optional demographics, self-reported, for filtered lists later (issue #1). Never public.
    gender: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")  # see schemas.GENDERS
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    arm_span_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    ascents: Mapped[list["AscentRow"]] = relationship(back_populates="climber", cascade="all, delete-orphan")


ASCENT_DONE = "done"
ASCENT_TRIED = "tried"


class AscentRow(Base):
    """A problem on a climber's list: either climbed ("done") or attempted ("tried")."""
    __tablename__ = "ascents"
    climber_id: Mapped[int] = mapped_column(ForeignKey("climbers.id"), primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default=ASCENT_DONE, server_default=ASCENT_DONE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    climber: Mapped[ClimberRow] = relationship(back_populates="ascents")


class ComparisonRow(Base):
    """Live opinion: one row per (climber, pair). Edits overwrite in place."""
    __tablename__ = "comparisons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    climber_id: Mapped[int] = mapped_column(ForeignKey("climbers.id"), nullable=False)
    problem_a: Mapped[int] = mapped_column(ForeignKey("problems.id"), nullable=False)  # a < b
    problem_b: Mapped[int] = mapped_column(ForeignKey("problems.id"), nullable=False)
    verdict: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    __table_args__ = (UniqueConstraint("climber_id", "problem_a", "problem_b", name="uq_comparison"),)


class ComparisonHistoryRow(Base):
    """Audit trail of every answer ever given. Never used for ranking."""
    __tablename__ = "comparison_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    climber_id: Mapped[int] = mapped_column(ForeignKey("climbers.id"), nullable=False)
    problem_a: Mapped[int] = mapped_column(ForeignKey("problems.id"), nullable=False)
    problem_b: Mapped[int] = mapped_column(ForeignKey("problems.id"), nullable=False)
    verdict: Mapped[str] = mapped_column(String, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class MagicLinkRow(Base):
    __tablename__ = "magic_links"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    climber_id: Mapped[int] = mapped_column(ForeignKey("climbers.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SessionRow(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    climber_id: Mapped[int] = mapped_column(ForeignKey("climbers.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class RatingRunRow(Base):
    __tablename__ = "rating_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    algorithm: Mapped[str] = mapped_column(String, nullable=False)
    include_attempts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    n_comparisons: Mapped[int] = mapped_column(Integer, default=0)
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    snapshots: Mapped[list["RatingSnapshotRow"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RatingSnapshotRow(Base):
    __tablename__ = "rating_snapshots"
    run_id: Mapped[int] = mapped_column(ForeignKey("rating_runs.id"), primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_comparisons: Mapped[int] = mapped_column(Integer, default=0)
    n_climbers: Mapped[int] = mapped_column(Integer, default=0)
    run: Mapped[RatingRunRow] = relationship(back_populates="snapshots")


def make_engine(path: Path | str):
    engine = create_engine(f"sqlite:///{path}", future=True)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def make_session_factory(path: Path | str) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(path), expire_on_commit=False)


# Columns added after a table first shipped. create_all() only creates missing
# tables, so these are applied with ALTER TABLE when absent. (table, column, DDL)
_ADDED_COLUMNS = [
    ("ascents", "status", "VARCHAR NOT NULL DEFAULT 'done'"),
    ("rating_runs", "include_attempts", "BOOLEAN NOT NULL DEFAULT 0"),
    ("climbers", "public_profile", "BOOLEAN NOT NULL DEFAULT 0"),
    ("climbers", "is_test", "BOOLEAN NOT NULL DEFAULT 0"),
    ("climbers", "gender", "VARCHAR NOT NULL DEFAULT ''"),
    ("climbers", "height_cm", "INTEGER"),
    ("climbers", "arm_span_cm", "INTEGER"),
    ("problems", "ch_id", "INTEGER"),
]


def create_schema(path: Path | str) -> None:
    engine = make_engine(path)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for table, column, ddl in _ADDED_COLUMNS:
            cols = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if column not in cols:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_local_db(seed: Path = SEED_DB, local: Path = LOCAL_DB, force: bool = False) -> Path:
    """Copy the committed seed DB to the gitignored local DB if it doesn't exist."""
    if not seed.exists():
        raise FileNotFoundError(f"seed database missing: {seed} (run `ranking db build-seed`)")
    if not local.exists() or force:
        shutil.copyfile(seed, local)
    create_schema(local)  # idempotent: adds any tables introduced since the copy was made
    return local

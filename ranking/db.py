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
PROBLEMS_CSV = DATA_DIR / "hardest_problems.csv"


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
    request_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    ascents: Mapped[list["AscentRow"]] = relationship(back_populates="climber", cascade="all, delete-orphan")


class AscentRow(Base):
    __tablename__ = "ascents"
    climber_id: Mapped[int] = mapped_column(ForeignKey("climbers.id"), primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), primary_key=True)
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


def create_schema(path: Path | str) -> None:
    Base.metadata.create_all(make_engine(path))


def init_local_db(seed: Path = SEED_DB, local: Path = LOCAL_DB, force: bool = False) -> Path:
    """Copy the committed seed DB to the gitignored local DB if it doesn't exist."""
    if not seed.exists():
        raise FileNotFoundError(f"seed database missing: {seed} (run `ranking db build-seed`)")
    if local.exists() and not force:
        return local
    shutil.copyfile(seed, local)
    return local

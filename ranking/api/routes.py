from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import repo
from ..confidence import confidence_tier
from ..scale import grade_to_rating
from ..db import ASCENT_DONE, ASCENT_TRIED, AscentRow, ClimberRow, ComparisonRow, ProblemRow
from ..models import Verdict
from . import auth
from .deps import client_ip, get_db, get_mailer, get_recomputer, get_settings, rate_limited
from .schemas import (
    AdminProfileOut, AscentsIn, AscentsOut, ClimberOut, ComparisonIn, ComparisonOut, DetailsOut, EmailIn, InviteIn,
    InviteRequestIn,
    MeUpdateIn, PairOut, PersonalRowOut, ProblemOut, ProblemSuggestionIn, ProgressOut, PublicProfileOut,
    RankingOut, RankingRowOut, RankingStatsOut,
)

log = logging.getLogger(__name__)

public = APIRouter(prefix="/api")
member = APIRouter(prefix="/api", dependencies=[Depends(auth.current_climber)])
admin = APIRouter(prefix="/api/admin", dependencies=[Depends(auth.current_admin)])


def problem_out(p: ProblemRow) -> ProblemOut:
    return ProblemOut(id=p.id, name=p.name, crag=p.crag, country=p.country, grade=p.current_grade,
                      fa_name=p.fa_name, fa_date=p.fa_date, ascent_count=p.ascent_count)


def climber_out(s: Session, c: ClimberRow) -> ClimberOut:
    n_asc = s.scalar(select(func.count()).select_from(AscentRow).where(AscentRow.climber_id == c.id)) or 0
    n_cmp = s.scalar(select(func.count()).select_from(ComparisonRow).where(ComparisonRow.climber_id == c.id)) or 0
    d = details_out(c)
    return ClimberOut(id=c.id, name=c.name, email=c.email, status=c.status, is_admin=c.is_admin,
                      n_ascents=n_asc, n_comparisons=n_cmp, request_note=c.request_note or "",
                      public_profile=c.public_profile, is_test=c.is_test,
                      **d.model_dump(), details_complete=d.complete)


def details_out(c: ClimberRow) -> DetailsOut:
    return DetailsOut(gender=c.gender or "", height_cm=c.height_cm, arm_span_cm=c.arm_span_cm)


def _personal_rows(s: Session, climber: ClimberRow, attempt_weight: float) -> list[PersonalRowOut]:
    mine = repo.personal(s, climber.id, attempt_weight)
    st = repo.ascent_statuses(s, climber.id)
    global_rank = {prob.id: snap.rank for snap, prob in repo.latest_ranking(s, "bradley_terry")}
    return [
        PersonalRowOut(rank=r.rank, problem=problem_out(s.get(ProblemRow, int(r.problem_id))),
                       status=st.get(int(r.problem_id), ASCENT_DONE),
                       rating=round(r.rating, 1), global_rank=global_rank.get(int(r.problem_id)),
                       n_comparisons=r.n_comparisons)
        for r in mine.ratings
    ]


def _comparison_rows(s: Session, climber_id: int) -> list[ComparisonOut]:
    return [
        ComparisonOut(problem_a=problem_out(s.get(ProblemRow, r.problem_a)),
                      problem_b=problem_out(s.get(ProblemRow, r.problem_b)),
                      verdict=Verdict(r.verdict), updated_at=r.updated_at.isoformat(), kind=kind)
        for r, kind in repo.climber_comparisons(s, climber_id)
    ]


# ---- public -----------------------------------------------------------------

@public.post("/invite-requests", status_code=202)
def request_invite(body: InviteRequestIn, request: Request, s: Session = Depends(get_db),
                   limit=Depends(rate_limited("invite"))):
    limit((f"ip:{client_ip(request)}", f"email:{body.email.lower()}"))
    existing = repo.get_climber_by_email(s, body.email)
    if existing is None:
        repo.add_climber(s, body.name, body.email, status="requested", request_note=body.note)
    elif existing.status == "requested":
        existing.name, existing.request_note = body.name, body.note
    return {"ok": True}


@public.post("/auth/request-link", status_code=202)
def request_link(body: EmailIn, request: Request, s: Session = Depends(get_db), settings=Depends(get_settings),
                 mailer=Depends(get_mailer), limit=Depends(rate_limited("magic_link"))):
    limit((f"ip:{client_ip(request)}",))
    # The per-address cap only stops us mail-bombing someone: it is unauthenticated, so it
    # must not 429 (that would let anyone lock a member out, and would confirm membership).
    if limit.consume((f"email:{body.email.lower()}",)) is not None:
        return {"ok": True}
    climber = repo.get_climber_by_email(s, body.email)
    if climber is None and body.email.lower() in settings.admin_emails:
        climber = repo.add_climber(s, body.email.split("@")[0], body.email, status="active", is_admin=True)
    if climber is not None and climber.status in ("invited", "active"):
        url = auth.create_magic_link(s, settings, climber)
        mailer.magic_link(climber.email, climber.name, url, invite=False)
    # Always 202: don't reveal who is a member.
    return {"ok": True}


@public.get("/auth/callback")
def auth_callback(token: str, s: Session = Depends(get_db), settings=Depends(get_settings),
                  mailer=Depends(get_mailer)):
    climber, activated = auth.consume_magic_link(s, token)
    session_token = auth.create_session(s, settings, climber)
    if activated:
        mailer.welcome(climber.email, climber.name, settings.base_url)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(auth.COOKIE, session_token, httponly=True, samesite="lax", secure=settings.cookie_secure,
                    max_age=settings.session_ttl_days * 86400)
    return resp


@public.post("/auth/logout")
def logout(request: Request, response: Response, s: Session = Depends(get_db)):
    auth.destroy_session(s, request.cookies.get(auth.COOKIE))
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@public.get("/me")
def me(s: Session = Depends(get_db), climber=Depends(auth.optional_climber)):
    return None if climber is None else climber_out(s, climber)


def _profile_fields(s: Session, c: ClimberRow, attempt_weight: float) -> dict:
    p = repo.progress(s, c.id)
    return dict(name=c.name, n_done=p["n_done"], n_tried=p["n_tried"],
                n_comparisons=p["n_done_answered"] + p["n_attempt_answered"],
                ranking=_personal_rows(s, c, attempt_weight), comparisons=_comparison_rows(s, c.id))


@public.get("/climbers/{climber_id}/public", response_model=PublicProfileOut)
def public_profile(climber_id: int, s: Session = Depends(get_db), settings=Depends(get_settings)):
    """A member's personal ordering and answers, if they have chosen to make them public."""
    c = s.get(ClimberRow, climber_id)
    if c is None or c.status != "active" or not c.public_profile:
        raise HTTPException(404, "This profile is private or does not exist.")
    return PublicProfileOut(**_profile_fields(s, c, settings.attempt_weight))


# ---- member -----------------------------------------------------------------

@member.get("/problems", response_model=list[ProblemOut])
def list_problems(s: Session = Depends(get_db)):
    return [problem_out(p) for p in s.scalars(select(ProblemRow).order_by(ProblemRow.id))]


@member.post("/problem-suggestions", status_code=202)
def suggest_problem(body: ProblemSuggestionIn, s: Session = Depends(get_db),
                    climber=Depends(auth.current_climber), settings=Depends(get_settings),
                    mailer=Depends(get_mailer), limit=Depends(rate_limited("suggestion"))):
    """A member reports a boulder missing from the list; admins get an email and decide."""
    existing = s.scalar(select(ProblemRow).where(func.lower(ProblemRow.name) == body.name.lower(),
                                                 func.lower(ProblemRow.crag) == body.crag.lower()))
    if existing is not None:
        raise HTTPException(409, f"{existing.name} ({existing.crag}) is already on the list.")
    limit((f"climber:{climber.id}",))
    recipients = sorted({*repo.admin_emails(s), *settings.admin_emails})
    try:
        mailer.problem_suggestion(recipients, climber.name, climber.email, {
            "name": body.name, "crag": body.crag, "country": body.country, "grade": body.grade,
            "fa": body.fa_name, "date": body.fa_date, "note": body.note,
        }, settings.base_url)
    except OSError as e:  # smtplib errors are OSErrors; nothing was delivered
        log.exception("could not email admins about a suggested boulder")
        limit.refund((f"climber:{climber.id}",))
        raise HTTPException(503, "Couldn't reach the mail server. Please try again in a minute.") from e
    return {"ok": True}


@member.get("/me/ascents", response_model=AscentsOut)
def get_ascents(s: Session = Depends(get_db), climber=Depends(auth.current_climber)):
    st = repo.ascent_statuses(s, climber.id)
    return AscentsOut(done=sorted(p for p, v in st.items() if v == ASCENT_DONE),
                      tried=sorted(p for p, v in st.items() if v == ASCENT_TRIED))


@member.put("/me/ascents", response_model=ProgressOut)
def put_ascents(body: AscentsIn, s: Session = Depends(get_db), climber=Depends(auth.current_climber),
                recomputer=Depends(get_recomputer)):
    try:
        changed = repo.set_ascents(s, climber.id, body.done, body.tried)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if changed:
        # Status changes alter attempt weights, and removals delete comparisons.
        # Commit before recomputing so the background session sees those changes.
        s.commit()
        recomputer.schedule()
    return progress(s, climber)


@member.get("/me/progress", response_model=ProgressOut)
def progress(s: Session = Depends(get_db), climber=Depends(auth.current_climber)):
    return ProgressOut(**repo.progress(s, climber.id))


@member.get("/me/pairs", response_model=list[PairOut])
def pairs(limit: int = 20, s: Session = Depends(get_db), climber=Depends(auth.current_climber)):
    st = repo.ascent_statuses(s, climber.id)
    out = []
    for a, b, kind in repo.next_pairs(s, climber.id, limit=limit):
        out.append(PairOut(problem_a=problem_out(s.get(ProblemRow, int(a.id))),
                           problem_b=problem_out(s.get(ProblemRow, int(b.id))),
                           kind=kind, status_a=st[int(a.id)], status_b=st[int(b.id)]))
    return out


@member.post("/me/comparisons", response_model=ProgressOut)
def post_comparison(body: ComparisonIn, s: Session = Depends(get_db), climber=Depends(auth.current_climber),
                    recomputer=Depends(get_recomputer)):
    if body.problem_a == body.problem_b:
        raise HTTPException(400, "problems must differ")
    try:
        repo.record_comparison(s, climber.id, body.problem_a, body.problem_b, body.verdict)
    except ValueError as e:
        raise HTTPException(400, str(e))
    s.commit()
    recomputer.schedule()
    return progress(s, climber)


@member.get("/me/comparisons", response_model=list[ComparisonOut])
def my_comparisons(s: Session = Depends(get_db), climber=Depends(auth.current_climber)):
    return _comparison_rows(s, climber.id)


@member.patch("/me", response_model=ClimberOut)
def update_me(body: MeUpdateIn, s: Session = Depends(get_db), climber=Depends(auth.current_climber)):
    if body.public_profile is not None:
        climber.public_profile = body.public_profile
    # Demographics are nullable, so distinguish "not sent" from "sent null" (= clear).
    for f in ("gender", "height_cm", "arm_span_cm"):
        if f in body.model_fields_set:
            setattr(climber, f, getattr(body, f) if getattr(body, f) is not None or f != "gender" else "")
    s.flush()
    return climber_out(s, climber)


@member.get("/ranking", response_model=RankingOut)
def ranking(algo: str = "bradley_terry", include_attempts: bool = False,
            s: Session = Depends(get_db), climber=Depends(auth.current_climber), settings=Depends(get_settings)):
    if algo not in repo.ALGORITHMS:
        raise HTTPException(400, f"algo must be one of {repo.ALGORITHMS}")
    ok, made, need = repo.can_view_ranking(s, climber.id)
    if not ok and not climber.is_admin:
        raise HTTPException(403, f"Compare {need - made} more pair(s) of problems you've climbed to unlock the ranking.")
    run = repo.latest_run(s, algo, include_attempts)
    rows = [
        RankingRowOut(rank=snap.rank, problem=problem_out(prob), rating=round(snap.rating, 1),
                      uncertainty=None if snap.uncertainty is None else round(snap.uncertainty, 1),
                      n_comparisons=snap.n_comparisons, n_climbers=snap.n_climbers,
                      confidence=confidence_tier(snap.n_comparisons, snap.n_climbers), seed_grade=prob.seed_grade,
                      seed_rating=grade_to_rating(prob.seed_grade),
                      delta=round(snap.rating - grade_to_rating(prob.seed_grade), 1))
        for snap, prob in repo.latest_ranking(s, algo, include_attempts)
    ]
    real = ClimberRow.is_test == False  # noqa: E712 - test users don't count towards the global picture
    n_members = s.scalar(select(func.count()).select_from(ClimberRow)
                         .where(ClimberRow.status == "active", real)) or 0
    n_voters = s.scalar(select(func.count(func.distinct(ComparisonRow.climber_id)))
                        .join(ClimberRow, ClimberRow.id == ComparisonRow.climber_id).where(real)) or 0
    n_total = s.scalar(select(func.count()).select_from(ComparisonRow)
                       .join(ClimberRow, ClimberRow.id == ComparisonRow.climber_id).where(real)) or 0
    stats = RankingStatsOut(n_problems=len(rows), n_with_data=sum(1 for r in rows if r.n_comparisons > 0),
                            n_members=n_members, n_voters=n_voters, n_comparisons_total=n_total)
    return RankingOut(algorithm=algo, include_attempts=include_attempts,
                      attempt_weight=settings.attempt_weight if include_attempts else None,
                      computed_at=run.computed_at.isoformat() if run else None,
                      n_comparisons=run.n_comparisons if run else 0, stats=stats, rows=rows)


@member.get("/me/ranking", response_model=list[PersonalRowOut])
def my_ranking(s: Session = Depends(get_db), climber=Depends(auth.current_climber), settings=Depends(get_settings)):
    return _personal_rows(s, climber, settings.attempt_weight)


# ---- admin ------------------------------------------------------------------

@admin.get("/climbers", response_model=list[ClimberOut])
def climbers(status: str | None = None, s: Session = Depends(get_db)):
    q = select(ClimberRow).order_by(ClimberRow.created_at.desc())
    if status:
        q = q.where(ClimberRow.status == status)
    return [climber_out(s, c) for c in s.scalars(q)]


def _invite(s: Session, settings, mailer, climber: ClimberRow, is_test: bool | None = None) -> None:
    if climber.status in ("requested", "deactivated"):
        climber.status = "invited"
    if is_test is not None:
        climber.is_test = is_test  # no recompute needed: they have no comparisons yet
    url = auth.create_magic_link(s, settings, climber)
    mailer.magic_link(climber.email, climber.name, url, invite=True)


@admin.post("/climbers/{climber_id}/invite", response_model=ClimberOut)
def invite_existing(climber_id: int, test: bool | None = None, s: Session = Depends(get_db),
                    settings=Depends(get_settings), mailer=Depends(get_mailer)):
    """Send (or resend) an invitation. `test=true` marks the account as a test user first."""
    c = s.get(ClimberRow, climber_id)
    if c is None:
        raise HTTPException(404)
    _invite(s, settings, mailer, c, is_test=test)
    return climber_out(s, c)


@admin.post("/invite", response_model=ClimberOut)
def invite_new(body: InviteIn, s: Session = Depends(get_db), settings=Depends(get_settings),
               mailer=Depends(get_mailer)):
    c = repo.get_climber_by_email(s, body.email)
    if c is None:
        c = repo.add_climber(s, body.name, body.email, status="invited")
    _invite(s, settings, mailer, c, is_test=body.is_test)
    return climber_out(s, c)


@admin.post("/climbers/{climber_id}/reject", response_model=ClimberOut)
def reject(climber_id: int, s: Session = Depends(get_db)):
    c = s.get(ClimberRow, climber_id)
    if c is None:
        raise HTTPException(404)
    c.status = "deactivated"
    return climber_out(s, c)


@admin.post("/climbers/{climber_id}/admin", response_model=ClimberOut)
def set_admin(climber_id: int, value: bool = True, s: Session = Depends(get_db)):
    c = s.get(ClimberRow, climber_id)
    if c is None:
        raise HTTPException(404)
    c.is_admin = value
    return climber_out(s, c)


@admin.post("/climbers/{climber_id}/test", response_model=ClimberOut)
def set_test(climber_id: int, value: bool = True, s: Session = Depends(get_db), recomputer=Depends(get_recomputer)):
    """Mark a climber as a test user: they can use everything, but their comparisons
    never count towards the global ranking. Toggling triggers a recompute."""
    c = s.get(ClimberRow, climber_id)
    if c is None:
        raise HTTPException(404)
    if c.is_test != value:
        c.is_test = value
        s.commit()
        recomputer.schedule()
    return climber_out(s, c)


@admin.get("/climbers/{climber_id}/profile", response_model=AdminProfileOut)
def admin_profile(climber_id: int, s: Session = Depends(get_db), settings=Depends(get_settings)):
    """Read-only view of a member's ascents, answers and personal ordering, for spotting
    abuse. Available for every account regardless of status or the public-profile flag."""
    c = s.get(ClimberRow, climber_id)
    if c is None:
        raise HTTPException(404)
    fields = _profile_fields(s, c, settings.attempt_weight)
    latest = max((r.updated_at for r in fields["comparisons"]), default=None)
    return AdminProfileOut(**fields, id=c.id, email=c.email, status=c.status, is_admin=c.is_admin,
                           is_test=c.is_test, public_profile=c.public_profile, updated_at=latest,
                           details=details_out(c))


@admin.post("/recompute")
def recompute(recomputer=Depends(get_recomputer)):
    recomputer.run_now()
    return {"ok": True}

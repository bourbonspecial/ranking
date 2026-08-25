from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import repo
from ..confidence import confidence_tier
from ..db import ASCENT_DONE, ASCENT_TRIED, AscentRow, ClimberRow, ComparisonRow, ProblemRow
from ..models import Verdict
from . import auth
from .deps import get_db, get_mailer, get_recomputer, get_settings
from .schemas import (
    AscentsIn, AscentsOut, ClimberOut, ComparisonIn, ComparisonOut, EmailIn, InviteIn, InviteRequestIn,
    PairOut, PersonalRowOut, ProblemOut, ProgressOut, RankingOut, RankingRowOut,
)

public = APIRouter(prefix="/api")
member = APIRouter(prefix="/api", dependencies=[Depends(auth.current_climber)])
admin = APIRouter(prefix="/api/admin", dependencies=[Depends(auth.current_admin)])


def problem_out(p: ProblemRow) -> ProblemOut:
    return ProblemOut(id=p.id, name=p.name, crag=p.crag, country=p.country, grade=p.current_grade,
                      fa_name=p.fa_name, fa_date=p.fa_date, ascent_count=p.ascent_count)


def climber_out(s: Session, c: ClimberRow) -> ClimberOut:
    n_asc = s.scalar(select(func.count()).select_from(AscentRow).where(AscentRow.climber_id == c.id)) or 0
    n_cmp = s.scalar(select(func.count()).select_from(ComparisonRow).where(ComparisonRow.climber_id == c.id)) or 0
    return ClimberOut(id=c.id, name=c.name, email=c.email, status=c.status, is_admin=c.is_admin,
                      n_ascents=n_asc, n_comparisons=n_cmp, request_note=c.request_note or "")


# ---- public -----------------------------------------------------------------

@public.post("/invite-requests", status_code=202)
def request_invite(body: InviteRequestIn, s: Session = Depends(get_db)):
    existing = repo.get_climber_by_email(s, body.email)
    if existing is None:
        repo.add_climber(s, body.name, body.email, status="requested", request_note=body.note)
    elif existing.status == "requested":
        existing.name, existing.request_note = body.name, body.note
    return {"ok": True}


@public.post("/auth/request-link", status_code=202)
def request_link(body: EmailIn, s: Session = Depends(get_db), settings=Depends(get_settings),
                 mailer=Depends(get_mailer)):
    climber = repo.get_climber_by_email(s, body.email)
    if climber is None and body.email.lower() in settings.admin_emails:
        climber = repo.add_climber(s, body.email.split("@")[0], body.email, status="active", is_admin=True)
    if climber is not None and climber.status in ("invited", "active"):
        url = auth.create_magic_link(s, settings, climber)
        mailer.magic_link(climber.email, climber.name, url, invite=False)
    # Always 202: don't reveal who is a member.
    return {"ok": True}


@public.get("/auth/callback")
def auth_callback(token: str, s: Session = Depends(get_db), settings=Depends(get_settings)):
    climber = auth.consume_magic_link(s, token)
    session_token = auth.create_session(s, settings, climber)
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


# ---- member -----------------------------------------------------------------

@member.get("/problems", response_model=list[ProblemOut])
def list_problems(s: Session = Depends(get_db)):
    return [problem_out(p) for p in s.scalars(select(ProblemRow).order_by(ProblemRow.id))]


@member.get("/me/ascents", response_model=AscentsOut)
def get_ascents(s: Session = Depends(get_db), climber=Depends(auth.current_climber)):
    st = repo.ascent_statuses(s, climber.id)
    return AscentsOut(done=sorted(p for p, v in st.items() if v == ASCENT_DONE),
                      tried=sorted(p for p, v in st.items() if v == ASCENT_TRIED))


@member.put("/me/ascents", response_model=ProgressOut)
def put_ascents(body: AscentsIn, s: Session = Depends(get_db), climber=Depends(auth.current_climber)):
    known = {p.id for p in s.scalars(select(ProblemRow))}
    bad = (set(body.done) | set(body.tried)) - known
    if bad:
        raise HTTPException(400, f"unknown problem ids: {sorted(bad)}")
    repo.set_ascents(s, climber.id, body.done, body.tried)
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
    return [
        ComparisonOut(problem_a=problem_out(s.get(ProblemRow, r.problem_a)),
                      problem_b=problem_out(s.get(ProblemRow, r.problem_b)),
                      verdict=Verdict(r.verdict), updated_at=r.updated_at.isoformat(), kind=kind)
        for r, kind in repo.climber_comparisons(s, climber.id)
    ]


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
                      confidence=confidence_tier(snap.n_comparisons, snap.n_climbers), seed_grade=prob.seed_grade)
        for snap, prob in repo.latest_ranking(s, algo, include_attempts)
    ]
    return RankingOut(algorithm=algo, include_attempts=include_attempts,
                      attempt_weight=settings.attempt_weight if include_attempts else None,
                      computed_at=run.computed_at.isoformat() if run else None,
                      n_comparisons=run.n_comparisons if run else 0, rows=rows)


@member.get("/me/ranking", response_model=list[PersonalRowOut])
def my_ranking(s: Session = Depends(get_db), climber=Depends(auth.current_climber), settings=Depends(get_settings)):
    mine = repo.personal(s, climber.id, settings.attempt_weight)
    st = repo.ascent_statuses(s, climber.id)
    global_rank = {prob.id: snap.rank for snap, prob in repo.latest_ranking(s, "bradley_terry")}
    return [
        PersonalRowOut(rank=r.rank, problem=problem_out(s.get(ProblemRow, int(r.problem_id))),
                       status=st.get(int(r.problem_id), ASCENT_DONE),
                       rating=round(r.rating, 1), global_rank=global_rank.get(int(r.problem_id)),
                       n_comparisons=r.n_comparisons)
        for r in mine.ratings
    ]


# ---- admin ------------------------------------------------------------------

@admin.get("/climbers", response_model=list[ClimberOut])
def climbers(status: str | None = None, s: Session = Depends(get_db)):
    q = select(ClimberRow).order_by(ClimberRow.created_at.desc())
    if status:
        q = q.where(ClimberRow.status == status)
    return [climber_out(s, c) for c in s.scalars(q)]


def _invite(s: Session, settings, mailer, climber: ClimberRow) -> None:
    if climber.status in ("requested", "deactivated"):
        climber.status = "invited"
    url = auth.create_magic_link(s, settings, climber)
    mailer.magic_link(climber.email, climber.name, url, invite=True)


@admin.post("/climbers/{climber_id}/invite", response_model=ClimberOut)
def invite_existing(climber_id: int, s: Session = Depends(get_db), settings=Depends(get_settings),
                    mailer=Depends(get_mailer)):
    c = s.get(ClimberRow, climber_id)
    if c is None:
        raise HTTPException(404)
    _invite(s, settings, mailer, c)
    return climber_out(s, c)


@admin.post("/invite", response_model=ClimberOut)
def invite_new(body: InviteIn, s: Session = Depends(get_db), settings=Depends(get_settings),
               mailer=Depends(get_mailer)):
    c = repo.get_climber_by_email(s, body.email)
    if c is None:
        c = repo.add_climber(s, body.name, body.email, status="invited")
    _invite(s, settings, mailer, c)
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


@admin.post("/recompute")
def recompute(recomputer=Depends(get_recomputer)):
    recomputer.run_now()
    return {"ok": True}

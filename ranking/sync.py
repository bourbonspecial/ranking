"""Import a member's ascents from climbing-history.org (issue #4).

climbing-history.org exposes a small read-only API for The List
(`/api/v1/the-list/...`, api-key protected). We never write to it. The flow is:

1. the member searches for their climbing-history record by name;
2. we fetch that climber's boulders and match each against our `problems` table;
3. the member reviews the matches in the UI and saves through the normal
   `PUT /api/me/ascents`, so recomputes and the "removing a problem deletes its
   comparisons" rule keep working unchanged.

Matching prefers the stored climbing-history id (`ProblemRow.ch_id`, backfilled
by an admin from the `/boulders` listing), then normalised name + crag, then a
normalised name that is unique on our side. Anything at 8C or harder that we
can't match is reported so the member can suggest it.
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import ASCENT_DONE, ASCENT_TRIED, ProblemRow
from .scale import GRADE_SEED


class SyncError(Exception):
    """climbing-history.org was unreachable or answered with an error."""


# climbing-history.org sits behind Cloudflare, whose Browser Integrity Check rejects Python's
# default "Python-urllib/3.x" User-Agent with a 403 (error 1010) before the request reaches the
# app - identical for good and bad keys, so it looks like an auth problem. Identify ourselves.
USER_AGENT = "TheList/1.0 (+https://the-list.climbing-history.org)"


class ClimbingHistoryClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 15.0):
        self.base_url, self.api_key, self.timeout = base_url.rstrip("/"), api_key, timeout

    def _get(self, path: str, **params) -> list | dict:
        q = urllib.parse.urlencode({**params, "api_key": self.api_key})
        req = urllib.request.Request(f"{self.base_url}{path}?{q}",
                                     headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise SyncError(f"climbing-history.org answered {e.code}") from e
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise SyncError("climbing-history.org could not be reached") from e

    def search_climbers(self, q: str) -> list[dict]:
        return self._get("/climbers", q=q)

    def climber_boulders(self, climber_id: int) -> list[dict]:
        return self._get(f"/climbers/{int(climber_id)}/boulders")

    def hard_boulders(self) -> list[dict]:
        return self._get("/boulders")


# ---- normalisation -------------------------------------------------------------

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def norm(text: str | None) -> str:
    """Accent-, case- and punctuation-insensitive key: 'Soudain Seul!' -> 'soudain seul'."""
    s = unicodedata.normalize("NFKD", text or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).casefold()
    return _NON_ALNUM.sub(" ", s).strip()


def norm_grade(grade: str | None) -> str:
    """'8C+/9A' -> '8C+', '8C (hard)' -> '8C'. Empty for ungraded."""
    g = (grade or "").split("/")[0]
    g = re.sub(r"\(.*?\)", "", g).strip().upper()
    return g


def is_hard(grade: str | None) -> bool:
    """8C or harder, including grades above our seed table (9B and up)."""
    g = norm_grade(grade)
    return g in GRADE_SEED or g.startswith("9")


# ---- matching -----------------------------------------------------------------

@dataclass
class Matcher:
    by_ch_id: dict[int, ProblemRow] = field(default_factory=dict)
    by_name_crag: dict[tuple[str, str], ProblemRow] = field(default_factory=dict)
    by_name: dict[str, ProblemRow | None] = field(default_factory=dict)  # None = ambiguous

    @classmethod
    def load(cls, s: Session) -> "Matcher":
        m = cls()
        for p in s.scalars(select(ProblemRow)):
            if p.ch_id:
                m.by_ch_id[p.ch_id] = p
            m.by_name_crag[(norm(p.name), norm(p.crag))] = p
            m.by_name[norm(p.name)] = None if norm(p.name) in m.by_name else p
        return m

    def match(self, climb: dict) -> ProblemRow | None:
        cid = climb.get("climb_id")
        if cid is not None and int(cid) in self.by_ch_id:
            return self.by_ch_id[int(cid)]
        n = norm(climb.get("climb_name"))
        if (p := self.by_name_crag.get((n, norm(climb.get("crag_name"))))) is not None:
            return p
        return self.by_name.get(n)


def summarise_ascents(ascents: list[dict]) -> dict[int, dict]:
    """One row per climb: done if any ascent was successful (dated by the first send),
    otherwise tried (dated by the latest attempt)."""
    out: dict[int, dict] = {}
    for a in ascents:
        cid = a.get("climb_id")
        if cid is None:
            continue
        row = out.setdefault(int(cid), {**a, "status": ASCENT_TRIED, "date": None})
        date = a.get("ascent_dt_end") or a.get("ascent_dt_start") or None
        if a.get("successful"):
            if row["status"] != ASCENT_DONE:
                row["status"], row["date"] = ASCENT_DONE, date
            elif date and (row["date"] is None or date < row["date"]):
                row["date"] = date
        elif row["status"] == ASCENT_TRIED and date and (row["date"] is None or date > row["date"]):
            row["date"] = date
    return out


def preview(s: Session, ascents: list[dict], current: dict[int, str]) -> dict:
    """Match a climber's climbing-history boulders against our problems.

    Returns matched rows (with the member's current status on our side), the hard
    boulders we couldn't match, and how many easier problems were ignored.
    """
    m = Matcher.load(s)
    matched, unmatched, skipped = [], [], 0
    for climb in summarise_ascents(ascents).values():
        p = m.match(climb)
        if p is not None:
            matched.append({"problem": p, "status": climb["status"], "current": current.get(p.id),
                            "ch_name": climb.get("climb_name") or "", "ch_grade": climb.get("grade") or "",
                            "ch_url": climb.get("climb_url") or "", "date": climb["date"] or ""})
        elif is_hard(climb.get("grade")):
            unmatched.append({"climb_id": int(climb["climb_id"]), "climb_name": climb.get("climb_name") or "",
                              "grade": climb.get("grade") or "", "crag_name": climb.get("crag_name") or "",
                              "climb_url": climb.get("climb_url") or "", "status": climb["status"]})
        else:
            skipped += 1
    matched.sort(key=lambda r: (r["status"] != ASCENT_DONE, r["problem"].name))
    return {"matched": matched, "unmatched": unmatched, "n_skipped": skipped}


def backfill_ids(s: Session, boulders: list[dict]) -> dict:
    """Store climbing-history ids/urls on problems matched by name. Returns a report of what
    matched and what didn't on either side so an admin can fix names by hand."""
    m = Matcher.load(s)
    linked, unmatched_theirs = 0, []
    seen: set[int] = set()
    for climb in boulders:
        p = m.match(climb)
        if p is None:
            unmatched_theirs.append({"climb_id": climb["climb_id"], "climb_name": climb.get("climb_name") or "",
                                     "grade": climb.get("grade") or "", "crag_name": climb.get("crag_name") or ""})
            continue
        seen.add(p.id)
        if p.ch_id != int(climb["climb_id"]) or (climb.get("climb_url") and p.ch_url != climb["climb_url"]):
            p.ch_id, p.ch_url = int(climb["climb_id"]), climb.get("climb_url") or p.ch_url
            linked += 1
    unmatched_ours = [{"id": p.id, "name": p.name, "crag": p.crag, "grade": p.current_grade}
                      for p in s.scalars(select(ProblemRow).order_by(ProblemRow.name)) if p.id not in seen and not p.ch_id]
    s.flush()
    return {"linked": linked, "unmatched_theirs": unmatched_theirs, "unmatched_ours": unmatched_ours}

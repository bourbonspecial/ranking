"""Build the seed database from data/hardest_problems.csv.

CSV columns: <index>,Climb,Grade,Crag,First Ascent,# Ascents
"First Ascent" looks like "Nalle Hukkataival (24th Oct 2016)" and may be blank.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .db import PROBLEMS_CSV, SEED_DB, ProblemRow, create_schema, make_session_factory
from .scale import grade_to_rating

_FA = re.compile(r"^\s*(?P<name>[^()]*?)\s*(?:\((?P<date>[^)]*)\))?\s*$")


def parse_first_ascent(text: str) -> tuple[str, str]:
    m = _FA.match(text or "")
    if not m:
        return (text or "").strip(), ""
    return (m.group("name") or "").strip(), (m.group("date") or "").strip()


def read_problems_csv(path: Path = PROBLEMS_CSV) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            grade = r["Grade"].strip()
            grade_to_rating(grade)  # validate
            fa_name, fa_date = parse_first_ascent(r.get("First Ascent", ""))
            rows.append({
                "name": r["Climb"].strip(),
                "seed_grade": grade,
                "current_grade": grade,
                "crag": (r.get("Crag") or "").strip(),
                "fa_name": fa_name,
                "fa_date": fa_date,
                "ascent_count": int(r.get("# Ascents") or 0),
            })
    return rows


def build_seed_db(csv_path: Path = PROBLEMS_CSV, db_path: Path = SEED_DB) -> int:
    if db_path.exists():
        db_path.unlink()
    create_schema(db_path)
    rows = read_problems_csv(csv_path)
    with make_session_factory(db_path)() as s:
        s.add_all(ProblemRow(**r) for r in rows)
        s.commit()
    return len(rows)

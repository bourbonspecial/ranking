# Boulder Ranking

Ranking engine for boulder problems 8C and harder, built from pairwise
"which was harder for you?" comparisons. See [SCOPE.md](SCOPE.md).

## Quick start

```
./start.sh --admin you@example.com     # venv, deps, db, frontend build, server on http://localhost:8000
```
Then sign in with that email on the landing page; the magic link is printed in the terminal.
`--reset` wipes the local database back to the seed; `--dev` also runs the Vite dev server
with hot reload on :5173.

## Data

- `data/hardest_problems_8c.csv` — source list of problems 8C and harder (433 problems).
- `data/seed.sqlite` — committed. Built from the CSV with `ranking db build-seed`; problems only.
- `data/local.sqlite` — gitignored. Copied from the seed on first `ranking db init`; all local
  climbers, comparisons and rating snapshots live here.

```
.venv/bin/ranking db init        # copy seed -> local (no-op if it exists; --force to reset)
.venv/bin/ranking recompute      # fit every algorithm, store a snapshot run in local.sqlite
.venv/bin/ranking list           # latest stored ranking (--algo elo|win_rate)
.venv/bin/ranking db import      # upsert a refreshed CSV into local.sqlite (keeps ids and comparisons)
```

Schema (`ranking/db.py`): problems, climbers, ascents, comparisons (live, one per
climber-pair), comparison_history (audit only), rating_runs, rating_snapshots.
`ranking/repo.py` is the repository layer the API will sit on.

## Phase 2: API

```
.venv/bin/ranking admin you@example.com --name "You"   # make yourself an admin in local.sqlite
.venv/bin/ranking serve --reload                        # http://127.0.0.1:8000/docs
```

Then `POST /api/auth/request-link {"email": ...}` — in dev the magic link is printed to the
server console (`RANKING_EMAIL_BACKEND=console`, the default).

Configuration lives in `.env` (gitignored; `start.sh` loads it). Copy `.env.example` and fill in
the Resend API key to send real mail via SMTP. `RANKING_BASE_URL` is embedded in every magic
link. `remknowles@gmail.com` and `alexander.gradenegger@gmail.com` are always admins
(`DEFAULT_ADMIN_EMAILS`); add more via `RANKING_ADMIN_EMAILS` or the admin panel's "Make admin".
An invited member receives a welcome email the first time they sign in. Admins can flag a
member as a **test user** (admin panel → Test): they can use everything, but their comparisons
are excluded from the global ranking and its stats.

Schema changes: `create_schema()` runs on every start (via `ranking db init`) and both creates
missing tables and adds missing columns listed in `db._ADDED_COLUMNS`, so a deploy migrates the
server database automatically. Add new columns there.

| route | who | what |
|---|---|---|
| `POST /api/invite-requests` | anyone | ask for an invite (name, email, note) |
| `POST /api/auth/request-link` · `GET /api/auth/callback` · `POST /api/auth/logout` · `GET /api/me` | anyone | magic-link auth |
| `GET /api/problems` | member | master list |
| `GET/PUT /api/me/ascents` · `GET /api/me/progress` | member | tick list and ranking-gate progress |
| `GET /api/me/pairs` · `POST /api/me/comparisons` · `GET /api/me/comparisons` | member | compare flow; posting an already-answered pair revises it |
| `GET /api/ranking?algo=` | member (gated) | latest stored ranking; `bradley_terry` / `elo` / `win_rate` |
| `GET /api/me/ranking` · `PATCH /api/me` | member | personal ranking with global rank alongside; toggle `public_profile`; set `gender`, `height_cm`, `arm_span_cm` (optional demographics, admin-visible only) |
| `GET /api/climbers/{id}/public` | anyone | a member's personal ordering + answers, only if they opted in |
| `GET /api/admin/climbers?status=` · `POST /api/admin/climbers/{id}/invite` · `POST /api/admin/invite` · `POST /api/admin/climbers/{id}/reject` · `POST /api/admin/climbers/{id}/admin` · `POST /api/admin/recompute` | admin | invite queue and tooling |

Ascents are `done` or `tried`. Comparisons involving a tried problem are offered last, opt-in,
weighted at `RANKING_ATTEMPT_WEIGHT` (default 0.4), excluded from the ranking gate, and stored as
a separate ranking variant (`GET /api/ranking?include_attempts=true`).

Ratings are recomputed in the background ~20s after the last comparison (`RANKING_RECOMPUTE_DEBOUNCE`).

## Phase 3: frontend

Vite + Svelte 5 SPA in `frontend/`, served by FastAPI from `frontend/dist` (built output is
gitignored — run the build before `ranking serve`).

```
cd frontend && npm install && npm run build     # production build -> dist/
cd frontend && npm run dev                       # dev server on :5173, proxies /api to :8000
```

Pages: landing (invite request / sign-in), My ascents, Compare (← ↓ → keys, `s` to skip),
My answers (revise inline), The list (gated; algorithm + grade filters), Profile (personal
ordering vs global), Admin (invite queue, direct invite, recompute).

## Phase 1: rating engine

```
uv venv -p 3.12 && uv pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ranking simulate --problems 120 --climbers 40 --seed 0
.venv/bin/ranking rank problems.csv comparisons.csv --algo bradley_terry
```

### Algorithms (`ranking/`)

| module | what |
|---|---|
| `bradley_terry.py` | **Default.** Bradley–Terry with ties (Davidson) fitted by MAP to all comparisons at once, with a Normal prior centred on the grade seed. Reports rating + uncertainty (Laplace). Order-independent. |
| `elo.py` | Sequential Elo replayed chronologically from the grade seeds. Ties = 0.5. |
| `winrate.py` | Naive share of comparisons "won". Sanity check only. |
| `personal.py` | Bradley–Terry fitted to one climber's own comparisons — the private "your ranking" view. |
| `pairs.py` | Compare-flow queue: unanswered pairs, rarest problems first. Ranking gate threshold `min(10, possible pairs)`. |
| `models.py` | `Problem`, `Comparison`, `Verdict`; `latest_comparisons()` keeps one answer per climber-pair. |
| `simulate.py` | Synthetic world with hidden true difficulties, mis-graded problems, biased climbers. Used to tune and test. |

Ratings are on an Elo-like scale (400 points = 10:1 odds). Seeds:
8C 1500 · 8C+ 1750 · 9A 2000 · 9A+ 2250.

### Prior strength (tuned on the simulator)

Spearman correlation with the hidden true order, mean over 8 seeds, 100
problems, 40 climbers:

| | grades only | Elo k=32 | BT sd=50 | **BT sd=100** | BT sd=200 | BT sd=400 | BT no prior |
|---|---|---|---|---|---|---|---|
| accurate grades, all pairs answered | 0.855 | 0.946 | 0.958 | **0.951** | 0.918 | 0.898 | 0.926 |
| accurate grades, 30% of pairs | 0.855 | 0.949 | 0.947 | **0.951** | 0.935 | 0.895 | 0.893 |
| noisy grades, all pairs | 0.740 | 0.910 | 0.913 | **0.917** | 0.896 | 0.881 | 0.917 |
| noisy grades, 30% of pairs | 0.740 | 0.909 | 0.878 | **0.909** | 0.901 | 0.873 | 0.885 |

`prior_sd=100` is the default. Medium priors (200–1000) do worst: they let a
handful of noisy comparisons drag sparsely-compared problems a long way
without either the grade or the data anchoring them.

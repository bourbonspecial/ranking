# Boulder Ranking — Scope v0.2

## Goal

A single, continuously updated, globally ordered list of every boulder problem
graded **8C+ or harder** (floor raised from 8C to match the source list), worldwide, derived from pairwise "which was harder for
you?" judgements made by climbers who have climbed both problems.

Grades are not the output. The ordering is. Grade bands may be layered on top
later as an afterthought.

## Principles

- **Harder = harder for you.** No attempt to normalise for style or morphology.
- **One climber, one opinion per pair.** Re-answering a pair replaces the
  previous answer; only the most recent answer counts.
- **Seed from consensus, overwrite with data.** Problems start at a rating
  implied by their climbing-history.org grade; over time comparison data fully
  replaces that prior.
- **Everything is recomputable.** Raw comparisons are the source of truth.
  Ratings are derived and can be recomputed from scratch under any algorithm.
- **Names visible to members, votes visible to nobody.** Members can see who is
  on the site; individual votes are never shown to other users.

## Entities

### Problem
- `id`, `name`, `area`, `country`
- `seed_grade` — grade on climbing-history.org at import time (8C, 8C+, 9A, 9A+)
- `ch_id` / `ch_url` — link back to climbing-history.org
- `ascent_count` — number of known ascents (from climbing-history.org; used to
  bias pair selection towards obscure problems)
- Includes disputed / unverified problems; no filtering.

### Climber (user)
- `id`, `name` (real name, visible to members), `email`
- `status`: requested → invited → active
- Eligibility: **≥2 climbed ascents at 8C+ or harder** (i.e. at least one possible pair)
- `ascents`: Problem ids on the climber's list, each **done** (climbed) or
  **tried** (attempted, not climbed)

### Attempts
Climbers may also list problems they have tried but not done, and compare
them against problems they have climbed. A comparison involving a tried
problem is an *attempt comparison*:
- Offered only after every done–done pair is answered, and only if the
  climber opts in.
- Weighted at `attempt_weight` (default **0.4**, `RANKING_ATTEMPT_WEIGHT`)
  in every algorithm; the weight is derived at compute time from current
  statuses, so sending a tried problem promotes its old comparisons.
- Never counts towards the ranking gate.
- Rankings are stored in two variants — done-only and with attempts — and
  members toggle between them on the list.

### Comparison
- `climber_id`, `problem_a_id`, `problem_b_id` (stored canonically, a < b)
- `verdict`: `A_HARDER` | `SIMILAR` | `B_HARDER`
- `created_at`, `updated_at`
- Unique on (climber, a, b). Editing overwrites; a history table keeps old
  values for audit but they never feed the ranking.

### Rating snapshot
- `algorithm`, `problem_id`, `rating`, `uncertainty`, `n_comparisons`,
  `computed_at`
- Written by a batch recompute; one row per problem per algorithm per run.

## Rating engine

The engine is a pure Python package with no web dependencies, built and tested
first against simulated data (Phase 1).

Input: the current set of comparisons (latest per climber-pair). Output: a
rating + uncertainty per problem, per algorithm.

### Algorithms

Several rankings are computed side by side; the UI shows one by default and
lets members switch.

| Algorithm | Role | Notes |
|---|---|---|
| **Bradley–Terry with ties (Davidson) + grade prior** | **Default** | Batch model fitted to all comparisons at once. Order-independent, handles ties natively, produces a proper uncertainty estimate. The grade seed enters as a Bayesian prior whose weight shrinks as a problem accumulates comparisons — satisfies "overwritten by data over time". |
| Elo | Familiar comparison | Sequential, replayed from comparison history in timestamp order. Seeded 8C=1500, 8C+=1750, 9A=2000, 9A+=2250. Ties scored 0.5. K configurable. |
| TrueSkill / Glicko-2 | Optional, later | Uncertainty-aware sequential ratings. Cheap to add once the engine interface exists. |
| Naive win-rate / Copeland | Sanity check | Fraction of comparisons "won", for spotting where the models disagree with raw data. |

Why Bradley–Terry is the default: the data will be sparse and arrive in bursts
(one climber answering 50 pairs in a sitting). Sequential systems like Elo give
different answers depending on the order those 50 answers are processed and
over-weight the most recent voter. A batch model has no such dependency and
the "overwrite the prior over time" behaviour falls out naturally.

### Confidence indicator
Per problem: number of distinct climbers who have compared it, number of
comparisons, and the model's uncertainty. Shown on the list as a simple
tier (e.g. low / medium / high) plus the raw counts on hover/detail.
Problems with zero comparisons are still listed, at their seed rating, flagged
"no data".

### Pair selection
When a climber is comparing, the queue of unanswered pairs from their ascent
list is ordered so that pairs containing problems with **few ascents** (from
climbing-history.org) and **few existing comparisons** in the system come
first. Climbers can work through the entire queue; there is no cap. Answered
pairs remain accessible for revision.

## Web application

### Stack
- **Backend:** FastAPI, SQLAlchemy, SQLite (committed `data/seed.sqlite` with
  problems only; gitignored `data/local.sqlite` copied from it for running). Rating recompute runs as a background job after new
  comparisons (debounced) and on a schedule.
- **Frontend:** Single-page app — SvelteKit or React+Vite (decide at build
  time; Svelte preferred for a small hobby project). Served by the same
  container.
- **Auth:** Magic-link email. No passwords. Session cookie after link click.
- **Email:** SMTP via a transactional provider (e.g. Resend / Postmark free
  tier) or the home server's own relay.
- **Deployment:** Docker Compose on the home server, reverse proxy with TLS.

### Pages

Public:
1. **Landing / invite request** — deliberately sparse and intriguing. Explains
   almost nothing beyond "a ranking of the world's hardest boulders, built by
   the people who've climbed them". Short form: name, email, a free-text
   "what have you climbed at 8C or harder?" field. Submits an invite request.
2. **Magic-link landing** — consumes the token, sets session.

Members:
3. **Tick list** — searchable master list of 8C+ problems; climber toggles
   their ascents. Link to "problem missing?" which creates an admin request.
4. **Compare** — one pair at a time, three buttons, keyboard shortcuts,
   progress indicator ("14 of 210 pairs answered"). Option to skip.
5. **My comparisons** — list of everything answered, editable.
6. **Ranking** — the ordered list. Columns: rank, problem, area, seed grade,
   rating, confidence. Filter by grade/country, algorithm switcher.
   **Gated:** visible once the climber has made 10 comparisons, or all of
   their possible pairs if fewer than 10.
7. **Profile** — climber's ascents, comparison count, and their **personal
   ranking**: their ascents ordered by their own comparisons only (fit the
   same model on just their data), shown alongside the global rank for each.
   Private to the climber.

Admin:
8. **Invite requests** — queue of requests; approve (sends magic-link invite)
   or reject. Also direct "send invite to email".
9. **Problems** — import/refresh from climbing-history.org, edit, merge
   duplicates, handle "problem missing" requests.
10. **Climbers** — list, deactivate.
11. **Rankings** — trigger recompute, view per-algorithm output, download CSV.

## Data import

One-off script plus a repeatable refresh: pull all problems ≥8C from
climbing-history.org (via API or DB access, since we own it) with name, area,
country, current grade, ascent count, and the ch id. Refresh updates
`ascent_count` and grade but never changes `seed_grade` once set, so the prior
is stable.

## Out of scope (for now)

- Routes; anything below 8C
- Public visibility of the ranking or any votes
- Vote weighting by climber
- Recording ascent context (flash, conditions, year)
- Mobile app; social features; public sign-up without invite
- Automatic grade assignment from the ordering

## Phases

**Phase 1 — Rating engine (no web)**
Python package `ranking/`: data model for comparisons, Bradley–Terry-with-ties
+ prior, Elo replay, win-rate baseline, per-climber fit, confidence measures.
Simulator that generates problems with a hidden "true difficulty", climbers
with noisy perceptions and partial tick lists, and comparisons — used to test
that each algorithm recovers the true order and to tune the prior weight and
K-factor. CLI to run against a CSV of comparisons. Full test suite.

**Phase 2 — Backend**
FastAPI app, schema + migrations, climbing-history.org import, magic-link
auth, API endpoints for all member and admin actions, background recompute,
ranking gate logic, pair-selection ordering.

**Phase 3 — Frontend**
Landing/invite page, tick list, compare flow, my comparisons, ranking,
profile, admin screens.

**Phase 4 — Deploy**
Docker Compose, TLS, email provider, backups of the Postgres volume, first
batch of invites.

## Open items

- ~~Prior weight for Bradley–Terry~~ — settled in Phase 1: `prior_sd=100`
  rating points (seed outweighed after roughly 12 comparisons). Best or
  joint-best on the simulator across dense/sparse data and accurate/noisy
  grades; see README.
- ~~Access method for climbing-history.org data~~ — CSV export at `data/hardest_problems.csv` for now.
- Email provider choice.
- Svelte vs React.

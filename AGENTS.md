# AGENTS.md

Working notes for anyone (human or agent) contributing to this repo. `CLAUDE.md` is a symlink
to this file. Keep it short; details live in `README.md` and `SCOPE.md`.

## What this is

A members-only site that produces one globally ordered list of every boulder problem graded
**8C or harder**. The order comes from pairwise "which was harder for you?" answers given by
climbers who have climbed (or tried) both problems — not from grades. Grades only seed the
starting ratings; comparison data overwrites them over time. Raw comparisons are the source of
truth; every ranking is recomputable from scratch under any algorithm.

Goals, in priority order:

1. A trustworthy ordering from a small number of very strong climbers — pairs are chosen to
   maximise information, and every climber's answers stay private.
2. Low friction for members: magic-link sign-in, tick your list, answer a handful of pairs,
   the list unlocks.
3. Simple to run: one Python process, SQLite, a built Svelte SPA, behind nginx on a home server.

Layout:

- `ranking/` — engine (`bradley_terry.py`, `elo.py`, `winrate.py`, `pairs.py`, `personal.py`, `scale.py`), storage
  (`db.py`, `repo.py`), and the FastAPI app (`ranking/api/`).
- `frontend/` — Svelte 5 + Vite SPA; `frontend/dist` is built locally and shipped.
- `data/` — source CSV from climbing-history.org and the committed `seed.sqlite`.
- `tests/` — pytest suite. `SCOPE.md` is the product spec; `README.md` covers setup and ops.

## Development workflow

1. **Branch.** Start from up-to-date `main`: `git switch -c <short-topic-name> main`.
   Never commit directly to `main`.
2. **Commit in logical units.** Each commit should be one coherent change that leaves the
   tree working (tests passing). Separate refactors from behaviour changes, and mechanical
   changes from the interesting ones, so each can be reviewed on its own.
   Commit messages follow the Go convention
   (<https://go.dev/doc/contribute#commit_messages>):

   ```
   api/routes: refund the rate-limit token when the suggestion email fails

   A member whose suggestion could not be emailed was charged one of their
   five hourly tokens and shown a 500. Send first, then charge; on an SMTP
   error give the token back and return 503 with a retry hint.

   Fixes #12
   ```

   - First line: `<package or area>: <what changed>`, lowercase after the colon, no trailing
     period, ideally under ~76 characters. Area examples: `api/routes`, `repo`, `frontend/ticks`,
     `tests`, `docs`, `all`.
   - Blank line, then a body in complete sentences explaining *what* and *why* — the diff
     already shows *how*. Write it for someone reading `git log` in a year.
   - Reference issues at the end (`Fixes #N`, `Updates #N`).
3. **Push the branch.** `git push -u origin <branch>`. Rebase on `main` rather than merging
   it in; force-push your own branch freely (`--force-with-lease`), never `main`.
4. **Open a pull request** against `main`. The description should give a reviewer everything
   they need without opening the diff:
   - What changed and why (link the issue or the SCOPE.md section it serves).
   - Anything a reviewer should look at carefully, or that you are unsure about.
   - **Testing done:** which automated tests were added or changed, the `pytest` result, and
     any manual checks (e.g. "signed in as a test user, ticked two problems, confirmed the
     ranking recomputed"). If the frontend changed, confirm `npm run build` succeeds and
     describe what you clicked through.
   - Deployment notes if any: new env vars (`.env.example` updated?), schema changes
     (`db._ADDED_COLUMNS`?), nginx changes.

Small fixes still get a PR; the PR is the record of what was tested and why.

## Testing strategy

Run the whole suite before every push: `.venv/bin/python -m pytest -q` (≈3 s). Frontend:
`cd frontend && npm run build` — there are no JS unit tests yet; the build catches template and
import errors.

What the tests cover, and where new tests go:

- **Engine** (`test_bradley_terry.py`, `test_elo_winrate.py`, `test_weights.py`,
  `test_simulation.py`) — algorithm correctness on hand-built comparison sets, seed/prior
  behaviour, attempt weighting, and a simulation that checks the fitted order recovers a known
  true order from noisy votes. Change these when you touch rating maths; a new algorithm needs
  the same treatment plus registration in `repo.ALGORITHMS`.
- **Pair selection and personal rankings** (`test_pairs_personal.py`) — next-pair ordering,
  the done-first/attempts-after rule, the ranking gate.
- **Storage** (`test_db.py`, `test_models.py`) — schema creation and migration
  (`_ADDED_COLUMNS`), CSV import and re-import keeping ids, repository functions against a
  temporary SQLite file.
- **API** (`test_api.py`, `test_rate_limit.py`) — end-to-end through FastAPI's `TestClient`
  against a fresh seed database per test (`conftest.py`). Auth via real magic links pulled
  from the console mailer, member/admin permission boundaries, input validation, rate limits,
  and that writes which change comparison weights trigger a recompute
  (`recompute_debounce_seconds=0` makes it synchronous).

Conventions:

- Tests are black-box where possible: drive the API or repo, assert on responses and DB state,
  not on internals.
- Every bug fix gets a regression test that fails before the fix.
- Anything that sends email uses the `console` backend and asserts on `app.state.mailer.sent`;
  never hit SMTP in tests.
- Keep tests fast and deterministic — no sleeps, no network, no wall-clock (inject a clock as
  `SlidingWindowRateLimiter` does).
- No manual testing checklist is a substitute for a test, but UI changes should still be
  clicked through with `./start.sh --dev` and described in the PR.

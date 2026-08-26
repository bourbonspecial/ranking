#!/usr/bin/env bash
# Spin everything up for local use: venv, deps, database, frontend build, server.
# Usage: ./start.sh [--admin you@example.com] [--reset] [--dev]
#   --admin EMAIL  make EMAIL an admin (so you can sign in; magic link prints below)
#   --reset        wipe data/local.sqlite back to the seed
#   --dev          also run the Vite dev server on :5173 with hot reload (API still on :8000)
set -euo pipefail
cd "$(dirname "$0")"

ADMIN="" RESET=0 DEV=0
while [ $# -gt 0 ]; do
  case "$1" in
    --admin) ADMIN="$2"; shift 2 ;;
    --reset) RESET=1; shift ;;
    --dev)   DEV=1; shift ;;
    *) echo "unknown option $1"; exit 1 ;;
  esac
done

step() { printf '\n\033[1;33m▸ %s\033[0m\n' "$*"; }

if [ -f .env ]; then
  step "Loading .env"
  set -a; # export everything sourced
  # shellcheck disable=SC1091
  . ./.env
  set +a
  [ -z "${RANKING_SMTP_PASSWORD:-}" ] && [ "${RANKING_EMAIL_BACKEND:-console}" = smtp ] && \
    echo "warning: RANKING_EMAIL_BACKEND=smtp but RANKING_SMTP_PASSWORD is empty - falling back to console" && export RANKING_EMAIL_BACKEND=console
fi

step "Python environment"
command -v uv >/dev/null || { echo "uv not found: https://docs.astral.sh/uv/"; exit 1; }
[ -d .venv ] || uv venv -p 3.12 -q
uv pip install -q -e ".[dev]"

step "Database"
[ -f data/seed.sqlite ] || .venv/bin/ranking db build-seed
if [ "$RESET" = 1 ]; then .venv/bin/ranking db init --force; else .venv/bin/ranking db init; fi
[ -n "$ADMIN" ] && .venv/bin/ranking admin "$ADMIN"

step "Frontend"
command -v npm >/dev/null || { echo "npm not found"; exit 1; }
(cd frontend && { [ -d node_modules ] || npm install --silent; } && npm run build --silent)

if [ "$DEV" = 1 ]; then
  step "Vite dev server → http://localhost:5173 (hot reload)"
  (cd frontend && npm run dev -- --strictPort >/dev/null 2>&1 &)
fi

step "API + app → http://localhost:8000"
if [ "${RANKING_EMAIL_BACKEND:-console}" = console ]; then echo "Sign-in links are printed here (RANKING_EMAIL_BACKEND=console). Ctrl-C to stop."; else echo "Email via SMTP ${RANKING_SMTP_HOST:-}. Ctrl-C to stop."; fi
[ "$DEV" = 1 ] && trap 'pkill -f "vite" 2>/dev/null || true' EXIT
exec .venv/bin/ranking serve --host 127.0.0.1 --port 8000

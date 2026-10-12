#!/usr/bin/env bash
# Start HR Recruit Agent backend.
# Activates the project venv, checks .env exists, runs uvicorn with auto-reload.
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "ERROR: .venv not found. Run: python -m venv .venv && .venv/bin/pip install -e ."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill MINIMAX_API_KEY."
  exit 1
fi

exec uvicorn app.main:app --port 8000 --host 127.0.0.1 --reload

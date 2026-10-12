#!/usr/bin/env bash
# Start HR Recruit Agent frontend (Vite dev server).
set -e
cd "$(dirname "$0")"

if [ ! -d node_modules ]; then
  echo "node_modules missing, running npm install..."
  npm install
fi

exec npm run dev

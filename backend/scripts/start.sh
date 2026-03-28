#!/usr/bin/env sh
set -eu

python scripts/apply_migration.py
python -m app.seed
uvicorn app.main:app --host 0.0.0.0 --port 8000

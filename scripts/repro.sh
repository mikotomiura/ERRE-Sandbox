#!/usr/bin/env bash
# Thin alias kept for the historical entry point named in
# docs/experiment-tracking.md. The reproduction entry point is now
# scripts/verify_committed_artifacts.py, which covers the sealed real-model
# bundles as well as this fixture and works identically on Windows.
#
# See REPRODUCING.md. To verify everything (what CI runs on both operating
# systems):
#
#   uv run --frozen --no-dev python scripts/verify_committed_artifacts.py
#
# This script narrows that to the ECL v0 golden fixture only.
#
# Why the ERRE_ZONE_BIAS_P export that used to live here is gone: it set 0.1
# while every bundle's manifest pins "0.2", and measurement on 2026-09-12 showed
# the golden verify passes identically at 0.1 / 0.2 / 0.9 / unset -- it was both
# wrong and inert. Carrying it into the wider target set would not have been
# inert, because the society and live-loop replays read the same variable. The
# new entry point sets the value each bundle records in its own env_pins, per
# subprocess (.steering/20260912-paper03-repro-path/decisions.md DA-P03R-1).

set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=".venv/Scripts/python.exe"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON=".venv/bin/python"
fi
if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: Python venv not found. Run 'uv sync' first." >&2
    exit 2
fi

exec "$PYTHON" scripts/verify_committed_artifacts.py --only ecl-v0-golden

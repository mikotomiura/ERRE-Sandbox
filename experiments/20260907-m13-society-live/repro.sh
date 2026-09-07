#!/usr/bin/env bash
# M13 society live-closure Issue 007 — Ollama-free replay-verify (1 command
# reproduction). Verifies the COMMITTED bytes: Plane G replay + request
# conformance + fixed constructor fingerprint + the 3 side annotations.
# Opens no connection, spends nothing, regardless of --real. Used for the
# WSL/Linux side of the L3 cross-platform byte check (or the equivalent CI
# job, when no WSL project venv is available on this host).
#
#   ./repro.sh              # the committed Ollama-free rehearsal bundle
#   ./repro.sh --real       # the sealed real bundle (absent until a future
#                            # ratified session produces one)
set -euo pipefail
cd "$(dirname "$0")/../.."

export PYTHONUTF8=1
if [ "${1:-}" = "--real" ]; then
  python scripts/m13_society_live_capture.py --verify --real
else
  python scripts/m13_society_live_capture.py --verify
fi

#!/usr/bin/env bash
# ECL v0 live-capture — 1-command Ollama-free replay-verify (Issue 002,
# loop/20260706-ecl-v0-live-run/issues/002-replay-verify-apparatus.md, I4-G5).
#
# This apparatus reproduces a committed artifact bundle's ecl_trace_checksum
# from decisions.jsonl alone (O3a, inner_invocations == 0) and re-renders the
# full artifact set from the same replayed result to check every per-artifact
# SHA-256 (O3b) — see scripts/ecl_v0_live_capture.py's `verify()`.
#
# Issue 003 (sealed live run) / Issue 004 (final swap) will populate
# experiments/20260706-ecl-v0-live-capture/artifacts/ with the committed
# sealed-run artifact. Until that lands this script falls back to the
# synthetic golden template (tests/fixtures/ecl_v0_golden/), so the
# 1-command contract exists today and exits 0 (Issue 002 scope).
#
# Usage:
#   bash experiments/20260706-ecl-v0-live-capture/repro.sh [artifact_dir]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEFAULT_ARTIFACT_DIR="${REPO_ROOT}/experiments/20260706-ecl-v0-live-capture/artifacts"
TEMPLATE_ARTIFACT_DIR="${REPO_ROOT}/tests/fixtures/ecl_v0_golden"

ARTIFACT_DIR="${1:-${DEFAULT_ARTIFACT_DIR}}"

if [ ! -f "${ARTIFACT_DIR}/manifest.json" ]; then
  echo "[repro] no committed live artifact at ${ARTIFACT_DIR} yet (Issue 003/004)"
  echo "[repro] falling back to the synthetic golden template: ${TEMPLATE_ARTIFACT_DIR}"
  ARTIFACT_DIR="${TEMPLATE_ARTIFACT_DIR}"
fi

if [ -x "${REPO_ROOT}/.venv/Scripts/python.exe" ]; then
  PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
elif [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python"
else
  PYTHON="python3"
fi

echo "[repro] Ollama-free replay-verify: ${ARTIFACT_DIR}"
"${PYTHON}" "${REPO_ROOT}/scripts/ecl_v0_live_capture.py" --verify --artifact-dir "${ARTIFACT_DIR}"

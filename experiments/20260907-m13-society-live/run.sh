#!/usr/bin/env bash
# M13 society live-closure Issue 007 sealed real run (human-gated) — WSL2 /
# Linux side. REAL SPEND — run only after the user has explicitly ratified
# the spend. See run.ps1 for the full note; --confirm-spend is mandatory and
# the harness additionally refuses unpinned provenance, off-plan parameters
# (the roster/horizon/seed/perturbation-budget are frozen and not exposed as
# flags at all, AC7), and overwriting an existing sealed bundle.
#
# HARD STOP (binding for Issue 007 itself): not invoked by this issue's own
# automation. Documented here for a future ratified session only.
set -euo pipefail
cd "$(dirname "$0")/../.."

export PYTHONUTF8=1

# Fail fast on unset provenance rather than sealing an unauditable artifact.
missing=()
for name in QWEN3_DIGEST OLLAMA_VERSION VRAM_GB; do
  if [ -z "${!name:-}" ]; then missing+=("$name"); fi
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "ERROR: unset provenance environment variable(s): ${missing[*]}" >&2
  echo "Set them before the sealed run, e.g.:" >&2
  echo '  export QWEN3_DIGEST=$(ollama show qwen3:8b --json | jq -r .digest)' >&2
  echo '  export OLLAMA_VERSION=$(ollama --version)' >&2
  echo '  export VRAM_GB=16' >&2
  exit 2
fi

# --uv-lock-sha256 is intentionally NOT passed: the harness derives it from
# this checkout's uv.lock. No ticks/seed/agent-ids flags exist (AC7).
python scripts/m13_society_live_capture.py --capture --real --confirm-spend \
  --out-dir experiments/20260907-m13-society-live/artifacts \
  --qwen3-model-digest "$QWEN3_DIGEST" \
  --ollama-version "$OLLAMA_VERSION" \
  --vram-gb "$VRAM_GB"

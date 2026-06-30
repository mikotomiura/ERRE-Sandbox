#!/usr/bin/env bash
# M13-ES4 scorer offline diagnostic — 1-command reproduction (CPU only, zero GPU).
set -euo pipefail
cd "$(dirname "$0")/../.."
PYTHONPATH=src python scripts/es4_scorer_diag.py \
  --run-dir experiments/20260630-es4-phase0/phaseA \
  --out experiments/20260701-es4-scorer-diag/diagnostic.json

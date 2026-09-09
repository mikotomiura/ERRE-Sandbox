#!/usr/bin/env bash
# paper01 scope-condition -- issue 007 one-command reproduction.
#
# ① export PYTHONHASHSEED (from SEED) + HF_HUB_OFFLINE=1 + PYTHONUTF8=1
# ② --fidelity  (design-final.md §6 pin (b)+(c); exit 1 on mismatch, exit 2
#                on source-unavailable -- scripts/paper01_scope_condition.py's
#                cli_fidelity() never conflates the two; either is fatal here)
# ③ --scope     -> results/scope.json
# ④ --scope again into a scratch path, SHA-256 compare -> exit 1 on mismatch
# ⑤ metrics.json (build_metrics.py, read-only extraction -- never recomputes
#                 a statistic)
# ⑥ completion marker (final log line; see run_gate.py's
#                       run_sh_has_completion_marker / PID-survival +
#                       log-tail progress judgement --
#                       feedback_log_tail_completion_marker.md)
#
# Runs on both Windows (Git Bash) and WSL2/Linux. Python is resolved from
# $PYTHON if set, else .venv/Scripts/python.exe (Windows), else
# .venv/bin/python (WSL2/Linux), else a bare python3 on PATH.
#
# Needs a live Ocsai fetch (network) for ② and ③/④ -- this is the I-007b
# ("実走") half of issue 007; I-007a wrote this script but never ran it
# (`.steering/20260908-paper01-scope-condition/blockers.md` ブロッカー4:
# Ocsai is not in the local source inventory, and the measurement's
# network fetch requires explicit user authorisation before I-007b runs
# it -- `feedback_prompt_approval_not_execution.md`).
#
# **Do not run mutation testing while this script is running** (design-final
# .md / issue 007 Background: "CI を回している最中にリポジトリのファイルを
# 触らない" -- G1's own reflection on a corrupted final CI run).
set -euo pipefail
cd "$(dirname "$0")/../.."

EXP_DIR="experiments/20260908-paper01-scope-condition"
RESULTS_DIR="$EXP_DIR/results"
LOG_FILE="$RESULTS_DIR/run.log"
mkdir -p "$RESULTS_DIR"

# --- PYTHON resolution (both platforms) -------------------------------
if [ -z "${PYTHON:-}" ]; then
  if [ -x ".venv/Scripts/python.exe" ]; then
    PYTHON=".venv/Scripts/python.exe"
  elif [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
  else
    PYTHON="python3"
  fi
fi
export PYTHON
export HF_HUB_OFFLINE=1
export PYTHONUTF8=1
export PYTHONHASHSEED="$(cat "$EXP_DIR/SEED")"

{
  echo "[run.sh] ① PYTHON=$PYTHON PYTHONHASHSEED=$PYTHONHASHSEED HF_HUB_OFFLINE=$HF_HUB_OFFLINE"

  echo "[run.sh] ② --fidelity (design-final.md §6 pin (b)+(c); exit 1=mismatch, exit 2=source-unavailable)"
  "$PYTHON" scripts/paper01_scope_condition.py --fidelity

  echo "[run.sh] ③ --scope, run 1 -> $RESULTS_DIR/scope.json"
  "$PYTHON" scripts/paper01_scope_condition.py --scope

  echo "[run.sh] ④ --scope, run 2 (scratch path) + SHA-256 byte-identity gate"
  SCRATCH_DIR="$(mktemp -d)"
  trap 'rm -rf "$SCRATCH_DIR"' EXIT
  REPEAT_PATH="$SCRATCH_DIR/scope-repeat.json"
  "$PYTHON" scripts/paper01_scope_condition.py --scope --scope-out "$REPEAT_PATH"
  "$PYTHON" "$EXP_DIR/run_gate.py" check-hashes \
    "$RESULTS_DIR/scope.json" "$REPEAT_PATH"

  echo "[run.sh] ⑤ metrics.json (build_metrics.py, read-only extraction)"
  "$PYTHON" "$EXP_DIR/build_metrics.py"

  echo "[run.sh] ⑥ done"
  printf '%s\n' '{"event": "PAPER01_SCOPE_CONDITION_RUN_COMPLETE", "status": "ok"}'
} 2>&1 | tee "$LOG_FILE"

exit "${PIPESTATUS[0]}"

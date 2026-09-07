#!/usr/bin/env bash
# paper01 G1 external audit -- issue 008 one-command reproduction.
#
# ① export PYTHONHASHSEED (from SEED) + HF_HUB_OFFLINE=1
# ② --fidelity            (design-final.md §2; exits != 0 on any mismatch)
# ③ --audit               (2 corpora -> results/external-audit.json)
# ④ --audit again into a scratch path, SHA-256 compare -> exit 1 on mismatch
# ⑤ metrics.json          (build_metrics.py, read-only distillation)
# ⑥ completion marker     (final log line; see run_gate.py's
#                          run_sh_has_completion_marker / PID-survival +
#                          log-tail progress judgement --
#                          feedback_log_tail_completion_marker.md)
#
# Runs on both Windows (Git Bash) and WSL2/Linux. Python is resolved from
# $PYTHON if set, else .venv/Scripts/python.exe (Windows), else
# .venv/bin/python (WSL2/Linux), else a bare python3 on PATH.
#
# ③ alone measures ~1408s (~23min, real qwen3-scale corpora, CPU-only
# encoders); ④ repeats it, so the whole script is ~47min end to end. This
# is expected (design-final.md §3/§4's full corpus x arm x candidate
# battery), not a hang -- monitor by PID survival + this log's tail, never
# by an encoder-library progress bar's most recent (possibly stale) line.
set -euo pipefail
cd "$(dirname "$0")/../.."

EXP_DIR="experiments/20260907-paper01-g1"
RESULTS_DIR="$EXP_DIR/results"
LOG_FILE="$RESULTS_DIR/run.log"
mkdir -p "$RESULTS_DIR"

# --- PYTHON resolution (design-final.md §7 / issue 008: both platforms) ---
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

  echo "[run.sh] ② --fidelity (design-final.md §2, exits != 0 on mismatch)"
  "$PYTHON" scripts/paper01_external_audit.py --fidelity

  echo "[run.sh] ③ --audit, run 1 -> $RESULTS_DIR/external-audit.json"
  "$PYTHON" scripts/paper01_external_audit.py --audit

  echo "[run.sh] ④ --audit, run 2 (scratch path) + SHA-256 byte-identity gate"
  SCRATCH_DIR="$(mktemp -d)"
  trap 'rm -rf "$SCRATCH_DIR"' EXIT
  REPEAT_PATH="$SCRATCH_DIR/external-audit-repeat.json"
  "$PYTHON" scripts/paper01_external_audit.py --audit --audit-out "$REPEAT_PATH"
  "$PYTHON" "$EXP_DIR/run_gate.py" check-hashes \
    "$RESULTS_DIR/external-audit.json" "$REPEAT_PATH"

  echo "[run.sh] ⑤ metrics.json (build_metrics.py, read-only distillation)"
  "$PYTHON" "$EXP_DIR/build_metrics.py"

  echo "[run.sh] ⑥ done"
  printf '%s\n' '{"event": "PAPER01_G1_RUN_COMPLETE", "status": "ok"}'
} 2>&1 | tee "$LOG_FILE"

exit "${PIPESTATUS[0]}"

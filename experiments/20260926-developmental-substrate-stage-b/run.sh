#!/usr/bin/env bash
# developmental substrate Stage B — B-pre (prereg §7) の 1 コマンド再計算。
#
# 入力 = M13 C-proper bank (tracked)。sha256 が prereg §7 の値と一致しなければ計算せず
# b_pre_established=false を返す (「実行できなかった」を「成立」に畳まない)。
# 2 回計算して results.json の byte 一致を確認する (決定性 witness)。
set -euo pipefail
cd "$(dirname "$0")/../.."

EXP_DIR="experiments/20260926-developmental-substrate-stage-b"
RESULTS_DIR="$EXP_DIR/results/b_pre"
mkdir -p "$RESULTS_DIR"

if [ -z "${PYTHON:-}" ]; then
  if [ -x ".venv/Scripts/python.exe" ]; then
    PYTHON=".venv/Scripts/python.exe"
  elif [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
  else
    PYTHON="python3"
  fi
fi
export PYTHONUTF8=1
export PYTHONHASHSEED="$(cat "$EXP_DIR/SEED")"

{
  echo "[run.sh] PYTHON=$PYTHON PYTHONHASHSEED=$PYTHONHASHSEED"
  "$PYTHON" scripts/stage_b_pre.py --out "$RESULTS_DIR/results.json"
  SCRATCH_DIR="$(mktemp -d)"
  trap 'rm -rf "$SCRATCH_DIR"' EXIT
  "$PYTHON" scripts/stage_b_pre.py --out "$SCRATCH_DIR/repeat.json"
  if cmp -s "$RESULTS_DIR/results.json" "$SCRATCH_DIR/repeat.json"; then
    echo "[run.sh] repeat byte-identical"
  else
    echo "[run.sh] repeat MISMATCH" >&2
    exit 1
  fi
  printf '%s\n' '{"event": "STAGE_B_PRE_RUN_COMPLETE", "status": "ok"}'
} 2>&1 | tee "$RESULTS_DIR/run.log"

exit "${PIPESTATUS[0]}"

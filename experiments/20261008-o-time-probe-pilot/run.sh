#!/usr/bin/env bash
# 候補 O_time (時期の評価) — null pilot の機械判定と本走の判定の 1 コマンド再計算 (prereg §9)。
#
# 凍結は 2 段 (prereg §9): pilot は第 1 段 (PILOT-FROZEN) の後、本走は第 2 段 (FROZEN) の後にだけ動く。
#   それぞれの段の manifest の --verify が凍結条件を満たさなければ非 0 で終わり、本 script は (2) で止まる。
#
# 使い方:
#   bash experiments/20261008-o-time-probe-pilot/run.sh pilot   # results/pilot/{records.jsonl,meta.json} の後
#   bash experiments/20261008-o-time-probe-pilot/run.sh main    # results/run/{records.jsonl,meta.json} の後
# 順序:
#   (1) 入力の存在
#   (2) 本登録の manifest の照合 (段ごと。コード・test・certification・見取り図・fixture 表・prereg が凍結時と
#       byte 一致し、結び付きが成り立ち、その段の凍結条件を満たす。main は pilot の GO・driver の certification も要る。違えば止まる)
#   (3) pilot: 機械判定 (GO と R / STOP)。main: pilot の GO と R を読み、判定する (GO でなければ判定しない)
#   certification は凍結時のものを読むだけで、実走後に変異 harness を回し直さない。
# set -e と個別行で、検査より先に本計算が走らない。2 回計算して byte 一致を確かめる。
set -euo pipefail
cd "$(dirname "$0")/../.."

EXP_DIR="experiments/20261008-o-time-probe-pilot"
CERT="$EXP_DIR/results/certification.json"
SKETCH="$EXP_DIR/results/sketch.json"
GATE="$EXP_DIR/results/pilot/gate.json"
STAGE="${1:-}"

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

case "$STAGE" in
  pilot) RUN_DIR="$EXP_DIR/results/pilot" ;;
  main) RUN_DIR="$EXP_DIR/results/run" ;;
  *) echo "usage: run.sh pilot|main" >&2; exit 2 ;;
esac
test -f "$RUN_DIR/records.jsonl"
test -f "$RUN_DIR/meta.json"
"$PYTHON" scripts/o_time_probe_manifest.py --verify --stage "$STAGE"
SCRATCH_DIR="$(mktemp -d)"
trap 'rm -rf "$SCRATCH_DIR"' EXIT
if [ "$STAGE" = "pilot" ]; then
  "$PYTHON" scripts/o_time_probe_pilot_gate.py --records "$RUN_DIR/records.jsonl" \
    --meta "$RUN_DIR/meta.json" --cert "$CERT" --sketch "$SKETCH" --out "$GATE"
  "$PYTHON" scripts/o_time_probe_pilot_gate.py --records "$RUN_DIR/records.jsonl" \
    --meta "$RUN_DIR/meta.json" --cert "$CERT" --sketch "$SKETCH" --out "$SCRATCH_DIR/repeat.json"
  cmp -s "$GATE" "$SCRATCH_DIR/repeat.json"
else
  test -f "$GATE"
  "$PYTHON" scripts/o_time_probe_scorer.py --records "$RUN_DIR/records.jsonl" \
    --meta "$RUN_DIR/meta.json" --cert "$CERT" --gate "$GATE" --out "$RUN_DIR/results.json"
  "$PYTHON" scripts/o_time_probe_scorer.py --records "$RUN_DIR/records.jsonl" \
    --meta "$RUN_DIR/meta.json" --cert "$CERT" --gate "$GATE" --out "$SCRATCH_DIR/repeat.json"
  cmp -s "$RUN_DIR/results.json" "$SCRATCH_DIR/repeat.json"
fi
echo "[run.sh] $STAGE: repeat byte-identical"

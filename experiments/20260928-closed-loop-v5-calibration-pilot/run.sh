#!/usr/bin/env bash
# 閉ループ v5 前段 — 較正 pilot の検証・測定・写像の 1 コマンド再計算 (pilot prereg §8)。
#
# 実走 (GPU、別途 user 裁定) が results/run/{records.jsonl,meta.json} を書いた後に使う。
# 順序: (1) 凍結 v2 manifest の照合 (2) 凍結 v4 manifest の照合 (本登録が import する v4 の battery / sim が
#       凍結時と byte 一致) (3) 本登録の manifest の照合 (写像のコード・test・certification・見取り図・prereg が
#       凍結時と byte 一致し、certification と見取り図が現在のコードに結び付いていること。違えば止まる)
#       (4) 検証 → 測定 → 写像。certification は凍結時のものを読むだけで、実走後に変異 harness を回し直さない。
#       set -e と個別行で、検査より先に本計算が走らない。
# 2 回計算して selection.json の byte 一致を確認する。所要は 10 時間を超えうる (prereg §10 の実測。セッションに依らない process で走らせる)。
set -euo pipefail
cd "$(dirname "$0")/../.."

EXP_DIR="experiments/20260928-closed-loop-v5-calibration-pilot"
RUN_DIR="$EXP_DIR/results/run"
CERT="$EXP_DIR/results/pilot_mutation.json"

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

test -f "$RUN_DIR/records.jsonl"
test -f "$RUN_DIR/meta.json"
"$PYTHON" scripts/skill_lever_manifest.py --verify
"$PYTHON" scripts/closed_loop_manifest.py --verify
"$PYTHON" scripts/closed_loop_v5_manifest.py --verify
"$PYTHON" -m scripts.closed_loop_v5_select --records "$RUN_DIR/records.jsonl" \
  --meta "$RUN_DIR/meta.json" --cert "$CERT" --out "$RUN_DIR/selection.json"
SCRATCH_DIR="$(mktemp -d)"
trap 'rm -rf "$SCRATCH_DIR"' EXIT
"$PYTHON" -m scripts.closed_loop_v5_select --records "$RUN_DIR/records.jsonl" \
  --meta "$RUN_DIR/meta.json" --cert "$CERT" --out "$SCRATCH_DIR/repeat.json"
cmp -s "$RUN_DIR/selection.json" "$SCRATCH_DIR/repeat.json"
echo "[run.sh] repeat byte-identical"

#!/usr/bin/env bash
# 探索を身体側へ (b) 歩行 → decode 条件 — 較正 pilot の検証・測定・写像の 1 コマンド再計算 (pilot prereg §11)。
#
# status: 凍結しなかった (door-close、2026-09-30、user 裁定 DU-4。prereg の冒頭と §13・§16)。
#   本登録の manifest の --verify は凍結条件を満たさないことを報告して止まるので、本 script は (4) で止まる。
#   以下は、凍結していれば使う予定だった手順の記録である。
#
# 実走 (GPU、別途 user 裁定) が results/run/{records.jsonl,meta.json} を書いた後に使う。
# 順序:
#   (1) 凍結 v2 manifest の照合
#   (2) 凍結 v4 manifest の照合 (本登録が import する v4 の battery / sim が凍結時と byte 一致)
#   (3) 凍結 v5 manifest の照合 (本登録が import する v5 の scorer / sim / 写像が凍結時と byte 一致)
#   (4) 本登録の manifest の照合 (写像のコード・test・certification・見取り図・prereg が凍結時と byte 一致し、
#       certification と見取り図が現在のコードに結び付いていること。違えば止まる)
#   (5) 検証 → 測定 → 写像。certification は凍結時のものを読むだけで、実走後に変異 harness を回し直さない。
# set -e と個別行で、検査より先に本計算が走らない。
# 2 回計算して selection.json の byte 一致を確認する。候補が本確認に進むと数時間を超えうる
# (セッションに依らない process で走らせる)。
set -euo pipefail
cd "$(dirname "$0")/../.."

EXP_DIR="experiments/20260930-body-walk-calibration-pilot"
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
"$PYTHON" scripts/body_walk_manifest.py --verify
"$PYTHON" -m scripts.body_walk_select --records "$RUN_DIR/records.jsonl" \
  --meta "$RUN_DIR/meta.json" --cert "$CERT" --out "$RUN_DIR/selection.json"
SCRATCH_DIR="$(mktemp -d)"
trap 'rm -rf "$SCRATCH_DIR"' EXIT
"$PYTHON" -m scripts.body_walk_select --records "$RUN_DIR/records.jsonl" \
  --meta "$RUN_DIR/meta.json" --cert "$CERT" --out "$SCRATCH_DIR/repeat.json"
cmp -s "$RUN_DIR/selection.json" "$SCRATCH_DIR/repeat.json"
echo "[run.sh] repeat byte-identical"

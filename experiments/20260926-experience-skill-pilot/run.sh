#!/usr/bin/env bash
# 経験由来 Skill pilot — 判定の 1 コマンド再計算 (prereg v3 §8)。
#
# 実走 (GPU、別途 user 裁定) が results/run/{samples.jsonl,meta.json} を書いた後に使う。
# 順序: (1) 凍結 v2 manifest の照合 (v3 が import する v2 の純粋関数・battery が v2 凍結時と byte 一致)
#       (2) 凍結 v3 manifest の照合 (判定コード・test・certification・power 表・prereg が凍結時と byte 一致し、
#           certification と power 表が現在のコードに結び付いていること。違えば止まる)
#       (3) 判定。certification は凍結時のものを読むだけで、実走後に変異 harness を回し直さない。
#       set -e と個別行で、検査より先に本計算が走らない。
# 2 回計算して results.json の byte 一致を確認する。
set -euo pipefail
cd "$(dirname "$0")/../.."

EXP_DIR="experiments/20260926-experience-skill-pilot"
RUN_DIR="$EXP_DIR/results/run"
CERT="$EXP_DIR/results/v3_mutation.json"

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

test -f "$RUN_DIR/samples.jsonl"
test -f "$RUN_DIR/meta.json"
"$PYTHON" scripts/skill_lever_manifest.py --verify
"$PYTHON" scripts/skill_experience_manifest.py --verify
"$PYTHON" scripts/skill_experience_evaluate.py --records "$RUN_DIR/samples.jsonl" \
  --meta "$RUN_DIR/meta.json" --cert "$CERT" --out "$RUN_DIR/results.json"
SCRATCH_DIR="$(mktemp -d)"
trap 'rm -rf "$SCRATCH_DIR"' EXIT
"$PYTHON" scripts/skill_experience_evaluate.py --records "$RUN_DIR/samples.jsonl" \
  --meta "$RUN_DIR/meta.json" --cert "$CERT" --out "$SCRATCH_DIR/repeat.json"
cmp -s "$RUN_DIR/results.json" "$SCRATCH_DIR/repeat.json"
echo "[run.sh] repeat byte-identical"

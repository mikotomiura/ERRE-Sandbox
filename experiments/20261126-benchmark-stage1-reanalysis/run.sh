#!/usr/bin/env bash
# 判別性 gate 段 1 — 既存記録の再解析の 1 コマンド再計算 (rules.md)。
# 入力の sha256 を照合し (不一致なら非 0 で止まる)、2 回計算して byte 一致を確かめる。
# 凍結 dir の import で __pycache__ を作らないよう PYTHONDONTWRITEBYTECODE=1 を付ける。
set -euo pipefail
cd "$(dirname "$0")/../.."

EXP_DIR="experiments/20261126-benchmark-stage1-reanalysis"
if [ -z "${PYTHON:-}" ]; then
  if [ -x ".venv/Scripts/python.exe" ]; then
    PYTHON=".venv/Scripts/python.exe"
  else
    PYTHON=".venv/bin/python"
  fi
fi
export PYTHONDONTWRITEBYTECODE=1

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
"$PYTHON" -m scripts.benchmark_stage1_reanalysis --out "$EXP_DIR/results"
"$PYTHON" -m scripts.benchmark_stage1_reanalysis --out "$TMP" > /dev/null
cmp "$EXP_DIR/results/stage1.json" "$TMP/stage1.json"
echo "byte-identical: $EXP_DIR/results/stage1.json"

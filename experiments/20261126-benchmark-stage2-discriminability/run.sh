#!/usr/bin/env bash
# 判別性 gate 段 2 — 見取り図 (CPU)。2 回計算して byte 一致を確かめる。
# 使い方: bash experiments/20261126-benchmark-stage2-discriminability/run.sh sketch
set -euo pipefail
cd "$(dirname "$0")/../.."
D=experiments/20261126-benchmark-stage2-discriminability
export PYTHONDONTWRITEBYTECODE=1
case "${1:-sketch}" in
  sketch)
    T=$(mktemp -d)
    uv run python -m scripts.benchmark_stage2_sim --out "$T/a"
    uv run python -m scripts.benchmark_stage2_sim --out "$T/b"
    cmp "$T/a/sketch.json" "$T/b/sketch.json"
    cmp "$T/a/fixture_diffs.json" "$T/b/fixture_diffs.json"
    cp "$T/a/sketch.json" "$T/a/fixture_diffs.json" "$D/results/"
    echo "SKETCH OK (byte-identical)"
    ;;
  verify)
    uv run python -m scripts.benchmark_stage2_manifest --verify --stage pilot
    ;;
  *) echo "usage: run.sh {sketch|verify}" >&2; exit 2 ;;
esac

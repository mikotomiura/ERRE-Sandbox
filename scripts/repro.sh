#!/usr/bin/env bash
# ECL v0 golden — one-command offline reproducibility check (Issue 005).
#
# 使い方:
#   bash scripts/repro.sh
#
# 委託先の MacBook が Ollama 無し・offline 単独で committed golden を再生し、
# ecl_trace_checksum が manifest.json と byte 一致するか検証する
# (design-final.md §論点5 の cross-machine 再現性契約)。
#
# 決定性: LLM は記録済 Plane 2 の replay (inner_invocations == 0)、embedding は
# 定数ベクトルの in-memory mock ゆえ live 推論バックエンドを必要としない。
# reproducibility-discipline: seed 固定 (handoff.GOLDEN_SEED) / 1 コマンド再現。

set -uo pipefail

PYTHON=".venv/Scripts/python.exe"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON=".venv/bin/python"
fi
if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: Python venv not found. Run 'uv sync --extra eval' first." >&2
    exit 2
fi

# ERRE_ZONE_BIAS_P を manifest env pin と同値に固定 (未 pin 非決定源を塞ぐ)。
export ERRE_ZONE_BIAS_P="${ERRE_ZONE_BIAS_P:-0.1}"

exec "$PYTHON" scripts/ecl_v0_golden.py --verify \
    --golden-dir tests/fixtures/ecl_v0_golden

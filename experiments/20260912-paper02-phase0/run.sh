#!/usr/bin/env bash
# 論文 02 Phase 0 — feasibility pilot (1 コマンド再走)
#
# 前提: Ollama が起動していて llama3.1:8b と qwen3:8b が pull 済であること。
#
# 注意: これは byte 一致の replay ではない。draw を保存しない設計なので、
#       再走すると新しい draw が引かれる (env.md「再現性の限界」参照)。
set -euo pipefail
cd "$(dirname "$0")/../.."

uv run python scripts/paper02_phase0_pilot.py --model llama3.1:8b --role primary
uv run python scripts/paper02_phase0_pilot.py --model qwen3:8b   --role reference

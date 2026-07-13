#!/usr/bin/env bash
# M13 Layer2 ミラー・シム real 封印実走（construction、measurement でない）
# reproducibility-discipline: seed 固定 / env pin / 1 コマンド再現。
# 実行機 = G-GEAR（Windows native Ollama, port 11434）。Windows native + PYTHONUTF8=1 で実行。
# construction spend であって measurement spend でない（R-budget=0、floor/verdict/scorer/magnitude/divergence 非 emit）。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# --- env pins（2026-07-13 実測、G-GEAR）---
QWEN3_DIGEST="sha256:500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
OLLAMA_VERSION="0.31.2"
UV_LOCK_SHA256="9cc70f9dc5d61f6c74c08dee4dd73815993861022a80781a75ef5d873860c0f7"
VRAM_GB="16.0"   # RTX 5060 Ti 16GB
OUT_DIR="tests/fixtures/m2_layer2_live_golden"
RUN_ID="m2-layer2-live-golden"

export PYTHONUTF8=1

# --- Ollama health ---
curl -s http://localhost:11434/api/version

# --- capture（--self-other = Layer2-on、think=False は harness 強制、seed=0、N=3、horizon=12）---
python scripts/m4_society_live_capture.py --capture --self-other \
  --out-dir "$OUT_DIR" \
  --run-id "$RUN_ID" \
  --seed 0 \
  --qwen3-model-digest "$QWEN3_DIGEST" \
  --ollama-version "$OLLAMA_VERSION" \
  --vram-gb "$VRAM_GB" \
  --uv-lock-sha256 "$UV_LOCK_SHA256"

# --- Windows replay-verify（Ollama-free、byte-parity + inner_invocations=0）---
python scripts/m4_society_live_capture.py --verify --artifact-dir "$OUT_DIR"

# --- WSL cross-platform byte-parity は別途 experiments/.../wsl-verify.sh で実測 ---
echo "capture + Windows verify done. Next: WSL --verify for cross-platform byte-parity."

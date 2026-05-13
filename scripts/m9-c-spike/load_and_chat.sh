#!/usr/bin/env bash
# Load real Kant adapter into SGLang + chat round-trip — CS-6 / CS-9.
#
# Validates two acceptance criteria of Phase K-β:
#   1. PEFT directory direct load (CS-6) — POST /load_lora_adapter returns
#      success=true without HTTP 4xx/5xx
#   2. Kant文体差別化 (CS-9 inversion) — mock_kant_r8 (identity transform)
#      vs kant_r8_real (trained) で同一プロンプトの応答が異なる
#
# Pre-conditions:
#   * SGLang 0.5.10.post1 serving on localhost:30000 with --enable-lora
#   * /root/erre-sandbox/checkpoints/kant_r8_real/ exists (post-training)
#   * /root/erre-sandbox/checkpoints/mock_kant_r8/ exists (K-α artefact)
#
# Output: stdout の chat completion JSON 2 件 (mock + real)
set -euo pipefail

SERVER_URL="${SERVER_URL:-http://localhost:30000}"
PROMPT="${PROMPT:-純粋理性と実践理性の関係を、あなた自身の語り口で簡潔に説明してください。}"
MOCK_PATH="${MOCK_PATH:-/root/erre-sandbox/checkpoints/mock_kant_r8}"
REAL_PATH="${REAL_PATH:-/root/erre-sandbox/checkpoints/kant_r8_real}"
OUT_DIR="${OUT_DIR:-/mnt/c/ERRE-Sand_Box/.steering/20260508-m9-c-spike/k-beta-logs}"

mkdir -p "${OUT_DIR}"

echo "=== 1. /load_lora_adapter mock_kant_r8 ==="
curl -s -X POST "${SERVER_URL}/load_lora_adapter" \
    -H "Content-Type: application/json" \
    -d "{\"lora_name\": \"mock_kant_r8\", \"lora_path\": \"${MOCK_PATH}\"}" \
    | tee "${OUT_DIR}/load_mock.json" | jq

echo ""
echo "=== 2. /load_lora_adapter kant_r8_real ==="
curl -s -X POST "${SERVER_URL}/load_lora_adapter" \
    -H "Content-Type: application/json" \
    -d "{\"lora_name\": \"kant_r8_real\", \"lora_path\": \"${REAL_PATH}\"}" \
    | tee "${OUT_DIR}/load_real.json" | jq

echo ""
echo "=== 3. chat with mock_kant_r8 (CS-9 identity baseline) ==="
curl -s -X POST "${SERVER_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "$(jq -nc --arg p "${PROMPT}" '
      {
        model: "mock_kant_r8",
        messages: [{role: "user", content: $p}],
        max_tokens: 300,
        temperature: 0.7,
        seed: 0
      }
    ')" | tee "${OUT_DIR}/chat_mock.json" | jq -r '.choices[0].message.content // "ERROR: see chat_mock.json"'

echo ""
echo "=== 4. chat with kant_r8_real (Kant文体差別化) ==="
curl -s -X POST "${SERVER_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "$(jq -nc --arg p "${PROMPT}" '
      {
        model: "kant_r8_real",
        messages: [{role: "user", content: $p}],
        max_tokens: 300,
        temperature: 0.7,
        seed: 0
      }
    ')" | tee "${OUT_DIR}/chat_real.json" | jq -r '.choices[0].message.content // "ERROR: see chat_real.json"'

echo ""
echo "=== artefacts saved to ${OUT_DIR}/ ==="
ls -la "${OUT_DIR}/load_mock.json" "${OUT_DIR}/load_real.json" "${OUT_DIR}/chat_mock.json" "${OUT_DIR}/chat_real.json"

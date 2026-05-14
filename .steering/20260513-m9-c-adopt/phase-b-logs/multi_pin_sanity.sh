#!/bin/bash
# Phase B Step 4 — 3 adapter multi-pin load + chat round trip sanity.
# - Loads kant_r4_real, kant_r8_real, kant_r16_real into SGLang
# - Sends the same prompt to each via /v1/chat/completions
# - Captures responses to artifacts/ for verbatim comparison
set -e

SERVER=http://localhost:30000
PROMPT="Was ist die Bedingung der Möglichkeit der Erfahrung?"
ARTDIR=/mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/multi_pin_artifacts
mkdir -p "${ARTDIR}"

echo "=== health ==="
curl -sf "${SERVER}/health" | head -c 200; echo
curl -sf "${SERVER}/get_server_info" | head -c 500; echo
echo

echo "=== loading 3 adapters ==="
for r in 4 8 16; do
  name="kant_r${r}_real"
  path="/root/erre-sandbox/checkpoints/${name}"
  echo "--- load ${name} ---"
  resp=$(curl -s -X POST "${SERVER}/load_lora_adapter" \
    -H "Content-Type: application/json" \
    -d "{\"lora_name\": \"${name}\", \"lora_path\": \"${path}\"}")
  echo "${resp}" | tee "${ARTDIR}/load_${name}.json"
  echo
done

echo "=== chat round trip per rank ==="
for r in 4 8 16; do
  name="kant_r${r}_real"
  echo "--- chat ${name} ---"
  curl -s -X POST "${SERVER}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"${name}\", \"messages\": [{\"role\": \"user\", \"content\": \"${PROMPT}\"}], \"max_tokens\": 200, \"temperature\": 0.6, \"seed\": 0}" \
    | tee "${ARTDIR}/chat_${name}.json"
  echo
done

echo "=== response text (per rank) ==="
for r in 4 8 16; do
  name="kant_r${r}_real"
  echo "--- ${name} text ---"
  cat "${ARTDIR}/chat_${name}.json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('choices',[{}])[0].get('message',{}).get('content','ERROR'))" || echo "PARSE_ERROR"
  echo
done

echo "=== artefacts ==="
ls -la "${ARTDIR}/"

#!/usr/bin/env bash
# m9-c-adopt Plan B eval shard sequence — 4 runs sequentially in WSL.
#
# Runs tier_b_pilot.py for:
#   1. LoRA-on run0  (kant_r8v3, ~1.5h)
#   2. LoRA-on run1  (kant_r8v3, ~1.5h)
#   3. no-LoRA run0  (base Qwen3-8B, ~1h)
#   4. no-LoRA run1  (base Qwen3-8B, ~1h)
#
# Total ~5h GPU. Run from WSL2 with SGLang already up on port 30000.
#
# Usage:
#   nohup bash /mnt/c/ERRE-Sand_Box/scripts/m9-c-adopt/run_plan_b_eval_sequence.sh \
#       > /mnt/c/ERRE-Sand_Box/.steering/20260516-m9-c-adopt-plan-b-eval-gen/eval-sequence.log 2>&1 &

set -uo pipefail

REPO=/mnt/c/ERRE-Sand_Box
PYTHON="${REPO}/.venv/Scripts/python.exe"
if [[ ! -x "$PYTHON" ]]; then
    # If invoked via Linux venv (uncommon — clients are Windows-side),
    # fall back to /root/erre-sandbox/.venv.
    PYTHON=/root/erre-sandbox/.venv/bin/python
fi

OUT=${REPO}/data/eval/m9-c-adopt-plan-b-verdict
mkdir -p "$OUT"

run_pilot() {
    local label="$1"
    shift
    echo ""
    echo "==[ $label ]==  $(date -Iseconds)"
    if "$PYTHON" "${REPO}/scripts/m9-c-adopt/tier_b_pilot.py" "$@"; then
        echo "  [PASS] $label  $(date -Iseconds)"
    else
        echo "  [FAIL] $label exit=$?  $(date -Iseconds)"
        return 1
    fi
}

# Run 1: LoRA-on run0
run_pilot "LoRA-on run0" \
    --persona kant --rank 8 --run-idx 0 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --adapter-name kant_r8v3 \
    --output "${OUT}/kant_r8v3_run0_stim.duckdb" \
    || exit 1

# Run 2: LoRA-on run1
run_pilot "LoRA-on run1" \
    --persona kant --rank 8 --run-idx 1 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --adapter-name kant_r8v3 \
    --output "${OUT}/kant_r8v3_run1_stim.duckdb" \
    || exit 1

# Run 3: no-LoRA run0
run_pilot "no-LoRA run0" \
    --persona kant --no-lora-control --rank 0 --run-idx 0 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --output "${OUT}/kant_planb_nolora_run0_stim.duckdb" \
    || exit 1

# Run 4: no-LoRA run1
run_pilot "no-LoRA run1" \
    --persona kant --no-lora-control --rank 0 --run-idx 1 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --output "${OUT}/kant_planb_nolora_run1_stim.duckdb" \
    || exit 1

echo ""
echo "==[ ALL 4 RUNS COMPLETE ]==  $(date -Iseconds)"
echo "Output dir: ${OUT}"
ls -la "$OUT"

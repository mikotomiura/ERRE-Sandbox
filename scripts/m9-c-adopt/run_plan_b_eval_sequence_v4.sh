#!/usr/bin/env bash
# m9-c-adopt Plan B v4 eval shard sequence — 4 runs sequentially.
#
# Runs tier_b_pilot.py for:
#   1. LoRA-on run0  (kant_r8v4 = PR-2 `.mean()` reduce 後 retrain、~6 min)
#   2. LoRA-on run1  (kant_r8v4、~6 min)
#   3. no-LoRA run0  (base Qwen3-8B、~6 min)
#   4. no-LoRA run1  (base Qwen3-8B、~6 min)
#
# Total ~25-30 min. Run from **Git Bash on Windows** (project root cwd)
# with SGLang already up on port 30000 in WSL2
# (launch_sglang_plan_b_v4.sh で kant_r8v4 を load 済、Windows から
#  http://127.0.0.1:30000 へ到達可能を pre-check 済).
#
# Windows python.exe を Git Bash 経由で呼ぶことで、tier_b_pilot.py の
# path 引数が Windows ネイティブ path で解釈される (WSL2 binfmt_misc
# interop 経由だと /mnt/c/... の auto path translation が効かない場合あり、
# v3 で観測).
#
# 出力 path は v3 verdict shard (`data/eval/m9-c-adopt-plan-b-verdict/`)
# と並列共存 (forensic 完全性のため v3 shard は削除しない).
# no-LoRA control 2 runs も v4 session で再採取 (apples-to-apples
# temporal control + same SGLang session で forensic 一貫性).
#
# Usage (from project root in Git Bash):
#   nohup bash scripts/m9-c-adopt/run_plan_b_eval_sequence_v4.sh \
#       > .steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/eval-sequence-v4.log 2>&1 &

set -uo pipefail

PY=.venv/Scripts/python.exe
SCR=scripts/m9-c-adopt
OUT=data/eval/m9-c-adopt-plan-b-verdict-v4
mkdir -p "$OUT"

run_pilot() {
    local label="$1"
    shift
    echo ""
    echo "==[ $label ]==  $(date -Iseconds)"
    if "$PY" "${SCR}/tier_b_pilot.py" "$@"; then
        echo "  [PASS] $label  $(date -Iseconds)"
    else
        echo "  [FAIL] $label exit=$?  $(date -Iseconds)"
        return 1
    fi
}

# Run 1: LoRA-on run0 (kant_r8v4)
run_pilot "LoRA-on run0" \
    --persona kant --rank 8 --run-idx 0 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --adapter-name kant_r8v4 \
    --output "${OUT}/kant_r8v4_run0_stim.duckdb" \
    || exit 1

# Run 2: LoRA-on run1 (kant_r8v4)
run_pilot "LoRA-on run1" \
    --persona kant --rank 8 --run-idx 1 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --adapter-name kant_r8v4 \
    --output "${OUT}/kant_r8v4_run1_stim.duckdb" \
    || exit 1

# Run 3: no-LoRA run0 (base Qwen3-8B、v4 session で再採取)
run_pilot "no-LoRA run0" \
    --persona kant --no-lora-control --rank 0 --run-idx 0 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --output "${OUT}/kant_planb_nolora_run0_stim.duckdb" \
    || exit 1

# Run 4: no-LoRA run1 (base Qwen3-8B、v4 session で再採取)
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

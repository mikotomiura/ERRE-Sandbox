#!/usr/bin/env bash
# m9-c-adopt Plan B v4 — post-eval-shard pipeline (kant_r8v4):
# 1. Shard validation (validate_multiturn_shards.py)
# 2. 4-encoder rescore (rescore_vendi_alt_kernel.py × MPNet / E5-large / lex5 / BGE-M3)
# 3. Burrows per-condition (compute_burrows_delta.py × LoRA-on / no-LoRA)
# 4. ICC single-condition (compute_big5_icc.py × LoRA-on; no-LoRA proxy via v2 baseline ICC)
# 5. Axis aggregation (aggregate_plan_b_axes.py)
# 6. Verdict (da14_verdict_plan_b.py)
#
# Run after all 4 v4 eval shards are present in
# data/eval/m9-c-adopt-plan-b-verdict-v4/.
#
# 出力 base directory は本 PR-4 steering directory に変更
# (.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/)、全 output
# file 名に `*-v4-*` suffix を付与 (v3 と並列共存).

set -uo pipefail

REPO=/c/ERRE-Sand_Box
TASK=.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict
SHARDS=data/eval/m9-c-adopt-plan-b-verdict-v4
ALLOWLIST=.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json
PY=.venv/Scripts/python.exe
SCR=scripts/m9-c-adopt

V2_SHARDS_GLOB="$SHARDS/kant_r8v4_run*_stim.duckdb"
NOLORA_SHARDS_GLOB="$SHARDS/kant_planb_nolora_run*_stim.duckdb"

LOG="$TASK/post-eval-pipeline-v4.log"
mkdir -p "$(dirname "$LOG")"

step() {
    local label="$1"; shift
    echo ""
    echo "==[ $label $(date -Iseconds) ]==" | tee -a "$LOG"
    if "$@" 2>&1 | tee -a "$LOG"; then
        echo "  [PASS] $label" | tee -a "$LOG"
    else
        local code=$?
        echo "  [FAIL] $label exit=$code" | tee -a "$LOG"
        return $code
    fi
}

# ----- 1. Shard validation -----
step "validate LoRA-on shards" \
    "$PY" "$SCR/validate_multiturn_shards.py" \
    --persona kant --focal-target 300 \
    --shards-glob "$V2_SHARDS_GLOB" \
    --output "$TASK/validation-kant-r8v4.json"

step "validate no-LoRA shards" \
    "$PY" "$SCR/validate_multiturn_shards.py" \
    --persona kant --focal-target 300 \
    --shards-glob "$NOLORA_SHARDS_GLOB" \
    --output "$TASK/validation-kant-planb-nolora-v4.json"

# ----- 2. 4-encoder rescore -----
for spec in \
    "sentence-transformers/all-mpnet-base-v2 semantic mpnet" \
    "intfloat/multilingual-e5-large semantic e5large" \
    "lexical_5gram lexical_5gram lex5" \
    "BAAI/bge-m3 semantic bgem3"; do
    set -- $spec
    encoder="$1"; ktype="$2"; suffix="$3"
    step "rescore $suffix" \
        "$PY" "$SCR/rescore_vendi_alt_kernel.py" \
        --encoder "$encoder" \
        --kernel-type "$ktype" \
        --allowlist-path "$ALLOWLIST" \
        --v2-shards "$SHARDS/kant_r8v4_run0_stim.duckdb" \
                    "$SHARDS/kant_r8v4_run1_stim.duckdb" \
        --nolora-shards "$SHARDS/kant_planb_nolora_run0_stim.duckdb" \
                        "$SHARDS/kant_planb_nolora_run1_stim.duckdb" \
        --output "$TASK/da14-rescore-${suffix}-plan-b-kant-v4.json"
done

# ----- 3. Burrows per-condition -----
step "Burrows LoRA-on" \
    "$PY" "$SCR/compute_burrows_delta.py" \
    --persona kant \
    --shards-glob "$V2_SHARDS_GLOB" \
    --window-size 100 \
    --output "$TASK/tier-b-plan-b-kant-r8v4-burrows.json"

step "Burrows no-LoRA" \
    "$PY" "$SCR/compute_burrows_delta.py" \
    --persona kant \
    --shards-glob "$NOLORA_SHARDS_GLOB" \
    --window-size 100 \
    --output "$TASK/tier-b-plan-b-kant-planb-nolora-v4-burrows.json"

# ----- 4. ICC single-condition (LoRA-on, kant_r8v4 adapter) -----
step "ICC kant_r8v4" \
    "$PY" "$SCR/compute_big5_icc.py" \
    --persona kant \
    --shards-glob "$V2_SHARDS_GLOB" \
    --responder sglang \
    --sglang-host http://127.0.0.1:30000 \
    --sglang-adapter kant_r8v4 \
    --temperature 0.7 \
    --window-size 100 \
    --output "$TASK/tier-b-plan-b-kant-r8v4-icc.json"

# ----- 5. Axis aggregation -----
step "aggregate axes" \
    "$PY" "$SCR/aggregate_plan_b_axes.py" \
    --burrows-v2 "$TASK/tier-b-plan-b-kant-r8v4-burrows.json" \
    --burrows-nolora "$TASK/tier-b-plan-b-kant-planb-nolora-v4-burrows.json" \
    --icc-v2 "$TASK/tier-b-plan-b-kant-r8v4-icc.json" \
    --v2-shards "$SHARDS/kant_r8v4_run0_stim.duckdb" "$SHARDS/kant_r8v4_run1_stim.duckdb" \
    --nolora-shards "$SHARDS/kant_planb_nolora_run0_stim.duckdb" "$SHARDS/kant_planb_nolora_run1_stim.duckdb" \
    --eval-log "$TASK/eval-sequence-v4.log" \
    --out-burrows "$TASK/da14-burrows-plan-b-kant-v4.json" \
    --out-icc "$TASK/da14-icc-plan-b-kant-v4.json" \
    --out-throughput "$TASK/da14-throughput-plan-b-kant-v4.json"

# ----- 6. Verdict -----
step "verdict aggregator" \
    "$PY" "$SCR/da14_verdict_plan_b.py" \
    --rescore "$TASK/da14-rescore-mpnet-plan-b-kant-v4.json" \
    --rescore "$TASK/da14-rescore-e5large-plan-b-kant-v4.json" \
    --rescore "$TASK/da14-rescore-lex5-plan-b-kant-v4.json" \
    --rescore "$TASK/da14-rescore-bgem3-plan-b-kant-v4.json" \
    --burrows "$TASK/da14-burrows-plan-b-kant-v4.json" \
    --icc "$TASK/da14-icc-plan-b-kant-v4.json" \
    --throughput "$TASK/da14-throughput-plan-b-kant-v4.json" \
    --allowlist "$ALLOWLIST" \
    --output-json "$TASK/da14-verdict-plan-b-kant-v4.json" \
    --output-md "$TASK/da14-verdict-plan-b-kant-v4.md"

echo ""
echo "==[ POST-EVAL PIPELINE COMPLETE $(date -Iseconds) ]==" | tee -a "$LOG"
cat "$TASK/da14-verdict-plan-b-kant-v4.md"

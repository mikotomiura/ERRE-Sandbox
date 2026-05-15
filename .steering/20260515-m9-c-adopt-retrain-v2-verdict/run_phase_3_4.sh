#!/bin/bash
# Phase 3-4 execution: multi-turn pilot recapture + DA-14 verdict for retrain v2.
# Assumes training has exited (kant_r8_v2 checkpoint available).
# Runs SGLang under WSL2 + consumers/matrix under Windows-native python.
set -e

# === Configuration ===
REPO_WIN="C:/ERRE-Sand_Box"
REPO_WSL="/mnt/c/ERRE-Sand_Box"
TASK_DIR_REL=".steering/20260515-m9-c-adopt-retrain-v2-verdict"
TASK_DIR_WSL="${REPO_WSL}/${TASK_DIR_REL}"
MATRIX_INPUT_DIR="${TASK_DIR_REL}/matrix-inputs"
PREV_TASK=".steering/20260514-m9-c-adopt-pilot-multiturn"

ADAPTER_NAME="kant_r8_v2"
PILOT_OUT_DIR="data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2"
SGLANG_HOST="http://127.0.0.1:30000"
PYBIN_WIN=".venv/Scripts/python.exe"

mkdir -p "${PILOT_OUT_DIR}" "${MATRIX_INPUT_DIR}"

# Use root-level adapter (trainer.model.save_pretrained at end of training,
# byte-identical to checkpoint-4000)
ADAPTER_DIR="data/lora/m9-c-adopt-v2/kant_r8_v2"
if [ ! -f "${ADAPTER_DIR}/adapter_model.safetensors" ]; then
    echo "ERROR: no adapter_model.safetensors at ${ADAPTER_DIR}"
    exit 1
fi
LATEST_CKPT_WSL="${REPO_WSL}/${ADAPTER_DIR}"
echo "[phase3] using adapter: ${ADAPTER_DIR}"

# === Step 1: Start SGLang in WSL background ===
echo "[phase3] launching SGLang in WSL (max-lora-rank 8)"
wsl -d Ubuntu-22.04 -- bash -c 'bash /mnt/c/ERRE-Sand_Box/.steering/20260515-m9-c-adopt-retrain-v2-verdict/launch_sglang_wsl.sh' 2>&1
SGLANG_PID=$(cat "${TASK_DIR_REL}/sglang.pid")
echo "[phase3] SGLang WSL PID: ${SGLANG_PID}"

# === Step 2: Wait for SGLang ready ===
echo "[phase3] waiting for SGLang /health (up to 5 min)..."
for i in $(seq 1 60); do
    if curl -sf "${SGLANG_HOST}/health" > /dev/null 2>&1; then
        echo "[phase3] SGLang ready at attempt ${i}"
        break
    fi
    sleep 5
done

if ! curl -sf "${SGLANG_HOST}/health" > /dev/null 2>&1; then
    echo "[phase3] FATAL: SGLang not ready after 5 min — abort"
    exit 1
fi

# === Step 3: Load LoRA adapter ===
echo "[phase3] loading adapter ${ADAPTER_NAME} from ${LATEST_CKPT_WSL}"
LOAD_RESP=$(curl -s -X POST "${SGLANG_HOST}/load_lora_adapter" \
    -H "Content-Type: application/json" \
    -d "{\"lora_name\": \"${ADAPTER_NAME}\", \"lora_path\": \"${LATEST_CKPT_WSL}\"}")
echo "${LOAD_RESP}" | tee "${TASK_DIR_REL}/sglang-load-${ADAPTER_NAME}.json"
echo ""

# === Step 4: Run tier_b_pilot 2x (run 0/1) ===
for run_idx in 0 1; do
    out="${PILOT_OUT_DIR}/kant_r8v2_run${run_idx}_stim.duckdb"
    if [ -f "${out}" ]; then
        echo "[phase3] skip run ${run_idx} (output exists)"
        continue
    fi
    echo "[phase3] pilot run ${run_idx} → ${out}"
    "${PYBIN_WIN}" scripts/m9-c-adopt/tier_b_pilot.py \
        --persona kant --rank 8 --run-idx "${run_idx}" \
        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
        --sglang-host "${SGLANG_HOST}" \
        --adapter-name "${ADAPTER_NAME}" \
        --skip-adapter-check \
        --output "${out}" \
        --log-level info 2>&1 | tee "${TASK_DIR_REL}/pilot_run${run_idx}.log" | tail -5
done

# === Step 5: Validate shards (DA-13 publish precondition) ===
echo "[phase3] validate shards"
"${PYBIN_WIN}" scripts/m9-c-adopt/validate_multiturn_shards.py \
    --persona kant --focal-target 300 \
    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
    --output "${TASK_DIR_REL}/validation-v2-kant.json"

# === Step 6: Big5 ICC (uses SGLang, T=0.7) ===
echo "[phase4] Big5 ICC (SGLang LoRA-on)"
"${PYBIN_WIN}" scripts/m9-c-adopt/compute_big5_icc.py \
    --persona kant \
    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
    --responder sglang --sglang-host "${SGLANG_HOST}" \
    --sglang-adapter "${ADAPTER_NAME}" --temperature 0.7 \
    --window-size 100 \
    --output "${MATRIX_INPUT_DIR}/tier-b-icc-multiturn-kant-r8.json" \
    2>&1 | tee "${TASK_DIR_REL}/icc.log" | tail -5

# === Step 7: Stop SGLang ===
echo "[phase4] stopping SGLang PID ${SGLANG_PID}"
wsl -d Ubuntu-22.04 -- bash -c "kill -TERM ${SGLANG_PID} 2>/dev/null || true; sleep 5; kill -KILL ${SGLANG_PID} 2>/dev/null || true"

# === Step 8: Vendi semantic + Burrows (offline) ===
echo "[phase4] Vendi semantic"
"${PYBIN_WIN}" scripts/m9-c-adopt/compute_baseline_vendi.py \
    --persona kant --condition stimulus \
    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
    --kernel semantic --window-size 100 \
    --output "${MATRIX_INPUT_DIR}/tier-b-pilot-multiturn-kant-r8-vendi-semantic.json" \
    2>&1 | tee "${TASK_DIR_REL}/vendi.log" | tail -5

echo "[phase4] Burrows delta"
"${PYBIN_WIN}" scripts/m9-c-adopt/compute_burrows_delta.py \
    --persona kant \
    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
    --window-size 100 \
    --output "${MATRIX_INPUT_DIR}/tier-b-pilot-multiturn-kant-r8-burrows.json" \
    2>&1 | tee "${TASK_DIR_REL}/burrows.log" | tail -5

# === Step 9: Copy nolora baseline + matched baseline into matrix-inputs dir ===
echo "[phase4] populate matrix-inputs with baseline files from previous task"
for f in \
    "tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json" \
    "tier-b-pilot-multiturn-kant-nolora-burrows.json" \
    "tier-b-icc-multiturn-kant-nolora.json" \
    "tier-b-baseline-matched-kant-vendi-semantic.json" \
    "tier-b-baseline-matched-kant-burrows.json"; do
    if [ -f "${PREV_TASK}/${f}" ]; then
        cp "${PREV_TASK}/${f}" "${MATRIX_INPUT_DIR}/${f}"
        echo "  copied: ${f}"
    else
        echo "  MISSING: ${PREV_TASK}/${f}"
    fi
done

# === Step 10: DA-14 4-axis matrix (kant primary-rank 8) ===
echo "[phase4] DA-14 4-axis matrix"
"${PYBIN_WIN}" scripts/m9-c-adopt/da1_matrix_multiturn.py \
    --steering-historical .steering/20260513-m9-c-adopt \
    --steering-investigation "${MATRIX_INPUT_DIR}" \
    --ranks 8 --primary-rank 8 \
    --output "${TASK_DIR_REL}/da1-matrix-v2-kant.json" \
    2>&1 | tee "${TASK_DIR_REL}/da1-matrix-v2-kant.md"

echo ""
echo "=============================================="
echo "Phase 3-4 complete. Key artefacts:"
echo "  validation:   ${TASK_DIR_REL}/validation-v2-kant.json"
echo "  vendi r8:     ${MATRIX_INPUT_DIR}/tier-b-pilot-multiturn-kant-r8-vendi-semantic.json"
echo "  burrows r8:   ${MATRIX_INPUT_DIR}/tier-b-pilot-multiturn-kant-r8-burrows.json"
echo "  icc r8:       ${MATRIX_INPUT_DIR}/tier-b-icc-multiturn-kant-r8.json"
echo "  matrix:       ${TASK_DIR_REL}/da1-matrix-v2-kant.json"
echo "  matrix md:    ${TASK_DIR_REL}/da1-matrix-v2-kant.md"
echo "=============================================="

#!/usr/bin/env bash
# M13-ES4 Phase 0 — one-command reproduction (reproducibility-discipline).
#
# Runs from the Windows tree via the WSL root GPU venv (the WSL git checkout is
# stale; we import src from /mnt/c). SGLang fp8 qwen3:8b is the single generation
# backend; the MPNet encoder runs on CPU after the server is stopped (ADR §7
# phase-flip = stop server to free the GPU; the replay seams never call SGLang).
#
# Seeds / constants are frozen in src/erre_sandbox/evidence/es4_actuator/constants.py
# and the §5 pre-registration; this script tunes nothing.
#
# Prerequisite: full-freeze declared (run-manifest.json) + pre-flight assert PASS.
set -euo pipefail

REPO=/mnt/c/ERRE-Sand_Box
VENV=/root/erre-sandbox/.venv
RUN_DIR="${REPO}/experiments/20260630-es4-phase0"
PHASE_A_DIR="${RUN_DIR}/phaseA"
export PYTHONPATH="${REPO}/src"

run_py() { "${VENV}/bin/python" "$@"; }

echo "[run] === pre-flight sampling-hash assert ==="
run_py - <<'PY'
from erre_sandbox.evidence.es4_actuator.controls import preflight_sampling_hash
pf = preflight_sampling_hash("phase0")
assert pf.ok, f"pre-flight FAILED: {pf}"
print(f"pre-flight PASS (loco0==none={pf.loco_zero_equals_none}, "
      f"M2==A2={pf.m2_matches_a2_distribution}, max|dT|={pf.max_abs_temp_diff:.2e})")
PY

echo "[run] === launch SGLang fp8 (background) ==="
bash "${REPO}/scripts/es4/launch_sglang_es4.sh" >"${RUN_DIR}/sglang.log" 2>&1 &
disown
# /health returns 503 on this Blackwell GPU even when generation works; poll the
# /get_model_info liveness endpoint instead (DA-PH0-7).
echo "[run] waiting for SGLang /get_model_info ..."
for _ in $(seq 1 120); do
    if curl -sf http://127.0.0.1:30000/get_model_info >/dev/null 2>&1; then
        echo "[run] SGLang model loaded"; break
    fi
    sleep 5
done

echo "[run] === Phase A (generate + judge + adversarial score, persist) ==="
run_py "${REPO}/scripts/es4_phase0_run.py" --backend real --phase A \
    --run-dir "${PHASE_A_DIR}"

echo "[run] === phase-flip: stop SGLang (free GPU) ==="
pkill -f "sglang.launch_server" || true
sleep 10

echo "[run] === Phase B (replay + MPNet encoder -> verdict) ==="
run_py "${REPO}/scripts/es4_phase0_run.py" --backend real --phase B \
    --run-dir "${PHASE_A_DIR}" --out "${RUN_DIR}/verdict-phase0.json"

echo "[run] done. verdict -> ${RUN_DIR}/verdict-phase0.json"

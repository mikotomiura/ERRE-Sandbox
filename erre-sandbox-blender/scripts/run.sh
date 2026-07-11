#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 ERRE-Sandbox Contributors
#
# This file is part of erre-sandbox-blender.
# It is distributed under the terms of the GNU General Public License v3.0 or later.
#
# M13 M4 situated-3D — Issue 003 (I3): deterministic geometry-nodes .glb bake +
# same-machine byte idempotency procedure (design §1.3 二層 witness, developer
# side). Reproducibility-discipline: pinned Blender version + one-command regen +
# an explicit idempotency check that fails loudly on cross-run drift.
#
# The committed CI witness is the structural fingerprint sidecar
# (godot_project/assets/environment/<zone>_v1.fingerprint.json), verified without
# Blender by tests/test_integration/test_m4_zone_glb_fingerprint.py. This script
# is the *developer-side* half: it regenerates the committed .glb and asserts that
# a re-bake is byte-identical (seed-free geometry => deterministic on a fixed
# Blender build).
#
# --- Pinned toolchain (idempotency is only guaranteed within one build) ---
#   Blender 5.1.2 (hash ec6e62d40fa9, build date 2026-05-19)
#   Verified byte-idempotent on G-GEAR (Windows 11) 2026-07-11:
#     run1 sha256 = 5a7366e61a699e72174be70859514d6483d809bfefed66cd7aeb365d73d14519
#     run2 sha256 = 5a7366e61a699e72174be70859514d6483d809bfefed66cd7aeb365d73d14519
#   Cross-machine .glb bytes are NOT a witness (libm ULP drift); the 6-decimal
#   quantised fingerprint sidecar is (design §1.3, honest).
#
# Usage:
#   export BLENDER_BIN="C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
#   bash erre-sandbox-blender/scripts/run.sh            # bake peripatos
#   bash erre-sandbox-blender/scripts/run.sh --idempotency   # bake twice + diff
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BLENDER_BIN="${BLENDER_BIN:-blender}"

# I3 = peripatos only; I4 appends the remaining four zone export scripts here.
ZONES=(peripatos)

bake_zone() {
  local zone="$1"
  echo "[run.sh] baking ${zone} with ${BLENDER_BIN}"
  "${BLENDER_BIN}" --background --python \
    "${SCRIPT_DIR}/export_${zone}.py"
}

idempotency_check() {
  local zone="$1"
  local out="${REPO_ROOT}/godot_project/assets/environment/${zone}_v1.glb"
  local tmp1 tmp2
  tmp1="$(mktemp)"
  tmp2="$(mktemp)"
  bake_zone "${zone}" >/dev/null
  cp "${out}" "${tmp1}"
  bake_zone "${zone}" >/dev/null
  cp "${out}" "${tmp2}"
  echo "[run.sh] ${zone} run1 sha256: $(sha256sum "${tmp1}" | cut -d' ' -f1)"
  echo "[run.sh] ${zone} run2 sha256: $(sha256sum "${tmp2}" | cut -d' ' -f1)"
  if cmp -s "${tmp1}" "${tmp2}"; then
    echo "[run.sh] ${zone}: IDEMPOTENT (byte-identical across re-bake)"
  else
    echo "[run.sh] ${zone}: DRIFT — non-deterministic geometry (remove seed/random node)" >&2
    rm -f "${tmp1}" "${tmp2}"
    exit 1
  fi
  rm -f "${tmp1}" "${tmp2}"
}

main() {
  local mode="${1:-bake}"
  for zone in "${ZONES[@]}"; do
    case "${mode}" in
      --idempotency) idempotency_check "${zone}" ;;
      bake) bake_zone "${zone}" ;;
      *) echo "[run.sh] unknown mode: ${mode}" >&2; exit 2 ;;
    esac
  done
}

main "$@"

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 ERRE-Sandbox Contributors
#
# This file is part of erre-sandbox-blender.
# It is distributed under the terms of the GNU General Public License v3.0 or later.
#
# M13 M4 situated-3D — Issue 003 (I3) + Issue 004 (I4): deterministic
# geometry-nodes .glb bake + same-machine byte idempotency procedure (design §1.3
# 二層 witness, developer side). Reproducibility-discipline: pinned Blender version
# + one-command regen + an explicit idempotency check that fails loudly on
# cross-run drift. I3 landed peripatos; I4 appends study / chashitsu / agora /
# garden (all five under the identical seed-free determinism contract).
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
#   Verified byte-idempotent on G-GEAR (Windows 11) — each zone baked twice,
#   run1 sha256 == run2 sha256 (I4-G3):
#     peripatos (2026-07-11) = 5a7366e61a699e72174be70859514d6483d809bfefed66cd7aeb365d73d14519
#     study     (2026-07-12) = 38be385f058fb046c3685661e7b530e4ae913be3fb6d041f7b649a5377e1b117
#     chashitsu (2026-07-12) = 4aacdf5e494dead9053757290614eaba9d4dd24936ed144919d2b5bb1650095f
#     agora     (2026-07-12) = 86f23ea4827438b0ab553042874a33a1f36e831b5ac4ad944c83e429d51d4af8
#     garden    (2026-07-12) = 7f85c7973850b3e637b33b803ca465f3604e6e9fadde60a3615d66241e26b5f2
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

# I3 landed peripatos; I4 appends study / chashitsu / agora / garden.
ZONES=(peripatos study chashitsu agora garden)

# Zone -> export script basename. Almost all zones map to export_<zone>.py; the
# chashitsu zone is the exception — its geometry-nodes builder is
# export_chashitsu_gn.py (the primitive export_chashitsu.py is kept unchanged as
# the §1.2 staged-migration template), while its committed artefact is still
# chashitsu_v1.glb.
script_for_zone() {
  local zone="$1"
  case "${zone}" in
    chashitsu) echo "export_chashitsu_gn.py" ;;
    *) echo "export_${zone}.py" ;;
  esac
}

bake_zone() {
  local zone="$1"
  echo "[run.sh] baking ${zone} with ${BLENDER_BIN}"
  "${BLENDER_BIN}" --background --python \
    "${SCRIPT_DIR}/$(script_for_zone "${zone}")"
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

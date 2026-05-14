#!/bin/bash
set -e
cd /mnt/c/ERRE-Sand_Box
PYBIN=/root/erre-sandbox/.venv/bin/python
for rank in 4 8 16; do
    echo "=== per-rank Vendi rank=${rank} ==="
    PYTHONPATH=src "${PYBIN}" scripts/m9-c-adopt/compute_baseline_vendi.py \
      --persona kant --condition stimulus \
      --shards-glob "/mnt/c/ERRE-Sand_Box/data/eval/m9-c-adopt-tier-b-pilot/kant_r${rank}_run*_stim.duckdb" \
      --kernel lexical-5gram --window-size 100 \
      --output "/mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/tier-b-pilot-kant-r${rank}-vendi-lexical.json" \
      --log-level info 2>&1 | tail -5
done

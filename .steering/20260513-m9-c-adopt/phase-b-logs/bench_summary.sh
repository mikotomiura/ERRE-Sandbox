#!/bin/bash
PYBIN=/root/erre-sandbox/.venv/bin/python
for rank in 4 8 16; do
    out="/mnt/c/ERRE-Sand_Box/data/eval/m9-c-adopt-bench/single_lora-r${rank}.jsonl"
    echo "--- rank=${rank} ---"
    "${PYBIN}" -c "
import json, pathlib
data = pathlib.Path('${out}').read_text().strip().splitlines()
r = json.loads(data[-1])
print(f'  output_throughput_tok_s = {r.get(\"output_throughput\", \"NA\")}')
print(f'  ttft_p50_ms             = {r.get(\"median_ttft_ms\", \"NA\")}')
print(f'  ttft_p99_ms             = {r.get(\"p99_ttft_ms\", \"NA\")}')
print(f'  e2e_p99_ms              = {r.get(\"p99_e2e_latency_ms\", \"NA\")}')
print(f'  itl_p99_ms              = {r.get(\"p99_itl_ms\", \"NA\")}')
print(f'  successful              = {r.get(\"completed\", \"NA\")}')
print(f'  total_latency_ms        = {r.get(\"total_latency\", r.get(\"duration\", \"NA\"))}')
"
done

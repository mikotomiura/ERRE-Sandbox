"""DA17-3 Burrows JSON read-only inspection (commit せず ad-hoc)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[2]
v3_lora = json.loads((REPO / ".steering/20260516-m9-c-adopt-plan-b-eval-gen/tier-b-plan-b-kant-r8v3-burrows.json").read_text(encoding="utf-8"))
v4_lora = json.loads((REPO / ".steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/tier-b-plan-b-kant-r8v4-burrows.json").read_text(encoding="utf-8"))
v3_nolora = json.loads((REPO / ".steering/20260516-m9-c-adopt-plan-b-eval-gen/tier-b-plan-b-kant-planb-nolora-burrows.json").read_text(encoding="utf-8"))
v4_nolora = json.loads((REPO / ".steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/tier-b-plan-b-kant-planb-nolora-v4-burrows.json").read_text(encoding="utf-8"))


def summarise(name: str, j: dict) -> None:
    print(f"--- {name} ---")
    print(f"  shards: {j['shards']}")
    rc = j["lang_routing_counts"]
    print(f"  lang_routing: de={rc['de']}/total={rc['total_utterances_seen']} ({rc['de_fraction']:.2%})")
    print(f"    en_dropped={rc['en_dropped']}  ja_dropped={rc['ja_dropped']}  low_conf={rc['low_confidence_dropped']}")
    b = j["bootstrap"]
    print(f"  bootstrap point={b['point']:.4f}  lo={b['lo']:.4f}  hi={b['hi']:.4f}  n={b['n']}")
    pw = [round(w["mean_burrows"], 2) for w in j["per_window"]]
    print(f"  per_window means: {pw}")


summarise("v3 LoRA-on (kant_r8v3)", v3_lora)
summarise("v3 no-LoRA", v3_nolora)
summarise("v4 LoRA-on (kant_r8v4)", v4_lora)
summarise("v4 no-LoRA", v4_nolora)

# reduction% = (no-LoRA - LoRA) / no-LoRA * 100 (LoRA が低いほど positive)
v3_red = (v3_nolora["bootstrap"]["point"] - v3_lora["bootstrap"]["point"]) / v3_nolora["bootstrap"]["point"] * 100
v4_red = (v4_nolora["bootstrap"]["point"] - v4_lora["bootstrap"]["point"]) / v4_nolora["bootstrap"]["point"] * 100
print(f"\nReduction% (de-only):")
print(f"  v3: ({v3_nolora['bootstrap']['point']:.4f} - {v3_lora['bootstrap']['point']:.4f}) / {v3_nolora['bootstrap']['point']:.4f} * 100 = {v3_red:+.4f}%")
print(f"  v4: ({v4_nolora['bootstrap']['point']:.4f} - {v4_lora['bootstrap']['point']:.4f}) / {v4_nolora['bootstrap']['point']:.4f} * 100 = {v4_red:+.4f}%")
print(f"  Delta v3->v4: {v4_red - v3_red:+.4f} pt")

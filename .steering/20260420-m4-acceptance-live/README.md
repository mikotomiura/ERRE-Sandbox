# M4 live acceptance — evidence (partial)

This directory collects the 5 evidence items listed in
`.steering/20260420-m4-multi-agent-orchestrator/live-checklist.md`
from the **actual live run** of `uv run erre-sandbox --personas
kant,nietzsche,rikyu`.

## What's here

| # | Item | Status | Location | Source host |
|---|---|---|---|---|
| 1 | `/health` snapshot | pending | `evidence/gateway-health-*.json` | G-GEAR |
| 2 | 3-agent walking envelope stream | pending | `evidence/cognition-ticks-*.log` | G-GEAR |
| 3 | `semantic_memory` dump | pending | `evidence/semantic-memory-dump-*.txt` | G-GEAR |
| 4 | Dialog trace | pending | `evidence/dialog-trace-*.log` | G-GEAR |
| 5 | Godot 3-avatar recording | **✅ captured 2026-04-20** | `evidence/godot-3avatar-20260420-1625.mp4` | MacBook |

## How this split came about

Item #5 (the Godot recording) is the MacBook-side acceptance evidence —
it had to be captured on the machine running the 3D viewer. Items #1-#4
are produced on the G-GEAR box that runs `erre-sandbox` itself
(Ollama + cognition + memory + gateway), and will be collected by the
G-GEAR Claude Code session following the handoff at
`.steering/_handoff-g-gear-m4-live-validation.md`.

This PR delivers only #5. The G-GEAR side will either extend this
directory in a follow-up PR or open a companion branch with the other
four items and the final `acceptance.md` PASS/FAIL summary.

## Video capture notes

- Source: MacBook Godot editor running `godot_project/`, connected to
  G-GEAR's gateway over WebSocket
- Resolution 1280×720 (Godot embedded-game window size at capture time)
- Duration / fps observation: reviewed manually by the operator during
  recording; the acceptance note will be written after G-GEAR evidence
  arrives and the whole 5-item matrix is filled in

## Next step

Once G-GEAR contributes items #1-#4, write `acceptance.md` with the
PASS/FAIL table from `live-checklist.md` §PASS 条件 and decide whether
to cut the `v0.2.0-m4` tag.

# M4 live acceptance — evidence (partial)

This directory collects the 5 evidence items listed in
`.steering/20260420-m4-multi-agent-orchestrator/live-checklist.md`
from the **actual live run** of `uv run erre-sandbox --personas
kant,nietzsche,rikyu`.

## What's here

| # | Item | Status | Location | Source host |
|---|---|---|---|---|
| 1 | `/health` snapshot | ✅ PASS | `evidence/gateway-health-*.json` | G-GEAR |
| 2 | 3-agent walking envelope stream | ✅ PASS | `evidence/cognition-ticks-*.log` | G-GEAR |
| 3 | `semantic_memory` dump | ✅ PASS | `evidence/semantic-memory-dump-*.txt` | G-GEAR |
| 4 | Dialog trace | ✅ PASS | `evidence/dialog-trace-*.log` | G-GEAR |
| 5 | Godot 3-avatar recording | ✅ PASS (captured 2026-04-20) | `evidence/godot-3avatar-20260420-1625.mp4` | MacBook |

Full PASS/FAIL summary with criteria quotations → `acceptance.md`.

## How this split came about

Item #5 (the Godot recording) is the MacBook-side acceptance evidence —
it had to be captured on the machine running the 3D viewer. Items #1-#4
are produced on the G-GEAR box that runs `erre-sandbox` itself
(Ollama + cognition + memory + gateway), and were collected by the
G-GEAR Claude Code session following a MacBook ↔ G-GEAR handoff note
(the note itself was removed after M4 completion; its contents are
consolidated into this task's `requirement.md` / `design.md` /
`acceptance.md`).

Commit history:

- `22841d5 chore(m4): capture Godot 3-avatar live recording (acceptance #5)` — MacBook
- G-GEAR #1-#4 collection commits follow in this same branch

## Video capture notes

- Source: MacBook Godot editor running `godot_project/`, connected to
  G-GEAR's gateway (`ws://192.168.3.85:8000/ws/observe?subscribe=a_kant_001,a_nietzsche_001,a_rikyu_001`)
  over WebSocket
- Resolution 1280×720 (Godot embedded-game window size at capture time)
- Duration / fps observation: reviewed visually by the operator during
  recording — fps counter held 28-32 over the 60s window per
  `live-checklist.md` §#5

## Next step

All 5 items ✅ PASS. Open the PR for this branch and, once merged,
consult the user about cutting the `v0.2.0-m4` tag.

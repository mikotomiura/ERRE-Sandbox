# M6 live acceptance evidence

Every live run against a G-GEAR gateway drops artefacts under this
directory. The run-level procedure is codified in
`../tasklist.md` §"統合 + Acceptance"; this README is the quick
operational checklist.

## Prerequisites

1. G-GEAR is reachable from MacBook and a gateway is up:

   ```bash
   curl -s http://g-gear.local:8000/health | jq .
   # Expected: {"schema_version": "0.4.0-m6", ...}
   ```

2. Ollama model is warm (≥ 1 token/s):

   ```bash
   # On G-GEAR
   ollama list | grep qwen3
   ```

3. MacBook is on main or on an acceptance-scope branch with no
   uncommitted changes (`git status -sb`).

## Run a session

```bash
TS=$(date -u +%Y%m%d-%H%M%S)
OUT_BASE=.steering/20260421-m6-observatory/evidence

# 1. Tail the envelope stream while the live session runs.
uv run python "$OUT_BASE/_stream_probe_m6.py" \
    --url ws://g-gear.local:8000/ws/observe \
    --duration 180 \
    --out "$OUT_BASE/logs/live-$TS.jsonl" &
PROBE_PID=$!

# 2. Open Godot on MainScene (GUI). Interact: try all 3 camera modes,
#    click each avatar, toggle boundary (B), wander into chashitsu.
godot --path godot_project --scene scenes/MainScene.tscn

# 3. When done, let the probe finish its window.
wait $PROBE_PID

# 4. Capture screenshots into screenshots/ alongside the jsonl.
# 5. Copy acceptance-template.md to acceptance-$TS.md and fill it in.
cp "$OUT_BASE/acceptance-template.md" "$OUT_BASE/acceptance-$TS.md"
```

## Artefact layout

```
evidence/
├── README.md                      ← this file
├── acceptance-template.md         ← fill-in form (copy per run)
├── _stream_probe_m6.py            ← WS probe helper
├── logs/
│   ├── live-<TS>.jsonl            ← every envelope captured
│   ├── live-<TS>.jsonl.summary.json  ← per-kind counts
│   └── gateway-live-<TS>.log      ← G-GEAR stdout capture (copy over)
├── screenshots/
│   └── NN-<label>.png             ← one per 3-axis gate at minimum
└── acceptance-<TS>.md             ← filled-in verdict
```

## Common gotchas

- `schema_mismatch` handshake error → verify the Godot
  `CLIENT_SCHEMA_VERSION` constant and the gateway's `SCHEMA_VERSION`
  both read `0.4.0-m6`.
- Empty `reasoning_trace` counts → the LLM may not be following the
  trailing-JSON schema hint; either lower temperature or add a few-shot
  example via `prompting.RESPONSE_SCHEMA_HINT`.
- `g-gear.local` does not resolve → override the MacBook hosts file or
  set the ``ws_url`` export on `MainScene ▸ WebSocketClient` to the LAN
  IP.

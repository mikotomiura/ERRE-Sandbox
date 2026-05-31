# godot_project/scenes/dev/

**Developer-only** scenes for fixture replay and headless testing. See
`scripts/dev/README.md` for the GPL-free separation rationale.

## Content

- `FixtureHarness.tscn` — Composes `scenes/MainScene.tscn` (which already
  contains `WorldManager`, `EnvelopeRouter`, `AgentManager`, `WebSocketClient`
  etc.) with a `FixturePlayer` (`scripts/dev/FixturePlayer.gd`). On load
  the harness disables `WebSocketClient` so the client does not try to
  reach `ws://g-gear.local:8000/stream` during a fixture run.

## Launch

```
godot --path godot_project --headless --quit-after 30 \
      scenes/dev/FixtureHarness.tscn -- --fixture-dir=<abs path to fixtures/control_envelope>
```

`tests/test_godot_ws_client.py` drives this exact command during CI.

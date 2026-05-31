# ControlEnvelope JSON fixtures

This directory is the **authoritative wire-format specimen** for the
`ControlEnvelope` contract defined in
[`src/erre_sandbox/schemas.py`](../../src/erre_sandbox/schemas.py) §7.

## Purpose

1. **Contract specimen** — concrete examples of every on-wire envelope kind,
   for reviewers and reimplementers (Godot, future language bindings).
2. **Regression test data** — `tests/test_envelope_fixtures.py` parses every
   file and validates it against the current `ControlEnvelope` discriminated
   union. Any schema drift breaks CI immediately.
3. **Godot developer reference** — GDScript client authors read these files
   to know exactly what bytes they will see on the WebSocket.

## Coherent scenario

All seven fixtures are snapshots of **the same moment in one session**:

> Agent `a_kant_001` (`persona_id=kant`) has just entered the `peripatos`
> zone, switched to the `peripatetic` ERRE mode at tick 40 (DMN activation
> rising), and at tick 42 is walking along the Linden-Allee (facing east,
> `yaw ≈ π/2`). The utterance is a fragment of the *Beschluss* (conclusion)
> of Kant's *Kritik der praktischen Vernunft* (1788).

Shared invariants:

| field | value |
| --- | --- |
| `schema_version` | `0.1.0-m2` |
| `sent_at` | `2026-04-18T12:00:00Z` |
| `tick` | `42` (except `handshake.json` which is at tick `0`, session start) |
| `agent_id` (where present) | `a_kant_001` |

## Files

| File | `kind` | What it represents |
| --- | --- | --- |
| `handshake.json` | `handshake` | Capability negotiation at session start. |
| `agent_update.json` | `agent_update` | Full `AgentState` snapshot at tick 42. |
| `speech.json` | `speech` | Kant utters a Kritik fragment in German. |
| `move.json` | `move` | Locomotion intent toward the next Linden-Allee waypoint. |
| `animation.json` | `animation` | Walk animation, looping. |
| `world_tick.json` | `world_tick` | Global clock pulse, 1 active agent. |
| `error.json` | `error` | Observability example: the gateway rejects an unknown `kind` (`mode_change` is deliberately shown as *invalid* — ERRE mode transitions live in `Observation.event_type`, not in `ControlEnvelope.kind`). |

## How to consume (GDScript)

```gdscript
# In AgentController.gd — dispatch on envelope.kind
func _on_envelope_received(envelope: Dictionary) -> void:
    match envelope.get("kind", ""):
        "handshake":
            _negotiate_capabilities(envelope)
        "agent_update":
            _apply_agent_state(envelope["agent_state"])
        "speech":
            _spawn_speech_bubble(envelope)
        "move":
            _start_navigation(envelope["target"], envelope["speed"])
        "animation":
            _set_animation(envelope["animation_name"], envelope["loop"])
        "world_tick":
            _update_clock(envelope["wall_clock"])
        "error":
            push_error("gateway error: %s — %s" % [envelope["code"], envelope["detail"]])
        _:
            push_warning("Unknown envelope kind: %s" % envelope.get("kind"))
```

Datetime fields (`sent_at`, `wall_clock`) arrive as ISO 8601 strings; parse
them with `Time.get_unix_time_from_datetime_string()` if you need numeric
timestamps.

## How to consume (Python)

```python
import json
from pathlib import Path

from pydantic import TypeAdapter

from erre_sandbox.schemas import ControlEnvelope

adapter: TypeAdapter[ControlEnvelope] = TypeAdapter(ControlEnvelope)
raw = Path("fixtures/control_envelope/speech.json").read_text("utf-8")
envelope = adapter.validate_python(json.loads(raw))
assert envelope.kind == "speech"
```

## Update rules

- When `SCHEMA_VERSION` (see `schemas.py` §1) is bumped, every fixture here
  must be regenerated. `tests/test_envelope_fixtures.py::test_fixture_schema_version_matches`
  fails until they are.
- When a new envelope kind is added to `ControlEnvelope`, add a matching
  `<kind>.json` here. `test_all_seven_kinds_have_fixture` will fail if the
  kinds and fixtures diverge (update the expected set too).
- Do **not** edit `kind` values without updating `schemas.py` first —
  `schemas.py` is the single source of truth.

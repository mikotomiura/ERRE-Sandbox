# godot_project/scripts/dev/

**Developer-only** GDScript for fixture replay and headless regression testing.

## Content

- `FixturePlayer.gd` — Replays `fixtures/control_envelope/*.json` against the
  `EnvelopeRouter` so `scenes/dev/FixtureHarness.tscn` can exercise the full
  signal wiring without a running G-GEAR gateway (Contract-First workflow).
- `EclReplayPlayer.gd` — Offline-replays an ECL v0 / M2-society handoff
  (`manifest.json` + `envelope_stream.jsonl`) as an envelope-only headless print.
- `SocietyReplayViewer.gd` — M4 situated-3D viewer (`extends SceneTree`). Stands
  the committed N-body society substrate up with a replay **role split**: motion
  authority = `ecl_trace.jsonl` (per-`(physics_tick_index, order_slot)` absolute
  placement, echoed pass-through), speech/animation firing = `envelope_stream.jsonl`
  (`move` is not a position authority). Two modes: headless dump for CI witness
  (`--dump=<abs>`) and interactive timeline print. The whole-view wrapper scene
  is `scenes/dev/SocietyReplayScene.tscn`. Boot path (headless dump):

  ```
  godot --headless --path godot_project \
    --script res://scripts/dev/SocietyReplayViewer.gd \
    -- --manifest=<abs>/manifest.json --trace=<abs>/ecl_trace.jsonl \
       --stream=<abs>/envelope_stream.jsonl --dump=<abs>/placement_dump.jsonl
  ```

## Rules

1. **Never import from `dev/` in production scripts.** The production
   `WebSocketClient.gd` / `EnvelopeRouter.gd` / `AgentManager.gd` must stay
   agnostic to fixture replay. The separation guarantees that a future
   `.pck` export excluding this directory ships the production path only.
2. **Boot path**: Production runs `scenes/MainScene.tscn`; fixture replay runs
   `scenes/dev/FixtureHarness.tscn`. Never mix the two in the same scene.
3. **Fixture dir**: `FixturePlayer.gd` reads the absolute path from
   `OS.get_cmdline_user_args()` (`--fixture-dir=…`). Python tests inject it;
   interactive runs use the script's default resolution of
   `<repo>/fixtures/control_envelope/` via `ProjectSettings.globalize_path`.

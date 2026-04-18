# godot_project/scripts/dev/

**Developer-only** GDScript for fixture replay and headless regression testing.

## Content

- `FixturePlayer.gd` — Replays `fixtures/control_envelope/*.json` against the
  `EnvelopeRouter` so `scenes/dev/FixtureHarness.tscn` can exercise the full
  signal wiring without a running G-GEAR gateway (Contract-First workflow).

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

See `.steering/20260418-godot-ws-client/design.md` §Fixture 分離の実装詳細.

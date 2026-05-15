# ERRE-Sandbox

[English](README.md) | [日本語](README.ja.md)

ERRE-Sandbox is a research platform that re-implements the cognitive habits
of historical thinkers (Aristotle, Kant, Nietzsche, Rikyū, Dōgen, …) as
locally-hosted LLM agents inhabiting a shared 3D world. The system is
designed around two principles: **deliberate inefficiency** and **embodied
return**, used as first-class primitives to observe emergent intellectual
behavior.

## Status — M9-A merged, M9-B / M9-eval in progress (last verified 2026-05-08)

Wire schema is at **`0.10.0-m7h`** (M9-A `event-boundary-observability`
bump on top of M7ζ `live-resonance`). Three-agent society (Kant /
Nietzsche / Rikyū) boots through `uv run erre-sandbox --personas
kant,nietzsche,rikyu`, with the M5 ERRE-mode FSM, multi-turn LLM dialog,
and all five zone scenes (`peripatos` / `chashitsu` / `zazen` / `agora` /
`garden` plus `study` and `base_terrain`) live on a Godot 4.6 viewer.
Trigger-event tags (M9-A) propagate from the Python `Reflector` to the
`ReasoningPanel` so the operator can see *why* a reflection fired.

Recent landmarks (newest first):

- **Cognition-deepening 7-point decision** (2026-05-08, this PR — design only,
  no source change): three-source synthesis (Claude initial Plan-mode +
  independent reimagine subagent + Codex `gpt-5.5 xhigh` 197K-token review,
  ADOPT-WITH-CHANGES, HIGH 7 / MEDIUM 5 / LOW 3) for a future two-layer
  cognition architecture (`PhilosopherBase` immutable inheritance +
  `IndividualProfile` mutable runtime + `SubjectiveWorldModel` /
  `DevelopmentState` S1–S3 / `NarrativeArc` / bounded `WorldModelUpdateHint`).
  Implementation is **gated to post-M9** (M10-0 metric scaffolding precedes
  any schema work). Final spec lives in
  `.steering/20260508-cognition-deepen-7point-proposal/design-final.md`;
  ADRs in `decisions.md`. No effect on the running G-GEAR run1 calibration.
- **M9-eval ME-9 trigger amendment** (2026-05-07, PR #142): the regular STOP
  observed at run1 cells 100/101 is classified as a false-positive trigger
  (Codex 9th review, hybrid A/C verdict); cooldown re-adjustment is rejected.
  ADR ME-9 gets an Amendment 2026-05-07, and the v2 prompt is extended with
  §A.4 saturation model + §B-1b run102 resume procedure.
- **M9-eval Phase 2 run1 calibration v2 prompt** (2026-05-07, PR #141): live
  `qwen3:8b` G-GEAR launch prompt v2 (kant 1 cell × 5, wall ≈ 30 h × 2 nights),
  golden-battery driver + audit gate (`erre-eval-run-golden` /
  `erre-eval-audit`), 4-layer `raw_dialog` ↔ `metrics` schema contract
  (`src/erre_sandbox/contracts/eval_paths.py`), `data/eval/calibration/run1/`
  isolation with sidecar md5 receipt.
- **M9-eval CLI partial-fix** (2026-05-06, PR #140): `eval_audit` gate +
  capture-sidecar receipts + `--allow-partial` semantics, 1318 tests PASS.
- **M9-B LoRA execution plan** (2026-04-30, PR #127): SGLang-first ADR
  (DB1–DB10) with bounded Kant spike. Execution itself is the next
  milestone.
- **M9-A event-boundary observability** (2026-04-30, PR #117–#124, 6/6 PASS):
  `TriggerEventTag` end-to-end through reasoning panel, `pulse_zone`
  observability via log-based START counters.
- **Godot viewport layout** (2026-04-28, PR #115/#116): HSplit + collapse
  reasoning panel; live RTX 5060 Ti acceptance.
- **CI pipeline + Codex environment** (2026-04-28, PR #113/#114): pre-commit
  + 3-parallel CI jobs (`lint` / `typecheck` / `test`); `.codex/` config +
  `AGENTS.md` for first-class Codex-CLI partnership.
- **Contracts layer** (2026-04-28, PR #111/#112): `src/erre_sandbox/contracts/`
  for ui-allowable lightweight Pydantic boundary (thresholds, eval paths).
- Earlier release tags: `v0.1.0-m2` (contract freeze) / `v0.1.1-m2` (1-agent
  MVP) / `v0.2.0-m4` (3-agent reflection + dialog) / `v0.3.0-m5` (ERRE
  FSM + LLM dialog + zone visuals).

**Next milestones**: (1) M9-eval Phase 2 run1 wall-budget calibration on
G-GEAR (kant single-cell × 5, ~30 h overnight × 2); (2) M9-B LoRA execution
(`m9-c-spike`); (3) `godot-ws-keepalive` reliability work. After M9 fully
closes, **M10+ cognition-deepening** kicks off (M10-0 metrics → M10-A
two-layer schema scaffold → M10-B SWM read-only → M10-C bounded
`WorldModelUpdateHint` → M11-A `NarrativeArc` → M11-B S1–S3 transition →
M11-C kant-base × 3 individuals validation; S4/S5 / retirement / individual
LoRA gated to M12+).

## Key components

- **Python 3.11 core** (`src/erre_sandbox/`): Pydantic v2 schemas
  (`schemas.py`), inference adapters (Ollama / SGLang [planned]), memory
  (sqlite-vec + semantic layer with `origin_reflection_id`), CoALA-inspired
  cognition cycle with `Reflector`, ERRE FSM (`erre/`), world tick loop,
  in-memory dialog scheduler with proximity-based auto-fire.
- **Contracts layer** (`src/erre_sandbox/contracts/`): lightweight
  pydantic-only boundary modules (`thresholds.py`, `eval_paths.py`) that
  may be imported from `ui/`, `integration/`, `evidence/` without dragging
  in heavy deps.
- **Evidence layer** (`src/erre_sandbox/evidence/`): post-hoc metric
  computation — M8 baseline quality (`self_repetition_rate` /
  `cross_persona_echo_rate` / `bias_fired_rate`), M8 scaling profile
  (`pair_information_gain` / `late_turn_fraction` / `zone_kl_from_uniform`),
  M9-eval Tier-A pipeline (Burrows / MATTR / NLI / novelty / Empath proxy),
  bootstrap CI, golden baseline driver, capture sidecar.
- **Eval CLIs** (`src/erre_sandbox/cli/`):
  - `erre-sandbox` sub-commands — `run` (default), `export-log`,
    `baseline-metrics`, `scaling-metrics`.
  - Stand-alone — `python -m erre_sandbox.cli.eval_run_golden` /
    `python -m erre_sandbox.cli.eval_audit` (M9-eval).
- **Godot 4.6 frontend** (`godot_project/`): 3D visualization over a
  WebSocket bridge; humanoid avatars, ERRE-mode tint, dialog bubbles,
  reasoning panel with trigger-event tags, six rendered scenes
  (`MainScene` + `BaseTerrain` + 5 ERRE zones).
- **Personas** (`personas/*.yaml`): per-thinker habits, ERRE-mode
  sampling overrides, public-domain source references. Current set:
  `kant.yaml`, `nietzsche.yaml`, `rikyu.yaml` (additional personas
  gated on observability-triggered scaling — see
  `docs/glossary.md`).

## Getting started

```bash
uv sync
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -m "not godot"
```

The pre-commit hook runs `ruff check` and `ruff format --check` on staged
`src/` / `tests/` Python files at commit time. The GitHub Actions CI
workflow (`.github/workflows/ci.yml`, on push to `main` and on every PR)
runs all four checks (`ruff check`, `ruff format --check`, `mypy src`,
`pytest -m "not godot"`) in three parallel jobs (`lint` / `typecheck` /
`test`). Godot-binary tests (marked `@pytest.mark.godot`) are deselected
on CI and run manually. Requires [uv](https://docs.astral.sh/uv/). To
enable the local hook once after cloning:

```bash
uv tool install pre-commit
pre-commit install
```

Heavy ML dependencies for the M9-eval pipeline (sentence-transformers,
scipy, ollama, empath, arch) are isolated under the `eval` extras group:

```bash
uv sync --extra eval
```

### WebSocket connection-time auth (SH-2)

The orchestrator's WebSocket endpoint ships with three independent gates
(shared token / Origin allow-list / session cap 8) — all disabled by
default so existing Mac↔G-GEAR LAN workflows keep working. `bootstrap()`
refuses to start with `host=0.0.0.0` *and* all three gates off so a bare
`--host=0.0.0.0` cannot silently expose the server.

For LAN development without auth, opt into the Origin gate:

```bash
uv run python -m erre_sandbox \
  --allowed-origins=http://mac.local,http://g-gear.local
```

To turn on the shared-token gate, first provision the on-disk token
(preferred over env vars so it does not leak via `ps -E`):

```bash
mkdir -p var/secrets && chmod 700 var/secrets
python -c "import secrets; print(secrets.token_urlsafe(32))" \
  > var/secrets/ws_token
chmod 600 var/secrets/ws_token
uv run python -m erre_sandbox --require-token
```

Then connect with the matching `x-erre-token` header. Operational notes
(rotation, multi-token, override priority) live in
`docs/development-guidelines.md`.

## Layout

See `docs/repository-structure.md` for the authoritative layout and
`docs/architecture.md` for the end-to-end data flow. Glossary of
ERRE-specific terms (peripatos, chashitsu, shu-ha-ri, observability-
triggered scaling, …) is in `docs/glossary.md`.

## License

Dual-licensed under **Apache-2.0 OR MIT** at the user's choice. See
`LICENSE`, `LICENSE-MIT`, and `NOTICE`. Any Blender-side integration lives
in a separately-packaged GPL-3.0 project (`erre-sandbox-blender/`) to
prevent license contamination.

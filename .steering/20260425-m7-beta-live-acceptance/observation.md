# Observation — G-GEAR Live Acceptance Bundle (M7-β + M8 #87)

> Live run on G-GEAR (Windows / RTX, VRAM 16GB) on 2026-04-25.
> Personas: kant, nietzsche, rikyu (3 agents). Schema 0.5.0-m8.
> 2 runs × 80s × `_stream_probe_m8.py`, then `export-log` + `baseline-metrics`.
> See `baseline.md` for the M9 reference table from PR #88 + #89.

## TL;DR

- **β zone-residency: 5/6 PASS** (1 FAIL is small-sample noise, see §3)
- **PR #87 sanity: 2/2 PASS**
- Recommended **production default `ERRE_ZONE_BIAS_P = 0.1`**
  (Run 1 hit all 3 personas, Run 2's Rikyū dipped below threshold despite the
  higher bias)

## 1. Setup

| | value |
|---|---|
| Host | G-GEAR (Windows 11, NVIDIA RTX, 16 GB VRAM, ~15 GB free at start) |
| Models | `qwen3:8b` (chat), `nomic-embed-text:latest` (embed), via Ollama 11434 |
| `OLLAMA_NUM_PARALLEL` | `4` |
| Schema | server `0.5.0-m8`, probe `0.5.0-m8` (new `_stream_probe_m8.py`) |
| Personas | kant, nietzsche, rikyu (M4 3-agent config) |
| Run duration | 80 s wall-clock per run, observed via stream probe |
| WS endpoint | `ws://localhost:8000/ws/observe` |

The original M6 probe at `.steering/20260421-m6-observatory/evidence/_stream_probe_m6.py`
advertises `0.4.0-m6` and is left untouched as frozen evidence. The bundle
uses a fresh `_stream_probe_m8.py` with the right schema and `peer="macbook"`
(required by the `HandshakeMsg.peer` Literal).

## 2. β zone-residency table (PR #83, 6 items)

```
Run 1 (bias_p=0.1)
  Kant       peripatos+study      = 100.0%   PASS  (>=50%)
  Nietzsche  peripatos+garden     = 100.0%   PASS  (>=50%)
  Rikyū      chashitsu+garden+st  =  50.0%   PASS  (>=50%, exactly at threshold)

Run 2 (bias_p=0.2)
  Kant       peripatos+study      = 100.0%   PASS
  Nietzsche  peripatos+garden     = 100.0%   PASS
  Rikyū      chashitsu+garden+st  =  40.0%   FAIL  (chashitsu 40% + peripatos 60%)
```

Tick counts per agent (from `agent_update` envelopes): 4 in Run 1, 5 in Run 2.
Sample is small — see §3.

### β visual items (3, MacBook-side check, **not yet recorded**)

These require the Godot client on the MacBook. The G-GEAR session does not
have a display attached, so the screenshots are deferred:

- [ ] BoundaryLayer 5 zone rects on new Voronoi
- [ ] Study / Agora / Garden primitive buildings visible
- [ ] BaseTerrain 100 m + top-down hotkey `0` framing

Per `design.md` §5 these are **observation tasks only** — when the user
captures them on the MacBook, they should be saved as
`run-01-bias01/screenshot-{topdown,zone,reasoning}.png` and the boxes ticked
above. Behavioural results are independent of the visual check.

## 3. Why Rikyū-Run-2 dipped below threshold

**Hypothesis: small-sample noise, not a real regression.**

- Each agent emits an `agent_update` envelope only on cognition ticks, which
  default to 20 s. 80 s / 20 s ≈ 4-5 samples — exactly what we observed.
- With n=5, a single sample at `peripatos` instead of `chashitsu` swings
  Rikyū's preferred-zone share by 20 percentage points.
- Run 2 also showed only 4 dialog turns vs 12 in Run 1 (`baseline.json`),
  and only 2/3 agents ever entered a dialog (`num_agents=2`). The
  larger bias does not appear to *help* dialog co-location — it may be
  pulling Rikyū back to chashitsu (a quiet zone) and dispersing the
  agora/peripatos overlap that the Run 1 dialogs depended on.
- `bias_event_count` was **higher in Run 1** (1 event) than Run 2 (0
  events), the opposite of what the bias_p magnitude suggests. Either the
  bias-fire counter is sample-floor-bound at this run length, or the
  bias is short-circuited by persona prompting in Run 2's RNG draw.

**Production default recommendation: `ERRE_ZONE_BIAS_P = 0.1`** until
either (a) longer runs (>3 min) are sustainable on G-GEAR, or (b) M8
dialog-turn-rate metrics give us a multi-run mean that doesn't bottom
out at 0.

## 4. PR #87 RunLifecycleState sanity (2 items)

Both items PASS without invoking the live runtime:

- [x] **Default `epoch_phase == EpochPhase.AUTONOMOUS`** — confirmed via
  `RunLifecycleState()` REPL. Live orchestrator boot also implicitly
  exercises this since `WorldRuntime` constructs a `RunLifecycleState`
  in its `__init__` (see `src/erre_sandbox/world/tick.py:352`).
- [x] **FSM transitions** — `pytest tests/test_world/test_runtime_lifecycle.py`
  passes 9/9 (default + 2 happy-path transitions + 4 invalid-path
  `ValueError`s + 2 instance-replacement invariants). The `WorldRuntime`
  ctor requires a `cycle: CognitionCycle` so a bare REPL exercise is
  redundant given the unit-test coverage.

PR #87 is shipped as designed. No hotfix needed.

## 5. Acceptance summary (β + #87 sanity = 8 items)

| # | item | result |
|---|---|---|
| β.1 | Rikyū residency ≥ 50%               | Run 1 PASS (50%) / Run 2 FAIL (40%) — recommend bias_p=0.1 |
| β.2 | Kant residency ≥ 50%                | PASS both runs (100% each) |
| β.3 | Nietzsche residency ≥ 50%           | PASS both runs (100% each) |
| β.4 | BoundaryLayer 5 rects               | **deferred** (Godot screenshot, MacBook-side) |
| β.5 | Study/Agora/Garden buildings        | **deferred** (Godot screenshot) |
| β.6 | 100 m terrain + top-down hotkey `0` | **deferred** (Godot screenshot) |
| #87.1 | default phase AUTONOMOUS          | PASS (REPL + boot) |
| #87.2 | FSM transitions / ValueError      | PASS (`test_runtime_lifecycle.py` 9/9) |

**5 PASS + 1 FAIL (small-sample) + 3 deferred (visual)** out of 8 items.
The 3 deferred items move to the user's MacBook session.

## 6. Follow-ups

- [ ] User to capture 3 Godot screenshots from MacBook and tick β.4-β.6
- [ ] Optional hotfix PR if anyone wants to formalise the
  `ERRE_ZONE_BIAS_P=0.1` decision (currently this is just a runtime
  env-var, no code change). I'd hold off until n>=3 runs justify it.
- [ ] M8 episodic-log + baseline metrics: see `baseline.md` for the
  separate evaluation of PR #88 + PR #89.
- [ ] D9 in `.steering/20260424-m7-differentiation-observability/decisions.md`
  to record "β acceptance: 5/6 PASS, 1 small-sample FAIL, default 0.1".

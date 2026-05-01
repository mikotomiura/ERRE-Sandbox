# Codex independent review — m9-eval-system P3a-decide natural gating fix

> Codex `gpt-5.5 xhigh` independent review request. Prompt として
> `cat .steering/20260430-m9-eval-system/codex-review-prompt-natural-gating.md
>  | codex exec --skip-git-repo-check` で起動。
> 出力は `codex-review-natural-gating.md` に verbatim 保存。

---

## Context

You are reviewing a bug fix for ERRE-Sandbox m9-eval-system P3a pilot
data collection. The pilot ran on G-GEAR (Windows / RTX 5060 Ti / qwen3:8b
Q4_K_M / Ollama 0.22.0). 3 stimulus cells completed cleanly (focal=198,
total=342, dialogs=168). 3 natural cells **stalled after the initial
burst**:

- kant_natural: 13 min wall, 2 dialogs / 6 focal turns
- nietzsche_natural: 13 min wall, **0 dialogs / 0 focal turns** (starved)
- rikyu_natural: 13 min wall, 3 dialogs / 6 focal turns

CLI is `src/erre_sandbox/cli/eval_run_golden.py` (committed in PR #129).
The natural path constructs a full `WorldRuntime` + `CognitionCycle`
stack with all 3 personas registered in `Zone.AGORA` via
`_initial_state_for_natural` (separate seats inside AGORA).

## Root cause we converged on

`personas/{nietzsche,rikyu}.yaml` set `preferred_zones` that **do not
include AGORA** (Nietzsche=`[peripatos,study,garden]`,
Rikyū=`[chashitsu,garden,study]`). The cognition cycle prompt asks the
LLM to pick a `destination_zone` from `study|peripatos|chashitsu|agora|
garden|null`. When non-null, `_resample_destination_to_persona_zone`
(cognition/cycle.py:828) uses `bias_p` from
`os.environ.get("ERRE_ZONE_BIAS_P", "0.2")` — only 20% of the time does
it bias the destination back to a preferred zone. **80% of the time the
LLM-chosen non-preferred destination is honoured.**

Net: per cognition tick, ≈53% chance an agent moves to a non-AGORA zone.
After 3 ticks, ≈89% chance at least one agent has scattered. The
`InMemoryDialogScheduler.tick()` then sees `_iter_colocated_pairs`
return 0 pairs because `a.zone == b.zone` is no longer satisfied. Open
dialogs run to budget exhaustion (6 turns each), then no new dialog can
admit because no pair is co-located.

This explains the observed pattern exactly: **initial burst of 2-3
dialogs × 6 turns = 12-18 utterances, then plateau**.

## Fix being proposed

`InMemoryDialogScheduler` (frozen Protocol from M4 §7.5) gets a new
keyword-only `eval_natural_mode: bool = False` flag. When True:

1. `tick()` uses a new `_iter_all_distinct_pairs` helper instead of
   `_iter_colocated_pairs`. Every distinct agent pair is eligible
   regardless of zone equality.
2. The reflective-zone skip (`if a.zone not in _REFLECTIVE_ZONES`) is
   bypassed.
3. `schedule_initiate` similarly bypasses the zone-not-reflective reject
   (line 156).

Default `False` keeps M4-frozen behaviour for live multi-agent runs.
CLI opt-in is one keyword in `capture_natural`.

## Invariants explicitly preserved

- `initiator_id == target_id` → reject (programming error)
- Pair already open → second `schedule_initiate` returns None
- `COOLDOWN_TICKS=30` → same pair cannot re-admit within 30 ticks of
  previous close, even with zone bypass
- `AUTO_FIRE_PROB_PER_TICK=0.25` → probability gate still active
- `TIMEOUT_TICKS=6` → in-flight dialog still auto-closes when
  `last_activity_tick` is stale

11 new unit tests in
`tests/test_integration/test_dialog_eval_natural_mode.py` enforce all
the above. Existing 1221 tests still pass (full suite: 1232 passed).

## Diff (verbatim)

### `src/erre_sandbox/integration/dialog.py`

```python
# Constructor signature
def __init__(
    self,
    *,
    envelope_sink: Callable[[ControlEnvelope], None],
    rng: Random | None = None,
    turn_sink: Callable[[DialogTurnMsg], None] | None = None,
    golden_baseline_mode: bool = False,
    eval_natural_mode: bool = False,  # ← NEW
) -> None:
    ...
    self.golden_baseline_mode: bool = golden_baseline_mode
    self.eval_natural_mode: bool = eval_natural_mode  # ← NEW (public)

# schedule_initiate (line 167)
if (
    zone not in _REFLECTIVE_ZONES
    and not self.golden_baseline_mode
    and not self.eval_natural_mode  # ← NEW
):
    return None

# tick (line 299)
self._close_timed_out(world_tick)
if self.eval_natural_mode:
    pair_iter = _iter_all_distinct_pairs(agents)  # ← NEW helper
else:
    pair_iter = _iter_colocated_pairs(agents)
for a, b in pair_iter:
    if not self.eval_natural_mode and a.zone not in _REFLECTIVE_ZONES:
        continue
    key = _pair_key(a.agent_id, b.agent_id)
    if key in self._pair_to_id:
        continue
    last_close = self._last_close_tick.get(key)
    if last_close is not None and world_tick - last_close < self.COOLDOWN_TICKS:
        continue
    if self._rng.random() > self.AUTO_FIRE_PROB_PER_TICK:
        continue
    self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)

# New helper (line 406)
def _iter_all_distinct_pairs(
    agents: Iterable[AgentView],
) -> Iterator[tuple[AgentView, AgentView]]:
    sorted_agents = sorted(agents, key=lambda v: v.agent_id)
    for i, a in enumerate(sorted_agents):
        for b in sorted_agents[i + 1 :]:
            yield a, b
```

### `src/erre_sandbox/cli/eval_run_golden.py` (line 935-947)

```python
scheduler = InMemoryDialogScheduler(
    envelope_sink=runtime.inject_envelope,
    rng=scheduler_rng,
    turn_sink=duckdb_sink,
    golden_baseline_mode=False,
    eval_natural_mode=True,  # ← NEW
)
```

## Specific review asks

Please flag any of the following at HIGH / MEDIUM / LOW severity:

1. **Correctness**: does the diff actually fix the observed gating bug?
   Are there scenarios where the proposed fix still admits 0 pairs?
2. **Invariant preservation**: do cooldown / probability / timeout /
   self-reject / double-open-reject *really* still apply when
   `eval_natural_mode=True`? The test suite covers them but you may
   spot edge cases the tests miss.
3. **Protocol contract**: is the keyword-only `__init__` flag a clean
   extension to the M4-frozen `DialogScheduler` Protocol? The Protocol
   only fixes `schedule_initiate / record_turn / close_dialog`
   signatures, not `__init__` — but is the convention here clean?
4. **Naming**: `eval_natural_mode` vs alternatives (`relax_zone_gate`,
   `proximity_free`, `eval_logical_co_location`). The mode is set only
   for eval natural-condition capture, but the flag name should be
   readable to a future reader who has no eval context.
5. **Alternative fixes** considered and rejected (see
   design-natural-gating-fix.md):
   - Override persona `preferred_zones=[AGORA]` in CLI alone — rejected
     because `ERRE_ZONE_BIAS_P=0.2` default still leaks ~53% of the time
   - Drop MoveMsg in `WorldRuntime` for eval — rejected, world-layer
     eval-only knob would be invasive
   - Force `ERRE_ZONE_BIAS_P=1.0` env var + preferred override — env
     mutation is hacky, low diagnosability
   - Add explicit "eval pair set" frozenset API — rejected as more
     complex than a boolean flag
6. **Risk**: any way the diff breaks live multi-agent (M5/M6) runs that
   default `eval_natural_mode=False`?
7. **Future maintainability**: does the diff make the dialog scheduler's
   responsibility surface more confusing (now 2 boolean flags affecting
   semantically-similar bypass paths)?
8. **Re-capture confidence**: assuming the fix is shipped to G-GEAR, do
   you expect the 30-target-focal natural cell to complete within
   30-60 min wall? Any reason to expect a different gating bug to
   emerge once this one is fixed?

## Out of scope for this review

- LoRA training (M9-B) interaction — orthogonal milestone
- Tier B / Tier C metrics — not touched
- bootstrap CI (P5) — separate prep work in this same Mac session
- M9-A event boundary observability — already merged

## Format

Reply with HIGH / MEDIUM / LOW sections, then a final **Verdict: ship /
ship-with-edits / block** line. If you flag HIGH, please include enough
context that I can edit before merging.

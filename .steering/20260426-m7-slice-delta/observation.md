# M7 Slice δ — Observation Log

## Formula calibration (post-implementation)

The δ semi-formula tunables in ``src/erre_sandbox/cognition/relational.py``
landed at the following values after the C5 simulation calibration:

| Tunable | Value | Source |
|---|---|---|
| ``_DECAY_BASE`` | 0.02 | design-final Axis 1a |
| ``_DECAY_NEURO_COEFF`` | 0.06 | design-final Axis 1a (neuroticism-coupled) |
| ``_WEIGHT_BASE`` | 0.5 | design-final Axis 1c |
| ``_WEIGHT_EXTRA_COEFF`` | 1.0 | design-final Axis 1c (extraversion 0.5-1.5) |
| ``_IMPACT_ADDRESSEE_WEIGHT`` | 0.08 | C5 calibration retune (was 0.6 in C3) |
| ``_IMPACT_LENGTH_WEIGHT`` | 0.04 | C5 calibration retune (was 0.4 in C3) |
| ``_IMPACT_LENGTH_TARGET`` | 200 | utterance length saturation point |
| antagonism magnitude (kant↔nietzsche) | -0.10 | C5 calibration retune (was -0.30 in C3) |

### Why the C3 → C5 retune

The first-pass C3 values (impact 0.6/0.4, antagonism -0.30) saturated the
recurrence in 1-2 turns, making the belief-promotion threshold (0.45)
meaningless — every dyad with non-trivial impact would qualify on turn 1.
The C5 simulation regression test
(``tests/test_cognition/test_relational_simulation.py``) caught this and
drove the retune. New behaviour:

* kant→nietzsche (antagonism path) crosses ``|affinity|>0.45`` at ~turn 6.
* kant→rikyu (positive path) crosses at ~turn 7.
* nietzsche→rikyu (positive path) crosses at ~turn 9.
* All within the design-final window of 6-14 turns.

## Per-pair simulation snapshots

Computed via ``_simulate(...)`` over 20 turns from ``prev=0.0`` (no
real-world noise; deterministic recurrence only):

| Pair (speaker→addressee) | Crossing turn | Final affinity (turn 20) |
|---|---|---|
| kant → nietzsche | 6 | -0.79 (clamps toward -1) |
| kant → rikyu | 7 | +0.65 (sub-saturation) |
| nietzsche → rikyu | 9 | +0.51 (sub-saturation) |

The negative pair saturates harder because antagonism stacks the same
direction every turn; the positive pairs are bounded by the small
structural impact (max 0.12 per turn).

## Belief promotion thresholds

| Constant | Value | Module |
|---|---|---|
| ``BELIEF_THRESHOLD`` | 0.45 | ``cognition/belief.py`` |
| ``BELIEF_MIN_INTERACTIONS`` | 6 | ``cognition/belief.py`` |
| ``_TRUST_FLOOR`` | 0.70 | ``cognition/belief.py`` (trust/clash boundary) |

Classification mapping (from ``_classify_belief``):

| affinity range | belief_kind |
|---|---|
| ≥ 0.70 | trust |
| 0.0 < affinity < 0.70 | curious |
| -0.70 < affinity < 0.0 | wary |
| ≤ -0.70 | clash |
| ambivalent | reserved (history-aware classification, m8+) |

## Negative-path emotional_conflict cycle

| Constant | Value | Module |
|---|---|---|
| ``_NEGATIVE_DELTA_TRIGGER`` | -0.05 | ``world/tick.py`` |
| ``_EMOTIONAL_CONFLICT_GAIN`` | 0.5 | ``world/tick.py`` (per-event coefficient) |
| ``_EMOTIONAL_CONFLICT_DECAY`` | 0.02 | ``cognition/state.py`` (per-tick decay) |

A single -0.10 antagonism turn raises emotional_conflict by 0.05 (clamped).
Decay returns it to 0 in ~3 ticks if no further negative event reinforces
it. The kant↔nietzsche pair, sustained for 12 turns, accumulates conflict
to ~0.6 before decay catches up.

## Acceptance gate (Mac-side, deterministic)

All five C8 acceptance assertions pass via
``tests/test_integration/test_slice_delta_e2e.py``:

* ✅ both signs of delta observed (kant↔nietzsche negative)
* ✅ ``Physical.emotional_conflict`` > 0 for both sides after antagonism
* ✅ ``RelationshipBond.last_interaction_zone`` set per turn
* ✅ ≥1 belief promotion in ``semantic_memory`` with ``belief_kind`` populated
* ✅ deterministic upsert id (≤ 2 distinct rows for the kant↔nietzsche pair)

## Live G-GEAR run (landed — 5/5 PASS at run-02, run-01 retained as history)

**Final verdict: 5/5 PASS** via run-02 (option A: ``--duration 360``). Run-01
(122s) hit 4/5 with gate 2 falling short; run-02 (360s) flipped gate 2 by
giving the kant↔nietzsche antagonist pair enough recurrence to cross
|affinity| > 0.45. See ``.steering/20260426-m7-delta-live-fix/decisions.md``
for the option-A-success decision and the corrected duration window in
``run-guide-delta.md``.

### Run-02 (option A — landed, gate 2 flips)

``run-02-delta/`` on G-GEAR (RTX 5060 Ti 16GB / Ollama 0.21.2 / qwen3:8b),
2026-04-26 17:08-17:14 UTC+9, ``ERRE_ZONE_BIAS_P=0.1``,
``--personas kant,nietzsche,rikyu``, ``--db var/run-delta.db``, 362.07s elapsed,
**no code change vs main HEAD** (PR #97 + scaffold only).

| kind | count |
|---|---|
| world_tick | 190 |
| agent_update | 57 |
| speech / animation / reasoning_trace | 56 each |
| move | 54 |
| reflection_event | 11 |
| **dialog_turn** | **12** |
| dialog_initiate / dialog_close | 2 each |
| world_layout | 1 |
| **total** | **497** |

| table | rows |
|---|---|
| dialog_turns | 12 |
| relational_memory | 12 |
| episodic_memory | 41 |
| semantic_memory | 12 |
| procedural_memory | 0 |
| **belief_promotions (kind ≠ NULL)** | **1** |

Sole belief promotion: ``kant`` → ``wary`` toward ``nietzsche`` at
``confidence = 0.471`` — matches peak |affinity| = 0.471 (negative path,
``< -0.45``) and the C5 simulation prediction that the kant↔nietzsche
antagonist pair crosses earliest. The two positive paths (kant↔rikyu,
nietzsche↔rikyu) topped at +0.34 / +0.34, below the 0.45 threshold,
which is consistent with simulation; positive promotions would need
turn 7-9 per-dyad accumulation that the run-02 dialog distribution did
not provide.

| # | Gate | Result | Observed |
|---|---|---|---|
| 1 | ``db.table_counts.dialog_turns`` ≥ 3 | ✅ PASS | 12 |
| 2 | ``db.belief_promotions`` non-empty | ✅ **PASS (flipped)** | 1 (kant wary→nietzsche, conf 0.47) |
| 3 | ``journal.bonds_with_last_interaction_zone`` > 0 | ✅ PASS | 56/56 |
| 4 | ``journal.max_emotional_conflict_observed`` > 0 | ✅ PASS | 0.1154 |
| 5 | both signs of affinity present | ✅ PASS | 34 pos / 22 neg |

**Verdict: 5/5 PASS.** Option A succeeded with no code change — the
122s window in run-guide-delta.md was overoptimistic relative to the
formula's recurrence pace; 360s gives ≥1 dyad enough turns to cross.

### Surprising distribution detail

run-02 had **fewer** total dialog_turns (12) than run-01 (17), but more
**concentration**: 2 dialogs ran to dialog_close (vs run-01's 3 dialogs
producing 17 turns). The kant↔nietzsche pair received 4 antagonist
turns with ``ichigo_ichie_count`` reaching 3 — the recurrence multiplier
was the deciding factor, not raw turn volume. This is consistent with
the C5 simulation: antagonism stacks the same direction every turn,
saturating faster than the diffuse positive paths.

### Run-01 (history — first attempt, 4/5, retained for traceability)

#### Envelope tally (probe ``run-01.jsonl.summary.json``)

| kind | count |
|---|---|
| world_tick | 60 |
| agent_update / speech / animation / reasoning_trace | 18 each |
| dialog_turn | **17** |
| move | 17 |
| reflection_event | 3 |
| dialog_initiate | 3 |
| world_layout | 1 |
| **total** | **173** |

Schema version on the wire: ``0.7.0-m7d`` (matches PR #95).

#### DB tally (``run-01.db_summary.json``)

| table | rows |
|---|---|
| dialog_turns | 17 |
| relational_memory | 17 |
| episodic_memory | 12 |
| semantic_memory | 3 |
| procedural_memory | 0 |
| **belief_promotions (kind ≠ NULL)** | **0** |

#### Gate verdict (run-01)

| # | Gate | Result | Observed |
|---|---|---|---|
| 1 | ``db.table_counts.dialog_turns`` ≥ 3 | ✅ PASS | 17 |
| 2 | ``db.belief_promotions`` non-empty | ❌ **FAIL** | 0 (peak \|affinity\| = 0.358 < 0.45 threshold) |
| 3 | ``journal.bonds_with_last_interaction_zone`` > 0 | ✅ PASS | 28 (= 28/28 bonds carry the zone stamp) |
| 4 | ``journal.max_emotional_conflict_observed`` > 0 | ✅ PASS | 0.082 (negative path fired ≥1 time) |
| 5 | both signs of affinity present | ✅ PASS | 20 positive / 8 negative bond samples |

run-01 verdict: **4/5 — gate 2 missed.** Diagnosis below; remediation
landed via run-02 above.

#### Diagnosis (gate 2 at run-01, retained)

* Live affinity peaks: **+0.358** (positive) / **-0.324** (negative). Both
  below the ``BELIEF_THRESHOLD = 0.45`` from ``cognition/belief.py``.
* Per-dyad turn budget in 120s: 17 dialog_turns / 6 directional pairs (3
  personas × 2 directions) ≈ **2.8 turns/dyad** — but the C5 simulation
  in observation.md predicts crossing at turn **6 (kant↔nietzsche)** /
  **7 (kant→rikyu)** / **9 (nietzsche→rikyu)**.
* The deterministic e2e suite hits the threshold by stacking many turns on
  a single dyad with antagonism guaranteed every turn; the live run spreads
  turns across all dyads, dilutes antagonism with curiosity-mode openings,
  and the rikyu-side bonds saturate slower than the simulation because
  utterances are shorter than the 200-char saturation point.
* No 5th-gate-style hardware/runtime bug was observed — formula and
  ``last_interaction_zone`` plumbing both held up under live LLM noise.

#### Side-observations (informational, not gates)

* ``EXPLAIN QUERY PLAN`` (γ-run latency claim) was **not** measured in this
  run; left for ε if/when it becomes load-relevant.
* Godot ``ReasoningPanel`` screenshot: deferred to MacBook side per
  M7-β/M7-γ split (``project_m7_beta_baseline_frozen.md`` memory).
* Gateway logged one ``WebSocketDisconnect (code 1000)`` as ``ERROR`` in
  ``_recv_loop`` (``gateway.py:415``). Symptom is benign (clean MacBook
  disconnect surfacing as TaskGroup error); cosmetic log-noise residual,
  recorded in the live-fix task dir.

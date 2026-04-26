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

## Live G-GEAR run (landed — 4/5 PASS, 1 δ-residual handed to ε)

**Run-01** — ``run-01-delta/`` on G-GEAR (RTX 5060 Ti 16GB / Ollama 0.21.2 / qwen3:8b),
2026-04-26 16:48-16:51 UTC+9, ``ERRE_ZONE_BIAS_P=0.1``,
``--personas kant,nietzsche,rikyu``, ``--db var/run-delta.db``, 122.09s elapsed.

### Envelope tally (probe ``run-01.jsonl.summary.json``)

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

### DB tally (``run-01.db_summary.json``)

| table | rows |
|---|---|
| dialog_turns | 17 |
| relational_memory | 17 |
| episodic_memory | 12 |
| semantic_memory | 3 |
| procedural_memory | 0 |
| **belief_promotions (kind ≠ NULL)** | **0** |

### Gate verdict

| # | Gate | Result | Observed |
|---|---|---|---|
| 1 | ``db.table_counts.dialog_turns`` ≥ 3 | ✅ PASS | 17 |
| 2 | ``db.belief_promotions`` non-empty | ❌ **FAIL** | 0 (peak \|affinity\| = 0.358 < 0.45 threshold) |
| 3 | ``journal.bonds_with_last_interaction_zone`` > 0 | ✅ PASS | 28 (= 28/28 bonds carry the zone stamp) |
| 4 | ``journal.max_emotional_conflict_observed`` > 0 | ✅ PASS | 0.082 (negative path fired ≥1 time) |
| 5 | both signs of affinity present | ✅ PASS | 20 positive / 8 negative bond samples |

**Verdict: 4/5 — gate 2 missed.** Per ``run-guide-delta.md`` Step 7, observation.md
records the actual numbers but **does not** relax the gate; the failing path
is recorded as a δ-residual at ``.steering/20260426-m7-delta-live-fix/``
and handed to slice ε.

### Diagnosis (gate 2)

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

### Side-observations (informational, not gates)

* ``EXPLAIN QUERY PLAN`` (γ-run latency claim) was **not** measured in this
  run; left for ε if/when it becomes load-relevant.
* Godot ``ReasoningPanel`` screenshot: deferred to MacBook side per
  M7-β/M7-γ split (``project_m7_beta_baseline_frozen.md`` memory).
* Gateway logged one ``WebSocketDisconnect (code 1000)`` as ``ERROR`` in
  ``_recv_loop`` (``gateway.py:415``). Symptom is benign (clean MacBook
  disconnect surfacing as TaskGroup error); cosmetic log-noise residual,
  recorded in the live-fix task dir.

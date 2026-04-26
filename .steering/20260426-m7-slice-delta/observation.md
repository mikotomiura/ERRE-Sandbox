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

## Live G-GEAR run (pending)

The live ``uv run erre-sandbox --personas kant,nietzsche,rikyu --db var/run-delta.db``
acceptance run requires the RTX hardware (G-GEAR machine) and is left for
the user to dispatch. Expected observations from a 90-120s run:

* dialog_turn ≥ 3 (typically 6-12 turns across 2-3 dialogs)
* both signs of bond.affinity delta in time-series
* belief promotion in ``semantic_memory`` table with ``belief_kind`` populated
* ``recent_peer_turns`` p95 latency < γ Run-1 baseline (verify via
  ``EXPLAIN QUERY PLAN`` showing ``LIMIT`` push to SQLite)
* Godot ReasoningPanel screenshot showing ``"last in <zone> @ tick T"``

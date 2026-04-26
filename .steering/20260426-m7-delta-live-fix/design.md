# Design — M7 Slice δ Live Residual (Gate 2 Miss)

> Scaffold only. Plan mode (Opus + ``/reimagine``) is required before any
> code change here. This file enumerates the candidate causes and the
> minimum data needed to choose between them.

## Observed numbers (run-01)

* dialog_turn = 17, spread across 6 directional pairs (3 personas × 2
  directions) ≈ **2.8 turns / dyad**
* Peak |affinity| live = **0.358 (positive, kant↔rikyu after ~3 turns)**
  / **-0.324 (negative, kant↔nietzsche after ~3 turns)**
* ``BELIEF_THRESHOLD = 0.45`` (``cognition/belief.py``)
* ``BELIEF_MIN_INTERACTIONS = 6``
* C5 simulation crossing turns: 6 / 7 / 9 (deterministic, no LLM noise)

## Candidate causes (rank-ordered, most-likely first)

### A. Run is simply too short for the formula's recurrence

**Diagnosis fit**: Strong. The C5 simulation needs ~6-9 deterministic turns
to cross 0.45; live runs add LLM noise (curiosity-mode utterances, varying
length, addressee variance) that should *slow* convergence further. 17
turns ÷ 6 dyads = ~3 turns/dyad is short by a factor of ~2-3×.

**Test**: Re-run with ``--duration 360`` or ``--duration 600`` and see
whether ≥1 dyad crosses. Expect 60-90s × ~3 = **~30-50 dialog_turns** =
**~5-8 turns/dyad** to cross.

**Risk**: VRAM / qwen3:8b stability over a 5-10 minute run. Likely fine on
G-GEAR (16GB free, 5.2GB model).

### B. ``_IMPACT_*`` retune (C5) is now under-calibrated for live LLM

**Diagnosis fit**: Moderate. The C5 retune dropped impact 0.6→0.08 and
0.4→0.04 to stop turn-1 saturation in the *deterministic* simulation. Live
LLM utterances are shorter than the 200-char saturation point and contain
softer antagonism than the deterministic test, so the per-turn delta is
**smaller** than the simulation predicts.

**Test**: Measure live mean ``|delta_per_turn|`` from journal time-series.
If << 0.05/turn (simulation expectation), the live recurrence is even slower
than the simulation. If ~0.05/turn, A explains it on its own and B is not
needed.

**Risk**: Re-tuning impact upward re-introduces the C3 turn-1 saturation
problem if not carefully tested against the simulation regression.

### C. ``BELIEF_THRESHOLD`` is mis-calibrated for live runs

**Diagnosis fit**: Weak. 0.45 was chosen against the C5 simulation (crossing
at turn 6-9, well within the design window). Lowering it to 0.30 would be
ad-hoc unless we can defend it from the cognitive-science side
(``persona-erre`` skill).

**Test**: Read current ``persona-erre`` notes on belief-formation thresholds
and confirm whether 0.30-0.40 has any prior justification. If not, do not
go this route — defer to A or B.

**Risk**: Trust/curious/wary classification thresholds (0.70 / 0.0 / -0.70)
also need re-thinking if the master threshold moves.

### D. ``BELIEF_MIN_INTERACTIONS = 6`` blocks promotion even after threshold

**Diagnosis fit**: Possible secondary cause. Even if A is fixed and a dyad
crosses 0.45 by turn 5, promotion still waits for turn 6. With 17 total
turns spread over 6 dyads, no dyad in run-01 had 6 interactions to begin
with — so D is gated on A.

**Test**: After fixing A (longer run), check whether the first dyad to
cross 0.45 also has interaction_count ≥ 6 simultaneously. If yes, D is a
non-issue.

## Recommended sequence (Plan mode)

1. **Cheapest first**: re-run live with ``--duration 360`` (option A test).
   No code change. ~6 minutes wall-clock + ~2 minutes setup.
2. If A alone flips gate 2 → record in ``decisions.md`` ("δ live gate 2
   needs ≥360s; 120s window in run-guide was overoptimistic"), update the
   run-guide's expected window, no code change.
3. If A does **not** flip gate 2 → measure mean delta/turn (B test) and
   decide between B (re-tune) and C (lower threshold).
4. If neither A nor B/C flip it cleanly → defer to ε with a restated
   acceptance window (e.g. "≥1 belief promotion in a 6-minute 2-persona
   run").

## Test strategy

* No new pytest required for option-A path; the e2e suite remains the
  contract for the formula.
* If option B (re-tune) is taken, ``test_relational_simulation.py`` must
  keep passing — that test pins the C5 calibration. Any retune must
  re-derive the simulation crossing turns.
* Live re-run uses the same probe + db_summary scripts under
  ``.steering/20260426-m7-slice-delta/run-02-delta/`` (don't reuse
  run-01-delta).

## Side-observations (out of scope, recorded for ε)

* Gateway log: ``WebSocketDisconnect (code 1000)`` raised inside
  ``TaskGroup`` in ``gateway.py:415`` produces an ``ERROR`` line per
  clean MacBook disconnect. Should be caught and demoted to ``DEBUG``
  (or ``INFO`` "session closed cleanly"). Pure log-noise — does not
  affect data — but pollutes acceptance triage.

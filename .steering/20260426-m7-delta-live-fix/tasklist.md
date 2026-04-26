# Tasklist — M7 Slice δ Live Residual (Gate 2)

## Pre-flight

- [x] Read ``.steering/20260426-m7-slice-delta/observation.md`` "Live G-GEAR run (landed)"
- [x] Read ``.steering/20260426-m7-slice-delta/run-01-delta/run-01.db_summary.json``
- [x] Read this dir's ``requirement.md`` + ``design.md``
- [x] Confirm Plan mode + Opus + ``/reimagine`` cadence per CLAUDE.md
      → Plan landed at ``C:\Users\johnd\.claude\plans\ok-merge-typed-bubble.md``,
      reimagine skipped (option A is a non-design execution path; full
      reimagine reserved for B/C if needed)

## Plan mode (Opus + /reimagine)

- [x] Write plan choosing option A (cheapest, no code change)

## Option A path (cheapest) — **EXECUTED AND SUCCEEDED**

- [x] Re-run on G-GEAR with ``--duration 360`` (no code change)
      → 362.07s elapsed, 497 envelopes, 12 dialog_turns, peak |affinity| 0.471
- [x] Land artifacts under ``.steering/20260426-m7-slice-delta/run-02-delta/``
- [x] Update ``observation.md`` with run-02 numbers + flip gate 2 verdict
      → 5/5 PASS recorded, run-01 retained as history
- [x] Update ``run-guide-delta.md`` with the corrected duration window
      → Step 3 now states ``--duration 360`` minimum; artifact paths
      generalised to ``run-NN-delta/run-NN.*``
- [x] Commit on a fresh branch ``chore/m7-delta-live-fix`` (not the
      verdict branch — keep run-01 verdict immutable)

## Option B path (formula retune) — **NOT EXERCISED (option A succeeded)**

- [ ] Measure mean ``|delta_per_turn|`` from run-01 journal time-series
- [ ] Propose new ``_IMPACT_*`` values
- [ ] Rerun ``test_relational_simulation.py`` against proposed values;
      crossing turns must stay in the 6-14 design window
- [ ] Re-run all of ``tests/test_cognition/`` + ``test_slice_delta_e2e.py``
- [ ] Live re-run, same artifact path as option A
- [ ] PR on ``feat/m7-delta-formula-retune``

## Option C path (threshold lower) — **NOT EXERCISED (option A succeeded)**

- [ ] Justify with ``persona-erre`` skill notes
- [ ] Update ``cognition/belief.py`` constants
- [ ] Re-classify trust/curious/wary boundaries if master threshold moves
- [ ] Pytest suite full pass
- [ ] Live re-run + observation.md update

## Defer-to-ε path — **NOT EXERCISED (option A succeeded)**

- [ ] Write ``decisions.md`` "deferred to ε" with reasoning
- [ ] Add new acceptance criterion to ε task dir's ``requirement.md``
      (when ε starts)
- [ ] Close this task by referencing the deferral commit

## Side-residual (gateway log noise) — **DEFERRED to ε per D2**

- [ ] Catch ``WebSocketDisconnect`` inside ``gateway.py:_recv_loop``
      TaskGroup; demote clean closure to DEBUG/INFO
- [ ] Add a small unit test that simulates clean WS close
- [ ] Bundle into ε's gateway hygiene work, not into this PR
      (decision recorded in ``decisions.md`` D2 — keep logging
      signature stable across run-01/run-02/future runs for
      comparability)

## Verification — **PASSED at run-02**

- [x] run-02 db_summary shows belief_promotions ≥ 1 with non-NULL
      ``belief_kind`` for ≥1 row
      → 1 row: ``kant`` ``wary`` toward ``nietzsche`` at conf 0.471
- [x] Acceptance verdict in observation.md flips to 5/5 PASS
- [x] No regression in slice-δ e2e (``test_slice_delta_e2e.py`` 5/5
      pre-run smoke)

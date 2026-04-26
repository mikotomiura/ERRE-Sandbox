# Tasklist — M7 Slice δ Live Residual (Gate 2)

## Pre-flight

- [ ] Read ``.steering/20260426-m7-slice-delta/observation.md`` "Live G-GEAR run (landed)"
- [ ] Read ``.steering/20260426-m7-slice-delta/run-01-delta/run-01.db_summary.json``
- [ ] Read this dir's ``requirement.md`` + ``design.md``
- [ ] Confirm Plan mode + Opus + ``/reimagine`` cadence per CLAUDE.md

## Plan mode (Opus + /reimagine)

- [ ] Write ``design-final.md`` choosing one of: option A (longer run),
      option B (impact retune), option C (threshold lower), defer-to-ε
- [ ] If B/C, justify against ``persona-erre`` skill + C5 simulation regression

## Option A path (cheapest)

- [ ] Re-run on G-GEAR with ``--duration 360`` (no code change)
- [ ] Land artifacts under ``.steering/20260426-m7-slice-delta/run-02-delta/``
- [ ] Update ``observation.md`` with run-02 numbers + flip gate 2 verdict
- [ ] Update ``run-guide-delta.md`` with the corrected duration window
- [ ] Commit on a fresh branch ``chore/m7-delta-live-fix`` (not the
      verdict branch — keep run-01 verdict immutable)

## Option B path (formula retune)

- [ ] Measure mean ``|delta_per_turn|`` from run-01 journal time-series
- [ ] Propose new ``_IMPACT_*`` values
- [ ] Rerun ``test_relational_simulation.py`` against proposed values;
      crossing turns must stay in the 6-14 design window
- [ ] Re-run all of ``tests/test_cognition/`` + ``test_slice_delta_e2e.py``
- [ ] Live re-run, same artifact path as option A
- [ ] PR on ``feat/m7-delta-formula-retune``

## Option C path (threshold lower)

- [ ] Justify with ``persona-erre`` skill notes
- [ ] Update ``cognition/belief.py`` constants
- [ ] Re-classify trust/curious/wary boundaries if master threshold moves
- [ ] Pytest suite full pass
- [ ] Live re-run + observation.md update

## Defer-to-ε path

- [ ] Write ``decisions.md`` "deferred to ε" with reasoning
- [ ] Add new acceptance criterion to ε task dir's ``requirement.md``
      (when ε starts)
- [ ] Close this task by referencing the deferral commit

## Side-residual (gateway log noise)

- [ ] Catch ``WebSocketDisconnect`` inside ``gateway.py:_recv_loop``
      TaskGroup; demote clean closure to DEBUG/INFO
- [ ] Add a small unit test that simulates clean WS close
- [ ] Bundle into whichever PR ships first (option A re-run is fine —
      no formula coupling)

## Verification

- [ ] If a fix lands, run-02 db_summary shows belief_promotions ≥ 1
      with non-NULL ``belief_kind`` for ≥1 row
- [ ] Acceptance verdict in observation.md flips to 5/5 PASS
- [ ] No regression in ``tests/`` (target keeps the M7-δ pass count)

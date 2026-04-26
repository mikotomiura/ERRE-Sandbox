# Requirement — M7 Slice δ Live G-GEAR Residual (Gate 2 Miss)

## Background

The δ live G-GEAR acceptance run on 2026-04-26 (run-01, 122s, kant+nietzsche+rikyu)
landed 4/5 gates but **missed gate 2: belief_promotions non-empty**. See
``.steering/20260426-m7-slice-delta/observation.md`` "Live G-GEAR run (landed)"
for the full numbers.

Per ``run-guide-delta.md`` Step 7 — *do not edit observation.md to relax
expectations* — the failing gate is recorded here and handed to slice ε
(or fixed in a small follow-up if scope permits).

## Goal

Decide whether **gate 2** (belief_promotions ≥ 1 in a 90-120s 3-persona run)
is achievable as-is, or whether the formula / threshold / run shape must be
adjusted. End-state is one of:

1. **(fix)** A documented configuration change (e.g. tuned ``BELIEF_THRESHOLD``,
   tuned ``_IMPACT_*`` weights, smaller persona set, longer run) that makes
   gate 2 reliably reach in a live run, **without** invalidating the C5
   simulation regression test or the deterministic e2e suite.
2. **(defer)** A judgement that the gate as written is too tight for a 120s
   3-persona live run and is properly an ε-slice success criterion (e.g.
   "belief promotion observable within 6 minutes of live wall-clock"), with
   the new acceptance criterion landed alongside ε design.

Either outcome must be commit-tracked; option 1 needs a re-run of the live
acceptance to demonstrate the gate now lands.

## Out of scope

* Touching the deterministic e2e suite (``test_slice_delta_e2e.py``) —
  it already passes on Mac and G-GEAR.
* Re-tuning the C5 simulation regression test — the C5 calibration was
  validated by the ``test_relational_simulation.py`` regression and that
  must keep passing.
* Cosmetic gateway log-noise (``WebSocketDisconnect`` surfacing as
  ``ERROR`` in ``_recv_loop``) — recorded as a side-observation only,
  separate residual.

## Acceptance

* This task dir documents the candidate causes (see ``design.md``).
* Either a fix lands on a new branch with a re-run that flips gate 2 to
  PASS (and the new run-02 lands under
  ``.steering/20260426-m7-slice-delta/run-02-delta/``), or a deferral
  decision is recorded in ``decisions.md`` and the gate is restated in
  the ε task dir's ``requirement.md``.
* The gateway-disconnect side-observation is recorded under
  ``blockers.md`` (informational; not a gate) so it is not lost when ε
  starts.

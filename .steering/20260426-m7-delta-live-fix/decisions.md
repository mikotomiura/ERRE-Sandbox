# Decisions — M7 Slice δ Live Residual

## D1 — Option A succeeded; gate 2 flips on a 360s re-run with no code change

**Decision (2026-04-26)**: The δ live G-GEAR acceptance gate 2
(``belief_promotions`` non-empty) is achievable with the formula and
threshold values already on ``main`` (PR #95 + #96 + #97). The 90-120s
duration window in ``run-guide-delta.md`` was overoptimistic relative to
the recurrence pace of ``cognition/relational.py``; ``--duration 360``
gives ≥1 dyad enough turns to cross |affinity| > 0.45.

**Evidence (run-02 vs run-01)**:

| metric | run-01 (122s) | run-02 (362s) |
|---|---|---|
| dialog_initiate | 3 | 2 |
| dialog_turn | 17 | 12 |
| peak |affinity| | 0.358 | **0.471** |
| belief_promotions | 0 | **1** |
| max emotional_conflict | 0.082 | 0.115 |
| affinity sign distribution | 20 / 8 | 34 / 22 |

The single belief promotion at run-02 is **kant → wary about nietzsche**
at confidence 0.471. The kant↔nietzsche antagonist pair was driven by
``ichigo_ichie_count`` reaching 3 (vs run-01's 1-2), letting the
recurrence multiplier saturate the negative path.

**Surprise**: run-02 had **fewer** total dialog_turns (12) than run-01
(17). The win came from **concentration**, not volume — 2 dialogs that
each ran longer (closer to the dialog_turn_budget cap of 6) gave one
dyad enough recurrence to cross. Implication: live-acceptance design
should favour **fewer, longer dialogs on stable proximity** rather than
maximising total turn count. This is consistent with the C5 simulation,
which models pure-recurrence accumulation without proximity churn.

**Outcome**:

* ``observation.md`` updated with the run-02 5/5 PASS verdict; run-01
  retained as 4/5 history.
* ``run-guide-delta.md`` Step 3 corrected: ``--duration 360`` minimum;
  artifact paths use ``run-NN-delta/run-NN.*`` template instead of
  hard-coded ``run-01-delta``.
* Options B (impact retune) and C (threshold lower) **not exercised** —
  unnecessary at this point. Both remain on file in ``design.md`` for
  future runs that vary persona count or run length.
* δ formula calibration ( ``_IMPACT_*``, ``_DECAY_*``, antagonism table,
  ``BELIEF_THRESHOLD``, ``BELIEF_MIN_INTERACTIONS``) is **frozen** at the
  C5 retune values for slice ε baseline reference, mirroring the M7-β
  freeze pattern.

## D2 — Side-residual deferred (gateway WebSocketDisconnect log noise)

The ``WebSocketDisconnect (code 1000)`` ERROR log from
``gateway.py:_recv_loop`` inside ``TaskGroup`` reproduced cleanly in
run-02 (one occurrence on session ``3e7ff23b02210445``). Cosmetic
log-noise only; does not affect data quality or any gate.

**Decision**: Not bundled into the run-02 PR. Filed to ε as a separate
small fix task. Catching ``WebSocketDisconnect`` inside the TaskGroup
and demoting clean closure to ``DEBUG``/``INFO`` is independent from
formula and acceptance work, and the next live runs need to keep the
same logging signature for comparability. ε can pick this up alongside
other gateway hygiene.

## D3 — One-off LLM unparseable plan tolerated

run-02 logged one ``WARNING: LLM returned unparseable plan for agent
a_nietzsche_001 (len=345) — fallback`` at ``17:12:01``. Fallback
worked; no downstream effect on bonds, affinity, or belief promotion.

**Decision**: Tolerated as expected occasional LLM JSON parse flake.
Not a regression; not blocking. If this rate increases (e.g. >2% of
plan calls in future runs), revisit with persona-erre Skill to tighten
the system prompt; for now logged for awareness only.

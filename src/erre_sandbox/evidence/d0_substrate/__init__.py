"""M13-SUB1 D0 pack — structural conformance track (design-final.md, FROZEN §9).

Deterministic, GPU/LLM-free measurement-prevalidation apparatus: does a
complexity ladder over the situated-3D substrate (:mod:`ladder`, R0->R3) let
this codebase's runtime measure richer-than-ES-1 structure **non-
circularly**, before any sealed outcome-contrast run is attempted? This is
the **structural** half of the two-layer D0 pack
(``.steering/20260701-m13-sub1-d0-pack/design-final.md`` §0); the semantic
track (fork C, reference-free-originality LAO prevalidation) is out of scope
here (``.steering/20260702-m13-sub1-d0-structural/requirement.md`` — corpus
materialization gate unresolved) and reported as unevaluated in
:mod:`verdict_report`.

The package is **USE-only** over the frozen core: :mod:`constants` /
:mod:`stub` / :mod:`ladder` / :mod:`verdict_report` never import
``cognition`` or real ``world`` runtime code (world geometry is **mirrored**,
the same discipline as :mod:`erre_sandbox.evidence.spdm` /
:mod:`erre_sandbox.evidence.es3_locomotion`); :mod:`smoke` is the one module
that legitimately touches real ``world.physics`` (see its docstring, DA-D0S-5,
for why it still avoids ``world.tick``'s transitive ``cognition`` import).

**Claim boundary** (design-final.md §6, over-claim guard): ``STRUCTURAL_READY``
means substrate wiring + measurement capability have been demonstrated
non-circularly (necessary-substrate + measurement-capability, ES-1/ES-3
style) — **G-GEAR runtime-ready**, not Godot render-ready, and *not* a test
of the divergence hypothesis. ES-1 / ES-3 supply target/wiring only; their
own GO verdicts are never re-cited here as divergence evidence.

**Falsifiability (the design's central guarantee)**, mirroring the frozen
ES-1/ES-3 apparatus discipline:

* the D0a blind trace generator (:mod:`stub`) is seed-as-only-freedom — no
  stickiness / dwell / bias knob a designer could turn;
* every rung carries a **structure-destroying null** (collapses toward 0)
  and a **situated-function control** (collapses toward 0 by construction,
  proving the estimator itself is not vacuously always positive);
* the **anti-ES-1-collapse gate** (R1+, design-final.md §2 #5, the most
  load-bearing gate in this package) requires the seed-paired residual
  ``Delta_r = D_r - D_r^quantized`` to clear its own floor with a one-sided
  bootstrap CI, so a rung cannot pass by silently re-measuring ES-1's own
  discrete-zone substrate;
* verdict values are never pinned in a test — only branch logic is, over
  synthetic fixtures (circular re-baking guard).
"""

from __future__ import annotations

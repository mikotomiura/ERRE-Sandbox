"""M13 running-substrate track — minimal closed-loop running D0a re-run.

This sibling package is the **only new part** the running-substrate ADR
(`.steering/20260703-m13-running-impl-adr/design-final.md`, FROZEN §10) adds
on top of the frozen D0a structural apparatus
(:mod:`erre_sandbox.evidence.d0_substrate`): a **running-trace generator**
(:mod:`policy`) that drives a deterministic no-LLM agent policy over the real
:func:`erre_sandbox.world.physics.step_kinematics` + memory store, producing a
:class:`~erre_sandbox.evidence.d0_substrate.stub.Trace3D` whose within-zone
memory geometry is a **consequence of the agent's own history** (frozen replay
でない), then re-runs the byte-identical frozen R0->R3 ladder readout on it
(:mod:`running_ladder`).

**Why a new package rather than editing the frozen apparatus** (ADR §2.1,
Codex HIGH-3): the frozen ``ladder.py`` binds ``stub.build_seed_pair`` at
import time and calls it directly inside ``r0_r1_seed_point``, so the
blind generator cannot be drop-in replaced; monkeypatching it is a
**forbidden** tune path. Instead :mod:`running_ladder` re-implements the
*same readout recipe* driven by a running builder while importing the frozen
``ladder`` estimand/statistic helpers **read-only** (byte-identical), and a
**blind-equivalence golden test** pins that recipe as a faithful copy so any
difference is attributable to the generator alone.

**Read-only byte inheritance (ADR §2.1/§4.2, tune-to-pass guard)**: every
frozen module — ``ladder`` / ``stub`` / ``constants`` / ``smoke`` /
``verdict_report`` / ``world`` / ``memory`` / ``spdm`` — is **used, never
edited**. The frozen ``d0_substrate`` package's own USE-only-over-frozen-core
discipline (no ``cognition`` import; ``world.tick`` avoided via the local
``smoke.SmokeClock`` tick scheduler, DA-D0S-5) carries over unchanged.

**Claim boundary (ADR §6/§7, over-claim guard)**: ``STRUCTURAL_READY_RUNNING``
means within-zone situated structural outcome is measurable **non-circularly
on a running trace** and the frozen<->running distinction is real — a
**terminal-anchored existence-proof under a return-to-home errand**, NOT a
divergence test, and the R1 advance is **not itself running-specific** (the
running-ness gate certifies history-dependence separately; the C-memoryless
control shows the same concentration passes R1 without history — ADR §4.1).

**Scope**: this package is the frozen apparatus. The single sealed 64-seed D0a
running run is a **separate task** run from committed frozen code (ADR §5-5
one-shot kill; ``scripts/d0_running_verdict_run.py`` is the entry point but is
not executed here).
"""

from __future__ import annotations

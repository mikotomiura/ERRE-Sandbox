"""Frozen running-track constants (design-final.md §5, result-independent).

Every value here is frozen **before** the sealed run is executed
(forking-paths guard), mirroring the frozen
:mod:`erre_sandbox.evidence.d0_substrate.constants`. The running track adds
**exactly one** new frozen scalar — :data:`RUNNINGNESS_TV_FLOOR` — and even
that is not an independently invented number: it is a **structural
identification** with the inherited :data:`~...constants.LANDSCAPE_JACCARD_FLOOR`
(design-final.md §3.2/§5, DA-RUNIMPL-3). Every other quantity the policy uses
(``K_RETRIEVE`` / ``M_MEMORIES`` / ``CELL_MICRO_RADIUS_M`` / the spatial-term
knobs / seed bank / bootstrap knobs / floors) is **read-only inherited** from
the frozen parent module; there is **no new tunable scalar** (design-final.md
§5 全数値凍結表: "新規 tunable scalar = ゼロ").

Changing any value here requires a **superseding ADR**, identical to the D0
pack / ES-1 / ES-3 discipline.
"""

from __future__ import annotations

from typing import Final

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.smoke import D0B_TICK_HZ as _D0B_TICK_HZ

RUNNINGNESS_TV_FLOOR: Final[float] = _c.LANDSCAPE_JACCARD_FLOOR
"""Practical-effect floor the running-ness gate requires the history-ablation
total-variation to clear: ``CI_lower(TV) > RUNNINGNESS_TV_FLOOR``
(design-final.md §3.2).

**Result-independent structural identification** (design-final.md §5,
DA-RUNIMPL-3, NOT an independently chosen number): ``TV`` is a ``[0, 1]``
distribution-distance quantity, the same scale on which the frozen apparatus
already imposes its practical-effect floor
:data:`~erre_sandbox.evidence.d0_substrate.constants.LANDSCAPE_JACCARD_FLOOR`
(= 0.10, itself = ``spdm.DEGENERATE_NULL_FLOOR``). Imposing the *same*
practical-effect magnitude on the ``[0, 1]`` TV rather than inventing a fresh
scalar is what keeps this floor frozen-by-inheritance. Pinned value-equal to
``LANDSCAPE_JACCARD_FLOOR`` in ``tests/test_evidence/test_d0_running_constants.py``
so it can only move if the inherited floor moves (a superseding ADR)."""

POLICY_SPEED_MPS: Final[float] = 1.3
"""Constant walking speed of the running policy's physics transit. Inherited
value from :attr:`erre_sandbox.world.physics.Kinematics.speed_mps` default
(1.3 m/s), the same speed the frozen D0b-runtime smoke uses; not a verdict
gate (the trace records arrival positions, and physics is a
determinism/embodiment layer, not the history-dependence source —
design-final.md §2.3)."""

POLICY_TICK_HZ: Final[float] = _D0B_TICK_HZ
"""Physics tick rate of the running loop, inherited from
``smoke.D0B_TICK_HZ`` (= 30 Hz, the real production tick rate). ``dt = 1 /
POLICY_TICK_HZ``. Integer tick counting + fixed ``dt`` keep the loop
wall-clock-free and byte-reproducible (design-final.md §2.4)."""

__all__ = [
    "POLICY_SPEED_MPS",
    "POLICY_TICK_HZ",
    "RUNNINGNESS_TV_FLOOR",
]

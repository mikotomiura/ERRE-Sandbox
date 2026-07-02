"""Frozen §2/§3/§5 constants for the M13-SUB1 D0 structural conformance track.

This module is the **single source of truth** for every value the D0 pack
pre-registration froze **before** any result was seen (forking-paths guard,
mirroring :mod:`erre_sandbox.evidence.spdm.constants` /
:mod:`erre_sandbox.evidence.es3_locomotion.constants`). A value can only
change by a deliberate edit here, which itself requires a **superseding
ADR** (`.steering/20260701-m13-sub1-d0-pack/design-final.md` §9 is FROZEN).
No value is read off a result and then tuned.

Two provenance classes of constant live here:

* **Inherited** (Codex-reviewed, byte or value pinned to a frozen upstream
  apparatus): :data:`LANDSCAPE_JACCARD_FLOOR` / :data:`R_MIN` /
  :data:`NULL_NOISE_FACTOR` / the spatial-term knobs (from
  :mod:`erre_sandbox.evidence.spdm.constants`); :data:`CLOSURE_AMP_FLOOR` /
  :data:`ZERO_TOL` / :data:`CI_ALPHA` / :data:`N_RESAMPLES` / :data:`B` /
  :data:`MIN_VALID_SEEDS` (from
  :mod:`erre_sandbox.evidence.es3_locomotion.constants`). Pinned
  `is`-identity or value-equal in ``tests/test_evidence/test_d0_constants.py``.
* **Newly frozen by principle** (design-final.md §5 deferred these four to
  the implementation ADR; this Plan-mode session froze them *before* any
  result, result-independent — see
  ``.steering/20260702-m13-sub1-d0-structural/decisions.md`` DA-D0S-1):
  :data:`CONE_APERTURE_DEG`, :data:`CONE_RANGE_M`, :data:`PROP_FIXTURE_MIN`,
  :data:`MIN_PROP_ZONES`.

World geometry (:data:`ZONES` / :data:`ADJACENCY` / :data:`ZONE_CENTERS` /
:data:`WORLD_SIZE_M` / :data:`ZONE_PROPS`) is **mirrored**, not imported —
the same discipline as ``evidence.spdm.scenario`` / ``evidence.es3_locomotion.
scenario`` — and pinned byte-for-byte against :mod:`erre_sandbox.world.zones`
in ``tests/test_evidence/test_d0_stub.py`` so the mirror cannot silently
drift. D0b-runtime (:mod:`erre_sandbox.evidence.d0_substrate.smoke`) is the
one module in this package that legitimately touches real physics
(:func:`erre_sandbox.world.physics.step_kinematics`) — that module's own
docstring records why it does **not** import ``erre_sandbox.world.tick``
(transitively pulls ``cognition``, violating the evidence-layer USE-only
constraint; DA-D0S-5).
"""

from __future__ import annotations

from typing import Final, NamedTuple

from erre_sandbox.evidence.es3_locomotion.constants import AMP_FLOOR as _ES3_AMP_FLOOR
from erre_sandbox.evidence.es3_locomotion.constants import CI_ALPHA as _ES3_CI_ALPHA
from erre_sandbox.evidence.es3_locomotion.constants import (
    MIN_WALK_SEEDS as _ES3_MIN_WALK_SEEDS,
)
from erre_sandbox.evidence.es3_locomotion.constants import (
    N_RESAMPLES as _ES3_N_RESAMPLES,
)
from erre_sandbox.evidence.es3_locomotion.constants import ZERO_TOL as _ES3_ZERO_TOL
from erre_sandbox.evidence.es3_locomotion.constants import B as _ES3_B
from erre_sandbox.evidence.spdm.constants import (
    DEGENERATE_NULL_FLOOR as _SPDM_DEGENERATE_NULL_FLOOR,
)
from erre_sandbox.evidence.spdm.constants import K_RETRIEVE as _SPDM_K_RETRIEVE
from erre_sandbox.evidence.spdm.constants import M_MEMORIES as _SPDM_M_MEMORIES
from erre_sandbox.evidence.spdm.constants import (
    NULL_NOISE_FACTOR as _SPDM_NULL_NOISE_FACTOR,
)
from erre_sandbox.evidence.spdm.constants import Q_BATTERY_MIN as _SPDM_Q_BATTERY_MIN
from erre_sandbox.evidence.spdm.constants import R_MIN as _SPDM_R_MIN
from erre_sandbox.evidence.spdm.constants import (
    SPATIAL_COORD_REF as _SPDM_SPATIAL_COORD_REF,
)
from erre_sandbox.evidence.spdm.constants import SPATIAL_GAMMA as _SPDM_SPATIAL_GAMMA
from erre_sandbox.schemas import Zone

# --- A world-geometry mirror (pinned to erre_sandbox.world.zones in the test) --

ZONES: Final[tuple[Zone, ...]] = (
    Zone.STUDY,
    Zone.PERIPATOS,
    Zone.CHASHITSU,
    Zone.AGORA,
    Zone.GARDEN,
)
"""The five zones in ``Zone`` declaration order (deterministic across
interpreters). Mirrors ``evidence.spdm.scenario.ZONES``."""

WORLD_SIZE_M: Final[float] = 100.0
"""Mirror of ``world.zones.WORLD_SIZE_M``. Pinned in ``test_d0_stub.py``."""

_ZONE_OFFSET: Final[float] = WORLD_SIZE_M / 3.0
"""Mirror of ``world.zones._ZONE_OFFSET`` (derivation, not an independent
pin target — the pin test compares the resulting :data:`ZONE_CENTERS`)."""

ZONE_CENTERS: Final[dict[Zone, tuple[float, float, float]]] = {
    Zone.STUDY: (-_ZONE_OFFSET, 0.0, -_ZONE_OFFSET),
    Zone.PERIPATOS: (0.0, 0.0, 0.0),
    Zone.CHASHITSU: (_ZONE_OFFSET, 0.0, -_ZONE_OFFSET),
    Zone.AGORA: (0.0, 0.0, _ZONE_OFFSET),
    Zone.GARDEN: (_ZONE_OFFSET, 0.0, _ZONE_OFFSET),
}
"""Mirror of ``world.zones.ZONE_CENTERS``. Pinned byte-for-byte in
``test_d0_stub.py`` (mirror-drift guard, ES-1/ES-3 discipline)."""

ADJACENCY: Final[dict[Zone, tuple[Zone, ...]]] = {
    Zone.STUDY: (Zone.PERIPATOS,),
    Zone.PERIPATOS: (Zone.STUDY, Zone.CHASHITSU, Zone.AGORA, Zone.GARDEN),
    Zone.CHASHITSU: (Zone.PERIPATOS, Zone.GARDEN),
    Zone.AGORA: (Zone.PERIPATOS, Zone.GARDEN),
    Zone.GARDEN: (Zone.PERIPATOS, Zone.CHASHITSU, Zone.AGORA),
}
"""Walkable adjacency mirrored from ``world.zones.ADJACENCY`` (neighbour
tuples in :data:`ZONES` order so ``random.choice``/``randrange`` is
reproducible). Pinned in ``test_d0_stub.py``."""


class PropFixture(NamedTuple):
    """Mirror of ``world.zones.PropSpec`` (field-for-field, D0-local type).

    A separate local type (rather than importing ``world.zones.PropSpec``)
    keeps :mod:`stub` / :mod:`ladder` on the pure-mirror discipline every
    other ``evidence`` apparatus module follows — the only module in this
    package that imports real ``world`` runtime code is :mod:`smoke`
    (D0b-runtime, by design).
    """

    prop_id: str
    prop_kind: str
    x: float
    y: float
    z: float
    salience: float


ZONE_PROPS: Final[dict[Zone, tuple[PropFixture, ...]]] = {
    Zone.CHASHITSU: (
        PropFixture(
            prop_id="chawan_01",
            prop_kind="tea_bowl",
            x=_ZONE_OFFSET - 0.5,
            y=0.4,
            z=-_ZONE_OFFSET + 0.5,
            salience=0.7,
        ),
        PropFixture(
            prop_id="chawan_02",
            prop_kind="tea_bowl",
            x=_ZONE_OFFSET + 0.5,
            y=0.4,
            z=-_ZONE_OFFSET - 0.5,
            salience=0.6,
        ),
    ),
    Zone.STUDY: (),
    Zone.PERIPATOS: (),
    Zone.AGORA: (),
    Zone.GARDEN: (),
}
"""Mirror of ``world.zones.ZONE_PROPS``. Pinned byte-for-byte in
``test_d0_stub.py``. MVP sparsity (chashitsu-only) is what drives the
``PROP_FIXTURE_MIN`` / :data:`MIN_PROP_ZONES` gate to INCONCLUSIVE for R2/R3
on the real fixture (honest default prediction, DA-D0S-1) — this constant is
never edited to make that gate pass."""

# --- B D0a generator apparatus knobs (deterministic, seed-as-only-freedom) -----

B: Final[int] = _ES3_B
"""Blind trace count = the bootstrap unit count. Inherited from
``es3_locomotion.constants.B`` (= 64)."""

MIN_VALID_SEEDS: Final[int] = _ES3_MIN_WALK_SEEDS
"""Minimum valid seeds for a strong verdict. Inherited from
``es3_locomotion.constants.MIN_WALK_SEEDS`` (= 32): the continuous rungs
(R1+) carry within-cell/within-trace variance structure, so the ES-3
bootstrap-unit floor applies rather than ES-1's 8-seed discrete-only floor."""

M_MEMORIES: Final[int] = _SPDM_M_MEMORIES
"""Formation-memory count per arm (R0/R1 retrieval-landscape rungs).
Inherited from ``spdm.constants.M_MEMORIES`` (= 20): matched trace length
across arms, same as SPDM path-A/path-B."""

CELL_MICRO_RADIUS_M: Final[float] = 10.0
"""Within-zone micro-walk radius (apparatus knob, not a verdict gate).

Voronoi-cell principle (DA-D0S-3): the nearest-neighbour zone-centroid
distance is ``_ZONE_OFFSET * sqrt(2) ~= 47.14`` m (e.g. PERIPATOS↔STUDY), so
the Voronoi boundary sits ``~23.57`` m from any centroid. ``10.0`` m keeps
every micro-walk sample safely inside its own zone's Voronoi cell (< half
the boundary distance) regardless of which zone is occupied, so
``locate_zone`` on any generated ``(x, z)`` always agrees with the
walk-assigned zone (asserted in ``test_d0_stub.py``). Fixed by this
geometric margin, never by looking at a resulting ``Δ_r`` and adjusting the
knob to pass the anti-collapse gate (tune-to-pass is forbidden, DA-D0S-3)."""

AFFORDANCE_RADIUS_M: Final[float] = 2.0
"""Mirror of ``world.tick._AFFORDANCE_RADIUS_M`` (raw trace-row proximity
sense, used by the R3 action⇄obs closure rung — *not* the R2 perception
cone, which uses :data:`CONE_APERTURE_DEG` / :data:`CONE_RANGE_M` instead).
Pinned in ``test_d0_stub.py``."""

# --- C ladder floors / gates (§2, §5 — inherited, forking-paths pinned) --------

LANDSCAPE_JACCARD_FLOOR: Final[float] = _SPDM_DEGENERATE_NULL_FLOOR
"""Practical-effect floor for the R0/R1/R2 Jaccard-scale estimands
(``median(D_r) >= this``). Inherited from
``spdm.constants.DEGENERATE_NULL_FLOOR`` (= 0.10)."""

RESIDUAL_JACCARD_FLOOR: Final[float] = LANDSCAPE_JACCARD_FLOOR
"""Anti-ES-1-collapse gate floor for R1+ (``median(Delta_r) >= this``).
Value-equal to :data:`LANDSCAPE_JACCARD_FLOOR` but a **separate** constant
(Codex HIGH-1, design-final.md §2 #5): the residual-increment gate and the
absolute-magnitude gate must be able to diverge under a future superseding
ADR without coupling the two names."""

CLOSURE_AMP_FLOOR: Final[float] = _ES3_AMP_FLOOR
"""R3 closure-invariant floor (headroom-normalised, ES-3 style). Inherited
from ``es3_locomotion.constants.AMP_FLOOR`` (= 0.02)."""

R_MIN: Final[float] = _SPDM_R_MIN
"""Scale-free ratio gate (``median(D_r) / max(null_r) >= this``). Inherited
from ``spdm.constants.R_MIN`` (= 2.0)."""

ZERO_TOL: Final[float] = _ES3_ZERO_TOL
"""Numerical zero tolerance for structure-destroying nulls / situated-
function controls. Inherited from ``es3_locomotion.constants.ZERO_TOL``
(= 1e-9)."""

NULL_NOISE_FACTOR: Final[float] = _SPDM_NULL_NOISE_FACTOR
"""Observed-arm noise gate multiplier. Inherited from
``spdm.constants.NULL_NOISE_FACTOR`` (= 1.5)."""

CI_ALPHA: Final[float] = _ES3_CI_ALPHA
"""Two-sided alpha for the bootstrap CI (90% CI). Inherited from
``es3_locomotion.constants.CI_ALPHA``."""

N_RESAMPLES: Final[int] = _ES3_N_RESAMPLES
"""Bootstrap resample count. Inherited from
``es3_locomotion.constants.N_RESAMPLES`` (= 10000)."""

STRUCTURAL_READY_MIN_RUNG: Final[int] = 1
"""``STRUCTURAL_READY`` requires ``R* >= this`` (= R1). Principle
(design-final.md §5): R0 alone reproduces ES-1's own discrete-zone
substrate — not "genuinely 3D" — so R1 is the first rung that demonstrates
sub-zone structural measurement capability."""

# --- D retrieval spatial-term knobs (R0/R1 readout apparatus, inherited) -------

SPATIAL_GAMMA: Final[float] = _SPDM_SPATIAL_GAMMA
"""Spatial-proximity decay. Inherited from ``spdm.constants.SPATIAL_GAMMA``
(apparatus knob, not a verdict gate — the ladder verdict is scale-free /
Δ-floor, robust to the exact decay shape, mirroring SPDM's own reasoning)."""

SPATIAL_COORD_REF: Final[float] = _SPDM_SPATIAL_COORD_REF
"""Reference scale the proximity distance is normalised by. Inherited from
``spdm.constants.SPATIAL_COORD_REF``."""

K_RETRIEVE: Final[int] = _SPDM_K_RETRIEVE
"""Top-k retrieved memories per query. Inherited from
``spdm.constants.K_RETRIEVE``."""

Q_BATTERY_MIN: Final[int] = _SPDM_Q_BATTERY_MIN
"""Minimum zone-vocabulary-free query battery size. Inherited from
``spdm.constants.Q_BATTERY_MIN``."""

# --- E R2 perception-cone + prop-fixture gate (newly frozen, DA-D0S-1) ---------

CONE_APERTURE_DEG: Final[float] = 120.0
"""R2 perception-cone full aperture in degrees (half-angle 60 degrees from
the trace's ``yaw``). Principle (DA-D0S-1, result-independent): the
conventional human binocular horizontal field of view is ~114 degrees;
120 degrees is the standard "useful field of view" rounding used for a
simple forward-facing perception cone. Frozen before any ladder result was
seen; never adjusted to change which props fall inside the cone."""

CONE_RANGE_M: Final[float] = _ZONE_OFFSET
"""R2 perception-cone range in metres. Principle (DA-D0S-1): equals
``WORLD_SIZE_M / 3`` (= ``world.zones._ZONE_OFFSET``), the world's
own within-zone perception-reach scale. The nearest inter-zone centroid
distance is ``_ZONE_OFFSET * sqrt(2) ~= 47.14`` m, so this range keeps
perception within-zone rather than spilling into a neighbour's centroid."""

PROP_FIXTURE_MIN: Final[int] = 2
"""Minimum props a zone must carry to be R2-evaluable. Principle
(DA-D0S-1): a perception cone needs to be able to both include and exclude
at least one prop as yaw/position vary for within-zone affordance-set
divergence to be measurable at all; one prop cannot produce a varying set."""

MIN_PROP_ZONES: Final[int] = 2
"""Minimum number of prop-fixture-valid zones for R2 to be evaluable.
Principle (DA-D0S-1): the R2 landscape divergence needs a location-driven
*contrast* — with fewer than two prop-bearing zones there is nothing to
contrast the affordance set against. On the current MVP ``ZONE_PROPS``
(chashitsu-only) this gate is **not** met, so R2 (and hence R3, which is
contiguity-gated behind R2) is the honest default INCONCLUSIVE prediction
(DA-D0S-1) — this constant is never lowered to force R2 to evaluate."""

__all__ = [
    "ADJACENCY",
    "AFFORDANCE_RADIUS_M",
    "CELL_MICRO_RADIUS_M",
    "CI_ALPHA",
    "CLOSURE_AMP_FLOOR",
    "CONE_APERTURE_DEG",
    "CONE_RANGE_M",
    "K_RETRIEVE",
    "LANDSCAPE_JACCARD_FLOOR",
    "MIN_PROP_ZONES",
    "MIN_VALID_SEEDS",
    "M_MEMORIES",
    "NULL_NOISE_FACTOR",
    "N_RESAMPLES",
    "PROP_FIXTURE_MIN",
    "Q_BATTERY_MIN",
    "RESIDUAL_JACCARD_FLOOR",
    "R_MIN",
    "SPATIAL_COORD_REF",
    "SPATIAL_GAMMA",
    "STRUCTURAL_READY_MIN_RUNG",
    "WORLD_SIZE_M",
    "ZERO_TOL",
    "ZONES",
    "ZONE_CENTERS",
    "ZONE_PROPS",
    "B",
    "PropFixture",
]

"""Hard-coded persona-pair antagonism table for M7δ.

Why hard-coded vs derived:

* During Slice δ Plan mode the v2 ``/reimagine`` proposed deriving
  antagonism from a 7-D ``PersonalityTraits`` distance so the surface
  generalises to N personas. Empirical check on the production YAMLs
  (kant / nietzsche / rikyu) showed the normalised distances are
  K↔N=0.40, K↔R=0.30, N↔R=0.443 — i.e. N↔R is **larger** than K↔N,
  contradicting v2's pinned ordering. A trait-distance gate above 0.40
  fires for none; a gate at 0.40 fires for all three and erases the
  K↔N specificity.
* For δ's 3-persona world a hard-coded table is the correct tool: it
  guarantees the live-fire negative-delta path for kant↔nietzsche
  (``decisions.md`` §R3 M4) and is deterministic for unit tests.
* Generalisation to a derivation (cosine, asymmetric, etc.) is
  appropriate when persona count grows in m9-lora; until then YAGNI.

Symmetry: the table is *symmetric* in δ (Kant feels antagonism toward
Nietzsche to the same magnitude that Nietzsche feels it toward Kant).
m8-affinity-dynamics may revisit asymmetric reactions when richer
personality dimensions land.

See ``.steering/20260426-m7-slice-delta/design-final.md`` (Phase 3, axis
2 row) for the full rationale and computed distances.
"""

from __future__ import annotations

from typing import Final

# Mapping ``(speaker_persona_id, addressee_persona_id) → antagonism``.
# Antagonism is a *negative* event_impact contribution that flows into
# ``compute_affinity_delta`` and dominates the structural positive term so
# the delta lands clearly in the negative region. -0.30 is the calibrated
# magnitude from .steering/20260426-m7-slice-delta/design-final.md (Axis 2).
_TRAIT_ANTAGONISM: Final[dict[tuple[str, str], float]] = {
    ("kant", "nietzsche"): -0.30,
    ("nietzsche", "kant"): -0.30,
}


def lookup_antagonism(
    speaker_persona_id: str,
    addressee_persona_id: str | None,
) -> float:
    """Return the persona-pair antagonism magnitude or ``0.0`` if none.

    ``addressee_persona_id`` may be ``None`` when the addressee's persona
    cannot be resolved (defensive — should not happen on the production
    sink path, but the bootstrap chain calls this from a swallow-errors
    context).
    """
    if addressee_persona_id is None:
        return 0.0
    return _TRAIT_ANTAGONISM.get((speaker_persona_id, addressee_persona_id), 0.0)


__all__ = ["lookup_antagonism"]

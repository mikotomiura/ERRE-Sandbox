"""Belief-promotion gate trace (``swm_bond_affinity_trace``) — fork (C) VoI diagnostic.

A **new-module shadow** package (sibling of :mod:`erre_sandbox.evidence.saturation`)
that persists the sub-threshold ``RelationshipBond`` affinity / interaction-count
trajectory the III-a live §5.3 M1 root-cause diagnostic needs: the near-miss
population ``ichigo_ichie_count >= 6`` ∧ ``|affinity| < 0.45`` (interaction-count
gate satisfied, only the affinity gate binding). The 12-run live stock cannot
answer (i) cap-binding vs (ii) structural decoupling because it persists only
promotion-survivor bonds (``|affinity| >= 0.45``); this module captures the
sub-threshold trajectory a future flag-on run will use.

It shares no column order, no measure, and no schema with the frozen
``individual_state_trace`` / ``swm_modulation_saturation_trace`` /
``swm_hint_engagement_trace`` / ``swm_floor_input_trace`` tables, so those frozen
gates stay untouched. The instrumentation design is fixed in
``.steering/20260617-iiia-cap-voi-diagnostic/instrumentation-adr.md``.
"""

from __future__ import annotations

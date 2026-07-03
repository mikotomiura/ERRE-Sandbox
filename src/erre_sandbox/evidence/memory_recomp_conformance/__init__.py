"""M13-SUB1 memory-recomposition seam channel-conformance evidence layer.

Deterministic, GPU/LLM-free apparatus for the memory-recomposition seam
conditional re-entry gate of the M13-SUB1 forward disposition ADR
(``.steering/20260702-m13-sub1-disposition/``, ``NO_STRUCTURAL_FLOOR`` の後).

The **costed pre-register ADR** (``.steering/20260702-m13-sub1-memseam-adr/
design-final.md`` §0-§9, FROZEN, user ratify 済) turns the estimand from the ES-2
**output-diversity** type (which ended INCONCLUSIVE at low power) to the ES-1 / ES-3
**channel-conformance** type: does an input channel ``C`` bias an independent
downstream discrete decision ``D`` above a structure-destroying null, non-circularly?

* **C** (input channel) — the argmax directed-transition cell of an individual's
  *idle recomposition batch* (the ES-2 replay kernel's ``transition_distribution``,
  byte-inherited). Its ``to_content`` fixes a ``target_zone`` via
  :func:`channel.zone_of_formation`.
* **D** (downstream decision) — an **independent** post-idle Pólya-urn occupancy
  walk (independent RNG stream + independent ``visit_count`` init) whose only
  coupling to ``C`` is a ``target_zone`` match bonus reusing the frozen
  ``POLYA_ALPHA`` (no new free effect parameter).
* **estimand** — the scale-free entropy reduction ``conform_s`` that conditioning
  ``D`` on ``C``'s ``target_zone`` produces, tested against a **C↔D
  pairing-destroying permutation null** (other seeds' ``target_zone``), aggregated
  as a per-seed ``delta_s`` with a bootstrap CI (GO ⇔ ``CI_lower > 0``).

The package is **USE-only** over the frozen core: it imports the ES-2 apparatus
(``evidence.es2_replay``) and ``evidence.bootstrap_ci`` read-only, mirrors world
geometry through ``es2_replay.scenario`` (already pinned to ``world.zones``), and
never mutates a frozen asset. Every threshold in :mod:`constants` is
pre-registered *before* any result (``DA-MEMSEAM-IMPL-1``).

**Non-circularity** (design-final.md §5): ``D``'s ``visit_count`` never reads
``C``'s replay-walk state; the sole ``C→D`` path is the ``target_zone`` bonus. A
deterministic independence pin test asserts that feeding the same ``target_zone``
from a *different* ``C`` trace leaves ``D``'s weights byte-identical.

Claim boundary (design-final.md §4): a GO means "memory-recomposition state gives
an independent downstream discrete choice a non-circular causal bias"
(necessary-substrate type, identical to ES-1 / ES-3), **not** proof of H4
(embodiment produces divergence). No live agent / Godot connection — the walks are
synthetic (``claim_scope = "synthetic_post_idle_walk_only"``,
``live_agent_connected = False``). NO_GO is a progressive finding; INCONCLUSIVE
(low power / ill-posed channel / degenerate support / cost-ceiling) is kept
distinct.
"""

from __future__ import annotations

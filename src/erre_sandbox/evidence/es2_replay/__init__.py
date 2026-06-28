"""M13-ES2 path-recombination replay evidence layer.

Deterministic, GPU/LLM-free apparatus for the **second** step of the
embodiment-substrate arc (M13). On top of the ES-1 SPDM substrate (spatial
path-dependent memory, frozen GO), two same-base individuals A/B take
**preferential-return walks** (Pólya-urn α=1), lay down experience fragments,
and — during idle **replay** — recombine those fragments into novel *seed*
structures. The layer measures whether the recombination produces **de-novo,
path-dependent** novel seeds above a **content-stratified matched permutation
null**, under explicit **synthetic semantic competition**.

The package is **USE-only** over the frozen core: it imports
``memory.retrieval.spatial_proximity`` (the ES-1 spatial term), the
``evidence.spdm`` Jaccard primitive, and ``evidence.bootstrap_ci`` read-only,
and never imports ``cognition`` or mutates an ES-1 frozen asset. World geometry
is **mirrored** (not imported) and pinned to ``world.zones`` in the scenario
test. Every threshold in :mod:`constants` is pre-registered *before* any result.

**Non-circularity** (the design's central guarantee, ``design-final.md`` §12):

* the replay **kernel is verdict-blind** — it reads neither temporal order, nor
  A/B label, nor novelty (transition weight is ``proximity · semantic`` only);
* **segment-crossover is deliberately rejected** (it would *construct* de-novo
  splice transitions, making novelty mechanically guaranteed → covertly circular
  w.r.t. ③). Novelty must *emerge* from the order-blind walk;
* the de-novo novelty test is shown **able to fail** by a temporal-replay
  negative control (a stream replay that follows formation order scores below the
  floor — the apparatus-validity floor, Codex H3);
* the null is **content-stratified** (each permutation arm preserves the full
  content multiset; only per-content A/B location binding swaps, Codex H4);
* the seed comparison key is **canonical** (``canonical_seed_structure_id`` over
  shared content ids; raw fragment ids — disjoint per arm — never enter the
  verdict, Codex H1);
* the bootstrap unit is the **scenario seed** (per-seed null quantile feeds a
  ``delta_s``; ``N_PERM`` is not a sample size, Codex H5);
* low A/B divergence (5-zone hub convergence) is **INCONCLUSIVE**, never NO_GO
  (Codex H6).

This is **path-recombination** replay — distinct from
:mod:`erre_sandbox.cognition.world_model_replay`, which is a fixed-stream
reconcile replay (III-a §5.2). They share the word "replay" and nothing else.

Claim boundary (``design-final.md`` §0): a GO is "**eligible to proceed to
ES-3**", *not* the full hypothesis. NO_GO is a progressive finding;
INCONCLUSIVE is kept distinct from NO_GO. The neuroscience analogy
(hippocampal replay) is a design warrant, not direct causal evidence.
"""

from __future__ import annotations

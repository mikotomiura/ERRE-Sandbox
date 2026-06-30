"""M13-ES4 locomotion → temperature actuator sufficiency calibration layer.

The **fourth** step of the embodiment-substrate arc (M13). On top of the ES-1
SPDM substrate (frozen GO), the ES-2 recombination replay (bounded INCONCLUSIVE)
and the ES-3 locomotion → sampling **channel** verdict (GO = the channel is
wired), ES-4 asks the first **LLM-crossing** question: does driving that channel
as a **temperature-only actuator** (``gain_p=0``) over a frozen ``qwen3:8b``
decoder move the *output* into a divergent-favouring regime — measured as
**appropriateness-gated divergent-quality DQ = on-task rarity** against a frozen
common-use reference (``design-final.md`` §2)?

Unlike ES-1/2/3 (deterministic numpy, apparatus = run in one piece), ES-4's run
is **GPU generation** (SGLang fp8 + qwen3:8b, ~6,240 generations + judge passes).
The discipline ES-3 earned ("build the apparatus deterministically, *then* run")
is preserved by making **generation an injectable seam**: every module here takes
an ``inference_fn`` / ``encoder_fn`` / ``judge_fn`` ``Callable`` (the same shape
``golden_baseline.GoldenBaselineDriver`` uses), so the whole apparatus — condition
resolution, rarity scoring, the control battery, the cluster-paired estimand and
the five-vocabulary verdict — is exercised **LLM-free** under deterministic mocks.
Session 1 (this layer + its tests) wires and pins everything; Session 2 swaps the
seam for the real backend and runs Phase 0; Session 3 (only on Phase 0 PASS) runs
Phase 1.

The layer is **USE-only** over the core: it composes sampling through the frozen
``inference.sampling.compose_sampling`` and ``erre.locomotion_sampling`` (with
``gain_p=0``, ES-4's temperature-only actuator), reuses the MPNet semantic encoder
(``tier_b/vendi``), the seed derivation (``golden_baseline.derive_seed``) and the
hierarchical bootstrap (``bootstrap_ci``); it never imports ``cognition`` or
mutates a frozen ES-1/2/3 asset. Every threshold in :mod:`constants` is the
pre-registered ``design-final.md`` §5 freeze (user-ratified) **before** any result.

Claim boundary (``design-final.md`` §0 / §9): a GO means "**qwen3:8b local, frozen
decoding: the locomotion → temperature actuator moves output into a
divergent-favouring regime (on-task rarity ↑) — actuator *sufficiency***", **not**
"walking → genuine creative divergence" and **not** a re-proof of the closed-loop
core thesis. Because locomotion is the *only* temperature channel (``gain_p=0``),
no "locomotion-specific divergence beyond temperature" is claimed (A2 ≡ M2
distribution-matched equivalence makes this explicit). DQ is named
"appropriateness-gated divergent-quality (rarity)", **never** "originality"
(over-claim guard). The five-vocabulary verdict is INCONCLUSIVE-first: an
apparatus-invalid or under-powered measurement is never reported as a progressive
NO_GO (ES-2/ES-3 discipline).
"""

from __future__ import annotations

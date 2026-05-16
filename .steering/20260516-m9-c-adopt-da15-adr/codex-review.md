[HIGH-1] HIGH-3 violation risk: Plan A redefines Vendi operationally
- Finding: The numerals stay unchanged, but “Vendi d ≤ -0.5 under at least 2 candidate kernels” is not the same locked DA-14 `vendi_semantic` instrument. DA-14 artifacts/code are MPNet-pinned, and DA-14 only explicitly pre-authorized kernel swap for `vendi_fail_but_others_pass`; current state is Vendi + Burrows fail.
- Why it matters: This can become threshold movement in disguise: same number, changed measurement distribution, post-fail.
- Fix: Add: “DA-14 MPNet Vendi remains REJECT and is always reported. DA-15 defines a versioned amended metric, `vendi_semantic_v2_encoder_swap`, with the same point/CI thresholds. Primary gating encoders are exactly pre-registered and revision-pinned in D-2 before scoring. Exploratory encoders cannot contribute to ADOPT.”
- Severity rationale: HIGH because without this, Plan A can retroactively convert a failed DA-14 axis into a pass.

[HIGH-2] Cross-arm blind spot: retrieval encoders are not style validation
- Finding: V1/V2 both assume multilingual-e5 / bge-m3 will reveal persona-style better than MPNet. Their primary evidence is multilingual retrieval/semantic embedding, not stylometry or persona-style discrimination. A pass could reflect language/length artifacts.
- Why it matters: This is the likely shared Claude-lineage miss. E5 and BGE-M3 are retrieval-focused ([E5](https://arxiv.org/abs/2402.05672), [BGE-M3](https://arxiv.org/abs/2402.03216)); MPNet/SBERT-style embeddings target semantic similarity ([all-mpnet card](https://huggingface.co/sentence-transformers/all-mpnet-base-v2)); style representation is a distinct task ([LISA](https://arxiv.org/abs/2305.12696)).
- Fix: Add a Plan A eligibility gate: language-balanced and token-length-balanced bootstrap, within-language d reporting, and a preregistered calibration panel showing the encoder separates Kant-style/control text without relying on language ID. If the effect disappears under balancing, Plan A fails.
- Severity rationale: HIGH because Plan A is an ADOPT gate, not just exploratory diagnostics.

[MEDIUM-1] Plan B trigger must not harden the de+en soft warning retroactively
- Finding: `de+en=0.489 < 0.60` was a soft warning, not a DA-14 audit failure. Plan B is justified by DA-14 REJECT plus Candidate C fallback, not by reclassifying DI-5.
- Why it matters: Retrospective trigger promotion erodes preregistration discipline.
- Fix: Add: “DI-5 de+en mass remains a soft warning. Plan B is triggered by DA-14 REJECT; the de+en miss only prioritizes the targeted-hybrid shape.”
- Severity rationale: MEDIUM because the plan remains valid, but the rationale needs tightening.

[MEDIUM-2] Effect-size estimates are under-supported
- Finding: Plan A d deltas, Plan B 0.489→0.60 mass extrapolation, and Plan C rank=16 d ranges are priors, not literature-grounded estimates. LoRA/QLoRA support feasibility and parameter efficiency, not a rank=16 persona-style effect on this 5k weighted-CE setup ([LoRA](https://arxiv.org/abs/2106.09685), [QLoRA](https://arxiv.org/abs/2305.14314)).
- Why it matters: The numbers could bias future escalation decisions.
- Fix: Reword all predicted d ranges as “non-gating directional priors.” For Plan B, gate on achieved corpus stats and empirical DA-14 rerun. For Plan C, require Phase E dry-run evidence.
- Severity rationale: MEDIUM because empirical gates still decide outcomes.

[MEDIUM-3] Hybrid H-α is valid only with isolation
- Finding: Pre-staging Plan B during Plan A wall time is genuine parallelism only if it cannot contaminate Plan A scope, criteria, or PR contents.
- Why it matters: Otherwise the “not merged unless Plan A fails” rule becomes operationally leaky.
- Fix: Add: “H-α work occurs on a separate branch/worktree or uncommitted patch; it is not merged, tested as part of Plan A, or referenced in Plan A verdict. If Plan A fails, open a separate Plan B PR.”
- Severity rationale: MEDIUM because the tactic is acceptable with guardrails.

[LOW-1] Plan A ADOPT needs a named Burrows limitation
- Finding: Kant ADOPT via Vendi-swapped + ICC is allowed by 2-of-3 only after the DA-15 metric amendment, but Burrows still fails.
- Why it matters: Future readers may overclaim stylometric convergence.
- Fix: Add: “Burrows reduction remains FAIL; German function-word stylometry is not improved. Plan A ADOPT rests only on DA-15 Vendi semantics + ICC, and Burrows remains open for Plan B / reference-corpus work.”
- Severity rationale: LOW because quorum allows it, but portability needs the limitation.

Verdict: ADOPT-WITH-CHANGES

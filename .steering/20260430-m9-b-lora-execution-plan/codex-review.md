# Codex Independent Review — M9-B LoRA Execution Plan

## Overall verdict
- Qualified-sound: v2-B is directionally better than v1, but M9-B should not close until the trigger logic, offensive metric gate, and serving migration assumptions are corrected.

## Top 3 highest-risk decisions
1. The 4-condition AND trigger is likely to stall LoRA indefinitely; it is stricter than the frozen D1 baseline and makes `dialog_turn ≥500/persona` plus plateau plus divergence stability all binding at once (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:49`).
2. The plan still implies vLLM migration for M9-C even though current SGLang now has documented multi-LoRA, dynamic load/unload, pinned adapters, and overlap loading support (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:78-80`; [SGLang LoRA docs](https://docs.sglang.io/advanced_features/lora.html)).
3. The offensive gate uses noisy Tier B metrics and a poorly grounded 5% threshold, so it can reject useful LoRA or accept metric gaming (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:51-52`, `.steering/20260430-m9-b-lora-execution-plan/design-v2.md:164-167`).

## Findings

### HIGH (must address before M9-B closure)
- **HIGH-1**: 4-condition AND trigger contradicts the prior defer-and-measure ADR
  - Issue: The frozen D1 trigger allowed floor maintenance plus either data coverage or divergence plateau (`.steering/20260428-m9-lora-pre-plan/decisions.md:29-37`), while the hybrid now requires all four conditions simultaneously (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:49`).
  - Impact: This can make M9-C unreachable. The prior plan already warned that 500/persona was likely impractical from ζ scale (`.steering/20260428-m9-lora-pre-plan/decisions.md:44-50`).
  - Recommendation: Use `floor required AND (coverage reached OR plateau reached OR timebox reached)`. Treat divergence stability as a diagnostic, not a hard gate.

- **HIGH-2**: Offensive gate is not statistically operational
  - Issue: “post-LoRA Tier B < pre-LoRA baseline” rollback and “+5%” acceptance are underspecified (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:51-52`).
  - Impact: Tier B noise can dominate the decision; a single Vendi/IPIP shift can trigger false rollback.
  - Recommendation: Define a primary composite per persona, bootstrap confidence intervals over turns/runs, and require quorum: rollback only if 2-of-3 primary submetrics regress beyond CI or defensive canaries fail.

- **HIGH-3**: vLLM migration premise is stale
  - Issue: v1 assumed vLLM was the clear LoRA path because SGLang LoRA was immature (`.steering/20260430-m9-b-lora-execution-plan/design-v1.md:37-46`), but the hybrid timeline still schedules vLLM migration (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:78-80`).
  - Impact: A solo project may spend a full task migrating away from the serving stack that already supports resonance/FSM integration.
  - Recommendation: Change C/H to “SGLang-first LoRA runtime spike; vLLM fallback only if SGLang fails measured adapter swap, batching, or latency gates.” SGLang now documents `--enable-lora`, dynamic `/load_lora_adapter`, multiple adapters, `csgmv`, and overlap loading ([docs](https://docs.sglang.io/advanced_features/lora.html)).

- **HIGH-4**: Training/evaluation contamination is not fully isolated
  - Issue: v2 colocates Tier A-B metrics with training rows and says training/evaluation can use the same schema (`.steering/20260430-m9-b-lora-execution-plan/design-v2.md:71-103`).
  - Impact: A future trainer can accidentally learn evaluator outputs or judge artifacts.
  - Recommendation: Keep raw training Parquet metric-free, and store metrics in a sidecar table keyed by `run_id/persona_id/turn_idx`. Add a training-view contract: `evaluation_epoch=false` and metric columns excluded.

### MEDIUM (should address; planner judges accept/defer)
- **MEDIUM-1**: M9-B scope wording is inconsistent
  - Issue: v2 says M9-B implements Tier A and part of Tier B (`.steering/20260430-m9-b-lora-execution-plan/design-v2.md:139-171`), but the accepted timeline says M9-B is planning/design only (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:58-65`).
  - Impact: Moving target risk.
  - Recommendation: design-final should explicitly say M9-B produces specs only; M9-eval-system implements.

- **MEDIUM-2**: QLoRA NF4 is the conservative default, not the only realistic option
  - Issue: “唯一現実解” overstates the case (`.steering/20260430-m9-b-lora-execution-plan/design-v2.md:30-36`).
  - Impact: It can blind the plan to serving-side AWQ/GPTQ/INT4 alternatives or 8-bit LoRA fallbacks.
  - Recommendation: Keep QLoRA NF4 as default for training on 16GB, but record AWQ/GPTQ as serving alternatives and 8-bit LoRA as a quality/perf fallback.

- **MEDIUM-3**: Golden set size is underpowered for acceptance
  - Issue: 3 persona × 100 utterances is proposed (`.steering/20260430-m9-b-lora-execution-plan/design-v2.md:156-158`).
  - Impact: Good for smoke tests, weak for stable persona-fit claims.
  - Recommendation: Start with 100/persona for M9-eval-system, but require 300/persona before final LoRA acceptance; reserve 1000/persona for publication-grade work.

- **MEDIUM-4**: Evaluation frequency should split cheap and expensive tiers
  - Issue: “1 evaluation run per 100 turns” is added without VRAM accounting (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:40-43`).
  - Impact: Prometheus 2 8x7B-class judges will contend with qwen3:8b on the same 16GB box.
  - Recommendation: Tier A per turn, Tier B per 100 turns, Tier C offline per session/nightly.

### LOW (nice-to-have, defer-able)
- **LOW-1**: N=4 deferral is acceptable, but add a synthetic heldout scenario
  - Issue: Full persona 4 can wait (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:19`).
  - Impact: Eval infra may be overfit to exactly 3 personas.
  - Recommendation: Use a mocked/heldout fourth persona in eval tests without adding runtime N=4.

- **LOW-2**: LIWC replacement should be framed honestly
  - Issue: LIWC license risk is known (`.steering/20260430-m9-b-lora-execution-plan/design-v1.md:145`).
  - Impact: Empath/spaCy is credible as an OSS proxy, not a validated LIWC equivalent.
  - Recommendation: Prefer custom persona dictionaries + stylometry for M9; avoid Big-Five claims unless validated.

## Answers to 10 open questions
1. v2-B is better than v1, but only if timeboxed. v1’s “LoRA ASAP” cannot prove success because J5 is floor-only (`.steering/20260430-m9-b-lora-execution-plan/design-v1.md:111-112`), but v2 overcorrects with unreachable gates.
2. Delay is rational for research validity, but not if it blocks all LoRA learning. Add a one-persona LoRA spike in parallel with M9-eval-system, explicitly marked non-decisional.
3. Golden set in M9-eval-system is realistic at 100/persona only if treated as seed data. 300/persona is the real acceptance target.
4. Use judge hygiene: position swaps, length normalization, two local judges for close calls, human spot checks, and CI over repeated runs. Do not let Prometheus/G-Eval be the sole gate.
5. Relax `dialog_turn ≥500/persona` first. The prior ADR already identified v1’s turn threshold as effectively unreachable at ζ scale (`.steering/20260428-m9-lora-pre-plan/decisions.md:44-50`).
6. Physical partitioning is not overengineering; it is necessary. But a boolean flag alone is insufficient. Use separate raw/eval directories or sidecar metric tables.
7. “Initial run floor-only” is reasonable for exploration, but not for adoption. First run can avoid rollback; second/third runs must show CI-backed improvement.
8. Empath/spaCy are acceptable OSS proxies, but not replacements for LIWC psycholinguistic depth. Use them for descriptive signals, not hard Big-Five gates.
9. Multi-language strategy: normalize per language, compare within-language reference corpora, and avoid cross-language Burrows’ Delta. For Kant/Nietzsche, translated English can be a separate baseline, not mixed with German originals.
10. Risk hedge: produce a short M9-eval-system spec plus a single-persona LoRA spike protocol as the short-term deliverable. This preserves momentum without pretending the offensive gate is ready.

## Final note
- The planner is right that “single thinker-likeness score” should be rejected; the survey’s own conclusion says formal metrics are floors/proxies and expert review remains final (`.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md:326-349`). The missed third option is not v1 or v2-B: keep evaluation-first as the decision framework, but run a bounded, non-authoritative Kant LoRA spike on the current SGLang stack to expose adapter/runtime/data problems early while the evaluator is being built.

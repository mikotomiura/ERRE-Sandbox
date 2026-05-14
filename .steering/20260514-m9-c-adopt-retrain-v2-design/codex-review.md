# Codex review — m9-c-adopt retrain v2 spec design

## Verdict
ADOPT-WITH-CHANGES

## HIGH-A: MODIFY
Candidate B is the right primary path; Candidate C is not mandatory before the first v2 run because raw volume was empirically defeated (`realised_examples=5022`) and a naive +2500-turn collection could reproduce the same ja/short/dialog-heavy distribution. But `design-final.md` should not rely on random 10% validation alone.

Change proposals:
1. In `design-final.md` §3.3/§5, require group-aware validation: split by original `dialog_id`/source shard before monolog re-cast, and keep all `"<orig>_mono"` rows in the same side as their source.
2. Add a weight-concentration audit before training: per-language weighted mass, top 5% examples' share of total weight, and weighted effective sample size. If effective high-signal mass remains <1000 or top 5% mass is excessive, trigger Candidate C as fallback.
3. Define Candidate C as targeted hybrid only: +2500 turns must be de/en, >=60-token, monolog/long-form biased. A generic stimulus bump is not useful.

## HIGH-B: ADOPT
Compute feasibility is plausible. The observed K-beta baseline was `max_steps=2000`, `peak_vram_bytes=10553926656` (~9.83 GiB / 10.55 GB decimal depending unit), batch=1, grad_accum=8, NF4. Doubling `max_steps` increases wall time, not activation memory. A scalar sample weight column and per-example loss vector are negligible against QLoRA activation/model memory.

Keep the 8h abort. In implementation, avoid generation-time eval, keep eval batch=1, and use loss-only eval/early stopping so validation does not retain logits.

## HIGH-C: MODIFY
The weighting idea is acceptable as static importance weighting / curriculum-style reweighting, but the current statistical and implementation claims need correction.

Change proposals:
1. Replace the “HF Trainer standard `sample_weight` collator” claim in `design-final.md` §3.2/§3.4 with an explicit `WeightedTrainer.compute_loss` design. HF causal-LM models do not consume `sample_weight` automatically; the implementation must compute token CE with `reduction="none"`, reduce to per-example loss over non-`-100` labels, then use `(loss_i * weight_i).sum() / weight_i.sum().clamp_min(eps)`.
2. Normalize weights to mean 1.0 on the train split after clamping, and emit min/p50/p90/max plus weighted mass by language/length/marker bucket. This prevents the hand-set formula from silently changing effective LR.
3. Label the 0.35/0.20/0.15/0.30 coefficients as heuristic, not empirical. Sum-to-1 is interpretable but not evidence-derived.

The closest prior art is static importance weighting/curriculum learning. Focal loss is only a loose analogy because focal loss is dynamic and model-confidence based; DAP/preference personalization is not the matching objective.

## HIGH-D: MODIFY
Vendi `d <= -0.5` vs no-LoRA SGLang is defensible as a moderate, nontrivial direction threshold. Burrows >=5% is ambitious but acceptable as an ADOPT threshold because the current rank=8 proper effect is only ~0.83% reduction vs no-LoRA SGLang (`115.101 -> 114.141`), so passing it would mean a real shift.

The ICC threshold is not defensible as written. Current no-LoRA SGLang already has `icc_agreement_single=0.906` and rank=8 has ~0.900, so `ICC(A,1) >= 0.55` with lower CI >=0.50 is still an auto-pass and does not solve the old ICC(C,k)>0.97 informativeness problem.

Change proposal: make ICC(A,1) a guardrail unless it is relative to no-LoRA SGLang. Either require improvement over no-LoRA agreement (`delta > 0` with CI lower >0), or record ICC as diagnostic and require the adoption quorum to be met by Vendi/Burrows plus throughput. Under current thresholds, Kant ADOPT probability is artificially inflated by ICC auto-pass; with nontrivial ICC or Vendi+Burrows required, I would expect a low-to-moderate chance (~10-25%) rather than the apparent 25-50%.

## MEDIUM-1: ADOPT
The 5 metrics are enough for this design decision. Token proxy error is not fatal because the observed shape is extreme: 69.0% <30 proxy tokens and only 49 examples >=60 tokens is unlikely to invert under a +/-20% tokenizer correction.

Recommended additions for the implementation PR, not this PR: TTR or n-gram entropy as a cheap shortcut-overfit diagnostic, and real Qwen3-8B tokenization before final weight materialization. BPE fragmentation, clause depth, and embedding clustering are useful later but not necessary to ship this design.

One note: `scripts/analysis/analyze_kant_training_corpus.py` mirrors `build_examples()` rather than literally reusing it. Counts match `train_metadata.json`, so this is not a block, but DR-2 should record the maintenance risk.

## MEDIUM-2: MODIFY
Validation split + early stopping is sufficient only if the split is grouped and the weighted loss is normalized. Random 10% split is not sufficient once synthetic monolog rows duplicate source turns.

No metadata leakage is present if `language`, `token_count`, and `marker_density` stay outside ChatML/model inputs and are removed before `model(**inputs)`. The weighted reduction must be weighted-mean, not default mean over a pre-weighted loss tensor, or LR/batch scaling becomes unstable.

## MEDIUM-3: MODIFY
`dialog_id="<orig>_mono"` separation alone does not prevent eval contamination because the semantic duplicate can land in eval while its source turns are in train.

Required change: generate monolog re-casts only after a group split, derive them only from training-phase rows, store `synthetic_source_dialog_id` + source turn indices, and keep synthetic rows out of eval. Cap synthetic monolog rows to the stated ~150-300 range and report duplicate/source counts.

## LOW
- LOW-1: MODIFY. Before PR ship, append DA-14 to `.steering/20260513-m9-c-adopt/decisions.md` and fill DR-2 in `.steering/20260514-m9-c-adopt-retrain-v2-design/decisions.md`. The threshold pin file and `next-session-prompt.md` were not present at review time, so add/cross-link them after HIGH reflection.
- LOW-2: minor. `design-final.md` should replace “sample_weight standard path” wording, correct the “30x” clamp framing because the formula’s practical min is ~0.34 before normalization, and move the validation/early-stopping requirements into §3 rather than leaving them only in Risks.

## Closing note
Design-only PR can ship after HIGH-C and HIGH-D are edited, with HIGH-A validation/fallback language added. Do not require Candidate C before first training, but carry targeted-hybrid collection as the explicit fallback if weighted v2 fails DA-14 or overfit diagnostics. Tests were not re-run for this review.

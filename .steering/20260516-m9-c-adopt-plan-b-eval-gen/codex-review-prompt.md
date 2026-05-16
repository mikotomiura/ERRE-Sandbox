# Codex independent review — m9-c-adopt Plan B verdict (eval-gen PR)

## Context

PR `feature/m9-c-adopt-plan-b-eval-gen` implements the Plan B eval shard
generation + 4-encoder rescore + verdict aggregator for kant. The
retrain artifact (`data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500/`,
eval_loss=0.18259) was produced by PR #181 (merge SHA `f68ac63`); this
PR generates the inference shards, runs the 4-encoder rescore against
the Plan B D-2 allowlist, computes Burrows/ICC/throughput, and writes
the kant ADOPT / Phase E A-6 verdict.

## Scope of review

Apply HIGH / MEDIUM / LOW classification and report each finding
verbatim back into `.steering/20260516-m9-c-adopt-plan-b-eval-gen/
codex-review.md`. Focus on the *new* surfaces in this PR and the
*verdict-justification* path; the prep PR #183 retrain artefacts are
already merged and out of scope here.

### 1. `rescore_vendi_alt_kernel.py` CLI extension (blocker 2 resolution)

- `--v2-shards` / `--nolora-shards` / `--kernel-type` / `--allowlist-path`
  flags. Verify backward-compatibility (no flags → Plan A defaults
  unchanged), and that the `_resolve_encoder_default` helper correctly
  cross-validates `kernel_type=lexical_5gram` against the encoder
  argument.
- `_encode_pools_lexical_5gram` pool-fit semantics (DE-1 in design.md).
  Concern: pool-fit IDF means the IDF basis depends on BOTH conditions'
  utterances. Could a future PR introduce a Simpson's-style artefact if
  one condition disproportionately drives the vocabulary? Plan B kant
  shards are ~equal mass (n_v2 ≈ n_nolora) so this is theoretically a
  non-issue, but is the rationale durable enough to keep across
  nietzsche / rikyu (which may have asymmetric shards)?
- `library_versions_match_d2`: the new overlap-only check means
  `lexical_5gram` runs skip the `sentence_transformers` pin (it isn't
  loaded). Is this an acceptable downgrade of the D-2 enforcement
  contract, or does it leak audit guarantees?

### 2. `da14_verdict_plan_b.py` aggregator

- `_encoder_agreement_axis` — encoder agreement axis logic. 3-of-4
  primary, 2+ required, plus "all primary natural d share negative sign"
  direction discipline (BGE-M3 sign-flip generalisation). Edge case: if
  a primary has `natural_cohens_d=None` (e.g. degenerate window),
  `natural_ds` list excludes it but `all_negative` still passes on the
  remaining encoders — is that the intended semantic? Should `None`
  treated as a direction failure?
- `_aggregate_verdict` — ADOPT requires *all four* axes (encoder
  agreement, Burrows, ICC, throughput). Confirm this matches the Plan B
  design spec (`.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-
  allowlist-plan-b.json` `encoder_agreement_axis` + DA-14 thresholds).
- Threshold constants: `_VENDI_D_GATE=-0.5`, `_BURROWS_REDUCTION_GATE_PCT=5.0`,
  `_ICC_GATE=0.55`, `_THROUGHPUT_GATE_PCT=70.0`. Cross-check against
  `.steering/20260517-m9-c-adopt-plan-b-design/decisions.md` and the
  original DA-14 verdict frozen reference (PR #160 era).

### 3. Plan B eval shard generation

- The 4 shards (`kant_r8v3_run{0,1}_stim.duckdb` + `kant_planb_nolora_run{0,1}_stim.duckdb`) use the same `tier_b_pilot.py` invocation
  parameters as the v2 baseline (`--turn-count 300 --cycle-count 6
  --multi-turn-max 6`). Confirm apples-to-apples with the v2 reference
  (`data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`).
- SGLang launch (`launch_sglang_plan_b.sh`): K-α v5 invocation +
  `--lora-paths kant_r8v3=...checkpoint-1500 --max-loras-per-batch 1
  --max-lora-rank 8`. Cross-check against DR-4 in
  `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md`.
- no-LoRA shards: `--no-lora-control --rank 0` route via base Qwen3-8B.
  Confirm that the `_NO_LORA_MODEL` routing in `tier_b_pilot.py` matches
  the v2 baseline's no-LoRA path so the comparison is methodologically
  identical.

### 4. ADOPT / Phase E A-6 verdict justification (RESOLVED: PHASE_E_A6)

Verdict outputs (`da14-verdict-plan-b-kant.json` +
`da14-verdict-plan-b-kant.md`) reached **PHASE_E_A6** (REJECT, rank=16
spike routing). Per-axis result:

| axis | result | gate | value |
|---|---|---|---|
| Encoder agreement | FAIL | 3-of-4 primary, 2+ | 0/3 primaries pass all 3 axes; direction discipline FAIL |
| Burrows reduction% | FAIL | ≥5pt + CI lower>0 | −1.95% |
| ICC(A,1) | PASS | ≥0.55 | 0.9083 |
| Throughput pct | PASS | ≥70% | 99.17% |

Per-encoder natural d:
- MPNet: -0.5264 (negative direction, std_pass=False due to CI)
- E5-large: +0.4781 (opposite sign — retrain shifted Vendi semantic ↑, not ↓)
- lexical_5gram: +0.1805 (opposite sign)
- BGE-M3 (exploratory): +0.3317

Cross-encoder sign disagreement is **worse than Plan A** (where MPNet
and E5 agreed on negative, only BGE-M3 flipped). In Plan B even
lexical-5gram (retrieval-trained-free, shallow stylometry) flipped
positive.

**Review questions for Codex**:
- Is the verdict logic correctly routing to PHASE_E_A6 given 2 axes
  fail? (we expected ADOPT requires ALL 4 axes PASS, single fail →
  PHASE_E_A6)
- Are the REJECT root cause hypotheses (decisions.md DR-1) plausible?
  Specifically: (a) WeightedTrainer Blocker 2 (sample weight collapse,
  retrain blockers.md ブロッカー 2), (b) rank=8 capacity limit,
  (c) retrain corpus shifting persona style in unintended encoder
  directions
- Does the Burrows reduction% = −1.95% (LoRA-on Burrows HIGHER than
  no-LoRA) indicate the retrain made German function-word stylometry
  WORSE rather than better? Is this a known failure mode for narrow
  de_monolog training corpora?
- Should DA-16 ADR (rank=16 spike) prioritize fixing WeightedTrainer
  Blocker 2 BEFORE rank expansion (i.e. order: weight fix retrain
  rank=8 → if still REJECT then rank=16), or expand rank first?

### 5. Pre-push CI parity

Verify `pre-push-check.sh|.ps1` passes 4-stage check (ruff format
--check / ruff check / mypy src / pytest -q --ignore=tests/test_godot)
before merge.

## Required output format

```markdown
# Codex review — Plan B eval-gen PR

## HIGH
- [HIGH-1] ...
- [HIGH-2] ...

## MEDIUM
- [MEDIUM-1] ...

## LOW
- [LOW-1] ...

## OUT-OF-SCOPE / NICE-TO-HAVE
- ...
```

HIGH findings MUST be addressed before PR merge (apply changes or
explicit defer with rationale in decisions.md).
MEDIUM findings MUST be decided in decisions.md (apply/defer/reject).
LOW findings may be deferred to blockers.md with rationale.

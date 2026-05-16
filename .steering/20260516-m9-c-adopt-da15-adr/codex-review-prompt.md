# Codex independent review — DA-15 ADR (m9-c-adopt retrain v2 REJECT escalation)

You are an **independent reviewer** for an ADR (Architecture Decision Record)
proposed by Claude Code. The reviewer model is **gpt-5.5 (xhigh reasoning
effort)**; the ADR was drafted by **Claude Opus 4.7** (V1 = main agent) and
**Claude Opus 4.7** (V2 = Task tool subagent dispatched without V1 in
context). Both arms are the same model family, hence this review is the
**only** cross-model-family check.

## Your task

1. Read the empirical inputs (DA-14 verdict, prior ADRs, retrain v2 design) to
   ground yourself.
2. Read V1 / V2 / comparison drafts verbatim.
3. Issue **HIGH-N / MEDIUM-N / LOW-N** findings on the merged final decision
   (Plan A → Plan B sequential + Hybrid H-α pre-staging, Plan C → Phase E A-6).
4. **Detection priority — most important first**:
   - **HIGH-3 violation detection** = the *literal top priority*. DA-14
     thresholds (Vendi d ≤ -0.5, Burrows reduction ≥ 5%, ICC(A,1) ≥ 0.55) are
     *immutable* per `.steering/20260513-m9-c-adopt/decisions.md` DA-14. If the
     ADR draft re-defines, softens, replaces, re-scopes, or otherwise erodes
     these thresholds — flag as **HIGH-3 violation** even if the literal
     numerals are unchanged. The Vendi kernel swap (Plan A) is a known grey
     zone — see OQ-1 below.
   - **Plan A's HIGH-3 grey-zone resolution** = is "Vendi encoder swap with
     apples-to-apples rescoring of both arms" a methodology shift (acceptable)
     or a threshold movement in disguise (unacceptable)?
   - **Cross-arm leakage detection** = did V1 and V2 reach the same conclusion
     through *independent* reasoning, or do they share a structural blind spot
     traceable to their shared Claude lineage? Specifically: is there a
     consideration both V1 and V2 missed that a different model family would
     surface?
   - **Plan A/B/C numerical estimates** = are the predicted Cohen's d ranges
     literature-grounded or hand-waved? Particularly:
     - Plan A multilingual-e5 / bge-m3 for persona-style discrimination: is
       there real evidence these encoders surface stylistic vs lexical shifts
       better than MPNet?
     - Plan B de+en mass 0.489 → 0.60 (+11.3pp) producing Vendi d delta -0.3
       to -0.8: is this linear extrapolation defensible?
     - Plan C rank=16 on Qwen3-8B + NF4 + LoRA: VRAM envelope, OOM risk on a
       12GB-safety-margin GPU. Literature anchor for r=16 LoRA on a ~5k
       weighted-CE dataset.
   - **Hybrid H-α validity**: pre-staging Plan B driver during Plan A wall
     time (~1-2h). Is this premature work or genuine parallelism?
5. For each finding, propose a concrete fix (verbatim text change, or new
   constraint to add to the ADR).

## Required output format

```
[HIGH-N] <title>
- Finding: <what is wrong / risky>
- Why it matters: <impact on decision quality / HIGH-3 / future portability>
- Fix: <concrete text or constraint change>
- Severity rationale: <why HIGH not MEDIUM>
```

Same format for MEDIUM / LOW. End with a `Verdict:` line:
- `ADOPT` (no changes needed)
- `ADOPT-WITH-CHANGES` (HIGH findings must be reflected, others are optional)
- `REJECT-AND-REDRAFT` (HIGH findings fundamentally undermine the decision)

---

## Empirical inputs (read first)

### DA-14 verdict (`.steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json`)

```json
{
  "axes": {
    "vendi_semantic": {
      "v2_mean": 33.182859369999,
      "no_lora_mean": 33.31090056393359,
      "diff_v2_minus_nolora": -0.12804119393459246,
      "diff_ci_95": [-0.8540036491321873, 0.6211691251338816],
      "cohens_d": -0.1788470533504207,
      "threshold_point": -0.5,
      "threshold_ci": "ci_upper < 0",
      "pass": false
    },
    "burrows_reduction": {
      "v2_mean": 114.60777995370626,
      "no_lora_mean": 115.10090300065475,
      "reduction_pct": 0.4284267404450269,
      "reduction_ci_95_pct": [-1.8741679421100097, 2.4694606443580356],
      "threshold_point": 5.0,
      "threshold_ci": "ci_lower > 0",
      "pass": false
    },
    "icc_a1": {
      "v2_point": 0.9128856624319415,
      "v2_ci_95": [0.8807947019867548, 0.9691714836223514],
      "no_lora_point": 0.9061166429587485,
      "threshold_point": 0.55,
      "threshold_ci": "ci_lower >= 0.50",
      "pass": true
    },
    "throughput": {
      "v2_rate_focal_per_s": 0.82,
      "no_lora_rate_focal_per_s": 0.83,
      "throughput_pct_of_baseline": 98.79518072289156,
      "threshold_point": 70.0,
      "pass": true
    }
  },
  "primary_axes_passed": 1,
  "primary_quorum": "2_of_3",
  "verdict": "REJECT",
  "directional_v_prior_lora_r8": {
    "vendi_prior": 34.701,
    "vendi_v2": 33.182859369999,
    "vendi_direction": "REVERSED toward goal",
    "burrows_prior": 113.7227,
    "burrows_v2": 114.60777995370626,
    "burrows_direction": "slight degradation"
  }
}
```

### Pre-training audit (DI-5)

- N_eff = 3886.4 ✅ (target 1500)
- top 5% weight share = 0.139 ✅ (target ≤ 0.35)
- **de+en weighted mass = 0.489 ⚠️ soft warning** (target 0.60)
- per-language weighted mass: ja=0.498, en=0.278, de=0.211, mixed=0.013

### Training execution (DI-7)

- 4000 steps × NF4 LoRA r=8 took 16h19m on G-GEAR (8h envelope blown 2x)
- final eval_loss = 0.180 (step 500=0.191 → step 2000=0.166 → final=0.180,
  **mild overfit tendency between step 2000 and final**)
- peak VRAM = 10.62 GB (12 GB safety margin intact)

### DA-14 spec (`.steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json`)

```json
{
  "schema_version": 1,
  "adr": "DA-14",
  "primary_axes": {
    "vendi_semantic": {"metric": "cohens_d", "direction": "less_than_or_equal", "point_threshold": -0.5, "ci_constraint": "ci_upper < 0"},
    "burrows_reduction": {"metric": "burrows_delta_reduction_pct", "direction": "greater_than_or_equal", "point_threshold": 5.0, "ci_constraint": "ci_lower > 0"},
    "icc_a1": {"metric": "icc_a1", "direction": "greater_than_or_equal", "point_threshold": 0.55, "ci_constraint": "ci_lower >= 0.50"},
    "throughput": {"metric": "throughput_pct_of_baseline", "direction": "greater_than_or_equal", "point_threshold": 70.0}
  },
  "quorum_rule": {"kant": "2_of_3_primary", "nietzsche": "2_of_3_primary", "rikyu": "2_of_2_primary_burrows_named_limitation"},
  "ai_decision_protocol": {
    "all_primary_axes_pass": "ADOPT",
    "any_primary_axis_fail_with_quorum_below_2": "REJECT",
    "vendi_fail_but_others_pass": "ESCALATE_DA15_vendi_kernel_swap",
    "weight_concentration_audit_fail": "ESCALATE_CANDIDATE_C_targeted_hybrid"
  },
  "weight_audit_thresholds": {"n_eff_min": 1500, "n_eff_fallback_trigger": 1000, "top_5_pct_weight_share_max": 0.35, "top_5_pct_weight_share_fallback_trigger": 0.50, "de_en_weighted_mass_target": 0.60}
}
```

### Codebase pointers (Plan A code-change scope)

- `src/erre_sandbox/evidence/tier_b/vendi.py:294-322` — `_load_default_kernel`
  hardcodes `sentence-transformers/all-mpnet-base-v2`
- `scripts/m9-c-adopt/compute_baseline_vendi.py:188` — uses default kernel
- `src/erre_sandbox/training/dataset.py` — monolog re-cast logic (no language
  filter)
- `src/erre_sandbox/training/weighting.py` — per-language factor constants
- `scripts/m9-c-adopt/tier_b_pilot.py` — SGLang LoRA driver (no de-focused
  collector)

### Step 0 feasibility scan result

- **No de-focused monolog generator exists** in `scripts/m9-c-adopt/`. Plan B
  requires NEW driver code (~1.5h implementation) OR extension of existing
  `dataset.py` monolog re-cast with `where language == "de"` filter (B-1, ~50
  LOC).
- de=15.9% of 5022 examples ≈ 800 raw, expected 2-turn Kant pairs ≈ 40-60
  examples. **B-1 alone yields fewer than the 250+ target**, so Plan B effectively
  requires B-2 (new collector) or another data source.

---

## V1 draft (main agent, Claude Opus 4.7)

[Verbatim content of `da15-draft-v1.md` follows]

```markdown
# DA-15 draft V1 — main agent 生成

> **生成主体**: main Claude Code session (Opus 4.7)。本 file は **/reimagine
> 対象**であり、V2 (Task tool subagent 独立生成) と比較して使い分ける。確定 ADR
> ではない。

[... full V1 content embedded for Codex review; see
.steering/20260516-m9-c-adopt-da15-adr/da15-draft-v1.md for verbatim ...]
```

(Codex: read the file at the path above directly. It is included in the same
repo as this prompt.)

---

## V2 draft (Task tool subagent, Claude Opus 4.7, independent generation)

(Codex: read `.steering/20260516-m9-c-adopt-da15-adr/da15-draft-v2.md`
directly.)

---

## Comparison + hybrid analysis

(Codex: read `.steering/20260516-m9-c-adopt-da15-adr/da15-comparison.md`
directly.)

---

## Proposed final decision (the thing you are reviewing)

**Plan A → Plan B sequential, with Hybrid H-α pre-staging, Plan C → Phase E A-6.**

Concretely:

1. **Plan A** (Vendi kernel swap): parameterise `_load_default_kernel` in
   `vendi.py` to accept an encoder name. Rescore v2 multi-turn pilot and
   no-LoRA baseline windows under at least 2 of {multilingual-e5-large, bge-m3,
   philosophy-domain BERT}. Bootstrap CI on the rescored `cohens_d`. Compute
   envelope: 1-2h.

2. **During Plan A wall time, pre-stage Plan B driver** (Hybrid H-α): start
   skeleton of `scripts/m9-c-adopt/de_focused_monolog_collector.py` and the
   group-aware split extension. ~1.5h dead-time work. NOT merged unless Plan A
   fails.

3. **Plan A gate to Plan B**:
   - If Plan A pass (Vendi d ≤ -0.5 under at least 2 candidate kernels with CI
     upper < 0) → **kant ADOPT via 2-of-3 (Vendi-swapped + ICC)**, Plan B
     pre-stage shelved for future use.
   - If Plan A fail → **Plan B-2** (full new collector) triggers: ~3h
     G-GEAR shard generation + ~20h retrain + ~1h pilot recapture + ~30min
     consumers = ~25h.

4. **Plan C never runs in DA-15.** Reserved for Phase E A-6 (per DA-12's
   provisional rank=8 carry-over decision and v2's mild overfit signal).

5. **HIGH-3 self-review** (must be in ADR D-15):
   - DA-14 numerical thresholds unchanged
   - Plan A is a methodology shift, not a threshold movement (per DA-14
     `ai_decision_protocol.vendi_fail_but_others_pass = ESCALATE_DA15_vendi_kernel_swap`)
   - Apples-to-apples: rescore *both* v2 and no-LoRA baseline under the same
     swapped kernel before computing d
   - Encoder candidates + version pins + commit SHA pre-registered in D-2
     before reading the rescored verdict

---

## Open questions to address

- **OQ-1** (HIGH-3 grey zone): Vendi kernel swap = methodology shift
  (acceptable) or threshold movement in disguise (unacceptable)?
- **OQ-2**: encoder candidate list — multilingual-e5-large + bge-m3 sufficient?
  Should we also commit to a philosophy-domain BERT?
- **OQ-3**: vendi.py code change scope (~50 LOC) — same PR as ADR, or separate
  prep PR?
- **OQ-4**: should the soft warning (de+en=0.489 < 0.60) be retrospectively
  promoted to hard fallback trigger?
- **OQ-5**: confirm rank=16 belongs to Phase E A-6, not DA-15?
- **OQ-6**: kant ADOPT via 2-of-3 (Vendi-swapped + ICC) when Burrows still
  fails — acceptable per DA-14 quorum_rule, or should Burrows axis fail be
  documented as a per-persona limitation?
- **OQ-7** (cross-arm leakage): V1 and V2 both adopt sequential A → B. Is
  there a different model family blind spot here? E.g., should we be doing
  *neither* (a different escalation entirely)?

Begin your review.

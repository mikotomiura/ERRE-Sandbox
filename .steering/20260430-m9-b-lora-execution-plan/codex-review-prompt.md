# Codex Independent Review Request — M9-B LoRA Execution Plan

You are an independent senior reviewer for a research project (ERRE-Sandbox, an autonomous
3D society of historical thinkers powered by local LLMs). You operate as `gpt-5.5` with
`xhigh` reasoning effort. Your role is to provide an **independent perspective** that the
primary planner (Claude `opus-4-7`) cannot reach due to single-model bias.

The primary planner has produced a design comparison after applying `/reimagine` (deliberate
v1-vs-v2 antithesis exercise). Your job is to **stress-test the hybrid adoption** and call
out the highest-risk decisions before the user authorizes implementation.

## Files to read (verbatim, in order)

1. `.steering/20260430-m9-b-lora-execution-plan/requirement.md`
2. `.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md`
3. `.steering/20260430-m9-b-lora-execution-plan/design-v1.md`
4. `.steering/20260430-m9-b-lora-execution-plan/design-v2.md`
5. `.steering/20260430-m9-b-lora-execution-plan/design-comparison.md`

Background context (already merged):
- `.steering/20260428-m9-lora-pre-plan/decisions.md` (D1-D5 ADR baseline, frozen by PR #110)
- `.steering/20260428-m9-lora-pre-plan/design.md` (defer-and-measure methodology)
- `CLAUDE.md` (project ground rules: `/reimagine` mandatory for hard design,
  Plan→Clear→Execute handoff, Codex review mandatory for high-difficulty design)
- The hardware: G-GEAR mini = single RTX 4080 (16GB VRAM), runs SGLang + Ollama. MacBook is
  master/dev. No cloud LLM API allowed (zero-budget constraint).
- Prior empirical findings live in `.steering/20260426-m7-slice-zeta-live-resonance/observation.md`
  if you need ζ-3 cadence numbers (36:74:16 persona-driven movement speed divergence).

## What we want from you

Critically review the **hybrid adoption** documented in `design-comparison.md` (v2-B base
+ minor v1 retentions on F/J5). Specifically:

1. Is the v2-B antithesis ("evaluation infrastructure first, defer LoRA application")
   genuinely better than v1 ("implement LoRA ASAP")? Or is the planner overweighting the
   risk of "applying LoRA without an offensive metric"?
2. Are there **third options** the planner missed (neither v1 nor v2-B)?
3. Pick the 3 highest-risk decisions in the hybrid plan and explain why.
4. The planner deliberately listed **10 open questions** at the end of `design-comparison.md`
   — answer each with your independent judgment.

## Specific points to stress-test (please address each)

### Strategic / framing
- The reframing of M9-B's deliverable from "LoRA implementation plan" to "go-no-go
  judgment basis" — sound? Or does this turn M9-B into a moving target?
- Is splitting M9 into M9-B (plan) → M9-eval-system (eval infra) → M9-C (LoRA implementation)
  proportionate, or does it fragment momentum on a solo project?
- The 4th trigger condition (`prompting plateau`: <5% Tier B improvement over 2 consecutive
  runs) is the planner's strongest empirical innovation. Critique its operational definition.
  How would you measure "<5% improvement" robustly given Tier A-B metric noise?

### Quantization / library / serving (A/B/C)
- Is QLoRA NF4 truly the only realistic quantization for 16GB + qwen3:8b + 3 persona swap?
  Are there alternatives (AWQ + LoRA, GPTQ + LoRA, sharded FP8) that the planner overlooked?
- The deferral of unsloth-vs-PEFT to M9-C — does this leak premature optimization into M9-B
  in any subtle way? Or is the deferral clean?
- vLLM `--enable-lora` migration: does the cost of migrating off SGLang/Ollama justify
  full LoRA support, given that SGLang LoRA reached v0.3+ around 2025? Has SGLang's LoRA
  matured since the planner's snapshot?

### Dataset / Parquet / evaluation epoch (D/E/F)
- The Parquet schema in v2 makes evaluation metrics first-class fields. Is this **evaluator
  contamination** (training data colocated with metric values that were computed using
  models we may later fine-tune)? Or does `evaluation_epoch` partitioning + `persona_id`
  partitioning fully isolate this risk?
- Is the AND-of-4 trigger too strict? Suggest the most likely binding constraint.
- Should the evaluation-frequency policy ("1 evaluation run per 100 turns") be tighter or
  looser given that judge LLMs (Prometheus 2 8x7B) cost VRAM on the same hardware?

### Persona / adapter / drift (G/H/I)
- Is N=4 deferral to M10 a missed opportunity to validate the evaluation infrastructure
  on a 4-persona setup before committing to LoRA? Or is N=3 enough?
- The two-way drift gate (defensive + offensive) — is the offensive gate's "post-LoRA
  Tier B < pre-LoRA baseline → rollback" a circular dependency on a noisy metric? Should
  there be a quorum (e.g., 2-of-3 Tier B sub-metrics regress) instead of any-one regression?

### Evaluation framework (J)
- Critically evaluate the "5% absolute improvement requirement" (J5 offensive gate). Is
  this an empirically grounded number for LoRA on philosophical role-play, or borrowed
  from domain-general LoRA papers? What number would you propose, with rationale?
- The evaluation surface (Tiers A/B/C/D × 6 metric families surveyed in
  `research-evaluation-metrics.md`) is wide. Pick the **3 minimum-viable metrics** that
  must work on day one, and the **3 nice-to-have metrics** that can be deferred to M10.
- LIWC-22 license risk: is Empath / spaCy / a custom dictionary a credible OSS alternative,
  or does losing LIWC's psycholinguistic depth degrade the persona-fit signal materially?
- The honest-gap statement (philosophical depth is partly irreducible to single-number
  metrics) — does this undermine the entire J axis, or is the multi-channel report
  sufficient for the research framing?
- For golden set construction (3 persona × 100 reference utterances from canonical corpus):
  is 100 utterances enough? Should the planner aim for 300? 1000?

### Schedule / momentum / risk
- M9 milestone slips from 1 task (M9-C originally) to 3 tasks (M9-B / M9-eval-system /
  M9-C). For a solo researcher, is this delay acceptable, or does it risk losing momentum
  before LoRA is even attempted?
- Is there a way to **parallel-track** M9-eval-system and a small LoRA spike (e.g., on
  a single persona, with full awareness that the offensive gate is not yet computable)
  to keep momentum?
- What's the worst-case failure mode the hybrid plan does NOT defend against?

## Open-question answers requested (from `design-comparison.md`)

Please answer all 10 questions in `design-comparison.md` ## "残された判断 (codex review に問う)"
section. For each, give your independent judgment (not a summary of what the planner already
wrote).

## Output format (mandatory)

Produce a single markdown report. Use this structure exactly:

```markdown
# Codex Independent Review — M9-B LoRA Execution Plan

## Overall verdict
- One sentence: is the hybrid adoption sound, qualified-sound, or unsound?

## Top 3 highest-risk decisions
1. ...
2. ...
3. ...

## Findings

### HIGH (must address before M9-B closure)
- **HIGH-1**: <one-line title>
  - Issue: ...
  - Impact: ...
  - Recommendation: ...
- **HIGH-2**: ...
- (as many HIGH as warranted, but be selective — HIGH means M9-B should not close until addressed)

### MEDIUM (should address; planner judges accept/defer)
- **MEDIUM-1**: ...
- ...

### LOW (nice-to-have, defer-able)
- **LOW-1**: ...
- ...

## Answers to 10 open questions
1. ...
2. ...
... (all 10)

## Final note
- One paragraph: anything the planner clearly missed, or anything the planner is right
  about that you'd reinforce.
```

## Constraints

- **No code generation**. This is a review, not an implementation task.
- **No file edits**. Read-only review.
- **Verbatim citation** when you reference specific lines from the design docs (use file:line
  format, not paraphrase).
- **Be candid**. The planner's judgment is not authoritative. If v1 was actually better
  than v2-B, say so. If neither is good, say that.
- **Stay under 4000 words total**. Density over breadth.

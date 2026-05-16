# Codex independent review request — DA-16 ADR (kant Plan B PHASE_E_A6 順序判断)

## Role + report format

You are an **independent senior reviewer** for an in-progress ADR
(architecture decision record). Your task is to review the DA-16 ADR in
this repo and report findings in the following format:

- **HIGH**: design flaws / errors / unsafe assumptions that must be
  resolved **before this ADR is merged** to main. Quote the offending
  line(s) with file path + line number.
- **MEDIUM**: concerns that warrant explicit decision (record adopt /
  defer / reject in a follow-up `decisions.md` entry). Quote the offending
  line(s) with file path + line number.
- **LOW**: nits / wording / future improvements. May be deferred to
  next-session `blockers.md` persistently.

End with a one-line **Verdict**: `ADOPT` / `ADOPT-WITH-CHANGES` / `BLOCK`
/ `REVISE`.

## Context (read these first, in order)

The repo is at `/mnt/c/ERRE-Sand_Box` (Windows-mounted under WSL2). Read
these files completely before reviewing:

1. `.steering/20260517-m9-c-adopt-da16-design/requirement.md`
2. `.steering/20260517-m9-c-adopt-da16-design/design.md`
3. `.steering/20260517-m9-c-adopt-da16-design/decisions.md` (4 decisions:
   DA16-1 ordering, DA16-2 fix approach, DA16-3 PR split, DA16-4
   thresholds unchanged)
4. `.steering/20260517-m9-c-adopt-da16-design/blockers.md`
5. `.steering/20260517-m9-c-adopt-da16-design/tasklist.md`

For full context (background that DA-16 ADR depends on):

6. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1
   (verdict result + root cause hypothesis)
7. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.md`
   (4-axis verdict + per-encoder direction results)
8. `.steering/20260518-m9-c-adopt-plan-b-retrain/blockers.md` ブロッカー 2
   (WeightedTrainer sample weight collapse, mitigation candidates (a)/(b)/(c))
9. `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-5 / DR-6
   (existing WeightedTrainer patch history)
10. `src/erre_sandbox/training/weighting.py:411-462`
    (`compute_weighted_causal_lm_loss` — the function DA16-2 proposes to
    modify)
11. `src/erre_sandbox/training/train_kant_lora.py:1687-1715`
    (`WeightedTrainer.compute_loss` — call site of (10))
12. `tests/test_training/test_weighted_trainer.py`
    (existing unit tests for (10), batch=2 only — does NOT detect the
    Blocker 2 bug)

## What to check (priority order)

### HIGH priority audit targets

1. **DA16-1 ordering logic**: Is the argument that "direction
   disagreement (MPNet−, E5/lex5+) is better explained by weighting bug
   than by capacity" actually sound? Could rank=16 also produce
   per-encoder direction disagreement (e.g., through differential
   overfitting per encoder's affinity)? If yes, the rationale for
   choosing A over B weakens.

2. **DA16-2 (`.mean()` reduce)**: Is the proposed math change actually
   correct for batch=1 + gradient_accumulation_steps=8 semantics? The
   ADR claims:
   - `.mean()` over batch=1 gives `loss = l[0] * w[0]`
   - HF Trainer's micro-batch independent backward then accumulates
     `(1/grad_accum) * sum_i (l_i * w_i)` across micro-batches
   - This makes the gradient weight-aware

   Verify this against `transformers.Trainer.training_step` actual
   behavior (HF 4.57.6). Specifically: does HF Trainer divide by
   `accumulation_steps` inside `training_step` or only at
   `optimizer.step()`? And does the weighted-vs-unweighted comparison
   hold when `weights.mean()` across the full dataset is exactly 1
   (claimed by `compute_example_weight` normalization)?

3. **Existing test fixture compatibility**: The ADR claims existing
   `test_weighted_trainer.py` only needs the `expected` formula
   rewritten because batch=2 with `weights=[3.0, 1.0]` has
   `weights.mean()=2.0`, so `(l*w).sum()/sum(w)` and `(l*w).mean()`
   produce DIFFERENT absolute values. Trace through the actual math:
   - Old: `(l0*3 + l1*1) / 4`
   - New: `(l0*3 + l1*1) / 2`
   - These differ by factor 2 — is the ADR's "rewrite expected formula"
     guidance sufficient, or does this break the regression test's
     CI verbatim semantic (the test name says "matches_manual" — the
     test was supposed to encode the verbatim Codex HIGH-C formula)?
   - If the verbatim semantics change, DA16-2 should also document
     **how Codex HIGH-C formula is amended** (not just the test).

4. **PR-3 / PR-4 / PR-5 dependency graph**: Is PR-3 → PR-4 separation
   actually beneficial? PR-3 produces an adapter artifact + eval_loss
   trajectory; PR-4 produces a verdict. Could a reviewer of PR-3 verify
   PR-3 without PR-4's verdict result? If not, this is artificial
   splitting.

5. **DA16-4 thresholds unchanged**: Is this position actually defensible
   given that v3 was REJECTED with direction disagreement? Or is there
   a credible case that the thresholds themselves are mis-calibrated
   for Plan B's 4-encoder agreement axis (which is new in Plan B and
   was set at 3-of-4 primary)?

### MEDIUM priority audit targets

1. **`.mean()` reduce when batch contains a zero-weight example**: With
   the old formula `weights.sum()` clamp at 1e-8 ensured no division by
   zero. With `.mean()`, a batch entirely of zero-weight examples
   produces `loss=0` (and zero gradient), which is silently skipped.
   Is this acceptable? Should the ADR add a safeguard?

2. **eval_loss scale change**: ADR DA16-2 trade-off mentions "v3
   eval_loss and v4 eval_loss are not directly comparable". But
   downstream tooling (`train_metadata.json` recording, EarlyStopping
   callback, dashboards) compares eval_loss across runs. Is there a
   risk that a tool silently assumes comparability?

3. **WSL2 codex review path**: The blockers.md from
   `20260516-m9-c-adopt-plan-b-eval-gen` says PowerShell + codex caused
   "hook: PreToolUse Failed". Does WSL2 reliably avoid this, or does
   `.codex/hooks/*.py` still risk firing in WSL2 with different env
   semantics (paths, line endings)?

### LOW priority audit targets

1. **Wording**: Any place where the ADR is ambiguous about what is
   "doc-only" vs "will be implemented in PR-2"?
2. **memory update timing**: Should `project_plan_b_kant_phase_e_a6.md`
   memory be updated BEFORE merge (this PR) or AFTER PR-4 verdict
   (when actual outcome is known)?

## Constraints

- Quote evidence with `path:line` references
- Do not propose alternate architectures — focus on whether the ADR's
  chosen path is sound
- The ADR is **doc-only**; do not propose code edits, only design /
  ADR text changes
- If you spot an issue that contradicts a memory note (e.g.,
  `feedback_pre_push_ci_parity.md`), surface it

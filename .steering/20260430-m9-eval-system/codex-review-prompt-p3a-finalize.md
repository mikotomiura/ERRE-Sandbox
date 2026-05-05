# Codex independent review — m9-eval-system P3a-decide finalization (script v2 extension)

> Codex `gpt-5.5 xhigh` independent review request. Invoke with:
> `cat .steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md
>  | codex exec --skip-git-repo-check`
> Save output verbatim to `codex-review-p3a-finalize.md`.
> This is the **third** Codex review on m9-eval-system P3a (after the
> design v1 review and the natural-gating v2 review). The first two
> reviewed *what to fix*; this one reviews *how to interpret* — the
> implementation that turns 6 re-captured pilot DuckDB cells into the
> empirical data that drives the ME-4 Hybrid Baseline Ratio ADR Edit.

---

## Context

**Where we are**: G-GEAR re-captured 6 cells (3 personas × 2 conditions)
under the natural-gating fix v2 (PR #133, main=`67576d5`). The `_summary.json`
shows clean cells (focal=30/198, total=84..342, dialogs=14..168). The Mac
finalization session must now:

1. Process those 6 DuckDB files into per-condition CI widths.
2. Surface a `ratio_summary` so the ME-4 ADR Edit can be made with empirical
   width comparison data.
3. Recognize that ME-4's `判定基準` references **3 metrics** (Burrows Delta /
   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
   are computable in this Mac session — Vendi Score and Big5 ICC are P4
   territory.

**The diff under review**: `feature/m9-eval-p3a-finalize` (HEAD `6210fc5`)
extends `scripts/p3a_decide.py` from v1 (`stimulus_only`) to v2
(`stimulus_and_natural`) and adds 7 unit tests.

## Files to read

Read these in order. The first two are the changed code + tests. The next
two are the authoritative ADR text + workflow checklist that the
implementation must serve. The last two are the receipts that constrain
the data shape.

1. `scripts/p3a_decide.py` — full file (changed)
2. `tests/test_evidence/test_p3a_decide.py` — full file (new)
3. `.steering/20260430-m9-eval-system/decisions.md` lines 124-176 — ME-4 ADR
   text (current state: 1 partial update, expects "二度目の Edit" with
   empirical ratio)
4. `.steering/20260430-m9-eval-system/tasklist.md` lines 308-380 — P3a-decide
   workflow with 4 unchecked items in the "next Mac セッション" block
5. `data/eval/pilot/_summary.json` — cell-level summary committed by G-GEAR
   (ground truth for n_utterances per cell)
6. `data/eval/pilot/_rsync_receipt.txt` — rsync protocol + md5 hashes (for
   downstream Mac session continuity)

Supporting code that the script depends on (read if needed for verdict
calibration):

- `src/erre_sandbox/evidence/bootstrap_ci.py` — `bootstrap_ci()` percentile
  + `hierarchical_bootstrap_ci()` cluster+block (returns
  `BootstrapCIResult` with `width = hi - lo`)
- `src/erre_sandbox/evidence/tier_a/burrows.py` and `mattr.py` — metric
  computation surfaces

## What I want you to evaluate

Focus on these six dimensions. Skip generic style-guide nits — ruff is
already clean.

### Q1. Statistical methodology of `_ratio_summary`

The function computes `width_ratio_natural_over_stimulus = nat_w / stim_w`
where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
MATTR width) / 2`, aggregated across 3 personas.

**The N is asymmetric by design**: stimulus pilot has focal_rows ≈ 198
per cell, natural has focal_rows = 30 per cell (Phase A floor `focal>=25`).
CI width scales with `~1/sqrt(n)`, so a width ratio of `~sqrt(198/30) ≈
2.57x` would be expected purely from sample-size effects, even if
per-utterance variability is identical.

The script surfaces a 10% tolerance verdict on the raw ratio. Three
caveat lines are emitted alongside.

- Is "expose raw ratio + caveat" the right design, given the asymmetry?
  Or should the script normalize widths by `sqrt(n)` before computing the
  ratio (so the verdict reflects per-sample variability, not n-scaling)?
- If normalization is recommended, what's the right form: `width *
  sqrt(n)` (per-sample variability proxy) vs `width * sqrt(n / n_target)`
  (extrapolated CI width at target n)?
- Is the 10% tolerance defensible for a verdict thresholding decision,
  or should it be wider (e.g., the `width * sqrt(n)` ratio is more
  variable per-bootstrap)?

### Q2. ME-4 §判定基準 fidelity

ME-4 says (decisions.md L145-148, post-Mac-edit):

> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
> - 両条件で sub-metric の **mean CI width が小さい比率** を採用
> - 両者が同等 (差 <10%) なら 200/300 default を維持

The implementation:

- Uses Burrows Delta + **MATTR** (not in ADR), defers Vendi + Big5 ICC.
- Computes "mean CI width が小さい比率" as `nat / stim` (natural smaller
  → ratio < 1).
- Applies the 10% tolerance.

Issues to assess:

- Is replacing "Vendi + Big5 ICC" with **MATTR** a defensible substitution
  for this finalization session, given that Vendi and Big5 ICC require
  the `[eval]` extras (sentence-transformers, scipy) and an Ollama judge
  loop that this Mac session intentionally does not run?
- If MATTR is acceptable as a temporary stand-in, should the ratio
  verdict carry an additional disclaimer that Burrows + MATTR may
  produce a different ratio than Burrows + Vendi + Big5 ICC?
- The "mean CI width が小さい比率" phrasing is ambiguous in Japanese — it
  could mean "the proportion of conditions where mean width is smaller"
  (= 1.0 if all metrics agree, 0.5 if split) or "the ratio of mean
  widths" (= mean_width_smaller / mean_width_larger). The implementation
  reads it as the latter. Is that the natural reading?

### Q3. ME-4 partial-update vs final-Edit gap

The tasklist L376 calls this Mac session "ME-4 ADR を **二度目の Edit** で
実測値 ratio 確定". The header docstring of the new script + this prompt
flag that ME-4 will need a **partial update #3** (not final close), since
Vendi + Big5 ICC are deferred to P4.

Should:

- The ADR text be edited to reflect that "final close" requires a third
  Edit post-P4, and the second Edit is itself a partial update?
- Or is the existing ADR re-open clause (decisions.md L162-169) sufficient
  ("re-open 条件" already covers DB9 quorum sub-metric discrimination, and
  P4 results would naturally trigger a re-open)?
- If the second Edit should be made into a final close (closing partial
  state) by accepting the lightweight-metric ratio with a P4-revisit
  marker, what's the right ADR re-open clause to add?

### Q4. Schema design (`p3a_decide/v2`)

Payload structure:

```json
{
  "schema": "p3a_decide/v2",
  "scope": "stimulus_and_natural",
  "note": "...",
  "cells": [{ persona_id, condition, n_utterances, metrics }, ...],
  "by_condition": {
    "stimulus": { "burrows...": {mean_width, n_cells, per_cell_widths, per_cell_n}, ..., "mean_combined_width": {value, n_metrics}},
    "natural": ...
  },
  "ratio_summary": { ... see Q1 ... }
}
```

Issues to assess:

- v1 used `personas` as the top-level array key; v2 renamed to `cells`.
  Is the rename justified or does it break a downstream contract?
  (Search the repo for `_p3a_decide.json` / `personas` consumers — I
  don't find any in the current tree, but please verify.)
- Should `mean_combined_width` be a separate top-level key alongside
  `by_condition` rather than embedded inside it?
- The `per_cell_widths` and `per_cell_n` arrays are kept for transparency
  but are not consumed by the verdict logic. Is that the right call, or
  should the script omit them to keep the JSON minimal?

### Q5. Test coverage adequacy

7 tests cover: aggregation positive path, aggregation skip path, 3
verdict branches (within / natural_wider / stimulus_wider), skip path,
pilot_path naming. Missing:

- End-to-end test against a synthetic DuckDB (could be built with
  `duckdb.connect(":memory:")` + minimal `raw_dialog.dialog` table).
- Boundary test at exactly 10% tolerance (edge of within / wider).
- Test that the v1→v2 schema bump is committed in the JSON output.

Should any of these be added before merge, or are they over-engineering
for a one-shot decide script?

### Q6. Anything else

Please flag any HIGH risk you see that doesn't fit Q1-Q5 — especially
around:

- Read-only DuckDB open (DB6 invariant)
- Behavior when one of the 6 cells has 0 utterances
- Bootstrap CI seed determinism across persona × condition
  (`bootstrap_ci(..., seed=0)` is identical for all calls — does that
  cause cross-persona correlation in the resampled distributions, or is
  that fine because each call resamples its own input)
- Anything that would invalidate the ME-4 ratio decision once data is
  fed in

## Report format

Use this exact structure. Verdicts: `ship` / `revise` / `block`.

```
## Verdict
<ship | revise | block> — <one-sentence summary>

## HIGH (fix before run)
- HIGH-1: <title>
  Issue: <what is wrong>
  Why it matters: <impact on ME-4 ADR or empirical validity>
  Suggested fix: <concrete change>
- HIGH-2: ...

## MEDIUM (fix before merge)
- MEDIUM-1: ...

## LOW (defer / nice-to-have)
- LOW-1: ...

## Confirmation (what looks right)
- ...

## Notes / open questions
- ...
```

Per `.codex/budget.json` policy this invocation should fit within
`per_invocation_max=200K`. Today's used: 483,220 / 1,000,000 daily budget
(48% — comfortable headroom for a third invocation today).

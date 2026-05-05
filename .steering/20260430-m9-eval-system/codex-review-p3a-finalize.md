Reading prompt from stdin...
OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/johnd/ERRE-Sand Box
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/johnd/.codex/memories] (network access enabled)
reasoning effort: xhigh
reasoning summaries: none
session id: 019df805-d6b6-7351-9457-f84fb94a238f
--------
user
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

hook: SessionStart
hook: SessionStart Completed
hook: UserPromptSubmit
hook: UserPromptSubmit Completed
codex
Using `$erre-workflow` first because this is an ERRE review flow, then I’ll read the script, tests, ADR/tasklist excerpts, and pilot receipts before writing the verdict in the requested structure.
exec
/bin/zsh -lc "sed -n '1,220p' .agents/skills/erre-workflow/SKILL.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
---
name: erre-workflow
description: >
  ERRE-Sandbox task workflow for Codex. Use when starting, designing, implementing,
  reviewing, or finishing repository work; when the user mentions /start-task,
  /add-feature, /fix-bug, /refactor, /reimagine, /review-changes, or /finish-task;
  or when .steering records, Codex setup, task plans, or implementation handoffs are needed.
---

# ERRE Workflow

This is the Codex-native replacement for the Claude slash-command workflow. Claude command
files in `.claude/commands/` are reference material only; Codex should execute the workflow
through normal tool use, `.steering/` records, skills, hooks, and custom agents.

## Quick Start

1. Read `AGENTS.md`, `docs/development-guidelines.md`, and the relevant domain skill.
2. Create or update `.steering/YYYYMMDD-task-name/` before implementation work:
   `requirement.md`, `design.md`, and `tasklist.md` are required.
3. For design-heavy work, keep implementation paused until a plan is accepted. If the task
   has multiple plausible designs, perform a reimagine pass before editing source files.
4. Implement in small steps, updating `tasklist.md` as work completes.
5. Verify with focused checks first, then the documented full checks when feasible.
6. Finish by reviewing the diff and recording any decisions or limitations.

Use subagents only when the user explicitly asks for delegation or parallel agent work.
When they do, prefer the project-scoped agents in `.codex/agents/`.

## Task Start

Create `.steering/YYYYMMDD-task-name/` with:

- `requirement.md`: background, goal, scope, out of scope, acceptance criteria.
- `design.md`: approach, changed areas, compatibility, test strategy, rollback.
- `tasklist.md`: checkboxes at roughly 30-minute granularity.
- `decisions.md`: only for meaningful tradeoffs or policy choices.
- `blockers.md`: only when blocked or carrying deferred risk.

Use the current local date in `YYYYMMDD`. Prefer a short kebab-case task name.

## Implementation Flows

- **Feature**: read existing patterns, document the design, implement narrowly, add tests or
  verification proportional to risk, update docs when behavior changes.
- **Bug fix**: reproduce or explain the failure, record root cause, add or identify a
  regression check when feasible, then make the smallest defensible fix.
- **Refactor**: establish current checks first, preserve behavior, change in small steps,
  and avoid mixing feature or bug-fix work into the same task.

For source edits under `src/erre_sandbox/`, always consider:

- `architecture-rules` for layer direction and GPL/cloud API constraints.
- `python-standards` for Python style.
- `error-handling` when async, retry, timeout, WebSocket, sqlite, or LLM fallback behavior changes.
- `test-standards` when adding or changing tests.

## Reimagine

Use this for architecture, public interfaces, difficult bugs, and designs with multiple
credible approaches:

1. Save the first plan as `design-v1.md`.
2. Re-read only `requirement.md` and produce a fresh alternative in `design.md`.
3. Compare the two in `design-comparison.md`.
4. Choose v1, v2, or a hybrid and record the reason in `decisions.md`.

Do not use reimagine after implementation has already created side effects that would need
manual rollback.

## Review And Finish

Before final delivery:

- Run focused checks for touched areas.
- Run `uv run ruff check src tests`, `uv run ruff format --check src tests`,
  `uv run mypy src`, and `uv run pytest` when feasible.
- Review `git diff` for unrelated changes and do not revert user work.
- Update `tasklist.md` and `design.md` with what actually happened.
- Mention skipped checks or residual risk in the final response.

Do not commit unless the user asks. If committing, use `git-workflow`.

codex
I’m going to keep this as a review-only pass unless the requested review artifact needs to be written. The main calibration points are the ADR language and whether the raw CI width ratio is empirical evidence or just an `n`-effect measurement.
exec
/bin/zsh -lc 'git status --short' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
?? .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md
?? .steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md

exec
/bin/zsh -lc "nl -ba tests/test_evidence/test_p3a_decide.py | sed -n '1,320p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba scripts/p3a_decide.py | sed -n '1,260p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     1	"""Unit tests for the pure aggregation/verdict helpers in scripts/p3a_decide.py.
     2	
     3	The script itself is exercised end-to-end during the P3a-decide finalization
     4	session against real DuckDB pilots. These tests cover the lightweight
     5	aggregation logic that drives the ME-4 ratio Edit, since the verdict branch
     6	selection is decision-critical.
     7	"""
     8	
     9	from __future__ import annotations
    10	
    11	import importlib.util
    12	import sys
    13	from pathlib import Path
    14	
    15	import pytest
    16	
    17	_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "p3a_decide.py"
    18	
    19	
    20	@pytest.fixture(scope="module")
    21	def p3a_decide():
    22	    spec = importlib.util.spec_from_file_location("scripts_p3a_decide", _SCRIPT)
    23	    assert spec is not None
    24	    assert spec.loader is not None
    25	    module = importlib.util.module_from_spec(spec)
    26	    sys.modules[spec.name] = module
    27	    spec.loader.exec_module(module)
    28	    return module
    29	
    30	
    31	def _make_block(
    32	    persona: str,
    33	    condition: str,
    34	    burrows_width: float | None,
    35	    mattr_width: float | None,
    36	    n: int = 30,
    37	) -> dict:
    38	    metrics: dict = {}
    39	    if burrows_width is not None:
    40	        metrics["burrows_delta_per_utterance"] = {
    41	            "point": 0.5,
    42	            "lo": 0.5 - burrows_width / 2,
    43	            "hi": 0.5 + burrows_width / 2,
    44	            "width": burrows_width,
    45	            "n": n,
    46	            "n_resamples": 2000,
    47	            "method": "percentile",
    48	        }
    49	    if mattr_width is not None:
    50	        metrics["mattr_per_utterance"] = {
    51	            "point": 0.7,
    52	            "lo": 0.7 - mattr_width / 2,
    53	            "hi": 0.7 + mattr_width / 2,
    54	            "width": mattr_width,
    55	            "n": n,
    56	            "n_resamples": 2000,
    57	            "method": "percentile",
    58	        }
    59	    return {
    60	        "persona_id": persona,
    61	        "condition": condition,
    62	        "n_utterances": n,
    63	        "metrics": metrics,
    64	    }
    65	
    66	
    67	def test_mean_widths_by_condition_aggregates_per_persona(p3a_decide):
    68	    blocks = [
    69	        _make_block("kant", "stimulus", 0.20, 0.10, n=198),
    70	        _make_block("nietzsche", "stimulus", 0.30, 0.20, n=198),
    71	        _make_block("rikyu", "stimulus", 0.40, 0.30, n=198),
    72	        _make_block("kant", "natural", 0.50, 0.40, n=30),
    73	        _make_block("nietzsche", "natural", 0.60, 0.50, n=30),
    74	        _make_block("rikyu", "natural", 0.70, 0.60, n=30),
    75	    ]
    76	    summary = p3a_decide._mean_widths_by_condition(blocks)
    77	    stim = summary["stimulus"]
    78	    nat = summary["natural"]
    79	    assert stim["burrows_delta_per_utterance"]["mean_width"] == pytest.approx(0.30)
    80	    assert stim["mattr_per_utterance"]["mean_width"] == pytest.approx(0.20)
    81	    assert stim["mean_combined_width"]["value"] == pytest.approx(0.25)
    82	    assert nat["burrows_delta_per_utterance"]["mean_width"] == pytest.approx(0.60)
    83	    assert nat["mattr_per_utterance"]["mean_width"] == pytest.approx(0.50)
    84	    assert nat["mean_combined_width"]["value"] == pytest.approx(0.55)
    85	
    86	
    87	def test_mean_widths_skips_missing_metrics(p3a_decide):
    88	    blocks = [
    89	        _make_block("kant", "stimulus", None, None),
    90	        _make_block("kant", "natural", 0.5, 0.5),
    91	    ]
    92	    summary = p3a_decide._mean_widths_by_condition(blocks)
    93	    assert "skipped" in summary["stimulus"]["burrows_delta_per_utterance"]
    94	    assert "skipped" in summary["stimulus"]["mattr_per_utterance"]
    95	    assert "skipped" in summary["stimulus"]["mean_combined_width"]
    96	    assert summary["natural"]["mean_combined_width"]["value"] == pytest.approx(0.5)
    97	
    98	
    99	def test_ratio_summary_within_tolerance_maintains_default(p3a_decide):
   100	    by_condition = {
   101	        "stimulus": {"mean_combined_width": {"value": 0.25, "n_metrics": 2}},
   102	        "natural": {"mean_combined_width": {"value": 0.26, "n_metrics": 2}},
   103	    }
   104	    out = p3a_decide._ratio_summary(by_condition)
   105	    assert out["verdict"].startswith("within_tolerance")
   106	    assert out["abs_diff_from_unity_pct"] < 10.0
   107	    assert out["deferred_metrics"] == ["vendi_score", "big5_icc"]
   108	
   109	
   110	def test_ratio_summary_natural_wider_flags_alternative(p3a_decide):
   111	    by_condition = {
   112	        "stimulus": {"mean_combined_width": {"value": 0.20, "n_metrics": 2}},
   113	        "natural": {"mean_combined_width": {"value": 0.40, "n_metrics": 2}},
   114	    }
   115	    out = p3a_decide._ratio_summary(by_condition)
   116	    assert out["verdict"].startswith("natural_wider")
   117	    assert out["width_ratio_natural_over_stimulus"] == pytest.approx(2.0)
   118	    assert any("Pilot N is asymmetric" in c for c in out["caveats"])
   119	
   120	
   121	def test_ratio_summary_stimulus_wider_flags_alternative(p3a_decide):
   122	    by_condition = {
   123	        "stimulus": {"mean_combined_width": {"value": 0.40, "n_metrics": 2}},
   124	        "natural": {"mean_combined_width": {"value": 0.20, "n_metrics": 2}},
   125	    }
   126	    out = p3a_decide._ratio_summary(by_condition)
   127	    assert out["verdict"].startswith("stimulus_wider")
   128	    assert out["width_ratio_natural_over_stimulus"] == pytest.approx(0.5)
   129	
   130	
   131	def test_ratio_summary_skipped_when_missing_value(p3a_decide):
   132	    by_condition = {
   133	        "stimulus": {"mean_combined_width": {"value": 0.25, "n_metrics": 2}},
   134	        "natural": {"mean_combined_width": {"skipped": "no widths"}},
   135	    }
   136	    out = p3a_decide._ratio_summary(by_condition)
   137	    assert "skipped" in out
   138	    assert out["deferred_metrics"] == ["vendi_score", "big5_icc"]
   139	
   140	
   141	def test_pilot_path_uses_persona_and_condition(p3a_decide):
   142	    path = p3a_decide._pilot_path("kant", "natural")
   143	    assert path.name == "kant_natural_run0.duckdb"
   144	    path = p3a_decide._pilot_path("rikyu", "stimulus")
   145	    assert path.name == "rikyu_stimulus_run0.duckdb"

 succeeded in 0ms:
     1	"""Compute Tier A metrics + bootstrap CI on the P3a pilot cells (both conditions).
     2	
     3	m9-eval-system P3a-decide finalization session: the natural-side gating bug
     4	was fixed via ``InMemoryDialogScheduler.eval_natural_mode`` (ME-8) and the
     5	COOLDOWN_TICKS_EVAL re-cooldown amendment, and G-GEAR re-captured 6 cells
     6	(stimulus + natural × 3 personas). This script reads both conditions and
     7	emits CI widths so the ME-4 ratio ADR can be edited with empirical data.
     8	
     9	The script:
    10	
    11	1. Discovers ``data/eval/pilot/<persona>_<condition>_run<idx>.duckdb`` for
    12	   ``condition in ("stimulus", "natural")`` and 3 personas (6 cells total).
    13	2. Reads each file read-only (DB6: never write) and pulls the
    14	   ``utterance`` column for the focal speaker rows
    15	   (``speaker_persona_id == persona``).
    16	3. Computes the lightweight Tier A metrics per (persona, condition):
    17	   Burrows Delta per-utterance against the persona's own reference, MATTR
    18	   over the concatenated utterance stream. The heavy ML metrics
    19	   (NLI / novelty / Empath) require ``[eval]`` extras; if the imports fail
    20	   the script logs a clear "skipped — install eval extras" line per metric
    21	   and continues with the lightweight set.
    22	4. Bootstraps a 95% CI per (persona, condition, metric) via
    23	   :mod:`erre_sandbox.evidence.bootstrap_ci`.
    24	5. Aggregates mean CI width per condition across personas (Burrows + MATTR)
    25	   and emits a ``ratio_summary`` block. **The script does not finalize the
    26	   ME-4 ratio decision** — it surfaces empirical widths so the ADR Edit can
    27	   weigh them. The naïve ``natural / stimulus`` width ratio is included with
    28	   an explicit ``caveats`` field about N asymmetry (stimulus ~198, natural
    29	   ~30 focal utterances by design).
    30	6. Writes ``data/eval/pilot/_p3a_decide.json`` with schema ``p3a_decide/v2``.
    31	
    32	Pre-condition: the operator must rsync the G-GEAR DuckDB files into
    33	``data/eval/pilot/`` first. The script exits non-zero with an explicit
    34	error if any expected file is missing — see ``_rsync_receipt.txt`` for
    35	the manual rsync protocol (ME-2).
    36	
    37	Vendi Score and Big5 ICC (the other two metrics ME-4's verdict references)
    38	are P4 territory; this script lists them under ``deferred_metrics`` rather
    39	than computing them, so the ME-4 Edit must remain a partial-update until P4.
    40	
    41	Usage::
    42	
    43	    uv run python scripts/p3a_decide.py
    44	    # → writes data/eval/pilot/_p3a_decide.json
    45	"""
    46	
    47	from __future__ import annotations
    48	
    49	import json
    50	import math
    51	import sys
    52	from pathlib import Path
    53	from typing import TYPE_CHECKING, Any, Final
    54	
    55	if TYPE_CHECKING:
    56	    from collections.abc import Callable
    57	
    58	import duckdb
    59	
    60	from erre_sandbox.evidence.bootstrap_ci import bootstrap_ci
    61	from erre_sandbox.evidence.tier_a import (
    62	    BurrowsLanguageMismatchError,
    63	    compute_burrows_delta,
    64	    compute_mattr,
    65	)
    66	
    67	_PILOT_DIR: Final[Path] = Path("data/eval/pilot")
    68	_OUT_PATH: Final[Path] = _PILOT_DIR / "_p3a_decide.json"
    69	_PERSONAS: Final[tuple[str, ...]] = ("kant", "nietzsche", "rikyu")
    70	_CONDITIONS: Final[tuple[str, ...]] = ("stimulus", "natural")
    71	_RUN_IDX: Final[int] = 0
    72	_DEFERRED_METRICS: Final[tuple[str, ...]] = ("vendi_score", "big5_icc")
    73	_RATIO_TOLERANCE_PCT: Final[float] = 10.0
    74	
    75	_PERSONA_LANGUAGE: Final[dict[str, str]] = {
    76	    "kant": "de",
    77	    "nietzsche": "de",
    78	    "rikyu": "ja",
    79	}
    80	
    81	
    82	def _pilot_path(persona: str, condition: str) -> Path:
    83	    return _PILOT_DIR / f"{persona}_{condition}_run{_RUN_IDX}.duckdb"
    84	
    85	
    86	def _open_pilot(persona: str, condition: str) -> duckdb.DuckDBPyConnection:
    87	    path = _pilot_path(persona, condition)
    88	    if not path.is_file():
    89	        msg = (
    90	            f"missing pilot file: {path} — rsync from G-GEAR first "
    91	            f"(see {_PILOT_DIR}/_rsync_receipt.txt)"
    92	        )
    93	        raise FileNotFoundError(msg)
    94	    return duckdb.connect(str(path), read_only=True)
    95	
    96	
    97	def _focal_utterances(con: duckdb.DuckDBPyConnection, persona: str) -> list[str]:
    98	    rows = con.execute(
    99	        "SELECT utterance FROM raw_dialog.dialog "
   100	        "WHERE speaker_persona_id = ? AND utterance IS NOT NULL "
   101	        "ORDER BY tick, dialog_id, turn_index",
   102	        [persona],
   103	    ).fetchall()
   104	    return [str(r[0]) for r in rows if r[0]]
   105	
   106	
   107	def _per_utterance_burrows(persona: str, utterances: list[str]) -> list[float | None]:
   108	    """Compute Burrows Delta for each utterance against the persona reference.
   109	
   110	    Returns a list of floats; entries that raise BurrowsLanguageMismatchError
   111	    or are too short to score (NaN return) are mapped to ``None``.
   112	    """
   113	    from erre_sandbox.evidence.reference_corpus.loader import (  # noqa: PLC0415 — optional path
   114	        load_reference,
   115	    )
   116	
   117	    language = _PERSONA_LANGUAGE[persona]
   118	    try:
   119	        reference = load_reference(persona_id=persona, language=language)
   120	    except Exception as exc:  # noqa: BLE001 — broad on purpose: we degrade gracefully
   121	        print(  # noqa: T201
   122	            f"[skip] burrows reference unavailable for {persona}/{language}: {exc!r}",
   123	            file=sys.stderr,
   124	        )
   125	        return []
   126	    out: list[float | None] = []
   127	    for utt in utterances:
   128	        try:
   129	            value = compute_burrows_delta(utt, reference, language=language)
   130	        except BurrowsLanguageMismatchError:
   131	            out.append(None)
   132	            continue
   133	        if math.isnan(value):
   134	            out.append(None)
   135	        else:
   136	            out.append(float(value))
   137	    return out
   138	
   139	
   140	def _try_optional_metric(
   141	    name: str,
   142	    fn: Callable[[], dict[str, Any]],
   143	) -> dict[str, Any] | None:
   144	    """Call ``fn()`` and surface a clean skip line on any ImportError."""
   145	    try:
   146	        return fn()
   147	    except ImportError as exc:
   148	        print(  # noqa: T201
   149	            f"[skip] tier_a {name}: {exc.name} not installed "
   150	            f"(install with `uv sync --extra eval`)",
   151	            file=sys.stderr,
   152	        )
   153	        return None
   154	
   155	
   156	def _persona_block(persona: str, condition: str) -> dict[str, Any]:
   157	    con = _open_pilot(persona, condition)
   158	    try:
   159	        utterances = _focal_utterances(con, persona)
   160	    finally:
   161	        con.close()
   162	
   163	    block: dict[str, Any] = {
   164	        "persona_id": persona,
   165	        "condition": condition,
   166	        "n_utterances": len(utterances),
   167	        "metrics": {},
   168	    }
   169	
   170	    if not utterances:
   171	        block["note"] = "no focal utterances after rsync — pilot DB empty?"
   172	        return block
   173	
   174	    # Burrows Delta — per-utterance values, bootstrap on the per-utterance vector.
   175	    burrows_values = _per_utterance_burrows(persona, utterances)
   176	    finite = [v for v in burrows_values if v is not None]
   177	    if finite:
   178	        result = bootstrap_ci(burrows_values, n_resamples=2000, seed=0)
   179	        block["metrics"]["burrows_delta_per_utterance"] = {
   180	            "point": result.point,
   181	            "lo": result.lo,
   182	            "hi": result.hi,
   183	            "width": result.width,
   184	            "n": result.n,
   185	            "n_resamples": result.n_resamples,
   186	            "method": result.method,
   187	        }
   188	    else:
   189	        block["metrics"]["burrows_delta_per_utterance"] = {
   190	            "skipped": "no finite burrows values — reference corpus or language gap",
   191	        }
   192	
   193	    # MATTR — single value over the concatenated utterance stream. CI via
   194	    # bootstrap on per-utterance MATTR (so we have a distribution to resample).
   195	    per_utterance_mattr: list[float | None] = []
   196	    for utt in utterances:
   197	        value = compute_mattr(utt)
   198	        per_utterance_mattr.append(None if value is None else float(value))
   199	    finite_mattr = [v for v in per_utterance_mattr if v is not None]
   200	    if finite_mattr:
   201	        result = bootstrap_ci(per_utterance_mattr, n_resamples=2000, seed=0)
   202	        block["metrics"]["mattr_per_utterance"] = {
   203	            "point": result.point,
   204	            "lo": result.lo,
   205	            "hi": result.hi,
   206	            "width": result.width,
   207	            "n": result.n,
   208	            "n_resamples": result.n_resamples,
   209	            "method": result.method,
   210	        }
   211	    else:
   212	        block["metrics"]["mattr_per_utterance"] = {"skipped": "no MATTR values"}
   213	
   214	    # NLI / novelty / Empath — heavy ML metrics. We attempt the import and
   215	    # skip gracefully if [eval] extras are absent (Mac default is no extras).
   216	    nli_block = _try_optional_metric(
   217	        "nli_contradiction",
   218	        lambda: _nli_block(utterances),
   219	    )
   220	    if nli_block is not None:
   221	        block["metrics"]["nli_contradiction"] = nli_block
   222	
   223	    novelty_block = _try_optional_metric(
   224	        "semantic_novelty",
   225	        lambda: _novelty_block(utterances),
   226	    )
   227	    if novelty_block is not None:
   228	        block["metrics"]["semantic_novelty"] = novelty_block
   229	
   230	    empath_block = _try_optional_metric(
   231	        "empath_proxy",
   232	        lambda: _empath_block(utterances),
   233	    )
   234	    if empath_block is not None:
   235	        block["metrics"]["empath_proxy"] = empath_block
   236	
   237	    return block
   238	
   239	
   240	def _nli_block(utterances: list[str]) -> dict[str, Any]:
   241	    from erre_sandbox.evidence.tier_a import (  # noqa: PLC0415 — optional dep
   242	        compute_nli_contradiction,
   243	    )
   244	
   245	    pairs = [(utterances[i], utterances[i + 1]) for i in range(len(utterances) - 1)]
   246	    if not pairs:
   247	        return {"skipped": "fewer than 2 utterances"}
   248	    point = compute_nli_contradiction(pairs)
   249	    if point is None:
   250	        return {"skipped": "NLI scorer returned no result"}
   251	    # Per-pair scores are not exposed by the public API; for a CI we treat
   252	    # the mean as a single point estimate and flag the "no per-sample CI"
   253	    # status. P5 will refactor to return per-pair vectors for proper CI.
   254	    return {
   255	        "point": float(point),
   256	        "ci_status": (
   257	            "point_estimate_only — per-pair vector not exposed by tier_a.nli yet"
   258	        ),
   259	    }
   260	

exec
/bin/zsh -lc "nl -ba scripts/p3a_decide.py | sed -n '261,520p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   261	
   262	def _novelty_block(utterances: list[str]) -> dict[str, Any]:
   263	    from erre_sandbox.evidence.tier_a import (  # noqa: PLC0415 — optional dep
   264	        compute_semantic_novelty,
   265	    )
   266	
   267	    point = compute_semantic_novelty(utterances)
   268	    if point is None:
   269	        return {"skipped": "fewer than 2 utterances"}
   270	    return {
   271	        "point": float(point),
   272	        "ci_status": (
   273	            "point_estimate_only — per-step vector not exposed by tier_a.novelty yet"
   274	        ),
   275	    }
   276	
   277	
   278	def _empath_block(utterances: list[str]) -> dict[str, Any]:
   279	    from erre_sandbox.evidence.tier_a import (  # noqa: PLC0415 — optional dep
   280	        compute_empath_proxy,
   281	    )
   282	
   283	    scores = compute_empath_proxy(utterances)
   284	    if not scores:
   285	        return {"skipped": "empath returned empty dict"}
   286	    # Surface a coarse summary (top-5 categories by score). CI on individual
   287	    # categories is P4-territory because the IPIP-NEO loop produces the
   288	    # primary persona-style signal; here we just expose the vector.
   289	    top = sorted(scores.items(), key=lambda kv: -kv[1])[:5]
   290	    return {
   291	        "top_categories": [{"name": k, "score": float(v)} for k, v in top],
   292	        "ci_status": "vector_only — bootstrap CI deferred to P4 IPIP-NEO loop",
   293	    }
   294	
   295	
   296	def _mean_widths_by_condition(
   297	    blocks: list[dict[str, Any]],
   298	) -> dict[str, dict[str, Any]]:
   299	    """Aggregate per-cell widths into mean widths per condition.
   300	
   301	    Only the lightweight Tier A metrics (Burrows Delta + MATTR) are
   302	    aggregated here — Vendi Score and Big5 ICC are P4 deliverables and are
   303	    listed under ``deferred_metrics`` in the payload.
   304	    """
   305	    metric_keys = ("burrows_delta_per_utterance", "mattr_per_utterance")
   306	    summary: dict[str, dict[str, Any]] = {}
   307	    for condition in _CONDITIONS:
   308	        per_metric: dict[str, dict[str, Any]] = {}
   309	        for metric in metric_keys:
   310	            widths: list[float] = []
   311	            ns: list[int] = []
   312	            for block in blocks:
   313	                if block.get("condition") != condition:
   314	                    continue
   315	                metrics = block.get("metrics", {})
   316	                entry = metrics.get(metric)
   317	                if not isinstance(entry, dict) or "width" not in entry:
   318	                    continue
   319	                widths.append(float(entry["width"]))
   320	                ns.append(int(entry.get("n", 0)))
   321	            if widths:
   322	                per_metric[metric] = {
   323	                    "mean_width": sum(widths) / len(widths),
   324	                    "n_cells": len(widths),
   325	                    "per_cell_widths": widths,
   326	                    "per_cell_n": ns,
   327	                }
   328	            else:
   329	                per_metric[metric] = {"skipped": "no finite widths in this condition"}
   330	        finite = [
   331	            entry["mean_width"]
   332	            for entry in per_metric.values()
   333	            if "mean_width" in entry
   334	        ]
   335	        per_metric["mean_combined_width"] = (
   336	            {"value": sum(finite) / len(finite), "n_metrics": len(finite)}
   337	            if finite
   338	            else {"skipped": "no finite metric widths"}
   339	        )
   340	        summary[condition] = per_metric
   341	    return summary
   342	
   343	
   344	def _ratio_summary(
   345	    by_condition: dict[str, dict[str, Any]],
   346	) -> dict[str, Any]:
   347	    """Compute the naïve natural/stimulus mean width ratio with caveats.
   348	
   349	    The pilot N is asymmetric by design (stimulus ~198 focal, natural ~30
   350	    focal). CI width scales with 1/sqrt(n), so a direct width ratio is
   351	    confounded with sample-size effects — callers (i.e. the ME-4 ADR Edit)
   352	    must interpret this number with that caveat in mind, not finalize the
   353	    ratio decision on naïve width alone.
   354	    """
   355	    stim = by_condition.get("stimulus", {}).get("mean_combined_width", {})
   356	    nat = by_condition.get("natural", {}).get("mean_combined_width", {})
   357	    if "value" not in stim or "value" not in nat:
   358	        return {
   359	            "skipped": "one or both conditions missing mean_combined_width",
   360	            "deferred_metrics": list(_DEFERRED_METRICS),
   361	            "verdict_threshold_pct": _RATIO_TOLERANCE_PCT,
   362	        }
   363	    stim_w = float(stim["value"])
   364	    nat_w = float(nat["value"])
   365	    ratio = nat_w / stim_w if stim_w > 0 else float("inf")
   366	    diff_pct = abs(ratio - 1.0) * 100.0
   367	    if diff_pct < _RATIO_TOLERANCE_PCT:
   368	        verdict = "within_tolerance_default_200_300_maintainable"
   369	    elif ratio > 1.0:
   370	        verdict = "natural_wider_alternative_recommended_subject_to_n_caveat"
   371	    else:
   372	        verdict = "stimulus_wider_alternative_recommended_subject_to_n_caveat"
   373	    return {
   374	        "stimulus_mean_combined_width": stim_w,
   375	        "natural_mean_combined_width": nat_w,
   376	        "width_ratio_natural_over_stimulus": ratio,
   377	        "abs_diff_from_unity_pct": diff_pct,
   378	        "verdict_threshold_pct": _RATIO_TOLERANCE_PCT,
   379	        "verdict": verdict,
   380	        "deferred_metrics": list(_DEFERRED_METRICS),
   381	        "caveats": [
   382	            (
   383	                "Pilot N is asymmetric by design (stimulus ~198 focal, natural "
   384	                "~30 focal). CI width scales with 1/sqrt(n); a direct width "
   385	                "ratio is confounded with sample-size effects."
   386	            ),
   387	            (
   388	                "Vendi Score and Big5 ICC are deferred to P4. ME-4 cannot be "
   389	                "fully closed until P4 supplies those CI widths."
   390	            ),
   391	            (
   392	                "NLI / novelty / Empath are point estimates only in this "
   393	                "lightweight script; per-pair / per-step CI is P5 work."
   394	            ),
   395	        ],
   396	    }
   397	
   398	
   399	def main() -> int:
   400	    if not _PILOT_DIR.is_dir():
   401	        print(f"pilot directory not found: {_PILOT_DIR}", file=sys.stderr)  # noqa: T201
   402	        return 1
   403	    missing: list[str] = []
   404	    for persona in _PERSONAS:
   405	        for condition in _CONDITIONS:
   406	            candidate = _pilot_path(persona, condition)
   407	            if not candidate.is_file():
   408	                missing.append(str(candidate))
   409	    if missing:
   410	        print(  # noqa: T201
   411	            "missing pilot DuckDB files — rsync from G-GEAR first:",
   412	            file=sys.stderr,
   413	        )
   414	        for missing_path in missing:
   415	            print(f"  {missing_path}", file=sys.stderr)  # noqa: T201
   416	        print(  # noqa: T201
   417	            f"\nsee {_PILOT_DIR}/_rsync_receipt.txt for the ME-2 protocol",
   418	            file=sys.stderr,
   419	        )
   420	        return 2
   421	
   422	    blocks: list[dict[str, Any]] = []
   423	    for persona in _PERSONAS:
   424	        for condition in _CONDITIONS:
   425	            try:
   426	                blocks.append(_persona_block(persona, condition))
   427	            except Exception as exc:  # noqa: BLE001
   428	                blocks.append(
   429	                    {
   430	                        "persona_id": persona,
   431	                        "condition": condition,
   432	                        "error": f"{type(exc).__name__}: {exc!s}",
   433	                    }
   434	                )
   435	
   436	    by_condition = _mean_widths_by_condition(blocks)
   437	    ratio_summary = _ratio_summary(by_condition)
   438	
   439	    payload: dict[str, Any] = {
   440	        "schema": "p3a_decide/v2",
   441	        "scope": "stimulus_and_natural",
   442	        "note": (
   443	            "Both conditions present: natural side re-captured after the M5/M6 "
   444	            "zone-drift bug fix (eval_natural_mode flag, ME-8 ADR) and the "
   445	            "COOLDOWN_TICKS_EVAL=5 + wall default 120 amendment. CI widths are "
   446	            "surfaced per (persona, condition); the ME-4 ADR Edit is the "
   447	            "authority for the final ratio decision."
   448	        ),
   449	        "cells": blocks,
   450	        "by_condition": by_condition,
   451	        "ratio_summary": ratio_summary,
   452	    }
   453	    _OUT_PATH.write_text(
   454	        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
   455	        encoding="utf-8",
   456	    )
   457	    print(  # noqa: T201
   458	        f"wrote {_OUT_PATH} ({len(blocks)} cells; "
   459	        f"{len(_PERSONAS)} personas × {len(_CONDITIONS)} conditions)"
   460	    )
   461	    return 0
   462	
   463	
   464	if __name__ == "__main__":
   465	    sys.exit(main())

exec
/bin/zsh -lc "nl -ba .steering/20260430-m9-eval-system/tasklist.md | sed -n '308,380p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba .steering/20260430-m9-eval-system/decisions.md | sed -n '124,176p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   308	- [ ] [Mac] **P3a-decide** — bootstrap CI width 比較で ratio 確定 (本来 1h、実際は
   309	      gating bug fix 込みで 4-6h、natural 再採取後に二度目の Mac セッションで
   310	      最終 close):
   311	  - [x] **2026-05-01 Mac セッション (本セッション)**:
   312	    - [x] M5/M6 natural runtime gating bug の root-cause analysis 完了:
   313	          `personas/{nietzsche,rikyu}.yaml` preferred_zones に AGORA 不在 +
   314	          `ERRE_ZONE_BIAS_P=0.2` default で 53% per-tick zone drift →
   315	          `_iter_colocated_pairs` 0 pair → admit 停止
   316	    - [x] `.steering/20260430-m9-eval-system/design-natural-gating-fix.md` 起草
   317	          (Plan + /reimagine 4 案比較 + 採用判断)
   318	    - [x] 修正実装: `InMemoryDialogScheduler.eval_natural_mode: bool = False` flag、
   319	          `_iter_all_distinct_pairs` ヘルパ追加、両 flag 同時 True を reject
   320	    - [x] `cli/eval_run_golden.py:capture_natural` で `eval_natural_mode=True` opt-in
   321	    - [x] `tests/test_integration/test_dialog_eval_natural_mode.py` 12 件
   322	          (Red→Green 転換 + 5 invariant + 構築時 reject) 全 PASS
   323	    - [x] **Codex `gpt-5.5 xhigh` independent review** 完了
   324	          (`codex-review-prompt-natural-gating.md` → `codex-review-natural-gating.md`、
   325	          76,961 tokens、Verdict: **ship**、HIGH=0 MEDIUM=0 LOW=2 全反映)
   326	    - [x] 既存 1221 PASS 維持 (full suite **1248 passed** = 1221 + 12 new + 15
   327	          bootstrap_ci tests)
   328	    - [x] `src/erre_sandbox/evidence/bootstrap_ci.py` drafted (P5 prep を前倒し):
   329	          `bootstrap_ci()` percentile + `hierarchical_bootstrap_ci()` cluster+block
   330	          (Codex HIGH-2 の AR(1) 想定、N(0,1) 解析解 ± 5% / AR(1) 合成データで
   331	          iid vs block CI width 差を assert)
   332	    - [x] `tests/test_evidence/test_bootstrap_ci.py` 15 件全 PASS
   333	    - [x] `scripts/p3a_decide.py` drafted: stimulus 3 cell の Burrows Delta + MATTR
   334	          + (eval extras 任意で) NLI / novelty / Empath を CI 計算、
   335	          `data/eval/pilot/_p3a_decide.json` 出力。**rsync 待ち**で missing files
   336	          を検出した場合 exit 2 + ME-2 protocol 案内
   337	    - [x] `decisions.md` ME-4 ADR partial update + 新規 ME-8 ADR 追加
   338	    - [x] `g-gear-p3a-rerun-prompt.md` 起草 (次 G-GEAR セッション用、re-capture
   339	          手順 + 期待値 + DB rsync protocol)
   340	  - [x] **2026-05-01 Mac セッション v2 (本 P3a-decide v2 セッション)**:
   341	    - [x] G-GEAR Phase A 失敗レポート (`g-gear-phase-a-failure.md`、PR #131) を Read、
   342	          empirical cognition_period ≈ 120 s/tick を確定
   343	    - [x] design v1 §2 で △ 補助棄却した仮説 B (cooldown × cognition_period の wall
   344	          換算) を ◎ 主因に再格上げ確定
   345	    - [x] `design-natural-gating-fix-v2.md` 起草 (G-GEAR 5 案 + Mac /reimagine 3 案 =
   346	          8 案比較、α+β ハイブリッド採用、ζ/θ/ι 棄却理由明記)
   347	    - [x] Codex `gpt-5.5 xhigh` independent review v2 完了
   348	          (`codex-review-prompt-natural-gating-v2.md` → `codex-review-natural-gating-v2.md`
   349	          145,717 tokens、Verdict: revise)
   350	    - [x] HIGH-1 (wall default 不整合) / HIGH-2 (既存 cooldown test rewrite) /
   351	          MEDIUM-1 (ME-8 explicit amendment) / MEDIUM-2 (conservative estimate
   352	          primary 化) / Q5 (sentinel test 削除) / Q6 (eval cadence calibration
   353	          命名) すべて反映
   354	    - [x] 修正実装: `InMemoryDialogScheduler.COOLDOWN_TICKS_EVAL: ClassVar[int] = 5` +
   355	          `_effective_cooldown()` helper、`schedule_initiate` / `tick()` の cooldown
   356	          check 経由化。`_DEFAULT_WALL_TIMEOUT_MIN`: 90.0 → 120.0
   357	    - [x] test rewrite 2 件 (`test_eval_natural_mode_uses_reduced_cooldown` /
   358	          `test_eval_natural_mode_sustains_admission_after_initial_burst`) +
   359	          新規 4 件 (`test_effective_cooldown_returns_eval_value_when_flag_true` /
   360	          `test_effective_cooldown_returns_live_value_when_flag_false` /
   361	          `test_live_mode_cooldown_unchanged_via_tick` / 
   362	          `test_wall_timeout_min_default_is_120`) 全 PASS
   363	    - [x] full suite **1251 passed** / 31 skipped / 27 deselected (baseline 1248 から
   364	          default CI に +3、CLI test 1 件は eval marker で deselect)
   365	    - [x] `decisions.md` ME-8 amendment 2026-05-01 ブロック追加 (二度目の partial
   366	          update、explicit amendment with PR #131 empirical data)
   367	    - [x] `g-gear-p3a-rerun-prompt-v2.md` 起草 (Phase A 期待値桁再校正、wall 120 min)
   368	    - [x] `.codex/budget.json` 145,717 tokens 記録 (per_invocation_max=200K 内)
   369	  - [ ] **next G-GEAR セッション v2** (rerun-prompt-v2.md を貼り付けて起動):
   370	    - [ ] fix v2 適用版 (`COOLDOWN_TICKS_EVAL=5` + wall default 120) で natural
   371	          3 cell 再々採取 (focal>=25 target、Phase A 単独 sanity → Phase B 3 並列)
   372	    - [ ] DuckDB rsync via `/tmp/p3a_rsync_v2/` snapshot + ME-2 protocol
   373	  - [ ] **next Mac セッション** (rsync 完了後):
   374	    - [ ] `uv run python scripts/p3a_decide.py` で両 condition の CI 計算
   375	    - [ ] Burrows Delta / Vendi / Big5 ICC の CI width 比較
   376	    - [ ] ME-4 ADR を **二度目の Edit** で実測値 ratio 確定 (200/300 default vs
   377	          alternative)
   378	    - [ ] M9-B `blockers.md` の "Hybrid baseline 比率 200/300" 項目を close
   379	          (現状 M9-B blockers.md には該当項目なし。本セッションでは追加せず、
   380	          ratio 確定時に M9-B 側へ通知 / 必要なら起票)

 succeeded in 0ms:
   124	## ME-4 — Hybrid baseline ratio: P3a 完了後に確定 (Codex HIGH-3 系の defer ADR)
   125	
   126	- **決定 (元案)**: 200 (stimulus battery) / 300 (自然対話) を **default** とし、P3a で
   127	  両 condition × 3 persona の isolated pilot を採取し、bootstrap CI width で
   128	  ratio を確定する。
   129	- **2026-05-01 partial update (P3a-decide Mac セッション、Task 1+2 完了)**:
   130	  - **stimulus 3 cell**: G-GEAR 採取 focal=198 / total=342 / dialogs=168 で 3 persona
   131	    すべて完走済 (data/eval/pilot/_summary.json)。
   132	  - **natural 3 cell**: G-GEAR 採取は M5/M6 zone-drift bug で **partial**
   133	    (kant=6 focal / nietzsche=0 focal / rikyu=6 focal、~13 min wall で kill)。
   134	    本セッションで `InMemoryDialogScheduler.eval_natural_mode=True` を導入して bug
   135	    を解決 (PR `feature/m9-eval-p3a-decide`、ME-8 ADR 参照)。修正後の natural cell は
   136	    G-GEAR 再採取が必要 (本 Mac セッションでは LLM 不在で実機検証不可)。
   137	  - **bootstrap CI 計算**: `src/erre_sandbox/evidence/bootstrap_ci.py` を P5 prep として
   138	    drafted (本来 P5 phase 着手分の前倒し)、`scripts/p3a_decide.py` で stimulus side の
   139	    Burrows Delta + MATTR (lightweight) の CI を計算する経路を整備 (G-GEAR DuckDB の
   140	    rsync 待ち)。NLI / novelty / Empath は `[eval]` extras 必須なので Mac default では
   141	    skip + clear log line で degrade。
   142	  - **判定**: stimulus side のみで ratio を確定するのは統計的に invalid
   143	    (元 ADR の "両 condition で測定" 要件未充足)。**ratio 200/300 default は留保**、
   144	    natural 再採取後に再判定。
   145	- **判定基準 (元案維持)**:
   146	  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
   147	  - 両条件で sub-metric の **mean CI width が小さい比率** を採用
   148	  - 両者が同等 (差 <10%) なら 200/300 default を維持
   149	- **根拠**:
   150	  - Codex HIGH-3: 元案の「P3 採取後 P3b で 50 turn pilot」は順序 invert + 統計力不足
   151	  - 200 turn は Vendi の 200-turn window を 1 cycle 満たす最小値
   152	  - bootstrap CI width が直接的な測定対象 (DB9 quorum の信頼性)
   153	- **棄却**:
   154	  - 200/300 を data なしで freeze → arbitrary (元案のまま)
   155	  - **stimulus 側 CI のみで ratio 確定**: natural side との **比較**が ratio 決定の
   156	    本質 (元 ADR §判定基準 1) で、片側 CI のみでは比較できない → 棄却
   157	- **影響**:
   158	  - P3a-decide セッションで **partial 完了**: gating bug fix + bootstrap_ci module +
   159	    p3a_decide script は ready、natural 再採取後に最終 ratio 確定
   160	  - ratio 確定までは P3 (golden baseline 採取) 入り保留 — 本来 24h × overnight×2 の
   161	    G-GEAR 採取を、ratio 不確定で着手すると invalidation リスク
   162	- **re-open 条件**:
   163	  - **本 ADR は再採取後に二度目の Edit を要する** (current state = partial):
   164	    1. G-GEAR 再採取で natural side が完走 (focal 30 / total 90 / dialogs ~15)
   165	    2. Mac で `scripts/p3a_decide.py` を両 condition の duckdb に対し run
   166	    3. ratio default 200/300 vs alternative の bootstrap CI width 比較
   167	    4. 確定値で本 ADR を **再 Edit**
   168	  - golden baseline 採取後に DB9 quorum の sub-metric が persona discriminative でない
   169	    と判明 → ratio 再調整 + 再採取検討 (元案維持)
   170	- **partial-close 状態の文脈**:
   171	  - 本 ADR は **2 段階 close**: (1) bug fix + script ready (本セッション)、
   172	    (2) 再採取データで実測値 ratio (次 G-GEAR セッション + 次 Mac セッション)
   173	  - tasklist.md §P3a-decide はチェック項目を分割: "scheduler fix [x]" / "bootstrap CI
   174	    modules ready [x]" / "stimulus-side CI computed (rsync 待ち) [pending]" /
   175	    "ratio ADR 確定 (natural 再採取待ち) [pending]"
   176	

exec
/bin/zsh -lc "sed -n '1,220p' data/eval/pilot/_rsync_receipt.txt" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,220p' data/eval/pilot/_summary.json" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
{
  "cell_count": 6,
  "cells": [
    {
      "condition": "natural",
      "dialog_count": 15,
      "file": "kant_natural_run0.duckdb",
      "focal_rows": 30,
      "persona_id": "kant",
      "run_id": "kant_natural_run0",
      "run_idx": 0,
      "speaker_persona_breakdown": {
        "kant": 30,
        "nietzsche": 30,
        "rikyu": 30
      },
      "total_rows": 90,
      "utterance_chars_max": 161,
      "utterance_chars_mean": 53.24,
      "utterance_chars_median": 52.0
    },
    {
      "condition": "stimulus",
      "dialog_count": 168,
      "file": "kant_stimulus_run0.duckdb",
      "focal_rows": 198,
      "persona_id": "kant",
      "run_id": "kant_stimulus_run0",
      "run_idx": 0,
      "speaker_persona_breakdown": {
        "interlocutor": 144,
        "kant": 198
      },
      "total_rows": 342,
      "utterance_chars_max": 199,
      "utterance_chars_mean": 68.54,
      "utterance_chars_median": 68.0
    },
    {
      "condition": "natural",
      "dialog_count": 15,
      "file": "nietzsche_natural_run0.duckdb",
      "focal_rows": 30,
      "persona_id": "nietzsche",
      "run_id": "nietzsche_natural_run0",
      "run_idx": 0,
      "speaker_persona_breakdown": {
        "kant": 30,
        "nietzsche": 30,
        "rikyu": 30
      },
      "total_rows": 90,
      "utterance_chars_max": 161,
      "utterance_chars_mean": 47.2,
      "utterance_chars_median": 41.0
    },
    {
      "condition": "stimulus",
      "dialog_count": 168,
      "file": "nietzsche_stimulus_run0.duckdb",
      "focal_rows": 198,
      "persona_id": "nietzsche",
      "run_id": "nietzsche_stimulus_run0",
      "run_idx": 0,
      "speaker_persona_breakdown": {
        "interlocutor": 144,
        "nietzsche": 198
      },
      "total_rows": 342,
      "utterance_chars_max": 163,
      "utterance_chars_mean": 55.03,
      "utterance_chars_median": 45.5
    },
    {
      "condition": "natural",
      "dialog_count": 14,
      "file": "rikyu_natural_run0.duckdb",
      "focal_rows": 30,
      "persona_id": "rikyu",
      "run_id": "rikyu_natural_run0",
      "run_idx": 0,
      "speaker_persona_breakdown": {
        "kant": 27,
        "nietzsche": 27,
        "rikyu": 30
      },
      "total_rows": 84,
      "utterance_chars_max": 161,
      "utterance_chars_mean": 52.13,
      "utterance_chars_median": 40.0
    },
    {
      "condition": "stimulus",
      "dialog_count": 168,
      "file": "rikyu_stimulus_run0.duckdb",
      "focal_rows": 198,
      "persona_id": "rikyu",
      "run_id": "rikyu_stimulus_run0",
      "run_idx": 0,
      "speaker_persona_breakdown": {
        "interlocutor": 144,
        "rikyu": 198
      },
      "total_rows": 342,
      "utterance_chars_max": 597,
      "utterance_chars_mean": 33.46,
      "utterance_chars_median": 28.0
    }
  ],
  "pilot_dir": "data/eval/pilot",
  "schema": "p3a_summary/v1"
}

 succeeded in 0ms:
# P3a-decide v2 rerun rsync receipt

status: ready — natural re-capture after fix v2 completed; rsync to Mac pending (manual)
captured_at: 2026-05-02T00:50:11Z
mac_destination: ~/ERRE-Sand_Box/data/eval/pilot/

# Capture host
host_name: G-GEAR
os: Windows 11 Home
gpu: NVIDIA RTX 5060 Ti 16GB
ollama_version: 0.22.0
ollama_models: qwen3:8b (Q4_K_M, 5.2GB), nomic-embed-text:latest (274MB)

# Cell results (natural re-capture under fix v2; stimulus carried from PR #129)
# persona    condition  focal  total  dialogs
# kant       natural       30     90       15
# nietzsche  natural       30     90       15
# rikyu      natural       30     84       14
# kant       stimulus     198    342      168
# nietzsche  stimulus     198    342      168
# rikyu      stimulus     198    342      168
# All 3 natural cells passed Phase A guard (focal>=25 conservative lower bound).

# Fix v2 verification (post COOLDOWN_TICKS_EVAL=5 + wall default 120)
prior_phase_a_v1: kant=6/18/3 (cooldown gated, wall 10 min sanity timeout, PR #131)
phase_a_v2_sanity: kant=30/90/15 (single cell, wall=120 min budget, completed in ~16 min)
phase_b_v2_parallel: nietzsche=30/90/15 + rikyu=30/84/14 (3 cell parallel, wall 22 min)
  - kant Phase B parallel hit drain timeout (focal=30 reached internally, total=88,
    runtime drain exceeded 30.0s under Ollama queue contention) → re-ran kant alone
    sequentially (post-parallel, 16 min, focal=30/total=90 clean)
empirical_cognition_period: ~120 s/tick on qwen3:8b Q4_K_M / RTX 5060 Ti single cell
  (under 3-cell Ollama parallelism, per-tick latency stretched but total throughput
  improved due to concurrent batching)

# DuckDB snapshot checksums (md5; produced from /tmp/p3a_rsync_v2/)
# All 6 files are 524K; .duckdb format from duckdb v1.x via eval_run_golden CLI.
# These files are .gitignored — only this receipt + _summary.json are committed.
# Mac side restores by stripping .snapshot.duckdb suffix.
945d1e2301ecf2765c9dcce559a00a21  kant_natural_run0.duckdb.snapshot.duckdb
ba3c88d5a857cffdaf855473131aba3b  kant_stimulus_run0.duckdb.snapshot.duckdb
cb89df94a89a675aedfe0ec56d651fdb  nietzsche_natural_run0.duckdb.snapshot.duckdb
a512d5a99dab33ea769e6ff1e966bcfe  nietzsche_stimulus_run0.duckdb.snapshot.duckdb
6276767c9f5ca05f70fb4973adcc334b  rikyu_natural_run0.duckdb.snapshot.duckdb
1bf72395f43f20019d66673f2ded8666  rikyu_stimulus_run0.duckdb.snapshot.duckdb

# ME-2 manual rsync protocol (user runs out-of-band, MAC_HOST not in repo)
#
# G-GEAR side (snapshots already staged at /tmp/p3a_rsync_v2/):
#   ls -lh /tmp/p3a_rsync_v2/        # 6 files + _checksums.txt
#   rsync -av /tmp/p3a_rsync_v2/ <MAC_HOST>:~/ERRE-Sand_Box/data/eval/pilot/
#
# Mac side (P3a-decide finalization session):
#   for f in ~/ERRE-Sand_Box/data/eval/pilot/*.snapshot.duckdb; do
#     mv -- "$f" "${f%.snapshot.duckdb}"
#   done
#   md5sum ~/ERRE-Sand_Box/data/eval/pilot/*.duckdb
#   # compare against the checksums in this receipt
#   uv run python scripts/p3a_decide.py
#   # → data/eval/pilot/_p3a_decide.json + ME-4 ADR second Edit (ratio finalization)

codex
The ADR still frames the next Mac session as “二度目の Edit” that finalizes the ratio, while the script’s own docstring says ME-4 must remain partial until P4. I’m checking the dependency contracts and repo consumers now so the verdict can separate implementation bugs from ADR/process gaps.
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/bootstrap_ci.py | sed -n '1,260p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/tier_a/mattr.py | sed -n '1,260p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     1	"""Moving Average Type-Token Ratio (MATTR) — lexical diversity metric.
     2	
     3	MATTR (Covington & McFall 2010) sidesteps the well-known bias of plain
     4	TTR against text length by averaging the type-token ratio of every
     5	window of fixed size as the window slides across the token stream.
     6	The persona-discriminative claim in the M9 design is that thinkers
     7	with broader vocabularies (Nietzsche) sustain a higher MATTR than
     8	thinkers with a tight technical jargon set (Kant) at the same window
     9	size.
    10	
    11	Window size 100 is the literature default and matches what the
    12	Vendi-vs-MATTR Tier B comparison expects; if a future spike wants to
    13	tune it the parameter is exposed but pinned per-run for fairness.
    14	"""
    15	
    16	from __future__ import annotations
    17	
    18	DEFAULT_WINDOW: int = 100
    19	"""Default sliding window size in tokens.
    20	
    21	Covington & McFall (2010) recommend 100 tokens as the empirical sweet
    22	spot — small enough to retain locality, large enough to absorb the
    23	"first-token-of-a-window" novelty noise that drives plain TTR to 1.0
    24	on short snippets.
    25	"""
    26	
    27	
    28	def compute_mattr(
    29	    text: str,
    30	    *,
    31	    window: int = DEFAULT_WINDOW,
    32	) -> float | None:
    33	    """Mean type-token ratio over sliding windows of ``window`` tokens.
    34	
    35	    Args:
    36	        text: Whitespace-separated text. The same naive tokeniser as
    37	            :mod:`erre_sandbox.evidence.metrics` is used so the M8
    38	            baseline metric and the M9 Tier A metric line up at the
    39	            tokenisation layer (consistent inputs to a consistent
    40	            stylometric question).
    41	        window: Sliding window size in tokens. Must be ``>= 1``;
    42	            defaults to :data:`DEFAULT_WINDOW`.
    43	
    44	    Returns:
    45	        ``None`` when the text is empty (no measurement possible).
    46	        Otherwise the mean window TTR. When the text is shorter than
    47	        ``window`` the function falls back to plain TTR over all tokens
    48	        — the M8 ``compute_*`` contract treats short runs as
    49	        "best-effort, not NaN" so downstream bootstrap-CI sees a usable
    50	        number rather than a spurious gap.
    51	
    52	    Raises:
    53	        ValueError: If ``window < 1``.
    54	    """
    55	    if window < 1:
    56	        raise ValueError(f"window must be >= 1 (got {window})")
    57	    tokens = text.split()
    58	    if not tokens:
    59	        return None
    60	    n = len(tokens)
    61	    if n <= window:
    62	        return len(set(tokens)) / n
    63	
    64	    ratios: list[float] = []
    65	    for i in range(n - window + 1):
    66	        chunk = tokens[i : i + window]
    67	        ratios.append(len(set(chunk)) / window)
    68	    return sum(ratios) / len(ratios)

 succeeded in 0ms:
     1	"""Bootstrap confidence intervals for Tier A / Tier B metric aggregates.
     2	
     3	m9-eval-system P5 (Codex HIGH-2 in `codex-review.md`): hierarchical
     4	bootstrap with **outer cluster (run) + inner block (circular block of
     5	turn-level samples)** for autocorrelation-aware CI estimation. The DB9
     6	quorum semantics in `design-final.md` requires CI width per
     7	sub-metric to gate ratio confirmation.
     8	
     9	This module is drafted in P3a-decide (ahead of the formal P5 phase) so
    10	the stimulus-side ratio sanity-check can run on the pilot DuckDB files
    11	once they are rsync'd from G-GEAR. The full P5 features (block-length
    12	auto-estimation via autocorrelation, AR(1) sensitivity grid) will be
    13	layered on top in the dedicated P5 PR — the public API in this module
    14	is forward-compatible because callers consume CI tuples, not internal
    15	parameters.
    16	
    17	Quick reference:
    18	
    19	* :func:`bootstrap_ci` — minimum viable percentile bootstrap. Pure
    20	  numpy, deterministic under explicit ``seed``. Works for the P3a-decide
    21	  use-case (per-cell aggregate metrics, no within-cell autocorrelation
    22	  to model because each cell is one persona run).
    23	* :func:`hierarchical_bootstrap_ci` — outer cluster + inner block
    24	  resampling. Used by P3 / P3-validate when there are 5 runs × 500
    25	  turns per persona; the inner block protects the CI from
    26	  underestimating standard error when consecutive turns are correlated.
    27	
    28	Both helpers return :class:`BootstrapResult` so plotting / quorum gates
    29	can read ``point / lo / hi / width`` uniformly.
    30	"""
    31	
    32	from __future__ import annotations
    33	
    34	import math
    35	from dataclasses import dataclass
    36	from typing import TYPE_CHECKING
    37	
    38	import numpy as np
    39	
    40	if TYPE_CHECKING:
    41	    from collections.abc import Sequence
    42	
    43	DEFAULT_N_RESAMPLES: int = 2000
    44	"""Default bootstrap iteration count.
    45	
    46	2000 is enough for percentile CI stability at width <0.005 for
    47	N>=30 sample sizes — the M8 baseline metric pipeline used the same
    48	budget and shipped without observability complaints. For DB9 ratio
    49	gating the stability matters more than the iteration count, so the
    50	parameter is exposed and the script overrides up to 10K when running
    51	overnight.
    52	"""
    53	
    54	DEFAULT_CI: float = 0.95
    55	"""Default 2-sided percentile CI (95%)."""
    56	
    57	
    58	@dataclass(frozen=True, slots=True)
    59	class BootstrapResult:
    60	    """Bootstrap CI summary returned by every public helper here."""
    61	
    62	    point: float
    63	    """The point estimate computed from the original (un-resampled) sample."""
    64	    lo: float
    65	    """Lower percentile bound."""
    66	    hi: float
    67	    """Upper percentile bound."""
    68	    width: float
    69	    """``hi - lo``. Pre-computed because callers compare widths directly
    70	    (DB9 quorum, ME-4 ratio decision) and the dataclass is frozen so
    71	    storing the derived value is safe."""
    72	    n: int
    73	    """Effective sample size used (after dropping NaN/None)."""
    74	    n_resamples: int
    75	    """Bootstrap iteration count."""
    76	    method: str
    77	    """One of ``"percentile"`` / ``"hierarchical-block"``. Surfaced in
    78	    the JSON output so the consumer knows which estimator produced the
    79	    interval."""
    80	
    81	
    82	def _clean(values: Sequence[float | None]) -> np.ndarray:
    83	    """Drop None / NaN entries and return a float array.
    84	
    85	    Per the M8 ``compute_*`` contract, ``None``/``NaN`` mean "no
    86	    measurement" rather than "zero". The bootstrap path drops those
    87	    rows up front so the resampler does not propagate NaN.
    88	    """
    89	    cleaned = [
    90	        float(v)
    91	        for v in values
    92	        if v is not None and not (isinstance(v, float) and math.isnan(v))
    93	    ]
    94	    return np.asarray(cleaned, dtype=float)
    95	
    96	
    97	def bootstrap_ci(
    98	    values: Sequence[float | None],
    99	    *,
   100	    n_resamples: int = DEFAULT_N_RESAMPLES,
   101	    ci: float = DEFAULT_CI,
   102	    seed: int = 0,
   103	    statistic: str = "mean",
   104	) -> BootstrapResult:
   105	    """Percentile bootstrap CI for ``statistic`` of ``values``.
   106	
   107	    Args:
   108	        values: Per-sample measurements (one per cell / turn / item).
   109	            ``None``/``NaN`` entries are dropped via :func:`_clean`.
   110	        n_resamples: Bootstrap iteration count.
   111	        ci: Two-sided coverage in ``(0, 1)``.
   112	        seed: Deterministic bitstream seed (``np.random.default_rng``).
   113	        statistic: Either ``"mean"`` (default) or ``"median"``. The
   114	            quorum thresholds in `design-final.md` use means, so the
   115	            default is mean.
   116	
   117	    Returns:
   118	        :class:`BootstrapResult` with ``method="percentile"`` and
   119	        ``n`` reflecting the sample size after dropping NaN/None.
   120	
   121	    Raises:
   122	        ValueError: If ``ci`` is not in ``(0, 1)``, ``n_resamples < 1``,
   123	            or ``values`` is empty after cleaning.
   124	    """
   125	    if not 0.0 < ci < 1.0:
   126	        raise ValueError(f"ci must be in (0, 1) (got {ci})")
   127	    if n_resamples < 1:
   128	        raise ValueError(f"n_resamples must be >= 1 (got {n_resamples})")
   129	    if statistic not in {"mean", "median"}:
   130	        raise ValueError(f"statistic must be 'mean' or 'median' (got {statistic!r})")
   131	
   132	    cleaned = _clean(values)
   133	    n = cleaned.size
   134	    if n == 0:
   135	        raise ValueError("values has 0 finite entries — cannot bootstrap")
   136	
   137	    rng = np.random.default_rng(seed)
   138	    point = (
   139	        float(np.mean(cleaned)) if statistic == "mean" else float(np.median(cleaned))
   140	    )
   141	
   142	    indices = rng.integers(0, n, size=(n_resamples, n))
   143	    samples = cleaned[indices]
   144	    if statistic == "mean":
   145	        replicate_stats = samples.mean(axis=1)
   146	    else:
   147	        replicate_stats = np.median(samples, axis=1)
   148	
   149	    alpha = 1.0 - ci
   150	    lo = float(np.quantile(replicate_stats, alpha / 2.0))
   151	    hi = float(np.quantile(replicate_stats, 1.0 - alpha / 2.0))
   152	    return BootstrapResult(
   153	        point=point,
   154	        lo=lo,
   155	        hi=hi,
   156	        width=hi - lo,
   157	        n=n,
   158	        n_resamples=n_resamples,
   159	        method="percentile",
   160	    )
   161	
   162	
   163	def hierarchical_bootstrap_ci(
   164	    values_per_cluster: Sequence[Sequence[float | None]],
   165	    *,
   166	    block_length: int = 50,
   167	    n_resamples: int = DEFAULT_N_RESAMPLES,
   168	    ci: float = DEFAULT_CI,
   169	    seed: int = 0,
   170	) -> BootstrapResult:
   171	    """Cluster + circular-block bootstrap for autocorrelated turn streams.
   172	
   173	    Use this for P3 golden-baseline 5 runs × 500 turns (Codex HIGH-2):
   174	    the outer level resamples runs (clusters) with replacement, and the
   175	    inner level draws circular blocks of length ``block_length`` so the
   176	    within-run autocorrelation is preserved.
   177	
   178	    Args:
   179	        values_per_cluster: ``runs`` outer × ``turns`` inner — one
   180	            sequence per run (cluster). NaN/None within a cluster are
   181	            dropped (per :func:`_clean`); a cluster that ends up empty
   182	            is dropped from the outer resample.
   183	        block_length: Inner circular block length (turns). For 500-turn
   184	            runs the literature default 50 covers ~1 effective sample
   185	            per 10 blocks (sensitivity grid for tuning lives in P5).
   186	        n_resamples: Bootstrap iteration count.
   187	        ci: Two-sided coverage in ``(0, 1)``.
   188	        seed: Deterministic seed.
   189	
   190	    Returns:
   191	        :class:`BootstrapResult` with ``method="hierarchical-block"``
   192	        and ``n`` reflecting the **total** number of finite turn-level
   193	        observations across non-empty clusters (not the cluster count).
   194	
   195	    Raises:
   196	        ValueError: On invalid arguments or all-empty clusters.
   197	    """
   198	    if not 0.0 < ci < 1.0:
   199	        raise ValueError(f"ci must be in (0, 1) (got {ci})")
   200	    if n_resamples < 1:
   201	        raise ValueError(f"n_resamples must be >= 1 (got {n_resamples})")
   202	    if block_length < 1:
   203	        raise ValueError(f"block_length must be >= 1 (got {block_length})")
   204	
   205	    cleaned_clusters = [_clean(cluster) for cluster in values_per_cluster]
   206	    cleaned_clusters = [c for c in cleaned_clusters if c.size > 0]
   207	    if not cleaned_clusters:
   208	        raise ValueError("no finite values in any cluster")
   209	
   210	    rng = np.random.default_rng(seed)
   211	    pooled = np.concatenate(cleaned_clusters)
   212	    point = float(pooled.mean())
   213	    n_total = pooled.size
   214	    n_clusters = len(cleaned_clusters)
   215	
   216	    replicate_means = np.empty(n_resamples, dtype=float)
   217	    for r in range(n_resamples):
   218	        outer_idx = rng.integers(0, n_clusters, size=n_clusters)
   219	        replicate_concat: list[np.ndarray] = []
   220	        for ci_idx in outer_idx:
   221	            cluster = cleaned_clusters[ci_idx]
   222	            cluster_n = cluster.size
   223	            n_blocks = max(1, math.ceil(cluster_n / block_length))
   224	            starts = rng.integers(0, cluster_n, size=n_blocks)
   225	            for s in starts:
   226	                # Circular block (wraps around for indices >= cluster_n).
   227	                idx = (np.arange(block_length) + s) % cluster_n
   228	                replicate_concat.append(cluster[idx])
   229	        replicate = np.concatenate(replicate_concat)
   230	        replicate_means[r] = float(replicate.mean())
   231	
   232	    alpha = 1.0 - ci
   233	    lo = float(np.quantile(replicate_means, alpha / 2.0))
   234	    hi = float(np.quantile(replicate_means, 1.0 - alpha / 2.0))
   235	    return BootstrapResult(
   236	        point=point,
   237	        lo=lo,
   238	        hi=hi,
   239	        width=hi - lo,
   240	        n=n_total,
   241	        n_resamples=n_resamples,
   242	        method="hierarchical-block",
   243	    )
   244	
   245	
   246	__all__ = [
   247	    "DEFAULT_CI",
   248	    "DEFAULT_N_RESAMPLES",
   249	    "BootstrapResult",
   250	    "bootstrap_ci",
   251	    "hierarchical_bootstrap_ci",
   252	]

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/tier_a/burrows.py | sed -n '1,260p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     1	"""Burrows Delta — z-scored function-word L1 (Manhattan) distance.
     2	
     3	Codex ``gpt-5.5 xhigh`` review (HIGH-5) corrected an early sketch that
     4	called the metric "function-word vector cosine"; cosine distance is
     5	not the Burrows Delta family. The canonical R-stylo formulation
     6	(Eder/Rybicki/Kestemont, R Journal 2016) is:
     7	
     8	1. Pick a closed list of function words for the language under test.
     9	2. From a *background corpus* compute, per function word, the mean and
    10	   standard deviation of relative frequency.
    11	3. For each text under comparison, compute its relative frequency
    12	   vector and z-score against the background statistics.
    13	4. Delta between two texts = sum of absolute differences of their
    14	   z-vectors (Manhattan / L1 distance).
    15	
    16	In this codebase we hold the persona's z-vector in a
    17	:class:`BurrowsReference` and compare an incoming test text against it.
    18	The reference is per-language; cross-language comparison raises
    19	:class:`BurrowsLanguageMismatchError` (per ``blockers.md`` "Burrows
    20	multi-lang reference 暫定方針").
    21	
    22	P1a delivers the pure math against synthetic references. P1b populates
    23	real corpora (Akademie-Ausgabe Kant, KGW Nietzsche, 利休百首, plus a
    24	synthetic 4th persona) under :mod:`erre_sandbox.evidence.reference_corpus`
    25	once licensing has been confirmed (ME-6).
    26	"""
    27	
    28	from __future__ import annotations
    29	
    30	from collections import Counter
    31	from dataclasses import dataclass
    32	from math import isfinite
    33	from typing import TYPE_CHECKING
    34	
    35	if TYPE_CHECKING:  # pragma: no cover - typing only
    36	    from collections.abc import Iterable
    37	
    38	DEFAULT_WHITESPACE_LANGUAGES: frozenset[str] = frozenset({"en", "de"})
    39	"""Languages for which whitespace tokenisation gives a usable
    40	function-word count.
    41	
    42	Japanese (``"ja"``) requires a morphological analyser
    43	(MeCab/SudachiPy) — left to P1b. Calling
    44	:func:`compute_burrows_delta` with ``language="ja"`` and the default
    45	tokeniser raises explicitly so we don't silently fold a stylometric
    46	signal that is meaningless for the unsegmented script.
    47	"""
    48	
    49	
    50	class BurrowsLanguageMismatchError(ValueError):
    51	    """Raised when reference language does not match the test text language.
    52	
    53	    Function-word distributions are language-specific; comparing a German
    54	    profile against an English text would produce a meaningless number.
    55	    The contract defers explicit support of the third language (``"ja"``)
    56	    to a per-language tokenizer landing in P1b.
    57	    """
    58	
    59	
    60	class BurrowsTokenizationUnsupportedError(NotImplementedError):
    61	    """Raised when the requested language has no built-in tokeniser yet.
    62	
    63	    Lets P1b add a Japanese-specific entry without changing the public
    64	    contract: callers can detect "tokenizer missing" separately from
    65	    "language mismatch" and wire in their own splitter via
    66	    ``preprocessed_tokens`` once P1b ships the SudachiPy adapter.
    67	    """
    68	
    69	
    70	@dataclass(frozen=True)
    71	class BurrowsReference:
    72	    """Per-language Burrows reference profile.
    73	
    74	    Attributes:
    75	        language: ISO-ish language tag (``"en"`` / ``"de"`` / ``"ja"``).
    76	            Compared verbatim against the ``language`` argument of
    77	            :func:`compute_burrows_delta`.
    78	        function_words: Closed list of lower-case function words. Order
    79	            is positional; ``background_mean`` /
    80	            ``background_std`` / ``profile_freq`` align by index.
    81	        background_mean: Mean relative frequency of each function word
    82	            across a generic background corpus (per-token rate, in
    83	            ``[0, 1]``).
    84	        background_std: Standard deviation of relative frequency in the
    85	            same background corpus. Words with ``std <= 0`` are dropped
    86	            from the Delta sum (would z-divide by zero).
    87	        profile_freq: This persona's relative frequency vector for the
    88	            same function words, computed from the persona's reference
    89	            corpus.
    90	
    91	    Construction is left to ``reference_corpus`` ingestion (P1b). For
    92	    P1a tests, callers build a small synthetic ``BurrowsReference``
    93	    directly.
    94	    """
    95	
    96	    language: str
    97	    function_words: tuple[str, ...]
    98	    background_mean: tuple[float, ...]
    99	    background_std: tuple[float, ...]
   100	    profile_freq: tuple[float, ...]
   101	
   102	    def __post_init__(self) -> None:
   103	        n = len(self.function_words)
   104	        if not (
   105	            len(self.background_mean) == n
   106	            and len(self.background_std) == n
   107	            and len(self.profile_freq) == n
   108	        ):
   109	            raise ValueError(
   110	                "BurrowsReference vectors must have equal length;"
   111	                f" function_words={n} mean={len(self.background_mean)}"
   112	                f" std={len(self.background_std)} profile={len(self.profile_freq)}",
   113	            )
   114	        if any(s < 0 for s in self.background_std):
   115	            raise ValueError("background_std entries must be non-negative")
   116	        if any(not isfinite(v) for v in self.background_mean):
   117	            raise ValueError("background_mean entries must be finite")
   118	        if any(not isfinite(v) for v in self.background_std):
   119	            raise ValueError("background_std entries must be finite")
   120	        if any(not isfinite(v) for v in self.profile_freq):
   121	            raise ValueError("profile_freq entries must be finite")
   122	
   123	
   124	def _tokenize(text: str, language: str) -> list[str]:
   125	    """Lower-case whitespace tokeniser for ``en`` and ``de``.
   126	
   127	    Japanese routes through :class:`BurrowsTokenizationUnsupportedError`
   128	    until P1b lands a SudachiPy-backed splitter (or callers preprocess
   129	    the text into tokens themselves and use ``preprocessed_tokens=``).
   130	    """
   131	    if language not in DEFAULT_WHITESPACE_LANGUAGES:
   132	        raise BurrowsTokenizationUnsupportedError(
   133	            f"Burrows Delta default tokenizer does not support language"
   134	            f" {language!r}; pass preprocessed_tokens= or wait for P1b"
   135	            f" to ship a {language}-specific tokenizer",
   136	        )
   137	    # ``str.split`` (no args) collapses arbitrary whitespace, which is
   138	    # adequate for the function-word counting use-case where exact
   139	    # boundary handling at punctuation is tolerated noise.
   140	    return [tok.lower() for tok in text.split() if tok]
   141	
   142	
   143	def compute_burrows_delta(
   144	    text: str,
   145	    reference: BurrowsReference,
   146	    *,
   147	    language: str,
   148	    preprocessed_tokens: Iterable[str] | None = None,
   149	) -> float:
   150	    """Burrows Delta = sum of absolute z-score differences (L1 distance).
   151	
   152	    Args:
   153	        text: Test utterance / document. Ignored if ``preprocessed_tokens``
   154	            is provided — useful when the caller already ran a per-language
   155	            tokenizer (e.g. SudachiPy for Japanese).
   156	        reference: Per-language profile. ``reference.language`` must equal
   157	            ``language`` or :class:`BurrowsLanguageMismatchError` is raised.
   158	        language: Language of the test text. Must match
   159	            ``reference.language``.
   160	        preprocessed_tokens: Optional pre-tokenised lower-case stream that
   161	            bypasses the built-in whitespace tokeniser. Lets Japanese (and
   162	            future languages with non-trivial segmentation) participate
   163	            ahead of full P1b tokeniser plumbing.
   164	
   165	    Returns:
   166	        ``sum_i |z_test_i - z_profile_i|`` over function words with
   167	        ``std > 0``. Returns ``float('nan')`` when the test text is empty
   168	        or no function word survived the ``std > 0`` filter — a NaN here
   169	        is the explicit "metric unmeasurable" signal the bootstrap-CI
   170	        code path knows how to drop (per the M8 ``compute_*`` contract:
   171	        ``None``/``NaN`` means "no measurement", not "zero").
   172	
   173	    Raises:
   174	        BurrowsLanguageMismatchError: When ``language != reference.language``.
   175	        BurrowsTokenizationUnsupportedError: When ``language`` has no
   176	            default tokenizer and ``preprocessed_tokens`` is ``None``.
   177	    """
   178	    if language != reference.language:
   179	        raise BurrowsLanguageMismatchError(
   180	            f"Burrows reference language {reference.language!r} does not"
   181	            f" match test text language {language!r}; per-language"
   182	            f" reference contract requires identical tag",
   183	        )
   184	
   185	    tokens: list[str]
   186	    if preprocessed_tokens is not None:
   187	        tokens = [t.lower() for t in preprocessed_tokens if t]
   188	    else:
   189	        tokens = _tokenize(text, language)
   190	
   191	    total = len(tokens)
   192	    if total == 0:
   193	        return float("nan")
   194	
   195	    counts = Counter(tokens)
   196	
   197	    delta_sum = 0.0
   198	    counted = 0
   199	    for fw, mean, std, profile in zip(
   200	        reference.function_words,
   201	        reference.background_mean,
   202	        reference.background_std,
   203	        reference.profile_freq,
   204	        strict=True,
   205	    ):
   206	        if std <= 0.0:
   207	            continue
   208	        test_freq = counts.get(fw, 0) / total
   209	        z_test = (test_freq - mean) / std
   210	        z_profile = (profile - mean) / std
   211	        delta_sum += abs(z_test - z_profile)
   212	        counted += 1
   213	
   214	    if counted == 0:
   215	        return float("nan")
   216	    return delta_sum

exec
/bin/zsh -lc "rg -n \"_p3a_decide|p3a_decide|\\\"personas\\\"|cells\\\"\" . --glob '"'!*.duckdb'"'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
./scripts/p3a_decide.py:30:6. Writes ``data/eval/pilot/_p3a_decide.json`` with schema ``p3a_decide/v2``.
./scripts/p3a_decide.py:43:    uv run python scripts/p3a_decide.py
./scripts/p3a_decide.py:44:    # → writes data/eval/pilot/_p3a_decide.json
./scripts/p3a_decide.py:68:_OUT_PATH: Final[Path] = _PILOT_DIR / "_p3a_decide.json"
./scripts/p3a_decide.py:324:                    "n_cells": len(widths),
./scripts/p3a_decide.py:440:        "schema": "p3a_decide/v2",
./scripts/p3a_decide.py:449:        "cells": blocks,
./src/erre_sandbox/__main__.py:93:        default="personas",
./scripts/p3a_summary.py:142:        "cells": cells,
./data/eval/pilot/_summary.json:3:  "cells": [
./data/eval/pilot/_rsync_receipt.txt:58:#   uv run python scripts/p3a_decide.py
./data/eval/pilot/_rsync_receipt.txt:59:#   # → data/eval/pilot/_p3a_decide.json + ME-4 ADR second Edit (ratio finalization)
./src/erre_sandbox/cli/eval_run_golden.py:151:_PERSONAS_DIR_DEFAULT: Final[Path] = Path("personas")
./src/erre_sandbox/evidence/golden_baseline.py:522:        "personas": persona_list,
./src/erre_sandbox/evidence/golden_baseline.py:568:        len(manifest["personas"]),
./golden/seeds.json:4:  "personas": [
./src/erre_sandbox/bootstrap.py:78:    personas_dir: Path = field(default_factory=lambda: Path("personas"))
./src/erre_sandbox/evidence/reference_corpus/vectors.json:158:      "personas": {
./src/erre_sandbox/evidence/reference_corpus/vectors.json:399:      "personas": {
./src/erre_sandbox/evidence/reference_corpus/_build_vectors.py:18:          "personas": {
./src/erre_sandbox/evidence/reference_corpus/_build_vectors.py:228:                "personas": personas_de,
./src/erre_sandbox/evidence/reference_corpus/_build_vectors.py:234:                "personas": personas_ja,
./src/erre_sandbox/evidence/reference_corpus/_build_vectors.py:251:        personas = data["personas"]
./src/erre_sandbox/evidence/reference_corpus/loader.py:179:        personas_block = lang_data.get("personas")
./src/erre_sandbox/evidence/reference_corpus/loader.py:222:    personas_block = lang_data.get("personas")
./tests/test_main.py:24:    assert _resolve_agents(None, Path("personas")) == ()
./tests/test_main.py:28:    assert _resolve_agents("   ", Path("personas")) == ()
./tests/test_main.py:29:    assert _resolve_agents(",,", Path("personas")) == ()
./tests/test_main.py:33:    specs = _resolve_agents("kant,nietzsche,rikyu", Path("personas"))
./tests/test_main.py:67:    specs = _resolve_agents(" kant , nietzsche ", Path("personas"))
./tests/test_main.py:79:    assert args.personas_dir == "personas"
./tests/test_personas/test_load_all.py:26:PERSONA_DIR = REPO_ROOT / "personas"
./tests/test_persona_kant.py:21:KANT_YAML = REPO_ROOT / "personas" / "kant.yaml"
./tests/test_integration/test_slice_gamma_e2e.py:56:_PERSONAS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "personas"
./tests/test_integration/test_slice_delta_e2e.py:58:_PERSONAS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "personas"
./tests/test_behavior_profile.py:22:PERSONAS_DIR = REPO_ROOT / "personas"
./tests/test_bootstrap.py:42:    persona = _load_persona_yaml(Path("personas"), "kant")
./tests/test_bootstrap.py:58:        persona = _load_persona_yaml(Path("personas"), pid)
./tests/test_bootstrap.py:81:    return _load_persona_yaml(Path("personas"), "kant")
./tests/test_evidence/test_p3a_decide.py:1:"""Unit tests for the pure aggregation/verdict helpers in scripts/p3a_decide.py.
./tests/test_evidence/test_p3a_decide.py:17:_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "p3a_decide.py"
./tests/test_evidence/test_p3a_decide.py:21:def p3a_decide():
./tests/test_evidence/test_p3a_decide.py:22:    spec = importlib.util.spec_from_file_location("scripts_p3a_decide", _SCRIPT)
./tests/test_evidence/test_p3a_decide.py:67:def test_mean_widths_by_condition_aggregates_per_persona(p3a_decide):
./tests/test_evidence/test_p3a_decide.py:76:    summary = p3a_decide._mean_widths_by_condition(blocks)
./tests/test_evidence/test_p3a_decide.py:87:def test_mean_widths_skips_missing_metrics(p3a_decide):
./tests/test_evidence/test_p3a_decide.py:92:    summary = p3a_decide._mean_widths_by_condition(blocks)
./tests/test_evidence/test_p3a_decide.py:99:def test_ratio_summary_within_tolerance_maintains_default(p3a_decide):
./tests/test_evidence/test_p3a_decide.py:104:    out = p3a_decide._ratio_summary(by_condition)
./tests/test_evidence/test_p3a_decide.py:110:def test_ratio_summary_natural_wider_flags_alternative(p3a_decide):
./tests/test_evidence/test_p3a_decide.py:115:    out = p3a_decide._ratio_summary(by_condition)
./tests/test_evidence/test_p3a_decide.py:121:def test_ratio_summary_stimulus_wider_flags_alternative(p3a_decide):
./tests/test_evidence/test_p3a_decide.py:126:    out = p3a_decide._ratio_summary(by_condition)
./tests/test_evidence/test_p3a_decide.py:131:def test_ratio_summary_skipped_when_missing_value(p3a_decide):
./tests/test_evidence/test_p3a_decide.py:136:    out = p3a_decide._ratio_summary(by_condition)
./tests/test_evidence/test_p3a_decide.py:141:def test_pilot_path_uses_persona_and_condition(p3a_decide):
./tests/test_evidence/test_p3a_decide.py:142:    path = p3a_decide._pilot_path("kant", "natural")
./tests/test_evidence/test_p3a_decide.py:144:    path = p3a_decide._pilot_path("rikyu", "stimulus")
./tests/test_evidence/test_golden_baseline.py:169:    assert manifest["personas"] == list(DEFAULT_PERSONAS)

codex
A concrete implementation risk surfaced: `rikyu` is mapped to `ja`, while the Burrows implementation explicitly rejects Japanese unless pre-tokenized. Because `main()` catches cell-level exceptions and continues, this can quietly drop entire Rikyu cells and still produce a ratio from the remaining cells.
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/reference_corpus/loader.py | sed -n '160,250p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   160	
   161	    Returns:
   162	        Sorted tuple of ``(persona_id, language)`` pairs that have both
   163	        a provenance entry and a ``vectors.json`` profile. Pairs that
   164	        appear in only one of the two artefacts are excluded — they
   165	        would also raise on :func:`load_reference`, and the contract
   166	        for "available" is "loadable end-to-end".
   167	    """
   168	    vectors = _load_vectors_raw()
   169	    languages_block = vectors["languages"]
   170	    assert isinstance(languages_block, dict)
   171	    provenance = get_provenance_entries()
   172	    provenance_pairs = {(str(e["persona_id"]), str(e["language"])) for e in provenance}
   173	    out: list[tuple[str, str]] = []
   174	    for lang_key, lang_data in languages_block.items():
   175	        if language is not None and lang_key != language:
   176	            continue
   177	        if not isinstance(lang_data, dict):
   178	            continue
   179	        personas_block = lang_data.get("personas")
   180	        if not isinstance(personas_block, dict):
   181	            continue
   182	        for persona_id in personas_block:
   183	            pair = (persona_id, lang_key)
   184	            if pair in provenance_pairs:
   185	                out.append(pair)
   186	    return tuple(sorted(out))
   187	
   188	
   189	def _provenance_for(persona_id: str, language: str) -> dict[str, object]:
   190	    """Return the provenance entry for the pair, or raise."""
   191	    for entry in get_provenance_entries():
   192	        if entry.get("persona_id") == persona_id and entry.get("language") == language:
   193	            return entry
   194	    raise ReferenceCorpusMissingError(
   195	        f"no provenance entry registered for persona_id={persona_id!r}"
   196	        f" language={language!r} — see _provenance.yaml",
   197	    )
   198	
   199	
   200	def _vector_block_for(
   201	    persona_id: str, language: str
   202	) -> tuple[
   203	    tuple[str, ...],
   204	    tuple[float, ...],
   205	    tuple[float, ...],
   206	    tuple[float, ...],
   207	]:
   208	    """Return ``(function_words, bg_mean, bg_std, profile_freq)`` tuples."""
   209	    vectors = _load_vectors_raw()
   210	    languages_block = vectors["languages"]
   211	    assert isinstance(languages_block, dict)
   212	    if language not in languages_block:
   213	        raise ReferenceCorpusMissingError(
   214	            f"vectors.json has no language={language!r}; provenance entry"
   215	            f" registered persona_id={persona_id!r} but vectors are absent",
   216	        )
   217	    lang_data = languages_block[language]
   218	    if not isinstance(lang_data, dict):
   219	        raise ReferenceCorpusSchemaError(
   220	            f"vectors.json languages[{language!r}] must be a mapping",
   221	        )
   222	    personas_block = lang_data.get("personas")
   223	    if not isinstance(personas_block, dict) or persona_id not in personas_block:
   224	        raise ReferenceCorpusMissingError(
   225	            f"vectors.json languages[{language!r}].personas missing"
   226	            f" persona_id={persona_id!r}",
   227	        )
   228	    persona_block = personas_block[persona_id]
   229	    if not isinstance(persona_block, dict) or "profile_freq" not in persona_block:
   230	        raise ReferenceCorpusSchemaError(
   231	            f"vectors.json languages[{language!r}].personas[{persona_id!r}]"
   232	            f" missing 'profile_freq'",
   233	        )
   234	    fws = lang_data.get("function_words")
   235	    bg_mean = lang_data.get("background_mean")
   236	    bg_std = lang_data.get("background_std")
   237	    profile = persona_block.get("profile_freq")
   238	    if not (
   239	        isinstance(fws, list)
   240	        and isinstance(bg_mean, list)
   241	        and isinstance(bg_std, list)
   242	        and isinstance(profile, list)
   243	    ):
   244	        raise ReferenceCorpusSchemaError(
   245	            f"vectors.json languages[{language!r}] vectors must all be lists",
   246	        )
   247	    return (
   248	        tuple(str(w) for w in fws),
   249	        tuple(float(v) for v in bg_mean),
   250	        tuple(float(v) for v in bg_std),

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/reference_corpus/loader.py | sed -n '250,330p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   250	        tuple(float(v) for v in bg_std),
   251	        tuple(float(v) for v in profile),
   252	    )
   253	
   254	
   255	def load_reference(persona_id: str, language: str) -> BurrowsReference:
   256	    """Hydrate a frozen :class:`BurrowsReference` for the given pair.
   257	
   258	    Args:
   259	        persona_id: Stable persona identifier (matches ``personas/*.yaml``
   260	            and the keys under ``vectors.json``).
   261	        language: ISO-ish language tag (``"de"`` / ``"ja"``).
   262	
   263	    Returns:
   264	        A frozen :class:`BurrowsReference` ready to be passed to
   265	        :func:`erre_sandbox.evidence.tier_a.burrows.compute_burrows_delta`.
   266	
   267	    Raises:
   268	        ReferenceCorpusMissingError: ``(persona_id, language)`` is not
   269	            registered in either ``_provenance.yaml`` or ``vectors.json``.
   270	        ReferenceCorpusSchemaError: On-disk artefacts are structurally
   271	            broken (missing schema fields, vector length mismatch, etc.).
   272	    """
   273	    # Provenance is the gating contract — fetch it first so an
   274	    # unregistered pair never reaches the vectors lookup.
   275	    _provenance_for(persona_id, language)
   276	    fws, bg_mean, bg_std, profile = _vector_block_for(persona_id, language)
   277	    return BurrowsReference(
   278	        language=language,
   279	        function_words=fws,
   280	        background_mean=bg_mean,
   281	        background_std=bg_std,
   282	        profile_freq=profile,
   283	    )

exec
/bin/zsh -lc 'find data/eval/pilot -maxdepth 1 -type f -print | sort' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
data/eval/pilot/_rsync_receipt.txt
data/eval/pilot/_summary.json

exec
/bin/zsh -lc 'wc -l .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md' in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,120p' .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
    2031 .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md

 succeeded in 0ms:
Reading prompt from stdin...
OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/johnd/ERRE-Sand Box
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/johnd/.codex/memories] (network access enabled)
reasoning effort: xhigh
reasoning summaries: none
session id: 019df805-d6b6-7351-9457-f84fb94a238f
--------
user
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

exec
/bin/zsh -lc "sed -n '1,80p' .steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
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

exec
/bin/zsh -lc 'tail -n 180 .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
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

exec
/bin/zsh -lc "sed -n '1,80p' .steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
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


exec
/bin/zsh -lc 'rg -n "''^## Verdict|''^## HIGH|HIGH-|MEDIUM-|LOW-|final answer|codex" .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
8:sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/johnd/.codex/memories] (network access enabled)
17:> `cat .steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md
18:>  | codex exec --skip-git-repo-check`
19:> Save output verbatim to `codex-review-p3a-finalize.md`.
216:## Verdict
219:## HIGH (fix before run)
220:- HIGH-1: <title>
224:- HIGH-2: ...
227:- MEDIUM-1: ...
230:- LOW-1: ...
239:Per `.codex/budget.json` policy this invocation should fit within
247:codex
279:When they do, prefer the project-scoped agents in `.codex/agents/`.
335:codex
340:?? .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md
341:?? .steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md
986:   324	          (`codex-review-prompt-natural-gating.md` → `codex-review-natural-gating.md`、
992:   330	          (Codex HIGH-2 の AR(1) 想定、N(0,1) 解析解 ± 5% / AR(1) 合成データで
1010:   348	          (`codex-review-prompt-natural-gating-v2.md` → `codex-review-natural-gating-v2.md`
1012:   350	    - [x] HIGH-1 (wall default 不整合) / HIGH-2 (既存 cooldown test rewrite) /
1013:   351	          MEDIUM-1 (ME-8 explicit amendment) / MEDIUM-2 (conservative estimate
1030:   368	    - [x] `.codex/budget.json` 145,717 tokens 記録 (per_invocation_max=200K 内)
1045:   124	## ME-4 — Hybrid baseline ratio: P3a 完了後に確定 (Codex HIGH-3 系の defer ADR)
1071:   150	  - Codex HIGH-3: 元案の「P3 採取後 P3b で 50 turn pilot」は順序 invert + 統計力不足
1278:codex
1357:     3	m9-eval-system P5 (Codex HIGH-2 in `codex-review.md`): hierarchical
1527:   173	    Use this for P3 golden-baseline 5 runs × 500 turns (Codex HIGH-2):
1613:     3	Codex ``gpt-5.5 xhigh`` review (HIGH-5) corrected an early sketch that
1891:codex
2033:/bin/zsh -lc 'wc -l .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md' in /Users/johnd/ERRE-Sand Box
2035:/bin/zsh -lc "sed -n '1,120p' .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md" in /Users/johnd/ERRE-Sand Box
2037:    2031 .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md
2047:sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/johnd/.codex/memories] (network access enabled)
2056:> `cat .steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md
2057:>  | codex exec --skip-git-repo-check`
2058:> Save output verbatim to `codex-review-p3a-finalize.md`.
2162:/bin/zsh -lc "sed -n '1,80p' .steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md" in /Users/johnd/ERRE-Sand Box
2167:> `cat .steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md
2168:>  | codex exec --skip-git-repo-check`
2169:> Save output verbatim to `codex-review-p3a-finalize.md`.
2246:/bin/zsh -lc 'tail -n 180 .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md' in /Users/johnd/ERRE-Sand Box
2345:/bin/zsh -lc "sed -n '1,80p' .steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md" in /Users/johnd/ERRE-Sand Box
2350:> `cat .steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md
2351:>  | codex exec --skip-git-repo-check`
2352:> Save output verbatim to `codex-review-p3a-finalize.md`.

exec
/bin/zsh -lc 'ls -l .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
-rw-r--r--@ 1 johnd  staff  116752 May  5 21:05 .steering/20260430-m9-eval-system/codex-review-p3a-finalize.md

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/tier_a/__init__.py | sed -n '1,220p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     1	"""Tier A psycholinguistic metrics for the M9 evaluation system.
     2	
     3	The five Tier A metrics are pure post-hoc functions over collected
     4	``raw_dialog`` rows (DB6: never on the live inference path). Sub-module
     5	layout (per ``.steering/20260430-m9-eval-system/design-final.md`` §"v1
     6	補強 1: sub-module 構造"):
     7	
     8	* :mod:`burrows` — z-scored function-word L1 (Manhattan) Delta. Codex
     9	  HIGH-5 corrected the original "function-word vector cosine" sketch to
    10	  the canonical R-stylo formulation.
    11	* :mod:`mattr` — Moving Average Type-Token Ratio (window 100).
    12	* :mod:`nli` — DeBERTa-v3-base-mnli zero-shot contradiction.
    13	* :mod:`novelty` — MPNet semantic novelty (cosine distance to running
    14	  prior centroid).
    15	* :mod:`empath_proxy` — Empath secondary diagnostic. Used as a Tier A
    16	  psycholinguistic axis only; not a Big5 estimator (ME-1 / DB10).
    17	
    18	Each metric exposes a single pure ``compute_*`` function plus an
    19	optional injection point (``scorer`` / ``encoder`` / ``analyzer``) so
    20	unit tests can stub the heavy ML model. The default loader for the
    21	heavy path lives behind a lazy import — installing the project without
    22	``[eval]`` extras must not pull ``sentence-transformers`` or
    23	``transformers`` into resolution.
    24	"""
    25	
    26	from __future__ import annotations
    27	
    28	from erre_sandbox.evidence.tier_a.burrows import (
    29	    BurrowsLanguageMismatchError,
    30	    BurrowsReference,
    31	    compute_burrows_delta,
    32	)
    33	from erre_sandbox.evidence.tier_a.empath_proxy import compute_empath_proxy
    34	from erre_sandbox.evidence.tier_a.mattr import compute_mattr
    35	from erre_sandbox.evidence.tier_a.nli import compute_nli_contradiction
    36	from erre_sandbox.evidence.tier_a.novelty import compute_semantic_novelty
    37	
    38	__all__ = [
    39	    "BurrowsLanguageMismatchError",
    40	    "BurrowsReference",
    41	    "compute_burrows_delta",
    42	    "compute_empath_proxy",
    43	    "compute_mattr",
    44	    "compute_nli_contradiction",
    45	    "compute_semantic_novelty",
    46	]

exec
/bin/zsh -lc 'rg -n "def compute_nli_contradiction|def compute_semantic_novelty|def compute_empath_proxy" src/erre_sandbox/evidence/tier_a -n' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
src/erre_sandbox/evidence/tier_a/novelty.py:33:def compute_semantic_novelty(
src/erre_sandbox/evidence/tier_a/empath_proxy.py:33:def compute_empath_proxy(
src/erre_sandbox/evidence/tier_a/nli.py:32:def compute_nli_contradiction(

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/tier_a/novelty.py | sed -n '1,180p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/tier_a/nli.py | sed -n '1,180p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     1	"""Zero-shot NLI contradiction over (premise, hypothesis) pairs.
     2	
     3	The Tier A NLI metric quantifies whether a persona contradicts itself
     4	across consecutive turns or stated commitments. The default model is
     5	``MoritzLaurer/DeBERTa-v3-base-mnli`` — small enough (~140 MB) to load
     6	on the Mac side without GPU pressure, accurate enough to produce a
     7	useful contradiction probability for short philosophical exchanges.
     8	
     9	Tests stub the heavy model via the ``scorer`` keyword, so the unit
    10	tests exercise the aggregation logic without pulling
    11	``transformers`` into resolution. Real-model integration tests live
    12	behind ``@pytest.mark.eval`` and only run with ``--extra eval``
    13	installed.
    14	"""
    15	
    16	from __future__ import annotations
    17	
    18	from collections.abc import Callable, Sequence
    19	
    20	NLIScorer = Callable[[Sequence[tuple[str, str]]], list[float]]
    21	"""Stub-friendly callable shape: take ``(premise, hypothesis)`` pairs and
    22	return per-pair contradiction probability in ``[0, 1]``.
    23	
    24	Wrapping the model in a callable rather than depending on the concrete
    25	``transformers.Pipeline`` API keeps unit tests free of the heavy ML
    26	import and lets future spikes swap in alternative NLI heads
    27	(BIG5-CHAT regression head fallback, multilingual NLI) without
    28	touching the metric aggregation code.
    29	"""
    30	
    31	
    32	def compute_nli_contradiction(
    33	    pairs: Sequence[tuple[str, str]],
    34	    *,
    35	    scorer: NLIScorer | None = None,
    36	) -> float | None:
    37	    """Mean contradiction probability across the supplied pairs.
    38	
    39	    Args:
    40	        pairs: Sequence of ``(premise, hypothesis)`` strings — typically
    41	            consecutive utterances by the same persona, or a stated
    42	            principle vs. a later application of it.
    43	        scorer: Optional stub callable. When ``None`` the default
    44	            DeBERTa-v3-base-mnli pipeline is lazily loaded; tests
    45	            should always pass a stub to avoid the model download.
    46	
    47	    Returns:
    48	        ``None`` when ``pairs`` is empty (no measurement possible).
    49	        Otherwise the mean contradiction probability across pairs.
    50	    """
    51	    if not pairs:
    52	        return None
    53	    fn = scorer if scorer is not None else _load_default_scorer()
    54	    probs = list(fn(pairs))
    55	    if not probs:
    56	        return None
    57	    return sum(probs) / len(probs)
    58	
    59	
    60	def _load_default_scorer() -> NLIScorer:
    61	    """Lazy-load the default DeBERTa-v3-base-mnli zero-shot pipeline.
    62	
    63	    Heavy imports stay function-local so that the project is importable
    64	    without ``[eval]`` extras (``transformers`` resolution is then
    65	    skipped). ``# noqa: PLC0415`` is the project-wide pattern for this.
    66	    """
    67	    from transformers import (  # noqa: PLC0415  # heavy ML dep behind eval extras
    68	        pipeline,
    69	    )
    70	
    71	    pipe = pipeline(
    72	        "zero-shot-classification",
    73	        model="MoritzLaurer/DeBERTa-v3-base-mnli",
    74	    )
    75	    candidate_labels = ["contradiction", "neutral", "entailment"]
    76	
    77	    def scorer(pairs: Sequence[tuple[str, str]]) -> list[float]:
    78	        out: list[float] = []
    79	        for premise, hypothesis in pairs:
    80	            # The "[SEP]" join is the convention DeBERTa-v3-base-mnli
    81	            # was trained with; it lets the zero-shot head treat the
    82	            # pair as a single sequence whose label space is the three
    83	            # NLI classes above.
    84	            joined = f"{premise} [SEP] {hypothesis}"
    85	            result = pipe(joined, candidate_labels=candidate_labels)
    86	            scores = dict(zip(result["labels"], result["scores"], strict=True))
    87	            out.append(float(scores.get("contradiction", 0.0)))
    88	        return out
    89	
    90	    return scorer

 succeeded in 0ms:
     1	"""Semantic novelty — mean cosine distance to running prior centroid.
     2	
     3	For every turn after the first, embed the utterance with MPNet
     4	(``sentence-transformers/all-mpnet-base-v2``) and compare it to the
     5	average direction of all prior turns. A persona that keeps cycling
     6	through the same idea collapses toward zero; a persona that
     7	genuinely introduces new content yields persistent positive distance.
     8	
     9	The pure-numpy aggregation step is kept stub-friendly via the
    10	``encoder`` keyword. Tests inject a fixed embedding fixture so the
    11	heavy ``sentence-transformers`` import never fires unless the caller
    12	asked for the real model. Numpy is a core dependency, so the metric
    13	itself stays lightweight.
    14	"""
    15	
    16	from __future__ import annotations
    17	
    18	from collections.abc import Callable, Sequence
    19	
    20	import numpy as np
    21	
    22	NoveltyEncoder = Callable[[Sequence[str]], list[list[float]]]
    23	"""Stub-friendly callable shape: take a list of strings, return a list of
    24	embeddings (one per string, fixed dimensionality).
    25	
    26	Returning plain ``list[list[float]]`` rather than ``np.ndarray`` keeps
    27	test fixtures readable and avoids forcing the encoder implementation
    28	to use numpy (an Ollama-served embedding service, for example, can
    29	return Python lists directly).
    30	"""
    31	
    32	
    33	def compute_semantic_novelty(
    34	    utterances: Sequence[str],
    35	    *,
    36	    encoder: NoveltyEncoder | None = None,
    37	) -> float | None:
    38	    """Mean cosine distance between each turn embedding and prior centroid.
    39	
    40	    Args:
    41	        utterances: Ordered sequence of turn utterances. The first turn
    42	            has no prior centroid so it does not contribute; subsequent
    43	            turns each contribute one cosine-distance value.
    44	        encoder: Optional stub callable. When ``None`` the default
    45	            MPNet encoder is lazily loaded; tests should always pass a
    46	            stub.
    47	
    48	    Returns:
    49	        ``None`` when fewer than 2 utterances are available (no prior
    50	        centroid to compare against). Otherwise the mean cosine
    51	        distance ``1 - cos(emb_i, mean(emb_0..i-1))`` across
    52	        ``i = 1..n-1``. Values are in ``[0, 2]`` because cosine
    53	        similarity ranges over ``[-1, 1]``.
    54	    """
    55	    if len(utterances) < 2:  # noqa: PLR2004 — contract: need ≥2 turns
    56	        return None
    57	    fn = encoder if encoder is not None else _load_default_encoder()
    58	    raw = fn(list(utterances))
    59	    if not raw:
    60	        return None
    61	    matrix = np.asarray(raw, dtype=float)
    62	    if matrix.ndim != 2 or matrix.shape[0] != len(utterances):  # noqa: PLR2004 — 2D embedding matrix expected
    63	        raise ValueError(
    64	            f"encoder returned shape {matrix.shape}, expected 2D with"
    65	            f" {len(utterances)} rows",
    66	        )
    67	
    68	    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    69	    safe_norms = np.where(norms == 0, 1.0, norms)
    70	    unit = matrix / safe_norms
    71	
    72	    distances: list[float] = []
    73	    for i in range(1, len(unit)):
    74	        prior_mean = unit[:i].mean(axis=0)
    75	        prior_norm = float(np.linalg.norm(prior_mean))
    76	        if prior_norm == 0.0:
    77	            # Antipodal prior turns cancelled; treat as max novelty
    78	            # (1.0) rather than NaN so downstream aggregation still
    79	            # produces a number on pathological synthetic inputs.
    80	            distances.append(1.0)
    81	            continue
    82	        prior_unit = prior_mean / prior_norm
    83	        cos_sim = float(np.dot(unit[i], prior_unit))
    84	        distances.append(1.0 - cos_sim)
    85	
    86	    if not distances:
    87	        return None
    88	    return float(sum(distances) / len(distances))
    89	
    90	
    91	def _load_default_encoder() -> NoveltyEncoder:
    92	    """Lazy-load ``sentence-transformers/all-mpnet-base-v2``.
    93	
    94	    Heavy import deferred until the caller actually needs the real
    95	    embedding model — keeps the module importable without
    96	    ``[eval]`` extras.
    97	    """
    98	    from sentence_transformers import (  # noqa: PLC0415  # heavy ML dep behind eval extras
    99	        SentenceTransformer,
   100	    )
   101	
   102	    model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
   103	
   104	    def encoder(batch: Sequence[str]) -> list[list[float]]:
   105	        encoded = model.encode(list(batch), show_progress_bar=False)
   106	        return [list(map(float, vec)) for vec in encoded]
   107	
   108	    return encoder

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/tier_a/empath_proxy.py | sed -n '1,180p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     1	"""Empath secondary diagnostic — psycholinguistic category vector.
     2	
     3	Empath (Fast et al. 2016) is a deep-learning category lexicon that maps
     4	text to ~200 affective / topical categories ("anger", "ritual",
     5	"violence", ...). The M9 design uses Empath as **one Tier A axis**
     6	among the five — a coarse signal of which themes a persona spends
     7	words on, useful for descriptive contrast between Kant's "law" /
     8	"order" / "duty" register and Nietzsche's "war" / "art" / "power"
     9	register.
    10	
    11	**Big5 claim is explicitly NOT made.** ME-1 in the design's
    12	``decisions.md`` keeps Big5 self-report on IPIP-NEO via Tier B; using
    13	Empath as a Big5 estimator was the v1 sketch and was rejected. The
    14	secondary-diagnostic role lets the metric still earn its keep without
    15	inheriting the LIWC-shaped problems Empath was originally critiqued
    16	for.
    17	"""
    18	
    19	from __future__ import annotations
    20	
    21	from collections.abc import Callable, Sequence
    22	
    23	EmpathAnalyzer = Callable[[Sequence[str]], dict[str, float]]
    24	"""Stub-friendly callable: take a list of utterances, return a category
    25	score dict (category → mean / normalized intensity over the batch).
    26	
    27	The single-callable boundary lets unit tests inject a deterministic
    28	score map without spinning up the Empath lexicon (which downloads a
    29	pickle on first use).
    30	"""
    31	
    32	
    33	def compute_empath_proxy(
    34	    utterances: Sequence[str],
    35	    *,
    36	    analyzer: EmpathAnalyzer | None = None,
    37	) -> dict[str, float]:
    38	    """Return the Empath category-score vector aggregated over utterances.
    39	
    40	    Args:
    41	        utterances: Sequence of turn texts to analyse together. Empty
    42	            input returns an empty dict; the caller is responsible for
    43	            treating "no measurement" as it sees fit (Tier A
    44	            aggregation typically drops empty maps before bootstrap).
    45	        analyzer: Optional stub callable. When ``None`` the default
    46	            Empath lexicon is lazily loaded; tests should always pass
    47	            a stub to keep the lexicon download out of CI.
    48	
    49	    Returns:
    50	        Dict mapping Empath category name → score. Score units depend
    51	        on the analyzer (the default returns normalized intensities in
    52	        ``[0, 1]``); the metric layer treats this as opaque since the
    53	        downstream Tier A consumer just ranks personas by category.
    54	    """
    55	    if not utterances:
    56	        return {}
    57	    fn = analyzer if analyzer is not None else _load_default_analyzer()
    58	    return dict(fn(list(utterances)))
    59	
    60	
    61	def _load_default_analyzer() -> EmpathAnalyzer:
    62	    """Lazy-load the Empath lexicon and wrap ``analyze()`` as a callable.
    63	
    64	    Heavy import deferred so importing this module without ``[eval]``
    65	    extras stays free.
    66	    """
    67	    from empath import Empath  # noqa: PLC0415  # heavy data dep behind eval extras
    68	
    69	    lex = Empath()
    70	
    71	    def analyzer(batch: Sequence[str]) -> dict[str, float]:
    72	        joined = " ".join(batch)
    73	        # ``Empath.analyze`` returns ``Mapping[str, float] | None``;
    74	        # an empty input or unknown vocabulary yields ``None``, which
    75	        # we surface as an empty dict for type-stable callers.
    76	        result = lex.analyze(joined, normalize=True)
    77	        if result is None:
    78	            return {}
    79	        return {str(k): float(v) for k, v in result.items()}
    80	
    81	    return analyzer

codex
I have enough to classify the main risks. I’ll run the focused test file once so the report can distinguish “tests pass” from “coverage misses the decision-critical failure modes.”
exec
/bin/zsh -lc 'uv run pytest tests/test_evidence/test_p3a_decide.py' in /Users/johnd/ERRE-Sand Box
 succeeded in 533ms:
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/johnd/ERRE-Sand Box
configfile: pyproject.toml
plugins: asyncio-0.26.0, anyio-4.13.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 7 items

tests/test_evidence/test_p3a_decide.py .......                           [100%]

============================== 7 passed in 0.19s ===============================

exec
/bin/zsh -lc "PYTHONPATH=src python -c 'from erre_sandbox.evidence.reference_corpus.loader import load_reference; from erre_sandbox.evidence.tier_a import compute_burrows_delta; ref=load_reference(\"rikyu\", \"ja\"); print(ref.language); print(compute_burrows_delta(\"一期一会\", ref, language=\"ja\"))'" in /Users/johnd/ERRE-Sand Box
 exited 1 in 115ms:
codex
## Verdict
block — Current script can produce an ME-4 recommendation from raw, sample-size-confounded widths and can silently compute the ratio from partial cells.

## HIGH (fix before run)
- HIGH-1: Raw `natural / stimulus` CI width ratio is not decision-valid
  Issue: `_ratio_summary()` thresholds `nat_w / stim_w` directly in [scripts/p3a_decide.py](</Users/johnd/ERRE-Sand Box/scripts/p3a_decide.py:365>). With `natural n=30` and `stimulus n=198`, equal per-sample variability predicts `~2.57x` raw natural width.
  Why it matters: ME-4 could select an alternative ratio because natural is under-sampled in P3a, not because natural has higher intrinsic uncertainty.
  Suggested fix: Keep raw ratio as descriptive only. Add `width * sqrt(n)` as per-sample variability proxy, and for the ADR decision add target-extrapolated widths: `width * sqrt(n / n_target)` with explicit targets, e.g. stimulus `200`, natural `300`. Any verdict should use the target-extrapolated ratio, or be renamed `raw_only_no_decision`.

- HIGH-2: Rikyu Burrows can abort whole cells
  Issue: `_PERSONA_LANGUAGE["rikyu"] = "ja"`, but Burrows rejects Japanese without pre-tokenized input. `_per_utterance_burrows()` only catches `BurrowsLanguageMismatchError` in [scripts/p3a_decide.py](</Users/johnd/ERRE-Sand Box/scripts/p3a_decide.py:127>), so `BurrowsTokenizationUnsupportedError` propagates to `main()` and turns the entire Rikyu cell into `"error"`, losing MATTR too.
  Why it matters: The ratio can be computed from Kant/Nietzsche only while appearing to represent 3 personas.
  Suggested fix: Catch `BurrowsTokenizationUnsupportedError` per utterance or pre-tokenize Japanese. Do not let Burrows failure skip MATTR. Also require `n_cells == 3` per condition for decision metrics.

- HIGH-3: Partial/empty/error cells still allow ratio output
  Issue: `main()` catches broad cell exceptions and continues in [scripts/p3a_decide.py](</Users/johnd/ERRE-Sand Box/scripts/p3a_decide.py:425>); `_mean_widths_by_condition()` averages whatever finite widths exist. A 0-utterance or failed cell can still leave enough data for a verdict.
  Why it matters: The G-GEAR receipt defines six clean cells; ME-4 should not be edited from a degraded subset.
  Suggested fix: Add a validation gate before `ratio_summary`: expected 6 cells, expected focal counts from `_summary.json` or hard-coded P3a floors, no cell `"error"`, and required lightweight metrics present for all expected cells. Otherwise emit `ratio_summary.skipped` and return nonzero.

## MEDIUM (fix before merge)
- MEDIUM-1: ADR close state needs to match deferred metrics
  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
  Why it matters: The workflow can falsely close ME-4 from Burrows+MATTR even though Vendi and Big5 ICC are the ADR metrics.
  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.

- MEDIUM-2: MATTR substitute needs stronger labeling
  Issue: MATTR is acceptable for this Mac session as a lightweight proxy, but it is not an ADR-equivalent substitute for Vendi + Big5 ICC.
  Why it matters: Burrows+MATTR may produce a different ratio than Burrows+Vendi+Big5.
  Suggested fix: Add an explicit `proxy_metrics` block and caveat: `lightweight_ratio_is_not_final_me4_ratio`.

- MEDIUM-3: Tests miss the decision-critical failures
  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
  Why it matters: The current bug profile is mostly integration/validation, not pure aggregation.
  Suggested fix: Add at least one synthetic DuckDB E2E test and one test proving ratio is skipped/fails when any expected cell or required metric is missing. Boundary/schema tests are cheap but secondary.

- MEDIUM-4: Optional heavy metric failures can erase lightweight results
  Issue: `_try_optional_metric()` catches only `ImportError`. If `[eval]` extras are installed but model load/runtime fails, the exception bubbles to `main()` and marks the whole cell as error.
  Why it matters: Optional diagnostics should not invalidate Burrows+MATTR finalization.
  Suggested fix: Catch broad exceptions inside optional metric calls and record `"skipped": "<ExceptionType>: ..."` for that optional metric only.

## LOW (defer / nice-to-have)
- LOW-1: `cells` top-level rename is justified
  Repo search found no `_p3a_decide.json` consumers, and `cells` is more accurate for persona × condition rows.

- LOW-2: `mean_combined_width` inside `by_condition` is acceptable
  It is close to its inputs. A top-level alias would only help future consumers.

- LOW-3: Keep `per_cell_widths` and `per_cell_n`
  They are useful audit fields for the ADR and help expose asymmetric `n`.

- LOW-4: Same bootstrap seed is fine
  Reusing `seed=0` per call does not bias widths because each call resamples its own input. A per-cell seed would only reduce shared Monte Carlo noise patterns.

## Confirmation (what looks right)
- DuckDB opens use `read_only=True`, satisfying the DB6 invariant.
- Missing file preflight exits nonzero and points to `_rsync_receipt.txt`.
- The “mean CI width が小さい比率” interpretation as a width ratio is defensible in context, though field names should stay explicit.
- Focused check passed: `uv run pytest tests/test_evidence/test_p3a_decide.py` → 7 passed.
- `_summary.json` and `_rsync_receipt.txt` consistently describe the six expected cells: natural focal `30`, stimulus focal `198`.

## Notes / open questions
- If ME-4’s decision is about the planned baseline ratio, use target-extrapolated widths. If it is about intrinsic per-sample variability, use `width * sqrt(n)`. The JSON should expose both to avoid another interpretation gap.
- The 10% threshold is acceptable as the ADR’s equivalence band only after normalization/extrapolation. It is not defensible on the raw ratio.
hook: Stop
hook: Stop Completed
2026-05-05T12:08:11.669817Z ERROR codex_core::session: failed to record rollout items: thread 019df805-d6b6-7351-9457-f84fb94a238f not found
tokens used
80,837
## Verdict
block — Current script can produce an ME-4 recommendation from raw, sample-size-confounded widths and can silently compute the ratio from partial cells.

## HIGH (fix before run)
- HIGH-1: Raw `natural / stimulus` CI width ratio is not decision-valid
  Issue: `_ratio_summary()` thresholds `nat_w / stim_w` directly in [scripts/p3a_decide.py](</Users/johnd/ERRE-Sand Box/scripts/p3a_decide.py:365>). With `natural n=30` and `stimulus n=198`, equal per-sample variability predicts `~2.57x` raw natural width.
  Why it matters: ME-4 could select an alternative ratio because natural is under-sampled in P3a, not because natural has higher intrinsic uncertainty.
  Suggested fix: Keep raw ratio as descriptive only. Add `width * sqrt(n)` as per-sample variability proxy, and for the ADR decision add target-extrapolated widths: `width * sqrt(n / n_target)` with explicit targets, e.g. stimulus `200`, natural `300`. Any verdict should use the target-extrapolated ratio, or be renamed `raw_only_no_decision`.

- HIGH-2: Rikyu Burrows can abort whole cells
  Issue: `_PERSONA_LANGUAGE["rikyu"] = "ja"`, but Burrows rejects Japanese without pre-tokenized input. `_per_utterance_burrows()` only catches `BurrowsLanguageMismatchError` in [scripts/p3a_decide.py](</Users/johnd/ERRE-Sand Box/scripts/p3a_decide.py:127>), so `BurrowsTokenizationUnsupportedError` propagates to `main()` and turns the entire Rikyu cell into `"error"`, losing MATTR too.
  Why it matters: The ratio can be computed from Kant/Nietzsche only while appearing to represent 3 personas.
  Suggested fix: Catch `BurrowsTokenizationUnsupportedError` per utterance or pre-tokenize Japanese. Do not let Burrows failure skip MATTR. Also require `n_cells == 3` per condition for decision metrics.

- HIGH-3: Partial/empty/error cells still allow ratio output
  Issue: `main()` catches broad cell exceptions and continues in [scripts/p3a_decide.py](</Users/johnd/ERRE-Sand Box/scripts/p3a_decide.py:425>); `_mean_widths_by_condition()` averages whatever finite widths exist. A 0-utterance or failed cell can still leave enough data for a verdict.
  Why it matters: The G-GEAR receipt defines six clean cells; ME-4 should not be edited from a degraded subset.
  Suggested fix: Add a validation gate before `ratio_summary`: expected 6 cells, expected focal counts from `_summary.json` or hard-coded P3a floors, no cell `"error"`, and required lightweight metrics present for all expected cells. Otherwise emit `ratio_summary.skipped` and return nonzero.

## MEDIUM (fix before merge)
- MEDIUM-1: ADR close state needs to match deferred metrics
  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
  Why it matters: The workflow can falsely close ME-4 from Burrows+MATTR even though Vendi and Big5 ICC are the ADR metrics.
  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.

- MEDIUM-2: MATTR substitute needs stronger labeling
  Issue: MATTR is acceptable for this Mac session as a lightweight proxy, but it is not an ADR-equivalent substitute for Vendi + Big5 ICC.
  Why it matters: Burrows+MATTR may produce a different ratio than Burrows+Vendi+Big5.
  Suggested fix: Add an explicit `proxy_metrics` block and caveat: `lightweight_ratio_is_not_final_me4_ratio`.

- MEDIUM-3: Tests miss the decision-critical failures
  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
  Why it matters: The current bug profile is mostly integration/validation, not pure aggregation.
  Suggested fix: Add at least one synthetic DuckDB E2E test and one test proving ratio is skipped/fails when any expected cell or required metric is missing. Boundary/schema tests are cheap but secondary.

- MEDIUM-4: Optional heavy metric failures can erase lightweight results
  Issue: `_try_optional_metric()` catches only `ImportError`. If `[eval]` extras are installed but model load/runtime fails, the exception bubbles to `main()` and marks the whole cell as error.
  Why it matters: Optional diagnostics should not invalidate Burrows+MATTR finalization.
  Suggested fix: Catch broad exceptions inside optional metric calls and record `"skipped": "<ExceptionType>: ..."` for that optional metric only.

## LOW (defer / nice-to-have)
- LOW-1: `cells` top-level rename is justified
  Repo search found no `_p3a_decide.json` consumers, and `cells` is more accurate for persona × condition rows.

- LOW-2: `mean_combined_width` inside `by_condition` is acceptable
  It is close to its inputs. A top-level alias would only help future consumers.

- LOW-3: Keep `per_cell_widths` and `per_cell_n`
  They are useful audit fields for the ADR and help expose asymmetric `n`.

- LOW-4: Same bootstrap seed is fine
  Reusing `seed=0` per call does not bias widths because each call resamples its own input. A per-cell seed would only reduce shared Monte Carlo noise patterns.

## Confirmation (what looks right)
- DuckDB opens use `read_only=True`, satisfying the DB6 invariant.
- Missing file preflight exits nonzero and points to `_rsync_receipt.txt`.
- The “mean CI width が小さい比率” interpretation as a width ratio is defensible in context, though field names should stay explicit.
- Focused check passed: `uv run pytest tests/test_evidence/test_p3a_decide.py` → 7 passed.
- `_summary.json` and `_rsync_receipt.txt` consistently describe the six expected cells: natural focal `30`, stimulus focal `198`.

## Notes / open questions
- If ME-4’s decision is about the planned baseline ratio, use target-extrapolated widths. If it is about intrinsic per-sample variability, use `width * sqrt(n)`. The JSON should expose both to avoid another interpretation gap.
- The 10% threshold is acceptable as the ADR’s equivalence band only after normalization/extrapolation. It is not defensible on the raw ratio.

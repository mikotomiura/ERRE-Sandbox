Reading prompt from stdin...
OpenAI Codex v0.128.0 (research preview)
--------
workdir: C:\ERRE-Sand_Box
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, C:\Users\johnd\.codex\memories]
reasoning effort: xhigh
reasoning summaries: none
session id: 019e3186-7034-7591-82af-9d18a236aa6e
--------
user
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

hook: SessionStart
hook: SessionStart Failed
hook: UserPromptSubmit
hook: UserPromptSubmit Failed
codex
I’ll treat this as a code-review task and use the repo workflow skill first, then inspect the PR-local changes and write the classified findings into the requested steering file. After that I’ll run the pre-push parity checks if the local environment supports them.
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw .agents/skills/source-command-review-changes/SKILL.md' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw .agents/skills/erre-workflow/SKILL.md' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw .agents/skills/project-status/SKILL.md' in C:\ERRE-Sand_Box
 succeeded in 475ms:
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

## Network Access Policy

The `.codex/config.toml` workspace_write sandbox defaults to `network_access = false`
(SH-3 ADR, 2026-05-13). Codex `web_search = "live"` is decoupled and stays enabled 窶・queries leave the box, but repo contents do not.

Do NOT toggle `network_access = true` without explicit per-session user approval.
If a task genuinely needs egress (e.g. `uv sync` for a fresh dependency), surface
the need to the user first and request a one-shot override via `--config
sandbox_workspace_write.network_access=true`. Do not commit a `true` value into
`.codex/config.toml`. See `AGENTS.md` "Network access policy" section.

## Review And Finish

Before final delivery:

- Run focused checks for touched areas.
- Run `uv run ruff check src tests`, `uv run ruff format --check src tests`,
  `uv run mypy src`, and `uv run pytest` when feasible.
- Review `git diff` for unrelated changes and do not revert user work.
- Update `tasklist.md` and `design.md` with what actually happened.
- Mention skipped checks or residual risk in the final response.

Do not commit unless the user asks. If committing, use `git-workflow`.


 succeeded in 470ms:
---
name: project-status
description: >
  繝励Ο繧ｸ繧ｧ繧ｯ繝医・迴ｾ蝨ｨ縺ｮ迥ｶ諷九ｒ繝ｪ繧｢繝ｫ繧ｿ繧､繝縺ｧ蜿門ｾ励☆繧九・  菴懈･ｭ繧貞ｧ九ａ繧句燕繝ｻ繧ｳ繝ｳ繝・く繧ｹ繝医′蛻・°繧峨↑縺上↑縺｣縺滓凾繝ｻ騾ｲ謐励ｒ遒ｺ隱阪＠縺溘＞譎ゅ・
  譛霑代・螟画峩繧呈滑謠｡縺励◆縺・凾縺ｫ菴ｿ縺・Ｈit 迥ｶ諷九・譛霑代・繧ｳ繝溘ャ繝医・
  讒狗ｯ峨ヵ繧ｧ繝ｼ繧ｺ縺ｮ騾ｲ謐・(.steering/_setup-progress.md)繝ｻ譛ｪ蟇ｾ蠢・TODO繝ｻ
  螟画峩繝輔ぃ繧､繝ｫ邨ｱ險医ｒ荳諡ｬ縺ｧ蜿門ｾ励☆繧九ゅそ繝・す繝ｧ繝ｳ髢句ｧ区凾縺ｮ迥ｶ豕∵滑謠｡縺ｫ繧ゆｽｿ縺医ｋ縲・---

# Project Status

縺薙・繧ｹ繧ｭ繝ｫ縺ｯ迴ｾ蝨ｨ縺ｮ繝励Ο繧ｸ繧ｧ繧ｯ繝育憾諷九ｒ蜍慕噪縺ｫ蜿門ｾ励＠縺ｾ縺吶・
## 迴ｾ蝨ｨ縺ｮ git 迥ｶ諷・
!`git status --short`

## 譛霑代・繧ｳ繝溘ャ繝・(10 莉ｶ)

!`git log --oneline -10 2>/dev/null || echo "(no commits yet)"`

## 迴ｾ蝨ｨ縺ｮ繝悶Λ繝ｳ繝・
!`git branch --show-current`

## 讒狗ｯ峨ヵ繧ｧ繝ｼ繧ｺ騾ｲ謐・
!`grep -E "^\- \[" .steering/_setup-progress.md 2>/dev/null | head -20 || echo "(progress file not found)"`

## 譛ｪ蟇ｾ蠢・TODO 縺ｮ謨ｰ

!`grep -r "TODO\|FIXME\|HACK\|XXX" src/ tests/ 2>/dev/null | wc -l`

## 螟画峩繝輔ぃ繧､繝ｫ縺ｮ邨ｱ險・(逶ｴ霑代さ繝溘ャ繝医→縺ｮ蟾ｮ蛻・

!`git diff --stat HEAD 2>/dev/null || echo "(no HEAD yet)"`

## 譛霑大､画峩縺輔ｌ縺溘ヵ繧｡繧､繝ｫ (24 譎る俣莉･蜀・

!`find src/ tests/ -name "*.py" -newer .git/index -mtime -1 2>/dev/null | head -10`

## Skills 繝・ぅ繝ｬ繧ｯ繝医Μ

!`ls .agents/skills/ 2>/dev/null || echo "(no skills yet)"`

## 縺ゅ↑縺溘・繧ｿ繧ｹ繧ｯ

荳願ｨ倥・蜍慕噪繝・・繧ｿ繧貞・譫舌＠縲∽ｻ･荳九ｒ蝣ｱ蜻翫＠縺ｦ縺上□縺輔＞:

1. **迴ｾ迥ｶ繧ｵ繝槭Μ** 窶・迴ｾ蝨ｨ縺ｮ繝輔ぉ繝ｼ繧ｺ縺ｨ騾ｲ謐励ｒ 1-2 陦後〒
2. **騾ｲ陦御ｸｭ縺ｮ菴懈･ｭ** 窶・譛ｪ繧ｳ繝溘ャ繝医・螟画峩繧・峩霑代・螟画峩繝輔ぃ繧､繝ｫ縺九ｉ菴輔′騾ｲ繧薙〒縺・ｋ縺・3. **豕ｨ諢上☆縺ｹ縺咲せ** 窶・螟壽焚縺ｮ譛ｪ繧ｳ繝溘ャ繝亥､画峩縲ゝODO 縺ｮ蛛上ｊ縲・ｲ謐励ヵ繧｡繧､繝ｫ縺ｨ縺ｮ荵夜屬縺ｪ縺ｩ
4. **謗ｨ螂ｨ縺輔ｌ繧区ｬ｡縺ｮ繧｢繧ｯ繧ｷ繝ｧ繝ｳ** 窶・菴輔ｒ蜆ｪ蜈医☆縺ｹ縺阪° (setup 繝輔ぉ繝ｼ繧ｺ縺ｧ縺ゅｌ縺ｰ縺ｩ縺ｮ繧ｳ繝槭Φ繝峨ｒ谺｡縺ｫ螳溯｡後☆縺ｹ縺阪°)

繝ｬ繝昴・繝医・邁｡貎斐↓縲りｩｳ邏ｰ縺ｯ蠢・ｦ√↓蠢懊§縺ｦ繝ｦ繝ｼ繧ｶ繝ｼ縺瑚ｿｽ蜉縺ｧ雉ｪ蝠上☆繧九・

 succeeded in 480ms:
---
name: "source-command-review-changes"
description: "逶ｴ霑代・ git 螟画峩繧貞､夊ｧ堤噪縺ｫ繝ｬ繝薙Η繝ｼ縺吶ｋ縲Ｄode-reviewer 縺ｨ security-checker 繧・襍ｷ蜍輔＠縲∫ｵ先棡繧堤ｵｱ蜷医＠縺ｦ蝣ｱ蜻翫☆繧九ゅさ繝溘ャ繝亥燕縲￣R 菴懈・蜑阪↓螳溯｡後☆繧九・
---

# source-command-review-changes

Use this skill when the user asks to run the migrated source command `review-changes`.

## Command Template

# /review-changes

## 迴ｾ蝨ｨ縺ｮ迥ｶ豕・
$SHELL_PREPROCESS: git status --short 2>/dev/null || echo "(git 邂｡逅・､・"

## 螟画峩邨ｱ險・
$SHELL_PREPROCESS: git diff --stat HEAD 2>/dev/null || echo "(螟画峩縺ｪ縺・"

## 螳溯｡後ヵ繝ｭ繝ｼ

### Step 1: 螟画峩縺ｮ譛臥┌遒ｺ隱・
荳願ｨ倥・蜍慕噪繝・・繧ｿ縺九ｉ螟画峩繧堤｢ｺ隱阪ょ､画峩縺後↑縺・ｴ蜷医・荳ｭ譁ｭ:

> 縲悟､画峩縺後≠繧翫∪縺帙ｓ縲ゅΞ繝薙Η繝ｼ蟇ｾ雎｡縺後↑縺・◆繧∫ｵゆｺ・＠縺ｾ縺吶ゅ・
### Step 2: code-reviewer 縺ｮ襍ｷ蜍・
`code-reviewer` 繧ｵ繝悶お繝ｼ繧ｸ繧ｧ繝ｳ繝医ｒ襍ｷ蜍・

> Task: code-reviewer 縺ｧ逶ｴ霑代・ git diff 繧偵Ξ繝薙Η繝ｼ縲・IGH/MEDIUM 縺ｮ謖・遭繧貞━蜈育噪縺ｫ縲・
### Step 3: security-checker 縺ｮ襍ｷ蜍・
螟夜Κ蜈･蜉帙ｒ謇ｱ縺・､画峩繧・∬ｪ崎ｨｼ/隱榊庄縺ｫ髢｢繧上ｋ螟画峩縺後≠繧句ｴ蜷医～security-checker` 繧定ｵｷ蜍・

> Task: security-checker 縺ｧ螟画峩蜀・ｮｹ縺ｮ繧ｻ繧ｭ繝･繝ｪ繝・ぅ繝ｪ繧ｹ繧ｯ繧定ｪｿ譟ｻ縲・
### Step 4: 邨先棡縺ｮ邨ｱ蜷・
荳｡繧ｨ繝ｼ繧ｸ繧ｧ繝ｳ繝医°繧峨・繝ｬ繝昴・繝医ｒ邨ｱ蜷医＠縲∽ｻ･荳九・蠖｢蠑上〒陦ｨ遉ｺ:

```markdown
## 螟画峩繝ｬ繝薙Η繝ｼ邨先棡

### 螟画峩讎りｦ・- 螟画峩繝輔ぃ繧､繝ｫ謨ｰ: N
- 霑ｽ蜉陦梧焚: +N
- 蜑企勁陦梧焚: -N

### CRITICAL/HIGH・亥ｿ・亥ｯｾ蠢懶ｼ・[邨ｱ蜷医＠縺滓欠鞫肋

### MEDIUM・域耳螂ｨ蟇ｾ蠢懶ｼ・[邨ｱ蜷医＠縺滓欠鞫肋

### LOW・井ｻｻ諢丞ｯｾ蠢懶ｼ・[邨ｱ蜷医＠縺滓欠鞫肋

### 濶ｯ縺九▲縺溽せ
[code-reviewer 縺瑚ｩ穂ｾ｡縺励◆轤ｹ]
```

### Step 5: 繝ｦ繝ｼ繧ｶ繝ｼ縺ｸ縺ｮ謠先｡・
- CRITICAL/HIGH 縺後≠繧後・: 縲後％繧後ｉ繧剃ｿｮ豁｣縺励※縺九ｉ commit 縺励※縺上□縺輔＞縲・- 縺ｪ縺代ｌ縺ｰ: 縲慶ommit 縺励※蝠城｡後≠繧翫∪縺帙ｓ縲・
## 蛻ｶ邏・
- 蜈ｨ繝ｬ繝昴・繝医ｒ逕溘〒豬√＆縺ｪ縺・ｼ育ｵｱ蜷医・隕∫ｴ・☆繧具ｼ・- 驥崎ｦ√↑謖・遭繧定ｦ玖誠縺ｨ縺輔↑縺・- 縲悟撫鬘後↑縺励阪〒邨ゅｏ繧峨○繧句ｴ蜷医ｂ逅・罰繧定ｿｰ縺ｹ繧・

codex
The review skill references subagents for the migrated `/review-changes` command, but this request asks for an independent Codex review rather than delegated parallel review, so I’ll keep the review local and use the required steering output file.
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git branch --show-current' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff --stat HEAD' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git log --oneline -10' in C:\ERRE-Sand_Box
 succeeded in 294ms:
 M scripts/m9-c-adopt/rescore_vendi_alt_kernel.py
?? .agents/skills/source-command-add-feature/
?? .agents/skills/source-command-commands-setup-bootstrap/
?? .agents/skills/source-command-commands-setup-setup-docs/
?? .agents/skills/source-command-finish-task/
?? .agents/skills/source-command-fix-bug/
?? .agents/skills/source-command-refactor/
?? .agents/skills/source-command-reimagine/
?? .agents/skills/source-command-review-changes/
?? .agents/skills/source-command-smart-compact/
?? .agents/skills/source-command-start-task/
?? .codex/agents/build-executor.toml
?? .codex/agents/code-reviewer.toml
?? .codex/agents/dependency-checker.toml
?? .codex/agents/file-finder.toml
?? .codex/agents/impact-analyzer.toml
?? .codex/agents/log-analyzer.toml
?? .codex/agents/security-checker.toml
?? .codex/agents/test-analyzer.toml
?? .codex/agents/test-runner.toml
?? .steering/20260509-m9-individual-layer-schema-add/codex-review.stderr
?? .steering/20260509-m9-individual-layer-schema-add/next-session-prompt-phase-c-2.md
?? .steering/20260509-m9-individual-layer-schema-add/next-session-prompt-phase-c-3.md
?? .steering/20260509-m9-individual-layer-schema-add/next-session-prompt-phase-c-4.md
?? .steering/20260509-m9-individual-layer-schema-add/next-session-prompt-phase-c-5.md
?? .steering/20260509-m9-individual-layer-schema-add/next-session-prompt.md
?? .steering/20260514-m9-c-adopt-pilot-multiturn/next-session-prompt-FINAL.md
?? .steering/20260514-m9-c-adopt-retrain-v2-design/next-session-prompt-FINAL.md
?? .steering/20260516-m9-c-adopt-da15-impl/next-session-prompt-FINAL-plan-b.md
?? .steering/20260516-m9-c-adopt-plan-b-eval-gen/
?? .steering/20260517-m9-c-adopt-plan-b-design/next-session-prompt-FINAL-retrain.md
?? data/eval/calibration/run1/_checksums_run1_partial.txt
?? data/eval/m9-c-adopt-plan-b-verdict/
?? data/eval/partial/
?? scripts/m9-c-adopt/aggregate_plan_b_axes.py
?? scripts/m9-c-adopt/da14_verdict_plan_b.py
?? scripts/m9-c-adopt/launch_sglang_plan_b.sh
?? scripts/m9-c-adopt/run_plan_b_eval_sequence.sh
?? scripts/m9-c-adopt/run_plan_b_post_eval.sh
?? tests/test_scripts/

 succeeded in 300ms:
feature/m9-c-adopt-plan-b-eval-gen

 succeeded in 314ms:
858cadc Merge pull request #183 from mikotomiura:feature/m9-c-adopt-plan-b-verdict
b6143f3 docs(steering): m9-c-adopt Plan B verdict prep — eval-shard blocker 1 surfaced + handoff prompt + Windows symlink test skip
7f944dc Merge pull request #182 from mikotomiura/ERRE-Sandbox:chore/plan-b-next-session-prompt-post-merge
21c2bd4 docs(steering): m9-c-adopt Plan B next-session prompt — post-merge update (eval_loss trajectory + merge SHA)
f68ac63 Merge pull request #181 from mikotomiura:feature/m9-c-adopt-plan-b-retrain
b52ce1f chore(workflow): add pre-push CI-parity check + memory feedback (PR #181 reflection)
a5faef1 fix(ci): m9-c-adopt Plan B — sklearn missing in CI default profile
2a79ef6 docs(steering): m9-c-adopt Plan B retrain — session-end (DR-7) + next-session verdict prompt
227055b chore(plan-b): m9-c-adopt Plan B retrain — collection manifests + corpus gate PASS + lang-stratified train-time gate
e15979f perf(training): m9-c-adopt Plan B retrain — WeightedTrainer.compute_loss pop labels + prediction_loss_only=True (DR-5 / DR-6)

 succeeded in 318ms:
 scripts/m9-c-adopt/rescore_vendi_alt_kernel.py | 285 ++++++++++++++++++++-----
 1 file changed, 230 insertions(+), 55 deletions(-)

codex
The branch is `feature/m9-c-adopt-plan-b-eval-gen`. The working tree has one tracked script diff plus several untracked PR files, so I’m going to review the working tree against `HEAD`, including untracked files that are part of the eval-gen surface.
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg --files .steering/20260516-m9-c-adopt-plan-b-eval-gen .steering/20260517-m9-c-adopt-plan-b-design .steering/20260518-m9-c-adopt-plan-b-retrain scripts/m9-c-adopt tests/test_scripts data/eval/m9-c-adopt-plan-b-verdict' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff -- scripts/m9-c-adopt/rescore_vendi_alt_kernel.py' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-ChildItem -Recurse -File .steering/20260516-m9-c-adopt-plan-b-eval-gen | Select-Object FullName,Length' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-ChildItem -Recurse -File data/eval/m9-c-adopt-plan-b-verdict | Select-Object FullName,Length' in C:\ERRE-Sand_Box
 succeeded in 355ms:
diff --git a/scripts/m9-c-adopt/rescore_vendi_alt_kernel.py b/scripts/m9-c-adopt/rescore_vendi_alt_kernel.py
index cf53b05..8c74048 100644
--- a/scripts/m9-c-adopt/rescore_vendi_alt_kernel.py
+++ b/scripts/m9-c-adopt/rescore_vendi_alt_kernel.py
@@ -74,9 +74,18 @@ _E5_PASSAGE_PREFIX: str = "passage: "
 _D2_ALLOWLIST_PATH = Path(
     ".steering/20260516-m9-c-adopt-da15-impl/d2-encoder-allowlist.json",
 )
+"""Default D-2 allowlist (Plan A). Plan B verdict passes
+``--allowlist-path .steering/20260517-m9-c-adopt-plan-b-design/
+d2-encoder-allowlist-plan-b.json`` to opt-in to the 4-encoder
+agreement panel."""
 
+_LEXICAL_5GRAM_ENCODER_KEY: str = "lexical_5gram"
+"""Sentinel encoder name for the lexical-5gram (TF-IDF char-5-gram cosine)
+kernel. Matches the D-2 allowlist (Plan B) key and bypasses the
+SentenceTransformer code path."""
 
-def _load_allowlist() -> dict[str, Any]:
+
+def _load_allowlist(path: Path = _D2_ALLOWLIST_PATH) -> dict[str, Any]:
     """Load the D-2 pre-registration allowlist (Codex HIGH-1 enforcement).
 
     Calibration and rescore scripts refuse to run on encoders that are not
@@ -84,19 +93,17 @@ def _load_allowlist() -> dict[str, Any]:
     ``SentenceTransformer`` so the run cannot accidentally pick up a
     different snapshot from the local cache.
     """
-    if not _D2_ALLOWLIST_PATH.exists():
-        msg = f"D-2 allowlist missing: {_D2_ALLOWLIST_PATH}"
+    if not path.exists():
+        msg = f"D-2 allowlist missing: {path}"
         raise FileNotFoundError(msg)
-    return json.loads(_D2_ALLOWLIST_PATH.read_text(encoding="utf-8"))
+    return json.loads(path.read_text(encoding="utf-8"))
 
 
 def _local_revision_sha(encoder_name: str) -> str | None:
     """Read the locally-cached HF snapshot SHA. Works offline."""
     safe = encoder_name.replace("/", "--")
     base = (
-        Path.home()
-        / ".cache" / "huggingface" / "hub"
-        / f"models--{safe}" / "snapshots"
+        Path.home() / ".cache" / "huggingface" / "hub" / f"models--{safe}" / "snapshots"
     )
     if not base.exists():
         return None
@@ -127,7 +134,9 @@ def _load_focal_utterances(shard: Path, persona_id: str) -> list[str]:
 
 
 def _encode_pool(
-    encoder_name: str, revision: str, texts: list[str],
+    encoder_name: str,
+    revision: str,
+    texts: list[str],
 ) -> np.ndarray:
     """Encode every utterance once and return unit-norm row embeddings.
 
@@ -145,12 +154,59 @@ def _encode_pool(
     inputs = [(_E5_PASSAGE_PREFIX + t) if needs_e5_prefix else t for t in texts]
     logger.info("encoding %d utterances…", len(inputs))
     raw = np.asarray(
-        model.encode(inputs, show_progress_bar=False), dtype=float,
+        model.encode(inputs, show_progress_bar=False),
+        dtype=float,
     )
     norms = np.linalg.norm(raw, axis=1, keepdims=True)
     return raw / np.where(norms == 0, 1.0, norms)
 
 
+def _encode_pools_lexical_5gram(
+    v2_texts: list[str],
+    nolora_texts: list[str],
+) -> tuple[np.ndarray, np.ndarray]:
+    """Pool-fit TF-IDF char 5-gram encoding for the Plan B lexical kernel.
+
+    Returns ``(v2_unit, nolora_unit)`` — both unit-l2-normalized so that
+    ``unit @ unit.T`` recovers cosine similarity for the natural / bootstrap
+    window scoring path used by the semantic encoders.
+
+    DE-1 design rationale (see ``.steering/20260516-m9-c-adopt-plan-b-eval-
+    gen/design.md`` §7): fit ``TfidfVectorizer`` once on the merged pool so
+    both conditions share the same IDF basis (apples-to-apples). This
+    deviates from ``vendi_lexical_5gram.make_tfidf_5gram_cosine_kernel``'s
+    per-window fit, but mirrors the semantic pre-compute-once pattern used
+    by ``_encode_pool``: window slices are taken from a single, condition-
+    agnostic embedding space rather than re-fit per resample.
+    """
+    from sklearn.feature_extraction.text import (  # noqa: PLC0415
+        TfidfVectorizer,
+    )
+
+    n_v2 = len(v2_texts)
+    n_nolora = len(nolora_texts)
+    cleaned = [str(t) if str(t).strip() else " " for t in (v2_texts + nolora_texts)]
+    logger.info(
+        "lexical_5gram pool-fit: v2=%d nolora=%d merged=%d",
+        n_v2,
+        n_nolora,
+        len(cleaned),
+    )
+    vectorizer = TfidfVectorizer(
+        analyzer="char_wb",
+        ngram_range=(5, 5),
+        lowercase=True,
+        norm="l2",
+        sublinear_tf=False,
+    )
+    tfidf = vectorizer.fit_transform(cleaned).toarray().astype(float, copy=False)
+    # TfidfVectorizer(norm="l2") already l2-normalises rows, but re-clamp
+    # numerical drift so cosine via raw matmul is exact on the diagonal.
+    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
+    unit = tfidf / np.where(norms == 0, 1.0, norms)
+    return unit[:n_v2], unit[n_v2:]
+
+
 def _vendi_from_unit_embeddings(unit: np.ndarray, indices: np.ndarray) -> float:
     """Pull rows from the pre-normalised embedding matrix and Vendi-score them."""
     slice_ = unit[indices]
@@ -186,7 +242,11 @@ def _cohens_d(a: list[float], b: list[float]) -> float:
 
 
 def _bootstrap_window_diff_ci(
-    a: list[float], b: list[float], *, seed: int, n_resamples: int,
+    a: list[float],
+    b: list[float],
+    *,
+    seed: int,
+    n_resamples: int,
 ) -> dict[str, Any]:
     """Window-level bootstrap of the mean difference (a − b).
 
@@ -257,8 +317,12 @@ def _stratified_bootstrap_d(
         v2_idx_list: list[int] = []
         nolora_idx_list: list[int] = []
         for s in eligible:
-            v2_idx_list.extend(int(i) for i in rng.choice(v2_by[s], size=per_quota, replace=True))
-            nolora_idx_list.extend(int(i) for i in rng.choice(nolora_by[s], size=per_quota, replace=True))
+            v2_idx_list.extend(
+                int(i) for i in rng.choice(v2_by[s], size=per_quota, replace=True)
+            )
+            nolora_idx_list.extend(
+                int(i) for i in rng.choice(nolora_by[s], size=per_quota, replace=True)
+            )
         # Top-up: fill any remainder from a randomly chosen eligible stratum.
         while len(v2_idx_list) < window_size:
             s = eligible[int(rng.integers(0, len(eligible)))]
@@ -299,16 +363,41 @@ def _length_quartile(length: int, thresholds: tuple[int, int, int]) -> str:
     return "q4"
 
 
-def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
+def _resolve_encoder_default(args: argparse.Namespace) -> None:
+    """Apply post-parse defaulting + kernel_type/encoder cross-validation.
+
+    Split from ``main`` so unit tests can drive the same logic without
+    triggering DuckDB shard loading.
+    """
+    if args.kernel_type == "lexical_5gram":
+        if args.encoder is None:
+            args.encoder = _LEXICAL_5GRAM_ENCODER_KEY
+        elif args.encoder != _LEXICAL_5GRAM_ENCODER_KEY:
+            msg = (
+                f"--encoder must be {_LEXICAL_5GRAM_ENCODER_KEY!r} (or"
+                " omitted) when --kernel-type lexical_5gram; got"
+                f" {args.encoder!r}"
+            )
+            raise SystemExit(msg)
+    elif args.encoder is None:
+        raise SystemExit(
+            "--encoder is required for --kernel-type semantic (Plan A path)",
+        )
+
+
+def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915, C901, PLR0912
     p = argparse.ArgumentParser(prog="m9-c-adopt-da15-rescore")
     p.add_argument(
         "--encoder",
-        required=True,
+        default=None,
         help=(
             "HuggingFace model id. Plan A primary candidates are"
             " 'intfloat/multilingual-e5-large' and 'BAAI/bge-m3'. Pass"
             " 'sentence-transformers/all-mpnet-base-v2' to reproduce the"
             " DA-14 MPNet regression baseline under the same code path."
+            " Required for --kernel-type semantic; defaults to"
+            f" {_LEXICAL_5GRAM_ENCODER_KEY!r} when --kernel-type"
+            " lexical_5gram."
         ),
     )
     p.add_argument("--persona", default="kant", choices=("kant",))
@@ -327,9 +416,56 @@ def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
     p.add_argument("--seed", type=int, default=42)
     p.add_argument("--output", required=True, type=Path)
     p.add_argument(
-        "--log-level", default="info", choices=("debug", "info", "warning", "error"),
+        "--log-level",
+        default="info",
+        choices=("debug", "info", "warning", "error"),
+    )
+    p.add_argument(
+        "--v2-shards",
+        nargs="+",
+        type=Path,
+        default=list(_V2_SHARDS),
+        help=(
+            "DuckDB shard paths for the LoRA-on (v2 or Plan B) condition."
+            " Defaults to the Plan A v2 baseline (kant_r8v2_run{0,1}); pass"
+            " Plan B kant_r8v3 shards to score the Plan B retrain artifact."
+        ),
+    )
+    p.add_argument(
+        "--nolora-shards",
+        nargs="+",
+        type=Path,
+        default=list(_NOLORA_SHARDS),
+        help=(
+            "DuckDB shard paths for the no-LoRA control condition. Defaults"
+            " to the existing kant_nolora_run{0,1} SGLang baseline; pass the"
+            " Plan B no-LoRA control shards (kant_planb_nolora_run{0,1}) for"
+            " Plan B verdict apples-to-apples."
+        ),
+    )
+    p.add_argument(
+        "--kernel-type",
+        choices=("semantic", "lexical_5gram"),
+        default="semantic",
+        help=(
+            "Vendi kernel family. 'semantic' uses the SentenceTransformer"
+            " path (MPNet / E5 / BGE-M3). 'lexical_5gram' uses the Plan B"
+            " D-2 primary TF-IDF char-5-gram cosine kernel (pool-fit, see"
+            " DE-1 in design.md)."
+        ),
+    )
+    p.add_argument(
+        "--allowlist-path",
+        type=Path,
+        default=_D2_ALLOWLIST_PATH,
+        help=(
+            "Path to the D-2 allowlist JSON. Default is the Plan A allowlist"
+            f" ({_D2_ALLOWLIST_PATH}); pass the Plan B allowlist for the"
+            " 4-encoder agreement panel (encoder_agreement_axis)."
+        ),
     )
     args = p.parse_args(argv)
+    _resolve_encoder_default(args)
 
     logging.basicConfig(
         level=args.log_level.upper(),
@@ -340,59 +476,71 @@ def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
     # === Load + concatenate per-condition pools ===
     v2_utterances: list[str] = []
     v2_utt_per_shard: list[int] = []
-    for shard in _V2_SHARDS:
+    for shard in args.v2_shards:
         ut = _load_focal_utterances(shard, args.persona)
         v2_utterances.extend(ut)
         v2_utt_per_shard.append(len(ut))
 
     nolora_utterances: list[str] = []
     nolora_utt_per_shard: list[int] = []
-    for shard in _NOLORA_SHARDS:
+    for shard in args.nolora_shards:
         ut = _load_focal_utterances(shard, args.persona)
         nolora_utterances.extend(ut)
         nolora_utt_per_shard.append(len(ut))
 
     logger.info(
         "v2 utterances=%d nolora utterances=%d",
-        len(v2_utterances), len(nolora_utterances),
+        len(v2_utterances),
+        len(nolora_utterances),
     )
 
     # === D-2 allowlist enforcement (Codex HIGH-1) ===
-    allowlist = _load_allowlist()
+    allowlist = _load_allowlist(args.allowlist_path)
     if args.encoder not in allowlist["encoders"]:
         msg = (
             f"encoder {args.encoder!r} is not in the D-2 allowlist"
             f" ({sorted(allowlist['encoders'])}). Add the encoder to"
-            f" {_D2_ALLOWLIST_PATH} with a revision SHA and a role before"
+            f" {args.allowlist_path} with a revision SHA and a role before"
             " rerunning."
         )
         raise SystemExit(msg)
     pinned = allowlist["encoders"][args.encoder]
     revision = pinned["revision_sha"]
     role = pinned["role"]
-    local_sha = _local_revision_sha(args.encoder)
-    if local_sha and local_sha != revision:
-        logger.warning(
-            "local cache snapshot %s differs from pinned %s — passing pinned"
-            " revision to SentenceTransformer to force the right snapshot",
-            local_sha, revision,
-        )
+    if args.kernel_type == "semantic":
+        local_sha = _local_revision_sha(args.encoder)
+        if local_sha and local_sha != revision:
+            logger.warning(
+                "local cache snapshot %s differs from pinned %s — passing pinned"
+                " revision to SentenceTransformer to force the right snapshot",
+                local_sha,
+                revision,
+            )
 
     # === Encode each pool once (the only expensive call) ===
-    v2_unit = _encode_pool(args.encoder, revision, v2_utterances)
-    nolora_unit = _encode_pool(args.encoder, revision, nolora_utterances)
+    if args.kernel_type == "lexical_5gram":
+        v2_unit, nolora_unit = _encode_pools_lexical_5gram(
+            v2_utterances,
+            nolora_utterances,
+        )
+    else:
+        v2_unit = _encode_pool(args.encoder, revision, v2_utterances)
+        nolora_unit = _encode_pool(args.encoder, revision, nolora_utterances)
 
     # === Natural per-window scores ===
     v2_window_scores = _natural_window_scores(v2_unit, v2_utt_per_shard)
     nolora_window_scores = _natural_window_scores(nolora_unit, nolora_utt_per_shard)
     logger.info(
         "natural windows: v2=%d nolora=%d",
-        len(v2_window_scores), len(nolora_window_scores),
+        len(v2_window_scores),
+        len(nolora_window_scores),
     )
 
     standard = _bootstrap_window_diff_ci(
-        v2_window_scores, nolora_window_scores,
-        seed=args.seed, n_resamples=args.n_resamples,
+        v2_window_scores,
+        nolora_window_scores,
+        seed=args.seed,
+        n_resamples=args.n_resamples,
     )
 
     # === Strata ===
@@ -413,20 +561,26 @@ def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
 
     logger.info("running language-balanced bootstrap…")
     lang_balanced = _stratified_bootstrap_d(
-        v2_unit=v2_unit, nolora_unit=nolora_unit,
-        v2_strata=v2_langs, nolora_strata=nolora_langs,
+        v2_unit=v2_unit,
+        nolora_unit=nolora_unit,
+        v2_strata=v2_langs,
+        nolora_strata=nolora_langs,
         eligible_strata=["de", "en"],
         window_size=args.window_size,
-        n_resamples=args.balanced_n_resamples, seed=args.seed,
+        n_resamples=args.balanced_n_resamples,
+        seed=args.seed,
     )
 
     logger.info("running length-balanced bootstrap…")
     length_balanced = _stratified_bootstrap_d(
-        v2_unit=v2_unit, nolora_unit=nolora_unit,
-        v2_strata=v2_quartiles, nolora_strata=nolora_quartiles,
+        v2_unit=v2_unit,
+        nolora_unit=nolora_unit,
+        v2_strata=v2_quartiles,
+        nolora_strata=nolora_quartiles,
         eligible_strata=["q1", "q2", "q3", "q4"],
         window_size=args.window_size,
-        n_resamples=args.balanced_n_resamples, seed=args.seed,
+        n_resamples=args.balanced_n_resamples,
+        seed=args.seed,
     )
 
     logger.info("running within-language d…")
@@ -447,11 +601,14 @@ def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
             }
             continue
         within_lang[lang] = _stratified_bootstrap_d(
-            v2_unit=v2_unit, nolora_unit=nolora_unit,
-            v2_strata=v2_langs, nolora_strata=nolora_langs,
+            v2_unit=v2_unit,
+            nolora_unit=nolora_unit,
+            v2_strata=v2_langs,
+            nolora_strata=nolora_langs,
             eligible_strata=[lang],
             window_size=args.window_size,
-            n_resamples=args.balanced_n_resamples, seed=args.seed,
+            n_resamples=args.balanced_n_resamples,
+            seed=args.seed,
         )
 
     # === DA-14 threshold check (unchanged) ===
@@ -472,41 +629,58 @@ def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
     # === Runtime environment record (pre-registration audit) ===
     # Library versions and the pinned revision come from the D-2 allowlist;
     # we no longer call HfApi at runtime so the script is offline-safe.
-    import sentence_transformers as _st  # noqa: PLC0415
     import transformers as _tf  # noqa: PLC0415
 
     revision_sha = revision
-    library_versions = {
-        "sentence_transformers": _st.__version__,
+    library_versions: dict[str, str] = {
         "transformers": _tf.__version__,
     }
+    if args.kernel_type == "semantic":
+        import sentence_transformers as _st  # noqa: PLC0415
+
+        library_versions["sentence_transformers"] = _st.__version__
+    else:
+        import sklearn as _sk  # noqa: PLC0415
+
+        library_versions["sklearn"] = _sk.__version__
     expected_lib = allowlist.get("library_versions", {})
+    # Only enforce overlap (kernel-relevant libs). lexical_5gram skips the
+    # sentence_transformers pin since the kernel is computed via sklearn
+    # TF-IDF; the allowlist does not pin sklearn yet.
+    relevant_keys = set(expected_lib).intersection(library_versions)
     library_versions_match = all(
-        library_versions.get(k) == v for k, v in expected_lib.items()
+        library_versions[k] == expected_lib[k] for k in relevant_keys
     )
 
+    if args.kernel_type == "lexical_5gram":
+        metric_name = "vendi_lexical_5gram"
+    else:
+        metric_name = "vendi_semantic_v2_encoder_swap"
+
     payload: dict[str, Any] = {
         "encoder": args.encoder,
         "encoder_revision_sha": revision_sha,
         "encoder_role": role,
+        "kernel_type": args.kernel_type,
+        "allowlist_path": str(args.allowlist_path),
         "library_versions": library_versions,
         "library_versions_match_d2": library_versions_match,
         "preregistration_anchor": (
-            "DA-15 D-2 (.steering/20260516-m9-c-adopt-da15-impl/decisions.md"
-            " + d2-encoder-allowlist.json). Encoder + revision SHA + library"
-            " versions must match the pinned values for the verdict to count"
-            " as ADOPT-eligible. ``encoder_role`` decides whether this run can"
-            " contribute to the primary ADOPT panel (``primary``) or only"
-            " serves as the DA-14 regression baseline (``regression``)."
+            "DA-15 D-2 / Plan B D-2 allowlist. Encoder + revision SHA +"
+            " library versions must match the pinned values for the verdict"
+            " to count as ADOPT-eligible. ``encoder_role`` decides whether"
+            " this run can contribute to the primary ADOPT panel"
+            " (``primary``) or only serves as a regression baseline"
+            " (``regression``) / exploratory channel (``exploratory``)."
         ),
         "persona": args.persona,
-        "metric": "vendi_semantic_v2_encoder_swap",
+        "metric": metric_name,
         "window_size": args.window_size,
         "n_resamples": args.n_resamples,
         "balanced_n_resamples": args.balanced_n_resamples,
         "seed": args.seed,
-        "v2_shards": [s.name for s in _V2_SHARDS],
-        "nolora_shards": [s.name for s in _NOLORA_SHARDS],
+        "v2_shards": [s.name for s in args.v2_shards],
+        "nolora_shards": [s.name for s in args.nolora_shards],
         "natural_windows": {
             "v2_scores": v2_window_scores,
             "nolora_scores": nolora_window_scores,
@@ -533,7 +707,8 @@ def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
 
     args.output.parent.mkdir(parents=True, exist_ok=True)
     args.output.write_text(
-        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8",
+        json.dumps(payload, indent=2, ensure_ascii=False),
+        encoding="utf-8",
     )
     logger.info(
         "encoder=%s natural cohens_d=%.4f standard_pass=%s output=%s",

 succeeded in 408ms:

FullName                                                                                 Length
--------                                                                                 ------
C:\ERRE-Sand_Box\data\eval\m9-c-adopt-plan-b-verdict\kant_planb_nolora_run0_stim.duckdb 1323008
C:\ERRE-Sand_Box\data\eval\m9-c-adopt-plan-b-verdict\kant_planb_nolora_run1_stim.duckdb 1323008
C:\ERRE-Sand_Box\data\eval\m9-c-adopt-plan-b-verdict\kant_r8v3_run0_stim.duckdb         1323008
C:\ERRE-Sand_Box\data\eval\m9-c-adopt-plan-b-verdict\kant_r8v3_run1_stim.duckdb         1323008



 succeeded in 412ms:

FullName                                                                                                    Length
--------                                                                                                    ------
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\blockers.md                                    3575
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md                         6431
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md                                  29
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-burrows-plan-b-kant.json                   503
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-icc-plan-b-kant.json                       369
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json            4201
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json          4215
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json             4112
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json            4216
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-throughput-plan-b-kant.json                516
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-verdict-plan-b-kant.json                  4363
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-verdict-plan-b-kant.md                    2026
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\decisions.md                                  12633
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md                                     14018
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log                              8551
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\pr-body-draft.md                               2337
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\requirement.md                                 6622
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\tasklist.md                                    4545
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json  11906
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-r8v3-burrows.json          12091
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-r8v3-icc.json               3540
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\validation-kant-planb-nolora.json              2343
C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\validation-kant-r8v3.json                      2327



 succeeded in 588ms:
data/eval/m9-c-adopt-plan-b-verdict\kant_r8v3_run1_stim.duckdb
data/eval/m9-c-adopt-plan-b-verdict\kant_r8v3_run0_stim.duckdb
data/eval/m9-c-adopt-plan-b-verdict\kant_planb_nolora_run1_stim.duckdb
data/eval/m9-c-adopt-plan-b-verdict\kant_planb_nolora_run0_stim.duckdb
.steering/20260518-m9-c-adopt-plan-b-retrain\design.md
.steering/20260518-m9-c-adopt-plan-b-retrain\decisions.md
.steering/20260518-m9-c-adopt-plan-b-retrain\blockers.md
.steering/20260518-m9-c-adopt-plan-b-retrain\validation-plan-b-shards.json
.steering/20260518-m9-c-adopt-plan-b-retrain\validation-plan-b-shards-final.json
.steering/20260518-m9-c-adopt-plan-b-retrain\tasklist.md
.steering/20260518-m9-c-adopt-plan-b-retrain\requirement.md
.steering/20260518-m9-c-adopt-plan-b-retrain\next-session-prompt-FINAL-verdict.md
.steering/20260516-m9-c-adopt-plan-b-eval-gen\blockers.md
tests/test_scripts\__init__.py
tests/test_scripts\test_rescore_vendi_alt_kernel_cli.py
.steering/20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\da14-icc-plan-b-kant.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\da14-burrows-plan-b-kant.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md
.steering/20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md
.steering/20260516-m9-c-adopt-plan-b-eval-gen\da14-verdict-plan-b-kant.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\da14-throughput-plan-b-kant.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\decisions.md
.steering/20260516-m9-c-adopt-plan-b-eval-gen\da14-verdict-plan-b-kant.md
.steering/20260516-m9-c-adopt-plan-b-eval-gen\design.md
.steering/20260518-m9-c-adopt-plan-b-retrain\artifacts\weight-audit-final.json
.steering/20260517-m9-c-adopt-plan-b-design\tasklist.md
.steering/20260518-m9-c-adopt-plan-b-retrain\artifacts\smoke_manifest.json
.steering/20260518-m9-c-adopt-plan-b-retrain\artifacts\run2_manifest.json
.steering/20260518-m9-c-adopt-plan-b-retrain\artifacts\run1_manifest.json
.steering/20260518-m9-c-adopt-plan-b-retrain\artifacts\run0_manifest.json
.steering/20260518-m9-c-adopt-plan-b-retrain\artifacts\plan-b-corpus-gate-run0only.json
.steering/20260518-m9-c-adopt-plan-b-retrain\artifacts\plan-b-corpus-gate-final.json
.steering/20260517-m9-c-adopt-plan-b-design\requirement.md
.steering/20260517-m9-c-adopt-plan-b-design\next-session-prompt-FINAL-retrain.md
.steering/20260517-m9-c-adopt-plan-b-design\g-gear-collection-runbook.md
.steering/20260517-m9-c-adopt-plan-b-design\design.md
.steering/20260517-m9-c-adopt-plan-b-design\design-v2.md
.steering/20260517-m9-c-adopt-plan-b-design\design-v1.md
.steering/20260517-m9-c-adopt-plan-b-design\decisions.md
.steering/20260517-m9-c-adopt-plan-b-design\d2-encoder-allowlist-plan-b.json
.steering/20260517-m9-c-adopt-plan-b-design\codex-review.stderr
.steering/20260517-m9-c-adopt-plan-b-design\codex-review.md
.steering/20260517-m9-c-adopt-plan-b-design\codex-review-prompt.md
.steering/20260517-m9-c-adopt-plan-b-design\blockers.md
.steering/20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\tasklist.md
.steering/20260516-m9-c-adopt-plan-b-eval-gen\requirement.md
.steering/20260516-m9-c-adopt-plan-b-eval-gen\pr-body-draft.md
.steering/20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log
.steering/20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-r8v3-icc.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-r8v3-burrows.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\validation-kant-planb-nolora.json
.steering/20260516-m9-c-adopt-plan-b-eval-gen\validation-kant-r8v3.json
scripts/m9-c-adopt\audit_plan_b_corpus_stats.py
scripts/m9-c-adopt\aggregate_plan_b_axes.py
scripts/m9-c-adopt\compute_big5_icc.py
scripts/m9-c-adopt\compute_baseline_vendi.py
scripts/m9-c-adopt\bench_per_rank.sh
scripts/m9-c-adopt\compute_burrows_delta.py
scripts/m9-c-adopt\da14_verdict_plan_b.py
scripts/m9-c-adopt\validate_multiturn_shards.py
scripts/m9-c-adopt\tier_b_pilot.py
scripts/m9-c-adopt\run_plan_b_post_eval.sh
scripts/m9-c-adopt\run_plan_b_eval_sequence.sh
scripts/m9-c-adopt\rescore_vendi_alt_kernel.py
scripts/m9-c-adopt\launch_sglang_plan_b.sh
scripts/m9-c-adopt\de_focused_monolog_collector.py
scripts/m9-c-adopt\da1_matrix_multiturn.py
scripts/m9-c-adopt\da1_matrix.py
scripts/m9-c-adopt\da15_verdict.py
scripts/m9-c-adopt\da15_calibration_panel.py

hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw scripts/m9-c-adopt/da14_verdict_plan_b.py' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw scripts/m9-c-adopt/aggregate_plan_b_axes.py' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw scripts/m9-c-adopt/launch_sglang_plan_b.sh' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw scripts/m9-c-adopt/run_plan_b_eval_sequence.sh' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw scripts/m9-c-adopt/run_plan_b_post_eval.sh' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py' in C:\ERRE-Sand_Box
 succeeded in 386ms:
r"""DA-14 Plan B verdict aggregator 窶・kant ADOPT / Phase E A-6 (rank=16).

Reads the 4 rescore artefacts (MPNet + E5-large + lexical-5gram primary,
BGE-M3 exploratory) plus the kernel-independent Burrows / ICC / throughput
JSONs, applies the **encoder agreement axis** (3-of-4 primary with 2+
required, see ``.steering/20260517-m9-c-adopt-plan-b-design/
d2-encoder-allowlist-plan-b.json``), and writes the final verdict JSON +
markdown.

Plan B differs from DA-15 Plan A in two key ways:

1. **Encoder agreement axis** replaces the per-encoder eligibility +
   quorum logic. Plan B ADOPT requires at least 2 of the 3 *primary*
   encoders (MPNet / E5-large / lexical-5gram) to clear ALL of:

   * ``natural_d <= -0.5`` AND ``natural_diff_hi < 0``
   * ``language_balanced_d <= -0.5``
   * ``length_balanced_d <= -0.5``

   AND all 3 primaries must share the *same* (negative) sign on natural d
   窶・the BGE-M3 sign-flip lesson generalised to "majority direction
   discipline" (allowlist note ``rationale``).

2. **Burrows / ICC / throughput** axes are evaluated independently
   (kernel-agnostic) and *each* must clear:

   * Burrows reduction% >= 5 point AND CI lower > 0
   * ICC(A,1) >= 0.55
   * throughput pct of baseline >= 70%

Plan B kant ADOPT requires **all four** axis verdicts to PASS. A single
axis fail routes the persona to **Phase E A-6** (rank=16 spike, DA-16
ADR candidate 窶・see ``.steering/20260516-m9-c-adopt-plan-b-eval-gen/
blockers.md`` if recorded).

Usage::

    python scripts/m9-c-adopt/da14_verdict_plan_b.py \
        --rescore .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-mpnet-plan-b-kant.json \
        --rescore .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-e5large-plan-b-kant.json \
        --rescore .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-lex5-plan-b-kant.json \
        --rescore .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-bgem3-plan-b-kant.json \
        --burrows .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-burrows-plan-b-kant.json \
        --icc .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-icc-plan-b-kant.json \
        --throughput .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-throughput-plan-b-kant.json \
        --allowlist .steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json \
        --output-json .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.json \
        --output-md .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_VENDI_D_GATE: float = -0.5
_BURROWS_REDUCTION_GATE_PCT: float = 5.0
_ICC_GATE: float = 0.55
_THROUGHPUT_GATE_PCT: float = 70.0


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bootstrap_clears(payload: dict[str, Any] | None) -> bool:
    """Return True if a balanced bootstrap dict clears the DA-14 gates."""
    if not payload:
        return False
    return (
        payload.get("cohens_d") is not None
        and payload["cohens_d"] <= _VENDI_D_GATE
        and payload.get("diff_hi") is not None
        and payload["diff_hi"] < 0
    )


def _natural_clears(rescore: dict[str, Any]) -> tuple[bool, float | None, float | None]:
    """Natural-window gate: d <= -0.5 AND diff CI upper < 0."""
    sb = rescore.get("standard_bootstrap") or {}
    d = sb.get("cohens_d")
    hi = sb.get("diff_hi")
    pass_ = (
        d is not None
        and d <= _VENDI_D_GATE
        and hi is not None
        and hi < 0
    )
    return pass_, d, hi


def _per_encoder_summary(
    rescore: dict[str, Any],
    allowlist: dict[str, Any],
) -> dict[str, Any]:
    """Collect axis verdicts + role for a single encoder."""
    encoder = rescore["encoder"]
    d2_entry = allowlist["encoders"].get(encoder, {})
    role = d2_entry.get("role")
    pinned_sha = d2_entry.get("revision_sha")
    revision_match = rescore.get("encoder_revision_sha") == pinned_sha
    library_match = rescore.get("library_versions_match_d2", False)

    natural_pass, natural_d, natural_hi = _natural_clears(rescore)
    lang_pass = _bootstrap_clears(rescore.get("language_balanced_bootstrap"))
    length_pass = _bootstrap_clears(rescore.get("length_balanced_bootstrap"))

    lang_d = (
        rescore.get("language_balanced_bootstrap", {}).get("cohens_d")
        if rescore.get("language_balanced_bootstrap")
        else None
    )
    length_d = (
        rescore.get("length_balanced_bootstrap", {}).get("cohens_d")
        if rescore.get("length_balanced_bootstrap")
        else None
    )

    all_axes_pass = natural_pass and lang_pass and length_pass
    return {
        "encoder": encoder,
        "encoder_revision_sha": rescore.get("encoder_revision_sha"),
        "encoder_role_d2": role,
        "kernel_type": rescore.get("kernel_type", "semantic"),
        "d2_revision_match": revision_match,
        "d2_library_match": library_match,
        "natural_cohens_d": natural_d,
        "natural_diff_hi": natural_hi,
        "natural_pass": natural_pass,
        "language_balanced_d": lang_d,
        "language_balanced_pass": lang_pass,
        "length_balanced_d": length_d,
        "length_balanced_pass": length_pass,
        "all_three_axes_pass": all_axes_pass,
        "within_language_d": {
            lang: (entry.get("cohens_d") if isinstance(entry, dict) else None)
            for lang, entry in rescore.get("within_language", {}).items()
        },
    }


def _encoder_agreement_axis(per_encoder: list[dict[str, Any]]) -> dict[str, Any]:
    """3-primary-of-which-2-required encoder agreement gate.

    Returns the per-axis verdict + which encoders cleared. Primary list
    comes from allowlist role markers; exploratory (BGE-M3) is reported
    but cannot contribute to the quorum.
    """
    primaries = [e for e in per_encoder if e["encoder_role_d2"] == "primary"]
    exploratories = [
        e for e in per_encoder if e["encoder_role_d2"] == "exploratory"
    ]
    n_primary = len(primaries)
    n_primary_pass = sum(1 for e in primaries if e["all_three_axes_pass"])

    # Direction discipline: all primaries must share the same (negative)
    # natural d sign when the gate passes (BGE-M3 sign-flip generalisation).
    natural_ds = [
        e.get("natural_cohens_d") for e in primaries
        if e.get("natural_cohens_d") is not None
    ]
    all_negative = bool(natural_ds) and all(d < 0 for d in natural_ds)
    direction_pass = all_negative

    primary_pass = n_primary_pass >= 2 and direction_pass

    return {
        "primary_count_total": n_primary,
        "primary_count_passed_all_axes": n_primary_pass,
        "primary_count_required": 2,
        "direction_all_negative": all_negative,
        "axis_pass": primary_pass,
        "primary_encoders_passing": [
            e["encoder"] for e in primaries if e["all_three_axes_pass"]
        ],
        "exploratory_encoders_reported": [e["encoder"] for e in exploratories],
    }


def _burrows_axis(burrows: dict[str, Any]) -> dict[str, Any]:
    """Burrows reduction% gate (kernel-independent)."""
    reduction = burrows.get("reduction_pct")
    ci_lo = burrows.get("ci_lower")
    pass_ = (
        reduction is not None
        and reduction >= _BURROWS_REDUCTION_GATE_PCT
        and ci_lo is not None
        and ci_lo > 0
    )
    return {
        "reduction_pct": reduction,
        "ci_lower": ci_lo,
        "ci_upper": burrows.get("ci_upper"),
        "gate_pct": _BURROWS_REDUCTION_GATE_PCT,
        "axis_pass": pass_,
    }


def _icc_axis(icc: dict[str, Any]) -> dict[str, Any]:
    """ICC(A,1) gate (kernel-independent)."""
    point = icc.get("v2_point") or icc.get("point")
    pass_ = point is not None and point >= _ICC_GATE
    return {
        "icc_point": point,
        "gate": _ICC_GATE,
        "axis_pass": pass_,
    }


def _throughput_axis(throughput: dict[str, Any]) -> dict[str, Any]:
    """Throughput pct of baseline gate (kernel-independent)."""
    pct = throughput.get("throughput_pct_of_baseline") or throughput.get(
        "throughput_pct",
    )
    pass_ = pct is not None and pct >= _THROUGHPUT_GATE_PCT
    return {
        "throughput_pct_of_baseline": pct,
        "gate_pct": _THROUGHPUT_GATE_PCT,
        "axis_pass": pass_,
    }


def _aggregate_verdict(
    encoder_axis: dict[str, Any],
    burrows_axis: dict[str, Any],
    icc_axis: dict[str, Any],
    throughput_axis: dict[str, Any],
) -> str:
    """ADOPT if all four axes PASS, else PHASE_E_A6 (rank=16 spike)."""
    if (
        encoder_axis["axis_pass"]
        and burrows_axis["axis_pass"]
        and icc_axis["axis_pass"]
        and throughput_axis["axis_pass"]
    ):
        return "ADOPT"
    return "PHASE_E_A6"


def _fmt_or_dash(value: Any, fmt: str = ".4f") -> str:
    if isinstance(value, (int, float)) and value == value:
        return f"{value:{fmt}}"
    return "窶・


def _write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines: list[str] = []
    lines.append("# DA-14 Plan B verdict 窶・kant (encoder agreement axis)")
    lines.append("")
    lines.append(f"**verdict**: `{payload['verdict']}`")
    lines.append("")
    lines.append("## Thresholds (DA-14 / Plan B, unchanged)")
    lines.append("")
    th = payload["thresholds"]
    lines.append(f"- Vendi natural d 竕､ `{th['vendi_d_le']}` AND natural CI upper < 0")
    lines.append(f"- Lang-balanced d 竕､ `{th['vendi_d_le']}`")
    lines.append(f"- Length-balanced d 竕､ `{th['vendi_d_le']}`")
    lines.append(
        f"- Burrows reduction% 竕･ `{th['burrows_pct_ge']}` AND CI lower > 0",
    )
    lines.append(f"- ICC(A,1) 竕･ `{th['icc_ge']}`")
    lines.append(f"- Throughput pct of baseline 竕･ `{th['throughput_pct_ge']}%`")
    lines.append("")
    lines.append("## Per-encoder rescore (Plan B 4-encoder panel)")
    lines.append("")
    lines.append(
        "| encoder | role | natural d | lang-bal d | length-bal d | "
        "natural | lang-bal | length-bal | all-3 |",
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for enc in payload["per_encoder"]:
        nat_d = _fmt_or_dash(enc.get("natural_cohens_d"))
        lang_d = _fmt_or_dash(enc.get("language_balanced_d"))
        length_d = _fmt_or_dash(enc.get("length_balanced_d"))
        lines.append(
            f"| `{enc['encoder']}` | {enc.get('encoder_role_d2', '窶・)} | "
            f"{nat_d} | {lang_d} | {length_d} | "
            f"{'PASS' if enc['natural_pass'] else 'FAIL'} | "
            f"{'PASS' if enc['language_balanced_pass'] else 'FAIL'} | "
            f"{'PASS' if enc['length_balanced_pass'] else 'FAIL'} | "
            f"{'**YES**' if enc['all_three_axes_pass'] else 'no'} |",
        )
    lines.append("")
    lines.append("## Encoder agreement axis (3-of-4 primary, 2+ required)")
    lines.append("")
    ea = payload["axes"]["encoder_agreement"]
    lines.append(
        f"- Primaries clearing all 3 axes: **{ea['primary_count_passed_all_axes']}"
        f" of {ea['primary_count_total']}** "
        f"(required 竕･ {ea['primary_count_required']})",
    )
    lines.append(
        f"- All primary natural d share negative sign: "
        f"**{ea['direction_all_negative']}**",
    )
    lines.append(
        f"- Primary encoders passing: `{ea['primary_encoders_passing']}`",
    )
    lines.append(
        f"- Exploratory (reported, non-quorum): "
        f"`{ea['exploratory_encoders_reported']}`",
    )
    lines.append(f"- Axis verdict: `{'PASS' if ea['axis_pass'] else 'FAIL'}`")
    lines.append("")
    lines.append("## Kernel-independent axes")
    lines.append("")
    ba = payload["axes"]["burrows"]
    ia = payload["axes"]["icc"]
    ta = payload["axes"]["throughput"]
    lines.append(
        f"- Burrows reduction% = `{_fmt_or_dash(ba['reduction_pct'])}` "
        f"(CI lo=`{_fmt_or_dash(ba['ci_lower'])}` "
        f"hi=`{_fmt_or_dash(ba['ci_upper'])}`) 竊・"
        f"`{'PASS' if ba['axis_pass'] else 'FAIL'}`",
    )
    lines.append(
        f"- ICC(A,1) = `{_fmt_or_dash(ia['icc_point'])}` 竊・"
        f"`{'PASS' if ia['axis_pass'] else 'FAIL'}`",
    )
    lines.append(
        f"- Throughput pct = `{_fmt_or_dash(ta['throughput_pct_of_baseline'], '.2f')}%` 竊・"
        f"`{'PASS' if ta['axis_pass'] else 'FAIL'}`",
    )
    lines.append("")
    if payload["verdict"] == "ADOPT":
        lines.append("## kant ADOPT 窶・next step")
        lines.append("")
        lines.append(
            "All four axes PASS. Next session expands Plan B to nietzsche /"
            " rikyu by retraining each persona with the Plan B corpus +"
            " WeightedTrainer + DR-5/DR-6 patches, then recomputes this"
            " verdict per persona.",
        )
    else:
        lines.append("## Phase E A-6 (rank=16 spike) 窶・next step")
        lines.append("")
        lines.append(
            "At least one axis failed. Plan B kant is routed to Phase E A-6"
            " (rank=16 spike) as the next investment. Open a new ADR DA-16"
            " for the rank=16 hypothesis, recording which axes failed and"
            " the within-language d patterns that motivate rank capacity"
            " expansion vs further corpus tuning.",
        )
    lines.append("")
    lines.append("## Pre-registration anchor")
    lines.append("")
    lines.append(
        "Encoder + revision SHA + library versions + kernel_type are pinned"
        " in `.steering/20260517-m9-c-adopt-plan-b-design/"
        "d2-encoder-allowlist-plan-b.json`. Rescore + verdict outputs"
        " embed the runtime-detected SHA so the audit chain is self-"
        "contained.",
    )
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="m9-c-adopt-da14-verdict-plan-b")
    p.add_argument("--rescore", action="append", required=True, type=Path)
    p.add_argument("--burrows", required=True, type=Path)
    p.add_argument("--icc", required=True, type=Path)
    p.add_argument("--throughput", required=True, type=Path)
    p.add_argument("--allowlist", required=True, type=Path)
    p.add_argument("--output-json", required=True, type=Path)
    p.add_argument("--output-md", required=True, type=Path)
    args = p.parse_args(argv)

    allowlist = _load_json(args.allowlist)
    rescores = [_load_json(p) for p in args.rescore]
    burrows = _load_json(args.burrows)
    icc = _load_json(args.icc)
    throughput = _load_json(args.throughput)

    per_encoder = [_per_encoder_summary(r, allowlist) for r in rescores]
    encoder_axis = _encoder_agreement_axis(per_encoder)
    burrows_axis = _burrows_axis(burrows)
    icc_axis = _icc_axis(icc)
    throughput_axis = _throughput_axis(throughput)

    verdict = _aggregate_verdict(
        encoder_axis, burrows_axis, icc_axis, throughput_axis,
    )

    payload: dict[str, Any] = {
        "persona": "kant",
        "plan": "B",
        "verdict": verdict,
        "thresholds": {
            "vendi_d_le": _VENDI_D_GATE,
            "burrows_pct_ge": _BURROWS_REDUCTION_GATE_PCT,
            "icc_ge": _ICC_GATE,
            "throughput_pct_ge": _THROUGHPUT_GATE_PCT,
            "note": "DA-14 thresholds unchanged. Plan B applies them under"
            " the encoder agreement axis (3-of-4 primary, 2+ required) +"
            " kernel-independent Burrows/ICC/throughput.",
        },
        "per_encoder": per_encoder,
        "axes": {
            "encoder_agreement": encoder_axis,
            "burrows": burrows_axis,
            "icc": icc_axis,
            "throughput": throughput_axis,
        },
        "preregistration_anchor": (
            ".steering/20260517-m9-c-adopt-plan-b-design/"
            "d2-encoder-allowlist-plan-b.json (D-2 Plan B allowlist) +"
            " DA-14 thresholds unchanged. Encoder agreement axis from"
            " ``encoder_agreement_axis`` block of the allowlist."
        ),
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_markdown(payload, args.output_md)
    print(
        f"verdict={verdict} "
        f"encoder_agreement={encoder_axis['axis_pass']} "
        f"burrows={burrows_axis['axis_pass']} "
        f"icc={icc_axis['axis_pass']} "
        f"throughput={throughput_axis['axis_pass']}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


 succeeded in 399ms:
r"""m9-c-adopt Plan B 窶・aggregate per-condition Burrows / throughput axes
into the JSON format consumed by ``da14_verdict_plan_b.py``.

Reads:

* Burrows: two per-condition Burrows JSONs produced by
  ``compute_burrows_delta.py`` (LoRA-on and no-LoRA Plan B shards).
* ICC: a single ``compute_big5_icc.py`` JSON for the LoRA-on shards
  (kant_r8v3 adapter, SGLang). Falls through to ``v2_point`` field for
  the verdict aggregator.
* Throughput: derives `throughput_pct_of_baseline` from the per-shard
  metadata stored in each DuckDB shard (focal_per_s rate). LoRA-on
  rate / no-LoRA rate ﾃ・100.

Writes 3 separate JSONs in the format expected by ``da14_verdict_plan_b.
py``:

* ``--out-burrows``: ``{"reduction_pct": float, "ci_lower": float,
  "ci_upper": float, "v2_mean": float, "no_lora_mean": float}``
* ``--out-icc``: ``{"v2_point": float}``
* ``--out-throughput``: ``{"throughput_pct_of_baseline": float}``

Usage::

    python scripts/m9-c-adopt/aggregate_plan_b_axes.py \
        --burrows-v2 .steering/.../tier-b-plan-b-kant-r8v3-burrows.json \
        --burrows-nolora .steering/.../tier-b-plan-b-kant-planb-nolora-burrows.json \
        --icc-v2 .steering/.../tier-b-plan-b-kant-r8v3-icc.json \
        --v2-shards data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run0_stim.duckdb \
                    data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run1_stim.duckdb \
        --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb \
                        data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb \
        --out-burrows .steering/.../da14-burrows-plan-b-kant.json \
        --out-icc .steering/.../da14-icc-plan-b-kant.json \
        --out-throughput .steering/.../da14-throughput-plan-b-kant.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean, stdev
from typing import Any

import numpy as np


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _window_means(payload: dict[str, Any]) -> list[float]:
    """Extract per-window mean_burrows (skipping None) from a
    compute_burrows_delta.py output."""
    return [
        float(w["mean_burrows"])
        for w in payload.get("per_window", [])
        if w.get("mean_burrows") is not None
    ]


def _shard_focal_rate_from_log(log_path: Path, run_tag: str) -> float | None:
    """Parse final 'pilot done ... elapsed=X.X min completed=N' line for a
    given run tag (e.g. ``r8 run=0`` or ``nolora run=0``).

    Returns rate in focal/s, or None if the line is not yet present."""
    if not log_path.exists():
        return None
    rate: float | None = None
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if "pilot done" in line and run_tag in line:
            # Format: ... completed=N elapsed=X.X min ...
            try:
                completed_part = line.split("completed=")[1].split()[0]
                elapsed_part = line.split("elapsed=")[1].split()[0]
                completed = int(completed_part)
                elapsed_min = float(elapsed_part)
                rate = completed / (elapsed_min * 60.0)
            except (IndexError, ValueError):
                continue
    return rate


def _bootstrap_diff_pct_ci(
    v2: list[float],
    nolora: list[float],
    *,
    seed: int,
    n_resamples: int,
) -> tuple[float, float, float]:
    """Bootstrap CI for reduction%: (nolora_mean - v2_mean) / nolora_mean ﾃ・100.

    Returns (point_pct, ci_lo_pct, ci_hi_pct).
    """
    rng = np.random.default_rng(seed)
    a = np.asarray(v2, dtype=float)
    b = np.asarray(nolora, dtype=float)
    if a.size == 0 or b.size == 0:
        return float("nan"), float("nan"), float("nan")
    point = (float(b.mean()) - float(a.mean())) / float(b.mean()) * 100.0
    diffs: list[float] = []
    for _ in range(n_resamples):
        ra = rng.choice(a, size=a.size, replace=True)
        rb = rng.choice(b, size=b.size, replace=True)
        rm = float(rb.mean())
        if rm == 0:
            continue
        diffs.append((rm - float(ra.mean())) / rm * 100.0)
    if not diffs:
        return point, float("nan"), float("nan")
    diffs.sort()
    n = len(diffs)
    return point, diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="m9-c-adopt-aggregate-plan-b-axes")
    p.add_argument("--burrows-v2", required=True, type=Path)
    p.add_argument("--burrows-nolora", required=True, type=Path)
    p.add_argument("--icc-v2", required=True, type=Path)
    p.add_argument(
        "--icc-point-key",
        default="icc_agreement_single",
        help=(
            "Field name (inside the 'icc' block of the compute_big5_icc.py"
            " output, or top-level) holding the ICC(A,1) point estimate."
            " Default matches McGraw-Wong 'icc_agreement_single'."
        ),
    )
    p.add_argument("--v2-shards", nargs="+", required=True, type=Path)
    p.add_argument("--nolora-shards", nargs="+", required=True, type=Path)
    p.add_argument(
        "--eval-log",
        type=Path,
        required=True,
        help="Path to eval-sequence.log (used to derive per-run focal/s).",
    )
    p.add_argument("--out-burrows", required=True, type=Path)
    p.add_argument("--out-icc", required=True, type=Path)
    p.add_argument("--out-throughput", required=True, type=Path)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-resamples", type=int, default=2000)
    args = p.parse_args(argv)

    # ---- Burrows axis ----
    v2_payload = _load_json(args.burrows_v2)
    nolora_payload = _load_json(args.burrows_nolora)
    v2_means = _window_means(v2_payload)
    nolora_means = _window_means(nolora_payload)
    point, lo, hi = _bootstrap_diff_pct_ci(
        v2_means, nolora_means, seed=args.seed, n_resamples=args.n_resamples,
    )
    burrows_out = {
        "v2_mean": float(mean(v2_means)) if v2_means else None,
        "v2_stdev": float(stdev(v2_means)) if len(v2_means) > 1 else None,
        "no_lora_mean": float(mean(nolora_means)) if nolora_means else None,
        "no_lora_stdev": float(stdev(nolora_means)) if len(nolora_means) > 1 else None,
        "reduction_pct": point,
        "ci_lower": lo,
        "ci_upper": hi,
        "n_windows_v2": len(v2_means),
        "n_windows_nolora": len(nolora_means),
        "threshold_pct": 5.0,
        "note": (
            "reduction% = (no_lora_mean - v2_mean) / no_lora_mean ﾃ・100."
            " CI via 2000-iteration window-level bootstrap. DA-14 gate:"
            " reduction_pct >= 5 AND ci_lower > 0."
        ),
    }
    args.out_burrows.parent.mkdir(parents=True, exist_ok=True)
    args.out_burrows.write_text(
        json.dumps(burrows_out, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    # ---- ICC axis (single-condition, kernel-independent) ----
    icc_payload = _load_json(args.icc_v2)
    # compute_big5_icc.py output has icc.icc_agreement_single (= ICC(A,1))
    icc_block = icc_payload.get("icc", {})
    icc_point = (
        icc_block.get(args.icc_point_key)
        or icc_block.get("icc_agreement_single")
        or icc_payload.get(args.icc_point_key)
        or icc_payload.get("v2_point")
        or icc_payload.get("point")
    )
    icc_out = {
        "v2_point": float(icc_point) if icc_point is not None else None,
        "icc_source_path": str(args.icc_v2),
        "icc_field_used": args.icc_point_key,
        "threshold": 0.55,
        "note": (
            "ICC(A,1) absolute-agreement Big-5 ICC. DA-14 gate: point 竕･"
            " 0.55. Kernel-independent (computed via SGLang T=0.7 inference"
            " on focal utterances)."
        ),
    }
    args.out_icc.parent.mkdir(parents=True, exist_ok=True)
    args.out_icc.write_text(
        json.dumps(icc_out, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    # ---- Throughput axis ----
    # LoRA-on rates come from "pilot done persona=kant tag=r8 run=N ..."
    # no-LoRA rates come from "pilot done persona=kant tag=nolora run=N ..."
    v2_rates = [
        _shard_focal_rate_from_log(args.eval_log, f"tag=r8 run={i}")
        for i in range(len(args.v2_shards))
    ]
    nolora_rates = [
        _shard_focal_rate_from_log(args.eval_log, f"tag=nolora run={i}")
        for i in range(len(args.nolora_shards))
    ]
    v2_valid = [r for r in v2_rates if r is not None]
    nolora_valid = [r for r in nolora_rates if r is not None]
    v2_rate = float(mean(v2_valid)) if v2_valid else float("nan")
    nolora_rate = float(mean(nolora_valid)) if nolora_valid else float("nan")
    if nolora_rate and nolora_rate != 0 and nolora_rate == nolora_rate:
        throughput_pct = v2_rate / nolora_rate * 100.0
    else:
        throughput_pct = float("nan")
    throughput_out = {
        "v2_focal_per_s": v2_rate,
        "no_lora_focal_per_s": nolora_rate,
        "throughput_pct_of_baseline": throughput_pct,
        "v2_rates_per_shard": v2_rates,
        "no_lora_rates_per_shard": nolora_rates,
        "threshold_pct": 70.0,
        "note": (
            "throughput_pct_of_baseline = v2 mean rate / no-LoRA mean rate"
            " ﾃ・100. DA-14 gate: 竕･ 70%. Rates pulled from each shard's"
            " raw_dialog.metadata['pilot_rate_focal_per_s']."
        ),
    }
    args.out_throughput.parent.mkdir(parents=True, exist_ok=True)
    args.out_throughput.write_text(
        json.dumps(throughput_out, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    print(
        f"burrows reduction_pct={point:.4f} "
        f"icc_v2={icc_out['v2_point']} "
        f"throughput_pct={throughput_pct:.2f}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


 succeeded in 409ms:
#!/usr/bin/env bash
# m9-c-adopt Plan B verdict 窶・SGLang launch with kant_r8v3 LoRA adapter.
#
# K-ﾎｱ launch v5 + Plan B retrain best checkpoint (step 1500).
# See .steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md DR-4 for
# the Blackwell SM120 piecewise-cuda-graph workaround.
#
# Usage from WSL2 (background):
#   nohup bash /mnt/c/ERRE-Sand_Box/scripts/m9-c-adopt/launch_sglang_plan_b.sh \
#       > /mnt/c/ERRE-Sand_Box/.steering/20260516-m9-c-adopt-plan-b-eval-gen/sglang.log 2>&1 &
#
# Stop with:
#   pkill -f 'sglang.launch_server.*kant_r8v3'

set -euo pipefail

cd /root/erre-sandbox
source .venv/bin/activate

export HF_HOME=/root/.cache/huggingface
export HF_HUB_DISABLE_TELEMETRY=1
export PYTHONUTF8=1
export CUDA_HOME=/usr/local/cuda
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"

echo "[launch_sglang_plan_b] HF_HOME=${HF_HOME}"
echo "[launch_sglang_plan_b] python=$(which python)"
echo "[launch_sglang_plan_b] starting at $(date -Iseconds)"

exec python -m sglang.launch_server \
    --model Qwen/Qwen3-8B \
    --enable-lora \
    --max-loras-per-batch 1 \
    --max-lora-rank 8 \
    --lora-target-modules q_proj k_proj v_proj o_proj \
    --max-loaded-loras 1 \
    --lora-paths "kant_r8v3=/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500" \
    --quantization fp8 \
    --mem-fraction-static 0.85 \
    --max-total-tokens 2048 \
    --max-running-requests 1 \
    --disable-cuda-graph \
    --disable-piecewise-cuda-graph \
    --host 0.0.0.0 \
    --port 30000


 succeeded in 369ms:
#!/usr/bin/env bash
# m9-c-adopt Plan B eval shard sequence 窶・4 runs sequentially in WSL.
#
# Runs tier_b_pilot.py for:
#   1. LoRA-on run0  (kant_r8v3, ~1.5h)
#   2. LoRA-on run1  (kant_r8v3, ~1.5h)
#   3. no-LoRA run0  (base Qwen3-8B, ~1h)
#   4. no-LoRA run1  (base Qwen3-8B, ~1h)
#
# Total ~5h GPU. Run from WSL2 with SGLang already up on port 30000.
#
# Usage:
#   nohup bash /mnt/c/ERRE-Sand_Box/scripts/m9-c-adopt/run_plan_b_eval_sequence.sh \
#       > /mnt/c/ERRE-Sand_Box/.steering/20260516-m9-c-adopt-plan-b-eval-gen/eval-sequence.log 2>&1 &

set -uo pipefail

REPO=/mnt/c/ERRE-Sand_Box
PYTHON="${REPO}/.venv/Scripts/python.exe"
if [[ ! -x "$PYTHON" ]]; then
    # If invoked via Linux venv (uncommon 窶・clients are Windows-side),
    # fall back to /root/erre-sandbox/.venv.
    PYTHON=/root/erre-sandbox/.venv/bin/python
fi

OUT=${REPO}/data/eval/m9-c-adopt-plan-b-verdict
mkdir -p "$OUT"

run_pilot() {
    local label="$1"
    shift
    echo ""
    echo "==[ $label ]==  $(date -Iseconds)"
    if "$PYTHON" "${REPO}/scripts/m9-c-adopt/tier_b_pilot.py" "$@"; then
        echo "  [PASS] $label  $(date -Iseconds)"
    else
        echo "  [FAIL] $label exit=$?  $(date -Iseconds)"
        return 1
    fi
}

# Run 1: LoRA-on run0
run_pilot "LoRA-on run0" \
    --persona kant --rank 8 --run-idx 0 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --adapter-name kant_r8v3 \
    --output "${OUT}/kant_r8v3_run0_stim.duckdb" \
    || exit 1

# Run 2: LoRA-on run1
run_pilot "LoRA-on run1" \
    --persona kant --rank 8 --run-idx 1 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --adapter-name kant_r8v3 \
    --output "${OUT}/kant_r8v3_run1_stim.duckdb" \
    || exit 1

# Run 3: no-LoRA run0
run_pilot "no-LoRA run0" \
    --persona kant --no-lora-control --rank 0 --run-idx 0 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --output "${OUT}/kant_planb_nolora_run0_stim.duckdb" \
    || exit 1

# Run 4: no-LoRA run1
run_pilot "no-LoRA run1" \
    --persona kant --no-lora-control --rank 0 --run-idx 1 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --output "${OUT}/kant_planb_nolora_run1_stim.duckdb" \
    || exit 1

echo ""
echo "==[ ALL 4 RUNS COMPLETE ]==  $(date -Iseconds)"
echo "Output dir: ${OUT}"
ls -la "$OUT"


 succeeded in 378ms:
"""CLI smoke tests for ``scripts/m9-c-adopt/rescore_vendi_alt_kernel.py``.

Plan B verdict prep (`.steering/20260516-m9-c-adopt-plan-b-eval-gen/
design.md` ﾂｧ1.2) extended the script with ``--v2-shards`` / ``--nolora-shards``
/ ``--kernel-type`` / ``--allowlist-path`` flags so the same code path can
score the Plan B kant_r8v3 retrain artifact and the Plan B no-LoRA control
shards (blocker 2 of the prep PR 窶・hard-coded shard paths). These tests pin
the new CLI surface without requiring sentence-transformers or sklearn at
collection time.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "m9-c-adopt" / "rescore_vendi_alt_kernel.py"


@pytest.fixture(scope="module")
def rescore_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "rescore_vendi_alt_kernel",
        _SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rescore_vendi_alt_kernel"] = module
    spec.loader.exec_module(module)
    return module


def _build_parser(rescore_module: Any) -> Any:
    """Reconstruct the argparse parser without executing ``main``.

    ``main`` is one ~250-line function so the parser is rebuilt here by
    re-running the ``argparse`` block via a lightweight re-import trick:
    we monkeypatch ``argparse.ArgumentParser.parse_args`` to return the
    parsed Namespace and stop main's first side effect (``logging.
    basicConfig``).
    """
    raise NotImplementedError  # see direct parse_known_args() instead below


def _parse(rescore_module: Any, argv: list[str]) -> Any:
    """Run argparse only by invoking main() under a guard that aborts
    immediately after CLI parsing.

    The script's main() loads DuckDB shards right after ``parse_args``;
    we trigger that and capture the SystemExit from the shard-load failure
    while returning the parsed namespace via a sentinel exception.
    """

    class _CapturedArgs(BaseException):
        def __init__(self, ns: Any) -> None:
            self.ns = ns

    import argparse

    real_parse_args = argparse.ArgumentParser.parse_args

    def _capture(self: argparse.ArgumentParser, args: list[str] | None = None) -> Any:
        ns = real_parse_args(self, args)
        raise _CapturedArgs(ns)

    argparse.ArgumentParser.parse_args = _capture  # type: ignore[method-assign]
    try:
        try:
            rescore_module.main(argv)
        except _CapturedArgs as captured:
            return captured.ns
        raise AssertionError("parser did not raise _CapturedArgs")
    finally:
        argparse.ArgumentParser.parse_args = real_parse_args  # type: ignore[method-assign]


# ----- CLI parsing & validation tests -----


def test_default_shards_back_compat(rescore_module: Any) -> None:
    """No --v2-shards/--nolora-shards flags 竊・existing Plan A defaults."""
    ns = _parse(
        rescore_module,
        [
            "--encoder",
            "sentence-transformers/all-mpnet-base-v2",
            "--output",
            "output.json",
        ],
    )
    assert list(ns.v2_shards) == list(rescore_module._V2_SHARDS)
    assert list(ns.nolora_shards) == list(rescore_module._NOLORA_SHARDS)
    assert ns.kernel_type == "semantic"
    assert ns.allowlist_path == rescore_module._D2_ALLOWLIST_PATH


def test_custom_shards_override_defaults(rescore_module: Any) -> None:
    """Custom shard paths replace the Plan A constants."""
    ns = _parse(
        rescore_module,
        [
            "--encoder",
            "sentence-transformers/all-mpnet-base-v2",
            "--output",
            "output.json",
            "--v2-shards",
            "data/eval/a.duckdb",
            "data/eval/b.duckdb",
            "--nolora-shards",
            "data/eval/c.duckdb",
        ],
    )
    assert ns.v2_shards == [Path("data/eval/a.duckdb"), Path("data/eval/b.duckdb")]
    assert ns.nolora_shards == [Path("data/eval/c.duckdb")]


def test_kernel_type_lexical_5gram_defaults_encoder(rescore_module: Any) -> None:
    """--kernel-type lexical_5gram + no --encoder 竊・encoder defaults to
    the lexical_5gram allowlist key (post _resolve_encoder_default)."""
    ns = _parse(
        rescore_module,
        [
            "--kernel-type",
            "lexical_5gram",
            "--output",
            "output.json",
            "--v2-shards",
            "data/eval/a.duckdb",
            "--nolora-shards",
            "data/eval/b.duckdb",
            "--allowlist-path",
            ".steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json",
        ],
    )
    assert ns.kernel_type == "lexical_5gram"
    assert ns.encoder is None  # raw parse, before _resolve_encoder_default
    rescore_module._resolve_encoder_default(ns)
    assert ns.encoder == rescore_module._LEXICAL_5GRAM_ENCODER_KEY


def test_kernel_type_lexical_5gram_rejects_wrong_encoder(
    rescore_module: Any,
) -> None:
    """--kernel-type lexical_5gram + --encoder=foo 竊・SystemExit on
    _resolve_encoder_default."""
    ns = _parse(
        rescore_module,
        [
            "--kernel-type",
            "lexical_5gram",
            "--encoder",
            "sentence-transformers/all-mpnet-base-v2",
            "--output",
            "output.json",
            "--v2-shards",
            "data/eval/a.duckdb",
            "--nolora-shards",
            "data/eval/b.duckdb",
        ],
    )
    with pytest.raises(SystemExit, match="lexical_5gram"):
        rescore_module._resolve_encoder_default(ns)


def test_kernel_type_semantic_requires_encoder(rescore_module: Any) -> None:
    """--kernel-type semantic + no --encoder 竊・SystemExit on
    _resolve_encoder_default."""
    ns = _parse(
        rescore_module,
        [
            "--output",
            "output.json",
            "--v2-shards",
            "data/eval/a.duckdb",
            "--nolora-shards",
            "data/eval/b.duckdb",
        ],
    )
    with pytest.raises(SystemExit, match="required"):
        rescore_module._resolve_encoder_default(ns)


def test_kernel_type_invalid_choice_rejected(rescore_module: Any) -> None:
    """argparse choices=() guard catches unknown kernel families."""
    with pytest.raises(SystemExit):
        _parse(
            rescore_module,
            [
                "--encoder",
                "x",
                "--output",
                "output.json",
                "--kernel-type",
                "byte_pair_v1",
            ],
        )


# ----- lexical_5gram pool-fit semantics -----


def test_encode_pools_lexical_5gram_returns_unit_normed_matrices(
    rescore_module: Any,
) -> None:
    """``_encode_pools_lexical_5gram`` returns L2-normed dense matrices
    sized to the per-condition input counts. Each row's norm must be 1.0
    (within numerical tolerance) so the downstream ``unit @ unit.T``
    cosine recovery works exactly the same as the semantic path."""
    pytest.importorskip("sklearn")
    v2_texts = [
        "alpha bravo charlie delta echo",
        "alpha bravo charlie delta foxtrot",
    ]
    nolora_texts = [
        "zulu yankee whiskey victor uniform",
    ]
    v2_unit, nolora_unit = rescore_module._encode_pools_lexical_5gram(
        v2_texts,
        nolora_texts,
    )
    assert v2_unit.shape[0] == len(v2_texts)
    assert nolora_unit.shape[0] == len(nolora_texts)
    assert v2_unit.shape[1] == nolora_unit.shape[1]  # shared TF-IDF vocab
    v2_norms = np.linalg.norm(v2_unit, axis=1)
    nolora_norms = np.linalg.norm(nolora_unit, axis=1)
    assert np.allclose(v2_norms, 1.0, atol=1e-9)
    assert np.allclose(nolora_norms, 1.0, atol=1e-9)


def test_encode_pools_lexical_5gram_pool_fit_vs_per_window_fit(
    rescore_module: Any,
) -> None:
    """Pool-fit IDF and per-window-fit IDF give different cosine values
    because TF-IDF reweights by document frequency over the corpus seen
    at ``fit_transform`` time. DE-1 documents that the rescore design
    intentionally uses pool-fit (apples-to-apples IDF) and is not
    numerically equivalent to ``make_tfidf_5gram_cosine_kernel`` invoked
    per resample window."""
    pytest.importorskip("sklearn")
    from erre_sandbox.evidence.tier_b.vendi_lexical_5gram import (
        make_tfidf_5gram_cosine_kernel,
    )

    v2_texts = [
        "alpha bravo charlie delta echo",
        "alpha bravo charlie delta foxtrot",
    ]
    nolora_texts = [
        "alpha bravo charlie delta november",
    ]
    v2_unit, _ = rescore_module._encode_pools_lexical_5gram(
        v2_texts,
        nolora_texts,
    )
    pool_fit_cosine = float((v2_unit[0] @ v2_unit[1]).item())

    window_kernel = make_tfidf_5gram_cosine_kernel()
    per_window_matrix = window_kernel(v2_texts)
    per_window_cosine = float(per_window_matrix[0, 1])

    # Both are in [0, 1] (TF-IDF non-negative), diagonal=1, but the
    # off-diagonal differs because pool-fit IDF saw an extra document.
    assert 0.0 <= pool_fit_cosine <= 1.0
    assert 0.0 <= per_window_cosine <= 1.0
    assert pool_fit_cosine != pytest.approx(per_window_cosine, abs=1e-6)


 succeeded in 392ms:
#!/usr/bin/env bash
# m9-c-adopt Plan B 窶・post-eval-shard pipeline:
# 1. Shard validation (validate_multiturn_shards.py)
# 2. 4-encoder rescore (rescore_vendi_alt_kernel.py ﾃ・MPNet / E5-large / lex5 / BGE-M3)
# 3. Burrows per-condition (compute_burrows_delta.py ﾃ・LoRA-on / no-LoRA)
# 4. ICC single-condition (compute_big5_icc.py ﾃ・LoRA-on; no-LoRA proxy via v2 baseline ICC)
# 5. Axis aggregation (aggregate_plan_b_axes.py)
# 6. Verdict (da14_verdict_plan_b.py)
#
# Run after all 4 eval shards are present.

set -uo pipefail

REPO=/c/ERRE-Sand_Box
TASK=.steering/20260516-m9-c-adopt-plan-b-eval-gen
SHARDS=data/eval/m9-c-adopt-plan-b-verdict
ALLOWLIST=.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json
PY=.venv/Scripts/python.exe
SCR=scripts/m9-c-adopt

V2_SHARDS_GLOB="$SHARDS/kant_r8v3_run*_stim.duckdb"
NOLORA_SHARDS_GLOB="$SHARDS/kant_planb_nolora_run*_stim.duckdb"

LOG="$TASK/post-eval-pipeline.log"
mkdir -p "$(dirname "$LOG")"

step() {
    local label="$1"; shift
    echo ""
    echo "==[ $label $(date -Iseconds) ]==" | tee -a "$LOG"
    if "$@" 2>&1 | tee -a "$LOG"; then
        echo "  [PASS] $label" | tee -a "$LOG"
    else
        local code=$?
        echo "  [FAIL] $label exit=$code" | tee -a "$LOG"
        return $code
    fi
}

# ----- 1. Shard validation -----
step "validate LoRA-on shards" \
    "$PY" "$SCR/validate_multiturn_shards.py" \
    --persona kant --focal-target 300 \
    --shards-glob "$V2_SHARDS_GLOB" \
    --output "$TASK/validation-kant-r8v3.json"

step "validate no-LoRA shards" \
    "$PY" "$SCR/validate_multiturn_shards.py" \
    --persona kant --focal-target 300 \
    --shards-glob "$NOLORA_SHARDS_GLOB" \
    --output "$TASK/validation-kant-planb-nolora.json"

# ----- 2. 4-encoder rescore -----
for spec in \
    "sentence-transformers/all-mpnet-base-v2 semantic mpnet" \
    "intfloat/multilingual-e5-large semantic e5large" \
    "lexical_5gram lexical_5gram lex5" \
    "BAAI/bge-m3 semantic bgem3"; do
    set -- $spec
    encoder="$1"; ktype="$2"; suffix="$3"
    step "rescore $suffix" \
        "$PY" "$SCR/rescore_vendi_alt_kernel.py" \
        --encoder "$encoder" \
        --kernel-type "$ktype" \
        --allowlist-path "$ALLOWLIST" \
        --v2-shards "$SHARDS/kant_r8v3_run0_stim.duckdb" \
                    "$SHARDS/kant_r8v3_run1_stim.duckdb" \
        --nolora-shards "$SHARDS/kant_planb_nolora_run0_stim.duckdb" \
                        "$SHARDS/kant_planb_nolora_run1_stim.duckdb" \
        --output "$TASK/da14-rescore-${suffix}-plan-b-kant.json"
done

# ----- 3. Burrows per-condition -----
step "Burrows LoRA-on" \
    "$PY" "$SCR/compute_burrows_delta.py" \
    --persona kant \
    --shards-glob "$V2_SHARDS_GLOB" \
    --window-size 100 \
    --output "$TASK/tier-b-plan-b-kant-r8v3-burrows.json"

step "Burrows no-LoRA" \
    "$PY" "$SCR/compute_burrows_delta.py" \
    --persona kant \
    --shards-glob "$NOLORA_SHARDS_GLOB" \
    --window-size 100 \
    --output "$TASK/tier-b-plan-b-kant-planb-nolora-burrows.json"

# ----- 4. ICC single-condition (LoRA-on, kant_r8v3 adapter) -----
step "ICC kant_r8v3" \
    "$PY" "$SCR/compute_big5_icc.py" \
    --persona kant \
    --shards-glob "$V2_SHARDS_GLOB" \
    --responder sglang \
    --sglang-host http://127.0.0.1:30000 \
    --sglang-adapter kant_r8v3 \
    --temperature 0.7 \
    --window-size 100 \
    --output "$TASK/tier-b-plan-b-kant-r8v3-icc.json"

# ----- 5. Axis aggregation -----
step "aggregate axes" \
    "$PY" "$SCR/aggregate_plan_b_axes.py" \
    --burrows-v2 "$TASK/tier-b-plan-b-kant-r8v3-burrows.json" \
    --burrows-nolora "$TASK/tier-b-plan-b-kant-planb-nolora-burrows.json" \
    --icc-v2 "$TASK/tier-b-plan-b-kant-r8v3-icc.json" \
    --v2-shards "$SHARDS/kant_r8v3_run0_stim.duckdb" "$SHARDS/kant_r8v3_run1_stim.duckdb" \
    --nolora-shards "$SHARDS/kant_planb_nolora_run0_stim.duckdb" "$SHARDS/kant_planb_nolora_run1_stim.duckdb" \
    --eval-log "$TASK/eval-sequence.log" \
    --out-burrows "$TASK/da14-burrows-plan-b-kant.json" \
    --out-icc "$TASK/da14-icc-plan-b-kant.json" \
    --out-throughput "$TASK/da14-throughput-plan-b-kant.json"

# ----- 6. Verdict -----
step "verdict aggregator" \
    "$PY" "$SCR/da14_verdict_plan_b.py" \
    --rescore "$TASK/da14-rescore-mpnet-plan-b-kant.json" \
    --rescore "$TASK/da14-rescore-e5large-plan-b-kant.json" \
    --rescore "$TASK/da14-rescore-lex5-plan-b-kant.json" \
    --rescore "$TASK/da14-rescore-bgem3-plan-b-kant.json" \
    --burrows "$TASK/da14-burrows-plan-b-kant.json" \
    --icc "$TASK/da14-icc-plan-b-kant.json" \
    --throughput "$TASK/da14-throughput-plan-b-kant.json" \
    --allowlist "$ALLOWLIST" \
    --output-json "$TASK/da14-verdict-plan-b-kant.json" \
    --output-md "$TASK/da14-verdict-plan-b-kant.md"

echo ""
echo "==[ POST-EVAL PIPELINE COMPLETE $(date -Iseconds) ]==" | tee -a "$LOG"
cat "$TASK/da14-verdict-plan-b-kant.md"


hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw .steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw .steering/20260517-m9-c-adopt-plan-b-design/decisions.md' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw .steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw .steering/20260516-m9-c-adopt-plan-b-eval-gen/design.md' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw .steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw .steering/20260518-m9-c-adopt-plan-b-retrain/blockers.md' in C:\ERRE-Sand_Box
 succeeded in 482ms:
{
  "schema_version": 2,
  "plan": "B",
  "preregistration_note": "Plan B verdict 逕ｨ D-2 allowlist (HIGH-2 enforcement 邯呎価)縲１lan A 3 encoder 縺ｫ lexical-5gram 繧定ｿｽ蜉縺励‘ncoder agreement axis 繧・4-encoder 荳翫〒蛻､螳壹☆繧九・PNet 縺ｯ Plan A 縺ｧ縺ｮ per-encoder within-language d 邨先棡 (d_de=-0.72 譛蠑ｷ讀懷・蝎ｨ) 繧定ｸ上∪縺・primary 蠕ｩ蟶ｰ縲。GE-M3 縺ｯ Plan A natural d sign flip (+0.23) 繧定ｸ上∪縺・exploratory 譬ｼ荳九￡ (蝣ｱ蜻・obligatory 縺縺・ADOPT 蟇・ｸ惹ｸ榊庄)縲１lan B ADOPT 縺ｯ 3 primary encoder 縺ｮ縺・■ 2 莉･荳翫〒 natural d <= -0.5 + CI upper < 0 + lang-balanced d <= -0.5 + length-balanced d <= -0.5 繧呈ｺ縺溘☆縺薙→縲√°縺､隨ｦ蜿ｷ荳閾ｴ (3 縺ｨ繧・negative) 繧・pre-condition 縺ｨ縺吶ｋ縲Ｍexical-5gram 縺ｯ retrieval-trained 縺ｧ縺ｪ縺・independent kernel 縺ｨ縺励※ encoder diversity 繧堤｢ｺ菫昴☆繧九ょｮ溯｣・module path 縺ｯ譛ｬ PR 縺ｧ pre-register 縺ｮ縺ｿ縲∝ｮ溯｣・悽菴薙・谺｡繧ｻ繝・す繝ｧ繝ｳ (retrain prep) 縺ｧ `erre_sandbox.evidence.tier_b.vendi_lexical_5gram` 縺ｫ霑ｽ蜉縺吶ｋ縲・,
  "library_versions": {
    "sentence_transformers": "3.4.1",
    "transformers": "4.57.6"
  },
  "encoders": {
    "sentence-transformers/all-mpnet-base-v2": {
      "role": "primary",
      "revision_sha": "e8c3b32edf5434bc2275fc9bab85f82640a19130",
      "plan_a_role": "regression",
      "promotion_note": "Plan A within-language d 邨先棡 (d_de=-0.72) 縺ｧ per-language signal 縺ｮ譛蠑ｷ讀懷・蝎ｨ縺ｧ縺ゅｋ縺薙→縺・empirical 縺ｫ遒ｺ隱阪＆繧後◆縺溘ａ Plan B 縺ｧ縺ｯ primary 縺ｫ蠕ｩ蟶ｰ縲・
    },
    "intfloat/multilingual-e5-large": {
      "role": "primary",
      "revision_sha": "3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3",
      "plan_a_role": "primary",
      "promotion_note": "Plan A 縺ｮ en 霆ｸ讀懷・蝎ｨ (d_en=-0.58)縲１lan B 縺ｧ繧・primary 邯ｭ謖√・
    },
    "lexical_5gram": {
      "role": "primary",
      "revision_sha": "n/a",
      "implementation_module": "erre_sandbox.evidence.tier_b.vendi_lexical_5gram",
      "implementation_status": "pre-registered, not yet implemented; scoped to next-session retrain prep",
      "kernel_note": "Character 5-gram cosine similarity (Burrows-adjacent shallow stylometry)縲Ｓetrieval-trained 縺ｧ縺ｪ縺・independent 霆ｸ縺ｨ縺励※ encoder diversity 繧堤｢ｺ菫昴・
    },
    "BAAI/bge-m3": {
      "role": "exploratory",
      "revision_sha": "5617a9f61b028005a4858fdac845db406aefb181",
      "plan_a_role": "primary",
      "exclusion_reason": "Plan A natural d sign flip (+0.23 vs MPNet/E5 negative)縲Ｓetrieval-trained encoder 縺ｮ disagreement 繧・ADOPT 荳榊ｯ・ｸ主喧縺吶ｋ (BGE-M3 sign flip 謨呵ｨ薙・ generalisation)縲ょｱ蜻翫・ obligatory縲・
    }
  },
  "encoder_agreement_axis": {
    "primary_count_required": 2,
    "primary_count_total": 3,
    "direction_requirement": "all_negative_when_passing",
    "gate_conditions_per_encoder": [
      "natural_d <= -0.5 AND natural_diff_ci_upper < 0",
      "lang_balanced_d <= -0.5",
      "length_balanced_d <= -0.5"
    ],
    "rationale": "BGE-M3 sign flip 謨呵ｨ薙ｒ generalise縲・ encoder 縺・retrieval artefact 縺ｧ flip 縺励※繧・majority direction discipline (3 primary 縺ｮ縺・■ 2 縺悟酔譁ｹ蜷・+ gate clear) 縺ｧ ADOPT 蛻､螳壹′閻舌ｉ縺ｪ縺・・
  },
  "burrows_axis_note": "Burrows axis 縺ｯ encoder 髱樔ｾ晏ｭ倥↑縺ｮ縺ｧ譛ｬ allowlist 蟇ｾ雎｡螟悶・A-14 threshold (>= 5% point + CI lower > 0) 繧剃ｸ榊､峨〒驕ｩ逕ｨ縲１lan B 縺ｯ de monolog 髮・ｸｭ縺ｧ Burrows axis 荳ｻ逶ｮ讓咎＃謌舌ｒ迢吶≧險ｭ險医・
}


 succeeded in 495ms:
# 驥崎ｦ√↑險ｭ險亥愛譁ｭ 窶・m9-c-adopt Phase 2 (Plan B) design + driver

> 譛ｬ file 縺ｯ譛ｬ PR 蜀・・ session-local decisions 繧定ｨ倬鹸縺吶ｋ縲・> 讓ｪ譁ｭ逧・ADR (DA-1 ~ DA-15) 縺ｯ `.steering/20260513-m9-c-adopt/decisions.md`
> 繧貞盾辣ｧ (DA-16 蛟呵｣懊・ Plan B 邨先棡谺｡隨ｬ縺ｧ蛻･ ADR PR 縺ｧ襍ｷ逾ｨ)縲・
## DI-1: V1 / V2 / hybrid 謗｡逕ｨ蛻､螳・(`/reimagine` 繧・Task tool subagent 邨檎罰)

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: 譛ｬ繧ｿ繧ｹ繧ｯ縺ｯ譁ｰ隕・driver 險ｭ險・+ 譁ｰ隕・training 謗｡逕ｨ蛻､譁ｭ +
  achieved corpus gate 縺ｮ 3 霆ｸ縺ｧ螟壽｡医≠繧翫≧繧玖ｨｭ險医Ａ.claude/commands/
  reimagine.md` Step 3 縲瑚・蛻・↓ "隕九↑縺九▲縺溘％縺ｨ縺ｫ縺吶ｋ" 縺ｨ螳｣險縺吶ｋ縲阪・
  蜷御ｸ context 蜀・〒 V1 anchor leak 縺瑚ｵｷ縺阪ｋ縺溘ａ (DA-15 ADR DI-2 譌｢遏･
  蝠城｡・縲〃2 繧・Task tool subagent (Plan mode) 縺ｧ independent 逕滓・縲・- **謗｡逕ｨ process**:
  1. V1: primary agent 縺・`.steering/20260517-m9-c-adopt-plan-b-design/
     design-v1.md` 繧堤函謌・  2. V2: Task tool Plan subagent 縺・V1 繧定ｪｭ縺ｾ縺壹↓迢ｬ遶狗函謌舌∫ｵ先棡繧・     `design-v2.md` 縺ｫ materialise
  3. V1 / V2 繧呈ｯ碑ｼ・”ybrid 繧・`design.md` 縺ｫ遒ｺ螳・(譛ｬ PR 縺ｮ SSOT)
- **V2 縺瑚ｦ区栢縺・◆驥崎ｦ・finding** (V1 縺瑚ｦ玖誠縺ｨ縺励※縺・◆ / 蠑ｱ縺九▲縺・:
  - **monolog-as-stimulus-response vs system-prompt self-reflection
    縺ｮ驕ｸ謚櫁ｻｸ** (V2 ﾂｧ1.4): self-reflection 縺ｯ persona 縺ｮ referent 縺・    閾ｪ蛻・・霄ｫ縺ｫ蛛上ｊ縲。urrows function-word axis 繧・artefact 縺ｧ豁ｪ繧√ｋ縲・    stimulus-response 蠖｢縺ｯ argument 蜀・ｮｹ縺ｫ蜷代￥縺ｮ縺ｧ Critique 鬚ｨ
    transcendental argumentation 縺ｫ閾ｪ辟ｶ (LISA stylometry "content-
    bleached style channel" 莉ｮ隱ｬ縺ｨ謨ｴ蜷・
  - **de-alone 竕･ 0.30 hard gate** 縺ｮ minority opinion (V2 ﾂｧ8): Plan A
    縺ｮ per-language signal 縺ｯ de 縺ｧ譛蠑ｷ (-0.72 MPNet)縲‘n free-rider
    髦ｲ豁｢縺ｮ縺溘ａ de+en 竕･ 0.60 縺ｨ de 竕･ 0.30 縺ｮ **2 axis 縺ｫ蛻・屬**縲・    Codex MEDIUM-1 驕募渚縺ｧ縺ｯ縺ｪ縺・(DI-5 謨ｰ蛟､繧・retroactive 遘ｻ蜍輔○縺壹・    譁ｰ隕・axis 繧・Plan B 縺ｧ襍ｷ縺薙☆)
  - **3-of-4 encoder panel with majority direction discipline** (V2
    ﾂｧ5.3): BGE-M3 sign flip 謨呵ｨ薙ｒ generalise縲〉etrieval encoder 縺ｮ
    disagreement 繧・ADOPT 荳榊ｯ・ｸ主喧
  - **max_steps=2500 + EarlyStoppingCallback patience=2 min_delta=0.005**
    (V2 ﾂｧ3): v2 縺ｮ eval_loss 0.166竊・.180 envelope 縺ｫ empirically tied
  - **譁ｰ隕・stimulus battery 繧剃ｽ懊ｉ縺壽里蟄・kant.yaml subset 縺ｧ貂医∪縺・*
    (V2 ﾂｧ1.2): V1 縺ｯ `kant_de_focused.yaml` 繧呈眠隕剰ｿｽ蜉縺励※縺・◆縺後・    corpus capital 繧堤ｵ槭ｋ V2 縺ｮ蛻､譁ｭ縺ｮ縺ｻ縺・′譛ｬ ADR 縺ｮ "Plan B shape
    guide" 諤ｧ雉ｪ縺ｫ蜷郁・
- **V1 縺瑚ｲ｢迪ｮ縺励◆轤ｹ**:
  - G-GEAR runbook 縺ｮ structure (Phase B 蛻､譁ｭ 8 縺ｮ Windows native +
    PYTHONUTF8=1 邨瑚ｷｯ縺ｮ譏取枚蛹・
  - 譌｢蟄・patterns 縺ｨ縺ｮ謨ｴ蜷域ｧ mapping (DA-11 manifest convention 遲・
- **hybrid 謗｡逕ｨ (design.md)**:
  - V2 substance 繧・base 縺ｫ謗｡逕ｨ (ﾂｧ1.1 / ﾂｧ2 / ﾂｧ3 / ﾂｧ4 / ﾂｧ5)
  - V1 縺ｮ G-GEAR runbook structure 繧・ﾂｧ1.7 縺ｫ邨ｱ蜷・  - **MODIFY V2**: `vendi_lexical_5gram.py` 螳溯｣・・譛ｬ PR scope 螟・    (next-session retrain prep 縺ｧ螳溯｣・縲よ悽 PR 縺ｯ D-2 allowlist 縺ｫ
    module path 繧・pre-register 縺ｮ縺ｿ縲ら炊逕ｱ: retrain 螳溯｡悟燕縺ｫ verdict
    險育ｮ励・襍ｰ繧峨↑縺・◆繧・blocker 縺ｫ縺ｪ繧峨★縲∵悽 PR scope tightening
    (design + driver + 謗｡蜿匁ｺ門ｙ) 繧堤ｶｭ謖・- **繝医Ξ繝ｼ繝峨が繝・*:
  - V2 謗｡逕ｨ縺ｧ V1 縺ｮ譁ｰ隕・stimulus battery 縺ｯ謐ｨ縺ｦ縺・(corpus capital 遽邏・
  - V2 縺ｮ max_steps=2500 縺ｯ v2 baseline (4000) 繧医ｊ遏ｭ縺・‘arly stopping
    縺ｧ 1500-2500 steps 諠ｳ螳壹Ｔtep 2500 縺ｧ converge 荳崎ｶｳ縺ｮ risk 縺ｯ
    patience=2 縺ｧ蜷ｸ蜿・(val loss 荳頑・蜑阪↓豁｢繧√ｌ縺ｰ best checkpoint emit
    貂・
- **蠖ｱ髻ｿ遽・峇**: 譛ｬ PR 縺ｮ design.md 縺ｯ hybrid 謗｡逕ｨ迚医〃1/V2 縺ｯ historical
  record 縺ｨ縺励※ retain縲よｬ｡繧ｻ繝・す繝ｧ繝ｳ handoff 縺ｯ hybrid 縺ｫ蠕薙≧縲・
## DI-2: monolog-as-stimulus-response vs system-prompt self-reflection

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: de-monolog 謗｡蜿悶・ 2 霆ｸ驕ｸ謚櫁い縲７2 ﾂｧ1.4 縺ｧ stimulus-response
  蠖｢繧呈治逕ｨ縲《elf-reflection 蠖｢繧呈｣・唆縲・- **謗｡逕ｨ**: stimulus-response (persona prompt + de stimulus subset 縺九ｉ
  driver 縺・monolog 繧・emit)
- **逅・罰**:
  1. self-reflection 縺ｯ referent 縺・persona 閾ｪ菴薙↓蛛上ｊ (Critique-meta-
     talk artefact)縲。urrows function-word axis 繧・artificial 縺ｫ謚ｼ縺嶺ｸ翫￡繧・  2. Critique 邉ｻ邨ｱ縺ｮ Kant style 縺ｯ縲瑚ｪｭ閠・↓蜷代￠縺ｦ隰帙§繧・monolog縲阪〒縺ゅ▲縺ｦ
     縲瑚・蟾ｱ蜀・怐縲阪〒縺ｯ縺ｪ縺・・縺ｧ persona fit 縺ｧ縺ｪ縺・  3. stimulus-response 蠖｢縺ｯ LISA stylometry 縺ｮ "content-bleached
     content-independent style channel" 莉ｮ隱ｬ縺ｨ謨ｴ蜷・(Codex HIGH-2 蜿肴丐)
- **譽・唆**:
  - system-prompt self-reflection (荳願ｨ・1-2)
  - 譁ｰ隕・de-only stimulus battery 菴懈・ (V1 譯医…orpus capital 驕主臆縲・    V2 縺ｮ譌｢蟄・kant.yaml subset 縺ｧ蜊∝・)
- **蠖ｱ髻ｿ遽・峇**: `de_focused_monolog_collector.py` 縺ｮ system prompt 險ｭ險医・  stimulus loading 譁ｹ驥昴・
## DI-3: Plan B achieved corpus stats gate 縺ｫ de-alone 竕･ 0.30 繧定ｿｽ蜉 (V2 minority opinion)

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: Plan A 邨先棡縺ｯ per-language 縺ｧ de 縺梧怙蠑ｷ signal source
  (d_de=-0.72 MPNet)縲Ｅe+en mass 竕･ 0.60 縺縺代□縺ｨ en 縺・free-rider 縺ｫ
  縺ｪ縺｣縺ｦ de signal 縺悟・縺ｪ縺・Μ繧ｹ繧ｯ縺後≠繧九・- **驕ｸ謚櫁い**:
  - A: de+en 竕･ 0.60 縺ｮ縺ｿ hard gate (V1 譯・
  - B: de+en 竕･ 0.60 + de 竕･ 0.30 縺ｮ 2 axis hard gate (V2 minority opinion)
  - C: de 竕･ 0.30 縺ｮ縺ｿ hard gate (en 繧呈叛譽・
- **謗｡逕ｨ**: B (V2 minority opinion)
- **逅・罰**:
  1. Plan A non-gating observation 縺ｧ de 縺梧怙蠑ｷ signal 縺ｮ莠句ｮ・  2. en 縺ｯ 2 逡ｪ謇・(-0.58) 縺ｪ縺ｮ縺ｧ關ｽ縺ｨ縺帙↑縺・(B 縺・C 繧医ｊ strict)
  3. Codex MEDIUM-1 驕募渚縺ｧ縺ｯ縺ｪ縺・ DI-5 縺ｮ de+en 謨ｰ蛟､ (0.489) 繧・     retroactive 遘ｻ蜍輔☆繧九・縺ｧ縺ｯ縺ｪ縺上・*譁ｰ隕・axis 繧・Plan B 縺ｧ襍ｷ縺薙☆**縲・     "Plan B 襍ｷ蜍募ｾ後・ corpus shape expectation 繧・hard gate 縺ｫ縺吶ｋ"
     縺薙→縺ｯ MEDIUM-1 縺檎ｦ√§繧・"retroactive trigger promotion" 縺ｨ
     繧ｫ繝・ざ繝ｪ縺碁＆縺・- **繝医Ξ繝ｼ繝峨が繝・*:
  - 謗｡蜿門・ driver 縺ｮ雋闕ｷ蠅・(de bias 繧貞ｼｷ縺上☆繧句ｿ・ｦ√｝rompt tuning 縺・    蠢・ｦ・縲ゅ□縺・R-1 縺ｮ dry-run pre-test 縺ｧ莠句燕貂ｬ螳壹☆繧後・ mitigation 蜿ｯ
- **蠖ｱ髻ｿ遽・峇**: `audit_plan_b_corpus_stats.py` 縺ｮ 4 axis gate縲‥river
  縺ｮ persona prompt augmentation縲～d2-encoder-allowlist-plan-b.json` 縺ｮ
  preregistration note縲・
## DI-4: D-2 allowlist 縺ｧ MPNet primary 蠕ｩ蟶ｰ縲。GE-M3 exploratory 譬ｼ荳九￡縲〕exical-5gram 霑ｽ蜉

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: Plan A allowlist 縺ｧ縺ｯ MPNet=regression縲。GE-M3=primary
  縺縺｣縺溘′縲￣lan A 邨先棡縺ｧ BGE-M3 縺・natural d sign flip (+0.23) 繧・  襍ｷ縺薙＠縲｀PNet 縺・per-language 縺ｧ譛蠑ｷ (-0.72) 縺縺｣縺溘・- **謗｡逕ｨ**: V2 ﾂｧ5 縺ｮ 4-encoder panel
  - primary: MPNet (de 霆ｸ譛蠑ｷ)縲・5-large (en 霆ｸ讀懷・蝎ｨ)縲〕exical-5gram
    (retrieval-trained 縺ｧ縺ｪ縺・independent)
  - exploratory: BGE-M3 (Plan A sign flip 蝣ｱ蜻・obligatory縲、DOPT 荳榊ｯ・ｸ・
- **逅・罰**:
  1. Plan A 邨碁ｨ鍋噪莠句ｮ・(per-encoder within-language d) 縺ｫ蝓ｺ縺･縺・role
     蜀榊牡蠖薙※
  2. encoder agreement axis (3 primary 縺ｮ 2 莉･荳翫′蜷梧婿蜷代〒 gate clear)
     縺ｧ 1 encoder 縺ｮ retrieval artefact 縺・ADOPT 蛻､螳壹ｒ閻舌ｉ縺帙↑縺・  3. lexical-5gram 縺ｯ Burrows-adjacent shallow stylometry縲〉etrieval-
     trained 縺ｧ縺ｪ縺・independent kernel 繧定ｿｽ蜉縺吶ｋ縺薙→縺ｧ encoder
     diversity 繧堤｢ｺ菫・- **繝医Ξ繝ｼ繝峨が繝・*:
  - `vendi_lexical_5gram.py` 螳溯｣・′蠢・ｦ・(~50 LOC)縲よ悽 PR scope 繧堤ｵ槭ｋ
    縺溘ａ **谺｡繧ｻ繝・す繝ｧ繝ｳ (retrain prep) 縺ｫ scope**縲よ悽 PR 縺ｯ allowlist
    縺ｫ module path 繧・pre-register 縺ｮ縺ｿ縲・- **蠖ｱ髻ｿ遽・峇**: `d2-encoder-allowlist-plan-b.json`縲∵ｬ｡繧ｻ繝・す繝ｧ繝ｳ縺ｧ縺ｮ
  `vendi_lexical_5gram.py` 螳溯｣・+ 譌｢蟄・`vendi.py:_load_default_kernel`
  縺ｸ縺ｮ kernel 蠑墓焚霑ｽ蜉縲・
## DI-5: dataset.py 諡｡蠑ｵ縺ｯ train_kant_lora.py 蜀・〒螳滓命 (function 譛ｬ菴薙・謇蝨ｨ)

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: next-session prompt 縺ｯ "dataset.py 諡｡蠑ｵ" 繧定ｦ∵ｱゅ☆繧九′縲・  螳滄圀縺ｮ `_group_aware_stratified_split` 譛ｬ菴薙・
  `src/erre_sandbox/training/train_kant_lora.py` 縺ｫ髮・ｴ・＆繧後※縺・ｋ
  (line 785-836)縲・- **謗｡逕ｨ**: 譛ｬ PR 縺ｧ縺ｯ `train_kant_lora.py` 縺ｫ `stratify_by_language`
  kw-only flag 繧定ｿｽ蜉縲Ａdataset.py` 閾ｪ菴薙・螟画峩縺励↑縺・・- **逅・罰**:
  1. function 譛ｬ菴薙′ train_kant_lora.py 縺ｫ縺ゅｋ縺ｮ縺ｧ縲√◎縺薙ｒ諡｡蠑ｵ縺吶ｋ
     縺ｮ縺・minimum diff (蠑墓焚 1 縺､ + 蜀・Κ stratum key 螟画峩)
  2. dataset.py 縺ｮ `build_weighted_examples` 縺ｯ per-row metadata extract
     繧呈球蠖薙《plit 縺ｯ train_kant_lora 縺ｮ雋ｬ蜍吶∬ｲｬ蜍吝・髮｢繧剃ｿ昴▽
  3. next-session prompt 縺ｮ "dataset.py 諡｡蠑ｵ" 陦ｨ險倥・ naming 縺ｫ驕弱℃縺壹・     螳溯｣・ｴ謇繧堤ｴ・據縺吶ｋ迚ｩ縺ｧ縺ｯ縺ｪ縺・- **繝医Ξ繝ｼ繝峨が繝・*: 陦ｨ險倥→螳溯｣・ｴ謇縺御ｹ夜屬縺吶ｋ隕九°縺代・蟾ｮ縲Ｅecisions.md
  譛ｬ蛻､譁ｭ縺ｧ譏取枚蛹悶☆繧九％縺ｨ縺ｧ future reader 縺梧ｷｷ荵ｱ縺励↑縺・・- **蠖ｱ髻ｿ遽・峇**: `train_kant_lora.py` 縺ｮ `_group_aware_stratified_split`縲・  CLI flag `--lang-stratified-split`縲》est 縺ｯ
  `tests/test_training/test_dataset_lang_stratified.py` 縺ｮ naming 縺ｧ
  test_dataset 邉ｻ蛻励↓驟咲ｽｮ (next-session prompt 縺ｮ naming 繧・honour)縲・
## DI-6: lexical-5gram 螳溯｣・・譛ｬ PR scope 螟・(next-session retrain prep)

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: V2 ﾂｧ6 縺ｯ `vendi_lexical_5gram.py` 繧呈悽 PR 縺ｫ蜷ｫ繧√※縺・◆縲・- **謗｡逕ｨ**: 譛ｬ PR 縺ｯ **D-2 allowlist 縺ｫ module path 繧・pre-register
  縺ｮ縺ｿ**縲ょｮ溯｣・+ unit test 縺ｯ谺｡繧ｻ繝・す繝ｧ繝ｳ (retrain prep) 縺ｧ陦後≧縲・- **逅・罰**:
  1. retrain 螳溯｡悟燕縺ｫ verdict 險育ｮ励・襍ｰ繧峨↑縺・◆繧√∵悽 PR 縺ｧ螳溯｣・＠縺ｦ繧・     blocker 縺ｫ縺ｪ繧峨↑縺・  2. 譛ｬ PR scope tightening (design + driver + 謗｡蜿匁ｺ門ｙ) 繧堤ｶｭ謖√・     ~7-8h envelope 繧貞ｮ医ｋ
  3. `vendi.py:_load_default_kernel` 縺ｮ encoder 蠑墓焚蛹悶・ Plan A PR
     #179 縺ｧ貂医ｓ縺ｧ縺・ｋ縺後∵眠 kernel 繧ｿ繧､繝・("lexical") 繧定ｿｽ蜉縺吶ｋ縺ｫ縺ｯ
     `_load_default_kernel` 縺ｮ wrapper 諡｡蠑ｵ縺悟ｿ・ｦ√ゅ％繧後ｂ谺｡繧ｻ繝・す繝ｧ繝ｳ
     scope 縺ｫ邨ｱ蜷・(`vendi_lexical_5gram.py` + `vendi.py` 縺ｮ lexical
     kernel dispatch 繧貞酔譎ゅ↓陦後≧)
- **繝医Ξ繝ｼ繝峨が繝・*:
  - 谺｡繧ｻ繝・す繝ｧ繝ｳ縺・2 task (lexical-5gram 螳溯｣・+ retrain) 縺ｫ縺ｪ繧九・    lexical-5gram 縺ｯ ~30min縲〉etrain 縺ｯ ~20h overnight 縺ｪ縺ｮ縺ｧ overhead
    minimal
- **蠖ｱ髻ｿ遽・峇**: 谺｡繧ｻ繝・す繝ｧ繝ｳ handoff prompt 縺ｫ lexical-5gram 螳溯｣・ｒ
  譛蛻昴・ task 縺ｨ縺励※譏守､ｺ縲・
## DI-8: Codex independent review (gpt-5.5 xhigh) verdict ADOPT-WITH-CHANGES縲・ 莉ｶ蜈ｨ蜿肴丐

- **蛻､譁ｭ譌･譎・*: 2026-05-17 (`codex-review.md` verbatim 蜿鈴伜ｾ後∵悽繧ｻ繝・す繝ｧ繝ｳ蜀・  縺ｧ蜈ｨ HIGH/MEDIUM/LOW 蜿肴丐)
- **閭梧勹**: `.steering/20260517-m9-c-adopt-plan-b-design/codex-review.md`
  (gpt-5.5 xhigh) 縺御ｻ･荳・5 莉ｶ繧呈欠鞫・
  - **HIGH-1**: Plan B retrain command 縺・executable 縺ｧ縺ｪ縺・・    `train_kant_lora.py` 縺ｮ CLI 縺ｯ `--plan-b-gate` / `--lang-stratified-split`
    / `--eval-steps` 繧帝愆蜃ｺ縺励※縺翫ｉ縺壹～_handle_weighted_path` 繧・    `stratify_by_language` 繧呈ｸ｡縺励※縺・↑縺・～EarlyStoppingCallback` 繧・attach
    縺輔ｌ縺ｦ縺・↑縺・よｬ｡繧ｻ繝・す繝ｧ繝ｳ縺ｮ retrain 縺・argparse 縺ｧ failing
  - **HIGH-2**: `audit_plan_b_corpus_stats.py` 縺ｮ CLI 縺・`--n-eff-min` 遲・    threshold override flag 繧帝愆蜃ｺ縲Ｑreregistered hard gate 縺碁°逕ｨ荳翫・
    flag 縺ｧ蜍輔°縺帙ｋ縺ｮ縺ｯ HIGH-3 discipline (threshold motion 遖∵ｭ｢) 縺ｫ驕募渚
  - **MEDIUM-1**: 謗｡蜿・manifest 縺・documented but not emitted縲Ｓunbook ﾂｧ7 縺ｧ
    manifest schema 繧貞ｮ夂ｾｩ貂医□縺後…ollector 縺ｫ譖ｸ縺榊・縺励さ繝ｼ繝峨′縺ｪ縺・  - **MEDIUM-2**: "no addressee" 縺・metadata only 縺ｧ output-filtered 縺ｧ縺ｪ縺・・    `filter_de_monolog` 縺ｯ language / length / marker / trigram 縺ｮ縺ｿ蠑ｷ蛻ｶ縲・    "du / Sie / Ihre / Frage" 縺ｪ縺ｩ縺ｮ addressee marker 縺・accepted text 縺ｫ
    谿九▲縺溘∪縺ｾ `addressee=None` 縺ｧ謖ｿ蜈･縺輔ｌ繧・(weighting path 縺・"addressed
    text 繧・no-addressee 縺ｨ縺励※ boost" 縺励※縺励∪縺・
  - **LOW-1**: `--dry-run` 縺ｮ resume contract 驕募渚縲・LI help 縺ｨ runbook 縺ｯ
    "smoke dry-run 縺ｯ state 繧・preserve 縺励↑縺・ 縺ｨ險縺・′縲～run_collection()`
    縺ｯ always read + flush 縺励※縺・ｋ
- **蜿肴丐** (譛ｬ PR scope 蜀・〒蜈ｨ莉ｶ):
  1. **HIGH-1**:
     - `_build_arg_parser` 縺ｫ `--plan-b-gate` / `--lang-stratified-split` /
       `--eval-steps` 繧定ｿｽ蜉
     - `train_kant_lora` 繧ｷ繧ｰ繝阪メ繝｣縺ｫ `eval_steps` / `plan_b_gate` /
       `lang_stratified_split` 繧定ｿｽ蜉
     - `_run_weighted_path` 縺ｧ `stratify_by_language=lang_stratified_split`
       繧・`_collect_from_shards_weighted` 縺ｫ forward
     - `_pre_training_audit` 逶ｴ蠕後↓
       `erre_sandbox.training.plan_b_gate.audit_corpus` 繧貞他縺ｳ縲・-axis
       gate fail 縺ｧ `PlanBCorpusGateError` raise (exit 8)
     - `plan-b-corpus-gate.json` 繧・`output_dir_path` 縺ｫ蠢・★ emit
       (forensic)
     - `_run_trainer_weighted` 縺ｫ `plan_b_gate` 繧・threading縲ゝrue 譎ゅ↓
       `EarlyStoppingCallback(early_stopping_patience=2,
       early_stopping_threshold=0.005)` 繧・attach縲・       `metric_for_best_model="eval_loss"` + `greater_is_better=False` +
       `load_best_model_at_end=True` 繧・TrainingArguments 縺ｫ霑ｽ蜉
     - `eval_steps` 縺ｧ eval cadence 繧剃ｸ頑嶌縺榊庄閭ｽ (Plan B 縺ｧ縺ｯ 250 謗ｨ螂ｨ)
     - main() 縺ｮ exit code mapping 縺ｫ 8 = `PlanBCorpusGateError` 繧定ｿｽ蜉
     - `PlanBCorpusGateError` 繧・`exceptions.py` 縺ｫ譁ｰ隕剰ｿｽ蜉
  2. **HIGH-2**:
     - `scripts/m9-c-adopt/audit_plan_b_corpus_stats.py` 繧・thin CLI wrapper
       縺ｫ rewrite縲Ｕhreshold override CLI flags (`--n-eff-min` 遲・ 繧・**蜑企勁**
     - gate logic 繧・`src/erre_sandbox/training/plan_b_gate.py` 縺ｮ
       `audit_corpus` 縺ｫ promote (production 縺ｮ single source of truth)縲・       Threshold kwargs 縺ｯ pure function 縺ｫ谿九ｋ縺後，LI / `--plan-b-gate`
       path 縺ｮ縺ｩ縺｡繧峨ｂ production constants 繧偵ワ繝ｼ繝峨さ繝ｼ繝・bind
  3. **MEDIUM-1**: `de_focused_monolog_collector._write_manifest` 繧呈眠隕剰ｿｽ蜉縲・     collection 螳御ｺ・凾縺ｫ蠢・★ `<shard>_manifest.json` 繧・emit縲Ｔchema 縺ｯ
     runbook ﾂｧ7 騾壹ｊ (merge SHA / sampling params / filter thresholds /
     stimulus subset ids / acceptance rate)縲Ｎerge SHA 縺ｯ迺ｰ蠅・､画焚
     `PLAN_B_MERGE_SHA` 邨檎罰 (runbook 縺ｧ operator 縺・export 縺吶ｋ)
  4. **MEDIUM-2**: `filter_de_monolog` 縺ｫ **5 霆ｸ逶ｮ** "addressee" 繧定ｿｽ蜉縲・     informal 2nd-person (du / dich / dir / dein- / euch / euer / fragst)
     縺ｯ case-insensitive 縺ｧ match縲’ormal (Sie / Ihnen / Ihr-) 縺ｯ
     **case-sensitive** 縺ｧ match (lowercase "sie" / "ihr" 縺ｯ 3rd-person
     pronoun 縺ｨ縺励※ monolog 縺ｧ鬆ｻ蜃ｺ縺吶ｋ縺ｮ縺ｧ髯､螟・縲ＡFilterResult` 縺ｫ
     `has_addressee` field 繧定ｿｽ蜉縲Ａtests/test_de_focused_monolog_
     collector.py` 縺ｫ 3 test 霑ｽ蜉 (du / formal Sie / 3rd-person ihrer 縺ｮ
     misfire 蝗樣∩)
  5. **LOW-1**: `run_collection` 縺ｧ `args.dry_run=True` 譎ゅ・
     `_read_resume_state` 繧・skip 縺励～pilot_state` 繧貞・鬆ｭ縺ｧ wipe
     (acceptance rate 貂ｬ螳壹′豎ｺ螳夂噪縺ｫ)
- **譽・唆**: 縺ｪ縺・(蜈ｨ 5 莉ｶ adopt)
- **蠖ｱ髻ｿ遽・峇**:
  - `train_kant_lora.py` CLI 縺・runbook 縺ｮ retrain command 縺ｨ荳閾ｴ
  - 譌｢蟄・K-ﾎｲ / v2 baseline path 縺ｯ `--plan-b-gate` 譛ｪ謖・ｮ壹〒蜍穂ｽ應ｸ榊､・    (test_train_kant_lora_cli 縺ｮ譌｢蟄・13 test 蜈ｨ pass)
  - 譁ｰ test 15 莉ｶ (collector / 7 莉ｶ lang-stratified / 10 莉ｶ audit) 蜈ｨ pass縲・    譌｢蟄・training suite 45 莉ｶ蜈ｨ pass縲｝ilot smoke 13 莉ｶ蜈ｨ pass = **83 莉ｶ
    regression pass**

## DI-7: `--plan-b-gate` CLI flag 繧・default off (regression safety)

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: Plan B 縺ｮ hard gate 譏・ｼ (de+en 竕･ 0.60 + de 竕･ 0.30) 繧・  譌｢蟄・K-ﾎｲ / v2 baseline path 縺ｫ驕ｩ逕ｨ縺吶ｋ縺ｨ縲”istorical training run
  (5022 examples縲‥e+en=0.489) 縺・abort 縺吶ｋ縺薙→縺ｫ縺ｪ繧九・- **謗｡逕ｨ**: `--plan-b-gate` CLI flag 繧・default False縲∵悴謖・ｮ壹・ path 縺ｯ
  蜍穂ｽ應ｸ榊､・(譌｢蟄・N_eff / top_5 soft + hard gate 縺ｮ縺ｿ)縲・- **逅・罰**:
  1. 譌｢蟄・v2 retrain artefact (PR #168) 縺・re-train 荳崎・縺ｫ縺ｪ繧・risk 繧・     蝗樣∩
  2. Plan B 襍ｷ蜍輔・ **譛ｬ PR merge 蠕後・ retrain session 縺ｧ縺ｮ縺ｿ** trigger縲・     蝗槫ｸｰ test 縺ｮ golden test 繧堤ｴ螢翫＠縺ｪ縺・- **繝医Ξ繝ｼ繝峨が繝・*:
  - CLI flag 縺悟｢励∴繧九′縲～--plan-b-gate` 縺ｮ諢丞袖縺ｯ self-documenting
- **蠖ｱ髻ｿ遽・峇**: `train_kant_lora.py` 縺ｮ argparse縲》est
  `test_train_kant_lora_cli.py` 譌｢蟄・case 荳榊､峨∵眠隕・plan-b-gate test
  繧定ｿｽ蜉縲・

 succeeded in 447ms:
# 險ｭ險・窶・Plan B eval generation + verdict 險育ｮ・
## 0. Framing

prep PR #183 縺ｧ險倬鹸縺輔ｌ縺・blocker 1 (Plan B eval shard 荳榊惠) + blocker 2
(`rescore_vendi_alt_kernel.py` 縺ｮ shard path hard-coded) 繧定ｧ｣豸医＠縲・DA-14 thresholds 荳榊､峨・縺ｾ縺ｾ encoder agreement axis (3-of-4 primary 縺ｮ縺・■
2 莉･荳願ｦ∽ｻｶ) 縺ｧ kant ADOPT / Phase E A-6 (rank=16 spike) 繧貞愛螳壹☆繧九・
retrain artifact (`data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500/`縲・eval_loss=0.18259縲《tep 1500 best) 繧・SGLang LoRA adapter 縺ｨ縺励※ load縲・v2 baseline 縺ｨ **蜷・protocol** 縺ｧ stim eval 繧呈治蜿悶＠ apples-to-apples 豈碑ｼ・繧呈・遶九＆縺帙ｋ縲・
## 1. 螳溯｣・い繝励Ο繝ｼ繝・
### 1.1 Step 0: branch + steering

1. `git checkout main && git pull origin main`
2. `git checkout -b feature/m9-c-adopt-plan-b-eval-gen`
3. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/` 5 讓呎ｺ・file 襍ｷ逾ｨ

### 1.2 Step 1: `rescore_vendi_alt_kernel.py` CLI 諡｡蠑ｵ (~30 min)

**螟画峩蜀・ｮｹ** (`scripts/m9-c-adopt/rescore_vendi_alt_kernel.py`):

1. `--v2-shards` (kw-only `nargs="+"` Path縲‥efault `_V2_SHARDS`)
2. `--nolora-shards` (kw-only `nargs="+"` Path縲‥efault `_NOLORA_SHARDS`)
3. `--kernel-type` (`{semantic, lexical_5gram}` default `semantic`)
4. `--encoder` 繧・kernel_type=lexical_5gram 縺ｧ optional 蛹・   (lexical_5gram 縺ｯ encoder 髱樔ｾ晏ｭ倥√◆縺縺・allowlist 蠑輔″蠖薙※縺ｮ縺溘ａ
   "lexical_5gram" 繧・allowlist key 縺ｨ縺励※蜿励￠繧・
5. `_encode_pool` 繧・kernel_type 蟇ｾ蠢懊↓諡｡蠑ｵ:
   - semantic: 蠕捺擂騾壹ｊ (SentenceTransformer + L2 norm)
   - lexical_5gram: `TfidfVectorizer(analyzer="char_wb",
     ngram_range=(5,5), lowercase=True, norm="l2", sublinear_tf=False)`
     繧貞・ pool (v2 + no-LoRA 繧・merge) 縺ｧ fit縲∝推 condition 繧・     transform 縺励※ unit-normalized TF-IDF dense matrix 繧定ｿ斐☆
6. payload 縺ｮ `encoder` 繝輔ぅ繝ｼ繝ｫ繝峨・ kernel_type=lexical_5gram 譎・   `"lexical_5gram"` 繧定ｨ倬鹸 (allowlist key 縺ｨ荳閾ｴ)縲～encoder_revision_sha`
   縺ｯ `"n/a"` (allowlist 騾壹ｊ)
7. **D-2 allowlist 縺ｯ Plan B 逕ｨ** (`.steering/20260517-m9-c-adopt-plan-b-
   design/d2-encoder-allowlist-plan-b.json`) 繧貞盾辣ｧ:
   - `_D2_ALLOWLIST_PATH` 繧・CLI flag `--allowlist-path` 縺ｧ override 蜿ｯ閭ｽ蛹・     (default 縺ｯ譌｢蟄・Plan A path縲￣lan B 逕ｨ縺ｯ譏守､ｺ謖・ｮ・

**繝・せ繝・* (`tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py`):

- CLI parsing test: `--v2-shards a.duckdb b.duckdb --nolora-shards
  c.duckdb --kernel-type lexical_5gram` 縺ｮ args 隗｣驥・- backward-compat: flag 逵∫払譎・default 縺・`_V2_SHARDS` / `_NOLORA_SHARDS`
- kernel-type validation: invalid value 縺ｧ `SystemExit`
- lexical_5gram path: `_encode_pool` 縺・`make_tfidf_5gram_cosine_kernel`
  縺ｨ謨ｴ蜷医☆繧・unit-normalized vectors 繧定ｿ斐☆縺薙→
  (importorskip("sklearn") guard縲・ 轤ｹ繧ｻ繝・ヨ驕ｵ螳・

### 1.3 Step 2: SGLang server start + Plan B adapter load (G-GEAR WSL2)

K-ﾎｱ launch v5 invocation (DR-4 遒ｺ螳・:

```bash
PYTHONUTF8=1 python -m sglang.launch_server \
    --model-path Qwen/Qwen3-8B \
    --host 0.0.0.0 --port 30000 \
    --quantization fp8 \
    --mem-fraction-static 0.85 \
    --max-total-tokens 2048 \
    --max-running-requests 1 \
    --disable-cuda-graph \
    --disable-piecewise-cuda-graph \
    --lora-paths kant_r8v3=/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500 \
    --max-loras-per-batch 1 \
    --max-lora-rank 8
```

**襍ｷ蜍・verification**:
- `curl http://127.0.0.1:30000/v1/models` 縺ｧ adapter `kant_r8v3` 縺・  list 縺輔ｌ繧九％縺ｨ
- micro smoke (~3 net縲×60s) 縺ｧ sampler argmax kernel 縺・deadlock 縺励↑縺・  縺薙→ (DR-4 謨呵ｨ・

### 1.4 Step 3: Plan B eval shard 逕滓・ (~5h GPU overnight)

**LoRA-on run ﾃ・2** (~1.5h ﾃ・2 = 3h):
```bash
python scripts/m9-c-adopt/tier_b_pilot.py \
    --persona kant --rank 8 --run-idx 0 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --lora-name kant_r8v3 \
    --output data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run0_stim.duckdb

python scripts/m9-c-adopt/tier_b_pilot.py \
    --persona kant --rank 8 --run-idx 1 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --lora-name kant_r8v3 \
    --output data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run1_stim.duckdb
```

**no-LoRA control run ﾃ・2** (~1h ﾃ・2 = 2h):
```bash
python scripts/m9-c-adopt/tier_b_pilot.py \
    --persona kant --no-lora-control --rank 0 --run-idx 0 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --output data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb

python scripts/m9-c-adopt/tier_b_pilot.py \
    --persona kant --no-lora-control --rank 0 --run-idx 1 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --output data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb
```

**stimulus protocol** 縺ｯ v2 baseline (PR #160 era) 縺ｨ螳悟・縺ｫ蜷御ｸ
(`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)縲・
### 1.5 Step 4: Shard 讀懆ｨｼ

```bash
python scripts/m9-c-adopt/validate_multiturn_shards.py \
    data/eval/m9-c-adopt-plan-b-verdict/*.duckdb
```

讀懆ｨｼ鬆・岼:
- alternation: focal speaker (kant) 縺ｨ stimulus speaker 縺ｮ莠､莠呈ｧ
- row count: 譛溷ｾ・turn 謨ｰ (~1800 turn = 300 turn ﾃ・6 cycle) 縺ｨ縺ｮ荳閾ｴ
- multi-turn 謨ｴ蜷域ｧ: cycle 蜀・〒 multi-turn-max=6 莉･蜀・↓蜿弱∪縺｣縺ｦ縺・ｋ縺・
### 1.6 Step 5: 4-encoder rescore (~1-2h CPU)

D-2 allowlist (Plan B) 繧・`--allowlist-path` 縺ｧ謖・ｮ・

```bash
# MPNet (primary)
python scripts/m9-c-adopt/rescore_vendi_alt_kernel.py \
    --encoder sentence-transformers/all-mpnet-base-v2 \
    --kernel-type semantic \
    --allowlist-path .steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json \
    --v2-shards data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run0_stim.duckdb \
                data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run1_stim.duckdb \
    --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb \
                    data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb \
    --output .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-mpnet-plan-b-kant.json

# E5-large (primary) 窶・same with encoder swap + output suffix=e5large
# lexical-5gram (primary) 窶・--encoder lexical_5gram --kernel-type lexical_5gram
# BGE-M3 (exploratory) 窶・encoder swap + output suffix=bgem3
```

### 1.7 Step 6: Burrows / ICC / throughput

```bash
# Burrows reduction% (encoder 髱樔ｾ晏ｭ・
python scripts/m9-c-adopt/compute_burrows_delta.py \
    --v2-shards data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run{0,1}_stim.duckdb \
    --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run{0,1}_stim.duckdb \
    --output .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-burrows-plan-b-kant.json

# ICC(A,1) cross-recompute (Big-5 absolute agreement)
python scripts/m9-c-adopt/compute_big5_icc.py \
    --v2-shards ... --nolora-shards ... \
    --output .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-icc-plan-b-kant.json

# throughput pct of baseline
python scripts/m9-c-adopt/da1_matrix_multiturn.py \
    --shards ... --metric throughput \
    --output .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-throughput-plan-b-kant.json
```

(蜷・script 縺ｮ豁｣遒ｺ縺ｪ CLI 縺ｯ螳溯｣・凾縺ｫ遒ｺ隱阪∫樟迥ｶ design 繝吶・繧ｹ)

### 1.8 Step 7: verdict aggregator

譁ｰ隕・`scripts/m9-c-adopt/da14_verdict_plan_b.py` 繧定ｵｷ縺薙☆:

```python
# 蜈･蜉・ 4 rescore JSON + Burrows + ICC + throughput JSON
# 蜃ｺ蜉・ da14-verdict-plan-b-kant.json + da14-verdict-plan-b-kant.md

def evaluate_encoder_agreement(rescores: list[dict]) -> dict:
    """3 primary (MPNet/E5-large/lexical-5gram) 縺ｮ縺・■ 2 莉･荳翫〒
    natural_d <= -0.5 AND ci_upper < 0 AND lang_balanced_d <= -0.5
    AND length_balanced_d <= -0.5 AND 隨ｦ蜿ｷ荳閾ｴ (3 縺ｨ繧・negative)."""
    ...

def evaluate_burrows(burrows: dict) -> bool:
    """reduction% >= 5 point AND ci_lower > 0."""
    ...

def evaluate_icc(icc: dict) -> bool:
    """ICC(A,1) >= 0.55."""
    ...

def evaluate_throughput(throughput: dict) -> bool:
    """throughput pct of baseline >= 70%."""
    ...

def aggregate_verdict(...) -> Literal["ADOPT", "PHASE_E_A6"]:
    """蜈ｨ axis pass 竊・ADOPT縲・ axis 縺ｧ繧・fail 竊・PHASE_E_A6."""
```

### 1.9 Step 8: kant ADOPT or Phase E A-6 蛻､螳・+ decisions.md 險倬鹸

- 蜈ｨ gate pass 竊・`DR-1: kant Plan B ADOPT` 繧・decisions.md 縺ｫ險倬鹸縲・  谺｡ PR (nietzsche/rikyu 螻暮幕) 逕ｨ next-session prompt 襍ｷ逾ｨ
- 1 axis fail 竊・`DR-1: kant Plan B REJECT 竊・Phase E A-6 (rank=16) 遘ｻ陦形縲・  DA-16 ADR 襍ｷ逾ｨ蛟呵｣懊ｒ blockers.md 縺ｫ險倬鹸

### 1.10 Step 9: Codex independent review

`.steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review-prompt.md`
繧定ｵｷ逾ｨ縺励∽ｻ･荳九ｒ萓晞ｼ:

- 4-encoder rescore JSON 縺ｮ謨ｴ蜷域ｧ遒ｺ隱・(allowlist revision SHA 荳閾ｴ縲・  CI bound 險育ｮ励・豁｣蠖捺ｧ)
- verdict aggregator 縺ｮ繝ｭ繧ｸ繝・け (encoder agreement axis 縺ｮ 3-of-4 險育ｮ励・  CI gate 縺ｮ蠅・阜譚｡莉ｶ)
- ADOPT/REJECT 蛻､螳壹・ root cause assessment (縺ｩ縺ｮ axis 縺梧ｱｺ螳夂噪縺縺｣縺溘°)
- HIGH/MEDIUM/LOW 蠖｢蠑上〒蝣ｱ蜻贋ｾ晞ｼ

`cat .steering/<task>/codex-review-prompt.md | codex exec
--skip-git-repo-check` 縺ｧ襍ｷ蜍輔∝・蜉帙ｒ `codex-review.md` 縺ｫ verbatim 菫晏ｭ倥・
### 1.11 Step 10: pre-push CI parity + commit + PR

```bash
# WSL2
bash scripts/dev/pre-push-check.sh
# 4 谿ｵ (ruff format --check / ruff check / mypy src / pytest -q) 蜈ｨ pass 縺ｧ push 蜿ｯ
```

## 2. 螟画峩蟇ｾ雎｡

### 菫ｮ豁｣縺吶ｋ繝輔ぃ繧､繝ｫ

- `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py` 窶・CLI flag 諡｡蠑ｵ
  (`--v2-shards` / `--nolora-shards` / `--kernel-type` / `--allowlist-path`)
  + `_encode_pool` 縺ｮ kernel_type 蟇ｾ蠢・(semantic / lexical_5gram)

### 譁ｰ隕丈ｽ懈・縺吶ｋ繝輔ぃ繧､繝ｫ

- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/{requirement,design,
  tasklist,decisions,blockers}.md`
- `tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py`
- `scripts/m9-c-adopt/da14_verdict_plan_b.py`
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-{mpnet,
  e5large,lex5,bgem3}-plan-b-kant.json`
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-{burrows,icc,
  throughput}-plan-b-kant.json`
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.
  {json,md}`
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review-prompt.md`
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md`

### Track 蛹悶☆繧九ヵ繧｡繧､繝ｫ (generated, ~MB scale)

- `data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run{0,1}_stim.duckdb`
- `data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run{0,1}_stim.duckdb`

(DV-3 縺ｮ forensic JSON only 繝昴Μ繧ｷ繝ｼ鬘樔ｼｼ縺縺後‘val shard 縺ｯ蜀咲函謌蝉ｸ榊庄
繧ｳ繧ｹ繝・~5h GPU 縺ｧ valuable artefact 縺ｮ縺溘ａ commit縲ゅし繧､繧ｺ縺ｯ譌｢蟄・v2 shards
縺ｨ蜷檎ｭ・~10 MB ﾃ・4 = ~40 MB 繧ｹ繧ｱ繝ｼ繝ｫ繧呈Φ螳壹∬ｶ・℃譎ゅ・ LFS 讀懆ｨ・

## 3. 蠖ｱ髻ｿ遽・峇

- `rescore_vendi_alt_kernel.py` 縺ｮ譌｢蟄・invocation (Plan A) 縺ｯ default
  蛟､縺ｧ螳悟・ backward-compat縲￣R #179 / DA-15 譌｢蟄・JSON 蜀咲函謌舌・荳崎ｦ・- 譁ｰ directory `data/eval/m9-c-adopt-plan-b-verdict/` (Plan A / v2
  artifact 縺ｫ蜑ｯ菴懃畑縺ｪ縺・
- D-2 allowlist (Plan B) 縺ｯ譛ｬ PR 縺ｧ縺ｯ蜿ら・縺ｮ縺ｿ縲∵隼險ゅ＠縺ｪ縺・
## 4. 譌｢蟄倥ヱ繧ｿ繝ｼ繝ｳ縺ｨ縺ｮ謨ｴ蜷域ｧ

- forensic JSON commit縲∥dapter binary 縺ｯ git 螟・(PR #181 / #183 縺ｧ蜷後ヱ繧ｿ繝ｼ繝ｳ)
- D-2 allowlist (Plan B) 縺ｯ PR #179 design 縺ｧ蝗ｺ螳壽ｸ医〉evision_sha 蜴ｳ螳・- vendi_lexical_5gram.py + `_load_default_kernel(kernel_type='lexical_5gram')`
  dispatch 縺ｯ PR #181 縺ｧ merged 貂医∵悽 PR 縺ｧ縺ｯ consumer 蛛ｴ (rescore script)
  繧呈隼菫ｮ縺吶ｋ縺ｮ縺ｿ
- pre-push CI parity check (memory `feedback_pre_push_ci_parity.md`) 繧貞宍螳・
## 5. 繝・せ繝域姶逡･

- `tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py` 縺ｧ CLI 諡｡蠑ｵ
  縺ｮ 4 繧ｱ繝ｼ繧ｹ (parsing / backward-compat / kernel-type validation /
  lexical_5gram path) 繧・unit test
- lexical_5gram path 縺ｫ縺ｯ `pytest.importorskip("sklearn")` 繧貞ｿ・★莉倅ｸ・  (extras-only 3 轤ｹ繧ｻ繝・ヨ縲，LAUDE.md 遖∵ｭ｢莠矩・
- 譌｢蟄・`tests/test_evidence/test_vendi_lexical_5gram.py` (PR #181 縺ｧ merged
  貂・ 縺ｨ縺ｮ謨ｴ蜷域ｧ遒ｺ隱・- pre-push CI parity check (ruff format --check / ruff check / mypy src
  / pytest -q) 繧・commit 蜑阪↓蠢・★螳溯｡・
## 6. 繝ｭ繝ｼ繝ｫ繝舌ャ繧ｯ險育判

- branch revert 縺ｧ蜈ｨ artifact 縺梧ｶ医∴繧・(`feature/m9-c-adopt-plan-b-eval-gen`
  縺ｯ main 豢ｾ逕溘〒迢ｬ遶・
- ADOPT 蛻､螳壼ｾ後↓譁ｰ逋ｺ隕九′蜃ｺ縺溷ｴ蜷医∵悽 PR 縺ｮ verdict JSON 繧・reference
  artefact 縺ｨ縺励※谿九＠縲∵眠 PR 縺ｧ蜀崎ｩ穂ｾ｡
- Phase E A-6 遘ｻ陦悟愛螳壼ｾ後．A-16 ADR (rank=16 spike) 繧貞挨 PR 縺ｧ襍ｷ逾ｨ縲・  譛ｬ PR 縺ｮ verdict 縺ｯ reference 縺ｨ縺励※菫晄戟

## 7. 險ｭ險亥愛譁ｭ (譛ｬ PR 蝗ｺ譛峨‥ecisions.md 縺ｫ險倬鹸莠亥ｮ・

- **DE-1**: lexical_5gram 縺ｮ rescore 蜀・dispatch 縺ｯ **pool-fit** semantics
  (v2 + no-LoRA 蜈ｨ utterance 繧・merge 縺励※ TfidfVectorizer.fit縲∝推 condition
  繧・transform 縺励※ unit-normalized matrix 竊・譌｢蟄・`_vendi_from_unit_
  embeddings` slicing pattern 繧呈ｵ∫畑) 繧呈治逕ｨ縲ら炊逕ｱ: (1) apples-to-apples
  IDF basis 繧剃ｸ｡ condition 縺ｧ蜈ｱ譛峨・2) bootstrap iteration 縺斐→縺ｮ refit
  cost 繧貞屓驕ｿ (~250s per encoder 蜑頑ｸ・縲・3) `make_tfidf_5gram_cosine_
  kernel` 縺ｮ per-window-fit semantics 縺ｨ縺ｯ謨ｰ蛟､縺御ｸ閾ｴ縺励↑縺・′縲．A-14
  rescore 險ｭ險医・縲悟・ pool 縺ｧ encode 竊・window slice縲阪′蜑肴署
  (semantic path 繧ょ酔讒・

- **DE-2**: verdict aggregator script 蜷阪・ `da14_verdict_plan_b.py`
  (譁ｰ隕・ 繧呈治逕ｨ縲Ａda15_verdict.py` (Plan A) 縺ｨ荳ｦ蛻怜ｭ伜惠縺輔○縲￣lan A/B 縺ｮ
  axis 險育ｮ励Ο繧ｸ繝・け縺ｮ蟾ｮ蛻・ｒ譏守､ｺ蛹・(encoder agreement axis 3-of-4 縺ｯ
  Plan B 蝗ｺ譛・

- **DE-3**: eval shard 繧・`data/eval/m9-c-adopt-plan-b-verdict/`
  莉･荳九↓ commit (forensic JSON only 繝昴Μ繧ｷ繝ｼ DV-3 縺ｮ萓句､・縲ら炊逕ｱ:
  re-generate cost ~5h GPU縲∥rtefact 繧ｵ繧､繧ｺ ~40 MB 繧ｹ繧ｱ繝ｼ繝ｫ縺ｯ git 縺ｧ
  險ｱ螳ｹ遽・峇縲´FS 荳崎ｦ・

 succeeded in 447ms:
# 驥崎ｦ√↑險ｭ險亥愛譁ｭ 窶・Plan B eval generation + verdict 險育ｮ・
> 譛ｬ file 縺ｯ譛ｬ繧ｻ繝・す繝ｧ繝ｳ蝗ｺ譛峨・ session-local decisions 繧定ｨ倬鹸縺吶ｋ縲・> 讓ｪ譁ｭ ADR 縺ｯ `.steering/20260513-m9-c-adopt/decisions.md`縲・> Plan B verdict prep 縺ｯ `.steering/20260518-m9-c-adopt-plan-b-verdict/
> decisions.md` DV-1縲廛V-3縲〉etrain prep 縺ｯ
> `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-1縲廛R-7
> 繧貞盾辣ｧ縲・
## DE-1: lexical_5gram rescore 縺ｯ **pool-fit** TF-IDF (per-window-fit 縺ｧ縺ｯ縺ｪ縺・

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: Plan B D-2 primary 縺ｮ lexical_5gram 縺ｯ
  `vendi_lexical_5gram.make_tfidf_5gram_cosine_kernel` 縺ｧ **per-window-fit**
  semantics (TF-IDF 繧・window 蜀・〒 fit縲∝､夜Κ corpus 縺ｨ迢ｬ遶・ 繧呈署萓帙☆繧九・  縺励°縺・`rescore_vendi_alt_kernel.py` 縺ｮ DA-15 險ｭ險医・縲悟・ pool 縺ｧ encode
  once 竊・window slice縲阪′蜑肴署 (semantic path 繧ょ酔讒・縲・- **驕ｸ謚櫁い**:
  - A: per-window-fit (production semantics 螳悟・荳閾ｴ縲｜ootstrap iteration
    縺斐→縺ｫ TfidfVectorizer.fit_transform縲×250s overhead per encoder)
  - B: pool-fit (TfidfVectorizer.fit_transform 繧・v2+no-LoRA merged pool
    縺ｧ荳蝗槫ｮ溯｡後∝推 condition 繧・transform 縺励※ unit-normalized 陦悟・ 竊・    譌｢蟄・`_vendi_from_unit_embeddings` slicing pattern 縺ｫ豬∫畑)
- **謗｡逕ｨ**: B
- **逅・罰**:
  1. **Apples-to-apples IDF basis**: 荳｡ condition 縺悟酔縺・TF-IDF 驥阪∩莉倥￠
     遨ｺ髢薙〒隧穂ｾ｡縺輔ｌ繧九Ｑer-window-fit 縺ｯ window 縺斐→縺ｫ IDF basis 縺・     螟牙虚縺励…ondition 髢捺ｯ碑ｼ・〒 artefact 繧堤函繧蜿ｯ閭ｽ諤ｧ
  2. **bootstrap efficiency**: 2000 standard + 500 balanced ﾃ・3 strata =
     ~5000 iteration 縺ｮ TfidfVectorizer.fit_transform 繧貞屓驕ｿ
  3. **譌｢蟄・semantic path 縺ｨ縺ｮ謨ｴ蜷域ｧ**: MPNet/E5/BGE-M3 繧ょ・ pool 縺ｧ
     encode once 竊・window slice (Plan A 縺九ｉ荳榊､・
- **繝医Ξ繝ｼ繝峨が繝・*:
  - **DE-1 caveat**: pool-fit 縺ｯ `vendi_lexical_5gram.make_tfidf_5gram_
    cosine_kernel` 縺ｮ production 謗｡蜿匁凾 semantics 縺ｨ荳閾ｴ縺励↑縺・(per-
    window-fit)縲１roduction `compute_vendi` 邨檎罰縺ｮ score 縺ｨ縺ｯ謨ｰ蛟､縺・    逡ｰ縺ｪ繧句庄閭ｽ諤ｧ縺ゅｊ縲・odex review 縺ｧ MEDIUM 謖・遭縺ｮ菴吝慍縺ゅｊ縲・  - **Plan B kant shards 縺ｯ ~equal mass** (n_v2 竕・n_nolora) 縺ｧ pool-fit
    縺ｮ Simpson's-style artefact 縺ｯ菴弱Μ繧ｹ繧ｯ縲Ｏietzsche / rikyu 螻暮幕譎ゅ↓
    asymmetric shards 縺ｫ縺ｪ繧句ｴ蜷医・蜀崎ｩ穂ｾ｡
- **蠖ｱ髻ｿ遽・峇**: `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py::
  _encode_pools_lexical_5gram`縲～tests/test_scripts/test_rescore_vendi_
  alt_kernel_cli.py::test_encode_pools_lexical_5gram_pool_fit_vs_per_
  window_fit` 縺ｧ pool-fit vs per-window-fit 縺ｮ髱樔ｸ閾ｴ繧呈・譁・喧
- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: nietzsche / rikyu 縺ｮ Plan B 螻暮幕縺ｧ shards 縺・  asymmetric 縺ｫ縺ｪ繧句ｴ蜷医√∪縺溘・ Codex MEDIUM 謖・遭縺ｧ pool-fit semantics
  縺ｮ螯･蠖捺ｧ縺ｫ逍醍ｾｩ縺悟・縺溷ｴ蜷・
## DE-2: verdict aggregator 縺ｯ譁ｰ隕・`da14_verdict_plan_b.py` (Plan A 逕ｨ `da15_verdict.py` 縺ｨ荳ｦ蛻怜ｭ伜惠)

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: Plan A 逕ｨ `da15_verdict.py` 縺ｯ縲継er-encoder eligibility +
  quorum 2-of-3 axes縲阪・ Plan A 蝗ｺ譛峨Ο繧ｸ繝・け縲１lan B 縺ｮ encoder agreement
  axis (3-of-4 primary縲・+ required縲‥irection discipline) 縺ｯ蛻･繝ｭ繧ｸ繝・け
  縺ｪ縺ｮ縺ｧ縲～da15_verdict.py` 繧呈僑蠑ｵ縺吶ｋ縺ｨ Plan A/B 縺ｮ雋ｬ蜍吶′豺ｷ縺倥ｋ縲・- **驕ｸ謚櫁い**:
  - A: `da15_verdict.py` 縺ｫ `--plan {A,B}` flag 繧定ｿｽ蜉縺・dispatch
  - B: 譁ｰ隕・`da14_verdict_plan_b.py` 繧定ｵｷ縺薙＠縲￣lan A 縺ｯ譌｢蟄倡ｶｭ謖・- **謗｡逕ｨ**: B
- **逅・罰**:
  1. Plan A 縺ｯ譌｢縺ｫ merged 貂医∬ｿｽ蜉 flag 縺ｧ譌｢蟄・invocation 繧貞｣翫＆縺ｪ縺・     譁ｹ縺・safer
  2. Plan B 縺ｮ encoder agreement axis 縺ｯ **Plan B 蝗ｺ譛・* 縺ｮ design
     decision (allowlist 縺ｮ `encoder_agreement_axis` block)縲・Plan C
     莉･髯阪〒蛻･ axis 險ｭ險医′譚･縺溷ｴ蜷医∥ggregator 縺ｯ plan 縺斐→縺ｫ蛻･ script
     縺ｫ縺励◆譁ｹ縺瑚ｪｭ縺ｿ繧・☆縺・  3. diff 譛蟆丞喧 窶・`da15_verdict.py` 縺ｯ螟画峩荳崎ｦ√￣lan A 譌｢蟄・JSON 蜀・     逕滓・繧ゆｸ崎ｦ・- **繝医Ξ繝ｼ繝峨が繝・*: 2 script 縺ｮ驥崎､・Ο繧ｸ繝・け (load JSON縲》hreshold 驕ｩ逕ｨ)
  縺・~50 陦檎匱逕溘ょ・騾壼喧縺ｯ蛻･ PR 縺ｧ commit 蛟呵｣・- **蠖ｱ髻ｿ遽・峇**: `scripts/m9-c-adopt/da14_verdict_plan_b.py` 譁ｰ隕上・  譌｢蟄・`da15_verdict.py` 荳榊､峨・- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: Plan C 險ｭ險域凾縺ｫ common library
  (`m9_c_adopt_verdict_lib.py`) 繧呈歓蜃ｺ縺吶ｋ縺句愛譁ｭ

## DE-3: Plan B eval shards (`data/eval/m9-c-adopt-plan-b-verdict/`) 縺ｯ git 縺ｧ commit (DV-3 萓句､・

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: prep PR #183 縺ｮ DV-3 縺ｯ縲径dapter binary 縺ｯ git 螟悶’orensic
  JSON 縺ｮ縺ｿ commit縲阪→縺励◆縲１lan B eval shards 縺ｯ ~10 MB ﾃ・4 = ~40 MB
  繧ｹ繧ｱ繝ｼ繝ｫ縺ｧ縲∝・逕滓・繧ｳ繧ｹ繝医・ **~30 min GPU** (譛ｬ繧ｻ繝・す繝ｧ繝ｳ螳滓ｸｬ縲・  蠖灘・ 5h 諠ｳ螳壹ｒ螟ｧ蟷・洒邵ｮ)縲・- **驕ｸ謚櫁い**:
  - A: git 縺ｧ commit (譛ｬ PR scope 縺ｫ蜷ｫ繧√ｋ縲」erdict reproducibility 竊・
  - B: .gitignore 縺ｧ髯､螟・(re-generation 蜑肴署縲“it size 蠅・-)
  - C: HuggingFace Hub 縺ｫ push (binary 縺ｯ蛻･ store縲’orensic JSON 縺ｮ縺ｿ
    git 縺ｫ)
- **謗｡逕ｨ**: A
- **逅・罰**:
  1. ~40 MB 縺ｯ git 縺ｧ險ｱ螳ｹ遽・峇 (LFS 荳崎ｦ√～data/eval/` 縺ｫ縺ｯ譌｢縺ｫ v2 baseline
     shards 縺・~80 MB commit 貂医・蜑堺ｾ・
  2. verdict JSON 縺梧欠縺・shards 縺・repo 蜀・↓縺ゅｋ縺ｨ future reader 縺・     蜀咲樟遒ｺ隱阪〒縺阪ｋ (rescore_vendi_alt_kernel.py 繧呈眠 shards 縺ｧ蜀榊ｮ溯｡・     縺励※謨ｰ蛟､繧・replay 蜿ｯ閭ｽ)
  3. ~30 min 蜀咲函謌舌・ **GPU 蜊譛・* 縺ｧ霆ｽ縺上↑縺・さ繧ｹ繝医∥rtefact reuse 縺ｮ
     萓｡蛟､縺碁ｫ倥＞
- **繝医Ξ繝ｼ繝峨が繝・*: ~40 MB 縺ｮ git repo size 蠅励・FS 遘ｻ陦後・蟆・擂隱ｲ鬘後・- **蠖ｱ髻ｿ遽・峇**: `data/eval/m9-c-adopt-plan-b-verdict/*.duckdb` 4 蛟九ｒ
  譛ｬ PR 縺ｧ commit縲・- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: nietzsche / rikyu 縺ｮ Plan B 螻暮幕縺ｧ shards 縺・  ~150 MB 繧ｹ繧ｱ繝ｼ繝ｫ縺ｫ縺ｪ繧句ｴ蜷医´FS 遘ｻ陦後ｒ讀懆ｨ・
## DE-4: ICC 縺ｯ LoRA-on single-condition 縺ｮ縺ｿ險育ｮ・(no-LoRA ICC 縺ｯ computation skip)

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: DA-14 ICC(A,1) gate 縺ｯ **LoRA-on 縺ｮ Big-5 荳雋ｫ諤ｧ 竕･ 0.55** 繧・  隕∵ｱゅ☆繧・(kernel-independent axis)縲Ａcompute_big5_icc.py` 縺ｯ SGLang 謗ｨ隲・  ~30 min/condition 繧定ｦ√☆繧九Ｗ2 baseline 縺ｧ縺ｮ kant_r8v2 ICC 縺ｯ 0.91 縺ｧ
  gate (0.55) 繧貞､ｧ縺阪￥荳雁屓繧翫￣lan B retrain 縺ｧ蜷・Big-5 scoring 譁ｹ豕輔ｒ
  菴ｿ縺・剞繧・0.55 繧剃ｸ句屓繧句庄閭ｽ諤ｧ縺ｯ逅・ｫ紋ｸ贋ｽ弱＞縲・- **驕ｸ謚櫁い**:
  - A: LoRA-on + no-LoRA 荳｡譁ｹ險育ｮ・(full apples-to-apples縲・~30 min GPU)
  - B: LoRA-on 縺ｮ縺ｿ險育ｮ・(gate 隧穂ｾ｡縺ｫ蠢・ｦ√↑蛟､縺ｮ縺ｿ縲］o-LoRA ICC 縺ｯ
    documented as out-of-scope of the gate)
  - C: v2 baseline ICC (0.91) 繧・proxy 縺ｧ菴ｿ縺・(computation skip縲・    Plan B 謨ｰ蛟､縺ｯ譛ｪ讀懆ｨｼ)
- **謗｡逕ｨ**: B
- **逅・罰**:
  1. DA-14 gate 縺ｯ **LoRA-on ICC 竕･ 0.55** 縺ｧ縺ゅｊ縲］o-LoRA ICC 縺ｯ gate
     蜈･蜉帙〒縺ｪ縺・(DA-15 verdict structure 繧定ｸ剰･ｲ)
  2. v2 verdict 縺ｮ `run_phase_3_4.sh` 繧・LoRA-on ICC 縺ｮ縺ｿ險育ｮ励＠縺・     (`compute_big5_icc.py` 蜻ｼ縺ｳ蜃ｺ縺励・ 1 蝗槭・縺ｿ)
  3. SGLang 縺ｯ譛ｬ繧ｻ繝・す繝ｧ繝ｳ縺ｧ kant_r8v3 adapter 繧・load 貂医∬ｿｽ蜉
     setup 荳崎ｦ・- **繝医Ξ繝ｼ繝峨が繝・*:
  - no-LoRA Big-5 荳雋ｫ諤ｧ縺ｯ譛ｬ PR 縺ｧ貂ｬ螳壹＆繧後↑縺・ゅ◆縺縺・Plan B 險ｭ險医〒
    no-LoRA control 縺ｮ ICC 縺ｯ gate 蟇・ｸ弱＠縺ｪ縺・・縺ｧ螳溷ｮｳ縺ｪ縺・  - Codex review 縺ｧ MEDIUM 謖・遭縺ｮ菴吝慍縺ゅｊ: "荳｡ condition 縺ｮ ICC 繧・    荳ｦ蛻怜ｱ蜻翫☆縺ｹ縺・縲よ悽 PR 縺ｧ縺ｯ gate-relevant 謨ｰ蛟､縺ｫ邨槭ｋ
- **蠖ｱ髻ｿ遽・峇**: `scripts/m9-c-adopt/run_plan_b_post_eval.sh` Step 4 縺ｧ
  `compute_big5_icc.py` 縺ｯ LoRA-on 縺ｮ 1 蝗槭・縺ｿ蜻ｼ縺ｶ
- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: Codex MEDIUM 謖・遭縺ｧ no-LoRA ICC 隕∵ｱゅ′蜃ｺ縺・  蝣ｴ蜷医∝挨 PR 縺ｧ `compute_big5_icc.py` 繧定ｿｽ蜉螳溯｡・(~30 min)

## DR-1: kant Plan B verdict = **PHASE_E_A6** (REJECT) 竊・DA-16 ADR (rank=16 spike) 襍ｷ逾ｨ蛟呵｣・
- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: Plan B retrain (kant_r8_v3縲‘val_loss=0.18259縲｜est step 1500)
  縺ｫ蟇ｾ縺玲悽 PR 縺ｧ eval shard 謗｡蜿・+ 4-encoder rescore + Burrows + ICC +
  throughput 繧貞ｮ滓命縲Ａda14-verdict-plan-b-kant.json` 縺ｮ邨先棡:

  | axis | result | gate | comment |
  |---|---|---|---|
  | Encoder agreement | **FAIL** | 3-of-4 primary, 2+ | 0/3 primaries pass all 3 axes; direction discipline FAIL (MPNet 竏・ E5/lex5 +) |
  | Burrows reduction% | **FAIL** | 竕･5pt + CI lower>0 | 竏・.95% (LoRA-on Burrows 114.71 > no-LoRA 112.52) |
  | ICC(A,1) | PASS | 竕･0.55 | 0.9083 |
  | Throughput pct | PASS | 竕･70% | 99.17% |

  Per-encoder natural d:
  - MPNet: 竏・.5264 (negative direction, but std_pass=False due to CI)
  - E5-large: **+0.4781** (opposite sign 窶・retrain shifted Vendi
    semantic 竊・ not 竊・
  - lexical_5gram: +0.1805 (opposite sign)
  - BGE-M3 (exploratory): +0.3317

- **謗｡逕ｨ**: kant ADOPT 繧・REJECT縲￣hase E A-6 (rank=16 spike) 遘ｻ陦後ｒ遒ｺ螳壹・  DA-16 ADR 繧貞挨 PR 縺ｧ襍ｷ逾ｨ縺励〉ank=16 hypothesis (capacity expansion)
  vs corpus tuning (training signal 荳崎ｶｳ) vs WeightedTrainer Blocker 2
  (sample weight collapse縲〉etrain blockers.md 繝悶Ο繝・き繝ｼ 2) 縺ｮ蠖ｱ髻ｿ繧・  蛻・ｊ蛻・￠繧・spike 繧定ｨｭ險医☆繧九・
- **REJECT 譬ｹ蝗莉ｮ隱ｬ**:
  1. **WeightedTrainer sample weight collapse** (retrain Blocker 2縲・     batch_size=1 縺ｧ weight 縺梧焚蟄ｦ逧・↓逶ｸ谿ｺ): DA-14 weighting (de monolog
     蜆ｪ蜈・ 縺・training 荳ｭ縺ｫ蜉ｹ縺・※縺・↑縺九▲縺溷庄閭ｽ諤ｧ縲Ｆval_loss 縺ｯ荳九′繧・     (general loss objective) 縺・DA-14 axis (style/diversity gate) 縺ｯ
     謾ｹ蝟・＠縺ｪ縺・ｵ先棡縺ｨ謨ｴ蜷・  2. **rank=8 capacity 荳崎ｶｳ**: kant 縺ｮ Burrows/style 菫｡蜿ｷ縺ｯ de
     monolog 縺ｫ縺励°縺ｪ縺上〉ank=8 縺ｧ縺ｯ capacity 縺瑚ｶｳ繧翫↑縺・庄閭ｽ諤ｧ縲・     rank=16 縺ｧ蜀・retrain 縺梧ｬ｡縺ｮ繧ｹ繝・ャ繝・(Phase E A-6)
  3. **encoder direction disagreement**: MPNet 雋繝ｻE5/lex5 豁｣縺ｯ
     "Plan B retrain 縺御ｸ驛ｨ縺ｮ encoder 縺ｧ persona shift 繧帝・婿蜷代↓
     隱倡匱" 繧堤､ｺ蜚・Ｓetrain corpus 縺ｮ de_monolog (Akademie-Ausgabe)
     縺・persona style 繧・**MPNet 隕也せ縺ｧ縺ｯ蠑ｷ蛹悶・5/lex5 隕也せ縺ｧ縺ｯ
     dilute** 縺励※縺・ｋ蜿ｯ閭ｽ諤ｧ縲・A-16 spike 險ｭ險域凾縺ｫ corpus 蛻・梵縺悟ｿ・ｦ・
- **蠖ｱ髻ｿ遽・峇**:
  - 譛ｬ PR 螳御ｺ・ｾ後］ietzsche / rikyu 縺ｮ Plan B 螻暮幕繧・**菫晉蕗** (kant
    縺ｧ gate clear 縺ｧ縺阪↑縺・ｻ･荳翫∽ｻ・persona 繧ょ酔讒倥↓繧ｳ繧ｱ繧狗｢ｺ邇・ｫ倥＞)
  - DA-16 ADR 縺ｧ rank=16 spike 繧貞挨 PR 縺ｧ襍ｷ逾ｨ
  - WeightedTrainer Blocker 2 菫ｮ豁｣繧貞挨 PR 縺ｧ **蜆ｪ蜈・* (retrain
    blockers.md 繝悶Ο繝・き繝ｼ 2 縺ｮ證ｫ螳壼ｯｾ蠢懈｡・(a) `compute_loss` 蜀・〒
    weights.sum() 蜑ｲ繧頑綾縺励ｒ豁｢繧√ｋ)

- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**:
  - DA-16 spike (rank=16 retrain) 縺ｮ verdict 縺悟・縺滓凾
  - WeightedTrainer Blocker 2 菫ｮ豁｣蠕後・ retrain verdict 縺悟・縺滓凾
  - 荳願ｨ・2 霆ｸ荳｡譁ｹ縺瑚ｩｦ陦後＆繧後◆蠕後￣lan A (encoder swap-only)
    縺ｨ縺ｮ豈碑ｼ・〒縲罫ank 諡｡螟ｧ vs weighting 菫ｮ豁｣縲阪・縺ｩ縺｡繧峨′蜉ｹ縺上°遒ｺ螳・
## DE-5: Throughput axis 縺ｯ eval-sequence.log 縺九ｉ rate 繧・parse (shard metadata 縺ｫ rate 蛻励↑縺・

- **蛻､譁ｭ譌･譎・*: 2026-05-17
- **閭梧勹**: 蠖灘・ `aggregate_plan_b_axes.py` 縺ｯ shard 縺ｮ
  `raw_dialog.metadata` 繝・・繝悶Ν縺九ｉ `pilot_rate_focal_per_s` 繧定ｪｭ繧
  險ｭ險医□縺｣縺溘′縲《hard 讀懆ｨｼ縺ｧ **metadata 繝・・繝悶Ν閾ｪ菴薙′蟄伜惠縺励↑縺・* 縺薙→縺・  蛻､譏・(`raw_dialog.dialog` + `main.pilot_state` 縺ｮ縺ｿ)縲Ｑilot_state 縺ｫ縺ｯ
  rate 諠・ｱ縺檎┌縺・・- **驕ｸ謚櫁い**:
  - A: `tier_b_pilot.py` 繧呈隼菫ｮ縺励※ shard 縺ｫ rate 繧剃ｿ晏ｭ・(`metadata`
    繝・・繝悶Ν霑ｽ蜉縲×50 陦・diff縲∵悽 PR scope 諡｡螟ｧ)
  - B: eval-sequence.log 繧・parse 縺励※ `pilot done ... elapsed=X.X min
    completed=N` 縺九ｉ rate 繧帝・ｮ・  - C: throughput axis 繧呈悽 PR 縺ｧ縺ｯ skip 縺励※ documented as
    "carried from v2 baseline"
- **謗｡逕ｨ**: B
- **逅・罰**:
  1. `tier_b_pilot.py` 謾ｹ菫ｮ縺ｯ譛ｬ PR scope 螟・(eval generation 縺ｯ scope
     1.2 step 1 縺ｧ蝗ｺ螳壽ｸ医‥river 謾ｹ菫ｮ縺ｪ縺・
  2. eval-sequence.log 縺ｮ `pilot done` 陦後・螳牙ｮ・format (譛ｬ繧ｻ繝・す繝ｧ繝ｳ縺ｧ
     逕滓・縺輔ｌ縺溯｡後ｒ逶ｴ謗･ inspect 貂医・ run 蜈ｨ縺ｦ縺ｧ荳閾ｴ)
  3. throughput pct 縺ｯ cross-condition 豈碑ｼ・〒諢丞袖繧呈戟縺､縲Ｍog parse 縺ｯ
     forensic JSON 縺ｮ domain 諡｡蠑ｵ縺ｫ驕弱℃縺壹」erdict reproducibility 縺ｯ
     菫昴◆繧後ｋ
- **繝医Ξ繝ｼ繝峨が繝・*: log file format 螟画峩縺ｧ aggregator 縺悟｣翫ｌ繧九Μ繧ｹ繧ｯ
  縺ゅｊ (`_shard_focal_rate_from_log` 縺ｯ閼・＞譁・ｭ怜・ split)縲Ａtier_b_pilot.
  py` 縺ｮ log format 繧貞､峨∴繧句挨 PR 縺悟・縺溘ｉ譛ｬ aggregator 繧りｿｽ蠕薙′蠢・ｦ・- **蠖ｱ髻ｿ遽・峇**: `aggregate_plan_b_axes.py::_shard_focal_rate_from_log`縲・  `aggregate_plan_b_axes.py::main` 縺ｮ throughput section
- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: `tier_b_pilot.py` 縺ｮ log format 縺悟､峨ｏ縺｣縺溘→縺・

 succeeded in 476ms:
# 驥崎ｦ√↑險ｭ險亥愛譁ｭ 窶・Plan B retrain prep + 謗｡蜿・+ kickoff

> 譛ｬ file 縺ｯ譛ｬ繧ｻ繝・す繝ｧ繝ｳ蝗ｺ譛峨・ session-local decisions 繧定ｨ倬鹸縺吶ｋ縲・> 讓ｪ譁ｭ ADR 縺ｯ `.steering/20260513-m9-c-adopt/decisions.md`縲￣lan B design
> 蛻､譁ｭ縺ｯ `.steering/20260517-m9-c-adopt-plan-b-design/decisions.md` DI-1縲廛I-8
> 繧貞盾辣ｧ縲・
## DR-1: `_load_default_kernel` 縺ｸ縺ｮ kernel_type dispatch (譌｢蟄・signature 莠呈鋤諤ｧ邯ｭ謖・

- **蛻､譁ｭ譌･譎・*: 2026-05-18
- **閭梧勹**: Plan B design DI-6 縺ｧ縲畦exical-5gram 螳溯｣・・ next-session scope縲・  縺ｨ豎ｺ縺ｾ繧翫∵悽繧ｻ繝・す繝ｧ繝ｳ縺ｧ `vendi.py:_load_default_kernel` 繧呈僑蠑ｵ縺吶ｋ蠢・ｦ√′
  逕溘§縺溘よ里蟄・regression test
  `test_load_default_kernel_signature_accepts_encoder_name` 縺ｯ source 蜀・↓
  `encoder_name or _DEFAULT_ENCODER_MODEL_ID` 譁・ｭ怜・縺後≠繧九％縺ｨ繧・assert 縺吶ｋ縲・- **驕ｸ謚櫁い**:
  - A: `_load_default_kernel(encoder_name=None, *, kernel_type="semantic")`
    縺ｨ縺励※ kwarg 霑ｽ蜉縲〔ernel_type==`"lexical_5gram"` 縺ｧ dispatch
  - B: 蛻･髢｢謨ｰ `_load_lexical_5gram_kernel()` 繧・tier_b/vendi_lexical_5gram.py
    縺ｫ鄂ｮ縺阪…onsumer 蛛ｴ (da1_matrix_multiturn.py) 縺ｧ encoder_name 縺ｫ蠢懊§縺ｦ
    dispatch
  - C: `_load_default_kernel` 繧帝ｫ倬嚴蛹・(factory pattern)
- **謗｡逕ｨ**: A
- **逅・罰**:
  1. Plan B design ﾂｧ1.5 縺ｧ譏取枚蛹悶＆繧後◆ `vendi.py:_load_default_kernel(
     kernel_type=...) 縺九ｉ dispatch` 譁ｹ驥昴↓蜷郁・
  2. 譌｢蟄・source 蜀・・ `encoder_name or _DEFAULT_ENCODER_MODEL_ID` 陦後ｒ
     菫晄戟縺ｧ縺阪ｋ (regression test green-keep)
  3. kwarg-only 縺ｫ縺吶ｋ縺薙→縺ｧ positional callers (Plan A pipeline) 繧剃ｸ榊､・     縺ｮ縺ｾ縺ｾ縲∵眠 dispatch path 繧・opt-in 縺ｫ縺ｧ縺阪ｋ
- **繝医Ξ繝ｼ繝峨が繝・*: kernel_type 縺ｫ霑ｽ蜉蛟､ (萓・ byte-pair) 繧定ｶｳ縺呎凾縺ｫ signature
  縺瑚ぇ螟ｧ蛹悶☆繧九Μ繧ｹ繧ｯ縲ょｰ・擂 3 莉･荳翫↓蛻・ｲ舌☆繧九↑繧・C (factory) 繧貞・閠・・- **蠖ｱ髻ｿ遽・峇**: vendi.py + vendi_lexical_5gram.py + 譌｢蟄・test 荳榊､峨∵眠隕・  test 1 莉ｶ霑ｽ蜉縲・- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: 谺｡縺ｮ Plan (C 遲・ 縺ｧ蛻･ kernel family 縺瑚ｿｽ蜉縺輔ｌ繧区凾縲・
## DR-2: 譌｢蟄・`make_lexical_5gram_kernel` (Jaccard) 縺ｨ譁ｰ `vendi_lexical_5gram.py` (TF-IDF cosine) 繧貞・蟄・
- **蛻､譁ｭ譌･譎・*: 2026-05-18
- **閭梧勹**: `vendi.py` 縺ｫ縺ｯ譌｢縺ｫ `make_lexical_5gram_kernel` (P4b sensitivity
  panel 縺ｧ菴ｿ縺・Jaccard kernel) 縺悟ｮ溯｣・＆繧後※縺・ｋ縲１lan B D-2 allowlist 縺ｮ
  `lexical_5gram` primary 縺ｯ char 5-gram **cosine** kernel 縺ｨ譖ｸ縺九ｌ縺ｦ縺・ｋ縲・  Jaccard 縺ｨ cosine 縺ｧ縺ｯ謨ｰ蛟､諤ｧ雉ｪ縺檎焚縺ｪ繧・(Jaccard 縺ｯ髮・粋縺ｮ overlap縲…osine
  縺ｯ TF-IDF weighting 霎ｼ縺ｿ縺ｮ蜀・ｩ・縲・- **驕ｸ謚櫁い**:
  - A: Jaccard 繧・deprecate 縺励※ cosine 縺ｫ邨ｱ荳
  - B: 蛻･繝｢繧ｸ繝･繝ｼ繝ｫ `vendi_lexical_5gram.py` 縺ｫ cosine 繧貞・髮｢縲゛accard 縺ｯ
    P4b sensitivity panel 逕ｨ縺ｫ retain
- **謗｡逕ｨ**: B
- **逅・罰**:
  1. P4b sensitivity panel 縺ｯ譌｢蟄・baseline 縺ｧ繝ｬ繝昴・繝域ｸ医∩ (`test_vendi_
     kernel_sensitivity_panel_shape_matches_weights` 縺御ｾ晄侠)
  2. d2-encoder-allowlist-plan-b.json 縺ｮ `implementation_module` 縺・     `erre_sandbox.evidence.tier_b.vendi_lexical_5gram` 縺ｨ譏守､ｺ pre-register
     縺輔ｌ縺ｦ縺・ｋ
  3. Plan A 縺ｮ P4b 騾｣邯壽ｧ (`hybrid-X-Y` kernel name) 繧堤ｴ螢翫＠縺ｪ縺・- **繝医Ξ繝ｼ繝峨が繝・*: 縲畦exical_5gram縲阪→縺・≧蜷榊燕縺ｧ 2 縺､縺ｮ kernel 縺悟ｭ伜惠縺吶ｋ
  豺ｷ荵ｱ縺ｮ菴吝慍縲よ悽 file 縺ｧ譏守､ｺ蛻・屬縺吶ｋ縺薙→縺ｧ future reader 縺梧ｷｷ荵ｱ縺励↑縺・・- **蠖ｱ髻ｿ遽・峇**: `make_lexical_5gram_kernel` (Jaccard) 縺ｯ P4b panel 蟆ら畑縲・  Plan B verdict 險育ｮ励〒縺ｯ菴ｿ繧上↑縺・Ａmake_tfidf_5gram_cosine_kernel`
  (譁ｰ) 縺・Plan B D-2 primary縲・- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: Plan B verdict 螳御ｺ・ｾ後゛accard 繧・deprecate 縺吶ｋ縺・  retain 縺吶ｋ縺句挨 PR 縺ｧ蜀崎ｩ穂ｾ｡縲・
## DR-4: SGLang 襍ｷ蜍・invocation 繧・`--quantization fp8 --max-total-tokens 2048 --max-running-requests 1 --disable-cuda-graph --disable-piecewise-cuda-graph` 縺ｫ遒ｺ螳・(Blackwell SM120 + Qwen3-8B + 16 GB VRAM)

- **蛻､譁ｭ譌･譎・*: 2026-05-16 (譛ｬ繧ｻ繝・す繝ｧ繝ｳ縲ヾGLang 襍ｷ蜍・blocker 隗｣豎ｺ蠕・
- **閭梧勹**: Plan B next-session prompt 縺ｫ蠕薙▲縺ｦ
  `python -m sglang.launch_server --model-path Qwen/Qwen3-8B --host 0.0.0.0
  --port 30000 --mem-fraction-static 0.85 --chunked-prefill-size 8192
  --max-running-requests 8 --disable-cuda-graph` 縺ｧ襍ｷ蜍・竊・BF16 縺ｧ OOM
  sigquit縲Ｇp8 quant + max-total-tokens 2048 + max-running-requests 1
  霑ｽ蜉縺ｧ襍ｷ蜍墓・蜉溘☆繧九ｂ縲＿wen3-8B 繧ｵ繝ｳ繝励Μ繝ｳ繧ｰ (argmax CUDA kernel) 縺・  hang 竊・watchdog timeout 300s 縺ｧ蜀・sigquit縲・- **隧ｦ縺励◆縺薙→**:
  1. K-ﾎｱ launch v5 invocation (`--quantization fp8 --max-total-tokens 2048
     --max-running-requests 1 --disable-cuda-graph`) 竊・server up + chat
     warmup OK 縺縺・driver chat 譎ゅ↓ sampler argmax CUDA kernel deadlock
  2. `--disable-piecewise-cuda-graph` 繧定ｿｽ蜉 竊・ready 蠕・micro smoke
     (3 net縲・ attempts縲・0.9s elapsed縲∥cceptance 37.5%縲×7.5s/attempt
     throughput) PASS縲‥river chat 繧ょ撫鬘後↑縺・- **謗｡逕ｨ**: SGLang launch invocation 繧剃ｻ･荳九↓遒ｺ螳・
  ```
  PYTHONUTF8=1 python -m sglang.launch_server \
      --model-path Qwen/Qwen3-8B \
      --host 0.0.0.0 --port 30000 \
      --quantization fp8 \
      --mem-fraction-static 0.85 \
      --max-total-tokens 2048 \
      --max-running-requests 1 \
      --disable-cuda-graph \
      --disable-piecewise-cuda-graph
  ```
- **逅・罰**:
  1. Qwen3-8B BF16 竕・16 GB 縺ｯ 16 GB VRAM 縺ｫ髱咏噪縺ｫ fit 縺帙★ 竊・fp8 蠢・・  2. RTX 5060 Ti = Blackwell SM120 縺ｧ SGLang 0.5.10.post1 縺ｮ piecewise
     CUDA graph capture 縺・sampler.argmax 繧・deadlock 縺輔○繧・     (`scheduler.py:1361 event_loop_overlap` 竊・`forward_batch_generation`
     竊・`sample` 竊・`forward (sampler.py:107)` 竊・`argmax` CUDA kernel 縺・     hang 縺励※ watchdog timeout) 竊・`--disable-piecewise-cuda-graph` 縺ｧ
     蝗樣∩
  3. throughput ~7.5s/attempt 縺ｯ dry-run smoke 縺ｮ險ｱ螳ｹ遽・峇 (50 net @
     37.5% acceptance 竕・17 min縲・50 net main collection 竕・~83 min縲∝ｽ灘・
     runbook 諠ｳ螳・3h 繧医ｊ騾溘＞)
- **繝医Ξ繝ｼ繝峨が繝・*:
  - CUDA graphs disable 縺ｧ peak throughput 縺ｯ繧・ｄ菴惹ｸ九☆繧九′縲。lackwell
    + fp8 邨瑚ｷｯ縺ｮ螳牙ｮ壽ｧ縺檎｢ｺ菫昴〒縺阪ｋ縺ｮ縺ｧ謗｡蜿悶・螳瑚ｵｰ蜿ｯ閭ｽ
  - Codex review 遲峨〒縲悟・ CUDA graph optimisation disable 縺ｯ蠢・ｦ√°縲阪→
    謖・遭縺輔ｌ繧句庄閭ｽ諤ｧ縺ゅｊ縲ょ・菴鍋噪縺ｫ縺ｯ piecewise 縺縺・disable 縺ｧ蜊∝・縺九・
    莉雁屓譎る俣蛻ｶ邏・〒蛟句挨讀懆ｨｼ縺励※縺・↑縺・(`--disable-piecewise-cuda-graph`
    + cuda-graph enable 縺ｮ邨・∩蜷医ｏ縺帙・譛ｪ隧ｦ陦・縲よｬ｡繧ｻ繝・す繝ｧ繝ｳ縺ｧ `+`
    cuda-graph enable + piecewise disable 繧・benchmark 縺吶ｋ菴吝慍縺ゅｊ縲・- **蠖ｱ髻ｿ遽・峇**:
  - 譛ｬ繧ｻ繝・す繝ｧ繝ｳ縺ｮ dry-run smoke + main collection + 谺｡蝗・retrain serving
    襍ｷ蜍輔さ繝槭Φ繝・(Plan B 謗｡蜿悶・ base model 縺ｪ縺ｮ縺ｧ LoRA enable 縺ｯ荳崎ｦ・
  - `g-gear-collection-runbook.md` ﾂｧ2 縺ｮ SGLang launch command 繧ょ酔
    invocation 繧呈治逕ｨ (Plan B / future plan 縺ｧ蜀榊茜逕ｨ)
  - memory `reference_qwen3_sglang_fp8_required.md` 繧剃ｽ懈・縲｝roject 讓ｪ譁ｭ
    縺ｧ蜿ら・蜿ｯ閭ｽ縺ｫ
- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: 
  - SGLang 0.5.11+ release 縺ｧ Blackwell piecewise CUDA graph 縺御ｿｮ豁｣縺輔ｌ縺滓凾
  - GPU 縺御ｺ､謠帙＆繧後◆譎・(Blackwell 莉･螟悶↑繧牙ｾ捺擂 v5 invocation 縺ｧ蜊∝・)

## DR-5: WeightedTrainer.compute_loss 縺九ｉ ``labels`` 繧・pop 縺・HF 蜀・Κ CE 驥崎､・ｨ育ｮ励ｒ蛛懈ｭ｢

- **蛻､譁ｭ譌･譎・*: 2026-05-18
- **閭梧勹**: v2 retrain (DI-7) 縺ｧ step time 縺悟・譛・5.35 s/it 竊・螳壼ｸｸ ~13窶・4 s/it
  縺ｫ蜉｣蛹悶・000 steps 繧・8h envelope 縺ｫ蜿弱ａ繧峨ｌ縺・16h19m 繧定ｦ√＠縺溘・  `src/erre_sandbox/training/train_kant_lora.py:WeightedTrainer.compute_loss`
  (L1690窶・704) 繧定ｪｭ繧縺ｨ縲～labels` 繧・`inputs` 縺ｫ谿九＠縺溘∪縺ｾ `model(**inputs)`
  繧貞他繧薙〒縺翫ｊ縲？F CausalLM 縺悟・驛ｨ縺ｧ cross-entropy loss 繧定ｨ育ｮ励☆繧九よ悽螳溯｣・・
  邯壹￠縺ｦ `compute_weighted_causal_lm_loss(outputs.logits, inputs["labels"],
  weights)` 縺ｧ蜷後§ logits/labels 縺ｫ蟇ｾ縺励※ weighted CE 繧貞・險育ｮ励＠縺ｦ縺・ｋ縺溘ａ縲・  蜀・Κ loss 縺ｯ螳悟・縺ｫ discard 縺輔ｌ縺ｦ縺・ｋ縲・- **蜑ｯ菴懃畑縺ｮ隕狗ｩ阪ｂ繧・*:
  - Qwen3-8B vocab=151936 縺ｧ蜀・Κ CE 縺檎｢ｺ菫昴☆繧・`shift_logits` 荳ｭ髢・tensor 縺ｯ
    seq=128 / bf16 謠帷ｮ励〒 micro-batch 蠖薙◆繧・~38 MB
  - grad_accum=8 竊・train step 蠖薙◆繧・~300 MB / eval 1 pass (503 examples) 竊・    ~19 GB 縺ｫ驕斐☆繧倶ｽ吝臆 intermediate
  - DI-7 譎らせ VRAM 15973/16311 MiB (free 78 MiB) 縺ｧ allocator slow path 縺ｫ
    關ｽ縺｡縺滉ｻｮ隱ｬ縺ｨ謨ｴ蜷・- **驕ｸ謚櫁い**:
  - A: `inputs.pop("labels")` 縺ｧ labels 繧貞叙繧雁・縺励※縺九ｉ `model(**inputs)` 繧・    蜻ｼ縺ｳ縲～compute_weighted_causal_lm_loss` 縺ｫ縺ｯ local 縺ｮ `labels` 繧呈ｸ｡縺・  - B: `model.forward()` 繧・override 縺励※蜀・Κ CE 繧呈椛豁｢
  - C: `Trainer` 縺ｮ `compute_loss_func` API (Transformers 4.46+) 縺ｫ蛻・崛
- **謗｡逕ｨ**: A
- **逅・罰**:
  1. 3 陦・diff縲〕oss 謨ｰ蠑上・autograd graph繝ｻgradient 縺ｯ荳榊､・(`compute_weighted_
     causal_lm_loss` 縺ｯ Codex HIGH-C verbatim縲∝・蜉・tensors 縺ｯ蜷後§)
  2. HF CausalLM 縺ｮ `forward(..., labels=None)` 縺ｯ `output.loss=None` 縺ｧ霑斐ｋ縺・     `output.logits` 縺ｯ螟峨ｏ繧峨↑縺・竊・`compute_weighted_causal_lm_loss` 縺ｸ縺ｮ
     蜈･蜉帙↓蜑ｯ菴懃畑縺ｪ縺・  3. B 縺ｯ GPL-3.0 risk 縺ｨ菫晏ｮ医さ繧ｹ繝医， 縺ｯ subclass 繝代ち繝ｼ繝ｳ蜈ｨ蟒・〒 diff 驕主､ｧ
- **繝医Ξ繝ｼ繝峨が繝・*:
  - HF Trainer 縺ｮ `prediction_step` 縺ｯ `compute_loss(model, inputs,
    return_outputs=True)` 繧貞他縺ｶ縺溘ａ縲～return_outputs=True` 邨瑚ｷｯ縺ｧ繧・    `(weighted_loss, outputs)` 繧定ｿ斐○繧句ｿ・ｦ√′縺ゅｋ縺後∵眠 compute_loss 縺ｯ
    蠑輔″邯壹″蜷後§ tuple 繧定ｿ斐☆縺溘ａ API contract 縺ｯ荳榊､・- **蠖ｱ髻ｿ遽・峇**:
  - `_run_trainer_weighted` 縺ｮ `WeightedTrainer` 蜀・compute_loss 縺ｮ縺ｿ
  - 譌｢蟄・`tests/test_training/test_weighted_trainer.py` 縺ｯ `compute_weighted_
    causal_lm_loss` 縺ｮ pure function 繧堤峩謗･蜻ｼ縺ｶ縺溘ａ縲∵悽繝代ャ繝√↓蟇ｾ縺吶ｋ
    regression 繧定ｵｷ縺薙＆縺ｪ縺・(45 莉ｶ PASS 螳滓ｸｬ)
  - DA-14 thresholds / weighting 謨ｰ蠑・/ DA-15 corpus gate / eval criteria 縺ｯ
    荳蛻・､画峩縺励↑縺・- **譛ｪ遒ｺ螳・*: 螳・runtime 謾ｹ蝟・ｹ・・譛ｬ繧ｻ繝・す繝ｧ繝ｳ縺ｧ譛ｪ貂ｬ螳壹・-GEAR 縺ｧ
  `--weighted --max-steps 50 --save-steps 100000 --eval-steps 100000` 縺ｮ
  蜑榊ｾ梧ｯ碑ｼ・′蠢・ｦ√・- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: Plan B retrain benchmark 蠕後∵隼蝟・ｹ・′諠ｳ螳壻ｸ矩剞
  (謨ｰ%) 繧剃ｸ句屓繧・Plan B envelope 縺ｫ蜿弱∪繧峨↑縺・ｴ蜷医ヽ-3 (NF4+LoRA backward
  slow path 莉ｮ隱ｬ) 縺ｮ蜀崎ｩ穂ｾ｡縲・
## DR-6: TrainingArguments 縺ｫ `prediction_loss_only=True` 繧呈・遉ｺ (蜑ｯ繝代ャ繝・

- **蛻､譁ｭ譌･譎・*: 2026-05-18
- **閭梧勹**: HF Trainer 縺ｮ eval 縺ｯ default `prediction_loss_only=False`縲・  `compute_metrics=None` 縺ｮ縺ｨ縺阪・ Trainer 螳溯｣・↓繧医▲縺ｦ logits accumulation 繧・  蜀・Κ縺ｧ謚大宛縺励※縺・ｋ蜿ｯ閭ｽ諤ｧ繧ゅ≠繧九′縲∵・遉ｺ逧・↓ True 繧堤ｫ九※繧後・ short-circuit
  邨瑚ｷｯ縺檎｢ｺ螳溘↓蜿悶ｉ繧後ｋ縲１lan B `EarlyStoppingCallback(metric_for_best_model="eval_loss")` 縺ｯ eval_loss 縺ｮ縺ｿ繧貞盾辣ｧ縺吶ｋ縺溘ａ縲∝憶菴懃畑縺ｪ縺励・- **謗｡逕ｨ**: TrainingArguments 縺ｮ eval_kwargs 縺ｫ `prediction_loss_only=True`
  繧定ｿｽ蜉 (`per_device_eval_batch_size=1` 縺ｨ蜷・dict)
- **逅・罰**:
  1. DR-5 縺ｨ迢ｬ遶九↓蜉ｹ縺丞庄閭ｽ諤ｧ縺ｮ縺ゅｋ eval-side 縺ｮ蟆乗怙驕ｩ蛹・  2. 1 陦瑚ｿｽ蜉縲〉evert 繧ｳ繧ｹ繝医・譛蟆・  3. eval_loss 縺ｯ蠑輔″邯壹″ `metrics["eval_loss"]` 縺ｧ蜿門ｾ怜庄閭ｽ縲～train_metadata.json` 縺ｸ縺ｮ險倬鹸邨瑚ｷｯ繝ｻEarlyStoppingCallback 邨瑚ｷｯ縺ｫ蜑ｯ菴懃畑縺ｪ縺・  4. Transformers 4.57.6 (AGENTS.md) 縺ｧ `prediction_loss_only` 縺ｯ螳牙ｮ・API
- **謗ｧ縺医ａ縺ｪ隕狗ｩ阪ｂ繧・*:
  - HF Trainer 縺ｮ version / 螳溯｣・ｬ｡隨ｬ縺ｧ `compute_metrics=None` 譎ゅ↓縺ｯ譌｢縺ｫ蜷檎ｭ・    蜍穂ｽ懊・蜿ｯ閭ｽ諤ｧ繧ゅ≠繧翫・*縲悟ｿ・★ eval 30窶・0% 謾ｹ蝟・阪→縺ｯ諠ｳ螳壹＠縺ｪ縺・*
  - 蜉ｹ譫懊・ short eval benchmark (荳ｻ繝代ャ繝∝腰迢ｬ vs 荳ｻ+蜑ｯ繝代ャ繝・ 縺ｧ遒ｺ隱・- **繝医Ξ繝ｼ繝峨が繝・*: 蟆・擂 compute_metrics (BLEU / perplexity 遲・ 繧貞ｰ主・縺吶ｋ
  譎ゅ↓縺ｯ `False` 縺ｫ謌ｻ縺吝ｿ・ｦ√′縺ゅｋ縺後√◎縺ｮ譎らせ縺ｧ revisit縲・- **蠖ｱ髻ｿ遽・峇**: TrainingArguments 縺ｮ eval_kwargs dict 縺ｮ縺ｿ縲Ｇinal
  `trainer.evaluate()` 縺ｯ荳榊､峨‘val_loss 險倬鹸縺ｮ菫｡鬆ｼ諤ｧ繧貞━蜈医・- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: short benchmark 縺ｧ蟾ｮ縺瑚ｦ九∴縺ｪ縺・ｴ蜷医∝挨 PR 縺ｧ
  `prediction_loss_only` 陦後・縺ｿ revert (荳ｻ繝代ャ繝√・邯ｭ謖・縲・
## DR-7: 譛ｬ繧ｻ繝・す繝ｧ繝ｳ螳御ｺ・渕貅・ 蛻晏屓 eval (step 250) 縺ｧ eval_loss=0.2582 (驕疲・縲〉etrain 縺ｯ WSL2 background 縺ｧ邯咏ｶ・

- **蛻､譁ｭ譌･譎・*: 2026-05-16 (譛ｬ繧ｻ繝・す繝ｧ繝ｳ譛ｫ)
- **閭梧勹**: next-session prompt 縺ｮ螳御ｺ・擅莉ｶ縲罫etrain kickoff command 襍ｷ蜍輔・  譛蛻昴・ checkpoint 縺ｧ `eval_loss < initial`縲阪ｒ貅縺溘＠縺滓凾轤ｹ縺ｧ譛ｬ繧ｻ繝・す繝ｧ繝ｳ繧・  蛛懈ｭ｢縺吶ｋ縲Ｓetrain (~3h) 縺ｮ螳瑚ｵｰ縺ｯ overnight縲」erdict 險育ｮ励・谺｡縲・そ繝・す繝ｧ繝ｳ縲・- **謗｡逕ｨ**: 蛻晏屓 eval 驕疲・譎らせ縺ｧ譛ｬ繧ｻ繝・す繝ｧ繝ｳ螳御ｺ・→縺ｿ縺ｪ縺励…ommit + push縲・  retrain 繝励Ο繧ｻ繧ｹ (PID 387 in WSL2) 縺ｯ session 邨ゆｺ・ｾ後ｂ邯咏ｶ壹・- **螳滓ｸｬ蛟､** (譛ｬ繧ｻ繝・す繝ｧ繝ｳ譛ｫ譎らせ):
  - 蛻晏屓 eval (step 250): `eval_loss=0.2582`縲～eval_runtime=99.53s`縲・    `epoch=0.1756`
  - step pace: ~4 s/it (v2 baseline 14 s/it 縺九ｉ **3.3ﾃ・鬮倬溷喧**縲・    DR-5/DR-6 patch 螳溷柑)
  - ETA full retrain: ~2h47m (v2 縺ｮ 16h19m 縺九ｉ **5.8ﾃ・鬮倬溷喧**)
- **逅・罰**:
  1. `eval_loss=0.258 < initial loss (竕・2.0-2.5 for Qwen3-8B base)`縲・     蟄ｦ鄙偵′蜿取據譁ｹ蜷代↓騾ｲ繧薙〒縺・ｋ遒ｺ隱肴ｸ・  2. step pace stable 縺ｧ early stopping fire / OOM / crash 縺ｮ蜈・吶↑縺・  3. session 4.5-5h envelope 蜀・〒螳御ｺ・(譛ｬ繧ｻ繝・す繝ｧ繝ｳ ~3h50m縲》arget 4.5h
     莉･蜀・
- **蠖ｱ髻ｿ遽・峇**: 谺｡縲・そ繝・す繝ｧ繝ｳ縺ｧ `train_metadata.json` 縺ｮ eval_loss trajectory
  繧定ｪｭ縺ｿ縲｜est checkpoint 繧剃ｽｿ縺｣縺ｦ DA-14 rerun verdict 繧定ｨ育ｮ励☆繧九・- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: retrain 縺碁比ｸｭ縺ｧ abort 縺励◆蝣ｴ蜷医∵悽蛻､譁ｭ繧呈彫蝗槭＠
  retrain 蜀崎ｵｷ蜍輔ｒ蛻･ session 縺ｧ螳滓命縲・
## DR-3: lexical-5gram 縺ｮ遏ｭ蜈･蜉・(char_wb 5-gram empty vocab) fallback 縺ｯ identity

- **蛻､譁ｭ譌･譎・*: 2026-05-18
- **閭梧勹**: `TfidfVectorizer(analyzer="char_wb", ngram_range=(5,5))` 縺ｯ蜈ｨ
  蜈･蜉帙′ 5 譁・ｭ玲悴貅縺ｧ edge-pad 蠕後ｂ 5-gram 繧堤肇縺ｾ縺ｪ縺・凾縺ｫ遨ｺ vocabulary 縺ｧ
  `ValueError("empty vocabulary")` 繧・raise 縺吶ｋ縲・- **驕ｸ謚櫁い**:
  - A: ValueError 繧・propagate (caller 雋ｬ莉ｻ)
  - B: empty vocab 繧・try/except 縺ｧ蜿励￠ identity 陦悟・繧定ｿ斐☆ (no similarity
    signal 縺ｨ縺ｿ縺ｪ縺・
  - C: zeros 陦悟・繧定ｿ斐☆ (`_check_kernel` 縺ｮ diagonal=1 assert 縺ｧ螟ｱ譬ｼ)
- **謗｡逕ｨ**: B
- **逅・罰**:
  1. `compute_vendi` 邨檎罰縺ｧ蜻ｼ縺ｰ繧後◆譎ゅ↓ identity 陦悟・縺ｪ繧・score=N 縺ｨ縺ｿ縺ｪ縺輔ｌ
     繧・("each item is fully distinct") 縺ｮ縺梧э蜻ｳ逧・↓謨ｴ蜷・  2. 謗｡蜿悶＆繧後◆ focal turn 縺ｯ騾壼ｸｸ 竕･60 token (filter 貂医∩) 縺ｪ縺ｮ縺ｧ boundary
     case 縺ｯ test fixture 縺ｧ縺励°隗ｦ繧後↑縺・  3. C 縺ｯ `_check_kernel` 縺ｧ diagonal!=1 縺ｧ螟ｱ譬ｼ縺ｫ縺ｪ繧・- **繝医Ξ繝ｼ繝峨が繝・*: 縲悟・ sample 縺檎洒縺・竊・score=N 縺ｧ diversity 譛螟ｧ縲阪・隱､隗｣
  諡帙￥縺後￣lan B 縺ｧ縺ｯ token>=60 filter 縺後≠繧九・縺ｧ production 縺ｧ縺ｯ蛻ｰ驕比ｸ崎・
- **蠖ｱ髻ｿ遽・峇**: 譁ｰ test `test_short_inputs_below_5_chars_fallback_identity`
  縺ｧ縺薙・謖吝虚繧呈・譁・喧縲｝roduction 縺ｧ縺ｯ filter 縺ｧ髯､螟悶＆繧後ｋ譌ｨ繧・docstring 縺ｫ險倩ｼ・

 succeeded in 429ms:
# 繝悶Ο繝・き繝ｼ險倬鹸

## 繝悶Ο繝・き繝ｼ 1: SGLang 蛻晏屓襍ｷ蜍・OOM (BF16 縺ｧ Qwen3-8B 縺・16 GB VRAM 縺ｫ fit 縺帙★)

- **逋ｺ逕滓律譎・*: 2026-05-16 13:49 JST
- **逞・憾**: Plan B next-session prompt 騾壹ｊ
  `python -m sglang.launch_server --model-path Qwen/Qwen3-8B --host 0.0.0.0
  --port 30000 --mem-fraction-static 0.85 --chunked-prefill-size 8192
  --max-running-requests 8 --disable-cuda-graph` 繧定ｵｷ蜍・竊・shards loading 蠕・  `RuntimeError: Not enough memory. Please try to increase
  --mem-fraction-static. Current value: mem_fraction_static=0.85` 竊・  child sigquit 縺ｧ server 蛛懈ｭ｢
- **隧ｦ縺励◆縺薙→**:
  1. K-ﾎｱ report (`.steering/20260508-m9-c-spike/k-alpha-report.md`) 縺ｮ launch
     v5 invocation 繧堤｢ｺ隱・窶・`--quantization fp8` + `--max-total-tokens 2048`
     + `--max-running-requests 1` 縺・empirical 縺ｫ蠢・医→蛻､譏・  2. `scripts/m9-c-spike/launch_sglang.sh` 縺ｮ蜿ら・ 窶・fp8 quant + LoRA enable
     莉倥″縺梧里蟄倬°逕ｨ蠖｢諷・- **蜴溷屏**: Plan B next-session prompt 縺ｫ蜷ｫ縺ｾ繧後ｋ SGLang command 縺・BF16
  default (`dtype="auto"`) 縺ｧ縺ゅｊ縲＿wen3-8B (竕・16 GB BF16) 縺・  16 GB VRAM 縺ｮ RTX 5060 Ti 縺ｫ髱咏噪縺ｫ fit 縺励↑縺・Ａmem-fraction-static`
  繧剃ｸ翫￡縺ｦ繧・KV cache + activations 縺ｮ菴呵｣輔′縺ｪ縺・fail 縺吶ｋ縲・- **隗｣豎ｺ譁ｹ豕・*: K-ﾎｱ report 縺ｮ launch v5 invocation 縺ｫ貅匁侠縺励・  `--quantization fp8 --max-total-tokens 2048 --max-running-requests 1`
  繧定ｿｽ蜉縺励※蜀崎ｵｷ蜍・(LoRA enable 縺ｯ Plan B 謗｡蜿悶・ base model 縺ｮ縺溘ａ逵∫払)縲・  PID 395 縺ｧ蜀崎ｵｷ蜍墓・蜉溘・- **謨呵ｨ・*:
  - Qwen3-8B + 16 GB VRAM SGLang 襍ｷ蜍輔・ **蟶ｸ縺ｫ fp8 蠢・・*縲１lan B / Plan C
    / 蠕檎ｶ壹そ繝・す繝ｧ繝ｳ縺ｮ handoff prompt 縺ｫ繧・`--quantization fp8 --max-total-
    tokens 2048 --max-running-requests 1` 繧呈・譁・喧縺吶ｋ
  - K-ﾎｱ report 縺ｮ launch v5 縺悟腰荳 source of truth縲￣lan A / Plan B handoff
    縺ｮ SGLang command 縺ｯ launch v5 縺九ｉ **delta 縺縺第嶌縺・* 驕狗畑縺ｫ謠・∴繧・  - memory `qwen3:8b + Ollama gotchas` 縺ｨ荳ｦ蛻励・ SGLang 繝｡繝｢繝ｪ memo 繧定ｵｷ縺薙☆
    蛟呵｣・(譛ｬ PR 縺ｮ reflection 縺ｧ讀懆ｨ・

## 繝悶Ο繝・き繝ｼ 2: WeightedTrainer 縺ｮ sample weight 縺・batch_size=1 縺ｧ讒矩逧・↓逶ｸ谿ｺ縺輔ｌ繧狗桝縺・(譛ｬ PR 縺ｧ縺ｯ譛ｪ菫ｮ豁｣縲∝挨 issue 縺ｨ縺励※險倬鹸縺ｮ縺ｿ)

- **逋ｺ逕滓律譎・*: 2026-05-18 (DR-5 荳ｻ繝代ャ繝∬ｪｿ譟ｻ荳ｭ縺ｫ豢ｾ逕溽匱隕・
- **逞・憾**: `compute_weighted_causal_lm_loss` (`src/erre_sandbox/training/weighting.py:411`) 縺ｯ
  ```
  (per_example_loss * weights).sum() / torch.clamp(weights.sum(), min=1e-8)
  ```
  縺ｧ reduce 縺吶ｋ縲Ａper_device_train_batch_size=1` 縺ｧ micro-batch 繧剃ｽ懊ｋ縺ｨ
  `per_example_loss` shape 縺ｯ `(1,)`縲～weights` shape 繧・`(1,)` 縺ｧ縲・  `(per_example_loss[0] * w) / w = per_example_loss[0]` 縺ｨ weight 縺・  謨ｰ蟄ｦ逧・↓逶ｸ谿ｺ縺輔ｌ繧九・- **gradient_accumulation_steps=8 縺ｧ繧ょ撫鬘・*: HF Trainer 縺ｯ蜷・micro-batch
  迢ｬ遶九↓ `loss / grad_accum` 繧・backward 縺吶ｋ縺溘ａ縲［icro-batch 蜀・〒
  weight 繧・normalise 縺吶ｋ迴ｾ螳溯｣・〒縺ｯ weight 蜉ｹ譫懊′蜈ｨ step 縺ｧ豸亥､ｱ縺励※縺・ｋ
  蜿ｯ閭ｽ諤ｧ縺後≠繧九・- **蠖ｱ髻ｿ莉ｮ隱ｬ**: DA-14 weighting (`compute_example_weight`縲…oefficient
  0.35/0.20/0.15/0.30縲］ormalise to mean=1) 縺ｯ謗｡逕ｨ縺励◆縺後∝ｮ・training 荳翫・
  unweighted average 縺ｨ遲我ｾ｡縺ｫ謖ｯ繧玖・縺｣縺ｦ縺・◆蜿ｯ閭ｽ諤ｧ縲・A-14 verdict REJECT
  縺ｮ蜴溷屏縺ｮ荳縺､縺後詣eighting 縺悟柑縺・※縺・↑縺・阪□縺｣縺溷庄閭ｽ諤ｧ繧ょ凄螳壹〒縺阪↑縺・・- **譛ｬ PR 縺ｧ縺ｯ**: 蜉ｹ邇・喧縺ｧ縺ｯ縺ｪ縺丞ｭｦ鄙呈э蜻ｳ隲悶・蛻･ issue縲よ悽 PR (DR-5 / DR-6
  WeightedTrainer 蜉ｹ邇・喧) 縺ｧ縺ｯ菫ｮ豁｣縺励↑縺・・- **證ｫ螳壼ｯｾ蠢懈｡・(險倬鹸縺ｮ縺ｿ縲∵悽 PR scope 螟・**:
  - 蛟呵｣・(a): `compute_loss` 蜀・〒 `per_example_loss[0] * weights[0]` 繧・    霑斐☆ (`weights.sum()` 縺ｧ縺ｮ蜑ｲ繧頑綾縺励ｒ豁｢繧√｜atch=1 縺ｧ繧・weight 縺・    蜍ｾ驟・magnitude 縺ｫ逶ｴ謗･荵励ｋ蠖｢)縲ゅ◆縺縺励％繧後・ batch>=2 縺ｮ繧ｻ繝槭Φ繝・ぅ繧ｯ繧ｹ
    螟画峩繧剃ｼｴ縺・◆繧∝挨騾疲､懆ｨ・  - 蛟呵｣・(b): `gradient_accumulation_steps` 繧ｹ繧ｳ繝ｼ繝励〒 micro-batch 縺ｮ
    weight 繧貞粋邂励＠縺ｦ縺九ｉ豁｣隕丞喧 (HF Trainer 縺ｮ callback hook 縺ｧ螳溯｣・
  - 蛟呵｣・(c): `per_device_train_batch_size>=2` 縺ｮ VRAM-friendly 縺ｪ讒区・
    繧呈爾邏｢ (Qwen3-8B + NF4 + rank=8 縺ｧ batch=2 縺御ｹ励ｋ縺玖ｦ・spike縲∫樟迥ｶ
    DI-7 縺ｧ縺ｯ VRAM 98% 縺ｧ縺ｻ縺ｼ辟｡逅・
- **蜆ｪ蜈亥ｺｦ蛻､譁ｭ縺ｮ繧ｿ繧､繝溘Φ繧ｰ**: Plan B retrain 縺ｮ DA-14 rerun verdict 縺悟・縺・  譎らせ縲Ｗerdict ADOPT 縺ｪ繧画悽 issue 繧剃ｿ晉蕗縲ヽEJECT 縺ｪ繧画悽 issue 縺ｮ
  fix 繧貞━蜈・(DA-14 縺・weight 荳咲匱縺ｮ縺ｾ縺ｾ縺縺｣縺溘°繧貞・繧雁・縺代ｋ縺溘ａ)縲・- **謨呵ｨ・*:
  - per-example loss reduction 繧貞ｮ溯｣・☆繧区凾縲｜atch=1 縺ｨ grad_accum>1 繧・    邨・∩蜷医ｏ縺帙ｋ縺ｨ weight 縺檎嶌谿ｺ縺輔ｌ繧区ｧ矩逧・ヰ繧ｰ繧堤函縺ｿ繧・☆縺・・odex
    HIGH-C verbatim 謨ｰ蠑上・ batch>=2 繧呈囓鮟吝燕謠舌＠縺ｦ縺・◆縺後〃RAM 蛻ｶ邏・〒
    batch=1 繧呈治逕ｨ縺励◆譎らせ縺ｧ諢丞袖隲悶′蟠ｩ繧後※縺・◆
  - 謨ｰ蠑丞腰菴薙・ unit test (`test_weighted_trainer.py`) 縺ｯ batch=2 縺ｧ
    pass 縺吶ｋ縺溘ａ譛ｬ蝠城｡後・讀懷・縺ｧ縺阪↑縺九▲縺溘ょｮ・training context 縺ｧ縺ｮ
    諢丞袖隲・test (gradient direction 縺・weight 縺ｫ蠢懃ｭ斐☆繧九°) 繧定ｿｽ蜉縺吶ｋ
    縺ｮ縺梧悽遲・


codex
I’ve got the design records and new scripts loaded. The main review pressure points now are whether the generated artifacts actually match the scripts’ assumptions, and whether the verdict path is strict enough for the registered Plan B gates.
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "turn-count|cycle-count|multi-turn-max|kant_r8v2|nolora|tier_b_pilot" -S .steering scripts data tests' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "NO_LORA|no-lora|no_lora|adapter-name|lora-name|rank|pilot done|completed=|elapsed=|model" scripts/m9-c-adopt/tier_b_pilot.py' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files = '"'mpnet','e5large','lex5','bgem3' | ForEach-Object { \".steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-"'$($_)-plan-b-kant.json" }; foreach ($f in $files) { $j=Get-Content $f -Raw | ConvertFrom-Json; [pscustomobject]@{file=$f; encoder=$j.encoder; kernel_type=$j.kernel_type; role=$j.encoder_role; revision=$j.encoder_revision_sha; libmatch=$j.library_versions_match_d2; libs=($j.library_versions | ConvertTo-Json -Compress); natural_d=$j.standard_bootstrap.cohens_d; diff_hi=$j.standard_bootstrap.diff_hi; lang_d=$j.language_balanced_bootstrap.cohens_d; length_d=$j.length_balanced_bootstrap.cohens_d; v2=($j.v2_shards -join '"','); nolora=("'$j.nolora_shards -join '"',')} } | Format-List" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$v = Get-Content .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.json -Raw | ConvertFrom-Json; $v | ConvertTo-Json -Depth 8' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files = '"'.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-burrows-plan-b-kant.json','.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-icc-plan-b-kant.json','.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-throughput-plan-b-kant.json'; foreach ("'$f in $files) { Write-Output "FILE $f"; Get-Content $f -Raw }' in C:\ERRE-Sand_Box
 succeeded in 392ms:
3:Per-rank serialized inference loop against SGLang with LoRA adapter routing.
6:``model=kant_r{rank}_real`` per Step 4 multi-pin sanity result.
26:* ``--no-lora-control`` (HIGH-1) routes to the SGLang base model
27:  (``model=Qwen/Qwen3-8B``, no adapter) so a same-protocol no-LoRA control can
28:  be captured under the very same SGLang server. ``--rank`` is accepted as
40:        --persona kant --rank 8 --run-idx 0 \\
47:        --persona kant --rank 8 --run-idx 0 \\
54:        --persona kant --rank 0 --run-idx 0 --no-lora-control \\
97:_NO_LORA_MODEL: Final = "Qwen/Qwen3-8B"
276:    model_name: str,
285:        "model": model_name,
344:    ``--max-loras-per-batch >= rank_count`` and POST ``/load_lora_adapter`` for
345:    each rank ahead of time (re-using ``multi_pin_sanity.sh``). This check
349:        f"{host.rstrip('/')}/v1/models",
356:        msg = f"sglang /v1/models unreachable at {host}: {exc!r}"
461:def _derive_seed(persona: str, rank: int, run_idx: int, no_lora: bool) -> int:
462:    tag = "nolora" if no_lora else f"r{rank}"
469:    rank = args.rank
471:    no_lora = bool(args.no_lora_control)
474:    if no_lora:
475:        model_name = _NO_LORA_MODEL
478:        model_name = args.adapter_name or f"{persona_id}_r{rank}_real"
479:        run_tag = f"r{rank}"
495:    seed_root = _derive_seed(persona_id, rank, run_idx, no_lora)
505:            "resuming from cycle=%d last_stim=%s completed=%d",
511:    if not args.skip_adapter_check and not no_lora:
514:            adapter_name=model_name,
517:        logger.info("adapter %s confirmed loaded on sglang", model_name)
518:    elif no_lora:
519:        logger.info("--no-lora-control mode: routing to base model %s", model_name)
576:                        model_name=model_name,
625:                    "checkpoint persona=%s tag=%s run=%d completed=%d/%d"
643:        "pilot done persona=%s tag=%s run=%d completed=%d elapsed=%.1f min output=%s",
658:            "Per-rank Tier B pilot 采取 against SGLang with LoRA adapter routing."
665:        "--rank",
670:            "LoRA rank; pass 0 with --no-lora-control to route to the SGLang"
671:            " base model."
690:        "--no-lora-control",
693:            "Route to the SGLang base model (no LoRA adapter) for a"
694:            " same-protocol no-LoRA control capture. Pair with --rank 0."
700:    p.add_argument("--adapter-name", default=None)
723:    if args.no_lora_control and args.rank != 0:
725:            "--no-lora-control was passed with --rank %d; rank is ignored in"
726:            " no-LoRA mode (use --rank 0 to make this explicit)",
727:            args.rank,
729:    if not args.no_lora_control and args.rank == 0:
730:        msg = "--rank 0 requires --no-lora-control"

 succeeded in 545ms:
tests\test_m9_c_adopt_pilot.py:1:"""Smoke tests for ``scripts/m9-c-adopt/tier_b_pilot.py`` multi-turn logic.
tests\test_m9_c_adopt_pilot.py:6:``--multi-turn-max`` cap without spinning up SGLang. The end-to-end DuckDB
tests\test_m9_c_adopt_pilot.py:20:_PILOT_PATH = _REPO_ROOT / "scripts" / "m9-c-adopt" / "tier_b_pilot.py"
tests\test_m9_c_adopt_pilot.py:25:    spec = importlib.util.spec_from_file_location("tier_b_pilot", _PILOT_PATH)
tests\test_m9_c_adopt_pilot.py:29:    sys.modules["tier_b_pilot"] = module
tests\test_m9_c_adopt_pilot.py:91:def test_derive_seed_distinct_for_lora_vs_nolora(pilot_module):
tests\test_m9_c_adopt_pilot.py:93:    s_nolora = pilot_module._derive_seed("kant", 8, 0, no_lora=True)
tests\test_m9_c_adopt_pilot.py:94:    assert s_lora != s_nolora
scripts\m9-c-adopt\tier_b_pilot.py:14:* ``--multi-turn-max 1`` (default) folds multi-turn stimuli to a single focal
scripts\m9-c-adopt\tier_b_pilot.py:19:* ``--multi-turn-max N >= 2`` enables baseline-style no-prior alternating-speaker
scripts\m9-c-adopt\tier_b_pilot.py:39:    python scripts/m9-c-adopt/tier_b_pilot.py \\
scripts\m9-c-adopt\tier_b_pilot.py:41:        --turn-count 300 --cycle-count 6 \\
scripts\m9-c-adopt\tier_b_pilot.py:46:    python scripts/m9-c-adopt/tier_b_pilot.py \\
scripts\m9-c-adopt\tier_b_pilot.py:48:        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \\
scripts\m9-c-adopt\tier_b_pilot.py:53:    python scripts/m9-c-adopt/tier_b_pilot.py \\
scripts\m9-c-adopt\tier_b_pilot.py:55:        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \\
scripts\m9-c-adopt\tier_b_pilot.py:57:        --output data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_nolora_run0_stim.duckdb
scripts\m9-c-adopt\tier_b_pilot.py:462:    tag = "nolora" if no_lora else f"r{rank}"
scripts\m9-c-adopt\tier_b_pilot.py:476:        run_tag = "nolora"
scripts\m9-c-adopt\tier_b_pilot.py:527:        f"multi-turn-max={multi_turn_max} (focal per stim avg ="
scripts\m9-c-adopt\tier_b_pilot.py:675:    p.add_argument("--turn-count", type=int, default=_DEFAULT_TURN_COUNT)
scripts\m9-c-adopt\tier_b_pilot.py:676:    p.add_argument("--cycle-count", type=int, default=_DEFAULT_CYCLE_COUNT)
scripts\m9-c-adopt\tier_b_pilot.py:678:        "--multi-turn-max",
scripts\m9-c-adopt\run_plan_b_post_eval.sh:22:NOLORA_SHARDS_GLOB="$SHARDS/kant_planb_nolora_run*_stim.duckdb"
scripts\m9-c-adopt\run_plan_b_post_eval.sh:50:    --shards-glob "$NOLORA_SHARDS_GLOB" \
scripts\m9-c-adopt\run_plan_b_post_eval.sh:51:    --output "$TASK/validation-kant-planb-nolora.json"
scripts\m9-c-adopt\run_plan_b_post_eval.sh:68:        --nolora-shards "$SHARDS/kant_planb_nolora_run0_stim.duckdb" \
scripts\m9-c-adopt\run_plan_b_post_eval.sh:69:                        "$SHARDS/kant_planb_nolora_run1_stim.duckdb" \
scripts\m9-c-adopt\run_plan_b_post_eval.sh:84:    --shards-glob "$NOLORA_SHARDS_GLOB" \
scripts\m9-c-adopt\run_plan_b_post_eval.sh:86:    --output "$TASK/tier-b-plan-b-kant-planb-nolora-burrows.json"
scripts\m9-c-adopt\run_plan_b_post_eval.sh:104:    --burrows-nolora "$TASK/tier-b-plan-b-kant-planb-nolora-burrows.json" \
scripts\m9-c-adopt\run_plan_b_post_eval.sh:107:    --nolora-shards "$SHARDS/kant_planb_nolora_run0_stim.duckdb" "$SHARDS/kant_planb_nolora_run1_stim.duckdb" \
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:4:# Runs tier_b_pilot.py for:
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:34:    if "$PYTHON" "${REPO}/scripts/m9-c-adopt/tier_b_pilot.py" "$@"; then
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:45:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:54:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:63:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:65:    --output "${OUT}/kant_planb_nolora_run0_stim.duckdb" \
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:71:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:73:    --output "${OUT}/kant_planb_nolora_run1_stim.duckdb" \
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:59:    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb"),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:60:    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run1_stim.duckdb"),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:62:_NOLORA_SHARDS = (
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:63:    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_nolora_run0_stim.duckdb"),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:64:    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_nolora_run1_stim.duckdb"),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:166:    nolora_texts: list[str],
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:170:    Returns ``(v2_unit, nolora_unit)`` — both unit-l2-normalized so that
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:187:    n_nolora = len(nolora_texts)
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:188:    cleaned = [str(t) if str(t).strip() else " " for t in (v2_texts + nolora_texts)]
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:190:        "lexical_5gram pool-fit: v2=%d nolora=%d merged=%d",
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:192:        n_nolora,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:254:    ``diff_v2_minus_nolora`` + ``diff_ci_95``): the CI is on ``mean(ra) -
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:283:    nolora_unit: np.ndarray,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:285:    nolora_strata: np.ndarray,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:304:    nolora_by: dict[str, np.ndarray] = {
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:305:        s: np.where(nolora_strata == s)[0] for s in eligible_strata
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:307:    eligible = [s for s in eligible_strata if v2_by[s].size and nolora_by[s].size]
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:314:    nolora_scores: list[float] = []
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:318:        nolora_idx_list: list[int] = []
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:323:            nolora_idx_list.extend(
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:324:                int(i) for i in rng.choice(nolora_by[s], size=per_quota, replace=True)
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:330:        while len(nolora_idx_list) < window_size:
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:332:            nolora_idx_list.append(int(rng.choice(nolora_by[s])))
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:334:        nolora_idx = np.asarray(nolora_idx_list[:window_size], dtype=int)
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:336:        nolora_score = _vendi_from_unit_embeddings(nolora_unit, nolora_idx)
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:338:        nolora_scores.append(nolora_score)
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:339:        diffs.append(v2_score - nolora_score)
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:348:        "nolora_mean": float(np.mean(nolora_scores)),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:352:        "cohens_d": _cohens_d(v2_scores, nolora_scores),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:430:            " Defaults to the Plan A v2 baseline (kant_r8v2_run{0,1}); pass"
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:435:        "--nolora-shards",
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:438:        default=list(_NOLORA_SHARDS),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:441:            " to the existing kant_nolora_run{0,1} SGLang baseline; pass the"
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:442:            " Plan B no-LoRA control shards (kant_planb_nolora_run{0,1}) for"
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:484:    nolora_utterances: list[str] = []
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:485:    nolora_utt_per_shard: list[int] = []
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:486:    for shard in args.nolora_shards:
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:488:        nolora_utterances.extend(ut)
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:489:        nolora_utt_per_shard.append(len(ut))
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:492:        "v2 utterances=%d nolora utterances=%d",
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:494:        len(nolora_utterances),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:522:        v2_unit, nolora_unit = _encode_pools_lexical_5gram(
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:524:            nolora_utterances,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:528:        nolora_unit = _encode_pool(args.encoder, revision, nolora_utterances)
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:532:    nolora_window_scores = _natural_window_scores(nolora_unit, nolora_utt_per_shard)
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:534:        "natural windows: v2=%d nolora=%d",
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:536:        len(nolora_window_scores),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:541:        nolora_window_scores,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:548:    nolora_langs = np.asarray([_detect_language(t) for t in nolora_utterances])
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:549:    merged_lengths = sorted(len(t) for t in v2_utterances + nolora_utterances)
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:558:    nolora_quartiles = np.asarray(
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:559:        [_length_quartile(len(t), quartile_cuts) for t in nolora_utterances],
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:565:        nolora_unit=nolora_unit,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:567:        nolora_strata=nolora_langs,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:577:        nolora_unit=nolora_unit,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:579:        nolora_strata=nolora_quartiles,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:590:        nolora_mass = int((nolora_langs == lang).sum())
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:591:        if v2_mass < args.window_size or nolora_mass < args.window_size:
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:595:                "n_nolora": nolora_mass,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:605:            nolora_unit=nolora_unit,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:607:            nolora_strata=nolora_langs,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:683:        "nolora_shards": [s.name for s in args.nolora_shards],
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:686:            "nolora_scores": nolora_window_scores,
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:688:            "nolora_mean": float(np.mean(nolora_window_scores)),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:689:            "cohens_d": _cohens_d(v2_window_scores, nolora_window_scores),
scripts\m9-c-adopt\de_focused_monolog_collector.py:14:* `scripts/m9-c-adopt/tier_b_pilot.py` (SGLang client + DuckDB sink base)
scripts\m9-c-adopt\de_focused_monolog_collector.py:16:差分 from `tier_b_pilot.py`:
scripts\m9-c-adopt\de_focused_monolog_collector.py:81:# Constants (mirrors tier_b_pilot.py where applicable)
scripts\m9-c-adopt\de_focused_monolog_collector.py:197:# Persona prompt — fork of tier_b_pilot._build_system_prompt for de monolog
scripts\m9-c-adopt\de_focused_monolog_collector.py:209:    Mirrors ``tier_b_pilot._build_system_prompt`` so the persona block
scripts\m9-c-adopt\de_focused_monolog_collector.py:245:# SGLang HTTP client (mirrors tier_b_pilot._sglang_chat with extra penalties)
scripts\m9-c-adopt\da1_matrix_multiturn.py:211:    nolora_vendi = _load(si / "tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json")
scripts\m9-c-adopt\da1_matrix_multiturn.py:212:    nolora_burrows = _load(si / "tier-b-pilot-multiturn-kant-nolora-burrows.json")
scripts\m9-c-adopt\da1_matrix_multiturn.py:213:    nolora_icc = _load(si / "tier-b-icc-multiturn-kant-nolora.json")
scripts\m9-c-adopt\da1_matrix_multiturn.py:231:            nolora_vendi,
scripts\m9-c-adopt\da1_matrix_multiturn.py:232:            nolora_burrows,
scripts\m9-c-adopt\da1_matrix_multiturn.py:233:            nolora_icc,
scripts\m9-c-adopt\da1_matrix_multiturn.py:264:    matched_baseline_for_compare = nolora_vendi or matched_vendi or hist_vendi
scripts\m9-c-adopt\da1_matrix_multiturn.py:265:    matched_burrows_for_compare = nolora_burrows or matched_burrows or hist_burrows
scripts\m9-c-adopt\da1_matrix_multiturn.py:268:        if nolora_vendi
scripts\m9-c-adopt\da15_calibration_panel.py:14:  ``data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb``
scripts\m9-c-adopt\da15_calibration_panel.py:21:  distribution overlaps with kant_r8v2_run0_stim. The natural baseline is
scripts\m9-c-adopt\da15_calibration_panel.py:56:    "data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb",
scripts\m9-c-adopt\da15_calibration_panel.py:60:with kant_r8v2_run0_stim (de/en/ja). The natural baseline is almost
scripts\m9-c-adopt\da15_calibration_panel.py:234:            "kant_r8v2_run0_stim — generated by Qwen3-8B + kant LoRA r8 v2"
scripts\m9-c-adopt\da15_calibration_panel.py:239:            " matches the kant_r8v2 pool. D-1 substitution: Codex spec"
scripts\m9-c-adopt\compute_big5_icc.py:19:``tier_b_pilot.py`` (which is multi-turn stimulus-conditioned dialog).
scripts\m9-c-adopt\aggregate_plan_b_axes.py:27:        --burrows-nolora .steering/.../tier-b-plan-b-kant-planb-nolora-burrows.json \
scripts\m9-c-adopt\aggregate_plan_b_axes.py:31:        --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb \
scripts\m9-c-adopt\aggregate_plan_b_axes.py:32:                        data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb \
scripts\m9-c-adopt\aggregate_plan_b_axes.py:66:    given run tag (e.g. ``r8 run=0`` or ``nolora run=0``).
scripts\m9-c-adopt\aggregate_plan_b_axes.py:88:    nolora: list[float],
scripts\m9-c-adopt\aggregate_plan_b_axes.py:93:    """Bootstrap CI for reduction%: (nolora_mean - v2_mean) / nolora_mean × 100.
scripts\m9-c-adopt\aggregate_plan_b_axes.py:99:    b = np.asarray(nolora, dtype=float)
scripts\m9-c-adopt\aggregate_plan_b_axes.py:121:    p.add_argument("--burrows-nolora", required=True, type=Path)
scripts\m9-c-adopt\aggregate_plan_b_axes.py:133:    p.add_argument("--nolora-shards", nargs="+", required=True, type=Path)
scripts\m9-c-adopt\aggregate_plan_b_axes.py:149:    nolora_payload = _load_json(args.burrows_nolora)
scripts\m9-c-adopt\aggregate_plan_b_axes.py:151:    nolora_means = _window_means(nolora_payload)
scripts\m9-c-adopt\aggregate_plan_b_axes.py:153:        v2_means, nolora_means, seed=args.seed, n_resamples=args.n_resamples,
scripts\m9-c-adopt\aggregate_plan_b_axes.py:158:        "no_lora_mean": float(mean(nolora_means)) if nolora_means else None,
scripts\m9-c-adopt\aggregate_plan_b_axes.py:159:        "no_lora_stdev": float(stdev(nolora_means)) if len(nolora_means) > 1 else None,
scripts\m9-c-adopt\aggregate_plan_b_axes.py:164:        "n_windows_nolora": len(nolora_means),
scripts\m9-c-adopt\aggregate_plan_b_axes.py:206:    # no-LoRA rates come from "pilot done persona=kant tag=nolora run=N ..."
scripts\m9-c-adopt\aggregate_plan_b_axes.py:211:    nolora_rates = [
scripts\m9-c-adopt\aggregate_plan_b_axes.py:212:        _shard_focal_rate_from_log(args.eval_log, f"tag=nolora run={i}")
scripts\m9-c-adopt\aggregate_plan_b_axes.py:213:        for i in range(len(args.nolora_shards))
scripts\m9-c-adopt\aggregate_plan_b_axes.py:216:    nolora_valid = [r for r in nolora_rates if r is not None]
scripts\m9-c-adopt\aggregate_plan_b_axes.py:218:    nolora_rate = float(mean(nolora_valid)) if nolora_valid else float("nan")
scripts\m9-c-adopt\aggregate_plan_b_axes.py:219:    if nolora_rate and nolora_rate != 0 and nolora_rate == nolora_rate:
scripts\m9-c-adopt\aggregate_plan_b_axes.py:220:        throughput_pct = v2_rate / nolora_rate * 100.0
scripts\m9-c-adopt\aggregate_plan_b_axes.py:225:        "no_lora_focal_per_s": nolora_rate,
scripts\m9-c-adopt\aggregate_plan_b_axes.py:228:        "no_lora_rates_per_shard": nolora_rates,
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:4:design.md` §1.2) extended the script with ``--v2-shards`` / ``--nolora-shards``
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:88:    """No --v2-shards/--nolora-shards flags → existing Plan A defaults."""
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:99:    assert list(ns.nolora_shards) == list(rescore_module._NOLORA_SHARDS)
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:116:            "--nolora-shards",
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:121:    assert ns.nolora_shards == [Path("data/eval/c.duckdb")]
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:136:            "--nolora-shards",
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:164:            "--nolora-shards",
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:182:            "--nolora-shards",
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:221:    nolora_texts = [
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:224:    v2_unit, nolora_unit = rescore_module._encode_pools_lexical_5gram(
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:226:        nolora_texts,
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:229:    assert nolora_unit.shape[0] == len(nolora_texts)
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:230:    assert v2_unit.shape[1] == nolora_unit.shape[1]  # shared TF-IDF vocab
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:232:    nolora_norms = np.linalg.norm(nolora_unit, axis=1)
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:234:    assert np.allclose(nolora_norms, 1.0, atol=1e-9)
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:255:    nolora_texts = [
tests\test_scripts\test_rescore_vendi_alt_kernel_cli.py:260:        nolora_texts,
.steering\20260518-m9-c-adopt-plan-b-verdict\tasklist.md:33:      `--nolora-shards`、blocker 2)
.steering\20260518-m9-c-adopt-plan-b-verdict\tasklist.md:35:- [ ] tier_b_pilot.py で LoRA-on / no-LoRA shards 生成 (~5h GPU)
.steering\20260518-m9-c-adopt-plan-b-verdict\requirement.md:51:      `kant_planb_nolora_run{0,1}_stim.duckdb` を新規生成、
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:47:   - `--v2-shards` / `--nolora-shards` を kw-only flag で追加
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:57:   - LoRA-on run × 2: `tier_b_pilot.py --persona kant --rank 8
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:58:     --run-idx {0,1} --turn-count 300 --cycle-count 6 --multi-turn-max 6
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:62:     --turn-count 300 --cycle-count 6 --multi-turn-max 6 --output
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:63:     data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run{0,1}_stim.duckdb`
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:71:     --nolora-shards <Plan B no-LoRA run0 run1>
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:127:10. `scripts/m9-c-adopt/tier_b_pilot.py` (eval generation driver)
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:144:- **stim protocol は v2 baseline と apples-to-apples**: `tier_b_pilot.py`
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:145:  の引数 (`--turn-count 300 --cycle-count 6 --multi-turn-max 6`) を
.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:33:   - `--v2-shards` / `--nolora-shards` kw-only flag 追加、default は
.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:36:2. **Plan B eval shard 生成** (`tier_b_pilot.py` 再利用):
.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:39:   - LoRA-on run: `--rank 8 --multi-turn-max 6 --turn-count 300
.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:40:     --cycle-count 6` × 2 run (`run0`、`run1`) → 2 shards、~1.5h × 2
.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:41:   - no-LoRA control: `--no-lora-control --rank 0 --multi-turn-max 6
.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:42:     --turn-count 300 --cycle-count 6` × 2 run → 2 shards、~1h × 2
.steering\20260518-m9-c-adopt-plan-b-verdict\blockers.md:9:    - `data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`
.steering\20260518-m9-c-adopt-plan-b-verdict\blockers.md:11:    - `data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_nolora_run{0,1}_stim.duckdb`
.steering\20260518-m9-c-adopt-plan-b-verdict\blockers.md:24:     `_NOLORA_SHARDS` パスのみで Plan B shard を accept する仕組みなし
.steering\20260518-m9-c-adopt-plan-b-verdict\blockers.md:63:    `_NOLORA_SHARDS` は module-level constant の Path tuple
.steering\20260518-m9-c-adopt-plan-b-verdict\blockers.md:69:  1. `rescore_vendi_alt_kernel.py` 冒頭の `_V2_SHARDS` / `_NOLORA_SHARDS`
.steering\20260518-m9-c-adopt-plan-b-verdict\blockers.md:77:  - 候補 (a): `--v2-shards` / `--nolora-shards` を kw-only CLI flag で追加、
data\eval\m9-c-adopt-tier-b-pilot-multiturn\_checksums.txt:1:3736b9ff90603bc52a18cc4241a08d628c77c02ee6285486f21fb1931f8d0bf7 *kant_nolora_run0_stim.duckdb
data\eval\m9-c-adopt-tier-b-pilot-multiturn\_checksums.txt:2:09321e82e9e78998d5d30894319cdc1f443c525312f8fb110bd1c184ccdd7276 *kant_nolora_run1_stim.duckdb
data\calibration\kant_heidegger_corpus.json:6:  "license_attribution": "kant_r8v2_run0_stim — generated by Qwen3-8B + kant LoRA r8 v2 (Apache-2.0 generation pipeline, repository licence applies). nietzsche_stimulus_run0 — generated by Qwen3-8B + nietzsche persona prompt (no LoRA), license-clean Apache-2.0 pipeline, stimulus condition selected so the language distribution matches the kant_r8v2 pool. D-1 substitution: Codex spec named Heidegger as control, repo has nietzsche persona instead; both are 19c-German non-Kant philosophers from the same generation pipeline.",
data\calibration\kant_heidegger_corpus.json:11:    "kant": "data\\eval\\m9-c-adopt-tier-b-pilot-multiturn-v2\\kant_r8v2_run0_stim.duckdb",
.steering\20260517-m9-c-adopt-plan-b-design\tasklist.md:5:      / DI-1〜5 / dataset.py / weighting.py / tier_b_pilot.py /
.steering\20260517-m9-c-adopt-plan-b-design\requirement.md:119:- `scripts/m9-c-adopt/tier_b_pilot.py` (generation-side prompt base)
.steering\20260517-m9-c-adopt-plan-b-design\g-gear-collection-runbook.md:36:shape を作るには no-LoRA base が正解)。`tier_b_pilot.py` の
.steering\20260517-m9-c-adopt-plan-b-design\design.md:32:`tier_b_pilot.py` を base に流用:
.steering\20260517-m9-c-adopt-plan-b-design\design.md:219:  2. driver smoke test: `--dry-run --turn-count 50 --cycle-count 1` で
.steering\20260517-m9-c-adopt-plan-b-design\design.md:275:- `tier_b_pilot.py` の SGLang client + DuckDB sink パターン継承
.steering\20260517-m9-c-adopt-plan-b-design\design-v2.md:22:  (multi-turn ではない)。`tier_b_pilot.py` を base にするが
.steering\20260517-m9-c-adopt-plan-b-design\design-v1.md:17:- `tier_b_pilot.py` の SGLang chat client + DuckDB sink を base に流用
.steering\20260517-m9-c-adopt-plan-b-design\design-v1.md:142:     --persona kant --turn-count 250 --cycle-count 10 --no-lora-control
.steering\20260517-m9-c-adopt-plan-b-design\design-v1.md:180:- `tier_b_pilot.py` の SGLang client + DuckDB sink パターン継承
.steering\20260517-m9-c-adopt-plan-b-design\design-v1.md:201:  test のみ、`--turn-count 5 --cycle-count 1` で本物 SGLang 必要なし、
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:112:- `scripts/m9-c-adopt/tier_b_pilot.py` (driver base 流用元)
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:1371:scripts/m9-c-adopt\rescore_vendi_alt_kernel.py:383:    nolora_unit = _encode_pool(args.encoder, revision, nolora_utterances)
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:2310:  21: **driver**: `scripts/m9-c-adopt/de_focused_monolog_collector.py`縲・`tier_b_pilot.py` 繧・base 縺ｫ豬∫畑:
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:2468: 179:   2. driver smoke test: `--dry-run --turn-count 50 --cycle-count 1` 縺ｧ
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:2518: 229: - `tier_b_pilot.py` 縺ｮ SGLang client + DuckDB sink 繝代ち繝ｼ繝ｳ邯呎価
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:2596:  32: shape 繧剃ｽ懊ｋ縺ｫ縺ｯ no-LoRA base 縺梧ｭ｣隗｣)縲Ａtier_b_pilot.py` 縺ｮ
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:3072:  12: * `scripts/m9-c-adopt/tier_b_pilot.py` (SGLang client + DuckDB sink base)
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:3074:  14: 蟾ｮ蛻・from `tier_b_pilot.py`:
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:3137:  77: # Constants (mirrors tier_b_pilot.py where applicable)
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:3253: 193: # Persona prompt 窶・fork of tier_b_pilot._build_system_prompt for de monolog
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:3265: 205:     Mirrors ``tier_b_pilot._build_system_prompt`` so the persona block
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:3301: 241: # SGLang HTTP client (mirrors tier_b_pilot._sglang_chat with extra penalties)
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6304:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "load_stimulus|stimulus_dir|golden/stimulus|stimulus" scripts/m9-c-adopt/tier_b_pilot.py tests/test_m9_c_adopt_pilot.py .steering/20260517-m9-c-adopt-plan-b-design/requirement.md' in C:\ERRE-Sand_Box
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6317:scripts/m9-c-adopt/tier_b_pilot.py:9:shard never leaks back into training. Per-stimulus checkpoint resume is keyed
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6318:scripts/m9-c-adopt/tier_b_pilot.py:10:on ``(cycle_idx, stimulus_id)`` so an interrupted run picks up where it left
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6319:scripts/m9-c-adopt/tier_b_pilot.py:20:  stimulus protocol: for each stimulus, run ``min(expected_turn_count, N)`` turns
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6320:scripts/m9-c-adopt/tier_b_pilot.py:22:  with the same focal-persona system prompt + same stimulus user prompt (only
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6321:scripts/m9-c-adopt/tier_b_pilot.py:23:  ``turn=K`` marker varies). Mirrors ``GoldenBaselineDriver.run_stimulus`` +
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6322:scripts/m9-c-adopt/tier_b_pilot.py:24:  ``_make_stimulus_inference_fn`` (eval_run_golden.py) which delete persona_id
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6323:scripts/m9-c-adopt/tier_b_pilot.py:87:_DEFAULT_STIMULUS_DIR: Final = _REPO_ROOT / "golden" / "stimulus"
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6324:scripts/m9-c-adopt/tier_b_pilot.py:120:    last_stimulus_id TEXT,
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6325:scripts/m9-c-adopt/tier_b_pilot.py:126:_INTERLOCUTOR_ID: Final = "_stimulus"
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6326:scripts/m9-c-adopt/tier_b_pilot.py:137:def _load_stimulus_battery(persona_id: str, root: Path) -> list[dict[str, Any]]:
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6327:scripts/m9-c-adopt/tier_b_pilot.py:141:        msg = f"{path}: malformed stimulus YAML"
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6328:scripts/m9-c-adopt/tier_b_pilot.py:146:def _focal_turn_count(stimulus: dict[str, Any], multi_turn_max: int) -> int:
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6329:scripts/m9-c-adopt/tier_b_pilot.py:147:    """Per-stimulus focal-speaker turn count.
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6330:scripts/m9-c-adopt/tier_b_pilot.py:149:    Mirrors ``eval_run_golden._focal_turn_count`` (P3 stimulus condition) so
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6331:scripts/m9-c-adopt/tier_b_pilot.py:161:    expected = int(stimulus.get("expected_turn_count", 1))
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6332:scripts/m9-c-adopt/tier_b_pilot.py:166:def _total_turn_count(stimulus: dict[str, Any], multi_turn_max: int) -> int:
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6333:scripts/m9-c-adopt/tier_b_pilot.py:167:    """Total turns per stimulus (focal + interlocutor)."""
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6334:scripts/m9-c-adopt/tier_b_pilot.py:170:    expected = int(stimulus.get("expected_turn_count", 1))
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6335:scripts/m9-c-adopt/tier_b_pilot.py:208:    selected_ids = {s.get("stimulus_id") for s in selected}
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6336:scripts/m9-c-adopt/tier_b_pilot.py:209:    return [s for s in battery if s.get("stimulus_id") in selected_ids]
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6337:scripts/m9-c-adopt/tier_b_pilot.py:213:# Persona prompt — minimal, mirrors eval_run_golden._build_stimulus_system_prompt
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6338:scripts/m9-c-adopt/tier_b_pilot.py:237:        "a curated stimulus from a Toulmin / Theory-of-Mind / RoleEval / "
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6339:scripts/m9-c-adopt/tier_b_pilot.py:251:    stimulus: dict[str, Any], cycle_idx: int, turn_index: int
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6340:scripts/m9-c-adopt/tier_b_pilot.py:253:    prompt_text = str(stimulus.get("prompt_text", "")).strip()
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6341:scripts/m9-c-adopt/tier_b_pilot.py:254:    category = str(stimulus.get("category", ""))
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6342:scripts/m9-c-adopt/tier_b_pilot.py:256:        f"[stimulus_id={stimulus.get('stimulus_id', '?')} "
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6343:scripts/m9-c-adopt/tier_b_pilot.py:379:        "SELECT last_cycle_idx, last_stimulus_id, completed_turns"
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6344:scripts/m9-c-adopt/tier_b_pilot.py:390:    stimulus_id: str,
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6345:scripts/m9-c-adopt/tier_b_pilot.py:396:        (cycle_idx, stimulus_id, completed, datetime.now(UTC)),
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6346:scripts/m9-c-adopt/tier_b_pilot.py:484:    battery = _load_stimulus_battery(persona_id, args.stimulus_dir)
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6347:scripts/m9-c-adopt/tier_b_pilot.py:540:        for stim_idx, stimulus in enumerate(sliced):
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6348:scripts/m9-c-adopt/tier_b_pilot.py:543:            stim_id = str(stimulus.get("stimulus_id", f"unknown_{stim_idx}"))
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6349:scripts/m9-c-adopt/tier_b_pilot.py:553:            zone = str(stimulus.get("expected_zone", ""))
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6350:scripts/m9-c-adopt/tier_b_pilot.py:555:            total_turns_this_stim = _total_turn_count(stimulus, multi_turn_max)
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6351:scripts/m9-c-adopt/tier_b_pilot.py:571:                user_prompt = _build_user_prompt(stimulus, cycle_idx, turn_index)
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6352:scripts/m9-c-adopt/tier_b_pilot.py:659:            " Outputs raw_dialog with epoch_phase=evaluation; per-stimulus"
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6353:scripts/m9-c-adopt/tier_b_pilot.py:682:            "Per-stimulus turn cap. 1 (default) reproduces the DA-11 single-turn"
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6354:scripts/m9-c-adopt/tier_b_pilot.py:684:            " stimulus protocol (focal kant on turn 0/2/..., interlocutor on"
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6355:scripts/m9-c-adopt/tier_b_pilot.py:685:            " turn 1/...). Current Kant stimulus max expected_turn_count=3, so"
.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6356:scripts/m9-c-adopt/tier_b_pilot.py:703:        "--stimulus-dir",
.steering\20260517-m9-c-adopt-plan-b-design\codex-review-prompt.md:99:- `scripts/m9-c-adopt/tier_b_pilot.py` (driver base 流用元)
.steering\20260515-m9-c-adopt-retrain-v2-verdict\vendi.log:1:2026-05-16 07:54:45,660 [__main__] INFO: loading 2 shards: ['kant_r8v2_run0_stim.duckdb', 'kant_r8v2_run1_stim.duckdb']
.steering\20260515-m9-c-adopt-retrain-v2-verdict\vendi.log:2:2026-05-16 07:54:45,873 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\vendi.log:11:2026-05-16 07:55:21,793 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\validation-v2-kant.json:8:      "shard": "kant_r8v2_run0_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\validation-v2-kant.json:53:      "shard": "kant_r8v2_run1_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\tasklist.md:26:- [x] tier_b_pilot.py run 0 → 6.1 min、run 1 → 6.0 min
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\design.md:49:   - `--turn-count 1000` で focal=500 early-stop を抑制 (calibration 主旨)
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:61:# === Step 4: Run tier_b_pilot 2x (run 0/1) ===
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:63:    out="${PILOT_OUT_DIR}/kant_r8v2_run${run_idx}_stim.duckdb"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:69:    "${PYBIN_WIN}" scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:71:        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:83:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:90:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:105:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:113:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:118:# === Step 9: Copy nolora baseline + matched baseline into matrix-inputs dir ===
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:121:    "tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json" \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:122:    "tier-b-pilot-multiturn-kant-nolora-burrows.json" \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:123:    "tier-b-icc-multiturn-kant-nolora.json" \
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\decisions.md:24:### H1. stimulus 500 focal が現 command (`--turn-count 500 --cycle-count 3`) で **到達不能**
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\decisions.md:30:  `--turn-count 500 --cycle-count 6` に変更 (focal≈504、target 500 を満たす)。
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\decisions.md:34:### H2. run1 `--turn-count 1000` は 600 min endpoint を潰す
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\decisions.md:36:  `--turn-count 1000` だと 600 min cell が約 535 min で early stop し、
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\decisions.md:40:  `--turn-count 2000` に変更 (Codex 推奨: 1500 以上、保守的に 2000)。
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\decisions.md:114:  `--turn-count 2000` (early stop 抑制) で 120/240/360/480/600 wall endpoint を
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\decisions.md:118:- **§Phase B stimulus**: `--turn-count 500 --cycle-count 6` (focal≈504)、新
.steering\20260515-m9-c-adopt-retrain-v2-verdict\pilot_run1.log:1:2026-05-16 07:48:09,761 [__main__] INFO: pilot start persona=kant tag=r8 run=1 sliced=45 multi-turn-max=6 (focal per stim avg = 1.11)
.steering\20260515-m9-c-adopt-retrain-v2-verdict\pilot_run1.log:14:2026-05-16 07:54:09,457 [__main__] INFO: pilot done persona=kant tag=r8 run=1 completed=300 elapsed=6.0 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run1_stim.duckdb
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\codex-review-run1-calibration.md:9:- 問題: v1 流用の `--turn-count 500 --cycle-count 3` は stimulus battery が oversampling しないため focal=500 に届かない。read-only pure-function check では kant/nietzsche/rikyu とも total focal=264。PR #140 後は `focal_rows < args.turn_count` が fatal になるので Phase B stimulus 全 cell が fail する。
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\codex-review-run1-calibration.md:10:- 推奨: v2 prompt で stimulus の `cycle_count` を 6 以上に変更する。`--turn-count 500 --cycle-count 6` は focal≈504 で audit target 500 を満たす。3-cycle 固定が必要なら target を 264 に下げる判断が必要だが、これは P3 spec 変更扱い。
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\codex-review-run1-calibration.md:12:### H2. run1 `--turn-count 1000` は 600 min endpoint を潰す
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\codex-review-run1-calibration.md:14:- 問題: single rate 期待値 1.87/min なら 600 min で focal≈1122。`--turn-count 1000` だと 600 min cell が約535 minで early stop し、最重要の 600 min wall sample が取れない。
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\codex-review-run1-calibration.md:15:- 推奨: calibration only で `--turn-count 1500` 以上、保守的には `2000`。120/240/360/480/600 wall cells は return code 3 を正常な calibration partial として扱い、production audit と混ぜない。
.steering\20260515-m9-c-adopt-retrain-v2-verdict\pilot_run0.log:1:2026-05-16 07:42:04,402 [__main__] INFO: pilot start persona=kant tag=r8 run=0 sliced=45 multi-turn-max=6 (focal per stim avg = 1.11)
.steering\20260515-m9-c-adopt-retrain-v2-verdict\pilot_run0.log:14:2026-05-16 07:48:09,549 [__main__] INFO: pilot done persona=kant tag=r8 run=0 completed=300 elapsed=6.1 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run0_stim.duckdb
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\codex-review-prompt-run1-calibration.md:57:=120/240/360/480/600 min。`--turn-count 1000` で focal=500 early-stop を抑制
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\codex-review-prompt-run1-calibration.md:181:- `--turn-count 1000` で focal=500 early-stop を抑制する設計は意図通りに動くか
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\codex-review-prompt-run1-calibration.md:185:  expected focal ≈ 1122 (single 1.87) は超過するため `--turn-count 1500` の
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:10:[phase3] pilot run 0 → data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:15:2026-05-16 07:48:09,549 [__main__] INFO: pilot done persona=kant tag=r8 run=0 completed=300 elapsed=6.1 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run0_stim.duckdb
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:16:[phase3] pilot run 1 → data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run1_stim.duckdb
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:21:2026-05-16 07:54:09,457 [__main__] INFO: pilot done persona=kant tag=r8 run=1 completed=300 elapsed=6.0 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run1_stim.duckdb
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:25:2026-05-16 07:54:25,621 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:26:2026-05-16 07:54:30,549 [__main__] INFO: window 4/?  shard=kant_r8v2_run1_stim.duckdb w_idx=0 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:27:2026-05-16 07:54:35,465 [__main__] INFO: window 5/?  shard=kant_r8v2_run1_stim.duckdb w_idx=1 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:28:2026-05-16 07:54:40,329 [__main__] INFO: window 6/?  shard=kant_r8v2_run1_stim.duckdb w_idx=2 big5=E:3.10/A:3.40/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:38:2026-05-16 07:55:40,995 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:39:2026-05-16 07:55:41,070 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=0 total=100 de=51 en=36 ja=5 other=0 dropped=8 mean_burrows=113.2953
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:40:2026-05-16 07:55:41,135 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=1 total=100 de=55 en=35 ja=1 other=0 dropped=9 mean_burrows=116.3416
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:41:2026-05-16 07:55:41,209 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=2 total=100 de=54 en=36 ja=4 other=0 dropped=6 mean_burrows=111.3366
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:44:  copied: tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:45:  copied: tier-b-pilot-multiturn-kant-nolora-burrows.json
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:46:  copied: tier-b-icc-multiturn-kant-nolora.json
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:11:    "kant_r8v2_run0_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:12:    "kant_r8v2_run1_stim.duckdb"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:26:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:33:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:40:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:47:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:54:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:61:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:32:    "kant_r8v2_run0_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:33:    "kant_r8v2_run1_stim.duckdb"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:37:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:104:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:173:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:240:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:304:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:372:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:11:    "kant_nolora_run0_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:12:    "kant_nolora_run1_stim.duckdb"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:26:      "run_id": "kant_nolora_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:33:      "run_id": "kant_nolora_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:40:      "run_id": "kant_nolora_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:47:      "run_id": "kant_nolora_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:54:      "run_id": "kant_nolora_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:61:      "run_id": "kant_nolora_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:32:    "kant_nolora_run0_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:33:    "kant_nolora_run1_stim.duckdb"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:37:      "run_id": "kant_nolora_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:105:      "run_id": "kant_nolora_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:172:      "run_id": "kant_nolora_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:239:      "run_id": "kant_nolora_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:308:      "run_id": "kant_nolora_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:377:      "run_id": "kant_nolora_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:8:    "kant_r8v2_run0_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:9:    "kant_r8v2_run1_stim.duckdb"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:32:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:50:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:68:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:86:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:104:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:122:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-nolora.json:8:    "kant_nolora_run0_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-nolora.json:9:    "kant_nolora_run1_stim.duckdb"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-nolora.json:32:      "run_id": "kant_nolora_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-nolora.json:50:      "run_id": "kant_nolora_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-nolora.json:68:      "run_id": "kant_nolora_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-nolora.json:86:      "run_id": "kant_nolora_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-nolora.json:104:      "run_id": "kant_nolora_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-nolora.json:122:      "run_id": "kant_nolora_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:1:2026-05-16 07:54:10,572 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:2:2026-05-16 07:54:15,629 [__main__] INFO: window 1/?  shard=kant_r8v2_run0_stim.duckdb w_idx=0 big5=E:3.10/A:3.50/C:3.20/N:3.00/O:3.20 rate=0.19 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:3:2026-05-16 07:54:20,613 [__main__] INFO: window 2/?  shard=kant_r8v2_run0_stim.duckdb w_idx=1 big5=E:3.20/A:3.40/C:3.40/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:4:2026-05-16 07:54:25,609 [__main__] INFO: window 3/?  shard=kant_r8v2_run0_stim.duckdb w_idx=2 big5=E:3.10/A:3.40/C:3.40/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:5:2026-05-16 07:54:25,621 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:6:2026-05-16 07:54:30,549 [__main__] INFO: window 4/?  shard=kant_r8v2_run1_stim.duckdb w_idx=0 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:7:2026-05-16 07:54:35,465 [__main__] INFO: window 5/?  shard=kant_r8v2_run1_stim.duckdb w_idx=1 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:8:2026-05-16 07:54:40,329 [__main__] INFO: window 6/?  shard=kant_r8v2_run1_stim.duckdb w_idx=2 big5=E:3.10/A:3.40/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\design.md:40:python scripts/m9-c-adopt/tier_b_pilot.py --persona kant --rank 8 \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\design.md:42:    --multi-turn-max 6 --max-focal-per-shard 300 \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:49:  3. tier_b_pilot.py を `--rank 8 --adapter-name kant_r8_v2` で 2 run 採取
.steering\20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:52:- **注意**: tier_b_pilot.py の CLI には `--max-focal-per-shard` も `--adapter <path>`
.steering\20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:54:  `--turn-count 300 --cycle-count 6 --multi-turn-max 6 --adapter-name <name>` で、
.steering\20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:8:      "diff_v2_minus_nolora": -0.12804119393459246,
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:2:2026-05-16 07:55:40,427 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:3:2026-05-16 07:55:40,846 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb w=0 total=100 de=54 en=35 ja=3 other=0 dropped=8 mean_burrows=114.3998
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:4:2026-05-16 07:55:40,919 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb w=1 total=100 de=56 en=35 ja=2 other=0 dropped=7 mean_burrows=116.1064
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:5:2026-05-16 07:55:40,985 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb w=2 total=100 de=54 en=36 ja=4 other=0 dropped=6 mean_burrows=116.1669
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:6:2026-05-16 07:55:40,995 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:7:2026-05-16 07:55:41,070 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=0 total=100 de=51 en=36 ja=5 other=0 dropped=8 mean_burrows=113.2953
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:8:2026-05-16 07:55:41,135 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=1 total=100 de=55 en=35 ja=1 other=0 dropped=9 mean_burrows=116.3416
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:9:2026-05-16 07:55:41,209 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=2 total=100 de=54 en=36 ja=4 other=0 dropped=6 mean_burrows=111.3366
.steering\20260514-m9-c-adopt-retrain-v2-impl\tasklist.md:59:- [ ] `python scripts/m9-c-adopt/tier_b_pilot.py --persona kant --rank 8
.steering\20260514-m9-c-adopt-retrain-v2-impl\tasklist.md:60:      --adapter data/lora/m9-c-adopt-v2/kant_r8_v2/ --multi-turn-max 6
.steering\20260514-m9-c-adopt-retrain-v2-impl\next-session-prompt-FINAL-training.md:43:   - `python scripts/m9-c-adopt/tier_b_pilot.py --persona kant --rank 8 \\
.steering\20260514-m9-c-adopt-retrain-v2-impl\next-session-prompt-FINAL-training.md:45:       --multi-turn-max 6 --max-focal-per-shard 300 \\
.steering\20260430-m9-eval-system\codex-review-step1-prompt.md:93:--turn-count INT                     default 200 (P3a target)
.steering\20260430-m9-eval-system\codex-review-step1-prompt.md:94:--cycle-count INT                    default 3 (stimulus only — P3 design integrity)
.steering\20260430-m9-eval-system\codex-review-natural-gating-v2.md:2954:  1051	        "--turn-count",
.steering\20260430-m9-eval-system\codex-review-natural-gating-v2.md:2964:  1061	        "--cycle-count",
.steering\20260430-m9-eval-system\codex-review-natural-gating-v2.md:3091:/bin/zsh -lc "rg -n \"wall_timeout_min|capture_natural|add_argument\\(|--wall-timeout-min|turn-count|condition\" tests src/erre_sandbox/cli/eval_run_golden.py tests/test_cli tests/test_integration" in /Users/johnd/ERRE-Sand Box
.steering\20260430-m9-eval-system\codex-review-natural-gating-v2.md:3115:src/erre_sandbox/cli/eval_run_golden.py:12:  persona accumulates ``--turn-count`` turns across ``--cycle-count`` cycles.
.steering\20260430-m9-eval-system\codex-review-natural-gating-v2.md:3117:src/erre_sandbox/cli/eval_run_golden.py:20:  focal speaker has uttered ``--turn-count`` turns.
.steering\20260430-m9-eval-system\codex-review-natural-gating-v2.md:3122:src/erre_sandbox/cli/eval_run_golden.py:48:        --turn-count 200 --cycle-count 3 \\
.steering\20260430-m9-eval-system\codex-review-natural-gating-v2.md:3143:src/erre_sandbox/cli/eval_run_golden.py:1051:        "--turn-count",
.steering\20260430-m9-eval-system\codex-review-natural-gating-v2.md:3207:    12	  persona accumulates ``--turn-count`` turns across ``--cycle-count`` cycles.
.steering\20260430-m9-eval-system\codex-review-natural-gating-v2.md:3215:    20	  focal speaker has uttered ``--turn-count`` turns.
.steering\20260430-m9-eval-system\codex-review-natural-gating-v2.md:3243:    48	        --turn-count 200 --cycle-count 3 \\
.steering\20260430-m9-eval-system\codex-review-prompt-phase2-run0-timeout.md:216:  cognition_period に turn-count に依存する degradation (memory growth、
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt.md:45:   - `python scripts/m9-c-adopt/tier_b_pilot.py --persona kant --rank 8 \
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt.md:47:       --multi-turn-max 6 --output .steering/<task>/tier-b-pilot-multiturn-kant-r8-v2.duckdb`
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt.md:129:- pilot 採取: `python scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt.md:131:    --multi-turn-max 6 --max-focal-per-shard 300 --output ...`
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt.md:140:  baseline artefact (`tier-b-pilot-multiturn-kant-nolora-*.json`) と比較
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt.md:199:- [ ] multi-turn pilot recapture (`tier_b_pilot.py --rank 8 v2 adapter`、
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt.md:214:  `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-*.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt-FINAL.md:56:   - `python scripts/m9-c-adopt/tier_b_pilot.py --persona kant --rank 8 \\
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt-FINAL.md:58:       --multi-turn-max 6 --max-focal-per-shard 300 \\
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt-FINAL.md:64:     (`.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-*.json`)
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt-FINAL.md:177:- pilot: `python scripts/m9-c-adopt/tier_b_pilot.py --persona kant --rank 8 \\
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt-FINAL.md:179:    --multi-turn-max 6 --max-focal-per-shard 300 \\
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt-FINAL.md:189:    `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-*.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt-FINAL.md:280:  `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-*.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\design-final.md:137:    `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-{vendi-semantic,burrows,icc}.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\da1-thresholds-recalibrated.json:9:    "vendi_semantic": "tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json",
.steering\20260514-m9-c-adopt-retrain-v2-design\da1-thresholds-recalibrated.json:10:    "burrows": "tier-b-pilot-multiturn-kant-nolora-burrows.json",
.steering\20260514-m9-c-adopt-retrain-v2-design\da1-thresholds-recalibrated.json:11:    "icc": "tier-b-icc-multiturn-kant-nolora.json"
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:37:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:38:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-burrows.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:39:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-icc.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:570:    `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-{vendi-semantic,burrows,icc}.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1317:- `scripts/m9-c-adopt/tier_b_pilot.py`:
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1318:  - `--multi-turn-max N` flag (default 1 縺ｧ驕主悉莠呈鋤)
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1323:  - run_id 蜻ｽ蜷・`{persona}_{r{rank}|nolora}_run{idx}_pilot`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1340:- consumer execution (matched baseline + multi-turn LoRA ﾃ・3 rank + nolora縲・  Vendi + Burrows + Big5 ICC + matrix render): **334 s 竕・5.5 min**
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1378:- `--turn-count 300 --cycle-count 6` 繧堤ｶｭ謖・(compute 謚大宛)
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1383:- mitigation 1 (full-battery `--turn-count 528+`) 縺ｯ compute ~5-6h 縺ｨ驥阪￥縲∵悽 PR
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1434:  - `tier_b_pilot.py`: `--no-lora-control` flag 霑ｽ蜉
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1456:- **LOW-2** (`--multi-turn-max 6`): 謗｡逕ｨ ADOPT-WITH-NOTE縲Ｅesign.md 縺ｫ
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1548:  .steering\20260513-m9-c-adopt\decisions.md:546:       実装 (`scripts/m9-c-adopt/tier_b_pilot.py`)、smoke test、full
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1642:  .steering\20260513-m9-c-adopt\decisions.md:720:    - pilot 6 shards は本 PR で新規実装の `tier_b_pilot.py` 単発 stim →
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4330:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4331:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-burrows.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4332:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-icc.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4510:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4511:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-burrows.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4512:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-icc.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4558:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path .steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-icc.json' in C:\ERRE-Sand_Box
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4560:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path .steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-burrows.json' in C:\ERRE-Sand_Box
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4562:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path .steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json' in C:\ERRE-Sand_Box
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4574:    "kant_nolora_run0_stim.duckdb",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4575:    "kant_nolora_run1_stim.duckdb"
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4589:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4596:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4603:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4610:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4617:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4624:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4666:    "kant_nolora_run0_stim.duckdb",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4667:    "kant_nolora_run1_stim.duckdb"
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4671:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4739:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4806:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4873:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:4942:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5011:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5599:Get-Content : パス 'C:\ERRE-Sand_Box\.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-icc
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5604:    + CategoryInfo          : ObjectNotFound: (C:\ERRE-Sand_Bo...nolora-icc.json:String) [Get-Content], ItemNotFoundEx 
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5610:Get-Content : パス 'C:\ERRE-Sand_Box\.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-icc
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5615:    + CategoryInfo          : ObjectNotFound: (C:\ERRE-Sand_Bo...nolora-icc.json:String) [Get-Content], ItemNotFoundEx 
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5629:.steering/20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5630:.steering/20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-burrows.json
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5634:.steering/20260514-m9-c-adopt-pilot-multiturn\tier-b-icc-multiturn-kant-nolora.json
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5641:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path .steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-icc-multiturn-kant-nolora.json' in C:\ERRE-Sand_Box
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5650:    "kant_nolora_run0_stim.duckdb",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5651:    "kant_nolora_run1_stim.duckdb"
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5674:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5692:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5710:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5728:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5746:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:5764:      "run_id": "kant_nolora_run1_stim",
.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:37:v2 §Phase B 通り。`--cycle-count 6` を必ず指定 (PR #140 反映、cycle-count=3
.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:48:      --turn-count 500 --cycle-count 6 \
.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:67:PR #140 の audit gate が `cycle-count=3` で fire するのを `cycle-count=6` で
.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:71:2. `--cycle-count 7` または `--turn-count 600` に上げて当該 cell のみ再採取
.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:88:      --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:110:  --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:135:    --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:293:該当 cell のみ `--cycle-count 7` で再採取。それでも focal<500 なら
.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:294:`--turn-count 600` に拡張。それでも失敗なら Mac へ報告 (PR #140 audit gate 修正
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review-prompt.md:24:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review-prompt.md:25:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-burrows.json`
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review-prompt.md:26:- `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-icc.json`
.steering\20260430-m9-eval-system\g-gear-p3a-rerun-prompt.md:89:  --turn-count 30 --wall-timeout-min 10 \
.steering\20260430-m9-eval-system\g-gear-p3a-rerun-prompt.md:116:     --turn-count 30 --wall-timeout-min 60 \
.steering\20260430-m9-eval-system\g-gear-p3a-rerun-prompt.md:120:     --turn-count 30 --wall-timeout-min 60 \
.steering\20260430-m9-eval-system\g-gear-p3a-rerun-prompt.md:124:     --turn-count 30 --wall-timeout-min 60 \
.steering\20260430-m9-eval-system\g-gear-p3a-rerun-prompt-v2.md:114:  --turn-count 30 --wall-timeout-min 120 \
.steering\20260430-m9-eval-system\g-gear-p3a-rerun-prompt-v2.md:151:     --turn-count 30 --wall-timeout-min 120 \
.steering\20260430-m9-eval-system\g-gear-p3a-rerun-prompt-v2.md:156:     --turn-count 30 --wall-timeout-min 120 \
.steering\20260430-m9-eval-system\g-gear-p3a-rerun-prompt-v2.md:161:     --turn-count 30 --wall-timeout-min 120 \
.steering\20260430-m9-eval-system\g-gear-p3a-prompt.md:102:--turn-count INT                        default 200 (P3a 専用、P3 本番は別フラグで 500)
.steering\20260430-m9-eval-system\g-gear-p3a-prompt.md:103:--cycle-count INT                       default 3 (stimulus condition のみ参照)
.steering\20260430-m9-eval-system\g-gear-p3a-prompt.md:158:      --turn-count 200 \
.steering\20260514-m9-c-adopt-pilot-multiturn\validation-multiturn-kant.json:8:      "shard": "kant_nolora_run0_stim.duckdb",
.steering\20260514-m9-c-adopt-pilot-multiturn\validation-multiturn-kant.json:53:      "shard": "kant_nolora_run1_stim.duckdb",
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt.md:93:   --condition / --turn-count / --cycle-count / --wall-timeout-min` を熟読)
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt.md:150:    --turn-count 50 --wall-timeout-min 60 \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt.md:168:      --turn-count 500 --cycle-count 3 \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt.md:187:    --turn-count 500 --wall-timeout-min 360 \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt.md:203:  --turn-count 500 --wall-timeout-min 360 \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:109:  --turn-count 50 --cycle-count 1 \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:130:**wall-limited stop** させるため `--turn-count 2000` で early stop を抑制 (Codex
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:131:H2 反映、`--turn-count 1000` だと 600 min cell が 535 min で stop してしまう)。
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:146:    --turn-count 2000 --wall-timeout-min "$WALL" \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:191:| 104 | 600 | 1.55-1.59 | 930-954 | 791-1097 | partial (turn-count=2000 で early stop しない) |
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:261:**重要 (Codex H1 反映)**: `--cycle-count 6` を指定すること。`cycle-count=3` だと
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:263:として fatal 化する。`cycle-count=6` で focal≈504 を確保する。
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:270:      --turn-count 500 --cycle-count 6 \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:302:      --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:321:  --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:346:    --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:516:  --turn-count 2000 --wall-timeout-min 360 \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:539:  --turn-count 500 --cycle-count 7 \
.steering\20260430-m9-eval-system\decisions.md:784:**B/C parity 比較** (m9 evaluation contract `--turn-count 500` 維持):
.steering\20260430-m9-eval-system\decisions.md:830:- `--turn-count 500` 以外に拡張する場合 (例: 1000) は throughput 線形外挿で
.steering\20260430-m9-eval-system\codex-review.md:3274:    39	            "preparation and for baseline turn-count reporting."
.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-FINAL.md:58:   - `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-{vendi-semantic,burrows,icc}.json`
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:11:    "kant_nolora_run0_stim.duckdb",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:12:    "kant_nolora_run1_stim.duckdb"
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:26:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:33:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:40:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:47:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:54:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:61:      "run_id": "kant_nolora_run1_stim",
.steering\20260430-m9-eval-system\codex-review-step1.raw.log:106:--turn-count INT                     default 200 (P3a target)
.steering\20260430-m9-eval-system\codex-review-step1.raw.log:107:--cycle-count INT                    default 3 (stimulus only — P3 design integrity)
.steering\20260430-m9-eval-system\codex-review-step1.raw.log:6349:  src\erre_sandbox\cli\export_log.py:39:            "preparation and for baseline turn-count reporting."
.steering\20260514-m9-c-adopt-pilot-multiturn\tasklist.md:15:- [ ] `tier_b_pilot.py` 拡張: `--multi-turn-max N` flag、`_focal_turn_count`
.steering\20260514-m9-c-adopt-pilot-multiturn\tasklist.md:20:- [ ] Smoke test: `--turn-count 10 --multi-turn-max 6` で kant_r8_real 単 cycle、
.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-scenario-II-retrain-v2.md:46:- multi-turn pilot 再採取 (本 PR 拡張済 driver `tier_b_pilot.py --multi-turn-max 6` 再利用)
.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-scenario-II-retrain-v2.md:58:- 既存 artefact `tier-b-pilot-multiturn-kant-nolora-{vendi,burrows,icc}.json`
.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-scenario-II-retrain-v2.md:81:- multi-turn pilot 再採取 (`tier_b_pilot.py --multi-turn-max 6 --rank 8` で
.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:12:- **背景**: design.md 初版 (no-LoRA SGLang control なし、turn-count 300 単独
.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:28:- `--turn-count 300 --cycle-count 6` を維持 (compute 抑制)
.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:34:- mitigation 1 (full-battery `--turn-count 528+`) は compute ~5-6h と重く、本 PR
.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:96:  - `tier_b_pilot.py`: `--no-lora-control` flag 追加
.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:126:- **LOW-2** (`--multi-turn-max 6`): 採用 ADOPT-WITH-NOTE。design.md に
.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-scenario-I-phase-e-direct.md:32:4. `scripts/m9-c-adopt/tier_b_pilot.py` (multi-turn 拡張済、Phase E でも再利用)
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-burrows.json:32:    "kant_nolora_run0_stim.duckdb",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-burrows.json:33:    "kant_nolora_run1_stim.duckdb"
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-burrows.json:37:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-burrows.json:105:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-burrows.json:172:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-burrows.json:239:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-burrows.json:308:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-pilot-multiturn-kant-nolora-burrows.json:377:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:54:### 拡張内容 (`scripts/m9-c-adopt/tier_b_pilot.py`)
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:57:   - `--multi-turn-max N` (default `1` で過去互換、investigation で
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:58:     `--multi-turn-max 6` を使用。Kant max expected_turn_count=3 のため 6 は
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:98:8. **default `--multi-turn-max`**: `1` (single-turn mode 過去互換)。investigation
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:99:   採取は `--multi-turn-max 6` で実行。
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:102:   `{persona}_nolora_run{idx}_pilot` (LoRA-on shard と分離可能)。
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:109:- **no-LoRA control 2 shard** (HIGH-1): `kant_nolora_run{0,1}_stim.duckdb`
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:110:- `--turn-count 300 --cycle-count 6 --multi-turn-max 6`
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:166:- `scripts/m9-c-adopt/tier_b_pilot.py` — multi-turn 採取拡張 (上記)
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:184:- `scripts/m9-c-adopt/tier_b_pilot.py` の `--multi-turn-max` default は `1` の
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:209:  `--turn-count 10 --multi-turn-max 6` で kant_r8_real adapter を 1 cycle 走らせ、
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:220:.venv/Scripts/python.exe scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:222:  --turn-count 10 --cycle-count 2 --multi-turn-max 6 \
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:262:  `--multi-turn-max` を渡さなければ完全に single-turn pilot と同じ挙動。
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:274:2. **`expected_turn_count` の handling**: `--multi-turn-max 6` で全 stimulus の
.steering\20260514-m9-c-adopt-pilot-multiturn\requirement.md:25:- `scripts/m9-c-adopt/tier_b_pilot.py` を multi-turn 採取可能に拡張
.steering\20260514-m9-c-adopt-pilot-multiturn\requirement.md:45:- [ ] `tier_b_pilot.py` multi-turn 拡張 + `--multi-turn-max N` flag (default 1 で
.steering\20260514-m9-c-adopt-pilot-multiturn\requirement.md:72:- `scripts/m9-c-adopt/tier_b_pilot.py` (拡張対象)
.steering\20260514-m9-c-adopt-pilot-multiturn\run_pilot_multiturn.sh:30:    "${PYBIN}" scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_pilot_multiturn.sh:32:      --turn-count "${TURN_COUNT}" --cycle-count "${CYCLE_COUNT}" \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_pilot_multiturn.sh:33:      --multi-turn-max "${MULTI_TURN_MAX}" \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_pilot_multiturn.sh:45:  out="${PILOT_DIR}/${PERSONA}_nolora_run${run_idx}_stim.duckdb"
.steering\20260514-m9-c-adopt-pilot-multiturn\run_pilot_multiturn.sh:50:  log="${LOGDIR}/${PERSONA}_nolora_run${run_idx}.log"
.steering\20260514-m9-c-adopt-pilot-multiturn\run_pilot_multiturn.sh:51:  echo "[start nolora] run=${run_idx} -> ${out}"
.steering\20260514-m9-c-adopt-pilot-multiturn\run_pilot_multiturn.sh:53:  "${PYBIN}" scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_pilot_multiturn.sh:55:    --turn-count "${TURN_COUNT}" --cycle-count "${CYCLE_COUNT}" \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_pilot_multiturn.sh:56:    --multi-turn-max "${MULTI_TURN_MAX}" \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_pilot_multiturn.sh:62:  echo "[done  nolora] run=${run_idx} elapsed=${elapsed}s out=${out}"
.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-scenario-III-phase-e-amended.md:23:   (`tier_b_pilot.py` `--multi-turn-max 6` で full battery 採取)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\blockers.md:14:- **原因**: `tier_b_pilot.py` は shard に rate metadata を保存していない。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\blockers.md:18:  `tier_b_pilot.py` 改修は本 PR scope 外とする。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\blockers.md:21:    など) を `metadata` テーブルに保存する pattern を `tier_b_pilot.py`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\blockers.md:49:  - eval shard 採取 (本 PR の `tier_b_pilot.py` invocation を persona
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:67:nolora_shards="${PILOT_DIR}/kant_nolora_run*_stim.duckdb"
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:68:echo "[nolora] vendi semantic"
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:71:  --shards-glob "${nolora_shards}" \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:73:  --output "${STEERING}/tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json" \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:74:  > "${STEERING}/logs/mt_nolora_vendi.log" 2>&1
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:76:echo "[nolora] burrows delta"
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:79:  --shards-glob "${nolora_shards}" \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:81:  --output "${STEERING}/tier-b-pilot-multiturn-kant-nolora-burrows.json" \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:82:  > "${STEERING}/logs/mt_nolora_burrows.log" 2>&1
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:84:echo "[nolora] Big5 ICC (SGLang base, T=0.7)"
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:87:  --shards-glob "${nolora_shards}" \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:91:  --output "${STEERING}/tier-b-icc-multiturn-kant-nolora.json" \
.steering\20260514-m9-c-adopt-pilot-multiturn\run_consumers.sh:92:  > "${STEERING}/logs/mt_nolora_icc.log" 2>&1
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:46:7. `scripts/m9-c-adopt/tier_b_pilot.py` (拡張対象、現在 single-turn のみ)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:386:  26: ### 諡｡蠑ｵ蜀・ｮｹ (`scripts/m9-c-adopt/tier_b_pilot.py`)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:389:  29:    - `--multi-turn-max N` (default `1` 縺ｧ驕主悉莠呈鋤縲（nvestigation 縺ｧ `--multi-turn-max 6` 繧剃ｽｿ逕ｨ)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:418:  58:    turn loop 縺ｯ騾比ｸｭ蜀埼幕縺励↑縺・《timulus 蜊倅ｽ阪〒 resume)縲・8. **default `--multi-turn-max`**: `1` (single-turn mode 驕主悉莠呈鋤)縲Ｊnvestigation
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:419:  59:    謗｡蜿悶・ `--multi-turn-max 6` 縺ｧ螳溯｡後・
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:425:  65: - `--turn-count 300 --cycle-count 6 --multi-turn-max 6`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:460: 100: - `scripts/m9-c-adopt/tier_b_pilot.py` 窶・multi-turn 謗｡蜿匁僑蠑ｵ (荳願ｨ・
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:477: 117: - `scripts/m9-c-adopt/tier_b_pilot.py` 縺ｮ `--multi-turn-max` default 縺ｯ `1` 縺ｮ
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:490: 130:   `--turn-count 10 --multi-turn-max 6` 縺ｧ kant_r8_real adapter 繧・1 cycle 襍ｰ繧峨○縲・  DuckDB shard 縺ｫ turn_index 0..N-1 縺・alternating speaker 縺ｧ譖ｸ縺崎ｾｼ縺ｾ繧後※縺・ｋ縺薙→繧・  逶ｮ隕也｢ｺ隱阪・- **邨ｱ蜷医ユ繧ｹ繝・*: 6 shard 謗｡蜿門ｮ碁≠縺御ｺ句ｮ滉ｸ翫・邨ｱ蜷医ユ繧ｹ繝医Ｄonsumer (Vendi/ICC/Burrows)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:496: 136: .venv/Scripts/python.exe scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:498: 138:   --turn-count 10 --cycle-count 2 --multi-turn-max 6 \
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:510: 150:   `--multi-turn-max` 繧呈ｸ｡縺輔↑縺代ｌ縺ｰ螳悟・縺ｫ single-turn pilot 縺ｨ蜷後§謖吝虚縲・- 譁ｰ directory `data/eval/m9-c-adopt-tier-b-pilot-multiturn/` 縺ｸ縺ｮ shard 譖ｸ縺榊・縺励・
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:517: 157:    邨檎罰 (豺ｷ蝨ｨ backend)" 繧・"interlocutor 縺ｯ蝗ｺ螳・utterance (no-op)" 繧呈､懆ｨ弱＠縺溘′縲・   baseline 縺ｨ蜷・protocol 縺ｧ蟇ｾ豈斐☆繧九↓縺ｯ same-inference-fn 縺梧怙繧・apples-to-apples縲・2. **`expected_turn_count` 縺ｮ handling**: `--multi-turn-max 6` 縺ｧ蜈ｨ stimulus 縺ｮ
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:551:  21: - `scripts/m9-c-adopt/tier_b_pilot.py` 繧・multi-turn 謗｡蜿門庄閭ｽ縺ｫ諡｡蠑ｵ
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:569:  39: - [ ] `tier_b_pilot.py` multi-turn 諡｡蠑ｵ + `--multi-turn-max N` flag (default 1 縺ｧ
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:593:  63: - `scripts/m9-c-adopt/tier_b_pilot.py` (諡｡蠑ｵ蟇ｾ雎｡)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:629:  25: - `scripts/m9-c-adopt/tier_b_pilot.py` を multi-turn 採取可能に拡張
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:649:  45: - [ ] `tier_b_pilot.py` multi-turn 拡張 + `--multi-turn-max N` flag (default 1 で
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:676:  72: - `scripts/m9-c-adopt/tier_b_pilot.py` (拡張対象)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:717:  36: ### 拡張内容 (`scripts/m9-c-adopt/tier_b_pilot.py`)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:720:  39:    - `--multi-turn-max N` (default `1` で過去互換、investigation で `--multi-turn-max 6` を使用)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:755:  74: 8. **default `--multi-turn-max`**: `1` (single-turn mode 過去互換)。investigation
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:756:  75:    採取は `--multi-turn-max 6` で実行。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:763:  82: - `--turn-count 300 --cycle-count 6 --multi-turn-max 6`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:799: 118: - `scripts/m9-c-adopt/tier_b_pilot.py` — multi-turn 採取拡張 (上記)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:817: 136: - `scripts/m9-c-adopt/tier_b_pilot.py` の `--multi-turn-max` default は `1` の
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:842: 161:   `--turn-count 10 --multi-turn-max 6` で kant_r8_real adapter を 1 cycle 走らせ、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:853: 172: .venv/Scripts/python.exe scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:855: 174:   --turn-count 10 --cycle-count 2 --multi-turn-max 6 \
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:867: 186:   `--multi-turn-max` を渡さなければ完全に single-turn pilot と同じ挙動。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:879: 198: 2. **`expected_turn_count` の handling**: `--multi-turn-max 6` で全 stimulus の
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:1070: 169:   `compute_baseline_vendi.py` / `tier_b_pilot.py` / `bench_per_rank.sh`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:1351:254:- **症状**: Phase B pilot driver (`tier_b_pilot.py`) は DA-11 で single-turn
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:1600: 546:        実装 (`scripts/m9-c-adopt/tier_b_pilot.py`)、smoke test、full
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:1720: 720:     - pilot 6 shards は本 PR で新規実装の `tier_b_pilot.py` 単発 stim →
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:1794: 254: - **症状**: Phase B pilot driver (`tier_b_pilot.py`) は DA-11 で single-turn
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:1815:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); $i=1; Get-Content -Encoding UTF8 -Path scripts/m9-c-adopt/tier_b_pilot.py | ForEach-Object { '"'{0,4}: {1}' -f "'$i++, $_ }' in C:\ERRE-Sand_Box
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:2076:  24:     python scripts/m9-c-adopt/tier_b_pilot.py \\
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:2078:  26:         --turn-count 300 --cycle-count 6 \\
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:2596: 544:     p.add_argument("--turn-count", type=int, default=_DEFAULT_TURN_COUNT)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:2597: 545:     p.add_argument("--cycle-count", type=int, default=_DEFAULT_CYCLE_COUNT)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:4516:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); rg -n "eval_run_golden|turn-count|cycle-count|kant_stimulus_run|golden" .steering/20260513-m9-c-adopt .steering/20260430-m9-eval-system docs | Select-Object -First 100' in C:\ERRE-Sand_Box
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:4914:src/erre_sandbox\cli\eval_run_golden.py:20:  focal speaker has uttered ``--turn-count`` turns.
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5698:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5711:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5717:+  1. Apples-to-apples pilot を名乗るなら `--turn-count` を 500+ focal/run に上げ、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5719:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5830:+  - `scripts/m9-c-adopt/tier_b_pilot.py:447`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5831:+  - `scripts/m9-c-adopt/tier_b_pilot.py:452`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5832:+  - `scripts/m9-c-adopt/tier_b_pilot.py:480`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5882:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5969:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5982:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5988:+  1. Apples-to-apples pilot を名乗るなら `--turn-count` を 500+ focal/run に上げ、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5990:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6101:+  - `scripts/m9-c-adopt/tier_b_pilot.py:447`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6102:+  - `scripts/m9-c-adopt/tier_b_pilot.py:452`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6103:+  - `scripts/m9-c-adopt/tier_b_pilot.py:480`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6153:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6238:  59:   `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6251:  72:   - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6257:  78:   1. Apples-to-apples pilot を名乗るなら `--turn-count` を 500+ focal/run に上げ、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6259:  80:      Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6370: 191:   - `scripts/m9-c-adopt/tier_b_pilot.py:447`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6371: 192:   - `scripts/m9-c-adopt/tier_b_pilot.py:452`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6372: 193:   - `scripts/m9-c-adopt/tier_b_pilot.py:480`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6422: 243: ### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6504:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6517:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6523:+  1. Apples-to-apples pilot を名乗るなら `--turn-count` を 500+ focal/run に上げ、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6525:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6636:+  - `scripts/m9-c-adopt/tier_b_pilot.py:447`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6637:+  - `scripts/m9-c-adopt/tier_b_pilot.py:452`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6638:+  - `scripts/m9-c-adopt/tier_b_pilot.py:480`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6688:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6785:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6798:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6804:+  1. Apples-to-apples pilot を名乗るなら `--turn-count` を 500+ focal/run に上げ、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6806:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6917:+  - `scripts/m9-c-adopt/tier_b_pilot.py:447`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6918:+  - `scripts/m9-c-adopt/tier_b_pilot.py:452`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6919:+  - `scripts/m9-c-adopt/tier_b_pilot.py:480`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6969:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7064:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7077:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7083:+  1. Apples-to-apples pilot を名乗るなら `--turn-count` を 500+ focal/run に上げ、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7085:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7196:+  - `scripts/m9-c-adopt/tier_b_pilot.py:447`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7197:+  - `scripts/m9-c-adopt/tier_b_pilot.py:452`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7198:+  - `scripts/m9-c-adopt/tier_b_pilot.py:480`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7248:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7354:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7367:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7373:+  1. Apples-to-apples pilot を名乗るなら `--turn-count` を 500+ focal/run に上げ、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7375:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7486:+  - `scripts/m9-c-adopt/tier_b_pilot.py:447`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7487:+  - `scripts/m9-c-adopt/tier_b_pilot.py:452`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7488:+  - `scripts/m9-c-adopt/tier_b_pilot.py:480`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7538:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:23:- `--v2-shards` / `--nolora-shards` / `--kernel-type` / `--allowlist-path`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:32:  shards are ~equal mass (n_v2 ≈ n_nolora) so this is theoretically a
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:60:- The 4 shards (`kant_r8v3_run{0,1}_stim.duckdb` + `kant_planb_nolora_run{0,1}_stim.duckdb`) use the same `tier_b_pilot.py` invocation
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:61:  parameters as the v2 baseline (`--turn-count 300 --cycle-count 6
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:62:  --multi-turn-max 6`). Confirm apples-to-apples with the v2 reference
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:63:  (`data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`).
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:69:  Confirm that the `_NO_LORA_MODEL` routing in `tier_b_pilot.py` matches
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-icc-multiturn-kant-nolora.json:8:    "kant_nolora_run0_stim.duckdb",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-icc-multiturn-kant-nolora.json:9:    "kant_nolora_run1_stim.duckdb"
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-icc-multiturn-kant-nolora.json:32:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-icc-multiturn-kant-nolora.json:50:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-icc-multiturn-kant-nolora.json:68:      "run_id": "kant_nolora_run0_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-icc-multiturn-kant-nolora.json:86:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-icc-multiturn-kant-nolora.json:104:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\tier-b-icc-multiturn-kant-nolora.json:122:      "run_id": "kant_nolora_run1_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\report.md:105:- `scripts/m9-c-adopt/tier_b_pilot.py`:
.steering\20260514-m9-c-adopt-pilot-multiturn\report.md:106:  - `--multi-turn-max N` flag (default 1 で過去互換)
.steering\20260514-m9-c-adopt-pilot-multiturn\report.md:111:  - run_id 命名 `{persona}_{r{rank}|nolora}_run{idx}_pilot`
.steering\20260514-m9-c-adopt-pilot-multiturn\report.md:130:- consumer execution (matched baseline + multi-turn LoRA × 3 rank + nolora、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:28:  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:41:  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:47:  1. Apples-to-apples pilot を名乗るなら `--turn-count` を 500+ focal/run に上げ、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:49:     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:160:  - `scripts/m9-c-adopt/tier_b_pilot.py:447`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:161:  - `scripts/m9-c-adopt/tier_b_pilot.py:452`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:162:  - `scripts/m9-c-adopt/tier_b_pilot.py:480`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:212:### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review-prompt.md:33:7. `scripts/m9-c-adopt/tier_b_pilot.py` (拡張対象、現在 single-turn のみ)
.steering\20260516-m9-c-adopt-da15-impl\next-session-prompt-FINAL-plan-b.md:39:   - 既存 `tier_b_pilot.py` の generation-side prompt + persona response
.steering\20260516-m9-c-adopt-da15-impl\next-session-prompt-FINAL-plan-b.md:84:10. `scripts/m9-c-adopt/tier_b_pilot.py` (generation-side prompt base)
.steering\20260516-m9-c-adopt-da15-adr\codex-review-prompt.md:75:      "diff_v2_minus_nolora": -0.12804119393459246,
.steering\20260516-m9-c-adopt-da15-adr\codex-review-prompt.md:166:- `scripts/m9-c-adopt/tier_b_pilot.py` — SGLang LoRA driver (no de-focused
.steering\20260516-m9-c-adopt-da15-adr\design.md:104:  monolog/long-form bias の stimulus driver。tier_b_pilot.py の generation-
.steering\20260516-m9-c-adopt-da15-adr\decisions.md:17:    `tier_b_pilot.py`, `validate_multiturn_shards.py` の 7 file。
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:18:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:19:    "kant_r8v2_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:21:  "nolora_shards": [
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:22:    "kant_nolora_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:23:    "kant_nolora_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:34:    "nolora_scores": [
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:43:    "nolora_mean": 33.31090045820279,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:63:    "nolora_mean": 27.965639782002224,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:80:    "nolora_mean": 29.701891914615803,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:95:      "nolora_mean": 18.23903177478302,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:109:      "nolora_mean": 26.60142873056358,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:118:      "n_nolora": 19,
.steering\20260516-m9-c-adopt-da15-impl\design.md:35:kant_r8v2_run{0,1}_stim.duckdb`、no-LoRA shards = `data/eval/m9-c-adopt-tier-
.steering\20260516-m9-c-adopt-da15-impl\design.md:36:b-pilot-multiturn/kant_nolora_run{0,1}_stim.duckdb` (3 windows/shard × 2 shard
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:88:      "diff_v2_minus_nolora": -0.12804119393459246,
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:179:- `scripts/m9-c-adopt/tier_b_pilot.py` — SGLang LoRA driver (no de-focused
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:1378:    1. **G-GEAR foundational work** 繧貞・陦・ SGLang LoRA pilot driver 譁ｰ隕・       螳溯｣・(`scripts/m9-c-adopt/tier_b_pilot.py`)縲《moke test縲’ull
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:1530:    - pilot 6 shards 縺ｯ譛ｬ PR 縺ｧ譁ｰ隕丞ｮ溯｣・・ `tier_b_pilot.py` 蜊倡匱 stim 竊・      kant 1-turn = 300 turn/run ﾃ・6 = 1800 turn 縺ｮ **single-turn** 謗｡蜿・    - single-turn 險ｭ險医・ DA-11 scope narrowing 縺ｧ遒ｺ螳・("multi-turn 縺ｯ
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:1703:    - `tier_b_pilot.py` (`--multi-turn-max` + `--no-lora-control` + atomic
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:1841:  `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-*.json`
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:2624:      "diff_v2_minus_nolora": -0.12804119393459246,
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:2794:    "vendi_semantic": "tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json",
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:2795:    "burrows": "tier-b-pilot-multiturn-kant-nolora-burrows.json",
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:2796:    "icc": "tier-b-icc-multiturn-kant-nolora.json"
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3038:.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:4:  "metric": "vendi_semantic",
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3039:.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:68:  "scope_narrowing_note": "Per DA-11 (Phase B \u7b2c 3 \u30bb\u30c3\u30b7\u30e7\u30f3 scope narrowing): Vendi only. Big5 ICC consumer + Burrows \u0394 language handling are deferred to Phase B \u7b2c 4 \u30bb\u30c3\u30b7\u30e7\u30f3 (separate PR)."
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3040:.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:10:  "lang_confidence_threshold": 0.85,
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3041:.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:444:  "named_limitation": "Option A language routing (DA-11): en/ja utterances dropped because there is no Cambridge Edition English Kant reference (license-pending, M9-eval-system separate PR) and Japanese Burrows tokenization is deferred (H-2). Effective sample size is the de_fraction above."
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3155:scripts/m9-c-adopt\tier_b_pilot.py:276:    model_name: str,
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3156:scripts/m9-c-adopt\tier_b_pilot.py:285:        "model": model_name,
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3157:scripts/m9-c-adopt\tier_b_pilot.py:475:        model_name = _NO_LORA_MODEL
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3158:scripts/m9-c-adopt\tier_b_pilot.py:478:        model_name = args.adapter_name or f"{persona_id}_r{rank}_real"
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3159:scripts/m9-c-adopt\tier_b_pilot.py:514:            adapter_name=model_name,
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3160:scripts/m9-c-adopt\tier_b_pilot.py:517:        logger.info("adapter %s confirmed loaded on sglang", model_name)
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3161:scripts/m9-c-adopt\tier_b_pilot.py:519:        logger.info("--no-lora-control mode: routing to base model %s", model_name)
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3162:scripts/m9-c-adopt\tier_b_pilot.py:576:                        model_name=model_name,
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3311:    - pilot 6 shards は本 PR で新規実装の `tier_b_pilot.py` 単発 stim →
.steering\20260516-m9-c-adopt-da15-adr\codex-review.stderr:3605:scripts/m9-c-adopt\tier_b_pilot.py
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:18:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:19:    "kant_r8v2_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:21:  "nolora_shards": [
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:22:    "kant_nolora_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:23:    "kant_nolora_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:34:    "nolora_scores": [
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:43:    "nolora_mean": 17.423262628268116,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:63:    "nolora_mean": 15.916551276233836,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:80:    "nolora_mean": 15.975736285438902,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:95:      "nolora_mean": 13.721859894691466,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:109:      "nolora_mean": 14.123587518550822,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:118:      "n_nolora": 19,
.steering\20260516-m9-c-adopt-da15-impl\codex-review.md:3:- Why it matters: HIGH-3 requires DA-14 thresholds to remain unchanged. In DA-14, `.steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json:8-15` records `diff_v2_minus_nolora`, `diff_ci_95`, and `cohens_d` separately, with `threshold_ci = "ci_upper < 0"`. DA-15's `_bootstrap_window_d_ci()` instead appends `_cohens_d(ra, rb)` and returns `lo` / `hi` over that d distribution (`scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:142-163`), while `da15_verdict.py:73-90` treats `standard_bootstrap["hi"]` as the natural diff upper bound. This changes the statistical gate, even though the artifact says `diff_ci_upper_lt` (`.steering/20260516-m9-c-adopt-da15-impl/da15-rescore-e5-large-kant.json:44-48`).
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:18:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:19:    "kant_r8v2_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:21:  "nolora_shards": [
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:22:    "kant_nolora_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:23:    "kant_nolora_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:34:    "nolora_scores": [
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:43:    "nolora_mean": 4.086636064525256,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:63:    "nolora_mean": 3.8434021789993222,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:80:    "nolora_mean": 3.9439946362241134,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:95:      "nolora_mean": 3.2087718789025006,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:109:      "nolora_mean": 3.823814985831723,
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:118:      "n_nolora": 19,
.steering\20260509-m9-individual-layer-schema-add\tasklist.md:74:- [x] **既存 partial 退避**: 41 ファイルを `data/eval/partial/` へ移動 (15 stimulus duckdb cycle-count=3 fail + 3 natural .tmp + 18 logs + walltimes + meta)
.steering\20260509-m9-individual-layer-schema-add\tasklist.md:96:- [x] **判断 9 起票**: ~5h/cell wall budget 前提で multi-session 化、`timeout 360m` (6h cap) + run 単位分割、`--turn-count 500` 維持で B/C parity 確保
.steering\20260509-m9-individual-layer-schema-add\decisions.md:172:  - C: `--turn-count 500 → 200` に短縮 (B/C parity 破壊、M9 evaluation contract 変更、Codex review 要再依頼)
.steering\20260509-m9-individual-layer-schema-add\decisions.md:176:  1. **B/C parity 維持**: `--turn-count 500` を変更すると Phase B との直接比較性が崩れ、M9 evaluation contract も変わる (判断 9-bis 候補を回避)
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt.md:27:`cycle-count=6` で再採取。既存 5/6 採取分 (cycle-count=3、PR #140 audit gate
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt.md:50:- stimulus run0-4 × 3 persona = 15 .duckdb (5/6 採取、cycle-count=3 fail)
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt.md:85:      --turn-count 500 --cycle-count 6 \
.steering\20260509-m9-individual-layer-schema-add\codex-review.stderr:740: 144:   - `data/eval/golden/*_stimulus_run*.duckdb` — Phase B で再採取される (`cycle-count=6` audit gate hit のため)。再採取が **B-1 merge 後**ならこの問題なし。**B-1 merge 前の kick** ではあとで migration が必要。
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c.md:80:      --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c.md:177:- focal_observed: **全 15 cell で 504** (focal_target=500、+4 over-shoot は cycle-count=6 の自然な結果)
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c-revised.md:19:- `--turn-count 500` 維持 (B/C parity を破壊しない)
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c-revised.md:107:    --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260513-security-hardening-pre-m10\codex-review.stderr:2753:    12	  persona accumulates ``--turn-count`` turns across ``--cycle-count`` cycles.
.steering\20260513-security-hardening-pre-m10\codex-review.stderr:2761:    20	  focal speaker has uttered ``--turn-count`` turns.
.steering\20260513-security-hardening-pre-m10\codex-review.stderr:2789:    48	        --turn-count 200 --cycle-count 3 \\
.steering\20260513-security-hardening-pre-m10\codex-review.stderr:3100:  1355	        "--turn-count",
.steering\20260513-security-hardening-pre-m10\codex-review.stderr:3110:  1365	        "--cycle-count",
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c-5.md:39:- `--turn-count 500` 維持 (B/C parity)
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c-5.md:108:    --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c-5.md:235:- B/C parity: `--turn-count 500` 維持、stimulus 5 min/cell vs natural 5h13m/cell の throughput
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c-3.md:36:- `--turn-count 500` 維持 (B/C parity)
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c-3.md:104:    --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c-2.md:27:- `--turn-count 500` 維持 (B/C parity)
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c-2.md:95:    --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c-4.md:36:- `--turn-count 500` 維持 (B/C parity)
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt-phase-c-4.md:104:    --turn-count 500 --wall-timeout-min "$WALL" \
.steering\20260515-security-hardening-pre-m10-followup\codex-review.stderr:5228:    12	  persona accumulates ``--turn-count`` turns across ``--cycle-count`` cycles.
.steering\20260515-security-hardening-pre-m10-followup\codex-review.stderr:5236:    20	  focal speaker has uttered ``--turn-count`` turns.
.steering\20260515-security-hardening-pre-m10-followup\codex-review.stderr:5264:    48	        --turn-count 200 --cycle-count 3 \\
.steering\20260513-m9-c-adopt\next-session-prompt-pilot-multiturn-investigation.md:50:5. `scripts/m9-c-adopt/tier_b_pilot.py` (本セッションで multi-turn 拡張する
.steering\20260513-m9-c-adopt\next-session-prompt-pilot-multiturn-investigation.md:59:`scripts/m9-c-adopt/tier_b_pilot.py` 内 `_focal_turn_count()` を
.steering\20260513-m9-c-adopt\next-session-prompt-pilot-multiturn-investigation.md:76:CLI: `--multi-turn-max N` (default 1 で過去互換、本セッション investigation
.steering\20260513-m9-c-adopt\next-session-prompt-pilot-multiturn-investigation.md:93:- 採取モード: multi-turn (`--multi-turn-max 6` で stim × 6 alternating
.steering\20260513-m9-c-adopt\next-session-prompt-pilot-multiturn-investigation.md:228:- [ ] `tier_b_pilot.py` multi-turn 拡張 (CLI flag 追加 + interlocutor 設計)
.steering\20260513-m9-c-adopt\next-session-prompt-pilot-multiturn-investigation.md:259:- 既存 consumers: `scripts/m9-c-adopt/{compute_big5_icc,compute_burrows_delta,compute_baseline_vendi,da1_matrix,tier_b_pilot}.py`
.steering\20260513-m9-c-adopt\next-session-prompt-phase-b-4.md:22:driver 新規実装 (`scripts/m9-c-adopt/tier_b_pilot.py`)、3 rank × 2 run ×
.steering\20260513-m9-c-adopt\next-session-prompt-phase-b-4.md:47:7. `scripts/m9-c-adopt/tier_b_pilot.py` (pilot driver、SGLang LoRA routing)
.steering\20260513-m9-c-adopt\next-session-prompt-phase-b-4.md:287:- pilot driver: `scripts/m9-c-adopt/tier_b_pilot.py` (本 session で新規)
.steering\20260513-m9-c-adopt\decisions.md:546:       実装 (`scripts/m9-c-adopt/tier_b_pilot.py`)、smoke test、full
.steering\20260513-m9-c-adopt\decisions.md:720:    - pilot 6 shards は本 PR で新規実装の `tier_b_pilot.py` 単発 stim →
.steering\20260513-m9-c-adopt\decisions.md:927:    - `tier_b_pilot.py` (`--multi-turn-max` + `--no-lora-control` + atomic
.steering\20260513-m9-c-adopt\decisions.md:1079:  `.steering/20260514-m9-c-adopt-pilot-multiturn/tier-b-pilot-multiturn-kant-nolora-*.json`
.steering\20260513-m9-c-adopt\phase-b-report.md:169:  `compute_baseline_vendi.py` / `tier_b_pilot.py` / `bench_per_rank.sh`
.steering\20260513-m9-c-adopt\phase-b-progress.md:159:  `tier_b_pilot.py` / `bench_per_rank.sh`
.steering\20260513-m9-c-adopt\blockers.md:254:- **症状**: Phase B pilot driver (`tier_b_pilot.py`) は DA-11 で single-turn
.steering\20260513-m9-c-adopt\codex-review.stderr:2783:**B/C parity 豈碑ｼ・* (m9 evaluation contract `--turn-count 500` 邯ｭ謖・:
.steering\20260513-m9-c-adopt\codex-review.stderr:2821:  (萓・ 6h 雜・〒 systematic) 竊・Ollama / qwen3:8b throughput regression 繧堤桝縺・- `--turn-count 500` 莉･螟悶↓諡｡蠑ｵ縺吶ｋ蝣ｴ蜷・(萓・ 1000) 縺ｯ throughput 邱壼ｽ｢螟匁諺縺ｧ
.steering\20260513-m9-c-adopt\phase-b-logs\run_pilot.sh:26:    /root/erre-sandbox/.venv/bin/python /mnt/c/ERRE-Sand_Box/scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260513-m9-c-adopt\phase-b-logs\run_pilot.sh:28:      --turn-count "${TURN_COUNT}" --cycle-count "${CYCLE_COUNT}" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-burrows-plan-b-kant.json:10:  "n_windows_nolora": 6,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json:23:  "nolora_shards": [
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json:24:    "kant_planb_nolora_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json:25:    "kant_planb_nolora_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json:36:    "nolora_scores": [
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json:45:    "nolora_mean": 80.78330656549629,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json:65:    "nolora_mean": 69.22241146302044,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json:82:    "nolora_mean": 69.00969122995332,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json:97:      "nolora_mean": 55.884385865748335,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json:111:      "nolora_mean": 54.68762577115437,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-lex5-plan-b-kant.json:120:      "n_nolora": 25,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json:23:  "nolora_shards": [
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json:24:    "kant_planb_nolora_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json:25:    "kant_planb_nolora_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json:36:    "nolora_scores": [
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json:45:    "nolora_mean": 33.762240742340445,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json:65:    "nolora_mean": 28.143313717161416,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json:82:    "nolora_mean": 30.11283102633695,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json:97:      "nolora_mean": 18.09811219733678,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json:111:      "nolora_mean": 26.834484247426914,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-mpnet-plan-b-kant.json:120:      "n_nolora": 25,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json:23:  "nolora_shards": [
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json:24:    "kant_planb_nolora_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json:25:    "kant_planb_nolora_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json:36:    "nolora_scores": [
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json:45:    "nolora_mean": 4.040053820793086,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json:65:    "nolora_mean": 3.779507389266897,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json:82:    "nolora_mean": 3.8976578887432463,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json:97:      "nolora_mean": 3.1097916478604635,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json:111:      "nolora_mean": 3.785756305850816,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-e5large-plan-b-kant.json:120:      "n_nolora": 25,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json:23:  "nolora_shards": [
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json:24:    "kant_planb_nolora_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json:25:    "kant_planb_nolora_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json:36:    "nolora_scores": [
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json:45:    "nolora_mean": 17.386899428325226,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json:65:    "nolora_mean": 15.901533382563386,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json:82:    "nolora_mean": 15.902321794765735,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json:97:      "nolora_mean": 13.496548002035931,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json:111:      "nolora_mean": 14.051618326083583,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\da14-rescore-bgem3-plan-b-kant.json:120:      "n_nolora": 25,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:4:2026-05-17 00:20:26,468 [__main__] INFO: pilot start persona=kant tag=r8 run=0 sliced=45 multi-turn-max=6 (focal per stim avg = 1.11)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:20:2026-05-17 00:26:33,370 [__main__] INFO: pilot start persona=kant tag=r8 run=1 sliced=45 multi-turn-max=6 (focal per stim avg = 1.11)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:36:2026-05-17 00:32:42,062 [__main__] INFO: pilot start persona=kant tag=nolora run=0 sliced=45 multi-turn-max=6 (focal per stim avg = 1.11)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:37:2026-05-17 00:33:16,889 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=25/300 rate=0.72 focal/s eta=6.4 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:38:2026-05-17 00:33:40,539 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=50/300 rate=0.85 focal/s eta=4.9 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:39:2026-05-17 00:34:17,224 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=75/300 rate=0.79 focal/s eta=4.8 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:40:2026-05-17 00:34:42,463 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=100/300 rate=0.83 focal/s eta=4.0 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:41:2026-05-17 00:35:17,869 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=125/300 rate=0.80 focal/s eta=3.6 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:42:2026-05-17 00:35:41,118 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=150/300 rate=0.84 focal/s eta=3.0 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:43:2026-05-17 00:36:14,761 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=175/300 rate=0.82 focal/s eta=2.5 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:44:2026-05-17 00:36:40,136 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=200/300 rate=0.84 focal/s eta=2.0 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:45:2026-05-17 00:37:17,879 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=225/300 rate=0.82 focal/s eta=1.5 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:46:2026-05-17 00:37:43,975 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=250/300 rate=0.83 focal/s eta=1.0 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:47:2026-05-17 00:38:19,181 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=275/300 rate=0.82 focal/s eta=0.5 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:48:2026-05-17 00:38:43,005 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=300/300 rate=0.83 focal/s eta=0.0 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:49:2026-05-17 00:38:43,018 [__main__] INFO: pilot done persona=kant tag=nolora run=0 completed=300 elapsed=6.0 min output=data\eval\m9-c-adopt-plan-b-verdict\kant_planb_nolora_run0_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:52:2026-05-17 00:38:43,253 [__main__] INFO: pilot start persona=kant tag=nolora run=1 sliced=45 multi-turn-max=6 (focal per stim avg = 1.11)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:53:2026-05-17 00:39:19,349 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=25/300 rate=0.69 focal/s eta=6.6 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:54:2026-05-17 00:39:45,404 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=50/300 rate=0.80 focal/s eta=5.2 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:55:2026-05-17 00:40:21,238 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=75/300 rate=0.77 focal/s eta=4.9 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:56:2026-05-17 00:40:44,609 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=100/300 rate=0.82 focal/s eta=4.0 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:57:2026-05-17 00:41:18,540 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=125/300 rate=0.80 focal/s eta=3.6 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:58:2026-05-17 00:41:43,691 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=150/300 rate=0.83 focal/s eta=3.0 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:59:2026-05-17 00:42:17,887 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=175/300 rate=0.82 focal/s eta=2.6 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:60:2026-05-17 00:42:45,873 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=200/300 rate=0.82 focal/s eta=2.0 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:61:2026-05-17 00:43:22,209 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=225/300 rate=0.81 focal/s eta=1.5 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:62:2026-05-17 00:43:47,731 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=250/300 rate=0.82 focal/s eta=1.0 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:63:2026-05-17 00:44:23,104 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=275/300 rate=0.81 focal/s eta=0.5 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:64:2026-05-17 00:44:48,503 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=300/300 rate=0.82 focal/s eta=0.0 min
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:65:2026-05-17 00:44:48,516 [__main__] INFO: pilot done persona=kant tag=nolora run=1 completed=300 elapsed=6.1 min output=data\eval\m9-c-adopt-plan-b-verdict\kant_planb_nolora_run1_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:70:-rw-r--r-- 1 johnd 197611 1323008  5月 17 00:38 kant_planb_nolora_run0_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\eval-sequence.log:71:-rw-r--r-- 1 johnd 197611 1323008  5月 17 00:44 kant_planb_nolora_run1_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:28:2. `--nolora-shards` (kw-only `nargs="+"` Path、default `_NOLORA_SHARDS`)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:49:- CLI parsing test: `--v2-shards a.duckdb b.duckdb --nolora-shards
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:51:- backward-compat: flag 省略時 default が `_V2_SHARDS` / `_NOLORA_SHARDS`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:86:python scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:88:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:93:python scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:95:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:103:python scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:105:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:107:    --output data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:109:python scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:111:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:113:    --output data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:117:(`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:129:- multi-turn 整合性: cycle 内で multi-turn-max=6 以内に収まっているか
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:143:    --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:144:                    data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:158:    --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run{0,1}_stim.duckdb \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:163:    --v2-shards ... --nolora-shards ... \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:239:  (`--v2-shards` / `--nolora-shards` / `--kernel-type` / `--allowlist-path`)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:260:- `data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run{0,1}_stim.duckdb`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json:32:    "kant_planb_nolora_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json:33:    "kant_planb_nolora_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json:37:      "run_id": "kant_planb_nolora_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json:104:      "run_id": "kant_planb_nolora_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json:170:      "run_id": "kant_planb_nolora_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json:235:      "run_id": "kant_planb_nolora_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json:298:      "run_id": "kant_planb_nolora_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json:365:      "run_id": "kant_planb_nolora_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\pr-body-draft.md:9:  protocol (`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\pr-body-draft.md:11:  `--nolora-shards` / `--kernel-type` / `--allowlist-path` flags
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tasklist.md:21:- [x] `--nolora-shards` (kw-only `nargs="+"`) 追加
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tasklist.md:42:- [ ] LoRA-on run0: `tier_b_pilot.py --rank 8 --lora-name kant_r8v3
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tasklist.md:46:      → `kant_planb_nolora_run0_stim.duckdb`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\tasklist.md:48:      → `kant_planb_nolora_run1_stim.duckdb`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\decisions.md:38:  - **Plan B kant shards は ~equal mass** (n_v2 ≈ n_nolora) で pool-fit
.steering\20260516-m9-c-adopt-plan-b-eval-gen\decisions.md:108:  ~30 min/condition を要する。v2 baseline での kant_r8v2 ICC は 0.91 で
.steering\20260516-m9-c-adopt-plan-b-eval-gen\decisions.md:200:  - A: `tier_b_pilot.py` を改修して shard に rate を保存 (`metadata`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\decisions.md:208:  1. `tier_b_pilot.py` 改修は本 PR scope 外 (eval generation は scope
.steering\20260516-m9-c-adopt-plan-b-eval-gen\decisions.md:216:  あり (`_shard_focal_rate_from_log` は脆い文字列 split)。`tier_b_pilot.
.steering\20260516-m9-c-adopt-plan-b-eval-gen\decisions.md:220:- **見直しタイミング**: `tier_b_pilot.py` の log format が変わったとき
.steering\20260516-m9-c-adopt-plan-b-eval-gen\requirement.md:23:  control shards (`kant_planb_nolora_run{0,1}_stim.duckdb`) を生成
.steering\20260516-m9-c-adopt-plan-b-eval-gen\requirement.md:41:   - `--v2-shards` / `--nolora-shards` kw-only flag 追加 (default は
.steering\20260516-m9-c-adopt-plan-b-eval-gen\requirement.md:49:   - LoRA-on × 2 (run0, run1): `tier_b_pilot.py --rank 8 --turn-count 300
.steering\20260516-m9-c-adopt-plan-b-eval-gen\requirement.md:50:     --cycle-count 6 --multi-turn-max 6`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\requirement.md:112:- `scripts/m9-c-adopt/tier_b_pilot.py` (eval generation driver)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\requirement.md:124:  既に Option (a) `--v2-shards`/`--nolora-shards` を推奨確定)。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\validation-kant-planb-nolora.json:8:      "shard": "kant_planb_nolora_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\validation-kant-planb-nolora.json:53:      "shard": "kant_planb_nolora_run1_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:36:- `--v2-shards` / `--nolora-shards` / `--kernel-type` / `--allowlist-path`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:45:  shards are ~equal mass (n_v2 ≈ n_nolora) so this is theoretically a
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:73:- The 4 shards (`kant_r8v3_run{0,1}_stim.duckdb` + `kant_planb_nolora_run{0,1}_stim.duckdb`) use the same `tier_b_pilot.py` invocation
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:74:  parameters as the v2 baseline (`--turn-count 300 --cycle-count 6
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:75:  --multi-turn-max 6`). Confirm apples-to-apples with the v2 reference
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:76:  (`data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`).
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:82:  Confirm that the `_NO_LORA_MODEL` routing in `tier_b_pilot.py` matches
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:552:+    nolora_texts: list[str],
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:556:+    Returns ``(v2_unit, nolora_unit)`` — both unit-l2-normalized so that
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:573:+    n_nolora = len(nolora_texts)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:574:+    cleaned = [str(t) if str(t).strip() else " " for t in (v2_texts + nolora_texts)]
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:576:+        "lexical_5gram pool-fit: v2=%d nolora=%d merged=%d",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:578:+        n_nolora,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:614:         nolora_idx_list: list[int] = []
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:617:-            nolora_idx_list.extend(int(i) for i in rng.choice(nolora_by[s], size=per_quota, replace=True))
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:621:+            nolora_idx_list.extend(
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:622:+                int(i) for i in rng.choice(nolora_by[s], size=per_quota, replace=True)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:687:+            " Defaults to the Plan A v2 baseline (kant_r8v2_run{0,1}); pass"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:692:+        "--nolora-shards",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:695:+        default=list(_NOLORA_SHARDS),
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:698:+            " to the existing kant_nolora_run{0,1} SGLang baseline; pass the"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:699:+            " Plan B no-LoRA control shards (kant_planb_nolora_run{0,1}) for"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:739:     nolora_utterances: list[str] = []
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:740:     nolora_utt_per_shard: list[int] = []
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:741:-    for shard in _NOLORA_SHARDS:
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:742:+    for shard in args.nolora_shards:
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:744:         nolora_utterances.extend(ut)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:745:         nolora_utt_per_shard.append(len(ut))
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:748:         "v2 utterances=%d nolora utterances=%d",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:749:-        len(v2_utterances), len(nolora_utterances),
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:751:+        len(nolora_utterances),
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:788:-    nolora_unit = _encode_pool(args.encoder, revision, nolora_utterances)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:790:+        v2_unit, nolora_unit = _encode_pools_lexical_5gram(
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:792:+            nolora_utterances,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:796:+        nolora_unit = _encode_pool(args.encoder, revision, nolora_utterances)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:800:     nolora_window_scores = _natural_window_scores(nolora_unit, nolora_utt_per_shard)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:802:         "natural windows: v2=%d nolora=%d",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:803:-        len(v2_window_scores), len(nolora_window_scores),
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:805:+        len(nolora_window_scores),
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:809:-        v2_window_scores, nolora_window_scores,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:812:+        nolora_window_scores,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:822:-        v2_unit=v2_unit, nolora_unit=nolora_unit,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:823:-        v2_strata=v2_langs, nolora_strata=nolora_langs,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:825:+        nolora_unit=nolora_unit,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:827:+        nolora_strata=nolora_langs,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:837:-        v2_unit=v2_unit, nolora_unit=nolora_unit,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:838:-        v2_strata=v2_quartiles, nolora_strata=nolora_quartiles,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:840:+        nolora_unit=nolora_unit,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:842:+        nolora_strata=nolora_quartiles,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:855:-            v2_unit=v2_unit, nolora_unit=nolora_unit,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:856:-            v2_strata=v2_langs, nolora_strata=nolora_langs,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:858:+            nolora_unit=nolora_unit,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:860:+            nolora_strata=nolora_langs,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:935:-        "nolora_shards": [s.name for s in _NOLORA_SHARDS],
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:937:+        "nolora_shards": [s.name for s in args.nolora_shards],
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:940:             "nolora_scores": nolora_window_scores,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:956:C:\ERRE-Sand_Box\data\eval\m9-c-adopt-plan-b-verdict\kant_planb_nolora_run0_stim.duckdb 1323008
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:957:C:\ERRE-Sand_Box\data\eval\m9-c-adopt-plan-b-verdict\kant_planb_nolora_run1_stim.duckdb 1323008
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:985:C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json  11906
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:988:C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\validation-kant-planb-nolora.json              2343
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:996:data/eval/m9-c-adopt-plan-b-verdict\kant_planb_nolora_run1_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:997:data/eval/m9-c-adopt-plan-b-verdict\kant_planb_nolora_run0_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1042:.steering/20260516-m9-c-adopt-plan-b-eval-gen\tier-b-plan-b-kant-planb-nolora-burrows.json
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1049:.steering/20260516-m9-c-adopt-plan-b-eval-gen\validation-kant-planb-nolora.json
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1059:scripts/m9-c-adopt\tier_b_pilot.py
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1557:        --burrows-nolora .steering/.../tier-b-plan-b-kant-planb-nolora-burrows.json \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1561:        --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1562:                        data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1596:    given run tag (e.g. ``r8 run=0`` or ``nolora run=0``).
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1618:    nolora: list[float],
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1623:    """Bootstrap CI for reduction%: (nolora_mean - v2_mean) / nolora_mean ﾃ・100.
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1629:    b = np.asarray(nolora, dtype=float)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1651:    p.add_argument("--burrows-nolora", required=True, type=Path)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1663:    p.add_argument("--nolora-shards", nargs="+", required=True, type=Path)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1679:    nolora_payload = _load_json(args.burrows_nolora)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1681:    nolora_means = _window_means(nolora_payload)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1683:        v2_means, nolora_means, seed=args.seed, n_resamples=args.n_resamples,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1688:        "no_lora_mean": float(mean(nolora_means)) if nolora_means else None,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1689:        "no_lora_stdev": float(stdev(nolora_means)) if len(nolora_means) > 1 else None,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1694:        "n_windows_nolora": len(nolora_means),
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1736:    # no-LoRA rates come from "pilot done persona=kant tag=nolora run=N ..."
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1741:    nolora_rates = [
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1742:        _shard_focal_rate_from_log(args.eval_log, f"tag=nolora run={i}")
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1743:        for i in range(len(args.nolora_shards))
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1746:    nolora_valid = [r for r in nolora_rates if r is not None]
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1748:    nolora_rate = float(mean(nolora_valid)) if nolora_valid else float("nan")
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1749:    if nolora_rate and nolora_rate != 0 and nolora_rate == nolora_rate:
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1750:        throughput_pct = v2_rate / nolora_rate * 100.0
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1755:        "no_lora_focal_per_s": nolora_rate,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1758:        "no_lora_rates_per_shard": nolora_rates,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1836:# Runs tier_b_pilot.py for:
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1866:    if "$PYTHON" "${REPO}/scripts/m9-c-adopt/tier_b_pilot.py" "$@"; then
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1877:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1886:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1895:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1897:    --output "${OUT}/kant_planb_nolora_run0_stim.duckdb" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1903:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1905:    --output "${OUT}/kant_planb_nolora_run1_stim.duckdb" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1918:design.md` ﾂｧ1.2) extended the script with ``--v2-shards`` / ``--nolora-shards``
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2002:    """No --v2-shards/--nolora-shards flags 竊・existing Plan A defaults."""
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2013:    assert list(ns.nolora_shards) == list(rescore_module._NOLORA_SHARDS)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2030:            "--nolora-shards",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2035:    assert ns.nolora_shards == [Path("data/eval/c.duckdb")]
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2050:            "--nolora-shards",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2078:            "--nolora-shards",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2096:            "--nolora-shards",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2135:    nolora_texts = [
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2138:    v2_unit, nolora_unit = rescore_module._encode_pools_lexical_5gram(
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2140:        nolora_texts,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2143:    assert nolora_unit.shape[0] == len(nolora_texts)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2144:    assert v2_unit.shape[1] == nolora_unit.shape[1]  # shared TF-IDF vocab
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2146:    nolora_norms = np.linalg.norm(nolora_unit, axis=1)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2148:    assert np.allclose(nolora_norms, 1.0, atol=1e-9)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2169:    nolora_texts = [
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2174:        nolora_texts,
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2211:NOLORA_SHARDS_GLOB="$SHARDS/kant_planb_nolora_run*_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2239:    --shards-glob "$NOLORA_SHARDS_GLOB" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2240:    --output "$TASK/validation-kant-planb-nolora.json"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2257:        --nolora-shards "$SHARDS/kant_planb_nolora_run0_stim.duckdb" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2258:                        "$SHARDS/kant_planb_nolora_run1_stim.duckdb" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2273:    --shards-glob "$NOLORA_SHARDS_GLOB" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2275:    --output "$TASK/tier-b-plan-b-kant-planb-nolora-burrows.json"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2293:    --burrows-nolora "$TASK/tier-b-plan-b-kant-planb-nolora-burrows.json" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2296:    --nolora-shards "$SHARDS/kant_planb_nolora_run0_stim.duckdb" "$SHARDS/kant_planb_nolora_run1_stim.duckdb" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2627:2. `--nolora-shards` (kw-only `nargs="+"` Path縲‥efault `_NOLORA_SHARDS`)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2644:- CLI parsing test: `--v2-shards a.duckdb b.duckdb --nolora-shards
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2645:  c.duckdb --kernel-type lexical_5gram` 縺ｮ args 隗｣驥・- backward-compat: flag 逵∫払譎・default 縺・`_V2_SHARDS` / `_NOLORA_SHARDS`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2678:python scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2680:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2685:python scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2687:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2695:python scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2697:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2699:    --output data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2701:python scripts/m9-c-adopt/tier_b_pilot.py \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2703:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2705:    --output data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2709:(`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)縲・
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2720:- multi-turn 謨ｴ蜷域ｧ: cycle 蜀・〒 multi-turn-max=6 莉･蜀・↓蜿弱∪縺｣縺ｦ縺・ｋ縺・
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2733:    --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2734:                    data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2748:    --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run{0,1}_stim.duckdb \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2753:    --v2-shards ... --nolora-shards ... \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2824:  (`--v2-shards` / `--nolora-shards` / `--kernel-type` / `--allowlist-path`)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2845:- `data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run{0,1}_stim.duckdb`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2931:    window-fit)縲１roduction `compute_vendi` 邨檎罰縺ｮ score 縺ｨ縺ｯ謨ｰ蛟､縺・    逡ｰ縺ｪ繧句庄閭ｽ諤ｧ縺ゅｊ縲・odex review 縺ｧ MEDIUM 謖・遭縺ｮ菴吝慍縺ゅｊ縲・  - **Plan B kant shards 縺ｯ ~equal mass** (n_v2 竕・n_nolora) 縺ｧ pool-fit
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2980:- **閭梧勹**: DA-14 ICC(A,1) gate 縺ｯ **LoRA-on 縺ｮ Big-5 荳雋ｫ諤ｧ 竕･ 0.55** 繧・  隕∵ｱゅ☆繧・(kernel-independent axis)縲Ａcompute_big5_icc.py` 縺ｯ SGLang 謗ｨ隲・  ~30 min/condition 繧定ｦ√☆繧九Ｗ2 baseline 縺ｧ縺ｮ kant_r8v2 ICC 縺ｯ 0.91 縺ｧ
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3053:  - A: `tier_b_pilot.py` 繧呈隼菫ｮ縺励※ shard 縺ｫ rate 繧剃ｿ晏ｭ・(`metadata`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3060:  1. `tier_b_pilot.py` 謾ｹ菫ｮ縺ｯ譛ｬ PR scope 螟・(eval generation 縺ｯ scope
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3068:  縺ゅｊ (`_shard_focal_rate_from_log` 縺ｯ閼・＞譁・ｭ怜・ split)縲Ａtier_b_pilot.
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3070:- **隕狗峩縺励ち繧､繝溘Φ繧ｰ**: `tier_b_pilot.py` 縺ｮ log format 縺悟､峨ｏ縺｣縺溘→縺・
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3321:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "turn-count|cycle-count|multi-turn-max|kant_r8v2|nolora|tier_b_pilot" -S .steering scripts data tests' in C:\ERRE-Sand_Box
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3323:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "NO_LORA|no-lora|no_lora|adapter-name|lora-name|rank|pilot done|completed=|elapsed=|model" scripts/m9-c-adopt/tier_b_pilot.py' in C:\ERRE-Sand_Box
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3328:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files = '"'mpnet','e5large','lex5','bgem3' | ForEach-Object { \".steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-"'$($_)-plan-b-kant.json" }; foreach ($f in $files) { $j=Get-Content $f -Raw | ConvertFrom-Json; [pscustomobject]@{file=$f; encoder=$j.encoder; kernel_type=$j.kernel_type; role=$j.encoder_role; revision=$j.encoder_revision_sha; libmatch=$j.library_versions_match_d2; libs=($j.library_versions | ConvertTo-Json -Compress); natural_d=$j.standard_bootstrap.cohens_d; diff_hi=$j.standard_bootstrap.diff_hi; lang_d=$j.language_balanced_bootstrap.cohens_d; length_d=$j.length_balanced_bootstrap.cohens_d; v2=($j.v2_shards -join '"','); nolora=("'$j.nolora_shards -join '"',')} } | Format-List" in C:\ERRE-Sand_Box
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3350:462:    tag = "nolora" if no_lora else f"r{rank}"

2026-05-16T16:03:53.898687Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.4 seconds
Output:
発生場所 行:2 文字:687
+ ... 2_shards -join ','); nolora=($j.nolora_shards -join ',')} } | Format- ...
+                                                                 ~
空のパイプ要素は許可されていません。
    + CategoryInfo          : ParserError: (:) [], ParentContainsErrorRecordException
    + FullyQualifiedErrorId : EmptyPipeElement
 

 exited 1 in 396ms:
発生場所 行:2 文字:687
+ ... 2_shards -join ','); nolora=($j.nolora_shards -join ',')} } | Format- ...
+                                                                 ~
空のパイプ要素は許可されていません。
    + CategoryInfo          : ParserError: (:) [], ParentContainsErrorRecordException
    + FullyQualifiedErrorId : EmptyPipeElement
 

 succeeded in 438ms:
FILE .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-burrows-plan-b-kant.json
{
  "v2_mean": 114.71002407117312,
  "v2_stdev": 3.4035332729350425,
  "no_lora_mean": 112.5179979604629,
  "no_lora_stdev": 3.431660143908644,
  "reduction_pct": -1.9481559843256908,
  "ci_lower": -5.071678780278143,
  "ci_upper": 1.1403078782223786,
  "n_windows_v2": 6,
  "n_windows_nolora": 6,
  "threshold_pct": 5.0,
  "note": "reduction% = (no_lora_mean - v2_mean) / no_lora_mean ﾃ・100. CI via 2000-iteration window-level bootstrap. DA-14 gate: reduction_pct >= 5 AND ci_lower > 0."
}
FILE .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-icc-plan-b-kant.json
{
  "v2_point": 0.908256880733948,
  "icc_source_path": ".steering\\20260516-m9-c-adopt-plan-b-eval-gen\\tier-b-plan-b-kant-r8v3-icc.json",
  "icc_field_used": "icc_agreement_single",
  "threshold": 0.55,
  "note": "ICC(A,1) absolute-agreement Big-5 ICC. DA-14 gate: point 竕･ 0.55. Kernel-independent (computed via SGLang T=0.7 inference on focal utterances)."
}
FILE .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-throughput-plan-b-kant.json
{
  "v2_focal_per_s": 0.819672131147541,
  "no_lora_focal_per_s": 0.8265027322404372,
  "throughput_pct_of_baseline": 99.17355371900825,
  "v2_rates_per_shard": [
    0.819672131147541,
    0.819672131147541
  ],
  "no_lora_rates_per_shard": [
    0.8333333333333334,
    0.819672131147541
  ],
  "threshold_pct": 70.0,
  "note": "throughput_pct_of_baseline = v2 mean rate / no-LoRA mean rate ﾃ・100. DA-14 gate: 竕･ 70%. Rates pulled from each shard's raw_dialog.metadata['pilot_rate_focal_per_s']."
}

 succeeded in 464ms:
{
    "persona":  "kant",
    "plan":  "B",
    "verdict":  "PHASE_E_A6",
    "thresholds":  {
                       "vendi_d_le":  -0.5,
                       "burrows_pct_ge":  5.0,
                       "icc_ge":  0.55,
                       "throughput_pct_ge":  70.0,
                       "note":  "DA-14 thresholds unchanged. Plan B applies them under the encoder agreement axis (3-of-4 primary, 2+ required) + kernel-independent Burrows/ICC/throughput."
                   },
    "per_encoder":  [
                        {
                            "encoder":  "sentence-transformers/all-mpnet-base-v2",
                            "encoder_revision_sha":  "e8c3b32edf5434bc2275fc9bab85f82640a19130",
                            "encoder_role_d2":  "primary",
                            "kernel_type":  "semantic",
                            "d2_revision_match":  true,
                            "d2_library_match":  true,
                            "natural_cohens_d":  -0.5264004849343598,
                            "natural_diff_hi":  0.5179740570667519,
                            "natural_pass":  false,
                            "language_balanced_d":  -0.26532670180282614,
                            "language_balanced_pass":  false,
                            "length_balanced_d":  -0.3964164738424532,
                            "length_balanced_pass":  false,
                            "all_three_axes_pass":  false,
                            "within_language_d":  {
                                                      "de":  -0.37696738138972413,
                                                      "en":  -0.1788346870878692,
                                                      "ja":  null
                                                  }
                        },
                        {
                            "encoder":  "intfloat/multilingual-e5-large",
                            "encoder_revision_sha":  "3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3",
                            "encoder_role_d2":  "primary",
                            "kernel_type":  "semantic",
                            "d2_revision_match":  true,
                            "d2_library_match":  true,
                            "natural_cohens_d":  0.47812889123437974,
                            "natural_diff_hi":  0.09363902426551185,
                            "natural_pass":  false,
                            "language_balanced_d":  0.5310397813245353,
                            "language_balanced_pass":  false,
                            "length_balanced_d":  0.3069407935488557,
                            "length_balanced_pass":  false,
                            "all_three_axes_pass":  false,
                            "within_language_d":  {
                                                      "de":  0.755936332171652,
                                                      "en":  0.6746564192834165,
                                                      "ja":  null
                                                  }
                        },
                        {
                            "encoder":  "lexical_5gram",
                            "encoder_revision_sha":  "n/a",
                            "encoder_role_d2":  "primary",
                            "kernel_type":  "lexical_5gram",
                            "d2_revision_match":  true,
                            "d2_library_match":  true,
                            "natural_cohens_d":  0.1804817101608472,
                            "natural_diff_hi":  3.0389435092949384,
                            "natural_pass":  false,
                            "language_balanced_d":  0.31176437689821035,
                            "language_balanced_pass":  false,
                            "length_balanced_d":  0.3245984330039873,
                            "length_balanced_pass":  false,
                            "all_three_axes_pass":  false,
                            "within_language_d":  {
                                                      "de":  0.2323172167666138,
                                                      "en":  0.41576626646891585,
                                                      "ja":  null
                                                  }
                        },
                        {
                            "encoder":  "BAAI/bge-m3",
                            "encoder_revision_sha":  "5617a9f61b028005a4858fdac845db406aefb181",
                            "encoder_role_d2":  "exploratory",
                            "kernel_type":  "semantic",
                            "d2_revision_match":  true,
                            "d2_library_match":  true,
                            "natural_cohens_d":  0.3317428988243919,
                            "natural_diff_hi":  0.5585934689306988,
                            "natural_pass":  false,
                            "language_balanced_d":  0.22562010862377416,
                            "language_balanced_pass":  false,
                            "length_balanced_d":  0.19907770666220162,
                            "length_balanced_pass":  false,
                            "all_three_axes_pass":  false,
                            "within_language_d":  {
                                                      "de":  0.28594491448337117,
                                                      "en":  0.32015451139651424,
                                                      "ja":  null
                                                  }
                        }
                    ],
    "axes":  {
                 "encoder_agreement":  {
                                           "primary_count_total":  3,
                                           "primary_count_passed_all_axes":  0,
                                           "primary_count_required":  2,
                                           "direction_all_negative":  false,
                                           "axis_pass":  false,
                                           "primary_encoders_passing":  [

                                                                        ],
                                           "exploratory_encoders_reported":  [
                                                                                 "BAAI/bge-m3"
                                                                             ]
                                       },
                 "burrows":  {
                                 "reduction_pct":  -1.9481559843256908,
                                 "ci_lower":  -5.071678780278143,
                                 "ci_upper":  1.1403078782223786,
                                 "gate_pct":  5.0,
                                 "axis_pass":  false
                             },
                 "icc":  {
                             "icc_point":  0.908256880733948,
                             "gate":  0.55,
                             "axis_pass":  true
                         },
                 "throughput":  {
                                    "throughput_pct_of_baseline":  99.17355371900825,
                                    "gate_pct":  70.0,
                                    "axis_pass":  true
                                }
             },
    "preregistration_anchor":  ".steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json (D-2 Plan B allowlist) + DA-14 thresholds unchanged. Encoder agreement axis from ``encoder_agreement_axis`` block of the allowlist."
}

hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content .steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md -TotalCount 80' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Item .steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md | Format-List FullName,Length,Attributes,LinkType,Target,LastWriteTime' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files = @('"'mpnet','e5large','lex5','bgem3') | ForEach-Object { \".steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-"'$($_)-plan-b-kant.json" }; foreach ($f in $files) { $j=Get-Content $f -Raw | ConvertFrom-Json; Write-Output "FILE=$f"; Write-Output "encoder=$($j.encoder) kernel=$($j.kernel_type) role=$($j.encoder_role) revision=$($j.encoder_revision_sha) libmatch=$($j.library_versions_match_d2)"; Write-Output "libs=$(($j.library_versions | ConvertTo-Json -Compress))"; Write-Output "natural_d=$($j.standard_bootstrap.cohens_d) diff_hi=$($j.standard_bootstrap.diff_hi) lang_d=$($j.language_balanced_bootstrap.cohens_d) length_d=$($j.length_balanced_bootstrap.cohens_d)"; Write-Output "v2=$($j.v2_shards -join '"',')\"; Write-Output \"nolora="'$($j.nolora_shards -join '"',')\"; Write-Output '' }" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '(Get-Content .steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md | Measure-Object -Line).Lines' in C:\ERRE-Sand_Box
 succeeded in 388ms:


FullName      : C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md
Length        : 360633
Attributes    : Archive
LinkType      : 
Target        : {}
LastWriteTime : 2026/05/17 1:04:11




 succeeded in 398ms:
Reading prompt from stdin...
OpenAI Codex v0.128.0 (research preview)
--------
workdir: C:\ERRE-Sand_Box
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, C:\Users\johnd\.codex\memories]
reasoning effort: xhigh
reasoning summaries: none
session id: 019e3186-7034-7591-82af-9d18a236aa6e
--------
user
# Codex independent review 窶・m9-c-adopt Plan B verdict (eval-gen PR)

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
  flags. Verify backward-compatibility (no flags 竊・Plan A defaults
  unchanged), and that the `_resolve_encoder_default` helper correctly
  cross-validates `kernel_type=lexical_5gram` against the encoder
  argument.
- `_encode_pools_lexical_5gram` pool-fit semantics (DE-1 in design.md).
  Concern: pool-fit IDF means the IDF basis depends on BOTH conditions'
  utterances. Could a future PR introduce a Simpson's-style artefact if
  one condition disproportionately drives the vocabulary? Plan B kant
  shards are ~equal mass (n_v2 竕・n_nolora) so this is theoretically a
  non-issue, but is the rationale durable enough to keep across
  nietzsche / rikyu (which may have asymmetric shards)?
- `library_versions_match_d2`: the new overlap-only check means
  `lexical_5gram` runs skip the `sentence_transformers` pin (it isn't
  loaded). Is this an acceptable downgrade of the D-2 enforcement
  contract, or does it leak audit guarantees?

### 2. `da14_verdict_plan_b.py` aggregator

- `_encoder_agreement_axis` 窶・encoder agreement axis logic. 3-of-4
  primary, 2+ required, plus "all primary natural d share negative sign"
  direction discipline (BGE-M3 sign-flip generalisation). Edge case: if
  a primary has `natural_cohens_d=None` (e.g. degenerate window),
  `natural_ds` list excludes it but `all_negative` still passes on the
  remaining encoders 窶・is that the intended semantic? Should `None`
  treated as a direction failure?
- `_aggregate_verdict` 窶・ADOPT requires *all four* axes (encoder
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
- SGLang launch (`launch_sglang_plan_b.sh`): K-ﾎｱ v5 invocation +
  `--lora-paths kant_r8v3=...checkpoint-1500 --max-loras-per-batch 1
  --max-lora-rank 8`. Cross-check against DR-4 in
  `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md`.

 succeeded in 402ms:
FILE=.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-mpnet-plan-b-kant.json
encoder=sentence-transformers/all-mpnet-base-v2 kernel=semantic role=primary revision=e8c3b32edf5434bc2275fc9bab85f82640a19130 libmatch=True
libs={"transformers":"4.57.6","sentence_transformers":"3.4.1"}
natural_d=-0.5264004849343598 diff_hi=0.5179740570667519 lang_d=-0.26532670180282614 length_d=-0.3964164738424532
v2=kant_r8v3_run0_stim.duckdb,kant_r8v3_run1_stim.duckdb
nolora=kant_planb_nolora_run0_stim.duckdb,kant_planb_nolora_run1_stim.duckdb

FILE=.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-e5large-plan-b-kant.json
encoder=intfloat/multilingual-e5-large kernel=semantic role=primary revision=3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3 libmatch=True
libs={"transformers":"4.57.6","sentence_transformers":"3.4.1"}
natural_d=0.47812889123437974 diff_hi=0.09363902426551185 lang_d=0.5310397813245353 length_d=0.3069407935488557
v2=kant_r8v3_run0_stim.duckdb,kant_r8v3_run1_stim.duckdb
nolora=kant_planb_nolora_run0_stim.duckdb,kant_planb_nolora_run1_stim.duckdb

FILE=.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-lex5-plan-b-kant.json
encoder=lexical_5gram kernel=lexical_5gram role=primary revision=n/a libmatch=True
libs={"transformers":"4.57.6","sklearn":"1.8.0"}
natural_d=0.1804817101608472 diff_hi=3.0389435092949384 lang_d=0.31176437689821035 length_d=0.3245984330039873
v2=kant_r8v3_run0_stim.duckdb,kant_r8v3_run1_stim.duckdb
nolora=kant_planb_nolora_run0_stim.duckdb,kant_planb_nolora_run1_stim.duckdb

FILE=.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-bgem3-plan-b-kant.json
encoder=BAAI/bge-m3 kernel=semantic role=exploratory revision=5617a9f61b028005a4858fdac845db406aefb181 libmatch=True
libs={"transformers":"4.57.6","sentence_transformers":"3.4.1"}
natural_d=0.3317428988243919 diff_hi=0.5585934689306988 lang_d=0.22562010862377416 length_d=0.19907770666220162
v2=kant_r8v3_run0_stim.duckdb,kant_r8v3_run1_stim.duckdb
nolora=kant_planb_nolora_run0_stim.duckdb,kant_planb_nolora_run1_stim.duckdb


 succeeded in 416ms:
4302

hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "# Codex review|## HIGH|HIGH-|MEDIUM-|LOW-|OUT-OF-SCOPE|Final|Findings|PHASE_E" .steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content .steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md -Tail 180' in C:\ERRE-Sand_Box
 succeeded in 341ms:
86:### 4. ADOPT / Phase E A-6 verdict justification (RESOLVED: PHASE_E_A6)
89:`da14-verdict-plan-b-kant.md`) reached **PHASE_E_A6** (REJECT, rank=16
111:- Is the verdict logic correctly routing to PHASE_E_A6 given 2 axes
113:  PHASE_E_A6)
136:# Codex review — Plan B eval-gen PR
138:## HIGH
139:- [HIGH-1] ...
140:- [HIGH-2] ...
143:- [MEDIUM-1] ...
146:- [LOW-1] ...
148:## OUT-OF-SCOPE / NICE-TO-HAVE
500:     """Load the D-2 pre-registration allowlist (Codex HIGH-1 enforcement).
754:     # === D-2 allowlist enforcement (Codex HIGH-1) ===
1326:    """ADOPT if all four axes PASS, else PHASE_E_A6 (rank=16 spike)."""
1334:    return "PHASE_E_A6"
2349:  "preregistration_note": "Plan B verdict 逕ｨ D-2 allowlist (HIGH-2 enforcement 邯呎価)縲１lan A 3 encoder 縺ｫ lexical-5gram 繧定ｿｽ蜉縺励‘ncoder agreement axis 繧・4-encoder 荳翫〒蛻､螳壹☆繧九・PNet 縺ｯ Plan A 縺ｧ縺ｮ per-encoder within-language d 邨先棡 (d_de=-0.72 譛蠑ｷ讀懷・蝎ｨ) 繧定ｸ上∪縺・primary 蠕ｩ蟶ｰ縲。GE-M3 縺ｯ Plan A natural d sign flip (+0.23) 繧定ｸ上∪縺・exploratory 譬ｼ荳九￡ (蝣ｱ蜻・obligatory 縺縺・ADOPT 蟇・ｸ惹ｸ榊庄)縲１lan B ADOPT 縺ｯ 3 primary encoder 縺ｮ縺・■ 2 莉･荳翫〒 natural d <= -0.5 + CI upper < 0 + lang-balanced d <= -0.5 + length-balanced d <= -0.5 繧呈ｺ縺溘☆縺薙→縲√°縺､隨ｦ蜿ｷ荳閾ｴ (3 縺ｨ繧・negative) 繧・pre-condition 縺ｨ縺吶ｋ縲Ｍexical-5gram 縺ｯ retrieval-trained 縺ｧ縺ｪ縺・independent kernel 縺ｨ縺励※ encoder diversity 繧堤｢ｺ菫昴☆繧九ょｮ溯｣・module path 縺ｯ譛ｬ PR 縺ｧ pre-register 縺ｮ縺ｿ縲∝ｮ溯｣・悽菴薙・谺｡繧ｻ繝・す繝ｧ繝ｳ (retrain prep) 縺ｧ `erre_sandbox.evidence.tier_b.vendi_lexical_5gram` 縺ｫ霑ｽ蜉縺吶ｋ縲・,
2419:    髦ｲ豁｢縺ｮ縺溘ａ de+en 竕･ 0.60 縺ｨ de 竕･ 0.30 縺ｮ **2 axis 縺ｫ蛻・屬**縲・    Codex MEDIUM-1 驕募渚縺ｧ縺ｯ縺ｪ縺・(DI-5 謨ｰ蛟､繧・retroactive 遘ｻ蜍輔○縺壹・    譁ｰ隕・axis 繧・Plan B 縺ｧ襍ｷ縺薙☆)
2455:     content-independent style channel" 莉ｮ隱ｬ縺ｨ謨ｴ蜷・(Codex HIGH-2 蜿肴丐)
2472:  3. Codex MEDIUM-1 驕募渚縺ｧ縺ｯ縺ｪ縺・ DI-5 縺ｮ de+en 謨ｰ蛟､ (0.489) 繧・     retroactive 遘ｻ蜍輔☆繧九・縺ｧ縺ｯ縺ｪ縺上・*譁ｰ隕・axis 繧・Plan B 縺ｧ襍ｷ縺薙☆**縲・     "Plan B 襍ｷ蜍募ｾ後・ corpus shape expectation 繧・hard gate 縺ｫ縺吶ｋ"
2473:     縺薙→縺ｯ MEDIUM-1 縺檎ｦ√§繧・"retroactive trigger promotion" 縺ｨ
2535:  - **HIGH-1**: Plan B retrain command 縺・executable 縺ｧ縺ｪ縺・・    `train_kant_lora.py` 縺ｮ CLI 縺ｯ `--plan-b-gate` / `--lang-stratified-split`
2538:  - **HIGH-2**: `audit_plan_b_corpus_stats.py` 縺ｮ CLI 縺・`--n-eff-min` 遲・    threshold override flag 繧帝愆蜃ｺ縲Ｑreregistered hard gate 縺碁°逕ｨ荳翫・
2539:    flag 縺ｧ蜍輔°縺帙ｋ縺ｮ縺ｯ HIGH-3 discipline (threshold motion 遖∵ｭ｢) 縺ｫ驕募渚
2540:  - **MEDIUM-1**: 謗｡蜿・manifest 縺・documented but not emitted縲Ｓunbook ﾂｧ7 縺ｧ
2541:    manifest schema 繧貞ｮ夂ｾｩ貂医□縺後…ollector 縺ｫ譖ｸ縺榊・縺励さ繝ｼ繝峨′縺ｪ縺・  - **MEDIUM-2**: "no addressee" 縺・metadata only 縺ｧ output-filtered 縺ｧ縺ｪ縺・・    `filter_de_monolog` 縺ｯ language / length / marker / trigram 縺ｮ縺ｿ蠑ｷ蛻ｶ縲・    "du / Sie / Ihre / Frage" 縺ｪ縺ｩ縺ｮ addressee marker 縺・accepted text 縺ｫ
2544:  - **LOW-1**: `--dry-run` 縺ｮ resume contract 驕募渚縲・LI help 縺ｨ runbook 縺ｯ
2548:  1. **HIGH-1**:
2567:  2. **HIGH-2**:
2573:  3. **MEDIUM-1**: `de_focused_monolog_collector._write_manifest` 繧呈眠隕剰ｿｽ蜉縲・     collection 螳御ｺ・凾縺ｫ蠢・★ `<shard>_manifest.json` 繧・emit縲Ｔchema 縺ｯ
2577:  4. **MEDIUM-2**: `filter_de_monolog` 縺ｫ **5 霆ｸ逶ｮ** "addressee" 繧定ｿｽ蜉縲・     informal 2nd-person (du / dich / dir / dein- / euch / euer / fragst)
2584:  5. **LOW-1**: `run_collection` 縺ｧ `args.dry_run=True` 譎ゅ・
2790:def aggregate_verdict(...) -> Literal["ADOPT", "PHASE_E_A6"]:
2791:    """蜈ｨ axis pass 竊・ADOPT縲・ axis 縺ｧ繧・fail 竊・PHASE_E_A6."""
3000:## DR-1: kant Plan B verdict = **PHASE_E_A6** (REJECT) 竊・DA-16 ADR (rank=16 spike) 襍ｷ逾ｨ蛟呵｣・
3189:     causal_lm_loss` 縺ｯ Codex HIGH-C verbatim縲∝・蜉・tensors 縺ｯ蜷後§)
3303:    HIGH-C verbatim 謨ｰ蠑上・ batch>=2 繧呈囓鮟吝燕謠舌＠縺ｦ縺・◆縺後〃RAM 蛻ｶ邏・〒
3336:26:* ``--no-lora-control`` (HIGH-1) routes to the SGLang base model
3342:97:_NO_LORA_MODEL: Final = "Qwen/Qwen3-8B"
3610:.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6323:scripts/m9-c-adopt/tier_b_pilot.py:87:_DEFAULT_STIMULUS_DIR: Final = _REPO_ROOT / "golden" / "stimulus"
3612:.steering\20260517-m9-c-adopt-plan-b-design\codex-review.stderr:6325:scripts/m9-c-adopt/tier_b_pilot.py:126:_INTERLOCUTOR_ID: Final = "_stimulus"
3814:.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1456:- **LOW-2** (`--multi-turn-max 6`): 謗｡逕ｨ ADOPT-WITH-NOTE縲Ｅesign.md 縺ｫ
3925:.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:126:- **LOW-2** (`--multi-turn-max 6`): 採用 ADOPT-WITH-NOTE。design.md に
3941:.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:109:- **no-LoRA control 2 shard** (HIGH-1): `kant_nolora_run{0,1}_stim.duckdb`
4031:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5882:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
4039:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6153:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
4047:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6422: 243: ### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
4055:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6688:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
4063:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6969:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
4071:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7248:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
4079:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7538:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
4106:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:212:### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
4164:.steering\20260516-m9-c-adopt-da15-impl\codex-review.md:3:- Why it matters: HIGH-3 requires DA-14 thresholds to remain unchanged. In DA-14, `.steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json:8-15` records `diff_v2_minus_nolora`, `diff_ci_95`, and `cohens_d` separately, with `threshold_ci = "ci_upper < 0"`. DA-15's `_bootstrap_window_d_ci()` instead appends `_cohens_d(ra, rb)` and returns `lo` / `hi` over that d distribution (`scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:142-163`), while `da15_verdict.py:73-90` treats `standard_bootstrap["hi"]` as the natural diff upper bound. This changes the statistical gate, even though the artifact says `diff_ci_upper_lt` (`.steering/20260516-m9-c-adopt-da15-impl/da15-rescore-e5-large-kant.json:44-48`).
4568:    "verdict":  "PHASE_E_A6",
4846:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "# Codex review|## HIGH|HIGH-|MEDIUM-|LOW-|OUT-OF-SCOPE|Final|Findings|PHASE_E" .steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md' in C:\ERRE-Sand_Box

 succeeded in 357ms:
                                           "primary_encoders_passing":  [

                                                                        ],
                                           "exploratory_encoders_reported":  [
                                                                                 "BAAI/bge-m3"
                                                                             ]
                                       },
                 "burrows":  {
                                 "reduction_pct":  -1.9481559843256908,
                                 "ci_lower":  -5.071678780278143,
                                 "ci_upper":  1.1403078782223786,
                                 "gate_pct":  5.0,
                                 "axis_pass":  false
                             },
                 "icc":  {
                             "icc_point":  0.908256880733948,
                             "gate":  0.55,
                             "axis_pass":  true
                         },
                 "throughput":  {
                                    "throughput_pct_of_baseline":  99.17355371900825,
                                    "gate_pct":  70.0,
                                    "axis_pass":  true
                                }
             },
    "preregistration_anchor":  ".steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json (D-2 Plan B allowlist) + DA-14 thresholds unchanged. Encoder agreement axis from ``encoder_agreement_axis`` block of the allowlist."
}

hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content .steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md -TotalCount 80' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Item .steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md | Format-List FullName,Length,Attributes,LinkType,Target,LastWriteTime' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files = @('"'mpnet','e5large','lex5','bgem3') | ForEach-Object { \".steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-"'$($_)-plan-b-kant.json" }; foreach ($f in $files) { $j=Get-Content $f -Raw | ConvertFrom-Json; Write-Output "FILE=$f"; Write-Output "encoder=$($j.encoder) kernel=$($j.kernel_type) role=$($j.encoder_role) revision=$($j.encoder_revision_sha) libmatch=$($j.library_versions_match_d2)"; Write-Output "libs=$(($j.library_versions | ConvertTo-Json -Compress))"; Write-Output "natural_d=$($j.standard_bootstrap.cohens_d) diff_hi=$($j.standard_bootstrap.diff_hi) lang_d=$($j.language_balanced_bootstrap.cohens_d) length_d=$($j.length_balanced_bootstrap.cohens_d)"; Write-Output "v2=$($j.v2_shards -join '"',')\"; Write-Output \"nolora="'$($j.nolora_shards -join '"',')\"; Write-Output '' }" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '(Get-Content .steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md | Measure-Object -Line).Lines' in C:\ERRE-Sand_Box
 succeeded in 388ms:


FullName      : C:\ERRE-Sand_Box\.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md
Length        : 360633
Attributes    : Archive
LinkType      : 
Target        : {}
LastWriteTime : 2026/05/17 1:04:11




 succeeded in 398ms:
Reading prompt from stdin...
OpenAI Codex v0.128.0 (research preview)
--------
workdir: C:\ERRE-Sand_Box
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, C:\Users\johnd\.codex\memories]
reasoning effort: xhigh
reasoning summaries: none
session id: 019e3186-7034-7591-82af-9d18a236aa6e
--------
user
# Codex independent review 遯ｶ繝ｻm9-c-adopt Plan B verdict (eval-gen PR)

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
  flags. Verify backward-compatibility (no flags 遶翫・Plan A defaults
  unchanged), and that the `_resolve_encoder_default` helper correctly
  cross-validates `kernel_type=lexical_5gram` against the encoder
  argument.
- `_encode_pools_lexical_5gram` pool-fit semantics (DE-1 in design.md).
  Concern: pool-fit IDF means the IDF basis depends on BOTH conditions'
  utterances. Could a future PR introduce a Simpson's-style artefact if
  one condition disproportionately drives the vocabulary? Plan B kant
  shards are ~equal mass (n_v2 遶輔・n_nolora) so this is theoretically a
  non-issue, but is the rationale durable enough to keep across
  nietzsche / rikyu (which may have asymmetric shards)?
- `library_versions_match_d2`: the new overlap-only check means
  `lexical_5gram` runs skip the `sentence_transformers` pin (it isn't
  loaded). Is this an acceptable downgrade of the D-2 enforcement
  contract, or does it leak audit guarantees?

### 2. `da14_verdict_plan_b.py` aggregator

- `_encoder_agreement_axis` 遯ｶ繝ｻencoder agreement axis logic. 3-of-4
  primary, 2+ required, plus "all primary natural d share negative sign"
  direction discipline (BGE-M3 sign-flip generalisation). Edge case: if
  a primary has `natural_cohens_d=None` (e.g. degenerate window),
  `natural_ds` list excludes it but `all_negative` still passes on the
  remaining encoders 遯ｶ繝ｻis that the intended semantic? Should `None`
  treated as a direction failure?
- `_aggregate_verdict` 遯ｶ繝ｻADOPT requires *all four* axes (encoder
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
- SGLang launch (`launch_sglang_plan_b.sh`): K-・趣ｽｱ v5 invocation +
  `--lora-paths kant_r8v3=...checkpoint-1500 --max-loras-per-batch 1
  --max-lora-rank 8`. Cross-check against DR-4 in
  `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md`.

 succeeded in 402ms:
FILE=.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-mpnet-plan-b-kant.json
encoder=sentence-transformers/all-mpnet-base-v2 kernel=semantic role=primary revision=e8c3b32edf5434bc2275fc9bab85f82640a19130 libmatch=True
libs={"transformers":"4.57.6","sentence_transformers":"3.4.1"}
natural_d=-0.5264004849343598 diff_hi=0.5179740570667519 lang_d=-0.26532670180282614 length_d=-0.3964164738424532
v2=kant_r8v3_run0_stim.duckdb,kant_r8v3_run1_stim.duckdb
nolora=kant_planb_nolora_run0_stim.duckdb,kant_planb_nolora_run1_stim.duckdb

FILE=.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-e5large-plan-b-kant.json
encoder=intfloat/multilingual-e5-large kernel=semantic role=primary revision=3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3 libmatch=True
libs={"transformers":"4.57.6","sentence_transformers":"3.4.1"}
natural_d=0.47812889123437974 diff_hi=0.09363902426551185 lang_d=0.5310397813245353 length_d=0.3069407935488557
v2=kant_r8v3_run0_stim.duckdb,kant_r8v3_run1_stim.duckdb
nolora=kant_planb_nolora_run0_stim.duckdb,kant_planb_nolora_run1_stim.duckdb

FILE=.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-lex5-plan-b-kant.json
encoder=lexical_5gram kernel=lexical_5gram role=primary revision=n/a libmatch=True
libs={"transformers":"4.57.6","sklearn":"1.8.0"}
natural_d=0.1804817101608472 diff_hi=3.0389435092949384 lang_d=0.31176437689821035 length_d=0.3245984330039873
v2=kant_r8v3_run0_stim.duckdb,kant_r8v3_run1_stim.duckdb
nolora=kant_planb_nolora_run0_stim.duckdb,kant_planb_nolora_run1_stim.duckdb

FILE=.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-bgem3-plan-b-kant.json
encoder=BAAI/bge-m3 kernel=semantic role=exploratory revision=5617a9f61b028005a4858fdac845db406aefb181 libmatch=True
libs={"transformers":"4.57.6","sentence_transformers":"3.4.1"}
natural_d=0.3317428988243919 diff_hi=0.5585934689306988 lang_d=0.22562010862377416 length_d=0.19907770666220162
v2=kant_r8v3_run0_stim.duckdb,kant_r8v3_run1_stim.duckdb
nolora=kant_planb_nolora_run0_stim.duckdb,kant_planb_nolora_run1_stim.duckdb


 succeeded in 416ms:
4302

hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "# Codex review|## HIGH|HIGH-|MEDIUM-|LOW-|OUT-OF-SCOPE|Final|Findings|PHASE_E" .steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content .steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md -Tail 180' in C:\ERRE-Sand_Box

hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "sglang.launch_server|--model-path|--model Qwen|--lora-paths|--max-loras-per-batch|--max-lora-rank" scripts/m9-c-spike scripts/m9-c-adopt .steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md .steering/20260516-m9-c-adopt-plan-b-eval-gen/design.md' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "model-path|--model " .venv/Lib/site-packages/sglang -g "*.py"' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw scripts/m9-c-spike/launch_sglang.sh' in C:\ERRE-Sand_Box
 succeeded in 284ms:
.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md:69:  `python -m sglang.launch_server --model-path Qwen/Qwen3-8B --host 0.0.0.0
.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md:84:  PYTHONUTF8=1 python -m sglang.launch_server \
.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md:85:      --model-path Qwen/Qwen3-8B \
.steering/20260516-m9-c-adopt-plan-b-eval-gen/design.md:62:PYTHONUTF8=1 python -m sglang.launch_server \
.steering/20260516-m9-c-adopt-plan-b-eval-gen/design.md:63:    --model-path Qwen/Qwen3-8B \
.steering/20260516-m9-c-adopt-plan-b-eval-gen/design.md:71:    --lora-paths kant_r8v3=/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500 \
.steering/20260516-m9-c-adopt-plan-b-eval-gen/design.md:72:    --max-loras-per-batch 1 \
.steering/20260516-m9-c-adopt-plan-b-eval-gen/design.md:73:    --max-lora-rank 8
scripts/m9-c-spike\launch_sglang.sh:21:exec python -m sglang.launch_server \
scripts/m9-c-spike\launch_sglang.sh:22:    --model Qwen/Qwen3-8B \
scripts/m9-c-spike\launch_sglang.sh:24:    --max-loras-per-batch 3 \
scripts/m9-c-spike\launch_sglang.sh:25:    --max-lora-rank 8 \
scripts/m9-c-adopt\bench_per_rank.sh:3:# (CS-1 launch v6: --max-lora-rank 16, --max-loras-per-batch 3 --max-loaded-loras 3,
scripts/m9-c-adopt\launch_sglang_plan_b.sh:13:#   pkill -f 'sglang.launch_server.*kant_r8v3'
scripts/m9-c-adopt\launch_sglang_plan_b.sh:31:exec python -m sglang.launch_server \
scripts/m9-c-adopt\launch_sglang_plan_b.sh:32:    --model Qwen/Qwen3-8B \
scripts/m9-c-adopt\launch_sglang_plan_b.sh:34:    --max-loras-per-batch 1 \
scripts/m9-c-adopt\launch_sglang_plan_b.sh:35:    --max-lora-rank 8 \
scripts/m9-c-adopt\launch_sglang_plan_b.sh:38:    --lora-paths "kant_r8v3=/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500" \
scripts/m9-c-adopt\tier_b_pilot.py:344:    ``--max-loras-per-batch >= rank_count`` and POST ``/load_lora_adapter`` for

2026-05-16T16:05:10.656898Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.3 seconds
Output:
rg: .venv/Lib/site-packages/sglang: IO error for operation on .venv/Lib/site-packages/sglang: 指定されたファイルが見つかりません。 (os error 2)

 exited 1 in 268ms:
rg: .venv/Lib/site-packages/sglang: IO error for operation on .venv/Lib/site-packages/sglang: 指定されたファイルが見つかりません。 (os error 2)

 succeeded in 290ms:
#!/usr/bin/env bash
# m9-c-spike Phase K-ﾎｲ SGLang launch (CS-1 launch v5).
#
# Usage from WSL2:
#   bash /mnt/c/ERRE-Sand_Box/scripts/m9-c-spike/launch_sglang.sh 2>&1 | tee /mnt/c/ERRE-Sand_Box/.steering/20260508-m9-c-spike/k-beta-logs/sglang.log
set -euo pipefail

cd /root/erre-sandbox
source .venv/bin/activate

export HF_HOME=/root/.cache/huggingface
export HF_HUB_DISABLE_TELEMETRY=1
export CUDA_HOME=/usr/local/cuda
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"

echo "[launch_sglang] HF_HOME=${HF_HOME}"
echo "[launch_sglang] python=$(which python)"
echo "[launch_sglang] starting at $(date -Iseconds)"

exec python -m sglang.launch_server \
    --model Qwen/Qwen3-8B \
    --enable-lora \
    --max-loras-per-batch 3 \
    --max-lora-rank 8 \
    --lora-target-modules q_proj k_proj v_proj o_proj \
    --max-loaded-loras 3 \
    --quantization fp8 \
    --mem-fraction-static 0.85 \
    --max-total-tokens 2048 \
    --max-running-requests 1 \
    --disable-cuda-graph \
    --port 30000 \
    --host 127.0.0.1


codex
Two concrete issues are emerging in the verdict path: the post-eval shell pipeline can continue after a failed step, and the verdict aggregator records D-2 revision/library matches without using them as eligibility gates. I’m checking the local CI script now so I can distinguish code-review findings from environment failures.
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw scripts/dev/pre-push-check.sh' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw scripts/dev/pre-push-check.ps1' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw .steering/20260516-m9-c-adopt-plan-b-eval-gen/validation-kant-r8v3.json; Get-Content -Raw .steering/20260516-m9-c-adopt-plan-b-eval-gen/validation-kant-planb-nolora.json' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content .steering/20260516-m9-c-adopt-plan-b-eval-gen/eval-sequence.log -Tail 80' in C:\ERRE-Sand_Box
 succeeded in 337ms:
#!/usr/bin/env bash
# Pre-push CI parity check (bash, WSL2 / macOS / Linux)
#
# 菴ｿ縺・婿:
#   bash scripts/dev/pre-push-check.sh
#
# CI (.github/workflows/ci.yml) 縺ｨ蜷後§ 4 谿ｵ髫弱ｒ local 縺ｧ螳溯｡後☆繧九・# 1 谿ｵ縺ｧ繧・fail 縺ｪ繧・exit 髱槭ぞ繝ｭ縲Ｑush / `gh pr create` 縺ｮ蜑阪↓蠢・★螳溯｡後☆繧九・#
# Memory: feedback_pre_push_ci_parity.md (PR #181 reflection 縺ｧ襍ｷ逾ｨ)

set -uo pipefail

NO_FORMAT=${NO_FORMAT:-0}
NO_LINT=${NO_LINT:-0}
NO_MYPY=${NO_MYPY:-0}
NO_PYTEST=${NO_PYTEST:-0}

FAILED=0
STARTED=$(date +%s)

PYTHON=".venv/Scripts/python.exe"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON=".venv/bin/python"
fi
if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: Python venv not found. Run 'uv sync --extra eval' first." >&2
    exit 2
fi

step() {
    local label="$1"; shift
    echo ""
    echo "==[ $label ]=="
    local step_start
    step_start=$(date +%s)
    if "$@"; then
        printf "  [PASS] %s (%ss)\n" "$label" "$(( $(date +%s) - step_start ))"
    else
        local code=$?
        printf "  [FAIL] %s (exit=%s, %ss)\n" "$label" "$code" "$(( $(date +%s) - step_start ))"
        FAILED=$((FAILED + 1))
    fi
}

[[ "$NO_FORMAT" == "0" ]] && step "ruff format --check" "$PYTHON" -m ruff format --check src tests
[[ "$NO_LINT" == "0" ]]   && step "ruff check"          "$PYTHON" -m ruff check src tests
[[ "$NO_MYPY" == "0" ]]   && step "mypy src"            "$PYTHON" -m mypy src
[[ "$NO_PYTEST" == "0" ]] && step "pytest -q (non-godot)" "$PYTHON" -m pytest -q --ignore=tests/test_godot

TOTAL_DUR=$(( $(date +%s) - STARTED ))
echo ""
if [[ "$FAILED" -eq 0 ]]; then
    echo "==[ ALL CHECKS PASSED (${TOTAL_DUR}s total) ]=="
    echo "Safe to push / gh pr create."
    exit 0
else
    echo "==[ ${FAILED} CHECK(S) FAILED (${TOTAL_DUR}s total) ]=="
    echo "DO NOT push. Fix the failures above and re-run."
    exit 1
fi


 succeeded in 328ms:
# Pre-push CI parity check (PowerShell, G-GEAR Windows native venv)
#
# 菴ｿ縺・婿:
#   .\scripts\dev\pre-push-check.ps1
#
# CI (.github/workflows/ci.yml) 縺ｨ蜷後§ 4 谿ｵ髫弱ｒ local 縺ｧ螳溯｡後☆繧九・# 1 谿ｵ縺ｧ繧・fail 縺ｪ繧・exit 髱槭ぞ繝ｭ縲Ｑush / `gh pr create` 縺ｮ蜑阪↓蠢・★螳溯｡後☆繧九・#
# Memory: feedback_pre_push_ci_parity.md (PR #181 reflection 縺ｧ襍ｷ逾ｨ)
# 萓句､也噪縺ｫ skip 縺励◆縺・ｴ蜷医・譏守､ｺ逧・↑ `-SkipPytest` 遲峨・ flag 繧堤畑諢上☆繧九°縲・# 隧ｲ蠖・commit 縺ｫ縲詣hy CI fix is acceptable縲阪ｒ justification 縺ｨ縺励※險倬鹸縺吶ｋ縲・
[CmdletBinding()]
param(
    [switch]$NoFormat,
    [switch]$NoLint,
    [switch]$NoMypy,
    [switch]$NoPytest
)

$ErrorActionPreference = 'Continue'
$Script:Failed = 0
$Script:Started = Get-Date

function Step {
    param([string]$Label, [scriptblock]$Body)
    Write-Host ""
    Write-Host "==[ $Label ]==" -ForegroundColor Cyan
    $stepStart = Get-Date
    & $Body
    $exit = $LASTEXITCODE
    $dur = ((Get-Date) - $stepStart).TotalSeconds
    if ($exit -eq 0) {
        Write-Host ("  [PASS] {0} ({1:N1}s)" -f $Label, $dur) -ForegroundColor Green
    } else {
        Write-Host ("  [FAIL] {0} (exit={1}, {2:N1}s)" -f $Label, $exit, $dur) -ForegroundColor Red
        $Script:Failed += 1
    }
}

$Python = ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "ERROR: $Python not found. Run 'uv sync --extra eval' first." -ForegroundColor Red
    exit 2
}

if (-not $NoFormat) {
    Step "ruff format --check src tests" { & $Python -m ruff format --check src tests }
}

if (-not $NoLint) {
    Step "ruff check src tests" { & $Python -m ruff check src tests }
}

if (-not $NoMypy) {
    Step "mypy src" { & $Python -m mypy src }
}

if (-not $NoPytest) {
    Step "pytest -q (non-godot)" { & $Python -m pytest -q --ignore=tests/test_godot }
}

$totalDur = ((Get-Date) - $Script:Started).TotalSeconds
Write-Host ""
if ($Script:Failed -eq 0) {
    Write-Host ("==[ ALL CHECKS PASSED ({0:N1}s total) ]==" -f $totalDur) -ForegroundColor Green
    Write-Host "Safe to push / gh pr create." -ForegroundColor Green
    exit 0
} else {
    Write-Host ("==[ {0} CHECK(S) FAILED ({1:N1}s total) ]==" -f $Script:Failed, $totalDur) -ForegroundColor Red
    Write-Host "DO NOT push. Fix the failures above and re-run." -ForegroundColor Red
    exit 1
}


 succeeded in 292ms:
{
  "persona": "kant",
  "focal_target": 300,
  "shard_count": 2,
  "all_shards_pass": true,
  "results": [
    {
      "shard": "kant_r8v3_run0_stim.duckdb",
      "all_pass": true,
      "checks": {
        "1_alternation": {
          "pass": true,
          "violations": [],
          "distribution": [
            {
              "speaker_persona_id": "_stimulus",
              "turn_index": 1,
              "count": 234
            },
            {
              "speaker_persona_id": "kant",
              "turn_index": 0,
              "count": 270
            },
            {
              "speaker_persona_id": "kant",
              "turn_index": 2,
              "count": 30
            }
          ]
        },
        "2_focal_count": {
          "pass": true,
          "focal_count": 300,
          "target": 300,
          "tolerance_band": [
            285,
            315
          ]
        },
        "3_incomplete_dialog": {
          "pass": true,
          "violations": []
        },
        "4_focal_only_consumer": {
          "focal_count": 300,
          "non_focal_count": 234,
          "total_count": 534
        }
      }
    },
    {
      "shard": "kant_r8v3_run1_stim.duckdb",
      "all_pass": true,
      "checks": {
        "1_alternation": {
          "pass": true,
          "violations": [],
          "distribution": [
            {
              "speaker_persona_id": "_stimulus",
              "turn_index": 1,
              "count": 234
            },
            {
              "speaker_persona_id": "kant",
              "turn_index": 0,
              "count": 270
            },
            {
              "speaker_persona_id": "kant",
              "turn_index": 2,
              "count": 30
            }
          ]
        },
        "2_focal_count": {
          "pass": true,
          "focal_count": 300,
          "target": 300,
          "tolerance_band": [
            285,
            315
          ]
        },
        "3_incomplete_dialog": {
          "pass": true,
          "violations": []
        },
        "4_focal_only_consumer": {
          "focal_count": 300,
          "non_focal_count": 234,
          "total_count": 534
        }
      }
    }
  ]
}
{
  "persona": "kant",
  "focal_target": 300,
  "shard_count": 2,
  "all_shards_pass": true,
  "results": [
    {
      "shard": "kant_planb_nolora_run0_stim.duckdb",
      "all_pass": true,
      "checks": {
        "1_alternation": {
          "pass": true,
          "violations": [],
          "distribution": [
            {
              "speaker_persona_id": "_stimulus",
              "turn_index": 1,
              "count": 234
            },
            {
              "speaker_persona_id": "kant",
              "turn_index": 0,
              "count": 270
            },
            {
              "speaker_persona_id": "kant",
              "turn_index": 2,
              "count": 30
            }
          ]
        },
        "2_focal_count": {
          "pass": true,
          "focal_count": 300,
          "target": 300,
          "tolerance_band": [
            285,
            315
          ]
        },
        "3_incomplete_dialog": {
          "pass": true,
          "violations": []
        },
        "4_focal_only_consumer": {
          "focal_count": 300,
          "non_focal_count": 234,
          "total_count": 534
        }
      }
    },
    {
      "shard": "kant_planb_nolora_run1_stim.duckdb",
      "all_pass": true,
      "checks": {
        "1_alternation": {
          "pass": true,
          "violations": [],
          "distribution": [
            {
              "speaker_persona_id": "_stimulus",
              "turn_index": 1,
              "count": 234
            },
            {
              "speaker_persona_id": "kant",
              "turn_index": 0,
              "count": 270
            },
            {
              "speaker_persona_id": "kant",
              "turn_index": 2,
              "count": 30
            }
          ]
        },
        "2_focal_count": {
          "pass": true,
          "focal_count": 300,
          "target": 300,
          "tolerance_band": [
            285,
            315
          ]
        },
        "3_incomplete_dialog": {
          "pass": true,
          "violations": []
        },
        "4_focal_only_consumer": {
          "focal_count": 300,
          "non_focal_count": 234,
          "total_count": 534
        }
      }
    }
  ]
}

 succeeded in 310ms:
==[ START 2026-05-17T00:20:26+09:00 ]==
==[ LoRA-on run0 2026-05-17T00:20:26+09:00 ]==
2026-05-17 00:20:26,468 [__main__] INFO: adapter kant_r8v3 confirmed loaded on sglang
2026-05-17 00:20:26,468 [__main__] INFO: pilot start persona=kant tag=r8 run=0 sliced=45 multi-turn-max=6 (focal per stim avg = 1.11)
2026-05-17 00:21:03,095 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=25/300 rate=0.68 focal/s eta=6.7 min
2026-05-17 00:21:29,427 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=50/300 rate=0.79 focal/s eta=5.2 min
2026-05-17 00:22:06,019 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=75/300 rate=0.75 focal/s eta=5.0 min
2026-05-17 00:22:30,833 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=100/300 rate=0.80 focal/s eta=4.1 min
2026-05-17 00:23:07,775 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=125/300 rate=0.77 focal/s eta=3.8 min
2026-05-17 00:23:33,035 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=150/300 rate=0.80 focal/s eta=3.1 min
2026-05-17 00:24:08,232 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=175/300 rate=0.79 focal/s eta=2.6 min
2026-05-17 00:24:34,828 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=200/300 rate=0.81 focal/s eta=2.1 min
2026-05-17 00:25:06,829 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=225/300 rate=0.80 focal/s eta=1.6 min
2026-05-17 00:25:32,073 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=250/300 rate=0.82 focal/s eta=1.0 min
2026-05-17 00:26:07,681 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=275/300 rate=0.81 focal/s eta=0.5 min
2026-05-17 00:26:33,098 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=300/300 rate=0.82 focal/s eta=0.0 min
2026-05-17 00:26:33,112 [__main__] INFO: pilot done persona=kant tag=r8 run=0 completed=300 elapsed=6.1 min output=data\eval\m9-c-adopt-plan-b-verdict\kant_r8v3_run0_stim.duckdb
==[ LoRA-on run1 2026-05-17T00:26:33+09:00 ]==
2026-05-17 00:26:33,370 [__main__] INFO: adapter kant_r8v3 confirmed loaded on sglang
2026-05-17 00:26:33,370 [__main__] INFO: pilot start persona=kant tag=r8 run=1 sliced=45 multi-turn-max=6 (focal per stim avg = 1.11)
2026-05-17 00:27:08,704 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=25/300 rate=0.71 focal/s eta=6.5 min
2026-05-17 00:27:34,489 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=50/300 rate=0.82 focal/s eta=5.1 min
2026-05-17 00:28:09,238 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=75/300 rate=0.78 focal/s eta=4.8 min
2026-05-17 00:28:35,961 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=100/300 rate=0.82 focal/s eta=4.1 min
2026-05-17 00:29:12,027 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=125/300 rate=0.79 focal/s eta=3.7 min
2026-05-17 00:29:36,800 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=150/300 rate=0.82 focal/s eta=3.1 min
2026-05-17 00:30:11,702 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=175/300 rate=0.80 focal/s eta=2.6 min
2026-05-17 00:30:38,155 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=200/300 rate=0.82 focal/s eta=2.0 min
2026-05-17 00:31:19,115 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=225/300 rate=0.79 focal/s eta=1.6 min
2026-05-17 00:31:42,500 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=250/300 rate=0.81 focal/s eta=1.0 min
2026-05-17 00:32:17,874 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=275/300 rate=0.80 focal/s eta=0.5 min
2026-05-17 00:32:41,816 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=300/300 rate=0.81 focal/s eta=0.0 min
2026-05-17 00:32:41,830 [__main__] INFO: pilot done persona=kant tag=r8 run=1 completed=300 elapsed=6.1 min output=data\eval\m9-c-adopt-plan-b-verdict\kant_r8v3_run1_stim.duckdb
==[ no-LoRA run0 2026-05-17T00:32:41+09:00 ]==
2026-05-17 00:32:42,061 [__main__] INFO: --no-lora-control mode: routing to base model Qwen/Qwen3-8B
2026-05-17 00:32:42,062 [__main__] INFO: pilot start persona=kant tag=nolora run=0 sliced=45 multi-turn-max=6 (focal per stim avg = 1.11)
2026-05-17 00:33:16,889 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=25/300 rate=0.72 focal/s eta=6.4 min
2026-05-17 00:33:40,539 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=50/300 rate=0.85 focal/s eta=4.9 min
2026-05-17 00:34:17,224 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=75/300 rate=0.79 focal/s eta=4.8 min
2026-05-17 00:34:42,463 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=100/300 rate=0.83 focal/s eta=4.0 min
2026-05-17 00:35:17,869 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=125/300 rate=0.80 focal/s eta=3.6 min
2026-05-17 00:35:41,118 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=150/300 rate=0.84 focal/s eta=3.0 min
2026-05-17 00:36:14,761 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=175/300 rate=0.82 focal/s eta=2.5 min
2026-05-17 00:36:40,136 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=200/300 rate=0.84 focal/s eta=2.0 min
2026-05-17 00:37:17,879 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=225/300 rate=0.82 focal/s eta=1.5 min
2026-05-17 00:37:43,975 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=250/300 rate=0.83 focal/s eta=1.0 min
2026-05-17 00:38:19,181 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=275/300 rate=0.82 focal/s eta=0.5 min
2026-05-17 00:38:43,005 [__main__] INFO: checkpoint persona=kant tag=nolora run=0 completed=300/300 rate=0.83 focal/s eta=0.0 min
2026-05-17 00:38:43,018 [__main__] INFO: pilot done persona=kant tag=nolora run=0 completed=300 elapsed=6.0 min output=data\eval\m9-c-adopt-plan-b-verdict\kant_planb_nolora_run0_stim.duckdb
==[ no-LoRA run1 2026-05-17T00:38:43+09:00 ]==
2026-05-17 00:38:43,253 [__main__] INFO: --no-lora-control mode: routing to base model Qwen/Qwen3-8B
2026-05-17 00:38:43,253 [__main__] INFO: pilot start persona=kant tag=nolora run=1 sliced=45 multi-turn-max=6 (focal per stim avg = 1.11)
2026-05-17 00:39:19,349 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=25/300 rate=0.69 focal/s eta=6.6 min
2026-05-17 00:39:45,404 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=50/300 rate=0.80 focal/s eta=5.2 min
2026-05-17 00:40:21,238 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=75/300 rate=0.77 focal/s eta=4.9 min
2026-05-17 00:40:44,609 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=100/300 rate=0.82 focal/s eta=4.0 min
2026-05-17 00:41:18,540 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=125/300 rate=0.80 focal/s eta=3.6 min
2026-05-17 00:41:43,691 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=150/300 rate=0.83 focal/s eta=3.0 min
2026-05-17 00:42:17,887 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=175/300 rate=0.82 focal/s eta=2.6 min
2026-05-17 00:42:45,873 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=200/300 rate=0.82 focal/s eta=2.0 min
2026-05-17 00:43:22,209 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=225/300 rate=0.81 focal/s eta=1.5 min
2026-05-17 00:43:47,731 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=250/300 rate=0.82 focal/s eta=1.0 min
2026-05-17 00:44:23,104 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=275/300 rate=0.81 focal/s eta=0.5 min
2026-05-17 00:44:48,503 [__main__] INFO: checkpoint persona=kant tag=nolora run=1 completed=300/300 rate=0.82 focal/s eta=0.0 min
2026-05-17 00:44:48,516 [__main__] INFO: pilot done persona=kant tag=nolora run=1 completed=300 elapsed=6.1 min output=data\eval\m9-c-adopt-plan-b-verdict\kant_planb_nolora_run1_stim.duckdb
==[ ALL DONE 2026-05-17T00:44:48+09:00 ]==
total 5176
drwxr-xr-x 1 johnd 197611       0  5譛・17 00:44 .
drwxr-xr-x 1 johnd 197611       0  5譛・17 00:18 ..
-rw-r--r-- 1 johnd 197611 1323008  5譛・17 00:38 kant_planb_nolora_run0_stim.duckdb
-rw-r--r-- 1 johnd 197611 1323008  5譛・17 00:44 kant_planb_nolora_run1_stim.duckdb
-rw-r--r-- 1 johnd 197611 1323008  5譛・17 00:26 kant_r8v3_run0_stim.duckdb
-rw-r--r-- 1 johnd 197611 1323008  5譛・17 00:32 kant_r8v3_run1_stim.duckdb

hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-ChildItem data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2 -Filter '*kant_r8v2*' | Select-Object Name,Length,LastWriteTime" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "kant_r8v2_run|m9-c-adopt-tier-b-pilot-multiturn-v2|turn-count 300|cycle-count 6|multi-turn-max 6" .steering scripts tests -S' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-ChildItem data/eval/m9-c-adopt-tier-b-pilot-multiturn -Filter 'kant_nolora*' | Select-Object Name,Length,LastWriteTime" in C:\ERRE-Sand_Box
 succeeded in 367ms:

Name                        Length LastWriteTime     
----                        ------ -------------     
kant_r8v2_run0_stim.duckdb 1323008 2026/05/16 7:48:09
kant_r8v2_run1_stim.duckdb 1323008 2026/05/16 7:54:09



 succeeded in 372ms:
scripts\m9-c-adopt\tier_b_pilot.py:41:        --turn-count 300 --cycle-count 6 \\
scripts\m9-c-adopt\tier_b_pilot.py:48:        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \\
scripts\m9-c-adopt\tier_b_pilot.py:55:        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \\
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:45:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:54:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:63:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:71:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:59:    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb"),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:60:    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run1_stim.duckdb"),
scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:430:            " Defaults to the Plan A v2 baseline (kant_r8v2_run{0,1}); pass"
scripts\m9-c-adopt\da15_calibration_panel.py:14:  ``data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb``
scripts\m9-c-adopt\da15_calibration_panel.py:21:  distribution overlaps with kant_r8v2_run0_stim. The natural baseline is
scripts\m9-c-adopt\da15_calibration_panel.py:56:    "data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb",
scripts\m9-c-adopt\da15_calibration_panel.py:60:with kant_r8v2_run0_stim (de/en/ja). The natural baseline is almost
scripts\m9-c-adopt\da15_calibration_panel.py:234:            "kant_r8v2_run0_stim — generated by Qwen3-8B + kant LoRA r8 v2"
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:58:     --run-idx {0,1} --turn-count 300 --cycle-count 6 --multi-turn-max 6
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:62:     --turn-count 300 --cycle-count 6 --multi-turn-max 6 --output
.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:145:  の引数 (`--turn-count 300 --cycle-count 6 --multi-turn-max 6`) を
.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:39:   - LoRA-on run: `--rank 8 --multi-turn-max 6 --turn-count 300
.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:40:     --cycle-count 6` × 2 run (`run0`、`run1`) → 2 shards、~1.5h × 2
.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:41:   - no-LoRA control: `--no-lora-control --rank 0 --multi-turn-max 6
.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:42:     --turn-count 300 --cycle-count 6` × 2 run → 2 shards、~1h × 2
.steering\20260518-m9-c-adopt-plan-b-verdict\blockers.md:9:    - `data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`
.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:37:v2 §Phase B 通り。`--cycle-count 6` を必ず指定 (PR #140 反映、cycle-count=3
.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:48:      --turn-count 500 --cycle-count 6 \
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:261:**重要 (Codex H1 反映)**: `--cycle-count 6` を指定すること。`cycle-count=3` だと
.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:270:      --turn-count 500 --cycle-count 6 \
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\decisions.md:30:  `--turn-count 500 --cycle-count 6` に変更 (focal≈504、target 500 を満たす)。
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\decisions.md:118:- **§Phase B stimulus**: `--turn-count 500 --cycle-count 6` (focal≈504)、新
.steering\20260507-m9-eval-phase2-run1-calibration-prompt\codex-review-run1-calibration.md:10:- 推奨: v2 prompt で stimulus の `cycle_count` を 6 以上に変更する。`--turn-count 500 --cycle-count 6` は focal≈504 で audit target 500 を満たす。3-cycle 固定が必要なら target を 264 に下げる判断が必要だが、これは P3 spec 変更扱い。
.steering\20260513-m9-c-adopt\next-session-prompt-pilot-multiturn-investigation.md:93:- 採取モード: multi-turn (`--multi-turn-max 6` で stim × 6 alternating
.steering\20260509-m9-individual-layer-schema-add\next-session-prompt.md:85:      --turn-count 500 --cycle-count 6 \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:2:2026-05-16 07:55:40,427 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:3:2026-05-16 07:55:40,846 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb w=0 total=100 de=54 en=35 ja=3 other=0 dropped=8 mean_burrows=114.3998
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:4:2026-05-16 07:55:40,919 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb w=1 total=100 de=56 en=35 ja=2 other=0 dropped=7 mean_burrows=116.1064
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:5:2026-05-16 07:55:40,985 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb w=2 total=100 de=54 en=36 ja=4 other=0 dropped=6 mean_burrows=116.1669
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:6:2026-05-16 07:55:40,995 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:7:2026-05-16 07:55:41,070 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=0 total=100 de=51 en=36 ja=5 other=0 dropped=8 mean_burrows=113.2953
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:8:2026-05-16 07:55:41,135 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=1 total=100 de=55 en=35 ja=1 other=0 dropped=9 mean_burrows=116.3416
.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:9:2026-05-16 07:55:41,209 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=2 total=100 de=54 en=36 ja=4 other=0 dropped=6 mean_burrows=111.3366
.steering\20260515-m9-c-adopt-retrain-v2-verdict\design.md:42:    --multi-turn-max 6 --max-focal-per-shard 300 \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:1:2026-05-16 07:54:10,572 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:2:2026-05-16 07:54:15,629 [__main__] INFO: window 1/?  shard=kant_r8v2_run0_stim.duckdb w_idx=0 big5=E:3.10/A:3.50/C:3.20/N:3.00/O:3.20 rate=0.19 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:3:2026-05-16 07:54:20,613 [__main__] INFO: window 2/?  shard=kant_r8v2_run0_stim.duckdb w_idx=1 big5=E:3.20/A:3.40/C:3.40/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:4:2026-05-16 07:54:25,609 [__main__] INFO: window 3/?  shard=kant_r8v2_run0_stim.duckdb w_idx=2 big5=E:3.10/A:3.40/C:3.40/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:5:2026-05-16 07:54:25,621 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:6:2026-05-16 07:54:30,549 [__main__] INFO: window 4/?  shard=kant_r8v2_run1_stim.duckdb w_idx=0 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:7:2026-05-16 07:54:35,465 [__main__] INFO: window 5/?  shard=kant_r8v2_run1_stim.duckdb w_idx=1 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:8:2026-05-16 07:54:40,329 [__main__] INFO: window 6/?  shard=kant_r8v2_run1_stim.duckdb w_idx=2 big5=E:3.10/A:3.40/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:54:  `--turn-count 300 --cycle-count 6 --multi-turn-max 6 --adapter-name <name>` で、
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:11:    "kant_r8v2_run0_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:12:    "kant_r8v2_run1_stim.duckdb"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:26:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:33:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:40:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:47:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:54:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:61:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\vendi.log:1:2026-05-16 07:54:45,660 [__main__] INFO: loading 2 shards: ['kant_r8v2_run0_stim.duckdb', 'kant_r8v2_run1_stim.duckdb']
.steering\20260515-m9-c-adopt-retrain-v2-verdict\vendi.log:2:2026-05-16 07:54:45,873 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\vendi.log:11:2026-05-16 07:55:21,793 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260514-m9-c-adopt-retrain-v2-impl\tasklist.md:60:      --adapter data/lora/m9-c-adopt-v2/kant_r8_v2/ --multi-turn-max 6
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:8:    "kant_r8v2_run0_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:9:    "kant_r8v2_run1_stim.duckdb"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:32:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:50:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:68:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:86:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:104:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:122:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:32:    "kant_r8v2_run0_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:33:    "kant_r8v2_run1_stim.duckdb"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:37:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:104:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:173:      "run_id": "kant_r8v2_run0_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:240:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:304:      "run_id": "kant_r8v2_run1_stim",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:372:      "run_id": "kant_r8v2_run1_stim",
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:58:     `--multi-turn-max 6` を使用。Kant max expected_turn_count=3 のため 6 は
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:99:   採取は `--multi-turn-max 6` で実行。
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:110:- `--turn-count 300 --cycle-count 6 --multi-turn-max 6`
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:209:  `--turn-count 10 --multi-turn-max 6` で kant_r8_real adapter を 1 cycle 走らせ、
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:222:  --turn-count 10 --cycle-count 2 --multi-turn-max 6 \
.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:274:2. **`expected_turn_count` の handling**: `--multi-turn-max 6` で全 stimulus の
.steering\20260515-m9-c-adopt-retrain-v2-verdict\pilot_run1.log:14:2026-05-16 07:54:09,457 [__main__] INFO: pilot done persona=kant tag=r8 run=1 completed=300 elapsed=6.0 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run1_stim.duckdb
.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:12:- **背景**: design.md 初版 (no-LoRA SGLang control なし、turn-count 300 単独
.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:28:- `--turn-count 300 --cycle-count 6` を維持 (compute 抑制)
.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:126:- **LOW-2** (`--multi-turn-max 6`): 採用 ADOPT-WITH-NOTE。design.md に
.steering\20260515-m9-c-adopt-retrain-v2-verdict\validation-v2-kant.json:8:      "shard": "kant_r8v2_run0_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\validation-v2-kant.json:53:      "shard": "kant_r8v2_run1_stim.duckdb",
.steering\20260515-m9-c-adopt-retrain-v2-verdict\pilot_run0.log:14:2026-05-16 07:48:09,549 [__main__] INFO: pilot done persona=kant tag=r8 run=0 completed=300 elapsed=6.1 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run0_stim.duckdb
.steering\20260514-m9-c-adopt-retrain-v2-impl\next-session-prompt-FINAL-training.md:45:       --multi-turn-max 6 --max-focal-per-shard 300 \\
.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-scenario-III-phase-e-amended.md:23:   (`tier_b_pilot.py` `--multi-turn-max 6` で full battery 採取)
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:10:[phase3] pilot run 0 → data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:15:2026-05-16 07:48:09,549 [__main__] INFO: pilot done persona=kant tag=r8 run=0 completed=300 elapsed=6.1 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run0_stim.duckdb
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:16:[phase3] pilot run 1 → data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run1_stim.duckdb
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:21:2026-05-16 07:54:09,457 [__main__] INFO: pilot done persona=kant tag=r8 run=1 completed=300 elapsed=6.0 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run1_stim.duckdb
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:25:2026-05-16 07:54:25,621 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:26:2026-05-16 07:54:30,549 [__main__] INFO: window 4/?  shard=kant_r8v2_run1_stim.duckdb w_idx=0 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:27:2026-05-16 07:54:35,465 [__main__] INFO: window 5/?  shard=kant_r8v2_run1_stim.duckdb w_idx=1 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:28:2026-05-16 07:54:40,329 [__main__] INFO: window 6/?  shard=kant_r8v2_run1_stim.duckdb w_idx=2 big5=E:3.10/A:3.40/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:38:2026-05-16 07:55:40,995 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:39:2026-05-16 07:55:41,070 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=0 total=100 de=51 en=36 ja=5 other=0 dropped=8 mean_burrows=113.2953
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:40:2026-05-16 07:55:41,135 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=1 total=100 de=55 en=35 ja=1 other=0 dropped=9 mean_burrows=116.3416
.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:41:2026-05-16 07:55:41,209 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=2 total=100 de=54 en=36 ja=4 other=0 dropped=6 mean_burrows=111.3366
.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-scenario-II-retrain-v2.md:46:- multi-turn pilot 再採取 (本 PR 拡張済 driver `tier_b_pilot.py --multi-turn-max 6` 再利用)
.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-scenario-II-retrain-v2.md:81:- multi-turn pilot 再採取 (`tier_b_pilot.py --multi-turn-max 6 --rank 8` で
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:389:  29:    - `--multi-turn-max N` (default `1` 縺ｧ驕主悉莠呈鋤縲（nvestigation 縺ｧ `--multi-turn-max 6` 繧剃ｽｿ逕ｨ)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:419:  59:    謗｡蜿悶・ `--multi-turn-max 6` 縺ｧ螳溯｡後・
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:425:  65: - `--turn-count 300 --cycle-count 6 --multi-turn-max 6`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:490: 130:   `--turn-count 10 --multi-turn-max 6` 縺ｧ kant_r8_real adapter 繧・1 cycle 襍ｰ繧峨○縲・  DuckDB shard 縺ｫ turn_index 0..N-1 縺・alternating speaker 縺ｧ譖ｸ縺崎ｾｼ縺ｾ繧後※縺・ｋ縺薙→繧・  逶ｮ隕也｢ｺ隱阪・- **邨ｱ蜷医ユ繧ｹ繝・*: 6 shard 謗｡蜿門ｮ碁≠縺御ｺ句ｮ滉ｸ翫・邨ｱ蜷医ユ繧ｹ繝医Ｄonsumer (Vendi/ICC/Burrows)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:498: 138:   --turn-count 10 --cycle-count 2 --multi-turn-max 6 \
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:517: 157:    邨檎罰 (豺ｷ蝨ｨ backend)" 繧・"interlocutor 縺ｯ蝗ｺ螳・utterance (no-op)" 繧呈､懆ｨ弱＠縺溘′縲・   baseline 縺ｨ蜷・protocol 縺ｧ蟇ｾ豈斐☆繧九↓縺ｯ same-inference-fn 縺梧怙繧・apples-to-apples縲・2. **`expected_turn_count` 縺ｮ handling**: `--multi-turn-max 6` 縺ｧ蜈ｨ stimulus 縺ｮ
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:720:  39:    - `--multi-turn-max N` (default `1` で過去互換、investigation で `--multi-turn-max 6` を使用)
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:756:  75:    採取は `--multi-turn-max 6` で実行。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:763:  82: - `--turn-count 300 --cycle-count 6 --multi-turn-max 6`
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:842: 161:   `--turn-count 10 --multi-turn-max 6` で kant_r8_real adapter を 1 cycle 走らせ、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:855: 174:   --turn-count 10 --cycle-count 2 --multi-turn-max 6 \
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:879: 198: 2. **`expected_turn_count` の handling**: `--multi-turn-max 6` で全 stimulus の
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:2078:  26:         --turn-count 300 --cycle-count 6 \\
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5698:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5711:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5719:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5882:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5969:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5982:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5990:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6153:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6238:  59:   `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6251:  72:   - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6259:  80:      Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6422: 243: ### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6504:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6517:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6525:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6688:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6785:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6798:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6806:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6969:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7064:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7077:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7085:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7248:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7354:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7367:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7375:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7538:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:16:PILOT_OUT_DIR="data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:63:    out="${PILOT_OUT_DIR}/kant_r8v2_run${run_idx}_stim.duckdb"
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:71:        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:83:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:90:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:105:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:113:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260514-m9-c-adopt-pilot-multiturn\tasklist.md:20:- [ ] Smoke test: `--turn-count 10 --multi-turn-max 6` で kant_r8_real 単 cycle、
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:28:  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:41:  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:49:     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:212:### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt.md:47:       --multi-turn-max 6 --output .steering/<task>/tier-b-pilot-multiturn-kant-r8-v2.duckdb`
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt.md:131:    --multi-turn-max 6 --max-focal-per-shard 300 --output ...`
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt-FINAL.md:58:       --multi-turn-max 6 --max-focal-per-shard 300 \\
.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt-FINAL.md:179:    --multi-turn-max 6 --max-focal-per-shard 300 \\
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:18:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:19:    "kant_r8v2_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:18:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:19:    "kant_r8v2_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:18:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:19:    "kant_r8v2_run1_stim.duckdb"
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1378:- `--turn-count 300 --cycle-count 6` 繧堤ｶｭ謖・(compute 謚大宛)
.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1456:- **LOW-2** (`--multi-turn-max 6`): 謗｡逕ｨ ADOPT-WITH-NOTE縲Ｅesign.md 縺ｫ
.steering\20260516-m9-c-adopt-da15-impl\design.md:34:rescore。v2 shards = `data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/
.steering\20260516-m9-c-adopt-da15-impl\design.md:35:kant_r8v2_run{0,1}_stim.duckdb`、no-LoRA shards = `data/eval/m9-c-adopt-tier-
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:61:  parameters as the v2 baseline (`--turn-count 300 --cycle-count 6
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:62:  --multi-turn-max 6`). Confirm apples-to-apples with the v2 reference
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:63:  (`data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`).
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:88:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:95:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:105:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:111:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:117:(`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\requirement.md:49:   - LoRA-on × 2 (run0, run1): `tier_b_pilot.py --rank 8 --turn-count 300
.steering\20260516-m9-c-adopt-plan-b-eval-gen\requirement.md:50:     --cycle-count 6 --multi-turn-max 6`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\pr-body-draft.md:9:  protocol (`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:74:  parameters as the v2 baseline (`--turn-count 300 --cycle-count 6
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:75:  --multi-turn-max 6`). Confirm apples-to-apples with the v2 reference
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:76:  (`data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`).
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:687:+            " Defaults to the Plan A v2 baseline (kant_r8v2_run{0,1}); pass"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1877:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1886:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1895:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1903:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2680:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2687:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2697:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2703:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2709:(`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)縲・
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3394:scripts\m9-c-adopt\tier_b_pilot.py:41:        --turn-count 300 --cycle-count 6 \\
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3396:scripts\m9-c-adopt\tier_b_pilot.py:48:        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \\
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3398:scripts\m9-c-adopt\tier_b_pilot.py:55:        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \\
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3417:scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:45:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3418:scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:54:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3419:scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:63:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3421:scripts\m9-c-adopt\run_plan_b_eval_sequence.sh:71:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3423:scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:59:    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb"),
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3424:scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:60:    Path("data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run1_stim.duckdb"),
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3452:scripts\m9-c-adopt\rescore_vendi_alt_kernel.py:430:            " Defaults to the Plan A v2 baseline (kant_r8v2_run{0,1}); pass"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3503:scripts\m9-c-adopt\da15_calibration_panel.py:14:  ``data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb``
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3504:scripts\m9-c-adopt\da15_calibration_panel.py:21:  distribution overlaps with kant_r8v2_run0_stim. The natural baseline is
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3505:scripts\m9-c-adopt\da15_calibration_panel.py:56:    "data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3506:scripts\m9-c-adopt\da15_calibration_panel.py:60:with kant_r8v2_run0_stim (de/en/ja). The natural baseline is almost
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3507:scripts\m9-c-adopt\da15_calibration_panel.py:234:            "kant_r8v2_run0_stim — generated by Qwen3-8B + kant LoRA r8 v2"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3557:.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:58:     --run-idx {0,1} --turn-count 300 --cycle-count 6 --multi-turn-max 6
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3558:.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:62:     --turn-count 300 --cycle-count 6 --multi-turn-max 6 --output
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3563:.steering\20260518-m9-c-adopt-plan-b-verdict\next-session-prompt-FINAL-eval-gen-plus-verdict.md:145:  の引数 (`--turn-count 300 --cycle-count 6 --multi-turn-max 6`) を
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3566:.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:39:   - LoRA-on run: `--rank 8 --multi-turn-max 6 --turn-count 300
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3567:.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:40:     --cycle-count 6` × 2 run (`run0`、`run1`) → 2 shards、~1.5h × 2
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3568:.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:41:   - no-LoRA control: `--no-lora-control --rank 0 --multi-turn-max 6
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3569:.steering\20260518-m9-c-adopt-plan-b-verdict\design.md:42:     --turn-count 300 --cycle-count 6` × 2 run → 2 shards、~1h × 2
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3570:.steering\20260518-m9-c-adopt-plan-b-verdict\blockers.md:9:    - `data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3578:data\calibration\kant_heidegger_corpus.json:6:  "license_attribution": "kant_r8v2_run0_stim — generated by Qwen3-8B + kant LoRA r8 v2 (Apache-2.0 generation pipeline, repository licence applies). nietzsche_stimulus_run0 — generated by Qwen3-8B + nietzsche persona prompt (no LoRA), license-clean Apache-2.0 pipeline, stimulus condition selected so the language distribution matches the kant_r8v2 pool. D-1 substitution: Codex spec named Heidegger as control, repo has nietzsche persona instead; both are 19c-German non-Kant philosophers from the same generation pipeline.",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3579:data\calibration\kant_heidegger_corpus.json:11:    "kant": "data\\eval\\m9-c-adopt-tier-b-pilot-multiturn-v2\\kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3645:.steering\20260515-m9-c-adopt-retrain-v2-verdict\vendi.log:1:2026-05-16 07:54:45,660 [__main__] INFO: loading 2 shards: ['kant_r8v2_run0_stim.duckdb', 'kant_r8v2_run1_stim.duckdb']
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3646:.steering\20260515-m9-c-adopt-retrain-v2-verdict\vendi.log:2:2026-05-16 07:54:45,873 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb focal=300 windows=3
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3647:.steering\20260515-m9-c-adopt-retrain-v2-verdict\vendi.log:11:2026-05-16 07:55:21,793 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3648:.steering\20260515-m9-c-adopt-retrain-v2-verdict\validation-v2-kant.json:8:      "shard": "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3649:.steering\20260515-m9-c-adopt-retrain-v2-verdict\validation-v2-kant.json:53:      "shard": "kant_r8v2_run1_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3653:.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:63:    out="${PILOT_OUT_DIR}/kant_r8v2_run${run_idx}_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3655:.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:71:        --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3656:.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:83:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3657:.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:90:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3658:.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:105:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3659:.steering\20260515-m9-c-adopt-retrain-v2-verdict\run_phase_3_4.sh:113:    --shards-glob "${PILOT_OUT_DIR}/kant_r8v2_run*_stim.duckdb" \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3665:.steering\20260507-m9-eval-phase2-run1-calibration-prompt\decisions.md:30:  `--turn-count 500 --cycle-count 6` に変更 (focal≈504、target 500 を満たす)。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3670:.steering\20260507-m9-eval-phase2-run1-calibration-prompt\decisions.md:118:- **§Phase B stimulus**: `--turn-count 500 --cycle-count 6` (focal≈504)、新
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3672:.steering\20260515-m9-c-adopt-retrain-v2-verdict\pilot_run1.log:14:2026-05-16 07:54:09,457 [__main__] INFO: pilot done persona=kant tag=r8 run=1 completed=300 elapsed=6.0 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run1_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3674:.steering\20260507-m9-eval-phase2-run1-calibration-prompt\codex-review-run1-calibration.md:10:- 推奨: v2 prompt で stimulus の `cycle_count` を 6 以上に変更する。`--turn-count 500 --cycle-count 6` は focal≈504 で audit target 500 を満たす。3-cycle 固定が必要なら target を 264 に下げる判断が必要だが、これは P3 spec 変更扱い。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3679:.steering\20260515-m9-c-adopt-retrain-v2-verdict\pilot_run0.log:14:2026-05-16 07:48:09,549 [__main__] INFO: pilot done persona=kant tag=r8 run=0 completed=300 elapsed=6.1 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run0_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3683:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:10:[phase3] pilot run 0 → data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run0_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3684:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:15:2026-05-16 07:48:09,549 [__main__] INFO: pilot done persona=kant tag=r8 run=0 completed=300 elapsed=6.1 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run0_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3685:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:16:[phase3] pilot run 1 → data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run1_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3686:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:21:2026-05-16 07:54:09,457 [__main__] INFO: pilot done persona=kant tag=r8 run=1 completed=300 elapsed=6.0 min output=data\eval\m9-c-adopt-tier-b-pilot-multiturn-v2\kant_r8v2_run1_stim.duckdb
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3687:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:25:2026-05-16 07:54:25,621 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3688:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:26:2026-05-16 07:54:30,549 [__main__] INFO: window 4/?  shard=kant_r8v2_run1_stim.duckdb w_idx=0 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3689:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:27:2026-05-16 07:54:35,465 [__main__] INFO: window 5/?  shard=kant_r8v2_run1_stim.duckdb w_idx=1 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3690:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:28:2026-05-16 07:54:40,329 [__main__] INFO: window 6/?  shard=kant_r8v2_run1_stim.duckdb w_idx=2 big5=E:3.10/A:3.40/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3691:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:38:2026-05-16 07:55:40,995 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3692:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:39:2026-05-16 07:55:41,070 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=0 total=100 de=51 en=36 ja=5 other=0 dropped=8 mean_burrows=113.2953
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3693:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:40:2026-05-16 07:55:41,135 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=1 total=100 de=55 en=35 ja=1 other=0 dropped=9 mean_burrows=116.3416
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3694:.steering\20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:41:2026-05-16 07:55:41,209 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=2 total=100 de=54 en=36 ja=4 other=0 dropped=6 mean_burrows=111.3366
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3698:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:11:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3699:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:12:    "kant_r8v2_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3700:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:26:      "run_id": "kant_r8v2_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3701:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:33:      "run_id": "kant_r8v2_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3702:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:40:      "run_id": "kant_r8v2_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3703:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:47:      "run_id": "kant_r8v2_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3704:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:54:      "run_id": "kant_r8v2_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3705:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-vendi-semantic.json:61:      "run_id": "kant_r8v2_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3706:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:32:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3707:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:33:    "kant_r8v2_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3708:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:37:      "run_id": "kant_r8v2_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3709:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:104:      "run_id": "kant_r8v2_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3710:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:173:      "run_id": "kant_r8v2_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3711:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:240:      "run_id": "kant_r8v2_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3712:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:304:      "run_id": "kant_r8v2_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3713:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:372:      "run_id": "kant_r8v2_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3730:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:8:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3731:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:9:    "kant_r8v2_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3732:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:32:      "run_id": "kant_r8v2_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3733:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:50:      "run_id": "kant_r8v2_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3734:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:68:      "run_id": "kant_r8v2_run0_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3735:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:86:      "run_id": "kant_r8v2_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3736:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:104:      "run_id": "kant_r8v2_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3737:.steering\20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:122:      "run_id": "kant_r8v2_run1_stim",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3746:.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:1:2026-05-16 07:54:10,572 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb focal=300 windows=3
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3747:.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:2:2026-05-16 07:54:15,629 [__main__] INFO: window 1/?  shard=kant_r8v2_run0_stim.duckdb w_idx=0 big5=E:3.10/A:3.50/C:3.20/N:3.00/O:3.20 rate=0.19 win/s
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3748:.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:3:2026-05-16 07:54:20,613 [__main__] INFO: window 2/?  shard=kant_r8v2_run0_stim.duckdb w_idx=1 big5=E:3.20/A:3.40/C:3.40/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3749:.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:4:2026-05-16 07:54:25,609 [__main__] INFO: window 3/?  shard=kant_r8v2_run0_stim.duckdb w_idx=2 big5=E:3.10/A:3.40/C:3.40/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3750:.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:5:2026-05-16 07:54:25,621 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3751:.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:6:2026-05-16 07:54:30,549 [__main__] INFO: window 4/?  shard=kant_r8v2_run1_stim.duckdb w_idx=0 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.10 rate=0.20 win/s
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3752:.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:7:2026-05-16 07:54:35,465 [__main__] INFO: window 5/?  shard=kant_r8v2_run1_stim.duckdb w_idx=1 big5=E:3.10/A:3.50/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3753:.steering\20260515-m9-c-adopt-retrain-v2-verdict\icc.log:8:2026-05-16 07:54:40,329 [__main__] INFO: window 6/?  shard=kant_r8v2_run1_stim.duckdb w_idx=2 big5=E:3.10/A:3.40/C:3.30/N:3.00/O:3.00 rate=0.20 win/s
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3755:.steering\20260515-m9-c-adopt-retrain-v2-verdict\design.md:42:    --multi-turn-max 6 --max-focal-per-shard 300 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3758:.steering\20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:54:  `--turn-count 300 --cycle-count 6 --multi-turn-max 6 --adapter-name <name>` で、
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3760:.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:2:2026-05-16 07:55:40,427 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb focal=300 windows=3
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3761:.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:3:2026-05-16 07:55:40,846 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb w=0 total=100 de=54 en=35 ja=3 other=0 dropped=8 mean_burrows=114.3998
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3762:.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:4:2026-05-16 07:55:40,919 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb w=1 total=100 de=56 en=35 ja=2 other=0 dropped=7 mean_burrows=116.1064
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3763:.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:5:2026-05-16 07:55:40,985 [__main__] INFO: shard=kant_r8v2_run0_stim.duckdb w=2 total=100 de=54 en=36 ja=4 other=0 dropped=6 mean_burrows=116.1669
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3764:.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:6:2026-05-16 07:55:40,995 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb focal=300 windows=3
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3765:.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:7:2026-05-16 07:55:41,070 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=0 total=100 de=51 en=36 ja=5 other=0 dropped=8 mean_burrows=113.2953
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3766:.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:8:2026-05-16 07:55:41,135 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=1 total=100 de=55 en=35 ja=1 other=0 dropped=9 mean_burrows=116.3416
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3767:.steering\20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:9:2026-05-16 07:55:41,209 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=2 total=100 de=54 en=36 ja=4 other=0 dropped=6 mean_burrows=111.3366
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3769:.steering\20260514-m9-c-adopt-retrain-v2-impl\tasklist.md:60:      --adapter data/lora/m9-c-adopt-v2/kant_r8_v2/ --multi-turn-max 6
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3771:.steering\20260514-m9-c-adopt-retrain-v2-impl\next-session-prompt-FINAL-training.md:45:       --multi-turn-max 6 --max-focal-per-shard 300 \\
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3786:.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt.md:47:       --multi-turn-max 6 --output .steering/<task>/tier-b-pilot-multiturn-kant-r8-v2.duckdb`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3788:.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt.md:131:    --multi-turn-max 6 --max-focal-per-shard 300 --output ...`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3793:.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt-FINAL.md:58:       --multi-turn-max 6 --max-focal-per-shard 300 \\
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3796:.steering\20260514-m9-c-adopt-retrain-v2-design\next-session-prompt-FINAL.md:179:    --multi-turn-max 6 --max-focal-per-shard 300 \\
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3811:.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1378:- `--turn-count 300 --cycle-count 6` 繧堤ｶｭ謖・(compute 謚大宛)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3814:.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1456:- **LOW-2** (`--multi-turn-max 6`): 謗｡逕ｨ ADOPT-WITH-NOTE縲Ｅesign.md 縺ｫ
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3858:.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:37:v2 §Phase B 通り。`--cycle-count 6` を必ず指定 (PR #140 反映、cycle-count=3
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3859:.steering\20260430-m9-eval-system\g-gear-phase-bc-launch-prompt.md:48:      --turn-count 500 --cycle-count 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3893:.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:261:**重要 (Codex H1 反映)**: `--cycle-count 6` を指定すること。`cycle-count=3` だと
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3895:.steering\20260430-m9-eval-system\g-gear-p3-launch-prompt-v2.md:270:      --turn-count 500 --cycle-count 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3917:.steering\20260514-m9-c-adopt-pilot-multiturn\tasklist.md:20:- [ ] Smoke test: `--turn-count 10 --multi-turn-max 6` で kant_r8_real 単 cycle、
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3918:.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-scenario-II-retrain-v2.md:46:- multi-turn pilot 再採取 (本 PR 拡張済 driver `tier_b_pilot.py --multi-turn-max 6` 再利用)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3920:.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-scenario-II-retrain-v2.md:81:- multi-turn pilot 再採取 (`tier_b_pilot.py --multi-turn-max 6 --rank 8` で
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3921:.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:12:- **背景**: design.md 初版 (no-LoRA SGLang control なし、turn-count 300 単独
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3922:.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:28:- `--turn-count 300 --cycle-count 6` を維持 (compute 抑制)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3925:.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:126:- **LOW-2** (`--multi-turn-max 6`): 採用 ADOPT-WITH-NOTE。design.md に
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3937:.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:58:     `--multi-turn-max 6` を使用。Kant max expected_turn_count=3 のため 6 は
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3939:.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:99:   採取は `--multi-turn-max 6` で実行。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3942:.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:110:- `--turn-count 300 --cycle-count 6 --multi-turn-max 6`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3945:.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:209:  `--turn-count 10 --multi-turn-max 6` で kant_r8_real adapter を 1 cycle 走らせ、
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3947:.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:222:  --turn-count 10 --cycle-count 2 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3949:.steering\20260514-m9-c-adopt-pilot-multiturn\design.md:274:2. **`expected_turn_count` の handling**: `--multi-turn-max 6` で全 stimulus の
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3963:.steering\20260514-m9-c-adopt-pilot-multiturn\next-session-prompt-scenario-III-phase-e-amended.md:23:   (`tier_b_pilot.py` `--multi-turn-max 6` で full battery 採取)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3983:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:389:  29:    - `--multi-turn-max N` (default `1` 縺ｧ驕主悉莠呈鋤縲（nvestigation 縺ｧ `--multi-turn-max 6` 繧剃ｽｿ逕ｨ)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3985:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:419:  59:    謗｡蜿悶・ `--multi-turn-max 6` 縺ｧ螳溯｡後・
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3986:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:425:  65: - `--turn-count 300 --cycle-count 6 --multi-turn-max 6`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3989:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:490: 130:   `--turn-count 10 --multi-turn-max 6` 縺ｧ kant_r8_real adapter 繧・1 cycle 襍ｰ繧峨○縲・  DuckDB shard 縺ｫ turn_index 0..N-1 縺・alternating speaker 縺ｧ譖ｸ縺崎ｾｼ縺ｾ繧後※縺・ｋ縺薙→繧・  逶ｮ隕也｢ｺ隱阪・- **邨ｱ蜷医ユ繧ｹ繝・*: 6 shard 謗｡蜿門ｮ碁≠縺御ｺ句ｮ滉ｸ翫・邨ｱ蜷医ユ繧ｹ繝医Ｄonsumer (Vendi/ICC/Burrows)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3991:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:498: 138:   --turn-count 10 --cycle-count 2 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:3993:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:517: 157:    邨檎罰 (豺ｷ蝨ｨ backend)" 繧・"interlocutor 縺ｯ蝗ｺ螳・utterance (no-op)" 繧呈､懆ｨ弱＠縺溘′縲・   baseline 縺ｨ蜷・protocol 縺ｧ蟇ｾ豈斐☆繧九↓縺ｯ same-inference-fn 縺梧怙繧・apples-to-apples縲・2. **`expected_turn_count` 縺ｮ handling**: `--multi-turn-max 6` 縺ｧ蜈ｨ stimulus 縺ｮ
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4001:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:720:  39:    - `--multi-turn-max N` (default `1` で過去互換、investigation で `--multi-turn-max 6` を使用)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4003:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:756:  75:    採取は `--multi-turn-max 6` で実行。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4004:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:763:  82: - `--turn-count 300 --cycle-count 6 --multi-turn-max 6`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4007:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:842: 161:   `--turn-count 10 --multi-turn-max 6` で kant_r8_real adapter を 1 cycle 走らせ、
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4009:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:855: 174:   --turn-count 10 --cycle-count 2 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4011:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:879: 198: 2. **`expected_turn_count` の handling**: `--multi-turn-max 6` で全 stimulus の
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4019:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:2078:  26:         --turn-count 300 --cycle-count 6 \\
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4024:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5698:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4025:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5711:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4027:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5719:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4031:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5882:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4032:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5969:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4033:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5982:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4035:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5990:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4039:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6153:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4040:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6238:  59:   `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4041:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6251:  72:   - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4043:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6259:  80:      Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4047:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6422: 243: ### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4048:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6504:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4049:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6517:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4051:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6525:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4055:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6688:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4056:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6785:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4057:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6798:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4059:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6806:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4063:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6969:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4064:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7064:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4065:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7077:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4067:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7085:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4071:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7248:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4072:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7354:+  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4073:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7367:+  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4075:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7375:+     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4079:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7538:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4083:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:61:  parameters as the v2 baseline (`--turn-count 300 --cycle-count 6
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4084:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:62:  --multi-turn-max 6`). Confirm apples-to-apples with the v2 reference
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4085:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review-prompt.md:63:  (`data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`).
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4099:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:28:  `--turn-count 300 --cycle-count 6` のままなので、per-rank window は 6 個程度に
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4100:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:41:  - design は planned multi-turn でも `--turn-count 300 --cycle-count 6` を指定
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4102:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:49:     Baseline に近い形なら `--turn-count 528 --cycle-count 6` が自然。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4106:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:212:### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4114:.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:18:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4115:.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-mpnet-regression-kant.json:19:    "kant_r8v2_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4126:.steering\20260516-m9-c-adopt-da15-impl\design.md:35:kant_r8v2_run{0,1}_stim.duckdb`、no-LoRA shards = `data/eval/m9-c-adopt-tier-
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4152:.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:18:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4153:.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-bge-m3-kant.json:19:    "kant_r8v2_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4165:.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:18:    "kant_r8v2_run0_stim.duckdb",
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4166:.steering\20260516-m9-c-adopt-da15-impl\da15-rescore-e5-large-kant.json:19:    "kant_r8v2_run1_stim.duckdb"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4183:.steering\20260509-m9-individual-layer-schema-add\next-session-prompt.md:85:      --turn-count 500 --cycle-count 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4209:.steering\20260513-m9-c-adopt\next-session-prompt-pilot-multiturn-investigation.md:93:- 採取モード: multi-turn (`--multi-turn-max 6` で stim × 6 alternating
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4303:.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:88:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4305:.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:95:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4307:.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:105:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4310:.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:111:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4312:.steering\20260516-m9-c-adopt-plan-b-eval-gen\design.md:117:(`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)。
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4328:.steering\20260516-m9-c-adopt-plan-b-eval-gen\pr-body-draft.md:9:  protocol (`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4342:.steering\20260516-m9-c-adopt-plan-b-eval-gen\requirement.md:49:   - LoRA-on × 2 (run0, run1): `tier_b_pilot.py --rank 8 --turn-count 300
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4343:.steering\20260516-m9-c-adopt-plan-b-eval-gen\requirement.md:50:     --cycle-count 6 --multi-turn-max 6`
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4351:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:74:  parameters as the v2 baseline (`--turn-count 300 --cycle-count 6
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4352:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:75:  --multi-turn-max 6`). Confirm apples-to-apples with the v2 reference
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4353:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:76:  (`data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`).
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4365:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:687:+            " Defaults to the Plan A v2 baseline (kant_r8v2_run{0,1}); pass"
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4440:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1877:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4441:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1886:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4442:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1895:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4444:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:1903:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4476:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2680:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4478:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2687:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4480:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2697:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4483:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2703:    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4485:.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:2709:(`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)縲・
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4800:  parameters as the v2 baseline (`--turn-count 300 --cycle-count 6
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4801:  --multi-turn-max 6`). Confirm apples-to-apples with the v2 reference
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4802:  (`data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`).
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4890:3814:.steering\20260514-m9-c-adopt-retrain-v2-design\codex-review.stderr:1456:- **LOW-2** (`--multi-turn-max 6`): 謗｡逕ｨ ADOPT-WITH-NOTE縲Ｅesign.md 縺ｫ
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4891:3925:.steering\20260514-m9-c-adopt-pilot-multiturn\decisions.md:126:- **LOW-2** (`--multi-turn-max 6`): 採用 ADOPT-WITH-NOTE。design.md に
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4893:4031:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:5882:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4894:4039:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6153:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4895:4047:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6422: 243: ### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4896:4055:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6688:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4897:4063:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:6969:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4898:4071:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7248:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4899:4079:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.stderr:7538:+### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:4900:4106:.steering\20260514-m9-c-adopt-pilot-multiturn\codex-review.md:212:### LOW-2 — `--multi-turn-max 6` is harmless but should be explained as future-proofing
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:5037:  parameters as the v2 baseline (`--turn-count 300 --cycle-count 6
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:5038:  --multi-turn-max 6`). Confirm apples-to-apples with the v2 reference
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:5039:  (`data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`).
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:5597:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-ChildItem data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2 -Filter '*kant_r8v2*' | Select-Object Name,Length,LastWriteTime" in C:\ERRE-Sand_Box
.steering\20260516-m9-c-adopt-plan-b-eval-gen\codex-review.md:5599:"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "kant_r8v2_run|m9-c-adopt-tier-b-pilot-multiturn-v2|turn-count 300|cycle-count 6|multi-turn-max 6" .steering scripts tests -S' in C:\ERRE-Sand_Box

 succeeded in 316ms:

Name                          Length LastWriteTime      
----                          ------ -------------      
kant_nolora_run0_stim.duckdb 1323008 2026/05/14 13:46:38
kant_nolora_run1_stim.duckdb 1323008 2026/05/14 13:52:36



hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw .steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"_VENDI|_BURROWS|_ICC|THROUGHPUT|threshold|0.55|70|5\\.0|-0\\.5\" scripts/m9-c-adopt/da15_verdict.py .steering/20260515-m9-c-adopt-retrain-v2-verdict -S" in C:\ERRE-Sand_Box
 succeeded in 289ms:
{
  "comparator": "no-LoRA SGLang baseline (DA-14 authoritative)",
  "comparator_artefact_dir": ".steering/20260514-m9-c-adopt-pilot-multiturn/",
  "axes": {
    "vendi_semantic": {
      "v2_mean": 33.182859369999,
      "no_lora_mean": 33.31090056393359,
      "diff_v2_minus_nolora": -0.12804119393459246,
      "diff_ci_95": [
        -0.8540036491321873,
        0.6211691251338816
      ],
      "cohens_d": -0.1788470533504207,
      "threshold_point": -0.5,
      "threshold_ci": "ci_upper < 0",
      "pass": false
    },
    "burrows_reduction": {
      "v2_mean": 114.60777995370626,
      "no_lora_mean": 115.10090300065475,
      "reduction_pct": 0.4284267404450269,
      "reduction_ci_95_pct": [
        -1.8741679421100097,
        2.4694606443580356
      ],
      "threshold_point": 5.0,
      "threshold_ci": "ci_lower > 0",
      "pass": false
    },
    "icc_a1": {
      "v2_point": 0.9128856624319415,
      "v2_ci_95": [
        0.8807947019867548,
        0.9691714836223514
      ],
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
    "vendi_direction": "REVERSED toward goal (was wrong, now correct sign but insufficient magnitude)",
    "burrows_prior": 113.7227,
    "burrows_v2": 114.60777995370626,
    "burrows_direction": "slight degradation (was small reduction, now small increase)"
  },
  "matrix_script_note": "scripts/m9-c-adopt/da1_matrix_multiturn.py compares against MATCHED HISTORICAL Ollama baseline (DA-11 era). DA-14 mandates no-LoRA SGLang baseline. This file applies DA-14 thresholds correctly."
}

 succeeded in 297ms:
scripts/m9-c-adopt/da15_verdict.py:4:pre-registered DA-14 thresholds (unchanged) under the DA-15 amended metric
scripts/m9-c-adopt/da15_verdict.py:12:* rescore gate under balanced conditions: cohens_d ≤ -0.5 with diff CI
scripts/m9-c-adopt/da15_verdict.py:41:_VENDI_D_GATE: float = -0.5
scripts/m9-c-adopt/da15_verdict.py:42:_VENDI_AUC_GATE: float = 0.75
scripts/m9-c-adopt/da15_verdict.py:62:    if calib.get("overall_auc", 0) < _VENDI_AUC_GATE:
scripts/m9-c-adopt/da15_verdict.py:68:    return all(v["auc"] >= _VENDI_AUC_GATE for v in scored) if scored else False
scripts/m9-c-adopt/da15_verdict.py:76:        and payload["cohens_d"] <= _VENDI_D_GATE
scripts/m9-c-adopt/da15_verdict.py:95:        and natural_d <= _VENDI_D_GATE
scripts/m9-c-adopt/da15_verdict.py:235:    lines.append(f"- Plan A quorum threshold: **{q['quorum_threshold']}**")
scripts/m9-c-adopt/da15_verdict.py:262:            f" (AUC ≥ {_VENDI_AUC_GATE}) and the DA-14 thresholds (cohens_d ≤"
scripts/m9-c-adopt/da15_verdict.py:263:            f" {_VENDI_D_GATE}, CI upper < 0) under standard + balanced"
scripts/m9-c-adopt/da15_verdict.py:279:            " **non-gating** — Plan A's pre-registered thresholds operate"
scripts/m9-c-adopt/da15_verdict.py:281:            " upgrade ADOPT only when the global threshold clears across"
scripts/m9-c-adopt/da15_verdict.py:384:        "thresholds": {
scripts/m9-c-adopt/da15_verdict.py:385:            "vendi_cohens_d_le": _VENDI_D_GATE,
scripts/m9-c-adopt/da15_verdict.py:387:            "vendi_calibration_auc_ge": _VENDI_AUC_GATE,
scripts/m9-c-adopt/da15_verdict.py:388:            "burrows_reduction_pct_ge": 5.0,
scripts/m9-c-adopt/da15_verdict.py:389:            "icc_point_ge": 0.55,
scripts/m9-c-adopt/da15_verdict.py:390:            "throughput_pct_ge": 70.0,
scripts/m9-c-adopt/da15_verdict.py:391:            "note": "DA-14 thresholds, unchanged. DA-15 swaps the encoder and renames the metric.",
scripts/m9-c-adopt/da15_verdict.py:397:            "quorum_threshold": "2_of_3",
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.md:8:| single-turn pilot LoRA r=8 (PR #165) | 34.701 [34.673, 34.729] | 0.9843 [0.9795, 0.9946] | 113.723 [113.314, 114.131] |
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.md:17:  "primary_vendi_diff_point": 2.0155055489451357,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:2:  "preregistered_thresholds": {
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:6:      "vendi_cohens_d_lt": -0.5,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:24:    "primary_vendi_diff_point": 2.0155055489451357,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:69:        30.950622354467058,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:76:        "point": 108.5337029133786,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:83:        113.37006342878728,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:86:        110.428419870017,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:94:        107.24507000458404,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:99:        104.92703857084643,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:152:        "lo": 109.03637349837003,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:158:        113.37006342878728,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:165:        107.24507000458404,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:168:        104.92703857084643,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:236:        "point": 34.70096800564424,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:239:        "width": 0.05557249253320862,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:245:        34.80447098464963,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:247:        35.560105708173225,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:254:        "point": 113.72272053877083,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:257:        "width": 0.8170892706921791,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:262:        110.02554789082534,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:301:        "point": 114.60777995370626,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:302:        "lo": 113.65786098227092,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:304:        "width": 1.8998379428706471,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:308:        114.39976319570022,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:313:        111.33662708471356
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da1-matrix-v2-kant.json:320:        "agreement_lo": 0.8807947019867548,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\burrows.log:7:2026-05-16 07:55:41,070 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=0 total=100 de=51 en=36 ja=5 other=0 dropped=8 mean_burrows=113.2953
.steering/20260515-m9-c-adopt-retrain-v2-verdict\audit-real-tokenizer.log:8:2026-05-15 15:08:03,086 WARNING __main__ pre-training audit: de+en weighted mass=0.489 below soft warning threshold 0.60; continuing training but flag in train_metadata
.steering/20260515-m9-c-adopt-retrain-v2-verdict\audit-real-tokenizer.log:10:{"base_model": "Qwen/Qwen3-8B", "batch_size": 1, "db_paths": ["data\\eval\\golden\\kant_natural_run0.duckdb", "data\\eval\\golden\\kant_natural_run1.duckdb", "data\\eval\\golden\\kant_natural_run2.duckdb", "data\\eval\\golden\\kant_natural_run3.duckdb", "data\\eval\\golden\\kant_natural_run4.duckdb", "data\\eval\\golden\\kant_stimulus_run0.duckdb", "data\\eval\\golden\\kant_stimulus_run1.duckdb", "data\\eval\\golden\\kant_stimulus_run2.duckdb", "data\\eval\\golden\\kant_stimulus_run3.duckdb", "data\\eval\\golden\\kant_stimulus_run4.duckdb"], "eval_dialog_ids_n": 285, "eval_loss": null, "eval_split_size": 503, "gradient_accumulation_steps": 8, "learning_rate": 0.0002, "lora_rank": 8, "max_seq_length": 2048, "max_steps": 4000, "metadata": {"audit_de_en_mass": 0.48850351569210393, "audit_n_eff": 3886.3808333167804, "audit_top_5_pct": 0.13908401226837194, "seed": 42, "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"]}, "min_examples_threshold": 1000, "output_dir": "data\\lora\\m9-c-adopt-v2\\kant_r8_v2", "peak_vram_bytes": 0, "persona_id": "kant", "quantization": "nf4", "realised_examples": 5022, "save_steps": 500, "shard_stats": [{"path": "data\\eval\\golden\\kant_natural_run0.duckdb", "persona_examples": 501, "raw_rows": 1507}, {"path": "data\\eval\\golden\\kant_natural_run1.duckdb", "persona_examples": 500, "raw_rows": 1504}, {"path": "data\\eval\\golden\\kant_natural_run2.duckdb", "persona_examples": 500, "raw_rows": 1480}, {"path": "data\\eval\\golden\\kant_natural_run3.duckdb", "persona_examples": 500, "raw_rows": 1497}, {"path": "data\\eval\\golden\\kant_natural_run4.duckdb", "persona_examples": 501, "raw_rows": 1513}, {"path": "data\\eval\\golden\\kant_stimulus_run0.duckdb", "persona_examples": 504, "raw_rows": 852}, {"path": "data\\eval\\golden\\kant_stimulus_run1.duckdb", "persona_examples": 504, "raw_rows": 852}, {"path": "data\\eval\\golden\\kant_stimulus_run2.duckdb", "persona_examples": 504, "raw_rows": 852}, {"path": "data\\eval\\golden\\kant_stimulus_run3.duckdb", "persona_examples": 504, "raw_rows": 852}, {"path": "data\\eval\\golden\\kant_stimulus_run4.duckdb", "persona_examples": 504, "raw_rows": 852}], "synthetic_monolog_n": 500, "train_dialog_ids_n": 2562, "train_loss": null, "training_executed": false, "weight_audit_path": "data\\lora\\m9-c-adopt-v2\\kant_r8_v2\\weight-audit.json", "weighted": true}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\pilot_run1.log:3:2026-05-16 07:49:09,767 [__main__] INFO: checkpoint persona=kant tag=r8 run=1 completed=50/300 rate=0.83 focal/s eta=5.0 min
.steering/20260515-m9-c-adopt-retrain-v2-verdict\validation-v2-kant.json:23:              "count": 270
.steering/20260515-m9-c-adopt-retrain-v2-verdict\validation-v2-kant.json:68:              "count": 270
.steering/20260515-m9-c-adopt-retrain-v2-verdict\pilot_run0.log:4:2026-05-16 07:43:44,467 [__main__] INFO: checkpoint persona=kant tag=r8 run=0 completed=75/300 rate=0.75 focal/s eta=5.0 min
.steering/20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:39:2026-05-16 07:55:41,070 [__main__] INFO: shard=kant_r8v2_run1_stim.duckdb w=0 total=100 de=51 en=36 ja=5 other=0 dropped=8 mean_burrows=113.2953
.steering/20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:57:| single-turn pilot LoRA r=8 (PR #165) | 34.701 [34.673, 34.729] | 0.9843 [0.9795, 0.9946] | 113.723 [113.314, 114.131] |
.steering/20260515-m9-c-adopt-retrain-v2-verdict\phase_3_4.log:66:  "primary_vendi_diff_point": 2.0155055489451357,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\next-session-prompt-FINAL-da15-adr.md:18:retrain v2 が DA-14 thresholds で REJECT になったため、次に試す 3 案
.steering/20260515-m9-c-adopt-retrain-v2-verdict\next-session-prompt-FINAL-da15-adr.md:39:   - 期待 outcome (DA-14 thresholds 通過想定)
.steering/20260515-m9-c-adopt-retrain-v2-verdict\next-session-prompt-FINAL-da15-adr.md:54:6. `.steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json`
.steering/20260515-m9-c-adopt-retrain-v2-verdict\next-session-prompt-FINAL-da15-adr.md:55:   (DA-14 thresholds 詳細)
.steering/20260515-m9-c-adopt-retrain-v2-verdict\next-session-prompt-FINAL-da15-adr.md:79:- **HIGH-3 post-hoc threshold movement 禁止**: DA-14 thresholds は変更不可。
.steering/20260515-m9-c-adopt-retrain-v2-verdict\next-session-prompt-FINAL-da15-adr.md:80:  ADR は新しい approach の妥当性を述べるもので、threshold を緩める ADR は禁止。
.steering/20260515-m9-c-adopt-retrain-v2-verdict\requirement.md:47:- [ ] `da1-matrix-v2-kant.json` (DA-14 thresholds 適用)
.steering/20260515-m9-c-adopt-retrain-v2-verdict\requirement.md:57:- `.steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json`
.steering/20260515-m9-c-adopt-retrain-v2-verdict\tasklist.md:5:- [x] DA-14 thresholds-recalibrated.json の存在確認
.steering/20260515-m9-c-adopt-retrain-v2-verdict\design.md:52:- `da1_matrix_multiturn.py --thresholds-file <DA-14 recalibrated>` で 4 軸判定
.steering/20260515-m9-c-adopt-retrain-v2-verdict\design.md:57:- Vendi semantic Cohen's d <= -0.5 (point + CI upper < 0)
.steering/20260515-m9-c-adopt-retrain-v2-verdict\design.md:59:- ICC(A,1) >= 0.55 (point + CI lower >= 0.50)
.steering/20260515-m9-c-adopt-retrain-v2-verdict\design.md:60:- throughput >= 70%
.steering/20260515-m9-c-adopt-retrain-v2-verdict\design.md:62:**HIGH-3 禁止**: post-hoc threshold movement 禁止。ADOPT/REJECT 判定後に
.steering/20260515-m9-c-adopt-retrain-v2-verdict\design.md:63:thresholds を緩めるのは DA-15 起票が正路。
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:13:      "cohens_d": -0.1788470533504207,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:14:      "threshold_point": -0.5,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:15:      "threshold_ci": "ci_upper < 0",
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:19:      "v2_mean": 114.60777995370626,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:26:      "threshold_point": 5.0,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:27:      "threshold_ci": "ci_lower > 0",
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:33:        0.8807947019867548,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:37:      "threshold_point": 0.55,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:38:      "threshold_ci": "ci_lower >= 0.50",
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:45:      "threshold_point": 70.0,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:53:    "vendi_prior": 34.701,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:57:    "burrows_v2": 114.60777995370626,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\da14-verdict-v2-kant.json:60:  "matrix_script_note": "scripts/m9-c-adopt/da1_matrix_multiturn.py compares against MATCHED HISTORICAL Ollama baseline (DA-11 era). DA-14 mandates no-LoRA SGLang baseline. This file applies DA-14 thresholds correctly."
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-windows-cpu-fail.log:5:2026-05-15 15:09:28,128 WARNING __main__ pre-training audit: de+en weighted mass=0.489 below soft warning threshold 0.60; continuing training but flag in train_metadata
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-windows-cpu-fail.log:11:Loading checkpoint shards:  20%|##        | 1/5 [00:44<02:57, 44.40s/it]Loading checkpoint shards:  40%|####      | 2/5 [01:49<02:50, 56.70s/it]Loading checkpoint shards:  60%|######    | 3/5 [02:55<02:02, 61.05s/it]Loading checkpoint shards:  80%|########  | 4/5 [03:44<00:56, 56.19s/it]Loading checkpoint shards: 100%|##########| 5/5 [03:44<00:00, 44.94s/it]
.steering/20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:101:  - **Axis 1 (Vendi semantic Cohen's d ≤ -0.5、CI upper < 0)**: **FAIL**
.steering/20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:103:    - Cohen's d = **-0.1788** (target ≤ -0.5、correct direction but insufficient magnitude)
.steering/20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:109:  - **Axis 3 (ICC(A,1) ≥ 0.55、CI lower ≥ 0.50)**: **PASS**
.steering/20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:111:    - no-LoRA ICC(A,1) = 0.9061 (両方とも threshold を大きく超過)
.steering/20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:112:  - **Axis 4 (throughput ≥ 70%)**: **PASS**
.steering/20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:122:  - Vendi: 34.7010 → 33.1829 (-1.52、prior +1.39 wrong → v2 -0.13 correct、
.steering/20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:125:  - DA-14 thresholds は absolute magnitude を要求するため、reversal だけでは不十分
.steering/20260515-m9-c-adopt-retrain-v2-verdict\decisions.md:137:- **HIGH-3 post-hoc threshold movement 禁止**: DA-14 thresholds を緩めて
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:7:[2026-05-16 07:41:28] server_args=ServerArgs(model_path='Qwen/Qwen3-8B', tokenizer_path='Qwen/Qwen3-8B', tokenizer_mode='auto', tokenizer_worker_num=1, skip_tokenizer_init=False, load_format='auto', model_loader_extra_config='{}', trust_remote_code=False, context_length=None, is_embedding=False, enable_multimodal=None, revision=None, model_impl='auto', host='127.0.0.1', port=30000, fastapi_root_path='', grpc_mode=False, skip_server_warmup=False, warmups=None, nccl_port=None, checkpoint_engine_wait_weights_before_ready=False, ssl_keyfile=None, ssl_certfile=None, ssl_ca_certs=None, ssl_keyfile_password=None, enable_ssl_refresh=False, dtype='auto', quantization='fp8', quantization_param_path=None, kv_cache_dtype='auto', enable_fp32_lm_head=False, modelopt_quant=None, modelopt_checkpoint_restore_path=None, modelopt_checkpoint_save_path=None, modelopt_export_path=None, quantize_and_serve=False, rl_quant_profile=None, mem_fraction_static=0.85, max_running_requests=1, max_queued_requests=None, max_total_tokens=2048, chunked_prefill_size=2048, enable_dynamic_chunking=False, max_prefill_tokens=16384, prefill_max_requests=None, schedule_policy='fcfs', enable_priority_scheduling=False, disable_priority_preemption=False, default_priority_value=None, abort_on_priority_when_disabled=False, schedule_low_priority_values_first=False, priority_scheduling_preemption_threshold=10, schedule_conservativeness=1.0, page_size=1, swa_full_tokens_ratio=0.8, disable_hybrid_swa_memory=False, radix_eviction_policy='lru', enable_prefill_delayer=False, prefill_delayer_max_delay_passes=30, prefill_delayer_token_usage_low_watermark=None, prefill_delayer_forward_passes_buckets=None, prefill_delayer_wait_seconds_buckets=None, device='cuda', tp_size=1, pp_size=1, pp_max_micro_batch_size=None, pp_async_batch_depth=0, stream_interval=1, stream_response_default_include_usage=False, incremental_streaming_output=False, enable_streaming_session=False, random_seed=546829712, constrained_json_whitespace_pattern=None, constrained_json_disable_any_whitespace=False, watchdog_timeout=300, soft_watchdog_timeout=None, dist_timeout=None, download_dir=None, model_checksum=None, base_gpu_id=0, gpu_id_step=1, sleep_on_idle=False, use_ray=False, custom_sigquit_handler=None, log_level='info', log_level_http=None, log_requests=False, log_requests_level=2, log_requests_format='text', log_requests_target=None, uvicorn_access_log_exclude_prefixes=[], crash_dump_folder=None, show_time_cost=False, enable_metrics=False, enable_mfu_metrics=False, enable_metrics_for_all_schedulers=False, tokenizer_metrics_custom_labels_header='x-custom-labels', tokenizer_metrics_allowed_custom_labels=None, extra_metric_labels=None, bucket_time_to_first_token=None, bucket_inter_token_latency=None, bucket_e2e_request_latency=None, collect_tokens_histogram=False, prompt_tokens_buckets=None, generation_tokens_buckets=None, gc_warning_threshold_secs=0.0, decode_log_interval=40, enable_request_time_stats_logging=False, kv_events_config=None, enable_trace=False, otlp_traces_endpoint='localhost:4317', export_metrics_to_file=False, export_metrics_to_file_dir=None, api_key=None, admin_api_key=None, served_model_name='Qwen/Qwen3-8B', weight_version='default', chat_template=None, hf_chat_template_name=None, completion_template=None, file_storage_path='sglang_storage', enable_cache_report=False, reasoning_parser=None, tool_call_parser=None, tool_server=None, sampling_defaults='model', dp_size=1, load_balance_method='round_robin', attn_cp_size=1, moe_dp_size=1, dist_init_addr=None, nnodes=1, node_rank=0, json_model_override_args='{}', preferred_sampling_params=None, enable_lora=True, enable_lora_overlap_loading=False, max_lora_rank=8, lora_target_modules={'q_proj', 'v_proj', 'k_proj', 'o_proj'}, lora_paths=[], max_loaded_loras=1, max_loras_per_batch=1, lora_eviction_policy='lru', lora_backend='csgmv', max_lora_chunk_size=16, experts_shared_outer_loras=None, attention_backend='flashinfer', decode_attention_backend=None, prefill_attention_backend=None, sampling_backend='flashinfer', grammar_backend='xgrammar', mm_attention_backend=None, fp8_gemm_runner_backend='auto', fp4_gemm_runner_backend='auto', nsa_prefill_backend=None, nsa_decode_backend=None, disable_flashinfer_autotune=False, mamba_backend='triton', speculative_algorithm=None, speculative_draft_model_path=None, speculative_draft_model_revision=None, speculative_draft_load_format=None, speculative_num_steps=None, speculative_eagle_topk=None, speculative_num_draft_tokens=None, speculative_accept_threshold_single=1.0, speculative_accept_threshold_acc=1.0, speculative_token_map=None, speculative_attention_mode='prefill', speculative_draft_attention_backend=None, speculative_moe_runner_backend='auto', speculative_moe_a2a_backend=None, speculative_draft_model_quantization='fp8', speculative_ngram_min_bfs_breadth=1, speculative_ngram_max_bfs_breadth=10, speculative_ngram_match_type='BFS', speculative_ngram_max_trie_depth=18, speculative_ngram_capacity=10000000, enable_multi_layer_eagle=False, ep_size=1, moe_a2a_backend='none', moe_runner_backend='auto', flashinfer_mxfp4_moe_precision='default', enable_flashinfer_allreduce_fusion=False, enforce_disable_flashinfer_allreduce_fusion=False, enable_aiter_allreduce_fusion=False, deepep_mode='auto', ep_num_redundant_experts=0, ep_dispatch_algorithm=None, init_expert_location='trivial', enable_eplb=False, eplb_algorithm='auto', eplb_rebalance_num_iterations=1000, eplb_rebalance_layers_per_chunk=None, eplb_min_rebalancing_utilization_threshold=1.0, expert_distribution_recorder_mode=None, expert_distribution_recorder_buffer_size=1000, enable_expert_distribution_metrics=False, deepep_config=None, moe_dense_tp_size=None, elastic_ep_backend=None, enable_elastic_expert_backup=False, mooncake_ib_device=None, max_mamba_cache_size=None, mamba_ssm_dtype=None, mamba_full_memory_ratio=0.9, mamba_scheduler_strategy='no_buffer', mamba_track_interval=256, linear_attn_backend='triton', linear_attn_decode_backend=None, linear_attn_prefill_backend=None, enable_hierarchical_cache=False, hicache_ratio=2.0, hicache_size=0, hicache_write_policy='write_through', hicache_io_backend='kernel', hicache_mem_layout='layer_first', hicache_storage_backend=None, hicache_storage_prefetch_policy='best_effort', hicache_storage_backend_extra_config=None, enable_hisparse=False, hisparse_config=None, enable_lmcache=False, kt_weight_path=None, kt_method='AMXINT4', kt_cpuinfer=None, kt_threadpool_count=2, kt_num_gpu_experts=None, kt_max_deferred_experts_per_token=None, dllm_algorithm=None, dllm_algorithm_config=None, enable_double_sparsity=False, ds_channel_config_path=None, ds_heavy_channel_num=32, ds_heavy_token_num=256, ds_heavy_channel_type='qk', ds_sparse_decode_threshold=4096, cpu_offload_gb=0, offload_group_size=-1, offload_num_in_group=1, offload_prefetch_step=1, offload_mode='cpu', multi_item_scoring_delimiter=None, disable_radix_cache=False, cuda_graph_max_bs=8, cuda_graph_bs=[1, 2, 4, 8], disable_cuda_graph=True, disable_cuda_graph_padding=False, enable_profile_cuda_graph=False, enable_cudagraph_gc=False, enable_layerwise_nvtx_marker=False, enable_nccl_nvls=False, enable_symm_mem=False, disable_flashinfer_cutlass_moe_fp4_allgather=False, enable_tokenizer_batch_encode=False, disable_tokenizer_batch_decode=False, disable_outlines_disk_cache=False, disable_custom_all_reduce=False, enable_mscclpp=False, enable_torch_symm_mem=False, pre_warm_nccl=False, disable_overlap_schedule=False, enable_mixed_chunk=False, enable_dp_attention=False, enable_dp_lm_head=False, enable_two_batch_overlap=False, enable_single_batch_overlap=False, tbo_token_distribution_threshold=0.48, enable_torch_compile=False, disable_piecewise_cuda_graph=True, enforce_piecewise_cuda_graph=False, enable_torch_compile_debug_mode=False, torch_compile_max_bs=32, piecewise_cuda_graph_max_tokens=2048, piecewise_cuda_graph_tokens=[4, 8, 12, 16, 20, 24, 28, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 192, 208, 224, 240, 256, 288, 320, 352, 384, 416, 448, 480, 512, 576, 640, 704, 768, 832, 896, 960, 1024, 1280, 1536, 1792, 2048], piecewise_cuda_graph_compiler='eager', torchao_config='', enable_nan_detection=False, enable_p2p_check=False, triton_attention_reduce_in_fp32=False, triton_attention_num_kv_splits=8, triton_attention_split_tile_size=None, num_continuous_decode_steps=1, delete_ckpt_after_loading=False, enable_memory_saver=False, enable_weights_cpu_backup=False, enable_draft_weights_cpu_backup=False, allow_auto_truncate=False, enable_custom_logit_processor=False, flashinfer_mla_disable_ragged=False, disable_shared_experts_fusion=False, disable_chunked_prefix_cache=False, disable_fast_image_processor=False, keep_mm_feature_on_device=False, enable_return_hidden_states=False, enable_return_routed_experts=False, scheduler_recv_interval=1, numa_node=None, enable_deterministic_inference=False, rl_on_policy_target=None, enable_attn_tp_input_scattered=False, gc_threshold=None, enable_nsa_prefill_context_parallel=False, nsa_prefill_cp_mode='round-robin-split', enable_fused_qk_norm_rope=False, enable_precise_embedding_interpolation=False, enable_fused_moe_sum_all_reduce=False, enable_prefill_context_parallel=False, prefill_cp_mode='in-seq-split', enable_dynamic_batch_tokenizer=False, dynamic_batch_tokenizer_batch_size=32, dynamic_batch_tokenizer_batch_timeout=0.002, debug_tensor_dump_output_folder=None, debug_tensor_dump_layers=None, debug_tensor_dump_input_file=None, debug_tensor_dump_inject=False, disaggregation_mode='null', disaggregation_transfer_backend='mooncake', disaggregation_bootstrap_port=8998, disaggregation_ib_device=None, disaggregation_decode_enable_offload_kvcache=False, num_reserved_decode_tokens=512, disaggregation_decode_polling_interval=1, encoder_only=False, language_only=False, encoder_transfer_backend='zmq_to_scheduler', encoder_urls=[], enable_adaptive_dispatch_to_encoder=False, custom_weight_loader=[], weight_loader_disable_mmap=False, remote_instance_weight_loader_seed_instance_ip=None, remote_instance_weight_loader_seed_instance_service_port=None, remote_instance_weight_loader_send_weights_group_ports=None, remote_instance_weight_loader_backend='nccl', remote_instance_weight_loader_start_seed_via_transfer_engine=False, engine_info_bootstrap_port=6789, modelexpress_config=None, enable_pdmux=False, pdmux_config_path=None, sm_group_num=8, enable_broadcast_mm_inputs_process=False, enable_prefix_mm_cache=False, mm_enable_dp_encoder=False, mm_process_config={}, limit_mm_data_per_request=None, enable_mm_global_cache=False, decrypted_config_file=None, decrypted_draft_config_file=None, forward_hooks=None)
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:21:Multi-thread loading shards:   0% Completed | 0/5 [00:00<?, ?it/s]Multi-thread loading shards:  20% Completed | 1/5 [00:03<00:15,  3.93s/it]Multi-thread loading shards:  40% Completed | 2/5 [00:07<00:11,  3.99s/it]Multi-thread loading shards:  60% Completed | 3/5 [00:09<00:05,  2.70s/it]Multi-thread loading shards:  80% Completed | 4/5 [00:11<00:02,  2.63s/it]Multi-thread loading shards: 100% Completed | 5/5 [00:13<00:00,  2.47s/it]Multi-thread loading shards: 100% Completed | 5/5 [00:13<00:00,  2.77s/it]
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:56:[2026-05-16 07:42:08] INFO:     127.0.0.1:37270 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:76:[2026-05-16 07:42:16] Prefill batch, #new-seq: 1, #new-token: 44, #cached-token: 215, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 32.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:79:[2026-05-16 07:42:17] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 32.49, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:97:[2026-05-16 07:42:21] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 31.60, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:193:[2026-05-16 07:42:48] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 31.66, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:194:[2026-05-16 07:42:49] INFO:     127.0.0.1:54570 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:263:[2026-05-16 07:43:05] Prefill batch, #new-seq: 1, #new-token: 55, #cached-token: 214, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 70.53
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:292:[2026-05-16 07:43:13] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 32.01, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:319:[2026-05-16 07:43:21] INFO:     127.0.0.1:58700 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:372:[2026-05-16 07:43:34] INFO:     127.0.0.1:47004 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:375:[2026-05-16 07:43:34] INFO:     127.0.0.1:47010 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:377:[2026-05-16 07:43:35] INFO:     127.0.0.1:47018 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:378:[2026-05-16 07:43:35] Prefill batch, #new-seq: 1, #new-token: 41, #cached-token: 226, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 70.42
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:380:[2026-05-16 07:43:36] INFO:     127.0.0.1:47034 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:383:[2026-05-16 07:43:37] INFO:     127.0.0.1:47048 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:385:[2026-05-16 07:43:37] INFO:     127.0.0.1:47052 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:388:[2026-05-16 07:43:38] INFO:     127.0.0.1:47056 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:430:[2026-05-16 07:43:48] Prefill batch, #new-seq: 1, #new-token: 33, #cached-token: 225, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 114.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:432:[2026-05-16 07:43:48] INFO:     127.0.0.1:49170 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:455:[2026-05-16 07:43:55] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 32.46, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:458:[2026-05-16 07:43:54] INFO:     127.0.0.1:48570 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:479:[2026-05-16 07:43:58] INFO:     127.0.0.1:55570 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:501:[2026-05-16 07:44:04] Prefill batch, #new-seq: 1, #new-token: 43, #cached-token: 226, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 136.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:512:[2026-05-16 07:44:07] Decode batch, #running-req: 1, #token: 295, token usage: 0.14, cuda graph: False, gen throughput (token/s): 33.70, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:538:[2026-05-16 07:44:15] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 32.42, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:587:[2026-05-16 07:44:28] INFO:     127.0.0.1:54570 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:614:[2026-05-16 07:44:36] Prefill batch, #new-seq: 1, #new-token: 65, #cached-token: 207, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 70.10
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:634:[2026-05-16 07:44:40] Prefill batch, #new-seq: 1, #new-token: 54, #cached-token: 213, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 55.05
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:666:[2026-05-16 07:44:48] Prefill batch, #new-seq: 1, #new-token: 42, #cached-token: 225, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 85.03
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:690:[2026-05-16 07:44:55] Prefill batch, #new-seq: 1, #new-token: 48, #cached-token: 225, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 61.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:733:[2026-05-16 07:45:04] INFO:     127.0.0.1:40704 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:805:[2026-05-16 07:45:24] INFO:     127.0.0.1:56706 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:815:[2026-05-16 07:45:27] Decode batch, #running-req: 1, #token: 276, token usage: 0.13, cuda graph: False, gen throughput (token/s): 31.70, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:836:[2026-05-16 07:45:32] Prefill batch, #new-seq: 1, #new-token: 53, #cached-token: 214, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 45.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:839:[2026-05-16 07:45:33] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 32.96, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:871:[2026-05-16 07:45:42] INFO:     127.0.0.1:58370 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:875:[2026-05-16 07:45:43] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 31.60, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:893:[2026-05-16 07:45:48] INFO:     127.0.0.1:43570 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:959:[2026-05-16 07:46:03] INFO:     127.0.0.1:42708 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1001:[2026-05-16 07:46:21] INFO:     127.0.0.1:59170 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1006:[2026-05-16 07:46:22] Decode batch, #running-req: 1, #token: 285, token usage: 0.14, cuda graph: False, gen throughput (token/s): 33.70, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1046:[2026-05-16 07:46:31] Prefill batch, #new-seq: 1, #new-token: 54, #cached-token: 226, token usage: 0.14, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 105.06
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1048:[2026-05-16 07:46:31] Prefill batch, #new-seq: 1, #new-token: 52, #cached-token: 215, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 93.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1078:[2026-05-16 07:46:39] INFO:     127.0.0.1:33970 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1100:[2026-05-16 07:46:45] Prefill batch, #new-seq: 1, #new-token: 59, #cached-token: 213, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 51.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1114:[2026-05-16 07:46:49] Prefill batch, #new-seq: 1, #new-token: 45, #cached-token: 213, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 70.21
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1258:[2026-05-16 07:47:28] INFO:     127.0.0.1:52170 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1311:[2026-05-16 07:47:40] INFO:     127.0.0.1:38702 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1351:[2026-05-16 07:47:50] INFO:     127.0.0.1:35470 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1357:[2026-05-16 07:47:52] Prefill batch, #new-seq: 1, #new-token: 74, #cached-token: 213, token usage: 0.14, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 70.08
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1378:[2026-05-16 07:47:57] Prefill batch, #new-seq: 1, #new-token: 48, #cached-token: 225, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 48.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1401:[2026-05-16 07:48:03] Decode batch, #running-req: 1, #token: 291, token usage: 0.14, cuda graph: False, gen throughput (token/s): 35.00, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1479:[2026-05-16 07:48:24] Decode batch, #running-req: 1, #token: 286, token usage: 0.14, cuda graph: False, gen throughput (token/s): 35.04, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1487:[2026-05-16 07:48:27] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 33.68, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1516:[2026-05-16 07:48:34] INFO:     127.0.0.1:53270 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1539:[2026-05-16 07:48:40] INFO:     127.0.0.1:55702 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1681:[2026-05-16 07:49:15] Decode batch, #running-req: 1, #token: 292, token usage: 0.14, cuda graph: False, gen throughput (token/s): 33.70, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1682:[2026-05-16 07:49:16] INFO:     127.0.0.1:45704 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1736:[2026-05-16 07:49:31] INFO:     127.0.0.1:35704 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1757:[2026-05-16 07:49:36] Prefill batch, #new-seq: 1, #new-token: 65, #cached-token: 207, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 70.25
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1782:[2026-05-16 07:49:41] Prefill batch, #new-seq: 1, #new-token: 59, #cached-token: 213, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 52.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1807:[2026-05-16 07:49:47] Prefill batch, #new-seq: 1, #new-token: 42, #cached-token: 225, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 82.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1858:[2026-05-16 07:50:02] INFO:     127.0.0.1:33700 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1862:[2026-05-16 07:50:04] INFO:     127.0.0.1:33708 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1909:[2026-05-16 07:50:15] Prefill batch, #new-seq: 1, #new-token: 52, #cached-token: 215, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 70.41
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1915:[2026-05-16 07:50:17] Prefill batch, #new-seq: 1, #new-token: 53, #cached-token: 215, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 30.55
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1990:[2026-05-16 07:50:38] Prefill batch, #new-seq: 1, #new-token: 47, #cached-token: 225, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 65.07
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1994:[2026-05-16 07:50:39] INFO:     127.0.0.1:37006 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1997:[2026-05-16 07:50:40] INFO:     127.0.0.1:37010 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:1999:[2026-05-16 07:50:41] INFO:     127.0.0.1:37012 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2002:[2026-05-16 07:50:40] INFO:     127.0.0.1:37020 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2030:[2026-05-16 07:50:48] INFO:     127.0.0.1:56170 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2055:[2026-05-16 07:50:55] INFO:     127.0.0.1:40240 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2056:[2026-05-16 07:50:55] Prefill batch, #new-seq: 1, #new-token: 33, #cached-token: 225, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 65.79
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2057:[2026-05-16 07:50:55] Decode batch, #running-req: 1, #token: 261, token usage: 0.13, cuda graph: False, gen throughput (token/s): 31.25, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2058:[2026-05-16 07:50:55] INFO:     127.0.0.1:40254 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2059:[2026-05-16 07:50:55] Prefill batch, #new-seq: 1, #new-token: 60, #cached-token: 213, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 55.69
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2101:[2026-05-16 07:51:06] INFO:     127.0.0.1:35704 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2103:[2026-05-16 07:51:07] INFO:     127.0.0.1:35708 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2119:[2026-05-16 07:51:11] Prefill batch, #new-seq: 1, #new-token: 40, #cached-token: 226, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 75.03
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2135:[2026-05-16 07:51:13] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 32.60, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2159:[2026-05-16 07:51:20] INFO:     127.0.0.1:38770 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2252:[2026-05-16 07:51:46] Prefill batch, #new-seq: 1, #new-token: 46, #cached-token: 213, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 42.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2253:[2026-05-16 07:51:46] INFO:     127.0.0.1:59702 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2255:[2026-05-16 07:51:46] INFO:     127.0.0.1:59706 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2261:[2026-05-16 07:51:47] Prefill batch, #new-seq: 1, #new-token: 33, #cached-token: 225, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 70.90
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2262:[2026-05-16 07:51:48] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 31.41, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2272:[2026-05-16 07:51:50] Prefill batch, #new-seq: 1, #new-token: 74, #cached-token: 213, token usage: 0.14, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 52.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2283:[2026-05-16 07:51:54] Prefill batch, #new-seq: 1, #new-token: 33, #cached-token: 225, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 70.25
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2307:[2026-05-16 07:51:59] Prefill batch, #new-seq: 1, #new-token: 35, #cached-token: 214, token usage: 0.12, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 170.90
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2313:[2026-05-16 07:52:01] INFO:     127.0.0.1:58170 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2346:[2026-05-16 07:52:14] INFO:     127.0.0.1:58270 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2356:[2026-05-16 07:52:15] INFO:     127.0.0.1:49270 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2386:[2026-05-16 07:52:23] Prefill batch, #new-seq: 1, #new-token: 53, #cached-token: 215, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 61.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2399:[2026-05-16 07:52:27] Prefill batch, #new-seq: 1, #new-token: 48, #cached-token: 226, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 54.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2426:[2026-05-16 07:52:34] INFO:     127.0.0.1:35370 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2440:[2026-05-16 07:52:39] INFO:     127.0.0.1:53070 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2511:[2026-05-16 07:52:57] INFO:     127.0.0.1:38970 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2529:[2026-05-16 07:53:01] Prefill batch, #new-seq: 1, #new-token: 37, #cached-token: 214, token usage: 0.12, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 230.55
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2562:[2026-05-16 07:53:10] INFO:     127.0.0.1:60970 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2571:[2026-05-16 07:53:12] INFO:     127.0.0.1:32770 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2597:[2026-05-16 07:53:18] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 32.21, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2607:[2026-05-16 07:53:21] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 32.21, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2610:[2026-05-16 07:53:22] Decode batch, #running-req: 1, #token: 270, token usage: 0.13, cuda graph: False, gen throughput (token/s): 33.30, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2621:[2026-05-16 07:53:25] INFO:     127.0.0.1:60708 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2644:[2026-05-16 07:53:31] INFO:     127.0.0.1:60770 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2673:[2026-05-16 07:53:39] INFO:     127.0.0.1:38170 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2712:[2026-05-16 07:53:48] Prefill batch, #new-seq: 1, #new-token: 46, #cached-token: 213, token usage: 0.13, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 70.23
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2804:[2026-05-16 07:54:10] INFO:     127.0.0.1:45170 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2813:[2026-05-16 07:54:11] Prefill batch, #new-seq: 1, #new-token: 19, #cached-token: 56, token usage: 0.04, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 195.05
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2815:[2026-05-16 07:54:11] Prefill batch, #new-seq: 1, #new-token: 19, #cached-token: 57, token usage: 0.04, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 193.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2833:[2026-05-16 07:54:12] INFO:     127.0.0.1:45270 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2867:[2026-05-16 07:54:13] INFO:     127.0.0.1:53170 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2877:[2026-05-16 07:54:14] Prefill batch, #new-seq: 1, #new-token: 19, #cached-token: 56, token usage: 0.04, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 205.01
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2959:[2026-05-16 07:54:18] Prefill batch, #new-seq: 1, #new-token: 1, #cached-token: 74, token usage: 0.04, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 10.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:2988:[2026-05-16 07:54:19] INFO:     127.0.0.1:53700 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3116:[2026-05-16 07:54:23] INFO:     127.0.0.1:49370 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3189:[2026-05-16 07:54:27] INFO:     127.0.0.1:49706 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3204:[2026-05-16 07:54:28] INFO:     127.0.0.1:49770 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3241:[2026-05-16 07:54:29] INFO:     127.0.0.1:49970 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3280:[2026-05-16 07:54:31] INFO:     127.0.0.1:47030 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3282:[2026-05-16 07:54:31] INFO:     127.0.0.1:47038 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3284:[2026-05-16 07:54:31] INFO:     127.0.0.1:47048 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3286:[2026-05-16 07:54:31] INFO:     127.0.0.1:47050 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3288:[2026-05-16 07:54:31] INFO:     127.0.0.1:47056 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3290:[2026-05-16 07:54:31] INFO:     127.0.0.1:47064 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3292:[2026-05-16 07:54:32] INFO:     127.0.0.1:47072 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3294:[2026-05-16 07:54:32] INFO:     127.0.0.1:47088 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3355:[2026-05-16 07:54:34] INFO:     127.0.0.1:47370 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3401:[2026-05-16 07:54:36] Decode batch, #running-req: 1, #token: 0, token usage: 0.00, cuda graph: False, gen throughput (token/s): 21.70, #queue-req: 0
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3402:[2026-05-16 07:54:37] Prefill batch, #new-seq: 1, #new-token: 1, #cached-token: 74, token usage: 0.04, #running-req: 0, #queue-req: 0, cuda graph: False, input throughput (token/s): 10.70
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3433:[2026-05-16 07:54:38] INFO:     127.0.0.1:47708 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\sglang.log:3466:[2026-05-16 07:54:39] INFO:     127.0.0.1:47870 - "POST /v1/chat/completions HTTP/1.1" 200 OK
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-vendi-semantic.json:124:      "spectrum_entropy": 3.396795074503704
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:10:  "lang_confidence_threshold": 0.85,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:14:    "de": 570,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:26:    "lo": 109.03637349837003,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:48:      "mean_burrows": 113.37006342878728,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:57:        96.13137087805714,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:64:        112.1435701756818,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:66:        96.69676397083845,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:68:        79.31135160970251,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:79:        117.42475870360573,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:84:        103.25964019170755
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:109:        120.87370519046101,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:130:        102.63707316652255,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:152:        137.52060355312125,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:160:        130.76705618024778,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:167:        145.05703744636344,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:180:        133.0703954115442,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:181:        112.1435701756818,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:184:        137.36247041497543,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:203:        96.79706978162726,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:204:        115.09777379015247,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:209:        104.43706098740434,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:230:        113.76706980835418,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:234:        94.25393106552036,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:259:        97.16870679507855,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:261:        112.1435701756818,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:263:        137.36247041497543,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:273:        110.59706096962222,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:280:        163.7970181282387,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:287:        134.99745705617423,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:290:        87.70439145355498,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:291:        97.16870679507855
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:308:        108.51662254470288,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:326:        104.43706098740434,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:329:        134.99745705617423,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:336:        137.36247041497543,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:352:        105.09403835386918,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:367:        112.1435701756818,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:379:        85.3526153977052,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:399:      "mean_burrows": 107.24507000458404,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:401:        102.63707316652255,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:413:        124.98417987050861,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:423:        130.76705618024778,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:430:        106.07357047386034,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:473:        107.02557487188348,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:490:        120.87370519046101,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:505:        145.05703744636344,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:554:      "mean_burrows": 104.92703857084643,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:568:        121.92747097314694,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:571:        103.70488360515034,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:612:        112.1435701756818,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:622:        109.07761681637066,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:687:        92.55701644692851,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:713:        104.43706098740434,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:720:        112.1435701756818,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:721:        112.1435701756818,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:723:        137.36247041497543,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:724:        120.87370519046101,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:725:        150.36897037877327,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:734:        117.05929453117707,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:741:        160.74140705561751,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:765:        112.1435701756818,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-baseline-matched-kant-burrows.json:783:        115.09777379015247,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:18:    "icc_agreement_average": 0.984344422700587,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-r8.json:19:    "icc_agreement_lower_ci": 0.8807947019867548,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:12:2026-05-15 15:19:36,148 WARNING __main__ pre-training audit: de+en weighted mass=0.489 below soft warning threshold 0.60; continuing training but flag in train_metadata
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:18:2026-05-15 15:19:36,707 INFO httpx HTTP Request: HEAD https://huggingface.co/api/resolve-cache/models/Qwen/Qwen3-8B/b968826d9c46dd6066d109eabc6255188de91218/tokenizer_config.json "HTTP/1.1 200 OK"
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:27:Loading weights:   0%|          | 0/399 [00:00<?, ?it/s]Loading weights:   0%|          | 1/399 [00:01<09:41,  1.46s/it]Loading weights:   1%|          | 2/399 [00:02<07:31,  1.14s/it]Loading weights:   1%|          | 4/399 [00:03<04:06,  1.60it/s]Loading weights:   1%|▏         | 5/399 [00:03<04:09,  1.58it/s]Loading weights:   2%|▏         | 6/399 [00:04<04:31,  1.44it/s]Loading weights:   2%|▏         | 9/399 [00:05<02:56,  2.21it/s]Loading weights:   3%|▎         | 10/399 [00:06<03:54,  1.66it/s]Loading weights:   3%|▎         | 12/399 [00:10<06:54,  1.07s/it]Loading weights:   3%|▎         | 13/399 [00:13<10:32,  1.64s/it]Loading weights:   4%|▍         | 15/399 [00:23<17:34,  2.75s/it]Loading weights:   4%|▍         | 16/399 [00:28<21:24,  3.35s/it]Loading weights:   4%|▍         | 17/399 [00:41<34:54,  5.48s/it]Loading weights:   5%|▌         | 20/399 [00:54<31:11,  4.94s/it]Loading weights:   5%|▌         | 21/399 [01:25<1:02:43,  9.96s/it]Loading weights:   6%|▌         | 23/399 [01:48<1:05:51, 10.51s/it]Loading weights:  23%|██▎       | 90/399 [01:48<03:01,  1.70it/s]  Loading weights:  46%|████▋     | 185/399 [01:48<00:43,  4.95it/s]Loading weights:  72%|███████▏  | 287/399 [01:48<00:11,  9.88it/s]Loading weights:  98%|█████████▊| 391/399 [01:48<00:00, 16.99it/s]Loading weights: 100%|██████████| 399/399 [01:48<00:00,  3.67it/s]
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:34:Map:   0%|          | 0/5019 [00:00<?, ? examples/s]Map:  20%|█▉        | 1000/5019 [00:00<00:00, 5380.83 examples/s]Map:  40%|███▉      | 2000/5019 [00:00<00:00, 5822.16 examples/s]Map:  80%|███████▉  | 4000/5019 [00:00<00:00, 7676.47 examples/s]Map: 100%|█████████▉| 5000/5019 [00:00<00:00, 8070.17 examples/s]Map: 100%|██████████| 5019/5019 [00:00<00:00, 7318.75 examples/s]
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:37:  0%|          | 0/4000 [00:00<?, ?it/s]  0%|          | 1/4000 [00:33<37:07:04, 33.41s/it]  0%|          | 2/4000 [00:52<27:29:26, 24.75s/it]  0%|          | 3/4000 [01:06<22:11:39, 19.99s/it]  0%|          | 4/4000 [01:20<19:44:17, 17.78s/it]  0%|          | 5/4000 [01:33<17:32:37, 15.81s/it]  0%|          | 6/4000 [01:47<16:59:57, 15.32s/it]  0%|          | 7/4000 [01:59<15:56:05, 14.37s/it]  0%|          | 8/4000 [02:14<16:01:47, 14.46s/it]  0%|          | 9/4000 [02:29<16:08:54, 14.57s/it]  0%|          | 10/4000 [02:41<15:22:52, 13.88s/it]                                                      0%|          | 10/4000 [02:41<15:22:52, 13.88s/it]  0%|          | 11/4000 [02:54<14:51:52, 13.41s/it]  0%|          | 12/4000 [03:08<15:22:03, 13.87s/it]  0%|          | 13/4000 [03:23<15:31:35, 14.02s/it]  0%|          | 14/4000 [03:35<14:58:40, 13.53s/it]  0%|          | 15/4000 [03:50<15:15:17, 13.78s/it]  0%|          | 16/4000 [04:02<14:49:07, 13.39s/it]  0%|          | 17/4000 [04:17<15:11:34, 13.73s/it]  0%|          | 18/4000 [04:29<14:45:28, 13.34s/it]  0%|          | 19/4000 [04:43<15:04:53, 13.64s/it]  0%|          | 20/4000 [04:56<14:43:12, 13.31s/it]                                                      0%|          | 20/4000 [04:56<14:43:12, 13.31s/it]  1%|          | 21/4000 [05:08<14:23:32, 13.02s/it]  1%|          | 22/4000 [05:22<14:42:19, 13.31s/it]  1%|          | 23/4000 [05:36<14:59:42, 13.57s/it]  1%|          | 24/4000 [05:49<14:36:14, 13.22s/it]  1%|          | 25/4000 [06:01<14:21:59, 13.01s/it]  1%|          | 26/4000 [06:16<14:55:32, 13.52s/it]  1%|          | 27/4000 [06:30<15:09:03, 13.73s/it]  1%|          | 28/4000 [06:43<14:47:09, 13.40s/it]  1%|          | 29/4000 [06:57<15:02:54, 13.64s/it]  1%|          | 30/4000 [07:12<15:20:47, 13.92s/it]                                                      1%|          | 30/4000 [07:12<15:20:47, 13.92s/it]  1%|          | 31/4000 [07:24<14:51:26, 13.48s/it]  1%|          | 32/4000 [07:36<14:28:04, 13.13s/it]  1%|          | 33/4000 [07:51<14:53:37, 13.52s/it]  1%|          | 34/4000 [08:05<15:12:08, 13.80s/it]  1%|          | 35/4000 [08:17<14:39:13, 13.30s/it]  1%|          | 36/4000 [08:32<15:04:09, 13.69s/it]  1%|          | 37/4000 [08:45<14:41:32, 13.35s/it]  1%|          | 38/4000 [08:56<14:08:09, 12.84s/it]  1%|          | 39/4000 [09:11<14:44:07, 13.39s/it]  1%|          | 40/4000 [09:23<14:21:21, 13.05s/it]                                                      1%|          | 40/4000 [09:23<14:21:21, 13.05s/it]  1%|          | 41/4000 [09:38<14:53:21, 13.54s/it]  1%|          | 42/4000 [09:51<14:38:52, 13.32s/it]  1%|          | 43/4000 [10:05<14:57:01, 13.60s/it]  1%|          | 44/4000 [10:18<14:41:55, 13.38s/it]  1%|          | 45/4000 [10:32<15:05:09, 13.73s/it]  1%|          | 46/4000 [10:46<15:12:11, 13.84s/it]  1%|          | 47/4000 [10:59<14:41:25, 13.38s/it]  1%|          | 48/4000 [11:14<15:08:03, 13.79s/it]  1%|          | 49/4000 [11:26<14:45:32, 13.45s/it]  1%|▏         | 50/4000 [11:39<14:29:57, 13.21s/it]                                                      1%|▏         | 50/4000 [11:39<14:29:57, 13.21s/it]  1%|▏         | 51/4000 [11:53<14:50:37, 13.53s/it]  1%|▏         | 52/4000 [12:06<14:37:42, 13.34s/it]  1%|▏         | 53/4000 [12:21<15:03:14, 13.73s/it]  1%|▏         | 54/4000 [12:33<14:33:30, 13.28s/it]  1%|▏         | 55/4000 [12:47<14:51:17, 13.56s/it]  1%|▏         | 56/4000 [12:59<14:25:21, 13.16s/it]  1%|▏         | 57/4000 [13:14<14:50:35, 13.55s/it]  1%|▏         | 58/4000 [13:26<14:30:41, 13.25s/it]  1%|▏         | 59/4000 [13:41<15:02:20, 13.74s/it]  2%|▏         | 60/4000 [13:54<14:34:14, 13.31s/it]                                                      2%|▏         | 60/4000 [13:54<14:34:14, 13.31s/it]  2%|▏         | 61/4000 [14:08<14:58:59, 13.69s/it]  2%|▏         | 62/4000 [14:21<14:38:36, 13.39s/it]  2%|▏         | 63/4000 [14:35<14:56:15, 13.66s/it]  2%|▏         | 64/4000 [14:48<14:35:38, 13.35s/it]  2%|▏         | 65/4000 [15:02<14:47:32, 13.53s/it]  2%|▏         | 66/4000 [15:14<14:28:12, 13.24s/it]  2%|▏         | 67/4000 [15:29<14:51:13, 13.60s/it]  2%|▏         | 68/4000 [15:43<15:02:44, 13.78s/it]  2%|▏         | 69/4000 [15:55<14:40:29, 13.44s/it]  2%|▏         | 70/4000 [16:10<14:59:23, 13.73s/it]                                                      2%|▏         | 70/4000 [16:10<14:59:23, 13.73s/it]  2%|▏         | 71/4000 [16:22<14:31:05, 13.30s/it]  2%|▏         | 72/4000 [16:37<14:51:35, 13.62s/it]  2%|▏         | 73/4000 [16:49<14:31:03, 13.31s/it]  2%|▏         | 74/4000 [17:04<14:53:24, 13.65s/it]  2%|▏         | 75/4000 [17:16<14:37:52, 13.42s/it]  2%|▏         | 76/4000 [17:31<14:55:10, 13.69s/it]  2%|▏         | 77/4000 [17:43<14:29:45, 13.30s/it]  2%|▏         | 78/4000 [17:58<14:57:04, 13.72s/it]  2%|▏         | 79/4000 [18:12<15:09:04, 13.91s/it]  2%|▏         | 80/4000 [18:25<14:40:46, 13.48s/it]                                                      2%|▏         | 80/4000 [18:25<14:40:46, 13.48s/it]  2%|▏         | 81/4000 [18:39<14:57:48, 13.75s/it]  2%|▏         | 82/4000 [18:52<14:36:13, 13.42s/it]  2%|▏         | 83/4000 [19:06<14:54:54, 13.71s/it]  2%|▏         | 84/4000 [19:19<14:33:17, 13.38s/it]  2%|▏         | 85/4000 [19:33<14:54:19, 13.71s/it]  2%|▏         | 86/4000 [19:48<15:06:15, 13.89s/it]  2%|▏         | 87/4000 [20:00<14:41:42, 13.52s/it]  2%|▏         | 88/4000 [20:14<14:56:05, 13.74s/it]  2%|▏         | 89/4000 [20:27<14:37:49, 13.47s/it]  2%|▏         | 90/4000 [20:41<14:45:39, 13.59s/it]                                                      2%|▏         | 90/4000 [20:41<14:45:39, 13.59s/it]  2%|▏         | 91/4000 [20:54<14:30:37, 13.36s/it]  2%|▏         | 92/4000 [21:08<14:49:25, 13.66s/it]  2%|▏         | 93/4000 [21:21<14:22:40, 13.25s/it]  2%|▏         | 94/4000 [21:35<14:52:28, 13.71s/it]  2%|▏         | 95/4000 [21:48<14:36:20, 13.46s/it]  2%|▏         | 96/4000 [22:03<14:51:22, 13.70s/it]  2%|▏         | 97/4000 [22:17<15:06:34, 13.94s/it]  2%|▏         | 98/4000 [22:29<14:27:49, 13.34s/it]  2%|▏         | 99/4000 [22:44<14:55:46, 13.78s/it]  2%|▎         | 100/4000 [22:56<14:27:44, 13.35s/it]                                                       2%|▎         | 100/4000 [22:56<14:27:44, 13.35s/it]  3%|▎         | 101/4000 [23:09<14:13:08, 13.13s/it]  3%|▎         | 102/4000 [23:23<14:42:49, 13.59s/it]  3%|▎         | 103/4000 [23:38<15:03:43, 13.91s/it]  3%|▎         | 104/4000 [23:50<14:33:38, 13.45s/it]  3%|▎         | 105/4000 [24:05<14:54:38, 13.78s/it]  3%|▎         | 106/4000 [24:18<14:33:58, 13.47s/it]  3%|▎         | 107/4000 [24:32<14:47:31, 13.68s/it]  3%|▎         | 108/4000 [24:45<14:26:07, 13.35s/it]  3%|▎         | 109/4000 [24:57<14:03:55, 13.01s/it]  3%|▎         | 110/4000 [25:11<14:37:21, 13.53s/it]                                                       3%|▎         | 110/4000 [25:11<14:37:21, 13.53s/it]  3%|▎         | 111/4000 [25:24<14:09:01, 13.10s/it]  3%|▎         | 112/4000 [25:38<14:33:44, 13.48s/it]  3%|▎         | 113/4000 [25:53<14:56:20, 13.84s/it]  3%|▎         | 114/4000 [26:05<14:32:02, 13.46s/it]  3%|▎         | 115/4000 [26:20<14:52:43, 13.79s/it]  3%|▎         | 116/4000 [26:34<15:05:23, 13.99s/it]  3%|▎         | 117/4000 [26:47<14:37:23, 13.56s/it]  3%|▎         | 118/4000 [27:01<14:55:05, 13.83s/it]  3%|▎         | 119/4000 [27:14<14:36:58, 13.56s/it]  3%|▎         | 120/4000 [27:27<14:15:50, 13.23s/it]                                                       3%|▎         | 120/4000 [27:27<14:15:50, 13.23s/it]  3%|▎         | 121/4000 [27:41<14:44:49, 13.69s/it]  3%|▎         | 122/4000 [27:56<15:02:07, 13.96s/it]  3%|▎         | 123/4000 [28:09<14:37:25, 13.58s/it]  3%|▎         | 124/4000 [28:23<14:52:19, 13.81s/it]  3%|▎         | 125/4000 [28:36<14:31:17, 13.49s/it]  3%|▎         | 126/4000 [28:50<14:54:22, 13.85s/it]  3%|▎         | 127/4000 [29:03<14:33:51, 13.54s/it]  3%|▎         | 128/4000 [29:18<14:51:14, 13.81s/it]  3%|▎         | 129/4000 [29:30<14:16:02, 13.27s/it]  3%|▎         | 130/4000 [29:44<14:34:18, 13.56s/it]                                                       3%|▎         | 130/4000 [29:44<14:34:18, 13.56s/it]  3%|▎         | 131/4000 [29:57<14:15:08, 13.26s/it]  3%|▎         | 132/4000 [30:11<14:37:49, 13.62s/it]  3%|▎         | 133/4000 [30:26<14:57:32, 13.93s/it]  3%|▎         | 134/4000 [30:38<14:32:48, 13.55s/it]  3%|▎         | 135/4000 [30:53<14:54:44, 13.89s/it]  3%|▎         | 136/4000 [31:06<14:35:26, 13.59s/it]  3%|▎         | 137/4000 [31:20<14:52:33, 13.86s/it]  3%|▎         | 138/4000 [31:33<14:27:34, 13.48s/it]  3%|▎         | 139/4000 [31:48<14:48:39, 13.81s/it]  4%|▎         | 140/4000 [32:00<14:27:43, 13.49s/it]                                                       4%|▎         | 140/4000 [32:00<14:27:43, 13.49s/it]  4%|▎         | 141/4000 [32:15<14:44:11, 13.75s/it]  4%|▎         | 142/4000 [32:27<14:16:58, 13.33s/it]  4%|▎         | 143/4000 [32:42<14:43:30, 13.74s/it]  4%|▎         | 144/4000 [32:56<14:54:32, 13.92s/it]  4%|▎         | 145/4000 [33:08<14:25:28, 13.47s/it]  4%|▎         | 146/4000 [33:21<14:10:23, 13.24s/it]  4%|▎         | 147/4000 [33:35<14:28:19, 13.52s/it]  4%|▎         | 148/4000 [33:48<14:12:14, 13.27s/it]  4%|▎         | 149/4000 [34:02<14:34:11, 13.62s/it]  4%|▍         | 150/4000 [34:15<14:11:58, 13.28s/it]                                                       4%|▍         | 150/4000 [34:15<14:11:58, 13.28s/it]  4%|▍         | 151/4000 [34:30<14:37:48, 13.68s/it]  4%|▍         | 152/4000 [34:42<14:21:26, 13.43s/it]  4%|▍         | 153/4000 [34:56<14:32:43, 13.61s/it]  4%|▍         | 154/4000 [35:09<14:09:47, 13.26s/it]  4%|▍         | 155/4000 [35:24<14:37:57, 13.70s/it]  4%|▍         | 156/4000 [35:36<14:15:27, 13.35s/it]  4%|▍         | 157/4000 [35:51<14:41:33, 13.76s/it]  4%|▍         | 158/4000 [36:04<14:24:48, 13.51s/it]  4%|▍         | 159/4000 [36:18<14:48:08, 13.87s/it]  4%|▍         | 160/4000 [36:31<14:26:28, 13.54s/it]                                                       4%|▍         | 160/4000 [36:31<14:26:28, 13.54s/it]  4%|▍         | 161/4000 [36:46<14:42:14, 13.79s/it]  4%|▍         | 162/4000 [36:58<14:24:15, 13.51s/it]  4%|▍         | 163/4000 [37:13<14:42:49, 13.80s/it]  4%|▍         | 164/4000 [37:26<14:24:42, 13.53s/it]  4%|▍         | 165/4000 [37:40<14:38:21, 13.74s/it]  4%|▍         | 166/4000 [37:53<14:16:52, 13.41s/it]  4%|▍         | 167/4000 [38:07<14:35:52, 13.71s/it]  4%|▍         | 168/4000 [38:20<14:20:22, 13.47s/it]  4%|▍         | 169/4000 [38:35<14:44:45, 13.86s/it]  4%|▍         | 170/4000 [38:49<14:59:26, 14.09s/it]                                                       4%|▍         | 170/4000 [38:49<14:59:26, 14.09s/it]  4%|▍         | 171/4000 [39:02<14:33:06, 13.68s/it]  4%|▍         | 172/4000 [39:16<14:44:06, 13.86s/it]  4%|▍         | 173/4000 [39:29<14:26:44, 13.59s/it]  4%|▍         | 174/4000 [39:44<14:46:01, 13.89s/it]  4%|▍         | 175/4000 [39:56<14:16:47, 13.44s/it]  4%|▍         | 176/4000 [40:11<14:47:13, 13.92s/it]  4%|▍         | 177/4000 [40:26<15:05:02, 14.20s/it]  4%|▍         | 178/4000 [40:39<14:29:31, 13.65s/it]  4%|▍         | 179/4000 [40:51<14:11:19, 13.37s/it]  4%|▍         | 180/4000 [41:06<14:34:44, 13.74s/it]                                                       4%|▍         | 180/4000 [41:06<14:34:44, 13.74s/it]  5%|▍         | 181/4000 [41:20<14:46:09, 13.92s/it]  5%|▍         | 182/4000 [41:33<14:18:08, 13.49s/it]  5%|▍         | 183/4000 [41:47<14:33:48, 13.74s/it]  5%|▍         | 184/4000 [42:00<14:19:49, 13.52s/it]  5%|▍         | 185/4000 [42:14<14:35:04, 13.76s/it]  5%|▍         | 186/4000 [42:27<14:16:57, 13.48s/it]  5%|▍         | 187/4000 [42:42<14:36:25, 13.79s/it]  5%|▍         | 188/4000 [42:54<14:07:33, 13.34s/it]  5%|▍         | 189/4000 [43:08<14:15:08, 13.46s/it]  5%|▍         | 190/4000 [43:20<13:58:28, 13.20s/it]                                                       5%|▍         | 190/4000 [43:20<13:58:28, 13.20s/it]  5%|▍         | 191/4000 [43:35<14:21:11, 13.57s/it]  5%|▍         | 192/4000 [43:47<14:01:12, 13.25s/it]  5%|▍         | 193/4000 [44:02<14:23:02, 13.60s/it]  5%|▍         | 194/4000 [44:14<14:03:12, 13.29s/it]  5%|▍         | 195/4000 [44:29<14:34:35, 13.79s/it]  5%|▍         | 196/4000 [44:42<14:11:53, 13.44s/it]  5%|▍         | 197/4000 [44:56<14:21:26, 13.59s/it]  5%|▍         | 198/4000 [45:10<14:36:08, 13.83s/it]  5%|▍         | 199/4000 [45:23<14:15:07, 13.50s/it]  5%|▌         | 200/4000 [45:37<14:29:02, 13.72s/it]                                                       5%|▌         | 200/4000 [45:37<14:29:02, 13.72s/it]  5%|▌         | 201/4000 [45:50<14:12:14, 13.46s/it]  5%|▌         | 202/4000 [46:04<14:24:26, 13.66s/it]  5%|▌         | 203/4000 [46:17<14:02:33, 13.31s/it]  5%|▌         | 204/4000 [46:32<14:33:49, 13.81s/it]  5%|▌         | 205/4000 [46:44<14:08:15, 13.41s/it]  5%|▌         | 206/4000 [46:58<14:20:34, 13.61s/it]  5%|▌         | 207/4000 [47:11<14:03:33, 13.34s/it]  5%|▌         | 208/4000 [47:25<14:24:19, 13.68s/it]  5%|▌         | 209/4000 [47:38<14:01:12, 13.31s/it]  5%|▌         | 210/4000 [47:53<14:27:10, 13.73s/it]                                                       5%|▌         | 210/4000 [47:53<14:27:10, 13.73s/it]  5%|▌         | 211/4000 [48:07<14:38:13, 13.91s/it]  5%|▌         | 212/4000 [48:20<14:16:45, 13.57s/it]  5%|▌         | 213/4000 [48:34<14:27:37, 13.75s/it]  5%|▌         | 214/4000 [48:46<14:06:14, 13.41s/it]  5%|▌         | 215/4000 [49:01<14:26:43, 13.74s/it]  5%|▌         | 216/4000 [49:13<13:59:08, 13.31s/it]  5%|▌         | 217/4000 [49:28<14:28:31, 13.78s/it]  5%|▌         | 218/4000 [49:41<14:10:38, 13.50s/it]  5%|▌         | 219/4000 [49:55<14:25:58, 13.74s/it]  6%|▌         | 220/4000 [50:08<14:04:59, 13.41s/it]                                                       6%|▌         | 220/4000 [50:08<14:04:59, 13.41s/it]  6%|▌         | 221/4000 [50:23<14:34:49, 13.89s/it]  6%|▌         | 222/4000 [50:37<14:41:57, 14.01s/it]  6%|▌         | 223/4000 [50:50<14:17:32, 13.62s/it]  6%|▌         | 224/4000 [51:04<14:32:24, 13.86s/it]  6%|▌         | 225/4000 [51:17<14:03:07, 13.40s/it]  6%|▌         | 226/4000 [51:31<14:26:42, 13.78s/it]  6%|▌         | 227/4000 [51:44<14:04:52, 13.44s/it]  6%|▌         | 228/4000 [51:59<14:30:46, 13.85s/it]  6%|▌         | 229/4000 [52:13<14:41:45, 14.03s/it]  6%|▌         | 230/4000 [52:26<14:24:37, 13.76s/it]                                                       6%|▌         | 230/4000 [52:26<14:24:37, 13.76s/it]  6%|▌         | 231/4000 [52:39<14:03:31, 13.43s/it]  6%|▌         | 232/4000 [52:54<14:27:06, 13.81s/it]  6%|▌         | 233/4000 [53:06<13:57:29, 13.34s/it]  6%|▌         | 234/4000 [53:20<14:14:46, 13.62s/it]  6%|▌         | 235/4000 [53:33<13:55:59, 13.32s/it]  6%|▌         | 236/4000 [53:47<14:20:27, 13.72s/it]  6%|▌         | 237/4000 [54:00<13:59:50, 13.39s/it]  6%|▌         | 238/4000 [54:14<14:16:07, 13.65s/it]  6%|▌         | 239/4000 [54:27<14:04:35, 13.47s/it]  6%|▌         | 240/4000 [54:42<14:25:48, 13.82s/it]                                                       6%|▌         | 240/4000 [54:42<14:25:48, 13.82s/it]  6%|▌         | 241/4000 [54:54<13:57:48, 13.37s/it]  6%|▌         | 242/4000 [55:09<14:21:34, 13.76s/it]  6%|▌         | 243/4000 [55:22<13:59:28, 13.41s/it]  6%|▌         | 244/4000 [55:36<14:23:46, 13.80s/it]  6%|▌         | 245/4000 [55:49<14:00:57, 13.44s/it]  6%|▌         | 246/4000 [56:03<14:14:25, 13.66s/it]  6%|▌         | 247/4000 [56:16<14:01:00, 13.45s/it]  6%|▌         | 248/4000 [56:29<13:47:50, 13.24s/it]  6%|▌         | 249/4000 [56:43<14:12:46, 13.64s/it]  6%|▋         | 250/4000 [56:56<13:54:34, 13.35s/it]                                                       6%|▋         | 250/4000 [56:56<13:54:34, 13.35s/it]  6%|▋         | 251/4000 [57:11<14:18:27, 13.74s/it]  6%|▋         | 252/4000 [57:23<13:54:50, 13.36s/it]  6%|▋         | 253/4000 [57:38<14:15:47, 13.70s/it]  6%|▋         | 254/4000 [57:52<14:31:50, 13.96s/it]  6%|▋         | 255/4000 [58:05<14:10:20, 13.62s/it]  6%|▋         | 256/4000 [58:18<13:49:57, 13.30s/it]  6%|▋         | 257/4000 [58:32<14:16:35, 13.73s/it]  6%|▋         | 258/4000 [58:47<14:34:01, 14.01s/it]  6%|▋         | 259/4000 [59:00<14:10:02, 13.63s/it]  6%|▋         | 260/4000 [59:14<14:28:56, 13.94s/it]                                                       6%|▋         | 260/4000 [59:14<14:28:56, 13.94s/it]  7%|▋         | 261/4000 [59:27<14:01:49, 13.51s/it]  7%|▋         | 262/4000 [59:42<14:29:06, 13.95s/it]  7%|▋         | 263/4000 [59:55<14:08:43, 13.63s/it]  7%|▋         | 264/4000 [1:00:09<14:22:35, 13.85s/it]  7%|▋         | 265/4000 [1:00:22<14:06:31, 13.60s/it]  7%|▋         | 266/4000 [1:00:37<14:19:25, 13.81s/it]  7%|▋         | 267/4000 [1:00:49<14:00:32, 13.51s/it]  7%|▋         | 268/4000 [1:01:04<14:18:07, 13.80s/it]  7%|▋         | 269/4000 [1:01:16<13:51:37, 13.37s/it]  7%|▋         | 270/4000 [1:01:31<14:19:01, 13.82s/it]                                                         7%|▋         | 270/4000 [1:01:31<14:19:01, 13.82s/it]  7%|▋         | 271/4000 [1:01:44<13:57:40, 13.48s/it]  7%|▋         | 272/4000 [1:01:59<14:23:38, 13.90s/it]  7%|▋         | 273/4000 [1:02:11<14:04:32, 13.60s/it]  7%|▋         | 274/4000 [1:02:26<14:21:15, 13.87s/it]  7%|▋         | 275/4000 [1:02:39<13:56:51, 13.48s/it]  7%|▋         | 276/4000 [1:02:53<14:18:06, 13.83s/it]  7%|▋         | 277/4000 [1:03:06<13:56:05, 13.47s/it]  7%|▋         | 278/4000 [1:03:20<14:15:15, 13.79s/it]  7%|▋         | 279/4000 [1:03:33<13:58:35, 13.52s/it]  7%|▋         | 280/4000 [1:03:48<14:17:26, 13.83s/it]                                                         7%|▋         | 280/4000 [1:03:48<14:17:26, 13.83s/it]  7%|▋         | 281/4000 [1:04:00<13:55:43, 13.48s/it]  7%|▋         | 282/4000 [1:04:15<14:13:45, 13.78s/it]  7%|▋         | 283/4000 [1:04:27<13:46:06, 13.33s/it]  7%|▋         | 284/4000 [1:04:42<14:17:00, 13.84s/it]  7%|▋         | 285/4000 [1:04:55<13:54:37, 13.48s/it]  7%|▋         | 286/4000 [1:05:09<14:13:33, 13.79s/it]  7%|▋         | 287/4000 [1:05:22<13:54:28, 13.48s/it]  7%|▋         | 288/4000 [1:05:37<14:15:18, 13.83s/it]  7%|▋         | 289/4000 [1:05:50<13:56:48, 13.53s/it]  7%|▋         | 290/4000 [1:06:04<14:09:42, 13.74s/it]                                                         7%|▋         | 290/4000 [1:06:04<14:09:42, 13.74s/it]  7%|▋         | 291/4000 [1:06:17<13:53:25, 13.48s/it]  7%|▋         | 292/4000 [1:06:29<13:27:16, 13.06s/it]  7%|▋         | 293/4000 [1:06:44<14:00:21, 13.60s/it]  7%|▋         | 294/4000 [1:06:58<14:12:32, 13.80s/it]  7%|▋         | 295/4000 [1:07:11<13:55:46, 13.53s/it]  7%|▋         | 296/4000 [1:07:25<14:09:15, 13.76s/it]  7%|▋         | 297/4000 [1:07:38<13:58:52, 13.59s/it]  7%|▋         | 298/4000 [1:07:53<14:24:41, 14.01s/it]  7%|▋         | 299/4000 [1:08:06<13:56:10, 13.56s/it]  8%|▊         | 300/4000 [1:08:21<14:18:01, 13.91s/it]                                                         8%|▊         | 300/4000 [1:08:21<14:18:01, 13.91s/it]  8%|▊         | 301/4000 [1:08:33<13:57:43, 13.59s/it]  8%|▊         | 302/4000 [1:08:48<14:14:34, 13.87s/it]  8%|▊         | 303/4000 [1:09:01<13:54:46, 13.55s/it]  8%|▊         | 304/4000 [1:09:15<14:08:10, 13.77s/it]  8%|▊         | 305/4000 [1:09:28<13:48:17, 13.45s/it]  8%|▊         | 306/4000 [1:09:42<14:06:52, 13.76s/it]  8%|▊         | 307/4000 [1:09:57<14:24:37, 14.05s/it]  8%|▊         | 308/4000 [1:10:10<14:01:54, 13.68s/it]  8%|▊         | 309/4000 [1:10:24<14:12:53, 13.86s/it]  8%|▊         | 310/4000 [1:10:36<13:46:01, 13.43s/it]                                                         8%|▊         | 310/4000 [1:10:36<13:46:01, 13.43s/it]  8%|▊         | 311/4000 [1:10:49<13:32:09, 13.21s/it]  8%|▊         | 312/4000 [1:11:04<14:00:02, 13.67s/it]  8%|▊         | 313/4000 [1:11:18<14:15:41, 13.93s/it]  8%|▊         | 314/4000 [1:11:31<13:57:09, 13.63s/it]  8%|▊         | 315/4000 [1:11:46<14:14:20, 13.91s/it]  8%|▊         | 316/4000 [1:11:58<13:48:08, 13.49s/it]  8%|▊         | 317/4000 [1:12:13<14:10:15, 13.85s/it]  8%|▊         | 318/4000 [1:12:28<14:27:08, 14.13s/it]  8%|▊         | 319/4000 [1:12:41<14:08:54, 13.84s/it]  8%|▊         | 320/4000 [1:12:56<14:20:16, 14.03s/it]                                                         8%|▊         | 320/4000 [1:12:56<14:20:16, 14.03s/it]  8%|▊         | 321/4000 [1:13:08<13:52:02, 13.57s/it]  8%|▊         | 322/4000 [1:13:23<14:10:38, 13.88s/it]  8%|▊         | 323/4000 [1:13:36<13:52:47, 13.59s/it]  8%|▊         | 324/4000 [1:13:50<14:07:00, 13.83s/it]  8%|▊         | 325/4000 [1:14:03<13:46:34, 13.49s/it]  8%|▊         | 326/4000 [1:14:17<14:05:54, 13.81s/it]  8%|▊         | 327/4000 [1:14:30<13:44:35, 13.47s/it]  8%|▊         | 328/4000 [1:14:45<14:10:27, 13.90s/it]  8%|▊         | 329/4000 [1:14:59<14:18:46, 14.04s/it]  8%|▊         | 330/4000 [1:15:12<13:54:39, 13.65s/it]                                                         8%|▊         | 330/4000 [1:15:12<13:54:39, 13.65s/it]  8%|▊         | 331/4000 [1:15:26<14:09:49, 13.90s/it]  8%|▊         | 332/4000 [1:15:39<13:43:25, 13.47s/it]  8%|▊         | 333/4000 [1:15:51<13:28:22, 13.23s/it]  8%|▊         | 334/4000 [1:16:06<13:54:57, 13.67s/it]  8%|▊         | 335/4000 [1:16:18<13:28:14, 13.23s/it]  8%|▊         | 336/4000 [1:16:33<13:55:55, 13.69s/it]  8%|▊         | 337/4000 [1:16:46<13:40:18, 13.44s/it]  8%|▊         | 338/4000 [1:17:01<14:01:29, 13.79s/it]  8%|▊         | 339/4000 [1:17:13<13:31:44, 13.30s/it]  8%|▊         | 340/4000 [1:17:28<13:58:48, 13.75s/it]                                                         8%|▊         | 340/4000 [1:17:28<13:58:48, 13.75s/it]  9%|▊         | 341/4000 [1:17:40<13:39:36, 13.44s/it]  9%|▊         | 342/4000 [1:17:55<14:08:38, 13.92s/it]  9%|▊         | 343/4000 [1:18:10<14:13:45, 14.01s/it]  9%|▊         | 344/4000 [1:18:22<13:51:18, 13.64s/it]  9%|▊         | 345/4000 [1:18:37<14:11:18, 13.97s/it]  9%|▊         | 346/4000 [1:18:49<13:40:50, 13.48s/it]  9%|▊         | 347/4000 [1:19:04<14:05:30, 13.89s/it]  9%|▊         | 348/4000 [1:19:17<13:44:52, 13.55s/it]  9%|▊         | 349/4000 [1:19:32<14:09:38, 13.96s/it]  9%|▉         | 350/4000 [1:19:47<14:29:59, 14.30s/it]                                                         9%|▉         | 350/4000 [1:19:47<14:29:59, 14.30s/it]  9%|▉         | 351/4000 [1:20:00<13:58:41, 13.79s/it]  9%|▉         | 352/4000 [1:20:14<14:09:12, 13.97s/it]  9%|▉         | 353/4000 [1:20:27<13:49:30, 13.65s/it]  9%|▉         | 354/4000 [1:20:41<13:58:24, 13.80s/it]  9%|▉         | 355/4000 [1:20:54<13:42:20, 13.54s/it]  9%|▉         | 356/4000 [1:21:08<13:56:17, 13.77s/it]  9%|▉         | 357/4000 [1:21:21<13:40:55, 13.52s/it]  9%|▉         | 358/4000 [1:21:36<14:00:25, 13.85s/it]  9%|▉         | 359/4000 [1:21:49<13:43:35, 13.57s/it]  9%|▉         | 360/4000 [1:22:03<13:59:20, 13.84s/it]                                                         9%|▉         | 360/4000 [1:22:03<13:59:20, 13.84s/it]  9%|▉         | 361/4000 [1:22:16<13:39:13, 13.51s/it]  9%|▉         | 362/4000 [1:22:31<13:58:01, 13.82s/it]  9%|▉         | 363/4000 [1:22:43<13:36:27, 13.47s/it]  9%|▉         | 364/4000 [1:22:58<13:58:25, 13.84s/it]  9%|▉         | 365/4000 [1:23:10<13:32:03, 13.40s/it]  9%|▉         | 366/4000 [1:23:25<13:54:13, 13.77s/it]  9%|▉         | 367/4000 [1:23:37<13:29:14, 13.36s/it]  9%|▉         | 368/4000 [1:23:52<13:45:37, 13.64s/it]  9%|▉         | 369/4000 [1:24:06<14:05:05, 13.96s/it]  9%|▉         | 370/4000 [1:24:19<13:35:48, 13.48s/it]                                                         9%|▉         | 370/4000 [1:24:19<13:35:48, 13.48s/it]  9%|▉         | 371/4000 [1:24:33<13:53:46, 13.79s/it]  9%|▉         | 372/4000 [1:24:46<13:39:29, 13.55s/it]  9%|▉         | 373/4000 [1:24:59<13:28:48, 13.38s/it]  9%|▉         | 374/4000 [1:25:14<13:48:59, 13.72s/it]  9%|▉         | 375/4000 [1:25:28<13:58:21, 13.88s/it]  9%|▉         | 376/4000 [1:25:40<13:30:40, 13.42s/it]  9%|▉         | 377/4000 [1:25:55<13:50:25, 13.75s/it]  9%|▉         | 378/4000 [1:26:07<13:27:21, 13.37s/it]  9%|▉         | 379/4000 [1:26:22<13:52:27, 13.79s/it] 10%|▉         | 380/4000 [1:26:35<13:32:10, 13.46s/it]                                                        10%|▉         | 380/4000 [1:26:35<13:32:10, 13.46s/it] 10%|▉         | 381/4000 [1:26:50<13:58:51, 13.91s/it] 10%|▉         | 382/4000 [1:27:02<13:30:10, 13.44s/it] 10%|▉         | 383/4000 [1:27:17<13:53:58, 13.83s/it] 10%|▉         | 384/4000 [1:27:29<13:31:42, 13.47s/it] 10%|▉         | 385/4000 [1:27:42<13:16:34, 13.22s/it] 10%|▉         | 386/4000 [1:27:56<13:38:39, 13.59s/it] 10%|▉         | 387/4000 [1:28:11<13:49:03, 13.77s/it] 10%|▉         | 388/4000 [1:28:23<13:28:52, 13.44s/it] 10%|▉         | 389/4000 [1:28:38<13:50:13, 13.79s/it] 10%|▉         | 390/4000 [1:28:51<13:32:52, 13.51s/it]                                                        10%|▉         | 390/4000 [1:28:51<13:32:52, 13.51s/it] 10%|▉         | 391/4000 [1:29:06<13:54:23, 13.87s/it] 10%|▉         | 392/4000 [1:29:18<13:37:28, 13.59s/it] 10%|▉         | 393/4000 [1:29:33<13:53:45, 13.87s/it] 10%|▉         | 394/4000 [1:29:46<13:40:51, 13.66s/it] 10%|▉         | 395/4000 [1:30:00<13:50:47, 13.83s/it] 10%|▉         | 396/4000 [1:30:13<13:33:35, 13.54s/it] 10%|▉         | 397/4000 [1:30:28<13:48:15, 13.79s/it] 10%|▉         | 398/4000 [1:30:40<13:28:46, 13.47s/it] 10%|▉         | 399/4000 [1:30:55<13:41:28, 13.69s/it] 10%|█         | 400/4000 [1:31:08<13:28:12, 13.47s/it]                                                        10%|█         | 400/4000 [1:31:08<13:28:12, 13.47s/it] 10%|█         | 401/4000 [1:31:22<13:51:44, 13.87s/it] 10%|█         | 402/4000 [1:31:35<13:36:16, 13.61s/it] 10%|█         | 403/4000 [1:31:50<14:03:24, 14.07s/it] 10%|█         | 404/4000 [1:32:03<13:37:27, 13.64s/it] 10%|█         | 405/4000 [1:32:18<13:54:39, 13.93s/it] 10%|█         | 406/4000 [1:32:32<14:03:19, 14.08s/it] 10%|█         | 407/4000 [1:32:45<13:42:50, 13.74s/it] 10%|█         | 408/4000 [1:33:00<13:58:49, 14.01s/it] 10%|█         | 409/4000 [1:33:12<13:34:24, 13.61s/it] 10%|█         | 410/4000 [1:33:27<13:57:42, 14.00s/it]                                                        10%|█         | 410/4000 [1:33:27<13:57:42, 14.00s/it] 10%|█         | 411/4000 [1:33:40<13:40:41, 13.72s/it] 10%|█         | 412/4000 [1:33:55<13:53:04, 13.93s/it] 10%|█         | 413/4000 [1:34:07<13:30:15, 13.55s/it] 10%|█         | 414/4000 [1:34:22<13:50:31, 13.90s/it] 10%|█         | 415/4000 [1:34:35<13:24:41, 13.47s/it] 10%|█         | 416/4000 [1:34:50<13:53:44, 13.96s/it] 10%|█         | 417/4000 [1:35:02<13:27:10, 13.52s/it] 10%|█         | 418/4000 [1:35:16<13:40:44, 13.75s/it] 10%|█         | 419/4000 [1:35:29<13:21:38, 13.43s/it] 10%|█         | 420/4000 [1:35:44<13:46:18, 13.85s/it]                                                        10%|█         | 420/4000 [1:35:44<13:46:18, 13.85s/it] 11%|█         | 421/4000 [1:35:59<13:58:41, 14.06s/it] 11%|█         | 422/4000 [1:36:11<13:37:19, 13.71s/it] 11%|█         | 423/4000 [1:36:26<13:45:06, 13.84s/it] 11%|█         | 424/4000 [1:36:38<13:24:53, 13.50s/it] 11%|█         | 425/4000 [1:36:53<13:54:20, 14.00s/it] 11%|█         | 426/4000 [1:37:06<13:23:21, 13.49s/it] 11%|█         | 427/4000 [1:37:21<13:48:55, 13.92s/it] 11%|█         | 428/4000 [1:37:35<13:57:20, 14.07s/it] 11%|█         | 429/4000 [1:37:48<13:36:00, 13.71s/it] 11%|█         | 430/4000 [1:38:02<13:47:20, 13.90s/it]                                                        11%|█         | 430/4000 [1:38:02<13:47:20, 13.90s/it] 11%|█         | 431/4000 [1:38:15<13:18:31, 13.42s/it] 11%|█         | 432/4000 [1:38:29<13:30:37, 13.63s/it] 11%|█         | 433/4000 [1:38:42<13:22:01, 13.49s/it] 11%|█         | 434/4000 [1:38:55<13:07:54, 13.26s/it] 11%|█         | 435/4000 [1:39:09<13:32:29, 13.67s/it] 11%|█         | 436/4000 [1:39:24<13:44:36, 13.88s/it] 11%|█         | 437/4000 [1:39:36<13:23:05, 13.52s/it] 11%|█         | 438/4000 [1:39:52<13:52:14, 14.02s/it] 11%|█         | 439/4000 [1:40:04<13:28:12, 13.62s/it] 11%|█         | 440/4000 [1:40:19<13:45:28, 13.91s/it]                                                        11%|█         | 440/4000 [1:40:19<13:45:28, 13.91s/it] 11%|█         | 441/4000 [1:40:34<14:00:03, 14.16s/it] 11%|█         | 442/4000 [1:40:47<13:40:56, 13.84s/it] 11%|█         | 443/4000 [1:41:01<13:53:01, 14.05s/it] 11%|█         | 444/4000 [1:41:14<13:33:41, 13.73s/it] 11%|█         | 445/4000 [1:41:29<13:49:36, 14.00s/it] 11%|█         | 446/4000 [1:41:42<13:29:18, 13.66s/it] 11%|█         | 447/4000 [1:41:56<13:48:26, 13.99s/it] 11%|█         | 448/4000 [1:42:09<13:27:31, 13.64s/it] 11%|█         | 449/4000 [1:42:24<13:46:49, 13.97s/it] 11%|█▏        | 450/4000 [1:42:37<13:27:35, 13.65s/it]                                                        11%|█▏        | 450/4000 [1:42:37<13:27:35, 13.65s/it] 11%|█▏        | 451/4000 [1:42:51<13:43:39, 13.92s/it] 11%|█▏        | 452/4000 [1:43:06<13:49:04, 14.02s/it] 11%|█▏        | 453/4000 [1:43:18<13:26:32, 13.64s/it] 11%|█▏        | 454/4000 [1:43:33<13:43:43, 13.94s/it] 11%|█▏        | 455/4000 [1:43:46<13:24:03, 13.61s/it] 11%|█▏        | 456/4000 [1:44:00<13:35:36, 13.81s/it] 11%|█▏        | 457/4000 [1:44:13<13:10:57, 13.39s/it] 11%|█▏        | 458/4000 [1:44:27<13:29:40, 13.72s/it] 11%|█▏        | 459/4000 [1:44:40<13:21:29, 13.58s/it] 12%|█▏        | 460/4000 [1:44:55<13:44:44, 13.98s/it]                                                        12%|█▏        | 460/4000 [1:44:55<13:44:44, 13.98s/it] 12%|█▏        | 461/4000 [1:45:08<13:15:49, 13.49s/it] 12%|█▏        | 462/4000 [1:45:22<13:30:22, 13.74s/it] 12%|█▏        | 463/4000 [1:45:37<13:46:31, 14.02s/it] 12%|█▏        | 464/4000 [1:45:49<13:23:54, 13.64s/it] 12%|█▏        | 465/4000 [1:46:02<13:02:13, 13.28s/it] 12%|█▏        | 466/4000 [1:46:17<13:30:02, 13.75s/it] 12%|█▏        | 467/4000 [1:46:29<13:09:20, 13.41s/it] 12%|█▏        | 468/4000 [1:46:44<13:31:16, 13.78s/it] 12%|█▏        | 469/4000 [1:46:59<13:46:20, 14.04s/it] 12%|█▏        | 470/4000 [1:47:12<13:26:34, 13.71s/it]                                                        12%|█▏        | 470/4000 [1:47:12<13:26:34, 13.71s/it] 12%|█▏        | 471/4000 [1:47:26<13:38:33, 13.92s/it] 12%|█▏        | 472/4000 [1:47:39<13:15:57, 13.54s/it] 12%|█▏        | 473/4000 [1:47:54<13:40:44, 13.96s/it] 12%|█▏        | 474/4000 [1:48:06<13:13:56, 13.51s/it] 12%|█▏        | 475/4000 [1:48:21<13:34:46, 13.87s/it] 12%|█▏        | 476/4000 [1:48:34<13:19:47, 13.62s/it] 12%|█▏        | 477/4000 [1:48:48<13:33:16, 13.85s/it] 12%|█▏        | 478/4000 [1:49:01<13:12:25, 13.50s/it] 12%|█▏        | 479/4000 [1:49:13<12:53:27, 13.18s/it] 12%|█▏        | 480/4000 [1:49:28<13:15:43, 13.56s/it]                                                        12%|█▏        | 480/4000 [1:49:28<13:15:43, 13.56s/it] 12%|█▏        | 481/4000 [1:49:40<12:56:47, 13.24s/it] 12%|█▏        | 482/4000 [1:49:55<13:24:19, 13.72s/it] 12%|█▏        | 483/4000 [1:50:08<13:07:19, 13.43s/it] 12%|█▏        | 484/4000 [1:50:22<13:20:04, 13.65s/it] 12%|█▏        | 485/4000 [1:50:36<13:34:15, 13.90s/it] 12%|█▏        | 486/4000 [1:50:49<13:10:07, 13.49s/it] 12%|█▏        | 487/4000 [1:51:01<12:47:42, 13.11s/it] 12%|█▏        | 488/4000 [1:51:16<13:13:06, 13.55s/it] 12%|█▏        | 489/4000 [1:51:28<12:51:44, 13.19s/it] 12%|█▏        | 490/4000 [1:51:43<13:13:54, 13.57s/it]                                                        12%|█▏        | 490/4000 [1:51:43<13:13:54, 13.57s/it] 12%|█▏        | 491/4000 [1:51:56<13:05:42, 13.43s/it] 12%|█▏        | 492/4000 [1:52:10<13:25:10, 13.77s/it] 12%|█▏        | 493/4000 [1:52:23<13:02:23, 13.39s/it] 12%|█▏        | 494/4000 [1:52:37<13:26:48, 13.81s/it] 12%|█▏        | 495/4000 [1:52:53<13:49:31, 14.20s/it] 12%|█▏        | 496/4000 [1:53:05<13:20:26, 13.71s/it] 12%|█▏        | 497/4000 [1:53:20<13:35:03, 13.96s/it] 12%|█▏        | 498/4000 [1:53:32<13:11:51, 13.57s/it] 12%|█▏        | 499/4000 [1:53:47<13:37:23, 14.01s/it] 12%|█▎        | 500/4000 [1:54:02<13:50:17, 14.23s/it]                                                        12%|█▎        | 500/4000 [1:54:02<13:50:17, 14.23s/it]{'loss': '27.66', 'grad_norm': '1.167', 'learning_rate': '1.5e-05', 'epoch': '0.01594'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:45:{'loss': '3.035', 'grad_norm': '0.5533', 'learning_rate': '0.0001483', 'epoch': '0.1435'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:71:{'loss': '1.691', 'grad_norm': '0.4194', 'learning_rate': '0.0001983', 'epoch': '0.5579'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:80:{'loss': '1.629', 'grad_norm': '0.3537', 'learning_rate': '0.0001967', 'epoch': '0.7013'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:157: 14%|█▍        | 70/503 [00:53<04:05,  1.76it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:158: 14%|█▍        | 71/503 [00:55<07:42,  1.07s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:159: 14%|█▍        | 72/503 [00:55<06:02,  1.19it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:184: 19%|█▉        | 97/503 [01:14<03:59,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:243: 31%|███       | 156/503 [02:01<03:24,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:257: 34%|███▍      | 170/503 [02:13<04:20,  1.28it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:357: 54%|█████▎    | 270/503 [03:30<02:31,  1.53it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:437: 70%|██████▉   | 350/503 [04:31<02:38,  1.04s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:438: 70%|██████▉   | 351/503 [04:31<02:02,  1.24it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:439: 70%|██████▉   | 352/503 [04:31<01:38,  1.53it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:440: 70%|███████   | 353/503 [04:32<01:22,  1.83it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:441: 70%|███████   | 354/503 [04:34<02:36,  1.05s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:457: 74%|███████▎  | 370/503 [04:46<02:14,  1.01s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:488: 80%|███████▉  | 401/503 [05:07<00:55,  1.85it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:503: 83%|████████▎ | 416/503 [05:19<00:55,  1.56it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:518: 86%|████████▌ | 431/503 [05:31<00:55,  1.30it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:538: 90%|████████▉ | 451/503 [05:46<00:55,  1.06s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:557: 93%|█████████▎| 470/503 [05:59<00:17,  1.90it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:597: 13%|█▎        | 501/4000 [2:00:46<127:28:08, 131.15s/it] 13%|█▎        | 502/4000 [2:00:59<92:56:29, 95.65s/it]   13%|█▎        | 503/4000 [2:01:13<69:09:52, 71.20s/it] 13%|█▎        | 504/4000 [2:01:26<52:04:21, 53.62s/it] 13%|█▎        | 505/4000 [2:01:40<40:44:28, 41.97s/it] 13%|█▎        | 506/4000 [2:01:55<32:45:07, 33.75s/it] 13%|█▎        | 507/4000 [2:02:08<26:36:09, 27.42s/it] 13%|█▎        | 508/4000 [2:02:22<22:50:31, 23.55s/it] 13%|█▎        | 509/4000 [2:02:35<19:41:12, 20.30s/it] 13%|█▎        | 510/4000 [2:02:49<18:00:17, 18.57s/it]                                                        13%|█▎        | 510/4000 [2:02:49<18:00:17, 18.57s/it] 13%|█▎        | 511/4000 [2:03:02<16:18:42, 16.83s/it] 13%|█▎        | 512/4000 [2:03:17<15:39:17, 16.16s/it] 13%|█▎        | 513/4000 [2:03:29<14:38:20, 15.11s/it] 13%|█▎        | 514/4000 [2:03:44<14:31:57, 15.01s/it] 13%|█▎        | 515/4000 [2:03:57<13:56:10, 14.40s/it] 13%|█▎        | 516/4000 [2:04:10<13:24:58, 13.86s/it] 13%|█▎        | 517/4000 [2:04:24<13:38:28, 14.10s/it] 13%|█▎        | 518/4000 [2:04:37<13:12:24, 13.65s/it] 13%|█▎        | 519/4000 [2:04:52<13:28:42, 13.94s/it] 13%|█▎        | 520/4000 [2:05:06<13:33:25, 14.02s/it]                                                        13%|█▎        | 520/4000 [2:05:06<13:33:25, 14.02s/it] 13%|█▎        | 521/4000 [2:05:19<13:11:25, 13.65s/it] 13%|█▎        | 522/4000 [2:05:34<13:31:19, 14.00s/it] 13%|█▎        | 523/4000 [2:05:46<13:07:32, 13.59s/it] 13%|█▎        | 524/4000 [2:05:59<12:48:32, 13.27s/it] 13%|█▎        | 525/4000 [2:06:13<13:11:37, 13.67s/it] 13%|█▎        | 526/4000 [2:06:26<12:53:56, 13.37s/it] 13%|█▎        | 527/4000 [2:06:40<13:10:03, 13.65s/it] 13%|█▎        | 528/4000 [2:06:53<12:50:08, 13.31s/it] 13%|█▎        | 529/4000 [2:07:07<13:03:05, 13.54s/it] 13%|█▎        | 530/4000 [2:07:20<12:51:05, 13.33s/it]                                                        13%|█▎        | 530/4000 [2:07:20<12:51:05, 13.33s/it] 13%|█▎        | 531/4000 [2:07:32<12:33:33, 13.03s/it] 13%|█▎        | 532/4000 [2:07:46<12:54:40, 13.40s/it] 13%|█▎        | 533/4000 [2:08:01<13:21:49, 13.88s/it] 13%|█▎        | 534/4000 [2:08:14<12:54:28, 13.41s/it] 13%|█▎        | 535/4000 [2:08:28<13:13:20, 13.74s/it] 13%|█▎        | 536/4000 [2:08:41<12:56:00, 13.44s/it] 13%|█▎        | 537/4000 [2:08:56<13:20:15, 13.87s/it] 13%|█▎        | 538/4000 [2:09:10<13:33:52, 14.11s/it] 13%|█▎        | 539/4000 [2:09:23<13:11:52, 13.73s/it] 14%|█▎        | 540/4000 [2:09:36<12:49:38, 13.35s/it]                                                        14%|█▎        | 540/4000 [2:09:36<12:49:38, 13.35s/it] 14%|█▎        | 541/4000 [2:09:51<13:15:25, 13.80s/it] 14%|█▎        | 542/4000 [2:10:05<13:26:55, 14.00s/it] 14%|█▎        | 543/4000 [2:10:17<12:59:32, 13.53s/it] 14%|█▎        | 544/4000 [2:10:32<13:14:35, 13.79s/it] 14%|█▎        | 545/4000 [2:10:45<13:00:34, 13.56s/it] 14%|█▎        | 546/4000 [2:10:59<13:16:32, 13.84s/it] 14%|█▎        | 547/4000 [2:11:12<13:00:21, 13.56s/it] 14%|█▎        | 548/4000 [2:11:27<13:14:45, 13.81s/it] 14%|█▎        | 549/4000 [2:11:39<12:53:57, 13.46s/it] 14%|█▍        | 550/4000 [2:11:54<13:17:54, 13.88s/it]                                                        14%|█▍        | 550/4000 [2:11:54<13:17:54, 13.88s/it] 14%|█▍        | 551/4000 [2:12:07<13:00:21, 13.58s/it] 14%|█▍        | 552/4000 [2:12:21<13:13:35, 13.81s/it] 14%|█▍        | 553/4000 [2:12:34<12:56:14, 13.51s/it] 14%|█▍        | 554/4000 [2:12:49<13:15:52, 13.86s/it] 14%|█▍        | 555/4000 [2:13:01<12:50:00, 13.41s/it] 14%|█▍        | 556/4000 [2:13:16<13:09:25, 13.75s/it] 14%|█▍        | 557/4000 [2:13:29<12:55:32, 13.52s/it] 14%|█▍        | 558/4000 [2:13:43<13:16:58, 13.89s/it] 14%|█▍        | 559/4000 [2:13:58<13:33:54, 14.19s/it] 14%|█▍        | 560/4000 [2:14:11<13:04:38, 13.69s/it]                                                        14%|█▍        | 560/4000 [2:14:11<13:04:38, 13.69s/it] 14%|█▍        | 561/4000 [2:14:25<13:19:37, 13.95s/it] 14%|█▍        | 562/4000 [2:14:38<13:01:01, 13.63s/it] 14%|█▍        | 563/4000 [2:14:52<13:08:01, 13.76s/it] 14%|█▍        | 564/4000 [2:15:05<12:56:14, 13.55s/it] 14%|█▍        | 565/4000 [2:15:20<13:16:36, 13.91s/it] 14%|█▍        | 566/4000 [2:15:33<12:49:38, 13.45s/it] 14%|█▍        | 567/4000 [2:15:47<13:08:53, 13.79s/it] 14%|█▍        | 568/4000 [2:16:00<12:55:05, 13.55s/it] 14%|█▍        | 569/4000 [2:16:14<13:06:45, 13.76s/it] 14%|█▍        | 570/4000 [2:16:27<12:47:06, 13.42s/it]                                                        14%|█▍        | 570/4000 [2:16:27<12:47:06, 13.42s/it] 14%|█▍        | 571/4000 [2:16:42<13:13:01, 13.88s/it] 14%|█▍        | 572/4000 [2:16:56<13:18:37, 13.98s/it] 14%|█▍        | 573/4000 [2:17:09<12:54:48, 13.57s/it] 14%|█▍        | 574/4000 [2:17:21<12:37:23, 13.26s/it] 14%|█▍        | 575/4000 [2:17:36<13:03:56, 13.73s/it] 14%|█▍        | 576/4000 [2:17:51<13:22:10, 14.06s/it] 14%|█▍        | 577/4000 [2:18:04<13:03:38, 13.74s/it] 14%|█▍        | 578/4000 [2:18:18<13:07:44, 13.81s/it] 14%|█▍        | 579/4000 [2:18:31<12:49:04, 13.49s/it] 14%|█▍        | 580/4000 [2:18:45<13:10:50, 13.87s/it]                                                        14%|█▍        | 580/4000 [2:18:45<13:10:50, 13.87s/it] 15%|█▍        | 581/4000 [2:18:59<12:57:33, 13.65s/it] 15%|█▍        | 582/4000 [2:19:13<13:15:05, 13.96s/it] 15%|█▍        | 583/4000 [2:19:26<12:52:45, 13.57s/it] 15%|█▍        | 584/4000 [2:19:41<13:14:18, 13.95s/it] 15%|█▍        | 585/4000 [2:19:56<13:27:48, 14.19s/it] 15%|█▍        | 586/4000 [2:20:08<12:55:31, 13.63s/it] 15%|█▍        | 587/4000 [2:20:22<13:10:38, 13.90s/it] 15%|█▍        | 588/4000 [2:20:35<12:49:16, 13.53s/it] 15%|█▍        | 589/4000 [2:20:50<13:08:30, 13.87s/it] 15%|█▍        | 590/4000 [2:21:03<12:56:15, 13.66s/it]                                                        15%|█▍        | 590/4000 [2:21:03<12:56:15, 13.66s/it] 15%|█▍        | 591/4000 [2:21:17<13:11:00, 13.92s/it] 15%|█▍        | 592/4000 [2:21:30<12:52:32, 13.60s/it] 15%|█▍        | 593/4000 [2:21:45<13:11:16, 13.94s/it] 15%|█▍        | 594/4000 [2:21:58<12:51:14, 13.59s/it] 15%|█▍        | 595/4000 [2:22:12<13:08:48, 13.90s/it] 15%|█▍        | 596/4000 [2:22:25<12:48:46, 13.55s/it] 15%|█▍        | 597/4000 [2:22:40<13:08:26, 13.90s/it] 15%|█▍        | 598/4000 [2:22:53<12:48:23, 13.55s/it] 15%|█▍        | 599/4000 [2:23:05<12:25:30, 13.15s/it] 15%|█▌        | 600/4000 [2:23:20<12:54:55, 13.68s/it]                                                        15%|█▌        | 600/4000 [2:23:20<12:54:55, 13.68s/it] 15%|█▌        | 601/4000 [2:23:34<13:09:17, 13.93s/it] 15%|█▌        | 602/4000 [2:23:47<12:44:29, 13.50s/it] 15%|█▌        | 603/4000 [2:24:02<13:07:36, 13.91s/it] 15%|█▌        | 604/4000 [2:24:14<12:44:10, 13.50s/it] 15%|█▌        | 605/4000 [2:24:29<13:03:15, 13.84s/it] 15%|█▌        | 606/4000 [2:24:42<12:47:15, 13.56s/it] 15%|█▌        | 607/4000 [2:24:56<12:59:38, 13.79s/it] 15%|█▌        | 608/4000 [2:25:09<12:39:47, 13.44s/it] 15%|█▌        | 609/4000 [2:25:24<13:04:51, 13.89s/it] 15%|█▌        | 610/4000 [2:25:36<12:45:56, 13.56s/it]                                                        15%|█▌        | 610/4000 [2:25:36<12:45:56, 13.56s/it] 15%|█▌        | 611/4000 [2:25:51<13:03:25, 13.87s/it] 15%|█▌        | 612/4000 [2:26:03<12:37:10, 13.41s/it] 15%|█▌        | 613/4000 [2:26:18<12:59:07, 13.80s/it] 15%|█▌        | 614/4000 [2:26:33<13:14:44, 14.08s/it] 15%|█▌        | 615/4000 [2:26:45<12:49:06, 13.63s/it] 15%|█▌        | 616/4000 [2:26:58<12:30:22, 13.30s/it] 15%|█▌        | 617/4000 [2:27:13<12:55:12, 13.75s/it] 15%|█▌        | 618/4000 [2:27:25<12:36:59, 13.43s/it] 15%|█▌        | 619/4000 [2:27:40<12:55:29, 13.76s/it] 16%|█▌        | 620/4000 [2:27:53<12:36:25, 13.43s/it]                                                        16%|█▌        | 620/4000 [2:27:53<12:36:25, 13.43s/it] 16%|█▌        | 621/4000 [2:28:05<12:23:15, 13.20s/it] 16%|█▌        | 622/4000 [2:28:20<12:51:44, 13.71s/it] 16%|█▌        | 623/4000 [2:28:33<12:32:48, 13.38s/it] 16%|█▌        | 624/4000 [2:28:47<12:52:21, 13.73s/it] 16%|█▌        | 625/4000 [2:29:00<12:34:22, 13.41s/it] 16%|█▌        | 626/4000 [2:29:15<12:56:25, 13.81s/it] 16%|█▌        | 627/4000 [2:29:27<12:30:16, 13.35s/it] 16%|█▌        | 628/4000 [2:29:32<10:19:37, 11.03s/it] 16%|█▌        | 629/4000 [2:29:45<10:44:57, 11.48s/it] 16%|█▌        | 630/4000 [2:30:00<11:43:41, 12.53s/it]                                                        16%|█▌        | 630/4000 [2:30:00<11:43:41, 12.53s/it] 16%|█▌        | 631/4000 [2:30:13<11:44:44, 12.55s/it] 16%|█▌        | 632/4000 [2:30:27<12:12:09, 13.04s/it] 16%|█▌        | 633/4000 [2:30:39<12:03:38, 12.90s/it] 16%|█▌        | 634/4000 [2:30:54<12:32:20, 13.41s/it] 16%|█▌        | 635/4000 [2:31:07<12:23:32, 13.26s/it] 16%|█▌        | 636/4000 [2:31:22<12:50:24, 13.74s/it] 16%|█▌        | 637/4000 [2:31:35<12:34:48, 13.47s/it] 16%|█▌        | 638/4000 [2:31:47<12:11:52, 13.06s/it] 16%|█▌        | 639/4000 [2:32:01<12:39:29, 13.56s/it] 16%|█▌        | 640/4000 [2:32:14<12:24:31, 13.30s/it]                                                        16%|█▌        | 640/4000 [2:32:14<12:24:31, 13.30s/it] 16%|█▌        | 641/4000 [2:32:29<12:46:46, 13.70s/it] 16%|█▌        | 642/4000 [2:32:41<12:27:30, 13.36s/it] 16%|█▌        | 643/4000 [2:32:56<12:50:41, 13.77s/it] 16%|█▌        | 644/4000 [2:33:09<12:32:33, 13.45s/it] 16%|█▌        | 645/4000 [2:33:21<12:10:09, 13.06s/it] 16%|█▌        | 646/4000 [2:33:35<12:35:29, 13.51s/it] 16%|█▌        | 647/4000 [2:33:50<12:56:16, 13.89s/it] 16%|█▌        | 648/4000 [2:34:03<12:36:05, 13.53s/it] 16%|█▌        | 649/4000 [2:34:17<12:47:31, 13.74s/it] 16%|█▋        | 650/4000 [2:34:30<12:30:30, 13.44s/it]                                                        16%|█▋        | 650/4000 [2:34:30<12:30:30, 13.44s/it] 16%|█▋        | 651/4000 [2:34:44<12:48:41, 13.77s/it] 16%|█▋        | 652/4000 [2:34:57<12:28:53, 13.42s/it] 16%|█▋        | 653/4000 [2:35:12<12:50:29, 13.81s/it] 16%|█▋        | 654/4000 [2:35:24<12:27:07, 13.40s/it] 16%|█▋        | 655/4000 [2:35:39<12:47:39, 13.77s/it] 16%|█▋        | 656/4000 [2:35:54<13:07:21, 14.13s/it] 16%|█▋        | 657/4000 [2:36:07<12:43:34, 13.70s/it] 16%|█▋        | 658/4000 [2:36:20<12:47:30, 13.78s/it] 16%|█▋        | 659/4000 [2:36:33<12:32:57, 13.52s/it] 16%|█▋        | 660/4000 [2:36:48<12:51:28, 13.86s/it]                                                        16%|█▋        | 660/4000 [2:36:48<12:51:28, 13.86s/it] 17%|█▋        | 661/4000 [2:37:01<12:35:15, 13.57s/it] 17%|█▋        | 662/4000 [2:37:16<12:56:04, 13.95s/it] 17%|█▋        | 663/4000 [2:37:30<12:57:30, 13.98s/it] 17%|█▋        | 664/4000 [2:37:42<12:33:07, 13.55s/it] 17%|█▋        | 665/4000 [2:37:55<12:20:04, 13.31s/it] 17%|█▋        | 666/4000 [2:38:10<12:40:56, 13.69s/it] 17%|█▋        | 667/4000 [2:38:22<12:17:56, 13.28s/it] 17%|█▋        | 668/4000 [2:38:34<12:01:16, 12.99s/it] 17%|█▋        | 669/4000 [2:38:49<12:29:49, 13.51s/it] 17%|█▋        | 670/4000 [2:39:04<12:53:04, 13.93s/it]                                                        17%|█▋        | 670/4000 [2:39:04<12:53:04, 13.93s/it] 17%|█▋        | 671/4000 [2:39:17<12:30:44, 13.53s/it] 17%|█▋        | 672/4000 [2:39:31<12:52:34, 13.93s/it] 17%|█▋        | 673/4000 [2:39:44<12:34:05, 13.60s/it] 17%|█▋        | 674/4000 [2:39:59<12:48:41, 13.87s/it] 17%|█▋        | 675/4000 [2:40:11<12:26:44, 13.47s/it] 17%|█▋        | 676/4000 [2:40:26<12:43:22, 13.78s/it] 17%|█▋        | 677/4000 [2:40:38<12:24:48, 13.45s/it] 17%|█▋        | 678/4000 [2:40:53<12:44:18, 13.80s/it] 17%|█▋        | 679/4000 [2:41:06<12:28:28, 13.52s/it] 17%|█▋        | 680/4000 [2:41:20<12:42:17, 13.78s/it]                                                        17%|█▋        | 680/4000 [2:41:20<12:42:17, 13.78s/it] 17%|█▋        | 681/4000 [2:41:33<12:18:41, 13.35s/it] 17%|█▋        | 682/4000 [2:41:48<12:46:19, 13.86s/it] 17%|█▋        | 683/4000 [2:42:03<13:01:33, 14.14s/it] 17%|█▋        | 684/4000 [2:42:15<12:30:51, 13.59s/it] 17%|█▋        | 685/4000 [2:42:29<12:43:36, 13.82s/it] 17%|█▋        | 686/4000 [2:42:42<12:25:59, 13.51s/it] 17%|█▋        | 687/4000 [2:42:55<12:12:00, 13.26s/it] 17%|█▋        | 688/4000 [2:43:09<12:37:19, 13.72s/it] 17%|█▋        | 689/4000 [2:43:24<12:54:16, 14.03s/it] 17%|█▋        | 690/4000 [2:43:37<12:27:46, 13.55s/it]                                                        17%|█▋        | 690/4000 [2:43:37<12:27:46, 13.55s/it] 17%|█▋        | 691/4000 [2:43:49<12:09:05, 13.22s/it] 17%|█▋        | 692/4000 [2:44:04<12:36:12, 13.72s/it] 17%|█▋        | 693/4000 [2:44:17<12:18:38, 13.40s/it] 17%|█▋        | 694/4000 [2:44:31<12:31:43, 13.64s/it] 17%|█▋        | 695/4000 [2:44:44<12:17:16, 13.38s/it] 17%|█▋        | 696/4000 [2:44:58<12:41:13, 13.82s/it] 17%|█▋        | 697/4000 [2:45:11<12:19:51, 13.44s/it] 17%|█▋        | 698/4000 [2:45:25<12:35:49, 13.73s/it] 17%|█▋        | 699/4000 [2:45:38<12:18:51, 13.43s/it] 18%|█▊        | 700/4000 [2:45:52<12:28:24, 13.61s/it]                                                        18%|█▊        | 700/4000 [2:45:52<12:28:24, 13.61s/it] 18%|█▊        | 701/4000 [2:46:07<12:47:59, 13.97s/it] 18%|█▊        | 702/4000 [2:46:20<12:25:19, 13.56s/it] 18%|█▊        | 703/4000 [2:46:32<12:05:41, 13.21s/it] 18%|█▊        | 704/4000 [2:46:46<12:23:28, 13.53s/it] 18%|█▊        | 705/4000 [2:46:59<12:09:33, 13.28s/it] 18%|█▊        | 706/4000 [2:47:14<12:36:53, 13.79s/it] 18%|█▊        | 707/4000 [2:47:27<12:20:01, 13.48s/it] 18%|█▊        | 708/4000 [2:47:41<12:40:59, 13.87s/it] 18%|█▊        | 709/4000 [2:47:54<12:22:58, 13.55s/it] 18%|█▊        | 710/4000 [2:48:09<12:39:02, 13.84s/it]                                                        18%|█▊        | 710/4000 [2:48:09<12:39:02, 13.84s/it] 18%|█▊        | 711/4000 [2:48:22<12:24:56, 13.59s/it] 18%|█▊        | 712/4000 [2:48:37<12:47:13, 14.00s/it] 18%|█▊        | 713/4000 [2:48:52<13:00:07, 14.24s/it] 18%|█▊        | 714/4000 [2:49:04<12:34:54, 13.78s/it] 18%|█▊        | 715/4000 [2:49:19<12:49:52, 14.06s/it] 18%|█▊        | 716/4000 [2:49:32<12:30:46, 13.72s/it] 18%|█▊        | 717/4000 [2:49:46<12:41:33, 13.92s/it] 18%|█▊        | 718/4000 [2:49:59<12:23:46, 13.60s/it] 18%|█▊        | 719/4000 [2:50:14<12:41:18, 13.92s/it] 18%|█▊        | 720/4000 [2:50:26<12:11:54, 13.39s/it]                                                        18%|█▊        | 720/4000 [2:50:26<12:11:54, 13.39s/it] 18%|█▊        | 721/4000 [2:50:40<12:22:10, 13.58s/it] 18%|█▊        | 722/4000 [2:50:53<12:08:30, 13.33s/it] 18%|█▊        | 723/4000 [2:51:07<12:30:21, 13.74s/it] 18%|█▊        | 724/4000 [2:51:20<12:06:51, 13.31s/it] 18%|█▊        | 725/4000 [2:51:32<11:52:49, 13.06s/it] 18%|█▊        | 726/4000 [2:51:47<12:20:38, 13.57s/it] 18%|█▊        | 727/4000 [2:52:02<12:37:46, 13.89s/it] 18%|█▊        | 728/4000 [2:52:14<12:21:00, 13.59s/it] 18%|█▊        | 729/4000 [2:52:27<12:06:19, 13.32s/it] 18%|█▊        | 730/4000 [2:52:42<12:25:01, 13.67s/it]                                                        18%|█▊        | 730/4000 [2:52:42<12:25:01, 13.67s/it] 18%|█▊        | 731/4000 [2:52:56<12:39:55, 13.95s/it] 18%|█▊        | 732/4000 [2:53:09<12:24:13, 13.66s/it] 18%|█▊        | 733/4000 [2:53:24<12:35:21, 13.87s/it] 18%|█▊        | 734/4000 [2:53:36<12:14:33, 13.49s/it] 18%|█▊        | 735/4000 [2:53:51<12:33:39, 13.85s/it] 18%|█▊        | 736/4000 [2:54:03<12:11:09, 13.44s/it] 18%|█▊        | 737/4000 [2:54:18<12:35:02, 13.88s/it] 18%|█▊        | 738/4000 [2:54:31<12:13:28, 13.49s/it] 18%|█▊        | 739/4000 [2:54:46<12:36:27, 13.92s/it] 18%|█▊        | 740/4000 [2:55:00<12:46:43, 14.11s/it]                                                        18%|█▊        | 740/4000 [2:55:00<12:46:43, 14.11s/it] 19%|█▊        | 741/4000 [2:55:13<12:18:43, 13.60s/it] 19%|█▊        | 742/4000 [2:55:27<12:35:47, 13.92s/it] 19%|█▊        | 743/4000 [2:55:40<12:15:13, 13.54s/it] 19%|█▊        | 744/4000 [2:55:54<12:26:58, 13.76s/it] 19%|█▊        | 745/4000 [2:56:07<12:05:54, 13.38s/it] 19%|█▊        | 746/4000 [2:56:21<12:24:08, 13.72s/it] 19%|█▊        | 747/4000 [2:56:36<12:43:26, 14.08s/it] 19%|█▊        | 748/4000 [2:56:49<12:25:35, 13.76s/it] 19%|█▊        | 749/4000 [2:57:02<12:00:09, 13.29s/it] 19%|█▉        | 750/4000 [2:57:16<12:21:26, 13.69s/it]                                                        19%|█▉        | 750/4000 [2:57:16<12:21:26, 13.69s/it] 19%|█▉        | 751/4000 [2:57:31<12:38:51, 14.01s/it] 19%|█▉        | 752/4000 [2:57:44<12:23:07, 13.73s/it] 19%|█▉        | 753/4000 [2:57:58<12:35:49, 13.97s/it] 19%|█▉        | 754/4000 [2:58:12<12:21:37, 13.71s/it] 19%|█▉        | 755/4000 [2:58:26<12:40:15, 14.06s/it] 19%|█▉        | 756/4000 [2:58:39<12:19:33, 13.68s/it] 19%|█▉        | 757/4000 [2:58:54<12:39:28, 14.05s/it] 19%|█▉        | 758/4000 [2:59:07<12:15:10, 13.61s/it] 19%|█▉        | 759/4000 [2:59:19<11:58:38, 13.30s/it] 19%|█▉        | 760/4000 [2:59:34<12:20:31, 13.71s/it]                                                        19%|█▉        | 760/4000 [2:59:34<12:20:31, 13.71s/it] 19%|█▉        | 761/4000 [2:59:48<12:30:17, 13.90s/it] 19%|█▉        | 762/4000 [3:00:01<12:17:44, 13.67s/it] 19%|█▉        | 763/4000 [3:00:16<12:29:50, 13.90s/it] 19%|█▉        | 764/4000 [3:00:29<12:13:38, 13.60s/it] 19%|█▉        | 765/4000 [3:00:43<12:27:47, 13.87s/it] 19%|█▉        | 766/4000 [3:00:56<12:06:32, 13.48s/it] 19%|█▉        | 767/4000 [3:01:11<12:26:54, 13.86s/it] 19%|█▉        | 768/4000 [3:01:23<12:03:18, 13.43s/it] 19%|█▉        | 769/4000 [3:01:38<12:20:40, 13.75s/it] 19%|█▉        | 770/4000 [3:01:52<12:33:23, 13.99s/it]                                                        19%|█▉        | 770/4000 [3:01:52<12:33:23, 13.99s/it] 19%|█▉        | 771/4000 [3:02:05<12:14:16, 13.64s/it] 19%|█▉        | 772/4000 [3:02:20<12:37:49, 14.09s/it] 19%|█▉        | 773/4000 [3:02:35<12:50:20, 14.32s/it] 19%|█▉        | 774/4000 [3:02:48<12:27:03, 13.89s/it] 19%|█▉        | 775/4000 [3:03:00<12:01:30, 13.42s/it] 19%|█▉        | 776/4000 [3:03:15<12:26:03, 13.88s/it] 19%|█▉        | 777/4000 [3:03:28<12:01:26, 13.43s/it] 19%|█▉        | 778/4000 [3:03:42<12:17:00, 13.72s/it] 19%|█▉        | 779/4000 [3:03:57<12:33:55, 14.04s/it] 20%|█▉        | 780/4000 [3:04:10<12:18:24, 13.76s/it]                                                        20%|█▉        | 780/4000 [3:04:10<12:18:24, 13.76s/it] 20%|█▉        | 781/4000 [3:04:24<12:22:26, 13.84s/it] 20%|█▉        | 782/4000 [3:04:37<12:03:35, 13.49s/it] 20%|█▉        | 783/4000 [3:04:49<11:41:44, 13.09s/it] 20%|█▉        | 784/4000 [3:05:03<12:09:17, 13.61s/it] 20%|█▉        | 785/4000 [3:05:18<12:25:12, 13.91s/it] 20%|█▉        | 786/4000 [3:05:31<12:08:43, 13.60s/it] 20%|█▉        | 787/4000 [3:05:45<12:16:40, 13.76s/it] 20%|█▉        | 788/4000 [3:05:58<12:03:59, 13.52s/it] 20%|█▉        | 789/4000 [3:06:13<12:29:44, 14.01s/it] 20%|█▉        | 790/4000 [3:06:26<12:05:45, 13.57s/it]                                                        20%|█▉        | 790/4000 [3:06:26<12:05:45, 13.57s/it] 20%|█▉        | 791/4000 [3:06:40<12:22:00, 13.87s/it] 20%|█▉        | 792/4000 [3:06:53<12:03:17, 13.53s/it] 20%|█▉        | 793/4000 [3:07:08<12:20:52, 13.86s/it] 20%|█▉        | 794/4000 [3:07:21<12:09:05, 13.64s/it] 20%|█▉        | 795/4000 [3:07:35<12:19:05, 13.84s/it] 20%|█▉        | 796/4000 [3:07:50<12:35:46, 14.15s/it] 20%|█▉        | 797/4000 [3:08:03<12:19:57, 13.86s/it] 20%|█▉        | 798/4000 [3:08:18<12:33:09, 14.11s/it] 20%|█▉        | 799/4000 [3:08:31<12:12:25, 13.73s/it] 20%|██        | 800/4000 [3:08:45<12:22:30, 13.92s/it]                                                        20%|██        | 800/4000 [3:08:45<12:22:30, 13.92s/it] 20%|██        | 801/4000 [3:08:58<12:06:35, 13.63s/it] 20%|██        | 802/4000 [3:09:13<12:29:45, 14.07s/it] 20%|██        | 803/4000 [3:09:26<12:11:51, 13.74s/it] 20%|██        | 804/4000 [3:09:40<12:21:27, 13.92s/it] 20%|██        | 805/4000 [3:09:55<12:36:51, 14.21s/it] 20%|██        | 806/4000 [3:10:08<12:13:01, 13.77s/it] 20%|██        | 807/4000 [3:10:23<12:27:58, 14.06s/it] 20%|██        | 808/4000 [3:10:35<11:58:41, 13.51s/it] 20%|██        | 809/4000 [3:10:50<12:18:26, 13.88s/it] 20%|██        | 810/4000 [3:11:02<11:55:54, 13.47s/it]                                                        20%|██        | 810/4000 [3:11:02<11:55:54, 13.47s/it] 20%|██        | 811/4000 [3:11:17<12:10:11, 13.74s/it] 20%|██        | 812/4000 [3:11:32<12:30:33, 14.13s/it] 20%|██        | 813/4000 [3:11:44<12:09:22, 13.73s/it] 20%|██        | 814/4000 [3:11:59<12:25:02, 14.03s/it] 20%|██        | 815/4000 [3:12:12<12:04:58, 13.66s/it] 20%|██        | 816/4000 [3:12:27<12:23:24, 14.01s/it] 20%|██        | 817/4000 [3:12:41<12:23:22, 14.01s/it] 20%|██        | 818/4000 [3:12:54<12:04:23, 13.66s/it] 20%|██        | 819/4000 [3:13:08<12:19:59, 13.96s/it] 20%|██        | 820/4000 [3:13:21<12:03:07, 13.64s/it]                                                        20%|██        | 820/4000 [3:13:21<12:03:07, 13.64s/it] 21%|██        | 821/4000 [3:13:36<12:16:43, 13.90s/it] 21%|██        | 822/4000 [3:13:49<11:59:39, 13.59s/it] 21%|██        | 823/4000 [3:14:03<12:11:47, 13.82s/it] 21%|██        | 824/4000 [3:14:16<12:00:18, 13.61s/it] 21%|██        | 825/4000 [3:14:31<12:14:05, 13.87s/it] 21%|██        | 826/4000 [3:14:43<11:56:14, 13.54s/it] 21%|██        | 827/4000 [3:14:58<12:15:05, 13.90s/it] 21%|██        | 828/4000 [3:15:11<11:55:25, 13.53s/it] 21%|██        | 829/4000 [3:15:26<12:17:52, 13.96s/it] 21%|██        | 830/4000 [3:15:38<11:52:52, 13.49s/it]                                                        21%|██        | 830/4000 [3:15:38<11:52:52, 13.49s/it] 21%|██        | 831/4000 [3:15:53<12:14:09, 13.90s/it] 21%|██        | 832/4000 [3:16:06<11:54:52, 13.54s/it] 21%|██        | 833/4000 [3:16:20<12:08:44, 13.81s/it] 21%|██        | 834/4000 [3:16:33<11:47:22, 13.41s/it] 21%|██        | 835/4000 [3:16:47<12:04:47, 13.74s/it] 21%|██        | 836/4000 [3:17:00<11:43:44, 13.35s/it] 21%|██        | 837/4000 [3:17:14<11:56:43, 13.60s/it] 21%|██        | 838/4000 [3:17:26<11:42:51, 13.34s/it] 21%|██        | 839/4000 [3:17:41<12:09:23, 13.84s/it] 21%|██        | 840/4000 [3:17:54<11:54:50, 13.57s/it]                                                        21%|██        | 840/4000 [3:17:54<11:54:50, 13.57s/it] 21%|██        | 841/4000 [3:18:09<12:02:57, 13.73s/it] 21%|██        | 842/4000 [3:18:21<11:47:16, 13.44s/it] 21%|██        | 843/4000 [3:18:36<12:03:27, 13.75s/it] 21%|██        | 844/4000 [3:18:51<12:22:08, 14.11s/it] 21%|██        | 845/4000 [3:19:03<11:59:42, 13.69s/it] 21%|██        | 846/4000 [3:19:17<12:05:06, 13.79s/it] 21%|██        | 847/4000 [3:19:30<11:46:50, 13.45s/it] 21%|██        | 848/4000 [3:19:45<12:06:36, 13.83s/it] 21%|██        | 849/4000 [3:19:58<11:53:56, 13.59s/it] 21%|██▏       | 850/4000 [3:20:12<12:08:15, 13.87s/it]                                                        21%|██▏       | 850/4000 [3:20:12<12:08:15, 13.87s/it] 21%|██▏       | 851/4000 [3:20:25<11:46:56, 13.47s/it] 21%|██▏       | 852/4000 [3:20:40<12:07:59, 13.88s/it] 21%|██▏       | 853/4000 [3:20:52<11:45:05, 13.44s/it] 21%|██▏       | 854/4000 [3:21:07<12:01:57, 13.77s/it] 21%|██▏       | 855/4000 [3:21:20<11:49:20, 13.53s/it] 21%|██▏       | 856/4000 [3:21:34<12:06:27, 13.86s/it] 21%|██▏       | 857/4000 [3:21:47<11:51:48, 13.59s/it] 21%|██▏       | 858/4000 [3:22:02<12:06:58, 13.88s/it] 21%|██▏       | 859/4000 [3:22:15<11:49:50, 13.56s/it] 22%|██▏       | 860/4000 [3:22:29<12:01:09, 13.78s/it]                                                        22%|██▏       | 860/4000 [3:22:29<12:01:09, 13.78s/it] 22%|██▏       | 861/4000 [3:22:42<11:46:36, 13.51s/it] 22%|██▏       | 862/4000 [3:22:57<12:10:30, 13.97s/it] 22%|██▏       | 863/4000 [3:23:12<12:22:55, 14.21s/it] 22%|██▏       | 864/4000 [3:23:24<12:00:15, 13.78s/it] 22%|██▏       | 865/4000 [3:23:39<12:14:05, 14.05s/it] 22%|██▏       | 866/4000 [3:23:52<11:54:01, 13.67s/it] 22%|██▏       | 867/4000 [3:24:06<12:08:48, 13.96s/it] 22%|██▏       | 868/4000 [3:24:19<11:49:46, 13.60s/it] 22%|██▏       | 869/4000 [3:24:33<11:58:45, 13.77s/it] 22%|██▏       | 870/4000 [3:24:46<11:38:36, 13.39s/it]                                                        22%|██▏       | 870/4000 [3:24:46<11:38:36, 13.39s/it] 22%|██▏       | 871/4000 [3:25:01<11:57:36, 13.76s/it] 22%|██▏       | 872/4000 [3:25:13<11:42:51, 13.48s/it] 22%|██▏       | 873/4000 [3:25:28<12:01:29, 13.84s/it] 22%|██▏       | 874/4000 [3:25:41<11:45:51, 13.55s/it] 22%|██▏       | 875/4000 [3:25:55<11:58:59, 13.80s/it] 22%|██▏       | 876/4000 [3:26:08<11:37:56, 13.40s/it] 22%|██▏       | 877/4000 [3:26:23<12:02:36, 13.88s/it] 22%|██▏       | 878/4000 [3:26:35<11:40:47, 13.47s/it] 22%|██▏       | 879/4000 [3:26:50<11:53:46, 13.72s/it] 22%|██▏       | 880/4000 [3:27:02<11:37:12, 13.41s/it]                                                        22%|██▏       | 880/4000 [3:27:02<11:37:12, 13.41s/it] 22%|██▏       | 881/4000 [3:27:17<11:56:46, 13.79s/it] 22%|██▏       | 882/4000 [3:27:30<11:43:12, 13.53s/it] 22%|██▏       | 883/4000 [3:27:44<11:56:52, 13.80s/it] 22%|██▏       | 884/4000 [3:27:57<11:39:41, 13.47s/it] 22%|██▏       | 885/4000 [3:28:12<11:57:44, 13.82s/it] 22%|██▏       | 886/4000 [3:28:24<11:37:51, 13.45s/it] 22%|██▏       | 887/4000 [3:28:38<11:48:50, 13.66s/it] 22%|██▏       | 888/4000 [3:28:51<11:31:46, 13.34s/it] 22%|██▏       | 889/4000 [3:29:06<11:52:10, 13.74s/it] 22%|██▏       | 890/4000 [3:29:21<12:15:54, 14.20s/it]                                                        22%|██▏       | 890/4000 [3:29:21<12:15:54, 14.20s/it] 22%|██▏       | 891/4000 [3:29:34<11:51:34, 13.73s/it] 22%|██▏       | 892/4000 [3:29:46<11:30:53, 13.34s/it] 22%|██▏       | 893/4000 [3:30:00<11:48:33, 13.68s/it] 22%|██▏       | 894/4000 [3:30:13<11:29:58, 13.33s/it] 22%|██▏       | 895/4000 [3:30:28<11:52:53, 13.78s/it] 22%|██▏       | 896/4000 [3:30:41<11:36:22, 13.46s/it] 22%|██▏       | 897/4000 [3:30:55<11:58:09, 13.89s/it] 22%|██▏       | 898/4000 [3:31:10<12:04:08, 14.01s/it] 22%|██▏       | 899/4000 [3:31:22<11:43:23, 13.61s/it] 22%|██▎       | 900/4000 [3:31:37<11:59:21, 13.92s/it]                                                        22%|██▎       | 900/4000 [3:31:37<11:59:21, 13.92s/it] 23%|██▎       | 901/4000 [3:31:49<11:36:32, 13.49s/it] 23%|██▎       | 902/4000 [3:32:04<11:55:31, 13.86s/it] 23%|██▎       | 903/4000 [3:32:17<11:34:28, 13.45s/it] 23%|██▎       | 904/4000 [3:32:32<11:56:52, 13.89s/it] 23%|██▎       | 905/4000 [3:32:44<11:35:26, 13.48s/it] 23%|██▎       | 906/4000 [3:32:59<11:50:59, 13.79s/it] 23%|██▎       | 907/4000 [3:33:12<11:40:05, 13.58s/it] 23%|██▎       | 908/4000 [3:33:26<11:51:27, 13.81s/it] 23%|██▎       | 909/4000 [3:33:41<12:06:47, 14.11s/it] 23%|██▎       | 910/4000 [3:33:54<11:46:50, 13.73s/it]                                                        23%|██▎       | 910/4000 [3:33:54<11:46:50, 13.73s/it] 23%|██▎       | 911/4000 [3:34:08<11:52:52, 13.85s/it] 23%|██▎       | 912/4000 [3:34:21<11:36:17, 13.53s/it] 23%|██▎       | 913/4000 [3:34:35<11:55:11, 13.90s/it] 23%|██▎       | 914/4000 [3:34:48<11:38:48, 13.59s/it] 23%|██▎       | 915/4000 [3:35:03<11:54:34, 13.90s/it] 23%|██▎       | 916/4000 [3:35:15<11:32:51, 13.48s/it] 23%|██▎       | 917/4000 [3:35:30<11:55:50, 13.93s/it] 23%|██▎       | 918/4000 [3:35:43<11:31:16, 13.46s/it] 23%|██▎       | 919/4000 [3:35:58<11:53:23, 13.89s/it] 23%|██▎       | 920/4000 [3:36:10<11:35:02, 13.54s/it]                                                        23%|██▎       | 920/4000 [3:36:10<11:35:02, 13.54s/it] 23%|██▎       | 921/4000 [3:36:25<11:49:08, 13.82s/it] 23%|██▎       | 922/4000 [3:36:38<11:31:52, 13.49s/it] 23%|██▎       | 923/4000 [3:36:52<11:48:27, 13.81s/it] 23%|██▎       | 924/4000 [3:37:05<11:26:37, 13.39s/it] 23%|██▎       | 925/4000 [3:37:19<11:49:09, 13.84s/it] 23%|██▎       | 926/4000 [3:37:32<11:34:37, 13.56s/it] 23%|██▎       | 927/4000 [3:37:47<11:46:34, 13.80s/it] 23%|██▎       | 928/4000 [3:37:59<11:30:04, 13.48s/it] 23%|██▎       | 929/4000 [3:38:14<11:47:48, 13.83s/it] 23%|██▎       | 930/4000 [3:38:29<12:05:27, 14.18s/it]                                                        23%|██▎       | 930/4000 [3:38:29<12:05:27, 14.18s/it] 23%|██▎       | 931/4000 [3:38:42<11:38:53, 13.66s/it] 23%|██▎       | 932/4000 [3:38:56<11:55:13, 13.99s/it] 23%|██▎       | 933/4000 [3:39:09<11:36:47, 13.63s/it] 23%|██▎       | 934/4000 [3:39:24<11:51:33, 13.92s/it] 23%|██▎       | 935/4000 [3:39:37<11:35:15, 13.61s/it] 23%|██▎       | 936/4000 [3:39:51<11:50:26, 13.91s/it] 23%|██▎       | 937/4000 [3:40:04<11:26:29, 13.45s/it] 23%|██▎       | 938/4000 [3:40:16<11:11:29, 13.16s/it] 23%|██▎       | 939/4000 [3:40:31<11:37:35, 13.67s/it] 24%|██▎       | 940/4000 [3:40:44<11:22:22, 13.38s/it]                                                        24%|██▎       | 940/4000 [3:40:44<11:22:22, 13.38s/it] 24%|██▎       | 941/4000 [3:40:58<11:33:05, 13.59s/it] 24%|██▎       | 942/4000 [3:41:11<11:21:39, 13.37s/it] 24%|██▎       | 943/4000 [3:41:25<11:37:13, 13.68s/it] 24%|██▎       | 944/4000 [3:41:38<11:27:52, 13.51s/it] 24%|██▎       | 945/4000 [3:41:52<11:35:46, 13.67s/it] 24%|██▎       | 946/4000 [3:42:04<11:16:28, 13.29s/it] 24%|██▎       | 947/4000 [3:42:19<11:31:41, 13.59s/it] 24%|██▎       | 948/4000 [3:42:32<11:26:32, 13.50s/it] 24%|██▎       | 949/4000 [3:42:47<11:45:04, 13.87s/it] 24%|██▍       | 950/4000 [3:43:00<11:28:30, 13.54s/it]                                                        24%|██▍       | 950/4000 [3:43:00<11:28:30, 13.54s/it] 24%|██▍       | 951/4000 [3:43:14<11:41:41, 13.81s/it] 24%|██▍       | 952/4000 [3:43:27<11:24:02, 13.47s/it] 24%|██▍       | 953/4000 [3:43:42<11:45:13, 13.89s/it] 24%|██▍       | 954/4000 [3:43:54<11:25:42, 13.51s/it] 24%|██▍       | 955/4000 [3:44:08<11:36:45, 13.73s/it] 24%|██▍       | 956/4000 [3:44:21<11:23:30, 13.47s/it] 24%|██▍       | 957/4000 [3:44:36<11:42:45, 13.86s/it] 24%|██▍       | 958/4000 [3:44:49<11:28:11, 13.57s/it] 24%|██▍       | 959/4000 [3:45:03<11:42:44, 13.87s/it] 24%|██▍       | 960/4000 [3:45:16<11:19:26, 13.41s/it]                                                        24%|██▍       | 960/4000 [3:45:16<11:19:26, 13.41s/it] 24%|██▍       | 961/4000 [3:45:31<11:42:54, 13.88s/it] 24%|██▍       | 962/4000 [3:45:44<11:26:58, 13.57s/it] 24%|██▍       | 963/4000 [3:45:58<11:40:57, 13.85s/it] 24%|██▍       | 964/4000 [3:46:11<11:28:27, 13.61s/it] 24%|██▍       | 965/4000 [3:46:26<11:44:49, 13.93s/it] 24%|██▍       | 966/4000 [3:46:39<11:31:12, 13.67s/it] 24%|██▍       | 967/4000 [3:46:51<11:12:38, 13.31s/it] 24%|██▍       | 968/4000 [3:47:05<11:22:08, 13.50s/it] 24%|██▍       | 969/4000 [3:47:19<11:30:05, 13.66s/it] 24%|██▍       | 970/4000 [3:47:32<11:18:05, 13.43s/it]                                                        24%|██▍       | 970/4000 [3:47:32<11:18:05, 13.43s/it] 24%|██▍       | 971/4000 [3:47:45<11:04:36, 13.16s/it] 24%|██▍       | 972/4000 [3:48:00<11:29:55, 13.67s/it] 24%|██▍       | 973/4000 [3:48:14<11:43:16, 13.94s/it] 24%|██▍       | 974/4000 [3:48:27<11:23:53, 13.56s/it] 24%|██▍       | 975/4000 [3:48:42<11:42:19, 13.93s/it] 24%|██▍       | 976/4000 [3:48:54<11:24:18, 13.58s/it] 24%|██▍       | 977/4000 [3:49:07<11:02:08, 13.14s/it] 24%|██▍       | 978/4000 [3:49:21<11:27:09, 13.64s/it] 24%|██▍       | 979/4000 [3:49:34<11:12:49, 13.36s/it] 24%|██▍       | 980/4000 [3:49:49<11:30:52, 13.73s/it]                                                        24%|██▍       | 980/4000 [3:49:49<11:30:52, 13.73s/it] 25%|██▍       | 981/4000 [3:50:03<11:45:01, 14.01s/it] 25%|██▍       | 982/4000 [3:50:16<11:29:10, 13.70s/it] 25%|██▍       | 983/4000 [3:50:31<11:43:35, 13.99s/it] 25%|██▍       | 984/4000 [3:50:44<11:25:51, 13.64s/it] 25%|██▍       | 985/4000 [3:50:58<11:39:52, 13.93s/it] 25%|██▍       | 986/4000 [3:51:11<11:19:32, 13.53s/it] 25%|██▍       | 987/4000 [3:51:26<11:34:04, 13.82s/it] 25%|██▍       | 988/4000 [3:51:38<11:20:33, 13.56s/it] 25%|██▍       | 989/4000 [3:51:53<11:31:07, 13.77s/it] 25%|██▍       | 990/4000 [3:52:06<11:16:58, 13.49s/it]                                                        25%|██▍       | 990/4000 [3:52:06<11:16:58, 13.49s/it] 25%|██▍       | 991/4000 [3:52:21<11:38:40, 13.93s/it] 25%|██▍       | 992/4000 [3:52:34<11:27:46, 13.72s/it] 25%|██▍       | 993/4000 [3:52:48<11:39:11, 13.95s/it] 25%|██▍       | 994/4000 [3:53:01<11:21:52, 13.61s/it] 25%|██▍       | 995/4000 [3:53:16<11:35:26, 13.89s/it] 25%|██▍       | 996/4000 [3:53:28<11:17:55, 13.54s/it] 25%|██▍       | 997/4000 [3:53:43<11:29:18, 13.77s/it] 25%|██▍       | 998/4000 [3:53:57<11:44:10, 14.07s/it] 25%|██▍       | 999/4000 [3:54:10<11:24:42, 13.69s/it] 25%|██▌       | 1000/4000 [3:54:25<11:38:35, 13.97s/it]                                                         25%|██▌       | 1000/4000 [3:54:25<11:38:35, 13.97s/it]{'eval_loss': '0.1912', 'eval_runtime': '386.5', 'eval_samples_per_second': '1.301', 'eval_steps_per_second': '1.301', 'epoch': '0.797'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:718: 14%|█▍        | 70/503 [00:54<07:34,  1.05s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:720: 14%|█▍        | 72/503 [00:55<04:47,  1.50it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:721: 15%|█▍        | 73/503 [00:55<04:00,  1.79it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:818: 34%|███▍      | 170/503 [02:11<04:21,  1.27it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:918: 54%|█████▎    | 270/503 [03:27<02:28,  1.57it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:998: 70%|██████▉   | 350/503 [04:28<02:01,  1.25it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:999: 70%|██████▉   | 351/503 [04:28<01:35,  1.59it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1000: 70%|██████▉   | 352/503 [04:28<01:17,  1.95it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1001: 70%|███████   | 353/503 [04:30<02:23,  1.05it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1002: 70%|███████   | 354/503 [04:30<01:51,  1.33it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1015: 73%|███████▎  | 367/503 [04:38<00:55,  2.47it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1017: 73%|███████▎  | 369/503 [04:39<00:49,  2.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1018: 74%|███████▎  | 370/503 [04:39<00:47,  2.80it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1049: 80%|███████▉  | 401/503 [04:55<00:55,  1.84it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1118: 93%|█████████▎| 470/503 [05:46<00:20,  1.62it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1158: 25%|██▌       | 1001/4000 [4:00:53<105:07:07, 126.18s/it] 25%|██▌       | 1002/4000 [4:01:06<76:44:37, 92.15s/it]   25%|██▌       | 1003/4000 [4:01:20<57:18:14, 68.83s/it] 25%|██▌       | 1004/4000 [4:01:32<43:09:25, 51.86s/it] 25%|██▌       | 1005/4000 [4:01:47<33:53:23, 40.74s/it] 25%|██▌       | 1006/4000 [4:02:01<27:14:38, 32.76s/it] 25%|██▌       | 1007/4000 [4:02:14<22:18:51, 26.84s/it] 25%|██▌       | 1008/4000 [4:02:29<19:12:59, 23.12s/it] 25%|██▌       | 1009/4000 [4:02:41<16:36:13, 19.98s/it] 25%|██▌       | 1010/4000 [4:02:56<15:14:04, 18.34s/it]                                                         25%|██▌       | 1010/4000 [4:02:56<15:14:04, 18.34s/it] 25%|██▌       | 1011/4000 [4:03:09<13:50:16, 16.67s/it] 25%|██▌       | 1012/4000 [4:03:21<12:49:34, 15.45s/it] 25%|██▌       | 1013/4000 [4:03:36<12:32:39, 15.12s/it] 25%|██▌       | 1014/4000 [4:03:48<11:52:02, 14.31s/it] 25%|██▌       | 1015/4000 [4:04:03<12:02:30, 14.52s/it] 25%|██▌       | 1016/4000 [4:04:16<11:37:12, 14.02s/it] 25%|██▌       | 1017/4000 [4:04:31<11:47:08, 14.22s/it] 25%|██▌       | 1018/4000 [4:04:45<11:48:11, 14.25s/it] 25%|██▌       | 1019/4000 [4:04:57<11:22:40, 13.74s/it] 26%|██▌       | 1020/4000 [4:05:12<11:38:17, 14.06s/it]                                                         26%|██▌       | 1020/4000 [4:05:12<11:38:17, 14.06s/it] 26%|██▌       | 1021/4000 [4:05:25<11:16:08, 13.62s/it] 26%|██▌       | 1022/4000 [4:05:39<11:29:10, 13.89s/it] 26%|██▌       | 1023/4000 [4:05:52<11:12:19, 13.55s/it] 26%|██▌       | 1024/4000 [4:06:06<11:24:47, 13.81s/it] 26%|██▌       | 1025/4000 [4:06:19<11:05:38, 13.42s/it] 26%|██▌       | 1026/4000 [4:06:34<11:29:44, 13.92s/it] 26%|██▌       | 1027/4000 [4:06:47<11:12:12, 13.57s/it] 26%|██▌       | 1028/4000 [4:07:02<11:28:18, 13.90s/it] 26%|██▌       | 1029/4000 [4:07:14<11:13:42, 13.61s/it] 26%|██▌       | 1030/4000 [4:07:29<11:21:08, 13.76s/it]                                                         26%|██▌       | 1030/4000 [4:07:29<11:21:08, 13.76s/it] 26%|██▌       | 1031/4000 [4:07:41<11:07:04, 13.48s/it] 26%|██▌       | 1032/4000 [4:07:56<11:21:16, 13.77s/it] 26%|██▌       | 1033/4000 [4:08:08<11:01:00, 13.37s/it] 26%|██▌       | 1034/4000 [4:08:21<10:49:17, 13.13s/it] 26%|██▌       | 1035/4000 [4:08:35<11:09:06, 13.54s/it] 26%|██▌       | 1036/4000 [4:08:48<10:50:37, 13.17s/it] 26%|██▌       | 1037/4000 [4:09:02<11:10:24, 13.58s/it] 26%|██▌       | 1038/4000 [4:09:15<10:55:04, 13.27s/it] 26%|██▌       | 1039/4000 [4:09:30<11:18:02, 13.74s/it] 26%|██▌       | 1040/4000 [4:09:44<11:32:33, 14.04s/it]                                                         26%|██▌       | 1040/4000 [4:09:44<11:32:33, 14.04s/it] 26%|██▌       | 1041/4000 [4:09:57<11:14:39, 13.68s/it] 26%|██▌       | 1042/4000 [4:10:12<11:27:45, 13.95s/it] 26%|██▌       | 1043/4000 [4:10:25<11:10:16, 13.60s/it] 26%|██▌       | 1044/4000 [4:10:38<11:12:04, 13.64s/it] 26%|██▌       | 1045/4000 [4:10:51<10:57:00, 13.34s/it] 26%|██▌       | 1046/4000 [4:11:04<10:47:59, 13.16s/it] 26%|██▌       | 1047/4000 [4:11:18<11:06:00, 13.53s/it] 26%|██▌       | 1048/4000 [4:11:30<10:50:04, 13.21s/it] 26%|██▌       | 1049/4000 [4:11:46<11:17:34, 13.78s/it] 26%|██▋       | 1050/4000 [4:11:58<10:59:17, 13.41s/it]                                                         26%|██▋       | 1050/4000 [4:11:58<10:59:17, 13.41s/it] 26%|██▋       | 1051/4000 [4:12:13<11:15:42, 13.75s/it] 26%|██▋       | 1052/4000 [4:12:25<10:52:36, 13.28s/it] 26%|██▋       | 1053/4000 [4:12:40<11:14:56, 13.74s/it] 26%|██▋       | 1054/4000 [4:12:52<11:00:20, 13.45s/it] 26%|██▋       | 1055/4000 [4:13:07<11:14:48, 13.75s/it] 26%|██▋       | 1056/4000 [4:13:19<10:57:42, 13.40s/it] 26%|██▋       | 1057/4000 [4:13:34<11:17:28, 13.81s/it] 26%|██▋       | 1058/4000 [4:13:47<11:01:00, 13.48s/it] 26%|██▋       | 1059/4000 [4:14:02<11:19:54, 13.87s/it] 26%|██▋       | 1060/4000 [4:14:14<11:00:57, 13.49s/it]                                                         26%|██▋       | 1060/4000 [4:14:14<11:00:57, 13.49s/it] 27%|██▋       | 1061/4000 [4:14:29<11:12:27, 13.73s/it] 27%|██▋       | 1062/4000 [4:14:41<10:59:29, 13.47s/it] 27%|██▋       | 1063/4000 [4:14:56<11:12:27, 13.74s/it] 27%|██▋       | 1064/4000 [4:15:08<10:55:50, 13.40s/it] 27%|██▋       | 1065/4000 [4:15:23<11:13:01, 13.76s/it] 27%|██▋       | 1066/4000 [4:15:35<10:50:56, 13.31s/it] 27%|██▋       | 1067/4000 [4:15:50<11:04:17, 13.59s/it] 27%|██▋       | 1068/4000 [4:16:02<10:51:43, 13.34s/it] 27%|██▋       | 1069/4000 [4:16:17<11:08:58, 13.69s/it] 27%|██▋       | 1070/4000 [4:16:29<10:52:40, 13.37s/it]                                                         27%|██▋       | 1070/4000 [4:16:29<10:52:40, 13.37s/it] 27%|██▋       | 1071/4000 [4:16:44<11:07:21, 13.67s/it] 27%|██▋       | 1072/4000 [4:16:57<10:52:32, 13.37s/it] 27%|██▋       | 1073/4000 [4:17:11<11:08:17, 13.70s/it] 27%|██▋       | 1074/4000 [4:17:23<10:50:23, 13.34s/it] 27%|██▋       | 1075/4000 [4:17:38<11:08:29, 13.71s/it] 27%|██▋       | 1076/4000 [4:17:51<11:00:18, 13.55s/it] 27%|██▋       | 1077/4000 [4:18:06<11:15:21, 13.86s/it] 27%|██▋       | 1078/4000 [4:18:18<10:56:51, 13.49s/it] 27%|██▋       | 1079/4000 [4:18:33<11:11:00, 13.78s/it] 27%|██▋       | 1080/4000 [4:18:46<10:58:37, 13.53s/it]                                                         27%|██▋       | 1080/4000 [4:18:46<10:58:37, 13.53s/it] 27%|██▋       | 1081/4000 [4:19:01<11:15:19, 13.88s/it] 27%|██▋       | 1082/4000 [4:19:13<10:53:17, 13.43s/it] 27%|██▋       | 1083/4000 [4:19:28<11:12:51, 13.84s/it] 27%|██▋       | 1084/4000 [4:19:43<11:27:18, 14.14s/it] 27%|██▋       | 1085/4000 [4:19:55<11:08:04, 13.75s/it] 27%|██▋       | 1086/4000 [4:20:09<11:11:53, 13.83s/it] 27%|██▋       | 1087/4000 [4:20:22<10:52:37, 13.44s/it] 27%|██▋       | 1088/4000 [4:20:37<11:13:39, 13.88s/it] 27%|██▋       | 1089/4000 [4:20:49<10:52:09, 13.44s/it] 27%|██▋       | 1090/4000 [4:21:04<11:05:21, 13.72s/it]                                                         27%|██▋       | 1090/4000 [4:21:04<11:05:21, 13.72s/it] 27%|██▋       | 1091/4000 [4:21:16<10:48:34, 13.38s/it] 27%|██▋       | 1092/4000 [4:21:31<11:04:14, 13.71s/it] 27%|██▋       | 1093/4000 [4:21:44<10:55:51, 13.54s/it] 27%|██▋       | 1094/4000 [4:21:58<10:58:22, 13.59s/it] 27%|██▋       | 1095/4000 [4:22:10<10:42:41, 13.27s/it] 27%|██▋       | 1096/4000 [4:22:23<10:34:57, 13.12s/it] 27%|██▋       | 1097/4000 [4:22:37<10:53:31, 13.51s/it] 27%|██▋       | 1098/4000 [4:22:52<11:11:18, 13.88s/it] 27%|██▋       | 1099/4000 [4:23:05<10:51:48, 13.48s/it] 28%|██▊       | 1100/4000 [4:23:19<11:02:18, 13.70s/it]                                                         28%|██▊       | 1100/4000 [4:23:19<11:02:18, 13.70s/it] 28%|██▊       | 1101/4000 [4:23:32<10:48:23, 13.42s/it] 28%|██▊       | 1102/4000 [4:23:46<11:03:09, 13.73s/it] 28%|██▊       | 1103/4000 [4:23:58<10:42:35, 13.31s/it] 28%|██▊       | 1104/4000 [4:24:11<10:37:20, 13.20s/it] 28%|██▊       | 1105/4000 [4:24:26<10:53:59, 13.55s/it] 28%|██▊       | 1106/4000 [4:24:38<10:34:45, 13.16s/it] 28%|██▊       | 1107/4000 [4:24:52<10:51:29, 13.51s/it] 28%|██▊       | 1108/4000 [4:25:05<10:37:08, 13.22s/it] 28%|██▊       | 1109/4000 [4:25:19<10:45:33, 13.40s/it] 28%|██▊       | 1110/4000 [4:25:31<10:33:31, 13.15s/it]                                                         28%|██▊       | 1110/4000 [4:25:31<10:33:31, 13.15s/it] 28%|██▊       | 1111/4000 [4:25:44<10:26:23, 13.01s/it] 28%|██▊       | 1112/4000 [4:25:59<10:53:28, 13.58s/it] 28%|██▊       | 1113/4000 [4:26:13<11:03:48, 13.80s/it] 28%|██▊       | 1114/4000 [4:26:25<10:42:51, 13.37s/it] 28%|██▊       | 1115/4000 [4:26:38<10:30:54, 13.12s/it] 28%|██▊       | 1116/4000 [4:26:53<10:53:53, 13.60s/it] 28%|██▊       | 1117/4000 [4:27:05<10:36:34, 13.25s/it] 28%|██▊       | 1118/4000 [4:27:20<10:53:01, 13.60s/it] 28%|██▊       | 1119/4000 [4:27:34<11:12:02, 14.00s/it] 28%|██▊       | 1120/4000 [4:27:47<10:54:44, 13.64s/it]                                                         28%|██▊       | 1120/4000 [4:27:47<10:54:44, 13.64s/it] 28%|██▊       | 1121/4000 [4:28:00<10:35:16, 13.24s/it] 28%|██▊       | 1122/4000 [4:28:14<10:56:11, 13.68s/it] 28%|██▊       | 1123/4000 [4:28:27<10:38:35, 13.32s/it] 28%|██▊       | 1124/4000 [4:28:41<10:52:15, 13.61s/it] 28%|██▊       | 1125/4000 [4:28:56<11:05:19, 13.88s/it] 28%|██▊       | 1126/4000 [4:29:08<10:51:10, 13.59s/it] 28%|██▊       | 1127/4000 [4:29:21<10:36:25, 13.29s/it] 28%|██▊       | 1128/4000 [4:29:36<10:56:37, 13.72s/it] 28%|██▊       | 1129/4000 [4:29:51<11:14:37, 14.10s/it] 28%|██▊       | 1130/4000 [4:30:03<10:54:09, 13.68s/it]                                                         28%|██▊       | 1130/4000 [4:30:03<10:54:09, 13.68s/it] 28%|██▊       | 1131/4000 [4:30:18<11:04:58, 13.91s/it] 28%|██▊       | 1132/4000 [4:30:31<10:47:54, 13.55s/it] 28%|██▊       | 1133/4000 [4:30:43<10:34:31, 13.28s/it] 28%|██▊       | 1134/4000 [4:30:58<10:58:46, 13.79s/it] 28%|██▊       | 1135/4000 [4:31:13<11:06:40, 13.96s/it] 28%|██▊       | 1136/4000 [4:31:26<10:55:52, 13.74s/it] 28%|██▊       | 1137/4000 [4:31:40<11:02:17, 13.88s/it] 28%|██▊       | 1138/4000 [4:31:53<10:46:25, 13.55s/it] 28%|██▊       | 1139/4000 [4:32:07<11:00:04, 13.84s/it] 28%|██▊       | 1140/4000 [4:32:20<10:44:04, 13.51s/it]                                                         28%|██▊       | 1140/4000 [4:32:20<10:44:04, 13.51s/it] 29%|██▊       | 1141/4000 [4:32:35<11:02:41, 13.91s/it] 29%|██▊       | 1142/4000 [4:32:50<11:14:21, 14.16s/it] 29%|██▊       | 1143/4000 [4:33:02<10:52:43, 13.71s/it] 29%|██▊       | 1144/4000 [4:33:17<11:04:40, 13.96s/it] 29%|██▊       | 1145/4000 [4:33:29<10:42:11, 13.50s/it] 29%|██▊       | 1146/4000 [4:33:44<10:57:42, 13.83s/it] 29%|██▊       | 1147/4000 [4:33:57<10:41:20, 13.49s/it] 29%|██▊       | 1148/4000 [4:34:12<11:02:04, 13.93s/it] 29%|██▊       | 1149/4000 [4:34:26<11:09:24, 14.09s/it] 29%|██▉       | 1150/4000 [4:34:39<10:47:01, 13.62s/it]                                                         29%|██▉       | 1150/4000 [4:34:39<10:47:01, 13.62s/it] 29%|██▉       | 1151/4000 [4:34:53<11:02:11, 13.95s/it] 29%|██▉       | 1152/4000 [4:35:06<10:46:03, 13.61s/it] 29%|██▉       | 1153/4000 [4:35:21<11:03:11, 13.98s/it] 29%|██▉       | 1154/4000 [4:35:33<10:40:36, 13.51s/it] 29%|██▉       | 1155/4000 [4:35:48<10:59:41, 13.91s/it] 29%|██▉       | 1156/4000 [4:36:00<10:36:39, 13.43s/it] 29%|██▉       | 1157/4000 [4:36:13<10:28:21, 13.26s/it] 29%|██▉       | 1158/4000 [4:36:28<10:45:35, 13.63s/it] 29%|██▉       | 1159/4000 [4:36:40<10:31:32, 13.34s/it] 29%|██▉       | 1160/4000 [4:36:56<10:55:53, 13.86s/it]                                                         29%|██▉       | 1160/4000 [4:36:56<10:55:53, 13.86s/it] 29%|██▉       | 1161/4000 [4:37:09<10:56:18, 13.87s/it] 29%|██▉       | 1162/4000 [4:37:22<10:41:10, 13.56s/it] 29%|██▉       | 1163/4000 [4:37:37<10:54:50, 13.85s/it] 29%|██▉       | 1164/4000 [4:37:50<10:42:37, 13.60s/it] 29%|██▉       | 1165/4000 [4:38:04<10:51:20, 13.79s/it] 29%|██▉       | 1166/4000 [4:38:17<10:37:28, 13.50s/it] 29%|██▉       | 1167/4000 [4:38:32<10:58:37, 13.95s/it] 29%|██▉       | 1168/4000 [4:38:44<10:31:50, 13.39s/it] 29%|██▉       | 1169/4000 [4:38:59<10:50:32, 13.79s/it] 29%|██▉       | 1170/4000 [4:39:11<10:34:39, 13.46s/it]                                                         29%|██▉       | 1170/4000 [4:39:11<10:34:39, 13.46s/it] 29%|██▉       | 1171/4000 [4:39:26<10:53:30, 13.86s/it] 29%|██▉       | 1172/4000 [4:39:39<10:34:56, 13.47s/it] 29%|██▉       | 1173/4000 [4:39:53<10:51:49, 13.83s/it] 29%|██▉       | 1174/4000 [4:40:06<10:32:57, 13.44s/it] 29%|██▉       | 1175/4000 [4:40:20<10:47:58, 13.76s/it] 29%|██▉       | 1176/4000 [4:40:33<10:33:41, 13.46s/it] 29%|██▉       | 1177/4000 [4:40:48<10:47:30, 13.76s/it] 29%|██▉       | 1178/4000 [4:41:00<10:28:06, 13.35s/it] 29%|██▉       | 1179/4000 [4:41:15<10:47:09, 13.76s/it] 30%|██▉       | 1180/4000 [4:41:27<10:30:12, 13.41s/it]                                                         30%|██▉       | 1180/4000 [4:41:27<10:30:12, 13.41s/it] 30%|██▉       | 1181/4000 [4:41:42<10:48:55, 13.81s/it] 30%|██▉       | 1182/4000 [4:41:57<11:02:48, 14.11s/it] 30%|██▉       | 1183/4000 [4:42:09<10:40:49, 13.65s/it] 30%|██▉       | 1184/4000 [4:42:24<10:54:13, 13.94s/it] 30%|██▉       | 1185/4000 [4:42:37<10:38:23, 13.61s/it] 30%|██▉       | 1186/4000 [4:42:52<10:56:25, 14.00s/it] 30%|██▉       | 1187/4000 [4:43:04<10:32:17, 13.49s/it] 30%|██▉       | 1188/4000 [4:43:19<10:46:43, 13.80s/it] 30%|██▉       | 1189/4000 [4:43:31<10:29:46, 13.44s/it] 30%|██▉       | 1190/4000 [4:43:46<10:49:54, 13.88s/it]                                                         30%|██▉       | 1190/4000 [4:43:46<10:49:54, 13.88s/it] 30%|██▉       | 1191/4000 [4:43:59<10:36:39, 13.60s/it] 30%|██▉       | 1192/4000 [4:44:14<10:51:15, 13.92s/it] 30%|██▉       | 1193/4000 [4:44:28<11:01:41, 14.14s/it] 30%|██▉       | 1194/4000 [4:44:41<10:42:11, 13.73s/it] 30%|██▉       | 1195/4000 [4:44:56<10:53:18, 13.97s/it] 30%|██▉       | 1196/4000 [4:45:08<10:32:27, 13.53s/it] 30%|██▉       | 1197/4000 [4:45:23<10:48:50, 13.89s/it] 30%|██▉       | 1198/4000 [4:45:36<10:39:28, 13.69s/it] 30%|██▉       | 1199/4000 [4:45:51<10:56:01, 14.05s/it] 30%|███       | 1200/4000 [4:46:04<10:34:05, 13.59s/it]                                                         30%|███       | 1200/4000 [4:46:04<10:34:05, 13.59s/it] 30%|███       | 1201/4000 [4:46:18<10:42:58, 13.78s/it] 30%|███       | 1202/4000 [4:46:30<10:25:48, 13.42s/it] 30%|███       | 1203/4000 [4:46:45<10:38:21, 13.69s/it] 30%|███       | 1204/4000 [4:46:59<10:52:34, 14.00s/it] 30%|███       | 1205/4000 [4:47:12<10:25:55, 13.44s/it] 30%|███       | 1206/4000 [4:47:26<10:41:06, 13.77s/it] 30%|███       | 1207/4000 [4:47:39<10:28:45, 13.51s/it] 30%|███       | 1208/4000 [4:47:54<10:43:20, 13.83s/it] 30%|███       | 1209/4000 [4:48:06<10:24:04, 13.42s/it] 30%|███       | 1210/4000 [4:48:20<10:32:21, 13.60s/it]                                                         30%|███       | 1210/4000 [4:48:20<10:32:21, 13.60s/it] 30%|███       | 1211/4000 [4:48:33<10:19:55, 13.34s/it] 30%|███       | 1212/4000 [4:48:48<10:40:17, 13.78s/it] 30%|███       | 1213/4000 [4:49:01<10:30:02, 13.56s/it] 30%|███       | 1214/4000 [4:49:15<10:44:42, 13.88s/it] 30%|███       | 1215/4000 [4:49:28<10:25:42, 13.48s/it] 30%|███       | 1216/4000 [4:49:42<10:40:30, 13.80s/it] 30%|███       | 1217/4000 [4:49:55<10:23:12, 13.44s/it] 30%|███       | 1218/4000 [4:50:10<10:41:35, 13.84s/it] 30%|███       | 1219/4000 [4:50:23<10:26:58, 13.53s/it] 30%|███       | 1220/4000 [4:50:37<10:41:31, 13.85s/it]                                                         30%|███       | 1220/4000 [4:50:37<10:41:31, 13.85s/it] 31%|███       | 1221/4000 [4:50:52<10:55:26, 14.15s/it] 31%|███       | 1222/4000 [4:51:05<10:36:02, 13.74s/it] 31%|███       | 1223/4000 [4:51:20<10:49:55, 14.04s/it] 31%|███       | 1224/4000 [4:51:32<10:29:43, 13.61s/it] 31%|███       | 1225/4000 [4:51:46<10:39:18, 13.82s/it] 31%|███       | 1226/4000 [4:51:59<10:23:51, 13.49s/it] 31%|███       | 1227/4000 [4:52:14<10:38:24, 13.81s/it] 31%|███       | 1228/4000 [4:52:26<10:20:45, 13.44s/it] 31%|███       | 1229/4000 [4:52:41<10:37:34, 13.81s/it] 31%|███       | 1230/4000 [4:52:56<10:48:58, 14.06s/it]                                                         31%|███       | 1230/4000 [4:52:56<10:48:58, 14.06s/it] 31%|███       | 1231/4000 [4:53:08<10:31:52, 13.69s/it] 31%|███       | 1232/4000 [4:53:23<10:42:22, 13.92s/it] 31%|███       | 1233/4000 [4:53:36<10:25:11, 13.56s/it] 31%|███       | 1234/4000 [4:53:50<10:41:34, 13.92s/it] 31%|███       | 1235/4000 [4:54:03<10:26:13, 13.59s/it] 31%|███       | 1236/4000 [4:54:17<10:35:30, 13.80s/it] 31%|███       | 1237/4000 [4:54:30<10:20:38, 13.48s/it] 31%|███       | 1238/4000 [4:54:45<10:43:20, 13.98s/it] 31%|███       | 1239/4000 [4:55:00<10:46:53, 14.06s/it] 31%|███       | 1240/4000 [4:55:12<10:29:11, 13.68s/it]                                                         31%|███       | 1240/4000 [4:55:12<10:29:11, 13.68s/it] 31%|███       | 1241/4000 [4:55:25<10:09:11, 13.25s/it] 31%|███       | 1242/4000 [4:55:40<10:32:08, 13.75s/it] 31%|███       | 1243/4000 [4:55:52<10:17:07, 13.43s/it] 31%|███       | 1244/4000 [4:56:07<10:35:48, 13.84s/it] 31%|███       | 1245/4000 [4:56:22<10:51:22, 14.19s/it] 31%|███       | 1246/4000 [4:56:35<10:30:35, 13.74s/it] 31%|███       | 1247/4000 [4:56:49<10:35:51, 13.86s/it] 31%|███       | 1248/4000 [4:57:02<10:21:40, 13.55s/it] 31%|███       | 1249/4000 [4:57:16<10:34:49, 13.85s/it] 31%|███▏      | 1250/4000 [4:57:29<10:17:57, 13.48s/it]                                                         31%|███▏      | 1250/4000 [4:57:29<10:17:57, 13.48s/it] 31%|███▏      | 1251/4000 [4:57:43<10:33:26, 13.83s/it] 31%|███▏      | 1252/4000 [4:57:56<10:20:37, 13.55s/it] 31%|███▏      | 1253/4000 [4:58:11<10:32:11, 13.81s/it] 31%|███▏      | 1254/4000 [4:58:24<10:19:36, 13.54s/it] 31%|███▏      | 1255/4000 [4:58:38<10:26:16, 13.69s/it] 31%|███▏      | 1256/4000 [4:58:42<8:11:14, 10.74s/it]  31%|███▏      | 1257/4000 [4:58:57<9:09:10, 12.01s/it] 31%|███▏      | 1258/4000 [4:59:09<9:15:46, 12.16s/it] 31%|███▏      | 1259/4000 [4:59:24<9:50:51, 12.93s/it] 32%|███▏      | 1260/4000 [4:59:38<10:13:25, 13.43s/it]                                                         32%|███▏      | 1260/4000 [4:59:38<10:13:25, 13.43s/it] 32%|███▏      | 1261/4000 [4:59:51<10:05:56, 13.27s/it] 32%|███▏      | 1262/4000 [5:00:06<10:25:44, 13.71s/it] 32%|███▏      | 1263/4000 [5:00:18<10:06:46, 13.30s/it] 32%|███▏      | 1264/4000 [5:00:33<10:28:14, 13.78s/it] 32%|███▏      | 1265/4000 [5:00:46<10:13:41, 13.46s/it] 32%|███▏      | 1266/4000 [5:01:01<10:33:40, 13.91s/it] 32%|███▏      | 1267/4000 [5:01:15<10:36:56, 13.98s/it] 32%|███▏      | 1268/4000 [5:01:27<10:14:09, 13.49s/it] 32%|███▏      | 1269/4000 [5:01:40<10:05:49, 13.31s/it] 32%|███▏      | 1270/4000 [5:01:55<10:22:20, 13.68s/it]                                                         32%|███▏      | 1270/4000 [5:01:55<10:22:20, 13.68s/it] 32%|███▏      | 1271/4000 [5:02:08<10:08:48, 13.39s/it] 32%|███▏      | 1272/4000 [5:02:22<10:22:20, 13.69s/it] 32%|███▏      | 1273/4000 [5:02:34<10:05:26, 13.32s/it] 32%|███▏      | 1274/4000 [5:02:50<10:28:53, 13.84s/it] 32%|███▏      | 1275/4000 [5:03:02<10:15:04, 13.54s/it] 32%|███▏      | 1276/4000 [5:03:17<10:29:01, 13.86s/it] 32%|███▏      | 1277/4000 [5:03:29<10:08:54, 13.42s/it] 32%|███▏      | 1278/4000 [5:03:44<10:25:24, 13.79s/it] 32%|███▏      | 1279/4000 [5:03:56<10:05:32, 13.35s/it] 32%|███▏      | 1280/4000 [5:04:11<10:24:34, 13.78s/it]                                                         32%|███▏      | 1280/4000 [5:04:11<10:24:34, 13.78s/it] 32%|███▏      | 1281/4000 [5:04:26<10:36:50, 14.05s/it] 32%|███▏      | 1282/4000 [5:04:38<10:07:36, 13.41s/it] 32%|███▏      | 1283/4000 [5:04:53<10:27:37, 13.86s/it] 32%|███▏      | 1284/4000 [5:05:05<10:05:31, 13.38s/it] 32%|███▏      | 1285/4000 [5:05:19<10:20:00, 13.70s/it] 32%|███▏      | 1286/4000 [5:05:32<10:07:12, 13.42s/it] 32%|███▏      | 1287/4000 [5:05:47<10:27:25, 13.88s/it] 32%|███▏      | 1288/4000 [5:06:00<10:16:52, 13.65s/it] 32%|███▏      | 1289/4000 [5:06:15<10:26:06, 13.86s/it] 32%|███▏      | 1290/4000 [5:06:27<10:11:55, 13.55s/it]                                                         32%|███▏      | 1290/4000 [5:06:27<10:11:55, 13.55s/it] 32%|███▏      | 1291/4000 [5:06:42<10:25:03, 13.84s/it] 32%|███▏      | 1292/4000 [5:06:57<10:36:50, 14.11s/it] 32%|███▏      | 1293/4000 [5:07:10<10:22:46, 13.80s/it] 32%|███▏      | 1294/4000 [5:07:24<10:28:05, 13.93s/it] 32%|███▏      | 1295/4000 [5:07:37<10:14:54, 13.64s/it] 32%|███▏      | 1296/4000 [5:07:51<10:27:19, 13.92s/it] 32%|███▏      | 1297/4000 [5:08:04<10:12:40, 13.60s/it] 32%|███▏      | 1298/4000 [5:08:19<10:32:31, 14.05s/it] 32%|███▏      | 1299/4000 [5:08:34<10:36:50, 14.15s/it] 32%|███▎      | 1300/4000 [5:08:47<10:18:07, 13.74s/it]                                                         32%|███▎      | 1300/4000 [5:08:47<10:18:07, 13.74s/it] 33%|███▎      | 1301/4000 [5:09:01<10:28:47, 13.98s/it] 33%|███▎      | 1302/4000 [5:09:13<10:04:16, 13.44s/it] 33%|███▎      | 1303/4000 [5:09:28<10:21:00, 13.82s/it] 33%|███▎      | 1304/4000 [5:09:41<10:07:30, 13.52s/it] 33%|███▎      | 1305/4000 [5:09:55<10:19:06, 13.78s/it] 33%|███▎      | 1306/4000 [5:10:08<10:09:36, 13.58s/it] 33%|███▎      | 1307/4000 [5:10:23<10:26:45, 13.96s/it] 33%|███▎      | 1308/4000 [5:10:38<10:39:24, 14.25s/it] 33%|███▎      | 1309/4000 [5:10:51<10:15:12, 13.72s/it] 33%|███▎      | 1310/4000 [5:11:03<9:58:02, 13.34s/it]                                                         33%|███▎      | 1310/4000 [5:11:03<9:58:02, 13.34s/it] 33%|███▎      | 1311/4000 [5:11:17<10:12:30, 13.67s/it] 33%|███▎      | 1312/4000 [5:11:30<10:00:43, 13.41s/it] 33%|███▎      | 1313/4000 [5:11:45<10:19:16, 13.83s/it] 33%|███▎      | 1314/4000 [5:12:00<10:35:42, 14.20s/it] 33%|███▎      | 1315/4000 [5:12:13<10:16:05, 13.77s/it] 33%|███▎      | 1316/4000 [5:12:27<10:24:57, 13.97s/it] 33%|███▎      | 1317/4000 [5:12:42<10:34:59, 14.20s/it] 33%|███▎      | 1318/4000 [5:12:55<10:18:51, 13.84s/it] 33%|███▎      | 1319/4000 [5:13:10<10:31:25, 14.13s/it] 33%|███▎      | 1320/4000 [5:13:22<10:05:58, 13.57s/it]                                                         33%|███▎      | 1320/4000 [5:13:22<10:05:58, 13.57s/it] 33%|███▎      | 1321/4000 [5:13:35<9:54:52, 13.32s/it]  33%|███▎      | 1322/4000 [5:13:49<10:03:55, 13.53s/it] 33%|███▎      | 1323/4000 [5:14:02<9:53:13, 13.30s/it]  33%|███▎      | 1324/4000 [5:14:16<10:08:16, 13.64s/it] 33%|███▎      | 1325/4000 [5:14:29<9:56:27, 13.38s/it]  33%|███▎      | 1326/4000 [5:14:43<10:10:43, 13.70s/it] 33%|███▎      | 1327/4000 [5:14:58<10:18:21, 13.88s/it] 33%|███▎      | 1328/4000 [5:15:10<10:04:26, 13.57s/it] 33%|███▎      | 1329/4000 [5:15:25<10:19:35, 13.92s/it] 33%|███▎      | 1330/4000 [5:15:38<10:03:09, 13.55s/it]                                                         33%|███▎      | 1330/4000 [5:15:38<10:03:09, 13.55s/it] 33%|███▎      | 1331/4000 [5:15:52<10:13:13, 13.79s/it] 33%|███▎      | 1332/4000 [5:16:05<9:58:16, 13.45s/it]  33%|███▎      | 1333/4000 [5:16:19<10:10:56, 13.74s/it] 33%|███▎      | 1334/4000 [5:16:32<9:56:01, 13.41s/it]  33%|███▎      | 1335/4000 [5:16:47<10:13:10, 13.80s/it] 33%|███▎      | 1336/4000 [5:17:02<10:29:46, 14.18s/it] 33%|███▎      | 1337/4000 [5:17:15<10:13:41, 13.83s/it] 33%|███▎      | 1338/4000 [5:17:29<10:20:42, 13.99s/it] 33%|███▎      | 1339/4000 [5:17:42<10:02:28, 13.58s/it] 34%|███▎      | 1340/4000 [5:17:56<10:17:12, 13.92s/it]                                                         34%|███▎      | 1340/4000 [5:17:56<10:17:12, 13.92s/it] 34%|███▎      | 1341/4000 [5:18:09<10:03:54, 13.63s/it] 34%|███▎      | 1342/4000 [5:18:24<10:19:43, 13.99s/it] 34%|███▎      | 1343/4000 [5:18:39<10:26:07, 14.14s/it] 34%|███▎      | 1344/4000 [5:18:51<10:04:53, 13.66s/it] 34%|███▎      | 1345/4000 [5:19:04<9:50:16, 13.34s/it]  34%|███▎      | 1346/4000 [5:19:19<10:08:17, 13.75s/it] 34%|███▎      | 1347/4000 [5:19:31<9:52:04, 13.39s/it]  34%|███▎      | 1348/4000 [5:19:46<10:06:57, 13.73s/it] 34%|███▎      | 1349/4000 [5:20:00<10:14:36, 13.91s/it] 34%|███▍      | 1350/4000 [5:20:13<9:59:33, 13.57s/it]                                                         34%|███▍      | 1350/4000 [5:20:13<9:59:33, 13.57s/it] 34%|███▍      | 1351/4000 [5:20:27<10:11:22, 13.85s/it] 34%|███▍      | 1352/4000 [5:20:40<9:54:39, 13.47s/it]  34%|███▍      | 1353/4000 [5:20:55<10:10:52, 13.85s/it] 34%|███▍      | 1354/4000 [5:21:07<9:57:29, 13.55s/it]  34%|███▍      | 1355/4000 [5:21:22<10:09:00, 13.81s/it] 34%|███▍      | 1356/4000 [5:21:35<9:54:19, 13.49s/it]  34%|███▍      | 1357/4000 [5:21:49<10:11:45, 13.89s/it] 34%|███▍      | 1358/4000 [5:22:02<9:53:18, 13.47s/it]  34%|███▍      | 1359/4000 [5:22:17<10:12:45, 13.92s/it] 34%|███▍      | 1360/4000 [5:22:31<10:19:44, 14.09s/it]                                                         34%|███▍      | 1360/4000 [5:22:31<10:19:44, 14.09s/it] 34%|███▍      | 1361/4000 [5:22:44<9:58:26, 13.61s/it]  34%|███▍      | 1362/4000 [5:22:58<10:04:21, 13.75s/it] 34%|███▍      | 1363/4000 [5:23:11<9:55:30, 13.55s/it]  34%|███▍      | 1364/4000 [5:23:25<10:06:57, 13.82s/it] 34%|███▍      | 1365/4000 [5:23:40<10:21:56, 14.16s/it] 34%|███▍      | 1366/4000 [5:23:53<10:00:54, 13.69s/it] 34%|███▍      | 1367/4000 [5:24:08<10:12:03, 13.95s/it] 34%|███▍      | 1368/4000 [5:24:20<9:58:06, 13.63s/it]  34%|███▍      | 1369/4000 [5:24:35<10:07:16, 13.85s/it] 34%|███▍      | 1370/4000 [5:24:47<9:49:30, 13.45s/it]                                                         34%|███▍      | 1370/4000 [5:24:47<9:49:30, 13.45s/it] 34%|███▍      | 1371/4000 [5:25:01<9:54:45, 13.57s/it] 34%|███▍      | 1372/4000 [5:25:14<9:46:33, 13.39s/it] 34%|███▍      | 1373/4000 [5:25:29<10:06:43, 13.86s/it] 34%|███▍      | 1374/4000 [5:25:42<9:47:53, 13.43s/it]  34%|███▍      | 1375/4000 [5:25:56<10:03:36, 13.80s/it] 34%|███▍      | 1376/4000 [5:26:09<9:49:27, 13.48s/it]  34%|███▍      | 1377/4000 [5:26:24<10:10:54, 13.97s/it] 34%|███▍      | 1378/4000 [5:26:39<10:18:25, 14.15s/it] 34%|███▍      | 1379/4000 [5:26:51<9:53:58, 13.60s/it]  34%|███▍      | 1380/4000 [5:27:04<9:41:26, 13.32s/it]                                                        34%|███▍      | 1380/4000 [5:27:04<9:41:26, 13.32s/it] 35%|███▍      | 1381/4000 [5:27:17<9:48:28, 13.48s/it] 35%|███▍      | 1382/4000 [5:27:30<9:42:16, 13.34s/it] 35%|███▍      | 1383/4000 [5:27:45<9:56:05, 13.67s/it] 35%|███▍      | 1384/4000 [5:27:58<9:45:37, 13.43s/it] 35%|███▍      | 1385/4000 [5:28:13<10:06:21, 13.91s/it] 35%|███▍      | 1386/4000 [5:28:27<10:09:16, 13.98s/it] 35%|███▍      | 1387/4000 [5:28:40<9:57:14, 13.71s/it]  35%|███▍      | 1388/4000 [5:28:54<10:06:32, 13.93s/it] 35%|███▍      | 1389/4000 [5:29:08<9:56:59, 13.72s/it]  35%|███▍      | 1390/4000 [5:29:22<10:05:54, 13.93s/it]                                                         35%|███▍      | 1390/4000 [5:29:22<10:05:54, 13.93s/it] 35%|███▍      | 1391/4000 [5:29:34<9:43:09, 13.41s/it]  35%|███▍      | 1392/4000 [5:29:49<10:00:18, 13.81s/it] 35%|███▍      | 1393/4000 [5:30:02<9:44:48, 13.46s/it]  35%|███▍      | 1394/4000 [5:30:17<10:03:03, 13.88s/it] 35%|███▍      | 1395/4000 [5:30:29<9:49:24, 13.58s/it]  35%|███▍      | 1396/4000 [5:30:44<10:03:32, 13.91s/it] 35%|███▍      | 1397/4000 [5:30:59<10:14:21, 14.16s/it] 35%|███▍      | 1398/4000 [5:31:12<9:57:43, 13.78s/it]  35%|███▍      | 1399/4000 [5:31:26<10:04:57, 13.96s/it] 35%|███▌      | 1400/4000 [5:31:39<9:53:19, 13.69s/it]                                                         35%|███▌      | 1400/4000 [5:31:39<9:53:19, 13.69s/it] 35%|███▌      | 1401/4000 [5:31:54<10:05:44, 13.98s/it] 35%|███▌      | 1402/4000 [5:32:07<9:48:37, 13.59s/it]  35%|███▌      | 1403/4000 [5:32:21<10:03:20, 13.94s/it] 35%|███▌      | 1404/4000 [5:32:34<9:41:12, 13.43s/it]  35%|███▌      | 1405/4000 [5:32:48<9:49:48, 13.64s/it] 35%|███▌      | 1406/4000 [5:33:01<9:41:30, 13.45s/it] 35%|███▌      | 1407/4000 [5:33:15<9:57:30, 13.83s/it] 35%|███▌      | 1408/4000 [5:33:30<10:11:07, 14.15s/it] 35%|███▌      | 1409/4000 [5:33:42<9:45:53, 13.57s/it]  35%|███▌      | 1410/4000 [5:33:57<9:56:42, 13.82s/it]                                                        35%|███▌      | 1410/4000 [5:33:57<9:56:42, 13.82s/it] 35%|███▌      | 1411/4000 [5:34:10<9:42:19, 13.50s/it] 35%|███▌      | 1412/4000 [5:34:24<9:58:26, 13.87s/it] 35%|███▌      | 1413/4000 [5:34:37<9:42:00, 13.50s/it] 35%|███▌      | 1414/4000 [5:34:51<9:52:50, 13.75s/it] 35%|███▌      | 1415/4000 [5:35:04<9:41:37, 13.50s/it] 35%|███▌      | 1416/4000 [5:35:19<9:54:24, 13.80s/it] 35%|███▌      | 1417/4000 [5:35:33<10:04:54, 14.05s/it] 35%|███▌      | 1418/4000 [5:35:46<9:42:23, 13.53s/it]  35%|███▌      | 1419/4000 [5:35:59<9:33:06, 13.32s/it] 36%|███▌      | 1420/4000 [5:36:13<9:49:27, 13.71s/it]                                                        36%|███▌      | 1420/4000 [5:36:13<9:49:27, 13.71s/it] 36%|███▌      | 1421/4000 [5:36:26<9:32:24, 13.32s/it] 36%|███▌      | 1422/4000 [5:36:40<9:50:19, 13.74s/it] 36%|███▌      | 1423/4000 [5:36:55<9:56:34, 13.89s/it] 36%|███▌      | 1424/4000 [5:37:08<9:44:24, 13.61s/it] 36%|███▌      | 1425/4000 [5:37:22<9:58:06, 13.94s/it] 36%|███▌      | 1426/4000 [5:37:35<9:43:14, 13.60s/it] 36%|███▌      | 1427/4000 [5:37:48<9:33:28, 13.37s/it] 36%|███▌      | 1428/4000 [5:38:02<9:47:08, 13.70s/it] 36%|███▌      | 1429/4000 [5:38:15<9:34:44, 13.41s/it] 36%|███▌      | 1430/4000 [5:38:29<9:45:42, 13.67s/it]                                                        36%|███▌      | 1430/4000 [5:38:29<9:45:42, 13.67s/it] 36%|███▌      | 1431/4000 [5:38:42<9:28:18, 13.27s/it] 36%|███▌      | 1432/4000 [5:38:57<9:48:56, 13.76s/it] 36%|███▌      | 1433/4000 [5:39:09<9:29:31, 13.31s/it] 36%|███▌      | 1434/4000 [5:39:23<9:42:19, 13.62s/it] 36%|███▌      | 1435/4000 [5:39:36<9:29:39, 13.33s/it] 36%|███▌      | 1436/4000 [5:39:50<9:42:46, 13.64s/it] 36%|███▌      | 1437/4000 [5:40:03<9:29:22, 13.33s/it] 36%|███▌      | 1438/4000 [5:40:17<9:45:21, 13.71s/it] 36%|███▌      | 1439/4000 [5:40:30<9:30:04, 13.36s/it] 36%|███▌      | 1440/4000 [5:40:44<9:44:22, 13.70s/it]                                                        36%|███▌      | 1440/4000 [5:40:44<9:44:22, 13.70s/it] 36%|███▌      | 1441/4000 [5:40:57<9:27:41, 13.31s/it] 36%|███▌      | 1442/4000 [5:41:12<9:45:15, 13.73s/it] 36%|███▌      | 1443/4000 [5:41:24<9:25:02, 13.26s/it] 36%|███▌      | 1444/4000 [5:41:38<9:44:08, 13.71s/it] 36%|███▌      | 1445/4000 [5:41:51<9:23:45, 13.24s/it] 36%|███▌      | 1446/4000 [5:42:05<9:42:06, 13.68s/it] 36%|███▌      | 1447/4000 [5:42:18<9:27:23, 13.33s/it] 36%|███▌      | 1448/4000 [5:42:32<9:38:30, 13.60s/it] 36%|███▌      | 1449/4000 [5:42:44<9:23:19, 13.25s/it] 36%|███▋      | 1450/4000 [5:42:59<9:43:04, 13.72s/it]                                                        36%|███▋      | 1450/4000 [5:42:59<9:43:04, 13.72s/it] 36%|███▋      | 1451/4000 [5:43:12<9:33:29, 13.50s/it] 36%|███▋      | 1452/4000 [5:43:27<9:48:23, 13.86s/it] 36%|███▋      | 1453/4000 [5:43:40<9:32:18, 13.48s/it] 36%|███▋      | 1454/4000 [5:43:54<9:40:48, 13.69s/it] 36%|███▋      | 1455/4000 [5:44:06<9:21:30, 13.24s/it] 36%|███▋      | 1456/4000 [5:44:21<9:42:06, 13.73s/it] 36%|███▋      | 1457/4000 [5:44:33<9:26:40, 13.37s/it] 36%|███▋      | 1458/4000 [5:44:48<9:42:48, 13.76s/it] 36%|███▋      | 1459/4000 [5:45:01<9:27:48, 13.41s/it] 36%|███▋      | 1460/4000 [5:45:15<9:45:25, 13.83s/it]                                                        36%|███▋      | 1460/4000 [5:45:15<9:45:25, 13.83s/it] 37%|███▋      | 1461/4000 [5:45:28<9:30:12, 13.47s/it] 37%|███▋      | 1462/4000 [5:45:43<9:42:49, 13.78s/it] 37%|███▋      | 1463/4000 [5:45:56<9:32:16, 13.53s/it] 37%|███▋      | 1464/4000 [5:46:10<9:41:30, 13.76s/it] 37%|███▋      | 1465/4000 [5:46:23<9:33:19, 13.57s/it] 37%|███▋      | 1466/4000 [5:46:37<9:45:52, 13.87s/it] 37%|███▋      | 1467/4000 [5:46:50<9:30:42, 13.52s/it] 37%|███▋      | 1468/4000 [5:47:05<9:44:56, 13.86s/it] 37%|███▋      | 1469/4000 [5:47:18<9:30:40, 13.53s/it] 37%|███▋      | 1470/4000 [5:47:32<9:47:13, 13.93s/it]                                                        37%|███▋      | 1470/4000 [5:47:32<9:47:13, 13.93s/it] 37%|███▋      | 1471/4000 [5:47:45<9:25:16, 13.41s/it] 37%|███▋      | 1472/4000 [5:47:59<9:39:42, 13.76s/it] 37%|███▋      | 1473/4000 [5:48:12<9:22:00, 13.34s/it] 37%|███▋      | 1474/4000 [5:48:26<9:39:07, 13.76s/it] 37%|███▋      | 1475/4000 [5:48:39<9:26:26, 13.46s/it] 37%|███▋      | 1476/4000 [5:48:53<9:37:18, 13.72s/it] 37%|███▋      | 1477/4000 [5:49:08<9:52:05, 14.08s/it] 37%|███▋      | 1478/4000 [5:49:21<9:29:29, 13.55s/it] 37%|███▋      | 1479/4000 [5:49:36<9:46:22, 13.96s/it] 37%|███▋      | 1480/4000 [5:49:48<9:26:28, 13.49s/it]                                                        37%|███▋      | 1480/4000 [5:49:48<9:26:28, 13.49s/it] 37%|███▋      | 1481/4000 [5:50:02<9:33:57, 13.67s/it] 37%|███▋      | 1482/4000 [5:50:15<9:27:32, 13.52s/it] 37%|███▋      | 1483/4000 [5:50:30<9:38:26, 13.79s/it] 37%|███▋      | 1484/4000 [5:50:42<9:24:02, 13.45s/it] 37%|███▋      | 1485/4000 [5:50:57<9:34:50, 13.71s/it] 37%|███▋      | 1486/4000 [5:51:09<9:18:59, 13.34s/it] 37%|███▋      | 1487/4000 [5:51:24<9:32:54, 13.68s/it] 37%|███▋      | 1488/4000 [5:51:36<9:22:42, 13.44s/it] 37%|███▋      | 1489/4000 [5:51:51<9:41:17, 13.89s/it] 37%|███▋      | 1490/4000 [5:52:06<9:44:12, 13.97s/it]                                                        37%|███▋      | 1490/4000 [5:52:06<9:44:12, 13.97s/it] 37%|███▋      | 1491/4000 [5:52:18<9:30:03, 13.63s/it] 37%|███▋      | 1492/4000 [5:52:33<9:40:32, 13.89s/it] 37%|███▋      | 1493/4000 [5:52:46<9:27:09, 13.57s/it] 37%|███▋      | 1494/4000 [5:53:00<9:40:29, 13.90s/it] 37%|███▋      | 1495/4000 [5:53:13<9:28:51, 13.63s/it] 37%|███▋      | 1496/4000 [5:53:28<9:45:36, 14.03s/it] 37%|███▋      | 1497/4000 [5:53:41<9:28:28, 13.63s/it] 37%|███▋      | 1498/4000 [5:53:56<9:40:32, 13.92s/it] 37%|███▋      | 1499/4000 [5:54:09<9:27:13, 13.61s/it] 38%|███▊      | 1500/4000 [5:54:21<9:17:33, 13.38s/it]                                                        38%|███▊      | 1500/4000 [5:54:21<9:17:33, 13.38s/it]{'eval_loss': '0.1665', 'eval_runtime': '371.2', 'eval_samples_per_second': '1.355', 'eval_steps_per_second': '1.355', 'epoch': '1.593'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1165:{'loss': '1.193', 'grad_norm': '0.3786', 'learning_rate': '0.0001719', 'epoch': '1.705'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1167:{'loss': '1.304', 'grad_norm': '0.3502', 'learning_rate': '0.0001708', 'epoch': '1.736'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1168:{'loss': '1.307', 'grad_norm': '0.3685', 'learning_rate': '0.0001702', 'epoch': '1.752'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1176:{'loss': '1.295', 'grad_norm': '0.3702', 'learning_rate': '0.0001654', 'epoch': '1.88'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1191:{'loss': '1.224', 'grad_norm': '0.3188', 'learning_rate': '0.0001558', 'epoch': '2.118'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1192:{'loss': '1.136', 'grad_norm': '0.2821', 'learning_rate': '0.0001551', 'epoch': '2.134'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1255:  9%|▉         | 47/503 [00:34<04:27,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1278: 14%|█▍        | 70/503 [00:53<04:21,  1.66it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1279: 14%|█▍        | 71/503 [00:55<07:49,  1.09s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1280: 14%|█▍        | 72/503 [00:55<06:07,  1.17it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1281: 15%|█▍        | 73/503 [00:55<04:56,  1.45it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1367: 32%|███▏      | 159/503 [02:04<03:22,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1378: 34%|███▍      | 170/503 [02:13<03:44,  1.48it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1478: 54%|█████▎    | 270/503 [03:33<03:22,  1.15it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1557: 70%|██████▉   | 350/503 [04:33<02:04,  1.23it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1558: 70%|██████▉   | 351/503 [04:34<01:42,  1.48it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1559: 70%|██████▉   | 352/503 [04:34<01:26,  1.75it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1560: 70%|███████   | 353/503 [04:36<02:39,  1.06s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1561: 70%|███████   | 354/503 [04:37<02:06,  1.18it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1577: 74%|███████▎  | 370/503 [04:49<01:51,  1.19it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1659: 90%|████████▉ | 452/503 [05:52<00:55,  1.09s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1677: 93%|█████████▎| 470/503 [06:05<00:21,  1.51it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1717: 38%|███▊      | 1501/4000 [6:01:11<91:42:32, 132.11s/it] 38%|███▊      | 1502/4000 [6:01:24<66:53:15, 96.40s/it]  38%|███▊      | 1503/4000 [6:01:36<49:26:19, 71.28s/it] 38%|███▊      | 1504/4000 [6:01:51<37:33:34, 54.17s/it] 38%|███▊      | 1505/4000 [6:02:05<29:18:58, 42.30s/it] 38%|███▊      | 1506/4000 [6:02:18<23:08:57, 33.42s/it] 38%|███▊      | 1507/4000 [6:02:32<19:14:40, 27.79s/it] 38%|███▊      | 1508/4000 [6:02:45<16:02:27, 23.17s/it] 38%|███▊      | 1509/4000 [6:03:00<14:17:40, 20.66s/it] 38%|███▊      | 1510/4000 [6:03:12<12:38:35, 18.28s/it]                                                         38%|███▊      | 1510/4000 [6:03:12<12:38:35, 18.28s/it] 38%|███▊      | 1511/4000 [6:03:27<11:55:13, 17.24s/it] 38%|███▊      | 1512/4000 [6:03:40<11:02:55, 15.99s/it] 38%|███▊      | 1513/4000 [6:03:54<10:34:33, 15.31s/it] 38%|███▊      | 1514/4000 [6:04:06<9:59:21, 14.47s/it]  38%|███▊      | 1515/4000 [6:04:22<10:06:29, 14.64s/it] 38%|███▊      | 1516/4000 [6:04:34<9:37:49, 13.96s/it]  38%|███▊      | 1517/4000 [6:04:48<9:45:26, 14.15s/it] 38%|███▊      | 1518/4000 [6:05:01<9:24:25, 13.64s/it] 38%|███▊      | 1519/4000 [6:05:16<9:38:25, 13.99s/it] 38%|███▊      | 1520/4000 [6:05:28<9:22:13, 13.60s/it]                                                        38%|███▊      | 1520/4000 [6:05:28<9:22:13, 13.60s/it] 38%|███▊      | 1521/4000 [6:05:43<9:32:42, 13.86s/it] 38%|███▊      | 1522/4000 [6:05:56<9:18:34, 13.52s/it] 38%|███▊      | 1523/4000 [6:06:10<9:31:49, 13.85s/it] 38%|███▊      | 1524/4000 [6:06:25<9:44:12, 14.16s/it] 38%|███▊      | 1525/4000 [6:06:38<9:22:54, 13.65s/it] 38%|███▊      | 1526/4000 [6:06:52<9:36:29, 13.98s/it] 38%|███▊      | 1527/4000 [6:07:05<9:20:31, 13.60s/it] 38%|███▊      | 1528/4000 [6:07:20<9:36:53, 14.00s/it] 38%|███▊      | 1529/4000 [6:07:35<9:46:17, 14.24s/it] 38%|███▊      | 1530/4000 [6:07:47<9:25:09, 13.73s/it]                                                        38%|███▊      | 1530/4000 [6:07:47<9:25:09, 13.73s/it] 38%|███▊      | 1531/4000 [6:08:02<9:37:16, 14.03s/it] 38%|███▊      | 1532/4000 [6:08:15<9:17:58, 13.56s/it] 38%|███▊      | 1533/4000 [6:08:29<9:33:08, 13.94s/it] 38%|███▊      | 1534/4000 [6:08:42<9:18:36, 13.59s/it] 38%|███▊      | 1535/4000 [6:08:55<9:06:20, 13.30s/it] 38%|███▊      | 1536/4000 [6:09:09<9:19:54, 13.63s/it] 38%|███▊      | 1537/4000 [6:09:21<9:03:33, 13.24s/it] 38%|███▊      | 1538/4000 [6:09:36<9:16:16, 13.56s/it] 38%|███▊      | 1539/4000 [6:09:48<9:05:32, 13.30s/it] 38%|███▊      | 1540/4000 [6:10:03<9:20:00, 13.66s/it]                                                        38%|███▊      | 1540/4000 [6:10:03<9:20:00, 13.66s/it] 39%|███▊      | 1541/4000 [6:10:15<9:03:42, 13.27s/it] 39%|███▊      | 1542/4000 [6:10:30<9:24:15, 13.77s/it] 39%|███▊      | 1543/4000 [6:10:43<9:13:39, 13.52s/it] 39%|███▊      | 1544/4000 [6:10:58<9:28:02, 13.88s/it] 39%|███▊      | 1545/4000 [6:11:10<9:11:40, 13.48s/it] 39%|███▊      | 1546/4000 [6:11:25<9:25:59, 13.84s/it] 39%|███▊      | 1547/4000 [6:11:38<9:14:28, 13.56s/it] 39%|███▊      | 1548/4000 [6:11:53<9:27:34, 13.89s/it] 39%|███▊      | 1549/4000 [6:12:05<9:12:06, 13.52s/it] 39%|███▉      | 1550/4000 [6:12:20<9:25:08, 13.84s/it]                                                        39%|███▉      | 1550/4000 [6:12:20<9:25:08, 13.84s/it] 39%|███▉      | 1551/4000 [6:12:35<9:35:51, 14.11s/it] 39%|███▉      | 1552/4000 [6:12:48<9:21:19, 13.76s/it] 39%|███▉      | 1553/4000 [6:13:02<9:32:10, 14.03s/it] 39%|███▉      | 1554/4000 [6:13:15<9:18:33, 13.70s/it] 39%|███▉      | 1555/4000 [6:13:30<9:28:55, 13.96s/it] 39%|███▉      | 1556/4000 [6:13:42<9:12:11, 13.56s/it] 39%|███▉      | 1557/4000 [6:13:57<9:30:07, 14.00s/it] 39%|███▉      | 1558/4000 [6:14:10<9:17:50, 13.71s/it] 39%|███▉      | 1559/4000 [6:14:26<9:33:45, 14.10s/it] 39%|███▉      | 1560/4000 [6:14:38<9:09:08, 13.50s/it]                                                        39%|███▉      | 1560/4000 [6:14:38<9:09:08, 13.50s/it] 39%|███▉      | 1561/4000 [6:14:52<9:22:38, 13.84s/it] 39%|███▉      | 1562/4000 [6:15:05<9:08:27, 13.50s/it] 39%|███▉      | 1563/4000 [6:15:19<9:18:22, 13.75s/it] 39%|███▉      | 1564/4000 [6:15:32<9:05:19, 13.43s/it] 39%|███▉      | 1565/4000 [6:15:46<9:13:03, 13.63s/it] 39%|███▉      | 1566/4000 [6:15:59<9:05:57, 13.46s/it] 39%|███▉      | 1567/4000 [6:16:13<9:16:00, 13.71s/it] 39%|███▉      | 1568/4000 [6:16:26<9:05:10, 13.45s/it] 39%|███▉      | 1569/4000 [6:16:39<8:59:34, 13.32s/it] 39%|███▉      | 1570/4000 [6:16:54<9:11:06, 13.61s/it]                                                        39%|███▉      | 1570/4000 [6:16:54<9:11:06, 13.61s/it] 39%|███▉      | 1571/4000 [6:17:06<9:01:05, 13.37s/it] 39%|███▉      | 1572/4000 [6:17:21<9:12:31, 13.65s/it] 39%|███▉      | 1573/4000 [6:17:33<9:02:14, 13.41s/it] 39%|███▉      | 1574/4000 [6:17:48<9:12:39, 13.67s/it] 39%|███▉      | 1575/4000 [6:18:01<9:05:09, 13.49s/it] 39%|███▉      | 1576/4000 [6:18:16<9:22:31, 13.92s/it] 39%|███▉      | 1577/4000 [6:18:30<9:31:24, 14.15s/it] 39%|███▉      | 1578/4000 [6:18:43<9:12:23, 13.68s/it] 39%|███▉      | 1579/4000 [6:18:58<9:22:33, 13.94s/it] 40%|███▉      | 1580/4000 [6:19:11<9:11:20, 13.67s/it]                                                        40%|███▉      | 1580/4000 [6:19:11<9:11:20, 13.67s/it] 40%|███▉      | 1581/4000 [6:19:23<8:56:34, 13.31s/it] 40%|███▉      | 1582/4000 [6:19:38<9:10:17, 13.65s/it] 40%|███▉      | 1583/4000 [6:19:50<8:59:57, 13.40s/it] 40%|███▉      | 1584/4000 [6:20:04<9:06:33, 13.57s/it] 40%|███▉      | 1585/4000 [6:20:18<9:05:04, 13.54s/it] 40%|███▉      | 1586/4000 [6:20:33<9:21:05, 13.95s/it] 40%|███▉      | 1587/4000 [6:20:45<9:06:21, 13.59s/it] 40%|███▉      | 1588/4000 [6:20:59<9:11:24, 13.72s/it] 40%|███▉      | 1589/4000 [6:21:12<8:58:59, 13.41s/it] 40%|███▉      | 1590/4000 [6:21:27<9:11:03, 13.72s/it]                                                        40%|███▉      | 1590/4000 [6:21:27<9:11:03, 13.72s/it] 40%|███▉      | 1591/4000 [6:21:39<8:53:06, 13.28s/it] 40%|███▉      | 1592/4000 [6:21:54<9:11:57, 13.75s/it] 40%|███▉      | 1593/4000 [6:22:06<8:58:26, 13.42s/it] 40%|███▉      | 1594/4000 [6:22:21<9:15:26, 13.85s/it] 40%|███▉      | 1595/4000 [6:22:34<9:01:18, 13.50s/it] 40%|███▉      | 1596/4000 [6:22:49<9:14:06, 13.83s/it] 40%|███▉      | 1597/4000 [6:23:02<9:06:45, 13.65s/it] 40%|███▉      | 1598/4000 [6:23:16<9:13:43, 13.83s/it] 40%|███▉      | 1599/4000 [6:23:29<9:04:57, 13.62s/it] 40%|████      | 1600/4000 [6:23:43<9:06:39, 13.67s/it]                                                        40%|████      | 1600/4000 [6:23:43<9:06:39, 13.67s/it] 40%|████      | 1601/4000 [6:23:56<9:00:44, 13.52s/it] 40%|████      | 1602/4000 [6:24:10<9:08:48, 13.73s/it] 40%|████      | 1603/4000 [6:24:23<9:01:18, 13.55s/it] 40%|████      | 1604/4000 [6:24:38<9:18:27, 13.98s/it] 40%|████      | 1605/4000 [6:24:50<8:52:31, 13.34s/it] 40%|████      | 1606/4000 [6:25:05<9:10:02, 13.79s/it] 40%|████      | 1607/4000 [6:25:17<8:50:01, 13.29s/it] 40%|████      | 1608/4000 [6:25:32<9:09:53, 13.79s/it] 40%|████      | 1609/4000 [6:25:45<8:57:55, 13.50s/it] 40%|████      | 1610/4000 [6:25:59<9:03:21, 13.64s/it]                                                        40%|████      | 1610/4000 [6:25:59<9:03:21, 13.64s/it] 40%|████      | 1611/4000 [6:26:12<8:57:28, 13.50s/it] 40%|████      | 1612/4000 [6:26:27<9:11:11, 13.85s/it] 40%|████      | 1613/4000 [6:26:40<8:59:54, 13.57s/it] 40%|████      | 1614/4000 [6:26:54<9:11:18, 13.86s/it] 40%|████      | 1615/4000 [6:27:09<9:20:02, 14.09s/it] 40%|████      | 1616/4000 [6:27:22<9:03:40, 13.68s/it] 40%|████      | 1617/4000 [6:27:36<9:11:14, 13.88s/it] 40%|████      | 1618/4000 [6:27:49<9:02:07, 13.66s/it] 40%|████      | 1619/4000 [6:28:04<9:13:08, 13.94s/it] 40%|████      | 1620/4000 [6:28:17<9:01:25, 13.65s/it]                                                        40%|████      | 1620/4000 [6:28:17<9:01:25, 13.65s/it] 41%|████      | 1621/4000 [6:28:31<9:11:28, 13.91s/it] 41%|████      | 1622/4000 [6:28:44<8:59:31, 13.61s/it] 41%|████      | 1623/4000 [6:28:59<9:08:49, 13.85s/it] 41%|████      | 1624/4000 [6:29:11<8:56:07, 13.54s/it] 41%|████      | 1625/4000 [6:29:26<9:06:43, 13.81s/it] 41%|████      | 1626/4000 [6:29:39<8:55:03, 13.52s/it] 41%|████      | 1627/4000 [6:29:54<9:14:05, 14.01s/it] 41%|████      | 1628/4000 [6:30:08<9:17:05, 14.09s/it] 41%|████      | 1629/4000 [6:30:21<9:03:46, 13.76s/it] 41%|████      | 1630/4000 [6:30:35<9:10:05, 13.93s/it]                                                        41%|████      | 1630/4000 [6:30:35<9:10:05, 13.93s/it] 41%|████      | 1631/4000 [6:30:49<9:02:06, 13.73s/it] 41%|████      | 1632/4000 [6:31:03<9:08:00, 13.89s/it] 41%|████      | 1633/4000 [6:31:15<8:52:16, 13.49s/it] 41%|████      | 1634/4000 [6:31:31<9:12:58, 14.02s/it] 41%|████      | 1635/4000 [6:31:45<9:18:07, 14.16s/it] 41%|████      | 1636/4000 [6:31:58<9:03:40, 13.80s/it] 41%|████      | 1637/4000 [6:32:10<8:39:54, 13.20s/it] 41%|████      | 1638/4000 [6:32:25<9:00:04, 13.72s/it] 41%|████      | 1639/4000 [6:32:37<8:46:32, 13.38s/it] 41%|████      | 1640/4000 [6:32:52<9:01:14, 13.76s/it]                                                        41%|████      | 1640/4000 [6:32:52<9:01:14, 13.76s/it] 41%|████      | 1641/4000 [6:33:05<8:51:43, 13.52s/it] 41%|████      | 1642/4000 [6:33:20<9:03:58, 13.84s/it] 41%|████      | 1643/4000 [6:33:33<8:52:56, 13.57s/it] 41%|████      | 1644/4000 [6:33:47<9:06:14, 13.91s/it] 41%|████      | 1645/4000 [6:34:00<8:54:54, 13.63s/it] 41%|████      | 1646/4000 [6:34:15<9:07:47, 13.96s/it] 41%|████      | 1647/4000 [6:34:27<8:47:41, 13.46s/it] 41%|████      | 1648/4000 [6:34:42<9:07:03, 13.96s/it] 41%|████      | 1649/4000 [6:34:56<9:07:42, 13.98s/it] 41%|████▏     | 1650/4000 [6:35:10<8:57:37, 13.73s/it]                                                        41%|████▏     | 1650/4000 [6:35:10<8:57:37, 13.73s/it] 41%|████▏     | 1651/4000 [6:35:22<8:43:40, 13.38s/it] 41%|████▏     | 1652/4000 [6:35:37<9:01:31, 13.84s/it] 41%|████▏     | 1653/4000 [6:35:50<8:51:38, 13.59s/it] 41%|████▏     | 1654/4000 [6:36:04<9:00:24, 13.82s/it] 41%|████▏     | 1655/4000 [6:36:20<9:15:24, 14.21s/it] 41%|████▏     | 1656/4000 [6:36:32<8:56:28, 13.73s/it] 41%|████▏     | 1657/4000 [6:36:47<9:07:33, 14.02s/it] 41%|████▏     | 1658/4000 [6:37:01<9:12:21, 14.15s/it] 41%|████▏     | 1659/4000 [6:37:15<9:03:51, 13.94s/it] 42%|████▏     | 1660/4000 [6:37:29<9:12:16, 14.16s/it]                                                        42%|████▏     | 1660/4000 [6:37:29<9:12:16, 14.16s/it] 42%|████▏     | 1661/4000 [6:37:43<9:00:48, 13.87s/it] 42%|████▏     | 1662/4000 [6:37:56<8:50:14, 13.61s/it] 42%|████▏     | 1663/4000 [6:38:10<9:00:33, 13.88s/it] 42%|████▏     | 1664/4000 [6:38:25<9:11:33, 14.17s/it] 42%|████▏     | 1665/4000 [6:38:37<8:44:46, 13.48s/it] 42%|████▏     | 1666/4000 [6:38:52<8:59:54, 13.88s/it] 42%|████▏     | 1667/4000 [6:39:04<8:42:35, 13.44s/it] 42%|████▏     | 1668/4000 [6:39:19<9:02:00, 13.95s/it] 42%|████▏     | 1669/4000 [6:39:32<8:52:53, 13.72s/it] 42%|████▏     | 1670/4000 [6:39:47<8:58:31, 13.87s/it]                                                        42%|████▏     | 1670/4000 [6:39:47<8:58:31, 13.87s/it] 42%|████▏     | 1671/4000 [6:40:00<8:47:40, 13.59s/it] 42%|████▏     | 1672/4000 [6:40:14<8:58:35, 13.88s/it] 42%|████▏     | 1673/4000 [6:40:27<8:51:09, 13.70s/it] 42%|████▏     | 1674/4000 [6:40:42<8:56:11, 13.83s/it] 42%|████▏     | 1675/4000 [6:40:55<8:50:19, 13.69s/it] 42%|████▏     | 1676/4000 [6:41:10<9:07:05, 14.12s/it] 42%|████▏     | 1677/4000 [6:41:23<8:50:07, 13.69s/it] 42%|████▏     | 1678/4000 [6:41:37<9:01:40, 14.00s/it] 42%|████▏     | 1679/4000 [6:41:50<8:41:13, 13.47s/it] 42%|████▏     | 1680/4000 [6:42:03<8:36:06, 13.35s/it]                                                        42%|████▏     | 1680/4000 [6:42:03<8:36:06, 13.35s/it] 42%|████▏     | 1681/4000 [6:42:17<8:48:15, 13.67s/it] 42%|████▏     | 1682/4000 [6:42:32<9:03:44, 14.07s/it] 42%|████▏     | 1683/4000 [6:42:45<8:50:31, 13.74s/it] 42%|████▏     | 1684/4000 [6:43:00<8:58:33, 13.95s/it] 42%|████▏     | 1685/4000 [6:43:13<8:48:10, 13.69s/it] 42%|████▏     | 1686/4000 [6:43:27<8:56:06, 13.90s/it] 42%|████▏     | 1687/4000 [6:43:40<8:43:04, 13.57s/it] 42%|████▏     | 1688/4000 [6:43:54<8:49:50, 13.75s/it] 42%|████▏     | 1689/4000 [6:44:07<8:37:48, 13.44s/it] 42%|████▏     | 1690/4000 [6:44:21<8:50:59, 13.79s/it]                                                        42%|████▏     | 1690/4000 [6:44:21<8:50:59, 13.79s/it] 42%|████▏     | 1691/4000 [6:44:37<9:06:51, 14.21s/it] 42%|████▏     | 1692/4000 [6:44:50<8:54:05, 13.88s/it] 42%|████▏     | 1693/4000 [6:45:04<8:57:51, 13.99s/it] 42%|████▏     | 1694/4000 [6:45:17<8:47:58, 13.74s/it] 42%|████▏     | 1695/4000 [6:45:31<8:55:20, 13.94s/it] 42%|████▏     | 1696/4000 [6:45:44<8:35:24, 13.42s/it] 42%|████▏     | 1697/4000 [6:45:58<8:45:36, 13.69s/it] 42%|████▏     | 1698/4000 [6:46:11<8:38:13, 13.51s/it] 42%|████▏     | 1699/4000 [6:46:26<8:50:23, 13.83s/it] 42%|████▎     | 1700/4000 [6:46:38<8:28:01, 13.25s/it]                                                        42%|████▎     | 1700/4000 [6:46:38<8:28:01, 13.25s/it] 43%|████▎     | 1701/4000 [6:46:53<8:51:09, 13.86s/it] 43%|████▎     | 1702/4000 [6:47:06<8:38:36, 13.54s/it] 43%|████▎     | 1703/4000 [6:47:21<8:54:10, 13.95s/it] 43%|████▎     | 1704/4000 [6:47:33<8:35:01, 13.46s/it] 43%|████▎     | 1705/4000 [6:47:48<8:54:41, 13.98s/it] 43%|████▎     | 1706/4000 [6:48:01<8:40:20, 13.61s/it] 43%|████▎     | 1707/4000 [6:48:15<8:47:44, 13.81s/it] 43%|████▎     | 1708/4000 [6:48:30<9:01:09, 14.17s/it] 43%|████▎     | 1709/4000 [6:48:42<8:36:35, 13.53s/it] 43%|████▎     | 1710/4000 [6:48:55<8:33:54, 13.46s/it]                                                        43%|████▎     | 1710/4000 [6:48:55<8:33:54, 13.46s/it] 43%|████▎     | 1711/4000 [6:49:10<8:46:33, 13.80s/it] 43%|████▎     | 1712/4000 [6:49:23<8:32:52, 13.45s/it] 43%|████▎     | 1713/4000 [6:49:38<8:52:07, 13.96s/it] 43%|████▎     | 1714/4000 [6:49:50<8:33:46, 13.49s/it] 43%|████▎     | 1715/4000 [6:50:05<8:49:38, 13.91s/it] 43%|████▎     | 1716/4000 [6:50:17<8:30:20, 13.41s/it] 43%|████▎     | 1717/4000 [6:50:32<8:45:58, 13.82s/it] 43%|████▎     | 1718/4000 [6:50:45<8:33:37, 13.50s/it] 43%|████▎     | 1719/4000 [6:50:59<8:41:27, 13.72s/it] 43%|████▎     | 1720/4000 [6:51:12<8:36:54, 13.60s/it]                                                        43%|████▎     | 1720/4000 [6:51:12<8:36:54, 13.60s/it] 43%|████▎     | 1721/4000 [6:51:26<8:41:56, 13.74s/it] 43%|████▎     | 1722/4000 [6:51:39<8:28:53, 13.40s/it] 43%|████▎     | 1723/4000 [6:51:53<8:39:20, 13.68s/it] 43%|████▎     | 1724/4000 [6:52:07<8:33:18, 13.53s/it] 43%|████▎     | 1725/4000 [6:52:21<8:44:15, 13.83s/it] 43%|████▎     | 1726/4000 [6:52:34<8:32:32, 13.52s/it] 43%|████▎     | 1727/4000 [6:52:47<8:29:24, 13.45s/it] 43%|████▎     | 1728/4000 [6:53:02<8:40:08, 13.74s/it] 43%|████▎     | 1729/4000 [6:53:17<8:58:32, 14.23s/it] 43%|████▎     | 1730/4000 [6:53:29<8:36:40, 13.66s/it]                                                        43%|████▎     | 1730/4000 [6:53:29<8:36:40, 13.66s/it] 43%|████▎     | 1731/4000 [6:53:45<8:56:02, 14.17s/it] 43%|████▎     | 1732/4000 [6:53:57<8:38:35, 13.72s/it] 43%|████▎     | 1733/4000 [6:54:12<8:50:17, 14.04s/it] 43%|████▎     | 1734/4000 [6:54:25<8:35:59, 13.66s/it] 43%|████▎     | 1735/4000 [6:54:39<8:46:11, 13.94s/it] 43%|████▎     | 1736/4000 [6:54:53<8:38:13, 13.73s/it] 43%|████▎     | 1737/4000 [6:55:07<8:43:29, 13.88s/it] 43%|████▎     | 1738/4000 [6:55:20<8:32:01, 13.58s/it] 43%|████▎     | 1739/4000 [6:55:34<8:41:04, 13.83s/it] 44%|████▎     | 1740/4000 [6:55:50<8:57:29, 14.27s/it]                                                        44%|████▎     | 1740/4000 [6:55:50<8:57:29, 14.27s/it] 44%|████▎     | 1741/4000 [6:56:03<8:49:19, 14.06s/it] 44%|████▎     | 1742/4000 [6:56:16<8:36:59, 13.74s/it] 44%|████▎     | 1743/4000 [6:56:29<8:29:35, 13.55s/it] 44%|████▎     | 1744/4000 [6:56:44<8:38:32, 13.79s/it] 44%|████▎     | 1745/4000 [6:56:56<8:27:36, 13.51s/it] 44%|████▎     | 1746/4000 [6:57:11<8:35:24, 13.72s/it] 44%|████▎     | 1747/4000 [6:57:23<8:23:50, 13.42s/it] 44%|████▎     | 1748/4000 [6:57:38<8:35:27, 13.73s/it] 44%|████▎     | 1749/4000 [6:57:51<8:28:00, 13.54s/it] 44%|████▍     | 1750/4000 [6:58:06<8:45:00, 14.00s/it]                                                        44%|████▍     | 1750/4000 [6:58:06<8:45:00, 14.00s/it] 44%|████▍     | 1751/4000 [6:58:21<8:52:48, 14.21s/it] 44%|████▍     | 1752/4000 [6:58:34<8:41:23, 13.92s/it] 44%|████▍     | 1753/4000 [6:58:47<8:30:03, 13.62s/it] 44%|████▍     | 1754/4000 [6:59:02<8:43:37, 13.99s/it] 44%|████▍     | 1755/4000 [6:59:13<8:16:39, 13.27s/it] 44%|████▍     | 1756/4000 [6:59:29<8:38:39, 13.87s/it] 44%|████▍     | 1757/4000 [6:59:44<8:50:30, 14.19s/it] 44%|████▍     | 1758/4000 [6:59:56<8:35:48, 13.80s/it] 44%|████▍     | 1759/4000 [7:00:08<8:16:11, 13.28s/it] 44%|████▍     | 1760/4000 [7:00:24<8:38:35, 13.89s/it]                                                        44%|████▍     | 1760/4000 [7:00:24<8:38:35, 13.89s/it] 44%|████▍     | 1761/4000 [7:00:36<8:21:33, 13.44s/it] 44%|████▍     | 1762/4000 [7:00:51<8:40:59, 13.97s/it] 44%|████▍     | 1763/4000 [7:01:05<8:41:12, 13.98s/it] 44%|████▍     | 1764/4000 [7:01:19<8:35:05, 13.82s/it] 44%|████▍     | 1765/4000 [7:01:33<8:43:06, 14.04s/it] 44%|████▍     | 1766/4000 [7:01:46<8:27:44, 13.64s/it] 44%|████▍     | 1767/4000 [7:02:01<8:41:00, 14.00s/it] 44%|████▍     | 1768/4000 [7:02:13<8:22:07, 13.50s/it] 44%|████▍     | 1769/4000 [7:02:28<8:41:23, 14.02s/it] 44%|████▍     | 1770/4000 [7:02:41<8:21:57, 13.51s/it]                                                        44%|████▍     | 1770/4000 [7:02:41<8:21:57, 13.51s/it] 44%|████▍     | 1771/4000 [7:02:54<8:14:49, 13.32s/it] 44%|████▍     | 1772/4000 [7:03:09<8:35:39, 13.89s/it] 44%|████▍     | 1773/4000 [7:03:23<8:37:50, 13.95s/it] 44%|████▍     | 1774/4000 [7:03:36<8:23:11, 13.56s/it] 44%|████▍     | 1775/4000 [7:03:50<8:28:41, 13.72s/it] 44%|████▍     | 1776/4000 [7:04:03<8:22:23, 13.55s/it] 44%|████▍     | 1777/4000 [7:04:17<8:32:24, 13.83s/it] 44%|████▍     | 1778/4000 [7:04:30<8:24:07, 13.61s/it] 44%|████▍     | 1779/4000 [7:04:46<8:39:41, 14.04s/it] 44%|████▍     | 1780/4000 [7:04:58<8:25:56, 13.67s/it]                                                        44%|████▍     | 1780/4000 [7:04:58<8:25:56, 13.67s/it] 45%|████▍     | 1781/4000 [7:05:13<8:33:21, 13.88s/it] 45%|████▍     | 1782/4000 [7:05:25<8:16:19, 13.43s/it] 45%|████▍     | 1783/4000 [7:05:40<8:31:12, 13.84s/it] 45%|████▍     | 1784/4000 [7:05:53<8:22:37, 13.61s/it] 45%|████▍     | 1785/4000 [7:06:06<8:12:18, 13.34s/it] 45%|████▍     | 1786/4000 [7:06:20<8:26:31, 13.73s/it] 45%|████▍     | 1787/4000 [7:06:33<8:11:34, 13.33s/it] 45%|████▍     | 1788/4000 [7:06:48<8:32:53, 13.91s/it] 45%|████▍     | 1789/4000 [7:07:02<8:36:19, 14.01s/it] 45%|████▍     | 1790/4000 [7:07:14<8:15:36, 13.46s/it]                                                        45%|████▍     | 1790/4000 [7:07:14<8:15:36, 13.46s/it] 45%|████▍     | 1791/4000 [7:07:27<8:07:17, 13.24s/it] 45%|████▍     | 1792/4000 [7:07:42<8:24:38, 13.71s/it] 45%|████▍     | 1793/4000 [7:07:57<8:36:36, 14.04s/it] 45%|████▍     | 1794/4000 [7:08:09<8:18:18, 13.55s/it] 45%|████▍     | 1795/4000 [7:08:24<8:32:59, 13.96s/it] 45%|████▍     | 1796/4000 [7:08:36<8:07:36, 13.27s/it] 45%|████▍     | 1797/4000 [7:08:49<8:03:34, 13.17s/it] 45%|████▍     | 1798/4000 [7:09:04<8:22:30, 13.69s/it] 45%|████▍     | 1799/4000 [7:09:16<8:07:10, 13.28s/it] 45%|████▌     | 1800/4000 [7:09:31<8:23:17, 13.73s/it]                                                        45%|████▌     | 1800/4000 [7:09:31<8:23:17, 13.73s/it] 45%|████▌     | 1801/4000 [7:09:43<8:11:30, 13.41s/it] 45%|████▌     | 1802/4000 [7:09:59<8:34:26, 14.04s/it] 45%|████▌     | 1803/4000 [7:10:11<8:14:54, 13.52s/it] 45%|████▌     | 1804/4000 [7:10:26<8:32:04, 13.99s/it] 45%|████▌     | 1805/4000 [7:10:41<8:36:03, 14.11s/it] 45%|████▌     | 1806/4000 [7:10:54<8:26:45, 13.86s/it] 45%|████▌     | 1807/4000 [7:11:07<8:13:13, 13.49s/it] 45%|████▌     | 1808/4000 [7:11:21<8:21:40, 13.73s/it] 45%|████▌     | 1809/4000 [7:11:34<8:10:15, 13.43s/it] 45%|████▌     | 1810/4000 [7:11:48<8:23:15, 13.79s/it]                                                        45%|████▌     | 1810/4000 [7:11:48<8:23:15, 13.79s/it] 45%|████▌     | 1811/4000 [7:12:01<8:12:33, 13.50s/it] 45%|████▌     | 1812/4000 [7:12:16<8:29:02, 13.96s/it] 45%|████▌     | 1813/4000 [7:12:28<8:08:44, 13.41s/it] 45%|████▌     | 1814/4000 [7:12:43<8:28:31, 13.96s/it] 45%|████▌     | 1815/4000 [7:12:56<8:11:45, 13.50s/it] 45%|████▌     | 1816/4000 [7:13:11<8:30:14, 14.02s/it] 45%|████▌     | 1817/4000 [7:13:23<8:12:06, 13.53s/it] 45%|████▌     | 1818/4000 [7:13:39<8:29:28, 14.01s/it] 45%|████▌     | 1819/4000 [7:13:52<8:21:47, 13.80s/it] 46%|████▌     | 1820/4000 [7:14:06<8:28:43, 14.00s/it]                                                        46%|████▌     | 1820/4000 [7:14:06<8:28:43, 14.00s/it] 46%|████▌     | 1821/4000 [7:14:19<8:16:47, 13.68s/it] 46%|████▌     | 1822/4000 [7:14:33<8:22:19, 13.84s/it] 46%|████▌     | 1823/4000 [7:14:49<8:36:27, 14.23s/it] 46%|████▌     | 1824/4000 [7:15:01<8:15:52, 13.67s/it] 46%|████▌     | 1825/4000 [7:15:14<8:05:26, 13.39s/it] 46%|████▌     | 1826/4000 [7:15:29<8:22:52, 13.88s/it] 46%|████▌     | 1827/4000 [7:15:44<8:36:49, 14.27s/it] 46%|████▌     | 1828/4000 [7:15:57<8:20:06, 13.81s/it] 46%|████▌     | 1829/4000 [7:16:11<8:24:03, 13.93s/it] 46%|████▌     | 1830/4000 [7:16:24<8:11:24, 13.59s/it]                                                        46%|████▌     | 1830/4000 [7:16:24<8:11:24, 13.59s/it] 46%|████▌     | 1831/4000 [7:16:38<8:18:49, 13.80s/it] 46%|████▌     | 1832/4000 [7:16:51<8:11:09, 13.59s/it] 46%|████▌     | 1833/4000 [7:17:05<8:18:06, 13.79s/it] 46%|████▌     | 1834/4000 [7:17:18<8:10:26, 13.59s/it] 46%|████▌     | 1835/4000 [7:17:32<8:05:54, 13.47s/it] 46%|████▌     | 1836/4000 [7:17:46<8:16:37, 13.77s/it] 46%|████▌     | 1837/4000 [7:17:59<8:06:40, 13.50s/it] 46%|████▌     | 1838/4000 [7:18:13<8:12:11, 13.66s/it] 46%|████▌     | 1839/4000 [7:18:26<8:03:56, 13.44s/it] 46%|████▌     | 1840/4000 [7:18:40<8:11:27, 13.65s/it]                                                        46%|████▌     | 1840/4000 [7:18:40<8:11:27, 13.65s/it] 46%|████▌     | 1841/4000 [7:18:53<8:05:48, 13.50s/it] 46%|████▌     | 1842/4000 [7:19:08<8:22:43, 13.98s/it] 46%|████▌     | 1843/4000 [7:19:23<8:25:57, 14.07s/it] 46%|████▌     | 1844/4000 [7:19:36<8:15:22, 13.79s/it] 46%|████▌     | 1845/4000 [7:19:48<8:01:24, 13.40s/it] 46%|████▌     | 1846/4000 [7:20:03<8:16:25, 13.83s/it] 46%|████▌     | 1847/4000 [7:20:16<8:02:02, 13.43s/it] 46%|████▌     | 1848/4000 [7:20:30<8:16:54, 13.85s/it] 46%|████▌     | 1849/4000 [7:20:43<8:08:21, 13.62s/it] 46%|████▋     | 1850/4000 [7:20:58<8:18:26, 13.91s/it]                                                        46%|████▋     | 1850/4000 [7:20:58<8:18:26, 13.91s/it] 46%|████▋     | 1851/4000 [7:21:13<8:34:28, 14.36s/it] 46%|████▋     | 1852/4000 [7:21:26<8:12:56, 13.77s/it] 46%|████▋     | 1853/4000 [7:21:41<8:22:34, 14.05s/it] 46%|████▋     | 1854/4000 [7:21:53<8:06:06, 13.59s/it] 46%|████▋     | 1855/4000 [7:22:08<8:19:42, 13.98s/it] 46%|████▋     | 1856/4000 [7:22:20<8:03:28, 13.53s/it] 46%|████▋     | 1857/4000 [7:22:35<8:12:56, 13.80s/it] 46%|████▋     | 1858/4000 [7:22:48<8:01:09, 13.48s/it] 46%|████▋     | 1859/4000 [7:23:03<8:17:31, 13.94s/it] 46%|████▋     | 1860/4000 [7:23:16<8:07:16, 13.66s/it]                                                        46%|████▋     | 1860/4000 [7:23:16<8:07:16, 13.66s/it] 47%|████▋     | 1861/4000 [7:23:27<7:47:45, 13.12s/it] 47%|████▋     | 1862/4000 [7:23:42<8:06:40, 13.66s/it] 47%|████▋     | 1863/4000 [7:23:56<8:01:44, 13.53s/it] 47%|████▋     | 1864/4000 [7:24:11<8:20:12, 14.05s/it] 47%|████▋     | 1865/4000 [7:24:25<8:18:51, 14.02s/it] 47%|████▋     | 1866/4000 [7:24:37<7:56:36, 13.40s/it] 47%|████▋     | 1867/4000 [7:24:52<8:11:32, 13.83s/it] 47%|████▋     | 1868/4000 [7:25:05<8:03:23, 13.60s/it] 47%|████▋     | 1869/4000 [7:25:20<8:15:53, 13.96s/it] 47%|████▋     | 1870/4000 [7:25:32<8:00:41, 13.54s/it]                                                        47%|████▋     | 1870/4000 [7:25:32<8:00:41, 13.54s/it] 47%|████▋     | 1871/4000 [7:25:47<8:14:01, 13.92s/it] 47%|████▋     | 1872/4000 [7:26:00<8:00:55, 13.56s/it] 47%|████▋     | 1873/4000 [7:26:14<8:10:18, 13.83s/it] 47%|████▋     | 1874/4000 [7:26:27<8:02:39, 13.62s/it] 47%|████▋     | 1875/4000 [7:26:41<8:08:22, 13.79s/it] 47%|████▋     | 1876/4000 [7:26:55<8:03:49, 13.67s/it] 47%|████▋     | 1877/4000 [7:27:09<8:10:41, 13.87s/it] 47%|████▋     | 1878/4000 [7:27:22<7:56:59, 13.49s/it] 47%|████▋     | 1879/4000 [7:27:37<8:14:26, 13.99s/it] 47%|████▋     | 1880/4000 [7:27:49<7:59:19, 13.57s/it]                                                        47%|████▋     | 1880/4000 [7:27:49<7:59:19, 13.57s/it] 47%|████▋     | 1881/4000 [7:28:04<8:12:11, 13.94s/it] 47%|████▋     | 1882/4000 [7:28:16<7:53:23, 13.41s/it] 47%|████▋     | 1883/4000 [7:28:31<8:09:53, 13.88s/it] 47%|████▋     | 1884/4000 [7:28:35<6:24:49, 10.91s/it] 47%|████▋     | 1885/4000 [7:28:50<7:01:30, 11.96s/it] 47%|████▋     | 1886/4000 [7:29:03<7:17:53, 12.43s/it] 47%|████▋     | 1887/4000 [7:29:18<7:41:15, 13.10s/it] 47%|████▋     | 1888/4000 [7:29:33<7:59:11, 13.61s/it] 47%|████▋     | 1889/4000 [7:29:46<7:51:18, 13.40s/it] 47%|████▋     | 1890/4000 [7:30:00<8:03:39, 13.75s/it]                                                        47%|████▋     | 1890/4000 [7:30:00<8:03:39, 13.75s/it] 47%|████▋     | 1891/4000 [7:30:13<7:51:18, 13.41s/it] 47%|████▋     | 1892/4000 [7:30:27<8:03:38, 13.77s/it] 47%|████▋     | 1893/4000 [7:30:43<8:21:29, 14.28s/it] 47%|████▋     | 1894/4000 [7:30:56<8:04:33, 13.81s/it] 47%|████▋     | 1895/4000 [7:31:11<8:16:09, 14.14s/it] 47%|████▋     | 1896/4000 [7:31:24<8:05:13, 13.84s/it] 47%|████▋     | 1897/4000 [7:31:37<8:04:23, 13.82s/it] 47%|████▋     | 1898/4000 [7:31:50<7:53:56, 13.53s/it] 47%|████▋     | 1899/4000 [7:32:05<8:01:19, 13.75s/it] 48%|████▊     | 1900/4000 [7:32:18<7:57:19, 13.64s/it]                                                        48%|████▊     | 1900/4000 [7:32:18<7:57:19, 13.64s/it] 48%|████▊     | 1901/4000 [7:32:33<8:08:52, 13.97s/it] 48%|████▊     | 1902/4000 [7:32:46<7:56:25, 13.62s/it] 48%|████▊     | 1903/4000 [7:33:01<8:11:36, 14.07s/it] 48%|████▊     | 1904/4000 [7:33:15<8:16:36, 14.22s/it] 48%|████▊     | 1905/4000 [7:33:28<8:06:30, 13.93s/it] 48%|████▊     | 1906/4000 [7:33:43<8:10:29, 14.05s/it] 48%|████▊     | 1907/4000 [7:33:56<8:03:18, 13.86s/it] 48%|████▊     | 1908/4000 [7:34:10<8:05:31, 13.93s/it] 48%|████▊     | 1909/4000 [7:34:24<7:59:06, 13.75s/it] 48%|████▊     | 1910/4000 [7:34:38<8:04:39, 13.91s/it]                                                        48%|████▊     | 1910/4000 [7:34:38<8:04:39, 13.91s/it] 48%|████▊     | 1911/4000 [7:34:52<8:01:25, 13.83s/it] 48%|████▊     | 1912/4000 [7:35:06<8:08:18, 14.03s/it] 48%|████▊     | 1913/4000 [7:35:18<7:47:55, 13.45s/it] 48%|████▊     | 1914/4000 [7:35:33<8:02:28, 13.88s/it] 48%|████▊     | 1915/4000 [7:35:45<7:40:40, 13.26s/it] 48%|████▊     | 1916/4000 [7:36:00<7:58:55, 13.79s/it] 48%|████▊     | 1917/4000 [7:36:12<7:38:45, 13.21s/it] 48%|████▊     | 1918/4000 [7:36:27<7:59:06, 13.81s/it] 48%|████▊     | 1919/4000 [7:36:40<7:47:52, 13.49s/it] 48%|████▊     | 1920/4000 [7:36:54<8:01:12, 13.88s/it]                                                        48%|████▊     | 1920/4000 [7:36:54<8:01:12, 13.88s/it] 48%|████▊     | 1921/4000 [7:37:07<7:51:23, 13.60s/it] 48%|████▊     | 1922/4000 [7:37:22<7:58:20, 13.81s/it] 48%|████▊     | 1923/4000 [7:37:35<7:53:22, 13.67s/it] 48%|████▊     | 1924/4000 [7:37:49<7:58:38, 13.83s/it] 48%|████▊     | 1925/4000 [7:38:02<7:51:10, 13.62s/it] 48%|████▊     | 1926/4000 [7:38:17<8:00:50, 13.91s/it] 48%|████▊     | 1927/4000 [7:38:30<7:46:56, 13.51s/it] 48%|████▊     | 1928/4000 [7:38:45<8:04:38, 14.03s/it] 48%|████▊     | 1929/4000 [7:38:57<7:47:19, 13.54s/it] 48%|████▊     | 1930/4000 [7:39:12<7:58:39, 13.87s/it]                                                        48%|████▊     | 1930/4000 [7:39:12<7:58:39, 13.87s/it] 48%|████▊     | 1931/4000 [7:39:25<7:49:46, 13.62s/it] 48%|████▊     | 1932/4000 [7:39:40<8:03:55, 14.04s/it] 48%|████▊     | 1933/4000 [7:39:55<8:16:38, 14.42s/it] 48%|████▊     | 1934/4000 [7:40:07<7:45:37, 13.52s/it] 48%|████▊     | 1935/4000 [7:40:19<7:37:21, 13.29s/it] 48%|████▊     | 1936/4000 [7:40:34<7:52:42, 13.74s/it] 48%|████▊     | 1937/4000 [7:40:47<7:46:00, 13.55s/it] 48%|████▊     | 1938/4000 [7:41:02<7:56:57, 13.88s/it] 48%|████▊     | 1939/4000 [7:41:15<7:49:26, 13.67s/it] 48%|████▊     | 1940/4000 [7:41:30<8:04:33, 14.11s/it]                                                        48%|████▊     | 1940/4000 [7:41:30<8:04:33, 14.11s/it] 49%|████▊     | 1941/4000 [7:41:42<7:42:30, 13.48s/it] 49%|████▊     | 1942/4000 [7:41:58<8:01:53, 14.05s/it] 49%|████▊     | 1943/4000 [7:42:12<8:01:51, 14.06s/it] 49%|████▊     | 1944/4000 [7:42:25<7:51:38, 13.76s/it] 49%|████▊     | 1945/4000 [7:42:37<7:39:11, 13.41s/it] 49%|████▊     | 1946/4000 [7:42:52<7:51:10, 13.76s/it] 49%|████▊     | 1947/4000 [7:43:05<7:43:19, 13.54s/it] 49%|████▊     | 1948/4000 [7:43:19<7:52:30, 13.82s/it] 49%|████▊     | 1949/4000 [7:43:32<7:40:35, 13.47s/it] 49%|████▉     | 1950/4000 [7:43:46<7:43:49, 13.58s/it]                                                        49%|████▉     | 1950/4000 [7:43:46<7:43:49, 13.58s/it] 49%|████▉     | 1951/4000 [7:44:00<7:43:44, 13.58s/it] 49%|████▉     | 1952/4000 [7:44:14<7:51:15, 13.81s/it] 49%|████▉     | 1953/4000 [7:44:29<8:04:20, 14.20s/it] 49%|████▉     | 1954/4000 [7:44:41<7:44:22, 13.62s/it] 49%|████▉     | 1955/4000 [7:44:56<7:55:43, 13.96s/it] 49%|████▉     | 1956/4000 [7:45:09<7:44:10, 13.63s/it] 49%|████▉     | 1957/4000 [7:45:22<7:34:32, 13.35s/it] 49%|████▉     | 1958/4000 [7:45:37<7:51:19, 13.85s/it] 49%|████▉     | 1959/4000 [7:45:51<7:56:42, 14.01s/it] 49%|████▉     | 1960/4000 [7:46:04<7:46:58, 13.73s/it]                                                        49%|████▉     | 1960/4000 [7:46:04<7:46:58, 13.73s/it] 49%|████▉     | 1961/4000 [7:46:16<7:31:59, 13.30s/it] 49%|████▉     | 1962/4000 [7:46:32<7:52:56, 13.92s/it] 49%|████▉     | 1963/4000 [7:46:45<7:41:21, 13.59s/it] 49%|████▉     | 1964/4000 [7:46:59<7:54:46, 13.99s/it] 49%|████▉     | 1965/4000 [7:47:14<8:04:15, 14.28s/it] 49%|████▉     | 1966/4000 [7:47:26<7:33:46, 13.39s/it] 49%|████▉     | 1967/4000 [7:47:38<7:24:42, 13.12s/it] 49%|████▉     | 1968/4000 [7:47:53<7:45:56, 13.76s/it] 49%|████▉     | 1969/4000 [7:48:07<7:48:14, 13.83s/it] 49%|████▉     | 1970/4000 [7:48:22<7:56:16, 14.08s/it]                                                        49%|████▉     | 1970/4000 [7:48:22<7:56:16, 14.08s/it] 49%|████▉     | 1971/4000 [7:48:34<7:37:58, 13.54s/it] 49%|████▉     | 1972/4000 [7:48:49<7:51:22, 13.95s/it] 49%|████▉     | 1973/4000 [7:49:02<7:35:46, 13.49s/it] 49%|████▉     | 1974/4000 [7:49:16<7:46:40, 13.82s/it] 49%|████▉     | 1975/4000 [7:49:29<7:37:09, 13.55s/it] 49%|████▉     | 1976/4000 [7:49:44<7:48:51, 13.90s/it] 49%|████▉     | 1977/4000 [7:49:59<8:01:34, 14.28s/it] 49%|████▉     | 1978/4000 [7:50:12<7:43:48, 13.76s/it] 49%|████▉     | 1979/4000 [7:50:27<7:55:00, 14.10s/it] 50%|████▉     | 1980/4000 [7:50:39<7:35:58, 13.54s/it]                                                        50%|████▉     | 1980/4000 [7:50:39<7:35:58, 13.54s/it] 50%|████▉     | 1981/4000 [7:50:51<7:27:10, 13.29s/it] 50%|████▉     | 1982/4000 [7:51:06<7:42:22, 13.75s/it] 50%|████▉     | 1983/4000 [7:51:21<7:49:38, 13.97s/it] 50%|████▉     | 1984/4000 [7:51:34<7:37:49, 13.63s/it] 50%|████▉     | 1985/4000 [7:51:46<7:24:06, 13.22s/it] 50%|████▉     | 1986/4000 [7:52:01<7:46:00, 13.88s/it] 50%|████▉     | 1987/4000 [7:52:16<7:52:58, 14.10s/it] 50%|████▉     | 1988/4000 [7:52:29<7:44:59, 13.87s/it] 50%|████▉     | 1989/4000 [7:52:43<7:46:39, 13.92s/it] 50%|████▉     | 1990/4000 [7:52:57<7:39:18, 13.71s/it]                                                        50%|████▉     | 1990/4000 [7:52:57<7:39:18, 13.71s/it] 50%|████▉     | 1991/4000 [7:53:12<7:52:22, 14.11s/it] 50%|████▉     | 1992/4000 [7:53:24<7:31:34, 13.49s/it] 50%|████▉     | 1993/4000 [7:53:39<7:47:13, 13.97s/it] 50%|████▉     | 1994/4000 [7:53:51<7:31:28, 13.50s/it] 50%|████▉     | 1995/4000 [7:54:07<7:50:32, 14.08s/it] 50%|████▉     | 1996/4000 [7:54:19<7:32:00, 13.53s/it] 50%|████▉     | 1997/4000 [7:54:33<7:42:56, 13.87s/it] 50%|████▉     | 1998/4000 [7:54:47<7:35:33, 13.65s/it] 50%|████▉     | 1999/4000 [7:55:02<7:48:02, 14.03s/it] 50%|█████     | 2000/4000 [7:55:17<7:58:55, 14.37s/it]                                                        50%|█████     | 2000/4000 [7:55:17<7:58:55, 14.37s/it]{'eval_loss': '0.1662', 'eval_runtime': '392.4', 'eval_samples_per_second': '1.282', 'eval_steps_per_second': '1.282', 'epoch': '2.389'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1737:{'loss': '1.043', 'grad_norm': '0.3249', 'learning_rate': '0.0001288', 'epoch': '2.708'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1814:  9%|▉         | 46/503 [00:34<04:29,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1817: 10%|▉         | 49/503 [00:37<04:27,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1838: 14%|█▍        | 70/503 [00:53<04:11,  1.72it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1839: 14%|█▍        | 71/503 [00:55<07:44,  1.08s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1840: 14%|█▍        | 72/503 [00:55<06:01,  1.19it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:1936: 34%|███▍      | 170/503 [02:09<02:37,  2.11it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2034: 54%|█████▎    | 270/503 [03:26<01:48,  2.14it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2114: 70%|██████▉   | 350/503 [04:28<02:08,  1.19it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2115: 70%|██████▉   | 351/503 [04:28<01:43,  1.46it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2116: 70%|██████▉   | 352/503 [04:29<01:25,  1.76it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2117: 70%|███████   | 353/503 [04:31<02:39,  1.06s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2118: 70%|███████   | 354/503 [04:31<02:03,  1.20it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2134: 74%|███████▎  | 370/503 [04:43<02:18,  1.04s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2165: 80%|███████▉  | 401/503 [05:05<00:55,  1.85it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2190: 85%|████████▌ | 428/503 [05:25<00:55,  1.35it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2232: 93%|█████████▎| 470/503 [05:56<00:16,  1.97it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2272: 50%|█████     | 2001/4000 [8:01:56<72:02:44, 129.75s/it] 50%|█████     | 2002/4000 [8:02:11<52:57:20, 95.42s/it]  50%|█████     | 2003/4000 [8:02:24<39:10:14, 70.61s/it] 50%|█████     | 2004/4000 [8:02:39<29:53:23, 53.91s/it] 50%|█████     | 2005/4000 [8:02:51<23:00:09, 41.51s/it] 50%|█████     | 2006/4000 [8:03:07<18:41:56, 33.76s/it] 50%|█████     | 2007/4000 [8:03:21<15:30:04, 28.00s/it] 50%|█████     | 2008/4000 [8:03:34<13:00:39, 23.51s/it] 50%|█████     | 2009/4000 [8:03:50<11:37:45, 21.03s/it] 50%|█████     | 2010/4000 [8:04:04<10:34:41, 19.14s/it]                                                         50%|█████     | 2010/4000 [8:04:04<10:34:41, 19.14s/it] 50%|█████     | 2011/4000 [8:04:18<9:34:35, 17.33s/it]  50%|█████     | 2012/4000 [8:04:30<8:46:33, 15.89s/it] 50%|█████     | 2013/4000 [8:04:45<8:38:34, 15.66s/it] 50%|█████     | 2014/4000 [8:05:00<8:31:09, 15.44s/it] 50%|█████     | 2015/4000 [8:05:13<8:09:36, 14.80s/it] 50%|█████     | 2016/4000 [8:05:28<8:08:34, 14.78s/it] 50%|█████     | 2017/4000 [8:05:44<8:15:56, 15.01s/it] 50%|█████     | 2018/4000 [8:05:57<7:59:05, 14.50s/it] 50%|█████     | 2019/4000 [8:06:11<7:56:55, 14.44s/it] 50%|█████     | 2020/4000 [8:06:24<7:43:22, 14.04s/it]                                                        50%|█████     | 2020/4000 [8:06:24<7:43:22, 14.04s/it] 51%|█████     | 2021/4000 [8:06:38<7:42:39, 14.03s/it] 51%|█████     | 2022/4000 [8:06:52<7:34:01, 13.77s/it] 51%|█████     | 2023/4000 [8:07:07<7:49:16, 14.24s/it] 51%|█████     | 2024/4000 [8:07:20<7:34:37, 13.80s/it] 51%|█████     | 2025/4000 [8:07:34<7:36:40, 13.87s/it] 51%|█████     | 2026/4000 [8:07:46<7:23:22, 13.48s/it] 51%|█████     | 2027/4000 [8:08:01<7:37:10, 13.90s/it] 51%|█████     | 2028/4000 [8:08:14<7:25:07, 13.54s/it] 51%|█████     | 2029/4000 [8:08:29<7:39:33, 13.99s/it] 51%|█████     | 2030/4000 [8:08:41<7:19:12, 13.38s/it]                                                        51%|█████     | 2030/4000 [8:08:41<7:19:12, 13.38s/it] 51%|█████     | 2031/4000 [8:08:56<7:34:26, 13.85s/it] 51%|█████     | 2032/4000 [8:09:09<7:26:51, 13.62s/it] 51%|█████     | 2033/4000 [8:09:23<7:35:54, 13.91s/it] 51%|█████     | 2034/4000 [8:09:39<7:48:07, 14.29s/it] 51%|█████     | 2035/4000 [8:09:51<7:31:46, 13.79s/it] 51%|█████     | 2036/4000 [8:10:06<7:44:28, 14.19s/it] 51%|█████     | 2037/4000 [8:10:19<7:23:40, 13.56s/it] 51%|█████     | 2038/4000 [8:10:33<7:33:15, 13.86s/it] 51%|█████     | 2039/4000 [8:10:46<7:20:16, 13.47s/it] 51%|█████     | 2040/4000 [8:11:01<7:34:38, 13.92s/it]                                                        51%|█████     | 2040/4000 [8:11:01<7:34:38, 13.92s/it] 51%|█████     | 2041/4000 [8:11:13<7:23:52, 13.59s/it] 51%|█████     | 2042/4000 [8:11:28<7:34:22, 13.92s/it] 51%|█████     | 2043/4000 [8:11:41<7:25:00, 13.64s/it] 51%|█████     | 2044/4000 [8:11:55<7:28:33, 13.76s/it] 51%|█████     | 2045/4000 [8:12:08<7:22:22, 13.58s/it] 51%|█████     | 2046/4000 [8:12:23<7:28:55, 13.78s/it] 51%|█████     | 2047/4000 [8:12:36<7:21:01, 13.55s/it] 51%|█████     | 2048/4000 [8:12:51<7:37:13, 14.05s/it] 51%|█████     | 2049/4000 [8:13:03<7:21:02, 13.56s/it] 51%|█████▏    | 2050/4000 [8:13:19<7:37:35, 14.08s/it]                                                        51%|█████▏    | 2050/4000 [8:13:19<7:37:35, 14.08s/it] 51%|█████▏    | 2051/4000 [8:13:31<7:17:49, 13.48s/it] 51%|█████▏    | 2052/4000 [8:13:45<7:29:26, 13.84s/it] 51%|█████▏    | 2053/4000 [8:13:58<7:16:02, 13.44s/it] 51%|█████▏    | 2054/4000 [8:14:13<7:32:05, 13.94s/it] 51%|█████▏    | 2055/4000 [8:14:26<7:21:13, 13.61s/it] 51%|█████▏    | 2056/4000 [8:14:40<7:27:00, 13.80s/it] 51%|█████▏    | 2057/4000 [8:14:53<7:17:34, 13.51s/it] 51%|█████▏    | 2058/4000 [8:15:08<7:30:08, 13.91s/it] 51%|█████▏    | 2059/4000 [8:15:20<7:18:04, 13.54s/it] 52%|█████▏    | 2060/4000 [8:15:34<7:23:29, 13.72s/it]                                                        52%|█████▏    | 2060/4000 [8:15:34<7:23:29, 13.72s/it] 52%|█████▏    | 2061/4000 [8:15:47<7:15:25, 13.47s/it] 52%|█████▏    | 2062/4000 [8:16:02<7:28:14, 13.88s/it] 52%|█████▏    | 2063/4000 [8:16:14<7:12:02, 13.38s/it] 52%|█████▏    | 2064/4000 [8:16:30<7:28:34, 13.90s/it] 52%|█████▏    | 2065/4000 [8:16:41<7:08:44, 13.29s/it] 52%|█████▏    | 2066/4000 [8:16:57<7:26:38, 13.86s/it] 52%|█████▏    | 2067/4000 [8:17:09<7:16:02, 13.53s/it] 52%|█████▏    | 2068/4000 [8:17:24<7:28:23, 13.93s/it] 52%|█████▏    | 2069/4000 [8:17:37<7:14:57, 13.51s/it] 52%|█████▏    | 2070/4000 [8:17:49<7:03:03, 13.15s/it]                                                        52%|█████▏    | 2070/4000 [8:17:49<7:03:03, 13.15s/it] 52%|█████▏    | 2071/4000 [8:18:04<7:22:18, 13.76s/it] 52%|█████▏    | 2072/4000 [8:18:19<7:30:58, 14.03s/it] 52%|█████▏    | 2073/4000 [8:18:32<7:20:10, 13.71s/it] 52%|█████▏    | 2074/4000 [8:18:46<7:23:22, 13.81s/it] 52%|█████▏    | 2075/4000 [8:18:59<7:17:10, 13.63s/it] 52%|█████▏    | 2076/4000 [8:19:14<7:31:26, 14.08s/it] 52%|█████▏    | 2077/4000 [8:19:26<7:13:03, 13.51s/it] 52%|█████▏    | 2078/4000 [8:19:41<7:26:58, 13.95s/it] 52%|█████▏    | 2079/4000 [8:19:54<7:11:11, 13.47s/it] 52%|█████▏    | 2080/4000 [8:20:09<7:31:24, 14.11s/it]                                                        52%|█████▏    | 2080/4000 [8:20:09<7:31:24, 14.11s/it] 52%|█████▏    | 2081/4000 [8:20:22<7:13:36, 13.56s/it] 52%|█████▏    | 2082/4000 [8:20:36<7:24:47, 13.91s/it] 52%|█████▏    | 2083/4000 [8:20:51<7:29:59, 14.08s/it] 52%|█████▏    | 2084/4000 [8:21:04<7:20:12, 13.79s/it] 52%|█████▏    | 2085/4000 [8:21:19<7:30:46, 14.12s/it] 52%|█████▏    | 2086/4000 [8:21:31<7:14:04, 13.61s/it] 52%|█████▏    | 2087/4000 [8:21:46<7:27:49, 14.05s/it] 52%|█████▏    | 2088/4000 [8:21:59<7:12:01, 13.56s/it] 52%|█████▏    | 2089/4000 [8:22:14<7:27:44, 14.06s/it] 52%|█████▏    | 2090/4000 [8:22:26<7:07:26, 13.43s/it]                                                        52%|█████▏    | 2090/4000 [8:22:26<7:07:26, 13.43s/it] 52%|█████▏    | 2091/4000 [8:22:41<7:25:36, 14.01s/it] 52%|█████▏    | 2092/4000 [8:22:54<7:17:03, 13.74s/it] 52%|█████▏    | 2093/4000 [8:23:08<7:20:16, 13.85s/it] 52%|█████▏    | 2094/4000 [8:23:21<7:11:06, 13.57s/it] 52%|█████▏    | 2095/4000 [8:23:35<7:15:04, 13.70s/it] 52%|█████▏    | 2096/4000 [8:23:49<7:11:46, 13.61s/it] 52%|█████▏    | 2097/4000 [8:24:03<7:20:13, 13.88s/it] 52%|█████▏    | 2098/4000 [8:24:16<7:08:48, 13.53s/it] 52%|█████▏    | 2099/4000 [8:24:31<7:24:22, 14.03s/it] 52%|█████▎    | 2100/4000 [8:24:44<7:12:35, 13.66s/it]                                                        52%|█████▎    | 2100/4000 [8:24:44<7:12:35, 13.66s/it] 53%|█████▎    | 2101/4000 [8:24:58<7:19:13, 13.88s/it] 53%|█████▎    | 2102/4000 [8:25:11<7:05:54, 13.46s/it] 53%|█████▎    | 2103/4000 [8:25:26<7:16:40, 13.81s/it] 53%|█████▎    | 2104/4000 [8:25:38<7:03:46, 13.41s/it] 53%|█████▎    | 2105/4000 [8:25:53<7:18:50, 13.89s/it] 53%|█████▎    | 2106/4000 [8:26:08<7:28:30, 14.21s/it] 53%|█████▎    | 2107/4000 [8:26:20<7:10:34, 13.65s/it] 53%|█████▎    | 2108/4000 [8:26:35<7:20:58, 13.98s/it] 53%|█████▎    | 2109/4000 [8:26:47<7:04:15, 13.46s/it] 53%|█████▎    | 2110/4000 [8:27:00<6:58:48, 13.30s/it]                                                        53%|█████▎    | 2110/4000 [8:27:00<6:58:48, 13.30s/it] 53%|█████▎    | 2111/4000 [8:27:15<7:13:49, 13.78s/it] 53%|█████▎    | 2112/4000 [8:27:29<7:11:36, 13.72s/it] 53%|█████▎    | 2113/4000 [8:27:42<7:07:26, 13.59s/it] 53%|█████▎    | 2114/4000 [8:27:57<7:20:26, 14.01s/it] 53%|█████▎    | 2115/4000 [8:28:09<7:05:55, 13.56s/it] 53%|█████▎    | 2116/4000 [8:28:24<7:19:15, 13.99s/it] 53%|█████▎    | 2117/4000 [8:28:37<7:06:34, 13.59s/it] 53%|█████▎    | 2118/4000 [8:28:50<7:00:46, 13.41s/it] 53%|█████▎    | 2119/4000 [8:29:05<7:10:15, 13.72s/it] 53%|█████▎    | 2120/4000 [8:29:18<7:03:52, 13.53s/it]                                                        53%|█████▎    | 2120/4000 [8:29:18<7:03:52, 13.53s/it] 53%|█████▎    | 2121/4000 [8:29:32<7:12:47, 13.82s/it] 53%|█████▎    | 2122/4000 [8:29:45<7:00:05, 13.42s/it] 53%|█████▎    | 2123/4000 [8:29:59<7:12:19, 13.82s/it] 53%|█████▎    | 2124/4000 [8:30:12<6:59:23, 13.41s/it] 53%|█████▎    | 2125/4000 [8:30:26<7:09:13, 13.74s/it] 53%|█████▎    | 2126/4000 [8:30:39<6:57:26, 13.37s/it] 53%|█████▎    | 2127/4000 [8:30:54<7:14:35, 13.92s/it] 53%|█████▎    | 2128/4000 [8:31:07<7:04:05, 13.59s/it] 53%|█████▎    | 2129/4000 [8:31:21<7:08:45, 13.75s/it] 53%|█████▎    | 2130/4000 [8:31:34<7:04:21, 13.62s/it]                                                        53%|█████▎    | 2130/4000 [8:31:34<7:04:21, 13.62s/it] 53%|█████▎    | 2131/4000 [8:31:49<7:10:26, 13.82s/it] 53%|█████▎    | 2132/4000 [8:32:02<7:01:28, 13.54s/it] 53%|█████▎    | 2133/4000 [8:32:16<7:07:38, 13.74s/it] 53%|█████▎    | 2134/4000 [8:32:29<7:02:10, 13.57s/it] 53%|█████▎    | 2135/4000 [8:32:44<7:12:40, 13.92s/it] 53%|█████▎    | 2136/4000 [8:32:56<6:56:56, 13.42s/it] 53%|█████▎    | 2137/4000 [8:33:11<7:15:09, 14.01s/it] 53%|█████▎    | 2138/4000 [8:33:24<6:59:52, 13.53s/it] 53%|█████▎    | 2139/4000 [8:33:39<7:13:13, 13.97s/it] 54%|█████▎    | 2140/4000 [8:33:50<6:52:28, 13.31s/it]                                                        54%|█████▎    | 2140/4000 [8:33:50<6:52:28, 13.31s/it] 54%|█████▎    | 2141/4000 [8:34:03<6:49:17, 13.21s/it] 54%|█████▎    | 2142/4000 [8:34:18<7:04:16, 13.70s/it] 54%|█████▎    | 2143/4000 [8:34:31<6:50:53, 13.28s/it] 54%|█████▎    | 2144/4000 [8:34:46<7:07:08, 13.81s/it] 54%|█████▎    | 2145/4000 [8:34:58<6:51:45, 13.32s/it] 54%|█████▎    | 2146/4000 [8:35:16<7:35:33, 14.74s/it] 54%|█████▎    | 2147/4000 [8:35:31<7:35:46, 14.76s/it] 54%|█████▎    | 2148/4000 [8:35:46<7:41:41, 14.96s/it] 54%|█████▎    | 2149/4000 [8:35:59<7:18:19, 14.21s/it] 54%|█████▍    | 2150/4000 [8:36:14<7:32:11, 14.67s/it]                                                        54%|█████▍    | 2150/4000 [8:36:14<7:32:11, 14.67s/it] 54%|█████▍    | 2151/4000 [8:36:27<7:11:14, 13.99s/it] 54%|█████▍    | 2152/4000 [8:36:41<7:16:57, 14.19s/it] 54%|█████▍    | 2153/4000 [8:36:54<7:06:08, 13.84s/it] 54%|█████▍    | 2154/4000 [8:37:09<7:09:02, 13.94s/it] 54%|█████▍    | 2155/4000 [8:37:22<7:03:26, 13.77s/it] 54%|█████▍    | 2156/4000 [8:37:36<7:02:28, 13.75s/it] 54%|█████▍    | 2157/4000 [8:37:49<6:58:45, 13.63s/it] 54%|█████▍    | 2158/4000 [8:38:03<7:04:00, 13.81s/it] 54%|█████▍    | 2159/4000 [8:38:17<7:00:36, 13.71s/it] 54%|█████▍    | 2160/4000 [8:38:32<7:15:13, 14.19s/it]                                                        54%|█████▍    | 2160/4000 [8:38:32<7:15:13, 14.19s/it] 54%|█████▍    | 2161/4000 [8:38:46<7:15:30, 14.21s/it] 54%|█████▍    | 2162/4000 [8:38:59<7:04:27, 13.86s/it] 54%|█████▍    | 2163/4000 [8:39:14<7:11:56, 14.11s/it] 54%|█████▍    | 2164/4000 [8:39:27<7:02:47, 13.82s/it] 54%|█████▍    | 2165/4000 [8:39:41<7:00:18, 13.74s/it] 54%|█████▍    | 2166/4000 [8:39:54<6:54:40, 13.57s/it] 54%|█████▍    | 2167/4000 [8:40:08<7:01:11, 13.79s/it] 54%|█████▍    | 2168/4000 [8:40:22<6:58:01, 13.69s/it] 54%|█████▍    | 2169/4000 [8:40:36<7:03:45, 13.89s/it] 54%|█████▍    | 2170/4000 [8:40:48<6:46:15, 13.32s/it]                                                        54%|█████▍    | 2170/4000 [8:40:48<6:46:15, 13.32s/it] 54%|█████▍    | 2171/4000 [8:41:03<7:02:23, 13.86s/it] 54%|█████▍    | 2172/4000 [8:41:15<6:45:54, 13.32s/it] 54%|█████▍    | 2173/4000 [8:41:30<6:58:12, 13.73s/it] 54%|█████▍    | 2174/4000 [8:41:44<7:02:20, 13.88s/it] 54%|█████▍    | 2175/4000 [8:41:56<6:48:26, 13.43s/it] 54%|█████▍    | 2176/4000 [8:42:09<6:39:47, 13.15s/it] 54%|█████▍    | 2177/4000 [8:42:23<6:50:33, 13.51s/it] 54%|█████▍    | 2178/4000 [8:42:36<6:43:07, 13.28s/it] 54%|█████▍    | 2179/4000 [8:42:50<6:49:03, 13.48s/it] 55%|█████▍    | 2180/4000 [8:43:05<7:04:37, 14.00s/it]                                                        55%|█████▍    | 2180/4000 [8:43:05<7:04:37, 14.00s/it] 55%|█████▍    | 2181/4000 [8:43:17<6:46:45, 13.42s/it] 55%|█████▍    | 2182/4000 [8:43:32<7:00:34, 13.88s/it] 55%|█████▍    | 2183/4000 [8:43:45<6:52:57, 13.64s/it] 55%|█████▍    | 2184/4000 [8:43:59<6:56:42, 13.77s/it] 55%|█████▍    | 2185/4000 [8:44:12<6:50:19, 13.56s/it] 55%|█████▍    | 2186/4000 [8:44:27<6:57:08, 13.80s/it] 55%|█████▍    | 2187/4000 [8:44:40<6:48:34, 13.52s/it] 55%|█████▍    | 2188/4000 [8:44:54<6:55:29, 13.76s/it] 55%|█████▍    | 2189/4000 [8:45:07<6:47:14, 13.49s/it] 55%|█████▍    | 2190/4000 [8:45:22<7:04:44, 14.08s/it]                                                        55%|█████▍    | 2190/4000 [8:45:22<7:04:44, 14.08s/it] 55%|█████▍    | 2191/4000 [8:45:35<6:48:24, 13.55s/it] 55%|█████▍    | 2192/4000 [8:45:49<7:00:24, 13.95s/it] 55%|█████▍    | 2193/4000 [8:46:02<6:45:23, 13.46s/it] 55%|█████▍    | 2194/4000 [8:46:17<7:01:45, 14.01s/it] 55%|█████▍    | 2195/4000 [8:46:29<6:45:53, 13.49s/it] 55%|█████▍    | 2196/4000 [8:46:44<7:00:21, 13.98s/it] 55%|█████▍    | 2197/4000 [8:46:59<7:04:38, 14.13s/it] 55%|█████▍    | 2198/4000 [8:47:12<6:56:25, 13.87s/it] 55%|█████▍    | 2199/4000 [8:47:28<7:10:50, 14.35s/it] 55%|█████▌    | 2200/4000 [8:47:41<7:04:36, 14.15s/it]                                                        55%|█████▌    | 2200/4000 [8:47:41<7:04:36, 14.15s/it] 55%|█████▌    | 2201/4000 [8:47:55<6:55:12, 13.85s/it] 55%|█████▌    | 2202/4000 [8:48:07<6:40:26, 13.36s/it] 55%|█████▌    | 2203/4000 [8:48:22<6:55:58, 13.89s/it] 55%|█████▌    | 2204/4000 [8:48:36<6:58:27, 13.98s/it] 55%|█████▌    | 2205/4000 [8:48:49<6:52:27, 13.79s/it] 55%|█████▌    | 2206/4000 [8:49:05<7:07:21, 14.29s/it] 55%|█████▌    | 2207/4000 [8:49:19<7:08:04, 14.33s/it] 55%|█████▌    | 2208/4000 [8:49:33<6:59:50, 14.06s/it] 55%|█████▌    | 2209/4000 [8:49:47<6:59:38, 14.06s/it] 55%|█████▌    | 2210/4000 [8:50:00<6:52:21, 13.82s/it]                                                        55%|█████▌    | 2210/4000 [8:50:00<6:52:21, 13.82s/it] 55%|█████▌    | 2211/4000 [8:50:14<6:54:08, 13.89s/it] 55%|█████▌    | 2212/4000 [8:50:27<6:47:58, 13.69s/it] 55%|█████▌    | 2213/4000 [8:50:41<6:50:14, 13.77s/it] 55%|█████▌    | 2214/4000 [8:50:54<6:42:05, 13.51s/it] 55%|█████▌    | 2215/4000 [8:51:09<6:55:33, 13.97s/it] 55%|█████▌    | 2216/4000 [8:51:21<6:39:42, 13.44s/it] 55%|█████▌    | 2217/4000 [8:51:36<6:53:24, 13.91s/it] 55%|█████▌    | 2218/4000 [8:51:49<6:37:33, 13.39s/it] 55%|█████▌    | 2219/4000 [8:52:04<6:51:26, 13.86s/it] 56%|█████▌    | 2220/4000 [8:52:16<6:37:51, 13.41s/it]                                                        56%|█████▌    | 2220/4000 [8:52:16<6:37:51, 13.41s/it] 56%|█████▌    | 2221/4000 [8:52:31<6:54:08, 13.97s/it] 56%|█████▌    | 2222/4000 [8:52:45<6:48:16, 13.78s/it] 56%|█████▌    | 2223/4000 [8:52:59<6:55:09, 14.02s/it] 56%|█████▌    | 2224/4000 [8:53:12<6:44:15, 13.66s/it] 56%|█████▌    | 2225/4000 [8:53:27<6:52:31, 13.94s/it] 56%|█████▌    | 2226/4000 [8:53:40<6:45:26, 13.71s/it] 56%|█████▌    | 2227/4000 [8:53:54<6:50:24, 13.89s/it] 56%|█████▌    | 2228/4000 [8:54:07<6:42:12, 13.62s/it] 56%|█████▌    | 2229/4000 [8:54:22<6:56:19, 14.10s/it] 56%|█████▌    | 2230/4000 [8:54:34<6:38:23, 13.50s/it]                                                        56%|█████▌    | 2230/4000 [8:54:34<6:38:23, 13.50s/it] 56%|█████▌    | 2231/4000 [8:54:49<6:51:40, 13.96s/it] 56%|█████▌    | 2232/4000 [8:55:02<6:40:06, 13.58s/it] 56%|█████▌    | 2233/4000 [8:55:17<6:51:25, 13.97s/it] 56%|█████▌    | 2234/4000 [8:55:31<6:54:52, 14.10s/it] 56%|█████▌    | 2235/4000 [8:55:45<6:47:44, 13.86s/it] 56%|█████▌    | 2236/4000 [8:55:59<6:49:12, 13.92s/it] 56%|█████▌    | 2237/4000 [8:56:14<7:02:43, 14.39s/it] 56%|█████▌    | 2238/4000 [8:56:27<6:51:04, 14.00s/it] 56%|█████▌    | 2239/4000 [8:56:39<6:34:05, 13.43s/it] 56%|█████▌    | 2240/4000 [8:56:54<6:48:08, 13.91s/it]                                                        56%|█████▌    | 2240/4000 [8:56:54<6:48:08, 13.91s/it] 56%|█████▌    | 2241/4000 [8:57:07<6:33:57, 13.44s/it] 56%|█████▌    | 2242/4000 [8:57:22<6:49:58, 13.99s/it] 56%|█████▌    | 2243/4000 [8:57:34<6:35:20, 13.50s/it] 56%|█████▌    | 2244/4000 [8:57:50<6:50:31, 14.03s/it] 56%|█████▌    | 2245/4000 [8:58:02<6:40:15, 13.68s/it] 56%|█████▌    | 2246/4000 [8:58:17<6:45:55, 13.89s/it] 56%|█████▌    | 2247/4000 [8:58:29<6:34:21, 13.50s/it] 56%|█████▌    | 2248/4000 [8:58:43<6:38:54, 13.66s/it] 56%|█████▌    | 2249/4000 [8:58:57<6:33:31, 13.48s/it] 56%|█████▋    | 2250/4000 [8:59:11<6:40:14, 13.72s/it]                                                        56%|█████▋    | 2250/4000 [8:59:11<6:40:14, 13.72s/it] 56%|█████▋    | 2251/4000 [8:59:26<6:56:06, 14.27s/it] 56%|█████▋    | 2252/4000 [8:59:39<6:37:17, 13.64s/it] 56%|█████▋    | 2253/4000 [8:59:53<6:48:21, 14.03s/it] 56%|█████▋    | 2254/4000 [9:00:07<6:41:32, 13.80s/it] 56%|█████▋    | 2255/4000 [9:00:21<6:44:48, 13.92s/it] 56%|█████▋    | 2256/4000 [9:00:34<6:38:40, 13.72s/it] 56%|█████▋    | 2257/4000 [9:00:49<6:43:45, 13.90s/it] 56%|█████▋    | 2258/4000 [9:01:04<6:55:11, 14.30s/it] 56%|█████▋    | 2259/4000 [9:01:16<6:35:18, 13.62s/it] 56%|█████▋    | 2260/4000 [9:01:31<6:47:25, 14.05s/it]                                                        56%|█████▋    | 2260/4000 [9:01:31<6:47:25, 14.05s/it] 57%|█████▋    | 2261/4000 [9:01:44<6:38:58, 13.77s/it] 57%|█████▋    | 2262/4000 [9:01:58<6:42:02, 13.88s/it] 57%|█████▋    | 2263/4000 [9:02:11<6:34:38, 13.63s/it] 57%|█████▋    | 2264/4000 [9:02:26<6:41:30, 13.88s/it] 57%|█████▋    | 2265/4000 [9:02:41<6:50:27, 14.19s/it] 57%|█████▋    | 2266/4000 [9:02:53<6:35:03, 13.67s/it] 57%|█████▋    | 2267/4000 [9:03:08<6:48:53, 14.16s/it] 57%|█████▋    | 2268/4000 [9:03:20<6:31:32, 13.56s/it] 57%|█████▋    | 2269/4000 [9:03:35<6:42:55, 13.97s/it] 57%|█████▋    | 2270/4000 [9:03:49<6:37:19, 13.78s/it]                                                        57%|█████▋    | 2270/4000 [9:03:49<6:37:19, 13.78s/it] 57%|█████▋    | 2271/4000 [9:04:03<6:42:19, 13.96s/it] 57%|█████▋    | 2272/4000 [9:04:18<6:48:25, 14.18s/it] 57%|█████▋    | 2273/4000 [9:04:30<6:34:35, 13.71s/it] 57%|█████▋    | 2274/4000 [9:04:45<6:45:20, 14.09s/it] 57%|█████▋    | 2275/4000 [9:04:58<6:28:50, 13.53s/it] 57%|█████▋    | 2276/4000 [9:05:13<6:43:34, 14.05s/it] 57%|█████▋    | 2277/4000 [9:05:26<6:37:33, 13.84s/it] 57%|█████▋    | 2278/4000 [9:05:40<6:41:01, 13.97s/it] 57%|█████▋    | 2279/4000 [9:05:53<6:32:24, 13.68s/it] 57%|█████▋    | 2280/4000 [9:06:08<6:37:24, 13.86s/it]                                                        57%|█████▋    | 2280/4000 [9:06:08<6:37:24, 13.86s/it] 57%|█████▋    | 2281/4000 [9:06:23<6:47:35, 14.23s/it] 57%|█████▋    | 2282/4000 [9:06:35<6:31:31, 13.67s/it] 57%|█████▋    | 2283/4000 [9:06:50<6:38:56, 13.94s/it] 57%|█████▋    | 2284/4000 [9:07:04<6:43:29, 14.11s/it] 57%|█████▋    | 2285/4000 [9:07:17<6:34:47, 13.81s/it] 57%|█████▋    | 2286/4000 [9:07:32<6:45:04, 14.18s/it] 57%|█████▋    | 2287/4000 [9:07:45<6:28:52, 13.62s/it] 57%|█████▋    | 2288/4000 [9:08:00<6:41:33, 14.07s/it] 57%|█████▋    | 2289/4000 [9:08:14<6:43:17, 14.14s/it] 57%|█████▋    | 2290/4000 [9:08:27<6:33:28, 13.81s/it]                                                        57%|█████▋    | 2290/4000 [9:08:27<6:33:28, 13.81s/it] 57%|█████▋    | 2291/4000 [9:08:41<6:34:58, 13.87s/it] 57%|█████▋    | 2292/4000 [9:08:55<6:30:44, 13.73s/it] 57%|█████▋    | 2293/4000 [9:09:09<6:33:13, 13.82s/it] 57%|█████▋    | 2294/4000 [9:09:22<6:26:28, 13.59s/it] 57%|█████▋    | 2295/4000 [9:09:37<6:36:42, 13.96s/it] 57%|█████▋    | 2296/4000 [9:09:49<6:21:33, 13.44s/it] 57%|█████▋    | 2297/4000 [9:10:04<6:38:26, 14.04s/it] 57%|█████▋    | 2298/4000 [9:10:19<6:40:59, 14.14s/it] 57%|█████▋    | 2299/4000 [9:10:32<6:32:24, 13.84s/it] 57%|█████▊    | 2300/4000 [9:10:46<6:38:51, 14.08s/it]                                                        57%|█████▊    | 2300/4000 [9:10:46<6:38:51, 14.08s/it] 58%|█████▊    | 2301/4000 [9:11:00<6:32:33, 13.86s/it] 58%|█████▊    | 2302/4000 [9:11:15<6:42:18, 14.22s/it] 58%|█████▊    | 2303/4000 [9:11:29<6:46:10, 14.36s/it] 58%|█████▊    | 2304/4000 [9:11:43<6:36:49, 14.04s/it] 58%|█████▊    | 2305/4000 [9:11:57<6:36:14, 14.03s/it] 58%|█████▊    | 2306/4000 [9:12:12<6:45:56, 14.38s/it] 58%|█████▊    | 2307/4000 [9:12:24<6:28:29, 13.77s/it] 58%|█████▊    | 2308/4000 [9:12:37<6:23:26, 13.60s/it] 58%|█████▊    | 2309/4000 [9:12:52<6:30:18, 13.85s/it] 58%|█████▊    | 2310/4000 [9:13:05<6:20:27, 13.51s/it]                                                        58%|█████▊    | 2310/4000 [9:13:05<6:20:27, 13.51s/it] 58%|█████▊    | 2311/4000 [9:13:20<6:34:06, 14.00s/it] 58%|█████▊    | 2312/4000 [9:13:34<6:37:59, 14.15s/it] 58%|█████▊    | 2313/4000 [9:13:47<6:23:26, 13.64s/it] 58%|█████▊    | 2314/4000 [9:14:01<6:30:11, 13.89s/it] 58%|█████▊    | 2315/4000 [9:14:16<6:38:38, 14.19s/it] 58%|█████▊    | 2316/4000 [9:14:29<6:24:49, 13.71s/it] 58%|█████▊    | 2317/4000 [9:14:44<6:41:06, 14.30s/it] 58%|█████▊    | 2318/4000 [9:14:59<6:41:32, 14.32s/it] 58%|█████▊    | 2319/4000 [9:15:14<6:48:33, 14.58s/it] 58%|█████▊    | 2320/4000 [9:15:27<6:37:12, 14.19s/it]                                                        58%|█████▊    | 2320/4000 [9:15:27<6:37:12, 14.19s/it] 58%|█████▊    | 2321/4000 [9:15:41<6:38:04, 14.23s/it] 58%|█████▊    | 2322/4000 [9:15:55<6:28:42, 13.90s/it] 58%|█████▊    | 2323/4000 [9:16:09<6:33:06, 14.06s/it] 58%|█████▊    | 2324/4000 [9:16:24<6:42:22, 14.40s/it] 58%|█████▊    | 2325/4000 [9:16:37<6:24:38, 13.78s/it] 58%|█████▊    | 2326/4000 [9:16:52<6:35:17, 14.17s/it] 58%|█████▊    | 2327/4000 [9:17:04<6:20:03, 13.63s/it] 58%|█████▊    | 2328/4000 [9:17:19<6:33:39, 14.13s/it] 58%|█████▊    | 2329/4000 [9:17:33<6:27:53, 13.93s/it] 58%|█████▊    | 2330/4000 [9:17:45<6:14:40, 13.46s/it]                                                        58%|█████▊    | 2330/4000 [9:17:45<6:14:40, 13.46s/it] 58%|█████▊    | 2331/4000 [9:18:00<6:27:29, 13.93s/it] 58%|█████▊    | 2332/4000 [9:18:12<6:10:22, 13.32s/it] 58%|█████▊    | 2333/4000 [9:18:28<6:31:28, 14.09s/it] 58%|█████▊    | 2334/4000 [9:18:42<6:31:11, 14.09s/it] 58%|█████▊    | 2335/4000 [9:18:55<6:23:54, 13.83s/it] 58%|█████▊    | 2336/4000 [9:19:10<6:27:45, 13.98s/it] 58%|█████▊    | 2337/4000 [9:19:23<6:21:57, 13.78s/it] 58%|█████▊    | 2338/4000 [9:19:38<6:34:06, 14.23s/it] 58%|█████▊    | 2339/4000 [9:19:50<6:17:39, 13.64s/it] 58%|█████▊    | 2340/4000 [9:20:06<6:29:10, 14.07s/it]                                                        58%|█████▊    | 2340/4000 [9:20:06<6:29:10, 14.07s/it] 59%|█████▊    | 2341/4000 [9:20:17<6:09:57, 13.38s/it] 59%|█████▊    | 2342/4000 [9:20:33<6:28:14, 14.05s/it] 59%|█████▊    | 2343/4000 [9:20:45<6:08:47, 13.35s/it] 59%|█████▊    | 2344/4000 [9:21:00<6:26:35, 14.01s/it] 59%|█████▊    | 2345/4000 [9:21:14<6:20:52, 13.81s/it] 59%|█████▊    | 2346/4000 [9:21:28<6:24:53, 13.96s/it] 59%|█████▊    | 2347/4000 [9:21:41<6:21:44, 13.86s/it] 59%|█████▊    | 2348/4000 [9:21:56<6:24:31, 13.97s/it] 59%|█████▊    | 2349/4000 [9:22:09<6:19:22, 13.79s/it] 59%|█████▉    | 2350/4000 [9:22:24<6:25:07, 14.00s/it]                                                        59%|█████▉    | 2350/4000 [9:22:24<6:25:07, 14.00s/it] 59%|█████▉    | 2351/4000 [9:22:37<6:19:50, 13.82s/it] 59%|█████▉    | 2352/4000 [9:22:51<6:20:42, 13.86s/it] 59%|█████▉    | 2353/4000 [9:23:04<6:15:12, 13.67s/it] 59%|█████▉    | 2354/4000 [9:23:19<6:28:52, 14.18s/it] 59%|█████▉    | 2355/4000 [9:23:32<6:17:37, 13.77s/it] 59%|█████▉    | 2356/4000 [9:23:48<6:30:23, 14.25s/it] 59%|█████▉    | 2357/4000 [9:24:00<6:16:17, 13.74s/it] 59%|█████▉    | 2358/4000 [9:24:16<6:31:46, 14.32s/it] 59%|█████▉    | 2359/4000 [9:24:28<6:14:44, 13.70s/it] 59%|█████▉    | 2360/4000 [9:24:43<6:25:06, 14.09s/it]                                                        59%|█████▉    | 2360/4000 [9:24:43<6:25:06, 14.09s/it] 59%|█████▉    | 2361/4000 [9:24:56<6:17:45, 13.83s/it] 59%|█████▉    | 2362/4000 [9:25:11<6:23:20, 14.04s/it] 59%|█████▉    | 2363/4000 [9:25:24<6:19:08, 13.90s/it] 59%|█████▉    | 2364/4000 [9:25:39<6:26:48, 14.19s/it] 59%|█████▉    | 2365/4000 [9:25:55<6:35:11, 14.50s/it] 59%|█████▉    | 2366/4000 [9:26:07<6:20:33, 13.97s/it] 59%|█████▉    | 2367/4000 [9:26:23<6:31:51, 14.40s/it] 59%|█████▉    | 2368/4000 [9:26:35<6:16:29, 13.84s/it] 59%|█████▉    | 2369/4000 [9:26:51<6:29:44, 14.34s/it] 59%|█████▉    | 2370/4000 [9:27:03<6:12:15, 13.70s/it]                                                        59%|█████▉    | 2370/4000 [9:27:03<6:12:15, 13.70s/it] 59%|█████▉    | 2371/4000 [9:27:18<6:22:27, 14.09s/it] 59%|█████▉    | 2372/4000 [9:27:31<6:17:44, 13.92s/it] 59%|█████▉    | 2373/4000 [9:27:46<6:23:11, 14.13s/it] 59%|█████▉    | 2374/4000 [9:27:59<6:15:37, 13.86s/it] 59%|█████▉    | 2375/4000 [9:28:14<6:25:42, 14.24s/it] 59%|█████▉    | 2376/4000 [9:28:28<6:18:21, 13.98s/it] 59%|█████▉    | 2377/4000 [9:28:43<6:24:49, 14.23s/it] 59%|█████▉    | 2378/4000 [9:28:56<6:20:43, 14.08s/it] 59%|█████▉    | 2379/4000 [9:29:11<6:22:59, 14.18s/it] 60%|█████▉    | 2380/4000 [9:29:24<6:17:22, 13.98s/it]                                                        60%|█████▉    | 2380/4000 [9:29:24<6:17:22, 13.98s/it] 60%|█████▉    | 2381/4000 [9:29:39<6:26:57, 14.34s/it] 60%|█████▉    | 2382/4000 [9:29:52<6:09:25, 13.70s/it] 60%|█████▉    | 2383/4000 [9:30:05<6:05:15, 13.55s/it] 60%|█████▉    | 2384/4000 [9:30:19<6:09:15, 13.71s/it] 60%|█████▉    | 2385/4000 [9:30:32<6:05:08, 13.57s/it] 60%|█████▉    | 2386/4000 [9:30:47<6:16:19, 13.99s/it] 60%|█████▉    | 2387/4000 [9:31:00<6:09:03, 13.73s/it] 60%|█████▉    | 2388/4000 [9:31:16<6:24:51, 14.32s/it] 60%|█████▉    | 2389/4000 [9:31:28<6:09:35, 13.76s/it] 60%|█████▉    | 2390/4000 [9:31:44<6:22:39, 14.26s/it]                                                        60%|█████▉    | 2390/4000 [9:31:44<6:22:39, 14.26s/it] 60%|█████▉    | 2391/4000 [9:31:56<6:07:18, 13.70s/it] 60%|█████▉    | 2392/4000 [9:32:11<6:17:21, 14.08s/it] 60%|█████▉    | 2393/4000 [9:32:24<6:03:38, 13.58s/it] 60%|█████▉    | 2394/4000 [9:32:39<6:18:44, 14.15s/it] 60%|█████▉    | 2395/4000 [9:32:51<6:03:04, 13.57s/it] 60%|█████▉    | 2396/4000 [9:33:05<6:00:23, 13.48s/it] 60%|█████▉    | 2397/4000 [9:33:20<6:14:22, 14.01s/it] 60%|█████▉    | 2398/4000 [9:33:32<5:58:29, 13.43s/it] 60%|█████▉    | 2399/4000 [9:33:47<6:14:03, 14.02s/it] 60%|██████    | 2400/4000 [9:33:59<5:58:13, 13.43s/it]                                                        60%|██████    | 2400/4000 [9:33:59<5:58:13, 13.43s/it] 60%|██████    | 2401/4000 [9:34:13<5:56:39, 13.38s/it] 60%|██████    | 2402/4000 [9:34:27<6:03:50, 13.66s/it] 60%|██████    | 2403/4000 [9:34:43<6:19:37, 14.26s/it] 60%|██████    | 2404/4000 [9:34:56<6:10:03, 13.91s/it] 60%|██████    | 2405/4000 [9:35:10<6:11:06, 13.96s/it] 60%|██████    | 2406/4000 [9:35:23<6:03:47, 13.69s/it] 60%|██████    | 2407/4000 [9:35:35<5:51:15, 13.23s/it] 60%|██████    | 2408/4000 [9:35:51<6:09:45, 13.94s/it] 60%|██████    | 2409/4000 [9:36:03<5:57:21, 13.48s/it] 60%|██████    | 2410/4000 [9:36:18<6:09:40, 13.95s/it]                                                        60%|██████    | 2410/4000 [9:36:18<6:09:40, 13.95s/it] 60%|██████    | 2411/4000 [9:36:32<6:05:34, 13.80s/it] 60%|██████    | 2412/4000 [9:36:44<5:54:09, 13.38s/it] 60%|██████    | 2413/4000 [9:37:00<6:12:56, 14.10s/it] 60%|██████    | 2414/4000 [9:37:12<5:58:28, 13.56s/it] 60%|██████    | 2415/4000 [9:37:27<6:12:50, 14.11s/it] 60%|██████    | 2416/4000 [9:37:40<6:01:53, 13.71s/it] 60%|██████    | 2417/4000 [9:37:55<6:13:20, 14.15s/it] 60%|██████    | 2418/4000 [9:38:07<5:56:44, 13.53s/it] 60%|██████    | 2419/4000 [9:38:23<6:10:54, 14.08s/it] 60%|██████    | 2420/4000 [9:38:36<6:06:57, 13.94s/it]                                                        60%|██████    | 2420/4000 [9:38:36<6:06:57, 13.94s/it] 61%|██████    | 2421/4000 [9:38:51<6:10:24, 14.08s/it] 61%|██████    | 2422/4000 [9:39:05<6:09:02, 14.03s/it] 61%|██████    | 2423/4000 [9:39:19<6:12:01, 14.15s/it] 61%|██████    | 2424/4000 [9:39:33<6:05:53, 13.93s/it] 61%|██████    | 2425/4000 [9:39:45<5:51:58, 13.41s/it] 61%|██████    | 2426/4000 [9:40:00<6:06:44, 13.98s/it] 61%|██████    | 2427/4000 [9:40:13<5:55:53, 13.58s/it] 61%|██████    | 2428/4000 [9:40:28<6:07:31, 14.03s/it] 61%|██████    | 2429/4000 [9:40:41<6:03:07, 13.87s/it] 61%|██████    | 2430/4000 [9:40:56<6:10:24, 14.16s/it]                                                        61%|██████    | 2430/4000 [9:40:56<6:10:24, 14.16s/it] 61%|██████    | 2431/4000 [9:41:09<6:03:07, 13.89s/it] 61%|██████    | 2432/4000 [9:41:24<6:08:59, 14.12s/it] 61%|██████    | 2433/4000 [9:41:37<6:00:51, 13.82s/it] 61%|██████    | 2434/4000 [9:41:50<5:51:27, 13.47s/it] 61%|██████    | 2435/4000 [9:42:05<6:06:01, 14.03s/it] 61%|██████    | 2436/4000 [9:42:19<6:04:12, 13.97s/it] 61%|██████    | 2437/4000 [9:42:33<6:07:49, 14.12s/it] 61%|██████    | 2438/4000 [9:42:47<6:02:12, 13.91s/it] 61%|██████    | 2439/4000 [9:42:59<5:49:50, 13.45s/it] 61%|██████    | 2440/4000 [9:43:15<6:03:55, 14.00s/it]                                                        61%|██████    | 2440/4000 [9:43:15<6:03:55, 14.00s/it] 61%|██████    | 2441/4000 [9:43:27<5:50:30, 13.49s/it] 61%|██████    | 2442/4000 [9:43:42<6:05:42, 14.08s/it] 61%|██████    | 2443/4000 [9:43:57<6:11:59, 14.33s/it] 61%|██████    | 2444/4000 [9:44:11<6:06:00, 14.11s/it] 61%|██████    | 2445/4000 [9:44:24<6:00:37, 13.91s/it] 61%|██████    | 2446/4000 [9:44:39<6:06:43, 14.16s/it] 61%|██████    | 2447/4000 [9:44:52<5:58:25, 13.85s/it] 61%|██████    | 2448/4000 [9:45:07<6:04:28, 14.09s/it] 61%|██████    | 2449/4000 [9:45:20<5:59:01, 13.89s/it] 61%|██████▏   | 2450/4000 [9:45:33<5:47:28, 13.45s/it]                                                        61%|██████▏   | 2450/4000 [9:45:33<5:47:28, 13.45s/it] 61%|██████▏   | 2451/4000 [9:45:48<6:03:18, 14.07s/it] 61%|██████▏   | 2452/4000 [9:46:03<6:07:01, 14.23s/it] 61%|██████▏   | 2453/4000 [9:46:16<5:57:52, 13.88s/it] 61%|██████▏   | 2454/4000 [9:46:31<6:09:03, 14.32s/it] 61%|██████▏   | 2455/4000 [9:46:44<5:54:07, 13.75s/it] 61%|██████▏   | 2456/4000 [9:46:57<5:52:12, 13.69s/it] 61%|██████▏   | 2457/4000 [9:47:12<6:01:44, 14.07s/it] 61%|██████▏   | 2458/4000 [9:47:25<5:54:50, 13.81s/it] 61%|██████▏   | 2459/4000 [9:47:39<5:57:41, 13.93s/it] 62%|██████▏   | 2460/4000 [9:47:53<5:55:42, 13.86s/it]                                                        62%|██████▏   | 2460/4000 [9:47:53<5:55:42, 13.86s/it] 62%|██████▏   | 2461/4000 [9:48:06<5:51:01, 13.68s/it] 62%|██████▏   | 2462/4000 [9:48:21<5:57:14, 13.94s/it] 62%|██████▏   | 2463/4000 [9:48:35<5:55:34, 13.88s/it] 62%|██████▏   | 2464/4000 [9:48:49<5:58:19, 14.00s/it] 62%|██████▏   | 2465/4000 [9:49:02<5:53:58, 13.84s/it] 62%|██████▏   | 2466/4000 [9:49:17<6:00:41, 14.11s/it] 62%|██████▏   | 2467/4000 [9:49:30<5:52:58, 13.82s/it] 62%|██████▏   | 2468/4000 [9:49:45<6:00:15, 14.11s/it] 62%|██████▏   | 2469/4000 [9:49:59<5:57:30, 14.01s/it] 62%|██████▏   | 2470/4000 [9:50:13<5:59:42, 14.11s/it]                                                        62%|██████▏   | 2470/4000 [9:50:13<5:59:42, 14.11s/it] 62%|██████▏   | 2471/4000 [9:50:27<5:56:50, 14.00s/it] 62%|██████▏   | 2472/4000 [9:50:43<6:08:36, 14.47s/it] 62%|██████▏   | 2473/4000 [9:50:55<5:52:29, 13.85s/it] 62%|██████▏   | 2474/4000 [9:51:10<6:02:24, 14.25s/it] 62%|██████▏   | 2475/4000 [9:51:23<5:49:40, 13.76s/it] 62%|██████▏   | 2476/4000 [9:51:38<6:04:12, 14.34s/it] 62%|██████▏   | 2477/4000 [9:51:51<5:50:15, 13.80s/it] 62%|██████▏   | 2478/4000 [9:52:07<6:04:10, 14.36s/it] 62%|██████▏   | 2479/4000 [9:52:19<5:50:45, 13.84s/it] 62%|██████▏   | 2480/4000 [9:52:35<6:01:11, 14.26s/it]                                                        62%|██████▏   | 2480/4000 [9:52:35<6:01:11, 14.26s/it] 62%|██████▏   | 2481/4000 [9:52:48<5:53:23, 13.96s/it] 62%|██████▏   | 2482/4000 [9:53:03<5:59:20, 14.20s/it] 62%|██████▏   | 2483/4000 [9:53:16<5:51:47, 13.91s/it] 62%|██████▏   | 2484/4000 [9:53:28<5:41:41, 13.52s/it] 62%|██████▏   | 2485/4000 [9:53:44<5:59:17, 14.23s/it] 62%|██████▏   | 2486/4000 [9:53:58<5:55:46, 14.10s/it] 62%|██████▏   | 2487/4000 [9:54:12<5:54:23, 14.05s/it] 62%|██████▏   | 2488/4000 [9:54:27<5:59:37, 14.27s/it] 62%|██████▏   | 2489/4000 [9:54:41<5:55:52, 14.13s/it] 62%|██████▏   | 2490/4000 [9:54:56<6:08:17, 14.63s/it]                                                        62%|██████▏   | 2490/4000 [9:54:56<6:08:17, 14.63s/it] 62%|██████▏   | 2491/4000 [9:55:11<6:07:30, 14.61s/it] 62%|██████▏   | 2492/4000 [9:55:24<5:57:06, 14.21s/it] 62%|██████▏   | 2493/4000 [9:55:39<6:01:16, 14.38s/it] 62%|██████▏   | 2494/4000 [9:55:53<5:55:27, 14.16s/it] 62%|██████▏   | 2495/4000 [9:56:05<5:42:17, 13.65s/it] 62%|██████▏   | 2496/4000 [9:56:21<5:56:51, 14.24s/it] 62%|██████▏   | 2497/4000 [9:56:33<5:43:56, 13.73s/it] 62%|██████▏   | 2498/4000 [9:56:49<5:59:55, 14.38s/it] 62%|██████▏   | 2499/4000 [9:57:04<6:01:13, 14.44s/it] 62%|██████▎   | 2500/4000 [9:57:17<5:55:20, 14.21s/it]                                                        62%|██████▎   | 2500/4000 [9:57:17<5:55:20, 14.21s/it]{'eval_loss': '0.1649', 'eval_runtime': '383.7', 'eval_samples_per_second': '1.311', 'eval_steps_per_second': '1.311', 'epoch': '3.185'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2301:{'loss': '0.9701', 'grad_norm': '0.3416', 'learning_rate': '8.156e-05', 'epoch': '3.647'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2393: 14%|█▍        | 70/503 [00:53<04:49,  1.50it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2493: 34%|███▍      | 170/503 [02:12<04:35,  1.21it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2499: 35%|███▍      | 176/503 [02:16<03:12,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2565: 49%|████▊     | 244/503 [03:10<02:32,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2589: 54%|█████▎    | 270/503 [03:31<03:41,  1.05it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2664: 70%|██████▉   | 350/503 [04:32<02:03,  1.24it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2665: 70%|██████▉   | 351/503 [04:32<01:46,  1.43it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2666: 70%|██████▉   | 352/503 [04:32<01:32,  1.63it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2667: 70%|███████   | 353/503 [04:33<01:20,  1.87it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2668: 70%|███████   | 354/503 [04:35<02:27,  1.01it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2684: 74%|███████▎  | 370/503 [04:48<02:28,  1.11s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2714: 80%|███████▉  | 402/503 [05:10<00:55,  1.84it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2774: 92%|█████████▏| 465/503 [05:58<00:22,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2779: 93%|█████████▎| 470/503 [06:03<00:35,  1.08s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2810:100%|█████████▉| 502/503 [06:26<00:00,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2818: 63%|██████▎   | 2501/4000 [10:04:04<54:53:07, 131.81s/it] 63%|██████▎   | 2502/4000 [10:04:17<40:05:47, 96.36s/it]  63%|██████▎   | 2503/4000 [10:04:32<29:52:49, 71.86s/it] 63%|██████▎   | 2504/4000 [10:04:45<22:35:14, 54.35s/it] 63%|██████▎   | 2505/4000 [10:05:00<17:38:56, 42.50s/it] 63%|██████▎   | 2506/4000 [10:05:13<13:58:55, 33.69s/it] 63%|██████▎   | 2507/4000 [10:05:27<11:27:32, 27.63s/it] 63%|██████▎   | 2508/4000 [10:05:42<9:53:12, 23.86s/it]  63%|██████▎   | 2509/4000 [10:05:55<8:33:34, 20.67s/it] 63%|██████▎   | 2510/4000 [10:06:10<7:48:27, 18.86s/it]                                                         63%|██████▎   | 2510/4000 [10:06:10<7:48:27, 18.86s/it] 63%|██████▎   | 2511/4000 [10:06:24<7:09:09, 17.29s/it] 63%|██████▎   | 2512/4000 [10:06:30<5:45:04, 13.91s/it] 63%|██████▎   | 2513/4000 [10:06:44<5:49:24, 14.10s/it] 63%|██████▎   | 2514/4000 [10:06:58<5:45:18, 13.94s/it] 63%|██████▎   | 2515/4000 [10:07:12<5:50:55, 14.18s/it] 63%|██████▎   | 2516/4000 [10:07:26<5:45:01, 13.95s/it] 63%|██████▎   | 2517/4000 [10:07:41<5:51:58, 14.24s/it] 63%|██████▎   | 2518/4000 [10:07:54<5:46:13, 14.02s/it] 63%|██████▎   | 2519/4000 [10:08:07<5:33:58, 13.53s/it] 63%|██████▎   | 2520/4000 [10:08:22<5:50:50, 14.22s/it]                                                         63%|██████▎   | 2520/4000 [10:08:22<5:50:50, 14.22s/it] 63%|██████▎   | 2521/4000 [10:08:37<5:52:50, 14.31s/it] 63%|██████▎   | 2522/4000 [10:08:51<5:48:21, 14.14s/it] 63%|██████▎   | 2523/4000 [10:09:04<5:43:38, 13.96s/it] 63%|██████▎   | 2524/4000 [10:09:19<5:48:29, 14.17s/it] 63%|██████▎   | 2525/4000 [10:09:32<5:42:11, 13.92s/it] 63%|██████▎   | 2526/4000 [10:09:47<5:46:14, 14.09s/it] 63%|██████▎   | 2527/4000 [10:10:01<5:44:23, 14.03s/it] 63%|██████▎   | 2528/4000 [10:10:15<5:49:06, 14.23s/it] 63%|██████▎   | 2529/4000 [10:10:29<5:43:09, 14.00s/it] 63%|██████▎   | 2530/4000 [10:10:43<5:45:52, 14.12s/it]                                                         63%|██████▎   | 2530/4000 [10:10:43<5:45:52, 14.12s/it] 63%|██████▎   | 2531/4000 [10:10:56<5:37:44, 13.79s/it] 63%|██████▎   | 2532/4000 [10:11:12<5:50:33, 14.33s/it] 63%|██████▎   | 2533/4000 [10:11:24<5:35:07, 13.71s/it] 63%|██████▎   | 2534/4000 [10:11:40<5:49:22, 14.30s/it] 63%|██████▎   | 2535/4000 [10:11:52<5:37:45, 13.83s/it] 63%|██████▎   | 2536/4000 [10:12:08<5:51:21, 14.40s/it] 63%|██████▎   | 2537/4000 [10:12:20<5:34:48, 13.73s/it] 63%|██████▎   | 2538/4000 [10:12:36<5:47:03, 14.24s/it] 63%|██████▎   | 2539/4000 [10:12:48<5:32:16, 13.65s/it] 64%|██████▎   | 2540/4000 [10:13:03<5:42:55, 14.09s/it]                                                         64%|██████▎   | 2540/4000 [10:13:03<5:42:55, 14.09s/it] 64%|██████▎   | 2541/4000 [10:13:17<5:38:19, 13.91s/it] 64%|██████▎   | 2542/4000 [10:13:29<5:26:30, 13.44s/it] 64%|██████▎   | 2543/4000 [10:13:45<5:42:38, 14.11s/it] 64%|██████▎   | 2544/4000 [10:13:57<5:31:01, 13.64s/it] 64%|██████▎   | 2545/4000 [10:14:13<5:44:42, 14.21s/it] 64%|██████▎   | 2546/4000 [10:14:25<5:31:35, 13.68s/it] 64%|██████▎   | 2547/4000 [10:14:41<5:44:14, 14.22s/it] 64%|██████▎   | 2548/4000 [10:14:54<5:39:08, 14.01s/it] 64%|██████▎   | 2549/4000 [10:15:09<5:44:53, 14.26s/it] 64%|██████▍   | 2550/4000 [10:15:22<5:35:05, 13.87s/it]                                                         64%|██████▍   | 2550/4000 [10:15:22<5:35:05, 13.87s/it] 64%|██████▍   | 2551/4000 [10:15:35<5:25:11, 13.47s/it] 64%|██████▍   | 2552/4000 [10:15:50<5:39:36, 14.07s/it] 64%|██████▍   | 2553/4000 [10:16:05<5:44:28, 14.28s/it] 64%|██████▍   | 2554/4000 [10:16:18<5:38:56, 14.06s/it] 64%|██████▍   | 2555/4000 [10:16:31<5:25:42, 13.52s/it] 64%|██████▍   | 2556/4000 [10:16:46<5:38:27, 14.06s/it] 64%|██████▍   | 2557/4000 [10:16:59<5:30:56, 13.76s/it] 64%|██████▍   | 2558/4000 [10:17:11<5:20:46, 13.35s/it] 64%|██████▍   | 2559/4000 [10:17:27<5:36:04, 13.99s/it] 64%|██████▍   | 2560/4000 [10:17:39<5:23:33, 13.48s/it]                                                         64%|██████▍   | 2560/4000 [10:17:39<5:23:33, 13.48s/it] 64%|██████▍   | 2561/4000 [10:17:55<5:38:06, 14.10s/it] 64%|██████▍   | 2562/4000 [10:18:10<5:43:27, 14.33s/it] 64%|██████▍   | 2563/4000 [10:18:23<5:34:12, 13.95s/it] 64%|██████▍   | 2564/4000 [10:18:35<5:19:05, 13.33s/it] 64%|██████▍   | 2565/4000 [10:18:50<5:36:14, 14.06s/it] 64%|██████▍   | 2566/4000 [10:19:04<5:30:09, 13.81s/it] 64%|██████▍   | 2567/4000 [10:19:16<5:21:28, 13.46s/it] 64%|██████▍   | 2568/4000 [10:19:32<5:34:55, 14.03s/it] 64%|██████▍   | 2569/4000 [10:19:44<5:24:09, 13.59s/it] 64%|██████▍   | 2570/4000 [10:20:00<5:36:47, 14.13s/it]                                                         64%|██████▍   | 2570/4000 [10:20:00<5:36:47, 14.13s/it] 64%|██████▍   | 2571/4000 [10:20:12<5:25:52, 13.68s/it] 64%|██████▍   | 2572/4000 [10:20:28<5:39:06, 14.25s/it] 64%|██████▍   | 2573/4000 [10:20:41<5:29:10, 13.84s/it] 64%|██████▍   | 2574/4000 [10:20:53<5:17:14, 13.35s/it] 64%|██████▍   | 2575/4000 [10:21:08<5:30:21, 13.91s/it] 64%|██████▍   | 2576/4000 [10:21:21<5:21:03, 13.53s/it] 64%|██████▍   | 2577/4000 [10:21:36<5:34:42, 14.11s/it] 64%|██████▍   | 2578/4000 [10:21:49<5:25:39, 13.74s/it] 64%|██████▍   | 2579/4000 [10:22:05<5:37:59, 14.27s/it] 64%|██████▍   | 2580/4000 [10:22:17<5:21:38, 13.59s/it]                                                         64%|██████▍   | 2580/4000 [10:22:17<5:21:38, 13.59s/it] 65%|██████▍   | 2581/4000 [10:22:30<5:22:17, 13.63s/it] 65%|██████▍   | 2582/4000 [10:22:44<5:20:34, 13.56s/it] 65%|██████▍   | 2583/4000 [10:22:58<5:27:24, 13.86s/it] 65%|██████▍   | 2584/4000 [10:23:11<5:22:56, 13.68s/it] 65%|██████▍   | 2585/4000 [10:23:26<5:26:15, 13.83s/it] 65%|██████▍   | 2586/4000 [10:23:39<5:19:55, 13.58s/it] 65%|██████▍   | 2587/4000 [10:23:53<5:25:13, 13.81s/it] 65%|██████▍   | 2588/4000 [10:24:07<5:23:50, 13.76s/it] 65%|██████▍   | 2589/4000 [10:24:21<5:29:44, 14.02s/it] 65%|██████▍   | 2590/4000 [10:24:35<5:25:26, 13.85s/it]                                                         65%|██████▍   | 2590/4000 [10:24:35<5:25:26, 13.85s/it] 65%|██████▍   | 2591/4000 [10:24:50<5:34:36, 14.25s/it] 65%|██████▍   | 2592/4000 [10:25:02<5:19:54, 13.63s/it] 65%|██████▍   | 2593/4000 [10:25:17<5:30:12, 14.08s/it] 65%|██████▍   | 2594/4000 [10:25:30<5:18:07, 13.58s/it] 65%|██████▍   | 2595/4000 [10:25:46<5:35:40, 14.33s/it] 65%|██████▍   | 2596/4000 [10:25:58<5:22:03, 13.76s/it] 65%|██████▍   | 2597/4000 [10:26:14<5:34:52, 14.32s/it] 65%|██████▍   | 2598/4000 [10:26:27<5:26:59, 13.99s/it] 65%|██████▍   | 2599/4000 [10:26:38<5:09:06, 13.24s/it] 65%|██████▌   | 2600/4000 [10:26:54<5:27:30, 14.04s/it]                                                         65%|██████▌   | 2600/4000 [10:26:54<5:27:30, 14.04s/it] 65%|██████▌   | 2601/4000 [10:27:09<5:31:06, 14.20s/it] 65%|██████▌   | 2602/4000 [10:27:22<5:24:32, 13.93s/it] 65%|██████▌   | 2603/4000 [10:27:34<5:11:46, 13.39s/it] 65%|██████▌   | 2604/4000 [10:27:51<5:31:26, 14.25s/it] 65%|██████▌   | 2605/4000 [10:28:03<5:19:13, 13.73s/it] 65%|██████▌   | 2606/4000 [10:28:19<5:32:39, 14.32s/it] 65%|██████▌   | 2607/4000 [10:28:33<5:28:35, 14.15s/it] 65%|██████▌   | 2608/4000 [10:28:47<5:32:04, 14.31s/it] 65%|██████▌   | 2609/4000 [10:29:01<5:26:20, 14.08s/it] 65%|██████▌   | 2610/4000 [10:29:15<5:29:27, 14.22s/it]                                                         65%|██████▌   | 2610/4000 [10:29:15<5:29:27, 14.22s/it] 65%|██████▌   | 2611/4000 [10:29:29<5:22:14, 13.92s/it] 65%|██████▌   | 2612/4000 [10:29:43<5:23:20, 13.98s/it] 65%|██████▌   | 2613/4000 [10:29:56<5:17:13, 13.72s/it] 65%|██████▌   | 2614/4000 [10:30:08<5:09:22, 13.39s/it] 65%|██████▌   | 2615/4000 [10:30:24<5:20:38, 13.89s/it] 65%|██████▌   | 2616/4000 [10:30:37<5:18:01, 13.79s/it] 65%|██████▌   | 2617/4000 [10:30:52<5:25:28, 14.12s/it] 65%|██████▌   | 2618/4000 [10:31:05<5:20:44, 13.92s/it] 65%|██████▌   | 2619/4000 [10:31:20<5:26:00, 14.16s/it] 66%|██████▌   | 2620/4000 [10:31:34<5:21:17, 13.97s/it]                                                         66%|██████▌   | 2620/4000 [10:31:34<5:21:17, 13.97s/it] 66%|██████▌   | 2621/4000 [10:31:46<5:07:32, 13.38s/it] 66%|██████▌   | 2622/4000 [10:32:01<5:22:35, 14.05s/it] 66%|██████▌   | 2623/4000 [10:32:14<5:11:12, 13.56s/it] 66%|██████▌   | 2624/4000 [10:32:29<5:20:56, 13.99s/it] 66%|██████▌   | 2625/4000 [10:32:42<5:15:54, 13.79s/it] 66%|██████▌   | 2626/4000 [10:32:57<5:21:40, 14.05s/it] 66%|██████▌   | 2627/4000 [10:33:10<5:14:03, 13.72s/it] 66%|██████▌   | 2628/4000 [10:33:24<5:18:47, 13.94s/it] 66%|██████▌   | 2629/4000 [10:33:38<5:15:55, 13.83s/it] 66%|██████▌   | 2630/4000 [10:33:51<5:09:59, 13.58s/it]                                                         66%|██████▌   | 2630/4000 [10:33:51<5:09:59, 13.58s/it] 66%|██████▌   | 2631/4000 [10:34:06<5:23:14, 14.17s/it] 66%|██████▌   | 2632/4000 [10:34:19<5:10:27, 13.62s/it] 66%|██████▌   | 2633/4000 [10:34:32<5:07:38, 13.50s/it] 66%|██████▌   | 2634/4000 [10:34:47<5:21:05, 14.10s/it] 66%|██████▌   | 2635/4000 [10:35:00<5:10:32, 13.65s/it] 66%|██████▌   | 2636/4000 [10:35:15<5:23:55, 14.25s/it] 66%|██████▌   | 2637/4000 [10:35:30<5:25:47, 14.34s/it] 66%|██████▌   | 2638/4000 [10:35:43<5:17:52, 14.00s/it] 66%|██████▌   | 2639/4000 [10:35:56<5:07:23, 13.55s/it] 66%|██████▌   | 2640/4000 [10:36:11<5:20:16, 14.13s/it]                                                         66%|██████▌   | 2640/4000 [10:36:11<5:20:16, 14.13s/it] 66%|██████▌   | 2641/4000 [10:36:25<5:15:37, 13.94s/it] 66%|██████▌   | 2642/4000 [10:36:37<5:02:51, 13.38s/it] 66%|██████▌   | 2643/4000 [10:36:53<5:20:23, 14.17s/it] 66%|██████▌   | 2644/4000 [10:37:05<5:09:58, 13.72s/it] 66%|██████▌   | 2645/4000 [10:37:21<5:20:40, 14.20s/it] 66%|██████▌   | 2646/4000 [10:37:36<5:27:41, 14.52s/it] 66%|██████▌   | 2647/4000 [10:37:49<5:19:05, 14.15s/it] 66%|██████▌   | 2648/4000 [10:38:03<5:16:44, 14.06s/it] 66%|██████▌   | 2649/4000 [10:38:17<5:11:58, 13.86s/it] 66%|██████▋   | 2650/4000 [10:38:30<5:08:47, 13.72s/it]                                                         66%|██████▋   | 2650/4000 [10:38:30<5:08:47, 13.72s/it] 66%|██████▋   | 2651/4000 [10:38:44<5:11:42, 13.86s/it] 66%|██████▋   | 2652/4000 [10:38:58<5:11:26, 13.86s/it] 66%|██████▋   | 2653/4000 [10:39:13<5:16:22, 14.09s/it] 66%|██████▋   | 2654/4000 [10:39:26<5:12:17, 13.92s/it] 66%|██████▋   | 2655/4000 [10:39:39<5:02:40, 13.50s/it] 66%|██████▋   | 2656/4000 [10:39:54<5:15:31, 14.09s/it] 66%|██████▋   | 2657/4000 [10:40:07<5:03:50, 13.57s/it] 66%|██████▋   | 2658/4000 [10:40:22<5:17:39, 14.20s/it] 66%|██████▋   | 2659/4000 [10:40:37<5:20:55, 14.36s/it] 66%|██████▋   | 2660/4000 [10:40:50<5:12:45, 14.00s/it]                                                         66%|██████▋   | 2660/4000 [10:40:50<5:12:45, 14.00s/it] 67%|██████▋   | 2661/4000 [10:41:06<5:23:00, 14.47s/it] 67%|██████▋   | 2662/4000 [10:41:18<5:06:25, 13.74s/it] 67%|██████▋   | 2663/4000 [10:41:31<5:06:26, 13.75s/it] 67%|██████▋   | 2664/4000 [10:41:46<5:11:04, 13.97s/it] 67%|██████▋   | 2665/4000 [10:41:59<5:05:05, 13.71s/it] 67%|██████▋   | 2666/4000 [10:42:13<5:08:53, 13.89s/it] 67%|██████▋   | 2667/4000 [10:42:27<5:05:13, 13.74s/it] 67%|██████▋   | 2668/4000 [10:42:41<5:11:09, 14.02s/it] 67%|██████▋   | 2669/4000 [10:42:54<5:03:30, 13.68s/it] 67%|██████▋   | 2670/4000 [10:43:10<5:18:58, 14.39s/it]                                                         67%|██████▋   | 2670/4000 [10:43:10<5:18:58, 14.39s/it] 67%|██████▋   | 2671/4000 [10:43:23<5:05:21, 13.79s/it] 67%|██████▋   | 2672/4000 [10:43:36<5:02:01, 13.65s/it] 67%|██████▋   | 2673/4000 [10:43:50<5:06:29, 13.86s/it] 67%|██████▋   | 2674/4000 [10:44:04<5:05:26, 13.82s/it] 67%|██████▋   | 2675/4000 [10:44:19<5:09:50, 14.03s/it] 67%|██████▋   | 2676/4000 [10:44:32<5:07:09, 13.92s/it] 67%|██████▋   | 2677/4000 [10:44:47<5:10:53, 14.10s/it] 67%|██████▋   | 2678/4000 [10:45:01<5:07:46, 13.97s/it] 67%|██████▋   | 2679/4000 [10:45:13<5:00:58, 13.67s/it] 67%|██████▋   | 2680/4000 [10:45:27<5:02:01, 13.73s/it]                                                         67%|██████▋   | 2680/4000 [10:45:27<5:02:01, 13.73s/it] 67%|██████▋   | 2681/4000 [10:45:41<4:58:43, 13.59s/it] 67%|██████▋   | 2682/4000 [10:45:55<5:02:59, 13.79s/it] 67%|██████▋   | 2683/4000 [10:46:08<4:59:22, 13.64s/it] 67%|██████▋   | 2684/4000 [10:46:23<5:06:02, 13.95s/it] 67%|██████▋   | 2685/4000 [10:46:37<5:03:46, 13.86s/it] 67%|██████▋   | 2686/4000 [10:46:52<5:14:37, 14.37s/it] 67%|██████▋   | 2687/4000 [10:47:05<5:02:25, 13.82s/it] 67%|██████▋   | 2688/4000 [10:47:20<5:14:57, 14.40s/it] 67%|██████▋   | 2689/4000 [10:47:33<5:00:04, 13.73s/it] 67%|██████▋   | 2690/4000 [10:47:46<4:57:58, 13.65s/it]                                                         67%|██████▋   | 2690/4000 [10:47:46<4:57:58, 13.65s/it] 67%|██████▋   | 2691/4000 [10:48:01<5:03:31, 13.91s/it] 67%|██████▋   | 2692/4000 [10:48:14<5:00:46, 13.80s/it] 67%|██████▋   | 2693/4000 [10:48:29<5:05:11, 14.01s/it] 67%|██████▋   | 2694/4000 [10:48:42<5:01:23, 13.85s/it] 67%|██████▋   | 2695/4000 [10:48:58<5:12:06, 14.35s/it] 67%|██████▋   | 2696/4000 [10:49:10<4:57:20, 13.68s/it] 67%|██████▋   | 2697/4000 [10:49:25<5:08:47, 14.22s/it] 67%|██████▋   | 2698/4000 [10:49:37<4:54:24, 13.57s/it] 67%|██████▋   | 2699/4000 [10:49:50<4:51:53, 13.46s/it] 68%|██████▊   | 2700/4000 [10:50:05<4:57:21, 13.72s/it]                                                         68%|██████▊   | 2700/4000 [10:50:05<4:57:21, 13.72s/it] 68%|██████▊   | 2701/4000 [10:50:18<4:55:29, 13.65s/it] 68%|██████▊   | 2702/4000 [10:50:31<4:52:35, 13.53s/it] 68%|██████▊   | 2703/4000 [10:50:46<4:57:02, 13.74s/it] 68%|██████▊   | 2704/4000 [10:50:59<4:56:26, 13.72s/it] 68%|██████▊   | 2705/4000 [10:51:11<4:44:32, 13.18s/it] 68%|██████▊   | 2706/4000 [10:51:27<4:59:24, 13.88s/it] 68%|██████▊   | 2707/4000 [10:51:41<5:03:57, 14.10s/it] 68%|██████▊   | 2708/4000 [10:51:55<4:57:18, 13.81s/it] 68%|██████▊   | 2709/4000 [10:52:09<5:01:58, 14.03s/it] 68%|██████▊   | 2710/4000 [10:52:23<4:59:43, 13.94s/it]                                                         68%|██████▊   | 2710/4000 [10:52:23<4:59:43, 13.94s/it] 68%|██████▊   | 2711/4000 [10:52:36<4:55:41, 13.76s/it] 68%|██████▊   | 2712/4000 [10:52:51<5:00:09, 13.98s/it] 68%|██████▊   | 2713/4000 [10:53:04<4:57:12, 13.86s/it] 68%|██████▊   | 2714/4000 [10:53:19<5:00:55, 14.04s/it] 68%|██████▊   | 2715/4000 [10:53:32<4:58:40, 13.95s/it] 68%|██████▊   | 2716/4000 [10:53:47<5:01:54, 14.11s/it] 68%|██████▊   | 2717/4000 [10:54:01<4:58:36, 13.96s/it] 68%|██████▊   | 2718/4000 [10:54:15<5:03:08, 14.19s/it] 68%|██████▊   | 2719/4000 [10:54:29<4:58:21, 13.97s/it] 68%|██████▊   | 2720/4000 [10:54:44<5:07:04, 14.39s/it]                                                         68%|██████▊   | 2720/4000 [10:54:44<5:07:04, 14.39s/it] 68%|██████▊   | 2721/4000 [10:54:57<4:54:40, 13.82s/it] 68%|██████▊   | 2722/4000 [10:55:12<5:07:16, 14.43s/it] 68%|██████▊   | 2723/4000 [10:55:25<4:54:30, 13.84s/it] 68%|██████▊   | 2724/4000 [10:55:41<5:07:23, 14.45s/it] 68%|██████▊   | 2725/4000 [10:55:53<4:51:59, 13.74s/it] 68%|██████▊   | 2726/4000 [10:56:09<5:05:43, 14.40s/it] 68%|██████▊   | 2727/4000 [10:56:21<4:53:48, 13.85s/it] 68%|██████▊   | 2728/4000 [10:56:37<5:02:59, 14.29s/it] 68%|██████▊   | 2729/4000 [10:56:50<4:54:04, 13.88s/it] 68%|██████▊   | 2730/4000 [10:57:05<5:04:18, 14.38s/it]                                                         68%|██████▊   | 2730/4000 [10:57:05<5:04:18, 14.38s/it] 68%|██████▊   | 2731/4000 [10:57:18<4:57:07, 14.05s/it] 68%|██████▊   | 2732/4000 [10:57:33<5:00:46, 14.23s/it] 68%|██████▊   | 2733/4000 [10:57:47<4:57:50, 14.10s/it] 68%|██████▊   | 2734/4000 [10:58:01<4:57:52, 14.12s/it] 68%|██████▊   | 2735/4000 [10:58:14<4:53:02, 13.90s/it] 68%|██████▊   | 2736/4000 [10:58:29<4:55:10, 14.01s/it] 68%|██████▊   | 2737/4000 [10:58:42<4:50:55, 13.82s/it] 68%|██████▊   | 2738/4000 [10:58:56<4:53:36, 13.96s/it] 68%|██████▊   | 2739/4000 [10:59:09<4:47:18, 13.67s/it] 68%|██████▊   | 2740/4000 [10:59:25<5:00:04, 14.29s/it]                                                         68%|██████▊   | 2740/4000 [10:59:25<5:00:04, 14.29s/it] 69%|██████▊   | 2741/4000 [10:59:37<4:45:12, 13.59s/it] 69%|██████▊   | 2742/4000 [10:59:50<4:43:25, 13.52s/it] 69%|██████▊   | 2743/4000 [11:00:05<4:52:50, 13.98s/it] 69%|██████▊   | 2744/4000 [11:00:19<4:49:52, 13.85s/it] 69%|██████▊   | 2745/4000 [11:00:34<4:54:02, 14.06s/it] 69%|██████▊   | 2746/4000 [11:00:47<4:51:10, 13.93s/it] 69%|██████▊   | 2747/4000 [11:01:02<4:55:41, 14.16s/it] 69%|██████▊   | 2748/4000 [11:01:17<5:03:20, 14.54s/it] 69%|██████▊   | 2749/4000 [11:01:31<4:56:46, 14.23s/it] 69%|██████▉   | 2750/4000 [11:01:43<4:43:43, 13.62s/it]                                                         69%|██████▉   | 2750/4000 [11:01:43<4:43:43, 13.62s/it] 69%|██████▉   | 2751/4000 [11:01:59<4:56:49, 14.26s/it] 69%|██████▉   | 2752/4000 [11:02:11<4:45:42, 13.74s/it] 69%|██████▉   | 2753/4000 [11:02:26<4:54:00, 14.15s/it] 69%|██████▉   | 2754/4000 [11:02:38<4:39:45, 13.47s/it] 69%|██████▉   | 2755/4000 [11:02:53<4:49:18, 13.94s/it] 69%|██████▉   | 2756/4000 [11:03:07<4:46:49, 13.83s/it] 69%|██████▉   | 2757/4000 [11:03:22<4:52:53, 14.14s/it] 69%|██████▉   | 2758/4000 [11:03:36<4:50:36, 14.04s/it] 69%|██████▉   | 2759/4000 [11:03:50<4:51:12, 14.08s/it] 69%|██████▉   | 2760/4000 [11:04:03<4:47:51, 13.93s/it]                                                         69%|██████▉   | 2760/4000 [11:04:03<4:47:51, 13.93s/it] 69%|██████▉   | 2761/4000 [11:04:16<4:40:38, 13.59s/it] 69%|██████▉   | 2762/4000 [11:04:32<4:52:35, 14.18s/it] 69%|██████▉   | 2763/4000 [11:04:46<4:54:18, 14.28s/it] 69%|██████▉   | 2764/4000 [11:05:00<4:48:55, 14.03s/it] 69%|██████▉   | 2765/4000 [11:05:13<4:46:27, 13.92s/it] 69%|██████▉   | 2766/4000 [11:05:28<4:49:36, 14.08s/it] 69%|██████▉   | 2767/4000 [11:05:41<4:44:57, 13.87s/it] 69%|██████▉   | 2768/4000 [11:05:56<4:50:11, 14.13s/it] 69%|██████▉   | 2769/4000 [11:06:09<4:46:59, 13.99s/it] 69%|██████▉   | 2770/4000 [11:06:24<4:49:20, 14.11s/it]                                                         69%|██████▉   | 2770/4000 [11:06:24<4:49:20, 14.11s/it] 69%|██████▉   | 2771/4000 [11:06:37<4:44:16, 13.88s/it] 69%|██████▉   | 2772/4000 [11:06:52<4:46:41, 14.01s/it] 69%|██████▉   | 2773/4000 [11:07:05<4:42:32, 13.82s/it] 69%|██████▉   | 2774/4000 [11:07:19<4:43:19, 13.87s/it] 69%|██████▉   | 2775/4000 [11:07:33<4:43:16, 13.87s/it] 69%|██████▉   | 2776/4000 [11:07:49<4:55:13, 14.47s/it] 69%|██████▉   | 2777/4000 [11:08:01<4:40:32, 13.76s/it] 69%|██████▉   | 2778/4000 [11:08:16<4:49:41, 14.22s/it] 69%|██████▉   | 2779/4000 [11:08:29<4:39:06, 13.72s/it] 70%|██████▉   | 2780/4000 [11:08:44<4:49:06, 14.22s/it]                                                         70%|██████▉   | 2780/4000 [11:08:44<4:49:06, 14.22s/it] 70%|██████▉   | 2781/4000 [11:08:57<4:39:39, 13.77s/it] 70%|██████▉   | 2782/4000 [11:09:12<4:50:09, 14.29s/it] 70%|██████▉   | 2783/4000 [11:09:25<4:39:39, 13.79s/it] 70%|██████▉   | 2784/4000 [11:09:41<4:52:43, 14.44s/it] 70%|██████▉   | 2785/4000 [11:09:54<4:47:52, 14.22s/it] 70%|██████▉   | 2786/4000 [11:10:09<4:48:52, 14.28s/it] 70%|██████▉   | 2787/4000 [11:10:23<4:45:17, 14.11s/it] 70%|██████▉   | 2788/4000 [11:10:37<4:47:52, 14.25s/it] 70%|██████▉   | 2789/4000 [11:10:51<4:43:34, 14.05s/it] 70%|██████▉   | 2790/4000 [11:11:06<4:48:09, 14.29s/it]                                                         70%|██████▉   | 2790/4000 [11:11:06<4:48:09, 14.29s/it] 70%|██████▉   | 2791/4000 [11:11:19<4:44:24, 14.11s/it] 70%|██████▉   | 2792/4000 [11:11:34<4:47:03, 14.26s/it] 70%|██████▉   | 2793/4000 [11:11:48<4:43:46, 14.11s/it] 70%|██████▉   | 2794/4000 [11:12:02<4:47:21, 14.30s/it] 70%|██████▉   | 2795/4000 [11:12:16<4:43:47, 14.13s/it] 70%|██████▉   | 2796/4000 [11:12:32<4:51:35, 14.53s/it] 70%|██████▉   | 2797/4000 [11:12:44<4:37:59, 13.86s/it] 70%|██████▉   | 2798/4000 [11:12:59<4:45:26, 14.25s/it] 70%|██████▉   | 2799/4000 [11:13:11<4:33:48, 13.68s/it] 70%|███████   | 2800/4000 [11:13:25<4:33:20, 13.67s/it]                                                         70%|███████   | 2800/4000 [11:13:25<4:33:20, 13.67s/it] 70%|███████   | 2801/4000 [11:13:39<4:36:46, 13.85s/it] 70%|███████   | 2802/4000 [11:13:53<4:33:13, 13.68s/it] 70%|███████   | 2803/4000 [11:14:07<4:39:34, 14.01s/it] 70%|███████   | 2804/4000 [11:14:21<4:34:39, 13.78s/it] 70%|███████   | 2805/4000 [11:14:36<4:46:06, 14.37s/it] 70%|███████   | 2806/4000 [11:14:49<4:34:34, 13.80s/it] 70%|███████   | 2807/4000 [11:15:03<4:33:41, 13.77s/it] 70%|███████   | 2808/4000 [11:15:17<4:38:19, 14.01s/it] 70%|███████   | 2809/4000 [11:15:31<4:37:04, 13.96s/it] 70%|███████   | 2810/4000 [11:15:43<4:25:20, 13.38s/it]                                                         70%|███████   | 2810/4000 [11:15:43<4:25:20, 13.38s/it] 70%|███████   | 2811/4000 [11:15:59<4:39:21, 14.10s/it] 70%|███████   | 2812/4000 [11:16:13<4:37:26, 14.01s/it] 70%|███████   | 2813/4000 [11:16:27<4:40:21, 14.17s/it] 70%|███████   | 2814/4000 [11:16:41<4:35:59, 13.96s/it] 70%|███████   | 2815/4000 [11:16:55<4:39:15, 14.14s/it] 70%|███████   | 2816/4000 [11:17:09<4:35:18, 13.95s/it] 70%|███████   | 2817/4000 [11:17:21<4:24:09, 13.40s/it] 70%|███████   | 2818/4000 [11:17:36<4:34:07, 13.92s/it] 70%|███████   | 2819/4000 [11:17:48<4:24:44, 13.45s/it] 70%|███████   | 2820/4000 [11:18:02<4:24:22, 13.44s/it]                                                         70%|███████   | 2820/4000 [11:18:02<4:24:22, 13.44s/it] 71%|███████   | 2821/4000 [11:18:18<4:39:10, 14.21s/it] 71%|███████   | 2822/4000 [11:18:30<4:26:49, 13.59s/it] 71%|███████   | 2823/4000 [11:18:46<4:39:31, 14.25s/it] 71%|███████   | 2824/4000 [11:18:58<4:29:32, 13.75s/it] 71%|███████   | 2825/4000 [11:19:14<4:40:14, 14.31s/it] 71%|███████   | 2826/4000 [11:19:26<4:30:18, 13.82s/it] 71%|███████   | 2827/4000 [11:19:42<4:41:38, 14.41s/it] 71%|███████   | 2828/4000 [11:19:55<4:30:41, 13.86s/it] 71%|███████   | 2829/4000 [11:20:11<4:41:32, 14.43s/it] 71%|███████   | 2830/4000 [11:20:23<4:30:27, 13.87s/it]                                                         71%|███████   | 2830/4000 [11:20:23<4:30:27, 13.87s/it] 71%|███████   | 2831/4000 [11:20:36<4:25:08, 13.61s/it] 71%|███████   | 2832/4000 [11:20:52<4:37:23, 14.25s/it] 71%|███████   | 2833/4000 [11:21:04<4:26:22, 13.70s/it] 71%|███████   | 2834/4000 [11:21:20<4:38:48, 14.35s/it] 71%|███████   | 2835/4000 [11:21:33<4:27:04, 13.76s/it] 71%|███████   | 2836/4000 [11:21:48<4:37:01, 14.28s/it] 71%|███████   | 2837/4000 [11:22:00<4:24:49, 13.66s/it] 71%|███████   | 2838/4000 [11:22:14<4:25:34, 13.71s/it] 71%|███████   | 2839/4000 [11:22:29<4:29:33, 13.93s/it] 71%|███████   | 2840/4000 [11:22:42<4:26:25, 13.78s/it]                                                         71%|███████   | 2840/4000 [11:22:42<4:26:25, 13.78s/it] 71%|███████   | 2841/4000 [11:22:58<4:37:49, 14.38s/it] 71%|███████   | 2842/4000 [11:23:11<4:28:46, 13.93s/it] 71%|███████   | 2843/4000 [11:23:24<4:24:52, 13.74s/it] 71%|███████   | 2844/4000 [11:23:38<4:28:17, 13.93s/it] 71%|███████   | 2845/4000 [11:23:51<4:23:20, 13.68s/it] 71%|███████   | 2846/4000 [11:24:06<4:27:15, 13.90s/it] 71%|███████   | 2847/4000 [11:24:19<4:25:31, 13.82s/it] 71%|███████   | 2848/4000 [11:24:34<4:28:16, 13.97s/it] 71%|███████   | 2849/4000 [11:24:47<4:23:28, 13.73s/it] 71%|███████▏  | 2850/4000 [11:25:03<4:38:03, 14.51s/it]                                                         71%|███████▏  | 2850/4000 [11:25:03<4:38:03, 14.51s/it] 71%|███████▏  | 2851/4000 [11:25:16<4:25:19, 13.86s/it] 71%|███████▏  | 2852/4000 [11:25:29<4:21:33, 13.67s/it] 71%|███████▏  | 2853/4000 [11:25:44<4:27:36, 14.00s/it] 71%|███████▏  | 2854/4000 [11:25:57<4:23:41, 13.81s/it] 71%|███████▏  | 2855/4000 [11:26:11<4:26:15, 13.95s/it] 71%|███████▏  | 2856/4000 [11:26:25<4:23:35, 13.83s/it] 71%|███████▏  | 2857/4000 [11:26:40<4:28:45, 14.11s/it] 71%|███████▏  | 2858/4000 [11:26:53<4:25:12, 13.93s/it] 71%|███████▏  | 2859/4000 [11:27:07<4:22:55, 13.83s/it] 72%|███████▏  | 2860/4000 [11:27:21<4:27:33, 14.08s/it]                                                         72%|███████▏  | 2860/4000 [11:27:21<4:27:33, 14.08s/it] 72%|███████▏  | 2861/4000 [11:27:35<4:22:48, 13.84s/it] 72%|███████▏  | 2862/4000 [11:27:49<4:26:48, 14.07s/it] 72%|███████▏  | 2863/4000 [11:28:05<4:38:19, 14.69s/it] 72%|███████▏  | 2864/4000 [11:28:17<4:23:39, 13.93s/it] 72%|███████▏  | 2865/4000 [11:28:31<4:22:52, 13.90s/it] 72%|███████▏  | 2866/4000 [11:28:46<4:28:08, 14.19s/it] 72%|███████▏  | 2867/4000 [11:29:02<4:35:57, 14.61s/it] 72%|███████▏  | 2868/4000 [11:29:15<4:28:00, 14.21s/it] 72%|███████▏  | 2869/4000 [11:29:27<4:14:16, 13.49s/it] 72%|███████▏  | 2870/4000 [11:29:42<4:23:45, 14.00s/it]                                                         72%|███████▏  | 2870/4000 [11:29:42<4:23:45, 14.00s/it] 72%|███████▏  | 2871/4000 [11:29:55<4:16:03, 13.61s/it] 72%|███████▏  | 2872/4000 [11:30:11<4:28:51, 14.30s/it] 72%|███████▏  | 2873/4000 [11:30:23<4:19:09, 13.80s/it] 72%|███████▏  | 2874/4000 [11:30:39<4:30:08, 14.39s/it] 72%|███████▏  | 2875/4000 [11:30:52<4:21:52, 13.97s/it] 72%|███████▏  | 2876/4000 [11:31:05<4:18:45, 13.81s/it] 72%|███████▏  | 2877/4000 [11:31:21<4:30:28, 14.45s/it] 72%|███████▏  | 2878/4000 [11:31:34<4:17:44, 13.78s/it] 72%|███████▏  | 2879/4000 [11:31:48<4:23:18, 14.09s/it] 72%|███████▏  | 2880/4000 [11:32:01<4:14:25, 13.63s/it]                                                         72%|███████▏  | 2880/4000 [11:32:01<4:14:25, 13.63s/it] 72%|███████▏  | 2881/4000 [11:32:17<4:24:57, 14.21s/it] 72%|███████▏  | 2882/4000 [11:32:29<4:14:15, 13.65s/it] 72%|███████▏  | 2883/4000 [11:32:45<4:26:17, 14.30s/it] 72%|███████▏  | 2884/4000 [11:32:57<4:13:37, 13.64s/it] 72%|███████▏  | 2885/4000 [11:33:10<4:10:46, 13.49s/it] 72%|███████▏  | 2886/4000 [11:33:26<4:22:12, 14.12s/it] 72%|███████▏  | 2887/4000 [11:33:38<4:11:29, 13.56s/it] 72%|███████▏  | 2888/4000 [11:33:53<4:20:09, 14.04s/it] 72%|███████▏  | 2889/4000 [11:34:06<4:12:07, 13.62s/it] 72%|███████▏  | 2890/4000 [11:34:22<4:26:46, 14.42s/it]                                                         72%|███████▏  | 2890/4000 [11:34:22<4:26:46, 14.42s/it] 72%|███████▏  | 2891/4000 [11:34:34<4:14:17, 13.76s/it] 72%|███████▏  | 2892/4000 [11:34:49<4:22:22, 14.21s/it] 72%|███████▏  | 2893/4000 [11:35:02<4:13:10, 13.72s/it] 72%|███████▏  | 2894/4000 [11:35:18<4:23:49, 14.31s/it] 72%|███████▏  | 2895/4000 [11:35:31<4:18:00, 14.01s/it] 72%|███████▏  | 2896/4000 [11:35:43<4:08:47, 13.52s/it] 72%|███████▏  | 2897/4000 [11:35:59<4:20:31, 14.17s/it] 72%|███████▏  | 2898/4000 [11:36:11<4:10:15, 13.63s/it] 72%|███████▏  | 2899/4000 [11:36:27<4:22:15, 14.29s/it] 72%|███████▎  | 2900/4000 [11:36:39<4:10:11, 13.65s/it]                                                         72%|███████▎  | 2900/4000 [11:36:39<4:10:11, 13.65s/it] 73%|███████▎  | 2901/4000 [11:36:55<4:20:52, 14.24s/it] 73%|███████▎  | 2902/4000 [11:37:07<4:10:31, 13.69s/it] 73%|███████▎  | 2903/4000 [11:37:21<4:08:01, 13.57s/it] 73%|███████▎  | 2904/4000 [11:37:36<4:19:19, 14.20s/it] 73%|███████▎  | 2905/4000 [11:37:48<4:06:48, 13.52s/it] 73%|███████▎  | 2906/4000 [11:38:02<4:05:50, 13.48s/it] 73%|███████▎  | 2907/4000 [11:38:17<4:13:08, 13.90s/it] 73%|███████▎  | 2908/4000 [11:38:30<4:11:10, 13.80s/it] 73%|███████▎  | 2909/4000 [11:38:44<4:13:15, 13.93s/it] 73%|███████▎  | 2910/4000 [11:38:58<4:11:11, 13.83s/it]                                                         73%|███████▎  | 2910/4000 [11:38:58<4:11:11, 13.83s/it] 73%|███████▎  | 2911/4000 [11:39:13<4:15:15, 14.06s/it] 73%|███████▎  | 2912/4000 [11:39:26<4:12:39, 13.93s/it] 73%|███████▎  | 2913/4000 [11:39:39<4:06:42, 13.62s/it] 73%|███████▎  | 2914/4000 [11:39:53<4:10:30, 13.84s/it] 73%|███████▎  | 2915/4000 [11:40:07<4:07:29, 13.69s/it] 73%|███████▎  | 2916/4000 [11:40:21<4:11:08, 13.90s/it] 73%|███████▎  | 2917/4000 [11:40:35<4:09:07, 13.80s/it] 73%|███████▎  | 2918/4000 [11:40:47<4:03:01, 13.48s/it] 73%|███████▎  | 2919/4000 [11:41:03<4:14:53, 14.15s/it] 73%|███████▎  | 2920/4000 [11:41:17<4:11:53, 13.99s/it]                                                         73%|███████▎  | 2920/4000 [11:41:17<4:11:53, 13.99s/it] 73%|███████▎  | 2921/4000 [11:41:32<4:15:47, 14.22s/it] 73%|███████▎  | 2922/4000 [11:41:47<4:23:17, 14.65s/it] 73%|███████▎  | 2923/4000 [11:42:00<4:12:48, 14.08s/it] 73%|███████▎  | 2924/4000 [11:42:16<4:21:08, 14.56s/it] 73%|███████▎  | 2925/4000 [11:42:28<4:09:42, 13.94s/it] 73%|███████▎  | 2926/4000 [11:42:44<4:18:35, 14.45s/it] 73%|███████▎  | 2927/4000 [11:42:55<4:02:55, 13.58s/it] 73%|███████▎  | 2928/4000 [11:43:09<4:02:33, 13.58s/it] 73%|███████▎  | 2929/4000 [11:43:23<4:06:44, 13.82s/it] 73%|███████▎  | 2930/4000 [11:43:37<4:05:23, 13.76s/it]                                                         73%|███████▎  | 2930/4000 [11:43:37<4:05:23, 13.76s/it] 73%|███████▎  | 2931/4000 [11:43:52<4:14:52, 14.31s/it] 73%|███████▎  | 2932/4000 [11:44:05<4:03:11, 13.66s/it] 73%|███████▎  | 2933/4000 [11:44:19<4:04:04, 13.72s/it] 73%|███████▎  | 2934/4000 [11:44:33<4:07:27, 13.93s/it] 73%|███████▎  | 2935/4000 [11:44:49<4:18:19, 14.55s/it] 73%|███████▎  | 2936/4000 [11:45:01<4:05:52, 13.87s/it] 73%|███████▎  | 2937/4000 [11:45:15<4:04:44, 13.81s/it] 73%|███████▎  | 2938/4000 [11:45:29<4:08:39, 14.05s/it] 73%|███████▎  | 2939/4000 [11:45:43<4:04:24, 13.82s/it] 74%|███████▎  | 2940/4000 [11:45:58<4:13:17, 14.34s/it]                                                         74%|███████▎  | 2940/4000 [11:45:58<4:13:17, 14.34s/it] 74%|███████▎  | 2941/4000 [11:46:11<4:03:01, 13.77s/it] 74%|███████▎  | 2942/4000 [11:46:24<4:01:00, 13.67s/it] 74%|███████▎  | 2943/4000 [11:46:39<4:06:10, 13.97s/it] 74%|███████▎  | 2944/4000 [11:46:53<4:04:44, 13.91s/it] 74%|███████▎  | 2945/4000 [11:47:07<4:05:15, 13.95s/it] 74%|███████▎  | 2946/4000 [11:47:20<4:04:13, 13.90s/it] 74%|███████▎  | 2947/4000 [11:47:34<4:01:09, 13.74s/it] 74%|███████▎  | 2948/4000 [11:47:48<4:05:44, 14.02s/it] 74%|███████▎  | 2949/4000 [11:48:01<3:59:59, 13.70s/it] 74%|███████▍  | 2950/4000 [11:48:14<3:52:18, 13.27s/it]                                                         74%|███████▍  | 2950/4000 [11:48:14<3:52:18, 13.27s/it] 74%|███████▍  | 2951/4000 [11:48:29<4:04:30, 13.99s/it] 74%|███████▍  | 2952/4000 [11:48:42<3:55:22, 13.48s/it] 74%|███████▍  | 2953/4000 [11:48:57<4:04:43, 14.02s/it] 74%|███████▍  | 2954/4000 [11:49:09<3:55:42, 13.52s/it] 74%|███████▍  | 2955/4000 [11:49:25<4:08:04, 14.24s/it] 74%|███████▍  | 2956/4000 [11:49:39<4:02:39, 13.95s/it] 74%|███████▍  | 2957/4000 [11:49:53<4:03:10, 13.99s/it] 74%|███████▍  | 2958/4000 [11:50:06<3:59:06, 13.77s/it] 74%|███████▍  | 2959/4000 [11:50:20<4:03:15, 14.02s/it] 74%|███████▍  | 2960/4000 [11:50:34<4:01:32, 13.94s/it]                                                         74%|███████▍  | 2960/4000 [11:50:34<4:01:32, 13.94s/it] 74%|███████▍  | 2961/4000 [11:50:49<4:03:58, 14.09s/it] 74%|███████▍  | 2962/4000 [11:51:02<4:01:33, 13.96s/it] 74%|███████▍  | 2963/4000 [11:51:16<4:00:36, 13.92s/it] 74%|███████▍  | 2964/4000 [11:51:30<4:00:06, 13.91s/it] 74%|███████▍  | 2965/4000 [11:51:45<4:03:15, 14.10s/it] 74%|███████▍  | 2966/4000 [11:51:58<4:00:28, 13.95s/it] 74%|███████▍  | 2967/4000 [11:52:14<4:09:31, 14.49s/it] 74%|███████▍  | 2968/4000 [11:52:26<3:57:45, 13.82s/it] 74%|███████▍  | 2969/4000 [11:52:42<4:05:43, 14.30s/it] 74%|███████▍  | 2970/4000 [11:52:54<3:56:25, 13.77s/it]                                                         74%|███████▍  | 2970/4000 [11:52:54<3:56:25, 13.77s/it] 74%|███████▍  | 2971/4000 [11:53:09<4:03:44, 14.21s/it] 74%|███████▍  | 2972/4000 [11:53:22<3:53:54, 13.65s/it] 74%|███████▍  | 2973/4000 [11:53:38<4:06:15, 14.39s/it] 74%|███████▍  | 2974/4000 [11:53:50<3:55:21, 13.76s/it] 74%|███████▍  | 2975/4000 [11:54:03<3:52:21, 13.60s/it] 74%|███████▍  | 2976/4000 [11:54:19<4:02:37, 14.22s/it] 74%|███████▍  | 2977/4000 [11:54:33<4:03:36, 14.29s/it] 74%|███████▍  | 2978/4000 [11:54:47<3:58:29, 14.00s/it] 74%|███████▍  | 2979/4000 [11:55:01<4:00:07, 14.11s/it] 74%|███████▍  | 2980/4000 [11:55:14<3:54:01, 13.77s/it]                                                         74%|███████▍  | 2980/4000 [11:55:14<3:54:01, 13.77s/it] 75%|███████▍  | 2981/4000 [11:55:26<3:44:23, 13.21s/it] 75%|███████▍  | 2982/4000 [11:55:41<3:55:19, 13.87s/it] 75%|███████▍  | 2983/4000 [11:55:55<3:53:53, 13.80s/it] 75%|███████▍  | 2984/4000 [11:56:07<3:46:24, 13.37s/it] 75%|███████▍  | 2985/4000 [11:56:24<4:00:14, 14.20s/it] 75%|███████▍  | 2986/4000 [11:56:38<4:02:21, 14.34s/it] 75%|███████▍  | 2987/4000 [11:56:52<3:57:10, 14.05s/it] 75%|███████▍  | 2988/4000 [11:57:04<3:46:12, 13.41s/it] 75%|███████▍  | 2989/4000 [11:57:19<3:55:52, 14.00s/it] 75%|███████▍  | 2990/4000 [11:57:32<3:48:33, 13.58s/it]                                                         75%|███████▍  | 2990/4000 [11:57:32<3:48:33, 13.58s/it] 75%|███████▍  | 2991/4000 [11:57:47<3:58:23, 14.18s/it] 75%|███████▍  | 2992/4000 [11:58:01<3:56:28, 14.08s/it] 75%|███████▍  | 2993/4000 [11:58:13<3:47:46, 13.57s/it] 75%|███████▍  | 2994/4000 [11:58:29<3:57:28, 14.16s/it] 75%|███████▍  | 2995/4000 [11:58:41<3:46:32, 13.52s/it] 75%|███████▍  | 2996/4000 [11:58:57<3:58:28, 14.25s/it] 75%|███████▍  | 2997/4000 [11:59:09<3:49:01, 13.70s/it] 75%|███████▍  | 2998/4000 [11:59:25<3:58:34, 14.29s/it] 75%|███████▍  | 2999/4000 [11:59:37<3:49:17, 13.74s/it] 75%|███████▌  | 3000/4000 [11:59:53<3:58:42, 14.32s/it]                                                         75%|███████▌  | 3000/4000 [11:59:53<3:58:42, 14.32s/it]{'eval_loss': '0.1611', 'eval_runtime': '389.5', 'eval_samples_per_second': '1.291', 'eval_steps_per_second': '1.291', 'epoch': '3.982'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2829:{'loss': '0.7046', 'grad_norm': '0.3948', 'learning_rate': '5.7e-05', 'epoch': '4.156'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2836:{'loss': '0.7703', 'grad_norm': '0.3558', 'learning_rate': '5.195e-05', 'epoch': '4.268'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2838:{'loss': '0.6388', 'grad_norm': '0.2888', 'learning_rate': '5.054e-05', 'epoch': '4.3'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2843:{'loss': '0.834', 'grad_norm': '0.4072', 'learning_rate': '4.706e-05', 'epoch': '4.379'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2855:{'loss': '0.7284', 'grad_norm': '0.4704', 'learning_rate': '3.908e-05', 'epoch': '4.571'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:2935: 14%|█▍        | 70/503 [00:53<05:05,  1.42it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3035: 34%|███▍      | 170/503 [02:13<03:47,  1.46it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3056: 38%|███▊      | 191/503 [02:28<03:03,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3121: 51%|█████     | 256/503 [03:20<02:25,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3135: 54%|█████▎    | 270/503 [03:31<04:26,  1.14s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3210: 70%|██████▉   | 350/503 [04:32<02:10,  1.17it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3211: 70%|██████▉   | 351/503 [04:32<01:43,  1.46it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3212: 70%|██████▉   | 352/503 [04:33<01:25,  1.77it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3213: 70%|███████   | 353/503 [04:35<02:42,  1.08s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3214: 70%|███████   | 354/503 [04:35<02:05,  1.18it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3230: 74%|███████▎  | 370/503 [04:48<02:30,  1.13s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3330: 93%|█████████▎| 470/503 [06:03<00:35,  1.09s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3370: 75%|███████▌  | 3001/4000 [12:06:41<36:42:07, 132.26s/it] 75%|███████▌  | 3002/4000 [12:06:52<26:39:10, 96.14s/it]  75%|███████▌  | 3003/4000 [12:07:06<19:44:16, 71.27s/it] 75%|███████▌  | 3004/4000 [12:07:21<15:02:30, 54.37s/it] 75%|███████▌  | 3005/4000 [12:07:33<11:33:00, 41.79s/it] 75%|███████▌  | 3006/4000 [12:07:49<9:23:43, 34.03s/it]  75%|███████▌  | 3007/4000 [12:08:01<7:33:38, 27.41s/it] 75%|███████▌  | 3008/4000 [12:08:16<6:33:58, 23.83s/it] 75%|███████▌  | 3009/4000 [12:08:29<5:37:32, 20.44s/it] 75%|███████▌  | 3010/4000 [12:08:45<5:13:40, 19.01s/it]                                                         75%|███████▌  | 3010/4000 [12:08:45<5:13:40, 19.01s/it] 75%|███████▌  | 3011/4000 [12:08:58<4:45:06, 17.30s/it] 75%|███████▌  | 3012/4000 [12:09:10<4:19:13, 15.74s/it] 75%|███████▌  | 3013/4000 [12:09:26<4:20:37, 15.84s/it] 75%|███████▌  | 3014/4000 [12:09:40<4:12:44, 15.38s/it] 75%|███████▌  | 3015/4000 [12:09:54<4:04:45, 14.91s/it] 75%|███████▌  | 3016/4000 [12:10:08<4:01:37, 14.73s/it] 75%|███████▌  | 3017/4000 [12:10:22<3:56:59, 14.47s/it] 75%|███████▌  | 3018/4000 [12:10:37<3:59:54, 14.66s/it] 75%|███████▌  | 3019/4000 [12:10:51<3:53:27, 14.28s/it] 76%|███████▌  | 3020/4000 [12:11:03<3:44:18, 13.73s/it]                                                         76%|███████▌  | 3020/4000 [12:11:03<3:44:18, 13.73s/it] 76%|███████▌  | 3021/4000 [12:11:19<3:55:06, 14.41s/it] 76%|███████▌  | 3022/4000 [12:11:35<4:01:58, 14.85s/it] 76%|███████▌  | 3023/4000 [12:11:48<3:50:27, 14.15s/it] 76%|███████▌  | 3024/4000 [12:12:04<3:59:08, 14.70s/it] 76%|███████▌  | 3025/4000 [12:12:16<3:47:25, 14.00s/it] 76%|███████▌  | 3026/4000 [12:12:32<3:56:03, 14.54s/it] 76%|███████▌  | 3027/4000 [12:12:44<3:43:54, 13.81s/it] 76%|███████▌  | 3028/4000 [12:13:00<3:53:22, 14.41s/it] 76%|███████▌  | 3029/4000 [12:13:12<3:40:46, 13.64s/it] 76%|███████▌  | 3030/4000 [12:13:27<3:51:15, 14.30s/it]                                                         76%|███████▌  | 3030/4000 [12:13:27<3:51:15, 14.30s/it] 76%|███████▌  | 3031/4000 [12:13:40<3:40:53, 13.68s/it] 76%|███████▌  | 3032/4000 [12:13:55<3:48:48, 14.18s/it] 76%|███████▌  | 3033/4000 [12:14:09<3:46:27, 14.05s/it] 76%|███████▌  | 3034/4000 [12:14:24<3:50:05, 14.29s/it] 76%|███████▌  | 3035/4000 [12:14:37<3:46:46, 14.10s/it] 76%|███████▌  | 3036/4000 [12:14:52<3:48:09, 14.20s/it] 76%|███████▌  | 3037/4000 [12:15:05<3:43:53, 13.95s/it] 76%|███████▌  | 3038/4000 [12:15:19<3:45:12, 14.05s/it] 76%|███████▌  | 3039/4000 [12:15:33<3:43:31, 13.96s/it] 76%|███████▌  | 3040/4000 [12:15:47<3:45:25, 14.09s/it]                                                         76%|███████▌  | 3040/4000 [12:15:47<3:45:25, 14.09s/it] 76%|███████▌  | 3041/4000 [12:16:01<3:41:31, 13.86s/it] 76%|███████▌  | 3042/4000 [12:16:16<3:49:14, 14.36s/it] 76%|███████▌  | 3043/4000 [12:16:29<3:40:56, 13.85s/it] 76%|███████▌  | 3044/4000 [12:16:42<3:38:52, 13.74s/it] 76%|███████▌  | 3045/4000 [12:16:57<3:40:21, 13.84s/it] 76%|███████▌  | 3046/4000 [12:17:12<3:49:14, 14.42s/it] 76%|███████▌  | 3047/4000 [12:17:25<3:39:42, 13.83s/it] 76%|███████▌  | 3048/4000 [12:17:39<3:39:34, 13.84s/it] 76%|███████▌  | 3049/4000 [12:17:53<3:41:01, 13.94s/it] 76%|███████▋  | 3050/4000 [12:18:06<3:39:26, 13.86s/it]                                                         76%|███████▋  | 3050/4000 [12:18:06<3:39:26, 13.86s/it] 76%|███████▋  | 3051/4000 [12:18:22<3:47:11, 14.36s/it] 76%|███████▋  | 3052/4000 [12:18:34<3:35:46, 13.66s/it] 76%|███████▋  | 3053/4000 [12:18:49<3:43:02, 14.13s/it] 76%|███████▋  | 3054/4000 [12:19:02<3:34:38, 13.61s/it] 76%|███████▋  | 3055/4000 [12:19:17<3:41:16, 14.05s/it] 76%|███████▋  | 3056/4000 [12:19:29<3:32:09, 13.49s/it] 76%|███████▋  | 3057/4000 [12:19:42<3:30:12, 13.37s/it] 76%|███████▋  | 3058/4000 [12:19:56<3:34:40, 13.67s/it] 76%|███████▋  | 3059/4000 [12:20:10<3:32:32, 13.55s/it] 76%|███████▋  | 3060/4000 [12:20:25<3:42:54, 14.23s/it]                                                         76%|███████▋  | 3060/4000 [12:20:25<3:42:54, 14.23s/it] 77%|███████▋  | 3061/4000 [12:20:38<3:33:41, 13.65s/it] 77%|███████▋  | 3062/4000 [12:20:53<3:40:52, 14.13s/it] 77%|███████▋  | 3063/4000 [12:21:06<3:33:52, 13.70s/it] 77%|███████▋  | 3064/4000 [12:21:19<3:33:21, 13.68s/it] 77%|███████▋  | 3065/4000 [12:21:34<3:37:01, 13.93s/it] 77%|███████▋  | 3066/4000 [12:21:47<3:35:19, 13.83s/it] 77%|███████▋  | 3067/4000 [12:22:02<3:38:50, 14.07s/it] 77%|███████▋  | 3068/4000 [12:22:18<3:45:09, 14.50s/it] 77%|███████▋  | 3069/4000 [12:22:31<3:40:24, 14.20s/it] 77%|███████▋  | 3070/4000 [12:22:43<3:29:01, 13.49s/it]                                                         77%|███████▋  | 3070/4000 [12:22:43<3:29:01, 13.49s/it] 77%|███████▋  | 3071/4000 [12:22:59<3:40:07, 14.22s/it] 77%|███████▋  | 3072/4000 [12:23:11<3:30:15, 13.59s/it] 77%|███████▋  | 3073/4000 [12:23:25<3:30:31, 13.63s/it] 77%|███████▋  | 3074/4000 [12:23:39<3:35:25, 13.96s/it] 77%|███████▋  | 3075/4000 [12:23:52<3:30:44, 13.67s/it] 77%|███████▋  | 3076/4000 [12:24:07<3:33:38, 13.87s/it] 77%|███████▋  | 3077/4000 [12:24:20<3:31:30, 13.75s/it] 77%|███████▋  | 3078/4000 [12:24:36<3:39:40, 14.30s/it] 77%|███████▋  | 3079/4000 [12:24:48<3:29:27, 13.64s/it] 77%|███████▋  | 3080/4000 [12:25:01<3:26:59, 13.50s/it]                                                         77%|███████▋  | 3080/4000 [12:25:01<3:26:59, 13.50s/it] 77%|███████▋  | 3081/4000 [12:25:15<3:29:41, 13.69s/it] 77%|███████▋  | 3082/4000 [12:25:29<3:28:54, 13.65s/it] 77%|███████▋  | 3083/4000 [12:25:41<3:21:51, 13.21s/it] 77%|███████▋  | 3084/4000 [12:25:57<3:32:29, 13.92s/it] 77%|███████▋  | 3085/4000 [12:26:10<3:31:09, 13.85s/it] 77%|███████▋  | 3086/4000 [12:26:25<3:33:33, 14.02s/it] 77%|███████▋  | 3087/4000 [12:26:38<3:30:43, 13.85s/it] 77%|███████▋  | 3088/4000 [12:26:53<3:33:54, 14.07s/it] 77%|███████▋  | 3089/4000 [12:27:06<3:30:31, 13.87s/it] 77%|███████▋  | 3090/4000 [12:27:20<3:31:12, 13.93s/it]                                                         77%|███████▋  | 3090/4000 [12:27:20<3:31:12, 13.93s/it] 77%|███████▋  | 3091/4000 [12:27:34<3:30:19, 13.88s/it] 77%|███████▋  | 3092/4000 [12:27:48<3:32:39, 14.05s/it] 77%|███████▋  | 3093/4000 [12:28:02<3:29:55, 13.89s/it] 77%|███████▋  | 3094/4000 [12:28:15<3:28:31, 13.81s/it] 77%|███████▋  | 3095/4000 [12:28:30<3:31:31, 14.02s/it] 77%|███████▋  | 3096/4000 [12:28:44<3:29:07, 13.88s/it] 77%|███████▋  | 3097/4000 [12:28:59<3:34:05, 14.23s/it] 77%|███████▋  | 3098/4000 [12:29:12<3:28:47, 13.89s/it] 77%|███████▋  | 3099/4000 [12:29:24<3:21:34, 13.42s/it] 78%|███████▊  | 3100/4000 [12:29:40<3:31:11, 14.08s/it]                                                         78%|███████▊  | 3100/4000 [12:29:40<3:31:11, 14.08s/it] 78%|███████▊  | 3101/4000 [12:29:52<3:23:13, 13.56s/it] 78%|███████▊  | 3102/4000 [12:30:06<3:23:12, 13.58s/it] 78%|███████▊  | 3103/4000 [12:30:21<3:31:15, 14.13s/it] 78%|███████▊  | 3104/4000 [12:30:34<3:24:01, 13.66s/it] 78%|███████▊  | 3105/4000 [12:30:49<3:31:22, 14.17s/it] 78%|███████▊  | 3106/4000 [12:31:02<3:24:43, 13.74s/it] 78%|███████▊  | 3107/4000 [12:31:15<3:24:45, 13.76s/it] 78%|███████▊  | 3108/4000 [12:31:30<3:26:07, 13.87s/it] 78%|███████▊  | 3109/4000 [12:31:43<3:23:41, 13.72s/it] 78%|███████▊  | 3110/4000 [12:31:57<3:26:04, 13.89s/it]                                                         78%|███████▊  | 3110/4000 [12:31:57<3:26:04, 13.89s/it] 78%|███████▊  | 3111/4000 [12:32:11<3:23:46, 13.75s/it] 78%|███████▊  | 3112/4000 [12:32:26<3:32:22, 14.35s/it] 78%|███████▊  | 3113/4000 [12:32:39<3:23:46, 13.78s/it] 78%|███████▊  | 3114/4000 [12:32:52<3:22:35, 13.72s/it] 78%|███████▊  | 3115/4000 [12:33:06<3:23:45, 13.81s/it] 78%|███████▊  | 3116/4000 [12:33:20<3:20:11, 13.59s/it] 78%|███████▊  | 3117/4000 [12:33:34<3:23:21, 13.82s/it] 78%|███████▊  | 3118/4000 [12:33:47<3:22:03, 13.75s/it] 78%|███████▊  | 3119/4000 [12:34:01<3:21:01, 13.69s/it] 78%|███████▊  | 3120/4000 [12:34:15<3:23:23, 13.87s/it]                                                         78%|███████▊  | 3120/4000 [12:34:15<3:23:23, 13.87s/it] 78%|███████▊  | 3121/4000 [12:34:29<3:20:18, 13.67s/it] 78%|███████▊  | 3122/4000 [12:34:43<3:24:20, 13.96s/it] 78%|███████▊  | 3123/4000 [12:34:57<3:24:48, 14.01s/it] 78%|███████▊  | 3124/4000 [12:35:11<3:24:18, 13.99s/it] 78%|███████▊  | 3125/4000 [12:35:25<3:21:07, 13.79s/it] 78%|███████▊  | 3126/4000 [12:35:37<3:15:29, 13.42s/it] 78%|███████▊  | 3127/4000 [12:35:53<3:26:08, 14.17s/it] 78%|███████▊  | 3128/4000 [12:36:07<3:24:20, 14.06s/it] 78%|███████▊  | 3129/4000 [12:36:19<3:17:01, 13.57s/it] 78%|███████▊  | 3130/4000 [12:36:35<3:27:16, 14.30s/it]                                                         78%|███████▊  | 3130/4000 [12:36:35<3:27:16, 14.30s/it] 78%|███████▊  | 3131/4000 [12:36:47<3:18:00, 13.67s/it] 78%|███████▊  | 3132/4000 [12:37:03<3:25:15, 14.19s/it] 78%|███████▊  | 3133/4000 [12:37:15<3:16:24, 13.59s/it] 78%|███████▊  | 3134/4000 [12:37:31<3:25:14, 14.22s/it] 78%|███████▊  | 3135/4000 [12:37:43<3:17:14, 13.68s/it] 78%|███████▊  | 3136/4000 [12:37:59<3:24:03, 14.17s/it] 78%|███████▊  | 3137/4000 [12:38:12<3:20:24, 13.93s/it] 78%|███████▊  | 3138/4000 [12:38:24<3:12:35, 13.41s/it] 78%|███████▊  | 3139/4000 [12:38:40<3:23:11, 14.16s/it] 78%|███████▊  | 3140/4000 [12:38:45<2:42:35, 11.34s/it]                                                         78%|███████▊  | 3140/4000 [12:38:45<2:42:35, 11.34s/it] 79%|███████▊  | 3141/4000 [12:38:58<2:52:03, 12.02s/it] 79%|███████▊  | 3142/4000 [12:39:12<2:59:27, 12.55s/it] 79%|███████▊  | 3143/4000 [12:39:27<3:08:27, 13.19s/it] 79%|███████▊  | 3144/4000 [12:39:40<3:09:29, 13.28s/it] 79%|███████▊  | 3145/4000 [12:39:54<3:12:37, 13.52s/it] 79%|███████▊  | 3146/4000 [12:40:08<3:12:23, 13.52s/it] 79%|███████▊  | 3147/4000 [12:40:23<3:17:28, 13.89s/it] 79%|███████▊  | 3148/4000 [12:40:36<3:16:24, 13.83s/it] 79%|███████▊  | 3149/4000 [12:40:51<3:19:27, 14.06s/it] 79%|███████▉  | 3150/4000 [12:41:05<3:17:05, 13.91s/it]                                                         79%|███████▉  | 3150/4000 [12:41:05<3:17:05, 13.91s/it] 79%|███████▉  | 3151/4000 [12:41:19<3:18:31, 14.03s/it] 79%|███████▉  | 3152/4000 [12:41:32<3:15:31, 13.83s/it] 79%|███████▉  | 3153/4000 [12:41:48<3:23:09, 14.39s/it] 79%|███████▉  | 3154/4000 [12:42:00<3:13:02, 13.69s/it] 79%|███████▉  | 3155/4000 [12:42:15<3:19:53, 14.19s/it] 79%|███████▉  | 3156/4000 [12:42:28<3:12:19, 13.67s/it] 79%|███████▉  | 3157/4000 [12:42:41<3:11:19, 13.62s/it] 79%|███████▉  | 3158/4000 [12:42:56<3:15:14, 13.91s/it] 79%|███████▉  | 3159/4000 [12:43:09<3:11:51, 13.69s/it] 79%|███████▉  | 3160/4000 [12:43:24<3:17:39, 14.12s/it]                                                         79%|███████▉  | 3160/4000 [12:43:24<3:17:39, 14.12s/it] 79%|███████▉  | 3161/4000 [12:43:36<3:09:11, 13.53s/it] 79%|███████▉  | 3162/4000 [12:43:52<3:18:41, 14.23s/it] 79%|███████▉  | 3163/4000 [12:44:04<3:10:09, 13.63s/it] 79%|███████▉  | 3164/4000 [12:44:18<3:09:22, 13.59s/it] 79%|███████▉  | 3165/4000 [12:44:33<3:13:54, 13.93s/it] 79%|███████▉  | 3166/4000 [12:44:47<3:13:28, 13.92s/it] 79%|███████▉  | 3167/4000 [12:45:01<3:14:21, 14.00s/it] 79%|███████▉  | 3168/4000 [12:45:14<3:11:55, 13.84s/it] 79%|███████▉  | 3169/4000 [12:45:30<3:20:08, 14.45s/it] 79%|███████▉  | 3170/4000 [12:45:42<3:10:23, 13.76s/it]                                                         79%|███████▉  | 3170/4000 [12:45:42<3:10:23, 13.76s/it] 79%|███████▉  | 3171/4000 [12:45:56<3:08:55, 13.67s/it] 79%|███████▉  | 3172/4000 [12:46:10<3:12:13, 13.93s/it] 79%|███████▉  | 3173/4000 [12:46:24<3:09:31, 13.75s/it] 79%|███████▉  | 3174/4000 [12:46:36<3:03:36, 13.34s/it] 79%|███████▉  | 3175/4000 [12:46:52<3:13:04, 14.04s/it] 79%|███████▉  | 3176/4000 [12:47:04<3:05:23, 13.50s/it] 79%|███████▉  | 3177/4000 [12:47:19<3:11:56, 13.99s/it] 79%|███████▉  | 3178/4000 [12:47:33<3:10:14, 13.89s/it] 79%|███████▉  | 3179/4000 [12:47:47<3:13:00, 14.11s/it] 80%|███████▉  | 3180/4000 [12:48:01<3:10:45, 13.96s/it]                                                         80%|███████▉  | 3180/4000 [12:48:01<3:10:45, 13.96s/it] 80%|███████▉  | 3181/4000 [12:48:13<3:02:15, 13.35s/it] 80%|███████▉  | 3182/4000 [12:48:29<3:12:02, 14.09s/it] 80%|███████▉  | 3183/4000 [12:48:41<3:05:17, 13.61s/it] 80%|███████▉  | 3184/4000 [12:48:56<3:09:37, 13.94s/it] 80%|███████▉  | 3185/4000 [12:49:08<3:02:33, 13.44s/it] 80%|███████▉  | 3186/4000 [12:49:23<3:09:54, 14.00s/it] 80%|███████▉  | 3187/4000 [12:49:36<3:05:41, 13.70s/it] 80%|███████▉  | 3188/4000 [12:49:49<3:00:57, 13.37s/it] 80%|███████▉  | 3189/4000 [12:50:04<3:09:26, 14.01s/it] 80%|███████▉  | 3190/4000 [12:50:19<3:12:01, 14.22s/it]                                                         80%|███████▉  | 3190/4000 [12:50:19<3:12:01, 14.22s/it] 80%|███████▉  | 3191/4000 [12:50:33<3:09:56, 14.09s/it] 80%|███████▉  | 3192/4000 [12:50:47<3:11:08, 14.19s/it] 80%|███████▉  | 3193/4000 [12:51:01<3:08:11, 13.99s/it] 80%|███████▉  | 3194/4000 [12:51:16<3:10:34, 14.19s/it] 80%|███████▉  | 3195/4000 [12:51:29<3:08:29, 14.05s/it] 80%|███████▉  | 3196/4000 [12:51:44<3:11:51, 14.32s/it] 80%|███████▉  | 3197/4000 [12:51:58<3:08:12, 14.06s/it] 80%|███████▉  | 3198/4000 [12:52:11<3:06:13, 13.93s/it] 80%|███████▉  | 3199/4000 [12:52:26<3:07:15, 14.03s/it] 80%|████████  | 3200/4000 [12:52:41<3:14:26, 14.58s/it]                                                         80%|████████  | 3200/4000 [12:52:41<3:14:26, 14.58s/it] 80%|████████  | 3201/4000 [12:52:54<3:05:49, 13.95s/it] 80%|████████  | 3202/4000 [12:53:10<3:12:38, 14.48s/it] 80%|████████  | 3203/4000 [12:53:22<3:03:01, 13.78s/it] 80%|████████  | 3204/4000 [12:53:37<3:07:50, 14.16s/it] 80%|████████  | 3205/4000 [12:53:50<3:01:51, 13.73s/it] 80%|████████  | 3206/4000 [12:54:03<3:00:24, 13.63s/it] 80%|████████  | 3207/4000 [12:54:19<3:08:27, 14.26s/it] 80%|████████  | 3208/4000 [12:54:31<3:01:15, 13.73s/it] 80%|████████  | 3209/4000 [12:54:47<3:08:53, 14.33s/it] 80%|████████  | 3210/4000 [12:54:59<3:01:05, 13.75s/it]                                                         80%|████████  | 3210/4000 [12:54:59<3:01:05, 13.75s/it] 80%|████████  | 3211/4000 [12:55:13<3:00:19, 13.71s/it] 80%|████████  | 3212/4000 [12:55:28<3:03:44, 13.99s/it] 80%|████████  | 3213/4000 [12:55:42<3:03:30, 13.99s/it] 80%|████████  | 3214/4000 [12:55:56<3:04:05, 14.05s/it] 80%|████████  | 3215/4000 [12:56:09<3:01:13, 13.85s/it] 80%|████████  | 3216/4000 [12:56:25<3:08:03, 14.39s/it] 80%|████████  | 3217/4000 [12:56:37<2:58:24, 13.67s/it] 80%|████████  | 3218/4000 [12:56:53<3:07:01, 14.35s/it] 80%|████████  | 3219/4000 [12:57:05<2:58:24, 13.71s/it] 80%|████████  | 3220/4000 [12:57:18<2:56:52, 13.61s/it]                                                         80%|████████  | 3220/4000 [12:57:18<2:56:52, 13.61s/it] 81%|████████  | 3221/4000 [12:57:33<3:00:18, 13.89s/it] 81%|████████  | 3222/4000 [12:57:47<2:59:20, 13.83s/it] 81%|████████  | 3223/4000 [12:58:00<2:57:54, 13.74s/it] 81%|████████  | 3224/4000 [12:58:14<3:00:02, 13.92s/it] 81%|████████  | 3225/4000 [12:58:28<2:57:50, 13.77s/it] 81%|████████  | 3226/4000 [12:58:42<3:00:41, 14.01s/it] 81%|████████  | 3227/4000 [12:58:56<2:58:52, 13.88s/it] 81%|████████  | 3228/4000 [12:59:10<3:00:56, 14.06s/it] 81%|████████  | 3229/4000 [12:59:24<2:59:47, 13.99s/it] 81%|████████  | 3230/4000 [12:59:39<3:01:37, 14.15s/it]                                                         81%|████████  | 3230/4000 [12:59:39<3:01:37, 14.15s/it] 81%|████████  | 3231/4000 [12:59:53<2:59:58, 14.04s/it] 81%|████████  | 3232/4000 [13:00:07<3:00:54, 14.13s/it] 81%|████████  | 3233/4000 [13:00:21<2:58:42, 13.98s/it] 81%|████████  | 3234/4000 [13:00:36<3:04:34, 14.46s/it] 81%|████████  | 3235/4000 [13:00:48<2:55:46, 13.79s/it] 81%|████████  | 3236/4000 [13:01:04<3:03:18, 14.40s/it] 81%|████████  | 3237/4000 [13:01:17<2:55:41, 13.82s/it] 81%|████████  | 3238/4000 [13:01:32<3:01:41, 14.31s/it] 81%|████████  | 3239/4000 [13:01:45<2:54:12, 13.74s/it] 81%|████████  | 3240/4000 [13:01:58<2:51:57, 13.58s/it]                                                         81%|████████  | 3240/4000 [13:01:58<2:51:57, 13.58s/it] 81%|████████  | 3241/4000 [13:02:12<2:53:51, 13.74s/it] 81%|████████  | 3242/4000 [13:02:26<2:53:39, 13.75s/it] 81%|████████  | 3243/4000 [13:02:39<2:51:45, 13.61s/it] 81%|████████  | 3244/4000 [13:02:54<2:55:29, 13.93s/it] 81%|████████  | 3245/4000 [13:03:09<3:01:24, 14.42s/it] 81%|████████  | 3246/4000 [13:03:22<2:53:56, 13.84s/it] 81%|████████  | 3247/4000 [13:03:35<2:51:42, 13.68s/it] 81%|████████  | 3248/4000 [13:03:49<2:53:38, 13.85s/it] 81%|████████  | 3249/4000 [13:04:03<2:52:05, 13.75s/it] 81%|████████▏ | 3250/4000 [13:04:17<2:52:22, 13.79s/it]                                                         81%|████████▏ | 3250/4000 [13:04:17<2:52:22, 13.79s/it] 81%|████████▏ | 3251/4000 [13:04:30<2:49:38, 13.59s/it] 81%|████████▏ | 3252/4000 [13:04:46<2:57:56, 14.27s/it] 81%|████████▏ | 3253/4000 [13:04:58<2:50:32, 13.70s/it] 81%|████████▏ | 3254/4000 [13:05:11<2:47:35, 13.48s/it] 81%|████████▏ | 3255/4000 [13:05:26<2:51:58, 13.85s/it] 81%|████████▏ | 3256/4000 [13:05:39<2:50:24, 13.74s/it] 81%|████████▏ | 3257/4000 [13:05:54<2:53:52, 14.04s/it] 81%|████████▏ | 3258/4000 [13:06:07<2:50:34, 13.79s/it] 81%|████████▏ | 3259/4000 [13:06:21<2:52:38, 13.98s/it] 82%|████████▏ | 3260/4000 [13:06:37<2:57:55, 14.43s/it]                                                         82%|████████▏ | 3260/4000 [13:06:37<2:57:55, 14.43s/it] 82%|████████▏ | 3261/4000 [13:06:51<2:55:29, 14.25s/it] 82%|████████▏ | 3262/4000 [13:07:03<2:49:18, 13.76s/it] 82%|████████▏ | 3263/4000 [13:07:19<2:56:01, 14.33s/it] 82%|████████▏ | 3264/4000 [13:07:31<2:47:44, 13.67s/it] 82%|████████▏ | 3265/4000 [13:07:47<2:54:31, 14.25s/it] 82%|████████▏ | 3266/4000 [13:07:59<2:48:16, 13.75s/it] 82%|████████▏ | 3267/4000 [13:08:15<2:53:51, 14.23s/it] 82%|████████▏ | 3268/4000 [13:08:27<2:45:39, 13.58s/it] 82%|████████▏ | 3269/4000 [13:08:43<2:55:03, 14.37s/it] 82%|████████▏ | 3270/4000 [13:08:56<2:48:47, 13.87s/it]                                                         82%|████████▏ | 3270/4000 [13:08:56<2:48:47, 13.87s/it] 82%|████████▏ | 3271/4000 [13:09:09<2:45:58, 13.66s/it] 82%|████████▏ | 3272/4000 [13:09:25<2:53:01, 14.26s/it] 82%|████████▏ | 3273/4000 [13:09:39<2:52:57, 14.27s/it] 82%|████████▏ | 3274/4000 [13:09:53<2:50:46, 14.11s/it] 82%|████████▏ | 3275/4000 [13:10:05<2:44:07, 13.58s/it] 82%|████████▏ | 3276/4000 [13:10:21<2:52:24, 14.29s/it] 82%|████████▏ | 3277/4000 [13:10:33<2:45:09, 13.71s/it] 82%|████████▏ | 3278/4000 [13:10:49<2:52:30, 14.34s/it] 82%|████████▏ | 3279/4000 [13:11:01<2:45:08, 13.74s/it] 82%|████████▏ | 3280/4000 [13:11:17<2:50:33, 14.21s/it]                                                         82%|████████▏ | 3280/4000 [13:11:17<2:50:33, 14.21s/it] 82%|████████▏ | 3281/4000 [13:11:30<2:46:06, 13.86s/it] 82%|████████▏ | 3282/4000 [13:11:42<2:39:01, 13.29s/it] 82%|████████▏ | 3283/4000 [13:11:57<2:46:29, 13.93s/it] 82%|████████▏ | 3284/4000 [13:12:09<2:40:18, 13.43s/it] 82%|████████▏ | 3285/4000 [13:12:25<2:48:56, 14.18s/it] 82%|████████▏ | 3286/4000 [13:12:38<2:42:49, 13.68s/it] 82%|████████▏ | 3287/4000 [13:12:52<2:43:03, 13.72s/it] 82%|████████▏ | 3288/4000 [13:13:06<2:45:41, 13.96s/it] 82%|████████▏ | 3289/4000 [13:13:20<2:44:52, 13.91s/it] 82%|████████▏ | 3290/4000 [13:13:35<2:49:33, 14.33s/it]                                                         82%|████████▏ | 3290/4000 [13:13:35<2:49:33, 14.33s/it] 82%|████████▏ | 3291/4000 [13:13:50<2:49:28, 14.34s/it] 82%|████████▏ | 3292/4000 [13:14:03<2:46:50, 14.14s/it] 82%|████████▏ | 3293/4000 [13:14:17<2:45:33, 14.05s/it] 82%|████████▏ | 3294/4000 [13:14:31<2:44:44, 14.00s/it] 82%|████████▏ | 3295/4000 [13:14:46<2:47:11, 14.23s/it] 82%|████████▏ | 3296/4000 [13:14:59<2:44:52, 14.05s/it] 82%|████████▏ | 3297/4000 [13:15:14<2:46:06, 14.18s/it] 82%|████████▏ | 3298/4000 [13:15:28<2:44:19, 14.04s/it] 82%|████████▏ | 3299/4000 [13:15:42<2:46:00, 14.21s/it] 82%|████████▎ | 3300/4000 [13:15:56<2:43:58, 14.05s/it]                                                         82%|████████▎ | 3300/4000 [13:15:56<2:43:58, 14.05s/it] 83%|████████▎ | 3301/4000 [13:16:11<2:48:04, 14.43s/it] 83%|████████▎ | 3302/4000 [13:16:24<2:41:18, 13.87s/it] 83%|████████▎ | 3303/4000 [13:16:39<2:46:47, 14.36s/it] 83%|████████▎ | 3304/4000 [13:16:52<2:39:27, 13.75s/it] 83%|████████▎ | 3305/4000 [13:17:07<2:45:25, 14.28s/it] 83%|████████▎ | 3306/4000 [13:17:19<2:37:42, 13.64s/it] 83%|████████▎ | 3307/4000 [13:17:33<2:37:07, 13.60s/it] 83%|████████▎ | 3308/4000 [13:17:47<2:40:37, 13.93s/it] 83%|████████▎ | 3309/4000 [13:18:01<2:40:20, 13.92s/it] 83%|████████▎ | 3310/4000 [13:18:14<2:36:57, 13.65s/it]                                                         83%|████████▎ | 3310/4000 [13:18:14<2:36:57, 13.65s/it] 83%|████████▎ | 3311/4000 [13:18:29<2:40:42, 14.00s/it] 83%|████████▎ | 3312/4000 [13:18:45<2:46:16, 14.50s/it] 83%|████████▎ | 3313/4000 [13:18:58<2:42:50, 14.22s/it] 83%|████████▎ | 3314/4000 [13:19:10<2:32:38, 13.35s/it] 83%|████████▎ | 3315/4000 [13:19:26<2:41:33, 14.15s/it] 83%|████████▎ | 3316/4000 [13:19:40<2:40:53, 14.11s/it] 83%|████████▎ | 3317/4000 [13:19:53<2:38:44, 13.95s/it] 83%|████████▎ | 3318/4000 [13:20:08<2:41:19, 14.19s/it] 83%|████████▎ | 3319/4000 [13:20:22<2:38:45, 13.99s/it] 83%|████████▎ | 3320/4000 [13:20:35<2:37:29, 13.90s/it]                                                         83%|████████▎ | 3320/4000 [13:20:35<2:37:29, 13.90s/it] 83%|████████▎ | 3321/4000 [13:20:50<2:39:51, 14.13s/it] 83%|████████▎ | 3322/4000 [13:21:04<2:38:20, 14.01s/it] 83%|████████▎ | 3323/4000 [13:21:18<2:39:00, 14.09s/it] 83%|████████▎ | 3324/4000 [13:21:31<2:36:29, 13.89s/it] 83%|████████▎ | 3325/4000 [13:21:46<2:38:05, 14.05s/it] 83%|████████▎ | 3326/4000 [13:21:59<2:35:13, 13.82s/it] 83%|████████▎ | 3327/4000 [13:22:14<2:37:08, 14.01s/it] 83%|████████▎ | 3328/4000 [13:22:27<2:35:12, 13.86s/it] 83%|████████▎ | 3329/4000 [13:22:43<2:40:15, 14.33s/it] 83%|████████▎ | 3330/4000 [13:22:55<2:34:12, 13.81s/it]                                                         83%|████████▎ | 3330/4000 [13:22:55<2:34:12, 13.81s/it] 83%|████████▎ | 3331/4000 [13:23:09<2:33:04, 13.73s/it] 83%|████████▎ | 3332/4000 [13:23:23<2:34:37, 13.89s/it] 83%|████████▎ | 3333/4000 [13:23:37<2:34:14, 13.88s/it] 83%|████████▎ | 3334/4000 [13:23:51<2:36:28, 14.10s/it] 83%|████████▎ | 3335/4000 [13:24:05<2:35:13, 14.00s/it] 83%|████████▎ | 3336/4000 [13:24:19<2:35:46, 14.08s/it] 83%|████████▎ | 3337/4000 [13:24:33<2:33:42, 13.91s/it] 83%|████████▎ | 3338/4000 [13:24:47<2:32:45, 13.85s/it] 83%|████████▎ | 3339/4000 [13:25:01<2:33:58, 13.98s/it] 84%|████████▎ | 3340/4000 [13:25:17<2:39:35, 14.51s/it]                                                         84%|████████▎ | 3340/4000 [13:25:17<2:39:35, 14.51s/it] 84%|████████▎ | 3341/4000 [13:25:29<2:30:52, 13.74s/it] 84%|████████▎ | 3342/4000 [13:25:44<2:35:42, 14.20s/it] 84%|████████▎ | 3343/4000 [13:25:57<2:30:35, 13.75s/it] 84%|████████▎ | 3344/4000 [13:26:10<2:30:51, 13.80s/it] 84%|████████▎ | 3345/4000 [13:26:25<2:31:42, 13.90s/it] 84%|████████▎ | 3346/4000 [13:26:38<2:31:12, 13.87s/it] 84%|████████▎ | 3347/4000 [13:26:53<2:33:19, 14.09s/it] 84%|████████▎ | 3348/4000 [13:27:07<2:31:16, 13.92s/it] 84%|████████▎ | 3349/4000 [13:27:20<2:29:08, 13.75s/it] 84%|████████▍ | 3350/4000 [13:27:34<2:31:12, 13.96s/it]                                                         84%|████████▍ | 3350/4000 [13:27:34<2:31:12, 13.96s/it] 84%|████████▍ | 3351/4000 [13:27:48<2:30:04, 13.87s/it] 84%|████████▍ | 3352/4000 [13:28:03<2:32:32, 14.12s/it] 84%|████████▍ | 3353/4000 [13:28:16<2:30:13, 13.93s/it] 84%|████████▍ | 3354/4000 [13:28:31<2:31:51, 14.10s/it] 84%|████████▍ | 3355/4000 [13:28:44<2:29:33, 13.91s/it] 84%|████████▍ | 3356/4000 [13:28:58<2:30:11, 13.99s/it] 84%|████████▍ | 3357/4000 [13:29:12<2:27:28, 13.76s/it] 84%|████████▍ | 3358/4000 [13:29:27<2:31:17, 14.14s/it] 84%|████████▍ | 3359/4000 [13:29:39<2:24:48, 13.56s/it] 84%|████████▍ | 3360/4000 [13:29:53<2:25:10, 13.61s/it]                                                         84%|████████▍ | 3360/4000 [13:29:53<2:25:10, 13.61s/it] 84%|████████▍ | 3361/4000 [13:30:07<2:27:28, 13.85s/it] 84%|████████▍ | 3362/4000 [13:30:20<2:26:10, 13.75s/it] 84%|████████▍ | 3363/4000 [13:30:33<2:21:35, 13.34s/it] 84%|████████▍ | 3364/4000 [13:30:49<2:28:54, 14.05s/it] 84%|████████▍ | 3365/4000 [13:31:03<2:29:59, 14.17s/it] 84%|████████▍ | 3366/4000 [13:31:17<2:28:28, 14.05s/it] 84%|████████▍ | 3367/4000 [13:31:30<2:27:07, 13.95s/it] 84%|████████▍ | 3368/4000 [13:31:45<2:28:25, 14.09s/it] 84%|████████▍ | 3369/4000 [13:31:59<2:27:05, 13.99s/it] 84%|████████▍ | 3370/4000 [13:32:13<2:28:24, 14.13s/it]                                                         84%|████████▍ | 3370/4000 [13:32:13<2:28:24, 14.13s/it] 84%|████████▍ | 3371/4000 [13:32:27<2:27:06, 14.03s/it] 84%|████████▍ | 3372/4000 [13:32:39<2:21:04, 13.48s/it] 84%|████████▍ | 3373/4000 [13:32:55<2:28:34, 14.22s/it] 84%|████████▍ | 3374/4000 [13:33:08<2:23:04, 13.71s/it] 84%|████████▍ | 3375/4000 [13:33:23<2:27:05, 14.12s/it] 84%|████████▍ | 3376/4000 [13:33:37<2:26:27, 14.08s/it] 84%|████████▍ | 3377/4000 [13:33:52<2:28:49, 14.33s/it] 84%|████████▍ | 3378/4000 [13:34:05<2:25:35, 14.04s/it] 84%|████████▍ | 3379/4000 [13:34:19<2:26:45, 14.18s/it] 84%|████████▍ | 3380/4000 [13:34:33<2:24:56, 14.03s/it]                                                         84%|████████▍ | 3380/4000 [13:34:33<2:24:56, 14.03s/it] 85%|████████▍ | 3381/4000 [13:34:47<2:23:49, 13.94s/it] 85%|████████▍ | 3382/4000 [13:35:03<2:29:05, 14.48s/it] 85%|████████▍ | 3383/4000 [13:35:15<2:22:40, 13.87s/it] 85%|████████▍ | 3384/4000 [13:35:28<2:20:20, 13.67s/it] 85%|████████▍ | 3385/4000 [13:35:43<2:22:04, 13.86s/it] 85%|████████▍ | 3386/4000 [13:35:56<2:21:22, 13.81s/it] 85%|████████▍ | 3387/4000 [13:36:12<2:27:06, 14.40s/it] 85%|████████▍ | 3388/4000 [13:36:24<2:19:45, 13.70s/it] 85%|████████▍ | 3389/4000 [13:36:40<2:25:44, 14.31s/it] 85%|████████▍ | 3390/4000 [13:36:52<2:18:25, 13.62s/it]                                                         85%|████████▍ | 3390/4000 [13:36:52<2:18:25, 13.62s/it] 85%|████████▍ | 3391/4000 [13:37:05<2:17:18, 13.53s/it] 85%|████████▍ | 3392/4000 [13:37:20<2:20:10, 13.83s/it] 85%|████████▍ | 3393/4000 [13:37:33<2:19:17, 13.77s/it] 85%|████████▍ | 3394/4000 [13:37:47<2:20:18, 13.89s/it] 85%|████████▍ | 3395/4000 [13:38:01<2:19:16, 13.81s/it] 85%|████████▍ | 3396/4000 [13:38:17<2:25:29, 14.45s/it] 85%|████████▍ | 3397/4000 [13:38:29<2:17:37, 13.69s/it] 85%|████████▍ | 3398/4000 [13:38:42<2:16:49, 13.64s/it] 85%|████████▍ | 3399/4000 [13:38:57<2:18:25, 13.82s/it] 85%|████████▌ | 3400/4000 [13:39:12<2:23:58, 14.40s/it]                                                         85%|████████▌ | 3400/4000 [13:39:12<2:23:58, 14.40s/it] 85%|████████▌ | 3401/4000 [13:39:25<2:17:53, 13.81s/it] 85%|████████▌ | 3402/4000 [13:39:40<2:22:46, 14.32s/it] 85%|████████▌ | 3403/4000 [13:39:53<2:16:38, 13.73s/it] 85%|████████▌ | 3404/4000 [13:40:08<2:20:50, 14.18s/it] 85%|████████▌ | 3405/4000 [13:40:21<2:18:00, 13.92s/it] 85%|████████▌ | 3406/4000 [13:40:36<2:19:47, 14.12s/it] 85%|████████▌ | 3407/4000 [13:40:50<2:18:04, 13.97s/it] 85%|████████▌ | 3408/4000 [13:41:04<2:19:56, 14.18s/it] 85%|████████▌ | 3409/4000 [13:41:18<2:18:27, 14.06s/it] 85%|████████▌ | 3410/4000 [13:41:32<2:18:47, 14.11s/it]                                                         85%|████████▌ | 3410/4000 [13:41:32<2:18:47, 14.11s/it] 85%|████████▌ | 3411/4000 [13:41:45<2:16:07, 13.87s/it] 85%|████████▌ | 3412/4000 [13:42:00<2:17:14, 14.00s/it] 85%|████████▌ | 3413/4000 [13:42:13<2:14:43, 13.77s/it] 85%|████████▌ | 3414/4000 [13:42:27<2:13:52, 13.71s/it] 85%|████████▌ | 3415/4000 [13:42:41<2:15:59, 13.95s/it] 85%|████████▌ | 3416/4000 [13:42:55<2:15:17, 13.90s/it] 85%|████████▌ | 3417/4000 [13:43:07<2:10:00, 13.38s/it] 85%|████████▌ | 3418/4000 [13:43:23<2:16:08, 14.04s/it] 85%|████████▌ | 3419/4000 [13:43:35<2:10:13, 13.45s/it] 86%|████████▌ | 3420/4000 [13:43:50<2:15:21, 14.00s/it]                                                         86%|████████▌ | 3420/4000 [13:43:50<2:15:21, 14.00s/it] 86%|████████▌ | 3421/4000 [13:44:02<2:10:26, 13.52s/it] 86%|████████▌ | 3422/4000 [13:44:16<2:09:50, 13.48s/it] 86%|████████▌ | 3423/4000 [13:44:31<2:15:24, 14.08s/it] 86%|████████▌ | 3424/4000 [13:44:43<2:09:29, 13.49s/it] 86%|████████▌ | 3425/4000 [13:44:59<2:15:19, 14.12s/it] 86%|████████▌ | 3426/4000 [13:45:12<2:10:31, 13.64s/it] 86%|████████▌ | 3427/4000 [13:45:27<2:16:30, 14.29s/it] 86%|████████▌ | 3428/4000 [13:45:40<2:10:46, 13.72s/it] 86%|████████▌ | 3429/4000 [13:45:56<2:16:44, 14.37s/it] 86%|████████▌ | 3430/4000 [13:46:08<2:09:35, 13.64s/it]                                                         86%|████████▌ | 3430/4000 [13:46:08<2:09:35, 13.64s/it] 86%|████████▌ | 3431/4000 [13:46:21<2:09:55, 13.70s/it] 86%|████████▌ | 3432/4000 [13:46:37<2:15:34, 14.32s/it] 86%|████████▌ | 3433/4000 [13:46:49<2:09:31, 13.71s/it] 86%|████████▌ | 3434/4000 [13:47:06<2:16:19, 14.45s/it] 86%|████████▌ | 3435/4000 [13:47:18<2:09:18, 13.73s/it] 86%|████████▌ | 3436/4000 [13:47:33<2:14:58, 14.36s/it] 86%|████████▌ | 3437/4000 [13:47:45<2:08:01, 13.64s/it] 86%|████████▌ | 3438/4000 [13:47:59<2:07:45, 13.64s/it] 86%|████████▌ | 3439/4000 [13:48:14<2:10:33, 13.96s/it] 86%|████████▌ | 3440/4000 [13:48:27<2:09:14, 13.85s/it]                                                         86%|████████▌ | 3440/4000 [13:48:27<2:09:14, 13.85s/it] 86%|████████▌ | 3441/4000 [13:48:43<2:12:42, 14.24s/it] 86%|████████▌ | 3442/4000 [13:48:54<2:05:17, 13.47s/it] 86%|████████▌ | 3443/4000 [13:49:10<2:11:27, 14.16s/it] 86%|████████▌ | 3444/4000 [13:49:22<2:05:31, 13.55s/it] 86%|████████▌ | 3445/4000 [13:49:36<2:05:38, 13.58s/it] 86%|████████▌ | 3446/4000 [13:49:50<2:06:52, 13.74s/it] 86%|████████▌ | 3447/4000 [13:50:03<2:05:40, 13.64s/it] 86%|████████▌ | 3448/4000 [13:50:18<2:07:25, 13.85s/it] 86%|████████▌ | 3449/4000 [13:50:33<2:11:58, 14.37s/it] 86%|████████▋ | 3450/4000 [13:50:47<2:10:32, 14.24s/it]                                                         86%|████████▋ | 3450/4000 [13:50:47<2:10:32, 14.24s/it] 86%|████████▋ | 3451/4000 [13:51:02<2:11:09, 14.33s/it] 86%|████████▋ | 3452/4000 [13:51:15<2:09:24, 14.17s/it] 86%|████████▋ | 3453/4000 [13:51:28<2:03:40, 13.57s/it] 86%|████████▋ | 3454/4000 [13:51:44<2:09:45, 14.26s/it] 86%|████████▋ | 3455/4000 [13:51:56<2:04:05, 13.66s/it] 86%|████████▋ | 3456/4000 [13:52:11<2:08:56, 14.22s/it] 86%|████████▋ | 3457/4000 [13:52:23<2:01:53, 13.47s/it] 86%|████████▋ | 3458/4000 [13:52:39<2:07:15, 14.09s/it] 86%|████████▋ | 3459/4000 [13:52:52<2:05:04, 13.87s/it] 86%|████████▋ | 3460/4000 [13:53:06<2:06:18, 14.03s/it]                                                         86%|████████▋ | 3460/4000 [13:53:06<2:06:18, 14.03s/it] 87%|████████▋ | 3461/4000 [13:53:20<2:05:20, 13.95s/it] 87%|████████▋ | 3462/4000 [13:53:34<2:06:06, 14.06s/it] 87%|████████▋ | 3463/4000 [13:53:48<2:05:15, 13.99s/it] 87%|████████▋ | 3464/4000 [13:54:00<1:59:13, 13.35s/it] 87%|████████▋ | 3465/4000 [13:54:16<2:06:06, 14.14s/it] 87%|████████▋ | 3466/4000 [13:54:28<1:59:34, 13.44s/it] 87%|████████▋ | 3467/4000 [13:54:44<2:05:56, 14.18s/it] 87%|████████▋ | 3468/4000 [13:54:56<2:00:27, 13.59s/it] 87%|████████▋ | 3469/4000 [13:55:11<2:04:58, 14.12s/it] 87%|████████▋ | 3470/4000 [13:55:25<2:02:10, 13.83s/it]                                                         87%|████████▋ | 3470/4000 [13:55:25<2:02:10, 13.83s/it] 87%|████████▋ | 3471/4000 [13:55:39<2:02:54, 13.94s/it] 87%|████████▋ | 3472/4000 [13:55:52<2:01:55, 13.86s/it] 87%|████████▋ | 3473/4000 [13:56:07<2:03:17, 14.04s/it] 87%|████████▋ | 3474/4000 [13:56:20<2:01:40, 13.88s/it] 87%|████████▋ | 3475/4000 [13:56:32<1:56:42, 13.34s/it] 87%|████████▋ | 3476/4000 [13:56:48<2:03:18, 14.12s/it] 87%|████████▋ | 3477/4000 [13:57:01<1:58:22, 13.58s/it] 87%|████████▋ | 3478/4000 [13:57:14<1:58:09, 13.58s/it] 87%|████████▋ | 3479/4000 [13:57:30<2:03:44, 14.25s/it] 87%|████████▋ | 3480/4000 [13:57:42<1:58:08, 13.63s/it]                                                         87%|████████▋ | 3480/4000 [13:57:42<1:58:08, 13.63s/it] 87%|████████▋ | 3481/4000 [13:57:58<2:03:46, 14.31s/it] 87%|████████▋ | 3482/4000 [13:58:11<1:58:53, 13.77s/it] 87%|████████▋ | 3483/4000 [13:58:26<2:02:47, 14.25s/it] 87%|████████▋ | 3484/4000 [13:58:38<1:57:42, 13.69s/it] 87%|████████▋ | 3485/4000 [13:58:52<1:56:37, 13.59s/it] 87%|████████▋ | 3486/4000 [13:59:06<1:58:42, 13.86s/it] 87%|████████▋ | 3487/4000 [13:59:20<1:58:06, 13.81s/it] 87%|████████▋ | 3488/4000 [13:59:35<2:01:58, 14.29s/it] 87%|████████▋ | 3489/4000 [13:59:47<1:56:08, 13.64s/it] 87%|████████▋ | 3490/4000 [14:00:03<2:01:55, 14.34s/it]                                                         87%|████████▋ | 3490/4000 [14:00:03<2:01:55, 14.34s/it] 87%|████████▋ | 3491/4000 [14:00:15<1:54:58, 13.55s/it] 87%|████████▋ | 3492/4000 [14:00:29<1:54:34, 13.53s/it] 87%|████████▋ | 3493/4000 [14:00:43<1:56:09, 13.75s/it] 87%|████████▋ | 3494/4000 [14:00:59<2:01:42, 14.43s/it] 87%|████████▋ | 3495/4000 [14:01:12<1:57:22, 13.94s/it] 87%|████████▋ | 3496/4000 [14:01:25<1:56:06, 13.82s/it] 87%|████████▋ | 3497/4000 [14:01:41<2:00:21, 14.36s/it] 87%|████████▋ | 3498/4000 [14:01:53<1:54:56, 13.74s/it] 87%|████████▋ | 3499/4000 [14:02:08<1:58:41, 14.21s/it] 88%|████████▊ | 3500/4000 [14:02:21<1:53:59, 13.68s/it]                                                         88%|████████▊ | 3500/4000 [14:02:21<1:53:59, 13.68s/it]{'eval_loss': '0.1711', 'eval_runtime': '388.8', 'eval_samples_per_second': '1.294', 'eval_steps_per_second': '1.294', 'epoch': '4.778'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3377:{'loss': '0.6718', 'grad_norm': '0.3219', 'learning_rate': '2.709e-05', 'epoch': '4.889'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3382:{'loss': '0.716', 'grad_norm': '0.3703', 'learning_rate': '2.438e-05', 'epoch': '4.969'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3383:{'loss': '0.7096', 'grad_norm': '0.4437', 'learning_rate': '2.385e-05', 'epoch': '4.985'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3385:{'loss': '0.6322', 'grad_norm': '0.3736', 'learning_rate': '2.281e-05', 'epoch': '5.016'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3386:{'loss': '0.6469', 'grad_norm': '0.2833', 'learning_rate': '2.23e-05', 'epoch': '5.032'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3387:{'loss': '0.623', 'grad_norm': '0.3179', 'learning_rate': '2.18e-05', 'epoch': '5.048'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3388:{'loss': '0.5517', 'grad_norm': '0.3366', 'learning_rate': '2.129e-05', 'epoch': '5.064'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3389:{'loss': '0.5878', 'grad_norm': '0.3429', 'learning_rate': '2.08e-05', 'epoch': '5.08'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3390:{'loss': '0.6419', 'grad_norm': '0.3818', 'learning_rate': '2.03e-05', 'epoch': '5.096'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3397:{'loss': '0.6163', 'grad_norm': '0.3317', 'learning_rate': '1.701e-05', 'epoch': '5.207'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3403:{'loss': '0.7037', 'grad_norm': '0.3912', 'learning_rate': '1.44e-05', 'epoch': '5.303'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3411:{'loss': '0.5709', 'grad_norm': '0.3016', 'learning_rate': '1.123e-05', 'epoch': '5.43'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3414:{'loss': '0.6707', 'grad_norm': '0.4228', 'learning_rate': '1.014e-05', 'epoch': '5.478'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3471: 11%|█         | 53/503 [00:41<04:25,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3488: 14%|█▍        | 70/503 [00:56<07:29,  1.04s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3499: 16%|█▌        | 81/503 [01:03<04:07,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3576: 31%|███▏      | 158/503 [02:03<03:22,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3588: 34%|███▍      | 170/503 [02:13<03:11,  1.74it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3644: 46%|████▌     | 229/503 [03:00<02:40,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3685: 54%|█████▎    | 270/503 [03:32<02:31,  1.54it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3727: 62%|██████▏   | 312/503 [04:03<01:52,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3765: 70%|██████▉   | 350/503 [04:32<01:02,  2.43it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3766: 70%|██████▉   | 351/503 [04:34<02:33,  1.01s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3767: 70%|██████▉   | 352/503 [04:35<02:00,  1.25it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3768: 70%|███████   | 353/503 [04:35<01:36,  1.56it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3769: 70%|███████   | 354/503 [04:35<01:21,  1.84it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3785: 74%|███████▎  | 370/503 [04:49<01:18,  1.69it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3819: 80%|████████  | 404/503 [05:13<00:55,  1.77it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3885: 93%|█████████▎| 470/503 [06:04<00:18,  1.76it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3925: 88%|████████▊ | 3501/4000 [14:09:06<18:09:48, 131.04s/it] 88%|████████▊ | 3502/4000 [14:09:21<13:20:09, 96.40s/it]  88%|████████▊ | 3503/4000 [14:09:33<9:48:22, 71.03s/it]  88%|████████▊ | 3504/4000 [14:09:47<7:23:59, 53.71s/it] 88%|████████▊ | 3505/4000 [14:10:01<5:45:13, 41.85s/it] 88%|████████▊ | 3506/4000 [14:10:14<4:34:08, 33.30s/it] 88%|████████▊ | 3507/4000 [14:10:30<3:50:16, 28.02s/it] 88%|████████▊ | 3508/4000 [14:10:41<3:09:45, 23.14s/it] 88%|████████▊ | 3509/4000 [14:10:54<2:43:53, 20.03s/it] 88%|████████▊ | 3510/4000 [14:11:09<2:29:54, 18.36s/it]                                                         88%|████████▊ | 3510/4000 [14:11:09<2:29:54, 18.36s/it] 88%|████████▊ | 3511/4000 [14:11:23<2:18:32, 17.00s/it] 88%|████████▊ | 3512/4000 [14:11:37<2:11:09, 16.13s/it] 88%|████████▊ | 3513/4000 [14:11:50<2:04:37, 15.35s/it] 88%|████████▊ | 3514/4000 [14:12:04<2:00:37, 14.89s/it] 88%|████████▊ | 3515/4000 [14:12:18<1:57:36, 14.55s/it] 88%|████████▊ | 3516/4000 [14:12:34<2:00:26, 14.93s/it] 88%|████████▊ | 3517/4000 [14:12:46<1:53:39, 14.12s/it] 88%|████████▊ | 3518/4000 [14:13:01<1:56:24, 14.49s/it] 88%|████████▊ | 3519/4000 [14:13:13<1:50:27, 13.78s/it] 88%|████████▊ | 3520/4000 [14:13:27<1:50:39, 13.83s/it]                                                         88%|████████▊ | 3520/4000 [14:13:27<1:50:39, 13.83s/it] 88%|████████▊ | 3521/4000 [14:13:42<1:51:32, 13.97s/it] 88%|████████▊ | 3522/4000 [14:13:55<1:50:25, 13.86s/it] 88%|████████▊ | 3523/4000 [14:14:07<1:45:26, 13.26s/it] 88%|████████▊ | 3524/4000 [14:14:23<1:52:37, 14.20s/it] 88%|████████▊ | 3525/4000 [14:14:38<1:54:32, 14.47s/it] 88%|████████▊ | 3526/4000 [14:14:51<1:49:36, 13.87s/it] 88%|████████▊ | 3527/4000 [14:15:07<1:53:55, 14.45s/it] 88%|████████▊ | 3528/4000 [14:15:19<1:48:48, 13.83s/it] 88%|████████▊ | 3529/4000 [14:15:33<1:48:15, 13.79s/it] 88%|████████▊ | 3530/4000 [14:15:47<1:49:07, 13.93s/it]                                                         88%|████████▊ | 3530/4000 [14:15:47<1:49:07, 13.93s/it] 88%|████████▊ | 3531/4000 [14:16:00<1:47:19, 13.73s/it] 88%|████████▊ | 3532/4000 [14:16:15<1:48:17, 13.88s/it] 88%|████████▊ | 3533/4000 [14:16:28<1:47:14, 13.78s/it] 88%|████████▊ | 3534/4000 [14:16:43<1:48:25, 13.96s/it] 88%|████████▊ | 3535/4000 [14:16:56<1:47:03, 13.82s/it] 88%|████████▊ | 3536/4000 [14:17:12<1:52:01, 14.49s/it] 88%|████████▊ | 3537/4000 [14:17:24<1:46:48, 13.84s/it] 88%|████████▊ | 3538/4000 [14:17:38<1:45:53, 13.75s/it] 88%|████████▊ | 3539/4000 [14:17:53<1:47:34, 14.00s/it] 88%|████████▊ | 3540/4000 [14:18:06<1:45:39, 13.78s/it]                                                         88%|████████▊ | 3540/4000 [14:18:06<1:45:39, 13.78s/it] 89%|████████▊ | 3541/4000 [14:18:21<1:47:39, 14.07s/it] 89%|████████▊ | 3542/4000 [14:18:34<1:46:20, 13.93s/it] 89%|████████▊ | 3543/4000 [14:18:49<1:47:18, 14.09s/it] 89%|████████▊ | 3544/4000 [14:19:02<1:45:42, 13.91s/it] 89%|████████▊ | 3545/4000 [14:19:16<1:44:27, 13.77s/it] 89%|████████▊ | 3546/4000 [14:19:30<1:45:49, 13.99s/it] 89%|████████▊ | 3547/4000 [14:19:43<1:43:20, 13.69s/it] 89%|████████▊ | 3548/4000 [14:19:57<1:44:08, 13.82s/it] 89%|████████▊ | 3549/4000 [14:20:11<1:44:09, 13.86s/it] 89%|████████▉ | 3550/4000 [14:20:26<1:45:36, 14.08s/it]                                                         89%|████████▉ | 3550/4000 [14:20:26<1:45:36, 14.08s/it] 89%|████████▉ | 3551/4000 [14:20:39<1:44:15, 13.93s/it] 89%|████████▉ | 3552/4000 [14:20:53<1:44:23, 13.98s/it] 89%|████████▉ | 3553/4000 [14:21:07<1:43:24, 13.88s/it] 89%|████████▉ | 3554/4000 [14:21:23<1:46:48, 14.37s/it] 89%|████████▉ | 3555/4000 [14:21:35<1:41:58, 13.75s/it] 89%|████████▉ | 3556/4000 [14:21:50<1:45:44, 14.29s/it] 89%|████████▉ | 3557/4000 [14:22:03<1:41:17, 13.72s/it] 89%|████████▉ | 3558/4000 [14:22:19<1:46:05, 14.40s/it] 89%|████████▉ | 3559/4000 [14:22:31<1:41:49, 13.85s/it] 89%|████████▉ | 3560/4000 [14:22:47<1:45:01, 14.32s/it]                                                         89%|████████▉ | 3560/4000 [14:22:47<1:45:01, 14.32s/it] 89%|████████▉ | 3561/4000 [14:22:59<1:40:12, 13.70s/it] 89%|████████▉ | 3562/4000 [14:23:12<1:39:25, 13.62s/it] 89%|████████▉ | 3563/4000 [14:23:27<1:40:32, 13.80s/it] 89%|████████▉ | 3564/4000 [14:23:43<1:44:48, 14.42s/it] 89%|████████▉ | 3565/4000 [14:23:56<1:42:55, 14.20s/it] 89%|████████▉ | 3566/4000 [14:24:10<1:42:22, 14.15s/it] 89%|████████▉ | 3567/4000 [14:24:24<1:41:14, 14.03s/it] 89%|████████▉ | 3568/4000 [14:24:36<1:36:12, 13.36s/it] 89%|████████▉ | 3569/4000 [14:24:52<1:41:10, 14.08s/it] 89%|████████▉ | 3570/4000 [14:25:04<1:36:36, 13.48s/it]                                                         89%|████████▉ | 3570/4000 [14:25:04<1:36:36, 13.48s/it] 89%|████████▉ | 3571/4000 [14:25:19<1:41:09, 14.15s/it] 89%|████████▉ | 3572/4000 [14:25:32<1:36:56, 13.59s/it] 89%|████████▉ | 3573/4000 [14:25:45<1:36:23, 13.55s/it] 89%|████████▉ | 3574/4000 [14:26:01<1:40:44, 14.19s/it] 89%|████████▉ | 3575/4000 [14:26:13<1:36:34, 13.63s/it] 89%|████████▉ | 3576/4000 [14:26:29<1:40:40, 14.25s/it] 89%|████████▉ | 3577/4000 [14:26:41<1:35:51, 13.60s/it] 89%|████████▉ | 3578/4000 [14:26:54<1:35:38, 13.60s/it] 89%|████████▉ | 3579/4000 [14:27:09<1:36:38, 13.77s/it] 90%|████████▉ | 3580/4000 [14:27:22<1:36:03, 13.72s/it]                                                         90%|████████▉ | 3580/4000 [14:27:22<1:36:03, 13.72s/it] 90%|████████▉ | 3581/4000 [14:27:36<1:35:27, 13.67s/it] 90%|████████▉ | 3582/4000 [14:27:50<1:37:16, 13.96s/it] 90%|████████▉ | 3583/4000 [14:28:04<1:36:29, 13.88s/it] 90%|████████▉ | 3584/4000 [14:28:19<1:38:07, 14.15s/it] 90%|████████▉ | 3585/4000 [14:28:35<1:40:56, 14.59s/it] 90%|████████▉ | 3586/4000 [14:28:47<1:35:45, 13.88s/it] 90%|████████▉ | 3587/4000 [14:29:00<1:34:45, 13.77s/it] 90%|████████▉ | 3588/4000 [14:29:14<1:35:05, 13.85s/it] 90%|████████▉ | 3589/4000 [14:29:28<1:34:06, 13.74s/it] 90%|████████▉ | 3590/4000 [14:29:40<1:30:28, 13.24s/it]                                                         90%|████████▉ | 3590/4000 [14:29:40<1:30:28, 13.24s/it] 90%|████████▉ | 3591/4000 [14:29:56<1:35:15, 13.97s/it] 90%|████████▉ | 3592/4000 [14:30:09<1:34:01, 13.83s/it] 90%|████████▉ | 3593/4000 [14:30:23<1:33:55, 13.85s/it] 90%|████████▉ | 3594/4000 [14:30:36<1:32:53, 13.73s/it] 90%|████████▉ | 3595/4000 [14:30:51<1:34:24, 13.99s/it] 90%|████████▉ | 3596/4000 [14:31:05<1:33:45, 13.92s/it] 90%|████████▉ | 3597/4000 [14:31:19<1:34:35, 14.08s/it] 90%|████████▉ | 3598/4000 [14:31:33<1:33:29, 13.95s/it] 90%|████████▉ | 3599/4000 [14:31:44<1:28:15, 13.20s/it] 90%|█████████ | 3600/4000 [14:31:57<1:27:00, 13.05s/it]                                                         90%|█████████ | 3600/4000 [14:31:57<1:27:00, 13.05s/it] 90%|█████████ | 3601/4000 [14:32:13<1:31:44, 13.79s/it] 90%|█████████ | 3602/4000 [14:32:25<1:28:17, 13.31s/it] 90%|█████████ | 3603/4000 [14:32:40<1:32:50, 14.03s/it] 90%|█████████ | 3604/4000 [14:32:52<1:28:35, 13.42s/it] 90%|█████████ | 3605/4000 [14:33:06<1:29:10, 13.55s/it] 90%|█████████ | 3606/4000 [14:33:20<1:30:13, 13.74s/it] 90%|█████████ | 3607/4000 [14:33:34<1:29:23, 13.65s/it] 90%|█████████ | 3608/4000 [14:33:50<1:33:25, 14.30s/it] 90%|█████████ | 3609/4000 [14:34:02<1:29:07, 13.68s/it] 90%|█████████ | 3610/4000 [14:34:17<1:32:18, 14.20s/it]                                                         90%|█████████ | 3610/4000 [14:34:17<1:32:18, 14.20s/it] 90%|█████████ | 3611/4000 [14:34:29<1:27:48, 13.54s/it] 90%|█████████ | 3612/4000 [14:34:45<1:31:00, 14.07s/it] 90%|█████████ | 3613/4000 [14:34:57<1:26:55, 13.48s/it] 90%|█████████ | 3614/4000 [14:35:10<1:26:09, 13.39s/it] 90%|█████████ | 3615/4000 [14:35:24<1:27:04, 13.57s/it] 90%|█████████ | 3616/4000 [14:35:37<1:26:14, 13.47s/it] 90%|█████████ | 3617/4000 [14:35:53<1:30:16, 14.14s/it] 90%|█████████ | 3618/4000 [14:36:05<1:27:04, 13.68s/it] 90%|█████████ | 3619/4000 [14:36:21<1:30:49, 14.30s/it] 90%|█████████ | 3620/4000 [14:36:34<1:27:14, 13.77s/it]                                                         90%|█████████ | 3620/4000 [14:36:34<1:27:14, 13.77s/it] 91%|█████████ | 3621/4000 [14:36:47<1:26:13, 13.65s/it] 91%|█████████ | 3622/4000 [14:37:01<1:26:44, 13.77s/it] 91%|█████████ | 3623/4000 [14:37:14<1:25:31, 13.61s/it] 91%|█████████ | 3624/4000 [14:37:29<1:27:16, 13.93s/it] 91%|█████████ | 3625/4000 [14:37:43<1:26:13, 13.80s/it] 91%|█████████ | 3626/4000 [14:37:57<1:27:09, 13.98s/it] 91%|█████████ | 3627/4000 [14:38:10<1:25:49, 13.81s/it] 91%|█████████ | 3628/4000 [14:38:26<1:29:17, 14.40s/it] 91%|█████████ | 3629/4000 [14:38:38<1:25:03, 13.76s/it] 91%|█████████ | 3630/4000 [14:38:54<1:28:53, 14.42s/it]                                                         91%|█████████ | 3630/4000 [14:38:54<1:28:53, 14.42s/it] 91%|█████████ | 3631/4000 [14:39:07<1:24:37, 13.76s/it] 91%|█████████ | 3632/4000 [14:39:22<1:27:54, 14.33s/it] 91%|█████████ | 3633/4000 [14:39:35<1:24:20, 13.79s/it] 91%|█████████ | 3634/4000 [14:39:51<1:28:07, 14.45s/it] 91%|█████████ | 3635/4000 [14:40:03<1:24:28, 13.89s/it] 91%|█████████ | 3636/4000 [14:40:19<1:27:52, 14.49s/it] 91%|█████████ | 3637/4000 [14:40:33<1:27:08, 14.40s/it] 91%|█████████ | 3638/4000 [14:40:47<1:25:07, 14.11s/it] 91%|█████████ | 3639/4000 [14:41:01<1:24:24, 14.03s/it] 91%|█████████ | 3640/4000 [14:41:15<1:24:39, 14.11s/it]                                                         91%|█████████ | 3640/4000 [14:41:15<1:24:39, 14.11s/it] 91%|█████████ | 3641/4000 [14:41:29<1:23:52, 14.02s/it] 91%|█████████ | 3642/4000 [14:41:43<1:23:24, 13.98s/it] 91%|█████████ | 3643/4000 [14:41:57<1:23:00, 13.95s/it] 91%|█████████ | 3644/4000 [14:42:11<1:23:27, 14.07s/it] 91%|█████████ | 3645/4000 [14:42:24<1:22:12, 13.90s/it] 91%|█████████ | 3646/4000 [14:42:36<1:18:43, 13.34s/it] 91%|█████████ | 3647/4000 [14:42:52<1:23:02, 14.12s/it] 91%|█████████ | 3648/4000 [14:43:06<1:21:23, 13.87s/it] 91%|█████████ | 3649/4000 [14:43:20<1:22:04, 14.03s/it] 91%|█████████▏| 3650/4000 [14:43:33<1:20:14, 13.75s/it]                                                         91%|█████████▏| 3650/4000 [14:43:33<1:20:14, 13.75s/it] 91%|█████████▏| 3651/4000 [14:43:47<1:20:37, 13.86s/it] 91%|█████████▏| 3652/4000 [14:44:01<1:20:13, 13.83s/it] 91%|█████████▏| 3653/4000 [14:44:13<1:17:21, 13.38s/it] 91%|█████████▏| 3654/4000 [14:44:29<1:21:19, 14.10s/it] 91%|█████████▏| 3655/4000 [14:44:41<1:17:53, 13.55s/it] 91%|█████████▏| 3656/4000 [14:44:57<1:21:28, 14.21s/it] 91%|█████████▏| 3657/4000 [14:45:13<1:23:42, 14.64s/it] 91%|█████████▏| 3658/4000 [14:45:25<1:19:01, 13.86s/it] 91%|█████████▏| 3659/4000 [14:45:40<1:21:38, 14.36s/it] 92%|█████████▏| 3660/4000 [14:45:53<1:17:54, 13.75s/it]                                                         92%|█████████▏| 3660/4000 [14:45:53<1:17:54, 13.75s/it] 92%|█████████▏| 3661/4000 [14:46:09<1:21:24, 14.41s/it] 92%|█████████▏| 3662/4000 [14:46:21<1:17:50, 13.82s/it] 92%|█████████▏| 3663/4000 [14:46:37<1:20:43, 14.37s/it] 92%|█████████▏| 3664/4000 [14:46:49<1:16:18, 13.63s/it] 92%|█████████▏| 3665/4000 [14:47:04<1:19:24, 14.22s/it] 92%|█████████▏| 3666/4000 [14:47:16<1:15:08, 13.50s/it] 92%|█████████▏| 3667/4000 [14:47:30<1:15:35, 13.62s/it] 92%|█████████▏| 3668/4000 [14:47:46<1:19:41, 14.40s/it] 92%|█████████▏| 3669/4000 [14:47:59<1:16:02, 13.78s/it] 92%|█████████▏| 3670/4000 [14:48:14<1:18:23, 14.25s/it]                                                         92%|█████████▏| 3670/4000 [14:48:14<1:18:23, 14.25s/it] 92%|█████████▏| 3671/4000 [14:48:26<1:14:46, 13.64s/it] 92%|█████████▏| 3672/4000 [14:48:40<1:14:15, 13.58s/it] 92%|█████████▏| 3673/4000 [14:48:54<1:15:24, 13.84s/it] 92%|█████████▏| 3674/4000 [14:49:08<1:14:52, 13.78s/it] 92%|█████████▏| 3675/4000 [14:49:21<1:13:43, 13.61s/it] 92%|█████████▏| 3676/4000 [14:49:35<1:14:54, 13.87s/it] 92%|█████████▏| 3677/4000 [14:49:49<1:14:07, 13.77s/it] 92%|█████████▏| 3678/4000 [14:50:03<1:14:51, 13.95s/it] 92%|█████████▏| 3679/4000 [14:50:17<1:13:58, 13.83s/it] 92%|█████████▏| 3680/4000 [14:50:29<1:11:32, 13.41s/it]                                                         92%|█████████▏| 3680/4000 [14:50:29<1:11:32, 13.41s/it] 92%|█████████▏| 3681/4000 [14:50:45<1:15:16, 14.16s/it] 92%|█████████▏| 3682/4000 [14:50:57<1:11:42, 13.53s/it] 92%|█████████▏| 3683/4000 [14:51:13<1:15:13, 14.24s/it] 92%|█████████▏| 3684/4000 [14:51:25<1:12:00, 13.67s/it] 92%|█████████▏| 3685/4000 [14:51:41<1:15:30, 14.38s/it] 92%|█████████▏| 3686/4000 [14:51:55<1:14:19, 14.20s/it] 92%|█████████▏| 3687/4000 [14:52:10<1:14:13, 14.23s/it] 92%|█████████▏| 3688/4000 [14:52:23<1:12:59, 14.04s/it] 92%|█████████▏| 3689/4000 [14:52:36<1:10:11, 13.54s/it] 92%|█████████▏| 3690/4000 [14:52:52<1:13:43, 14.27s/it]                                                         92%|█████████▏| 3690/4000 [14:52:52<1:13:43, 14.27s/it] 92%|█████████▏| 3691/4000 [14:53:04<1:10:05, 13.61s/it] 92%|█████████▏| 3692/4000 [14:53:17<1:09:50, 13.61s/it] 92%|█████████▏| 3693/4000 [14:53:32<1:10:49, 13.84s/it] 92%|█████████▏| 3694/4000 [14:53:45<1:10:11, 13.76s/it] 92%|█████████▏| 3695/4000 [14:54:00<1:11:00, 13.97s/it] 92%|█████████▏| 3696/4000 [14:54:13<1:10:32, 13.92s/it] 92%|█████████▏| 3697/4000 [14:54:27<1:09:44, 13.81s/it] 92%|█████████▏| 3698/4000 [14:54:41<1:10:07, 13.93s/it] 92%|█████████▏| 3699/4000 [14:54:55<1:09:17, 13.81s/it] 92%|█████████▎| 3700/4000 [14:55:09<1:09:36, 13.92s/it]                                                         92%|█████████▎| 3700/4000 [14:55:09<1:09:36, 13.92s/it] 93%|█████████▎| 3701/4000 [14:55:22<1:08:23, 13.72s/it] 93%|█████████▎| 3702/4000 [14:55:37<1:09:38, 14.02s/it] 93%|█████████▎| 3703/4000 [14:55:51<1:09:06, 13.96s/it] 93%|█████████▎| 3704/4000 [14:56:05<1:09:42, 14.13s/it] 93%|█████████▎| 3705/4000 [14:56:19<1:09:08, 14.06s/it] 93%|█████████▎| 3706/4000 [14:56:35<1:11:16, 14.55s/it] 93%|█████████▎| 3707/4000 [14:56:47<1:07:15, 13.77s/it] 93%|█████████▎| 3708/4000 [14:57:03<1:09:55, 14.37s/it] 93%|█████████▎| 3709/4000 [14:57:15<1:06:36, 13.73s/it] 93%|█████████▎| 3710/4000 [14:57:31<1:09:28, 14.37s/it]                                                         93%|█████████▎| 3710/4000 [14:57:31<1:09:28, 14.37s/it] 93%|█████████▎| 3711/4000 [14:57:43<1:06:17, 13.76s/it] 93%|█████████▎| 3712/4000 [14:57:59<1:09:12, 14.42s/it] 93%|█████████▎| 3713/4000 [14:58:11<1:05:10, 13.63s/it] 93%|█████████▎| 3714/4000 [14:58:24<1:04:41, 13.57s/it] 93%|█████████▎| 3715/4000 [14:58:40<1:07:25, 14.19s/it] 93%|█████████▎| 3716/4000 [14:58:52<1:04:17, 13.58s/it] 93%|█████████▎| 3717/4000 [14:59:08<1:07:10, 14.24s/it] 93%|█████████▎| 3718/4000 [14:59:20<1:04:22, 13.70s/it] 93%|█████████▎| 3719/4000 [14:59:36<1:06:52, 14.28s/it] 93%|█████████▎| 3720/4000 [14:59:48<1:03:37, 13.64s/it]                                                         93%|█████████▎| 3720/4000 [14:59:48<1:03:37, 13.64s/it] 93%|█████████▎| 3721/4000 [15:00:01<1:03:00, 13.55s/it] 93%|█████████▎| 3722/4000 [15:00:16<1:03:47, 13.77s/it] 93%|█████████▎| 3723/4000 [15:00:29<1:03:28, 13.75s/it] 93%|█████████▎| 3724/4000 [15:00:44<1:04:06, 13.94s/it] 93%|█████████▎| 3725/4000 [15:00:57<1:02:49, 13.71s/it] 93%|█████████▎| 3726/4000 [15:01:12<1:04:55, 14.22s/it] 93%|█████████▎| 3727/4000 [15:01:25<1:02:14, 13.68s/it] 93%|█████████▎| 3728/4000 [15:01:40<1:04:48, 14.29s/it] 93%|█████████▎| 3729/4000 [15:01:52<1:01:32, 13.63s/it] 93%|█████████▎| 3730/4000 [15:02:08<1:03:48, 14.18s/it]                                                         93%|█████████▎| 3730/4000 [15:02:08<1:03:48, 14.18s/it] 93%|█████████▎| 3731/4000 [15:02:20<1:01:03, 13.62s/it] 93%|█████████▎| 3732/4000 [15:02:36<1:03:53, 14.30s/it] 93%|█████████▎| 3733/4000 [15:02:48<1:00:46, 13.66s/it] 93%|█████████▎| 3734/4000 [15:03:02<1:00:49, 13.72s/it] 93%|█████████▎| 3735/4000 [15:03:18<1:03:12, 14.31s/it] 93%|█████████▎| 3736/4000 [15:03:32<1:02:28, 14.20s/it] 93%|█████████▎| 3737/4000 [15:03:45<1:01:31, 14.03s/it] 93%|█████████▎| 3738/4000 [15:03:58<58:48, 13.47s/it]   93%|█████████▎| 3739/4000 [15:04:14<1:01:52, 14.22s/it] 94%|█████████▎| 3740/4000 [15:04:26<59:00, 13.62s/it]                                                         94%|█████████▎| 3740/4000 [15:04:26<59:00, 13.62s/it] 94%|█████████▎| 3741/4000 [15:04:42<1:02:23, 14.46s/it] 94%|█████████▎| 3742/4000 [15:04:54<59:23, 13.81s/it]   94%|█████████▎| 3743/4000 [15:05:08<59:16, 13.84s/it] 94%|█████████▎| 3744/4000 [15:05:23<59:54, 14.04s/it] 94%|█████████▎| 3745/4000 [15:05:37<59:21, 13.97s/it] 94%|█████████▎| 3746/4000 [15:05:52<1:01:05, 14.43s/it] 94%|█████████▎| 3747/4000 [15:06:05<58:19, 13.83s/it]   94%|█████████▎| 3748/4000 [15:06:20<1:00:35, 14.43s/it] 94%|█████████▎| 3749/4000 [15:06:33<57:51, 13.83s/it]   94%|█████████▍| 3750/4000 [15:06:49<1:00:12, 14.45s/it]                                                         94%|█████████▍| 3750/4000 [15:06:49<1:00:12, 14.45s/it] 94%|█████████▍| 3751/4000 [15:07:01<57:20, 13.82s/it]   94%|█████████▍| 3752/4000 [15:07:17<59:40, 14.44s/it] 94%|█████████▍| 3753/4000 [15:07:29<56:59, 13.84s/it] 94%|█████████▍| 3754/4000 [15:07:45<58:45, 14.33s/it] 94%|█████████▍| 3755/4000 [15:07:58<57:16, 14.03s/it] 94%|█████████▍| 3756/4000 [15:08:10<54:23, 13.38s/it] 94%|█████████▍| 3757/4000 [15:08:26<56:52, 14.04s/it] 94%|█████████▍| 3758/4000 [15:08:37<53:42, 13.32s/it] 94%|█████████▍| 3759/4000 [15:08:53<56:10, 13.98s/it] 94%|█████████▍| 3760/4000 [15:09:05<54:02, 13.51s/it]                                                       94%|█████████▍| 3760/4000 [15:09:05<54:02, 13.51s/it] 94%|█████████▍| 3761/4000 [15:09:21<56:29, 14.18s/it] 94%|█████████▍| 3762/4000 [15:09:33<53:49, 13.57s/it] 94%|█████████▍| 3763/4000 [15:09:49<55:50, 14.14s/it] 94%|█████████▍| 3764/4000 [15:10:02<55:00, 13.99s/it] 94%|█████████▍| 3765/4000 [15:10:17<55:29, 14.17s/it] 94%|█████████▍| 3766/4000 [15:10:31<54:58, 14.10s/it] 94%|█████████▍| 3767/4000 [15:10:45<54:58, 14.16s/it] 94%|█████████▍| 3768/4000 [15:10:49<43:12, 11.17s/it] 94%|█████████▍| 3769/4000 [15:11:03<46:05, 11.97s/it] 94%|█████████▍| 3770/4000 [15:11:17<48:08, 12.56s/it]                                                       94%|█████████▍| 3770/4000 [15:11:17<48:08, 12.56s/it] 94%|█████████▍| 3771/4000 [15:11:33<51:42, 13.55s/it] 94%|█████████▍| 3772/4000 [15:11:45<49:31, 13.03s/it] 94%|█████████▍| 3773/4000 [15:11:59<50:24, 13.32s/it] 94%|█████████▍| 3774/4000 [15:12:13<51:17, 13.62s/it] 94%|█████████▍| 3775/4000 [15:12:27<51:02, 13.61s/it] 94%|█████████▍| 3776/4000 [15:12:41<51:15, 13.73s/it] 94%|█████████▍| 3777/4000 [15:12:54<51:08, 13.76s/it] 94%|█████████▍| 3778/4000 [15:13:08<50:56, 13.77s/it] 94%|█████████▍| 3779/4000 [15:13:23<51:28, 13.97s/it] 94%|█████████▍| 3780/4000 [15:13:36<50:47, 13.85s/it]                                                       94%|█████████▍| 3780/4000 [15:13:36<50:47, 13.85s/it] 95%|█████████▍| 3781/4000 [15:13:50<50:42, 13.89s/it] 95%|█████████▍| 3782/4000 [15:14:03<49:19, 13.58s/it] 95%|█████████▍| 3783/4000 [15:14:18<50:14, 13.89s/it] 95%|█████████▍| 3784/4000 [15:14:32<50:03, 13.91s/it] 95%|█████████▍| 3785/4000 [15:14:46<50:04, 13.97s/it] 95%|█████████▍| 3786/4000 [15:15:00<49:53, 13.99s/it] 95%|█████████▍| 3787/4000 [15:15:12<48:04, 13.54s/it] 95%|█████████▍| 3788/4000 [15:15:28<50:10, 14.20s/it] 95%|█████████▍| 3789/4000 [15:15:42<49:34, 14.10s/it] 95%|█████████▍| 3790/4000 [15:15:56<49:44, 14.21s/it]                                                       95%|█████████▍| 3790/4000 [15:15:56<49:44, 14.21s/it] 95%|█████████▍| 3791/4000 [15:16:13<51:33, 14.80s/it] 95%|█████████▍| 3792/4000 [15:16:24<47:56, 13.83s/it] 95%|█████████▍| 3793/4000 [15:16:38<47:26, 13.75s/it] 95%|█████████▍| 3794/4000 [15:16:52<47:36, 13.87s/it] 95%|█████████▍| 3795/4000 [15:17:05<46:58, 13.75s/it] 95%|█████████▍| 3796/4000 [15:17:20<47:28, 13.96s/it] 95%|█████████▍| 3797/4000 [15:17:34<47:11, 13.95s/it] 95%|█████████▍| 3798/4000 [15:17:48<47:14, 14.03s/it] 95%|█████████▍| 3799/4000 [15:18:02<46:46, 13.96s/it] 95%|█████████▌| 3800/4000 [15:18:17<48:10, 14.45s/it]                                                       95%|█████████▌| 3800/4000 [15:18:17<48:10, 14.45s/it] 95%|█████████▌| 3801/4000 [15:18:29<45:32, 13.73s/it] 95%|█████████▌| 3802/4000 [15:18:45<47:12, 14.30s/it] 95%|█████████▌| 3803/4000 [15:18:57<44:59, 13.70s/it] 95%|█████████▌| 3804/4000 [15:19:13<46:31, 14.24s/it] 95%|█████████▌| 3805/4000 [15:19:25<44:36, 13.73s/it] 95%|█████████▌| 3806/4000 [15:19:39<44:28, 13.76s/it] 95%|█████████▌| 3807/4000 [15:19:53<44:41, 13.89s/it] 95%|█████████▌| 3808/4000 [15:20:07<43:53, 13.72s/it] 95%|█████████▌| 3809/4000 [15:20:21<44:22, 13.94s/it] 95%|█████████▌| 3810/4000 [15:20:34<43:12, 13.64s/it]                                                       95%|█████████▌| 3810/4000 [15:20:34<43:12, 13.64s/it] 95%|█████████▌| 3811/4000 [15:20:50<45:07, 14.33s/it] 95%|█████████▌| 3812/4000 [15:21:02<43:01, 13.73s/it] 95%|█████████▌| 3813/4000 [15:21:16<43:02, 13.81s/it] 95%|█████████▌| 3814/4000 [15:21:31<43:39, 14.08s/it] 95%|█████████▌| 3815/4000 [15:21:45<43:02, 13.96s/it] 95%|█████████▌| 3816/4000 [15:21:59<43:16, 14.11s/it] 95%|█████████▌| 3817/4000 [15:22:13<42:40, 13.99s/it] 95%|█████████▌| 3818/4000 [15:22:27<42:37, 14.05s/it] 95%|█████████▌| 3819/4000 [15:22:41<41:57, 13.91s/it] 96%|█████████▌| 3820/4000 [15:22:57<43:33, 14.52s/it]                                                       96%|█████████▌| 3820/4000 [15:22:57<43:33, 14.52s/it] 96%|█████████▌| 3821/4000 [15:23:08<40:50, 13.69s/it] 96%|█████████▌| 3822/4000 [15:23:22<40:41, 13.71s/it] 96%|█████████▌| 3823/4000 [15:23:36<40:53, 13.86s/it] 96%|█████████▌| 3824/4000 [15:23:50<40:22, 13.77s/it] 96%|█████████▌| 3825/4000 [15:24:04<40:47, 13.99s/it] 96%|█████████▌| 3826/4000 [15:24:18<40:19, 13.90s/it] 96%|█████████▌| 3827/4000 [15:24:33<40:42, 14.12s/it] 96%|█████████▌| 3828/4000 [15:24:47<40:20, 14.07s/it] 96%|█████████▌| 3829/4000 [15:25:01<39:54, 14.00s/it] 96%|█████████▌| 3830/4000 [15:25:15<39:57, 14.10s/it]                                                       96%|█████████▌| 3830/4000 [15:25:15<39:57, 14.10s/it] 96%|█████████▌| 3831/4000 [15:25:28<39:14, 13.93s/it] 96%|█████████▌| 3832/4000 [15:25:43<39:23, 14.07s/it] 96%|█████████▌| 3833/4000 [15:25:57<38:55, 13.98s/it] 96%|█████████▌| 3834/4000 [15:26:11<38:41, 13.98s/it] 96%|█████████▌| 3835/4000 [15:26:24<38:00, 13.82s/it] 96%|█████████▌| 3836/4000 [15:26:38<38:02, 13.92s/it] 96%|█████████▌| 3837/4000 [15:26:52<37:25, 13.78s/it] 96%|█████████▌| 3838/4000 [15:27:06<37:33, 13.91s/it] 96%|█████████▌| 3839/4000 [15:27:19<36:47, 13.71s/it] 96%|█████████▌| 3840/4000 [15:27:35<38:32, 14.45s/it]                                                       96%|█████████▌| 3840/4000 [15:27:35<38:32, 14.45s/it] 96%|█████████▌| 3841/4000 [15:27:47<36:20, 13.71s/it] 96%|█████████▌| 3842/4000 [15:28:03<37:44, 14.33s/it] 96%|█████████▌| 3843/4000 [15:28:17<37:17, 14.25s/it] 96%|█████████▌| 3844/4000 [15:28:31<36:32, 14.06s/it] 96%|█████████▌| 3845/4000 [15:28:45<36:38, 14.18s/it] 96%|█████████▌| 3846/4000 [15:28:59<36:05, 14.06s/it] 96%|█████████▌| 3847/4000 [15:29:13<35:57, 14.10s/it] 96%|█████████▌| 3848/4000 [15:29:27<35:22, 13.97s/it] 96%|█████████▌| 3849/4000 [15:29:38<33:23, 13.27s/it] 96%|█████████▋| 3850/4000 [15:29:54<34:59, 14.00s/it]                                                       96%|█████████▋| 3850/4000 [15:29:54<34:59, 14.00s/it] 96%|█████████▋| 3851/4000 [15:30:08<34:31, 13.91s/it] 96%|█████████▋| 3852/4000 [15:30:20<32:56, 13.35s/it] 96%|█████████▋| 3853/4000 [15:30:36<34:52, 14.23s/it] 96%|█████████▋| 3854/4000 [15:30:48<32:55, 13.53s/it] 96%|█████████▋| 3855/4000 [15:31:04<34:25, 14.25s/it] 96%|█████████▋| 3856/4000 [15:31:16<32:30, 13.54s/it] 96%|█████████▋| 3857/4000 [15:31:32<34:01, 14.28s/it] 96%|█████████▋| 3858/4000 [15:31:44<32:10, 13.60s/it] 96%|█████████▋| 3859/4000 [15:32:00<33:31, 14.26s/it] 96%|█████████▋| 3860/4000 [15:32:13<32:46, 14.05s/it]                                                       96%|█████████▋| 3860/4000 [15:32:13<32:46, 14.05s/it] 97%|█████████▋| 3861/4000 [15:32:27<32:35, 14.07s/it] 97%|█████████▋| 3862/4000 [15:32:41<32:24, 14.09s/it] 97%|█████████▋| 3863/4000 [15:32:55<32:06, 14.06s/it] 97%|█████████▋| 3864/4000 [15:33:10<31:56, 14.09s/it] 97%|█████████▋| 3865/4000 [15:33:24<31:54, 14.18s/it] 97%|█████████▋| 3866/4000 [15:33:38<31:15, 14.00s/it] 97%|█████████▋| 3867/4000 [15:33:52<31:01, 14.00s/it] 97%|█████████▋| 3868/4000 [15:34:05<30:39, 13.93s/it] 97%|█████████▋| 3869/4000 [15:34:20<30:33, 14.00s/it] 97%|█████████▋| 3870/4000 [15:34:33<30:09, 13.92s/it]                                                       97%|█████████▋| 3870/4000 [15:34:33<30:09, 13.92s/it] 97%|█████████▋| 3871/4000 [15:34:47<30:03, 13.98s/it] 97%|█████████▋| 3872/4000 [15:35:01<29:35, 13.87s/it] 97%|█████████▋| 3873/4000 [15:35:15<29:13, 13.81s/it] 97%|█████████▋| 3874/4000 [15:35:29<29:09, 13.88s/it] 97%|█████████▋| 3875/4000 [15:35:42<28:44, 13.80s/it] 97%|█████████▋| 3876/4000 [15:35:57<28:49, 13.95s/it] 97%|█████████▋| 3877/4000 [15:36:10<28:32, 13.92s/it] 97%|█████████▋| 3878/4000 [15:36:25<28:34, 14.06s/it] 97%|█████████▋| 3879/4000 [15:36:38<28:01, 13.90s/it] 97%|█████████▋| 3880/4000 [15:36:53<28:03, 14.03s/it]                                                       97%|█████████▋| 3880/4000 [15:36:53<28:03, 14.03s/it] 97%|█████████▋| 3881/4000 [15:37:06<27:23, 13.81s/it] 97%|█████████▋| 3882/4000 [15:37:22<28:27, 14.47s/it] 97%|█████████▋| 3883/4000 [15:37:34<26:48, 13.75s/it] 97%|█████████▋| 3884/4000 [15:37:50<27:45, 14.36s/it] 97%|█████████▋| 3885/4000 [15:38:02<26:10, 13.66s/it] 97%|█████████▋| 3886/4000 [15:38:18<27:04, 14.25s/it] 97%|█████████▋| 3887/4000 [15:38:30<25:37, 13.61s/it] 97%|█████████▋| 3888/4000 [15:38:44<25:35, 13.71s/it] 97%|█████████▋| 3889/4000 [15:38:58<25:43, 13.90s/it] 97%|█████████▋| 3890/4000 [15:39:12<25:22, 13.84s/it]                                                       97%|█████████▋| 3890/4000 [15:39:12<25:22, 13.84s/it] 97%|█████████▋| 3891/4000 [15:39:28<26:14, 14.45s/it] 97%|█████████▋| 3892/4000 [15:39:40<24:46, 13.76s/it] 97%|█████████▋| 3893/4000 [15:39:55<25:19, 14.20s/it] 97%|█████████▋| 3894/4000 [15:40:07<24:09, 13.67s/it] 97%|█████████▋| 3895/4000 [15:40:23<25:04, 14.32s/it] 97%|█████████▋| 3896/4000 [15:40:35<23:39, 13.65s/it] 97%|█████████▋| 3897/4000 [15:40:51<24:37, 14.34s/it] 97%|█████████▋| 3898/4000 [15:41:04<23:21, 13.74s/it] 97%|█████████▋| 3899/4000 [15:41:19<24:01, 14.27s/it] 98%|█████████▊| 3900/4000 [15:41:31<22:28, 13.48s/it]                                                       98%|█████████▊| 3900/4000 [15:41:31<22:28, 13.48s/it] 98%|█████████▊| 3901/4000 [15:41:47<23:35, 14.30s/it] 98%|█████████▊| 3902/4000 [15:42:00<22:45, 13.93s/it] 98%|█████████▊| 3903/4000 [15:42:14<22:37, 13.99s/it] 98%|█████████▊| 3904/4000 [15:42:28<22:17, 13.93s/it] 98%|█████████▊| 3905/4000 [15:42:42<22:16, 14.06s/it] 98%|█████████▊| 3906/4000 [15:42:56<21:39, 13.82s/it] 98%|█████████▊| 3907/4000 [15:43:07<20:28, 13.21s/it] 98%|█████████▊| 3908/4000 [15:43:23<21:30, 14.03s/it] 98%|█████████▊| 3909/4000 [15:43:35<20:18, 13.39s/it] 98%|█████████▊| 3910/4000 [15:43:49<20:11, 13.46s/it]                                                       98%|█████████▊| 3910/4000 [15:43:49<20:11, 13.46s/it] 98%|█████████▊| 3911/4000 [15:44:04<20:54, 14.10s/it] 98%|█████████▊| 3912/4000 [15:44:16<19:43, 13.45s/it] 98%|█████████▊| 3913/4000 [15:44:32<20:28, 14.12s/it] 98%|█████████▊| 3914/4000 [15:44:44<19:20, 13.50s/it] 98%|█████████▊| 3915/4000 [15:45:00<20:01, 14.14s/it] 98%|█████████▊| 3916/4000 [15:45:12<19:06, 13.65s/it] 98%|█████████▊| 3917/4000 [15:45:26<18:47, 13.59s/it] 98%|█████████▊| 3918/4000 [15:45:40<18:51, 13.79s/it] 98%|█████████▊| 3919/4000 [15:45:54<18:33, 13.75s/it] 98%|█████████▊| 3920/4000 [15:46:10<19:14, 14.43s/it]                                                       98%|█████████▊| 3920/4000 [15:46:10<19:14, 14.43s/it] 98%|█████████▊| 3921/4000 [15:46:22<18:10, 13.80s/it] 98%|█████████▊| 3922/4000 [15:46:38<18:42, 14.39s/it] 98%|█████████▊| 3923/4000 [15:46:50<17:29, 13.64s/it] 98%|█████████▊| 3924/4000 [15:47:05<18:04, 14.26s/it] 98%|█████████▊| 3925/4000 [15:47:17<16:56, 13.56s/it] 98%|█████████▊| 3926/4000 [15:47:30<16:35, 13.46s/it] 98%|█████████▊| 3927/4000 [15:47:45<16:44, 13.76s/it] 98%|█████████▊| 3928/4000 [15:47:58<16:24, 13.68s/it] 98%|█████████▊| 3929/4000 [15:48:13<16:21, 13.82s/it] 98%|█████████▊| 3930/4000 [15:48:26<15:58, 13.70s/it]                                                       98%|█████████▊| 3930/4000 [15:48:26<15:58, 13.70s/it] 98%|█████████▊| 3931/4000 [15:48:42<16:29, 14.34s/it] 98%|█████████▊| 3932/4000 [15:48:54<15:22, 13.57s/it] 98%|█████████▊| 3933/4000 [15:49:09<15:48, 14.16s/it] 98%|█████████▊| 3934/4000 [15:49:21<14:58, 13.61s/it] 98%|█████████▊| 3935/4000 [15:49:37<15:27, 14.26s/it] 98%|█████████▊| 3936/4000 [15:49:49<14:32, 13.63s/it] 98%|█████████▊| 3937/4000 [15:50:05<14:57, 14.25s/it] 98%|█████████▊| 3938/4000 [15:50:17<14:03, 13.61s/it] 98%|█████████▊| 3939/4000 [15:50:31<13:54, 13.68s/it] 98%|█████████▊| 3940/4000 [15:50:47<14:17, 14.29s/it]                                                       98%|█████████▊| 3940/4000 [15:50:47<14:17, 14.29s/it] 99%|█████████▊| 3941/4000 [15:50:58<13:13, 13.45s/it] 99%|█████████▊| 3942/4000 [15:51:12<13:02, 13.49s/it] 99%|█████████▊| 3943/4000 [15:51:26<13:09, 13.85s/it] 99%|█████████▊| 3944/4000 [15:51:40<12:57, 13.88s/it] 99%|█████████▊| 3945/4000 [15:51:55<12:48, 13.97s/it] 99%|█████████▊| 3946/4000 [15:52:08<12:30, 13.89s/it] 99%|█████████▊| 3947/4000 [15:52:23<12:22, 14.02s/it] 99%|█████████▊| 3948/4000 [15:52:36<12:01, 13.87s/it] 99%|█████████▊| 3949/4000 [15:52:50<11:42, 13.78s/it] 99%|█████████▉| 3950/4000 [15:53:03<11:27, 13.76s/it]                                                       99%|█████████▉| 3950/4000 [15:53:03<11:27, 13.76s/it] 99%|█████████▉| 3951/4000 [15:53:17<11:08, 13.65s/it] 99%|█████████▉| 3952/4000 [15:53:29<10:38, 13.30s/it] 99%|█████████▉| 3953/4000 [15:53:45<11:02, 14.10s/it] 99%|█████████▉| 3954/4000 [15:53:58<10:22, 13.54s/it] 99%|█████████▉| 3955/4000 [15:54:13<10:38, 14.19s/it] 99%|█████████▉| 3956/4000 [15:54:26<09:59, 13.63s/it] 99%|█████████▉| 3957/4000 [15:54:41<10:14, 14.28s/it] 99%|█████████▉| 3958/4000 [15:54:55<09:56, 14.21s/it] 99%|█████████▉| 3959/4000 [15:55:07<09:12, 13.46s/it] 99%|█████████▉| 3960/4000 [15:55:23<09:31, 14.28s/it]                                                       99%|█████████▉| 3960/4000 [15:55:23<09:31, 14.28s/it] 99%|█████████▉| 3961/4000 [15:55:36<08:54, 13.70s/it] 99%|█████████▉| 3962/4000 [15:55:52<09:07, 14.41s/it] 99%|█████████▉| 3963/4000 [15:56:04<08:28, 13.74s/it] 99%|█████████▉| 3964/4000 [15:56:19<08:33, 14.26s/it] 99%|█████████▉| 3965/4000 [15:56:31<07:55, 13.60s/it] 99%|█████████▉| 3966/4000 [15:56:48<08:08, 14.36s/it] 99%|█████████▉| 3967/4000 [15:57:00<07:32, 13.72s/it] 99%|█████████▉| 3968/4000 [15:57:15<07:35, 14.23s/it] 99%|█████████▉| 3969/4000 [15:57:29<07:14, 14.03s/it] 99%|█████████▉| 3970/4000 [15:57:41<06:45, 13.51s/it]                                                       99%|█████████▉| 3970/4000 [15:57:43<06:45, 13.51s/it] 99%|█████████▉| 3971/4000 [15:57:56<06:44, 13.96s/it] 99%|█████████▉| 3972/4000 [15:58:08<06:14, 13.37s/it] 99%|█████████▉| 3973/4000 [15:58:24<06:20, 14.09s/it] 99%|█████████▉| 3974/4000 [15:58:36<05:50, 13.49s/it] 99%|█████████▉| 3975/4000 [15:58:52<05:58, 14.34s/it] 99%|█████████▉| 3976/4000 [15:59:04<05:27, 13.66s/it] 99%|█████████▉| 3977/4000 [15:59:20<05:29, 14.34s/it] 99%|█████████▉| 3978/4000 [15:59:34<05:13, 14.25s/it] 99%|█████████▉| 3979/4000 [15:59:48<04:56, 14.11s/it]100%|█████████▉| 3980/4000 [16:00:01<04:37, 13.89s/it]                                                      100%|█████████▉| 3980/4000 [16:00:01<04:37, 13.89s/it]100%|█████████▉| 3981/4000 [16:00:15<04:21, 13.77s/it]100%|█████████▉| 3982/4000 [16:00:29<04:08, 13.79s/it]100%|█████████▉| 3983/4000 [16:00:43<03:56, 13.91s/it]100%|█████████▉| 3984/4000 [16:00:57<03:43, 13.94s/it]100%|█████████▉| 3985/4000 [16:01:09<03:20, 13.37s/it]100%|█████████▉| 3986/4000 [16:01:25<03:17, 14.08s/it]100%|█████████▉| 3987/4000 [16:01:37<02:55, 13.49s/it]100%|█████████▉| 3988/4000 [16:01:53<02:51, 14.29s/it]100%|█████████▉| 3989/4000 [16:02:07<02:35, 14.11s/it]100%|█████████▉| 3990/4000 [16:02:21<02:21, 14.12s/it]                                                      100%|█████████▉| 3990/4000 [16:02:21<02:21, 14.12s/it]100%|█████████▉| 3991/4000 [16:02:34<02:05, 13.91s/it]100%|█████████▉| 3992/4000 [16:02:49<01:52, 14.10s/it]100%|█████████▉| 3993/4000 [16:03:03<01:38, 14.03s/it]100%|█████████▉| 3994/4000 [16:03:17<01:24, 14.13s/it]100%|█████████▉| 3995/4000 [16:03:31<01:10, 14.05s/it]100%|█████████▉| 3996/4000 [16:03:45<00:56, 14.10s/it]100%|█████████▉| 3997/4000 [16:03:59<00:41, 13.97s/it]100%|█████████▉| 3998/4000 [16:04:13<00:28, 14.08s/it]100%|█████████▉| 3999/4000 [16:04:27<00:13, 13.91s/it]100%|██████████| 4000/4000 [16:04:43<00:00, 14.51s/it]                                                      100%|██████████| 4000/4000 [16:04:43<00:00, 14.51s/it]{'eval_loss': '0.1788', 'eval_runtime': '390.5', 'eval_samples_per_second': '1.288', 'eval_steps_per_second': '1.288', 'epoch': '5.574'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3926:{'loss': '0.5501', 'grad_norm': '0.3762', 'learning_rate': '7.799e-06', 'epoch': '5.59'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3931:{'loss': '0.6703', 'grad_norm': '0.3797', 'learning_rate': '6.308e-06', 'epoch': '5.669'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:3933:{'loss': '0.5717', 'grad_norm': '0.4194', 'learning_rate': '5.754e-06', 'epoch': '5.701'}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4007:  6%|▋         | 32/503 [00:22<04:37,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4045: 14%|█▍        | 70/503 [00:54<06:38,  1.09it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4095: 24%|██▍       | 120/503 [01:32<03:44,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4123: 29%|██▉       | 148/503 [01:54<03:29,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4143: 34%|███▍      | 170/503 [02:12<04:40,  1.19it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4243: 54%|█████▎    | 270/503 [03:32<03:27,  1.13it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4282: 61%|██████▏   | 309/503 [04:01<01:54,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4315: 68%|██████▊   | 342/503 [04:26<01:34,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4323: 70%|██████▉   | 350/503 [04:32<01:28,  1.72it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4324: 70%|██████▉   | 351/503 [04:35<02:48,  1.11s/it][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4325: 70%|██████▉   | 352/503 [04:35<02:10,  1.16it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4326: 70%|███████   | 353/503 [04:35<01:44,  1.44it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4327: 70%|███████   | 354/503 [04:35<01:25,  1.73it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4340: 74%|███████▎  | 370/503 [04:47<01:32,  1.44it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4362: 78%|███████▊  | 392/503 [05:04<01:05,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4366: 79%|███████▊  | 396/503 [05:07<01:03,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4387: 83%|████████▎ | 417/503 [05:22<00:50,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4395: 84%|████████▍ | 425/503 [05:29<00:45,  1.70it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4440: 93%|█████████▎| 470/503 [06:04<00:18,  1.79it/s][A
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4483:  0%|          | 0/503 [00:00<?, ?it/s]  0%|          | 2/503 [00:00<01:17,  6.48it/s]  1%|          | 3/503 [00:02<08:58,  1.08s/it]  1%|          | 4/503 [00:02<06:32,  1.27it/s]  1%|          | 5/503 [00:03<05:04,  1.64it/s]  1%|          | 6/503 [00:03<04:10,  1.99it/s]  1%|▏         | 7/503 [00:05<08:52,  1.07s/it]  2%|▏         | 8/503 [00:06<06:51,  1.20it/s]  2%|▏         | 9/503 [00:06<05:30,  1.50it/s]  2%|▏         | 10/503 [00:06<04:34,  1.80it/s]  2%|▏         | 11/503 [00:09<09:07,  1.11s/it]  2%|▏         | 12/503 [00:09<07:06,  1.15it/s]  3%|▎         | 13/503 [00:09<05:41,  1.43it/s]  3%|▎         | 14/503 [00:10<04:40,  1.74it/s]  3%|▎         | 15/503 [00:10<03:56,  2.07it/s]  3%|▎         | 16/503 [00:11<04:44,  1.71it/s]  3%|▎         | 17/503 [00:11<04:03,  2.00it/s]  4%|▎         | 18/503 [00:11<03:32,  2.28it/s]  4%|▍         | 19/503 [00:11<03:07,  2.57it/s]  4%|▍         | 20/503 [00:14<07:58,  1.01it/s]  4%|▍         | 21/503 [00:14<06:20,  1.27it/s]  4%|▍         | 22/503 [00:15<05:11,  1.55it/s]  5%|▍         | 23/503 [00:15<04:23,  1.82it/s]  5%|▍         | 24/503 [00:17<08:53,  1.11s/it]  5%|▍         | 25/503 [00:18<06:59,  1.14it/s]  5%|▌         | 26/503 [00:18<05:39,  1.41it/s]  5%|▌         | 27/503 [00:20<09:47,  1.23s/it]  6%|▌         | 28/503 [00:21<07:31,  1.05it/s]  6%|▌         | 29/503 [00:21<05:55,  1.33it/s]  6%|▌         | 30/503 [00:21<04:46,  1.65it/s]  6%|▌         | 31/503 [00:24<08:53,  1.13s/it]  6%|▋         | 32/503 [00:24<06:58,  1.12it/s]  7%|▋         | 33/503 [00:24<05:36,  1.40it/s]  7%|▋         | 34/503 [00:24<04:37,  1.69it/s]  7%|▋         | 35/503 [00:27<08:45,  1.12s/it]  7%|▋         | 36/503 [00:27<06:50,  1.14it/s]  7%|▋         | 37/503 [00:27<05:26,  1.43it/s]  8%|▊         | 38/503 [00:28<04:28,  1.73it/s]  8%|▊         | 39/503 [00:28<03:45,  2.06it/s]  8%|▊         | 40/503 [00:30<08:12,  1.06s/it]  8%|▊         | 41/503 [00:31<06:26,  1.19it/s]  8%|▊         | 42/503 [00:31<05:12,  1.47it/s]  9%|▊         | 43/503 [00:31<04:20,  1.76it/s]  9%|▊         | 44/503 [00:34<08:32,  1.12s/it]  9%|▉         | 45/503 [00:34<06:42,  1.14it/s]  9%|▉         | 46/503 [00:34<05:22,  1.42it/s]  9%|▉         | 47/503 [00:35<04:28,  1.70it/s] 10%|▉         | 48/503 [00:37<08:40,  1.14s/it] 10%|▉         | 49/503 [00:37<06:45,  1.12it/s] 10%|▉         | 50/503 [00:38<05:25,  1.39it/s] 10%|█         | 51/503 [00:38<04:27,  1.69it/s] 10%|█         | 52/503 [00:40<08:33,  1.14s/it] 11%|█         | 56/503 [00:42<05:07,  1.46it/s] 11%|█▏        | 57/503 [00:42<04:34,  1.62it/s] 12%|█▏        | 58/503 [00:43<04:03,  1.83it/s] 12%|█▏        | 59/503 [00:43<03:36,  2.05it/s] 12%|█▏        | 60/503 [00:45<07:10,  1.03it/s] 12%|█▏        | 61/503 [00:46<05:51,  1.26it/s] 12%|█▏        | 62/503 [00:46<04:50,  1.52it/s] 13%|█▎        | 63/503 [00:46<04:04,  1.80it/s] 13%|█▎        | 64/503 [00:49<07:53,  1.08s/it] 13%|█▎        | 65/503 [00:49<06:14,  1.17it/s] 13%|█▎        | 66/503 [00:49<05:04,  1.43it/s] 13%|█▎        | 67/503 [00:50<04:14,  1.71it/s] 14%|█▎        | 68/503 [00:52<08:17,  1.14s/it] 14%|█▎        | 69/503 [00:52<06:26,  1.12it/s] 14%|█▍        | 70/503 [00:53<05:11,  1.39it/s] 14%|█▍        | 71/503 [00:53<04:18,  1.67it/s] 14%|█▍        | 72/503 [00:55<08:10,  1.14s/it] 15%|█▍        | 73/503 [00:56<06:22,  1.12it/s] 15%|█▍        | 74/503 [00:56<05:10,  1.38it/s] 15%|█▍        | 75/503 [00:56<04:18,  1.66it/s] 15%|█▌        | 76/503 [00:59<08:09,  1.15s/it] 15%|█▌        | 77/503 [00:59<06:20,  1.12it/s] 16%|█▌        | 78/503 [00:59<05:03,  1.40it/s] 16%|█▌        | 79/503 [01:00<04:06,  1.72it/s] 16%|█▌        | 80/503 [01:02<07:58,  1.13s/it] 16%|█▌        | 81/503 [01:02<06:13,  1.13it/s] 16%|█▋        | 82/503 [01:03<04:58,  1.41it/s] 17%|█▋        | 83/503 [01:03<04:03,  1.72it/s] 17%|█▋        | 84/503 [01:05<07:54,  1.13s/it] 17%|█▋        | 85/503 [01:06<06:08,  1.13it/s] 17%|█▋        | 86/503 [01:06<04:57,  1.40it/s] 17%|█▋        | 87/503 [01:06<04:09,  1.67it/s] 17%|█▋        | 88/503 [01:09<07:53,  1.14s/it] 18%|█▊        | 89/503 [01:09<06:10,  1.12it/s] 18%|█▊        | 90/503 [01:09<05:02,  1.37it/s] 18%|█▊        | 91/503 [01:10<04:07,  1.66it/s] 18%|█▊        | 92/503 [01:11<04:28,  1.53it/s] 18%|█▊        | 93/503 [01:11<03:47,  1.80it/s] 19%|█▊        | 94/503 [01:11<03:17,  2.07it/s] 19%|█▉        | 95/503 [01:12<02:55,  2.33it/s] 19%|█▉        | 96/503 [01:14<07:04,  1.04s/it] 19%|█▉        | 97/503 [01:14<05:32,  1.22it/s] 19%|█▉        | 98/503 [01:15<04:30,  1.50it/s] 20%|█▉        | 99/503 [01:15<03:44,  1.80it/s] 20%|█▉        | 100/503 [01:17<07:31,  1.12s/it] 20%|██        | 101/503 [01:18<05:51,  1.14it/s] 20%|██        | 102/503 [01:18<04:43,  1.41it/s] 20%|██        | 103/503 [01:18<03:55,  1.70it/s] 21%|██        | 104/503 [01:21<07:33,  1.14s/it] 21%|██        | 105/503 [01:21<05:52,  1.13it/s] 21%|██        | 106/503 [01:21<04:42,  1.41it/s] 21%|██▏       | 107/503 [01:22<03:51,  1.71it/s] 21%|██▏       | 108/503 [01:22<03:13,  2.04it/s] 22%|██▏       | 109/503 [01:24<06:35,  1.00s/it] 22%|██▏       | 110/503 [01:24<05:14,  1.25it/s] 22%|██▏       | 111/503 [01:25<04:20,  1.51it/s] 22%|██▏       | 112/503 [01:27<07:48,  1.20s/it] 22%|██▏       | 113/503 [01:27<06:00,  1.08it/s] 23%|██▎       | 114/503 [01:28<04:48,  1.35it/s] 23%|██▎       | 115/503 [01:28<03:59,  1.62it/s] 23%|██▎       | 116/503 [01:28<03:24,  1.89it/s] 23%|██▎       | 117/503 [01:31<07:01,  1.09s/it] 23%|██▎       | 118/503 [01:31<05:32,  1.16it/s] 24%|██▎       | 119/503 [01:31<04:27,  1.44it/s] 24%|██▍       | 120/503 [01:32<03:40,  1.74it/s] 24%|██▍       | 121/503 [01:34<07:00,  1.10s/it] 24%|██▍       | 122/503 [01:34<05:29,  1.16it/s] 24%|██▍       | 123/503 [01:35<04:26,  1.43it/s] 25%|██▍       | 124/503 [01:35<03:38,  1.73it/s] 25%|██▍       | 125/503 [01:37<07:16,  1.16s/it] 25%|██▌       | 126/503 [01:38<05:39,  1.11it/s] 25%|██▌       | 127/503 [01:38<04:32,  1.38it/s] 25%|██▌       | 128/503 [01:38<03:42,  1.68it/s] 26%|██▌       | 129/503 [01:41<06:42,  1.08s/it] 26%|██▌       | 130/503 [01:41<05:16,  1.18it/s] 26%|██▌       | 131/503 [01:41<04:14,  1.46it/s] 26%|██▌       | 132/503 [01:41<03:28,  1.78it/s] 26%|██▋       | 133/503 [01:42<03:43,  1.65it/s] 27%|██▋       | 134/503 [01:43<03:10,  1.93it/s] 27%|██▋       | 135/503 [01:43<02:48,  2.18it/s] 27%|██▋       | 136/503 [01:43<02:32,  2.41it/s] 27%|██▋       | 137/503 [01:46<06:12,  1.02s/it] 27%|██▋       | 138/503 [01:46<04:55,  1.23it/s] 28%|██▊       | 139/503 [01:46<04:02,  1.50it/s] 28%|██▊       | 140/503 [01:47<03:24,  1.77it/s] 28%|██▊       | 141/503 [01:49<06:48,  1.13s/it] 28%|██▊       | 142/503 [01:49<05:18,  1.13it/s] 28%|██▊       | 143/503 [01:50<04:15,  1.41it/s] 29%|██▊       | 144/503 [01:50<03:31,  1.70it/s] 29%|██▉       | 145/503 [01:52<06:40,  1.12s/it] 29%|██▉       | 146/503 [01:53<05:12,  1.14it/s] 29%|██▉       | 147/503 [01:53<04:12,  1.41it/s] 29%|██▉       | 148/503 [01:53<03:25,  1.73it/s] 30%|██▉       | 149/503 [01:56<06:41,  1.13s/it] 30%|██▉       | 150/503 [01:56<05:11,  1.13it/s] 30%|███       | 151/503 [01:56<04:10,  1.41it/s] 30%|███       | 152/503 [01:56<03:23,  1.73it/s] 30%|███       | 153/503 [01:59<06:29,  1.11s/it] 31%|███       | 154/503 [01:59<05:04,  1.14it/s] 31%|███       | 155/503 [01:59<04:06,  1.41it/s] 31%|███       | 156/503 [02:00<03:27,  1.67it/s] 31%|███       | 157/503 [02:02<06:37,  1.15s/it] 31%|███▏      | 158/503 [02:03<05:09,  1.12it/s] 32%|███▏      | 159/503 [02:03<04:10,  1.37it/s] 32%|███▏      | 160/503 [02:05<07:00,  1.23s/it] 32%|███▏      | 161/503 [02:06<05:25,  1.05it/s] 32%|███▏      | 162/503 [02:06<04:18,  1.32it/s] 32%|███▏      | 163/503 [02:06<03:31,  1.60it/s] 33%|███▎      | 164/503 [02:09<06:37,  1.17s/it] 33%|███▎      | 165/503 [02:09<05:07,  1.10it/s] 33%|███▎      | 166/503 [02:09<04:04,  1.38it/s] 33%|███▎      | 167/503 [02:10<03:20,  1.68it/s] 33%|███▎      | 168/503 [02:10<02:49,  1.97it/s] 34%|███▎      | 169/503 [02:12<06:00,  1.08s/it] 34%|███▍      | 170/503 [02:13<04:41,  1.18it/s] 34%|███▍      | 171/503 [02:13<03:44,  1.48it/s] 34%|███▍      | 172/503 [02:13<03:05,  1.79it/s] 34%|███▍      | 173/503 [02:14<03:24,  1.62it/s] 35%|███▍      | 174/503 [02:14<02:52,  1.91it/s] 35%|███▍      | 175/503 [02:15<02:31,  2.17it/s] 35%|███▍      | 176/503 [02:15<02:16,  2.39it/s] 35%|███▌      | 177/503 [02:17<05:30,  1.02s/it] 35%|███▌      | 178/503 [02:18<04:22,  1.24it/s] 36%|███▌      | 179/503 [02:18<03:33,  1.52it/s] 36%|███▌      | 180/503 [02:18<02:57,  1.81it/s] 36%|███▌      | 181/503 [02:21<06:01,  1.12s/it] 36%|███▌      | 182/503 [02:21<04:41,  1.14it/s] 36%|███▋      | 183/503 [02:21<03:46,  1.41it/s] 37%|███▋      | 184/503 [02:22<03:06,  1.71it/s] 37%|███▋      | 185/503 [02:24<06:02,  1.14s/it] 37%|███▋      | 186/503 [02:24<04:42,  1.12it/s] 37%|███▋      | 187/503 [02:25<03:43,  1.41it/s] 37%|███▋      | 188/503 [02:25<03:04,  1.71it/s] 38%|███▊      | 189/503 [02:27<06:02,  1.15s/it] 38%|███▊      | 190/503 [02:28<04:42,  1.11it/s] 38%|███▊      | 191/503 [02:28<03:42,  1.40it/s] 38%|███▊      | 192/503 [02:28<02:59,  1.73it/s] 38%|███▊      | 193/503 [02:30<05:36,  1.09s/it] 39%|███▊      | 194/503 [02:31<04:23,  1.17it/s] 39%|███▉      | 195/503 [02:31<03:29,  1.47it/s] 39%|███▉      | 196/503 [02:31<02:53,  1.77it/s] 39%|███▉      | 197/503 [02:32<02:28,  2.06it/s] 39%|███▉      | 198/503 [02:34<05:28,  1.08s/it] 40%|███▉      | 199/503 [02:34<04:18,  1.18it/s] 40%|███▉      | 200/503 [02:35<03:33,  1.42it/s] 40%|███▉      | 201/503 [02:37<06:22,  1.27s/it] 40%|████      | 202/503 [02:38<04:56,  1.02it/s] 40%|████      | 203/503 [02:38<03:56,  1.27it/s] 41%|████      | 204/503 [02:38<03:13,  1.54it/s] 41%|████      | 205/503 [02:41<05:54,  1.19s/it] 41%|████      | 206/503 [02:41<04:35,  1.08it/s] 41%|████      | 207/503 [02:41<03:41,  1.34it/s] 41%|████▏     | 208/503 [02:42<02:59,  1.64it/s] 42%|████▏     | 209/503 [02:44<05:40,  1.16s/it] 42%|████▏     | 213/503 [02:46<03:22,  1.43it/s] 43%|████▎     | 214/503 [02:46<03:01,  1.60it/s] 43%|████▎     | 215/503 [02:47<02:40,  1.80it/s] 43%|████▎     | 216/503 [02:47<02:21,  2.02it/s] 43%|████▎     | 217/503 [02:49<04:35,  1.04it/s] 43%|████▎     | 218/503 [02:49<03:44,  1.27it/s] 44%|████▎     | 219/503 [02:50<03:06,  1.53it/s] 44%|████▎     | 220/503 [02:50<02:38,  1.79it/s] 44%|████▍     | 221/503 [02:53<05:13,  1.11s/it] 44%|████▍     | 222/503 [02:53<04:04,  1.15it/s] 44%|████▍     | 223/503 [02:53<03:18,  1.41it/s] 45%|████▍     | 224/503 [02:53<02:46,  1.68it/s] 45%|████▍     | 225/503 [02:56<05:19,  1.15s/it] 45%|████▍     | 226/503 [02:56<04:08,  1.11it/s] 45%|████▌     | 227/503 [02:57<03:21,  1.37it/s] 45%|████▌     | 228/503 [02:57<02:47,  1.65it/s] 46%|████▌     | 229/503 [02:59<05:14,  1.15s/it] 46%|████▌     | 230/503 [03:00<04:04,  1.12it/s] 46%|████▌     | 231/503 [03:00<03:14,  1.40it/s] 46%|████▌     | 232/503 [03:00<02:38,  1.71it/s] 46%|████▋     | 233/503 [03:03<05:08,  1.14s/it] 47%|████▋     | 234/503 [03:03<03:59,  1.12it/s] 47%|████▋     | 235/503 [03:03<03:10,  1.41it/s] 47%|████▋     | 236/503 [03:04<02:37,  1.70it/s] 47%|████▋     | 237/503 [03:06<05:00,  1.13s/it] 47%|████▋     | 238/503 [03:06<03:53,  1.13it/s] 48%|████▊     | 239/503 [03:07<03:09,  1.39it/s] 48%|████▊     | 240/503 [03:07<02:39,  1.65it/s] 48%|████▊     | 241/503 [03:09<05:06,  1.17s/it] 48%|████▊     | 242/503 [03:10<03:59,  1.09it/s] 48%|████▊     | 243/503 [03:10<03:12,  1.35it/s] 49%|████▊     | 244/503 [03:10<02:40,  1.61it/s] 49%|████▊     | 245/503 [03:13<04:57,  1.15s/it] 49%|████▉     | 246/503 [03:13<03:51,  1.11it/s] 49%|████▉     | 247/503 [03:13<03:03,  1.39it/s] 49%|████▉     | 248/503 [03:14<02:27,  1.72it/s] 50%|████▉     | 249/503 [03:14<02:29,  1.70it/s] 50%|████▉     | 250/503 [03:15<02:09,  1.96it/s] 50%|████▉     | 251/503 [03:15<01:54,  2.20it/s] 50%|█████     | 252/503 [03:15<01:43,  2.42it/s] 50%|█████     | 253/503 [03:18<04:10,  1.00s/it] 50%|█████     | 254/503 [03:18<03:16,  1.27it/s] 51%|█████     | 255/503 [03:18<02:39,  1.55it/s] 51%|█████     | 256/503 [03:19<02:13,  1.85it/s] 51%|█████     | 257/503 [03:19<01:52,  2.20it/s] 51%|█████▏    | 258/503 [03:21<04:11,  1.03s/it] 51%|█████▏    | 259/503 [03:21<03:17,  1.24it/s] 52%|█████▏    | 260/503 [03:22<02:39,  1.53it/s] 52%|█████▏    | 261/503 [03:22<02:11,  1.85it/s] 52%|█████▏    | 262/503 [03:24<04:21,  1.08s/it] 52%|█████▏    | 263/503 [03:25<03:24,  1.17it/s] 52%|█████▏    | 264/503 [03:25<02:44,  1.45it/s] 53%|█████▎    | 265/503 [03:25<02:16,  1.74it/s] 53%|█████▎    | 266/503 [03:27<04:09,  1.05s/it] 53%|█████▎    | 267/503 [03:28<03:15,  1.20it/s] 53%|█████▎    | 268/503 [03:28<02:38,  1.48it/s] 53%|█████▎    | 269/503 [03:28<02:12,  1.76it/s] 54%|█████▎    | 270/503 [03:31<04:19,  1.11s/it] 54%|█████▍    | 271/503 [03:31<03:22,  1.15it/s] 54%|█████▍    | 272/503 [03:31<02:43,  1.42it/s] 54%|█████▍    | 273/503 [03:32<02:13,  1.72it/s] 54%|█████▍    | 274/503 [03:34<04:15,  1.12s/it] 55%|█████▍    | 275/503 [03:34<03:18,  1.15it/s] 55%|█████▍    | 276/503 [03:35<02:38,  1.43it/s] 55%|█████▌    | 277/503 [03:35<02:10,  1.73it/s] 55%|█████▌    | 278/503 [03:37<04:19,  1.15s/it] 55%|█████▌    | 279/503 [03:38<03:20,  1.12it/s] 56%|█████▌    | 280/503 [03:38<02:39,  1.39it/s] 56%|█████▌    | 281/503 [03:38<02:11,  1.69it/s] 56%|█████▌    | 282/503 [03:39<01:51,  1.99it/s] 56%|█████▋    | 283/503 [03:41<03:54,  1.06s/it] 56%|█████▋    | 284/503 [03:41<03:02,  1.20it/s] 57%|█████▋    | 285/503 [03:42<02:27,  1.48it/s] 57%|█████▋    | 286/503 [03:42<02:02,  1.77it/s] 57%|█████▋    | 287/503 [03:44<03:58,  1.11s/it] 57%|█████▋    | 288/503 [03:45<03:06,  1.15it/s] 57%|█████▋    | 289/503 [03:45<02:28,  1.44it/s] 58%|█████▊    | 290/503 [03:45<02:03,  1.73it/s] 58%|█████▊    | 291/503 [03:46<02:18,  1.53it/s] 58%|█████▊    | 292/503 [03:46<01:55,  1.82it/s] 58%|█████▊    | 293/503 [03:47<01:39,  2.10it/s] 58%|█████▊    | 294/503 [03:47<01:28,  2.37it/s] 59%|█████▊    | 295/503 [03:49<03:35,  1.04s/it] 59%|█████▉    | 296/503 [03:50<02:48,  1.23it/s] 59%|█████▉    | 297/503 [03:50<02:15,  1.52it/s] 59%|█████▉    | 298/503 [03:50<01:52,  1.83it/s] 59%|█████▉    | 299/503 [03:53<03:40,  1.08s/it] 60%|█████▉    | 300/503 [03:53<02:51,  1.18it/s] 60%|█████▉    | 301/503 [03:53<02:17,  1.47it/s] 60%|██████    | 302/503 [03:54<01:53,  1.77it/s] 60%|██████    | 303/503 [03:56<03:37,  1.09s/it] 60%|██████    | 304/503 [03:56<02:49,  1.17it/s] 61%|██████    | 305/503 [03:56<02:14,  1.47it/s] 61%|██████    | 306/503 [03:57<01:50,  1.78it/s] 61%|██████    | 307/503 [03:59<03:38,  1.11s/it] 61%|██████    | 308/503 [03:59<02:49,  1.15it/s] 61%|██████▏   | 309/503 [04:00<02:16,  1.42it/s] 62%|██████▏   | 310/503 [04:00<01:53,  1.71it/s] 62%|██████▏   | 311/503 [04:02<03:39,  1.14s/it] 62%|██████▏   | 312/503 [04:03<02:49,  1.13it/s] 62%|██████▏   | 313/503 [04:03<02:15,  1.40it/s] 62%|██████▏   | 314/503 [04:03<01:52,  1.69it/s] 63%|██████▎   | 315/503 [04:06<03:35,  1.14s/it] 63%|██████▎   | 316/503 [04:06<02:46,  1.13it/s] 63%|██████▎   | 317/503 [04:06<02:12,  1.41it/s] 63%|██████▎   | 318/503 [04:07<01:48,  1.70it/s] 63%|██████▎   | 319/503 [04:07<01:30,  2.03it/s] 64%|██████▎   | 320/503 [04:09<03:14,  1.06s/it] 64%|██████▍   | 321/503 [04:10<02:31,  1.20it/s] 64%|██████▍   | 322/503 [04:10<02:01,  1.49it/s] 64%|██████▍   | 323/503 [04:10<01:39,  1.81it/s] 64%|██████▍   | 324/503 [04:13<03:14,  1.08s/it] 65%|██████▍   | 325/503 [04:13<02:30,  1.18it/s] 65%|██████▍   | 326/503 [04:13<02:00,  1.47it/s] 65%|██████▌   | 327/503 [04:13<01:39,  1.78it/s] 65%|██████▌   | 328/503 [04:16<03:02,  1.04s/it] 65%|██████▌   | 329/503 [04:16<02:21,  1.23it/s] 66%|██████▌   | 330/503 [04:16<01:51,  1.55it/s] 66%|██████▌   | 331/503 [04:16<01:31,  1.89it/s] 66%|██████▌   | 332/503 [04:17<01:21,  2.10it/s] 66%|██████▌   | 333/503 [04:17<01:12,  2.36it/s] 66%|██████▋   | 334/503 [04:17<01:05,  2.60it/s] 67%|██████▋   | 335/503 [04:18<01:00,  2.76it/s] 67%|██████▋   | 336/503 [04:20<02:47,  1.00s/it] 67%|██████▋   | 337/503 [04:20<02:11,  1.27it/s] 67%|██████▋   | 338/503 [04:21<01:46,  1.55it/s] 67%|██████▋   | 339/503 [04:21<01:28,  1.85it/s] 68%|██████▊   | 340/503 [04:21<01:16,  2.13it/s] 68%|██████▊   | 341/503 [04:24<02:50,  1.06s/it] 68%|██████▊   | 342/503 [04:24<02:13,  1.20it/s] 68%|██████▊   | 343/503 [04:24<01:47,  1.49it/s] 68%|██████▊   | 344/503 [04:25<01:27,  1.81it/s] 69%|██████▊   | 345/503 [04:27<02:53,  1.10s/it] 69%|██████▉   | 346/503 [04:27<02:14,  1.16it/s] 69%|██████▉   | 347/503 [04:28<01:46,  1.46it/s] 69%|██████▉   | 348/503 [04:28<01:27,  1.77it/s] 69%|██████▉   | 349/503 [04:30<02:52,  1.12s/it] 70%|██████▉   | 350/503 [04:31<02:12,  1.15it/s] 70%|██████▉   | 351/503 [04:31<01:45,  1.44it/s] 70%|██████▉   | 352/503 [04:31<01:26,  1.74it/s] 70%|███████   | 353/503 [04:31<01:13,  2.05it/s] 70%|███████   | 354/503 [04:34<02:37,  1.05s/it] 71%|███████   | 355/503 [04:34<02:02,  1.20it/s] 71%|███████   | 356/503 [04:34<01:38,  1.49it/s] 71%|███████   | 357/503 [04:35<01:22,  1.78it/s] 71%|███████   | 358/503 [04:37<02:50,  1.17s/it] 71%|███████▏  | 359/503 [04:38<02:11,  1.09it/s] 72%|███████▏  | 360/503 [04:38<01:44,  1.37it/s] 72%|███████▏  | 361/503 [04:38<01:25,  1.65it/s] 72%|███████▏  | 362/503 [04:41<02:45,  1.17s/it] 72%|███████▏  | 363/503 [04:41<02:08,  1.09it/s] 72%|███████▏  | 364/503 [04:41<01:41,  1.36it/s] 73%|███████▎  | 365/503 [04:42<01:22,  1.66it/s] 73%|███████▎  | 366/503 [04:44<02:37,  1.15s/it] 73%|███████▎  | 367/503 [04:44<02:01,  1.12it/s] 73%|███████▎  | 368/503 [04:45<01:36,  1.39it/s] 73%|███████▎  | 369/503 [04:45<01:18,  1.70it/s] 74%|███████▎  | 370/503 [04:47<02:33,  1.16s/it] 74%|███████▍  | 371/503 [04:48<01:58,  1.11it/s] 74%|███████▍  | 374/503 [04:49<01:18,  1.64it/s] 75%|███████▍  | 375/503 [04:49<01:09,  1.84it/s] 75%|███████▍  | 376/503 [04:49<01:01,  2.07it/s] 75%|███████▍  | 377/503 [04:50<00:54,  2.30it/s] 75%|███████▌  | 378/503 [04:50<00:48,  2.56it/s] 75%|███████▌  | 379/503 [04:52<01:47,  1.15it/s] 76%|███████▌  | 380/503 [04:52<01:27,  1.41it/s] 76%|███████▌  | 381/503 [04:53<01:11,  1.70it/s] 76%|███████▌  | 382/503 [04:53<00:59,  2.02it/s] 76%|███████▌  | 383/503 [04:53<00:52,  2.27it/s] 76%|███████▋  | 384/503 [04:54<00:47,  2.49it/s] 77%|███████▋  | 385/503 [04:54<00:46,  2.52it/s] 77%|███████▋  | 386/503 [04:54<00:45,  2.55it/s] 77%|███████▋  | 387/503 [04:55<00:45,  2.57it/s] 77%|███████▋  | 388/503 [04:55<00:45,  2.51it/s] 77%|███████▋  | 389/503 [04:56<00:45,  2.51it/s] 78%|███████▊  | 390/503 [04:56<00:45,  2.48it/s] 78%|███████▊  | 391/503 [04:56<00:43,  2.57it/s] 78%|███████▊  | 392/503 [04:57<00:42,  2.60it/s] 78%|███████▊  | 393/503 [04:57<00:41,  2.64it/s] 78%|███████▊  | 394/503 [04:57<00:36,  2.97it/s] 79%|███████▊  | 395/503 [04:58<00:33,  3.25it/s] 79%|███████▊  | 396/503 [04:58<00:30,  3.51it/s] 79%|███████▉  | 397/503 [04:58<00:28,  3.70it/s] 79%|███████▉  | 398/503 [04:58<00:27,  3.84it/s] 79%|███████▉  | 399/503 [04:59<00:26,  3.94it/s] 80%|███████▉  | 400/503 [04:59<00:25,  4.01it/s] 80%|███████▉  | 401/503 [04:59<00:25,  4.06it/s] 80%|███████▉  | 402/503 [04:59<00:24,  4.04it/s] 80%|████████  | 403/503 [05:00<00:25,  3.98it/s] 80%|████████  | 404/503 [05:00<00:24,  3.97it/s] 81%|████████  | 405/503 [05:00<00:24,  4.02it/s] 81%|████████  | 406/503 [05:00<00:23,  4.16it/s] 81%|████████  | 407/503 [05:00<00:22,  4.32it/s] 81%|████████  | 408/503 [05:01<00:21,  4.48it/s] 81%|████████▏ | 409/503 [05:01<00:20,  4.63it/s] 82%|████████▏ | 410/503 [05:01<00:19,  4.87it/s] 82%|████████▏ | 411/503 [05:01<00:17,  5.14it/s] 82%|████████▏ | 412/503 [05:01<00:17,  5.33it/s] 82%|████████▏ | 413/503 [05:02<00:16,  5.48it/s] 82%|████████▏ | 414/503 [05:02<00:15,  5.59it/s] 83%|████████▎ | 415/503 [05:02<00:15,  5.68it/s] 83%|████████▎ | 416/503 [05:02<00:15,  5.74it/s] 83%|████████▎ | 417/503 [05:02<00:14,  5.77it/s] 83%|████████▎ | 418/503 [05:02<00:14,  5.81it/s] 83%|████████▎ | 419/503 [05:03<00:14,  5.81it/s] 83%|████████▎ | 420/503 [05:03<00:14,  5.83it/s] 84%|████████▎ | 421/503 [05:03<00:14,  5.84it/s] 84%|████████▍ | 422/503 [05:03<00:13,  5.86it/s] 84%|████████▍ | 423/503 [05:03<00:13,  5.85it/s] 84%|████████▍ | 424/503 [05:03<00:13,  5.84it/s] 84%|████████▍ | 425/503 [05:04<00:13,  5.85it/s] 85%|████████▍ | 426/503 [05:04<00:13,  5.82it/s] 85%|████████▍ | 427/503 [05:04<00:13,  5.83it/s] 85%|████████▌ | 428/503 [05:04<00:12,  5.83it/s] 85%|████████▌ | 429/503 [05:04<00:12,  5.81it/s] 85%|████████▌ | 430/503 [05:04<00:12,  5.80it/s] 86%|████████▌ | 431/503 [05:05<00:12,  5.80it/s] 86%|████████▌ | 432/503 [05:05<00:12,  5.79it/s] 86%|████████▌ | 433/503 [05:05<00:12,  5.79it/s] 86%|████████▋ | 434/503 [05:05<00:12,  5.74it/s] 86%|████████▋ | 435/503 [05:05<00:11,  5.75it/s] 87%|████████▋ | 436/503 [05:06<00:11,  5.77it/s] 87%|████████▋ | 437/503 [05:06<00:11,  5.79it/s] 87%|████████▋ | 438/503 [05:06<00:11,  5.79it/s] 87%|████████▋ | 439/503 [05:06<00:11,  5.79it/s] 87%|████████▋ | 440/503 [05:06<00:10,  5.80it/s] 88%|████████▊ | 441/503 [05:06<00:10,  5.81it/s] 88%|████████▊ | 442/503 [05:07<00:10,  5.81it/s] 88%|████████▊ | 443/503 [05:07<00:10,  5.82it/s] 88%|████████▊ | 444/503 [05:07<00:10,  5.82it/s] 88%|████████▊ | 445/503 [05:07<00:09,  5.82it/s] 89%|████████▊ | 446/503 [05:07<00:10,  5.69it/s] 89%|████████▉ | 447/503 [05:07<00:09,  5.65it/s] 89%|████████▉ | 448/503 [05:08<00:09,  5.71it/s] 89%|████████▉ | 449/503 [05:08<00:09,  5.73it/s] 89%|████████▉ | 450/503 [05:08<00:09,  5.75it/s] 90%|████████▉ | 451/503 [05:08<00:09,  5.75it/s] 90%|████████▉ | 452/503 [05:08<00:08,  5.77it/s] 90%|█████████ | 453/503 [05:08<00:08,  5.78it/s] 90%|█████████ | 454/503 [05:09<00:08,  5.80it/s] 90%|█████████ | 455/503 [05:09<00:08,  5.80it/s] 91%|█████████ | 456/503 [05:09<00:08,  5.80it/s] 91%|█████████ | 457/503 [05:09<00:07,  5.77it/s] 91%|█████████ | 458/503 [05:09<00:07,  5.79it/s] 91%|█████████▏| 459/503 [05:09<00:07,  5.81it/s] 91%|█████████▏| 460/503 [05:10<00:07,  5.81it/s] 92%|█████████▏| 461/503 [05:10<00:07,  5.80it/s] 92%|█████████▏| 462/503 [05:10<00:07,  5.81it/s] 92%|█████████▏| 463/503 [05:10<00:06,  5.81it/s] 92%|█████████▏| 464/503 [05:10<00:06,  5.83it/s] 92%|█████████▏| 465/503 [05:11<00:06,  5.84it/s] 93%|█████████▎| 466/503 [05:11<00:06,  5.85it/s] 93%|█████████▎| 467/503 [05:11<00:06,  5.84it/s] 93%|█████████▎| 468/503 [05:11<00:06,  5.81it/s] 93%|█████████▎| 469/503 [05:11<00:05,  5.81it/s] 93%|█████████▎| 470/503 [05:11<00:05,  5.80it/s] 94%|█████████▎| 471/503 [05:12<00:05,  5.81it/s] 94%|█████████▍| 472/503 [05:12<00:05,  5.78it/s] 94%|█████████▍| 473/503 [05:12<00:05,  5.79it/s] 94%|█████████▍| 474/503 [05:12<00:04,  5.80it/s] 94%|█████████▍| 475/503 [05:12<00:04,  5.81it/s] 95%|█████████▍| 476/503 [05:12<00:04,  5.80it/s] 95%|█████████▍| 477/503 [05:13<00:04,  5.80it/s] 95%|█████████▌| 478/503 [05:13<00:04,  5.80it/s] 95%|█████████▌| 479/503 [05:13<00:04,  5.80it/s] 95%|█████████▌| 480/503 [05:13<00:03,  5.80it/s] 96%|█████████▌| 481/503 [05:13<00:03,  5.80it/s] 96%|█████████▌| 482/503 [05:13<00:03,  5.81it/s] 96%|█████████▌| 483/503 [05:14<00:03,  5.81it/s] 96%|█████████▌| 484/503 [05:14<00:03,  5.81it/s] 96%|█████████▋| 485/503 [05:14<00:03,  5.81it/s] 97%|█████████▋| 486/503 [05:14<00:02,  5.81it/s] 97%|█████████▋| 487/503 [05:14<00:02,  5.84it/s] 97%|█████████▋| 488/503 [05:14<00:02,  5.84it/s] 97%|█████████▋| 489/503 [05:15<00:02,  5.83it/s] 97%|█████████▋| 490/503 [05:15<00:02,  5.84it/s] 98%|█████████▊| 491/503 [05:15<00:02,  5.85it/s] 98%|█████████▊| 492/503 [05:15<00:01,  5.73it/s] 98%|█████████▊| 493/503 [05:15<00:01,  5.69it/s] 98%|█████████▊| 494/503 [05:16<00:01,  5.72it/s] 98%|█████████▊| 495/503 [05:16<00:01,  5.76it/s] 99%|█████████▊| 496/503 [05:16<00:01,  5.78it/s] 99%|█████████▉| 497/503 [05:16<00:01,  5.80it/s] 99%|█████████▉| 498/503 [05:16<00:00,  5.81it/s] 99%|█████████▉| 499/503 [05:16<00:00,  5.82it/s] 99%|█████████▉| 500/503 [05:17<00:00,  5.83it/s]100%|█████████▉| 501/503 [05:17<00:00,  5.83it/s]100%|█████████▉| 502/503 [05:17<00:00,  5.83it/s]100%|██████████| 503/503 [05:17<00:00,  5.84it/s]100%|██████████| 503/503 [05:17<00:00,  1.58it/s]
.steering/20260515-m9-c-adopt-retrain-v2-verdict\training-wsl.log:4489:{"base_model": "Qwen/Qwen3-8B", "batch_size": 1, "db_paths": ["/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_natural_run0.duckdb", "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_natural_run1.duckdb", "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_natural_run2.duckdb", "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_natural_run3.duckdb", "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_natural_run4.duckdb", "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_stimulus_run0.duckdb", "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_stimulus_run1.duckdb", "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_stimulus_run2.duckdb", "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_stimulus_run3.duckdb", "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_stimulus_run4.duckdb"], "eval_dialog_ids_n": 285, "eval_loss": 0.1802508682012558, "eval_split_size": 503, "gradient_accumulation_steps": 8, "learning_rate": 0.0002, "lora_rank": 8, "max_seq_length": 2048, "max_steps": 4000, "metadata": {"audit_de_en_mass": 0.48850351569210393, "audit_n_eff": 3886.3808333167804, "audit_top_5_pct": 0.13908401226837194, "seed": 42, "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"]}, "min_examples_threshold": 1000, "output_dir": "/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v2", "peak_vram_bytes": 10617952768, "persona_id": "kant", "quantization": "nf4", "realised_examples": 5022, "save_steps": 500, "shard_stats": [{"path": "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_natural_run0.duckdb", "persona_examples": 501, "raw_rows": 1507}, {"path": "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_natural_run1.duckdb", "persona_examples": 500, "raw_rows": 1504}, {"path": "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_natural_run2.duckdb", "persona_examples": 500, "raw_rows": 1480}, {"path": "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_natural_run3.duckdb", "persona_examples": 500, "raw_rows": 1497}, {"path": "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_natural_run4.duckdb", "persona_examples": 501, "raw_rows": 1513}, {"path": "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_stimulus_run0.duckdb", "persona_examples": 504, "raw_rows": 852}, {"path": "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_stimulus_run1.duckdb", "persona_examples": 504, "raw_rows": 852}, {"path": "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_stimulus_run2.duckdb", "persona_examples": 504, "raw_rows": 852}, {"path": "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_stimulus_run3.duckdb", "persona_examples": 504, "raw_rows": 852}, {"path": "/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_stimulus_run4.duckdb", "persona_examples": 504, "raw_rows": 852}], "synthetic_monolog_n": 500, "train_dialog_ids_n": 2562, "train_loss": 1.315564801454544, "training_executed": true, "weight_audit_path": "/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v2/weight-audit.json", "weighted": true}
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-icc-multiturn-kant-nolora.json:45:        "reverse_keyed_agreement": 0.8708333333333333,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:10:  "lang_confidence_threshold": 0.85,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:25:    "point": 114.60777995370626,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:26:    "lo": 113.65786098227092,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:28:    "width": 1.8998379428706471,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:45:      "mean_burrows": 114.39976319570022,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:68:        70.96650407237394,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:76:        109.6199205556535,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:87:        137.36247041497543,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:89:        148.9530895704406,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:126:        77.65167015851428,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:127:        137.36247041497543,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:135:        70.96650407237394,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:137:        113.76706980835418,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:148:        168.18116137030074,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:154:        78.95270346236832,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:166:        113.76706980835418,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:193:        100.18028784704175,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:196:        150.36897037877327,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:202:        105.7944317701046,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:207:        85.25104555009233,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:224:        114.6302289414709,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:235:        92.7267055070101,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:253:        103.02704359764857,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:269:        70.96650407237394,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:272:        113.76706980835418,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:274:        133.09029967003835,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:288:        78.95270346236832,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:323:        93.13708970067599,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:336:        104.47647703154296,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:342:        104.04559376080564,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:347:        95.87054311969109,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:354:        78.95270346236832,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:363:        70.96650407237394,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:365:        113.76706980835418,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:380:      "mean_burrows": 111.33662708471356,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:397:        128.61550447028785,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:399:        128.01710709524895,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:400:        121.75895456701652,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:402:        70.96650407237394,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:403:        86.66870923046703,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:416:        131.25558343609703,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:425:        79.31135160970251,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:426:        121.75895456701652,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-r8-burrows.json:431:        77.65167015851428,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-vendi-semantic.json:51:      "spectrum_entropy": 3.4991687052379135
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:10:  "lang_confidence_threshold": 0.85,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:54:        168.18116137030074,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:56:        106.57092035512827,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:57:        126.12214307038542,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:66:        114.70171643768263,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:72:        74.88002475787091,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:79:        88.92670985600799,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:82:        143.17056881969066,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:84:        105.20818729337024,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:87:        137.36247041497543,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:89:        104.7046793791524,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:90:        128.61550447028785,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:98:        113.76706980835418,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:133:        121.75895456701652,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:151:        108.35593795070106,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:189:        168.18116137030074,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:195:        125.04591018048262,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:198:        150.66217704192462,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:205:        130.06251461187705,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:220:        100.18028784704175,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:230:        70.96650407237394,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:249:        107.67031322574034,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:256:        168.18116137030074,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:260:        106.59234210708743,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:263:        114.41115073164707,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:273:        113.76706980835418,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:276:        70.96650407237394,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:282:        110.97097002411978,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:290:        78.95270346236832,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:293:        128.61550447028785,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:298:        70.96650407237394,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:301:        109.58097702006035,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:322:        170.14269514878114,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:325:        142.57025560785615,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:330:        78.95270346236832,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:335:        121.75895456701652,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:337:        104.47647703154296,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:338:        70.96650407237394,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:341:        113.76706980835418,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:346:        118.5870406332183,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:358:        114.03302301270402,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:360:        148.9530895704406,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:362:        150.66217704192462,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:394:        117.76591703387146,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:408:        104.47947031966896,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:413:        81.32365181377048,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:418:        129.70734728297322,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:426:        169.42597704037445,
.steering/20260515-m9-c-adopt-retrain-v2-verdict\matrix-inputs\tier-b-pilot-multiturn-kant-nolora-burrows.json:437:        109.58097702006035,

codex
The shard protocol checks out: the Plan B logs show `turn-count=300`, `cycle-count=6`, `multi-turn-max=6`, two LoRA-on runs and two no-LoRA runs, each with 300 focal turns; validation JSONs pass for all four shards. I’m running the 4-stage pre-push parity check now.
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command ".\\scripts\\dev\\pre-push-check.ps1" in C:\ERRE-Sand_Box
2026-05-16T16:06:06.627874Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.9 seconds
Output:

==[ ruff format --check src tests ]==
  [FAIL] ruff format --check src tests (exit=1, 0.1s)

==[ ruff check src tests ]==
  [FAIL] ruff check src tests (exit=1, 0.1s)

==[ mypy src ]==
  [FAIL] mypy src (exit=1, 0.0s)

==[ pytest -q (non-godot) ]==
  [FAIL] pytest -q (non-godot) (exit=4, 0.2s)

==[ 4 CHECK(S) FAILED (0.5s total) ]==
DO NOT push. Fix the failures above and re-run.
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\ERRE-Sand_Box\.venv\Lib\site-packages\ruff\__main__.py", line 27, in <module>
  File "C:\ERRE-Sand_Box\.venv\Lib\site-packages\ruff\__main__.py", line 17, in _run
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 548, in run
    with Popen(*popenargs, **kwargs) as process:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 1026, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 1538, in _execute_child
    hp, ht, pid, tid = _winapi.CreateProcess(executable, args,
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [WinError 5] アクセスが拒否されました。
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\ERRE-Sand_Box\.venv\Lib\site-packages\ruff\__main__.py", line 27, in <module>
  File "C:\ERRE-Sand_Box\.venv\Lib\site-packages\ruff\__main__.py", line 17, in _run
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 548, in run
    with Popen(*popenargs, **kwargs) as process:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 1026, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 1538, in _execute_child
    hp, ht, pid, tid = _winapi.CreateProcess(executable, args,
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [WinError 5] アクセスが拒否されました。
C:\ERRE-Sand_Box\.venv\Scripts\python.exe: Error while finding module specification for 'mypy.__main__' (ImportError: DLL load failed while importing mypy: アクセスが拒否されました。)
ImportError while loading conftest 'C:\ERRE-Sand_Box\tests\conftest.py'.
tests\conftest.py:16: in <module>
    from erre_sandbox.schemas import (
src\erre_sandbox\__init__.py:10: in <module>
    from erre_sandbox.schemas import (
src\erre_sandbox\schemas.py:38: in <module>
    from pydantic import BaseModel, ConfigDict, Field
.venv\Lib\site-packages\pydantic\__init__.py:5: in <module>
    ???
.venv\Lib\site-packages\pydantic\_migration.py:4: in <module>
    ???
.venv\Lib\site-packages\pydantic\warnings.py:5: in <module>
    ???
.venv\Lib\site-packages\pydantic\version.py:7: in <module>
    ???
.venv\Lib\site-packages\pydantic_core\__init__.py:8: in <module>
    ???
E   ImportError: DLL load failed while importing _pydantic_core: アクセスが拒否されました。

 exited 1 in 876ms:

==[ ruff format --check src tests ]==
  [FAIL] ruff format --check src tests (exit=1, 0.1s)

==[ ruff check src tests ]==
  [FAIL] ruff check src tests (exit=1, 0.1s)

==[ mypy src ]==
  [FAIL] mypy src (exit=1, 0.0s)

==[ pytest -q (non-godot) ]==
  [FAIL] pytest -q (non-godot) (exit=4, 0.2s)

==[ 4 CHECK(S) FAILED (0.5s total) ]==
DO NOT push. Fix the failures above and re-run.
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\ERRE-Sand_Box\.venv\Lib\site-packages\ruff\__main__.py", line 27, in <module>
  File "C:\ERRE-Sand_Box\.venv\Lib\site-packages\ruff\__main__.py", line 17, in _run
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 548, in run
    with Popen(*popenargs, **kwargs) as process:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 1026, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 1538, in _execute_child
    hp, ht, pid, tid = _winapi.CreateProcess(executable, args,
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [WinError 5] アクセスが拒否されました。
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\ERRE-Sand_Box\.venv\Lib\site-packages\ruff\__main__.py", line 27, in <module>
  File "C:\ERRE-Sand_Box\.venv\Lib\site-packages\ruff\__main__.py", line 17, in _run
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 548, in run
    with Popen(*popenargs, **kwargs) as process:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 1026, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "C:\Users\johnd\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\subprocess.py", line 1538, in _execute_child
    hp, ht, pid, tid = _winapi.CreateProcess(executable, args,
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [WinError 5] アクセスが拒否されました。
C:\ERRE-Sand_Box\.venv\Scripts\python.exe: Error while finding module specification for 'mypy.__main__' (ImportError: DLL load failed while importing mypy: アクセスが拒否されました。)
ImportError while loading conftest 'C:\ERRE-Sand_Box\tests\conftest.py'.
tests\conftest.py:16: in <module>
    from erre_sandbox.schemas import (
src\erre_sandbox\__init__.py:10: in <module>
    from erre_sandbox.schemas import (
src\erre_sandbox\schemas.py:38: in <module>
    from pydantic import BaseModel, ConfigDict, Field
.venv\Lib\site-packages\pydantic\__init__.py:5: in <module>
    ???
.venv\Lib\site-packages\pydantic\_migration.py:4: in <module>
    ???
.venv\Lib\site-packages\pydantic\warnings.py:5: in <module>
    ???
.venv\Lib\site-packages\pydantic\version.py:7: in <module>
    ???
.venv\Lib\site-packages\pydantic_core\__init__.py:8: in <module>
    ???
E   ImportError: DLL load failed while importing _pydantic_core: アクセスが拒否されました。

hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "def _per_encoder_summary|d2_revision_match|d2_library_match|all_three_axes_pass|def _encoder_agreement_axis|primary_count_required|natural_ds|all_negative|def _aggregate_verdict" scripts/m9-c-adopt/da14_verdict_plan_b.py' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "library_versions|relevant_keys|library_versions_match|sklearn|sentence_transformers" scripts/m9-c-adopt/rescore_vendi_alt_kernel.py .steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"set -uo|set -euo|step\\(|step \\\"|POST-EVAL PIPELINE COMPLETE|cat \\\"\\"'$TASK" scripts/m9-c-adopt/run_plan_b_post_eval.sh' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "--turn-count 300 --cycle-count 6 --multi-turn-max 6|--no-lora-control|--adapter-name|--max-loras-per-batch|--max-lora-rank|--lora-paths|--model" scripts/m9-c-adopt/run_plan_b_eval_sequence.sh scripts/m9-c-adopt/launch_sglang_plan_b.sh scripts/m9-c-adopt/tier_b_pilot.py .steering/20260515-m9-c-adopt-retrain-v2-verdict/decisions.md .steering/20260515-m9-c-adopt-retrain-v2-verdict/pilot_run0.log .steering/20260515-m9-c-adopt-retrain-v2-verdict/pilot_run1.log' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "v2_valid|nolora_valid|throughput_pct|_shard_focal_rate_from_log|v2_rates|nolora_rates" scripts/m9-c-adopt/aggregate_plan_b_axes.py' in C:\ERRE-Sand_Box
 succeeded in 300ms:
95:def _per_encoder_summary(
128:        "d2_revision_match": revision_match,
129:        "d2_library_match": library_match,
137:        "all_three_axes_pass": all_axes_pass,
145:def _encoder_agreement_axis(per_encoder: list[dict[str, Any]]) -> dict[str, Any]:
157:    n_primary_pass = sum(1 for e in primaries if e["all_three_axes_pass"])
161:    natural_ds = [
165:    all_negative = bool(natural_ds) and all(d < 0 for d in natural_ds)
166:    direction_pass = all_negative
173:        "primary_count_required": 2,
174:        "direction_all_negative": all_negative,
177:            e["encoder"] for e in primaries if e["all_three_axes_pass"]
226:def _aggregate_verdict(
284:            f"{'**YES**' if enc['all_three_axes_pass'] else 'no'} |",
293:        f"(required ≥ {ea['primary_count_required']})",
297:        f"**{ea['direction_all_negative']}**",

2026-05-16T16:06:30.467805Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.3 seconds
Output:
rg: unrecognized flag --turn-count 300 --cycle-count 6 --multi-turn-max 6|--no-lora-control|--adapter-name|--max-loras-per-batch|--max-lora-rank|--lora-paths|--model

 exited 1 in 343ms:
rg: unrecognized flag --turn-count 300 --cycle-count 6 --multi-turn-max 6|--no-lora-control|--adapter-name|--max-loras-per-batch|--max-lora-rank|--lora-paths|--model

 succeeded in 375ms:
11:* Throughput: derives `throughput_pct_of_baseline` from the per-shard
21:* ``--out-throughput``: ``{"throughput_pct_of_baseline": float}``
64:def _shard_focal_rate_from_log(log_path: Path, run_tag: str) -> float | None:
207:    v2_rates = [
208:        _shard_focal_rate_from_log(args.eval_log, f"tag=r8 run={i}")
211:    nolora_rates = [
212:        _shard_focal_rate_from_log(args.eval_log, f"tag=nolora run={i}")
215:    v2_valid = [r for r in v2_rates if r is not None]
216:    nolora_valid = [r for r in nolora_rates if r is not None]
217:    v2_rate = float(mean(v2_valid)) if v2_valid else float("nan")
218:    nolora_rate = float(mean(nolora_valid)) if nolora_valid else float("nan")
220:        throughput_pct = v2_rate / nolora_rate * 100.0
222:        throughput_pct = float("nan")
226:        "throughput_pct_of_baseline": throughput_pct,
227:        "v2_rates_per_shard": v2_rates,
228:        "no_lora_rates_per_shard": nolora_rates,
231:            "throughput_pct_of_baseline = v2 mean rate / no-LoRA mean rate"
244:        f"throughput_pct={throughput_pct:.2f}",

 succeeded in 394ms:
.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json:5:  "library_versions": {
.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json:6:    "sentence_transformers": "3.4.1",
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:147:    from sentence_transformers import (  # noqa: PLC0415
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:182:    from sklearn.feature_extraction.text import (  # noqa: PLC0415
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:635:    library_versions: dict[str, str] = {
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:639:        import sentence_transformers as _st  # noqa: PLC0415
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:641:        library_versions["sentence_transformers"] = _st.__version__
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:643:        import sklearn as _sk  # noqa: PLC0415
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:645:        library_versions["sklearn"] = _sk.__version__
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:646:    expected_lib = allowlist.get("library_versions", {})
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:648:    # sentence_transformers pin since the kernel is computed via sklearn
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:649:    # TF-IDF; the allowlist does not pin sklearn yet.
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:650:    relevant_keys = set(expected_lib).intersection(library_versions)
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:651:    library_versions_match = all(
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:652:        library_versions[k] == expected_lib[k] for k in relevant_keys
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:666:        "library_versions": library_versions,
scripts/m9-c-adopt/rescore_vendi_alt_kernel.py:667:        "library_versions_match_d2": library_versions_match,

2026-05-16T16:06:30.565428Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.4 seconds
Output:
POST-EVAL : 用語 'POST-EVAL' は、コマンドレット、関数、スクリプト ファイル、または操作可能なプログラムの名前として認識されません。名前が正しく記述されていることを確認し、パスが含まれている場合はそのパスが正しいこ
とを確認してから、再試行してください。
発生場所 行:2 文字:40
+ rg -n "set -uo|set -euo|step\(|step \"|POST-EVAL PIPELINE COMPLETE|ca ...
+                                        ~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (POST-EVAL:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
 

 exited 1 in 437ms:
POST-EVAL : 用語 'POST-EVAL' は、コマンドレット、関数、スクリプト ファイル、または操作可能なプログラムの名前として認識されません。名前が正しく記述されていることを確認し、パスが含まれている場合はそのパスが正しいこ
とを確認してから、再試行してください。
発生場所 行:2 文字:40
+ rg -n "set -uo|set -euo|step\(|step \"|POST-EVAL PIPELINE COMPLETE|ca ...
+                                        ~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (POST-EVAL:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
 


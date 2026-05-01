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
session id: 019de3f2-d3a9-7e23-a98b-e6f434816b55
--------
user
# Codex independent review — m9-eval-system P3a-decide v2 (cooldown × cognition_period)

> Codex `gpt-5.5 xhigh` independent review request. Prompt として
> `cat .steering/20260430-m9-eval-system/codex-review-prompt-natural-gating-v2.md
> | codex exec --skip-git-repo-check` で起動。
> 出力は `codex-review-natural-gating-v2.md` に verbatim 保存。本 review は
> v1 (`codex-review-natural-gating.md`、Verdict: ship) の **後続**で、v1 の
> fix がデプロイされた後の empirical observation で別の dominant gate が
> 露呈したため。

---

## Context

You previously reviewed and shipped a fix (Verdict: ship, HIGH=0/MEDIUM=0/
LOW=2) for m9-eval-system P3a natural-condition pilot stalling. The fix
added `InMemoryDialogScheduler.eval_natural_mode: bool = False` flag that
bypasses zone-equality and reflective-zone gates so 3 personas can
sustain dialog after LLM-driven `destination_zone` scatters them.

**The fix worked partially**. G-GEAR Phase A re-capture (PR #131) showed:

| 指標 | v1 修正前 | v1 期待 | v1 修正後 実測 |
|---|---|---|---|
| focal_rows (kant) | 6 | 30 | **6** |
| total_rows | 12 | ~90 | **18** |
| dialogs | 2 | ~10 | **3** |
| nietzsche admit | 0 (starved) | included | **2 dialogs** ✅ |
| wall | 13 min (kill) | 5-8 min | **10 min wall timeout** |

**Zone scatter (hypothesis D) is solved** — Nietzsche starve is gone,
all 3 pairs admit at least once. But all 18 turns happened in `tick=1..5`,
then **8 minutes of zero admits**.

## Re-activated dominant gate (hypothesis B from design v1)

design v1 §2 **rejected** hypothesis B with the rationale "world_tick 50+
in 13 min wall makes 30-tick cooldown < 30% of wall, so cooldown alone
can't explain stall." That premise was **wrong empirically**:

```
empirical: 600 s wall → max(world_tick) = 5 ⇒ 1 tick ≈ 120 s
root cause: qwen3:8b Q4_K_M on RTX 5060 Ti — reflection (embed + chat) +
            action selection (chat) + dialog turn (chat × 6) accumulate as
            serial round-trips, blocking cognition tick advance
effective cooldown: COOLDOWN_TICKS=30 × 120 s = 60 min wall
                   ⇒ within 10 min wall, same pair re-admit is physically
                     impossible
```

`g-gear-phase-a-failure.md` (PR #131) inter-turn delta confirms: 18
utterances clustered in ~95 s burst, then 8 min plateau with no admits
even though Reflection trigger logs show cognition is alive (Reflection
fires every ~30 s after burst — tick rate ~1/30 s during reflection-only
phase, but ~1/120 s during dialog phase).

## Candidate space (G-GEAR §4 + Mac /reimagine)

G-GEAR proposed 5 candidates. Mac added 3 reimagine alternatives (ζ/θ/ι).

| 案 | 内容 | 実装複雑度 | 概念純度 | empirical 必達 | test impact |
|---|---|---|---|---|---|
| α | eval mode で COOLDOWN_TICKS=5 | 低 | 中 | 高 | 低 |
| β | wall budget 30→60 min for natural | 低 (CLI default) | 高 | 中 | 無 |
| γ | AUTO_FIRE_PROB_PER_TICK=1.0 | 低 | 中 | 低 (cooldown dominant) | 中 |
| δ | 1 cell 逐次採取 | 低 | 中 | 低 (cognition_period 不変) | 無 |
| ε | dialog_turn_budget 6→3 | 中 | 低 (stylo signal 薄) | 中 | 中 |
| **ζ** *(reimagine)* | wall-time-based cooldown (`time.monotonic()`) | 中 | 高 | 高 | 中 |
| **θ** *(reimagine)* | cooldown 完全廃止 + prob のみ | 低 | 中 | 中 | 低 |
| **ι** *(reimagine)* | β+δ ハイブリッド (cooldown 不変、wall 大、cell 逐次) | 低 | **最高** | 中 (3h × 3 cell) | 無 |

## Proposed fix v2: α + β hybrid

### Adopted rationale

1. **empirical 必達確率が高い**: 60 min wall × cooldown=5 ticks ⇒ 30 ticks /
   5 ticks per cycle ≈ 5-6 cycle ⇒ focal kant ≈ 30 (target 達成)
2. **実装最小**: `COOLDOWN_TICKS_EVAL: ClassVar[int] = 5` 別定数化 +
   `_effective_cooldown()` helper + CLI default 30→60 min の 3 箇所変更
3. **既存 test 完全互換**: live mode の `COOLDOWN_TICKS=30` 不変、既存 1248 PASS 維持
4. **ME-8 invariant 後退最小**: "cooldown active" → "cooldown active with
   eval-mode-specific reduced threshold" に文言更新するのみ、cooldown 概念自体は保持
5. **reimagine 代案で全敗**: ζ は M4 frozen Protocol 純粋関数性違反、θ は dominant
   gate 移転 (cooldown→prob)、ι は wall 12h × overnight × multi-run で運用コスト許容外

### Diff sketch

```python
# src/erre_sandbox/integration/dialog.py
class InMemoryDialogScheduler:
    COOLDOWN_TICKS: ClassVar[int] = 30  # live (unchanged)
    COOLDOWN_TICKS_EVAL: ClassVar[int] = 5  # NEW eval_natural_mode 限定

    def _effective_cooldown(self) -> int:
        return self.COOLDOWN_TICKS_EVAL if self.eval_natural_mode else self.COOLDOWN_TICKS

    # schedule_initiate (existing line ~200):
    if (
        last_close is not None
        and tick - last_close < self._effective_cooldown()  # was self.COOLDOWN_TICKS
        and not self.golden_baseline_mode
    ):
        return None

    # tick() (existing line ~337):
    if last_close is not None and world_tick - last_close < self._effective_cooldown():
        continue  # was self.COOLDOWN_TICKS
```

```python
# src/erre_sandbox/cli/eval_run_golden.py
# capture_natural の click option:
@click.option(
    "--wall-timeout-min",
    type=int,
    default=60,  # was 30
    help="Maximum wall-clock minutes for the natural capture phase.",
)
```

### Test plan (12→16 cases in test_dialog_eval_natural_mode.py)

1. **`test_eval_mode_uses_reduced_cooldown`**: eval_natural_mode=True で同一 pair が
   tick 5 後に再 admit 可能、tick 4 では reject
2. **`test_live_mode_cooldown_unchanged`**: eval_natural_mode=False で
   COOLDOWN_TICKS=30 が active、tick 29 で reject / tick 30 で admit
3. **`test_effective_cooldown_returns_correct_value`**: helper の純関数 contract
4. **`test_class_constants_unchanged`**: `COOLDOWN_TICKS == 30` /
   `COOLDOWN_TICKS_EVAL == 5` の sentinel test

CLI test に `--wall-timeout-min default=60` の 1 ケース追加。

### ME-8 ADR §invariant の partial-update

v1 ADR で「Cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
invariant は両 mode で active のまま」と書いた箇所を以下に Edit:

> **Cooldown (eval-mode 別 threshold = `COOLDOWN_TICKS_EVAL=5`、live は
> `COOLDOWN_TICKS=30`)** / probability / timeout / 自己 dialog reject /
> 二重 open reject の invariant は両 mode で active のまま — eval natural cadence
> は維持、proximity 制約のみ削除 + cooldown threshold を eval mode で reduce。

### 期待される empirical 値 (G-GEAR rerun)

```
60 min wall × 1 tick / 120 s = 30 ticks 進行
cooldown=5 ticks per cycle、prob 0.25 込みで実効 ~6 cycle  (G-GEAR 計算)
3 dialogs × 6 turns × 5 cycle ~= 90 utterance
focal kant per cell ≈ 90 / 3 = 30 ✓
```

ただし AUTO_FIRE_PROB_PER_TICK=0.25 の variance を加味した realistic estimate は:
```
1 cycle = 6 ticks (turn) + 5 ticks (cooldown) = 11 ticks/cycle
60 min wall × 30 ticks / 11 ticks per cycle ≈ 2.7 cycle
2.7 × 18 utt = 49 utterance/cell
focal kant per cell ≈ 16-30 (variance あり)
```

→ default=60 min は最低保証、不足なら 90/120 min に上げる。

## Specific questions to Codex

Please return findings in HIGH / MEDIUM / LOW format with file:line refs.
Particular concerns:

- **Q1**: §2.4 ι (β+δ ハイブリッド = cooldown semantics 不変 + 4h wall + 1 cell 逐次)
  を「wall 爆発」で棄却したが、ME-8 invariant 後退ゼロという観点で本当は ι が
  正解では？α+β は ME-8 ADR の invariant を後退させる semantic cost を払うが、
  ι は払わない。empirical wall コスト (12h × overnight) は許容外と判断したが、
  これは scoping bias で過剰に α+β に寄せていないか？
- **Q2**: `COOLDOWN_TICKS_EVAL=5` を hardcoded class const にしたが、CLI
  `--cooldown-ticks-eval N` で override 可能にすべきか？将来 cognition_period
  が変動した時の柔軟性 vs hardcoded sentinel test の robustness の trade-off。
- **Q3**: §5 リスク 2 で realistic estimate が focal=16-30 と margin が薄いと自己
  認定した。`--wall-timeout-min default=60` ではなく `default=90` にすべきか？
  90 min なら realistic 4 cycle = 72 utt = focal 24/cell が下限保証 (mean 30+)。
- **Q4**: ME-8 §invariant 文言の "active with reduced threshold" は v1 contract
  に対し silent な後退ではないか？v1 では "active" を厳格定義としていた可能性、
  本 v2 で文言を緩めるのは ADR re-open のままで OK か (新 ADR child 起票が必要か)。
- **Q5**: §3.3.3 で追加した 4 test のうち `test_class_constants_unchanged` は
  sentinel test として over-defensive ではないか？将来 COOLDOWN_TICKS_EVAL の
  empirical 再校正で値変更があった場合に false positive で test 落ちる。
- **Q6**: dialog_turn_budget=6 と reduced cooldown=5 の組合せで「close 直後 (tick T)
  → cooldown 抜け (tick T+5) → 即再 admit」が同 pair で連発する "ピンポン admit"
  が起こり得る。これは natural cadence の semantics 上問題ないか？dialog_turn_budget
  が同 pair 占有を最低 6 ticks 保証するので indirect には防がれるが、明示的な
  "minimum gap between dialogs of same pair" として cooldown=5 で意味的に十分か。
- **Q7**: §2 候補空間 で **γ (AUTO_FIRE_PROB_PER_TICK=1.0) を「cooldown が dominant
  gate のため効果限定」**と棄却したが、本 v2 で α+β に切り替えた後は **prob 0.25 の
  variance が新たな副次 dominant gate になる可能性**。realistic estimate の variance
  を抑えるため eval mode で prob=1.0 に上げる組合せ案 (= α+β+γ ハイブリッド) は
  考慮するべきでないか？
- **Q8**: design v1 では "Cooldown / probability / timeout は active のまま (natural
  cadence 保持)" を core invariant として claim したが、empirical で cognition_period
  120 s/tick が判明した今、cooldown=30 ticks の意味は live mode (cognition_period
  ~10 s/tick 想定) と eval mode で全く別物。**M4 frozen Protocol の "tick ベース
  cooldown" 抽象化自体が漏れている**のではないか (= ζ wall-time cooldown が本来正解
  だが overscoping で defer して良いか)。

## Files to consult (relative to repo root)

- `.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md` (本 design v2)
- `.steering/20260430-m9-eval-system/design-natural-gating-fix.md` (v1)
- `.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md` (PR #131 empirical report)
- `.steering/20260430-m9-eval-system/decisions.md` ME-8 ADR (v1)
- `.steering/20260430-m9-eval-system/codex-review-natural-gating.md` (v1 verdict)
- `src/erre_sandbox/integration/dialog.py` (修正対象、特に line 89-95 / 200-210 / 337)
- `src/erre_sandbox/cli/eval_run_golden.py` (`capture_natural` の click options)
- `tests/test_integration/test_dialog_eval_natural_mode.py` (12 既存 test、4 追加予定)

## Output format requested

```
## Verdict
[ship | revise | reject] — one-line summary

## HIGH (must fix before merge)
HIGH-1 ...  file:line + finding + recommendation

## MEDIUM (should consider)
MEDIUM-1 ...

## LOW (nice to have)
LOW-1 ...

## Answers to Q1-Q8
Q1: ...
Q2: ...
...
```

## Token budget reminder

`.codex/budget.json` daily=1M、本日 used=337,503 (~33%)。本 invocation は
per_invocation_max=200K 範囲内で完了させること。`gpt-5.5 xhigh` で。

hook: SessionStart
hook: SessionStart Completed
hook: UserPromptSubmit
hook: UserPromptSubmit Completed
codex
Using `$erre-workflow` for the review flow, plus `project-status` for repository orientation before I assess the proposed v2 design. I’ll read the local steering notes and target code, then return findings with concrete file/line refs.
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

exec
/bin/zsh -lc "sed -n '1,220p' .agents/skills/project-status/SKILL.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
---
name: project-status
description: >
  プロジェクトの現在の状態をリアルタイムで取得する。
  作業を始める前・コンテキストが分からなくなった時・進捗を確認したい時・
  最近の変更を把握したい時に使う。git 状態・最近のコミット・
  構築フェーズの進捗 (.steering/_setup-progress.md)・未対応 TODO・
  変更ファイル統計を一括で取得する。セッション開始時の状況把握にも使える。
---

# Project Status

このスキルは現在のプロジェクト状態を動的に取得します。

## 現在の git 状態

!`git status --short`

## 最近のコミット (10 件)

!`git log --oneline -10 2>/dev/null || echo "(no commits yet)"`

## 現在のブランチ

!`git branch --show-current`

## 構築フェーズ進捗

!`grep -E "^\- \[" .steering/_setup-progress.md 2>/dev/null | head -20 || echo "(progress file not found)"`

## 未対応 TODO の数

!`grep -r "TODO\|FIXME\|HACK\|XXX" src/ tests/ 2>/dev/null | wc -l`

## 変更ファイルの統計 (直近コミットとの差分)

!`git diff --stat HEAD 2>/dev/null || echo "(no HEAD yet)"`

## 最近変更されたファイル (24 時間以内)

!`find src/ tests/ -name "*.py" -newer .git/index -mtime -1 2>/dev/null | head -10`

## Skills ディレクトリ

!`ls .agents/skills/ 2>/dev/null || echo "(no skills yet)"`

## あなたのタスク

上記の動的データを分析し、以下を報告してください:

1. **現状サマリ** — 現在のフェーズと進捗を 1-2 行で
2. **進行中の作業** — 未コミットの変更や直近の変更ファイルから何が進んでいるか
3. **注意すべき点** — 多数の未コミット変更、TODO の偏り、進捗ファイルとの乖離など
4. **推奨される次のアクション** — 何を優先すべきか (setup フェーズであればどのコマンドを次に実行すべきか)

レポートは簡潔に。詳細は必要に応じてユーザーが追加で質問する。

codex
The workflow says no source edits are needed for this review, so I’m staying read-only. I’m checking the current branch/dirty state first so file refs and conclusions match the active workspace.
exec
/bin/zsh -lc 'git status --short' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
?? .steering/20260430-m9-eval-system/codex-review-prompt-natural-gating-v2.md
?? .steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md

exec
/bin/zsh -lc 'git branch --show-current' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
feature/m9-eval-p3a-decide-v2

exec
/bin/zsh -lc 'git diff --stat HEAD' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
exec
/bin/zsh -lc 'git log --oneline -10' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
491db4b docs(steering): m9-eval-p3a Phase A 失敗レポート (cooldown × cognition_period re-activation) (#131)
9b3bc87 fix(eval): m9-eval-system P3a-decide — natural gating fix + bootstrap_ci P5 prep (#130)
00ff121 feat(eval): m9-eval-system P3a Step 1-5 — eval_run_golden CLI + pilot 採取 (#129)
4b57a95 feat(eval): m9-eval-system P0-P2c — Tier 0 contract + Tier A 5 metric + golden battery + driver (#128)
ff29ca2 docs(steering): m9-b LoRA execution plan — v3 hybrid 確定 (codex review 反映 + 第 3 の道採用) (#127)
85e02ea docs(claude): canonicalize Codex collaboration workflow + add token budget guard (#126)
0fd6d7f docs(setup): migrate Phase 0-7 → 0-9 with Marketplace + Codex Bridge phases (#125)
e910855 chore(steering): add missing orchestrator-03.log to m9-a run-01-m9a (PR #120 follow-up) (#124)
59ab03f revert(godot): drop V3 pulse trace prints — diagnostic役目終了 (PR #121 revert) (#123)
b168fee docs(steering): m9-a v3/v4/v5-client live G-GEAR PASS — overall 6/6 (#122)

exec
/bin/zsh -lc 'rg -n "TODO|FIXME|HACK|XXX" src tests' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
src/erre_sandbox/world/tick.py:382:        # TODO(T14): the unbounded queue is a deliberate MVP trade-off
src/erre_sandbox/schemas.py:1020:    # TODO(m4-memory-semantic-layer): pin embedding dimensionality once the
tests/test_integration/_ws_helpers.py:16:# TODO(T20): promote _parse_envelope to a public name when we tidy up

codex
The branch has only two untracked steering files, including the v2 design under review; source and tests are clean relative to HEAD. I’m reading the v2 design against the shipped scheduler/CLI code and the v1 ADR now.
exec
/bin/zsh -lc 'wc -l .steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md .steering/20260430-m9-eval-system/design-natural-gating-fix.md .steering/20260430-m9-eval-system/g-gear-phase-a-failure.md .steering/20260430-m9-eval-system/decisions.md .steering/20260430-m9-eval-system/codex-review-natural-gating.md src/erre_sandbox/integration/dialog.py src/erre_sandbox/cli/eval_run_golden.py tests/test_integration/test_dialog_eval_natural_mode.py' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     301 .steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md
     235 .steering/20260430-m9-eval-system/design-natural-gating-fix.md
     132 .steering/20260430-m9-eval-system/g-gear-phase-a-failure.md
     439 .steering/20260430-m9-eval-system/decisions.md
    2705 .steering/20260430-m9-eval-system/codex-review-natural-gating.md
     450 src/erre_sandbox/integration/dialog.py
    1219 src/erre_sandbox/cli/eval_run_golden.py
     343 tests/test_integration/test_dialog_eval_natural_mode.py
    5824 total

exec
/bin/zsh -lc 'rg -n "''^#|''^##|COOLDOWN|AUTO_FIRE|wall-timeout|eval_natural|natural|ME-8|invariant|cooldown|prob|dialog_turn_budget|capture_natural|tick'"\\(|schedule_initiate\" .steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md .steering/20260430-m9-eval-system/design-natural-gating-fix.md .steering/20260430-m9-eval-system/g-gear-phase-a-failure.md .steering/20260430-m9-eval-system/decisions.md .steering/20260430-m9-eval-system/codex-review-natural-gating.md src/erre_sandbox/integration/dialog.py src/erre_sandbox/cli/eval_run_golden.py tests/test_integration/test_dialog_eval_natural_mode.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:1:# G-GEAR Phase A 失敗レポート — natural re-capture stalled (post-fix)
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:3:> 起草: G-GEAR セッション 2026-05-01 22:50 UTC+9 (kant_natural sanity run after PR #130 merge)
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:4:> 目的: Mac セッション (P3a-decide finalization) が ME-8 ADR を re-open
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:5:> + design-natural-gating-fix.md v2 起草するための実機計測 hand-off。
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:7:## 1. TL;DR
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:9:- **Phase A guard tripped** — `kant_natural` 単独 sanity で `focal=6 / total=18 / dialogs=3` (10 min wall timeout)。
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:12:- **未解決の gate** = `COOLDOWN_TICKS=30` × **実測 cognition_period ≈ 120 s/tick** → 実効 cooldown ≈ 60 min → 10 min wall 内で再 admit が物理的に不可能。
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:13:- design-natural-gating-fix.md §2 で **棄却された仮説 B (cooldown × cognition_period の wall 換算) を re-activate** すべき。前提値 `world_tick 50+ for 10 min wall` が empirical に成立しなかった。
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:15:## 2. 観測指標
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:17:### 2.1 採取結果 vs 期待値
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:27:### 2.2 dialog-by-dialog tick + wall span
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:37:### 2.3 inter-turn delta (順 18 turn の `created_at` 差分)
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:50:## 3. 仮説再評価
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:52:### 3.1 仮説 B re-activate (design-natural-gating-fix.md §2 で △ 補助 → ◎ 主因に格上げ)
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:54:- design 当時の前提: `nietzsche cognition_period=7s + DEFAULT_COGNITION_PERIOD_S=10s → world_tick 50+ in 13 min wall` → cooldown=30 ticks は OK ⇒ 棄却根拠
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:59:  3. burst 終了後は cognition+reflection だけだが、それでも Reflection trigger log の inter-arrival ~30 s ⇒ tick rate ~ 1 / 30 s が下限、cooldown 30 ticks = 15 min wall
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:61:### 3.2 仮説 C (`_close_timed_out` race) は依然棄却
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:63:- 全 dialog が 6 turn budget (= dialog_turn_budget) で正常 close、premature close ではない
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:66:### 3.3 仮説 D (zone scatter) は **fix で解決済**
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:69:- `eval_natural_mode=True` の zone-bypass が effective に動作 (ME-8 ADR の expected behaviour 一致)
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:71:## 4. Mac 側で要検討の選択肢
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:77:| **α** | `eval_natural_mode=True` 時に `COOLDOWN_TICKS` も縮める (例: 5 ticks) | natural cadence の概念が薄まる、ME-8 ADR §invariant の "cooldown active" を更新要 |
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:78:| **β** | wall budget を大幅拡張 (--wall-timeout-min 90 → 180+ for natural) | wall は伸びるが概念は綺麗。実測 120 s/tick × 30 cooldown = 60 min × ~3 cycle = 180 min 必要見込 |
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:79:| **γ** | `AUTO_FIRE_PROB_PER_TICK` を eval mode で 0.25 → 1.0 | per-pair admit 加速、ただし cooldown が dominant gate なら効果限定 |
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:81:| **ε** | dialog_turn_budget を 6 → 3 に縮めて burst 期間を短縮、cooldown 計算根拠を変える | dialog 内 turn 数が減る、Burrows/MATTR の per-dialog stylo signal が薄まる |
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:83:### 推奨判断材料
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:85:- **α (cooldown 縮小)** は最も直接的だが ME-8 ADR の "cooldown active" 文言と概念整合のため Codex review 推奨
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:87:- **α + β ハイブリッド** (eval mode で cooldown=5 + wall=60 min) が実用解の最有力候補
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:89:### Mac 側で確認すべき計算
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:92:- cooldown=5 ticks = 10 min × 0.083 cycle/min = **約 5 cycle 期待** = 5 × 3 dialogs × 6 turns = **90 utterance**
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:94:- → α (cooldown 5) + wall 60 min が最小実用組合せ
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:96:## 5. 保全状態
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:100:| `data/eval/pilot/kant_natural_run0.duckdb.tmp` | **保持** (staged-rename 失敗で .tmp 残存) | 524 KB |
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:101:| `data/eval/pilot/kant_natural_run0.log` | **保持** (httpx + cognition full log) | 33 KB |
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:102:| `data/eval/pilot/{nietzsche,rikyu}_natural_*.duckdb*` | **未生成** (Phase B 未起動) | — |
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:109:## 6. ME-8 ADR re-open 候補項目
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:111:decisions.md ME-8 §re-open 条件 の 3 項目目 "fix 後も admit が初動 burst で停止する場合" が **発火**。本レポートを根拠に Mac で:
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:113:1. ME-8 ADR §影響 / §re-open 条件 を partial-update (本セッション empirical data を引用)
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:115:3. design-natural-gating-fix.md v2 として代案比較を再実施
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:118:## 7. Hand-off チェックリスト (Mac セッション用)
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:121:- [ ] decisions.md ME-8 §re-open 条件発火を AD R partial-update
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:122:- [ ] design-natural-gating-fix.md v2 起草 (5.0 critical insight 級の re-evaluation: bias_p=0.2 の代わりに actual cognition_period が dominant)
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:124:- [ ] 実装 + 12 unit test 拡張 (cooldown 縮小 invariant 再定義 / wall 期待値 update)
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:128:## 8. 注記
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:132:- 本ブランチ `feature/m9-eval-p3a-natural-stalled-report` は本レポート 1 ファイル commit のみ。stimulus 既存データ更新なし、_summary.json 不更新。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:1:# M5/M6 natural runtime gating bug — design v2 (P3a-decide v2)
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:5:> 反映を一元化する。**design v1 (`design-natural-gating-fix.md`) の続編**:
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:6:> v1 は仮説 D (zone scatter) を解決したが、empirical で仮説 B (cooldown ×
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:10:## 1. v2 を起草する empirical 根拠
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:12:### 1.1 v1 fix 後の G-GEAR Phase A 観測 (PR #131)
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:23:**v1 で未解決**: 18 turn 全部が tick 1-5 内、tick=5 以降 8 min 0 admit (= cooldown 中)。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:25:### 1.2 dominant gate の empirical 確定
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:34:実効 cooldown = `COOLDOWN_TICKS=30` × 120 s/tick = **60 min wall**
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:37:### 1.3 design v1 §2 仮説 B の再評価
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:40:> kant_natural 13 min wall で nietzsche cognition_period=7s + WorldRuntime
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:48:## 2. 候補空間 (G-GEAR §4 の 5 案 + /reimagine 代案 3)
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:55:| α | eval mode で COOLDOWN_TICKS=5 (現状 30) | 低 | 中 | 高 (10 min wall × 5 ticks/cooldown 必要) | 低 |
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:56:| β | wall budget 30→60 min for natural | 低 (CLI flag default 変更) | 高 | 中 (cooldown=30 単独では 1 cycle のみ) | 無 |
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:57:| γ | AUTO_FIRE_PROB_PER_TICK 0.25→1.0 | 低 | 中 | 低 (cooldown が dominant gate のため効果限定) | 中 |
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:59:| ε | dialog_turn_budget 6→3 | 中 | 低 (per-dialog stylo signal が薄まる) | 中 | 中 |
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:60:| **ζ** *(reimagine)* | wall-time-based cooldown (`time.monotonic()`) | 中 (monotonic 経路 + monkeypatch test) | 高 (tick rate 変動に robust) | 高 | 中 |
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:61:| **θ** *(reimagine)* | cooldown 完全廃止 + AUTO_FIRE_PROB_PER_TICK のみ | 低 | 中 (prob が gate に) | 中 (prob 0.25 で variability 大) | 低 |
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:62:| **ι** *(reimagine)* | β + δ ハイブリッド (cooldown 不変、wall 大拡張、cell 逐次) | 低 | **最高** (cooldown semantics 不変) | 中 (3h × 3 cell = 9h、overnight) | 無 |
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:64:### 2.1 G-GEAR 推奨 α + β ハイブリッドの empirical 計算
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:68:cooldown=5 ticks × 120 s/tick = 10 min wall cooldown
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:69:30 ticks / 5 ticks per cycle ≈ 6 cycle (G-GEAR 計算 5 cycle、prob 0.25 込みで)
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:74:### 2.2 /reimagine 代案 ζ (wall-time cooldown) の検討
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:81:# schedule_initiate / tick で:
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:83:if last_close_wall is not None and (time.monotonic() - last_close_wall) < COOLDOWN_WALL_S:
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:89:   60 s/tick に半減しても cooldown semantics が崩れない。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:90:2. 「natural cadence 1 min = 1 dialog 開始」という人間直感と一致。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:95:   `monkeypatch time.monotonic` が全 cooldown test に必要 (現状 1228+ test の cooldown
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:98:3. CLAUDE.md "コードに既存パターンに従う" 原則違反 (cooldown は M4 から tick ベース)。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:99:4. eval mode 専用 → 別経路 if 分岐 → コード経路 fork、ME-8 invariant を二重定義することに。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:101:**評価**: ζ は overscoping。本タスクのターゲットは "natural pilot 30 focal を 60 min wall
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:103:解決すべきは empirical な cooldown semantics の再校正のみ。**棄却**。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:105:### 2.3 /reimagine 代案 θ (cooldown 完全廃止) の検討
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:109:# eval_natural_mode=True のとき cooldown check 全 bypass
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:110:if self.eval_natural_mode:
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:111:    pass  # cooldown チェック飛ばす
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:115:1. mental model 最小化 (cooldown 概念が無くなる)。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:116:2. AUTO_FIRE_PROB_PER_TICK=0.25 が唯一の cadence 制御 → tunable は 1 個のみ。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:119:1. **dominant gate が cooldown から prob に移転**するだけで、prob 0.25 の cognition_period
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:121:   30 達成の確実性が cooldown=5 案より低)。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:123:   AUTO_FIRE が当たれば即 admit、3 pair 全部が同 tick で同時に admit する "burst 多発"
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:124:   が起こり得る。dialog_turn_budget=6 で「同 pair が 6 tick 占有」されることで indirect に
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:126:3. ME-8 ADR §invariant の "cooldown active" を完全削除する必要、PR #130 で確定した
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:129:**評価**: cooldown 概念削除は ME-8 ADR の意味的後退。dominant gate を prob に移すだけで
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:132:### 2.4 /reimagine 代案 ι (β + δ) の検討
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:135:- α/cooldown 不変 (`COOLDOWN_TICKS=30` keep)
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:142:cooldown=30 → 4 cycle (cycle 間隔 30 ticks × 120 s = 60 min)
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:148:**利点**: cooldown semantics 不変、ME-8 §invariant は v1 のまま、test 影響ゼロ。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:152:   大きい。stimulus + natural の両建てで 12h × 5 run = 60h overnight が現実的でない。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:158:## 3. 採用案: α + β ハイブリッド
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:160:### 3.1 採用根拠
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:163:2. **実装最小**: `COOLDOWN_TICKS_EVAL: ClassVar[int] = 5` 別定数化 + `_effective_cooldown()`
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:165:3. **既存 test 完全互換**: live mode の COOLDOWN_TICKS=30 不変、既存 1248 PASS 維持。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:166:4. **ME-8 invariant 後退最小**: "cooldown active" → "cooldown active with eval-mode-specific
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:167:   reduced threshold" に文言更新するのみ、cooldown 概念自体は保持。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:171:### 3.2 棄却サマリ
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:175:| γ | cooldown が dominant gate のため prob 単独調整は効果限定 |
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:179:| θ | cooldown→prob の dominant gate 移転、ME-8 invariant 後退 |
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:182:### 3.3 採用案の修正範囲
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:184:#### 3.3.1 `src/erre_sandbox/integration/dialog.py`
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:188:    COOLDOWN_TICKS: ClassVar[int] = 30
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:189:    """Live multi-agent run の cooldown (live cognition_period での
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:190:    natural cadence 維持)。"""
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:192:    COOLDOWN_TICKS_EVAL: ClassVar[int] = 5
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:193:    """eval_natural_mode=True 時の reduced cooldown。実測 cognition_period
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:199:    def _effective_cooldown(self) -> int:
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:200:        """eval_natural_mode flag に応じた cooldown ticks を返す純関数。"""
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:201:        return self.COOLDOWN_TICKS_EVAL if self.eval_natural_mode else self.COOLDOWN_TICKS
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:204:`schedule_initiate` の cooldown check と `tick()` 内の cooldown check 両方を
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:205:`self._effective_cooldown()` 経由に統一。`golden_baseline_mode=True` の cooldown bypass
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:208:#### 3.3.2 `src/erre_sandbox/cli/eval_run_golden.py`
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:210:`capture_natural` の `--wall-timeout-min` default を **30 → 60** に変更。stimulus
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:213:#### 3.3.3 `tests/test_integration/test_dialog_eval_natural_mode.py` 拡張
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:216:eval-specific reduced cooldown の new contract を追加検証):
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:218:1. **`test_eval_mode_uses_reduced_cooldown`**: eval_natural_mode=True で同一 pair が
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:220:2. **`test_live_mode_cooldown_unchanged`**: eval_natural_mode=False (default) で
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:221:   COOLDOWN_TICKS=30 が active、tick 29 で reject / tick 30 で admit
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:222:3. **`test_effective_cooldown_returns_correct_value`**: `_effective_cooldown()`
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:224:4. **`test_class_constants_unchanged`**: `COOLDOWN_TICKS == 30` /
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:225:   `COOLDOWN_TICKS_EVAL == 5` の sentinel test (将来の silent な定数変更を防ぐ)
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:227:CLI test (`tests/test_cli/test_eval_run_golden.py`) に `--wall-timeout-min` default が
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:228:60 min for natural を assert する 1 ケース追加 (既存 12 mock test の隣)。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:230:### 3.4 ME-8 ADR §invariant の partial-update
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:232:v1 で「Cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:233:invariant は両 mode で active のまま」と書いた箇所を以下に Edit:
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:235:> **Cooldown (eval-mode 別 threshold = `COOLDOWN_TICKS_EVAL=5`、live は
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:236:> `COOLDOWN_TICKS=30`)** / probability / timeout / 自己 dialog reject /
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:237:> 二重 open reject の invariant は両 mode で active のまま — eval natural cadence
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:238:> は維持、proximity 制約のみ削除 + cooldown threshold を eval mode で reduce。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:242:- **fix v2 後も focal<25 で stop** → 別 dominant gate (prob 0.25 / 推論 deadlock 等) を再特定
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:244:  COOLDOWN_TICKS_EVAL=5 の妥当性を再評価 (60s なら cooldown=10 候補、240s なら cooldown=3
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:247:### 3.5 design v1 §採用案との差分明示
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:249:design v1 §6.1 の "Cooldown / probability / timeout は active のまま (natural cadence 保持)"
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:252:> v1 では cooldown_ticks=30 を eval mode でも flat に保持していたが、empirical で
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:253:> dominant gate と判明。v2 では eval mode 限定で COOLDOWN_TICKS_EVAL=5 に reduce
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:257:## 4. 受け入れ条件 (本 Mac セッション完了時)
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:260:- [ ] codex-review-prompt-natural-gating-v2.md 起草 (本セッション)
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:262:- [ ] HIGH/MEDIUM 反映後に decisions.md ME-8 二度目の partial-update
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:268:## 5. リスクと反証
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:270:- **リスク 1**: 60 min wall × cooldown=5 で focal=30 達成は **理論計算**、empirical で
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:271:  AUTO_FIRE_PROB_PER_TICK=0.25 の variance により 5 cycle 完走しない可能性。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:272:  - 反証実験: G-GEAR 再々採取で focal<25 が再発した場合、ME-8 §re-open 条件 1 項目目で
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:274:- **リスク 2**: eval mode reduced cooldown が dialog_turn_budget=6 と組合わさって
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:276:  ticks) で natural cadence が崩れる可能性。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:277:  - 反証: 1 cycle = 6 ticks (turn) + 5 ticks (cooldown) = 11 ticks/cycle、cognition_period
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:279:    G-GEAR 計算 (5 cycle = 90 utterance) は **prob 0.25 を込めていない**ため過大評価。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:281:  - **判断**: v2 では `--wall-timeout-min default=60` を採用、focal target 30 達成が
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:285:## 6. Codex review
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:288:`codex-review-prompt-natural-gating-v2.md` / `codex-review-natural-gating-v2.md` を
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:289:verbatim 保存。HIGH は実装前に反映、MEDIUM は decisions.md ME-8 に取り込み。
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:292:- Q1: §2.4 ι (β+δ) を「wall 爆発」で棄却したが、stimulus と natural を別 SOP で運用
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:293:  するなら ι が ME-8 invariant 後退ゼロで本来は最小侵襲では？
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:294:- Q2: §3.3.1 で `COOLDOWN_TICKS_EVAL=5` を hardcoded class const にしたが、CLI
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:295:  `--cooldown-ticks-eval N` で override 可能にすべきか？
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:296:- Q3: §5 リスク 2 の cycle 計算で AUTO_FIRE_PROB=0.25 を考慮すると wall=60 min default は
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:298:- Q4: ME-8 §invariant 文言の "active with reduced threshold" 表現は v1 contract に対し
tests/test_integration/test_dialog_eval_natural_mode.py:1:"""Tests for ``InMemoryDialogScheduler.eval_natural_mode`` flag.
tests/test_integration/test_dialog_eval_natural_mode.py:3:m9-eval-system P3a-decide Task 1 — natural runtime gating bug fix.
tests/test_integration/test_dialog_eval_natural_mode.py:5:Background (from `.steering/20260430-m9-eval-system/design-natural-gating-fix.md`):
tests/test_integration/test_dialog_eval_natural_mode.py:6:G-GEAR pilot 採取で natural condition (3 persona × 30 focal target) が
tests/test_integration/test_dialog_eval_natural_mode.py:13:修正: ``eval_natural_mode: bool = False`` flag を scheduler に追加し、True
tests/test_integration/test_dialog_eval_natural_mode.py:14:のとき ``tick()`` の zone equality / reflective zone 制約を bypass。
tests/test_integration/test_dialog_eval_natural_mode.py:15:cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
tests/test_integration/test_dialog_eval_natural_mode.py:16:invariant は両 mode で保持される (natural cadence は維持)。
tests/test_integration/test_dialog_eval_natural_mode.py:19:``capture_natural`` のみが指定する。
tests/test_integration/test_dialog_eval_natural_mode.py:46:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:47:# Helpers
tests/test_integration/test_dialog_eval_natural_mode.py:48:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:61:    """RNG whose ``random()`` always returns 0.0 (≤ AUTO_FIRE_PROB)."""
tests/test_integration/test_dialog_eval_natural_mode.py:68:    """RNG whose ``random()`` always returns 0.99 (> AUTO_FIRE_PROB)."""
tests/test_integration/test_dialog_eval_natural_mode.py:74:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:75:# Default constructor: eval_natural_mode is False (M4-frozen behaviour)
tests/test_integration/test_dialog_eval_natural_mode.py:76:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:79:def test_default_constructor_keeps_eval_natural_mode_false() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:82:    assert scheduler.eval_natural_mode is False
tests/test_integration/test_dialog_eval_natural_mode.py:85:def test_eval_natural_mode_is_independent_of_golden_baseline_mode() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:89:        envelope_sink=sink, eval_natural_mode=True, golden_baseline_mode=False
tests/test_integration/test_dialog_eval_natural_mode.py:92:        envelope_sink=sink, eval_natural_mode=False, golden_baseline_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:94:    assert scheduler_a.eval_natural_mode is True
tests/test_integration/test_dialog_eval_natural_mode.py:96:    assert scheduler_b.eval_natural_mode is False
tests/test_integration/test_dialog_eval_natural_mode.py:103:    ``golden_baseline_mode`` override the cooldown / timeout invariant
tests/test_integration/test_dialog_eval_natural_mode.py:104:    that ``eval_natural_mode`` advertises — surface the inconsistency at
tests/test_integration/test_dialog_eval_natural_mode.py:108:    with pytest.raises(ValueError, match="golden_baseline_mode and eval_natural_mode"):
tests/test_integration/test_dialog_eval_natural_mode.py:112:            eval_natural_mode=True,
tests/test_integration/test_dialog_eval_natural_mode.py:116:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:117:# Bug repro (default False): zone drift halts admission
tests/test_integration/test_dialog_eval_natural_mode.py:118:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:123:    proximity-only ``tick()`` cannot admit new dialogs.
tests/test_integration/test_dialog_eval_natural_mode.py:125:    This mirrors the G-GEAR pilot natural-condition pattern: initial burst
tests/test_integration/test_dialog_eval_natural_mode.py:132:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=False
tests/test_integration/test_dialog_eval_natural_mode.py:141:    scheduler.tick(world_tick=0, agents=co_located)
tests/test_integration/test_dialog_eval_natural_mode.py:151:    # Advance world tick past COOLDOWN_TICKS so cooldown is no longer the gate.
tests/test_integration/test_dialog_eval_natural_mode.py:152:    far_tick = scheduler.COOLDOWN_TICKS + 5
tests/test_integration/test_dialog_eval_natural_mode.py:160:    scheduler.tick(world_tick=far_tick, agents=scattered)
tests/test_integration/test_dialog_eval_natural_mode.py:163:        "pairs, so even after cooldown expires no admit fires"
tests/test_integration/test_dialog_eval_natural_mode.py:167:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:168:# Fix: eval_natural_mode=True admits any pair regardless of zone
tests/test_integration/test_dialog_eval_natural_mode.py:169:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:172:def test_eval_natural_mode_admits_pairs_across_different_zones() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:175:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:182:    scheduler.tick(world_tick=0, agents=scattered)
tests/test_integration/test_dialog_eval_natural_mode.py:188:def test_eval_natural_mode_admits_two_study_agents() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:190:    mode but eval natural treats all pairs as eligible — including STUDY-STUDY."""
tests/test_integration/test_dialog_eval_natural_mode.py:193:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:199:    scheduler.tick(world_tick=0, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:205:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:206:# Invariants preserved in eval_natural_mode
tests/test_integration/test_dialog_eval_natural_mode.py:207:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:210:def test_eval_natural_mode_preserves_self_dialog_reject() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:212:    scheduler = InMemoryDialogScheduler(envelope_sink=sink, eval_natural_mode=True)
tests/test_integration/test_dialog_eval_natural_mode.py:213:    result = scheduler.schedule_initiate("kant", "kant", Zone.AGORA, tick=0)
tests/test_integration/test_dialog_eval_natural_mode.py:217:def test_eval_natural_mode_preserves_double_open_reject() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:219:    scheduler = InMemoryDialogScheduler(envelope_sink=sink, eval_natural_mode=True)
tests/test_integration/test_dialog_eval_natural_mode.py:220:    first = scheduler.schedule_initiate("kant", "rikyu", Zone.AGORA, tick=0)
tests/test_integration/test_dialog_eval_natural_mode.py:222:    second = scheduler.schedule_initiate("kant", "rikyu", Zone.AGORA, tick=1)
tests/test_integration/test_dialog_eval_natural_mode.py:226:def test_eval_natural_mode_preserves_cooldown_via_tick() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:227:    """Cooldown still applies after a close — tick() must not re-admit
tests/test_integration/test_dialog_eval_natural_mode.py:228:    the same pair within ``COOLDOWN_TICKS`` even with the zone bypass."""
tests/test_integration/test_dialog_eval_natural_mode.py:231:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:237:    scheduler.tick(world_tick=0, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:242:    # Within cooldown window — no re-admit.
tests/test_integration/test_dialog_eval_natural_mode.py:243:    for w in range(1, scheduler.COOLDOWN_TICKS):
tests/test_integration/test_dialog_eval_natural_mode.py:244:        scheduler.tick(world_tick=w, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:246:            f"cooldown breached at tick {w}: same pair re-admitted within "
tests/test_integration/test_dialog_eval_natural_mode.py:247:            f"{scheduler.COOLDOWN_TICKS} ticks"
tests/test_integration/test_dialog_eval_natural_mode.py:250:    # Past cooldown — admit again.
tests/test_integration/test_dialog_eval_natural_mode.py:251:    scheduler.tick(world_tick=scheduler.COOLDOWN_TICKS, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:255:def test_eval_natural_mode_preserves_probability_gate() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:256:    """RNG > AUTO_FIRE_PROB still suppresses admit even with zone bypass."""
tests/test_integration/test_dialog_eval_natural_mode.py:259:        envelope_sink=sink, rng=_never_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:265:    scheduler.tick(world_tick=0, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:269:def test_eval_natural_mode_preserves_timeout_close() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:273:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:279:    scheduler.tick(world_tick=0, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:282:    # No activity recorded for TIMEOUT_TICKS ticks → tick() should auto-close.
tests/test_integration/test_dialog_eval_natural_mode.py:283:    scheduler.tick(world_tick=scheduler.TIMEOUT_TICKS, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:290:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:291:# Sustained admission scenario (Red→Green core)
tests/test_integration/test_dialog_eval_natural_mode.py:292:# ---------------------------------------------------------------------------
tests/test_integration/test_dialog_eval_natural_mode.py:295:def test_eval_natural_mode_sustains_admission_after_initial_burst() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:296:    """Reproduce the natural-condition observation pattern: initial burst,
tests/test_integration/test_dialog_eval_natural_mode.py:299:    Counter-example to the bug repro above: with eval_natural_mode=True,
tests/test_integration/test_dialog_eval_natural_mode.py:300:    even after agents scatter, admit fires resume after cooldown.
tests/test_integration/test_dialog_eval_natural_mode.py:304:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:312:    scheduler.tick(world_tick=0, agents=agents_initial)
tests/test_integration/test_dialog_eval_natural_mode.py:318:        # Stamp activity at tick 6 so close anchors cooldown there.
tests/test_integration/test_dialog_eval_natural_mode.py:332:    # Now agents scatter. Drive ticks past cooldown and check admit resumes.
tests/test_integration/test_dialog_eval_natural_mode.py:338:    far_tick = 6 + scheduler.COOLDOWN_TICKS  # 36
tests/test_integration/test_dialog_eval_natural_mode.py:339:    scheduler.tick(world_tick=far_tick, agents=scattered)
tests/test_integration/test_dialog_eval_natural_mode.py:341:        "after cooldown expires, all three pairs should re-admit even "
src/erre_sandbox/cli/eval_run_golden.py:15:* ``--condition natural`` — replicates :func:`erre_sandbox.bootstrap.bootstrap`
src/erre_sandbox/cli/eval_run_golden.py:34:* HIGH-5 — natural-condition scheduler RNG is seeded with
src/erre_sandbox/cli/eval_run_golden.py:41:reserved for ERRE mode in the live-run contract, while the stimulus / natural
src/erre_sandbox/cli/eval_run_golden.py:112:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:113:# Constants
src/erre_sandbox/cli/eval_run_golden.py:114:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:123:"""Hard wall-clock cap for one capture, primarily natural condition."""
src/erre_sandbox/cli/eval_run_golden.py:164:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:165:# Result dataclasses
src/erre_sandbox/cli/eval_run_golden.py:166:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:182:    """Returned from :func:`capture_stimulus` / :func:`capture_natural`.
src/erre_sandbox/cli/eval_run_golden.py:211:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:212:# Stimulus prompt builder (CLI-local; Codex MEDIUM-4 — do not reach into
src/erre_sandbox/cli/eval_run_golden.py:213:# integration.dialog_turn private symbols).
src/erre_sandbox/cli/eval_run_golden.py:214:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:276:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:277:# Inference factories
src/erre_sandbox/cli/eval_run_golden.py:278:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:388:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:389:# DuckDB sink
src/erre_sandbox/cli/eval_run_golden.py:390:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:477:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:478:# Stratified slicing (Codex HIGH-1)
src/erre_sandbox/cli/eval_run_golden.py:479:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:553:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:554:# Persona / agent helpers
src/erre_sandbox/cli/eval_run_golden.py:555:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:565:def _initial_state_for_natural(persona: PersonaSpec) -> AgentState:
src/erre_sandbox/cli/eval_run_golden.py:566:    """Build the AgentState used to register a persona for the natural run.
src/erre_sandbox/cli/eval_run_golden.py:584:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:585:# Output path / overwrite policy (Codex HIGH-4)
src/erre_sandbox/cli/eval_run_golden.py:586:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:607:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:608:# Stimulus capture
src/erre_sandbox/cli/eval_run_golden.py:609:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:770:    # firing. The driver calls schedule_initiate first, the envelope sink
src/erre_sandbox/cli/eval_run_golden.py:799:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:800:# Natural capture (full bootstrap stack, headless)
src/erre_sandbox/cli/eval_run_golden.py:801:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:804:async def capture_natural(  # noqa: C901, PLR0915 — composition root mirrors bootstrap.py
src/erre_sandbox/cli/eval_run_golden.py:819:    """Capture one natural-condition cell using a headless WorldRuntime stack.
src/erre_sandbox/cli/eval_run_golden.py:835:            f"persona={persona!r} is not part of the natural-condition agent "
src/erre_sandbox/cli/eval_run_golden.py:840:    run_id = f"{persona}_natural_run{run_idx}"
src/erre_sandbox/cli/eval_run_golden.py:848:        # ME-2 keeps the natural-condition memory DB /tmp-scoped so the eval
src/erre_sandbox/cli/eval_run_golden.py:851:            f"/tmp/p3a_natural_{persona}_run{run_idx}.sqlite",  # noqa: S108
src/erre_sandbox/cli/eval_run_golden.py:865:        logger.exception("ollama health check failed for natural capture")
src/erre_sandbox/cli/eval_run_golden.py:943:        # AGORA. See .steering/20260430-m9-eval-system/design-natural-gating-fix.md
src/erre_sandbox/cli/eval_run_golden.py:945:        eval_natural_mode=True,
src/erre_sandbox/cli/eval_run_golden.py:957:        runtime.register_agent(_initial_state_for_natural(spec), spec)
src/erre_sandbox/cli/eval_run_golden.py:965:    runtime_task = asyncio.create_task(runtime.run(), name="p3a-natural-runtime")
src/erre_sandbox/cli/eval_run_golden.py:972:                    "natural capture aborting on fatal sink error: %s",
src/erre_sandbox/cli/eval_run_golden.py:977:                logger.info("natural capture focal budget %d reached", turn_count)
src/erre_sandbox/cli/eval_run_golden.py:1019:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:1020:# CLI entry
src/erre_sandbox/cli/eval_run_golden.py:1021:# ---------------------------------------------------------------------------
src/erre_sandbox/cli/eval_run_golden.py:1046:        choices=("stimulus", "natural"),
src/erre_sandbox/cli/eval_run_golden.py:1056:            "Stimulus condition slices the battery to fit; natural condition "
src/erre_sandbox/cli/eval_run_golden.py:1090:        help="Embedding model tag (natural condition only).",
src/erre_sandbox/cli/eval_run_golden.py:1097:            "sqlite path for the natural-condition cognition stack "
src/erre_sandbox/cli/eval_run_golden.py:1098:            "(default: /tmp/p3a_natural_<persona>_run<idx>.sqlite)."
src/erre_sandbox/cli/eval_run_golden.py:1102:        "--wall-timeout-min",
src/erre_sandbox/cli/eval_run_golden.py:1106:            "Hard wall-clock cap for natural condition in minutes "
src/erre_sandbox/cli/eval_run_golden.py:1153:        result = await capture_natural(
src/erre_sandbox/cli/eval_run_golden.py:1216:    "capture_natural",
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:1:# M5/M6 natural runtime gating bug — design (P3a-decide Task 1)
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:7:## 1. 観測症状 (G-GEAR PR #129 採取)
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:11:| kant_natural | 13 min (kill) | 2 | 6 | kant=6 / nietzsche=3 / rikyu=3 |
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:12:| nietzsche_natural | 13 min (kill, starved) | 0 | 0 | — |
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:13:| rikyu_natural | 13 min (kill) | 3 | 6 | kant=6 / nietzsche=6 / rikyu=6 |
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:15:**stimulus side は 3 cell とも focal=198 / dialogs=168 で完走**、natural 専用の
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:18:## 2. 仮説 4 件と裏取り
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:23:| B | COOLDOWN_TICKS 30 × cognition_period 7-18s で実効 cooldown 30 min+ | 確かに wall は長いが、cognition tick は最終的に進む。kant_natural 13 min wall で nietzsche cognition_period=7s + WorldRuntime DEFAULT_COGNITION_PERIOD_S=10s → world_tick は 50+ 進むはず → cooldown 単独では説明不可 | △ 補助 |
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:24:| C | `_close_timed_out` が in-flight dialog を premature close | 既存 dialog の transcript が 6 turn (= dialog_turn_budget default) で揃っており、exhausted close で正常終了している。timeout race 未発生 | × 棄却 |
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:27:### Hypothesis D の精緻なメカニズム
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:29:1. `cli/eval_run_golden.py:_initial_state_for_natural` は 3 persona を
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:49:## 3. 初回案 (Claude single-shot)
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:52:**`eval_natural_mode: bool = False`** flag を追加。`True` のとき:
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:54:- `tick()` 内で `_iter_colocated_pairs(agents)` を呼ばず、`agents` の **全 distinct pair**
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:60:- `COOLDOWN_TICKS` / `AUTO_FIRE_PROB_PER_TICK` / `TIMEOUT_TICKS` はすべて
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:61:  default 通り **active のまま** (natural cadence を保つ)。
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:64:eval_natural_mode=True)` を渡す **1 行追加** のみ。
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:66:## 4. /reimagine 代案 (zero-from-scratch alternative)
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:79:- `eval_run_golden.py:capture_natural` 内で `PersonaSpec` を model_copy し、
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:93:  与え、`tick()` はその pair を直接反復。
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:97:## 5. 比較と採用判断
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:99:### 5.0 critical insight: `ERRE_ZONE_BIAS_P` の default = 0.2
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:108:を提示する事実と組み合わせると、natural condition の per-tick zone change rate は
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:121:### 5.1 代案再評価
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:134:### 5.2 採用案: **初回案 (scheduler flag `eval_natural_mode`)** 単独
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:141:3. **概念的に正しい**: eval natural は「3 persona を論理的に同居させる」ための
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:143:4. CLI 1 行追加 (`InMemoryDialogScheduler(..., eval_natural_mode=True)`) は
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:146:   許容範囲とする (decisions.md ME-8 で justify)。
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:151:## 6. 修正範囲 (採用案 = 初回案 scheduler flag)
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:153:### 6.1 修正ファイル
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:156:  - `InMemoryDialogScheduler.__init__` に `eval_natural_mode: bool = False` 追加
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:158:  - `tick()` 内で `eval_natural_mode=True` のとき
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:162:  - **Cooldown / probability / timeout は active のまま** (natural cadence 保持)
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:163:  - `schedule_initiate` の zone 制約 (line 156) は `eval_natural_mode=True` でも
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:170:    `eval_natural_mode=True` を 1 引数追加 (`golden_baseline_mode=False` の隣)
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:173:- `tests/test_integration/test_dialog_eval_natural_mode.py` (新規):
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:175:     - eval_natural_mode=False (既存挙動) で、3 agent が異なる zone に分散すると
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:177:     - eval_natural_mode=True で、同じ scenario でも admission が継続することを assert
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:178:  2. **invariant 保持**:
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:179:     - cooldown は active (close 後 30 tick 待つ)
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:180:     - probability gate は active (rng > 0.25 → admit しない)
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:187:  4. **scheduler 単体テスト**: ManualClock 不要、`tick()` を直接呼んで
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:191:### 6.2 既存 1221 テスト互換性
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:193:`eval_natural_mode: bool = False` default のため、既存挙動は完全に維持。
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:196:  golden_baseline_mode は eval_natural_mode と直交、両 default False / True で
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:199:### 6.3 schemas.py の Protocol 整合
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:202:ので keyword-only flag 追加は Protocol 違反にあたらない。`tick()` /
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:203:`schedule_initiate()` / `record_turn()` / `close_dialog()` の signature は
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:206:## 7. 受け入れ条件
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:208:- [ ] 新規 test_dialog_eval_natural_mode.py の Red→Green 転換テストが PASS
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:211:- [ ] cooldown / probability / timeout / 自己 dialog reject / 二重 open reject
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:212:      の invariant が True/False 両方で維持される
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:216:- [ ] decisions.md に新規 ADR (ME-8) 追加: "eval natural condition は
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:217:      InMemoryDialogScheduler.eval_natural_mode=True で zone 制約を bypass"
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:220:## 8. リスクと反証
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:231:## 9. Codex review
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:234:回す。codex-review-prompt-natural-gating.md / codex-review-natural-gating.md を
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:235:verbatim 保存。HIGH は実装前に反映、MEDIUM は decisions.md ME-8 に取り込み。
.steering/20260430-m9-eval-system/decisions.md:1:# Decisions — m9-eval-system (Codex review MEDIUM 反映)
.steering/20260430-m9-eval-system/decisions.md:3:## ADR 体裁
.steering/20260430-m9-eval-system/decisions.md:14:## ME-1 — IPIP-NEO fallback trigger operational definition (Codex MEDIUM-1)
.steering/20260430-m9-eval-system/decisions.md:51:## ME-2 — DuckDB snapshot semantics (G-GEAR write → Mac read-only) (Codex MEDIUM-2)
.steering/20260430-m9-eval-system/decisions.md:85:## ME-3 — Tier C lock + preflight TOCTOU close (Codex MEDIUM-3)
.steering/20260430-m9-eval-system/decisions.md:124:## ME-4 — Hybrid baseline ratio: P3a 完了後に確定 (Codex HIGH-3 系の defer ADR)
.steering/20260430-m9-eval-system/decisions.md:132:  - **natural 3 cell**: G-GEAR 採取は M5/M6 zone-drift bug で **partial**
.steering/20260430-m9-eval-system/decisions.md:134:    本セッションで `InMemoryDialogScheduler.eval_natural_mode=True` を導入して bug
.steering/20260430-m9-eval-system/decisions.md:135:    を解決 (PR `feature/m9-eval-p3a-decide`、ME-8 ADR 参照)。修正後の natural cell は
.steering/20260430-m9-eval-system/decisions.md:144:    natural 再採取後に再判定。
.steering/20260430-m9-eval-system/decisions.md:155:  - **stimulus 側 CI のみで ratio 確定**: natural side との **比較**が ratio 決定の
.steering/20260430-m9-eval-system/decisions.md:159:    p3a_decide script は ready、natural 再採取後に最終 ratio 確定
.steering/20260430-m9-eval-system/decisions.md:164:    1. G-GEAR 再採取で natural side が完走 (focal 30 / total 90 / dialogs ~15)
.steering/20260430-m9-eval-system/decisions.md:175:    "ratio ADR 確定 (natural 再採取待ち) [pending]"
.steering/20260430-m9-eval-system/decisions.md:179:## ME-5 — RNG seed: hashlib.blake2b で uint64 stable seed (Codex MEDIUM-5)
.steering/20260430-m9-eval-system/decisions.md:209:## ME-6 — Burrows reference corpus QC (Codex MEDIUM-6)
.steering/20260430-m9-eval-system/decisions.md:244:## ME-7 — RoleEval Option A 採択 + MCQ schema / scoring protocol (LOW-1 close、Codex 2026-05-01 review)
.steering/20260430-m9-eval-system/decisions.md:355:## ME-8 — eval natural condition の zone gate bypass (P3a-decide gating bug fix)
.steering/20260430-m9-eval-system/decisions.md:357:- **決定**: `InMemoryDialogScheduler.__init__` に **`eval_natural_mode: bool = False`**
.steering/20260430-m9-eval-system/decisions.md:359:  1. `tick()` 内で `_iter_colocated_pairs` の代わりに新規ヘルパ
.steering/20260430-m9-eval-system/decisions.md:362:  2. `tick()` 内の `_REFLECTIVE_ZONES` skip を bypass
.steering/20260430-m9-eval-system/decisions.md:363:  3. `schedule_initiate` 内の zone-not-reflective reject を bypass
.steering/20260430-m9-eval-system/decisions.md:364:  4. **cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
.steering/20260430-m9-eval-system/decisions.md:365:     invariant は両 mode で active のまま** — natural cadence は維持、proximity
.steering/20260430-m9-eval-system/decisions.md:367:- **構築時防御**: `golden_baseline_mode=True` と `eval_natural_mode=True` の同時指定は
.steering/20260430-m9-eval-system/decisions.md:370:- **CLI opt-in**: `cli/eval_run_golden.py:capture_natural` の scheduler 構築に
.steering/20260430-m9-eval-system/decisions.md:371:  `eval_natural_mode=True` を 1 引数追加 (planning purity 違反は最小)
.steering/20260430-m9-eval-system/decisions.md:373:  - **観測**: G-GEAR P3a pilot で natural 3 cell が初動 burst 2-3 dialogs (= 12-18
.steering/20260430-m9-eval-system/decisions.md:374:    utterances) で完全停止。stimulus 3 cell は同条件で focal=198 完走 → natural 専用の
.steering/20260430-m9-eval-system/decisions.md:384:  - **代案比較**: `decisions.md` 関連の `design-natural-gating-fix.md` §5 で
.steering/20260430-m9-eval-system/decisions.md:388:  - **Codex `gpt-5.5 xhigh` independent review** (`codex-review-natural-gating.md`):
.steering/20260430-m9-eval-system/decisions.md:401:  - `src/erre_sandbox/integration/dialog.py`: flag 追加 + 構築時 reject + tick()/
.steering/20260430-m9-eval-system/decisions.md:402:    schedule_initiate() の bypass + `_iter_all_distinct_pairs` ヘルパ
.steering/20260430-m9-eval-system/decisions.md:403:  - `src/erre_sandbox/cli/eval_run_golden.py`: capture_natural の scheduler 構築に
.steering/20260430-m9-eval-system/decisions.md:404:    `eval_natural_mode=True` を 1 引数追加 (CLI ロジックは不変)
.steering/20260430-m9-eval-system/decisions.md:405:  - `tests/test_integration/test_dialog_eval_natural_mode.py`: 12 unit test
.steering/20260430-m9-eval-system/decisions.md:406:    (Red→Green 転換 + 5 invariant + 構築時 reject)、既存 1221 PASS は default
.steering/20260430-m9-eval-system/decisions.md:408:  - 次 G-GEAR セッションで natural 再採取時に修正効果を実機検証
.steering/20260430-m9-eval-system/decisions.md:413:  - `last_close_tick` のクラスタ的な spread を logs で確認 (cooldown が effective
.steering/20260430-m9-eval-system/decisions.md:419:  - **逆に admit 過多で natural cadence が壊れる場合** → AUTO_FIRE_PROB_PER_TICK
.steering/20260430-m9-eval-system/decisions.md:420:    の 0.25 を eval 用に低めに調整、または cooldown 延長
.steering/20260430-m9-eval-system/decisions.md:422:    緩和ルールを ADR child で起票 (cooldown/timeout の "両 flag union" semantics
.steering/20260430-m9-eval-system/decisions.md:427:## ME-summary
.steering/20260430-m9-eval-system/decisions.md:432:- ME-4 は P3a-decide セッションで **partial update**、natural 再採取後に **二度目の
.steering/20260430-m9-eval-system/decisions.md:435:- ME-8 (本セッション新規) は m9-eval-system P3a-decide gating bug fix の確定 ADR、
src/erre_sandbox/integration/dialog.py:12:* The Protocol is frozen at M4 foundation and says ``schedule_initiate``
src/erre_sandbox/integration/dialog.py:18:* ``tick()`` is an extension method (not part of the Protocol) that drives
src/erre_sandbox/integration/dialog.py:20:  the pair's cooldown has elapsed get a probabilistic initiate.
src/erre_sandbox/integration/dialog.py:89:    COOLDOWN_TICKS: ClassVar[int] = 30
src/erre_sandbox/integration/dialog.py:95:    AUTO_FIRE_PROB_PER_TICK: ClassVar[float] = 0.25
src/erre_sandbox/integration/dialog.py:100:    probability to 1.0 or 0.0 deterministically.
src/erre_sandbox/integration/dialog.py:110:        eval_natural_mode: bool = False,
src/erre_sandbox/integration/dialog.py:121:        # external golden baseline driver bypasses cooldown / timeout / zone
src/erre_sandbox/integration/dialog.py:123:        # same agent pair without the natural-dialog admission rules. Public
src/erre_sandbox/integration/dialog.py:125:        # (200 turn, mode=True) and natural-dialog phase (300 turn,
src/erre_sandbox/integration/dialog.py:128:        # m9-eval-system P3a-decide (design-natural-gating-fix.md): when True
src/erre_sandbox/integration/dialog.py:129:        # the eval natural-condition pilot bypasses zone-equality and
src/erre_sandbox/integration/dialog.py:130:        # reflective-zone gates inside ``tick()`` and ``schedule_initiate()``
src/erre_sandbox/integration/dialog.py:132:        # scatters them across study/peripatos/chashitsu. Cooldown / probability
src/erre_sandbox/integration/dialog.py:134:        # so admission cadence is still natural — only the spatial constraint
src/erre_sandbox/integration/dialog.py:137:        # natural phase uses ``eval_natural_mode=True`` (proximity-free
src/erre_sandbox/integration/dialog.py:140:        self.eval_natural_mode: bool = eval_natural_mode
src/erre_sandbox/integration/dialog.py:141:        if eval_natural_mode and golden_baseline_mode:
src/erre_sandbox/integration/dialog.py:142:            # Codex review LOW-1 (2026-05-01): the invariant claims for
src/erre_sandbox/integration/dialog.py:143:            # ``eval_natural_mode`` (cooldown / timeout active) only hold
src/erre_sandbox/integration/dialog.py:145:            # a programming error because golden_baseline overrides cooldown
src/erre_sandbox/integration/dialog.py:150:                "golden_baseline_mode and eval_natural_mode on the same "
src/erre_sandbox/integration/dialog.py:152:                "vs natural). Construct two schedulers if both phases are "
src/erre_sandbox/integration/dialog.py:161:        # ``tick()``; for now the memory footprint is irrelevant.
src/erre_sandbox/integration/dialog.py:168:    def schedule_initiate(
src/erre_sandbox/integration/dialog.py:188:            and not self.eval_natural_mode
src/erre_sandbox/integration/dialog.py:192:            # bursts) — bypass the natural-dialog cultural restriction.
src/erre_sandbox/integration/dialog.py:193:            # m9-eval-system P3a-decide: eval natural condition lets agents
src/erre_sandbox/integration/dialog.py:203:            and tick - last_close < self.COOLDOWN_TICKS
src/erre_sandbox/integration/dialog.py:207:            # repeatedly; cooldown would otherwise serialize them across
src/erre_sandbox/integration/dialog.py:270:        (``DialogCloseMsg.tick`` and the cooldown anchor both honour it).
src/erre_sandbox/integration/dialog.py:308:    def tick(self, world_tick: int, agents: Sequence[AgentView]) -> None:
src/erre_sandbox/integration/dialog.py:315:        2. for each co-located pair in reflective zones, probabilistically
src/erre_sandbox/integration/dialog.py:316:           admit (if not already open and past cooldown)
src/erre_sandbox/integration/dialog.py:318:        m9-eval-system P3a-decide: when ``eval_natural_mode`` is True the
src/erre_sandbox/integration/dialog.py:321:        skip below is bypassed. Cooldown / probability / timeout invariants
src/erre_sandbox/integration/dialog.py:322:        remain active so admission cadence is still natural — only proximity
src/erre_sandbox/integration/dialog.py:326:        if self.eval_natural_mode:
src/erre_sandbox/integration/dialog.py:331:            if not self.eval_natural_mode and a.zone not in _REFLECTIVE_ZONES:
src/erre_sandbox/integration/dialog.py:337:            if last_close is not None and world_tick - last_close < self.COOLDOWN_TICKS:
src/erre_sandbox/integration/dialog.py:339:            if self._rng.random() > self.AUTO_FIRE_PROB_PER_TICK:
src/erre_sandbox/integration/dialog.py:341:            self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)
src/erre_sandbox/integration/dialog.py:375:            # the natural inactivity timeout is suppressed to avoid races
src/erre_sandbox/integration/dialog.py:376:            # between driver close and tick() auto-close.
src/erre_sandbox/integration/dialog.py:399:# ---------------------------------------------------------------------------
src/erre_sandbox/integration/dialog.py:400:# Module-private helpers
src/erre_sandbox/integration/dialog.py:401:# ---------------------------------------------------------------------------
src/erre_sandbox/integration/dialog.py:433:    m9-eval-system P3a-decide: used by ``tick()`` when
src/erre_sandbox/integration/dialog.py:434:    ``eval_natural_mode=True``. The zone field on the leading element is
src/erre_sandbox/integration/dialog.py:436:    ``schedule_initiate`` envelope), but pair eligibility itself does not
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:14:# Codex independent review — m9-eval-system P3a-decide natural gating fix
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:17:> `cat .steering/20260430-m9-eval-system/codex-review-prompt-natural-gating.md
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:19:> 出力は `codex-review-natural-gating.md` に verbatim 保存。
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:23:## Context
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:28:total=342, dialogs=168). 3 natural cells **stalled after the initial
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:31:- kant_natural: 13 min wall, 2 dialogs / 6 focal turns
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:32:- nietzsche_natural: 13 min wall, **0 dialogs / 0 focal turns** (starved)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:33:- rikyu_natural: 13 min wall, 3 dialogs / 6 focal turns
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:36:The natural path constructs a full `WorldRuntime` + `CognitionCycle`
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:38:`_initial_state_for_natural` (separate seats inside AGORA).
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:40:## Root cause we converged on
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:54:`InMemoryDialogScheduler.tick()` then sees `_iter_colocated_pairs`
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:62:## Fix being proposed
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:65:keyword-only `eval_natural_mode: bool = False` flag. When True:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:67:1. `tick()` uses a new `_iter_all_distinct_pairs` helper instead of
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:72:3. `schedule_initiate` similarly bypasses the zone-not-reflective reject
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:76:CLI opt-in is one keyword in `capture_natural`.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:78:## Invariants explicitly preserved
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:81:- Pair already open → second `schedule_initiate` returns None
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:82:- `COOLDOWN_TICKS=30` → same pair cannot re-admit within 30 ticks of
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:84:- `AUTO_FIRE_PROB_PER_TICK=0.25` → probability gate still active
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:89:`tests/test_integration/test_dialog_eval_natural_mode.py` enforce all
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:92:## Diff (verbatim)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:94:### `src/erre_sandbox/integration/dialog.py`
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:97:# Constructor signature
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:105:    eval_natural_mode: bool = False,  # ← NEW
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:109:    self.eval_natural_mode: bool = eval_natural_mode  # ← NEW (public)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:111:# schedule_initiate (line 167)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:115:    and not self.eval_natural_mode  # ← NEW
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:119:# tick (line 299)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:121:if self.eval_natural_mode:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:126:    if not self.eval_natural_mode and a.zone not in _REFLECTIVE_ZONES:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:132:    if last_close is not None and world_tick - last_close < self.COOLDOWN_TICKS:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:134:    if self._rng.random() > self.AUTO_FIRE_PROB_PER_TICK:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:136:    self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:138:# New helper (line 406)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:148:### `src/erre_sandbox/cli/eval_run_golden.py` (line 935-947)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:156:    eval_natural_mode=True,  # ← NEW
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:160:## Specific review asks
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:166:2. **Invariant preservation**: do cooldown / probability / timeout /
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:168:   `eval_natural_mode=True`? The test suite covers them but you may
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:172:   only fixes `schedule_initiate / record_turn / close_dialog`
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:174:4. **Naming**: `eval_natural_mode` vs alternatives (`relax_zone_gate`,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:176:   for eval natural-condition capture, but the flag name should be
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:179:   design-natural-gating-fix.md):
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:189:   default `eval_natural_mode=False`?
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:194:   you expect the 30-target-focal natural cell to complete within
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:198:## Out of scope for this review
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:205:## Format
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:216:I’ll treat this as a code-review pass, using the ERRE workflow entry point first, then I’ll inspect the scheduler, CLI wiring, and the new tests against the invariants you listed.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:229:# ERRE Workflow
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:235:## Quick Start
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:249:## Task Start
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:261:## Implementation Flows
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:277:## Reimagine
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:290:## Review And Finish
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:312:# Project Status
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:316:## 現在の git 状態
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:320:## 最近のコミット (10 件)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:324:## 現在のブランチ
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:328:## 構築フェーズ進捗
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:332:## 未対応 TODO の数
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:336:## 変更ファイルの統計 (直近コミットとの差分)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:340:## 最近変更されたファイル (24 時間以内)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:344:## Skills ディレクトリ
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:348:## あなたのタスク
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:429:        # AGORA. See .steering/20260430-m9-eval-system/design-natural-gating-fix.md
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:431:        eval_natural_mode=True,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:443:        runtime.register_agent(_initial_state_for_natural(spec), spec)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:451:    runtime_task = asyncio.create_task(runtime.run(), name="p3a-natural-runtime")
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:458:                    "natural capture aborting on fatal sink error: %s",
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:463:                logger.info("natural capture focal budget %d reached", turn_count)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:480:* The Protocol is frozen at M4 foundation and says ``schedule_initiate``
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:486:* ``tick()`` is an extension method (not part of the Protocol) that drives
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:488:  the pair's cooldown has elapsed get a probabilistic initiate.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:557:    COOLDOWN_TICKS: ClassVar[int] = 30
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:563:    AUTO_FIRE_PROB_PER_TICK: ClassVar[float] = 0.25
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:568:    probability to 1.0 or 0.0 deterministically.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:578:        eval_natural_mode: bool = False,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:589:        # external golden baseline driver bypasses cooldown / timeout / zone
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:591:        # same agent pair without the natural-dialog admission rules. Public
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:593:        # (200 turn, mode=True) and natural-dialog phase (300 turn,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:596:        # m9-eval-system P3a-decide (design-natural-gating-fix.md): when True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:597:        # the eval natural-condition pilot bypasses zone-equality and
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:598:        # reflective-zone gates inside ``tick()`` and ``schedule_initiate()``
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:600:        # scatters them across study/peripatos/chashitsu. Cooldown / probability
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:602:        # so admission cadence is still natural — only the spatial constraint
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:605:        # natural phase uses ``eval_natural_mode=True`` (proximity-free
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:608:        self.eval_natural_mode: bool = eval_natural_mode
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:614:        # ``tick()``; for now the memory footprint is irrelevant.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:621:    def schedule_initiate(
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:641:            and not self.eval_natural_mode
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:645:            # bursts) — bypass the natural-dialog cultural restriction.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:646:            # m9-eval-system P3a-decide: eval natural condition lets agents
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:656:            and tick - last_close < self.COOLDOWN_TICKS
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:660:            # repeatedly; cooldown would otherwise serialize them across
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:723:        (``DialogCloseMsg.tick`` and the cooldown anchor both honour it).
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:761:    def tick(self, world_tick: int, agents: Sequence[AgentView]) -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:768:        2. for each co-located pair in reflective zones, probabilistically
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:769:           admit (if not already open and past cooldown)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:771:        m9-eval-system P3a-decide: when ``eval_natural_mode`` is True the
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:774:        skip below is bypassed. Cooldown / probability / timeout invariants
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:775:        remain active so admission cadence is still natural — only proximity
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:779:        if self.eval_natural_mode:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:784:            if not self.eval_natural_mode and a.zone not in _REFLECTIVE_ZONES:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:790:            if last_close is not None and world_tick - last_close < self.COOLDOWN_TICKS:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:792:            if self._rng.random() > self.AUTO_FIRE_PROB_PER_TICK:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:794:            self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:828:            # the natural inactivity timeout is suppressed to avoid races
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:829:            # between driver close and tick() auto-close.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:852:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:853:# Module-private helpers
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:854:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:882:    m9-eval-system P3a-decide: used by ``tick()`` when
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:883:    ``eval_natural_mode=True``. The zone field on the leading element is
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:885:    ``schedule_initiate`` envelope), but pair eligibility itself does not
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:906:?? .steering/20260430-m9-eval-system/codex-review-prompt-natural-gating.md
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:907:?? .steering/20260430-m9-eval-system/design-natural-gating-fix.md
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:908:?? tests/test_integration/test_dialog_eval_natural_mode.py
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:911:/bin/zsh -lc 'git diff -- src/erre_sandbox/integration/dialog.py src/erre_sandbox/cli/eval_run_golden.py tests/test_integration/test_dialog_eval_natural_mode.py' in /Users/johnd/ERRE-Sand Box
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:917:@@ -938,6 +938,11 @@ async def capture_natural(  # noqa: C901, PLR0915 — composition root mirrors b
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:923:+        # AGORA. See .steering/20260430-m9-eval-system/design-natural-gating-fix.md
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:925:+        eval_natural_mode=True,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:937:+        eval_natural_mode: bool = False,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:942:         # (200 turn, mode=True) and natural-dialog phase (300 turn,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:945:+        # m9-eval-system P3a-decide (design-natural-gating-fix.md): when True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:946:+        # the eval natural-condition pilot bypasses zone-equality and
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:947:+        # reflective-zone gates inside ``tick()`` and ``schedule_initiate()``
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:949:+        # scatters them across study/peripatos/chashitsu. Cooldown / probability
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:951:+        # so admission cadence is still natural — only the spatial constraint
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:954:+        # natural phase uses ``eval_natural_mode=True`` (proximity-free
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:957:+        self.eval_natural_mode: bool = eval_natural_mode
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:969:+            and not self.eval_natural_mode
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:973:             # bursts) — bypass the natural-dialog cultural restriction.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:974:+            # m9-eval-system P3a-decide: eval natural condition lets agents
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:982:         2. for each co-located pair in reflective zones, probabilistically
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:983:            admit (if not already open and past cooldown)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:985:+        m9-eval-system P3a-decide: when ``eval_natural_mode`` is True the
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:988:+        skip below is bypassed. Cooldown / probability / timeout invariants
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:989:+        remain active so admission cadence is still natural — only proximity
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:995:+        if self.eval_natural_mode:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1000:+            if not self.eval_natural_mode and a.zone not in _REFLECTIVE_ZONES:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1013:+    m9-eval-system P3a-decide: used by ``tick()`` when
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1014:+    ``eval_natural_mode=True``. The zone field on the leading element is
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1016:+    ``schedule_initiate`` envelope), but pair eligibility itself does not
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1030:/bin/zsh -lc "sed -n '1,360p' tests/test_integration/test_dialog_eval_natural_mode.py" in /Users/johnd/ERRE-Sand Box
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1032:"""Tests for ``InMemoryDialogScheduler.eval_natural_mode`` flag.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1034:m9-eval-system P3a-decide Task 1 — natural runtime gating bug fix.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1036:Background (from `.steering/20260430-m9-eval-system/design-natural-gating-fix.md`):
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1037:G-GEAR pilot 採取で natural condition (3 persona × 30 focal target) が
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1044:修正: ``eval_natural_mode: bool = False`` flag を scheduler に追加し、True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1045:のとき ``tick()`` の zone equality / reflective zone 制約を bypass。
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1046:cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1047:invariant は両 mode で保持される (natural cadence は維持)。
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1050:``capture_natural`` のみが指定する。
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1075:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1076:# Helpers
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1077:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1090:    """RNG whose ``random()`` always returns 0.0 (≤ AUTO_FIRE_PROB)."""
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1097:    """RNG whose ``random()`` always returns 0.99 (> AUTO_FIRE_PROB)."""
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1103:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1104:# Default constructor: eval_natural_mode is False (M4-frozen behaviour)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1105:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1108:def test_default_constructor_keeps_eval_natural_mode_false() -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1111:    assert scheduler.eval_natural_mode is False
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1114:def test_eval_natural_mode_is_independent_of_golden_baseline_mode() -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1118:        envelope_sink=sink, eval_natural_mode=True, golden_baseline_mode=False
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1121:        envelope_sink=sink, eval_natural_mode=False, golden_baseline_mode=True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1123:    assert scheduler_a.eval_natural_mode is True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1125:    assert scheduler_b.eval_natural_mode is False
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1129:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1130:# Bug repro (default False): zone drift halts admission
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1131:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1136:    proximity-only ``tick()`` cannot admit new dialogs.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1138:    This mirrors the G-GEAR pilot natural-condition pattern: initial burst
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1145:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=False
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1154:    scheduler.tick(world_tick=0, agents=co_located)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1164:    # Advance world tick past COOLDOWN_TICKS so cooldown is no longer the gate.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1165:    far_tick = scheduler.COOLDOWN_TICKS + 5
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1173:    scheduler.tick(world_tick=far_tick, agents=scattered)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1176:        "pairs, so even after cooldown expires no admit fires"
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1180:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1181:# Fix: eval_natural_mode=True admits any pair regardless of zone
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1182:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1185:def test_eval_natural_mode_admits_pairs_across_different_zones() -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1188:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1195:    scheduler.tick(world_tick=0, agents=scattered)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1201:def test_eval_natural_mode_admits_two_study_agents() -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1203:    mode but eval natural treats all pairs as eligible — including STUDY-STUDY."""
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1206:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1212:    scheduler.tick(world_tick=0, agents=agents)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1218:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1219:# Invariants preserved in eval_natural_mode
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1220:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1223:def test_eval_natural_mode_preserves_self_dialog_reject() -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1226:        envelope_sink=sink, eval_natural_mode=True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1228:    result = scheduler.schedule_initiate("kant", "kant", Zone.AGORA, tick=0)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1232:def test_eval_natural_mode_preserves_double_open_reject() -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1235:        envelope_sink=sink, eval_natural_mode=True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1237:    first = scheduler.schedule_initiate("kant", "rikyu", Zone.AGORA, tick=0)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1239:    second = scheduler.schedule_initiate("kant", "rikyu", Zone.AGORA, tick=1)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1243:def test_eval_natural_mode_preserves_cooldown_via_tick() -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1244:    """Cooldown still applies after a close — tick() must not re-admit
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1245:    the same pair within ``COOLDOWN_TICKS`` even with the zone bypass."""
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1248:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1254:    scheduler.tick(world_tick=0, agents=agents)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1259:    # Within cooldown window — no re-admit.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1260:    for w in range(1, scheduler.COOLDOWN_TICKS):
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1261:        scheduler.tick(world_tick=w, agents=agents)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1263:            f"cooldown breached at tick {w}: same pair re-admitted within "
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1264:            f"{scheduler.COOLDOWN_TICKS} ticks"
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1267:    # Past cooldown — admit again.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1268:    scheduler.tick(world_tick=scheduler.COOLDOWN_TICKS, agents=agents)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1272:def test_eval_natural_mode_preserves_probability_gate() -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1273:    """RNG > AUTO_FIRE_PROB still suppresses admit even with zone bypass."""
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1276:        envelope_sink=sink, rng=_never_fire(), eval_natural_mode=True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1282:    scheduler.tick(world_tick=0, agents=agents)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1286:def test_eval_natural_mode_preserves_timeout_close() -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1290:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1296:    scheduler.tick(world_tick=0, agents=agents)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1299:    # No activity recorded for TIMEOUT_TICKS ticks → tick() should auto-close.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1300:    scheduler.tick(world_tick=scheduler.TIMEOUT_TICKS, agents=agents)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1307:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1308:# Sustained admission scenario (Red→Green core)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1309:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1312:def test_eval_natural_mode_sustains_admission_after_initial_burst() -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1313:    """Reproduce the natural-condition observation pattern: initial burst,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1316:    Counter-example to the bug repro above: with eval_natural_mode=True,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1317:    even after agents scatter, admit fires resume after cooldown.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1321:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1329:    scheduler.tick(world_tick=0, agents=agents_initial)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1335:        # Stamp activity at tick 6 so close anchors cooldown there.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1349:    # Now agents scatter. Drive ticks past cooldown and check admit resumes.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1355:    far_tick = 6 + scheduler.COOLDOWN_TICKS  # 36
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1356:    scheduler.tick(world_tick=far_tick, agents=scattered)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1358:        "after cooldown expires, all three pairs should re-admit even "
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1363:/bin/zsh -lc "rg -n \"class DialogScheduler|Protocol|schedule_initiate|InMemoryDialogScheduler|tick\\(\" src tests | head -120" in /Users/johnd/ERRE-Sand Box
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1369:src/erre_sandbox/world/tick.py:808:    async def _on_physics_tick(self) -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1370:src/erre_sandbox/world/tick.py:1038:    async def _on_cognition_tick(self) -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1371:src/erre_sandbox/world/tick.py:1080:        self._run_dialog_tick()
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1372:src/erre_sandbox/world/tick.py:1082:            await self._drive_dialog_turns(self._current_world_tick())
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1373:src/erre_sandbox/world/tick.py:1084:    def _run_dialog_tick(self) -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1376:src/erre_sandbox/world/tick.py:1105:            tick_fn(self._current_world_tick(), views)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1377:src/erre_sandbox/world/tick.py:1110:    def _current_world_tick(self) -> int:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1380:src/erre_sandbox/world/tick.py:1270:    async def _on_heartbeat_tick(self) -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1381:src/erre_sandbox/world/tick.py:1273:                tick=self._current_world_tick(),
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1390:src/erre_sandbox/integration/dialog.py:12:* The Protocol is frozen at M4 foundation and says ``schedule_initiate``
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1392:src/erre_sandbox/integration/dialog.py:18:* ``tick()`` is an extension method (not part of the Protocol) that drives
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1394:src/erre_sandbox/integration/dialog.py:130:        # reflective-zone gates inside ``tick()`` and ``schedule_initiate()``
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1396:src/erre_sandbox/integration/dialog.py:146:        # ``tick()``; for now the memory footprint is irrelevant.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1398:src/erre_sandbox/integration/dialog.py:153:    def schedule_initiate(
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1402:src/erre_sandbox/integration/dialog.py:293:    def tick(self, world_tick: int, agents: Sequence[AgentView]) -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1403:src/erre_sandbox/integration/dialog.py:326:            self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1404:src/erre_sandbox/integration/dialog.py:361:            # between driver close and tick() auto-close.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1405:src/erre_sandbox/integration/dialog.py:414:    m9-eval-system P3a-decide: used by ``tick()`` when
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1406:src/erre_sandbox/integration/dialog.py:417:    ``schedule_initiate`` envelope), but pair eligibility itself does not
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1409:tests/test_evidence/test_golden_baseline.py:9:   per stimulus through ``schedule_initiate`` / ``record_turn`` /
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1423:src/erre_sandbox/schemas.py:1331:    def schedule_initiate(
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1432:src/erre_sandbox/cli/eval_run_golden.py:770:    # firing. The driver calls schedule_initiate first, the envelope sink
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1440:tests/test_world/test_temporal_events.py:166:    await runtime._on_physics_tick()
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1441:tests/test_memory/test_store.py:705:def test_add_bias_event_allows_multiple_per_tick(store: MemoryStore) -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1442:tests/test_world/test_tick.py:346:    async def test_move_msg_drives_next_physics_tick(
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1443:src/erre_sandbox/cognition/reflection.py:238:    def record_tick(self, agent_id: str) -> int:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1444:src/erre_sandbox/cognition/reflection.py:271:        ticks_since = self.record_tick(agent_state.agent_id)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1446:src/erre_sandbox/evidence/golden_baseline.py:5:(``schedule_initiate`` / ``record_turn`` / ``close_dialog``). When the
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1449:src/erre_sandbox/evidence/golden_baseline.py:375:        open_tick = self._allocate_tick()
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1450:src/erre_sandbox/evidence/golden_baseline.py:376:        admitted = self.scheduler.schedule_initiate(
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1451:src/erre_sandbox/evidence/golden_baseline.py:394:            turn_tick = self._allocate_tick()
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1452:src/erre_sandbox/evidence/golden_baseline.py:419:        close_tick = self._allocate_tick()
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1453:src/erre_sandbox/evidence/golden_baseline.py:434:    def _allocate_tick(self) -> int:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1454:tests/conftest.py:202:def _build_world_tick(tick: int, overrides: dict[str, Any]) -> WorldTickMsg:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1455:tests/test_cognition/test_reflection.py:104:        reflector.record_tick("a")
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1456:tests/test_cognition/test_reflection.py:105:        reflector.record_tick("a")
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1457:tests/test_cognition/test_reflection.py:106:        assert reflector.record_tick("a") == 3
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1458:tests/test_cognition/test_reflection.py:107:        assert reflector.record_tick("b") == 1
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1459:tests/test_cognition/test_reflection.py:109:        assert reflector.record_tick("a") == 1
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1472:tests/test_integration/test_slice_gamma_e2e.py:118:    initiate = scheduler.schedule_initiate(
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1477:tests/test_integration/test_slice_delta_e2e.py:109:    initiate = scheduler.schedule_initiate(
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1487:/bin/zsh -lc "sed -n '1,220p' .steering/20260430-m9-eval-system/design-natural-gating-fix.md" in /Users/johnd/ERRE-Sand Box
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1530:# =============================================================================
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1531:# §1 Protocol constants
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1532:# =============================================================================
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1547:(:attr:`Cognitive.dialog_turn_budget`, :attr:`DialogTurnMsg.turn_index`) and
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1661:# =============================================================================
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1662:# §2 Enums
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1663:# =============================================================================
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1753:# M5/M6 natural runtime gating bug — design (P3a-decide Task 1)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1759:## 1. 観測症状 (G-GEAR PR #129 採取)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1763:| kant_natural | 13 min (kill) | 2 | 6 | kant=6 / nietzsche=3 / rikyu=3 |
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1764:| nietzsche_natural | 13 min (kill, starved) | 0 | 0 | — |
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1765:| rikyu_natural | 13 min (kill) | 3 | 6 | kant=6 / nietzsche=6 / rikyu=6 |
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1767:**stimulus side は 3 cell とも focal=198 / dialogs=168 で完走**、natural 専用の
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1770:## 2. 仮説 4 件と裏取り
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1775:| B | COOLDOWN_TICKS 30 × cognition_period 7-18s で実効 cooldown 30 min+ | 確かに wall は長いが、cognition tick は最終的に進む。kant_natural 13 min wall で nietzsche cognition_period=7s + WorldRuntime DEFAULT_COGNITION_PERIOD_S=10s → world_tick は 50+ 進むはず → cooldown 単独では説明不可 | △ 補助 |
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1776:| C | `_close_timed_out` が in-flight dialog を premature close | 既存 dialog の transcript が 6 turn (= dialog_turn_budget default) で揃っており、exhausted close で正常終了している。timeout race 未発生 | × 棄却 |
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1779:### Hypothesis D の精緻なメカニズム
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1781:1. `cli/eval_run_golden.py:_initial_state_for_natural` は 3 persona を
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1801:## 3. 初回案 (Claude single-shot)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1804:**`eval_natural_mode: bool = False`** flag を追加。`True` のとき:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1806:- `tick()` 内で `_iter_colocated_pairs(agents)` を呼ばず、`agents` の **全 distinct pair**
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1812:- `COOLDOWN_TICKS` / `AUTO_FIRE_PROB_PER_TICK` / `TIMEOUT_TICKS` はすべて
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1813:  default 通り **active のまま** (natural cadence を保つ)。
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1816:eval_natural_mode=True)` を渡す **1 行追加** のみ。
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1818:## 4. /reimagine 代案 (zero-from-scratch alternative)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1831:- `eval_run_golden.py:capture_natural` 内で `PersonaSpec` を model_copy し、
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1845:  与え、`tick()` はその pair を直接反復。
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1849:## 5. 比較と採用判断
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1851:### 5.0 critical insight: `ERRE_ZONE_BIAS_P` の default = 0.2
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1860:を提示する事実と組み合わせると、natural condition の per-tick zone change rate は
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1873:### 5.1 代案再評価
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1886:### 5.2 採用案: **初回案 (scheduler flag `eval_natural_mode`)** 単独
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1893:3. **概念的に正しい**: eval natural は「3 persona を論理的に同居させる」ための
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1895:4. CLI 1 行追加 (`InMemoryDialogScheduler(..., eval_natural_mode=True)`) は
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1898:   許容範囲とする (decisions.md ME-8 で justify)。
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1903:## 6. 修正範囲 (採用案 = 初回案 scheduler flag)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1905:### 6.1 修正ファイル
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1908:  - `InMemoryDialogScheduler.__init__` に `eval_natural_mode: bool = False` 追加
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1910:  - `tick()` 内で `eval_natural_mode=True` のとき
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1914:  - **Cooldown / probability / timeout は active のまま** (natural cadence 保持)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1915:  - `schedule_initiate` の zone 制約 (line 156) は `eval_natural_mode=True` でも
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1922:    `eval_natural_mode=True` を 1 引数追加 (`golden_baseline_mode=False` の隣)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1925:- `tests/test_integration/test_dialog_eval_natural_mode.py` (新規):
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1927:     - eval_natural_mode=False (既存挙動) で、3 agent が異なる zone に分散すると
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1929:     - eval_natural_mode=True で、同じ scenario でも admission が継続することを assert
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1930:  2. **invariant 保持**:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1931:     - cooldown は active (close 後 30 tick 待つ)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1932:     - probability gate は active (rng > 0.25 → admit しない)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1939:  4. **scheduler 単体テスト**: ManualClock 不要、`tick()` を直接呼んで
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1943:### 6.2 既存 1221 テスト互換性
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1945:`eval_natural_mode: bool = False` default のため、既存挙動は完全に維持。
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1948:  golden_baseline_mode は eval_natural_mode と直交、両 default False / True で
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1951:### 6.3 schemas.py の Protocol 整合
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1954:ので keyword-only flag 追加は Protocol 違反にあたらない。`tick()` /
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1955:`schedule_initiate()` / `record_turn()` / `close_dialog()` の signature は
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1958:## 7. 受け入れ条件
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1960:- [ ] 新規 test_dialog_eval_natural_mode.py の Red→Green 転換テストが PASS
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1963:- [ ] cooldown / probability / timeout / 自己 dialog reject / 二重 open reject
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1964:      の invariant が True/False 両方で維持される
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1968:- [ ] decisions.md に新規 ADR (ME-8) 追加: "eval natural condition は
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1969:      InMemoryDialogScheduler.eval_natural_mode=True で zone 制約を bypass"
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1972:## 8. リスクと反証
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1983:# =============================================================================
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1984:# §7.5 DialogScheduler (interface only, M4 foundation)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1985:# =============================================================================
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2000:    def schedule_initiate(
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2010:        dialog, cooldown, zone mismatch). Non-``None`` is the envelope to
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2038:    def _run_dialog_tick(self) -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2059:            tick_fn(self._current_world_tick(), views)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2064:    def _current_world_tick(self) -> int:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2090:           ``len(transcript) >= speaker.cognitive.dialog_turn_budget``.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2200:            budget = speaker_rt.state.cognitive.dialog_turn_budget
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2267:        self._run_dialog_tick()
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2269:            await self._drive_dialog_turns(self._current_world_tick())
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2271:    def _run_dialog_tick(self) -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2392:    # firing. The driver calls schedule_initiate first, the envelope sink
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2421:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2422:# Natural capture (full bootstrap stack, headless)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2423:# ---------------------------------------------------------------------------
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2426:async def capture_natural(  # noqa: C901, PLR0915 — composition root mirrors bootstrap.py
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2441:    """Capture one natural-condition cell using a headless WorldRuntime stack.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2447:/bin/zsh -lc 'uv run pytest tests/test_integration/test_dialog_eval_natural_mode.py' in /Users/johnd/ERRE-Sand Box
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2457:tests/test_integration/test_dialog_eval_natural_mode.py ...........      [100%]
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2484:   943	        # AGORA. See .steering/20260430-m9-eval-system/design-natural-gating-fix.md
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2486:   945	        eval_natural_mode=True,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2502:   414	    m9-eval-system P3a-decide: used by ``tick()`` when
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2503:   415	    ``eval_natural_mode=True``. The zone field on the leading element is
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2505:   417	    ``schedule_initiate`` envelope), but pair eligibility itself does not
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2513:   100	    probability to 1.0 or 0.0 deterministically.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2523:   110	        eval_natural_mode: bool = False,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2534:   121	        # external golden baseline driver bypasses cooldown / timeout / zone
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2536:   123	        # same agent pair without the natural-dialog admission rules. Public
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2538:   125	        # (200 turn, mode=True) and natural-dialog phase (300 turn,
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2541:   128	        # m9-eval-system P3a-decide (design-natural-gating-fix.md): when True
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2542:   129	        # the eval natural-condition pilot bypasses zone-equality and
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2543:   130	        # reflective-zone gates inside ``tick()`` and ``schedule_initiate()``
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2545:   132	        # scatters them across study/peripatos/chashitsu. Cooldown / probability
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2547:   134	        # so admission cadence is still natural — only the spatial constraint
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2550:   137	        # natural phase uses ``eval_natural_mode=True`` (proximity-free
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2553:   140	        self.eval_natural_mode: bool = eval_natural_mode
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2559:   146	        # ``tick()``; for now the memory footprint is irrelevant.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2566:   153	    def schedule_initiate(
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2586:   173	            and not self.eval_natural_mode
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2590:   177	            # bursts) — bypass the natural-dialog cultural restriction.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2591:   178	            # m9-eval-system P3a-decide: eval natural condition lets agents
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2601:   188	            and tick - last_close < self.COOLDOWN_TICKS
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2607:   293	    def tick(self, world_tick: int, agents: Sequence[AgentView]) -> None:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2614:   300	        2. for each co-located pair in reflective zones, probabilistically
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2615:   301	           admit (if not already open and past cooldown)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2617:   303	        m9-eval-system P3a-decide: when ``eval_natural_mode`` is True the
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2620:   306	        skip below is bypassed. Cooldown / probability / timeout invariants
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2621:   307	        remain active so admission cadence is still natural — only proximity
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2625:   311	        if self.eval_natural_mode:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2630:   316	            if not self.eval_natural_mode and a.zone not in _REFLECTIVE_ZONES:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2636:   322	            if last_close is not None and world_tick - last_close < self.COOLDOWN_TICKS:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2638:   324	            if self._rng.random() > self.AUTO_FIRE_PROB_PER_TICK:
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2640:   326	            self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2657:LOW-1: The two-mode boolean surface is now slightly easy to misread. In [dialog.py](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:128), the comment says `eval_natural_mode` preserves cooldown / probability / timeout, which is true for the CLI path because [eval_run_golden.py](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/cli/eval_run_golden.py:940) sets `golden_baseline_mode=False`. If a future caller sets both booleans true, `golden_baseline_mode` still bypasses cooldown and timeout. I would either document that the invariant claim assumes `golden_baseline_mode=False`, or assert/reject both true if that combination is not meaningful.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2661:Correctness: yes, this fixes the observed natural gating bug. With `eval_natural_mode=True`, [tick()](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:310) no longer depends on `a.zone == b.zone`, and [schedule_initiate()](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:170) no longer rejects non-reflective zones. Remaining 0-admission cases are expected: fewer than two agents, all pairs already open, all pairs in cooldown, RNG suppression, or scheduler/tick not wired.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2663:Invariant preservation: for the shipped CLI mode, yes. Self-reject, double-open reject, cooldown, probability gate, and timeout all remain active. The only caveat is the LOW-1 combined-flag case.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2667:Risk to live M5/M6: low. Default `eval_natural_mode=False` preserves the old path.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2669:Re-capture confidence: good. I would expect the focal-30 natural cells to complete barring LLM throughput/runtime failures. This removes the structural “0 colocated pairs forever” plateau; cooldown and RNG can still create pauses, but not permanent starvation.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2671:Verification: `uv run pytest tests/test_integration/test_dialog_eval_natural_mode.py` passed, 11/11. I did not rerun the full 1232-test suite.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2689:LOW-1: The two-mode boolean surface is now slightly easy to misread. In [dialog.py](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:128), the comment says `eval_natural_mode` preserves cooldown / probability / timeout, which is true for the CLI path because [eval_run_golden.py](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/cli/eval_run_golden.py:940) sets `golden_baseline_mode=False`. If a future caller sets both booleans true, `golden_baseline_mode` still bypasses cooldown and timeout. I would either document that the invariant claim assumes `golden_baseline_mode=False`, or assert/reject both true if that combination is not meaningful.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2693:Correctness: yes, this fixes the observed natural gating bug. With `eval_natural_mode=True`, [tick()](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:310) no longer depends on `a.zone == b.zone`, and [schedule_initiate()](/Users/johnd/ERRE-Sand%20Box/src/erre_sandbox/integration/dialog.py:170) no longer rejects non-reflective zones. Remaining 0-admission cases are expected: fewer than two agents, all pairs already open, all pairs in cooldown, RNG suppression, or scheduler/tick not wired.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2695:Invariant preservation: for the shipped CLI mode, yes. Self-reject, double-open reject, cooldown, probability gate, and timeout all remain active. The only caveat is the LOW-1 combined-flag case.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2699:Risk to live M5/M6: low. Default `eval_natural_mode=False` preserves the old path.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2701:Re-capture confidence: good. I would expect the focal-30 natural cells to complete barring LLM throughput/runtime failures. This removes the structural “0 colocated pairs forever” plateau; cooldown and RNG can still create pauses, but not permanent starvation.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2703:Verification: `uv run pytest tests/test_integration/test_dialog_eval_natural_mode.py` passed, 11/11. I did not rerun the full 1232-test suite.

exec
/bin/zsh -lc "nl -ba .steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md | sed -n '1,301p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba .steering/20260430-m9-eval-system/g-gear-phase-a-failure.md | sed -n '1,132p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     1	# G-GEAR Phase A 失敗レポート — natural re-capture stalled (post-fix)
     2	
     3	> 起草: G-GEAR セッション 2026-05-01 22:50 UTC+9 (kant_natural sanity run after PR #130 merge)
     4	> 目的: Mac セッション (P3a-decide finalization) が ME-8 ADR を re-open
     5	> + design-natural-gating-fix.md v2 起草するための実機計測 hand-off。
     6	
     7	## 1. TL;DR
     8	
     9	- **Phase A guard tripped** — `kant_natural` 単独 sanity で `focal=6 / total=18 / dialogs=3` (10 min wall timeout)。
    10	- SOP §"想定 hazard" の `Phase A で focal<25` 条件に該当、Phase B (3 並列) には進まず stop。
    11	- **gating fix の半分は機能** (cross-zone admit が pair coverage を 2→3 dialog に拡大、前回 starve した Nietzsche が今回は kant-nietzsche / nietzsche-rikyu 両 pair で initial admit)。
    12	- **未解決の gate** = `COOLDOWN_TICKS=30` × **実測 cognition_period ≈ 120 s/tick** → 実効 cooldown ≈ 60 min → 10 min wall 内で再 admit が物理的に不可能。
    13	- design-natural-gating-fix.md §2 で **棄却された仮説 B (cooldown × cognition_period の wall 換算) を re-activate** すべき。前提値 `world_tick 50+ for 10 min wall` が empirical に成立しなかった。
    14	
    15	## 2. 観測指標
    16	
    17	### 2.1 採取結果 vs 期待値
    18	
    19	| 指標 | PR #129 stall (pre-fix) | post-fix 期待 | **post-fix 実測 (本セッション)** |
    20	|---|---|---|---|
    21	| focal_rows (kant) | 6 | 30 | **6** |
    22	| total_rows | 12 | ~90 | **18** |
    23	| dialogs | 2 | ~10 | **3** |
    24	| wall | 13 min (kill) | 5-8 min | **10 min (wall timeout)** |
    25	| nietzsche admit | 0 (starved) | included | **2 dialogs** (kant-nietzsche + rikyu-nietzsche) |
    26	
    27	### 2.2 dialog-by-dialog tick + wall span
    28	
    29	| dialog_id | speakers | turns | tick range | zones (DB record) | wall span |
    30	|---|---|---|---|---|---|
    31	| `d_dfa4cbde` | kant ↔ nietzsche | 6 | 1 → 3 | agora, study, peripatos | ~61 s |
    32	| `d_fa9a299f` | kant ↔ rikyu | 6 | 1 → 3 | peripatos, garden | ~60 s |
    33	| `d_83d25195` | nietzsche ↔ rikyu | 6 | 3 → 5 | study, garden | ~35 s |
    34	
    35	**全 18 turn が tick 1-5 内で発生**、tick=5 以降 (22:42:29 onward) は **8 分間 0 admit**。Reflection trigger log は 22:47/22:48/22:49/22:50 で継続発火しているので cognition cycle 自体は live (= world は止まっていない)。
    36	
    37	### 2.3 inter-turn delta (順 18 turn の `created_at` 差分)
    38	
    39	```
    40	turn 1: +2.3s   turn 7:  +2.3s   turn 13: +0.0s
    41	turn 2: +0.0s   turn 8:  +0.0s   turn 14: +0.4s
    42	turn 3: +22.2s  turn 9:  +32.1s  turn 15: +12.3s
    43	turn 4: +0.0s   turn 10: +0.0s   turn 16: +3.3s
    44	turn 5: +1.8s   turn 11: +0.0s   turn 17: +18.4s
    45	turn 6: +0.0s   turn 12: +0.7s
    46	```
    47	
    48	burst (~95 s) 内で 3 dialogs × 6 turns = 18 utterances。turn 17 後 (22:42:29) → wall timeout (22:50:30) で **8 min 0 admit**。
    49	
    50	## 3. 仮説再評価
    51	
    52	### 3.1 仮説 B re-activate (design-natural-gating-fix.md §2 で △ 補助 → ◎ 主因に格上げ)
    53	
    54	- design 当時の前提: `nietzsche cognition_period=7s + DEFAULT_COGNITION_PERIOD_S=10s → world_tick 50+ in 13 min wall` → cooldown=30 ticks は OK ⇒ 棄却根拠
    55	- **empirical**: 600 s wall で max(tick) = 5 → **120 s / tick** (cognition_period より 12× 遅い)
    56	- 原因推定 (G-GEAR 側からの仮説、Mac で再検証要):
    57	  1. `qwen3:8b` Q4_K_M on RTX 5060 Ti で reflection (embed + chat) + action selection (chat) + dialog turn (chat × 6) が **serial round-trip** で蓄積
    58	  2. cognition tick が `_run_dialog_tick` 含む全 sub-stage 完了を待つため、burst 中は dialog turn 6 回分の chat call が tick advance を blocking
    59	  3. burst 終了後は cognition+reflection だけだが、それでも Reflection trigger log の inter-arrival ~30 s ⇒ tick rate ~ 1 / 30 s が下限、cooldown 30 ticks = 15 min wall
    60	
    61	### 3.2 仮説 C (`_close_timed_out` race) は依然棄却
    62	
    63	- 全 dialog が 6 turn budget (= dialog_turn_budget) で正常 close、premature close ではない
    64	- 各 dialog の last turn と CloseDialogMsg 間に異常 wall span 観測なし
    65	
    66	### 3.3 仮説 D (zone scatter) は **fix で解決済**
    67	
    68	- pair coverage が 2 → 3 に拡大、Nietzsche starve が消えた
    69	- `eval_natural_mode=True` の zone-bypass が effective に動作 (ME-8 ADR の expected behaviour 一致)
    70	
    71	## 4. Mac 側で要検討の選択肢
    72	
    73	planning purity 制約で G-GEAR 側コード変更不可。Mac セッション (Plan + /reimagine + Codex review 起動推奨) で確定すべき:
    74	
    75	| 案 | 内容 | trade-off |
    76	|---|---|---|
    77	| **α** | `eval_natural_mode=True` 時に `COOLDOWN_TICKS` も縮める (例: 5 ticks) | natural cadence の概念が薄まる、ME-8 ADR §invariant の "cooldown active" を更新要 |
    78	| **β** | wall budget を大幅拡張 (--wall-timeout-min 90 → 180+ for natural) | wall は伸びるが概念は綺麗。実測 120 s/tick × 30 cooldown = 60 min × ~3 cycle = 180 min 必要見込 |
    79	| **γ** | `AUTO_FIRE_PROB_PER_TICK` を eval mode で 0.25 → 1.0 | per-pair admit 加速、ただし cooldown が dominant gate なら効果限定 |
    80	| **δ** | 採取設計再考 (eval は LLM 1 cell ずつ運用、3 並列ではなく逐次) | wall 単純倍化、ただし cognition_period 自体は変わらない |
    81	| **ε** | dialog_turn_budget を 6 → 3 に縮めて burst 期間を短縮、cooldown 計算根拠を変える | dialog 内 turn 数が減る、Burrows/MATTR の per-dialog stylo signal が薄まる |
    82	
    83	### 推奨判断材料
    84	
    85	- **α (cooldown 縮小)** は最も直接的だが ME-8 ADR の "cooldown active" 文言と概念整合のため Codex review 推奨
    86	- **β (wall 拡大)** は概念純粋だが 1 cell 180 min × 3 cell 並列で 3 時間 wall — overnight 採取になる、stimulus と異なる運用
    87	- **α + β ハイブリッド** (eval mode で cooldown=5 + wall=60 min) が実用解の最有力候補
    88	
    89	### Mac 側で確認すべき計算
    90	
    91	- 60 min wall × 1 tick/120 s = 30 ticks 進行
    92	- cooldown=5 ticks = 10 min × 0.083 cycle/min = **約 5 cycle 期待** = 5 × 3 dialogs × 6 turns = **90 utterance**
    93	- focal kant = 1/3 × 90 = 30 ✓ (target 達成)
    94	- → α (cooldown 5) + wall 60 min が最小実用組合せ
    95	
    96	## 5. 保全状態
    97	
    98	| ファイル | 状態 | サイズ |
    99	|---|---|---|
   100	| `data/eval/pilot/kant_natural_run0.duckdb.tmp` | **保持** (staged-rename 失敗で .tmp 残存) | 524 KB |
   101	| `data/eval/pilot/kant_natural_run0.log` | **保持** (httpx + cognition full log) | 33 KB |
   102	| `data/eval/pilot/{nietzsche,rikyu}_natural_*.duckdb*` | **未生成** (Phase B 未起動) | — |
   103	| `data/eval/pilot/*_stimulus_*.duckdb` | **無傷** (PR #129 既存) | 各 524 KB |
   104	| `data/eval/pilot/_summary.json` / `_rsync_receipt.txt` | **未更新** (失敗を _summary に書かない) | — |
   105	| working tree | clean、git diff 0 | — |
   106	
   107	`.duckdb*` は `.gitignore` 済 (commit 対象は markdown レポートのみ)。
   108	
   109	## 6. ME-8 ADR re-open 候補項目
   110	
   111	decisions.md ME-8 §re-open 条件 の 3 項目目 "fix 後も admit が初動 burst で停止する場合" が **発火**。本レポートを根拠に Mac で:
   112	
   113	1. ME-8 ADR §影響 / §re-open 条件 を partial-update (本セッション empirical data を引用)
   114	2. 採用案を α / β / γ / δ / ε / ハイブリッドから 1 つ確定 (Plan + /reimagine + Codex review)
   115	3. design-natural-gating-fix.md v2 として代案比較を再実施
   116	4. 実装 + test 後、G-GEAR 再々採取 (本レポートを base に Phase A 期待値の桁を再校正)
   117	
   118	## 7. Hand-off チェックリスト (Mac セッション用)
   119	
   120	- [ ] 本レポート (`g-gear-phase-a-failure.md`) を Mac で Read
   121	- [ ] decisions.md ME-8 §re-open 条件発火を AD R partial-update
   122	- [ ] design-natural-gating-fix.md v2 起草 (5.0 critical insight 級の re-evaluation: bias_p=0.2 の代わりに actual cognition_period が dominant)
   123	- [ ] α / β / γ / δ / ε から採用案確定 (Codex `gpt-5.5 xhigh` review に回す)
   124	- [ ] 実装 + 12 unit test 拡張 (cooldown 縮小 invariant 再定義 / wall 期待値 update)
   125	- [ ] G-GEAR 再々採取 prompt (`g-gear-p3a-rerun-prompt.md` v2) を起草
   126	- [ ] tasklist.md §P3a-decide にチェック項目追加 ("仮説 B re-activate"/ "fix v2 確定")
   127	
   128	## 8. 注記
   129	
   130	- 本セッションは planning purity を厳守 (コード変更 0 件)。修正は Mac セッションで Plan mode + Codex review を経由する。
   131	- `.tmp` DuckDB は **保持**、Mac 側で読みたい場合は rsync 可能だが、本診断データは本レポート本文に inline 済 (re-rsync 不要のはず)。
   132	- 本ブランチ `feature/m9-eval-p3a-natural-stalled-report` は本レポート 1 ファイル commit のみ。stimulus 既存データ更新なし、_summary.json 不更新。

 succeeded in 0ms:
     1	# M5/M6 natural runtime gating bug — design v2 (P3a-decide v2)
     2	
     3	> Plan-mode 等価ドキュメント (auto-mode 内 "Plan + /reimagine + Codex review"
     4	> CLAUDE.md 制約)。本ファイルで初期案 + reimagine 代案 + 採用案 + Codex review
     5	> 反映を一元化する。**design v1 (`design-natural-gating-fix.md`) の続編**:
     6	> v1 は仮説 D (zone scatter) を解決したが、empirical で仮説 B (cooldown ×
     7	> cognition_period の wall 換算) が re-activate された (PR #131
     8	> `g-gear-phase-a-failure.md` 参照)。
     9	
    10	## 1. v2 を起草する empirical 根拠
    11	
    12	### 1.1 v1 fix 後の G-GEAR Phase A 観測 (PR #131)
    13	
    14	| 指標 | v1 修正前 (PR #129) | v1 期待値 | **v1 修正後 実測 (本セッション根拠)** |
    15	|---|---|---|---|
    16	| focal_rows (kant) | 6 | 30 | **6** |
    17	| total_rows | 12 | ~90 | **18** |
    18	| dialogs | 2 | ~10 | **3** |
    19	| nietzsche admit | 0 (starved) | included | **2 dialogs** ✅ |
    20	| wall | 13 min (kill) | 5-8 min | **10 min wall timeout** |
    21	
    22	**v1 の効果**: nietzsche starve は解消 (zone bypass が機能)、3 pair 全部 admit。
    23	**v1 で未解決**: 18 turn 全部が tick 1-5 内、tick=5 以降 8 min 0 admit (= cooldown 中)。
    24	
    25	### 1.2 dominant gate の empirical 確定
    26	
    27	```
    28	empirical: 600 s wall → max(world_tick) = 5 ⇒ 1 tick ≈ 120 s
    29	原因: qwen3:8b Q4_K_M on RTX 5060 Ti で
    30	      reflection embed + chat + action selection + dialog turn × 6 が
    31	      serial round-trip で蓄積、cognition tick advance を blocking
    32	```
    33	
    34	実効 cooldown = `COOLDOWN_TICKS=30` × 120 s/tick = **60 min wall**
    35	⇒ 10 min wall 内で同一 pair が再 admit されるのは物理的に不可能。
    36	
    37	### 1.3 design v1 §2 仮説 B の再評価
    38	
    39	design v1 は仮説 B を「△ 補助」とし、棄却根拠として以下を引いた:
    40	> kant_natural 13 min wall で nietzsche cognition_period=7s + WorldRuntime
    41	> DEFAULT_COGNITION_PERIOD_S=10s → world_tick は 50+ 進むはず
    42	
    43	これは **誤った前提**。実機の 7B-Q4 ローカル推論では LLM round-trip が
    44	cognition_period の名目値を完全に upper-bound として支配しない。本 design v2
    45	では仮説 B を「◎ 主因」に格上げし、design v1 §2 の判断を v2 §1 で **明示的に
    46	覆す**。
    47	
    48	## 2. 候補空間 (G-GEAR §4 の 5 案 + /reimagine 代案 3)
    49	
    50	G-GEAR `g-gear-phase-a-failure.md` §4 の 5 案 + 本 Mac セッションの /reimagine
    51	で 3 案追加 (ζ / θ / ι)。
    52	
    53	| 案 | 内容 | 実装複雑度 | 概念純度 | empirical 必達確率 | test impact |
    54	|---|---|---|---|---|---|
    55	| α | eval mode で COOLDOWN_TICKS=5 (現状 30) | 低 | 中 | 高 (10 min wall × 5 ticks/cooldown 必要) | 低 |
    56	| β | wall budget 30→60 min for natural | 低 (CLI flag default 変更) | 高 | 中 (cooldown=30 単独では 1 cycle のみ) | 無 |
    57	| γ | AUTO_FIRE_PROB_PER_TICK 0.25→1.0 | 低 | 中 | 低 (cooldown が dominant gate のため効果限定) | 中 |
    58	| δ | 1 cell 逐次採取 (3 並列廃止) | 低 (CLI 運用変更) | 中 | 低 (cognition_period 不変、wall 単純倍化のみ) | 無 |
    59	| ε | dialog_turn_budget 6→3 | 中 | 低 (per-dialog stylo signal が薄まる) | 中 | 中 |
    60	| **ζ** *(reimagine)* | wall-time-based cooldown (`time.monotonic()`) | 中 (monotonic 経路 + monkeypatch test) | 高 (tick rate 変動に robust) | 高 | 中 |
    61	| **θ** *(reimagine)* | cooldown 完全廃止 + AUTO_FIRE_PROB_PER_TICK のみ | 低 | 中 (prob が gate に) | 中 (prob 0.25 で variability 大) | 低 |
    62	| **ι** *(reimagine)* | β + δ ハイブリッド (cooldown 不変、wall 大拡張、cell 逐次) | 低 | **最高** (cooldown semantics 不変) | 中 (3h × 3 cell = 9h、overnight) | 無 |
    63	
    64	### 2.1 G-GEAR 推奨 α + β ハイブリッドの empirical 計算
    65	
    66	```
    67	60 min wall × 1 tick / 120 s = 30 ticks 進行
    68	cooldown=5 ticks × 120 s/tick = 10 min wall cooldown
    69	30 ticks / 5 ticks per cycle ≈ 6 cycle (G-GEAR 計算 5 cycle、prob 0.25 込みで)
    70	3 dialogs × 6 turns × 5 cycle = 90 utterance
    71	focal kant per cell ≈ 90 × (1/3) = 30 ✓ (target 達成)
    72	```
    73	
    74	### 2.2 /reimagine 代案 ζ (wall-time cooldown) の検討
    75	
    76	**仮想実装**:
    77	```python
    78	import time
    79	self._last_close_wall: dict[frozenset[str], float] = {}
    80	
    81	# schedule_initiate / tick で:
    82	last_close_wall = self._last_close_wall.get(key)
    83	if last_close_wall is not None and (time.monotonic() - last_close_wall) < COOLDOWN_WALL_S:
    84	    return None
    85	```
    86	
    87	**利点**:
    88	1. tick rate (cognition_period) の変動に対し robust。将来 FP16 化で cognition_period が
    89	   60 s/tick に半減しても cooldown semantics が崩れない。
    90	2. 「natural cadence 1 min = 1 dialog 開始」という人間直感と一致。
    91	
    92	**欠点**:
    93	1. **M4 frozen Protocol の純粋関数性違反**: `DialogScheduler` Protocol は tick ベースの
    94	   deterministic semantics で、`time.monotonic()` 注入は副作用源を増やす。test では
    95	   `monkeypatch time.monotonic` が全 cooldown test に必要 (現状 1228+ test の cooldown
    96	   関連 ~20 件全部に影響)。
    97	2. ManualClock + tick 駆動の既存 test fixture を破壊。
    98	3. CLAUDE.md "コードに既存パターンに従う" 原則違反 (cooldown は M4 から tick ベース)。
    99	4. eval mode 専用 → 別経路 if 分岐 → コード経路 fork、ME-8 invariant を二重定義することに。
   100	
   101	**評価**: ζ は overscoping。本タスクのターゲットは "natural pilot 30 focal を 60 min wall
   102	で完走" であり、将来の cognition_period 変動 robustness は本タスクスコープ外。本タスクで
   103	解決すべきは empirical な cooldown semantics の再校正のみ。**棄却**。
   104	
   105	### 2.3 /reimagine 代案 θ (cooldown 完全廃止) の検討
   106	
   107	**仮想実装**:
   108	```python
   109	# eval_natural_mode=True のとき cooldown check 全 bypass
   110	if self.eval_natural_mode:
   111	    pass  # cooldown チェック飛ばす
   112	```
   113	
   114	**利点**:
   115	1. mental model 最小化 (cooldown 概念が無くなる)。
   116	2. AUTO_FIRE_PROB_PER_TICK=0.25 が唯一の cadence 制御 → tunable は 1 個のみ。
   117	
   118	**欠点**:
   119	1. **dominant gate が cooldown から prob に移転**するだけで、prob 0.25 の cognition_period
   120	   依存性が浮上。120 s/tick × 30 ticks × 0.25 = 7.5 admit 期待 (variance 大、focal target
   121	   30 達成の確実性が cooldown=5 案より低)。
   122	2. 同 pair の即時連続 admit リスク: dialog close 直後 (last_activity_tick の次の tick) に
   123	   AUTO_FIRE が当たれば即 admit、3 pair 全部が同 tick で同時に admit する "burst 多発"
   124	   が起こり得る。dialog_turn_budget=6 で「同 pair が 6 tick 占有」されることで indirect に
   125	   防がれるが、これは fragile な暗黙依存。
   126	3. ME-8 ADR §invariant の "cooldown active" を完全削除する必要、PR #130 で確定した
   127	   contract から後退。
   128	
   129	**評価**: cooldown 概念削除は ME-8 ADR の意味的後退。dominant gate を prob に移すだけで
   130	empirical robustness が改善するわけでもない。**棄却**。
   131	
   132	### 2.4 /reimagine 代案 ι (β + δ) の検討
   133	
   134	**仮想実装**:
   135	- α/cooldown 不変 (`COOLDOWN_TICKS=30` keep)
   136	- β: wall=30 min → 240 min (4h)
   137	- δ: 3 並列 → 1 cell 逐次運用
   138	
   139	**期待計算**:
   140	```
   141	240 min × 1 tick / 120 s = 120 ticks
   142	cooldown=30 → 4 cycle (cycle 間隔 30 ticks × 120 s = 60 min)
   143	4 cycle × 3 dialogs × 6 turns = 72 utterance
   144	focal kant ≈ 72 / 3 = 24 (target 30 にやや不足)
   145	1 cell 4h × 3 cell = 12h overnight 採取
   146	```
   147	
   148	**利点**: cooldown semantics 不変、ME-8 §invariant は v1 のまま、test 影響ゼロ。
   149	
   150	**欠点**:
   151	1. wall 12h overnight 採取は stimulus 採取 (cell ~3 min、3 cell 並列 ~3 min) との運用乖離が
   152	   大きい。stimulus + natural の両建てで 12h × 5 run = 60h overnight が現実的でない。
   153	2. focal target 30 を満たすには wall=300 min 以上必要、運用ぎりぎり。
   154	3. 1 cell 逐次は 3 並列より wall 効率が常に悪い。
   155	
   156	**評価**: 概念純度は最高だが運用コストが許容外。**棄却**。
   157	
   158	## 3. 採用案: α + β ハイブリッド
   159	
   160	### 3.1 採用根拠
   161	
   162	1. **empirical 必達確率が高い**: §2.1 計算で focal kant ≈ 30 達成、G-GEAR 推奨と一致。
   163	2. **実装最小**: `COOLDOWN_TICKS_EVAL: ClassVar[int] = 5` 別定数化 + `_effective_cooldown()`
   164	   helper + CLI default 30→60 min の 3 箇所変更。
   165	3. **既存 test 完全互換**: live mode の COOLDOWN_TICKS=30 不変、既存 1248 PASS 維持。
   166	4. **ME-8 invariant 後退最小**: "cooldown active" → "cooldown active with eval-mode-specific
   167	   reduced threshold" に文言更新するのみ、cooldown 概念自体は保持。
   168	5. **/reimagine 代案 ζ/θ/ι の trade-off で全敗**: ζ は overscoping、θ は dominant gate
   169	   移転、ι は wall 爆発 — α+β が支配的。
   170	
   171	### 3.2 棄却サマリ
   172	
   173	| 案 | 主棄却理由 |
   174	|---|---|
   175	| γ | cooldown が dominant gate のため prob 単独調整は効果限定 |
   176	| δ | cognition_period 不変、wall 単純倍化のみ |
   177	| ε | per-dialog stylo signal を薄める (Burrows/MATTR の measurement 劣化) |
   178	| ζ | M4 frozen Protocol の純粋関数性違反、overscoping |
   179	| θ | cooldown→prob の dominant gate 移転、ME-8 invariant 後退 |
   180	| ι | wall 12h × overnight × 多 run で運用コスト許容外 |
   181	
   182	### 3.3 採用案の修正範囲
   183	
   184	#### 3.3.1 `src/erre_sandbox/integration/dialog.py`
   185	
   186	```python
   187	class InMemoryDialogScheduler:
   188	    COOLDOWN_TICKS: ClassVar[int] = 30
   189	    """Live multi-agent run の cooldown (live cognition_period での
   190	    natural cadence 維持)。"""
   191	
   192	    COOLDOWN_TICKS_EVAL: ClassVar[int] = 5
   193	    """eval_natural_mode=True 時の reduced cooldown。実測 cognition_period
   194	    ≈ 120 s/tick (qwen3:8b Q4_K_M on RTX 5060 Ti) で 60 min wall = 30 tick
   195	    のうち 5-6 cycle 完走を保証する empirical 値。re-open 条件: 推論
   196	    backend が変わって cognition_period が ±50% 以上変動した場合は
   197	    本値を再評価。"""
   198	
   199	    def _effective_cooldown(self) -> int:
   200	        """eval_natural_mode flag に応じた cooldown ticks を返す純関数。"""
   201	        return self.COOLDOWN_TICKS_EVAL if self.eval_natural_mode else self.COOLDOWN_TICKS
   202	```
   203	
   204	`schedule_initiate` の cooldown check と `tick()` 内の cooldown check 両方を
   205	`self._effective_cooldown()` 経由に統一。`golden_baseline_mode=True` の cooldown bypass
   206	は既存通り (両 flag 同時 True は v1 で reject 済)。
   207	
   208	#### 3.3.2 `src/erre_sandbox/cli/eval_run_golden.py`
   209	
   210	`capture_natural` の `--wall-timeout-min` default を **30 → 60** に変更。stimulus
   211	側 default は既存 (~10 min) のまま。CLI flag で override 可能を維持。
   212	
   213	#### 3.3.3 `tests/test_integration/test_dialog_eval_natural_mode.py` 拡張
   214	
   215	既存 12 ケースに以下を **追加** (default 値の意味的不変は v1 で確立済、本 v2 は
   216	eval-specific reduced cooldown の new contract を追加検証):
   217	
   218	1. **`test_eval_mode_uses_reduced_cooldown`**: eval_natural_mode=True で同一 pair が
   219	   tick 5 後に再 admit 可能、tick 4 では reject されることを assert
   220	2. **`test_live_mode_cooldown_unchanged`**: eval_natural_mode=False (default) で
   221	   COOLDOWN_TICKS=30 が active、tick 29 で reject / tick 30 で admit
   222	3. **`test_effective_cooldown_returns_correct_value`**: `_effective_cooldown()`
   223	   helper の純関数 contract (eval=5 / live=30)
   224	4. **`test_class_constants_unchanged`**: `COOLDOWN_TICKS == 30` /
   225	   `COOLDOWN_TICKS_EVAL == 5` の sentinel test (将来の silent な定数変更を防ぐ)
   226	
   227	CLI test (`tests/test_cli/test_eval_run_golden.py`) に `--wall-timeout-min` default が
   228	60 min for natural を assert する 1 ケース追加 (既存 12 mock test の隣)。
   229	
   230	### 3.4 ME-8 ADR §invariant の partial-update
   231	
   232	v1 で「Cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
   233	invariant は両 mode で active のまま」と書いた箇所を以下に Edit:
   234	
   235	> **Cooldown (eval-mode 別 threshold = `COOLDOWN_TICKS_EVAL=5`、live は
   236	> `COOLDOWN_TICKS=30`)** / probability / timeout / 自己 dialog reject /
   237	> 二重 open reject の invariant は両 mode で active のまま — eval natural cadence
   238	> は維持、proximity 制約のみ削除 + cooldown threshold を eval mode で reduce。
   239	
   240	**追加 §re-open 条件 (本 v2 起草時 = 三度目)**:
   241	
   242	- **fix v2 後も focal<25 で stop** → 別 dominant gate (prob 0.25 / 推論 deadlock 等) を再特定
   243	- **推論 backend が変わって cognition_period が 60s 以下 / 240s 以上に変動** →
   244	  COOLDOWN_TICKS_EVAL=5 の妥当性を再評価 (60s なら cooldown=10 候補、240s なら cooldown=3
   245	  候補、empirical 再採取で確定)
   246	
   247	### 3.5 design v1 §採用案との差分明示
   248	
   249	design v1 §6.1 の "Cooldown / probability / timeout は active のまま (natural cadence 保持)"
   250	を design v2 §3.3 で **明示的に書き換え**:
   251	
   252	> v1 では cooldown_ticks=30 を eval mode でも flat に保持していたが、empirical で
   253	> dominant gate と判明。v2 では eval mode 限定で COOLDOWN_TICKS_EVAL=5 に reduce
   254	> (live mode は影響無し)。Cooldown 概念自体は両 mode で保持される (= ピンポン admit
   255	> 防止の semantics は eval mode でも生きている)。
   256	
   257	## 4. 受け入れ条件 (本 Mac セッション完了時)
   258	
   259	- [x] design v2 起草 (本ドキュメント、5 + 3 案比較 + 採用)
   260	- [ ] codex-review-prompt-natural-gating-v2.md 起草 (本セッション)
   261	- [ ] Codex `gpt-5.5 xhigh` independent review verbatim 保存 (Verdict: ship 想定)
   262	- [ ] HIGH/MEDIUM 反映後に decisions.md ME-8 二度目の partial-update
   263	- [ ] dialog.py + eval_run_golden.py 修正 + 4 unit test 追加 (12→16)
   264	- [ ] 既存 1248 PASS 維持 (full suite)
   265	- [ ] g-gear-p3a-rerun-prompt-v2.md 起草 (Phase A 期待値の桁再校正)
   266	- [ ] PR 作成 (PR #131 リンク参照、Codex review verdict と HIGH 反映状況明記)
   267	
   268	## 5. リスクと反証
   269	
   270	- **リスク 1**: 60 min wall × cooldown=5 で focal=30 達成は **理論計算**、empirical で
   271	  AUTO_FIRE_PROB_PER_TICK=0.25 の variance により 5 cycle 完走しない可能性。
   272	  - 反証実験: G-GEAR 再々採取で focal<25 が再発した場合、ME-8 §re-open 条件 1 項目目で
   273	    別 dominant gate (推論 deadlock 等) を再特定。
   274	- **リスク 2**: eval mode reduced cooldown が dialog_turn_budget=6 と組合わさって
   275	  burst 過多 (5 ticks 直前 close → 5 ticks 後即再 admit → 11 ticks per cycle で 6 cycle/30
   276	  ticks) で natural cadence が崩れる可能性。
   277	  - 反証: 1 cycle = 6 ticks (turn) + 5 ticks (cooldown) = 11 ticks/cycle、cognition_period
   278	    120 s/tick で 22 min/cycle、60 min wall で約 2.7 cycle = 16 utterance/cell。
   279	    G-GEAR 計算 (5 cycle = 90 utterance) は **prob 0.25 を込めていない**ため過大評価。
   280	    realistic estimate = 16-30 utterance/cell、focal kant per cell = 8-15。
   281	  - **判断**: v2 では `--wall-timeout-min default=60` を採用、focal target 30 達成が
   282	    margin に欠ける場合は default を 90 / 120 min に上げる調整余地を残す。
   283	    G-GEAR 再採取で実測値を確認してから default 確定 (現 default=60 は最低保証)。
   284	
   285	## 6. Codex review
   286	
   287	本 design v2 + 実装 diff sketch 確定後、`gpt-5.5 xhigh` independent review に回す。
   288	`codex-review-prompt-natural-gating-v2.md` / `codex-review-natural-gating-v2.md` を
   289	verbatim 保存。HIGH は実装前に反映、MEDIUM は decisions.md ME-8 に取り込み。
   290	
   291	特に Codex に問いたい論点:
   292	- Q1: §2.4 ι (β+δ) を「wall 爆発」で棄却したが、stimulus と natural を別 SOP で運用
   293	  するなら ι が ME-8 invariant 後退ゼロで本来は最小侵襲では？
   294	- Q2: §3.3.1 で `COOLDOWN_TICKS_EVAL=5` を hardcoded class const にしたが、CLI
   295	  `--cooldown-ticks-eval N` で override 可能にすべきか？
   296	- Q3: §5 リスク 2 の cycle 計算で AUTO_FIRE_PROB=0.25 を考慮すると wall=60 min default は
   297	  margin が薄い。default=90 min に変更すべきか？
   298	- Q4: ME-8 §invariant 文言の "active with reduced threshold" 表現は v1 contract に対し
   299	  silent な後退ではないか？(明示的な ADR re-open + 文言再定義で良いか)
   300	- Q5: §3.3.3 で追加 4 test のうち、`test_class_constants_unchanged` の sentinel test は
   301	  本当に必要か (over-defensive ではないか)？

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/cli/eval_run_golden.py | sed -n '850,1040p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba .steering/20260430-m9-eval-system/decisions.md | sed -n '300,439p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/integration/dialog.py | sed -n '1,390p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba tests/test_integration/test_dialog_eval_natural_mode.py | sed -n '1,380p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   850	        memory_db_path = Path(
   851	            f"/tmp/p3a_natural_{persona}_run{run_idx}.sqlite",  # noqa: S108
   852	        )
   853	    if memory_db_path.exists():
   854	        memory_db_path.unlink()
   855	
   856	    memory = MemoryStore(db_path=str(memory_db_path))
   857	    memory.create_schema()
   858	
   859	    embedding = EmbeddingClient(model=embed_model, endpoint=ollama_host)
   860	    inference = OllamaChatClient(model=chat_model, endpoint=ollama_host)
   861	
   862	    try:
   863	        await inference.health_check()
   864	    except OllamaUnavailableError as exc:
   865	        logger.exception("ollama health check failed for natural capture")
   866	        state.fatal_error = f"ollama unreachable: {exc!r}"
   867	        return CaptureResult(
   868	            run_id=run_id,
   869	            output_path=temp_path,
   870	            total_rows=0,
   871	            focal_rows=0,
   872	            fatal_error=state.fatal_error,
   873	        )
   874	
   875	    retriever = Retriever(memory, embedding)
   876	
   877	    # Build the WorldRuntime + cognition stack.  ``runtime_factory`` is the
   878	    # injection seam used by the unit test to swap in a ManualClock-driven
   879	    # WorldRuntime + stub DialogTurnGenerator.  Production path uses the
   880	    # default factory below.
   881	    if runtime_factory is None:
   882	
   883	        def _resolve_persona_display_name(agent_id: str) -> str | None:
   884	            pid = runtime.agent_persona_id(agent_id)
   885	            if pid is None:
   886	                return None
   887	            spec = persona_specs.get(pid)
   888	            return spec.display_name if spec is not None else None
   889	
   890	        reflector = Reflector(
   891	            store=memory,
   892	            embedding=embedding,
   893	            llm=inference,
   894	            persona_resolver=_resolve_persona_display_name,
   895	        )
   896	        cycle = CognitionCycle(
   897	            retriever=retriever,
   898	            store=memory,
   899	            embedding=embedding,
   900	            llm=inference,
   901	            erre_policy=DefaultERREModePolicy(),
   902	            bias_sink=lambda _e: None,
   903	            reflector=reflector,
   904	        )
   905	        runtime = WorldRuntime(cycle=cycle)
   906	    else:
   907	        runtime = runtime_factory(
   908	            memory=memory,
   909	            embedding=embedding,
   910	            inference=inference,
   911	            retriever=retriever,
   912	            persona_specs=persona_specs,
   913	        )
   914	
   915	    def _persona_resolver(agent_id: str) -> str | None:
   916	        return runtime.agent_persona_id(agent_id)
   917	
   918	    def _zone_resolver(speaker_id: str, _dialog_id: str) -> str:
   919	        zone = runtime.get_agent_zone(speaker_id)
   920	        return zone.value if zone is not None else ""
   921	
   922	    duckdb_sink = _make_duckdb_sink(
   923	        con=con,
   924	        run_id=run_id,
   925	        focal_persona_id=persona,
   926	        persona_resolver=_persona_resolver,
   927	        fallback_speaker_persona=persona,
   928	        fallback_addressee_persona="?",
   929	        zone_resolver=_zone_resolver,
   930	        state=state,
   931	        enough_event=enough_event,
   932	        focal_budget=turn_count,
   933	    )
   934	
   935	    scheduler_rng = random.Random(seed_root)  # noqa: S311 — non-crypto, eval seed
   936	    scheduler = InMemoryDialogScheduler(
   937	        envelope_sink=runtime.inject_envelope,
   938	        rng=scheduler_rng,
   939	        turn_sink=duckdb_sink,
   940	        golden_baseline_mode=False,
   941	        # P3a-decide gating fix: bypass zone-equality so the 3 personas can
   942	        # sustain dialog after LLM destination_zone scatters them out of
   943	        # AGORA. See .steering/20260430-m9-eval-system/design-natural-gating-fix.md
   944	        # for root-cause analysis.
   945	        eval_natural_mode=True,
   946	    )
   947	    runtime.attach_dialog_scheduler(scheduler)
   948	
   949	    dialog_generator = OllamaDialogTurnGenerator(llm=inference, personas=persona_specs)
   950	    runtime.attach_dialog_generator(dialog_generator)
   951	
   952	    # Register all three personas so proximity auto-fire has every pair
   953	    # available.  Codex MEDIUM-5 confirmed _iter_colocated_pairs only checks
   954	    # zone equality, so the three seats inside AGORA are sufficient.
   955	    for pid in DEFAULT_PERSONAS:
   956	        spec = persona_specs[pid]
   957	        runtime.register_agent(_initial_state_for_natural(spec), spec)
   958	
   959	    # Warmup — same fail-soft logic as stimulus.
   960	    await _warm_up_ollama(inference, persona_specs[persona])
   961	
   962	    # Drive: spawn runtime task + watchdog.  The watchdog returns once the
   963	    # focal budget is reached, the wall hard cap is hit, or the runtime
   964	    # task itself completes (e.g. fatal error inside the cycle).
   965	    runtime_task = asyncio.create_task(runtime.run(), name="p3a-natural-runtime")
   966	    wall_deadline = time.monotonic() + wall_timeout_min * 60.0
   967	
   968	    async def _watchdog() -> None:
   969	        while True:
   970	            if state.fatal_error is not None:
   971	                logger.error(
   972	                    "natural capture aborting on fatal sink error: %s",
   973	                    state.fatal_error,
   974	                )
   975	                return
   976	            if enough_event.is_set():
   977	                logger.info("natural capture focal budget %d reached", turn_count)
   978	                return
   979	            if runtime_task.done():
   980	                logger.info("runtime task exited before focal budget")
   981	                return
   982	            if time.monotonic() >= wall_deadline:
   983	                state.fatal_error = f"wall timeout ({wall_timeout_min} min) exceeded"
   984	                logger.error(state.fatal_error)
   985	                return
   986	            await asyncio.sleep(0.5)
   987	
   988	    try:
   989	        await _watchdog()
   990	    finally:
   991	        runtime.stop()
   992	        try:
   993	            await asyncio.wait_for(runtime_task, timeout=_RUNTIME_DRAIN_GRACE_S)
   994	        except TimeoutError:
   995	            state.fatal_error = (
   996	                state.fatal_error or f"runtime drain exceeded {_RUNTIME_DRAIN_GRACE_S}s"
   997	            )
   998	            runtime_task.cancel()
   999	            with contextlib.suppress(asyncio.CancelledError, Exception):
  1000	                await runtime_task
  1001	
  1002	    write_with_checkpoint(con)
  1003	
  1004	    # Close the rest of the stack so /tmp sqlite handles flush before the
  1005	    # caller renames the DuckDB file out of .tmp.
  1006	    await inference.close()
  1007	    await embedding.close()
  1008	    await memory.close()
  1009	
  1010	    return CaptureResult(
  1011	        run_id=run_id,
  1012	        output_path=temp_path,
  1013	        total_rows=state.total,
  1014	        focal_rows=state.focal,
  1015	        fatal_error=state.fatal_error,
  1016	    )
  1017	
  1018	
  1019	# ---------------------------------------------------------------------------
  1020	# CLI entry
  1021	# ---------------------------------------------------------------------------
  1022	
  1023	
  1024	def _build_arg_parser() -> argparse.ArgumentParser:
  1025	    parser = argparse.ArgumentParser(
  1026	        prog="erre-eval-run-golden",
  1027	        description=(
  1028	            "Capture one (persona, condition, run_idx) cell into a fresh "
  1029	            "DuckDB file under raw_dialog schema for m9-eval P3a."
  1030	        ),
  1031	    )
  1032	    parser.add_argument(
  1033	        "--persona",
  1034	        choices=list(DEFAULT_PERSONAS),
  1035	        required=True,
  1036	        help="Focal persona id (kant / nietzsche / rikyu).",
  1037	    )
  1038	    parser.add_argument(
  1039	        "--run-idx",
  1040	        type=int,

 succeeded in 0ms:
   300	
   301	  5. **wording 整合**: `design-final.md` §Hybrid baseline の "Kant biographical MCQ" を
   302	     "**persona-specific biographical / thought-history MCQ**" に Edit 済 (本 ADR と同 PR)。
   303	     `blockers.md` LOW-1 は closed (Option A 採用) に Edit 済
   304	
   305	- **根拠**:
   306	  - Claude trade-off 4 軸 (構成斉一性 / CI 交絡 / persona-factuality dimension /
   307	    drafting 工数) で Option A が支配的
   308	  - Codex `gpt-5.5` (`codex-review-low1.md`、109,448 tokens、2026-05-01) verdict
   309	    "Adopt Option A" + MEDIUM 5 件 + LOW 2 件補強で構造的バイアス除去 (同一モデル
   310	    1 発案では構造的バイアス残存リスク、CLAUDE.md "Codex 連携" 規定に従う)
   311	  - psychometric / NLP-eval literature: per-item Δ は item-level 差分の signal に
   312	    sensitive、cross-persona absolute は equating されないため不採用 (Codex MEDIUM-3)
   313	  - RoleEval 原典 (Shen et al. 2024 arXiv:2312.16132): "MCQ 形式は recall のみ測定、
   314	    生成評価ではない" 性質を **floor diagnostic として明示的に**位置付け、生成評価
   315	    (Wachsmuth / ToM / dilemma) と分離
   316	
   317	- **棄却**:
   318	  - Option B (Kant のみ MCQ): per-persona stimulus mass 違いで Vendi/Burrows の
   319	    persona 横比較が交絡 (Claude / Codex 両支持で棄却)
   320	  - Option C (RoleEval 全廃): persona-factuality 軸が消え、style / argumentation /
   321	    ToM の 3 軸偏重に (Claude / Codex 両支持で棄却)
   322	  - Option D (共通 philosophical attribution MCQ): item equating はしやすいが、
   323	    測るものが persona self-knowledge から一般哲学 trivia に寄る、RoleEval の "role
   324	    knowledge" 目的とずれる (Codex LOW-1 で棄却)
   325	  - cross-persona absolute accuracy ranking: psychometric equating 未実施のため不適切
   326	    (Codex MEDIUM-3)
   327	  - `legend` source_grade を scored accuracy に含める: legend は historical record の
   328	    後世形成なので "factuality" を測れない (Codex MEDIUM-2)
   329	
   330	- **影響**:
   331	  - `golden/stimulus/_schema.yaml` に MCQ 専用 11 field 追加 (本 ADR §1)
   332	  - `golden/stimulus/{kant,nietzsche,rikyu}.yaml` 各 10 問起草 (chronology 2 / works
   333	    2 / practice 2 / relationships 2 / material_term 2 で均等化)
   334	  - P2c で `evidence/golden_baseline.py::GoldenBaselineDriver` に MCQ scoring
   335	    branch 追加 (per-item Δ / cycle 1 only / option seeded shuffle)
   336	  - P4a で `evidence/tier_b/big5_icc.py` の base control を per-item 拡張 (ME-1 と
   337	    本 ADR の共通基盤化)
   338	  - `tests/fixtures/synthetic_4th_mcq.yaml` (任意、P2c で driver schema test 用)
   339	  - `decisions.md` ME-summary を 6 件 → 7 件に update
   340	
   341	- **re-open 条件**:
   342	  - cycle 1 first exposure scoring が item recall として機能しないと判明 (例: 全
   343	    persona / 全 item で base control が ceiling に張り付く) → cycle 1 でも sample
   344	    size 不足の場合、stem variant + option shuffle で cycle 2/3 を再活用検討
   345	  - per-item Δ の bootstrap CI が広すぎる場合 → 10 問では sample size 不足、20 問
   346	    拡張検討
   347	  - `source_grade: legend` の比率が想定より高くなり scoring eligible <50% に落ちる
   348	    場合 → Rikyū item の attested fact 補強 (m9-eval-corpus 後送)
   349	  - persona prompt の `cognitive_habits` から `present_in_persona_prompt: true` 比率
   350	    が偏り、prompt parroting で過度に正答率が上がる場合 → false 比率を 5/10 以上に
   351	    引き上げる item 再設計
   352	
   353	---
   354	
   355	## ME-8 — eval natural condition の zone gate bypass (P3a-decide gating bug fix)
   356	
   357	- **決定**: `InMemoryDialogScheduler.__init__` に **`eval_natural_mode: bool = False`**
   358	  flag を追加。`True` のとき:
   359	  1. `tick()` 内で `_iter_colocated_pairs` の代わりに新規ヘルパ
   360	     `_iter_all_distinct_pairs` を使い、3 persona の **全 distinct pair** を
   361	     zone equality 制約なしで反復
   362	  2. `tick()` 内の `_REFLECTIVE_ZONES` skip を bypass
   363	  3. `schedule_initiate` 内の zone-not-reflective reject を bypass
   364	  4. **cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
   365	     invariant は両 mode で active のまま** — natural cadence は維持、proximity
   366	     制約のみ削除
   367	- **構築時防御**: `golden_baseline_mode=True` と `eval_natural_mode=True` の同時指定は
   368	  `ValueError` で reject (Codex review LOW-1 反映、両 flag は互いに disjoint な
   369	  capture phase をカバー、組合せの semantics は未定義)
   370	- **CLI opt-in**: `cli/eval_run_golden.py:capture_natural` の scheduler 構築に
   371	  `eval_natural_mode=True` を 1 引数追加 (planning purity 違反は最小)
   372	- **根拠**:
   373	  - **観測**: G-GEAR P3a pilot で natural 3 cell が初動 burst 2-3 dialogs (= 12-18
   374	    utterances) で完全停止。stimulus 3 cell は同条件で focal=198 完走 → natural 専用の
   375	    gating 挙動が発火していた
   376	  - **root-cause**: `personas/{nietzsche,rikyu}.yaml` の `preferred_zones` が AGORA を
   377	    含まない (Nietzsche=[peripatos,study,garden], Rikyu=[chashitsu,garden,study])。
   378	    LLM が `destination_zone` を選び、`_resample_destination_to_persona_zone`
   379	    (cognition/cycle.py:828) は `os.environ.get("ERRE_ZONE_BIAS_P", "0.2")` で
   380	    20% でしか preferred bias を発火させない。**80% は LLM choice を honor** →
   381	    数 tick 後に AGORA から散る → `_iter_colocated_pairs` が 0 pair → admit 停止
   382	  - **計算根拠**: per-tick zone change rate ≈ (4/6) × (1 - 0.2) = 53%、
   383	    3-tick 後 1 名以上 scatter 確率 = 1 - 0.47^3 ≈ 89% (観測症状と一致)
   384	  - **代案比較**: `decisions.md` 関連の `design-natural-gating-fix.md` §5 で
   385	    4 案比較。代案 B (preferred_zones=[AGORA] override) は bias_p=0.2 で 53% leak、
   386	    代案 A (world/ 層で MoveMsg drop) は planning purity 違反、代案 C (pair set API)
   387	    は boolean flag より重い。**初回案 (scheduler flag) を採用**
   388	  - **Codex `gpt-5.5 xhigh` independent review** (`codex-review-natural-gating.md`):
   389	    HIGH=0 / MEDIUM=0 / LOW=2 で **Verdict: ship**。LOW-1 (両 flag 組合せ防御) と
   390	    LOW-2 (docstring "ordered" → "unordered") は本 ADR commit 前に反映済
   391	- **棄却**:
   392	  - 代案 A (world/ 層 MoveMsg drop): planning purity 違反、M5/M6/M7ζ dwell+phase
   393	    wheel との相互作用リスク
   394	  - 代案 B (preferred_zones=[AGORA] override CLI 単独): `ERRE_ZONE_BIAS_P=0.2`
   395	    default で 53% leak 残存
   396	  - 代案 B+ (env var 強制 1.0 + preferred override): env mutation hack で
   397	    diagnosability 低
   398	  - 代案 C (explicit pair set API): boolean flag より重い、conceptual gain なし
   399	  - persona zone 制約の default 緩和: M4 frozen Protocol contract 違反
   400	- **影響**:
   401	  - `src/erre_sandbox/integration/dialog.py`: flag 追加 + 構築時 reject + tick()/
   402	    schedule_initiate() の bypass + `_iter_all_distinct_pairs` ヘルパ
   403	  - `src/erre_sandbox/cli/eval_run_golden.py`: capture_natural の scheduler 構築に
   404	    `eval_natural_mode=True` を 1 引数追加 (CLI ロジックは不変)
   405	  - `tests/test_integration/test_dialog_eval_natural_mode.py`: 12 unit test
   406	    (Red→Green 転換 + 5 invariant + 構築時 reject)、既存 1221 PASS は default
   407	    False で完全互換 (本セッション full suite 1248 PASS)
   408	  - 次 G-GEAR セッションで natural 再採取時に修正効果を実機検証
   409	- **再採取での観測ターゲット**:
   410	  - focal=30 / total=90 / dialogs ~15 を **30-60 min wall** で完走
   411	  - 既存 dialog の utterance 内容に大きな変化はない見込み (LLM prompt は同一、
   412	    physical zone のみ自由化)
   413	  - `last_close_tick` のクラスタ的な spread を logs で確認 (cooldown が effective
   414	    に活きていれば 30+ tick 間隔で admit が分散)
   415	- **re-open 条件**:
   416	  - **fix 後も admit が初動 burst で停止する場合** → root cause の他要因を再特定
   417	    (仮説 B/C を再評価)。ERRE_ZONE_BIAS_P 周りの cognition / runtime 側に追加 bug
   418	    がある可能性
   419	  - **逆に admit 過多で natural cadence が壊れる場合** → AUTO_FIRE_PROB_PER_TICK
   420	    の 0.25 を eval 用に低めに調整、または cooldown 延長
   421	  - **golden_baseline_mode と組合せたいケースが将来発生** → 構築時 reject の
   422	    緩和ルールを ADR child で起票 (cooldown/timeout の "両 flag union" semantics
   423	    定義)
   424	
   425	---
   426	
   427	## ME-summary
   428	
   429	- 本 ADR **8 件** で Codex `gpt-5.5 xhigh` 3 回 review (2026-04-30 design.md MEDIUM 6 +
   430	  LOW 1 / 2026-05-01 LOW-1 RoleEval MEDIUM 5 + LOW 2 / 2026-05-01 P3a-decide gating
   431	  fix LOW 2) 全件に対応
   432	- ME-4 は P3a-decide セッションで **partial update**、natural 再採取後に **二度目の
   433	  Edit が必要** (current state = bug fix done + script ready, ratio 確定は次回)
   434	- ME-7 は本タスク P2a で確定、stimulus YAML schema と MCQ scoring protocol を規定
   435	- ME-8 (本セッション新規) は m9-eval-system P3a-decide gating bug fix の確定 ADR、
   436	  Codex Verdict: ship
   437	- LOW-1 (RoleEval wording) は ME-7 で close、本 ADR set 範囲内に取り込み済
   438	- 既存 M9-B DB1-DB10 ADR との衝突: 無し
   439	- M2_THRESHOLDS / SCHEMA_VERSION / DialogTurnMsg / RunLifecycleState への破壊変更: 無し

 succeeded in 0ms:
     1	"""In-memory implementation of the M4 :class:`DialogScheduler` Protocol.
     2	
     3	Responsibility: admission-control and lifecycle tracking for agent-to-agent
     4	dialogs. The scheduler *also* owns the envelope emission path — when it
     5	admits an initiate or closes a dialog, it calls the injected ``sink``
     6	callable with the corresponding :class:`ControlEnvelope`, so callers do not
     7	need to route the return value back into the gateway's queue themselves.
     8	
     9	Design rationale (see
    10	``.steering/20260420-m4-multi-agent-orchestrator/design.md`` §v2):
    11	
    12	* The Protocol is frozen at M4 foundation and says ``schedule_initiate``
    13	  returns ``DialogInitiateMsg | None``; we keep that return contract but
    14	  the authoritative delivery path is the sink. Callers that build on the
    15	  Protocol API only get a signal of "was this admitted"; they MUST NOT
    16	  put the returned envelope onto a queue themselves — doing so would
    17	  duplicate the envelope delivered via the sink.
    18	* ``tick()`` is an extension method (not part of the Protocol) that drives
    19	  proximity-based auto-firing: two agents sharing a reflective zone after
    20	  the pair's cooldown has elapsed get a probabilistic initiate.
    21	* All randomness flows through an injected :class:`~random.Random` so the
    22	  auto-fire path is deterministic under test.
    23	"""
    24	
    25	from __future__ import annotations
    26	
    27	import logging
    28	import uuid
    29	from dataclasses import dataclass, field
    30	from random import Random
    31	from typing import TYPE_CHECKING, ClassVar, Final
    32	
    33	from erre_sandbox.schemas import (
    34	    AgentView,
    35	    DialogCloseMsg,
    36	    DialogInitiateMsg,
    37	    DialogTurnMsg,
    38	    Zone,
    39	)
    40	
    41	if TYPE_CHECKING:
    42	    from collections.abc import Callable, Iterable, Iterator, Sequence
    43	    from typing import Literal
    44	
    45	    from erre_sandbox.schemas import ControlEnvelope
    46	
    47	logger = logging.getLogger(__name__)
    48	
    49	
    50	@dataclass
    51	class _OpenDialog:
    52	    """In-flight dialog state carried by the scheduler's ``_open`` map."""
    53	
    54	    dialog_id: str
    55	    initiator: str
    56	    target: str
    57	    zone: Zone
    58	    opened_tick: int
    59	    last_activity_tick: int
    60	    turns: list[DialogTurnMsg] = field(default_factory=list)
    61	
    62	
    63	_REFLECTIVE_ZONES: Final[frozenset[Zone]] = frozenset(
    64	    {Zone.PERIPATOS, Zone.CHASHITSU, Zone.AGORA, Zone.GARDEN},
    65	)
    66	"""Zones where proximity-based dialog admission is allowed.
    67	
    68	``Zone.STUDY`` is intentionally excluded — the M2 persona-erre model treats
    69	the study as a private deep-work space where interrupting speech is
    70	culturally inappropriate.
    71	"""
    72	
    73	
    74	def _pair_key(a: str, b: str) -> frozenset[str]:
    75	    """Order-agnostic dialog pair identity used as a dict key."""
    76	    return frozenset({a, b})
    77	
    78	
    79	class InMemoryDialogScheduler:
    80	    """Default :class:`DialogScheduler` implementation for MVP multi-agent runs.
    81	
    82	    State lives entirely in memory; there is no persistence because M4
    83	    scoped dialog history to the transient layer (semantic summaries come
    84	    from the Reflector on a different path). If a future milestone wants
    85	    cross-run dialog transcripts, subclass and override ``record_turn`` /
    86	    ``close_dialog`` to also write to sqlite.
    87	    """
    88	
    89	    COOLDOWN_TICKS: ClassVar[int] = 30
    90	    """Ticks that must elapse after a close before the same pair may reopen."""
    91	
    92	    TIMEOUT_TICKS: ClassVar[int] = 6
    93	    """Inactivity window after which an open dialog is auto-closed."""
    94	
    95	    AUTO_FIRE_PROB_PER_TICK: ClassVar[float] = 0.25
    96	    """Probability that a qualifying co-located pair is admitted on a tick.
    97	
    98	    Keeps dialog from firing every single cognition tick when two agents
    99	    happen to share a zone; the RNG is injected so tests can force the
   100	    probability to 1.0 or 0.0 deterministically.
   101	    """
   102	
   103	    def __init__(
   104	        self,
   105	        *,
   106	        envelope_sink: Callable[[ControlEnvelope], None],
   107	        rng: Random | None = None,
   108	        turn_sink: Callable[[DialogTurnMsg], None] | None = None,
   109	        golden_baseline_mode: bool = False,
   110	        eval_natural_mode: bool = False,
   111	    ) -> None:
   112	        self._sink = envelope_sink
   113	        self._rng = rng if rng is not None else Random()  # noqa: S311 — non-crypto
   114	        # M8 L6-D1: optional per-turn sink. When bootstrap wires it to a
   115	        # ``MemoryStore.add_dialog_turn_sync`` closure (with agent_id →
   116	        # persona_id resolution baked in), every recorded turn lands in
   117	        # sqlite for later LoRA-training export. Left None for unit tests
   118	        # and the existing lightweight fixtures that have no store.
   119	        self._turn_sink = turn_sink
   120	        # m9-eval-system P2b (design-final.md §Orchestrator): when True the
   121	        # external golden baseline driver bypasses cooldown / timeout / zone
   122	        # restriction so that 70-stimulus battery × 3 cycles can drive the
   123	        # same agent pair without the natural-dialog admission rules. Public
   124	        # attribute so the driver can flip it between stimulus phase
   125	        # (200 turn, mode=True) and natural-dialog phase (300 turn,
   126	        # mode=False) within the same scheduler instance / MemoryStore.
   127	        self.golden_baseline_mode: bool = golden_baseline_mode
   128	        # m9-eval-system P3a-decide (design-natural-gating-fix.md): when True
   129	        # the eval natural-condition pilot bypasses zone-equality and
   130	        # reflective-zone gates inside ``tick()`` and ``schedule_initiate()``
   131	        # so 3 personas can sustain dialog after LLM-driven destination_zone
   132	        # scatters them across study/peripatos/chashitsu. Cooldown / probability
   133	        # / timeout / self-dialog reject / double-open reject all remain active
   134	        # so admission cadence is still natural — only the spatial constraint
   135	        # is dropped. Orthogonal to ``golden_baseline_mode``: stimulus phase
   136	        # uses ``golden_baseline_mode=True`` (driver controls everything),
   137	        # natural phase uses ``eval_natural_mode=True`` (proximity-free
   138	        # logical co-location). Default False keeps M4-frozen Protocol
   139	        # behaviour for live multi-agent runs.
   140	        self.eval_natural_mode: bool = eval_natural_mode
   141	        if eval_natural_mode and golden_baseline_mode:
   142	            # Codex review LOW-1 (2026-05-01): the invariant claims for
   143	            # ``eval_natural_mode`` (cooldown / timeout active) only hold
   144	            # when ``golden_baseline_mode`` is False — combining the two is
   145	            # a programming error because golden_baseline overrides cooldown
   146	            # and timeout independently. Reject construction up-front rather
   147	            # than letting the two flags interleave silently.
   148	            msg = (
   149	                "InMemoryDialogScheduler does not support enabling both "
   150	                "golden_baseline_mode and eval_natural_mode on the same "
   151	                "instance — they cover disjoint capture phases (stimulus "
   152	                "vs natural). Construct two schedulers if both phases are "
   153	                "needed in the same run."
   154	            )
   155	            raise ValueError(msg)
   156	        self._open: dict[str, _OpenDialog] = {}
   157	        self._pair_to_id: dict[frozenset[str], str] = {}
   158	        # Bounded by C(N, 2) for N agents — M4 targets N≤3 so this cannot
   159	        # grow beyond a few entries. If a future milestone scales to N>100
   160	        # agents, cap this to an LRU dict or prune by stale age from
   161	        # ``tick()``; for now the memory footprint is irrelevant.
   162	        self._last_close_tick: dict[frozenset[str], int] = {}
   163	
   164	    # ------------------------------------------------------------------
   165	    # Protocol methods (frozen in schemas.py §7.5)
   166	    # ------------------------------------------------------------------
   167	
   168	    def schedule_initiate(
   169	        self,
   170	        initiator_id: str,
   171	        target_id: str,
   172	        zone: Zone,
   173	        tick: int,
   174	    ) -> DialogInitiateMsg | None:
   175	        """Admit or reject a new dialog.
   176	
   177	        Returns the :class:`DialogInitiateMsg` on admission for callers that
   178	        rely on the Protocol signature, BUT the envelope is already on the
   179	        way to consumers via the injected sink at the moment this method
   180	        returns. Callers must not forward the return value onto the same
   181	        envelope queue — see module docstring.
   182	        """
   183	        if initiator_id == target_id:
   184	            return None
   185	        if (
   186	            zone not in _REFLECTIVE_ZONES
   187	            and not self.golden_baseline_mode
   188	            and not self.eval_natural_mode
   189	        ):
   190	            # m9-eval-system P2b: golden baseline stimulus battery includes
   191	            # ``Zone.STUDY`` (Kant Wachsmuth/RoleEval, Nietzsche aphoristic
   192	            # bursts) — bypass the natural-dialog cultural restriction.
   193	            # m9-eval-system P3a-decide: eval natural condition lets agents
   194	            # wander out of reflective zones (LLM-driven destination_zone)
   195	            # and we still want them to dialog — bypass zone gate too.
   196	            return None
   197	        key = _pair_key(initiator_id, target_id)
   198	        if key in self._pair_to_id:
   199	            return None
   200	        last_close = self._last_close_tick.get(key)
   201	        if (
   202	            last_close is not None
   203	            and tick - last_close < self.COOLDOWN_TICKS
   204	            and not self.golden_baseline_mode
   205	        ):
   206	            # m9-eval-system P2b: 70 stimulus × 3 cycles drives the same pair
   207	            # repeatedly; cooldown would otherwise serialize them across
   208	            # ≥ 30-tick gaps and inflate baseline tick range artificially.
   209	            return None
   210	
   211	        dialog_id = _allocate_dialog_id()
   212	        self._open[dialog_id] = _OpenDialog(
   213	            dialog_id=dialog_id,
   214	            initiator=initiator_id,
   215	            target=target_id,
   216	            zone=zone,
   217	            opened_tick=tick,
   218	            last_activity_tick=tick,
   219	        )
   220	        self._pair_to_id[key] = dialog_id
   221	        envelope = DialogInitiateMsg(
   222	            tick=tick,
   223	            initiator_agent_id=initiator_id,
   224	            target_agent_id=target_id,
   225	            zone=zone,
   226	        )
   227	        self._emit(envelope)
   228	        return envelope
   229	
   230	    def record_turn(self, turn: DialogTurnMsg) -> None:
   231	        """Attach ``turn`` to its dialog's transcript.
   232	
   233	        Raises ``KeyError`` when the dialog is not open — this surfaces bugs
   234	        (agents speaking into a closed dialog) rather than silently dropping.
   235	
   236	        When a ``turn_sink`` was injected at construction (M8 L6-D1), the
   237	        turn is forwarded to it after the in-memory bookkeeping so the sink
   238	        observes turns in the same order as the transcript. Sink exceptions
   239	        are caught and logged — a transient persistence failure must not
   240	        tear down the live dialog loop.
   241	        """
   242	        dialog = self._open.get(turn.dialog_id)
   243	        if dialog is None:
   244	            raise KeyError(
   245	                f"record_turn called for unknown dialog_id={turn.dialog_id!r}",
   246	            )
   247	        dialog.turns.append(turn)
   248	        dialog.last_activity_tick = turn.tick
   249	        if self._turn_sink is not None:
   250	            try:
   251	                self._turn_sink(turn)
   252	            except Exception:
   253	                logger.exception(
   254	                    "turn_sink raised for dialog_id=%s turn_index=%d; "
   255	                    "dropping row but keeping dialog alive",
   256	                    turn.dialog_id,
   257	                    turn.turn_index,
   258	                )
   259	
   260	    def close_dialog(
   261	        self,
   262	        dialog_id: str,
   263	        reason: Literal["completed", "interrupted", "timeout", "exhausted"],
   264	        *,
   265	        tick: int | None = None,
   266	    ) -> DialogCloseMsg:
   267	        """Close ``dialog_id`` and emit the envelope via the sink.
   268	
   269	        When ``tick`` is provided the close is recorded at that world tick
   270	        (``DialogCloseMsg.tick`` and the cooldown anchor both honour it).
   271	        When omitted, falls back to ``dialog.last_activity_tick`` so callers
   272	        that only see the M4-frozen Protocol surface continue to behave as
   273	        before. The keyword-only ``tick`` is the supported path for any
   274	        caller that knows the current world tick (timeout sweep, exhausted
   275	        budget, manual interrupt) — see codex review F1 (2026-04-28) for
   276	        the stale-tick regression that motivated the parameter.
   277	
   278	        Raises ``KeyError`` when the id is not currently open.
   279	        """
   280	        return self._close_dialog_at(dialog_id, reason, tick)
   281	
   282	    def _close_dialog_at(
   283	        self,
   284	        dialog_id: str,
   285	        reason: Literal["completed", "interrupted", "timeout", "exhausted"],
   286	        tick: int | None,
   287	    ) -> DialogCloseMsg:
   288	        """Apply the close operation, honouring an optional override tick."""
   289	        dialog = self._open.pop(dialog_id, None)
   290	        if dialog is None:
   291	            raise KeyError(f"close_dialog called for unknown dialog_id={dialog_id!r}")
   292	        close_tick = tick if tick is not None else dialog.last_activity_tick
   293	        key = _pair_key(dialog.initiator, dialog.target)
   294	        self._pair_to_id.pop(key, None)
   295	        self._last_close_tick[key] = close_tick
   296	        envelope = DialogCloseMsg(
   297	            tick=close_tick,
   298	            dialog_id=dialog_id,
   299	            reason=reason,
   300	        )
   301	        self._emit(envelope)
   302	        return envelope
   303	
   304	    # ------------------------------------------------------------------
   305	    # Protocol-external extensions
   306	    # ------------------------------------------------------------------
   307	
   308	    def tick(self, world_tick: int, agents: Sequence[AgentView]) -> None:
   309	        """Drive proximity-based admission + timeout close in one step.
   310	
   311	        Called by ``WorldRuntime._on_cognition_tick`` after per-agent
   312	        cognition has run. Order:
   313	
   314	        1. close any dialogs whose last_activity_tick is older than TIMEOUT
   315	        2. for each co-located pair in reflective zones, probabilistically
   316	           admit (if not already open and past cooldown)
   317	
   318	        m9-eval-system P3a-decide: when ``eval_natural_mode`` is True the
   319	        spatial gates are dropped. ``_iter_all_distinct_pairs`` enumerates
   320	        every distinct agent pair regardless of zone, and the reflective-zone
   321	        skip below is bypassed. Cooldown / probability / timeout invariants
   322	        remain active so admission cadence is still natural — only proximity
   323	        is removed.
   324	        """
   325	        self._close_timed_out(world_tick)
   326	        if self.eval_natural_mode:
   327	            pair_iter = _iter_all_distinct_pairs(agents)
   328	        else:
   329	            pair_iter = _iter_colocated_pairs(agents)
   330	        for a, b in pair_iter:
   331	            if not self.eval_natural_mode and a.zone not in _REFLECTIVE_ZONES:
   332	                continue
   333	            key = _pair_key(a.agent_id, b.agent_id)
   334	            if key in self._pair_to_id:
   335	                continue
   336	            last_close = self._last_close_tick.get(key)
   337	            if last_close is not None and world_tick - last_close < self.COOLDOWN_TICKS:
   338	                continue
   339	            if self._rng.random() > self.AUTO_FIRE_PROB_PER_TICK:
   340	                continue
   341	            self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)
   342	
   343	    def get_dialog_id(self, agent_a: str, agent_b: str) -> str | None:
   344	        """Return the open dialog id for the (a, b) pair if any, else None."""
   345	        return self._pair_to_id.get(_pair_key(agent_a, agent_b))
   346	
   347	    @property
   348	    def open_count(self) -> int:
   349	        return len(self._open)
   350	
   351	    def transcript_of(self, dialog_id: str) -> list[DialogTurnMsg]:
   352	        dialog = self._open.get(dialog_id)
   353	        return list(dialog.turns) if dialog is not None else []
   354	
   355	    def iter_open_dialogs(self) -> Iterator[tuple[str, str, str, Zone]]:
   356	        """Yield ``(dialog_id, initiator_id, target_id, zone)`` for each open dialog.
   357	
   358	        Added for ``m5-orchestrator-integration``: the per-tick turn driver in
   359	        :class:`~erre_sandbox.world.tick.WorldRuntime` needs to enumerate every
   360	        open dialog to decide budget / speaker / turn generation. Read-only
   361	        — callers must not mutate the scheduler's state via the yielded ids
   362	        except through the existing ``record_turn`` / ``close_dialog`` surface.
   363	        """
   364	        for did, dialog in self._open.items():
   365	            yield did, dialog.initiator, dialog.target, dialog.zone
   366	
   367	    # ------------------------------------------------------------------
   368	    # Internals
   369	    # ------------------------------------------------------------------
   370	
   371	    def _close_timed_out(self, world_tick: int) -> None:
   372	        if self.golden_baseline_mode:
   373	            # m9-eval-system P2b: stimulus phase uses long expected_turn_count
   374	            # (1-3) per stimulus; the driver explicitly closes each dialog so
   375	            # the natural inactivity timeout is suppressed to avoid races
   376	            # between driver close and tick() auto-close.
   377	            return
   378	        expired: list[str] = [
   379	            did
   380	            for did, d in self._open.items()
   381	            if world_tick - d.last_activity_tick >= self.TIMEOUT_TICKS
   382	        ]
   383	        for did in expired:
   384	            self.close_dialog(did, reason="timeout", tick=world_tick)
   385	
   386	    def _emit(self, envelope: ControlEnvelope) -> None:
   387	        try:
   388	            self._sink(envelope)
   389	        except Exception:
   390	            # We refuse to let a sink failure desync scheduler state — log and

 succeeded in 0ms:
     1	"""Tests for ``InMemoryDialogScheduler.eval_natural_mode`` flag.
     2	
     3	m9-eval-system P3a-decide Task 1 — natural runtime gating bug fix.
     4	
     5	Background (from `.steering/20260430-m9-eval-system/design-natural-gating-fix.md`):
     6	G-GEAR pilot 採取で natural condition (3 persona × 30 focal target) が
     7	**初動 burst 2-3 dialogs 後に admission が完全停止**する症状が観測された。
     8	root cause は LLM-driven ``destination_zone`` で agents が AGORA から散り、
     9	``_iter_colocated_pairs`` の ``a.zone == b.zone`` 制約で 0 pair 返却 →
    10	新規 dialog が立ち上がらない、というもの。``ERRE_ZONE_BIAS_P=0.2`` default
    11	で 80% は LLM zone を honor するため preferred_zones override では救えない。
    12	
    13	修正: ``eval_natural_mode: bool = False`` flag を scheduler に追加し、True
    14	のとき ``tick()`` の zone equality / reflective zone 制約を bypass。
    15	cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
    16	invariant は両 mode で保持される (natural cadence は維持)。
    17	
    18	Default ``False`` で既存 1221 PASS は完全互換、``True`` opt-in は CLI
    19	``capture_natural`` のみが指定する。
    20	"""
    21	
    22	from __future__ import annotations
    23	
    24	from random import Random
    25	from typing import TYPE_CHECKING
    26	
    27	import pytest
    28	
    29	from erre_sandbox.integration.dialog import (
    30	    AgentView,
    31	    InMemoryDialogScheduler,
    32	)
    33	from erre_sandbox.schemas import (
    34	    DialogCloseMsg,
    35	    DialogInitiateMsg,
    36	    DialogTurnMsg,
    37	    Zone,
    38	)
    39	
    40	if TYPE_CHECKING:
    41	    from collections.abc import Callable
    42	
    43	    from erre_sandbox.schemas import ControlEnvelope
    44	
    45	
    46	# ---------------------------------------------------------------------------
    47	# Helpers
    48	# ---------------------------------------------------------------------------
    49	
    50	
    51	def _collector() -> tuple[list[ControlEnvelope], Callable[[ControlEnvelope], None]]:
    52	    captured: list[ControlEnvelope] = []
    53	
    54	    def sink(env: ControlEnvelope) -> None:
    55	        captured.append(env)
    56	
    57	    return captured, sink
    58	
    59	
    60	def _always_fire() -> Random:
    61	    """RNG whose ``random()`` always returns 0.0 (≤ AUTO_FIRE_PROB)."""
    62	    r = Random(0)
    63	    r.random = lambda: 0.0  # type: ignore[method-assign]
    64	    return r
    65	
    66	
    67	def _never_fire() -> Random:
    68	    """RNG whose ``random()`` always returns 0.99 (> AUTO_FIRE_PROB)."""
    69	    r = Random(0)
    70	    r.random = lambda: 0.99  # type: ignore[method-assign]
    71	    return r
    72	
    73	
    74	# ---------------------------------------------------------------------------
    75	# Default constructor: eval_natural_mode is False (M4-frozen behaviour)
    76	# ---------------------------------------------------------------------------
    77	
    78	
    79	def test_default_constructor_keeps_eval_natural_mode_false() -> None:
    80	    _captured, sink = _collector()
    81	    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    82	    assert scheduler.eval_natural_mode is False
    83	
    84	
    85	def test_eval_natural_mode_is_independent_of_golden_baseline_mode() -> None:
    86	    """Two flags address orthogonal concerns and can be set independently."""
    87	    _captured, sink = _collector()
    88	    scheduler_a = InMemoryDialogScheduler(
    89	        envelope_sink=sink, eval_natural_mode=True, golden_baseline_mode=False
    90	    )
    91	    scheduler_b = InMemoryDialogScheduler(
    92	        envelope_sink=sink, eval_natural_mode=False, golden_baseline_mode=True
    93	    )
    94	    assert scheduler_a.eval_natural_mode is True
    95	    assert scheduler_a.golden_baseline_mode is False
    96	    assert scheduler_b.eval_natural_mode is False
    97	    assert scheduler_b.golden_baseline_mode is True
    98	
    99	
   100	def test_combining_both_modes_is_rejected() -> None:
   101	    """Codex review LOW-1: the two flags cover disjoint capture phases.
   102	    Combining them on the same instance would silently let
   103	    ``golden_baseline_mode`` override the cooldown / timeout invariant
   104	    that ``eval_natural_mode`` advertises — surface the inconsistency at
   105	    construction instead.
   106	    """
   107	    _captured, sink = _collector()
   108	    with pytest.raises(ValueError, match="golden_baseline_mode and eval_natural_mode"):
   109	        InMemoryDialogScheduler(
   110	            envelope_sink=sink,
   111	            golden_baseline_mode=True,
   112	            eval_natural_mode=True,
   113	        )
   114	
   115	
   116	# ---------------------------------------------------------------------------
   117	# Bug repro (default False): zone drift halts admission
   118	# ---------------------------------------------------------------------------
   119	
   120	
   121	def test_default_mode_admission_stops_when_agents_scatter() -> None:
   122	    """Document the gating bug: when agents drift to different zones the
   123	    proximity-only ``tick()`` cannot admit new dialogs.
   124	
   125	    This mirrors the G-GEAR pilot natural-condition pattern: initial burst
   126	    fires while all 3 personas are still in AGORA, then LLM-driven
   127	    ``destination_zone`` scatters them and ``_iter_colocated_pairs``
   128	    returns nothing → new admissions plateau at 0.
   129	    """
   130	    _captured, sink = _collector()
   131	    scheduler = InMemoryDialogScheduler(
   132	        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=False
   133	    )
   134	
   135	    # Tick 0 — all three in AGORA. Three pairs eligible, all admit.
   136	    co_located = [
   137	        AgentView(agent_id="kant", zone=Zone.AGORA, tick=0),
   138	        AgentView(agent_id="nietzsche", zone=Zone.AGORA, tick=0),
   139	        AgentView(agent_id="rikyu", zone=Zone.AGORA, tick=0),
   140	    ]
   141	    scheduler.tick(world_tick=0, agents=co_located)
   142	    assert scheduler.open_count == 3, (
   143	        "all three pairs should admit on tick 0 with rng=always_fire"
   144	    )
   145	
   146	    # Close all three (simulate budget exhaustion, much sooner than timeout).
   147	    for did, _i, _t, _z in list(scheduler.iter_open_dialogs()):
   148	        scheduler.close_dialog(did, reason="exhausted", tick=0)
   149	    assert scheduler.open_count == 0
   150	
   151	    # Advance world tick past COOLDOWN_TICKS so cooldown is no longer the gate.
   152	    far_tick = scheduler.COOLDOWN_TICKS + 5
   153	
   154	    # Now agents have scattered (LLM destination_zone moved them).
   155	    scattered = [
   156	        AgentView(agent_id="kant", zone=Zone.STUDY, tick=far_tick),
   157	        AgentView(agent_id="nietzsche", zone=Zone.PERIPATOS, tick=far_tick),
   158	        AgentView(agent_id="rikyu", zone=Zone.CHASHITSU, tick=far_tick),
   159	    ]
   160	    scheduler.tick(world_tick=far_tick, agents=scattered)
   161	    assert scheduler.open_count == 0, (
   162	        "BUG REPRO: with default mode, scattered agents have 0 co-located "
   163	        "pairs, so even after cooldown expires no admit fires"
   164	    )
   165	
   166	
   167	# ---------------------------------------------------------------------------
   168	# Fix: eval_natural_mode=True admits any pair regardless of zone
   169	# ---------------------------------------------------------------------------
   170	
   171	
   172	def test_eval_natural_mode_admits_pairs_across_different_zones() -> None:
   173	    _captured, sink = _collector()
   174	    scheduler = InMemoryDialogScheduler(
   175	        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
   176	    )
   177	    scattered = [
   178	        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
   179	        AgentView(agent_id="nietzsche", zone=Zone.PERIPATOS, tick=0),
   180	        AgentView(agent_id="rikyu", zone=Zone.CHASHITSU, tick=0),
   181	    ]
   182	    scheduler.tick(world_tick=0, agents=scattered)
   183	    assert scheduler.open_count == 3, (
   184	        "all three distinct pairs should admit regardless of zone"
   185	    )
   186	
   187	
   188	def test_eval_natural_mode_admits_two_study_agents() -> None:
   189	    """``Zone.STUDY`` is excluded from ``_REFLECTIVE_ZONES`` in default
   190	    mode but eval natural treats all pairs as eligible — including STUDY-STUDY."""
   191	    captured, sink = _collector()
   192	    scheduler = InMemoryDialogScheduler(
   193	        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
   194	    )
   195	    agents = [
   196	        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
   197	        AgentView(agent_id="nietzsche", zone=Zone.STUDY, tick=0),
   198	    ]
   199	    scheduler.tick(world_tick=0, agents=agents)
   200	    assert scheduler.open_count == 1
   201	    initiates = [env for env in captured if isinstance(env, DialogInitiateMsg)]
   202	    assert len(initiates) == 1
   203	
   204	
   205	# ---------------------------------------------------------------------------
   206	# Invariants preserved in eval_natural_mode
   207	# ---------------------------------------------------------------------------
   208	
   209	
   210	def test_eval_natural_mode_preserves_self_dialog_reject() -> None:
   211	    _captured, sink = _collector()
   212	    scheduler = InMemoryDialogScheduler(envelope_sink=sink, eval_natural_mode=True)
   213	    result = scheduler.schedule_initiate("kant", "kant", Zone.AGORA, tick=0)
   214	    assert result is None
   215	
   216	
   217	def test_eval_natural_mode_preserves_double_open_reject() -> None:
   218	    _captured, sink = _collector()
   219	    scheduler = InMemoryDialogScheduler(envelope_sink=sink, eval_natural_mode=True)
   220	    first = scheduler.schedule_initiate("kant", "rikyu", Zone.AGORA, tick=0)
   221	    assert isinstance(first, DialogInitiateMsg)
   222	    second = scheduler.schedule_initiate("kant", "rikyu", Zone.AGORA, tick=1)
   223	    assert second is None
   224	
   225	
   226	def test_eval_natural_mode_preserves_cooldown_via_tick() -> None:
   227	    """Cooldown still applies after a close — tick() must not re-admit
   228	    the same pair within ``COOLDOWN_TICKS`` even with the zone bypass."""
   229	    _captured, sink = _collector()
   230	    scheduler = InMemoryDialogScheduler(
   231	        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
   232	    )
   233	    agents = [
   234	        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
   235	        AgentView(agent_id="rikyu", zone=Zone.GARDEN, tick=0),
   236	    ]
   237	    scheduler.tick(world_tick=0, agents=agents)
   238	    assert scheduler.open_count == 1
   239	    [(did, _i, _t, _z)] = list(scheduler.iter_open_dialogs())
   240	    scheduler.close_dialog(did, reason="exhausted", tick=0)
   241	
   242	    # Within cooldown window — no re-admit.
   243	    for w in range(1, scheduler.COOLDOWN_TICKS):
   244	        scheduler.tick(world_tick=w, agents=agents)
   245	        assert scheduler.open_count == 0, (
   246	            f"cooldown breached at tick {w}: same pair re-admitted within "
   247	            f"{scheduler.COOLDOWN_TICKS} ticks"
   248	        )
   249	
   250	    # Past cooldown — admit again.
   251	    scheduler.tick(world_tick=scheduler.COOLDOWN_TICKS, agents=agents)
   252	    assert scheduler.open_count == 1
   253	
   254	
   255	def test_eval_natural_mode_preserves_probability_gate() -> None:
   256	    """RNG > AUTO_FIRE_PROB still suppresses admit even with zone bypass."""
   257	    _captured, sink = _collector()
   258	    scheduler = InMemoryDialogScheduler(
   259	        envelope_sink=sink, rng=_never_fire(), eval_natural_mode=True
   260	    )
   261	    agents = [
   262	        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
   263	        AgentView(agent_id="rikyu", zone=Zone.GARDEN, tick=0),
   264	    ]
   265	    scheduler.tick(world_tick=0, agents=agents)
   266	    assert scheduler.open_count == 0
   267	
   268	
   269	def test_eval_natural_mode_preserves_timeout_close() -> None:
   270	    """In-flight dialogs still time out when ``last_activity_tick`` is stale."""
   271	    captured, sink = _collector()
   272	    scheduler = InMemoryDialogScheduler(
   273	        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
   274	    )
   275	    agents = [
   276	        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
   277	        AgentView(agent_id="rikyu", zone=Zone.GARDEN, tick=0),
   278	    ]
   279	    scheduler.tick(world_tick=0, agents=agents)
   280	    assert scheduler.open_count == 1
   281	
   282	    # No activity recorded for TIMEOUT_TICKS ticks → tick() should auto-close.
   283	    scheduler.tick(world_tick=scheduler.TIMEOUT_TICKS, agents=agents)
   284	    close_envs = [e for e in captured if isinstance(e, DialogCloseMsg)]
   285	    assert len(close_envs) == 1
   286	    assert close_envs[0].reason == "timeout"
   287	    assert scheduler.open_count == 0
   288	
   289	
   290	# ---------------------------------------------------------------------------
   291	# Sustained admission scenario (Red→Green core)
   292	# ---------------------------------------------------------------------------
   293	
   294	
   295	def test_eval_natural_mode_sustains_admission_after_initial_burst() -> None:
   296	    """Reproduce the natural-condition observation pattern: initial burst,
   297	    then continued admission across many ticks despite zone drift.
   298	
   299	    Counter-example to the bug repro above: with eval_natural_mode=True,
   300	    even after agents scatter, admit fires resume after cooldown.
   301	    """
   302	    _captured, sink = _collector()
   303	    scheduler = InMemoryDialogScheduler(
   304	        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
   305	    )
   306	
   307	    agents_initial = [
   308	        AgentView(agent_id="kant", zone=Zone.AGORA, tick=0),
   309	        AgentView(agent_id="nietzsche", zone=Zone.AGORA, tick=0),
   310	        AgentView(agent_id="rikyu", zone=Zone.AGORA, tick=0),
   311	    ]
   312	    scheduler.tick(world_tick=0, agents=agents_initial)
   313	    assert scheduler.open_count == 3
   314	
   315	    # Simulate dialog turns + exhaustion close at tick 6 (mock budget=6).
   316	    open_now = list(scheduler.iter_open_dialogs())
   317	    for did, init_id, target_id, _z in open_now:
   318	        # Stamp activity at tick 6 so close anchors cooldown there.
   319	        scheduler.record_turn(
   320	            DialogTurnMsg(
   321	                tick=6,
   322	                dialog_id=did,
   323	                speaker_id=init_id,
   324	                addressee_id=target_id,
   325	                turn_index=0,
   326	                utterance="warmup",
   327	            )
   328	        )
   329	        scheduler.close_dialog(did, reason="exhausted", tick=6)
   330	    assert scheduler.open_count == 0
   331	
   332	    # Now agents scatter. Drive ticks past cooldown and check admit resumes.
   333	    scattered = [
   334	        AgentView(agent_id="kant", zone=Zone.STUDY, tick=40),
   335	        AgentView(agent_id="nietzsche", zone=Zone.PERIPATOS, tick=40),
   336	        AgentView(agent_id="rikyu", zone=Zone.CHASHITSU, tick=40),
   337	    ]
   338	    far_tick = 6 + scheduler.COOLDOWN_TICKS  # 36
   339	    scheduler.tick(world_tick=far_tick, agents=scattered)
   340	    assert scheduler.open_count == 3, (
   341	        "after cooldown expires, all three pairs should re-admit even "
   342	        "though every agent is in a different zone"
   343	    )

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/integration/dialog.py | sed -n '390,470p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/cli/eval_run_golden.py | sed -n '1024,1185p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   390	            # We refuse to let a sink failure desync scheduler state — log and
   391	            # continue. The sink is the gateway's responsibility; if it is
   392	            # broken that is a gateway-layer bug, not ours.
   393	            logger.exception(
   394	                "Dialog scheduler sink raised for envelope kind=%s",
   395	                envelope.kind,
   396	            )
   397	
   398	
   399	# ---------------------------------------------------------------------------
   400	# Module-private helpers
   401	# ---------------------------------------------------------------------------
   402	
   403	
   404	def _allocate_dialog_id() -> str:
   405	    return f"d_{uuid.uuid4().hex[:8]}"
   406	
   407	
   408	def _iter_colocated_pairs(
   409	    agents: Iterable[AgentView],
   410	) -> Iterator[tuple[AgentView, AgentView]]:
   411	    """Yield (a, b) pairs of distinct agents sharing the same zone.
   412	
   413	    Each unordered pair is yielded exactly once with a stable ``a.agent_id``
   414	    < ``b.agent_id`` ordering, so callers can use the first entry as the
   415	    canonical initiator without extra sorting.
   416	    """
   417	    sorted_agents = sorted(agents, key=lambda v: v.agent_id)
   418	    for i, a in enumerate(sorted_agents):
   419	        for b in sorted_agents[i + 1 :]:
   420	            if a.zone == b.zone:
   421	                yield a, b
   422	
   423	
   424	def _iter_all_distinct_pairs(
   425	    agents: Iterable[AgentView],
   426	) -> Iterator[tuple[AgentView, AgentView]]:
   427	    """Yield every distinct unordered pair regardless of zone, exactly once.
   428	
   429	    Each unordered pair surfaces with a stable ``a.agent_id`` < ``b.agent_id``
   430	    ordering (mirroring :func:`_iter_colocated_pairs`), so callers can use
   431	    the first entry as the canonical initiator without extra sorting.
   432	
   433	    m9-eval-system P3a-decide: used by ``tick()`` when
   434	    ``eval_natural_mode=True``. The zone field on the leading element is
   435	    still meaningful (it becomes the dialog's recorded zone via the
   436	    ``schedule_initiate`` envelope), but pair eligibility itself does not
   437	    depend on zone equality.
   438	    """
   439	    sorted_agents = sorted(agents, key=lambda v: v.agent_id)
   440	    for i, a in enumerate(sorted_agents):
   441	        for b in sorted_agents[i + 1 :]:
   442	            yield a, b
   443	
   444	
   445	__all__ = [
   446	    # Re-exported from :mod:`erre_sandbox.schemas` for import ergonomics in
   447	    # callers that already reach into this module for the scheduler.
   448	    "AgentView",
   449	    "InMemoryDialogScheduler",
   450	]

 succeeded in 0ms:
  1024	def _build_arg_parser() -> argparse.ArgumentParser:
  1025	    parser = argparse.ArgumentParser(
  1026	        prog="erre-eval-run-golden",
  1027	        description=(
  1028	            "Capture one (persona, condition, run_idx) cell into a fresh "
  1029	            "DuckDB file under raw_dialog schema for m9-eval P3a."
  1030	        ),
  1031	    )
  1032	    parser.add_argument(
  1033	        "--persona",
  1034	        choices=list(DEFAULT_PERSONAS),
  1035	        required=True,
  1036	        help="Focal persona id (kant / nietzsche / rikyu).",
  1037	    )
  1038	    parser.add_argument(
  1039	        "--run-idx",
  1040	        type=int,
  1041	        required=True,
  1042	        help="Seed manifest run index (0..4 per design).",
  1043	    )
  1044	    parser.add_argument(
  1045	        "--condition",
  1046	        choices=("stimulus", "natural"),
  1047	        required=True,
  1048	        help="Capture condition.",
  1049	    )
  1050	    parser.add_argument(
  1051	        "--turn-count",
  1052	        type=int,
  1053	        default=_DEFAULT_TURN_COUNT,
  1054	        help=(
  1055	            "Focal-speaker turn budget for the cell (default %(default)d). "
  1056	            "Stimulus condition slices the battery to fit; natural condition "
  1057	            "stops the runtime once the budget is reached."
  1058	        ),
  1059	    )
  1060	    parser.add_argument(
  1061	        "--cycle-count",
  1062	        type=int,
  1063	        default=_DEFAULT_CYCLE_COUNT,
  1064	        help="Stimulus cycle count (default %(default)d).",
  1065	    )
  1066	    parser.add_argument(
  1067	        "--output",
  1068	        type=Path,
  1069	        required=True,
  1070	        help="DuckDB output path; capture writes to <output>.tmp first.",
  1071	    )
  1072	    parser.add_argument(
  1073	        "--overwrite",
  1074	        action="store_true",
  1075	        help="Replace an existing --output file (default: refuse).",
  1076	    )
  1077	    parser.add_argument(
  1078	        "--ollama-host",
  1079	        default="http://127.0.0.1:11434",
  1080	        help="Ollama HTTP endpoint (default %(default)s).",
  1081	    )
  1082	    parser.add_argument(
  1083	        "--model",
  1084	        default="qwen3:8b",
  1085	        help="Chat model tag (default %(default)s).",
  1086	    )
  1087	    parser.add_argument(
  1088	        "--embed-model",
  1089	        default="nomic-embed-text",
  1090	        help="Embedding model tag (natural condition only).",
  1091	    )
  1092	    parser.add_argument(
  1093	        "--memory-db",
  1094	        type=Path,
  1095	        default=None,
  1096	        help=(
  1097	            "sqlite path for the natural-condition cognition stack "
  1098	            "(default: /tmp/p3a_natural_<persona>_run<idx>.sqlite)."
  1099	        ),
  1100	    )
  1101	    parser.add_argument(
  1102	        "--wall-timeout-min",
  1103	        type=float,
  1104	        default=_DEFAULT_WALL_TIMEOUT_MIN,
  1105	        help=(
  1106	            "Hard wall-clock cap for natural condition in minutes "
  1107	            "(default %(default).0f)."
  1108	        ),
  1109	    )
  1110	    parser.add_argument(
  1111	        "--personas-dir",
  1112	        type=Path,
  1113	        default=_PERSONAS_DIR_DEFAULT,
  1114	        help="personas/ directory (default %(default)s).",
  1115	    )
  1116	    parser.add_argument(
  1117	        "--log-level",
  1118	        default="info",
  1119	        choices=("debug", "info", "warning", "error"),
  1120	        help="Root logger level.",
  1121	    )
  1122	    return parser
  1123	
  1124	
  1125	async def _async_main(args: argparse.Namespace) -> int:
  1126	    temp_path, final_path = _resolve_output_paths(args.output, overwrite=args.overwrite)
  1127	    logger.info(
  1128	        "capture begin persona=%s condition=%s run_idx=%d turn_count=%d "
  1129	        "temp=%s final=%s",
  1130	        args.persona,
  1131	        args.condition,
  1132	        args.run_idx,
  1133	        args.turn_count,
  1134	        temp_path,
  1135	        final_path,
  1136	    )
  1137	
  1138	    if args.condition == "stimulus":
  1139	        async with OllamaChatClient(
  1140	            model=args.model, endpoint=args.ollama_host
  1141	        ) as client:
  1142	            result = await capture_stimulus(
  1143	                persona=args.persona,
  1144	                run_idx=args.run_idx,
  1145	                turn_count=args.turn_count,
  1146	                cycle_count=args.cycle_count,
  1147	                temp_path=temp_path,
  1148	                inference_fn=None,
  1149	                client=client,
  1150	                personas_dir=args.personas_dir,
  1151	            )
  1152	    else:
  1153	        result = await capture_natural(
  1154	            persona=args.persona,
  1155	            run_idx=args.run_idx,
  1156	            turn_count=args.turn_count,
  1157	            temp_path=temp_path,
  1158	            ollama_host=args.ollama_host,
  1159	            chat_model=args.model,
  1160	            embed_model=args.embed_model,
  1161	            memory_db_path=args.memory_db,
  1162	            wall_timeout_min=args.wall_timeout_min,
  1163	            personas_dir=args.personas_dir,
  1164	        )
  1165	
  1166	    if result.fatal_error is not None:
  1167	        logger.error(
  1168	            "capture FAILED persona=%s condition=%s run_idx=%d "
  1169	            "total=%d focal=%d reason=%s",
  1170	            args.persona,
  1171	            args.condition,
  1172	            args.run_idx,
  1173	            result.total_rows,
  1174	            result.focal_rows,
  1175	            result.fatal_error,
  1176	        )
  1177	        # Leave temp_path on disk for inspection; refuse the atomic rename.
  1178	        return 2
  1179	
  1180	    atomic_temp_rename(temp_path, final_path)
  1181	    logger.info(
  1182	        "capture OK persona=%s condition=%s run_idx=%d total=%d focal=%d output=%s",
  1183	        args.persona,
  1184	        args.condition,
  1185	        args.run_idx,

exec
/bin/zsh -lc "rg -n \"wall_timeout_min|capture_natural|add_argument\\(|--wall-timeout-min|turn-count|condition\" tests src/erre_sandbox/cli/eval_run_golden.py tests/test_cli tests/test_integration" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc 'rg -n "wall_timeout_min|_build_arg_parser|parse_args|capture_natural|--wall-timeout-min" tests/test_cli tests/test_integration tests | head -80' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
tests/test_cli/test_eval_run_golden.py:28:    _build_arg_parser,
tests/test_cli/test_eval_run_golden.py:276:    parser = _build_arg_parser()
tests/test_cli/test_eval_run_golden.py:278:    args = parser.parse_args(
tests/test_cli/test_eval_run_golden.py:300:    parser = _build_arg_parser()
tests/test_cli/test_eval_run_golden.py:302:        parser.parse_args(
tests/test_main.py:77:    args = _build_parser().parse_args([])
tests/test_main.py:83:    args = _build_parser().parse_args(["--personas", "kant,nietzsche"])
tests/test_main.py:89:    args = _build_parser().parse_args(["--personas-dir", target])
tests/test_cli/test_eval_run_golden.py:28:    _build_arg_parser,
tests/test_cli/test_eval_run_golden.py:276:    parser = _build_arg_parser()
tests/test_cli/test_eval_run_golden.py:278:    args = parser.parse_args(
tests/test_cli/test_eval_run_golden.py:300:    parser = _build_arg_parser()
tests/test_cli/test_eval_run_golden.py:302:        parser.parse_args(
tests/test_integration/test_dialog_eval_natural_mode.py:19:``capture_natural`` のみが指定する。
tests/test_integration/test_dialog_eval_natural_mode.py:19:``capture_natural`` のみが指定する。

 succeeded in 0ms:
src/erre_sandbox/cli/eval_run_golden.py:4:``(persona, condition, run_idx)`` cell into a fresh DuckDB file under the
src/erre_sandbox/cli/eval_run_golden.py:8:Two conditions, single CLI:
src/erre_sandbox/cli/eval_run_golden.py:10:* ``--condition stimulus`` — drives :class:`GoldenBaselineDriver` with a
src/erre_sandbox/cli/eval_run_golden.py:12:  persona accumulates ``--turn-count`` turns across ``--cycle-count`` cycles.
src/erre_sandbox/cli/eval_run_golden.py:15:* ``--condition natural`` — replicates :func:`erre_sandbox.bootstrap.bootstrap`
src/erre_sandbox/cli/eval_run_golden.py:20:  focal speaker has uttered ``--turn-count`` turns.
src/erre_sandbox/cli/eval_run_golden.py:27:* HIGH-2 — focal speaker turn budget for both conditions (driver alternates
src/erre_sandbox/cli/eval_run_golden.py:34:* HIGH-5 — natural-condition scheduler RNG is seeded with
src/erre_sandbox/cli/eval_run_golden.py:42:condition is encoded in ``run_id`` instead.
src/erre_sandbox/cli/eval_run_golden.py:47:        --persona kant --run-idx 0 --condition stimulus \\
src/erre_sandbox/cli/eval_run_golden.py:48:        --turn-count 200 --cycle-count 3 \\
src/erre_sandbox/cli/eval_run_golden.py:117:"""Focal speaker turn budget per ``(persona, condition)`` cell (P3a target)."""
src/erre_sandbox/cli/eval_run_golden.py:123:"""Hard wall-clock cap for one capture, primarily natural condition."""
src/erre_sandbox/cli/eval_run_golden.py:182:    """Returned from :func:`capture_stimulus` / :func:`capture_natural`.
src/erre_sandbox/cli/eval_run_golden.py:225:    """System prompt for the stimulus condition.
src/erre_sandbox/cli/eval_run_golden.py:650:    """Capture one stimulus-condition cell into ``temp_path``.
src/erre_sandbox/cli/eval_run_golden.py:740:    # Warmup is a pre-condition only when we own the client.
src/erre_sandbox/cli/eval_run_golden.py:804:async def capture_natural(  # noqa: C901, PLR0915 — composition root mirrors bootstrap.py
src/erre_sandbox/cli/eval_run_golden.py:814:    wall_timeout_min: float,
src/erre_sandbox/cli/eval_run_golden.py:819:    """Capture one natural-condition cell using a headless WorldRuntime stack.
src/erre_sandbox/cli/eval_run_golden.py:835:            f"persona={persona!r} is not part of the natural-condition agent "
src/erre_sandbox/cli/eval_run_golden.py:848:        # ME-2 keeps the natural-condition memory DB /tmp-scoped so the eval
src/erre_sandbox/cli/eval_run_golden.py:966:    wall_deadline = time.monotonic() + wall_timeout_min * 60.0
src/erre_sandbox/cli/eval_run_golden.py:983:                state.fatal_error = f"wall timeout ({wall_timeout_min} min) exceeded"
src/erre_sandbox/cli/eval_run_golden.py:1028:            "Capture one (persona, condition, run_idx) cell into a fresh "
src/erre_sandbox/cli/eval_run_golden.py:1032:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1038:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1044:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1045:        "--condition",
src/erre_sandbox/cli/eval_run_golden.py:1048:        help="Capture condition.",
src/erre_sandbox/cli/eval_run_golden.py:1050:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1051:        "--turn-count",
src/erre_sandbox/cli/eval_run_golden.py:1056:            "Stimulus condition slices the battery to fit; natural condition "
src/erre_sandbox/cli/eval_run_golden.py:1060:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1066:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1072:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1077:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1082:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1087:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1090:        help="Embedding model tag (natural condition only).",
src/erre_sandbox/cli/eval_run_golden.py:1092:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1097:            "sqlite path for the natural-condition cognition stack "
src/erre_sandbox/cli/eval_run_golden.py:1101:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1102:        "--wall-timeout-min",
src/erre_sandbox/cli/eval_run_golden.py:1106:            "Hard wall-clock cap for natural condition in minutes "
src/erre_sandbox/cli/eval_run_golden.py:1110:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1116:    parser.add_argument(
src/erre_sandbox/cli/eval_run_golden.py:1128:        "capture begin persona=%s condition=%s run_idx=%d turn_count=%d "
src/erre_sandbox/cli/eval_run_golden.py:1131:        args.condition,
src/erre_sandbox/cli/eval_run_golden.py:1138:    if args.condition == "stimulus":
src/erre_sandbox/cli/eval_run_golden.py:1153:        result = await capture_natural(
src/erre_sandbox/cli/eval_run_golden.py:1162:            wall_timeout_min=args.wall_timeout_min,
src/erre_sandbox/cli/eval_run_golden.py:1168:            "capture FAILED persona=%s condition=%s run_idx=%d "
src/erre_sandbox/cli/eval_run_golden.py:1171:            args.condition,
src/erre_sandbox/cli/eval_run_golden.py:1182:        "capture OK persona=%s condition=%s run_idx=%d total=%d focal=%d output=%s",
src/erre_sandbox/cli/eval_run_golden.py:1184:        args.condition,
src/erre_sandbox/cli/eval_run_golden.py:1216:    "capture_natural",
tests/test_cli/test_eval_run_golden.py:284:            "--condition",
tests/test_cli/test_eval_run_golden.py:292:    assert args.condition == "stimulus"
tests/test_cli/test_eval_run_golden.py:308:                "--condition",
tests/test_cli/test_eval_run_golden.py:284:            "--condition",
tests/test_cli/test_eval_run_golden.py:292:    assert args.condition == "stimulus"
tests/test_cli/test_eval_run_golden.py:308:                "--condition",
tests/test_integration/test_scenario_memory_write.py:91:    asymmetry of nomic-embed-text-v1.5 is a correctness condition, not a
tests/test_integration/test_dialog_eval_natural_mode.py:6:G-GEAR pilot 採取で natural condition (3 persona × 30 focal target) が
tests/test_integration/test_dialog_eval_natural_mode.py:19:``capture_natural`` のみが指定する。
tests/test_integration/test_dialog_eval_natural_mode.py:125:    This mirrors the G-GEAR pilot natural-condition pattern: initial burst
tests/test_integration/test_dialog_eval_natural_mode.py:296:    """Reproduce the natural-condition observation pattern: initial burst,
tests/test_integration/test_scenario_memory_write.py:91:    asymmetry of nomic-embed-text-v1.5 is a correctness condition, not a
tests/test_cognition/test_trigger_pick.py:256:    """A tick with only temporal still produces a tag (firing condition relaxed)."""
tests/test_integration/test_dialog_eval_natural_mode.py:6:G-GEAR pilot 採取で natural condition (3 persona × 30 focal target) が
tests/test_integration/test_dialog_eval_natural_mode.py:19:``capture_natural`` のみが指定する。
tests/test_integration/test_dialog_eval_natural_mode.py:125:    This mirrors the G-GEAR pilot natural-condition pattern: initial burst
tests/test_integration/test_dialog_eval_natural_mode.py:296:    """Reproduce the natural-condition observation pattern: initial burst,
tests/test_evidence/test_scaling_metrics.py:81:    """3 turns + history_k=3 means no conditional pair can be formed."""
tests/test_evidence/test_scaling_metrics.py:121:    # one conditional sample exists.
tests/test_memory/test_store.py:276:# Dialog turn log (M8 L6-D1 precondition)
tests/test_cognition/test_reflection.py:5:* :class:`ReflectionPolicy` evaluation of the three trigger conditions
tests/test_schemas.py:65:def test_agent_state_defaults_match_csdg_human_condition() -> None:
tests/test_evidence/test_tier_a/test_burrows_corpus_qc.py:326:        f" across {len(rhos)} chunk pairs; reopen condition documented"

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/cli/eval_run_golden.py | sed -n '1,150p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     1	r"""``eval_run_golden`` — drive the m9-eval golden battery against live qwen3:8b.
     2	
     3	This CLI is the m9-eval-system **P3a Step 1** entry point: it captures one
     4	``(persona, condition, run_idx)`` cell into a fresh DuckDB file under the
     5	``raw_dialog`` schema enforced by
     6	:mod:`erre_sandbox.contracts.eval_paths` / :mod:`erre_sandbox.evidence.eval_store`.
     7	
     8	Two conditions, single CLI:
     9	
    10	* ``--condition stimulus`` — drives :class:`GoldenBaselineDriver` with a
    11	  **stratified slice** of ``golden/stimulus/<persona>.yaml`` so the focal
    12	  persona accumulates ``--turn-count`` turns across ``--cycle-count`` cycles.
    13	  No WorldRuntime is needed; each stimulus opens / drives / closes a single
    14	  dialog through the public scheduler API.
    15	* ``--condition natural`` — replicates :func:`erre_sandbox.bootstrap.bootstrap`
    16	  headlessly (no uvicorn): MemoryStore (sqlite) + EmbeddingClient +
    17	  CognitionCycle + WorldRuntime + InMemoryDialogScheduler +
    18	  OllamaDialogTurnGenerator. Three personas (kant + nietzsche + rikyu) are
    19	  registered in :attr:`Zone.AGORA`; the watchdog stops the runtime once the
    20	  focal speaker has uttered ``--turn-count`` turns.
    21	
    22	Codex `gpt-5.5 xhigh` review (`.steering/20260430-m9-eval-system/codex-review-step1.md`)
    23	is reflected end-to-end:
    24	
    25	* HIGH-1 — :func:`_stratified_stimulus_slice` keeps proportional category
    26	  representation instead of YAML-prefix slicing.
    27	* HIGH-2 — focal speaker turn budget for both conditions (driver alternates
    28	  speakers on multi-turn stimuli).
    29	* HIGH-3 — DuckDB sink is **fail-fast**; an INSERT error sets the run
    30	  ``fatal_error`` flag and aborts before any atomic rename.
    31	* HIGH-4 — capture writes to ``<output>.tmp``; pre-existing ``<output>``
    32	  refuses unless ``--overwrite`` is passed; final ``atomic_temp_rename``
    33	  is the only path that publishes the result file.
    34	* HIGH-5 — natural-condition scheduler RNG is seeded with
    35	  :func:`derive_seed` so admission auto-fire is reproducible per ``run_idx``.
    36	* HIGH-6 — ``runtime.stop()`` is followed by
    37	  ``asyncio.wait_for(runtime_task, grace_s)``; on timeout the run is
    38	  abandoned (no rename) so partial captures cannot masquerade as complete.
    39	
    40	The ``mode`` raw column is **left empty** (Codex MEDIUM-2): the column is
    41	reserved for ERRE mode in the live-run contract, while the stimulus / natural
    42	condition is encoded in ``run_id`` instead.
    43	
    44	Usage::
    45	
    46	    python -m erre_sandbox.cli.eval_run_golden \\
    47	        --persona kant --run-idx 0 --condition stimulus \\
    48	        --turn-count 200 --cycle-count 3 \\
    49	        --output data/eval/pilot/kant_stimulus_run0.duckdb
    50	"""
    51	
    52	from __future__ import annotations
    53	
    54	import argparse
    55	import asyncio
    56	import contextlib
    57	import logging
    58	import random
    59	import sys
    60	import time
    61	from collections import defaultdict
    62	from dataclasses import dataclass, field
    63	from datetime import UTC, datetime
    64	from pathlib import Path
    65	from typing import TYPE_CHECKING, Any, Final
    66	
    67	import duckdb
    68	import yaml
    69	
    70	from erre_sandbox.cognition import CognitionCycle, Reflector
    71	from erre_sandbox.erre import ZONE_TO_DEFAULT_ERRE_MODE, DefaultERREModePolicy
    72	from erre_sandbox.evidence.eval_store import (
    73	    atomic_temp_rename,
    74	    bootstrap_schema,
    75	    write_with_checkpoint,
    76	)
    77	from erre_sandbox.evidence.golden_baseline import (
    78	    DEFAULT_INTERLOCUTOR_ID,
    79	    DEFAULT_PERSONAS,
    80	    GoldenBaselineDriver,
    81	    assert_seed_manifest_consistent,
    82	    derive_seed,
    83	    load_seed_manifest,
    84	    load_stimulus_battery,
    85	)
    86	from erre_sandbox.inference import (
    87	    ChatMessage,
    88	    OllamaChatClient,
    89	    OllamaUnavailableError,
    90	    compose_sampling,
    91	)
    92	from erre_sandbox.integration.dialog import InMemoryDialogScheduler
    93	from erre_sandbox.integration.dialog_turn import OllamaDialogTurnGenerator
    94	from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
    95	from erre_sandbox.schemas import (
    96	    AgentState,
    97	    DialogTurnMsg,
    98	    ERREMode,
    99	    ERREModeName,
   100	    PersonaSpec,
   101	    Position,
   102	    SamplingDelta,
   103	    Zone,
   104	)
   105	from erre_sandbox.world import WorldRuntime
   106	
   107	if TYPE_CHECKING:
   108	    from collections.abc import Callable
   109	
   110	logger = logging.getLogger(__name__)
   111	
   112	# ---------------------------------------------------------------------------
   113	# Constants
   114	# ---------------------------------------------------------------------------
   115	
   116	_DEFAULT_TURN_COUNT: Final[int] = 200
   117	"""Focal speaker turn budget per ``(persona, condition)`` cell (P3a target)."""
   118	
   119	_DEFAULT_CYCLE_COUNT: Final[int] = 3
   120	"""Stimulus battery cycle count — matches design-final.md P3 production."""
   121	
   122	_DEFAULT_WALL_TIMEOUT_MIN: Final[float] = 90.0
   123	"""Hard wall-clock cap for one capture, primarily natural condition."""
   124	
   125	_RUNTIME_DRAIN_GRACE_S: Final[float] = 30.0
   126	"""Seconds to await ``runtime_task`` after ``runtime.stop()`` (Codex HIGH-6)."""
   127	
   128	_AGENT_ID_FMT: Final[str] = "a_{persona_id}_001"
   129	"""Mirrors :func:`erre_sandbox.bootstrap._build_initial_state` agent id shape."""
   130	
   131	_NATURAL_AGORA_POSITIONS: Final[dict[str, tuple[float, float, float]]] = {
   132	    # Three distinct seats inside AGORA so the M5/M6 separation nudge does
   133	    # not perturb spawn coordinates the very first physics tick. AGORA uses
   134	    # the default zone radius, well within the 5m proximity threshold so
   135	    # all three pairs auto-fire.
   136	    "kant": (0.0, 0.0, 0.0),
   137	    "nietzsche": (0.8, 0.0, 0.0),
   138	    "rikyu": (-0.8, 0.0, 0.0),
   139	}
   140	
   141	_PERSONAS_DIR_DEFAULT: Final[Path] = Path("personas")
   142	
   143	_INFERENCE_RETRY_MAX_ATTEMPTS: Final[int] = 3
   144	_INFERENCE_RETRY_BASE_S: Final[float] = 0.2
   145	_INFERENCE_RETRY_MULTIPLIER: Final[float] = 4.0
   146	
   147	_STIMULUS_NUM_PREDICT: Final[int] = 240
   148	_STIMULUS_MCQ_NUM_PREDICT: Final[int] = 8
   149	_STIMULUS_STOP: Final[tuple[str, ...]] = ("\n\n",)
   150	_STIMULUS_MCQ_STOP: Final[tuple[str, ...]] = ("\n",)

exec
/bin/zsh -lc "nl -ba tests/test_cli/test_eval_run_golden.py | sed -n '250,330p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   250	        del sink  # discard real sink, use broken one instead
   251	        return broken
   252	
   253	    monkeypatch.setattr(mod, "_make_duckdb_sink", _broken_sink_factory)
   254	
   255	    temp = tmp_path / "broken.duckdb.tmp"
   256	    result = await capture_stimulus(
   257	        persona="kant",
   258	        run_idx=0,
   259	        turn_count=10,
   260	        cycle_count=1,
   261	        temp_path=temp,
   262	        inference_fn=_stub_text_inference,
   263	        client=None,
   264	    )
   265	    assert result.fatal_error == "injected duckdb failure"
   266	    assert result.total_rows == 0
   267	    assert result.focal_rows == 0
   268	
   269	
   270	# ---------------------------------------------------------------------------
   271	# CLI argparse (LOW; sanity for the live invocation surface)
   272	# ---------------------------------------------------------------------------
   273	
   274	
   275	def test_arg_parser_has_required_flags() -> None:
   276	    parser = _build_arg_parser()
   277	    # parse a known-good invocation
   278	    args = parser.parse_args(
   279	        [
   280	            "--persona",
   281	            "kant",
   282	            "--run-idx",
   283	            "0",
   284	            "--condition",
   285	            "stimulus",
   286	            "--output",
   287	            "x.duckdb",
   288	        ]
   289	    )
   290	    assert args.persona == "kant"
   291	    assert args.run_idx == 0
   292	    assert args.condition == "stimulus"
   293	    assert str(args.output).endswith("x.duckdb")
   294	    assert args.turn_count == 200
   295	    assert args.cycle_count == 3
   296	    assert args.overwrite is False
   297	
   298	
   299	def test_arg_parser_rejects_unknown_persona() -> None:
   300	    parser = _build_arg_parser()
   301	    with pytest.raises(SystemExit):
   302	        parser.parse_args(
   303	            [
   304	                "--persona",
   305	                "voltaire",
   306	                "--run-idx",
   307	                "0",
   308	                "--condition",
   309	                "stimulus",
   310	                "--output",
   311	                "x.duckdb",
   312	            ]
   313	        )

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/world/tick.py | sed -n '360,460p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   360	        # M6-A-2b: simulated time-of-day tracking. ``_time_start`` is
   361	        # lazily initialised on the first physics tick so ``_current_period``
   362	        # matches the clock the runtime was actually started with (not the
   363	        # clock the constructor saw, which is usually still at t=0).
   364	        self._time_start: float | None = None
   365	        self._current_period: TimeOfDay = TimeOfDay.DAWN
   366	        # M6-A-2b: ProximityEvent needs a prev-tick distance per agent pair
   367	        # to detect threshold crossings. Key is ``frozenset({id_a, id_b})``
   368	        # so each unordered pair gets exactly one entry regardless of which
   369	        # side registered first. Stale entries (one side de-registered)
   370	        # remain until the pair is observed again and overwrites itself;
   371	        # WorldRuntime does not currently expose agent removal, so
   372	        # purge-on-deregister is left to the caller that adds that hook.
   373	        self._pair_distances: dict[frozenset[str], float] = {}
   374	        # M7 B1: per-(agent_id, prop_id) last-seen XZ distance so
   375	        # AffordanceEvent emits once per *entry* into a prop's salient radius,
   376	        # not every tick the agent remains inside it. Populated lazily by
   377	        # ``_fire_affordance_events``; entries are never purged (the table is
   378	        # O(agents × props) and both bounds are small at MVP scale).
   379	        self._agent_prop_distances: dict[tuple[str, str], float] = {}
   380	        self._agents: dict[str, AgentRuntime] = {}
   381	        self._events: list[ScheduledEvent] = []
   382	        # TODO(T14): the unbounded queue is a deliberate MVP trade-off
   383	        # (see decisions.md D7). When T14 wires a real WebSocket consumer,
   384	        # switch to ``maxsize=10_000`` and add an oldest-drop / back-pressure
   385	        # policy so a stalled client cannot grow memory without bound.
   386	        self._envelopes: asyncio.Queue[ControlEnvelope] = asyncio.Queue()
   387	        self._dialog_scheduler: DialogScheduler | None = None
   388	        # M5 orchestrator-integration: optional LLM-backed generator consulted
   389	        # at the end of each cognition tick via ``_drive_dialog_turns``. When
   390	        # ``None`` (e.g. unit tests that construct a bare runtime), open
   391	        # dialogs are still admitted / timed out by the scheduler but no
   392	        # utterances are generated — they close via the existing timeout path.
   393	        self._dialog_generator: DialogTurnGenerator | None = None
   394	        self._running: bool = False
   395	        self._seq: int = 0
   396	        # M8 L6-D3: run-level epoch state for the two-phase methodology.
   397	        # Defaults to AUTONOMOUS so existing callers (run()) get today's
   398	        # behaviour unchanged. Mutated only via transition_to_q_and_a() /
   399	        # transition_to_evaluation() — direct assignment is not supported
   400	        # (the field is addressed through a read-only property).
   401	        self._run_lifecycle: RunLifecycleState = RunLifecycleState()
   402	
   403	    # ----- Run lifecycle (M8) -----
   404	
   405	    @property
   406	    def run_lifecycle(self) -> RunLifecycleState:
   407	        """Snapshot of the current run-level epoch state.
   408	
   409	        Returns the live ``RunLifecycleState`` instance. Pydantic models are
   410	        mutable by default, but callers **must not** mutate it — all state
   411	        changes go through :meth:`transition_to_q_and_a` /
   412	        :meth:`transition_to_evaluation` so the FSM invariants hold.
   413	        """
   414	        return self._run_lifecycle
   415	
   416	    def transition_to_q_and_a(self) -> RunLifecycleState:
   417	        """Advance the run from ``autonomous`` to ``q_and_a``.
   418	
   419	        Raises :class:`ValueError` if the current phase is not
   420	        :attr:`EpochPhase.AUTONOMOUS`. Replaces the lifecycle instance so
   421	        observers that snapshotted the old value see a stable record.
   422	        """
   423	        current = self._run_lifecycle.epoch_phase
   424	        if current is not EpochPhase.AUTONOMOUS:
   425	            msg = (
   426	                f"cannot transition to q_and_a from {current.value!r}; "
   427	                "only autonomous → q_and_a is allowed"
   428	            )
   429	            raise ValueError(msg)
   430	        self._run_lifecycle = RunLifecycleState(epoch_phase=EpochPhase.Q_AND_A)
   431	        return self._run_lifecycle
   432	
   433	    def transition_to_evaluation(self) -> RunLifecycleState:
   434	        """Advance the run from ``q_and_a`` to ``evaluation``.
   435	
   436	        Raises :class:`ValueError` if the current phase is not
   437	        :attr:`EpochPhase.Q_AND_A`. Direct ``autonomous → evaluation`` is
   438	        disallowed to protect the autonomous-emergence claim (any Q&A
   439	        interaction with the researcher must be recorded before the run
   440	        enters offline scoring).
   441	        """
   442	        current = self._run_lifecycle.epoch_phase
   443	        if current is not EpochPhase.Q_AND_A:
   444	            msg = (
   445	                f"cannot transition to evaluation from {current.value!r}; "
   446	                "only q_and_a → evaluation is allowed"
   447	            )
   448	            raise ValueError(msg)
   449	        self._run_lifecycle = RunLifecycleState(epoch_phase=EpochPhase.EVALUATION)
   450	        return self._run_lifecycle
   451	
   452	    # ----- Registration -----
   453	
   454	    def register_agent(self, state: AgentState, persona: PersonaSpec) -> None:
   455	        """Add an agent whose cognition cycle this runtime should drive.
   456	
   457	        Must be called before :meth:`run` or from within a handler on the
   458	        same event-loop task; the runtime uses a plain :class:`dict` for
   459	        ``_agents`` and takes no lock, so concurrent mutation from a
   460	        different task would race with the scheduler.

exec
/bin/zsh -lc 'rg -n "dialog_turn_budget|close_dialog|record_turn|_drive_dialog|attach_dialog|scheduler.tick|_run_dialog_tick|cognition_tick|DEFAULT_COGNITION_PERIOD" src/erre_sandbox/world src/erre_sandbox/cognition src/erre_sandbox/schemas.py personas tests' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
src/erre_sandbox/schemas.py:57:(:attr:`Cognitive.dialog_turn_budget`, :attr:`DialogTurnMsg.turn_index`) and
src/erre_sandbox/schemas.py:517:    dialog_turn_budget: int = Field(
src/erre_sandbox/schemas.py:1157:    :attr:`Cognitive.dialog_turn_budget` for exhaustion close-out. The first
src/erre_sandbox/schemas.py:1173:            "``Cognitive.dialog_turn_budget`` to drive the exhaustion close."
src/erre_sandbox/schemas.py:1286:    :attr:`Cognitive.dialog_turn_budget` cap (distinct from the
src/erre_sandbox/schemas.py:1346:    def record_turn(self, turn: DialogTurnMsg) -> None:
src/erre_sandbox/schemas.py:1350:    def close_dialog(
src/erre_sandbox/schemas.py:1389:        :meth:`record_turn` / :meth:`close_dialog`.
src/erre_sandbox/world/tick.py:292:    """One in-flight turn request staged by :meth:`WorldRuntime._drive_dialog_turns`.
src/erre_sandbox/world/tick.py:320:    DEFAULT_COGNITION_PERIOD_S: ClassVar[float] = 10.0
src/erre_sandbox/world/tick.py:348:            else self.DEFAULT_COGNITION_PERIOD_S
src/erre_sandbox/world/tick.py:389:        # at the end of each cognition tick via ``_drive_dialog_turns``. When
src/erre_sandbox/world/tick.py:568:        # synchronously inside ``InMemoryDialogScheduler.record_turn``.
src/erre_sandbox/world/tick.py:724:    def attach_dialog_scheduler(self, scheduler: DialogScheduler) -> None:
src/erre_sandbox/world/tick.py:733:    def attach_dialog_generator(self, generator: DialogTurnGenerator) -> None:
src/erre_sandbox/world/tick.py:736:        When attached, :meth:`_on_cognition_tick` walks every open dialog
src/erre_sandbox/world/tick.py:739:        speaker's ``dialog_turn_budget`` is saturated, or (b) asks the
src/erre_sandbox/world/tick.py:745:        generator, mirroring :meth:`attach_dialog_scheduler`.
src/erre_sandbox/world/tick.py:771:            self._on_cognition_tick,
src/erre_sandbox/world/tick.py:1038:    async def _on_cognition_tick(self) -> None:
src/erre_sandbox/world/tick.py:1080:        self._run_dialog_tick()
src/erre_sandbox/world/tick.py:1082:            await self._drive_dialog_turns(self._current_world_tick())
src/erre_sandbox/world/tick.py:1084:    def _run_dialog_tick(self) -> None:
src/erre_sandbox/world/tick.py:1108:            logger.exception("dialog scheduler tick raised")
src/erre_sandbox/world/tick.py:1113:        Shared by ``_run_dialog_tick``, ``_drive_dialog_turns``, and
src/erre_sandbox/world/tick.py:1131:    async def _drive_dialog_turns(self, world_tick: int) -> None:
src/erre_sandbox/world/tick.py:1143:           ``len(transcript) >= speaker.cognitive.dialog_turn_budget``.
src/erre_sandbox/world/tick.py:1150:           :meth:`InMemoryDialogScheduler.record_turn` (updates transcript and
src/erre_sandbox/world/tick.py:1152:           the WebSocket consumers). Scheduler ``record_turn`` does not emit
src/erre_sandbox/world/tick.py:1202:                scheduler.record_turn(res)
src/erre_sandbox/world/tick.py:1225:        :meth:`_drive_dialog_turns` then runs under ``asyncio.gather``.
src/erre_sandbox/world/tick.py:1244:            budget = speaker_rt.state.cognitive.dialog_turn_budget
src/erre_sandbox/world/tick.py:1247:                    scheduler.close_dialog(did, reason="exhausted", tick=world_tick)
tests/test_schemas.py:589:    for method_name in ("schedule_initiate", "record_turn", "close_dialog"):
tests/test_schemas_m5.py:5:* ``Cognitive.dialog_turn_budget`` default = 6, ``ge=0``
tests/test_schemas_m5.py:47:# asserted because they are *additive* — M5's dialog_turn_budget etc. are
tests/test_schemas_m5.py:51:# ---------- §4 Cognitive.dialog_turn_budget ---------------------------------
tests/test_schemas_m5.py:54:def test_cognitive_dialog_turn_budget_default_is_six() -> None:
tests/test_schemas_m5.py:56:    assert cognitive.dialog_turn_budget == 6
tests/test_schemas_m5.py:59:def test_cognitive_dialog_turn_budget_accepts_zero() -> None:
tests/test_schemas_m5.py:60:    cognitive = Cognitive(dialog_turn_budget=0)
tests/test_schemas_m5.py:61:    assert cognitive.dialog_turn_budget == 0
tests/test_schemas_m5.py:64:def test_cognitive_dialog_turn_budget_rejects_negative() -> None:
tests/test_schemas_m5.py:66:        Cognitive(dialog_turn_budget=-1)
tests/schema_golden/control_envelope.schema.json:170:        "dialog_turn_budget": {
tests/schema_golden/control_envelope.schema.json:227:      "description": "A dialog has ended (M4 foundation).\n\n``reason`` is a closed literal set so the gateway and the scheduler can\ndispatch on it without string matching.\n\nM5 adds ``\"exhausted\"`` to signal that the agent hit its\n:attr:`Cognitive.dialog_turn_budget` cap (distinct from the\nscheduler's ``\"timeout\"``, which is driven by wall-clock).",
tests/schema_golden/control_envelope.schema.json:321:      "description": "A single turn inside an ongoing dialog (M4 foundation).\n\n``speaker_id`` and ``addressee_id`` are both carried so Godot can drive\nthe correct animations (speech bubble / head-turn) without re-deriving\norientation from world state.\n\n``turn_index`` was added in M5 (0.3.0-m5) so consumers can (a) detect\nout-of-order delivery over WebSocket and (b) correlate with\n:attr:`Cognitive.dialog_turn_budget` for exhaustion close-out. The first\nturn of a dialog is ``turn_index=0`` and the value increases by 1 per\nemitted :class:`DialogTurnMsg`.",
tests/schema_golden/control_envelope.schema.json:357:          "description": "Monotonic 0-based index within the dialog. Increments by 1 per emitted turn across both speakers. Paired with ``Cognitive.dialog_turn_budget`` to drive the exhaustion close.",
tests/test_evidence/test_golden_baseline.py:9:   per stimulus through ``schedule_initiate`` / ``record_turn`` /
tests/test_evidence/test_golden_baseline.py:10:   ``close_dialog`` (Codex HIGH-4: there is no input queue surface).
tests/test_evidence/test_golden_baseline.py:358:    # Scheduler is empty after the run — close_dialog actually closed it.
tests/test_integration/test_slice_gamma_e2e.py:5:1. ``InMemoryDialogScheduler.record_turn`` invokes the relational sink
tests/test_integration/test_slice_gamma_e2e.py:154:        scheduler.record_turn(
tests/test_integration/test_slice_gamma_e2e.py:262:    scheduler.record_turn(
tests/schema_golden/agent_state.schema.json:30:        "dialog_turn_budget": {
tests/test_world/test_per_agent_cognition_period.py:4:but :meth:`WorldRuntime._on_cognition_tick` now selects only agents whose
tests/test_integration/test_dialog_sink.py:5:via a static dict, emits three ``record_turn`` calls under one dialog, and
tests/test_integration/test_dialog_sink.py:57:    so tests peek at ``scheduler._open`` to drive ``record_turn`` with a
tests/test_integration/test_dialog_sink.py:70:async def test_record_turn_persists_through_sink(store: MemoryStore) -> None:
tests/test_integration/test_dialog_sink.py:85:        scheduler.record_turn(
tests/test_integration/test_dialog_sink.py:118:    scheduler.record_turn(
tests/test_integration/test_dialog.py:65:    for method in ("schedule_initiate", "record_turn", "close_dialog"):
tests/test_integration/test_dialog.py:125:    scheduler.close_dialog(dialog_id, reason="completed")
tests/test_integration/test_dialog.py:142:    scheduler.close_dialog(dialog_id, reason="completed")
tests/test_integration/test_dialog.py:153:# record_turn / close_dialog
tests/test_integration/test_dialog.py:157:def test_record_turn_appends_to_transcript() -> None:
tests/test_integration/test_dialog.py:171:    scheduler.record_turn(turn)
tests/test_integration/test_dialog.py:175:def test_record_turn_raises_for_unknown_dialog() -> None:
tests/test_integration/test_dialog.py:187:        scheduler.record_turn(bogus)
tests/test_integration/test_dialog.py:190:def test_close_dialog_emits_envelope_and_frees_pair() -> None:
tests/test_integration/test_dialog.py:197:    close = scheduler.close_dialog(dialog_id, reason="completed")
tests/test_integration/test_dialog.py:209:def test_close_dialog_raises_for_unknown_id() -> None:
tests/test_integration/test_dialog.py:213:        scheduler.close_dialog("d_missing", reason="completed")
tests/test_integration/test_dialog.py:228:    scheduler.tick(5, views)
tests/test_integration/test_dialog.py:240:    scheduler.tick(5, views)
tests/test_integration/test_dialog.py:248:    scheduler.tick(1, [AgentView(agent_id="solo", zone=Zone.PERIPATOS, tick=1)])
tests/test_integration/test_dialog.py:255:    scheduler.tick(
tests/test_integration/test_dialog.py:270:    scheduler.tick(
tests/test_integration/test_dialog.py:292:    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 1, views_same_zone)
tests/test_integration/test_dialog.py:296:    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 2, views_same_zone)
tests/test_integration/test_dialog.py:342:    scheduler.close_dialog(did, reason="completed")
tests/test_integration/test_dialog.py:347:# F1 regression — close_dialog tick parameter (codex review 2026-04-28)
tests/test_integration/test_dialog.py:351:def test_close_dialog_uses_explicit_tick_when_provided() -> None:
tests/test_integration/test_dialog.py:358:    close = scheduler.close_dialog(did, reason="completed", tick=explicit_tick)
tests/test_integration/test_dialog.py:388:    scheduler.tick(
tests/test_integration/test_dialog.py:401:def test_close_dialog_falls_back_to_last_activity_when_tick_omitted() -> None:
tests/test_integration/test_dialog.py:415:    scheduler.record_turn(turn)
tests/test_integration/test_dialog.py:416:    close = scheduler.close_dialog(did, reason="completed")
tests/test_integration/test_slice_delta_e2e.py:140:        scheduler.record_turn(
tests/test_integration/test_slice_delta_e2e.py:188:        scheduler.record_turn(
tests/test_integration/test_slice_delta_e2e.py:219:    scheduler.record_turn(
tests/test_integration/test_slice_delta_e2e.py:261:        scheduler.record_turn(
tests/test_integration/test_slice_delta_e2e.py:309:        scheduler.record_turn(
tests/test_integration/test_slice_delta_e2e.py:373:    scheduler.record_turn(
tests/test_integration/test_slice_delta_e2e.py:425:        scheduler.record_turn(
tests/test_integration/test_dialog_turn.py:196:#     when len(transcript) >= dialog_turn_budget, using scheduler.transcript_of
tests/test_integration/test_dialog_turn.py:223:        scheduler.record_turn(
tests/test_integration/test_dialog_turn.py:236:    budget = kant_state.cognitive.dialog_turn_budget
tests/test_integration/test_dialog_turn.py:238:    close_env = scheduler.close_dialog(dialog_id, reason="exhausted")
tests/test_integration/test_dialog_turn.py:241:    # envelopes via the sink from ``schedule_initiate`` and ``close_dialog``.
tests/test_integration/test_dialog_turn.py:242:    # ``record_turn`` accumulates transcript state silently — the gateway is
tests/test_world/test_tick.py:202:    async def test_cognition_tick_calls_step_for_each_agent(
tests/test_world/test_tick.py:227:    async def test_cognition_tick_swaps_pending_observations(
tests/test_world/test_tick.py:330:        # M7ζ-3 phase wheel: ``_on_cognition_tick`` reads ``clock.monotonic``
tests/test_integration/test_dialog_golden_baseline_mode.py:85:    scheduler.close_dialog(dialog_id, reason="completed", tick=0)
tests/test_integration/test_dialog_golden_baseline_mode.py:102:    scheduler.close_dialog(dialog_id, reason="completed")
tests/test_integration/test_dialog_golden_baseline_mode.py:130:    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 100, agents=())
tests/test_integration/test_dialog_golden_baseline_mode.py:142:    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 1, agents=())
tests/test_integration/test_dialog_golden_baseline_mode.py:190:    scheduler.close_dialog(dialog_id, reason="completed", tick=0)
tests/test_integration/test_dialog_orchestration_wiring.py:3:Covers :meth:`WorldRuntime.attach_dialog_generator` and the private
tests/test_integration/test_dialog_orchestration_wiring.py:4:``_drive_dialog_turns`` step called from ``_on_cognition_tick``:
tests/test_integration/test_dialog_orchestration_wiring.py:6:* budget boundary (`turn_index >= dialog_turn_budget` => exhausted close)
tests/test_integration/test_dialog_orchestration_wiring.py:14:end-to-end without the LLM. The ``_drive_dialog_turns`` method is called
tests/test_integration/test_dialog_orchestration_wiring.py:126:        cognitive={"dialog_turn_budget": budget},
tests/test_integration/test_dialog_orchestration_wiring.py:132:        cognitive={"dialog_turn_budget": budget},
tests/test_integration/test_dialog_orchestration_wiring.py:153:    runtime.attach_dialog_scheduler(scheduler)
tests/test_integration/test_dialog_orchestration_wiring.py:167:    scheduler.record_turn(
tests/test_integration/test_dialog_orchestration_wiring.py:184:async def test_drive_dialog_turns_generates_when_under_budget(
tests/test_integration/test_dialog_orchestration_wiring.py:194:    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]
tests/test_integration/test_dialog_orchestration_wiring.py:199:    await runtime._drive_dialog_turns(world_tick=1)
tests/test_integration/test_dialog_orchestration_wiring.py:213:async def test_drive_dialog_turns_closes_with_exhausted_when_budget_hit(
tests/test_integration/test_dialog_orchestration_wiring.py:223:    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]
tests/test_integration/test_dialog_orchestration_wiring.py:239:    await runtime._drive_dialog_turns(world_tick=10)
tests/test_integration/test_dialog_orchestration_wiring.py:257:async def test_drive_dialog_turns_speaker_alternation(
tests/test_integration/test_dialog_orchestration_wiring.py:266:    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]
tests/test_integration/test_dialog_orchestration_wiring.py:273:    await runtime._drive_dialog_turns(world_tick=1)
tests/test_integration/test_dialog_orchestration_wiring.py:278:    await runtime._drive_dialog_turns(world_tick=2)
tests/test_integration/test_dialog_orchestration_wiring.py:283:    await runtime._drive_dialog_turns(world_tick=3)
tests/test_integration/test_dialog_orchestration_wiring.py:292:async def test_drive_dialog_turns_none_return_emits_nothing(
tests/test_integration/test_dialog_orchestration_wiring.py:301:    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]
tests/test_integration/test_dialog_orchestration_wiring.py:310:    await runtime._drive_dialog_turns(world_tick=1)
tests/test_integration/test_dialog_orchestration_wiring.py:312:    # Generator was called but returned None — no record_turn, no sink emit.
tests/test_integration/test_dialog_orchestration_wiring.py:318:async def test_drive_dialog_turns_exception_does_not_break_siblings(
tests/test_integration/test_dialog_orchestration_wiring.py:351:    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]
tests/test_integration/test_dialog_orchestration_wiring.py:356:    await runtime._drive_dialog_turns(world_tick=1)
tests/test_integration/test_dialog_orchestration_wiring.py:373:async def test_drive_dialog_turns_without_generator_is_noop(
tests/test_integration/test_dialog_orchestration_wiring.py:381:    # Deliberately DO NOT attach_dialog_generator.
tests/test_integration/test_dialog_orchestration_wiring.py:385:    await runtime._drive_dialog_turns(world_tick=1)
tests/test_integration/test_dialog_orchestration_wiring.py:395:async def test_drive_dialog_turns_without_scheduler_is_noop() -> None:
tests/test_integration/test_dialog_orchestration_wiring.py:408:    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]
tests/test_integration/test_dialog_orchestration_wiring.py:411:    await runtime._drive_dialog_turns(world_tick=1)
tests/test_integration/test_dialog_orchestration_wiring.py:420:async def test_drive_dialog_turns_preserves_initiate_envelope(
tests/test_integration/test_dialog_orchestration_wiring.py:430:    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]
tests/test_integration/test_dialog_orchestration_wiring.py:437:    await runtime._drive_dialog_turns(world_tick=1)
tests/test_integration/test_dialog_orchestration_wiring.py:450:async def test_drive_dialog_turns_works_after_participants_leave_zone(
tests/test_integration/test_dialog_orchestration_wiring.py:464:    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]
tests/test_integration/test_dialog_orchestration_wiring.py:474:    await runtime._drive_dialog_turns(world_tick=1)
tests/test_integration/test_dialog_orchestration_wiring.py:479:# Regression — attach_dialog_generator is idempotent in intent
tests/test_integration/test_dialog_orchestration_wiring.py:483:def test_attach_dialog_generator_replaces_previous(
tests/test_integration/test_dialog_orchestration_wiring.py:489:    The method mirrors :meth:`WorldRuntime.attach_dialog_scheduler`'s
tests/test_integration/test_dialog_orchestration_wiring.py:499:    runtime.attach_dialog_generator(gen1)  # type: ignore[arg-type]
tests/test_integration/test_dialog_orchestration_wiring.py:500:    runtime.attach_dialog_generator(gen2)  # type: ignore[arg-type]
tests/test_integration/test_dialog_orchestration_wiring.py:518:async def test_drive_dialog_turns_budget_boundary(
tests/test_integration/test_dialog_orchestration_wiring.py:530:    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]
tests/test_integration/test_dialog_orchestration_wiring.py:545:    await runtime._drive_dialog_turns(world_tick=10)
tests/test_integration/test_dialog_eval_natural_mode.py:141:    scheduler.tick(world_tick=0, agents=co_located)
tests/test_integration/test_dialog_eval_natural_mode.py:148:        scheduler.close_dialog(did, reason="exhausted", tick=0)
tests/test_integration/test_dialog_eval_natural_mode.py:160:    scheduler.tick(world_tick=far_tick, agents=scattered)
tests/test_integration/test_dialog_eval_natural_mode.py:182:    scheduler.tick(world_tick=0, agents=scattered)
tests/test_integration/test_dialog_eval_natural_mode.py:199:    scheduler.tick(world_tick=0, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:237:    scheduler.tick(world_tick=0, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:240:    scheduler.close_dialog(did, reason="exhausted", tick=0)
tests/test_integration/test_dialog_eval_natural_mode.py:244:        scheduler.tick(world_tick=w, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:251:    scheduler.tick(world_tick=scheduler.COOLDOWN_TICKS, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:265:    scheduler.tick(world_tick=0, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:279:    scheduler.tick(world_tick=0, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:283:    scheduler.tick(world_tick=scheduler.TIMEOUT_TICKS, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:312:    scheduler.tick(world_tick=0, agents=agents_initial)
tests/test_integration/test_dialog_eval_natural_mode.py:319:        scheduler.record_turn(
tests/test_integration/test_dialog_eval_natural_mode.py:329:        scheduler.close_dialog(did, reason="exhausted", tick=6)
tests/test_integration/test_dialog_eval_natural_mode.py:339:    scheduler.tick(world_tick=far_tick, agents=scattered)

codex
One important mismatch has surfaced: the current CLI default is already `90.0` minutes, while the v2 design still describes changing `30 → 60`. I’m checking whether that’s just stale prose or an implementation risk, because it affects the verdict.
exec
/bin/zsh -lc "nl -ba tests/test_integration/test_dialog.py | sed -n '220,410p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba tests/test_integration/test_dialog_golden_baseline_mode.py | sed -n '1,230p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   220	
   221	def test_tick_auto_fires_when_two_agents_share_reflective_zone() -> None:
   222	    captured, sink = _collector()
   223	    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.0))
   224	    views = [
   225	        AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=5),
   226	        AgentView(agent_id="b", zone=Zone.PERIPATOS, tick=5),
   227	    ]
   228	    scheduler.tick(5, views)
   229	    assert any(isinstance(c, DialogInitiateMsg) for c in captured)
   230	    assert scheduler.open_count == 1
   231	
   232	
   233	def test_tick_skips_when_rng_above_probability() -> None:
   234	    captured, sink = _collector()
   235	    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.99))
   236	    views = [
   237	        AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=5),
   238	        AgentView(agent_id="b", zone=Zone.PERIPATOS, tick=5),
   239	    ]
   240	    scheduler.tick(5, views)
   241	    assert captured == []
   242	    assert scheduler.open_count == 0
   243	
   244	
   245	def test_tick_skips_for_lone_agent() -> None:
   246	    captured, sink = _collector()
   247	    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.0))
   248	    scheduler.tick(1, [AgentView(agent_id="solo", zone=Zone.PERIPATOS, tick=1)])
   249	    assert captured == []
   250	
   251	
   252	def test_tick_skips_when_agents_in_different_zones() -> None:
   253	    captured, sink = _collector()
   254	    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.0))
   255	    scheduler.tick(
   256	        1,
   257	        [
   258	            AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=1),
   259	            AgentView(agent_id="b", zone=Zone.CHASHITSU, tick=1),
   260	        ],
   261	    )
   262	    assert captured == []
   263	
   264	
   265	def test_tick_auto_closes_timed_out_dialog() -> None:
   266	    captured, sink = _collector()
   267	    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.99))
   268	    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
   269	    # Fast-forward past TIMEOUT_TICKS with no turns recorded.
   270	    scheduler.tick(
   271	        InMemoryDialogScheduler.TIMEOUT_TICKS + 1,
   272	        [
   273	            AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=1),
   274	            AgentView(agent_id="b", zone=Zone.PERIPATOS, tick=1),
   275	        ],
   276	    )
   277	    assert any(
   278	        isinstance(c, DialogCloseMsg) and c.reason == "timeout" for c in captured
   279	    )
   280	    assert scheduler.open_count == 0
   281	
   282	
   283	def test_tick_respects_cooldown_after_auto_close() -> None:
   284	    captured, sink = _collector()
   285	    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.0))
   286	    views_same_zone = [
   287	        AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=0),
   288	        AgentView(agent_id="b", zone=Zone.PERIPATOS, tick=0),
   289	    ]
   290	    # Open then timeout-close.
   291	    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
   292	    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 1, views_same_zone)
   293	    initial_envelopes = len(captured)
   294	    # Immediately tick again — cooldown must suppress auto re-firing even
   295	    # though the RNG would otherwise admit.
   296	    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 2, views_same_zone)
   297	    assert len(captured) == initial_envelopes  # no new initiate/close
   298	
   299	
   300	# ---------------------------------------------------------------------------
   301	# iter_open_dialogs — orchestrator-integration enumerator (M5)
   302	# ---------------------------------------------------------------------------
   303	
   304	
   305	def test_iter_open_dialogs_returns_empty_when_no_open() -> None:
   306	    _captured, sink = _collector()
   307	    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
   308	    assert list(scheduler.iter_open_dialogs()) == []
   309	
   310	
   311	def test_iter_open_dialogs_yields_dialog_id_pair_and_zone() -> None:
   312	    _captured, sink = _collector()
   313	    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
   314	    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
   315	    entries = list(scheduler.iter_open_dialogs())
   316	    assert len(entries) == 1
   317	    did, init, target, zone = entries[0]
   318	    assert init == "a"
   319	    assert target == "b"
   320	    assert zone is Zone.PERIPATOS
   321	    # The dialog_id must match scheduler.get_dialog_id for the same pair.
   322	    assert scheduler.get_dialog_id("a", "b") == did
   323	
   324	
   325	def test_iter_open_dialogs_enumerates_multiple_dialogs() -> None:
   326	    _captured, sink = _collector()
   327	    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
   328	    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
   329	    scheduler.schedule_initiate("c", "d", Zone.CHASHITSU, tick=0)
   330	    entries = list(scheduler.iter_open_dialogs())
   331	    assert len(entries) == 2
   332	    pairs = {(init, target) for _did, init, target, _zone in entries}
   333	    assert pairs == {("a", "b"), ("c", "d")}
   334	
   335	
   336	def test_iter_open_dialogs_drops_closed_dialogs() -> None:
   337	    _captured, sink = _collector()
   338	    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
   339	    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
   340	    did = scheduler.get_dialog_id("a", "b")
   341	    assert did is not None
   342	    scheduler.close_dialog(did, reason="completed")
   343	    assert list(scheduler.iter_open_dialogs()) == []
   344	
   345	
   346	# ---------------------------------------------------------------------------
   347	# F1 regression — close_dialog tick parameter (codex review 2026-04-28)
   348	# ---------------------------------------------------------------------------
   349	
   350	
   351	def test_close_dialog_uses_explicit_tick_when_provided() -> None:
   352	    captured, sink = _collector()
   353	    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.0))
   354	    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
   355	    did = scheduler.get_dialog_id("a", "b")
   356	    assert did is not None
   357	    explicit_tick = 42
   358	    close = scheduler.close_dialog(did, reason="completed", tick=explicit_tick)
   359	    assert close.tick == explicit_tick
   360	    closes = [c for c in captured if isinstance(c, DialogCloseMsg)]
   361	    assert closes[-1].tick == explicit_tick
   362	    cooldown = InMemoryDialogScheduler.COOLDOWN_TICKS
   363	    assert (
   364	        scheduler.schedule_initiate(
   365	            "a",
   366	            "b",
   367	            Zone.PERIPATOS,
   368	            tick=explicit_tick + cooldown - 1,
   369	        )
   370	        is None
   371	    )
   372	    assert (
   373	        scheduler.schedule_initiate(
   374	            "a",
   375	            "b",
   376	            Zone.PERIPATOS,
   377	            tick=explicit_tick + cooldown + 1,
   378	        )
   379	        is not None
   380	    )
   381	
   382	
   383	def test_tick_timeout_close_emits_current_tick_not_last_activity() -> None:
   384	    captured, sink = _collector()
   385	    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.99))
   386	    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
   387	    timeout_world_tick = InMemoryDialogScheduler.TIMEOUT_TICKS + 1
   388	    scheduler.tick(
   389	        timeout_world_tick,
   390	        [
   391	            AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=timeout_world_tick),
   392	            AgentView(agent_id="b", zone=Zone.PERIPATOS, tick=timeout_world_tick),
   393	        ],
   394	    )
   395	    closes = [c for c in captured if isinstance(c, DialogCloseMsg)]
   396	    assert len(closes) == 1
   397	    assert closes[0].reason == "timeout"
   398	    assert closes[0].tick == timeout_world_tick
   399	
   400	
   401	def test_close_dialog_falls_back_to_last_activity_when_tick_omitted() -> None:
   402	    captured, sink = _collector()
   403	    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
   404	    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
   405	    did = scheduler.get_dialog_id("a", "b")
   406	    assert did is not None
   407	    turn = DialogTurnMsg(
   408	        tick=5,
   409	        dialog_id=did,
   410	        speaker_id="a",

 succeeded in 0ms:
     1	"""Unit tests for ``InMemoryDialogScheduler.golden_baseline_mode`` flag.
     2	
     3	m9-eval-system P2b minimum patch (design-final.md §Orchestrator,
     4	decisions.md ME-7): the external golden baseline driver flips this flag
     5	during the 200-stimulus phase to bypass cooldown / timeout / zone
     6	restriction. Default ``False`` keeps every existing test green; this
     7	suite verifies only the *bypass* semantics and the *runtime toggle*
     8	contract that the driver depends on (P2c uses one scheduler instance
     9	across stimulus + natural phases by flipping the public attribute).
    10	"""
    11	
    12	from __future__ import annotations
    13	
    14	from random import Random
    15	from typing import TYPE_CHECKING
    16	
    17	from erre_sandbox.integration.dialog import InMemoryDialogScheduler
    18	from erre_sandbox.schemas import DialogInitiateMsg, Zone
    19	
    20	if TYPE_CHECKING:
    21	    from collections.abc import Callable
    22	
    23	    from erre_sandbox.schemas import ControlEnvelope
    24	
    25	
    26	def _collector() -> tuple[list[ControlEnvelope], Callable[[ControlEnvelope], None]]:
    27	    captured: list[ControlEnvelope] = []
    28	
    29	    def sink(env: ControlEnvelope) -> None:
    30	        captured.append(env)
    31	
    32	    return captured, sink
    33	
    34	
    35	# ---------------------------------------------------------------------------
    36	# Default behaviour (False) — existing semantics unchanged
    37	# ---------------------------------------------------------------------------
    38	
    39	
    40	def test_default_constructor_keeps_mode_false() -> None:
    41	    _captured, sink = _collector()
    42	    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    43	    assert scheduler.golden_baseline_mode is False
    44	
    45	
    46	# ---------------------------------------------------------------------------
    47	# Mode True — zone restriction bypass (Zone.STUDY admitted)
    48	# ---------------------------------------------------------------------------
    49	
    50	
    51	def test_mode_true_admits_study_zone() -> None:
    52	    """Stimulus battery includes ``Zone.STUDY`` for Kant/Nietzsche claims."""
    53	    _captured, sink = _collector()
    54	    scheduler = InMemoryDialogScheduler(
    55	        envelope_sink=sink,
    56	        golden_baseline_mode=True,
    57	    )
    58	    admitted = scheduler.schedule_initiate("kant", "interlocutor", Zone.STUDY, tick=0)
    59	    assert isinstance(admitted, DialogInitiateMsg)
    60	    assert admitted.zone == Zone.STUDY
    61	
    62	
    63	def test_mode_false_still_rejects_study_zone() -> None:
    64	    """Default mode keeps the natural-dialog cultural restriction."""
    65	    _captured, sink = _collector()
    66	    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    67	    assert scheduler.schedule_initiate("a", "b", Zone.STUDY, tick=0) is None
    68	
    69	
    70	# ---------------------------------------------------------------------------
    71	# Mode True — cooldown bypass (rapid stimulus loop on same pair)
    72	# ---------------------------------------------------------------------------
    73	
    74	
    75	def test_mode_true_bypasses_cooldown_on_same_pair() -> None:
    76	    """70 stimulus × 3 cycles drives the same persona pair without 30-tick gaps."""
    77	    _captured, sink = _collector()
    78	    scheduler = InMemoryDialogScheduler(
    79	        envelope_sink=sink,
    80	        golden_baseline_mode=True,
    81	    )
    82	    scheduler.schedule_initiate("kant", "interlocutor", Zone.PERIPATOS, tick=0)
    83	    dialog_id = scheduler.get_dialog_id("kant", "interlocutor")
    84	    assert dialog_id is not None
    85	    scheduler.close_dialog(dialog_id, reason="completed", tick=0)
    86	    # Re-open immediately at tick=1 (well within the 30-tick cooldown window).
    87	    reopened = scheduler.schedule_initiate(
    88	        "kant",
    89	        "interlocutor",
    90	        Zone.PERIPATOS,
    91	        tick=1,
    92	    )
    93	    assert isinstance(reopened, DialogInitiateMsg)
    94	
    95	
    96	def test_mode_false_still_rejects_during_cooldown() -> None:
    97	    _captured, sink = _collector()
    98	    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    99	    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
   100	    dialog_id = scheduler.get_dialog_id("a", "b")
   101	    assert dialog_id is not None
   102	    scheduler.close_dialog(dialog_id, reason="completed")
   103	    inside_cooldown = scheduler.schedule_initiate(
   104	        "a",
   105	        "b",
   106	        Zone.PERIPATOS,
   107	        tick=InMemoryDialogScheduler.COOLDOWN_TICKS - 1,
   108	    )
   109	    assert inside_cooldown is None
   110	
   111	
   112	# ---------------------------------------------------------------------------
   113	# Mode True — timeout suppression in tick()
   114	# ---------------------------------------------------------------------------
   115	
   116	
   117	def test_mode_true_suppresses_timeout_close_in_tick() -> None:
   118	    """Driver explicitly closes dialogs; tick() must not race-close them."""
   119	    _captured, sink = _collector()
   120	    rng = Random(0)
   121	    scheduler = InMemoryDialogScheduler(
   122	        envelope_sink=sink,
   123	        rng=rng,
   124	        golden_baseline_mode=True,
   125	    )
   126	    scheduler.schedule_initiate("kant", "interlocutor", Zone.PERIPATOS, tick=0)
   127	    dialog_id = scheduler.get_dialog_id("kant", "interlocutor")
   128	    assert dialog_id is not None
   129	    # Empty agents iterable so auto-fire path doesn't add new dialogs.
   130	    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 100, agents=())
   131	    # Dialog must still be open — driver is the sole closer in golden mode.
   132	    assert scheduler.open_count == 1
   133	    assert scheduler.get_dialog_id("kant", "interlocutor") == dialog_id
   134	
   135	
   136	def test_mode_false_still_auto_closes_on_timeout() -> None:
   137	    _captured, sink = _collector()
   138	    rng = Random(0)
   139	    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=rng)
   140	    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
   141	    assert scheduler.open_count == 1
   142	    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 1, agents=())
   143	    assert scheduler.open_count == 0
   144	
   145	
   146	# ---------------------------------------------------------------------------
   147	# Mode True — invariants that MUST still hold (sanity for driver)
   148	# ---------------------------------------------------------------------------
   149	
   150	
   151	def test_mode_true_still_rejects_self_pair() -> None:
   152	    """Same-id initiator/target is a programming error in any mode."""
   153	    _captured, sink = _collector()
   154	    scheduler = InMemoryDialogScheduler(
   155	        envelope_sink=sink,
   156	        golden_baseline_mode=True,
   157	    )
   158	    assert scheduler.schedule_initiate("kant", "kant", Zone.STUDY, tick=0) is None
   159	
   160	
   161	def test_mode_true_still_rejects_already_open_pair() -> None:
   162	    """Driver must close before re-opening even in golden mode."""
   163	    _captured, sink = _collector()
   164	    scheduler = InMemoryDialogScheduler(
   165	        envelope_sink=sink,
   166	        golden_baseline_mode=True,
   167	    )
   168	    scheduler.schedule_initiate("kant", "interlocutor", Zone.STUDY, tick=0)
   169	    second = scheduler.schedule_initiate("kant", "interlocutor", Zone.STUDY, tick=1)
   170	    assert second is None
   171	
   172	
   173	# ---------------------------------------------------------------------------
   174	# Runtime toggle (driver flips between phases on one instance)
   175	# ---------------------------------------------------------------------------
   176	
   177	
   178	def test_runtime_toggle_enables_then_disables_bypass() -> None:
   179	    """P2c driver: stimulus phase mode=True → flip → natural phase mode=False."""
   180	    _captured, sink = _collector()
   181	    scheduler = InMemoryDialogScheduler(
   182	        envelope_sink=sink,
   183	        golden_baseline_mode=True,
   184	    )
   185	    # Phase 1: STUDY admitted while True.
   186	    admitted = scheduler.schedule_initiate("kant", "interlocutor", Zone.STUDY, tick=0)
   187	    assert isinstance(admitted, DialogInitiateMsg)
   188	    dialog_id = scheduler.get_dialog_id("kant", "interlocutor")
   189	    assert dialog_id is not None
   190	    scheduler.close_dialog(dialog_id, reason="completed", tick=0)
   191	
   192	    # Driver flips to False between phases.
   193	    scheduler.golden_baseline_mode = False
   194	
   195	    # Phase 2: STUDY is now rejected again (natural-dialog rules restored).
   196	    rejected = scheduler.schedule_initiate(
   197	        "kant",
   198	        "interlocutor",
   199	        Zone.STUDY,
   200	        tick=InMemoryDialogScheduler.COOLDOWN_TICKS + 1,
   201	    )
   202	    assert rejected is None
   203	    # And cooldown applies again — at tick just past close, PERIPATOS within
   204	    # cooldown also rejected.
   205	    inside_cooldown = scheduler.schedule_initiate(
   206	        "kant",
   207	        "interlocutor",
   208	        Zone.PERIPATOS,
   209	        tick=1,
   210	    )
   211	    assert inside_cooldown is None

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/world/tick.py | sed -n '1120,1275p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/world/tick.py | sed -n '720,1120p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
  1120	
  1121	    def _agent_views(self) -> Sequence[AgentView]:
  1122	        return [
  1123	            AgentView(
  1124	                agent_id=rt.agent_id,
  1125	                zone=rt.state.position.zone,
  1126	                tick=rt.state.tick,
  1127	            )
  1128	            for rt in self._agents.values()
  1129	        ]
  1130	
  1131	    async def _drive_dialog_turns(self, world_tick: int) -> None:
  1132	        """Walk every open dialog and either generate a turn or close at budget.
  1133	
  1134	        Called only when both :attr:`_dialog_scheduler` and
  1135	        :attr:`_dialog_generator` are set. For each open dialog the method
  1136	        consults :meth:`InMemoryDialogScheduler.iter_open_dialogs` and:
  1137	
  1138	        1. Picks the next speaker by strict alternation:
  1139	           ``turn_index % 2 == 0`` => initiator, else target. Derived from
  1140	           ``len(transcript)`` rather than a tracked counter so the scheduler
  1141	           remains the single source of truth.
  1142	        2. Closes the dialog with ``reason="exhausted"`` when
  1143	           ``len(transcript) >= speaker.cognitive.dialog_turn_budget``.
  1144	        3. Otherwise dispatches the generator concurrently via
  1145	           :func:`asyncio.gather` with ``return_exceptions=True`` so one
  1146	           misbehaving pair cannot cancel the siblings. ``None`` return is a
  1147	           soft close — the existing timeout path will reap it later. An
  1148	           exception logs at ``WARNING`` and leaves the dialog untouched.
  1149	        4. On a fresh ``DialogTurnMsg`` it calls
  1150	           :meth:`InMemoryDialogScheduler.record_turn` (updates transcript and
  1151	           ``last_activity_tick``) and :meth:`inject_envelope` (fan-out to
  1152	           the WebSocket consumers). Scheduler ``record_turn`` does not emit
  1153	           on its own, so the explicit inject here is load-bearing.
  1154	
  1155	        If a referenced speaker agent is not registered with this runtime
  1156	        the dialog is skipped and a warning logged — it means the runtime
  1157	        and scheduler have drifted, which is a bug in higher-layer wiring.
  1158	        """
  1159	        scheduler = self._dialog_scheduler
  1160	        generator = self._dialog_generator
  1161	        if scheduler is None or generator is None:
  1162	            return
  1163	        open_dialogs: list[tuple[str, str, str, Zone]] = list(
  1164	            scheduler.iter_open_dialogs(),
  1165	        )
  1166	        if not open_dialogs:
  1167	            return
  1168	
  1169	        pending = self._stage_dialog_turns(
  1170	            scheduler=scheduler,
  1171	            generator=generator,
  1172	            open_dialogs=open_dialogs,
  1173	            world_tick=world_tick,
  1174	        )
  1175	        if not pending:
  1176	            return
  1177	        results = await asyncio.gather(
  1178	            *(p.coro for p in pending),
  1179	            return_exceptions=True,
  1180	        )
  1181	        for p, res in zip(pending, results, strict=True):
  1182	            if isinstance(res, BaseException):
  1183	                logger.warning(
  1184	                    "dialog turn generation failed for dialog %s speaker %s: %s",
  1185	                    p.dialog_id,
  1186	                    p.speaker_id,
  1187	                    res,
  1188	                )
  1189	                continue
  1190	            if res is None:
  1191	                # Soft close — leave for timeout reaper.
  1192	                continue
  1193	            if not isinstance(res, DialogTurnMsg):
  1194	                logger.warning(
  1195	                    "dialog turn generator returned unexpected type %s "
  1196	                    "for dialog %s — dropping",
  1197	                    type(res).__name__,
  1198	                    p.dialog_id,
  1199	                )
  1200	                continue
  1201	            try:
  1202	                scheduler.record_turn(res)
  1203	            except KeyError:
  1204	                # Dialog closed mid-gather (timeout / exhausted / external).
  1205	                logger.debug(
  1206	                    "dialog %s closed before turn %d could be recorded",
  1207	                    p.dialog_id,
  1208	                    p.turn_index,
  1209	                )
  1210	                continue
  1211	            self.inject_envelope(res)
  1212	
  1213	    def _stage_dialog_turns(
  1214	        self,
  1215	        *,
  1216	        scheduler: DialogScheduler,
  1217	        generator: DialogTurnGenerator,
  1218	        open_dialogs: Sequence[tuple[str, str, str, Zone]],
  1219	        world_tick: int,
  1220	    ) -> list[_PendingTurn]:
  1221	        """Decide per-dialog what to do this tick: close, skip, or enqueue.
  1222	
  1223	        Synchronous because every decision (budget / unknown agent / close)
  1224	        is local state. Returned pending turns are staged coroutines that
  1225	        :meth:`_drive_dialog_turns` then runs under ``asyncio.gather``.
  1226	        """
  1227	        pending: list[_PendingTurn] = []
  1228	        for did, init_id, target_id, _zone in open_dialogs:
  1229	            transcript = scheduler.transcript_of(did)
  1230	            turn_index = len(transcript)
  1231	            speaker_id = init_id if turn_index % 2 == 0 else target_id
  1232	            addressee_id = target_id if speaker_id == init_id else init_id
  1233	            speaker_rt = self._agents.get(speaker_id)
  1234	            addressee_rt = self._agents.get(addressee_id)
  1235	            if speaker_rt is None or addressee_rt is None:
  1236	                logger.warning(
  1237	                    "dialog %s references unregistered agent(s) "
  1238	                    "speaker=%s addressee=%s — skipping",
  1239	                    did,
  1240	                    speaker_id,
  1241	                    addressee_id,
  1242	                )
  1243	                continue
  1244	            budget = speaker_rt.state.cognitive.dialog_turn_budget
  1245	            if turn_index >= budget:
  1246	                try:
  1247	                    scheduler.close_dialog(did, reason="exhausted", tick=world_tick)
  1248	                except KeyError:
  1249	                    # Racy concurrent close (timeout already ran) — ignore.
  1250	                    logger.debug("dialog %s already closed before exhaust", did)
  1251	                continue
  1252	            pending.append(
  1253	                _PendingTurn(
  1254	                    dialog_id=did,
  1255	                    speaker_id=speaker_id,
  1256	                    addressee_id=addressee_id,
  1257	                    turn_index=turn_index,
  1258	                    coro=generator.generate_turn(
  1259	                        dialog_id=did,
  1260	                        speaker_state=speaker_rt.state,
  1261	                        speaker_persona=speaker_rt.persona,
  1262	                        addressee_state=addressee_rt.state,
  1263	                        transcript=transcript,
  1264	                        world_tick=world_tick,
  1265	                    ),
  1266	                ),
  1267	            )
  1268	        return pending
  1269	
  1270	    async def _on_heartbeat_tick(self) -> None:
  1271	        await self._envelopes.put(
  1272	            WorldTickMsg(
  1273	                tick=self._current_world_tick(),
  1274	                active_agents=len(self._agents),
  1275	            ),

 succeeded in 0ms:
   720	        second delivery path. Raw queue access stays private.
   721	        """
   722	        self._envelopes.put_nowait(envelope)
   723	
   724	    def attach_dialog_scheduler(self, scheduler: DialogScheduler) -> None:
   725	        """Install the scheduler consulted at the end of each cognition tick.
   726	
   727	        Separated from ``__init__`` because the scheduler's envelope sink
   728	        normally wants to call :meth:`inject_envelope` on this same runtime,
   729	        which is awkward to arrange before the runtime exists.
   730	        """
   731	        self._dialog_scheduler = scheduler
   732	
   733	    def attach_dialog_generator(self, generator: DialogTurnGenerator) -> None:
   734	        """Install the LLM-backed :class:`DialogTurnGenerator` (M5).
   735	
   736	        When attached, :meth:`_on_cognition_tick` walks every open dialog
   737	        after the scheduler's proximity-auto-fire / timeout-close pass and
   738	        either (a) closes the dialog with ``reason="exhausted"`` if the
   739	        speaker's ``dialog_turn_budget`` is saturated, or (b) asks the
   740	        generator for the next utterance and records/emits the resulting
   741	        :class:`DialogTurnMsg`. ``None`` from the generator leaves the
   742	        dialog untouched for the existing timeout path to reap.
   743	
   744	        Last-writer-wins: re-attaching replaces the previously attached
   745	        generator, mirroring :meth:`attach_dialog_scheduler`.
   746	        """
   747	        self._dialog_generator = generator
   748	
   749	    # ----- Lifecycle -----
   750	
   751	    async def run(self) -> None:
   752	        """Run the scheduler until :meth:`stop` is called.
   753	
   754	        Uses a single min-heap of absolute ``due_at`` timestamps; on each
   755	        iteration it pops the earliest event, awaits
   756	        :meth:`Clock.sleep_until`, invokes the handler (with per-handler
   757	        exception isolation so one bug cannot kill the loop), and reschedules
   758	        the event at ``due_at + period`` (anti-drift: absolute time, not
   759	        cumulative deltas).
   760	        """
   761	        now = self._clock.monotonic()
   762	        self._schedule(
   763	            now + self._physics_dt,
   764	            self._physics_dt,
   765	            self._on_physics_tick,
   766	            name="physics",
   767	        )
   768	        self._schedule(
   769	            now + self._cognition_period,
   770	            self._cognition_period,
   771	            self._on_cognition_tick,
   772	            name="cognition",
   773	        )
   774	        self._schedule(
   775	            now + self._heartbeat_period,
   776	            self._heartbeat_period,
   777	            self._on_heartbeat_tick,
   778	            name="heartbeat",
   779	        )
   780	
   781	        self._running = True
   782	        try:
   783	            while self._running and self._events:
   784	                ev = heapq.heappop(self._events)
   785	                await self._clock.sleep_until(ev.due_at)
   786	                if not self._running:
   787	                    break
   788	                try:
   789	                    await ev.handler()
   790	                except Exception:
   791	                    logger.exception("world tick handler %s failed", ev.name)
   792	                # Anti-drift: next due is previous due + period, not now + period.
   793	                self._seq += 1
   794	                next_due = ev.due_at + ev.period
   795	                heapq.heappush(
   796	                    self._events,
   797	                    replace(ev, due_at=next_due, seq=self._seq),
   798	                )
   799	        finally:
   800	            self._running = False
   801	
   802	    def stop(self) -> None:
   803	        """Signal :meth:`run` to return at the next scheduling point."""
   804	        self._running = False
   805	
   806	    # ----- Handlers -----
   807	
   808	    async def _on_physics_tick(self) -> None:
   809	        dt = self._physics_dt
   810	        for rt in self._agents.values():
   811	            # Capture the zone BEFORE model_copy overwrites it; otherwise the
   812	            # emitted ZoneTransitionEvent's from_zone would equal to_zone.
   813	            prev_zone = rt.state.position.zone
   814	            new_pos, zone_changed = step_kinematics(rt.kinematics, dt)
   815	            if new_pos != rt.state.position:
   816	                rt.state = rt.state.model_copy(update={"position": new_pos})
   817	            if zone_changed is not None:
   818	                rt.pending.append(
   819	                    ZoneTransitionEvent(
   820	                        tick=rt.state.tick,
   821	                        agent_id=rt.agent_id,
   822	                        from_zone=prev_zone,
   823	                        to_zone=zone_changed,
   824	                    ),
   825	                )
   826	        # M7ζ-3: pair separation nudge — runs after step_kinematics so it
   827	        # corrects any pair whose Python orchestrator routed them to
   828	        # near-identical waypoints before the proximity-event detector
   829	        # samples distances. Order matters: separation must precede
   830	        # ``_fire_proximity_events`` so the latter sees the post-nudge
   831	        # geometry and reports stable enter/leave crossings instead of
   832	        # oscillating around the threshold every tick.
   833	        if len(self._agents) >= 2:  # noqa: PLR2004 — "pair" is inherently 2
   834	            self._apply_separation_force()
   835	        # M6-A-2b: time-of-day cascade — emit a TemporalEvent for every
   836	        # registered agent when the simulated clock crosses a period
   837	        # boundary. No-agent ticks are hot-pathed so ``_time_start`` stays
   838	        # None until at least one agent is registered; when agents appear
   839	        # later their first tick sees elapsed near zero.
   840	        if self._agents:
   841	            self._fire_temporal_events()
   842	        # M6-A-2b: agent-pair proximity crossings. Requires at least two
   843	        # agents and the kinematic positions just advanced above, so this
   844	        # runs AFTER the move loop in the same tick. Single-agent worlds
   845	        # hot-path: no pairs, nothing to do.
   846	        if len(self._agents) >= 2:  # noqa: PLR2004 — "pair" is inherently 2
   847	            self._fire_proximity_events()
   848	        # M7 B1: agent-prop affordance entries. Also needs the kinematic
   849	        # positions just advanced above. Runs with any non-empty agent set —
   850	        # a lone agent still notices props. Props are loaded from the static
   851	        # ZONE_PROPS table so the loop cost is bounded by the MVP fixture
   852	        # (two chashitsu tea bowls in the initial scope).
   853	        if self._agents:
   854	            self._fire_affordance_events()
   855	
   856	    def _apply_separation_force(self) -> None:
   857	        """Nudge agent pairs apart on the XZ plane when distance < radius.
   858	
   859	        For each unordered pair, the threshold is the *larger* of the two
   860	        personas' ``separation_radius_m`` so a tight-bubble persona (e.g.
   861	        Rikyū's 1.2 m) does not block a wider-bubble peer (Kant 1.5 m)
   862	        from claiming personal space. When inside the radius both agents
   863	        receive a fixed :data:`_SEP_PUSH_M` push along the unit vector
   864	        between them; identical positions (``d == 0``) deterministically
   865	        fall back to ``(1, 0)`` so the test outcome is reproducible.
   866	
   867	        :class:`Kinematics` is kept in sync with :class:`Position` so the
   868	        next physics tick's ``step_kinematics`` integrates from the
   869	        post-nudge coordinate; the persisted ``AgentState`` carries the
   870	        same coordinate so the Godot ``agent_update`` envelope reflects
   871	        it without any wire-side change.
   872	
   873	        Complexity is ``O(n*(n-1)/2)`` over registered agents — fine for
   874	        the 3-agent MVP scale; revisit if MASTER-PLAN scales agent count.
   875	        """
   876	        for rt_a, rt_b in combinations(self._agents.values(), 2):
   877	            radius = max(
   878	                rt_a.persona.behavior_profile.separation_radius_m,
   879	                rt_b.persona.behavior_profile.separation_radius_m,
   880	            )
   881	            if radius == 0.0:
   882	                continue
   883	            dx = rt_a.state.position.x - rt_b.state.position.x
   884	            dz = rt_a.state.position.z - rt_b.state.position.z
   885	            d = math.hypot(dx, dz)
   886	            if d >= radius:
   887	                continue
   888	            if d == 0.0:
   889	                ux, uz = 1.0, 0.0
   890	            else:
   891	                ux, uz = dx / d, dz / d
   892	            for rt, sign in ((rt_a, +1.0), (rt_b, -1.0)):
   893	                new_pos = rt.state.position.model_copy(
   894	                    update={
   895	                        "x": rt.state.position.x + sign * ux * _SEP_PUSH_M,
   896	                        "z": rt.state.position.z + sign * uz * _SEP_PUSH_M,
   897	                    },
   898	                )
   899	                rt.state = rt.state.model_copy(update={"position": new_pos})
   900	                rt.kinematics.position = new_pos
   901	
   902	    def _fire_proximity_events(self) -> None:
   903	        """Detect agent-pair distance crossings of :data:`_PROXIMITY_THRESHOLD_M`.
   904	
   905	        Distance is computed on the XZ plane to match
   906	        :mod:`erre_sandbox.world.physics` (the Y axis carries avatar height,
   907	        not a meaningful spatial separation). For each unordered pair:
   908	
   909	        * First-time observation → cache distance, no event.
   910	        * Crossed from ``>= threshold`` to ``< threshold`` → emit
   911	          ``crossing="enter"`` to both agents.
   912	        * Crossed from ``< threshold`` to ``>= threshold`` → emit
   913	          ``crossing="leave"`` to both agents.
   914	        * Stayed on the same side → cache update only, no event.
   915	
   916	        Both sides of a crossing see the same ``distance_prev`` /
   917	        ``distance_now`` values; only ``other_agent_id`` differs. This
   918	        matches the observation stream's perspective-per-agent semantics
   919	        (each agent gets its own view of what just happened to it).
   920	        """
   921	        for rt_a, rt_b in combinations(self._agents.values(), 2):
   922	            dx = rt_a.state.position.x - rt_b.state.position.x
   923	            dz = rt_a.state.position.z - rt_b.state.position.z
   924	            distance = math.hypot(dx, dz)
   925	            key = frozenset({rt_a.agent_id, rt_b.agent_id})
   926	            prev = self._pair_distances.get(key)
   927	            self._pair_distances[key] = distance
   928	            if prev is None:
   929	                # First observation: no prior tick to compare against.
   930	                continue
   931	            crossed_enter = (
   932	                prev >= _PROXIMITY_THRESHOLD_M and distance < _PROXIMITY_THRESHOLD_M
   933	            )
   934	            crossed_leave = (
   935	                prev < _PROXIMITY_THRESHOLD_M and distance >= _PROXIMITY_THRESHOLD_M
   936	            )
   937	            if not (crossed_enter or crossed_leave):
   938	                continue
   939	            crossing: Literal["enter", "leave"] = "enter" if crossed_enter else "leave"
   940	            tick_a = rt_a.state.tick
   941	            tick_b = rt_b.state.tick
   942	            rt_a.pending.append(
   943	                ProximityEvent(
   944	                    tick=tick_a,
   945	                    agent_id=rt_a.agent_id,
   946	                    other_agent_id=rt_b.agent_id,
   947	                    distance_prev=prev,
   948	                    distance_now=distance,
   949	                    crossing=crossing,
   950	                ),
   951	            )
   952	            rt_b.pending.append(
   953	                ProximityEvent(
   954	                    tick=tick_b,
   955	                    agent_id=rt_b.agent_id,
   956	                    other_agent_id=rt_a.agent_id,
   957	                    distance_prev=prev,
   958	                    distance_now=distance,
   959	                    crossing=crossing,
   960	                ),
   961	            )
   962	
   963	    def _fire_affordance_events(self) -> None:
   964	        """Emit :class:`AffordanceEvent` when an agent enters a prop's radius.
   965	
   966	        Mirrors the crossing-only semantics of :meth:`_fire_proximity_events`:
   967	        the event fires once when the XZ distance first falls below
   968	        :data:`_AFFORDANCE_RADIUS_M`, then stays silent until the agent has
   969	        moved back out of range and re-entered. This matches ProximityEvent's
   970	        "edge, not level" design so chashitsu visitors do not flood the
   971	        observation stream while sitting next to a tea bowl.
   972	
   973	        Iterates every ``(agent, prop)`` pair in the static :data:`ZONE_PROPS`
   974	        table. Bound at MVP scope: three agents × two chashitsu bowls = six
   975	        distance checks per tick.
   976	        """
   977	        for zone, props in ZONE_PROPS.items():
   978	            if not props:
   979	                continue
   980	            for rt in self._agents.values():
   981	                ax = rt.state.position.x
   982	                az = rt.state.position.z
   983	                for prop in props:
   984	                    dx = ax - prop.x
   985	                    dz = az - prop.z
   986	                    distance = math.hypot(dx, dz)
   987	                    key = (rt.agent_id, prop.prop_id)
   988	                    prev = self._agent_prop_distances.get(key)
   989	                    self._agent_prop_distances[key] = distance
   990	                    if prev is None:
   991	                        # First observation: no prior tick to compare against.
   992	                        # Do not fire on the very first frame the prop is seen,
   993	                        # otherwise every spawn-inside-chashitsu triggers a
   994	                        # spurious entry even when the agent never moved.
   995	                        continue
   996	                    crossed_enter = (
   997	                        prev >= _AFFORDANCE_RADIUS_M and distance < _AFFORDANCE_RADIUS_M
   998	                    )
   999	                    if not crossed_enter:
  1000	                        continue
  1001	                    rt.pending.append(
  1002	                        AffordanceEvent(
  1003	                            tick=rt.state.tick,
  1004	                            agent_id=rt.agent_id,
  1005	                            prop_id=prop.prop_id,
  1006	                            prop_kind=prop.prop_kind,
  1007	                            zone=zone,
  1008	                            distance=distance,
  1009	                            salience=prop.salience,
  1010	                        ),
  1011	                    )
  1012	
  1013	    def _fire_temporal_events(self) -> None:
  1014	        """Detect and emit TimeOfDay boundary crossings for all agents."""
  1015	        now = self._clock.monotonic()
  1016	        if self._time_start is None:
  1017	            self._time_start = now
  1018	            # Silently sync the initial period to the boot time — no event
  1019	            # on first ever tick because there is no prior period to cite.
  1020	            self._current_period = _time_of_day(0.0, self._day_duration_s)
  1021	            return
  1022	        elapsed = now - self._time_start
  1023	        new_period = _time_of_day(elapsed, self._day_duration_s)
  1024	        if new_period == self._current_period:
  1025	            return
  1026	        previous = self._current_period
  1027	        self._current_period = new_period
  1028	        for rt in self._agents.values():
  1029	            rt.pending.append(
  1030	                TemporalEvent(
  1031	                    tick=rt.state.tick,
  1032	                    agent_id=rt.agent_id,
  1033	                    period_prev=previous,
  1034	                    period_now=new_period,
  1035	                ),
  1036	            )
  1037	
  1038	    async def _on_cognition_tick(self) -> None:
  1039	        if not self._agents:
  1040	            return
  1041	        # M7ζ-3 phase wheel: the global cognition heap event still fires at
  1042	        # ``_cognition_period`` cadence, but only agents whose
  1043	        # ``next_cognition_due`` has elapsed (and which are not in
  1044	        # post-MoveMsg dwell) actually step this tick. The 1e-6 tolerance
  1045	        # absorbs floating-point drift between the global heap due time and
  1046	        # the per-agent due time computed from ``cognition_period_s``.
  1047	        now = self._clock.monotonic()
  1048	        # Evaluate agents list once so that dict mutation during gather
  1049	        # (register_agent from inside a handler, if anyone ever does that)
  1050	        # cannot desynchronise the result / runtime pairing below.
  1051	        runtimes = list(self._agents.values())
  1052	        due: list[AgentRuntime] = []
  1053	        for rt in runtimes:
  1054	            if now < rt.dwell_until:
  1055	                continue  # in seiza dwell, skip this cognition tick
  1056	            if rt.next_cognition_due <= now + 1e-6:
  1057	                due.append(rt)
  1058	        if due:
  1059	            results = await asyncio.gather(
  1060	                *(self._step_one(rt) for rt in due),
  1061	                return_exceptions=True,
  1062	            )
  1063	            for rt, res in zip(due, results, strict=True):
  1064	                self._consume_result(rt, res)
  1065	                # ``cognition_period_s`` is the *minimum* gap between this
  1066	                # agent's cognition steps. ``dwell_until`` (set inside
  1067	                # ``_consume_result`` when a MoveMsg fires) layers an
  1068	                # *upper* override on top: when ``dwell_time_s >
  1069	                # cognition_period_s`` (e.g. Rikyū's 90 s dwell vs 18 s
  1070	                # period) dwell wins, when ``dwell_time_s <
  1071	                # cognition_period_s`` (e.g. Nietzsche's 5 s dwell vs 7 s
  1072	                # period) period still bounds the next step. This is the
  1073	                # intended semantics — dwell never speeds an agent up.
  1074	                rt.next_cognition_due = (
  1075	                    now + rt.persona.behavior_profile.cognition_period_s
  1076	                )
  1077	        # Dialog scheduler runs every global tick regardless of which agents
  1078	        # were due, so persona-driven cognition cadence does not starve
  1079	        # proximity-driven dialog initiations.
  1080	        self._run_dialog_tick()
  1081	        if self._dialog_generator is not None and self._dialog_scheduler is not None:
  1082	            await self._drive_dialog_turns(self._current_world_tick())
  1083	
  1084	    def _run_dialog_tick(self) -> None:
  1085	        """Evaluate the dialog scheduler after all per-agent cognition ran.
  1086	
  1087	        The scheduler consumes a narrow projection (:class:`AgentView`) of
  1088	        each runtime so it cannot reach into kinematics or the pending
  1089	        observation buffer. Dialog envelopes are delivered through the
  1090	        scheduler's injected sink, which :func:`bootstrap` wires back to
  1091	        :meth:`inject_envelope`.
  1092	        """
  1093	        if self._dialog_scheduler is None:
  1094	            return
  1095	        views = self._agent_views()
  1096	        # The scheduler type is a Protocol frozen in schemas.py §7.5 —
  1097	        # ``tick`` is the concrete extension exposed by the default
  1098	        # :class:`InMemoryDialogScheduler`. Callers supplying a custom
  1099	        # scheduler should either subclass that class or accept that the
  1100	        # proximity auto-fire logic is skipped.
  1101	        tick_fn = getattr(self._dialog_scheduler, "tick", None)
  1102	        if tick_fn is None:
  1103	            return
  1104	        try:
  1105	            tick_fn(self._current_world_tick(), views)
  1106	        except Exception:
  1107	            # A misbehaving scheduler must not crash the cognition loop.
  1108	            logger.exception("dialog scheduler tick raised")
  1109	
  1110	    def _current_world_tick(self) -> int:
  1111	        """Return the highest per-agent tick, or 0 when no agents are registered.
  1112	
  1113	        Shared by ``_run_dialog_tick``, ``_drive_dialog_turns``, and
  1114	        ``_on_heartbeat_tick`` so the three consumers of "current world
  1115	        tick" always see the same value. Cheap enough to recompute each
  1116	        call (M4 target N ≤ 10 agents); if agent counts grow we could
  1117	        cache and invalidate inside ``_consume_result``.
  1118	        """
  1119	        return max((rt.state.tick for rt in self._agents.values()), default=0)
  1120	

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/world/tick.py | sed -n '520,720p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   520	        """
   521	        rt = self._agents.get(agent_id)
   522	        if rt is None:
   523	            return None
   524	        return rt.state.position.zone
   525	
   526	    def apply_affinity_delta(
   527	        self,
   528	        *,
   529	        agent_id: str,
   530	        other_agent_id: str,
   531	        delta: float,
   532	        tick: int,
   533	        zone: Zone | None = None,
   534	    ) -> None:
   535	        """Apply an affinity ``delta`` to ``agent_id``'s bond with ``other_agent_id``.
   536	
   537	        Mutates :attr:`AgentRuntime.state` in place via ``model_copy`` so the
   538	        next ``AgentUpdateMsg`` snapshot picks up the new
   539	        :class:`RelationshipBond`. When ``agent_id`` has no existing bond
   540	        with ``other_agent_id`` a fresh bond is appended; otherwise the
   541	        existing bond's :attr:`RelationshipBond.affinity` is updated (clamped
   542	        through :func:`erre_sandbox.cognition.relational.apply_affinity`),
   543	        :attr:`RelationshipBond.ichigo_ichie_count` is incremented, and
   544	        :attr:`RelationshipBond.last_interaction_tick` is set to ``tick``.
   545	
   546	        M7δ extensions:
   547	
   548	        * ``zone`` — when supplied, written to
   549	          :attr:`RelationshipBond.last_interaction_zone` so the Godot
   550	          ``ReasoningPanel`` can render ``"<persona> affinity ±0.NN
   551	          (N turns, last in <zone> @ tick T)"``. Default ``None`` keeps
   552	          the field unset for callers that have not yet been migrated.
   553	        * ``Physical.emotional_conflict`` write — negative ``delta`` past
   554	          the M7δ trigger threshold (``< -0.05``) raises this field by
   555	          ``abs(delta) * 0.5`` (clamped to ``[0, 1]``). Decay back to
   556	          baseline lives in :func:`erre_sandbox.cognition.state.advance_physical`
   557	          (per-tick ``-0.02``). Closes the dangling-read at
   558	          ``cognition/state.py::sleep_penalty`` (R3 M4).
   559	
   560	        Silent no-op when ``agent_id`` is not registered: the relational
   561	        hook fires from the bootstrap turn-sink chain, which races a
   562	        possible (M7γ-out-of-scope) deregistration. Future M9+ removal
   563	        wiring should keep this fail-soft so a transient missing agent
   564	        cannot crash the live runtime.
   565	        """
   566	        # SAFETY: single-writer assumption. The relational sink in
   567	        # bootstrap is the sole producer of affinity-delta calls and runs
   568	        # synchronously inside ``InMemoryDialogScheduler.record_turn``.
   569	        # If M9 introduces parallel cognition cycles or external mutators
   570	        # this method must guard ``rt.state.model_copy`` with an
   571	        # ``asyncio.Lock`` to prevent lost updates (R3 H2).
   572	        rt = self._agents.get(agent_id)
   573	        if rt is None:
   574	            return
   575	        existing = list(rt.state.relationships)
   576	        new_bonds: list[RelationshipBond] = []
   577	        found = False
   578	        for bond in existing:
   579	            if bond.other_agent_id == other_agent_id:
   580	                new_bonds.append(
   581	                    bond.model_copy(
   582	                        update={
   583	                            "affinity": apply_affinity(bond.affinity, delta),
   584	                            "ichigo_ichie_count": bond.ichigo_ichie_count + 1,
   585	                            "last_interaction_tick": tick,
   586	                            "last_interaction_zone": zone,
   587	                        },
   588	                    ),
   589	                )
   590	                found = True
   591	            else:
   592	                new_bonds.append(bond)
   593	        if not found:
   594	            new_bonds.append(
   595	                RelationshipBond(
   596	                    other_agent_id=other_agent_id,
   597	                    affinity=apply_affinity(0.0, delta),
   598	                    familiarity=0.0,
   599	                    ichigo_ichie_count=1,
   600	                    last_interaction_tick=tick,
   601	                    last_interaction_zone=zone,
   602	                ),
   603	            )
   604	        # M7δ: negative delta past the trigger threshold raises the
   605	        # speaker / addressee's emotional_conflict so future cognition
   606	        # cycles read the residue (sleep_penalty already consumes it).
   607	        new_physical = rt.state.physical
   608	        if delta < _NEGATIVE_DELTA_TRIGGER:
   609	            bumped = min(
   610	                1.0,
   611	                rt.state.physical.emotional_conflict
   612	                + abs(delta) * _EMOTIONAL_CONFLICT_GAIN,
   613	            )
   614	            new_physical = rt.state.physical.model_copy(
   615	                update={"emotional_conflict": bumped},
   616	            )
   617	        rt.state = rt.state.model_copy(
   618	            update={"relationships": new_bonds, "physical": new_physical},
   619	        )
   620	
   621	    def apply_belief_promotion(
   622	        self,
   623	        *,
   624	        agent_id: str,
   625	        other_agent_id: str,
   626	        belief_kind: Literal["trust", "clash", "wary", "curious", "ambivalent"],
   627	    ) -> None:
   628	        """Stamp ``RelationshipBond.latest_belief_kind`` on a promoted dyad (M7ζ).
   629	
   630	        Called from the bootstrap relational sink the moment
   631	        :func:`erre_sandbox.cognition.belief.maybe_promote_belief` returns a
   632	        non-None record, so the next ``AgentUpdateMsg`` snapshot carries the
   633	        typed classification on the bond. Co-locating the write here (rather
   634	        than at agent_state-export time via a semantic_memory lookup) avoids
   635	        an extra DB read on every panel refresh; the bond IS the source of
   636	        truth for what the Godot ``ReasoningPanel`` renders.
   637	
   638	        Silent no-op when ``agent_id`` is not registered or the bond is
   639	        absent: the relational sink is fire-and-forget, identical to
   640	        :meth:`apply_affinity_delta`'s contract.
   641	
   642	        SAFETY: same single-writer assumption as :meth:`apply_affinity_delta`
   643	        — the bootstrap sink is the sole producer and runs synchronously.
   644	        """
   645	        rt = self._agents.get(agent_id)
   646	        if rt is None:
   647	            return
   648	        existing = list(rt.state.relationships)
   649	        new_bonds: list[RelationshipBond] = []
   650	        found = False
   651	        for bond in existing:
   652	            if bond.other_agent_id == other_agent_id:
   653	                new_bonds.append(
   654	                    bond.model_copy(update={"latest_belief_kind": belief_kind}),
   655	                )
   656	                found = True
   657	            else:
   658	                new_bonds.append(bond)
   659	        if not found:
   660	            # Defensive: a promotion without a prior bond should never
   661	            # happen (maybe_promote_belief reads bond fields), but if it
   662	            # does the sink stays fail-soft rather than fabricating a bond.
   663	            return
   664	        rt.state = rt.state.model_copy(update={"relationships": new_bonds})
   665	
   666	    def layout_snapshot(self, *, tick: int = 0) -> WorldLayoutMsg:
   667	        """Construct a :class:`WorldLayoutMsg` from the static zone tables (M7γ).
   668	
   669	        Pure read of :data:`erre_sandbox.world.zones.ZONE_CENTERS` and
   670	        :data:`~erre_sandbox.world.zones.ZONE_PROPS` — no runtime state is
   671	        consulted because in γ the world layout is immutable per run. The
   672	        gateway emits this message exactly once per WS connection
   673	        (see Slice γ Commit 3), immediately before completing the
   674	        handshake-side ``registry.add(...)`` call.
   675	
   676	        ``tick`` defaults to ``0`` to match the on-connect convention used
   677	        by the ``world_layout.json`` fixture and asserted by
   678	        ``tests/test_envelope_fixtures.py::test_shared_invariants_across_fixtures``.
   679	        """
   680	        zones = [
   681	            ZoneLayout(zone=zone, x=x, y=y, z=z)
   682	            for zone, (x, y, z) in ZONE_CENTERS.items()
   683	        ]
   684	        props: list[PropLayout] = [
   685	            PropLayout(
   686	                prop_id=spec.prop_id,
   687	                prop_kind=spec.prop_kind,
   688	                zone=zone,
   689	                x=spec.x,
   690	                y=spec.y,
   691	                z=spec.z,
   692	                salience=spec.salience,
   693	            )
   694	            for zone, prop_specs in ZONE_PROPS.items()
   695	            for spec in prop_specs
   696	        ]
   697	        return WorldLayoutMsg(tick=tick, zones=zones, props=props)
   698	
   699	    # ----- Envelope consumers (T14 hooks) -----
   700	
   701	    async def recv_envelope(self) -> ControlEnvelope:
   702	        """Await and return the next envelope (FIFO).
   703	
   704	        Blocking variant intended for T14's WebSocket producer.
   705	        """
   706	        return await self._envelopes.get()
   707	
   708	    def drain_envelopes(self) -> list[ControlEnvelope]:
   709	        """Non-blocking drain of all currently queued envelopes (FIFO)."""
   710	        out: list[ControlEnvelope] = []
   711	        while not self._envelopes.empty():
   712	            out.append(self._envelopes.get_nowait())
   713	        return out
   714	
   715	    def inject_envelope(self, envelope: ControlEnvelope) -> None:
   716	        """Append ``envelope`` to the fan-out queue from non-runtime code.
   717	
   718	        Exposed for the dialog scheduler's envelope sink so it can interleave
   719	        ``dialog_*`` messages with the cognition-generated stream without a
   720	        second delivery path. Raw queue access stays private.

exec
/bin/zsh -lc "rg -n \"state.tick|next_cognition_due|tick \\+|model_copy\\(update=.*tick|_consume_result|AgentState\\(\" src/erre_sandbox/world/tick.py src/erre_sandbox/cognition/cycle.py src/erre_sandbox/schemas.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
src/erre_sandbox/schemas.py:372:            "``next_cognition_due`` is advanced by this value (phase wheel) "
src/erre_sandbox/schemas.py:589:class AgentState(BaseModel):
src/erre_sandbox/cognition/cycle.py:187:    the current prompt. The caller (:meth:`WorldRuntime._consume_result`)
src/erre_sandbox/cognition/cycle.py:332:            tick=agent_state.tick,
src/erre_sandbox/cognition/cycle.py:427:            tick=agent_state.tick,
src/erre_sandbox/cognition/cycle.py:449:            tick=agent_state.tick + 1,
src/erre_sandbox/cognition/cycle.py:455:                "tick": agent_state.tick + 1,
src/erre_sandbox/cognition/cycle.py:491:                    tick=new_state.tick,
src/erre_sandbox/cognition/cycle.py:591:            tick=agent_state.tick,
src/erre_sandbox/cognition/cycle.py:598:            entered_at_tick=agent_state.tick,
src/erre_sandbox/cognition/cycle.py:606:            agent_state.tick,
src/erre_sandbox/cognition/cycle.py:609:            tick=agent_state.tick,
src/erre_sandbox/cognition/cycle.py:650:                "tick": agent_state.tick + 1,
src/erre_sandbox/cognition/cycle.py:655:            AgentUpdateMsg(tick=new_state.tick, agent_state=new_state),
src/erre_sandbox/cognition/cycle.py:675:            AgentUpdateMsg(tick=new_state.tick, agent_state=new_state),
src/erre_sandbox/cognition/cycle.py:680:                    tick=new_state.tick,
src/erre_sandbox/cognition/cycle.py:695:                    tick=new_state.tick,
src/erre_sandbox/cognition/cycle.py:707:                    tick=new_state.tick,
src/erre_sandbox/cognition/cycle.py:735:                tick=new_state.tick,
src/erre_sandbox/cognition/cycle.py:747:                ReasoningTraceMsg(tick=new_state.tick, trace=trace),
src/erre_sandbox/cognition/cycle.py:1007:      emitted tick is ``agent_state.tick + 1`` — the tick the event will
src/erre_sandbox/cognition/cycle.py:1010:      uses ``agent_state.tick`` because those events are same-tick inputs.
src/erre_sandbox/world/tick.py:279:    # actually steps when ``next_cognition_due <= clock.monotonic()`` — so
src/erre_sandbox/world/tick.py:282:    next_cognition_due: float = 0.0
src/erre_sandbox/world/tick.py:820:                        tick=rt.state.tick,
src/erre_sandbox/world/tick.py:940:            tick_a = rt_a.state.tick
src/erre_sandbox/world/tick.py:941:            tick_b = rt_b.state.tick
src/erre_sandbox/world/tick.py:1003:                            tick=rt.state.tick,
src/erre_sandbox/world/tick.py:1031:                    tick=rt.state.tick,
src/erre_sandbox/world/tick.py:1043:        # ``next_cognition_due`` has elapsed (and which are not in
src/erre_sandbox/world/tick.py:1056:            if rt.next_cognition_due <= now + 1e-6:
src/erre_sandbox/world/tick.py:1064:                self._consume_result(rt, res)
src/erre_sandbox/world/tick.py:1067:                # ``_consume_result`` when a MoveMsg fires) layers an
src/erre_sandbox/world/tick.py:1074:                rt.next_cognition_due = (
src/erre_sandbox/world/tick.py:1117:        cache and invalidate inside ``_consume_result``.
src/erre_sandbox/world/tick.py:1119:        return max((rt.state.tick for rt in self._agents.values()), default=0)
src/erre_sandbox/world/tick.py:1126:                tick=rt.state.tick,
src/erre_sandbox/world/tick.py:1295:    def _consume_result(

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/schemas.py | sed -n '490,535p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   490	    """Short-timescale mental state (tick-level)."""
   491	
   492	    model_config = ConfigDict(extra="forbid")
   493	
   494	    # Russell circumplex (immediate affect).
   495	    valence: _Signed = 0.0
   496	    arousal: _Signed = 0.0
   497	    # Plutchik dominant emotion, if any.
   498	    dominant_emotion: PlutchikDimension | None = None
   499	    # CSDG CharacterState-inspired drives.
   500	    motivation: _Unit = 0.5
   501	    stress: _Unit = 0.0
   502	    curiosity: _Unit = 0.5
   503	    # ERRE-specific cognitive facets.
   504	    shuhari_stage: ShuhariStage = ShuhariStage.SHU
   505	    dmn_activation: _Unit = Field(
   506	        default=0.3,
   507	        description="Default Mode Network activation proxy.",
   508	    )
   509	    active_goals: list[str] = Field(
   510	        default_factory=list,
   511	        max_length=10,
   512	        description=(
   513	            "Free-form short goal strings; promoted to a structured Goal type "
   514	            "in M4 (this is a planned breaking change)."
   515	        ),
   516	    )
   517	    dialog_turn_budget: int = Field(
   518	        default=6,
   519	        ge=0,
   520	        description=(
   521	            "Remaining dialog turns before the agent auto-closes its current "
   522	            "dialog with ``DialogCloseMsg.reason='exhausted'``. Default 6 was "
   523	            "validated empirically in the M5 LLM spike "
   524	            "(.steering/20260420-m5-llm-spike/decisions.md judgement 4). "
   525	            "0 means 'no more turns permitted'."
   526	        ),
   527	    )
   528	
   529	
   530	class ERREMode(BaseModel):
   531	    """The agent's current ERRE mode with its sampling overrides."""
   532	
   533	    model_config = ConfigDict(extra="forbid")
   534	
   535	    name: ERREModeName

exec
/bin/zsh -lc 'rg -n "cognition_period_s|dialog_turn_budget|dwell_time|preferred_zones" personas src tests | head -120' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
personas/nietzsche.yaml:122:preferred_zones:
personas/nietzsche.yaml:137:  cognition_period_s: 7.0
personas/nietzsche.yaml:138:  dwell_time_s: 5.0
personas/rikyu.yaml:123:preferred_zones:
personas/rikyu.yaml:142:  cognition_period_s: 18.0
personas/rikyu.yaml:143:  dwell_time_s: 90.0
personas/kant.yaml:106:preferred_zones:
personas/kant.yaml:121:  cognition_period_s: 14.0
personas/kant.yaml:122:  dwell_time_s: 30.0
tests/test_schemas_m5.py:5:* ``Cognitive.dialog_turn_budget`` default = 6, ``ge=0``
tests/test_schemas_m5.py:47:# asserted because they are *additive* — M5's dialog_turn_budget etc. are
tests/test_schemas_m5.py:51:# ---------- §4 Cognitive.dialog_turn_budget ---------------------------------
tests/test_schemas_m5.py:54:def test_cognitive_dialog_turn_budget_default_is_six() -> None:
tests/test_schemas_m5.py:56:    assert cognitive.dialog_turn_budget == 6
tests/test_schemas_m5.py:59:def test_cognitive_dialog_turn_budget_accepts_zero() -> None:
tests/test_schemas_m5.py:60:    cognitive = Cognitive(dialog_turn_budget=0)
tests/test_schemas_m5.py:61:    assert cognitive.dialog_turn_budget == 0
tests/test_schemas_m5.py:64:def test_cognitive_dialog_turn_budget_rejects_negative() -> None:
tests/test_schemas_m5.py:66:        Cognitive(dialog_turn_budget=-1)
tests/test_cognition/test_belief_promotion.py:42:        preferred_zones=[Zone.PERIPATOS],
tests/test_schemas.py:170:        preferred_zones=[Zone.STUDY, Zone.PERIPATOS],
tests/test_schemas.py:352:        preferred_zones=[Zone.STUDY, Zone.PERIPATOS],
tests/test_persona_kant.py:86:def test_kant_preferred_zones_include_peripatos(kant: PersonaSpec) -> None:
tests/test_persona_kant.py:89:    assert Zone.PERIPATOS in kant.preferred_zones
tests/test_persona_kant.py:90:    assert Zone.STUDY in kant.preferred_zones
src/erre_sandbox/__main__.py:168:        if not persona.preferred_zones:
src/erre_sandbox/__main__.py:170:                f"Persona {pid!r} has no preferred_zones; cannot infer initial_zone",
src/erre_sandbox/__main__.py:173:            AgentSpec(persona_id=pid, initial_zone=persona.preferred_zones[0]),
tests/test_cognition/test_relational.py:66:        preferred_zones=[Zone.PERIPATOS],
tests/test_cognition/test_relational_simulation.py:82:        preferred_zones=[Zone.PERIPATOS],
tests/test_behavior_profile.py:36:    assert bp.cognition_period_s == 10.0
tests/test_behavior_profile.py:37:    assert bp.dwell_time_s == 0.0
tests/test_behavior_profile.py:48:def test_cognition_period_s_clamped() -> None:
tests/test_behavior_profile.py:50:        BehaviorProfile(cognition_period_s=2.0)
tests/test_behavior_profile.py:52:        BehaviorProfile(cognition_period_s=121.0)
tests/test_behavior_profile.py:55:def test_dwell_time_s_clamped() -> None:
tests/test_behavior_profile.py:57:        BehaviorProfile(dwell_time_s=-1.0)
tests/test_behavior_profile.py:59:        BehaviorProfile(dwell_time_s=601.0)
tests/test_behavior_profile.py:77:    assert bp.cognition_period_s == pytest.approx(14.0)
tests/test_behavior_profile.py:78:    assert bp.dwell_time_s == pytest.approx(30.0)
tests/test_behavior_profile.py:85:    assert bp.cognition_period_s == pytest.approx(7.0)
tests/test_behavior_profile.py:86:    assert bp.dwell_time_s == pytest.approx(5.0)
tests/test_behavior_profile.py:93:    assert bp.cognition_period_s == pytest.approx(18.0)
tests/test_behavior_profile.py:94:    assert bp.dwell_time_s == pytest.approx(90.0)
tests/test_cognition/test_zone_bias.py:4:LLM's ``destination_zone`` choice toward the persona's ``preferred_zones``
tests/test_cognition/test_zone_bias.py:36:def test_empty_preferred_zones_is_no_op(
tests/test_cognition/test_zone_bias.py:39:    persona = make_persona_spec(preferred_zones=[])
tests/test_cognition/test_zone_bias.py:54:    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
tests/test_cognition/test_zone_bias.py:63:    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
tests/test_cognition/test_zone_bias.py:72:    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
tests/test_cognition/test_zone_bias.py:81:    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
tests/test_cognition/test_zone_bias.py:94:    persona = make_persona_spec(preferred_zones=["chashitsu", "garden", "study"])
tests/test_cognition/test_zone_bias.py:112:    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
tests/test_cognition/test_zone_bias.py:137:    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
tests/test_cognition/test_zone_bias.py:156:    persona = make_persona_spec(preferred_zones=["chashitsu", "garden"])
tests/test_world/test_apply_affinity_delta.py:57:        preferred_zones=[Zone.PERIPATOS],
src/erre_sandbox/cognition/prompting.py:70:    zones = ", ".join(z.value for z in persona.preferred_zones)
tests/schema_golden/control_envelope.schema.json:170:        "dialog_turn_budget": {
tests/schema_golden/control_envelope.schema.json:227:      "description": "A dialog has ended (M4 foundation).\n\n``reason`` is a closed literal set so the gateway and the scheduler can\ndispatch on it without string matching.\n\nM5 adds ``\"exhausted\"`` to signal that the agent hit its\n:attr:`Cognitive.dialog_turn_budget` cap (distinct from the\nscheduler's ``\"timeout\"``, which is driven by wall-clock).",
tests/schema_golden/control_envelope.schema.json:321:      "description": "A single turn inside an ongoing dialog (M4 foundation).\n\n``speaker_id`` and ``addressee_id`` are both carried so Godot can drive\nthe correct animations (speech bubble / head-turn) without re-deriving\norientation from world state.\n\n``turn_index`` was added in M5 (0.3.0-m5) so consumers can (a) detect\nout-of-order delivery over WebSocket and (b) correlate with\n:attr:`Cognitive.dialog_turn_budget` for exhaustion close-out. The first\nturn of a dialog is ``turn_index=0`` and the value increases by 1 per\nemitted :class:`DialogTurnMsg`.",
tests/schema_golden/control_envelope.schema.json:357:          "description": "Monotonic 0-based index within the dialog. Increments by 1 per emitted turn across both speakers. Paired with ``Cognitive.dialog_turn_budget`` to drive the exhaustion close.",
tests/test_world/test_per_agent_cognition_period.py:9:* **Phase wheel** — three personas with distinct ``cognition_period_s``
tests/test_world/test_per_agent_cognition_period.py:14:* **Dwell** — a persona with ``dwell_time_s > 0`` is suppressed for that
tests/test_world/test_per_agent_cognition_period.py:45:        make_persona_spec(behavior_profile={"cognition_period_s": 14.0}),
tests/test_world/test_per_agent_cognition_period.py:49:        make_persona_spec(behavior_profile={"cognition_period_s": 7.0}),
tests/test_world/test_per_agent_cognition_period.py:53:        make_persona_spec(behavior_profile={"cognition_period_s": 18.0}),
tests/test_world/test_per_agent_cognition_period.py:108:                "cognition_period_s": 10.0,
tests/test_world/test_per_agent_cognition_period.py:109:                "dwell_time_s": 90.0,
tests/schema_golden/persona_spec.schema.json:7:        "cognition_period_s": {
tests/schema_golden/persona_spec.schema.json:15:        "dwell_time_s": {
tests/schema_golden/persona_spec.schema.json:232:    "preferred_zones": {
tests/schema_golden/persona_spec.schema.json:258:    "preferred_zones"
src/erre_sandbox/cognition/cycle.py:269:        # persona's preferred_zones is resampled toward the preferred list.
src/erre_sandbox/cognition/cycle.py:415:        # Slice β: nudge the LLM's destination toward persona preferred_zones
src/erre_sandbox/cognition/cycle.py:418:        # destination is already preferred, when preferred_zones is empty,
src/erre_sandbox/cognition/cycle.py:837:    ``persona.preferred_zones``, pick a uniform replacement from that list
src/erre_sandbox/cognition/cycle.py:860:    if not persona.preferred_zones:
src/erre_sandbox/cognition/cycle.py:864:    if plan.destination_zone in persona.preferred_zones:
src/erre_sandbox/cognition/cycle.py:868:    new_dest = rng.choice(persona.preferred_zones)
tests/schema_golden/agent_state.schema.json:30:        "dialog_turn_budget": {
src/erre_sandbox/world/tick.py:280:    # personas with longer ``cognition_period_s`` skip ticks and personas
src/erre_sandbox/world/tick.py:284:    # ``persona.behavior_profile.dwell_time_s`` seconds suppress cognition
src/erre_sandbox/world/tick.py:338:        cognition_period_s: float | None = None,
src/erre_sandbox/world/tick.py:346:            cognition_period_s
src/erre_sandbox/world/tick.py:347:            if cognition_period_s is not None
src/erre_sandbox/world/tick.py:739:        speaker's ``dialog_turn_budget`` is saturated, or (b) asks the
src/erre_sandbox/world/tick.py:1046:        # the per-agent due time computed from ``cognition_period_s``.
src/erre_sandbox/world/tick.py:1065:                # ``cognition_period_s`` is the *minimum* gap between this
src/erre_sandbox/world/tick.py:1068:                # *upper* override on top: when ``dwell_time_s >
src/erre_sandbox/world/tick.py:1069:                # cognition_period_s`` (e.g. Rikyū's 90 s dwell vs 18 s
src/erre_sandbox/world/tick.py:1070:                # period) dwell wins, when ``dwell_time_s <
src/erre_sandbox/world/tick.py:1071:                # cognition_period_s`` (e.g. Nietzsche's 5 s dwell vs 7 s
src/erre_sandbox/world/tick.py:1075:                    now + rt.persona.behavior_profile.cognition_period_s
src/erre_sandbox/world/tick.py:1143:           ``len(transcript) >= speaker.cognitive.dialog_turn_budget``.
src/erre_sandbox/world/tick.py:1244:            budget = speaker_rt.state.cognitive.dialog_turn_budget
src/erre_sandbox/world/tick.py:1334:                # suppressed for ``dwell_time_s`` before the phase wheel
src/erre_sandbox/world/tick.py:1335:                # resumes. dwell_time_s == 0.0 (the default) makes this a
src/erre_sandbox/world/tick.py:1337:                dwell = rt.persona.behavior_profile.dwell_time_s
tests/test_world/test_apply_belief_promotion.py:50:        preferred_zones=[Zone.PERIPATOS],
tests/test_world/conftest.py:116:        cognition_period_s=10.0,
src/erre_sandbox/evidence/scaling_metrics.py:64:Mirrors the ``dialog_turn_budget`` cap observed in M7-δ run logs — each
src/erre_sandbox/schemas.py:57:(:attr:`Cognitive.dialog_turn_budget`, :attr:`DialogTurnMsg.turn_index`) and
src/erre_sandbox/schemas.py:365:    cognition_period_s: float = Field(
src/erre_sandbox/schemas.py:376:    dwell_time_s: float = Field(
src/erre_sandbox/schemas.py:411:    preferred_zones: list[Zone]
src/erre_sandbox/schemas.py:517:    dialog_turn_budget: int = Field(
src/erre_sandbox/schemas.py:1157:    :attr:`Cognitive.dialog_turn_budget` for exhaustion close-out. The first
src/erre_sandbox/schemas.py:1173:            "``Cognitive.dialog_turn_budget`` to drive the exhaustion close."
src/erre_sandbox/schemas.py:1286:    :attr:`Cognitive.dialog_turn_budget` cap (distinct from the
tests/conftest.py:115:            "preferred_zones": ["study", "peripatos"],
tests/test_integration/test_dialog_turn.py:133:        preferred_zones=["chashitsu", "garden"],
tests/test_integration/test_dialog_turn.py:196:#     when len(transcript) >= dialog_turn_budget, using scheduler.transcript_of
tests/test_integration/test_dialog_turn.py:236:    budget = kant_state.cognitive.dialog_turn_budget
tests/test_integration/test_dialog_eval_natural_mode.py:11:で 80% は LLM zone を honor するため preferred_zones override では救えない。
tests/test_integration/test_dialog_orchestration_wiring.py:6:* budget boundary (`turn_index >= dialog_turn_budget` => exhausted close)
tests/test_integration/test_dialog_orchestration_wiring.py:126:        cognitive={"dialog_turn_budget": budget},
tests/test_integration/test_dialog_orchestration_wiring.py:132:        cognitive={"dialog_turn_budget": budget},
tests/test_personas/test_load_all.py:112:def test_preferred_zones_differ_from_kant(personas: dict[str, PersonaSpec]) -> None:
tests/test_personas/test_load_all.py:113:    """At least one preferred_zones set must disagree with Kant's.
tests/test_personas/test_load_all.py:118:    kant_zones = set(personas["kant"].preferred_zones)

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/world/tick.py | sed -n '1288,1365p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
  1288	        return await self._cycle.step(
  1289	            rt.state,
  1290	            rt.persona,
  1291	            obs,
  1292	            tick_seconds=self._cognition_period,
  1293	        )
  1294	
  1295	    def _consume_result(
  1296	        self,
  1297	        rt: AgentRuntime,
  1298	        res: CycleResult | BaseException,
  1299	    ) -> None:
  1300	        if isinstance(res, BaseException):
  1301	            logger.exception(
  1302	                "agent %s step raised",
  1303	                rt.agent_id,
  1304	                exc_info=res,
  1305	            )
  1306	            return
  1307	        rt.state = res.agent_state
  1308	        rt.kinematics.position = res.agent_state.position
  1309	        # M6-A-2b: observations detected post-LLM (stress crossings) are
  1310	        # surfaced one tick late — append them to ``pending`` so the next
  1311	        # cognition tick sees the signal. Empty for agents whose stress
  1312	        # stayed on one side of the mid-band, which is the common case.
  1313	        if res.follow_up_observations:
  1314	            rt.pending.extend(res.follow_up_observations)
  1315	        for env in res.envelopes:
  1316	            if isinstance(env, MoveMsg):
  1317	                # Resolve a "zone-only" MoveMsg (coords unchanged from current
  1318	                # position, only zone field differs) to the target zone's spawn
  1319	                # point. CognitionCycle._build_envelopes emits this shape when
  1320	                # the LLM returns a destination_zone, relying on the world
  1321	                # layer to map semantic zone -> physical coordinates. Without
  1322	                # this resolution, step_kinematics would see dest == position,
  1323	                # mark "arrived immediately", and never cross a zone boundary
  1324	                # -> pending observations stay empty -> episodic_memory never
  1325	                # populates (GAP-1 blocker for MASTER-PLAN §4.4 #3).
  1326	                tgt = env.target
  1327	                if locate_zone(tgt.x, tgt.y, tgt.z) is not tgt.zone:
  1328	                    resolved = default_spawn(tgt.zone).model_copy(
  1329	                        update={"yaw": tgt.yaw, "pitch": tgt.pitch},
  1330	                    )
  1331	                    env = env.model_copy(update={"target": resolved})  # noqa: PLW2901 — intentional re-bind to propagate the zone-resolved target to both apply_move_command and the downstream queue
  1332	                apply_move_command(rt.kinematics, env)
  1333	                # M7ζ-3: arm seiza-style dwell so the persona's cognition is
  1334	                # suppressed for ``dwell_time_s`` before the phase wheel
  1335	                # resumes. dwell_time_s == 0.0 (the default) makes this a
  1336	                # no-op, so personas without a dwell tuning are unaffected.
  1337	                dwell = rt.persona.behavior_profile.dwell_time_s
  1338	                if dwell > 0.0:
  1339	                    rt.dwell_until = self._clock.monotonic() + dwell
  1340	            self._envelopes.put_nowait(env)
  1341	
  1342	    # ----- Scheduling helper -----
  1343	
  1344	    def _schedule(
  1345	        self,
  1346	        due_at: float,
  1347	        period: float,
  1348	        handler: Callable[[], Awaitable[None]],
  1349	        *,
  1350	        name: str,
  1351	    ) -> None:
  1352	        self._seq += 1
  1353	        heapq.heappush(
  1354	            self._events,
  1355	            ScheduledEvent(
  1356	                due_at=due_at,
  1357	                seq=self._seq,
  1358	                period=period,
  1359	                handler=handler,
  1360	                name=name,
  1361	            ),
  1362	        )

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/cognition/cycle.py | sed -n '420,465p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   420	        # envelope-level contract is unchanged in the common case.
   421	        plan = _bias_target_zone(
   422	            plan,
   423	            persona,
   424	            self._bias_rng,
   425	            self._zone_bias_p,
   426	            agent_id=agent_state.agent_id,
   427	            tick=agent_state.tick,
   428	            bias_sink=self._bias_sink,
   429	        )
   430	
   431	        # Step 8: compose Cognitive via pure LLM delta.
   432	        new_cognitive = apply_llm_delta(
   433	            agent_state.cognitive,
   434	            plan,
   435	            config=self._update_config,
   436	            rng=self._rng,
   437	        )
   438	
   439	        # Step 8.5 (M6-A-2b): detect stress threshold crossings. Unlike the
   440	        # fatigue / hunger crossings in Step 2.25, stress lives in Cognitive
   441	        # which is only known AFTER the LLM call, so the event arrives one
   442	        # tick late by design. The runtime consumes
   443	        # ``CycleResult.follow_up_observations`` and appends them to the
   444	        # agent's pending buffer so the next tick's prompt sees the signal.
   445	        stress_events = _detect_stress_crossing(
   446	            previous=agent_state.cognitive,
   447	            current=new_cognitive,
   448	            agent_id=agent_state.agent_id,
   449	            tick=agent_state.tick + 1,
   450	        )
   451	
   452	        # Step 9: assemble the post-tick state + envelopes.
   453	        new_state = agent_state.model_copy(
   454	            update={
   455	                "tick": agent_state.tick + 1,
   456	                "physical": new_physical,
   457	                "cognitive": new_cognitive,
   458	            },
   459	        )
   460	        envelopes = self._build_envelopes(
   461	            new_state,
   462	            plan,
   463	            persona=persona,
   464	            observations=observations,
   465	            memories=memories,

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/schemas.py | sed -n '350,385p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba tests/test_world/test_per_agent_cognition_period.py | sed -n '1,160p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   350	    ``SCHEMA_VERSION`` is not bumped when fields are added here.
   351	    """
   352	
   353	    model_config = ConfigDict(extra="forbid")
   354	
   355	    movement_speed_factor: float = Field(
   356	        default=1.0,
   357	        ge=0.3,
   358	        le=2.5,
   359	        description=(
   360	            "Multiplier applied to ``CognitionCycle.DEFAULT_DESTINATION_SPEED`` "
   361	            "(1.3 m/s) when emitting MoveMsg. Yields the persona's distinctive "
   362	            "gait rhythm in the live ``MoveMsg.speed`` histogram."
   363	        ),
   364	    )
   365	    cognition_period_s: float = Field(
   366	        default=10.0,
   367	        ge=3.0,
   368	        le=120.0,
   369	        description=(
   370	            "Base period of this agent's cognition tick. The 10 s global "
   371	            "scheduler in ``world/tick.py`` runs unchanged, but each agent's "
   372	            "``next_cognition_due`` is advanced by this value (phase wheel) "
   373	            "so Nietzsche-like bursts and Rikyū-like slow cadences emerge."
   374	        ),
   375	    )
   376	    dwell_time_s: float = Field(
   377	        default=0.0,
   378	        ge=0.0,
   379	        le=600.0,
   380	        description=(
   381	            "Extra delay added once after a MoveMsg fires (seiza-like dwell). "
   382	            "Suppresses cognition ticks for this duration before the phase "
   383	            "wheel resumes — Rikyū's ≥20 min seiza is the headline use case."
   384	        ),
   385	    )

 succeeded in 0ms:
     1	"""M7ζ-3: phase-wheel cognition cadence + post-MoveMsg dwell.
     2	
     3	The global cognition heap event still fires at ``_cognition_period`` (10 s),
     4	but :meth:`WorldRuntime._on_cognition_tick` now selects only agents whose
     5	``next_cognition_due`` has elapsed and which are not in seiza dwell. This
     6	file verifies that two distinct mechanisms produce visibly different step
     7	counts in a 60 s window:
     8	
     9	* **Phase wheel** — three personas with distinct ``cognition_period_s``
    10	  step at distinct cadences. The 10 s global grid rounds finer periods up
    11	  to grid multiples, so 14 s and 18 s tie at the 20 s effective rate while
    12	  7 s rides every global tick. Live divergence between Kant (14 s) and
    13	  Rikyū (18 s) comes from the second mechanism below.
    14	* **Dwell** — a persona with ``dwell_time_s > 0`` is suppressed for that
    15	  duration after firing a MoveMsg. Rikyū's 90 s dwell after one move
    16	  dampens the next several global ticks, which is what gives Rikyū the
    17	  visible "long seiza" cadence in live observation.
    18	"""
    19	
    20	from __future__ import annotations
    21	
    22	import asyncio
    23	from collections import Counter
    24	from typing import TYPE_CHECKING, Any
    25	
    26	from erre_sandbox.cognition import CycleResult
    27	from erre_sandbox.schemas import AgentUpdateMsg, MoveMsg, Position, Zone
    28	
    29	if TYPE_CHECKING:
    30	    from .conftest import MockCycleCall, RuntimeHarness
    31	
    32	
    33	async def _pump(times: int = 10) -> None:
    34	    for _ in range(times):
    35	        await asyncio.sleep(0)
    36	
    37	
    38	async def test_phase_wheel_diverges_per_persona_period(
    39	    world_harness: RuntimeHarness,
    40	    make_agent_state: Any,
    41	    make_persona_spec: Any,
    42	) -> None:
    43	    world_harness.runtime.register_agent(
    44	        make_agent_state(agent_id="a_kant"),
    45	        make_persona_spec(behavior_profile={"cognition_period_s": 14.0}),
    46	    )
    47	    world_harness.runtime.register_agent(
    48	        make_agent_state(agent_id="a_niet"),
    49	        make_persona_spec(behavior_profile={"cognition_period_s": 7.0}),
    50	    )
    51	    world_harness.runtime.register_agent(
    52	        make_agent_state(agent_id="a_rikyu"),
    53	        make_persona_spec(behavior_profile={"cognition_period_s": 18.0}),
    54	    )
    55	
    56	    task = asyncio.create_task(world_harness.runtime.run())
    57	    await _pump()
    58	    # Six global cognition ticks at 10 s cadence (60 s wall-clock).
    59	    for _ in range(6):
    60	        world_harness.clock.advance(10.0)
    61	        await _pump(800)
    62	
    63	    counts = Counter(c.agent_state.agent_id for c in world_harness.cycle.calls)
    64	
    65	    # Nietzsche (7 s, finer than the 10 s global grid) must outpace both
    66	    # peers — this is the headline "burst" cadence.
    67	    assert counts["a_niet"] > counts["a_kant"]
    68	    assert counts["a_niet"] > counts["a_rikyu"]
    69	    # Kant (14 s) and Rikyū (18 s) both round up to 20 s on the 10 s grid,
    70	    # so they tie at this resolution; the dwell test below differentiates
    71	    # them. Both must still register at least one step in the window.
    72	    assert counts["a_kant"] >= 1
    73	    assert counts["a_rikyu"] >= 1
    74	
    75	    world_harness.runtime.stop()
    76	    world_harness.clock.advance(1.0)
    77	    await _pump()
    78	    await task
    79	
    80	
    81	async def test_dwell_suppresses_cognition_after_move(
    82	    world_harness: RuntimeHarness,
    83	    make_agent_state: Any,
    84	    make_persona_spec: Any,
    85	) -> None:
    86	    async def respond_with_move(call: MockCycleCall) -> object:
    87	        return CycleResult(
    88	            agent_state=call.agent_state,
    89	            envelopes=[
    90	                AgentUpdateMsg(
    91	                    tick=call.agent_state.tick,
    92	                    agent_state=call.agent_state,
    93	                ),
    94	                MoveMsg(
    95	                    tick=call.agent_state.tick,
    96	                    agent_id=call.agent_state.agent_id,
    97	                    target=Position(x=0.0, y=0.0, z=0.0, zone=Zone.STUDY),
    98	                    speed=1.0,
    99	                ),
   100	            ],
   101	        )
   102	
   103	    world_harness.cycle.set_responder(respond_with_move)
   104	    world_harness.runtime.register_agent(
   105	        make_agent_state(agent_id="a_rikyu"),
   106	        make_persona_spec(
   107	            behavior_profile={
   108	                "cognition_period_s": 10.0,
   109	                "dwell_time_s": 90.0,
   110	            },
   111	        ),
   112	    )
   113	
   114	    task = asyncio.create_task(world_harness.runtime.run())
   115	    await _pump()
   116	    # Six global cognition ticks at 10 s cadence (60 s wall-clock). The
   117	    # first one fires the MoveMsg and arms a 90 s dwell, so the remaining
   118	    # five must be suppressed.
   119	    for _ in range(6):
   120	        world_harness.clock.advance(10.0)
   121	        await _pump(800)
   122	
   123	    assert len(world_harness.cycle.calls) == 1
   124	
   125	    world_harness.runtime.stop()
   126	    world_harness.clock.advance(1.0)
   127	    await _pump()
   128	    await task

exec
/bin/zsh -lc 'rg -n "''^def test_" tests/test_integration/test_dialog_eval_natural_mode.py tests/test_integration/test_dialog_golden_baseline_mode.py tests/test_cli/test_eval_run_golden.py' in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc 'rg -n "COOLDOWN_TICKS|eval_natural_mode|cooldown" tests/test_integration/test_dialog_eval_natural_mode.py tests/test_integration/test_dialog.py tests/test_integration/test_dialog_golden_baseline_mode.py' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
tests/test_integration/test_dialog_eval_natural_mode.py:79:def test_default_constructor_keeps_eval_natural_mode_false() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:85:def test_eval_natural_mode_is_independent_of_golden_baseline_mode() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:100:def test_combining_both_modes_is_rejected() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:121:def test_default_mode_admission_stops_when_agents_scatter() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:172:def test_eval_natural_mode_admits_pairs_across_different_zones() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:188:def test_eval_natural_mode_admits_two_study_agents() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:210:def test_eval_natural_mode_preserves_self_dialog_reject() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:217:def test_eval_natural_mode_preserves_double_open_reject() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:226:def test_eval_natural_mode_preserves_cooldown_via_tick() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:255:def test_eval_natural_mode_preserves_probability_gate() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:269:def test_eval_natural_mode_preserves_timeout_close() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:295:def test_eval_natural_mode_sustains_admission_after_initial_burst() -> None:
tests/test_cli/test_eval_run_golden.py:45:def test_focal_turn_count_handles_odd_and_even() -> None:
tests/test_cli/test_eval_run_golden.py:53:def test_stratified_slice_preserves_category_proportions() -> None:
tests/test_cli/test_eval_run_golden.py:82:def test_stratified_slice_returns_full_battery_when_target_exceeds_capacity() -> None:
tests/test_cli/test_eval_run_golden.py:89:def test_stratified_slice_zero_target_returns_empty() -> None:
tests/test_cli/test_eval_run_golden.py:101:def test_resolve_output_paths_refuses_existing_without_overwrite(
tests/test_cli/test_eval_run_golden.py:110:def test_resolve_output_paths_returns_temp_with_overwrite(
tests/test_cli/test_eval_run_golden.py:120:def test_resolve_output_paths_clears_stale_temp_sibling(tmp_path: Path) -> None:
tests/test_cli/test_eval_run_golden.py:275:def test_arg_parser_has_required_flags() -> None:
tests/test_cli/test_eval_run_golden.py:299:def test_arg_parser_rejects_unknown_persona() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:40:def test_default_constructor_keeps_mode_false() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:51:def test_mode_true_admits_study_zone() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:63:def test_mode_false_still_rejects_study_zone() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:75:def test_mode_true_bypasses_cooldown_on_same_pair() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:96:def test_mode_false_still_rejects_during_cooldown() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:117:def test_mode_true_suppresses_timeout_close_in_tick() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:136:def test_mode_false_still_auto_closes_on_timeout() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:151:def test_mode_true_still_rejects_self_pair() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:161:def test_mode_true_still_rejects_already_open_pair() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:178:def test_runtime_toggle_enables_then_disables_bypass() -> None:

 succeeded in 0ms:
tests/test_integration/test_dialog_eval_natural_mode.py:1:"""Tests for ``InMemoryDialogScheduler.eval_natural_mode`` flag.
tests/test_integration/test_dialog_eval_natural_mode.py:13:修正: ``eval_natural_mode: bool = False`` flag を scheduler に追加し、True
tests/test_integration/test_dialog_eval_natural_mode.py:15:cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
tests/test_integration/test_dialog_eval_natural_mode.py:75:# Default constructor: eval_natural_mode is False (M4-frozen behaviour)
tests/test_integration/test_dialog_eval_natural_mode.py:79:def test_default_constructor_keeps_eval_natural_mode_false() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:82:    assert scheduler.eval_natural_mode is False
tests/test_integration/test_dialog_eval_natural_mode.py:85:def test_eval_natural_mode_is_independent_of_golden_baseline_mode() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:89:        envelope_sink=sink, eval_natural_mode=True, golden_baseline_mode=False
tests/test_integration/test_dialog_eval_natural_mode.py:92:        envelope_sink=sink, eval_natural_mode=False, golden_baseline_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:94:    assert scheduler_a.eval_natural_mode is True
tests/test_integration/test_dialog_eval_natural_mode.py:96:    assert scheduler_b.eval_natural_mode is False
tests/test_integration/test_dialog_eval_natural_mode.py:103:    ``golden_baseline_mode`` override the cooldown / timeout invariant
tests/test_integration/test_dialog_eval_natural_mode.py:104:    that ``eval_natural_mode`` advertises — surface the inconsistency at
tests/test_integration/test_dialog_eval_natural_mode.py:108:    with pytest.raises(ValueError, match="golden_baseline_mode and eval_natural_mode"):
tests/test_integration/test_dialog_eval_natural_mode.py:112:            eval_natural_mode=True,
tests/test_integration/test_dialog_eval_natural_mode.py:132:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=False
tests/test_integration/test_dialog_eval_natural_mode.py:151:    # Advance world tick past COOLDOWN_TICKS so cooldown is no longer the gate.
tests/test_integration/test_dialog_eval_natural_mode.py:152:    far_tick = scheduler.COOLDOWN_TICKS + 5
tests/test_integration/test_dialog_eval_natural_mode.py:163:        "pairs, so even after cooldown expires no admit fires"
tests/test_integration/test_dialog_eval_natural_mode.py:168:# Fix: eval_natural_mode=True admits any pair regardless of zone
tests/test_integration/test_dialog_eval_natural_mode.py:172:def test_eval_natural_mode_admits_pairs_across_different_zones() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:175:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:188:def test_eval_natural_mode_admits_two_study_agents() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:193:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:206:# Invariants preserved in eval_natural_mode
tests/test_integration/test_dialog_eval_natural_mode.py:210:def test_eval_natural_mode_preserves_self_dialog_reject() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:212:    scheduler = InMemoryDialogScheduler(envelope_sink=sink, eval_natural_mode=True)
tests/test_integration/test_dialog_eval_natural_mode.py:217:def test_eval_natural_mode_preserves_double_open_reject() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:219:    scheduler = InMemoryDialogScheduler(envelope_sink=sink, eval_natural_mode=True)
tests/test_integration/test_dialog_eval_natural_mode.py:226:def test_eval_natural_mode_preserves_cooldown_via_tick() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:228:    the same pair within ``COOLDOWN_TICKS`` even with the zone bypass."""
tests/test_integration/test_dialog_eval_natural_mode.py:231:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:242:    # Within cooldown window — no re-admit.
tests/test_integration/test_dialog_eval_natural_mode.py:243:    for w in range(1, scheduler.COOLDOWN_TICKS):
tests/test_integration/test_dialog_eval_natural_mode.py:246:            f"cooldown breached at tick {w}: same pair re-admitted within "
tests/test_integration/test_dialog_eval_natural_mode.py:247:            f"{scheduler.COOLDOWN_TICKS} ticks"
tests/test_integration/test_dialog_eval_natural_mode.py:250:    # Past cooldown — admit again.
tests/test_integration/test_dialog_eval_natural_mode.py:251:    scheduler.tick(world_tick=scheduler.COOLDOWN_TICKS, agents=agents)
tests/test_integration/test_dialog_eval_natural_mode.py:255:def test_eval_natural_mode_preserves_probability_gate() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:259:        envelope_sink=sink, rng=_never_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:269:def test_eval_natural_mode_preserves_timeout_close() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:273:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:295:def test_eval_natural_mode_sustains_admission_after_initial_burst() -> None:
tests/test_integration/test_dialog_eval_natural_mode.py:299:    Counter-example to the bug repro above: with eval_natural_mode=True,
tests/test_integration/test_dialog_eval_natural_mode.py:300:    even after agents scatter, admit fires resume after cooldown.
tests/test_integration/test_dialog_eval_natural_mode.py:304:        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
tests/test_integration/test_dialog_eval_natural_mode.py:318:        # Stamp activity at tick 6 so close anchors cooldown there.
tests/test_integration/test_dialog_eval_natural_mode.py:332:    # Now agents scatter. Drive ticks past cooldown and check admit resumes.
tests/test_integration/test_dialog_eval_natural_mode.py:338:    far_tick = 6 + scheduler.COOLDOWN_TICKS  # 36
tests/test_integration/test_dialog_eval_natural_mode.py:341:        "after cooldown expires, all three pairs should re-admit even "
tests/test_integration/test_dialog.py:118:def test_schedule_initiate_rejects_during_cooldown() -> None:
tests/test_integration/test_dialog.py:131:        tick=InMemoryDialogScheduler.COOLDOWN_TICKS - 1,
tests/test_integration/test_dialog.py:136:def test_schedule_initiate_admits_after_cooldown_elapsed() -> None:
tests/test_integration/test_dialog.py:147:        tick=InMemoryDialogScheduler.COOLDOWN_TICKS + 1,
tests/test_integration/test_dialog.py:283:def test_tick_respects_cooldown_after_auto_close() -> None:
tests/test_integration/test_dialog.py:294:    # Immediately tick again — cooldown must suppress auto re-firing even
tests/test_integration/test_dialog.py:362:    cooldown = InMemoryDialogScheduler.COOLDOWN_TICKS
tests/test_integration/test_dialog.py:368:            tick=explicit_tick + cooldown - 1,
tests/test_integration/test_dialog.py:377:            tick=explicit_tick + cooldown + 1,
tests/test_integration/test_dialog_golden_baseline_mode.py:5:during the 200-stimulus phase to bypass cooldown / timeout / zone
tests/test_integration/test_dialog_golden_baseline_mode.py:71:# Mode True — cooldown bypass (rapid stimulus loop on same pair)
tests/test_integration/test_dialog_golden_baseline_mode.py:75:def test_mode_true_bypasses_cooldown_on_same_pair() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:86:    # Re-open immediately at tick=1 (well within the 30-tick cooldown window).
tests/test_integration/test_dialog_golden_baseline_mode.py:96:def test_mode_false_still_rejects_during_cooldown() -> None:
tests/test_integration/test_dialog_golden_baseline_mode.py:103:    inside_cooldown = scheduler.schedule_initiate(
tests/test_integration/test_dialog_golden_baseline_mode.py:107:        tick=InMemoryDialogScheduler.COOLDOWN_TICKS - 1,
tests/test_integration/test_dialog_golden_baseline_mode.py:109:    assert inside_cooldown is None
tests/test_integration/test_dialog_golden_baseline_mode.py:200:        tick=InMemoryDialogScheduler.COOLDOWN_TICKS + 1,
tests/test_integration/test_dialog_golden_baseline_mode.py:203:    # And cooldown applies again — at tick just past close, PERIPATOS within
tests/test_integration/test_dialog_golden_baseline_mode.py:204:    # cooldown also rejected.
tests/test_integration/test_dialog_golden_baseline_mode.py:205:    inside_cooldown = scheduler.schedule_initiate(
tests/test_integration/test_dialog_golden_baseline_mode.py:211:    assert inside_cooldown is None

codex
The v2 design file appears to have changed while I’m reviewing it: it now contains an empirical correction about the existing `90.0` minute default that was not in my first read. I’m re-reading the current version before finalizing findings so I don’t report stale issues.
exec
/bin/zsh -lc 'wc -l .steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md' in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba .steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md | sed -n '180,330p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     323 .steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md

 succeeded in 0ms:
   180	| ι | wall 12h × overnight × 多 run で運用コスト許容外 |
   181	
   182	### 3.3 採用案の修正範囲
   183	
   184	#### 3.3.1 `src/erre_sandbox/integration/dialog.py`
   185	
   186	```python
   187	class InMemoryDialogScheduler:
   188	    COOLDOWN_TICKS: ClassVar[int] = 30
   189	    """Live multi-agent run の cooldown (live cognition_period での
   190	    natural cadence 維持)。"""
   191	
   192	    COOLDOWN_TICKS_EVAL: ClassVar[int] = 5
   193	    """eval_natural_mode=True 時の reduced cooldown。実測 cognition_period
   194	    ≈ 120 s/tick (qwen3:8b Q4_K_M on RTX 5060 Ti) で 60 min wall = 30 tick
   195	    のうち 5-6 cycle 完走を保証する empirical 値。re-open 条件: 推論
   196	    backend が変わって cognition_period が ±50% 以上変動した場合は
   197	    本値を再評価。"""
   198	
   199	    def _effective_cooldown(self) -> int:
   200	        """eval_natural_mode flag に応じた cooldown ticks を返す純関数。"""
   201	        return self.COOLDOWN_TICKS_EVAL if self.eval_natural_mode else self.COOLDOWN_TICKS
   202	```
   203	
   204	`schedule_initiate` の cooldown check と `tick()` 内の cooldown check 両方を
   205	`self._effective_cooldown()` 経由に統一。`golden_baseline_mode=True` の cooldown bypass
   206	は既存通り (両 flag 同時 True は v1 で reject 済)。
   207	
   208	#### 3.3.2 `src/erre_sandbox/cli/eval_run_golden.py`
   209	
   210	**重要 empirical 訂正**: 現状の `_DEFAULT_WALL_TIMEOUT_MIN: Final[float] = 90.0`
   211	であり、G-GEAR Phase A の 10 min wall は operator が手動で sanity 用に短縮した
   212	値。default 90 min は §2.1 の minimum 60 min を既に満たしているため、**β は
   213	コード側 default 変更不要**。
   214	
   215	ただし §5 リスク 2 の realistic estimate (variance 込みで focal=16-30) に対し
   216	margin を強化するため、本 v2 では **default を 90 → 120 min に拡張** (Codex Q3
   217	で精査):
   218	
   219	```python
   220	# 既存 (line 122)
   221	_DEFAULT_WALL_TIMEOUT_MIN: Final[float] = 90.0
   222	
   223	# v2 提案
   224	_DEFAULT_WALL_TIMEOUT_MIN: Final[float] = 120.0
   225	```
   226	
   227	stimulus 側 default は影響なし (capture_stimulus は wall budget 持たない、
   228	turn_count 駆動)。`--wall-timeout-min N` で操作者 override 可能を維持。
   229	
   230	**alternative**: default 90 min を維持し、G-GEAR rerun 操作者に明示的に
   231	`--wall-timeout-min 120` を渡してもらう運用解。コード変更ゼロでシンプルだが、
   232	将来の sanity test で再び短い wall が選ばれて Phase A guard `focal<25` を踏む
   233	risk が残る。コード側 default を上げる方が defensive。
   234	
   235	#### 3.3.3 `tests/test_integration/test_dialog_eval_natural_mode.py` 拡張
   236	
   237	既存 12 ケースに以下を **追加** (default 値の意味的不変は v1 で確立済、本 v2 は
   238	eval-specific reduced cooldown の new contract を追加検証):
   239	
   240	1. **`test_eval_mode_uses_reduced_cooldown`**: eval_natural_mode=True で同一 pair が
   241	   tick 5 後に再 admit 可能、tick 4 では reject されることを assert
   242	2. **`test_live_mode_cooldown_unchanged`**: eval_natural_mode=False (default) で
   243	   COOLDOWN_TICKS=30 が active、tick 29 で reject / tick 30 で admit
   244	3. **`test_effective_cooldown_returns_correct_value`**: `_effective_cooldown()`
   245	   helper の純関数 contract (eval=5 / live=30)
   246	4. **`test_class_constants_unchanged`**: `COOLDOWN_TICKS == 30` /
   247	   `COOLDOWN_TICKS_EVAL == 5` の sentinel test (将来の silent な定数変更を防ぐ)
   248	
   249	CLI test (`tests/test_cli/test_eval_run_golden.py`) に `--wall-timeout-min` default が
   250	60 min for natural を assert する 1 ケース追加 (既存 12 mock test の隣)。
   251	
   252	### 3.4 ME-8 ADR §invariant の partial-update
   253	
   254	v1 で「Cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
   255	invariant は両 mode で active のまま」と書いた箇所を以下に Edit:
   256	
   257	> **Cooldown (eval-mode 別 threshold = `COOLDOWN_TICKS_EVAL=5`、live は
   258	> `COOLDOWN_TICKS=30`)** / probability / timeout / 自己 dialog reject /
   259	> 二重 open reject の invariant は両 mode で active のまま — eval natural cadence
   260	> は維持、proximity 制約のみ削除 + cooldown threshold を eval mode で reduce。
   261	
   262	**追加 §re-open 条件 (本 v2 起草時 = 三度目)**:
   263	
   264	- **fix v2 後も focal<25 で stop** → 別 dominant gate (prob 0.25 / 推論 deadlock 等) を再特定
   265	- **推論 backend が変わって cognition_period が 60s 以下 / 240s 以上に変動** →
   266	  COOLDOWN_TICKS_EVAL=5 の妥当性を再評価 (60s なら cooldown=10 候補、240s なら cooldown=3
   267	  候補、empirical 再採取で確定)
   268	
   269	### 3.5 design v1 §採用案との差分明示
   270	
   271	design v1 §6.1 の "Cooldown / probability / timeout は active のまま (natural cadence 保持)"
   272	を design v2 §3.3 で **明示的に書き換え**:
   273	
   274	> v1 では cooldown_ticks=30 を eval mode でも flat に保持していたが、empirical で
   275	> dominant gate と判明。v2 では eval mode 限定で COOLDOWN_TICKS_EVAL=5 に reduce
   276	> (live mode は影響無し)。Cooldown 概念自体は両 mode で保持される (= ピンポン admit
   277	> 防止の semantics は eval mode でも生きている)。
   278	
   279	## 4. 受け入れ条件 (本 Mac セッション完了時)
   280	
   281	- [x] design v2 起草 (本ドキュメント、5 + 3 案比較 + 採用)
   282	- [ ] codex-review-prompt-natural-gating-v2.md 起草 (本セッション)
   283	- [ ] Codex `gpt-5.5 xhigh` independent review verbatim 保存 (Verdict: ship 想定)
   284	- [ ] HIGH/MEDIUM 反映後に decisions.md ME-8 二度目の partial-update
   285	- [ ] dialog.py + eval_run_golden.py 修正 + 4 unit test 追加 (12→16)
   286	- [ ] 既存 1248 PASS 維持 (full suite)
   287	- [ ] g-gear-p3a-rerun-prompt-v2.md 起草 (Phase A 期待値の桁再校正)
   288	- [ ] PR 作成 (PR #131 リンク参照、Codex review verdict と HIGH 反映状況明記)
   289	
   290	## 5. リスクと反証
   291	
   292	- **リスク 1**: 60 min wall × cooldown=5 で focal=30 達成は **理論計算**、empirical で
   293	  AUTO_FIRE_PROB_PER_TICK=0.25 の variance により 5 cycle 完走しない可能性。
   294	  - 反証実験: G-GEAR 再々採取で focal<25 が再発した場合、ME-8 §re-open 条件 1 項目目で
   295	    別 dominant gate (推論 deadlock 等) を再特定。
   296	- **リスク 2**: eval mode reduced cooldown が dialog_turn_budget=6 と組合わさって
   297	  burst 過多 (5 ticks 直前 close → 5 ticks 後即再 admit → 11 ticks per cycle で 6 cycle/30
   298	  ticks) で natural cadence が崩れる可能性。
   299	  - 反証: 1 cycle = 6 ticks (turn) + 5 ticks (cooldown) = 11 ticks/cycle、cognition_period
   300	    120 s/tick で 22 min/cycle、60 min wall で約 2.7 cycle = 16 utterance/cell。
   301	    G-GEAR 計算 (5 cycle = 90 utterance) は **prob 0.25 を込めていない**ため過大評価。
   302	    realistic estimate = 16-30 utterance/cell、focal kant per cell = 8-15。
   303	  - **判断**: v2 では `--wall-timeout-min default=60` を採用、focal target 30 達成が
   304	    margin に欠ける場合は default を 90 / 120 min に上げる調整余地を残す。
   305	    G-GEAR 再採取で実測値を確認してから default 確定 (現 default=60 は最低保証)。
   306	
   307	## 6. Codex review
   308	
   309	本 design v2 + 実装 diff sketch 確定後、`gpt-5.5 xhigh` independent review に回す。
   310	`codex-review-prompt-natural-gating-v2.md` / `codex-review-natural-gating-v2.md` を
   311	verbatim 保存。HIGH は実装前に反映、MEDIUM は decisions.md ME-8 に取り込み。
   312	
   313	特に Codex に問いたい論点:
   314	- Q1: §2.4 ι (β+δ) を「wall 爆発」で棄却したが、stimulus と natural を別 SOP で運用
   315	  するなら ι が ME-8 invariant 後退ゼロで本来は最小侵襲では？
   316	- Q2: §3.3.1 で `COOLDOWN_TICKS_EVAL=5` を hardcoded class const にしたが、CLI
   317	  `--cooldown-ticks-eval N` で override 可能にすべきか？
   318	- Q3: §5 リスク 2 の cycle 計算で AUTO_FIRE_PROB=0.25 を考慮すると wall=60 min default は
   319	  margin が薄い。default=90 min に変更すべきか？
   320	- Q4: ME-8 §invariant 文言の "active with reduced threshold" 表現は v1 contract に対し
   321	  silent な後退ではないか？(明示的な ADR re-open + 文言再定義で良いか)
   322	- Q5: §3.3.3 で追加 4 test のうち、`test_class_constants_unchanged` の sentinel test は
   323	  本当に必要か (over-defensive ではないか)？

exec
/bin/zsh -lc 'git diff -- .steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
exec
/bin/zsh -lc 'git status --short' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
?? .steering/20260430-m9-eval-system/codex-review-prompt-natural-gating-v2.md
?? .steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md

exec
/bin/zsh -lc "nl -ba .steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md | sed -n '1,180p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba .steering/20260430-m9-eval-system/codex-review-prompt-natural-gating-v2.md | sed -n '1,260p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     1	# M5/M6 natural runtime gating bug — design v2 (P3a-decide v2)
     2	
     3	> Plan-mode 等価ドキュメント (auto-mode 内 "Plan + /reimagine + Codex review"
     4	> CLAUDE.md 制約)。本ファイルで初期案 + reimagine 代案 + 採用案 + Codex review
     5	> 反映を一元化する。**design v1 (`design-natural-gating-fix.md`) の続編**:
     6	> v1 は仮説 D (zone scatter) を解決したが、empirical で仮説 B (cooldown ×
     7	> cognition_period の wall 換算) が re-activate された (PR #131
     8	> `g-gear-phase-a-failure.md` 参照)。
     9	
    10	## 1. v2 を起草する empirical 根拠
    11	
    12	### 1.1 v1 fix 後の G-GEAR Phase A 観測 (PR #131)
    13	
    14	| 指標 | v1 修正前 (PR #129) | v1 期待値 | **v1 修正後 実測 (本セッション根拠)** |
    15	|---|---|---|---|
    16	| focal_rows (kant) | 6 | 30 | **6** |
    17	| total_rows | 12 | ~90 | **18** |
    18	| dialogs | 2 | ~10 | **3** |
    19	| nietzsche admit | 0 (starved) | included | **2 dialogs** ✅ |
    20	| wall | 13 min (kill) | 5-8 min | **10 min wall timeout** |
    21	
    22	**v1 の効果**: nietzsche starve は解消 (zone bypass が機能)、3 pair 全部 admit。
    23	**v1 で未解決**: 18 turn 全部が tick 1-5 内、tick=5 以降 8 min 0 admit (= cooldown 中)。
    24	
    25	### 1.2 dominant gate の empirical 確定
    26	
    27	```
    28	empirical: 600 s wall → max(world_tick) = 5 ⇒ 1 tick ≈ 120 s
    29	原因: qwen3:8b Q4_K_M on RTX 5060 Ti で
    30	      reflection embed + chat + action selection + dialog turn × 6 が
    31	      serial round-trip で蓄積、cognition tick advance を blocking
    32	```
    33	
    34	実効 cooldown = `COOLDOWN_TICKS=30` × 120 s/tick = **60 min wall**
    35	⇒ 10 min wall 内で同一 pair が再 admit されるのは物理的に不可能。
    36	
    37	### 1.3 design v1 §2 仮説 B の再評価
    38	
    39	design v1 は仮説 B を「△ 補助」とし、棄却根拠として以下を引いた:
    40	> kant_natural 13 min wall で nietzsche cognition_period=7s + WorldRuntime
    41	> DEFAULT_COGNITION_PERIOD_S=10s → world_tick は 50+ 進むはず
    42	
    43	これは **誤った前提**。実機の 7B-Q4 ローカル推論では LLM round-trip が
    44	cognition_period の名目値を完全に upper-bound として支配しない。本 design v2
    45	では仮説 B を「◎ 主因」に格上げし、design v1 §2 の判断を v2 §1 で **明示的に
    46	覆す**。
    47	
    48	## 2. 候補空間 (G-GEAR §4 の 5 案 + /reimagine 代案 3)
    49	
    50	G-GEAR `g-gear-phase-a-failure.md` §4 の 5 案 + 本 Mac セッションの /reimagine
    51	で 3 案追加 (ζ / θ / ι)。
    52	
    53	| 案 | 内容 | 実装複雑度 | 概念純度 | empirical 必達確率 | test impact |
    54	|---|---|---|---|---|---|
    55	| α | eval mode で COOLDOWN_TICKS=5 (現状 30) | 低 | 中 | 高 (10 min wall × 5 ticks/cooldown 必要) | 低 |
    56	| β | wall budget 30→60 min for natural | 低 (CLI flag default 変更) | 高 | 中 (cooldown=30 単独では 1 cycle のみ) | 無 |
    57	| γ | AUTO_FIRE_PROB_PER_TICK 0.25→1.0 | 低 | 中 | 低 (cooldown が dominant gate のため効果限定) | 中 |
    58	| δ | 1 cell 逐次採取 (3 並列廃止) | 低 (CLI 運用変更) | 中 | 低 (cognition_period 不変、wall 単純倍化のみ) | 無 |
    59	| ε | dialog_turn_budget 6→3 | 中 | 低 (per-dialog stylo signal が薄まる) | 中 | 中 |
    60	| **ζ** *(reimagine)* | wall-time-based cooldown (`time.monotonic()`) | 中 (monotonic 経路 + monkeypatch test) | 高 (tick rate 変動に robust) | 高 | 中 |
    61	| **θ** *(reimagine)* | cooldown 完全廃止 + AUTO_FIRE_PROB_PER_TICK のみ | 低 | 中 (prob が gate に) | 中 (prob 0.25 で variability 大) | 低 |
    62	| **ι** *(reimagine)* | β + δ ハイブリッド (cooldown 不変、wall 大拡張、cell 逐次) | 低 | **最高** (cooldown semantics 不変) | 中 (3h × 3 cell = 9h、overnight) | 無 |
    63	
    64	### 2.1 G-GEAR 推奨 α + β ハイブリッドの empirical 計算
    65	
    66	```
    67	60 min wall × 1 tick / 120 s = 30 ticks 進行
    68	cooldown=5 ticks × 120 s/tick = 10 min wall cooldown
    69	30 ticks / 5 ticks per cycle ≈ 6 cycle (G-GEAR 計算 5 cycle、prob 0.25 込みで)
    70	3 dialogs × 6 turns × 5 cycle = 90 utterance
    71	focal kant per cell ≈ 90 × (1/3) = 30 ✓ (target 達成)
    72	```
    73	
    74	### 2.2 /reimagine 代案 ζ (wall-time cooldown) の検討
    75	
    76	**仮想実装**:
    77	```python
    78	import time
    79	self._last_close_wall: dict[frozenset[str], float] = {}
    80	
    81	# schedule_initiate / tick で:
    82	last_close_wall = self._last_close_wall.get(key)
    83	if last_close_wall is not None and (time.monotonic() - last_close_wall) < COOLDOWN_WALL_S:
    84	    return None
    85	```
    86	
    87	**利点**:
    88	1. tick rate (cognition_period) の変動に対し robust。将来 FP16 化で cognition_period が
    89	   60 s/tick に半減しても cooldown semantics が崩れない。
    90	2. 「natural cadence 1 min = 1 dialog 開始」という人間直感と一致。
    91	
    92	**欠点**:
    93	1. **M4 frozen Protocol の純粋関数性違反**: `DialogScheduler` Protocol は tick ベースの
    94	   deterministic semantics で、`time.monotonic()` 注入は副作用源を増やす。test では
    95	   `monkeypatch time.monotonic` が全 cooldown test に必要 (現状 1228+ test の cooldown
    96	   関連 ~20 件全部に影響)。
    97	2. ManualClock + tick 駆動の既存 test fixture を破壊。
    98	3. CLAUDE.md "コードに既存パターンに従う" 原則違反 (cooldown は M4 から tick ベース)。
    99	4. eval mode 専用 → 別経路 if 分岐 → コード経路 fork、ME-8 invariant を二重定義することに。
   100	
   101	**評価**: ζ は overscoping。本タスクのターゲットは "natural pilot 30 focal を 60 min wall
   102	で完走" であり、将来の cognition_period 変動 robustness は本タスクスコープ外。本タスクで
   103	解決すべきは empirical な cooldown semantics の再校正のみ。**棄却**。
   104	
   105	### 2.3 /reimagine 代案 θ (cooldown 完全廃止) の検討
   106	
   107	**仮想実装**:
   108	```python
   109	# eval_natural_mode=True のとき cooldown check 全 bypass
   110	if self.eval_natural_mode:
   111	    pass  # cooldown チェック飛ばす
   112	```
   113	
   114	**利点**:
   115	1. mental model 最小化 (cooldown 概念が無くなる)。
   116	2. AUTO_FIRE_PROB_PER_TICK=0.25 が唯一の cadence 制御 → tunable は 1 個のみ。
   117	
   118	**欠点**:
   119	1. **dominant gate が cooldown から prob に移転**するだけで、prob 0.25 の cognition_period
   120	   依存性が浮上。120 s/tick × 30 ticks × 0.25 = 7.5 admit 期待 (variance 大、focal target
   121	   30 達成の確実性が cooldown=5 案より低)。
   122	2. 同 pair の即時連続 admit リスク: dialog close 直後 (last_activity_tick の次の tick) に
   123	   AUTO_FIRE が当たれば即 admit、3 pair 全部が同 tick で同時に admit する "burst 多発"
   124	   が起こり得る。dialog_turn_budget=6 で「同 pair が 6 tick 占有」されることで indirect に
   125	   防がれるが、これは fragile な暗黙依存。
   126	3. ME-8 ADR §invariant の "cooldown active" を完全削除する必要、PR #130 で確定した
   127	   contract から後退。
   128	
   129	**評価**: cooldown 概念削除は ME-8 ADR の意味的後退。dominant gate を prob に移すだけで
   130	empirical robustness が改善するわけでもない。**棄却**。
   131	
   132	### 2.4 /reimagine 代案 ι (β + δ) の検討
   133	
   134	**仮想実装**:
   135	- α/cooldown 不変 (`COOLDOWN_TICKS=30` keep)
   136	- β: wall=30 min → 240 min (4h)
   137	- δ: 3 並列 → 1 cell 逐次運用
   138	
   139	**期待計算**:
   140	```
   141	240 min × 1 tick / 120 s = 120 ticks
   142	cooldown=30 → 4 cycle (cycle 間隔 30 ticks × 120 s = 60 min)
   143	4 cycle × 3 dialogs × 6 turns = 72 utterance
   144	focal kant ≈ 72 / 3 = 24 (target 30 にやや不足)
   145	1 cell 4h × 3 cell = 12h overnight 採取
   146	```
   147	
   148	**利点**: cooldown semantics 不変、ME-8 §invariant は v1 のまま、test 影響ゼロ。
   149	
   150	**欠点**:
   151	1. wall 12h overnight 採取は stimulus 採取 (cell ~3 min、3 cell 並列 ~3 min) との運用乖離が
   152	   大きい。stimulus + natural の両建てで 12h × 5 run = 60h overnight が現実的でない。
   153	2. focal target 30 を満たすには wall=300 min 以上必要、運用ぎりぎり。
   154	3. 1 cell 逐次は 3 並列より wall 効率が常に悪い。
   155	
   156	**評価**: 概念純度は最高だが運用コストが許容外。**棄却**。
   157	
   158	## 3. 採用案: α + β ハイブリッド
   159	
   160	### 3.1 採用根拠
   161	
   162	1. **empirical 必達確率が高い**: §2.1 計算で focal kant ≈ 30 達成、G-GEAR 推奨と一致。
   163	2. **実装最小**: `COOLDOWN_TICKS_EVAL: ClassVar[int] = 5` 別定数化 + `_effective_cooldown()`
   164	   helper + CLI default 30→60 min の 3 箇所変更。
   165	3. **既存 test 完全互換**: live mode の COOLDOWN_TICKS=30 不変、既存 1248 PASS 維持。
   166	4. **ME-8 invariant 後退最小**: "cooldown active" → "cooldown active with eval-mode-specific
   167	   reduced threshold" に文言更新するのみ、cooldown 概念自体は保持。
   168	5. **/reimagine 代案 ζ/θ/ι の trade-off で全敗**: ζ は overscoping、θ は dominant gate
   169	   移転、ι は wall 爆発 — α+β が支配的。
   170	
   171	### 3.2 棄却サマリ
   172	
   173	| 案 | 主棄却理由 |
   174	|---|---|
   175	| γ | cooldown が dominant gate のため prob 単独調整は効果限定 |
   176	| δ | cognition_period 不変、wall 単純倍化のみ |
   177	| ε | per-dialog stylo signal を薄める (Burrows/MATTR の measurement 劣化) |
   178	| ζ | M4 frozen Protocol の純粋関数性違反、overscoping |
   179	| θ | cooldown→prob の dominant gate 移転、ME-8 invariant 後退 |
   180	| ι | wall 12h × overnight × 多 run で運用コスト許容外 |

 succeeded in 0ms:
     1	# Codex independent review — m9-eval-system P3a-decide v2 (cooldown × cognition_period)
     2	
     3	> Codex `gpt-5.5 xhigh` independent review request. Prompt として
     4	> `cat .steering/20260430-m9-eval-system/codex-review-prompt-natural-gating-v2.md
     5	> | codex exec --skip-git-repo-check` で起動。
     6	> 出力は `codex-review-natural-gating-v2.md` に verbatim 保存。本 review は
     7	> v1 (`codex-review-natural-gating.md`、Verdict: ship) の **後続**で、v1 の
     8	> fix がデプロイされた後の empirical observation で別の dominant gate が
     9	> 露呈したため。
    10	
    11	---
    12	
    13	## Context
    14	
    15	You previously reviewed and shipped a fix (Verdict: ship, HIGH=0/MEDIUM=0/
    16	LOW=2) for m9-eval-system P3a natural-condition pilot stalling. The fix
    17	added `InMemoryDialogScheduler.eval_natural_mode: bool = False` flag that
    18	bypasses zone-equality and reflective-zone gates so 3 personas can
    19	sustain dialog after LLM-driven `destination_zone` scatters them.
    20	
    21	**The fix worked partially**. G-GEAR Phase A re-capture (PR #131) showed:
    22	
    23	| 指標 | v1 修正前 | v1 期待 | v1 修正後 実測 |
    24	|---|---|---|---|
    25	| focal_rows (kant) | 6 | 30 | **6** |
    26	| total_rows | 12 | ~90 | **18** |
    27	| dialogs | 2 | ~10 | **3** |
    28	| nietzsche admit | 0 (starved) | included | **2 dialogs** ✅ |
    29	| wall | 13 min (kill) | 5-8 min | **10 min wall timeout** |
    30	
    31	**Zone scatter (hypothesis D) is solved** — Nietzsche starve is gone,
    32	all 3 pairs admit at least once. But all 18 turns happened in `tick=1..5`,
    33	then **8 minutes of zero admits**.
    34	
    35	## Re-activated dominant gate (hypothesis B from design v1)
    36	
    37	design v1 §2 **rejected** hypothesis B with the rationale "world_tick 50+
    38	in 13 min wall makes 30-tick cooldown < 30% of wall, so cooldown alone
    39	can't explain stall." That premise was **wrong empirically**:
    40	
    41	```
    42	empirical: 600 s wall → max(world_tick) = 5 ⇒ 1 tick ≈ 120 s
    43	root cause: qwen3:8b Q4_K_M on RTX 5060 Ti — reflection (embed + chat) +
    44	            action selection (chat) + dialog turn (chat × 6) accumulate as
    45	            serial round-trips, blocking cognition tick advance
    46	effective cooldown: COOLDOWN_TICKS=30 × 120 s = 60 min wall
    47	                   ⇒ within 10 min wall, same pair re-admit is physically
    48	                     impossible
    49	```
    50	
    51	`g-gear-phase-a-failure.md` (PR #131) inter-turn delta confirms: 18
    52	utterances clustered in ~95 s burst, then 8 min plateau with no admits
    53	even though Reflection trigger logs show cognition is alive (Reflection
    54	fires every ~30 s after burst — tick rate ~1/30 s during reflection-only
    55	phase, but ~1/120 s during dialog phase).
    56	
    57	## Candidate space (G-GEAR §4 + Mac /reimagine)
    58	
    59	G-GEAR proposed 5 candidates. Mac added 3 reimagine alternatives (ζ/θ/ι).
    60	
    61	| 案 | 内容 | 実装複雑度 | 概念純度 | empirical 必達 | test impact |
    62	|---|---|---|---|---|---|
    63	| α | eval mode で COOLDOWN_TICKS=5 | 低 | 中 | 高 | 低 |
    64	| β | wall budget 30→60 min for natural | 低 (CLI default) | 高 | 中 | 無 |
    65	| γ | AUTO_FIRE_PROB_PER_TICK=1.0 | 低 | 中 | 低 (cooldown dominant) | 中 |
    66	| δ | 1 cell 逐次採取 | 低 | 中 | 低 (cognition_period 不変) | 無 |
    67	| ε | dialog_turn_budget 6→3 | 中 | 低 (stylo signal 薄) | 中 | 中 |
    68	| **ζ** *(reimagine)* | wall-time-based cooldown (`time.monotonic()`) | 中 | 高 | 高 | 中 |
    69	| **θ** *(reimagine)* | cooldown 完全廃止 + prob のみ | 低 | 中 | 中 | 低 |
    70	| **ι** *(reimagine)* | β+δ ハイブリッド (cooldown 不変、wall 大、cell 逐次) | 低 | **最高** | 中 (3h × 3 cell) | 無 |
    71	
    72	## Proposed fix v2: α + β hybrid
    73	
    74	### Adopted rationale
    75	
    76	1. **empirical 必達確率が高い**: 60 min wall × cooldown=5 ticks ⇒ 30 ticks /
    77	   5 ticks per cycle ≈ 5-6 cycle ⇒ focal kant ≈ 30 (target 達成)
    78	2. **実装最小**: `COOLDOWN_TICKS_EVAL: ClassVar[int] = 5` 別定数化 +
    79	   `_effective_cooldown()` helper + CLI default 30→60 min の 3 箇所変更
    80	3. **既存 test 完全互換**: live mode の `COOLDOWN_TICKS=30` 不変、既存 1248 PASS 維持
    81	4. **ME-8 invariant 後退最小**: "cooldown active" → "cooldown active with
    82	   eval-mode-specific reduced threshold" に文言更新するのみ、cooldown 概念自体は保持
    83	5. **reimagine 代案で全敗**: ζ は M4 frozen Protocol 純粋関数性違反、θ は dominant
    84	   gate 移転 (cooldown→prob)、ι は wall 12h × overnight × multi-run で運用コスト許容外
    85	
    86	### Diff sketch
    87	
    88	```python
    89	# src/erre_sandbox/integration/dialog.py
    90	class InMemoryDialogScheduler:
    91	    COOLDOWN_TICKS: ClassVar[int] = 30  # live (unchanged)
    92	    COOLDOWN_TICKS_EVAL: ClassVar[int] = 5  # NEW eval_natural_mode 限定
    93	
    94	    def _effective_cooldown(self) -> int:
    95	        return self.COOLDOWN_TICKS_EVAL if self.eval_natural_mode else self.COOLDOWN_TICKS
    96	
    97	    # schedule_initiate (existing line ~200):
    98	    if (
    99	        last_close is not None
   100	        and tick - last_close < self._effective_cooldown()  # was self.COOLDOWN_TICKS
   101	        and not self.golden_baseline_mode
   102	    ):
   103	        return None
   104	
   105	    # tick() (existing line ~337):
   106	    if last_close is not None and world_tick - last_close < self._effective_cooldown():
   107	        continue  # was self.COOLDOWN_TICKS
   108	```
   109	
   110	```python
   111	# src/erre_sandbox/cli/eval_run_golden.py
   112	# capture_natural の click option:
   113	@click.option(
   114	    "--wall-timeout-min",
   115	    type=int,
   116	    default=60,  # was 30
   117	    help="Maximum wall-clock minutes for the natural capture phase.",
   118	)
   119	```
   120	
   121	### Test plan (12→16 cases in test_dialog_eval_natural_mode.py)
   122	
   123	1. **`test_eval_mode_uses_reduced_cooldown`**: eval_natural_mode=True で同一 pair が
   124	   tick 5 後に再 admit 可能、tick 4 では reject
   125	2. **`test_live_mode_cooldown_unchanged`**: eval_natural_mode=False で
   126	   COOLDOWN_TICKS=30 が active、tick 29 で reject / tick 30 で admit
   127	3. **`test_effective_cooldown_returns_correct_value`**: helper の純関数 contract
   128	4. **`test_class_constants_unchanged`**: `COOLDOWN_TICKS == 30` /
   129	   `COOLDOWN_TICKS_EVAL == 5` の sentinel test
   130	
   131	CLI test に `--wall-timeout-min default=60` の 1 ケース追加。
   132	
   133	### ME-8 ADR §invariant の partial-update
   134	
   135	v1 ADR で「Cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
   136	invariant は両 mode で active のまま」と書いた箇所を以下に Edit:
   137	
   138	> **Cooldown (eval-mode 別 threshold = `COOLDOWN_TICKS_EVAL=5`、live は
   139	> `COOLDOWN_TICKS=30`)** / probability / timeout / 自己 dialog reject /
   140	> 二重 open reject の invariant は両 mode で active のまま — eval natural cadence
   141	> は維持、proximity 制約のみ削除 + cooldown threshold を eval mode で reduce。
   142	
   143	### 期待される empirical 値 (G-GEAR rerun)
   144	
   145	```
   146	60 min wall × 1 tick / 120 s = 30 ticks 進行
   147	cooldown=5 ticks per cycle、prob 0.25 込みで実効 ~6 cycle  (G-GEAR 計算)
   148	3 dialogs × 6 turns × 5 cycle ~= 90 utterance
   149	focal kant per cell ≈ 90 / 3 = 30 ✓
   150	```
   151	
   152	ただし AUTO_FIRE_PROB_PER_TICK=0.25 の variance を加味した realistic estimate は:
   153	```
   154	1 cycle = 6 ticks (turn) + 5 ticks (cooldown) = 11 ticks/cycle
   155	60 min wall × 30 ticks / 11 ticks per cycle ≈ 2.7 cycle
   156	2.7 × 18 utt = 49 utterance/cell
   157	focal kant per cell ≈ 16-30 (variance あり)
   158	```
   159	
   160	→ default=60 min は最低保証、不足なら 90/120 min に上げる。
   161	
   162	## Specific questions to Codex
   163	
   164	Please return findings in HIGH / MEDIUM / LOW format with file:line refs.
   165	Particular concerns:
   166	
   167	- **Q1**: §2.4 ι (β+δ ハイブリッド = cooldown semantics 不変 + 4h wall + 1 cell 逐次)
   168	  を「wall 爆発」で棄却したが、ME-8 invariant 後退ゼロという観点で本当は ι が
   169	  正解では？α+β は ME-8 ADR の invariant を後退させる semantic cost を払うが、
   170	  ι は払わない。empirical wall コスト (12h × overnight) は許容外と判断したが、
   171	  これは scoping bias で過剰に α+β に寄せていないか？
   172	- **Q2**: `COOLDOWN_TICKS_EVAL=5` を hardcoded class const にしたが、CLI
   173	  `--cooldown-ticks-eval N` で override 可能にすべきか？将来 cognition_period
   174	  が変動した時の柔軟性 vs hardcoded sentinel test の robustness の trade-off。
   175	- **Q3**: §5 リスク 2 で realistic estimate が focal=16-30 と margin が薄いと自己
   176	  認定した。`--wall-timeout-min default=60` ではなく `default=90` にすべきか？
   177	  90 min なら realistic 4 cycle = 72 utt = focal 24/cell が下限保証 (mean 30+)。
   178	- **Q4**: ME-8 §invariant 文言の "active with reduced threshold" は v1 contract
   179	  に対し silent な後退ではないか？v1 では "active" を厳格定義としていた可能性、
   180	  本 v2 で文言を緩めるのは ADR re-open のままで OK か (新 ADR child 起票が必要か)。
   181	- **Q5**: §3.3.3 で追加した 4 test のうち `test_class_constants_unchanged` は
   182	  sentinel test として over-defensive ではないか？将来 COOLDOWN_TICKS_EVAL の
   183	  empirical 再校正で値変更があった場合に false positive で test 落ちる。
   184	- **Q6**: dialog_turn_budget=6 と reduced cooldown=5 の組合せで「close 直後 (tick T)
   185	  → cooldown 抜け (tick T+5) → 即再 admit」が同 pair で連発する "ピンポン admit"
   186	  が起こり得る。これは natural cadence の semantics 上問題ないか？dialog_turn_budget
   187	  が同 pair 占有を最低 6 ticks 保証するので indirect には防がれるが、明示的な
   188	  "minimum gap between dialogs of same pair" として cooldown=5 で意味的に十分か。
   189	- **Q7**: §2 候補空間 で **γ (AUTO_FIRE_PROB_PER_TICK=1.0) を「cooldown が dominant
   190	  gate のため効果限定」**と棄却したが、本 v2 で α+β に切り替えた後は **prob 0.25 の
   191	  variance が新たな副次 dominant gate になる可能性**。realistic estimate の variance
   192	  を抑えるため eval mode で prob=1.0 に上げる組合せ案 (= α+β+γ ハイブリッド) は
   193	  考慮するべきでないか？
   194	- **Q8**: design v1 では "Cooldown / probability / timeout は active のまま (natural
   195	  cadence 保持)" を core invariant として claim したが、empirical で cognition_period
   196	  120 s/tick が判明した今、cooldown=30 ticks の意味は live mode (cognition_period
   197	  ~10 s/tick 想定) と eval mode で全く別物。**M4 frozen Protocol の "tick ベース
   198	  cooldown" 抽象化自体が漏れている**のではないか (= ζ wall-time cooldown が本来正解
   199	  だが overscoping で defer して良いか)。
   200	
   201	## Files to consult (relative to repo root)
   202	
   203	- `.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md` (本 design v2)
   204	- `.steering/20260430-m9-eval-system/design-natural-gating-fix.md` (v1)
   205	- `.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md` (PR #131 empirical report)
   206	- `.steering/20260430-m9-eval-system/decisions.md` ME-8 ADR (v1)
   207	- `.steering/20260430-m9-eval-system/codex-review-natural-gating.md` (v1 verdict)
   208	- `src/erre_sandbox/integration/dialog.py` (修正対象、特に line 89-95 / 200-210 / 337)
   209	- `src/erre_sandbox/cli/eval_run_golden.py` (`capture_natural` の click options)
   210	- `tests/test_integration/test_dialog_eval_natural_mode.py` (12 既存 test、4 追加予定)
   211	
   212	## Output format requested
   213	
   214	```
   215	## Verdict
   216	[ship | revise | reject] — one-line summary
   217	
   218	## HIGH (must fix before merge)
   219	HIGH-1 ...  file:line + finding + recommendation
   220	
   221	## MEDIUM (should consider)
   222	MEDIUM-1 ...
   223	
   224	## LOW (nice to have)
   225	LOW-1 ...
   226	
   227	## Answers to Q1-Q8
   228	Q1: ...
   229	Q2: ...
   230	...
   231	```
   232	
   233	## Token budget reminder
   234	
   235	`.codex/budget.json` daily=1M、本日 used=337,503 (~33%)。本 invocation は
   236	per_invocation_max=200K 範囲内で完了させること。`gpt-5.5 xhigh` で。

codex
## Verdict
revise — α+β is a defensible short-term fix, but the current design/test plan has blocking inconsistencies around wall timeout and the existing cooldown test.

## HIGH
HIGH-1: `.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:210` says current default is `90.0` and proposes `120.0`, but the same file still says CLI test should assert `60` at line 249 and risk text says `default=60` at lines 303-305. `src/erre_sandbox/cli/eval_run_golden.py:122` is already `90.0`. Recommendation: pick one contract. I would set design + code + CLI test to `120.0`, or explicitly keep `90.0`; do not regress to `60`.

HIGH-2: `tests/test_integration/test_dialog_eval_natural_mode.py:226` currently asserts eval mode preserves `COOLDOWN_TICKS=30` through tick admission. The v2 design says “add” four tests at `.steering/.../design-natural-gating-fix-v2.md:235`, but this existing test must be rewritten or it will fail after `_effective_cooldown()`. Recommendation: rename/update it to assert `COOLDOWN_TICKS_EVAL=5`, then add the live-mode unchanged test separately.

## MEDIUM
MEDIUM-1: ME-8 should be explicitly amended, not silently softened. `decisions.md:364` currently records cooldown as active in both modes, and v2 changes the threshold semantics at `.steering/.../design-natural-gating-fix-v2.md:257`. Recommendation: add a dated “ME-8 amendment / re-open result” section with PR #131 empirical data and the new eval threshold.

MEDIUM-2: The success estimate is still overconfident. `.steering/.../design-natural-gating-fix-v2.md:66` counts cooldown cycles without dialog duration or RNG waiting; lines 299-302 later contradict it. Recommendation: make the conservative estimate primary and justify the wall default from that estimate.

## LOW
LOW-1: `codex-review-prompt-natural-gating-v2.md:110` still describes a Click option with `default=60`, but the code uses argparse and `_DEFAULT_WALL_TIMEOUT_MIN` at `eval_run_golden.py:122`. Update the prompt artifact before saving the review verbatim.

## Answers to Q1-Q8
Q1: ι is conceptually clean but not the right P3a fix. It still misses focal 30 at 4h by its own estimate and imposes large operational cost. α+β is acceptable if ME-8 is explicitly amended.

Q2: Do not add `--cooldown-ticks-eval` yet. A class constant plus ADR re-open condition is better for this empirical calibration. CLI tuning would make run comparability worse.

Q3: Use `120` if changing the default; otherwise keep existing `90`. Do not set `60`.

Q4: It is a contract change. OK as a re-opened ME-8 amendment; not OK as silent wording drift.

Q5: `test_class_constants_unchanged` is over-defensive. Prefer behavior tests: eval admits at 5, live admits at 30.

Q6: Cooldown 5 is semantically enough for this eval mode because dialog duration adds the real gap. It is not live-natural semantics, so document it as eval cadence calibration.

Q7: Do not add γ in the same patch. Keep probability active for attribution; if v2 with 90/120 still fails, re-open on probability as the next dominant gate.

Q8: Yes, tick-based cooldown leaks wall-time assumptions under slow local LLMs. ζ is the cleaner long-term model, but deferring it is reasonable for P3a because it changes scheduler semantics and tests more broadly.
hook: Stop
hook: Stop Completed
2026-05-01T14:34:20.095698Z ERROR codex_core::session: failed to record rollout items: thread 019de3f2-d3a9-7e23-a98b-e6f434816b55 not found
tokens used
145,717
## Verdict
revise — α+β is a defensible short-term fix, but the current design/test plan has blocking inconsistencies around wall timeout and the existing cooldown test.

## HIGH
HIGH-1: `.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:210` says current default is `90.0` and proposes `120.0`, but the same file still says CLI test should assert `60` at line 249 and risk text says `default=60` at lines 303-305. `src/erre_sandbox/cli/eval_run_golden.py:122` is already `90.0`. Recommendation: pick one contract. I would set design + code + CLI test to `120.0`, or explicitly keep `90.0`; do not regress to `60`.

HIGH-2: `tests/test_integration/test_dialog_eval_natural_mode.py:226` currently asserts eval mode preserves `COOLDOWN_TICKS=30` through tick admission. The v2 design says “add” four tests at `.steering/.../design-natural-gating-fix-v2.md:235`, but this existing test must be rewritten or it will fail after `_effective_cooldown()`. Recommendation: rename/update it to assert `COOLDOWN_TICKS_EVAL=5`, then add the live-mode unchanged test separately.

## MEDIUM
MEDIUM-1: ME-8 should be explicitly amended, not silently softened. `decisions.md:364` currently records cooldown as active in both modes, and v2 changes the threshold semantics at `.steering/.../design-natural-gating-fix-v2.md:257`. Recommendation: add a dated “ME-8 amendment / re-open result” section with PR #131 empirical data and the new eval threshold.

MEDIUM-2: The success estimate is still overconfident. `.steering/.../design-natural-gating-fix-v2.md:66` counts cooldown cycles without dialog duration or RNG waiting; lines 299-302 later contradict it. Recommendation: make the conservative estimate primary and justify the wall default from that estimate.

## LOW
LOW-1: `codex-review-prompt-natural-gating-v2.md:110` still describes a Click option with `default=60`, but the code uses argparse and `_DEFAULT_WALL_TIMEOUT_MIN` at `eval_run_golden.py:122`. Update the prompt artifact before saving the review verbatim.

## Answers to Q1-Q8
Q1: ι is conceptually clean but not the right P3a fix. It still misses focal 30 at 4h by its own estimate and imposes large operational cost. α+β is acceptable if ME-8 is explicitly amended.

Q2: Do not add `--cooldown-ticks-eval` yet. A class constant plus ADR re-open condition is better for this empirical calibration. CLI tuning would make run comparability worse.

Q3: Use `120` if changing the default; otherwise keep existing `90`. Do not set `60`.

Q4: It is a contract change. OK as a re-opened ME-8 amendment; not OK as silent wording drift.

Q5: `test_class_constants_unchanged` is over-defensive. Prefer behavior tests: eval admits at 5, live admits at 30.

Q6: Cooldown 5 is semantically enough for this eval mode because dialog duration adds the real gap. It is not live-natural semantics, so document it as eval cadence calibration.

Q7: Do not add γ in the same patch. Keep probability active for attribution; if v2 with 90/120 still fails, re-open on probability as the next dominant gate.

Q8: Yes, tick-based cooldown leaks wall-time assumptions under slow local LLMs. ζ is the cleaner long-term model, but deferring it is reasonable for P3a because it changes scheduler semantics and tests more broadly.

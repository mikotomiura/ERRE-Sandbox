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
session id: 019e06b6-e777-7631-92c3-ec17b3365e47
--------
user
# Codex independent review request — M9-eval-system P4a Tier B 起草

## 役割

あなたは ERRE-Sandbox プロジェクトの **independent reviewer**。Claude が起草
した P4a Tier B 設計案 (v1 + v2 + comparison v3) を **同一モデル 1 発生成の
構造的バイアス** から救出するために招かれている。Verdict + 優先度付き finding
+ web-search-based prior art 引用で reply してほしい。要約禁止、verbatim 保存
される。

## 報告フォーマット (厳守)

1. **Verdict**: 一行 — `APPROVE` / `ADOPT-WITH-CHANGES` / `REJECT`
2. **HIGH** finding (must reflect before merge): 各 finding に
   `[HIGH-N] title` + ≥3 行 rationale + 引用 (URL or paper)
3. **MEDIUM** finding (decisions.md ADR 反映): `[MEDIUM-N]`
4. **LOW** finding (blockers.md defer 可): `[LOW-N]`
5. **Prior art summary** (web search 必須): 下記 §「Prior art 必須調査」5 件全件
6. **Closing note**: v3 hybrid を採用すべきか / v1 / v2 / 別案

## Mission の再掲

`src/erre_sandbox/evidence/tier_b/` をゼロから起草、LoRA 採用判定 (DB9 quorum)
の 3 sub-metric (Vendi Score / Big5 stability ICC / Burrows Δ) のうち Tier B
新規 2 (Vendi / Big5 ICC) + IPIP-NEO administering helper を提供する。Burrows
Δ は `tier_a/burrows.py` 既存。

DB9 quorum (M9-B `decisions.md` DB9):
- adoption: 3 sub-metric の 2-of-3 が `BootstrapResult` の CI で baseline positive
- rollback: 2-of-3 が baseline negative
- Tier A=floor diagnostic、Tier C=defensive canary、**Tier B=offensive gate
  唯一の arbiter**

## 必読 reference files (本セッション scope 内、独立 read 可能)

### Claude 設計案 (3 件、本 prompt の review 対象)

- `.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md` (infrastructure-first)
- `.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md` (psychometric-rigor-first)
- `.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md` (hybrid v3 candidate)

### ADR 制約 (絶対遵守)

- `.steering/20260430-m9-b-lora-execution-plan/decisions.md` DB1-DB11 (M9-B)
- `.steering/20260430-m9-eval-system/decisions.md` ME-1〜ME-9 (M9-eval)
- `.steering/20260430-m9-eval-system/design-final.md` (Tier B が DB9 で果たす役割)

### 既存 infrastructure (流用先)

- `src/erre_sandbox/evidence/bootstrap_ci.py` — `BootstrapResult`,
  `hierarchical_bootstrap_ci(values_per_cluster, *, block_length=50,
  cluster_only=False, auto_block=False, n_resamples=2000, ci=0.95, seed=0)`,
  `estimate_block_length()` (PR #146 P5 hardening)
- `src/erre_sandbox/evidence/tier_a/empath_proxy.py` — proxy framing docstring
  雛形 (DB10 honest framing)
- `src/erre_sandbox/evidence/tier_a/novelty.py` — MPNet
  (`paraphrase-multilingual-mpnet-base-v2`) lazy-load パターン
- `src/erre_sandbox/evidence/eval_store.py` — DuckDB schema、`metrics.tier_b`
  table column (`run_id/persona_id/turn_idx/metric_name/metric_value/notes`)、
  `connect_training_view()` は `raw_dialog.dialog` projection only (DB5
  contract)

### Codex 過去 review 履歴 (本タスクと同質補正期待の文脈)

- `.steering/20260430-m9-eval-system/codex-review.md` (P5 HIGH-2 hierarchical
  bootstrap、HIGH-3 Vendi 200-turn 最小、HIGH-5 Burrows L1)
- 過去 5 連続 (P3a-finalize / Phase 2 run0 / CLI partial-fix / run1 calibration /
  ME-9 trigger) で Claude solo 検出不能の HIGH を切出した empirical 実績あり

## v3 hybrid の要点 (review 対象)

| Q | v3 commitment |
|---|---|
| Q1 Vendi kernel | hybrid (semantic MPNet 0.7 + lexical 5-gram 0.3) |
| Q1 window | 100 turn (design-final 整合) |
| Q2 IPIP-NEO 版 | IPIP-50 (Goldberg 1992、日本語 Murakami 2002/2003 流用) |
| Q3 ICC formula | ICC(2,k) consistency primary + ICC(A,1) absolute agreement diagnostic |
| Q4 bootstrap | `cluster_only=True` primary + `auto_block=True` diagnostic 併載 |
| Q5 LIWC alternative | DB10 Option D 通り全廃、Tier B 全 module 冒頭 docstring に honest framing |

## Prior art 必須調査 (web search 強制、verbatim 引用)

以下 5 件全件で literature 引用を伴う finding を出してほしい。1 件でも skip した
ら REJECT 扱い。

1. **Vendi Score 2023 paper** (https://arxiv.org/abs/2210.02410) の kernel 選択
   - hybrid kernel (semantic + lexical) の prior art 有無
   - 100-turn vs 200-turn window の minimum sample size 議論
   - orthogonal one-hot で score=N が成立する数学的条件
2. **IPIP-NEO Mini-20 vs IPIP-50** (Donnellan et al. 2006、Goldberg 1992)
   - Cronbach α の dimension-level reliability 比較
   - LLM personality assessment の 2024-2026 prior art (e.g.,
     Salecha et al. 2024 arXiv 2405.06058、Huang et al. arXiv 2310.01386 等)
   - Mini-20 が ICC<0.6 trigger を不当発火させるリスク
3. **ICC for LLM personality stability** prior art (2024-2026)
   - ICC(2,k) consistency vs ICC(A,1) absolute agreement の選択基準
   - Koo & Li 2016 cutoff (0.5/0.75/0.9) が absolute agreement に適用可か
   - drift detection 文脈での appropriate ICC formula
4. **LIWC vs Empath empirical equivalence** (Fast et al. 2016)
   - DB10 Option D (LIWC 全廃) の justifiability
   - Tier A Empath proxy framing が DB10 honest framing 要件を満たすか
5. **Mini-IPIP / IPIP-50 日本語版** (Murakami 2002/2003)
   - 利用条件 (open / 学術 / 商用)、license, retrieval URL
   - cross-language validation 問題

## review で必ず check してほしい質問群

下記は launch prompt §「Codex review で必須に問うこと」全件を細分化したもの。
省略禁止。

### Vendi 関連

- Q1A: hybrid kernel weight 0.7/0.3 の妥当性 (Friedman & Dieng 2023 Section 4)
- Q1B: window 100 turn が Vendi spectrum stability に sufficient か
  (Codex 過去 HIGH-3 で 200-turn 最小と指摘、v3 で 100 維持の trade-off)
- Q1C: orthogonal one-hot で score=N が成立する条件と sanity test 設計
- Q1D: multilingual (ja+en mixed) で MPNet kernel が semantic similarity を
  fairly 測れるか

### IPIP-NEO 関連

- Q2A: IPIP-50 vs Mini-IPIP-20 の Cronbach α gap が ME-1 fallback (ICC<0.6)
  trigger 判定に与える影響
- Q2B: 日本語 IPIP-50 (Murakami 2002/2003) の利用 license 確認、
  defer 必要なら fallback path
- Q2C: persona-conditional prompt (kant/rikyu/nietzsche system prompt + IPIP-NEO
  item) の framing が social desirability bias (Salecha 2024) に耐えるか
- Q2D: 5-point Likert vs 7-point Likert の trade-off (LLM agentic loop 文脈)
- Q2E: balanced reverse-keyed item 比率 (~50%) の妥当性

### Big5 ICC 関連

- Q3A: ICC(2,k) consistency と ICC(A,1) absolute agreement のどちらを ME-1
  trigger primary にするべきか
- Q3B: ME-1 threshold 0.6 (point) / 0.5 (lower CI) が absolute agreement にも
  literally 適用可か、再評価必要か
- Q3C: per-window n=100 turn が ICC 計算に sufficient か (rule-of-thumb / power
  analysis literature)
- Q3D: identical 回答列 → ICC = 1.0 の sanity test が両 formula で成立するか
- Q3E: 5 run × 5 window = 25 cluster で ICC 信頼区間が construct validity に
  耐えるか

### bootstrap 関連

- Q4A: `cluster_only=True` primary + `auto_block=True` diagnostic 併載が JSON
  consumer 側で混乱を招かないか
- Q4B: PR #146 で `cluster_only` を承諾した HIGH-2 framing と矛盾しないか
- Q4C: 25 cluster (cluster_only) と 12.5 cluster (200-turn window 案) の
  effective sample size 比較
- Q4D: bootstrap CI が persona-conditional でなく pooled で運用される場合の
  variance underestimation リスク

### LIWC 関連

- Q5A: DB10 Option D (LIWC 全廃) の literature justifiability
- Q5B: Tier B 全 module 冒頭 docstring の honest framing 文言が DB10 要件を
  satisfied するか (`empath_proxy.py` 雛形と同等の rigor か)

### 設計全体

- Q6A: v3 hybrid が v1 + v2 の structural bias を残していないか (independent
  reviewer 視点)
- Q6B: `metrics.tier_b` の column schema (`turn_idx` を `window_index` 意味で
  再利用) の semantic abuse リスク
- Q6C: DB11 contamination prevention (PR #145) の Tier B 観点 follow-up
- Q6D: P5 残課題 2 件 (Vendi orthogonal one-hot test / Big5 ICC 1.0 convergence
  test) を本 PR で close する妥当性

## 出力先

verdict + finding は **そのまま raw text** で reply。Claude が
`.steering/20260430-m9-eval-system/codex-review-p4a.md` に **verbatim 保存**
する (要約禁止)。

## 工数 expectation

- web search 5 件全件 + finding 起票で **30-40 分**、token 予算 ~150K-200K
  程度を想定 (`.codex/budget.json` の per-invocation max 内)

## 最後に

直近 5 連続の Codex review で Claude solo 検出不能の HIGH を毎回切り出してきた
empirical 実績がある。本 review でも同質の補正を期待する。Adopt-with-changes
が default expected verdict。

hook: SessionStart
hook: SessionStart Completed
hook: UserPromptSubmit
hook: UserPromptSubmit Completed
codex
I’ll treat this as a review task and use `$erre-workflow` as the entry point. I’m going to read the target design/ADR files first, then run the required web search before forming findings.
exec
/bin/zsh -lc "sed -n '1,220p' .agents/skills/erre-workflow/SKILL.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,220p' .agents/skills/project-status/SKILL.md" in /Users/johnd/ERRE-Sand Box
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
`$erre-workflow` confirms this is a review-only path, so I won’t create or edit steering files. I’m now reading the three Claude proposals plus the binding ADR/design files and the existing Tier A/bootstrap/store code that constrains Tier B.
exec
/bin/zsh -lc 'wc -l .steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md .steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md .steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md .steering/20260430-m9-b-lora-execution-plan/decisions.md .steering/20260430-m9-eval-system/decisions.md .steering/20260430-m9-eval-system/design-final.md .steering/20260430-m9-eval-system/codex-review.md src/erre_sandbox/evidence/bootstrap_ci.py src/erre_sandbox/evidence/tier_a/empath_proxy.py src/erre_sandbox/evidence/tier_a/novelty.py src/erre_sandbox/evidence/eval_store.py' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     391 .steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md
     216 .steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md
     147 .steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md
     326 .steering/20260430-m9-b-lora-execution-plan/decisions.md
     713 .steering/20260430-m9-eval-system/decisions.md
     615 .steering/20260430-m9-eval-system/design-final.md
    3944 .steering/20260430-m9-eval-system/codex-review.md
     389 src/erre_sandbox/evidence/bootstrap_ci.py
      81 src/erre_sandbox/evidence/tier_a/empath_proxy.py
     108 src/erre_sandbox/evidence/tier_a/novelty.py
     436 src/erre_sandbox/evidence/eval_store.py
    7366 total

exec
/bin/zsh -lc 'rg -n "DB9|DB10|DB11|DB5|ME-1|ME-9|Tier B|Vendi|ICC|Burrows|tier_b|turn_idx|connect_training_view|BootstrapResult|cluster_only|auto_block|estimate_block_length" .steering/20260430-m9-b-lora-execution-plan/decisions.md .steering/20260430-m9-eval-system/decisions.md .steering/20260430-m9-eval-system/design-final.md .steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md .steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md .steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md .steering/20260430-m9-eval-system/codex-review.md src/erre_sandbox/evidence/bootstrap_ci.py src/erre_sandbox/evidence/eval_store.py src/erre_sandbox/evidence/tier_a/empath_proxy.py src/erre_sandbox/evidence/tier_a/novelty.py' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
.steering/20260430-m9-eval-system/decisions.md:6:5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)。本 ADR set は M9-B DB1-DB10 と
.steering/20260430-m9-eval-system/decisions.md:14:## ME-1 — IPIP-NEO fallback trigger operational definition (Codex MEDIUM-1)
.steering/20260430-m9-eval-system/decisions.md:18:  - **trigger**: golden baseline 採取後 (3 persona × 5 run の Big5 ICC 計測完了時点) に
.steering/20260430-m9-eval-system/decisions.md:19:    **≥2/3 personas で ICC 点推定 < 0.6 OR 95% lower CI bound < 0.5**
.steering/20260430-m9-eval-system/decisions.md:20:  - **検出 timing**: P5 (bootstrap CI) 完了直後の自動チェック、`evidence/tier_b/big5_icc.py`
.steering/20260430-m9-eval-system/decisions.md:27:  - Codex MEDIUM-1: 「ICC < 0.6 が頻発」の頻発に denominator 無し → 監査不能
.steering/20260430-m9-eval-system/decisions.md:30:  - Koo/Li ICC 解釈: 0.5-0.75 = moderate (effectsize docs)、0.6 boundary は
.steering/20260430-m9-eval-system/decisions.md:39:  - `evidence/tier_b/big5_icc.py` に diagnostic 4 種 (ICC point, lower CI, acquiescence,
.steering/20260430-m9-eval-system/decisions.md:63:     の `connect_training_view()` / `connect_analysis_view()` の両 entry で wrapper enforced)
.steering/20260430-m9-eval-system/decisions.md:139:    Burrows Delta + MATTR (lightweight) の CI を計算する経路を整備 (G-GEAR DuckDB の
.steering/20260430-m9-eval-system/decisions.md:146:  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/decisions.md:151:  - 200 turn は Vendi の 200-turn window を 1 cycle 満たす最小値
.steering/20260430-m9-eval-system/decisions.md:152:  - bootstrap CI width が直接的な測定対象 (DB9 quorum の信頼性)
.steering/20260430-m9-eval-system/decisions.md:168:  - golden baseline 採取後に DB9 quorum の sub-metric が persona discriminative でない
.steering/20260430-m9-eval-system/decisions.md:178:  - **2 段階 close は不正確だった**: 当初想定の「(2) で最終 close」は Vendi + Big5 ICC
.steering/20260430-m9-eval-system/decisions.md:181:    ratio 実測 (本 update、Burrows + MATTR のみ) / (3) full ratio 実測 (P4 完了後、
.steering/20260430-m9-eval-system/decisions.md:182:    Vendi + Big5 ICC を含めて再判定)。
.steering/20260430-m9-eval-system/decisions.md:189:      | Burrows Delta | 6.09 | 2.49 | **0.41** | 2 (kant+nietzsche) |
.steering/20260430-m9-eval-system/decisions.md:194:    - **方向性は両 metric で一致** (Burrows 0.41、MATTR 0.992 ≤ 1.0): natural narrower
.steering/20260430-m9-eval-system/decisions.md:196:    - **scale dominance caveat**: Burrows (~6.0 scale) が MATTR (~0.013 scale) を
.steering/20260430-m9-eval-system/decisions.md:197:      ~470x で支配しているため、combined ratio は実質 Burrows 単独の判定。per-metric
.steering/20260430-m9-eval-system/decisions.md:201:    - 根拠 1: target-extrapolated で natural が 41% (Burrows) / 99% (MATTR) — natural
.steering/20260430-m9-eval-system/decisions.md:205:      Vendi 200-turn window 1 cycle の最小値 (元 ADR §根拠 2) で下限制約あり、
.steering/20260430-m9-eval-system/decisions.md:211:    - 暫定性の根拠: Vendi + Big5 ICC が P4 完了後に異なる方向性を示す可能性あり、
.steering/20260430-m9-eval-system/decisions.md:212:      Rikyu Burrows は Japanese tokenizer 未実装で 2/3 persona のみ寄与 (n_cells=2)。
.steering/20260430-m9-eval-system/decisions.md:214:    - **P4 deliverable**: Vendi Score + Big5 ICC を全 6 cell に対し計算 → ratio
.steering/20260430-m9-eval-system/decisions.md:218:    - **m9-eval-corpus expansion**: rikyu Japanese tokenizer 実装 → Rikyu Burrows
.steering/20260430-m9-eval-system/decisions.md:221:    - **DB9 quorum sub-metric 不足**: golden baseline 採取後に persona-discriminative
.steering/20260430-m9-eval-system/decisions.md:224:    - 本 ADR は ME-4 §判定基準が指す **3 metric (Burrows / Vendi / Big5 ICC)**
.steering/20260430-m9-eval-system/decisions.md:225:      のうち 1/3 metric (Burrows、Rikyu 除く 2/3 persona) + lightweight proxy 1
.steering/20260430-m9-eval-system/decisions.md:226:      metric (MATTR、3/3 persona) のみで判断している。**Vendi + Big5 ICC を含む
.steering/20260430-m9-eval-system/decisions.md:237:      script schema bump v1 → v3、`_KNOWN_LIMITATIONS` 経由で rikyu Burrows を
.steering/20260430-m9-eval-system/decisions.md:272:## ME-6 — Burrows reference corpus QC (Codex MEDIUM-6)
.steering/20260430-m9-eval-system/decisions.md:342:     - **base control measurement (ME-1 の per-item 拡張)**: persona prompt 無しの
.steering/20260430-m9-eval-system/decisions.md:344:       ME-1 が IPIP-NEO control を規定するのに対し、本 ADR は MCQ control を規定
.steering/20260430-m9-eval-system/decisions.md:381:  - Option B (Kant のみ MCQ): per-persona stimulus mass 違いで Vendi/Burrows の
.steering/20260430-m9-eval-system/decisions.md:399:  - P4a で `evidence/tier_b/big5_icc.py` の base control を per-item 拡張 (ME-1 と
.steering/20260430-m9-eval-system/decisions.md:566:## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)
.steering/20260430-m9-eval-system/decisions.md:628:    本 incident で覆すのは不適切、IPIP-NEO ICC sample size に余分な影響
.steering/20260430-m9-eval-system/decisions.md:656:rate=1.596/min ≈ 95.75/h) で **ME-9 trigger ≥80/h に該当**し、G-GEAR Claude が
.steering/20260430-m9-eval-system/decisions.md:712:- 既存 M9-B DB1-DB10 ADR との衝突: 無し
src/erre_sandbox/evidence/eval_store.py:6:entry point is :func:`connect_training_view`, which opens a DuckDB file
src/erre_sandbox/evidence/eval_store.py:28:Both :func:`connect_training_view` and :func:`connect_analysis_view`
src/erre_sandbox/evidence/eval_store.py:99:_METRIC_TIERS: tuple[str, ...] = ("tier_a", "tier_b", "tier_c")
src/erre_sandbox/evidence/eval_store.py:104:    ' "turn_idx" INTEGER,'
src/erre_sandbox/evidence/eval_store.py:111:Tier A is per-turn, Tier B is per-100-turn aggregate, Tier C is judge
src/erre_sandbox/evidence/eval_store.py:216:def connect_training_view(db_path: str | Path) -> RawTrainingRelation:
src/erre_sandbox/evidence/eval_store.py:433:    "connect_training_view",
src/erre_sandbox/evidence/tier_a/empath_proxy.py:11:**Big5 claim is explicitly NOT made.** ME-1 in the design's
src/erre_sandbox/evidence/tier_a/empath_proxy.py:12:``decisions.md`` keeps Big5 self-report on IPIP-NEO via Tier B; using
src/erre_sandbox/evidence/bootstrap_ci.py:1:"""Bootstrap confidence intervals for Tier A / Tier B metric aggregates.
src/erre_sandbox/evidence/bootstrap_ci.py:5:turn-level samples)** for autocorrelation-aware CI estimation. The DB9
src/erre_sandbox/evidence/bootstrap_ci.py:13:* :func:`estimate_block_length` — Politis-White-inspired autocorrelation
src/erre_sandbox/evidence/bootstrap_ci.py:17:* ``cluster_only`` flag on :func:`hierarchical_bootstrap_ci` — skips
src/erre_sandbox/evidence/bootstrap_ci.py:19:  Tier B per-100-turn metric where the 25 windows / persona means the
src/erre_sandbox/evidence/bootstrap_ci.py:22:* ``auto_block`` flag on :func:`hierarchical_bootstrap_ci` — passes the
src/erre_sandbox/evidence/bootstrap_ci.py:23:  pooled stream through :func:`estimate_block_length` to pick the
src/erre_sandbox/evidence/bootstrap_ci.py:36:* :func:`estimate_block_length` — automatic block-length picker for the
src/erre_sandbox/evidence/bootstrap_ci.py:37:  ``auto_block`` path of :func:`hierarchical_bootstrap_ci`.
src/erre_sandbox/evidence/bootstrap_ci.py:39:All helpers return :class:`BootstrapResult` so plotting / quorum gates
src/erre_sandbox/evidence/bootstrap_ci.py:59:budget and shipped without observability complaints. For DB9 ratio
src/erre_sandbox/evidence/bootstrap_ci.py:75:class BootstrapResult:
src/erre_sandbox/evidence/bootstrap_ci.py:86:    (DB9 quorum, ME-4 ratio decision) and the dataclass is frozen so
src/erre_sandbox/evidence/bootstrap_ci.py:120:) -> BootstrapResult:
src/erre_sandbox/evidence/bootstrap_ci.py:134:        :class:`BootstrapResult` with ``method="percentile"`` and
src/erre_sandbox/evidence/bootstrap_ci.py:168:    return BootstrapResult(
src/erre_sandbox/evidence/bootstrap_ci.py:179:def estimate_block_length(
src/erre_sandbox/evidence/bootstrap_ci.py:237:    cluster_only: bool,
src/erre_sandbox/evidence/bootstrap_ci.py:238:    auto_block: bool,
src/erre_sandbox/evidence/bootstrap_ci.py:244:    if cluster_only:
src/erre_sandbox/evidence/bootstrap_ci.py:246:    if auto_block:
src/erre_sandbox/evidence/bootstrap_ci.py:248:        effective_block_length = estimate_block_length(
src/erre_sandbox/evidence/bootstrap_ci.py:262:    cluster_only: bool,
src/erre_sandbox/evidence/bootstrap_ci.py:266:    if cluster_only:
src/erre_sandbox/evidence/bootstrap_ci.py:286:    cluster_only: bool = False,
src/erre_sandbox/evidence/bootstrap_ci.py:287:    auto_block: bool = False,
src/erre_sandbox/evidence/bootstrap_ci.py:291:) -> BootstrapResult:
src/erre_sandbox/evidence/bootstrap_ci.py:306:            per 10 blocks. Ignored when ``cluster_only=True``; replaced
src/erre_sandbox/evidence/bootstrap_ci.py:307:            when ``auto_block=True``.
src/erre_sandbox/evidence/bootstrap_ci.py:308:        cluster_only: When ``True``, skip the inner block step and
src/erre_sandbox/evidence/bootstrap_ci.py:310:            draw. Use this for Tier B per-100-turn windowed metrics
src/erre_sandbox/evidence/bootstrap_ci.py:314:        auto_block: When ``True`` (and ``cluster_only=False``), call
src/erre_sandbox/evidence/bootstrap_ci.py:315:            :func:`estimate_block_length` on the pooled stream and use
src/erre_sandbox/evidence/bootstrap_ci.py:323:        :class:`BootstrapResult`. ``method`` is
src/erre_sandbox/evidence/bootstrap_ci.py:324:        ``"hierarchical-cluster-only"`` when ``cluster_only=True`` and
src/erre_sandbox/evidence/bootstrap_ci.py:353:        cluster_only=cluster_only,
src/erre_sandbox/evidence/bootstrap_ci.py:354:        auto_block=auto_block,
src/erre_sandbox/evidence/bootstrap_ci.py:364:            cluster_only=cluster_only,
src/erre_sandbox/evidence/bootstrap_ci.py:371:    return BootstrapResult(
src/erre_sandbox/evidence/bootstrap_ci.py:385:    "BootstrapResult",
src/erre_sandbox/evidence/bootstrap_ci.py:387:    "estimate_block_length",
.steering/20260430-m9-eval-system/design-final.md:24:| P4a | Tier B `evidence/tier_b/{vendi,ipip_neo,big5_icc}.py` 実装 | Claude | Mac | CPU + 7B-Q4 借用 (~5GB MPS) | 5h | unit test 緑 |
.steering/20260430-m9-eval-system/design-final.md:25:| P4b | Tier B 後付け実行 (採取済 raw_dialog から post-hoc) | Operator | G-GEAR | 7B-Q4 ~5GB | 2h | metrics schema 投入完了 |
.steering/20260430-m9-eval-system/design-final.md:26:| P5 | bootstrap CI + 2-of-3 quorum logic (DB9、`evidence/bootstrap_ci.py`) | Claude | Mac | CPU only | 3h | sub-metric 3 個 ready |
.steering/20260430-m9-eval-system/design-final.md:50:1. **API contract**: `eval_store.connect_training_view()` が **唯一** の training-loader
.steering/20260430-m9-eval-system/design-final.md:57:   eval store fixture を作り、**全 training egress 経路** (`connect_training_view()` /
.steering/20260430-m9-eval-system/design-final.md:87:- Big5 stability ICC は **IPIP-NEO 自己申告 self-report のみ** に依拠 (Tier B、agent
.steering/20260430-m9-eval-system/design-final.md:89:- stylometric 一致は Burrows Delta (Tier A)
.steering/20260430-m9-eval-system/design-final.md:90:- persona-fit textual diversity は Vendi (Tier B)
.steering/20260430-m9-eval-system/design-final.md:96:- blockers.md DB10 honest framing "LIWC OSS proxy で Big5 claim は honest に避ける"
.steering/20260430-m9-eval-system/design-final.md:105:ICC < 0.6 が頻発した場合の **conditional fallback** を `decisions.md` に re-open
.steering/20260430-m9-eval-system/design-final.md:107:- BIG5-CHAT regression head を Tier B に追加し second opinion 化
.steering/20260430-m9-eval-system/design-final.md:117:    (within-persona floor diagnostic、cross-persona absolute accuracy は DB9 比較指標に
.steering/20260430-m9-eval-system/design-final.md:137:- 50 turn では Vendi の expected window 200 turn が満たされず統計力不足
.steering/20260430-m9-eval-system/design-final.md:138:  (Codex HIGH-3 evidence: Vendi は kernel/eigenvalue based、sample 必要)
.steering/20260430-m9-eval-system/design-final.md:231:- `eval_thresholds.py` — DB9 quorum bound、frozen Pydantic、snapshot test ガード
.steering/20260430-m9-eval-system/design-final.md:234:- `eval_store.py` — DuckDB connection、schema bootstrap、`connect_training_view()`
.steering/20260430-m9-eval-system/design-final.md:238:  - `burrows.py` — **Burrows Delta** = z-scored function-word frequency vector の
.steering/20260430-m9-eval-system/design-final.md:248:- `tier_b/` directory:
.steering/20260430-m9-eval-system/design-final.md:250:  - `vendi.py` — Vendi Score (semantic kernel)
.steering/20260430-m9-eval-system/design-final.md:252:  - `big5_icc.py` — Big5 stability ICC (run × mode で計算)
.steering/20260430-m9-eval-system/design-final.md:262:  Tier B per-100-turn metric は cluster-only resample (各 persona あたり 25 window
.steering/20260430-m9-eval-system/design-final.md:274:- `eval_tier_b.py` — Tier B post-hoc 計算 (G-GEAR 実行)
.steering/20260430-m9-eval-system/design-final.md:293:- `tests/test_evidence/test_tier_b/` (3 test file)
.steering/20260430-m9-eval-system/design-final.md:312:  P0b contracts + CI gate ──┤── DB5 contract gate (3 層)
.steering/20260430-m9-eval-system/design-final.md:326:  P4a Tier B 3 metric                ┐
.steering/20260430-m9-eval-system/design-final.md:327:  P4b Tier B 後付け実行 (G-GEAR)      ├── post-hoc
.steering/20260430-m9-eval-system/design-final.md:335:**DB9 sub-metric 3 個 (Vendi / Big5 ICC / Burrows Delta) ready 時期**:
.steering/20260430-m9-eval-system/design-final.md:336:- Burrows: P1a 完了時 (per-turn computed)
.steering/20260430-m9-eval-system/design-final.md:337:- Vendi / Big5 ICC: P4a 完了時 (per-100-turn computed)
.steering/20260430-m9-eval-system/design-final.md:385:- pingouin: ICC は scipy.stats + numpy で実装可
.steering/20260430-m9-eval-system/design-final.md:398:  `aggregate(db_path)` パターンを Tier A 5 metric / Tier B 3 metric にも踏襲
.steering/20260430-m9-eval-system/design-final.md:414:1. **DB5 schema-guard**: `tests/test_evidence/test_eval_paths_contract.py` で
.steering/20260430-m9-eval-system/design-final.md:419:3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260430-m9-eval-system/design-final.md:434:  Burrows Delta が persona-discriminative (Kant ≠ Nietzsche、distance 差 ≥ fixed delta)
.steering/20260430-m9-eval-system/design-final.md:435:- `test_tier_b/`: 3 metric が known distribution で expected 値、IPIP-NEO loop が
.steering/20260430-m9-eval-system/design-final.md:440:### Burrows multi-lang (blockers.md 暫定方針)
.steering/20260430-m9-eval-system/design-final.md:448:  - metrics sidecar の `(run_id, persona_id, turn_idx)` で raw に LEFT JOIN して
.steering/20260430-m9-eval-system/design-final.md:451:  - DB9 sub-metric 3 個に CI 数値、persona-discriminative 観察を `blockers.md`
.steering/20260430-m9-eval-system/design-final.md:485:   - cross-mode stability ICC は run independence 前提が壊れる可能性
.steering/20260430-m9-eval-system/design-final.md:486:   - **conditional fallback**: ICC < 0.6 が頻発したら BIG5-CHAT regression head を
.steering/20260430-m9-eval-system/design-final.md:487:     Tier B に追加し second opinion 化。発火条件を `decisions.md` に明文化
.steering/20260430-m9-eval-system/design-final.md:489:3. **Burrows Delta multi-language reference の汚染** (blockers.md 既出)
.steering/20260430-m9-eval-system/design-final.md:497:   - 反復: P3b で pilot run 50 turn 両形式比較、Burrows / Vendi の bootstrap CI
.steering/20260430-m9-eval-system/design-final.md:514:| Burrows Delta = z-scored function-word L1 (cosine ではない) | HIGH-5 | design.md §burrows.py 定義 | ✅ 反映済 |
.steering/20260430-m9-eval-system/design-final.md:515:| IPIP fallback trigger operational definition | MEDIUM-1 | `decisions.md` ME-1 ADR | ✅ ADR 化 |
.steering/20260430-m9-eval-system/design-final.md:520:| Burrows token floor: corpus QC 化 (固定 50K → ≥5K-word chunk stability) | MEDIUM-6 | `decisions.md` ME-6 ADR / `blockers.md` reopen 条件 | ✅ ADR 化 |
.steering/20260430-m9-eval-system/design-final.md:537:  - LIWC は v2 Option D (blockers.md 1 件 close + work cost zero + DB10 honest framing
.steering/20260430-m9-eval-system/design-final.md:555:  P1a (Tier A sub-module、Burrows は z-score Delta で実装) → P2c (external golden
.steering/20260430-m9-eval-system/design-final.md:568:- `connect_training_view()` の返り値を **`RawTrainingRelation`** (constrained
.steering/20260430-m9-eval-system/design-final.md:581:- Tier B per-100-turn metric は cluster-only resample (effective sample size 25
.steering/20260430-m9-eval-system/design-final.md:589:- 50 turn では Vendi の 200 turn window 不足、最小 200 turn/condition/persona
.steering/20260430-m9-eval-system/design-final.md:601:**HIGH-5 反映** — Burrows Delta correction:
.steering/20260430-m9-eval-system/design-final.md:605:- DB9 quorum sub-metric の名称は "Burrows Delta" のまま (M9-B `decisions.md`
.steering/20260430-m9-eval-system/design-final.md:606:  DB9 と整合)、内部実装を Delta 規格に合わせる
.steering/20260430-m9-eval-system/design-final.md:612:- DB1-DB10 の M9-B ADR との衝突: 無し
.steering/20260430-m9-eval-system/codex-review.md:32:2-of-3 quorum drift gate (M9-B ADR DB9). Its completion criterion is to take a
.steering/20260430-m9-eval-system/codex-review.md:33:3 persona × 5 run × 500 turn **golden baseline** to a state where Vendi /
.steering/20260430-m9-eval-system/codex-review.md:34:Big5-ICC / Burrows-Delta have bootstrap CI ready (precondition for M9-C-adopt).
.steering/20260430-m9-eval-system/codex-review.md:43:3. `.steering/20260430-m9-b-lora-execution-plan/decisions.md` — DB1-DB10 ADR set
.steering/20260430-m9-eval-system/codex-review.md:44:   that constrains this task (especially DB5 raw/sidecar separation, DB6 epoch
.steering/20260430-m9-eval-system/codex-review.md:45:   policy, DB9 bootstrap CI quorum, DB10 4-tier framework)
.steering/20260430-m9-eval-system/codex-review.md:47:   this task is expected to close (LIWC license, Burrows multi-lang, judge bias)
.steering/20260430-m9-eval-system/codex-review.md:58:| DB5 physical separation | DuckDB single file + named schemas (`raw_dialog`, `metrics`) + training-loader API guard (`connect_training_view()` raises `EvaluationContaminationError` on `metrics.*` SELECT) + **CI grep gate** in `.github/workflows/ci.yml` blocking `metrics.` in training-loader paths. 3-layer defense. Parquet demoted to nightly export format only. |
.steering/20260430-m9-eval-system/codex-review.md:60:| LIWC | **Option D**: full retirement. Big5 stability claim relies on **IPIP-NEO short-form self-report only** (Tier B, agent answers via local 7B-Q4). Empath retained as Tier A *secondary diagnostic only* (no Big5 claim). LIWC license deferral closes immediately. |
.steering/20260430-m9-eval-system/codex-review.md:68:G-GEAR runs P3 baseline capture, P4b Tier B post-hoc, and P6 Tier C nightly.
.steering/20260430-m9-eval-system/codex-review.md:113:   *conditional fallback* to BIG5-CHAT regression head if ICC < 0.6 frequently —
.steering/20260430-m9-eval-system/codex-review.md:126:   statistical power to detect a difference in bootstrap-CI width on Burrows
.steering/20260430-m9-eval-system/codex-review.md:127:   Delta and Vendi? What's the minimum pilot size that would be defensible?
.steering/20260430-m9-eval-system/codex-review.md:131:5. **Burrows Delta multi-language reference: 50K token noise floor.** The
.steering/20260430-m9-eval-system/codex-review.md:151:   `evidence/tier_b/*.py` from Mac (Mac→GG implied but not flagged)? Is the
.steering/20260430-m9-eval-system/codex-review.md:157:- DB1-DB10 ADR set (M9-B `decisions.md`) — blocked from change in this review
.steering/20260430-m9-eval-system/codex-review.md:480:     7	DB5 物理分離を **別 Parquet file** で達成 (`raw_dialog/` と `metrics/` 配下を path 規約で
.steering/20260430-m9-eval-system/codex-review.md:489:    16	DB5 物理分離を **DuckDB 単 file の named schema (raw_dialog / metrics) + training-
.steering/20260430-m9-eval-system/codex-review.md:504:    31	| **DB5 物理分離** | 別 Parquet file + path 規約 | DuckDB 単 file + named schema + training-loader API guard + CI grep gate |
.steering/20260430-m9-eval-system/codex-review.md:547:    74	- **Hybrid baseline** は drift gate の baseline noise を統制、Burrows Delta /
.steering/20260430-m9-eval-system/codex-review.md:548:    75	  Vendi の statistical power を高める
.steering/20260430-m9-eval-system/codex-review.md:582:   109	   - 理由: blockers.md DB10 honest framing と完全整合、license 議論自体が消滅、
.steering/20260430-m9-eval-system/codex-review.md:584:   111	   - 補強: v2 自身がリスク 3 で挙げた「self-report bias」対策として、ICC < 0.6
.steering/20260430-m9-eval-system/codex-review.md:599:   126	   - 理由: `tier_a.py` 1 file に 5 metric (Burrows / MATTR / NLI / novelty /
.steering/20260430-m9-eval-system/codex-review.md:630:   157	- (a) blockers.md DB10 の "LIWC OSS proxy で Big5 claim は honest に避ける" と
.steering/20260430-m9-eval-system/codex-review.md:645:   172	> **DuckDB 単 file + schema-guard + CI grep gate** で DB5 を構造的に守り、
.steering/20260430-m9-eval-system/codex-review.md:675:    21	| P4a | Tier B `evidence/tier_b/{vendi,ipip_neo,big5_icc}.py` 実装 | Claude | Mac | CPU + 7B-Q4 借用 (~5GB MPS) | 5h | unit test 緑 |
.steering/20260430-m9-eval-system/codex-review.md:676:    22	| P4b | Tier B 後付け実行 (採取済 raw_dialog から post-hoc) | Operator | G-GEAR | 7B-Q4 ~5GB | 2h | metrics schema 投入完了 |
.steering/20260430-m9-eval-system/codex-review.md:677:    23	| P5 | bootstrap CI + 2-of-3 quorum logic (DB9、`evidence/bootstrap_ci.py`) | Claude | Mac | CPU only | 3h | sub-metric 3 個 ready |
.steering/20260430-m9-eval-system/codex-review.md:701:    47	1. **API contract**: `eval_store.connect_training_view()` が **唯一** の training-loader entry。
.steering/20260430-m9-eval-system/codex-review.md:728:    74	- Big5 stability ICC は **IPIP-NEO 自己申告 self-report のみ** に依拠 (Tier B、agent
.steering/20260430-m9-eval-system/codex-review.md:730:    76	- stylometric 一致は Burrows Delta (Tier A)
.steering/20260430-m9-eval-system/codex-review.md:731:    77	- persona-fit textual diversity は Vendi (Tier B)
.steering/20260430-m9-eval-system/codex-review.md:737:    83	- blockers.md DB10 honest framing "LIWC OSS proxy で Big5 claim は honest に避ける"
.steering/20260430-m9-eval-system/codex-review.md:746:    92	ICC < 0.6 が頻発した場合の **conditional fallback** を `decisions.md` に re-open
.steering/20260430-m9-eval-system/codex-review.md:748:    94	- BIG5-CHAT regression head を Tier B に追加し second opinion 化
.steering/20260430-m9-eval-system/codex-review.md:772:   118	- P3b で pilot run 50 turn 両形式を比較し、Burrows Delta / Vendi の bootstrap CI
.steering/20260430-m9-eval-system/codex-review.md:840:   186	- `eval_thresholds.py` — DB9 quorum bound、frozen Pydantic、snapshot test ガード
.steering/20260430-m9-eval-system/codex-review.md:843:   189	- `eval_store.py` — DuckDB connection、schema bootstrap、`connect_training_view()`
.steering/20260430-m9-eval-system/codex-review.md:847:   193	  - `burrows.py` — Burrows Delta function-word vector cosine
.steering/20260430-m9-eval-system/codex-review.md:852:   198	- `tier_b/` directory:
.steering/20260430-m9-eval-system/codex-review.md:854:   200	  - `vendi.py` — Vendi Score (semantic kernel)
.steering/20260430-m9-eval-system/codex-review.md:856:   202	  - `big5_icc.py` — Big5 stability ICC (run × mode で計算)
.steering/20260430-m9-eval-system/codex-review.md:871:   217	- `eval_tier_b.py` — Tier B post-hoc 計算 (G-GEAR 実行)
.steering/20260430-m9-eval-system/codex-review.md:890:   236	- `tests/test_evidence/test_tier_b/` (3 test file)
.steering/20260430-m9-eval-system/codex-review.md:909:   255	  P0b contracts + CI gate ──┤── DB5 contract gate (3 層)
.steering/20260430-m9-eval-system/codex-review.md:928:   269	  P4a Tier B 3 metric                ┐
.steering/20260430-m9-eval-system/codex-review.md:929:   270	  P4b Tier B 後付け実行 (G-GEAR)      ├── post-hoc
.steering/20260430-m9-eval-system/codex-review.md:937:   278	**DB9 sub-metric 3 個 (Vendi / Big5 ICC / Burrows Delta) ready 時期**:
.steering/20260430-m9-eval-system/codex-review.md:938:   279	- Burrows: P1a 完了時 (per-turn computed)
.steering/20260430-m9-eval-system/codex-review.md:939:   280	- Vendi / Big5 ICC: P4a 完了時 (per-100-turn computed)
.steering/20260430-m9-eval-system/codex-review.md:979:   320	- pingouin: ICC は scipy.stats + numpy で実装可
.steering/20260430-m9-eval-system/codex-review.md:992:   333	  `aggregate(db_path)` パターンを Tier A 5 metric / Tier B 3 metric にも踏襲
.steering/20260430-m9-eval-system/codex-review.md:1008:   349	1. **DB5 schema-guard**: `tests/test_evidence/test_eval_paths_contract.py` で
.steering/20260430-m9-eval-system/codex-review.md:1013:   354	3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260430-m9-eval-system/codex-review.md:1026:   367	  Burrows Delta が persona-discriminative (Kant ≠ Nietzsche、distance 差 ≥ fixed delta)
.steering/20260430-m9-eval-system/codex-review.md:1027:   368	- `test_tier_b/`: 3 metric が known distribution で expected 値、IPIP-NEO loop が
.steering/20260430-m9-eval-system/codex-review.md:1032:   373	### Burrows multi-lang (blockers.md 暫定方針)
.steering/20260430-m9-eval-system/codex-review.md:1040:   381	  - metrics sidecar の `(run_id, persona_id, turn_idx)` で raw に LEFT JOIN して
.steering/20260430-m9-eval-system/codex-review.md:1043:   384	  - DB9 sub-metric 3 個に CI 数値、persona-discriminative 観察を `blockers.md`
.steering/20260430-m9-eval-system/codex-review.md:1077:   418	   - cross-mode stability ICC は run independence 前提が壊れる可能性
.steering/20260430-m9-eval-system/codex-review.md:1078:   419	   - **conditional fallback**: ICC < 0.6 が頻発したら BIG5-CHAT regression head を
.steering/20260430-m9-eval-system/codex-review.md:1079:   420	     Tier B に追加し second opinion 化。発火条件を `decisions.md` に明文化
.steering/20260430-m9-eval-system/codex-review.md:1081:   422	3. **Burrows Delta multi-language reference の汚染** (blockers.md 既出)
.steering/20260430-m9-eval-system/codex-review.md:1089:   430	   - 反復: P3b で pilot run 50 turn 両形式比較、Burrows / Vendi の bootstrap CI
.steering/20260430-m9-eval-system/codex-review.md:1100:   441	- DB5 物理表現の DuckDB 単 file vs 別 Parquet file 戦略の優劣 (3 層 contract の
.steering/20260430-m9-eval-system/codex-review.md:1105:   446	- Burrows Delta multi-lang reference の閾値 (50K token noise floor)
.steering/20260430-m9-eval-system/codex-review.md:1124:   465	  - LIWC は v2 Option D (blockers.md 1 件 close + work cost zero + DB10 honest framing
.steering/20260430-m9-eval-system/codex-review.md:1145:     1	# Decisions — M9-B LoRA Execution Plan (10 ADR: DB1-DB10)
.steering/20260430-m9-eval-system/codex-review.md:1224:    80	    - plateau: prompting + persona YAML 拡張のみで Tier B metric が **2 連続 run で
.steering/20260430-m9-eval-system/codex-review.md:1225:    81	      <5% improvement** (operational definition は DB9 quorum logic に統合)
.steering/20260430-m9-eval-system/codex-review.md:1245:   101	## DB5 — Parquet schema: **raw + sidecar 物理分離** (HIGH-4 反映)
.steering/20260430-m9-eval-system/codex-review.md:1250:   106	  - **metrics/**: sidecar evaluation metric table。`run_id + persona_id + turn_idx` で
.steering/20260430-m9-eval-system/codex-review.md:1276:   132	    - **Tier B**: per 100 turns (Vendi / IPIP-NEO / Big5 ICC)
.steering/20260430-m9-eval-system/codex-review.md:1335:   191	## DB9 — Drift gate: composite + bootstrap CI + 2-of-3 quorum (HIGH-2 反映)
.steering/20260430-m9-eval-system/codex-review.md:1338:   194	  - **Primary composite per persona**: 各 persona の Tier B から 3 sub-metric:
.steering/20260430-m9-eval-system/codex-review.md:1352:   208	  - codex HIGH-2: 「5%」固定 + Tier B noise → false rollback / metric gaming リスク
.steering/20260430-m9-eval-system/codex-review.md:1367:   223	## DB10 — J 評価系 framework: 4-tier + persona-conditional + multi-channel (specs only in M9-B)
.steering/20260430-m9-eval-system/codex-review.md:1372:   228	    - Tier A: per-turn cheap (LIWC/Empath / Burrows Delta / MATTR / semantic novelty / NLI)
.steering/20260430-m9-eval-system/codex-review.md:1373:   229	    - Tier B: per-100-turn (Vendi Score / IPIP-NEO / Big5 stability ICC)
.steering/20260430-m9-eval-system/codex-review.md:1440:    20	- **status**: DB10 で正式 framing 採用、license 最終決定は defer
.steering/20260430-m9-eval-system/codex-review.md:1449:    29	- **option D**: stylometry (Burrows' Delta) のみで persona-fit を測り、Big-Five claim を諦める
.steering/20260430-m9-eval-system/codex-review.md:1453:    33	### Burrows' Delta multi-language strategy 詳細
.steering/20260430-m9-eval-system/codex-review.md:1455:    35	- **暫定方針** (DB10 で確定):
.steering/20260430-m9-eval-system/codex-review.md:1458:    38	  - cross-language Burrows' Delta は使わない
.steering/20260430-m9-eval-system/codex-review.md:1486:    66	- **issue**: DB10 で 100/persona seed → 300 acceptance → 1000 publication staging を確定
.steering/20260430-m9-eval-system/codex-review.md:1507:    87	- **観測点**: M9-eval-system Tier B 実装完了直後の 2-3 run で plateau curve を観察
.steering/20260430-m9-eval-system/codex-review.md:1509:    89	### Tier B sub-metric 3 個の選定妥当性
.steering/20260430-m9-eval-system/codex-review.md:1510:    90	- DB9 で `vendi_score` / `big5_stability_icc` / `burrows_delta_to_reference` を選定
.steering/20260430-m9-eval-system/codex-review.md:1512:    92	- **再評価条件**: M9-eval-system Tier B 実装完了後の golden baseline 採取で discriminative 確認、
.steering/20260430-m9-eval-system/codex-review.md:1520:   100	| Burrows multi-lang | dialog 言語混在運用 | M9-eval-system reference corpus |
.steering/20260430-m9-eval-system/codex-review.md:1526:   106	| N=3 plateau curve | Tier B 実装完了 | M9-eval-system Tier B 完了直後 |
.steering/20260430-m9-eval-system/codex-review.md:1527:   107	| Tier B sub-metric 3 | golden baseline 採取 | M9-eval-system 終盤 |
.steering/20260430-m9-eval-system/codex-review.md:1534:     5	M9-B の J 軸 (思想家らしさの評価系 framework) の ADR (DB10) を起草する前に、
.steering/20260430-m9-eval-system/codex-review.md:1735:   206	### Stylometry / Burrows' Delta (arXiv:2507.00838 2025; arXiv:2408.08946 2024)
.steering/20260430-m9-eval-system/codex-review.md:1737:   208	- **Scoring**: Burrows' Delta = z-scored function-word frequency の Manhattan distance
.steering/20260430-m9-eval-system/codex-review.md:1751:   222	- **Scoring**: Cronbach's α (≥0.7)、ICC (≥0.75)、test-retest r
.steering/20260430-m9-eval-system/codex-review.md:1775:   246	### Vendi Score (Friedman & Dieng, TMLR 2023, arXiv:2210.02410)
.steering/20260430-m9-eval-system/codex-review.md:1811:   282	| **F5 Cognitive trait** | Big Five (IPIP-NEO + LIWC-22 cross-validation) | Stylometry (Burrows' Delta to thinker reference) |
.steering/20260430-m9-eval-system/codex-review.md:1812:   283	| **F6 Diversity** | Vendi Score (semantic kernel) | MATTR (lexical streaming) |
.steering/20260430-m9-eval-system/codex-review.md:1820:   291	- `Burrows' Delta` to thinker reference corpus (function-word vector、2ms)
.steering/20260430-m9-eval-system/codex-review.md:1828:   299	### Tier B: per-100-turn (medium)
.steering/20260430-m9-eval-system/codex-review.md:1830:   301	- `Vendi Score` rolling 200-turn window (50-80ms when window slides、stride=1 で <1ms/turn amortized)
.steering/20260430-m9-eval-system/codex-review.md:1831:   302	- `personality stability across mode` (Cronbach's α / ICC)
.steering/20260430-m9-eval-system/codex-review.md:1855:   321	- Vendi Score 解釈: persona の「思考の幅」次第で適正値が異なる
.steering/20260430-m9-eval-system/codex-review.md:1886:   352	- DB10 (J 軸 ADR) は「Tier A-D の階層構造」を採用、「single thinker-likeness score」は棄却
.steering/20260430-m9-eval-system/codex-review.md:1916:   382	- [Vendi Score arXiv:2210.02410](https://arxiv.org/abs/2210.02410)
.steering/20260430-m9-eval-system/codex-review.md:1930:The local evidence shows several design assertions are load-bearing: the grep gate is only string-based, bootstrap CI is currently described as plain NumPy resampling, and “frequently” for ICC fallback is not operationalized. I’m checking the repo shape now so the recommendations fit actual paths instead of being abstract.
.steering/20260430-m9-eval-system/codex-review.md:3381:web search: intraclass correlation coefficient ICC interpretation 0.6 0.75 reliability Koo Li 2016 guidelines
.steering/20260430-m9-eval-system/codex-review.md:3383:web search: Burrows Delta stylometry minimum text length number of words function words z scores corpus size stable
.steering/20260430-m9-eval-system/codex-review.md:3393:web search: Vendi Score sample diversity effective number samples kernel eigenvalues TMLR 2023 formula
.steering/20260430-m9-eval-system/codex-review.md:3768:- **Finding**: The design says `connect_training_view()` is the only training entry, but the current training export path already reads sqlite directly and is documented as consumed by M9 LoRA. Grep for `metrics.` misses quoted SQL, dynamic SQL, direct DuckDB connections, `read_parquet("...metrics...")`, and future Rust/Go tooling.
.steering/20260430-m9-eval-system/codex-review.md:3770:- **Recommendation**: Add a behavioral CI test over every training egress command/API with sentinel `metrics` rows and assert no metric fields/values leave the process. `connect_training_view()` should return raw rows or a constrained relation, not an unrestricted DuckDB connection. If arbitrary SQL is needed, export a raw-only snapshot for training.
.steering/20260430-m9-eval-system/codex-review.md:3771:- **Severity rationale**: HIGH because contamination prevention is DB5’s core contract; implementing the wrong guard now creates later baseline/training rework.
.steering/20260430-m9-eval-system/codex-review.md:3774:- **Finding**: `bootstrap_ci.py` is specified as NumPy resampling, but dialog turns are autoregressive and Tier B units are per-100-turn/window, not iid rows.
.steering/20260430-m9-eval-system/codex-review.md:3776:- **Recommendation**: Specify hierarchical bootstrap: resample runs as clusters, then circular/stationary blocks within each 500-turn run. Choose block length via pilot/autocorrelation or sensitivity grid, and report Tier B CI as based on only 25 windows/persona unless widened.
.steering/20260430-m9-eval-system/codex-review.md:3777:- **Severity rationale**: HIGH because DB9 drift/adoption decisions become overconfident under iid resampling.
.steering/20260430-m9-eval-system/codex-review.md:3780:- **Finding**: The table runs P3 golden capture before P3b ratio tuning, so any ratio change forces a 7500-turn rerun. Also, 50 turns cannot evaluate Vendi if the expected window is 200 turns.
.steering/20260430-m9-eval-system/codex-review.md:3781:- **Evidence**: [design.md:19](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/design.md:19>), [design.md:20](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/design.md:20>), [design.md:118](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/design.md:118>), [research-evaluation-metrics.md:301](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md:301>). Vendi is kernel/eigenvalue based over the sample ([OpenReview](https://openreview.net/forum?id=g97OHbQyk1)).
.steering/20260430-m9-eval-system/codex-review.md:3791:### HIGH-5: Burrows Delta is specified as the wrong metric
.steering/20260430-m9-eval-system/codex-review.md:3792:- **Finding**: `burrows.py` is described as “function-word vector cosine,” but the research doc defines Burrows Delta as distance over z-scored function-word frequencies.
.steering/20260430-m9-eval-system/codex-review.md:3794:- **Recommendation**: Implement actual Burrows Delta, or rename the quorum submetric to Cosine Delta and update DB9 wording, thresholds, and tests.
.steering/20260430-m9-eval-system/codex-review.md:3798:- **Finding**: “ICC < 0.6 が頻発” has no denominator. LLM survey responses are known to show social desirability artifacts.
.steering/20260430-m9-eval-system/codex-review.md:3799:- **Evidence**: [design.md:91](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/design.md:91>), [design.md:419](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/design.md:419>); Salecha et al. report LLM social desirability bias in Big Five surveys ([arXiv](https://arxiv.org/abs/2405.06058)); Koo/Li-style ICC interpretation treats 0.5-0.75 as moderate ([effectsize docs](https://easystats.github.io/effectsize/reference/interpret_icc.html)).
.steering/20260430-m9-eval-system/codex-review.md:3800:- **Recommendation**: Define “frequent” as e.g. ≥2/3 personas with ICC point <0.6 or lower CI <0.5 after golden baseline. Add acquiescence/straight-line checks, balanced/reverse items, and a base-model/persona-prompt control.
.steering/20260430-m9-eval-system/codex-review.md:3813:- **Severity rationale**: MEDIUM because Tier C is not the primary DB9 gate, but race semantics should be recorded.
.steering/20260430-m9-eval-system/codex-review.md:3827:### MEDIUM-6: 50K Burrows token floor needs corpus-QC semantics
.steering/20260430-m9-eval-system/codex-review.md:3865:- **Finding**: The design says `connect_training_view()` is the only training entry, but the current training export path already reads sqlite directly and is documented as consumed by M9 LoRA. Grep for `metrics.` misses quoted SQL, dynamic SQL, direct DuckDB connections, `read_parquet("...metrics...")`, and future Rust/Go tooling.
.steering/20260430-m9-eval-system/codex-review.md:3867:- **Recommendation**: Add a behavioral CI test over every training egress command/API with sentinel `metrics` rows and assert no metric fields/values leave the process. `connect_training_view()` should return raw rows or a constrained relation, not an unrestricted DuckDB connection. If arbitrary SQL is needed, export a raw-only snapshot for training.
.steering/20260430-m9-eval-system/codex-review.md:3868:- **Severity rationale**: HIGH because contamination prevention is DB5’s core contract; implementing the wrong guard now creates later baseline/training rework.
.steering/20260430-m9-eval-system/codex-review.md:3871:- **Finding**: `bootstrap_ci.py` is specified as NumPy resampling, but dialog turns are autoregressive and Tier B units are per-100-turn/window, not iid rows.
.steering/20260430-m9-eval-system/codex-review.md:3873:- **Recommendation**: Specify hierarchical bootstrap: resample runs as clusters, then circular/stationary blocks within each 500-turn run. Choose block length via pilot/autocorrelation or sensitivity grid, and report Tier B CI as based on only 25 windows/persona unless widened.
.steering/20260430-m9-eval-system/codex-review.md:3874:- **Severity rationale**: HIGH because DB9 drift/adoption decisions become overconfident under iid resampling.
.steering/20260430-m9-eval-system/codex-review.md:3877:- **Finding**: The table runs P3 golden capture before P3b ratio tuning, so any ratio change forces a 7500-turn rerun. Also, 50 turns cannot evaluate Vendi if the expected window is 200 turns.
.steering/20260430-m9-eval-system/codex-review.md:3878:- **Evidence**: [design.md:19](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/design.md:19>), [design.md:20](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/design.md:20>), [design.md:118](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/design.md:118>), [research-evaluation-metrics.md:301](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md:301>). Vendi is kernel/eigenvalue based over the sample ([OpenReview](https://openreview.net/forum?id=g97OHbQyk1)).
.steering/20260430-m9-eval-system/codex-review.md:3888:### HIGH-5: Burrows Delta is specified as the wrong metric
.steering/20260430-m9-eval-system/codex-review.md:3889:- **Finding**: `burrows.py` is described as “function-word vector cosine,” but the research doc defines Burrows Delta as distance over z-scored function-word frequencies.
.steering/20260430-m9-eval-system/codex-review.md:3891:- **Recommendation**: Implement actual Burrows Delta, or rename the quorum submetric to Cosine Delta and update DB9 wording, thresholds, and tests.
.steering/20260430-m9-eval-system/codex-review.md:3895:- **Finding**: “ICC < 0.6 が頻発” has no denominator. LLM survey responses are known to show social desirability artifacts.
.steering/20260430-m9-eval-system/codex-review.md:3896:- **Evidence**: [design.md:91](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/design.md:91>), [design.md:419](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/design.md:419>); Salecha et al. report LLM social desirability bias in Big Five surveys ([arXiv](https://arxiv.org/abs/2405.06058)); Koo/Li-style ICC interpretation treats 0.5-0.75 as moderate ([effectsize docs](https://easystats.github.io/effectsize/reference/interpret_icc.html)).
.steering/20260430-m9-eval-system/codex-review.md:3897:- **Recommendation**: Define “frequent” as e.g. ≥2/3 personas with ICC point <0.6 or lower CI <0.5 after golden baseline. Add acquiescence/straight-line checks, balanced/reverse items, and a base-model/persona-prompt control.
.steering/20260430-m9-eval-system/codex-review.md:3910:- **Severity rationale**: MEDIUM because Tier C is not the primary DB9 gate, but race semantics should be recorded.
.steering/20260430-m9-eval-system/codex-review.md:3924:### MEDIUM-6: 50K Burrows token floor needs corpus-QC semantics
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:1:# P4a Tier B — design v2 (/reimagine 後、psychometric-rigor-first 起点)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:4:> infrastructure-reuse + minimum-cost を起点にした (Mini-IPIP-20、cluster_only
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:8:> Refs: Codex HIGH-3 (Vendi 200-turn 最小)、Codex HIGH-2 (cluster + block hierarchical
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:11:> (ICC notation)。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:20:| 失敗モード | psychometric weakness (mini-20 reliability、cluster_only over-coverage) を見逃す | infrastructure complexity 増・工数膨張 |
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:24:`tier_b/` 3 module を提供し、DB9 quorum (Vendi / Big5 ICC / Burrows Δ) を稼働
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:25:させる。Tier B が offensive gate の唯一の arbiter。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:29:### Q1. Vendi Score kernel
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:33:- **window 100 → 200 に拡大**: Codex HIGH-3 が「Vendi は 200-turn 最小」を
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:43:  bootstrap も併用 (cluster_only ではなく `cluster + block`)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:45:**v2 が v1 を破壊する点**: window=100 cluster_only mode を再考。HIGH-3 を
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:65:### Q3. Big5 ICC formula
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:67:**v2**: ICC(A,1) absolute agreement single rater (McGraw & Wong 1996 notation
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:68:= Shrout & Fleiss 1979 ICC(2,1) absolute agreement) + ICC(2,k) consistency
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:71:- **rationale 切り替え**: v1 は ICC(2,k) consistency primary。だが LoRA
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:75:- ICC(A,1): 単一 run の reliability、5 run でも単一 score を扱う想定
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:76:- ICC(2,k) consistency: diagnostic for cross-check
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:77:- ME-1 cutoff (ICC<0.6 / lower CI<0.5) は absolute agreement 文脈でも適用可、
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:79:  consistency ICC が中心)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:87:hierarchical bootstrap (cluster_only ではない)。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:89:- v1 の cluster_only は per-window autocorrelation を完全に放棄。これは
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:90:  「window 内 sample 順序に意味がない」場合に正当だが、Vendi は kernel
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:94:  cluster_only=False, auto_block=True)` を採用 — PR #146 の `auto_block`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:99:**v2 が v1 を破壊する点**: cluster_only は P5 hardening で実装したが
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:100:**Tier B の使用文脈には not necessarily right fit**。auto_block が prior art
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:105:**v2 (確定、v1 と同)**: DB10 Option D。Tier B では LIWC alternative 新規導入
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:108:ここは v1 と一致。/reimagine も DB10 を破棄する根拠を見出さない。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:116:class VendiResult:
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:144:class Big5ICCResult:
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:145:    icc_point: float              # ICC(A,1) absolute agreement (v2)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:148:    icc_2k_consistency: float     # diagnostic (v2): consistency ICC(2,k)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:150:    fallback_fire: bool           # ICC < 0.6 OR lower CI < 0.5
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:151:    formula: str                  # "ICC(A,1) absolute agreement, McGraw-Wong 1996"
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:157:`metrics.tier_b` table column 流用は v1 と同じ。v2 では `metric_name` に追加:
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:159:- `tier_b.vendi_spectrum_entropy` (内部診断)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:160:- `tier_b.cronbach_alpha_extraversion` ... 5 行 (per dimension)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:161:- `tier_b.big5_icc_2k_consistency_diagnostic`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:174:  ICC が変化することを確認 (consistency なら不変、agreement なら変化)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:180:| 全体 | **~10-12h** (v2 は 50 items + 200 window + auto_block で +25-50%) |
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:185:- 得るもの: psychometric reliability up (α 0.6-0.7 → 0.8+)、Vendi spectrum
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:186:  stability up、ICC construct validity 改善、auto_block で bootstrap CI 妥当性 up
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:194:- **ICC formula 切り替えで ME-1 threshold の妥当性が揺らぐ**: Codex に
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:196:- **auto_block の per-cluster cap が cluster_only より bootstrap CI が
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:205:- **cluster_only mode 実装済**: PR #146 の労力を活かしたい
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:211:- Vendi: window=100 維持 (design-final 整合) + hybrid kernel (semantic+lexical) 採用
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:213:- ICC: ICC(2,k) consistency primary 維持 + ICC(A,1) absolute agreement diagnostic
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md:215:- bootstrap: cluster_only primary + auto_block diagnostic を JSON 出力併載
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:1:# P4a Tier B — design comparison (v1 vs v2 → hybrid v3 候補)
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:11:### Q1. Vendi Score kernel
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:34:**v3 selection**: IPIP-50。理由: psychometric reliability (α 0.8+) は ME-1
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:35:fallback 判定 (ICC<0.6) の信頼性に直結。call budget +150% は **eval-only**
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:42:### Q3. Big5 ICC formula
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:46:| primary | ICC(2,k) consistency average | ICC(A,1) absolute agreement single | **ICC(2,k) consistency primary + ICC(A,1) absolute agreement diagnostic** |
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:47:| diagnostic | ICC(3,1) | ICC(2,k) consistency | ICC(A,1) + ICC(3,1) (両 surfaced) |
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:48:| ME-1 threshold | 0.6 / 0.5 そのまま | 切替で再評価必要 | 0.6 / 0.5 は ICC(2,k) primary に維持、ICC(A,1) は diagnostic threshold 別途 |
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:50:**v3 selection**: 両 surfaced。primary は v1 (ICC(2,k) consistency、ME-1 threshold
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:51:互換性)、diagnostic に v2 (ICC(A,1) absolute agreement) を追加。理由: drift
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:53:ME-1 threshold 0.6 は consistency ICC を念頭に Koo-Li 2016 から得たもので、
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:57:**ADR 候補**: ME-10 として「Big5 ICC は consistency primary + agreement diagnostic
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:58:両報告」を起票。Codex に「ICC(A,1) を primary にすべき」と明確に指摘されたら
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:67:| bootstrap | `cluster_only=True` | `cluster_only=False, auto_block=True` | **cluster_only primary + auto_block diagnostic 併載** |
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:69:**v3 selection**: cluster_only primary を維持 (PR #146 effective sample size 25
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:70:framing は Codex HIGH-2 で承諾済)。auto_block diagnostic を JSON 出力併載で
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:73:**ADR 候補**: ME-11 として「Tier B bootstrap は cluster_only primary、auto_block
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:80:| DB10 Option D 通り全廃 | DB10 Option D 通り全廃 | **DB10 Option D 通り全廃 (一致)** |
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:82:差なし。Tier B 全 module 冒頭 docstring に honest framing 明示。
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:86:**Tier B v3 = window 100 + hybrid Vendi kernel (semantic 0.7 + lexical 5-gram 0.3)
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:87:+ IPIP-50 (Goldberg 1992、Murakami 日本語版) + Big5 ICC は consistency ICC(2,k)
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:88:primary + absolute agreement ICC(A,1) diagnostic 両報告 + bootstrap cluster_only
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:89:primary + auto_block diagnostic 併載 + LIWC 全廃 (DB10 Option D)**。工数推定
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:96:| Q1 Vendi kernel | ✗ semantic single | ✓ hybrid (v3 と同) | ✓ |
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:99:| Q3 ICC primary | ✓ ICC(2,k) consistency (v3 と同) | ✗ ICC(A,1) は threshold 揺らぎ | ✓ |
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:100:| Q3 ICC diagnostic | ✗ ICC(3,1) のみ | ✓ ICC(A,1) も含める (v3 と同) | ✓ |
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:101:| Q4 bootstrap | ✓ cluster_only primary (v3 と同) | ✗ block primary は HIGH-2 承諾 framing 矛盾 | ✓ |
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:102:| Q4 auto_block | ✗ 採用せず | ✓ 採用 (v3 と同 diagnostic) | ✓ |
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:111:1. **Vendi hybrid kernel の重み 0.7/0.3 の妥当性**: prior art (Friedman & Dieng 2023
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:113:2. **window 100 turn が Vendi spectrum stability に sufficient か**: HIGH-3 が
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:116:3. **IPIP-50 vs Mini-IPIP-20 の reliability gap が ICC fallback 判定に与える影響**:
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:117:   Mini-20 で α 0.6-0.7 → ICC ceiling も同程度 → ME-1 threshold 0.6 触れる
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:121:5. **ICC(2,k) consistency と ICC(A,1) absolute agreement の併報告が drift
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:122:   detection 文脈で適切か**: どちらを ME-1 trigger に使うべきか
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:123:6. **per-window n=100 turn が ICC 計算に sufficient か**: rule-of-thumb (k items
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:125:7. **cluster_only と auto_block の両報告が JSON consumer 側で混乱を招かないか**:
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:133:- ICC primary/diagnostic 切替の最終判定 (Codex 推奨次第)
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md:134:- Vendi hybrid kernel weight (0.7/0.3 vs prior-art alternative)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:1:# P4a Tier B — design v1 (Plan mode 初回案)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:4:> art / ICC stability 起点) から再生成され、design-comparison.md で hybrid v3 を
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:8:> (`m9-eval-system-p4a-tier-glistening-tulip.md`)、ADR DB9/DB10/DB11 (M9-B)、
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:9:> ME-1/ME-4/ME-5 (M9-eval)、Codex HIGH-2/HIGH-5 (P5)、PR #146 P5 hardening
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:10:> (`hierarchical_bootstrap_ci(cluster_only=True)`)。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:14:`src/erre_sandbox/evidence/tier_b/` をゼロから起草し、LoRA 採用判定 (DB9 quorum)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:15:の 3 sub-metric (Vendi Score / Big5 stability ICC / Burrows Δ) のうち、Tier B
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:16:新規 2 件 (Vendi / Big5 ICC) と IPIP-NEO 質問紙 administering helper を提供する。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:17:Burrows Δ は `tier_a/burrows.py` 既存。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:21:- adoption: 3 sub-metric の 2-of-3 が `BootstrapResult` の CI で baseline positive 方向
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:26:Tier B は **offensive gate の唯一の arbiter** — Tier A=floor diagnostic、
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:27:Tier C=defensive canary なので、Tier B 不在の限り LoRA 採用判定は機能不全。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:31:### Q1. Vendi Score kernel
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:65:### Q3. Big5 ICC formula
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:67:**v1**: ICC(2,k) random raters average + ICC(3,1) fixed raters single (diagnostic)。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:69:- ICC(2,k): primary metric。run を rater (random sample) 扱い、5 run の平均
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:71:- ICC(3,1): diagnostic only。fixed run 単一 score の reliability。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:73:- ME-1 cutoff: ICC point < 0.6 OR lower CI < 0.5 が ≥2/3 personas → fallback fire
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:74:- 1.0 convergence sanity: 同一回答列 → ICC = 1.0 (within float tolerance)。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:76:- bootstrap CI: per-100-turn windowed Big5 score を `cluster_only=True` で resample
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:79:**Codex に問う**: ICC(2,k) vs ICC(3,1) vs ICC(2,1) の選択を LLM personality
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:83:### Q4. per-100-turn windowing × cluster_only bootstrap
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:85:**v1 (確定)**: 5 runs × 5 windows = 25 cluster/persona、`cluster_only=True`。
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:87:- PR #146 で `hierarchical_bootstrap_ci(values_per_cluster, *, cluster_only=True,
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:88:  n_resamples=2000, ci=0.95, seed=0) -> BootstrapResult` 完成、流用
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:91:- `BootstrapResult.method == "hierarchical-cluster-only"` を出力 JSON で表示
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:95:**v1 (確定)**: DB10 Option D 通り LIWC 全廃。Tier B では新規 LIWC alternative を
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:99:  しない、ME-1 既に明示)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:100:- Big5 claim は Tier B IPIP-NEO self-report のみ
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:101:- docstring 文言 (Tier B 全 module 冒頭): 「Big5 self-report via IPIP-NEO; not LIWC,
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:103:  only (ME-1 / DB10).」
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:107:### `src/erre_sandbox/evidence/tier_b/vendi.py`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:110:"""Vendi Score (Friedman & Dieng 2023) — diversity metric for Tier B DB9 quorum.
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:117:DB9 sub-metric: vendi_score. Persona-conditional: bootstrap CI per persona
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:119::func:`hierarchical_bootstrap_ci(cluster_only=True)`.
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:121:LIWC alternative honest framing (DB10 Option D): this module makes no Big5
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:130:VendiKernel = Callable[[Sequence[str]], np.ndarray]
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:135:class VendiResult:
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:136:    """Vendi Score for one window."""
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:145:    kernel: VendiKernel | None = None,
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:147:) -> VendiResult:
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:148:    """Compute Vendi Score for a window of utterances.
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:157:        :class:`VendiResult`. Empty input → score=0, n=0.
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:162:`BootstrapResult` via `hierarchical_bootstrap_ci(cluster_only=True)`.
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:164:### `src/erre_sandbox/evidence/tier_b/ipip_neo.py`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:172:LIWC alternative honest framing (DB10): Big5 self-report only — no claim that
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:215:Diagnostic (常時計測、ME-1 要件):
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:229:### `src/erre_sandbox/evidence/tier_b/big5_icc.py`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:232:"""Big5 stability ICC across runs / windows for Tier B DB9 quorum.
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:234:Sub-metric: big5_stability_icc. ICC(2,k) random-raters-average is the primary;
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:235:ICC(3,1) is reported as diagnostic. Identical responses → ICC=1.0 (sanity).
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:237:ME-1 fallback trigger: point ICC < 0.6 OR lower CI < 0.5 in ≥2/3 personas →
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:240:Bootstrap CI uses :func:`hierarchical_bootstrap_ci(cluster_only=True)` over
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:249:class Big5ICCResult:
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:250:    icc_point: float              # ICC(2,k) point estimate
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:253:    icc_31_diagnostic: float      # ICC(3,1) for cross-check
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:255:    fallback_fire: bool           # ICC < 0.6 OR lower CI < 0.5
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:256:    formula: str                  # "ICC(2,k) random-raters-average"
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:264:) -> Big5ICCResult: ...
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:269:`metrics.tier_b` table (already created by `bootstrap_schema()`) の column 流用:
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:272:run_id TEXT, persona_id TEXT, turn_idx INTEGER, metric_name TEXT,
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:276:Tier B では **`turn_idx` を `window_index` (0..24) として再利用** (column rename
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:279:- `tier_b.vendi_score`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:280:- `tier_b.big5_extraversion` ... `tier_b.big5_openness` (5 行)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:281:- `tier_b.big5_stability_icc`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:282:- `tier_b.big5_icc_31_diagnostic`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:283:- `tier_b.acquiescence_index`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:284:- `tier_b.straight_line_runs`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:285:- `tier_b.reverse_keyed_agreement`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:294:def fetch_tier_b_metric(
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:301:    """Return [(window_index, metric_value, notes), ...] for Tier B."""
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:303:        "SELECT turn_idx, metric_value, notes"
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:304:        f" FROM {METRICS_SCHEMA}.tier_b"
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:306:        " ORDER BY turn_idx",
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:311:DB5/DB6/DB11 contract: Tier B 計算は eval-side のみ、`metrics.tier_b` には
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:312:`connect_training_view()` から到達不可能 (training-view は `raw_dialog.dialog`
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:317:### `tests/test_evidence/test_tier_b/test_vendi.py` (5 件)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:323:5. `test_compute_vendi_per_persona_bootstrap_cluster_only` — integration with
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:324:   `hierarchical_bootstrap_ci(cluster_only=True)`、25 cluster
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:326:### `tests/test_evidence/test_tier_b/test_ipip_neo.py` (5 件)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:334:### `tests/test_evidence/test_tier_b/test_big5_icc.py` (5 件)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:340:5. `test_compute_big5_icc_bootstrap_cluster_only_seed_stable` — seed determinism
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:344:1. `test_fetch_tier_b_metric_round_trip` — INSERT → SELECT
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:345:2. `test_tier_b_isolation_from_training_view` — `connect_training_view()` から
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:346:   `metrics.tier_b` 不可視を sentinel 経由で確認
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:352:| ADR | 制約 | Tier B 実装の対応 |
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:354:| DB5/DB6 | raw_dialog vs metrics 物理分離、`evaluation_epoch=false` only training | Tier B は `metrics.tier_b` のみ。raw_dialog 不変。docstring 明示 |
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:355:| DB9 | 3 sub-metric 2-of-3 quorum、bootstrap CI で baseline 方向判定 | vendi.py + big5_icc.py で 2/3 sub-metric 提供、Burrows は tier_a 流用 |
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:356:| DB10 Option D | LIWC 全廃、proxy framing 必須、Big5 は IPIP-NEO self-report only | Tier B 全 module 冒頭 docstring に honest framing 明示 |
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:357:| DB11 (PR #145) | Tier B 計算 path が training に漏れない構造 | DB5 で構造的担保済、docstring/comment で明示 (assert 追加不要) |
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:358:| ME-1 | IPIP-NEO fallback ICC<0.6 OR lower CI<0.5 が ≥2/3 persona | `Big5ICCResult.fallback_fire` field、acquiescence/straight-line/reverse-keyed 4 種 diagnostic |
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:360:| ME-5 | blake2b uint64 seed、Mac/G-GEAR 同値性 | Vendi/ICC bootstrap で `seed` 引数を頭から伝播 |
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:364:- Vendi kernel 詳細: 純 cosine vs Gram-matrix normalization vs spectrum smoothing
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:366:- ICC formula: ICC(2,k) primary 選択の正当性 (LLM personality stability prior art)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:367:- per-window n=100 turn が ICC 計算に sufficient か (rule-of-thumb / power)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:368:- Vendi/IPIP-NEO/Big5 ICC 結果間の cross-validation (相関 / 直交性)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:375:- Burrows reference corpus 整備 (Tier A 既存範囲、blockers.md defer)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:377:- DB11 contamination assert 実装 (M9-C-adopt、現状 docstring 明示のみ)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:378:- Empath/spaCy/自作 LIWC alternative の新規導入 (DB10 Option D 確定済)
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md:379:- Tier B 3 metric を分割 PR で incremental merge (DB9 quorum 機能不全)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:1:# Decisions — M9-B LoRA Execution Plan (10 ADR: DB1-DB10)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:80:    - plateau: prompting + persona YAML 拡張のみで Tier B metric が **2 連続 run で
.steering/20260430-m9-b-lora-execution-plan/decisions.md:81:      <5% improvement** (operational definition は DB9 quorum logic に統合)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:101:## DB5 — Parquet schema: **raw + sidecar 物理分離** (HIGH-4 反映)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:106:  - **metrics/**: sidecar evaluation metric table。`run_id + persona_id + turn_idx` で
.steering/20260430-m9-b-lora-execution-plan/decisions.md:132:    - **Tier B**: per 100 turns (Vendi / IPIP-NEO / Big5 ICC)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:191:## DB9 — Drift gate: composite + bootstrap CI + 2-of-3 quorum (HIGH-2 反映)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:194:  - **Primary composite per persona**: 各 persona の Tier B から 3 sub-metric:
.steering/20260430-m9-b-lora-execution-plan/decisions.md:208:  - codex HIGH-2: 「5%」固定 + Tier B noise → false rollback / metric gaming リスク
.steering/20260430-m9-b-lora-execution-plan/decisions.md:223:## DB10 — J 評価系 framework: 4-tier + persona-conditional + multi-channel (specs only in M9-B)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:228:    - Tier A: per-turn cheap (LIWC/Empath / Burrows Delta / MATTR / semantic novelty / NLI)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:229:    - Tier B: per-100-turn (Vendi Score / IPIP-NEO / Big5 stability ICC)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:274:## DB11 — Cognition deepening contamination prevention (PR #144 Codex HIGH-3 反映、addendum 2026-05-08)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:308:- DB5 (Parquet schema 物理分離) に `individual_layer_enabled` field を 1 つ追加 (additive)

exec
/bin/zsh -lc "sed -n '1,220p' .steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# P4a Tier B — design v1 (Plan mode 初回案)

> 本 v1 は意図的に /reimagine で破棄される対象。次の v2 が別の出発点 (例: prior
> art / ICC stability 起点) から再生成され、design-comparison.md で hybrid v3 を
> 検討する。HIGH 検出は Codex review に委ねる。
>
> Refs: launch prompt (`mac-p4a-tier-b-launch-prompt.md`)、plan file
> (`m9-eval-system-p4a-tier-glistening-tulip.md`)、ADR DB9/DB10/DB11 (M9-B)、
> ME-1/ME-4/ME-5 (M9-eval)、Codex HIGH-2/HIGH-5 (P5)、PR #146 P5 hardening
> (`hierarchical_bootstrap_ci(cluster_only=True)`)。

## 1. Mission

`src/erre_sandbox/evidence/tier_b/` をゼロから起草し、LoRA 採用判定 (DB9 quorum)
の 3 sub-metric (Vendi Score / Big5 stability ICC / Burrows Δ) のうち、Tier B
新規 2 件 (Vendi / Big5 ICC) と IPIP-NEO 質問紙 administering helper を提供する。
Burrows Δ は `tier_a/burrows.py` 既存。

quorum role:

- adoption: 3 sub-metric の 2-of-3 が `BootstrapResult` の CI で baseline positive 方向
- rollback: 2-of-3 が baseline negative 方向
- single regression は warning のみ
- defensive canary (Tier C: self_rep / cross_echo) は本 PR scope 外

Tier B は **offensive gate の唯一の arbiter** — Tier A=floor diagnostic、
Tier C=defensive canary なので、Tier B 不在の限り LoRA 採用判定は機能不全。

## 2. The 5 question answers (v1 commitment)

### Q1. Vendi Score kernel

**v1**: semantic kernel (sentence-transformers MPNet
`paraphrase-multilingual-mpnet-base-v2`)。

- 算出: `vendi.score(utterances, k=mpnet_cosine_kernel)` 同様の
  custom path、または `vendi-score` package の cosine similarity matrix path
- multilingual 必要 (kant=ja/en mixed, rikyu=ja, nietzsche=ja/en mixed)
- `tier_a/novelty.py` で MPNet encoder lazy-load 既に存在 → 流用 (追加 dep なし)
- sanity: 直交 one-hot input → score = N (within float tolerance)。P5 残課題 close
- trade-off: per-window 100 utterances → cosine matrix 100×100。25 windows × 3 persona
  × 5 run = 375 windows。MPNet inference を 100 utt/window で batch、CPU でも
  許容範囲 (~1s/window 想定、合計 6-10 min)

**棄却候補**: unigram count kernel — multilingual 弱い、長い utterance で
N-gram-overlap 過小評価、Codex prior art に正当化させる必要が高い

### Q2. IPIP-NEO 版

**v1**: Mini-IPIP-20 (Donnellan et al., 2006)。

- 20 items × 25 windows × 3 persona × 5 run = **7,500 LLM calls**
  (vs short-50: 18,750 / full-300: 112,500)
- agentic loop overhead 最小化、qwen3:8b deterministic temp=0
- 5-point Likert (1=strongly disagree ... 5=strongly agree)
- balanced reverse-keyed: ~50% items
- Big5 dimension: 4 items × 5 dimension (E/A/C/N/O)
- 日本語 prompt 整備 (Goldberg 1992 の英語原文 + 既存日本語訳との対照)。kant/rikyu
  /nietzsche persona は system prompt で persona-conditional 環境にする
- replay determinism test: temp=0 で identical input → identical output

**Codex に問う**: short-50 (Goldberg 1992) との reliability/validity trade-off、
日本語訳の cross-language validation literature

### Q3. Big5 ICC formula

**v1**: ICC(2,k) random raters average + ICC(3,1) fixed raters single (diagnostic)。

- ICC(2,k): primary metric。run を rater (random sample) 扱い、5 run の平均
  reliability。across-mode (peripatos/chashitsu/zazen) variability も run に吸収
- ICC(3,1): diagnostic only。fixed run 単一 score の reliability。
- 算出は `pingouin.intraclass_corr` か自前 ANOVA-based formula
- ME-1 cutoff: ICC point < 0.6 OR lower CI < 0.5 が ≥2/3 personas → fallback fire
- 1.0 convergence sanity: 同一回答列 → ICC = 1.0 (within float tolerance)。
  P5 残課題 close
- bootstrap CI: per-100-turn windowed Big5 score を `cluster_only=True` で resample
  (window が cluster、5 run × 5 window = 25 cluster)

**Codex に問う**: ICC(2,k) vs ICC(3,1) vs ICC(2,1) の選択を LLM personality
stability 文脈で正当化する prior art (2024-2026)、convergence threshold 0.6 の
empirical 妥当性

### Q4. per-100-turn windowing × cluster_only bootstrap

**v1 (確定)**: 5 runs × 5 windows = 25 cluster/persona、`cluster_only=True`。

- PR #146 で `hierarchical_bootstrap_ci(values_per_cluster, *, cluster_only=True,
  n_resamples=2000, ci=0.95, seed=0) -> BootstrapResult` 完成、流用
- effective sample size 25 framing は Codex HIGH-2 で既に承諾、PR description
  + docstring で明示
- `BootstrapResult.method == "hierarchical-cluster-only"` を出力 JSON で表示

### Q5. LIWC alternative honest framing

**v1 (確定)**: DB10 Option D 通り LIWC 全廃。Tier B では新規 LIWC alternative を
**導入しない**。

- Empath は `tier_a/empath_proxy.py` に既存 (psycholinguistic axis only、Big5 claim
  しない、ME-1 既に明示)
- Big5 claim は Tier B IPIP-NEO self-report のみ
- docstring 文言 (Tier B 全 module 冒頭): 「Big5 self-report via IPIP-NEO; not LIWC,
  not a Big5 claim from external lexicon. Tier A Empath is psycholinguistic axis
  only (ME-1 / DB10).」

## 3. API skeleton (signatures)

### `src/erre_sandbox/evidence/tier_b/vendi.py`

```python
"""Vendi Score (Friedman & Dieng 2023) — diversity metric for Tier B DB9 quorum.

Computes the exponential of Shannon entropy of the eigenvalue spectrum of the
similarity kernel matrix K, normalized so K_ii = 1. With the MPNet semantic
kernel this measures **semantic diversity**: identical utterances → score=1,
fully orthogonal one-hot → score=N.

DB9 sub-metric: vendi_score. Persona-conditional: bootstrap CI per persona
across 25 windows / persona (5 runs × 5 per-100-turn windows). Use with
:func:`hierarchical_bootstrap_ci(cluster_only=True)`.

LIWC alternative honest framing (DB10 Option D): this module makes no Big5
claim; Big5 self-report goes through ``ipip_neo.py`` + ``big5_icc.py``.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

VendiKernel = Callable[[Sequence[str]], np.ndarray]
"""Stub-friendly callable: return N×N similarity matrix in [0, 1]."""


@dataclass(frozen=True, slots=True)
class VendiResult:
    """Vendi Score for one window."""
    score: float           # exp(H(eigenvalues))
    n: int                 # window size (utterances)
    kernel: str            # "mpnet-cosine" | "unigram-count" | <stub>


def compute_vendi(
    utterances: Sequence[str],
    *,
    kernel: VendiKernel | None = None,
    kernel_name: str = "mpnet-cosine",
) -> VendiResult:
    """Compute Vendi Score for a window of utterances.

    Args:
        utterances: 1 window (typically 100 turns).
        kernel: Optional stub callable (utterances -> N×N similarity).
            Default is MPNet cosine via the lazy loader.
        kernel_name: Identifier surfaced in the result.

    Returns:
        :class:`VendiResult`. Empty input → score=0, n=0.
    """
```

Plus a per-persona aggregator that takes 25 windows and returns
`BootstrapResult` via `hierarchical_bootstrap_ci(cluster_only=True)`.

### `src/erre_sandbox/evidence/tier_b/ipip_neo.py`

```python
"""IPIP-NEO Mini-20 (Donnellan et al. 2006) administering helper.

Builds the prompt, parses persona LLM responses, returns Big5 score vector.
Deterministic under temperature=0 + same seed (replay determinism test).

LIWC alternative honest framing (DB10): Big5 self-report only — no claim that
this maps to LIWC categories or any external lexicon.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

PersonaResponder = Callable[[str], int]
"""Stub-friendly: take prompt, return Likert 1..5 integer."""


@dataclass(frozen=True, slots=True)
class Big5Scores:
    """Per-administration Big5 vector."""
    extraversion: float
    agreeableness: float
    conscientiousness: float
    neuroticism: float
    openness: float
    n_items: int  # 20 for Mini-IPIP, 50 for short, 300 for full
    version: str  # "mini-ipip-20" | "short-50" | "full-300"


def administer_ipip_neo(
    responder: PersonaResponder,
    *,
    version: str = "mini-ipip-20",
    language: str = "en",
) -> Big5Scores:
    """Administer the questionnaire and return Big5 scores.

    Args:
        responder: Callable taking item prompt → 1..5 integer.
            Tests pass a deterministic stub.
        version: "mini-ipip-20" | "short-50" | "full-300".
        language: "en" | "ja" — selects the prompt corpus.

    Returns:
        :class:`Big5Scores` averaged over the items per dimension after
        reverse-keying.
    """
```

Diagnostic (常時計測、ME-1 要件):

```python
@dataclass(frozen=True, slots=True)
class IPIPDiagnostic:
    """Quality-control side-channel — never used as Big5 itself."""

exec
/bin/zsh -lc "sed -n '221,430p' .steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
    acquiescence_index: float       # logit balance over Likert 1..5
    straight_line_runs: int         # max consecutive identical answers
    reverse_keyed_agreement: float  # corr between forward / reverse pairs


def compute_ipip_diagnostic(responses: Sequence[int]) -> IPIPDiagnostic: ...
```

### `src/erre_sandbox/evidence/tier_b/big5_icc.py`

```python
"""Big5 stability ICC across runs / windows for Tier B DB9 quorum.

Sub-metric: big5_stability_icc. ICC(2,k) random-raters-average is the primary;
ICC(3,1) is reported as diagnostic. Identical responses → ICC=1.0 (sanity).

ME-1 fallback trigger: point ICC < 0.6 OR lower CI < 0.5 in ≥2/3 personas →
emit re-open candidate to ``decisions.md``.

Bootstrap CI uses :func:`hierarchical_bootstrap_ci(cluster_only=True)` over
25 windows / persona (5 run × 5 per-100-turn window).
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Big5ICCResult:
    icc_point: float              # ICC(2,k) point estimate
    icc_lower_ci: float           # 95% bootstrap lower bound
    icc_upper_ci: float           # 95% bootstrap upper bound
    icc_31_diagnostic: float      # ICC(3,1) for cross-check
    n_windows: int                # cluster count (25 typical)
    fallback_fire: bool           # ICC < 0.6 OR lower CI < 0.5
    formula: str                  # "ICC(2,k) random-raters-average"


def compute_big5_icc(
    big5_per_window: Sequence[Big5Scores],
    *,
    seed: int = 0,
    n_resamples: int = 2000,
) -> Big5ICCResult: ...
```

## 4. Persistence model (eval_store.py 統合)

`metrics.tier_b` table (already created by `bootstrap_schema()`) の column 流用:

```
run_id TEXT, persona_id TEXT, turn_idx INTEGER, metric_name TEXT,
metric_value DOUBLE, notes TEXT
```

Tier B では **`turn_idx` を `window_index` (0..24) として再利用** (column rename
は破壊的、避ける)。`metric_name` の値を以下に固定:

- `tier_b.vendi_score`
- `tier_b.big5_extraversion` ... `tier_b.big5_openness` (5 行)
- `tier_b.big5_stability_icc`
- `tier_b.big5_icc_31_diagnostic`
- `tier_b.acquiescence_index`
- `tier_b.straight_line_runs`
- `tier_b.reverse_keyed_agreement`

`notes` には JSON で kernel_name / version / formula を埋める。

### eval_store.py への additive patch

新規 helper のみ追加 (既存 API 破壊しない):

```python
def fetch_tier_b_metric(
    view: AnalysisView,
    *,
    run_id: str,
    persona_id: str,
    metric_name: str,
) -> list[tuple[int, float, str | None]]:
    """Return [(window_index, metric_value, notes), ...] for Tier B."""
    return view.execute(
        "SELECT turn_idx, metric_value, notes"
        f" FROM {METRICS_SCHEMA}.tier_b"
        " WHERE run_id = ? AND persona_id = ? AND metric_name = ?"
        " ORDER BY turn_idx",
        (run_id, persona_id, metric_name),
    )
```

DB5/DB6/DB11 contract: Tier B 計算は eval-side のみ、`metrics.tier_b` には
`connect_training_view()` から到達不可能 (training-view は `raw_dialog.dialog`
projection のみ)。**追加 assert 不要、構造的に保証済**。docstring で明示。

## 5. Test plan (9-15 件)

### `tests/test_evidence/test_tier_b/test_vendi.py` (5 件)

1. `test_compute_vendi_orthogonal_one_hot_score_equals_n` — sanity (P5 残課題)
2. `test_compute_vendi_identical_utterances_score_equals_one` — degenerate
3. `test_compute_vendi_empty_input_returns_zero_n` — boundary
4. `test_compute_vendi_kernel_stub_round_trip` — stub 経由
5. `test_compute_vendi_per_persona_bootstrap_cluster_only` — integration with
   `hierarchical_bootstrap_ci(cluster_only=True)`、25 cluster

### `tests/test_evidence/test_tier_b/test_ipip_neo.py` (5 件)

1. `test_administer_ipip_neo_mini_20_replay_determinism` — replay (temp=0 stub)
2. `test_administer_ipip_neo_reverse_keyed_consistency` — reverse-keyed score
3. `test_compute_ipip_diagnostic_acquiescence_index_balanced` — balanced
4. `test_compute_ipip_diagnostic_straight_line_detection` — 10 連続同回答
5. `test_administer_ipip_neo_japanese_prompt_round_trip` — language="ja" stub

### `tests/test_evidence/test_tier_b/test_big5_icc.py` (5 件)

1. `test_compute_big5_icc_identical_windows_returns_one` — 1.0 (P5 残課題)
2. `test_compute_big5_icc_uncorrelated_windows_below_threshold` — synthetic <0.5
3. `test_compute_big5_icc_fallback_fire_threshold` — <0.6 OR lower CI <0.5
4. `test_compute_big5_icc_31_diagnostic_present` — diagnostic surfaced
5. `test_compute_big5_icc_bootstrap_cluster_only_seed_stable` — seed determinism

### `tests/test_evidence/test_eval_store.py` 追加 (1-2 件)

1. `test_fetch_tier_b_metric_round_trip` — INSERT → SELECT
2. `test_tier_b_isolation_from_training_view` — `connect_training_view()` から
   `metrics.tier_b` 不可視を sentinel 経由で確認

合計: 16 件 (上限内)。

## 6. ADR alignment (絶対遵守)

| ADR | 制約 | Tier B 実装の対応 |
|---|---|---|
| DB5/DB6 | raw_dialog vs metrics 物理分離、`evaluation_epoch=false` only training | Tier B は `metrics.tier_b` のみ。raw_dialog 不変。docstring 明示 |
| DB9 | 3 sub-metric 2-of-3 quorum、bootstrap CI で baseline 方向判定 | vendi.py + big5_icc.py で 2/3 sub-metric 提供、Burrows は tier_a 流用 |
| DB10 Option D | LIWC 全廃、proxy framing 必須、Big5 は IPIP-NEO self-report only | Tier B 全 module 冒頭 docstring に honest framing 明示 |
| DB11 (PR #145) | Tier B 計算 path が training に漏れない構造 | DB5 で構造的担保済、docstring/comment で明示 (assert 追加不要) |
| ME-1 | IPIP-NEO fallback ICC<0.6 OR lower CI<0.5 が ≥2/3 persona | `Big5ICCResult.fallback_fire` field、acquiescence/straight-line/reverse-keyed 4 種 diagnostic |
| ME-4 | ratio 200/300 の re-eval は P4 完了 trigger | P4a 完了 = partial update #4 trigger、PR description 明示 |
| ME-5 | blake2b uint64 seed、Mac/G-GEAR 同値性 | Vendi/ICC bootstrap で `seed` 引数を頭から伝播 |

## 7. v1 で意図的に未解決にしている点 (/reimagine + Codex で challenge)

- Vendi kernel 詳細: 純 cosine vs Gram-matrix normalization vs spectrum smoothing
- IPIP-NEO 日本語 prompt の cross-language validation literature
- ICC formula: ICC(2,k) primary 選択の正当性 (LLM personality stability prior art)
- per-window n=100 turn が ICC 計算に sufficient か (rule-of-thumb / power)
- Vendi/IPIP-NEO/Big5 ICC 結果間の cross-validation (相関 / 直交性)

## 8. Out of scope (この PR で触らない)

- LoRA training (M9-C-adopt 範囲)
- Tier C judge LLM (P6 範囲)
- G-GEAR golden baseline 採取 (P3 範囲、calibration 待ち)
- Burrows reference corpus 整備 (Tier A 既存範囲、blockers.md defer)
- persona refactor / philosopher_seed (M10-A、認知深化 PR #144)
- DB11 contamination assert 実装 (M9-C-adopt、現状 docstring 明示のみ)
- Empath/spaCy/自作 LIWC alternative の新規導入 (DB10 Option D 確定済)
- Tier B 3 metric を分割 PR で incremental merge (DB9 quorum 機能不全)

## 9. Effort estimate

| Sub-step | 推定 |
|---|---|
| design-v1.md (本書) | 30min ✓ |
| /reimagine v2 + comparison.md | 1h |
| Codex review prompt + execution + 反映 | 1.5h |
| design-final.md + decisions.md ADR 追記 | 30min |
| Implementation (3 file + tests + eval_store) | 3.5h |
| PR | 30min |
| **合計** | **~7.5-8h** (1-2 セッション) |

exec
/bin/zsh -lc "sed -n '1,220p' .steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,260p' .steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# P4a Tier B — design comparison (v1 vs v2 → hybrid v3 候補)

> v1 (`p4a-tier-b-design-v1.md`): infrastructure-first / minimum-cost
> v2 (`p4a-tier-b-design-v2.md`): psychometric-rigor-first / statistical-power
>
> 本書は両案を 5 question 軸で比較し、hybrid v3 を提示する。Codex review が
> 起爆。最終解は `p4a-tier-b-design-final.md` に記述。

## Question-by-question 比較

### Q1. Vendi Score kernel

| 軸 | v1 | v2 | hybrid v3 候補 |
|---|---|---|---|
| kernel | semantic MPNet (single) | semantic MPNet 0.7 + lexical 5-gram 0.3 | **hybrid kernel 採用 (v2)** |
| window size | 100 turn | 200 turn | **100 turn 維持 (v1、design-final 整合)** |
| sanity | direct one-hot ≈ N | lexical 成分で one-hot=N 担保 | hybrid のまま one-hot=N (lexical 成分で) |
| trade-off | 単純・低コスト、paraphrase 過敏 | spectrum stable、surface noise 緩和、window 数半減 | spectrum stable + window 数維持 |

**v3 selection**: kernel は v2 (hybrid)、window は v1 (100)。理由: window 200 化は
design-final.md (per-100-turn) を破壊する coast 高、hybrid kernel は per-window
内 spectrum stability を改善するので window 100 のままでも paraphrase 過敏問題
を緩和できる。

### Q2. IPIP-NEO 版

| 軸 | v1 | v2 | hybrid v3 候補 |
|---|---|---|---|
| 版 | Mini-IPIP-20 (Donnellan 2006) | IPIP-50 (Goldberg 1992) | **IPIP-50 採用 (v2)** (条件: 日本語 license clear) |
| call budget | 7,500 | 18,750 | 18,750 (G-GEAR overnight 並行で吸収) |
| α reliability | 0.6-0.7 marginal | 0.8+ stable | 0.8+ |
| 日本語訳 | 翻案要 (Mini-IPIP は日本語版確立薄) | Murakami 2002/2003 流用 | Murakami 2002/2003 (license 要確認) |

**v3 selection**: IPIP-50。理由: psychometric reliability (α 0.8+) は ME-1
fallback 判定 (ICC<0.6) の信頼性に直結。call budget +150% は **eval-only**
用途で問題にならない (live inference の話ではない)。

**defer 条件**: 日本語訳 license が clear できない場合は Mini-IPIP-20 fallback +
ADR で defer 理由明示。Codex prior art search で Murakami 2002/2003 公開状況
確認。

### Q3. Big5 ICC formula

| 軸 | v1 | v2 | hybrid v3 候補 |
|---|---|---|---|
| primary | ICC(2,k) consistency average | ICC(A,1) absolute agreement single | **ICC(2,k) consistency primary + ICC(A,1) absolute agreement diagnostic** |
| diagnostic | ICC(3,1) | ICC(2,k) consistency | ICC(A,1) + ICC(3,1) (両 surfaced) |
| ME-1 threshold | 0.6 / 0.5 そのまま | 切替で再評価必要 | 0.6 / 0.5 は ICC(2,k) primary に維持、ICC(A,1) は diagnostic threshold 別途 |

**v3 selection**: 両 surfaced。primary は v1 (ICC(2,k) consistency、ME-1 threshold
互換性)、diagnostic に v2 (ICC(A,1) absolute agreement) を追加。理由: drift
detection の意味論的に absolute agreement が筋という v2 の指摘は valid だが、
ME-1 threshold 0.6 は consistency ICC を念頭に Koo-Li 2016 から得たもので、
absolute agreement に流用すると threshold 妥当性が揺らぐ。両 surfaced で
construct validity と threshold 互換性の両立を狙う。

**ADR 候補**: ME-10 として「Big5 ICC は consistency primary + agreement diagnostic
両報告」を起票。Codex に「ICC(A,1) を primary にすべき」と明確に指摘されたら
v2 採用に切替。

### Q4. windowing × bootstrap

| 軸 | v1 | v2 | hybrid v3 候補 |
|---|---|---|---|
| window size | 100 turn | 200 turn | **100 turn (v1、design-final 整合)** |
| cluster 数 | 25 / persona | 12.5 / persona | 25 / persona |
| bootstrap | `cluster_only=True` | `cluster_only=False, auto_block=True` | **cluster_only primary + auto_block diagnostic 併載** |

**v3 selection**: cluster_only primary を維持 (PR #146 effective sample size 25
framing は Codex HIGH-2 で承諾済)。auto_block diagnostic を JSON 出力併載で
variance estimation の robustness を補強する。

**ADR 候補**: ME-11 として「Tier B bootstrap は cluster_only primary、auto_block
は diagnostic 併載」を起票。

### Q5. LIWC alternative honest framing

| v1 | v2 | hybrid v3 |
|---|---|---|
| DB10 Option D 通り全廃 | DB10 Option D 通り全廃 | **DB10 Option D 通り全廃 (一致)** |

差なし。Tier B 全 module 冒頭 docstring に honest framing 明示。

## v3 hybrid summary (one-paragraph)

**Tier B v3 = window 100 + hybrid Vendi kernel (semantic 0.7 + lexical 5-gram 0.3)
+ IPIP-50 (Goldberg 1992、Murakami 日本語版) + Big5 ICC は consistency ICC(2,k)
primary + absolute agreement ICC(A,1) diagnostic 両報告 + bootstrap cluster_only
primary + auto_block diagnostic 併載 + LIWC 全廃 (DB10 Option D)**。工数推定
~9-10h (v1 8h と v2 12h の中間)。

## 採否判定 matrix

| Question | v1 採否 | v2 採否 | v3 採否 |
|---|---|---|---|
| Q1 Vendi kernel | ✗ semantic single | ✓ hybrid (v3 と同) | ✓ |
| Q1 window | ✓ 100 (v3 と同) | ✗ 200 (design-final 破壊) | ✓ |
| Q2 IPIP-NEO | ✗ Mini-20 reliability marginal | ✓ IPIP-50 (v3 と同、要 license 確認) | ✓ |
| Q3 ICC primary | ✓ ICC(2,k) consistency (v3 と同) | ✗ ICC(A,1) は threshold 揺らぎ | ✓ |
| Q3 ICC diagnostic | ✗ ICC(3,1) のみ | ✓ ICC(A,1) も含める (v3 と同) | ✓ |
| Q4 bootstrap | ✓ cluster_only primary (v3 と同) | ✗ block primary は HIGH-2 承諾 framing 矛盾 | ✓ |
| Q4 auto_block | ✗ 採用せず | ✓ 採用 (v3 と同 diagnostic) | ✓ |
| Q5 LIWC | ✓ 全廃 | ✓ 全廃 | ✓ |

v3 が全項目で「最良の選択」を吸収。

## Codex review で v3 を challenge する点

下記を `codex-review-prompt-p4a.md` に明記:

1. **Vendi hybrid kernel の重み 0.7/0.3 の妥当性**: prior art (Friedman & Dieng 2023
   Section 4) で hybrid kernel の weight rationale はあるか
2. **window 100 turn が Vendi spectrum stability に sufficient か**: HIGH-3 が
   200-turn 最小と指摘した、100 で hybrid kernel なら mitigated と主張するが
   prior art empirical 確認
3. **IPIP-50 vs Mini-IPIP-20 の reliability gap が ICC fallback 判定に与える影響**:
   Mini-20 で α 0.6-0.7 → ICC ceiling も同程度 → ME-1 threshold 0.6 触れる
   リスク。IPIP-50 で α 0.8+ なら threshold 余裕度 up
4. **日本語 IPIP-50 (Murakami 2002/2003) の利用条件**: 商用 / 研究目的 / open
   など。defer 必要なら ADR で明示
5. **ICC(2,k) consistency と ICC(A,1) absolute agreement の併報告が drift
   detection 文脈で適切か**: どちらを ME-1 trigger に使うべきか
6. **per-window n=100 turn が ICC 計算に sufficient か**: rule-of-thumb (k items
   per dimension、n raters) と power analysis literature
7. **cluster_only と auto_block の両報告が JSON consumer 側で混乱を招かないか**:
   primary/diagnostic 区別の framing
8. **v3 は v1+v2 の hybrid だが、本質的な構造的バイアスを残していないか**:
   独立 reviewer (Codex) ならではの sanity check

## v3 で残す未解決 (Codex 反映後 design-final.md に確定)

- IPIP-50 日本語 license 確認結果次第で版 fallback 切替
- ICC primary/diagnostic 切替の最終判定 (Codex 推奨次第)
- Vendi hybrid kernel weight (0.7/0.3 vs prior-art alternative)
- per-window n=100 sufficiency の empirical/literature 確認

## v3 effort estimate

| Sub-step | 推定 |
|---|---|
| design-v1.md (済) | 30min |
| design-v2.md + comparison (本書、済) | 1h |
| Codex review prompt + execution + 反映 | 1.5h |
| design-final.md + decisions.md ADR | 30min |
| Implementation (3 file + tests + eval_store) | 4h (v1 3.5h + IPIP-50 +0.5h) |
| PR | 30min |
| **合計** | **~8.5-9h** (v1 8h、v2 12h の中間) |

 succeeded in 0ms:
# P4a Tier B — design v2 (/reimagine 後、psychometric-rigor-first 起点)

> **/reimagine premise**: v1 を意図的に破棄し、別の出発点から再起草。v1 は
> infrastructure-reuse + minimum-cost を起点にした (Mini-IPIP-20、cluster_only
> only、MPNet 流用)。v2 は **psychometric rigor + statistical power を最優先** に
> し、infrastructure cost を二次評価軸として再構成する。
>
> Refs: Codex HIGH-3 (Vendi 200-turn 最小)、Codex HIGH-2 (cluster + block hierarchical
> bootstrap)、Salecha 2024 (LLM Big5 social desirability bias)、Donnellan 2006
> (Mini-IPIP reliability)、Goldberg 1992 (IPIP-50)、Shrout & Fleiss 1979
> (ICC notation)。

## v2 の基本方針 (v1 との対比)

| 項目 | v1 (infrastructure-first) | v2 (rigor-first) |
|---|---|---|
| 出発点 | bootstrap_ci PR #146 流用 | 心理測定論 + 統計検出力 |
| 評価基準 | 計算コスト・dep 重複回避 | reliability / construct validity / power |
| trade-off | 工数 8h 内に収める | 必要なら工数増を許容 |
| 失敗モード | psychometric weakness (mini-20 reliability、cluster_only over-coverage) を見逃す | infrastructure complexity 増・工数膨張 |

## 1. Mission (v1 と同じ)

`tier_b/` 3 module を提供し、DB9 quorum (Vendi / Big5 ICC / Burrows Δ) を稼働
させる。Tier B が offensive gate の唯一の arbiter。

## 2. The 5 question — v2 (rigor-first)

### Q1. Vendi Score kernel

**v2**: hybrid kernel (semantic MPNet + lexical 5-gram) + 200-turn window。

- **window 100 → 200 に拡大**: Codex HIGH-3 が「Vendi は 200-turn 最小」を
  prior art (Friedman & Dieng 2023) ベースで指摘。100 turn は spectrum collapse
  リスクが Codex 側で raise されている領域
- **kernel 拡張**: semantic alone は paraphrase に過敏、lexical alone は
  surface-form noise に過敏 → hybrid (重み 0.7 semantic / 0.3 lexical 5-gram)
- 直交 one-hot sanity (P5 残課題) は lexical 成分で達成、score=N
- 効果: window 200 化で 5 runs × 2.5 windows = **12.5 cluster/persona**
  (window 数半減、cluster 内 turn 数倍増、有効サンプル空間は同等だが
  spectrum stability は向上)
- trade-off: window 数減 → bootstrap CI width 拡大。`block_length` 内側 block
  bootstrap も併用 (cluster_only ではなく `cluster + block`)

**v2 が v1 を破壊する点**: window=100 cluster_only mode を再考。HIGH-3 を
literally 受け止め直す。

### Q2. IPIP-NEO 版

**v2**: IPIP-50 short (Goldberg 1992) — Mini-IPIP-20 では reliability 不十分。

- Mini-IPIP-20 は per-dimension **4 items**、Cronbach α が dimension 依存で
  0.6-0.7 と marginal (Donnellan 2006 self-reported)
- IPIP-50 は per-dimension **10 items**、α が安定して 0.8 以上
- agentic loop overhead: 50 items × 25 windows × 3 persona × 5 run =
  **18,750 calls** (vs mini-20: 7,500)
- qwen3:8b で 1 item ≤ 1s 想定、合計 ~5h overnight 1 回限り (M9-eval P3 で
  G-GEAR 走行と並行可)
- balanced reverse-keyed: ~50% items
- 日本語訳: IPIP-50 公式日本語版 (Murakami 2002 / 2003) を流用、出典明記

**v2 が v1 を破壊する点**: Mini-IPIP-20 は cost-only 観点。psychometric
reliability prior art は IPIP-50 を強く支持。Codex prior art search に確認させる。

### Q3. Big5 ICC formula

**v2**: ICC(A,1) absolute agreement single rater (McGraw & Wong 1996 notation
= Shrout & Fleiss 1979 ICC(2,1) absolute agreement) + ICC(2,k) consistency
diagnostic。

- **rationale 切り替え**: v1 は ICC(2,k) consistency primary。だが LoRA
  drift detection の文脈では「baseline と比べて Big5 score が同じか」を
  問うため、**absolute agreement** が construct validity 上正しい。
  consistency は rater-level offset を除外してしまう
- ICC(A,1): 単一 run の reliability、5 run でも単一 score を扱う想定
- ICC(2,k) consistency: diagnostic for cross-check
- ME-1 cutoff (ICC<0.6 / lower CI<0.5) は absolute agreement 文脈でも適用可、
  ただし **threshold 値の妥当性は再評価必要** (Koo & Li 2016 の cutoff は
  consistency ICC が中心)

**v2 が v1 を破壊する点**: formula 選択は notation 違いではなく construct
意味が異なる。LoRA drift detection の意味論で再選択。

### Q4. windowing × bootstrap

**v2**: 200-turn window × 5 runs = 12.5 cluster/persona、`cluster + block`
hierarchical bootstrap (cluster_only ではない)。

- v1 の cluster_only は per-window autocorrelation を完全に放棄。これは
  「window 内 sample 順序に意味がない」場合に正当だが、Vendi は kernel
  matrix 全体を扱うため per-window 内構造を block bootstrap で保つほうが
  variance underestimation を防ぐ
- `hierarchical_bootstrap_ci(values_per_cluster, block_length=50,
  cluster_only=False, auto_block=True)` を採用 — PR #146 の `auto_block`
  path で per-cluster block を Politis-White 推定で動的選択
- effective sample size framing は cluster (12.5) ではなく blocks 経由の
  effective n に切替

**v2 が v1 を破壊する点**: cluster_only は P5 hardening で実装したが
**Tier B の使用文脈には not necessarily right fit**。auto_block が prior art
寄り。

### Q5. LIWC alternative honest framing

**v2 (確定、v1 と同)**: DB10 Option D。Tier B では LIWC alternative 新規導入
なし。Empath は Tier A 既存範囲。

ここは v1 と一致。/reimagine も DB10 を破棄する根拠を見出さない。

## 3. API skeleton — v2 で v1 から変わる点

### `vendi.py` 差分

```python
@dataclass(frozen=True, slots=True)
class VendiResult:
    score: float
    n: int                    # 200 (v2) vs 100 (v1)
    kernel: str               # "hybrid-mpnet-5gram" (v2) vs "mpnet-cosine" (v1)
    spectrum_entropy: float   # 内部診断、kernel matrix の H(λ)
    semantic_weight: float    # 0.7
    lexical_weight: float     # 0.3
```

### `ipip_neo.py` 差分

```python
@dataclass(frozen=True, slots=True)
class Big5Scores:
    extraversion: float
    agreeableness: float
    conscientiousness: float
    neuroticism: float
    openness: float
    n_items: int     # 50 (v2) vs 20 (v1)
    version: str     # "ipip-50" (v2) vs "mini-ipip-20" (v1)
    cronbach_alpha: dict[str, float]  # 新: 各 dimension の α 計算値
```

### `big5_icc.py` 差分

```python
@dataclass(frozen=True, slots=True)
class Big5ICCResult:
    icc_point: float              # ICC(A,1) absolute agreement (v2)
    icc_lower_ci: float
    icc_upper_ci: float
    icc_2k_consistency: float     # diagnostic (v2): consistency ICC(2,k)
    n_windows: int                # 12.5 cluster (v2) vs 25 (v1)
    fallback_fire: bool           # ICC < 0.6 OR lower CI < 0.5
    formula: str                  # "ICC(A,1) absolute agreement, McGraw-Wong 1996"
    threshold_basis: str          # "Koo-Li 2016 / re-evaluated for absolute agreement"
```

## 4. Persistence — v2 (v1 とほぼ同)

`metrics.tier_b` table column 流用は v1 と同じ。v2 では `metric_name` に追加:

- `tier_b.vendi_spectrum_entropy` (内部診断)
- `tier_b.cronbach_alpha_extraversion` ... 5 行 (per dimension)
- `tier_b.big5_icc_2k_consistency_diagnostic`

`notes` JSON で kernel weights / version / formula を埋める。

## 5. Test plan — v2 で追加 (合計 18-20 件)

v1 16 件 + 追加:

- `test_compute_vendi_window_200_spectrum_stability` — 200-turn での
  kernel matrix spectrum がランダム性に対して安定
- `test_compute_vendi_hybrid_kernel_weight_sum_one` — 0.7+0.3=1.0 sanity
- `test_compute_ipip_neo_50_cronbach_alpha_lower_bound` — α >= 0.7 (synthetic)
- `test_compute_big5_icc_absolute_agreement_offset_sensitivity` — offset 加算で
  ICC が変化することを確認 (consistency なら不変、agreement なら変化)

## 6. Effort estimate — v2

| Sub-step | 推定 |
|---|---|
| 全体 | **~10-12h** (v2 は 50 items + 200 window + auto_block で +25-50%) |

v1 の 8h との差は **2-4h 増**。trade-off:

- 工数増 +2-4h
- 得るもの: psychometric reliability up (α 0.6-0.7 → 0.8+)、Vendi spectrum
  stability up、ICC construct validity 改善、auto_block で bootstrap CI 妥当性 up

## 7. v2 の意図的な懸念点

- **window 200 化が design-final.md (M9-eval) で per-100-turn を確定済**:
  確定文書の上書きが必要。decisions.md 新 ADR で justify
- **IPIP-50 日本語訳 license**: Murakami 2002/2003 の利用条件確認が要 — defer
  すれば Mini-IPIP-20 fallback
- **ICC formula 切り替えで ME-1 threshold の妥当性が揺らぐ**: Codex に
  literature 確認させる
- **auto_block の per-cluster cap が cluster_only より bootstrap CI が
  狭すぎる可能性**: synthetic AR(1) test で empirical 確認
- **agentic loop budget +150% (mini-20 → ipip-50)**: G-GEAR 並行 OK か要確認

## 8. v2 が捨てている v1 の正しさ (hybrid v3 候補)

v1 が正しい点 (v2 が損なうべきでないもの):

- **infrastructure-reuse**: MPNet encoder lazy-load 流用は依然強い
- **cluster_only mode 実装済**: PR #146 の労力を活かしたい
- **per-100-turn windowing が design-final 確定済**: 上書きは新 ADR coast 高い
- **8h 工数内に収まる**: solo cadence で安全

→ **hybrid v3 候補**:

- Vendi: window=100 維持 (design-final 整合) + hybrid kernel (semantic+lexical) 採用
- IPIP-NEO: **IPIP-50 採択** (psychometric reliability 優先)
- ICC: ICC(2,k) consistency primary 維持 + ICC(A,1) absolute agreement diagnostic
  追加 (両 framing surfaced)
- bootstrap: cluster_only primary + auto_block diagnostic を JSON 出力併載
- Window 200 化は **defer** (design-final 上書きを ADR で正当化するコスト > 利得)

exec
/bin/zsh -lc "sed -n '90,250p' .steering/20260430-m9-b-lora-execution-plan/decisions.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '250,330p' .steering/20260430-m9-b-lora-execution-plan/decisions.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
- **影響**:
  - M9-eval-system が独立タスクとして大規模化
  - golden set 採取に専門知識 (philosopher domain expert) が必要
- **re-open 条件**:
  - golden set 整備が solo cadence に対し時間的に困難
  - LIWC license が approve、商用使用可

---

## ADR 横断: third option (codex final note 反映)

**bounded, non-authoritative single-persona Kant LoRA spike を SGLang 上で M9-eval-system
と並行実施する**。adoption 判断は評価系完成後の post-spike re-eval まで保留。

- **目的**: 評価系構築中に LoRA 学習・adapter swap・runtime 技術リスクを早期検出
- **non-authoritative**: spike の結果のみで adoption しない (評価系 gate 通過必須)
- **scope**: Kant 1 persona のみ、既存 dialog_turn を training data として use、
  `evaluation_epoch=false` partition のみ
- **deliverable**: SGLang LoRA endpoint 動作確認 + adapter swap latency 実測 +
  vLLM migration 必要性 measured 判断材料
- **タスク**: 別タスク `M9-C-spike` として切り出し (新規 scaffold)

---

## DB11 — Cognition deepening contamination prevention (PR #144 Codex HIGH-3 反映、addendum 2026-05-08)

PR #144 (`docs/cognition-deepen-decision-2026-05-08`、main=`e641f8d`) で確定した認知深化
二層 architecture から、M9-B LoRA training pipeline への contamination 防止 ADR を追加。

### 決定

raw_dialog metadata に `individual_layer_enabled: bool` field を追加 (default=false)。
training-view contract loader は **`evaluation_epoch=false AND individual_layer_enabled=false`**
の両方を満たす行のみ訓練 eligible とする。training pipeline 入口で
`all(row.metadata.individual_layer_enabled is False)` を assert し、contamination
検出時は fail-fast。

### 根拠

PR #144 Codex `gpt-5.5 xhigh` review HIGH-3 (`M9-B LoRA training contamination`):
> Individual layer を M9-B 前または並行で cognition に混ぜると、LoRA が philosopher_base
> ではなく「個体 overlay 済み Kant」を学習する。PR #127 の固定 Kant style 前提を破り、
> 後続の base/individual 分解が測定不能になる。

固定 Kant style を保証する training を維持するため、Individual layer が現れた tick の
raw_dialog は **どんな状況でも** training export から除外する。

### 棄却

- 「flag を追加せず、M10-A scaffold 開始時に手動で training export を一時停止する」案:
  human-error 余地が高く、M9-B execution が M10-A と時系列で重なる場合に防御不能
- 「`evaluation_epoch=true` を流用する」案: eval / cognition deepening の 2 軸は orthogonal
  (cognition deepening enabled かつ eval ではない tick がありうる)、統一は意味歪曲
- 「runtime check のみで partition を切らない」案: dataset レベルの persistence で固定する
  ことで、後段 pipeline が flag を尊重する保証が強化される

### 影響

- DB5 (Parquet schema 物理分離) に `individual_layer_enabled` field を 1 つ追加 (additive)
- DB6 (Evaluation epoch 分離) の training-view contract に AND 条件を追加 (additive)
- M9-eval-system Parquet pipeline 実装時に flag 対応必須
- M9-C-adopt (LoRA execution) で training-view loader assert 実装必須
- M10-A scaffold 設計時に `individual_layer_enabled=true` set 責務を明示

### re-open 条件

- 認知深化 phasing が M11+ 以降で根本的に変更され、Individual layer の概念自体が撤回された
  場合 (現時点では PR #144 で確定済み、撤回 path は M12+ research re-evaluation の
  empirical evidence 後でのみ可能)
- LoRA を Individual layer にも適用すると判断された場合 (PR #144 M12+ research gate 該当、
  その時点で contamination 防止 logic を再設計)

### Cross-reference

- PR #144 design-final.md §2.1 (M9 trunk との接続 / M9-B LoRA contamination 防止)
- PR #144 decisions.md DA-8 (philosopher_seed refactor ADOPT-WITH-CHANGES)
- `.steering/20260508-cognition-deepen-7point-proposal/codex-review.md` HIGH-3

 succeeded in 0ms:
  - v1/v2 4-AND: D1 ADR と矛盾、unreachable リスク
  - 500/persona: ζ scale で達成困難
- **影響**:
  - LoRA 適用が現実的タイミングで fire 可能
  - timebox により M9 milestone delay が bounded
- **re-open 条件**:
  - 300/persona も実態で困難 → 再 relax (200/persona) 検討
  - timebox 8 session が早すぎ・遅すぎ判明 → 調整

---

## DB5 — Parquet schema: **raw + sidecar 物理分離** (HIGH-4 反映)

- **決定**: training data と evaluation metric を **物理的に別 table** に保存。
  - **raw_dialog/**: metric-free training table。`evaluation_epoch=*/persona_id=*/run_id=*/`
    partition、training は `evaluation_epoch=false/` のみ読む contract で強制。
  - **metrics/**: sidecar evaluation metric table。`run_id + persona_id + turn_idx` で
    raw に join。tier (A/B/C) + metric_name + metric_value + metadata schema。
- **根拠**:
  - codex HIGH-4: boolean flag (evaluation_epoch) だけでは training pipeline が物理的に
    metric column にアクセス可能、汚染リスク (judge artifact 学習)
  - 物理分離 + training-view contract で contamination を構造的に不可能にする
- **棄却**:
  - v1/v2: 単一 Parquet schema に metric column 統合 → contamination リスク
- **影響**:
  - Parquet pipeline 実装 (M9-eval-system) の複雑度が中程度増加
  - training loader は明示的に `raw_dialog/evaluation_epoch=false/` のみ読む実装
  - dashboard / analysis は raw + metrics を join して使用
- **re-open 条件**:
  - sidecar join overhead が training latency に影響大
  - schema migration が必要な structural change

---

## DB6 — Evaluation epoch 分離: Run-level flag + 物理 partition + sidecar (HIGH-4 統合) + 頻度 policy (MEDIUM-4)

- **決定**:
  - `evaluation_epoch: bool` を Run config 必須化、Default `False`
  - Parquet partition で物理分離 (`raw_dialog/evaluation_epoch=*/`)
  - sidecar metrics table も同 partition 構造
  - **頻度 policy**:
    - **Tier A**: per turn (cheap, ~50ms total)
    - **Tier B**: per 100 turns (Vendi / IPIP-NEO / Big5 ICC)
    - **Tier C**: nightly offline batch (Prometheus 2 / G-Eval / FANToM-adapted) — autonomous run 停止時のみ実行
- **根拠**:
  - codex HIGH-4 + MEDIUM-4: Tier C judge LLM (Prometheus 2 8x7B class) は qwen3:8b agent
    と VRAM contention、同時実行不可
  - 物理 partition は HIGH-4 解消の core mechanism
- **棄却**:
  - v1/v2 の boolean flag 単独: contamination リスク
  - Tier C を per-100-turn に走らせる案: VRAM contention で agent 停止
- **影響**:
  - autonomous loop に nightly batch slot 追加が必要
  - dashboard は per-tier の latency profile を表示
- **re-open 条件**:
  - Tier C judge LLM が smaller model に置換可能で contention 解消

---

## DB7 — Persona N=4 拡張時期: defer to M10 + synthetic heldout 4th in eval tests (LOW-1 反映)

- **決定**:
  - Runtime N=4 (agora 主体 4 人目 actual deploy) は **M10 まで完全 defer**
  - ただし **eval pipeline test には mocked 4th persona scenario を含める**
- **根拠**:
  - M9-B / M9-eval-system 期間は N=3 の divergence 漸近線 + 評価系構築が優先
  - codex LOW-1: eval pipeline が N=3 専用に overfit するのを防ぐため、synthetic 4th
    persona を test fixture として使う
  - 4 人目の persona YAML 起草 / reference corpus 整備 / golden set は M10 着手時に開始
- **棄却**:
  - v1: M9-B 中 YAML 起草 → 評価系設計を複雑化
  - 完全 defer (synthetic も含めない): eval pipeline overfit リスク
- **影響**:
  - eval pipeline test に synthetic persona fixture 追加
  - M10 で agora 主体 candidate を再評価
- **re-open 条件**:
  - N=3 の divergence が早期に saturate、4 人目で extension が必要
  - M10 timeline で 4 人目 candidate が確定

---

## DB8 — Adapter swap runbook: SGLang `/load_lora_adapter` first

- **決定**:
  - **SGLang `/load_lora_adapter` REST endpoint** で adapter dynamic load
  - `--max-loras N` + `--max-lora-rank R` 起動オプション
  - hot path persona は `pinned adapters` で pin
  - **runbook 起草は M9-C-spike 完了後**、実測値 (latency / cold start / throughput) 込み
- **根拠**:
  - DB3 (SGLang-first) と整合
  - SGLang docs cited by codex
  - 実測値なしの runbook は無価値、spike 完了後に書く
- **棄却**:
  - v1/v2 vLLM LoRARequest API ラッパ路線 → DB3 で破棄
- **影響**:
  - M9-C-spike が runbook の前提
- **re-open 条件**:
  - SGLang LoRA で adapter swap が機能不全 → vLLM fallback (DB3 re-open)

---

## DB9 — Drift gate: composite + bootstrap CI + 2-of-3 quorum (HIGH-2 反映)

- **決定**: drift gate を **統計的に厳密** に運用:
  - **Primary composite per persona**: 各 persona の Tier B から 3 sub-metric:
    - `vendi_score` (semantic kernel)
    - `big5_stability_icc` (across-mode personality stability)
    - `burrows_delta_to_reference` (persona-fit)
  - **Bootstrap CI** over turns/runs: 各 sub-metric の 95% CI を計算
  - **Quorum rule**:
    - rollback (drift): 2-of-3 sub-metric が CI で baseline negative 方向
    - adoption: 2-of-3 sub-metric が CI で baseline positive 方向
  - **Single regression**: warning ログのみ、rollback しない
  - **Defensive canary** (即時): self_rep > 0.15 OR cross_echo > 0.15 (any 1) → CI 待たず auto rollback
  - **Initial run** (first LoRA application): floor 維持で許容 (warmup 認可)
  - **Subsequent runs (≥2)**: 2-of-3 quorum で adoption / rollback 判定
  - **3 連続 adoption 失敗**: LoRA 設定 (rank / dataset) を破棄、再 spike
- **根拠**:
  - codex HIGH-2: 「5%」固定 + Tier B noise → false rollback / metric gaming リスク
  - bootstrap CI + quorum で statistical robustness
  - Effect size は persona-conditional に bootstrap で決める (固定 5% を破棄)
- **棄却**:
  - v1 「floor 維持のみ」: 効果測定不能
  - v2 「絶対 5% 改善」: noise floor が persona 依存、根拠不十分
- **影響**:
  - bootstrap CI 実装 (M9-eval-system)
  - quorum logic 実装 (M9-C-adopt)
- **re-open 条件**:
  - 3 sub-metric の選定が実態で不適切 (例: vendi_score が persona に discriminative でない)
  - CI 計算 cost が prohibitive

---

## DB10 — J 評価系 framework: 4-tier + persona-conditional + multi-channel (specs only in M9-B)

- **決定**:
  - **M9-B 内 deliverable は specs のみ** (実装コードは出さない、MEDIUM-1 反映)
  - **4-tier 階層** (research-evaluation-metrics.md ベース):
    - Tier A: per-turn cheap (LIWC/Empath / Burrows Delta / MATTR / semantic novelty / NLI)
    - Tier B: per-100-turn (Vendi Score / IPIP-NEO / Big5 stability ICC)
    - Tier C: per-session offline (Prometheus 2 / G-Eval / FANToM-adapted / ROSCOE)
    - Tier D: sparse manual (FActScore-adapted / 専門家 review / RoleEval-adapted MCQ)
  - **persona-conditional gate**: absolute value ではなく persona-baseline からの bootstrap
    CI 偏差 (Rikyu LOW idea density は適正、Kant HIGH も適正)
  - **golden set staging** (MEDIUM-3 反映):
    - M9-eval-system: **100/persona seed**
    - LoRA 採用判定: **300/persona acceptance**
    - 学術発表時: **1000/persona publication-grade**
  - **multi-channel honest framing**: single thinker-likeness score 採用しない、
    formal benchmark = floor / proxy = exploratory / expert review = final
  - **LIWC alternatives honest framing** (LOW-2 反映): Empath/spaCy は proxy であり LIWC 等価ではない、
    Big-Five claim は LIWC 商用 license + validation あって初めて成立、proxy ベースの
    Big-Five claim は honest に避ける
- **根拠**:
  - research-evaluation-metrics.md L326-349 honest gap assessment
  - codex MEDIUM-1 / 3 / LOW-2 反映
- **棄却**:
  - v1: framework 宣言のみ、内容空白
  - v2 単独: M9-B 内で Tier A 実装まで含む scope creep
  - 「single thinker-likeness score」: research-evaluation-metrics.md と Codex 双方が棄却
- **影響**:

exec
/bin/zsh -lc "sed -n '1,80p' .steering/20260430-m9-eval-system/decisions.md && sed -n '120,240p' .steering/20260430-m9-eval-system/decisions.md && sed -n '566,690p' .steering/20260430-m9-eval-system/decisions.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# Decisions — m9-eval-system (Codex review MEDIUM 反映)

## ADR 体裁

各 ADR は M9-B `.steering/20260430-m9-b-lora-execution-plan/decisions.md` と同形式の
5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)。本 ADR set は M9-B DB1-DB10 と
**並列** で、m9-eval-system タスク独自の 6 件 (Codex `gpt-5.5 xhigh` review MEDIUM
を反映) + 1 件 (HIGH-3 で確定する ratio の placeholder)。

ID prefix: `ME` (m9-Eval-system) で M9-B `DB` と区別。

---

## ME-1 — IPIP-NEO fallback trigger operational definition (Codex MEDIUM-1)

- **決定**: BIG5-CHAT regression head conditional fallback の **発火条件** を以下に
  確定:
  - **trigger**: golden baseline 採取後 (3 persona × 5 run の Big5 ICC 計測完了時点) に
    **≥2/3 personas で ICC 点推定 < 0.6 OR 95% lower CI bound < 0.5**
  - **検出 timing**: P5 (bootstrap CI) 完了直後の自動チェック、`evidence/tier_b/big5_icc.py`
    が判定して `decisions.md` に re-open 候補を append
  - **追加 diagnostic** (常時計測): acquiescence index (logit balance)、straight-line
    response (≥10 連続同回答)、balanced/reverse-keyed item agreement
  - **control comparison**: persona prompt 無し base model (qwen3:8b raw) で同 IPIP-NEO
    を 1 回測定し、persona 効果と base model self-report bias を separately report
- **根拠**:
  - Codex MEDIUM-1: 「ICC < 0.6 が頻発」の頻発に denominator 無し → 監査不能
  - Salecha et al. 2024 (arXiv 2405.06058): LLM Big5 self-report に social
    desirability bias の empirical 報告
  - Koo/Li ICC 解釈: 0.5-0.75 = moderate (effectsize docs)、0.6 boundary は
    "moderate vs questionable" の境界
  - acquiescence / straight-line / reverse-keyed は psychometric standard (Tomas
    et al., Schmidt et al.)
- **棄却**:
  - 元案「frequent」のみで quantitative threshold 無し → 監査不能で棄却
  - 全 persona AND 条件 (3/3) → false negative リスク (1 persona で fallback 発火しても
    measurement model 全体に問題があり得る)
- **影響**:
  - `evidence/tier_b/big5_icc.py` に diagnostic 4 種 (ICC point, lower CI, acquiescence,
    straight-line) を追加
  - golden baseline 後 `decisions.md` に再 open 判定 ADR 追記の workflow
  - control measurement 1 run (~10 turn equivalent) を P3 にも組み込み
- **re-open 条件**:
  - golden baseline 採取後の判定で fallback fire → BIG5-CHAT regression head
    実装 ADR を別途起票 (本 ADR の child)
  - 0.6 / 0.5 閾値が persona-specific に不適切と判明 → persona-conditional
    threshold に変更検討

---

## ME-2 — DuckDB snapshot semantics (G-GEAR write → Mac read-only) (Codex MEDIUM-2)

- **決定**: G-GEAR が DuckDB file の唯一 writer、Mac は read-only consumer。
  rsync は以下の protocol で実行:
  1. **G-GEAR 側**: 採取セッション終了時に `con.execute("CHECKPOINT")` →
     `con.close()` で WAL を main file に flush
  2. **G-GEAR 側**: `cp <golden>.duckdb /tmp/<golden>.snapshot.duckdb` で同 fs 内 copy
     (DuckDB の同時 open lock 衝突回避)
  3. **G-GEAR → Mac rsync**: `rsync -av /tmp/<golden>.snapshot.duckdb mac:/data/eval/golden/`
  4. **Mac 側 atomic rename**: rsync 完了後 `mv` で `<golden>.duckdb.tmp` → `<golden>.duckdb`
     (部分転送 file を application が open しないため)
  5. **Mac 側 open**: `duckdb.connect(path, read_only=True)` を強制 (`eval_store.py`
     の `connect_training_view()` / `connect_analysis_view()` の両 entry で wrapper enforced)
  - **NFS / SMB / iCloud 共有 fs 経由は禁止** (DuckDB doc が file lock 警告)
- **根拠**:
  - Codex MEDIUM-2: live G-GEAR file を Mac から open は CHECKPOINT 前なら破損リスク
  - DuckDB doc (Concurrency): single-process write + multi-process read-only OK、
    ただし shared fs 注意
  - atomic rename は POSIX 移動が same-fs 内 atomic である事実に依拠
- **棄却**:
  - live file の直接 read → 破損 / 古い snapshot 読み出しリスク
  - SQLite WAL 風の hot replication → DuckDB は WAL replay の cross-process 安全性が
    documented でない、棄却
- **影響**:
  - `infra/scripts/sync_golden_baseline.sh` (新規) で G-GEAR → Mac の rsync orchestration
  - `eval_store.py` の Mac 経路は read_only=True 強制 (test 化)
  - golden baseline 採取 SOP に CHECKPOINT step を追加
- **re-open 条件**:
  - dataset size が大きく (>100GB) rsync コスト過大 → DuckDB native replication 機構
    検討
  - skip rate が想定より高い (>50%) → スケジュール時間帯見直し

---

## ME-4 — Hybrid baseline ratio: P3a 完了後に確定 (Codex HIGH-3 系の defer ADR)

- **決定 (元案)**: 200 (stimulus battery) / 300 (自然対話) を **default** とし、P3a で
  両 condition × 3 persona の isolated pilot を採取し、bootstrap CI width で
  ratio を確定する。
- **2026-05-01 partial update (P3a-decide Mac セッション、Task 1+2 完了)**:
  - **stimulus 3 cell**: G-GEAR 採取 focal=198 / total=342 / dialogs=168 で 3 persona
    すべて完走済 (data/eval/pilot/_summary.json)。
  - **natural 3 cell**: G-GEAR 採取は M5/M6 zone-drift bug で **partial**
    (kant=6 focal / nietzsche=0 focal / rikyu=6 focal、~13 min wall で kill)。
    本セッションで `InMemoryDialogScheduler.eval_natural_mode=True` を導入して bug
    を解決 (PR `feature/m9-eval-p3a-decide`、ME-8 ADR 参照)。修正後の natural cell は
    G-GEAR 再採取が必要 (本 Mac セッションでは LLM 不在で実機検証不可)。
  - **bootstrap CI 計算**: `src/erre_sandbox/evidence/bootstrap_ci.py` を P5 prep として
    drafted (本来 P5 phase 着手分の前倒し)、`scripts/p3a_decide.py` で stimulus side の
    Burrows Delta + MATTR (lightweight) の CI を計算する経路を整備 (G-GEAR DuckDB の
    rsync 待ち)。NLI / novelty / Empath は `[eval]` extras 必須なので Mac default では
    skip + clear log line で degrade。
  - **判定**: stimulus side のみで ratio を確定するのは統計的に invalid
    (元 ADR の "両 condition で測定" 要件未充足)。**ratio 200/300 default は留保**、
    natural 再採取後に再判定。
- **判定基準 (元案維持)**:
  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
  - 両条件で sub-metric の **mean CI width が小さい比率** を採用
  - 両者が同等 (差 <10%) なら 200/300 default を維持
- **根拠**:
  - Codex HIGH-3: 元案の「P3 採取後 P3b で 50 turn pilot」は順序 invert + 統計力不足
  - 200 turn は Vendi の 200-turn window を 1 cycle 満たす最小値
  - bootstrap CI width が直接的な測定対象 (DB9 quorum の信頼性)
- **棄却**:
  - 200/300 を data なしで freeze → arbitrary (元案のまま)
  - **stimulus 側 CI のみで ratio 確定**: natural side との **比較**が ratio 決定の
    本質 (元 ADR §判定基準 1) で、片側 CI のみでは比較できない → 棄却
- **影響**:
  - P3a-decide セッションで **partial 完了**: gating bug fix + bootstrap_ci module +
    p3a_decide script は ready、natural 再採取後に最終 ratio 確定
  - ratio 確定までは P3 (golden baseline 採取) 入り保留 — 本来 24h × overnight×2 の
    G-GEAR 採取を、ratio 不確定で着手すると invalidation リスク
- **re-open 条件**:
  - **本 ADR は再採取後に二度目の Edit を要する** (current state = partial):
    1. G-GEAR 再採取で natural side が完走 (focal 30 / total 90 / dialogs ~15)
    2. Mac で `scripts/p3a_decide.py` を両 condition の duckdb に対し run
    3. ratio default 200/300 vs alternative の bootstrap CI width 比較
    4. 確定値で本 ADR を **再 Edit**
  - golden baseline 採取後に DB9 quorum の sub-metric が persona discriminative でない
    と判明 → ratio 再調整 + 再採取検討 (元案維持)
- **partial-close 状態の文脈**:
  - 本 ADR は **2 段階 close**: (1) bug fix + script ready (本セッション)、
    (2) 再採取データで実測値 ratio (次 G-GEAR セッション + 次 Mac セッション)
  - tasklist.md §P3a-decide はチェック項目を分割: "scheduler fix [x]" / "bootstrap CI
    modules ready [x]" / "stimulus-side CI computed (rsync 待ち) [pending]" /
    "ratio ADR 確定 (natural 再採取待ち) [pending]"

- **2026-05-05 partial update #3 (P3a-finalize Mac セッション、lightweight ratio 確定)**:
  - **2 段階 close は不正確だった**: 当初想定の「(2) で最終 close」は Vendi + Big5 ICC
    が P4 territory であることを見落としていた。本 ADR は **3 段階 partial close**
    に再構造化される: (1) bug fix + script ready (2026-05-01 #1) / (2) lightweight
    ratio 実測 (本 update、Burrows + MATTR のみ) / (3) full ratio 実測 (P4 完了後、
    Vendi + Big5 ICC を含めて再判定)。
  - **empirical 実測値** (`data/eval/pilot/_p3a_decide.json`、schema `p3a_decide/v3`):
    - **6 cell rsync 完了** (G-GEAR PR #133 → Mac、md5 6/6 hash 一致)
    - **target-extrapolated ratio** (n_target_stim=200, n_target_nat=300、
      `width × sqrt(n / n_target)` で sample-size 効果除去 — Codex P3a-finalize HIGH-1):
      | metric | stim extrap | nat extrap | nat/stim | n_cells |
      |---|---|---|---|---|
      | Burrows Delta | 6.09 | 2.49 | **0.41** | 2 (kant+nietzsche) |
      | MATTR | 0.0131 | 0.0130 | **0.992** | 3 (全 persona) |
      | combined (mean) | 3.05 | 1.25 | **0.41** | — |
    - **verdict**: `stimulus_wider_at_target_alternative_recommended` (combined ratio
      0.41 → natural が target 換算で 59% 狭い、10% tolerance 大幅超過)
    - **方向性は両 metric で一致** (Burrows 0.41、MATTR 0.992 ≤ 1.0): natural narrower
      or equal at deployed scale → verdict は scale-domination の影響を受けず robust
    - **scale dominance caveat**: Burrows (~6.0 scale) が MATTR (~0.013 scale) を
      ~470x で支配しているため、combined ratio は実質 Burrows 単独の判定。per-metric
      breakdown は `by_condition` で個別公開。
  - **judgment for ratio default (200/300) — provisional**:
    - **lightweight verdict**: 200/300 default を **暫定維持** (適用条件付き、下記)
    - 根拠 1: target-extrapolated で natural が 41% (Burrows) / 99% (MATTR) — natural
      は default budget 300 turn で十分な CI 精度を達成見込み、widen 不要
    - 根拠 2: stimulus が natural より大幅に wider at target → stimulus 200 turn は
      tighter CI 達成のため **追加 turn が望ましい可能性**。ただし 200 turn は
      Vendi 200-turn window 1 cycle の最小値 (元 ADR §根拠 2) で下限制約あり、
      固定維持。
    - 根拠 3: 元 ADR §判定基準 3 「両者が同等 (差 <10%) なら default 維持」は
      本 lightweight 結果では適用不能 (差 59% で同等ではない)、ただし方向性は
      「natural を増やす必要なし」+「stimulus を増やしたいが下限制約」なので
      **default 200/300 が最良の lightweight 判定**となる。
    - 暫定性の根拠: Vendi + Big5 ICC が P4 完了後に異なる方向性を示す可能性あり、
      Rikyu Burrows は Japanese tokenizer 未実装で 2/3 persona のみ寄与 (n_cells=2)。
  - **適用条件 (provisional → final 移行のための再開条件)**:
    - **P4 deliverable**: Vendi Score + Big5 ICC を全 6 cell に対し計算 → ratio
      verdict を再算出。**P4 結果が方向反転** (natural が stimulus より wider at
      target) または **lightweight ratio から 10%超のズレ** → 本 ADR を **partial
      update #4** で再 Edit、ratio default を再評価。
    - **m9-eval-corpus expansion**: rikyu Japanese tokenizer 実装 → Rikyu Burrows
      が 3/3 persona で寄与可能に → ratio 再算出。**ratio が現在値 (0.41) から
      10%超のズレ** → partial update #5 で再 Edit。
    - **DB9 quorum sub-metric 不足**: golden baseline 採取後に persona-discriminative
      が不十分 → ratio 再調整 + 再採取検討 (元案維持)。
  - **追加 caveat (Codex P3a-finalize 反映)**:
    - 本 ADR は ME-4 §判定基準が指す **3 metric (Burrows / Vendi / Big5 ICC)**
      のうち 1/3 metric (Burrows、Rikyu 除く 2/3 persona) + lightweight proxy 1
      metric (MATTR、3/3 persona) のみで判断している。**Vendi + Big5 ICC を含む
      full verdict は P4 territory** で、本 update は lightweight proxy update。
    - 数値の生 source は `data/eval/pilot/_p3a_decide.json` を verbatim 参照する
      (re-derive 防止)。
    - Codex review trail: `codex-review-prompt-p3a-finalize.md` →
      `codex-review-p3a-finalize.md` (Verdict block、HIGH 3 / MEDIUM 4 / LOW 4 全反映)。
  - **partial-close 状態の文脈の改訂**:
    - 本 ADR は **3 段階 partial close** (上記)、本 update で **段階 (2) close**
    - tasklist.md §P3a-decide は段階 (2) のチェック項目すべて [x] 化、段階 (3) を
      M9-D / M9-E (P4) のタスクリスト側で受け継ぐ
    - main 側 implementation: branch `feature/m9-eval-p3a-finalize` (本 PR で merge)、
      script schema bump v1 → v3、`_KNOWN_LIMITATIONS` 経由で rikyu Burrows を
      validation warning routing

---
## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)

- **決定**:
  1. **CLI fix scope** (別タスク `m9-eval-cli-partial-fix` で実装、Plan +
     /reimagine 必須):
     - `_SinkState` に `soft_timeout: str | None` 追加 (現 `fatal_error` と分離)
     - `CaptureResult` に `partial_capture: bool` + `stop_reason: str` +
       `drain_completed: bool` 追加
     - wall timeout path で `<output>.capture.json` sidecar 永続化 (schema:
       `{status, stop_reason, focal_target, focal_observed, total_rows,
       wall_timeout_min, drain_completed, runtime_drain_timeout, git_sha,
       captured_at}`)
     - `_async_main` return code: 0 (complete) / 2 (fatal、現状維持) /
       **3 (partial_publish 新設)**
     - `eval_audit` CLI 新設 (`src/erre_sandbox/cli/eval_audit.py`):
       `focal >= target` AND `sidecar.status == "complete"` を機械的に gate、
       partial は別 exit code で audit fail
     - `_resolve_output_paths` の stale `.tmp` unlink 前に sidecar 存在 + status
       チェック、partial salvage の意図を明示する flag (`--allow-partial-rescue`)
       追加検討
  2. **Phase 2 採取戦略**:
     - run1 を **600 min single calibration cell** (kant のみ 1 cell、3-parallel
       でない 1-only) で先行実行、120/240/360/480 min 時点で focal / total /
       memory sqlite row count / Ollama latency を記録
     - 結果から run2-4 の wall budget を empirical 確定 (Codex H1: 600 min が
       最低ライン、安全率 0.85 で計算)
     - run0 partial は **primary 5 runs matrix から外す** (Codex H2: prefix
       censoring で memory growth / fatigue / prompt-length の late-run signal
       系統欠落)、`data/eval/partial/` 隔離 + `partial_capture=true` sidecar 付き
       diagnostic 専用
     - run0 を 500 focal で **再採取** (CLI fix + audit CLI merge 完了後)
  3. **G-GEAR rescue verify (Phase A、本 ADR 確定後即時)**: `.tmp` +
     `.tmp.wal` 存在 + DuckDB read/count 検証を CLI fix 完了前に実施、結果を
     `.steering/20260430-m9-eval-system/blockers.md` の incident block に記録

- **根拠**:
  - empirical 観測: 3 cell wall=360 min で focal=381/390/399 (76-80% prefix
    censoring)、focal/hour ≈65、3-parallel contention 2.0x+ (事前推計 1.5x の
    1.33x 過小評価)
  - Codex `gpt-5.5 xhigh` review (`codex-review-phase2-run0-timeout.md`、
    281,778 tokens、Verdict: revise) で Claude 単独案の 4 HIGH 級欠陥切出:
    - H1 (480 min 不足): `65*8*0.85=442 < 500`、600 min 最低ライン
    - H2 (run0 primary 採用 NG): wall-time prefix censoring は random missing
      では無く、`width * sqrt(n / n_target)` (`scripts/p3a_decide.py:360` の
      iid sample-mean 近似) の前提崩壊
    - H3 (return 0 + canonical NG): HIGH-6 contract 違反、audit/analytics/
      training egress が誤採用するリスク
    - H4 (salvage-first NG): SIGKILL/OOM では `.tmp` も消失、stale `.tmp` は
      次回起動で `unlink()`
  - DuckDB doc: CHECKPOINT は WAL を main file 同期、CLI close も persistent
    DB を checkpoint/close (Python `finally` 到達時のみ保証)

- **棄却**:
  - **Claude 単独案の 480 min budget continuation** (Codex H1) — 500 未達
    濃厚で再 timeout 連鎖
  - **Claude 単独案の sample-size correction で run0 primary 採用** (Codex H2) —
    censoring 構造を無視した補正で late-run signal が体系的欠落
  - **Claude 単独案の return 0 + canonical publish** (Codex H3) — partial と
    complete の機械的区別不能、HIGH-6 contract 違反
  - **salvage-first hybrid** (Codex H4) — `.tmp` は graceful path 限定保証で
    SIGKILL/OOM 時に消失、CLI fix 完了前の run1 launch は同じ事故再発リスク
  - **C 案 (turn=400 spec 下方修正)** — P3 spec stage 2 close 済 (PR #134) を
    本 incident で覆すのは不適切、IPIP-NEO ICC sample size に余分な影響
  - **D 案 (sequential 直列 wall=480)** — 1 cell 4.35h × 15 = 65h、2 overnight
    で収まらず M9 milestone 全体延伸過大

- **影響**:
  - 新規タスク `m9-eval-cli-partial-fix` (`/start-task` で起票) で CLI fix +
    `eval_audit` CLI を実装、本タスクから独立 PR 化
  - 本タスク内では G-GEAR rescue verify (Phase A) のみ実施、run1 calibration
    と run2-4 採取は CLI fix merge 後に再開
  - `g-gear-p3-launch-prompt.md` 更新: wall budget guidance + run1 calibration
    step 追加
  - `data/eval/partial/` directory 新設 (run0 partial 隔離保存先)
  - Phase 2 deadline 延伸 (推定 1-2 week、CLI fix PR + run1 calibration +
    run0 再採取の累積)

- **re-open 条件**:
  - G-GEAR で `.tmp` 全消失 → run0 partial 救出不可、`partial/censored` 解析
    自体を skip (本 incident close 条件のみ満たして次へ)
  - run1 calibration で 120-min 単位 focal/hour rate が 65 を大きく外れる
    (例: ≤55 / ≥80) → COOLDOWN_TICKS_EVAL や cognition_period の再調整 ADR
    起票 (本 ADR の child)
  - CLI fix 実装中に Codex の追加 HIGH 切出 → fix 設計の Plan + /reimagine で
    再収束、本 ADR 改訂

### Amendment 2026-05-07 — trigger zone の rate basis 明示 (擬陽性 trigger 修正)

**根拠**: PR #141 merge 後の G-GEAR run1 calibration が cell 100 (wall=120 min、
focal=195、rate=1.625/min ≈ 97.5/h) と cell 101 (wall=240 min、focal=383、
rate=1.596/min ≈ 95.75/h) で **ME-9 trigger ≥80/h に該当**し、G-GEAR Claude が
正規 STOP した。しかし Codex 9 回目 review (`.steering/20260507-m9-eval-
cooldown-readjust-adr/codex-review-trigger-interpretation.md` verbatim、
81,541 tok、Verdict: hybrid A/C) で **擬陽性 trigger** と判定:

- 65/h trigger は **run0 incident の 3-parallel rate basis** 由来 (Codex H1 の
  `65 × 8 × 0.85 = 442` 算出時の文脈)
- run1 calibration は **kant single** で実行のため、observation の rate basis
  が違う。本 amendment で明示する
- pilot single (1.875/min) と run100/101 (1.625/1.596/min) は wall-duration
  効果 (memory pressure 累積) で説明可能、`COOLDOWN_TICKS_EVAL=5` の失敗証拠
  ではない

**修正後の trigger zone**:

| context | rate basis | central zone | trigger zone |
|---|---|---|---|
| **single calibration** (kant のみ、run_idx=100..104) | direct observation | 1.55-1.87 /min (= 93-112 /h) | < 1.20 /min or > 2.20 /min (= < 72 /h or > 132 /h) |
| **3-parallel production** (kant+nietzsche+rikyu、run_idx=0..4) | direct observation | 0.92-1.20 /min (= 55-72 /h) | < 0.55-0.92 /min or > 1.20-1.33 /min (= < 33-55 /h or > 72-80 /h) |

single → parallel 換算の contention factor は **暫定 1.5-1.76× の bracket**
(pilot 16 min vs run0 360 min の mixed effect が含まれる、wall-aligned 校正は
run102 (360 min single) 採取後に確定)。

**run100/101 の評価 (amendment 適用後)**:
- single calibration central zone (1.55-1.87/min) の **下限内**、擬陽性ではない
- v2 prompt §Phase A.4 の linear 期待値 table は saturation model に更新
  (Codex M1)、600 min single は 1.55-1.59/min が central 予測

**新 child ADR の起票要否**: COOLDOWN_TICKS_EVAL や cognition_period の再調整は
**不要** (Codex Q3 棄却)。run102 採取で contention factor を再校正、run2-4 wall
budget を確定する流れで M9 Phase 2 を継続。

**反映先**:
- v2 prompt (`g-gear-p3-launch-prompt-v2.md`) の §Phase A.4 期待値 table と

exec
/bin/zsh -lc "sed -n '80,150p' .steering/20260430-m9-eval-system/design-final.md && sed -n '240,275p' .steering/20260430-m9-eval-system/design-final.md && sed -n '390,455p' .steering/20260430-m9-eval-system/design-final.md && sed -n '500,610p' .steering/20260430-m9-eval-system/design-final.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
- Parquet export は `COPY ... TO ... (FORMAT PARQUET)` で zero-copy
- Tier A pure function は DuckDB Python API で columnar 取得 → numpy で計算
- 7500 turn × N metric の bootstrap resample も DuckDB 内で完結

### LIWC alternative: Option D (Big5 全面 IPIP-NEO 移管、LIWC 全廃) — v2 採用

**Option D 確定**:
- Big5 stability ICC は **IPIP-NEO 自己申告 self-report のみ** に依拠 (Tier B、agent
  に local 7B-Q4 が IPIP-NEO 短縮版 120 item を質問・回答)
- stylometric 一致は Burrows Delta (Tier A)
- persona-fit textual diversity は Vendi (Tier B)
- Empath は **secondary diagnostic** として Tier A の psycholinguistic axis 1 つに
  採用、**Big5 claim には使わない**
- これで `blockers.md` の LIWC license defer が **即時 close** (Option D 採用)

**根拠**:
- blockers.md DB10 honest framing "LIWC OSS proxy で Big5 claim は honest に避ける"
  と完全整合
- LIWC license decision tree を node ごと刈り取れる (work cost zero)
- IPIP-NEO は psychometric literature で Big5 推定の standard、self-report bias は
  周知だが well-documented
- spaCy 自前 dictionary (Option C) は category 設計 + validation に数日〜数週間の
  work cost、solo で完結させる現実性が低い

**self-report bias 対策 (v2 リスク 3 への補強)**:
ICC < 0.6 が頻発した場合の **conditional fallback** を `decisions.md` に re-open
条件として明記:
- BIG5-CHAT regression head を Tier B に追加し second opinion 化
- defer ではなく conditional fallback として記録 (発火条件を事前明文化)

### Golden baseline 採取: Hybrid (200 stimulus + 300 自然対話) — v2 採用、比率は pilot で defer 解消

**500 turn/run の構成**:
- 最初の **200 turn**: curated stimulus battery を fixed order で投入
  - Wachsmuth Toulmin 引き出す prompt: 30
  - ToM info-asymmetric scenario (chashitsu): 20
  - RoleEval-adapted **persona-specific biographical / thought-history MCQ**: 10
    (within-persona floor diagnostic、cross-persona absolute accuracy は DB9 比較指標に
    使わない。詳細 ADR は `decisions.md` ME-7、Codex review reflection は
    `codex-review-low1.md`)
  - persona-conditional moral dilemma: 10
  - 計 70 stimulus × 3 巡 = 210 turn (端数 10 turn は最後 stimulus を切り詰め)
- 残り **300 turn**: 既存 `InMemoryDialogScheduler` の自然対話 (peripatos / chashitsu /
  agora / garden の場の遷移を含む)

**根拠**:
- 純自然対話 baseline は drift gate baseline noise が大きい (topic 効果と style
  効果が混在)
- 純 stimulus baseline は ζ 軸 (mode 遷移) を測れず M9-A event-boundary observability
  と契約不整合
- hybrid で両得: stylometric reference の統制 + persona の場の対応観察

**比率 defer (微調整 1、Codex HIGH-3 で順序修正)**:
- 元案: P3 採取後に P3b で 50 turn pilot → 比率変更時 7500 turn 再採取の risk
- **修正後**: P3 の前に **P3a (200 turn × 両形式 × 3 persona の isolated pilot)** を
  挟み、bootstrap CI width が小さい比率を empirical 確定してから P3 採取に入る
  (Codex HIGH-3: "P3b is ordered after the data it is supposed to tune")
- 50 turn では Vendi の expected window 200 turn が満たされず統計力不足
  (Codex HIGH-3 evidence: Vendi は kernel/eigenvalue based、sample 必要)
- P3a は **fresh scheduler / store / seed** で golden baseline (P3) と完全分離、
  pilot 結果が baseline state に carry-over しないことを test 化
- 結果は `decisions.md` の ratio ADR に記録 (defer 解消)

### Orchestrator: 既存 scheduler に minimum patch + 外部 golden driver (Codex HIGH-4 反映)

**新規 wrapper を新設しない**。既存 `src/erre_sandbox/integration/dialog.py` の
`InMemoryDialogScheduler` に **`golden_baseline_mode: bool = False` 引数のみ**を追加
(cooldown / timeout bypass)。default `False` で既存全テスト pass。

**stimulus 投入は外部 golden driver から公開 API 経由** (Codex HIGH-4 反映、元案の
"scheduler input queue に push" は scheduler に該 surface が無いため棄却):
    test text の同 function word 頻度を z-score → reference の z-score との差の
    絶対値の和。元案の "function-word vector cosine" は cosine distance であって
    Delta 規格と異なる (Codex HIGH-5)。stylometry literature (R Journal stylo 2016,
    R Eder/Rybicki/Kestemont) に準拠
  - `mattr.py` — Moving Average Type-Token Ratio (window 100)
  - `nli.py` — DeBERTa-v3-base-mnli zero-shot NLI contradiction
  - `novelty.py` — MPNet embedding 距離 semantic novelty
  - `empath_proxy.py` — Empath secondary diagnostic (Big5 claim には使わない)
- `tier_b/` directory:
  - `__init__.py`
  - `vendi.py` — Vendi Score (semantic kernel)
  - `ipip_neo.py` — IPIP-NEO 短縮版 agentic loop (local 7B-Q4)
  - `big5_icc.py` — Big5 stability ICC (run × mode で計算)
- `tier_c/` directory:
  - `__init__.py`
  - `prometheus.py` — Prometheus 2 client (Ollama HTTP)
  - `geval.py` — G-Eval logit-weighted scoring
  - `bias_mitigation.py` — position-swap / length-norm / two-judge protocol
- `bootstrap_ci.py` — **hierarchical bootstrap** (Codex HIGH-2 反映): outer level
  で run を cluster として resample (5 run × 3 persona = 15 cluster)、inner level で
  各 500-turn run 内に **circular block bootstrap** (Politis-Romano stationary block
  variant) を適用、block length は P3b pilot の autocorrelation で決定 (default 50)。
  Tier B per-100-turn metric は cluster-only resample (各 persona あたり 25 window
  しか無い = effective sample size 小、CI が広がる事実を report で明示)。
  3 sub-metric quorum logic は decision layer (M9-C-adopt)。`numpy` + `arch`
  (時系列 bootstrap 標準) または `scipy.stats.bootstrap` の独自 wrapper で実装
- `golden_baseline.py` — stimulus battery YAML loader + run 駆動 (既存 scheduler に
  push)
- `reference_corpus/` — Kant 独+英訳、Nietzsche、Rikyu、synthetic 4th persona の
  function-word vector pickle

CLI (`src/erre_sandbox/cli/`):
- `eval_ingest.py` — sqlite dialog_turns → DuckDB raw_dialog ingest
- `eval_tier_a.py` — Tier A post-hoc 計算
- `eval_tier_b.py` — Tier B post-hoc 計算 (G-GEAR 実行)
- `eval_tier_c.py` — Tier C nightly judge (systemd-timer から呼ばれる entry)

- sentence-transformers の HuggingFace deprecation 群を **局所的に**
  `filterwarnings ignore` で許可 (test 全体には影響させない、`@pytest.mark.filterwarnings`
  decorator で限定)

## 既存パターンとの整合性

- **Pure-function metric pattern**: `evidence/metrics.py` の `compute_*` 関数群と
  `aggregate(db_path)` パターンを Tier A 5 metric / Tier B 3 metric にも踏襲
- **CLI subcommand**: 既存 `cli/{baseline_metrics,scaling_metrics,export_log}.py` の
  argparse + JSON/JSONL out パターンを `eval_*` 6 CLI に踏襲、`schema: "<name>_v1"` 慣例
- **Pydantic frozen contracts**: `contracts/thresholds.py` の frozen pattern を
  `eval_thresholds.py` に踏襲 (`model_config = ConfigDict(extra="forbid", frozen=True)`)
- **Persona YAML additive**: `schema_version="0.10.0-m7h"` 維持、既存 field 不変、
  `ipip_neo_short` のみ optional 追加。`_synthetic_4th.yaml` も同じ schema
- **MemoryStore 経由**: `memory/store.py` の `iter_dialog_turns()` で turn 取得し、
  `eval_ingest` CLI で DuckDB raw_dialog schema に投入
- **inference/sampling.py** の `compose_sampling()` override → IPIP-NEO 質問時に
  override で deterministic (temperature=0.0) に切替

## テスト戦略

### Contract gate (実装中、pytest)

1. **DB5 schema-guard**: `tests/test_evidence/test_eval_paths_contract.py` で
   training loader が `metrics` schema を SELECT したら明示的
   `EvaluationContaminationError` raise を確認
2. **CI grep gate**: `.github/workflows/ci.yml` で training loader path に
   `metrics.` を grep 検出したら fail
3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
   resample N=1000、95% CI が解析解 ± 5% 内。加えて **AR(1) 合成 turn metric** を
   生成し、iid resample と block bootstrap で CI width が体感的に異なることを
   `test_bootstrap_ci.py` で fixture 化 (Codex HIGH-2 / verification suggestion 反映)
4. **Frozen snapshot**: `eval_thresholds` 改変時の合意 trail を snapshot test で要求

### DB7 LOW-1 (synthetic 4th persona heldout fixture)

- `personas/_synthetic_4th.yaml`: Big5 が 3 既存 persona と直交する架空 thinker
- `test_golden_baseline.py` で 4 persona scenario を Tier A pipeline に通し、3-persona
  overfitting (3-only assumption が出たら fail) を防ぐ

### Tier acceptance (実装後、pytest)

- `test_tier_a/`: 5 metric が synthetic + 4th persona heldout で NaN/crash 無く計算、
  Burrows Delta が persona-discriminative (Kant ≠ Nietzsche、distance 差 ≥ fixed delta)
- `test_tier_b/`: 3 metric が known distribution で expected 値、IPIP-NEO loop が
  deterministic temperature=0 で stable
- `test_tier_c/`: bias mitigation hook (position-swap / length-norm) が判定不変性を
  保つかを fixture pair で確認

### Burrows multi-lang (blockers.md 暫定方針)

- per-language reference でしか比較しない契約を test 化 (cross-lang を呼ぶと例外)

### Golden baseline integrity (G-GEAR run 後、CLI)

- `python -m erre_sandbox.cli.eval_audit data/eval/golden/*.duckdb`:
  - 3 persona × 5 run × 500 turn = 7500 turn 完全性確認
  - metrics sidecar の `(run_id, persona_id, turn_idx)` で raw に LEFT JOIN して
    miss が無いこと確認
- `python -m erre_sandbox.cli.eval_report --bootstrap-ci`:
  - DB9 sub-metric 3 個に CI 数値、persona-discriminative 観察を `blockers.md`
    L89-93 に追記 (defer 解消)

## ロールバック計画

5. **Tier C judge LLM の VRAM contention 検出失敗**
   - Prometheus 2 8x7B Q4 (~14 GB) + 万一 ollama qwen3 が leak で常駐 (FP16 16 GB)
     → OOM
   - 反復: systemd unit の preflight に `nvidia-smi --query-gpu=memory.free` チェッ
     ク、free < 14 GB なら skip + log

### Codex 独立 review 結果サマリ (詳細は `codex-review.md` 全文 verbatim)

| 項目 | Severity | 反映先 | Status |
|---|---|---|---|
| Schema guard executable boundary (sentinel test + constrained relation) | HIGH-1 | design.md §DuckDB / `tests/test_evidence/test_eval_paths_contract.py` | ✅ 反映済 |
| Hierarchical bootstrap (cluster runs + circular blocks) | HIGH-2 | design.md §bootstrap_ci.py / test_bootstrap_ci.py | ✅ 反映済 |
| Pilot ordering: P3a を P3 前に移動、200 turn × 両形式 isolated | HIGH-3 | design.md Hardware allocation table | ✅ 反映済 |
| Stimulus injection は公開 API 経由 (input queue 不存在) | HIGH-4 | design.md §Orchestrator / `evidence/golden_baseline.py` | ✅ 反映済 |
| Burrows Delta = z-scored function-word L1 (cosine ではない) | HIGH-5 | design.md §burrows.py 定義 | ✅ 反映済 |
| IPIP fallback trigger operational definition | MEDIUM-1 | `decisions.md` ME-1 ADR | ✅ ADR 化 |
| DuckDB snapshot semantics (CHECKPOINT + temp+rename + read_only) | MEDIUM-2 | design.md Hardware allocation P3 + `decisions.md` ME-2 | ✅ 反映済 |
| Tier C lock TOCTOU + Persistent= 決定 | MEDIUM-3 | `decisions.md` ME-3 ADR | ✅ ADR 化 |
| Dependency placement: heavy ML deps を eval extras 隔離 | MEDIUM-4 | design.md §pyproject.toml | ✅ 反映済 |
| RNG seed: hashlib.blake2b で uint64、`hash()` 棄却 | MEDIUM-5 | design.md §RNG seed 戦略 | ✅ 反映済 |
| Burrows token floor: corpus QC 化 (固定 50K → ≥5K-word chunk stability) | MEDIUM-6 | `decisions.md` ME-6 ADR / `blockers.md` reopen 条件 | ✅ ADR 化 |
| RoleEval Kant 限定 vs persona-specific MCQ 区別 | LOW-1 | `blockers.md` defer | ✅ defer |

---

## 設計判断の履歴

- **初回案 (`design-v1.md`)**: 別 Parquet file 物理分離 / pyarrow + polars / LIWC
  Option C (spaCy + 自前 dict) / 新規 wrapper Orchestrator / Tier A live per-turn /
  asyncio + file-lock
- **再生成案 (v2)**: DuckDB 単 file + schema-guard / DuckDB 単独 / LIWC Option D /
  既存 scheduler minimum patch / 全 post-hoc / systemd-timer + flock / Hybrid baseline
- **比較**: `design-comparison.md` 参照
- **採用**: **ハイブリッド (v2 ベース + v1 補強 2 点 + 微調整 2 点)**
- **根拠**:
  - データ層は v2 (DuckDB schema-guard + CI grep gate の 3 層 defense が path 規約より
    厳格)
  - LIWC は v2 Option D (blockers.md 1 件 close + work cost zero + DB10 honest framing
    と完全整合)
  - Orchestrator は v2 minimum patch (scheduler 不変条件維持、新 layer 創設の cost 回避)
  - 計算 timing は v2 全 post-hoc (DB6 厳守、live inference 不負荷)
  - **v1 補強 1**: metric file 構造を `evidence/tier_a/` sub-module 化 (`tier_a.py`
    単 file は 800+ 行で review-friendly でない)
  - **v1 補強 2**: Hardware allocation は v1 の Phase 区分形式 (subtask flat より
    依存関係 / 同期点が table から読める、`tasklist.md` の `[Mac]` / `[GG]` /
    `[Mac→GG]` tag 付与に直結)
  - **微調整 1**: Hybrid baseline 比率 200/300 は default で start、P3b pilot で
    empirical 調整、`blockers.md` に defer 解消記録
  - **微調整 2**: Tier C nightly は systemd-timer **単独**、Mac launchd → ssh
    trigger は採用しない (構成最小化、master/agent 責務分離は将来 ablation で再検討)
- **Codex review 完了 (2026-04-30)**: HIGH 5 / MEDIUM 6 / LOW 1。HIGH 全件を本文に
  反映、MEDIUM は `decisions.md` に 5 要素 ADR、LOW は `blockers.md` に defer。
  本ファイルを `design-final.md` に rename して Phase P0 に入る。
- **次工程**: P0a (LIWC Option D 確定 → blockers close) → P0b (`contracts/eval_paths.py`
  + sentinel CI test) → P0c (`evidence/eval_store.py` の `RawTrainingRelation`) →
  P1a (Tier A sub-module、Burrows は z-score Delta で実装) → P2c (external golden
  driver) → P3a (200 turn isolated pilot) → P3a-decide (ratio 確定) → P3 (golden
  baseline 採取) の依存順。

## Codex review HIGH 反映履歴

### 2026-04-30 — Codex `gpt-5.5 xhigh` (`codex-review.md`)

**Summary verdict**: "Proceed with HIGH fixes before P0a. Lowest-cost wins:
move P3b before P3, replace `hash()` seeds, and make training/eval dependency
boundaries executable."

**HIGH-1 反映** — Schema guard executable boundary:
- `connect_training_view()` の返り値を **`RawTrainingRelation`** (constrained
  relation) に変更、生 DuckDB connection を返さない
- 任意 SQL を必要とする caller には `export_raw_only_snapshot(out_path)` で
  raw-only Parquet snapshot を取らせる
- `tests/test_evidence/test_eval_paths_contract.py` に **sentinel metric rows**
  ("M9_EVAL_SENTINEL_*" 文字列) を埋めた fixture を追加、全 training egress 経路
  (含む既存 `cli/export_log.py`) を sentinel test 範囲に含める
- CI grep gate は補強層 (静的) として維持、sentinel test を真の boundary に格上げ

**HIGH-2 反映** — Hierarchical bootstrap:
- `bootstrap_ci.py` を hierarchical bootstrap (outer: run cluster resample / inner:
  circular block bootstrap) に specify
- block length は P3a pilot の autocorrelation で empirical 決定 (default 50)
- Tier B per-100-turn metric は cluster-only resample (effective sample size 25
  window/persona と report で明示)
- `test_bootstrap_ci.py` に AR(1) 合成 turn metric fixture を追加、iid vs block CI
  width の差を test 化

**HIGH-3 反映** — Pilot ordering:
- 元 P3 (golden 採取) → P3b (50 turn pilot) の順を **P3a (200 turn × 両形式 ×
  3 persona isolated pilot) → P3a-decide (ratio ADR) → P3 (golden 採取)** に修正
- 50 turn では Vendi の 200 turn window 不足、最小 200 turn/condition/persona
- P3a は fresh scheduler / store / seed で完全分離、carry-over 防止 test 化

**HIGH-4 反映** — Stimulus injection without input queue:
- `InMemoryDialogScheduler` に input queue surface が無い事実を確認
  (`schedule_initiate` / `record_turn` / `close_dialog` / `tick` のみ公開)
- 元案の "scheduler input queue に push" を棄却、外部 `GoldenBaselineDriver` が
  公開 API のみで stimulus を駆動する形に変更
- scheduler への patch は `golden_baseline_mode: bool = False` のみに縮小
  (cooldown/timeout bypass)、turn_sink は既存 M8 L6-D1 の sink を再利用
- driver の dry-run test (1 stimulus + 70 stimulus battery) を P2c に追加

**HIGH-5 反映** — Burrows Delta correction:
- `evidence/tier_a/burrows.py` の定義を "function-word vector cosine" から
  **"z-scored function-word frequency vector の L1 (Manhattan) 距離"** に修正
- stylometry literature (R Journal stylo 2016, Eder/Rybicki/Kestemont) 準拠
- DB9 quorum sub-metric の名称は "Burrows Delta" のまま (M9-B `decisions.md`
  DB9 と整合)、内部実装を Delta 規格に合わせる

**MEDIUM 6 件は `decisions.md` (新規) に 5 要素 ADR として記録、LOW 1 件は
`blockers.md` (新規、m9-eval-system 配下) に defer。** 詳細はそれぞれの file。


exec
/bin/zsh -lc "sed -n '1,140p' src/erre_sandbox/evidence/tier_a/novelty.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,120p' src/erre_sandbox/evidence/tier_a/empath_proxy.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""Empath secondary diagnostic — psycholinguistic category vector.

Empath (Fast et al. 2016) is a deep-learning category lexicon that maps
text to ~200 affective / topical categories ("anger", "ritual",
"violence", ...). The M9 design uses Empath as **one Tier A axis**
among the five — a coarse signal of which themes a persona spends
words on, useful for descriptive contrast between Kant's "law" /
"order" / "duty" register and Nietzsche's "war" / "art" / "power"
register.

**Big5 claim is explicitly NOT made.** ME-1 in the design's
``decisions.md`` keeps Big5 self-report on IPIP-NEO via Tier B; using
Empath as a Big5 estimator was the v1 sketch and was rejected. The
secondary-diagnostic role lets the metric still earn its keep without
inheriting the LIWC-shaped problems Empath was originally critiqued
for.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

EmpathAnalyzer = Callable[[Sequence[str]], dict[str, float]]
"""Stub-friendly callable: take a list of utterances, return a category
score dict (category → mean / normalized intensity over the batch).

The single-callable boundary lets unit tests inject a deterministic
score map without spinning up the Empath lexicon (which downloads a
pickle on first use).
"""


def compute_empath_proxy(
    utterances: Sequence[str],
    *,
    analyzer: EmpathAnalyzer | None = None,
) -> dict[str, float]:
    """Return the Empath category-score vector aggregated over utterances.

    Args:
        utterances: Sequence of turn texts to analyse together. Empty
            input returns an empty dict; the caller is responsible for
            treating "no measurement" as it sees fit (Tier A
            aggregation typically drops empty maps before bootstrap).
        analyzer: Optional stub callable. When ``None`` the default
            Empath lexicon is lazily loaded; tests should always pass
            a stub to keep the lexicon download out of CI.

    Returns:
        Dict mapping Empath category name → score. Score units depend
        on the analyzer (the default returns normalized intensities in
        ``[0, 1]``); the metric layer treats this as opaque since the
        downstream Tier A consumer just ranks personas by category.
    """
    if not utterances:
        return {}
    fn = analyzer if analyzer is not None else _load_default_analyzer()
    return dict(fn(list(utterances)))


def _load_default_analyzer() -> EmpathAnalyzer:
    """Lazy-load the Empath lexicon and wrap ``analyze()`` as a callable.

    Heavy import deferred so importing this module without ``[eval]``
    extras stays free.
    """
    from empath import Empath  # noqa: PLC0415  # heavy data dep behind eval extras

    lex = Empath()

    def analyzer(batch: Sequence[str]) -> dict[str, float]:
        joined = " ".join(batch)
        # ``Empath.analyze`` returns ``Mapping[str, float] | None``;
        # an empty input or unknown vocabulary yields ``None``, which
        # we surface as an empty dict for type-stable callers.
        result = lex.analyze(joined, normalize=True)
        if result is None:
            return {}
        return {str(k): float(v) for k, v in result.items()}

    return analyzer

 succeeded in 0ms:
"""Semantic novelty — mean cosine distance to running prior centroid.

For every turn after the first, embed the utterance with MPNet
(``sentence-transformers/all-mpnet-base-v2``) and compare it to the
average direction of all prior turns. A persona that keeps cycling
through the same idea collapses toward zero; a persona that
genuinely introduces new content yields persistent positive distance.

The pure-numpy aggregation step is kept stub-friendly via the
``encoder`` keyword. Tests inject a fixed embedding fixture so the
heavy ``sentence-transformers`` import never fires unless the caller
asked for the real model. Numpy is a core dependency, so the metric
itself stays lightweight.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

NoveltyEncoder = Callable[[Sequence[str]], list[list[float]]]
"""Stub-friendly callable shape: take a list of strings, return a list of
embeddings (one per string, fixed dimensionality).

Returning plain ``list[list[float]]`` rather than ``np.ndarray`` keeps
test fixtures readable and avoids forcing the encoder implementation
to use numpy (an Ollama-served embedding service, for example, can
return Python lists directly).
"""


def compute_semantic_novelty(
    utterances: Sequence[str],
    *,
    encoder: NoveltyEncoder | None = None,
) -> float | None:
    """Mean cosine distance between each turn embedding and prior centroid.

    Args:
        utterances: Ordered sequence of turn utterances. The first turn
            has no prior centroid so it does not contribute; subsequent
            turns each contribute one cosine-distance value.
        encoder: Optional stub callable. When ``None`` the default
            MPNet encoder is lazily loaded; tests should always pass a
            stub.

    Returns:
        ``None`` when fewer than 2 utterances are available (no prior
        centroid to compare against). Otherwise the mean cosine
        distance ``1 - cos(emb_i, mean(emb_0..i-1))`` across
        ``i = 1..n-1``. Values are in ``[0, 2]`` because cosine
        similarity ranges over ``[-1, 1]``.
    """
    if len(utterances) < 2:  # noqa: PLR2004 — contract: need ≥2 turns
        return None
    fn = encoder if encoder is not None else _load_default_encoder()
    raw = fn(list(utterances))
    if not raw:
        return None
    matrix = np.asarray(raw, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != len(utterances):  # noqa: PLR2004 — 2D embedding matrix expected
        raise ValueError(
            f"encoder returned shape {matrix.shape}, expected 2D with"
            f" {len(utterances)} rows",
        )

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    safe_norms = np.where(norms == 0, 1.0, norms)
    unit = matrix / safe_norms

    distances: list[float] = []
    for i in range(1, len(unit)):
        prior_mean = unit[:i].mean(axis=0)
        prior_norm = float(np.linalg.norm(prior_mean))
        if prior_norm == 0.0:
            # Antipodal prior turns cancelled; treat as max novelty
            # (1.0) rather than NaN so downstream aggregation still
            # produces a number on pathological synthetic inputs.
            distances.append(1.0)
            continue
        prior_unit = prior_mean / prior_norm
        cos_sim = float(np.dot(unit[i], prior_unit))
        distances.append(1.0 - cos_sim)

    if not distances:
        return None
    return float(sum(distances) / len(distances))


def _load_default_encoder() -> NoveltyEncoder:
    """Lazy-load ``sentence-transformers/all-mpnet-base-v2``.

    Heavy import deferred until the caller actually needs the real
    embedding model — keeps the module importable without
    ``[eval]`` extras.
    """
    from sentence_transformers import (  # noqa: PLC0415  # heavy ML dep behind eval extras
        SentenceTransformer,
    )

    model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

    def encoder(batch: Sequence[str]) -> list[list[float]]:
        encoded = model.encode(list(batch), show_progress_bar=False)
        return [list(map(float, vec)) for vec in encoded]

    return encoder

exec
/bin/zsh -lc "sed -n '1,390p' src/erre_sandbox/evidence/bootstrap_ci.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""Bootstrap confidence intervals for Tier A / Tier B metric aggregates.

m9-eval-system P5 (Codex HIGH-2 in `codex-review.md`): hierarchical
bootstrap with **outer cluster (run) + inner block (circular block of
turn-level samples)** for autocorrelation-aware CI estimation. The DB9
quorum semantics in `design-final.md` requires CI width per
sub-metric to gate ratio confirmation.

This module was drafted in P3a-decide (ahead of the formal P5 phase) so
the stimulus-side ratio sanity-check could run on the pilot DuckDB files
once they were rsync'd from G-GEAR. The P5 hardening pass adds:

* :func:`estimate_block_length` — Politis-White-inspired autocorrelation
  probe that returns a heuristic block length capped at ``max_block``.
  White-noise series collapse to ~1; strong AR(1) series grow toward
  ``max_block``.
* ``cluster_only`` flag on :func:`hierarchical_bootstrap_ci` — skips
  the inner block entirely and resamples whole clusters (used by the
  Tier B per-100-turn metric where the 25 windows / persona means the
  effective sample size is the cluster count and per-window
  autocorrelation is not measured).
* ``auto_block`` flag on :func:`hierarchical_bootstrap_ci` — passes the
  pooled stream through :func:`estimate_block_length` to pick the
  inner-block size at call time.

Quick reference:

* :func:`bootstrap_ci` — minimum viable percentile bootstrap. Pure
  numpy, deterministic under explicit ``seed``. Works for the P3a-decide
  use-case (per-cell aggregate metrics, no within-cell autocorrelation
  to model because each cell is one persona run).
* :func:`hierarchical_bootstrap_ci` — outer cluster + inner block
  resampling. Used by P3 / P3-validate when there are 5 runs × 500
  turns per persona; the inner block protects the CI from
  underestimating standard error when consecutive turns are correlated.
* :func:`estimate_block_length` — automatic block-length picker for the
  ``auto_block`` path of :func:`hierarchical_bootstrap_ci`.

All helpers return :class:`BootstrapResult` so plotting / quorum gates
can read ``point / lo / hi / width`` uniformly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_N_RESAMPLES: int = 2000
"""Default bootstrap iteration count.

2000 is enough for percentile CI stability at width <0.005 for
N>=30 sample sizes — the M8 baseline metric pipeline used the same
budget and shipped without observability complaints. For DB9 ratio
gating the stability matters more than the iteration count, so the
parameter is exposed and the script overrides up to 10K when running
overnight.
"""

DEFAULT_CI: float = 0.95
"""Default 2-sided percentile CI (95%)."""

MIN_SAMPLE_SIZE: int = 10
"""Minimum sample size for block-length estimation.
Samples with fewer finite values fall back to block length 1.
"""


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Bootstrap CI summary returned by every public helper here."""

    point: float
    """The point estimate computed from the original (un-resampled) sample."""
    lo: float
    """Lower percentile bound."""
    hi: float
    """Upper percentile bound."""
    width: float
    """``hi - lo``. Pre-computed because callers compare widths directly
    (DB9 quorum, ME-4 ratio decision) and the dataclass is frozen so
    storing the derived value is safe."""
    n: int
    """Effective sample size used (after dropping NaN/None)."""
    n_resamples: int
    """Bootstrap iteration count."""
    method: str
    """One of ``"percentile"`` / ``"hierarchical-block"``. Surfaced in
    the JSON output so the consumer knows which estimator produced the
    interval."""


def _clean(values: Sequence[float | None]) -> np.ndarray:
    """Drop None / NaN entries and return a float array.

    Per the M8 ``compute_*`` contract, ``None``/``NaN`` mean "no
    measurement" rather than "zero". The bootstrap path drops those
    rows up front so the resampler does not propagate NaN.
    """
    cleaned = [
        float(v)
        for v in values
        if v is not None and not (isinstance(v, float) and math.isnan(v))
    ]
    return np.asarray(cleaned, dtype=float)


def bootstrap_ci(
    values: Sequence[float | None],
    *,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    ci: float = DEFAULT_CI,
    seed: int = 0,
    statistic: str = "mean",
) -> BootstrapResult:
    """Percentile bootstrap CI for ``statistic`` of ``values``.

    Args:
        values: Per-sample measurements (one per cell / turn / item).
            ``None``/``NaN`` entries are dropped via :func:`_clean`.
        n_resamples: Bootstrap iteration count.
        ci: Two-sided coverage in ``(0, 1)``.
        seed: Deterministic bitstream seed (``np.random.default_rng``).
        statistic: Either ``"mean"`` (default) or ``"median"``. The
            quorum thresholds in `design-final.md` use means, so the
            default is mean.

    Returns:
        :class:`BootstrapResult` with ``method="percentile"`` and
        ``n`` reflecting the sample size after dropping NaN/None.

    Raises:
        ValueError: If ``ci`` is not in ``(0, 1)``, ``n_resamples < 1``,
            or ``values`` is empty after cleaning.
    """
    if not 0.0 < ci < 1.0:
        raise ValueError(f"ci must be in (0, 1) (got {ci})")
    if n_resamples < 1:
        raise ValueError(f"n_resamples must be >= 1 (got {n_resamples})")
    if statistic not in {"mean", "median"}:
        raise ValueError(f"statistic must be 'mean' or 'median' (got {statistic!r})")

    cleaned = _clean(values)
    n = cleaned.size
    if n == 0:
        raise ValueError("values has 0 finite entries — cannot bootstrap")

    rng = np.random.default_rng(seed)
    point = (
        float(np.mean(cleaned)) if statistic == "mean" else float(np.median(cleaned))
    )

    indices = rng.integers(0, n, size=(n_resamples, n))
    samples = cleaned[indices]
    if statistic == "mean":
        replicate_stats = samples.mean(axis=1)
    else:
        replicate_stats = np.median(samples, axis=1)

    alpha = 1.0 - ci
    lo = float(np.quantile(replicate_stats, alpha / 2.0))
    hi = float(np.quantile(replicate_stats, 1.0 - alpha / 2.0))
    return BootstrapResult(
        point=point,
        lo=lo,
        hi=hi,
        width=hi - lo,
        n=n,
        n_resamples=n_resamples,
        method="percentile",
    )


def estimate_block_length(
    values: Sequence[float | None],
    *,
    max_block: int = 100,
) -> int:
    """Heuristic block length for circular-block bootstrap.

    Inspired by Politis-White (2004) automatic block-length selection: walks
    the sample autocorrelation function and returns the first lag at which
    ``|ρ̂(k)|`` falls below the noise floor ``2 / sqrt(n)``. White-noise-like
    series collapse to ~1; persistent AR-style series grow toward
    ``max_block``.

    The probe horizon is ``min(n // 4, ⌈5 · log10(n)⌉)`` so the routine is
    cheap (O(n · log10 n)) and the cap matches the rule-of-thumb upper
    bound for stationary block bootstrap (block ≤ ``n / 4``).

    Args:
        values: 1D sequence (NaN/None dropped via :func:`_clean`).
        max_block: Hard upper bound on the returned block length. Useful
            when the caller wants to cap the cost of inner-block resampling.

    Returns:
        Integer block length in ``[1, min(max_block, max(1, n // 4))]``.
        Returns 1 for series shorter than 10 finite samples or with zero
        variance (constant series).
    """
    if max_block < 1:
        raise ValueError(f"max_block must be >= 1 (got {max_block})")
    cleaned = _clean(values)
    n = cleaned.size
    if n < MIN_SAMPLE_SIZE:
        return 1

    centered = cleaned - cleaned.mean()
    var = float((centered * centered).mean())
    if var == 0.0:
        return 1

    cap = max(1, n // 4)
    k_max = min(cap, max(1, int(5.0 * math.log10(max(n, 10)))))
    threshold = 2.0 / math.sqrt(n)

    for k in range(1, k_max + 1):
        rho_k = float((centered[: n - k] * centered[k:]).mean() / var)
        if abs(rho_k) < threshold:
            return min(max(1, k), max_block, cap)

    # Every probed lag was above the noise floor: hand back the largest
    # length we are willing to use without exceeding the n // 4 ceiling.
    return min(k_max, max_block, cap)


def _compute_effective_block_length(
    cleaned_clusters: list[np.ndarray],
    pooled: np.ndarray,
    block_length: int,
    *,
    cluster_only: bool,
    auto_block: bool,
) -> tuple[str, int]:
    """Determine effective block length and method label.

    Returns (method_label, effective_block_length).
    """
    if cluster_only:
        return "hierarchical-cluster-only", block_length
    if auto_block:
        per_cluster_cap = max((c.size for c in cleaned_clusters), default=1)
        effective_block_length = estimate_block_length(
            pooled.tolist(),
            max_block=per_cluster_cap,
        )
        return "hierarchical-block", effective_block_length
    return "hierarchical-block", block_length


def _draw_one_replicate(
    cleaned_clusters: list[np.ndarray],
    rng: np.random.Generator,
    n_clusters: int,
    effective_block_length: int,
    *,
    cluster_only: bool,
) -> np.ndarray:
    """Draw one bootstrap replicate."""
    outer_idx = rng.integers(0, n_clusters, size=n_clusters)
    if cluster_only:
        return np.concatenate(
            [cleaned_clusters[ci_idx] for ci_idx in outer_idx],
        )
    replicate_concat: list[np.ndarray] = []
    for ci_idx in outer_idx:
        cluster = cleaned_clusters[ci_idx]
        cluster_n = cluster.size
        n_blocks = max(1, math.ceil(cluster_n / effective_block_length))
        starts = rng.integers(0, cluster_n, size=n_blocks)
        for s in starts:
            idx = (np.arange(effective_block_length) + s) % cluster_n
            replicate_concat.append(cluster[idx])
    return np.concatenate(replicate_concat)


def hierarchical_bootstrap_ci(
    values_per_cluster: Sequence[Sequence[float | None]],
    *,
    block_length: int = 50,
    cluster_only: bool = False,
    auto_block: bool = False,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    ci: float = DEFAULT_CI,
    seed: int = 0,
) -> BootstrapResult:
    """Cluster + circular-block bootstrap for autocorrelated turn streams.

    Use this for P3 golden-baseline 5 runs × 500 turns (Codex HIGH-2):
    the outer level resamples runs (clusters) with replacement, and the
    inner level draws circular blocks of length ``block_length`` so the
    within-run autocorrelation is preserved.

    Args:
        values_per_cluster: ``runs`` outer × ``turns`` inner — one
            sequence per run (cluster). NaN/None within a cluster are
            dropped (per :func:`_clean`); a cluster that ends up empty
            is dropped from the outer resample.
        block_length: Inner circular block length (turns). For 500-turn
            runs the literature default 50 covers ~1 effective sample
            per 10 blocks. Ignored when ``cluster_only=True``; replaced
            when ``auto_block=True``.
        cluster_only: When ``True``, skip the inner block step and
            concatenate the entire selected cluster verbatim per outer
            draw. Use this for Tier B per-100-turn windowed metrics
            where the 25 windows / persona means the effective sample
            size is the cluster count and within-window autocorrelation
            is not modelled.
        auto_block: When ``True`` (and ``cluster_only=False``), call
            :func:`estimate_block_length` on the pooled stream and use
            that estimate as the inner block length. ``block_length``
            is ignored in this mode.
        n_resamples: Bootstrap iteration count.
        ci: Two-sided coverage in ``(0, 1)``.
        seed: Deterministic seed.

    Returns:
        :class:`BootstrapResult`. ``method`` is
        ``"hierarchical-cluster-only"`` when ``cluster_only=True`` and
        ``"hierarchical-block"`` otherwise. ``n`` is the total number of
        finite turn-level observations across non-empty clusters.

    Raises:
        ValueError: On invalid arguments or all-empty clusters.
    """
    if not 0.0 < ci < 1.0:
        raise ValueError(f"ci must be in (0, 1) (got {ci})")
    if n_resamples < 1:
        raise ValueError(f"n_resamples must be >= 1 (got {n_resamples})")
    if block_length < 1:
        raise ValueError(f"block_length must be >= 1 (got {block_length})")

    cleaned_clusters = [_clean(cluster) for cluster in values_per_cluster]
    cleaned_clusters = [c for c in cleaned_clusters if c.size > 0]
    if not cleaned_clusters:
        raise ValueError("no finite values in any cluster")

    rng = np.random.default_rng(seed)
    pooled = np.concatenate(cleaned_clusters)
    point = float(pooled.mean())
    n_total = pooled.size
    n_clusters = len(cleaned_clusters)

    method_label, effective_block_length = _compute_effective_block_length(
        cleaned_clusters,
        pooled,
        block_length,
        cluster_only=cluster_only,
        auto_block=auto_block,
    )

    replicate_means = np.empty(n_resamples, dtype=float)
    for r in range(n_resamples):
        replicate = _draw_one_replicate(
            cleaned_clusters,
            rng,
            n_clusters,
            effective_block_length,
            cluster_only=cluster_only,
        )
        replicate_means[r] = float(replicate.mean())

    alpha = 1.0 - ci
    lo = float(np.quantile(replicate_means, alpha / 2.0))
    hi = float(np.quantile(replicate_means, 1.0 - alpha / 2.0))
    return BootstrapResult(
        point=point,
        lo=lo,
        hi=hi,
        width=hi - lo,
        n=n_total,
        n_resamples=n_resamples,
        method=method_label,
    )


__all__ = [
    "DEFAULT_CI",
    "DEFAULT_N_RESAMPLES",
    "BootstrapResult",
    "bootstrap_ci",
    "estimate_block_length",
    "hierarchical_bootstrap_ci",
]

exec
/bin/zsh -lc "sed -n '1,180p' src/erre_sandbox/evidence/eval_store.py && sed -n '180,280p' src/erre_sandbox/evidence/eval_store.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""DuckDB-backed evaluation store — m9-eval-system Phase 0 (P0b + P0c).

This module is the **implementation half** of the four-layer evaluation
contamination contract; the policy half lives in
:mod:`erre_sandbox.contracts.eval_paths`. The single training-egress
entry point is :func:`connect_training_view`, which opens a DuckDB file
read-only and returns a :class:`RawTrainingRelation` that exposes only
``raw_dialog`` rows — never the ``metrics`` schema, never an arbitrary
SQL execution surface.

P0c additions (this commit):

* :func:`bootstrap_schema` — idempotent CREATE for ``raw_dialog.dialog``
  and ``metrics.tier_{a,b,c}``. The raw column set is locked in lockstep
  with :data:`ALLOWED_RAW_DIALOG_KEYS` (module-load-time check).
* :class:`AnalysisView` + :func:`connect_analysis_view` — Mac-side
  read-only multi-schema reader for analytics / notebooks. NOT a
  training-egress route; the grep gate in CI keeps the metric schema
  reference confined to this module.
* :func:`export_raw_only_snapshot` — Parquet export of ``raw_dialog``
  only, the sanctioned route for callers that need ad-hoc SQL on raw
  rows (run the SQL against the snapshot, not the live file).
* :func:`write_with_checkpoint` and :func:`atomic_temp_rename` — the
  two ME-2 helpers that implement the G-GEAR → Mac snapshot semantics
  documented in
  ``.steering/20260430-m9-eval-system/decisions.md`` §ME-2.

Both :func:`connect_training_view` and :func:`connect_analysis_view`
open the underlying DuckDB file with ``read_only=True``. Any write
attempt against either handle (even via private attribute access) must
surface as a DuckDB error — the test suite covers both paths.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Self

import duckdb

from erre_sandbox.contracts.eval_paths import (
    ALLOWED_RAW_DIALOG_KEYS,
    METRICS_SCHEMA,
    RAW_DIALOG_SCHEMA,
    EvaluationContaminationError,
    RawTrainingRelation,
    assert_no_metrics_leak,
    assert_no_sentinel_leak,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterator, Mapping

RAW_DIALOG_TABLE: str = "dialog"
"""Table name inside :data:`RAW_DIALOG_SCHEMA` (qualified
``raw_dialog.dialog``).

Kept as a public constant so :func:`bootstrap_schema` and the contract
test agree on the same physical name.
"""

# ---------------------------------------------------------------------------
# Bootstrap DDL — column set locked in lockstep with the contract.
# ---------------------------------------------------------------------------

_RAW_DIALOG_DDL_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "TEXT"),
    ("run_id", "TEXT"),
    ("dialog_id", "TEXT"),
    ("tick", "INTEGER"),
    ("turn_index", "INTEGER"),
    ("speaker_agent_id", "TEXT"),
    ("speaker_persona_id", "TEXT"),
    ("addressee_agent_id", "TEXT"),
    ("addressee_persona_id", "TEXT"),
    ("utterance", "TEXT"),
    ("mode", "TEXT"),
    ("zone", "TEXT"),
    ("reasoning", "TEXT"),
    ("epoch_phase", "TEXT"),
    ("created_at", "TIMESTAMP"),
)

_BOOTSTRAP_COLUMN_NAMES: frozenset[str] = frozenset(
    name for name, _ in _RAW_DIALOG_DDL_COLUMNS
)
if _BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS:
    # Fail-fast at import: divergence here would silently widen the
    # contract, which is the exact failure mode the four-layer defence
    # is meant to prevent.
    raise EvaluationContaminationError(
        "bootstrap DDL column set"
        f" {sorted(_BOOTSTRAP_COLUMN_NAMES)} diverges from"
        f" ALLOWED_RAW_DIALOG_KEYS {sorted(ALLOWED_RAW_DIALOG_KEYS)}"
        " — update both in lockstep",
    )

_METRIC_TIERS: tuple[str, ...] = ("tier_a", "tier_b", "tier_c")

_METRIC_TIER_COLUMNS: str = (
    '"run_id" TEXT,'
    ' "persona_id" TEXT,'
    ' "turn_idx" INTEGER,'
    ' "metric_name" TEXT,'
    ' "metric_value" DOUBLE,'
    ' "notes" TEXT'
)
"""Generic per-metric row shape used by all three tiers at P0c.

Tier A is per-turn, Tier B is per-100-turn aggregate, Tier C is judge
score; later phases may introduce tier-specific columns. The current
shape is intentionally narrow so the contract surface stays tight.
"""


def _inspect_raw_dialog_columns(
    conn: duckdb.DuckDBPyConnection,
) -> list[str]:
    """Return ordered column names of ``raw_dialog.dialog``.

    Module-level helper used by both :class:`_DuckDBRawTrainingRelation`
    construction and :func:`export_raw_only_snapshot`. Raises
    :class:`EvaluationContaminationError` if the table is missing.
    """
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = ? AND table_name = ?"
        " ORDER BY ordinal_position",
        (RAW_DIALOG_SCHEMA, RAW_DIALOG_TABLE),
    ).fetchall()
    if not rows:
        raise EvaluationContaminationError(
            f"{RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE} not found in DuckDB"
            f" file; cannot construct training view (was the schema"
            f" bootstrapped? — see bootstrap_schema)",
        )
    return [str(row[0]) for row in rows]


class _DuckDBRawTrainingRelation:
    """Concrete :class:`RawTrainingRelation` backed by a read-only DuckDB connection.

    Designed as a **constrained facade**:

    * The connection is held privately; no public attribute exposes it.
    * Only a fixed SELECT against ``raw_dialog.dialog`` is ever issued.
    * Column projection is the **intersection** of the physical columns
      with :data:`ALLOWED_RAW_DIALOG_KEYS`; any column outside the
      allow-list is dropped before the row reaches the caller, and a
      mismatch between the physical schema and the allow-list raises
      :class:`EvaluationContaminationError` at construction.
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        physical_columns = _inspect_raw_dialog_columns(conn)
        outside_allowlist = [
            col for col in physical_columns if col not in ALLOWED_RAW_DIALOG_KEYS
        ]
        if outside_allowlist:
            raise EvaluationContaminationError(
                f"raw_dialog.{RAW_DIALOG_TABLE} contains column(s)"
                f" {sorted(outside_allowlist)!r} that are not on the"
                f" raw_dialog allow-list"
                f" ({sorted(ALLOWED_RAW_DIALOG_KEYS)})",
            )
        self._columns: tuple[str, ...] = tuple(physical_columns)
        # Belt-and-braces: confirm we never aliased the metrics schema in.
        if any(col.startswith(f"{METRICS_SCHEMA}.") for col in self._columns):
            raise EvaluationContaminationError(
                f"raw_dialog projection includes a {METRICS_SCHEMA}-qualified"
                f" column: {self._columns!r}",
            )

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    @property
    @property
    def schema_name(self) -> str:
        return RAW_DIALOG_SCHEMA

    @property
    def columns(self) -> tuple[str, ...]:
        return self._columns

    def row_count(self) -> int:
        result = self._conn.execute(
            f"SELECT COUNT(*) FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}",  # noqa: S608  # constants are module-private literals, no user input
        ).fetchone()
        if result is None:
            return 0
        return int(result[0])

    def iter_rows(self) -> Iterator[Mapping[str, object]]:
        # Quote each column with DuckDB identifier rules so any future
        # column added to the allow-list cannot collide with reserved
        # keywords (``order``, ``mode``, ``zone`` are all candidates).
        projection = ", ".join(f'"{col}"' for col in self._columns)
        sql = f"SELECT {projection} FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # projection comes from validated allow-list, identifiers are module constants
        cursor = self._conn.execute(sql)
        rows = cursor.fetchall()
        for row in rows:
            row_dict: dict[str, object] = dict(zip(self._columns, row, strict=True))
            assert_no_metrics_leak(row_dict.keys(), context="iter_rows")
            assert_no_sentinel_leak(row_dict.values(), context="iter_rows")
            yield row_dict

    def close(self) -> None:
        """Release the underlying DuckDB connection. Idempotent."""
        with contextlib.suppress(duckdb.Error):
            self._conn.close()


def connect_training_view(db_path: str | Path) -> RawTrainingRelation:
    """Open *db_path* read-only and return a constrained training-egress view.

    This is the **only** training-loader entry point in the codebase.
    Any caller that bypasses it (raw ``duckdb.connect``, direct
    ``read_parquet`` against the metrics schema, etc.) violates the
    contract — the static grep gate in CI catches the obvious shapes,
    while the sentinel test catches the dynamic ones.
    """
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        return _DuckDBRawTrainingRelation(conn)
    except Exception:
        conn.close()
        raise


# ---------------------------------------------------------------------------
# P0c — schema bootstrap
# ---------------------------------------------------------------------------


def bootstrap_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create ``raw_dialog.dialog`` and ``metrics.tier_{a,b,c}`` idempotently.

    *con* must be a writable connection (``read_only=False``); a
    read-only handle will surface DuckDB's own error. The DDL is
    ``CREATE … IF NOT EXISTS`` everywhere, so this is safe to call
    repeatedly on existing files (e.g. orchestration glue that doesn't
    track whether it already ran).

    The ``raw_dialog.dialog`` column set is identical to
    :data:`ALLOWED_RAW_DIALOG_KEYS`; the module-load-time check above
    refuses to import the module if the two ever drift.
    """
    raw_dialog_cols = ", ".join(
        f'"{name}" {ddl_type}' for name, ddl_type in _RAW_DIALOG_DDL_COLUMNS
    )

    con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_DIALOG_SCHEMA}")
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {METRICS_SCHEMA}")

    con.execute(
        f"CREATE TABLE IF NOT EXISTS"
        f" {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"
        f" ({raw_dialog_cols})",
    )

    for tier in _METRIC_TIERS:
        con.execute(
            f"CREATE TABLE IF NOT EXISTS"
            f" {METRICS_SCHEMA}.{tier}"
            f" ({_METRIC_TIER_COLUMNS})",
        )


# ---------------------------------------------------------------------------
# P0c — analysis view (Mac-side full read, NOT a training egress)
# ---------------------------------------------------------------------------


class AnalysisView:
    """Read-only handle that spans both ``raw_dialog`` and ``metrics``.

    Intended for Mac-side analytics, dashboards, and notebooks — i.e.

exec
/bin/zsh -lc "sed -n '280,470p' src/erre_sandbox/evidence/eval_store.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
    Intended for Mac-side analytics, dashboards, and notebooks — i.e.
    any context where reading metric scores **is** the point. The
    training-egress contract therefore deliberately does NOT apply
    here: callers can run arbitrary SELECTs against either schema.

    What protects the boundary: the CI grep gate confines metric
    schema references to this module, so :func:`connect_analysis_view`
    is the sole sanctioned multi-schema reader. Any new training-side
    code path that imports this class would be surfaced by code review
    + the sentinel CI test (which scans documented training-egress
    modules — see ``.github/workflows/ci.yml`` ``eval-egress-grep-gate``
    job).
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def execute(
        self,
        sql: str,
        params: tuple[object, ...] | None = None,
    ) -> list[tuple[object, ...]]:
        """Run *sql* against the read-only connection and fetch all rows."""
        cursor = (
            self._conn.execute(sql)
            if params is None
            else self._conn.execute(sql, params)
        )
        return list(cursor.fetchall())

    def close(self) -> None:
        """Release the underlying DuckDB connection. Idempotent."""
        with contextlib.suppress(duckdb.Error):
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def connect_analysis_view(db_path: str | Path) -> AnalysisView:
    """Open *db_path* read-only for full multi-schema analysis access.

    The ME-2 protocol mandates that only G-GEAR writes the file, while
    Mac consumes the post-CHECKPOINT snapshot read-only — this entry is
    the Mac-side enforcement of that role.
    """
    conn = duckdb.connect(str(db_path), read_only=True)
    return AnalysisView(conn)


# ---------------------------------------------------------------------------
# P0c — Parquet snapshot (raw rows only)
# ---------------------------------------------------------------------------


def export_raw_only_snapshot(
    src_path: str | Path,
    out_path: str | Path,
) -> None:
    """Copy ``raw_dialog.dialog`` from *src_path* to a Parquet *out_path*.

    The metrics schema is never touched. Callers that need ad-hoc SQL
    over raw rows should run that SQL against the snapshot — keeping a
    single auditable egress route is one of the HIGH-1 fixes from the
    Codex review (see ``.steering/20260430-m9-eval-system/codex-review.md``).
    """
    src = str(src_path)
    out = str(out_path)
    if "'" in out:
        # The COPY statement embeds *out* as a quoted string literal;
        # an internal single quote would break the boundary. Reject
        # rather than try to escape (the project never produces such
        # paths in practice).
        raise ValueError(
            f"export_raw_only_snapshot: out_path must not contain a"
            f" single quote (got {out!r})",
        )
    conn = duckdb.connect(src, read_only=True)
    try:
        physical = _inspect_raw_dialog_columns(conn)
        outside = [c for c in physical if c not in ALLOWED_RAW_DIALOG_KEYS]
        if outside:
            raise EvaluationContaminationError(
                f"raw_dialog.{RAW_DIALOG_TABLE} contains column(s)"
                f" {sorted(outside)!r} outside the allow-list; refusing"
                f" to snapshot",
            )
        # Defence-in-depth: re-run the metric-prefix check on the
        # projection that will land in the Parquet file.
        assert_no_metrics_leak(physical, context="export_raw_only_snapshot")
        projection = ", ".join(f'"{col}"' for col in physical)
        copy_sql = (
            f"COPY (SELECT {projection} FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE})"  # noqa: S608  # identifiers are module constants, path validated above
            f" TO '{out}' (FORMAT PARQUET)"
        )
        conn.execute(copy_sql)
    finally:
        with contextlib.suppress(duckdb.Error):
            conn.close()


# ---------------------------------------------------------------------------
# P0c — ME-2 helpers (CHECKPOINT + atomic same-fs rename)
# ---------------------------------------------------------------------------


def write_with_checkpoint(con: duckdb.DuckDBPyConnection) -> None:
    """Flush the WAL via ``CHECKPOINT`` and close *con* (ME-2 step 1).

    G-GEAR-side helper invoked at the end of each capture session: it
    guarantees the on-disk file is consistent before the snapshot copy
    + rsync to Mac. Decision is logged in
    ``.steering/20260430-m9-eval-system/decisions.md`` §ME-2.
    """
    con.execute("CHECKPOINT")
    with contextlib.suppress(duckdb.Error):
        con.close()


def atomic_temp_rename(
    temp_path: Path | str,
    final_path: Path | str,
) -> None:
    """POSIX same-filesystem atomic rename (ME-2 step 4).

    Verifies that *temp_path* and *final_path* live on the same
    filesystem device; ``Path.replace`` otherwise falls back to copy +
    remove on Linux, which loses atomicity and would let the analysis
    view momentarily observe a torn file. NFS / SMB / iCloud-shared
    paths are explicitly out of scope (see ME-2).
    """
    temp_path = Path(temp_path)
    final_path = Path(final_path)
    temp_dev = temp_path.parent.stat().st_dev
    final_dev = final_path.parent.stat().st_dev
    if temp_dev != final_dev:
        raise OSError(
            f"atomic_temp_rename requires same filesystem;"
            f" temp_path on st_dev={temp_dev},"
            f" final_path on st_dev={final_dev}",
        )
    temp_path.replace(final_path)


__all__ = [
    "RAW_DIALOG_TABLE",
    "AnalysisView",
    "atomic_temp_rename",
    "bootstrap_schema",
    "connect_analysis_view",
    "connect_training_view",
    "export_raw_only_snapshot",
    "write_with_checkpoint",
]

exec
/bin/zsh -lc 'rg -n "individual_layer_enabled|evaluation_epoch|ALLOWED_RAW_DIALOG_KEYS|METRICS_SCHEMA|RAW_DIALOG_SCHEMA|RawTrainingRelation|assert_no_metrics_leak|sentinel" src/erre_sandbox/contracts src/erre_sandbox/evidence/eval_store.py tests .github/workflows/ci.yml' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
.github/workflows/ci.yml:77:    # 4-layer DuckDB schema-guard contract). The behavioural sentinel
.github/workflows/ci.yml:92:        # here AND covered by the sentinel CI test.
.github/workflows/ci.yml:108:          # ``METRICS_SCHEMA`` constant import is permitted (it's how
src/erre_sandbox/evidence/eval_store.py:7:read-only and returns a :class:`RawTrainingRelation` that exposes only
src/erre_sandbox/evidence/eval_store.py:15:  with :data:`ALLOWED_RAW_DIALOG_KEYS` (module-load-time check).
src/erre_sandbox/evidence/eval_store.py:43:    ALLOWED_RAW_DIALOG_KEYS,
src/erre_sandbox/evidence/eval_store.py:44:    METRICS_SCHEMA,
src/erre_sandbox/evidence/eval_store.py:45:    RAW_DIALOG_SCHEMA,
src/erre_sandbox/evidence/eval_store.py:47:    RawTrainingRelation,
src/erre_sandbox/evidence/eval_store.py:48:    assert_no_metrics_leak,
src/erre_sandbox/evidence/eval_store.py:49:    assert_no_sentinel_leak,
src/erre_sandbox/evidence/eval_store.py:56:"""Table name inside :data:`RAW_DIALOG_SCHEMA` (qualified
src/erre_sandbox/evidence/eval_store.py:88:if _BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS:
src/erre_sandbox/evidence/eval_store.py:95:        f" ALLOWED_RAW_DIALOG_KEYS {sorted(ALLOWED_RAW_DIALOG_KEYS)}"
src/erre_sandbox/evidence/eval_store.py:122:    Module-level helper used by both :class:`_DuckDBRawTrainingRelation`
src/erre_sandbox/evidence/eval_store.py:130:        (RAW_DIALOG_SCHEMA, RAW_DIALOG_TABLE),
src/erre_sandbox/evidence/eval_store.py:134:            f"{RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE} not found in DuckDB"
src/erre_sandbox/evidence/eval_store.py:141:class _DuckDBRawTrainingRelation:
src/erre_sandbox/evidence/eval_store.py:142:    """Concrete :class:`RawTrainingRelation` backed by a read-only DuckDB connection.
src/erre_sandbox/evidence/eval_store.py:149:      with :data:`ALLOWED_RAW_DIALOG_KEYS`; any column outside the
src/erre_sandbox/evidence/eval_store.py:159:            col for col in physical_columns if col not in ALLOWED_RAW_DIALOG_KEYS
src/erre_sandbox/evidence/eval_store.py:166:                f" ({sorted(ALLOWED_RAW_DIALOG_KEYS)})",
src/erre_sandbox/evidence/eval_store.py:170:        if any(col.startswith(f"{METRICS_SCHEMA}.") for col in self._columns):
src/erre_sandbox/evidence/eval_store.py:172:                f"raw_dialog projection includes a {METRICS_SCHEMA}-qualified"
src/erre_sandbox/evidence/eval_store.py:182:        return RAW_DIALOG_SCHEMA
src/erre_sandbox/evidence/eval_store.py:190:            f"SELECT COUNT(*) FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}",  # noqa: S608  # constants are module-private literals, no user input
src/erre_sandbox/evidence/eval_store.py:201:        sql = f"SELECT {projection} FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # projection comes from validated allow-list, identifiers are module constants
src/erre_sandbox/evidence/eval_store.py:206:            assert_no_metrics_leak(row_dict.keys(), context="iter_rows")
src/erre_sandbox/evidence/eval_store.py:207:            assert_no_sentinel_leak(row_dict.values(), context="iter_rows")
src/erre_sandbox/evidence/eval_store.py:216:def connect_training_view(db_path: str | Path) -> RawTrainingRelation:
src/erre_sandbox/evidence/eval_store.py:223:    while the sentinel test catches the dynamic ones.
src/erre_sandbox/evidence/eval_store.py:227:        return _DuckDBRawTrainingRelation(conn)
src/erre_sandbox/evidence/eval_store.py:248:    :data:`ALLOWED_RAW_DIALOG_KEYS`; the module-load-time check above
src/erre_sandbox/evidence/eval_store.py:255:    con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_DIALOG_SCHEMA}")
src/erre_sandbox/evidence/eval_store.py:256:    con.execute(f"CREATE SCHEMA IF NOT EXISTS {METRICS_SCHEMA}")
src/erre_sandbox/evidence/eval_store.py:260:        f" {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"
src/erre_sandbox/evidence/eval_store.py:267:            f" {METRICS_SCHEMA}.{tier}"
src/erre_sandbox/evidence/eval_store.py:289:    + the sentinel CI test (which scans documented training-egress
src/erre_sandbox/evidence/eval_store.py:363:        outside = [c for c in physical if c not in ALLOWED_RAW_DIALOG_KEYS]
src/erre_sandbox/evidence/eval_store.py:372:        assert_no_metrics_leak(physical, context="export_raw_only_snapshot")
src/erre_sandbox/evidence/eval_store.py:375:            f"COPY (SELECT {projection} FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE})"  # noqa: S608  # identifiers are module constants, path validated above
src/erre_sandbox/contracts/eval_paths.py:12:   :class:`RawTrainingRelation` Protocol that exposes **only** raw rows
src/erre_sandbox/contracts/eval_paths.py:17:   sentinel-row fixtures (``M9_EVAL_SENTINEL_LEAK_*``) that verify no
src/erre_sandbox/contracts/eval_paths.py:23:   sentinel test scope because the M9 LoRA training pipeline reads
src/erre_sandbox/contracts/eval_paths.py:29:relation + sentinel test are the **primary** boundary, with grep as a
src/erre_sandbox/contracts/eval_paths.py:48:RAW_DIALOG_SCHEMA: Final[str] = "raw_dialog"
src/erre_sandbox/contracts/eval_paths.py:57:METRICS_SCHEMA: Final[str] = "metrics"
src/erre_sandbox/contracts/eval_paths.py:70:ALLOWED_RAW_DIALOG_KEYS: Final[frozenset[str]] = frozenset(
src/erre_sandbox/contracts/eval_paths.py:117:These prefixes are used by :func:`assert_no_metrics_leak` as a
src/erre_sandbox/contracts/eval_paths.py:120:added it to :data:`ALLOWED_RAW_DIALOG_KEYS`. Patterns are checked with
src/erre_sandbox/contracts/eval_paths.py:129:the boundary has been breached. Tests should plant sentinel values in the
src/erre_sandbox/contracts/eval_paths.py:146:    * Calling a method on :class:`RawTrainingRelation` that would route
src/erre_sandbox/contracts/eval_paths.py:162:def assert_no_metrics_leak(keys: Iterable[str], *, context: str) -> None:
src/erre_sandbox/contracts/eval_paths.py:166:    :data:`ALLOWED_RAW_DIALOG_KEYS` allow-list **and** (b) not start with
src/erre_sandbox/contracts/eval_paths.py:168:    into the error message so failures at sentinel fixtures point at the
src/erre_sandbox/contracts/eval_paths.py:183:    out_of_allowlist = [k for k in keys_seen if k not in ALLOWED_RAW_DIALOG_KEYS]
src/erre_sandbox/contracts/eval_paths.py:188:            f" {sorted(ALLOWED_RAW_DIALOG_KEYS)})",
src/erre_sandbox/contracts/eval_paths.py:192:def assert_no_sentinel_leak(
src/erre_sandbox/contracts/eval_paths.py:197:    """Raise :class:`EvaluationContaminationError` if any value is a leak sentinel.
src/erre_sandbox/contracts/eval_paths.py:211:            f"{context}: sentinel leak value(s) {leaked!r} surfaced through"
src/erre_sandbox/contracts/eval_paths.py:222:class RawTrainingRelation(Protocol):
src/erre_sandbox/contracts/eval_paths.py:229:    * any column outside :data:`ALLOWED_RAW_DIALOG_KEYS`,
src/erre_sandbox/contracts/eval_paths.py:230:    * any join or subquery against :data:`METRICS_SCHEMA`.
src/erre_sandbox/contracts/eval_paths.py:240:        """Always equal to :data:`RAW_DIALOG_SCHEMA`.
src/erre_sandbox/contracts/eval_paths.py:250:        Must satisfy ``set(columns) <= ALLOWED_RAW_DIALOG_KEYS``; the
src/erre_sandbox/contracts/eval_paths.py:251:        sentinel test asserts this on every implementation.
src/erre_sandbox/contracts/eval_paths.py:261:        :func:`assert_no_metrics_leak` before yielding so a bug in the
src/erre_sandbox/contracts/eval_paths.py:267:    "ALLOWED_RAW_DIALOG_KEYS",
src/erre_sandbox/contracts/eval_paths.py:269:    "METRICS_SCHEMA",
src/erre_sandbox/contracts/eval_paths.py:270:    "RAW_DIALOG_SCHEMA",
src/erre_sandbox/contracts/eval_paths.py:273:    "RawTrainingRelation",
src/erre_sandbox/contracts/eval_paths.py:274:    "assert_no_metrics_leak",
src/erre_sandbox/contracts/eval_paths.py:275:    "assert_no_sentinel_leak",
tests/test_cli/test_eval_run_golden.py:35:from erre_sandbox.contracts.eval_paths import ALLOWED_RAW_DIALOG_KEYS
tests/test_cli/test_eval_run_golden.py:185:        assert set(cols) == ALLOWED_RAW_DIALOG_KEYS
tests/test_evidence/test_eval_paths_contract.py:5:named schema + 4 層 contract" — a sentinel-row red-team fixture
tests/test_evidence/test_eval_paths_contract.py:12:  the :class:`RawTrainingRelation` it returns.
tests/test_evidence/test_eval_paths_contract.py:29:    ALLOWED_RAW_DIALOG_KEYS,
tests/test_evidence/test_eval_paths_contract.py:31:    METRICS_SCHEMA,
tests/test_evidence/test_eval_paths_contract.py:32:    RAW_DIALOG_SCHEMA,
tests/test_evidence/test_eval_paths_contract.py:35:    RawTrainingRelation,
tests/test_evidence/test_eval_paths_contract.py:36:    assert_no_metrics_leak,
tests/test_evidence/test_eval_paths_contract.py:37:    assert_no_sentinel_leak,
tests/test_evidence/test_eval_paths_contract.py:61:any training-egress route. ``assert_no_sentinel_leak`` is the assertion."""
tests/test_evidence/test_eval_paths_contract.py:69:def _seed_duckdb_with_sentinel_rows(
tests/test_evidence/test_eval_paths_contract.py:74:    """Build a DuckDB file with both schemas, seeded with sentinel rows.
tests/test_evidence/test_eval_paths_contract.py:82:        con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_DIALOG_SCHEMA}")
tests/test_evidence/test_eval_paths_contract.py:83:        con.execute(f"CREATE SCHEMA IF NOT EXISTS {METRICS_SCHEMA}")
tests/test_evidence/test_eval_paths_contract.py:101:            f"CREATE TABLE {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"
tests/test_evidence/test_eval_paths_contract.py:137:            f"INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # test-controlled identifiers and value count
tests/test_evidence/test_eval_paths_contract.py:142:        # metrics.tier_a — poisoned with leak sentinels.
tests/test_evidence/test_eval_paths_contract.py:144:            f"CREATE TABLE {METRICS_SCHEMA}.tier_a ("
tests/test_evidence/test_eval_paths_contract.py:154:            f"INSERT INTO {METRICS_SCHEMA}.tier_a VALUES (?,?,?,?,?,?)",  # noqa: S608  # test-controlled module-constant identifier
tests/test_evidence/test_eval_paths_contract.py:169:    _seed_duckdb_with_sentinel_rows(db)
tests/test_evidence/test_eval_paths_contract.py:181:        assert isinstance(relation, RawTrainingRelation)
tests/test_evidence/test_eval_paths_contract.py:182:        assert relation.schema_name == RAW_DIALOG_SCHEMA
tests/test_evidence/test_eval_paths_contract.py:190:        assert set(relation.columns) <= ALLOWED_RAW_DIALOG_KEYS
tests/test_evidence/test_eval_paths_contract.py:203:            assert set(row.keys()) <= ALLOWED_RAW_DIALOG_KEYS
tests/test_evidence/test_eval_paths_contract.py:207:        # Allowed sentinel survives, leak sentinels never appear.
tests/test_evidence/test_eval_paths_contract.py:236:                f"RawTrainingRelation must not expose {forbidden!r}"
tests/test_evidence/test_eval_paths_contract.py:254:    _seed_duckdb_with_sentinel_rows(
tests/test_evidence/test_eval_paths_contract.py:267:        con.execute(f"CREATE SCHEMA {RAW_DIALOG_SCHEMA}")
tests/test_evidence/test_eval_paths_contract.py:279:def test_assert_no_metrics_leak_rejects_forbidden_prefix() -> None:
tests/test_evidence/test_eval_paths_contract.py:281:        assert_no_metrics_leak(
tests/test_evidence/test_eval_paths_contract.py:288:def test_assert_no_metrics_leak_rejects_keys_outside_allowlist() -> None:
tests/test_evidence/test_eval_paths_contract.py:290:        assert_no_metrics_leak(
tests/test_evidence/test_eval_paths_contract.py:296:def test_assert_no_metrics_leak_passes_for_allowlist_only() -> None:
tests/test_evidence/test_eval_paths_contract.py:297:    assert_no_metrics_leak(
tests/test_evidence/test_eval_paths_contract.py:303:def test_assert_no_sentinel_leak_detects_leak_prefix() -> None:
tests/test_evidence/test_eval_paths_contract.py:305:        assert_no_sentinel_leak(
tests/test_evidence/test_eval_paths_contract.py:312:def test_assert_no_sentinel_leak_ignores_non_strings() -> None:
tests/test_evidence/test_eval_paths_contract.py:313:    assert_no_sentinel_leak([0, 1.5, None, "ok"], context="unit")
tests/test_evidence/test_eval_paths_contract.py:321:def _seed_dialog_turns_with_sentinel(db_path: Path) -> int:
tests/test_evidence/test_eval_paths_contract.py:323:    sentinel; return the row count."""
tests/test_evidence/test_eval_paths_contract.py:339:    # Insert one row whose utterance carries a leak sentinel — even if
tests/test_evidence/test_eval_paths_contract.py:342:    # this row therefore exercises ``assert_no_metrics_leak`` over keys.
tests/test_evidence/test_eval_paths_contract.py:364:    :data:`ALLOWED_RAW_DIALOG_KEYS` and carry no metric-shaped key.
tests/test_evidence/test_eval_paths_contract.py:366:    The leak-sentinel value living inside ``utterance`` is allowed to
tests/test_evidence/test_eval_paths_contract.py:370:    sentinel string, and the contract must not over-fire on values.
tests/test_evidence/test_eval_paths_contract.py:373:    expected = _seed_dialog_turns_with_sentinel(db)
tests/test_evidence/test_eval_paths_contract.py:385:        leaked = keys - ALLOWED_RAW_DIALOG_KEYS
tests/test_evidence/test_eval_paths_contract.py:386:        assert keys <= ALLOWED_RAW_DIALOG_KEYS, (
tests/test_evidence/test_eval_paths_contract.py:390:        assert_no_metrics_leak(row.keys(), context="export-log row")
tests/test_evidence/test_eval_paths_contract.py:402:    _seed_dialog_turns_with_sentinel(db)
tests/test_evidence/test_golden_baseline.py:196:    """Concrete sentinel: the committed kant/run_idx=0 seed is the canonical value.
tests/test_evidence/test_eval_store.py:6:  :data:`ALLOWED_RAW_DIALOG_KEYS`.
tests/test_evidence/test_eval_store.py:15:  sentinel even when the source database has metrics rows.
tests/test_evidence/test_eval_store.py:29:    ALLOWED_RAW_DIALOG_KEYS,
tests/test_evidence/test_eval_store.py:30:    METRICS_SCHEMA,
tests/test_evidence/test_eval_store.py:31:    RAW_DIALOG_SCHEMA,
tests/test_evidence/test_eval_store.py:63:            (RAW_DIALOG_SCHEMA, RAW_DIALOG_TABLE),
tests/test_evidence/test_eval_store.py:67:    assert {row[0] for row in rows} == ALLOWED_RAW_DIALOG_KEYS
tests/test_evidence/test_eval_store.py:77:            (METRICS_SCHEMA,),
tests/test_evidence/test_eval_store.py:110:        assert set(relation.columns) == ALLOWED_RAW_DIALOG_KEYS
tests/test_evidence/test_eval_store.py:127:            f"INSERT INTO {METRICS_SCHEMA}.tier_a"  # noqa: S608  # module constants
tests/test_evidence/test_eval_store.py:141:            f"SELECT metric_name, metric_value FROM {METRICS_SCHEMA}.tier_a"  # noqa: S608  # module constants
tests/test_evidence/test_eval_store.py:181:    rogue_sql = f'INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE} ("id") VALUES (?)'  # noqa: S608  # module constants
tests/test_evidence/test_eval_store.py:200:    rogue_sql = f'INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE} ("id") VALUES (?)'  # noqa: S608  # module constants
tests/test_evidence/test_eval_store.py:217:        f"INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # module constants
tests/test_evidence/test_eval_store.py:224:        f"INSERT INTO {METRICS_SCHEMA}.tier_a"  # noqa: S608  # module constants
tests/test_evidence/test_eval_store.py:279:        assert col_set == ALLOWED_RAW_DIALOG_KEYS
tests/test_evidence/test_eval_store.py:283:        # No leak sentinel ever surfaces — the metrics row in the source
tests/test_evidence/test_eval_store.py:331:    count_sql = f"SELECT COUNT(*) FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # identifiers are module constants
tests/test_evidence/test_eval_store.py:352:    count_sql = f"SELECT COUNT(*) FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # identifiers are module constants
tests/test_integration/test_multi_agent_stream.py:501:            # Global WorldTickMsg sentinel so every subscriber has something

exec
/bin/zsh -lc "sed -n '1,280p' src/erre_sandbox/contracts/eval_paths.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '60,120p' .github/workflows/ci.yml" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""Evaluation data-path contract.

The executable boundary between ``raw_dialog`` (training-eligible) and
``metrics`` (evaluation-only).

This module is the **API contract** layer of the 4-layer defence specified
in ``.steering/20260430-m9-eval-system/design-final.md``
§"DuckDB 単 file + named schema + 4 層 contract":

1. **API contract** (this module): schema-name constants, an explicit
   allow-list of ``raw_dialog`` columns, a constrained relation
   :class:`RawTrainingRelation` Protocol that exposes **only** raw rows
   (no DuckDB connection, no arbitrary SQL), and the
   :class:`EvaluationContaminationError` that every egress path must raise
   when a metric-shaped key surfaces.
2. **Behavioural CI test** (``tests/test_evidence/test_eval_paths_contract.py``):
   sentinel-row fixtures (``M9_EVAL_SENTINEL_LEAK_*``) that verify no
   training-egress route surfaces metric data.
3. **Static CI grep gate** (``.github/workflows/ci.yml``): fails the build
   if any module under the training-egress allowlist textually mentions
   ``metrics.``.
4. **Existing-egress audit** (``cli/export_log.py``): is included in the
   sentinel test scope because the M9 LoRA training pipeline reads
   ``dialog_turns`` through it.

Codex ``gpt-5.5 xhigh`` review (HIGH-1) elevated this contract from a
path-only convention to a behavioural one — grep alone cannot catch
dynamic SQL or quoted ``read_parquet`` calls, so the constrained
relation + sentinel test are the **primary** boundary, with grep as a
back-stop.

Layer rule (``contracts`` package): stdlib + pydantic only — no
``duckdb``, ``numpy``, or other heavy imports here. The DuckDB-backed
implementation lives in :mod:`erre_sandbox.evidence.eval_store`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable, Iterator, Mapping

# ---------------------------------------------------------------------------
# Schema names
# ---------------------------------------------------------------------------

RAW_DIALOG_SCHEMA: Final[str] = "raw_dialog"
"""Name of the DuckDB schema that holds training-eligible dialog turns.

This is the **only** schema the LoRA training pipeline is allowed to read
through :func:`erre_sandbox.evidence.eval_store.connect_training_view`.
Tier 0 contract (DB5): every column here must be metric-free — turn id,
agent / persona / mode / zone, utterance, timestamp, reasoning trace.
"""

METRICS_SCHEMA: Final[str] = "metrics"
"""Name of the DuckDB schema that holds Tier A/B/C scores keyed by
``(run_id, persona_id, turn_idx)``.

Reading this schema from a training-loader code path is a contract
violation that must surface as :class:`EvaluationContaminationError`.
"""


# ---------------------------------------------------------------------------
# Column allow-list / forbidden patterns
# ---------------------------------------------------------------------------

ALLOWED_RAW_DIALOG_KEYS: Final[frozenset[str]] = frozenset(
    {
        "id",
        "run_id",
        "dialog_id",
        "tick",
        "turn_index",
        "speaker_agent_id",
        "speaker_persona_id",
        "addressee_agent_id",
        "addressee_persona_id",
        "utterance",
        "mode",
        "zone",
        "reasoning",
        "epoch_phase",
        "created_at",
    },
)
"""Closed allow-list of column names permitted on a ``raw_dialog`` row.

Any key emitted by a training-egress path MUST be a member of this set.
``mode`` / ``zone`` / ``reasoning`` are reserved for the M9 ingest CLI
that copies sqlite ``dialog_turns`` into DuckDB ``raw_dialog``; the
existing M8 sink only populates a subset of these (see
``cli/export_log.py``), which is a strict subset and therefore safe.
"""

FORBIDDEN_METRIC_KEY_PATTERNS: Final[tuple[str, ...]] = (
    "metric_",
    "score_",
    "vendi_",
    "burrows_",
    "icc_",
    "embedding_",
    "novelty_",
    "logit_",
    "judge_",
    "geval_",
    "prometheus_",
    "nli_",
    "mattr_",
    "empath_",
)
"""Substring prefixes that signal a metric-shaped key has leaked into a
training-egress payload.

These prefixes are used by :func:`assert_no_metrics_leak` as a
**defence-in-depth** check on top of the closed allow-list — a key like
``"empath_anger"`` would be rejected even if a future commit accidentally
added it to :data:`ALLOWED_RAW_DIALOG_KEYS`. Patterns are checked with
``str.startswith`` (case-sensitive) since column names are
canonicalised lower_snake_case throughout the codebase.
"""

SENTINEL_LEAK_PREFIX: Final[str] = "M9_EVAL_SENTINEL_LEAK_"
"""String prefix used by the contamination CI fixture.

If a value starting with this prefix appears in a training-egress payload
the boundary has been breached. Tests should plant sentinel values in the
``metrics`` schema and assert they never reach ``connect_training_view``
output — see :class:`EvaluationContaminationError` and
``tests/test_evidence/test_eval_paths_contract.py``.
"""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EvaluationContaminationError(RuntimeError):
    """Raised when a training-egress path attempts to expose metric data.

    Examples that MUST raise:

    * Calling a method on :class:`RawTrainingRelation` that would route
      to the ``metrics`` schema.
    * Building a row dict whose keys include any
      :data:`FORBIDDEN_METRIC_KEY_PATTERNS` prefix.
    * Surfacing a value with the :data:`SENTINEL_LEAK_PREFIX`.

    Catching this exception silently is a **contract bug**; tests assert
    the error type, not just any exception subclass.
    """


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def assert_no_metrics_leak(keys: Iterable[str], *, context: str) -> None:
    """Raise :class:`EvaluationContaminationError` if any *keys* look metric-shaped.

    The check is layered: keys must (a) belong to the
    :data:`ALLOWED_RAW_DIALOG_KEYS` allow-list **and** (b) not start with
    any :data:`FORBIDDEN_METRIC_KEY_PATTERNS` prefix. *context* is woven
    into the error message so failures at sentinel fixtures point at the
    egress path that leaked.
    """
    keys_seen: list[str] = list(keys)
    forbidden: list[str] = []
    for key in keys_seen:
        for pattern in FORBIDDEN_METRIC_KEY_PATTERNS:
            if key.startswith(pattern):
                forbidden.append(key)
                break
    if forbidden:
        raise EvaluationContaminationError(
            f"{context}: forbidden metric-shaped key(s) {sorted(set(forbidden))!r}"
            f" leaked into training egress",
        )
    out_of_allowlist = [k for k in keys_seen if k not in ALLOWED_RAW_DIALOG_KEYS]
    if out_of_allowlist:
        raise EvaluationContaminationError(
            f"{context}: key(s) {sorted(set(out_of_allowlist))!r} are not on the"
            f" raw_dialog allow-list (expected subset of"
            f" {sorted(ALLOWED_RAW_DIALOG_KEYS)})",
        )


def assert_no_sentinel_leak(
    values: Iterable[object],
    *,
    context: str,
) -> None:
    """Raise :class:`EvaluationContaminationError` if any value is a leak sentinel.

    Used by the red-team contamination fixture: planting
    :data:`SENTINEL_LEAK_PREFIX` values in the ``metrics`` schema and
    checking that no such value ever surfaces through a training-egress
    route. Pure-string check; non-string values pass.
    """
    leaked: list[str] = [
        value
        for value in values
        if isinstance(value, str) and value.startswith(SENTINEL_LEAK_PREFIX)
    ]
    if leaked:
        raise EvaluationContaminationError(
            f"{context}: sentinel leak value(s) {leaked!r} surfaced through"
            f" a training-egress path",
        )


# ---------------------------------------------------------------------------
# Constrained relation Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class RawTrainingRelation(Protocol):
    """Read-only view onto ``raw_dialog`` rows for training pipelines.

    Implementations MUST NOT expose:

    * the underlying DuckDB ``Connection`` or ``DuckDBPyRelation``,
    * an arbitrary SQL execution method,
    * any column outside :data:`ALLOWED_RAW_DIALOG_KEYS`,
    * any join or subquery against :data:`METRICS_SCHEMA`.

    Callers that genuinely need ad-hoc SQL must use
    ``eval_store.export_raw_only_snapshot(out_path)`` (added in P0c) and
    run their query against the *snapshot* — that route is auditable in
    a single place.
    """

    @property
    def schema_name(self) -> str:
        """Always equal to :data:`RAW_DIALOG_SCHEMA`.

        Used by tests to verify the relation cannot be re-pointed at the
        ``metrics`` schema after construction.
        """

    @property
    def columns(self) -> tuple[str, ...]:
        """Tuple of column names exposed on each row.

        Must satisfy ``set(columns) <= ALLOWED_RAW_DIALOG_KEYS``; the
        sentinel test asserts this on every implementation.
        """

    def row_count(self) -> int:
        """Return the number of ``raw_dialog`` rows visible through the view."""

    def iter_rows(self) -> Iterator[Mapping[str, object]]:
        """Iterate over rows as plain dicts.

        Implementations should validate emitted keys via
        :func:`assert_no_metrics_leak` before yielding so a bug in the
        underlying SELECT cannot silently leak a forbidden column.
        """


__all__ = [
    "ALLOWED_RAW_DIALOG_KEYS",
    "FORBIDDEN_METRIC_KEY_PATTERNS",
    "METRICS_SCHEMA",
    "RAW_DIALOG_SCHEMA",
    "SENTINEL_LEAK_PREFIX",
    "EvaluationContaminationError",
    "RawTrainingRelation",
    "assert_no_metrics_leak",
    "assert_no_sentinel_leak",
]

 succeeded in 0ms:
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
          python-version-file: .python-version
      - name: Sync dependencies
        run: uv sync --frozen --all-groups
      - name: pytest -m "not godot and not eval"
        # ``eval``-marked tests need the [eval] extras (heavy ML deps:
        # sentence-transformers, transformers, empath). The default
        # CI install (``--all-groups``) only pulls dependency-groups,
        # so deselect ``eval``-marked tests here; m9-eval-system Tier
        # A unit tests stay on the default selection because they
        # inject stub callables and have no real-model imports.
        run: uv run pytest -m "not godot and not eval"

  eval-egress-grep-gate:
    # m9-eval-system Phase P0b — defence-in-depth (layer 4 of the
    # 4-layer DuckDB schema-guard contract). The behavioural sentinel
    # test in tests/test_evidence/test_eval_paths_contract.py is the
    # primary boundary; this grep is a static back-stop that catches
    # the obvious ``metrics.`` shape inside the documented training-
    # egress allow-list. See
    # .steering/20260430-m9-eval-system/design-final.md
    # §"DuckDB 単 file + named schema + 4 層 contract".
    name: eval egress grep gate (no `metrics.` in training paths)
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - uses: actions/checkout@v4
      - name: Forbid `metrics.` in training-egress modules
        # Allow-list of paths that read raw_dialog for the LoRA
        # training pipeline. New training egress paths MUST be added
        # here AND covered by the sentinel CI test.
        run: |
          set -euo pipefail
          paths=(
            src/erre_sandbox/cli/export_log.py
            src/erre_sandbox/evidence/eval_store.py
          )
          missing=()
          for p in "${paths[@]}"; do
            if [ ! -f "$p" ]; then missing+=("$p"); fi
          done
          if [ ${#missing[@]} -gt 0 ]; then
            echo "::error::training-egress allow-list points at missing path(s): ${missing[*]}"
            exit 1
          fi
          # Look for any reference to the metrics schema. The
          # ``METRICS_SCHEMA`` constant import is permitted (it's how
          # eval_store guards the boundary), but a literal ``metrics.``
          # qualifier inside a training-egress module is not.
          if grep -nE '"metrics\.|'\''metrics\.' "${paths[@]}"; then
            echo "::error::training-egress module references the metrics schema literally — that is a contract violation (see contracts/eval_paths.py)"
            exit 1
          fi
          echo "[eval-egress-grep-gate] PASS"

exec
/bin/zsh -lc "sed -n '1,120p' tests/test_evidence/test_eval_store.py && sed -n '120,240p' tests/test_evidence/test_eval_store.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""Tests for :mod:`erre_sandbox.evidence.eval_store` P0c additions.

Covers (per ``.steering/20260430-m9-eval-system/tasklist.md`` §P0c):

* :func:`bootstrap_schema` idempotency and column-set lock-step with
  :data:`ALLOWED_RAW_DIALOG_KEYS`.
* :func:`connect_training_view` opens read-only after bootstrap and
  refuses writes (defence verification at the implementation level —
  the public protocol surface is already covered by
  ``test_eval_paths_contract.py``).
* :func:`connect_analysis_view` returns an :class:`AnalysisView` that
  can SELECT both schemas but cannot INSERT.
* :func:`export_raw_only_snapshot` writes a Parquet whose columns are
  a subset of the raw allow-list and whose rows carry no metric
  sentinel even when the source database has metrics rows.
* :func:`write_with_checkpoint` + :func:`atomic_temp_rename`
  round-trip: a CHECKPOINTed file moved to a new path is openable via
  :func:`connect_analysis_view`.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from erre_sandbox.contracts.eval_paths import (
    ALLOWED_RAW_DIALOG_KEYS,
    METRICS_SCHEMA,
    RAW_DIALOG_SCHEMA,
    SENTINEL_LEAK_PREFIX,
)
from erre_sandbox.evidence.eval_store import (
    RAW_DIALOG_TABLE,
    AnalysisView,
    atomic_temp_rename,
    bootstrap_schema,
    connect_analysis_view,
    connect_training_view,
    export_raw_only_snapshot,
    write_with_checkpoint,
)


def _writable(db: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db), read_only=False)


# ---------------------------------------------------------------------------
# bootstrap_schema
# ---------------------------------------------------------------------------


def test_bootstrap_creates_full_allowlist_for_raw_dialog(tmp_path: Path) -> None:
    db = tmp_path / "fresh.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        rows = con.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = ? AND table_name = ?",
            (RAW_DIALOG_SCHEMA, RAW_DIALOG_TABLE),
        ).fetchall()
    finally:
        con.close()
    assert {row[0] for row in rows} == ALLOWED_RAW_DIALOG_KEYS


def test_bootstrap_creates_three_metric_tier_tables(tmp_path: Path) -> None:
    db = tmp_path / "fresh.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        rows = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
            (METRICS_SCHEMA,),
        ).fetchall()
    finally:
        con.close()
    assert {row[0] for row in rows} == {"tier_a", "tier_b", "tier_c"}


def test_bootstrap_is_idempotent(tmp_path: Path) -> None:
    """Repeated bootstrap calls on the same connection must not raise."""
    db = tmp_path / "fresh.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        bootstrap_schema(con)
        bootstrap_schema(con)
    finally:
        con.close()


def test_bootstrap_then_training_view_yields_zero_rows(tmp_path: Path) -> None:
    """Bootstrap-only files open cleanly via the training view with
    row_count() == 0, confirming the constrained relation is
    constructable on a freshly-bootstrapped store."""
    db = tmp_path / "fresh.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    relation = connect_training_view(db)
    try:
        assert relation.row_count() == 0
        assert set(relation.columns) == ALLOWED_RAW_DIALOG_KEYS
        assert list(relation.iter_rows()) == []
    finally:
        relation.close()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# connect_analysis_view (Mac-side full read)
# ---------------------------------------------------------------------------



def test_analysis_view_reads_metrics_tier_a(tmp_path: Path) -> None:
    db = tmp_path / "with_metrics.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        insert_sql = (
            f"INSERT INTO {METRICS_SCHEMA}.tier_a"  # noqa: S608  # module constants
            ' ("run_id", "persona_id", "turn_idx", "metric_name",'
            ' "metric_value", "notes") VALUES (?, ?, ?, ?, ?, ?)'
        )
        con.execute(
            insert_sql,
            ("run-001", "kant", 0, "burrows_delta", 4.2, "fixture"),
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()
    view = connect_analysis_view(db)
    try:
        select_sql = (
            f"SELECT metric_name, metric_value FROM {METRICS_SCHEMA}.tier_a"  # noqa: S608  # module constants
            " ORDER BY turn_idx"
        )
        rows = view.execute(select_sql)
    finally:
        view.close()
    assert rows == [("burrows_delta", 4.2)]


def test_analysis_view_supports_context_manager(tmp_path: Path) -> None:
    db = tmp_path / "ctx.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    with connect_analysis_view(db) as view:
        assert isinstance(view, AnalysisView)
        result = view.execute("SELECT 1")
        assert result == [(1,)]


# ---------------------------------------------------------------------------
# read_only enforcement (both entries)
# ---------------------------------------------------------------------------


def test_training_view_underlying_connection_is_read_only(tmp_path: Path) -> None:
    """The constrained relation's protocol forbids SQL execution from
    the public surface, but as a defence in depth the underlying
    DuckDB handle is also opened ``read_only=True`` so a contract
    bug that leaked the connection would still fail loud."""
    db = tmp_path / "ro.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
    finally:
        write_with_checkpoint(con)

    rogue_sql = f'INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE} ("id") VALUES (?)'  # noqa: S608  # module constants

    relation = connect_training_view(db)
    try:
        private_conn = relation._conn  # type: ignore[attr-defined]
        with pytest.raises(duckdb.Error):
            private_conn.execute(rogue_sql, ("rogue",))
    finally:
        relation.close()  # type: ignore[attr-defined]


def test_analysis_view_refuses_writes(tmp_path: Path) -> None:
    db = tmp_path / "ro.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
    finally:
        write_with_checkpoint(con)

    rogue_sql = f'INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE} ("id") VALUES (?)'  # noqa: S608  # module constants

    view = connect_analysis_view(db)
    try:
        with pytest.raises(duckdb.Error):
            view.execute(rogue_sql, ("rogue",))
    finally:
        view.close()


# ---------------------------------------------------------------------------
# export_raw_only_snapshot
# ---------------------------------------------------------------------------


def _seed_raw_and_metrics(db: Path) -> None:
    raw_insert_sql = (
        f"INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # module constants
        ' ("id", "run_id", "dialog_id", "tick", "turn_index",'
        ' "speaker_persona_id", "addressee_persona_id", "utterance",'
        ' "mode", "zone", "created_at")'
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    metric_insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.tier_a"  # noqa: S608  # module constants
        ' ("run_id", "persona_id", "turn_idx", "metric_name",'
        ' "metric_value", "notes") VALUES (?, ?, ?, ?, ?, ?)'
    )

    con = _writable(db)
    try:
        bootstrap_schema(con)
        con.execute(
            raw_insert_sql,
            (
                "row1",
                "run-001",
                "d_kant_nietzsche_0001",
                10,
                0,
                "kant",

web search: 
web search: Vendi Score arXiv 2210.02410 kernel similarity matrix exponential Shannon entropy one-hot score N Friedman Dieng
web search: 
web search: https://arxiv.org/abs/2210.02410
web search: 
web search: https://ar5iv.org/pdf/2210.02410
web search: 
web search: 'combining distinct similarity functions' in https://ar5iv.org/pdf/2210.02410
web search: 
web search: Donnellan Oswald Baird Lucas 2006 Mini-IPIP Cronbach alpha reliability 20-item Mini-IPIP pdf
web search: 
web search: IPIP 50-item Big-Five Factor Markers coefficient alpha official IPIP table Goldberg
web search: 
web search: https://www.sciencedirect.com/science/article/pii/S019188690500022X
web search: 
web search: International Personality Item Pool public domain use freely available items official
web search: 
web search: Salecha et al 2024 arXiv 2405.06058 LLM Big Five personality social desirability bias
web search: 
web search: https://pmc.ncbi.nlm.nih.gov/articles/PMC11650498/
web search: 
web search: Koo Li 2016 ICC guideline consistency absolute agreement cutoff 0.5 0.75 0.9 PMC
web search: 
web search: LLM personality stability intraclass correlation ICC Big Five 2024
web search: 
web search: https://pubmed.ncbi.nlm.nih.gov/27330520/
web search: 
web search: Koo Li ICC values less than 0.5 between 0.5 and 0.75 poor moderate good excellent reliability quote
web search: 
web search: Fast Chen Bernstein 2016 Empath LIWC correlation validation categories PLOS ONE
web search: 
web search: Murakami 2002 Japanese IPIP 50 Big Five scale Murakami 2003 license
web search: 
web search: https://www.jstage.jst.go.jp/article/jjpjspp/11/2/11_KJ00002442203/_article/-char/ja
codex
Verdict: ADOPT-WITH-CHANGES

**HIGH finding (must reflect before merge)**

[HIGH-1] Vendi hybrid kernel/window is still arbitrary and mathematically under-specified  
v3’s semantic 0.7 + lexical 0.3 choice has conceptual prior art only: Friedman & Dieng support user-defined and combined similarity functions, but not this weight pair or semantic+5gram as a validated text gate.  
The one-hot sanity is also misstated: score=N holds only when the normalized kernel is exactly identity, i.e. all off-diagonal similarities are zero and K is PSD with K_ii=1. A lexical one-hot component does not make the hybrid score N if the semantic component has nonzero off-diagonals.  
100-turn windows are not supported by Vendi prior art. The 2025 finite-sample paper strengthens concern that empirical Vendi can be sample-size fragile; it does not justify either 100 or 200 as sufficient. Keep 100 only with a preregistered sensitivity test: semantic-only, lexical-only, hybrid 0.5/0.5, 0.7/0.3, and 0.9/0.1 on pilot data.  
Citation: https://arxiv.org/abs/2210.02410 ; https://github.com/vertaix/Vendi-Score ; https://proceedings.mlr.press/v286/ospanov25a.html

[HIGH-2] ICC notation and gate semantics are not merge-safe  
“ICC(2,k) consistency” mixes naming systems. Koo/Li require choosing model, type, and definition; McGraw-Wong distinguishes ICC(C,k) consistency from ICC(A,k) absolute agreement, while Shrout-Fleiss ICC(2,k) is commonly mapped to two-way random absolute-agreement average.  
For ME-1 fallback, consistency ICC can be primary only if the question is “is the IPIP measurement stable across runs/windows?” For DB9 drift/adoption, absolute level shift matters; a systematic Big5 offset can leave consistency high while representing persona drift.  
Before merge, v3 must name exact formulas in one notation, expose both average and single-measure variants, and specify which consumer uses which: ME-1 reliability trigger vs DB9 baseline-positive/negative gate. Do not apply the same 0.6/0.5 threshold to ICC(A,1) without calibration.  
Citation: https://pubmed.ncbi.nlm.nih.gov/27330520/ ; https://www.unistat.com/guide/intraclass-correlation-coefficients/

[HIGH-3] “Murakami 2002/2003 Japanese IPIP-50” is not a valid item-source commitment  
Murakami 2003 is evidence for Japanese lexical Big Five extraction, not a license-cleared Japanese IPIP-50 item corpus. It even warns that Japanese Big Five content may differ in details from English-language content.  
The English IPIP items/scales are public domain, including commercial use, but the design must identify the exact Japanese item source, retrieval URL, and license. The IPIP translations page points to Japanese IPIP translations by Nakayama/Karlin, not Murakami as an IPIP-50 translation source.  
Merge condition: either vendor the exact public-domain Japanese IPIP-50 text with provenance, or ship `language="en"` only and mark Japanese administration blocked/deferred.  
Citation: https://www.jstage.jst.go.jp/article/jjpjspp/11/2/11_KJ00002442203/_article/-char/ja ; https://ipip.ori.org/index.htm ; https://ipip.ori.org/newPermission.htm ; https://ipip.ori.org/newTranslations.htm

[HIGH-4] IPIP administering helper needs anti-demand-characteristics design, not just diagnostics  
Salecha et al. show LLMs infer personality-test context and shift toward socially desirable Big Five answers; reverse-coding reduces but does not eliminate the bias. v3’s persona-conditional prompt plus explicit IPIP item wording is therefore high-risk.  
The helper should avoid announcing “Big Five/IPIP/personality test” in the prompt, isolate items or use constrained scoring, randomize order deterministically, include decoys/control items, and record base-model no-persona controls required by ME-1.  
A stable biased response pattern can produce deceptively high ICC, so this is not a cosmetic issue; it directly affects the DB9 offensive gate.  
Citation: https://arxiv.org/abs/2405.06058 ; https://www.nature.com/articles/s42256-025-01115-6

**MEDIUM finding (decisions.md ADR 反映)**

[MEDIUM-1] Bootstrap output must prevent primary/diagnostic confusion  
`cluster_only=True` primary is compatible with PR #146 if v3 keeps the effective sample size disclosure at 25 clusters/persona. `auto_block=True` may be useful, but JSON must use explicit fields such as `ci_primary` and `ci_diagnostic_auto_block`; quorum code must consume only `ci_primary`. Also forbid pooled-persona CI unless the output is explicitly marked exploratory, because pooling underestimates persona-conditional variance.

[MEDIUM-2] `metrics.tier_b.turn_idx` as `window_index` is tolerable but semantically leaky  
Do not rename the column in this PR, but add helpers that return `window_index`, not raw `turn_idx`, and put `window_start_turn`, `window_end_turn`, `window_size`, and `metric_schema_version` in notes JSON. This avoids downstream code joining a 100-turn aggregate to a single raw turn by accident.

[MEDIUM-3] DB11 follow-up cannot be hand-waved by “DB5 guarantees it”  
The current `raw_dialog` allow-list does not include `individual_layer_enabled`, while DB11 says training eligibility requires `evaluation_epoch=false AND individual_layer_enabled=false`. P4a does not need to implement all DB11 plumbing, but it must not claim no assert is needed. Add an ADR note that Tier B remains eval-only and that DB11 raw-schema/training-view enforcement is a separate required follow-up.

[MEDIUM-4] Multilingual Vendi fairness needs a diagnostic path  
v3 assumes multilingual MPNet fairly compares ja/en mixed utterances. The existing Tier A novelty code currently lazy-loads `all-mpnet-base-v2`, not the multilingual model named in the prompt, so implementation can silently diverge. Add tests that assert the exact model id, plus language-stratified Vendi outputs for ja-only, en-only, and mixed windows.

[MEDIUM-5] ICC sample size and degenerate tests need explicit handling  
n=100 turns is not the ICC sample size once each window is collapsed to one Big5 vector; the effective ICC design is 5 runs × 5 windows × 5 domains/items depending on layout. 25 clusters can support a diagnostic baseline but not publication-grade construct validity. Identical all-constant responses can produce 0/0 in ANOVA formulas, so `ICC=1.0` must be a deliberate degenerate special case, not assumed.

**LOW finding (blockers.md defer 可)**

[LOW-1] Keep 5-point Likert unless a calibration run proves 7-point improves reliability  
IPIP’s standard administration is compatible with 5-point parsing and lower LLM output ambiguity. 7-point may add variance without construct gain. Balanced reverse-keying around 50% is fine, but item order must avoid obvious forward/reverse adjacency.

[LOW-2] Closing P5 residual tests in this PR is appropriate  
Close Vendi identity-kernel score=N and Big5 ICC identical-response convergence in P4a, because the new modules own those invariants. Label them regression/sanity tests, not evidence that the metric is valid.

[LOW-3] LIWC retirement is justified, but copy the honest framing style exactly  
`empath_proxy.py` already says Empath is a secondary psycholinguistic diagnostic and makes no Big5 claim. Tier B module docstrings should match that rigor: IPIP self-report only, no LIWC equivalence, no external-lexicon Big5 inference.

**Prior art summary (web search 必須)**

1. Vendi Score 2023: supports user-defined similarity kernels and shows combined similarity functions can be meaningful, but gives no 0.7/0.3 semantic+lexical weight and no 100/200-turn minimum. score=N requires K=I after normalization. Sources: https://arxiv.org/abs/2210.02410 ; https://github.com/vertaix/Vendi-Score ; finite-sample caution https://proceedings.mlr.press/v286/ospanov25a.html

2. IPIP-NEO Mini-20 vs IPIP-50: official IPIP tables put Mini-IPIP mean alpha around .70 with some dimensions .65-.69, while IPIP-50 broad-domain scales are around mean .84. This supports v3’s IPIP-50 over Mini-20 because Mini-20 can sit on the ME-1 0.6 boundary. Sources: https://ipip.ori.org/MiniIPIPTable.htm ; https://ipip.ori.org/newBigFive5broadTable.htm ; https://www.sciencedirect.com/science/article/abs/pii/S019188690500022X

3. ICC for LLM personality stability: Koo/Li supports selecting model/type/definition and interpreting ICC by CI; absolute agreement is not interchangeable with consistency. Recent LLM psychometric work stresses reliability plus construct validity, and smaller/instruction-sensitive models remain risky. Sources: https://pubmed.ncbi.nlm.nih.gov/27330520/ ; https://www.unistat.com/guide/intraclass-correlation-coefficients/ ; https://www.nature.com/articles/s42256-025-01115-6

4. LIWC vs Empath: Fast et al. show Empath correlates strongly with similar LIWC categories, but that is category-level/topic-emotion similarity, not a Big5 substitute. DB10 Option D is defensible: retire LIWC from Tier B and keep Empath only as Tier A secondary diagnostic. Source: https://arxiv.org/abs/1602.06979

5. Japanese Mini-IPIP/IPIP-50: IPIP English items/scales are public domain for commercial and non-commercial use. Murakami 2003 validates Japanese lexical Big Five conditions, not an IPIP-50 translation/license. Use official IPIP Japanese translation provenance or defer Japanese administration. Sources: https://ipip.ori.org/index.htm ; https://ipip.ori.org/newPermission.htm ; https://ipip.ori.org/newTranslations.htm ; https://www.jstage.jst.go.jp/article/jjpjspp/11/2/11_KJ00002442203/_article/-char/ja

**Closing note**

Adopt v3 hybrid, not v1 or v2, but only after the HIGH fixes. The right final shape is v3 with: Vendi kernel sensitivity instead of hard-coded 0.7/0.3 faith, corrected ICC notation/consumer semantics, license-cleared Japanese IPIP corpus or explicit defer, and anti-social-desirability IPIP administration.
hook: Stop
hook: Stop Completed
2026-05-08T08:37:04.405636Z ERROR codex_core::session: failed to record rollout items: thread 019e06b6-e777-7631-92c3-ec17b3365e47 not found
tokens used
196,213
Verdict: ADOPT-WITH-CHANGES

**HIGH finding (must reflect before merge)**

[HIGH-1] Vendi hybrid kernel/window is still arbitrary and mathematically under-specified  
v3’s semantic 0.7 + lexical 0.3 choice has conceptual prior art only: Friedman & Dieng support user-defined and combined similarity functions, but not this weight pair or semantic+5gram as a validated text gate.  
The one-hot sanity is also misstated: score=N holds only when the normalized kernel is exactly identity, i.e. all off-diagonal similarities are zero and K is PSD with K_ii=1. A lexical one-hot component does not make the hybrid score N if the semantic component has nonzero off-diagonals.  
100-turn windows are not supported by Vendi prior art. The 2025 finite-sample paper strengthens concern that empirical Vendi can be sample-size fragile; it does not justify either 100 or 200 as sufficient. Keep 100 only with a preregistered sensitivity test: semantic-only, lexical-only, hybrid 0.5/0.5, 0.7/0.3, and 0.9/0.1 on pilot data.  
Citation: https://arxiv.org/abs/2210.02410 ; https://github.com/vertaix/Vendi-Score ; https://proceedings.mlr.press/v286/ospanov25a.html

[HIGH-2] ICC notation and gate semantics are not merge-safe  
“ICC(2,k) consistency” mixes naming systems. Koo/Li require choosing model, type, and definition; McGraw-Wong distinguishes ICC(C,k) consistency from ICC(A,k) absolute agreement, while Shrout-Fleiss ICC(2,k) is commonly mapped to two-way random absolute-agreement average.  
For ME-1 fallback, consistency ICC can be primary only if the question is “is the IPIP measurement stable across runs/windows?” For DB9 drift/adoption, absolute level shift matters; a systematic Big5 offset can leave consistency high while representing persona drift.  
Before merge, v3 must name exact formulas in one notation, expose both average and single-measure variants, and specify which consumer uses which: ME-1 reliability trigger vs DB9 baseline-positive/negative gate. Do not apply the same 0.6/0.5 threshold to ICC(A,1) without calibration.  
Citation: https://pubmed.ncbi.nlm.nih.gov/27330520/ ; https://www.unistat.com/guide/intraclass-correlation-coefficients/

[HIGH-3] “Murakami 2002/2003 Japanese IPIP-50” is not a valid item-source commitment  
Murakami 2003 is evidence for Japanese lexical Big Five extraction, not a license-cleared Japanese IPIP-50 item corpus. It even warns that Japanese Big Five content may differ in details from English-language content.  
The English IPIP items/scales are public domain, including commercial use, but the design must identify the exact Japanese item source, retrieval URL, and license. The IPIP translations page points to Japanese IPIP translations by Nakayama/Karlin, not Murakami as an IPIP-50 translation source.  
Merge condition: either vendor the exact public-domain Japanese IPIP-50 text with provenance, or ship `language="en"` only and mark Japanese administration blocked/deferred.  
Citation: https://www.jstage.jst.go.jp/article/jjpjspp/11/2/11_KJ00002442203/_article/-char/ja ; https://ipip.ori.org/index.htm ; https://ipip.ori.org/newPermission.htm ; https://ipip.ori.org/newTranslations.htm

[HIGH-4] IPIP administering helper needs anti-demand-characteristics design, not just diagnostics  
Salecha et al. show LLMs infer personality-test context and shift toward socially desirable Big Five answers; reverse-coding reduces but does not eliminate the bias. v3’s persona-conditional prompt plus explicit IPIP item wording is therefore high-risk.  
The helper should avoid announcing “Big Five/IPIP/personality test” in the prompt, isolate items or use constrained scoring, randomize order deterministically, include decoys/control items, and record base-model no-persona controls required by ME-1.  
A stable biased response pattern can produce deceptively high ICC, so this is not a cosmetic issue; it directly affects the DB9 offensive gate.  
Citation: https://arxiv.org/abs/2405.06058 ; https://www.nature.com/articles/s42256-025-01115-6

**MEDIUM finding (decisions.md ADR 反映)**

[MEDIUM-1] Bootstrap output must prevent primary/diagnostic confusion  
`cluster_only=True` primary is compatible with PR #146 if v3 keeps the effective sample size disclosure at 25 clusters/persona. `auto_block=True` may be useful, but JSON must use explicit fields such as `ci_primary` and `ci_diagnostic_auto_block`; quorum code must consume only `ci_primary`. Also forbid pooled-persona CI unless the output is explicitly marked exploratory, because pooling underestimates persona-conditional variance.

[MEDIUM-2] `metrics.tier_b.turn_idx` as `window_index` is tolerable but semantically leaky  
Do not rename the column in this PR, but add helpers that return `window_index`, not raw `turn_idx`, and put `window_start_turn`, `window_end_turn`, `window_size`, and `metric_schema_version` in notes JSON. This avoids downstream code joining a 100-turn aggregate to a single raw turn by accident.

[MEDIUM-3] DB11 follow-up cannot be hand-waved by “DB5 guarantees it”  
The current `raw_dialog` allow-list does not include `individual_layer_enabled`, while DB11 says training eligibility requires `evaluation_epoch=false AND individual_layer_enabled=false`. P4a does not need to implement all DB11 plumbing, but it must not claim no assert is needed. Add an ADR note that Tier B remains eval-only and that DB11 raw-schema/training-view enforcement is a separate required follow-up.

[MEDIUM-4] Multilingual Vendi fairness needs a diagnostic path  
v3 assumes multilingual MPNet fairly compares ja/en mixed utterances. The existing Tier A novelty code currently lazy-loads `all-mpnet-base-v2`, not the multilingual model named in the prompt, so implementation can silently diverge. Add tests that assert the exact model id, plus language-stratified Vendi outputs for ja-only, en-only, and mixed windows.

[MEDIUM-5] ICC sample size and degenerate tests need explicit handling  
n=100 turns is not the ICC sample size once each window is collapsed to one Big5 vector; the effective ICC design is 5 runs × 5 windows × 5 domains/items depending on layout. 25 clusters can support a diagnostic baseline but not publication-grade construct validity. Identical all-constant responses can produce 0/0 in ANOVA formulas, so `ICC=1.0` must be a deliberate degenerate special case, not assumed.

**LOW finding (blockers.md defer 可)**

[LOW-1] Keep 5-point Likert unless a calibration run proves 7-point improves reliability  
IPIP’s standard administration is compatible with 5-point parsing and lower LLM output ambiguity. 7-point may add variance without construct gain. Balanced reverse-keying around 50% is fine, but item order must avoid obvious forward/reverse adjacency.

[LOW-2] Closing P5 residual tests in this PR is appropriate  
Close Vendi identity-kernel score=N and Big5 ICC identical-response convergence in P4a, because the new modules own those invariants. Label them regression/sanity tests, not evidence that the metric is valid.

[LOW-3] LIWC retirement is justified, but copy the honest framing style exactly  
`empath_proxy.py` already says Empath is a secondary psycholinguistic diagnostic and makes no Big5 claim. Tier B module docstrings should match that rigor: IPIP self-report only, no LIWC equivalence, no external-lexicon Big5 inference.

**Prior art summary (web search 必須)**

1. Vendi Score 2023: supports user-defined similarity kernels and shows combined similarity functions can be meaningful, but gives no 0.7/0.3 semantic+lexical weight and no 100/200-turn minimum. score=N requires K=I after normalization. Sources: https://arxiv.org/abs/2210.02410 ; https://github.com/vertaix/Vendi-Score ; finite-sample caution https://proceedings.mlr.press/v286/ospanov25a.html

2. IPIP-NEO Mini-20 vs IPIP-50: official IPIP tables put Mini-IPIP mean alpha around .70 with some dimensions .65-.69, while IPIP-50 broad-domain scales are around mean .84. This supports v3’s IPIP-50 over Mini-20 because Mini-20 can sit on the ME-1 0.6 boundary. Sources: https://ipip.ori.org/MiniIPIPTable.htm ; https://ipip.ori.org/newBigFive5broadTable.htm ; https://www.sciencedirect.com/science/article/abs/pii/S019188690500022X

3. ICC for LLM personality stability: Koo/Li supports selecting model/type/definition and interpreting ICC by CI; absolute agreement is not interchangeable with consistency. Recent LLM psychometric work stresses reliability plus construct validity, and smaller/instruction-sensitive models remain risky. Sources: https://pubmed.ncbi.nlm.nih.gov/27330520/ ; https://www.unistat.com/guide/intraclass-correlation-coefficients/ ; https://www.nature.com/articles/s42256-025-01115-6

4. LIWC vs Empath: Fast et al. show Empath correlates strongly with similar LIWC categories, but that is category-level/topic-emotion similarity, not a Big5 substitute. DB10 Option D is defensible: retire LIWC from Tier B and keep Empath only as Tier A secondary diagnostic. Source: https://arxiv.org/abs/1602.06979

5. Japanese Mini-IPIP/IPIP-50: IPIP English items/scales are public domain for commercial and non-commercial use. Murakami 2003 validates Japanese lexical Big Five conditions, not an IPIP-50 translation/license. Use official IPIP Japanese translation provenance or defer Japanese administration. Sources: https://ipip.ori.org/index.htm ; https://ipip.ori.org/newPermission.htm ; https://ipip.ori.org/newTranslations.htm ; https://www.jstage.jst.go.jp/article/jjpjspp/11/2/11_KJ00002442203/_article/-char/ja

**Closing note**

Adopt v3 hybrid, not v1 or v2, but only after the HIGH fixes. The right final shape is v3 with: Vendi kernel sensitivity instead of hard-coded 0.7/0.3 faith, corrected ICC notation/consumer semantics, license-cleared Japanese IPIP corpus or explicit defer, and anti-social-desirability IPIP administration.

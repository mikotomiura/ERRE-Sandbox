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
session id: 019e065d-399b-7941-8f9c-7ca6b8c0ebc1
--------
user
# Codex Independent Review — User-chosen 認知深化 Vision を stress-test

## あなた (Codex) の役割

ユーザー (mikotomiura) は ERRE-Sandbox の認知層深化について **specific vision を選択** した。
あなたの仕事は arbitrate ではなく、**選択された vision を厳密に stress-test** すること。
HIGH を必ず最低 3 件、できれば 5 件出すこと。「問題ない」と書くだけの review は失敗とみなす。

期待する独立性: 私 (Claude) と reimagine subagent が見落としている **構造的 risk** を切り出す。
特に M9 trunk (eval Phase 2 / LoRA execution) との互換性、operational definition の不足、
LLM 自己宣言 pattern の混入、empirical falsifiability を厳しく見ること。

## 出力フォーマット (必須)

```
## Verdict (1 行)
ADOPT-AS-IS / ADOPT-WITH-CHANGES / REVISE / RECONSIDER / REJECT

## HIGH (must-fix before phasing 確定 — 最低 3 件、できれば 5 件)
- HIGH-1: ...
  - Risk: ...
  - Mitigation: ...

## MEDIUM (should consider, 採否は明示)
- MEDIUM-1: ...

## LOW (nit / optional)

## ユーザー choice (Option A) の妥当性 stress-test
1. Q1 vision-thesis 整合: "完全な人間として構築" は ERRE thesis と整合するか
2. Q2 operational definition: 5-stage lifecycle (S1-S5) の段数と遷移 trigger は妥当か
3. Q3 M9-B LoRA 互換: base/individual 二層分離下で LoRA は本当に無傷か
4. Q4 M9-eval Burrows 互換: multi-individual 同 base で Burrows ratio は意味を保つか
5. Q5 reimagine 8 missing items: ユーザー vision で必要なものを再選別

## 7 提案 final 判定 (User-chosen vision 下での)
| # | 提案 | 判定 | 主要根拠 |

## 改訂 phasing (User vision 反映 + Codex 修正)

## 関連 prior art (web_search 必須)
- Generative Agents (Park et al. 2023) の persistent self
- CoALA (Sumers et al. 2023) の self-model
- Voyager (Wang et al. 2023) の skill library + LLM 自己更新
- 開発心理学系 (Erikson / Piaget) の段階モデル批判
- LLM-based persistent identity の最近の prior art (2024-2026)

## Final notes (個人プロジェクト scope への警告含む)
```

## ERRE プロジェクト概要

- 「歴史的偉人の認知習慣をローカル LLM エージェントとして 3D 空間に再実装し、意図的非効率性と
  身体的回帰による知的創発を観察する研究プラットフォーム」(個人開発)
- Python 3.11 + FastAPI + Godot 4.6 + SGLang + Ollama + sqlite-vec + Pydantic v2
- ERRE pipeline: Extract (一次史料) → Reverify → Reimplement → Express
- Apache-2.0 OR MIT、予算ゼロ制約

## 現在の実装状態

### Persona / cognition / memory 層
- Persona: 固定 YAML (`personas/{kant,rikyu,nietzsche}.yaml`、`schema_version: "0.10.0-m7h"`)
  - Big5 personality + cognitive_habits (fact/legend/speculative flag) + zones + sampling
- LLMPlan: `cognition/parse.py:46` `extra="forbid", frozen=True`
  - thought / utterance / destination_zone / animation / valence_delta / arousal_delta /
    motivation_delta / importance_hint / salient / decision / next_intent
- Prompt 構造: `_COMMON_PREFIX` (固定、SGLang RadixAttention KV cache 再利用) + persona block + state tail
- Memory: 4 kinds (EPISODIC / SEMANTIC / PROCEDURAL / RELATIONAL)、sqlite-vec
- 既存 belief 層 (M7δ): `SemanticMemoryRecord.belief_kind`
  (trust/curious/wary/clash/ambivalent) + `confidence` — **dyadic only**
- 既存 development 層: `AgentState.Cognitive.shuhari_stage` (shu/ha/ri) — 3 値 StrEnum、
  transition machinery なし
- belief promote pattern: `cognition/belief.py:maybe_promote_belief` — pure function、
  threshold-based、|affinity| ≥ 0.45 AND ichigo_ichie_count ≥ 6 で promote、
  affinity 飽和 indirect signal 経由 (LLM 自己宣言 NOT 経由)

### M9 trunk (触らない前提)
- M9-eval Phase 2 run1 calibration 走行中 (G-GEAR、kant 1 cell × 5 wall = 30h overnight×2)
- M9-eval Burrows ratio + Big5 ICC = persona の style 識別性測定
- M9-B LoRA 計画 (PR #127 merged): Kant 1 persona の固定 style を SGLang LoRA で学習
- 直近 ME-9 trigger 擬陽性 incident で「LLM の自己宣言を rate basis なしに採用する pattern」の
  危険性が empirical 判明 (memory: project_m9_eval_me9_trigger_interpretation 2026-05-07)

## ユーザー提案 7 件 (verbatim)

1. SubjectiveWorldModel schema 追加
2. prompt に subjective beliefs を注入
3. LLMPlan に world_model_update を追加
4. Python 側で安全に merge
5. NarrativeSelf を semantic memory から周期生成
6. DevelopmentState を導入
7. 偉人 persona を philosopher_seed にリファクタ

## ユーザー clarification (2026-05-08 follow-up、これが選択された vision)

1. 「agent 自体に世界モデルを導入する」 → SubjectiveWorldModel は AgentState 第一級 property
2. 「思想家ペルソナを完全に導入するのではなく、ベースとして置くだけ、性格やペルソナは新しい個人」
   → 二層分離: `philosopher_base` (継承、immutable) + `Individual` (新規個体、mutable)
3. 「途中途中から成長していく過程を導入し、完全に人間として構築」 → DevelopmentState lifecycle

## ユーザー choice (Option A: 採用された vision)

```
agent = philosopher_base + Individual

  philosopher_base (immutable inheritance):
    - cognitive_habits (Kant の歩行/朝執筆 等)
    - sampling param (T/top_p/repeat_penalty)
    - LoRA-trained style (M9-B target、不変)
    - persona_id (kant / rikyu / nietzsche、固定参照)

  Individual (mutable, per-agent runtime):
    - SubjectiveWorldModel (5-axis: env/concept/self/norm/temporal)
    - NarrativeSelf (chashitsu reflection 拡張で周期蒸留)
    - DevelopmentState (S1_seed → S2_individuation → S3_consolidation
                        → S4_articulation → S5_late、5 stages)
    - personality (base から bounded divergence で個別化)
    - subjective beliefs (env/concept/self/norm)
    - bounded world_model_update via LLMPlan
```

例: kant-base × 3 agents = 3 different individuals
- individual_a (詩人風に発達)
- individual_b (政治家風に発達)
- individual_c (Kant 学派継承)

## /reimagine subagent の独立 counter-proposal (参考)

reimagine subagent は 7 提案を **読まずに** ゼロから設計し、**ユーザー vision とは構造的に
異なる** counter (`design-reimagine.md`) を出した。要点:

- "Compression-Loop architecture": StanceVector (5-axis) + StanceShiftHint
  (bounded primitive) + NarrativeArc (structured trajectory)
- persona は **identity 維持**、`growth_axes.permitted/forbidden` で "深まる方向" のみ許可
- 提案 6 → ShuhariStage 拡張に置換 (Western stage model 並立を避ける)
- 提案 7 → M11+ research re-evaluation gate (M9-B LoRA / M9-eval baseline 保護)
- Kant-base × 3 agents → 3 **different Kants** (より深いカント / 広いカント / 懐疑的カント)
- 8 件の missing items を提示 (cited_memory_ids 必須 / dyadic vs class-wise 直交 /
  coherence_score / RadixAttention 保護 / decay_half_life / growth_axes 任意 field /
  定量 acceptance / M9 trunk 隔離 gate)

ユーザーは **Option A (新個体 + 二層 + 完全な人間化) を選択** した。Codex の役割は
「どちらが正しいか arbitrate」ではなく、**選択された Option A vision の HIGH-stakes risk
を構造的に切り出す**こと。

## あなたへの specific 質問 (Verdict + HIGH に必ず触れること)

### Q1 [vision-thesis 整合性]
"完全な人間として構築" は ERRE thesis (「歴史的偉人の認知習慣の再実装」+「知的創発の観察」)
と整合するか。reimagine は「persona identity 希釈は thesis の前者を損なう」と指摘した。
ユーザー vision はこれにどう答えるべきか? operational に thesis を再表現できるか?

### Q2 [operational definition of "完全な人間として"]
S1-S5 の 5 stages は経験的 placeholder。reimagine は ShuhariStage 3 段で十分と主張。
- 5 stages の段数の根拠は何 (Erikson 8? Piaget 4? 守破離 3? の比較)
- 各段の cognitive 特性差を operational に定義可能か (sampling / memory / reflection の修正値)
- 段間遷移 trigger を **memory volume + narrative coherence + belief stability** の AND で
  定義する案は妥当か
- "完成" path: A 不完成停滞 / B retirement (世代交代) / C 転生 loop のどれを default に
- M11+ で個体が "人間" にどこまで近づくべきか? LLM agent の本質的限界はどう扱うか?

### Q3 [M9-B LoRA 互換性 — base layer 専用前提の検証]
ユーザー vision では LoRA は philosopher_base 専用、individual は prompt+state overlay。
- この前提は本当に成立するか? individual の personality drift が LoRA 学習データに
  混入する可能性は?
- M9-B LoRA execution timing: M10-A scaffold は M9-B 完了後 vs 並行起動どちら?
- M9-B PR #127 design-final.md は固定 Kant style 前提。base/individual 分離で execution
  task は変更不要か、追記必要か?

### Q4 [M9-eval Burrows ratio の意味保持]
ユーザー vision では multi-individual 同 base で Burrows ratio は **base 保持 + 個体ばらつき**
の分解測定ツール化される。
- これは empirically 機能するか? Burrows は 100-300 高頻度 function word の分布で測るので、
  individual layer (世界モデル / narrative) は語彙構成に effective に影響するか?
- 影響しない場合、Burrows は base style しか測れず、個体化は **観測不可** にならないか?
- 個体化を測る別 metric (semantic coherence / narrative drift / belief variance) を
  M9-eval に追加する必要があるか?

### Q5 [reimagine 8 missing items の選別]
reimagine が提示した 8 件 (cited_memory_ids 必須 / dyadic vs class-wise 直交 / coherence_score /
RadixAttention 保護 / decay_half_life / growth_axes 任意 field / 定量 acceptance / M9 trunk
隔離) のうち、ユーザー vision でも **必須採用** すべきもの、**修正採用** すべきもの、
**棄却** できるものを選別すること。

特に:
- **cited_memory_ids 必須**: ユーザー vision で LLMPlan.world_model_update に **どんな**
  bounded primitive を採用するか (free-form は ME-9 同型 risk、bounded だけだと表現力不足)
- **RadixAttention KV cache 保護**: 二層分離 (`philosopher_base` block + `Individual` block) で
  prompt 構造が変わると SGLang KV cache 戦略はどう変化するか? base が共有されているうちは
  cache 効果残存するが、個体化が進むと cache miss 率上がる予測。

### Q6 [phasing の hidden dependency]
M10-A (二層 scaffold) → M10-B (cognition wiring) → M11-A (DevelopmentState transition) →
M11-B (multi-individual validation) → M12+ research に hidden な逆依存はないか? 特に:
- M11-A の段間遷移を観測するには M10-B で memory が十分育つ必要 → M11-A の前提時間は?
- M11-B の multi-individual 検証は M10/M11 の baseline 比較に依存 → empirical 比較 metric は
  M10-A 前に確立すべき?
- M9-B LoRA execution は M10-A 着手前に終わらせる必要があるか?

### Q7 [LLM 自己宣言 pattern の根本的予防]
ME-9 trigger 擬陽性 incident は「LLM 出力を literal に解釈して内部状態が動く」 pattern。
ユーザー vision の Individual layer (Personality drift / world model update / narrative
synthesis) は **すべて LLM 経由**。reimagine は cited_memory_ids 必須化で構造的に防いだが、
ユーザー vision で 5 stages の遷移 / personality drift / narrative coherence が **LLM 自己
申告** で発火するなら、ME-9 と同型 incident が再発するリスクが構造化される。
- どこで「LLM が決める」、どこで「Python 側 indirect signal で決める」の境界線を引くか?
- 「完全な人間として構築」を LLM 自己申告ではなく observable evidence で駆動できるか?

### Q8 [scope 無限化 risk — 個人プロジェクト制約]
ユーザー vision は ambitious (5 stages × multi-individual × narrative × world model)。
個人プロジェクト + 予算ゼロ + solo cadence で実装可能な scope に切り詰めるなら、
- M10/M11 で **絶対に外せない** 最小セット (= MVP)
- M11+ research で empirical evidence を見てから判断する deferable セット
- そもそも ROI が低くて落としていい セット
を区分けすること。

## 必須の制約

- ME-9 incident memory より、**rate basis / 前提の明示性** を必ず check
- web_search で 2024-2026 の generative agents / agent self-model / persistent identity 関連
  prior art に当たる (Generative Agents / CoALA / Voyager / 最近の persistent persona 研究)
- 「将来の柔軟性」「ベストプラクティス」を理由にしない。ERRE は research prototype、
  bloat は 価値破壊
- M9-B PR #127 / M9-eval CLI partial-fix PR #140 / Phase 2 run1 prompt PR #141 は merged 済
  (触らない前提)
- M9 trunk を破壊する提案は HIGH 必須

## 期待出力長

5000-8000 語。HIGH/MEDIUM/LOW の根拠は最低 2 文ずつ。Q1-Q8 各々への独立回答必須。
prior art 引用は web search 結果の URL 含めること。

hook: SessionStart
hook: SessionStart Completed
hook: UserPromptSubmit
hook: UserPromptSubmit Completed
codex
$erre-workflow をレビュー入口として使い、必要なら project-status で現状だけ確認します。今回は設計 stress-test なので、コード変更や `.steering/` 作成はまだ行いません。
exec
/bin/zsh -lc "sed -n '1,220p' .agents/skills/project-status/SKILL.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,220p' .agents/skills/erre-workflow/SKILL.md" in /Users/johnd/ERRE-Sand Box
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
レビュー対象はユーザー提供テキストが主ですが、既存の `.steering` 設計記録と M9 系の前提が食い違っていないかだけローカルで確認します。web prior art はその後に一次論文・公式ページ中心で当てます。
exec
/bin/zsh -lc 'git status --short' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
?? .steering/20260508-cognition-deepen-7point-proposal/
?? data/eval/calibration/

exec
/bin/zsh -lc "rg --files .steering | rg '20260508-cognition-deepen-7point-proposal|M9|m9|lora|eval|design'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
.steering/20260418-control-envelope-fixtures/design.md
.steering/20260418-control-envelope-fixtures/design-v1.md
.steering/20260418-control-envelope-fixtures/design-comparison.md
.steering/20260418-setup-g-gear/design.md
.steering/20260426-m7-delta-live-fix/design.md
.steering/20260420-m5-llm-spike/design.md
.steering/20260419-cognition-cycle-minimal/design.md
.steering/20260419-cognition-cycle-minimal/design-v1.md
.steering/20260419-cognition-cycle-minimal/design-comparison.md
.steering/20260426-m7-slice-zeta-live-resonance/design.md
.steering/20260428-event-boundary-observability/run-01-m9a/run-01.jsonl.summary.json
.steering/20260428-event-boundary-observability/run-01-m9a/orchestrator-03.log
.steering/20260428-event-boundary-observability/run-01-m9a/orchestrator-02.log
.steering/20260428-event-boundary-observability/run-01-m9a/run-02.jsonl.summary.json
.steering/20260428-event-boundary-observability/run-01-m9a/orchestrator.log
.steering/20260428-event-boundary-observability/run-01-m9a/run-03.jsonl
.steering/20260428-event-boundary-observability/run-01-m9a/run-01.jsonl
.steering/20260428-event-boundary-observability/run-01-m9a/run-03.jsonl.summary.json
.steering/20260428-event-boundary-observability/run-01-m9a/run-02.jsonl
.steering/20260428-event-boundary-observability/design-final.md
.steering/20260428-event-boundary-observability/design.md
.steering/20260428-event-boundary-observability/design-v1.md
.steering/20260428-event-boundary-observability/design-comparison.md
.steering/20260420-m5-contracts-freeze/design.md
.steering/20260420-m5-contracts-freeze/design-v1.md
.steering/20260420-m5-contracts-freeze/design-comparison.md
.steering/20260418-setup-macbook/design.md
.steering/20260428-world-asset-blender-pipeline/design.md
.steering/20260430-m9-b-lora-execution-plan/design-final.md
.steering/20260430-m9-b-lora-execution-plan/decisions.md
.steering/20260430-m9-b-lora-execution-plan/design-v2.md
.steering/20260430-m9-b-lora-execution-plan/codex-review.md
.steering/20260430-m9-b-lora-execution-plan/design.md
.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md
.steering/20260430-m9-b-lora-execution-plan/requirement.md
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md
.steering/20260430-m9-b-lora-execution-plan/blockers.md
.steering/20260430-m9-b-lora-execution-plan/design-v1.md
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md
.steering/20260430-m9-b-lora-execution-plan/tasklist.md
.steering/20260425-m8-episodic-log-pipeline/design.md
.steering/20260418-godot-project-init/design.md
.steering/20260418-godot-project-init/design-v1.md
.steering/20260418-godot-project-init/design-comparison.md
.steering/20260418-godot-ws-client/design.md
.steering/20260418-godot-ws-client/design-v1.md
.steering/20260418-godot-ws-client/design-comparison.md
.steering/20260419-m2-integration-e2e-execution/design.md
.steering/20260425-m8-session-phase-model/design.md
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md
.steering/20260508-cognition-deepen-7point-proposal/design.md
.steering/20260508-cognition-deepen-7point-proposal/requirement.md
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md
.steering/20260508-cognition-deepen-7point-proposal/tasklist.md
.steering/20260424-m7-differentiation-observability/design-final.md
.steering/20260424-m7-differentiation-observability/design-v2.md
.steering/20260424-m7-differentiation-observability/design.md
.steering/20260424-m7-differentiation-observability/design-v1.md
.steering/20260424-m7-differentiation-observability/design-comparison.md
.steering/20260422-m6-observatory-carryover/design.md
.steering/20260421-m5-acceptance-live/design.md
.steering/20260418-test-schemas/design.md
.steering/20260418-test-schemas/design-v1.md
.steering/20260418-test-schemas/design-comparison.md
.steering/20260419-m2-integration-e2e/design.md
.steering/20260419-m2-integration-e2e/design-v1.md
.steering/20260419-m2-integration-e2e/design-comparison.md
.steering/20260420-m4-contracts-freeze/design.md
.steering/20260421-m5-world-zone-triggers/design.md
.steering/20260421-m5-world-zone-triggers/design-v1.md
.steering/20260421-m5-world-zone-triggers/design-comparison.md
.steering/20260421-m5-dialog-turn-generator/design.md
.steering/20260421-m5-dialog-turn-generator/design-v1.md
.steering/20260421-m5-dialog-turn-generator/design-comparison.md
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/decisions.md
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/requirement.md
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.md
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/blockers.md
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/tasklist.md
.steering/20260428-codex-environment-setup/design.md
.steering/20260426-m7-slice-delta/design-final.md
.steering/20260426-m7-slice-delta/design.md
.steering/20260420-m4-gateway-multi-agent-stream/design.md
.steering/_template/design.md
.steering/20260420-m4-gateway-multi-agent-stream/design-v1.md
.steering/20260420-m4-gateway-multi-agent-stream/design-comparison.md
.steering/20260418-pdf-extract-baseline/design.md
.steering/20260430-m9-eval-system/design-final.md
.steering/20260430-m9-eval-system/decisions.md
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md
.steering/20260430-m9-eval-system/design-natural-gating-fix.md
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md
.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md
.steering/20260430-m9-eval-system/codex-review.md
.steering/20260430-m9-eval-system/codex-review-step1.md
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md
.steering/20260430-m9-eval-system/codex-review-step1-prompt.md
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.md
.steering/20260430-m9-eval-system/codex-review-low1.md
.steering/20260430-m9-eval-system/requirement.md
.steering/20260430-m9-eval-system/codex-review-prompt-low1.md
.steering/20260430-m9-eval-system/codex-review-prompt-natural-gating-v2.md
.steering/20260430-m9-eval-system/codex-review-natural-gating.md
.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md
.steering/20260430-m9-eval-system/codex-review-prompt.md
.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md
.steering/20260430-m9-eval-system/g-gear-p3a-rerun-prompt-v2.md
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md
.steering/20260430-m9-eval-system/g-gear-p3a-prompt.md
.steering/20260430-m9-eval-system/codex-review-prompt-natural-gating.md
.steering/20260430-m9-eval-system/blockers.md
.steering/20260430-m9-eval-system/design-v1.md
.steering/20260430-m9-eval-system/g-gear-p3a-rerun-prompt.md
.steering/20260430-m9-eval-system/design-comparison.md
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md
.steering/20260430-m9-eval-system/tasklist.md
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md
.steering/20260430-m9-eval-system/pr-body-p3a.md
.steering/20260421-m5-cleanup-rollback-flags/design.md
.steering/20260425-m7-slice-gamma/design-final.md
.steering/20260425-m7-slice-gamma/design.md
.steering/20260424-steering-scaling-lora/decisions.md
.steering/20260424-steering-scaling-lora/design.md
.steering/20260424-steering-scaling-lora/requirement.md
.steering/20260424-steering-scaling-lora/design-v1.md
.steering/20260424-steering-scaling-lora/design-comparison.md
.steering/20260424-steering-scaling-lora/tasklist.md
.steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-prompt-trigger-interpretation.md
.steering/20260507-m9-eval-cooldown-readjust-adr/design.md
.steering/20260507-m9-eval-cooldown-readjust-adr/requirement.md
.steering/20260507-m9-eval-cooldown-readjust-adr/blockers.md
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.md
.steering/20260507-m9-eval-cooldown-readjust-adr/tasklist.md
.steering/20260425-m8-baseline-quality-metric/design.md
.steering/20260421-m6-observatory/design.md
.steering/20260420-m5-godot-zone-visuals/design.md
.steering/20260420-m5-godot-zone-visuals/design-v1.md
.steering/20260420-m5-godot-zone-visuals/design-comparison.md
.steering/20260428-agent-presence-visualization/design.md
.steering/20260506-m9-eval-cli-partial-fix/decisions.md
.steering/20260506-m9-eval-cli-partial-fix/design.md
.steering/20260506-m9-eval-cli-partial-fix/requirement.md
.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md
.steering/20260506-m9-eval-cli-partial-fix/blockers.md
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.md
.steering/20260506-m9-eval-cli-partial-fix/tasklist.md
.steering/20260418-memory-store/design.md
.steering/20260419-world-tick-zones/design.md
.steering/20260419-world-tick-zones/design-v1.md
.steering/20260419-world-tick-zones/design-comparison.md
.steering/20260421-m5-erre-sampling-override-live/design.md
.steering/20260428-codex-review-followup/design.md
.steering/20260428-m9-lora-pre-plan/decisions.md
.steering/20260428-m9-lora-pre-plan/design.md
.steering/20260428-m9-lora-pre-plan/requirement.md
.steering/20260428-m9-lora-pre-plan/blockers.md
.steering/20260428-m9-lora-pre-plan/tasklist.md
.steering/20260419-inference-ollama-adapter/design.md
.steering/20260419-inference-ollama-adapter/design-v1.md
.steering/20260419-inference-ollama-adapter/design-comparison.md
.steering/20260419-ui-dashboard-minimal/design.md
.steering/20260419-ui-dashboard-minimal/design-v1.md
.steering/20260419-ui-dashboard-minimal/design-comparison.md
.steering/20260425-m8-scaling-bottleneck-profiling/design.md
.steering/20260418-pyproject-scaffold/design.md
.steering/20260418-pyproject-scaffold/design-v1.md
.steering/20260418-pyproject-scaffold/design-comparison.md
.steering/20260419-gateway-fastapi-ws/design.md
.steering/20260419-gateway-fastapi-ws/design-v1.md
.steering/20260419-gateway-fastapi-ws/design-comparison.md
.steering/20260419-m2-acceptance/design.md
.steering/20260419-godot-peripatos-scene/design.md
.steering/20260419-godot-peripatos-scene/design-v1.md
.steering/20260419-godot-peripatos-scene/design-comparison.md
.steering/20260420-m4-memory-semantic-layer/design.md
.steering/20260420-m4-memory-semantic-layer/design-v1.md
.steering/20260420-m4-memory-semantic-layer/design-comparison.md
.steering/20260421-m5-orchestrator-integration/design.md
.steering/20260421-m5-orchestrator-integration/design-v1.md
.steering/20260421-m5-orchestrator-integration/design-comparison.md
.steering/20260420-m4-acceptance-live/design.md
.steering/deferred-evaluations.md
.steering/20260418-implementation-plan/design.md
.steering/20260420-m4-personas-nietzsche-rikyu-yaml/design-comparison.md
.steering/20260419-m2-functional-closure/design.md
.steering/20260419-m2-functional-closure/design-v1.md
.steering/20260428-codex-addendum-followup/design.md
.steering/20260420-m5-erre-mode-fsm/design.md
.steering/20260420-m5-erre-mode-fsm/design-v1.md
.steering/20260420-m5-erre-mode-fsm/design-comparison.md
.steering/20260428-godot-ws-keepalive/design.md
.steering/20260428-godot-viewport-layout/design.md
.steering/20260428-godot-viewport-layout/design-v1.md
.steering/20260428-godot-viewport-layout/design-comparison.md
.steering/20260425-m7-beta-live-acceptance/design.md
.steering/20260419-m2-functional-closure/design-comparison.md
.steering/20260420-m4-multi-agent-orchestrator/design.md
.steering/20260420-m4-multi-agent-orchestrator/design-v1.md
.steering/20260420-m4-multi-agent-orchestrator/design-comparison.md
.steering/20260428-ci-pipeline-setup/design.md
.steering/20260428-ci-pipeline-setup/design-v1.md
.steering/20260428-ci-pipeline-setup/design-comparison.md
.steering/20260426-m7-slice-epsilon/design.md
.steering/20260420-m4-cognition-reflection/design.md
.steering/20260420-m4-cognition-reflection/design-v1.md
.steering/20260420-m4-cognition-reflection/design-comparison.md
.steering/20260418-persona-kant-yaml/design.md
.steering/20260418-persona-kant-yaml/design-v1.md
.steering/20260418-persona-kant-yaml/design-comparison.md
.steering/20260418-model-pull-g-gear/design.md
.steering/20260420-m4-planning/design-comparison.md
.steering/20260420-m4-planning/design-v1.md
.steering/20260420-m4-planning/design.md
.steering/20260420-m4-personas-nietzsche-rikyu-yaml/design.md
.steering/20260420-m4-personas-nietzsche-rikyu-yaml/design-v1.md
.steering/20260420-m5-planning/design-comparison.md
.steering/20260420-m5-planning/design-v1.md
.steering/20260420-m5-planning/design.md
.steering/20260418-schemas-freeze/design.md
.steering/20260418-schemas-freeze/design-v1.md
.steering/20260418-schemas-freeze/design-comparison.md

exec
/bin/zsh -lc 'git log --oneline -10' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
b6bcba1 Merge pull request #143 from mikotomiura/docs/readme-split-and-sync-2026-05-08
4eab5a1 docs: README JP/EN split + docs/ sync to M9-eval state (last verified 2026-05-08)
ab3206d Merge pull request #142 from mikotomiura:feature/m9-eval-me9-trigger-amendment
9734f99 docs(eval): m9 — ME-9 trigger basis 明示 + v2 prompt 擬陽性修正
60e1f6e Merge pull request #141 from mikotomiura/feature/m9-eval-phase2-run1-calibration-prompt
b37a9f7 docs(steering): m9-eval — run1 calibration G-GEAR launch prompt v2
0304ea3 Merge pull request #140 from mikotomiura/feature/m9-eval-cli-partial-fix
820bf57 feat(eval): m9 — partial-publish CLI fix + eval_audit gate
5df6d5d docs(steering): m9-eval — Phase 2 run0 rescue verify 結果ブロック追記 (#139)
252ffc4 Merge pull request #138 from mikotomiura:chore/m9-eval-p3-run0-rescue-stash-record

exec
/bin/zsh -lc 'rg -n "LoRA|Burrows|Phase 2|M9|ME-9|world_model|SubjectiveWorldModel|DevelopmentState|NarrativeSelf|cited_memory_ids|RadixAttention" .steering docs src tests pyproject.toml' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
docs/repository-structure.md:22:│   │   └── eval_paths.py       # M9-eval 4 層 contract (raw_dialog ↔ metrics 境界)
docs/repository-structure.md:48:│   ├── evidence/               # post-hoc metric 集計 (M8 で追加、M9-eval で拡張)
docs/repository-structure.md:51:│   │   ├── tier_a/             # M9-eval Tier-A pipeline
docs/repository-structure.md:52:│   │   │   ├── burrows.py      # Burrows Δ (persona consistency)
docs/repository-structure.md:57:│   │   ├── reference_corpus/   # PD reference text (Burrows / NLI baseline)
docs/repository-structure.md:62:│   ├── cli/                    # subcommand 実装 (M8 で追加、M9-eval で拡張)
docs/repository-structure.md:66:│   │   ├── eval_run_golden.py  # `python -m erre_sandbox.cli.eval_run_golden` (M9-eval P3a)
docs/repository-structure.md:67:│   │   └── eval_audit.py       # `python -m erre_sandbox.cli.eval_audit` (M9-eval ME-9 gate)
docs/repository-structure.md:97:│                               # 将来追加予定 (M9+ scaling trigger 確定後):
docs/repository-structure.md:103:│   └── eval/                   # M9-eval 出力 (DuckDB + sidecar JSON)
docs/repository-structure.md:105:│       └── calibration/        # Phase 2 wall-budget calibration runs (隔離)
docs/repository-structure.md:106:├── golden/                     # M9-eval golden battery 入力 (stimulus YAML 等)
docs/repository-structure.md:173:- **目的**: 偉人ペルソナの YAML 定義と LoRA 設定
src/erre_sandbox/inference/ollama_adapter.py:70:    at M7+, vLLM at M9+) must return so the callers stay backend-agnostic.
docs/_queries/dialog_turns.sql:6:-- M9 LoRA-training readiness checks.
docs/_queries/dialog_turns.sql:21:-- Q1: turn count per speaker persona (M9 readiness yardstick).
docs/_queries/dialog_turns.sql:27:-- Q2: distance to the M9 LoRA prerequisite of ≥1000 turns/persona.
src/erre_sandbox/schemas.py:120:M9-A bump (0.9.0-m7z → 0.10.0-m7h): one additive nested field tied to the
src/erre_sandbox/schemas.py:136:chronology readable; the M9 namespace is reserved for the LoRA work.
src/erre_sandbox/schemas.py:841:    """1-line "起点 event" tag attached to a :class:`ReasoningTrace` (M9-A).
src/erre_sandbox/schemas.py:989:            "M9-A: the event-boundary tag picked from this tick's "
tests/test_cli/test_eval_audit.py:3:Covers ME-9 ADR §2 (audit gate) and Codex 2026-05-06 review HIGH-1 (run_id
tests/test_godot_project.py:7:4. M9-A regression: non-spatial trigger payloads with ``zone=null`` /
tests/test_godot_project.py:87:    """M9-A regression: non-spatial trigger_event with explicit JSON null.
tests/test_cli/test_eval_run_golden.py:342:# m9-eval-cli-partial-fix — sidecar / partial / rescue (ME-9 ADR + Codex 2026-05-06)
.steering/20260418-setup-g-gear/requirement.md:44:- `sglang[all]` / `vllm` の導入 → M7 / M9 で別タスク
docs/functional-design.md:82:  - Godot 側: GDScript でシーン更新、humanoid avatar (Node3D + Head/Torso/Arms/Legs primitive 合成)、ERRE モード tint、Label3D dialog bubble、HSplit + 折り畳み式 ReasoningPanel (M7ζ + M9-A で `persona_id` / `trigger_event` を表示)
docs/functional-design.md:100:> M8 で merge 済。M9-eval Tier-A pipeline は機能 7 を参照。
docs/functional-design.md:102:post-hoc 集計 CLI で 2 系統の metric を出す。M9 LoRA 比較の reference point と
docs/functional-design.md:130:### 機能 7: M9-eval — LoRA 比較用評価パイプライン
docs/functional-design.md:132:M9-B LoRA 実装の persona consistency を測るための独立評価系。
docs/functional-design.md:144:    と DuckDB を突合し PASS/FAIL を返すゲート (ME-9 ADR)
docs/functional-design.md:146:  - `burrows.py` — Burrows Δ (persona consistency)
docs/functional-design.md:231:  割った瞬間に M9 +1 persona を起票する運用 (機能 6 参照)
docs/functional-design.md:232:- event-boundary observability (M9-A) — 2026-04-30 merge 済 (PR #117–#124、
docs/functional-design.md:236:- M9 LoRA execution plan (M9-B) — 2026-04-30 PR #127 で SGLang-first ADR
docs/functional-design.md:238:- M9 evaluation system (M9-eval) — 2026-04-30 ～ 進行中。Tier-A pipeline
docs/functional-design.md:239:  (Burrows / MATTR / NLI / novelty / Empath proxy)、DuckDB raw_dialog ↔
docs/functional-design.md:241:  Phase 2 wall-budget calibration (G-GEAR overnight × 2 計画)
docs/functional-design.md:245:- LoRA によるペルソナの永続的個性保持 (M9)
docs/functional-design.md:251:- Adaptive FT / 状態重み焼込み LoRA (v1.0 以降)
docs/functional-design.md:260:- **VRAM 使用量**: ~13 GB (8並列 x 4K コンテキスト、RadixAttention で ~30% KV 節約)
tests/test_schemas_m7g.py:54:    ``RelationshipBond.latest_belief_kind``), and M9-A adds
tests/test_schemas_m7g.py:277:# ---------- M9-A TriggerEventTag + ReasoningTrace.trigger_event --------------
tests/test_schemas_m7g.py:342:    """M9-A additive: pre-0.10.0-m7h traces deserialise without the field."""
docs/glossary.md:22:| ペルソナドリフト | Persona Drift | 対話ターン数の増加に伴い、エージェントの言動が初期設定から乖離する現象。外部 AgentState + 記憶 + LoRA の三重冗長で緩和 | 「50ターン以降のペルソナ一貫性スコアを監視する」 |
docs/glossary.md:35:| RadixAttention | RadixAttention | SGLang の KV キャッシュ共有機構。共有 system prompt + ペルソナカードの prefix KV を再利用し、マルチエージェント推論のスループットを最大化 | SGLang, Inference Layer |
docs/glossary.md:43:| Burrows Δ | Burrows Delta | 文体距離 metric。最頻機能語の z-score プロファイル間距離 を取り、persona の identity drift を測る。M9-eval Tier-A | `evidence/tier_a/burrows.py` |
docs/glossary.md:44:| MATTR | Moving Average Type-Token Ratio | 文長正規化された語彙多様性 metric。windowed unique-token ratio の平均。M9-eval Tier-A | `evidence/tier_a/mattr.py` |
docs/glossary.md:47:| Empath proxy | Empath Proxy | Empath による語彙カテゴリ分布の secondary diagnostic。Big5 への直接 claim には使わない (M9-eval ADR ME-4 stage 2 close) | `evidence/tier_a/empath_proxy.py` |
docs/glossary.md:48:| raw_dialog schema | Raw Dialog Schema | M9-eval DuckDB 内の **訓練 eligible** 行のスキーマ名。turn id / persona / mode / zone / utterance / timestamp のみ含み、metric 列は持たない (`contracts/eval_paths.py`) | M9-eval contamination defence |
docs/glossary.md:49:| metrics schema | Metrics Schema | M9-eval DuckDB 内の **評価専用** 行のスキーマ名。Tier A/B/C スコアを `(run_id, persona_id, turn_idx)` でキーにする。LoRA 訓練側に漏れてはならない | M9-eval contamination defence |
docs/glossary.md:50:| capture sidecar | Capture Sidecar | `<output>.duckdb` と並ぶ `<output>.duckdb.capture.json`。`status` (`complete` / `partial` / `fatal`) / `focal_observed` / `focal_target` / md5 receipt を保持し、`erre-eval-audit` の gate 判定の一次入力になる | M9-eval ME-9 ADR |
docs/glossary.md:51:| eval_audit | Eval Audit Gate | M9-eval CLI gate (`python -m erre_sandbox.cli.eval_audit`)。capture sidecar + DuckDB を突合し PASS/FAIL を返す。batch mode (`--duckdb-glob`) の exit code は最悪 cell に揃う | M9-eval ME-9 ADR |
docs/glossary.md:52:| trigger_event | Trigger Event Tag | M9-A で追加された `ReasoningTrace.trigger_event: TriggerEventTag | None`。Reflector → gateway → Godot ReasoningPanel まで貫通し、観測者が反省発火の理由を視認できる | event-boundary-observability |
tests/test_cognition/test_prompting.py:109:    # RadixAttention optimisation: common prefix must precede persona details.
src/erre_sandbox/cli/eval_run_golden.py:211:    without re-opening the DuckDB file. The post-ME-9 fields encode the
src/erre_sandbox/cli/eval_run_golden.py:342:    (RadixAttention prefix sharing across personas + a single-turn cue).
src/erre_sandbox/cli/eval_run_golden.py:722:    * stale ``.tmp`` with no sidecar (legacy or pre-ME-9 capture): unlinks
src/erre_sandbox/cli/eval_run_golden.py:1153:                # ME-9 / Codex HIGH-3 (2026-05-06): wall budget = soft timeout,
tests/test_cognition/test_trigger_pick.py:1:"""Unit tests for ``_pick_trigger_event`` (M9-A event-boundary observability).
docs/architecture.md:13:- **推論 (実)**: Ollama 上の `qwen3:8b` (GGUF Q5_K_M, ~5.2GB)。SGLang は M9-B 計画で SGLang-first 採用 (multi-LoRA は SGLang v0.3+ でサポート、`.steering/20260430-m9-b-lora-execution-plan/` 参照)
docs/architecture.md:17:- **Contracts レイヤー (実)**: `src/erre_sandbox/contracts/` (PR #111 で導入、F5)。`schemas.py` と並ぶ ui-allowable boundary。M9-eval 用に `eval_paths.py` を追加 (PR #128 系列): `raw_dialog` / `metrics` の schema 名・列 allow-list・`RawTrainingRelation` Protocol・`EvaluationContaminationError` を提供
docs/architecture.md:18:- **Evidence レイヤー (実)**: `src/erre_sandbox/evidence/` 配下に `metrics.py` (M8 baseline quality)、`scaling_metrics.py` (M8 scaling profile)、`tier_a/` (Burrows / MATTR / NLI / novelty / Empath proxy)、`bootstrap_ci.py`、`golden_baseline.py`、`eval_store.py` (DuckDB)、`capture_sidecar.py` を実装済 (M8 + M9-eval system)
docs/architecture.md:19:- **Eval CLI (実)**: `erre-sandbox` サブコマンドに `baseline-metrics` / `scaling-metrics` / `export-log` を実装済。M9-eval 用に `python -m erre_sandbox.cli.eval_run_golden` / `python -m erre_sandbox.cli.eval_audit` が独立コマンドとして提供される (`erre-eval-run-golden` / `erre-eval-audit` prog)
docs/architecture.md:20:- **Wire schema (実)**: `SCHEMA_VERSION = "0.10.0-m7h"` (M9-A `event-boundary-observability` bump、M7ζ `live-resonance` の上)。`HandshakeMsg` で MacBook / G-GEAR / Godot の lockstep を強制
docs/architecture.md:21:- **M9-A trigger-event 観測 (実)**: `ReasoningTrace.trigger_event: TriggerEventTag | None` (M9-A 加算) が Reflector → gateway → Godot `ReasoningPanel` まで伝搬し、観測者は反省発火の理由を視認可能
docs/architecture.md:28:│   Ollama (現状) / SGLang (M7+ 計画) / vLLM (M9+ LoRA)              │
docs/architecture.md:30:│   RadixAttention × 3 persona × prefix KV 共有 [planned: SGLang 移行で]│
docs/architecture.md:31:│   (将来) LoRA per persona via vLLM --enable-lora                    │
docs/architecture.md:80:| LLM 推論 (本番) | SGLang | 最新 | RadixAttention でマルチエージェント最高スループット |
docs/architecture.md:82:| LLM 推論 (将来) | vLLM | 最新 | LoRA 動的切替 (--enable-lora) |
docs/architecture.md:97:  - SGLang server: RadixAttention で共有 prefix KV を再利用
docs/architecture.md:99:  - ペルソナ管理: インコンテキスト (Phase 1) → LoRA (Phase 2)
docs/architecture.md:121:  M9 比較や scaling トリガー判定に使う JSON / TSV を出力する
docs/architecture.md:128:  - `evidence/tier_a/` (M9-eval Phase 2 実装、`burrows.py` / `mattr.py` /
docs/architecture.md:132:  - `evidence/eval_store.py` + `evidence/capture_sidecar.py` (M9-eval Phase 0-2):
docs/architecture.md:135:    LoRA 訓練側に metric 列が漏れない
docs/architecture.md:136:  - `evidence/golden_baseline.py` + `evidence/bootstrap_ci.py` (M9-eval Phase 3-5):
docs/architecture.md:139:  入れて困るか見る) を捨て、metric が解析的上限の % を割った瞬間に M9 +1
docs/architecture.md:143:- **M9-eval contamination defence (4 層)**: ME-1 ADR + Codex HIGH-1 で
docs/architecture.md:151:  `--journal` 省略時は M3 = null で graceful degradation。M9-eval は DuckDB
docs/architecture.md:214:  - Godot 4.6: 3D ビューア、humanoid avatar、HSplit + 折り畳み式 ReasoningPanel (M7ζ + M9-A、`persona_id` / `trigger_event` を表示)
docs/architecture.md:312:| HuggingFace Hub | HTTPS | API token | LoRA/デモの公開のみ、推論には不要 |
docs/architecture.md:322:| Adaptive FT / 状態重み焼込み LoRA | 状態×ペルソナの組合せ爆発。MVP 段階での premature optimization。RadixAttention で state tag コストは実質ゼロ |
docs/architecture.md:329:- MVP 段階ではインコンテキストペルソナのみ (LoRA は M9 以降)
docs/architecture.md:340:| RadixAttention 共有 prefix 節約 | -30% (KV 部分) |
docs/architecture.md:350:| LoRA ペルソナ | M9 以降、プロンプトペルソナの限界が見えたとき | inference/ に vLLM adapter 追加 |
src/erre_sandbox/cli/baseline_metrics.py:4:M8 L6-D1 sinks and emits a JSON document shaped for M9 LoRA comparison. The
src/erre_sandbox/cli/baseline_metrics.py:37:            "stable so M9 LoRA comparison runs can diff against it."
tests/test_memory/test_store.py:475:    """The canonical M9-readiness query returns per-persona turn counts."""
tests/test_memory/test_store.py:599:    """Explicit ``epoch_phase=Q_AND_A`` is persisted (m9-LoRA producer path)."""
src/erre_sandbox/cli/eval_audit.py:4:ME-9 ADR. Reads ``<output>.duckdb`` plus its sidecar
src/erre_sandbox/cli/eval_audit.py:300:            " (m9-eval Phase 3 audit, ME-9 ADR)."
tests/schema_golden/control_envelope.schema.json:847:          "description": "M9-A: the event-boundary tag picked from this tick's observations by priority. Lets the Godot ``ReasoningPanel`` show the trigger 1-liner and the ``BoundaryLayer`` pulse the originating zone for the focused agent. Older M7ζ producers (pre-0.10.0-m7h) deserialise as ``None``; consumers must tolerate the missing case."
tests/schema_golden/control_envelope.schema.json:1148:      "description": "1-line \"起点 event\" tag attached to a :class:`ReasoningTrace` (M9-A).\n\nLets the Godot ``ReasoningPanel`` show \"this trace was a reaction to X\"\nand the ``BoundaryLayer`` pulse the originating zone, without forcing\nconsumers to scan the raw observation stream. Cognition cycle picks one\nwinner per tick by priority (zone_transition > affordance > proximity >\nbiorhythm > erre_mode_shift > temporal > internal > speech > perception);\nsame-tick losers in the spatial set are surfaced as ``secondary_kinds``\nfor a \"+N more\" UI hint.\n\nWire contract: ``ref_id`` is structured (zone_transition→``to_zone``,\naffordance→``prop_id``, proximity→``other_agent_id``, otherwise ``None``).\nDisplay text (e.g. \"Linden-Allee に入った\") is composed *client-side* in\n``godot_project/scripts/i18n/Strings.gd`` so backend stays free of i18n.",
src/erre_sandbox/cli/export_log.py:5:rows as newline-delimited JSON. Consumed by the M9 LoRA training pipeline
src/erre_sandbox/cli/export_log.py:28:"""Formats accepted by ``--format``. Parquet joins this set in the M9 LoRA task."""
src/erre_sandbox/cli/export_log.py:38:            "newline-delimited JSON. Intended for M9 LoRA training-data "
src/erre_sandbox/cli/export_log.py:54:            "deferred to the M9 LoRA task (decisions D4)."
.steering/20260419-cognition-cycle-minimal/decisions.md:65:- **根拠**: persona-erre Skill §ルール 3 の RadixAttention 最適化 (SGLang M7+ で
src/erre_sandbox/world/tick.py:562:        possible (M7γ-out-of-scope) deregistration. Future M9+ removal
src/erre_sandbox/world/tick.py:569:        # If M9 introduces parallel cognition cycles or external mutators
.steering/20260419-cognition-cycle-minimal/design.md:46:- `build_system_prompt(persona, agent) -> str` — RadixAttention 最適化のため
.steering/20260419-cognition-cycle-minimal/design.md:225:- 共通 prefix がペルソナ固有部分より前にある (RadixAttention 最適化確認)
tests/test_integration/test_dialog_golden_baseline_mode.py:195:    # Phase 2: STUDY is now rejected again (natural-dialog rules restored).
.steering/20260419-cognition-cycle-minimal/requirement.md:118:- **LoRA ペルソナ** (M9+)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:1:# Design Final — M9-B LoRA Execution Plan (v3 hybrid: 評価基盤先行 + 並行 Kant spike)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:6:> v1 (Claude 単独 LoRA-first 案) は `design-v1.md` で破棄。
.steering/20260430-m9-b-lora-execution-plan/design-final.md:15:LoRA 適用の go-no-go gate は評価系完成後に判定する **(v2-B 路線維持)** が、
.steering/20260430-m9-b-lora-execution-plan/design-final.md:16:**LoRA 学習・adapter swap・runtime に関する技術リスクは、
.steering/20260430-m9-b-lora-execution-plan/design-final.md:21:1. **SGLang-first**: SGLang は v0.3+ で multi-LoRA / dynamic load/unload / pinned adapters /
.steering/20260430-m9-b-lora-execution-plan/design-final.md:31:5. **bounded parallel Kant spike**: 評価系構築と並行で、Kant 1 persona に対し SGLang LoRA
.steering/20260430-m9-b-lora-execution-plan/design-final.md:37:### A. 量子化戦略 (DB1) → QLoRA NF4 default + AWQ/GPTQ alternatives recorded
.steering/20260430-m9-b-lora-execution-plan/design-final.md:39:- **default**: QLoRA NF4 (bnb double-quantization)、base ~4-5GB、3 persona base 共有 + adapter ~50MB/persona
.steering/20260430-m9-b-lora-execution-plan/design-final.md:41:  - AWQ + LoRA: serving-side quality 維持
.steering/20260430-m9-b-lora-execution-plan/design-final.md:42:  - GPTQ + LoRA: 量子化品質トレードオフ
.steering/20260430-m9-b-lora-execution-plan/design-final.md:43:  - 8-bit LoRA: NF4 で 4-bit が品質面で破綻した時の fallback
.steering/20260430-m9-b-lora-execution-plan/design-final.md:47:### B. Library 選定 (DB2) → defer to M9-C kickoff
.steering/20260430-m9-b-lora-execution-plan/design-final.md:49:- PEFT vs unsloth は M9-eval-system 完了後の M9-C 着手時に spike (rank=8 統一)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:50:- **codex 開示の追加**: SGLang の LoRA training compatibility は別途確認必要
.steering/20260430-m9-b-lora-execution-plan/design-final.md:52:  serving は SGLang LoRA adapter 形式に変換
.steering/20260430-m9-b-lora-execution-plan/design-final.md:57:- LoRA は SGLang `--enable-lora` + `/load_lora_adapter` で実装
.steering/20260430-m9-b-lora-execution-plan/design-final.md:58:- multi-LoRA + overlap loading は documented サポート (SGLang docs cited by codex)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:139:- multi-LoRA: `--max-loras N` + `--max-lora-rank R` 起動オプション
.steering/20260430-m9-b-lora-execution-plan/design-final.md:161:- **Initial run** (first LoRA application): floor 維持で許容 (warmup 認める)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:165:- **3 連続 run** で adoption 条件未達 → 当該 LoRA 設定 (rank / dataset) を破棄、再 spike
.steering/20260430-m9-b-lora-execution-plan/design-final.md:169:#### M9-B 内 deliverable: **specs only** (MEDIUM-1 反映)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:170:M9-B では実装コードを出さず、以下の **spec ドキュメント**のみ deliverable:
.steering/20260430-m9-b-lora-execution-plan/design-final.md:174:- Burrows' Delta reference corpus 整備計画
.steering/20260430-m9-b-lora-execution-plan/design-final.md:181:- Burrows' Delta to thinker reference (per-language、translation 別 baseline)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:211:- M9-eval-system: **100/persona** seed (smoke test 用)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:212:- LoRA 採用判定: **300/persona** acceptance threshold
.steering/20260430-m9-b-lora-execution-plan/design-final.md:226:| **Trigger** | floor (self_rep≤0.10 AND echo≤0.10) AND (coverage 300/persona OR plateau 2-run<5% OR timebox 8 session) | LoRA 適用 fire |
.steering/20260430-m9-b-lora-execution-plan/design-final.md:229:| **Adoption (run ≥2)** | 2-of-3 Tier B sub-metric (Vendi / Big5 ICC / Burrows Delta) が CI で baseline positive 方向 | 採用確定 |
.steering/20260430-m9-b-lora-execution-plan/design-final.md:230:| **Drift (post-LoRA)** | 2-of-3 Tier B sub-metric が CI で baseline negative 方向 | rollback |
.steering/20260430-m9-b-lora-execution-plan/design-final.md:231:| **3 連続 adoption 失敗** | 上記 adoption 条件 3 run 連続未達 | LoRA 設定破棄、再 spike |
.steering/20260430-m9-b-lora-execution-plan/design-final.md:233:| **eval ready** | golden baseline 採取 (3 persona × 5 run × 500 turn) + Tier B (Vendi+ICC) 実装完了 | LoRA adoption 判断 enabled |
.steering/20260430-m9-b-lora-execution-plan/design-final.md:237:### M9-B (本タスク, planning + spec only)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:240:- [ ] M9-eval-system + M9-C-spike + M9-C スコープ確定
.steering/20260430-m9-b-lora-execution-plan/design-final.md:243:### M9-eval-system (新タスク, M9-B 後)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:252:### M9-C-spike (新タスク, **M9-eval-system と並行**) ← codex 第 3 の道
.steering/20260430-m9-b-lora-execution-plan/design-final.md:255:- HF Transformers + PEFT (or unsloth) で Kant LoRA 学習 (rank=8, dataset 既存 dialog_turn)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:257:- M9 → vLLM migration 必要性の measured 判断材料
.steering/20260430-m9-b-lora-execution-plan/design-final.md:258:- **adoption 判断は M9-eval-system 完成後 post-spike re-eval まで保留**
.steering/20260430-m9-b-lora-execution-plan/design-final.md:261:### M9-C-adopt (旧 M9-C, M9-eval-system + M9-C-spike + 評価系 ready 達成後)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:262:- adoption gate (DB9) で LoRA 採用判断
.steering/20260430-m9-b-lora-execution-plan/design-final.md:276:| MEDIUM-1 (M9-B scope) | DB10 → specs only 明文化 | ✅ 反映 |
.steering/20260430-m9-b-lora-execution-plan/design-final.md:277:| MEDIUM-2 (QLoRA "唯一現実解") | DB1 → conservative default + alternatives recorded | ✅ 反映 |
.steering/20260430-m9-b-lora-execution-plan/design-final.md:282:| **Final note (third option)** | M9-C-spike として並行構造化 | ✅ **反映 = 設計の中核転換** |
.steering/20260430-m9-b-lora-execution-plan/design-final.md:287:- LIWC 商用 license の最終可否判定 (M9-eval-system 中)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:288:- Burrows' Delta multi-language strategy 詳細 (M9-eval-system 中)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:289:- Prometheus 2 / G-Eval bias mitigation runbook (M9-eval-system 中)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:290:- 専門家 qualitative review の人 selection (M9-C-adopt 直前)
tests/test_evidence/test_eval_paths_contract.py:15:  the DuckDB store, because the M9 LoRA training pipeline currently
tests/test_evidence/test_eval_paths_contract.py:50:ALLOWED_SENTINEL = "M9_EVAL_SENTINEL_RAW_OK"
tests/test_evidence/test_eval_paths_contract.py:361:    """``erre-sandbox export-log`` is on the M9 training-egress path
tests/test_evidence/test_eval_paths_contract.py:362:    (the LoRA pipeline currently consumes its JSONL). Every row it
tests/test_evidence/test_p3a_decide.py:246:    """Codex HIGH-3 vs HIGH-2 reconciliation: rikyu Burrows missing is a
tests/test_evidence/test_p3a_decide.py:251:    # Drop Burrows from both rikyu cells (mirrors real Mac run output).
tests/test_evidence/test_p3a_decide.py:259:    assert all("BurrowsTokenizationUnsupportedError" in w for w in out["warnings"])
tests/test_evidence/test_p3a_decide.py:319:    # Skip the real Burrows path (no reference corpus available in tmp_path);
.steering/20260430-m9-b-lora-execution-plan/decisions.md:1:# Decisions — M9-B LoRA Execution Plan (10 ADR: DB1-DB10)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:6:本 ADR set は m9-lora-pre-plan の D1-D5 (PR #110 merged) を **継承し、M9 実行 phase の
.steering/20260430-m9-b-lora-execution-plan/decisions.md:12:## DB1 — 量子化戦略: QLoRA NF4 default + alternatives recorded
.steering/20260430-m9-b-lora-execution-plan/decisions.md:14:- **決定**: 学習時 quantization は **QLoRA NF4 (bnb double-quantization)** を default 採用。
.steering/20260430-m9-b-lora-execution-plan/decisions.md:15:  alternatives (AWQ + LoRA / GPTQ + LoRA / 8-bit LoRA) を記録、bounded Kant spike で
.steering/20260430-m9-b-lora-execution-plan/decisions.md:19:  - QLoRA NF4 + double-quantization で 1-2% 性能低下、許容範囲
.steering/20260430-m9-b-lora-execution-plan/decisions.md:22:  - LoRA FP16: VRAM 不足
.steering/20260430-m9-b-lora-execution-plan/decisions.md:23:  - INT8 + LoRA: NF4 の上位互換なし
.steering/20260430-m9-b-lora-execution-plan/decisions.md:25:  - 学習 pipeline は HF Transformers + PEFT/unsloth (M9-C-spike で確定)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:26:  - serving は SGLang LoRA adapter format に変換 (DB3)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:28:  - Kant spike で NF4 quality が許容範囲外 → 8-bit LoRA fallback
.steering/20260430-m9-b-lora-execution-plan/decisions.md:29:  - SGLang AWQ + LoRA 互換が confirmed → AWQ への serving migration 検討
.steering/20260430-m9-b-lora-execution-plan/decisions.md:33:## DB2 — Library 選定: defer to M9-C kickoff
.steering/20260430-m9-b-lora-execution-plan/decisions.md:35:- **決定**: PEFT vs unsloth の選定は **M9-eval-system + M9-C-spike 完了後の M9-C-adopt 着手時**
.steering/20260430-m9-b-lora-execution-plan/decisions.md:36:  に rank=8 統一 spike で決める。M9-B / M9-eval-system では library を確定しない。
.steering/20260430-m9-b-lora-execution-plan/decisions.md:38:  - 学習 library 選定は LoRA を実際に走らせる時点で十分
.steering/20260430-m9-b-lora-execution-plan/decisions.md:44:  - M9-C-spike では一時的に PEFT (公式・ecosystem 厚い) を使用、final 選定は別
.steering/20260430-m9-b-lora-execution-plan/decisions.md:46:  - unsloth の SGLang LoRA adapter format compatibility が問題
.steering/20260430-m9-b-lora-execution-plan/decisions.md:53:- **決定**: **現行 SGLang を維持し、LoRA は SGLang `--enable-lora` + `/load_lora_adapter`
.steering/20260430-m9-b-lora-execution-plan/decisions.md:56:  - codex HIGH-3: SGLang は v0.3+ で multi-LoRA / dynamic load/unload / pinned adapters /
.steering/20260430-m9-b-lora-execution-plan/decisions.md:59:  - 私の v1/v2 認識 (SGLang LoRA 安定性未検証) は stale だった
.steering/20260430-m9-b-lora-execution-plan/decisions.md:65:  - LoRA adapter format は SGLang 互換に変換が必要
.steering/20260430-m9-b-lora-execution-plan/decisions.md:69:  - resonance / FSM が SGLang LoRA 経路で regression
.steering/20260430-m9-b-lora-execution-plan/decisions.md:75:- **決定**: LoRA 適用 trigger を **`floor MUST AND (coverage 300/persona OR plateau OR timebox)`**
.steering/20260430-m9-b-lora-execution-plan/decisions.md:93:  - LoRA 適用が現実的タイミングで fire 可能
.steering/20260430-m9-b-lora-execution-plan/decisions.md:94:  - timebox により M9 milestone delay が bounded
.steering/20260430-m9-b-lora-execution-plan/decisions.md:115:  - Parquet pipeline 実装 (M9-eval-system) の複雑度が中程度増加
.steering/20260430-m9-b-lora-execution-plan/decisions.md:155:  - M9-B / M9-eval-system 期間は N=3 の divergence 漸近線 + 評価系構築が優先
.steering/20260430-m9-b-lora-execution-plan/decisions.md:160:  - v1: M9-B 中 YAML 起草 → 評価系設計を複雑化
.steering/20260430-m9-b-lora-execution-plan/decisions.md:177:  - **runbook 起草は M9-C-spike 完了後**、実測値 (latency / cold start / throughput) 込み
.steering/20260430-m9-b-lora-execution-plan/decisions.md:183:  - v1/v2 vLLM LoRARequest API ラッパ路線 → DB3 で破棄
.steering/20260430-m9-b-lora-execution-plan/decisions.md:185:  - M9-C-spike が runbook の前提
.steering/20260430-m9-b-lora-execution-plan/decisions.md:187:  - SGLang LoRA で adapter swap が機能不全 → vLLM fallback (DB3 re-open)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:204:  - **Initial run** (first LoRA application): floor 維持で許容 (warmup 認可)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:206:  - **3 連続 adoption 失敗**: LoRA 設定 (rank / dataset) を破棄、再 spike
.steering/20260430-m9-b-lora-execution-plan/decisions.md:215:  - bootstrap CI 実装 (M9-eval-system)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:216:  - quorum logic 実装 (M9-C-adopt)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:223:## DB10 — J 評価系 framework: 4-tier + persona-conditional + multi-channel (specs only in M9-B)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:226:  - **M9-B 内 deliverable は specs のみ** (実装コードは出さない、MEDIUM-1 反映)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:228:    - Tier A: per-turn cheap (LIWC/Empath / Burrows Delta / MATTR / semantic novelty / NLI)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:235:    - M9-eval-system: **100/persona seed**
.steering/20260430-m9-b-lora-execution-plan/decisions.md:236:    - LoRA 採用判定: **300/persona acceptance**
.steering/20260430-m9-b-lora-execution-plan/decisions.md:248:  - v2 単独: M9-B 内で Tier A 実装まで含む scope creep
.steering/20260430-m9-b-lora-execution-plan/decisions.md:251:  - M9-eval-system が独立タスクとして大規模化
.steering/20260430-m9-b-lora-execution-plan/decisions.md:261:**bounded, non-authoritative single-persona Kant LoRA spike を SGLang 上で M9-eval-system
.steering/20260430-m9-b-lora-execution-plan/decisions.md:264:- **目的**: 評価系構築中に LoRA 学習・adapter swap・runtime 技術リスクを早期検出
.steering/20260430-m9-b-lora-execution-plan/decisions.md:268:- **deliverable**: SGLang LoRA endpoint 動作確認 + adapter swap latency 実測 +
.steering/20260430-m9-b-lora-execution-plan/decisions.md:270:- **タスク**: 別タスク `M9-C-spike` として切り出し (新規 scaffold)
tests/test_evidence/test_capture_sidecar.py:5:(ME-9 ADR) and Codex 2026-05-06 review reflections:
tests/test_evidence/test_metrics.py:140:    # affinity deferred per decisions D1 — shape must stay stable for M9.
.steering/20260419-cognition-cycle-minimal/design-v1.md:141:| V1-W8 | system prompt が 1 文字列 f-string | 中 | docstring ルール / persona-erre Skill §ルール 3 の fact/legend/speculative 注記を反映できず、RadixAttention prefix 最適化 (共通 prefix → ペルソナ固有) も崩れる |
.steering/20260419-cognition-cycle-minimal/design-v1.md:144:| V1-W11 | 重要度・プロンプト・パースが cycle 内 private に埋もれる | 中 | M4+ で importance を LLM scoring に切り替える・prompt を RadixAttention-aware に改修する時に cycle.py 全体を書き直す羽目になる |
src/erre_sandbox/contracts/eval_paths.py:17:   sentinel-row fixtures (``M9_EVAL_SENTINEL_LEAK_*``) that verify no
src/erre_sandbox/contracts/eval_paths.py:23:   sentinel test scope because the M9 LoRA training pipeline reads
src/erre_sandbox/contracts/eval_paths.py:51:This is the **only** schema the LoRA training pipeline is allowed to read
src/erre_sandbox/contracts/eval_paths.py:92:``mode`` / ``zone`` / ``reasoning`` are reserved for the M9 ingest CLI
src/erre_sandbox/contracts/eval_paths.py:125:SENTINEL_LEAK_PREFIX: Final[str] = "M9_EVAL_SENTINEL_LEAK_"
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:4:> v2-B「評価基盤先行 (LoRA 適用前に J 軸を確立)」をアンチテーゼ仮説として採用。
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:9:**v1 の暗黙前提**: 「LoRA を回せば persona divergence は伸びる」
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:10:**v2 の前提**: 「**LoRA 適用の成否を測れない状態で適用してはならない**」
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:13:「思想家らしさが向上したか」を測る攻めの metric が ζ time でも未定義。LoRA を適用しても
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:17:を測っていない。LoRA 適用の必要性自体が empirically 立証されていない (research-evaluation-metrics.md
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:20:→ **M9-B では LoRA 適用判断を保留し、評価系を先に立てる**。LoRA 関連は技術調査
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:23:これにより M9-B の deliverable は「LoRA 実装 plan」ではなく「**LoRA 適用 / 不適用の go-no-go
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:28:### A. 量子化戦略 → **QLoRA (NF4) を技術選定として採用、適用判断は defer**
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:31:- 技術調査として QLoRA NF4 を採用候補とする (VRAM 16GB 制約下の唯一現実解)
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:35:**根拠 (v1 と同):** G-GEAR 16GB + qwen3:8b + 3 persona swap は QLoRA 必須
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:41:**決定**: PEFT vs unsloth spike は **M9-eval-system 完了後の M9-C kickoff 時** に実施
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:42:**根拠**: 学習 library 選定は LoRA を実際に走らせる時点で十分。先行決定する benefit なし
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:45:### C. Serving 移行判断 → **現行 SGLang/Ollama 維持、vLLM 移行は LoRA 適用判断後**
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:48:- M9-B / M9-eval-system 期間は現行 SGLang/Ollama 維持
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:49:- vLLM 移行は LoRA 適用が決まった時点で実装フェーズの一部として遂行
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:52:**根拠**: SGLang 撤退は大規模変更、LoRA 必要性が empirical に立証されてから判断すべき
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:53:**棄却**: v1 の「vLLM full migration を M9-C 早期に実行」 — premature
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:57:**決定**: 以下 **すべて** が満たされたら LoRA 適用 fire:
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:65:- 条件 4 は v1 の「LoRA を回せば divergence 伸びる」前提を empirical に検証する
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:66:- prompting で伸ばせるなら LoRA は不要、伸ばせないなら LoRA を適用する正当な根拠あり
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:67:- 「天井未確認で LoRA 適用」は実験設計として弱い (LoRA の効果か prompting の余地かを区別不能)
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:116:- M9-B / M9-eval-system 期間は **N=3 の divergence 漸近線** を測ることが優先
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:120:**棄却**: v1 の「M9-B 中 YAML 起草」 — premature commitment
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:122:### H. Adapter swap runbook → **defer until LoRA 適用決定後**
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:124:**決定**: vLLM LoRARequest API ラッパ実装は LoRA 適用決定 (条件 D 4 つすべて満たし) 後
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:131:- **攻め (改善要求)**: LoRA 適用 run で Tier B (Vendi Score + IPIP-NEO Big5 stability)
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:132:  が pre-LoRA baseline より **下回った** 場合は次 run でも auto rollback
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:133:- baseline は J6 で採取する pre-LoRA golden baseline (M9-eval-system 成果物)
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:139:### J. 思想家らしさ評価系 framework → **M9-B 内で Tier A 完全実装 + Tier B 半分実装 + golden baseline 採取**
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:147:4. **persona-fit**: Burrows' Delta to thinker reference + LIWC analytic style
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:151:- Per-turn (Tier A): LIWC-22 (license 確定後) / Burrows' Delta / MATTR / semantic novelty / contradiction NLI
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:157:**必要**。3 persona × 100 reference utterances を canonical corpus から抽出 (Critique / Zarathustra / Nampōroku)。**M9-eval-system タスクの最初の deliverable**
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:160:- LoRA 適用前 (= 現状の prompting + persona YAML のみ) で Tier A-B metric を 5 run 連続採取
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:165:- **採用**: 「floor 維持のみ」(v1) ではなく「pre-LoRA baseline からの **絶対 5% 以上の改善**」を要求
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:166:- 5% は現実的な fine-tuning による divergence 改善幅 (LoRA paper の estimate)
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:170:- M9-B 内: Tier A 全実装 + Tier B のうち Vendi Score + Big Five stability ICC 実装 + golden baseline 採取の準備
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:171:- M9-eval-system: Tier B 完全実装 (Prometheus 2 rubric / FANToM-adapted / FActScore-adapted) + 専門家 review pipeline + golden set 採取
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:173:**v1 との差**: v1 は J 軸を framework のみで内容空白に近かったが、v2 は実装の半分を M9-B に
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:174:取り込み、golden baseline を積極採取する。LoRA 適用判断は J 軸完成後
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:180:| Dataset trigger | dialog_turn≥500 AND div±10% AND floor (self_rep≤0.10, echo≤0.10) AND **prompting plateau (<5% improvement 2 runs)** | LoRA 適用 fire |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:182:| **Baseline drift (攻)** | post-LoRA Tier B < pre-LoRA baseline | auto rollback |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:183:| **改善要求 (J5 攻めの gate)** | post-LoRA Tier B - pre-LoRA baseline ≥ 5% | LoRA 採用 |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:185:| 評価系 ready | golden baseline 採取完了 + Tier B Vendi+ICC 実装完了 | LoRA 適用判断 enabled |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:187:## 実装順序 (M9-B + M9-eval-system + M9-C handoff)
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:189:### M9-B (本タスク内): plan のみ + Tier A 設計
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:191:2. Tier A metric の interface 定義 (実装は M9-eval-system)
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:192:3. Burrows' Delta reference corpus 整備計画 (Critique / Zarathustra / Nampōroku 入手 + 前処理)
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:195:6. M9-eval-system タスクのスコープ確定
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:197:### M9-eval-system (新タスク, M9-B 後): 評価系実装
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:206:### M9-C (LoRA 実装、M9-eval-system 完了後の go-no-go gate 通過後): LoRA 適用
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:209:3. LoRA 学習 loop 実装
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:213:7. LoRA 効果評価 (Tier A-D 全 layer で baseline 比較)
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:219:| 評価系後置の論理矛盾 | 評価系を M9-B / M9-eval-system で先行実装、LoRA 適用前に baseline 採取 |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:220:| AND 強条件の現実性 | 条件 4 (prompting plateau) で **prompting 天井未確認のまま LoRA 適用** を防止 |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:221:| vLLM full migration コスト | LoRA 適用決定後にだけ migration、不要なら現行維持 |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:222:| LIWC license | M9-B 期間中に評価、商用不可なら OSS alternative (Empath / spaCy) に切替 |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:223:| 「LoRA を回せば divergence 伸びる」前提の検証なし | 条件 4 で empirical に検証 (prompting で伸びるなら LoRA 不要) |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:224:| Burrows' Delta 翻訳汚染 | reference corpus 整備計画で multi-language strategy を M9-B に組込 |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:231:1. **時間コスト**: M9-B + M9-eval-system + M9-C の 3 タスク化により LoRA 実装着手が 2-3 倍延伸
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:236:5. **絶対 5% 改善要求の根拠**: LoRA paper estimate は domain-general、philosophical role-play 用途では noise floor が異なる可能性
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:237:6. **N=3 漸近線が不明**: prompting で N=3 がどこまで divergence するか M9-B 時点では未知。
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:239:7. **M9-C を保留することのリスク**: M9 milestone 自体の delay、外部 stakeholder への commit 影響
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:245:| LoRA 適用 timing | M9-C 早期 | 評価系完成後 + prompting plateau 確認後 |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:247:| Serving migration | M9-C で vLLM full migration | LoRA 適用決定後に limited migration |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:248:| Persona N=4 | M9-B で YAML 起草 | M10 へ完全 defer |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:252:| Risk profile | LoRA を打つ前提が empirical に未検証 | 評価系自体の品質と timing リスク |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:253:| 短期 deliverable | M9-C 早期着手 | 評価系の完成 (LoRA は遅延) |
.steering/20260430-m9-b-lora-execution-plan/design-v2.md:254:| 長期妥当性 | LoRA 適用の成否判定が事後不能 | empirical foundation 重視 |
.steering/20260419-cognition-cycle-minimal/design-comparison.md:21:| **system prompt** | 1 f-string に全部 | 共通 prefix + ペルソナ固有 + 動的 tail の 3 段 (RadixAttention 最適化) | **v2** |
.steering/20260419-cognition-cycle-minimal/design-comparison.md:54:  追加機能 (RNG 注入、Reflection trigger、RadixAttention prompt、event_type
src/erre_sandbox/integration/dialog_turn.py:128:action envelope. Placed first so SGLang's RadixAttention (M7+) can share KV
src/erre_sandbox/integration/dialog_turn.py:177:    Order is load-bearing: common prefix first (RadixAttention), persona
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:1:# Codex Independent Review — M9-B LoRA Execution Plan
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:4:- Qualified-sound: v2-B is directionally better than v1, but M9-B should not close until the trigger logic, offensive metric gate, and serving migration assumptions are corrected.
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:7:1. The 4-condition AND trigger is likely to stall LoRA indefinitely; it is stricter than the frozen D1 baseline and makes `dialog_turn ≥500/persona` plus plateau plus divergence stability all binding at once (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:49`).
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:8:2. The plan still implies vLLM migration for M9-C even though current SGLang now has documented multi-LoRA, dynamic load/unload, pinned adapters, and overlap loading support (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:78-80`; [SGLang LoRA docs](https://docs.sglang.io/advanced_features/lora.html)).
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:9:3. The offensive gate uses noisy Tier B metrics and a poorly grounded 5% threshold, so it can reject useful LoRA or accept metric gaming (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:51-52`, `.steering/20260430-m9-b-lora-execution-plan/design-v2.md:164-167`).
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:13:### HIGH (must address before M9-B closure)
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:16:  - Impact: This can make M9-C unreachable. The prior plan already warned that 500/persona was likely impractical from ζ scale (`.steering/20260428-m9-lora-pre-plan/decisions.md:44-50`).
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:20:  - Issue: “post-LoRA Tier B < pre-LoRA baseline” rollback and “+5%” acceptance are underspecified (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:51-52`).
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:25:  - Issue: v1 assumed vLLM was the clear LoRA path because SGLang LoRA was immature (`.steering/20260430-m9-b-lora-execution-plan/design-v1.md:37-46`), but the hybrid timeline still schedules vLLM migration (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:78-80`).
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:27:  - Recommendation: Change C/H to “SGLang-first LoRA runtime spike; vLLM fallback only if SGLang fails measured adapter swap, batching, or latency gates.” SGLang now documents `--enable-lora`, dynamic `/load_lora_adapter`, multiple adapters, `csgmv`, and overlap loading ([docs](https://docs.sglang.io/advanced_features/lora.html)).
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:35:- **MEDIUM-1**: M9-B scope wording is inconsistent
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:36:  - Issue: v2 says M9-B implements Tier A and part of Tier B (`.steering/20260430-m9-b-lora-execution-plan/design-v2.md:139-171`), but the accepted timeline says M9-B is planning/design only (`.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:58-65`).
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:38:  - Recommendation: design-final should explicitly say M9-B produces specs only; M9-eval-system implements.
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:40:- **MEDIUM-2**: QLoRA NF4 is the conservative default, not the only realistic option
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:42:  - Impact: It can blind the plan to serving-side AWQ/GPTQ/INT4 alternatives or 8-bit LoRA fallbacks.
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:43:  - Recommendation: Keep QLoRA NF4 as default for training on 16GB, but record AWQ/GPTQ as serving alternatives and 8-bit LoRA as a quality/perf fallback.
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:48:  - Recommendation: Start with 100/persona for M9-eval-system, but require 300/persona before final LoRA acceptance; reserve 1000/persona for publication-grade work.
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:64:  - Recommendation: Prefer custom persona dictionaries + stylometry for M9; avoid Big-Five claims unless validated.
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:67:1. v2-B is better than v1, but only if timeboxed. v1’s “LoRA ASAP” cannot prove success because J5 is floor-only (`.steering/20260430-m9-b-lora-execution-plan/design-v1.md:111-112`), but v2 overcorrects with unreachable gates.
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:68:2. Delay is rational for research validity, but not if it blocks all LoRA learning. Add a one-persona LoRA spike in parallel with M9-eval-system, explicitly marked non-decisional.
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:69:3. Golden set in M9-eval-system is realistic at 100/persona only if treated as seed data. 300/persona is the real acceptance target.
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:75:9. Multi-language strategy: normalize per language, compare within-language reference corpora, and avoid cross-language Burrows’ Delta. For Kant/Nietzsche, translated English can be a separate baseline, not mixed with German originals.
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:76:10. Risk hedge: produce a short M9-eval-system spec plus a single-persona LoRA spike protocol as the short-term deliverable. This preserves momentum without pretending the offensive gate is ready.
.steering/20260430-m9-b-lora-execution-plan/codex-review.md:79:- The planner is right that “single thinker-likeness score” should be rejected; the survey’s own conclusion says formal metrics are floors/proxies and expert review remains final (`.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md:326-349`). The missed third option is not v1 or v2-B: keep evaluation-first as the decision framework, but run a bounded, non-authoritative Kant LoRA spike on the current SGLang stack to expose adapter/runtime/data problems early while the evaluator is being built.
.steering/20260421-m5-dialog-turn-generator/decisions.md:11:- **背景**: `.steering/20260420-m5-planning/design.md` §Phase 2 / §LLM プロンプト設計方針 では
.steering/20260419-cognition-cycle-minimal/tasklist.md:41:- [ ] `_COMMON_PREFIX` (RadixAttention 用)
tests/test_evidence/test_tier_a/test_burrows_corpus_qc.py:1:"""Reference-corpus QC tests for Burrows Delta (P1b / ME-6).
tests/test_evidence/test_tier_a/test_burrows_corpus_qc.py:13:   other persona's profile under the Burrows L1 distance. Validates
tests/test_evidence/test_tier_a/test_burrows_corpus_qc.py:22:   ``blockers.md`` "Burrows corpus license — corpus expansion".
tests/test_evidence/test_tier_a/test_burrows_corpus_qc.py:52:    BurrowsReference,
tests/test_evidence/test_tier_a/test_burrows_corpus_qc.py:141:        assert isinstance(ref, BurrowsReference)
tests/test_evidence/test_tier_a/test_burrows_corpus_qc.py:290:    """ME-6: rank ordering of personas under Burrows Δ is stable across chunks."""
tests/test_evidence/test_tier_a/test_burrows.py:1:"""Burrows Delta unit tests — pure math against synthetic references.
tests/test_evidence/test_tier_a/test_burrows.py:10:sketch was rejected as not-Burrows. The persona-discriminative test
tests/test_evidence/test_tier_a/test_burrows.py:23:    BurrowsLanguageMismatchError,
tests/test_evidence/test_tier_a/test_burrows.py:24:    BurrowsReference,
tests/test_evidence/test_tier_a/test_burrows.py:25:    BurrowsTokenizationUnsupportedError,
tests/test_evidence/test_tier_a/test_burrows.py:42:def _ref(profile: tuple[float, ...]) -> BurrowsReference:
tests/test_evidence/test_tier_a/test_burrows.py:43:    return BurrowsReference(
tests/test_evidence/test_tier_a/test_burrows.py:85:    zero_std_ref = BurrowsReference(
tests/test_evidence/test_tier_a/test_burrows.py:103:    mixed_ref = BurrowsReference(
tests/test_evidence/test_tier_a/test_burrows.py:140:    with pytest.raises(BurrowsLanguageMismatchError):
tests/test_evidence/test_tier_a/test_burrows.py:145:    ja_ref = BurrowsReference(
tests/test_evidence/test_tier_a/test_burrows.py:152:    with pytest.raises(BurrowsTokenizationUnsupportedError):
tests/test_evidence/test_tier_a/test_burrows.py:157:    ja_ref = BurrowsReference(
tests/test_evidence/test_tier_a/test_burrows.py:179:        BurrowsReference(
tests/test_evidence/test_tier_a/test_burrows.py:190:        BurrowsReference(
src/erre_sandbox/evidence/capture_sidecar.py:4:Adopted in m9-eval-cli-partial-fix (ME-9 ADR) so partial / fatal / complete
.steering/20260421-m5-dialog-turn-generator/design.md:55:- **prompt 3 段構成**: `_common_prefix()` (RadixAttention 共有) → `_persona_block()`
.steering/20260421-m5-dialog-turn-generator/design.md:134:| persona-erre Skill §ルール 3 (RadixAttention 最適化) | system prompt の共通 prefix を先頭に配置 |
.steering/20260426-m7-slice-zeta-live-resonance/decisions.md:12:対称に **ζ で live 体感を集約** することで、M9-LoRA に進む前に「見える差分・
.steering/20260426-m7-slice-zeta-live-resonance/decisions.md:18:動因**。これは memory にない「実体験から来る要請」であり M9 より前置すべき。
.steering/20260426-m7-slice-zeta-live-resonance/decisions.md:52:- `m9-lora-pre-plan` — D1+D2 (成長機構 + LoRA gate + 全体プラン)
.steering/20260426-m7-slice-zeta-live-resonance/decisions.md:57:される。D は M9 の主要 deliverable、A2/A3 はアセット制作タスクで時間
.steering/20260426-m7-slice-zeta-live-resonance/decisions.md:109:identity が画面に出ない退行になる。M9 で persona expansion 線を
.steering/20260426-m7-slice-zeta-live-resonance/decisions.md:142:  1 PR 最速 land、M9-LoRA 着手前にユーザー live 体感を最速で底上げ。
.steering/20260426-m7-slice-zeta-live-resonance/decisions.md:164:| M9-LoRA 着手阻害 | 小 | 小 |
.steering/20260418-persona-kant-yaml/requirement.md:35:- LoRA 設定 (M9)
.steering/20260421-m5-dialog-turn-generator/requirement.md:5:M5 Phase 2 の並列 4 本のうち、LLM 対話生成の**核心タスク**。
.steering/20260421-m5-dialog-turn-generator/requirement.md:14:- `.steering/20260420-m5-planning/design.md` §Phase 2 / §LLM プロンプト設計方針
.steering/20260421-m5-dialog-turn-generator/requirement.md:124:- `.steering/20260420-m5-planning/design.md` §Phase 2 / §LLM プロンプト設計方針 (上位設計)
.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md:5:M9-B の J 軸 (思想家らしさの評価系 framework) の ADR (DB10) を起草する前に、
.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md:206:### Stylometry / Burrows' Delta (arXiv:2507.00838 2025; arXiv:2408.08946 2024)
.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md:208:- **Scoring**: Burrows' Delta = z-scored function-word frequency の Manhattan distance
.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md:282:| **F5 Cognitive trait** | Big Five (IPIP-NEO + LIWC-22 cross-validation) | Stylometry (Burrows' Delta to thinker reference) |
.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md:291:- `Burrows' Delta` to thinker reference corpus (function-word vector、2ms)
.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md:351:これを踏まえ M9-B 設計フェーズで:
src/erre_sandbox/integration/dialog.py:137:        # sqlite for later LoRA-training export. Left None for unit tests
src/erre_sandbox/evidence/metrics.py:231:    and is the exact shape M9 comparison runs must also produce. Keys use
src/erre_sandbox/evidence/metrics.py:283:        # (L6 D1 residual). Retained as a null field so M9 comparison runs
.steering/20260430-m9-b-lora-execution-plan/requirement.md:1:# M9-B LoRA execution plan — 量子化戦略 + 評価系 framework + 10 軸 ADR 確定
.steering/20260430-m9-b-lora-execution-plan/requirement.md:6:M9-A (event-boundary-observability、PR #117-#124) で zone pulse / TRIGGER 観測も
.steering/20260430-m9-b-lora-execution-plan/requirement.md:7:live G-GEAR で 6/6 PASS。M9 の入口として `m9-lora-pre-plan` (PR #110, 2026-04-28
.steering/20260430-m9-b-lora-execution-plan/requirement.md:13:2. **QLoRA / 量子化戦略** — memory `project_m9_pre_plan` で「次回計画で明示」と保留
.steering/20260430-m9-b-lora-execution-plan/requirement.md:17:   未定義。LoRA 適用の go-no-go gate が論理的に成立しない構造的欠落
.steering/20260430-m9-b-lora-execution-plan/requirement.md:19:M9-B はこれら未決事項を確定し、実装着手 (M9-C 以降) の go-no-go gate を作る。
.steering/20260430-m9-b-lora-execution-plan/requirement.md:26:M9-B の plan セッション完了時点で、以下が
.steering/20260430-m9-b-lora-execution-plan/requirement.md:37:5. `tasklist.md`: M9-C / M9-eval-system 着手 tasklist が dependency 順 + 工数
.steering/20260430-m9-b-lora-execution-plan/requirement.md:48:本セッションでは Plan までを完成させ、実装は別タスクで切る (M9-C 以降)。
.steering/20260430-m9-b-lora-execution-plan/requirement.md:54:- **A. 量子化戦略**: QLoRA(4bit) / LoRA(FP16) / INT8+LoRA 選定。G-GEAR 16GB +
.steering/20260430-m9-b-lora-execution-plan/requirement.md:58:  SGLang LoRA 待ち vs ハイブリッド (推論は SGLang 維持 + LoRA は vLLM)
.steering/20260430-m9-b-lora-execution-plan/requirement.md:66:- **G. Persona N=4 拡張時期**: agora 主体 (4 人目候補) を M9-B 中追加 / M10 /
.steering/20260430-m9-b-lora-execution-plan/requirement.md:70:- **I. Baseline drift gate**: LoRA 適用後 self_rep / cross_echo / divergence の
.steering/20260430-m9-b-lora-execution-plan/requirement.md:80:  - **J4**: 最低 baseline 採取方針 (LoRA 適用前現在値を floor 記録)
.steering/20260430-m9-b-lora-execution-plan/requirement.md:82:  - **J6**: 評価系の実装は **M9-eval-system (新タスク)** に切り出す
.steering/20260430-m9-b-lora-execution-plan/requirement.md:87:2. 評価系の実装 (judge prompt / golden set / 自動化 dashboard) → M9-eval-system
.steering/20260430-m9-b-lora-execution-plan/requirement.md:88:3. LoRA 実装本体 (vLLM 起動 / spike 実行 / Parquet 実装 / adapter 学習) → M9-C
.steering/20260430-m9-b-lora-execution-plan/requirement.md:103:- [ ] `tasklist.md` に M9-C / M9-eval-system 着手用 implementation tasklist が
.steering/20260430-m9-b-lora-execution-plan/requirement.md:116:- `docs/architecture.md` (LoRA / serving 統合先)
.steering/20260430-m9-b-lora-execution-plan/requirement.md:119:- memory `project_session_eod_2026_04_30` (M9-B 第 1 候補指定)
.steering/20260430-m9-b-lora-execution-plan/requirement.md:120:- memory `project_m9_pre_plan` (QLoRA/量子化戦略の defer 明示)
.steering/20260430-m9-b-lora-execution-plan/requirement.md:128:  (LoRA 適用前に J 軸を確立)」を v2-B として立てる
.steering/20260430-m9-b-lora-execution-plan/requirement.md:131:- 後続タスク: M9-eval-system (新規) → M9-C (LoRA 実装)
.steering/20260426-m7-slice-epsilon/decisions.md:85:- m9-LoRA で per-persona 並列 cognition cycle を回す予定であり、`_make_relational_sink`
.steering/20260426-m7-slice-epsilon/decisions.md:86:  closure が再エントラント問題に当たる前に service 化が必要 (m9-LoRA より先に
.steering/20260426-m7-slice-epsilon/decisions.md:196:## D5 — Q&A epoch driver は m9-LoRA scope (ε では `EpochPhase.QA_USER` を
.steering/20260426-m7-slice-epsilon/decisions.md:209:- **B**: ε では `epoch_phase` を sink に通すだけ、`Q_AND_A` 産出は m9-LoRA へ。
.steering/20260426-m7-slice-epsilon/decisions.md:229:- m9-LoRA タスクで CLI/UI 経由の researcher prompt を実装する際、
.steering/20260426-m7-slice-epsilon/decisions.md:251:  別 task (m9-LoRA か後続 slice) で扱うべき
.steering/20260426-m7-slice-epsilon/design.md:12:集約消費し、M9-LoRA と M10-11 に綺麗な土台を渡す。
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:1:# Codex Independent Review Request — M9-B LoRA Execution Plan
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:35:1. Is the v2-B antithesis ("evaluation infrastructure first, defer LoRA application")
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:36:   genuinely better than v1 ("implement LoRA ASAP")? Or is the planner overweighting the
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:37:   risk of "applying LoRA without an offensive metric"?
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:46:- The reframing of M9-B's deliverable from "LoRA implementation plan" to "go-no-go
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:47:  judgment basis" — sound? Or does this turn M9-B into a moving target?
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:48:- Is splitting M9 into M9-B (plan) → M9-eval-system (eval infra) → M9-C (LoRA implementation)
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:55:- Is QLoRA NF4 truly the only realistic quantization for 16GB + qwen3:8b + 3 persona swap?
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:56:  Are there alternatives (AWQ + LoRA, GPTQ + LoRA, sharded FP8) that the planner overlooked?
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:57:- The deferral of unsloth-vs-PEFT to M9-C — does this leak premature optimization into M9-B
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:60:  full LoRA support, given that SGLang LoRA reached v0.3+ around 2025? Has SGLang's LoRA
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:74:  on a 4-persona setup before committing to LoRA? Or is N=3 enough?
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:75:- The two-way drift gate (defensive + offensive) — is the offensive gate's "post-LoRA
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:76:  Tier B < pre-LoRA baseline → rollback" a circular dependency on a noisy metric? Should
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:81:  this an empirically grounded number for LoRA on philosophical role-play, or borrowed
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:82:  from domain-general LoRA papers? What number would you propose, with rationale?
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:95:- M9 milestone slips from 1 task (M9-C originally) to 3 tasks (M9-B / M9-eval-system /
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:96:  M9-C). For a solo researcher, is this delay acceptable, or does it risk losing momentum
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:97:  before LoRA is even attempted?
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:98:- Is there a way to **parallel-track** M9-eval-system and a small LoRA spike (e.g., on
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:114:# Codex Independent Review — M9-B LoRA Execution Plan
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:126:### HIGH (must address before M9-B closure)
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md:132:- (as many HIGH as warranted, but be selective — HIGH means M9-B should not close until addressed)
.steering/20260428-godot-viewport-layout/requirement.md:16:side overlay または resizable split として共存。M9-LoRA 着手前に live
src/erre_sandbox/evidence/tier_a/empath_proxy.py:5:"violence", ...). The M9 design uses Empath as **one Tier A axis**
src/erre_sandbox/integration/gateway.py:591:        # ---------- Phase 2: ACTIVE ----------
.steering/20260426-m7-slice-epsilon/observation.md:87:calibration baselining (M9).
.steering/20260426-m7-slice-epsilon/observation.md:102:``Q_AND_A`` rows do not appear until the m9-LoRA Q&A driver lands.
.steering/20260426-m7-slice-epsilon/observation.md:140:  for M9: long autonomous runs with no Q&A interruption push every dyad
.steering/20260426-m7-slice-epsilon/observation.md:141:  to the trust/clash boundary, which collapses belief diversity. The M9
.steering/20260426-m7-slice-epsilon/observation.md:142:  LoRA Q&A driver is expected to inject ``Q_AND_A`` turns that the
.steering/20260426-m7-slice-epsilon/observation.md:159:ε live acceptance is **landed**. Next: M9 (belief-persistence extraction
.steering/20260426-m7-slice-epsilon/observation.md:160:+ Q&A LoRA driver) will exercise the ``Q_AND_A`` filter branch this slice
.steering/20260426-m7-slice-zeta-live-resonance/requirement.md:15:している。M9-LoRA に進む前に、この「見える差分・見える社会・見える成長」を
.steering/20260426-m7-slice-zeta-live-resonance/requirement.md:63:- D2 (04/22) **全体のプランを練る (どれぐらいデータを集めたら LoRA を適用
.steering/20260426-m7-slice-zeta-live-resonance/requirement.md:143:- D2: M9-LoRA gate は MASTER-PLAN §11 に記載があるが、データ閾値・適用
.steering/20260426-m7-slice-zeta-live-resonance/requirement.md:175:変わる比較的低リスクな改善」を集約**し、D の戦略タスクは別文書 (M9 pre-plan)
.steering/20260426-m7-slice-zeta-live-resonance/requirement.md:176:に切り出す。**M9-LoRA に着手する前に live 体験の解像度を底上げする**
.steering/20260426-m7-slice-zeta-live-resonance/requirement.md:191:8. **D は ζ 外** で M9 pre-plan に切り出す
.steering/20260426-m7-slice-zeta-live-resonance/requirement.md:209:- **D1+D2 (成長メカニズム + LoRA gate)** → 新タスク `m9-lora-pre-plan` に
.steering/20260430-m9-b-lora-execution-plan/blockers.md:1:# Blockers & Deferred Items — M9-B LoRA Execution Plan
.steering/20260430-m9-b-lora-execution-plan/blockers.md:5:Codex review LOW finding および設計上 M9-B closure では即決できない判断事項を defer。
.steering/20260430-m9-b-lora-execution-plan/blockers.md:12:- **defer 先**: M9-eval-system (eval test fixture として synthetic 4th persona を含める)
.steering/20260430-m9-b-lora-execution-plan/blockers.md:18:- **defer 先**: M9-eval-system (LIWC license 評価 + alternative decision tree 起草)
.steering/20260430-m9-b-lora-execution-plan/blockers.md:22:## M9-B closure では決められない判断事項
.steering/20260430-m9-b-lora-execution-plan/blockers.md:35:- **option D**: stylometry (Burrows' Delta) のみで persona-fit を測り、Big-Five claim
.steering/20260430-m9-b-lora-execution-plan/blockers.md:40:### Burrows' Delta multi-language strategy 詳細
.steering/20260430-m9-b-lora-execution-plan/blockers.md:45:  - cross-language Burrows' Delta は使わない
.steering/20260430-m9-b-lora-execution-plan/blockers.md:47:- **defer 先**: M9-eval-system (reference corpus 整備時に詳細詰め)
.steering/20260430-m9-b-lora-execution-plan/blockers.md:60:- **defer 先**: M9-eval-system (Tier C 実装時に runbook 起草)
.steering/20260430-m9-b-lora-execution-plan/blockers.md:66:  - M9-C-adopt 直前で 3 persona × 1 専門家を確保
.steering/20260430-m9-b-lora-execution-plan/blockers.md:69:- **defer 先**: M9-C-adopt 直前
.steering/20260430-m9-b-lora-execution-plan/blockers.md:80:- v1「LoRA ASAP」を棄却したことで、短期 deliverable が遅延
.steering/20260430-m9-b-lora-execution-plan/blockers.md:81:- M9 milestone の 2-3 倍延長 (M9-B / M9-eval-system / M9-C-spike / M9-C-adopt)
.steering/20260430-m9-b-lora-execution-plan/blockers.md:83:- **再評価条件**: M9-eval-system が予想以上に長期化 (>3 セッション) → M9-C-spike を
.steering/20260430-m9-b-lora-execution-plan/blockers.md:86:### M9-C-spike の adoption 判断 leakage リスク
.steering/20260430-m9-b-lora-execution-plan/blockers.md:89:- **対策強化条件**: M9-C-spike Kant が「明らかに人間目視で改善」した場合の判断 protocol を起草
.steering/20260430-m9-b-lora-execution-plan/blockers.md:94:- **観測点**: M9-eval-system Tier B 実装完了直後の 2-3 run で plateau curve を観察
.steering/20260430-m9-b-lora-execution-plan/blockers.md:99:- **再評価条件**: M9-eval-system Tier B 実装完了後の golden baseline 採取で discriminative 確認、
.steering/20260430-m9-b-lora-execution-plan/blockers.md:107:| Burrows multi-lang | dialog 言語混在運用 | M9-eval-system reference corpus |
.steering/20260430-m9-b-lora-execution-plan/blockers.md:108:| Judge bias runbook | judge LLM 確定 | M9-eval-system Tier C 実装 |
.steering/20260430-m9-b-lora-execution-plan/blockers.md:109:| 専門家 selection | 評価系完成 | M9-C-adopt 直前 |
.steering/20260430-m9-b-lora-execution-plan/blockers.md:111:| v1 機会コスト再評価 | M9-eval-system >3 セッション | M9-eval-system 中盤 |
.steering/20260430-m9-b-lora-execution-plan/blockers.md:112:| M9-C-spike leakage | spike Kant 目視改善 | M9-C-spike 完了時 |
.steering/20260430-m9-b-lora-execution-plan/blockers.md:113:| N=3 plateau curve | Tier B 実装完了 | M9-eval-system Tier B 完了直後 |
.steering/20260430-m9-b-lora-execution-plan/blockers.md:114:| Tier B sub-metric 3 | golden baseline 採取 | M9-eval-system 終盤 |
.steering/20260426-m7-slice-epsilon/requirement.md:12:land し、M9 (LoRA / persona-distinct silhouette) と M10-11 に綺麗な土台を
.steering/20260426-m7-slice-epsilon/requirement.md:81:- **M2 long-run / M1 N≥3 / agora cold zone calibration** → M9
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:1:# Design v1 — Claude 初回案 (10 軸: LoRA 実装最優先路線)
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:8:m9-lora-pre-plan の 5 ADR (D1-D5) を尊重しつつ、未決事項を **「LoRA を回せば
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:10:評価系 (J 軸) は framework 宣言だけにとどめ、本格実装は M9-eval-system に切り出す。
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:12:短期的 deliverable: M9-C で 3 persona の LoRA adapter を学習・swap 動作させること。
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:16:### A. 量子化戦略 → **QLoRA (NF4) 採用**
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:20:- QLoRA (NF4 + double-quantization) で base を 4-5GB に圧縮、3 persona base 共有 + adapter (~50MB/persona) で 6GB 強で済む
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:21:- 性能低下は LoRA 系 paper で 1-2% 前後、許容範囲
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:24:- LoRA FP16: VRAM 不足 (3 persona swap 不可)
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:25:- INT8 + LoRA: NF4 ほど圧縮されず QLoRA の上位互換性なし
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:30:- QLoRA 最適化済 + 2-5x 高速学習
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:40:- vLLM `--enable-lora` は LoRA hot swap の決定版、`LoRARequest` API で adapter 切替
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:41:- SGLang LoRA は v0.3+ で対応開始、安定性未検証
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:45:- SGLang 維持: LoRA 機能不足
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:46:- ハイブリッド (推論 SGLang + LoRA は vLLM): 二重運用コスト過大
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:50:**決定**: 以下 3 条件が **すべて** 満たされたら LoRA 適用 fire
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:85:### G. Persona N=4 拡張時期 → **M9-B 中に YAML 起草、spike は M9-C**
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:88:- VRAM 実測は M9-C で base 共有 (QLoRA) + 4 adapter 同時 load の VRAM 試算と実測
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:90:### H. Adapter swap runbook → **vLLM LoRARequest 経由**
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:93:- request 時に `LoRARequest(lora_name, lora_int_id, lora_local_path)` で adapter 指定
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:103:### J. 思想家らしさ評価系 framework → **Tier A のみ M9-B 内、Tier B-D は M9-eval-system**
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:105:- M9-B: Tier A (per-turn cheap metrics) 5 個を schema に組み込む宣言
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:107:  - Burrows' Delta to thinker reference corpus
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:111:- M9-eval-system: Tier B-D (Vendi / Prometheus / FANToM / FActScore / 専門家 review) を切り出し
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:118:| Dataset trigger | dialog_turn ≥ 500 AND divergence ±10% AND floor (self_rep ≤ 0.10, cross_echo ≤ 0.10) | LoRA 適用 fire |
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:123:## 実装順序 (M9-C へのハンドオフ)
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:127:3. unsloth で persona 1 (Kant) の QLoRA spike (rank=8、500 turn 起点)
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:134:10. M9-eval-system キックオフ (J 軸 Tier B-D)
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:140:1. **評価系後置の論理矛盾**: J6 で M9-eval-system に切り出すが、攻めの gate がない状態で
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:141:   LoRA 適用したとき「思想家らしさが向上したか」を測れない → 適用の成否判定不能
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:146:5. **「LoRA を回せば divergence は伸びる」前提の検証なし**: prompting + persona YAML 拡張で
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:147:   現在の divergence をどこまで伸ばせるかの天井を測っていない。LoRA 適用の必要性自体が
.steering/20260430-m9-b-lora-execution-plan/design-v1.md:149:6. **Burrows' Delta は philosophical 翻訳に弱い**: Kant 独原典 vs 英訳の差異が persona-fit
.steering/20260420-m5-planning/design.md:141:**System prompt 構造** (RadixAttention 最適化のため persona block を先頭):
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:13:| **A. 量子化** | QLoRA NF4 即採用 + 実装着手 | QLoRA NF4 を技術選定として採用、実装は gate | **v2 採用**: 選定は確定、実装は J 軸完成後 |
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:14:| **B. Library** | unsloth 即採用 | M9-eval-system 完了後 spike | **v2 採用**: premature 決定回避 |
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:15:| **C. Serving** | vLLM full migration | 現行 SGLang 維持、LoRA 決定後 | **v2 採用**: 移行コスト避ける |
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:19:| **G. Persona N=4** | M9-B 中 YAML 起草 | 完全 defer to M10 | **v2 採用**: 評価系優先 |
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:20:| **H. Adapter swap** | M9-C 早期実装 | LoRA 適用決定後 | **v2 採用**: 不要なら捨てる |
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:21:| **I. Drift gate** | 守りのみ (margin 50%) | 双方向 (守 + 攻、攻は post-LoRA Tier B baseline 比較) | **v2 採用**: gate 完結 |
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:22:| **J. 評価系** | framework 宣言のみ | Tier A 完全実装 + Tier B 半実装 + golden baseline | **v2 採用**: M9-B の deliverable を評価系に再定義 |
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:35:- LoRA 適用判断の保留 (A/B/C/G/H すべて)
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:37:- 評価系を M9-B の主 deliverable 化 (J)
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:42:- J5 攻めの gate を「絶対 5% 改善」固定ではなく「初回 LoRA run は floor 維持で許容、
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:43:  2 回目以降の run は 5% 改善要求」に緩和。理由: LoRA は warmup が必要、初回で 5% は厳しい
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:49:| Dataset trigger | dialog_turn≥500 AND div±10% AND floor (self_rep≤0.10, echo≤0.10) AND prompting plateau (<5% improvement 2 連続 run) | LoRA 適用 fire |
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:51:| Drift (攻) | post-LoRA Tier B < pre-LoRA baseline | auto rollback (2 回目以降 run のみ) |
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:52:| 改善要求 (J5 攻めの gate) | 初回 run: floor 維持。2 回目以降: post-LoRA Tier B ≥ pre-LoRA + 5% | LoRA 採用 |
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:54:| 評価系 ready | golden baseline 採取完了 + Tier B (Vendi + Big5 ICC) 実装完了 | LoRA 適用判断 enabled |
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:59:M9-B (本タスク, planning + design only):
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:62:  ├ Burrows' Delta reference corpus 整備計画
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:65:  └ M9-eval-system スコープ確定
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:67:M9-eval-system (新タスク):
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:78:M9-C (LoRA 実装):
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:81:  ├ LoRA 学習 loop
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:91:1. **M9 milestone 全体の delay**: M9-B + M9-eval-system で 2-3 セッション + M9-C で計 3-5 セッション。
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:92:   M9 全体で原計画より 2 倍程度の時間 → 外部 commit / OSF 事前登録への影響評価必要
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:97:5. **絶対 5% 改善要求の根拠**: LoRA paper の domain-general estimate を philosophical role-play
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:100:7. **M9-eval-system の design 自体が大規模化**: J 軸 framework だけだったはずが、評価系実装が
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:101:   独立タスクの規模になる → 当初の M9-B → M9-C 直行よりも複雑度増加
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:109:2. M9 milestone の delay を許容する判断は研究プロジェクトとして合理的か?
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:110:3. golden set 整備を M9-eval-system に含めることの工数見積り (現実的か)
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:116:9. Burrows' Delta の翻訳汚染対応として multi-language strategy は何が現実的か?
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:117:10. M9-B で実装着手しないことの risk hedge (短期 deliverable を別形で出すか?)
src/erre_sandbox/evidence/tier_a/__init__.py:1:"""Tier A psycholinguistic metrics for the M9 evaluation system.
src/erre_sandbox/evidence/tier_a/__init__.py:29:    BurrowsLanguageMismatchError,
src/erre_sandbox/evidence/tier_a/__init__.py:30:    BurrowsReference,
src/erre_sandbox/evidence/tier_a/__init__.py:39:    "BurrowsLanguageMismatchError",
src/erre_sandbox/evidence/tier_a/__init__.py:40:    "BurrowsReference",
src/erre_sandbox/memory/store.py:207:                # tracking ≥1000 turns/persona prerequisite of the M9 LoRA
src/erre_sandbox/memory/store.py:844:        every existing call site (and every M7ε run before the m9-LoRA
src/erre_sandbox/memory/store.py:916:          speaker-scoped for LoRA training-data semantics).
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:1:# Tasklist — M9-B LoRA Execution Plan
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:5:M9-B 自身の closure tasklist + 後続 3 タスク (M9-eval-system / M9-C-spike / M9-C-adopt) の
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:10:## Phase A: M9-B closure (本タスク内)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:28:- [ ] `.steering/[YYYYMMDD]-m9-c-adopt/` scaffold 作成 (M9-eval-system 完了後でも可) [S]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:42:## Phase B: M9-eval-system (新タスク, M9-B 後)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:56:- [ ] Burrows' Delta to thinker reference 実装 (per-language) [M] [DB10、blockers.md]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:57:- [ ] Burrows reference corpus 整備 (Kant Critique / Nietzsche Zarathustra / Rikyu Nampōroku) [L] [DB10]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:94:### M9-eval-system 完了確認
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:101:## Phase C: M9-C-spike (新タスク, **M9-eval-system と並行**)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:104:adoption 判断は M9-eval-system 完成後の post-spike re-eval で行う。
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:106:### SGLang LoRA runtime 動作確認
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:110:- [ ] SGLang LoRA documentation 実装と差分 (codex cited docs) [S] [DB3]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:112:### Kant LoRA 学習 spike
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:115:- [ ] QLoRA NF4 + rank=8 で Kant LoRA 学習 (1 epoch) [M] [DB1]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:123:- [ ] M5 resonance / ERRE FSM が SGLang LoRA 経路で regression していないか確認 [M] [DB3]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:133:### M9-C-spike 完了確認
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:134:- [ ] SGLang LoRA endpoint 全動作確認
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:138:- [ ] M9-C-spike が「明らかに人間目視で改善」した場合の judgment protocol を blockers.md に追記
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:142:## Phase D: M9-C-adopt (M9-eval-system + M9-C-spike + 評価系 ready 達成後)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:145:1. M9-eval-system 完了 (golden baseline + Tier B 実装)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:146:2. M9-C-spike 完了 (SGLang LoRA runtime 動作確認 + Kant spike)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:153:### 3 persona LoRA 展開
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:154:- [ ] Nietzsche LoRA 学習 [M] [DB1/DB2]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:155:- [ ] Rikyu LoRA 学習 [M] [DB1/DB2]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:165:### LoRA 効果評価
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:166:- [ ] pre-LoRA baseline (M9-eval-system 採取済) と post-LoRA を比較 [M]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:170:### M9 milestone 完了確認
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:171:- [ ] 3 persona LoRA adapter が SGLang で運用可能
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:176:### 専門家 review 準備 (M9-C-adopt 直前)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:186:- [ ] M9-B closure 時に MEMORY.md に entry 追加 (project_m9_b_merged.md 仮称) [S]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:191:- [ ] docs/architecture.md に LoRA / serving section 追加 (DB3 SGLang-first) [M] [M9-eval-system 後]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:196:- [ ] M9-B 完了 commit 後、context 使用率確認 [S]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:204:M9-B (本タスク, plan only)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:210:M9-eval-system  ←─並行─→  M9-C-spike (bounded, non-authoritative)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:211:  (Tier 0/A/B/C/D 実装 +              (SGLang LoRA runtime 動作確認 +
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:218:                M9-C-adopt
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:220:              (3 persona LoRA + 双方向 drift gate + adoption 判定)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:230:| M9-B | 0.5 セッション (ほぼ完了) | done |
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:231:| M9-eval-system | 4-6 セッション | ~2 weeks |
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:232:| M9-C-spike | 2-3 セッション (並行) | ~1 week (M9-eval-system overlap) |
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:233:| M9-C-adopt | 3-4 セッション | ~1.5 weeks |
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:234:| **M9 total** | **9-13 セッション** | **~4 weeks** |
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:236:(参考: 当初の M9-C 直行案は 2-3 セッション想定だった。評価基盤先行 + spike 並行で 3-5 倍延伸、
.steering/20260428-godot-viewport-layout/design-comparison.md:111:   「この PR で UX 着地」という位置付け。M9-LoRA 着手前に live UX 底上げを
src/erre_sandbox/evidence/tier_a/burrows.py:1:"""Burrows Delta — z-scored function-word L1 (Manhattan) distance.
src/erre_sandbox/evidence/tier_a/burrows.py:5:not the Burrows Delta family. The canonical R-stylo formulation
src/erre_sandbox/evidence/tier_a/burrows.py:17::class:`BurrowsReference` and compare an incoming test text against it.
src/erre_sandbox/evidence/tier_a/burrows.py:19::class:`BurrowsLanguageMismatchError` (per ``blockers.md`` "Burrows
src/erre_sandbox/evidence/tier_a/burrows.py:50:class BurrowsLanguageMismatchError(ValueError):
src/erre_sandbox/evidence/tier_a/burrows.py:60:class BurrowsTokenizationUnsupportedError(NotImplementedError):
src/erre_sandbox/evidence/tier_a/burrows.py:71:class BurrowsReference:
src/erre_sandbox/evidence/tier_a/burrows.py:72:    """Per-language Burrows reference profile.
src/erre_sandbox/evidence/tier_a/burrows.py:92:    P1a tests, callers build a small synthetic ``BurrowsReference``
src/erre_sandbox/evidence/tier_a/burrows.py:110:                "BurrowsReference vectors must have equal length;"
src/erre_sandbox/evidence/tier_a/burrows.py:127:    Japanese routes through :class:`BurrowsTokenizationUnsupportedError`
src/erre_sandbox/evidence/tier_a/burrows.py:132:        raise BurrowsTokenizationUnsupportedError(
src/erre_sandbox/evidence/tier_a/burrows.py:133:            f"Burrows Delta default tokenizer does not support language"
src/erre_sandbox/evidence/tier_a/burrows.py:145:    reference: BurrowsReference,
src/erre_sandbox/evidence/tier_a/burrows.py:150:    """Burrows Delta = sum of absolute z-score differences (L1 distance).
src/erre_sandbox/evidence/tier_a/burrows.py:157:            ``language`` or :class:`BurrowsLanguageMismatchError` is raised.
src/erre_sandbox/evidence/tier_a/burrows.py:174:        BurrowsLanguageMismatchError: When ``language != reference.language``.
src/erre_sandbox/evidence/tier_a/burrows.py:175:        BurrowsTokenizationUnsupportedError: When ``language`` has no
src/erre_sandbox/evidence/tier_a/burrows.py:179:        raise BurrowsLanguageMismatchError(
src/erre_sandbox/evidence/tier_a/burrows.py:180:            f"Burrows reference language {reference.language!r} does not"
src/erre_sandbox/evidence/tier_a/mattr.py:6:The persona-discriminative claim in the M9 design is that thinkers
src/erre_sandbox/evidence/tier_a/mattr.py:38:            baseline metric and the M9 Tier A metric line up at the
.steering/20260420-m4-cognition-reflection/tasklist.md:10:## Phase 2: branch & 実装
.steering/20260420-m5-planning/design-v1.md:9:再適用する。Phase 1 schema freeze → Phase 2 並列 → Phase 3 integration → Phase 4
.steering/20260420-m4-multi-agent-orchestrator/design.md:277:  4. AgentView projection は M5/M9 でも再利用可能な先行投資
.steering/20260420-m5-planning/design-comparison.md:10:- Phase 1 schema freeze → Phase 2 並列 4 本 → Phase 3 integration → Phase 4 live
.steering/20260420-m5-planning/design-comparison.md:39:| **並列化可能度 (G-GEAR+Mac 2 機)** | **高** (Phase 2 で 4 本並列、LLM + Godot で自然分担) | 低 (Phase 1-3 は直列、Phase 4 で初めて並列化) |
.steering/20260420-m5-planning/design-comparison.md:68:| 並列化可能度 | 案 A 並 (高) — Phase 2 の並列 4 本を維持 |
.steering/20260425-m7-beta-live-acceptance/design.md:44:  └─ baseline.md (#88 + #89、M9 reference として凍結宣言)
.steering/20260425-m7-beta-live-acceptance/design.md:60:├── baseline.md                (新規、#88 + #89 の数値 table、M9 reference)
.steering/20260420-m5-planning/tasklist.md:39:### Phase 2: 並列 4 本 (並列, 1-2 日 each)
.steering/20260425-m7-beta-live-acceptance/observation.md:6:> See `baseline.md` for the M9 reference table from PR #88 + #89.
src/erre_sandbox/cognition/prompting.py:6:  SGLang's RadixAttention (M7+) can reuse its KV cache across personas.
.steering/20260425-m7-beta-live-acceptance/baseline.md:1:# Baseline — M9 LoRA Reference (PR #88 + #89, n=2 frozen)
.steering/20260425-m7-beta-live-acceptance/baseline.md:4:> M9 LoRA-trained runs MUST diff against the values below.
.steering/20260425-m7-beta-live-acceptance/baseline.md:45:## Reference table (frozen for M9 LoRA comparison)
.steering/20260425-m7-beta-live-acceptance/baseline.md:71:self-repetition, no cross-persona echo" at the n=2 / 80 s scale. M9 LoRA
.steering/20260425-m7-beta-live-acceptance/baseline.md:72:runs need to reproduce this and not regress; if LoRA pushes either rate
.steering/20260425-m7-beta-live-acceptance/baseline.md:75:## Anomalies (recorded for M9 / further runs)
.steering/20260425-m7-beta-live-acceptance/baseline.md:99:   M9 LoRA runs at the same length should be allowed slack on this
.steering/20260425-m7-beta-live-acceptance/baseline.md:102:## M9 LoRA comparison protocol
.steering/20260425-m7-beta-live-acceptance/baseline.md:104:When M9 ships an LoRA-tuned variant, the diff procedure is:
.steering/20260425-m7-beta-live-acceptance/baseline.md:107:   with `qwen3:8b + LoRA` swapped in for `qwen3:8b`.
.steering/20260425-m7-beta-live-acceptance/baseline.md:111:4. M9 should match or improve `bias_fired_rate` (≥ 0.5556) and not
.steering/20260425-m7-beta-live-acceptance/baseline.md:114:5. If LoRA changes turn frequency, re-run at the same wall-clock
.steering/20260425-m7-beta-live-acceptance/baseline.md:118:M9 lands. Add an M9 row to a new comparison table instead.
.steering/20260420-m4-planning/requirement.md:52:- M5 以降 (ERRE モード FSM / SGLang / LoRA) の詳細
.steering/20260425-m7-beta-live-acceptance/requirement.md:36:   M9 比較の reference として固定
.steering/20260425-m7-beta-live-acceptance/requirement.md:53:- LoRA / user-dialogue IF の live 検証 (L6 別 steering、M9-M10 スコープ)
.steering/20260425-m7-beta-live-acceptance/requirement.md:95:  並記 — frozen as M9 reference
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:23:特に M9 trunk (eval Phase 2 / LoRA execution) との互換性、operational definition の不足、
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:45:3. Q3 M9-B LoRA 互換: base/individual 二層分離下で LoRA は本当に無傷か
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:46:4. Q4 M9-eval Burrows 互換: multi-individual 同 base で Burrows ratio は意味を保つか
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:80:- Prompt 構造: `_COMMON_PREFIX` (固定、SGLang RadixAttention KV cache 再利用) + persona block + state tail
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:90:### M9 trunk (触らない前提)
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:91:- M9-eval Phase 2 run1 calibration 走行中 (G-GEAR、kant 1 cell × 5 wall = 30h overnight×2)
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:92:- M9-eval Burrows ratio + Big5 ICC = persona の style 識別性測定
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:93:- M9-B LoRA 計画 (PR #127 merged): Kant 1 persona の固定 style を SGLang LoRA で学習
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:94:- 直近 ME-9 trigger 擬陽性 incident で「LLM の自己宣言を rate basis なしに採用する pattern」の
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:99:1. SubjectiveWorldModel schema 追加
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:101:3. LLMPlan に world_model_update を追加
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:103:5. NarrativeSelf を semantic memory から周期生成
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:104:6. DevelopmentState を導入
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:109:1. 「agent 自体に世界モデルを導入する」 → SubjectiveWorldModel は AgentState 第一級 property
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:112:3. 「途中途中から成長していく過程を導入し、完全に人間として構築」 → DevelopmentState lifecycle
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:122:    - LoRA-trained style (M9-B target、不変)
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:126:    - SubjectiveWorldModel (5-axis: env/concept/self/norm/temporal)
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:127:    - NarrativeSelf (chashitsu reflection 拡張で周期蒸留)
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:128:    - DevelopmentState (S1_seed → S2_individuation → S3_consolidation
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:132:    - bounded world_model_update via LLMPlan
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:149:- 提案 7 → M11+ research re-evaluation gate (M9-B LoRA / M9-eval baseline 保護)
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:151:- 8 件の missing items を提示 (cited_memory_ids 必須 / dyadic vs class-wise 直交 /
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:152:  coherence_score / RadixAttention 保護 / decay_half_life / growth_axes 任意 field /
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:153:  定量 acceptance / M9 trunk 隔離 gate)
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:175:### Q3 [M9-B LoRA 互換性 — base layer 専用前提の検証]
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:176:ユーザー vision では LoRA は philosopher_base 専用、individual は prompt+state overlay。
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:177:- この前提は本当に成立するか? individual の personality drift が LoRA 学習データに
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:179:- M9-B LoRA execution timing: M10-A scaffold は M9-B 完了後 vs 並行起動どちら?
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:180:- M9-B PR #127 design-final.md は固定 Kant style 前提。base/individual 分離で execution
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:183:### Q4 [M9-eval Burrows ratio の意味保持]
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:184:ユーザー vision では multi-individual 同 base で Burrows ratio は **base 保持 + 個体ばらつき**
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:186:- これは empirically 機能するか? Burrows は 100-300 高頻度 function word の分布で測るので、
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:188:- 影響しない場合、Burrows は base style しか測れず、個体化は **観測不可** にならないか?
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:190:  M9-eval に追加する必要があるか?
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:193:reimagine が提示した 8 件 (cited_memory_ids 必須 / dyadic vs class-wise 直交 / coherence_score /
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:194:RadixAttention 保護 / decay_half_life / growth_axes 任意 field / 定量 acceptance / M9 trunk
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:199:- **cited_memory_ids 必須**: ユーザー vision で LLMPlan.world_model_update に **どんな**
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:200:  bounded primitive を採用するか (free-form は ME-9 同型 risk、bounded だけだと表現力不足)
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:201:- **RadixAttention KV cache 保護**: 二層分離 (`philosopher_base` block + `Individual` block) で
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:206:M10-A (二層 scaffold) → M10-B (cognition wiring) → M11-A (DevelopmentState transition) →
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:211:- M9-B LoRA execution は M10-A 着手前に終わらせる必要があるか?
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:214:ME-9 trigger 擬陽性 incident は「LLM 出力を literal に解釈して内部状態が動く」 pattern。
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:216:synthesis) は **すべて LLM 経由**。reimagine は cited_memory_ids 必須化で構造的に防いだが、
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:218:申告** で発火するなら、ME-9 と同型 incident が再発するリスクが構造化される。
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:232:- ME-9 incident memory より、**rate basis / 前提の明示性** を必ず check
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:237:- M9-B PR #127 / M9-eval CLI partial-fix PR #140 / Phase 2 run1 prompt PR #141 は merged 済
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:239:- M9 trunk を破壊する提案は HIGH 必須
.steering/20260508-cognition-deepen-7point-proposal/codex-review.md:399:レビュー対象はユーザー提供テキストが主ですが、既存の `.steering` 設計記録と M9 系の前提が食い違っていないかだけローカルで確認します。web prior art はその後に一次論文・公式ページ中心で当てます。
.steering/20260420-m4-multi-agent-orchestrator/design-comparison.md:87:   AgentView は M5 の ERRE mode FSM や M9 の agent telemetry でも再利用でき
src/erre_sandbox/evidence/reference_corpus/_provenance.yaml:1:# Reference corpus provenance — Burrows Delta P1b
src/erre_sandbox/evidence/reference_corpus/_provenance.yaml:5:#   - language: ISO-ish tag (must match BurrowsReference.language)
src/erre_sandbox/evidence/reference_corpus/_provenance.yaml:31:#         translation licensing is confirmed (blockers.md "Burrows corpus
src/erre_sandbox/evidence/reference_corpus/loader.py:1:"""Reference-corpus loader for Burrows Delta.
src/erre_sandbox/evidence/reference_corpus/loader.py:4::class:`erre_sandbox.evidence.tier_a.burrows.BurrowsReference` instances
src/erre_sandbox/evidence/reference_corpus/loader.py:17:   :class:`BurrowsReference` (whose ``__post_init__`` validates equal
src/erre_sandbox/evidence/reference_corpus/loader.py:23:The loader **does not** evaluate or compute Burrows Delta — that lives
src/erre_sandbox/evidence/reference_corpus/loader.py:38:from erre_sandbox.evidence.tier_a.burrows import BurrowsReference
src/erre_sandbox/evidence/reference_corpus/loader.py:83:    :func:`load_reference` rather than lurking until a Burrows Delta
src/erre_sandbox/evidence/reference_corpus/loader.py:255:def load_reference(persona_id: str, language: str) -> BurrowsReference:
src/erre_sandbox/evidence/reference_corpus/loader.py:256:    """Hydrate a frozen :class:`BurrowsReference` for the given pair.
src/erre_sandbox/evidence/reference_corpus/loader.py:264:        A frozen :class:`BurrowsReference` ready to be passed to
src/erre_sandbox/evidence/reference_corpus/loader.py:277:    return BurrowsReference(
src/erre_sandbox/cognition/cycle.py:1117:"""Priority order for :func:`_pick_trigger_event` (M9-A).
src/erre_sandbox/cognition/cycle.py:1127:"""Cap on :attr:`TriggerEventTag.secondary_kinds` (M9-A).
src/erre_sandbox/cognition/cycle.py:1138:    """Resolve ``(zone, ref_id)`` for the winning trigger kind (M9-A helper).
src/erre_sandbox/cognition/cycle.py:1181:    """Pick the winning event boundary tag from this tick's observations (M9-A).
src/erre_sandbox/evidence/reference_corpus/function_words.py:1:"""Closed function-word lists per language for Burrows Delta.
src/erre_sandbox/evidence/reference_corpus/function_words.py:3:Stylometry tradition (Burrows 2002; Eder/Rybicki/Kestemont 2016, R Journal
src/erre_sandbox/evidence/reference_corpus/function_words.py:12:package's German MFW preset; we pin a fixed subset so the M9 reference
src/erre_sandbox/evidence/reference_corpus/function_words.py:23:``BurrowsTokenizationUnsupportedError`` in
src/erre_sandbox/evidence/reference_corpus/function_words.py:27:cannot run a real tokeniser yet; the Burrows code consumes
src/erre_sandbox/evidence/reference_corpus/function_words.py:94:Burrows list. Includes both modern ``dass`` and historical ``daß``
src/erre_sandbox/evidence/reference_corpus/function_words.py:128:"""High-frequency Japanese particles used as the closed Burrows list.
src/erre_sandbox/evidence/reference_corpus/function_words.py:133:inflating the Burrows L1 sum with pure noise. Expansion to a full
src/erre_sandbox/evidence/reference_corpus/function_words.py:136:``blockers.md`` "Burrows corpus license — Rikyu corpus expansion").
.steering/20260420-m4-planning/tasklist.md:118:- LoRA per persona
.steering/20260421-m5-godot-schema-version-bump/requirement.md:17:schema_version 更新だけが M5 Phase 2 で漏れていた**。
src/erre_sandbox/bootstrap.py:502:        # sqlite ``dialog_turns`` for later LoRA-training export. The closure
src/erre_sandbox/bootstrap.py:526:            # the m9-LoRA Q&A driver lands.
.steering/20260428-codex-review-followup/decisions.md:102:- **次アクション**: `tasklist.md` Phase 2 完了。
src/erre_sandbox/evidence/reference_corpus/__init__.py:1:"""Reference corpora for Tier A Burrows Delta (M9 evaluation system).
src/erre_sandbox/evidence/reference_corpus/__init__.py:13:  :class:`erre_sandbox.evidence.tier_a.burrows.BurrowsReference` for a
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:17:   feedback loop 不足**。schema を増やすだけでは LLM の振る舞いは変わらない (cf. ME-9
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:34:ME-9 trigger 擬陽性と同型 — LLM が「学んだ」と宣言すればそれが真になる構造、
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:37:がない)、(iv) M9-eval Burrows ratio が「persona ごとの語彙分布」を測定中なのに
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:105:    cited_memory_ids: list[str]  # 必須 ≥ 1; 直近 N tick の retrieved_memories から選ぶ
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:115:`cited_memory_ids` が直近の `retrieved_memories` (ReasoningTrace 既存 field) と
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:170:**"the persona stays; the depth grows"** の範囲制約。M9-B LoRA が学習する style 軸
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:171:(固定) と直交。M9-eval Burrows ratio は YAML root level で測るため
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:182:| 5. plan 適用 | `stance_shift_hint.cited_memory_ids` | StanceVector (条件満足時のみ) |
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:187:step 5 の "条件満足時" = `cited_memory_ids` が ≥ 1 個の retrieved_memories と一致 +
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:203:**絶対に `_COMMON_PREFIX` を変えない**。SGLang RadixAttention の KV cache 再利用が
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:217:  RadixAttention prefix は引き続き再利用できる。
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:229:- **新 free-form フィールドは追加しない** (ME-9 incident 教訓)。
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:231:### 3.7 phasing (M9 完了後の milestone 配置)
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:234:M9 trunk (UNTOUCHED): run1 calibration → eval Phase 2 → M9-B LoRA execution
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:235:         → M9-eval Phase 2 vs LoRA 比較 baseline 確立                       ← 触らない
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:242:                 強くなることを統計的に確認 (Burrows ratio に対して直交シグナル)
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:248:   - apply_stance_shift_hint() pure function (cited_memory_ids verify 含む)
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:264:   - 後方互換、 M9-B LoRA / M9-eval Burrows baseline は影響なし
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:268:   - M9-eval baseline と M10/M11 の介入後を比較
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:275:**前段が後段なしで独立に成立** する形。ME-9 incident の "LLM の自己宣言だけで trigger
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:286:| 1 | SubjectiveWorldModel schema 追加 | **StanceVector** (5-axis) | 構造は独立に再発見。axis 集合が一部一致 (env / concept / self / norm)。ただし本案は dyadic を含めず `interlocutor_class` で anonymize する制約を強く打ち出す |
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:287:| 2 | prompt に subjective beliefs を注入 | **user prompt 側に Held stances section** | 完全一致。本案は **system prompt を絶対汚さない** 制約を明示 (RadixAttention KV cache 保護) |
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:288:| 3 | LLMPlan に world_model_update を追加 | **StanceShiftHint (bounded primitive)** | 一致するが本案は **cited_memory_ids 必須** + **direction を 3 値 enum** に絞る (free-form 不可)。提案 3 を "as-is で採用すべきでない" と独立に判定したのと同型 |
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:290:| 5 | NarrativeSelf を semantic memory から周期生成 | **NarrativeArc** (chashitsu reflection 延長) | 構造一致。本案は free-form prose ではなく **structured ArcSegment trajectory + coherence_score** で metric-able にする違いあり |
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:299:| 6 | DevelopmentState を導入 | **却下 → ShuhariStage transition machinery 拡張に置換** | 既存 `shuhari_stage` (shu/ha/ri) と axis 重複。Western stage model 並立は ERRE thesis (守破離 = 仏教/茶道由来) と incoherent。本案は新 schema を作らず ShuhariStage を rich 化することで同じ機能を達成 |
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:300:| 7 | 偉人 persona を philosopher_seed にリファクタ | **却下 → growth_axes 任意 field 追加に置換** | (a) M9-B LoRA は固定 Kant style を学習する設計、seed 化で学習対象が消失。(b) M9-eval Burrows は固定 style 識別 metric、再 calibration 必要で M9 まで blocked。(c) "philosopher_seed" naming は ペルソナ抽出 pipeline (一次史料からの認知習慣抽出) の成果物の意味づけを変える。本案は persona を維持したまま `growth_axes` 任意 field で "深まる方向" のみ宣言 |
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:309:| **RadixAttention KV cache 保護制約** (system prompt 不変 / user prompt 側のみ拡張) | 提案 2 では cache 戦略は示されない | 本案では明示制約として書く (M9-B SGLang 計画と直結) |
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:312:| **acceptance 基準の定量化** (各 milestone で metric を要求) | 提案 1-7 は schema 設計のみで eval を伴わない | M10-A: Burrows 直交シグナル, M10-B: adoption rate, M10-C: coherence_score, M11-A: 遷移発火 |
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:313:| **M9 trunk 隔離の明示宣言** | 提案では M9-B / M9-eval との関係が議論されていない | 本案は M9 完全終了 (LoRA 学習 + eval 比較) 後にのみ M10 を着手する gate を設置 |
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:318:7 は M9 trunk を破壊するため、M11+ research re-evaluation の gate に置く。
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:320:coherence metric / cache 保護) を加える** ことで、ME-9 trigger 擬陽性 incident と
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:323:## 5. M9 trunk (eval / LoRA) との互換性
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:325:**M10 着手は M9 完全終了後** (run1 calibration → Phase 2 → LoRA → 比較) を gate にする。
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:328:1. M9-B LoRA は固定 Kant style を学習。本案は persona を維持するので LoRA の学習対象は
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:329:   不変 — `growth_axes` は YAML root の任意拡張、Burrows ratio は既存 root field で測る。
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:330:2. M9-eval Phase 2 の baseline (persona 識別性) が確立してから StanceVector を入れる
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:333:3. SGLang RadixAttention の KV cache は system prompt 共有を前提にしているので、本案の
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:344:**判断**: StanceShiftHint を `cited_memory_ids: list[str]` 必須 + Python 側 verify 経由の
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:347:**根拠**: ME-9 trigger 擬陽性 incident (2026-05-07) は「rate 閾値を文字通り受けて停止
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:357:重心を移すと前者の研究価値 (一次史料からの認知習慣抽出) が損なわれる。M9-B LoRA は
.steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md:358:固定 style を前提とし、M9-eval Burrows は固定 style 識別を測る。両者が成立しているうちに
src/erre_sandbox/evidence/reference_corpus/_build_vectors.py:88:    ``BurrowsTokenizationUnsupportedError``).
src/erre_sandbox/evidence/reference_corpus/_build_vectors.py:123:    # consumer (BurrowsReference) requires positional alignment.
.steering/20260426-m7-slice-epsilon/run-guide-epsilon.md:9:> one fresh `scaling_metrics.json` reference for M9 calibration.
.steering/20260426-m7-slice-epsilon/run-guide-epsilon.md:150:  the m9-LoRA Q&A driver does)
.steering/20260426-m7-slice-epsilon/run-guide-epsilon.md:172:No ``Q_AND_A`` rows until the m9-LoRA Q&A driver lands.
.steering/20260508-cognition-deepen-7point-proposal/design.md:19:これは単なる schema 拡張提案ではない。**M9 trunk (eval + LoRA)** が前者の解釈に depend
.steering/20260508-cognition-deepen-7point-proposal/design.md:20:しているため、提案 7 (philosopher_seed) は M9 を破壊しうる。提案 1, 4, 5 は前者と衝突せず
.steering/20260508-cognition-deepen-7point-proposal/design.md:27:| 1 SubjectiveWorldModel | `SemanticMemoryRecord.belief_kind` (dyadic, 5 cat) | 直交 (belief_kind は dyad only、提案は env/concept/self/norm 含む) | 低: gap fill |
.steering/20260508-cognition-deepen-7point-proposal/design.md:28:| 2 prompt injection | `_COMMON_PREFIX` + `_format_persona_block` + RadixAttention KV 再利用 | injection 位置で cache 戦略影響 | 中: user prompt 側なら安全 |
.steering/20260508-cognition-deepen-7point-proposal/design.md:29:| 3 LLMPlan world_model_update | `LLMPlan(extra="forbid", frozen=True)` cognition/parse.py:46 | schema versioning + parse path | **高: role-play 増幅 risk** |
.steering/20260508-cognition-deepen-7point-proposal/design.md:31:| 5 NarrativeSelf 周期生成 | M4 chashitsu reflection + semantic promote | 同 trigger に乗るか別 trigger か | 中 |
.steering/20260508-cognition-deepen-7point-proposal/design.md:32:| 6 DevelopmentState | `AgentState.Cognitive.shuhari_stage` (shu/ha/ri) | **直接重複** | 高: 統合 / 棄却の二択 |
.steering/20260508-cognition-deepen-7point-proposal/design.md:33:| 7 philosopher_seed | personas/*.yaml 0.10.0-m7h, M9-B LoRA Kant target, M9-eval Burrows | **M9 trunk 全体の前提** | **最高: M9 まで blocked** |
.steering/20260508-cognition-deepen-7point-proposal/design.md:37:### 2.1 [ADOPT] 提案 1: SubjectiveWorldModel schema 追加
.steering/20260508-cognition-deepen-7point-proposal/design.md:51:**phasing**: M10 (M9-eval / M9-B 完了後)。M10-A タスクとして scaffold。
.steering/20260508-cognition-deepen-7point-proposal/design.md:55:**判定根拠**: SubjectiveWorldModel が agent 内部に存在しても、prompt に提示されなければ
.steering/20260508-cognition-deepen-7point-proposal/design.md:59:- **`_COMMON_PREFIX` を絶対に汚さない** (RadixAttention KV cache 再利用が壊れる)
.steering/20260508-cognition-deepen-7point-proposal/design.md:66:### 2.3 [MODIFY] 提案 3: LLMPlan に world_model_update 追加
.steering/20260508-cognition-deepen-7point-proposal/design.md:71:   採用するのは、最近 ME-9 trigger 擬陽性で empirical に痛い目を見た構造と同型
.steering/20260508-cognition-deepen-7point-proposal/design.md:82:- 新 belief 生成は **NarrativeSelf 周期生成 (提案 5) または既存の Python-side promotion
.steering/20260508-cognition-deepen-7point-proposal/design.md:94:- 入力: 現在の SubjectiveWorldModel + LLMPlan の bounded primitives + 直近 N 観察 +
.steering/20260508-cognition-deepen-7point-proposal/design.md:96:- 出力: `SubjectiveWorldModel | None` (変化なしなら None)
.steering/20260508-cognition-deepen-7point-proposal/design.md:101:### 2.5 [ADOPT, defer] 提案 5: NarrativeSelf 周期生成
.steering/20260508-cognition-deepen-7point-proposal/design.md:109:- 入力: semantic memory top-K (importance order) + SubjectiveWorldModel + 直近の
.steering/20260508-cognition-deepen-7point-proposal/design.md:111:- 出力: `NarrativeSelf` record (free-form prose 200-400 char, 蒸留 LLM call)
.steering/20260508-cognition-deepen-7point-proposal/design.md:117:### 2.6 [REJECT standalone, MODIFY to extension] 提案 6: DevelopmentState
.steering/20260508-cognition-deepen-7point-proposal/design.md:129:  - 遷移 trigger: SubjectiveWorldModel + NarrativeSelf の coherence 閾値 (M11+)
.steering/20260508-cognition-deepen-7point-proposal/design.md:137:1. **M9-B LoRA は固定 Kant style を学習する設計** (`.steering/20260430-m9-b-.../design-final.md` L17)。 seed→trajectory にすると LoRA 学習対象が消える。
.steering/20260508-cognition-deepen-7point-proposal/design.md:138:2. **M9-eval Burrows ratio は固定 style 識別に depend** — 提案 7 採用は Burrows
.steering/20260508-cognition-deepen-7point-proposal/design.md:141:   meaningful に消費する大変更を M9 期間中に始めるのは process 的にも危険。
.steering/20260508-cognition-deepen-7point-proposal/design.md:146:- M9-eval Phase 2 完了 → ベースラインの persona 識別性が確立される
.steering/20260508-cognition-deepen-7point-proposal/design.md:151:**phasing**: **M11+ research re-evaluation** にゲート。M9-eval Phase 2 + M9-B post-LoRA
.steering/20260508-cognition-deepen-7point-proposal/design.md:161:M9 trunk (UNTOUCHED, 続行):
.steering/20260508-cognition-deepen-7point-proposal/design.md:163:  - M9-eval Phase 2 完了
.steering/20260508-cognition-deepen-7point-proposal/design.md:164:  - M9-B LoRA execution (Kant 1 persona, fixed style)
.steering/20260508-cognition-deepen-7point-proposal/design.md:165:  - M9-eval Phase 2 → LoRA 比較 baseline 確立
.steering/20260508-cognition-deepen-7point-proposal/design.md:166:  ↓ M9 完了
.steering/20260508-cognition-deepen-7point-proposal/design.md:169:  - 提案 1: SubjectiveWorldModel schema (env/concept/self/norm/temporal 5 axis)
.steering/20260508-cognition-deepen-7point-proposal/design.md:179:M11-A: NarrativeSelf
.steering/20260508-cognition-deepen-7point-proposal/design.md:188:  - 提案 7: M9 results で persona 識別が「強すぎ」と empirical に判明した場合のみ
.steering/20260508-cognition-deepen-7point-proposal/design.md:199:- ❓ 提案 7 を "M11+ defer" にしたが、これは「M9-eval が成功する」前提。もし
.steering/20260508-cognition-deepen-7point-proposal/design.md:200:  M9-eval Phase 2 で persona 識別性が低い (= LLM が同質な発話しかしない) と判明したら、
.steering/20260508-cognition-deepen-7point-proposal/design.md:201:  提案 7 が **M9 内で必要** な可能性すら出る。Codex review で empirical risk を点検。
.steering/20260508-cognition-deepen-7point-proposal/design.md:203:- ❓ 提案 5 (NarrativeSelf) を M11 にしたが、これを **先に**入れて agent の自己整合性を
.steering/20260508-cognition-deepen-7point-proposal/design.md:204:  上げてから M9-B LoRA 学習データを取る方が良いという順序もある。phasing 再検討要。
.steering/20260508-cognition-deepen-7point-proposal/design.md:212:1. SubjectiveWorldModel と belief_kind の axis 直交性は本当に成立するか。
.steering/20260508-cognition-deepen-7point-proposal/design.md:213:2. world_model_update on LLMPlan は bounded primitive で十分機能するか、それとも
.steering/20260508-cognition-deepen-7point-proposal/design.md:215:3. NarrativeSelf を M9-B より **前** に入れる順序の妥当性。LoRA 学習データの質に効くか。
.steering/20260508-cognition-deepen-7point-proposal/design.md:216:4. philosopher_seed は M9 trunk が成功した場合 even unnecessary か (= 固定ペルソナで
.steering/20260418-model-pull-g-gear/requirement.md:36:- LoRA / vLLM の導入 → M9
.steering/20260428-codex-review-followup/codex_review.md:556:### Finding D9: [P3] M9 pre-plan is strong, but its tasklist and blocker file are stale
.steering/20260428-codex-review-followup/codex_review.md:566:The M9 pre-plan itself is one of the better steering records: it is clearly marked as pre-plan, cites data sources, and structures five ADRs with v1/v2/hybrid choices. However, its tasklist still shows commit/PR items open even though the recent git log indicates the M9 pre-plan commit/PR has landed. `blockers.md` also remains a raw template.
.steering/20260428-codex-review-followup/codex_review.md:580:- M9 pre-plan steering status matches repository history.
.steering/20260418-schemas-freeze/decisions.md:49:- **見直しタイミング**: M9 で LoRA per persona 導入時、persona_id が
.steering/20260418-schemas-freeze/decisions.md:50:  LoRA adapter 名と 1-1 対応する必要が出たら命名規約を見直す
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:9:G-GEAR で M9-eval Phase 2 run1 calibration (kant 1 cell × 5 wall = 30h overnight×2) を
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:12:認知エンティティ」への思想転換** を含むため、M9-B LoRA / M9-eval / 既存の belief 系統 /
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:20:1. SubjectiveWorldModel schema 追加
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:22:3. LLMPlan に world_model_update を追加
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:24:5. NarrativeSelf を semantic memory から周期生成
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:25:6. DevelopmentState を導入
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:37:   - `philosopher_base` (継承、immutable、cognitive_habits + sampling、M9-B LoRA target)
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:53:    - LoRA-trained 文体 (M9-B target)
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:56:    - SubjectiveWorldModel (= 1, AgentState 第一級 property)
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:58:    - bounded world_model_update (= 3 修正版)
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:60:    - NarrativeSelf 周期蒸留 (= 5)
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:61:    - DevelopmentState lifecycle (= 6, individual 側にあるので shuhari と直交)
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:65:### M9 trunk への影響 (再評価)
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:67:二層分離なら M9 trunk は **無傷** で進められる:
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:68:- M9-B LoRA は `philosopher_base` の Kant 文体を学習 (現設計不変)
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:69:- M9-eval Burrows ratio は **base 保持 + 個体ばらつき** の分解測定ツール化
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:71:- Phase 2 baseline は invalidate されず、個体化計測の reference point になる
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:82:- LoRA adapter は **base layer 専用** か、それとも個体差も学習対象か?
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:83:  (後者なら M9-B 設計に影響)
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:99:- 各判定に **既存コードへの影響** + **M9-B LoRA / M9-eval への影響** + **代替案有無**
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:101:- ADOPT/MODIFY と判定したものについて、phasing (M9 内 / M10 / M11+) を割当てる
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:102:- 全体として M9 完了までブロックしない実行順序を提示する
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:109:| 1 SubjectiveWorldModel | `SemanticMemoryRecord.belief_kind` (M7δ) | 同一 axis 重複の可能性、統合設計必須 |
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:110:| 2 prompt injection | `_COMMON_PREFIX` (RadixAttention KV cache 前提) | prompt 構造変更が SGLang cache 戦略に波及 |
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:111:| 3 LLMPlan world_model_update | `cognition/parse.py:46` `LLMPlan(extra="forbid", frozen=True)` | schema versioning 必須、parse path への影響 |
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:113:| 5 NarrativeSelf 周期生成 | M4 chashitsu reflection / semantic memory promote | reflection trigger と timing 衝突の可能性 |
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:114:| 6 DevelopmentState | `AgentState.Cognitive.shuhari_stage` (shu/ha/ri) | 直接重複、関係を明示しないと 2 系統並立 |
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:115:| 7 philosopher_seed | `personas/*.yaml` schema_version 0.10.0-m7h、 M9-B LoRA Kant target、M9-eval Burrows 固定 style 前提 | M9 trunk 全体の前提を変える、最大リスク |
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:119:- G-GEAR の run1 calibration 走行 (別軸、ME-9 ADR で running)
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:120:- M9-eval CLI 改修 (PR #140 で完了)
.steering/20260508-cognition-deepen-7point-proposal/requirement.md:121:- M9-B LoRA execution 着手 (PR #127 計画は確定済、ただし提案 7 採用なら見直し)
.steering/20260425-m7-beta-live-acceptance/tasklist.md:109:- [x] M9 LoRA 比較 run 時に diff する reference として「凍結」宣言
.steering/20260425-m7-beta-live-acceptance/tasklist.md:118:      「baseline 固定済 (n=2)、M9 比較準備完了」として追記
.steering/20260424-m7-differentiation-observability/design-final.md:72:- `requirement.md`: 3 軸（LoRA / agent scaling / user-dialog IF）。**H2 が提案した運用予算節は L6 内に入れない** — CLAUDE.md と architecture-rules Skill に既記載のため DRY
.steering/20260428-codex-review-followup/requirement.md:43:- LoRA / M9 関連 (前 PR #110 で確定済、本 task 無関係)
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:10:特に M9 trunk (eval Phase 2 / LoRA execution) との互換性、operational definition の不足、
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:32:3. Q3 M9-B LoRA 互換: base/individual 二層分離下で LoRA は本当に無傷か
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:33:4. Q4 M9-eval Burrows 互換: multi-individual 同 base で Burrows ratio は意味を保つか
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:67:- Prompt 構造: `_COMMON_PREFIX` (固定、SGLang RadixAttention KV cache 再利用) + persona block + state tail
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:77:### M9 trunk (触らない前提)
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:78:- M9-eval Phase 2 run1 calibration 走行中 (G-GEAR、kant 1 cell × 5 wall = 30h overnight×2)
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:79:- M9-eval Burrows ratio + Big5 ICC = persona の style 識別性測定
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:80:- M9-B LoRA 計画 (PR #127 merged): Kant 1 persona の固定 style を SGLang LoRA で学習
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:81:- 直近 ME-9 trigger 擬陽性 incident で「LLM の自己宣言を rate basis なしに採用する pattern」の
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:86:1. SubjectiveWorldModel schema 追加
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:88:3. LLMPlan に world_model_update を追加
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:90:5. NarrativeSelf を semantic memory から周期生成
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:91:6. DevelopmentState を導入
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:96:1. 「agent 自体に世界モデルを導入する」 → SubjectiveWorldModel は AgentState 第一級 property
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:99:3. 「途中途中から成長していく過程を導入し、完全に人間として構築」 → DevelopmentState lifecycle
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:109:    - LoRA-trained style (M9-B target、不変)
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:113:    - SubjectiveWorldModel (5-axis: env/concept/self/norm/temporal)
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:114:    - NarrativeSelf (chashitsu reflection 拡張で周期蒸留)
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:115:    - DevelopmentState (S1_seed → S2_individuation → S3_consolidation
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:119:    - bounded world_model_update via LLMPlan
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:136:- 提案 7 → M11+ research re-evaluation gate (M9-B LoRA / M9-eval baseline 保護)
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:138:- 8 件の missing items を提示 (cited_memory_ids 必須 / dyadic vs class-wise 直交 /
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:139:  coherence_score / RadixAttention 保護 / decay_half_life / growth_axes 任意 field /
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:140:  定量 acceptance / M9 trunk 隔離 gate)
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:162:### Q3 [M9-B LoRA 互換性 — base layer 専用前提の検証]
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:163:ユーザー vision では LoRA は philosopher_base 専用、individual は prompt+state overlay。
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:164:- この前提は本当に成立するか? individual の personality drift が LoRA 学習データに
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:166:- M9-B LoRA execution timing: M10-A scaffold は M9-B 完了後 vs 並行起動どちら?
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:167:- M9-B PR #127 design-final.md は固定 Kant style 前提。base/individual 分離で execution
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:170:### Q4 [M9-eval Burrows ratio の意味保持]
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:171:ユーザー vision では multi-individual 同 base で Burrows ratio は **base 保持 + 個体ばらつき**
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:173:- これは empirically 機能するか? Burrows は 100-300 高頻度 function word の分布で測るので、
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:175:- 影響しない場合、Burrows は base style しか測れず、個体化は **観測不可** にならないか?
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:177:  M9-eval に追加する必要があるか?
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:180:reimagine が提示した 8 件 (cited_memory_ids 必須 / dyadic vs class-wise 直交 / coherence_score /
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:181:RadixAttention 保護 / decay_half_life / growth_axes 任意 field / 定量 acceptance / M9 trunk
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:186:- **cited_memory_ids 必須**: ユーザー vision で LLMPlan.world_model_update に **どんな**
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:187:  bounded primitive を採用するか (free-form は ME-9 同型 risk、bounded だけだと表現力不足)
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:188:- **RadixAttention KV cache 保護**: 二層分離 (`philosopher_base` block + `Individual` block) で
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:193:M10-A (二層 scaffold) → M10-B (cognition wiring) → M11-A (DevelopmentState transition) →
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:198:- M9-B LoRA execution は M10-A 着手前に終わらせる必要があるか?
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:201:ME-9 trigger 擬陽性 incident は「LLM 出力を literal に解釈して内部状態が動く」 pattern。
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:203:synthesis) は **すべて LLM 経由**。reimagine は cited_memory_ids 必須化で構造的に防いだが、
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:205:申告** で発火するなら、ME-9 と同型 incident が再発するリスクが構造化される。
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:219:- ME-9 incident memory より、**rate basis / 前提の明示性** を必ず check
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:224:- M9-B PR #127 / M9-eval CLI partial-fix PR #140 / Phase 2 run1 prompt PR #141 は merged 済
.steering/20260508-cognition-deepen-7point-proposal/codex-review-prompt.md:226:- M9 trunk を破壊する提案は HIGH 必須
.steering/20260428-codex-review-followup/tasklist.md:19:### Phase 2: F6 (frame byte limit)
.steering/20260424-m7-differentiation-observability/decisions.md:13:## D2. L6 (LoRA / scaling / user-dialogue IF) は別 steering で並行起票
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:28:  ├── lora_adapter_id: str | None              (M9-B LoRA target)
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:35:  ├── world_model: SubjectiveWorldModel         (= 提案 1、AgentState property、5 axis)
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:36:  ├── narrative_self: NarrativeSelf | None      (= 提案 5、周期蒸留 result)
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:37:  ├── development_state: DevelopmentState       (= 提案 6、lifecycle 段階)
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:48:- `world_model`: 完全に individual 側 (base は "無" を default で提供)
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:49:- LoRA adapter: base layer のみに適用 (= 個体差は prompt/state overlay)
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:59:| `SemanticMemoryRecord.belief_kind` | individual の dyadic belief (subjective beliefs に統合) | 小: 既存維持、SubjectiveWorldModel と axis 直交 |
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:61:| `LLMPlan` | individual の出力 (個体の意思決定) | 中: world_model_update 追加 (bounded primitive) |
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:68:| 1 SubjectiveWorldModel | ADOPT in memory layer | **ADOPT as `Individual.world_model` property** (AgentState 第一級) | "agent 自体に" 明確化を反映、配置変更 |
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:70:| 3 LLMPlan world_model_update | MODIFY to bounded primitive | **ADOPT as bounded primitive** | 同じ判定 (free-form は role-play 増幅、bounded primitive 必須) |
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:72:| 5 NarrativeSelf | M11-A defer | **M10-B (M9-B 後の最初の milestone)** | 個体連続性に必須、後送不可 |
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:73:| 6 DevelopmentState | REJECT standalone | **ADOPT as `Individual.development_state`** | shuhari_stage は base 側技能習得、DevelopmentState は individual 側 lifecycle、**直交** |
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:74:| 7 philosopher_seed | DEFER M11+ | **ADOPT as conceptual two-layer refactor** | base = LoRA target (M9-B 不変)、individual = overlay。M9 trunk 破壊しない |
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:86:  S1_seed:       初期化直後、base habit 強い、world_model 空
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:87:  S2_individuation: 個体差発現、world_model 5-15 entries、narrative 未生成
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:88:  S3_consolidation: 信念の安定、world_model 15-50 entries、narrative_self 初回生成
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:111:- world_model entries ≥ 段ごと閾値 (S2: 5, S3: 15, S4: 50, S5: 150)
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:131:M9 trunk (UNTOUCHED):
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:133:  - M9-eval Phase 2 完了
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:134:  - M9-B LoRA execution (philosopher_base = Kant 文体、固定)
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:135:  ↓ M9 完了 → individual layer 構築開始可能
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:138:  - PhilosopherBase / Individual / SubjectiveWorldModel / DevelopmentState
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:146:  - SubjectiveWorldModel の write path: prompt 注入 + bounded LLMPlan update +
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:148:  - NarrativeSelf 周期蒸留 (chashitsu reflection 拡張で発火)
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:149:  - DevelopmentState は S1 固定 (transition machinery は M11)
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:152:M11-A: DevelopmentState transition machinery (提案 6 lifecycle 化)
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:159:  - Burrows ratio で base 保持 + 個体ばらつきを分解測定
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:160:  - acceptance: base style identity ≥ 0.6 (LoRA 効果残存) AND individual variance ≥
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:166:  - LoRA を individual layer にも適用するか判断
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:181:3. **LoRA scope**: M9-B LoRA は base layer 専用か、individual の personality drift も
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:182:   学習対象か? 後者なら M9-B execution 着手前に再判断必要。
.steering/20260508-cognition-deepen-7point-proposal/design-clarified.md:185:   とき、SGLang RadixAttention 効果はどこまで保たれるか? 多 individual で多 base
.steering/20260424-m7-differentiation-observability/design-comparison.md:19:| L6 steering | 3 軸 (LoRA / scaling / user-dialog) | 4 節 (+ 運用予算制約) + **ADR 3 本** + design.md の acceptance gate |
.steering/20260424-m7-differentiation-observability/design-comparison.md:37:- **ADR 形式** の decisions.md (LoRA backend / agent cap / dialogue IF modality)
.steering/20260424-m7-differentiation-observability/design-v1.md:74:- **requirement.md**: M9 LoRA 適用の発火条件を言語化
.steering/20260424-m7-differentiation-observability/design-v1.md:76:  1. LoRA 閾値: episodic/reflection/dialog どの数値で export 発火か
.steering/20260424-m7-differentiation-observability/requirement.md:13:L6 (LoRA / agent scaling / user-dialogue IF) ロードマップは
.steering/20260424-m7-differentiation-observability/design-v2.md:55:- `requirement.md`: 4 節。(a) LoRA adoption path (データ収集→評価→adapter 適用トリガ), (b) agent scaling (3→6→N の world 負荷/tick budget/LLM 並列), (c) user-dialogue IF (4 人目 agent としてユーザ参加の contract), (d) 運用予算制約 (ローカル LLM only, Ollama 並列上限)
.steering/20260424-m7-differentiation-observability/design-v2.md:56:- `design.md`: acceptance gate 定量化。LoRA は「反省 200 件→DPO pair 抽出→Lite fine-tune 試行」gate
.steering/20260424-m7-differentiation-observability/design-v2.md:57:- `decisions.md`: ADR 形式 3 本 (LoRA backend, agent cap, dialogue IF modality)
.steering/20260508-cognition-deepen-7point-proposal/tasklist.md:6:- [x] M9-B LoRA design-final.md の前提確認
.steering/20260508-cognition-deepen-7point-proposal/tasklist.md:15:## Phase 2: User clarification 反映 (DONE 2026-05-08)
.steering/20260508-cognition-deepen-7point-proposal/tasklist.md:35:- [ ] PR description draft (M9-eval / M9-B 影響整理含む)
.steering/20260508-cognition-deepen-7point-proposal/tasklist.md:39:- [ ] M10-A scaffold task の `.steering/` dir 作成 (M9 完了後 kick)
.steering/20260508-cognition-deepen-7point-proposal/tasklist.md:40:- [ ] M9-B execution task に "post-LoRA で base/individual 検証 acceptance" を追記
.steering/20260508-cognition-deepen-7point-proposal/tasklist.md:46:- M9-eval / M9-B / G-GEAR run1 calibration の中断・修正
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/decisions.md:59:### M1. 5 wall sequential は ME-9 の "single 600 min cell" から実質変更
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/decisions.md:107:| Q5 ME-9 re-open trigger 連動 | C (Codex review/child ADR)、720 強行は trigger 空文化 | 採用 (v2 prompt §ブロッカー予測で明記) |
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/decisions.md:126:- **§ブロッカー予測**: ME-9 re-open trigger (focal/h ≤55 / ≥80) で **C 案
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/decisions.md:133:- 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260426-m7-slice-delta/design-final.md:37:- Add `# SAFETY: single-writer (M9 may need asyncio.Lock)` comment at `world/tick.py:455-510` (R3 H2). No Lock now — premature.
.steering/20260426-m7-slice-delta/design-final.md:90:| `src/erre_sandbox/world/tick.py:455-510` | Extend `apply_affinity_delta(self, ..., zone: Zone)`; write `last_interaction_zone=zone`; on `delta < -0.05` write `Physical.emotional_conflict += abs(delta)*0.5` clamped [0,1]; add `# SAFETY: single-writer (M9 may need asyncio.Lock)` comment; post-mutation belief promotion check | 2, 3, 5, H2 |
.steering/20260425-m8-session-phase-model/decisions.md:37:  されない (M8 spike は単一 WorldRuntime 前提)。M9 以降で必要になったら
.steering/20260425-m8-session-phase-model/decisions.md:71:- Q&A epoch の LLM routing 実装は M9 以降 (次の /start-task で別 spike を立てる)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:17:- 関連 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:26:## 1. 背景: run0 incident と ME-9 ADR の確定方針
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:28:2026-05-06 Phase 2 run0 で 3 cell が wall=360 min で FAILED
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:30:(`codex-review-phase2-run0-timeout.md`) HIGH 4 件を切出後、ME-9 ADR で:
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:105:明示 + history (ME-9 ADR / run0 incident docs) と同居。
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:114:6. §Phase C — natural 全 15 cell + run0 再採取 (現 v1 §Phase 2 の置換)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:137:**はず**。ME-8 と ME-9 の間で `COOLDOWN_TICKS_EVAL` が変化していないか
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:165:### Q5. ME-9 re-open 条件との連動
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:166:ME-9 ADR re-open 条件 (`decisions.md:646` "focal/hour rate が 65 を大きく外れる、
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:169:run1 で observed focal/min が 0.92 (≤55/h、ME-9 re-open trigger 該当) を
.steering/20260421-m5-acceptance-live/acceptance.md:35:**7 項目すべて PASS**。M5 Phase 2 の本番 wire (FSM + sampling delta + dialog turn generator + orchestrator integration + Godot visuals) が実機 LLM 経路 + MacBook viewer の両方で意図通り動作することを確認した。
.steering/20260421-m5-acceptance-live/acceptance.md:117:したが、Godot 側 constant は **M5 Phase 2 全体で更新が漏れていた**
.steering/20260426-m7-slice-delta/decisions.md:46:User-confirmed via AskUserQuestion in Plan mode. Deferred to ε (M9-lora
.steering/20260426-m7-slice-delta/decisions.md:148:refactor (M9 sharding 等) で silent breakage の risk。3 箇所 SLF001 suppression。
.steering/20260425-m8-session-phase-model/design.md:94:- L6 ADR D3 → M8 spike (本 task) → M9 以降の Q&A runtime / LLM routing
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md:6:> 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md:57:6. **§Phase C** — natural 全 15 cell + run0 再採取 (現 v1 §Phase 2 の置換):
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md:130:5. **ME-9 re-open 条件との連動**: run1 で observed focal/min が 0.92 (≤55/h)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md:138:- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260426-m7-slice-delta/design.md:56:- 案 D: defer to ε / m9-lora (LoRA 出力で自動分化を待つ)
.steering/20260419-m2-functional-closure/requirement.md:56:- **SGLang 移行 / LoRA**: M7+ スコープ
.steering/20260421-m5-acceptance-live/requirement.md:5:M5 Phase 2 の 7 本の PR (#56 contracts-freeze / #57 fsm / #58 world-zone-triggers /
.steering/20260421-m5-acceptance-live/requirement.md:71:- M6 以降のタスク (新規 persona 追加、LoRA 等)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/requirement.md:6:main = `0304ea3`) で ME-9 ADR の CLI fix + sidecar + audit gate が main へ反映
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/requirement.md:7:された。これにより partial publish が機械的に区別可能になり、Phase 2 run1
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/requirement.md:15:ME-9 ADR は run1 を「kant のみ 1 cell × wall 600 min single calibration」で
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/requirement.md:51:- run2-4 の実走および merge 後の matrix 確定 (M9-eval 全体タスクへ持ち越し)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/requirement.md:54:- vLLM / SGLang / LoRA 周辺 (M9-B 系統)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/requirement.md:73:- [ ] PR description で v1 prompt との差分を明示し、ME-9 ADR をリンク参照
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/requirement.md:78:- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9 ("Phase 2 run0
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/requirement.md:81:  Phase 2 run0 wall-timeout (2026-05-06)"
.steering/20260425-m8-session-phase-model/tasklist.md:18:- [ ] **Phase 2**: session_phase の所在を AgentState vs BootConfig で決定
.steering/20260421-m5-orchestrator-integration/decisions.md:3:本タスクで採用した設計判断とその根拠。M5 Phase 2 の最後の 2 タスク
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.md:24:### M1. 5 wall sequential は ME-9 の “single 600 min cell” から実質変更
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.md:61:ME-9 re-open trigger に当たるなら、default は停止して Codex review/child ADR。720 min 強行は「re-open 条件」を空文化する。D は review 後の暫定運用案としてなら可。
.steering/20260421-m5-orchestrator-integration/requirement.md:5:M5 Phase 2 の前段 3 タスク (PR #58 FSM wire / PR #60 sampling delta / PR #61 dialog
.steering/20260421-m5-orchestrator-integration/requirement.md:17:7 項目 PASS/FAIL を判定できる状態にする。これは M5 Phase 2 の critical path 上
.steering/20260426-m7-slice-delta/requirement.md:73:- LoRA / persona 分化 → L6 / m9-lora
.steering/20260426-m7-slice-delta/requirement.md:106:- [ ] M9 LoRA 比較 reference として γ Run-1 と δ Run-1 の baseline metrics 並記
.steering/20260419-m2-integration-e2e-execution/requirement.md:58:- **SGLang 移行 / LoRA** — M7 以降
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:30:- 関連 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:39:## 1. 背景: run0 incident と ME-9 ADR の確定方針
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:41:2026-05-06 Phase 2 run0 で 3 cell が wall=360 min で FAILED
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:43:(`codex-review-phase2-run0-timeout.md`) HIGH 4 件を切出後、ME-9 ADR で:
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:118:明示 + history (ME-9 ADR / run0 incident docs) と同居。
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:127:6. §Phase C — natural 全 15 cell + run0 再採取 (現 v1 §Phase 2 の置換)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:150:**はず**。ME-8 と ME-9 の間で `COOLDOWN_TICKS_EVAL` が変化していないか
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:178:### Q5. ME-9 re-open 条件との連動
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:179:ME-9 ADR re-open 条件 (`decisions.md:646` "focal/hour rate が 65 を大きく外れる、
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:182:run1 で observed focal/min が 0.92 (≤55/h、ME-9 re-open trigger 該当) を
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:345:I’ve confirmed the workflow only requires records for implementation work; this review stays read-only. Next I’m reading the local guidance and the ME-9/code references needed to validate the proposed prompt mechanics.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:542:   566	## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:562:   586	  2. **Phase 2 採取戦略**:
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:606:   630	    で収まらず M9 milestone 全体延伸過大
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:616:   640	  - Phase 2 deadline 延伸 (推定 1-2 week、CLI fix PR + run1 calibration +
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:635:   659	  LOW 1 / 2026-05-05 P3a-finalize HIGH 3 / MEDIUM 4 / LOW 4 / 2026-05-06 Phase 2
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:645:   669	- 既存 M9-B DB1-DB10 ADR との衝突: 無し
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:668:    17	> ## ⚠️ 2026-05-06 追記 — Phase 2 run0 incident で本 prompt は SUPERSEDED
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:670:    19	> 2026-05-06 の Phase 2 run0 (3-parallel natural、wall=360 min) は 3 cell 全て
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:675:    24	> **本 prompt の §Phase 2 採取と §ブロッカー予測 item 2 は不正確** (wall=360 を
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:677:    26	> 正しい運用は ME-9 ADR (`decisions.md`) と `cli-fix-and-audit-design.md` を
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:699:    48	> `--focal-target` + `--report-json` の 3 flag に集約)。Phase 1 / Phase 2 採取
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:764:   332	   < 500)、**600 min 最低ライン**。対処は ME-9 ADR の通り CLI fix + run1
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:766:   334	   詳細: `decisions.md` ME-9 / `blockers.md` "active incident: Phase 2 run0
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:934:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:48:> `--focal-target` + `--report-json` の 3 flag に集約)。Phase 1 / Phase 2 採取
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:1223:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:10:Phase 2 run0 で 3 cell が wall=360 min で FAILED (focal=381/390/399 prefix
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:1798:.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:81:| **ε** | dialog_turn_budget を 6 → 3 に縮めて burst 期間を短縮、cooldown 計算根拠を変える | dialog 内 turn 数が減る、Burrows/MATTR の per-dialog stylo signal が薄まる |
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:1896:.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:482:.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:81:| **ε** | dialog_turn_budget を 6 → 3 に縮めて burst 期間を短縮、cooldown 計算根拠を変える | dialog 内 turn 数が減る、Burrows/MATTR の per-dialog stylo signal が薄まる |
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:2044:.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:1423:    81	| **ε** | dialog_turn_budget を 6 → 3 に縮めて burst 期間を短縮、cooldown 計算根拠を変える | dialog 内 turn 数が減る、Burrows/MATTR の per-dialog stylo signal が薄まる |
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:2440:5df6d5d docs(steering): m9-eval — Phase 2 run0 rescue verify 結果ブロック追記 (#139)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:2442:e474f5a chore(eval): m9-eval-p3 — Phase 2 run0 rescue 証跡 + .gitignore patch
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:2444:48d7f1a (origin/docs/m9-eval-phase2-run0-incident-record) docs(steering): add G-GEAR rescue verify prompt for Phase 2 run0 .tmp
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:2445:efcdfab docs(steering): m9-eval Phase 2 run0 wall-timeout incident — ME-9 ADR + Codex 6th review
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:2455:     4	ME-9 ADR. Reads ``<output>.duckdb`` plus its sidecar
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:2724:   722	    * stale ``.tmp`` with no sidecar (legacy or pre-ME-9 capture): unlinks
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:2900:  1153	                # ME-9 / Codex HIGH-3 (2026-05-06): wall budget = soft timeout,
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3480:efcdfab docs(steering): m9-eval Phase 2 run0 wall-timeout incident — ME-9 ADR + Codex 6th review
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3512:    17	   Burrows Delta per-utterance against the persona's own reference, MATTR
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3566:    71	    BurrowsLanguageMismatchError,
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3570:    75	from erre_sandbox.evidence.tier_a.burrows import BurrowsTokenizationUnsupportedError
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3602:   107	# captures the Burrows Delta Japanese tokenizer gap: ``compute_burrows_delta``
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3603:   108	# raises ``BurrowsTokenizationUnsupportedError`` for any rikyu utterance
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3606:   111	# lightweight partial update of ME-4 with Burrows scoped to (kant,
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3610:   115	        "BurrowsTokenizationUnsupportedError — Japanese tokenizer not "
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3646:   151	    """Compute Burrows Delta for each utterance against the persona reference.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3648:   153	    Returns a list of floats; entries that raise BurrowsLanguageMismatchError
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3668:   173	        except (BurrowsLanguageMismatchError, BurrowsTokenizationUnsupportedError):
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3670:   175	            # BurrowsTokenizationUnsupportedError; previously only
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3671:   176	            # BurrowsLanguageMismatchError was caught, so the exception
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3693:   198	    extras) propagated to ``main()`` and erased the entire cell — Burrows
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3841:   479	      Burrows is known-skipped because the Japanese tokenizer is not
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3907:scripts/p3a_decide.py:731:                "Vendi + Big5 ICC; this Mac session computes Burrows Delta + "
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3945:.steering/20260430-m9-eval-system/design-final.md:335:**DB9 sub-metric 3 個 (Vendi / Big5 ICC / Burrows Delta) ready 時期**:
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3951:.steering/20260430-m9-eval-system/design-final.md:419:3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3963:.steering/20260430-m9-eval-system/design-final.md:497:   - 反復: P3b で pilot run 50 turn 両形式比較、Burrows / Vendi の bootstrap CI
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:3966:.steering/20260430-m9-eval-system/design-final.md:555:  P1a (Tier A sub-module、Burrows は z-score Delta で実装) → P2c (external golden
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4000:.steering/20260430-m9-eval-system/decisions.md:146:  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4010:.steering/20260430-m9-eval-system/decisions.md:224:    - 本 ADR は ME-4 §判定基準が指す **3 metric (Burrows / Vendi / Big5 ICC)**
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4021:.steering/20260430-m9-eval-system/decisions.md:381:  - Option B (Kant のみ MCQ): per-persona stimulus mass 違いで Vendi/Burrows の
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4031:.steering/20260430-m9-eval-system/decisions.md:566:## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4046:.steering/20260430-m9-eval-system/decisions.md:640:  - Phase 2 deadline 延伸 (推定 1-2 week、CLI fix PR + run1 calibration +
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4051:.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md:26:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4053:.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md:96:> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4054:.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md:102:- Uses Burrows Delta + **MATTR** (not in ADR), defers Vendi + Big5 ICC.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4057:.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md:115:  produce a different ratio than Burrows + Vendi + Big5 ICC?
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4065:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:1:# CLI Fix + Audit CLI 設計サマリ — Phase 2 run0 incident 対応
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4066:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:10:Phase 2 run0 で 3 cell が wall=360 min で FAILED (focal=381/390/399 prefix
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4075:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:248:- incident: `blockers.md` "active incident: Phase 2 run0 wall-timeout (2026-05-06)"
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4083:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:1:# Codex Independent Review — Phase 2 run0 wall-timeout incident
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4084:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:5:m9-eval-system Phase 2 run0 で 3 cell (kant / nietzsche / rikyu) すべてが
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4095:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:136:- (g) run0 救出を採用すると Phase 2 の "5 runs × 3 personas × 2 conditions"
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4118:.steering/20260430-m9-eval-system/design-natural-gating-fix.md:225:  scheduler は admit する。文体には影響あるが eval 目的 (Burrows / Vendi の
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4121:.steering/20260430-m9-eval-system/codex-review-prompt.md:21:Big5-ICC / Burrows-Delta have bootstrap CI ready (precondition for M9-C-adopt).
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4144:.steering/20260430-m9-eval-system/design-v1.md:71:- (3) Burrows のみは Big5 を諦めることになり DB9 sub-metric `big5_stability_icc` の
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4150:.steering/20260430-m9-eval-system/design-v1.md:173:**DB9 sub-metric 3 個 (Vendi / Big5 ICC / Burrows Delta) ready 時期**:
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4178:.steering/20260430-m9-eval-system/codex-review-step1-prompt.md:183:   The ratio decision is bootstrap CI WIDTH on Burrows/Vendi/ICC, where
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4182:.steering/20260430-m9-eval-system/codex-review-step1.md:14:It collapses Kant’s pilot to Wachsmuth-only, so the “stimulus” condition no longer represents the planned 70-item mix. Vendi/Burrows CI width is prompt-genre sensitive, so category mix is not secondary here. Do not use `cycle_count=2`; it breaks the 200-vs-200 pilot symmetry.  
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4201:.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:1:# G-GEAR セッション用プロンプト — Phase 2 run0 `.tmp` rescue verify
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4202:.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:7:> **本セッションは採取しない**。Phase 2 run0 で wall=360 min FAILED した
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4204:.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:17:タスク `20260430-m9-eval-system` の Phase 2 run0 wall-timeout incident の
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4207:.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:51:Phase 2 採取時の output path は launch prompt 通り `data/eval/golden/` のはず
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4212:.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:86:# Phase 2 run0 の expected counts (Mac 側 incident report 由来)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4242:scripts/p3_run0_rescue_verify.py:1:"""Phase 2 run0 wall-timeout rescue verify (ME-9 確定アクション #1).
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4252:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:17:> ## ⚠️ 2026-05-06 追記 — Phase 2 run0 incident で本 prompt は SUPERSEDED
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4253:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:19:> 2026-05-06 の Phase 2 run0 (3-parallel natural、wall=360 min) は 3 cell 全て
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4280:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:226:# Phase 2 run0 incident のような partial 群を別運用したい場合
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4294:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:332:   < 500)、**600 min 最低ライン**。対処は ME-9 ADR の通り CLI fix + run1
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4296:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:334:   詳細: `decisions.md` ME-9 / `blockers.md` "active incident: Phase 2 run0
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4394:.steering/20260430-m9-eval-system/tasklist.md:443:  - [ ] 3 sub-metric (Vendi / Big5 ICC / Burrows Delta) の CI 計算 ready
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4398:.steering/20260430-m9-eval-system/tasklist.md:468:- [ ] [Mac] DB9 sub-metric 3 個 (Vendi / Big5 ICC / Burrows Delta) の bootstrap CI
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4450:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:39:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4452:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:109:> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4453:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:115:- Uses Burrows Delta + **MATTR** (not in ADR), defers Vendi + Big5 ICC.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4456:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:128:  produce a different ratio than Burrows + Vendi + Big5 ICC?
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4466:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1037:   375	    - [ ] Burrows Delta / Vendi / Big5 ICC の CI width 比較
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4467:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1067:   146	  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4505:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2078:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4507:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2148:> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4508:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2154:- Uses Burrows Delta + **MATTR** (not in ADR), defers Vendi + Big5 ICC.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4509:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2189:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4511:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2261:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4513:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2331:> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4514:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2337:- Uses Burrows Delta + **MATTR** (not in ADR), defers Vendi + Big5 ICC.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4515:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2372:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4524:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2873:  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4525:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2874:  Why it matters: The workflow can falsely close ME-4 from Burrows+MATTR even though Vendi and Big5 ICC are the ADR metrics.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4526:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2875:  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4528:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2879:  Why it matters: Burrows+MATTR may produce a different ratio than Burrows+Vendi+Big5.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4529:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2941:  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4530:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2942:  Why it matters: The workflow can falsely close ME-4 from Burrows+MATTR even though Vendi and Big5 ICC are the ADR metrics.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4531:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2943:  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4533:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2947:  Why it matters: Burrows+MATTR may produce a different ratio than Burrows+Vendi+Big5.
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4568:.steering/20260430-m9-eval-system/g-gear-p3a-prompt.md:191:#   - utterance 文字数 mean/median (Burrows / Vendi の input volume 確認)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4590:.steering/20260430-m9-eval-system/blockers.md:28:  Vendi/Burrows の persona 横比較を交絡、Option C は persona-factuality 軸を消す。
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4596:.steering/20260430-m9-eval-system/blockers.md:162:| Burrows chunk stability (Nietzsche) | rank instability 検出 (現状 ρ=1.0 PASS) | golden baseline 採取後 |
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4598:.steering/20260430-m9-eval-system/blockers.md:167:## active incident: Phase 2 run0 wall-timeout (2026-05-06)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4599:.steering/20260430-m9-eval-system/blockers.md:171:P3 production 採取の Phase 2 run0 (3-parallel: kant + nietzsche + rikyu, natural
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4611:.steering/20260430-m9-eval-system/blockers.md:230:**source path**: `data/eval/golden/` (Phase 2 採取時の output 先)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4615:.steering/20260430-m9-eval-system/blockers.md:251:**partial の取り扱い**: ME-9 ADR の通り primary 5 runs matrix から外す
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4619:.steering/20260430-m9-eval-system/codex-review-prompt-low1.md:55:   Vendi/Burrows の persona 横比較が "stimulus 種類効果 × persona 効果" 分離不能
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4626:.steering/20260430-m9-eval-system/requirement.md:17:  2. M9-C-adopt の前提条件として **Vendi / Big5 ICC / Burrows Delta の 3 sub-metric
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4627:.steering/20260430-m9-eval-system/requirement.md:19:  3. golden baseline (LoRA 適用前の anchor) を採取しておかないと、後で adopt 判断に
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4639:.steering/20260430-m9-eval-system/requirement.md:114:- `docs/glossary.md` — Tier 0/A/B/C / Vendi / Burrows Delta / IPIP-NEO 等の用語
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4648:.steering/20260430-m9-eval-system/codex-review-low1.md:68:   Vendi/Burrows の persona 横比較が "stimulus 種類効果 × persona 効果" 分離不能
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4655:.steering/20260430-m9-eval-system/codex-review-low1.md:374:| Burrows chunk stability (Nietzsche) | rank instability 検出 (現状 ρ=1.0 PASS) | golden baseline 採取後 |
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4685:.steering/20260430-m9-eval-system/codex-review-low1.md:565:  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4718:.steering/20260430-m9-eval-system/codex-review-low1.md:992:   494	   - 反復: P3b で pilot run 50 turn 両形式比較、Burrows / Vendi の bootstrap CI
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4719:.steering/20260430-m9-eval-system/codex-review-low1.md:1003:   416	3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4729:.steering/20260430-m9-eval-system/codex-review-low1.md:1533:   Vendi/Burrows の persona 横比較が "stimulus 種類効果 × persona 効果" 分離不能
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4733:.steering/20260430-m9-eval-system/codex-review-low1.md:1672:   Vendi/Burrows の persona 横比較が "stimulus 種類効果 × persona 効果" 分離不能
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4742:.steering/20260430-m9-eval-system/codex-review-low1.md:1932:   207	  - [ ] Burrows Delta / Vendi / Big5 ICC の CI width 計算
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4747:.steering/20260430-m9-eval-system/codex-review-low1.md:2342:.steering/20260430-m9-b-lora-execution-plan/design-v2.md:171:- M9-eval-system: Tier B 完全実装 (Prometheus 2 rubric / FANToM-adapted / FActScore-adapted) + 専門家 review pipeline + golden set 採取
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4751:.steering/20260430-m9-eval-system/codex-review-low1.md:2351:.steering/20260430-m9-eval-system/design-final.md:416:3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4761:.steering/20260430-m9-eval-system/codex-review-low1.md:2444:.steering/20260430-m9-eval-system/codex-review-low1.md:1003:   416	3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4764:.steering/20260430-m9-eval-system/codex-review-low1.md:2556:.steering/20260430-m9-b-lora-execution-plan/design-v1.md:111:- M9-eval-system: Tier B-D (Vendi / Prometheus / FANToM / FActScore / 専門家 review) を切り出し
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4768:.steering/20260430-m9-eval-system/codex-review-low1.md:2588:.steering/20260430-m9-eval-system/codex-review.md:1013:   354	3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:4851:tests/test_cli/test_eval_audit.py:3:Covers ME-9 ADR §2 (audit gate) and Codex 2026-05-06 review HIGH-1 (run_id
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:5184:     4	Adopted in m9-eval-cli-partial-fix (ME-9 ADR) so partial / fatal / complete
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:5650:tests/test_cli/test_eval_audit.py:3:Covers ME-9 ADR §2 (audit gate) and Codex 2026-05-06 review HIGH-1 (run_id
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6520:.steering/20260430-m9-eval-system/blockers.md:167:## active incident: Phase 2 run0 wall-timeout (2026-05-06)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6521:.steering/20260430-m9-eval-system/blockers.md:171:P3 production 採取の Phase 2 run0 (3-parallel: kant + nietzsche + rikyu, natural
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6533:.steering/20260430-m9-eval-system/blockers.md:230:**source path**: `data/eval/golden/` (Phase 2 採取時の output 先)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6538:.steering/20260430-m9-eval-system/blockers.md:251:**partial の取り扱い**: ME-9 ADR の通り primary 5 runs matrix から外す
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6540:.steering/20260430-m9-eval-system/blockers.md:254:`partial/censored` diagnostic 専用として `M9-A audit` 等に活用候補。
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6543:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:1:# CLI Fix + Audit CLI 設計サマリ — Phase 2 run0 incident 対応
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6545:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:10:Phase 2 run0 で 3 cell が wall=360 min で FAILED (focal=381/390/399 prefix
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6577:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:248:- incident: `blockers.md` "active incident: Phase 2 run0 wall-timeout (2026-05-06)"
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6583:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:17:> ## ⚠️ 2026-05-06 追記 — Phase 2 run0 incident で本 prompt は SUPERSEDED
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6584:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:19:> 2026-05-06 の Phase 2 run0 (3-parallel natural、wall=360 min) は 3 cell 全て
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6606:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:199:`m9-eval-cli-partial-fix` (ME-9 ADR、CLI fix PR 適用後) で実装された
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6615:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:226:# Phase 2 run0 incident のような partial 群を別運用したい場合
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6621:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:233:# `data/eval/partial/` 隔離の運用は ME-9 ADR どおり。
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6637:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:334:   詳細: `decisions.md` ME-9 / `blockers.md` "active incident: Phase 2 run0
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6734:    88	# m9-eval-system Phase 2 run0 rescue stash (.duckdb copies from .tmp).
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6797:.steering/20260430-m9-eval-system/blockers.md:230:**source path**: `data/eval/golden/` (Phase 2 採取時の output 先)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6801:.steering/20260430-m9-eval-system/blockers.md:254:`partial/censored` diagnostic 専用として `M9-A audit` 等に活用候補。
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6904:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:233:# `data/eval/partial/` 隔離の運用は ME-9 ADR どおり。
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:6987:.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:51:Phase 2 採取時の output path は launch prompt 通り `data/eval/golden/` のはず
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7101:     6	main = `0304ea3`) で ME-9 ADR の CLI fix + sidecar + audit gate が main へ反映
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7102:     7	された。これにより partial publish が機械的に区別可能になり、Phase 2 run1
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7110:    15	ME-9 ADR は run1 を「kant のみ 1 cell × wall 600 min single calibration」で
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7146:    51	- run2-4 の実走および merge 後の matrix 確定 (M9-eval 全体タスクへ持ち越し)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7149:    54	- vLLM / SGLang / LoRA 周辺 (M9-B 系統)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7168:    73	- [ ] PR description で v1 prompt との差分を明示し、ME-9 ADR をリンク参照
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7173:    78	- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9 ("Phase 2 run0
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7176:    81	  Phase 2 run0 wall-timeout (2026-05-06)"
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7240:     6	> 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7291:    57	6. **§Phase C** — natural 全 15 cell + run0 再採取 (現 v1 §Phase 2 の置換):
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7364:   130	5. **ME-9 re-open 条件との連動**: run1 で observed focal/min が 0.92 (≤55/h)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7372:   138	- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7570:   167	## active incident: Phase 2 run0 wall-timeout (2026-05-06)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7574:   171	P3 production 採取の Phase 2 run0 (3-parallel: kant + nietzsche + rikyu, natural
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7618:   215	### 確定アクション (ME-9 ADR で確定、本 incident block 期間中)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7633:   230	**source path**: `data/eval/golden/` (Phase 2 採取時の output 先)
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7654:   251	**partial の取り扱い**: ME-9 ADR の通り primary 5 runs matrix から外す
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7657:   254	`partial/censored` diagnostic 専用として `M9-A audit` 等に活用候補。
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:7663:   260	- **本タスク内 reopen 不要**: ME-9 ADR で確定、CLI fix は別タスクに切り出し
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:8090:### M1. 5 wall sequential は ME-9 の “single 600 min cell” から実質変更
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:8127:ME-9 re-open trigger に当たるなら、default は停止して Codex review/child ADR。720 min 強行は「re-open 条件」を空文化する。D は review 後の暫定運用案としてなら可。
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:8161:### M1. 5 wall sequential は ME-9 の “single 600 min cell” から実質変更
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.raw.log:8198:ME-9 re-open trigger に当たるなら、default は停止して Codex review/child ADR。720 min 強行は「re-open 条件」を空文化する。D は review 後の暫定運用案としてなら可。
.steering/_verify-report-20260429.md:20:| — | Phase 2 (新規 marketplace) | ❌ skip — `docs/external-skills.md` 不在 |
.steering/_verify-report-20260429.md:21:| Phase 2 | Phase 3 | ✅ 完了 — ただし `docs/agent-shared.md` 不在 |
.steering/_verify-report-20260429.md:34:### Phase 2: Marketplace ❌ SKIPPED (新仕様)
.steering/_verify-report-20260429.md:51:- 公式 Skill 重複回避: 検証不能 (Phase 2 skip により真実源なし)
.steering/_verify-report-20260429.md:129:1. **`docs/external-skills.md` が存在しない** — Phase 2 (marketplace) を skip した結果。Phase 4 で「公式 Skill 重複回避」検証ができない
.steering/_verify-report-20260429.md:153:- 差分の主因: 新仕様で Phase 2 (Marketplace) と Phase 5 (Codex Bridge) が追加され、本リポはその仕様パスを採用していない (=skip + 代替レイアウト) ため、検証項目が増えて差分が表面化した
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/blockers.md:33:- target ratio (Burrows / MATTR) 確定、ME-4 stage 3 close 候補
.steering/20260507-m9-eval-phase2-run1-calibration-prompt/blockers.md:35:### D-4. ME-9 re-open trigger 該当時の child ADR 起票
.steering/20260425-m8-baseline-quality-metric/decisions.md:14:  「affinity 推移」ではない別指標で、baseline に混入すると M9 比較が歪む
.steering/20260425-m8-baseline-quality-metric/decisions.md:18:  - v3 (proxy 使用) → 意味論乖離で M9 比較精度を下げる
.steering/20260425-m8-baseline-quality-metric/decisions.md:41:  別の望ましい性質。単一閾値だと両者を分解できず、LoRA 比較時に「どちらが
.steering/20260425-m8-baseline-quality-metric/decisions.md:47:  使わない。純粋に M9 との diff 可能な生数値として残す
.steering/20260425-m8-scaling-bottleneck-profiling/decisions.md:81:- v2 entropy slope への昇格は M9 で run 5+ 集まった後の reconsider に
.steering/20260425-m8-scaling-bottleneck-profiling/decisions.md:180:| M1 pair_information_gain | < 30% × log2(C(N,2)) | 哲学確定。N=2 は分母 1 pair で構造的限界 → 上限 0 / threshold 0 / strict `<` で silent skip。% 値の最終 calibration は M9 で N≥3 sample 蓄積後 |
.steering/20260425-m8-scaling-bottleneck-profiling/decisions.md:181:| M2 late_turn_fraction | > 0.6 | **provisional** — short run では M2 が 0.0 に張り付き relevant data 不足。M9 で long-run 再評価へ defer |
.steering/20260425-m8-scaling-bottleneck-profiling/decisions.md:206:  したら % 表現に揃えられるが M9 へ deferral)
.steering/20260425-m8-scaling-bottleneck-profiling/decisions.md:207:- σ-based fallback は M9 で run 5+ 蓄積後に追加検討 (Out of scope)
.steering/20260425-m8-baseline-quality-metric/design.md:9:L6 ADR D1 (`defer-and-measure`) の M8 precondition 後半。M9 LoRA 導入後に
.steering/20260425-m8-baseline-quality-metric/design.md:11:M8 時点で固定する。baseline なしでは M9 の効果測定が不能。
.steering/20260425-m8-baseline-quality-metric/design.md:126:- 平均 / 分散 / 代表値を `baseline.md` に記録、M9 比較の reference 固定
.steering/20260425-m8-baseline-quality-metric/design.md:133:- Parquet export (M9 LoRA task で追加)
.steering/20260425-m8-scaling-bottleneck-profiling/profile.md:93:**N≥3 で 30% 閾値が正常動作**する根拠は本 sample では sample A 1 件のみ。M9 で
.steering/20260425-m8-scaling-bottleneck-profiling/profile.md:95:spike では「30% × log2(C(N,2)) を確定哲学」として、% 値の最終確定は M9 へ。
.steering/20260425-m8-scaling-bottleneck-profiling/profile.md:119:→ 閾値 60% は **provisional**。M9 で長 run (>360s) を重ねたあと再評価。本 spike
.steering/20260425-m8-scaling-bottleneck-profiling/profile.md:145:全 sample が閾値より上 (alert 出ず)。**閾値 30% を確定**。M9 以降で 4 zone
.steering/20260425-m8-scaling-bottleneck-profiling/profile.md:152:M9 で n≥10 を蓄積後に CI と percentile を再計算する。
.steering/20260425-m8-scaling-bottleneck-profiling/profile.md:179:  - % 値の最終確定は N=3 long-run + N=4 sample が揃った M9 へ defer
.steering/20260425-m8-scaling-bottleneck-profiling/profile.md:182:  での再評価を M9 へ defer
.steering/20260425-m8-scaling-bottleneck-profiling/profile.md:183:* **M9 への引き継ぎ事項**:
.steering/20260425-m8-scaling-bottleneck-profiling/profile.md:192:  M1 が None で評価不能になる。120s+ で安定して 2+ dialog が出る (D, A)。M9 以降の
.steering/20260425-m8-scaling-bottleneck-profiling/profile.md:196:  弱い。M9 で 4th persona を agora 主体にする実験が立てられる
.steering/20260506-m9-eval-cli-partial-fix/decisions.md:10:- **背景**: ME-9 ADR で確定した「soft_timeout 分離 + sidecar + audit CLI」方針を
.steering/20260506-m9-eval-cli-partial-fix/decisions.md:23:  - 案 C 系は spec 起票やり直し + Phase 2 既存 30 cell との混在運用不可
.steering/20260506-m9-eval-cli-partial-fix/decisions.md:28:- **見直しタイミング**: M9-B `event_log` 拡張時、または partial publish の
.steering/20260506-m9-eval-cli-partial-fix/decisions.md:204:- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260425-m8-baseline-quality-metric/requirement.md:5:L6 ADR D1 (`defer-and-measure`) の M8 precondition。LoRA 導入後の比較基準
.steering/20260425-m8-baseline-quality-metric/requirement.md:7:する必要がある。baseline なしでは M9 で A1-b (全 persona LoRA) / A1-c
.steering/20260425-m8-baseline-quality-metric/requirement.md:25:- M9 で比較 run を流した時、同フォーマットで diff 可能
.steering/20260425-m8-baseline-quality-metric/requirement.md:45:- Parquet export (M9 LoRA task で必要になってから)
.steering/20260506-m9-eval-cli-partial-fix/design.md:39:  Phase 2 既存 30 cell との混在運用不可
.steering/20260506-m9-eval-cli-partial-fix/design.md:43:詳細比較マトリクスは Plan agent 出力 (Phase 2) を `~/.claude/plans/sleepy-fluttering-lake.md`
.steering/20260506-m9-eval-cli-partial-fix/design.md:131:- 不要 (CLI 単体タスク、Phase 2 run1 calibration は別タスク)
.steering/20260506-m9-eval-cli-partial-fix/design.md:165:- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260425-m8-baseline-quality-metric/tasklist.md:26:### Phase 2: sink 注入 (cognition + bootstrap)
.steering/20260425-m8-baseline-quality-metric/tasklist.md:114:- [ ] `baseline.md` に平均 / 分散 / 代表値を table 化、M9 比較 reference 固定
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.md:59:M9-B の `event_log` 追加が additive なら `extra="allow"` が最小コスト。semantics を変える場合だけ major version を導入する。C は現時点では重い。
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.md:72:- Phase 2 run1 calibration 自体は本タスク外。
.steering/20260418-implementation-plan/decisions.md:97:  MVP (1 体) では RadixAttention の恩恵が小さい
.steering/20260418-implementation-plan/decisions.md:129:    (RadixAttention で prefix KV 共有) → API が根本的に異なる
.steering/20260506-m9-eval-cli-partial-fix/tasklist.md:5:- [ ] `decisions.md` ME-9 ADR を再読
.steering/20260506-m9-eval-cli-partial-fix/tasklist.md:19:- [ ] 3 案を構造的 trade-off / test 可観測性 / caller 影響 / M9-B 再利用性 で比較
.steering/20260506-m9-eval-cli-partial-fix/tasklist.md:23:## Phase 2: 着手前 Codex independent review (必須)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:24:## 1. 背景: Phase 2 run0 incident と ME-9 ADR の確定方針
.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:26:2026-05-06、M9-eval Phase 2 run0 で 3 cell が **wall=360 min** で FAILED
.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:29:が Claude 単独案の **HIGH 4 件** を切出し、ME-9 ADR
.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:30:(`.steering/20260430-m9-eval-system/decisions.md` ME-9) で以下の方針が確定:
.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:39:4. **HIGH-2 (sample-size correction)**: Phase 2 run0 の partial を救済する
.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:167:spec 1.4 は `"schema_version": "1"` 固定。M9-B 以降で `event_log` / `q_and_a_subset`
.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:179:M9-B `event_log` 追加を想定した時、最も refactor cost が低い path はどれか。
.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:188:- M9-B での audit 拡張時に guard が制約になる懸念
.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:276:- **scope 厳守**: 本タスクは CLI fix + audit 整備のみ。Phase 2 run1 calibration
.steering/20260420-m5-godot-zone-visuals/requirement.md:5:M5 Phase 2 の並列 4 本のうち MacBook 側担当。G-GEAR が LLM/FSM 3 本
.steering/20260420-m5-godot-zone-visuals/requirement.md:71:- `.steering/20260420-m5-planning/tasklist.md` §Phase 2 並列 4 本
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:4:> (ME-9 ADR の hand-off。本 requirement はその実装側 task 起票で、spec を
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:9:Phase 2 run0 で 3 cell が wall=360 min で FAILED (focal=381/390/399 prefix
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:23:ME-9 ADR でこれらを (a) `eval_run_golden.py` の `soft_timeout` 分離 + sidecar
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:30:ME-9 ADR の実装を完了し、Phase 2 run1 calibration 着手のための前提
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:62:- HIGH-2 sample-size correction (ME-9 ADR で defer 確定、本タスク再採用しない)
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:63:- Phase 2 run1 の実走 (本タスクは CLI / audit 整備のみ、実走は別タスク)
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:64:- vLLM / SGLang LoRA 関連の改修 (M9-B 系統)
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:65:- `eval_audit` の policy 拡張 (例: per-persona threshold) は M9 後に持ち越し
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:70:- [ ] `eval_run_golden.py` が ME-9 ADR の spec 通りに改修されている
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:90:- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:92:  Phase 2 run0 wall-timeout (2026-05-06)"
.steering/20260506-m9-eval-cli-partial-fix/requirement.md:106:  - **複数案ありうる設計**: 案 A (soft_timeout 分離 + sidecar、ME-9 ADR の
.steering/20260418-implementation-plan/MASTER-PLAN.md:48:│ Inference: Ollama (MVP) / SGLang (M7+) / vLLM+LoRA (M9+)     │
.steering/20260418-implementation-plan/MASTER-PLAN.md:146:| **M8** | 観察 → LoRA 判断の橋渡し spike | `m8-episodic-log-pipeline`, `m8-baseline-quality-metric`, `m8-scaling-bottleneck-profiling`, `m8-session-phase-model` | L6 ADR 1/2/3 の preconditions を同時解決、M9 着手の go/no-go 判定材料を生む (詳細: `.steering/20260424-steering-scaling-lora/decisions.md`) |
.steering/20260418-implementation-plan/MASTER-PLAN.md:147:| **M9** | LoRA per persona (vLLM) | `inference-vllm-adapter`, `lora-training-pipeline`, `lora-runtime-swap` | M4-M7 で蓄積した ≥1000 ターン/ペルソナの対話ログで訓練。前提: L6 ADR1 の defer-and-measure 方針、M8 baseline quality data で A1-a/b/c/d/e 比較 |
.steering/20260418-implementation-plan/MASTER-PLAN.md:268:# M9: uv pip install "vllm"     # LoRA hot-swap
.steering/20260418-implementation-plan/MASTER-PLAN.md:393:| R12 | LoRA 訓練 (M9) のデータ不足 | M4-M7 で対話ログを常時 SQLite 永続化、ペルソナごと ≥1000 ターン蓄積 |
.steering/20260418-implementation-plan/MASTER-PLAN.md:486:| llm-inference | T09, T11, T19, M7 (SGLang), M9 (vLLM LoRA) |
.steering/20260506-m9-eval-cli-partial-fix/blockers.md:5:### B-1. ME-9 ADR 実装の hand-off に CLI fix 詳細仕様が不足
.steering/20260506-m9-eval-cli-partial-fix/blockers.md:15:  §Phase 1 (stimulus) / §Phase 2 (natural、wall budget / parallel 戦略) /
.steering/20260506-m9-eval-cli-partial-fix/blockers.md:16:  §empirical 工数推計 は ME-9 ADR の run1 calibration 結果が出てから v2 として
.steering/20260506-m9-eval-cli-partial-fix/blockers.md:30:### D-3. M9-B `event_log` 追加時の sidecar schema 進化
.steering/20260506-m9-eval-cli-partial-fix/blockers.md:31:- 本 PR の `SidecarV1.model_config = ConfigDict(extra="allow")` は M9-B の
.steering/20260506-m9-eval-cli-partial-fix/blockers.md:33:- **defer 理由**: `event_log` の正式 schema は M9-B / M10 の audit-trail 要求
.steering/20260506-m9-eval-cli-partial-fix/blockers.md:43:- **対応案**: M9 後の release-tooling 起票時に `scripts/sidecar_redact.py`
.steering/20260506-m9-eval-cli-partial-fix/blockers.md:59:  refactor は不要。M9-B での diagnostic 強化時に再評価。
.steering/20260506-m9-eval-cli-partial-fix/blockers.md:66:- **観測点**: Phase 2 run1 calibration で `runtime_drain_timeout=true` の
.steering/20260420-m5-godot-zone-visuals/tasklist.md:26:## 実装 — Phase 2: BodyTinter + DialogBubble
.steering/20260425-m8-scaling-bottleneck-profiling/requirement.md:28:- 4th persona の選定 / 追加実装 (M9 or later)
.steering/20260425-m8-scaling-bottleneck-profiling/requirement.md:29:- `dialog.py:113` の N 依存ハードコード解消 (M9 or later の別 task)
.steering/20260425-m8-scaling-bottleneck-profiling/requirement.md:30:- Dialog scheduler の tier / cooldown 再設計 (M9 以降)
.steering/20260425-m8-scaling-bottleneck-profiling/pre-plan-research.md:108:- **`_iter_colocated_pairs` の O(N²)**: 「削除」ではなく「M9 で parameterize」が
.steering/20260425-m8-scaling-bottleneck-profiling/pre-plan-research.md:118:  RadixAttention 共有 prefix       -30% (KV)
.steering/20260425-m8-scaling-bottleneck-profiling/pre-plan-research.md:211:4. M9 go/no-go: "いずれかの metric が threshold exceed したら +1 persona を起票"
.steering/20260421-m5-erre-sampling-override-live/requirement.md:80:- `.steering/20260420-m5-planning/design.md` §Phase 2 並列 4 本
.steering/20260425-m8-scaling-bottleneck-profiling/tasklist.md:56:- [ ] merge 後、L6 D2 status を「閾値案確定、M9 以降のトリガー判定に使用可」に更新
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:37:## 1. 背景: Phase 2 run0 incident と ME-9 ADR の確定方針
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:39:2026-05-06、M9-eval Phase 2 run0 で 3 cell が **wall=360 min** で FAILED
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:42:が Claude 単独案の **HIGH 4 件** を切出し、ME-9 ADR
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:43:(`.steering/20260430-m9-eval-system/decisions.md` ME-9) で以下の方針が確定:
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:52:4. **HIGH-2 (sample-size correction)**: Phase 2 run0 の partial を救済する
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:180:spec 1.4 は `"schema_version": "1"` 固定。M9-B 以降で `event_log` / `q_and_a_subset`
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:192:M9-B `event_log` 追加を想定した時、最も refactor cost が低い path はどれか。
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:201:- M9-B での audit 拡張時に guard が制約になる懸念
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:289:- **scope 厳守**: 本タスクは CLI fix + audit 整備のみ。Phase 2 run1 calibration
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:1004:    (RadixAttention prefix sharing across personas + a single-turn cue).
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2102:   sentinel-row fixtures (``M9_EVAL_SENTINEL_LEAK_*``) that verify no
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2108:   sentinel test scope because the M9 LoRA training pipeline reads
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2136:This is the **only** schema the LoRA training pipeline is allowed to read
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2177:``mode`` / ``zone`` / ``reasoning`` are reserved for the M9 ingest CLI
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2210:SENTINEL_LEAK_PREFIX: Final[str] = "M9_EVAL_SENTINEL_LEAK_"
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2322:- **推論 (実)**: Ollama 上の `qwen3:8b` (GGUF Q5_K_M, ~5.2GB)。SGLang は M7 移行検討、vLLM は M9 (LoRA) 計画
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2333:│   Ollama (現状) / SGLang (M7+ 計画) / vLLM (M9+ LoRA)              │
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2335:│   RadixAttention × 3 persona × prefix KV 共有 [planned: SGLang 移行で]│
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2336:│   (将来) LoRA per persona via vLLM --enable-lora                    │
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2385:| LLM 推論 (本番) | SGLang | 最新 | RadixAttention でマルチエージェント最高スループット |
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2387:| LLM 推論 (将来) | vLLM | 最新 | LoRA 動的切替 (--enable-lora) |
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2402:  - SGLang server: RadixAttention で共有 prefix KV を再利用
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2404:  - ペルソナ管理: インコンテキスト (Phase 1) → LoRA (Phase 2)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2426:  M9 比較や scaling トリガー判定に使う JSON / TSV を出力する
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2434:  入れて困るか見る) を捨て、metric が解析的上限の % を割った瞬間に M9 +1
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2492:/bin/zsh -lc 'rg -n "ME-9|cli-fix|sidecar|partial|allow-partial|drain" .steering/20260430-m9-eval-system .steering/20260506-m9-eval-cli-partial-fix' in /Users/johnd/ERRE-Sand Box
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2529:.steering/20260506-m9-eval-cli-partial-fix/design.md:133:- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2532:.steering/20260506-m9-eval-cli-partial-fix/requirement.md:4:> (ME-9 ADR の hand-off。本 requirement はその実装側 task 起票で、spec を
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2538:.steering/20260506-m9-eval-cli-partial-fix/requirement.md:23:ME-9 ADR でこれらを (a) `eval_run_golden.py` の `soft_timeout` 分離 + sidecar
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2540:.steering/20260506-m9-eval-cli-partial-fix/requirement.md:30:ME-9 ADR の実装を完了し、Phase 2 run1 calibration 着手のための前提
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2547:.steering/20260506-m9-eval-cli-partial-fix/requirement.md:62:- HIGH-2 sample-size correction (ME-9 ADR で defer 確定、本タスク再採用しない)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2548:.steering/20260506-m9-eval-cli-partial-fix/requirement.md:70:- [ ] `eval_run_golden.py` が ME-9 ADR の spec 通りに改修されている
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2555:.steering/20260506-m9-eval-cli-partial-fix/requirement.md:90:- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2558:.steering/20260506-m9-eval-cli-partial-fix/requirement.md:106:  - **複数案ありうる設計**: 案 A (soft_timeout 分離 + sidecar、ME-9 ADR の
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2560:.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:24:## 1. 背景: Phase 2 run0 incident と ME-9 ADR の確定方針
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2561:.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:29:が Claude 単独案の **HIGH 4 件** を切出し、ME-9 ADR
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2562:.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:30:(`.steering/20260430-m9-eval-system/decisions.md` ME-9) で以下の方針が確定:
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2569:.steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md:39:4. **HIGH-2 (sample-size correction)**: Phase 2 run0 の partial を救済する
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2627:.steering/20260506-m9-eval-cli-partial-fix/_codex-review-cli-fix-transcript.log:37:## 1. 背景: Phase 2 run0 incident と ME-9 ADR の確定方針
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2628:.steering/20260506-m9-eval-cli-partial-fix/_codex-review-cli-fix-transcript.log:42:が Claude 単独案の **HIGH 4 件** を切出し、ME-9 ADR
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2629:.steering/20260506-m9-eval-cli-partial-fix/_codex-review-cli-fix-transcript.log:43:(`.steering/20260430-m9-eval-system/decisions.md` ME-9) で以下の方針が確定:
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2636:.steering/20260506-m9-eval-cli-partial-fix/_codex-review-cli-fix-transcript.log:52:4. **HIGH-2 (sample-size correction)**: Phase 2 run0 の partial を救済する
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2719:.steering/20260430-m9-eval-system/decisions.md:566:## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2742:.steering/20260506-m9-eval-cli-partial-fix/tasklist.md:5:- [ ] `decisions.md` ME-9 ADR を再読
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2772:.steering/20260430-m9-eval-system/blockers.md:215:### 確定アクション (ME-9 ADR で確定、本 incident block 期間中)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2778:.steering/20260430-m9-eval-system/blockers.md:251:**partial の取り扱い**: ME-9 ADR の通り primary 5 runs matrix から外す
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2780:.steering/20260430-m9-eval-system/blockers.md:254:`partial/censored` diagnostic 専用として `M9-A audit` 等に活用候補。
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2782:.steering/20260430-m9-eval-system/blockers.md:260:- **本タスク内 reopen 不要**: ME-9 ADR で確定、CLI fix は別タスクに切り出し
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2823:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2873:  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2824:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2875:  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2825:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2883:  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2827:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2941:  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2828:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2943:  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2829:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2951:  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2848:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:26:> 正しい運用は ME-9 ADR (`decisions.md`) と `cli-fix-and-audit-design.md` を
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2860:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:290:   < 500)、**600 min 最低ライン**。対処は ME-9 ADR の通り CLI fix + run1
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2861:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:292:   詳細: `decisions.md` ME-9 / `blockers.md` "active incident: Phase 2 run0
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2866:.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:10:> 行う。詳細は `decisions.md` ME-9、`blockers.md` "active incident: Phase 2
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2869:.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:44:cat .steering/20260430-m9-eval-system/decisions.md | grep -A 80 "^## ME-9"
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2901:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:3:> **scope**: 本ファイルは ME-9 ADR の design hand-off。**実装は本タスクで行わない**。
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2954:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:247:- ADR: `decisions.md` ME-9 (本 spec の確定 ADR)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:2955:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:261:4. ✅ `decisions.md` ME-9 ADR 追加
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3001:> (ME-9 ADR の hand-off。本 requirement はその実装側 task 起票で、spec を
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3006:Phase 2 run0 で 3 cell が wall=360 min で FAILED (focal=381/390/399 prefix
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3020:ME-9 ADR でこれらを (a) `eval_run_golden.py` の `soft_timeout` 分離 + sidecar
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3027:ME-9 ADR の実装を完了し、Phase 2 run1 calibration 着手のための前提
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3059:- HIGH-2 sample-size correction (ME-9 ADR で defer 確定、本タスク再採用しない)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3060:- Phase 2 run1 の実走 (本タスクは CLI / audit 整備のみ、実走は別タスク)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3061:- vLLM / SGLang LoRA 関連の改修 (M9-B 系統)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3062:- `eval_audit` の policy 拡張 (例: per-persona threshold) は M9 後に持ち越し
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3067:- [ ] `eval_run_golden.py` が ME-9 ADR の spec 通りに改修されている
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3087:- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3089:  Phase 2 run0 wall-timeout (2026-05-06)"
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3103:  - **複数案ありうる設計**: 案 A (soft_timeout 分離 + sidecar、ME-9 ADR の
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3109:# CLI Fix + Audit CLI 設計サマリ — Phase 2 run0 incident 対応
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3111:> **scope**: 本ファイルは ME-9 ADR の design hand-off。**実装は本タスクで行わない**。
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3118:Phase 2 run0 で 3 cell が wall=360 min で FAILED (focal=381/390/399 prefix
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3289:### 2.3 batch mode (Phase 2 全体 sweep)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3355:- ADR: `decisions.md` ME-9 (本 spec の確定 ADR)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3356:- incident: `blockers.md` "active incident: Phase 2 run0 wall-timeout (2026-05-06)"
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3394:  Phase 2 既存 30 cell との混在運用不可
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3398:詳細比較マトリクスは Plan agent 出力 (Phase 2) を `~/.claude/plans/sleepy-fluttering-lake.md`
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3469:- 不要 (CLI 単体タスク、Phase 2 run1 calibration は別タスク)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3503:- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3508:/bin/zsh -lc 'rg -n "''^## ME-9|partial masquerade|allow-partial-rescue|sample-size|eval_audit|soft_timeout|sidecar" .steering/20260430-m9-eval-system/decisions.md' in /Users/johnd/ERRE-Sand Box
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3511:566:## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3537:## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3557:  2. **Phase 2 採取戦略**:
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3601:    で収まらず M9 milestone 全体延伸過大
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3611:  - Phase 2 deadline 延伸 (推定 1-2 week、CLI fix PR + run1 calibration +
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3848:.steering/20260506-m9-eval-cli-partial-fix/requirement.md:65:- `eval_audit` の policy 拡張 (例: per-persona threshold) は M9 後に持ち越し
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3935:.steering/20260506-m9-eval-cli-partial-fix/_codex-review-cli-fix-transcript.log:3062:- `eval_audit` の policy 拡張 (例: per-persona threshold) は M9 後に持ち越し
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3951:.steering/20260506-m9-eval-cli-partial-fix/_codex-review-cli-fix-transcript.log:3508:/bin/zsh -lc 'rg -n "''^## ME-9|partial masquerade|allow-partial-rescue|sample-size|eval_audit|soft_timeout|sidecar" .steering/20260430-m9-eval-system/decisions.md' in /Users/johnd/ERRE-Sand Box
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3969:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2864:  Suggested fix: Catch `BurrowsTokenizationUnsupportedError` per utterance or pre-tokenize Japanese. Do not let Burrows failure skip MATTR. Also require `n_cells == 3` per condition for decision metrics.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3970:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2874:  Why it matters: The workflow can falsely close ME-4 from Burrows+MATTR even though Vendi and Big5 ICC are the ADR metrics.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3972:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2932:  Suggested fix: Catch `BurrowsTokenizationUnsupportedError` per utterance or pre-tokenize Japanese. Do not let Burrows failure skip MATTR. Also require `n_cells == 3` per condition for decision metrics.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3973:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2942:  Why it matters: The workflow can falsely close ME-4 from Burrows+MATTR even though Vendi and Big5 ICC are the ADR metrics.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:3979:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.md:33:[MEDIUM] M3: `eval_audit` が現 main に存在せず、Phase 2 検証手順が未実装
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:4096:.steering/20260430-m9-eval-system/codex-review.md:3768:- **Finding**: The design says `connect_training_view()` is the only training entry, but the current training export path already reads sqlite directly and is documented as consumed by M9 LoRA. Grep for `metrics.` misses quoted SQL, dynamic SQL, direct DuckDB connections, `read_parquet("...metrics...")`, and future Rust/Go tooling.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:4101:.steering/20260430-m9-eval-system/codex-review.md:3865:- **Finding**: The design says `connect_training_view()` is the only training entry, but the current training export path already reads sqlite directly and is documented as consumed by M9 LoRA. Grep for `metrics.` misses quoted SQL, dynamic SQL, direct DuckDB connections, `read_parquet("...metrics...")`, and future Rust/Go tooling.
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:4182:tests/test_evidence/test_eval_paths_contract.py:361:    """``erre-sandbox export-log`` is on the M9 training-egress path
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:4233:M8 L6-D1 sinks and emits a JSON document shaped for M9 LoRA comparison. The
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:4266:            "stable so M9 LoRA comparison runs can diff against it."
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:4549:        # Allow-list of paths that read raw_dialog for the LoRA
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:4942:rows as newline-delimited JSON. Consumed by the M9 LoRA training pipeline
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:4965:"""Formats accepted by ``--format``. Parquet joins this set in the M9 LoRA task."""
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:4975:            "newline-delimited JSON. Intended for M9 LoRA training-data "
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:4991:            "deferred to the M9 LoRA task (decisions D4)."
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:5084:  the DuckDB store, because the M9 LoRA training pipeline currently
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:5119:ALLOWED_SENTINEL = "M9_EVAL_SENTINEL_RAW_OK"
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:6030:    90	        # Allow-list of paths that read raw_dialog for the LoRA
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:6081:    24	  Phase 2 既存 30 cell との混在運用不可
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:6085:    28	詳細比較マトリクスは Plan agent 出力 (Phase 2) を `~/.claude/plans/sleepy-fluttering-lake.md`
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:6156:    99	- 不要 (CLI 単体タスク、Phase 2 run1 calibration は別タスク)
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:6190:   133	- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:6386:    15	  the DuckDB store, because the M9 LoRA training pipeline currently
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:6467:M9-B の `event_log` 追加が additive なら `extra="allow"` が最小コスト。semantics を変える場合だけ major version を導入する。C は現時点では重い。
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:6480:- Phase 2 run1 calibration 自体は本タスク外。
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:6545:M9-B の `event_log` 追加が additive なら `extra="allow"` が最小コスト。semantics を変える場合だけ major version を導入する。C は現時点では重い。
.steering/20260506-m9-eval-cli-partial-fix/codex-review-cli-fix.raw.log:6558:- Phase 2 run1 calibration 自体は本タスク外。
.steering/20260418-implementation-plan/requirement.md:30:- 本番構築版 (M4 / M5 / M7 / M9 / M10-11) の段階計画
.steering/20260425-m8-scaling-bottleneck-profiling/design.md:15:閾値案を確定する。M9 以降の 4th persona 起票は本 spike の閾値判定
.steering/20260418-implementation-plan/tasklist.md:69:### M9 — LoRA per persona (vLLM)
.steering/20260428-m9-lora-pre-plan/decisions.md:4:> 本文書は M9 着手前の意思決定を 5 ADR で確定する。実 LoRA training は含まない。
.steering/20260428-m9-lora-pre-plan/decisions.md:10:## D1. LoRA 適用 trigger 閾値
.steering/20260428-m9-lora-pre-plan/decisions.md:13:- **背景**: M9 で persona 別 LoRA fine-tuning に進むが、いつ適用するかの定量基準が
.steering/20260428-m9-lora-pre-plan/decisions.md:27:    連続 run で divergence 比率が flat 化したら LoRA 発火。turn 数は無関係扱い
.steering/20260428-m9-lora-pre-plan/decisions.md:36:    - **論理式**: `LoRA 発火 = (baseline floor 維持: self_rep ≤ 0.10 AND
.steering/20260428-m9-lora-pre-plan/decisions.md:49:- **トレードオフ**: v1 単独だと unreachable で M9 が永遠に着手できない。v2 単独だと
.steering/20260428-m9-lora-pre-plan/decisions.md:67:- **背景**: LoRA 適用時の base model / adapter rank / 訓練 dataset の構成を確定する
.steering/20260428-m9-lora-pre-plan/decisions.md:72:  並行して記録される。Parquet export は M9 scope に含まれる
.steering/20260428-m9-lora-pre-plan/decisions.md:91:      比較し、>2x 乖離が観測された時のみ rank 再配分 (M9 spike で実装)。
.steering/20260428-m9-lora-pre-plan/decisions.md:103:  r=8 → 観測後再配分 の段階方式は初期コストを抑える代わりに、最初の M9 run
.steering/20260428-m9-lora-pre-plan/decisions.md:107:  実装 (rank パラメータ受け入れ可能性)、PEFT vs unsloth 選定 spike (M9 内別 ADR)。
.steering/20260428-m9-lora-pre-plan/decisions.md:109:- **見直しタイミング**: M9 first run の loss curve で persona 間 >2x 乖離が
.steering/20260428-m9-lora-pre-plan/decisions.md:164:    +4% のみ) → 4th 投入は **保留**、M9 着手前に long-run で M3 再計測。
.steering/20260428-m9-lora-pre-plan/decisions.md:186:  済だが、M9 着手前に M11 開放条件と scope を確定する必要がある。
.steering/20260428-m9-lora-pre-plan/decisions.md:193:    evaluation) をそのまま M11 で全開放。M9 → M10 → M11 順序固定、
.steering/20260428-m9-lora-pre-plan/decisions.md:235:## D5. LoRA degradation rollback シナリオ
.steering/20260428-m9-lora-pre-plan/decisions.md:238:- **背景**: LoRA 適用後に persona quality が baseline より劣化した場合の
.steering/20260428-m9-lora-pre-plan/decisions.md:239:  rollback 手順が未定義。R12 (LoRA データ不足) と並ぶ M9 リスクだが、
.steering/20260428-m9-lora-pre-plan/decisions.md:247:    adapter ファイルを差し替えるだけ、base model は不変。発火条件は M9 run の
.steering/20260428-m9-lora-pre-plan/decisions.md:254:    「persona signature」として基準化し、LoRA 後にこの比率が崩れた (例:
.steering/20260428-m9-lora-pre-plan/decisions.md:265:      (M9 spike で確定)、両条件 → 人間裁定 → adapter unload。
.steering/20260428-m9-lora-pre-plan/decisions.md:275:  - **D1 との関係**: D1 の baseline floor (self_rep > 0.10 等) は **LoRA 適用
.steering/20260428-m9-lora-pre-plan/decisions.md:276:    gate** (適用前 reject)、D5 の baseline floor 超過は **LoRA 適用後の rollback
.steering/20260428-m9-lora-pre-plan/decisions.md:281:  signature divergence 閾値 (0.5) は 1 サンプル外挿で根拠が弱い。M9 spike で
.steering/20260428-m9-lora-pre-plan/decisions.md:285:  `m9-baseline-diff-runner` (新規 task 候補、baseline vs M9 run の diff 計測)、
.steering/20260428-m9-lora-pre-plan/decisions.md:288:- **見直しタイミング**: M9 first run 後、signature divergence 実測値が
.steering/20260425-m7-slice-gamma/design-final.md:112:## 採用しなかった v2 の細部 (M9+ で再検討)
.steering/20260428-m9-lora-pre-plan/tasklist.md:4:> 本タスクは documentation only。下記は M9 着手 prerequisites であり、
.steering/20260428-m9-lora-pre-plan/tasklist.md:19:## M9 着手 prerequisites (本 pre-plan で確定、別 task で実行)
.steering/20260428-m9-lora-pre-plan/tasklist.md:35:  M9 scope 確認済) [D2 hybrid]
.steering/20260428-m9-lora-pre-plan/tasklist.md:78:- [x] git commit (`docs(m9-pre-plan): 5 ADR with /reimagine v1+v2 hybrid for LoRA trigger / model / scaling / M11 / rollback`, commit 9989bf8)
.steering/20260430-m9-eval-system/design-final.md:56:   で **sentinel metric rows** (一意な文字列値、例 `"M9_EVAL_SENTINEL_*"`) を埋めた
.steering/20260430-m9-eval-system/design-final.md:89:- stylometric 一致は Burrows Delta (Tier A)
.steering/20260430-m9-eval-system/design-final.md:128:- 純 stimulus baseline は ζ 軸 (mode 遷移) を測れず M9-A event-boundary observability
.steering/20260430-m9-eval-system/design-final.md:238:  - `burrows.py` — **Burrows Delta** = z-scored function-word frequency vector の
.steering/20260430-m9-eval-system/design-final.md:264:  3 sub-metric quorum logic は decision layer (M9-C-adopt)。`numpy` + `arch`
.steering/20260430-m9-eval-system/design-final.md:335:**DB9 sub-metric 3 個 (Vendi / Big5 ICC / Burrows Delta) ready 時期**:
.steering/20260430-m9-eval-system/design-final.md:336:- Burrows: P1a 完了時 (per-turn computed)
.steering/20260430-m9-eval-system/design-final.md:338:- bootstrap CI 計算 ready: **P5 完了時 = タスク後半** (M9-C-adopt 直前)
.steering/20260430-m9-eval-system/design-final.md:419:3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260430-m9-eval-system/design-final.md:434:  Burrows Delta が persona-discriminative (Kant ≠ Nietzsche、distance 差 ≥ fixed delta)
.steering/20260430-m9-eval-system/design-final.md:440:### Burrows multi-lang (blockers.md 暫定方針)
.steering/20260430-m9-eval-system/design-final.md:489:3. **Burrows Delta multi-language reference の汚染** (blockers.md 既出)
.steering/20260430-m9-eval-system/design-final.md:497:   - 反復: P3b で pilot run 50 turn 両形式比較、Burrows / Vendi の bootstrap CI
.steering/20260430-m9-eval-system/design-final.md:514:| Burrows Delta = z-scored function-word L1 (cosine ではない) | HIGH-5 | design.md §burrows.py 定義 | ✅ 反映済 |
.steering/20260430-m9-eval-system/design-final.md:520:| Burrows token floor: corpus QC 化 (固定 50K → ≥5K-word chunk stability) | MEDIUM-6 | `decisions.md` ME-6 ADR / `blockers.md` reopen 条件 | ✅ ADR 化 |
.steering/20260430-m9-eval-system/design-final.md:555:  P1a (Tier A sub-module、Burrows は z-score Delta で実装) → P2c (external golden
.steering/20260430-m9-eval-system/design-final.md:573:  ("M9_EVAL_SENTINEL_*" 文字列) を埋めた fixture を追加、全 training egress 経路
.steering/20260430-m9-eval-system/design-final.md:601:**HIGH-5 反映** — Burrows Delta correction:
.steering/20260430-m9-eval-system/design-final.md:605:- DB9 quorum sub-metric の名称は "Burrows Delta" のまま (M9-B `decisions.md`
.steering/20260430-m9-eval-system/design-final.md:612:- DB1-DB10 の M9-B ADR との衝突: 無し
.steering/20260428-m9-lora-pre-plan/design.md:4:> 本タスクは documentation only。実 LoRA training・vLLM 起動・persona YAML 追加は
.steering/20260428-m9-lora-pre-plan/design.md:5:> 含まない。M9 着手の go/no-go 判断材料を 5 ADR + prerequisites として確定する。
.steering/20260428-m9-lora-pre-plan/design.md:10:**defer-and-measure** 哲学を M9 へ発展させ、5 つの決定 (LoRA trigger / model+rank+dataset
.steering/20260428-m9-lora-pre-plan/design.md:19:M9 は実投資コストが大きいため、起点 ADR で前提検証を二重化する。
.steering/20260428-m9-lora-pre-plan/design.md:30:- L6 ADR D1 (defer-and-measure) / D2 (3 metric trigger) / D3 (session_phase enum) の M9 接続
.steering/20260428-m9-lora-pre-plan/design.md:33:- 実 LoRA training 実行 (M9 本体: `m9-lora-training-pipeline` / `m9-lora-runtime-swap`)
.steering/20260428-m9-lora-pre-plan/design.md:35:- PEFT / unsloth tool 選定の commit (情報蓄積のみ、最終決定は M9 spike)
.steering/20260428-m9-lora-pre-plan/design.md:53:| `.steering/20260418-implementation-plan/MASTER-PLAN.md` L48, L146-147, L268, L393 | 推論 stack (vLLM+LoRA M9+), M8/M9 タスク定義, R12 (LoRA データ不足) | D1, D2 |
.steering/20260428-m9-lora-pre-plan/design.md:100:誤って M9 着手と読まれないよう冒頭 status 節に "PRE-PLAN — no execution" を明記
.steering/20260428-m9-lora-pre-plan/design.md:103:実 LoRA training は本 task の scope 外であるため、コード差分・モデル差分は発生
.steering/20260419-inference-ollama-adapter/decisions.md:26:  - RadixAttention の prefix KV 共有 (llm-inference Skill §ルール 2) は
.steering/20260419-inference-ollama-adapter/decisions.md:45:  「最初から拡張性のためだけに重い」、M9 まで未使用のフィールドを持つのは
.steering/20260428-m9-lora-pre-plan/requirement.md:1:# M9 LoRA pre-plan — 成長機構と適用 gate の設計
.steering/20260428-m9-lora-pre-plan/requirement.md:8:- D2 (04/22) 「全体のプランを練る (どれぐらいデータを集めたら LoRA を
.steering/20260428-m9-lora-pre-plan/requirement.md:12:揃った。M9 で persona ごとの LoRA fine-tuning に進むが、その前に「いつ・
.steering/20260428-m9-lora-pre-plan/requirement.md:13:何を・どうやって」LoRA を適用するかの意思決定文書が独立して存在しない。
.steering/20260428-m9-lora-pre-plan/requirement.md:19:M9 着手前に decisions.md に以下を記録:
.steering/20260428-m9-lora-pre-plan/requirement.md:20:- LoRA 適用 trigger 閾値 (episodic_log row 数 / dialog_turn 数 /
.steering/20260428-m9-lora-pre-plan/requirement.md:25:- LoRA degradation rollback シナリオ
.steering/20260428-m9-lora-pre-plan/requirement.md:36:- 実 LoRA training 実行 (M9 本体)
.steering/20260428-m9-lora-pre-plan/requirement.md:44:- [ ] tasklist.md に M9 着手の prerequisites 列挙
.steering/20260425-m7-slice-gamma/decisions.md:24:making the M9 ablation that swaps in a richer transcript inherently
.steering/20260425-m7-slice-gamma/decisions.md:128:**How to apply**: when δ or M9 introduces persona-pair-specific surfaces,
.steering/20260425-m7-slice-gamma/decisions.md:152:   evaluation methodology (D1/D2 trajectories vs LoRA), not the embodied
.steering/20260425-m7-slice-gamma/decisions.md:159:behaviour without anatomy, the deferral becomes M9+; if not, anatomy
.steering/20260425-m7-slice-gamma/decisions.md:290:  assumption** に依存しているが未文書化 (`world/tick.py:510`)。M9 並列処理導入で
.steering/20260430-m9-eval-system/decisions.md:5:各 ADR は M9-B `.steering/20260430-m9-b-lora-execution-plan/decisions.md` と同形式の
.steering/20260430-m9-eval-system/decisions.md:6:5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)。本 ADR set は M9-B DB1-DB10 と
.steering/20260430-m9-eval-system/decisions.md:10:ID prefix: `ME` (m9-Eval-system) で M9-B `DB` と区別。
.steering/20260430-m9-eval-system/decisions.md:139:    Burrows Delta + MATTR (lightweight) の CI を計算する経路を整備 (G-GEAR DuckDB の
.steering/20260430-m9-eval-system/decisions.md:146:  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/decisions.md:181:    ratio 実測 (本 update、Burrows + MATTR のみ) / (3) full ratio 実測 (P4 完了後、
.steering/20260430-m9-eval-system/decisions.md:189:      | Burrows Delta | 6.09 | 2.49 | **0.41** | 2 (kant+nietzsche) |
.steering/20260430-m9-eval-system/decisions.md:194:    - **方向性は両 metric で一致** (Burrows 0.41、MATTR 0.992 ≤ 1.0): natural narrower
.steering/20260430-m9-eval-system/decisions.md:196:    - **scale dominance caveat**: Burrows (~6.0 scale) が MATTR (~0.013 scale) を
.steering/20260430-m9-eval-system/decisions.md:197:      ~470x で支配しているため、combined ratio は実質 Burrows 単独の判定。per-metric
.steering/20260430-m9-eval-system/decisions.md:201:    - 根拠 1: target-extrapolated で natural が 41% (Burrows) / 99% (MATTR) — natural
.steering/20260430-m9-eval-system/decisions.md:212:      Rikyu Burrows は Japanese tokenizer 未実装で 2/3 persona のみ寄与 (n_cells=2)。
.steering/20260430-m9-eval-system/decisions.md:218:    - **m9-eval-corpus expansion**: rikyu Japanese tokenizer 実装 → Rikyu Burrows
.steering/20260430-m9-eval-system/decisions.md:224:    - 本 ADR は ME-4 §判定基準が指す **3 metric (Burrows / Vendi / Big5 ICC)**
.steering/20260430-m9-eval-system/decisions.md:225:      のうち 1/3 metric (Burrows、Rikyu 除く 2/3 persona) + lightweight proxy 1
.steering/20260430-m9-eval-system/decisions.md:235:      M9-D / M9-E (P4) のタスクリスト側で受け継ぐ
.steering/20260430-m9-eval-system/decisions.md:237:      script schema bump v1 → v3、`_KNOWN_LIMITATIONS` 経由で rikyu Burrows を
.steering/20260430-m9-eval-system/decisions.md:272:## ME-6 — Burrows reference corpus QC (Codex MEDIUM-6)
.steering/20260430-m9-eval-system/decisions.md:381:  - Option B (Kant のみ MCQ): per-persona stimulus mass 違いで Vendi/Burrows の
.steering/20260430-m9-eval-system/decisions.md:566:## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)
.steering/20260430-m9-eval-system/decisions.md:586:  2. **Phase 2 採取戦略**:
.steering/20260430-m9-eval-system/decisions.md:630:    で収まらず M9 milestone 全体延伸過大
.steering/20260430-m9-eval-system/decisions.md:640:  - Phase 2 deadline 延伸 (推定 1-2 week、CLI fix PR + run1 calibration +
.steering/20260430-m9-eval-system/decisions.md:656:rate=1.596/min ≈ 95.75/h) で **ME-9 trigger ≥80/h に該当**し、G-GEAR Claude が
.steering/20260430-m9-eval-system/decisions.md:687:budget を確定する流れで M9 Phase 2 を継続。
.steering/20260430-m9-eval-system/decisions.md:702:  LOW 1 / 2026-05-05 P3a-finalize HIGH 3 / MEDIUM 4 / LOW 4 / 2026-05-06 Phase 2
.steering/20260430-m9-eval-system/decisions.md:712:- 既存 M9-B DB1-DB10 ADR との衝突: 無し
.steering/20260419-m2-integration-e2e/integration-contract.md:180:- [ ] 複数インスタンスでのロードバランシング (M9 以降)
.steering/20260430-m9-eval-system/codex-review-prompt.md:19:2-of-3 quorum drift gate (M9-B ADR DB9). Its completion criterion is to take a
.steering/20260430-m9-eval-system/codex-review-prompt.md:21:Big5-ICC / Burrows-Delta have bootstrap CI ready (precondition for M9-C-adopt).
.steering/20260430-m9-eval-system/codex-review-prompt.md:34:   this task is expected to close (LIWC license, Burrows multi-lang, judge bias)
.steering/20260430-m9-eval-system/codex-review-prompt.md:59:## Required deliverables (HIGH / MEDIUM / LOW format, identical to M9-B review)
.steering/20260430-m9-eval-system/codex-review-prompt.md:113:   statistical power to detect a difference in bootstrap-CI width on Burrows
.steering/20260430-m9-eval-system/codex-review-prompt.md:118:5. **Burrows Delta multi-language reference: 50K token noise floor.** The
.steering/20260430-m9-eval-system/codex-review-prompt.md:144:- DB1-DB10 ADR set (M9-B `decisions.md`) — blocked from change in this review
.steering/20260430-m9-eval-system/design-v1.md:14:| P1 | Tier A 5 metric (Burrows / MATTR / novelty / NLI / LIWC-alt) | Claude | Mac | CPU + MPS (MPNet 推論) | 6h | unit test 緑 |
.steering/20260430-m9-eval-system/design-v1.md:21:| P6 | Tier C nightly infra (Prometheus 2 / G-Eval、agent 停止時) | Operator | **G-GEAR** | judge LLM (~24GB、agent 停止条件) | 4h (infra のみ、本番 run は M9-C-adopt) | runbook 草案 |
.steering/20260430-m9-eval-system/design-v1.md:71:- (3) Burrows のみは Big5 を諦めることになり DB9 sub-metric `big5_stability_icc` の
.steering/20260430-m9-eval-system/design-v1.md:102:- M9-eval-system では infra のみ実装、本番 run (Prometheus 2 / G-Eval / FANToM /
.steering/20260430-m9-eval-system/design-v1.md:103:  ROSCOE) は M9-C-adopt に移行
.steering/20260430-m9-eval-system/design-v1.md:169:  P6  Tier C nightly infra  ◄── 並行可、judgment 出力は M9-C-adopt
.steering/20260430-m9-eval-system/design-v1.md:173:**DB9 sub-metric 3 個 (Vendi / Big5 ICC / Burrows Delta) ready 時期**:
.steering/20260430-m9-eval-system/design-v1.md:174:- Burrows: P1 完了時 (per-turn computed)
.steering/20260430-m9-eval-system/design-v1.md:176:- bootstrap CI 計算 ready: **P5 完了時 = タスク後半 (M9-C-adopt 直前)**
.steering/20260430-m9-eval-system/design-v1.md:255:### Burrows multi-lang (blockers.md 暫定方針)
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md:177:| ε | per-dialog stylo signal を薄める (Burrows/MATTR の measurement 劣化) |
.steering/20260425-m7-slice-gamma/requirement.md:52:- LoRA による persona 分化 (L6 の scope、別 steering)
.steering/20260421-m5-cleanup-rollback-flags/requirement.md:5:M5 Phase 2 acceptance は **7/7 PASS** で完了、`v0.3.0-m5` タグ付与済
.steering/20260428-event-boundary-observability/design-final.md:53:- 既存 docstring (L73-129 付近の version notes) に M9-A entry 追記 (M7 系の最後の minor として 0.10.0-m7h 採番、M9 名前空間衝突を避ける)
.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:1:# G-GEAR セッション用プロンプト — Phase 2 run0 `.tmp` rescue verify
.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:7:> **本セッションは採取しない**。Phase 2 run0 で wall=360 min FAILED した
.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:10:> 行う。詳細は `decisions.md` ME-9、`blockers.md` "active incident: Phase 2
.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:17:タスク `20260430-m9-eval-system` の Phase 2 run0 wall-timeout incident の
.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:44:cat .steering/20260430-m9-eval-system/decisions.md | grep -A 80 "^## ME-9"
.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:51:Phase 2 採取時の output path は launch prompt 通り `data/eval/golden/` のはず
.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:86:# Phase 2 run0 の expected counts (Mac 側 incident report 由来)
.steering/20260419-inference-ollama-adapter/design-v1.md:114:| V1-W3 | `/api/generate` は単純 prompt 完結 mode。ペルソナ (system) + 観察 (user) の 2 メッセージ構造は `/api/chat` が本来の場所。system prompt を prompt 先頭に連結する ad-hoc 解では RadixAttention の prefix 共有 (llm-inference Skill) の恩恵を捨てる | 高 | Yes |
.steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md:1:# 重要な設計判断 — m9-eval ME-9 trigger 解釈タスク (旧称: cooldown-readjust-adr)
.steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md:6:> **ME-9 trigger basis 明示 (ADR amendment) + v2 prompt 擬陽性修正** に変更。
.steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md:36:### H1. ME-9 trigger の rate basis を分離 (single vs parallel-estimated)
.steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md:37:- **採用**: ADR (`decisions.md` ME-9) に **Amendment 2026-05-07** ブロックを
.steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md:94:- **ADR (`.steering/20260430-m9-eval-system/decisions.md` ME-9)**: Amendment
.steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md:109:- 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9 (本 PR で
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:9:> v1 (`g-gear-p3-launch-prompt.md`) は **Phase 2 run0 wall-timeout incident
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:11:> reference。本 v2 は ME-9 ADR (`decisions.md`) と PR #140 の新 contract
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:49:### 0.5 run1 calibration の制約 (ME-9 ADR より)
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:54:  (`decisions.md` ME-9 / 本タスク M1 採用)
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:60:   - **ME-9** (CLI fix + run1 calibration、本 v2 の権威 source)
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:128:ME-9 ADR の run1 calibration を **kant 1 persona × 5 wall endpoint** で実行
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:178:### A.4 期待値 table (saturation model、ME-9 Amendment 2026-05-07 反映)
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:196:**ME-9 trigger zone の rate basis は context-dependent** (ME-9 Amendment
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:254:| 0.92 | 0.523 | 1126 → **ME-9 re-open trigger** (§ブロッカー予測 C 案へ) |
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:326:### C.3 run0 partial の再採取 (§Phase 2 run0 incident 由来)
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:452:Refs: .steering/20260430-m9-eval-system/decisions.md ME-9
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:478:**ME-9 Amendment 2026-05-07 (`decisions.md` ME-9 末尾) で trigger zone を
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:569:- 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260419-inference-ollama-adapter/design-comparison.md:14:| **Ollama endpoint** | `/api/generate` (prompt 完結) | `/api/chat` (system + user messages) | **v2** (RadixAttention 前向き) |
.steering/20260424-steering-scaling-lora/decisions.md:6:## D1. LoRA による persona 分化 — defer-and-measure
.steering/20260424-steering-scaling-lora/decisions.md:9:  (`cognition/prompting.py:65-89`、`persona-erre` Skill L28-62)。LoRA 関連コード 0 件。
.steering/20260424-steering-scaling-lora/decisions.md:10:  M9 前提は ≥1000 turns/persona 対話ログ (MASTER-PLAN L146)、現 MVP は ~20 turns/persona。
.steering/20260424-steering-scaling-lora/decisions.md:11:- **選択肢**: A1-a 現状維持 / A1-b 全 persona LoRA / A1-c hybrid / A1-d 継続事前学習 /
.steering/20260424-steering-scaling-lora/decisions.md:14:- **採用**: architecture 確定は **M9 まで defer**。M8 では baseline 計測と
.steering/20260424-steering-scaling-lora/decisions.md:15:  episodic log pipeline 整備に専念、A1-a を暫定継続 (RadixAttention で KV prefix 共有)。
.steering/20260424-steering-scaling-lora/decisions.md:25:    すると baseline が常に 0.0 になり M9 比較が不能)
.steering/20260424-steering-scaling-lora/decisions.md:29:    実数に昇格。M9 LoRA 効果測定の追加 reference 軸として活用
.steering/20260424-steering-scaling-lora/decisions.md:30:  - M9 着手条件: baseline data (fidelity + bias_fired_rate 固定) + ≥500 turns/persona
.steering/20260424-steering-scaling-lora/decisions.md:31:    到達 (M9 前提 ≥1000 の緩和は別 ADR)。affinity は M9 着手の必須ではないが、
.steering/20260424-steering-scaling-lora/decisions.md:35:  Run 1 が M9 比較 reference)。詳細: `.steering/20260425-m7-beta-live-acceptance/baseline.md`。
.steering/20260424-steering-scaling-lora/decisions.md:39:    (n=12 turns では near-duplicate 検出するに corpus 不足、M9 同条件 run でも
.steering/20260424-steering-scaling-lora/decisions.md:43:  - **M9 比較準備完了**: 同 G-GEAR / qwen3:8b+LoRA / 3 persona / 80s / bias_p=0.1
.steering/20260424-steering-scaling-lora/decisions.md:44:    で `baseline-metrics` を回し、Run 1 と diff を取れば M9 着手判断可能
.steering/20260424-steering-scaling-lora/decisions.md:62:  - M9 着手条件: いずれかの metric が定量的に閾値超過、補完 persona 候補リストを起票
.steering/20260424-steering-scaling-lora/decisions.md:84:  - M9 着手条件: Q&A epoch prototype で MacBook↔G-GEAR 往復遅延 <500ms を達成
.steering/20260430-m9-eval-system/design-comparison.md:50:- **Tier A live per-turn** は M9 milestone の "drift gate を実行時に発火" の
.steering/20260430-m9-eval-system/design-comparison.md:64:  (M9-A event-boundary observability の latency 観測値による)
.steering/20260430-m9-eval-system/design-comparison.md:74:- **Hybrid baseline** は drift gate の baseline noise を統制、Burrows Delta /
.steering/20260430-m9-eval-system/design-comparison.md:93:  遅延 (この task scope では問題ないが、M9-C-adopt で live gate を作る時に
.steering/20260430-m9-eval-system/design-comparison.md:126:   - 理由: `tier_a.py` 1 file に 5 metric (Burrows / MATTR / NLI / novelty /
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:81:| **ε** | dialog_turn_budget を 6 → 3 に縮めて burst 期間を短縮、cooldown 計算根拠を変える | dialog 内 turn 数が減る、Burrows/MATTR の per-dialog stylo signal が薄まる |
.steering/20260430-m9-eval-system/pr-body-p3a.md:109:4. M9-B blockers の "Hybrid baseline 比率 200/300" 項目 close
.steering/20260430-m9-eval-system/design-natural-gating-fix.md:225:  scheduler は admit する。文体には影響あるが eval 目的 (Burrows / Vendi の
.steering/20260424-steering-scaling-lora/design.md:18:- **ADR の時制誤認**: v1 は "M8 で (c) hybrid LoRA 試作" のように *architecture を先取り commit* する採用を書いていた。M8+ の材料が目的なら、ADR は「先取り commit」ではなく「何を観測/測定したら commit 可能になるか」を書くべき。
.steering/20260424-steering-scaling-lora/design.md:29:- LoRA 関連コードは 0 件 (grep 済)。M9 roadmap 行 (`.steering/20260418-implementation-plan/MASTER-PLAN.md:146`) に "vLLM + LoRA per persona、M4-M7 の ≥1000 turns/persona 対話ログで訓練" とのみ。
.steering/20260424-steering-scaling-lora/design.md:33:- Prompt 合成: `cognition/prompting.py:65-89` が persona YAML + AgentState を system prompt に射影。RadixAttention 共有 prefix 最適化 (同 Skill L137-139)。
.steering/20260424-steering-scaling-lora/design.md:50:### Axis 1 — LoRA による persona 分化
.steering/20260424-steering-scaling-lora/design.md:54:| A1-a | prompt injection のみ維持 | 現状。RadixAttention で KV 共有し CPU/GPU コスト最小 |
.steering/20260424-steering-scaling-lora/design.md:55:| A1-b | persona ごとに LoRA adapter | M9 roadmap 済。1000 turns/persona の log が前提 |
.steering/20260424-steering-scaling-lora/design.md:56:| A1-c | 混合 (一部 persona のみ LoRA) | 非対称性が dialog scheduler と混乱。経年で不均衡が拡大 |
.steering/20260424-steering-scaling-lora/design.md:57:| A1-d | 継続事前学習 (全 persona まとめて 1 モデル微調整) | persona 分化は prompt に戻る、LoRA と排他ではない |
.steering/20260424-steering-scaling-lora/design.md:58:| A1-e | RAG (episodic memory から in-context 例示) | LoRA 不要、schema 変更最小、品質測定容易 |
.steering/20260424-steering-scaling-lora/design.md:59:| A1-f | instruction-tune (role-play fidelity 向上ベース) | LoRA の前段前処理、単独では分化効果が弱い |
.steering/20260424-steering-scaling-lora/design.md:93:1. **Episodic log 吸い上げ pipeline** — LoRA 訓練 (A1) にも、scaling 判定 metric (A2) にも、Q&A epoch の ground truth (A3) にも必要。
.steering/20260424-steering-scaling-lora/design.md:94:2. **Baseline quality metric** — prompt-only での会話 fidelity、bias 発火頻度、affinity 推移曲線。A1 の LoRA 後比較基準、A2 の scaling トリガー判定基準。
.steering/20260424-steering-scaling-lora/design.md:111:現状 M7 行と M9 行の間が空白。M8 を次のように追記:
.steering/20260424-steering-scaling-lora/design.md:114:| **M8** | 観察 → LoRA 判断の橋渡し spike | 
.steering/20260424-steering-scaling-lora/design.md:117:    L6 ADR 1/2/3 の preconditions を同時解決、M9 着手の go/no-go 判定材料 |
.steering/20260424-steering-scaling-lora/design.md:120:M9 行 (line ~146) には追記: "前提: L6 ADR1 の defer-and-measure 方針、M8 の baseline quality data".
.steering/20260424-steering-scaling-lora/design.md:135:**ADR 1 — LoRA による persona 分化 (defer-and-measure)**
.steering/20260424-steering-scaling-lora/design.md:136:- 現状: qwen3:8b + prompt injection、LoRA コード 0 件、M9 前提 ≥1000 turns/persona 未達
.steering/20260424-steering-scaling-lora/design.md:138:- 採用: **architecture 確定は M9 まで defer、M8 では baseline 計測と episodic log pipeline 整備のみ**
.steering/20260424-steering-scaling-lora/design.md:139:- 根拠: 現 MVP データ量不足、A1-b/c/d/e の比較は baseline 無しでは判断不能。A1-a を暫定継続するコスト小 (RadixAttention 効率)
.steering/20260424-steering-scaling-lora/design.md:140:- 次アクション: M8 spike `m8-episodic-log-pipeline` + `m8-baseline-quality-metric` を起票、M9 着手前に A1-a/b/c/d/e の比較評価を実施
.steering/20260424-steering-scaling-lora/design.md:147:- 次アクション: `m8-scaling-bottleneck-profiling` で metric 候補を 3 本提案、各閾値を live data で確定、超過確認後 M9 で +1 persona 候補リスト起票
.steering/20260424-steering-scaling-lora/design.md:158:- M9 行に前提追記
.steering/20260424-steering-scaling-lora/design.md:164:- `gh pr create`、title `docs(steering): L6 — scaling / LoRA / user-dialogue IF roadmap`
.steering/20260424-steering-scaling-lora/design.md:176:| `.steering/20260418-implementation-plan/MASTER-PLAN.md` | 既存編集 (M8 行追加、M9 前提追記) | ~6 行差分 |
.steering/20260428-event-boundary-observability/design.md:180:  2. `summary` 文字列で因果が text 化され、ref_id 単独より読める (M9 LoRA pre-plan 「推奨第 1 候補」の研究 observatory 価値に直結)
.steering/20260430-m9-eval-system/blockers.md:6:defer 期限と reopen 条件を明示。M9-B 親タスクの blockers (`.steering/20260430-m9-b-lora-execution-plan/blockers.md`)
.steering/20260430-m9-eval-system/blockers.md:28:  Vendi/Burrows の persona 横比較を交絡、Option C は persona-factuality 軸を消す。
.steering/20260430-m9-eval-system/blockers.md:51:### LIWC license 評価 (M9-B blockers から継承、本タスクで close 候補)
.steering/20260430-m9-eval-system/blockers.md:53:- **issue**: M9-B `blockers.md` の "LIWC 商用 license の最終可否判定"
.steering/20260430-m9-eval-system/blockers.md:56:- **defer 先**: 本タスク P0a で M9-B blockers.md を Edit して "Option D 採用" 記載
.steering/20260430-m9-eval-system/blockers.md:61:### Burrows corpus license (Cambridge Edition / Kaufmann translation 等)
.steering/20260430-m9-eval-system/blockers.md:75:  下記 "Burrows reference corpus — English translations defer" で independent
.steering/20260430-m9-eval-system/blockers.md:78:### Burrows reference corpus — English translations defer (2026-05-01 P1b 開設)
.steering/20260430-m9-eval-system/blockers.md:86:  - 独原典のみで Burrows 経路を回し、対話が英語に流れた場合は
.steering/20260430-m9-eval-system/blockers.md:87:    `BurrowsLanguageMismatchError` で明示 fail (silent fallback 禁止)
.steering/20260430-m9-eval-system/blockers.md:98:### Burrows reference corpus — toy-scale corpus expansion (2026-05-01 P1b 開設)
.steering/20260430-m9-eval-system/blockers.md:117:### Burrows Delta multi-lang reference の閾値 (M9-B blockers から継承)
.steering/20260430-m9-eval-system/blockers.md:125:### Judge bias mitigation runbook (M9-B blockers から継承)
.steering/20260430-m9-eval-system/blockers.md:128:- **暫定方針** (M9-B 既出):
.steering/20260430-m9-eval-system/blockers.md:159:| Burrows corpus license (independent) | Cambridge / Kaufmann PD edition 確認 | m9-eval-corpus |
.steering/20260430-m9-eval-system/blockers.md:160:| Burrows en translations defer | PD 英訳 edition 入手 | m9-eval-corpus / 後続 |
.steering/20260430-m9-eval-system/blockers.md:161:| Burrows toy-scale expansion | Akademie-Ausgabe 全文 / 利休関連 PD 大規模 | m9-eval-corpus |
.steering/20260430-m9-eval-system/blockers.md:162:| Burrows chunk stability (Nietzsche) | rank instability 検出 (現状 ρ=1.0 PASS) | golden baseline 採取後 |
.steering/20260430-m9-eval-system/blockers.md:167:## active incident: Phase 2 run0 wall-timeout (2026-05-06)
.steering/20260430-m9-eval-system/blockers.md:171:P3 production 採取の Phase 2 run0 (3-parallel: kant + nietzsche + rikyu, natural
.steering/20260430-m9-eval-system/blockers.md:215:### 確定アクション (ME-9 ADR で確定、本 incident block 期間中)
.steering/20260430-m9-eval-system/blockers.md:230:**source path**: `data/eval/golden/` (Phase 2 採取時の output 先)
.steering/20260430-m9-eval-system/blockers.md:251:**partial の取り扱い**: ME-9 ADR の通り primary 5 runs matrix から外す
.steering/20260430-m9-eval-system/blockers.md:254:`partial/censored` diagnostic 専用として `M9-A audit` 等に活用候補。
.steering/20260430-m9-eval-system/blockers.md:260:- **本タスク内 reopen 不要**: ME-9 ADR で確定、CLI fix は別タスクに切り出し
.steering/20260430-m9-eval-system/blockers.md:271:- 不適切なら DB9 sub-metric を Tier A 系に入れ替え検討 (M9-B `blockers.md` の
.steering/20260430-m9-eval-system/codex-review-prompt-natural-gating.md:187:- LoRA training (M9-B) interaction — orthogonal milestone
.steering/20260430-m9-eval-system/codex-review-prompt-natural-gating.md:190:- M9-A event boundary observability — already merged
.steering/20260424-steering-scaling-lora/requirement.md:1:# L6 — Scaling / LoRA / User-Dialogue IF Roadmap
.steering/20260424-steering-scaling-lora/requirement.md:6:で決定: "L6 (LoRA / scaling / user-dialogue IF) は別 steering で並行起票、
.steering/20260424-steering-scaling-lora/requirement.md:13:1. **LoRA による persona 分化** — 今は 1 base model + prompt injection で
.steering/20260424-steering-scaling-lora/requirement.md:14:   3 agent を区別しているが、persona ごとに LoRA adapter を焼いた場合の
.steering/20260430-m9-eval-system/codex-review-natural-gating.raw.log:200:- LoRA training (M9-B) interaction — orthogonal milestone
.steering/20260430-m9-eval-system/codex-review-natural-gating.raw.log:203:- M9-A event boundary observability — already merged
.steering/20260430-m9-eval-system/codex-review-natural-gating.raw.log:585:        # sqlite for later LoRA-training export. Left None for unit tests
.steering/20260430-m9-eval-system/codex-review-natural-gating.raw.log:1610:M9-A bump (0.9.0-m7z → 0.10.0-m7h): one additive nested field tied to the
.steering/20260430-m9-eval-system/codex-review-natural-gating.raw.log:1626:chronology readable; the M9 namespace is reserved for the LoRA work.
.steering/20260430-m9-eval-system/codex-review-natural-gating.raw.log:2530:   117	        # sqlite for later LoRA-training export. Left None for unit tests
.steering/20260428-event-boundary-observability/observation.md:1:# Live G-GEAR observation — event-boundary-observability (M9-A)
.steering/20260428-event-boundary-observability/observation.md:243:- PR #118 (M9-A feature) https://github.com/mikotomiura/ERRE-Sandbox/pull/118
.steering/20260430-m9-eval-system/g-gear-p3a-prompt.md:20:- P1a-b: tier_a/ 5 metric (Burrows Delta z-score L1 / MATTR / NLI / novelty /
.steering/20260430-m9-eval-system/g-gear-p3a-prompt.md:191:#   - utterance 文字数 mean/median (Burrows / Vendi の input volume 確認)
.steering/20260430-m9-eval-system/g-gear-p3a-prompt.md:249:- `M9-A` 完了履歴: `.steering/20260428-event-boundary-observability/` (G-GEAR 実機検収の前例、PR #117-#124)
.steering/20260424-steering-scaling-lora/design-v1.md:1:# Plan — L6 ADR Roadmap (Scaling / LoRA / User-Dialogue IF)
.steering/20260424-steering-scaling-lora/design-v1.md:8:M7 Slice β が main に merge された直後 (PR #83, commit `a76343c`, 2026-04-24)。親タスク `20260424-m7-differentiation-observability` の decisions D2 により、L6 (LoRA / agent scaling / user-dialogue IF) は **コード作業と戦略文書を混ぜない** ために別 steering として並走起票される運びとなった。現状 M8+ の意思決定材料が存在せず、γ 着手時に「何故この schema/輪郭か」の参照が欠落する。本タスクでこの gap を埋め、M8 以降の spike task が preconditions を持って起票できる状態にする。
.steering/20260424-steering-scaling-lora/design-v1.md:24:- `llm-inference` Skill (`.claude/skills/llm-inference/SKILL.md`) を Read、VRAM 予算 (~13GB/16GB on RTX 5060 Ti) と M9 前提を把握
.steering/20260424-steering-scaling-lora/design-v1.md:33:  - MASTER-PLAN への影響 (M8 行追加、M9 LoRA 前提の再確認)
.steering/20260424-steering-scaling-lora/design-v1.md:39:**ADR 1 — LoRA による persona 分化**
.steering/20260424-steering-scaling-lora/design-v1.md:40:- 現状: `qwen3:8b` 1 base + prompt injection (`cognition/prompting.py:65-89`) で 3 persona 分化。LoRA への参照はコードゼロ、MASTER-PLAN.md:146 で M9 (vLLM + `--enable-lora`) 目標。
.steering/20260424-steering-scaling-lora/design-v1.md:41:- 選択肢: (a) 現状維持 (b) persona ごとに LoRA (c) hybrid — 高分散 persona のみ LoRA、他 prompt
.steering/20260424-steering-scaling-lora/design-v1.md:43:- 根拠: LoRA 学習には ≥1000 turns/persona が必要 (MASTER-PLAN M9 行)。現 MVP は ~20 turns/persona、M4-M7 の live log で調達可能。prompt injection は RadixAttention (`cognition/prompting.py:6`) で KV prefix 共有でき現状コスト小、LoRA swap 実装は M9 adapter pipeline に委譲
.steering/20260424-steering-scaling-lora/design-v1.md:44:- 次アクション: M8 spike task "LoRA training cost benchmark" の preconditions (DPO ペア抽出、adapter hot-swap 遅延測定) を列挙
.steering/20260424-steering-scaling-lora/design-v1.md:61:- `.steering/20260418-implementation-plan/MASTER-PLAN.md` に **M8 行を追加** (現状 M7 と M9 の間が空白)。内容: M8 = "hybrid LoRA spike + 4th agent onboarding + user-dialogue IF contract"、前提に本 L6 ADR 3 本を参照
.steering/20260424-steering-scaling-lora/design-v1.md:62:- M9 LoRA 行 (line ~146) に "前提: L6 ADR1 採用 (c) hybrid、M8 spike 結果" を追記
.steering/20260424-steering-scaling-lora/design-v1.md:70:- `gh pr create` — title: `docs(steering): L6 — scaling / LoRA / user-dialogue IF roadmap`
.steering/20260424-steering-scaling-lora/design-v1.md:80:| `.steering/20260418-implementation-plan/MASTER-PLAN.md` | 既存編集 (M8 行追加、M9 前提追記、L6 milestone 行) |
.steering/20260424-steering-scaling-lora/design-v1.md:86:- M9 LoRA 前提: `.steering/20260418-implementation-plan/MASTER-PLAN.md` L146 付近
.steering/20260430-m9-eval-system/tasklist.md:16:## Phase 2 (Implementation) — 順次・依存順
.steering/20260430-m9-eval-system/tasklist.md:20:- [x] [Mac] **P0a** — LIWC Option D 確定 → M9-B `blockers.md` の "LIWC license" 項目を
.steering/20260430-m9-eval-system/tasklist.md:35:    - [x] sentinel "M9_EVAL_SENTINEL_LEAK_*" rows fixture (raw_dialog + metrics 両方に
.steering/20260430-m9-eval-system/tasklist.md:79:        `BurrowsReference` / `BurrowsLanguageMismatchError`)
.steering/20260430-m9-eval-system/tasklist.md:81:        (Codex HIGH-5)。`BurrowsReference` frozen dataclass、per-language
.steering/20260430-m9-eval-system/tasklist.md:140:        本セッションでは扱わず** blockers.md "Burrows reference corpus —
.steering/20260430-m9-eval-system/tasklist.md:153:        BurrowsReference` + `available_personas()` + provenance
.steering/20260430-m9-eval-system/tasklist.md:333:    - [x] `scripts/p3a_decide.py` drafted: stimulus 3 cell の Burrows Delta + MATTR
.steering/20260430-m9-eval-system/tasklist.md:387:    - [x] HIGH-2 (Rikyu silent abort): `BurrowsTokenizationUnsupportedError` を
.steering/20260430-m9-eval-system/tasklist.md:389:          回避。real run で発覚した「Rikyu Burrows 完全 skip」シナリオは
.steering/20260430-m9-eval-system/tasklist.md:400:          - Burrows Delta extrap: stim=6.09 / nat=2.49 / **ratio=0.41** (n_cells=2)
.steering/20260430-m9-eval-system/tasklist.md:402:          - combined extrap ratio: 0.41 (Burrows scale-dominant、方向性は両 metric 一致)
.steering/20260430-m9-eval-system/tasklist.md:408:    - [ ] M9-B `blockers.md` の "Hybrid baseline 比率 200/300" 項目を close
.steering/20260430-m9-eval-system/tasklist.md:409:          (現状 M9-B blockers.md には該当項目なし。本セッションでは追加せず、
.steering/20260430-m9-eval-system/tasklist.md:410:          ratio 確定時に M9-B 側へ通知 / 必要なら起票)
.steering/20260430-m9-eval-system/tasklist.md:443:  - [ ] 3 sub-metric (Vendi / Big5 ICC / Burrows Delta) の CI 計算 ready
.steering/20260430-m9-eval-system/tasklist.md:463:  - [ ] judge bias mitigation runbook 起草 (M9-B blockers から継承、本タスクで close)
.steering/20260430-m9-eval-system/tasklist.md:468:- [ ] [Mac] DB9 sub-metric 3 個 (Vendi / Big5 ICC / Burrows Delta) の bootstrap CI
.steering/20260430-m9-eval-system/tasklist.md:472:      LoRA training / M9-C-spike 混入無し)
.steering/20260430-m9-eval-system/tasklist.md:482:- Burrows corpus license: P1b 着手時に edition 採否
.steering/20260430-m9-eval-system/tasklist.md:502:solo cadence で **3-4 calendar weeks**、M9 milestone delay は M9-B 計画の
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:1:# Codex Independent Review — Phase 2 run0 wall-timeout incident
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:5:m9-eval-system Phase 2 run0 で 3 cell (kant / nietzsche / rikyu) すべてが
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:8:Phase 2 残りの budget 戦略を立てたが、過去にも線形外挿で empirical を
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:39:Phase 2 では `--wall-timeout-min 360` を G-GEAR 側で override していた。
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:129:  の前提 (Burrows scale-dominant) はこの範囲で valid か?
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:136:- (g) run0 救出を採用すると Phase 2 の "5 runs × 3 personas × 2 conditions"
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:195:### 4. Phase 2 残り 4 runs の budget 戦略
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:221:  と、Phase 2 で必要な 8h は 4x の乖離。design-natural-gating-fix-v2.md
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:234:1-2 日遅延する。Phase 2 全体の deadline は明記されていない (m9-b LoRA
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:235:は M9 milestone 内、Phase 2 は eval foundation)。
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:253:  (Phase 2 launch 仕様)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:14:# Codex Independent Review Prompt — m9-eval ME-9 trigger interpretation (run1 cell 100/101)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:26:本タスク (`20260507-m9-eval-cooldown-readjust-adr`) は M9-eval Phase 2 run1
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:27:calibration 実行中に **ME-9 trigger** が発火し、その解釈に rate basis 不整合
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:181:- (A) ADR (`decisions.md` ME-9) を amendment block で rate basis 明示 +
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:530:/bin/zsh -lc 'rg -n "ME-9|run1 calibration|65|55|80|ブロッカー予測|Phase A|focal/min|COOLDOWN" .steering/20260430-m9-eval-system .steering/20260507-m9-eval-cooldown-readjust-adr' in /Users/johnd/ERRE-Sand Box
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:532:.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-prompt-trigger-interpretation.md:1:# Codex Independent Review Prompt — m9-eval ME-9 trigger interpretation (run1 cell 100/101)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:533:.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-prompt-trigger-interpretation.md:14:calibration 実行中に **ME-9 trigger** が発火し、その解釈に rate basis 不整合
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:558:.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-prompt-trigger-interpretation.md:168:- (A) ADR (`decisions.md` ME-9) を amendment block で rate basis 明示 +
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:590:.steering/20260430-m9-eval-system/blockers.md:215:### 確定アクション (ME-9 ADR で確定、本 incident block 期間中)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:592:.steering/20260430-m9-eval-system/blockers.md:251:**partial の取り扱い**: ME-9 ADR の通り primary 5 runs matrix から外す
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:593:.steering/20260430-m9-eval-system/blockers.md:260:- **本タスク内 reopen 不要**: ME-9 ADR で確定、CLI fix は別タスクに切り出し
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:603:.steering/20260430-m9-eval-system/decisions.md:566:## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:613:.steering/20260430-m9-eval-system/decisions.md:640:  - Phase 2 deadline 延伸 (推定 1-2 week、CLI fix PR + run1 calibration +
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:669:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:24:> **本 prompt の §Phase 2 採取と §ブロッカー予測 item 2 は不正確** (wall=360 を
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:671:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:26:> 正しい運用は ME-9 ADR (`decisions.md`) と `cli-fix-and-audit-design.md` を
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:673:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:55:> v2 は ME-9 ADR の run1 calibration (kant only × 5 wall sequential、
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:676:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:210:`m9-eval-cli-partial-fix` (ME-9 ADR、CLI fix PR 適用後) で実装された
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:677:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:244:# `data/eval/partial/` 隔離の運用は ME-9 ADR どおり。
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:684:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:343:   < 500)、**600 min 最低ライン**。対処は ME-9 ADR の通り CLI fix + run1
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:685:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:345:   詳細: `decisions.md` ME-9 / `blockers.md` "active incident: Phase 2 run0
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:688:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:11:> reference。本 v2 は ME-9 ADR (`decisions.md`) と PR #140 の新 contract
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:692:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:49:### 0.5 run1 calibration の制約 (ME-9 ADR より)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:693:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:54:  (`decisions.md` ME-9 / 本タスク M1 採用)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:694:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:60:   - **ME-9** (CLI fix + run1 calibration、本 v2 の権威 source)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:697:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:128:ME-9 ADR の run1 calibration を **kant 1 persona × 5 wall endpoint** で実行
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:706:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:236:| 0.92 | 0.523 | 1126 → **ME-9 re-open trigger** (§ブロッカー予測 C 案へ) |
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:716:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:434:Refs: .steering/20260430-m9-eval-system/decisions.md ME-9
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:720:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:458:### B-1. run1 calibration で observed focal/min が ME-9 re-open trigger に該当 (≤55/h ≈ 0.92/min または ≥80/h ≈ 1.33/min)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:721:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:461:720 min 強行 (旧案 A) は ME-9 re-open trigger を空文化するため禁止 (Codex
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:726:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:515:- 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:727:.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:10:> 行う。詳細は `decisions.md` ME-9、`blockers.md` "active incident: Phase 2
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:728:.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md:44:cat .steering/20260430-m9-eval-system/decisions.md | grep -A 80 "^## ME-9"
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:834:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1042:   380	          ratio 確定時に M9-B 側へ通知 / 必要なら起票)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:856:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1790:   180	            f"Burrows reference language {reference.language!r} does not"
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:859:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1996:   255	def load_reference(persona_id: str, language: str) -> BurrowsReference:
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:900:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:3:> **scope**: 本ファイルは ME-9 ADR の design hand-off。**実装は本タスクで行わない**。
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:902:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:247:- ADR: `decisions.md` ME-9 (本 spec の確定 ADR)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:903:.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:261:4. ✅ `decisions.md` ME-9 ADR 追加
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:949:.steering/20260430-m9-eval-system/codex-review-low1.md:2312:   155	  - M9-B / M9-eval-system 期間は N=3 の divergence 漸近線 + 評価系構築が優先
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1004:.steering/20260430-m9-eval-system/codex-review.md:1209:    65	  - LoRA adapter format は SGLang 互換に変換が必要
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1006:.steering/20260430-m9-eval-system/codex-review.md:1299:   155	  - M9-B / M9-eval-system 期間は N=3 の divergence 漸近線 + 評価系構築が優先
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1471:The cited wording exists in both the active prompt and ME-9 ADR, and the branch has untracked steering/data artifacts as expected. Next I’m narrowing to exact line ranges plus the sidecar JSONs so the verdict rests on the repository data, not just the prompt summary.
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1477:   566	## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1497:   586	  2. **Phase 2 採取戦略**:
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1541:   630	    で収まらず M9 milestone 全体延伸過大
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1551:   640	  - Phase 2 deadline 延伸 (推定 1-2 week、CLI fix PR + run1 calibration +
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1574:     9	> v1 (`g-gear-p3-launch-prompt.md`) は **Phase 2 run0 wall-timeout incident
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1576:    11	> reference。本 v2 は ME-9 ADR (`decisions.md`) と PR #140 の新 contract
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1614:    49	### 0.5 run1 calibration の制約 (ME-9 ADR より)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1619:    54	  (`decisions.md` ME-9 / 本タスク M1 採用)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1625:    60	   - **ME-9** (CLI fix + run1 calibration、本 v2 の権威 source)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1693:   128	ME-9 ADR の run1 calibration を **kant 1 persona × 5 wall endpoint** で実行
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1801:   236	| 0.92 | 0.523 | 1126 → **ME-9 re-open trigger** (§ブロッカー予測 C 案へ) |
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1854:   236	| 0.92 | 0.523 | 1126 → **ME-9 re-open trigger** (§ブロッカー予測 C 案へ) |
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:1926:   308	### C.3 run0 partial の再採取 (§Phase 2 run0 incident 由来)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2001:   160	| Burrows en translations defer | PD 英訳 edition 入手 | m9-eval-corpus / 後続 |
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2002:   161	| Burrows toy-scale expansion | Akademie-Ausgabe 全文 / 利休関連 PD 大規模 | m9-eval-corpus |
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2003:   162	| Burrows chunk stability (Nietzsche) | rank instability 検出 (現状 ρ=1.0 PASS) | golden baseline 採取後 |
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2008:   167	## active incident: Phase 2 run0 wall-timeout (2026-05-06)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2012:   171	P3 production 採取の Phase 2 run0 (3-parallel: kant + nietzsche + rikyu, natural
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2056:   215	### 確定アクション (ME-9 ADR で確定、本 incident block 期間中)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2071:   230	**source path**: `data/eval/golden/` (Phase 2 採取時の output 先)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2451:/bin/zsh -lc "rg -n \"ブロッカー予測|observed focal/min|0\\.92|1\\.33|C 案|ME-9 re-open\" .steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md" in /Users/johnd/ERRE-Sand Box
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2453:236:| 0.92 | 0.523 | 1126 → **ME-9 re-open trigger** (§ブロッカー予測 C 案へ) |
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2455:458:### B-1. run1 calibration で observed focal/min が ME-9 re-open trigger に該当 (≤55/h ≈ 0.92/min または ≥80/h ≈ 1.33/min)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2457:461:720 min 強行 (旧案 A) は ME-9 re-open trigger を空文化するため禁止 (Codex
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2480:   458	### B-1. run1 calibration で observed focal/min が ME-9 re-open trigger に該当 (≤55/h ≈ 0.92/min または ≥80/h ≈ 1.33/min)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2483:   461	720 min 強行 (旧案 A) は ME-9 re-open trigger を空文化するため禁止 (Codex
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2542:.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-prompt-trigger-interpretation.md:1:# Codex Independent Review Prompt — m9-eval ME-9 trigger interpretation (run1 cell 100/101)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2544:.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-prompt-trigger-interpretation.md:14:calibration 実行中に **ME-9 trigger** が発火し、その解釈に rate basis 不整合
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2597:.steering/20260507-m9-eval-phase2-run1-calibration-prompt/decisions.md:59:### M1. 5 wall sequential は ME-9 の "single 600 min cell" から実質変更
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2605:.steering/20260507-m9-eval-phase2-run1-calibration-prompt/decisions.md:107:| Q5 ME-9 re-open trigger 連動 | C (Codex review/child ADR)、720 強行は trigger 空文化 | 採用 (v2 prompt §ブロッカー予測で明記) |
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2610:.steering/20260507-m9-eval-phase2-run1-calibration-prompt/decisions.md:126:- **§ブロッカー予測**: ME-9 re-open trigger (focal/h ≤55 / ≥80) で **C 案
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2611:.steering/20260507-m9-eval-cooldown-readjust-adr/requirement.md:6:> 完了時点で **ME-9 trigger** に該当し、G-GEAR Claude が正規 STOP。
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2651:.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:165:### Q5. ME-9 re-open 条件との連動
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2653:.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-prompt-run1-calibration.md:169:run1 で observed focal/min が 0.92 (≤55/h、ME-9 re-open trigger 該当) を
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2661:.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.md:24:### M1. 5 wall sequential は ME-9 の “single 600 min cell” から実質変更
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2667:.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.md:61:ME-9 re-open trigger に当たるなら、default は停止して Codex review/child ADR。720 min 強行は「re-open 条件」を空文化する。D は review 後の暫定運用案としてなら可。
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2669:.steering/20260507-m9-eval-phase2-run1-calibration-prompt/blockers.md:35:### D-4. ME-9 re-open trigger 該当時の child ADR 起票
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2704:.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md:130:5. **ME-9 re-open 条件との連動**: run1 で observed focal/min が 0.92 (≤55/h)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2705:.steering/20260507-m9-eval-phase2-run1-calibration-prompt/requirement.md:15:ME-9 ADR は run1 を「kant のみ 1 cell × wall 600 min single calibration」で
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2715:- 解釈 A の妥当性: 強い。ME-9 ADR の根拠は run0 3-parallel `≈65/h` で、ADR も run0 観測を根拠にしている。`run1` は [ME-9 ADR](/Users/johnd/ERRE-Sand%20Box/.steering/20260430-m9-eval-system/decisions.md:586) で single と明記されるため、basis 混在がある。
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2733:実作業は A: ME-9 ADR amendment block で rate basis 明示、v2 prompt B-1 refresh。PR の結論は C: wording 修正のみで完結し、cooldown 再調整は defer。
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2736:### H1. ME-9 trigger の rate basis を分離
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2772:- 解釈 A の妥当性: 強い。ME-9 ADR の根拠は run0 3-parallel `≈65/h` で、ADR も run0 観測を根拠にしている。`run1` は [ME-9 ADR](/Users/johnd/ERRE-Sand%20Box/.steering/20260430-m9-eval-system/decisions.md:586) で single と明記されるため、basis 混在がある。
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2790:実作業は A: ME-9 ADR amendment block で rate basis 明示、v2 prompt B-1 refresh。PR の結論は C: wording 修正のみで完結し、cooldown 再調整は defer。
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.raw.log:2793:### H1. ME-9 trigger の rate basis を分離
.steering/20260424-steering-scaling-lora/design-comparison.md:7:tasklist.md にプリセットされた暫定採用 (ADR1=hybrid LoRA / ADR2=4th persona / ADR3=user-as-special-agent) をそのまま ADR 化するプラン。design.md は「ADR の書き方メタ」(~50 行) として位置付け、decisions.md に 5 節 ≤20 行で 3 ADR を書き下す流れ。MASTER-PLAN は M8 行追加と M9 前提追記。Plan agent 省略、/reimagine も省略。
.steering/20260424-steering-scaling-lora/design-comparison.md:17:| ADR の時制 | "M8 で (c) hybrid LoRA 試作" = architecture 先取り | "M8 で baseline 計測、M9 まで architecture 判断 defer" |
.steering/20260424-steering-scaling-lora/design-comparison.md:20:| ADR 1 採用 | (c) hybrid LoRA 試作 | defer-and-measure (M9 まで判断先送り) |
.steering/20260424-steering-scaling-lora/design-comparison.md:26:| MASTER-PLAN M8 行 | "hybrid LoRA spike + 4th agent onboarding + user-dialogue IF contract" | "観察 → LoRA 判断の橋渡し spike" (判断素材収集が主) |
.steering/20260424-steering-scaling-lora/design-comparison.md:29:| リスク | architecture 先取り commit で M9 の選択肢を早期に縮退 | docs 量が増える (1-2h の時間制約を圧迫する可能性) |
.steering/20260424-steering-scaling-lora/design-comparison.md:39:- **architecture 先取り**: M9 の判断を M8 に前倒し、データ無しで LoRA の hybrid/full/none を選ぶ構造に。データが出た後に覆ると ADR 全体が再執筆対象に。
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:426:ff29ca2 docs(steering): m9-b LoRA execution plan — v3 hybrid 確定 (codex review 反映 + 第 3 の道採用) (#127)
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:482:.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md:81:| **ε** | dialog_turn_budget を 6 → 3 に縮めて burst 期間を短縮、cooldown 計算根拠を変える | dialog 内 turn 数が減る、Burrows/MATTR の per-dialog stylo signal が薄まる |
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:849:.steering/20260430-m9-eval-system/decisions.md:209:## ME-6 — Burrows reference corpus QC (Codex MEDIUM-6)
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:1423:    81	| **ε** | dialog_turn_budget を 6 → 3 に縮めて burst 期間を短縮、cooldown 計算根拠を変える | dialog 内 turn 数が減る、Burrows/MATTR の per-dialog stylo signal が薄まる |
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:1653:   177	| ε | per-dialog stylo signal を薄める (Burrows/MATTR の measurement 劣化) |
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:1999:   318	  - Option B (Kant のみ MCQ): per-persona stimulus mass 違いで Vendi/Burrows の
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:2119:   438	- 既存 M9-B DB1-DB10 ADR との衝突: 無し
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:2239:   117	        # sqlite for later LoRA-training export. Left None for unit tests
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:4089:   195	    # Phase 2: STUDY is now rejected again (natural-dialog rules restored).
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:4717:   562	        possible (M7γ-out-of-scope) deregistration. Future M9+ removal
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:4724:   569	        # If M9 introduces parallel cognition cycles or external mutators
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:5850:   177	| ε | per-dialog stylo signal を薄める (Burrows/MATTR の measurement 劣化) |
.steering/20260424-steering-scaling-lora/tasklist.md:1:# Tasklist — L6 Steering (LoRA / Scaling / User-Dialogue IF)
.steering/20260424-steering-scaling-lora/tasklist.md:35:- [x] **D1. LoRA による persona 分化 — defer-and-measure**
.steering/20260424-steering-scaling-lora/tasklist.md:36:  - architecture 確定は M9 まで defer、M8 では baseline 計測と log pipeline
.steering/20260424-steering-scaling-lora/tasklist.md:47:- [x] M8 行を追加 (M7 と M9 の間の空白を埋める)
.steering/20260424-steering-scaling-lora/tasklist.md:48:- [x] M9 行に L6 ADR1 defer-and-measure 前提を追記
.steering/20260424-steering-scaling-lora/tasklist.md:58:- [ ] `gh pr create`、title `docs(steering): L6 — scaling / LoRA / user-dialogue IF roadmap`
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.md:33:[MEDIUM] M3: `eval_audit` が現 main に存在せず、Phase 2 検証手順が未実装
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:38:3. Recognize that ME-4's `判定基準` references **3 metrics** (Burrows Delta /
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:39:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:83:where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:109:> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:115:- Uses Burrows Delta + **MATTR** (not in ADR), defers Vendi + Big5 ICC.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:127:  verdict carry an additional disclaimer that Burrows + MATTR may
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:128:  produce a different ratio than Burrows + Vendi + Big5 ICC?
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:511:    17	   Burrows Delta per-utterance against the persona's own reference, MATTR
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:518:    24	5. Aggregates mean CI width per condition across personas (Burrows + MATTR)
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:556:    62	    BurrowsLanguageMismatchError,
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:602:   108	    """Compute Burrows Delta for each utterance against the persona reference.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:604:   110	    Returns a list of floats; entries that raise BurrowsLanguageMismatchError
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:624:   130	        except BurrowsLanguageMismatchError:
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:668:   174	    # Burrows Delta — per-utterance values, bootstrap on the per-utterance vector.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:799:   301	    Only the lightweight Tier A metrics (Burrows Delta + MATTR) are
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:995:   333	    - [x] `scripts/p3a_decide.py` drafted: stimulus 3 cell の Burrows Delta + MATTR
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1037:   375	    - [ ] Burrows Delta / Vendi / Big5 ICC の CI width 比較
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1040:   378	    - [ ] M9-B `blockers.md` の "Hybrid baseline 比率 200/300" 項目を close
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1041:   379	          (現状 M9-B blockers.md には該当項目なし。本セッションでは追加せず、
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1042:   380	          ratio 確定時に M9-B 側へ通知 / 必要なら起票)
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1060:   139	    Burrows Delta + MATTR (lightweight) の CI を計算する経路を整備 (G-GEAR DuckDB の
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1067:   146	  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1290:     6	The persona-discriminative claim in the M9 design is that thinkers
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1322:    38	            baseline metric and the M9 Tier A metric line up at the
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1611:     1	"""Burrows Delta — z-scored function-word L1 (Manhattan) distance.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1615:     5	not the Burrows Delta family. The canonical R-stylo formulation
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1627:    17	:class:`BurrowsReference` and compare an incoming test text against it.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1629:    19	:class:`BurrowsLanguageMismatchError` (per ``blockers.md`` "Burrows
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1660:    50	class BurrowsLanguageMismatchError(ValueError):
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1670:    60	class BurrowsTokenizationUnsupportedError(NotImplementedError):
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1681:    71	class BurrowsReference:
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1682:    72	    """Per-language Burrows reference profile.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1702:    92	    P1a tests, callers build a small synthetic ``BurrowsReference``
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1720:   110	                "BurrowsReference vectors must have equal length;"
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1737:   127	    Japanese routes through :class:`BurrowsTokenizationUnsupportedError`
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1742:   132	        raise BurrowsTokenizationUnsupportedError(
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1743:   133	            f"Burrows Delta default tokenizer does not support language"
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1755:   145	    reference: BurrowsReference,
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1760:   150	    """Burrows Delta = sum of absolute z-score differences (L1 distance).
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1767:   157	            ``language`` or :class:`BurrowsLanguageMismatchError` is raised.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1784:   174	        BurrowsLanguageMismatchError: When ``language != reference.language``.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1785:   175	        BurrowsTokenizationUnsupportedError: When ``language`` has no
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1789:   179	        raise BurrowsLanguageMismatchError(
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1790:   180	            f"Burrows reference language {reference.language!r} does not"
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1892:A concrete implementation risk surfaced: `rikyu` is mapped to `ja`, while the Burrows implementation explicitly rejects Japanese unless pre-tokenized. Because `main()` catches cell-level exceptions and continues, this can quietly drop entire Rikyu cells and still produce a ratio from the remaining cells.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1996:   255	def load_reference(persona_id: str, language: str) -> BurrowsReference:
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:1997:   256	    """Hydrate a frozen :class:`BurrowsReference` for the given pair.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2005:   264	        A frozen :class:`BurrowsReference` ready to be passed to
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2018:   277	    return BurrowsReference(
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2077:3. Recognize that ME-4's `判定基準` references **3 metrics** (Burrows Delta /
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2078:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2122:where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2148:> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2154:- Uses Burrows Delta + **MATTR** (not in ADR), defers Vendi + Big5 ICC.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2188:3. Recognize that ME-4's `判定基準` references **3 metrics** (Burrows Delta /
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2189:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2233:where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2260:3. Recognize that ME-4's `判定基準` references **3 metrics** (Burrows Delta /
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2261:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2305:where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2331:> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2337:- Uses Burrows Delta + **MATTR** (not in ADR), defers Vendi + Big5 ICC.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2371:3. Recognize that ME-4's `判定基準` references **3 metrics** (Burrows Delta /
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2372:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2416:where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2486:     1	"""Tier A psycholinguistic metrics for the M9 evaluation system.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2514:    29	    BurrowsLanguageMismatchError,
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2515:    30	    BurrowsReference,
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2524:    39	    "BurrowsLanguageMismatchError",
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2525:    40	    "BurrowsReference",
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2753:     5	"violence", ...). The M9 design uses Empath as **one Tier A axis**
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2861:- HIGH-2: Rikyu Burrows can abort whole cells
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2862:  Issue: `_PERSONA_LANGUAGE["rikyu"] = "ja"`, but Burrows rejects Japanese without pre-tokenized input. `_per_utterance_burrows()` only catches `BurrowsLanguageMismatchError` in [scripts/p3a_decide.py](</Users/johnd/ERRE-Sand Box/scripts/p3a_decide.py:127>), so `BurrowsTokenizationUnsupportedError` propagates to `main()` and turns the entire Rikyu cell into `"error"`, losing MATTR too.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2864:  Suggested fix: Catch `BurrowsTokenizationUnsupportedError` per utterance or pre-tokenize Japanese. Do not let Burrows failure skip MATTR. Also require `n_cells == 3` per condition for decision metrics.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2873:  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2874:  Why it matters: The workflow can falsely close ME-4 from Burrows+MATTR even though Vendi and Big5 ICC are the ADR metrics.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2875:  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2879:  Why it matters: Burrows+MATTR may produce a different ratio than Burrows+Vendi+Big5.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2883:  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2889:  Why it matters: Optional diagnostics should not invalidate Burrows+MATTR finalization.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2929:- HIGH-2: Rikyu Burrows can abort whole cells
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2930:  Issue: `_PERSONA_LANGUAGE["rikyu"] = "ja"`, but Burrows rejects Japanese without pre-tokenized input. `_per_utterance_burrows()` only catches `BurrowsLanguageMismatchError` in [scripts/p3a_decide.py](</Users/johnd/ERRE-Sand Box/scripts/p3a_decide.py:127>), so `BurrowsTokenizationUnsupportedError` propagates to `main()` and turns the entire Rikyu cell into `"error"`, losing MATTR too.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2932:  Suggested fix: Catch `BurrowsTokenizationUnsupportedError` per utterance or pre-tokenize Japanese. Do not let Burrows failure skip MATTR. Also require `n_cells == 3` per condition for decision metrics.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2941:  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2942:  Why it matters: The workflow can falsely close ME-4 from Burrows+MATTR even though Vendi and Big5 ICC are the ADR metrics.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2943:  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2947:  Why it matters: Burrows+MATTR may produce a different ratio than Burrows+Vendi+Big5.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2951:  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2957:  Why it matters: Optional diagnostics should not invalidate Burrows+MATTR finalization.
.steering/20260428-event-boundary-observability/run-02-debug-trace/godot-output.log:13:#       spatial 3/3 で pulse_zone START 到達、temporal 2/2 は正しく drop。視覚目視も OK。**M9-A V3/V4 全 PASS**。
.steering/20260430-m9-eval-system/codex-review-step1-prompt.md:28:  - `evidence/tier_a/` 5 metric (Burrows z-score Delta L1 / MATTR / NLI /
.steering/20260430-m9-eval-system/codex-review-step1-prompt.md:183:   The ratio decision is bootstrap CI WIDTH on Burrows/Vendi/ICC, where
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-prompt-trigger-interpretation.md:1:# Codex Independent Review Prompt — m9-eval ME-9 trigger interpretation (run1 cell 100/101)
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-prompt-trigger-interpretation.md:13:本タスク (`20260507-m9-eval-cooldown-readjust-adr`) は M9-eval Phase 2 run1
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-prompt-trigger-interpretation.md:14:calibration 実行中に **ME-9 trigger** が発火し、その解釈に rate basis 不整合
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-prompt-trigger-interpretation.md:168:- (A) ADR (`decisions.md` ME-9) を amendment block で rate basis 明示 +
.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:1:# CLI Fix + Audit CLI 設計サマリ — Phase 2 run0 incident 対応
.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:3:> **scope**: 本ファイルは ME-9 ADR の design hand-off。**実装は本タスクで行わない**。
.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:10:Phase 2 run0 で 3 cell が wall=360 min で FAILED (focal=381/390/399 prefix
.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:181:### 2.3 batch mode (Phase 2 全体 sweep)
.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:247:- ADR: `decisions.md` ME-9 (本 spec の確定 ADR)
.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:248:- incident: `blockers.md` "active incident: Phase 2 run0 wall-timeout (2026-05-06)"
.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:261:4. ✅ `decisions.md` ME-9 ADR 追加
.steering/20260430-m9-eval-system/codex-review-step1.md:14:It collapses Kant’s pilot to Wachsmuth-only, so the “stimulus” condition no longer represents the planned 70-item mix. Vendi/Burrows CI width is prompt-genre sensitive, so category mix is not secondary here. Do not use `cycle_count=2`; it breaks the 200-vs-200 pilot symmetry.  
.steering/20260507-m9-eval-cooldown-readjust-adr/design.md:1:# 設計 — m9-eval ME-9 trigger 解釈 (旧称: cooldown-readjust-adr)
.steering/20260507-m9-eval-cooldown-readjust-adr/design.md:13:1. **ADR (`.steering/20260430-m9-eval-system/decisions.md` ME-9)** に
.steering/20260507-m9-eval-cooldown-readjust-adr/design.md:29:- `.steering/20260430-m9-eval-system/decisions.md` — ME-9 末尾に Amendment
.steering/20260507-m9-eval-cooldown-readjust-adr/design.md:51:- **ME-9 ADR**: 旧 re-open 条件 (≤55/h / ≥80/h trigger) は Amendment で
.steering/20260507-m9-eval-cooldown-readjust-adr/design.md:65:  本 ADR (ME-9) も末尾に追記方式
.steering/20260507-m9-eval-cooldown-readjust-adr/design.md:75:- markdownlint: 修正後の v2 prompt + decisions.md ME-9 で MD022/MD032 警告
.steering/20260507-m9-eval-cooldown-readjust-adr/design.md:93:| H1 (rate basis 分離) | ME-9 Amendment table + v2 §B-1 table | trigger zone が context-dependent |
.steering/20260507-m9-eval-cooldown-readjust-adr/design.md:110:- 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9 (本 PR で
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:14:# Codex Independent Review — Phase 2 run0 wall-timeout incident
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:18:m9-eval-system Phase 2 run0 で 3 cell (kant / nietzsche / rikyu) すべてが
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:21:Phase 2 残りの budget 戦略を立てたが、過去にも線形外挿で empirical を
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:52:Phase 2 では `--wall-timeout-min 360` を G-GEAR 側で override していた。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:142:  の前提 (Burrows scale-dominant) はこの範囲で valid か?
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:149:- (g) run0 救出を採用すると Phase 2 の "5 runs × 3 personas × 2 conditions"
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:208:### 4. Phase 2 残り 4 runs の budget 戦略
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:234:  と、Phase 2 で必要な 8h は 4x の乖離。design-natural-gating-fix-v2.md
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:247:1-2 日遅延する。Phase 2 全体の deadline は明記されていない (m9-b LoRA
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:248:は M9 milestone 内、Phase 2 は eval foundation)。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:266:  (Phase 2 launch 仕様)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:1495:   239	    (RadixAttention prefix sharing across personas + a single-turn cue).
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:2093:   562	        possible (M7γ-out-of-scope) deregistration. Future M9+ removal
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:2100:   569	        # If M9 introduces parallel cognition cycles or external mutators
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:2852:    38	3. Recognize that ME-4's `判定基準` references **3 metrics** (Burrows Delta /
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:2853:    39	   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:2897:    83	where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:2923:   109	> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:2929:   115	- Uses Burrows Delta + **MATTR** (not in ADR), defers Vendi + Big5 ICC.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:2941:   127	  verdict carry an additional disclaimer that Burrows + MATTR may
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:2942:   128	  produce a different ratio than Burrows + Vendi + Big5 ICC?
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3081:     5	各 ADR は M9-B `.steering/20260430-m9-b-lora-execution-plan/decisions.md` と同形式の
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3082:     6	5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)。本 ADR set は M9-B DB1-DB10 と
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3086:    10	ID prefix: `ME` (m9-Eval-system) で M9-B `DB` と区別。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3215:   139	    Burrows Delta + MATTR (lightweight) の CI を計算する経路を整備 (G-GEAR DuckDB の
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3222:   146	  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3257:   181	    ratio 実測 (本 update、Burrows + MATTR のみ) / (3) full ratio 実測 (P4 完了後、
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3265:   189	      | Burrows Delta | 6.09 | 2.49 | **0.41** | 2 (kant+nietzsche) |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3270:   194	    - **方向性は両 metric で一致** (Burrows 0.41、MATTR 0.992 ≤ 1.0): natural narrower
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3272:   196	    - **scale dominance caveat**: Burrows (~6.0 scale) が MATTR (~0.013 scale) を
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3273:   197	      ~470x で支配しているため、combined ratio は実質 Burrows 単独の判定。per-metric
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3277:   201	    - 根拠 1: target-extrapolated で natural が 41% (Burrows) / 99% (MATTR) — natural
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3288:   212	      Rikyu Burrows は Japanese tokenizer 未実装で 2/3 persona のみ寄与 (n_cells=2)。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3294:   218	    - **m9-eval-corpus expansion**: rikyu Japanese tokenizer 実装 → Rikyu Burrows
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3300:   224	    - 本 ADR は ME-4 §判定基準が指す **3 metric (Burrows / Vendi / Big5 ICC)**
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3301:   225	      のうち 1/3 metric (Burrows、Rikyu 除く 2/3 persona) + lightweight proxy 1
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3311:   235	      M9-D / M9-E (P4) のタスクリスト側で受け継ぐ
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3313:   237	      script schema bump v1 → v3、`_KNOWN_LIMITATIONS` 経由で rikyu Burrows を
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3469:   127	### Phase 2 — natural 全 15 cell (3-persona parallel × 5 run、~24-30h)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3781:   177	| ε | per-dialog stylo signal を薄める (Burrows/MATTR の measurement 劣化) |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3910:83:where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3920:109:> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3983:518:    24	5. Aggregates mean CI width per condition across personas (Burrows + MATTR)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4063:1037:   375	    - [ ] Burrows Delta / Vendi / Big5 ICC の CI width 比較
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4064:1040:   378	    - [ ] M9-B `blockers.md` の "Hybrid baseline 比率 200/300" 項目を close
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4065:1041:   379	          (現状 M9-B blockers.md には該当項目なし。本セッションでは追加せず、
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4067:1067:   146	  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4125:1629:    19	:class:`BurrowsLanguageMismatchError` (per ``blockers.md`` "Burrows
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4159:2122:where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4169:2148:> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4178:2233:where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4188:2305:where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4198:2331:> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4207:2416:where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4525:   479	      Burrows is known-skipped because the Japanese tokenizer is not
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4575:  2861	- HIGH-2: Rikyu Burrows can abort whole cells
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4576:  2862	  Issue: `_PERSONA_LANGUAGE["rikyu"] = "ja"`, but Burrows rejects Japanese without pre-tokenized input. `_per_utterance_burrows()` only catches `BurrowsLanguageMismatchError` in [scripts/p3a_decide.py](</Users/johnd/ERRE-Sand Box/scripts/p3a_decide.py:127>), so `BurrowsTokenizationUnsupportedError` propagates to `main()` and turns the entire Rikyu cell into `"error"`, losing MATTR too.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4578:  2864	  Suggested fix: Catch `BurrowsTokenizationUnsupportedError` per utterance or pre-tokenize Japanese. Do not let Burrows failure skip MATTR. Also require `n_cells == 3` per condition for decision metrics.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4587:  2873	  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4588:  2874	  Why it matters: The workflow can falsely close ME-4 from Burrows+MATTR even though Vendi and Big5 ICC are the ADR metrics.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4589:  2875	  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4593:  2879	  Why it matters: Burrows+MATTR may produce a different ratio than Burrows+Vendi+Big5.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4597:  2883	  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4603:  2889	  Why it matters: Optional diagnostics should not invalidate Burrows+MATTR finalization.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4732:   405	    Only the lightweight Tier A metrics (Burrows Delta + MATTR) are
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4765:   479	      Burrows is known-skipped because the Japanese tokenizer is not
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4830:   544	    **warnings** (documented library limitations such as rikyu Burrows
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4927:   636	                "update** of ME-4 (Burrows Delta + MATTR), not a final close."
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4972:    17	   Burrows Delta per-utterance against the persona's own reference, MATTR
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5026:    71	    BurrowsLanguageMismatchError,
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5030:    75	from erre_sandbox.evidence.tier_a.burrows import BurrowsTokenizationUnsupportedError
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5070:   107	# captures the Burrows Delta Japanese tokenizer gap: ``compute_burrows_delta``
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5071:   108	# raises ``BurrowsTokenizationUnsupportedError`` for any rikyu utterance
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5074:   111	# lightweight partial update of ME-4 with Burrows scoped to (kant,
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5078:   115	        "BurrowsTokenizationUnsupportedError — Japanese tokenizer not "
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5096:scripts/p3a_decide.py:111:# lightweight partial update of ME-4 with Burrows scoped to (kant,
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5279:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2873:  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5280:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2875:  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5281:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2883:  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5287:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2941:  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5288:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2943:  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5289:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2951:  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5628:.steering/20260430-m9-eval-system/codex-review-prompt.md:34:   this task is expected to close (LIWC license, Burrows multi-lang, judge bias)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5775:.steering/20260430-m9-eval-system/codex-review.md:47:   this task is expected to close (LIWC license, Burrows multi-lang, judge bias)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5927:/bin/zsh -lc 'rg -n "phase2|Phase 2|golden|run0|partial|timeout|focal=|focal_rows|1158|381|390|399" .steering data scripts src tests -S' in /Users/johnd/ERRE-Sand Box
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5934:scripts/p3a_decide.py:111:# lightweight partial update of ME-4 with Burrows scoped to (kant,
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5997:data/eval/pilot/_p3a_decide.json:289:      "Vendi Score and Big5 ICC are deferred to P4. This Mac session can therefore only deliver a **lightweight partial update** of ME-4 (Burrows Delta + MATTR), not a final close.",
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6111:src/erre_sandbox/integration/gateway.py:591:        # ---------- Phase 2: ACTIVE ----------
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6230:.steering/20260419-gateway-fastapi-ws/design.md:43:        # ---- Phase 2: ACTIVE -----------------------------------------
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6259:tests/test_integration/test_dialog_golden_baseline_mode.py:195:    # Phase 2: STUDY is now rejected again (natural-dialog rules restored).
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6288:.steering/_verify-report-20260429.md:20:| — | Phase 2 (新規 marketplace) | ❌ skip — `docs/external-skills.md` 不在 |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6289:.steering/_verify-report-20260429.md:21:| Phase 2 | Phase 3 | ✅ 完了 — ただし `docs/agent-shared.md` 不在 |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6290:.steering/_verify-report-20260429.md:34:### Phase 2: Marketplace ❌ SKIPPED (新仕様)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6291:.steering/_verify-report-20260429.md:51:- 公式 Skill 重複回避: 検証不能 (Phase 2 skip により真実源なし)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6292:.steering/_verify-report-20260429.md:129:1. **`docs/external-skills.md` が存在しない** — Phase 2 (marketplace) を skip した結果。Phase 4 で「公式 Skill 重複回避」検証ができない
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6293:.steering/_verify-report-20260429.md:153:- 差分の主因: 新仕様で Phase 2 (Marketplace) と Phase 5 (Codex Bridge) が追加され、本リポはその仕様パスを採用していない (=skip + 代替レイアウト) ため、検証項目が増えて差分が表面化した
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6301:.steering/20260419-gateway-fastapi-ws/tasklist.md:40:  - Phase 2 ACTIVE: per-client queue 作成 → registry.add → TaskGroup で
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6309:.steering/_verify-report-20260418.md:26:### Phase 2: CLAUDE.md ✅
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6312:.steering/20260421-m5-erre-sampling-override-live/requirement.md:80:- `.steering/20260420-m5-planning/design.md` §Phase 2 並列 4 本
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6325:.steering/20260430-m9-b-lora-execution-plan/design-final.md:233:| **eval ready** | golden baseline 採取 (3 persona × 5 run × 500 turn) + Tier B (Vendi+ICC) 実装完了 | LoRA adoption 判断 enabled |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6339:.steering/20260428-codex-review-followup/decisions.md:102:- **次アクション**: `tasklist.md` Phase 2 完了。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6341:.steering/20260430-m9-b-lora-execution-plan/design-v2.md:133:- baseline は J6 で採取する pre-LoRA golden baseline (M9-eval-system 成果物)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6342:.steering/20260430-m9-b-lora-execution-plan/design-v2.md:139:### J. 思想家らしさ評価系 framework → **M9-B 内で Tier A 完全実装 + Tier B 半分実装 + golden baseline 採取**
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6344:.steering/20260430-m9-b-lora-execution-plan/design-v2.md:170:- M9-B 内: Tier A 全実装 + Tier B のうち Vendi Score + Big Five stability ICC 実装 + golden baseline 採取の準備
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6345:.steering/20260430-m9-b-lora-execution-plan/design-v2.md:171:- M9-eval-system: Tier B 完全実装 (Prometheus 2 rubric / FANToM-adapted / FActScore-adapted) + 専門家 review pipeline + golden set 採取
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6346:.steering/20260430-m9-b-lora-execution-plan/design-v2.md:174:取り込み、golden baseline を積極採取する。LoRA 適用判断は J 軸完成後
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6347:.steering/20260430-m9-b-lora-execution-plan/design-v2.md:185:| 評価系 ready | golden baseline 採取完了 + Tier B Vendi+ICC 実装完了 | LoRA 適用判断 enabled |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6423:.steering/20260421-m5-godot-schema-version-bump/requirement.md:17:schema_version 更新だけが M5 Phase 2 で漏れていた**。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6427:.steering/20260430-m9-b-lora-execution-plan/requirement.md:87:2. 評価系の実装 (judge prompt / golden set / 自動化 dashboard) → M9-eval-system
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6431:.steering/20260428-codex-review-followup/tasklist.md:19:### Phase 2: F6 (frame byte limit)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6462:.steering/20260430-m9-b-lora-execution-plan/blockers.md:99:- **再評価条件**: M9-eval-system Tier B 実装完了後の golden baseline 採取で discriminative 確認、
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6463:.steering/20260430-m9-b-lora-execution-plan/blockers.md:114:| Tier B sub-metric 3 | golden baseline 採取 | M9-eval-system 終盤 |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6464:.steering/20260421-m5-orchestrator-integration/decisions.md:3:本タスクで採用した設計判断とその根拠。M5 Phase 2 の最後の 2 タスク
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6486:.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:22:| **J. 評価系** | framework 宣言のみ | Tier A 完全実装 + Tier B 半実装 + golden baseline | **v2 採用**: M9-B の deliverable を評価系に再定義 |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6487:.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:54:| 評価系 ready | golden baseline 採取完了 + Tier B (Vendi + Big5 ICC) 実装完了 | LoRA 適用判断 enabled |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6492:.steering/20260430-m9-b-lora-execution-plan/design-comparison.md:110:3. golden set 整備を M9-eval-system に含めることの工数見積り (現実的か)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6498:.steering/20260430-m9-b-lora-execution-plan/tasklist.md:145:1. M9-eval-system 完了 (golden baseline + Tier B 実装)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6501:.steering/20260420-m4-cognition-reflection/tasklist.md:10:## Phase 2: branch & 実装
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6506:.steering/20260421-m5-orchestrator-integration/requirement.md:5:M5 Phase 2 の前段 3 タスク (PR #58 FSM wire / PR #60 sampling delta / PR #61 dialog
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6508:.steering/20260421-m5-orchestrator-integration/requirement.md:17:7 項目 PASS/FAIL を判定できる状態にする。これは M5 Phase 2 の critical path 上
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6533:.steering/20260421-m5-acceptance-live/acceptance.md:35:**7 項目すべて PASS**。M5 Phase 2 の本番 wire (FSM + sampling delta + dialog turn generator + orchestrator integration + Godot visuals) が実機 LLM 経路 + MacBook viewer の両方で意図通り動作することを確認した。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6534:.steering/20260421-m5-acceptance-live/acceptance.md:117:したが、Godot 側 constant は **M5 Phase 2 全体で更新が漏れていた**
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6554:.steering/20260421-m5-acceptance-live/requirement.md:5:M5 Phase 2 の 7 本の PR (#56 contracts-freeze / #57 fsm / #58 world-zone-triggers /
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6560:.steering/20260425-m8-session-phase-model/tasklist.md:18:- [ ] **Phase 2**: session_phase の所在を AgentState vs BootConfig で決定
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6571:.steering/20260421-m5-dialog-turn-generator/decisions.md:11:- **背景**: `.steering/20260420-m5-planning/design.md` §Phase 2 / §LLM プロンプト設計方針 では
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6579:.steering/20260421-m5-dialog-turn-generator/requirement.md:5:M5 Phase 2 の並列 4 本のうち、LLM 対話生成の**核心タスク**。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6580:.steering/20260421-m5-dialog-turn-generator/requirement.md:14:- `.steering/20260420-m5-planning/design.md` §Phase 2 / §LLM プロンプト設計方針
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6583:.steering/20260421-m5-dialog-turn-generator/requirement.md:124:- `.steering/20260420-m5-planning/design.md` §Phase 2 / §LLM プロンプト設計方針 (上位設計)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6592:.steering/20260421-m5-cleanup-rollback-flags/requirement.md:5:M5 Phase 2 acceptance は **7/7 PASS** で完了、`v0.3.0-m5` タグ付与済
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6593:.steering/20260425-m8-baseline-quality-metric/tasklist.md:26:### Phase 2: sink 注入 (cognition + bootstrap)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6620:.steering/20260430-m9-eval-system/design-final.md:555:  P1a (Tier A sub-module、Burrows は z-score Delta で実装) → P2c (external golden
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6791:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2873:  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6792:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2875:  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6793:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2883:  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6795:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2941:  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6796:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2943:  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6797:.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md:2951:  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6846:.steering/20260430-m9-eval-system/codex-review.md:1512:    92	- **再評価条件**: M9-eval-system Tier B 実装完了後の golden baseline 採取で discriminative 確認、
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6847:.steering/20260430-m9-eval-system/codex-review.md:1527:   107	| Tier B sub-metric 3 | golden baseline 採取 | M9-eval-system 終盤 |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6884:.steering/20260420-m5-godot-zone-visuals/tasklist.md:26:## 実装 — Phase 2: BodyTinter + DialogBubble
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6911:.steering/20260420-m5-godot-zone-visuals/requirement.md:5:M5 Phase 2 の並列 4 本のうち MacBook 側担当。G-GEAR が LLM/FSM 3 本
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6912:.steering/20260420-m5-godot-zone-visuals/requirement.md:71:- `.steering/20260420-m5-planning/tasklist.md` §Phase 2 並列 4 本
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6913:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:1:# Codex Independent Review — Phase 2 run0 wall-timeout incident
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6914:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:5:m9-eval-system Phase 2 run0 で 3 cell (kant / nietzsche / rikyu) すべてが
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6916:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:8:Phase 2 残りの budget 戦略を立てたが、過去にも線形外挿で empirical を
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6921:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:39:Phase 2 では `--wall-timeout-min 360` を G-GEAR 側で override していた。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6934:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:136:- (g) run0 救出を採用すると Phase 2 の "5 runs × 3 personas × 2 conditions"
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6951:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:195:### 4. Phase 2 残り 4 runs の budget 戦略
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6956:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:221:  と、Phase 2 で必要な 8h は 4x の乖離。design-natural-gating-fix-v2.md
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6959:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:234:1-2 日遅延する。Phase 2 全体の deadline は明記されていない (m9-b LoRA
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6960:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:235:は M9 milestone 内、Phase 2 は eval foundation)。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6962:.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md:253:  (Phase 2 launch 仕様)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6963:.steering/20260420-m5-planning/design-v1.md:9:再適用する。Phase 1 schema freeze → Phase 2 並列 → Phase 3 integration → Phase 4
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6964:.steering/_setup-progress.md:34:- [x] **Phase 2: /setup-claude-md** — CLAUDE.md と .steering
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6965:.steering/_setup-progress.md:101:  - Phase 2 状態: skipped (公式 plugin 未導入 / `docs/external-skills.md` 不在)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6966:.steering/_setup-progress.md:115:| — | Phase 2 (新規) | marketplace (本リポ skip) |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:6967:.steering/_setup-progress.md:116:| Phase 2 | Phase 3 | claude-md (本リポは agent-shared.md 不採用) |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7006:.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:127:### Phase 2 — natural 全 15 cell (3-persona parallel × 5 run、~24-30h)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7036:.steering/20260420-m5-planning/design-comparison.md:10:- Phase 1 schema freeze → Phase 2 並列 4 本 → Phase 3 integration → Phase 4 live
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7037:.steering/20260420-m5-planning/design-comparison.md:39:| **並列化可能度 (G-GEAR+Mac 2 機)** | **高** (Phase 2 で 4 本並列、LLM + Godot で自然分担) | 低 (Phase 1-3 は直列、Phase 4 で初めて並列化) |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7038:.steering/20260420-m5-planning/design-comparison.md:68:| 並列化可能度 | 案 A 並 (高) — Phase 2 の並列 4 本を維持 |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7049:.steering/20260430-m9-eval-system/codex-review-low1.md:374:| Burrows chunk stability (Nietzsche) | rank instability 検出 (現状 ρ=1.0 PASS) | golden baseline 採取後 |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7114:.steering/20260430-m9-eval-system/codex-review-low1.md:2342:.steering/20260430-m9-b-lora-execution-plan/design-v2.md:171:- M9-eval-system: Tier B 完全実装 (Prometheus 2 rubric / FANToM-adapted / FActScore-adapted) + 専門家 review pipeline + golden set 採取
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7127:.steering/20260430-m9-eval-system/requirement.md:19:  3. golden baseline (LoRA 適用前の anchor) を採取しておかないと、後で adopt 判断に
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7137:.steering/20260420-m5-planning/tasklist.md:39:### Phase 2: 並列 4 本 (並列, 1-2 日 each)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7305:.steering/20260430-m9-eval-system/tasklist.md:16:## Phase 2 (Implementation) — 順次・依存順
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7489:.steering/20260430-m9-eval-system/blockers.md:162:| Burrows chunk stability (Nietzsche) | rank instability 検出 (現状 ρ=1.0 PASS) | golden baseline 採取後 |
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7492:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:14:# Codex Independent Review — Phase 2 run0 wall-timeout incident
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7493:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:18:m9-eval-system Phase 2 run0 で 3 cell (kant / nietzsche / rikyu) すべてが
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7495:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:21:Phase 2 残りの budget 戦略を立てたが、過去にも線形外挿で empirical を
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7500:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:52:Phase 2 では `--wall-timeout-min 360` を G-GEAR 側で override していた。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7513:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:149:- (g) run0 救出を採用すると Phase 2 の "5 runs × 3 personas × 2 conditions"
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7530:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:208:### 4. Phase 2 残り 4 runs の budget 戦略
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7535:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:234:  と、Phase 2 で必要な 8h は 4x の乖離。design-natural-gating-fix-v2.md
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7538:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:247:1-2 日遅延する。Phase 2 全体の deadline は明記されていない (m9-b LoRA
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7539:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:248:は M9 milestone 内、Phase 2 は eval foundation)。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7541:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:266:  (Phase 2 launch 仕様)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7657:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:3469:   127	### Phase 2 — natural 全 15 cell (3-persona parallel × 5 run、~24-30h)
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7723:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4587:  2873	  Issue: The script says ME-4 remains partial until P4, but tasklist lines 374-377 still say this Mac session compares Burrows/Vendi/Big5 and finalizes the ratio.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7724:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4589:  2875	  Suggested fix: Edit ME-4/tasklist to call this a lightweight partial update. If accepting a provisional close, add a re-open clause: P4 Burrows/Vendi/Big5 target-extrapolated ratio differing by `>=10%` or disagreeing in direction reopens ME-4.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7725:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:4597:  2883	  Issue: Current 7 tests pass, but they do not cover synthetic DuckDB end-to-end, schema `p3a_decide/v2`, partial-cell rejection, Rikyu Japanese Burrows failure, or exact 10% boundary.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:7739:.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:5074:   111	# lightweight partial update of ME-4 with Burrows scoped to (kant,
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:8135:.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md:4089:   195	    # Phase 2: STUDY is now rejected again (natural-dialog rules restored).
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:8243:.steering/20260420-m4-acceptance-live/acceptance.md:81:Phase 2 (fresh DB 再起動後) も同様に蓄積: kant=13 / nietzsche=13 / rikyu=30, origin nulls=0。
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:8495:.steering/20260425-m8-episodic-log-pipeline/tasklist.md:21:## Phase 2: DialogScheduler sink
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:8622:.steering/20260422-m6-observatory-carryover/tasklist.md:10:## Phase 2: Stress BiorhythmEvent
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:9364:src/erre_sandbox/evidence/reference_corpus/function_words.py:128:"""High-frequency Japanese particles used as the closed Burrows list.
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:10942:  "note": "Both conditions present: natural side re-captured after the M5/M6 zone-drift bug fix (eval_natural_mode flag, ME-8 ADR) and the COOLDOWN_TICKS_EVAL=5 + wall default 120 amendment. CI widths are surfaced per (persona, condition); the verdict in ratio_summary is computed on target-extrapolated widths (ME-4 default budgets, stimulus=200, natural=300) per Codex P3a-finalize HIGH-1. The ME-4 ADR Edit is the authority for the final ratio decision; this script provides the empirical inputs. Documented library limitations (e.g. rikyu Burrows Japanese tokenizer absence) surface under validation_warnings rather than blocking the verdict — ME-4 must remain re-openable on m9-eval-corpus tokenizer delivery.",
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:10952:    "warning": "lightweight_ratio_is_not_final_me4_ratio: ME-4 references Vendi + Big5 ICC; this Mac session computes Burrows Delta + MATTR as a lightweight proxy. P4 must re-run the verdict with the ADR-named metrics before ME-4 can be fully closed."
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:10957:      "Vendi Score and Big5 ICC are deferred to P4. This Mac session can therefore only deliver a **lightweight partial update** of ME-4 (Burrows Delta + MATTR), not a final close.",
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:10987:      "cell (rikyu, stimulus) metric 'burrows_delta_per_utterance' known limitation: BurrowsTokenizationUnsupportedError — Japanese tokenizer not implemented in tier_a.burrows; pre-tokenizing 青空文庫/国文大観 deferred to m9-eval-corpus expansion. ratio for this metric is computed on (kant, nietzsche) only; rikyu contribution comes from MATTR alone. ME-4 must remain re-openable on tokenizer delivery.",
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:10988:      "cell (rikyu, natural) metric 'burrows_delta_per_utterance' known limitation: BurrowsTokenizationUnsupportedError — Japanese tokenizer not implemented in tier_a.burrows; pre-tokenizing 青空文庫/国文大観 deferred to m9-eval-corpus expansion. ratio for this metric is computed on (kant, nietzsche) only; rikyu contribution comes from MATTR alone. ME-4 must remain re-openable on tokenizer delivery."
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:10998:    "cell (rikyu, stimulus) metric 'burrows_delta_per_utterance' known limitation: BurrowsTokenizationUnsupportedError — Japanese tokenizer not implemented in tier_a.burrows; pre-tokenizing 青空文庫/国文大観 deferred to m9-eval-corpus expansion. ratio for this metric is computed on (kant, nietzsche) only; rikyu contribution comes from MATTR alone. ME-4 must remain re-openable on tokenizer delivery.",
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:10999:    "cell (rikyu, natural) metric 'burrows_delta_per_utterance' known limitation: BurrowsTokenizationUnsupportedError — Japanese tokenizer not implemented in tier_a.burrows; pre-tokenizing 青空文庫/国文大観 deferred to m9-eval-corpus expansion. ratio for this metric is computed on (kant, nietzsche) only; rikyu contribution comes from MATTR alone. ME-4 must remain re-openable on tokenizer delivery."
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:11079:[MEDIUM] M3: `eval_audit` が現 main に存在せず、Phase 2 検証手順が未実装
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.raw.log:11122:[MEDIUM] M3: `eval_audit` が現 main に存在せず、Phase 2 検証手順が未実装
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:17:> ## ⚠️ 2026-05-06 追記 — Phase 2 run0 incident で本 prompt は SUPERSEDED
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:19:> 2026-05-06 の Phase 2 run0 (3-parallel natural、wall=360 min) は 3 cell 全て
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:24:> **本 prompt の §Phase 2 採取と §ブロッカー予測 item 2 は不正確** (wall=360 を
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:26:> 正しい運用は ME-9 ADR (`decisions.md`) と `cli-fix-and-audit-design.md` を
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:48:> `--focal-target` + `--report-json` の 3 flag に集約)。Phase 1 / Phase 2 採取
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:55:> v2 は ME-9 ADR の run1 calibration (kant only × 5 wall sequential、
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:174:### Phase 2 — natural 全 15 cell (3-persona parallel × 5 run、~24-30h)
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:210:`m9-eval-cli-partial-fix` (ME-9 ADR、CLI fix PR 適用後) で実装された
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:237:# Phase 2 run0 incident のような partial 群を別運用したい場合
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:244:# `data/eval/partial/` 隔離の運用は ME-9 ADR どおり。
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:343:   < 500)、**600 min 最低ライン**。対処は ME-9 ADR の通り CLI fix + run1
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:345:   詳細: `decisions.md` ME-9 / `blockers.md` "active incident: Phase 2 run0
.steering/20260420-m4-acceptance-live/acceptance.md:81:Phase 2 (fresh DB 再起動後) も同様に蓄積: kant=13 / nietzsche=13 / rikyu=30, origin nulls=0。
.steering/20260430-m9-eval-system/codex-review.md:32:2-of-3 quorum drift gate (M9-B ADR DB9). Its completion criterion is to take a
.steering/20260430-m9-eval-system/codex-review.md:34:Big5-ICC / Burrows-Delta have bootstrap CI ready (precondition for M9-C-adopt).
.steering/20260430-m9-eval-system/codex-review.md:47:   this task is expected to close (LIWC license, Burrows multi-lang, judge bias)
.steering/20260430-m9-eval-system/codex-review.md:72:## Required deliverables (HIGH / MEDIUM / LOW format, identical to M9-B review)
.steering/20260430-m9-eval-system/codex-review.md:126:   statistical power to detect a difference in bootstrap-CI width on Burrows
.steering/20260430-m9-eval-system/codex-review.md:131:5. **Burrows Delta multi-language reference: 50K token noise floor.** The
.steering/20260430-m9-eval-system/codex-review.md:157:- DB1-DB10 ADR set (M9-B `decisions.md`) — blocked from change in this review
.steering/20260430-m9-eval-system/codex-review.md:523:    50	- **Tier A live per-turn** は M9 milestone の "drift gate を実行時に発火" の
.steering/20260430-m9-eval-system/codex-review.md:537:    64	  (M9-A event-boundary observability の latency 観測値による)
.steering/20260430-m9-eval-system/codex-review.md:547:    74	- **Hybrid baseline** は drift gate の baseline noise を統制、Burrows Delta /
.steering/20260430-m9-eval-system/codex-review.md:566:    93	  遅延 (この task scope では問題ないが、M9-C-adopt で live gate を作る時に
.steering/20260430-m9-eval-system/codex-review.md:599:   126	   - 理由: `tier_a.py` 1 file に 5 metric (Burrows / MATTR / NLI / novelty /
.steering/20260430-m9-eval-system/codex-review.md:730:    76	- stylometric 一致は Burrows Delta (Tier A)
.steering/20260430-m9-eval-system/codex-review.md:766:   112	- 純 stimulus baseline は ζ 軸 (mode 遷移) を測れず M9-A event-boundary observability
.steering/20260430-m9-eval-system/codex-review.md:772:   118	- P3b で pilot run 50 turn 両形式を比較し、Burrows Delta / Vendi の bootstrap CI
.steering/20260430-m9-eval-system/codex-review.md:847:   193	  - `burrows.py` — Burrows Delta function-word vector cosine
.steering/20260430-m9-eval-system/codex-review.md:937:   278	**DB9 sub-metric 3 個 (Vendi / Big5 ICC / Burrows Delta) ready 時期**:
.steering/20260430-m9-eval-system/codex-review.md:938:   279	- Burrows: P1a 完了時 (per-turn computed)
.steering/20260430-m9-eval-system/codex-review.md:940:   281	- bootstrap CI 計算 ready: **P5 完了時 = タスク後半** (M9-C-adopt 直前)
.steering/20260430-m9-eval-system/codex-review.md:1013:   354	3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260430-m9-eval-system/codex-review.md:1026:   367	  Burrows Delta が persona-discriminative (Kant ≠ Nietzsche、distance 差 ≥ fixed delta)
.steering/20260430-m9-eval-system/codex-review.md:1032:   373	### Burrows multi-lang (blockers.md 暫定方針)
.steering/20260430-m9-eval-system/codex-review.md:1081:   422	3. **Burrows Delta multi-language reference の汚染** (blockers.md 既出)
.steering/20260430-m9-eval-system/codex-review.md:1089:   430	   - 反復: P3b で pilot run 50 turn 両形式比較、Burrows / Vendi の bootstrap CI
.steering/20260430-m9-eval-system/codex-review.md:1105:   446	- Burrows Delta multi-lang reference の閾値 (50K token noise floor)
.steering/20260430-m9-eval-system/codex-review.md:1145:     1	# Decisions — M9-B LoRA Execution Plan (10 ADR: DB1-DB10)
.steering/20260430-m9-eval-system/codex-review.md:1150:     6	本 ADR set は m9-lora-pre-plan の D1-D5 (PR #110 merged) を **継承し、M9 実行 phase の
.steering/20260430-m9-eval-system/codex-review.md:1156:    12	## DB1 — 量子化戦略: QLoRA NF4 default + alternatives recorded
.steering/20260430-m9-eval-system/codex-review.md:1158:    14	- **決定**: 学習時 quantization は **QLoRA NF4 (bnb double-quantization)** を default 採用。
.steering/20260430-m9-eval-system/codex-review.md:1159:    15	  alternatives (AWQ + LoRA / GPTQ + LoRA / 8-bit LoRA) を記録、bounded Kant spike で
.steering/20260430-m9-eval-system/codex-review.md:1163:    19	  - QLoRA NF4 + double-quantization で 1-2% 性能低下、許容範囲
.steering/20260430-m9-eval-system/codex-review.md:1166:    22	  - LoRA FP16: VRAM 不足
.steering/20260430-m9-eval-system/codex-review.md:1167:    23	  - INT8 + LoRA: NF4 の上位互換なし
.steering/20260430-m9-eval-system/codex-review.md:1169:    25	  - 学習 pipeline は HF Transformers + PEFT/unsloth (M9-C-spike で確定)
.steering/20260430-m9-eval-system/codex-review.md:1170:    26	  - serving は SGLang LoRA adapter format に変換 (DB3)
.steering/20260430-m9-eval-system/codex-review.md:1172:    28	  - Kant spike で NF4 quality が許容範囲外 → 8-bit LoRA fallback
.steering/20260430-m9-eval-system/codex-review.md:1173:    29	  - SGLang AWQ + LoRA 互換が confirmed → AWQ への serving migration 検討
.steering/20260430-m9-eval-system/codex-review.md:1177:    33	## DB2 — Library 選定: defer to M9-C kickoff
.steering/20260430-m9-eval-system/codex-review.md:1179:    35	- **決定**: PEFT vs unsloth の選定は **M9-eval-system + M9-C-spike 完了後の M9-C-adopt 着手時**
.steering/20260430-m9-eval-system/codex-review.md:1180:    36	  に rank=8 統一 spike で決める。M9-B / M9-eval-system では library を確定しない。
.steering/20260430-m9-eval-system/codex-review.md:1182:    38	  - 学習 library 選定は LoRA を実際に走らせる時点で十分
.steering/20260430-m9-eval-system/codex-review.md:1188:    44	  - M9-C-spike では一時的に PEFT (公式・ecosystem 厚い) を使用、final 選定は別
.steering/20260430-m9-eval-system/codex-review.md:1190:    46	  - unsloth の SGLang LoRA adapter format compatibility が問題
.steering/20260430-m9-eval-system/codex-review.md:1197:    53	- **決定**: **現行 SGLang を維持し、LoRA は SGLang `--enable-lora` + `/load_lora_adapter`
.steering/20260430-m9-eval-system/codex-review.md:1200:    56	  - codex HIGH-3: SGLang は v0.3+ で multi-LoRA / dynamic load/unload / pinned adapters /
.steering/20260430-m9-eval-system/codex-review.md:1203:    59	  - 私の v1/v2 認識 (SGLang LoRA 安定性未検証) は stale だった
.steering/20260430-m9-eval-system/codex-review.md:1209:    65	  - LoRA adapter format は SGLang 互換に変換が必要
.steering/20260430-m9-eval-system/codex-review.md:1213:    69	  - resonance / FSM が SGLang LoRA 経路で regression
.steering/20260430-m9-eval-system/codex-review.md:1219:    75	- **決定**: LoRA 適用 trigger を **`floor MUST AND (coverage 300/persona OR plateau OR timebox)`**
.steering/20260430-m9-eval-system/codex-review.md:1237:    93	  - LoRA 適用が現実的タイミングで fire 可能
.steering/20260430-m9-eval-system/codex-review.md:1238:    94	  - timebox により M9 milestone delay が bounded
.steering/20260430-m9-eval-system/codex-review.md:1259:   115	  - Parquet pipeline 実装 (M9-eval-system) の複雑度が中程度増加
.steering/20260430-m9-eval-system/codex-review.md:1299:   155	  - M9-B / M9-eval-system 期間は N=3 の divergence 漸近線 + 評価系構築が優先
.steering/20260430-m9-eval-system/codex-review.md:1304:   160	  - v1: M9-B 中 YAML 起草 → 評価系設計を複雑化
.steering/20260430-m9-eval-system/codex-review.md:1321:   177	  - **runbook 起草は M9-C-spike 完了後**、実測値 (latency / cold start / throughput) 込み
.steering/20260430-m9-eval-system/codex-review.md:1327:   183	  - v1/v2 vLLM LoRARequest API ラッパ路線 → DB3 で破棄
.steering/20260430-m9-eval-system/codex-review.md:1329:   185	  - M9-C-spike が runbook の前提
.steering/20260430-m9-eval-system/codex-review.md:1331:   187	  - SGLang LoRA で adapter swap が機能不全 → vLLM fallback (DB3 re-open)
.steering/20260430-m9-eval-system/codex-review.md:1348:   204	  - **Initial run** (first LoRA application): floor 維持で許容 (warmup 認可)
.steering/20260430-m9-eval-system/codex-review.md:1350:   206	  - **3 連続 adoption 失敗**: LoRA 設定 (rank / dataset) を破棄、再 spike
.steering/20260430-m9-eval-system/codex-review.md:1359:   215	  - bootstrap CI 実装 (M9-eval-system)
.steering/20260430-m9-eval-system/codex-review.md:1360:   216	  - quorum logic 実装 (M9-C-adopt)
.steering/20260430-m9-eval-system/codex-review.md:1367:   223	## DB10 — J 評価系 framework: 4-tier + persona-conditional + multi-channel (specs only in M9-B)
.steering/20260430-m9-eval-system/codex-review.md:1370:   226	  - **M9-B 内 deliverable は specs のみ** (実装コードは出さない、MEDIUM-1 反映)
.steering/20260430-m9-eval-system/codex-review.md:1372:   228	    - Tier A: per-turn cheap (LIWC/Empath / Burrows Delta / MATTR / semantic novelty / NLI)
.steering/20260430-m9-eval-system/codex-review.md:1379:   235	    - M9-eval-system: **100/persona seed**
.steering/20260430-m9-eval-system/codex-review.md:1380:   236	    - LoRA 採用判定: **300/persona acceptance**
.steering/20260430-m9-eval-system/codex-review.md:1392:   248	  - v2 単独: M9-B 内で Tier A 実装まで含む scope creep
.steering/20260430-m9-eval-system/codex-review.md:1395:   251	  - M9-eval-system が独立タスクとして大規模化
.steering/20260430-m9-eval-system/codex-review.md:1405:   261	**bounded, non-authoritative single-persona Kant LoRA spike を SGLang 上で M9-eval-system
.steering/20260430-m9-eval-system/codex-review.md:1408:   264	- **目的**: 評価系構築中に LoRA 学習・adapter swap・runtime 技術リスクを早期検出
.steering/20260430-m9-eval-system/codex-review.md:1412:   268	- **deliverable**: SGLang LoRA endpoint 動作確認 + adapter swap latency 実測 +
.steering/20260430-m9-eval-system/codex-review.md:1414:   270	- **タスク**: 別タスク `M9-C-spike` として切り出し (新規 scaffold)
.steering/20260430-m9-eval-system/codex-review.md:1421:     1	# Blockers & Deferred Items — M9-B LoRA Execution Plan
.steering/20260430-m9-eval-system/codex-review.md:1425:     5	Codex review LOW finding および設計上 M9-B closure では即決できない判断事項を defer。
.steering/20260430-m9-eval-system/codex-review.md:1432:    12	- **defer 先**: M9-eval-system (eval test fixture として synthetic 4th persona を含める)
.steering/20260430-m9-eval-system/codex-review.md:1438:    18	- **defer 先**: M9-eval-system (LIWC license 評価 + alternative decision tree 起草)
.steering/20260430-m9-eval-system/codex-review.md:1442:    22	## M9-B closure では決められない判断事項
.steering/20260430-m9-eval-system/codex-review.md:1449:    29	- **option D**: stylometry (Burrows' Delta) のみで persona-fit を測り、Big-Five claim を諦める
.steering/20260430-m9-eval-system/codex-review.md:1450:    30	- **defer 先**: M9-eval-system 着手前 (Tier A 実装の前提)
.steering/20260430-m9-eval-system/codex-review.md:1453:    33	### Burrows' Delta multi-language strategy 詳細
.steering/20260430-m9-eval-system/codex-review.md:1458:    38	  - cross-language Burrows' Delta は使わない
.steering/20260430-m9-eval-system/codex-review.md:1460:    40	- **defer 先**: M9-eval-system (reference corpus 整備時に詳細詰め)
.steering/20260430-m9-eval-system/codex-review.md:1473:    53	- **defer 先**: M9-eval-system (Tier C 実装時に runbook 起草)
.steering/20260430-m9-eval-system/codex-review.md:1479:    59	  - M9-C-adopt 直前で 3 persona × 1 専門家を確保
.steering/20260430-m9-eval-system/codex-review.md:1482:    62	- **defer 先**: M9-C-adopt 直前
.steering/20260430-m9-eval-system/codex-review.md:1493:    73	- v1「LoRA ASAP」を棄却したことで、短期 deliverable が遅延
.steering/20260430-m9-eval-system/codex-review.md:1494:    74	- M9 milestone の 2-3 倍延長 (M9-B / M9-eval-system / M9-C-spike / M9-C-adopt)
.steering/20260430-m9-eval-system/codex-review.md:1496:    76	- **再評価条件**: M9-eval-system が予想以上に長期化 (>3 セッション) → M9-C-spike を
.steering/20260430-m9-eval-system/codex-review.md:1499:    79	### M9-C-spike の adoption 判断 leakage リスク
.steering/20260430-m9-eval-system/codex-review.md:1502:    82	- **対策強化条件**: M9-C-spike Kant が「明らかに人間目視で改善」した場合の判断 protocol を起草
.steering/20260430-m9-eval-system/codex-review.md:1507:    87	- **観測点**: M9-eval-system Tier B 実装完了直後の 2-3 run で plateau curve を観察
.steering/20260430-m9-eval-system/codex-review.md:1512:    92	- **再評価条件**: M9-eval-system Tier B 実装完了後の golden baseline 採取で discriminative 確認、
.steering/20260430-m9-eval-system/codex-review.md:1519:    99	| LIWC license | option A-D いずれか確定 | M9-eval-system 着手前 |
.steering/20260430-m9-eval-system/codex-review.md:1520:   100	| Burrows multi-lang | dialog 言語混在運用 | M9-eval-system reference corpus |
.steering/20260430-m9-eval-system/codex-review.md:1521:   101	| Judge bias runbook | judge LLM 確定 | M9-eval-system Tier C 実装 |
.steering/20260430-m9-eval-system/codex-review.md:1522:   102	| 専門家 selection | 評価系完成 | M9-C-adopt 直前 |
.steering/20260430-m9-eval-system/codex-review.md:1524:   104	| v1 機会コスト再評価 | M9-eval-system >3 セッション | M9-eval-system 中盤 |
.steering/20260430-m9-eval-system/codex-review.md:1525:   105	| M9-C-spike leakage | spike Kant 目視改善 | M9-C-spike 完了時 |
.steering/20260430-m9-eval-system/codex-review.md:1526:   106	| N=3 plateau curve | Tier B 実装完了 | M9-eval-system Tier B 完了直後 |
.steering/20260430-m9-eval-system/codex-review.md:1527:   107	| Tier B sub-metric 3 | golden baseline 採取 | M9-eval-system 終盤 |
.steering/20260430-m9-eval-system/codex-review.md:1534:     5	M9-B の J 軸 (思想家らしさの評価系 framework) の ADR (DB10) を起草する前に、
.steering/20260430-m9-eval-system/codex-review.md:1735:   206	### Stylometry / Burrows' Delta (arXiv:2507.00838 2025; arXiv:2408.08946 2024)
.steering/20260430-m9-eval-system/codex-review.md:1737:   208	- **Scoring**: Burrows' Delta = z-scored function-word frequency の Manhattan distance
.steering/20260430-m9-eval-system/codex-review.md:1811:   282	| **F5 Cognitive trait** | Big Five (IPIP-NEO + LIWC-22 cross-validation) | Stylometry (Burrows' Delta to thinker reference) |
.steering/20260430-m9-eval-system/codex-review.md:1820:   291	- `Burrows' Delta` to thinker reference corpus (function-word vector、2ms)
.steering/20260430-m9-eval-system/codex-review.md:1885:   351	これを踏まえ M9-B 設計フェーズで:
.steering/20260430-m9-eval-system/codex-review.md:2048:   115	        # sqlite for later LoRA-training export. Left None for unit tests
.steering/20260430-m9-eval-system/codex-review.md:2596:src/erre_sandbox/cli/export_log.py:5:rows as newline-delimited JSON. Consumed by the M9 LoRA training pipeline
.steering/20260430-m9-eval-system/codex-review.md:2600:src/erre_sandbox/cli/export_log.py:38:            "newline-delimited JSON. Intended for M9 LoRA training-data "
.steering/20260430-m9-eval-system/codex-review.md:2719:src/erre_sandbox/memory/store.py:916:          speaker-scoped for LoRA training-data semantics).
.steering/20260430-m9-eval-system/codex-review.md:2725:src/erre_sandbox/integration/dialog.py:115:        # sqlite for later LoRA-training export. Left None for unit tests
.steering/20260430-m9-eval-system/codex-review.md:2742:src/erre_sandbox/bootstrap.py:502:        # sqlite ``dialog_turns`` for later LoRA-training export. The closure
.steering/20260430-m9-eval-system/codex-review.md:2990:   844	        every existing call site (and every M7ε run before the m9-LoRA
.steering/20260430-m9-eval-system/codex-review.md:3062:   916	          speaker-scoped for LoRA training-data semantics).
.steering/20260430-m9-eval-system/codex-review.md:3165:   502	        # sqlite ``dialog_turns`` for later LoRA-training export. The closure
.steering/20260430-m9-eval-system/codex-review.md:3189:   526	            # the m9-LoRA Q&A driver lands.
.steering/20260430-m9-eval-system/codex-review.md:3240:     5	rows as newline-delimited JSON. Consumed by the M9 LoRA training pipeline
.steering/20260430-m9-eval-system/codex-review.md:3263:    28	"""Formats accepted by ``--format``. Parquet joins this set in the M9 LoRA task."""
.steering/20260430-m9-eval-system/codex-review.md:3273:    38	            "newline-delimited JSON. Intended for M9 LoRA training-data "
.steering/20260430-m9-eval-system/codex-review.md:3289:    54	            "deferred to the M9 LoRA task (decisions D4)."
.steering/20260430-m9-eval-system/codex-review.md:3383:web search: Burrows Delta stylometry minimum text length number of words function words z scores corpus size stable
.steering/20260430-m9-eval-system/codex-review.md:3768:- **Finding**: The design says `connect_training_view()` is the only training entry, but the current training export path already reads sqlite directly and is documented as consumed by M9 LoRA. Grep for `metrics.` misses quoted SQL, dynamic SQL, direct DuckDB connections, `read_parquet("...metrics...")`, and future Rust/Go tooling.
.steering/20260430-m9-eval-system/codex-review.md:3791:### HIGH-5: Burrows Delta is specified as the wrong metric
.steering/20260430-m9-eval-system/codex-review.md:3792:- **Finding**: `burrows.py` is described as “function-word vector cosine,” but the research doc defines Burrows Delta as distance over z-scored function-word frequencies.
.steering/20260430-m9-eval-system/codex-review.md:3794:- **Recommendation**: Implement actual Burrows Delta, or rename the quorum submetric to Cosine Delta and update DB9 wording, thresholds, and tests.
.steering/20260430-m9-eval-system/codex-review.md:3827:### MEDIUM-6: 50K Burrows token floor needs corpus-QC semantics
.steering/20260430-m9-eval-system/codex-review.md:3865:- **Finding**: The design says `connect_training_view()` is the only training entry, but the current training export path already reads sqlite directly and is documented as consumed by M9 LoRA. Grep for `metrics.` misses quoted SQL, dynamic SQL, direct DuckDB connections, `read_parquet("...metrics...")`, and future Rust/Go tooling.
.steering/20260430-m9-eval-system/codex-review.md:3888:### HIGH-5: Burrows Delta is specified as the wrong metric
.steering/20260430-m9-eval-system/codex-review.md:3889:- **Finding**: `burrows.py` is described as “function-word vector cosine,” but the research doc defines Burrows Delta as distance over z-scored function-word frequencies.
.steering/20260430-m9-eval-system/codex-review.md:3891:- **Recommendation**: Implement actual Burrows Delta, or rename the quorum submetric to Cosine Delta and update DB9 wording, thresholds, and tests.
.steering/20260430-m9-eval-system/codex-review.md:3924:### MEDIUM-6: 50K Burrows token floor needs corpus-QC semantics
.steering/20260430-m9-eval-system/codex-review-low1.md:18:- タスク: `m9-eval-system` (M9-A event-boundary observability の後続、4 タスク化された M9 milestone の 1)
.steering/20260430-m9-eval-system/codex-review-low1.md:68:   Vendi/Burrows の persona 横比較が "stimulus 種類効果 × persona 効果" 分離不能
.steering/20260430-m9-eval-system/codex-review-low1.md:98:  defer / ME-6: Burrows corpus QC が関連)
.steering/20260430-m9-eval-system/codex-review-low1.md:239:defer 期限と reopen 条件を明示。M9-B 親タスクの blockers (`.steering/20260430-m9-b-lora-execution-plan/blockers.md`)
.steering/20260430-m9-eval-system/codex-review-low1.md:263:### LIWC license 評価 (M9-B blockers から継承、本タスクで close 候補)
.steering/20260430-m9-eval-system/codex-review-low1.md:265:- **issue**: M9-B `blockers.md` の "LIWC 商用 license の最終可否判定"
.steering/20260430-m9-eval-system/codex-review-low1.md:268:- **defer 先**: 本タスク P0a で M9-B blockers.md を Edit して "Option D 採用" 記載
.steering/20260430-m9-eval-system/codex-review-low1.md:273:### Burrows corpus license (Cambridge Edition / Kaufmann translation 等)
.steering/20260430-m9-eval-system/codex-review-low1.md:287:  下記 "Burrows reference corpus — English translations defer" で independent
.steering/20260430-m9-eval-system/codex-review-low1.md:290:### Burrows reference corpus — English translations defer (2026-05-01 P1b 開設)
.steering/20260430-m9-eval-system/codex-review-low1.md:298:  - 独原典のみで Burrows 経路を回し、対話が英語に流れた場合は
.steering/20260430-m9-eval-system/codex-review-low1.md:299:    `BurrowsLanguageMismatchError` で明示 fail (silent fallback 禁止)
.steering/20260430-m9-eval-system/codex-review-low1.md:310:### Burrows reference corpus — toy-scale corpus expansion (2026-05-01 P1b 開設)
.steering/20260430-m9-eval-system/codex-review-low1.md:329:### Burrows Delta multi-lang reference の閾値 (M9-B blockers から継承)
.steering/20260430-m9-eval-system/codex-review-low1.md:337:### Judge bias mitigation runbook (M9-B blockers から継承)
.steering/20260430-m9-eval-system/codex-review-low1.md:340:- **暫定方針** (M9-B 既出):
.steering/20260430-m9-eval-system/codex-review-low1.md:371:| Burrows corpus license (independent) | Cambridge / Kaufmann PD edition 確認 | m9-eval-corpus |
.steering/20260430-m9-eval-system/codex-review-low1.md:372:| Burrows en translations defer | PD 英訳 edition 入手 | m9-eval-corpus / 後続 |
.steering/20260430-m9-eval-system/codex-review-low1.md:373:| Burrows toy-scale expansion | Akademie-Ausgabe 全文 / 利休関連 PD 大規模 | m9-eval-corpus |
.steering/20260430-m9-eval-system/codex-review-low1.md:374:| Burrows chunk stability (Nietzsche) | rank instability 検出 (現状 ρ=1.0 PASS) | golden baseline 採取後 |
.steering/20260430-m9-eval-system/codex-review-low1.md:386:- 不適切なら DB9 sub-metric を Tier A 系に入れ替え検討 (M9-B `blockers.md` の
.steering/20260430-m9-eval-system/codex-review-low1.md:406:125:- 純 stimulus baseline は ζ 軸 (mode 遷移) を測れず M9-A event-boundary observability
.steering/20260430-m9-eval-system/codex-review-low1.md:426:517:| Burrows token floor: corpus QC 化 (固定 50K → ≥5K-word chunk stability) | MEDIUM-6 | `decisions.md` ME-6 ADR / `blockers.md` reopen 条件 | ✅ ADR 化 |
.steering/20260430-m9-eval-system/codex-review-low1.md:440:各 ADR は M9-B `.steering/20260430-m9-b-lora-execution-plan/decisions.md` と同形式の
.steering/20260430-m9-eval-system/codex-review-low1.md:441:5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)。本 ADR set は M9-B DB1-DB10 と
.steering/20260430-m9-eval-system/codex-review-low1.md:445:ID prefix: `ME` (m9-Eval-system) で M9-B `DB` と区別。
.steering/20260430-m9-eval-system/codex-review-low1.md:565:  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition
.steering/20260430-m9-eval-system/codex-review-low1.md:616:## ME-6 — Burrows reference corpus QC (Codex MEDIUM-6)
.steering/20260430-m9-eval-system/codex-review-low1.md:656:- 既存 M9-B DB1-DB10 ADR との衝突: 無し
.steering/20260430-m9-eval-system/codex-review-low1.md:664:72:## Required deliverables (HIGH / MEDIUM / LOW format, identical to M9-B review)
.steering/20260430-m9-eval-system/codex-review-low1.md:686:1026:   367	  Burrows Delta が persona-discriminative (Kant ≠ Nietzsche、distance 差 ≥ fixed delta)
.steering/20260430-m9-eval-system/codex-review-low1.md:693:1159:    15	  alternatives (AWQ + LoRA / GPTQ + LoRA / 8-bit LoRA) を記録、bounded Kant spike で
.steering/20260430-m9-eval-system/codex-review-low1.md:695:1172:    28	  - Kant spike で NF4 quality が許容範囲外 → 8-bit LoRA fallback
.steering/20260430-m9-eval-system/codex-review-low1.md:697:1200:    56	  - codex HIGH-3: SGLang は v0.3+ で multi-LoRA / dynamic load/unload / pinned adapters /
.steering/20260430-m9-eval-system/codex-review-low1.md:710:1370:   226	  - **M9-B 内 deliverable は specs のみ** (実装コードは出さない、MEDIUM-1 反映)
.steering/20260430-m9-eval-system/codex-review-low1.md:716:1405:   261	**bounded, non-authoritative single-persona Kant LoRA spike を SGLang 上で M9-eval-system
.steering/20260430-m9-eval-system/codex-review-low1.md:718:1425:     5	Codex review LOW finding および設計上 M9-B closure では即決できない判断事項を defer。
.steering/20260430-m9-eval-system/codex-review-low1.md:725:1502:    82	- **対策強化条件**: M9-C-spike Kant が「明らかに人間目視で改善」した場合の判断 protocol を起草
.steering/20260430-m9-eval-system/codex-review-low1.md:726:1525:   105	| M9-C-spike leakage | spike Kant 目視改善 | M9-C-spike 完了時 |
.steering/20260430-m9-eval-system/codex-review-low1.md:761:3791:### HIGH-5: Burrows Delta is specified as the wrong metric
.steering/20260430-m9-eval-system/codex-review-low1.md:773:3827:### MEDIUM-6: 50K Burrows token floor needs corpus-QC semantics
.steering/20260430-m9-eval-system/codex-review-low1.md:788:3888:### HIGH-5: Burrows Delta is specified as the wrong metric
.steering/20260430-m9-eval-system/codex-review-low1.md:800:3924:### MEDIUM-6: 50K Burrows token floor needs corpus-QC semantics
.steering/20260430-m9-eval-system/codex-review-low1.md:837:   125	- 純 stimulus baseline は ζ 軸 (mode 遷移) を測れず M9-A event-boundary observability
.steering/20260430-m9-eval-system/codex-review-low1.md:906:   261	  3 sub-metric quorum logic は decision layer (M9-C-adopt)。`numpy` + `arch`
.steering/20260430-m9-eval-system/codex-review-low1.md:984:   486	3. **Burrows Delta multi-language reference の汚染** (blockers.md 既出)
.steering/20260430-m9-eval-system/codex-review-low1.md:992:   494	   - 反復: P3b で pilot run 50 turn 両形式比較、Burrows / Vendi の bootstrap CI
.steering/20260430-m9-eval-system/codex-review-low1.md:1003:   416	3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260430-m9-eval-system/codex-review-low1.md:1483:- タスク: `m9-eval-system` (M9-A event-boundary observability の後続、4 タスク化された M9 milestone の 1)
.steering/20260430-m9-eval-system/codex-review-low1.md:1533:   Vendi/Burrows の persona 横比較が "stimulus 種類効果 × persona 効果" 分離不能
.steering/20260430-m9-eval-system/codex-review-low1.md:1563:  defer / ME-6: Burrows corpus QC が関連)
.steering/20260430-m9-eval-system/codex-review-low1.md:1622:- タスク: `m9-eval-system` (M9-A event-boundary observability の後続、4 タスク化された M9 milestone の 1)
.steering/20260430-m9-eval-system/codex-review-low1.md:1672:   Vendi/Burrows の persona 横比較が "stimulus 種類効果 × persona 効果" 分離不能
.steering/20260430-m9-eval-system/codex-review-low1.md:1702:  defer / ME-6: Burrows corpus QC が関連)
.steering/20260430-m9-eval-system/codex-review-low1.md:1843:defer 期限と reopen 条件を明示。M9-B 親タスクの blockers (`.steering/20260430-m9-b-lora-execution-plan/blockers.md`)
.steering/20260430-m9-eval-system/codex-review-low1.md:1932:   207	  - [ ] Burrows Delta / Vendi / Big5 ICC の CI width 計算
.steering/20260430-m9-eval-system/codex-review-low1.md:1934:   209	  - [ ] M9-B `blockers.md` の "Hybrid baseline 比率 200/300" 項目を close
.steering/20260430-m9-eval-system/codex-review-low1.md:1983:     1	# Reference corpus provenance — Burrows Delta P1b
.steering/20260430-m9-eval-system/codex-review-low1.md:1987:     5	#   - language: ISO-ish tag (must match BurrowsReference.language)
.steering/20260430-m9-eval-system/codex-review-low1.md:2013:    31	#         translation licensing is confirmed (blockers.md "Burrows corpus
.steering/20260430-m9-eval-system/codex-review-low1.md:2162:   141	        assert isinstance(ref, BurrowsReference)
.steering/20260430-m9-eval-system/codex-review-low1.md:2265:     1	# Blockers & Deferred Items — M9-B LoRA Execution Plan
.steering/20260430-m9-eval-system/codex-review-low1.md:2269:     5	Codex review LOW finding および設計上 M9-B closure では即決できない判断事項を defer。
.steering/20260430-m9-eval-system/codex-review-low1.md:2276:    12	- **defer 先**: M9-eval-system (eval test fixture として synthetic 4th persona を含める)
.steering/20260430-m9-eval-system/codex-review-low1.md:2282:    18	- **defer 先**: M9-eval-system (LIWC license 評価 + alternative decision tree 起草)
.steering/20260430-m9-eval-system/codex-review-low1.md:2286:    22	## M9-B closure では決められない判断事項
.steering/20260430-m9-eval-system/codex-review-low1.md:2299:    35	- **option D**: stylometry (Burrows' Delta) のみで persona-fit を測り、Big-Five claim
.steering/20260430-m9-eval-system/codex-review-low1.md:2312:   155	  - M9-B / M9-eval-system 期間は N=3 の divergence 漸近線 + 評価系構築が優先
.steering/20260430-m9-eval-system/codex-review-low1.md:2317:   160	  - v1: M9-B 中 YAML 起草 → 評価系設計を複雑化
.steering/20260430-m9-eval-system/codex-review-low1.md:2342:.steering/20260430-m9-b-lora-execution-plan/design-v2.md:171:- M9-eval-system: Tier B 完全実装 (Prometheus 2 rubric / FANToM-adapted / FActScore-adapted) + 専門家 review pipeline + golden set 採取
.steering/20260430-m9-eval-system/codex-review-low1.md:2351:.steering/20260430-m9-eval-system/design-final.md:416:3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260430-m9-eval-system/codex-review-low1.md:2359:.steering/20260430-m9-b-lora-execution-plan/blockers.md:12:- **defer 先**: M9-eval-system (eval test fixture として synthetic 4th persona を含める)
.steering/20260430-m9-eval-system/codex-review-low1.md:2444:.steering/20260430-m9-eval-system/codex-review-low1.md:1003:   416	3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260430-m9-eval-system/codex-review-low1.md:2527:.steering/20260430-m9-eval-system/codex-review-low1.md:2276:    12	- **defer 先**: M9-eval-system (eval test fixture として synthetic 4th persona を含める)
.steering/20260430-m9-eval-system/codex-review-low1.md:2556:.steering/20260430-m9-b-lora-execution-plan/design-v1.md:111:- M9-eval-system: Tier B-D (Vendi / Prometheus / FANToM / FActScore / 専門家 review) を切り出し
.steering/20260430-m9-eval-system/codex-review-low1.md:2588:.steering/20260430-m9-eval-system/codex-review.md:1013:   354	3. **Bootstrap CI shape**: 既知分布 (synthetic Vendi / ICC / Burrows triple) で
.steering/20260430-m9-eval-system/codex-review-low1.md:2599:.steering/20260430-m9-eval-system/codex-review.md:1432:    12	- **defer 先**: M9-eval-system (eval test fixture として synthetic 4th persona を含める)
.steering/20260430-m9-eval-system/codex-review-low1.md:2668:- **観察 / 根拠**: DB7 は runtime N=4 を M10 defer し、M9 では eval pipeline の 3-persona overfit 防止が目的。現状 `personas/_synthetic_4th.yaml` は未作成で、reference corpus でも analytical background mean fixture。
.steering/20260430-m9-eval-system/codex-review-low1.md:2710:- **観察 / 根拠**: DB7 は runtime N=4 を M10 defer し、M9 では eval pipeline の 3-persona overfit 防止が目的。現状 `personas/_synthetic_4th.yaml` は未作成で、reference corpus でも analytical background mean fixture。
.steering/20260507-m9-eval-cooldown-readjust-adr/requirement.md:6:> 完了時点で **ME-9 trigger** に該当し、G-GEAR Claude が正規 STOP。
.steering/20260507-m9-eval-cooldown-readjust-adr/requirement.md:23:ADR (`decisions.md` ME-9, line 646):
.steering/20260507-m9-eval-cooldown-readjust-adr/requirement.md:69:- vLLM / SGLang / LoRA (M9-B 系統)
.steering/20260507-m9-eval-cooldown-readjust-adr/requirement.md:80:  - 解釈 C: ADR (`decisions.md` ME-9) amendment + v2 prompt 修正
.steering/20260507-m9-eval-cooldown-readjust-adr/requirement.md:87:- 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9 (本タスクで
.steering/20260428-event-boundary-observability/design-comparison.md:82:2. **summary 文字列は live 観察体験を質的に底上げする** — `[icon] bowl_01 @ chashitsu` より `[icon] 茶碗を取り上げた @ chashitsu` の方が user は因果を読める。研究 observatory 価値に直結 (M9 LoRA pre-plan の "推奨第 1 候補" 理由とも整合)
.steering/20260419-gateway-fastapi-ws/design.md:43:        # ---- Phase 2: ACTIVE -----------------------------------------
.steering/20260430-m9-eval-system/requirement.md:5:- **直接の前段**: M9-B LoRA execution plan (PR #127 merged, main=`ff29ca2`) で 10 ADR
.steering/20260430-m9-eval-system/requirement.md:9:- **位置付け**: M9 milestone は M9-A (event-boundary observability、PR #117-#124 完全
.steering/20260430-m9-eval-system/requirement.md:10:  クローズ済) に続き、M9-B → **M9-eval-system (本タスク)** + M9-C-spike (並行) →
.steering/20260430-m9-eval-system/requirement.md:11:  M9-C-adopt の順で進む。本タスクと M9-C-spike は独立進行し、M9-C-adopt で合流する。
.steering/20260430-m9-eval-system/requirement.md:13:  1. LoRA fine-tuning の効果は「ペルソナ忠実度・心理的整合・stylometric 一致」を多軸で
.steering/20260430-m9-eval-system/requirement.md:15:     無いまま spike を走らせると、empirical foundation 抜きの judgment になり LoRA
.steering/20260430-m9-eval-system/requirement.md:16:     採用判断 (M9-C-adopt) を支えられない。
.steering/20260430-m9-eval-system/requirement.md:17:  2. M9-C-adopt の前提条件として **Vendi / Big5 ICC / Burrows Delta の 3 sub-metric
.steering/20260430-m9-eval-system/requirement.md:19:  3. golden baseline (LoRA 適用前の anchor) を採取しておかないと、後で adopt 判断に
.steering/20260430-m9-eval-system/requirement.md:25:baseline を採取して、M9-C-adopt の前提条件 (DB9 の sub-metric 3 個が bootstrap CI 計算
.steering/20260430-m9-eval-system/requirement.md:39:  - Burrows Delta (function word frequency vector cosine)
.steering/20260430-m9-eval-system/requirement.md:56:  Burrows Delta) が計算 ready 状態に到達。
.steering/20260430-m9-eval-system/requirement.md:62:- M9-C-spike (SGLang LoRA bounded Kant spike) — 別 `/start-task m9-c-spike` で並行進行。
.steering/20260430-m9-eval-system/requirement.md:63:- M9-C-adopt の判断そのもの — 本タスクは前提条件を整えるところまで。
.steering/20260430-m9-eval-system/requirement.md:64:- LoRA training pipeline 実装 — M9-D で扱う。
.steering/20260430-m9-eval-system/requirement.md:84:      Burrows Delta) が **bootstrap CI 計算 ready** (M9-C-adopt の前提) — P5 完了時、
.steering/20260430-m9-eval-system/requirement.md:87:      defer 項目 1 件 close) — **Option D 確定 / 2026-04-30 P0a で M9-B
.steering/20260430-m9-eval-system/requirement.md:97:      LoRA training や M9-C-spike の混入無し) — closure 時に確認
.steering/20260430-m9-eval-system/requirement.md:101:### M9-B 直接前段 (Read 必須)
.steering/20260430-m9-eval-system/requirement.md:106:- `.steering/20260430-m9-b-lora-execution-plan/blockers.md` — LIWC license / Burrows
.steering/20260430-m9-eval-system/requirement.md:108:- `.steering/20260430-m9-b-lora-execution-plan/tasklist.md` Phase B 節 (M9-eval-system tasklist)
.steering/20260430-m9-eval-system/requirement.md:114:- `docs/glossary.md` — Tier 0/A/B/C / Vendi / Burrows Delta / IPIP-NEO 等の用語
.steering/20260430-m9-eval-system/requirement.md:127:- **Codex independent review 必須**: M9-B で Codex web search が SGLang v0.3+ multi-LoRA を
.steering/20260430-m9-eval-system/requirement.md:137:- **並行タスク**: M9-C-spike は別 `/start-task m9-c-spike` で起こす。両者独立、
.steering/20260430-m9-eval-system/requirement.md:138:  M9-C-adopt で合流。
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:200:- LoRA training (M9-B) interaction — orthogonal milestone
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:203:- M9-A event boundary observability — already merged
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:585:        # sqlite for later LoRA-training export. Left None for unit tests
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1610:M9-A bump (0.9.0-m7z → 0.10.0-m7h): one additive nested field tied to the
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:1626:chronology readable; the M9 namespace is reserved for the LoRA work.
.steering/20260430-m9-eval-system/codex-review-natural-gating.md:2530:   117	        # sqlite for later LoRA-training export. Left None for unit tests
.steering/20260428-event-boundary-observability/tasklist.md:21:- [ ] schemas.py docstring (L73-129 周辺) に M9-A entry 追記 (`0.10.0-m7h` の意味)
.steering/20260507-m9-eval-cooldown-readjust-adr/blockers.md:1:# ブロッカー — m9-eval ME-9 trigger 解釈タスク
.steering/20260507-m9-eval-cooldown-readjust-adr/blockers.md:6:- **解消**: ME-9 Amendment 2026-05-07 で trigger zone を context-aware (single
.steering/20260507-m9-eval-cooldown-readjust-adr/blockers.md:10:### B-2. ADR (`decisions.md` ME-9) の rate basis ambiguity
.steering/20260507-m9-eval-cooldown-readjust-adr/blockers.md:42:- target ratio (Burrows / MATTR) 確定、ME-4 stage 3 close 候補
.steering/20260507-m9-eval-cooldown-readjust-adr/blockers.md:74:- ME-4 partial close 構造、ME-9 amendment と、ADR 末尾追記による re-define
.steering/20260430-m9-eval-system/codex-review-prompt-low1.md:5:- タスク: `m9-eval-system` (M9-A event-boundary observability の後続、4 タスク化された M9 milestone の 1)
.steering/20260430-m9-eval-system/codex-review-prompt-low1.md:55:   Vendi/Burrows の persona 横比較が "stimulus 種類効果 × persona 効果" 分離不能
.steering/20260430-m9-eval-system/codex-review-prompt-low1.md:85:  defer / ME-6: Burrows corpus QC が関連)
.steering/20260419-gateway-fastapi-ws/requirement.md:76:- SGLang / vLLM の後段切替 → M7 / M9
.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md:25:3. Recognize that ME-4's `判定基準` references **3 metrics** (Burrows Delta /
.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md:26:   Vendi / Big5 ICC) but only **2 lightweight metrics** (Burrows Delta + MATTR)
.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md:70:where `stim_w` and `nat_w` are mean CI widths of `(Burrows Delta width +
.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md:96:> - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md:102:- Uses Burrows Delta + **MATTR** (not in ADR), defers Vendi + Big5 ICC.
.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md:114:  verdict carry an additional disclaimer that Burrows + MATTR may
.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md:115:  produce a different ratio than Burrows + Vendi + Big5 ICC?
.steering/20260419-gateway-fastapi-ws/tasklist.md:40:  - Phase 2 ACTIVE: per-client queue 作成 → registry.add → TaskGroup で
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.md:6:- 解釈 A の妥当性: 強い。ME-9 ADR の根拠は run0 3-parallel `≈65/h` で、ADR も run0 観測を根拠にしている。`run1` は [ME-9 ADR](/Users/johnd/ERRE-Sand%20Box/.steering/20260430-m9-eval-system/decisions.md:586) で single と明記されるため、basis 混在がある。
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.md:24:実作業は A: ME-9 ADR amendment block で rate basis 明示、v2 prompt B-1 refresh。PR の結論は C: wording 修正のみで完結し、cooldown 再調整は defer。
.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.md:27:### H1. ME-9 trigger の rate basis を分離
.steering/_verify-report-20260418.md:26:### Phase 2: CLAUDE.md ✅
.steering/20260425-m8-episodic-log-pipeline/decisions.md:11:  - L6 D1 の真の目的は M9 LoRA 訓練用の対話 turn 数 tracking
.steering/20260425-m8-episodic-log-pipeline/decisions.md:12:  - LoRA 訓練入力は対話 turn そのもの、reasoning_trace は認知内部の観察シグナル
.steering/20260425-m8-episodic-log-pipeline/decisions.md:53:  - LoRA 訓練 pipeline (HuggingFace datasets) は JSONL を直接 load 可
.steering/20260425-m8-episodic-log-pipeline/decisions.md:54:  - Parquet は M9 LoRA task で本当に必要になった時に追加、追加 cost は低い
.steering/20260425-m8-episodic-log-pipeline/decisions.md:56:  error を返す (M9 で追加時は値を増やす)
.steering/20260420-m4-personas-nietzsche-rikyu-yaml/requirement.md:51:- LoRA per persona → M9
.steering/20260425-m8-episodic-log-pipeline/design.md:8:L6 ADR D1 (`defer-and-measure`) の M8 precondition。M9 LoRA 訓練の前提
.steering/20260425-m8-episodic-log-pipeline/design.md:121:- M9 前提 ≥1000 turns/persona までの距離見積
.steering/20260425-m8-episodic-log-pipeline/design.md:127:- Parquet export (LoRA task で pyarrow 追加時に)
.steering/20260425-m8-episodic-log-pipeline/design.md:128:- DPO ペア抽出 / 選別ロジック (M9 early task)
.steering/20260425-m8-episodic-log-pipeline/design.md:136:- L6 ADR D1 の真の目的 (LoRA 訓練用 turn 数 tracking) に focus、scope 爆弾を
.steering/20260425-m8-episodic-log-pipeline/requirement.md:9:L6 ADR D1 (`defer-and-measure`) の M8 precondition。M9 LoRA 訓練は
.steering/20260425-m8-episodic-log-pipeline/requirement.md:12:終了で消失。LoRA 訓練データへの経路を作るため、対話 turn を sqlite に永続化し、
.steering/20260425-m8-episodic-log-pipeline/requirement.md:67:- MASTER-PLAN: L146 (M9 LoRA 前提)
.steering/20260425-m8-episodic-log-pipeline/tasklist.md:21:## Phase 2: DialogScheduler sink
.steering/20260425-m8-episodic-log-pipeline/tasklist.md:39:      pair 頻度 / M9 準備状態 (≥1000 turns/persona までの距離) の 4 queries
.steering/20260425-m8-episodic-log-pipeline/tasklist.md:65:- [ ] `log-snapshot.md` に persona 別 turn count + M9 前提までの距離を記録
.steering/_setup-progress.md:34:- [x] **Phase 2: /setup-claude-md** — CLAUDE.md と .steering
.steering/_setup-progress.md:101:  - Phase 2 状態: skipped (公式 plugin 未導入 / `docs/external-skills.md` 不在)
.steering/_setup-progress.md:115:| — | Phase 2 (新規) | marketplace (本リポ skip) |
.steering/_setup-progress.md:116:| Phase 2 | Phase 3 | claude-md (本リポは agent-shared.md 不採用) |
.steering/_setup-progress.md:358:    (`_COMMON_PREFIX` → persona 固有 → 動的 tail、RadixAttention 最適化) +
.steering/20260418-godot-ws-client/decisions.md:15:  - Router の 7 専用 signal 契約が T17 avatar 接続 / M5 zone visuals / M9 LoRA
.steering/20260418-godot-ws-client/design-comparison.md:87:2. **T17/M5/M9 への波及効果**: Router の signal 契約は後続タスクの接続点になる。
.steering/20260422-m6-observatory-carryover/tasklist.md:10:## Phase 2: Stress BiorhythmEvent
.steering/20260418-godot-ws-client/design.md:271:  - T17/M5/M9 への signal 契約基盤として Router の 7 専用 signal が長期投資になる

web search: 
web search: Generative Agents Interactive Simulacra of Human Behavior Park 2023 arxiv persistent memory reflection plan
web search: 
web search: 2024 LLM agent persistent identity self model memory arxiv
web search: 
web search: "Examining Identity Drift" "LLM agents" 2025
web search: 
web search: "Agent Identity Evals" "Measuring Agentic Identity" arxiv 2507.17257
web search: 
web search: Piaget stage theory criticism cognitive development empirical evidence stage model critique
web search: 
web search: Erik Erikson eight stages psychosocial development official encyclopedia Britannica
web search: 
web search: SGLang RadixAttention prefix cache official documentation
web search: 
web search: https://arxiv.org/abs/2304.03442
web search: 
web search: 'dynamic' in https://sgl-project.github.io/advanced_features/lora.html
web search: 
web search: Burrows Delta stylometry function words most frequent words method
codex
ローカル確認では、M9-B は「評価基盤先行 + bounded Kant spike」、M9-eval は Burrows/Vendi/Big5 を adoption 前提にしており、Option A はここに新しい混入経路を作る可能性が高いです。次に、active task の設計文書から Option A と reimagine の差分を押さえます。
exec
/bin/zsh -lc "sed -n '1,260p' .steering/20260508-cognition-deepen-7point-proposal/design-clarified.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# Design — Post-clarification 改訂判定 (2026-05-08)

> このドキュメントは `design.md` の判定をユーザー clarification (2026-05-08
> follow-up) で **再評価** したもの。元の `design.md` は initial reading として残す。
> 最終判定は `design-final.md` (Codex review 後) でまとめる。

## 0. Clarification の structural reading

ユーザー clarification は 7 提案を「個別 schema 追加の集合」から **二層アーキテクチャへの
統一的転換** に framing し直した。要点:

- 提案 1, 7 が同根: **agent は新しい個体**、philosopher は **base layer**
- 提案 5, 6 が同根: 個体が **時間経過で発達する**
- 提案 2, 3, 4 は二層モデルで個体側を駆動する mechanism

このため判定は **個別 ADOPT/REJECT** ではなく **architecture as a whole** で判断される
べきで、その場合 7 提案はすべて単一 architecture の構成要素として ADOPT すべき。

## 1. 二層アーキテクチャの draft 設計

### 1.1 Layer 分離

```
PhilosopherBase (immutable, inherited)
  ├── cognitive_habits: list[CognitiveHabit]   (現 personas/*.yaml の cognitive_habits 流用)
  ├── default_sampling: SamplingParam          (現 default_sampling 流用)
  ├── preferred_zones: list[Zone]              (現 preferred_zones 流用)
  ├── lora_adapter_id: str | None              (M9-B LoRA target)
  └── persona_id: str                          (kant / rikyu / nietzsche、固定 reference)

Individual (mutable, per-agent runtime state)
  ├── individual_id: str                        (新規 entity)
  ├── base: PhilosopherBase                     (継承、reference)
  ├── personality: Personality                  (Big5 + wabi/ma_sense、base から divergence 可)
  ├── world_model: SubjectiveWorldModel         (= 提案 1、AgentState property、5 axis)
  ├── narrative_self: NarrativeSelf | None      (= 提案 5、周期蒸留 result)
  ├── development_state: DevelopmentState       (= 提案 6、lifecycle 段階)
  ├── shuhari_stage: ShuhariStage               (既存、base 側技能習得とは別文脈で再解釈)
  └── (memory, relational bond は既存通り)
```

**継承 contract** (HIGH 必要、Codex に問う):
- `cognitive_habits`: base から継承、individual が override は **不可** (= "Kant 由来の散歩
  は揺るがない")
- `default_sampling`: base から継承、individual が override **可** (= 個体の気分で揺らぐ)
- `personality`: base が default 提供、individual が初期から **bounded divergence** で
  個別化 (= 兄弟でも性格が違う)
- `world_model`: 完全に individual 側 (base は "無" を default で提供)
- LoRA adapter: base layer のみに適用 (= 個体差は prompt/state overlay)

### 1.2 既存資産との関係 (二層解釈下で再評価)

| 既存 | layer 配属 | 変更必要性 |
|---|---|---|
| `personas/*.yaml` | → `PhilosopherBase` に rename / refactor | **大**: schema_version bump、loader 改修、prompting 改修 |
| `AgentState.persona_id` | individual.base.persona_id へ間接化 | 中: getter 維持で互換可 |
| `AgentState.cognitive`, `AgentState.physical`, `AgentState.erre` | individual の sub-state | 小: 既存配置を維持 |
| `AgentState.shuhari_stage` | individual.shuhari_stage | 小: 配置維持。意味解釈のみ変更 (技能習得 stage、lifecycle とは別) |
| `SemanticMemoryRecord.belief_kind` | individual の dyadic belief (subjective beliefs に統合) | 小: 既存維持、SubjectiveWorldModel と axis 直交 |
| `RelationshipBond` | individual 側 | 小: 既存維持 |
| `LLMPlan` | individual の出力 (個体の意思決定) | 中: world_model_update 追加 (bounded primitive) |
| Prompt `_COMMON_PREFIX` | base + individual 両方を反映するよう改修 | 中: cache 戦略再設計 |

### 1.3 改訂された per-item 判定

| # | 旧判定 (initial) | **新判定 (clarification 後)** | 主要変更 |
|---|---|---|---|
| 1 SubjectiveWorldModel | ADOPT in memory layer | **ADOPT as `Individual.world_model` property** (AgentState 第一級) | "agent 自体に" 明確化を反映、配置変更 |
| 2 prompt 注入 | ADOPT w/ constraints | **ADOPT, 同設計** | 変更なし (`_COMMON_PREFIX` 汚染禁止、user prompt 側) |
| 3 LLMPlan world_model_update | MODIFY to bounded primitive | **ADOPT as bounded primitive** | 同じ判定 (free-form は role-play 増幅、bounded primitive 必須) |
| 4 safe merge | ADOPT | **ADOPT, belief.py pattern 流用** | 変更なし |
| 5 NarrativeSelf | M11-A defer | **M10-B (M9-B 後の最初の milestone)** | 個体連続性に必須、後送不可 |
| 6 DevelopmentState | REJECT standalone | **ADOPT as `Individual.development_state`** | shuhari_stage は base 側技能習得、DevelopmentState は individual 側 lifecycle、**直交** |
| 7 philosopher_seed | DEFER M11+ | **ADOPT as conceptual two-layer refactor** | base = LoRA target (M9-B 不変)、individual = overlay。M9 trunk 破壊しない |

## 2. 「完全に人間として構築」への operational 制約案 (initial)

ユーザー言明「途中途中から成長していく過程を導入し、完全に人間として構築」は scope
無限化リスク。Codex に operational definition を切り詰めてもらうため、**Claude 提案の
bounded interpretation** を先に置く:

### 2.1 段数の制約 (5 stage 案)

```
DevelopmentStage:
  S1_seed:       初期化直後、base habit 強い、world_model 空
  S2_individuation: 個体差発現、world_model 5-15 entries、narrative 未生成
  S3_consolidation: 信念の安定、world_model 15-50 entries、narrative_self 初回生成
  S4_articulation: 自己語り定常化、narrative cycle 安定、belief revision rate 減衰
  S5_late:       高 importance 記憶飽和、新規入力に rigidity (人間の老化アナロジー)
```

5 段は経験的選択 (Erikson 8 / Piaget 4 / 守破離 3 の中間)。

### 2.2 各段の cognitive 特性差 (operational)

| stage | sampling 修正 | memory window | reflection 周期 | personality drift 許容 |
|---|---|---|---|---|
| S1 | base 通り | 標準 | 標準 | high (個別化中) |
| S2 | T +0.05 (探索期) | 拡張 1.2x | 1.5x 高頻度 | high |
| S3 | base 通り | 標準 | 標準 | medium |
| S4 | T -0.05 (内向化) | 標準 | 1.5x 高頻度 | low |
| S5 | T -0.10 | 縮退 0.8x | 0.5x 低頻度 | very low |

これは **first principles ではなく empirical placeholder** で、Codex / 実装段階で再
calibration 必須。

### 2.3 段間遷移 criterion (transition trigger)

複合条件 (AND):
- world_model entries ≥ 段ごと閾値 (S2: 5, S3: 15, S4: 50, S5: 150)
- narrative_self が直近 N=3 cycles で stable (cosine sim > 0.85 to median)
- importance 累積 ≥ 段ごと閾値

これは memory promote / belief promote と同型 pattern (threshold AND interaction count)。

### 2.4 "完成" の定義 (= 死/置換するか問題)

3 path 候補 (Codex に判断委ねる):
- **path A**: 不完成。S5 で停滞、無限走行
- **path B**: 死/置換。S5 で N session 後に individual を retire、新 individual を同じ
  base から起動 (世代交代観察可)
- **path C**: stage rebirth。S5 から S2 にループ (転生 metaphor、研究的に面白いが
  現実的でない)

Claude 推奨: **path A** (個人プロジェクトの scope 制約、retirement / 転生は M12+ 研究)

## 3. 改訂 phasing (clarification 反映)

```
M9 trunk (UNTOUCHED):
  - run1 calibration (G-GEAR、in-flight)
  - M9-eval Phase 2 完了
  - M9-B LoRA execution (philosopher_base = Kant 文体、固定)
  ↓ M9 完了 → individual layer 構築開始可能

M10-A: Two-layer schema scaffold (提案 7 + 1 + 6 の structural 部分)
  - PhilosopherBase / Individual / SubjectiveWorldModel / DevelopmentState
    Pydantic schema を contracts/ 配下に新設
  - personas/*.yaml は 0.10.0-m7h → 0.11.0 に bump、PhilosopherBase に rename
  - AgentState を Individual 側に再配置 (互換 wrapper を 1 release 維持)
  - schema scaffold のみ、ロジック未配線、test 通過のみ
  - acceptance: 既存 1318 tests PASS、新 schema の golden test 追加

M10-B: Individual 側の cognition wiring (提案 1 + 2 + 3 + 4 + 5)
  - SubjectiveWorldModel の write path: prompt 注入 + bounded LLMPlan update +
    safe-merge (belief.py pattern 流用)
  - NarrativeSelf 周期蒸留 (chashitsu reflection 拡張で発火)
  - DevelopmentState は S1 固定 (transition machinery は M11)
  - acceptance: 100-tick smoke で 1 individual の世界モデル形成と narrative 生成を確認

M11-A: DevelopmentState transition machinery (提案 6 lifecycle 化)
  - 5 段 (S1-S5) と段間 trigger
  - 各段の sampling / memory / reflection 修正
  - acceptance: 1 individual を 1000-tick 走らせ S1→S2→S3 の遷移を確認

M11-B: Multi-individual 同 base 検証 (個体化の direct evidence)
  - 3 individual を同 PhilosopherBase (kant) から起動
  - Burrows ratio で base 保持 + 個体ばらつきを分解測定
  - acceptance: base style identity ≥ 0.6 (LoRA 効果残存) AND individual variance ≥
    threshold (個体化観測)

M12+ (research re-evaluation):
  - retirement / world transition (path B 検討)
  - 多 base × 多 individual の社会実験
  - LoRA を individual layer にも適用するか判断
```

## 4. 新規 HIGH-stakes な open question (Codex review 必須)

1. **base / individual inheritance contract**: cognitive_habits は immutable か?
   sampling は inherit + override 可能か? Big5 は base から divergence 許容範囲は?
   この設計が決まらないと M10-A scaffold が書けない。

2. **schema_version bump 戦略**: 0.10.0-m7h → 0.11.0 で persona YAML を
   PhilosopherBase に rename するときの **backward compat 戦略**:
   - personas/*.yaml の自動 migration script を書くか
   - 1 release 並走 (両 schema を loader で受ける) するか
   - 一括書換えで割り切るか (現在 3 personas しかない)

3. **LoRA scope**: M9-B LoRA は base layer 専用か、individual の personality drift も
   学習対象か? 後者なら M9-B execution 着手前に再判断必要。

4. **prompt 構造改修と KV cache**: `_COMMON_PREFIX` を base と individual で分離する
   とき、SGLang RadixAttention 効果はどこまで保たれるか? 多 individual で多 base
   になったら cache 効果は減衰するか?

5. **DevelopmentStage 5 段の妥当性**: 3 (shuhari と並立) / 5 (Claude 案) / 8 (Erikson)
   のどれが ERRE thesis に整合するか? 経験的選択ではなく first principles から
   論証できるか?

6. **"完成" の path 選択**: A (不完成) / B (retirement) / C (転生) のどれを M11-A の
   default 設計にするか?

7. **二層分離が role-play 増幅 risk を緩和するか悪化するか**: LLM に "あなたは Kant
   ベースの新しい個人 X" と告げると、LLM は X を **role-play する** 危険があり、これは
   現在の "あなたは Kant" より **悪化** する可能性がある (個体の自由度が高い分、創作の
   余地も広い)。

exec
/bin/zsh -lc "sed -n '1,280p' .steering/20260430-m9-b-lora-execution-plan/design-final.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,280p' .steering/20260508-cognition-deepen-7point-proposal/design-reimagine.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# Reimagine — 認知層深化のゼロベース代替案

> 本ドキュメントは ユーザーの 7 提案を **読まない状態で** ゼロから再構想した
> 独立設計案である。出発点の 1 文のみを read し、シングル subagent 1 発案
> バイアスを意識して最初の案を意図的に破棄してから本案を組んだ。突合節
> (§4) を書く段階で初めて 7 提案を `requirement.md` 内で確認している。

## 1. 問題再定式化 (1 文の出発点をどう解釈したか)

> 「現在の ERRE エージェントは固定 persona role-play から外れる手段を持たない。
> 創発が観察可能になるには、agent が環境/関係性/自己との interaction で内的状態を
> 蓄積し、その蓄積が後続の発話と行動を変える仕組みが必要」

この 1 文は次の 3 つの隠れ前提を含んでいる:

1. **「外れる手段がない」 = state 不足** ではなく **「変化が prompt に影響しない」 =
   feedback loop 不足**。schema を増やすだけでは LLM の振る舞いは変わらない (cf. ME-9
   trigger 擬陽性 incident — 外形 metric だけ動いて意味に届かなかった構造の同型)。
2. **「蓄積」** は raw memory の増殖ではなく **圧縮された解釈** でなければならない。
   raw episodic は M4 から既に蓄積されているのに role-play から外れない実例が現にある。
3. **「後続の発話と行動を変える」** には少なくとも 3 経路必要 — (a) prompt 注入,
   (b) sampling parameter の変調, (c) FSM 遷移条件の変化。schema 提案だけでは (a)
   しかカバーできない。

つまり問題の本質は **「圧縮された解釈を LLM の意思決定に閉じた fast loop に流し込み、
その loop の出力で再び解釈を更新する」** という cybernetic loop の欠落である。
schema 拡張は手段であって目的ではない。

## 2. 最初の 1 案 (意図的に破棄する初期案を 1 段落)

最初に思いついた案 (= 破棄する案): **「`AgentState.Cognitive` に
`internalized_lessons: list[str]` を追加し、reflection trigger で LLM に "今日学んだこと"
を 1 行書かせて貯める」**。これは却下する。理由は (i) free-form list の拘束のなさが
ME-9 trigger 擬陽性と同型 — LLM が「学んだ」と宣言すればそれが真になる構造、
(ii) belief_kind / shuhari_stage と axis 関係が定義されない、(iii) 「変化が後続の発話を
変える」 feedback loop を欠く (list を prompt に流すだけで読み手の LLM が反応する保証
がない)、(iv) M9-eval Burrows ratio が「persona ごとの語彙分布」を測定中なのに
internalized_lessons が persona 間で homogenize する方向にしか働かない。
**この初期案を捨て、cybernetic loop 設計に切り替える**。

## 3. 本案 (= reimagine 後): 認知層拡張の独立設計

### 3.1 設計の核 — 「Compression-Loop」 architecture

3 層を **環状** に接続する。ERRE thesis の "意図的非効率性 + 身体的回帰" を schema
化するのではなく、**圧縮 → 注入 → 行動 → 観察 → 再圧縮** という閉じた loop で実装する。

```
[LAYER R - Raw]                          [LAYER C - Compressed]
episodic_memory  ───reflect (M4 既存)───▶ semantic_memory (belief_kind 含む)
   ▲                                              │
   │                                              ▼ (新)
observations ◀──perceive──┐         StanceVector (新スキーマ, 5-axis × float)
                          │                       │
                          │                       ▼ (新)
                       ACTION    ◀──prompt-inject──┘ (cache-safe section)
                          │
                          ▼
                 [LAYER A - Action]
                 LLMPlan (既存) + StanceShiftHint (新, bounded primitive)
                          │
                          └──> Python-side:  apply_stance_shift_hint()
                                              (新, pure function, 提案 4 同型)
```

### 3.2 schema 追加 / 既存拡張のリスト

#### (新規) `StanceVector` — 5 axis × float の圧縮表象

```
class StanceVector(BaseModel):
    """Compressed, action-relevant projection of the agent's accumulated
    interpretation. Distilled from semantic_memory + RelationshipBond by
    a periodic synthesis step. Lives in AgentState.cognitive (in-memory),
    persisted as one row per (agent_id, axis) in a new `stance_vector` table."""
    model_config = ConfigDict(extra="forbid")
    axis: Literal[
        "zone_affordance",      # どの zone が自分の思考を進めるか
        "concept_affinity",     # 追究中の概念への引きの強さ (≠ belief_kind の dyad)
        "self_capability",      # 自己効力感の 5-axis 投影
        "ritual_devotion",      # 規範/儀式への内化
        "interlocutor_class",   # 「対話相手の質」の anonymized class (個別 id ではなく)
    ]
    value: float = Field(ge=-1.0, le=1.0)  # signed: 正は引き, 負は忌避
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_pointers: list[str]  # memory_id ≥ 1 必須 (LLM 自己宣言だけで生成不可)
    last_updated_tick: int
    decay_half_life_ticks: int = 1000  # 観察なしで自然に弱まる
```

**設計判断**: `belief_kind` (dyadic, 5-cat enum) との **axis 直交性を保証する制約** —
StanceVector の axis 集合に "**他者個別 id への信頼**" を **入れない**。
`interlocutor_class` は個別 id ではなく "学者風 / 詩人風 / 寡黙派" のような **anonymized
class** を持つ (新たな小さな enum を別途定義)。これで dyadic belief_kind と vector
StanceVector が overlap しない。

#### (新規) `StanceShiftHint` — LLMPlan の bounded primitive 拡張

```
class StanceShiftHint(BaseModel):
    """LLM が "stance を更新したい" と希望するときの bounded request.
    Python 側が evidence を verify してから merge する。"""
    axis: Literal[...]   # StanceVector と同じ
    direction: Literal["strengthen", "weaken", "no_change"]
    cited_memory_ids: list[str]  # 必須 ≥ 1; 直近 N tick の retrieved_memories から選ぶ
    # ← LLM は新 belief を free-form で生成できない。既存軸の方向性を観察に紐付けて
    #   主張するだけ。
```

LLMPlan に追加: `stance_shift_hint: StanceShiftHint | None = None`。default None なので
schema_version は minor bump (additive)。`extra="forbid", frozen=True` 制約は維持。

**この設計が回避するもの** — LLM が `"I now believe peripatos is meaningless"` と
書くだけで `StanceVector(zone_affordance=-1)` が成立してしまう pattern。
`cited_memory_ids` が直近の `retrieved_memories` (ReasoningTrace 既存 field) と
**集合包含関係を満たさなければ採用されない**。

#### (新規) `NarrativeArc` — 蓄積された StanceVector の経時的形状

```
class NarrativeArc(BaseModel):
    """An agent's "story so far", periodically synthesized at chashitsu entry.
    Not free-form prose: a structured trajectory over (axis, time)."""
    agent_id: str
    synthesized_at_tick: int
    arc_segments: list[ArcSegment]  # ≤ 5 segments (older folded)
    coherence_score: float          # 自分の発話と StanceVector の一致度 (0-1)
    last_episodic_pointer: str      # 最後に取り込んだ episodic id
```

**役割**: 単なるログではなく **coherence_score** が次の synthesis 時の trigger として
機能する。低いと chashitsu reflection が深い narrative cleanup を発火する (「自己の
ほつれ」の検出)。

#### (既存拡張) `Cognitive.shuhari_stage` を transition machinery 付きに

stage は維持 (`shu / ha / ri`)、追加するのは `transition_evidence_count: dict[stage, int]`
と遷移 trigger 関数 (pure):

```
def maybe_advance_shuhari(
    cog: Cognitive,
    stance: list[StanceVector],
    arc: NarrativeArc | None,
) -> ShuhariStage | None:
    # shu → ha: ritual_devotion が高い AND coherence_score > 0.7 が N サイクル続く
    # ha → ri: stance に 2 axis 以上で個性的偏差 (peer agent 分布から std > 1.5)
    # 戻り値 None = 変化なし
```

新 schema を作らず ShuhariStage を rich 化する。Western stage model を並立させない
(ERRE thesis の 守破離 + 仏教/茶道由来 を維持)。

#### (新規) `growth_trace` — persona YAML への optional 拡張

persona_id / display_name / cognitive_habits は **そのまま維持** する。persona は
固定 seed であり続けるが、各 persona に "成長許可方向" を追加:

```yaml
# kant.yaml に追加 (任意 field, 後方互換)
growth_axes:
  permitted:
    - concept_affinity:categorical_imperative   # この方向は時間で深まりうる
    - self_capability:critique_articulation
  forbidden:
    - interlocutor_class:詩人風                 # Kant が詩人を高く評価する逸脱は許さない
```

これは「ペルソナを seed にする」(= identity を希釈する) のではなく、
**"the persona stays; the depth grows"** の範囲制約。M9-B LoRA が学習する style 軸
(固定) と直交。M9-eval Burrows ratio は YAML root level で測るため
`growth_axes` 追加で baseline は影響を受けない。

### 3.3 データフロー (どの時点で何が読み書きされるか)

| Tick 内 step | Read | Write |
|---|---|---|
| 1. 観察収集 | observation stream | — |
| 2. 記憶検索 | episodic + semantic + StanceVector (新) | retrieved_memories (trace) |
| 3. prompt 構築 | StanceVector top-3 (新, **user prompt** 側) | — |
| 4. LLM call | system+user prompt | `LLMPlan` (+ `stance_shift_hint`) |
| 5. plan 適用 | `stance_shift_hint.cited_memory_ids` | StanceVector (条件満足時のみ) |
| 6. reflection (条件付) | episodic window | `SemanticMemoryRecord` (既存) |
| 7. **synthesize** (chashitsu 入室時) | semantic+StanceVector | `NarrativeArc` |
| 8. shuhari check | StanceVector + NarrativeArc | `Cognitive.shuhari_stage` |

step 5 の "条件満足時" = `cited_memory_ids` が ≥ 1 個の retrieved_memories と一致 +
direction が `no_change` でない + decay 適用後の |value| が 1.0 を超えない。

### 3.4 既存 belief_kind / shuhari_stage との関係

- **`belief_kind` (dyadic, M7δ)** ← 維持。役割は「特定相手 (個別 id) への態度」。
  StanceVector の `interlocutor_class` 軸とは axis 集合が直交する (個別 vs クラス)。
- **`shuhari_stage` (3-enum, M5)** ← 維持して **transition machinery** を追加。
  evidence カウンタを足し、関数 `maybe_advance_shuhari` を新設。Western stage 並立を避ける。
- 既存の `cognition/belief.py:maybe_promote_belief` の **pure function pattern** を
  そのまま `apply_stance_shift_hint` / `synthesize_narrative_arc` /
  `maybe_advance_shuhari` の 3 関数に踏襲する。layer 境界
  (cognition/ ↛ memory/) を維持。

### 3.5 prompt 注入箇所と KV cache 影響

**絶対に `_COMMON_PREFIX` を変えない**。SGLang RadixAttention の KV cache 再利用が
壊れる。

- 注入箇所: `build_user_prompt` の memories block の **直後** に新 section
  `Held stances:` を追加。既存 system prompt は無変更。
- token budget: top-3 axes × 1 行 = 約 60-80 tokens。memories block と同等オーダー。
- 形式:
  ```
  Held stances (axis: value @ confidence):
  - zone_affordance:peripatos +0.78 @ 0.65
  - concept_affinity:categorical_imperative +0.91 @ 0.88
  - self_capability:critique_articulation +0.42 @ 0.50
  ```
- system 側 (persona block + state tail) は **完全に同一文字列** で再構築されるので
  RadixAttention prefix は引き続き再利用できる。

### 3.6 LLM 出力契約変更の有無

**最小限 + bounded**。

- `LLMPlan` に `stance_shift_hint: StanceShiftHint | None = None` のみ追加
  (default None)。`extra="forbid", frozen=True` は維持。
- `RESPONSE_SCHEMA_HINT` に 1 セクション追加 (~ 8 行)。memory 引用の必須化を
  prompt に書く: "If you wish to update a stance, set `stance_shift_hint` and
  cite at least one `retrieved_memories` id; otherwise leave null".
- parse_llm_plan は既存で OK (Pydantic 検証で reject)。
- **新 free-form フィールドは追加しない** (ME-9 incident 教訓)。

### 3.7 phasing (M9 完了後の milestone 配置)

```
M9 trunk (UNTOUCHED): run1 calibration → eval Phase 2 → M9-B LoRA execution
         → M9-eval Phase 2 vs LoRA 比較 baseline 確立                       ← 触らない

[M10-A] StanceVector の **read-only** 部分を投入
   - schema 追加 + persistence (sqlite-vec ではなく plain table)
   - synthesis (semantic_memory → StanceVector) の周期実行 (chashitsu 入室)
   - prompt 注入 (user prompt の追加 section)
   - acceptance: 既存 100-tick smoke で persona 別の StanceVector が異なる軸で
                 強くなることを統計的に確認 (Burrows ratio に対して直交シグナル)
   - 影響範囲: cognition/, memory/store.py に table 追加, prompting.py に section
   - **LLMPlan は触らない** (read-only loop で安定確認)

[M10-B] StanceShiftHint = LLMPlan に bounded primitive 追加
   - LLMPlan minor schema bump (additive, 互換)
   - apply_stance_shift_hint() pure function (cited_memory_ids verify 含む)
   - acceptance: golden test "LLM が free-form で belief を主張しても採用されない"
   - acceptance: 100-tick で stance_shift_hint adoption rate を計測
                 (高すぎ = pickup が緩い / 低すぎ = LLM が cite を諦めている)

[M10-C] NarrativeArc synthesis
   - chashitsu reflection の延長として synthesize_narrative_arc()
   - coherence_score の計測 (発話 embedding と StanceVector cosine sim)
   - 低 coherence で深い reflection 発火する FSM 拡張

[M11-A] ShuhariStage transition machinery (拡張のみ、新 schema 作らず)
   - maybe_advance_shuhari() pure function
   - shu→ha→ri 遷移の empirical observation
   - acceptance: 単一 cell で観察行動駆動の遷移を確認

[M11-B] persona YAML に growth_axes (任意 field) を追加
   - 後方互換、 M9-B LoRA / M9-eval Burrows baseline は影響なし
   - acceptance: kant が detective_arc 方向に深まり詩人風を許さないことを確認

[M11+ research re-evaluation gate]
   - M9-eval baseline と M10/M11 の介入後を比較
   - 「persona 識別性が強すぎて創発が見えない」or「弱すぎて persona が消える」
     のいずれかを empirical に確認した場合のみ further refactor を検討
   - 先に decision を固定しない
```

各 milestone 単独で **acceptance 基準が定量** であり、後段が前段に depend するが
**前段が後段なしで独立に成立** する形。ME-9 incident の "LLM の自己宣言だけで trigger
する pattern" を全工程で除外。

## 4. ユーザーの 7 提案との突合

> ここで初めて 7 提案を read した (`requirement.md` 内 §提案 verbatim)。

 succeeded in 0ms:
# Design Final — M9-B LoRA Execution Plan (v3 hybrid: 評価基盤先行 + 並行 Kant spike)

> このドキュメントは Plan→Clear→Execute ハンドオフ規則に従い、`/clear` 後でも独立に
> Read 可能な体裁で書かれている。10 軸の ADR は `decisions.md` (DB1-DB10) に対応する。
>
> v1 (Claude 単独 LoRA-first 案) は `design-v1.md` で破棄。
> v2 (/reimagine 評価基盤先行案) は `design-v2.md` に保存。
> v1/v2 比較は `design-comparison.md`、外部 reviewer (Codex `gpt-5.5` `xhigh`) は
> `codex-review.md` に verbatim 保存。本書は **codex review HIGH 4 件すべてを反映**
> + **codex の指摘した第 3 の道 (bounded Kant spike on SGLang in parallel with eval-system)**
> を取り込んだ最終 hybrid。

## 設計思想 (v3 final)

LoRA 適用の go-no-go gate は評価系完成後に判定する **(v2-B 路線維持)** が、
**LoRA 学習・adapter swap・runtime に関する技術リスクは、
single-persona (Kant) bounded spike を SGLang 上で並行実施して早期に潰す**
(codex review final note 提案)。

key 転換:
1. **SGLang-first**: SGLang は v0.3+ で multi-LoRA / dynamic load/unload / pinned adapters /
   overlap loading / `--enable-lora` を documented サポート (codex HIGH-3、SGLang docs)。
   vLLM full migration は破棄、measured spike failure 時のみ fallback
2. **trigger relaxation**: 4 条件 AND は D1 ADR と矛盾 (codex HIGH-1)。
   `floor AND (coverage OR plateau OR timebox)` に緩和。divergence stability は diagnostic、
   hard gate ではない
3. **offensive gate 統計的厳密化**: 「5%」固定を破棄、composite + bootstrap CI + 2-of-3 quorum
   (codex HIGH-2)
4. **train/eval 物理分離**: Parquet boolean flag は不十分 (codex HIGH-4)。raw training
   table は metric-free、metric は sidecar table に分離
5. **bounded parallel Kant spike**: 評価系構築と並行で、Kant 1 persona に対し SGLang LoRA
   adapter swap + 学習 loop を non-authoritative spike として走らせる。**adoption 判断は
   評価系完成後の post-spike re-evaluation でのみ行う**

## 10 軸の確定 (DB1-DB10 ADR cross-ref)

### A. 量子化戦略 (DB1) → QLoRA NF4 default + AWQ/GPTQ alternatives recorded

- **default**: QLoRA NF4 (bnb double-quantization)、base ~4-5GB、3 persona base 共有 + adapter ~50MB/persona
- **alternatives 記録 (MEDIUM-2 反映)**:
  - AWQ + LoRA: serving-side quality 維持
  - GPTQ + LoRA: 量子化品質トレードオフ
  - 8-bit LoRA: NF4 で 4-bit が品質面で破綻した時の fallback
- **判断**: 「唯一現実解」ではなく「conservative default」と framing。Kant spike で
  実測 quality 検証

### B. Library 選定 (DB2) → defer to M9-C kickoff

- PEFT vs unsloth は M9-eval-system 完了後の M9-C 着手時に spike (rank=8 統一)
- **codex 開示の追加**: SGLang の LoRA training compatibility は別途確認必要
  (training は別 framework、SGLang は serving)。学習は HF Transformers + PEFT/unsloth、
  serving は SGLang LoRA adapter 形式に変換

### C. Serving 移行判断 (DB3) → **SGLang-first, vLLM fallback only** (HIGH-3 反映)

- 現行 SGLang 維持
- LoRA は SGLang `--enable-lora` + `/load_lora_adapter` で実装
- multi-LoRA + overlap loading は documented サポート (SGLang docs cited by codex)
- vLLM への migration は **measured spike failure** が条件:
  - adapter swap latency > 500ms (G-GEAR で 3 persona 切替不能)
  - batching collapse (N=3 同時 request で throughput drop)
  - integration regression (M5 resonance / ERRE FSM が破綻)
- いずれも spike で実測してから判断

**v1/v2 → v3 の最大の cost saving**: M5 以降の resonance 機構の再配線が不要

### D. Dataset trigger 閾値 (DB4) → `floor AND (coverage OR plateau OR timebox)` (HIGH-1 反映)

**新トリガー条件**:
- **MUST (floor)**: self_rep ≤ 0.10 AND cross_echo ≤ 0.10 (継続要件)
- **ANY ONE OF**:
  - **coverage**: dialog_turn ≥ 300/persona (D1 ADR の v1 を緩和、500→300、ζ scale 実態反映)
  - **plateau**: prompting + persona YAML 拡張のみで Tier B metric が 2 連続 run で <5% improvement (operational definition は HIGH-2 quorum logic に統合)
  - **timebox**: 8 セッション (~2 calendar weeks at solo cadence) 経過

**divergence stability** (ζ 36:74:16 ±10%) は **diagnostic** (warning trigger) のみ。
hard gate にしない (codex 指摘)

**v1/v2 4-AND からの relaxation**: floor は必須維持、それ以外はいずれかで OK。
**timebox の追加**: solo project の momentum loss 防止 (codex Q2 反映)

### E. Parquet export schema (DB5) → **raw + sidecar 分離** (HIGH-4 反映)

#### Raw training table (`raw_dialog/`)
**metric-free**。training loader が直接 import する table。
```
schema:
  - run_id: str
  - persona_id: str (partition key)
  - turn_idx: int
  - timestamp: float
  - mode: str (ERREMode)
  - zone: str
  - dialog_turn_text: str
  - reasoning_trace_text: str (nullable)
  - episodic_log_event: str (nullable)
  - embedding: list[float] (768d, nomic)
```
partition: `evaluation_epoch=*/persona_id=*/run_id=*/`
**training は `evaluation_epoch=false` partition のみ読む** (contract で強制)

#### Sidecar metrics table (`metrics/`)
評価 metric は別 table。`run_id + persona_id + turn_idx` で raw に join。
```
schema:
  - run_id: str
  - persona_id: str (partition key)
  - turn_idx: int
  - tier: str  # "A" | "B" | "C"
  - metric_name: str
  - metric_value: float
  - metric_metadata: dict
```

**train/eval contamination 解消**: training pipeline が metric column に物理的にアクセスできない。
training-view contract: `raw_dialog/evaluation_epoch=false/` のみ読む

### F. 評価 epoch 分離 (DB6) → Run-level flag + 物理 partition + sidecar (HIGH-4 反映 統合)

- `evaluation_epoch: bool` を Run config 必須化、Default `False`
- Parquet partition で物理分離 (`evaluation_epoch=*/`)
- sidecar metrics table も同 partition 構造
- evaluation 頻度 policy (MEDIUM-4 反映):
  - **Tier A**: per turn (cheap、~50ms)
  - **Tier B**: per 100 turns (Vendi / IPIP-NEO / Big5 ICC)
  - **Tier C**: nightly offline batch (Prometheus 2 / G-Eval / FANToM-adapted)
  - 同時 GPU contention 回避: Tier C は autonomous run 停止時のみ

### G. Persona N=4 拡張時期 (DB7) → defer to M10 + synthetic heldout 4th persona (LOW-1 反映)

- Runtime N=4 は M10 まで完全 defer
- ただし **eval pipeline test には mocked 4th persona scenario を含める** (LOW-1)
- 評価系が 3 persona 専用に overfit するのを防ぐ
- agora 主体 YAML 雛形は M10 着手時に起草

### H. Adapter swap runbook (DB8) → SGLang `/load_lora_adapter` first

- SGLang `/load_lora_adapter` REST endpoint で adapter dynamic load
- multi-LoRA: `--max-loras N` + `--max-lora-rank R` 起動オプション
- pinned adapters: hot path persona は pin
- runbook 起草は **bounded Kant spike 完了後**、実測値 (latency / cold start / throughput) 込み

### I. Baseline drift gate (DB9) → **composite + bootstrap CI + 2-of-3 quorum** (HIGH-2 反映)

#### Primary composite per persona
各 persona の Tier B から 3 sub-metric を選定して composite:
- `vendi_score` (semantic kernel)
- `big5_stability_icc` (across-mode personality stability)
- `burrows_delta_to_reference` (persona-fit)

#### Statistical operationalization
- **Bootstrap CI** over turns/runs: each metric の 95% CI を持つ
- **Quorum rule**: 2-of-3 sub-metric が CI で baseline からネガティブ方向に regress
  → rollback fire
- **Single regression**: warning ログのみ、rollback しない

#### Defensive canary (守りの drift)
- self_rep > 0.15 OR cross_echo > 0.15 (any 1 trigger) → auto rollback (これは即座、CI 待たない)

#### Adoption gate (攻めの gate)
- **Initial run** (first LoRA application): floor 維持で許容 (warmup 認める)
- **Subsequent runs (≥2)**: 2-of-3 sub-metric が CI で baseline 上回り (positive direction)
  → adoption 確定。期待 effect size は **persona-conditional に bootstrap で決める**
  (5% 固定棄却、codex HIGH-2)
- **3 連続 run** で adoption 条件未達 → 当該 LoRA 設定 (rank / dataset) を破棄、再 spike

### J. 思想家らしさ評価系 framework (DB10) → 4-tier + persona-conditional + multi-channel

#### M9-B 内 deliverable: **specs only** (MEDIUM-1 反映)
M9-B では実装コードを出さず、以下の **spec ドキュメント**のみ deliverable:
- Tier A-D metric の interface 定義
- Parquet schema (raw + sidecar) 定義
- golden set 採取の technical spec
- Burrows' Delta reference corpus 整備計画
- LIWC license 評価 + OSS alternative (Empath / spaCy / 自作 dictionary) decision tree

#### Tier 階層 (research-evaluation-metrics.md ベース)

**Tier A (per-turn, cheap, ~50ms total)**:
- LIWC-22 OR Empath OR custom dictionary (license 確定後選定)
- Burrows' Delta to thinker reference (per-language、translation 別 baseline)
- MATTR
- semantic novelty (MPNet embedding distance)
- repetition_rate, cross_persona_echo_rate (既存)
- persona_contradiction_rate (NLI head, 新規)

**Tier B (per-100-turn, medium)**:
- Vendi Score (semantic kernel、200-turn rolling window)
- IPIP-NEO-120 via local 7B-Q4 (questionnaire administration)
- Big5 stability ICC across mode

**Tier C (per-session offline, expensive)**:
- Prometheus 2 rubric assessment (CharacterBench 6-aspect taxonomy で instantiate)
- G-Eval logit-weighted scoring (Wachsmuth Toulmin 5 dimension)
- FANToM-adapted ToM probe (chashitsu info-asymmetric minimal pair)
- ROSCOE on reasoning trace (informativeness + self-consistency)

**Tier D (sparse manual)**:
- FActScore-adapted against Kant/Nietzsche/Rikyu canonical corpus
- 専門家 qualitative review
- RoleEval-adapted biographical MCQ pre-gate

#### Persona-conditional gate
- Idea density: Kant HIGH 期待 / Rikyu LOW 期待 (低が persona-fit)
- Allusion rate: persona 別 target rate
- Vendi Score 解釈: persona の「思考の幅」依存

→ **gate 設計は absolute value ではなく persona-baseline からの bootstrap CI 偏差**

#### Golden set ステージング (MEDIUM-3 反映)
- M9-eval-system: **100/persona** seed (smoke test 用)
- LoRA 採用判定: **300/persona** acceptance threshold
- 学術発表時: **1000/persona** publication-grade

#### Multi-channel honest framing
- 「single thinker-likeness score」は採用しない (research-evaluation-metrics.md L326-349)
- formal benchmark = floor、proxy = exploratory、expert review = final
- LIWC OSS alternative (Empath / spaCy) は proxy であり LIWC 等価ではない (LOW-2 反映)
- Big-Five claim は LIWC 商用 license + validation あって初めて成立、proxy ベースの
  Big-Five claim は honest に避ける

## 数値 gate サマリ (final)

| Gate | 条件 | 動作 |
|---|---|---|
| **Trigger** | floor (self_rep≤0.10 AND echo≤0.10) AND (coverage 300/persona OR plateau 2-run<5% OR timebox 8 session) | LoRA 適用 fire |
| **Defensive canary** | self_rep>0.15 OR echo>0.15 (any 1) | 即時 auto rollback |
| **Adoption (initial run)** | floor 維持 | 採用 (warmup 認可) |
| **Adoption (run ≥2)** | 2-of-3 Tier B sub-metric (Vendi / Big5 ICC / Burrows Delta) が CI で baseline positive 方向 | 採用確定 |
| **Drift (post-LoRA)** | 2-of-3 Tier B sub-metric が CI で baseline negative 方向 | rollback |
| **3 連続 adoption 失敗** | 上記 adoption 条件 3 run 連続未達 | LoRA 設定破棄、再 spike |
| **VRAM** | base 5GB + 3 adapter ≤ 7GB total (N=3 維持) | M10 で N=4 再評価 |
| **eval ready** | golden baseline 採取 (3 persona × 5 run × 500 turn) + Tier B (Vendi+ICC) 実装完了 | LoRA adoption 判断 enabled |

## 実装順序 (final, 4 タスク並行構造)

### M9-B (本タスク, planning + spec only)
- [x] requirement.md + research + design v1/v2/comparison + codex review
- [ ] design-final.md (本書) commit + decisions.md + blockers.md + tasklist.md commit
- [ ] M9-eval-system + M9-C-spike + M9-C スコープ確定
- src/ 変更ゼロ

### M9-eval-system (新タスク, M9-B 後)
- Parquet pipeline 実装 (raw + sidecar 分離)
- Tier A 実装
- Tier B 実装 (Vendi / IPIP-NEO / Big5 stability ICC)
- golden baseline 採取 (3 persona × 5 run × 500 turn)
- golden set 整備 (100/persona seed → 300 acceptance ロードマップ)
- Tier C 一部 (Prometheus 2 + G-Eval) 実装
- evaluation pipeline 自動化 + dashboard

### M9-C-spike (新タスク, **M9-eval-system と並行**) ← codex 第 3 の道
**bounded, non-authoritative single-persona Kant spike**:
- SGLang `--enable-lora` + `/load_lora_adapter` 動作確認
- HF Transformers + PEFT (or unsloth) で Kant LoRA 学習 (rank=8, dataset 既存 dialog_turn)
- adapter swap latency / cold start / throughput 実測
- M9 → vLLM migration 必要性の measured 判断材料
- **adoption 判断は M9-eval-system 完成後 post-spike re-eval まで保留**
- 学習データは training-view (`evaluation_epoch=false`) のみ使用、汚染防止

### M9-C-adopt (旧 M9-C, M9-eval-system + M9-C-spike + 評価系 ready 達成後)
- adoption gate (DB9) で LoRA 採用判断
- 3 persona に展開
- 双方向 drift gate 実装
- adapter swap runbook 文書化
- M10 への handoff (N=4 拡張判断)

## codex review 反映マッピング

| Finding | 反映先 | Status |
|---|---|---|
| HIGH-1 (4-AND trigger) | DB4 → `floor AND (coverage OR plateau OR timebox)` | ✅ 反映 |
| HIGH-2 (offensive gate stat) | DB9 → composite + bootstrap CI + 2-of-3 quorum | ✅ 反映 |
| HIGH-3 (vLLM stale) | DB3 → SGLang-first | ✅ 反映 (大規模変更) |
| HIGH-4 (train/eval contamination) | DB5/DB6 → raw + sidecar 分離 | ✅ 反映 |
| MEDIUM-1 (M9-B scope) | DB10 → specs only 明文化 | ✅ 反映 |
| MEDIUM-2 (QLoRA "唯一現実解") | DB1 → conservative default + alternatives recorded | ✅ 反映 |
| MEDIUM-3 (golden set 100→300→1000) | DB10 → staging adopted | ✅ 反映 |
| MEDIUM-4 (eval frequency VRAM) | DB6 → Tier A/B/C frequency policy | ✅ 反映 |
| LOW-1 (synthetic 4th persona) | DB7 → eval test scenario として採用 | ✅ 反映 |

exec
/bin/zsh -lc "sed -n '1,180p' .steering/20260430-m9-eval-system/requirement.md && sed -n '560,700p' .steering/20260430-m9-eval-system/decisions.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# m9-eval-system

## 背景

- **直接の前段**: M9-B LoRA execution plan (PR #127 merged, main=`ff29ca2`) で 10 ADR
  (DB1-DB10) を v3 hybrid として確定。Codex `gpt-5.5 xhigh` の HIGH 4 件を反映し、
  vLLM full migration ではなく **SGLang-first + bounded Kant spike 並行** の第 3 の道を
  採用した。本タスクは「ADR は揃った、実装はこれから」という実装フェーズの起点。
- **位置付け**: M9 milestone は M9-A (event-boundary observability、PR #117-#124 完全
  クローズ済) に続き、M9-B → **M9-eval-system (本タスク)** + M9-C-spike (並行) →
  M9-C-adopt の順で進む。本タスクと M9-C-spike は独立進行し、M9-C-adopt で合流する。
- **問題意識**:
  1. LoRA fine-tuning の効果は「ペルソナ忠実度・心理的整合・stylometric 一致」を多軸で
     測らない限り検証できない。Tier 構造 (DB10) と sidecar metrics (DB5/DB6) の実装が
     無いまま spike を走らせると、empirical foundation 抜きの judgment になり LoRA
     採用判断 (M9-C-adopt) を支えられない。
  2. M9-C-adopt の前提条件として **Vendi / Big5 ICC / Burrows Delta の 3 sub-metric
     が bootstrap CI 計算 ready** であること (DB9 の 2-of-3 quorum 起動に必須)。
  3. golden baseline (LoRA 適用前の anchor) を採取しておかないと、後で adopt 判断に
     必要な「効果量」の絶対値が測れず、回帰検出も成立しない。

## ゴール

DB1-DB10 を破らない評価 pipeline を実装し、3 persona × 5 run × 500 turn の golden
baseline を採取して、M9-C-adopt の前提条件 (DB9 の sub-metric 3 個が bootstrap CI 計算
ready) を満たす状態にする。

## スコープ

### 含むもの

- **Tier 0** (DB5/DB6):
  - `raw_dialog` Parquet (metric-free): turn id / agent / persona / mode / utterance /
    timestamp / reasoning trace のみ。LIWC やスコア類は混入させない (contamination 防止)。
  - `metrics` sidecar Parquet: turn id を join key に Tier A/B/C のスコアを格納。
  - 両者の **物理分離**を契約として固定 (path 規約 + schema validation)。
- **Tier A** per-turn metric (DB10):
  - LIWC **alternative** (LIWC 商用は license 評価で defer/adopt 判定)
  - Burrows Delta (function word frequency vector cosine)
  - MATTR (Moving Average Type-Token Ratio、ウィンドウ 100)
  - semantic novelty (embedding 距離による直前 N turn からの離脱)
  - NLI contradiction (簡易 entailment classifier)
- **Tier B** per-100-turn metric (DB10):
  - Vendi Score (diversity)
  - IPIP-NEO 短縮版 self-report (local 7B-Q4 で agent に質問・回答させる)
  - Big5 stability (across 5 run の ICC)
- **Tier C 一部** (DB10):
  - Prometheus 2 (open judge LLM、bias mitigation あり)
  - G-Eval (chain-of-thought 評価)
  - **nightly offline** で走らせる (実時間 inference に背負わせない、DB6)
- **golden baseline 採取**: 3 persona (Kant / Nietzsche / Rikyu) × 5 run × 500 turn。
- **golden set 整備**: 100 prompt/persona の seed セット。acceptance 300/persona は別 phase。
- **evaluation pipeline 自動化**: ingest → tier 別 metric 計算 → bootstrap CI →
  dashboard。
- **bootstrap CI + 2-of-3 quorum** (DB9) の sub-metric 3 個 (Vendi / Big5 ICC /
  Burrows Delta) が計算 ready 状態に到達。
- **LIWC license 評価**を決着させ、`.steering/20260430-m9-b-lora-execution-plan/blockers.md`
  の defer 項目を 1 件 close。

### 含まないもの

- M9-C-spike (SGLang LoRA bounded Kant spike) — 別 `/start-task m9-c-spike` で並行進行。
- M9-C-adopt の判断そのもの — 本タスクは前提条件を整えるところまで。
- LoRA training pipeline 実装 — M9-D で扱う。
- acceptance 300/persona の golden set 拡張 — 別 phase に後送。
- LIWC 商用ライセンスの契約事務 (本タスクは「alternative で行くか商用採用か」の
  決着まで。契約手続きが必要なら別タスク)。
- 既存 contracts/ schema の破壊的変更 — sidecar 追加で済むなら additive のみ。

## 受け入れ条件

- [x] `design.md` 冒頭に **Hardware allocation 表** が存在し、MacBook (master/dev) と
      G-GEAR (実行機) の subtask 工数 + GPU/VRAM 要件 + 同期点が明示されている
      (`design-final.md` Hardware allocation 節、Codex HIGH-3 で P3a / P3a-decide 追加)
- [x] `design.md` (→ `design-final.md`) / `decisions.md` (ME-1〜ME-6) /
      `tasklist.md` (P0a-P7 + closure 展開、`[Mac]`/`[GG]`/`[Mac→GG]` tag 付与) の
      3 点セット完成
- [ ] DB5 (raw + sidecar 物理分離) を破る実装が無いこと (schema validation + path 規約) —
      P0b/P0c 実装で確認、Codex HIGH-1 反映で **sentinel 動的 contract** + grep gate の
      4 層 defense
- [ ] DB6 (Tier A per-turn / B per-100 / C nightly offline 頻度 policy) を守る実装 —
      P1a-P6 実装で確認
- [ ] DB9 (bootstrap CI + 2-of-3 quorum) の sub-metric 3 個 (Vendi / Big5 ICC /
      Burrows Delta) が **bootstrap CI 計算 ready** (M9-C-adopt の前提) — P5 完了時、
      Codex HIGH-2 で hierarchical bootstrap 採用
- [x] LIWC license 評価が決着 (採用/alternative のいずれか確定、`blockers.md` の
      defer 項目 1 件 close) — **Option D 確定 / 2026-04-30 P0a で M9-B
      `blockers.md` "LIWC 商用 license の最終可否判定" を CLOSED に Edit 済**
- [x] Codex `gpt-5.5 xhigh` independent review を Plan 確定前に挟み、HIGH 全件反映 /
      MEDIUM 採否を `decisions.md` に記録 / LOW を `blockers.md` に defer
      (HIGH 5 件 → `design-final.md`、MEDIUM 6 件 → `decisions.md` ME-1〜6、LOW-1 →
      `blockers.md`)
- [ ] golden baseline (3 persona × 5 run × 500 turn) が採取され、Parquet として
      永続化されている — P3 完了時 (G-GEAR overnight×2)
- [x] `tasklist.md` の各 checkbox に `[Mac]` / `[GG]` / `[Mac→GG]` tag が付与されている
- [ ] `git diff` が scope に整合 (Tier 0/A/B/C 一部 実装 + golden 採取コードのみ。
      LoRA training や M9-C-spike の混入無し) — closure 時に確認

## 関連ドキュメント

### M9-B 直接前段 (Read 必須)

- `.steering/20260430-m9-b-lora-execution-plan/design-final.md` — v3 hybrid、10 軸 確定済
- `.steering/20260430-m9-b-lora-execution-plan/decisions.md` — DB1-DB10、5 要素フォーマット
- `.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md` — 6 系統 30+ metric
- `.steering/20260430-m9-b-lora-execution-plan/blockers.md` — LIWC license / Burrows
  multi-lang / judge bias mitigation 等の defer 項目
- `.steering/20260430-m9-b-lora-execution-plan/tasklist.md` Phase B 節 (M9-eval-system tasklist)

### プロジェクト一般

- `docs/architecture.md` — Tier 構造 / sidecar / contracts/ レイヤー位置付け
- `docs/development-guidelines.md` — Parquet 規約 / pandas vs polars 方針
- `docs/glossary.md` — Tier 0/A/B/C / Vendi / Burrows Delta / IPIP-NEO 等の用語

## 運用メモ

- **タスク種別**: その他 (実装フェーズの起点で、設計判断と多面的実装を含む。
  単一 `/add-feature` 等には収まらない)
- **破壊と構築（/reimagine）適用**: **Yes**
- **理由**: 以下の architecture 判断を含むため、Plan mode 内で `/reimagine` を発動して
  初回案を意図的に破棄し、ゼロから再生成案と比較する:
  1. raw + sidecar 分離方式の物理表現 (Parquet 構造 / path 規約 / join 戦略の代替案)
  2. LIWC alternative の選定 (open dictionary / 自前構築 / multi-lang 戦略)
  3. golden baseline の採取設計 (seed 選定 / run 独立性 / contamination 分離契約)
  4. Tier C nightly offline の実行基盤 (cron / queue / cost 上限)
- **Codex independent review 必須**: M9-B で Codex web search が SGLang v0.3+ multi-LoRA を
  提示し Claude の stale 認識を補正した empirical evidence あり。Plan 確定前に
  `codex-review-prompt.md` 起草 → `codex exec --skip-git-repo-check` →
  `codex-review.md` verbatim 保存。HIGH は実装前必反映、MEDIUM は decisions.md、
  LOW は blockers.md に持ち越し可。
- **Plan mode + Opus**: 高難度設計 (Parquet schema / Tier A-D framework / golden set
  methodology / contamination 分離契約) のため Plan mode 必須、Opus で設計確定まで。
- **context 管理**: 50% 超で `/smart-compact`、Plan 承認時 30% 超なら `/clear` →
  次セッションで `design-final.md` を Read してから実装入り。
- **planning purity**: Plan 承認前に `src/` を触らない。
- **並行タスク**: M9-C-spike は別 `/start-task m9-c-spike` で起こす。両者独立、
  M9-C-adopt で合流。
26 deselected): 本 PR では **1251 passed (+3)** / 31 skipped / 27 deselected (+1、
CLI test の eval marker 経由)。dialog test 3 件は default CI に組み込まれ、CLI
test 1 件は `-m eval` で別途検証 (single-shot 実測 PASS 確認済)。

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
  §ブロッカー予測 B-1 を本 amendment に整合させて修正 (同 PR で同時 merge)
- 旧 re-open 条件 (上記、≤55 / ≥80) は **本 amendment の trigger zone table で
  上書き**、condition-aware に再定義

---

## ME-summary

- 本 ADR **9 件** で Codex `gpt-5.5 xhigh` **6 回** review (2026-04-30 design.md MEDIUM 6 +
  LOW 1 / 2026-05-01 LOW-1 RoleEval MEDIUM 5 + LOW 2 / 2026-05-01 P3a-decide gating

exec
/bin/zsh -lc "sed -n '700,880p' src/erre_sandbox/schemas.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,220p' src/erre_sandbox/cognition/prompting.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,220p' src/erre_sandbox/cognition/belief.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,140p' src/erre_sandbox/cognition/parse.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
    Emitted by ``world/tick.py`` when the agent enters the salient radius of
    a named prop (e.g. a tea bowl within the chashitsu, a lectern in the
    study). The open-vocabulary ``prop_kind`` keeps the wire contract stable
    as new assets are added — downstream code should treat unknown kinds as
    generic environmental salience rather than switching exhaustively.
    """

    event_type: Literal["affordance"] = "affordance"
    prop_id: str = Field(..., description="Stable scene-level identifier.")
    prop_kind: str = Field(
        ...,
        description=(
            'Free-form kind label (e.g. "tea_bowl", "lectern", "stone_lantern"). '
            "Downstream code should not switch exhaustively on this value."
        ),
    )
    zone: Zone
    distance: float = Field(
        ...,
        ge=0.0,
        description="Distance in metres from the agent to the prop.",
    )
    salience: _Unit = 0.5


class ProximityEvent(_ObservationBase):
    """The agent's distance to another agent crossed a threshold (M6).

    Emitted once per crossing edge — entering or leaving a radius — rather
    than continuously, so the observation stream is not flooded by co-walking
    pairs. ``distance_prev`` and ``distance_now`` both refer to the current
    physics tick's pair distance and its immediately prior reading.
    """

    event_type: Literal["proximity"] = "proximity"
    other_agent_id: str
    distance_prev: float = Field(..., ge=0.0)
    distance_now: float = Field(..., ge=0.0)
    crossing: Literal["enter", "leave"]


class TemporalEvent(_ObservationBase):
    """The simulated time-of-day period rolled over (M6).

    Rolled once per period boundary (e.g. ``morning`` → ``noon``). The FSM
    may use this to bias dwell-time or trigger circadian-scheduled mode
    shifts; the LLM prompt surfaces it so the agent can reason about the
    phase of the day (e.g. Kant's regular afternoon walk).
    """

    event_type: Literal["temporal"] = "temporal"
    period_prev: TimeOfDay
    period_now: TimeOfDay


class BiorhythmEvent(_ObservationBase):
    """A fatigue / hunger / stress signal crossed a threshold (M6).

    Emitted by ``cognition/cycle.py`` when the CSDG half-step physical /
    cognitive update pushes one of the tracked signals across a policy
    threshold. Unlike :class:`InternalEvent`, this variant is structured:
    downstream code can switch on ``signal`` and ``threshold_crossed`` to
    drive UI / FSM reactions without parsing the freeform ``content`` of
    an ``InternalEvent``.
    """

    event_type: Literal["biorhythm"] = "biorhythm"
    signal: Literal["fatigue", "hunger", "stress"]
    level_prev: _Unit
    level_now: _Unit
    threshold_crossed: Literal["up", "down"]


Observation: TypeAlias = Annotated[
    PerceptionEvent
    | SpeechEvent
    | ZoneTransitionEvent
    | ERREModeShiftEvent
    | InternalEvent
    | AffordanceEvent
    | ProximityEvent
    | TemporalEvent
    | BiorhythmEvent,
    Field(discriminator="event_type"),
]
"""Discriminated union of all observation event types."""


# =============================================================================
# §6 Memory
# =============================================================================


class MemoryEntry(BaseModel):
    """A single memory row in the agent's Memory Stream.

    Pure domain type: embedding vectors and search scores are the memory-store
    layer's concern (T10) and intentionally absent here so backends can be
    swapped (sqlite-vec → Qdrant) without breaking the wire contract.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    agent_id: str
    kind: MemoryKind
    content: str
    importance: _Unit
    created_at: datetime = Field(default_factory=_utc_now)
    last_recalled_at: datetime | None = None
    recall_count: int = Field(default=0, ge=0)
    source_observation_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class ReflectionEvent(BaseModel):
    """Snapshot of one reflection step (M4 foundation).

    The cognition cycle distils a window of recent episodic entries into a
    single summary at reflection-trigger time. This struct is the on-wire /
    in-process record of that event, independent of both the trigger policy
    (decided in ``m4-cognition-reflection``) and the semantic-memory storage
    backend (decided in ``m4-memory-semantic-layer``).
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    tick: int = Field(..., ge=0)
    summary_text: str = Field(
        ...,
        description="LLM-distilled reflection content; UTF-8, not length-capped here.",
    )
    src_episodic_ids: list[str] = Field(
        default_factory=list,
        description="Source ``MemoryEntry.id`` values folded into the summary.",
    )
    created_at: datetime = Field(default_factory=_utc_now)


class TriggerEventTag(BaseModel):
    """1-line "起点 event" tag attached to a :class:`ReasoningTrace` (M9-A).

    Lets the Godot ``ReasoningPanel`` show "this trace was a reaction to X"
    and the ``BoundaryLayer`` pulse the originating zone, without forcing
    consumers to scan the raw observation stream. Cognition cycle picks one
    winner per tick by priority (zone_transition > affordance > proximity >
    biorhythm > erre_mode_shift > temporal > internal > speech > perception);
    same-tick losers in the spatial set are surfaced as ``secondary_kinds``
    for a "+N more" UI hint.

    Wire contract: ``ref_id`` is structured (zone_transition→``to_zone``,
    affordance→``prop_id``, proximity→``other_agent_id``, otherwise ``None``).
    Display text (e.g. "Linden-Allee に入った") is composed *client-side* in
    ``godot_project/scripts/i18n/Strings.gd`` so backend stays free of i18n.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "zone_transition",
        "affordance",
        "proximity",
        "temporal",
        "biorhythm",
        "erre_mode_shift",
        "internal",
        "speech",
        "perception",
    ] = Field(
        ...,
        description=(
            "Event_type of the winning observation that triggered this "
            "trace. Must match one of the nine :class:`Observation` "
            "discriminator values."
        ),
    )
    zone: Zone | None = Field(
        default=None,
        description=(
            "Zone where the trigger occurred. None for non-spatial kinds "

 succeeded in 0ms:
"""Pure string-building for the cognition cycle's LLM messages.

Split into three stages (persona-erre skill §ルール 3):

* ``_COMMON_PREFIX`` — shared across every agent / tick. Placed first so
  SGLang's RadixAttention (M7+) can reuse its KV cache across personas.
* ``build_system_prompt`` — persona-specific + current-state tail.
* ``build_user_prompt`` — observations + retrieved memories + the JSON
  response contract consumed by :func:`cognition.parse.parse_llm_plan`.

All three are side-effect-free and deterministic for a fixed input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.memory import RankedMemory
    from erre_sandbox.schemas import AgentState, Observation, PersonaSpec


_COMMON_PREFIX: Final[str] = (
    "You are an autonomous agent living in ERRE-Sandbox, a 3D world with "
    "five zones (study / peripatos / chashitsu / agora / garden). Each tick "
    "represents ten seconds of wall-clock time. Respond in character, "
    "following the cognitive habits of the persona described below. "
    "The ``utterance`` field MUST be written in Japanese (日本語) so the "
    "researcher observing the 3D scene can read it at a glance — "
    "original-language key terms (Kant のドイツ語/ラテン語, Nietzsche の"
    "ドイツ語など) may appear parenthetically inside the Japanese sentence. "
    "Keep utterances under 80 Japanese characters."
)

RESPONSE_SCHEMA_HINT: Final[str] = (
    "Respond with a SINGLE JSON object matching this schema (all deltas in "
    "[-1.0, 1.0], importance_hint in [0.0, 1.0]; use null for optional fields "
    "you intentionally skip). The last three keys (salient / decision / "
    "next_intent) are the reasoning trace shown to the researcher observing "
    "you — keep each under 80 characters of natural Japanese and be honest "
    "about why you act; leave them null only if genuinely not applicable:\n"
    "{\n"
    '  "thought": "internal monologue",\n'
    '  "utterance": "speech bubble text or null",\n'
    '  "destination_zone": "study|peripatos|chashitsu|agora|garden|null",\n'
    '  "animation": "walk|idle|sit_seiza|bow|null",\n'
    '  "valence_delta": 0.0,\n'
    '  "arousal_delta": 0.0,\n'
    '  "motivation_delta": 0.0,\n'
    '  "importance_hint": 0.5,\n'
    '  "salient": "what you found most salient this tick or null",\n'
    '  "decision": "the one-sentence reason for your action or null",\n'
    '  "next_intent": "what you plan to do next or null"\n'
    "}\n"
    "Return ONLY the JSON object. No prose outside the braces."
)


def _format_habit_line(habit_description: str, flag: str) -> str:
    return f"- {habit_description} [{flag}]"


def _format_persona_block(persona: PersonaSpec) -> str:
    habits = "\n".join(
        _format_habit_line(h.description, h.flag.value)
        for h in persona.cognitive_habits
    )
    zones = ", ".join(z.value for z in persona.preferred_zones)
    p = persona.personality
    # Big Five + ERRE-specific traits as two compact lines so three agents
    # sharing one scene read as three biologies instead of one. Numeric form
    # (not adjectives) keeps the prompt short and leaves the natural-language
    # interpretation to the LLM — giving each persona's own voice room to
    # colour identical 0.8 differently. See M7 First PR D4 in decisions.md.
    big_five = (
        f"openness={p.openness:.2f} conscientiousness={p.conscientiousness:.2f} "
        f"extraversion={p.extraversion:.2f} agreeableness={p.agreeableness:.2f} "
        f"neuroticism={p.neuroticism:.2f}"
    )
    aesthetic = f"wabi={p.wabi:.2f} ma_sense={p.ma_sense:.2f}"
    return (
        f"Persona: {persona.display_name} ({persona.era}).\n"
        f"Personality (Big Five, [0,1]): {big_five}.\n"
        f"Aesthetic sensibility: {aesthetic}.\n"
        f"Preferred zones: {zones}.\n"
        f"Cognitive habits (fact / legend / speculative):\n{habits}"
    )


def _format_state_tail(agent: AgentState) -> str:
    zone = agent.position.zone.value
    erre_mode = agent.erre.name.value
    cog = agent.cognitive
    phy = agent.physical
    return (
        f"Current tick: {agent.tick}.\n"
        f"Location: {zone}. ERRE mode: {erre_mode}.\n"
        f"Physical — sleep_quality={phy.sleep_quality:.2f}, "
        f"physical_energy={phy.physical_energy:.2f}, "
        f"fatigue={phy.fatigue:.2f}, cognitive_load={phy.cognitive_load:.2f}.\n"
        f"Cognitive — valence={cog.valence:.2f}, arousal={cog.arousal:.2f}, "
        f"motivation={cog.motivation:.2f}, stress={cog.stress:.2f}."
    )


def build_system_prompt(persona: PersonaSpec, agent: AgentState) -> str:
    """Assemble the system prompt in three stages (common / persona / tail).

    Ordering is load-bearing: the common prefix comes first so downstream
    KV caches can share it across personas (MVP Ollama does not exploit
    this, but SGLang at M7 will).
    """
    return "\n\n".join(
        [
            _COMMON_PREFIX,
            _format_persona_block(persona),
            _format_state_tail(agent),
        ],
    )


def _one_line(text: str, limit: int = 160) -> str:
    single = " ".join(text.split())
    if len(single) <= limit:
        return single
    return single[: limit - 1] + "…"


def format_memories(memories: Sequence[RankedMemory], max_items: int = 8) -> str:
    """Render *memories* as a bullet list sorted by strength (high first)."""
    if not memories:
        return "(no relevant memories)"
    ranked = sorted(memories, key=lambda m: m.strength, reverse=True)[:max_items]
    lines: list[str] = []
    for m in ranked:
        kind = m.entry.kind.value
        body = _one_line(m.entry.content)
        lines.append(f"- [{kind} strength={m.strength:.2f}] {body}")
    return "\n".join(lines)


def _observation_line(obs: Observation) -> str:  # noqa: PLR0911 — discriminator dispatch
    if obs.event_type == "perception":
        return _one_line(
            f"[perception] {obs.content} (intensity={obs.intensity:.2f})",
        )
    if obs.event_type == "speech":
        return _one_line(f"[speech by {obs.speaker_id}] {obs.utterance}")
    if obs.event_type == "zone_transition":
        frm = obs.from_zone.value
        to = obs.to_zone.value
        return f"[zone_transition] {frm} -> {to}"
    if obs.event_type == "erre_mode_shift":
        prev = obs.previous.value
        curr = obs.current.value
        return f"[erre_mode_shift] {prev} -> {curr} ({obs.reason})"
    if obs.event_type == "internal":
        return _one_line(
            f"[internal hint={obs.importance_hint:.2f}] {obs.content}",
        )
    if obs.event_type == "affordance":
        return _one_line(
            f"[affordance] {obs.prop_kind}#{obs.prop_id} in {obs.zone.value} "
            f"(distance={obs.distance:.1f}m, salience={obs.salience:.2f})",
        )
    if obs.event_type == "proximity":
        return (
            f"[proximity {obs.crossing}] other={obs.other_agent_id} "
            f"{obs.distance_prev:.1f}m -> {obs.distance_now:.1f}m"
        )
    if obs.event_type == "temporal":
        return f"[temporal] {obs.period_prev.value} -> {obs.period_now.value}"
    if obs.event_type == "biorhythm":
        return (
            f"[biorhythm {obs.signal}:{obs.threshold_crossed}] "
            f"{obs.level_prev:.2f} -> {obs.level_now:.2f}"
        )
    return "[unknown] (unformatted)"


_MAX_PROXIMITY_PER_TICK: Final[int] = 2
"""Upper bound on :class:`~erre_sandbox.schemas.ProximityEvent` items kept in
the user prompt per tick (M6-A-2b).

Rationale: with ``recent_limit=10`` a chaotic multi-agent scene can easily
fill every slot with proximity crossings (two agents pacing around each
other cross twice per round), pushing the more rare signals
(ZoneTransition / Biorhythm / ERREModeShift) out of the window entirely.
Keeping only the two most-recent proximity events preserves the
"somebody is near / just walked off" cue without starving the rest of the
stream."""


def _clamp_proximity(
    recent: Sequence[Observation],
    max_proximity: int = _MAX_PROXIMITY_PER_TICK,
) -> list[Observation]:
    """Drop all but the last ``max_proximity`` :class:`ProximityEvent`.

    Preserves the relative order of every non-proximity observation and of
    the surviving proximity entries. Implemented as a single left-to-right
    pass after counting total proximity entries so the surviving window is
    the *latest* ``max_proximity``, which is what the LLM should reason
    about (recent crossings matter more than ancient co-walks).
    """
    total_proximity = sum(1 for o in recent if o.event_type == "proximity")
    if total_proximity <= max_proximity:
        return list(recent)
    drop_before = total_proximity - max_proximity
    skipped = 0
    out: list[Observation] = []
    for o in recent:
        if o.event_type == "proximity" and skipped < drop_before:
            skipped += 1
            continue
        out.append(o)
    return out


 succeeded in 0ms:
"""LLM output parsing — JSON plan extraction with validation.

The LLM is prompted (see :mod:`cognition.prompting`) to return a single JSON
object matching :class:`LLMPlan`. This module is the single place where that
contract is enforced: malformed output collapses to ``None`` so the caller
(``cognition.cycle.CognitionCycle.step``) can fall back to the
"continue current action" path declared by ``docs/functional-design.md``
§2 error-condition row.

The parser tolerates common LLM idiosyncrasies (code fences, surrounding
prose, trailing whitespace) but does NOT try to salvage broken JSON — once
we mix forgiving heuristics and Pydantic validation we lose the ability to
tell "model misbehaved" from "adapter misbehaved".
"""

from __future__ import annotations

import json
import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# ``Zone`` stays a runtime import: it types :attr:`LLMPlan.destination_zone`
# and Pydantic resolves field types at model-build time, not under
# TYPE_CHECKING. noqa is intentional.
from erre_sandbox.schemas import Zone  # noqa: TC001

# Match ```json ... ``` or ``` ... ``` code fences (both common in LLM replies).
_FENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"```(?:json)?\s*(.*?)\s*```",
    re.DOTALL | re.IGNORECASE,
)

MAX_RAW_PLAN_BYTES: Final[int] = 64 * 1024
"""Upper bound on raw LLM text before we refuse to parse (security M1).

Ollama with an unbounded ``num_predict`` has been observed producing
multi-MB loops. We stay well under Python's ``json.loads`` practical memory
footprint and Ollama's realistic output. If an honest response ever grows
past this, the plan schema has outgrown its design and needs a redesign,
not a larger buffer.
"""


class LLMPlan(BaseModel):
    """One tick of agent action parsed out of the LLM's JSON response.

    All fields are bounded so a mis-configured prompt / persona can never
    produce an out-of-range ``_Signed`` that would later fail Pydantic
    validation deep inside :mod:`cognition.state`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    thought: str = Field(..., description="Internal monologue (may be persisted).")
    utterance: str | None = Field(
        default=None,
        description="Speech bubble content; ``None`` = stay silent.",
    )
    destination_zone: Zone | None = Field(
        default=None,
        description="Zone to walk to; ``None`` = stay put.",
    )
    animation: str | None = Field(
        default=None,
        description="Animation tag such as 'walk' / 'idle' / 'sit_seiza'.",
    )
    valence_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    arousal_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    motivation_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    importance_hint: float = Field(default=0.5, ge=0.0, le=1.0)
    # M6-A-3: optional reasoning rationale. Absence must not fail validation —
    # stable Ollama output is never 100% for added fields, and the plan's
    # action contract is independent of the reasoning trace.
    salient: str | None = Field(
        default=None,
        description="What the agent noticed as most salient this tick (xAI).",
    )
    decision: str | None = Field(
        default=None,
        description="One-sentence rationale behind the chosen action (xAI).",
    )
    next_intent: str | None = Field(
        default=None,
        description="Forward-looking intent surfaced for upcoming ticks (xAI).",
    )


def _find_matching_brace(text: str, start: int) -> int | None:
    r"""Return index of the ``}`` matching the ``{`` at *start*, or ``None``.

    Walks the string character by character, honouring double-quoted strings
    and ``\"`` escapes so embedded JSON strings don't throw off the depth.
    """
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


def _extract_json_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` block in *text*, or ``None``."""
    fence_match = _FENCE_RE.search(text)
    haystack = fence_match.group(1) if fence_match else text

    start = haystack.find("{")
    if start == -1:
        return None
    end = _find_matching_brace(haystack, start)
    if end is None:
        return None
    return haystack[start : end + 1]


def parse_llm_plan(text: str) -> LLMPlan | None:
    """Extract and validate an :class:`LLMPlan` from raw LLM text.

    Returns ``None`` on any failure — including missing JSON, malformed JSON,
    Pydantic validation error, or input exceeding :data:`MAX_RAW_PLAN_BYTES`
    (see security M1) — so the caller can deterministically route all of
    these to a single fallback branch.

 succeeded in 0ms:
"""Belief promotion bridge from RelationshipBond to SemanticMemoryRecord (M7δ).

The CSDG 2-layer memory pattern (short-term / long-term) is realised in
δ as a one-way bridge: when an agent's :class:`RelationshipBond` toward
a peer crosses an ``|affinity|`` threshold *and* the dyad has had at
least ``min_interactions`` turns, the bond is distilled into a typed
:class:`SemanticMemoryRecord` (``belief_kind`` × ``confidence``). The
record is upserted with a deterministic id so subsequent crossings
overwrite the prior belief in place rather than spamming the semantic
table.

Threshold / N calibration is exercised in
``tests/test_cognition/test_relational_simulation.py``: a 30-line
recurrence simulation iterates the M7δ semi-formula over 20 turns × 3
trait pairs and confirms saturation lands at turns 8-14, well inside
the live G-GEAR 90-120s window. The calibration values
(``threshold=0.45`` / ``min_interactions=6``) are also documented in
``.steering/20260426-m7-slice-delta/design-final.md`` (Axis 3).

This module is intentionally pure — :func:`maybe_promote_belief` builds
the record but does not write it to storage. The bootstrap relational
sink owns the synchronous ``_upsert_semantic_sync`` call so the layer
boundary (``cognition/`` does not import ``memory/``) is preserved.

See Also:
--------
* :class:`erre_sandbox.schemas.SemanticMemoryRecord` for the typed
  ``belief_kind`` and ``confidence`` fields (M7δ C1, schemas.py:752+).
* :mod:`erre_sandbox.cognition.relational` for the formula that drives
  ``RelationshipBond.affinity`` toward the saturation regime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

from erre_sandbox.cognition.relational import AFFINITY_UPPER
from erre_sandbox.schemas import SemanticMemoryRecord

if TYPE_CHECKING:
    from erre_sandbox.schemas import PersonaSpec, RelationshipBond


BELIEF_THRESHOLD: Final[float] = 0.45
"""``|affinity|`` floor for belief promotion (M7δ Axis 3 calibration).

Picked from the simulation in ``test_relational_simulation.py`` so that
saturating dyads cross around turn 8-14 — comfortably inside the 90-120s
live G-GEAR run and below the trivial-noise band where decay alone
would push affinity past the floor. v1 had asserted 0.5; v2's
simulation-driven 0.45 was adopted (design-final Phase 3 row "3").
"""

BELIEF_MIN_INTERACTIONS: Final[int] = 6
"""Minimum ``ichigo_ichie_count`` before a bond can be distilled.

Guards against a single high-magnitude antagonism turn (kant↔nietzsche
fires -0.255 on turn 1) immediately spawning a "clash" belief: real
beliefs need a small history of repeated interaction. v1 picked N=5;
v2's N=6 was adopted to match the simulation-derived saturation window.
"""

_TRUST_FLOOR: Final[float] = 0.70
"""Above this ``|affinity|`` magnitude the belief is "trust" / "clash"."""

BeliefKind = Literal["trust", "clash", "wary", "curious", "ambivalent"]
"""Mirrors the ``belief_kind`` Literal on :class:`SemanticMemoryRecord`."""


def _classify_belief(affinity: float) -> BeliefKind:
    """Map a saturated ``affinity`` value to a typed belief kind.

    The thresholds are split so that ``trust`` / ``clash`` mark strongly
    consolidated beliefs, while ``curious`` / ``wary`` mark beliefs that
    have crossed the promotion threshold but have not yet reached the
    high-confidence regime. ``ambivalent`` is reserved for future
    history-aware classification (oscillating beliefs); the M7δ
    promotion path never fires it because ``|affinity| > threshold`` is
    required.
    """
    if affinity >= _TRUST_FLOOR:
        return "trust"
    if affinity > 0.0:
        return "curious"
    if affinity <= -_TRUST_FLOOR:
        return "clash"
    return "wary"


def _compute_confidence(
    affinity: float,
    interactions: int,
    *,
    min_interactions: int,
) -> float:
    """``min(1.0, |affinity|/AFFINITY_UPPER * (interactions/min_interactions))``.

    Combines belief magnitude with interaction-count evidence. A bond at
    ``|affinity|=0.5`` after exactly ``min_interactions`` turns yields
    confidence 0.5; the same magnitude after 12 turns yields ~1.0 (the
    additional interactions strengthen the same belief).
    """
    if min_interactions <= 0:
        # Defensive: caller passed a non-positive threshold; fall back to
        # magnitude alone so we never divide by zero.
        return min(1.0, abs(affinity) / AFFINITY_UPPER)
    raw = (abs(affinity) / AFFINITY_UPPER) * (
        float(interactions) / float(min_interactions)
    )
    return min(1.0, raw)


def _belief_record_id(agent_id: str, other_agent_id: str) -> str:
    """Deterministic id so subsequent promotions overwrite the prior belief.

    Encoding ``(agent, other)`` rather than the bond's hash means a
    refreshed promotion always lands on the same row regardless of how
    the bond's affinity drifted between calls. Keeps the semantic table
    bounded by ``O(agent_pairs)`` rather than ``O(promotions)``.
    """
    return f"belief_{agent_id}__{other_agent_id}"


def _belief_summary(
    addressee_persona: PersonaSpec,
    kind: BeliefKind,
) -> str:
    """Render a human-readable belief summary for the SemanticMemoryRecord.

    Kept minimal — m8-affinity-dynamics Critics will query
    ``belief_kind`` directly so this string is mainly for the Godot
    ReasoningPanel and reflection log readability.
    """
    verb = {
        "trust": "trust",
        "curious": "feel drawn to",
        "wary": "feel wary of",
        "clash": "clash with",
        "ambivalent": "feel ambivalent toward",
    }[kind]
    return f"belief: I {verb} {addressee_persona.display_name}"


def maybe_promote_belief(
    bond: RelationshipBond,
    *,
    agent_id: str,
    persona: PersonaSpec,
    addressee_persona: PersonaSpec,
    threshold: float = BELIEF_THRESHOLD,
    min_interactions: int = BELIEF_MIN_INTERACTIONS,
) -> SemanticMemoryRecord | None:
    """Build a :class:`SemanticMemoryRecord` if ``bond`` qualifies for promotion.

    Returns ``None`` (no promotion) when either gate fails:

    * ``abs(bond.affinity) < threshold`` — bond hasn't reached belief
      magnitude yet.
    * ``bond.ichigo_ichie_count < min_interactions`` — too few turns to
      treat as a stable belief.

    When both gates pass, returns a populated record with a deterministic
    id so the caller's :meth:`MemoryStore.upsert_semantic` overwrites
    any prior promotion for the same dyad. The caller is responsible for
    persistence; this function is pure (no I/O).

    Args:
        bond: The :class:`RelationshipBond` *after* the apply_affinity_delta
            update for the current turn.
        agent_id: The bond-holder's ``agent_id`` (the SemanticMemoryRecord
            row is scoped to this id).
        persona: The bond-holder's :class:`PersonaSpec` (currently only
            used by the summary template; kept on the signature so future
            iterations can scale ``confidence`` by neuroticism etc.).
        addressee_persona: The other party's :class:`PersonaSpec`. Provides
            ``display_name`` for the summary.
        threshold: Override the module default ``BELIEF_THRESHOLD``. Tests
            use this to exercise the gate without touching the constant.
        min_interactions: Override ``BELIEF_MIN_INTERACTIONS``.

    Returns:
        A :class:`SemanticMemoryRecord` ready for ``upsert_semantic``, or
        ``None`` when the bond does not yet qualify.
    """
    del persona  # reserved for future scaling factors; unused in δ MVP.
    if abs(bond.affinity) < threshold:
        return None
    if bond.ichigo_ichie_count < min_interactions:
        return None
    kind = _classify_belief(bond.affinity)
    confidence = _compute_confidence(
        bond.affinity,
        bond.ichigo_ichie_count,
        min_interactions=min_interactions,
    )
    return SemanticMemoryRecord(
        id=_belief_record_id(agent_id, bond.other_agent_id),
        agent_id=agent_id,
        embedding=[],  # belief promotions ship without embeddings; m8 may add.
        summary=_belief_summary(addressee_persona=addressee_persona, kind=kind),
        origin_reflection_id=None,
        belief_kind=kind,
        confidence=confidence,
    )


__all__ = [
    "BELIEF_MIN_INTERACTIONS",
    "BELIEF_THRESHOLD",
    "BeliefKind",
    "maybe_promote_belief",
]

exec
/bin/zsh -lc "sed -n '220,420p' src/erre_sandbox/cognition/prompting.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '880,1040p' src/erre_sandbox/schemas.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:


def build_user_prompt(
    observations: Sequence[Observation],
    memories: Sequence[RankedMemory],
    recent_limit: int = 10,
) -> str:
    """Build the user message: recent observations + memories + JSON contract.

    ``recent_limit`` (default 10 — widened from 5 in M6-A-2b) is the window
    of the tail-most observations fed to the LLM. After slicing, the window
    is rebalanced by :func:`_clamp_proximity` so a chatty proximity stream
    cannot crowd out rarer signals.
    """
    recent = _clamp_proximity(list(observations)[-recent_limit:])
    obs_block = (
        "\n".join(_observation_line(o) for o in recent)
        if recent
        else "(nothing happened)"
    )
    mem_block = format_memories(memories)
    return (
        "Recent observations:\n"
        f"{obs_block}\n\n"
        "Relevant memories:\n"
        f"{mem_block}\n\n"
        "Decide what to do in the next ten seconds.\n\n"
        f"{RESPONSE_SCHEMA_HINT}"
    )


__all__ = [
    "RESPONSE_SCHEMA_HINT",
    "build_system_prompt",
    "build_user_prompt",
    "format_memories",
]

 succeeded in 0ms:
            "Zone where the trigger occurred. None for non-spatial kinds "
            "(temporal / biorhythm / internal / speech / perception / "
            "erre_mode_shift). The Godot ``BoundaryLayer`` only pulses "
            "when zone is set AND kind is in the spatial set "
            "{zone_transition, affordance, proximity}."
        ),
    )
    ref_id: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Structured reference id of the trigger. Mapping by kind: "
            "zone_transition→``to_zone`` (string-equal to ``zone``), "
            "affordance→``prop_id``, proximity→``other_agent_id``. "
            "None for kinds without a stable reference."
        ),
    )
    secondary_kinds: list[
        Literal[
            "zone_transition",
            "affordance",
            "proximity",
            "temporal",
            "biorhythm",
            "erre_mode_shift",
            "internal",
            "speech",
            "perception",
        ]
    ] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "Same-tick strong losers (kinds that were observed but did not "
            "win the priority vote). UI may render as '+N more'. Order "
            "follows priority descending; bounded to 8 to cap envelope size."
        ),
    )


class ReasoningTrace(BaseModel):
    """One tick of structured reasoning rationale (M6-A-3).

    Produced alongside an :class:`LLMPlan` by the cognition cycle's Step 5
    when the LLM fills the optional ``salient`` / ``decision`` /
    ``next_intent`` fields. Unlike :class:`ReflectionEvent` (which distils
    many ticks into one stored memory), this trace captures per-tick
    self-explanation — primarily for xAI observability in the Godot UI.

    All three narrative fields are optional because stable Ollama output is
    never 100%; downstream consumers must tolerate ``None``. The trace is
    safe to discard if missing — :class:`LLMPlan` parsing is independent,
    so a persona can produce a valid plan without producing a trace.
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    tick: int = Field(..., ge=0)
    persona_id: str | None = Field(
        default=None,
        description=(
            "Persona this trace belongs to (matches ``PersonaSpec.persona_id``). "
            "M7ζ-added so the Godot ``ReasoningPanel`` can render the persona "
            "identity alongside the trace without joining ``AgentState``. Older "
            "M7ε producers (pre-0.9.0-m7z) deserialise as ``None``; consumers "
            "must tolerate the missing case and fall back to ``agent_id``."
        ),
    )
    mode: ERREModeName
    salient: str | None = Field(
        default=None,
        description="What the agent noticed as most salient this tick.",
    )
    decision: str | None = Field(
        default=None,
        description="The one-sentence rationale behind the chosen action.",
    )
    next_intent: str | None = Field(
        default=None,
        description="Forward-looking intent surfaced for upcoming ticks.",
    )
    observed_objects: list[str] = Field(
        default_factory=list,
        description=(
            "Top-3 ``AffordanceEvent.prop_id`` values by salience that informed "
            "this tick's decision (M7γ). Empty list means the tick had no "
            "affordance signal worth surfacing — not a missing field."
        ),
    )
    nearby_agents: list[str] = Field(
        default_factory=list,
        description=(
            "Up to two ``ProximityEvent.other_agent_id`` values with "
            'crossing="enter" that informed this tick (M7γ). Order is '
            "insertion order from the observation stream."
        ),
    )
    retrieved_memories: list[str] = Field(
        default_factory=list,
        description=(
            "Top-3 ``MemoryEntry.id`` values surfaced by recall calls during "
            "this tick (M7γ). Lets the xAI panel link the decision back to the "
            "specific memory rows it leaned on."
        ),
    )
    trigger_event: TriggerEventTag | None = Field(
        default=None,
        description=(
            "M9-A: the event-boundary tag picked from this tick's "
            "observations by priority. Lets the Godot ``ReasoningPanel`` "
            "show the trigger 1-liner and the ``BoundaryLayer`` pulse the "
            "originating zone for the focused agent. Older M7ζ producers "
            "(pre-0.10.0-m7h) deserialise as ``None``; consumers must "
            "tolerate the missing case."
        ),
    )
    created_at: datetime = Field(default_factory=_utc_now)


class SemanticMemoryRecord(BaseModel):
    """Long-term semantic memory row distilled from reflection (M4 foundation).

    Minimal shape: the sqlite-vec schema (index configuration, embedding
    dimensionality, composite keys) is deferred to
    ``m4-memory-semantic-layer``. ``embedding`` is permitted to be empty so
    fixture files and unit tests can roundtrip without shipping a real vector.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    agent_id: str
    embedding: list[float] = Field(
        default_factory=list,
        description=(
            "Row-level vector. Expected non-empty at runtime; empty allowed for "
            "fixture payloads so contract tests do not pin a particular dim."
        ),
    )
    # TODO(m4-memory-semantic-layer): pin embedding dimensionality once the
    # sqlite-vec index schema chooses between multilingual-e5-small (384) and
    # ruri-v3-30m (256); add field_validator to reject wrong-length vectors.
    summary: str
    origin_reflection_id: str | None = Field(
        default=None,
        description="``ReflectionEvent`` this row was distilled from, if any.",
    )
    belief_kind: (
        Literal[
            "trust",
            "clash",
            "wary",
            "curious",
            "ambivalent",
        ]
        | None
    ) = Field(
        default=None,
        description=(
            "Typed classification of the belief this record represents (M7δ). "

exec
/bin/zsh -lc "sed -n '1,220p' src/erre_sandbox/contracts/eval_paths.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,220p' src/erre_sandbox/evidence/tier_a/burrows.py" in /Users/johnd/ERRE-Sand Box
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



 succeeded in 0ms:
"""Burrows Delta — z-scored function-word L1 (Manhattan) distance.

Codex ``gpt-5.5 xhigh`` review (HIGH-5) corrected an early sketch that
called the metric "function-word vector cosine"; cosine distance is
not the Burrows Delta family. The canonical R-stylo formulation
(Eder/Rybicki/Kestemont, R Journal 2016) is:

1. Pick a closed list of function words for the language under test.
2. From a *background corpus* compute, per function word, the mean and
   standard deviation of relative frequency.
3. For each text under comparison, compute its relative frequency
   vector and z-score against the background statistics.
4. Delta between two texts = sum of absolute differences of their
   z-vectors (Manhattan / L1 distance).

In this codebase we hold the persona's z-vector in a
:class:`BurrowsReference` and compare an incoming test text against it.
The reference is per-language; cross-language comparison raises
:class:`BurrowsLanguageMismatchError` (per ``blockers.md`` "Burrows
multi-lang reference 暫定方針").

P1a delivers the pure math against synthetic references. P1b populates
real corpora (Akademie-Ausgabe Kant, KGW Nietzsche, 利休百首, plus a
synthetic 4th persona) under :mod:`erre_sandbox.evidence.reference_corpus`
once licensing has been confirmed (ME-6).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable

DEFAULT_WHITESPACE_LANGUAGES: frozenset[str] = frozenset({"en", "de"})
"""Languages for which whitespace tokenisation gives a usable
function-word count.

Japanese (``"ja"``) requires a morphological analyser
(MeCab/SudachiPy) — left to P1b. Calling
:func:`compute_burrows_delta` with ``language="ja"`` and the default
tokeniser raises explicitly so we don't silently fold a stylometric
signal that is meaningless for the unsegmented script.
"""


class BurrowsLanguageMismatchError(ValueError):
    """Raised when reference language does not match the test text language.

    Function-word distributions are language-specific; comparing a German
    profile against an English text would produce a meaningless number.
    The contract defers explicit support of the third language (``"ja"``)
    to a per-language tokenizer landing in P1b.
    """


class BurrowsTokenizationUnsupportedError(NotImplementedError):
    """Raised when the requested language has no built-in tokeniser yet.

    Lets P1b add a Japanese-specific entry without changing the public
    contract: callers can detect "tokenizer missing" separately from
    "language mismatch" and wire in their own splitter via
    ``preprocessed_tokens`` once P1b ships the SudachiPy adapter.
    """


@dataclass(frozen=True)
class BurrowsReference:
    """Per-language Burrows reference profile.

    Attributes:
        language: ISO-ish language tag (``"en"`` / ``"de"`` / ``"ja"``).
            Compared verbatim against the ``language`` argument of
            :func:`compute_burrows_delta`.
        function_words: Closed list of lower-case function words. Order
            is positional; ``background_mean`` /
            ``background_std`` / ``profile_freq`` align by index.
        background_mean: Mean relative frequency of each function word
            across a generic background corpus (per-token rate, in
            ``[0, 1]``).
        background_std: Standard deviation of relative frequency in the
            same background corpus. Words with ``std <= 0`` are dropped
            from the Delta sum (would z-divide by zero).
        profile_freq: This persona's relative frequency vector for the
            same function words, computed from the persona's reference
            corpus.

    Construction is left to ``reference_corpus`` ingestion (P1b). For
    P1a tests, callers build a small synthetic ``BurrowsReference``
    directly.
    """

    language: str
    function_words: tuple[str, ...]
    background_mean: tuple[float, ...]
    background_std: tuple[float, ...]
    profile_freq: tuple[float, ...]

    def __post_init__(self) -> None:
        n = len(self.function_words)
        if not (
            len(self.background_mean) == n
            and len(self.background_std) == n
            and len(self.profile_freq) == n
        ):
            raise ValueError(
                "BurrowsReference vectors must have equal length;"
                f" function_words={n} mean={len(self.background_mean)}"
                f" std={len(self.background_std)} profile={len(self.profile_freq)}",
            )
        if any(s < 0 for s in self.background_std):
            raise ValueError("background_std entries must be non-negative")
        if any(not isfinite(v) for v in self.background_mean):
            raise ValueError("background_mean entries must be finite")
        if any(not isfinite(v) for v in self.background_std):
            raise ValueError("background_std entries must be finite")
        if any(not isfinite(v) for v in self.profile_freq):
            raise ValueError("profile_freq entries must be finite")


def _tokenize(text: str, language: str) -> list[str]:
    """Lower-case whitespace tokeniser for ``en`` and ``de``.

    Japanese routes through :class:`BurrowsTokenizationUnsupportedError`
    until P1b lands a SudachiPy-backed splitter (or callers preprocess
    the text into tokens themselves and use ``preprocessed_tokens=``).
    """
    if language not in DEFAULT_WHITESPACE_LANGUAGES:
        raise BurrowsTokenizationUnsupportedError(
            f"Burrows Delta default tokenizer does not support language"
            f" {language!r}; pass preprocessed_tokens= or wait for P1b"
            f" to ship a {language}-specific tokenizer",
        )
    # ``str.split`` (no args) collapses arbitrary whitespace, which is
    # adequate for the function-word counting use-case where exact
    # boundary handling at punctuation is tolerated noise.
    return [tok.lower() for tok in text.split() if tok]


def compute_burrows_delta(
    text: str,
    reference: BurrowsReference,
    *,
    language: str,
    preprocessed_tokens: Iterable[str] | None = None,
) -> float:
    """Burrows Delta = sum of absolute z-score differences (L1 distance).

    Args:
        text: Test utterance / document. Ignored if ``preprocessed_tokens``
            is provided — useful when the caller already ran a per-language
            tokenizer (e.g. SudachiPy for Japanese).
        reference: Per-language profile. ``reference.language`` must equal
            ``language`` or :class:`BurrowsLanguageMismatchError` is raised.
        language: Language of the test text. Must match
            ``reference.language``.
        preprocessed_tokens: Optional pre-tokenised lower-case stream that
            bypasses the built-in whitespace tokeniser. Lets Japanese (and
            future languages with non-trivial segmentation) participate
            ahead of full P1b tokeniser plumbing.

    Returns:
        ``sum_i |z_test_i - z_profile_i|`` over function words with
        ``std > 0``. Returns ``float('nan')`` when the test text is empty
        or no function word survived the ``std > 0`` filter — a NaN here
        is the explicit "metric unmeasurable" signal the bootstrap-CI
        code path knows how to drop (per the M8 ``compute_*`` contract:
        ``None``/``NaN`` means "no measurement", not "zero").

    Raises:
        BurrowsLanguageMismatchError: When ``language != reference.language``.
        BurrowsTokenizationUnsupportedError: When ``language`` has no
            default tokenizer and ``preprocessed_tokens`` is ``None``.
    """
    if language != reference.language:
        raise BurrowsLanguageMismatchError(
            f"Burrows reference language {reference.language!r} does not"
            f" match test text language {language!r}; per-language"
            f" reference contract requires identical tag",
        )

    tokens: list[str]
    if preprocessed_tokens is not None:
        tokens = [t.lower() for t in preprocessed_tokens if t]
    else:
        tokens = _tokenize(text, language)

    total = len(tokens)
    if total == 0:
        return float("nan")

    counts = Counter(tokens)

    delta_sum = 0.0
    counted = 0
    for fw, mean, std, profile in zip(
        reference.function_words,
        reference.background_mean,
        reference.background_std,
        reference.profile_freq,
        strict=True,
    ):
        if std <= 0.0:
            continue
        test_freq = counts.get(fw, 0) / total
        z_test = (test_freq - mean) / std
        z_profile = (profile - mean) / std
        delta_sum += abs(z_test - z_profile)
        counted += 1

    if counted == 0:
        return float("nan")
    return delta_sum

codex
## Verdict (1 行)
ADOPT-WITH-CHANGES

## HIGH (must-fix before phasing 確定 — 最低 3 件、できれば 5 件)
- HIGH-1: 「完全な人間」が ERRE thesis を希釈する
  - Risk: Option A のままでは「Kant の認知習慣を再実装した agent」ではなく「Kant 風 seed から生まれた別人格」の研究になる。これは thesis 前半の Extract/Reverify/Reimplement を弱め、M9-eval/LoRA が守っている persona identity 測定とも衝突する。
  - Mitigation: thesis を「歴史的認知習慣を immutable substrate とする、観測可能に発達する人工個体」と再定義する。`cognitive_habits` / LoRA style / `persona_id` は drift 禁止、Individual は world model・belief・narrative のみで発達する。

- HIGH-2: LLM 自己宣言で内部状態が動く ME-9 同型リスク
  - Risk: `world_model_update`、NarrativeSelf、DevelopmentState、personality drift を LLM 出力で直接更新すると、「私は成長した」「私は信じた」という宣言が state truth になる。ME-9 incident の rate basis 不明確問題と同じく、観測根拠なしの内部遷移が正規 trigger に見える。
  - Mitigation: LLM は `WorldModelUpdateHint` を提案するだけにする。Python 側が `cited_memory_ids`、直近観測、反復回数、信頼度、反証記憶を検証し、stage / personality / belief 更新は indirect signal で決める。

- HIGH-3: M9-B LoRA training contamination
  - Risk: Individual layer を M9-B 前または並行で cognition に混ぜると、LoRA が philosopher_base ではなく「個体 overlay 済み Kant」を学習する。PR #127 の固定 Kant style 前提を破り、後続の base/individual 分解が測定不能になる。
  - Mitigation: M9-B dataset は `individual_layer_enabled=false` の base-only run に限定する。M10-A scaffold は feature flag で並行可だが、prompt・raw_dialog・training export へ流すのは M9-B adoption baseline 後に限定する。

- HIGH-4: Burrows ratio は individualization metric にならない
  - Risk: Burrows Delta は主に高頻度語・機能語の文体差を見るため、world model や narrative の意味的個体差をほぼ拾わない可能性が高い。逆に Individual prompt が機能語分布を動かすなら、それは base style 保持の confound になる。
  - Mitigation: Burrows は base style retention 専用に固定する。個体化は `world_model` 分散、belief variance、NarrativeArc coherence/drift、semantic centroid distance、Agent Identity Evals 型の perturbation recovery で別測定する。

- HIGH-5: S1-S5 stage count が未検証の操作子になっている
  - Risk: 5 段は Erikson 8 / Piaget 4 / 守破離 3 の中間という説明しかなく、研究仮説ではなく任意 knob になる。任意 stage は、実験後に都合よく解釈できるため falsifiability を落とす。
  - Mitigation: M11 では `S1_seed / S2_exploring / S3_consolidated` までに縮めるか、5 label は hidden maturity score の view として扱う。各 stage は sampling、memory window、reflection frequency、drift bound の数値差と negative-control 条件を preregister する。

- HIGH-6: RadixAttention / prompt cache 劣化
  - Risk: `philosopher_base + Individual` を system prompt に素直に展開すると、個体ごと・tick ごとに prefix が変わり、SGLang RadixAttention の共有 prefix 効果が落ちる。SGLang docs は共通 token prefix 再利用が前提なので、mutable block の位置は性能要件そのもの。
  - Mitigation: prompt ordering は `_COMMON_PREFIX` → immutable `philosopher_base` → current state tail、Individual summary は user prompt 側の bounded top-K に置く。M10-A で cache hit rate / TTFT / prompt token 増分を acceptance に入れる。

- HIGH-7: solo project scope と hidden dependency
  - Risk: 5 stages × multi-individual × narrative × subjective world model × LoRA 分解は、M10/M11 の単一 milestone に載せるには広すぎる。M11-A transition を観測するには M10-B で十分な memory growth と個体化 metric が必要で、metric 未整備のまま進むと「動いたが評価不能」になる。
  - Mitigation: M10/M11 MVP は base/individual contract、SWM bounded update、cache-safe prompt、個体化 metric だけに絞る。NarrativeSelf prose、S4/S5、retirement、rebirth、individual LoRA は M12+ gate に送る。

## MEDIUM (should consider, 採否は明示)
- MEDIUM-1: `personas/*.yaml` の rename は採用保留。3 persona しかないが M9 trunk 中の schema churn は不要なので、まず loader wrapper で `PersonaSpec` を `PhilosopherBase` として読む。
- MEDIUM-2: `cited_memory_ids` は必須採用。ただし現行 `format_memories()` は memory id を prompt に出していないため、先に memory prompt 表示契約を変える必要がある。
- MEDIUM-3: `decay_half_life` は修正採用。world_model confidence と stance edges には必要だが、base identity と LoRA style には適用しない。
- MEDIUM-4: `coherence_score` は修正採用。初期は diagnostic のみにし、stage transition hard gate へ使うのは false-positive rate 測定後。
- MEDIUM-5: Japanese utterance と Burrows reference language の分離を採用。現行 Burrows 実装は `ja` tokenizer 未対応なので、M9-eval の対象 channel を明示しないと metric が空転する。

## LOW (nit / optional)
- `完全な人間` は外向けには避け、「persistent artificial individual」程度に落とす方が論文・README の過剰 claim を防げる。
- `S5_late` の老化 analog は研究的には面白いが、M11 では premature。rigidity は stage ではなく confidence saturation として表す方が実装が軽い。
- `Individual` は `agent_id` と混同しやすいので、schema 名は `IndividualProfile` または `RuntimeIndividualState` がよい。

## ユーザー choice (Option A) の妥当性 stress-test
1. Q1 vision-thesis 整合: 条件付きで整合する。答えは「歴史的人物そのものを作る」ではなく「歴史的認知習慣を継承した人工個体の発達を観察する」への thesis rewrite。base fidelity と individual divergence を別 metric に分けないと、ERRE は偉人再実装から一般 agent life-sim に流れる。

2. Q2 operational definition: S1-S5 は現時点では placeholder。段間 trigger の `memory volume + narrative coherence + belief stability` AND は方向性として妥当だが、最低 tick 数、反証記憶、cooldown、stage regression 禁止、rate basis を足さないと ME-9 型の擬陽性が残る。default completion path は A: 不完成停滞。B retirement / C rebirth は M12+。

3. Q3 M9-B LoRA 互換: 「LoRA は base 専用」は自然には成立しない。training data に Individual overlay が混じった瞬間に崩れる。M10-A scaffold は M9-B と並行可だが、cognition wiring と export は M9-B baseline 後。PR #127 design-final には base-only dataset manifest と exclusion rule の追記が必要。

4. Q4 M9-eval Burrows 互換: Burrows は base 保持を見るには有効だが、個体化観測には弱い。multi-individual 同 base では Burrows が同じ値になるのがむしろ成功条件になり得る。個体化は semantic/narrative/belief metrics を M9-eval sidecar に追加して測るべき。

5. Q5 reimagine 8 missing items: 必須採用は `cited_memory_ids`、dyadic/class-wise 直交、RadixAttention 保護、定量 acceptance、M9 trunk 隔離。修正採用は `coherence_score`、`decay_half_life`、`growth_axes`。棄却できるものはないが、`growth_axes` は Option A では `divergence_bounds` に改名する方がよい。

6. Q6 hidden dependency: M11-A は M10-B の memory 成熟待ちなので、calendar milestone ではなく data readiness gate にする。M11-B の比較 metric は M10-A 前に確定が必要。M9-B は M10 cognition wiring 前に終えるべきだが、schema-only scaffold は feature flag なら可。

7. Q7 LLM 自己宣言予防: 境界線は明確に、LLM は「候補提示」、Python は「状態遷移」。Narrative prose は LLM 生成可だが、coherence score、stage advance、personality drift、belief promotion は観測ログ・memory ids・反復回数・統計安定性でのみ駆動する。

8. Q8 scope: MVP は two-layer contract、SubjectiveWorldModel の bounded primitive、cache-safe prompt、Python merge、個体化 metric。defer は NarrativeSelf prose、S4/S5、retirement/rebirth、multi-base society、individual LoRA。落としてよいのは Erikson/Piaget 風の本格発達理論模倣と free-form self-model。

## 7 提案 final 判定 (User-chosen vision 下での)
| # | 提案 | 判定 | 主要根拠 |
|---|---|---|---|
| 1 | SubjectiveWorldModel schema | ADOPT-WITH-CHANGES | AgentState 第一級でよいが、axis/key/value/confidence/evidence の bounded 形に限定 |
| 2 | prompt に subjective beliefs 注入 | ADOPT-WITH-CHANGES | user prompt 側 top-K のみ。system prefix と base block は固定 |
| 3 | LLMPlan に world_model_update | ADOPT-WITH-CHANGES | free-form 禁止。`WorldModelUpdateHint` + `cited_memory_ids` 必須 |
| 4 | Python 側で安全に merge | ADOPT | `belief.py` の pure function / threshold / interaction count pattern を踏襲 |
| 5 | NarrativeSelf 周期生成 | DEFER / MODIFY | prose ではなく NarrativeArc + coherence diagnostic から開始 |
| 6 | DevelopmentState 導入 | REVISE | 5 stage 確定は早い。M11 は S1-S3 または maturity score から |
| 7 | philosopher_seed refactor | ADOPT-WITH-CHANGES | conceptual two-layer は採用。ただし M9 trunk 完了まで rename / export 混入禁止 |

## 改訂 phasing (User vision 反映 + Codex 修正)
- M9-freeze: M9-eval Phase 2 と M9-B LoRA は base-only dataset で完了。Option A の cognition wiring は入れない。
- M10-0: 個体化 metric、dataset manifest、cache benchmark、prompt ordering contract を先に確定。
- M10-A: `PhilosopherBase` / `IndividualProfile` / `SubjectiveWorldModel` schema scaffold。feature flag default off、既存 loader 互換維持。
- M10-B: read-only SWM synthesis と prompt 注入。LLMPlan はまだ触らず、cache hit と base fidelity を測る。
- M10-C: bounded `WorldModelUpdateHint` 追加。`cited_memory_ids` 検証、adoption rate、false-positive rejection test を追加。
- M11-A: NarrativeArc + coherence_score。stage transition にはまだ使わない。
- M11-B: S1-S3 の DevelopmentState transition。Python indirect signal のみで遷移。
- M11-C: kant-base × 3 individuals validation。Burrows は base retention、semantic/belief/narrative metrics は individual divergence。
- M12+: S4/S5、retirement、rebirth、multi-base society、individual LoRA を empirical gate 後に再評価。

## 関連 prior art (web_search 必須)
- Generative Agents (Park et al. 2023): memory stream、reflection、planning は Option A の NarrativeSelf/SWM に近いが、論文の貢献は believable behavior であって「人間性」の証明ではない。https://arxiv.org/abs/2304.03442
- CoALA (Sumers et al. 2023): language agent を modular memory、structured action space、decision process として扱うので、ERRE でも LLM 直書きではなく Python action/update 境界を置く根拠になる。https://arxiv.org/abs/2309.02427
- Voyager (Wang et al. 2023): skill library は environment feedback と self-verification で更新される。ERRE の world_model_update も「自己宣言」ではなく環境 evidence で閉じるべき。https://arxiv.org/abs/2305.16291
- Identity drift 研究: 2024 の identity drift 論文は persona assignment が identity 維持に十分でないことを示す。Option A は drift を許す設計なので、drift の上限と測定が必須。https://arxiv.org/abs/2412.00804
- Persistent Personas? (EACL 2026): extended dialogue で persona fidelity が劣化し、instruction following と trade-off が出る。M11 multi-individual は長期対話評価を前提化すべき。https://aclanthology.org/2026.eacl-long.246/
- Agent Identity Evals (2025): statelessness、stochasticity、prompt sensitivity が agent identity を壊すと整理している。ERRE では identity eval を M9-eval sidecar に追加する価値が高い。https://arxiv.org/abs/2507.17257
- Memoria / Memori (2025-2026): persistent memory は raw history 注入ではなく structured representation が有効という方向。SWM は compact structured state として設計すべき。https://arxiv.org/abs/2512.12686 / https://arxiv.org/abs/2603.19935
- 開発段階モデル批判: Piaget stage は理論 stage と empirical stage の不連続性・曖昧さが批判される。S1-S5 は心理学 stage claim ではなく engineering phase として扱うべき。https://link.springer.com/article/10.1007/s12124-022-09702-7
- SGLang RadixAttention / LoRA: RadixAttention は共通 token prefix 再利用が前提。LoRA 動的 load も adapter batching/TTFT の制約があるため、Option A は cache/adapter metric を acceptance に入れる必要がある。https://sgl-project-sglang-93.mintlify.app/concepts/radix-attention / https://sgl-project.github.io/advanced_features/lora.html

## Final notes (個人プロジェクト scope への警告含む)
Option A は採用可能だが、そのまま実装すると「評価不能な豊かな agent」になりやすい。ERRE の価値は bloat ではなく、local/zero-budget で観察可能な cognitive loop を作ることにある。M10/M11 は「人間らしさ」を増やす milestone ではなく、「base fidelity を保ったまま individual divergence を測定可能にする」milestone として固定するべき。
hook: Stop
hook: Stop Completed
2026-05-08T06:58:38.454316Z ERROR codex_core::session: failed to record rollout items: thread 019e065d-399b-7941-8f9c-7ca6b8c0ebc1 not found
tokens used
197,247
## Verdict (1 行)
ADOPT-WITH-CHANGES

## HIGH (must-fix before phasing 確定 — 最低 3 件、できれば 5 件)
- HIGH-1: 「完全な人間」が ERRE thesis を希釈する
  - Risk: Option A のままでは「Kant の認知習慣を再実装した agent」ではなく「Kant 風 seed から生まれた別人格」の研究になる。これは thesis 前半の Extract/Reverify/Reimplement を弱め、M9-eval/LoRA が守っている persona identity 測定とも衝突する。
  - Mitigation: thesis を「歴史的認知習慣を immutable substrate とする、観測可能に発達する人工個体」と再定義する。`cognitive_habits` / LoRA style / `persona_id` は drift 禁止、Individual は world model・belief・narrative のみで発達する。

- HIGH-2: LLM 自己宣言で内部状態が動く ME-9 同型リスク
  - Risk: `world_model_update`、NarrativeSelf、DevelopmentState、personality drift を LLM 出力で直接更新すると、「私は成長した」「私は信じた」という宣言が state truth になる。ME-9 incident の rate basis 不明確問題と同じく、観測根拠なしの内部遷移が正規 trigger に見える。
  - Mitigation: LLM は `WorldModelUpdateHint` を提案するだけにする。Python 側が `cited_memory_ids`、直近観測、反復回数、信頼度、反証記憶を検証し、stage / personality / belief 更新は indirect signal で決める。

- HIGH-3: M9-B LoRA training contamination
  - Risk: Individual layer を M9-B 前または並行で cognition に混ぜると、LoRA が philosopher_base ではなく「個体 overlay 済み Kant」を学習する。PR #127 の固定 Kant style 前提を破り、後続の base/individual 分解が測定不能になる。
  - Mitigation: M9-B dataset は `individual_layer_enabled=false` の base-only run に限定する。M10-A scaffold は feature flag で並行可だが、prompt・raw_dialog・training export へ流すのは M9-B adoption baseline 後に限定する。

- HIGH-4: Burrows ratio は individualization metric にならない
  - Risk: Burrows Delta は主に高頻度語・機能語の文体差を見るため、world model や narrative の意味的個体差をほぼ拾わない可能性が高い。逆に Individual prompt が機能語分布を動かすなら、それは base style 保持の confound になる。
  - Mitigation: Burrows は base style retention 専用に固定する。個体化は `world_model` 分散、belief variance、NarrativeArc coherence/drift、semantic centroid distance、Agent Identity Evals 型の perturbation recovery で別測定する。

- HIGH-5: S1-S5 stage count が未検証の操作子になっている
  - Risk: 5 段は Erikson 8 / Piaget 4 / 守破離 3 の中間という説明しかなく、研究仮説ではなく任意 knob になる。任意 stage は、実験後に都合よく解釈できるため falsifiability を落とす。
  - Mitigation: M11 では `S1_seed / S2_exploring / S3_consolidated` までに縮めるか、5 label は hidden maturity score の view として扱う。各 stage は sampling、memory window、reflection frequency、drift bound の数値差と negative-control 条件を preregister する。

- HIGH-6: RadixAttention / prompt cache 劣化
  - Risk: `philosopher_base + Individual` を system prompt に素直に展開すると、個体ごと・tick ごとに prefix が変わり、SGLang RadixAttention の共有 prefix 効果が落ちる。SGLang docs は共通 token prefix 再利用が前提なので、mutable block の位置は性能要件そのもの。
  - Mitigation: prompt ordering は `_COMMON_PREFIX` → immutable `philosopher_base` → current state tail、Individual summary は user prompt 側の bounded top-K に置く。M10-A で cache hit rate / TTFT / prompt token 増分を acceptance に入れる。

- HIGH-7: solo project scope と hidden dependency
  - Risk: 5 stages × multi-individual × narrative × subjective world model × LoRA 分解は、M10/M11 の単一 milestone に載せるには広すぎる。M11-A transition を観測するには M10-B で十分な memory growth と個体化 metric が必要で、metric 未整備のまま進むと「動いたが評価不能」になる。
  - Mitigation: M10/M11 MVP は base/individual contract、SWM bounded update、cache-safe prompt、個体化 metric だけに絞る。NarrativeSelf prose、S4/S5、retirement、rebirth、individual LoRA は M12+ gate に送る。

## MEDIUM (should consider, 採否は明示)
- MEDIUM-1: `personas/*.yaml` の rename は採用保留。3 persona しかないが M9 trunk 中の schema churn は不要なので、まず loader wrapper で `PersonaSpec` を `PhilosopherBase` として読む。
- MEDIUM-2: `cited_memory_ids` は必須採用。ただし現行 `format_memories()` は memory id を prompt に出していないため、先に memory prompt 表示契約を変える必要がある。
- MEDIUM-3: `decay_half_life` は修正採用。world_model confidence と stance edges には必要だが、base identity と LoRA style には適用しない。
- MEDIUM-4: `coherence_score` は修正採用。初期は diagnostic のみにし、stage transition hard gate へ使うのは false-positive rate 測定後。
- MEDIUM-5: Japanese utterance と Burrows reference language の分離を採用。現行 Burrows 実装は `ja` tokenizer 未対応なので、M9-eval の対象 channel を明示しないと metric が空転する。

## LOW (nit / optional)
- `完全な人間` は外向けには避け、「persistent artificial individual」程度に落とす方が論文・README の過剰 claim を防げる。
- `S5_late` の老化 analog は研究的には面白いが、M11 では premature。rigidity は stage ではなく confidence saturation として表す方が実装が軽い。
- `Individual` は `agent_id` と混同しやすいので、schema 名は `IndividualProfile` または `RuntimeIndividualState` がよい。

## ユーザー choice (Option A) の妥当性 stress-test
1. Q1 vision-thesis 整合: 条件付きで整合する。答えは「歴史的人物そのものを作る」ではなく「歴史的認知習慣を継承した人工個体の発達を観察する」への thesis rewrite。base fidelity と individual divergence を別 metric に分けないと、ERRE は偉人再実装から一般 agent life-sim に流れる。

2. Q2 operational definition: S1-S5 は現時点では placeholder。段間 trigger の `memory volume + narrative coherence + belief stability` AND は方向性として妥当だが、最低 tick 数、反証記憶、cooldown、stage regression 禁止、rate basis を足さないと ME-9 型の擬陽性が残る。default completion path は A: 不完成停滞。B retirement / C rebirth は M12+。

3. Q3 M9-B LoRA 互換: 「LoRA は base 専用」は自然には成立しない。training data に Individual overlay が混じった瞬間に崩れる。M10-A scaffold は M9-B と並行可だが、cognition wiring と export は M9-B baseline 後。PR #127 design-final には base-only dataset manifest と exclusion rule の追記が必要。

4. Q4 M9-eval Burrows 互換: Burrows は base 保持を見るには有効だが、個体化観測には弱い。multi-individual 同 base では Burrows が同じ値になるのがむしろ成功条件になり得る。個体化は semantic/narrative/belief metrics を M9-eval sidecar に追加して測るべき。

5. Q5 reimagine 8 missing items: 必須採用は `cited_memory_ids`、dyadic/class-wise 直交、RadixAttention 保護、定量 acceptance、M9 trunk 隔離。修正採用は `coherence_score`、`decay_half_life`、`growth_axes`。棄却できるものはないが、`growth_axes` は Option A では `divergence_bounds` に改名する方がよい。

6. Q6 hidden dependency: M11-A は M10-B の memory 成熟待ちなので、calendar milestone ではなく data readiness gate にする。M11-B の比較 metric は M10-A 前に確定が必要。M9-B は M10 cognition wiring 前に終えるべきだが、schema-only scaffold は feature flag なら可。

7. Q7 LLM 自己宣言予防: 境界線は明確に、LLM は「候補提示」、Python は「状態遷移」。Narrative prose は LLM 生成可だが、coherence score、stage advance、personality drift、belief promotion は観測ログ・memory ids・反復回数・統計安定性でのみ駆動する。

8. Q8 scope: MVP は two-layer contract、SubjectiveWorldModel の bounded primitive、cache-safe prompt、Python merge、個体化 metric。defer は NarrativeSelf prose、S4/S5、retirement/rebirth、multi-base society、individual LoRA。落としてよいのは Erikson/Piaget 風の本格発達理論模倣と free-form self-model。

## 7 提案 final 判定 (User-chosen vision 下での)
| # | 提案 | 判定 | 主要根拠 |
|---|---|---|---|
| 1 | SubjectiveWorldModel schema | ADOPT-WITH-CHANGES | AgentState 第一級でよいが、axis/key/value/confidence/evidence の bounded 形に限定 |
| 2 | prompt に subjective beliefs 注入 | ADOPT-WITH-CHANGES | user prompt 側 top-K のみ。system prefix と base block は固定 |
| 3 | LLMPlan に world_model_update | ADOPT-WITH-CHANGES | free-form 禁止。`WorldModelUpdateHint` + `cited_memory_ids` 必須 |
| 4 | Python 側で安全に merge | ADOPT | `belief.py` の pure function / threshold / interaction count pattern を踏襲 |
| 5 | NarrativeSelf 周期生成 | DEFER / MODIFY | prose ではなく NarrativeArc + coherence diagnostic から開始 |
| 6 | DevelopmentState 導入 | REVISE | 5 stage 確定は早い。M11 は S1-S3 または maturity score から |
| 7 | philosopher_seed refactor | ADOPT-WITH-CHANGES | conceptual two-layer は採用。ただし M9 trunk 完了まで rename / export 混入禁止 |

## 改訂 phasing (User vision 反映 + Codex 修正)
- M9-freeze: M9-eval Phase 2 と M9-B LoRA は base-only dataset で完了。Option A の cognition wiring は入れない。
- M10-0: 個体化 metric、dataset manifest、cache benchmark、prompt ordering contract を先に確定。
- M10-A: `PhilosopherBase` / `IndividualProfile` / `SubjectiveWorldModel` schema scaffold。feature flag default off、既存 loader 互換維持。
- M10-B: read-only SWM synthesis と prompt 注入。LLMPlan はまだ触らず、cache hit と base fidelity を測る。
- M10-C: bounded `WorldModelUpdateHint` 追加。`cited_memory_ids` 検証、adoption rate、false-positive rejection test を追加。
- M11-A: NarrativeArc + coherence_score。stage transition にはまだ使わない。
- M11-B: S1-S3 の DevelopmentState transition。Python indirect signal のみで遷移。
- M11-C: kant-base × 3 individuals validation。Burrows は base retention、semantic/belief/narrative metrics は individual divergence。
- M12+: S4/S5、retirement、rebirth、multi-base society、individual LoRA を empirical gate 後に再評価。

## 関連 prior art (web_search 必須)
- Generative Agents (Park et al. 2023): memory stream、reflection、planning は Option A の NarrativeSelf/SWM に近いが、論文の貢献は believable behavior であって「人間性」の証明ではない。https://arxiv.org/abs/2304.03442
- CoALA (Sumers et al. 2023): language agent を modular memory、structured action space、decision process として扱うので、ERRE でも LLM 直書きではなく Python action/update 境界を置く根拠になる。https://arxiv.org/abs/2309.02427
- Voyager (Wang et al. 2023): skill library は environment feedback と self-verification で更新される。ERRE の world_model_update も「自己宣言」ではなく環境 evidence で閉じるべき。https://arxiv.org/abs/2305.16291
- Identity drift 研究: 2024 の identity drift 論文は persona assignment が identity 維持に十分でないことを示す。Option A は drift を許す設計なので、drift の上限と測定が必須。https://arxiv.org/abs/2412.00804
- Persistent Personas? (EACL 2026): extended dialogue で persona fidelity が劣化し、instruction following と trade-off が出る。M11 multi-individual は長期対話評価を前提化すべき。https://aclanthology.org/2026.eacl-long.246/
- Agent Identity Evals (2025): statelessness、stochasticity、prompt sensitivity が agent identity を壊すと整理している。ERRE では identity eval を M9-eval sidecar に追加する価値が高い。https://arxiv.org/abs/2507.17257
- Memoria / Memori (2025-2026): persistent memory は raw history 注入ではなく structured representation が有効という方向。SWM は compact structured state として設計すべき。https://arxiv.org/abs/2512.12686 / https://arxiv.org/abs/2603.19935
- 開発段階モデル批判: Piaget stage は理論 stage と empirical stage の不連続性・曖昧さが批判される。S1-S5 は心理学 stage claim ではなく engineering phase として扱うべき。https://link.springer.com/article/10.1007/s12124-022-09702-7
- SGLang RadixAttention / LoRA: RadixAttention は共通 token prefix 再利用が前提。LoRA 動的 load も adapter batching/TTFT の制約があるため、Option A は cache/adapter metric を acceptance に入れる必要がある。https://sgl-project-sglang-93.mintlify.app/concepts/radix-attention / https://sgl-project.github.io/advanced_features/lora.html

## Final notes (個人プロジェクト scope への警告含む)
Option A は採用可能だが、そのまま実装すると「評価不能な豊かな agent」になりやすい。ERRE の価値は bloat ではなく、local/zero-budget で観察可能な cognitive loop を作ることにある。M10/M11 は「人間らしさ」を増やす milestone ではなく、「base fidelity を保ったまま individual divergence を測定可能にする」milestone として固定するべき。

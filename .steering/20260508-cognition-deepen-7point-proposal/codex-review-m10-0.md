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
session id: 019e1602-2ce7-7f32-aa63-8d1869a5aeed
--------
user
# Codex Independent Review — M10-0 concrete design (Reasoning model judgment 含む)

## あなた (Codex) の役割

私 (Claude) はユーザーの「Reasoning model」アイディア (post-training / RL / activation 分析 /
weight steering / 社会心理学的 trait 抽出を組み合わせた思考ドメイン model 開発) を ERRE M10+
phasing に射影した判定メモ (`reasoning-model-judgment.md`) を、PR #144 (merged design-final.md +
decisions.md DA-1〜DA-13) と PR #145 (DB11 contamination prevention) に対して validate し、
**M10-0 (Pre-flight: individuation metrics + dataset manifest + cache benchmark + prompt
ordering contract) の concrete design** を `m10-0-concrete-design-draft.md` として起こした。

あなたの仕事は arbitrate ではなく、**この 2 文書を独立 stress-test** すること:

1. `reasoning-model-judgment.md` の判定 (DEFER/ADOPT-WITH-CHANGES 配置) が既存 ADR 整合の
   うえでさらに structurally robust か
2. `m10-0-concrete-design-draft.md` の concrete design (channel × metric matrix、permanent
   layer、acceptance、threshold preregister、recovery protocol、WP 分割) が実装可能水準で
   miss / blind spot を含んでいないか

HIGH を必ず最低 3 件、できれば 5 件出すこと。「問題ない」と書くだけの review は失敗とみなす。

期待する独立性: Claude solo の判定と reimagine 未適用の concrete design に対し、
- M9-B LoRA contamination (DB11) との結合 risk
- LLM 自己宣言 pattern (DA-4 Q7) の再混入 risk
- empirical falsifiability の欠落
- mecab / Vendi kernel / Big5 ICC の operational definition 不足
- recovery protocol の ME-9 同型 false-positive risk
- M9-eval Phase 2 capture format との互換性

を厳しく見ること。Web search は **必須**: activation steering / representation engineering /
Identity Drift 系の 2024-2026 prior art を引用し、本提案が "weight-level intervention M12+ defer"
を正当化できるか確認すること。

## 出力フォーマット (必須)

```
## Verdict (1 行)
ADOPT-AS-IS / ADOPT-WITH-CHANGES / REVISE / RECONSIDER / REJECT

## HIGH (must-fix before M10-0 task scaffold 起票 — 最低 3 件、できれば 5 件)
- HIGH-1: ...
  - Risk: ...
  - Mitigation: ...

## MEDIUM (should consider, 採否は明示)

## LOW (nit / optional)

## reasoning-model-judgment.md 判定の妥当性 stress-test
1. Q1: "weight-level intervention M12+ defer" の妥当性 (2024-2026 activation steering / representation engineering の進展で M10/M11 active spike を許す根拠はあるか)
2. Q2: "trait 抽出 = sidecar metric" 化で User の Reasoning model 構想本来の表現力が失われていないか (失われていれば何を補うべきか)
3. Q3: §3.1 5 metrics (semantic_centroid_distance / belief_variance / world_model_overlap_jaccard / base_retention_burrows / intervention_recovery_rate) は概念的に直交か、重複測定はないか
4. Q4: §4 M11-C 再判定 gate の 4 条件は十分か (Burrows base retention + 3 divergence metrics + adoption rate + negative control)
5. Q5: §5 不採用 5 項目 (思考ドメイン model 開発 / base+individual 同一 LoRA / SWM+Dev+Arc 即 post-training / cognitive_habits runtime 上書き / 人間らしさ RL) の defer は永久 defer か empirical gate ありか

## m10-0-concrete-design-draft.md の stress-test
6. Q6: channel × metric matrix (§2.2) で見落としている channel / metric は (reasoning_trace 利用、cognitive habit recall rate 等)
7. Q7: 永続化 layer (§2.3、DuckDB `individuation_metrics` table) が training-view loader filter (DB11) を bypass しない設計担保は十分か
8. Q8: acceptance A2 (mecab ja-tokenizer Burrows ±0.05 以内) は妥当か、A3 (semantic_centroid_distance N=1 degenerate) の handling は適切か
9. Q9: threshold preregister 表 (§2.5) で TBD のまま M10-0 を close する acceptance 構造 (TBD を M11-C 直前に固定) は empirical preregister 原則に違反しないか
10. Q10: recovery protocol (§2.6) の opposite-stance memory 強制注入は LLM 自己宣言 pattern (DA-4 Q7) を再導入しないか、Python が evidence-driven に発火させる代替設計はあるか
11. Q11: WP 分割 (§3) の WP4 (mecab 移行) を M10-0 timing で行うか、M10-B/C 後の別 task にすべきか (依存最小化観点)
12. Q12: §4 リスク表 (mecab Burrows 変動 / embedding reproducibility / Big5 ICC N=1 degenerate / recovery protocol T_* 数値 / Vendi MPNet 日本語性能) で見落としているものは

## 関連 prior art (web_search 必須)
- Anthropic Constitutional AI / Representation Engineering (2024-2026)
- Activation Steering / RepE (Zou et al. 2023-2026 最新動向)
- Identity Drift in LLM agents (2025-2026 EACL / NeurIPS)
- Generative Agents persistent identity follow-up
- Agent Identity Evals 2025 + 後続
- Anthropic Persona Vectors / character steering 系
- Vendi score multilingual kernel 動向
- IPIP-NEO short form Japanese validation

## Final notes (個人プロジェクト scope + 予算ゼロ制約への警告含む)
```

## 入力ファイル (verbatim 引用、要約しないこと)

### 1. `reasoning-model-judgment.md` (全文)

```
# Reasoning model アイディア設計判断メモ

- **作成日**: 2026-05-11
- **位置づけ**: M10+ cognition-deepening の外付け記憶
- **入力**: ユーザーと対話内の問い
- **結論**: **M10 本線で model weight / activation intervention として取り込むのは却下。M10-0〜M10-C の評価・抽出・bounded steering 設計として取り込むのは採用。**

## 0. 要旨

ユーザーの中心アイディアは「思考ドメインを持つ Reasoning model」を作るために、事後学習・強化学習・ステアリング・社会心理学・活性化/重み分析を組み合わせ、特性を抽出・交差・介入する研究開発である。

ERRE-Sandbox に対しては、この発想は **個体化を観測・制御する研究プログラム** として有効。ただし M10 ではモデル重みそのものを開発対象にしない。M10 の責務は、`PhilosopherBase` の base fidelity と `IndividualProfile` の divergence を分離して測れる状態を作ることであり、weight-level intervention は M11-C empirical validation 後の M12+ research gate に置く。

## 1. 判定

| アイディアの要素 | ERRE 判定 | 配置 |
|---|---|---|
| LLM の事後学習 / SFT / RL | **DEFER** | M12+。M10 では取り込まない |
| 活性化・重み分析 | **RESEARCH SPIKE ONLY** | M12+。M10 本線の acceptance にしない |
| 特性ドメイン抽出 | **ADOPT-WITH-CHANGES** | M10-0 sidecar metrics として実装候補 |
| 特性の交差・合成 | **DEFER/MODIFY** | M11-C 後。同一 base multi-individual の結果を見て判断 |
| ステアリング / 介入 | **ADOPT-WITH-CHANGES** | M10-C `WorldModelUpdateHint` の bounded primitive に限定 |
| 実証実験設計 | **ADOPT** | M10-0 の中心タスクに組み込む |

## 2. 理由

M10+ の operational thesis は「歴史的認知習慣を immutable substrate とする、観測可能に発達する人工個体」を作り、base の保存性と individual の発達を同時に測ることである。

そのため、M10 で weight-level の reasoning model 開発に入ると、次の 3 つが崩れる。

1. **Base / Individual 分離が崩れる**
   `PhilosopherBase` の LoRA-trained style と `IndividualProfile` の world model divergence が同じ重み空間に混ざり、何が base retention で何が個体化か測れなくなる。

2. **M9-B LoRA contamination 防止と衝突する**
   M9-B training は `individual_layer_enabled=false` の base-only data だけを使う制約を持つ。M10 で個体 layer の出力を training / post-training に混ぜると、この設計判断を破る。

3. **LLM 自己宣言による内部状態更新リスクが再発する**
   Reasoning model型の "介入" を free-form steering として入れると、ME-9 incident と同型の false-positive 構造になる。ERRE では LLM は候補提示のみ、Python が observable evidence に基づいて state transition する。

## 3. M10 で採用する形

### 3.1 M10-0: Reasoning trait sidecar metrics

Reasoning modelの「抽出」を model-internal analysis ではなく、まず ERRE の観測ログからの sidecar metric として定義する。

候補:

- `semantic_centroid_distance`: 同一 `PhilosopherBase` 由来 individuals の発話 embedding 距離
- `belief_variance`: `SubjectiveWorldModel` / promoted belief のばらつき
- `world_model_overlap_jaccard`: SWM entry key の重なりと分岐
- `base_retention_burrows`: Burrows ratio は base style retention 専用
- `intervention_recovery_rate`: perturbation 後に base habit へ戻るか、individual belief が残るか

Acceptance:

- 既存 M9 baseline data に対して metric が valid 値を返す
- Burrows と individualization metrics が同じ概念を二重測定していない
- M10-A schema scaffold 前に、metric 名・入力 channel・出力 sidecar schema を固定する

### 3.2 M10-B: Read-only subjective trait injection

Reasoning modelの「特性ドメイン」は、`SubjectiveWorldModel` の top-K entry として USER prompt 側に bounded injection する。

制約:

- SYSTEM prompt には入れない
- `_COMMON_PREFIX` + immutable `PhilosopherBase` block の cache 共有を壊さない
- prompt token 増分は +200 以内
- LLMPlan はまだ変更しない

### 3.3 M10-C: Bounded steering only

Reasoning modelの「介入」は、free-form steering ではなく `WorldModelUpdateHint` に限定する。

許可:

\`\`\`python
WorldModelUpdateHint(
    axis="env" | "concept" | "self" | "norm" | "temporal",
    key="...",
    direction="strengthen" | "weaken" | "no_change",
    cited_memory_ids=[...],
)
\`\`\`

禁止:

- arbitrary hidden-state patching
- free-form "personality update"
- LLM の自己申告による stage advance
- weight update / LoRA update
- `cited_memory_ids` を伴わない belief injection

Python 側が `cited_memory_ids ⊆ retrieved_memories` を検証し、threshold を満たす場合だけ merge する。

## 4. M11-C 後に再判定する形

M11-C で `kant` base から 3 individuals を走らせ、次が同時成立した場合だけ Reasoning model型の deeper intervention を再評価する。

- Burrows ratio が base retention を示す
- semantic centroid / belief variance / SWM overlap が individual divergence を示す
- `WorldModelUpdateHint` の adoption rate が `[0.05, 0.40]` 内に収まる
- free-form belief が採用されない negative control が通る

その後の M12+ research gate 候補:

- activation analysis spike
- representation steering spike
- individual LoRA spike
- same-base multi-individual RL / preference tuning
- reasoning-domain transfer test

## 5. 採用しない形

以下は少なくとも M10/M11 では採用しない。

- 「思考ドメインを持った Reasoning model」を ERRE の新しい中核 model として作る
- Kant / Nietzsche / Rikyū の base persona と individual divergence を同一 LoRA に混ぜる
- SWM / DevelopmentState / NarrativeArc を学習データとして即座に post-training へ流す
- `PhilosopherBase` の `cognitive_habits` を runtime 成長で上書きする
- 人間らしさを直接 objective にした RL

## 6. 実装メモ

M10-0 task を起票する時、このメモは次の requirement に変換する。

1. Reasoning model 型 trait extraction を **sidecar metrics** として preregister する
2. metric 入力 channel を `raw_dialog`, `reasoning_trace`, `semantic_memory`, `SubjectiveWorldModel` に分ける
3. Burrows = base retention、semantic/belief/SWM metrics = individual divergence と明記する
4. M10-B/C の steering は `WorldModelUpdateHint` に閉じる
5. weight-level intervention は M12+ research gate に明示 defer する
```

### 2. `m10-0-concrete-design-draft.md` (本 prompt と同一 directory に配置済、Read で参照)

Path: `.steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md`

主要セクション:
- §1 memo 判定 (Claude solo)
- §2.2 Channel × Metric matrix (9 metrics × 4 channels)
- §2.3 永続化 layer (DuckDB additive table + JSON sidecar key)
- §2.4 Acceptance A1-A8
- §2.5 Threshold preregister 表 (8 thresholds、一部 TBD)
- §2.6 Intervention recovery protocol (T_base=200 / T_perturb=50 / T_recover=200 tick)
- §2.7 out-of-scope (M10-A/B/C / M11-A/B/C / M12+ への送り先)
- §2.8 PR #127 (M9-B LoRA) 追記事項
- §2.9 PR #148 P4a Tier B 接続 (Vendi / Big5 ICC)
- §3 WP 分割 (8 WP、production ~1400 LOC + test ~400)
- §4 リスク (HIGH 1 / MEDIUM 3 / LOW 1)

## 既存 ADR / merge 済 PR 引用 (Codex は file Read 可)

- `.steering/20260508-cognition-deepen-7point-proposal/design-final.md` (PR #144 merged) — §0 thesis re-articulation、§1 二層 architecture、§2 M9 trunk 接続、§3 phasing、§5 acceptance
- `.steering/20260508-cognition-deepen-7point-proposal/decisions.md` (PR #144 merged) — DA-1 〜 DA-13
- `.steering/20260430-m9-b-lora-execution-plan/design-final.md` (PR #145 で DB11 ADR Addendum 2026-05-08 追記) — base-only training data 制約
- `src/erre_sandbox/eval/tier_b/` (PR #148 merged) — Vendi / IPIP-NEO / Big5 ICC 実装
- `data/eval/golden/` (M9-eval Phase 2 capture format) — `_audit_stimulus.json` + per-cell `*.duckdb.capture.json`

## 個人プロジェクト scope への警告

- 予算ゼロ制約 (クラウド LLM API 非依存、ローカル SGLang+Ollama)
- 個人開発、現実的に M10-0 〜 M12 まで empirical 走行に 数ヶ月単位
- M9-eval Phase 2 run1 calibration は G-GEAR で overnight×2 (30h × 5 cells) かかる種類
- Codex review は HIGH 切出で実装前に compress するための tool であり、scope 拡大には使わない

## Verdict 解釈基準

- ADOPT-AS-IS: 何の修正もなく M10-0 task scaffold 起票可
- ADOPT-WITH-CHANGES: HIGH 反映で起票可 (推奨着地点)
- REVISE: HIGH 数件が structural、design を draft 段階に戻す
- RECONSIDER: 既存 ADR (PR #144/#145) との整合性を再検討する必要
- REJECT: 本提案を破棄し別アプローチ (例: M10-0 を skip して M10-A scaffold 直行)

以上。Web search を必ず使い、HIGH 最低 3 件 (理想 5 件) を出すこと。要約せず HIGH/MEDIUM/LOW
ごとに Risk + Mitigation を verbatim 提示すること。

hook: SessionStart
hook: SessionStart Completed
hook: UserPromptSubmit
hook: UserPromptSubmit Completed
codex
Using `$erre-workflow` for the review entry point, then I’ll read the concrete draft and the relevant merged design/ADR context before checking current prior art on the web.
exec
/bin/zsh -lc "sed -n '1,240p' .agents/skills/erre-workflow/SKILL.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,260p' .steering/20260508-cognition-deepen-7point-proposal/decisions.md" in /Users/johnd/ERRE-Sand Box
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
# Decisions — 認知深化 7-point 提案 ADR (3-source synthesis 後 final)

> 各 decision は (1) Claude initial / (2) User clarification / (3) reimagine / (4) Codex
> review の 4 入力を統合した最終判断。`Final` 列が単一の決定。

## DA-1: ERRE thesis の operational re-articulation

| 入力 | 案 |
|---|---|
| Claude initial | thesis は手付かず、提案 7 を DEFER で対応 |
| User clarification | "完全な人間として構築" (極端、scope 無限化リスク) |
| reimagine | persona identity 維持、growth_axes で深まる方向のみ (極端、新個体性を否定) |
| Codex HIGH-1 | 中道: "歴史的認知習慣を immutable substrate とする、観測可能に発達する人工個体" |

**Final**: Codex 案を採用。functional-design.md §1 の thesis 文言は変更せず、
**operational re-articulation** を design-final.md §0 に明記し、後続 milestone の
acceptance に "base fidelity" と "individual divergence" を **別 metric** として
preregister する (Codex HIGH-1 + HIGH-4)。

**根拠**: User vision の "新個体" は維持しつつ、reimagine の "identity 希釈危険" を
防ぐには、 drift 許容領域を **明示的に分割** する必要がある。`cognitive_habits` /
LoRA / `persona_id` を drift 禁止に置き、Individual layer は world model / belief /
narrative のみで発達する境界条件を強制する。

## DA-2: 提案 1 SubjectiveWorldModel — ADOPT-WITH-CHANGES

| 入力 | 案 |
|---|---|
| Claude initial | ADOPT in memory layer |
| User clarification | ADOPT as AgentState 第一級 property |
| reimagine | StanceVector 5-axis として独立再発見 |
| Codex | ADOPT-WITH-CHANGES、bounded 形に限定 |

**Final**: `IndividualProfile.world_model: SubjectiveWorldModel` として 第一級 property、
5-axis (env / concept / self / norm / temporal) × bounded entries 50/individual 上限、
`WorldModelEntry` ごとに `cited_memory_ids ≥ 1` 必須。

**Defer**: axis 集合の最終決定は M10-A scaffold 時に再評価可能 (現行は best-guess、
empirical 観測後に rebalance)。

## DA-3: 提案 2 prompt 注入 — ADOPT-WITH-CHANGES

| 入力 | 案 |
|---|---|
| Claude initial | ADOPT、user prompt 側、token bound 200 |
| reimagine | user prompt 側の memories 直後 section、80 tokens |
| Codex HIGH-6 | system prompt = `_COMMON_PREFIX` + immutable PhilosopherBase + state tail、
                  Individual は user prompt 側 bounded top-K |

**Final**: Codex 案を採用。prompt ordering contract を M10-0 で確定。SGLang RadixAttention
共有 prefix を **PhilosopherBase block まで拡大** (cache 効果向上)。M10-A acceptance に
`cache hit rate / TTFT / prompt token 増分` を含める。

## DA-4: 提案 3 LLMPlan world_model_update — ADOPT-WITH-CHANGES (free-form 禁止)

| 入力 | 案 |
|---|---|
| Claude initial | MODIFY、bounded primitive (topic_focus_shift 等) |
| User clarification | Individual 側で bounded 維持 |
| reimagine | StanceShiftHint + `cited_memory_ids` 必須 |
| Codex HIGH-2 | `WorldModelUpdateHint` + cited_memory_ids 必須、Python が verify |

**Final**: `WorldModelUpdateHint(axis, key, direction, cited_memory_ids)` として LLMPlan に
additive 追加。`direction: Literal["strengthen", "weaken", "no_change"]` の 3 値で free-form
禁止。Python が `cited_memory_ids ⊆ retrieved_memories` を検証してから merge。

**Reject path**: free-form `world_model_update: dict` 案は ME-9 incident 同型 (LLM 自己宣言
で内部状態が動く) のため不採用。

## DA-5: 提案 4 Python 側で安全に merge — ADOPT (pattern 流用)

| 入力 | 案 |
|---|---|
| Claude initial | ADOPT、belief.py pattern 流用 |
| reimagine | apply_stance_shift_hint() pure function |
| Codex | ADOPT |

**Final**: `cognition/belief.py:maybe_promote_belief` の pure-function + threshold-based +
layer-boundary-preserving pattern を以下 3 関数に踏襲:
- `apply_world_model_update_hint(swm, hint, retrieved_memories) -> SubjectiveWorldModel | None`
- `synthesize_narrative_arc(semantic_memory, swm) -> NarrativeArc | None`
- `maybe_advance_development(profile, evidence) -> DevelopmentState | None`

すべて pure、caller (bootstrap or cognition cycle) が persistence の owner。

## DA-6: 提案 5 NarrativeSelf 周期生成 — DEFER/MODIFY

| 入力 | 案 |
|---|---|
| Claude initial | ADOPT、M11-A defer |
| User clarification | M10-B 同期 (個体連続性に必須) |
| reimagine | NarrativeArc (structured trajectory、prose 否) + coherence_score |
| Codex | DEFER/MODIFY、prose ではなく Arc + coherence diagnostic |

**Final**: M11-A で `NarrativeArc` (structured) + `coherence_score` (diagnostic only) を
投入。**Free-form prose 化は M12+ defer** (token cost、role-play 増幅 risk、stage
transition 駆動には false-positive rate 計測後)。

**User clarification "M10-B 同期" は撤回**: Codex は cache 戦略 + scope 集中の観点から
M11-A defer を強く推奨。Individual 連続性は SWM だけで M10-B 段階は十分 (NarrativeArc は
"豊かさ" 追加であって連続性の必須ではない)。

## DA-7: 提案 6 DevelopmentState — REVISE (S1-S3 + hidden maturity score)

| 入力 | 案 |
|---|---|
| Claude initial | REJECT standalone、shuhari_stage 拡張 |
| User clarification | ADOPT、S1-S5 lifecycle で完全な人間化 |
| reimagine | REJECT、ShuhariStage 拡張で代替 |
| Codex HIGH-5 | REVISE、S1-S3 に縮小 or hidden maturity score の view |

**Final**: `DevelopmentState(stage: S1_seed/S2_exploring/S3_consolidated, maturity_score:
[0,1])` として ADOPT、ただし **S4/S5 は M12+ research gate**。

`shuhari_stage` (base 側技能習得) と DevelopmentState (Individual 側 lifecycle) は **意味
を分けて両立**:
- shuhari_stage: 「Kant の歩行を どこまで内化したか」(技能習得)
- development_state: 「個体が どこまで個別化したか」(lifecycle)

axis 直交を docstring に明記、両者の混同を防止。

**S5_late (老化 analog) は撤回**: Codex LOW-2 より `confidence saturation` で代替。

**User vision との差分**: "完全な人間として" 5 stages → 3 stages + hidden score。
M11-B 経験で S4 が必要と empirically 判明したら M12+ で追加検討。

## DA-8: 提案 7 philosopher_seed refactor — ADOPT-WITH-CHANGES (rename しない)

| 入力 | 案 |
|---|---|
| Claude initial | DEFER M11+ (M9 trunk 破壊リスク) |
| User clarification | ADOPT、二層分離 |
| reimagine | REJECT、persona 維持 + growth_axes |
| Codex | ADOPT-WITH-CHANGES、conceptual two-layer は採用、M9 trunk 完了まで rename / export 混入禁止 |

**Final**: 二層 conceptual refactor を採用 (User vision)、ただし以下の制約 (Codex HIGH-3):

1. `personas/*.yaml` の rename **しない** (schema_version 0.10.0-m7h 維持、3 persona しか
   ないが M9 trunk 中の churn を避ける)
2. `PersonaSpec` (schemas.py) に loader wrapper を追加 → `PhilosopherBase` として読める
3. M9-B LoRA training には Individual layer enabled run **混入禁止** (PR #127 design-final.md
   に base-only manifest と exclusion rule を追記)
4. M10-A scaffold は feature flag default off で並行可、ただし training/raw_dialog export
   への流入は M9-B baseline 後のみ

**Naming**: `philosopher_seed` という新名は使わず、**immutable PhilosopherBase + mutable
IndividualProfile** で機能を表現。User の "philosopher_seed" は意図 (= seed としての
位置づけ) を反映するが、命名としては reimagine の指摘通り Extract pipeline の意味を
弱める。Codex LOW-1 も "完全な人間" を外向け表現から外すよう推奨。

## DA-9: reimagine 8 missing items の選別 (Codex Q5 反映)

| Item | 採否 | 配置 |
|---|---|---|
| `cited_memory_ids` 必須 | **ADOPT 必須** | DA-2 / DA-4 / DA-5 / DA-7 全体 |
| dyadic vs class-wise axis 直交 | **ADOPT 必須** | belief_kind (dyadic) と SWM `axis` (class) を docstring + golden test で強制 |
| `coherence_score` metric | ADOPT-WITH-CHANGES | M11-A diagnostic only、hard gate は M11-B で false-positive 後 |
| RadixAttention KV cache 保護 | **ADOPT 必須** | DA-3、M10-0 contract |
| `decay_half_life` | ADOPT-WITH-CHANGES (Codex MEDIUM-3) | world_model のみ、base / LoRA に適用しない |
| `growth_axes.permitted/forbidden` | REJECT | User vision (Option A) と矛盾。Individual layer の divergence は別 schema (`personality_drift_offset` 等) で表現 |
| 定量 acceptance per milestone | **ADOPT 必須** | design-final.md §5 |
| M9 trunk 隔離 gate | **ADOPT 必須** | DA-8 + design-final.md §3 M9-freeze |

## DA-10: Burrows ratio の役割再定義 (Codex HIGH-4)

**Final**: Burrows = **base style retention 専用**。multi-individual 同 base で同じ値が
出るのが成功条件。個体化測定は別 sidecar metrics (semantic centroid distance / belief
variance / NarrativeArc drift / Agent Identity Evals 型 perturbation recovery)。

M10-0 で sidecar metrics を実装してから M10-A scaffold に着手。

## DA-11: schema_version bump 戦略

**Final**: `0.10.0-m7h → 0.11.0-m10c` の minor bump を M10-C (LLMPlan に
WorldModelUpdateHint 追加) で実施。additive のみ、後方互換維持。`personas/*.yaml`
schema_version は M10 中変更しない (Codex MEDIUM-1)。

## DA-12: Open questions deferred (M10/M11 実装時に決着)

- `decay_half_life_ticks` の calibration (initial = 1000、M10-B simulation で tune)
- `WorldModelUpdateHint.adoption rate` 目標 band `[0.05, 0.40]` の根拠 (M10-C 後 empirical)
- `personality_drift_offset` の bounded 範囲 ±0.1 per axis (M11-C で multi-individual
  divergence 観測後)
- `coherence_score` の hard threshold (M11-B で false-positive rate 測定後)
- S4_articulation 必要性 (M11-B 経験後 M12+ で再評価)
- Burrows tokenizer 戦略 (mecab / char n-gram、M10-0 sidecar 実装時)

## DA-13: 採用しなかった代替案の記録

- **`philosopher_seed` 命名**: User clarification の意図は反映するが命名は不採用 (reimagine
  + Codex LOW-1 の指摘で Extract pipeline 意味を弱める懸念)
- **S1-S5 5 stages**: Codex HIGH-5 で falsifiability 不足、S1-S3 + hidden maturity score に
  縮小
- **NarrativeSelf を free-form prose で M10-B 同期**: User clarification の意図だが Codex
  scope 集中観点で M11-A diagnostic only に defer
- **growth_axes.permitted/forbidden** (reimagine): User vision (Option A、新個体) と矛盾、
  Individual layer の divergence は別 mechanism で表現
- **path B retirement / path C rebirth**: M12+ research gate (Codex Q2)、default は path A 不完成停滞
- **完全な人間として構築 (User 文言)**: 外向け表現として "persistent artificial individual"
  に置換 (Codex LOW-1)、内部 thesis re-articulation で operational に表現 (DA-1)

exec
/bin/zsh -lc "sed -n '1,260p' .steering/20260508-cognition-deepen-7point-proposal/design-final.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# Design Final — 認知深化 7-point 提案 (3-source synthesis)

> Plan→Clear→Execute ハンドオフ規則に従い、`/clear` 後でも独立に Read 可能な体裁で書く。
>
> 3 source 由来:
> - `design.md` (Claude initial Plan-mode 判定)
> - `design-clarified.md` (User clarification 反映の二層解釈)
> - `design-reimagine.md` (independent reimagine、Compression-Loop counter-proposal)
> - `codex-review.md` (Codex `gpt-5.5 xhigh` independent review、Verdict ADOPT-WITH-CHANGES、
>   HIGH 7 / MEDIUM 5 / LOW 3、197K tokens、prior art 9 件 web search 引用)
>
> User decision (2026-05-08): **Option A** (新個体 + 二層 + 完全な人間化方向)
> Codex stress-test 結果を反映して **ユーザー vision を維持しつつ HIGH 7 件すべて吸収**

## 0. Thesis re-articulation (Codex HIGH-1 反映、必須)

ERRE thesis (functional-design.md §1) を **operational に再表現**:

> 旧: 「歴史的偉人の認知習慣をローカル LLM エージェントとして再実装し、知的創発を観察」
>
> 新: 「**歴史的認知習慣を immutable substrate とする、観測可能に発達する人工個体**
>      を作り、その発達と original substrate の保存性を同時に測定する」

これにより:
- "歴史的偉人を作る" 過剰 claim を回避 (Codex LOW-1)
- "完全な人間として" の scope 無限化を回避 (Codex HIGH-7)
- "認知習慣の再実装" と "知的創発の観察" の thesis 内部緊張を **drift-禁止 + 発達-許可
  axis 直交** で解消

reimagine が指摘した「persona identity 希釈は thesis を破壊する」と user vision の
「新個体」を統合する解: **identity は base layer に閉じ込め、Individual layer は別 axis
で divergence する**。

### immutable / mutable boundary (Codex HIGH-1 mitigation)

| 層 | 対象 | drift 許容 | 由来 |
|---|---|---|---|
| **PhilosopherBase** | `persona_id` | NO | 一次史料 |
| | `cognitive_habits` (Kant の歩行/朝執筆等) | NO | Extract pipeline |
| | `default_sampling` (T/top_p/repeat_penalty) | NO | Reverify pipeline |
| | LoRA-trained style | NO | M9-B target、固定 |
| | `preferred_zones` | NO | persona-zone 関係 |
| **Individual** | `world_model` (5-axis subjective) | YES (decay & evidence-driven) | 個体の interaction |
| | `subjective_beliefs` | YES (cited_memory_ids 必須) | 観察 |
| | `narrative_arc` (≠ free-form prose) | YES (周期蒸留) | semantic memory |
| | `development_state` (S1-S3) | YES (indirect signal) | observable evidence |
| | `personality_drift_offset` (Big5 の bounded ±0.1 等) | YES (限定) | 蓄積 |

「**identity は drift しない、divergence は別 axis で起きる**」 — これが Option A の正統解釈。

## 1. 二層 architecture (final, Codex HIGH-1/HIGH-6 反映)

### 1.1 Schema

```python
# contracts/cognition_v0_11_0.py (新)

class PhilosopherBase(BaseModel):
    """Immutable inheritance from Extract/Reverify pipeline.
    M9-B LoRA は本層を学習する。Individual layer の影響を一切受けない。"""
    model_config = ConfigDict(extra="forbid", frozen=True)
    persona_id: str                            # kant / rikyu / nietzsche
    display_name: str
    era: str
    cognitive_habits: list[CognitiveHabit]     # 既存 personas/*.yaml 流用
    default_sampling: SamplingParam
    preferred_zones: list[Zone]
    primary_corpus_refs: list[str]
    lora_adapter_id: str | None = None         # M9-B 後に注入

class IndividualProfile(BaseModel):            # Codex LOW-3: Individual → IndividualProfile
    """Mutable runtime individual built on top of an immutable PhilosopherBase."""
    model_config = ConfigDict(extra="forbid")
    individual_id: str                         # uuid (= agent_id と直結しない、Codex LOW-3)
    base_persona_id: str                       # PhilosopherBase reference
    world_model: SubjectiveWorldModel          # 提案 1
    development_state: DevelopmentState        # 提案 6 (REVISE: S1-S3)
    narrative_arc: NarrativeArc | None = None  # 提案 5 (DEFER/MODIFY: prose ではなく Arc)
    personality_drift_offset: PersonalityDrift # bounded ±0.1 per axis、cited evidence 駆動

class SubjectiveWorldModel(BaseModel):
    """5-axis bounded world view. AgentState 第一級 property (User clarification)。
    各 entry は cited_memory_ids 必須 (Codex HIGH-2)。"""
    model_config = ConfigDict(extra="forbid")
    entries: list[WorldModelEntry]             # bounded、上限 50/individual

class WorldModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    axis: Literal["env", "concept", "self", "norm", "temporal"]
    key: str                                   # axis 内の固有 key (e.g. "peripatos", "categorical_imperative")
    value: float = Field(ge=-1.0, le=1.0)      # signed
    confidence: float = Field(ge=0.0, le=1.0)
    cited_memory_ids: list[str]                # ≥ 1 必須 (Codex HIGH-2)
    last_updated_tick: int
    decay_half_life_ticks: int = 1000          # Codex MEDIUM-3、world_model のみ適用

class DevelopmentState(BaseModel):
    """S1-S3 のみ (Codex HIGH-5)。S4/S5 は M12+ で empirical evidence 後再評価。"""
    model_config = ConfigDict(extra="forbid")
    stage: Literal["S1_seed", "S2_exploring", "S3_consolidated"]
    maturity_score: float = Field(ge=0.0, le=1.0)  # hidden continuous score、stage は view
    transition_evidence: dict[str, int]        # observable evidence count per stage
    # 段間遷移は Python indirect signal のみ (Codex HIGH-2、Q7)

class NarrativeArc(BaseModel):
    """Structured trajectory (prose ではない、Codex 提案 5 DEFER/MODIFY)。
    coherence_score は M11-A では diagnostic のみ (Codex MEDIUM-4)。"""
    model_config = ConfigDict(extra="forbid")
    synthesized_at_tick: int
    arc_segments: list[ArcSegment]             # ≤ 5 segments
    coherence_score: float                     # diagnostic only initially
    last_episodic_pointer: str

class WorldModelUpdateHint(BaseModel):         # Codex HIGH-2: free-form 禁止、bounded primitive
    """LLM が world model 更新を要望する bounded primitive。
    LLM = candidate、Python = state transition (Codex Q7)。"""
    model_config = ConfigDict(extra="forbid")
    axis: Literal["env", "concept", "self", "norm", "temporal"]
    key: str
    direction: Literal["strengthen", "weaken", "no_change"]
    cited_memory_ids: list[str]                # ≥ 1 必須、retrieved_memories 内に集合包含
```

### 1.2 LLMPlan 拡張 (additive、minor schema bump、Codex HIGH-2 反映)

```python
# cognition/parse.py の LLMPlan に追加 (M10-C で投入)
world_model_update_hint: WorldModelUpdateHint | None = Field(default=None, ...)
```

`extra="forbid", frozen=True` 維持、後方互換 (default None)。

### 1.3 prompt 構造 (Codex HIGH-6 反映、cache-safe)

```
SYSTEM PROMPT:
  _COMMON_PREFIX (既存、絶対不変、SGLang RadixAttention 共有)
    ↓
  PhilosopherBase block (immutable per persona_id、cache 共有可)
    ↓
  current state tail (tick / zone / erre_mode / physical / cognitive、既存)

USER PROMPT:
  Recent observations (既存)
    ↓
  Relevant memories (既存、ただし memory id を出力するよう Codex MEDIUM-2 反映)
    ↓
  Held world-model entries (新、bounded top-K、上限 80 tokens)  ← Individual side
    ↓
  RESPONSE_SCHEMA_HINT (既存 + WorldModelUpdateHint section 追加)
```

**Cache 戦略**: System prompt は base persona ごとに reusable。Individual 部分は user
prompt 側の bounded top-K に閉じる。M10-A acceptance に **cache hit rate / TTFT /
prompt token 増分** を入れる (Codex HIGH-6 mitigation)。

### 1.4 LLM 自己宣言 pattern 排除 (Codex HIGH-2 + Q7、不可侵原則)

| 内部状態変化 | 駆動 source |
|---|---|
| `WorldModelUpdateHint` 採用 | Python が `cited_memory_ids` を retrieved_memories と集合検証 + threshold |
| `subjective_belief` (`belief_kind`) 昇格 | 既存 M7δ pattern (affinity 飽和 indirect signal) |
| `personality_drift_offset` 更新 | 反復観察 N 回 + statistical stability、LLM 申告では発火しない |
| `narrative_arc` 蒸留 | chashitsu reflection trigger (既存) + memory volume threshold |
| `coherence_score` 計算 | 発話 embedding と SWM cosine sim (Python pure) |
| `development_state.stage` 遷移 | maturity_score (= memory volume + coherence + belief stability の AND) + 最低 tick + cooldown + regression 禁止 |

**境界線 (Codex Q7)**: LLM は **候補提示**、Python は **state transition**。narrative
prose は LLM 生成可、stage advance / personality drift / belief promotion は observable
evidence のみ。

## 2. M9 trunk との接続 (Codex HIGH-3 mitigation、最重要)

### 2.1 M9-B LoRA contamination 防止

PR #127 (`.steering/20260430-m9-b-lora-execution-plan/`) design-final.md に **追記必須**:

- **dataset manifest**: `individual_layer_enabled=false` の base-only run のみ training data
- **exclusion rule**: M10-A 以降 scaffold が enable された tick の dialog_turn は training
  export から自動除外
- **flag check**: training pipeline 入口で `dataset.metadata.individual_layer_enabled == false`
  を assert

### 2.2 M9-eval Burrows ratio の役割再定義 (Codex HIGH-4)

| 用途 | metric |
|---|---|
| **base style retention** | Burrows ratio (現行のまま) |
| **個体化 divergence** | semantic centroid distance (sentence embedding) |
| | belief variance across same-base individuals |
| | NarrativeArc coherence/drift |
| | world_model entry overlap (Jaccard) |
| | Agent Identity Evals 型 perturbation recovery (Codex prior art) |

multi-individual 同 base で **Burrows が同じ値** = base 保持成功 (失敗ではない)。
個体化は別 sidecar metrics で測る。

### 2.3 Codex MEDIUM-5: Japanese utterance + Burrows tokenizer

現行 Burrows 実装は `ja` tokenizer 未対応。M10-0 タスクで M9-eval sidecar に **対象 channel
明示** (utterance vs reasoning trace) と **tokenizer 戦略** (mecab? char n-gram?) を定義。

## 3. 改訂 phasing (Codex 7 HIGH 反映、final)

```
[M9-freeze] (UNTOUCHED 継続、in-flight)
  - run1 calibration (G-GEAR)
  - M9-eval Phase 2 完了
  - M9-B LoRA execution: base-only dataset で実行 (HIGH-3 反映、PR #127 追記)
  - M9-eval Phase 2 vs LoRA 比較 baseline 確立
  ↓ M9 完全終了 後に M10 cognition wiring 着手可

[M10-0] Pre-flight (Codex HIGH-7、HIGH-3、HIGH-4 mitigation)
  - 個体化 metric 定義 + sidecar 実装 (semantic distance / belief variance / narrative drift)
  - dataset manifest 仕様確定 (`individual_layer_enabled` flag)
  - cache benchmark 枠組み (cache hit rate / TTFT / token delta)
  - prompt ordering contract (COMMON → base → state → user-bounded-top-K)
  - acceptance: 既存 baseline で metric が動くこと、benchmark が走ること
  - 影響範囲: M9-eval sidecar 拡張、PR #127 design-final.md 追記
  - **schema 変更なし**

[M10-A] Two-layer schema scaffold (Codex Q3、feature flag default off)
  - PhilosopherBase / IndividualProfile / SubjectiveWorldModel / DevelopmentState
    Pydantic schema を contracts/cognition_v0_11_0.py に新設
  - personas/*.yaml の rename はせず loader wrapper で `PersonaSpec` を `PhilosopherBase`
    として読む (Codex MEDIUM-1)
  - feature flag `cognition.individual_layer.enabled = false` (default off)
  - acceptance: 既存 1318 tests PASS、新 schema golden test、wrapper 互換確認
  - **cognition wiring なし** (read-write path 未配線)

[M10-B] Read-only SWM synthesis + prompt 注入 (Codex HIGH-6 cache-safe)
  - SWM 周期蒸留 (semantic_memory + RelationshipBond → SWM bounded top-K)
  - user prompt に Held world-model entries section 追加
  - LLMPlan は **未変更** (cache hit と base fidelity を測る)
  - acceptance: cache hit rate ≥ 80% baseline、TTFT ≤ +5%、prompt token +200 以内
  - acceptance: persona 別 SWM が異なる軸で強くなる (個体化 metric で empirical)

[M10-C] Bounded WorldModelUpdateHint (Codex HIGH-2 反映)
  - LLMPlan に `world_model_update_hint: WorldModelUpdateHint | None = None` 追加
  - apply_world_model_update_hint() pure function (cited_memory_ids verify)
  - acceptance: golden test 「LLM が free-form belief 主張しても採用されない」
  - acceptance: adoption rate measure (高すぎ = pickup 緩い、低すぎ = LLM が cite 諦め)
  - schema_version 0.10.0-m7h → 0.11.0-m10c minor bump (additive)

[M11-A] NarrativeArc + coherence_score (diagnostic only、Codex MEDIUM-4)
  - chashitsu reflection 拡張で synthesize_narrative_arc()
  - coherence_score 計測 (発話 embedding と SWM cosine sim)
  - **stage transition には未使用** (false-positive rate 測定後 M11-B で評価)
  - acceptance: low coherence で深い reflection 発火、prose 化はまだ defer

[M11-B] DevelopmentState transition machinery (S1-S3 のみ、Codex HIGH-5)
  - maybe_advance_development() pure function (Python indirect signal)
  - 遷移 trigger: maturity_score ≥ 段ごと閾値 + 最低 tick + cooldown + regression 禁止
  - 各 stage の sampling / memory / reflection 数値差を **preregister**
  - negative-control 条件: stage 操作 stripped run vs full run の divergence 比較
  - acceptance: 1 individual を 1000-tick 走らせ S1→S2→S3 の遷移が observable evidence
    駆動で発火 (LLM 自己申告では発火しない)

[M11-C] Multi-individual 同 base validation (Codex HIGH-4 反映)
  - 3 IndividualProfile を同 PhilosopherBase (kant) から起動

exec
/bin/zsh -lc "sed -n '1,260p' .steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# M10-0 Concrete Design Draft (Claude solo, pre-Codex)

- **作成日**: 2026-05-11
- **位置づけ**: `reasoning-model-judgment.md` を validation した上で、M10-0 (Pre-flight: individuation metrics + dataset manifest + cache benchmark + prompt ordering contract) を実装可能水準まで詰めた草案
- **入力**:
  - `reasoning-model-judgment.md` (Claude メモ、2026-05-11)
  - `design-final.md` §3 M10-0 (PR #144 merged)
  - `decisions.md` DA-1 / DA-8 / DA-10 / DA-12 (PR #144 merged)
  - PR #145 DB11 ADR (training-view contamination prevention)
  - P4a Tier B merged (`tier_b/` vendi / ipip_neo / big5_icc、PR #148)
- **status**: Codex independent review (gpt-5.5 xhigh) 起動前の Claude solo 案。`/reimagine` 未適用。

---

## 1. memo 判定 (Claude solo)

`reasoning-model-judgment.md` の判定は既存 ADR (DA-1〜DA-13、DB11、ME-9 metaphor) に対して内部矛盾なし。
ただし 5 gap (G1 MEDIUM + G2-G5 MINOR) を識別:

| # | severity | 内容 |
|---|---|---|
| G1 | MEDIUM | channel × metric の対応行列が欠落 (memo §6.2 で channel 列挙のみ) |
| G2 | MINOR | P4a Tier B 資産 (Vendi / Big5 ICC) を未参照 |
| G3 | MINOR | sidecar 永続化 layer 未指定 (DuckDB table vs JSON sidecar) |
| G4 | MINOR | 閾値の preregister 場所が design-final.md §6 で defer のまま |
| G5 | MINOR | `intervention_recovery_rate` の operationalization (perturbation protocol) 欠落 |

---

## 2. Concrete design

### 2.1 タスク配置 (M9 完全終了後 scaffold)

```
.steering/[YYYYMMDD]-m10-0-individuation-metrics/
  requirement.md
  design.md
  design-reimagine.md     (mandatory per CLAUDE.md)
  codex-review-prompt.md
  codex-review.md         (verbatim)
  decisions.md            (ADR DA-IM-1〜)
  tasklist.md
```

### 2.2 Channel × Metric matrix (G1 修復)

| Metric | Input channel | What | Aggregation | Phase |
|---|---|---|---|---|
| `burrows_base_retention` | `raw_dialog.utterance` (mecab ja-tokenizer) | function-word freq vs base corpus | per-individual | M10-0 (既存拡張) |
| `semantic_centroid_distance` | utterance embedding (sentence-transformer) | inter-individual style/content distance | pairwise same-base | M10-0 新規 |
| `vendi_diversity` (P4a Tier B 流用) | utterance embedding kernel | within-base population diversity | population-level | M10-0 新規 |
| `belief_variance` | `SemanticMemoryRecord.belief_kind` (promoted のみ) | cognitive content divergence | pairwise + class-wise | M10-0 新規 |
| `world_model_overlap_jaccard` | `SubjectiveWorldModel.entries.key` per axis | SWM key overlap | pairwise × 5 axes | M10-0 (metric 関数のみ先行、active 計測は M10-A 以降) |
| `big5_icc` (P4a Tier B 流用) | IPIP-NEO 応答 | personality stability across pop | ICC[2,1] within base | M10-0 新規 |
| `intervention_recovery_rate` | post-perturbation utterance | base habit recovery / individual stickiness | dual (Burrows recovery + SWM persistence) | M10-0 protocol 定義のみ、実走 M11-C |
| `narrative_drift` | NarrativeArc segments | trajectory divergence | pairwise edit distance | **M11-A 移送** (M10-0 では preregister のみ) |
| `worldmodel_update_adoption_rate` | `LLMPlan.world_model_update_hint` | adoption / total | rate | **M10-C 移送** |

### 2.3 永続化 layer (G3 修復)

- **DuckDB additive 1 table**: `individuation_metrics(run_id, individual_id, base_persona_id, tick, metric_name, value, channel, computed_at)`
  - 既存 `_audit_stimulus.json` capture pipeline と並走、DuckDB 側に集約 (M9-eval Phase 2 で確立した DuckDB sidecar 型を踏襲)
- **`_audit_stimulus.json` additive key**: `individuation_metrics_summary` (per-run population-level の最終値のみ)
- M9-eval CLI `--compute-individuation` flag (default off、M9-eval 既存 contract 不変、後方互換)

### 2.4 Acceptance criteria (preregister)

| ID | criterion | rationale |
|---|---|---|
| A1 | M9-eval baseline 5 cells で全 metric が valid float 返す (NaN / inf なし) | smoke |
| A2 | mecab ja-tokenizer で kant Burrows が現行 char n-gram 値と ±0.05 以内で再現 | tokenizer 移行回帰防止 (Codex MEDIUM-5 反映) |
| A3 | N=1 同 base で `semantic_centroid_distance` が degenerate (N≥2 で empirical 検定) | metric 健全性 (DB9 Tier B identity-kernel sanity と類似) |
| A4 | M9-eval Phase 2 既存 capture を input に Vendi が動く (新 corpus 不要、P4a Tier B 流用) | 再利用検証 |
| A5 | benchmark frame (cache hit rate / TTFT / prompt token delta) が baseline 値を出力 | M10-B 前提整備 (Codex HIGH-6) |
| A6 | schema 変更ゼロ (PhilosopherBase / IndividualProfile 未着手) | DB11 整合 |
| A7 | 既存 1356 tests PASS + 新 metric unit tests (≥ 15) PASS | 回帰防止 |
| A8 | `--compute-individuation` flag off で既存 CLI 出力が byte-for-byte 不変 | additive 検証 |

### 2.5 Threshold preregister 表 (G4 修復、M10-0 で固定する候補)

| Threshold | Initial value | Justification source |
|---|---|---|
| Burrows base retention ≥ | 0.6 | design-final.md §5 M11-C |
| pairwise centroid distance ≥ | TBD (M10-0 simulation で bootstrap) | 経験不在、bootstrap CI で設定 |
| Vendi divergence (kernel = MPNet) ≥ | TBD (P4a Tier B sensitivity test 後) | PR #148 follow-up `vendi-kernel-sensitivity` 待ち |
| `worldmodel_update_adoption_rate` band | [0.05, 0.40] | DA-12 |
| `belief_variance > 0` | strict | design-final.md §5 |
| `personality_drift_offset` bound | ±0.1 per axis | DA-12 (M11-C で multi-individual divergence 観測後再 calibration) |
| `big5_icc` (within-base) | TBD (population 立ち上がり後 calibrate) | ICC[2,1] convention |
| recovery_rate band | [0.4, 0.9] (predicted) | M11-C 後 calibrate |

### 2.6 Intervention recovery protocol (G5 修復)

```
prep:
  1. base individual を T_base = 200 tick 走らせ baseline Burrows / SWM snapshot 取得

perturbation:
  2. opposite-stance memory N = 5 entries を retrieved_memories に強制注入
     (e.g. kant に対し "morality is contextual" 系の belief を inject)
  3. T_perturb = 50 tick 走らせ perturbed_floor 計測

recovery:
  4. perturbation 除去後 T_recover = 200 tick 走らせ post recovery 計測

metric:
  recovery_rate    = (post_Burrows - perturbed_floor) / (baseline - perturbed_floor)
  stickiness_rate  = SWM entry persistence ratio (perturbation 方向 entry が T_recover 終了時に survive している割合)
```

- protocol 定義のみ M10-0、実走 M11-C (multi-individual gate)
- T_base / T_perturb / T_recover 数値は M11-B development_state machinery 立ち上がり後の simulation budget と整合させる必要 → M11-C 直前に再 calibration

### 2.7 out-of-scope (明示)

- `PhilosopherBase` / `IndividualProfile` schema 実装 → M10-A
- prompt 注入 (Held world-model entries section) → M10-B
- `WorldModelUpdateHint` の LLMPlan 拡張 → M10-C
- `NarrativeArc` 蒸留 + coherence_score → M11-A
- DevelopmentState transition machinery → M11-B
- Multi-individual same-base validation → M11-C
- Weight / activation 解析 / RL / preference tuning → M12+

### 2.8 PR #127 (M9-B LoRA) への追記必要事項

memo §2.2 / design-final.md §2.1 で既に DB11 として merged 済 (PR #145)。M10-0 着手時に **追加で** 必要な追記:

- M9-eval `--compute-individuation` flag が training-view loader filter (`evaluation_epoch=false AND individual_layer_enabled=false`) を **bypass しない** こと
- individuation metric の計算過程で生成される副作用 (DuckDB write 等) が training data manifest に流入しないこと
- assert: M10-0 で生成される `individuation_metrics` table 行は training pipeline 入口で除外

### 2.9 PR #148 P4a Tier B との接続

- Vendi: `tier_b/vendi.py` を import、kernel は MPNet 既定 (sensitivity follow-up 待ち)
- Big5 ICC: `tier_b/big5_icc.py` を import、ICC[2,1] (DB9 quorum offensive gate 用) を流用
- 両者は M9-eval Phase 2 capture (`_audit_stimulus.json`) を input にできることを A4 で検証

---

## 3. M10-0 タスクの workpackage 分割案

| WP | 内容 | LOC 想定 | depends |
|---|---|---|---|
| WP1 | `src/erre_sandbox/eval/individuation/` 新設 + metric 関数 8 個 (M10-0 phase のみ) | ~400 | P4a Tier B |
| WP2 | DuckDB schema migration (`individuation_metrics` table 追加) | ~80 | WP1 |
| WP3 | M9-eval CLI `--compute-individuation` flag + sidecar JSON key 追加 | ~120 | WP1, WP2 |
| WP4 | mecab ja-tokenizer 移行 + Burrows 再現性 test | ~200 | (none) |
| WP5 | Cache benchmark framework (cache hit rate / TTFT / prompt token counter) | ~150 | (none) |
| WP6 | Prompt ordering contract spec (markdown 仕様、no code) | ~50 lines doc | (none) |
| WP7 | Unit tests (≥ 15) + integration test against M9-eval Phase 2 baseline | ~400 | WP1-3 |
| WP8 | Recovery protocol spec (markdown only、M11-C 実装は別 task) | ~80 lines doc | (none) |

Total LOC 想定: ~1400 production + ~400 test = ~1800 (M9-eval CLI partial-fix +2857/-51 と同程度)。

---

## 4. リスク

| Risk | severity | mitigation |
|---|---|---|
| mecab 移行で kant Burrows が大きく変動 → 既存 baseline 不整合 | HIGH | A2 acceptance に ±0.05 tolerance 設定、超過時は char n-gram と dual-track |
| `semantic_centroid_distance` が embedding model 依存で reproducibility 低い | MEDIUM | model id pin + version capture を `individuation_metrics` 行に含める |
| Big5 ICC が N=1 で degenerate → M10-0 では計算不能 | MEDIUM | A3 で明示 (skip + log)、M11-C で N=3 になってから active |
| recovery protocol の T_base / T_perturb / T_recover が M11-C 実走前に不確定 | LOW | M10-0 で protocol 定義のみ、数値は M11-B 後 calibrate |
| Vendi MPNet kernel が日本語性能不足 (follow-up `multilingual-vendi-encoder` 未着手) | MEDIUM | M10-0 phase では provisional、kernel sensitivity follow-up 完了後 re-calibrate |

---

## 5. Codex review で問いたい点

1. memo §1 判定表の DEFER / ADOPT-WITH-CHANGES 配置は妥当か (特に "活性化・重み分析 = M12+" は科学的に防衛可能か、Hendrycks/Anthropic 系の representation steering 進展を踏まえて)
2. channel × metric matrix (§2.2) で見落としている channel / metric は (e.g. reasoning_trace、cognitive habit recall rate)
3. Big5 ICC 流用は ICC[2,1] consistency か absolute agreement かの選択は妥当か (P4a Tier B Codex 10th review ME-1 vs DB9 split を踏まえて)
4. recovery protocol (§2.6) の perturbation injection 方式 (opposite-stance memory 強制) は ME-9 同型 false-positive リスクを内包しないか
5. mecab ja-tokenizer 移行 (A2) を M10-0 timing で行うべきか、それとも M10-B/C 後の別 task にすべきか (依存最小化観点)
6. WP 分割 (§3) のうち、empirical preregister の閾値が「TBD」のままで M10-0 close できる acceptance になっているが、これは「TBD のまま M10-0 を close + M11-C 直前に固定する」運用で問題ないか
7. M10-0 と並行して進めることの allowed / forbidden 境界 (DB11 制約下、M9-B LoRA execution 中の sidecar metric 開発は許されるか)
8. prior art: Generative Agents / CoALA / Voyager / Identity Drift / Agent Identity Evals / Persistent Personas の最新動向で本 sidecar design に組み込むべき手法は

---

## 6. References

- `reasoning-model-judgment.md` (2026-05-11)
- `design-final.md` §0-3, §5 (PR #144 merged)
- `decisions.md` DA-1 / DA-8 / DA-10 / DA-12 (PR #144 merged)
- `.steering/20260430-m9-b-lora-execution-plan/design-final.md` DB11 ADR Addendum 2026-05-08 (PR #145 merged)
- `src/erre_sandbox/eval/tier_b/` (P4a Tier B、PR #148 merged)
- `docs/architecture.md` §9 (計画中アーキテクチャ)

codex
I’ve got the first-pass design context. Next I’m checking the contamination ADR, capture artifacts, and existing Tier B metric implementations because most likely failure modes are at those interfaces.
exec
/bin/zsh -lc "sed -n '1,280p' .steering/20260430-m9-b-lora-execution-plan/design-final.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '260,620p' .steering/20260508-cognition-deepen-7point-proposal/design-final.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
  - 3 IndividualProfile を同 PhilosopherBase (kant) から起動
  - Burrows = base retention ≥ 0.6 (= 同じ値 = 成功)
  - sidecar metrics で個体化 ≥ threshold (semantic centroid pairwise distance、belief variance、
    NarrativeArc 差異)
  - acceptance: 「base 保持 + 個体化分離」が同時成立する empirical evidence

[M12+ research re-evaluation gate]
  - S4_articulation / S5_late stage 検討 (M11-B 経験を踏まえ first principles で必要性
    判断、Codex HIGH-5 抑制)
  - retirement / rebirth (path B / C 検討、Codex Q2 default = A 不完成停滞)
  - multi-base society (kant + rikyu + nietzsche × 各 N individuals)
  - individual layer の LoRA 適用判定 (Codex HIGH-3 後継)
  - 上記いずれも先に decision 固定しない、empirical gate
```

## 4. 既存資産への影響 (rename / migration)

| 対象 | 改修種別 | timing |
|---|---|---|
| `personas/*.yaml` | rename **しない**、schema_version 0.10.0-m7h 維持 (Codex MEDIUM-1) | M10 中触らない |
| `PersonaSpec` (schemas.py) | wrapper を追加 → `PhilosopherBase` として読める (Codex MEDIUM-1) | M10-A |
| `AgentState.persona_id` | base reference の getter 維持で互換 | M10-A |
| `AgentState.shuhari_stage` | 既存維持。意味は **base 側技能習得** に限定 (lifecycle は Individual 側 DevelopmentState) | M10-A docstring update |
| `SemanticMemoryRecord.belief_kind` | 既存維持。dyadic only として SWM `axis` と直交 | unchanged |
| `cognition/belief.py:maybe_promote_belief` | pure function pattern を `apply_world_model_update_hint` 等に踏襲 | M10-C 流用 |
| `LLMPlan` | additive 拡張のみ (minor bump) | M10-C |
| `cognition/prompting.py:_format_persona_block` | `PhilosopherBase` 系統 + Individual 注入の責務分離 | M10-B |
| `format_memories` | memory id を prompt に出すよう契約変更 (Codex MEDIUM-2 dependency) | M10-A |

## 5. Acceptance criteria (per milestone、定量)

| Milestone | Quantitative criterion |
|---|---|
| M10-0 | 個体化 sidecar metric が baseline で valid 値を返す、benchmark 枠組み green |
| M10-A | 1318 tests PASS、新 schema golden test green、wrapper 互換 (既存 personas load OK) |
| M10-B | cache hit rate ≥ 80% baseline、TTFT delta ≤ 5%、prompt token +200 以内、SWM が persona 別に異なる軸で立ち上がる (Burrows 直交シグナル) |
| M10-C | adoption rate `[0.05, 0.40]` 内 (LLM が cite 諦めず、free-form は採用されず)、golden test 「free-form belief 主張は採用されない」 PASS |
| M11-A | coherence_score 計算が走る (diagnostic only)、low coherence で reflection 深化 trigger が発火 |
| M11-B | 1 individual 1000-tick で S1→S2→S3 が observable evidence 駆動で発火、LLM 自己申告 stripped run で発火しない (negative control) |
| M11-C | Burrows ≥ 0.6 (base 保持)、semantic centroid pairwise distance ≥ threshold (個体化)、belief variance > 0 (Codex HIGH-4 分解測定) |

## 6. Open questions left for implementation tasks (defer)

- `decay_half_life_ticks = 1000` の calibration: M10-B 実装時に simulation で再 tune
- `WorldModelUpdateHint.adoption rate` 目標 band `[0.05, 0.40]` の根拠: M10-C empirical
  測定後再評価
- `personality_drift_offset` の bounded 範囲 (±0.1 per axis): M11-C で multi-individual
  divergence 観測後再 calibration
- `coherence_score` の hard threshold: M11-A diagnostic phase 後、false-positive rate
  測定して M11-B で hard gate 化検討

## 7. Source documents

- 旧 design.md: Claude Plan-mode initial 判定 (個別 schema として読み、提案 6/7 を REJECT/DEFER)
- 旧 design-clarified.md: User clarification 反映 (二層解釈、Option A vision)
- 旧 design-reimagine.md: independent reimagine (Compression-Loop counter、persona identity 維持
  vs user vision の核 tension を提示)
- codex-review.md: Codex `gpt-5.5 xhigh` 197K tokens、ADOPT-WITH-CHANGES、HIGH 7 / MEDIUM 5 /
  LOW 3、prior art 9 件 web 引用 (Generative Agents / CoALA / Voyager / Identity Drift /
  Persistent Personas EACL 2026 / Agent Identity Evals 2025 / Memoria Memori / Piaget 批判 /
  SGLang RadixAttention LoRA)
- 本書 design-final.md: 3-source synthesis、Codex HIGH 7 件すべて反映、User Option A 維持

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
/bin/zsh -lc "find data/eval/golden -maxdepth 2 -type f | sort | sed -n '1,120p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
data/eval/golden/_audit_stimulus.json
data/eval/golden/_checksums_mac_received.txt
data/eval/golden/_checksums_phase_b.txt
data/eval/golden/kant_stimulus_run0.duckdb
data/eval/golden/kant_stimulus_run0.duckdb.capture.json
data/eval/golden/kant_stimulus_run1.duckdb
data/eval/golden/kant_stimulus_run1.duckdb.capture.json
data/eval/golden/kant_stimulus_run2.duckdb
data/eval/golden/kant_stimulus_run2.duckdb.capture.json
data/eval/golden/kant_stimulus_run3.duckdb
data/eval/golden/kant_stimulus_run3.duckdb.capture.json
data/eval/golden/kant_stimulus_run4.duckdb
data/eval/golden/kant_stimulus_run4.duckdb.capture.json
data/eval/golden/nietzsche_stimulus_run0.duckdb
data/eval/golden/nietzsche_stimulus_run0.duckdb.capture.json
data/eval/golden/nietzsche_stimulus_run1.duckdb
data/eval/golden/nietzsche_stimulus_run1.duckdb.capture.json
data/eval/golden/nietzsche_stimulus_run2.duckdb
data/eval/golden/nietzsche_stimulus_run2.duckdb.capture.json
data/eval/golden/nietzsche_stimulus_run3.duckdb
data/eval/golden/nietzsche_stimulus_run3.duckdb.capture.json
data/eval/golden/nietzsche_stimulus_run4.duckdb
data/eval/golden/nietzsche_stimulus_run4.duckdb.capture.json
data/eval/golden/rikyu_stimulus_run0.duckdb
data/eval/golden/rikyu_stimulus_run0.duckdb.capture.json
data/eval/golden/rikyu_stimulus_run1.duckdb
data/eval/golden/rikyu_stimulus_run1.duckdb.capture.json
data/eval/golden/rikyu_stimulus_run2.duckdb
data/eval/golden/rikyu_stimulus_run2.duckdb.capture.json
data/eval/golden/rikyu_stimulus_run3.duckdb
data/eval/golden/rikyu_stimulus_run3.duckdb.capture.json
data/eval/golden/rikyu_stimulus_run4.duckdb
data/eval/golden/rikyu_stimulus_run4.duckdb.capture.json

exec
/bin/zsh -lc "rg --files src/erre_sandbox/eval/tier_b tests data/eval/golden | sed -n '1,220p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
rg: src/erre_sandbox/eval/tier_b: No such file or directory (os error 2)
tests/test_main.py
tests/test_godot_mode_tint.py
tests/test_ui/test_messages.py
tests/test_ui/test_stub.py
tests/test_ui/test_server.py
tests/test_ui/test_state.py
tests/test_ui/__init__.py
tests/test_ui/conftest.py
tests/test_cli/test_eval_audit.py
tests/test_cli/test_eval_run_golden.py
tests/test_smoke.py
tests/test_godot_peripatos.py
tests/test_schemas_m5.py
data/eval/golden/kant_stimulus_run0.duckdb.capture.json
data/eval/golden/kant_stimulus_run1.duckdb.capture.json
tests/test_training/test_train_kant_lora.py
data/eval/golden/kant_stimulus_run2.duckdb.capture.json
tests/test_training/test_prompt_builder.py
data/eval/golden/_audit_stimulus.json
tests/test_training/test_dataset.py
tests/test_training/__init__.py
data/eval/golden/rikyu_stimulus_run4.duckdb.capture.json
tests/test_training/conftest.py
data/eval/golden/kant_stimulus_run3.duckdb.capture.json
data/eval/golden/rikyu_stimulus_run3.duckdb.capture.json
data/eval/golden/kant_stimulus_run4.duckdb.capture.json
data/eval/golden/rikyu_stimulus_run2.duckdb.capture.json
data/eval/golden/rikyu_stimulus_run1.duckdb.capture.json
data/eval/golden/_checksums_phase_b.txt
data/eval/golden/rikyu_stimulus_run0.duckdb.capture.json
data/eval/golden/_checksums_mac_received.txt
data/eval/golden/nietzsche_stimulus_run4.duckdb.capture.json
data/eval/golden/nietzsche_stimulus_run0.duckdb.capture.json
data/eval/golden/nietzsche_stimulus_run1.duckdb.capture.json
data/eval/golden/nietzsche_stimulus_run2.duckdb.capture.json
data/eval/golden/nietzsche_stimulus_run3.duckdb.capture.json
tests/test_cli_export_log.py
tests/test_godot_project.py
tests/test_memory/test_embedding_prefix.py
tests/test_memory/test_semantic_layer.py
tests/test_memory/test_embedding.py
tests/test_memory/test_store.py
tests/test_memory/__init__.py
tests/test_memory/test_retrieval.py
tests/test_memory/conftest.py
tests/__init__.py
tests/test_schema_contract.py
tests/test_persona_kant.py
tests/test_schemas_m7g.py
tests/test_erre/test_sampling_table.py
tests/test_erre/test_fsm.py
tests/test_erre/__init__.py
tests/test_schemas_m6.py
tests/test_envelope_fixtures.py
tests/test_cognition/test_prompting.py
tests/test_cognition/test_trigger_pick.py
tests/test_cognition/test_biorhythm_events.py
tests/test_cognition/test_reasoning_trace.py
tests/test_cognition/test_erre_mode_events.py
tests/test_cognition/test_belief_promotion.py
tests/test_cognition/test_decision_with_affinity.py
tests/test_cognition/test_cycle.py
tests/test_cognition/test_reflection.py
tests/test_cognition/test_importance.py
tests/test_cognition/test_state.py
tests/test_cognition/__init__.py
tests/test_cognition/test_relational.py
tests/test_cognition/test_zone_bias.py
tests/test_cognition/test_cycle_erre_fsm.py
tests/test_cognition/test_parse.py
tests/test_cognition/test_reflection_envelope.py
tests/test_cognition/test_movement_speed_persona_factor.py
tests/test_cognition/conftest.py
tests/test_cognition/test_relational_simulation.py
tests/test_schemas.py
tests/test_world/test_runtime_lifecycle.py
tests/test_world/test_apply_affinity_delta.py
tests/test_world/test_physics.py
tests/test_world/test_separation_force.py
tests/test_world/test_temporal_events.py
tests/test_world/test_tick.py
tests/test_world/__init__.py
tests/test_world/test_per_agent_cognition_period.py
tests/test_world/test_affordance_events.py
tests/test_world/test_apply_belief_promotion.py
tests/test_world/test_proximity_events.py
tests/test_world/conftest.py
tests/test_world/test_zones.py
tests/schema_golden/control_envelope.schema.json
tests/schema_golden/README.md
tests/schema_golden/persona_spec.schema.json
tests/schema_golden/agent_state.schema.json
tests/fixtures/synthetic_4th_mcq.yaml
tests/test_godot_ws_client.py
tests/_godot_helpers.py
tests/test_behavior_profile.py
tests/test_inference/test_sampling.py
tests/test_inference/test_sglang_adapter.py
tests/test_inference/__init__.py
tests/test_inference/test_ollama_adapter.py
tests/fixtures/m4/reflection_event.json
tests/fixtures/m4/agent_spec_3agents.json
tests/fixtures/m4/semantic_memory_record.json
tests/test_bootstrap.py
tests/test_godot_dialog_bubble.py
tests/test_envelope_kind_sync.py
tests/test_tools/test_build_mock_lora.py
tests/test_tools/__init__.py
tests/test_evidence/test_golden_stimulus_schema.py
tests/test_evidence/test_scaling_metrics.py
tests/test_evidence/test_eval_store.py
tests/test_integration/test_slice_gamma_e2e.py
tests/test_integration/test_scenario_walking.py
tests/test_integration/test_contract_snapshot.py
tests/test_integration/test_dialog_sink.py
tests/test_integration/test_dialog_turn.py
tests/test_integration/test_dialog_eval_natural_mode.py
tests/test_integration/test_dialog.py
tests/test_integration/test_dialog_golden_baseline_mode.py
tests/test_integration/test_dialog_orchestration_wiring.py
tests/test_integration/__init__.py
tests/test_integration/test_multi_agent_stream.py
tests/test_integration/test_slice_delta_e2e.py
tests/test_integration/test_scenario_memory_write.py
tests/test_integration/test_gateway.py
tests/test_integration/test_scenario_tick_robustness.py
tests/test_integration/_ws_helpers.py
tests/test_integration/conftest.py
tests/test_integration/test_world_layout_msg.py
tests/test_architecture/__init__.py
tests/test_architecture/test_layer_dependencies.py
tests/conftest.py
tests/test_evidence/test_metrics.py
tests/test_evidence/test_p3a_decide.py
tests/test_evidence/test_capture_sidecar.py
tests/test_evidence/test_tier_b/test_ipip_neo.py
tests/test_evidence/test_tier_b/__init__.py
tests/test_evidence/test_tier_b/test_big5_icc.py
tests/test_evidence/test_tier_b/test_vendi.py
tests/test_evidence/test_eval_paths_contract.py
tests/test_evidence/test_golden_baseline.py
tests/test_evidence/__init__.py
tests/test_evidence/test_bootstrap_ci.py
tests/test_cli_baseline_metrics.py
tests/test_personas/test_load_all.py
tests/test_personas/__init__.py
tests/test_evidence/test_tier_a/test_nli.py
tests/test_evidence/test_tier_a/test_novelty.py
tests/test_evidence/test_tier_a/test_mattr.py
tests/test_evidence/test_tier_a/__init__.py
tests/test_evidence/test_tier_a/test_empath_proxy.py
tests/test_evidence/test_tier_a/test_burrows_corpus_qc.py
tests/test_evidence/test_tier_a/test_burrows.py

exec
/bin/zsh -lc "sed -n '280,620p' .steering/20260430-m9-b-lora-execution-plan/design-final.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
| LOW-1 (synthetic 4th persona) | DB7 → eval test scenario として採用 | ✅ 反映 |
| LOW-2 (LIWC alternatives honest) | DB10 → proxy/equivalence honest framing | ✅ 反映 |
| **Final note (third option)** | M9-C-spike として並行構造化 | ✅ **反映 = 設計の中核転換** |

## 残存リスク (LOW defer to blockers.md)

`blockers.md` 参照。主な defer:
- LIWC 商用 license の最終可否判定 (M9-eval-system 中)
- Burrows' Delta multi-language strategy 詳細 (M9-eval-system 中)
- Prometheus 2 / G-Eval bias mitigation runbook (M9-eval-system 中)
- 専門家 qualitative review の人 selection (M9-C-adopt 直前)

## Addendum 2026-05-08 — Cognition deepening (PR #144) interaction

PR #144 (`docs/cognition-deepen-decision-2026-05-08`、main=`e641f8d`) で確定した認知深化
二層 architecture (`PhilosopherBase` + `IndividualProfile`) と本 M9-B LoRA training
pipeline の **contamination 防止** 制約を本書に取り込む。詳細は
`.steering/20260508-cognition-deepen-7point-proposal/design-final.md` §2.1 および
同 dir `decisions.md` DA-8、Codex `gpt-5.5 xhigh` review HIGH-3 を参照。

### 追加制約 (DB11 ADR、本 dir `decisions.md` 参照)

1. **dataset partition flag**: 既存の `evaluation_epoch` flag と並列に
   `individual_layer_enabled: bool` フィールドを raw_dialog metadata に追加 (default=false)。
2. **training-view contract 拡張**: `evaluation_epoch=false` only loader を
   `evaluation_epoch=false AND individual_layer_enabled=false` only loader に拡張。
3. **pipeline assert**: training pipeline 入口で
   `all(row.metadata.individual_layer_enabled is False)` を assert、contamination
   検出時は fail-fast。
4. **scaffold 並行可**: M10-A scaffold (PR #144 phasing) は feature flag default off で
   M9-B execution と並行可、ただし `individual_layer_enabled=true` で生成された
   raw_dialog は training export から **必ず除外**。

### 適用範囲

- **M9-eval-system** Parquet pipeline 実装時: `individual_layer_enabled` field 追加 (DB5 拡張)
- **M9-C-adopt** (LoRA execution): training-view loader assert 実装
- **M10-A scaffold** (post-M9): IndividualProfile activation 時に raw_dialog meta に
  `individual_layer_enabled=true` を立てる責務

### 影響なし

- DB1-DB10 ADR の本体 logic (量子化戦略 / SGLang-first / dataset trigger / drift gate / 等)
  はすべて変更なし
- M9-B execution 着手前提も変更なし (M9-eval-system 完了 + M9-C-spike 並行 + ready 達成後)
- 既存 raw_dialog data (M9-A / M7ζ / 過去 run) は `individual_layer_enabled=false` で
  default 解釈して問題なし (Individual layer は M10+ にのみ存在する)

exec
/bin/zsh -lc "sed -n '1,220p' data/eval/golden/_audit_stimulus.json" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,220p' data/eval/golden/kant_stimulus_run0.duckdb.capture.json" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
{
  "schema_version": "1",
  "status": "complete",
  "stop_reason": "complete",
  "focal_target": 500,
  "focal_observed": 504,
  "total_rows": 852,
  "wall_timeout_min": 120.0,
  "drain_completed": true,
  "runtime_drain_timeout": false,
  "git_sha": "ae679ac",
  "captured_at": "2026-05-09T03:54:57Z",
  "persona": "kant",
  "condition": "stimulus",
  "run_idx": 0,
  "duckdb_path": "C:\\ERRE-Sand_Box\\data\\eval\\golden\\kant_stimulus_run0.duckdb"
}
 succeeded in 0ms:
{
  "audited_at": "2026-05-09T05:10:59Z",
  "duckdb_glob": "data/eval/golden/*_stimulus_run*.duckdb",
  "focal_target": 500,
  "allow_partial": false,
  "total": 15,
  "complete": 15,
  "partial": 0,
  "missing_sidecar": 0,
  "mismatch": 0,
  "fail": 0,
  "overall_exit_code": 0,
  "details": [
    {
      "duckdb_path": "data\\eval\\golden\\kant_stimulus_run0.duckdb",
      "sidecar_path": "data\\eval\\golden\\kant_stimulus_run0.duckdb.capture.json",
      "status": "complete",
      "stop_reason": "complete",
      "focal_observed": 504,
      "focal_target": 500,
      "sidecar_total_rows": 852,
      "persona": "kant",
      "condition": "stimulus",
      "run_idx": 0,
      "actual_total_rows": 852,
      "actual_focal_rows": 504,
      "actual_run_ids": [
        "kant_stimulus_run0"
      ],
      "expected_run_id": "kant_stimulus_run0",
      "reason": "complete_pass",
      "exit_code": 0
    },
    {
      "duckdb_path": "data\\eval\\golden\\kant_stimulus_run1.duckdb",
      "sidecar_path": "data\\eval\\golden\\kant_stimulus_run1.duckdb.capture.json",
      "status": "complete",
      "stop_reason": "complete",
      "focal_observed": 504,
      "focal_target": 500,
      "sidecar_total_rows": 852,
      "persona": "kant",
      "condition": "stimulus",
      "run_idx": 1,
      "actual_total_rows": 852,
      "actual_focal_rows": 504,
      "actual_run_ids": [
        "kant_stimulus_run1"
      ],
      "expected_run_id": "kant_stimulus_run1",
      "reason": "complete_pass",
      "exit_code": 0
    },
    {
      "duckdb_path": "data\\eval\\golden\\kant_stimulus_run2.duckdb",
      "sidecar_path": "data\\eval\\golden\\kant_stimulus_run2.duckdb.capture.json",
      "status": "complete",
      "stop_reason": "complete",
      "focal_observed": 504,
      "focal_target": 500,
      "sidecar_total_rows": 852,
      "persona": "kant",
      "condition": "stimulus",
      "run_idx": 2,
      "actual_total_rows": 852,
      "actual_focal_rows": 504,
      "actual_run_ids": [
        "kant_stimulus_run2"
      ],
      "expected_run_id": "kant_stimulus_run2",
      "reason": "complete_pass",
      "exit_code": 0
    },
    {
      "duckdb_path": "data\\eval\\golden\\kant_stimulus_run3.duckdb",
      "sidecar_path": "data\\eval\\golden\\kant_stimulus_run3.duckdb.capture.json",
      "status": "complete",
      "stop_reason": "complete",
      "focal_observed": 504,
      "focal_target": 500,
      "sidecar_total_rows": 852,
      "persona": "kant",
      "condition": "stimulus",
      "run_idx": 3,
      "actual_total_rows": 852,
      "actual_focal_rows": 504,
      "actual_run_ids": [
        "kant_stimulus_run3"
      ],
      "expected_run_id": "kant_stimulus_run3",
      "reason": "complete_pass",
      "exit_code": 0
    },
    {
      "duckdb_path": "data\\eval\\golden\\kant_stimulus_run4.duckdb",
      "sidecar_path": "data\\eval\\golden\\kant_stimulus_run4.duckdb.capture.json",
      "status": "complete",
      "stop_reason": "complete",
      "focal_observed": 504,
      "focal_target": 500,
      "sidecar_total_rows": 852,
      "persona": "kant",
      "condition": "stimulus",
      "run_idx": 4,
      "actual_total_rows": 852,
      "actual_focal_rows": 504,
      "actual_run_ids": [
        "kant_stimulus_run4"
      ],
      "expected_run_id": "kant_stimulus_run4",
      "reason": "complete_pass",
      "exit_code": 0
    },
    {
      "duckdb_path": "data\\eval\\golden\\nietzsche_stimulus_run0.duckdb",
      "sidecar_path": "data\\eval\\golden\\nietzsche_stimulus_run0.duckdb.capture.json",
      "status": "complete",
      "stop_reason": "complete",
      "focal_observed": 504,
      "focal_target": 500,
      "sidecar_total_rows": 852,
      "persona": "nietzsche",
      "condition": "stimulus",
      "run_idx": 0,
      "actual_total_rows": 852,
      "actual_focal_rows": 504,
      "actual_run_ids": [
        "nietzsche_stimulus_run0"
      ],
      "expected_run_id": "nietzsche_stimulus_run0",
      "reason": "complete_pass",
      "exit_code": 0
    },
    {
      "duckdb_path": "data\\eval\\golden\\nietzsche_stimulus_run1.duckdb",
      "sidecar_path": "data\\eval\\golden\\nietzsche_stimulus_run1.duckdb.capture.json",
      "status": "complete",
      "stop_reason": "complete",
      "focal_observed": 504,
      "focal_target": 500,
      "sidecar_total_rows": 852,
      "persona": "nietzsche",
      "condition": "stimulus",
      "run_idx": 1,
      "actual_total_rows": 852,
      "actual_focal_rows": 504,
      "actual_run_ids": [
        "nietzsche_stimulus_run1"
      ],
      "expected_run_id": "nietzsche_stimulus_run1",
      "reason": "complete_pass",
      "exit_code": 0
    },
    {
      "duckdb_path": "data\\eval\\golden\\nietzsche_stimulus_run2.duckdb",
      "sidecar_path": "data\\eval\\golden\\nietzsche_stimulus_run2.duckdb.capture.json",
      "status": "complete",
      "stop_reason": "complete",
      "focal_observed": 504,
      "focal_target": 500,
      "sidecar_total_rows": 852,
      "persona": "nietzsche",
      "condition": "stimulus",
      "run_idx": 2,
      "actual_total_rows": 852,
      "actual_focal_rows": 504,
      "actual_run_ids": [
        "nietzsche_stimulus_run2"
      ],
      "expected_run_id": "nietzsche_stimulus_run2",
      "reason": "complete_pass",
      "exit_code": 0
    },
    {
      "duckdb_path": "data\\eval\\golden\\nietzsche_stimulus_run3.duckdb",
      "sidecar_path": "data\\eval\\golden\\nietzsche_stimulus_run3.duckdb.capture.json",
      "status": "complete",
      "stop_reason": "complete",
      "focal_observed": 504,
      "focal_target": 500,
      "sidecar_total_rows": 852,
      "persona": "nietzsche",
      "condition": "stimulus",
      "run_idx": 3,
      "actual_total_rows": 852,
      "actual_focal_rows": 504,
      "actual_run_ids": [
        "nietzsche_stimulus_run3"
      ],
      "expected_run_id": "nietzsche_stimulus_run3",
      "reason": "complete_pass",
      "exit_code": 0
    },
    {
      "duckdb_path": "data\\eval\\golden\\nietzsche_stimulus_run4.duckdb",
      "sidecar_path": "data\\eval\\golden\\nietzsche_stimulus_run4.duckdb.capture.json",
      "status": "complete",
      "stop_reason": "complete",
      "focal_observed": 504,
      "focal_target": 500,
      "sidecar_total_rows": 852,
      "persona": "nietzsche",
      "condition": "stimulus",
      "run_idx": 4,
      "actual_total_rows": 852,
      "actual_focal_rows": 504,
      "actual_run_ids": [
        "nietzsche_stimulus_run4"
      ],
      "expected_run_id": "nietzsche_stimulus_run4",
      "reason": "complete_pass",
      "exit_code": 0
    },
    {
      "duckdb_path": "data\\eval\\golden\\rikyu_stimulus_run0.duckdb",
      "sidecar_path": "data\\eval\\golden\\rikyu_stimulus_run0.duckdb.capture.json",
      "status": "complete",
      "stop_reason": "complete",
      "focal_observed": 504,
      "focal_target": 500,

exec
/bin/zsh -lc "rg --files src/erre_sandbox | rg 'tier_b|vendi|big5|ipip|burrows|capture|eval_store|audit|golden'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
src/erre_sandbox/evidence/golden_baseline.py
src/erre_sandbox/evidence/tier_b/ipip_neo.py
src/erre_sandbox/evidence/tier_b/vendi.py
src/erre_sandbox/evidence/tier_b/big5_icc.py
src/erre_sandbox/evidence/tier_b/__init__.py
src/erre_sandbox/evidence/capture_sidecar.py
src/erre_sandbox/evidence/eval_store.py
src/erre_sandbox/evidence/tier_a/burrows.py
src/erre_sandbox/cli/eval_run_golden.py
src/erre_sandbox/cli/eval_audit.py

exec
/bin/zsh -lc "sed -n '1,260p' src/erre_sandbox/evidence/capture_sidecar.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,280p' src/erre_sandbox/evidence/eval_store.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""``capture_sidecar`` — atomic JSON metadata sibling for eval capture files.

Spec: ``.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`` §1.4.
Adopted in m9-eval-cli-partial-fix (ME-9 ADR) so partial / fatal / complete
captures can be **machine-distinguished** without re-opening the DuckDB file.

Design notes (Codex 2026-05-06 review reflected):

* ``CaptureStatus`` and ``StopReason`` are :class:`typing.Literal` so the
  ``_async_main`` 3-way ``match`` in :mod:`erre_sandbox.cli.eval_run_golden`
  can use ``assert_never`` for exhaustiveness.
* ``SidecarV1.model_config = ConfigDict(extra="allow")`` so a future
  ``event_log`` / ``q_and_a_subset`` additive field does not require a
  major schema_version bump (Codex Q2).
* ``write_sidecar_atomic`` reuses :func:`atomic_temp_rename` from
  :mod:`erre_sandbox.evidence.eval_store` for same-filesystem POSIX rename.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from erre_sandbox.evidence.eval_store import atomic_temp_rename

CaptureStatus = Literal["complete", "partial", "fatal"]
"""Top-level capture outcome (drives audit gate + return code)."""

StopReason = Literal[
    "complete",
    "wall_timeout",
    "fatal_duckdb_insert",
    "fatal_ollama",
    "fatal_drain_timeout",
    "fatal_incomplete_before_target",
    "fatal_runtime_exception",
]
"""Concrete reason capture stopped — pinned via Codex L2 review."""

SIDECAR_SUFFIX: Final[str] = ".capture.json"
"""Filename suffix appended to the DuckDB path (e.g. ``foo.duckdb.capture.json``)."""

SIDECAR_SCHEMA_VERSION: Final[str] = "1"
"""Current schema version. ``extra='allow'`` covers additive fields."""

_SIDECAR_MAX_BYTES: Final[int] = 1 * 1024 * 1024
"""Defensive cap on a single sidecar JSON read (security review 2026-05-06).

Sidecars are produced by our own CLI so legitimate files stay under a few KB
even with future ``event_log`` additions; a multi-MB sidecar after rsync
from G-GEAR is the symptom of corruption or tampering. The cap is generous
to avoid false positives but guards :func:`read_sidecar` against
loading-the-whole-file-into-memory DoS."""


class SidecarV1(BaseModel):
    """v1 metadata payload alongside ``<output>.duckdb``.

    The discriminated ``status`` + ``stop_reason`` pair is what the audit
    CLI (:mod:`erre_sandbox.cli.eval_audit`) reads to decide PASS / FAIL.
    ``total_rows`` and ``focal_observed`` are cross-checked against the
    DuckDB ``raw_dialog.dialog`` table; mismatch yields return code 5.
    """

    model_config = ConfigDict(extra="allow")

    schema_version: Literal["1"] = "1"
    status: CaptureStatus
    stop_reason: StopReason
    focal_target: int
    focal_observed: int
    total_rows: int
    wall_timeout_min: float
    drain_completed: bool
    runtime_drain_timeout: bool
    git_sha: str
    captured_at: str
    persona: str
    condition: Literal["stimulus", "natural"]
    run_idx: int
    duckdb_path: str


def sidecar_path_for(duckdb_path: Path | str) -> Path:
    """Return the conventional sidecar path for *duckdb_path*."""
    p = Path(duckdb_path)
    return p.with_suffix(p.suffix + SIDECAR_SUFFIX)


def expected_run_id(payload: SidecarV1) -> str:
    """Reconstruct the ``raw_dialog.dialog.run_id`` value the capture used.

    Reflects Codex H1 (audit must verify same-run integrity): the eval CLI
    builds ``run_id`` from ``f"{persona}_{condition}_run{run_idx}"`` and
    persists every row with it; audit re-derives the same string from the
    sidecar to detect cross-cell contamination.
    """
    return f"{payload.persona}_{payload.condition}_run{payload.run_idx}"


def write_sidecar_atomic(path: Path | str, payload: SidecarV1) -> None:
    """Atomically write *payload* as JSON to *path* (temp + same-fs rename).

    Uses :func:`atomic_temp_rename` so the rename fails loudly if *path*
    crosses a filesystem boundary (NFS / SMB / iCloud are out of scope per
    ME-2). The temp file lives next to *path* with a ``.tmp`` suffix and is
    overwritten on retry.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    atomic_temp_rename(tmp, path)


def read_sidecar(path: Path | str) -> SidecarV1:
    """Read and validate a sidecar file.

    Raises :class:`pydantic.ValidationError` for schema violations (e.g.
    unknown ``status`` / ``stop_reason`` Literal value, missing required
    fields). The audit CLI converts this into return code 5 (mismatch);
    rescue tooling demands ``--force-rescue`` (Codex M4).

    Refuses files larger than :data:`_SIDECAR_MAX_BYTES` with
    :class:`OSError` so a corrupted / tampered sidecar cannot exhaust
    memory in the audit CLI (security review 2026-05-06 MEDIUM).
    """
    p = Path(path)
    size = p.stat().st_size
    if size > _SIDECAR_MAX_BYTES:
        msg = (
            f"sidecar {p!s} is {size} bytes, exceeds defensive cap {_SIDECAR_MAX_BYTES}"
        )
        raise OSError(msg)
    raw = json.loads(p.read_text(encoding="utf-8"))
    return SidecarV1.model_validate(raw)


__all__ = [
    "SIDECAR_SCHEMA_VERSION",
    "SIDECAR_SUFFIX",
    "CaptureStatus",
    "SidecarV1",
    "StopReason",
    "expected_run_id",
    "read_sidecar",
    "sidecar_path_for",
    "write_sidecar_atomic",
]

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
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Self

import duckdb

from erre_sandbox.contracts.eval_paths import (
    ALLOWED_RAW_DIALOG_KEYS,
    INDIVIDUAL_LAYER_ENABLED_KEY,
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
    # B-1 (m9-individual-layer-schema-add, Codex HIGH-1): NOT NULL +
    # DEFAULT FALSE keeps the column bivalent and lets existing INSERTs
    # that omit the new column still succeed with explicit false.
    ("individual_layer_enabled", "BOOLEAN NOT NULL DEFAULT FALSE"),
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

        # Aggregate row-level contamination check (Codex HIGH-2 / DB11 /
        # B-1): ``connect_training_view()`` is the loader boundary
        # contracted by blockers.md §B-1, so we raise *before* any caller
        # can reach ``iter_rows`` past a row that carries
        # ``epoch_phase=evaluation`` or a truthy / NULL
        # ``individual_layer_enabled``. SQL aggregate is used (not a
        # ``WHERE`` filter) to avoid silently diluting the
        # ``min_examples`` count check downstream in
        # ``assert_phase_beta_ready``. The aggregate is skipped when
        # either column is absent (legacy / pre-B-1 schemas) — those
        # cases are still picked up by ``assert_phase_beta_ready``
        # itself, so backwards compatibility at the loader is
        # preserved.
        column_set = frozenset(self._columns)
        if "epoch_phase" in column_set and INDIVIDUAL_LAYER_ENABLED_KEY in column_set:
            agg_row = self._conn.execute(
                "SELECT"  # noqa: S608  # all interpolations are module-private constants
                " COALESCE(SUM(CASE WHEN LOWER(epoch_phase) = 'evaluation'"
                " THEN 1 ELSE 0 END), 0),"
                f" COALESCE(SUM(CASE WHEN {INDIVIDUAL_LAYER_ENABLED_KEY}"
                f" IS NOT FALSE THEN 1 ELSE 0 END), 0)"
                f" FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}",
            ).fetchone()
            eval_count = int(agg_row[0]) if agg_row else 0
            ind_count = int(agg_row[1]) if agg_row else 0
            if eval_count > 0:
                raise EvaluationContaminationError(
                    f"raw_dialog.{RAW_DIALOG_TABLE}: {eval_count} row(s)"
                    f" carry epoch_phase~='evaluation' (case-insensitive)"
                    f" at construction time — rejecting at the loader"
                    f" boundary (Codex HIGH-2 / DB11 / B-1)",
                )
            if ind_count > 0:
                raise EvaluationContaminationError(
                    f"raw_dialog.{RAW_DIALOG_TABLE}: {ind_count} row(s)"
                    f" carry truthy or NULL {INDIVIDUAL_LAYER_ENABLED_KEY}"
                    f" at construction time — rejecting at the loader"
                    f" boundary (Codex HIGH-2 / DB11 / B-1)",
                )

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

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

exec
/bin/zsh -lc "sed -n '1,260p' src/erre_sandbox/evidence/tier_a/burrows.py" in /Users/johnd/ERRE-Sand Box
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

exec
/bin/zsh -lc "sed -n '1,260p' src/erre_sandbox/evidence/tier_b/ipip_neo.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""IPIP-50 (Goldberg 1992) administering helper for Tier B Big5 ICC.

The 50 items are vendored verbatim from the public-domain IPIP corpus
(https://ipip.ori.org/, English official, public domain commercial use OK).
Mini-IPIP-20 is intentionally not implemented because Mini-IPIP α 0.65-0.70
sits on the ME-1 fallback boundary 0.6 (M9-eval ME-12); IPIP-50 broad-domain
α ≈ 0.84 (https://ipip.ori.org/newBigFive5broadTable.htm).

Anti-demand-characteristics design (Codex P4a HIGH-4 / M9-eval ME-13). LLMs
infer personality-test context and shift toward socially desirable answers
(Salecha et al. 2024, https://arxiv.org/abs/2405.06058); the prompt template
therefore avoids "personality test", "Big Five", "IPIP", "questionnaire",
"survey", and "psychological" wording. Items are presented one at a time in
deterministically shuffled order, and decoy items dilute the test-taking
context inference.

Japanese administration is deferred (Codex P4a HIGH-3 / ME-12). The Murakami
2002/2003 lexical Big Five papers are not an IPIP-50 translation source; the
official IPIP translations page lists Nakayama/Karlin Japanese IPIP and a
license-cleared 50-item subset is required before ``language="ja"`` can be
admitted. Until then the helper raises ``NotImplementedError`` for ``ja``.

LIWC alternative honest framing (M9-B DB10 Option D): IPIP self-report only —
no LIWC equivalence claim, no external-lexicon Big5 inference. Tier A
``empath_proxy`` is a separate psycholinguistic axis (ME-1 / DB10 Option D).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

PersonaResponder = Callable[[str], int]
"""Stub-friendly callable: take an item prompt, return a 1..5 Likert integer.

Tests pass a deterministic stub (e.g. constant 3, alternating 1/5) so the
helper exercises scoring / shuffling / diagnostics without an LLM round-trip.
"""

DEFAULT_LIKERT_MIN: int = 1
DEFAULT_LIKERT_MAX: int = 5
"""5-point Likert administration (Codex P4a LOW-1 keep)."""

DEFAULT_DECOY_COUNT: int = 5
"""Decoy items count (Codex P4a HIGH-4)."""

PROMPT_TEMPLATE_EN: str = (
    "Read the statement and reply with one digit from 1 to 5 indicating how"
    " well it describes you, where 1 = not at all, 2 = a little,"
    " 3 = somewhat, 4 = mostly, 5 = very much.\n\nStatement: {item}\n\n"
    "Reply with only the digit."
)
"""Anti-demand-characteristics English prompt (M9-eval ME-13).

The forbidden keywords for self-test detection are encoded in
:data:`FORBIDDEN_KEYWORDS`; the unit test asserts the rendered prompt
contains none of them.
"""

FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    "personality test",
    "personality assessment",
    "big five",
    "big-five",
    "ipip",
    "questionnaire",
    "survey",
    "psychological",
    "psychometric",
)
"""Words/phrases the prompt must not contain (HIGH-4 anti-demand-characteristics).

Asserted by ``test_administer_ipip_50_no_personality_keywords_in_prompt``.
"""


@dataclass(frozen=True, slots=True)
class IPIPItem:
    """One IPIP-50 item.

    ``sign = +1`` for forward-keyed items (high Likert → high dimension);
    ``sign = -1`` for reverse-keyed items (high Likert → low dimension).
    """

    statement: str
    dimension: str  # "E" | "A" | "C" | "N" | "O"
    sign: int  # +1 forward, -1 reverse


@dataclass(frozen=True, slots=True)
class DecoyItem:
    """One decoy item (Codex P4a HIGH-4).

    Decoy items are presented in the same shuffled stream but excluded from
    Big5 scoring. Their Likert distribution feeds the ``decoy_consistency``
    diagnostic so an obviously biased responder (always 3, always 1) is
    surfaced.
    """

    statement: str


@dataclass(frozen=True, slots=True)
class Big5Scores:
    """Per-administration Big5 vector, dimensions in [1, 5] after reverse-keying."""

    extraversion: float
    agreeableness: float
    conscientiousness: float
    neuroticism: float
    openness: float
    n_items: int  # 50 for IPIP-50 (mini-ipip-20 deferred per ME-12)
    version: str  # "ipip-50"


@dataclass(frozen=True, slots=True)
class IPIPDiagnostic:
    """Quality-control side-channel — never used as Big5 itself.

    ME-1 specifies acquiescence / straight-line / reverse-keyed; HIGH-4
    adds ``decoy_consistency`` so a uniformly-biased responder is detected
    even if the diagnostics above pass.
    """

    acquiescence_index: float  # mean Likert centred at 3, abs avg deviation
    straight_line_runs: int  # max consecutive identical answers in shuffled order
    reverse_keyed_agreement: float  # corr between forward+reverse pairs (per dim)
    decoy_consistency: float  # |mean(decoy) - 3| / 2, in [0, 1]; high = biased


# ---------------------------------------------------------------------------
# IPIP-50 item corpus (vendored verbatim, public domain, English only)
# Source: https://ipip.ori.org/newBigFive5broadKey.htm
# ---------------------------------------------------------------------------

_IPIP_50_EN: tuple[IPIPItem, ...] = (
    # ===== Extraversion =====
    IPIPItem("Am the life of the party.", "E", +1),
    IPIPItem("Don't talk a lot.", "E", -1),
    IPIPItem("Feel comfortable around people.", "E", +1),
    IPIPItem("Keep in the background.", "E", -1),
    IPIPItem("Start conversations.", "E", +1),
    IPIPItem("Have little to say.", "E", -1),
    IPIPItem("Talk to a lot of different people at parties.", "E", +1),
    IPIPItem("Don't like to draw attention to myself.", "E", -1),
    IPIPItem("Don't mind being the center of attention.", "E", +1),
    IPIPItem("Am quiet around strangers.", "E", -1),
    # ===== Agreeableness =====
    IPIPItem("Feel little concern for others.", "A", -1),
    IPIPItem("Am interested in people.", "A", +1),
    IPIPItem("Insult people.", "A", -1),
    IPIPItem("Sympathize with others' feelings.", "A", +1),
    IPIPItem("Am not interested in other people's problems.", "A", -1),
    IPIPItem("Have a soft heart.", "A", +1),
    IPIPItem("Am not really interested in others.", "A", -1),
    IPIPItem("Take time out for others.", "A", +1),
    IPIPItem("Feel others' emotions.", "A", +1),
    IPIPItem("Make people feel at ease.", "A", +1),
    # ===== Conscientiousness =====
    IPIPItem("Am always prepared.", "C", +1),
    IPIPItem("Leave my belongings around.", "C", -1),
    IPIPItem("Pay attention to details.", "C", +1),
    IPIPItem("Make a mess of things.", "C", -1),
    IPIPItem("Get chores done right away.", "C", +1),
    IPIPItem("Often forget to put things back in their proper place.", "C", -1),
    IPIPItem("Like order.", "C", +1),
    IPIPItem("Shirk my duties.", "C", -1),
    IPIPItem("Follow a schedule.", "C", +1),
    IPIPItem("Am exacting in my work.", "C", +1),
    # ===== Neuroticism =====
    IPIPItem("Get stressed out easily.", "N", +1),
    IPIPItem("Am relaxed most of the time.", "N", -1),
    IPIPItem("Worry about things.", "N", +1),
    IPIPItem("Seldom feel blue.", "N", -1),
    IPIPItem("Am easily disturbed.", "N", +1),
    IPIPItem("Get upset easily.", "N", +1),
    IPIPItem("Change my mood a lot.", "N", +1),
    IPIPItem("Have frequent mood swings.", "N", +1),
    IPIPItem("Get irritated easily.", "N", +1),
    IPIPItem("Often feel blue.", "N", +1),
    # ===== Openness/Intellect =====
    IPIPItem("Have a rich vocabulary.", "O", +1),
    IPIPItem("Have difficulty understanding abstract ideas.", "O", -1),
    IPIPItem("Have a vivid imagination.", "O", +1),
    IPIPItem("Am not interested in abstract ideas.", "O", -1),
    IPIPItem("Have excellent ideas.", "O", +1),
    IPIPItem("Do not have a good imagination.", "O", -1),
    IPIPItem("Am quick to understand things.", "O", +1),
    IPIPItem("Use difficult words.", "O", +1),
    IPIPItem("Spend time reflecting on things.", "O", +1),
    IPIPItem("Am full of ideas.", "O", +1),
)

_DECOYS_EN: tuple[DecoyItem, ...] = (
    DecoyItem("Prefer hot weather to cold weather."),
    DecoyItem("Drink coffee in the morning."),
    DecoyItem("Live in a city of more than one million people."),
    DecoyItem("Have travelled outside my home country in the past year."),
    DecoyItem("Own at least one pet."),
)

_DIMENSIONS: tuple[str, ...] = ("E", "A", "C", "N", "O")


def get_ipip_50_items(language: str = "en") -> tuple[IPIPItem, ...]:
    """Return the IPIP-50 item corpus for the requested language.

    ``language="en"`` returns the public-domain Goldberg 1992 IPIP-50 items
    vendored above. ``language="ja"`` raises ``NotImplementedError`` —
    Japanese vendoring is deferred per M9-eval ME-12 (see
    ``blockers.md`` ``m9-eval-p4b-ja-ipip-vendoring``).
    """
    if language == "en":
        return _IPIP_50_EN
    if language == "ja":
        raise NotImplementedError(
            "Japanese IPIP-50 vendoring deferred — see blockers.md"
            " m9-eval-p4b-ja-ipip-vendoring (ME-12). Murakami 2002/2003 is"
            " not an IPIP-50 translation source; the official Nakayama/Karlin"
            " Japanese IPIP item corpus must be license-audited and vendored"
            " before language='ja' is admitted.",
        )
    raise ValueError(f"unsupported language {language!r} (expected 'en')")


def get_default_decoys(language: str = "en") -> tuple[DecoyItem, ...]:
    """Return the decoy items for the requested language."""
    if language == "en":
        return _DECOYS_EN
    if language == "ja":
        raise NotImplementedError(
            "Japanese decoy vendoring deferred (ME-12)",
        )
    raise ValueError(f"unsupported language {language!r}")


def render_item_prompt(item: IPIPItem | DecoyItem, *, language: str = "en") -> str:
    """Render the anti-demand-characteristics prompt for one item.

    The rendered string must not contain any of :data:`FORBIDDEN_KEYWORDS`
    (asserted in test). The same template is used for IPIP and decoy items
    so the responder cannot distinguish them by prompt shape.
    """
    if language != "en":
        raise NotImplementedError(
            f"language={language!r} prompt rendering deferred (ME-12)",
        )
    return PROMPT_TEMPLATE_EN.format(item=item.statement)


def administer_ipip_neo(
    responder: PersonaResponder,
    *,
    version: str = "ipip-50",
    language: str = "en",
    seed: int = 0,
    include_decoys: bool = True,
    decoy_count: int = DEFAULT_DECOY_COUNT,
) -> tuple[Big5Scores, IPIPDiagnostic]:

exec
/bin/zsh -lc "sed -n '1,260p' src/erre_sandbox/evidence/tier_b/vendi.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,260p' src/erre_sandbox/evidence/tier_b/big5_icc.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""Vendi Score (Friedman & Dieng 2023) — Tier B diversity metric.

The Vendi Score is the exponential of the Shannon entropy of the eigenvalue
spectrum of a positive semi-definite similarity kernel ``K`` with ``K_ii = 1``,
applied to ``K / N``. Identical items collapse to score 1; an identity kernel
with ``N`` items yields score ``N``.

DB9 sub-metric: ``vendi_score``. Persona-conditional: bootstrap CI per persona
across 25 windows (5 runs × 5 per-100-turn windows). Use with
:func:`erre_sandbox.evidence.bootstrap_ci.hierarchical_bootstrap_ci`
``cluster_only=True`` (M9-eval ME-14).

LIWC alternative honest framing (M9-B DB10 Option D): IPIP self-report only —
no LIWC equivalence claim, no external-lexicon Big5 inference. Tier A
``empath_proxy`` is a separate psycholinguistic axis (ME-1 / DB10 Option D).

ME-10 (Codex P4a HIGH-1) keeps the default kernel as ``"semantic"`` (MPNet,
the same encoder Tier A novelty uses). ``vendi_kernel_sensitivity_panel``
exposes the preregistered weight grid for the P4b sensitivity test on golden
baseline data; the production gate consumes the default kernel only until
that empirical comparison lands.

ME-15 metadata: emit ``window_index`` / ``window_start_turn`` /
``window_end_turn`` / ``window_size`` / ``metric_schema_version`` / ``kernel_name``
in the sidecar ``notes`` JSON when persisting to ``metrics.tier_b``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

VendiKernel = Callable[[Sequence[str]], np.ndarray]
"""Stub-friendly callable: utterances -> ``N × N`` similarity matrix.

The matrix must be symmetric, positive semi-definite, with diagonal entries
``1.0``. Off-diagonal entries are similarity scores in ``[0, 1]`` (cosine for
the semantic kernel, Jaccard for the lexical kernel). Tests pass deterministic
stubs so the heavy MPNet load never fires under unit tests.
"""

DEFAULT_KERNEL_NAME: str = "semantic"
"""Default kernel identifier surfaced in :class:`VendiResult` and notes JSON."""

_EIGENVALUE_FLOOR: float = 1e-12
"""Eigenvalues below this floor are treated as zero in the entropy sum.

Numerical noise from ``eigvalsh`` on a near-rank-deficient kernel can produce
small negative or sub-floor positive eigenvalues; clamping avoids ``log(0)``
without changing the entropy meaningfully (the contribution of a sub-floor
eigenvalue is below numpy's float resolution anyway).
"""


@dataclass(frozen=True, slots=True)
class VendiResult:
    """Vendi Score for a single window.

    ``score = N`` only when the normalized kernel equals the identity matrix
    (M9-eval ME-10). ``score = 1`` when every item is identical. Other values
    fall in ``[1, N]`` for PSD kernels with ``K_ii = 1``.
    """

    score: float
    n: int
    kernel_name: str
    semantic_weight: float
    lexical_weight: float
    spectrum_entropy: float


def _vendi_score_from_kernel(kernel_matrix: np.ndarray) -> tuple[float, float]:
    """Return ``(score, entropy)`` for an ``N × N`` PSD kernel with diag=1.

    Pulled out so the unit tests can exercise the math without going through
    the encoder boundary. The kernel must already be symmetric; ``eigvalsh``
    raises ``LinAlgError`` if asymmetry leaks past the input validation.
    """
    n = kernel_matrix.shape[0]
    if n == 0:
        return 0.0, 0.0
    normalized = kernel_matrix / float(n)
    eigvals = np.linalg.eigvalsh(normalized)
    safe = eigvals[eigvals > _EIGENVALUE_FLOOR]
    if safe.size == 0:
        return 1.0, 0.0
    entropy = float(-np.sum(safe * np.log(safe)))
    return float(np.exp(entropy)), entropy


def _check_kernel(matrix: np.ndarray, n: int) -> None:
    """Validate kernel shape, diagonal, and symmetry within float tolerance."""
    if matrix.shape != (n, n):
        raise ValueError(
            f"kernel matrix shape {matrix.shape} != ({n}, {n})",
        )
    if not np.allclose(np.diag(matrix), 1.0, atol=1e-6):
        raise ValueError("kernel diagonal must equal 1.0 (Vendi assumption)")
    if not np.allclose(matrix, matrix.T, atol=1e-6):
        raise ValueError("kernel must be symmetric")


def compute_vendi(
    utterances: Sequence[str],
    *,
    kernel: VendiKernel | None = None,
    kernel_name: str = DEFAULT_KERNEL_NAME,
    semantic_weight: float = 1.0,
    lexical_weight: float = 0.0,
) -> VendiResult:
    """Compute Vendi Score for a window of utterances.

    Args:
        utterances: One window — typically the 100 turns of a per-100-turn
            window. Order is preserved.
        kernel: Optional stub callable (``utterances -> N × N`` similarity).
            ``None`` lazy-loads the default semantic kernel (MPNet cosine,
            same encoder Tier A novelty uses).
        kernel_name: Identifier surfaced in :class:`VendiResult` and notes
            JSON. Use ``"semantic"`` / ``"lexical-5gram"`` /
            ``"hybrid-{semantic_weight}-{lexical_weight}"`` for production
            kernels, ``"identity"`` only inside tests.
        semantic_weight: Weight on the semantic component for ``hybrid-*``
            kernel identifiers; ``1.0`` for ``"semantic"``.
        lexical_weight: Weight on the lexical component for ``hybrid-*``;
            ``0.0`` for ``"semantic"``.

    Returns:
        :class:`VendiResult` with ``score``, ``n``, kernel metadata, and the
        underlying spectrum entropy. Empty input returns ``score=0.0, n=0``.

    Raises:
        ValueError: On inconsistent kernel shape, non-unit diagonal, or
            non-symmetric kernel matrix.
    """
    items = list(utterances)
    n = len(items)
    if n == 0:
        return VendiResult(
            score=0.0,
            n=0,
            kernel_name=kernel_name,
            semantic_weight=semantic_weight,
            lexical_weight=lexical_weight,
            spectrum_entropy=0.0,
        )

    fn = kernel if kernel is not None else _load_default_kernel()
    matrix = np.asarray(fn(items), dtype=float)
    _check_kernel(matrix, n)

    score, entropy = _vendi_score_from_kernel(matrix)
    return VendiResult(
        score=score,
        n=n,
        kernel_name=kernel_name,
        semantic_weight=semantic_weight,
        lexical_weight=lexical_weight,
        spectrum_entropy=entropy,
    )


def vendi_kernel_sensitivity_panel(
    utterances: Sequence[str],
    *,
    semantic_kernel: VendiKernel,
    lexical_kernel: VendiKernel,
    weights: Sequence[tuple[float, float]] = (
        (1.0, 0.0),
        (0.0, 1.0),
        (0.5, 0.5),
        (0.7, 0.3),
        (0.9, 0.1),
    ),
) -> list[VendiResult]:
    """Preregistered Vendi kernel sensitivity panel (M9-eval ME-10).

    Computes Vendi Score for the same window under each ``(semantic_weight,
    lexical_weight)`` combination so the P4b empirical comparison can rank
    kernels by persona-discriminative power on golden baseline data.

    The default ``weights`` grid is the preregistered set in ME-10:
    ``semantic-only`` / ``lexical-only`` / ``hybrid-0.5-0.5`` /
    ``hybrid-0.7-0.3`` / ``hybrid-0.9-0.1``.

    Args:
        utterances: One window of turn texts.
        semantic_kernel: Callable returning the semantic similarity matrix
            (cosine over MPNet embeddings in production).
        lexical_kernel: Callable returning the lexical similarity matrix
            (5-gram Jaccard in production; tests pass a deterministic stub).
        weights: Iterable of ``(semantic_weight, lexical_weight)`` pairs.
            Each pair must sum to a positive number; weights are applied to
            the matching kernel matrix and combined linearly.

    Returns:
        One :class:`VendiResult` per ``weights`` entry, in the same order.
    """
    items = list(utterances)
    n = len(items)
    if n == 0:
        return [
            VendiResult(
                score=0.0,
                n=0,
                kernel_name=_kernel_name_for(w_s, w_l),
                semantic_weight=w_s,
                lexical_weight=w_l,
                spectrum_entropy=0.0,
            )
            for w_s, w_l in weights
        ]

    semantic_matrix = np.asarray(semantic_kernel(items), dtype=float)
    lexical_matrix = np.asarray(lexical_kernel(items), dtype=float)
    _check_kernel(semantic_matrix, n)
    _check_kernel(lexical_matrix, n)

    results: list[VendiResult] = []
    for w_s, w_l in weights:
        if w_s + w_l <= 0:
            raise ValueError(
                f"weight sum must be positive (got {w_s} + {w_l})",
            )
        # Normalize so the combined matrix still has diagonal 1; both inputs
        # already have diagonal 1, so the convex sum preserves that.
        total = w_s + w_l
        combined = (w_s / total) * semantic_matrix + (w_l / total) * lexical_matrix
        score, entropy = _vendi_score_from_kernel(combined)
        results.append(
            VendiResult(
                score=score,
                n=n,
                kernel_name=_kernel_name_for(w_s, w_l),
                semantic_weight=w_s / total,
                lexical_weight=w_l / total,
                spectrum_entropy=entropy,
            ),
        )
    return results


def _kernel_name_for(semantic_weight: float, lexical_weight: float) -> str:
    """Return the kernel identifier for a ``(semantic, lexical)`` weight pair."""
    if math.isclose(lexical_weight, 0.0):
        return "semantic"
    if math.isclose(semantic_weight, 0.0):
        return "lexical-5gram"
    return f"hybrid-{semantic_weight:.1f}-{lexical_weight:.1f}"


def make_lexical_5gram_kernel() -> VendiKernel:
    """Return a deterministic lexical 5-gram Jaccard kernel.

    The kernel hashes character 5-grams of each utterance into sets and
    computes pairwise Jaccard similarity. Empty utterances collapse to a

 succeeded in 0ms:
"""Big5 stability ICC across runs/windows for Tier B DB9 quorum.

The intra-class correlation coefficient (ICC) over per-window Big5 score
vectors quantifies how stable the IPIP-50 self-report is across the 25
clusters of a typical run (5 runs × 5 per-100-turn windows).

DB9 sub-metric: ``big5_stability_icc``. Two consumers, two ICC variants
(M9-eval ME-11, Codex P4a HIGH-2):

* **ME-1 reliability fallback trigger**: ``ICC(C,k)`` consistency average
  is the primary value the trigger reads. Threshold ``point < 0.6 OR
  lower CI < 0.5`` in ≥2/3 personas fires the fallback (ME-1).
* **DB9 drift / adoption gate**: ``ICC(A,1)`` absolute agreement single
  rater is the primary value the gate reads. Level-shift sensitivity is
  intentional: a systematic Big5 offset is drift even if the rank order
  is preserved. ME-1 thresholds are *not* reused for ICC(A,1) — DB9
  cutoffs are calibrated separately on golden baseline data (P4b).

Notation: McGraw & Wong (1996). ``ICC(C,*)`` = consistency,
``ICC(A,*)`` = absolute agreement; ``*=1`` single rater, ``*=k`` k-rater
average. Mapping to Shrout & Fleiss (1979): ``ICC(2,k)`` ≈ ``ICC(C,k)``
or ``ICC(A,k)`` depending on whether absolute agreement was assumed.

Degenerate handling (Codex P4a MEDIUM-5): identical-all-constant response
matrices push BMS=0 and EMS=0 in the ANOVA decomposition. The function
returns ``icc_*=1.0, degenerate=True, me1_fallback_fire=False`` as an
explicit special case rather than an assumed limit. The
``test_compute_big5_icc_identical_windows_degenerate_returns_one`` test
pins this contract.

LIWC alternative honest framing (M9-B DB10 Option D): IPIP self-report
only — no LIWC equivalence claim, no external-lexicon Big5 inference.
Tier A ``empath_proxy`` is a separate psycholinguistic axis (ME-1 / DB10
Option D).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from erre_sandbox.evidence.bootstrap_ci import (
    DEFAULT_CI,
    DEFAULT_N_RESAMPLES,
    BootstrapResult,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence

    from erre_sandbox.evidence.tier_b.ipip_neo import Big5Scores

ME1_FALLBACK_POINT_THRESHOLD: float = 0.6
"""ICC(C,k) point estimate threshold for ME-1 fallback fire (M9-eval ME-1)."""

ME1_FALLBACK_LOWER_CI_THRESHOLD: float = 0.5
"""ICC(C,k) 95% lower CI threshold for ME-1 fallback fire (M9-eval ME-1)."""

_DIMENSION_ORDER: tuple[str, ...] = ("E", "A", "C", "N", "O")
"""Big5 dimension order. Maps :class:`Big5Scores` fields to matrix rows."""

_FORMULA_NOTATION: str = "McGraw-Wong 1996"


@dataclass(frozen=True, slots=True)
class Big5ICCResult:
    """Big5 stability ICC across windows.

    Two consumers (ME-11):

    * ME-1 (reliability fallback trigger) reads ``icc_consistency_average``
      and ``icc_consistency_lower_ci``; ``me1_fallback_fire`` summarises the
      0.6/0.5 threshold check.
    * DB9 (drift/adoption gate) reads ``icc_agreement_single`` and its CI.
      DB9 thresholds are *not* the ME-1 thresholds — see ME-11.

    ``degenerate`` is ``True`` for the all-identical-response special case
    (BMS=EMS=0 in the ANOVA); the ICC values are then deterministically
    set to 1.0 and the bootstrap intervals collapse to the same value.
    """

    # ME-1 consumer (reliability)
    icc_consistency_average: float
    icc_consistency_single: float
    icc_consistency_lower_ci: float
    icc_consistency_upper_ci: float
    me1_fallback_fire: bool

    # DB9 consumer (drift gate)
    icc_agreement_single: float
    icc_agreement_average: float
    icc_agreement_lower_ci: float
    icc_agreement_upper_ci: float

    # Diagnostic
    n_clusters: int  # number of Big5Scores windows fed in
    n_dimensions: int  # 5 (E/A/C/N/O)
    degenerate: bool
    formula_notation: str  # "McGraw-Wong 1996"


@dataclass(frozen=True, slots=True)
class TierBBootstrapPair:
    """Primary CI (cluster_only) + diagnostic CI (auto_block) pair.

    Per ME-14 (Codex P4a MEDIUM-1) the DB9 quorum code reads ``primary``
    only. ``diagnostic_auto_block`` is surfaced for variance-underestimation
    cross-checking and is not consumed by the gate. Pooled-persona CIs are
    forbidden unless an explicit ``is_exploratory`` flag is set elsewhere.
    """

    primary: BootstrapResult  # method="hierarchical-cluster-only"
    diagnostic_auto_block: BootstrapResult | None  # method="hierarchical-block"
    persona_id: str
    metric_name: str
    ess_disclosure: int  # cluster count, 25 typical (5 run × 5 window)


def _big5_matrix(big5_per_window: Sequence[Big5Scores]) -> np.ndarray:
    """Return ``(n_dimensions=5, n_windows)`` matrix of Big5 scores.

    Rows are dimensions in :data:`_DIMENSION_ORDER`, columns are windows in
    the input order. Used as the rating matrix for ICC computation.
    """
    n_windows = len(big5_per_window)
    matrix = np.empty((len(_DIMENSION_ORDER), n_windows), dtype=float)
    for j, scores in enumerate(big5_per_window):
        matrix[0, j] = scores.extraversion
        matrix[1, j] = scores.agreeableness
        matrix[2, j] = scores.conscientiousness
        matrix[3, j] = scores.neuroticism
        matrix[4, j] = scores.openness
    return matrix


def _icc_two_way_random(
    matrix: np.ndarray,
) -> tuple[float, float, float, float, bool]:
    """Compute ICC(C,1), ICC(C,k), ICC(A,1), ICC(A,k) and degenerate flag.

    Two-way random effects ANOVA (McGraw-Wong 1996 Table 4 cells for ICC2
    and ICC2k). ``matrix`` shape is ``(n_subjects, n_raters)``.

    Returns ``(icc_C1, icc_Ck, icc_A1, icc_Ak, degenerate)``. ``degenerate``
    is ``True`` when the ANOVA decomposition returns 0/0 (identical row or
    near-zero variance everywhere); ICC values are then 1.0.
    """
    n_subjects, n_raters = matrix.shape
    if n_subjects < 2 or n_raters < 2:  # noqa: PLR2004 — ICC needs ≥2 in each dim
        return 1.0, 1.0, 1.0, 1.0, True

    grand_mean = float(matrix.mean())
    subject_means = matrix.mean(axis=1)
    rater_means = matrix.mean(axis=0)

    # Sum-of-squares decomposition.
    ss_between_subjects = float(
        n_raters * np.sum((subject_means - grand_mean) ** 2),
    )
    ss_between_raters = float(
        n_subjects * np.sum((rater_means - grand_mean) ** 2),
    )
    ss_total = float(np.sum((matrix - grand_mean) ** 2))
    ss_residual = ss_total - ss_between_subjects - ss_between_raters

    df_subjects = n_subjects - 1
    df_raters = n_raters - 1
    df_residual = df_subjects * df_raters

    bms = ss_between_subjects / df_subjects if df_subjects > 0 else 0.0
    jms = ss_between_raters / df_raters if df_raters > 0 else 0.0
    ems = ss_residual / df_residual if df_residual > 0 else 0.0

    if math.isclose(bms, 0.0, abs_tol=1e-12) and math.isclose(
        ems,
        0.0,
        abs_tol=1e-12,
    ):
        return 1.0, 1.0, 1.0, 1.0, True

    icc_c1_denom = bms + (n_raters - 1) * ems
    icc_c1 = (bms - ems) / icc_c1_denom if icc_c1_denom > 0 else 0.0
    icc_ck = (bms - ems) / bms if bms > 0 else 0.0

    icc_a1_denom = bms + (n_raters - 1) * ems + n_raters * (jms - ems) / n_subjects
    icc_a1 = (bms - ems) / icc_a1_denom if icc_a1_denom > 0 else 0.0

    icc_ak_denom = bms + (jms - ems) / n_subjects
    icc_ak = (bms - ems) / icc_ak_denom if icc_ak_denom > 0 else 0.0

    return float(icc_c1), float(icc_ck), float(icc_a1), float(icc_ak), False


def _bootstrap_icc_cluster_only(
    matrix: np.ndarray,
    *,
    icc_index: int,
    seed: int,
    n_resamples: int,
    ci: float,
) -> tuple[float, float]:
    """Bootstrap CI for one of the four ICC variants.

    ``icc_index``: ``0=C1``, ``1=Ck``, ``2=A1``, ``3=Ak``. Resamples columns
    (raters/windows) with replacement; each column is a cluster in the
    cluster-only sense (M9-eval ME-14 / Codex P4a MEDIUM-1). Subjects are
    not resampled — the 5 Big5 dimensions are fixed by construction.
    """
    rng = np.random.default_rng(seed)
    n_raters = matrix.shape[1]
    replicate_iccs = np.empty(n_resamples, dtype=float)
    for r in range(n_resamples):
        cols = rng.integers(0, n_raters, size=n_raters)
        sampled = matrix[:, cols]
        replicate_iccs[r] = _icc_two_way_random(sampled)[icc_index]

    alpha = 1.0 - ci
    lo = float(np.quantile(replicate_iccs, alpha / 2.0))
    hi = float(np.quantile(replicate_iccs, 1.0 - alpha / 2.0))
    return lo, hi


def compute_big5_icc(
    big5_per_window: Sequence[Big5Scores],
    *,
    seed: int = 0,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    ci: float = DEFAULT_CI,
) -> Big5ICCResult:
    """Compute ICC(C,*) and ICC(A,*) over per-window Big5 scores.

    Args:
        big5_per_window: Sequence of :class:`Big5Scores`, one per window.
            Typically 25 entries (5 runs × 5 per-100-turn windows).
        seed: Deterministic bootstrap seed (M9-eval ME-5).
        n_resamples: Bootstrap iteration count.
        ci: Two-sided coverage in ``(0, 1)``.

    Returns:
        :class:`Big5ICCResult` with both consumers' values surfaced and
        ``me1_fallback_fire`` summarising the consistency-only threshold
        check (ME-1).

    Raises:
        ValueError: For empty input or fewer than 2 windows (ICC undefined).
    """
    n_windows = len(big5_per_window)
    if n_windows < 2:  # noqa: PLR2004 — ICC needs ≥2 raters
        raise ValueError(
            f"compute_big5_icc requires >=2 windows (got {n_windows})",
        )

    matrix = _big5_matrix(big5_per_window)
    icc_c1, icc_ck, icc_a1, icc_ak, degenerate = _icc_two_way_random(matrix)

    if degenerate:
        # Bootstrap collapses to the same value; surface 1.0 explicitly.

exec
/bin/zsh -lc "sed -n '1,260p' src/erre_sandbox/contracts/eval_paths.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '260,520p' src/erre_sandbox/evidence/tier_b/vendi.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '280,620p' src/erre_sandbox/evidence/eval_store.py" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '260,560p' src/erre_sandbox/evidence/tier_b/big5_icc.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
    computes pairwise Jaccard similarity. Empty utterances collapse to a
    single-element set so the diagonal stays at ``1.0``. Used as the lexical
    half of the sensitivity panel.
    """

    def kernel(items: Sequence[str]) -> np.ndarray:
        n = len(items)
        sets = [_char_5gram_set(text) for text in items]
        matrix = np.eye(n, dtype=float)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = sets[i], sets[j]
                if not a or not b:
                    sim = 0.0 if a != b else 1.0
                else:
                    sim = len(a & b) / len(a | b)
                matrix[i, j] = sim
                matrix[j, i] = sim
        return matrix

    return kernel


_NON_TOKEN = re.compile(r"\s+")


def _char_5gram_set(text: str) -> frozenset[str]:
    """Return the set of character 5-grams for a text (whitespace-collapsed)."""
    cleaned = _NON_TOKEN.sub(" ", text.strip())
    if len(cleaned) < 5:  # noqa: PLR2004 — 5-gram width is the documented cell
        return frozenset({cleaned}) if cleaned else frozenset()
    return frozenset(cleaned[i : i + 5] for i in range(len(cleaned) - 4))


def _load_default_kernel() -> VendiKernel:
    """Lazy-load the MPNet semantic cosine kernel.

    Heavy ``sentence-transformers`` import is deferred until the caller
    actually needs the real model — the eval extras gate keeps it out of base
    install resolution. The default model id is asserted by
    ``test_vendi_default_encoder_model_id_is_all_mpnet_base_v2``.
    """
    from sentence_transformers import (  # noqa: PLC0415  # heavy ML dep behind eval extras
        SentenceTransformer,
    )

    model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

    def kernel(items: Sequence[str]) -> np.ndarray:
        encoded = model.encode(list(items), show_progress_bar=False)
        matrix = np.asarray(encoded, dtype=float)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        safe = np.where(norms == 0, 1.0, norms)
        unit = matrix / safe
        cosine = unit @ unit.T
        # Numerical noise can push diagonal slightly above 1; clamp to keep
        # _check_kernel happy. Off-diagonal clamping to [0, 1] would mask real
        # negative similarity from contradictory text — leave that to the
        # caller to interpret.
        np.fill_diagonal(cosine, 1.0)
        return cosine

    return kernel


__all__ = [
    "DEFAULT_KERNEL_NAME",
    "VendiKernel",
    "VendiResult",
    "compute_vendi",
    "make_lexical_5gram_kernel",
    "vendi_kernel_sensitivity_panel",
]

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

INDIVIDUAL_LAYER_ENABLED_KEY: Final[str] = "individual_layer_enabled"
"""Single source of truth for the DB11 / M10-A individual-layer flag column name.

Exported so the training gate
(:func:`erre_sandbox.training.train_kant_lora.assert_phase_beta_ready`)
imports the same string the allow-list and the DDL lockstep check use,
keeping the m9-individual-layer-schema-add (B-1) contract on a single
canonical key. Changing the physical column name therefore requires
updating exactly one literal here.
"""

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
        INDIVIDUAL_LAYER_ENABLED_KEY,
        "created_at",
    },
)
"""Closed allow-list of column names permitted on a ``raw_dialog`` row.

Any key emitted by a training-egress path MUST be a member of this set.
``mode`` / ``zone`` / ``reasoning`` are reserved for the M9 ingest CLI
that copies sqlite ``dialog_turns`` into DuckDB ``raw_dialog``; the
existing M8 sink only populates a subset of these (see
``cli/export_log.py``), which is a strict subset and therefore safe.

:data:`INDIVIDUAL_LAYER_ENABLED_KEY` is the DB11 / M10-A individual-layer
activation flag; training-egress paths require it to be ``FALSE`` for
every row, enforced at three layers: (1) the DDL ``BOOLEAN NOT NULL
DEFAULT FALSE`` constraint in
:data:`erre_sandbox.evidence.eval_store._RAW_DIALOG_DDL_COLUMNS`,
(2) the construction-time aggregate assert inside
``_DuckDBRawTrainingRelation.__init__``, and (3) the row-level scan
inside :func:`erre_sandbox.training.train_kant_lora.assert_phase_beta_ready`.
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

 succeeded in 0ms:
        # Bootstrap collapses to the same value; surface 1.0 explicitly.
        cons_lo, cons_hi = 1.0, 1.0
        agr_lo, agr_hi = 1.0, 1.0
    else:
        cons_lo, cons_hi = _bootstrap_icc_cluster_only(
            matrix,
            icc_index=1,  # ICC(C,k)
            seed=seed,
            n_resamples=n_resamples,
            ci=ci,
        )
        agr_lo, agr_hi = _bootstrap_icc_cluster_only(
            matrix,
            icc_index=2,  # ICC(A,1)
            seed=seed,
            n_resamples=n_resamples,
            ci=ci,
        )

    me1_fallback_fire = not degenerate and (
        icc_ck < ME1_FALLBACK_POINT_THRESHOLD
        or cons_lo < ME1_FALLBACK_LOWER_CI_THRESHOLD
    )

    return Big5ICCResult(
        icc_consistency_average=icc_ck,
        icc_consistency_single=icc_c1,
        icc_consistency_lower_ci=cons_lo,
        icc_consistency_upper_ci=cons_hi,
        me1_fallback_fire=me1_fallback_fire,
        icc_agreement_single=icc_a1,
        icc_agreement_average=icc_ak,
        icc_agreement_lower_ci=agr_lo,
        icc_agreement_upper_ci=agr_hi,
        n_clusters=n_windows,
        n_dimensions=len(_DIMENSION_ORDER),
        degenerate=degenerate,
        formula_notation=_FORMULA_NOTATION,
    )


__all__ = [
    "ME1_FALLBACK_LOWER_CI_THRESHOLD",
    "ME1_FALLBACK_POINT_THRESHOLD",
    "Big5ICCResult",
    "TierBBootstrapPair",
    "compute_big5_icc",
]

 succeeded in 0ms:
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
# P4a — Tier B retrieval (M9-eval ME-15)
# ---------------------------------------------------------------------------

TIER_B_METRIC_SCHEMA_VERSION: str = "tier-b-v1"
"""Schema version embedded in Tier B sidecar ``notes`` JSON (ME-15).

Bumped when the notes JSON shape changes; consumers compare exact strings.
"""


@dataclass(frozen=True, slots=True)
class TierBMetricRow:
    """One row of ``metrics.tier_b`` decoded for analysis-side consumers.

    The physical column ``turn_idx`` is reused to carry the per-100-turn
    ``window_index`` (M9-eval ME-15 / Codex P4a MEDIUM-2). Helpers expose
    the field by its semantic name and parse the sidecar ``notes`` JSON so
    downstream code does not accidentally join a window aggregate to a raw
    turn.
    """

    window_index: int
    metric_value: float
    window_start_turn: int
    window_end_turn: int
    window_size: int
    metric_schema_version: str
    notes_raw: str | None  # untouched JSON for forward-compat fields


def _parse_tier_b_notes(notes: str | None) -> dict[str, object]:
    """Parse the Tier B sidecar JSON; missing fields default to zero / None.

    Tier B uses a fixed schema (ME-15) rather than free-form JSON to keep
    consumer code simple. The schema is small enough that an unconditional
    ``json.loads`` call is cheap; we still tolerate ``None`` / empty input
    for rows written before the schema was finalised.
    """
    if not notes:
        return {}
    try:
        parsed = json.loads(notes)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def fetch_tier_b_metric(
    view: AnalysisView,
    *,
    run_id: str,
    persona_id: str,
    metric_name: str,
) -> list[TierBMetricRow]:
    """Return Tier B rows for ``(run_id, persona_id, metric_name)``.

    Helper that centralises the ``turn_idx → window_index`` rename and the
    sidecar JSON parsing so downstream code (notebooks, dashboards, the
    eventual M9-C-adopt quorum logic) sees stable field names. ME-14
    requires the DB9 quorum code to read the *primary* CI only; this helper
    is the retrieval half — the per-window values feed into the cluster-only
    bootstrap before the quorum decision is made.

    Args:
        view: Read-only :class:`AnalysisView` (Mac-side, ME-2 protocol).
        run_id: Capture run identifier matching ``raw_dialog.run_id``.
        persona_id: Persona under evaluation.
        metric_name: One of the Tier B identifiers — e.g.
            ``"tier_b.vendi_score"`` / ``"tier_b.big5_stability_icc"``.

    Returns:
        List of :class:`TierBMetricRow`, ordered by ``window_index`` ascending.
    """
    select_sql = (
        f"SELECT turn_idx, metric_value, notes FROM {METRICS_SCHEMA}.tier_b"  # noqa: S608  # identifier is module-private constant
        " WHERE run_id = ? AND persona_id = ? AND metric_name = ?"
        " ORDER BY turn_idx"
    )
    rows = view.execute(select_sql, (run_id, persona_id, metric_name))
    decoded: list[TierBMetricRow] = []
    for row in rows:
        window_index_raw, metric_value_raw, notes_raw = row
        notes_str = notes_raw if isinstance(notes_raw, str) else None
        notes = _parse_tier_b_notes(notes_str)
        decoded.append(
            TierBMetricRow(
                window_index=_coerce_int(window_index_raw),
                metric_value=_coerce_float(metric_value_raw),
                window_start_turn=_coerce_int(notes.get("window_start_turn", 0)),
                window_end_turn=_coerce_int(notes.get("window_end_turn", 0)),
                window_size=_coerce_int(notes.get("window_size", 0)),
                metric_schema_version=_coerce_str(
                    notes.get("metric_schema_version", ""),
                ),
                notes_raw=notes_str,
            ),
        )
    return decoded


def _coerce_int(value: object) -> int:
    """Best-effort int coercion for DuckDB ``object`` row values."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, (str, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def _coerce_float(value: object) -> float:
    """Best-effort float coercion for DuckDB ``object`` row values."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _coerce_str(value: object) -> str:
    """Best-effort str coercion for notes JSON values."""
    if isinstance(value, str):
        return value
    return ""


def make_tier_b_notes(
    *,
    window_start_turn: int,
    window_end_turn: int,
    window_size: int,
    kernel_name: str | None = None,
    ipip_version: str | None = None,
    icc_formula: str | None = None,
) -> str:
    """Build the Tier B ``notes`` JSON with the fixed ME-15 schema.

    The same writer is used by Vendi, IPIP-NEO and Big5 ICC persisters so
    the JSON shape stays uniform across sub-metrics. Optional fields are
    included only when set; consumers tolerate their absence.
    """
    payload: dict[str, object] = {
        "window_start_turn": int(window_start_turn),
        "window_end_turn": int(window_end_turn),
        "window_size": int(window_size),
        "metric_schema_version": TIER_B_METRIC_SCHEMA_VERSION,
    }
    if kernel_name is not None:
        payload["kernel_name"] = kernel_name
    if ipip_version is not None:
        payload["ipip_version"] = ipip_version
    if icc_formula is not None:
        payload["icc_formula"] = icc_formula
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


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

web search: 
web search: 2025 Anthropic persona vectors monitoring and controlling character traits language models activation steering
web search: 
web search: Anthropic constitutional AI paper official 2024 constitutional classifiers representation engineering
web search: 
web search: Examining Identity Drift in Conversations of LLM Agents paper 2025 identity drift metric
web search: 
web search: Vendi Score paper Friedman Dieng 2023 diversity evaluation kernel text embedding
web search: 
web search: IPIP-NEO Japanese validation short form Big Five 2024 2025
web search: 
web search: https://www.anthropic.com/research/persona-vectors
web search: 
web search: https://cir.nii.ac.jp/crid/1390001205078139904?lang=ja
web search: 
web search: site:ipip.ori.org Japanese IPIP translation Nakayama Karlin
web search: 
web search: 
web search: 
web search: Generative Agents Interactive Simulacra Human Behavior persistent memory reflection paper 2023 2024 follow-up
web search: 
web search: sentence-transformers all-mpnet-base-v2 English model trained on 1B sentence pairs
web search: 
web search: https://huggingface.co/sentence-transformers/all-mpnet-base-v2
codex
The local check surfaced two concrete interface mismatches already: Tier B code lives under `evidence/tier_b`, not `eval/tier_b`, and the Phase 2 capture sidecars are audit metadata rather than metric input rows. I’m now folding that with the prior-art check before writing the verdict.
exec
/bin/zsh -lc "nl -ba .steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md | sed -n '1,240p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/eval_store.py | sed -n '1,240p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     1	# M10-0 Concrete Design Draft (Claude solo, pre-Codex)
     2	
     3	- **作成日**: 2026-05-11
     4	- **位置づけ**: `reasoning-model-judgment.md` を validation した上で、M10-0 (Pre-flight: individuation metrics + dataset manifest + cache benchmark + prompt ordering contract) を実装可能水準まで詰めた草案
     5	- **入力**:
     6	  - `reasoning-model-judgment.md` (Claude メモ、2026-05-11)
     7	  - `design-final.md` §3 M10-0 (PR #144 merged)
     8	  - `decisions.md` DA-1 / DA-8 / DA-10 / DA-12 (PR #144 merged)
     9	  - PR #145 DB11 ADR (training-view contamination prevention)
    10	  - P4a Tier B merged (`tier_b/` vendi / ipip_neo / big5_icc、PR #148)
    11	- **status**: Codex independent review (gpt-5.5 xhigh) 起動前の Claude solo 案。`/reimagine` 未適用。
    12	
    13	---
    14	
    15	## 1. memo 判定 (Claude solo)
    16	
    17	`reasoning-model-judgment.md` の判定は既存 ADR (DA-1〜DA-13、DB11、ME-9 metaphor) に対して内部矛盾なし。
    18	ただし 5 gap (G1 MEDIUM + G2-G5 MINOR) を識別:
    19	
    20	| # | severity | 内容 |
    21	|---|---|---|
    22	| G1 | MEDIUM | channel × metric の対応行列が欠落 (memo §6.2 で channel 列挙のみ) |
    23	| G2 | MINOR | P4a Tier B 資産 (Vendi / Big5 ICC) を未参照 |
    24	| G3 | MINOR | sidecar 永続化 layer 未指定 (DuckDB table vs JSON sidecar) |
    25	| G4 | MINOR | 閾値の preregister 場所が design-final.md §6 で defer のまま |
    26	| G5 | MINOR | `intervention_recovery_rate` の operationalization (perturbation protocol) 欠落 |
    27	
    28	---
    29	
    30	## 2. Concrete design
    31	
    32	### 2.1 タスク配置 (M9 完全終了後 scaffold)
    33	
    34	```
    35	.steering/[YYYYMMDD]-m10-0-individuation-metrics/
    36	  requirement.md
    37	  design.md
    38	  design-reimagine.md     (mandatory per CLAUDE.md)
    39	  codex-review-prompt.md
    40	  codex-review.md         (verbatim)
    41	  decisions.md            (ADR DA-IM-1〜)
    42	  tasklist.md
    43	```
    44	
    45	### 2.2 Channel × Metric matrix (G1 修復)
    46	
    47	| Metric | Input channel | What | Aggregation | Phase |
    48	|---|---|---|---|---|
    49	| `burrows_base_retention` | `raw_dialog.utterance` (mecab ja-tokenizer) | function-word freq vs base corpus | per-individual | M10-0 (既存拡張) |
    50	| `semantic_centroid_distance` | utterance embedding (sentence-transformer) | inter-individual style/content distance | pairwise same-base | M10-0 新規 |
    51	| `vendi_diversity` (P4a Tier B 流用) | utterance embedding kernel | within-base population diversity | population-level | M10-0 新規 |
    52	| `belief_variance` | `SemanticMemoryRecord.belief_kind` (promoted のみ) | cognitive content divergence | pairwise + class-wise | M10-0 新規 |
    53	| `world_model_overlap_jaccard` | `SubjectiveWorldModel.entries.key` per axis | SWM key overlap | pairwise × 5 axes | M10-0 (metric 関数のみ先行、active 計測は M10-A 以降) |
    54	| `big5_icc` (P4a Tier B 流用) | IPIP-NEO 応答 | personality stability across pop | ICC[2,1] within base | M10-0 新規 |
    55	| `intervention_recovery_rate` | post-perturbation utterance | base habit recovery / individual stickiness | dual (Burrows recovery + SWM persistence) | M10-0 protocol 定義のみ、実走 M11-C |
    56	| `narrative_drift` | NarrativeArc segments | trajectory divergence | pairwise edit distance | **M11-A 移送** (M10-0 では preregister のみ) |
    57	| `worldmodel_update_adoption_rate` | `LLMPlan.world_model_update_hint` | adoption / total | rate | **M10-C 移送** |
    58	
    59	### 2.3 永続化 layer (G3 修復)
    60	
    61	- **DuckDB additive 1 table**: `individuation_metrics(run_id, individual_id, base_persona_id, tick, metric_name, value, channel, computed_at)`
    62	  - 既存 `_audit_stimulus.json` capture pipeline と並走、DuckDB 側に集約 (M9-eval Phase 2 で確立した DuckDB sidecar 型を踏襲)
    63	- **`_audit_stimulus.json` additive key**: `individuation_metrics_summary` (per-run population-level の最終値のみ)
    64	- M9-eval CLI `--compute-individuation` flag (default off、M9-eval 既存 contract 不変、後方互換)
    65	
    66	### 2.4 Acceptance criteria (preregister)
    67	
    68	| ID | criterion | rationale |
    69	|---|---|---|
    70	| A1 | M9-eval baseline 5 cells で全 metric が valid float 返す (NaN / inf なし) | smoke |
    71	| A2 | mecab ja-tokenizer で kant Burrows が現行 char n-gram 値と ±0.05 以内で再現 | tokenizer 移行回帰防止 (Codex MEDIUM-5 反映) |
    72	| A3 | N=1 同 base で `semantic_centroid_distance` が degenerate (N≥2 で empirical 検定) | metric 健全性 (DB9 Tier B identity-kernel sanity と類似) |
    73	| A4 | M9-eval Phase 2 既存 capture を input に Vendi が動く (新 corpus 不要、P4a Tier B 流用) | 再利用検証 |
    74	| A5 | benchmark frame (cache hit rate / TTFT / prompt token delta) が baseline 値を出力 | M10-B 前提整備 (Codex HIGH-6) |
    75	| A6 | schema 変更ゼロ (PhilosopherBase / IndividualProfile 未着手) | DB11 整合 |
    76	| A7 | 既存 1356 tests PASS + 新 metric unit tests (≥ 15) PASS | 回帰防止 |
    77	| A8 | `--compute-individuation` flag off で既存 CLI 出力が byte-for-byte 不変 | additive 検証 |
    78	
    79	### 2.5 Threshold preregister 表 (G4 修復、M10-0 で固定する候補)
    80	
    81	| Threshold | Initial value | Justification source |
    82	|---|---|---|
    83	| Burrows base retention ≥ | 0.6 | design-final.md §5 M11-C |
    84	| pairwise centroid distance ≥ | TBD (M10-0 simulation で bootstrap) | 経験不在、bootstrap CI で設定 |
    85	| Vendi divergence (kernel = MPNet) ≥ | TBD (P4a Tier B sensitivity test 後) | PR #148 follow-up `vendi-kernel-sensitivity` 待ち |
    86	| `worldmodel_update_adoption_rate` band | [0.05, 0.40] | DA-12 |
    87	| `belief_variance > 0` | strict | design-final.md §5 |
    88	| `personality_drift_offset` bound | ±0.1 per axis | DA-12 (M11-C で multi-individual divergence 観測後再 calibration) |
    89	| `big5_icc` (within-base) | TBD (population 立ち上がり後 calibrate) | ICC[2,1] convention |
    90	| recovery_rate band | [0.4, 0.9] (predicted) | M11-C 後 calibrate |
    91	
    92	### 2.6 Intervention recovery protocol (G5 修復)
    93	
    94	```
    95	prep:
    96	  1. base individual を T_base = 200 tick 走らせ baseline Burrows / SWM snapshot 取得
    97	
    98	perturbation:
    99	  2. opposite-stance memory N = 5 entries を retrieved_memories に強制注入
   100	     (e.g. kant に対し "morality is contextual" 系の belief を inject)
   101	  3. T_perturb = 50 tick 走らせ perturbed_floor 計測
   102	
   103	recovery:
   104	  4. perturbation 除去後 T_recover = 200 tick 走らせ post recovery 計測
   105	
   106	metric:
   107	  recovery_rate    = (post_Burrows - perturbed_floor) / (baseline - perturbed_floor)
   108	  stickiness_rate  = SWM entry persistence ratio (perturbation 方向 entry が T_recover 終了時に survive している割合)
   109	```
   110	
   111	- protocol 定義のみ M10-0、実走 M11-C (multi-individual gate)
   112	- T_base / T_perturb / T_recover 数値は M11-B development_state machinery 立ち上がり後の simulation budget と整合させる必要 → M11-C 直前に再 calibration
   113	
   114	### 2.7 out-of-scope (明示)
   115	
   116	- `PhilosopherBase` / `IndividualProfile` schema 実装 → M10-A
   117	- prompt 注入 (Held world-model entries section) → M10-B
   118	- `WorldModelUpdateHint` の LLMPlan 拡張 → M10-C
   119	- `NarrativeArc` 蒸留 + coherence_score → M11-A
   120	- DevelopmentState transition machinery → M11-B
   121	- Multi-individual same-base validation → M11-C
   122	- Weight / activation 解析 / RL / preference tuning → M12+
   123	
   124	### 2.8 PR #127 (M9-B LoRA) への追記必要事項
   125	
   126	memo §2.2 / design-final.md §2.1 で既に DB11 として merged 済 (PR #145)。M10-0 着手時に **追加で** 必要な追記:
   127	
   128	- M9-eval `--compute-individuation` flag が training-view loader filter (`evaluation_epoch=false AND individual_layer_enabled=false`) を **bypass しない** こと
   129	- individuation metric の計算過程で生成される副作用 (DuckDB write 等) が training data manifest に流入しないこと
   130	- assert: M10-0 で生成される `individuation_metrics` table 行は training pipeline 入口で除外
   131	
   132	### 2.9 PR #148 P4a Tier B との接続
   133	
   134	- Vendi: `tier_b/vendi.py` を import、kernel は MPNet 既定 (sensitivity follow-up 待ち)
   135	- Big5 ICC: `tier_b/big5_icc.py` を import、ICC[2,1] (DB9 quorum offensive gate 用) を流用
   136	- 両者は M9-eval Phase 2 capture (`_audit_stimulus.json`) を input にできることを A4 で検証
   137	
   138	---
   139	
   140	## 3. M10-0 タスクの workpackage 分割案
   141	
   142	| WP | 内容 | LOC 想定 | depends |
   143	|---|---|---|---|
   144	| WP1 | `src/erre_sandbox/eval/individuation/` 新設 + metric 関数 8 個 (M10-0 phase のみ) | ~400 | P4a Tier B |
   145	| WP2 | DuckDB schema migration (`individuation_metrics` table 追加) | ~80 | WP1 |
   146	| WP3 | M9-eval CLI `--compute-individuation` flag + sidecar JSON key 追加 | ~120 | WP1, WP2 |
   147	| WP4 | mecab ja-tokenizer 移行 + Burrows 再現性 test | ~200 | (none) |
   148	| WP5 | Cache benchmark framework (cache hit rate / TTFT / prompt token counter) | ~150 | (none) |
   149	| WP6 | Prompt ordering contract spec (markdown 仕様、no code) | ~50 lines doc | (none) |
   150	| WP7 | Unit tests (≥ 15) + integration test against M9-eval Phase 2 baseline | ~400 | WP1-3 |
   151	| WP8 | Recovery protocol spec (markdown only、M11-C 実装は別 task) | ~80 lines doc | (none) |
   152	
   153	Total LOC 想定: ~1400 production + ~400 test = ~1800 (M9-eval CLI partial-fix +2857/-51 と同程度)。
   154	
   155	---
   156	
   157	## 4. リスク
   158	
   159	| Risk | severity | mitigation |
   160	|---|---|---|
   161	| mecab 移行で kant Burrows が大きく変動 → 既存 baseline 不整合 | HIGH | A2 acceptance に ±0.05 tolerance 設定、超過時は char n-gram と dual-track |
   162	| `semantic_centroid_distance` が embedding model 依存で reproducibility 低い | MEDIUM | model id pin + version capture を `individuation_metrics` 行に含める |
   163	| Big5 ICC が N=1 で degenerate → M10-0 では計算不能 | MEDIUM | A3 で明示 (skip + log)、M11-C で N=3 になってから active |
   164	| recovery protocol の T_base / T_perturb / T_recover が M11-C 実走前に不確定 | LOW | M10-0 で protocol 定義のみ、数値は M11-B 後 calibrate |
   165	| Vendi MPNet kernel が日本語性能不足 (follow-up `multilingual-vendi-encoder` 未着手) | MEDIUM | M10-0 phase では provisional、kernel sensitivity follow-up 完了後 re-calibrate |
   166	
   167	---
   168	
   169	## 5. Codex review で問いたい点
   170	
   171	1. memo §1 判定表の DEFER / ADOPT-WITH-CHANGES 配置は妥当か (特に "活性化・重み分析 = M12+" は科学的に防衛可能か、Hendrycks/Anthropic 系の representation steering 進展を踏まえて)
   172	2. channel × metric matrix (§2.2) で見落としている channel / metric は (e.g. reasoning_trace、cognitive habit recall rate)
   173	3. Big5 ICC 流用は ICC[2,1] consistency か absolute agreement かの選択は妥当か (P4a Tier B Codex 10th review ME-1 vs DB9 split を踏まえて)
   174	4. recovery protocol (§2.6) の perturbation injection 方式 (opposite-stance memory 強制) は ME-9 同型 false-positive リスクを内包しないか
   175	5. mecab ja-tokenizer 移行 (A2) を M10-0 timing で行うべきか、それとも M10-B/C 後の別 task にすべきか (依存最小化観点)
   176	6. WP 分割 (§3) のうち、empirical preregister の閾値が「TBD」のままで M10-0 close できる acceptance になっているが、これは「TBD のまま M10-0 を close + M11-C 直前に固定する」運用で問題ないか
   177	7. M10-0 と並行して進めることの allowed / forbidden 境界 (DB11 制約下、M9-B LoRA execution 中の sidecar metric 開発は許されるか)
   178	8. prior art: Generative Agents / CoALA / Voyager / Identity Drift / Agent Identity Evals / Persistent Personas の最新動向で本 sidecar design に組み込むべき手法は
   179	
   180	---
   181	
   182	## 6. References
   183	
   184	- `reasoning-model-judgment.md` (2026-05-11)
   185	- `design-final.md` §0-3, §5 (PR #144 merged)
   186	- `decisions.md` DA-1 / DA-8 / DA-10 / DA-12 (PR #144 merged)
   187	- `.steering/20260430-m9-b-lora-execution-plan/design-final.md` DB11 ADR Addendum 2026-05-08 (PR #145 merged)
   188	- `src/erre_sandbox/eval/tier_b/` (P4a Tier B、PR #148 merged)
   189	- `docs/architecture.md` §9 (計画中アーキテクチャ)

 succeeded in 0ms:
     1	"""DuckDB-backed evaluation store — m9-eval-system Phase 0 (P0b + P0c).
     2	
     3	This module is the **implementation half** of the four-layer evaluation
     4	contamination contract; the policy half lives in
     5	:mod:`erre_sandbox.contracts.eval_paths`. The single training-egress
     6	entry point is :func:`connect_training_view`, which opens a DuckDB file
     7	read-only and returns a :class:`RawTrainingRelation` that exposes only
     8	``raw_dialog`` rows — never the ``metrics`` schema, never an arbitrary
     9	SQL execution surface.
    10	
    11	P0c additions (this commit):
    12	
    13	* :func:`bootstrap_schema` — idempotent CREATE for ``raw_dialog.dialog``
    14	  and ``metrics.tier_{a,b,c}``. The raw column set is locked in lockstep
    15	  with :data:`ALLOWED_RAW_DIALOG_KEYS` (module-load-time check).
    16	* :class:`AnalysisView` + :func:`connect_analysis_view` — Mac-side
    17	  read-only multi-schema reader for analytics / notebooks. NOT a
    18	  training-egress route; the grep gate in CI keeps the metric schema
    19	  reference confined to this module.
    20	* :func:`export_raw_only_snapshot` — Parquet export of ``raw_dialog``
    21	  only, the sanctioned route for callers that need ad-hoc SQL on raw
    22	  rows (run the SQL against the snapshot, not the live file).
    23	* :func:`write_with_checkpoint` and :func:`atomic_temp_rename` — the
    24	  two ME-2 helpers that implement the G-GEAR → Mac snapshot semantics
    25	  documented in
    26	  ``.steering/20260430-m9-eval-system/decisions.md`` §ME-2.
    27	
    28	Both :func:`connect_training_view` and :func:`connect_analysis_view`
    29	open the underlying DuckDB file with ``read_only=True``. Any write
    30	attempt against either handle (even via private attribute access) must
    31	surface as a DuckDB error — the test suite covers both paths.
    32	"""
    33	
    34	from __future__ import annotations
    35	
    36	import contextlib
    37	import json
    38	from dataclasses import dataclass
    39	from pathlib import Path
    40	from typing import TYPE_CHECKING, Self
    41	
    42	import duckdb
    43	
    44	from erre_sandbox.contracts.eval_paths import (
    45	    ALLOWED_RAW_DIALOG_KEYS,
    46	    INDIVIDUAL_LAYER_ENABLED_KEY,
    47	    METRICS_SCHEMA,
    48	    RAW_DIALOG_SCHEMA,
    49	    EvaluationContaminationError,
    50	    RawTrainingRelation,
    51	    assert_no_metrics_leak,
    52	    assert_no_sentinel_leak,
    53	)
    54	
    55	if TYPE_CHECKING:  # pragma: no cover - typing only
    56	    from collections.abc import Iterator, Mapping
    57	
    58	RAW_DIALOG_TABLE: str = "dialog"
    59	"""Table name inside :data:`RAW_DIALOG_SCHEMA` (qualified
    60	``raw_dialog.dialog``).
    61	
    62	Kept as a public constant so :func:`bootstrap_schema` and the contract
    63	test agree on the same physical name.
    64	"""
    65	
    66	# ---------------------------------------------------------------------------
    67	# Bootstrap DDL — column set locked in lockstep with the contract.
    68	# ---------------------------------------------------------------------------
    69	
    70	_RAW_DIALOG_DDL_COLUMNS: tuple[tuple[str, str], ...] = (
    71	    ("id", "TEXT"),
    72	    ("run_id", "TEXT"),
    73	    ("dialog_id", "TEXT"),
    74	    ("tick", "INTEGER"),
    75	    ("turn_index", "INTEGER"),
    76	    ("speaker_agent_id", "TEXT"),
    77	    ("speaker_persona_id", "TEXT"),
    78	    ("addressee_agent_id", "TEXT"),
    79	    ("addressee_persona_id", "TEXT"),
    80	    ("utterance", "TEXT"),
    81	    ("mode", "TEXT"),
    82	    ("zone", "TEXT"),
    83	    ("reasoning", "TEXT"),
    84	    ("epoch_phase", "TEXT"),
    85	    # B-1 (m9-individual-layer-schema-add, Codex HIGH-1): NOT NULL +
    86	    # DEFAULT FALSE keeps the column bivalent and lets existing INSERTs
    87	    # that omit the new column still succeed with explicit false.
    88	    ("individual_layer_enabled", "BOOLEAN NOT NULL DEFAULT FALSE"),
    89	    ("created_at", "TIMESTAMP"),
    90	)
    91	
    92	_BOOTSTRAP_COLUMN_NAMES: frozenset[str] = frozenset(
    93	    name for name, _ in _RAW_DIALOG_DDL_COLUMNS
    94	)
    95	if _BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS:
    96	    # Fail-fast at import: divergence here would silently widen the
    97	    # contract, which is the exact failure mode the four-layer defence
    98	    # is meant to prevent.
    99	    raise EvaluationContaminationError(
   100	        "bootstrap DDL column set"
   101	        f" {sorted(_BOOTSTRAP_COLUMN_NAMES)} diverges from"
   102	        f" ALLOWED_RAW_DIALOG_KEYS {sorted(ALLOWED_RAW_DIALOG_KEYS)}"
   103	        " — update both in lockstep",
   104	    )
   105	
   106	_METRIC_TIERS: tuple[str, ...] = ("tier_a", "tier_b", "tier_c")
   107	
   108	_METRIC_TIER_COLUMNS: str = (
   109	    '"run_id" TEXT,'
   110	    ' "persona_id" TEXT,'
   111	    ' "turn_idx" INTEGER,'
   112	    ' "metric_name" TEXT,'
   113	    ' "metric_value" DOUBLE,'
   114	    ' "notes" TEXT'
   115	)
   116	"""Generic per-metric row shape used by all three tiers at P0c.
   117	
   118	Tier A is per-turn, Tier B is per-100-turn aggregate, Tier C is judge
   119	score; later phases may introduce tier-specific columns. The current
   120	shape is intentionally narrow so the contract surface stays tight.
   121	"""
   122	
   123	
   124	def _inspect_raw_dialog_columns(
   125	    conn: duckdb.DuckDBPyConnection,
   126	) -> list[str]:
   127	    """Return ordered column names of ``raw_dialog.dialog``.
   128	
   129	    Module-level helper used by both :class:`_DuckDBRawTrainingRelation`
   130	    construction and :func:`export_raw_only_snapshot`. Raises
   131	    :class:`EvaluationContaminationError` if the table is missing.
   132	    """
   133	    rows = conn.execute(
   134	        "SELECT column_name FROM information_schema.columns"
   135	        " WHERE table_schema = ? AND table_name = ?"
   136	        " ORDER BY ordinal_position",
   137	        (RAW_DIALOG_SCHEMA, RAW_DIALOG_TABLE),
   138	    ).fetchall()
   139	    if not rows:
   140	        raise EvaluationContaminationError(
   141	            f"{RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE} not found in DuckDB"
   142	            f" file; cannot construct training view (was the schema"
   143	            f" bootstrapped? — see bootstrap_schema)",
   144	        )
   145	    return [str(row[0]) for row in rows]
   146	
   147	
   148	class _DuckDBRawTrainingRelation:
   149	    """Concrete :class:`RawTrainingRelation` backed by a read-only DuckDB connection.
   150	
   151	    Designed as a **constrained facade**:
   152	
   153	    * The connection is held privately; no public attribute exposes it.
   154	    * Only a fixed SELECT against ``raw_dialog.dialog`` is ever issued.
   155	    * Column projection is the **intersection** of the physical columns
   156	      with :data:`ALLOWED_RAW_DIALOG_KEYS`; any column outside the
   157	      allow-list is dropped before the row reaches the caller, and a
   158	      mismatch between the physical schema and the allow-list raises
   159	      :class:`EvaluationContaminationError` at construction.
   160	    """
   161	
   162	    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
   163	        self._conn = conn
   164	        physical_columns = _inspect_raw_dialog_columns(conn)
   165	        outside_allowlist = [
   166	            col for col in physical_columns if col not in ALLOWED_RAW_DIALOG_KEYS
   167	        ]
   168	        if outside_allowlist:
   169	            raise EvaluationContaminationError(
   170	                f"raw_dialog.{RAW_DIALOG_TABLE} contains column(s)"
   171	                f" {sorted(outside_allowlist)!r} that are not on the"
   172	                f" raw_dialog allow-list"
   173	                f" ({sorted(ALLOWED_RAW_DIALOG_KEYS)})",
   174	            )
   175	        self._columns: tuple[str, ...] = tuple(physical_columns)
   176	        # Belt-and-braces: confirm we never aliased the metrics schema in.
   177	        if any(col.startswith(f"{METRICS_SCHEMA}.") for col in self._columns):
   178	            raise EvaluationContaminationError(
   179	                f"raw_dialog projection includes a {METRICS_SCHEMA}-qualified"
   180	                f" column: {self._columns!r}",
   181	            )
   182	
   183	        # Aggregate row-level contamination check (Codex HIGH-2 / DB11 /
   184	        # B-1): ``connect_training_view()`` is the loader boundary
   185	        # contracted by blockers.md §B-1, so we raise *before* any caller
   186	        # can reach ``iter_rows`` past a row that carries
   187	        # ``epoch_phase=evaluation`` or a truthy / NULL
   188	        # ``individual_layer_enabled``. SQL aggregate is used (not a
   189	        # ``WHERE`` filter) to avoid silently diluting the
   190	        # ``min_examples`` count check downstream in
   191	        # ``assert_phase_beta_ready``. The aggregate is skipped when
   192	        # either column is absent (legacy / pre-B-1 schemas) — those
   193	        # cases are still picked up by ``assert_phase_beta_ready``
   194	        # itself, so backwards compatibility at the loader is
   195	        # preserved.
   196	        column_set = frozenset(self._columns)
   197	        if "epoch_phase" in column_set and INDIVIDUAL_LAYER_ENABLED_KEY in column_set:
   198	            agg_row = self._conn.execute(
   199	                "SELECT"  # noqa: S608  # all interpolations are module-private constants
   200	                " COALESCE(SUM(CASE WHEN LOWER(epoch_phase) = 'evaluation'"
   201	                " THEN 1 ELSE 0 END), 0),"
   202	                f" COALESCE(SUM(CASE WHEN {INDIVIDUAL_LAYER_ENABLED_KEY}"
   203	                f" IS NOT FALSE THEN 1 ELSE 0 END), 0)"
   204	                f" FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}",
   205	            ).fetchone()
   206	            eval_count = int(agg_row[0]) if agg_row else 0
   207	            ind_count = int(agg_row[1]) if agg_row else 0
   208	            if eval_count > 0:
   209	                raise EvaluationContaminationError(
   210	                    f"raw_dialog.{RAW_DIALOG_TABLE}: {eval_count} row(s)"
   211	                    f" carry epoch_phase~='evaluation' (case-insensitive)"
   212	                    f" at construction time — rejecting at the loader"
   213	                    f" boundary (Codex HIGH-2 / DB11 / B-1)",
   214	                )
   215	            if ind_count > 0:
   216	                raise EvaluationContaminationError(
   217	                    f"raw_dialog.{RAW_DIALOG_TABLE}: {ind_count} row(s)"
   218	                    f" carry truthy or NULL {INDIVIDUAL_LAYER_ENABLED_KEY}"
   219	                    f" at construction time — rejecting at the loader"
   220	                    f" boundary (Codex HIGH-2 / DB11 / B-1)",
   221	                )
   222	
   223	    # ------------------------------------------------------------------
   224	    # Protocol surface
   225	    # ------------------------------------------------------------------
   226	
   227	    @property
   228	    def schema_name(self) -> str:
   229	        return RAW_DIALOG_SCHEMA
   230	
   231	    @property
   232	    def columns(self) -> tuple[str, ...]:
   233	        return self._columns
   234	
   235	    def row_count(self) -> int:
   236	        result = self._conn.execute(
   237	            f"SELECT COUNT(*) FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}",  # noqa: S608  # constants are module-private literals, no user input
   238	        ).fetchone()
   239	        if result is None:
   240	            return 0

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/tier_a/burrows.py | sed -n '1,240p'" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/tier_b/ipip_neo.py | sed -n '1,180p'" in /Users/johnd/ERRE-Sand Box
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

 succeeded in 0ms:
     1	"""IPIP-50 (Goldberg 1992) administering helper for Tier B Big5 ICC.
     2	
     3	The 50 items are vendored verbatim from the public-domain IPIP corpus
     4	(https://ipip.ori.org/, English official, public domain commercial use OK).
     5	Mini-IPIP-20 is intentionally not implemented because Mini-IPIP α 0.65-0.70
     6	sits on the ME-1 fallback boundary 0.6 (M9-eval ME-12); IPIP-50 broad-domain
     7	α ≈ 0.84 (https://ipip.ori.org/newBigFive5broadTable.htm).
     8	
     9	Anti-demand-characteristics design (Codex P4a HIGH-4 / M9-eval ME-13). LLMs
    10	infer personality-test context and shift toward socially desirable answers
    11	(Salecha et al. 2024, https://arxiv.org/abs/2405.06058); the prompt template
    12	therefore avoids "personality test", "Big Five", "IPIP", "questionnaire",
    13	"survey", and "psychological" wording. Items are presented one at a time in
    14	deterministically shuffled order, and decoy items dilute the test-taking
    15	context inference.
    16	
    17	Japanese administration is deferred (Codex P4a HIGH-3 / ME-12). The Murakami
    18	2002/2003 lexical Big Five papers are not an IPIP-50 translation source; the
    19	official IPIP translations page lists Nakayama/Karlin Japanese IPIP and a
    20	license-cleared 50-item subset is required before ``language="ja"`` can be
    21	admitted. Until then the helper raises ``NotImplementedError`` for ``ja``.
    22	
    23	LIWC alternative honest framing (M9-B DB10 Option D): IPIP self-report only —
    24	no LIWC equivalence claim, no external-lexicon Big5 inference. Tier A
    25	``empath_proxy`` is a separate psycholinguistic axis (ME-1 / DB10 Option D).
    26	"""
    27	
    28	from __future__ import annotations
    29	
    30	import hashlib
    31	from collections.abc import Callable, Sequence
    32	from dataclasses import dataclass
    33	
    34	PersonaResponder = Callable[[str], int]
    35	"""Stub-friendly callable: take an item prompt, return a 1..5 Likert integer.
    36	
    37	Tests pass a deterministic stub (e.g. constant 3, alternating 1/5) so the
    38	helper exercises scoring / shuffling / diagnostics without an LLM round-trip.
    39	"""
    40	
    41	DEFAULT_LIKERT_MIN: int = 1
    42	DEFAULT_LIKERT_MAX: int = 5
    43	"""5-point Likert administration (Codex P4a LOW-1 keep)."""
    44	
    45	DEFAULT_DECOY_COUNT: int = 5
    46	"""Decoy items count (Codex P4a HIGH-4)."""
    47	
    48	PROMPT_TEMPLATE_EN: str = (
    49	    "Read the statement and reply with one digit from 1 to 5 indicating how"
    50	    " well it describes you, where 1 = not at all, 2 = a little,"
    51	    " 3 = somewhat, 4 = mostly, 5 = very much.\n\nStatement: {item}\n\n"
    52	    "Reply with only the digit."
    53	)
    54	"""Anti-demand-characteristics English prompt (M9-eval ME-13).
    55	
    56	The forbidden keywords for self-test detection are encoded in
    57	:data:`FORBIDDEN_KEYWORDS`; the unit test asserts the rendered prompt
    58	contains none of them.
    59	"""
    60	
    61	FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    62	    "personality test",
    63	    "personality assessment",
    64	    "big five",
    65	    "big-five",
    66	    "ipip",
    67	    "questionnaire",
    68	    "survey",
    69	    "psychological",
    70	    "psychometric",
    71	)
    72	"""Words/phrases the prompt must not contain (HIGH-4 anti-demand-characteristics).
    73	
    74	Asserted by ``test_administer_ipip_50_no_personality_keywords_in_prompt``.
    75	"""
    76	
    77	
    78	@dataclass(frozen=True, slots=True)
    79	class IPIPItem:
    80	    """One IPIP-50 item.
    81	
    82	    ``sign = +1`` for forward-keyed items (high Likert → high dimension);
    83	    ``sign = -1`` for reverse-keyed items (high Likert → low dimension).
    84	    """
    85	
    86	    statement: str
    87	    dimension: str  # "E" | "A" | "C" | "N" | "O"
    88	    sign: int  # +1 forward, -1 reverse
    89	
    90	
    91	@dataclass(frozen=True, slots=True)
    92	class DecoyItem:
    93	    """One decoy item (Codex P4a HIGH-4).
    94	
    95	    Decoy items are presented in the same shuffled stream but excluded from
    96	    Big5 scoring. Their Likert distribution feeds the ``decoy_consistency``
    97	    diagnostic so an obviously biased responder (always 3, always 1) is
    98	    surfaced.
    99	    """
   100	
   101	    statement: str
   102	
   103	
   104	@dataclass(frozen=True, slots=True)
   105	class Big5Scores:
   106	    """Per-administration Big5 vector, dimensions in [1, 5] after reverse-keying."""
   107	
   108	    extraversion: float
   109	    agreeableness: float
   110	    conscientiousness: float
   111	    neuroticism: float
   112	    openness: float
   113	    n_items: int  # 50 for IPIP-50 (mini-ipip-20 deferred per ME-12)
   114	    version: str  # "ipip-50"
   115	
   116	
   117	@dataclass(frozen=True, slots=True)
   118	class IPIPDiagnostic:
   119	    """Quality-control side-channel — never used as Big5 itself.
   120	
   121	    ME-1 specifies acquiescence / straight-line / reverse-keyed; HIGH-4
   122	    adds ``decoy_consistency`` so a uniformly-biased responder is detected
   123	    even if the diagnostics above pass.
   124	    """
   125	
   126	    acquiescence_index: float  # mean Likert centred at 3, abs avg deviation
   127	    straight_line_runs: int  # max consecutive identical answers in shuffled order
   128	    reverse_keyed_agreement: float  # corr between forward+reverse pairs (per dim)
   129	    decoy_consistency: float  # |mean(decoy) - 3| / 2, in [0, 1]; high = biased
   130	
   131	
   132	# ---------------------------------------------------------------------------
   133	# IPIP-50 item corpus (vendored verbatim, public domain, English only)
   134	# Source: https://ipip.ori.org/newBigFive5broadKey.htm
   135	# ---------------------------------------------------------------------------
   136	
   137	_IPIP_50_EN: tuple[IPIPItem, ...] = (
   138	    # ===== Extraversion =====
   139	    IPIPItem("Am the life of the party.", "E", +1),
   140	    IPIPItem("Don't talk a lot.", "E", -1),
   141	    IPIPItem("Feel comfortable around people.", "E", +1),
   142	    IPIPItem("Keep in the background.", "E", -1),
   143	    IPIPItem("Start conversations.", "E", +1),
   144	    IPIPItem("Have little to say.", "E", -1),
   145	    IPIPItem("Talk to a lot of different people at parties.", "E", +1),
   146	    IPIPItem("Don't like to draw attention to myself.", "E", -1),
   147	    IPIPItem("Don't mind being the center of attention.", "E", +1),
   148	    IPIPItem("Am quiet around strangers.", "E", -1),
   149	    # ===== Agreeableness =====
   150	    IPIPItem("Feel little concern for others.", "A", -1),
   151	    IPIPItem("Am interested in people.", "A", +1),
   152	    IPIPItem("Insult people.", "A", -1),
   153	    IPIPItem("Sympathize with others' feelings.", "A", +1),
   154	    IPIPItem("Am not interested in other people's problems.", "A", -1),
   155	    IPIPItem("Have a soft heart.", "A", +1),
   156	    IPIPItem("Am not really interested in others.", "A", -1),
   157	    IPIPItem("Take time out for others.", "A", +1),
   158	    IPIPItem("Feel others' emotions.", "A", +1),
   159	    IPIPItem("Make people feel at ease.", "A", +1),
   160	    # ===== Conscientiousness =====
   161	    IPIPItem("Am always prepared.", "C", +1),
   162	    IPIPItem("Leave my belongings around.", "C", -1),
   163	    IPIPItem("Pay attention to details.", "C", +1),
   164	    IPIPItem("Make a mess of things.", "C", -1),
   165	    IPIPItem("Get chores done right away.", "C", +1),
   166	    IPIPItem("Often forget to put things back in their proper place.", "C", -1),
   167	    IPIPItem("Like order.", "C", +1),
   168	    IPIPItem("Shirk my duties.", "C", -1),
   169	    IPIPItem("Follow a schedule.", "C", +1),
   170	    IPIPItem("Am exacting in my work.", "C", +1),
   171	    # ===== Neuroticism =====
   172	    IPIPItem("Get stressed out easily.", "N", +1),
   173	    IPIPItem("Am relaxed most of the time.", "N", -1),
   174	    IPIPItem("Worry about things.", "N", +1),
   175	    IPIPItem("Seldom feel blue.", "N", -1),
   176	    IPIPItem("Am easily disturbed.", "N", +1),
   177	    IPIPItem("Get upset easily.", "N", +1),
   178	    IPIPItem("Change my mood a lot.", "N", +1),
   179	    IPIPItem("Have frequent mood swings.", "N", +1),
   180	    IPIPItem("Get irritated easily.", "N", +1),

exec
/bin/zsh -lc "nl -ba src/erre_sandbox/evidence/tier_b/ipip_neo.py | sed -n '198,250p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
   198	    DecoyItem("Live in a city of more than one million people."),
   199	    DecoyItem("Have travelled outside my home country in the past year."),
   200	    DecoyItem("Own at least one pet."),
   201	)
   202	
   203	_DIMENSIONS: tuple[str, ...] = ("E", "A", "C", "N", "O")
   204	
   205	
   206	def get_ipip_50_items(language: str = "en") -> tuple[IPIPItem, ...]:
   207	    """Return the IPIP-50 item corpus for the requested language.
   208	
   209	    ``language="en"`` returns the public-domain Goldberg 1992 IPIP-50 items
   210	    vendored above. ``language="ja"`` raises ``NotImplementedError`` —
   211	    Japanese vendoring is deferred per M9-eval ME-12 (see
   212	    ``blockers.md`` ``m9-eval-p4b-ja-ipip-vendoring``).
   213	    """
   214	    if language == "en":
   215	        return _IPIP_50_EN
   216	    if language == "ja":
   217	        raise NotImplementedError(
   218	            "Japanese IPIP-50 vendoring deferred — see blockers.md"
   219	            " m9-eval-p4b-ja-ipip-vendoring (ME-12). Murakami 2002/2003 is"
   220	            " not an IPIP-50 translation source; the official Nakayama/Karlin"
   221	            " Japanese IPIP item corpus must be license-audited and vendored"
   222	            " before language='ja' is admitted.",
   223	        )
   224	    raise ValueError(f"unsupported language {language!r} (expected 'en')")
   225	
   226	
   227	def get_default_decoys(language: str = "en") -> tuple[DecoyItem, ...]:
   228	    """Return the decoy items for the requested language."""
   229	    if language == "en":
   230	        return _DECOYS_EN
   231	    if language == "ja":
   232	        raise NotImplementedError(
   233	            "Japanese decoy vendoring deferred (ME-12)",
   234	        )
   235	    raise ValueError(f"unsupported language {language!r}")
   236	
   237	
   238	def render_item_prompt(item: IPIPItem | DecoyItem, *, language: str = "en") -> str:
   239	    """Render the anti-demand-characteristics prompt for one item.
   240	
   241	    The rendered string must not contain any of :data:`FORBIDDEN_KEYWORDS`
   242	    (asserted in test). The same template is used for IPIP and decoy items
   243	    so the responder cannot distinguish them by prompt shape.
   244	    """
   245	    if language != "en":
   246	        raise NotImplementedError(
   247	            f"language={language!r} prompt rendering deferred (ME-12)",
   248	        )
   249	    return PROMPT_TEMPLATE_EN.format(item=item.statement)
   250	

exec
/bin/zsh -lc "rg -n \"mecab|sudachi|fugashi|sentence-transformers|duckdb|scikit|numpy|torch|transformers\" pyproject.toml uv.lock | sed -n '1,220p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
pyproject.toml:35:    "numpy>=2,<3",
pyproject.toml:40:    # CI; heavy ML deps (sentence-transformers, scipy, ollama, empath, arch)
pyproject.toml:42:    "duckdb>=1.1,<2",
pyproject.toml:55:    "sentence-transformers>=3,<4",   # MPNet (novelty) + transformers pipeline (NLI)
pyproject.toml:73:# transformers / datasets / accelerate / bitsandbytes are imported lazily
pyproject.toml:77:    "transformers>=4.45,<5",
pyproject.toml:111:# transformers==5.3.0 pin which collides with both [training] (peft +
pyproject.toml:112:# transformers>=4.45,<5) and [eval] (sentence-transformers requires
pyproject.toml:113:# transformers<5). Operationally these stacks never co-reside on the
pyproject.toml:118:# can pin transformers per-extra without forcing a single global
pyproject.toml:230:module = ["transformers.*", "sentence_transformers.*", "empath.*", "ollama.*", "arch.*", "scipy.*"]
pyproject.toml:275:    "eval: requires the [eval] extras (sentence-transformers / transformers / empath); deselected by default",
pyproject.toml:277:    "training: requires the [training] extras (peft / transformers / accelerate / bitsandbytes / datasets); deselected by default — reserved for Phase K β real Kant training (B-1/B-2 解消後)",
uv.lock:26:    { name = "numpy" },
uv.lock:31:    { name = "torch", version = "2.11.0", source = { registry = "https://pypi.org/simple" } },
uv.lock:197:    { name = "numpy" },
uv.lock:251:    { name = "numpy" },
uv.lock:253:    { name = "torch", version = "2.11.0", source = { registry = "https://pypi.org/simple" } },
uv.lock:404:    { name = "torch", version = "2.9.1", source = { registry = "https://pypi.org/simple" } },
uv.lock:405:    { name = "transformers", version = "5.3.0", source = { registry = "https://pypi.org/simple" } },
uv.lock:532:    { name = "numpy" },
uv.lock:560:    { name = "numpy" },
uv.lock:605:name = "duckdb"
uv.lock:608:sdist = { url = "https://files.pythonhosted.org/packages/0c/66/744b4931b799a42f8cb9bc7a6f169e7b8e51195b62b246db407fd90bf15f/duckdb-1.5.2.tar.gz", hash = "sha256:638da0d5102b6cb6f7d47f83d0600708ac1d3cb46c5e9aaabc845f9ba4d69246", size = 18017166, upload-time = "2026-04-13T11:30:09.065Z" }
uv.lock:610:    { url = "https://files.pythonhosted.org/packages/9a/b0/d13e7e396d86c245290b3e93f692a2d27c2fe99f857aaf9205003c00c978/duckdb-1.5.2-cp311-cp311-macosx_10_9_universal2.whl", hash = "sha256:7f69164b048e498b9e9140a24343108a5ae5f17bfb3485185f55fdf9b1aa924d", size = 30020978, upload-time = "2026-04-13T11:28:52.486Z" },
uv.lock:611:    { url = "https://files.pythonhosted.org/packages/70/7b/ae1ec7f516394aa55501d1949af1f731be8d9d7433f0acc3f4632a0ba484/duckdb-1.5.2-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:81fc4fbf0b5e25840b39ba2a10b78c6953c0314d5d0434191e7898f34ab1bba3", size = 15947821, upload-time = "2026-04-13T11:28:55.981Z" },
uv.lock:612:    { url = "https://files.pythonhosted.org/packages/8a/a5/cae0105e01a85f85ead61723bb42dab14c2f8ec49f91e67a2372c02574a4/duckdb-1.5.2-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:56d38b3c4e0ef2abb58898d0fd423933999ed535c45e75e9d9f72e1d5fed69b8", size = 14201656, upload-time = "2026-04-13T11:28:58.316Z" },
uv.lock:613:    { url = "https://files.pythonhosted.org/packages/50/db/46c57e8813ac33762bddc9545610ed648751c5b6a379abf2dc6035505ce4/duckdb-1.5.2-cp311-cp311-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:376856066c65ccd55fcb3a380bbe33a71ce089fc4623d229ffc6e82251afdb6d", size = 19285181, upload-time = "2026-04-13T11:29:01.041Z" },
uv.lock:614:    { url = "https://files.pythonhosted.org/packages/dc/a2/67694010693ec8c8c975e6991f48ef886d35ecbdaa2f287234882a403c21/duckdb-1.5.2-cp311-cp311-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:c69907354ffee94ba8cf782daf0480dab7557f21ce27fffa6c0ea8f74ed4b8e2", size = 21394852, upload-time = "2026-04-13T11:29:03.814Z" },
uv.lock:615:    { url = "https://files.pythonhosted.org/packages/52/9f/2b1618c5a93949a70dcf105293db7e27bb2b2cc4aeb1ff46b806f430ec81/duckdb-1.5.2-cp311-cp311-win_amd64.whl", hash = "sha256:d9b4f5430bf4f05d4c0dc4c55c75def3a5af4be0343be20fa2bfc577343fbfc9", size = 13095526, upload-time = "2026-04-13T11:29:06.265Z" },
uv.lock:616:    { url = "https://files.pythonhosted.org/packages/b8/e9/cb39e0d94a32f5333e819112fd01439a31f541f9c56a31b66f9bd209704b/duckdb-1.5.2-cp311-cp311-win_arm64.whl", hash = "sha256:2323c1195c10fb2bb982fc0218c730b43d1b92a355d61e68e3c5f3ac9d44c34f", size = 13946215, upload-time = "2026-04-13T11:29:08.672Z" },
uv.lock:642:    { name = "duckdb" },
uv.lock:645:    { name = "numpy" },
uv.lock:659:    { name = "sentence-transformers" },
uv.lock:669:    { name = "transformers", version = "4.57.6", source = { registry = "https://pypi.org/simple" } },
uv.lock:701:    { name = "duckdb", specifier = ">=1.1,<2" },
uv.lock:705:    { name = "numpy", specifier = ">=2,<3" },
uv.lock:711:    { name = "sentence-transformers", marker = "extra == 'eval'", specifier = ">=3,<4" },
uv.lock:715:    { name = "transformers", marker = "extra == 'training'", specifier = ">=4.45,<5" },
uv.lock:782:    { name = "torch", version = "2.9.1", source = { registry = "https://pypi.org/simple" } },
uv.lock:783:    { name = "torch-c-dlpack-ext" },
uv.lock:809:    { name = "numpy" },
uv.lock:816:    { name = "torch", version = "2.9.1", source = { registry = "https://pypi.org/simple" } },
uv.lock:887:    { name = "numpy" },
uv.lock:1380:    { name = "numpy" },
uv.lock:1562:name = "numpy"
uv.lock:1565:sdist = { url = "https://files.pythonhosted.org/packages/d7/9f/b8cef5bffa569759033adda9481211426f12f53299629b410340795c2514/numpy-2.4.4.tar.gz", hash = "sha256:2d390634c5182175533585cc89f3608a4682ccb173cc9bb940b2881c8d6f8fa0", size = 20731587, upload-time = "2026-03-29T13:22:01.298Z" }
uv.lock:1567:    { url = "https://files.pythonhosted.org/packages/ef/c6/4218570d8c8ecc9704b5157a3348e486e84ef4be0ed3e38218ab473c83d2/numpy-2.4.4-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:f983334aea213c99992053ede6168500e5f086ce74fbc4acc3f2b00f5762e9db", size = 16976799, upload-time = "2026-03-29T13:18:15.438Z" },
uv.lock:1568:    { url = "https://files.pythonhosted.org/packages/dd/92/b4d922c4a5f5dab9ed44e6153908a5c665b71acf183a83b93b690996e39b/numpy-2.4.4-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:72944b19f2324114e9dc86a159787333b77874143efcf89a5167ef83cfee8af0", size = 14971552, upload-time = "2026-03-29T13:18:18.606Z" },
uv.lock:1569:    { url = "https://files.pythonhosted.org/packages/8a/dc/df98c095978fa6ee7b9a9387d1d58cbb3d232d0e69ad169a4ce784bde4fd/numpy-2.4.4-cp311-cp311-macosx_14_0_arm64.whl", hash = "sha256:86b6f55f5a352b48d7fbfd2dbc3d5b780b2d79f4d3c121f33eb6efb22e9a2015", size = 5476566, upload-time = "2026-03-29T13:18:21.532Z" },
uv.lock:1570:    { url = "https://files.pythonhosted.org/packages/28/34/b3fdcec6e725409223dd27356bdf5a3c2cc2282e428218ecc9cb7acc9763/numpy-2.4.4-cp311-cp311-macosx_14_0_x86_64.whl", hash = "sha256:ba1f4fc670ed79f876f70082eff4f9583c15fb9a4b89d6188412de4d18ae2f40", size = 6806482, upload-time = "2026-03-29T13:18:23.634Z" },
uv.lock:1571:    { url = "https://files.pythonhosted.org/packages/68/62/63417c13aa35d57bee1337c67446761dc25ea6543130cf868eace6e8157b/numpy-2.4.4-cp311-cp311-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:8a87ec22c87be071b6bdbd27920b129b94f2fc964358ce38f3822635a3e2e03d", size = 15973376, upload-time = "2026-03-29T13:18:26.677Z" },
uv.lock:1572:    { url = "https://files.pythonhosted.org/packages/cf/c5/9fcb7e0e69cef59cf10c746b84f7d58b08bc66a6b7d459783c5a4f6101a6/numpy-2.4.4-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:df3775294accfdd75f32c74ae39fcba920c9a378a2fc18a12b6820aa8c1fb502", size = 16925137, upload-time = "2026-03-29T13:18:30.14Z" },
uv.lock:1573:    { url = "https://files.pythonhosted.org/packages/7e/43/80020edacb3f84b9efdd1591120a4296462c23fd8db0dde1666f6ef66f13/numpy-2.4.4-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:0d4e437e295f18ec29bc79daf55e8a47a9113df44d66f702f02a293d93a2d6dd", size = 17329414, upload-time = "2026-03-29T13:18:33.733Z" },
uv.lock:1574:    { url = "https://files.pythonhosted.org/packages/fd/06/af0658593b18a5f73532d377188b964f239eb0894e664a6c12f484472f97/numpy-2.4.4-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:6aa3236c78803afbcb255045fbef97a9e25a1f6c9888357d205ddc42f4d6eba5", size = 18658397, upload-time = "2026-03-29T13:18:37.511Z" },
uv.lock:1575:    { url = "https://files.pythonhosted.org/packages/e6/ce/13a09ed65f5d0ce5c7dd0669250374c6e379910f97af2c08c57b0608eee4/numpy-2.4.4-cp311-cp311-win32.whl", hash = "sha256:30caa73029a225b2d40d9fae193e008e24b2026b7ee1a867b7ee8d96ca1a448e", size = 6239499, upload-time = "2026-03-29T13:18:40.372Z" },
uv.lock:1576:    { url = "https://files.pythonhosted.org/packages/bd/63/05d193dbb4b5eec1eca73822d80da98b511f8328ad4ae3ca4caf0f4db91d/numpy-2.4.4-cp311-cp311-win_amd64.whl", hash = "sha256:6bbe4eb67390b0a0265a2c25458f6b90a409d5d069f1041e6aff1e27e3d9a79e", size = 12614257, upload-time = "2026-03-29T13:18:42.95Z" },
uv.lock:1577:    { url = "https://files.pythonhosted.org/packages/87/c5/8168052f080c26fa984c413305012be54741c9d0d74abd7fbeeccae3889f/numpy-2.4.4-cp311-cp311-win_arm64.whl", hash = "sha256:fcfe2045fd2e8f3cb0ce9d4ba6dba6333b8fa05bb8a4939c908cd43322d14c7e", size = 10486775, upload-time = "2026-03-29T13:18:45.835Z" },
uv.lock:1578:    { url = "https://files.pythonhosted.org/packages/6b/33/8fae8f964a4f63ed528264ddf25d2b683d0b663e3cba26961eb838a7c1bd/numpy-2.4.4-pp311-pypy311_pp73-macosx_10_15_x86_64.whl", hash = "sha256:58c8b5929fcb8287cbd6f0a3fae19c6e03a5c48402ae792962ac465224a629a4", size = 16854491, upload-time = "2026-03-29T13:21:38.03Z" },
uv.lock:1579:    { url = "https://files.pythonhosted.org/packages/bc/d0/1aabee441380b981cf8cdda3ae7a46aa827d1b5a8cce84d14598bc94d6d9/numpy-2.4.4-pp311-pypy311_pp73-macosx_11_0_arm64.whl", hash = "sha256:eea7ac5d2dce4189771cedb559c738a71512768210dc4e4753b107a2048b3d0e", size = 14895830, upload-time = "2026-03-29T13:21:41.509Z" },
uv.lock:1580:    { url = "https://files.pythonhosted.org/packages/a5/b8/aafb0d1065416894fccf4df6b49ef22b8db045187949545bced89c034b8e/numpy-2.4.4-pp311-pypy311_pp73-macosx_14_0_arm64.whl", hash = "sha256:51fc224f7ca4d92656d5a5eb315f12eb5fe2c97a66249aa7b5f562528a3be38c", size = 5400927, upload-time = "2026-03-29T13:21:44.747Z" },
uv.lock:1581:    { url = "https://files.pythonhosted.org/packages/d6/77/063baa20b08b431038c7f9ff5435540c7b7265c78cf56012a483019ca72d/numpy-2.4.4-pp311-pypy311_pp73-macosx_14_0_x86_64.whl", hash = "sha256:28a650663f7314afc3e6ec620f44f333c386aad9f6fc472030865dc0ebb26ee3", size = 6715557, upload-time = "2026-03-29T13:21:47.406Z" },
uv.lock:1582:    { url = "https://files.pythonhosted.org/packages/c7/a8/379542d45a14f149444c5c4c4e7714707239ce9cc1de8c2803958889da14/numpy-2.4.4-pp311-pypy311_pp73-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:19710a9ca9992d7174e9c52f643d4272dcd1558c5f7af7f6f8190f633bd651a7", size = 15804253, upload-time = "2026-03-29T13:21:50.753Z" },
uv.lock:1583:    { url = "https://files.pythonhosted.org/packages/a2/c8/f0a45426d6d21e7ea3310a15cf90c43a14d9232c31a837702dba437f3373/numpy-2.4.4-pp311-pypy311_pp73-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:9b2aec6af35c113b05695ebb5749a787acd63cafc83086a05771d1e1cd1e555f", size = 16753552, upload-time = "2026-03-29T13:21:54.344Z" },
uv.lock:1584:    { url = "https://files.pythonhosted.org/packages/04/74/f4c001f4714c3ad9ce037e18cf2b9c64871a84951eaa0baf683a9ca9301c/numpy-2.4.4-pp311-pypy311_pp73-win_amd64.whl", hash = "sha256:f2cf083b324a467e1ab358c105f6cad5ea950f50524668a80c486ff1db24e119", size = 12509075, upload-time = "2026-03-29T13:21:57.644Z" },
uv.lock:1860:    { name = "numpy" },
uv.lock:2045:    { name = "numpy" },
uv.lock:2051:    { name = "torch", version = "2.9.1", source = { registry = "https://pypi.org/simple" } },
uv.lock:2092:    { name = "numpy" },
uv.lock:2140:    { name = "numpy" },
uv.lock:2154:    { name = "numpy" },
uv.lock:2159:    { name = "torch", version = "2.11.0", source = { registry = "https://pypi.org/simple" } },
uv.lock:2161:    { name = "transformers", version = "4.57.6", source = { registry = "https://pypi.org/simple" } },
uv.lock:2516:    { name = "numpy" },
uv.lock:2660:    { name = "torch", version = "2.9.1", source = { registry = "https://pypi.org/simple" } },
uv.lock:2661:    { name = "torch-c-dlpack-ext" },
uv.lock:2817:name = "scikit-learn"
uv.lock:2822:    { name = "numpy" },
uv.lock:2826:sdist = { url = "https://files.pythonhosted.org/packages/0e/d4/40988bf3b8e34feec1d0e6a051446b1f66225f8529b9309becaeef62b6c4/scikit_learn-1.8.0.tar.gz", hash = "sha256:9bccbb3b40e3de10351f8f5068e105d0f4083b1a65fa07b6634fbc401a6287fd", size = 7335585, upload-time = "2025-12-10T07:08:53.618Z" }
uv.lock:2828:    { url = "https://files.pythonhosted.org/packages/c9/92/53ea2181da8ac6bf27170191028aee7251f8f841f8d3edbfdcaf2008fde9/scikit_learn-1.8.0-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:146b4d36f800c013d267b29168813f7a03a43ecd2895d04861f1240b564421da", size = 8595835, upload-time = "2025-12-10T07:07:39.385Z" },
uv.lock:2829:    { url = "https://files.pythonhosted.org/packages/01/18/d154dc1638803adf987910cdd07097d9c526663a55666a97c124d09fb96a/scikit_learn-1.8.0-cp311-cp311-macosx_12_0_arm64.whl", hash = "sha256:f984ca4b14914e6b4094c5d52a32ea16b49832c03bd17a110f004db3c223e8e1", size = 8080381, upload-time = "2025-12-10T07:07:41.93Z" },
uv.lock:2830:    { url = "https://files.pythonhosted.org/packages/8a/44/226142fcb7b7101e64fdee5f49dbe6288d4c7af8abf593237b70fca080a4/scikit_learn-1.8.0-cp311-cp311-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:5e30adb87f0cc81c7690a84f7932dd66be5bac57cfe16b91cb9151683a4a2d3b", size = 8799632, upload-time = "2025-12-10T07:07:43.899Z" },
uv.lock:2831:    { url = "https://files.pythonhosted.org/packages/36/4d/4a67f30778a45d542bbea5db2dbfa1e9e100bf9ba64aefe34215ba9f11f6/scikit_learn-1.8.0-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:ada8121bcb4dac28d930febc791a69f7cb1673c8495e5eee274190b73a4559c1", size = 9103788, upload-time = "2025-12-10T07:07:45.982Z" },
uv.lock:2832:    { url = "https://files.pythonhosted.org/packages/89/3c/45c352094cfa60050bcbb967b1faf246b22e93cb459f2f907b600f2ceda5/scikit_learn-1.8.0-cp311-cp311-win_amd64.whl", hash = "sha256:c57b1b610bd1f40ba43970e11ce62821c2e6569e4d74023db19c6b26f246cb3b", size = 8081706, upload-time = "2025-12-10T07:07:48.111Z" },
uv.lock:2833:    { url = "https://files.pythonhosted.org/packages/3d/46/5416595bb395757f754feb20c3d776553a386b661658fb21b7c814e89efe/scikit_learn-1.8.0-cp311-cp311-win_arm64.whl", hash = "sha256:2838551e011a64e3053ad7618dda9310175f7515f1742fa2d756f7c874c05961", size = 7688451, upload-time = "2025-12-10T07:07:49.873Z" },
uv.lock:2841:    { name = "numpy" },
uv.lock:2858:name = "sentence-transformers"
uv.lock:2864:    { name = "scikit-learn" },
uv.lock:2866:    { name = "torch", version = "2.11.0", source = { registry = "https://pypi.org/simple" } },
uv.lock:2868:    { name = "transformers", version = "4.57.6", source = { registry = "https://pypi.org/simple" } },
uv.lock:2870:sdist = { url = "https://files.pythonhosted.org/packages/16/74/aca6f8a2b8d62b4daf8c9a0c49d2aa573381caf47dc35cbb343389229376/sentence_transformers-3.4.1.tar.gz", hash = "sha256:68daa57504ff548340e54ff117bd86c1d2f784b21e0fb2689cf3272b8937b24b", size = 223898, upload-time = "2025-01-29T14:25:55.982Z" }
uv.lock:2872:    { url = "https://files.pythonhosted.org/packages/05/89/7eb147a37b7f31d3c815543df539d8b8d0425e93296c875cc87719d65232/sentence_transformers-3.4.1-py3-none-any.whl", hash = "sha256:e026dc6d56801fd83f74ad29a30263f401b4b522165c19386d8bc10dcca805da", size = 275896, upload-time = "2025-01-29T14:25:53.614Z" },
uv.lock:2949:    { name = "numpy" },
uv.lock:2976:    { name = "torch", version = "2.9.1", source = { registry = "https://pypi.org/simple" } },
uv.lock:2977:    { name = "torch-memory-saver" },
uv.lock:2978:    { name = "torchao" },
uv.lock:2979:    { name = "torchaudio" },
uv.lock:2980:    { name = "torchcodec", marker = "(platform_machine != 'aarch64' and platform_machine != 'arm64' and platform_machine != 'armv7l') or sys_platform != 'linux'" },
uv.lock:2981:    { name = "torchvision" },
uv.lock:2983:    { name = "transformers", version = "5.3.0", source = { registry = "https://pypi.org/simple" } },
uv.lock:3073:    { name = "numpy" },
uv.lock:3130:    { name = "numpy" },
uv.lock:3156:    { name = "numpy" },
uv.lock:3242:    { name = "torch", version = "2.9.1", source = { registry = "https://pypi.org/simple" } },
uv.lock:3243:    { name = "torchvision" },
uv.lock:3287:name = "torch"
uv.lock:3320:    { url = "https://files.pythonhosted.org/packages/15/db/c064112ac0089af3d2f7a2b5bfbabf4aa407a78b74f87889e524b91c5402/torch-2.9.1-cp311-cp311-manylinux_2_28_aarch64.whl", hash = "sha256:62b3fd888277946918cba4478cf849303da5359f0fb4e3bfb86b0533ba2eaf8d", size = 104220430, upload-time = "2025-11-12T15:20:31.705Z" },
uv.lock:3321:    { url = "https://files.pythonhosted.org/packages/56/be/76eaa36c9cd032d3b01b001e2c5a05943df75f26211f68fae79e62f87734/torch-2.9.1-cp311-cp311-manylinux_2_28_x86_64.whl", hash = "sha256:d033ff0ac3f5400df862a51bdde9bad83561f3739ea0046e68f5401ebfa67c1b", size = 899821446, upload-time = "2025-11-12T15:20:15.544Z" },
uv.lock:3322:    { url = "https://files.pythonhosted.org/packages/47/cc/7a2949e38dfe3244c4df21f0e1c27bce8aedd6c604a587dd44fc21017cb4/torch-2.9.1-cp311-cp311-win_amd64.whl", hash = "sha256:0d06b30a9207b7c3516a9e0102114024755a07045f0c1d2f2a56b1819ac06bcb", size = 110973074, upload-time = "2025-11-12T15:21:39.958Z" },
uv.lock:3323:    { url = "https://files.pythonhosted.org/packages/1e/ce/7d251155a783fb2c1bb6837b2b7023c622a2070a0a72726ca1df47e7ea34/torch-2.9.1-cp311-none-macosx_11_0_arm64.whl", hash = "sha256:52347912d868653e1528b47cafaf79b285b98be3f4f35d5955389b1b95224475", size = 74463887, upload-time = "2025-11-12T15:20:36.611Z" },
uv.lock:3327:name = "torch"
uv.lock:3353:    { url = "https://files.pythonhosted.org/packages/ae/0d/98b410492609e34a155fa8b121b55c7dca229f39636851c3a9ec20edea21/torch-2.11.0-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:7b6a60d48062809f58595509c524b88e6ddec3ebe25833d6462eeab81e5f2ce4", size = 80529712, upload-time = "2026-03-23T18:12:02.608Z" },
uv.lock:3354:    { url = "https://files.pythonhosted.org/packages/84/03/acea680005f098f79fd70c1d9d5ccc0cb4296ec2af539a0450108232fc0c/torch-2.11.0-cp311-cp311-manylinux_2_28_aarch64.whl", hash = "sha256:d91aac77f24082809d2c5a93f52a5f085032740a1ebc9252a7b052ef5a4fddc6", size = 419718178, upload-time = "2026-03-23T18:10:46.675Z" },
uv.lock:3355:    { url = "https://files.pythonhosted.org/packages/8c/8b/d7be22fbec9ffee6cff31a39f8750d4b3a65d349a286cf4aec74c2375662/torch-2.11.0-cp311-cp311-manylinux_2_28_x86_64.whl", hash = "sha256:7aa2f9bbc6d4595ba72138026b2074be1233186150e9292865e04b7a63b8c67a", size = 530604548, upload-time = "2026-03-23T18:10:03.569Z" },
uv.lock:3356:    { url = "https://files.pythonhosted.org/packages/d1/bd/9912d30b68845256aabbb4a40aeefeef3c3b20db5211ccda653544ada4b6/torch-2.11.0-cp311-cp311-win_amd64.whl", hash = "sha256:73e24aaf8f36ab90d95cd1761208b2eb70841c2a9ca1a3f9061b39fc5331b708", size = 114519675, upload-time = "2026-03-23T18:11:52.995Z" },
uv.lock:3360:name = "torch-c-dlpack-ext"
uv.lock:3364:    { name = "torch", version = "2.9.1", source = { registry = "https://pypi.org/simple" } },
uv.lock:3366:sdist = { url = "https://files.pythonhosted.org/packages/37/de/921b6491efce5c389a5ef9bbed3d2d6660005840dae488124173180859ab/torch_c_dlpack_ext-0.1.5.tar.gz", hash = "sha256:d06f0357d575d22a168cc77acb9020fc4bae30968ceb6718a055dcbe92bacabe", size = 12913, upload-time = "2026-01-12T11:25:08.484Z" }
uv.lock:3368:    { url = "https://files.pythonhosted.org/packages/65/66/c12a9bb3a5ddc0962c00467891bf1ffdda39a4d4780bf0fbbf54523ff34e/torch_c_dlpack_ext-0.1.5-cp311-cp311-macosx_14_0_arm64.whl", hash = "sha256:56bd25a2af19280bf8a06aa62cff5510106f43235b9327d8561b3e9a659c4d84", size = 5076782, upload-time = "2026-01-12T11:24:37.868Z" },
uv.lock:3369:    { url = "https://files.pythonhosted.org/packages/20/e1/64e1e579d107064785549e70758e38a42376ab7e73d86897ed4beab10e74/torch_c_dlpack_ext-0.1.5-cp311-cp311-manylinux_2_24_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:fba674110e1fab0b176bb5a28223e157db65c90767d4ba74abdbee9f537b0e9d", size = 440949, upload-time = "2026-01-12T11:24:39.716Z" },
uv.lock:3370:    { url = "https://files.pythonhosted.org/packages/64/5c/3e1382a620824f92920ab3fae132d8fb4e85898284c99e0c6a7764e452ce/torch_c_dlpack_ext-0.1.5-cp311-cp311-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:3448c4f0d64104d0b2e58080a7efa72304a04960c18f338024b80b13cd3eca26", size = 897768, upload-time = "2026-01-12T11:24:41.209Z" },
uv.lock:3371:    { url = "https://files.pythonhosted.org/packages/54/4f/76ea1006b9038b496d01e916c91efd17cb782abde2491a261cf203f57e30/torch_c_dlpack_ext-0.1.5-cp311-cp311-win_amd64.whl", hash = "sha256:74676474e0afa9a4216c4755ea7cf05e8158be1d168f6bda669ba91097c263f2", size = 1479088, upload-time = "2026-01-12T11:24:42.436Z" },
uv.lock:3375:name = "torch-memory-saver"
uv.lock:3378:sdist = { url = "https://files.pythonhosted.org/packages/28/6c/21dfda5d31afb71f52cedff52370acbb8290485b3f0fee6816a15a3d08f1/torch_memory_saver-0.0.9.tar.gz", hash = "sha256:3bbf76391fb16870b1b0df279fc281c8a05ef8f8809400b309b0a8240e8ee5ba", size = 14220, upload-time = "2025-10-18T02:10:18.163Z" }
uv.lock:3380:    { url = "https://files.pythonhosted.org/packages/3a/35/b22df9e730d8444d62445a594421992781c7fad271325d41656d8a32d103/torch_memory_saver-0.0.9-cp39-abi3-manylinux2014_x86_64.whl", hash = "sha256:0cf26332993649f8ea1b95d7307dfba3a95ee6cee53de84a3e561fb21752b584", size = 488722, upload-time = "2025-10-18T02:10:16.825Z" },
uv.lock:3384:name = "torchao"
uv.lock:3388:    { url = "https://files.pythonhosted.org/packages/7d/fe/a24225d30775192a4c5d9cea3ecb95e6adc69d0a8b5ed98eb8e58d362344/torchao-0.9.0-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:bc708910301a9f98344d43f3fe2aa6d5e1fab706d772b6df47ff05087d664145", size = 5652091, upload-time = "2025-02-28T13:54:15.239Z" },
uv.lock:3389:    { url = "https://files.pythonhosted.org/packages/db/72/01f755514fb61eadc80b974eb4bd4f22f3009b35457773523e3bd497c511/torchao-0.9.0-py3-none-any.whl", hash = "sha256:ea5603c32762f1a9ade1a4dc7b00f5246623b24a28e49e666f614c79a408712a", size = 712541, upload-time = "2025-02-28T13:54:13.671Z" },
uv.lock:3393:name = "torchaudio"
uv.lock:3397:    { name = "torch", version = "2.9.1", source = { registry = "https://pypi.org/simple" } },
uv.lock:3400:    { url = "https://files.pythonhosted.org/packages/3f/6b/34e489fcb4adc4b571a166f2670cc7f156cbe3337867a892fade0a1a5224/torchaudio-2.9.1-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:6e3f5943135701168d30196e2befd46290180cdbb9ee508b167730d51f43208f", size = 807349, upload-time = "2025-11-12T15:25:57.843Z" },
uv.lock:3401:    { url = "https://files.pythonhosted.org/packages/a6/52/66830da8b638368bc0aef064f3307c88d28b526ff8e60a1fda681466b1b3/torchaudio-2.9.1-cp311-cp311-manylinux_2_28_aarch64.whl", hash = "sha256:d192cf3b1b677f6666dad60caf0ce7bab66965751570c694645dd905a6c61724", size = 474291, upload-time = "2025-11-12T15:25:45.21Z" },
uv.lock:3402:    { url = "https://files.pythonhosted.org/packages/cb/6f/d8f1f36c9f63ddef78f00f8f8ddb9638128ceb5f6824c28bead5af48fc63/torchaudio-2.9.1-cp311-cp311-manylinux_2_28_x86_64.whl", hash = "sha256:8327e21f51dced2b6de3ac6a63f04bae9be9bc213e151f85c76164568c7ebc3d", size = 2058677, upload-time = "2025-11-12T15:25:53.09Z" },
uv.lock:3403:    { url = "https://files.pythonhosted.org/packages/c3/ef/0ec42e783774bd1dda8bc2489e18b3e9c0a250384e0131cec9f35949f385/torchaudio-2.9.1-cp311-cp311-win_amd64.whl", hash = "sha256:b41339a71b186bad238d94cfb68d4c202db0033088a7b824ce5484674bf67057", size = 664681, upload-time = "2025-11-12T15:25:59.08Z" },
uv.lock:3407:name = "torchcodec"
uv.lock:3411:    { url = "https://files.pythonhosted.org/packages/c0/37/169238bb55017b08a93530d6f4474a112780df4c05c26c78df7dd58401f1/torchcodec-0.9.1-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:7a81d29e67cebefaec08f9c817635d1ff47205814884e527ef4b135a6c795612", size = 3899002, upload-time = "2025-12-10T15:55:49.911Z" },
uv.lock:3412:    { url = "https://files.pythonhosted.org/packages/75/74/11c59e0592e555df78cfee2fd4b8ba5c725e4bf160002af88ce09de99d9d/torchcodec-0.9.1-cp311-cp311-manylinux_2_28_x86_64.whl", hash = "sha256:5e959c7abf95de62f78653d416f00f7ca32936fbfd23371b23d5c8dc199f3670", size = 2048262, upload-time = "2025-12-10T15:55:29.552Z" },
uv.lock:3413:    { url = "https://files.pythonhosted.org/packages/53/66/0612c7852cb7854dec45db9357397b4dbd4d6274832cc8949a8d1c0e518a/torchcodec-0.9.1-cp311-cp311-win_amd64.whl", hash = "sha256:508e0ce6da1e4af186b131cdbdd3d998bc4313e9f3a3f5b78f64aa5f9685ed88", size = 2181959, upload-time = "2025-12-10T15:56:13.191Z" },
uv.lock:3417:name = "torchvision"
uv.lock:3421:    { name = "numpy" },
uv.lock:3423:    { name = "torch", version = "2.9.1", source = { registry = "https://pypi.org/simple" } },
uv.lock:3426:    { url = "https://files.pythonhosted.org/packages/e7/69/30f5f03752aa1a7c23931d2519b31e557f3f10af5089d787cddf3b903ecf/torchvision-0.24.1-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:056c525dc875f18fe8e9c27079ada166a7b2755cea5a2199b0bc7f1f8364e600", size = 1891436, upload-time = "2025-11-12T15:25:04.3Z" },
uv.lock:3427:    { url = "https://files.pythonhosted.org/packages/0c/69/49aae86edb75fe16460b59a191fcc0f568c2378f780bb063850db0fe007a/torchvision-0.24.1-cp311-cp311-manylinux_2_28_aarch64.whl", hash = "sha256:1e39619de698e2821d71976c92c8a9e50cdfd1e993507dfb340f2688bfdd8283", size = 2387757, upload-time = "2025-11-12T15:25:06.795Z" },
uv.lock:3428:    { url = "https://files.pythonhosted.org/packages/11/c9/1dfc3db98797b326f1d0c3f3bb61c83b167a813fc7eab6fcd2edb8c7eb9d/torchvision-0.24.1-cp311-cp311-manylinux_2_28_x86_64.whl", hash = "sha256:a0f106663e60332aa4fcb1ca2159ef8c3f2ed266b0e6df88de261048a840e0df", size = 8047682, upload-time = "2025-11-12T15:25:21.125Z" },
uv.lock:3429:    { url = "https://files.pythonhosted.org/packages/fa/bb/cfc6a6f6ccc84a534ed1fdf029ae5716dd6ff04e57ed9dc2dab38bf652d5/torchvision-0.24.1-cp311-cp311-win_amd64.whl", hash = "sha256:a9308cdd37d8a42e14a3e7fd9d271830c7fecb150dd929b642f3c1460514599a", size = 4037588, upload-time = "2025-11-12T15:25:14.402Z" },
uv.lock:3471:name = "transformers"
uv.lock:3482:    { name = "numpy" },
uv.lock:3491:sdist = { url = "https://files.pythonhosted.org/packages/c4/35/67252acc1b929dc88b6602e8c4a982e64f31e733b804c14bc24b47da35e6/transformers-4.57.6.tar.gz", hash = "sha256:55e44126ece9dc0a291521b7e5492b572e6ef2766338a610b9ab5afbb70689d3", size = 10134912, upload-time = "2026-01-16T10:38:39.284Z" }
uv.lock:3493:    { url = "https://files.pythonhosted.org/packages/03/b8/e484ef633af3887baeeb4b6ad12743363af7cce68ae51e938e00aaa0529d/transformers-4.57.6-py3-none-any.whl", hash = "sha256:4c9e9de11333ddfe5114bc872c9f370509198acf0b87a832a0ab9458e2bd0550", size = 11993498, upload-time = "2026-01-16T10:38:31.289Z" },
uv.lock:3497:name = "transformers"
uv.lock:3507:    { name = "numpy" },
uv.lock:3516:sdist = { url = "https://files.pythonhosted.org/packages/fc/1a/70e830d53ecc96ce69cfa8de38f163712d2b43ac52fbd743f39f56025c31/transformers-5.3.0.tar.gz", hash = "sha256:009555b364029da9e2946d41f1c5de9f15e6b1df46b189b7293f33a161b9c557", size = 8830831, upload-time = "2026-03-04T17:41:46.119Z" }
uv.lock:3518:    { url = "https://files.pythonhosted.org/packages/b8/88/ae8320064e32679a5429a2c9ebbc05c2bf32cefb6e076f9b07f6d685a9b4/transformers-5.3.0-py3-none-any.whl", hash = "sha256:50ac8c89c3c7033444fb3f9f53138096b997ebb70d4b5e50a2e810bf12d3d29a", size = 10661827, upload-time = "2026-03-04T17:41:42.722Z" },
uv.lock:3738:    { name = "numpy" },
uv.lock:3740:    { name = "torch", version = "2.9.1", source = { registry = "https://pypi.org/simple" } },
uv.lock:3741:    { name = "transformers", version = "5.3.0", source = { registry = "https://pypi.org/simple" } },

exec
/bin/zsh -lc "rg -n \"eval-egress|metrics\\.\" .github/workflows tests src/erre_sandbox/training src/erre_sandbox/contracts src/erre_sandbox/evidence | sed -n '1,220p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
.github/workflows/ci.yml:83:  eval-egress-grep-gate:
.github/workflows/ci.yml:88:    # the obvious ``metrics.`` shape inside the documented training-
.github/workflows/ci.yml:92:    name: eval egress grep gate (no `metrics.` in training paths)
.github/workflows/ci.yml:97:      - name: Forbid `metrics.` in training-egress modules
.github/workflows/ci.yml:117:          # eval_store guards the boundary), but a literal ``metrics.``
.github/workflows/ci.yml:137:          echo "[eval-egress-grep-gate] PASS (B-1 individual-layer literal guard included; weak backstop only — primary guard is the behavioural sentinel + construction-time aggregate assert)"
src/erre_sandbox/contracts/eval_paths.py:21:   ``metrics.``.
src/erre_sandbox/evidence/eval_store.py:14:  and ``metrics.tier_{a,b,c}``. The raw column set is locked in lockstep
src/erre_sandbox/evidence/eval_store.py:286:    """Create ``raw_dialog.dialog`` and ``metrics.tier_{a,b,c}`` idempotently.
src/erre_sandbox/evidence/eval_store.py:337:    modules — see ``.github/workflows/ci.yml`` ``eval-egress-grep-gate``
src/erre_sandbox/evidence/eval_store.py:393:    """One row of ``metrics.tier_b`` decoded for analysis-side consumers.
src/erre_sandbox/evidence/eval_store.py:526:    the JSON shape stays uniform across sub-metrics. Optional fields are
src/erre_sandbox/contracts/thresholds.py:5:narrative (``.steering/20260419-m2-integration-e2e/metrics.md``) explains the
src/erre_sandbox/evidence/tier_b/vendi.py:25:in the sidecar ``notes`` JSON when persisting to ``metrics.tier_b``.
tests/test_ui/test_state.py:134:    assert metrics.sample_count == 6
tests/test_evidence/test_scaling_metrics.py:573:    # Only the 6 autonomous turns drive metrics.
src/erre_sandbox/evidence/scaling_metrics.py:383:        raw = metrics.get(candidate)
src/erre_sandbox/evidence/scaling_metrics.py:554:       turns drive the relational-saturation metrics. Q&A epoch turns
src/erre_sandbox/evidence/scaling_metrics.py:573:        conn = store._conn  # noqa: SLF001 — sync close mirrors evidence.metrics.aggregate
tests/test_evidence/test_eval_store.py:206:    db = tmp_path / "with_metrics.duckdb"
tests/test_evidence/test_eval_store.py:562:    """DB5 sentinel: training view never surfaces metrics.tier_b columns."""
tests/test_evidence/test_eval_paths_contract.py:60:"""Values planted in metrics.tier_a — none of these may surface through
tests/test_evidence/test_eval_paths_contract.py:142:        # metrics.tier_a — poisoned with leak sentinels.

exec
/bin/zsh -lc "rg -n \"individual_layer_enabled|epoch_phase|connect_training_view|assert_phase_beta_ready\" src tests .steering/20260430-m9-b-lora-execution-plan | sed -n '1,240p'" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
tests/test_training/test_train_kant_lora.py:24:    connect_training_view,
tests/test_training/test_train_kant_lora.py:30:from erre_sandbox.training.train_kant_lora import assert_phase_beta_ready
tests/test_training/test_train_kant_lora.py:35:    """Hard-fail #1: any ``epoch_phase=evaluation`` row triggers (CS-3)."""
tests/test_training/test_train_kant_lora.py:38:        make_kant_row(utterance="LEAKED EVAL", epoch_phase="evaluation"),
tests/test_training/test_train_kant_lora.py:41:    with pytest.raises(EvaluationContaminationError, match="epoch_phase"):
tests/test_training/test_train_kant_lora.py:42:        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1)
tests/test_training/test_train_kant_lora.py:48:        make_kant_row(utterance="Clean turn", individual_layer_enabled=None),
tests/test_training/test_train_kant_lora.py:55:        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1)
tests/test_training/test_train_kant_lora.py:59:    """Hard-fail #3: ``individual_layer_enabled=True`` row triggers (DB11)."""
tests/test_training/test_train_kant_lora.py:62:        make_kant_row(utterance="LEAKED IND", individual_layer_enabled=True),
tests/test_training/test_train_kant_lora.py:67:        match="individual_layer_enabled",
tests/test_training/test_train_kant_lora.py:69:        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1)
tests/test_training/test_train_kant_lora.py:75:        make_kant_row(utterance=f"Sentence {i}", individual_layer_enabled=False)
tests/test_training/test_train_kant_lora.py:83:        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1000)
tests/test_training/test_train_kant_lora.py:90:        make_kant_row(utterance="LEAKED CASING", epoch_phase="EVALUATION"),
tests/test_training/test_train_kant_lora.py:93:    with pytest.raises(EvaluationContaminationError, match="epoch_phase"):
tests/test_training/test_train_kant_lora.py:94:        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1)
tests/test_training/test_train_kant_lora.py:98:    """Non-bool truthy ``individual_layer_enabled`` trips guard (sec MEDIUM-3)."""
tests/test_training/test_train_kant_lora.py:102:        {**make_kant_row(utterance="LEAKED INT"), "individual_layer_enabled": 1},
tests/test_training/test_train_kant_lora.py:106:        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1)
tests/test_training/test_train_kant_lora.py:112:        make_kant_row(utterance=f"Sentence {i}", individual_layer_enabled=False)
tests/test_training/test_train_kant_lora.py:116:    realised = assert_phase_beta_ready(
tests/test_training/test_train_kant_lora.py:125:# B-1 integration tests — bootstrap_schema → INSERT → connect_training_view
tests/test_training/test_train_kant_lora.py:154:    """B-1 GREEN: bootstrap → insert 3 clean rows → connect_training_view →
tests/test_training/test_train_kant_lora.py:155:    ``assert_phase_beta_ready(min_examples=1)`` returns realised count
tests/test_training/test_train_kant_lora.py:166:                individual_layer_enabled=False,
tests/test_training/test_train_kant_lora.py:174:    relation = connect_training_view(db)
tests/test_training/test_train_kant_lora.py:176:        realised = assert_phase_beta_ready(
tests/test_training/test_train_kant_lora.py:186:def test_assert_phase_beta_ready_blocks_individual_layer_true_via_real_relation(
tests/test_training/test_train_kant_lora.py:189:    """B-1 (Codex HIGH-2): a truthy ``individual_layer_enabled`` row must be
tests/test_training/test_train_kant_lora.py:201:            individual_layer_enabled=True,
tests/test_training/test_train_kant_lora.py:209:                individual_layer_enabled=False,
tests/test_training/test_train_kant_lora.py:217:    with pytest.raises(EvaluationContaminationError, match="individual_layer_enabled"):
tests/test_training/test_train_kant_lora.py:218:        connect_training_view(db)
tests/test_training/test_train_kant_lora.py:221:def test_assert_phase_beta_ready_blocks_evaluation_phase_via_real_relation(
tests/test_training/test_train_kant_lora.py:224:    """B-1 (Codex HIGH-2): an ``epoch_phase=evaluation`` row must be
tests/test_training/test_train_kant_lora.py:227:    inside ``assert_phase_beta_ready``); post-G7 the row is rejected at
tests/test_training/test_train_kant_lora.py:228:    ``connect_training_view`` with :class:`EvaluationContaminationError`."""
tests/test_training/test_train_kant_lora.py:235:            epoch_phase="evaluation",
tests/test_training/test_train_kant_lora.py:236:            individual_layer_enabled=False,
tests/test_training/test_train_kant_lora.py:242:            individual_layer_enabled=False,
tests/test_training/test_train_kant_lora.py:250:    with pytest.raises(EvaluationContaminationError, match="epoch_phase"):
tests/test_training/test_train_kant_lora.py:251:        connect_training_view(db)
tests/test_training/test_dataset.py:13:        make_kant_row(utterance="Should drop", epoch_phase="evaluation"),
tests/test_training/conftest.py:9:``individual_layer_enabled`` column to a synthetic DB would require
tests/test_training/conftest.py:35:    * ``columns`` — controls whether ``individual_layer_enabled`` is
tests/test_training/conftest.py:39:      ``dict[str, object]`` so tests can plant ``epoch_phase=evaluation``,
tests/test_training/conftest.py:40:      ``individual_layer_enabled=True``, or empty utterances at will.
tests/test_training/conftest.py:75:    "epoch_phase",
tests/test_training/conftest.py:91:            relation reports ``individual_layer_enabled`` in its
tests/test_training/conftest.py:98:        columns = (*columns, "individual_layer_enabled")
tests/test_training/conftest.py:105:    epoch_phase: str = "autonomous",
tests/test_training/conftest.py:106:    individual_layer_enabled: bool | None = False,
tests/test_training/conftest.py:114:    Setting ``individual_layer_enabled=None`` omits the key entirely
tests/test_training/conftest.py:132:        "epoch_phase": epoch_phase,
tests/test_training/conftest.py:135:    if individual_layer_enabled is not None:
tests/test_training/conftest.py:136:        row["individual_layer_enabled"] = individual_layer_enabled
tests/test_cli/test_eval_audit.py:67:                ' "utterance", "mode", "zone", "reasoning", "epoch_phase",'
tests/test_cli/test_eval_audit.py:93:                ' "utterance", "mode", "zone", "reasoning", "epoch_phase",'
.steering/20260430-m9-b-lora-execution-plan/design-final.md:303:   `individual_layer_enabled: bool` フィールドを raw_dialog metadata に追加 (default=false)。
.steering/20260430-m9-b-lora-execution-plan/design-final.md:305:   `evaluation_epoch=false AND individual_layer_enabled=false` only loader に拡張。
.steering/20260430-m9-b-lora-execution-plan/design-final.md:307:   `all(row.metadata.individual_layer_enabled is False)` を assert、contamination
.steering/20260430-m9-b-lora-execution-plan/design-final.md:310:   M9-B execution と並行可、ただし `individual_layer_enabled=true` で生成された
.steering/20260430-m9-b-lora-execution-plan/design-final.md:315:- **M9-eval-system** Parquet pipeline 実装時: `individual_layer_enabled` field 追加 (DB5 拡張)
.steering/20260430-m9-b-lora-execution-plan/design-final.md:318:  `individual_layer_enabled=true` を立てる責務
.steering/20260430-m9-b-lora-execution-plan/design-final.md:325:- 既存 raw_dialog data (M9-A / M7ζ / 過去 run) は `individual_layer_enabled=false` で
tests/test_schemas.py:600:def test_epoch_phase_has_three_members() -> None:
tests/test_schemas.py:604:def test_epoch_phase_round_trip_as_json() -> None:
tests/test_schemas.py:605:    state = RunLifecycleState(epoch_phase=EpochPhase.Q_AND_A)
tests/test_schemas.py:607:    assert payload["epoch_phase"] == "q_and_a"
tests/test_schemas.py:609:    assert restored.epoch_phase is EpochPhase.Q_AND_A
tests/test_schemas.py:616:    assert state.epoch_phase is EpochPhase.AUTONOMOUS
tests/test_schemas.py:623:    """``extra="forbid"`` guards typos like ``run_phase`` vs ``epoch_phase``."""
tests/test_schemas.py:626:            {"epoch_phase": "autonomous", "run_phase": "autonomous"},
tests/test_schemas.py:632:        RunLifecycleState.model_validate({"epoch_phase": "bogus"})
.steering/20260430-m9-b-lora-execution-plan/decisions.md:281:raw_dialog metadata に `individual_layer_enabled: bool` field を追加 (default=false)。
.steering/20260430-m9-b-lora-execution-plan/decisions.md:282:training-view contract loader は **`evaluation_epoch=false AND individual_layer_enabled=false`**
.steering/20260430-m9-b-lora-execution-plan/decisions.md:284:`all(row.metadata.individual_layer_enabled is False)` を assert し、contamination
.steering/20260430-m9-b-lora-execution-plan/decisions.md:308:- DB5 (Parquet schema 物理分離) に `individual_layer_enabled` field を 1 つ追加 (additive)
.steering/20260430-m9-b-lora-execution-plan/decisions.md:312:- M10-A scaffold 設計時に `individual_layer_enabled=true` set 責務を明示
src/erre_sandbox/contracts/eval_paths.py:52:through :func:`erre_sandbox.evidence.eval_store.connect_training_view`.
src/erre_sandbox/contracts/eval_paths.py:70:INDIVIDUAL_LAYER_ENABLED_KEY: Final[str] = "individual_layer_enabled"
src/erre_sandbox/contracts/eval_paths.py:74:(:func:`erre_sandbox.training.train_kant_lora.assert_phase_beta_ready`)
src/erre_sandbox/contracts/eval_paths.py:96:        "epoch_phase",
src/erre_sandbox/contracts/eval_paths.py:116:inside :func:`erre_sandbox.training.train_kant_lora.assert_phase_beta_ready`.
src/erre_sandbox/contracts/eval_paths.py:151:``metrics`` schema and assert they never reach ``connect_training_view``
tests/test_memory/test_store.py:495:# M7ε — dialog_turns.epoch_phase column + migration
tests/test_memory/test_store.py:499:def test_dialog_turns_schema_has_epoch_phase_column(store: MemoryStore) -> None:
tests/test_memory/test_store.py:500:    """A freshly created DB carries the M7ε ``epoch_phase`` column."""
tests/test_memory/test_store.py:503:    assert "epoch_phase" in cols
tests/test_memory/test_store.py:512:    assert "epoch_phase" in cols
tests/test_memory/test_store.py:523:    # Build an old-shape ``dialog_turns`` table by hand (no ``epoch_phase``).
tests/test_memory/test_store.py:571:        assert "epoch_phase" in cols
tests/test_memory/test_store.py:572:        # The legacy row survives with NULL epoch_phase.
tests/test_memory/test_store.py:576:        assert rows[0]["epoch_phase"] is None
tests/test_memory/test_store.py:585:    """``add_dialog_turn_sync`` defaults ``epoch_phase`` to AUTONOMOUS."""
tests/test_memory/test_store.py:595:    assert rows[0]["epoch_phase"] == EpochPhase.AUTONOMOUS.value
tests/test_memory/test_store.py:599:    """Explicit ``epoch_phase=Q_AND_A`` is persisted (m9-LoRA producer path)."""
tests/test_memory/test_store.py:606:        epoch_phase=EpochPhase.Q_AND_A,
tests/test_memory/test_store.py:610:    assert rows[0]["epoch_phase"] == EpochPhase.Q_AND_A.value
tests/test_memory/test_store.py:613:def test_iter_dialog_turns_filters_by_epoch_phase_autonomous(
tests/test_memory/test_store.py:629:        epoch_phase=EpochPhase.Q_AND_A,
tests/test_memory/test_store.py:636:            "addressee_persona_id, utterance, created_at, epoch_phase) "
tests/test_memory/test_store.py:653:    autonomous_rows = list(store.iter_dialog_turns(epoch_phase=EpochPhase.AUTONOMOUS))
tests/test_memory/test_store.py:657:    qa_rows = list(store.iter_dialog_turns(epoch_phase=EpochPhase.Q_AND_A))
src/erre_sandbox/training/exceptions.py:4::func:`erre_sandbox.training.train_kant_lora.assert_phase_beta_ready`:
src/erre_sandbox/training/exceptions.py:29:    Raised by :func:`assert_phase_beta_ready` when the training-view
src/erre_sandbox/training/exceptions.py:30:    schema does not expose the ``individual_layer_enabled`` column. The
src/erre_sandbox/training/exceptions.py:42:    landed, the production ``connect_training_view()`` path will never
src/erre_sandbox/training/exceptions.py:58:    Raised by :func:`assert_phase_beta_ready` when
src/erre_sandbox/training/dataset.py:5:ChatML formatter). It applies the persona / epoch_phase / empty-utterance
src/erre_sandbox/training/dataset.py:12:Filter order (mirrors :func:`assert_phase_beta_ready` so the gate count and
src/erre_sandbox/training/dataset.py:15:1. ``epoch_phase == "evaluation"`` rows are dropped (CS-3 sentinel).
src/erre_sandbox/training/dataset.py:56:            :func:`assert_phase_beta_ready` *before* this function runs, so
src/erre_sandbox/training/dataset.py:70:        # CS-3 belt-and-braces: even though assert_phase_beta_ready raises on
src/erre_sandbox/training/dataset.py:75:        if str(row.get("epoch_phase", "")).strip().lower() == _EVALUATION_PHASE_VALUE:
tests/test_evidence/test_scaling_metrics.py:512:# M7ε D4 / M8 D5 — aggregate() filters by epoch_phase
tests/test_evidence/test_scaling_metrics.py:551:            epoch_phase=EpochPhase.AUTONOMOUS,
tests/test_evidence/test_scaling_metrics.py:569:            epoch_phase=EpochPhase.Q_AND_A,
tests/test_evidence/test_scaling_metrics.py:598:            epoch_phase=EpochPhase.AUTONOMOUS,
tests/test_evidence/test_scaling_metrics.py:608:    """Pre-M7ε rows have NULL ``epoch_phase`` and must count as AUTONOMOUS.
tests/test_evidence/test_scaling_metrics.py:619:    # Insert rows directly with NULL epoch_phase, bypassing add_dialog_turn_sync.
tests/test_evidence/test_scaling_metrics.py:629:                "addressee_persona_id, utterance, created_at, epoch_phase) "
src/erre_sandbox/training/__init__.py:7:  ``individual_layer_enabled`` column. Phase β cannot proceed silently.
src/erre_sandbox/training/__init__.py:12:  error, returned for ``epoch_phase=evaluation`` rows or
src/erre_sandbox/training/__init__.py:13:  ``individual_layer_enabled=True`` rows that surface through the
src/erre_sandbox/training/__init__.py:20:* :func:`assert_phase_beta_ready` — 4-種 hard-fail gate (CS-3) that must
src/erre_sandbox/training/__init__.py:29:  ``connect_training_view`` for production callers), ``pydantic``,
src/erre_sandbox/training/__init__.py:52:    assert_phase_beta_ready,
src/erre_sandbox/training/__init__.py:61:    "assert_phase_beta_ready",
tests/test_evidence/test_eval_store.py:7:* :func:`connect_training_view` opens read-only after bootstrap and
tests/test_evidence/test_eval_store.py:42:    connect_training_view,
tests/test_evidence/test_eval_store.py:111:    relation = connect_training_view(db)
tests/test_evidence/test_eval_store.py:125:def test_bootstrap_individual_layer_enabled_column_is_not_null_with_default_false(
tests/test_evidence/test_eval_store.py:128:    """B-1 (Codex HIGH-1): the new ``individual_layer_enabled`` column must
tests/test_evidence/test_eval_store.py:140:            (RAW_DIALOG_SCHEMA, RAW_DIALOG_TABLE, "individual_layer_enabled"),
tests/test_evidence/test_eval_store.py:145:        "individual_layer_enabled column not found in raw_dialog.dialog"
tests/test_evidence/test_eval_store.py:150:        f"individual_layer_enabled must be NOT NULL, got is_nullable={is_nullable!r}"
tests/test_evidence/test_eval_store.py:156:        "individual_layer_enabled default must be FALSE,"
tests/test_evidence/test_eval_store.py:161:def test_explicit_null_insert_into_individual_layer_enabled_rejected(
tests/test_evidence/test_eval_store.py:186:        assert "individual_layer_enabled" in cols, (
tests/test_evidence/test_eval_store.py:193:                ' ("id", "individual_layer_enabled") VALUES (?, ?)',
tests/test_evidence/test_eval_store.py:267:    relation = connect_training_view(db)
tests/test_evidence/test_eval_store.py:582:    relation = connect_training_view(db)
tests/test_schemas_m7g.py:52:    ``dialog_turns.epoch_phase`` column, M7ζ bumps for additive panel
src/erre_sandbox/training/train_kant_lora.py:5:* :func:`assert_phase_beta_ready` — the 4-種 hard-fail gate. Pure Python
src/erre_sandbox/training/train_kant_lora.py:13:  ``assert_phase_beta_ready`` test suite) can be imported on a CI
src/erre_sandbox/training/train_kant_lora.py:22:1. ``epoch_phase == "evaluation"`` row present → :class:`EvaluationContaminationError`
src/erre_sandbox/training/train_kant_lora.py:23:2. ``individual_layer_enabled`` column absent in ``relation.columns`` →
src/erre_sandbox/training/train_kant_lora.py:25:3. ``individual_layer_enabled is True`` row present →
src/erre_sandbox/training/train_kant_lora.py:31:realised-count check, so a flood of ``epoch_phase=evaluation`` rows
src/erre_sandbox/training/train_kant_lora.py:37:``individual_layer_enabled`` as ``BOOLEAN NOT NULL DEFAULT FALSE`` and
src/erre_sandbox/training/train_kant_lora.py:39:aggregate assert (Codex HIGH-2) that rejects ``epoch_phase=evaluation``
src/erre_sandbox/training/train_kant_lora.py:40:rows and truthy / NULL ``individual_layer_enabled`` rows before any
src/erre_sandbox/training/train_kant_lora.py:79:def assert_phase_beta_ready(
src/erre_sandbox/training/train_kant_lora.py:84:    individual_layer_enabled_required: bool = True,
src/erre_sandbox/training/train_kant_lora.py:96:            output of :func:`erre_sandbox.evidence.eval_store.connect_training_view`).
src/erre_sandbox/training/train_kant_lora.py:99:            does not interfere with the synthetic ``individual_layer_enabled``
src/erre_sandbox/training/train_kant_lora.py:107:        individual_layer_enabled_required: When ``True`` (default), the
src/erre_sandbox/training/train_kant_lora.py:122:        EvaluationContaminationError: ``epoch_phase=evaluation`` row, or
src/erre_sandbox/training/train_kant_lora.py:123:            ``individual_layer_enabled=True`` row, surfaced through the
src/erre_sandbox/training/train_kant_lora.py:125:        BlockerNotResolvedError: ``individual_layer_enabled`` column is
src/erre_sandbox/training/train_kant_lora.py:133:    # 1) epoch_phase=evaluation contamination — must run first so the
src/erre_sandbox/training/train_kant_lora.py:141:        if str(r.get("epoch_phase", "")).strip().lower() == _EVALUATION_PHASE_VALUE
src/erre_sandbox/training/train_kant_lora.py:145:            f"assert_phase_beta_ready: {len(eval_rows)} row(s) carry"
src/erre_sandbox/training/train_kant_lora.py:146:            f" epoch_phase~={_EVALUATION_PHASE_VALUE!r} (case-insensitive);"
src/erre_sandbox/training/train_kant_lora.py:151:    # 2 + 3) individual_layer_enabled enforcement (DB11 / blocker B-1)
src/erre_sandbox/training/train_kant_lora.py:152:    if individual_layer_enabled_required:
src/erre_sandbox/training/train_kant_lora.py:155:                f"assert_phase_beta_ready: training-view schema does not"
src/erre_sandbox/training/train_kant_lora.py:170:                f"assert_phase_beta_ready: {len(ind_rows)} row(s) have"
src/erre_sandbox/training/train_kant_lora.py:181:            f"assert_phase_beta_ready: realised {persona_id!r} example count"
src/erre_sandbox/training/train_kant_lora.py:200:    :func:`assert_phase_beta_ready` around a real DuckDB-backed
src/erre_sandbox/training/train_kant_lora.py:217:            :func:`assert_phase_beta_ready`.
src/erre_sandbox/training/train_kant_lora.py:232:        connect_training_view,
src/erre_sandbox/training/train_kant_lora.py:235:    relation = connect_training_view(db_path)
src/erre_sandbox/training/train_kant_lora.py:236:    realised = assert_phase_beta_ready(
src/erre_sandbox/training/train_kant_lora.py:240:        individual_layer_enabled_required=True,
src/erre_sandbox/training/train_kant_lora.py:254:    "assert_phase_beta_ready",
tests/test_evidence/test_eval_paths_contract.py:11:* :func:`erre_sandbox.evidence.eval_store.connect_training_view` and
tests/test_evidence/test_eval_paths_contract.py:41:    connect_training_view,
tests/test_evidence/test_eval_paths_contract.py:174:# connect_training_view contract
tests/test_evidence/test_eval_paths_contract.py:179:    relation = connect_training_view(seeded_duckdb)
tests/test_evidence/test_eval_paths_contract.py:188:    relation = connect_training_view(seeded_duckdb)
tests/test_evidence/test_eval_paths_contract.py:197:    relation = connect_training_view(seeded_duckdb)
tests/test_evidence/test_eval_paths_contract.py:216:    relation = connect_training_view(seeded_duckdb)
tests/test_evidence/test_eval_paths_contract.py:231:    relation = connect_training_view(seeded_duckdb)
tests/test_evidence/test_eval_paths_contract.py:259:        connect_training_view(db)
tests/test_evidence/test_eval_paths_contract.py:271:        connect_training_view(db)
tests/test_evidence/test_eval_paths_contract.py:321:def test_individual_layer_enabled_in_allowed_keys() -> None:
tests/test_evidence/test_eval_paths_contract.py:324:    Without this membership ``connect_training_view`` would either drop
tests/test_evidence/test_eval_paths_contract.py:327:    assert "individual_layer_enabled" in ALLOWED_RAW_DIALOG_KEYS
tests/test_evidence/test_eval_paths_contract.py:330:def test_individual_layer_enabled_key_constant_exported() -> None:
tests/test_evidence/test_eval_paths_contract.py:339:    assert ep.INDIVIDUAL_LAYER_ENABLED_KEY == "individual_layer_enabled"
tests/test_world/test_runtime_lifecycle.py:25:        assert state.epoch_phase is EpochPhase.AUTONOMOUS
tests/test_world/test_runtime_lifecycle.py:39:        assert result.epoch_phase is EpochPhase.Q_AND_A
tests/test_world/test_runtime_lifecycle.py:40:        assert world_harness.runtime.run_lifecycle.epoch_phase is EpochPhase.Q_AND_A
tests/test_world/test_runtime_lifecycle.py:45:        assert result.epoch_phase is EpochPhase.EVALUATION
tests/test_world/test_runtime_lifecycle.py:46:        assert world_harness.runtime.run_lifecycle.epoch_phase is EpochPhase.EVALUATION
tests/test_world/test_runtime_lifecycle.py:58:        assert before.epoch_phase is EpochPhase.AUTONOMOUS
tests/test_world/test_runtime_lifecycle.py:68:        assert world_harness.runtime.run_lifecycle.epoch_phase is EpochPhase.AUTONOMOUS
src/erre_sandbox/cli/eval_run_golden.py:547:            # ``individual_layer_enabled`` column is intentionally
src/erre_sandbox/cli/eval_run_golden.py:561:                ' "epoch_phase", "created_at")'
src/erre_sandbox/schemas.py:630:    epoch_phase: EpochPhase = EpochPhase.AUTONOMOUS
src/erre_sandbox/world/tick.py:423:        current = self._run_lifecycle.epoch_phase
src/erre_sandbox/world/tick.py:430:        self._run_lifecycle = RunLifecycleState(epoch_phase=EpochPhase.Q_AND_A)
src/erre_sandbox/world/tick.py:442:        current = self._run_lifecycle.epoch_phase
src/erre_sandbox/world/tick.py:449:        self._run_lifecycle = RunLifecycleState(epoch_phase=EpochPhase.EVALUATION)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:246:- [ ] raw_dialog metadata schema に `individual_layer_enabled: bool` field 追加 (default=false) [S]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:247:- [ ] training-view contract loader に AND 条件 (`evaluation_epoch=false AND individual_layer_enabled=false`) 追加 [S]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:248:- [ ] sentinel test: `individual_layer_enabled=true` の行が training-view から除外されること [S]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:249:- [ ] grep gate: training paths に `individual_layer_enabled=true` row が現れたら CI fail (既存 `metrics.` grep gate と同型) [S]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:250:- [ ] schema migration: 既存 raw_dialog (M9-A / M7ζ / 過去 run) を `individual_layer_enabled=false` で default 解釈する backfill [S]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:253:- [ ] training pipeline 入口で `assert all(row.metadata.individual_layer_enabled is False)`、contamination 検出時 fail-fast [S]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:257:- [ ] IndividualProfile activation 時に raw_dialog meta `individual_layer_enabled=true` を立てる責務を docstring に明示 [S] (M10-A scaffold task で追跡)
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:261:- [ ] `eval egress grep gate` job (既存 CI workflow) に `individual_layer_enabled=true` の検出を追加 [S]
.steering/20260430-m9-b-lora-execution-plan/tasklist.md:262:- [ ] training-view loader unit test を `[evaluation_epoch ∈ {true,false}] × [individual_layer_enabled ∈ {true,false}]` の 4 組合せ matrix で実行 [S]
src/erre_sandbox/bootstrap.py:531:                epoch_phase=runtime.run_lifecycle.epoch_phase,
src/erre_sandbox/evidence/tier_b/__init__.py:22:eval-only; the DB11 ``individual_layer_enabled`` raw-schema enforcement
src/erre_sandbox/evidence/scaling_metrics.py:553:       D5 (epoch_phase boundary, M7ε): only ``EpochPhase.AUTONOMOUS``
src/erre_sandbox/evidence/scaling_metrics.py:558:       ``epoch_phase`` and are treated as AUTONOMOUS for backward compat
src/erre_sandbox/evidence/scaling_metrics.py:570:            store.iter_dialog_turns(epoch_phase=EpochPhase.AUTONOMOUS),
src/erre_sandbox/evidence/eval_store.py:6:entry point is :func:`connect_training_view`, which opens a DuckDB file
src/erre_sandbox/evidence/eval_store.py:28:Both :func:`connect_training_view` and :func:`connect_analysis_view`
src/erre_sandbox/evidence/eval_store.py:84:    ("epoch_phase", "TEXT"),
src/erre_sandbox/evidence/eval_store.py:88:    ("individual_layer_enabled", "BOOLEAN NOT NULL DEFAULT FALSE"),
src/erre_sandbox/evidence/eval_store.py:184:        # B-1): ``connect_training_view()`` is the loader boundary
src/erre_sandbox/evidence/eval_store.py:187:        # ``epoch_phase=evaluation`` or a truthy / NULL
src/erre_sandbox/evidence/eval_store.py:188:        # ``individual_layer_enabled``. SQL aggregate is used (not a
src/erre_sandbox/evidence/eval_store.py:191:        # ``assert_phase_beta_ready``. The aggregate is skipped when
src/erre_sandbox/evidence/eval_store.py:193:        # cases are still picked up by ``assert_phase_beta_ready``
src/erre_sandbox/evidence/eval_store.py:197:        if "epoch_phase" in column_set and INDIVIDUAL_LAYER_ENABLED_KEY in column_set:
src/erre_sandbox/evidence/eval_store.py:200:                " COALESCE(SUM(CASE WHEN LOWER(epoch_phase) = 'evaluation'"
src/erre_sandbox/evidence/eval_store.py:211:                    f" carry epoch_phase~='evaluation' (case-insensitive)"
src/erre_sandbox/evidence/eval_store.py:263:def connect_training_view(db_path: str | Path) -> RawTrainingRelation:
src/erre_sandbox/evidence/eval_store.py:646:    "connect_training_view",
src/erre_sandbox/memory/store.py:213:                # M7ε (m7-slice-epsilon): adds ``epoch_phase`` so M8 ADR D5 /
src/erre_sandbox/memory/store.py:232:                        epoch_phase TEXT,
src/erre_sandbox/memory/store.py:311:        """Idempotently ensure ``dialog_turns`` carries the M7ε ``epoch_phase`` column.
src/erre_sandbox/memory/store.py:313:        M7ε (m7-slice-epsilon): adds ``epoch_phase`` (NULLable TEXT) so
src/erre_sandbox/memory/store.py:326:        if "epoch_phase" not in existing:

codex
One more repo rule matters here: the proposed new package/import location touches the project’s layer boundaries, so I’m checking the architecture skill before finalizing that finding.
exec
/bin/zsh -lc "sed -n '1,240p' .agents/skills/architecture-rules/SKILL.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
---
name: architecture-rules
description: >
  レイヤー依存方向・インポート制約・GPL/クラウド API 禁止ルール。
  src/erre_sandbox/ 配下に新しいファイルを追加する・インポートを変更する・
  新しい依存ライブラリを追加する時に必須参照。
  schemas.py / inference/ / memory/ / cognition/ / world/ / ui/ / erre/
  のどのモジュールにコードを置くか判断する時、
  import 文が依存方向に違反していないか確認する時、
  pip install / uv add でライブラリを追加する時に自動召喚される。
  GPL ライブラリ (bpy 等) を src/erre_sandbox/ に import する禁止も含む。
---

# Architecture Rules

## このスキルの目的

ERRE-Sandbox のアーキテクチャは 2 拠点 (G-GEAR + MacBook) × 5 レイヤー構成。
インポートの依存方向を守ることで、将来のバックエンド差し替え (Qdrant、gRPC 等) を
最小の変更で実現できるようにする。また、GPL ライブラリとクラウド API の混入を防ぐ。

## レイヤー依存方向（絶対厳守）

```
world/ → cognition/ → inference/
                    → memory/
                          ↓
ui/ ──────────→ schemas.py ← (全モジュールが参照)
```

| モジュール | 依存先 | 依存禁止 |
|---|---|---|
| `schemas.py` | なし (最下層) | すべての src モジュール |
| `inference/` | `schemas.py` のみ | `memory/`, `cognition/`, `world/`, `ui/` |
| `memory/` | `schemas.py` のみ | `inference/`, `cognition/`, `world/`, `ui/` |
| `cognition/` | `inference/`, `memory/`, `schemas.py`, `erre/` | `world/`, `ui/` |
| `world/` | `cognition/`, `schemas.py` | `ui/`, `erre/` |
| `ui/` | `schemas.py` のみ | `inference/`, `memory/`, `cognition/`, `world/` |
| `erre/` | `schemas.py`, `inference/`, `memory/` | `cognition/`, `world/`, `ui/` |

### 依存方向の確認方法

```bash
# ui/ が inference/ を import していないか確認
grep -r "from erre_sandbox.inference" src/erre_sandbox/ui/
grep -r "from erre_sandbox.memory"    src/erre_sandbox/ui/

# schemas.py が他モジュールを import していないか確認
grep "from erre_sandbox\." src/erre_sandbox/schemas.py
```

## 絶対禁止ルール

### 禁止 1: GPL ライブラリを src/erre_sandbox/ に import

Blender の `bpy` は GPL-2+ のため、import するコードが GPL 派生物になる。
Apache-2.0 OR MIT デュアルライセンスと矛盾するため **絶対に混入させない**。

```python
# ❌ 絶対禁止
import bpy                          # GPL viral — Apache/MIT と矛盾
from bpy.types import Object        # 同上
```

将来 Blender 連携が必要になった場合 → `erre-sandbox-blender/` を別パッケージ (GPL-3) で分離。

### 禁止 2: クラウド LLM API を必須依存にする

OpenAI / Anthropic / Google の API は予算ゼロ制約に反する。

```python
# ❌ 禁止
import openai                       # 有料 API
from anthropic import Anthropic     # 有料 API
```

ローカル推論 (SGLang / Ollama / llama.cpp) のみ使用。

### 禁止 3: ui/ から inference/ / memory/ を直接 import

UI は WebSocket 経由で G-GEAR と通信する。Python の import で直接呼ばない。

```python
# ❌ 禁止 — ui/ から memory/ を直接呼ぶ
from erre_sandbox.memory.store import MemoryStore  # ui/ 内に書いてはいけない

# ✅ 正しい — WebSocket 経由
from erre_sandbox.schemas import ControlEnvelope   # スキーマのみ OK
```

### 禁止 4: schemas.py から他の src モジュールを import

`schemas.py` は最下層。循環参照を防ぐために依存なしを厳守。

```python
# ❌ 禁止
from erre_sandbox.memory.store import MemoryStore  # schemas.py 内に書いてはいけない

# ✅ 正しい — 型ヒントのみなら TYPE_CHECKING で遅延
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from erre_sandbox.memory.store import MemoryStore
```

## 新しいファイルの配置判断フロー

```
新しい .py ファイルを作る
    │
    ├─ LLM 推論関連?           → inference/
    ├─ 記憶・検索・埋め込み?   → memory/
    ├─ 認知サイクル・反省?     → cognition/
    ├─ ワールド・物理・ゾーン? → world/
    ├─ WebSocket クライアント・Godot 連携? → ui/
    ├─ ERRE パイプライン DSL?  → erre/
    └─ Pydantic スキーマ定義?  → schemas.py に追記 (ファイルは作らない)
```

## 依存ライブラリ追加の基準

新しいライブラリを `uv add` する前に全項目確認:

- [ ] 既存の依存で代替できないか?
- [ ] ライセンスは Apache-2.0 / MIT / BSD と互換か? (**GPL は本体に入れない**)
- [ ] メンテナンスが活発か? (直近 6 ヶ月以内にリリースがあるか)
- [ ] セキュリティ脆弱性はないか?
- [ ] 予算ゼロに抵触しないか? (有料 SaaS の必須依存は不可)

## チェックリスト

- [ ] 新しいファイルが正しいレイヤー (`inference/`, `memory/` 等) に置かれているか
- [ ] インポートが依存方向に違反していないか (`grep` で確認)
- [ ] `schemas.py` から他の src モジュールを import していないか
- [ ] `ui/` から `inference/` や `memory/` を直接 import していないか
- [ ] GPL ライブラリが `src/erre_sandbox/` に入っていないか
- [ ] クラウド LLM API が必須依存になっていないか
- [ ] 新しい依存のライセンスが Apache-2.0/MIT/BSD と互換か

## 補足資料

- `decision-tree.md` — 「どのモジュールに書くべきか」の判断フロー詳細版

## 関連する他の Skill

- `python-standards` — インポート順序・相対 vs 絶対インポートのルール
- `implementation-workflow` — Step B (既存パターン調査) でこの Skill を参照
- `llm-inference` — inference/ 内のモデル設定と VRAM 管理
- `persona-erre` — ペルソナ YAML 設計と ERRE モード定義
- `godot-gdscript` — Godot シーン・GDScript のコーディング規約と WebSocket 通信
- `blender-pipeline` — Blender アセットパイプラインの GPL 分離の具体的手順

codex
## Verdict (1 行)
ADOPT-WITH-CHANGES — M10-0 scaffold 前に HIGH 5 件を design に反映する条件付き採用。

## HIGH (must-fix before M10-0 task scaffold 起票 — 最低 3 件、できれば 5 件)

- HIGH-1: Threshold preregister が preregister になっていない
  - Risk: `pairwise centroid distance` / `Vendi` / `big5_icc` が TBD のまま M10-0 close される設計だと、M11-C 直前に同じ観測データで閾値を選んで同じデータで成功判定する circular gate になる。`recovery_rate [0.4,0.9]` も predicted と recalibrate が混在しており falsifiability が弱い。
  - Mitigation: M10-0 close 条件を「数値を固定」または「calibration protocol を固定」に変える。最低限、calibration data / evaluation data split、bootstrap 手順、exclusion/degenerate rule、effect direction、CI rule、freeze date を `thresholds.md` に固定し、TBD という値ではなく `calibrate_before_unblinding` という状態で管理する。

- HIGH-2: DB11 contamination 防止が新 `individuation_metrics` table まで拡張されていない
  - Risk: 既存境界は `raw_dialog` と `metrics.tier_{a,b,c}` を前提にしているが、draft は独立 `individuation_metrics` table と `_audit_stimulus.json` summary key を追加する。CI grep gate は `metrics.` literal中心なので、新 table/schema 名が training egress の sentinel/grep/allow-list 防御を bypass しうる。
  - Mitigation: 新 table は独立 schema ではなく既存 `metrics` schema 配下、例 `metrics.individuation` に置くか、完全別 DuckDB artifact に分離する。さらに `metric_schema_version`, `source_table`, `source_run_id`, `source_epoch_phase`, `source_individual_layer_enabled`, `source_filter_hash`, `embedding_model_id` を持たせ、training-view sentinel test に `metrics.individuation` poison row を追加する。`_audit_stimulus.json` は audit metadata のままにし、training manifest input にしない。

- HIGH-3: Recovery protocol が ME-9 同型 false-positive を再導入する
  - Risk: `opposite-stance memory N=5 entries` を `retrieved_memories` に強制注入すると、M10-C の `cited_memory_ids ⊆ retrieved_memories` 検証を trivially pass する。これは「LLM が引用したから belief として採用」へ戻る構造で、DA-4 の free-form 自己宣言禁止をすり抜ける。
  - Mitigation: perturbation は memory ではなく `counterfactual_challenge` channel に隔離し、`WorldModelUpdateHint` adoption の evidence source として無効化する。測るのは出力・Burrows・SWM persistence のみで、perturbation tick 中の SWM write は禁止。negative control として「counterfactual memory id を cite しても merge されない」テストを必須にする。

- HIGH-4: Burrows / MeCab A2 が operationally invalid
  - Risk: 現行 `burrows.py` は Japanese tokenizer 未対応で `ja` は明示例外、かつ Burrows は function-word z-score L1 であり char n-gram ratio との ±0.05 一致は同一概念の回帰ではない。A1 の「全 metric valid float」と A3 の「N=1 degenerate」も矛盾する。
  - Mitigation: M10-0 では MeCab migration を外し、`MetricResult(status=valid|degenerate|unsupported, value=None|float, reason=...)` を導入する。Burrows は `en/de` 既存、`ja` は tokenizer/reference-corpus task へ分離。どうしても比較するなら ±0.05 ではなく rank correlation / bootstrap stability / dual-track report にする。

- HIGH-5: M9-eval Phase 2 capture compatibility が誤認されている
  - Risk: draft は `_audit_stimulus.json` / per-cell capture を Vendi/Big5 input として扱っているが、実ファイルは audit metadata であり utterance windows ではない。Tier B 実装は実際には `src/erre_sandbox/evidence/tier_b/` 配下で、draft の `src/erre_sandbox/eval/tier_b/` は存在しない。
  - Mitigation: M10-0 loader を `AnalysisView` + `raw_dialog.dialog` window extraction として設計し、sidecar JSON は integrity/audit のみ使用する。A4 は「15 golden DuckDB files の `raw_dialog.dialog` から utterance windows を抽出して Vendi が走る」に書き換える。

## MEDIUM (should consider, 採否は明示)

- MEDIUM-1: Adopt — activation / RepE は M12+ production defer でよいが、M10-0 で後続 spike 用の provenance fields は確保する。
- MEDIUM-2: Adopt — `cognitive_habit_recall_rate` / action adherence / zone-behavior consistency を追加。発話 embedding だけでは「認知習慣」ではなく文体寄りになる。
- MEDIUM-3: Adopt-with-changes — Big5 ICC は diagnostic only。現行 code も Japanese IPIP vendoring を deferred にしているため、M10-0 gate に入れない。
- MEDIUM-4: Adopt — semantic centroid / Vendi / Burrows の相関行列を M10-0 output に含め、同一 channel の二重測定を検出する。
- MEDIUM-5: Defer — WP4 MeCab は別 task。M10-0 は tokenizer interface と unsupported handling まで。
- MEDIUM-6: Adopt — cache benchmark は prompt prefix hash、system/user split token count、KV cache hit proxy、TTFT p50/p95 を含める。

## LOW (nit / optional)

- `ICC[2,1]` 表記は現行 `big5_icc.py` の `ICC(A,1)` / `ICC(C,k)` と対応が曖昧。
- `base individual` という語は二層設計上やや混乱する。`same-base individual` に寄せる。
- LOC 見積もりは楽観的。loader + schema + sentinel + golden integration で 1800 LOC を超える可能性が高い。

## reasoning-model-judgment.md 判定の妥当性 stress-test

1. Q1: "weight-level intervention M12+ defer" の妥当性  
   妥当。ただし「activation analysis も完全 M12+」は強すぎる。Anthropic Persona Vectors は会話中/訓練中の personality shift monitoring と mitigation を示す一方、post-hoc steering の capability side effect も報告している。M10/M11 では read-only/offline spike だけ許し、runtime steering/weight update は M12+ gate が妥当。

2. Q2: trait 抽出 = sidecar metric 化で表現力が失われていないか  
   一部失われている。補うべきは trait ontology と行動 channel: cognitive habit recall/action adherence、reasoning_trace structure、belief update behavior、retrieval sensitivity、social interaction stance。

3. Q3: §3.1 5 metrics は直交か  
   直交ではない。semantic centroid と Vendi は同じ embedding kernel 依存、belief_variance と SWM Jaccard は同じ belief substrate 依存。Burrows は base style専用に残し、divergence gate は少なくとも 2 independent channels を要求する。

4. Q4: M11-C gate 4 条件は十分か  
   不十分。CI/effect size、negative-control variants、shuffled-memory control、no-individual-layer ablation、adoption-rate CI、pre-frozen threshold が必要。

5. Q5: 不採用 5 項目の defer は永久 defer か empirical gate ありか  
   分けるべき。`cognitive_habits runtime overwrite` は permanent reject。`base+individual same LoRA` / SWM→post-training / RL は M12+ empirical gate。`人間らしさ RL` は direct objective としては reject、narrow behavioral reliability objective なら M12+ research only。

## m10-0-concrete-design-draft.md の stress-test

6. Q6: matrix 見落とし  
   `reasoning_trace` structural metrics、cognitive habit recall/action adherence、retrieval provenance quality、cross-agent echo/identity collapse、prompt-order/cache metrics、counterfactual recovery channel。

7. Q7: permanent layer が DB11 bypass しないか  
   現状では不十分。新 table/schema 名が既存 `metrics.` gate 外に出る危険がある。HIGH-2 の通り既存 `metrics` schema か別 artifact に固定する。

8. Q8: A2 / A3 妥当性  
   A2 は不妥当。MeCab Burrows と char n-gram は別物。A3 は方向性は正しいが、A1 の valid float と衝突するため typed degenerate result が必要。

9. Q9: TBD close は preregister 違反か  
   そのままなら違反。数値 TBD は不可。calibration protocol TBD なしなら可。

10. Q10: recovery protocol の再混入 risk  
   高い。forced memory は evidence ではなく attack vector。代替は `counterfactual_challenge` quarantine + no-write replay + cite-disabled negative control。

11. Q11: WP4 MeCab timing  
   M10-0 ではやらない。依存追加、辞書/license、reference corpus、既存 Burrows contract の全てに触るため別 task。

12. Q12: 見落とし risk  
   capture loader mismatch、new schema contamination、TBD circularity、N=3 low power、Japanese IPIP unavailable、MPNet Japanese weakness、reasoning_trace training leakage、golden DB mutation、cache benchmark observer effect、local compute budget。

## 関連 prior art (web_search 必須)

- [Representation Engineering](https://arxiv.org/abs/2310.01405): high-level representation monitoring/manipulation は研究として成立している。
- [Microsoft ICLR 2025 activation steering](https://www.microsoft.com/en-us/research/publication/improving-instruction-following-in-language-models-through-activation-steering/): inference-time activation steering は実用化方向に進展。
- [Anthropic Persona Vectors](https://www.anthropic.com/research/persona-vectors): persona shift monitoring/mitigation の根拠。ただし side effect があり、M10 production defer を支持。
- [Agent Identity Evals](https://arxiv.org/abs/2507.17257): identity persistence と perturbation recovery を測る枠組みは M10-0 に適合。
- [Persistent Personas? EACL 2026](https://aclanthology.org/2026.eacl-long.246/): long dialogues で persona fidelity が劣化するため、100+ round 型評価が必要。
- [Evaluating Goal Drift in LM Agents](https://ojs.aaai.org/index.php/AIES/article/view/36541): competing objectives under long context で drift が起きる。
- [Vendi Score](https://openreview.net/forum?id=g97OHbQyk1): kernel choice が metric 定義そのもの。
- [Qwen3 Embedding](https://qwenlm.github.io/blog/qwen3-embedding/) と [all-mpnet-base-v2](https://huggingface.co/sentence-transformers/all-mpnet-base-v2): Japanese/multilingual kernelは再検討余地あり。
- [Japanese Big Five short form](https://cir.nii.ac.jp/crid/1390001205078139904?lang=ja) / [Japanese NEO-FFI validation](https://journals.sagepub.com/doi/10.2466/pr0.2001.88.2.443): Big5 Japanese validationは存在するが、現行 IPIP-50-ja vendoringとは別問題。

## Final notes (個人プロジェクト scope + 予算ゼロ制約への警告含む)

M10-0 は必要。ただし今の draft は「metric harness」「DB contamination」「Japanese tokenizer」「recovery eval」「cache benchmark」を一度に抱えすぎている。個人開発・ローカル SGLang/Ollama・G-GEAR overnight 前提なら、M10-0 はまず loader/manifest/storage/degenerate handling/threshold protocol に絞るべき。

Activation/weight intervention は prior art 的には魅力があるが、ERRE の DB11 と base/individual 分離を壊すコストが高い。M10/M11 では測定器を作り、M12+ で初めて介入を疑う、という順序は防衛可能。
hook: Stop
hook: Stop Completed
2026-05-11T07:54:05.050484Z ERROR codex_core::session: failed to record rollout items: thread 019e1602-2ce7-7f32-aa63-8d1869a5aeed not found
tokens used
271,822
## Verdict (1 行)
ADOPT-WITH-CHANGES — M10-0 scaffold 前に HIGH 5 件を design に反映する条件付き採用。

## HIGH (must-fix before M10-0 task scaffold 起票 — 最低 3 件、できれば 5 件)

- HIGH-1: Threshold preregister が preregister になっていない
  - Risk: `pairwise centroid distance` / `Vendi` / `big5_icc` が TBD のまま M10-0 close される設計だと、M11-C 直前に同じ観測データで閾値を選んで同じデータで成功判定する circular gate になる。`recovery_rate [0.4,0.9]` も predicted と recalibrate が混在しており falsifiability が弱い。
  - Mitigation: M10-0 close 条件を「数値を固定」または「calibration protocol を固定」に変える。最低限、calibration data / evaluation data split、bootstrap 手順、exclusion/degenerate rule、effect direction、CI rule、freeze date を `thresholds.md` に固定し、TBD という値ではなく `calibrate_before_unblinding` という状態で管理する。

- HIGH-2: DB11 contamination 防止が新 `individuation_metrics` table まで拡張されていない
  - Risk: 既存境界は `raw_dialog` と `metrics.tier_{a,b,c}` を前提にしているが、draft は独立 `individuation_metrics` table と `_audit_stimulus.json` summary key を追加する。CI grep gate は `metrics.` literal中心なので、新 table/schema 名が training egress の sentinel/grep/allow-list 防御を bypass しうる。
  - Mitigation: 新 table は独立 schema ではなく既存 `metrics` schema 配下、例 `metrics.individuation` に置くか、完全別 DuckDB artifact に分離する。さらに `metric_schema_version`, `source_table`, `source_run_id`, `source_epoch_phase`, `source_individual_layer_enabled`, `source_filter_hash`, `embedding_model_id` を持たせ、training-view sentinel test に `metrics.individuation` poison row を追加する。`_audit_stimulus.json` は audit metadata のままにし、training manifest input にしない。

- HIGH-3: Recovery protocol が ME-9 同型 false-positive を再導入する
  - Risk: `opposite-stance memory N=5 entries` を `retrieved_memories` に強制注入すると、M10-C の `cited_memory_ids ⊆ retrieved_memories` 検証を trivially pass する。これは「LLM が引用したから belief として採用」へ戻る構造で、DA-4 の free-form 自己宣言禁止をすり抜ける。
  - Mitigation: perturbation は memory ではなく `counterfactual_challenge` channel に隔離し、`WorldModelUpdateHint` adoption の evidence source として無効化する。測るのは出力・Burrows・SWM persistence のみで、perturbation tick 中の SWM write は禁止。negative control として「counterfactual memory id を cite しても merge されない」テストを必須にする。

- HIGH-4: Burrows / MeCab A2 が operationally invalid
  - Risk: 現行 `burrows.py` は Japanese tokenizer 未対応で `ja` は明示例外、かつ Burrows は function-word z-score L1 であり char n-gram ratio との ±0.05 一致は同一概念の回帰ではない。A1 の「全 metric valid float」と A3 の「N=1 degenerate」も矛盾する。
  - Mitigation: M10-0 では MeCab migration を外し、`MetricResult(status=valid|degenerate|unsupported, value=None|float, reason=...)` を導入する。Burrows は `en/de` 既存、`ja` は tokenizer/reference-corpus task へ分離。どうしても比較するなら ±0.05 ではなく rank correlation / bootstrap stability / dual-track report にする。

- HIGH-5: M9-eval Phase 2 capture compatibility が誤認されている
  - Risk: draft は `_audit_stimulus.json` / per-cell capture を Vendi/Big5 input として扱っているが、実ファイルは audit metadata であり utterance windows ではない。Tier B 実装は実際には `src/erre_sandbox/evidence/tier_b/` 配下で、draft の `src/erre_sandbox/eval/tier_b/` は存在しない。
  - Mitigation: M10-0 loader を `AnalysisView` + `raw_dialog.dialog` window extraction として設計し、sidecar JSON は integrity/audit のみ使用する。A4 は「15 golden DuckDB files の `raw_dialog.dialog` から utterance windows を抽出して Vendi が走る」に書き換える。

## MEDIUM (should consider, 採否は明示)

- MEDIUM-1: Adopt — activation / RepE は M12+ production defer でよいが、M10-0 で後続 spike 用の provenance fields は確保する。
- MEDIUM-2: Adopt — `cognitive_habit_recall_rate` / action adherence / zone-behavior consistency を追加。発話 embedding だけでは「認知習慣」ではなく文体寄りになる。
- MEDIUM-3: Adopt-with-changes — Big5 ICC は diagnostic only。現行 code も Japanese IPIP vendoring を deferred にしているため、M10-0 gate に入れない。
- MEDIUM-4: Adopt — semantic centroid / Vendi / Burrows の相関行列を M10-0 output に含め、同一 channel の二重測定を検出する。
- MEDIUM-5: Defer — WP4 MeCab は別 task。M10-0 は tokenizer interface と unsupported handling まで。
- MEDIUM-6: Adopt — cache benchmark は prompt prefix hash、system/user split token count、KV cache hit proxy、TTFT p50/p95 を含める。

## LOW (nit / optional)

- `ICC[2,1]` 表記は現行 `big5_icc.py` の `ICC(A,1)` / `ICC(C,k)` と対応が曖昧。
- `base individual` という語は二層設計上やや混乱する。`same-base individual` に寄せる。
- LOC 見積もりは楽観的。loader + schema + sentinel + golden integration で 1800 LOC を超える可能性が高い。

## reasoning-model-judgment.md 判定の妥当性 stress-test

1. Q1: "weight-level intervention M12+ defer" の妥当性  
   妥当。ただし「activation analysis も完全 M12+」は強すぎる。Anthropic Persona Vectors は会話中/訓練中の personality shift monitoring と mitigation を示す一方、post-hoc steering の capability side effect も報告している。M10/M11 では read-only/offline spike だけ許し、runtime steering/weight update は M12+ gate が妥当。

2. Q2: trait 抽出 = sidecar metric 化で表現力が失われていないか  
   一部失われている。補うべきは trait ontology と行動 channel: cognitive habit recall/action adherence、reasoning_trace structure、belief update behavior、retrieval sensitivity、social interaction stance。

3. Q3: §3.1 5 metrics は直交か  
   直交ではない。semantic centroid と Vendi は同じ embedding kernel 依存、belief_variance と SWM Jaccard は同じ belief substrate 依存。Burrows は base style専用に残し、divergence gate は少なくとも 2 independent channels を要求する。

4. Q4: M11-C gate 4 条件は十分か  
   不十分。CI/effect size、negative-control variants、shuffled-memory control、no-individual-layer ablation、adoption-rate CI、pre-frozen threshold が必要。

5. Q5: 不採用 5 項目の defer は永久 defer か empirical gate ありか  
   分けるべき。`cognitive_habits runtime overwrite` は permanent reject。`base+individual same LoRA` / SWM→post-training / RL は M12+ empirical gate。`人間らしさ RL` は direct objective としては reject、narrow behavioral reliability objective なら M12+ research only。

## m10-0-concrete-design-draft.md の stress-test

6. Q6: matrix 見落とし  
   `reasoning_trace` structural metrics、cognitive habit recall/action adherence、retrieval provenance quality、cross-agent echo/identity collapse、prompt-order/cache metrics、counterfactual recovery channel。

7. Q7: permanent layer が DB11 bypass しないか  
   現状では不十分。新 table/schema 名が既存 `metrics.` gate 外に出る危険がある。HIGH-2 の通り既存 `metrics` schema か別 artifact に固定する。

8. Q8: A2 / A3 妥当性  
   A2 は不妥当。MeCab Burrows と char n-gram は別物。A3 は方向性は正しいが、A1 の valid float と衝突するため typed degenerate result が必要。

9. Q9: TBD close は preregister 違反か  
   そのままなら違反。数値 TBD は不可。calibration protocol TBD なしなら可。

10. Q10: recovery protocol の再混入 risk  
   高い。forced memory は evidence ではなく attack vector。代替は `counterfactual_challenge` quarantine + no-write replay + cite-disabled negative control。

11. Q11: WP4 MeCab timing  
   M10-0 ではやらない。依存追加、辞書/license、reference corpus、既存 Burrows contract の全てに触るため別 task。

12. Q12: 見落とし risk  
   capture loader mismatch、new schema contamination、TBD circularity、N=3 low power、Japanese IPIP unavailable、MPNet Japanese weakness、reasoning_trace training leakage、golden DB mutation、cache benchmark observer effect、local compute budget。

## 関連 prior art (web_search 必須)

- [Representation Engineering](https://arxiv.org/abs/2310.01405): high-level representation monitoring/manipulation は研究として成立している。
- [Microsoft ICLR 2025 activation steering](https://www.microsoft.com/en-us/research/publication/improving-instruction-following-in-language-models-through-activation-steering/): inference-time activation steering は実用化方向に進展。
- [Anthropic Persona Vectors](https://www.anthropic.com/research/persona-vectors): persona shift monitoring/mitigation の根拠。ただし side effect があり、M10 production defer を支持。
- [Agent Identity Evals](https://arxiv.org/abs/2507.17257): identity persistence と perturbation recovery を測る枠組みは M10-0 に適合。
- [Persistent Personas? EACL 2026](https://aclanthology.org/2026.eacl-long.246/): long dialogues で persona fidelity が劣化するため、100+ round 型評価が必要。
- [Evaluating Goal Drift in LM Agents](https://ojs.aaai.org/index.php/AIES/article/view/36541): competing objectives under long context で drift が起きる。
- [Vendi Score](https://openreview.net/forum?id=g97OHbQyk1): kernel choice が metric 定義そのもの。
- [Qwen3 Embedding](https://qwenlm.github.io/blog/qwen3-embedding/) と [all-mpnet-base-v2](https://huggingface.co/sentence-transformers/all-mpnet-base-v2): Japanese/multilingual kernelは再検討余地あり。
- [Japanese Big Five short form](https://cir.nii.ac.jp/crid/1390001205078139904?lang=ja) / [Japanese NEO-FFI validation](https://journals.sagepub.com/doi/10.2466/pr0.2001.88.2.443): Big5 Japanese validationは存在するが、現行 IPIP-50-ja vendoringとは別問題。

## Final notes (個人プロジェクト scope + 予算ゼロ制約への警告含む)

M10-0 は必要。ただし今の draft は「metric harness」「DB contamination」「Japanese tokenizer」「recovery eval」「cache benchmark」を一度に抱えすぎている。個人開発・ローカル SGLang/Ollama・G-GEAR overnight 前提なら、M10-0 はまず loader/manifest/storage/degenerate handling/threshold protocol に絞るべき。

Activation/weight intervention は prior art 的には魅力があるが、ERRE の DB11 と base/individual 分離を壊すコストが高い。M10/M11 では測定器を作り、M12+ で初めて介入を疑う、という順序は防衛可能。

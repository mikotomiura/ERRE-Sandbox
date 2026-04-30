# M9-B LoRA execution plan — 量子化戦略 + 評価系 framework + 10 軸 ADR 確定

## 背景

M7-α〜ζ で関係性ループ + persona divergence + live observation tooling が揃い、
M9-A (event-boundary-observability、PR #117-#124) で zone pulse / TRIGGER 観測も
live G-GEAR で 6/6 PASS。M9 の入口として `m9-lora-pre-plan` (PR #110, 2026-04-28
merged) で 5 ADR (D1-D5) を /reimagine hybrid で確定したが、以下が未決のまま:

1. **post-merge 12 実行項目** (vLLM `--enable-lora` 起動 / PEFT vs unsloth spike /
   Parquet pipeline / dataset 結合 schema / N=4 VRAM 実測 / evaluation epoch /
   adapter swap runbook 等)
2. **QLoRA / 量子化戦略** — memory `project_m9_pre_plan` で「次回計画で明示」と保留
3. **思想家らしさの評価系 framework** — Evidence Layer 既存指標
   (repetition_rate / cross_persona_echo_rate) は劣化検知の **守備指標** のみ。
   思想的深度 / 一貫性 / 対話の非自明性 を測る **攻めの指標** が ζ 時点でも
   未定義。LoRA 適用の go-no-go gate が論理的に成立しない構造的欠落

M9-B はこれら未決事項を確定し、実装着手 (M9-C 以降) の go-no-go gate を作る。

高難度設計 (アーキテクチャ判断 + 公開 API 影響 + 複数案ありうる) のため、
CLAUDE.md ルール上 **Plan mode + /reimagine + Codex independent review** が必須。

## ゴール

M9-B の plan セッション完了時点で、以下が
`.steering/20260430-m9-b-lora-execution-plan/` に揃っていること:

1. `design-final.md`: 10 軸 (A-J) すべてに採用案 + 根拠 + 代替案棄却理由
2. `/reimagine` 痕跡: `design-v1.md` (初回案、破棄) + `design-v2.md` (再生成、
   v2-B「評価基盤先行」を仮アンチテーゼ) + `design-comparison.md`
3. Codex independent review: `codex-review-prompt.md` + `codex-review.md` (verbatim、
   要約禁止) が存在、HIGH 全反映 / MEDIUM 採否を `decisions.md` / LOW を
   `blockers.md` に defer 理由付きで記録
4. `decisions.md`: 10 ADR (DB1-DB10) が 5 要素 (決定 / 根拠 / 棄却 / 影響 /
   re-open 条件) で記録
5. `tasklist.md`: M9-C / M9-eval-system 着手 tasklist が dependency 順 + 工数
   (S/M/L) + 先決 ADR 紐付きで並ぶ
6. **数値 gate** が文書化: dataset trigger 閾値 / baseline drift gate / VRAM gate /
   攻めの gate (J5)
7. `research-evaluation-metrics.md`: 既存評価指標 ≥ 6 系統 (persona consistency /
   LLM-as-judge / ToM / philosophical depth / cognitive trait / diversity) を
   出典付きで整理
8. `git diff src/ godot_project/` が空 (planning purity)
9. Plan→Clear→Execute ハンドオフ準備: `design-final.md` が /clear 後でも独立 Read
   可能な体裁

本セッションでは Plan までを完成させ、実装は別タスクで切る (M9-C 以降)。

## スコープ

### 含むもの (10 軸)

- **A. 量子化戦略**: QLoRA(4bit) / LoRA(FP16) / INT8+LoRA 選定。G-GEAR 16GB +
  qwen3:8b + 3 persona swap の VRAM 試算 (numeric estimate 付き)
- **B. Library 選定**: PEFT vs unsloth 比較軸 + spike 実施判断 (rank=8 統一)
- **C. Serving 移行判断**: 現行 SGLang/Ollama → vLLM `--enable-lora` 移行 vs
  SGLang LoRA 待ち vs ハイブリッド (推論は SGLang 維持 + LoRA は vLLM)
- **D. Dataset trigger 閾値**: dialog_turn ≥500/persona / divergence ratio
  (ζ 36:74:16 起点) / baseline floor (self_rep≤0.10 等) の 3 軸の OR/AND と
  具体数値
- **E. Parquet export schema**: episodic_log + dialog_turn + reasoning_trace
  結合 schema + 必須/任意 + persona_id partition 戦略
- **F. 評価 epoch 分離**: autonomous (training input) / evaluation
  (annotation only) の Run-level flag + ログ汚染ゼロ保証メカニズム
- **G. Persona N=4 拡張時期**: agora 主体 (4 人目候補) を M9-B 中追加 / M10 /
  別軸 のいずれにするか + VRAM 実測 gate
- **H. Adapter swap runbook**: vLLM hot swap latency / cold start / SGLang 互換
  API ラッパ / failover 手順
- **I. Baseline drift gate**: LoRA 適用後 self_rep / cross_echo / divergence の
  劣化判定閾値 + 自動 rollback トリガ
- **J. 思想家らしさの評価系 framework**:
  - **J0**: 既存評価指標の文献調査 (Persona consistency / LLM-as-judge / ToM /
    philosophical depth / cognitive trait / diversity) を出典付きで整理
  - **J1**: 評価次元定義 (思想的深度 / 内部一貫性 / 対話的非自明性 /
    persona-fit / 概念連結性)
  - **J2**: 定量化手法選定 (LLM-as-judge / embedding 類似度 / golden set 比較 /
    概念グラフ ratio / 人間 annotator)
  - **J3**: golden set の必要性判断
  - **J4**: 最低 baseline 採取方針 (LoRA 適用前現在値を floor 記録)
  - **J5**: 攻めの gate 定義 (D1 hybrid 守りに加え n% 改善要求 vs floor 維持)
  - **J6**: 評価系の実装は **M9-eval-system (新タスク)** に切り出す

### 含まないもの

1. `src/` および `godot_project/` への変更 (planning purity)
2. 評価系の実装 (judge prompt / golden set / 自動化 dashboard) → M9-eval-system
3. LoRA 実装本体 (vLLM 起動 / spike 実行 / Parquet 実装 / adapter 学習) → M9-C
4. Persona N=4 の actual 追加 (4 人目 YAML 起草 / persona 実装) — 判断のみ
5. Serving migration の実行作業 (C 軸では決定のみ、実装別タスク)
6. golden set の収集 (必要性判断のみ)
7. 並行 scaffold タスクへの介入 (godot-ws-keepalive 等)

## 受け入れ条件

- [ ] `design-final.md` に 10 軸 (A-J) の採用案 / 棄却案 / 根拠が記録
- [ ] `research-evaluation-metrics.md` に既存評価指標 ≥ 6 系統が出典付きで整理
- [ ] `/reimagine` 痕跡 (`design-v1.md` + `design-v2.md` + `design-comparison.md`)
      が独立して存在
- [ ] Codex independent review 完了 (`codex-review-prompt.md` +
      `codex-review.md` verbatim)、HIGH 全反映 / MEDIUM 採否記録 / LOW defer 記録
- [ ] `decisions.md` に 10 ADR (DB1-DB10) が 5 要素で記録
- [ ] `tasklist.md` に M9-C / M9-eval-system 着手用 implementation tasklist が
      dependency 順 + 工数 + 先決 ADR 付きで並ぶ
- [ ] 数値 gate (dataset trigger / baseline drift / VRAM / 攻めの gate) 文書化
- [ ] `git diff src/ godot_project/` が空
- [ ] Plan→Clear→Execute ハンドオフ準備完了

## 関連ドキュメント

- `.steering/20260428-m9-lora-pre-plan/decisions.md` (D1-D5 ADR、本タスクの前提)
- `.steering/20260428-m9-lora-pre-plan/design.md` (defer-and-measure 方法論)
- `.steering/20260425-m8-baseline-quality-metric/design.md` L133 (Parquet pipeline 言及)
- `.steering/20260426-m7-slice-zeta-live-resonance/observation.md` (ζ-3 36:74:16 cadence)
- `.steering/20260426-m7-slice-zeta-live-resonance/observation.md` Reconnect-loop 節
- `docs/architecture.md` (LoRA / serving 統合先)
- `docs/development-guidelines.md` (Plan→Clear→Execute ハンドオフ規則)
- `CLAUDE.md` (Codex 連携 workflow、`feedback_active_codex_use`)
- memory `project_session_eod_2026_04_30` (M9-B 第 1 候補指定)
- memory `project_m9_pre_plan` (QLoRA/量子化戦略の defer 明示)

## 運用メモ

- 破壊と構築（/reimagine）適用: **Yes**
- 理由: アーキテクチャ判断 (serving migration / library 選定) + 公開 API 影響
  (Parquet schema / adapter swap runbook) + 複数案ありうる設計 (10 軸全て) +
  高難度判定 (CLAUDE.md gate 該当)。v2 アンチテーゼ仮説: 「評価基盤先行
  (LoRA 適用前に J 軸を確立)」を v2-B として立てる
- Codex independent review: **Yes** (memory `feedback_active_codex_use`)
- タスク種別: その他 (pure planning / decision-making)
- 後続タスク: M9-eval-system (新規) → M9-C (LoRA 実装)

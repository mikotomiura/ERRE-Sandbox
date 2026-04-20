# m5-planning — M5 マイルストーン計画策定

## 背景

M4 (multi-agent reflection + dialog + orchestrator) は 2026-04-20 に live 検証を含め
完全クローズし、`v0.2.0-m4` タグを付与済。3 エージェント (Kant / Nietzsche / Rikyū)
が並列走行、semantic memory + reflection の cycle は安定。ただし以下 2 点が未達:

1. **dialog_turn の LLM 生成**: M4 で `DialogTurnMsg` schema と gateway/Godot signal 経路は
   freeze 済だが、**発話生成ロジックと Godot 消費側が未実装**。M4 acceptance で
   「M5 で LLM 接続時に実装する」と明記されている。
2. **ERRE mode FSM**: MASTER-PLAN §5 の M5 定義「ERRE モード 6 種切替 + サンプリング切替」。
   現状は `_ZONE_TO_DEFAULT_ERRE_MODE` の static map で mode が固定され、
   zone entry 以外の event-driven 遷移が無い。

この 2 軸を **両輪** として M5 で回収する。両輪の設計判断・実装順序・acceptance 条件を
一塊の planning artifact として確定させ、以降の sub-task 群 (9 本) のキックオフを整える。

## ゴール

`.steering/20260420-m5-planning/` に /reimagine 作法の設計資産 (design-v1.md /
design-comparison.md / design.md / decisions.md / tasklist.md) を完成させ、
M5 の実装順序と acceptance 条件、rollback 計画を確定させる。planning 成果物の完成
をもって `m5-llm-spike` → `m5-contracts-freeze` → 並列 4 本 → 統合 → live 検証の
一連の sub-task に着手できる状態にする。

## スコープ

### 含むもの

- **M5 scope 確定** (ERRE mode FSM + dialog_turn LLM 生成 両輪、ユーザー決定済)
- **schema `0.3.0-m5` bump の具体的フィールド仕様** (追加 field / Protocol)
- **9 sub-task の責務分解と依存グラフ** (critical path 明示)
- **LLM プロンプト設計方針** (spike で固める項目の事前列挙)
- **Godot 視覚化の実装粒度** (bubble / mode tint / zone scene 追加)
- **Live acceptance 7 項目の仕様** (M4 と同形式)
- **Feature flag 設計** (`--disable-erre-fsm` / `--disable-dialog-turn` / `--disable-mode-sampling`)
- **/reimagine 2 案比較** (Contract-First 水平 vs Risk-First 垂直 → hybrid 採用)

### 含まないもの

- **実コードの変更**: 本タスクは planning のみ。schema bump / FSM / TurnGenerator 等の
  実装は各 sub-task branch (`feature/m5-*`) で行う
- **M6 以降のスコープ決定**: dialog のサンプリング動的制御 / procedural memory decay /
  Godot AnimationPlayer 本格化などは M5 の範囲外
- **persona YAML の新規作成**: 3 体 (Kant/Nietzsche/Rikyū) 固定、M5 で偉人追加はしない

## 受け入れ条件

- [ ] `.steering/20260420-m5-planning/design.md` に採用 hybrid 案の確定設計が記述される
- [ ] `.steering/20260420-m5-planning/design-v1.md` に初回 Contract-First 単独案 (案 A) が残る
- [ ] `.steering/20260420-m5-planning/design-comparison.md` に案 A / 案 B / hybrid の比較表が記述される
- [ ] `.steering/20260420-m5-planning/decisions.md` に scope / schema bump / reimagine 適用などの
      ユーザー決定と根拠が列挙される
- [ ] `.steering/20260420-m5-planning/tasklist.md` に 9 sub-task (llm-spike / contracts-freeze /
      erre-mode-fsm / erre-sampling-override-live / dialog-turn-generator / world-zone-triggers /
      godot-zone-visuals / orchestrator-integration / acceptance-live) のチェックボックスがある
- [ ] `v0.3.0-m5` schema の追加フィールド仕様が design.md に明記される
  (Cognitive.dialog_turn_budget / DialogTurnMsg.turn_index / DialogCloseMsg.reason=exhausted /
   ERREModeTransitionPolicy + DialogTurnGenerator Protocol)
- [ ] Live acceptance 7 項目の PASS 基準 + evidence 名が明記される
- [ ] Feature flag 3 種と各 OFF 挙動が明記される

## 関連ドキュメント

- `/Users/johnd/.claude/plans/async-petting-moon.md` (本 planning の承認済 plan)
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §5 (M5 originally scoped)
- `.steering/20260420-m4-planning/design.md` (M4 の Contract-First パターン = 参考テンプレート)
- `.steering/20260420-m4-acceptance-live/acceptance.md` (M4 acceptance 形式)
- `.claude/skills/persona-erre/SKILL.md` §ルール 2 + ルール 5 (ERRE mode delta table / zone-mode map)
- `src/erre_sandbox/schemas.py` (0.2.0-m4 の凍結状態)
- `src/erre_sandbox/integration/dialog.py` (InMemoryDialogScheduler 既存実装)
- `src/erre_sandbox/cognition/reflection.py:190` (TurnGenerator 実装の手本)

## 運用メモ

- **タスク種別**: その他 (planning / design 専用タスク。実装は各 sub-task branch で実施)
- **破壊と構築 (/reimagine) 適用**: **Yes**
  - 理由: ユーザー明示決定 (scope 確認時の質問 2 で「M5 planning 全体に適用」Recommended を選択)。
    加えて memory `feedback_reimagine_scope.md` の「content curation も対象、迷ったら適用」ルールに準拠。
    dialog_turn と ERRE mode FSM の両輪同時導入は public contract (schema) を更新する
    アーキテクチャ判断を含むため、初回案を意図的に破棄して代替案 (Risk-First Vertical Slicing)
    を並べ、比較後に hybrid (Contract-First + LLM Spike 先行) を採用する流れを踏む。
- **Plan 承認**: `/Users/johnd/.claude/plans/async-petting-moon.md` で ExitPlanMode 承認済

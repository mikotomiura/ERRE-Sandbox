# タスクリスト — M5 Planning

## 計画策定 (本タスク)

- [x] MASTER-PLAN §5 + M4 acceptance の scope 不整合を確認
- [x] /reimagine 作法で 2 案 (Contract-First / Risk-First) を起草
- [x] 案 A / 案 B / hybrid の比較を文書化 (`design-comparison.md`)
- [x] 採用案 (hybrid) を確定 (`design.md`)
- [x] ユーザー決定を記録 (`decisions.md`)
- [x] 本タスクリストを整備

## 計画承認後の次アクション

### Phase 0: LLM Spike (throwaway, 0.5 日)

- [ ] `/start-task m5-llm-spike` で `.steering/20260420-m5-llm-spike/` を作成
- [ ] Kant ↔ Rikyū の 1-on-1 対話を G-GEAR 実機で ad-hoc script 走らせる (コード commit しない)
- [ ] spike 結果を `decisions.md` に記述:
  - utterance 長の経験値 (例: num_predict=80 で 160 chars 以内に収まるか)
  - 停止語彙 (stop tokens) の選定
  - 適切 temperature 帯 (persona.default + ERRE delta が破綻しない範囲)
  - turn_index 上限 (6 が適切か、長すぎ/短すぎ)
  - 幻覚パターンと対策 (相手名の誤生成、無限繰返し、stage direction 混入)

### Phase 1: Contracts Freeze (直列, 0.5-1 日)

- [ ] `/start-task m5-contracts-freeze` + `feature/m5-contracts-freeze` branch
- [ ] `src/erre_sandbox/schemas.py` に `SCHEMA_VERSION="0.3.0-m5"` 反映
- [ ] `Cognitive.dialog_turn_budget: int = Field(default=6, ge=0)` 追加
- [ ] `DialogTurnMsg.turn_index: int = Field(..., ge=0)` 追加
- [ ] `DialogCloseMsg.reason` literal に `"exhausted"` 追加
- [ ] `ERREModeTransitionPolicy` + `DialogTurnGenerator` Protocol interface-only 追加
- [ ] `fixtures/control_envelope/*` 再生成
- [ ] `tests/schema_golden/*.schema.json` 再生成
- [ ] `conftest.py` の `agent_state_factory` で `dialog_turn_budget` default
- [ ] `uv run pytest -q` で 既存 525 test + 新 fixture PASS
- [ ] PR 作成 → review → merge

### Phase 2: 並列 4 本 (並列, 1-2 日 each)

Phase 1 merge 後、G-GEAR と MacBook 側で分担:

- [ ] `/start-task m5-erre-mode-fsm` — G-GEAR 側 (認知ロジック)
- [ ] `/start-task m5-erre-sampling-override-live` — G-GEAR 側 (LLM サンプリング)
- [ ] `/start-task m5-dialog-turn-generator` — G-GEAR 側 (LLM 対話生成) ← **核心**
- [ ] `/start-task m5-godot-zone-visuals` — MacBook 側 (Godot)

各 sub-task で `feature/m5-<name>` branch → PR → merge。

### Phase 3: 統合 (直列)

- [ ] `/start-task m5-world-zone-triggers` (FSM merge 後、0.5-1 日)
- [ ] `/start-task m5-orchestrator-integration` (全並列 merge 後、1 日)
  - [ ] `bootstrap.py` で FSM + TurnGenerator wiring
  - [ ] `__main__.py` に feature flag 3 種追加
  - [ ] integration test 拡張

### Phase 4: Live Acceptance (直列、0.5 日)

- [ ] `/start-task m5-acceptance-live`
- [ ] G-GEAR 側で `uv run erre-sandbox --personas kant,nietzsche,rikyu` 起動
- [ ] MacBook 側で Godot 接続、60s 録画
- [ ] Live Acceptance 7 項目の evidence 収集:
  - [ ] #1 `/health` schema_version=0.3.0-m5
  - [ ] #2 3-agent walking 60s
  - [ ] #3 ERRE mode FSM 遷移 + sampling delta 反映
  - [ ] #4 dialog_turn LLM 生成 (N≥3 turn, turn_index 単調増加)
  - [ ] #5 Godot dialog bubble 表示
  - [ ] #6 Godot ERRE mode tint 変化
  - [ ] #7 Reflection 回帰なし
- [ ] `acceptance.md` に 7 項目 PASS/FAIL まとめ
- [ ] 全 PASS 確認後、ユーザーに `v0.3.0-m5` タグ付与を確認

## 本タスク (m5-planning) の完了処理

- [ ] design.md / design-v1.md / design-comparison.md / decisions.md / tasklist.md / requirement.md の最終チェック
- [ ] `feature/m5-planning` branch で commit
- [ ] PR 作成 → review → merge
- [ ] MEMORY.md に M5 planning への参照追加 (必要なら)

## 制約・リマインダ

- 予算ゼロ (cloud LLM 禁止)
- `main` 直 push 禁止、全変更は feature branch + PR
- 既存 525 test に回帰なし
- GPL ライブラリを `src/erre_sandbox/` に import しない
- `.steering/` 記録は省略せず、各 sub-task で `/start-task` から始める

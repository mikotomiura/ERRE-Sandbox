# 設計 v1 — M5 Contract-First 水平分解 (破棄された初回案)

> **/reimagine 作法**: 本ファイルは初回設計案 (案 A) を残すための痕跡。
> 最終採用は `design.md` (hybrid)、比較は `design-comparison.md` を参照。

## 方針

M4 で確立した Contract-First 水平分解を M5 の 3 新軸 (Mode / Dialog / Visuals) に
再適用する。Phase 1 schema freeze → Phase 2 並列 → Phase 3 integration → Phase 4
live acceptance を踏襲。軸ごとに独立抽象を導入し contract を最小化して並列度を最大化。

## 3 新軸

| Axis | 名前 | 責務 | 主な層 |
|---|---|---|---|
| **M** | Mode transition (Static → FSM) | 静的 `_ZONE_TO_DEFAULT_ERRE_MODE` を event-driven FSM に置換。sampling override を live で反映 | schemas / world / cognition / inference |
| **D** | Dialog turn (LLM generation) | dialog_initiate 後に LLM で turn を生成し、record_turn + envelope emit + close 判定まで完走 | inference / cognition / integration/dialog / gateway |
| **V** | Visual feedback (Godot) | ERRE mode 視覚化 + dialog bubble を 30Hz 描画。`dialog_turn_received` signal 消費 | godot_project/scripts & scenes |

## サブタスク分解 (7 本)

1. `m5-contracts-freeze` (foundation, 直列, 最初必須, 0.5-1 日)
2. `m5-erre-mode-fsm` (Axis M logic, 並列可, 1-2 日)
3. `m5-erre-sampling-override-live` (Axis M infra, 並列可, 0.5-1 日)
4. `m5-dialog-turn-generator` (Axis D core, 並列可, 1.5-2 日)
5. `m5-world-zone-triggers` (Axis M integration, 直列 #2 後, 0.5-1 日)
6. `m5-godot-zone-visuals` (Axis V, 並列可, 1-2 日)
7. `m5-orchestrator-integration` (Phase 3 最終, 直列, 1 日)

## 依存グラフ

```
                [m5-contracts-freeze]
                        │
    ┌──────────┬────────┼──────────┬─────────┐
    ↓          ↓        ↓          ↓         ↓
 erre-       erre-    dialog-    godot-    (並列 4 本)
 mode-fsm   sampling  turn-      zone-
            override  generator  visuals
    │                    │
    ↓                    │
 world-zone-             │
 triggers                │
    │                    │
    └─────────┬──────────┘
              ↓
    [m5-orchestrator-integration]
              ↓
    [M5 acceptance live 検証]
```

**Critical Path**: `contracts-freeze → erre-mode-fsm → world-zone-triggers → orchestrator → live` ≒ 4-6 日。
並列 4 本が critical path を圧迫しない。

## Testing Strategy (案 v1)

- **unit**: `tests/test_erre/test_fsm.py` (新規)、`tests/test_integration/test_dialog_turn.py` (新規)、
  `tests/test_inference/test_sampling_live.py` (拡張)
- **integration**: `tests/test_integration/test_m5_e2e.py` で manual clock + mocked Ollama で 60s 分 simulate
- **live**: G-GEAR 実機 + MacBook Godot 録画、7 項目 acceptance

## 本案の弱点 (比較で顕在化、hybrid へ移行)

1. **LLM プロンプト品質リスクが integration 時点まで可視化されない**。dialog_turn
   が persona + ERRE mode + 対話履歴を混ぜて破綻せず会話するかは mock では検証できず、
   `m5-orchestrator-integration` の live 段階で初めて判明する。手戻り発生時の影響範囲が大きい。
2. `m5-contracts-freeze` の schema 決定 (例: `DialogTurnMsg.turn_index` の要否、
   `dialog_turn_budget` の初期値) が **実機フィードバック無しに確定** されるため、
   後続 sub-task で schema 再 bump が必要になるリスクがある。

この弱点を踏まえ、案 B (Risk-First Vertical Slicing) を対抗案として起草し、
最終的に hybrid 採用 → `design.md` に確定。

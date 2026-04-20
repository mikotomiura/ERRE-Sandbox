# 設計 — m5-contracts-freeze

## 実装アプローチ

`.steering/20260420-m5-planning/design.md` §Schema 0.3.0-m5 追加内容 に列挙された
additive 変更と 2 Protocol を `src/erre_sandbox/schemas.py` に機械的に反映する。
spike 結果 (`.steering/20260420-m5-llm-spike/decisions.md` 判断 4-7) が contract 側
への追加要求を **ゼロ** と確定しているので、planning spec から逸脱しない。

M4 の `m4-contracts-freeze` (2026-04-20 merged) を踏襲:

1. schemas.py を編集 (SCHEMA_VERSION bump + new fields + Protocols + `__all__`)
2. fixture JSON を更新 (schema_version 置換 + dialog_turn.json に turn_index 追加)
3. golden JSON を regenerate (README.md に記載のコマンドで)
4. conftest.py の `_build_dialog_turn` に `turn_index` default 追加
5. 最小 test を追加 (新 field の validation、Protocol の import 可能性)
6. `uv run pytest -q` + `ruff` + `mypy` を全通過させる

**非破壊原則**: 新 field は全て default 付き (`dialog_turn_budget=6`) または
新規 required (`turn_index`) で、既存 M4 fixture は `schema_version` 置換のみで parse
可能 (optional 相当の追加だけ)。`turn_index` は DialogTurnMsg に新規 required なので、
既存 `dialog_turn.json` fixture には明示追加する。

## 変更対象

### 修正するファイル

- `src/erre_sandbox/schemas.py` — SCHEMA_VERSION bump / 新 field / 2 Protocol / `__all__`
- `tests/conftest.py` — `_build_dialog_turn` に `turn_index` default 追加
- `fixtures/control_envelope/agent_update.json` — schema_version 0.3.0-m5
- `fixtures/control_envelope/animation.json` — schema_version
- `fixtures/control_envelope/dialog_close.json` — schema_version
- `fixtures/control_envelope/dialog_initiate.json` — schema_version
- `fixtures/control_envelope/dialog_turn.json` — schema_version + `turn_index: 0`
- `fixtures/control_envelope/error.json` — schema_version
- `fixtures/control_envelope/handshake.json` — schema_version
- `fixtures/control_envelope/move.json` — schema_version
- `fixtures/control_envelope/speech.json` — schema_version
- `fixtures/control_envelope/world_tick.json` — schema_version
- `tests/schema_golden/agent_state.schema.json` — regenerate
- `tests/schema_golden/control_envelope.schema.json` — regenerate
- `tests/schema_golden/persona_spec.schema.json` — regenerate
- `docs/repository-structure.md` — schema_version 言及の更新 (必要なら)

### 新規作成するファイル

- (最小限に留める。既存 `tests/test_schemas.py` に test を追加、または
  M4 パターンに従い `tests/test_schemas_m5.py` を新規作成)

### 削除するファイル

- なし

## 影響範囲

- **wire 互換**: 全 additive。M4 fixture に対して `schema_version` 文字列の置換 +
  `dialog_turn.json` への `turn_index` 追加のみ。既存 WebSocket consumer (Godot 側)
  は現時点で dialog_turn の `turn_index` を使わない (M5 godot-zone-visuals で consumer
  を書く) が、parse-time に未知 field として drop される動作に合致
- **既存 test**: 525 test は `schema_version` 直値比較を持たない限り PASS。
  `DialogTurnMsg` を直接構築する test が turn_index 未指定で fail する可能性 →
  該当箇所を grep で特定し、test 側に `turn_index=0` を追加
- **persona YAML**: `default_sampling` / `dialog_turn_budget` は persona 固有値として
  持たず、後続 task で AgentState.cognitive.dialog_turn_budget に default=6 で注入
  (persona YAML の schema 変更はない)
- **downstream sub-task** (並列 4 本): 本 merge 後、それぞれが新 field / Protocol に
  import 可能な状態で着手

## 既存パターンとの整合性

- M4 `m4-contracts-freeze` の schema bump 手順 (schemas.py → fixtures → golden →
  conftest → test) をそのまま再利用
- §7.5 既存の `DialogScheduler` Protocol の docstring pattern に倣い、interface-only
  の旨を明記、concrete 実装は後続 task に委ねる旨を docstring に記載
- `__all__` はアルファベット順維持 (既存パターン)
- golden 再生成は `tests/schema_golden/README.md` に記載のインラインスクリプト
  をそのまま使用

## テスト戦略

- **単体**:
  - `Cognitive(dialog_turn_budget=6)` / `(dialog_turn_budget=0)` / `(dialog_turn_budget=-1)`
    で境界 (ge=0 検証)
  - `DialogTurnMsg(..., turn_index=0)` / `(..., turn_index=-1)` で境界
  - `DialogCloseMsg(..., reason="exhausted")` が parse できる
  - `DialogCloseMsg(..., reason="abandoned")` 等の未知 literal は ValidationError
  - `from erre_sandbox.schemas import ERREModeTransitionPolicy, DialogTurnGenerator`
    が成功し、`isinstance` チェックは期待しない (runtime_checkable 無し前提)
- **回帰**:
  - `test_schema_contract.py::test_json_schema_matches_golden` が新 golden と一致
  - `uv run pytest -q` 全体で 0 failures
- **統合**:
  - 本 task は interface-only のため統合 test は追加しない。統合 test は各
    sub-task (erre-mode-fsm / dialog-turn-generator) で追加

## ロールバック計画

- 単一 PR `feature/m5-contracts-freeze` → review → merge
- 問題が見つかった場合は `git revert` で即座に `0.2.0-m4` に戻せる
  (schemas.py の変更は全て additive なので revert は機械的)
- fixture / golden は schemas.py に追従するので revert 同時に戻る

# T05 schemas-freeze

## 背景

ERRE-Sandbox は MacBook (マスター) と G-GEAR (実行機) の 2 台で並列稼働する。
MASTER-PLAN.md §W2 のリスク評価により、`ControlEnvelope` と `AgentState` の仕様を
固めないまま両機が独立実装すると末期に致命的な手戻りが発生する。
本タスクは Contract-First 戦略の中核で、`src/erre_sandbox/schemas.py` に
全モジュール共通の Pydantic v2 データ契約を定義し「凍結」する。
T06 (persona-kant-yaml) / T07 (control-envelope-fixtures) / T08 (test-schemas) /
T10 (memory-store) / T11 (inference-ollama-adapter) / T12 (cognition-cycle-minimal) /
T13 (world-tick-zones) / T14 (gateway-fastapi-ws) はすべてこの契約に従う。

## ゴール

`src/erre_sandbox/schemas.py` に以下を Pydantic v2 で定義し、
`uv run mypy`・`uv run ruff check` が strict 設定でパスする状態にする。

- `AgentState` (Physical / Cognitive / ERRE モード含む)
- `MemoryEntry` (Episodic / Semantic / Procedural / Relational の区別)
- `Observation` (エージェントが世界から受ける入力)
- `ControlEnvelope` (Gateway → Godot 向け JSON)
- `ERREMode` Enum (8 種: peripatetic / chashitsu / zazen / shu_kata / ha_deviate / ri_create / deep_work / shallow)
- `PersonaSpec` (ペルソナ YAML のルート型)
- `Zone` Enum (study / peripatos / chashitsu / agora / garden)

後続タスクでの後方互換性破壊を避けるため、全モデルに `extra="forbid"` を設定する。

## スコープ

### 含むもの
- Pydantic v2 BaseModel 群の定義 (上記 7 種)
- 値域・デフォルト値・フィールド説明 (Field(..., description=...))
- `from __future__ import annotations` と型ヒント完備
- ruff ALL / mypy strict 準拠
- CSDG `HumanCondition` (5 フィールド) を `AgentState.Physical` に骨格採用 (MASTER-PLAN.md §B.5-1)
- CSDG `CharacterState` (fatigue / motivation / stress / memory_buffer / relationships) の構造を `AgentState.Cognitive` に参考
- CSDG `DailyEvent` (event_type / domain / description / emotional_impact) を `Observation` に応用

### 含まないもの
- 状態遷移ロジック (T12 cognition-cycle-minimal で実装)
- メモリ永続化 (T10 memory-store で実装)
- ControlEnvelope 実装の実際の fixture (T07 で作成)
- ペルソナ YAML 実体 (T06 で作成)
- スキーマのユニットテスト本体 (T08 で作成、ただし本タスクで smoke 程度は可)
- NOTICE への CSDG 帰属追記 (decisions.md のみ記載、NOTICE 更新は T08 で確認)

## 受け入れ条件

- [ ] `src/erre_sandbox/schemas.py` に 7 種のトップレベル型が定義されている
- [ ] 全モデルに `model_config = ConfigDict(extra="forbid")` が設定されている
- [ ] ERRE モード 8 種が Enum で列挙され、zone 5 種も列挙されている
- [ ] CSDG `HumanCondition` のデフォルト値 (sleep_quality=0.7, physical_energy=0.7, mood_baseline=0.0, cognitive_load=0.2) が `AgentState.Physical` に反映されている
- [ ] `uv run ruff check` が警告ゼロでパスする
- [ ] `uv run mypy src/erre_sandbox/schemas.py` が strict でパスする
- [ ] 既存の `tests/test_smoke.py` が壊れない
- [ ] schemas.py が他の `erre_sandbox.*` を import していない (architecture-rules)
- [ ] `decisions.md` に CSDG 参考箇所を明記
- [ ] Conventional Commits でコミット & `feature/schemas-freeze` → PR 作成

## 関連ドキュメント

- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §B.2 / §B.3 / §B.5
- `docs/architecture.md` (データフロー)
- `docs/repository-structure.md` §4 (依存方向)
- `docs/glossary.md` (ERRE モード・ゾーン用語)
- `.claude/skills/python-standards/SKILL.md`
- `.claude/skills/persona-erre/SKILL.md`
- `.claude/skills/architecture-rules/SKILL.md`
- CSDG `csdg/schemas.py` (MIT, 参考)

## 運用メモ

- 破壊と構築（/reimagine）適用: **Yes**
- 理由: Contract の核であり、公開 API として後続 T06-T14 すべてが依存する。
  設計判断を含むため、memory 指示 (reimagine_trigger) に従い
  初回案を破棄・再生成して 2 案比較してから実装に入る。
- タスク種別: その他 (契約凍結・基盤整備)。`/add-feature` 等には載らず、
  本タスク内で直接設計→実装→テストまで行う。

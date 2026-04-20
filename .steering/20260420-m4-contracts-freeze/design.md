# 設計 — m4-contracts-freeze

## 実装アプローチ

M4 foundation を **schemas.py の minimal primitive 追加 + `SCHEMA_VERSION` bump
+ fixture 刷新** で凍結する。planning タスク (`/20260420-m4-planning/`) の
D3 (foundation 小型化) に従い、後続 5 本が並列実装を開始するために必須な
primitive のみを扱う。

実装詳細 (reflection 発火条件、sqlite schema、turn-taking policy、per-agent
routing 方式) は個別タスクに委譲する。

## 変更対象

### 修正するファイル

- `src/erre_sandbox/schemas.py`
  - `SCHEMA_VERSION: Final[str]` を `"0.1.0-m2"` → `"0.2.0-m4"` に bump
  - §3 末尾に `AgentSpec` 追加 (`persona_id` + `initial_zone` の最小 fields)
  - §6 末尾に `ReflectionEvent`, `SemanticMemoryRecord` 追加
  - §7 (ControlEnvelope) に `DialogInitiateMsg` / `DialogTurnMsg` / `DialogCloseMsg`
    を追加し、`ControlEnvelope` union に含める
  - §3 の後か独立 section (§3.5 or §9 etc.) に `DialogScheduler` Protocol を追加
    (`typing.Protocol`、メソッドシグネチャのみ、`runtime_checkable` なし)
  - `__all__` に 6 primitive + `DialogScheduler` を追加
- `src/erre_sandbox/bootstrap.py`
  - `BootConfig` (frozen dataclass) に
    `agents: tuple[AgentSpec, ...] = field(default_factory=tuple)` を追加
  - `agents` が空のときは従来通り M2 の 1-Kant フローを維持 (back-compat)。
    実際の N-agent 対応は `m4-multi-agent-orchestrator` で実装
  - `AgentSpec` は `schemas` から import (別 API は作らない)
- `godot_project/scripts/WebSocketClient.gd`
  - `CLIENT_SCHEMA_VERSION` を `"0.1.0-m2"` → `"0.2.0-m4"` に更新
- `godot_project/scripts/EnvelopeRouter.gd`
  - `on_envelope_received` match block に `"dialog_initiate"`, `"dialog_turn"`,
    `"dialog_close"` の arm を追加 (各々 no-op signal emit でよい、
    `push_warning` しないこと)
  - 対応する signal 宣言 3 本 (`dialog_initiate_received`, `dialog_turn_received`,
    `dialog_close_received`) を追加
- `fixtures/control_envelope/*.json` (既存 7 ファイル)
  - `schema_version` を `0.1.0-m2` → `0.2.0-m4` に更新
  - `agent_update.json` の nested `agent_state.schema_version` も更新
- `tests/schema_golden/{agent_state,persona_spec,control_envelope}.schema.json`
  - 新 primitive と bump に合わせて regenerate (README §Regeneration command 準拠)
- `tests/conftest.py`
  - `_build_dialog_initiate` / `_build_dialog_turn` / `_build_dialog_close` を
    `_ENVELOPE_BUILDERS` に追加
- `tests/test_schemas.py`
  - M4 primitive の round-trip / validation / discriminator dispatch テスト追記
- `tests/test_envelope_kind_sync.py`
  - `test_python_side_has_seven_kinds` を 10 kinds (7 既存 + 3 dialog) に更新、
    もしくは名称を動的化 (`test_python_side_covers_expected_kinds`) して
    EXPECTED_KINDS を明示 set で pin する方針に変更
- `.steering/20260420-m4-planning/tasklist.md`
  - 「MASTER-PLAN 追記」「`decisions.md` 作成」等、既に docs commit 済みの項目を
    `[x]` にする fixup。commit/push/PR/merge のうち既に終わっているものを `[x]`

### 新規作成するファイル

- `fixtures/control_envelope/dialog_initiate.json`
- `fixtures/control_envelope/dialog_turn.json`
- `fixtures/control_envelope/dialog_close.json`
- `tests/fixtures/m4/agent_spec_3agents.json` — BootConfig の 3-agent 例 (kant/nietzsche/rikyu)
- `tests/fixtures/m4/reflection_event.json` — ReflectionEvent サンプル
- `tests/fixtures/m4/semantic_memory_record.json` — SemanticMemoryRecord サンプル

### 削除するファイル

- なし (M4 fixture 併存期間。M4 merge 完了時に M2 限定 fixture を別タスクで削除)

## primitive 詳細 (schemas.py に追加する定義)

### AgentSpec (M4 §3 末尾)
```python
class AgentSpec(BaseModel):
    """Boot-time minimal agent declaration.

    Expanded (persona join, tick, position) at runtime by
    m4-multi-agent-orchestrator into a full AgentState. This struct only
    carries the two values the composition root needs to instantiate an
    agent: which persona YAML to load and where on the map to spawn it.
    """
    model_config = ConfigDict(extra="forbid")
    persona_id: str = Field(..., description="Matches PersonaSpec.persona_id.")
    initial_zone: Zone
```

### ReflectionEvent (§6 末尾)
```python
class ReflectionEvent(BaseModel):
    """A reflection step snapshot (cognition cycle → semantic_memory)."""
    model_config = ConfigDict(extra="forbid")
    agent_id: str
    tick: int = Field(..., ge=0)
    summary_text: str
    src_episodic_ids: list[str] = Field(default_factory=list)
```

### SemanticMemoryRecord (§6 末尾)
```python
class SemanticMemoryRecord(BaseModel):
    """Long-term semantic memory row (distilled from reflection)."""
    model_config = ConfigDict(extra="forbid")
    id: str
    agent_id: str
    embedding: list[float] = Field(default_factory=list,
        description="Row-level vector; empty list permitted for fixtures.")
    summary: str
    origin_reflection_id: str | None = None
```

### Dialog* messages (§7 ControlEnvelope variant)
```python
class DialogInitiateMsg(_EnvelopeBase):
    kind: Literal["dialog_initiate"] = "dialog_initiate"
    initiator_agent_id: str
    target_agent_id: str
    zone: Zone

class DialogTurnMsg(_EnvelopeBase):
    kind: Literal["dialog_turn"] = "dialog_turn"
    dialog_id: str
    speaker_id: str
    addressee_id: str
    utterance: str

class DialogCloseMsg(_EnvelopeBase):
    kind: Literal["dialog_close"] = "dialog_close"
    dialog_id: str
    reason: Literal["completed", "interrupted", "timeout"]
```

### DialogScheduler (interface only)
```python
from typing import Protocol

class DialogScheduler(Protocol):
    """Interface for agent-to-agent dialog orchestration.

    The concrete implementation (turn-taking policy, backpressure, timeout
    handling) is the responsibility of `m4-multi-agent-orchestrator`. This
    Protocol is frozen here so that cognition/world can type-hint against
    it without waiting for the implementation.
    """

    def schedule_initiate(
        self, initiator_id: str, target_id: str, zone: Zone, tick: int
    ) -> DialogInitiateMsg | None: ...

    def record_turn(self, turn: DialogTurnMsg) -> None: ...

    def close_dialog(self, dialog_id: str, reason: str) -> DialogCloseMsg: ...
```

## 影響範囲

- 本 bump は **breaking** (`SCHEMA_VERSION` 変更)。
  Gateway の handshake が `client.schema_version != SCHEMA_VERSION` で
  reject するため、旧 M2 fixture やクライアント (CLIENT_SCHEMA_VERSION) は
  同時に更新が必要。GDScript と Python の両側を同じ PR 内で揃える。
- `test_envelope_kind_sync.py::test_python_side_has_seven_kinds` が
  ハードコード `7` で失敗する。同 PR で更新。
- `fixtures/control_envelope/*.json` 全件の `schema_version` 更新が必要
  (既存 envelope fixture テスト `test_fixture_schema_version_matches` が検出)。
- `tests/schema_golden/*.schema.json` 3 件の regenerate が必要
  (既存 `test_json_schema_matches_golden` が検出)。
- `BootConfig.agents` のデフォルトは空 `tuple()` なので
  `__main__.cli` と既存 bootstrap パスには影響しない (back-compat)。
- `DialogScheduler` は Protocol only。具象クラスは存在しないため
  ランタイム挙動に影響なし。

## 既存パターンとの整合性

- **Contract-First (M2)**: schemas + fixtures + GDScript parser を同一 PR で
  凍結する M2 T05-T08 パターンを踏襲
- **`extra="forbid"`**: 新 BaseModel 全件に適用 (architecture-rules / test_schema_contract)
- **`_EnvelopeBase` 継承**: 新 Dialog* messages は既存 envelope 基底を継承し
  `schema_version` / `tick` / `sent_at` を自動で持つ
- **`Zone` / `ERREModeName` 再利用**: AgentSpec / DialogInitiateMsg の zone
  フィールドは既存 `Zone` StrEnum を再利用 (新 enum は作らない)
- **Golden JSON Schema regenerate**: README の regeneration command を
  そのまま実行、手編集しない

## テスト戦略

### 単体テスト (`tests/test_schemas.py` 追記)
- `test_agent_spec_validates_minimal_shape`
- `test_agent_spec_rejects_extra`
- `test_reflection_event_round_trip`
- `test_semantic_memory_record_round_trip`
- `test_semantic_memory_record_accepts_empty_embedding`
- `test_dialog_initiate_msg_validates`
- `test_dialog_turn_msg_validates`
- `test_dialog_close_msg_reason_is_literal`
- `test_control_envelope_union_dispatches_dialog_variants`
- `test_dialog_scheduler_protocol_has_required_methods`
  (Protocol メソッドの存在 + シグネチャ簡易チェック)

### 契約テスト (自動で回帰する既存テスト)
- `test_envelope_fixtures.py::test_all_expected_kinds_have_fixture`
  → 新 3 fixture が必要
- `test_envelope_fixtures.py::test_fixture_schema_version_matches`
  → 全 fixture bump が必要
- `test_schema_contract.py::test_json_schema_matches_golden`
  → 3 golden regenerate が必要
- `test_schema_contract.py::test_public_basemodel_forbids_extra`
  → 新 BaseModel に `extra="forbid"` 必須
- `test_envelope_kind_sync.py` → GDScript の match 更新が必要

### bootstrap テスト (`tests/test_bootstrap.py`)
- `BootConfig` の frozen + defaults チェックは既存のまま通過すること
- `agents` default が空 tuple であることを assert する 1 case を追加

### 統合テスト / E2E
- 本タスクは foundation 凍結のみ。
  ランタイム挙動変更なし → 既存 integration テスト全件 PASS 維持で十分
- M4 acceptance (3-agent live) は `m4-multi-agent-orchestrator` で実施

### 回帰ベースライン
- 既存 346 tests が全件 PASS (regression ゼロ)
- 新規 tests 追加により total は 355 前後になる見込み

## ロールバック計画

- PR revert 一発で戻る (single-commit-per-file 前提)。
- schema_version の bump 自体は fixture / golden / GDScript も含む同一 PR で
  行うので、revert 後に orphan state は発生しない。
- 万一 `m4-personas-*` 等が本 PR merge を前提にした PR を出している場合、
  Contract 変更は本 PR で閉じているため、revert 後も依存タスクは `main`
  に rebase して再出せる。

## schema_version bump の手順

1. `src/erre_sandbox/schemas.py` §1 の `SCHEMA_VERSION` を `"0.2.0-m4"` に更新
2. `godot_project/scripts/WebSocketClient.gd` の `CLIENT_SCHEMA_VERSION` を
   `"0.2.0-m4"` に更新
3. `fixtures/control_envelope/*.json` 全件の `schema_version` を更新
   (`agent_update.json` は nested `agent_state.schema_version` も)
4. `tests/schema_golden/*.schema.json` を README の regeneration command で再生成
5. `uv run pytest` 全緑を確認

## Out of scope (再掲)

- reflection 発火条件の実装
- `semantic_memory` sqlite テーブル定義・CRUD
- `DialogScheduler` の具象実装 (turn-taking)
- per-agent gateway routing 実装
- persona YAML 新規追加
- bootstrap の N-agent 起動フロー (CLI `--personas` flag は `__main__` のまま不変)

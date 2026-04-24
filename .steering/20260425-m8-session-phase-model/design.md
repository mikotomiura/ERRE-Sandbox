# Design — M8 Epoch Phase Model

本 design は `/Users/johnd/.claude/plans/misty-marinating-scone.md` (Plan mode 承認済)
を steering に転記したもの。軸 1-4 の /reimagine 採用判断は `decisions.md` 参照。

## 立脚点

L6 ADR D3 (`.steering/20260424-steering-scaling-lora/decisions.md`) の
`two-phase methodology` を schema 層に実装する M8 spike。Phase 1 探索で 2 件の
発見事項が plan を修正:

1. **命名衝突**: `integration/protocol.py:115-126` に既存 `SessionPhase`
   (gateway WS state = AWAITING_HANDSHAKE / ACTIVE / CLOSING) があるため、
   本 spike の enum は **`EpochPhase`** (autonomous / q_and_a / evaluation)
   と命名し直交させる。
2. **置き場所**: BootConfig は `@dataclass(frozen=True)` で mutable phase を
   持てず (`.steering/20260420-m4-contracts-freeze/decisions.md` D3)、
   AgentState は per-agent scope で run-level phase と噛み合わない。
   run-level mutable state は **WorldRuntime** (`src/erre_sandbox/world/tick.py:259`)
   に置くのが筋。

## 採用プラン

- `EpochPhase` StrEnum を `schemas.py` §2 に追加 (Zone / ERREModeName 同パターン)
- `RunLifecycleState` BaseModel を `schemas.py` 新規 §4.5 に追加
  (fields: `epoch_phase: EpochPhase`、`epoch_started_at: datetime`)
- WorldRuntime に `_run_lifecycle` 属性 + 公開プロパティ `run_lifecycle` を追加
- 遷移メソッド 2 本 (`transition_to_q_and_a()` / `transition_to_evaluation()`)、
  許可パス以外は `ValueError`
- Q&A 規約: `DialogTurnMsg.speaker_id="researcher"` を magic string として使用、
  autonomous epoch の log export は filter、PersonaId Literal は導入しない
- SCHEMA_VERSION を `0.4.0-m6` → `0.5.0-m8` に bump
- `personas/*.yaml` の schema_version 欄を同期更新
- `scripts/regen_schema_artifacts.py` で fixture を再生成

## 変更対象ファイル

| Path | 変更種別 |
|---|---|
| `src/erre_sandbox/schemas.py` | 編集 (新 enum、新 BaseModel、SCHEMA_VERSION bump、docstring) |
| `src/erre_sandbox/world/tick.py` | 編集 (WorldRuntime に lifecycle + 2 メソッド) |
| `personas/{kant,rikyu,nietzsche}.yaml` | 編集 (schema_version 同期) |
| `tests/test_schemas.py` | 編集 (EpochPhase / RunLifecycleState テスト追加) |
| `tests/test_world/test_runtime_lifecycle.py` | **新規** (FSM 遷移テスト) |
| `fixtures/control_envelope/*.json` + `tests/schema_golden/*.json` | 再生成 |
| `.steering/20260425-m8-session-phase-model/decisions.md` | **新規** (軸 1-4 記録) |

## 再利用する既存資産

- StrEnum 前例: `schemas.py:95` (Zone)、`schemas.py:105` (ERREModeName)、
  `schemas.py:127` (TimeOfDay)
- schema_version bump 前例: `.steering/20260420-m4-contracts-freeze/decisions.md` +
  `.steering/20260420-m5-contracts-freeze/decisions.md`
- fixture 再生成 script: `scripts/regen_schema_artifacts.py` (M5 追加、判断1)
- test 書式: `tests/test_schemas.py::test_str_enum_round_trip_as_json` (line 85)
- fixture factory 前例: `tests/conftest.py:36-80` の `make_agent_state` / `make_envelope`
- WorldRuntime test 前例: `tests/test_world/conftest.py` の `MockCycle` + `RuntimeHarness`

## 検証

### ユニットテスト (Mac 完走)
- `uv run pytest tests/test_schemas.py -k "epoch or lifecycle"` で新規テスト全パス
- `uv run pytest tests/test_world/test_runtime_lifecycle.py` で遷移 FSM 全パス
  - 許可: autonomous → q_and_a、q_and_a → evaluation
  - 不許可: autonomous → evaluation 直飛び、q_and_a → autonomous 逆行、
    evaluation → any、再遷移 (autonomous → autonomous 等)
- `uv run pytest` 全体で regression なし (既存 PASS 数を維持)

### 契約整合性
- `uv run python scripts/regen_schema_artifacts.py` 実行後の diff が
  期待通り (schema_version 欄のみ)
- `grep SCHEMA_VERSION src/erre_sandbox/schemas.py` と
  `grep schema_version personas/*.yaml` が `0.5.0-m8` で一致
- `git diff --stat main...HEAD` で `src/` + `tests/` + `personas/` + `.steering/` +
  fixtures のみ

### レビュー
- `impact-analyzer` で schema_version bump の呼び出し側影響を確認
- `code-reviewer` で schemas.py 追記 + WorldRuntime FSM をレビュー

## Out of Scope

- Q&A epoch 中の LLM routing (researcher → agent への発話 injection)
- Godot text input UI
- evaluation phase の中身 (M10-11 evaluation layer 本体)
- `personas/researcher.yaml` 作成 (speaker_id は magic string で済ませる)
- PersonaId Literal 導入
- 既存 gateway `SessionPhase` の改名 (意味ドメインが別なので併存)
- ControlEnvelope に epoch_phase 変種追加 (観察要件が立った時に別 spike)

## 設計判断の履歴

- Plan mode + /reimagine (軸 1-4) を 2026-04-24 に適用、同日実装着手
- L6 ADR D3 → M8 spike (本 task) → M9 以降の Q&A runtime / LLM routing

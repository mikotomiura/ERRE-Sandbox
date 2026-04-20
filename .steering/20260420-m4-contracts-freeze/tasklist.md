# タスクリスト — m4-contracts-freeze

## 準備
- [x] `.steering/20260420-m4-planning/design.md` (採用案 v2 + hybrid) を読む
- [x] `.steering/20260420-m4-planning/decisions.md` D3 (foundation 小型化) を読む
- [x] `.steering/20260418-implementation-plan/MASTER-PLAN.md §5.1` を読む
- [x] 既存 schemas.py / fixtures / EnvelopeRouter.gd / bootstrap.py を読み込み
      影響範囲を特定

## 実装
- [x] `feature/m4-contracts-freeze` branch を切る
- [x] `src/erre_sandbox/schemas.py`
  - [x] `SCHEMA_VERSION` を `"0.2.0-m4"` に bump
  - [x] `AgentSpec` を §3 末尾に追加
  - [x] `ReflectionEvent`, `SemanticMemoryRecord` を §6 末尾に追加
  - [x] `DialogInitiateMsg`, `DialogTurnMsg`, `DialogCloseMsg` を §7 に追加し
        `ControlEnvelope` union に含める
  - [x] `DialogScheduler` Protocol を追加
  - [x] `__all__` を更新
- [x] `src/erre_sandbox/bootstrap.py`
  - [x] `AgentSpec` を schemas から import
  - [x] `BootConfig.agents: tuple[AgentSpec, ...] = ()` を追加
        (frozen dataclass に immutable default 直書きで足りる)
- [x] `godot_project/scripts/WebSocketClient.gd`
  - [x] `CLIENT_SCHEMA_VERSION` を `"0.2.0-m4"` に更新
- [x] `godot_project/scripts/EnvelopeRouter.gd`
  - [x] `dialog_initiate` / `dialog_turn` / `dialog_close` match arm 追加
  - [x] 対応する signal 3 本を追加

## fixtures
- [x] `fixtures/control_envelope/*.json` 全件 `schema_version` を `0.2.0-m4` に更新
- [x] `fixtures/control_envelope/dialog_initiate.json` を新規作成
- [x] `fixtures/control_envelope/dialog_turn.json` を新規作成
- [x] `fixtures/control_envelope/dialog_close.json` を新規作成
- [x] `tests/fixtures/m4/agent_spec_3agents.json` を新規作成 (3 agent BootConfig)
- [x] `tests/fixtures/m4/reflection_event.json` を新規作成
- [x] `tests/fixtures/m4/semantic_memory_record.json` を新規作成

## tests
- [x] `tests/conftest.py` に dialog_* envelope builders を追加
- [x] `tests/test_schemas.py` に M4 primitive 向け test を追加
- [x] `tests/test_envelope_kind_sync.py` を set equality ベースに更新
      (ハードコード `7` を廃止、D6)
- [x] `tests/test_bootstrap.py` に BootConfig.agents default check を追加
- [x] `tests/schema_golden/*.schema.json` 3 件を regenerate
- [x] `personas/kant.yaml` の `schema_version` を bump (D7)

## 検証
- [x] `uv run pytest` 全緑: **378 passed, 20 skipped** (baseline 346 → 378)
- [x] `uv run ruff check` 対象ファイル (schemas / bootstrap / tests) 全クリーン
      (※ 既存 `src/erre_sandbox/world/tick.py` に PLW2901 が main 側から
      持ち越されているが本 PR 範囲外)
- [x] `uv run ruff format --check` — 84 files already formatted

## レビュー
- [ ] `code-reviewer` subagent レビュー (commit 後・PR 前に実施)
- [ ] `security-checker` subagent 軽量確認

## ドキュメント
- [ ] `docs/architecture.md` §Schemas に M4 primitive 見出し追加
      (肉付けは個別サブタスク、D6 方針) — 初回 commit で行う

## 完了処理
- [x] `decisions.md` 作成 (D1-D8、D2: minor bump、D4: Protocol only、D5: fixture 配置)
- [x] `.steering/20260420-m4-planning/tasklist.md` の MASTER-PLAN 追記以降の
      checkbox を `[x]` に更新
- [ ] commit: `feat(schemas): m4 contracts freeze — AgentSpec / Reflection / Dialog variants + schema 0.2.0-m4`
- [ ] push → PR 作成 (branch: `feature/m4-contracts-freeze`)
- [ ] PR review → main merge
- [ ] tag 発行なし

## 次のタスク (本 PR merge 後に並列実行可)
- `m4-personas-nietzsche-rikyu-yaml` (Axis A content)
- `m4-memory-semantic-layer` (Axis B infra)
- `m4-gateway-multi-agent-stream` (Axis A+C infra)

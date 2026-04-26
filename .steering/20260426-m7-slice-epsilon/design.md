# M7 Slice ε — Design

> 詳細な設計判断は `decisions.md` D1-D6 と Plan file
> `~/.claude/plans/breezy-riding-valley.md` に記録。本ファイルは設計の
> 1 行サマリと、PR-ε-1 / PR-ε-2 で具体的に何をどう変更するかの
> top-level 早見表として機能する。

## 実装アプローチ

ε は M7 系の **後始末 slice**。新機能でも refactor でもなく、δ post-merge
review (R4) の HIGH/MEDIUM 8 件と既知 deferred (live-fix D2、M8 D5) を
集約消費し、M9-LoRA と M10-11 に綺麗な土台を渡す。

設計の核心は 3 つ:

1. **既存資産を再利用**: `EpochPhase` (schemas.py:219) を再利用、新 `SessionPhase`
   を作らない (decisions.md D4)。`RunLifecycleState` /
   `WorldRuntime.transition_to_q_and_a` も既存実装を活用。
2. **scope 分離**: ε で wrapper accessor を入れない (m9-belief-persistence-extraction
   へ defer、D2)、LLM rate watch を scaling_metrics.json に入れない
   (infra-health-observability へ defer、D3)。
3. **2-PR 直列**: schema bump 有無で hygiene PR と feature PR を分割
   (decisions.md D1)、review surface を浅く保つ。

## 変更対象 (PR-ε-1 — no schema bump)

### 修正するファイル
- `src/erre_sandbox/integration/gateway.py` — (a) 71-87 行 orphaned docstring を
  `_MAX_RAW_FRAME_BYTES` 直下に restore (R4 H1)、(b) `_recv_loop` で
  `WebSocketDisconnect` を catch、`logger.debug` + `_GracefulCloseError` 変換
  (live-fix D2)
- `src/erre_sandbox/world/tick.py` — 122,129 行 docstring を
  `-0.30 → -0.10` + `0.15 → 0.05` + retune 注記 (R4 H2)
- `src/erre_sandbox/cognition/_trait_antagonism.py` — 35 行 module-level
  comment を `-0.30 → -0.10` (R4 H2/L1)
- `src/erre_sandbox/bootstrap.py` — 225, 319 行 `except sqlite3.OperationalError`
  を `except sqlite3.DatabaseError` (R4 M3)
- `tests/test_integration/test_gateway.py` — `test_recv_loop_handles_clean_websocket_disconnect`
  追加
- `tests/test_integration/test_slice_delta_e2e.py` — IntegrityError 注入 2 件
  (`test_relational_sink_swallows_integrity_error_on_add_sync` /
  `test_belief_persist_swallows_integrity_error_on_upsert_semantic`)
- `tests/test_cognition/test_belief_promotion.py` — parametrise 拡張
  (`(0.70, "trust")`, `(-0.70, "clash")` 追加、R4 M4) +
  `test_belief_promotion_at_exact_boundaries` 5 ケース (R4 M1) +
  `test_confidence_clamps_at_one` 1 ケース (R4 M6)

### 新規作成するファイル
- `.steering/20260426-m7-slice-epsilon/{requirement,decisions,design,tasklist,blockers}.md`
  — task scaffold

### 削除するファイル
なし。

## 変更対象 (PR-ε-2 — schema bump 0.7.0-m7d → 0.8.0-m7e、本 PR merge 後)

### 修正するファイル
- `src/erre_sandbox/schemas.py` — SCHEMA_VERSION bump、`DialogTurnRecord.epoch_phase`
  field 追加 (default `EpochPhase.AUTONOMOUS`)
- `src/erre_sandbox/memory/store.py` — `_migrate_dialog_turns_schema` 新設
  (idempotent、PRAGMA + ADD COLUMN)、`add_dialog_turn_sync(... epoch_phase=)` 引数、
  `iter_dialog_turns(... epoch_phase=)` filter kwarg、`create_schema()` で migration 呼び出し
- `src/erre_sandbox/evidence/scaling_metrics.py` — 553-566 行の docstring を
  `epoch_phase` に書き換え + `aggregate()` で
  `iter_dialog_turns(epoch_phase=EpochPhase.AUTONOMOUS)` を有効化
- `src/erre_sandbox/bootstrap.py` — dialog turn sink で
  `runtime.run_lifecycle.epoch_phase` を読んで stamp
- `godot_project/scripts/WebSocketClient.gd` — `CLIENT_SCHEMA_VERSION` 追従
- `tests/schema_golden/*.json` — re-bake
- `tests/test_memory_store.py` — migration idempotent + column round-trip +
  filter kwarg test
- `tests/test_evidence/test_scaling_metrics.py` —
  `test_aggregate_filters_qa_user_turns` + `test_aggregate_pre_migration_null_treated_as_autonomous`

### 新規作成するファイル
- `.steering/20260426-m7-slice-epsilon/run-guide-epsilon.md` — run-guide-delta.md
  の epsilon 版

## 影響範囲

- **wire schema** (PR-ε-2): `DialogTurnRecord` の field 追加。新規 default あり、
  古い JSON は欠落 field を許容 (Pydantic strict=False の慣行)。Godot client
  も追従、handshake mismatch なし。
- **DB schema** (PR-ε-2): `dialog_turns.epoch_phase` 列追加。NULL を許容、
  pre-migration row は AUTONOMOUS として読み出される。
- **observability** (PR-ε-2): `scaling_metrics.aggregate()` の filter active 化。
  autonomous-only run では no-op (現行運用と等価)、`Q_AND_A` row が来たら除外。
- **logging** (PR-ε-1): gateway `_recv_loop` の `WebSocketDisconnect` 取り扱いが
  ERROR → DEBUG に降格。acceptance log の `grep ERROR` count が drop する見込み。

## 既存パターンとの整合性

- `_migrate_semantic_schema` (memory/store.py) を `_migrate_dialog_turns_schema`
  の rectangular template として再利用
- `_persist_bias_event` (bootstrap.py) を将来 LLM unparseable rate sink の
  pattern source として infra-health-observability で再利用予定
- gamma R3 → δ scope 流れ
  (`.steering/20260425-m7-slice-gamma/decisions.md` §R3) を δ R4 → ε scope の
  前例として継承
- `_send_loop` (gateway.py:451) の `WebSocketDisconnect` catch + DEBUG +
  `_GracefulCloseError` 変換 pattern を `_recv_loop` にも適用 (symmetric)

## テスト戦略

- **単体テスト** (PR-ε-1): boundary tests (R4 M1/M4/M6)、IntegrityError 注入
  (R4 M3)。`monkeypatch` 中心、新 fixture 不要。
- **統合テスト** (PR-ε-1): gateway WS demote (caplog で DEBUG 確認 + ERROR 不在
  を assert)。既存 client / fast_timeouts fixture 再利用。
- **migration テスト** (PR-ε-2): `_migrate_dialog_turns_schema` の idempotent
  検証、PRAGMA で `session_phase` 列の存在を直接観察。
- **filter テスト** (PR-ε-2): `Q_AND_A` row を直接 SQL で insert してから
  `aggregate()` を呼び出し、autonomous turns のみが M1/M2/M3 計算に寄与する
  ことを assert。
- **E2E テスト** (PR-ε-2): live G-GEAR run-01-epsilon (90-360s)。autonomous-only
  なので filter は no-op、δ acceptance gate 5/5 維持を確認。新 metric の field
  が `scaling_metrics.json` に出力されることを smoke 確認。

## ロールバック計画

- **PR-ε-1**: docstring + log level + except scope + tests のみで wire 影響なし。
  単に PR を revert すれば復元可能。
- **PR-ε-2**: schema bump あり。revert 時は (a) Godot client `CLIENT_SCHEMA_VERSION`
  も同時 revert、(b) `dialog_turns.epoch_phase` 列は SQLite の `ALTER TABLE
  DROP COLUMN` をサポートしないので、列は残す (NULL のままで実害なし)。
  PR-ε-2 の migration は forward-only design なのでこれが受け入れる前提。

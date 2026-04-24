# Tasklist — M8 Episodic Log Pipeline (v2)

> L6 D1 precondition、~0.5-0.75d 見込 (Mac 実装、G-GEAR acceptance は本 PR 後)。
> /reimagine 適用済、v1 (3 event 全永続化) → v2 (dialog_turn のみ) に転回。
> 詳細 `design.md` / `decisions.md`。

## 準備
- [x] L6 ADR D1 (`.steering/20260424-steering-scaling-lora/decisions.md`) を Read
- [x] `architecture-rules` / `test-standards` Skill を Read
- [x] `MemoryStore` / `InMemoryDialogScheduler` / `__main__.py` の現状を調査
- [x] /reimagine 実施、v2 採用確定

## Phase 1: MemoryStore 拡張
- [ ] `dialog_turns` table を `create_schema()` に追加 (UNIQUE(dialog_id,
      turn_index) + index on speaker_persona_id, created_at)
- [ ] `_add_dialog_turn_sync()` を追加 (RLock 保持、INSERT OR IGNORE で冪等)
- [ ] `add_dialog_turn()` async wrapper を追加 (asyncio.to_thread)
- [ ] `iter_dialog_turns(persona=None, since=None)` generator を追加
      (export の iteration source)

## Phase 2: DialogScheduler sink
- [ ] `InMemoryDialogScheduler.__init__` に `turn_sink: Callable[[DialogTurnMsg],
      None] | None = None` を追加
- [ ] `record_turn()` で turn_sink があれば呼ぶ (既存 transcript append の直後)
- [ ] bootstrap で sink closure を構築 (agent_id → persona_id の閉包)

## Phase 3: CLI
- [ ] `src/erre_sandbox/cli/__init__.py` を新規 (package)
- [ ] `src/erre_sandbox/cli/export_log.py` を新規:
      `async def run_export(store, *, persona, since, out_path) -> int` 等
- [ ] `__main__.py` を argparse subparsers 化
      - 既存の 1-command behaviour を `run` subcommand に保ちつつ、
        argv[1] 省略時の後方互換 default を維持
      - `export-log` subcommand を追加 (`--format jsonl` / `--persona` /
        `--since` / `--out`)

## Phase 4: SQL サンプル
- [ ] `docs/_queries/dialog_turns.sql` に persona 別 count / time range /
      pair 頻度 / M9 準備状態 (≥1000 turns/persona までの距離) の 4 queries

## Phase 5: テスト
- [ ] `tests/test_memory/test_store.py` に 5 本追加:
      - `test_add_dialog_turn_inserts_row`
      - `test_add_dialog_turn_is_idempotent_on_duplicate`
      - `test_iter_dialog_turns_filters_by_persona`
      - `test_iter_dialog_turns_filters_by_since`
      - `test_dialog_turn_count_by_persona_query`
- [ ] `tests/test_integration/test_dialog_sink.py` 新規: Scheduler ->
      MemoryStore の e2e、3 turn を record_turn() して sqlite に 3 row 確認
- [ ] `tests/test_cli_export_log.py` 新規: subcommand 起動 → JSONL 出力 →
      再パース round-trip
- [ ] `uv run pytest` 全体で regression 確認

## Phase 6: Review + PR
- [ ] `code-reviewer` で store / scheduler / CLI をレビュー
- [ ] `impact-analyzer` で bootstrap sink 配線の影響確認
- [ ] `git diff --stat main...HEAD` を確認 (src / tests / docs / .steering のみ、
      SCHEMA_VERSION 変更なし)
- [ ] commit → PR (`feat(memory): M8 episodic log pipeline`)
- [ ] PR body に v2 scope 縮小の根拠と deferred 項目を明示

## Phase 7: G-GEAR acceptance (本 PR 後、別 session)
- [ ] live run 60-90s × 1 本
- [ ] `uv run erre-sandbox export-log --out baseline.jsonl`
- [ ] `log-snapshot.md` に persona 別 turn count + M9 前提までの距離を記録
- [ ] L6 D1 status を「baseline data 収集中」に更新

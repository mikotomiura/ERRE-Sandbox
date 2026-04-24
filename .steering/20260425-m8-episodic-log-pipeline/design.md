# Design — M8 Episodic Log Pipeline (v2, scope-reduced)

本 design は `/Users/johnd/.claude/plans/misty-marinating-scone.md` (Plan mode
承認済) を steering に転記したもの。/reimagine 軸 1-5 の採用は `decisions.md`。

## 立脚点

L6 ADR D1 (`defer-and-measure`) の M8 precondition。M9 LoRA 訓練の前提
`≥1000 turns/persona` を定量的に tracking するため、対話 log の永続化経路を
整備する。

### Phase 1 探索で発覚した scope bomb

tasklist 当初は 1d 見積だったが、探索で判明した事実:

- `DialogTurnMsg` / `ReasoningTraceMsg` / `ReflectionEventMsg` **3 event 種
  いずれも sqlite に永続化されていない** (envelope broadcast のみ)
- `DialogScheduler.transcript_of()` は in-memory、process 終了で消える
- `MemoryStore` は `episodic_memory` / `semantic_memory` / `procedural_memory` /
  `relational_memory` / `vec_embeddings` の 5 table のみ、dialog 系ゼロ
- `session_id` の notion はコード全体に存在しない
- `pyarrow` / pandas 未依存

3 event 全永続化 + schema bump + Parquet CLI は **1.5-2d 規模**、spike 1d 見積
を倍近く超える。

## 採用プラン (v2)

**対話 turn のみ永続化**、reasoning_trace / reflection_event は出さない。詳細の
各軸判断は `decisions.md` D1-D5 を参照。

### 変更内容

- 新 table `dialog_turns` を `MemoryStore.create_schema()` に追加
- `MemoryStore.add_dialog_turn_sync(turn, *, speaker_persona_id,
  addressee_persona_id)` + async wrapper
- `InMemoryDialogScheduler` ctor に optional `turn_sink: Callable[[DialogTurnMsg],
  None]` を追加、`record_turn()` で sink があれば呼ぶ
- `erre-sandbox export-log` subcommand を `__main__.py` argparse に追加
  (`--format jsonl` / `--persona` / `--since` / `--out`)
- SQL サンプルを `docs/_queries/dialog_turns.sql`
- test 3 組: `test_store.py::test_add_dialog_turn_*` 5 本 +
  `test_dialog_sink.py` 1 e2e + `test_cli_export_log.py`

### dialog_turns table schema

```sql
CREATE TABLE IF NOT EXISTS dialog_turns (
    id TEXT PRIMARY KEY,                     -- uuid4
    dialog_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    turn_index INTEGER NOT NULL,
    speaker_agent_id TEXT NOT NULL,
    speaker_persona_id TEXT NOT NULL,
    addressee_agent_id TEXT NOT NULL,
    addressee_persona_id TEXT NOT NULL,
    utterance TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(dialog_id, turn_index)            -- idempotency guard
);
CREATE INDEX IF NOT EXISTS ix_dialog_turns_persona
  ON dialog_turns(speaker_persona_id, created_at);
```

### 持続化の同期モデル

`DialogScheduler.record_turn()` Protocol は **同期** で凍結済
(`schemas.py:963`)。永続化のために async 化すると Protocol 破壊、M8 scope 外。

採用: `MemoryStore` に **同期** `add_dialog_turn_sync()` を公開、scheduler は
sync 呼び出しで block する (≈1-5ms/insert、許容)。async wrapper
(`add_dialog_turn()`) は CLI / 将来の async caller 向けに提供。sqlite の
RLock は既存 `_conn_lock` を再利用、M6 concurrent-access 規約と整合。

### 変更対象ファイル

| Path | 変更種別 |
|---|---|
| `src/erre_sandbox/memory/store.py` | 編集 (dialog_turns table + add methods) |
| `src/erre_sandbox/integration/dialog.py` | 編集 (turn_sink 引数追加) |
| `src/erre_sandbox/__main__.py` | 編集 (argparse subparsers 化 + export-log) |
| `src/erre_sandbox/cli/__init__.py` | **新規** (cli package) |
| `src/erre_sandbox/cli/export_log.py` | **新規** (export 実装) |
| `tests/test_memory/test_store.py` | 編集 (add_dialog_turn テスト 5 本) |
| `tests/test_integration/test_dialog_sink.py` | **新規** (scheduler → store e2e) |
| `tests/test_cli_export_log.py` | **新規** (CLI round-trip) |
| `docs/_queries/dialog_turns.sql` | **新規** (SQL サンプル集) |

### 再利用する既存資産

- `MemoryStore` pattern: `store.py:108-196` (create_schema)、`store.py:242-334`
  (_add_sync)
- concurrent-safety: `store.py:87` (_conn_lock RLock)、M6 fix
  (`tests/test_memory/test_store.py:242`)
- test fixture: `tests/test_memory/conftest.py:18-26` (in-memory store)
- argparse dispatch: `__main__.py:38`
- `DialogScheduler` Protocol: `schemas.py:963`
- persona_id 解決源: bootstrap の `AgentSpec` (persona_id) + AgentState.agent_id

## 検証

### ユニットテスト (Mac 完走)
- `uv run pytest tests/test_memory/test_store.py -k dialog_turn` 5 本 PASS
- `uv run pytest tests/test_integration/test_dialog_sink.py` PASS
- `uv run pytest tests/test_cli_export_log.py` PASS
- `uv run pytest` 全体で regression なし

### 契約整合性
- SCHEMA_VERSION 変更なし (wire 無変更の証跡)
- `grep pyarrow pyproject.toml` がゼロ (依存追加なし)
- `git diff --stat main...HEAD` が src / tests / docs / .steering のみ

### CLI 動作
- `uv run erre-sandbox export-log --help` で subcommand help
- 空 DB で `--out f.jsonl` が空ファイル + exit 0
- 3 turn inserted DB で `--persona kant` が 1 persona のみ

### G-GEAR acceptance (本 PR 後、別 session)
- live run 60-90s → `export-log --out baseline.jsonl`
- `log-snapshot.md` に persona 別 turn count
- M9 前提 ≥1000 turns/persona までの距離見積

## Out of Scope

- `ReasoningTraceMsg` / `ReflectionEventMsg` の sqlite 永続化 (別 spike)
- `session_id` 概念の導入 (M8 session-phase-model の後続 / Q&A epoch で扱う)
- Parquet export (LoRA task で pyarrow 追加時に)
- DPO ペア抽出 / 選別ロジック (M9 early task)
- `DialogTurnMsg` schema への persona_id 追加 (sink 側で解決)
- SCHEMA_VERSION bump (wire 無変更)

## 設計判断の履歴

- 2026-04-24 Plan mode 承認、/reimagine で v1 (3 event 全永続化) → v2 (dialog_turn
  のみ) に転回
- L6 ADR D1 の真の目的 (LoRA 訓練用 turn 数 tracking) に focus、scope 爆弾を
  軸 1-5 で体系的に削減

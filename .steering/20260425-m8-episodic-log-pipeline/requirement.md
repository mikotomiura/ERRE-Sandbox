# M8 Spike — Episodic Log Pipeline (v2, scope-reduced)

> **/reimagine 適用済 (2026-04-24)**: 初回 requirement (3 event 全永続化) は
> Phase 1 探索で発覚した scope 爆弾 (現在 3 event いずれも sqlite に存在しない)
> を受けて v2 に縮小。`design.md` / `decisions.md` D1-D5 参照。

## 背景

L6 ADR D1 (`defer-and-measure`) の M8 precondition。M9 LoRA 訓練は
`≥1000 turns/persona` を前提 (MASTER-PLAN L146)。現状 dialog_turn は
`InMemoryDialogScheduler.transcript_of()` の in-memory のみに存在し、process
終了で消失。LoRA 訓練データへの経路を作るため、対話 turn を sqlite に永続化し、
persona 別 count を SQL で取得可能にする。

## ゴール

- dialog_turn が sqlite `dialog_turns` table に漏れなく記録される
- `SELECT speaker_persona_id, COUNT(*) FROM dialog_turns GROUP BY
  speaker_persona_id` で persona 別 turn count が取得可能
- `uv run erre-sandbox export-log --format jsonl --out <path>` で JSONL export

## スコープ

### 含むもの
- `MemoryStore` に `dialog_turns` table + add_dialog_turn_sync/async メソッド
- `InMemoryDialogScheduler` に optional `turn_sink` 引数、record_turn() で発火
- bootstrap で sink を MemoryStore に繋ぐ、agent_id → persona_id map を閉包
- `erre-sandbox export-log` subcommand (argparse subparsers 化)
  - `--format jsonl` (default、他形式は明示的 error)
  - `--persona <id>` filter
  - `--since <ISO-8601>` filter
  - `--out <path>` (省略時 stdout)
- SQL サンプル集 (`docs/_queries/dialog_turns.sql`)
- unit test (store 5 本 + scheduler sink e2e + CLI round-trip)

### 含まないもの (/reimagine で defer した項目、decisions D1-D5)
- `ReasoningTraceMsg` / `ReflectionEventMsg` の sqlite 永続化
- `session_id` 概念の導入 (schema / gateway 横断改修)
- Parquet export (pyarrow 依存追加)
- DPO ペア抽出 / 選別ロジック
- `DialogTurnMsg` schema への persona_id 追加 (sink 側で解決)
- SCHEMA_VERSION bump

## 受け入れ条件

- [ ] `dialog_turns` table が `MemoryStore.create_schema()` で作成される
- [ ] `store.add_dialog_turn_sync(turn, speaker_persona_id=..., addressee_persona_id=...)`
      が duplicate (dialog_id, turn_index) で冪等 (UNIQUE 制約違反時は no-op
      または明示的に再 insert を reject)
- [ ] `InMemoryDialogScheduler` を turn_sink 付きで構築し、record_turn() 後に
      sqlite に row が追加される (unit test で検証)
- [ ] `uv run erre-sandbox export-log --format jsonl --out file.jsonl` が成功
      終了 (exit 0)、stdout モード (`--out -`) で JSONL を emit
- [ ] `--persona kant` filter が機能、`--since` filter が機能
- [ ] `uv run pytest` 全体で regression なし (現 797 PASS を維持)
- [ ] `git diff --stat main...HEAD` が src / tests / docs / .steering のみ
- [ ] SCHEMA_VERSION が変更されていない (`grep SCHEMA_VERSION src/erre_sandbox/schemas.py`
      で `0.5.0-m8` のまま)

## 関連ドキュメント

- 親 ADR: `.steering/20260424-steering-scaling-lora/decisions.md` D1
- 兄弟 spike: `.steering/20260425-m8-baseline-quality-metric/` (本 spike の
  export 出力を消費して baseline を算出)
- 関連 Skill: `architecture-rules` (memory/ レイヤー追記)、`test-standards`
  (sqlite 一時 DB)、`python-standards`
- MASTER-PLAN: L146 (M9 LoRA 前提)

## メモ: spike 粒度は暫定

L6 decisions.md の横断メモ通り、M8 spike 4 本 (本件 + baseline-quality-metric
+ scaling-bottleneck-profiling + session-phase-model) の粒度は M8 planning
session 最初に決定する保留項目。session-phase-model は PR #87 で merge 済。
本 spike は dialog_turn 永続化に特化、他 spike と独立に PR 可能。

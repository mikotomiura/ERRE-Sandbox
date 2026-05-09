# ブロッカー記録 — m9-individual-layer-schema-add

> Codex review (2026-05-09) 反映済 — D-2 削除 (本 PR で解消)、D-1 弱化 (Phase B kick を merge 後に倒す方針へ転換)

## (現状なし)

実装着手前 (Codex review 反映済) の段階。発生した blocker はここに追記する。

## 持ち越し候補 (defer、本タスク内で扱わない)

### D-1: 既存 `.duckdb` migration スクリプト (**弱化、fallback only**)

- **発生日時**: 2026-05-09 (本 PR 設計時)、改訂 2026-05-09 (Codex HIGH-3 反映で弱化)
- **症状**: 当初は「A+B 並列で Phase B を B-1 未 merge 状態で kick → 30 cell に新列なし」を想定したが、Codex HIGH-3 で **Phase B kick を PR-A merge 後に倒す** 判断 5 に転換した。これにより本来は migration スクリプト不要
- **fallback 条件**: 万一 user が PR-A merge **前** に Phase B kick を実行した場合、生成された `data/eval/golden/*.duckdb` に `individual_layer_enabled` 列が無い → `_DuckDBRawTrainingRelation.__init__` の構築時 aggregate assert で DuckDB column-not-found エラーになる risk (もしくは aggregate assert 側の skip 条件で凌ぐ)
- **対応案** (発火した場合のみ):
  - **対応 A (推奨)**: G-GEAR で `python -c "import duckdb; con=duckdb.connect('path.duckdb', read_only=False); con.execute('ALTER TABLE raw_dialog.dialog ADD COLUMN IF NOT EXISTS individual_layer_enabled BOOLEAN NOT NULL DEFAULT FALSE'); con.execute('CHECKPOINT'); con.close()"` を 30 cell に loop で適用 (DuckDB は `ALTER TABLE … ADD COLUMN ... DEFAULT ...` で既存行を default で埋める仕様、[DuckDB ALTER TABLE](https://duckdb.org/docs/1.1/sql/statements/alter_table))
  - **対応 B**: `scripts/migrate_individual_layer.py` CLI を新規作成 (idempotent、glob 経由で 30 cell に適用)
- **defer 理由**: PR-A merge 後に Phase B kick する判断 5 では migration 不要なので、本 PR には含めない
- **再開条件**: PR-A merge 前に Phase B kick が実行された場合のみ (回避は可能、user 操作の手順で明示する)
- **cross-reference**: `.steering/20260430-m9-eval-system/blockers.md` には記録しない (本 PR で解消方針確立済)

### D-4: `_seed_duckdb_with_sentinel_rows` fixture modernization (code-reviewer MEDIUM)

- **発生日時**: 2026-05-09 (PR #156 code-reviewer 指摘)
- **症状**: `tests/test_evidence/test_eval_paths_contract.py:69-103` の `_seed_duckdb_with_sentinel_rows` ヘルパーが `bootstrap_schema()` を使わず独自 11 列 DDL で `raw_dialog.dialog` を作成。新列 (`epoch_phase`, `individual_layer_enabled`, `speaker_agent_id`, `addressee_agent_id`, `reasoning`) が欠落しており、aggregate assert は skip 条件で通る。将来 `_DuckDBRawTrainingRelation.__init__` に追加 integrity check が入った場合に silent drift で false-green リスク
- **解決方法**: `_seed_duckdb_with_sentinel_rows` 内で `bootstrap_schema()` を呼び、`raw_dialog_extra_columns` poison column のみ `ALTER TABLE ADD COLUMN` で注入する形に refactor
- **defer 理由**: 本 PR scope 外 (test fixture refactor)。現状の 13 件の sentinel test は緑、本 PR の contract correctness には影響しない
- **再開条件**: M10-A scaffold タスク or test fixture modernization PR

### D-5: `_DuckDBRawTrainingRelation` に context manager protocol 未実装 (code-reviewer MEDIUM)

- **発生日時**: 2026-05-09 (PR #156 code-reviewer 指摘)
- **症状**: `_DuckDBRawTrainingRelation` (`eval_store.py:148-261`) は `close()` のみ。`AnalysisView` (line 362-367) は `__enter__/__exit__` 実装済で context manager protocol 一貫性が不揃い。test 側は `try/finally` + `relation.close()` で正しく処理されているが、`# type: ignore[attr-defined]` 付きで呼び出す形になっており保守性に影響
- **解決方法**: `_DuckDBRawTrainingRelation.__enter__/__exit__` 追加 or `RawTrainingRelation` Protocol に `close()` 追加 (Protocol 変更は scope 大)
- **defer 理由**: 本 PR の contract correctness には影響しない、refactor 範疇
- **再開条件**: M10 scope or relation API refactor PR

### D-3: M10-A scaffold (個体層 flag を立てる側)

- **発生日時**: 2026-05-09 (本 PR 設計時)
- **症状**: B-1 で schema 列追加 + DEFAULT FALSE で物理的に false が入るが、M10-A モード (個体層 evaluation epoch) で **truthy を立てる側のロジック** は未実装
- **解決方法**: M10-A scaffold タスクで `eval_run_golden.py` の INSERT 文に `individual_layer_enabled` 列を追加し、M10-A モード時に true を設定。同タスクで `assert_phase_beta_ready()` の hard-fail #3 (`EvaluationContaminationError`) + `_DuckDBRawTrainingRelation.__init__` の aggregate assert (HIGH-2) が真に working order であることを統合 test で確認
- **defer 理由**: 本 PR は schema 層のみ。M10-A は別フェーズ (m9-c-spike scope 外)
- **再開条件**: M10-A scaffold タスク起票時 (`.steering/20260430-m9-eval-system/blockers.md` ME-15 参照)

## 解消済 / 削除した defer 候補

### D-2: `_INDIVIDUAL_LAYER_COLUMN` 定数の二重定義解消 — **本 PR で解消** (Codex MEDIUM-3 反映)

当初 D-2 として defer したが、Codex MEDIUM-3 が「本 PR の自然な lockstep 拡張で defer 不要」と指摘 → 判断 7 で本 PR scope に取り込み:
- `eval_paths.py` に `INDIVIDUAL_LAYER_ENABLED_KEY: Final[str] = "individual_layer_enabled"` を追加 + `__all__` で export
- `ALLOWED_RAW_DIALOG_KEYS` 内で literal を constant 経由に置換
- `train_kant_lora.py:62` の `_INDIVIDUAL_LAYER_COLUMN` を削除し、`INDIVIDUAL_LAYER_ENABLED_KEY` を import に置換 (line 138 / 150 の参照も置換)
- 新規 test `test_individual_layer_enabled_in_allowed_keys_uses_constant` で constant 経由の使用を assert

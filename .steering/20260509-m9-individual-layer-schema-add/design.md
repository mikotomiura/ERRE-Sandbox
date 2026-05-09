# 設計 — m9-individual-layer-schema-add

> **Codex independent review (gpt-5.5 xhigh、2026-05-09)** 反映済 — Verdict: Adopt-with-changes
> HIGH 3 件 / MEDIUM 3 件 / LOW 1 件を `codex-review.md` から反映。

## 実装アプローチ

`raw_dialog.dialog` テーブルに `individual_layer_enabled BOOLEAN NOT NULL DEFAULT FALSE` 列を追加し、`ALLOWED_RAW_DIALOG_KEYS` の allow-list と DDL を **lockstep で同 commit 更新** する。`connect_training_view()` の `_DuckDBRawTrainingRelation.__init__` に **構築時 aggregate row assert** を追加して `epoch_phase=evaluation` 行 / `individual_layer_enabled IS NOT FALSE` 行を loader 層で fail-fast (Codex HIGH-2)。`assert_phase_beta_ready()` の hard-fail #2 (`train_kant_lora.py:138-145`) が production schema 経由で never-fire になることがゴール。

`INDIVIDUAL_LAYER_ENABLED_KEY` constant を `eval_paths.py` に export し、`train_kant_lora.py:62` の `_INDIVIDUAL_LAYER_COLUMN` を import に置き換え (Codex MEDIUM-3、定数二重定義解消)。Phase B kick は **PR-A merge 後に倒す** ことを推奨 (Codex HIGH-3、Migration script defer は維持するが弱化)。

## 変更対象

### 修正するファイル

- `src/erre_sandbox/contracts/eval_paths.py` (line 70-96 + new export)
  - `INDIVIDUAL_LAYER_ENABLED_KEY: Final[str] = "individual_layer_enabled"` を constant 領域に追加 (line 65 付近)
  - `ALLOWED_RAW_DIALOG_KEYS` frozenset 内で `INDIVIDUAL_LAYER_ENABLED_KEY` を使用 (literal は使わない)
  - `__all__` に `"INDIVIDUAL_LAYER_ENABLED_KEY"` を追加
  - allow-list docstring 末尾に「`individual_layer_enabled` is the DB11 / M10-A individual-layer activation flag; training-egress paths require it to be FALSE for every row (enforced by `assert_phase_beta_ready` AND construction-time aggregate assert in `_DuckDBRawTrainingRelation`).」を append
- `src/erre_sandbox/evidence/eval_store.py` (line 69-99 + 157-176)
  - `_RAW_DIALOG_DDL_COLUMNS` tuple に `("individual_layer_enabled", "BOOLEAN NOT NULL DEFAULT FALSE")` 追加 (line 84 `("epoch_phase", "TEXT")` の後) — **NOT NULL 必須** (HIGH-1)
  - import-time `_BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS` check (line 90-99) は両側同時更新で緑
  - `_DuckDBRawTrainingRelation.__init__` (line 157-176) に **構築時 aggregate row assert** を追加 (HIGH-2):
    - `SUM(CASE WHEN LOWER(epoch_phase)='evaluation' THEN 1 ELSE 0 END)` と `SUM(CASE WHEN individual_layer_enabled IS NOT FALSE THEN 1 ELSE 0 END)` を 1 SQL で集計
    - いずれも >0 なら `EvaluationContaminationError` raise (count を error message に含める)
- `src/erre_sandbox/training/train_kant_lora.py` (line 62 削除 + import 追加 + docstring 更新)
  - line 62 の `_INDIVIDUAL_LAYER_COLUMN: Final[str] = "individual_layer_enabled"` を **削除** (定数統一、MEDIUM-3)
  - `from erre_sandbox.contracts.eval_paths import INDIVIDUAL_LAYER_ENABLED_KEY` を追加し、line 138 / 150 で `_INDIVIDUAL_LAYER_COLUMN` を `INDIVIDUAL_LAYER_ENABLED_KEY` に置換
  - line 20-32 の hard-fail order docstring に「post-B-1 (m9-individual-layer-schema-add landed) では `BlockerNotResolvedError` は production schema 経由では never fire — `_DuckDBRawTrainingRelation.__init__` の aggregate assert + DDL `BOOLEAN NOT NULL DEFAULT FALSE` で防御層が拡張された旨」を追記
  - line 93-99 の `individual_layer_enabled_required` docstring を「Always True in production; tests pass False to bypass when fabricating pre-B-1 schema scenarios.」に書き換え
- `src/erre_sandbox/training/exceptions.py` (line 26-40)
  - `BlockerNotResolvedError` docstring に「protects non-bootstrap snapshots, old DuckDB artifacts, and future non-DuckDB relation implementations」を追記 (LOW-1)
- `.github/workflows/ci.yml` (line 83-123、`eval-egress-grep-gate` job)
  - 末尾に `individual_layer_enabled\s*[:=]\s*(True\|"true"\|1)` リテラル検出を追加
  - **コメントで「weak backstop only — primary guard is `_DuckDBRawTrainingRelation.__init__` aggregate assert + behavioral sentinel test」と明文化** (MEDIUM-1)
- `src/erre_sandbox/cli/eval_run_golden.py` (line 547 付近、コメントのみ追記、任意)
  - 「`individual_layer_enabled` は DDL `NOT NULL DEFAULT FALSE` で暗黙に false (M10-A 着手まで)」のコメント

### 新規作成するファイル / テスト

**`tests/test_evidence/test_eval_paths_contract.py`** に新規 test 1 件:
- `test_individual_layer_enabled_in_allowed_keys_uses_constant` — `INDIVIDUAL_LAYER_ENABLED_KEY` が allow-list に含まれる + 文字列値が `"individual_layer_enabled"` であること

**`tests/test_evidence/test_eval_store.py`** に新規 test 2 件 (DDL 検証は eval_store side、MEDIUM-2):
- `test_bootstrap_individual_layer_enabled_column_is_not_null_with_default_false` — `bootstrap_schema()` 後 `information_schema.columns` で `data_type=BOOLEAN`, `is_nullable='NO'`, `column_default='false'`/`FALSE`/`CAST('f' AS BOOLEAN)` 等 DuckDB 表記
- `test_explicit_null_insert_into_individual_layer_enabled_rejected` — `bootstrap_schema()` 後に `INSERT … VALUES (..., NULL, ...)` が DuckDB error (`NOT NULL constraint`) を raise

**`tests/test_training/test_train_kant_lora.py`** に新規統合 test 3 件 (real-DuckDB は train_kant_lora side、MEDIUM-2):
- `test_post_b1_real_relation_passes_blocker_check` — `bootstrap_schema()` → `make_kant_row()` を使い real DuckDB に **3 行のみ** INSERT (clean、`individual_layer_enabled=false`) → `connect_training_view` → `assert_phase_beta_ready(min_examples=1)` が `BlockerNotResolvedError` raise しない (return realised count >= 1)
- `test_assert_phase_beta_ready_blocks_individual_layer_true_via_real_relation` — real DuckDB に 1 truthy 行 + 数 clean 行 INSERT → `connect_training_view` で **construction time** に `EvaluationContaminationError` raise (HIGH-2 の aggregate assert で fail-fast)
- `test_assert_phase_beta_ready_blocks_evaluation_phase_via_real_relation` — real DuckDB に 1 `epoch_phase='evaluation'` 行 INSERT → `connect_training_view` で **construction time** に `EvaluationContaminationError` raise

### 削除するファイル
- なし

## 影響範囲

- **既存テスト**:
  - `test_bootstrap_creates_full_allowlist_for_raw_dialog` (line 59-71) は frozenset 厳密一致を assert → lockstep 同時更新で自動的に緑 (両側に新列が入る)
  - `test_eval_paths_contract.py` の `_seed_duckdb_with_sentinel_rows` (line 80-103) は **手書き DDL 11 列** で `individual_layer_enabled` を含まない → physical 側に列が無いのは subset check OK で互換、ただし HIGH-2 の aggregate assert は **`individual_layer_enabled` 列が存在しない場合は SQL でその列を参照できない** ので、aggregate assert を実装する際は **column が存在する場合のみ aggregate するか catch して skip する** 設計が必要 (詳細は §設計判断 1)
  - `tests/test_training/conftest.py` の `make_relation(with_individual_layer_column=False)` は引き続き `BlockerNotResolvedError` を trip (regression として価値、判断 4)
- **既存 INSERT (`eval_run_golden.py:547-571`)**: 15 列を名前指定で INSERT。新列 omit でも `BOOLEAN NOT NULL DEFAULT FALSE` で false が入る → 互換性維持 (M10-A で truthy を立てるまでは)
- **既存テスト INSERT (`tests/test_cli/test_eval_audit.py:63-100`, `tests/test_cli/test_p3a_decide.py:299` 等)**: 同上、列名指定 omit で互換
- **既存 `.duckdb` ファイル** (`data/eval/calibration/run1/*.duckdb`):
  - calibration data は training-view を経由しない (`g-gear-phase-bc-launch-prompt.md:144` で production glob と分離) → 影響なし
  - **判断 5 (Phase B kick を merge 後に倒す)** 採用で、`data/eval/golden/*.duckdb` は本 PR merge 後に G-GEAR で `bootstrap_schema()` 経由で生成 → 全て新 schema で生成される

## 既存パターンとの整合性

- **frozenset literal style + constant**: 既存 entry の trailing comma スタイル踏襲 + 新規 constant `INDIVIDUAL_LAYER_ENABLED_KEY` を export
- **DDL tuple style**: `_RAW_DIALOG_DDL_COLUMNS` の `(name, ddl_type)` 形式に揃える。`BOOLEAN NOT NULL DEFAULT FALSE` は単一文字列で OK (既存 `bootstrap_schema()` の `f'"{name}" {ddl_type}'` で展開可)
- **Aggregate assert SQL style**: 既存 `_inspect_raw_dialog_columns` (line 119-140) の `information_schema.columns` query パターンを参考に、SQL は単一 `SELECT … FROM raw_dialog.dialog` で
- **CI grep gate style**: `.github/workflows/ci.yml:83-123` の bash if grep + コメントスタイルに揃える、新規 job 作成しない
- **test fixture style**: `tests/test_evidence/conftest.py` の `tmp_path` + `_writable` ヘルパーを流用、real-DuckDB tests は `pytest.fixture(scope="function")` で per-test isolation

## テスト戦略

### TDD 順序 (RED → GREEN)

| # | テスト | 配置 | 期待される失敗 (B-1 前) | 緑への遷移 |
|---|---|---|---|---|
| R1 | `test_bootstrap_creates_full_allowlist_for_raw_dialog` (既存) | `test_eval_store.py` | allow-list と DDL の片方だけ更新だと frozenset 厳密一致が破れて赤 | G1+G2 同 commit で緑 |
| R2 | `test_bootstrap_individual_layer_enabled_column_is_not_null_with_default_false` (新規) | `test_eval_store.py` | DDL 未追加なら `information_schema.columns` に列なしで赤 | G2 で緑 (NOT NULL DEFAULT FALSE) |
| R3 | `test_explicit_null_insert_into_individual_layer_enabled_rejected` (新規) | `test_eval_store.py` | DDL 未追加または `BOOLEAN` のみだと NULL insert 通って赤 | G2 で緑 (NOT NULL) |
| R4 | `test_individual_layer_enabled_in_allowed_keys_uses_constant` (新規) | `test_eval_paths_contract.py` | allow-list 未追加または constant 未 export なら赤 | G1 で緑 |
| R5 | `test_post_b1_real_relation_passes_blocker_check` (新規統合) | `test_train_kant_lora.py` | DDL 未追加なら `BlockerNotResolvedError` で赤 | G1+G2 で緑 |
| R6 | `test_assert_phase_beta_ready_blocks_individual_layer_true_via_real_relation` (新規) | `test_train_kant_lora.py` | DDL + aggregate assert 未追加なら R5 と同じく `BlockerNotResolvedError` で赤 (truthy 行に到達する前) | G1+G2+G7 で緑 (`EvaluationContaminationError` raise at construction) |
| R7 | `test_assert_phase_beta_ready_blocks_evaluation_phase_via_real_relation` (新規) | `test_train_kant_lora.py` | aggregate assert 未追加なら construction で raise しないで Python gate に任せる挙動 | G7 で緑 (construction で fail-fast) |

### GREEN フェーズ (実装順)

1. **G1+G2 同 commit (lockstep 必須)**:
   - G1: `eval_paths.py` に `INDIVIDUAL_LAYER_ENABLED_KEY` constant 追加 + `ALLOWED_RAW_DIALOG_KEYS` で使用 + `__all__` 更新 + docstring 更新
   - G2: `eval_store.py::_RAW_DIALOG_DDL_COLUMNS` に `("individual_layer_enabled", "BOOLEAN NOT NULL DEFAULT FALSE")` 追加
2. **G3**: `train_kant_lora.py:62` の `_INDIVIDUAL_LAYER_COLUMN` 削除 + `INDIVIDUAL_LAYER_ENABLED_KEY` import 置換 + line 138 / 150 の参照置換 + line 20-32 hard-fail order docstring 更新 + line 93-99 引数 docstring 更新
4. **G4**: `exceptions.py:26-40` の `BlockerNotResolvedError` docstring 強化 (LOW-1)
5. **G5**: `.github/workflows/ci.yml` の `eval-egress-grep-gate` job に literal grep 追加 + weak backstop コメント (MEDIUM-1)
6. **G6 (任意)**: `eval_run_golden.py:547` 付近にコメント追記
7. **G7 (HIGH-2)**: `_DuckDBRawTrainingRelation.__init__` (line 157-176) に構築時 aggregate row assert 追加。SQL は `SELECT SUM(CASE WHEN LOWER(epoch_phase)='evaluation' THEN 1 ELSE 0 END), SUM(CASE WHEN individual_layer_enabled IS NOT FALSE THEN 1 ELSE 0 END) FROM raw_dialog.dialog`。`epoch_phase` / `individual_layer_enabled` 列が物理 schema に **無い** 場合は SQL を skip (subset check で OK 判定済 + B-1 schema 前のレガシー DB 互換性)

### 単体・統合・E2E
- **単体**: 新規 test 4 件 (R2, R3, R4 は schema/contract level、R5 は real DuckDB 経由、R6/R7 は HIGH-2 aggregate assert に対する整合性確認)
- **統合**: R5 + R6 + R7 は `bootstrap_schema()` → 実 DuckDB INSERT → `connect_training_view` → `assert_phase_beta_ready` 経路を end-to-end (mock 不使用)
- **E2E**: 不要 (`train_kant_lora` の inner loop は `NotImplementedError` skeleton で B-1 範囲外)

## 設計判断 (重要、`decisions.md` も参照)

### 判断 1: SQL 入口 `WHERE` filter は **追加しない**、ただし **構築時 aggregate row assert** を追加 (Codex HIGH-2 反映)

`connect_training_view()` の SQL に `WHERE` filter を組み込むと count check (`min_examples<1000`) が dilute され CS-3 order-sensitive 設計を破る。一方、column-presence assert のみだと DB11 ADR の loader-boundary contract が partial。

**採用**: `_DuckDBRawTrainingRelation.__init__` で `SUM(CASE WHEN LOWER(epoch_phase)='evaluation' THEN 1 ELSE 0 END), SUM(CASE WHEN individual_layer_enabled IS NOT FALSE THEN 1 ELSE 0 END)` を 1 SQL で aggregate し、いずれも >0 で `EvaluationContaminationError` raise。

実装 nuance: `epoch_phase` / `individual_layer_enabled` 列が物理 schema に存在しない場合は aggregate SQL をスキップ (legacy / pre-B-1 DB 互換)。aggregate query の DuckDB latency は ms オーダーで constant cost 許容。

### 判断 2: G1+G2 を **同 commit 必須** (lockstep)

import-time check が片方更新で破綻するため必須。technical 必須条件。

### 判断 3: `BOOLEAN NOT NULL DEFAULT FALSE` (Codex HIGH-1 反映)

NULL 許容では `bool(NULL or False) → False` の hole が残る。NOT NULL で物理的拒否 + DEFAULT で omit insert 互換 (`eval_run_golden.py:547` の 15 列 INSERT で omit)。bivalent contract 完全実装。

### 判断 4: 既存 regression test 保持 + `BlockerNotResolvedError` docstring 強化 (Codex LOW-1 反映)

production schema で never fire でも、別 schema 経路 (Parquet snapshot, future non-DuckDB) の防御層として regression test + Type を保持。docstring に「protects non-bootstrap snapshots, old DuckDB artifacts, future non-DuckDB relation implementations」明記。

### 判断 5: Phase B kick を **PR-A merge 後に倒す** (Codex HIGH-3 反映)

A+B 並列を「本セッション内で B-1 PR 作成 + Phase B kick prompt 確認」と再定義。kick タイミングは **PR-A merge 後に G-GEAR で `git pull` → kick** を推奨。Migration script は blockers.md D-1 として弱く保持 (万一 merge 前 kick された場合の rescue)。

### 判断 6: CI grep gate は **weak backstop only** (Codex MEDIUM-1 反映)

literal grep は `setattr` / `dict.update` / aliases / comprehensions を catch できない。primary guard は behavioral sentinel test + `_DuckDBRawTrainingRelation.__init__` aggregate assert。CI gate にコメントで明文化。

### 判断 7: 定数二重定義解消を本 PR に含める (Codex MEDIUM-3 反映)

`INDIVIDUAL_LAYER_ENABLED_KEY: Final[str]` を `eval_paths.py` に export、`__all__` に追加、`ALLOWED_RAW_DIALOG_KEYS` で使用、`train_kant_lora.py` から import。defer から本 PR scope に変更。diff cost ~15 行、blast radius 最小、lockstep 強化価値あり。

## ロールバック計画

- B-1 merge 後に `assert_phase_beta_ready()` または `_DuckDBRawTrainingRelation.__init__` が production schema で予期せぬ raise を起こした場合:
  1. `feature/m9-individual-layer-schema-add` を revert (G1+G2 + G7 commit を含む)
  2. `_BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS` import-time check が必ず lockstep を担保するので、片方だけ revert する事故は起きない
- CI grep gate (.github/workflows/ci.yml) が誤検出した場合:
  - regex を緩める or 該当 PR で false positive を `# noqa` 等で抑制
- 構築時 aggregate assert が legacy DB を誤って弾いた場合:
  - 列存在チェック (`if "epoch_phase" in physical_columns and "individual_layer_enabled" in physical_columns`) で skip 条件を緩める or assert を Python 級に移す
- 万一 `BOOLEAN NOT NULL DEFAULT FALSE` syntax が DuckDB 1.x で問題を起こした場合:
  - `BOOLEAN DEFAULT FALSE` に後退 (NULL 許容)、test を `is_nullable='YES'` に書き換え

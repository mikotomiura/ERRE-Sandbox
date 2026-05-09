# m9-individual-layer-schema-add

## 背景

ERRE-Sandbox の M9 Phase C-spike (`m9-c-spike`) の K-α (mock-LoRA infrastructure proof on WSL2) は PR #155 で merge 完了した (origin/main HEAD = `ac40411`)。次フェーズ K-β (real Kant training trigger) は **2 つの hard blocker** で gate されている:

- **B-1**: `m9-individual-layer-schema-add` (本タスク) — `assert_phase_beta_ready()` の hard-fail #2 (`BlockerNotResolvedError`、列 `individual_layer_enabled` absent 検出) を production schema 経由で never-fire にする schema 契約追加
- **B-2**: M9-eval P3 golden baseline 完了 (`min_examples ≥ 1000`) — `m9-eval-system` の Phase B + C 完了で解消 (本タスク範囲外)

DB11 ADR (PR #145, `.steering/20260430-m9-b-lora-execution-plan/cognition-deepen-decision-2026-05-08`) の cognition deepening contamination prevention は contract / docstring の更新は完了したが、**schema enforcement (DDL に列を追加 + allow-list lockstep) は別タスクに defer されていた**。これを Codex P4a MEDIUM-3 が「ADR と schema lockstep 違反」として再指摘した。本タスクが解消する。

## ゴール

- `src/erre_sandbox/contracts/eval_paths.py::ALLOWED_RAW_DIALOG_KEYS` と `src/erre_sandbox/evidence/eval_store.py::_RAW_DIALOG_DDL_COLUMNS` に `individual_layer_enabled` (BOOLEAN, default false) を **同 commit で lockstep 追加** する。
- `assert_phase_beta_ready()` の 4 種 hard-fail のうち **#2 (`BlockerNotResolvedError`)** が production DuckDB schema 経由では never-fire になる。test fixture 経由の mock relation (`with_individual_layer_column=False`) では引き続き fire するので regression test は保持される。
- CI `eval-egress-grep-gate` job に `individual_layer_enabled\s*[:=]\s*(True|"true"|1)` リテラル検出を追加。training-egress モジュール内の意図しない truthy 設定を mechanical に検出。
- 行動的 sentinel test を追加 (実 DuckDB に truthy 行を植えて `EvaluationContaminationError` raise を確認)。

## スコープ

### 含むもの
- `eval_paths.py` allow-list 1 列追加 + docstring 更新
- `eval_store.py` DDL 1 列追加 (BOOLEAN DEFAULT FALSE)
- `train_kant_lora.py` docstring のみ更新 (コード変更なし)
- `.github/workflows/ci.yml` の `eval-egress-grep-gate` job に literal grep 追加
- `tests/test_evidence/test_eval_paths_contract.py` に新規 test 2 件
- `tests/test_evidence/test_eval_store.py` に新規 test 1 件
- `tests/test_training/test_train_kant_lora.py` に新規統合 test 1 件 (実 DuckDB 経由)

### 含まないもの
- `connect_training_view()` への SQL `WHERE` filter 追加 (§設計判断 1 で却下、多層防御の単純性を理由に)
- 既存 `.duckdb` ファイル (`data/eval/golden/`, `data/eval/calibration/run1/`) への ALTER TABLE migration スクリプト (§Migration 問題 で別 PR に defer)
- `eval_run_golden.py:547` INSERT 列リスト更新 (列名指定 omit + `BOOLEAN DEFAULT FALSE` で互換、コメント追記のみ)
- M10-A scaffold (個体層 flag を立てる側、defer)
- B-2 (Phase B + C データ採取) 着手
- 8-mode FSM smoke 拡張 (m9-c-spike 候補 C、価値低)
- `_INDIVIDUAL_LAYER_COLUMN` 定数の二重定義解消 (REFACTOR は scope 外)

## 受け入れ条件

- [ ] `pytest tests/test_evidence/test_eval_store.py::test_bootstrap_creates_full_allowlist_for_raw_dialog` 緑 (lockstep 同時更新で frozenset 厳密一致)
- [ ] `pytest tests/test_evidence/test_eval_paths_contract.py -k 'allow or individual_layer'` 全緑
- [ ] `pytest tests/test_evidence/test_eval_store.py -k 'bootstrap or individual_layer'` 全緑
- [ ] `pytest tests/test_training/test_train_kant_lora.py` 全緑 (regression `test_individual_layer_column_absent_raises_blocker_not_resolved` 含む 7 件以上)
- [ ] 新規統合 test `test_assert_phase_beta_ready_blocks_individual_layer_true_via_real_relation` 緑 (実 DuckDB 経由で truthy 行 → `EvaluationContaminationError` raise)
- [ ] `ruff check src tests` 緑、`ruff format --check src tests` 緑、`mypy src` 緑
- [ ] CI `eval-egress-grep-gate` job が PASS で B-1 sentinel guard を含むメッセージを出す
- [ ] PR-A 作成、`/review-changes` skill (code-reviewer + security-checker) 通過
- [ ] Codex independent review 起動 (実装着手前) → HIGH 全反映 / MEDIUM `decisions.md` 採否記録 / LOW `blockers.md` 持ち越し可

## 関連ドキュメント

- `docs/architecture.md` の DuckDB single-file + named schema 4 層 contract 節
- `docs/development-guidelines.md` の TDD・Conventional Commits・main 直 push 禁止節
- `.steering/20260508-m9-c-spike/blockers.md` §B-1 — 本タスクの正確な scope 出典
- `.steering/20260508-m9-c-spike/k-alpha-report.md` — K-α retry merge 後の Mac side ADR adopt 待ち項目
- `.steering/20260430-m9-eval-system/blockers.md` ME-15 (DB11) — M10-A 同期待ち項目
- `.steering/20260430-m9-b-lora-execution-plan/decisions.md` DB11 — cognition deepening contamination prevention ADR
- `.claude/plans/m9-c-spike-pr-155-eventual-yeti.md` — 本タスクの Plan

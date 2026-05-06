# タスクリスト — m9-eval-cli-partial-fix

## Phase 0: 準備 / 状況把握
- [ ] `cli-fix-and-audit-design.md` (spec) を再読
- [ ] `decisions.md` ME-9 ADR を再読
- [ ] `blockers.md` active incident を再読
- [ ] `codex-review-phase2-run0-timeout.md` の HIGH 4 件を再読
- [ ] `eval_run_golden.py` 現行コードを Read (特に `_SinkState`, `_watchdog`,
  `CaptureResult`, `_async_main`, `_resolve_output_paths`)
- [ ] `eval_run_master_runner` の return-code ハンドリング箇所を Grep
- [ ] file-finder で sidecar / `.capture.json` 既存参照の有無を確認
- [ ] `g-gear-p3-launch-prompt.md` 現行内容を Read

## Phase 1: 設計 (Plan mode + Opus)
- [ ] Plan mode (Shift+Tab×2) + Opus に切替
- [ ] 案 A (soft_timeout 分離 + sidecar、ADR 現案) を design.md に展開
- [ ] 案 B (lifecycle hook で contract layer 化) を design.md に展開
- [ ] **`/reimagine` 発動** → 案 C (ゼロ再生成) を追加
- [ ] 3 案を構造的 trade-off / test 可観測性 / caller 影響 / M9-B 再利用性 で比較
- [ ] 採用案 (またはハイブリッド) を確定 → `design-final.md` に分離
- [ ] Plan 承認 (ユーザー確認)

## Phase 2: 着手前 Codex independent review (必須)
- [ ] `codex-review-prompt-cli-fix.md` 起票
  (spec ref + 採用案 + 報告フォーマット HIGH/MEDIUM/LOW)
- [ ] `cat ... | codex exec --skip-git-repo-check` で Codex `gpt-5.5 xhigh` 起動
- [ ] 出力を `codex-review-cli-fix.md` に **verbatim** 保存
- [ ] HIGH 反映方針を `decisions.md` に追記、MEDIUM 採否記録、LOW は
  `blockers.md` 持ち越し可
- [ ] `.codex/budget.json` 消費トークン更新

## Phase 3: 実装 — eval_run_golden.py
- [ ] `_SinkState.soft_timeout` 新設 (mutually exclusive with `fatal_error`)
- [ ] `_watchdog` 修正 (wall deadline 到達で `soft_timeout` セット、
  `fatal_error` は触らない)
- [ ] `CaptureResult` 拡張 (`soft_timeout`, `partial_capture`, `stop_reason`,
  `drain_completed`, `runtime_drain_timeout`, `selected_stimulus_ids`)
- [ ] sidecar `.capture.json` schema v1 の atomic temp+rename writer 実装
- [ ] `_async_main` return-code 体系再設計 (0 / 2 / 3、sidecar
  unconditional write)
- [ ] `--allow-partial-rescue` flag 追加、`_resolve_output_paths` の
  stale-tmp 自動 unlink を sidecar 存在下で refuse
- [ ] caller 側 (`eval_run_master_runner`) の return-code ハンドリング更新

## Phase 4: 実装 — eval_audit.py 新設
- [ ] CLI scaffold (argparse、`--duckdb` / `--duckdb-glob` / `--focal-target` /
  `--allow-partial` / `--report-json`)
- [ ] single-cell 判定ロジック (return 0/4/5/6)
- [ ] DuckDB row count cross-check (sidecar `total_rows` / `focal_observed`)
- [ ] batch mode (`--duckdb-glob` + JSON report 出力)

## Phase 5: テスト
- [ ] `tests/cli/test_eval_run_golden.py` rewrite (既存 test 影響範囲を明示)
- [ ] 新規 unit (CLI fix 5 件):
  - [ ] `test_capture_natural_wall_timeout_writes_sidecar`
  - [ ] `test_capture_natural_fatal_keeps_tmp_no_rename`
  - [ ] `test_capture_natural_complete_writes_sidecar_status_complete`
  - [ ] `test_resolve_output_paths_refuses_stale_tmp_with_sidecar`
  - [ ] `test_async_main_return_code_partial`
- [ ] `tests/cli/test_eval_audit.py` 新設 (audit 7 件):
  - [ ] complete + focal >= target → 0
  - [ ] complete + focal < target → 6
  - [ ] partial + `--allow-partial` → 0
  - [ ] partial without flag → 6
  - [ ] missing sidecar → 4
  - [ ] DB / sidecar mismatch → 5
  - [ ] batch JSON report
- [ ] 統合: 実 ollama mock client で wall=30s partial 端到端
- [ ] `pytest -q` 全 PASS / `ruff check` / `ruff format --check` / `mypy` 全 PASS

## Phase 6: レビュー
- [ ] code-reviewer subagent で内部レビュー
- [ ] security-checker subagent で sidecar I/O / stale-tmp rescue を確認
- [ ] HIGH 指摘への対応

## Phase 7: ドキュメント
- [ ] `g-gear-p3-launch-prompt.md` を新 contract で更新
  (wall budget / run1 calibration step / audit step)
- [ ] `docs/development-guidelines.md` に CLI return-code 規約追記 (必要なら)
- [ ] PR description draft (spec / Codex review / rewrite 範囲を明示)

## Phase 8: 完了処理
- [ ] `design-final.md` の最終化
- [ ] `decisions.md` の追記 (採用案根拠 + Codex MEDIUM 採否)
- [ ] commit (Conventional Commits、`Refs:` で spec / ADR を参照)
- [ ] PR 作成 → CI green 確認 → 自分でレビュー → squash merge
- [ ] memory 更新 (本タスク完了サマリ)

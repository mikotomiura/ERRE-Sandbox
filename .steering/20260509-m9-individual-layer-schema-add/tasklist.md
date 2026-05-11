# タスクリスト — m9-individual-layer-schema-add

> Codex review (2026-05-09) 反映済 — HIGH 3 件 / MEDIUM 3 件 / LOW 1 件を反映、test placement と DDL 仕様を更新。

## 準備
- [x] 関連 docs を読む (`docs/architecture.md` DuckDB 4 層 contract, `docs/development-guidelines.md` TDD/Conventional Commits)
- [x] Critical files の現状確認 (`eval_paths.py`, `eval_store.py`, `train_kant_lora.py`, `ci.yml`, `conftest.py`, `test_eval_paths_contract.py`)
- [x] Plan 確定 (`.claude/plans/m9-c-spike-pr-155-eventual-yeti.md`)
- [x] requirement.md / design.md / blockers.md / decisions.md 起票 (Codex review 反映済)

## Codex independent review (実装着手前)
- [x] `codex-review-prompt.md` 作成 (設計判断 + 8 specific points を verbatim、HIGH/MEDIUM/LOW format)
- [x] `cat codex-review-prompt.md | codex exec --skip-git-repo-check` で起動
- [x] 出力を `.steering/20260509-m9-individual-layer-schema-add/codex-review.md` に verbatim 保存 (43 行)
- [x] HIGH 反映 (HIGH-1 NOT NULL / HIGH-2 構築時 aggregate assert / HIGH-3 Phase B kick を merge 後に倒す)
- [x] MEDIUM 採否記録 (MEDIUM-1 weak backstop / MEDIUM-2 test placement / MEDIUM-3 定数統一を本 PR に)
- [x] LOW 持ち越し or 反映 (LOW-1 docstring 強化を本 PR に反映)
- [x] design.md / decisions.md / blockers.md を Codex review 反映で update

## 実装 (RED → GREEN)
- [x] `feature/m9-individual-layer-schema-add` ブランチ作成 (main `ac40411` から)
- [ ] **R1-R7**: RED テスト追加 → 全部赤を確認
  - [ ] `test_individual_layer_enabled_in_allowed_keys_uses_constant` (test_eval_paths_contract.py、判断 7 で `INDIVIDUAL_LAYER_ENABLED_KEY` constant 経由を assert)
  - [ ] `test_bootstrap_individual_layer_enabled_column_is_not_null_with_default_false` (test_eval_store.py、HIGH-1)
  - [ ] `test_explicit_null_insert_into_individual_layer_enabled_rejected` (test_eval_store.py、HIGH-1)
  - [ ] `test_post_b1_real_relation_passes_blocker_check` (test_train_kant_lora.py、real DuckDB、MEDIUM-2)
  - [ ] `test_assert_phase_beta_ready_blocks_individual_layer_true_via_real_relation` (test_train_kant_lora.py、real DuckDB、HIGH-2)
  - [ ] `test_assert_phase_beta_ready_blocks_evaluation_phase_via_real_relation` (test_train_kant_lora.py、real DuckDB、HIGH-2)
- [ ] **G1+G2 同 commit (lockstep 必須)**:
  - [ ] G1: `eval_paths.py` に `INDIVIDUAL_LAYER_ENABLED_KEY: Final[str]` 追加 + `ALLOWED_RAW_DIALOG_KEYS` で使用 + `__all__` 更新 + docstring 更新
  - [ ] G2: `eval_store.py::_RAW_DIALOG_DDL_COLUMNS` に `("individual_layer_enabled", "BOOLEAN NOT NULL DEFAULT FALSE")` 追加
- [ ] **G3**: `train_kant_lora.py:62` の `_INDIVIDUAL_LAYER_COLUMN` 削除 + `INDIVIDUAL_LAYER_ENABLED_KEY` import + line 138/150 参照置換 + hard-fail order docstring 更新 + 引数 docstring 更新
- [ ] **G4 (LOW-1)**: `exceptions.py:26-40` の `BlockerNotResolvedError` docstring 強化 (post-B-1 purpose 明記)
- [ ] **G5 (MEDIUM-1)**: `.github/workflows/ci.yml` の `eval-egress-grep-gate` job に literal grep 追加 + weak backstop コメント
- [ ] **G6 (任意)**: `eval_run_golden.py:547` 付近にコメント追記 (M10-A 担当者向け)
- [ ] **G7 (HIGH-2)**: `_DuckDBRawTrainingRelation.__init__` (line 157-176) に構築時 aggregate row assert 追加 (`SUM(CASE …)` × 2 で eval_count + truthy/null ind_count、>0 で `EvaluationContaminationError`)。物理列に存在しない場合は SQL skip (legacy DB 互換)

## テスト
- [ ] `pytest tests/test_evidence -v` 全緑
- [ ] `pytest tests/test_training -v` 全緑 (regression `test_individual_layer_column_absent_raises_blocker_not_resolved` 含む 7+ 件)
- [ ] `pytest tests/test_cli/test_eval_audit.py` 全緑 (既存 INSERT 互換確認)
- [ ] smoke: `uv run python -c "from erre_sandbox.contracts.eval_paths import ALLOWED_RAW_DIALOG_KEYS, INDIVIDUAL_LAYER_ENABLED_KEY; assert INDIVIDUAL_LAYER_ENABLED_KEY in ALLOWED_RAW_DIALOG_KEYS"`

## 静的解析
- [ ] `uv run ruff check src tests` 緑
- [ ] `uv run ruff format --check src tests` 緑
- [ ] `uv run mypy src` 緑

## レビュー
- [ ] `/review-changes` skill 経由で code-reviewer + security-checker 起動
- [ ] HIGH 指摘への対応
- [ ] (任意) Codex review 第 2 ラウンド (実装完了後の差分 review、`codex-review-round2-prompt.md` 経由)

## ドキュメント
- [x] design.md の Codex review HIGH 反映済を最終化
- [x] decisions.md の MEDIUM 採否記録 (判断 6, 7 を新規追加、判断 1, 3, 4, 5 を update)
- [x] blockers.md の defer 項目記載 (D-2 削除、D-1 弱化、D-3 維持)

## PR 作成
- [ ] `git push -u origin feature/m9-individual-layer-schema-add`
- [ ] `gh pr create` with PR body referencing `codex-review.md` + `design.md` + `decisions.md` 判断 7 件
- [ ] CI 全緑確認 (`lint` / `typecheck` / `test` / `eval-egress-grep-gate`)

## ハンドオフ (本タスク完了時)
- [ ] `.steering/20260508-m9-c-spike/blockers.md` の §B-1 を「PR-A 出題済 → merge 待ち」に更新
- [ ] **重要**: PR-A merge 後の手順を user に明示 (判断 5 反映):
  1. main merge 後、G-GEAR で `git pull origin main`
  2. `.steering/20260430-m9-eval-system/g-gear-phase-bc-launch-prompt.md` §Phase B 通り kick (~3-5h)
  3. Phase B 完了確認後、Phase C kick (~24-48h overnight×2)
- [ ] `.claude/memory/MEMORY.md` 更新は不要 (B-1 merge は M9-c-spike の常態化変更、memory には残さない)

## Phase B 採取 (2026-05-09 G-GEAR セッション、判断 5 + 判断 8 反映)
- [x] **B kick 環境転換**: WSL2 NAT mode で Ollama 127.0.0.1 不通 → Windows native + `PYTHONUTF8=1` + Git Bash GNU `timeout` で kick (判断 8)
- [x] **既存 partial 退避**: 41 ファイルを `data/eval/partial/` へ移動 (15 stimulus duckdb cycle-count=3 fail + 3 natural .tmp + 18 logs + walltimes + meta)
- [x] **Phase B 15 cell 採取**: 80.5 min wall (5 min/cell × 15)、全 cell focal=504, status=complete
- [x] **audit gate**: `_audit_stimulus.json` 15/15 complete、partial=0、fail=0、overall_exit_code=0
- [x] **md5 receipt**: `_checksums_phase_b.txt` 31 行 (15 .duckdb + 15 sidecar + 1 audit json) を CHECKPOINT 後に生成
- [x] **commit + push**: `feature/m9-eval-phase-b-stimulus-baseline` (commit `2812285`) で receipt + audit のみ commit、`.duckdb` / sidecar 本体は .gitignore 除外 + Phase C 統合 PR まで defer
- [x] **decisions.md 判断 8 追記**: WSL2→Windows native 転換 + Phase C 別セッション defer の理由を verbatim 記録
- [x] **next-session-prompt-phase-c.md 生成**: Phase C kick 用 handoff prompt (Phase B 実測値 + Windows native パターン明示)

## Defer (別 PR / 別タスク)
- [ ] **既存 `.duckdb` migration スクリプト** (D-1、**fallback only**) — Phase B kick が PR-A merge **前**に行われた場合の rescue 用。判断 5 採用で本来不要、Phase B kick が judgement 通り merge 後に行われたため未発火
- [ ] **M10-A scaffold (個体層 flag を立てる側)** (D-3) — `eval_run_golden.py` の INSERT で M10-A モード時に `individual_layer_enabled=true` を設定する側のロジック。本 PR は schema 層のみ
- [ ] **B-2-C Phase C 採取 (multi-session、判断 9 反映)** — G-GEAR で `next-session-prompt-phase-c-revised.md` 通りに kick (Windows native + sequential、`timeout 360m`、~3-5h/cell × 15 cell = ~50-75h、4-5 セッション)。run0 から run4 まで run 単位で分割、各セッション末に audit + commit
  - [x] C-1: run0 × 3 persona (kant/nietzsche/rikyu)、実測 15h 17min (kant 5h7m + nietzsche 5h3m + rikyu 5h6m、判断 9 ~5h/cell 予測一致)、audit 3/3 PASS
  - [x] C-2: run1 × 3 persona、実測 15h 51min (kant 5h13m + nietzsche 5h25m + rikyu 5h13m)、audit 3/3 PASS
  - [x] C-3: run2 × 3 persona、実測 15h 29min (kant 5h11m + nietzsche 5h7m + rikyu 5h11m)、audit 3/3 PASS
  - [ ] C-4: run3 × 3 persona、~12-15h
  - [ ] C-5: run4 × 3 persona + Phase E 統合 PR、~12-15h
- [ ] **Phase E 統合 PR** — Phase C 完了後、Phase B + C = 30 cell まとめて `feature/m9-eval-p3-golden-baseline-complete` で起票 (`g-gear-phase-bc-launch-prompt.md §Phase E` 参照)

## Phase C kick 失敗 (2026-05-09 G-GEAR セッション、判断 9 反映)
- [x] **C kick wall budget 仮定誤り発覚**: `next-session-prompt-phase-c.md` の 5-10 min/cell 仮定で kick → kant_natural_run0 が 89.5 min で focal_target=500 未到達 (438 行)、`timeout 90m` で kill (rc=124)
- [x] **observed throughput**: natural は ~5 dialog 行/min (Phase B stimulus ~100 focal/min と桁違い)、原因仮説は free-form open-ended dialog + 高頻度 reflection trigger + 3-agent triad
- [x] **判断 9 起票**: ~5h/cell wall budget 前提で multi-session 化、`timeout 360m` (6h cap) + run 単位分割、`--turn-count 500` 維持で B/C parity 確保
- [x] **B-2-C blocker 起票**: blockers.md にアクティブ blocker として記録、解消条件は run0..run4 完了
- [x] **partial cleanup 方針**: 既存 .tmp は削除して fresh kick (rescue で部分 dialog 継承すると continuity が壊れる)
- [x] **next-session-prompt-phase-c-revised.md 生成**: multi-session handoff prompt、state 判定セクション + run-by-run 分割実行手順
- [x] **session record commit**: decisions/blockers/tasklist/runlog/handoff を `feature/m9-eval-phase-b-stimulus-baseline` に追加 commit (Phase C 採取物 0 件、PR なし)

## 解消済 (本 PR で取り込み)
- [x] **`_INDIVIDUAL_LAYER_COLUMN` 定数の二重定義解消** (D-2) — Codex MEDIUM-3 反映で defer 取消、判断 7 として本 PR scope に取り込み

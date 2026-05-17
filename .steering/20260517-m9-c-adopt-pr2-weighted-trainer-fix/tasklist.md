# タスクリスト — PR-2 WeightedTrainer Blocker 2 fix

## 準備
- [x] `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜DA16-4 を Read
- [x] `.steering/20260517-m9-c-adopt-da16-design/design.md` PR-2 section を Read
- [x] `.steering/20260517-m9-c-adopt-da16-design/blockers.md` 持ち越し 1 を Read
- [x] `.steering/20260517-m9-c-adopt-da16-design/codex-review.md` を Read
- [x] `src/erre_sandbox/training/weighting.py:411-462` を Read
- [x] `src/erre_sandbox/training/train_kant_lora.py:1687-1715` を Read
- [x] `tests/test_training/test_weighted_trainer.py` を Read
- [x] memory `project_plan_b_kant_phase_e_a6.md` を確認
- [x] memory `feedback_pre_push_ci_parity.md` を確認

## ブランチ・ステアリング
- [x] `feature/m9-c-adopt-pr2-weighted-trainer-fix` branch (main 派生) 作成
- [x] `.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/` 5 標準 file
      を起票

## 実装
- [ ] `weighting.py:462` の reduce 式を `.mean()` に変更
- [ ] `weighting.py:412-442` の docstring を新意味論で更新
- [ ] `test_weighted_trainer.py:32-52` の helper を per-example margins
      対応 (DP2-1)
- [ ] 既存 test 2 件の expected を `.mean()` 基準に書き換え
- [ ] 既存 test の comment (L102-111, L138-144) を新式数式 + HIGH-2
      言及で更新
- [ ] 新規 test 1: `..._batch1_weight_changes_loss_magnitude` 追加
- [ ] 新規 test 2: `..._batch1_gradient_norm_scales_with_weight` 追加
- [ ] 新規 test 3: `..._batch2_per_example_loss_differs_weight_takes_effect`
      追加

## 検証
- [ ] `train_kant_lora.py:1687-1715` の `WeightedTrainer.compute_loss`
      が無変更を確認 (call site API contract 不変)
- [ ] `pre-push-check.ps1` 4 段全 pass 確認:
      - [ ] ruff format --check src tests
      - [ ] ruff check src tests
      - [ ] mypy src
      - [ ] pytest -q (既存 1510 + 新規 3 = ~1513 件)

## Codex independent review (WSL2 経由必須)
- [x] `codex-review-prompt.md` 起票 (HIGH/MEDIUM/LOW format 指定)
- [x] WSL2 経由で起動 (Linux native codex CLI v0.130.0、xhigh reasoning
      effort、CODEX_HOME=/mnt/c/Users/johnd/.codex で Windows auth.json 流用)
- [x] `codex-review.md` verbatim 保存 (verdict: **ADOPT-WITH-CHANGES**,
      HIGH 1/2/3 全て none)
- [x] MEDIUM-1 反映: weighting.py docstring を tighten (compute_example_
      weight が mean=1 を guarantee しないこと + batch≥2 "nearly identical"
      が in-expectation でしか成立しないこと + small batch では local
      mean(weights) で scale が変動するという caveat を明記)
- [x] LOW-1 反映: train_kant_lora.py:1697-1706 comment を更新 (shift/
      recompute contract は HIGH-C verbatim 維持、reducer は DA-16
      ADR DA16-2 で意図的に変更されたことを明記)

## 続 PR-3 用 handoff
- [ ] `next-session-prompt-FINAL-pr3-kant-r8-v4-retrain.md` 起票

## 完了処理 (commit + push + PR)
- [ ] memory `project_plan_b_kant_phase_e_a6.md` を PR-2 status で update
- [ ] git add + commit (Conventional Commits、scope=m9-c-adopt)
- [ ] git push origin feature/m9-c-adopt-pr2-weighted-trainer-fix
- [ ] `gh pr create --base main` で PR 作成 (codex-review.md リンク)
- [ ] PR URL を user に返却

## 持ち越し (本 PR scope 外、続 PR で扱う)
- kant_r8_v4 retrain 実行 (PR-3 scope、~5h GPU)
- DA-14 rerun verdict (PR-4 scope)
- rank=16 spike (PR-5 scope、PR-4 REJECT 時のみ)
- nietzsche / rikyu Plan B 展開 (PR-4 ADOPT 後の別 ADR)

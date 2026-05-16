# タスクリスト — Plan B design + driver

## 準備
- [x] 必須 input file 11 件読了 (verdict / decisions / design / DA-11/13/14
      / DI-1〜5 / dataset.py / weighting.py / tier_b_pilot.py /
      validate_multiturn_shards.py)
- [x] feature/m9-c-adopt-plan-b-driver branch (main 派生)
- [x] .steering/20260517-m9-c-adopt-plan-b-design/ 5 標準 file scaffold

## 設計 (Plan mode + /reimagine)
- [x] V1 design.md (collector prompt + blend ratio + corpus gate +
      hyperparams + D-2 allowlist)
- [x] V2 生成 (Task tool subagent dispatch、V1 anchor leak 回避)
- [x] V1 / V2 / hybrid 採用判定 + decisions.md DI-1 に記録

## 実装
- [x] `scripts/m9-c-adopt/de_focused_monolog_collector.py` 新規
      (Plan B-2 driver、de bias + ≥60 token + monolog/long-form prompt)
- [x] `src/erre_sandbox/training/dataset.py` 拡張 (language-stratified
      split option、optional layer)
- [x] `scripts/m9-c-adopt/audit_achieved_corpus_stats.py` 新規
      (de+en mass ≥ 0.60 + N_eff > 1500 + top 5% < 0.35 check)
- [x] `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist.json`
      新規 (HIGH-2 enforcement 継承)
- [x] G-GEAR 採取 runbook (`g-gear-runbook.md`、ENV + stimulus list +
      shard naming)

## テスト
- [x] `tests/test_scripts/test_de_focused_monolog_collector.py`
- [x] `tests/test_training/test_dataset.py` 拡張 (language-stratified
      split 動作)
- [x] `tests/test_scripts/test_audit_achieved_corpus_stats.py`
- [x] ruff + pytest pass

## レビュー
- [x] Codex independent review 起票 (codex-review-prompt.md)
- [x] codex-review.md verbatim 保存
- [x] HIGH 反映 + decisions.md に記録

## 完了処理
- [x] design.md の最終化 (hybrid 採用版)
- [x] decisions.md DI-1〜 を埋める
- [x] git add + commit + push
- [x] gh pr create

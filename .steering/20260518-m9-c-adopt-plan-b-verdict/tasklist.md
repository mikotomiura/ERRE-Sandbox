# タスクリスト

## 準備
- [x] CLAUDE.md セッション開始時行動規範を読み返す
- [x] next-session-prompt-FINAL-verdict.md を Read で取得
- [x] memory `reference_qwen3_sglang_fp8_required.md` を再確認
- [x] memory `feedback_pre_push_ci_parity.md` を再確認
- [x] `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md`
      DR-1〜DR-7 を内面化
- [x] `.steering/20260518-m9-c-adopt-plan-b-retrain/blockers.md`
      ブロッカー 1/2 を内面化
- [x] `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`
      を内面化
- [x] retrain artifact (`data/lora/m9-c-adopt-v2/kant_r8_v3/`) 検証

## 本 PR scope (prep)
- [x] `feature/m9-c-adopt-plan-b-verdict` branch を main HEAD `7f944dc`
      から分岐
- [x] `.steering/20260518-m9-c-adopt-plan-b-verdict/` 5 file 起票
- [x] retrain artifact 確認 (best_global_step=1500、
      eval_loss=0.18258875、EarlyStoppingCallback fire at step 1750)
- [x] vendi_lexical_5gram dispatch 検証 (`_load_default_kernel(
      kernel_type='lexical_5gram')` wired up in vendi.py L312-345)
- [x] blocker 1/2 の明文化 (eval shard 未生成、rescore script
      hard-coded path)
- [ ] retrain forensic JSON を track 化 (train_metadata.json /
      adapter_config.json)
- [ ] 次セッション handoff prompt
      `next-session-prompt-FINAL-eval-gen-plus-verdict.md` 作成

## NOT in scope (次 PR `feature/m9-c-adopt-plan-b-eval-gen` へ繰越)
- [ ] `rescore_vendi_alt_kernel.py` CLI flag 拡張 (`--v2-shards` /
      `--nolora-shards`、blocker 2)
- [ ] SGLang server start with kant_r8_v3 adapter load
- [ ] tier_b_pilot.py で LoRA-on / no-LoRA shards 生成 (~5h GPU)
- [ ] 4-encoder rescore (MPNet / E5-large / lexical-5gram / BGE-M3)
- [ ] Burrows / ICC / throughput cross-recompute
- [ ] encoder agreement axis 評価 (3-of-4、2 以上要件)
- [ ] kant ADOPT or Phase E A-6 verdict
- [ ] Codex independent review
- [ ] decisions.md DR-? に verdict 記録

## テスト
- 本 PR は documentation のみで unit test 追加なし

## レビュー
- [ ] code-reviewer は scope 上不要 (新 source code なし)
- [ ] Codex independent review は **次 PR** で起票
      (本 PR は documentation/artifact tracking のみのため不要)

## 完了処理
- [x] design.md / decisions.md / blockers.md の最終化 (DV-4 追加)
- [x] `pre-push-check.sh` 全 pass (4/4 段、ruff format/check + mypy +
      pytest 1502 passed + 47 skipped + 3 warnings、90s 完走)
- [ ] git commit (conventional commits format、本 PR scope を明示)
- [ ] git push + `gh pr create` で PR open

# タスクリスト

## 準備
- [x] PR #180 が main に merged 済 (SHA 51a724c) を確認
- [x] `feature/m9-c-adopt-plan-b-retrain` を main から派生
- [x] `.steering/20260518-m9-c-adopt-plan-b-retrain/` 5 標準 file 配置

## 実装 (~1h)
- [ ] `src/erre_sandbox/evidence/tier_b/vendi_lexical_5gram.py` 新規実装
- [ ] `src/erre_sandbox/evidence/tier_b/vendi.py` の `_load_default_kernel`
      に `kernel_type` kwarg 追加 + dispatch
- [ ] `src/erre_sandbox/evidence/tier_b/__init__.py` export 拡張
- [ ] `tests/test_evidence/test_tier_b/test_vendi_lexical_5gram.py` 新規 test

## テスト (~10 min)
- [ ] ruff format + check pass
- [ ] pytest `tests/test_evidence/test_tier_b/test_vendi_lexical_5gram.py` pass
- [ ] pytest `tests/test_evidence/test_tier_b/test_vendi.py` (既存 16 件) pass
- [ ] pytest `tests/test_training/` (既存 plan_b_gate 関連) pass

## G-GEAR 採取 (~3.5h)
- [ ] SGLang server 起動 (WSL2、base `Qwen/Qwen3-8B`)
- [ ] driver dry-run smoke (`--target-net 50 --max-attempts 200 --dry-run`)
- [ ] acceptance rate ~30% を確認、< 25% なら prompt augmentation
- [ ] main collection (`--target-net 250 --max-attempts 800`)
- [ ] `validate_multiturn_shards.py` で shard pass
- [ ] manifest emit 確認 (`kant_de_monolog_run0_manifest.json`)

## corpus gate pre-check (~5 min)
- [ ] `train_kant_lora --dry-run --weighted` で `weight-audit.json` 生成
- [ ] `audit_plan_b_corpus_stats.py` で `plan-b-corpus-gate.json` 生成
- [ ] gate 4 axes 全 pass を確認 (fail なら DI-α-FAIL 記録 → 再採取 / Phase E A-6)

## retrain kickoff (~20h background)
- [ ] WSL2 経由で `train_kant_lora --plan-b-gate --lang-stratified-split` を
      `run_in_background=True` で起動
- [ ] PID 記録 (`.steering/.../retrain-wsl.pid`)
- [ ] 最初の checkpoint (~step 250) で `eval_loss < initial` を確認
- [ ] retrain 中断条件 (early stopping fire / SGLang crash) の確認 procedure
      を `decisions.md` に明文化

## レビュー
- [ ] code-reviewer によるレビュー
- [ ] HIGH 指摘への対応

## ドキュメント
- [ ] 採取 manifest を `.steering/` にコピー (forensic)
- [ ] retrain stdout を `.steering/.../retrain-stdout.log` に tee

## 完了処理
- [ ] design.md の最終化
- [ ] decisions.md (本セッション固有の判断のみ)
- [ ] git commit (lexical-5gram + .steering + 採取 manifest + retrain log)
- [ ] gh pr create
- [ ] next-session-prompt (retrain 完了後の verdict 計算用) を起票

## WeightedTrainer 効率化パッチ (Plan B retrain 前の最小最適化、DR-5 / DR-6)
- [x] `WeightedTrainer.compute_loss` で `labels` を pop してから `model(**inputs)` を呼ぶ (主パッチ DR-5)
- [x] ruff format + check + mypy clean
- [x] `pytest tests/test_training/` 全 45 件 PASS (主パッチ後)
- [x] `TrainingArguments(prediction_loss_only=True)` を eval_kwargs に追加 (副パッチ DR-6)
- [x] ruff format + check + mypy clean (副パッチ後)
- [x] `pytest tests/test_training/` 全 45 件 PASS (副パッチ後)
- [x] sample weight collapse 疑いを blockers.md ブロッカー 2 に記録 (本 PR では未修正)
- [ ] G-GEAR で `--weighted --max-steps 50 --save-steps 100000 --eval-steps 100000` の前後 benchmark (主パッチのみ vs 主+副) → step/sec, peak_vram, train_loss 推移を比較
- [ ] benchmark 結果を `.steering/.../bench-pre.log` / `bench-post.log` として保存
- [ ] benchmark で副パッチが寄与しない場合は副パッチを revert する判断を decisions.md に追記

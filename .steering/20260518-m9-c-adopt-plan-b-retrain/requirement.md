# m9-c-adopt Plan B retrain prep + 採取 + kickoff

## 背景

PR #180 (`feature/m9-c-adopt-plan-b-driver`、merge SHA `51a724c`) で Plan B
design + de-monolog collector driver + 4-axis corpus gate + 5-axis post-hoc
filter が main に取り込まれた。本セッションは Plan B retrain の前提を整え、
実機 (G-GEAR) で de-monolog 採取を完走させ、retrain を overnight background
で起動するまでを scope とする。

retrain 完了後の DA-14 rerun verdict 計算は次々セッションで別 PR を起票する。

## ゴール

1. `vendi_lexical_5gram.py` (char 5-gram TF-IDF cosine kernel) を実装、D-2
   allowlist の primary encoder slot に bind 可能にする
2. G-GEAR で de-monolog 採取 (net 250、acceptance rate ~31% 想定) を完走
3. `audit_plan_b_corpus_stats.py` で Plan B corpus gate (n_eff ≥ 1500 /
   top_5 ≤ 0.35 / de+en ≥ 0.60 / de ≥ 0.30) を pre-check pass
4. `train_kant_lora --plan-b-gate --lang-stratified-split --max-steps 2500
   --eval-steps 250` を WSL2 GPU 経由で background 起動、最初の checkpoint
   で `eval_loss` が下がり始めることを確認

## スコープ

### 含むもの
- `src/erre_sandbox/evidence/tier_b/vendi_lexical_5gram.py` 新規実装 (~50-80 LOC)
- `src/erre_sandbox/evidence/tier_b/vendi.py` の `_load_default_kernel` に
  `kernel_type="lexical_5gram"` dispatch を追加 (既存 MPNet path は不変)
- `tests/test_evidence/test_tier_b/test_vendi_lexical_5gram.py` 新規 unit test
- `__init__.py` の export 拡張
- G-GEAR SGLang server 起動 (base model、LoRA load 不要)
- driver dry-run smoke で acceptance rate 測定
- main collection 完走 + manifest emit
- corpus gate pre-check
- retrain background kickoff

### 含まないもの
- retrain 完了後の DA-14 rerun verdict 計算 (~2h、次々セッション)
- Plan B verdict 文書化、kant ADOPT or Phase E A-6 移行判定
- nietzsche / rikyu の Plan B 展開
- Codex independent review (次々セッション verdict PR で起票)

## 受け入れ条件

- [ ] `feature/m9-c-adopt-plan-b-retrain` branch (main 派生、本セッション merge 後 main HEAD)
- [ ] `.steering/20260518-m9-c-adopt-plan-b-retrain/` 5 標準 file
- [ ] `vendi_lexical_5gram.py` 実装 + unit test (ruff + pytest pass)
- [ ] `vendi.py` の kernel dispatch 拡張 + 既存 test 回帰 pass
- [ ] G-GEAR SGLang server 起動確認 (base model `/v1/models` 応答 OK)
- [ ] collector dry-run で acceptance rate 測定済 (~30%)
- [ ] main collection で 250 net 達成、shard validation pass
- [ ] `plan-b-corpus-gate.json` が "pass" (4 axes 全 pass)
- [ ] retrain kickoff command 起動、最初の checkpoint で `eval_loss < initial`
- [ ] commit + push + `gh pr create` (lexical-5gram 実装 + 採取結果 + retrain log)

## 関連ドキュメント

- `.steering/20260517-m9-c-adopt-plan-b-design/design.md` (hybrid 採用版)
- `.steering/20260517-m9-c-adopt-plan-b-design/decisions.md` DI-1〜DI-8
- `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`
- `.steering/20260517-m9-c-adopt-plan-b-design/g-gear-collection-runbook.md`
- `.steering/20260517-m9-c-adopt-plan-b-design/codex-review.md` HIGH-1 反映
- `docs/architecture.md` M9 evaluation system セクション

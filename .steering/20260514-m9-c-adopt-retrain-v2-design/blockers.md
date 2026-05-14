# ブロッカー記録

> 現時点 (Step 0) で active blocker なし。
> Step 1-6 進行中に発生したものを順次記録する。

## 予期される潜在 blocker (plan-derived R1-R8)

- **R1**: training data re-extract で evaluation contamination 検出
  → `assert_phase_beta_ready()` が raise したら halt + 本 file 記録 + escalate
- **R2**: Codex token budget 超過 → 2 call split (Context+HIGH / MEDIUM+LOW)
- **R3**: `/reimagine` 3 候補 converge せず → `design-comparison.md` 作成、
  Plan mode user 承認待ち、retry 1 回まで
- **R4**: Qwen3-8B tokenizer download 失敗 → `tiktoken cl100k` proxy 採用 +
  本 file に M-1 として記録 + `corpus-analysis-kant.md` に proxy nature 明記
- **R5**: Step 1 で corpus 実は high-signal → DR-1 reversal、volume-driven (A) 採用
- **R6**: DA-14 が Codex MEDIUM で "cherry-picking" 指摘 → literature shoulder +
  empirical SGLang envelope に根拠 anchor (LoRA-on 値 NOT)
- **R7**: context > 50% → `/smart-compact` (Step 2 後 + Step 3 後)
- **R8**: scope creep (training 実行提案) → requirement.md NOT in scope 明示

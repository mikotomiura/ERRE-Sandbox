# ブロッカー記録

## ブロッカー 1: SGLang 初回起動 OOM (BF16 で Qwen3-8B が 16 GB VRAM に fit せず)

- **発生日時**: 2026-05-16 13:49 JST
- **症状**: Plan B next-session prompt 通り
  `python -m sglang.launch_server --model-path Qwen/Qwen3-8B --host 0.0.0.0
  --port 30000 --mem-fraction-static 0.85 --chunked-prefill-size 8192
  --max-running-requests 8 --disable-cuda-graph` を起動 → shards loading 後
  `RuntimeError: Not enough memory. Please try to increase
  --mem-fraction-static. Current value: mem_fraction_static=0.85` →
  child sigquit で server 停止
- **試したこと**:
  1. K-α report (`.steering/20260508-m9-c-spike/k-alpha-report.md`) の launch
     v5 invocation を確認 — `--quantization fp8` + `--max-total-tokens 2048`
     + `--max-running-requests 1` が empirical に必須と判明
  2. `scripts/m9-c-spike/launch_sglang.sh` の参照 — fp8 quant + LoRA enable
     付きが既存運用形態
- **原因**: Plan B next-session prompt に含まれる SGLang command が BF16
  default (`dtype="auto"`) であり、Qwen3-8B (≈ 16 GB BF16) が
  16 GB VRAM の RTX 5060 Ti に静的に fit しない。`mem-fraction-static`
  を上げても KV cache + activations の余裕がなく fail する。
- **解決方法**: K-α report の launch v5 invocation に準拠し、
  `--quantization fp8 --max-total-tokens 2048 --max-running-requests 1`
  を追加して再起動 (LoRA enable は Plan B 採取は base model のため省略)。
  PID 395 で再起動成功。
- **教訓**:
  - Qwen3-8B + 16 GB VRAM SGLang 起動は **常に fp8 必須**。Plan B / Plan C
    / 後続セッションの handoff prompt にも `--quantization fp8 --max-total-
    tokens 2048 --max-running-requests 1` を明文化する
  - K-α report の launch v5 が単一 source of truth、Plan A / Plan B handoff
    の SGLang command は launch v5 から **delta だけ書く** 運用に揃える
  - memory `qwen3:8b + Ollama gotchas` と並列の SGLang メモリ memo を起こす
    候補 (本 PR の reflection で検討)

## ブロッカー 2: WeightedTrainer の sample weight が batch_size=1 で構造的に相殺される疑い (本 PR では未修正、別 issue として記録のみ)

- **発生日時**: 2026-05-18 (DR-5 主パッチ調査中に派生発見)
- **症状**: `compute_weighted_causal_lm_loss` (`src/erre_sandbox/training/weighting.py:411`) は
  ```
  (per_example_loss * weights).sum() / torch.clamp(weights.sum(), min=1e-8)
  ```
  で reduce する。`per_device_train_batch_size=1` で micro-batch を作ると
  `per_example_loss` shape は `(1,)`、`weights` shape も `(1,)` で、
  `(per_example_loss[0] * w) / w = per_example_loss[0]` と weight が
  数学的に相殺される。
- **gradient_accumulation_steps=8 でも問題**: HF Trainer は各 micro-batch
  独立に `loss / grad_accum` を backward するため、micro-batch 内で
  weight を normalise する現実装では weight 効果が全 step で消失している
  可能性がある。
- **影響仮説**: DA-14 weighting (`compute_example_weight`、coefficient
  0.35/0.20/0.15/0.30、normalise to mean=1) は採用したが、実 training 上は
  unweighted average と等価に振る舞っていた可能性。DA-14 verdict REJECT
  の原因の一つが「weighting が効いていない」だった可能性も否定できない。
- **本 PR では**: 効率化ではなく学習意味論の別 issue。本 PR (DR-5 / DR-6
  WeightedTrainer 効率化) では修正しない。
- **暫定対応案 (記録のみ、本 PR scope 外)**:
  - 候補 (a): `compute_loss` 内で `per_example_loss[0] * weights[0]` を
    返す (`weights.sum()` での割り戻しを止め、batch=1 でも weight が
    勾配 magnitude に直接乗る形)。ただしこれは batch>=2 のセマンティクス
    変更を伴うため別途検討
  - 候補 (b): `gradient_accumulation_steps` スコープで micro-batch の
    weight を合算してから正規化 (HF Trainer の callback hook で実装)
  - 候補 (c): `per_device_train_batch_size>=2` の VRAM-friendly な構成
    を探索 (Qwen3-8B + NF4 + rank=8 で batch=2 が乗るか要 spike、現状
    DI-7 では VRAM 98% でほぼ無理)
- **優先度判断のタイミング**: Plan B retrain の DA-14 rerun verdict が出た
  時点。verdict ADOPT なら本 issue を保留、REJECT なら本 issue の
  fix を優先 (DA-14 が weight 不発のままだったかを切り分けるため)。
- **教訓**:
  - per-example loss reduction を実装する時、batch=1 と grad_accum>1 を
    組み合わせると weight が相殺される構造的バグを生みやすい。Codex
    HIGH-C verbatim 数式は batch>=2 を暗黙前提していたが、VRAM 制約で
    batch=1 を採用した時点で意味論が崩れていた
  - 数式単体の unit test (`test_weighted_trainer.py`) は batch=2 で
    pass するため本問題は検出できなかった。実 training context での
    意味論 test (gradient direction が weight に応答するか) を追加する
    のが本筋


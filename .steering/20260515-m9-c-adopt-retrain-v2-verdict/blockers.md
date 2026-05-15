# ブロッカー記録

## B-1: Windows-native .venv に CUDA torch なし、bf16 GPU 不可で training 早期終了

- **発生日時**: 2026-05-15 15:13 JST
- **症状**: `python -m erre_sandbox.training.train_kant_lora ... --weighted -v`
  (Windows-native `.venv` 経由) を起動したところ、Qwen3-8B checkpoint loading は
  成功するが `Trainer` 初期化時に
  `operator error: Your setup doesn't support bf16/gpu.` で exit (~5 min)。
- **試したこと**:
  1. `python -c "import torch; ..."` で確認 → torch = **2.11.0+cpu**
     (CUDA 無効)。RTX 5060 Ti 自体は nvidia-smi で正常認識。
  2. `transformers.utils.is_torch_bf16_gpu_available()` → False
     (期待通り CPU torch では False)。
  3. WSL2 Ubuntu-22.04 の `/root/erre-sandbox/.venv/bin/python` を確認
     → torch = **2.9.1+cu128**、CUDA True、bf16 True。
  4. WSL CUDA venv + Windows-side 最新 src (`PYTHONPATH=/mnt/c/ERRE-Sand_Box/src`)
     で dry-run を実行 → 同じ audit 数値 (N_eff=3886.4 等) で PASS。
- **原因**: PR #168 の retrain v2 implementation は Windows-native venv で
  開発・mypy validation されたが、Windows-native venv の torch は CPU-only であり、
  GPU training には WSL CUDA venv が必要 (前回 LoRA training も
  `data/lora/m9-c-adopt/archive/rank_8/kant/manifest.json` の output_dir
  `/root/erre-sandbox/checkpoints/...` を見ると WSL 経由だった)。
- **解決方法**: training の execution layer のみ WSL に切り替え:
  - Python: `/root/erre-sandbox/.venv/bin/python` (CUDA 有効)
  - Source: `PYTHONPATH=/mnt/c/ERRE-Sand_Box/src` (Windows-side 最新 main)
  - Data/Output paths: `/mnt/c/ERRE-Sand_Box/...` (translated)
  - dry-run audit (`--dry-run`) は両環境とも同一結果 (CPU 専用処理のため)
- **教訓**:
  - G-GEAR の Windows-native `.venv` は **GPU training 不可** (`+cpu` wheel)。
    audit / linter / mypy / dry-run 専用と心得る。
  - GPU training / SGLang serving は **WSL2 経由のみ**。
  - `data/lora/.../train_metadata.json` の output_dir パス形式 (Windows
    `data\\...` vs WSL `/mnt/c/.../` vs `/root/erre-sandbox/...`) を見れば
    どちらの環境で動いたか即判断できる。

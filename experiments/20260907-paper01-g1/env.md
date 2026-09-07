# 実行環境 (paper01 G1 外部監査)

## Python / パッケージ管理

- Python 3.11 (`pyproject.toml` `requires-python = ">=3.11,<3.12"`)
- 依存は `uv.lock` を SSOT として固定 (`uv sync --frozen`)。CI 既定は
  extras 無しで走る。I-002 (本モジュール) は stdlib のみで完結し、
  encoder は一切ロードしない。

## 二経路 (Windows / WSL2)

- Windows: `.venv/Scripts/python.exe`
- WSL2 / Linux: `.venv/bin/python`
- **本監査は CPU のみで完結する** (Gate 1 実測、2026-09-07)。encoder 4 種は
  HF キャッシュから `HF_HUB_OFFLINE=1` で load でき、GPU も sglang の
  phase-flip も不要。WSL2 GPU 経路は使わない。
- cross-platform float drift (libm 1-ULP) はあるため、JSON へ emit する
  float は量子化した上で照合する
  (`feedback_golden_crossplatform_float_drift.md` の教訓を踏襲)。

## encoder (I-003 以降で使用、本 issue では未使用)

`[eval]` extras で導入される `sentence-transformers==3.4.1` 経由:

- `sentence-transformers/all-mpnet-base-v2` (incumbent, X0/X1/X2)
- `sentence-transformers/all-MiniLM-L6-v2` (X3a)
- `intfloat/e5-small-v2` (X3b)
- `BAAI/bge-small-en-v1.5` (X3c)

CI は `[eval]` extras を入れない。判定規則の test はすべて encoder
非依存 (§7)。

## PYTHONHASHSEED

`SEED` ファイル (= `experiments/20260907-paper01-g1/SEED`) の値
(`20260907`) を `PYTHONHASHSEED` にも設定してから I-003 以降の実走を
起動すること:

```bash
export PYTHONHASHSEED=20260907
```

```powershell
$env:PYTHONHASHSEED = "20260907"
```

固定しない場合、jaccard 系候補 (X5) の集合演算がプロセスをまたいで
bit 再現しない (design-final.md §8)。

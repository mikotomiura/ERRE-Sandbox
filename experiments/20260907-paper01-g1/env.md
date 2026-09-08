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

## 最終化 (Loop I-008 / issue 008、`run.sh` 実走時点)

- **uv.lock 参照**: `sentence-transformers` は `uv.lock` (2026-09-07 時点) で
  `version = "3.4.1"`、`pyproject.toml` の `[eval]` extras 宣言
  (`>=3,<4`) と整合。`uv sync --frozen --extra eval` で本 issue の
  `.venv/Scripts/python.exe` を再現できる。
- **encoder バージョン (実測、HF キャッシュから offline load)**:
  - `sentence-transformers/all-mpnet-base-v2` (X0/X1/X2)
  - `sentence-transformers/all-MiniLM-L6-v2` (X3a)
  - `intfloat/e5-small-v2` (X3b)
  - `BAAI/bge-small-en-v1.5` (X3c)
  - いずれも `sentence-transformers==3.4.1` 経由でロード。`HF_HUB_OFFLINE=1`
    により追加ダウンロードは発生しない (Gate 1 実測済)。
- **OS (issue 008 実走機)**: Windows 11 Home 10.0.26200 (G-GEAR、
  `reference_g_gear_host.md`)、Git Bash 経由で `run.sh` を実行。Python
  3.11.15、CPU のみ (GPU 不要)。
- **実測所要時間**: `run.sh` ③ (`--audit` 1 回目) 実測 **1408 秒
  (約23分)** — real qwen3 相当のフルスケール外部コーパス x 8 候補 x
  複数 arm x 200 draws x bootstrap 10000 resamples の総量。④ (2 回目
  `--audit`) がほぼ同じ時間を要するため、`run.sh` 全体で**約 47 分**。
  2 回とも CPU のみ・追加ネットワークなし (`HF_HUB_OFFLINE=1`)。
- **cross-platform (Windows / WSL2) の相対**: 本 issue は Windows
  (Git Bash) 側での実走を正典とする。WSL2 側での L3 相当検証は
  scope 外 (issue 008 は「1 コマンド再現」の完走を Windows で確認する
  ことが Done 条件で、WSL2 での再実測は別セッションの持ち越し)。

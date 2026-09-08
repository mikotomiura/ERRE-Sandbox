# 実行環境 (paper01 scope condition)

## Python / パッケージ管理

- Python 3.11 (`pyproject.toml` `requires-python = ">=3.11,<3.12"`)
- 依存は `uv.lock` を SSOT として固定 (`uv sync --frozen`)。CI 既定は
  extras 無しで走る。I-001 (本モジュール) は stdlib のみで完結し、
  encoder は一切ロードしない。

## 二経路 (Windows / WSL2)

- Windows: `.venv/Scripts/python.exe`
- WSL2 / Linux: `.venv/bin/python`
- 本測定は G1 と同様 **CPU のみで完結する見込み** (I-002 以降で encoder を
  使う段になった時点で改めて確認する)。cross-platform float drift
  (libm 1-ULP) はあるため、JSON へ emit する float は量子化した上で照合する
  (`feedback_golden_crossplatform_float_drift.md` の教訓を踏襲)。

## 入力データ (G1 の再利用、新規取得なし)

本タスクは `experiments/20260907-paper01-g1/data/` の入力を再利用する。
SHA-256 pin と再取得手順は `data.md` を参照。

## PYTHONHASHSEED

`SEED` ファイル (= `experiments/20260908-paper01-scope-condition/SEED`) の値
(`20260908`) を `PYTHONHASHSEED` にも設定してから I-002 以降の実走を
起動すること:

```bash
export PYTHONHASHSEED=20260908
```

```powershell
$env:PYTHONHASHSEED = "20260908"
```

固定しない場合、集合演算を含む候補の結果がプロセスをまたいで bit 再現しない
(G1 design-final.md §8 と同じ理由)。

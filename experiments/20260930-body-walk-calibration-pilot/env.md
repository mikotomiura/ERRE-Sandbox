# 実行環境

- Python 3.11、`uv.lock` で固定。追加依存なし。
- 実モデル・GPU は使っていない。較正 pilot の実走・driver は起こしていない (door-close、prereg §16・user 裁定 DU-4)。

## 見取り図 (`results/decision_table.json`、2026-09-30)

- 実行は `python -m scripts.body_walk_select --decision-table --out experiments/20260930-body-walk-calibration-pilot/results/decision_table.json`。
  - マシンは G-GEAR (Windows native、16 論理コア、CPU のみ)。
  - 起動は `Start-Process -WindowStyle Hidden` (PYTHONUTF8=1・PYTHONHASHSEED=20260930)。
- 所要は 26,024 s (7.2 時間)。3 行とも door-close (prereg §13)。
- `target_sha256` は起動時に記録した、certification と同じ 14 ファイルの sha256。
  - manifest の `binding_violations` が、現在のコードとの一致を照合する。

## 変異試験の certification (`results/pilot_mutation.json`)

- 実行は `python scripts/body_walk_mutation_check.py --out experiments/20260930-body-walk-calibration-pilot/results/pilot_mutation.json`。
  - detached で起動した。
- 結果は 97 / 97 KILLED。変異の後、対象 4 ファイルが sha256 で原状復帰したことを確認した。
- 記録するもの:
  - コード 14 本・test 7 本・harness の sha256
  - 変異ごとの明細

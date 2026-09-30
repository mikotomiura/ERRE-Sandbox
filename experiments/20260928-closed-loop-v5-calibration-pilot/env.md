# 実行環境

- Python 3.11、`uv.lock` で固定。追加依存なし。
- 写像 (`run.sh`) は CPU のみ。
- 実走は prereg §8 に従う。凍結後に user 裁定 (2026-09-30、AskUserQuestion「写像まで通して実走する」) を受けて、1 回だけ行った。

## 実走時の環境 (2026-09-30、一次記録は `results/run/provenance.json`)

- **実行方法**
  - driver は `scripts/closed_loop_v5_driver.py` (main=`fcd66da`、#132)。
  - driver の sha256 は `2966e600…` で、開始時と終了時で同一。PINNED 28 ファイルは全て不変。
  - マシンは G-GEAR (Windows native)。
  - 起動は `Start-Process -WindowStyle Hidden` (PYTHONUTF8=1)。stdout / stderr は run dir の外のファイルへ redirect した。
- **実行期間と結果**
  - 期間は 2026-09-30T00:28:57Z〜00:38:05Z (UTC、約 9 分)。3,072 呼び出しを逐次に実行した。
  - 再送 0、length による打ち切り 0、exit_reason = completed。
  - 公開条件を全て満たし、`records.jsonl` に公開した (`published: true`):
    - 来歴の異常なし
    - 公開時の v2 / v4 / v5 manifest OK
    - 凍結 `validate` = computed
- **推論環境**
  - Ollama 0.32.12。
  - `qwen3:8b` の digest は `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`。開始時と終了時で同一。v2 / v3 / v4 の実走と同じ。
- **GPU**: NVIDIA GeForce RTX 5060 Ti 16 GB。起動前は 1.7 GB 使用・利用率 1% で、他の GPU 計算プロセスは無かった。
- **起動前検査** (`launch_problems()`): 空だった。つまり次を全て満たした。
  - driver certification (88/88 KILLED・登録変異の集合・sha256) が現在のファイルと一致した。
  - PINNED が HEAD と一致した。
  - v2 / v4 / v5 の凍結 manifest が `MANIFEST OK`。
- **provenance の `git_dirty: true`**: 追跡外の `tmlr-submit/`・`tmp/` によるもので、写像には使わない (v3 DE-R8 を継承)。
- **写像**: `bash experiments/20260928-closed-loop-v5-calibration-pilot/run.sh` を Git Bash で、`Start-Process -WindowStyle Hidden` で起動した。
  - 凍結 v2 → v4 → v5 manifest は `MANIFEST OK` ×3。
  - 写像を 2 回計算した (各 130 s・128 s)。出力の末尾は `[run.sh] repeat byte-identical`、exit 0。
  - 全候補が screening の 1〜3 点目で落ち、本確認に進まなかった。そのため、prereg §10 の見積もり (10 時間超) より大幅に短かった。

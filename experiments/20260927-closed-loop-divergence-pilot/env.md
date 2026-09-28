# 実行環境

- Python 3.11、`uv.lock` で固定。追加依存なし。
- 判定 (`run.sh`) は CPU のみ。
- 実走は prereg v4 §8 に従い、凍結後に user 裁定 (2026-09-28 GO) を受けて 1 回だけ行った。

## 実走時の環境 (2026-09-28、一次記録は `results/run/provenance.json`)

- **実行方法**
  - driver: `scripts/closed_loop_driver.py` (main=`451e7ff`、#128)。driver の sha256 は `52f59222…` で、開始時と終了時で同一。
  - マシン: G-GEAR、Windows native。
  - 起動: `Start-Process -WindowStyle Hidden` (PYTHONUTF8=1、stdout / stderr は run dir の外のファイルへ redirect)。
- **実行期間と結果**
  - 期間: 2026-09-28T01:42:22Z〜01:50:38Z (UTC)。
  - 2,808 呼び出しを逐次に実行した。
  - 再送 0、length による打ち切り 0、exit_reason = completed。
- **推論環境**
  - Ollama 0.32.12。
  - `qwen3:8b` の digest は `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` (開始時と終了時で同一)。
  - 以上 2 点は、v2 実走 (2026-09-26) と v3 実走 (2026-09-27) と同じ。
- **GPU**: NVIDIA GeForce RTX 5060 Ti 16 GB。起動前は 1.8 GB 使用・利用率 1% で、他の GPU 計算プロセスはなかった。AC 電源のスリープは無効。
- **起動前検査** (`launch_problems()`): 空だった。つまり次をすべて満たした。
  - driver certification (98/98 KILLED) が現在のファイルと一致。
  - PINNED が HEAD と一致。
  - v2 / v3 / v4 の凍結 manifest が `MANIFEST OK`。
- **所要の見積もり** (DR-6): plan 外の prompt・seed で 50 呼び出しを送り、0.18 s/call (約 9 分) と見積もった。
  - 使ったのは r = 11 と、合成した全成功・全試行の状態。
  - 応答は保存していないし、見ていない。本番の run dir は作っていない。
- **provenance の `git_dirty: true`**: 追跡外の `tmlr-submit/`・`tmp/` と、実走中に作られた `results/run/` によるもので、判定には使わない (v3 DE-R8 を継承)。
- **判定までの手順**: `scripts/closed_loop_judge.py` だけを使った。中身は次の 3 段で、3 段目まで進んだ。
  1. run gate: `RUN GATE OK`
  2. `bash run.sh`: 凍結 v2 / v4 manifest の照合 → 2 回の計算が byte 一致
  3. `scripts/closed_loop_describe.py`

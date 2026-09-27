# 実行環境

- Python 3.11、`uv.lock` で固定。追加依存なし。
- 判定 (`run.sh`) は CPU のみ。実走は prereg v3 §8 に従い、凍結後に user 裁定 (2026-09-27 GO) で 1 回だけ行った。

## 実走時の環境 (2026-09-27、一次記録は `results/run/provenance.json`)

- **実行方法**
  - driver: `scripts/skill_experience_driver.py` (main=`983a9ef`、#125)。driver sha256 は `8caa3136…` で、開始時と終了時で同一。
  - マシン: G-GEAR、Windows native。
  - 起動: `Start-Process -WindowStyle Hidden` (PYTHONUTF8=1、stdout / stderr はファイルへ redirect)。
- **実行期間と結果**
  - 期間: 2026-09-27T03:43:58Z〜03:50:50Z (UTC)。
  - 2,160 呼び出しを逐次に実行。再送 0、length による打ち切り 0。exit_reason = completed。
- **推論環境**
  - Ollama 0.32.12。
  - `qwen3:8b` の digest は `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` (開始時と終了時で同一)。
  - 以上 2 点は v2 実走 (2026-09-26) と同じ。
  - OLLAMA_FLASH_ATTENTION=1、OLLAMA_KV_CACHE_TYPE=q8_0、OLLAMA_NUM_PARALLEL=4 (driver は逐次なので並列は使っていない)。
- **GPU**: NVIDIA GeForce RTX 5060 Ti 16 GB。起動前に 1.3 GB 使用・利用率 0% で、他の GPU 計算プロセスはなかった。
- **起動前検査** (`launch_problems()`): 空だった。つまり次をすべて満たした。
  - driver certification (78/78 KILLED) が現在のファイルと一致。
  - PINNED が HEAD と一致。
  - 両凍結 manifest が `MANIFEST OK`。
- **provenance の `git_dirty: true`**: 追跡外の `tmlr-submit/`・`tmp/` と、実走中に作られた `results/run/` によるもので、
  判定には使わない (DE-R8)。
- **判定までの手順**: `scripts/skill_experience_run_gate.py` → `RUN GATE OK` → `bash run.sh` (2 回の計算が byte 一致)
  → `scripts/skill_experience_describe.py`。

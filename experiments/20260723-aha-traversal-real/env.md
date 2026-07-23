# M13 aha-substrate-embodiment traversal — I4 real qwen3 + real embedding channel exercise — environment / status

- **実験**: Issue 004 (I4) = traversal harness を real qwen3:8b（think=False）+ real
  nomic-embed-text（768d、local Ollama）で走らせる **channel exercise**（scripted の I1-I3
  traversal を real backend で「本物にする」だけで、emergent traversal 検証でも multi-zone
  実証でもない）。
- **apparatus**: `scripts/aha_traversal_live_capture.py --real`（`--capture`/`--verify`）+
  `src/erre_sandbox/integration/embodied/traversal_live.py`（`run_traversal_capture`
  の `inner_chat` 注入点、新設 `EmbeddingRecordReplayClient`）。
- **ADR**: `.steering/20260723-m13-aha-substrate-embodiment/design-final.md`（FROZEN、binding）。
- **前段**: I1（scripted traversal driver）+ I2（W2/W3 firing witness）+ I3（committed golden +
  W4 二層 fidelity anchor）が Ollama-free で完了済（`tests/fixtures/aha_traversal_golden/`）。

## status（2026-07-23、code path 実装完了・**sealed run 未実施 = BLOCKED**）

**I4-G1 実行ゲート: user spend ratify 未取得。real Ollama は本タスクで一度も起動していない
（`nvidia-smi` 等の GPU 確認コマンドも未実行）。**

- code path（`--real --capture` / `--real --verify`、`run_traversal_capture(inner_chat=...)`、
  `EmbeddingRecordReplayClient`）は landed・mock 化 unit test で record→replay 決定論を確認済み
  （`tests/test_integration/test_traversal_live.py::test_traversal_real_mode_replay_determinism`、
  real Ollama を一切使わない httpx MockTransport ベース）。
- **`run.ps1` は書かれているが実行されていない**（real spend、human-gated、別セッション必須）。
- **`artifacts/` は存在しない**（real 実走後にしか生じない。capture.log / manifest.json 等の
  placeholder も意図的に作成していない — 成績合わせ・fake 回避）。
- `repro.ps1`/`repro.sh`（Ollama-free replay-verify）は real 実走**後**にのみ機能する
  （`artifacts/` が空の間は読み込み対象ファイルが無く失敗する — これは期待される状態）。
- `run.ps1`/`repro.ps1`/`repro.sh` はいずれも冒頭で `PYTHONUTF8=1` を明示 set する（LOW-2 review、
  qwen3 の日本語 utterance の encoding 差異を避ける。以前は本 env.md の宣言のみで scaffold 側は
  未設定だった齟齬を解消）。

## 実走環境（封印前 pre-register 固定・実走後 tuning ゼロ、実走後に追記）

- **日時 / platform**: TBD（capture = Windows 11 native、PYTHONUTF8=1、cross-platform verify は
  WSL2 Ubuntu 22.04 継承）。
- **seed**: **0**（`run.ps1` に `--seed 0` 明示、`run_traversal_capture`/`real_capture` の既定値と
  一致・偶然の一致でなく pre-register 完全化、LOW-1 review）。
- **qwen3:8b digest / ollama version / VRAM**: TBD（実走後追記、Phase4b 踏襲）。
- **embed model**: nomic-embed-text（768d、`memory/embedding.py` 既定）。
- **uv.lock sha256**: TBD。
- **replay_checksum**: TBD（実走後追記）。

## 事前登録（design-final + Issue 004、tune-to-pass 閉塞）

- **Done = R1∧R2∧R3**（両 Plane 1 チャネルの reproducibility、`scripts/aha_traversal_live_capture.py`
  の `REAL_TRAVERSAL_DONE_FORMULA`）。
- **channel-exercise annotation = 非 gate**（`traversal_channel_exercise_summary`、distinct-zone /
  move-tick の honest count のみ、`>=K` 要求なし、toward-tuning 禁止）。
- **firing annotation = 非 gate**（side file、boolean/count のみ、verdict なし。real qwen3 は
  settle 空振りしうる = Phase 4b run1 と同型、空振りも成果として記録）。
- **stop condition**: 空振り時は 1 回まで pre-register 再走可（結果選別しない）。それ以上の
  再走・stimulus 調整は禁止。

## guard（不可侵）

construction-only、measurement 非 authorize、effect/divergence/floor/aha proxy/verdict 非算出、
「real-LLM emergent traversal が効く」「real embedding が multi-zone を生む」と主張しない
（embedding ⊥ zone routing、DA-1/DA-7）。organ 6ファイル + `two_phase_live.py` の firing witness +
`memory/embedding.py` + `inference/ollama_adapter.py` は read-only 再利用（無改変）。R-budget=0 /
holding / measurement-line CLOSE / door② UNMET・door CLOSED 不変。

# M13 live-loop I7 — real qwen3 sealed 実走 — environment / status

- **実験**: M13 live 双方向ループ閉包の I7 = 配線 (PR #89 landed) を **real qwen3:8b +
  real nomic-embed-text** で封印実走し、各 seam への到達性を live で観察する (construction)
- **apparatus**: `scripts/m13_live_loop_capture.py` (`--capture` / `--capture --real
  --confirm-spend` / `--verify`) + `src/erre_sandbox/integration/embodied/live_loop.py` +
  `src/erre_sandbox/integration/inbound.py` (**両方とも無改変・import 駆動のみ**)
- **ADR**: `.steering/20260724-m13-live-loop-closure/design-final.md` (FROZEN、binding) §5 Issue 007
- **セッション記録**: `.steering/20260904-m13-live-loop-i7-real-run/`
- **仮説接続**: これは **construction validation** (配線が real backend で各 seam に届く boolean 観察)
  であって measurement ではない。effect / detectability は C-proper 第2リンク = 凍結 measurement line
  (非測定・非再入)。借用 apparatus = Phase 4b (`two_phase_live.py` の SamplingSpy / seeded factory /
  env_pins overlay) + traversal I4 (`EmbeddingRecordReplayClient` の二チャネル record/replay)。
  凍結 `src/erre_sandbox/evidence/` は touch しない。

## honest scope (不可侵)

**land しているのは配線であって aha / emergence / effect ではない。**
I7 が全 seam 到達 + firing を live で観測しても、主張できるのは
**"wiring reached each seam (live, real qwen3)"** のみ。door② UNMET・計測ライン CLOSE・
R-budget=0・holding 不変。

さらに I7 固有の 2 境界 (manifest `observables.scope_boundary` にも埋め込み済):

1. **real なのは cognition 面のみ**。摂動は事前登録した scripted bounded 列を `InboundSink` に
   直接投入する構成で、**live Godot クライアントは使わない** (Godot send 契約は I5 で検証済、
   本機に godot バイナリ無し)。実 Godot + real qwen3 の end-to-end は別タスク (MacBook、env-gate)。
2. **wall-clock real-time セッションではない**。byte-parity 規律のため `ManualClock(start=0.0)` を使う。
   「live」= cognition チャネルが real、という意味であって実時間で回したという意味ではない。

## status (2026-09-04)

- **rehearsal (Ollama-free) = 構造緑・commit 済** (`rehearsal/`)。sealed run と **同一形状**
  (32 cognition × 20 physics tick、knob=on、1 tick あたり 1 摂動)、同一 artifact 集合、
  **同一 verify コード経路**。したがって rehearsal の緑は real bundle の verify が構造的に
  通ることの実証になる (差分は Plane 1 backend のみ)。
- **sealed real run (`artifacts/`) は未実走**。real spend は **user の ratify 待ち (hard STOP)**。
  `--real` は `--confirm-spend` 無しでは exit 2 で拒否する (規約でなく apparatus が強制)。

## 実走環境 (封印前 pre-register 固定・実走後 tuning ゼロ、実走後に追記)

- **日時 / platform**: TBD、capture = Windows 11 native (G-GEAR、`PYTHONUTF8=1`)、
  cross-platform verify = WSL2 Ubuntu (glibc) + Windows (UCRT)
- **qwen3:8b digest**: TBD (`--qwen3-model-digest` で manifest に pin)
- **ollama version**: TBD / **think**: False (`ThinkOffChatClient` 経由、`cognition/cycle.py` 無改変)
- **embed model**: `nomic-embed-text` (768d、Ollama-local)
- **VRAM**: RTX 5060 Ti 16GB
- **uv.lock sha256**: TBD (`--uv-lock-sha256` で pin)
- **replay_checksum**: TBD (実走後追記)
- **rehearsal replay_checksum**: `2ad3a39db14262a5c206f3d7930bd1f48bff59deb17f56d898c72d440aa48ecb`

## 事前登録 (sealed-run-before、`scripts/m13_live_loop_capture.py::LIVE_LOOP_OBSERVABLES` が SSOT)

- **Done = L1∧L2∧L3** (reproducibility のみ)。
  - **L1**: 32×20 tick を live qwen3:8b (think=False) + live nomic-embed-text に対して
    knob=on で完走 (exit 0)
  - **L2**: committed `decisions.jsonl` + `embedding_record.jsonl` の両 Plane 1 チャネルを、
    committed `inbound_perturbations.jsonl` から再構成した観測列で **無改変**
    `run_two_phase_capture` に replay → `replay_checksum` byte 一致・両 client
    `inner_invocations == 0`。加えて Plane L 再駆動 (`run_live_loop_capture`) が同一 checksum
  - **L3**: 同一 bundle が Windows (UCRT) / WSL Linux (glibc) で同一 artifact SHA-256
    (6 桁量子化が libm/backend drift を吸収、`feedback_golden_crossplatform_float_drift`)
- **annotation 2 種は非 gate** (side file、boolean/count のみ、Done 集合外、tune-to-pass 禁止):
  - `wiring_reachability.json` — correlation-id ごとの seam 到達性 boolean + 素の count。
    **到達性は因果ではない**。`firing_summary` / `same_tick_envelope_observed` の 2 seam は
    tick 単位の共起であって per-correlation の因果ではない (correlation-id は outbound
    wire protocol に到達しない、grill G2)
  - `two_phase_firing_annotation.json` — 本 run 自身の λ>0 tick における evaluation-phase 符号反転。
    **settle (no_eligible_tick、λ が 0 のまま) は正当な結果として正直に記録し、発火するまで再走しない**
- **verdict なし** (`verdict: null` を明示 emit)。

## 決定論 (Codex MED-5 踏襲)

- 強く主張できるのは **committed 2 チャネル replay の determinism + byte parity** であって、
  real qwen3 record の環境差完全再現ではない (過剰主張しない)。
- replay は committed 応答/ベクトルを再 serve、checksum は幾何のみ → knob 活性化は新非決定源ゼロ。
- 非決定源の封鎖: LLM = `RecordReplayChatClient`、embedding = `EmbeddingRecordReplayClient`
  (record 時に 6 桁量子化)、clock = `ManualClock(start=0.0)`、inbound `sent_at` = record-mode clock に pin
  (in-process 合成ゆえ実 send 時刻は非決定ノイズにしかならない)。

## SEED

`SEED` ファイル参照 (= 0)。`--seed` で上書き可だが sealed run は 0 固定。

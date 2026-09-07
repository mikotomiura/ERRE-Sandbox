# M13 society live-closure Issue 007 — environment / status

- **実験**: N=3 society live-closure (`society_live_loop.py`, Issues 002-006 で landed) を
  real qwen3:8b + real nomic-embed-text で封印実走するための **spend-gated ハーネス**
  (`scripts/m13_society_live_capture.py`) を用意し、**Ollama-free のリハーサルを緑にする**。
- **apparatus**: `scripts/m13_society_live_capture.py` (`--capture` / `--capture --real
  --confirm-spend` / `--verify`) + `src/erre_sandbox/integration/embodied/society_live_loop.py` +
  `src/erre_sandbox/integration/embodied/society_live.py` (**すべて無改変・import 駆動のみ**)
- **Issue**: `loop/20260906-m13-society-live-closure/issues/007.md`
- **仮説接続**: これは **construction validation**（配線が real backend で各 seam に届くかの
  boolean 観察）であって measurement ではない。effect / detectability は C-proper 第2リンクで
  凍結済 measurement line（非測定・非再入）。借用 apparatus = I7 (`m13_live_loop_capture.py`) の
  spend/provenance/overwrite ゲート設計 + traversal I4 の `EmbeddingRecordReplayClient`。
  凍結 `src/erre_sandbox/evidence/` は touch しない。

## honest scope（不可侵）

**land しているのはハーネスの配線であって aha / emergence / effect ではない。real 実走そのものは
本 issue では一度も行っていない。**

1. **real なのは（将来の ratified session で走らせた時点で）cognition 面のみ**。摂動は
   事前登録した scripted 36 通を `InboundSink` に直接投入する構成で、**live Godot クライアントは
   使わない**（この G-GEAR 機に godot バイナリが無い）。
2. **wall-clock real-time セッションではない**。`run_society_loop` 内部の
   `ManualClock(start=0.0)` を使う。
3. **real 実走の spend ratify は別ゲート**（`design-final.md` grill G4 相当）。このセッションは
   `--real` を一度も呼んでいない。`run.ps1` / `run.sh` は将来の ratified session のための
   ドキュメント化された起動スクリプトであり、**Issue 007 の一部としては実行しない**。

## status（2026-09-07 — rehearsal のみ・real 実走ゼロ）

- **rehearsal (Ollama-free) = 構造緑・commit 済** (`rehearsal/`)。sealed run と **同一形状**
  (N=3 agents × 12 cognition ticks × 20 physics ticks、36 perturbations、knob=on)、
  同一 artifact 集合、**同一 verify コード経路**。したがって rehearsal の緑は real bundle の
  verify が構造的に通ることの実証になる（差分は 2 backend オブジェクトのみ）。
- **sealed real run (`artifacts/`) = 未実行（この checkout に存在しない）**。
  `--real` は `--confirm-spend` 無しでは exit 2 で拒否する（規約でなく apparatus が強制）。
- **cross-platform (D3) の実測範囲**: committed rehearsal bundle を Linux CI に replay-verify
  させる経路で取る。**測っているのは「UCRT で bake した bytes が glibc replay で同一」であって、
  Linux 上で再 bake したのではない**（real Ollama が CI に無いので原理的に不可）。

## 事前登録（sealed-run-before、`scripts/m13_society_live_capture.py::SOCIETY_LIVE_CLOSURE_ANNOTATIONS`
が SSOT・import 時に凍結・CLI から上書き不可）

- **N=3** agents (`a_kant` / `a_nietzsche` / `a_rikyu`)、**n_cognition_ticks=12**、
  **physics_ticks_per_cognition=20**、**perturbation_count=36**、**seed=0**、**think=False**
- model = `qwen3:8b` / embed_model = `nomic-embed-text`
- **Done = L1∧L2∧L3**（reproducibility のみ。effect / aha / emergence は非測定・非主張）

## rehearsal 実測（2026-09-07、Ollama-free、committed）

| 観測 | 値 |
|---|---|
| replay_checksum | `77a4937d48d19c56cf6e9f93d7b49b092f38b55931b01616609bcff817abbba2` |
| capture_mode / real_backend / think | `scripted-rehearsal` / `False` / `False` |
| perturbation_count | 36 (N=3 × 12 tick) |
| uv.lock sha256 | `9cc70f9dc5d61f6c74c08dee4dd73815993861022a80781a75ef5d873860c0f7`
  (harness が checkout の `uv.lock` から自動導出) |
| fixed_constructor_fingerprint | `agent_states_sha256=f389ad5…417d` /
  `observation_factories_sha256=bd36fe…c35` / `personas_sha256=5a95b1…130` |
| wall_clock_real_time_session | `False` |

## sealed real run（実走後にのみ追記。2026-09-07 時点では未実行）

`run.ps1` / `run.sh` を **一度も実行していない**。以下は将来の ratified session が実行する際に
必要な環境変数のプレースホルダで、値はまだ埋まっていない:

- **qwen3:8b digest**: (未取得)
- **ollama version**: (未取得)
- **VRAM**: (未取得)
- **uv.lock sha256**: harness が checkout から自動導出（手動 pin 不要）
- **replay_checksum**: (real 実走後に追記)

## SEED

`SEED` ファイル参照 (= 0)。`SOCIETY_LIVE_SEED` は frozen module 定数で CLI から上書き不可
（AC7）。

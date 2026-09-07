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

## status（2026-09-07 更新 — **sealed real run 実施済**）

- **rehearsal (Ollama-free) = 構造緑・commit 済** (`rehearsal/`)。sealed run と **同一形状**
  (N=3 agents × 12 cognition ticks × 20 physics ticks、36 perturbations、knob=on)、
  同一 artifact 集合、**同一 verify コード経路**。したがって rehearsal の緑は real bundle の
  verify が構造的に通ることの実証になる（差分は 2 backend オブジェクトのみ）。
- **sealed real run (`artifacts/`) = 実施済（2026-09-07、別セッション
  `.steering/20260907-m13-society-live-real-run/`、user の明示 spend ratify 後）**。
  `run.ps1` exit 0 / `repro.ps1 -Real` exit 0。実走は **1 回のみ**、再走・調整なし。
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

## sealed real run 実測（2026-09-07、real qwen3:8b + real nomic-embed-text）

`run.ps1` を **1 回だけ実行**（user の明示 spend ratify 後）。exit 0。

### provenance pin

| 項目 | 値 |
|---|---|
| qwen3:8b digest | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| ollama version | `ollama version is 0.32.12` |
| VRAM | `16.0` GB (RTX 5060 Ti) |
| uv.lock sha256 | `9cc70f9dc5d61f6c74c08dee4dd73815993861022a80781a75ef5d873860c0f7`（harness 自動導出） |
| python / httpx / pydantic | `3.11.15` / `0.28.1` / `2.13.2` |

> `QWEN3_DIGEST` は `ollama show qwen3:8b --json` ではなく **`GET /api/tags` の `digest`** から
> 取得した。この機体の ollama 0.32.12 に `--json` フラグが存在しない
> (`Error: unknown flag: --json` を実測)。`run.ps1` の当該箇所は env 未設定時に出す **案内文言**
> であってコード経路ではないため、ハーネスは無改変。値は `ollama list` の ID
> (`500a1f067a9f`) の 64 hex 全長で `_QWEN3_DIGEST_RE` を満たす。

### L1（実走）— exit 0

| 観測 | 値 |
|---|---|
| capture_mode / real_backend / think | `real` / `True` / `False` |
| replay_checksum (geometry) | `8ee022197ae8959ea5092f027a2c5f2412bd4d669ee4a4f6b944d55876c12dd3` |
| society_event_log_checksum | `ec7a68a4078014bc891fd13f9a6ec30886d8c07e0506acf0513cf60bfc3aebf0` |
| inbound injected / dropped / rejected | 36 / 0 / 0 |
| LLM 呼び出し | 36（`llm_status=ok` 36/36、`llm_fell_back=False` 36/36） |
| embedding 呼び出し | 112 |
| wall（起動→完了、JST） | 12:03 → 12:05:34（約 2 分） |
| wall_clock_real_time_session | `False`（`ManualClock(start=0.0)`） |

### L2（`repro.ps1 -Real`）— exit 0

| 観測 | 値 |
|---|---|
| Plane G checksum | geometry / event_log / cognition_step_order / self_other_slot **全 match** |
| inner_invocations | LLM `{a_kant:0, a_nietzsche:0, a_rikyu:0}` / embedding `0` |
| request conformance | LLM 36/36 match・embedding 112/112 match（`sampling` は明示除外） |
| self_other segment present | 33 / 36 |
| artifact SHA-256 | 5 jsonl + `manifest.json` 再 render byte 一致 |
| 3 side file | 初回 verify で seed（`plane_g_parity` / `request_conformance` / `firing_annotation`） |

### annotation（plain count・非 gate・解釈を足さない）

| 観測 | 値 |
|---|---|
| firing: eligible_tick_count / witness | `0` / `0`（全 agent `fail_mode=no_eligible_tick`） |
| dialog envelope count | `0` |
| envelope kinds | `speech` 36 / `move` 36 / `animation` 36（計 108） |
| distinct zone（speech envelope の `zone`） | 3（`study` 1 / `peripatos` 34 / `chashitsu` 1） |
| per-agent zone | `a_kant` {study 1, peripatos 11} / `a_nietzsche` {peripatos 12} / `a_rikyu` {chashitsu 1, peripatos 11} |
| bias_fired | 36 中 1（`a_nietzsche` tick 5、`garden→peripatos`、`bias_p=0.2`） |

**settle（`no_eligible_tick`）は事前登録上の正当な結果であり、発火するまでの再走は行っていない。**

### erratum — manifest の `real_run_status` は凍結テキストで更新されない

この real bundle の `manifest.json` の `annotations.real_run_status` は
**`"NOT RUN as of Issue 007..."`** のまま。`SOCIETY_LIVE_CLOSURE_ANNOTATIONS` は
import 時に凍結された sealed-run-before 定数で、real / rehearsal のどちらの bundle にも
**verbatim で同じものが載る**設計のため。

- 文言は `as of Issue 007` と時点を明示しており、Issue 007 時点の記述としては**偽ではない**。
- ただし `annotations.L1` / `annotations.scope_boundary` が
  「**check `real_run_status` for what THIS bundle actually is**」と読者を誘導するため、
  **この bundle については誘導先が誤り**になる。
- **この bundle が real かどうかの正しい判別子は `env_pins.capture_mode == "real"` と
  `env_pins.real_backend == true`**（同じ annotations の冒頭がそう明記しており、
  `test_committed_sealed_real_bundle_verifies` が機械的に検査する）。
- **修正は本セッションでは行わない**: `verify` は凍結定数から `manifest.json` を再 render して
  byte 比較するため、annotation 文言を編集すると **committed 済の real / rehearsal 両 bundle の
  verify が落ちる**（= 再 bake が必要 = 実走の再実行に相当）。事前登録の tune-to-pass 閉包
  (S3) に触れる。`blockers.md` に持ち越す。

## SEED

`SEED` ファイル参照 (= 0)。`SOCIETY_LIVE_SEED` は frozen module 定数で CLI から上書き不可
（AC7）。

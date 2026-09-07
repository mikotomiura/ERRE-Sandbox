# M13 society live-closure Issue 007 — notes

> **現在の状態（2026-09-07 更新）**: sealed real run は **実施済**
> (`.steering/20260907-m13-society-live-real-run/`、user の明示 spend ratify 後に 1 回のみ)。
> **本ファイルの「Issue 007」と書かれた記述は Issue 007 時点（ハーネス land 時）のもの**で、
> 当時の事実として残してある。実走の実測値は下の
> 「sealed real run（real qwen3:8b + real nomic-embed-text）— 2026-09-07 実施済」節、
> および `env.md`「sealed real run 実測」節（SSOT）を見ること。

## 検証する仮説 / 位置づけ

これは **仮説検証 (measurement) ではない**。`docs/research-positioning.md` §5 の H に対する
verdict を出す実験ではなく、**construction validation** = 「Issues 002-006 で land した
N 体 society live-closure 配線 (`society_live_loop.py`) が、real backend (qwen3:8b +
nomic-embed-text) を挿しても各 seam に届き、決定論的に再構成できる」ことを確かめる
**ハーネス**を用意することの boolean 観察である。**本 issue では real backend を一度も
呼んでいない** — land しているのはハーネスのコードパスと、その正しさの実証である
Ollama-free rehearsal の緑のみ。

- 計測ライン (effect / detectability / divergence) は **C-proper で CLOSE 済**
  (`project_m13_c_proper` / `project_m13_post_cproper_disposition`) であり、本ハーネスは
  再入しない。
- aha は `project_aha_jlens_metric_wellposedness` で close 済。本ハーネスは aha を主張しない。
- door② UNMET・R-budget=0・holding は不変。

## 借用 apparatus / 出典

- I7 (`scripts/m13_live_loop_capture.py`、`experiments/20260904-m13-live-loop-live/`) —
  spend gate (`capture()` 本体に置く、CLI 迂回の直呼びも拒否) / provenance pin
  (model digest / ollama version / VRAM / uv.lock sha256) / sealed bundle 上書き拒否 /
  request conformance の**設計をそのままこの N-agent 版に踏襲**（import ではなく
  design-copy — `scripts/m13_live_loop_capture.py` と `scripts/m4_society_live_capture.py` は
  両方とも無改変のまま）。
- traversal I4 (`src/erre_sandbox/integration/embodied/traversal_live.py`) —
  `EmbeddingRecordReplayClient` / `RecordedEmbeddingCall` による embedding チャネルの
  record/replay（record 時 6 桁量子化）。**無改変で import**。
- society live-closure root（Issues 002-006、`society_live_loop.py` / `society_live.py`）—
  `build_society_live_world` / `run_society_live_loop` / `replay_society_plane_g` /
  `society_plane_g_bundle` / `society_request_conformance` / `society_firing_annotation`。
  **無改変で import**。
- 凍結 apparatus `src/erre_sandbox/evidence/**` は **touch しない**（import もしない）。

## 摂動列（事前登録、frozen）

`scripts/m13_society_live_capture.py::SOCIETY_LIVE_PERTURBATION_COUNT` (=36) が SSOT の値、
`society_live_loop.py::society_live_loop_perturbation_plan` が生成関数（無改変で import）。

- N=3 agents（`a_kant` / `a_nietzsche` / `a_rikyu`）× 12 cognition ticks = 36 通、
  1 (agent, window) ペアあたり 1 摂動。
- 摂動は scripted・in-process 合成であって wire 受信ではない。`sent_at` は record-mode clock
  (`SEALED_TS` = 2026-01-01T00:00:00+00:00) に pin。
- **stimulus は scripted、LLM の response（real 実走時）は unscripted**。したがって将来
  観測される経路も「創発的」でも「自己選択」でもない（traversal I4 / I7 と同じ honest label）。

## 実行手順

```powershell
# 1) Ollama-free リハーサル（spend ゼロ、いつでも可、1 コマンドで再現）
python scripts/m13_society_live_capture.py --capture   # rehearsal/ を bake（既存 rehearsal/ は再bake可）
.\experiments\20260907-m13-society-live\repro.ps1       # committed bytes を verify

# 2) sealed real run（user の spend ratify 後にのみ、別セッション）
# ollama 0.32.12 には `show --json` が無い (実測: Error: unknown flag: --json)。
# /api/tags の digest を使う (ollama list の ID の 64 hex 全長):
$env:QWEN3_DIGEST = ((Invoke-RestMethod http://localhost:11434/api/tags).models `
  | Where-Object { $_.name -eq "qwen3:8b" }).digest
$env:OLLAMA_VERSION = (ollama --version)
$env:VRAM_GB = "16"
.\experiments\20260907-m13-society-live\run.ps1
.\experiments\20260907-m13-society-live\repro.ps1 -Real

# 3) L3 cross-platform（WSL 側、または Linux CI が代替）
bash experiments/20260907-m13-society-live/repro.sh
```

> **Issue 007 では 1) のみを実行。2) は 2026-09-07 の別セッション
> (`.steering/20260907-m13-society-live-real-run/`) で user の明示 spend ratify 後に 1 回だけ実行済み。**
> 以下は Issue 007 時点の記述:
> (`run.ps1` / `run.sh` は将来の ratified session のために用意した、ドキュメント化された
> 起動スクリプト — 実行には `--confirm-spend` に加えて `QWEN3_DIGEST` /
> `OLLAMA_VERSION` / `VRAM_GB` の明示設定が要る。このセッションはいずれも設定していない)。
> 3) の Linux 実測は本機に WSL project venv が無いため直接は不可
> (`reference_wsl2_ollama_unreachable` / 過去 I7 セッションでも同一制約を確認済) —
> **Linux CI (この PR の CI run) が L3 の実測を兼ねる**。この test
> (`test_committed_rehearsal_bundle_verifies`) は bundle が無い checkout では skip する。

## 結果（2026-09-07、rehearsal のみ・Ollama-free）

| 観測 | 値 |
|---|---|
| replay_checksum | `77a4937d48d19c56cf6e9f93d7b49b092f38b55931b01616609bcff817abbba2` |
| capture_mode / real_backend / think | `scripted-rehearsal` / `False` / `False` |
| Plane G replay | byte 一致 / 両チャネル `inner_invocations=0` |
| request conformance | LLM 36/36 prompt (agent_id, window, system_prompt, user_prompt)・
  embedding 全件が (kind, text) で committed record と一致。`sampling` は比較対象から明示除外 |
| artifact SHA-256 | 6 artifact + 3 side file 全一致、`manifest.json` 再 render byte 一致 |
| firing annotation（非 gate） | `eligible_tick_count=0` / `witness_tick_count=0`
  （settle は正当な結果として正直に記録。firing は detectability ではない） |

**これは配線とリハーサル apparatus の緑であって、real qwen3 の実走結果ではない。**
`real_run_status` は manifest の `annotations` に `"NOT RUN as of Issue 007"` として明示している。

### sealed real run（real qwen3:8b + real nomic-embed-text）— **2026-09-07 実施済**

user の明示 spend ratify 後に `run.ps1` を **1 回だけ**実行。**再走・調整なし**。
provenance pin と全実測値は `env.md`「sealed real run 実測」節が SSOT。

| 観測 | 値 |
|---|---|
| L1 (`run.ps1`) | **exit 0**。`artifacts/` に 6 artifact を bake |
| replay_checksum | `8ee022197ae8959ea5092f027a2c5f2412bd4d669ee4a4f6b944d55876c12dd3` |
| capture_mode / real_backend / think | `real` / `True` / `False` |
| L2 (`repro.ps1 -Real`) | **exit 0**。Plane G byte 一致 / 両チャネル `inner_invocations=0` |
| request conformance | LLM 36/36・embedding 112/112 が committed record と一致（`sampling` 除外） |
| LLM call 結果 | `llm_status=ok` 36/36、`llm_fell_back=False` 36/36（fallback ゼロ） |
| firing annotation（非 gate） | `eligible_tick_count=0` / `witness_tick_count=0`（全 agent `no_eligible_tick`） |
| dialog envelope count | `0` |
| distinct zone | 3（`study` 1 / `peripatos` 34 / `chashitsu` 1、speech envelope 36 件中） |
| L3 (cross-platform) | **達成**。Linux CI run 34080293087 で `test_m13_society_live_capture.py` 22 passed / 0 skipped (`test_committed_sealed_real_bundle_verifies` が skip されず pass)。CI 全 5 job 緑 |

**settle は事前登録上の正当な結果**として封印した（firing するまで再走しない、が事前登録）。
上記 annotation は **plain count のまま**であり、解釈は足していない。

> **erratum**: この real bundle の `manifest.json` の `annotations.real_run_status` は
> `"NOT RUN as of Issue 007..."` のまま（凍結定数を real / rehearsal で共有する設計）。
> real 判別の正しい根拠は `env_pins.capture_mode == "real"` / `real_backend == true`。
> 詳細と非修正の理由は `env.md`「erratum」節 / `blockers.md`。

## 結果が主張できること / できないこと（不可侵）

- **言える**: 「Ollama-free rehearsal が configured shape (N=3×12×20、36 perturbations) で
  完走し、決定論的に committed bytes から再構成できた」「real 実走の spend gate / provenance
  gate / overwrite gate は、いずれも実際に発火する負例で検証済み」。
- **2026-09-07 の sealed real run 後に追加で言えるようになったこと**:
  「**real qwen3:8b + real nomic-embed-text を挿した状態で、事前登録した形状
  (N=3 × 12 cognition window × 20 physics tick、36 摂動、knob=on、self_other=True) が
  例外なく完走し (exit 0)、その bundle が Ollama-free replay で byte 一致で再構成できた**」
  = **配線が各 seam に届いたことの boolean**。
- **それでも言えない**: aha / emergence / effect / caused / divergence / detectability。
  **firing は settle した** (`eligible_tick_count=0`) ので、二相 knob が実 sampling を
  変えたことすら本走では観測していない（firing は非 gate であり、これは失敗ではなく
  事前登録上の正当な結果）。**wall-clock real-time session でもない**（`ManualClock`、
  摂動は scripted in-process 列、live Godot client なし）。ミラーは **prompt-level
  self-other context** であって心の理論ではない。**M4 の `memory_centroid` collapse は
  解決していない**。door② UNMET・計測ライン CLOSE・R-budget=0・holding は**すべて不変**。

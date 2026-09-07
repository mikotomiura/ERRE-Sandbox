# M13 society live-closure Issue 007 — notes

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
$env:QWEN3_DIGEST = (ollama show qwen3:8b --json | ConvertFrom-Json).digest  # 例
$env:OLLAMA_VERSION = (ollama --version)
$env:VRAM_GB = "16"
.\experiments\20260907-m13-society-live\run.ps1
.\experiments\20260907-m13-society-live\repro.ps1 -Real

# 3) L3 cross-platform（WSL 側、または Linux CI が代替）
bash experiments/20260907-m13-society-live/repro.sh
```

> **Issue 007 では 1) のみを実行済み。2) は一度も実行していない**
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

### sealed real run（real qwen3:8b + real nomic-embed-text）

**未実行。** 本 issue のスコープは `--capture --real --confirm-spend` の**コードパスを実装し
テストで防御すること**であって、実行することではない
(`assert_sealed_real_run` が `confirm_spend` 無しの直呼びも CLI 経由も同様に拒否することを
`tests/test_integration/test_m13_society_live_capture.py::test_spend_gate_rejects_direct_call_without_ratify`
で確認済み)。real 実走が起きたら、この節と `env.md` の「sealed real run」節を実測値で
更新する。

## 結果が主張できること / できないこと（不可侵）

- **言える**: 「Ollama-free rehearsal が configured shape (N=3×12×20、36 perturbations) で
  完走し、決定論的に committed bytes から再構成できた」「real 実走の spend gate / provenance
  gate / overwrite gate は、いずれも実際に発火する負例で検証済み」。
- **言えない**: 「real qwen3 で wiring が各 seam に届いた」（real 実走が起きていないため、
  I7 の "wiring reached each seam (live, real qwen3)" に相当する主張はまだできない）。
  aha / emergence / effect / caused / divergence / detectability は当然言えない。
  door② UNMET・計測ライン CLOSE・R-budget=0・holding は**すべて不変**。

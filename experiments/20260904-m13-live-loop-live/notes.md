# M13 live-loop I7 — notes

## 検証する仮説 / 位置づけ

これは **仮説検証 (measurement) ではない**。`docs/research-positioning.md` §5 の H に対する
verdict を出す実験ではなく、**construction validation** = 「PR #89 で land した live-loop 配線が、
real backend (qwen3:8b + nomic-embed-text) を挿しても各 seam に届き、決定論的に再構成できる」
ことの boolean 観察である。

- 計測ライン (effect / detectability / divergence) は **C-proper で CLOSE 済**
  (`project_m13_c_proper` / `project_m13_post_cproper_disposition`) であり、本実験は再入しない。
- aha は `project_aha_jlens_metric_wellposedness` で close 済。本実験は aha を主張しない。
- door② UNMET・R-budget=0・holding は不変。

## 借用 apparatus / 出典

- Phase 4b (`src/erre_sandbox/integration/embodied/two_phase_live.py`) —
  `SamplingSpyChatClient` による knob-on/off spied replay、`two_phase_firing_summary`、
  `build_two_phase_env_pins`、`evaluation_seeded_agent_state`。**無改変で import**。
- traversal I4 (`src/erre_sandbox/integration/embodied/traversal_live.py`) —
  `EmbeddingRecordReplayClient` / `RecordedEmbeddingCall` による embedding チャネルの
  record/replay (record 時 6 桁量子化)。**無改変で import**。
- 閉包 root (`src/erre_sandbox/integration/embodied/live_loop.py`、PR #89) —
  `build_live_loop_world` / `run_live_loop_capture` / `wiring_reachability_summary`。
  **無改変で import**。
- 凍結 apparatus `src/erre_sandbox/evidence/**` は **touch しない** (import もしない)。

## 摂動列 (事前登録、frozen)

`scripts/m13_live_loop_capture.py::live_loop_perturbation_plan` が SSOT。

- 1 cognition tick あたり 1 摂動 (`max_drain_per_tick=1`、sink は run 前に全件 push
  ゆえ push 順 == tick 順)。
- `source_zone` は 5 zone を決定論的に巡回、`modality="sight"` / `intensity=0.4` は固定、
  `content` = `"live-loop stimulus {tick}: movement and light from the {zone}"`。
- `sent_at` は record-mode clock (`handoff.GOLDEN_TS`) に pin。in-process 合成であって
  wire 受信ではないので、実 send 時刻は committed artifact 中の非決定ノイズにしかならない。
  `world_perturbation_to_perception` は `sent_at` を写さないので cognition / 幾何 / checksum
  には一切届かない (ledger の bytes のみに効く)。
- **stimulus は scripted、LLM の response は unscripted**。したがって観測される経路は
  「創発的」でも「自己選択」でもない (traversal I4 の LOW-2 と同じ honest label)。

## 実行手順

```powershell
# 1) Ollama-free リハーサル (spend ゼロ、いつでも可)
python scripts/m13_live_loop_capture.py --capture     # rehearsal/ を bake
.\experiments\20260904-m13-live-loop-live\repro.ps1   # committed bytes を verify

# 2) sealed real run (user の spend ratify 後にのみ)
$env:QWEN3_DIGEST = (ollama show qwen3:8b --json | ConvertFrom-Json).digest  # 例
.\experiments\20260904-m13-live-loop-live\run.ps1
.\experiments\20260904-m13-live-loop-live\repro.ps1 -Real

# 3) L3 cross-platform (WSL 側)
bash experiments/20260904-m13-live-loop-live/repro.sh --real
```

> **G-GEAR では 3) が動かない**: WSL 側に project venv が無い (`/root/erre-sandbox/.venv` 不在、
> system python3 に pydantic 無し、2026-09-06 再確認)。本機では代わりに
> `tests/test_integration/test_m13_live_loop_capture.py::test_committed_sealed_real_bundle_verifies`
> が committed real bundle を verify するので、**Linux CI が L3 の実測を兼ねる**。
> この test は bundle が無い checkout では skip する。

## 結果 (実走後に追記)

### rehearsal (Ollama-free、2026-09-04)

| 観測 | 値 |
|---|---|
| replay_checksum | `2ad3a39db14262a5c206f3d7930bd1f48bff59deb17f56d898c72d440aa48ecb` |
| Plane G replay | byte 一致 / 両チャネル `inner_invocations=0` / embedding 97/97 消費 |
| Plane L 再駆動 | Plane G と同一 checksum |
| artifact SHA-256 | 4 artifact + 2 side file 全一致、manifest 再 render byte 一致 |
| envelope | 96 通 schema 準拠 |
| request conformance | LLM 32/32 prompt・embedding 97/97 (kind, text) が committed record と一致 |
| reachability (非 gate) | 全 32 corr-id が全 seam 到達 / `no_double_send=True` / mismatch 0 |
| firing (非 gate) | `fired=True` / witness 31 / eligible 31 / `record_knob_on_pinned=True` |

**これは配線とリハーサル apparatus の緑であって、real qwen3 の実走結果ではない。**

### sealed real run (real qwen3:8b + real nomic-embed-text、2026-09-06)

`run.ps1` を **1 回のみ** 実行 (09:29:11〜09:30:40 JST、89 秒)。再走・パラメータ変更・
`--force` なし。verify は `repro.ps1 -Real` (Ollama-free)。

| 観測 | 値 |
|---|---|
| capture_mode | `real` (qwen3:8b think=False / nomic-embed-text、digest は `env.md` に pin) |
| L1 完走 | exit 0 / 32 cognition × 20 physics tick / 6 artifact / injected perturbations 32 |
| replay_checksum | `43eb904d11046b940ff03558cb60b12764b2c49c43e2f06b03b66d35762888eb` |
| Plane G replay | byte 一致 / 両チャネル `inner_invocations=0` / embedding 97/97 消費 |
| Plane L 再駆動 | Plane G と同一 checksum |
| artifact SHA-256 | 5 artifact 全一致、`manifest.json` 再 render byte 一致 |
| envelope | 96 通 schema 準拠 |
| request conformance | LLM 32/32 prompt・embedding 97/97 (kind, text) が committed record と一致 |
| reachability (非 gate) | 全 32 corr-id が全 seam 到達 / `no_double_send=True` / mismatch 0 / kind 各 32 |
| firing (非 gate) | `fired=True` / witness 29 / eligible 29 / `record_knob_on_pinned=True` / `fail_mode=None` |
| L3 cross-platform | 本機 WSL は project venv 不在ゆえ直接実測不可 → Linux CI で committed real bundle を verify (`test_committed_sealed_real_bundle_verifies`) |

**settle しなかった (firing した)**。ただし tick 0-2 の 3 tick は λ=0 で非 eligible
(λ を earn するまでの settle 区間)、tick 3 以降 29 tick が eligible。rehearsal は非 eligible が
tick 0 のみだったので **real の方が settle が 2 tick 長い** — 配線の失敗ではなく、real LLM の
行動列が scripted rehearsal と異なるという当然の帰結。

**これは配線が real backend 越しに各 seam へ届いたという boolean 観察であって、
aha / emergence / effect ではない。** firing ≠ detectability (bias が zone / 行動 / aha を
変えるかは凍結第2リンク、本 run は非測定)。real なのは cognition 面のみ (摂動は scripted 列を
`InboundSink` 直投入、live Godot 不使用) で、`ManualClock(start=0.0)` ゆえ real-time でもない。

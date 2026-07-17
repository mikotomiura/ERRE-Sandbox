# observation-memo — aha Phase 4b construction validation live (非 verdict human memo)

> **construction observation only。verdict/scorer/floor/aha proxy でない。effect の検出可能性は測っていない**
> (= C-proper 第2リンク = 凍結 measurement line、door② UNMET・door CLOSED)。firing⇔detectability 分離。

## 実走メタ (共通、run 1/2)
- platform: G-GEAR Windows 11 native / **qwen3:8b** digest `500a1f067a9f7826…` / **ollama 0.32.0** /
  **think=False** (`ThinkOffChatClient`) / VRAM 16GB / **uv.lock sha256** `9cc70f9dc5d61f6c…` / N=32 cognition tick /
  knob=on (`TwoPhaseKnob()`) / deep_work(=EVALUATION) seed + locomotion 装填 (λ0=0.0)。
- embedding = mock (constant vector)。live なのは action-LLM chat のみ。

## 再走 pre-registration (2026-07-17、run 2 実行前に記録、user 裁定「honest 再走 1 回」)
- **再走は 1 回のみ**。run 2 の結果に関わらず **run 1 (no_eligible_tick) と run 2 を両方 honest 報告**、結果選別しない。
- firing-given-λ>0 は決定的 (数式: evaluation σ=(−1,−1,+1) → temp/top_p↓・rp↑ ; mock-movement test
  `test_firing_evaluation_sign_inversion` green)。再走は「live agent に channel を exercise させる」行為であって
  結果 hunting でない。
- run 2 も settle (no_eligible_tick) なら「この golden 構成は reliably settle する」を honest 記録し、firing は
  apparatus/mock 水準の実証に留める (live firing 未観察)。**追加の再走はしない**。

## Run 1 (2026-07-17、no_eligible_tick、`run1-no-eligible/` に manifest+annotation 保全)
- **replay_checksum** = `ef6161b3e74a962757030569b89c48d7e19328ccc2bcf798f72f861a67876c53`。
- **replay-verify OK**: checksum byte 一致 + `inner_invocations==0` + manifest byte-identical re-render +
  96 envelopes schema 適合 (V2/V3b Windows leg PASS)。
- **firing annotation**: `fired=False` / `witness_tick_count=0` / `eligible_tick_count=0` / `checksums_match=True` /
  **`record_knob_on_pinned=True`** / **`fail_mode=no_eligible_tick`**。
- **診断 (honest)**: agent は peripatos へ歩いて settle。destination_zone = **peripatos 31 / study 1** (32/32 ok)、
  resolved_from = memory_centroid 32/32。agent が peripatos 到達後 dest==current_zone → **move_t=0 → λ が全 tick 0**
  → recorded call.sampling が 32 tick 全て一定 (0.7, 0.9, 1.0) → 符号反転の土台 (λ>0 tick) 不在。
- **解釈**: apparatus のバグでない (`record_knob_on_pinned=True` = record は真に knob=on、fidelity/spy/guard/mock-firing
  全 green)。「firing が起きて失敗」でもない (`eligible_no_inversion` でなく `no_eligible_tick`)。一因は既知の
  **memory_centroid collapse** (M4/Layer2、agent が peripatos 単一 collapse) + この run の LLM が peripatos 選択継続。
  = **channel 未 exercise の "no-data" 的結果**。

## Run 2 (2026-07-17、**firing GO**、主 artifacts = `artifacts/`)
- **replay_checksum** = `e087c406dbfb4f1976fd25aecd9130081efd68d103f044f397755f8f6cb1449c`。
- **replay-verify OK**: checksum byte 一致 + `inner_invocations==0` + manifest byte-identical re-render +
  96 envelopes schema 適合 (V2/V3b Windows leg PASS)。
- **firing annotation**: **`fired=True`** / **`witness_tick_count=25`** / **`eligible_tick_count=25`** /
  `checksums_match=True` / **`record_knob_on_pinned=True`** / **`fail_mode=None`**。
  → **eligible な λ>0 tick 25 本すべてで符号反転** (`eligible_no_inversion` ゼロ = 発火が漏れなく起きた)。
- **診断**: agent が移動。destination_zone = **peripatos 26 / study 5 / chashitsu 1** (32/32 ok)、
  distinct recorded call.sampling = **26** (λ が climb して per-tick sampling が変調)。LLM が多様な destination を
  選び agent が zone 間を移動 → dest != current_zone の tick で move_t=1 → λ>0 → knob-on の evaluation 符号反転が
  knob-off に対し live に発火。
- **解釈 (construction GO)**: **real qwen3:8b の sealed embodied loop で λ↔二相 knob が live 発火**した
  (evaluation 相で generation baseline から temp/top_p↓・rp↑ に符号反転、SamplingSpy で観察、幾何 checksum 不変)。
  measurement でない (effect detectability 非測定、magnitude/divergence 非出力)。

## 両 run の対比 (honest、pre-registration 通り両報告)
- run 1 = agent settle (peripatos 31/32) → λ=0 → no_eligible_tick (channel 未 exercise)。
- run 2 = agent 移動 (peripatos 26/study 5/chashitsu 1) → λ>0 25 tick → **firing fired (25/25 反転)**。
- 差 = LLM の destination 多様性 (非決定)。**apparatus は両 run で record_knob_on_pinned=True・replay byte-parity OK。**
  → firing witness は「agent が移動する live loop」で決定的に発火する (firing-given-λ>0 の live 実証)。
  再走は pre-register 通り 1 回のみ、結果選別なし。

## Done (reproducibility、V1∧V2∧V3a∧V3b) — 主 artifacts = run 2 → **HOLDS**
- [x] **V1** 完走 (run 2: exit 0 で 4 artifact = decisions 32 / ecl_trace / envelope 96 / manifest)。
- [x] **V2** replay 再現 (run 2: checksum `e087c406…` byte 一致 + inner_invocations==0)。
- [x] **V3a/V3b cross-platform 実測 HOLDS** = WSL2 Ubuntu 22.04 (glibc、`PYTHONPATH=/mnt/c/…/src` + WSL venv) と
  Windows (UCRT) で `--verify` → replay_checksum `e087c406…` byte 一致 + manifest byte-identical re-render + 全 artifact
  SHA 一致 (LIVE ARTIFACT OK 両 platform)。firing annotation も Win==WSL byte-identical (LF、6桁量子化が libm drift 吸収)。
- **CI leg**: `tests/test_integration/test_two_phase_live_golden.py` が committed bundle を Linux CI で replay-verify
  (checksum 再現 + firing witness fired=True + record_knob_on_pinned=True)。

## generation 対照 (phase 条件性、run 非依存)
- `two_phase_delta(GENERATION) ≡ locomotion_delta` の恒等は unit test (`test_generation_delta_equals_locomotion_delta`)
  で pin 済。offline generation spy-replay も knob on≡off (`test_generation_seed_no_inversion`)。→ 発火は evaluation 相のみ。

## 判定 (construction、非 verdict、2026-07-17)
- **construction validate GO**: real qwen3:8b の sealed embodied loop で **λ↔二相 knob が live 発火**した
  (run 2: evaluation 相の λ>0 tick 25 本すべてで knob-on の temp/top_p↓・rp↑ 符号反転を SamplingSpy で観察、幾何
  checksum 不変、record は真に knob=on、Win/WSL byte-parity)。run 1 の no_eligible_tick (agent settle) と併記 = firing は
  「agent が移動する live loop」で決定的に発火 (firing-given-λ>0 の live 実証)。
- **guard 厳守**: measurement でない。effect の検出可能性/大きさ/divergence/floor/aha proxy は **一切測っていない**
  (= C-proper 第2リンク = 凍結 measurement line)。door② UNMET・door CLOSED・R-budget=0・holding 不変。firing⇔detectability 分離。
- **非 gating memo**: rendering collapse (peripatos 単一 collapse、M4/Layer2 既知) は run 1 の settle の一因だが
  pass/fail・forward 選択の gating に使わない (「semantic uptake not assessed」)。
- 次工程は結果を承け別 ADR で再 fork ((a) aha 建設継続 / (b) door-open=②壁2 解決+user 裁定で measurement / (c) bounded-close)。
  **merge・door を開ける判断は user 裁定**。

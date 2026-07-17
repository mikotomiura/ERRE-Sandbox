# aha Phase 4b — λ↔二相 knob construction validation live — environment / status

- **実験**: aha!/DMN-ECN Phase 4b = λ↔二相 knob の real qwen3 sealed embodied loop での活性化 (construction)
- **apparatus**: `scripts/aha_phase4b_two_phase_live_capture.py` (`--capture` / `--verify`) +
  `src/erre_sandbox/integration/embodied/two_phase_live.py`
- **ADR**: `.steering/20260717-aha-phase4b-construction-validation-live/design-final.md` (FROZEN、binding)
- **仮説接続**: これは construction validation (knob が live embodied loop で発火する boolean 観察) であって
  measurement ではない (effect detectability = C-proper 第2リンク = 凍結 measurement line、非測定)。
  借用 apparatus = ecl_v1 (`live_v1.py` の SamplingSpy / seeded factory / env_pins overlay)。凍結 evidence 非 touch。

## status (2026-07-17、実装完了・sealed run 待ち)
- Ollama-free apparatus + test は landed。**sealed live run (real qwen3:8b、knob=on 1 run) は human-gated、未実走。**
- `run.ps1` = live capture (要 live Ollama + qwen3:8b pull、real spend)。
- `repro.ps1` = Ollama-free replay-verify (V2/V3a) + re-render (V3b) + firing annotation side file
  (`two_phase_firing_annotation.json`、manifest SHA 集合外)。

## 実走環境 (封印前 pre-register 固定・実走後 tuning ゼロ、実走後に追記)
- **日時 / platform**: TBD、capture = Windows 11 native (PYTHONUTF8=1)、
  cross-platform verify = WSL2 Ubuntu 22.04 (glibc) + Windows (UCRT)。
- **qwen3:8b digest**: TBD (manifest pin = 16 文字 prefix、v0/v1 踏襲)。
- **ollama**: TBD / **think**: False (`ThinkOffChatClient` 経由、cycle 無改変)。
- **VRAM**: RTX 5060 Ti 16GB。
- **uv.lock sha256**: TBD。
- **replay_checksum**: TBD (実走後追記)。

## 事前登録 (design-final §5)
- **Done = V1∧V2∧V3a∧V3b** (reproducibility)。
- **firing annotation = 非 gate** (side file、boolean/count のみ、tune-to-pass 禁止)。**verdict なし**。
- **firing witness** (Codex HIGH-1): evaluation-phase の ≥1 λ>0 tick で knob=on の per-tick sampling が knob=off に対し
  `on.temperature < off.temperature ∧ on.top_p < off.top_p ∧ on.repeat_penalty > off.repeat_penalty` (SamplingSpy 判定)。
- **record-knob-on pin** (Codex HIGH-2): committed call.sampling == knob=on replay spy sampling (record が真に knob=on)。
- **generation 対照**: `two_phase_delta(GEN) ≡ locomotion_delta` の恒等 (unit test) → 発火は phase 条件付き。
- V3b cross-platform byte 一致 (WSL Linux glibc / Windows UCRT) は 6桁量子化が libm drift を吸収
  (`feedback_golden_crossplatform_float_drift`)。

## 決定論 (Codex MED-5)
- 強く主張できるのは **committed decisions replay の determinism + byte parity**。real qwen3 record の環境差完全再現は
  過剰主張しない。
- replay は committed 応答を再 serve・checksum は幾何のみ → knob 活性化は新非決定源ゼロ。
- verify は knob-on **seeded state** で replay。firing annotation は SamplingSpy が recomposed per-tick sampling を捕捉。

## guard (不可侵)
- construction-only、measurement 非 authorize、effect detectability 非測定、aha scorer 化しない、firing⇔detectability 分離。
- R-budget=0 / holding / measurement-line CLOSE / door② UNMET・door CLOSED 不変。floor/landscape/verdict/divergence/
  magnitude/detectability/aha proxy 非出力、evidence 非 import (guard test で AST pin)。

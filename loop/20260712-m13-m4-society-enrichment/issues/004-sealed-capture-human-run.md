# Issue 004 (I4): SEALED G-GEAR capture（非 Loop, human-run、real qwen3:8b、一発）
verify_level: n/a   # 非 Loop（VRAM 依存・非再現・一発、ECL v0 Issue 003 posture）。Loop watchdog 対象外。

## Goal
G-GEAR Windows-native Ollama で real qwen3:8b（think=False）を封印実走し、N=3 agent society の
新 golden `tests/fixtures/m4_society_live_golden/` を landed する。4 成果物 + `expected_placement.jsonl` を
commit → `--verify` + parametrized godot test local 緑 → **multi-zone-or-honest-single-zone を honest 報告**
（動きを捏造しない、over-read 禁止）。

## Background
FROZEN design-final §I4 / §C。real `--capture` のみ VRAM 依存・非再現・一発ゆえ Loop 外（ECL v0 Issue 003 posture）。
凍結定数（sealed run 前固定、run 後変更は Stop）: `SOCIETY_LIVE_N_COGNITION_TICKS=12` / seed=0 / 3 agent
(kant/nietzsche/rikyu) / 初期 zone=study/peripatos/chashitsu / run_id="m4-society-live-golden" / think=False / model=qwen3:8b。
R1: think=False で zone 移動が起きない可能性（single-agent 知見「think=False が load-bearing」）→ honest single-zone
= first-class pass（decisions.md 判断1）。WSL2 → Windows-native Ollama 不通（reference_wsl2_ollama_unreachable）ゆえ
capture は Windows-native、`--verify` は Ollama-free で WSL 可。

## Scope
### In（human-run 手順）
1. **Gate 0**: qwen3:8b が Windows-native Ollama で think=False 起動するか smoke
   （reference_g_gear_host / reference_qwen3_ollama_gotchas）。`ollama list` で qwen3:8b 在庫確認。
2. `python scripts/m4_society_live_capture.py --capture --n-cognition-ticks 12 --run-id m4-society-live-golden
   --seed 0 --out-dir tests/fixtures/m4_society_live_golden --qwen3-model-digest <digest> --ollama-version <v>
   --vram-gb <v> --uv-lock-sha256 <hash>` を `& disown` + log tail completion marker で監視
   （feedback_wsl_bg_launch_needs_disown / feedback_log_tail_completion_marker）。
3. 4 成果物（manifest.json / ecl_trace.jsonl / decisions.jsonl / envelope_stream.jsonl）+ expected_placement.jsonl を commit。
4. `python scripts/m4_society_live_capture.py --verify --artifact-dir tests/fixtures/m4_society_live_golden` local exit 0。
5. `pytest tests/test_integration/test_m4_society_replay.py -q -k m4`（GODOT_BIN 有り）で m4 パラメータ緑（byte 一致）。
6. **honest 報告**: ecl_trace の distinct zone 数 + per-tick `plan.destination_zone` / resolver `resolved_from` の
   診断 dump（L1: authored destination / current zone / resolved zone / invalid-zone flag）。multi-zone なら
   その旨、single-zone なら「LLM が別 zone を選ばなかった／選んだが resolver 到達不能」を機序診断。**pass/fail に使わない**。
### Out
- capture harness/CLI の実装（I1/I2 で確定）。定数の変更（sealed run 後は Stop）。scripted zone 移動の捏造。

## Allowed Files
- `tests/fixtures/m4_society_live_golden/*`（新 fixture 生成 = capture 出力 commit）
- （報告のみ）`.steering/20260712-m13-m4-society-enrichment/blockers.md` / retrospective

## Acceptance Criteria（boolean のみ、verdict なし）
- AC4-G1: 4 成果物 + expected_placement.jsonl が commit され `--verify` exit 0（record→replay byte 一致、
  全 client inner_invocations==0、manifest 再 render 一致）。
- AC4-G2: `pytest ... -k m4` = passed（viewer headless dump が N=3 avatar を order_slot 順・trace 通りに解決、byte 一致）。
- AC4-G3: ecl_trace に **複数 distinct zone**（or honest single-zone 報告 + 機序診断）。**どちらも valid landed**。
- AC4-G4: envelope_stream に N=3 agent 分 speech/animation。

## Test Plan
`--verify`（Ollama-free、local + I5 で WSL）+ parametrized godot test（GODOT_BIN 有り）。distinct-zone は
annotation ゆえ Done gate でない（AC4-G3 は multi-or-single どちらも pass）。

## Stop Conditions
- sealed run 後に凍結定数を変更したくなる → **Stop**（tune-to-pass 封鎖、変更は superseding ADR）。
- zone 移動を scripted で捏造したくなる → **Stop**（plan.destination_zone は LLM authored のみ）。
- Gate 0 で qwen3:8b が think=False 起動しない → blockers.md（Ollama topology 診断、reference_wsl2_ollama_unreachable）。
- ChatGPT/Ollama usage/VRAM 制約 → honest 記録 + defer。

## Dependencies
- **I1, I2**（harness + CLI）。**I3**（viewer/test parametrize、m4 パラメータの有効化先）。

## Status
todo（human-run、非 Loop）

## Execution Result
（sealed run 後に記入。multi-zone-or-honest-single-zone 報告 + 診断）

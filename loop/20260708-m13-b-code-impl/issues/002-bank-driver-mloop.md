# Issue 002 (I2): bank driver（bake-out M-loop, zone bias off + pre-bias readout）+ BankLlmCallRecord + record-M
verify_level: recheck   # 公開 driver API + Codex 事実誤認 HIGH-1/HIGH-2 直結 + determinism 契約

## Goal
凍結 context を chat() へ M 回投入する **bake-out M-loop** を実装する。full cycle を通さず凍結
`(prompt, sampling)` を直投入し、**readout = pre-bias parsed `destination_zone`**。emit = bank 専用
`BankLlmCallRecord`（§I5 閉集合、`EclDecisionRecord` 非流用）。record/replay を bank 軸へ拡張し mc-index label で
Plane2 record-M を成す。**construction であって measurement でない**（H/count/divergence 非計算）。

## Background
FROZEN ADR §I1.4（bake-out, retrieve-count=0, pre-bias readout）/§I5（BankLlmCallRecord bank 専用 schema,
mc-index label, 全順序 tie-break）。Codex 事実誤認 HIGH-1（`_bias_target_zone` cycle.py:1643 が post-LLM で
zone を persona preferred へ差替え得る → zone bias off + pre-bias readout で lever の対称 preferred_zones と
交絡を殺す）/ HIGH-2（bake-out 直 chat() record ≠ full-cycle EclDecisionRecord → BankLlmCallRecord 新設）。
grill-goals.md D-4/D-5。**設計 FROZEN**。

## Scope
### In
- 新規 `src/erre_sandbox/integration/embodied/bank.py`:
  - `BankLlmCallRecord` dataclass（frozen）= `{frozen_ctx_id, condition, mc_index, system_prompt, user_prompt,
    sampling, raw_response, pre_bias_destination_zone}`（§I5 閉集合）。
  - `run_bank_mloop(*, llm, frozen_contexts, m_draws, ...)` — 各 `(frozen_ctx, condition∈{"on","off"})` に対し
    `llm.chat([SystemMsg, UserMsg], sampling=frozen)` を `m_draws` 回。**pre_bias_destination_zone =
    `parse_llm_plan(raw_response).destination_zone`**（direct parse、cycle 非経由 = 構造的 pre-bias）。retriever/
    store を M-loop 内で一切触れない。`ERRE_ZONE_BIAS_P=0` を pin。
  - `BankRecordReplayClient`（`RecordReplayChatClient` を bank 軸へ wrapper 拡張、`live_v1.SamplingSpyChatClient`
    の wrapper 先例）: record mode で `BankLlmCallRecord` 列捕捉、replay mode で同順再供給・`inner_invocations==0`。
  - M/K 凍結定数（`BANK_M_GOLDEN`/`BANK_K_GOLDEN` tiny pinned literal、powered 値は C-proper）。全順序 tie-break
    key `(order_slot, frozen_ctx_id, condition, mc_index, seq)`（`handoff.py:576` 超集合）。
  - bank manifest overlay + 独自 `BANK_SCHEMA_VERSION="ecl-bank-1"`（`handoff.MANIFEST_SCHEMA_VERSION` 無改変、
    `live_v1.attach_live_v1_observables` overlay 先例）。annotation raw-row 型 + `BANK_ANNOTATION_SCHEMA_VERSION`
    定義（writer は I5 が使う、ここでは型のみ）。
- 新規 `tests/test_integration/test_ecl_bank_driver.py`。
### Out
- competing cue fixture / provenance pass（I1）。spend ast-guard（I3）。annotation writer / golden bake（I5）。
  continuity gate test 群（I6）。live Ollama（D-10）。measurement 再入。

## Allowed Files
- `src/erre_sandbox/integration/embodied/bank.py`（新規）
- `tests/test_integration/test_ecl_bank_driver.py`（新規）
- **無改変厳守**: `loop.py`/`cycle.py`/`parse.py`/`handoff.py`/`live.py`/`live_v1.py`/committed golden

## Acceptance Criteria（AC↔test）
- I2-G1: `test_bank_mloop_pre_bias_readout` — M-loop の `pre_bias_destination_zone` が
  `parse_llm_plan(raw).destination_zone` に一致（direct pre-bias parse、cycle 非経由で bias 適用なし）
- I2-G2: `test_bank_llm_call_record_schema` — `BankLlmCallRecord` が §I5 の 8 field 閉集合ちょうど、
  M-loop は `EclDecisionRecord` を生成しない（type 非在 assert）
- I2-G3: `test_bank_record_m_mc_index` — 各 `(ctx, condition)` が `m_draws` 個の record を `mc_index` 0..M-1
  label で生成、全順序 `(order_slot, frozen_ctx_id, condition, mc_index, seq)` で sorted
- I2-G4: `test_bank_replay_roundtrip` — record K×M×2 → replay 同順再供給 → `inner_invocations==0` + bank byte 一致
- I2-G5: `test_bank_zone_bias_pinned_off` — driver が `ERRE_ZONE_BIAS_P=0` を pin（provenance/M-loop 双方で
  bias 非発火の前件）
- I2-G6: 既存 `test_ecl_flag_off_byte_invariant` + ECL replay test 群 緑維持（organ 無改変、N=1 byte 不変）
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`

## Test Plan
`pytest -q tests/test_integration/test_ecl_bank_driver.py` + 既存 ECL/flag-off 回帰 + pre-push 4 段。M-loop は
mock chat client（決定的 raw response）で live 非依存。record→replay 等価を mock で実証。

## Stop Conditions
- 全 AC 緑（Done）。
- driver が organ（loop.py/cycle.py/parse.py/handoff.py）の改変を要する → Stop（binding「organ 無改変」逸脱→
  superseding ADR）。
- M-loop が readout に post-bias zone を使わないと通らない → Stop（Codex HIGH-1 違反）。
- budget 到達 → Stop。

## Dependencies
- I1（`FrozenContext` / provenance pass の出力を消費）。

## Status
TODO

## Execution Result
（完了時に記入。PR 本文になる）

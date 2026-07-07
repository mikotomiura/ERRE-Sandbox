# Issue 001 (I1): competing-destination cue fixture + 凍結 context schema + substrate provenance pass
verify_level: recheck   # 公開 fixture API + T3 materiality (canonical-inputs-only) + forking-paths seal 直結

## Goal
反復 bank の **凍結 context 生成側**を構築する。enriched substrate（Z_comp に構造同型な affordance/memory-content
+ 中立 persona/AgentState、canonical inputs のみ `model_validate` 経由で編集）から、live 器官が canonical
builder（`build_system_prompt`/`build_user_prompt`）で 1 pass render した実 prompt を凍結する **provenance pass**
を実装する。凍結 context = `(frozen_ctx_id, system_prompt, user_prompt, sampling_on, sampling_off)`。
**construction であって measurement でない**（H/divergence 非計算）。

## Background
FROZEN ADR `.steering/20260707-m13-b-impl-design/design-final.md` §I1（lever = zone-pick-visible cue、
memory-geometry 破棄）/§I3（凍結 schema）/§I7（T3 materiality criterion 1-3）。grill-goals.md D-2/D-3/D-9(a)。
zone-pick を選ぶのは LLM 本体（`parse.py:63` `LLMPlan.destination_zone`）。memory location/zone は LLM 不可視
（`format_memories` は content のみ描画）ゆえ lever は prompt cue の対称構築に narrow。**設計 FROZEN、再オープン
しない**（fork なら Stop→superseding ADR）。

## Scope
### In
- 新規 `src/erre_sandbox/integration/embodied/bank_fixtures.py`:
  - cue 定数（result-independent、forking-paths seal）: `BANK_Z_COMP=(Zone.STUDY, Zone.GARDEN)` /
    `BANK_NEUTRAL_ZONE=Zone.AGORA` / per-context `BANK_LAMBDA_CTX`（λ_ctx literal tuple）。**literal pin**
    （`evidence.*` 非 import）。
  - `build_competing_cue_substrate(...)` — 中立 persona（`preferred_zones` 空）+ 凍結 AgentState snapshot
    （position zone=`BANK_NEUTRAL_ZONE`、中立 erre mode/physical/cognitive、`model_validate` 固定 dict）+
    各 z∈Z_comp に構造同型 affordance/zone_transition observation（同一 salience・同一個数・zone 名のみ差替え）+
    content 鏡映 memory（`RankedMemory` 静的手構築、kind/strength/content 直接付与、retriever 非呼出）。
  - `run_provenance_pass(...)` — enriched substrate を `run_ecl_loop`（無改変）で 1 full-cycle pass 走らせ、
    canonical builder が render した `(system_prompt, user_prompt)` + resolved sampling を捕捉。T_on
    （`LocomotionState(lam=λ_ctx)`）と T_off（`locomotion=None`）で `sampling_on`/`sampling_off` を得る
    （prompt は λ 非関与ゆえ byte 同一）。`ERRE_ZONE_BIAS_P=0` を pin、EclDecisionRecord で `bias_fired is None`。
  - `FrozenContext` dataclass（`frozen_ctx_id, system_prompt, user_prompt, sampling_on, sampling_off`、frozen）。
- 新規 `tests/test_integration/test_ecl_bank_fixtures.py`。
### Out
- bake-out M-loop / BankLlmCallRecord（I2）。spend guard（I3）。annotation side-file / golden（I5）。continuity
  gate test 群（I6）。live Ollama（mock-only 裁定 D-10）。measurement 再入。

## Allowed Files
- `src/erre_sandbox/integration/embodied/bank_fixtures.py`（新規）
- `tests/test_integration/test_ecl_bank_fixtures.py`（新規）
- **無改変厳守**: `loop.py`/`cycle.py`/`prompting.py`/`embodiment.py`/`parse.py`/`handoff.py`/`world/tick.py`/
  `live.py`/`live_v1.py`/committed golden

## Acceptance Criteria（AC↔test）
- I1-G1: `test_bank_cue_constants_literal_pin` — `BANK_Z_COMP`/`BANK_NEUTRAL_ZONE`/`BANK_LAMBDA_CTX` が literal +
  `evidence.*` 非 import（`ecl_v1.ECL_V1_LOCO_LAM0` の literal-pin 先例、AST scan）
- I1-G2: `test_bank_cue_canonical_inputs_only` — fixture は observation/persona/AgentState/memory を
  `model_validate` 経由のみ編集、**manual prompt string を手書きしない**（T3 criterion 1、AST で prompt 文字列
  直書き非在を assert）
- I1-G3: `test_bank_cue_symmetric` — Z_comp 各 zone の affordance/zone_transition observation が構造同型
  （同一 salience・同一個数、zone 名のみ差替え）+ content 鏡映 memory
- I1-G4: `test_bank_provenance_pass_uses_canonical_builder` — provenance pass が `build_system_prompt`/
  `build_user_prompt` 由来の prompt を render（canonical builder 経由、EclDecisionRecord 生成）
- I1-G5: `test_bank_provenance_bias_off` — provenance pass は `ERRE_ZONE_BIAS_P=0` 下で走り EclDecisionRecord の
  `bias_fired is None`
- I1-G6: `test_bank_frozen_context_prompt_identity` — 同一 context の `system_prompt`/`user_prompt` が T_on/T_off
  で byte 同一（sampling のみ 2 値、§I3.3）
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`

## Test Plan
`pytest -q tests/test_integration/test_ecl_bank_fixtures.py` + 既存 ECL 回帰 + pre-push 4 段。provenance pass は
mock inner chat（think 転送は既存 `live.ThinkOffChatClient` 経由でも可）で live 非依存に test。AST scan で
canonical-inputs-only / literal-pin を機械保証。

## Stop Conditions
- 全 AC 緑（Done）。
- fixture が organ（prompting.py/cycle.py/embodiment.py 等）の改変を要する → Stop（binding「organ 無改変」逸脱→
  superseding ADR）。
- 凍結 context を「対称 cue」でなく手書き prompt stimulus で作らないと通らない → Stop（T3 criterion 1 違反）。
- budget 到達 → Stop。

## Dependencies
- なし（起点）。I2/I5/I6 の前提。

## Status
TODO

## Execution Result
（完了時に記入。PR 本文になる）

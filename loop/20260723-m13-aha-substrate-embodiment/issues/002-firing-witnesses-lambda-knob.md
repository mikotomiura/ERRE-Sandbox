# Issue 002 (I2): firing witnesses — W2 λ update-path + W3 knob algebra
verify_level: recheck   # AC 直結（二相 knob 発火 = milestone の payload）+ measurement 非再入境界 = 独立再走対象

## Goal
I1 の traversal 上で、二相 knob が **traversal で earn した λ>0** の evaluation tick で発火することを exact/boolean で
緑にする: **W2 λ update-path**（λ>0・move の tick 系列 exact）+ **W3 knob algebra**（`sign_inversion_fired` +
generation-phase control + record-knob-on pin）。「knob が embodied な traversal 舞台で発火する」= 本 milestone の
payload。firing ≈ 恒等式（符号確認のみ・aha/effect 不問）を明記。

## Background
FROZEN ADR + design-final-ref.md。二相 knob = `erre/two_phase.py`（TwoPhaseKnob/two_phase_delta/EVALUATION_MODES/
phase_of_mode）、`cycle.py::_locomotion_delta_for` に landed。既存 firing witness `sign_inversion_fired`（Phase 4b、
λ>0 tick で knob-on vs off の recomposed sampling が `on.temp<off ∧ on.top_p<off ∧ on.rp>off`）+ `SamplingSpy` +
seeded factory（evaluation/generation）を再利用。Phase 4b は λ₀ seed 依存で run1 空振り → 本タスクは I1 の traversal
で λ を earn するので発火が seed 非依存。Codex MEDIUM-2（effect 測定に滑らない、exact tick 系列）/ LOW-3（恒等式性を
前面）反映。

## Scope
### In
- `traversal_live.py` 拡張:
  - **W2 λ update-path** 集計: 記録から `expected_move_ticks`（move_t=1 の tick）+ `expected_positive_lambda_ticks`
    （λ>0 の tick）系列を抽出（or quantized λ sequence checksum）。"sustained" 等効果量語を使わない。
  - **W3 knob algebra**: 既存 `sign_inversion_fired` を traversal 記録に適用。evaluation seeded（deep_work∈
    EVALUATION_MODES）で λ>0 tick 符号反転、generation seeded で knob-on≡off（phase 条件性 control）、record-knob-on
    pin（committed call.sampling==knob-on spy sampling）。
  - `traversal_firing_summary`（boolean/count のみ、verdict=None、side file）。
- `test_traversal_live.py`（W2/W3 部）:
  - `test_traversal_lambda_update_path`: `expected_move_ticks==[...]` ∧ `expected_positive_lambda_ticks==[...]`（byte-pin）。
  - `test_traversal_knob_algebra`: sign_inversion_fired（evaluation λ>0 tick）+ generation control（knob-on≡off）+
    record-knob-on pin。定義 docstring に「符号確認のみ・生成品質/差分/aha 不問」。
### Out
- committed golden / byte-parity / capture script（I3）。
- effect/divergence/floor/aha proxy/verdict の算出・emit（measurement 非再入）。
- organ 6ファイル改変。

## Allowed Files
- `src/erre_sandbox/integration/embodied/traversal_live.py`（I1 から拡張）
- `tests/test_integration/test_traversal_live.py`（I1 から拡張、W2/W3）
- **無改変厳守**: organ 6ファイル + `two_phase_live.py`（`sign_inversion_fired`/`SamplingSpy`/seeded factory を read-only 再利用）

## Acceptance Criteria（AC↔test）
- I2-G1 `test_traversal_lambda_update_path`: expected_move_ticks / expected_positive_lambda_ticks が byte-pin と一致。
- I2-G2 `test_traversal_knob_algebra`: evaluation λ>0 tick で sign_inversion_fired=True、generation control で
  knob-on≡off、record-knob-on pin=True。
- I2-G3: firing summary が boolean/count のみ（effect/divergence/floor/aha/verdict を emit しない、side file）。
- CI parity: `pwsh scripts/dev/pre-push-check.ps1` 4 段全緑（既存 golden 回帰ゼロ）。

## Test Plan
`pytest -q tests/test_integration/test_traversal_live.py -k "lambda_update or knob_algebra"` + pre-push 4 段。in-memory。

## Stop Conditions
- 全 AC 緑（Done）。
- I1 の traversal で λ>0 evaluation tick が生じない（earn 失敗）→ I1 の horizon/leg 凍結 discipline を見直す
  （成績を見て閾値を緩めない）。生じないのが構造要因なら Stop→ADR revise。
- witness が effect を測る方向に滑る（"sustained"/効果量）→ exact tick 系列 / boolean に是正（Codex MEDIUM-2）。
- organ 改変を要する → Stop→superseding ADR。budget 到達 → Stop。

## Dependencies
- I1（traversal driver core + 凍結 route）。

## Status
done

## Execution Result

**Status: DONE**（AC 全緑）。

### 変更ファイル
- `src/erre_sandbox/integration/embodied/traversal_live.py`（I1 の 431 行から拡張、
  W2/W3 追加分 約+260行）: `TRAVERSAL_EXPECTED_MOVE_TICKS` / `TRAVERSAL_EXPECTED_INCOMING_LAMBDA`
  / `TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS`（W2、frozen 定数から純粋導出）+
  `expected_lambda_sequence_checksum` + `traversal_generation_seed_agent_state` +
  `run_traversal_replay_spy` + `traversal_firing_summary`（W3）。
- `tests/test_integration/test_traversal_live.py`（I1 の 8 test から 11 test へ拡張）:
  `test_traversal_lambda_update_path` / `test_traversal_knob_algebra` /
  `test_traversal_firing_summary_is_boolean_count_only` を追加。

### W2 実測系列
`TRAVERSAL_EXPECTED_MOVE_TICKS = (0, 1, 2, 3, 4)`（全 5 leg が move）。
`TRAVERSAL_EXPECTED_INCOMING_LAMBDA = (0.0, 0.3, 0.51, 0.657, 0.7599)`（tick の
**サンプリング呼び出しが読む incoming λ**、`advance_lambda` の純粋fold）。
`TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS = (1, 2, 3, 4)`。
**λ 更新の tick 内前後関係（実測確定）**: `CognitionCycle._locomotion_delta_for` は
`agent_state.locomotion`（tick 開始時点、= 前 tick までの fold 結果）を読み、
`_advance_locomotion` によるλ更新は同 tick の Step 9 で `new_state` に書き込まれ
**次 tick から** 有効になる。ゆえ **tick 0 のサンプリングは seed λ=0（発火せず）、
tick 1 から λ>0**（tick 0 でなく tick 1 発火開始、実装前の desk 予想と一致・run で確認）。
**計算値との一致**: 実 run（`traversal_firing_summary`）の SamplingSpy から
eligible tick（knob-on sampling != knob-off sampling）を再計算すると
`(1, 2, 3, 4)` — `TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS` と完全一致
（`test_traversal_lambda_update_path` で assert）。

### W3 結果
`evaluation_phase_sign_inversion_fired=True`、`witness_tick_count=4`、
`eligible_tick_count=4`（tick 1-4 全て sign_inverted=True、tick 0 は knob-on==knob-off
で非発火＝設計通り）。generation-phase control（`traversal_generation_seed_agent_state`
= peripatetic）で同一 committed decisions を replay → knob-on≡off（quantised sampling
完全一致）確認。`record_knob_on_pinned=True`（committed call.sampling == knob-on
replay spy sampling）。`checksums_match=True`（knob は sampling のみ変調、trajectory 不変）。

### firing summary の非 emit 確認
`traversal_firing_summary` の戻り値は `verdict=None` / `hard_gate=False` / dict key に
banned 語（effect/effect_size/detectability/aha_proxy/aha_score/magnitude/score）なし
（`test_traversal_firing_summary_is_boolean_count_only` で assert）。`witness_tick_count`
/ `eligible_tick_count` は int（plain count、比率/閾値でない）。

### テスト結果
`pytest -v tests/test_integration/test_traversal_live.py`: **11 passed**
（W1 既存 8 + W2/W3 新規 3）。`pytest -q tests/test_integration/test_two_phase_live.py`:
**20 passed**（既存 firing apparatus 回帰ゼロ）。`ruff format --check` / `ruff check` /
`mypy`（対象2ファイル）: 全緑。

### organ 無改変
`git diff --stat` を organ 6ファイル + `two_phase_live.py` + `live_v1.py`
（`SamplingSpyChatClient` 新規 import 元）+ `live.py`（`ThinkOffChatClient`）に対し
実行、出力なし（空）。

### guard 遵守
firing ≈ 恒等式（符号確認のみ・「aha 実在」証明でない）を W3 test docstring に明記。
effect/divergence/floor/aha proxy/verdict は一切 emit せず（M1 の AST guard test が
`traversal_live.py` 全体を再スキャンし継続 PASS）。organ 6ファイル + `two_phase_live.py`
は read-only 再利用のみ（改変なし）。think=false 継続。

### blocker / organ 改変要否
なし。organ 改変は不要だった（`sign_inversion_fired` / `two_phase_firing_summary` /
`SamplingSpyChatClient` / seeded factory idiom を無改変のまま再利用し、traversal 固有の
seed/replay/summary 合成のみ追加）。

### 追記（code-review MEDIUM 2 + LOW 2 反映、witness 妥当性 implicit→explicit 化）
- **M-1 W2 役割明確化**: W2 は「λ→sampling 配線 + tick-timing（tick0 非発火/tick1+ 発火）
  の witness」であり **物理到達は witness しない**（到達 teeth は W1 の
  `test_traversal_undershoot_fails_route` が担う）旨を、実装（W2 セクション見出しコメント）
  + `test_traversal_lambda_update_path` docstring の両方に明記。
- **M-2 generation-control 非空性の直接 assert（vacuous green 封鎖）**: `test_traversal_knob_algebra`
  に `TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS` の各 tick で
  `gen_on_q[tick] != gen_on_q[0]`（λ=0 baseline との差分）を追加 assert。
  「λ>0 の gen tick が実在し（tick0 baseline と sampling が異なる＝λ が実際に動いた）、かつ
  その tick で knob-on≡off（符号反転しない）」を非 vacuous に pin（0==0 の trivial green を排除）。
- **LOW-1 checksum byte-pin**: `expected_lambda_sequence_checksum()` を hardcoded hash
  （`648163682b65adf72666ebb87d8a5f7edc6f26a4dfb520c1e74d109bf29eb2ad`）に対し assert する
  `test_traversal_lambda_sequence_checksum_pinned` を新設（`__all__` 公開のまま維持、
  ADR の「quantized λ sequence checksum」option を executable 化）。
- **LOW-2 golden-path 限定の明示**: `run_traversal_replay_spy` の docstring に
  「persona=golden_persona() / horizon=TRAVERSAL_HORIZON を hardcode、非 golden 経路の
  recorded を渡すと黙って不一致になる」旨を追記。
- スキップ: LOW-3（gen-control 重複 record、決定論ゆえ無害・perf のみ）/ LOW-4（I3 の
  golden 化時の再量子化 memo、I2 対象外）は指示通り未対応。

**再検証**: `pytest -v tests/test_integration/test_traversal_live.py` = **12 passed**
（既存11 + LOW-1 checksum pin test 1件追加）。`pytest -q test_two_phase_live.py` =
20 passed（回帰ゼロ）。`ruff format --check` / `ruff check` / `mypy`（対象2ファイル）= 全緑。
organ 6ファイル + `two_phase_live.py` + `live_v1.py` + `live.py` の `git diff --stat` = 空。

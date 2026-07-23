# design-final-ref — 各 issue subagent 用の自己完結 brief

SSOT = `.steering/20260723-m13-aha-substrate-embodiment/design-final.md`（FROZEN、Codex Adopt-with-changes 反映）。
以下は per-issue subagent が読む load-bearing 抜粋。

## 一次事実（read-only 確認済、実装で前提にしてよい）
1. `contracts/geometry.py::reflect_clamp(dest, zone)` は `locate_zone(result)==zone` を常に保証 → `resolve_destination`（`cognition/embodiment.py`）の `target.zone` は常に LLM の destination_zone（M4 golden 36/36 一致）。
2. `erre/locomotion_sampling.py::advance_lambda(prev, move_t, α=0.3)`、`move_t∈{0,1}`=containing zone 変化。zone 横断で λ>0 を earn、settle で λ→0。
3. 二相 knob = `erre/two_phase.py`（TwoPhaseKnob / two_phase_delta / EVALUATION_MODES / phase_of_mode）、`cognition/cycle.py::_locomotion_delta_for`（L962）に landed。λ>0 の evaluation-phase（deep_work∈EVALUATION_MODES）tick で符号反転発火。
4. 既存 apparatus（**再利用、無改変**）: `integration/embodied/two_phase_live.py` の `run_two_phase_capture`（`run_ecl_loop` drive body 再構成 + `two_phase_knob` 注入、Option A、fidelity test で `knob=None ≡ run_ecl_loop` を pin）+ `sign_inversion_fired` + `SamplingSpy` + seeded factory + build_env_pins。script 骨格 = `scripts/aha_phase4b_two_phase_live_capture.py`。golden fixture 形 = `tests/fixtures/m4_society_live_golden/`・phase4b golden。

## 採用アプローチ（Codex HIGH-2 反映で claim 降格）
**scripted planner が waypoint observations を消費する決定論的 traversal harness**（organ 非改変で world stimulus 経路を通す）。「agent が world に自律応答して巡る emergent traversal」は未検証・別 ADR/別 spend に defer。firing ≈ 恒等式で「aha 実在」証明でない（over-read 禁止）。

- 凍結 itinerary: `peripatos→agora→garden→chashitsu→study→peripatos`（5 distinct zones / 5 cross-zone legs / 6 waypoint visits）。
- 既存 `run_two_phase_capture` を plan-source 差し替え（scripted-traversal chat client）で再利用。obs 注入は `inject_observation`。organ 6ファイル（loop/cycle/handoff/two_phase/embodiment/geometry）無改変。

## witness（exact/checksum 系、tune-to-pass 閉塞、boolean/byte のみ・effect 非測定）
- **凍結（ADR 時点で確定）**: itinerary + zone-change 判定点（move_t）+ tick 定義。horizon は凍結行程が全 leg 完了に要する tick 数で**一意決定**（成績を見て置く閾値でない）。kinematics 確認要時は calibration run を golden 生成から完全分離（ログ破棄・期待系列変更禁止・不一致=ADR revise）。
- **W1 scripted-itinerary replay fidelity**: 記録 route == 凍結 itinerary（exact/prefix、byte-pinned route events、各 leg 一度境界横断）。`≥K distinct` の成績風閾値でない。
- **W2 λ update-path reached**: `expected_move_ticks==[...]` + `expected_positive_lambda_ticks==[...]` を byte-pin（or quantized λ sequence checksum）。"sustained" 等効果量語を使わない。
- **W3 knob algebra witness**: `sign_inversion_fired`（λ>0 eval tick で `on.temp<off ∧ on.top_p<off ∧ on.rp>off`）。定義に「sampling recomposition の符号確認のみ・生成品質/差分/aha 不問」。generation-phase control（knob-on≡off で phase 条件性）+ record-knob-on pin。
- **W4 determinism（二層 fidelity anchor）**: geometry checksum + Win/WSL byte-parity + 6桁量子化（emitted float + `envelope_provenance` 生 serialized 文字列も `handoff._quantize_embedded_json` で projection 境界再量子化）。anchor A = `run_two_phase_capture(knob=None)`≡baseline byte-parity（既存 test）/ anchor B = traversal driver `knob=None` が同一 scripted plan/obs 下で sampling fields 以外差分ゼロ（allowlist）。

## guard（不可侵）
construction-only・measurement 非再入。effect/divergence/floor/aha proxy/verdict 非 emit、verdict=None、side file（checksum/SHA 集合外）。door② UNMET / door CLOSED / R-budget=0 / holding / measurement-line CLOSE 不変。organ 6ファイル無改変（要改変=Stop→superseding ADR→user 裁定→Codex）。GPL src/ import 禁止・cloud LLM API 必須依存禁止・think=false。既存 golden 回帰ゼロ・byte-parity 不変。main 直 push 禁止。

# grill-goals — M13 aha-substrate-embodiment traversal

grill 確定（コード + M4 golden 実データ検証、user 裁定済）。issue-slicing の入力。

## 診断（入口前提の訂正）
- **embedding ⊥ zone routing**: `reflect_clamp` が `target.zone==destination_zone` を保証（M4 golden 36/36 一致）。real embedding は within-zone (x,z) のみ。
- **collapse の真因 = settle**（LLM が peripatos 58% author）。mocked embedding でない。
- **λ>0 は zone 横断で earn**（`advance_lambda` の move_t）。settle→λ=0。

## 確定ゴール（検証可能）
scripted planner が waypoint observations を消費する **決定論的 traversal harness** を建て、凍結 itinerary
`peripatos→agora→garden→chashitsu→study→peripatos`（5 distinct zones / 5 cross-zone legs / 6 waypoint visits）の
zone 横断で λ を earn → 二相 knob（deep_work∈EVALUATION_MODES）を λ>0 tick で発火。organ 無改変（Option A、既存
`run_two_phase_capture` を plan-source 差し替えで再利用）。Ollama-free 決定論 golden、real 実走は別 ratify。

Done = witness W1-W4 が exact/checksum/boolean で緑（下記 issue の AC↔test）:
- **W1 replay fidelity**: 記録 route == 凍結 itinerary（exact/prefix）。
- **W2 λ update-path**: `expected_move_ticks`/`expected_positive_lambda_ticks` byte-pin 一致。
- **W3 knob algebra**: `sign_inversion_fired`（λ>0 eval tick で符号反転）+ generation control + record-knob-on pin。符号確認のみ・aha/effect 不問。
- **W4 determinism**: committed golden checksum + 6桁量子化（provenance 文字列含む）+ 二層 fidelity anchor + Win/WSL byte-parity。

## Out（不可侵）
effect/divergence/floor/aha proxy/verdict 非 emit。real embedding (a)・real sealed 実走・M3・個性化 door・Godot
実 rendering は defer。door② UNMET / door CLOSED / R-budget=0 / holding / measurement-line CLOSE 不変。

## 実行方式
Loop Engineering（Q2 revise、M4/M2 前例に倣う）。3 縦スライス issue、依存チェーン sequential、subagent-per-issue
（実装 Sonnet / review Opus / 検証 Haiku、各 attempt test-runner→loop-watchdog recheck）。

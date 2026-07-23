# Issue 001 (I1): deterministic traversal harness core + 凍結値 pin + W1 replay fidelity
verify_level: recheck   # AC 直結（決定性 / route wiring）+ 凍結値 pin は tune-to-pass 境界 = 独立再走対象

## Goal
**scripted planner が waypoint observations を消費する決定論的 traversal harness の core** を建てる:
凍結 itinerary `peripatos→agora→garden→chashitsu→study→peripatos`（5 distinct zones / 5 cross-zone legs /
6 waypoint visits）を、既存 `run_two_phase_capture` を plan-source 差し替えで再利用して walk し、**記録 route が
凍結 itinerary と exact match**（W1 replay fidelity）することを in-memory（Ollama-free）で緑にする。organ 6ファイル
無改変。I2（firing witnesses）/ I3（golden・byte-parity）の土台。

## Background
FROZEN ADR `.steering/20260723-m13-aha-substrate-embodiment/design-final.md` +
`loop/20260723-m13-aha-substrate-embodiment/design-final-ref.md`（自己完結 brief）。
一次事実: `reflect_clamp` が `target.zone==destination_zone` を保証 / `advance_lambda` の move_t で λ earn /
既存 `two_phase_live.py::run_two_phase_capture`（Option A sibling driver、organ 無改変、fidelity test で
`knob=None≡run_ecl_loop` pin）+ SamplingSpy + seeded factory を再利用。Codex HIGH-1（閾値でなく exact/checksum）/
HIGH-2（"world 応答" over-read 禁止、scripted harness と明記）反映済。

## Scope
### In
- **凍結値 pin（read-only 先行、tune-to-pass 閉塞）**: 決定論的 transit kinematics（agent speed × physics 30Hz /
  cognition tick、`world/tick.py`・`contracts/geometry.py`）を read-only 確認し、凍結 itinerary が全 leg 境界横断
  するのに要する **horizon を一意に決定**（成績を見て置く閾値でない）。確定した `horizon` / `expected_route`（leg 系列）
  を `.steering/.../design-final.md` witness 節と本 issue に追記して凍結。calibration が要るなら golden 生成から完全
  分離（ログ破棄・期待系列変更禁止・不一致=ADR revise）。
- 新規 `src/erre_sandbox/integration/embodied/traversal_live.py`:
  - 凍結 itinerary 定数（5-leg tour）。
  - **scripted-traversal chat client**（Ollama-free mock）: waypoint observation を消費し対応 destination_zone を
    返す。think=false。"world 応答" と over-read しない（= scripted planner）。
  - obs 注入（`world.inject_observation` / obs_factory 経由）で waypoint stimulus を配置。
  - 既存 `run_two_phase_capture` を **plan-source 差し替え**で再利用（drive body 複製は最小、organ 無改変）。
  - route 抽出 helper（記録 destination_zone/位置系列 → leg 系列）。
- 新規 `tests/test_integration/test_traversal_live.py`（W1 部）:
  - `test_traversal_route_replay_fidelity`: 記録 route == 凍結 itinerary（exact/prefix、各 leg 一度境界横断）。
### Out
- W2 λ update-path / W3 knob algebra（I2）。committed golden / byte-parity / capture script（I3）。
- real qwen3 実走・real embedding・measurement 一切（effect/divergence/floor/aha/verdict 非 emit）。
- organ 6ファイル改変（要改変=Stop→superseding ADR）。

## Allowed Files
- `src/erre_sandbox/integration/embodied/traversal_live.py`（新規）
- `tests/test_integration/test_traversal_live.py`（新規、W1 部。I2/I3 が追記）
- `.steering/20260723-m13-aha-substrate-embodiment/design-final.md`（凍結値 append のみ）
- **無改変厳守**: `two_phase_live.py` / `loop.py` / `cycle.py` / `handoff.py` / `two_phase.py` /
  `locomotion_sampling.py` / `embodiment.py` / `contracts/geometry.py`（read-only 再利用）

## Acceptance Criteria（AC↔test）
- I1-G1 `test_traversal_route_replay_fidelity`: 記録 route == 凍結 itinerary leg 系列（exact/prefix）。
- I1-G2: 凍結値（horizon / expected_route）が ADR + 本 issue に append され、コードの定数と一致（drift なし）。
- I1-G3: organ 6ファイル無改変（diff で確認）。
- CI parity: `pwsh scripts/dev/pre-push-check.ps1` 4 段全緑（既存 golden 回帰ゼロ、PYTHONUTF8=1）。

## Test Plan
`pytest -q tests/test_integration/test_traversal_live.py -k route_replay` + pre-push 4 段。
in-memory（Ollama-free）ゆえ Blender/Godot/Ollama 不要で CI 緑。

## Stop Conditions
- 全 AC 緑（Done）。
- scripted itinerary が全 leg 境界横断せず route が exact match しない → horizon / obs 配置を凍結 discipline 内で
  修正（成績を見て閾値を緩めない = 禁止）。leg 設計自体が transit で境界を越えないなら Stop→ADR revise。
- `run_two_phase_capture` の plan-source 差し替えが organ 改変を強いる → Stop→superseding ADR→user 裁定→Codex。
- budget（max_attempts=6 / no_progress=4 / token_ceiling）到達 → Stop。

## Dependencies
なし（最初）。

## Status
done

## Execution Result

**Status: DONE**（AC 全緑）。

### 変更ファイル
- 新規 `src/erre_sandbox/integration/embodied/traversal_live.py`（431 行）。
- 新規 `tests/test_integration/test_traversal_live.py`（124 行）。
- `.steering/20260723-m13-aha-substrate-embodiment/design-final.md`（witness 節に
  「I1 凍結値確定」追記のみ、append-only）。
- organ 6ファイル（`loop.py`/`cycle.py`/`handoff.py`/`two_phase_live.py`/
  `two_phase.py`/`embodiment.py`/`contracts/geometry.py`/`locomotion_sampling.py`）:
  **無改変**（`git diff --stat` 空を確認）。

### 凍結値（calibration finding、コード定数と ADR に drift ゼロで反映済）
- `TRAVERSAL_HORIZON = 5`（1 leg = 1 cognition tick）。
- `TRAVERSAL_PHYSICS_TICKS_PER_COGNITION = 2000`（calibration 確認済み最小値 1500 +
  余裕。1000 は最長 leg `garden<->chashitsu`/`chashitsu<->study`（centroid 間
  ~66.7m）で未到達、1500/2000/3000 は byte-identical＝到達済）。
- `TRAVERSAL_EXPECTED_ROUTE = (peripatos, agora, garden, chashitsu, study, peripatos)`。

### route 抽出源
**end-of-cognition-tick 物理 zone**（`EclTraceRow.zone` の各 `agent_tick` 窓の最終行、
`extract_visit_sequence` 実装）。理由: 生 30Hz 連続トレースは `garden<->chashitsu` /
`chashitsu<->study` の直線経路が peripatos との Voronoi 三重点近傍を通るため一時的に
`peripatos` へ再突入する（frozen world layout の幾何学的事実、全 `physics_ticks_per_cognition`
で再現、horizon 不足ではない）。tick 境界サンプリングはこの一時的立ち寄りに影響されず、かつ
物理シミュレーションの実到達を要求する（1000-tick 未到達で fail する非同語反復的 witness）。
`decisions[i].plan.destination_zone` 系列（scripted plan の echo）は tautological なので
不採用。

### calibration の要点
一時スクリプト（golden 生成・実装コードから完全分離、ログ破棄済）で
`physics_ticks_per_cognition ∈ {20,100,500,1000,1500,2000,3000}` を走査し
`run_two_phase_capture`（scripted-traversal chat client + peripatos 始点 seed、
`two_phase_knob=None`）を駆動。1 cognition tick = 1 leg（horizon=5）を確認。
move_t 系列は 5 tick 全て 1（各 leg で current_zone≠destination_zone）。

### テスト結果
- `pytest -q tests/test_integration/test_traversal_live.py -k route_replay`: **2 passed**。
- `pytest -q tests/test_integration/test_traversal_live.py`（全 3 test）: **3 passed**。
- `ruff format --check` (新規2ファイル): 緑（already formatted）。
- `ruff check` (新規2ファイル): 緑（All checks passed）。
- `mypy src/erre_sandbox/integration/embodied/traversal_live.py`: 緑（Success, no issues）。
- 既存回帰 `pytest -q tests/test_integration/test_two_phase_live.py`: **20 passed**。
- 広域サニティ `pytest -q tests/test_integration/`: **605 passed**（既存 golden 含め全緑）。

### organ 無改変確認
`git diff --stat` を organ 6ファイル + `two_phase_live.py`/`locomotion_sampling.py` に
対し実行、出力なし（完全に空）＝無改変確認済。

### guard 遵守
effect/divergence/floor/aha proxy/verdict は一切 emit していない。観察量は
`extract_visit_sequence` の exact-match tuple 比較と `pairwise` 隣接不一致チェックのみ
（閾値・スコア・比率なし）。`two_phase_knob=None` で W3 knob algebra は非対象（I2 scope）。

### blocker / 設計不整合
なし。organ 改変は不要だった（Option A のまま sibling driver 差し替えのみで完結）。
ADR revise 級の齟齬なし。1 点、ADR 事前記述の「W1 各 leg 一度ずつ境界横断」を厳密な
連続トレース解釈で読むと `garden<->chashitsu`/`chashitsu<->study` の 2 leg で
一時的な二重横断（peripatos 再突入）が生じる幾何学的事実を calibration で発見したが、
これは「leg 設計自体が transit で境界を越えない」(Stop 条件) には該当しない
（到達は 100% 確認済み）ので、route 抽出源を tick 境界サンプリングに定めることで
ADR の意図（exact/boolean、tune-to-pass でない）を破らずに解決した。ADR 本文には
この finding を「I1 凍結値確定」として append 済み（superseding ADR は不要と判断）。

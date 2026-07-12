# Issue 003 (I3): SocietyReplayScene.tscn に Avatar2 追加 + test_m4_society_replay.py parametrize
verify_level: recheck   # AC2 causal wiring（viewer が N=3 を order_slot 順に解決）= 公開挙動直結

## Goal
既存 viewer（`SocietyReplayViewer.gd`、既に N-agent 対応、L293 `Avatar%d` slot 解決）を活かし、
(a) `SocietyReplayScene.tscn` に **静的 Avatar2 ノードを 1 個追加**、(b) `test_m4_society_replay.py` を
`[m2(N=2), m4(N=3)]` **parametrize**。**先に既存 m2 golden が新 parametrize 形で全緑（回帰ゼロ証明）**、
次いで m4 golden（I4 で landed 後）。EclReplayPlayer.gd / MainScene.tscn / SocietyReplayViewer.gd 無改変。

## Background
FROZEN design-final §E。headless dump 経路は scene を instantiate しない（SocietyReplayViewer.gd:103-112）→
機械 witness(AC4) は N=3 で .gd/.tscn 無改変で既に成立。壁は interactive scene の avatar ノード数と test 定数のみ。
既存 `.tscn` は Avatar0(L40-41)/Avatar1(L43-45) を `AgentAvatar.tscn` ext_resource `7_avatar` で instance。
既存 test は `_GOLDEN_DIR = m2_society_golden` 固定、行数定数 L69(`=40`)/L70(`=16`)、slot L205-208(`[0,1]`)。
Codex M3: 静的 Avatar2 は M2 replay で orphan idle avatar になる（cosmetic、dev-only）が headless dump は
trace に存在する slot のみ dump ゆえ AC 影響ゼロ（decisions.md M3）。Codex L2: M2 先行全緑 → M4 追加の順序。

## Scope
### In
- `godot_project/scenes/dev/SocietyReplayScene.tscn`:
  - **Avatar2 ノードを 1 個 append**（Avatar0/1 ブロック L40-45 を mirror、`7_avatar` ext_resource 再利用、
    `load_steps` 据置 = 新 ext_resource 不要）。order_slot 2 avatar の初期 transform（Avatar1 と別位置）。
- `tests/test_integration/test_m4_society_replay.py`:
  - **parametrize**（fork せず）: `_GOLDEN_DIR` + 行数定数(L69/L70) + slot 集合(L205-208) を golden 毎レコード
    `(golden_dir, n_agents, expected_placement_rows, expected_envelope_rows, expected_slots)` に置換。
    - `expected_placement_rows = n_agents × physics_ticks × cognition_ticks`、`expected_slots = list(range(n_agents))`。
  - 4 つの `@pytest.mark.godot` test（headless dump / deterministic / 5-zone load / idempotent）を
    `[m2(N=2), m4(N=3)]` で parametrize。`canonical_dumps`/`build_expected_placement`/`resolve_godot`/viewer CLI は無改修再利用。
  - **M2 パラメータは即有効**（回帰ゼロ、L2）。**m4 パラメータは golden 未 landed 段階では skip マーカ**
    （I4 で fixture commit 後に有効化）。dump slots == `range(n_agents)` を assert（M3）。
### Out
- SocietyReplayViewer.gd / EclReplayPlayer.gd / MainScene.tscn / 既存 zone .tscn の改変（無改変厳守）。
  m4 golden 生成（I4）。harness/CLI（I1/I2）。

## Allowed Files
- `godot_project/scenes/dev/SocietyReplayScene.tscn`（Avatar2 を 1 ノード append のみ）
- `tests/test_integration/test_m4_society_replay.py`（parametrize のみ、fork 禁止）
- **無改変厳守**: SocietyReplayViewer.gd / EclReplayPlayer.gd / MainScene.tscn / AgentAvatar.tscn / 既存 zone .tscn /
  既存 m2_society_golden fixture

## Acceptance Criteria（AC↔test）
- AC3-G1（回帰ゼロ）: `pytest tests/test_integration/test_m4_society_replay.py -q -k m2`（GODOT_BIN 有り）=
  既存 4 test が m2 パラメータで全緑（byte 一致は既存 committed expected と不変）。
- AC3-G2: parametrize 後も m2 の `test_headless_dump_matches_expected` の dump slots == [0,1]、
  placement 40 / envelope 16 行が不変。
- AC3-G3: `SocietyReplayScene.tscn` が headless load 可能（Avatar2 追加で parse エラーなし、5 zone load 不変）。
- AC3-G4: `test_m4_viz_measurement_guard.py` = passed（parametrize 後の test module が denylist 非在、glob 自動追随）。
- AC3-G5（m4、I4 後有効化）: m4 パラメータで headless dump slots == [0,1,2]、byte 一致（I4 で fixture commit 後）。
- CI parity: `bash scripts/dev/pre-push-check.sh` / `pwsh` 4 段（Godot 非依存は緑、Godot test は GODOT_BIN 有りで実走 / 無しで skip）。

## Test Plan
GODOT_BIN 設定下（`test_godot_project.py` で検証済の永続値）で m2 パラメータの headless dump/determinism/scene-load/
idempotent を実走 → 既存 committed expected と byte 一致（回帰ゼロ）。m4 パラメータは golden 未 landed 段階は
skip（I4 で fixture 追加後に自動有効）。GODOT_BIN 不在時は既存慣習で skip。

## Stop Conditions
- 全 AC 緑（Done、m4 分は I4 後）。
- SocietyReplayViewer.gd を改変しないと N=3 が解決できない → Stop（viewer は既に N-agent 対応 L293、改変不要）。
- 既存 m2 committed expected が byte 変化する → Stop（回帰、parametrize は挙動不変のはず）。
- EclReplayPlayer.gd / MainScene.tscn 改変を要する → Stop（無改変厳守）。
- HOW 越え → Stop → superseding ADR。budget 到達 → Stop。

## Dependencies
- なし（既存 m2 golden + viewer は committed、read-only）。**m4 パラメータの有効化は I4（golden landed）に依存**。

## Status
done

## Execution Result

- `godot_project/scenes/dev/SocietyReplayScene.tscn`: `Avatar2` ノードを 1 個 append
  （Avatar0/1 ブロックを mirror、`7_avatar` ext_resource 再利用、`load_steps=10` 据置、
  transform を Avatar1 と別位置 `(-2, 0, 0)` に）。
- `tests/test_integration/test_m4_society_replay.py`: `_GoldenCase` dataclass +
  `_GOLDEN_CASES`([m2(N=2), m4(N=3)]) + `_golden_params()` ヘルパで
  `_GOLDEN_DIR`/行数定数/slot 集合を golden 毎レコードへ置換。4 つの
  `@pytest.mark.godot` test を parametrize、m4 は `pytest.mark.skip`（I4 で
  fixture 委譲後に解除する reason 明記）。`test_scene_loads_five_zones` は
  `n_agents` から avatar node 数（`Avatar0..N-1`）も検証するよう拡張（I3 の
  Avatar2 追加を機械 witness 化）。`canonical_dumps`/`build_expected_placement`/
  `resolve_godot`/viewer CLI は無改修再利用。

### AC ↔ test 結果（GODOT_BIN 有効、実走）

- AC3-G1（回帰ゼロ）: PASS — `pytest tests/test_integration/test_m4_society_replay.py -q`
  → m2 パラメータで既存 4 test 全緑（`4 passed, 4 skipped`）、既存 committed
  `m2_society_golden/expected_placement.jsonl` は byte 不変（`git status --porcelain`
  で fixture dir 差分なし）。
- AC3-G2: PASS — m2 の `test_headless_dump_matches_expected` で dump slots ==
  `[0, 1]`、placement 40 / envelope 16 行を維持（`expected_slots == list(range(n_agents))`
  も assert）。
- AC3-G3: PASS — `test_scene_loads_five_zones` headless load 成功、5 zone 不変
  + m2 パラメータで avatar node 数 2 個を確認（`SCENE_OK zones=5 avatars=2`）。
- AC3-G4: PASS — `pytest tests/test_integration/test_m4_viz_measurement_guard.py -q`
  → `41 passed`（denylist 非在、glob 自動追随）。
- AC3-G5（m4）: SKIPPED（意図通り）— `m4_society_live_golden` フィクスチャ未着地
  (I4 待ち)、4 test とも `pytest.mark.skip` reason 付きで正直に skip。fake 緑にしない。
- 追加確認: `python -m mypy src` → `Success: no issues found in 240 source files`。
  `python -m ruff check` / `ruff format --check` → 両方緑。

### binding 逸脱

なし。`SocietyReplayViewer.gd` / `EclReplayPlayer.gd` / `MainScene.tscn` /
`AgentAvatar.tscn` / 既存 zone `.tscn` / 既存 `m2_society_golden` fixture は
無改変（`git status --porcelain` で確認、diff は本 issue の Allowed Files 2 件のみ）。

### 追記（I4 sealed golden landed 後、m4 有効化 — 2026-07-13）

I4 (commit 9d37ae6) で `tests/fixtures/m4_society_live_golden/`
(`ecl_trace.jsonl` / `envelope_stream.jsonl` / `decisions.jsonl` /
`manifest.json` / `expected_placement.jsonl`) が sealed landed。本 issue が
入れた m4 `pytest.mark.skip` を除去し、`expected_placement_rows=720` /
`expected_envelope_rows=72`（プレースホルダ `-1` から実測値へ、
`expected_placement.jsonl` を機械カウントして確定）に置換して m4(N=3) を実 test
として有効化。

- `python scripts/m4_society_live_capture.py --verify --artifact-dir
  tests/fixtures/m4_society_live_golden` → **exit 0**（record→replay byte 一致 /
  全 client `inner_invocations==0` / manifest 再 render 一致 / structural
  completeness / constructor fingerprint assert、全 OK ログ出力）。
- `GODOT_BIN` 設定下 `pytest tests/test_integration/test_m4_society_replay.py -q`
  → **8 passed, 0 skipped**（m2(4) + m4(4)、Godot 実走）。m4 の headless dump
  は slots `[0,1,2]` を `order_slot` 順に解決し `expected_placement.jsonl` と
  byte 一致。
- `pytest tests/test_integration/test_m4_society_live.py -q` → **12 passed**
  （回帰なし）。
- binding 逸脱なし（golden fixture 無改変、test の skip 解除 + 定数実測値化のみ）。

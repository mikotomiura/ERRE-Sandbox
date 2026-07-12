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
todo

## Execution Result
（完了時に記入。PR 本文になる）

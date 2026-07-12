# Retrospective: 20260711-m13-m4-code（M13 M4 situated 3D 可視化 実コード Loop）

## Task
FROZEN M4 impl-design ADR（PR #74）を実コードに落とす construction Loop。5 zone geometry-nodes 環境
.glb + 決定性 fingerprint + dev-only SocietyReplayViewer（golden N体 substrate の order_slot 順・trace 通り
決定的再生）+ measurement-zero / GPL 境界 guard。construction であって measurement でない（R-budget=0 不変）。

## Issues Completed（全 6 issue done、各 loop-watchdog recheck PASS）
- **I1**（fe72438）: measurement-zero guard（.py executable AST + .gd text scan、負 fixture 実効）+ GPL/SPDX 境界。
- **I2**（9469b74）: `export_zone_layout.py` + `zone_layout.json` + 純 GLB-JSON パーサ `_glb_json.py`（fail-closed）
  + zone .tscn root drift 6桁是正（33.33→33.333333）+ Zone enum 厳密5 Zazen非含。
- **I3**（0e984f6）: peripatos geometry-nodes .glb pipeline（seed-free / identity / 無圧縮）+ fingerprint +
  同一機 idempotency sha256 一致 + SPDX。
- **I4**（b4c6b2e）: 残り4 zone（study/chashitsu_gn/agora/garden）.glb + fingerprint、5 zone parametrize 緑、
  4 zone idempotent。primitive export_chashitsu.py は段階移行で温存。
- **I5**（c0fabbf）: `SocietyReplayViewer.gd`（motion=trace pass-through echo / speech·anim=envelope、move 非位置、
  別 clock domain 独立系列）+ `SocietyReplayScene.tscn`。EclReplayPlayer.gd / MainScene.tscn 無改変。
- **I6**（eb02b4e）: headless placement 検証（Godot dump→Python canonicalizer 正規化→committed expected byte 一致）
  + `expected_placement.jsonl`(56行) + 5 zone load boolean + idempotent。

## 統合
- pre-push フル CI（ruff format --check + ruff check + mypy src + pytest -q）= ALL CHECKS PASSED（3651 passed）。
- **WSL byte parity 実測 PASS**: 5 fingerprint 全 MATCH + expected_placement.jsonl(56行) MATCH（Linux 再生成
  byte 一致、cross-platform 決定性）。
- TASK-POST cross-review（code-reviewer[Opus] + Codex[gpt-5.5]、GitHub connector 経由）: **両者 HIGH=なし**。
  MEDIUM 3 件採用・反映（876c900）= parser fail-closed 完全実装（§1.3 HIGH-2）/ guard scan 拡張（Attribute+keyword）
  / .tscn コメント是正。不採用 2・user 裁定待ち 1（interactive mode）。

## Deferred
- **interactive mode の scene 実体化 + avatar 駆動**（Codex MEDIUM-2）= design §3.4 と issue I5「最小実装で可」の
  乖離。user 裁定待ち（推奨 = M4 fidelity 別 ADR へ defer）。decisions.md 判断参照。
- LOW 3 件（load_steps / _make_material Any / _with rename）= blockers.md defer。
- skinned humanoid rig/anim・.glb の dev scene wiring（判断3 decouple）= 次 fidelity ADR。

## What Worked
- **subagent-per-issue + loop-watchdog gate**: worker の自己申告 done を verify_level=recheck の独立再走で
  客観 gate。全 issue で機能。
- **dump フォーマットの厳密 pin**（I5/I6 に同一 spec 事前配布）で独立生成の byte 一致を一発達成。
- **fingerprint を committed .glb の純パーサ再計算で生成**（test と同一パーサ）→ byte 一致が構造的に保証、
  Blender 非依存で CI 緑。
- **二者 cross-review が guard/parser の穴を捕捉**: Codex が §1.3 HIGH-2（bufferView 必須）の実装漏れと
  guard の Attribute/keyword 見落としを検出。code-reviewer と guard-robustness で収束。empirical review の価値。

## What Failed
- **Codex 初回 local shell sandbox 起動不能**（`CreateProcessAsUserW failed: 1312`、Windows）+ 未 push branch は
  GitHub connector から不可視 → 判定不能。**対処** = feature branch を push（CI 緑 SHA）してから GitHub connector で
  再レビュー → genuine 二者ゲート成立。degrade でなく push-then-review が正着。
- **local `main` が stale**（PR #72/#73/#74 未反映）で merge-base 誤り → M2 コードが diff 混入。`git fetch` +
  origin/main 基準で是正（feedback_git_fetch_before_ahead_behind 再演、既知パターン）。

## Repeated Failure Patterns
- stale local base の罠（既知）→ cross-review 範囲確定前に必ず `git fetch` + origin/main。
- cross-platform float：6桁量子化で吸収（feedback_golden_crossplatform_float_drift 踏襲、WSL 実測で確認）。

## Docs Updates
- `docs/research-positioning.md` §8 に M4 landed 追記（統合 step）。

## Skill・Command Updates
- なし（既存 Loop 資産で完走）。loop-spawn.sh の対話 TUI 起動は単一エージェント非対応 → subagent-per-issue で代替
  （decisions.md 判断6、汎用パターン）。

## Next Loop
- **user 裁定**: interactive mode = implement now vs M4-fidelity ADR へ defer。
- Layer2 mirror-sim impl-design ADR（別トラック併存）or M4 fidelity（skinned humanoid）別 ADR（順序は user 裁定）。

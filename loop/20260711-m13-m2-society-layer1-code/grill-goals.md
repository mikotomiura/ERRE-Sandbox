# grill-goals — M13 M2 Layer1（N体 determinism、GATING）実コード実装

> grilling skill 実起動（2026-07-11、main checkout、タスクにつき 1 回）の出力。HOW は impl-design ADR
> （`.steering/20260711-m13-m2-impl-design/design-final.md` §M9）で test 名まで凍結済。本 grill は
> 「凍結契約を実コードに落とす際に残る非 HOW 判断分岐」を閉じ、検証可能ゴールを確定した。

## 検証可能ゴール（Done = 各 test が exit code 0 + pre-push 4 段 pass）

### Layer1 GATING（M2 の GO を決める）
| test | issue |
|---|---|
| `test_m2_society_legacy_byte_unchanged`（run_ecl_loop + 既存 golden 完全 byte unchanged） | I1（tick N=1）/ I5（handoff） |
| `test_m2_society_n1_canonical_equivalent`（N=1 が canonical projection で legacy 意味等価） | I2（driver）/ I5（handoff manifest） |
| `test_m2_society_sequential_scheduler_order`（sorted 逐次、gather 非経由） | I2 |
| `test_m2_society_plane2_per_agent_replay`（per-agent record→replay byte 一致） | I2 |
| `test_m2_step_cognition_once_seam`（public seam） | I2 |
| `test_m2_society_event_log_checksum_stable`（event/decision log 全体 checksum byte 一致） | I3 |
| `test_m2_log_carries_self_other_slot_forward_compat`（self_other slot null forward-compat） | I3 |
| `test_m2_pair_interaction_deterministic`（pair_key canonical JSON array substream） | I4 |
| `test_m2_society_determinism_permutation`（登録順 permutation → 同一 checksum） | I4 |
| `test_m2_society_determinism_checklist`（discovery guard: no-wall-clock/named substream/裸非 sorted 非在/ORDER BY/canonical sort） | I4 |
| `test_m2_society_handoff_manifest_pins`（M2 SCHEMA_VERSION / coord / tick 二軸 / determinism pin） | I5 |
| `test_m2_society_golden_matches_committed`（committed N体 golden byte 一致、WSL 実測） | I5 |

### spend guard（measurement 非再入の機械保証）
| test | issue |
|---|---|
| `test_m2_society_no_measurement_computation`（AST、production executable 限定・docstring 除外） | I6 |
| `test_m2_society_llm_call_cap`（gating replay/mock、live cap non-gating） | I6 |

### 統合ゲート
- `bash scripts/dev/pre-push-check.sh`（または `pwsh scripts/dev/pre-push-check.ps1`）4 段
  （ruff format --check / ruff check / mypy src / pytest -q）全 pass。**加えて I5 は WSL でも実測**。

## 閉じた非 HOW 判断分岐（decisions.md DG-1..5）
- DG-1: determinism test の N = permutation/checksum は N=3（chain-push 発火）、pair は N=2、legacy/canonical は N=1。
- DG-2: committed golden は WSL byte 一致実測が必須工程（分岐でなく I5 required）。
- DG-3: 実行モード = Loop（worktree + subagent-per-issue、user 裁定）。
- DG-4: Blender/geometry nodes 本格 3D は Layer1 land 後の M4 spike へ defer（user 裁定「先に A」）。
- DG-5: I5 に Godot EclReplayPlayer.gd bounded 拡張を含める（G-GEAR 編集）。

## 依存構造（issue-slicing）
- I1（tick sorted、foundation）→ I2（society driver）→ I3（event-log checksum）→ I4（pair substream + discovery
  guard）/ I5（handoff + golden、I4 と並列可）→ I6（spend guard、society 完成後に最終）。
- 全 issue `verify_level: recheck`（AC 直結 / 公開 API / determinism 契約 / measurement 非再入）。

## 不可侵（binding、逸脱は Stop→superseding ADR）
construction≠measurement（floor/verdict/scorer/landscape 非計算、R-budget=0）/ over-read 禁止 /
firing⇔detectability 混同禁止 / 5 機序分離継承 / run_ecl_loop 無改変（N=1 legacy byte 不変）/ 単一 agent 純関数
不変 / 凍結 apparatus read-only / Layer2 内部 HOW 前倒し禁止（seam slot 予約のみ）/ reasoning-trace door 保全 /
GPL を src/ に import 禁止 / クラウド LLM 必須依存禁止。

# design-final-ref — M13 live 双方向ループ閉包（tracked 参照）

SSOT = `.steering/20260724-m13-live-loop-closure/design-final.md`（FROZEN、`/reimagine`(v2) + Codex Adopt-with-changes 反映）。
`.steering/` は gitignore ゆえ本 ref が repo 追跡側の load-bearing 抜粋。

## honest framing（不可侵）
**配線であって aha/emergence/effect でない。** M13 aha *機構*（two-phase λ knob）を 3D world ループ内に
**配線**したものであり、創発・aha そのもの・effect の実証ではない。door② UNMET / 計測ライン CLOSE /
R-budget=0 / holding は不変。UI/README/PR で "caused"/"effect"/"emergence" を使わない。measurement 非再入。
許容表現 = "wiring reached each seam" / "production `bootstrap()` unchanged; live-loop root only"。

## 決定（要旨）— 2 平面分離 + 隔離 composition root
- **Plane L（live・非計測）**: Godot が bounded 摂動 → cognition → knob-on cycle → movement → Godot の
  tick-synchronous driven ループ。閉包専用の別 root（`integration/embodied/live_loop.py`）に隔離。
- **Plane G（golden・regression guard）**: capture を無改変 `run_two_phase_capture` に replay し 6 桁量子化
  checksum byte-parity。**closure 証明でなく regression guard**（MEDIUM-3）。closure 証明は W-live が担う。
- 本番 `bootstrap()` / organ / `world/tick.py` は無改変。

## Codex HIGH（設計時、design-final に反映済）
- **HIGH-1**: driven ループは outbound を再 inject しない（outbound owner = `_consume_result` 単一、二重送出検出）。
- **HIGH-2**: W-live は correlation-id の各 seam **到達性のみ**を assert（effect/caused/aha 主張しない）。
- **HIGH-3**: inbound は別 `InboundEnvelope` union / 別 `TypeAdapter`。`ControlEnvelope`（outbound 13 kind）無改変、SCHEMA_VERSION 不変。

## 無改変境界（Allowed Files = binding）
- organ（`loop`/`two_phase_live`/`traversal_live`/`cycle`/`handoff`/`two_phase`/`locomotion_sampling`/`geometry`）: import 駆動のみ。
- production（`bootstrap.py` observational identity / `world/tick.py` 既存 public seam）。
- 既存 `ControlEnvelope` outbound protocol / 既存 golden。
- GPL 分離: `src/` に `import bpy` 無し、`godot_project/` に Python 無し、Python↔Godot は WebSocket のみ。

## 縦スライス I1〜I6（詳細 = `issues/00X.md`）
I1 InboundEnvelope+WorldPerturbationMsg+→PerceptionEvent 写像 / I2 gateway inbound_sink opt-in / I3 live_loop 閉包 root /
I4 Plane G byte-parity golden / I5 Godot send_perturbation+契約 guard / I6 W-live 到達性 witness。

## TASK-POST cross-review（採否 = `.steering/.../decisions.md` 表、詳細下記）
- Codex(gpt-5.5) **Adopt-with-changes**（HIGH2/MED2）+ code-reviewer(Opus) **Approve**（MED2/LOW3）。
- 採用反映済: Codex H1（W-live を plain count 限定・firing_summary_detail 除去）/ H2（emitted_envelope →
  `same_tick_envelope_observed` tick-level honest 化）/ M1（no_double_send 全 kind）/ M2（target_agent_id 検証+
  rejected ledger）/ Opus M1（型注釈 `TypeAdapter[InboundEnvelope]`）/ M2（inbound parse 失敗 error message 精度）/
  LOW docstring。不採用: Opus LOW（deque 化、asyncio.Queue 維持）。
- Codex verbatim = `codex-review-post.md`（本 dir にコピー）。

## scope に含まないもの
I7 real qwen3 sealed 実走（code-path のみ、spend ratify 別ゲート）/ I5 headless-godot live send 実効 pass（環境 gate、
本機 godot 無し・CI `-m "not godot"`、CI 検証部 = `test_envelope_kind_sync` 緑維持 + 純 Python 契約 guard）/
effect/divergence/verdict/detectability/aha-proxy 測定 / phase-wheel 統合（別 task）。

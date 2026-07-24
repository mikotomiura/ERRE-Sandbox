# feat(m13-live-loop): aha 基盤 ↔ 3D 世界を live 双方向に配線（閉包専用 root、production 無改変）

## honest framing（不可侵・最初に読む）

**これは配線であって aha/emergence/effect ではない。** M13 aha *機構*（two-phase λ knob）を
3D world ループ内に **配線**（wire）したものであり、創発・aha そのもの・effect の実証ではない。

- door② UNMET / 計測ライン CLOSE / R-budget=0 / holding は**不変**。
- 許容表現 = "wiring reached each seam" / "production `bootstrap()` unchanged; live-loop root only"。
- UI/README/PR で "caused" / "effect" / "emergence" を使わない（測定は非再入）。
- `live-loop` は**閉包専用の別 composition root**で成立し、本番 phase-wheel への統合は別 task。

## 設計（FROZEN ADR 準拠）

> SSOT の ADR/decisions は `.steering/`（gitignore、ローカル）。repo 追跡側の load-bearing 参照は下記 `loop/` に置く。

- ADR 参照: [`design-final-ref.md`](design-final-ref.md)（honest binding / 2 平面分離 / Allowed Files / Codex HIGH / cross-review 採否）
- grill（検証可能ゴール）: [`grill.md`](grill.md) / 縦スライス issue: [`issues/`](issues/)
- TASK-POST Codex review: [`codex-review-post.md`](codex-review-post.md)（gpt-5.5、review 本体抜粋）
- board / events: [`_loop-board.md`](_loop-board.md) / [`_loop-events.jsonl`](_loop-events.jsonl)
- SSOT（ローカルのみ）: `.steering/20260724-m13-live-loop-closure/{design-final,decisions,codex-review,codex-review-post}.md`

**2 平面分離**: Plane L（live・非計測 driven ループ）が bounded 摂動→cognition→knob-on cycle→movement を
回し per-tick capture を吐く。Plane G（無改変 `run_two_phase_capture` replay の byte-parity）が organ 経路の
非破壊性を保証する regression guard。knob-on cycle は閉包専用 root（新規 `integration/embodied/live_loop.py`）に
隔離し、本番 `bootstrap()` / organ / `world/tick.py` を無改変に保つ。

## 変更内容（縦スライス I1〜I6）

| I | 内容 | 主ファイル |
|---|---|---|
| I1 | `InboundEnvelope` + `WorldPerturbationMsg`（別 union、`ControlEnvelope` 無改変=HIGH-3）+ `→PerceptionEvent` 純関数写像 | `schemas.py`(§7.x 追加のみ) / `integration/inbound.py` |
| I2 | gateway `inbound_sink: InboundSink \| None = None` opt-in（`None` で observational identity、非 None で enqueue） | `integration/gateway.py` / `inbound.py` |
| I3 | 閉包 root: knob-on cycle + driven tick ループ + capture。outbound は `_consume_result` に委譲=**再 inject しない**（HIGH-1）。`knob=None` fidelity byte-identical。同一 loop TaskGroup supervise（MED-2） | `integration/embodied/live_loop.py`(新規) |
| I4 | Plane G: capture→無改変 `run_two_phase_capture` replay の 6 桁量子化 checksum byte-parity（**regression guard**、MED-3） | `tests/.../test_live_loop_golden.py` + golden fixture |
| I5 | Godot `send_perturbation` + inbound UI trigger（`EnvelopeRouter.gd` 無改変=LOW-2、Godot は送信のみ・受信しない） | `godot_project/scripts/WebSocketClient.gd` / `dev/PerturbationTrigger.gd` |
| I6 | W-live correlation-id **到達性** witness（各 seam 通過 boolean、HIGH-2）+ 二重送出検出 boolean（HIGH-1）+ λ>0 eligible 符号反転 count（`two_phase_firing_summary` 無改変再利用）。verdict=None・measurement 非 emit | `integration/embodied/live_loop.py` |

## Codex HIGH の反映

- **HIGH-1（二重送出）**: outbound owner = `_consume_result` 単一。driven ループは `inject_envelope` を呼ばない
  （ソース構造 + `drain_envelopes` 単一 broadcast の二重 pin）。
- **HIGH-2（over-claim）**: W-live は correlation-id の各 seam **到達性のみ**を assert。effect/caused/aha を主張しない。
- **HIGH-3（schema 露出）**: inbound は別 `InboundEnvelope` union / 別 `TypeAdapter`。`ControlEnvelope`（outbound 13 kind）
  は byte-identical、SCHEMA_VERSION 不変、`test_envelope_kind_sync.py` 緑維持。

## 無改変境界（binding、ADR §4）

- organ（`loop`/`two_phase_live`/`traversal_live`/`cycle`/`handoff`/`two_phase`/`locomotion_sampling`/`geometry`）: import 駆動のみ。
- production（`bootstrap.py` observational identity / `world/tick.py` 既存 public seam のみ）。
- 既存 `ControlEnvelope` outbound protocol / 既存 golden。
- GPL 分離: `src/` に `import bpy` 無し、`godot_project/` に Python 無し、Python↔Godot は WebSocket のみ。

## scope に含まないもの

- **I7（real qwen3 sealed 実走）**: code-path のみ設計、実走は spend ratify で別ゲート（未実行）。
- **I5 headless-godot live send の実効 pass**: 環境 gate（本機に godot バイナリ無し・CI `-m "not godot"`）。
  CI 検証部 = `test_envelope_kind_sync.py` 緑維持 + 純 Python inbound 契約 guard。実機実効 pass は Godot 実装機で。
- effect/divergence/floor/verdict/aha-proxy/detectability の測定（measurement 非再入）。
- phase-wheel への統合（別 task）。

## 検証

- 各 issue: AC↔test で pin（verify_level=recheck を Haiku で独立再実行）。
- I3（閉包 root）は Opus code-reviewer **Approve**（HIGH 0）。
- 統合 CI parity: `pwsh scripts/dev/pre-push-check.ps1`（ruff format --check / ruff check / mypy src / pytest -q）4 段。
- WSL⇄Win byte-parity 実測は follow-up（user 裁定）。

## ロールバック

全変更 additive/opt-in。`inbound_sink=None`・knob 未注入・`WorldPerturbationMsg` 未送出で現状復帰。
新規ファイル削除 + gateway/schemas の additive 差分 revert で完全復旧。golden/organ/`bootstrap()`/`ControlEnvelope` 不変。

🤖 Generated with [Claude Code](https://claude.com/claude-code)

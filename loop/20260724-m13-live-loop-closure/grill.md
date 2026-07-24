# grill 結果 — M13 live 双方向ループ閉包（実装フェーズ）

> grilling Skill 実起動（2026-07-24）。goal は FROZEN ADR
> `.steering/20260724-m13-live-loop-closure/design-final.md` §5 で I1〜I6 に確定済ゆえ
> **確認寄り**。本 grill の役割 = Done/Stop を **exit code / test 名**で言える形に固定し、
> 実装中に割れうる分岐を事前に閉じる。

## 検証可能ゴール（task 全体の Done）

全 issue 緑 + 統合フル CI 緑:
`pwsh scripts/dev/pre-push-check.ps1`（ruff format --check / ruff check / mypy src / pytest -q）が
4 段 exit 0。加えて honest binding（配線であって aha/emergence/effect でない）が全 doc/PR に貫通。

## 各 issue の Done（AC↔test、exit code で言える形）

| I | Done test（pytest node、CI 対象=`not godot`） | 主 AC |
|---|---|---|
| I1 | `tests/test_integration/test_inbound.py` 緑 | `WorldPerturbationMsg`/`InboundEnvelope` bounded・`extra=forbid`・`→PerceptionEvent` 純関数写像 |
| I2 | `tests/test_integration/test_gateway_inbound_sink.py` 緑 + 既存 `test_gateway.py` 不変 | `inbound_sink=None` observational identity / 非 None で sink enqueue |
| I3 | `tests/test_integration/test_live_loop.py` 緑 | `knob=None` fidelity byte-identical / driven ループが move envelope を単一 broadcast（二重送出無し） |
| I4 | `tests/test_integration/test_live_loop_golden.py` 緑 | capture→無改変 `run_two_phase_capture` replay の 6 桁量子化 checksum byte-parity |
| I5 | `tests/test_envelope_kind_sync.py` 緑維持 + `tests/test_integration/test_inbound_gdscript_contract.py` 緑（純 Python）; `@pytest.mark.godot` の live send は環境 gate（下記 G3） | Godot `send_perturbation` + UI trigger、`EnvelopeRouter.gd` 無改変 |
| I6 | `tests/test_integration/test_live_loop_witness.py` 緑 | correlation-id 各 seam 到達性 boolean / 二重送出検出 / λ>0 eligible 符号反転 count（`two_phase_firing_summary` 再利用） |

## Stop 条件（即エスカレート）

- Allowed Files（ADR §4）を超える変更が必要になった（organ/production/`ControlEnvelope`/既存 golden に触れる必要）。
- `inbound_sink=None` で既存 `test_gateway.py` が 1 つでも落ちる（observational identity 破れ）。
- `knob=None` fidelity が byte-identical にならない（organ drift）。
- 同一 fingerprint の失敗反復（no-progress）。
- schema/新規依存の追加が必要（extras-only dep 新規 import は 3 点セット必須、逸脱時 Stop）。

## grill 決定（分岐の事前確定）

### G1 — `WorldPerturbationMsg`/`InboundEnvelope` 配置 = schemas.py §7.x（型）+ integration/inbound.py（写像+sink）
- **決定**: schema 型 2 つは `schemas.py` の §7 直後（§7.x）に追加。`→PerceptionEvent` 純関数写像と
  `InboundSink`（asyncio.Queue + correlation-id 付与）は `integration/inbound.py`。
- **理由**: ADR §4「修正」で確定済。schema は SSOT ゆえ型は schemas.py、振る舞い（写像/sink）は integration。
- **却下**: 型も inbound.py に置く案（schema SSOT 分散を招く）。

### G2 — correlation-id は **loop 所有の per-tick trace 台帳**（PerceptionEvent/MoveMsg に field を足さない）
- **決定**: `correlation_id` は `WorldPerturbationMsg`（新規・我々が所有）の field として運ぶ。
  W-live 到達性 witness は **`live_loop.py` の per-tick trace 構造**が
  「corr-id X が tick i で 各 seam（perturbation→PerceptionEvent→capture slot→firing_summary tick→emitted envelopes）に
  現れた」を構造的に記録して boolean assert する。**PerceptionEvent（既存 obs）にも MoveMsg（既存 outbound）にも
  corr-id field を追加しない**。
- **理由**: HIGH-2 は「到達性のみ」。driven ループは tick 同期で index を持つゆえ corr-id↔tick の対応は**構造的**に
  取れる（design.md v2）。既存 schema（PerceptionEvent/`ControlEnvelope`）無改変 binding を守る。
- **却下**: PerceptionEvent に corr-id field 追加（既存 obs schema 改変・organ 波及リスク）。

### G3 — I5 の Godot live 検証は**環境 gate**（I7 spend-gate と同型の honest 分離）
- **決定**: 本機（G-GEAR）に godot バイナリ無し（`resolve_godot()`→None→skip、CI は `-m "not godot"`）。
  I5 の CI 検証可能部 = (a) `test_envelope_kind_sync.py` 緑維持（inbound kind を `ControlEnvelope` に混ぜない=HIGH-3 で
  構造保証）+ (b) 純 Python の inbound 契約 guard（gdscript が組む frame payload を Python `InboundEnvelope` adapter が
  validate する `test_envelope_kind_sync.py` 同型 guard）。**実 headless-godot send の実効 pass は Godot 実装機（MacBook）へ deferred**。
- **理由**: 環境非依存で緑にできる部分と、Godot バイナリ依存部を分離。I7（real qwen3, spend-gate）と同じ「code-path/契約は今・実走は別ゲート」idiom。
- **却下**: I5 を「headless-godot 実効 pass 必須」にする（本機で緑不能→ block）。

### G4 — 実行方式 = per-issue subagent Loop（**spawn は user 明示承認ゲート**）
- **決定**: ADR §5/DA-5 と loop-engineering.md が binding =「各 issue を subagent で実行、main はオーケストレータに徹する」
  （実装 Sonnet / review Opus / 検証 Haiku）。ただし **subagent spawn は user 明示承認が要る**
  （memory `feedback_subagent_delegation_explicit_only` / loop-engineering.md L49）。
- **理由**: memory binding + 本 prompt 明記 + base 制約（Agent tool は user 要請時のみ）。
- **反映**: issue-slicing 後、issues + spawn/worktree 方針を提示して user 承認を得てから spawn する。

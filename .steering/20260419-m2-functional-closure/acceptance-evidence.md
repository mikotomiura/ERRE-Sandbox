# T21 MVP §4.4 受け入れ evidence

| # | 検収条件 | 結果 | Evidence |
|---|---|---|---|
| 1 | ollama + gateway listen | ✅ PASS | `evidence/gateway-health-20260420-002242.json` (`schema_version=0.1.0-m2`, `status=ok`, `active_sessions=2`) + `evidence/ollama-tags-20260420-002242.json` (qwen3:8b / nomic-embed-text:latest) + `evidence/listen-ports-20260420-002242.txt` (0.0.0.0:8000 / 127.0.0.1:11434 Listen) |
| 2 | Kant 10s ごと LLM 応答 | ✅ PASS | `evidence/cognition-ticks-20260420-002242.log` (40 行抜粋、`api/chat` + `api/embed` の ~10s cadence、 00:10:59→00:23:21 の ~12 分で 20 chat / 33 embed) |
| 3 | episodic_memory ≥5 + recall_count>0 | ✅ PASS | `evidence/episodic-memory-summary-20260420-002242.txt` (**COUNT=20, MAX(recall_count)=23**) + `evidence/episodic-memory-sample-20260420-002242.txt` (10 件 top サンプル、peripatos↔study を 10 往復記録) |
| 4 | Godot avatar 30Hz 歩行 | ⏳ 要 Mac 側録画 | `evidence/godot-walking-YYYYMMDD-HHMMSS.mp4` (MacBook で 30s 以上 record、peripatos↔study 移動の visual 確認) |

## 実施環境
- 実施日: 2026-04-20 00:00-00:25 JST
- G-GEAR: Windows 11 Home (mikoto-g-gear) + RTX 5060 Ti 16GB
- MacBook: MacBook Air M4, Godot 4.6.2.stable.official
- branch: `feature/t21-m2-functional-closure`
- schema_version: `0.1.0-m2`
- Ollama models: `qwen3:8b` (5.2 GB) + `nomic-embed-text:latest` (274 MB)

## T21 live 検証中に発見 + 修正した bug 2 件

| # | 症状 | 原因 | Fix |
|---|---|---|---|
| 1 | Orchestrator 起動後 cognition 初回 tick で `sqlite3.OperationalError: no such table: episodic_memory` | `bootstrap.py` で `MemoryStore(...)` instantiate 後に `create_schema()` を呼ぶ処理が欠けていた | `src/erre_sandbox/bootstrap.py` の `MemoryStore` 直後に `memory.create_schema()` を追加 (idempotent: `CREATE TABLE IF NOT EXISTS`) |
| 2 | cognition 10s で回るが `episodic_memory` が 0 のまま成長しない — agent が zone を跨がないため observation が発生しない | `cognition/cycle.py:_build_envelopes` が MoveMsg の target を「現在の x/y/z + zone フィールド差し替え」で作成 → `step_kinematics` の `locate_zone(dest.x,dest.y,dest.z)` が現在 zone を再計算 → zone_changed=None → observation 未発生 | `src/erre_sandbox/world/tick.py:_consume_result` で `locate_zone(tgt.x,tgt.y,tgt.z) ≠ tgt.zone` を検知したら `default_spawn(tgt.zone)` に座標を resolve (layer 越境を避け world 側で処理) |

両 fix を適用後、59 既存テスト (`test_bootstrap` + `test_world/`) 全 PASS、cognition が実際に peripatos↔study を 10 往復し episodic_memory に zone_transition が記録された。

## GAP-1 (WorldRuntime ↔ Gateway 配線) 解消宣言

T19 で発覚した **GAP-1** (`.steering/20260419-m2-integration-e2e-execution/known-gaps.md#gap-1`) は:

- PR #36 (`bootstrap.py` + `__main__.py`) による composition root 提供
- 本 T21 live 検証で発見・修正した bug 2 件 (`bootstrap.create_schema` + `world/tick` zone resolve)

の合計で、**MASTER-PLAN §4.4 の 4 検収項目のうち #1-#3 が実機 evidence 付きで PASS** 可能な状態に到達。#4 は Mac 側録画待ちのみ。

## 参照
- T21 設計: `.steering/20260419-m2-functional-closure/design.md`
- T21 handoff: `.steering/20260419-m2-functional-closure/handoff-to-g-gear.md`
- PR #36: https://github.com/mikotomiura/ERRE-Sandbox/pull/36
- MASTER-PLAN §4.4: `.steering/20260418-implementation-plan/MASTER-PLAN.md`
- known-gaps GAP-1: `.steering/20260419-m2-integration-e2e-execution/known-gaps.md#gap-1`

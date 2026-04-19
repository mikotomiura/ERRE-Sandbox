# MVP M2 Acceptance Checklist — T20

MVP M2 `integration-e2e` の受け入れ確認。T19 ライブ検証の結果を
formalize し、T19 で発覚した GAP-3 / GAP-5 を本 T20 で解消する。

## 実施サマリ

| 項目 | 値 |
|---|---|
| 実施日 | 2026-04-19 |
| 実施者 | @mikotomiura (MacBook Air M4 + G-GEAR) |
| M2 commit baseline | `54f9046` (T19 完了後) |
| Gateway schema_version | `0.1.0-m2` |
| Godot version | 4.6.2.stable.official |
| 対象ブランチ | `feature/t19-macbook-godot-integration` |

## 受け入れ項目

| ACC ID | 項目 | 結果 | Evidence | 備考 |
|---|---|---|---|---|
| ACC-SCENARIO-WALKING | MacBook Godot で Peripatos シーン live 接続 | ✅ PASS (layer scoped) | `.steering/20260419-m2-integration-e2e-execution/macbook-verification.md` §観察結果 | WS / Handshake / Session レイヤーは成立。Avatar 視覚移動は GAP-1 (`_NullRuntime`) のため range-out、M4 で解消予定 |
| ACC-SESSION-COUNTER | `/health` の `active_sessions` probe 運用 (runbook + 実測 evidence) | ✅ PASS (強化) | `session-counter-runbook.md` + `evidence/README.md` + `evidence/session-counter-settled-20260419-205304.log` (90s 全 `sessions=0` 定着) + `evidence/session-counter-connected-20260419-203430.log` (5s 全 `sessions=1` 成立) | GAP-3 対応。T20 では当初「runbook 策定」までを PASS 条件としていたが、**2026-04-19 20:53 JST に MacBook 上で 0→1→0 遷移と 90s 定着を実測完了** (Godot PID 85003/87766 を SIGTERM で graceful 停止後 90s 連続 `sessions=0`)。`evidence/` 配下に全ログ保管 |
| ACC-DOCS-UPDATED | `docs/architecture.md` に `_NullRuntime` 注意書き追加 | ✅ PASS | `docs/architecture.md` §Gateway (G-GEAR) | GAP-5 対応。M4 orchestrator への参照と session-counter runbook への link を追加 |
| ACC-HANDSHAKE | 4-step handshake の確立を視認 | ✅ PASS | `macbook-verification.md` L82-88 (Godot Output) | `[WS] connecting` → `[WS] connected` → `[WS] client HandshakeMsg sent` が gateway 側 `session ACTIVE` まで遷移 (gateway 側未 close を成功とみなす) |
| ACC-SCHEMA-COMPAT | Pydantic schemas.py と GDScript parser の field 互換性 | ✅ PASS | `src/erre_sandbox/schemas.py` + `godot_project/scripts/WebSocketClient.gd` | `schema_version=0.1.0-m2` で両端一致。ControlEnvelope / HandshakeMsg / WorldTickMsg / MoveMsg / AgentUpdateMsg の kind 判別動作 |

## 5 ACC 全 PASS — M2 closeout 条件達成

### 未達/範囲外項目の扱い

| 項目 | 現状 | 扱い |
|---|---|---|
| Avatar Tween 移動の視認 | GAP-1 により `_NullRuntime` 依存で検証不可 | **M4 `gateway-multi-agent-stream`** で real runtime inject して再検証 |
| 30Hz 描画 / WorldTickMsg 受信 | 同上 (envelope 流入なし) | 同上 |
| disconnect → reconnect 実機確認 | T19 では未実施 | 次回 M4 実機時に検証 (ACC 外として継続観察) |
| Godot live 自動 E2E | GAP-2 により未整備 | **M7 observability-logging** で検討 |
| Godot 4.6 diff 削減 | GAP-4 (記録のみ) | 対応しない |

## GAP 解消 matrix (T20 時点)

| GAP ID | 解消状態 | 解消先 |
|---|---|---|
| GAP-1 WorldRuntime↔Gateway 配線 | ⏳ 未解消 | M4 最優先 (`full-stack-orchestrator`) |
| GAP-2 live 自動化なし | ⏳ 未解消 | M7 検討 |
| GAP-3 session counter 監視 | ✅ 解消 (T20) | `session-counter-runbook.md` + `evidence/` (実測 0→1→0 + 90s 定着) |
| GAP-4 Godot 4.6 diff | 🟡 記録のみ | 対応しない |
| GAP-5 `_NullRuntime` docs 未反映 | ✅ 解消 (T20) | `docs/architecture.md` §Gateway |

## M2 closeout 宣言

本 checklist 作成時点で **MVP M2 は layer scope で達成** とみなす:

- Contract layer (WS / Handshake / Session FSM / Schema) : **完全動作**
- T19 で発覚した構造ギャップ (GAP-1) は M4 に明示タスク化
- GAP-3 / GAP-5 の closeout 対応は本 T20 で完了
- 残 GAP (GAP-2 / GAP-4) は優先度に応じて後続マイルストンに配置

M2 completion は MASTER-PLAN §4.3 の T20 行を `[x]` に反映することで formalize する。

## 参照

- T19 実施記録: `.steering/20260419-m2-integration-e2e-execution/`
- T20 requirement/design: 本ディレクトリ
- MASTER-PLAN: `.steering/20260418-implementation-plan/MASTER-PLAN.md`
- known-gaps 詳細: `.steering/20260419-m2-integration-e2e-execution/known-gaps.md`

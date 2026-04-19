# T20 M2 Acceptance — MVP M2 closeout + T19 known-gaps 吸収

## 背景

MVP M2 `integration-e2e` は T11-T19 までで以下が contract-level で動作することを確認済み:

- T14 Gateway (FastAPI + WebSocket) + handshake + session FSM
- T15-T17 Godot client (peripatos scene, WS client, fixture replay)
- T18 UI dashboard (optional)
- T19 両機合流 live integration (MacBook Godot ↔ G-GEAR gateway)

ただし T19 実施時に 5 件の **known gaps** が発覚
(`.steering/20260419-m2-integration-e2e-execution/known-gaps.md`)。
うち 2 件 (GAP-3, GAP-5) は **T20 acceptance に組み込んで解消** する方針が確定済み。

T20 は MVP M2 を formally 閉じ、M4 kickoff (GAP-1 full-stack orchestrator) の
前提を整える **closeout タスク** である。

## ゴール

1. M2 の acceptance checklist (`ACC-*`) が **全てチェック済** になっている
2. T19 known-gaps の GAP-3 / GAP-5 が解消されている
3. M2 completion が `.steering/20260418-implementation-plan/MASTER-PLAN.md` の tasklist に反映
4. `git tag m2-acceptance` もしくは PR マージで M2 を formally 閉じる (運用判断)

## スコープ

### 含むもの

- **ACC-SCENARIO-WALKING** — MacBook Godot で 1 agent が peripatos を walking するシナリオの手動視認 (T19 で既に一度実施、記録を acceptance として formalize)
- **ACC-SESSION-COUNTER (GAP-3 対応)** — MacBook から `curl http://<g-gear-ip>:8000/health | jq .active_sessions` を叩いて Godot 接続中に 1 以上を確認する runbook 追加
- **ACC-DOCS-UPDATED (GAP-5 対応)** — `docs/architecture.md` の Gateway セクションに `_NullRuntime` は debug-only default、production は `make_app(runtime=...)` で real runtime inject 必須と追記
- **ACC-HANDSHAKE** — handshake 4-step (client-hello → server-hello → ready → first envelope) の log / trace を記録として保存
- **ACC-SCHEMA-COMPAT** — Pydantic v2 schemas.py と GDScript parser の field 互換性を一覧表として残す
- **acceptance-checklist.md** を本タスクディレクトリに作成し、各 ACC の PASS/FAIL と evidence (ログ・スクリーンショット・commit sha) を記録
- MASTER-PLAN の T20 行を `[x]` に更新
- M2 completion の commit + tag

### 含まないもの

- **GAP-1 full-stack orchestrator 実装** → M4 `gateway-multi-agent-stream` の責務
- **GAP-2 Godot live の自動化テスト** → M7 observability で検討
- **GAP-4 Godot 4.6 diff の削減** → 記録のみ、対応しない
- 新機能追加 / リファクタリング (本タスクは closeout のみ)
- Godot / gateway コード自体の変更 (docs と runbook のみ)

## 受け入れ条件

- [ ] `acceptance-checklist.md` が本ディレクトリに存在し、全 ACC が PASS
- [ ] `docs/architecture.md` Gateway セクションに `_NullRuntime` 注意書きが追加されている
- [ ] `ACC-SESSION-COUNTER` runbook (curl one-liner + 期待値) が checklist に明記
- [ ] GAP-3 / GAP-5 が known-gaps.md 上で "解消済" として marking される
- [ ] MASTER-PLAN §4.3 の T20 行が `[x]` にチェック
- [ ] M2 closeout を記録する commit が `main` に向けて PR 作成可能な状態

## 関連ドキュメント

- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.3 (T20 `m2-acceptance`)
- `.steering/20260419-m2-integration-e2e-execution/known-gaps.md` (GAP-3, GAP-5)
- `.steering/20260419-m2-integration-e2e-execution/macbook-verification.md` (T19 live 記録)
- `.steering/20260419-gateway-fastapi-ws/` (T14 gateway 設計 — `_NullRuntime` の位置)
- `docs/architecture.md` Gateway セクション (ACC-DOCS-UPDATED の対象)

## 運用メモ

- 破壊と構築 (/reimagine) 適用: **No**
- 理由: 本タスクは closeout / documentation / runbook であり、設計判断や新規実装を含まない。受け入れ条件は T19 実施時点で既に確定済みの ACC 群を formalize するのみ。複数案検討の余地がない。

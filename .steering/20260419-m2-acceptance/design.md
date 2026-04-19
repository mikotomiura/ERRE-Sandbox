# 設計 — T20 M2 Acceptance

## 実装アプローチ

**Closeout タスク** として、コード変更は最小限に抑え、ドキュメントと
runbook の整備を中心に据える。以下の 3 軸で進める:

1. **Formalize** — T19 で一度視認した内容を `acceptance-checklist.md` に
   evidence (ログ抜粋 / commit sha / スクリーンショット参照) 付きで記録
2. **Close gaps** — GAP-3 (SESSION-COUNTER runbook 追加) と
   GAP-5 (docs/architecture.md の `_NullRuntime` 注意書き) を解消
3. **Mark complete** — MASTER-PLAN tasklist の T20 行を `[x]` に、
   known-gaps.md 上の GAP-3/5 を "解消済" として marking、M2 completion commit

意図的に **コード (src/, godot_project/) を変更しない**。
本タスクは M2 の closeout であり、新しいコード改修が入ると
T19 live 検証結果の有効性が失われる。

## 変更対象

### 修正するファイル

- `docs/architecture.md` — L96 "Gateway (G-GEAR)" セクションに `_NullRuntime` の
  注意書きと M4 orchestrator への参照を追加 (GAP-5)
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` — §4.3 の
  T20 行を `- [ ]` → `- [x]`、M2 completion note 追記
- `.steering/20260419-m2-integration-e2e-execution/known-gaps.md` —
  GAP-3 / GAP-5 のサマリ表に "✅ 解消 (T20)" 列を追加

### 新規作成するファイル

- `.steering/20260419-m2-acceptance/acceptance-checklist.md` —
  5 つの ACC (SCENARIO-WALKING / SESSION-COUNTER / DOCS-UPDATED /
  HANDSHAKE / SCHEMA-COMPAT) を表形式で記録。各行に
  PASS/FAIL / evidence / commit sha / 実施日
- `.steering/20260419-m2-acceptance/session-counter-runbook.md` —
  GAP-3 対応の curl one-liner runbook。MacBook から G-GEAR の
  `/health` を probe する手順と期待値
- `.steering/20260419-m2-acceptance/decisions.md` (必要に応じて) —
  M2 closeout における判断を記録

### 削除するファイル

- なし

## 影響範囲

- **コード**: ゼロ (src/, godot_project/, tests/ は無変更)
- **ドキュメント**: `docs/architecture.md` の Gateway セクション 1 箇所
- **作業記録**: MASTER-PLAN と known-gaps.md のマーキング更新
- **Git**: 新規タスクディレクトリ追加 + 上記 3 ファイルの update
- **下流タスク**: M4 kickoff (GAP-1) が本タスク完了後に着手可能となる

## 既存パターンとの整合性

- `.steering/` 配下のタスクは全て `requirement.md` / `design.md` /
  `tasklist.md` の 3 点セット + 任意の追加ファイルという pattern。
  本タスクは acceptance-checklist.md / session-counter-runbook.md を追加
- `docs/architecture.md` は sphinx 化されていないフラット markdown。
  既存 "### Gateway (G-GEAR)" セクション (L96-101) に箇条書きを足す形で整合
- MASTER-PLAN tasklist のマーキングは既存の `- [x]` 形式に従う

## テスト戦略

- **単体テスト**: なし (コード変更なし)
- **統合テスト**: なし (T19 で実施済、本タスクでは再実施しない)
- **E2E テスト**: なし (GAP-2 として M7 で検討)
- **検証方法**:
  - `docs/architecture.md` の変更を markdown viewer で確認
  - `acceptance-checklist.md` の全 ACC が PASS であることを目視確認
  - `curl http://<g-gear-ip>:8000/health | jq .active_sessions` を MacBook から
    叩き、0 (Godot 未接続時) と 1 (Godot 接続中) の両方を確認 (ACC-SESSION-COUNTER)

## ロールバック計画

- 全変更は markdown ドキュメントのみ。問題があれば `git revert` で即座に戻せる
- コード変更ゼロなので live integration (T19) の動作は影響を受けない
- MASTER-PLAN の `[x]` マーキングも単純な markdown edit なので戻し可能

## レビュー方針

- `code-reviewer` subagent は docs 中心のため優先度低 (skip 可)
- ただし `docs/architecture.md` の追記内容は
  `.steering/20260419-gateway-fastapi-ws/` と矛盾しないか
  セルフチェック (`_NullRuntime` の位置は `gateway.py:444-458`)

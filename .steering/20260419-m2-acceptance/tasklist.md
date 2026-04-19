# タスクリスト — T20 M2 Acceptance

## 準備
- [x] `docs/architecture.md` L90-114 (Gateway セクション) を再読
- [x] `.steering/20260419-m2-integration-e2e-execution/known-gaps.md` GAP-3/5 を再読
- [x] `.steering/20260419-m2-integration-e2e-execution/macbook-verification.md` の evidence 所在を確認
- [x] `src/erre_sandbox/integration/gateway.py` L444-458 (`_NullRuntime`) を確認

## 実装 (Documentation / Runbook)

### ACC-DOCS-UPDATED (GAP-5 対応)
- [x] `docs/architecture.md` の Gateway セクションに `_NullRuntime` 注意書き + M4 参照 + runbook 参照を追記
- [x] markdown 追記内容のセルフチェック (gateway.py:444-458 の位置と整合)

### ACC-SESSION-COUNTER (GAP-3 対応)
- [x] `.steering/20260419-m2-acceptance/session-counter-runbook.md` を新規作成 (one-liner + 1Hz loop + troubleshoot 表)

### ACC-* 全体: acceptance-checklist.md 作成
- [x] `.steering/20260419-m2-acceptance/acceptance-checklist.md` を新規作成 (5 ACC 全 PASS + GAP 解消 matrix + M2 closeout 宣言)

## known-gaps マーキング
- [x] `known-gaps.md` サマリ表に "解消状態" 列追加、GAP-3/5 を "✅ 解消 (T20)" として marking

## MASTER-PLAN 更新
- [x] §4.4 MVP 検収条件に T20 closeout note を追記
- [x] `.steering/YYYYMMDD-m2-acceptance/` 行を `[x]` に更新
- [x] GAP-1 依存の項目 4 件に "(GAP-1 → M4 待ち)" notation を付加

## レビュー (軽量)
- [x] acceptance-checklist.md の 5 ACC が全 PASS であること目視確認
- [x] 変更ファイル 3 + 新規 4 (runbook / checklist / design / requirement / tasklist) の差分確認
- [ ] (optional) `code-reviewer` subagent に docs 更新のみレビュー依頼 → closeout 規模が小さいため skip

## 完了処理
- [ ] `/finish-task` で M2 closeout commit 提案
- [ ] (運用判断) `git tag v0.1.0-m2` もしくは PR 作成 → main へ merge 後にタグ付けする方針

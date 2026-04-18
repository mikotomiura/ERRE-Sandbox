# タスクリスト

## 準備
- [x] MASTER-PLAN §8 と decisions.md §判断 3 を再確認
- [x] PDF 存在確認、`.gitignore` の現状確認
- [x] `feature/pdf-extract-baseline` ブランチ作成
- [x] `.steering/20260418-pdf-extract-baseline/` 作成と requirement/design 記入

## 実装
- [x] I1. `mkdir -p docs/_pdf_derived`
- [x] I2. `pdftotext -layout "ERRE-Sandbox_v0.2.pdf" docs/_pdf_derived/erre-sandbox-v0.2.txt`
      → 939 行 / 73 KB
- [x] I3. `.gitignore` に `docs/_pdf_derived/` を追記 (コメント付き)

## 検証
- [x] V1. ファイル存在、939 行 (>= 500 OK)
- [x] V2. 48 ヒット (ERRE-Sandbox / peripatos / chashitsu / 守破離)
- [x] V3. `git check-ignore` で `.gitignore:5:docs/_pdf_derived/` が match
- [x] V4. `git status --short` に `docs/_pdf_derived/` 出現せず

## レビュー
- [x] R1. code-reviewer 不要
- [x] R2. decisions.md 不要 (新規判断なし)

## ドキュメント
- [x] DOC1. `.steering/_setup-progress.md` の Phase 8 セクションに T03 完了を追記

## 完了処理
- [ ] DONE1. git add `.gitignore` `.steering/_setup-progress.md` `.steering/20260418-pdf-extract-baseline/`
- [ ] DONE2. git commit (Conventional Commits, scope: docs)
- [ ] DONE3. git push -u origin feature/pdf-extract-baseline
- [ ] DONE4. gh pr create (base=main)
- [ ] DONE5. GitHub で merge (ユーザー実行)
- [ ] DONE6. ローカル cleanup (main pull, feature ブランチ削除)

# 設計

## 実装アプローチ

MASTER-PLAN §8.2 のコマンドをそのまま実行する:

```bash
mkdir -p docs/_pdf_derived
pdftotext -layout "ERRE-Sandbox_v0.2.pdf" docs/_pdf_derived/erre-sandbox-v0.2.txt
# .gitignore に docs/_pdf_derived/ を追記 (既に無い場合のみ)
```

**`-layout` オプション採用理由**: レイアウト保持版は 2 カラム PDF の列順を
崩さず、見出し階層とインデントが維持される。Claude Code が章単位検索
(grep / head) で使いやすい。

## 変更対象

### 修正するファイル

- `.gitignore` — `docs/_pdf_derived/` 行を追記
- `.steering/_setup-progress.md` — Phase 8 セクションに T03 完了を追記

### 新規作成するファイル

- `docs/_pdf_derived/erre-sandbox-v0.2.txt` — **Git 管理外** (派生物)

### 削除するファイル

- なし

## 影響範囲

- **ローカル環境のみ**。生成物は gitignore で除外、リポジトリには入らない
- G-GEAR 側でも同じ T03 を個別実行することで、両機で同じテキストが利用可能
- `.gitignore` 変更により、今後 `docs/_pdf_derived/` 配下の何らかが誤って
  tracked に入ることを構造的に防止

## 既存パターンとの整合性

- `.gitignore` の既存エントリ `ERRE-Sandbox_v0.2.pdf` と整合
  (PDF 本体も派生物も両方除外)
- MASTER-PLAN §8.2 の手順をそのまま踏襲

## テスト戦略

環境構築と同種 (派生物生成) なので単体/統合テストは該当しない。
**機械検証**を以下で代替:

```bash
# ファイル存在と行数
test -f docs/_pdf_derived/erre-sandbox-v0.2.txt
wc -l docs/_pdf_derived/erre-sandbox-v0.2.txt         # >= 500 行を期待

# 想定キーワードの含有確認
grep -E "ERRE-Sandbox|peripatos|chashitsu|守破離" \
  docs/_pdf_derived/erre-sandbox-v0.2.txt | head -5

# gitignore 効果の確認
git status --short docs/_pdf_derived/                  # 空出力 = untracked かつ ignore
git check-ignore -v docs/_pdf_derived/erre-sandbox-v0.2.txt
```

## ロールバック計画

- `docs/_pdf_derived/` ディレクトリを `rm -rf` で削除するだけ
  (Git 管理外なのでリポジトリ影響なし)
- `.gitignore` の変更は `git checkout -- .gitignore` で戻せる
- `.steering/_setup-progress.md` も同じく `git checkout` で戻せる

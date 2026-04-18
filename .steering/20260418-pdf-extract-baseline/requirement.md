# T03 pdf-extract-baseline

## 背景

`ERRE-Sandbox_v0.2.pdf` (21p, 82KB) はプロジェクトの根拠資料として
ルート配置 + `.gitignore` 済みの状態で存在する。

`.steering/20260418-implementation-plan/decisions.md` §判断 3 で決定済み:
**PDF 原文の都度 Read はコンテキスト消費が大きい → pdftotext 化したテキストを主参照とする**。
日常の実装判断は `docs/*.md` を正とし、原文が必要な時はテキスト版を章単位で検索する。

T02 で poppler (pdftotext 26.04.0) を導入済み。今このタイミングで
テキスト化する前提が整った。

## ゴール

`docs/_pdf_derived/erre-sandbox-v0.2.txt` を生成し、以後の Claude Code セッション
から `Read docs/_pdf_derived/erre-sandbox-v0.2.txt` で章単位参照が可能な状態を作る。

生成物は `.gitignore` 下で未追跡のまま (派生物なのでリポジトリに含めない)、
各開発機が個別に T03 を実行して手元に生成する運用とする。

## スコープ

### 含むもの

- `docs/_pdf_derived/` ディレクトリ作成
- `pdftotext -layout` で `ERRE-Sandbox_v0.2.pdf` をテキスト化
- `.gitignore` に `docs/_pdf_derived/` 行を追記
- 生成物の目視スポット確認 (行数 / 章タイトルの存在)
- 生成手順を README 風に `docs/_pdf_derived/.placeholder` などで残すか判断

### 含まないもの

- テキスト版と docs/*.md のドリフト突合 → M2/M5 完了後の別タスクで実施
- PDF 内の画像抽出 (必要になった時点で別タスク)
- docs/*.md の編集 (T03 はテキスト化のみ)

## 受け入れ条件

- [ ] `docs/_pdf_derived/erre-sandbox-v0.2.txt` が存在し、>=500 行 (21p なら妥当)
- [ ] ファイルに「ERRE-Sandbox」「peripatos」「chashitsu」などの想定キーワードが含まれる
- [ ] `.gitignore` に `docs/_pdf_derived/` が含まれる
- [ ] `git status` で `docs/_pdf_derived/` 配下が untracked 扱いになる
      (`.gitignore` で除外されていることの確認)
- [ ] `.steering/_setup-progress.md` の Phase 8 セクションに T03 完了を追記
- [ ] feature/pdf-extract-baseline を push → PR → main merge

## 関連ドキュメント

- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §8 (PDF 資料の扱い方)
- `.steering/20260418-implementation-plan/decisions.md` §判断 3

## 運用メモ

- 破壊と構築 (`/reimagine`) 適用: **No**
- 理由: 1 コマンドで完結する単純作業、設計判断は既に済 (判断 3)
- タスク種類: その他 (ドキュメント派生物生成)

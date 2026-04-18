# タスクリスト — T04 pyproject-scaffold

## 準備
- [x] MASTER-PLAN.md §4.2 / §7.4 を再読
- [x] docs/repository-structure.md §1 §4 §5 を読む
- [x] docs/development-guidelines.md §1 §5 を読む
- [x] Skill `python-standards` / `architecture-rules` の SKILL.md を読む
- [x] Skill `git-workflow` の方針を確認

## 設計 (/reimagine 適用)
- [x] v1 案を design.md に書く
- [x] design-v1.md に退避
- [x] v2 案をゼロから再生成 (requirement.md のみに立脚)
- [x] design-comparison.md で 2 案を比較
- [x] 採用案を確定 (v2 + ハイブリッド調整 3 点)
- [x] 採用判断を design.md 末尾に追記

## 実装
- [x] `feature/pyproject-scaffold` ブランチ作成
- [x] `pyproject.toml` (uv_build + PEP 735 + ruff ALL + hybrid strict mypy)
- [x] `.python-version` (`3.11`)
- [x] `src/erre_sandbox/__init__.py` (`__version__ = "0.0.1"`)
- [x] `src/erre_sandbox/schemas.py` (docstring-only)
- [x] `src/erre_sandbox/{inference,memory,cognition,world,ui,erre}/__init__.py` (1 行 docstring)
- [x] `tests/__init__.py` / `tests/conftest.py` / `tests/test_smoke.py`
- [x] `LICENSE` / `LICENSE-MIT` / `NOTICE` 正式テキスト配置
- [x] `README.md` 最小版 (EN/JA)
- [x] `.gitignore` に Python/uv キャッシュ追加 (既存の docs/_pdf_derived/ 保持)

## テスト / 動作検証
- [x] `uv sync` 成功、`uv.lock` 生成
- [x] `uv run ruff check` 緑
- [x] `uv run ruff format --check` 緑
- [x] `uv run mypy src` 緑 (src strict で 8 ファイル通過)
- [x] `uv run pytest` 緑 (smoke 2 件 pass)

## レビュー
- [ ] code-reviewer によるレビュー (任意、/finish-task で実施)
- [ ] HIGH 指摘への対応

## ドキュメント
- [x] `.steering/20260418-pyproject-scaffold/` に requirement.md / design.md / design-v1.md / design-comparison.md / decisions.md / tasklist.md を記録
- [ ] `.steering/_setup-progress.md` の T04 行を `[x]` に更新

## 完了処理
- [x] design.md の最終化 (採用履歴を追記済み)
- [x] decisions.md の作成 (8 件の設計判断を記録)
- [ ] git commit (feature/pyproject-scaffold ブランチ)
- [ ] PR 作成 (main に向けて)

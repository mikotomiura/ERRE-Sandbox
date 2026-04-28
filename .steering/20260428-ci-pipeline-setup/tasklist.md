# タスクリスト — ci-pipeline-setup (v2 採用)

## 準備
- [x] 関連 docs を読む (CLAUDE.md / architecture.md / development-guidelines.md / repository-structure.md)
- [x] file-finder で既存 CI / lint / test / Godot skip パターンを調査
- [x] /reimagine で v1/v2 比較、v2 採用確定

## 実装

### A. pyproject.toml に godot marker 登録
- [ ] `[tool.pytest.ini_options]` に `markers = ["godot: requires Godot binary; deselect on CI via -m \"not godot\""]` を追加

### B. テストファイルに `@pytest.mark.godot` 付与
- [ ] `tests/test_godot_project.py` の `test_godot_project_boots_headless` に decorator
- [ ] `tests/test_godot_ws_client.py` の `resolve_godot()` を呼ぶ全関数に decorator
- [ ] `tests/test_godot_project.py` の binary 不要 2 関数 (`test_required_project_files_exist` / `test_godot_project_contains_no_python`) には decorator を**付けない**ことを確認
- [ ] ローカルで `uv run pytest tests/test_godot_project.py tests/test_godot_ws_client.py` を実行、pass を確認 (binary あり/なしどちらでも OK)
- [ ] ローカルで `uv run pytest -m "not godot" tests/test_godot_project.py` を実行、binary 必須の test だけが deselect されることを確認

### C. .pre-commit-config.yaml 新規作成
- [ ] repo: local + 2 hook (ruff-check / ruff-format) を `entry: uv run ruff ...` で記述
- [ ] `types: [python]` + `require_serial: true` 設定
- [ ] ローカルで `uv tool install pre-commit` (未インストールなら) → `pre-commit install`
- [ ] `pre-commit run --all-files` を実行、全 hook pass を確認
- [ ] 受け入れ条件 1 (`pre-commit run --all-files` 全 pass) 達成確認

### D. .github/workflows/ci.yml 新規作成
- [ ] 3 並列 jobs (`lint` / `typecheck` / `test`) を YAML で記述
- [ ] 共通 setup: `actions/checkout@v4` → `astral-sh/setup-uv@v5` (cache 有効) → `uv sync --frozen --all-groups`
- [ ] `lint` job: `uv run ruff check src tests` && `uv run ruff format --check src tests`
- [ ] `typecheck` job: `uv run mypy src`
- [ ] `test` job: `uv run pytest -m "not godot"`
- [ ] permissions: `contents: read`
- [ ] concurrency: `group: ci-${{ github.ref }}` / `cancel-in-progress: true`
- [ ] timeout-minutes: 各 job 10 分
- [ ] trigger: push (任意 branch) + pull_request
- [ ] YAML 構文チェック (`python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` または GitHub UI でのプッシュ前確認)

### E. README.md 更新
- [ ] L56-62 (English) verification command 直後に注記追記: "These run automatically via pre-commit (commit time) and GitHub Actions CI (push/PR). They can also be invoked manually via `uv run` as shown."
- [ ] L124-130 (日本語) に同等注記
- [ ] Getting Started セクション末尾に `uv tool install pre-commit && pre-commit install` を 1 行追記

### F. docs/development-guidelines.md 更新
- [ ] L25-26 を CI 化後表記に書換え
- [ ] L90-93 のテスト表「現状実装スナップショット」ブロックを更新 (実行頻度を "pre-commit" / "CI (push/PR)" に戻す、snapshot date を 2026-04-28)
- [ ] L107 「現状 manual」注記を「pre-commit / CI で自動実行」に書換え

### G. docs/architecture.md 更新
- [ ] L86 の CI 行を `(現状なし) [planned]` から実装済み entry に書換え
  例: `| CI | GitHub Actions + pre-commit | 最新 | uv sync --frozen → ruff/format/mypy/pytest を並列 3 jobs。詳細は .github/workflows/ci.yml |`
- [ ] §1 現状実装スナップショットの date 行 (`last verified 2026-04-28`) は変更不要 (本日と一致)

## テスト・検証
- [ ] `uv run ruff check src tests` 全 pass
- [ ] `uv run ruff format --check src tests` 全 pass
- [ ] `uv run mypy src` 全 pass
- [ ] `uv run pytest -m "not godot"` 全 pass
- [ ] `pre-commit run --all-files` 全 pass
- [ ] 受け入れ条件 6 項目 (requirement.md L48-54) チェック

## レビュー
- [ ] code-reviewer サブエージェントによるレビュー
- [ ] HIGH 指摘への対応 (あれば)
- [ ] MEDIUM 指摘の判断とユーザー確認

## ドキュメント・記録
- [ ] decisions.md に v2 採用根拠 + 受け入れ条件機械検証結果を記録
- [ ] design.md の最終化 (実装で乖離があれば更新)

## 完了処理
- [ ] git add (限定ファイル: .pre-commit-config.yaml / .github/workflows/ci.yml / pyproject.toml / tests/test_godot_*.py / README.md / docs/development-guidelines.md / docs/architecture.md / .steering/20260428-ci-pipeline-setup/)
- [ ] **co-existing changes (.agents/, .codex/, codex-environment-setup task) は別 commit に分離**
- [ ] `feat(ci): add pre-commit + GitHub Actions parallel CI` 形式の Conventional Commits でコミット (Refs: 付き)
- [ ] PR 作成 → 実 CI run で受け入れ条件達成を確認
- [ ] /finish-task で closure

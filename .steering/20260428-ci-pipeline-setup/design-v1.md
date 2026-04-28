# 設計 (v1 — 初回案)

## 実装アプローチ

「標準的なパターンに乗る」方針。pre-commit は astral-sh/ruff-pre-commit を hosted で
使い、GitHub Actions は single-job sequential で `uv sync --frozen` →
`ruff check` → `ruff format --check` → `mypy` → `pytest` を直列実行する。
Godot テストは既存の `pytest.skip(...)` 経路に任せ、新たな仕組みを足さない。

採用根拠: pre-commit / GitHub Actions の慣習に最も近く、外部レビュアー (codex 等)
にとって読み下しコストが低い。最低限の YAML 行数で動かせる。

## 変更対象

### 新規作成するファイル

- `.pre-commit-config.yaml` — pre-commit hooks (ruff check + ruff format)
  - repo: `https://github.com/astral-sh/ruff-pre-commit`
  - rev: 直近 stable (例: `v0.6.x` 系)
  - hooks: `ruff` (check), `ruff-format` (--check)
- `.github/workflows/ci.yml` — push / PR トリガーで verification 実行
  - runner: `ubuntu-latest`
  - steps: checkout → astral-sh/setup-uv@v5 (with cache) → `uv sync --frozen` →
    `uv run ruff check src tests` → `uv run ruff format --check src tests` →
    `uv run mypy src` → `uv run pytest`
  - permissions: `contents: read` のみ
  - concurrency: `group: ci-${{ github.ref }}` / `cancel-in-progress: true`

### 修正するファイル

- `README.md` L56-62 + L124-130 — verification コマンドにコメントで
  「pre-commit / CI で自動実行されるが manual でも `uv run` で実行可」を追記
- `docs/development-guidelines.md` L25-26, L90-93, L107 — "現状 manual" 注記を
  CI 化後の表記に復元
- `docs/architecture.md` L86 — `(現状なし)` / `[planned]` を実装済み表記に更新

### 削除するファイル

- なし

## 影響範囲

- すべての commit / PR で hook が走るようになる。初回 install 時に
  `uv tool install pre-commit && pre-commit install` を README に追記
- Godot テスト 2 件 (`test_godot_project_boots_headless`, `test_godot_ws_client`) は
  CI 上で skip される (binary 不在)。`test_required_project_files_exist` /
  `test_godot_project_contains_no_python` の 2 件は CI でも走る
- pytest 実行時間: ローカル ~30s 想定、CI 上は uv sync 込みで 3-4 分予想

## 既存パターンとの整合性

- README L56-62 の verification 5 コマンドをそのまま CI step に写す。乖離させない
- `pyproject.toml` L51-67 の `[dependency-groups]` を `uv sync --frozen` で
  解決。lint / typecheck / test の dev グループに既に分離されているため
  `--all-extras --dev` 相当で全部入る (uv のデフォルト挙動)
- mypy は requirement.md スコープ通り CI のみ (pre-commit には登録しない、slow)

## テスト戦略

- 単体テスト: 新設しない (CI 設定ファイル自体は実行で検証)
- 統合テスト: 新設しない
- E2E: PR を開いて CI が緑になることをもって受け入れ
- 受け入れ条件 (requirement.md L48-54) 全 6 項目を完了処理で確認

## ロールバック計画

- pre-commit が壊れた場合: `.pre-commit-config.yaml` を一時的に削除して revert
- CI が壊れた場合: ワークフローファイルを削除、または `if: false` で全 job を
  止めて main を保護
- 両方ともファイル単位で隔離されているため、`git revert <commit>` で 1 コマンド
  ロールバック可能

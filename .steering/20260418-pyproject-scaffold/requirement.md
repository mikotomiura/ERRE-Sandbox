# T04 pyproject-scaffold

## 背景

ERRE-Sandbox の Python 実装をスタートするための骨格を用意する段階。
T02 で uv + Python 3.11 の導入は完了し、T03 で PDF ベースラインを確保した。
次に進む T05 `schemas-freeze` は Contract Freeze の核であり、そこから先の
全タスク (T06-T20) が src/erre_sandbox のレイアウトと pyproject.toml の
ツール設定 (ruff / mypy / pytest) に依存する。

この骨格が曖昧なまま T05 に入ると、Contract Freeze 期間中にインフラ改修が
発生して契約が再凍結不能になる。したがって T04 で「src レイアウト・依存群・
ツール設定・CI 前提」をここで固める。

**参照**: `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.2 T04 行 /
§7.4 pyproject.toml 候補依存 / docs/repository-structure.md §1 / §4 /
docs/development-guidelines.md §1 §5.

## ゴール

- `uv sync` が成功してローカル仮想環境が作成され、`uv run python -c "import erre_sandbox"` が通る。
- `uv run ruff check` / `uv run ruff format --check` / `uv run mypy src` / `uv run pytest` がすべて緑。
- レイヤー骨格 (`schemas.py` / `inference/` / `memory/` / `cognition/` / `world/` / `ui/` / `erre/`) が
  `docs/repository-structure.md` §1 の通りに配置されている。
- 後続 T05 が「`schemas.py` に書けばそのまま pytest がフィクスチャ経由で検証できる」状態になる。

## スコープ

### 含むもの
- `pyproject.toml` 新規作成 (project metadata / 依存 / ruff / mypy / pytest 設定)
- `uv.lock` の初回生成
- `.python-version` 作成 (`3.11`)
- `src/erre_sandbox/` の最小レイヤー骨格 (`__init__.py` のみ、中身は TODO 許容)
- `schemas.py` のプレースホルダ (空 BaseModel を 1 個定義、T05 で本実装)
- `tests/` の conftest.py と smoke テスト 1 件
- `.gitignore` の Python / uv 向け更新
- LICENSE / LICENSE-MIT / NOTICE のプレースホルダ (中身は M2 末に本格化)

### 含まないもの
- `schemas.py` の本実装 (これは T05 の責務)
- ペルソナ YAML (T06)
- `inference/` / `memory/` / `cognition/` の実装コード (T10-T12)
- Godot プロジェクト (T15)
- `.github/workflows/ci.yml` の新規作成 (T04 では pyproject の土台のみ、CI は別タスクで扱う)
- pre-commit hook の整備 (別タスク)
- mkdocs 等ドキュメント自動生成パイプライン (M2 範囲外)

## 受け入れ条件

- [ ] `pyproject.toml` の `[project]` が Apache-2.0 OR MIT を宣言し、python 3.11 を require する
- [ ] `dependencies` に MASTER-PLAN §7.4 の 9 ライブラリ (pydantic / fastapi / uvicorn[standard] / websockets / httpx / sqlite-vec / pyyaml / numpy) が入っている
  - streamlit は optional-dependencies の "ui" グループへ (M2 後半の T18 optional のため必須化しない)
- [ ] dev 依存 (pytest / pytest-asyncio / ruff / mypy) が `[dependency-groups]` もしくは `[tool.uv]` の dev-dependencies として定義される
- [ ] `[tool.ruff]` が line-length・target-version・有効ルールを定義
- [ ] `[tool.mypy]` が python_version 3.11 / strict-ish 設定を定義 (schemas.py でノイズが出すぎない程度)
- [ ] `[tool.pytest.ini_options]` が pytest-asyncio を `asyncio_mode = "auto"` で有効化、`testpaths = ["tests"]`
- [ ] `uv sync` 実行で `uv.lock` が生成され、`.venv/` ができる
- [ ] `uv run ruff check` / `uv run ruff format --check` / `uv run mypy src` / `uv run pytest` の 4 コマンドすべて緑
- [ ] `.gitignore` に `.venv/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `*.egg-info/` が含まれる (既存の `docs/_pdf_derived/` を壊さない)
- [ ] `src/erre_sandbox/` 配下の `__init__.py` が各レイヤーに存在し、`architecture-rules` Skill の依存方向表 (schemas.py が最下層) に違反するインポートがゼロ
- [ ] `.steering/20260418-pyproject-scaffold/decisions.md` に 3 件以上の設計判断 (uv ビルドバックエンド / uv.lock のコミット是非 / ruff line-length / mypy 厳密度レベル) が記録される

## 関連ドキュメント

- `docs/repository-structure.md` §1 ディレクトリ構成 / §4 インポート規則 / §5 新規ファイル追加時のルール
- `docs/development-guidelines.md` §1 コーディング規約 / §5 パッケージ管理
- `docs/architecture.md` (Python 側アーキテクチャとレイヤー責務)
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.2 / §7.4
- Skill: `.claude/skills/python-standards/SKILL.md` / `.claude/skills/architecture-rules/SKILL.md` / `.claude/skills/git-workflow/SKILL.md`

## 運用メモ
- 破壊と構築（/reimagine）適用: **Yes**
- 理由: MASTER-PLAN §7.4 は「候補依存」を列挙しているだけで、
  (a) ビルドバックエンド (hatchling / uv_build / setuptools)、
  (b) uv.lock を Git に含めるか、
  (c) ruff ルールセット (E / F の最小 vs all + ignore)、
  (d) mypy の strict 度、
  (e) `[dependency-groups]` (PEP 735) vs `[tool.uv.dev-dependencies]` の選択、
  (f) optional-dependencies と dev の分け方、
  (g) src レイアウトの hatch ビルド設定、
  これらに複数案が存在し、後続 T05-T20 の DX・CI 挙動・配布戦略に波及する。
  MASTER-PLAN の文言をそのまま踏襲すると確証バイアスが入るため、
  初回案を書いた後に意図的にゼロから再生成して比較する。

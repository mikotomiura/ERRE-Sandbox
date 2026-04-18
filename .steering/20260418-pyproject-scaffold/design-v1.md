# 設計 (v1 初回案)

## 実装アプローチ

MASTER-PLAN §7.4 の候補依存をそのまま採用し、**広く使われている保守的な構成**で
土台を作る。hatchling + `[tool.uv]` の従来型レイアウト。ruff / mypy は
「T05 で schemas.py を書く時に摩擦を生まない」最小構成から始める。

方針の核:
- **ビルドバックエンド**: `hatchling`。mkdocstrings / editable install / wheel 作成の
  長期的な相性が一番実績がある。PyPI 配布を見据えた M10 以降でも使い回せる。
- **dev 依存**: `[tool.uv]` の `dev-dependencies` を使う (PEP 735 `[dependency-groups]`
  は比較的新しく、ツールサポートがまだばらつくため)。
- **optional-dependencies**: streamlit のみ `ui` extras に分離。UI ダッシュボードは
  T18 optional、Godot ルートが正道のため必須化しない。
- **uv.lock**: Git にコミット。本プロジェクトはアプリケーション/研究プラットフォームで、
  再現性が第一優先 (docs/development-guidelines §5)。
- **ruff**: line-length=100, select は E/F/I/W/B/UP/SIM、target-version=py311。
  `per-file-ignores` で `tests/` と `__init__.py` に緩和を入れる。
- **mypy**: `python_version=3.11`, `disallow_untyped_defs=true`, `warn_unused_ignores=true`、
  Pydantic v2 は `plugins=["pydantic.mypy"]`。strict は有効にしないが disallow_untyped_defs で
  型ヒント必須ルールを強制する。
- **pytest**: `asyncio_mode=auto`, `testpaths=["tests"]`, `pythonpath=["src"]`。

## 変更対象

### 修正するファイル
- `.gitignore` — Python/uv/ruff/mypy/pytest のキャッシュ、`.venv/` を追加 (既存の `docs/_pdf_derived/` は残す)

### 新規作成するファイル
- `pyproject.toml` — メタデータ + 依存 + [tool.ruff]/[tool.mypy]/[tool.pytest.ini_options]/[tool.hatch.build]
- `.python-version` — `3.11` のみ 1 行
- `src/erre_sandbox/__init__.py` — パッケージバージョン (`__version__ = "0.0.1"`)
- `src/erre_sandbox/schemas.py` — プレースホルダ (T05 で拡張)、`class _Placeholder(BaseModel)` 1 個
- `src/erre_sandbox/inference/__init__.py` — 空
- `src/erre_sandbox/memory/__init__.py` — 空
- `src/erre_sandbox/cognition/__init__.py` — 空
- `src/erre_sandbox/world/__init__.py` — 空
- `src/erre_sandbox/ui/__init__.py` — 空
- `src/erre_sandbox/erre/__init__.py` — 空
- `tests/__init__.py` — 空
- `tests/conftest.py` — プレースホルダ (将来の `agent_state_factory` を空コメントで示唆)
- `tests/test_smoke.py` — `from erre_sandbox import __version__` / `assert __version__` の 1 テスト
- `LICENSE` — Apache-2.0 プレースホルダ (M2 末に確定)
- `LICENSE-MIT` — MIT プレースホルダ
- `NOTICE` — Apache-2.0 帰属表示プレースホルダ

### 削除するファイル
- なし (既存資産は壊さない)

## 影響範囲

- 影響範囲は本リポジトリ内のみ。.claude/ / docs/ / .steering/ には直接変更なし。
- T05 (schemas-freeze) はこの骨格の上で `schemas.py` を膨らませる形で進む。
- G-GEAR 側は T09 モデル pull 待ちのためこの段階では動かない。
- CI は別タスクで追加するが、ここで pyproject.toml の tool 設定を確定させておくことで
  CI 導入時に `uv sync --frozen && uv run ruff check && uv run mypy src && uv run pytest` だけで成り立つ。

## 既存パターンとの整合性

- `docs/repository-structure.md` §1 のディレクトリ構成を 1:1 で実体化する。
- `docs/development-guidelines.md` §5 の「uv を単一ツールとして使う / lock で再現性」を踏襲。
- Skill `python-standards` の 7 ルール (型ヒント必須 / asyncio / Pydantic v2 / 命名 / f-string / インポート順 / コメント) を ruff 設定で機械的に強制できる範囲で反映。
- Skill `architecture-rules` の依存方向表を守るために、`schemas.py` は他の src モジュールを import しない骨格で出発する。

## テスト戦略

- 単体テスト: この段階では書かない (T08 `test-schemas` で本格化)。
- smoke テスト (`tests/test_smoke.py`): `import erre_sandbox` が成功し、`__version__` が空でないことの 1 件のみ。pytest と pytest-asyncio が正しく動くことの最低確認。
- 統合テスト: なし (T05-T08 の責務)。
- E2E: 不要。

## ロールバック計画

- pyproject.toml / src / tests / .gitignore / LICENSE 群はすべて新規ファイルまたは既存ファイルへの追記のみ。問題発生時は `git checkout -- .` + `rm -r src tests .venv uv.lock pyproject.toml .python-version LICENSE*` で原状復帰可能。
- `feature/pyproject-scaffold` ブランチで作業し、main への merge は PR 経由。PR を close すれば main 影響なし。

## 未決定事項 (v1 の弱点)

以下は「とりあえず保守的に選んだ」が、別案も十分検討可能:

1. ビルドバックエンドに hatchling を選んだが、uv 公式の `uv_build` (uv 0.5+) を選ぶと uv 単一ツールで完結するメリットがある。
2. dev 依存を `[tool.uv]` に寄せたが、PEP 735 `[dependency-groups]` の方が将来性は高い。
3. ruff ルールセット E/F/I/W/B/UP/SIM は「無難」だが、`ALL` + ignore リストで明示的にガバナンスする方が強い。
4. mypy を `disallow_untyped_defs` 止まりにしたが、最初から `strict=true` にして schemas.py を厳密に書かせる方が Contract Freeze に資する。
5. line-length=100 は日本語コメント対応で選んだが、ruff デフォルトの 88 の方が他の OSS との互換性が高い。

これらを v2 でゼロから再考する。

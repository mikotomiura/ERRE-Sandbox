# 設計 (v2 再生成案)

## 実装アプローチ — 「今後 T05-T20 で自分を守る pyproject にする」

要件 (requirement.md) を一度読み直すと、本タスクの本質は
「T05 Contract Freeze 前に、後戻り不能な構造・ツール選定をひとつの
ファイル (pyproject.toml) に凝縮させる」ことにある。pyproject の選択は
今後 16 タスクの開発者体験を決定づける。よって方針は

> **「デフォルトを疑う、標準を先取る、Contract を機械が守る」**

の 3 点。具体化すると:

### A. 単一ツール戦略: uv 公式ビルドバックエンドで貫く

本プロジェクトは `uv` を「Python / 仮想環境 / 依存 / スクリプト / lock」
の 5 役を集約する単一ツールとして採用した (docs/development-guidelines §5)。
そのため **ビルドバックエンドも `uv_build`** を選ぶ。uv 0.5 で GA、
PyPI 配布と editable install の両方を `uv build` / `uv sync` だけで完結できる。
hatchling は実績豊富だが「build バックエンドは hatchling、依存解決は uv」
という二系統ツールチェーンを生み、MacBook / G-GEAR 両機の同期時に差異の
根源となりうる。配布が現実化するのは M10 以降。その時点で必要なら差し替え可能
（`pyproject.toml` の数行の置換で済む）。**今は uv 単一ツール戦略を守る**。

### B. PEP 735 `[dependency-groups]` を採用する

`[tool.uv.dev-dependencies]` は uv 固有、`[dependency-groups]` は 2024 年採択の
PEP 735 標準。pip 25 / poetry 2 / pdm 2.18+ / uv 0.4+ が対応済み。
標準側に倒しておくと「uv から別ツールへ移植」もコストゼロに近づく。
さらに `dev` 単一ではなく **`lint` / `typecheck` / `test` / `docs`** に
細分割する。CI 時に必要なグループだけ sync することで
`ruff check` ジョブが pytest まで待たされない設計が可能になる (CI は別タスクだが、
そこで使える形をこの pyproject で確定させる)。

### C. ruff は `["ALL"]` + 明示的 ignore でガバナンスを明示

「どのルールを無効化するか」を明文化する方が、プロジェクトのコーディング文化を
コードで語れる。新しいルールが追加されたら自動的に noisy になるが、それこそが
「レビュー機会」。T05 以降でコードが 100 ファイル規模に膨らむ前の今こそ ALL を
採用するベストタイミング。

ignore する主なルール (根拠つき):
- `D*` (pydocstyle): docstring は公開 API のみ required、全関数には求めない (python-standards §7)
- `ANN*`: mypy と責務重複
- `COM812` / `ISC001`: ruff format と衝突
- `RUF001` / `RUF002` / `RUF003`: 日本語全角文字を許容するため必須
- `S101` (assert): pytest で assert を使う
- `EM*` / `TRY003` / `TRY300`: 例外文字列の形式規定は噛み合わない
- `PLR0913` (too-many-arguments): Pydantic BaseModel 初期化は多引数が自然
- `INP001` (implicit namespace package): src 配下で誤検知しやすい

per-file-ignores:
- `tests/**`: `S101`, `PLR2004` (magic number), `D`
- `**/__init__.py`: `F401` (re-export)、`D104`

### D. mypy はハイブリッド strict — src は厳密、tests は寛容

Contract Freeze を守るため `src/` は `strict = true`。ただし `tests/` は
`strict = false` + `disallow_untyped_defs = false` のセクションオーバーライド。
Pydantic v2 は `plugins = ["pydantic.mypy"]` で mypy が BaseModel を正しく読めるようにする。
`exclude = ["^.venv/"]` を明記 (念のため)。

### E. ruff / diff の line-length は 88 — 日本語は短文 + 改行で対処

line-length 100 はチーム規約で妥協が必要な時の選択だが、本プロジェクトは
個人開発で python-standards Skill が「コメントは最小限」を強制する。
88 が GitHub diff / black / ruff のデフォルトで OSS 互換性が高い。
日本語コメントが長くなる場合は文を短く切る方針で運用。

### F. uv.lock はコミット。.python-version は major.minor の `3.11` のみ

再現性 (MacBook ↔ G-GEAR 両機同期) 最優先のためロックはコミット。
`.python-version` は `3.11` のみ記述し、3.11 系の最新 patch に追従 (uv が解決)。
patch 固定すると MacBook の brew と G-GEAR の WSL で patch バージョンがずれた時に
摩擦になる。

### G. `schemas.py` は「docstring のみの空ファイル」で始める

v1 にあったような `_Placeholder(BaseModel)` は T05 着手時に削除コストが発生し、
mypy / ruff の「未使用」ノイズの素。**docstring (モジュール責務) のみ** にすると
- mypy も ruff も文句を言わない
- T05 で追記するだけで済む
- smoke テスト側で `from erre_sandbox import schemas` だけを実行し、
  「モジュールロードできる」ことを確認

### H. レイヤー骨格は `__init__.py` + 1 行 docstring

各レイヤーの責務 (docs/repository-structure.md §2) を 1 行 docstring で
`__init__.py` に書く。中身の class/func は置かない。IDE の hover でレイヤー
責務が即表示される。

### I. smoke テストは「7 レイヤーすべて import 成功」を網羅

v1 の `__version__` チェックより重要な検証として、

```python
def test_all_layers_importable() -> None:
    import erre_sandbox
    from erre_sandbox import schemas
    from erre_sandbox import inference, memory, cognition, world, ui, erre
    assert all(m is not None for m in (schemas, inference, memory, cognition, world, ui, erre))
```

これで「__init__.py のいずれかが文法エラーだとテストが落ちる」セーフティネットが作れる。
CI 化された時の最初の赤信号になる。

### J. LICENSE 類は「M2 末で確定」ではなく **今** 正式テキストで配置

- `LICENSE`: Apache-2.0 全文 (SPDX: Apache-2.0)
- `LICENSE-MIT`: MIT 全文 (SPDX: MIT)
- `NOTICE`: Apache-2.0 節 4(d) 要件 (Copyright notice + 派生物注記)

GitHub の license 検知 (linguist) に正確に引っかけるためにも先に正式テキスト
を置く。プレースホルダは先送りコストが高い。

### K. dev グループと optional-dependencies の切り分け

- **`[dependency-groups]` (ランタイムに不要、開発時のみ)**
  - `lint`: ruff
  - `typecheck`: mypy
  - `test`: pytest, pytest-asyncio
- **`[project.optional-dependencies]` (ランタイムに任意、配布される)**
  - `ui`: streamlit (T18 optional)

分け方の基準は「本番デプロイ時に必要か」。ruff/mypy/pytest は不要、
streamlit はダッシュボードを使う人だけ必要 → optional で提供。

---

## 変更対象

### 修正するファイル
- `.gitignore` — 既存末尾に追記 (`.venv/`, `__pycache__/`, `*.egg-info/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `*.pyc`, `build/`, `dist/`)。既存の `docs/_pdf_derived/` などは保持。

### 新規作成するファイル
**プロジェクト設定 (ルート)**
- `pyproject.toml` — build-system `uv_build` / project metadata / dependencies / [dependency-groups] lint,typecheck,test / [project.optional-dependencies] ui / [tool.ruff]/[tool.mypy]/[tool.pytest.ini_options]
- `.python-version` — `3.11\n`

**Python ソース骨格**
- `src/erre_sandbox/__init__.py` — 1 行 docstring + `__version__ = "0.0.1"`
- `src/erre_sandbox/schemas.py` — 1 段落 docstring のみ (T05 で本実装)
- `src/erre_sandbox/inference/__init__.py` — 1 行 docstring
- `src/erre_sandbox/memory/__init__.py` — 1 行 docstring
- `src/erre_sandbox/cognition/__init__.py` — 1 行 docstring
- `src/erre_sandbox/world/__init__.py` — 1 行 docstring
- `src/erre_sandbox/ui/__init__.py` — 1 行 docstring
- `src/erre_sandbox/erre/__init__.py` — 1 行 docstring

**テスト骨格**
- `tests/__init__.py` — 空
- `tests/conftest.py` — 空 (プレースホルダコメント 1 行のみ。将来 T08 でフィクスチャ追加)
- `tests/test_smoke.py` — `test_version_defined()` / `test_all_layers_importable()` の 2 件

**ライセンス・通知**
- `LICENSE` — Apache-2.0 全文
- `LICENSE-MIT` — MIT 全文
- `NOTICE` — Copyright (c) 2026 mikotomiura / Apache-2.0 節 4(d) の帰属表示

### 削除するファイル
- なし

---

## 影響範囲

- **T05 schemas-freeze への接続**: `src/erre_sandbox/schemas.py` が docstring-only
  で存在し、strict mypy 前提なので、T05 で BaseModel を追加した瞬間から型検査が
  機能する。Contract Freeze に入る前に「型検査の土台」が稼働していることが重要。
- **T08 test-schemas への接続**: pytest + pytest-asyncio mode=auto + testpaths=["tests"]
  が pyproject で確定しており、T08 は `tests/test_schemas.py` を追加するだけで
  CI に載る。
- **T15 godot-project-init / T17 godot-peripatos-scene**: `godot_project/` は
  Python 側とは物理分離。pyproject.toml が hatch ではなく uv_build を使うため、
  Godot 側から見た時に余計な build artifact が出ない。
- **CI 導入タスク (別タスク)**: `uv sync --frozen --group lint` / `--group typecheck` /
  `--group test` でジョブ並列化できる下地がここで決まる。

---

## 既存パターンとの整合性

- docs/repository-structure.md §1 ディレクトリ構成に 1:1 で対応。
- docs/development-guidelines.md §5 (uv 単一ツール / lock 再現性) に厳密に従う。
- Skill `python-standards` の全 7 ルールを ruff ALL (minus ignore) で機械強制可能な範囲で網羅。
- Skill `architecture-rules` のレイヤー図に沿って `__init__.py` を配置、schemas.py は他 src モジュールを import しない骨格。
- Skill `git-workflow` の Conventional Commits に従い、この作業は `feature/pyproject-scaffold` ブランチで行う。

---

## テスト戦略

- **Smoke (tests/test_smoke.py, 2 件)**:
  1. `test_version_defined`: `erre_sandbox.__version__` が非空文字列
  2. `test_all_layers_importable`: 7 レイヤー全モジュールを import して None でないことを確認
- **単体/統合/E2E**: 本タスクでは書かない (T08/T10/T19 の責務)。
- **ツールチェーン動作検証 (受入基準)**: `uv sync` / `uv run ruff check` / `uv run ruff format --check` / `uv run mypy src` / `uv run pytest` の 5 コマンドが緑。

---

## ロールバック計画

- 変更は全て **新規追加** か、既存 `.gitignore` への末尾追記のみ。破壊的変更なし。
- ブランチ `feature/pyproject-scaffold` で作業、PR を close すれば main 影響ゼロ。
- ローカルの `.venv/` / `uv.lock` が不要になれば削除して再 sync すればよい (uv はキャッシュから高速復元)。

---

## v2 が v1 より優れている点 (自己評価)

1. **一貫性**: 単一ツール戦略を build backend まで貫いた (uv_build)。
2. **標準先取り**: PEP 735 `[dependency-groups]` で将来のツール横断性を確保。
3. **ガバナンスの明示化**: ruff ALL + 明示的 ignore で「このプロジェクトが何を許し何を拒むか」がコードで読める。
4. **Contract Freeze への本質的貢献**: src strict mypy + schemas.py docstring-only で、T05 の最初のキータイプから型検査が効く。
5. **CI 並列化の下地**: dependency-groups を lint / typecheck / test に分割。
6. **LICENSE を先送りしない**: M2 末に回さず正式テキストで配置。
7. **smoke テストに意味を持たせた**: 7 レイヤー import 検証で __init__ シンタックスエラーを即検知。

## v2 の弱点 / リスク

- `uv_build` は 2024 年後半に GA、実績は hatchling より浅い。Mac arm64 / WSL2 で未知のエッジケースに遭遇する可能性。→ `uv build` が壊れたら `hatchling` に差し替える rollback を decisions.md に記録。
- ruff `ALL` は新しい ruff リリースで prone to break。→ `ruff` は dependency-groups で `>=0.6,<1.0` に固定し、定期的に手動アップデート。
- PEP 735 `[dependency-groups]` 非対応のサードパーティツール (古い CI イメージ等) は読めない。→ uv 自体が対応していれば CI は動く。

---

## 設計判断の履歴

- 初回案 (design-v1.md) と再生成案 (design.md = 本ファイル) を作成し、design-comparison.md で比較。
- **採用: v2 + ハイブリッド調整 3 点**
- 根拠: 本タスクの核心は Contract Freeze の土台作り。v2 の「uv 単一ツール戦略を build backend まで貫く / PEP 735 標準先取り / ruff ALL + src strict mypy による機械的ガバナンス / schemas.py docstring-only」が要件に直接応答している。
- v1 由来のリスク回避策 3 点を吸収:
  1. ruff ALL が noisy になったら select を縮小する権利を decisions.md に明記
  2. mypy は src strict を採用、ただし `warn_return_any = false` を T05 完了まで許容 (Pydantic v2 の戻り値型に摩擦がある時の逃げ道)
  3. uv_build で詰まったら hatchling にスイッチするロールバックパスを decisions.md に明記

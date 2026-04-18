# 重要な設計判断 — T04 pyproject-scaffold

## 判断 1: ビルドバックエンドは `uv_build` を採用 (hatchling ではなく)

- **判断日時**: 2026-04-18
- **背景**: uv 0.5 で uv 公式ビルドバックエンド `uv_build` が GA。本プロジェクトは既に uv を単一ツール戦略 (Python / 仮想環境 / 依存 / lock) として採用しており、build まで貫くか、実績の厚い hatchling に分岐するかの選択。
- **選択肢**:
  - A: **`uv_build`** — uv 単一ツールで完結、pyproject 行数が少ない、MacBook/G-GEAR の工具差異を最小化
  - B: `hatchling` — 実績豊富、mkdocstrings 等の OSS との親和性、エッジケース報告が蓄積済み
  - C: `setuptools` — 最古株だが pyproject-only プロジェクトでは過剰
- **採用**: **A (`uv_build`)**
- **理由**: 本プロジェクトが「uv 単一ツールで開発体験を統一する」と既に決めているため、build backend を別ツールにする一貫性の欠損コストの方が uv_build 実績浅のリスクより大きい。PyPI 配布の実需は M10 以降なので、その時点で再評価可能。
- **トレードオフ**: hatchling が持つ `hatch build --target custom` 等の柔軟性を諦める。
- **影響範囲**: pyproject.toml `[build-system]` / `[tool.uv.build-backend]`。ビルド成果物の生成形式。editable install の挙動。
- **見直しタイミング**:
  - (a) uv_build がエッジケースで詰まり 10 分以内に解消しない場合、即 hatchling に差し替える (設計で承認済みのロールバックパス)。
  - (b) M10 で PyPI 配布を開始する時に、hatchling の build plugin が欲しくなれば差し替え検討。

## 判断 2: dev 依存は PEP 735 `[dependency-groups]` に統一

- **判断日時**: 2026-04-18
- **背景**: uv には `[tool.uv.dev-dependencies]` という独自セクションがあるが、2024 年に採択された PEP 735 の `[dependency-groups]` が pip / poetry 2 / pdm / uv 0.4+ で標準化されつつある。
- **選択肢**:
  - A: **`[dependency-groups]`** (PEP 735、lint/typecheck/test に細分割)
  - B: `[tool.uv.dev-dependencies]` 単一グループ (uv 固有、実績厚)
  - C: `[project.optional-dependencies]` の `dev` extras を使う (ランタイム distribution に紛れ込む)
- **採用**: **A (`[dependency-groups]`)**、`lint`/`typecheck`/`test`/`dev` (集約) の 4 グループに分割
- **理由**: 標準側に倒すことでツール横断性を確保。CI 側で `uv sync --only-group lint` のように絞り込みでジョブ並列化が可能。
- **トレードオフ**: PEP 735 非対応の古い CI イメージでは動かない可能性 (uv 自体が対応していれば問題ないが、他ツールが読めない)。
- **影響範囲**: pyproject.toml `[dependency-groups]`。CI の将来設計。
- **見直しタイミング**: CI 導入タスクで `--only-group` の挙動が期待通りでなければ `dev` 単一に戻す選択肢あり。

## 判断 3: ruff は `select = ["ALL"]` + 明示的 ignore でガバナンスを明示

- **判断日時**: 2026-04-18
- **背景**: ruff のルールは数百種類あり、`E/F/I/W/B/UP/SIM` のような最小セットか、`ALL` から ignore で絞るかの選択がある。
- **選択肢**:
  - A: **`select = ["ALL"]` + 明示的 ignore** — 何を許し何を拒むかがコードで読める。新しい ruff ルールが自動で適用される。
  - B: `select = ["E","F","I","W","B","UP","SIM"]` 最小セット — 安定、noisy になりにくい
  - C: pre-commit の flake8 プラグイン列挙方式を模倣 — レガシー感
- **採用**: **A (`ALL` + ignore 約 20 ルール)**
- **理由**: Contract Freeze 前に「プロジェクトのコーディング文化」を機械可読に固定する好機。個人開発なので noisy さを吸収できる。T05 以降でコードが増える前に定着させる方が後戻りが効かない領域。
- **トレードオフ**: 新規 ruff リリース毎に新ルールで赤が出る運用コスト。→ `ruff>=0.6,<1.0` に version 固定して定期的に手動アップデート。
- **影響範囲**: `[tool.ruff.lint]` select/ignore。全ソース・テストの lint。
- **見直しタイミング**:
  - (a) T05 完了後にルール見直し。日本語コメントと相性の悪いルールが増えたら ignore 追加。
  - (b) noisy さで開発速度が大きく落ちたら最小セットに切り戻す権利あり (design.md 採用判断で承認済み)。

## 判断 4: mypy は src strict / tests 寛容のハイブリッド、ただし `warn_return_any = false`

- **判断日時**: 2026-04-18
- **背景**: Contract Freeze を守るため src は strict にしたい。しかし pytest 側は fixture の戻り値型等で strict すぎると摩擦が大きい。また Pydantic v2 は戻り値型の推論で Any を返すケースがあり `warn_return_any` が真だとノイズが多い。
- **選択肢**:
  - A: 全域 `strict = false` + `disallow_untyped_defs = true`
  - B: 全域 `strict = true` (tests 含む)
  - C: **src strict / tests 寛容 + `warn_return_any` を暫定 false**
- **採用**: **C**
- **理由**: Contract Freeze の趣旨 (schemas.py の型を機械で守る) に照らして src は strict が必要。tests は fixture 記述の柔軟性を優先。`warn_return_any = false` は Pydantic v2 との摩擦を避けるための一時的な逃げ道で、T05 schemas-freeze 完了時点で再評価して true に昇格する予定。
- **トレードオフ**: tests の型安全性が src より弱い。T05 までは Pydantic 関連で Any が漏れる可能性を許す。
- **影響範囲**: `[tool.mypy]` / `[[tool.mypy.overrides]]`。schemas.py を書く時の Developer Experience。
- **見直しタイミング**: **T05 schemas-freeze 完了時に必ず `warn_return_any = true` に昇格**。これを決意表明として decisions.md に記録する。

## 判断 5: ruff line-length は 88 (ruff/black デフォルト)

- **判断日時**: 2026-04-18
- **背景**: 日本語コメントは全角幅を食うので 100 にする選択もあるが、python-standards Skill の「コメント最小限」方針があるため必ずしも必要ない。
- **選択肢**:
  - A: **88** — ruff/black デフォルト、GitHub diff 2 分割、OSS 互換性
  - B: 100 — 日本語コメントで余裕
  - C: 120 — モダン IDE 前提
- **採用**: **A (88)**
- **理由**: OSS 流儀と GitHub diff レンダリングに揃える方が貢献者体験が良い。日本語コメントは短文 + 改行で対応。
- **トレードオフ**: 日本語 docstring が多いファイルで改行回数が増える (想定される頻度は低い)。
- **影響範囲**: `[tool.ruff]` line-length。全 Python ソース。
- **見直しタイミング**: 明らかに 88 が開発速度を下げる状況が現れたら 100 に緩和を検討。

## 判断 6: `uv.lock` を Git にコミット

- **判断日時**: 2026-04-18
- **背景**: アプリケーション or ライブラリかで lock のコミット方針が変わる。本プロジェクトは研究プラットフォーム + MacBook/G-GEAR 両機同期が必要。
- **選択肢**:
  - A: **コミットする** — 再現性、両機同期、CI で `--frozen` 強制
  - B: コミットしない — ライブラリ開発の流儀
- **採用**: **A**
- **理由**: docs/development-guidelines.md §5 で既に「CI では `uv sync --frozen` で再現可能なインストール」と決めている。両機で同じ依存 hash を保つために必須。
- **トレードオフ**: 依存更新の PR で uv.lock の差分が大きくなる。
- **影響範囲**: Git 履歴サイズ、CI 設定。
- **見直しタイミング**: M10 以降で PyPI ライブラリとしての配布を本格化する場合。その時も lock はコミットし続ける選択肢が有力。

## 判断 7: LICENSE/LICENSE-MIT/NOTICE は最初から正式テキストを配置 (プレースホルダにしない)

- **判断日時**: 2026-04-18
- **背景**: M2 末に本格化するとしてプレースホルダで始める案と、最初から正式テキストを置く案。
- **選択肢**:
  - A: プレースホルダ (M2 末に本格化)
  - B: **最初から正式テキスト (Apache-2.0 全文 + MIT 全文 + NOTICE)**
- **採用**: **B**
- **理由**: GitHub の license detection (linguist) / OSS クローン時の二度手間を回避。`pyproject.toml` の `license = "Apache-2.0 OR MIT"` と `license-files = [...]` に整合。
- **トレードオフ**: 今のタイミングで copyright holder の正確な名前を確定させる必要 (mikotomiura で確定)。
- **影響範囲**: ルート LICENSE 群、pyproject.toml の license 宣言。
- **見直しタイミング**: プロジェクト名義が変わった場合のみ更新 (現時点では mikotomiura で固定)。

## 判断 8: schemas.py は docstring-only で出発 (`_Placeholder(BaseModel)` を置かない)

- **判断日時**: 2026-04-18
- **背景**: T05 schemas-freeze で本実装するが、T04 時点で import 可能にしておく必要がある。プレースホルダクラスを置くと T05 着手時に削除コストと mypy/ruff 警告が発生する。
- **選択肢**:
  - A: プレースホルダ `_Placeholder(BaseModel)` を置く
  - B: **docstring のみ** (1 段落で T05 への引き継ぎ明記)
  - C: `pass` のみの空ファイル
- **採用**: **B**
- **理由**: mypy/ruff が警告を出さず、T05 での差分が「追加のみ」となる最小ノイズ構成。
- **トレードオフ**: 可読性のために 5-6 行の docstring だけ置くが、それだけ。
- **影響範囲**: `src/erre_sandbox/schemas.py` の初期状態。T05 の着手 Developer Experience。
- **見直しタイミング**: T05 着手時に削除 (docstring を本実装のものに置換)。

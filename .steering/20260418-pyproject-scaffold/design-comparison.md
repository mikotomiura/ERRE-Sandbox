# 設計案比較 — T04 pyproject-scaffold

## v1 (初回案) の要旨

MASTER-PLAN §7.4 を保守的に踏襲: hatchling ビルド + `[tool.uv.dev-dependencies]` +
ruff 限定ルールセット (E/F/I/W/B/UP/SIM, line-length=100) + mypy `disallow_untyped_defs` +
schemas.py プレースホルダ `_Placeholder(BaseModel)` + LICENSE はプレースホルダ。
smoke は `__version__` チェック 1 件のみ。

## v2 (再生成案) の要旨

単一ツール戦略を build backend まで貫く: `uv_build` + PEP 735 `[dependency-groups]`
を `lint/typecheck/test` に細分割 + ruff `ALL` + 明示的 ignore (line-length=88) +
mypy hybrid strict (src strict / tests 寛容) + schemas.py は docstring-only +
LICENSE は Apache-2.0/MIT 正式テキストを最初から配置 +
smoke は「7 レイヤー import 検証」を追加。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| ビルドバックエンド | hatchling | **uv_build** (uv 単一戦略を build まで貫く) |
| dev 依存の記述 | `[tool.uv.dev-dependencies]` | **PEP 735 `[dependency-groups]`**、`lint/typecheck/test` に細分割 |
| ruff ルールセット | `select = ["E","F","I","W","B","UP","SIM"]` | **`select = ["ALL"]` + 明示的 ignore リスト** |
| ruff line-length | 100 | **88** (ruff/black デフォルト、OSS 互換) |
| mypy | disallow_untyped_defs=true (中庸) | **src strict / tests 寛容のハイブリッド** |
| schemas.py | `_Placeholder(BaseModel)` を置く | **docstring のみ**、クラス無し |
| __init__.py | 空 | 1 行 docstring でレイヤー責務を書く |
| smoke test | `__version__` 1 件 | **version + 7 レイヤー import 検証の 2 件** |
| LICENSE | プレースホルダ (M2 末に本格化) | **正式テキストを今すぐ配置** |
| CI 並列化の下地 | 単一 dev グループ | lint / typecheck / test で分けて並列化可能 |
| uv.lock | コミット (同じ) | コミット (同じ) |
| .python-version | `3.11` (同じ) | `3.11` (同じ) |
| optional-dependencies | `ui=[streamlit]` (同じ) | `ui=[streamlit]` (同じ) |
| 変更規模 | 18 ファイル追加 | 18 ファイル追加 (同じ) |

## 評価

### v1 の長所
- 実績重視: hatchling は OSS での採用実績が豊富 (mkdocstrings, hypercorn, etc.)
- 段階的: mypy/ruff を緩く始めて、後で引き締める戦略は摩擦が少ない
- 予測可能性が高い: エッジケースで詰まる可能性が v2 より低い

### v1 の短所
- ツールチェーンが二系統 (hatchling + uv) になり、将来「なぜ hatchling?」の説明が必要
- dev 依存が uv ロックインな書き方
- ruff の限定ルールセットだと、T05 以降でコードが増えた時に新しい ruff ルールを追うコストが累積
- mypy disallow_untyped_defs 止まりだと、Pydantic BaseModel の戻り値型ミス等を防げる保証が弱い → Contract Freeze の趣旨に照らして弱い
- `_Placeholder(BaseModel)` は T05 着手時に削除前提のゴミ
- LICENSE プレースホルダは GitHub の license detection / OSS クローン時の二度手間

### v2 の長所
- **単一ツール戦略が貫徹される**: uv で build も sync も完結
- **標準先取り**: PEP 735 で将来のツール横断性
- **Contract を機械が守る**: src strict mypy + ruff ALL
- **CI を設計する時の自由度が高い**: group 分割で並列化の下地
- **ゴミを残さない**: schemas.py は docstring-only、LICENSE は正式配置
- **smoke に意味がある**: 7 レイヤー import で __init__ の文法エラーを即検知

### v2 の短所 / リスク
- `uv_build` は 2024 年後半 GA で実績が浅く、エッジケースで詰まる可能性
- ruff `ALL` は新しい ruff リリース毎に noisy になる運用コスト (個人開発で許容可)
- PEP 735 `[dependency-groups]` 非対応の古いツールは読めない (uv が読めれば CI は動く)
- src strict mypy は T05 で Pydantic v2 のトリッキーな型に噛み合わない場面でデバッグ工数が増える可能性

## 推奨案 — **v2 を採用** (ハイブリッド調整あり)

理由:
1. 本タスクの核心は **Contract Freeze の土台作り**。v2 の「src strict mypy + ruff ALL + schemas.py docstring-only」は Contract を機械で守る方向に振れており、要件に直接応答している。
2. プロジェクトが uv 単一ツール戦略を既に採用しているため、build backend まで uv_build で貫く方が一貫性が高い。
3. 個人開発 × 研究プラットフォームで、ガバナンスを明示化する運用コストを吸収できる規模。
4. v2 のリスク (uv_build 実績、ruff ALL の noisy) は decisions.md に明記してロールバックパスを確保する。

### v1 から取り込むハイブリッド調整 (3 点)

1. **ruff `ALL` は採用するが、noisy になったら select を縮小する権利を decisions.md に明記**: v1 の保守性の良さを安全弁として残す。
2. **mypy は src strict を採用するが、`warn_return_any = false` は最初の 2 週間だけ許容**: Pydantic v2 の戻り値型が強すぎる時の逃げ道。T05 完了後に false → true に昇格する TODO を decisions.md へ。
3. **uv_build で詰まったら 10 分以内に hatchling にスイッチ**: エッジケース検出時の即応パスを決めておく (decisions.md)。

これらは v2 本体の方向性を変えるものではなく、v2 の弱点を v1 の保守性で補う形。

## 採用判断の履歴
- 初回案 (design-v1.md) と再生成案 (design.md) を作成、本ファイルで比較
- **採用: v2 + ハイブリッド調整 3 点**
- 根拠: 本タスクの核心 "Contract Freeze の土台作り" に対して、v2 の機械的ガバナンスが要件により直接応答している。v1 のリスク回避策 3 点で v2 の弱点を補う。

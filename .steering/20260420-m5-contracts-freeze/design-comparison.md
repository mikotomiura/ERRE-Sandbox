# 設計案比較 — m5-contracts-freeze

## v1（初回案）の要旨

M4 `m4-contracts-freeze` の手順を機械的に踏襲。schemas.py → fixtures 手編集 →
golden 手動再生成 (README に書かれたインラインコマンド) → conftest 更新 →
後追いで最小 test 追加、の 6 ステップ直列。新 test は「既存 `test_schemas.py` に
追加、または M4 パターンに従い `test_schemas_m5.py` 新規作成」と曖昧に留めた。
fixture 10 ファイル全てに schema_version 置換を手編集で行う前提。

## v2（再生成案）の要旨

**TDD 順** で test を先に赤状態で書き、schemas.py 編集で緑化。fixture + golden の
更新は新規 `scripts/regen_schema_artifacts.py` に集約し、手編集事故を原理的に排除
(idempotent 再実行可能)。新 test は `tests/test_schemas_m5.py` に milestone 単位で
集約し、将来 M6/M7 でも同パターンで増やす。docs 更新を scope に明示組み込み、
後続タスクでの drift を防止。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| **実装順序** | schemas 編集 → fixtures 編集 → golden 再生成 → test 後追い | test 先行 (赤) → schemas 編集 (緑) → script 実行で fixtures/golden 一括更新 |
| **fixture / golden 更新** | 10 ファイルを手編集 + README のインラインコマンドを手動実行 | `scripts/regen_schema_artifacts.py` を新規追加、commit (再利用可能資産) |
| **test ファイル** | 曖昧 (既存 test_schemas.py に追加 or 新規、未確定) | `tests/test_schemas_m5.py` に確定、milestone grouping を規約化 |
| **新規成果物** | なし (test 1 ファイル増の可能性) | test ファイル 1 + scripts 1 (2 つの新ファイル) |
| **変更規模 (files)** | schemas + conftest + fixtures 10 + golden 3 + test 1 + docs = 約 17 | schemas + conftest + fixtures 10 + golden 3 + test 1 + script 1 + docs = 約 18 |
| **ヒューマンエラー耐性** | schema_version 置換漏れ / turn_index 追加忘れのリスクあり | script が idempotent でカバー、事故が起こり得ない |
| **将来の schema bump** | 同じ手順を毎回繰り返す | script を再実行するだけで fixture + golden 更新完了 |
| **契約の文書化** | schemas.py diff のみが真実の源 | pytest が "契約を凍結した意図" を実行可能形式で残す |
| **レビュアー体験** | 17 ファイル diff を PR で追う | schemas.py + test + script + "script 実行結果" の 4 塊で意図を説明 |
| **docs 更新の scope** | 「(必要なら)」で曖昧 | 明示組み込み、後続タスクへの漏れ防止 |
| **リスク** | 手編集事故 / test 後追いによる確証バイアス / milestone 履歴の埋没 | script 自体のバグ / 追加資産 (script) の保守コスト |

## 評価（各案の長所・短所）

### v1 の長所
- 既存 M4 手順の踏襲なので、実行パスが完全に既知
- 新規ファイルを最小化 (scripts/ 配下を新設しない)
- レビュー範囲が純粋に schemas.py 周りに閉じ、変更の意図が狭い

### v1 の短所
- fixture 10 ファイルの手編集でヒューマンエラーの余地 (特に `schema_version` タイポ、
  `turn_index` の差し忘れ、末尾改行・インデント不一致)
- test を後追いにすると、自分が書いた schemas.py が "pass する方向" に test を寄せる
  確証バイアスが入りうる (reimagine の主旨と矛盾)
- M5 で追加した契約がどこに記述されたかが将来探しにくい
  (`test_schemas.py` に増分を混ぜると履歴が埋没)
- M6 以降の contract bump でも同じ手順を手で繰り返す (自動化機会の見逃し)

### v2 の長所
- TDD 順序で「凍結したい契約」が最初に実行可能仕様として表現される
- `scripts/regen_schema_artifacts.py` は 1 度書けば将来の M6/M7 でも再利用できる資産
- milestone-grouped test ファイルで、過去の契約変更の意図を後から読みやすい
- fixture / golden が "schemas.py + script の決定論的結果" として機械的に説明可能
- 手編集事故の可能性が原理的にゼロ (idempotent script)
- docs 更新が scope 明示で漏れないので後続タスクが楽

### v2 の短所
- 新規ファイル 2 つ (`scripts/regen_schema_artifacts.py` / `test_schemas_m5.py`) の
  追加で diff が広がる (+20-60 行程度)
- `scripts/` ディレクトリを新設する場合、repo 構造に新しい区画を足す意思決定が伴う
  (本 repo では `scripts/` 未使用の可能性あり — 要確認)
- script 自体に将来バグが入ると複数 kind 同時破壊のリスク
  (ただし idempotent 設計なので検出は容易)

## 推奨案

**v2 (再生成案) を採用**

### 理由

1. **本 task の目的が "contract 凍結" である以上、pytest が first-class の契約記述と
   なる TDD 順序が筋として自然**。v1 のように test を後追いにすると、スキーマ変更の
   意図が schemas.py diff と steering/*.md という外部参照にしか残らず、数ヶ月後に
   読み返す人が契約の全体像を把握しにくい。
2. **fixture / golden の手編集は M4 でも神経質な作業だった**。本 task で script 化
   すれば、M6/M7 の bump で再利用でき、以降の schema freeze コストを一度限りの投資で
   大幅削減できる。投資額 (+20-40 行の script) が小さい。
3. **milestone-grouped test ファイル** は repo 内に precedent がないので、本 task で
   規約化する意味がある。`test_schemas_m5.py` があれば後続の `test_schemas_m6.py`
   が自然に連なり、各 milestone で何を凍結したかが test の構造から読める。
4. **v1 の "M4 踏襲" は安全策だが、M4 の手編集プロセス自体の改善機会を見逃している。**
   reimagine の主旨 (先行案の確証バイアスを排除) に沿って v1 の暗黙前提 (手編集 OK)
   を問い直した結果、自動化の価値が見えた。

### v2 の実装順序 (採用後の作業)

1. `scripts/` ディレクトリと `scripts/regen_schema_artifacts.py` を作成
   (ディレクトリが未使用なら repo 初導入、docstring でスクリプト用法を記載)
2. `tests/test_schemas_m5.py` を新規作成し、赤状態で 7 test を書く
3. `uv run pytest tests/test_schemas_m5.py` で全赤を確認
4. `src/erre_sandbox/schemas.py` を編集:
   - SCHEMA_VERSION を `"0.3.0-m5"` に
   - `Cognitive.dialog_turn_budget` 追加
   - `DialogTurnMsg.turn_index` 追加
   - `DialogCloseMsg.reason` literal 拡張
   - 2 Protocol 追加 + `__all__`
5. `uv run pytest tests/test_schemas_m5.py` で全緑を確認
6. `uv run python scripts/regen_schema_artifacts.py` 実行 → fixtures + golden 更新
7. `tests/conftest.py::_build_dialog_turn` の default=0 追加
8. Grep で `DialogTurnMsg(` 直接構築を探し、`turn_index=0` 明示付与
9. `uv run pytest -q` 全 PASS 確認、`ruff` / `mypy` PASS 確認
10. `docs/repository-structure.md` の schema_version 言及を 0.3.0-m5 に更新
11. commit → push → PR

### v1 から既に編集済の内容の扱い

schemas.py の以下 3 点は既に v2 採用後の編集内容と一致するため、そのまま保持する
(これから v2 手順の Step 2-4 を進める際、Step 4 で追加分のみを足す):

- `SCHEMA_VERSION = "0.3.0-m5"` ✅
- `Cognitive.dialog_turn_budget` ✅
- `DialogTurnMsg.turn_index` ✅

ただし v2 の TDD 原則に従い、**test を書いてから schemas.py に戻る** 順序を守るため、
残り 2 Protocol + literal 拡張 + `__all__` 更新は test 先行で進める。

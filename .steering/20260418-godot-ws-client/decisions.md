# 重要な設計判断 — T16 godot-ws-client

## 判断 1: 3 スクリプト完全分離 (v2 採用、v1 の 1 本詰めを破棄)

- **判断日時**: 2026-04-18
- **背景**: requirement.md が `WebSocketClient.gd` / `EnvelopeRouter.gd` /
  `AgentManager.gd` の 3 スクリプト構成を明示。v1 初回案は 1 本に畳む素直案で
  V1-W1 (SRP 違反) / V1-W5 (要件違反) を内包していた
- **選択肢**:
  - A: `WebSocketClient.gd` に全部詰める (v1 素直案)
  - B: Client / Router / AgentManager に責務分割 (v2 再生成案)
- **採用**: B
- **理由**:
  - requirement.md との整合性
  - Router の 7 専用 signal 契約が T17 avatar 接続 / M5 zone visuals / M9 LoRA
    ペルソナで再利用される共通基盤になる
  - Client は通信のみ、Router は分岐のみ、Manager は受け手のみ → 各々独立に
    テスト可能 + 差し替え可能
- **トレードオフ**: ファイル数 +2 (ただし 1 本 150 行より 3 本計 230 行の方が
  読みやすい)
- **影響範囲**: T17 avatar 実装時は AgentManager の各 handler を置き換えるだけ
- **詳細**: `design-comparison.md` + `design.md` §実装アプローチ

## 判断 2: Fixture 再生を別シーン境界で物理隔離

- **判断日時**: 2026-04-18
- **背景**: v1 は `WebSocketClient.gd` 内に fixture 再生を混ぜる設計で、
  production path に dev 用コードが残留する V1-W2 が致命的
- **選択肢**:
  - A: 同一スクリプト内に mode フラグ (v1)
  - B: `scripts/dev/FixturePlayer.gd` + `scenes/dev/FixtureHarness.tscn` に
    物理隔離 (v2)
  - C: Autoload singleton で切替
- **採用**: B
- **理由**:
  - `.pck` ビルド時に `scripts/dev/` / `scenes/dev/` を除外すれば production
    パッケージに fixture コードが入らない
  - production MainScene は不変。FixtureHarness.tscn は MainScene を instance
    した上で WebSocketClient を `set_process(false)` で止める
  - 環境変数・cmdline 引数を production path に入れる必要がなくなる
    (v1 の V1-W7 解消)
- **トレードオフ**: scene / script 2 組の dev 専用ディレクトリが増える
  (README.md で意図を明記することで compensation)
- **起動方式**: Python テストは godot を FixtureHarness.tscn で起動し
  `-- --fixture-dir=<abs>` で絶対パスを注入。production は MainScene.tscn で
  起動。「どのシーンを起動するか」で mode が決まる

## 判断 3: Schema ↔ GDScript kind 同期ガードを新設 (`test_envelope_kind_sync.py`)

- **判断日時**: 2026-04-18
- **背景**: Contract-First 方針 (MASTER-PLAN §2.2) は両機が contract からずれ
  ないことが核。v1 は schemas.py と EnvelopeRouter.gd の同期を手動に委ねて
  おり、V1-W4 (drift 検出不能) を内包
- **選択肢**:
  - A: 手動同期 (v1)
  - B: Python 側で 7 kind を抽出 + GDScript 側 regex で match arm キー抽出 +
    集合一致アサート (v2)
- **採用**: B
- **理由**:
  - schemas.py §7 が変わった時、CI が即 fail して開発者に更新を強制できる
  - Python 側は `get_args(ControlEnvelope)` で discriminated union の
    constituent クラスを辿る — Pydantic v2 の API 変更に対しても比較的頑健
  - Python-only のテストなので速い (秒未満)、Godot 未 install 環境でも走る
- **トレードオフ**:
  - regex は GDScript parser ではないので書き方に一定の制約 (match arm を
    1 行 `"kind":` で書く慣習を守る必要)
  - 対策: code-reviewer MEDIUM #3 対応として regex スコープを
    `on_envelope_received` 関数本体に限定 (`_ROUTER_DISPATCH_RE`)
- **影響範囲**: 将来 schemas.py §7 の拡張 / kind 追加 / kind 削除時にこの
  テストが最初に failure を通知する

## 判断 4: GDScript `class_name` 型注釈を回避 (cross-script reference)

- **判断日時**: 2026-04-18 (code レビュー中の HIGH fix)
- **背景**: 初回実装では `AgentManager.gd` / `WorldManager.gd` /
  `FixturePlayer.gd` が `EnvelopeRouter` を型アノテーションとして参照。
  `.godot/` global class cache が未生成な初回 headless boot で parse エラー
  "Could not find type EnvelopeRouter in the current scope" が発生
- **選択肢**:
  - A: `.godot/` cache を事前生成する事前処理を CI に追加
  - B: cross-script 参照箇所を `Node` 型に緩和し、`has_signal()` で duck typing
- **採用**: B
- **理由**:
  - CI の事前処理追加は脆いし Godot バージョンに依存する
  - `has_signal()` ガードで誤接続時に明示的エラーを出せるので type 安全性は
    むしろ上がる
  - EnvelopeRouter.gd 自体の `class_name EnvelopeRouter` 宣言は残す
    (将来 cache 正常化した後に cross-ref を戻せる余地を残す)
- **影響範囲**: AgentManager の `_REQUIRED_SIGNALS` 定数で必須 signal を列挙
  することで、Router がこの契約に従っているか boot 時に確認

## 判断 5: `_resolve_godot` を `conftest.py` ではなく `_godot_helpers.py` に抽出

- **判断日時**: 2026-04-18
- **背景**: design.md 初期案では conftest.py に移動するとしたが、conftest は
  pytest フィクスチャ専用というプロジェクト慣習 (既存 conftest.py がフィク
  スチャしか含まない)
- **選択肢**:
  - A: `tests/conftest.py` にモジュール関数として追加
  - B: `tests/_godot_helpers.py` に分離し、`from tests._godot_helpers import ...`
- **採用**: B
- **理由**:
  - conftest.py をフィクスチャ専用に保つ既存慣習を維持
  - ヘルパが増えた場合も `_godot_helpers.py` に集約できる
  - `tests/__init__.py` が既に空で存在するため package import が可能
- **影響範囲**: `test_godot_project.py` と `test_godot_ws_client.py` の両方が
  同じヘルパを共有 (`resolve_godot` / 定数 `GODOT_PROJECT` /
  `FIXTURES_CONTROL_ENVELOPE` / `HEADLESS_TIMEOUT_SEC`)

## 判断 6: `error` envelope の受信は `push_warning` + `print` で扱う

- **判断日時**: 2026-04-18 (code レビュー HIGH #1 fix)
- **背景**: 初回実装では `WorldManager._on_error_reported` が `push_error` を
  使用。`error` envelope は schemas.py §7 で定義された **structured observability
  payload** であり、Godot engine レベルの failure ではない
- **選択肢**:
  - A: `push_error` (初回実装)
  - B: `push_warning` + `print`
  - C: `print` のみ
- **採用**: B
- **理由**:
  - `test_godot_project.py:test_godot_project_boots_headless` が既に
    `"ERROR:" not in result.stderr` を assert しているため、`push_error` を
    使うと将来 CI 回帰で壊れる可能性
  - gateway からの構造化エラーは "予期される異常" であり recoverable、
    error-handling Skill ルール 6 に従うと WARNING が正しい severity
  - `print` も併用して stdout に残すことで可観測性を担保

## 判断 7: fixture 再生の 0.5 秒間隔と 2 秒 grace はハードコード定数化

- **判断日時**: 2026-04-18
- **背景**: v1 は「0.5s ハードコード」(V1-W6) として自覚的弱点化されていたが、
  MVP 段階で playlist YAML 機構まで作るのは過剰設計
- **選択肢**:
  - A: YAML playlist ファイル (`fixtures/control_envelope/playlist.yaml`)
  - B: GDScript 定数として `PLAYBACK_INTERVAL_SEC` / `POST_PLAYBACK_GRACE_SEC`
    + `DEFAULT_PLAYLIST` (v2)
  - C: コマンドライン引数で渡す
- **採用**: B
- **理由**:
  - `DEFAULT_PLAYLIST: PackedStringArray` を先頭に定数宣言しておけば、
    将来 YAML 化への差し替えポイントが明示的 (変数名が既に "default")
  - T16 スコープは固定 7 kind 再生で十分、YAML は M5 以降の拡張
  - ハードコード定数は `@export var` 化で将来エディタから変えられる

## 判断 8: セキュリティ対応として MAX_FRAME_BYTES / MAX_FIXTURE_BYTES を導入

- **判断日時**: 2026-04-18 (security-checker HIGH #1 + code-reviewer MEDIUM #2)
- **背景**: LAN 内・認証なしだが、G-GEAR 側のバグ / fixture 書き換えで
  巨大フレームが届いた場合に Godot プロセスがメモリ枯渇する DoS リスク
- **採用値**: 両者とも `1_048_576` bytes (1 MB)
- **理由**:
  - 7 fixture 実測は最大数 KB。1 MB 上限は通常運用に無影響
  - WebSocketClient は `get_packet().size()` で事前チェック、
    FixturePlayer は `file.get_length()` で事前チェック
  - push_warning / push_error で可視化
- **見直しタイミング**: M4 以降で multi-agent snapshot envelope が大型化した
  時、および G-GEAR 側送信レート計測後

## 判断 9: `MainScene.tscn` は手動編集した (Godot エディタ未使用)

- **判断日時**: 2026-04-18
- **背景**: impact-analyzer HIGH 局所 (load_steps 誤り) を把握した上で、
  本セッションでは Godot エディタが起動できない環境制約から手動編集を選択
- **採用値**: `load_steps=6` (4 ext_resource + 1 sub_resource + implicit root)
- **検証**: `test_godot_project_boots_headless` が Godot 4.6.2 で pass
  することで整合性を確認
- **リスク**: 次回 Godot エディタで開いて保存した時、ext_resource ID の
  canonical 化で diff が発生する可能性
- **対応**: PR レビュー時にエディタで開いて再保存した diff を別コミットで
  整形することを推奨 (本 PR では整形なしでマージ可)

## 判断 10: 正規表現による GDScript parse のスコープ限定

- **判断日時**: 2026-04-18 (code-reviewer MEDIUM #3 対応)
- **背景**: `_ROUTER_MATCH_KEY_RE` が `"kind_name":` 形式を行単位で検索するた
  め、将来 `EnvelopeRouter.gd` 内に dict literal や別の match block が追加
  された時 false positive のリスク
- **採用**: `_ROUTER_DISPATCH_RE` で `on_envelope_received` 関数本体を切り出し、
  その内部のみに `_ROUTER_MATCH_KEY_RE` を適用
- **理由**:
  - 後続開発者が EnvelopeRouter に helper を追加しても CI ガードが安定
  - 関数境界の概念を regex で表現することでテストの意図が読みやすくなる

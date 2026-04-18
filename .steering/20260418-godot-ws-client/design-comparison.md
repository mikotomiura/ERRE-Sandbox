# T16 godot-ws-client — 設計案比較 (v1 vs v2)

## v1 (初回案) の要旨

`WebSocketClient.gd` 1 本に **WebSocket 接続 + 再接続 + fixture 再生 +
kind dispatch** を全て詰める凡庸な素直案。`AgentManager.gd` はログスタブのみ、
`EnvelopeRouter.gd` は作らず Client 内の private メソッドに畳む。fixture
mode 切替は環境変数 + cmdline 引数の二重サポート。schemas.py ↔ GDScript の
kind 同期は手動。自覚的弱点を V1-W1 ～ W7 として本人が明示。

## v2 (再生成案) の要旨

3 スクリプト **完全分離** (Client = 通信 / Router = 7 個の専用 signal emit /
AgentManager = 受け手) + **fixture を別シーン境界** (`scenes/dev/
FixtureHarness.tscn` + `scripts/dev/FixturePlayer.gd`) で完全隔離 +
**schema 同期ガードテスト** (`tests/test_envelope_kind_sync.py`) で schemas.py
変更時のドリフトを CI で自動検出。Fixture mode 起動は `--fixture-dir` cmdline
引数のみに絞る。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| **責務分割** | WebSocketClient.gd 1 本に全部 (~150 行) | Client / Router / AgentManager の 3 本に分離 (計 ~230 行) |
| **EnvelopeRouter.gd** | 作らない (requirement 要件と不整合) | 作る。7 個の専用 signal を emit、kind 分岐の単一責任 |
| **Fixture 隔離** | production path に混入 (同一スクリプト内) | 別シーン境界 (`scenes/dev/` + `scripts/dev/`) で物理隔離 |
| **Fixture 起動方式** | 環境変数 + cmdline 引数の二重 | cmdline 引数 (`--fixture-dir`) のみ |
| **Schema 同期** | 手動 (将来 drift 放置) | CI ガードテスト (`test_envelope_kind_sync.py`) で自動検出 |
| **AgentManager 将来性** | T17 で書き直し懸念あり | Router の signal 経由で境界を固定、T17 は avatar connect のみ |
| **Playlist 拡張性** | 0.5s 間隔ハードコード、順序もハードコード | 順序は定数 array で先頭に宣言 (将来 YAML playlist 差替容易) |
| **MainScene.tscn 変更量** | WebSocketClient + AgentManager 2 ノードに script attach | 同左 (v1/v2 差なし) |
| **新規テスト** | 1 本 (`test_godot_ws_client.py`) | 2 本 (`test_godot_ws_client.py` + `test_envelope_kind_sync.py`) |
| **実装行数 (概算)** | ~300 行 (scripts 200 + tests 100) | ~490 行 (scripts 310 + tests 180) |
| **工数見込み** | 0.7 d | 1.0 d (requirement.md の 1d 見積と一致) |
| **変更規模** | 小さく始めて後で膨張 | 最初から分割、後続で広がらない |
| **テスト戦略** | Godot headless のみ | Godot headless + Python-only kind sync (二段) |
| **リスク** | 中-高: V1-W1〜W7 が蓄積して T17 破壊的変更を招く | 低-中: fixture 隔離と同期ガードで 2 大 MEDIUM を LOW に格下げ |

## 評価 (各案の長所・短所)

### v1 の長所
- **着手が軽い**: 新規ファイル 2 本 + 修正 2 ファイルで最小
- **理解が速い**: 1 ファイルに全部あるので読み手の認知負荷が小さい (短期的には)
- **MainScene.tscn 変更が 1 ノード分で済む**: impact-analyzer HIGH 局所の露出が小さい

### v1 の短所
- **requirement.md と設計が不整合**: 「EnvelopeRouter.gd を作る」と要件に
  明記しているのに設計で畳んでいる。要件側を後から変えるなら明示的に記録が必要
- **SRP 違反 (V1-W1)**: 150 行規模から肥大化。T17 で avatar 処理が入ると
  さらに膨らみ、破壊的リファクタが発生する予感
- **fixture コード混入 (V1-W2)**: 将来 `.pck` ビルド時に除外する手立てがない
- **schema drift 検出不能 (V1-W4)**: schemas.py が将来変わった時、GDScript
  側が黙って古くなる。発見は「動かしてみて気づく」頼み
- **テスト可能性が低い**: Router ロジックが private メソッド化され単体テスト
  困難

### v2 の長所
- **requirement.md と完全整合**: 3 スクリプト構成、EnvelopeRouter 中核
- **将来拡張が直線的**: T17 の avatar 処理は AgentManager に加算、M5 のゾーン
  視覚効果は Router signal を subscribe するだけ。既存コードへの衝突なし
- **fixture 物理隔離**: production path に dev 専用コードが一切入らない。
  `scripts/dev/` ディレクトリを production ビルドから除外する運用が自然
- **schema drift 自動検出**: schemas.py 変更 → CI fail → 開発者が EnvelopeRouter
  を更新する強制ループ。長期保守の前提が整う
- **signal baseline の確立**: EnvelopeRouter の 7 signal 契約は M5 `erre-mode-fsm`
  や `godot-zone-visuals` まで同じものが使える。この投資は T16 を超えて長く効く
- **テスト戦略が 2 段**: Python-only の kind sync テストは速い (秒未満) /
  headless 統合テストは重い (秒〜十秒)。CI パイプラインで前者を先行させられる

### v2 の短所
- **着手が重い**: ファイル 5 本新規 + 2 本修正。工数 1.0 d (v1 の 0.7 d より +0.3 d)
- **ディレクトリ階層が深くなる**: `scripts/dev/` / `scenes/dev/` が増える
  (impact-analyzer 的には MainScene.tscn の変更量は同じで、増えるのは新規
  ファイルだけなのでリスク増加はわずか)
- **FixtureHarness.tscn の設計が必要**: MainScene を instance しつつ
  WebSocketClient を disable する仕組みを追加設計 (ただし手順は明確、難度低)
- **Python regex で GDScript をパースするテスト**: 完全に堅牢ではなく、Router
  のコーディング規約 (match 文の書き方) に一定の制約が生じる

## 推奨案

**v2 を採用**。理由:

1. **requirement.md との整合性**: 要件で 3 スクリプト構成を明示しているのに
   設計で畳むのは、要件再定義を伴う意思決定。現時点で要件変更の必要性がない
   以上、v1 は要件違反に相当する
2. **T17/M5/M9 への波及効果**: Router の signal 契約は後続タスクの接続点になる。
   ここを最初に固めておけば後の設計自由度が大きい
3. **schema drift ガード**: Contract-First 方針 (MASTER-PLAN §2.2) の核は
   「両機が contract からずれないこと」。GDScript の drift 検出機構を T16 で
   作っておくのは Contract-First 思想の直接の延長
4. **工数差 +0.3 d は妥当**: requirement.md の見積 1.0 d は v2 前提と読める。
   v1 の 0.7 d は将来の破壊的リファクタ工数を隠蔽しているだけ
5. **V1-W2 (fixture 混入) は事故源**: 「後で分離」は高確率で忘れる。最初から
   物理境界を引くのが合理的

**採用判断日**: 2026-04-18
**採用根拠**: requirement 整合 / 将来拡張性 / Contract-First 思想の徹底 / v1 の
自覚的弱点のうち 5/7 (V1-W1, W2, W4, W5, W6) を構造で解消

## ハイブリッドの可能性検討

ユーザーが「ハイブリッド」を選択する場合の具体的な切り出し候補:

- **H1: v2 から Fixture 隔離 + Kind sync テストのみ採用、Router は作らず
  Client 内 match** — V1-W4/W2 を解消するが、V1-W1/W5 は残る。中途半端
- **H2: v2 から Router 分離 + Kind sync テストのみ採用、Fixture は v1 流 (同一
  スクリプト内)** — V1-W1/W4/W5 を解消するが、V1-W2 は残る。やや合理的
- **H3: v2 フル採用、ただし `scripts/dev/` は作らず、FixturePlayer.gd を
  `scripts/` 直下に置く** — 物理隔離を弱める。中途半端

ハイブリッドは v2 の効果を部分的に損なうため、**推奨は v2 フル採用**。

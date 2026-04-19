# 設計案比較 (v1 vs v2)

## v1 (初回案) の要旨

**FastAPI mini app + Vanilla JS SPA + StaticFiles**。
Python 側は `server.py` / `stub.py` / `metrics.py` の 3 ファイルに分割し、
HTML/JS/CSS は `static/` ディレクトリに置き `StaticFiles` で配信。
Client 側は生の Vanilla JS で DOM 操作、`collections.deque` で rolling window を
保持、閾値判定は client でも server でも可能にする素直な構成。

## v2 (再生成案) の要旨

**Single-file HTML + Server-side Metrics State + Typed UiMessage (3 kind)**。
HTML/JS/CSS は Python 文字列定数に埋め込み static ディレクトリなし。
Server 側で `DashboardState` が metrics 集計と threshold 判定を一元化し、
client には `SnapshotMsg` / `DeltaMsg` / `AlertMsg` の 3 種 discriminated
union として送出。Client 側は Web Components 3 つで宣言的に描画。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| Python ファイル数 | 5 (server/stub/metrics + static 3) | 7 (server/state/messages/stub/html + `__main__`/`__init__`) |
| 静的ファイルの扱い | `static/` ディレクトリ + `StaticFiles` mount | Python 定数 (`HTML_TEMPLATE`) に埋め込み、`/dashboard` が文字列返却 |
| WS メッセージ型 | ControlEnvelope をそのまま流す | UiMessage discriminated union 3 種 (snapshot/delta/alert) |
| Metrics 集計の場所 | 未明示 (client 側にも書ける余地) | Server 側 `MetricsAggregator` に一元化 |
| Threshold 判定の場所 | 未明示 | Server 側 `ThresholdEvaluator`、alert を push |
| 再接続時の挙動 | client 側状態はリセット | snapshot で直近 state を復元 |
| Client 側 JS パターン | 素の DOM 操作 | Web Components + Shadow DOM |
| テストの粒度 | 4 件 (最低ライン) | 10 件 (層別、state/stub/server を分離) |
| 既存パターンとの整合 | StaticFiles は標準、FastAPI app factory OK | schemas.py の discriminated union 思想を継承、より一貫 |
| 保守時の手間 | HTML/JS は独立ファイルで編集しやすい | Python 内埋め込み、編集時 editor の syntax highlight が弱い |
| 配布・再利用 | static ファイル群を同梱する必要 | Python モジュール単体で完結、CLI で即起動可 |
| 過設計リスク | 低 (最小構成) | 中 (UiMessage 3 種は minimal 要求より手厚い) |

## 評価

### v1 の長所
- **最小実装**: 学習曲線が浅く、誰でも数時間で保守可能
- **HTML/JS の編集性**: エディタの HTML モードで素直に書ける
- **StaticFiles が業界標準**: FastAPI の教科書通り
- **実装スピード最速**: 0.5d 以内に収まる蓋然性高

### v1 の短所
- **Metrics/Threshold の置き場所が曖昧**: client と server どちらにも書ける余地があり、
  実装者によってブレる
- **再接続で state リセット**: 開発中に dashboard ページをリロードすると履歴ロスト
- **テストの層構造が浅い**: 4 件程度では state/stub/server を個別に検証しきれない
- **schemas.py の discriminated union 思想との非対称**: WS でそのまま envelope を流すと、
  Threshold alert 等の UI 固有メッセージをどう追加するか後付けになる

### v2 の長所
- **責務分離が明確**: state (`DashboardState`) / transport (`UiMessage`) / rendering (HTML)
  が独立してテスト可能
- **schemas.py との思想一貫**: 3-kind discriminated union は既存 ControlEnvelope と同型
- **再接続耐性**: snapshot による state 復元
- **server 側ロジックが testable**: MetricsAggregator と ThresholdEvaluator を純関数 /
  純 dataclass で書け、TestClient 不要で単体テスト可能
- **10 件のテストで要件を超過**: 4 件要件に対して十分なカバレッジ

### v2 の短所
- **Python 文字列に HTML 埋込**: editor の syntax highlight が効かない
  (ただし raw string + f-string でギリギリ許容範囲)
- **ファイル数が若干多い**: 7 vs 5
- **UiMessage 3 種が要件より手厚い**: requirement は「envelope をそのまま流せ」と
  は書いていないが、「envelope 色分け + threshold 警告」を満たすだけなら v1 でも可
- **Web Components の学習コスト**: チーム (1 人) にとって初めてなら学習時間増

## 推奨案

### **v2 を推奨 (ただし html.py の内容は v1 的「HTML editor friendly」に寄せる)**

**根拠**:

1. **schemas.py / integration/ との思想一貫性が決定的**
   プロジェクトは既に「型付き discriminated union」で wire 契約を表現している
   (ControlEnvelope)。Dashboard の WS も同じ思想で UiMessage を定義すれば、
   学習コスト低・既存テストパターン流用可。逆に v1 の "envelope そのまま流し" は、
   後で threshold alert 等を足す時に混乱する。

2. **テスト容易性の差が大きい**
   v1 の「metrics 計算 unit test」は `deque` を触るだけで簡素だが、
   server 側で threshold 判定も含めた state を持つ v2 のほうが TestClient 不要な
   純関数テストが書ける。結果的に開発速度は早い可能性。

3. **再接続耐性が開発時の実用価値が大きい**
   開発中に何度もリロードするため、snapshot 復元は単純な DX 向上。
   実装コストは DashboardState の現状を dict に dump するだけなので安価。

4. **UiMessage 3 種は過設計ではなく必要設計**
   要件の「envelope 色分け」 + 「threshold 警告」は、同じ WS に性質の異なる
   2 種のメッセージを混在させる。discriminated union で分けるのが素直。

### v1 から取り込む要素 (ハイブリッドの部分)

- **HTML 編集性**: `html.py` の HTML_TEMPLATE 定数はなるべく plain な HTML として
  書き、JS は最小限。「Web Components は 1 個だけ」に絞り、他は普通の `<div>` + DOM 操作
  (Web Components 3 個 → 1 個に縮小で複雑性軽減)

### v2 採用で破棄する v1 の要素

- **`static/` ディレクトリ**: 廃止、Python 文字列に埋込
- **Client 側 metrics 計算**: 廃止、server 集計に統一

## 最終採用: v2 (Web Components を 1 個に縮小、HTML_TEMPLATE は plain HTML 寄せ)

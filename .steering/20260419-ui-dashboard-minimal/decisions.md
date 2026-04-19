# 設計判断 (T18 ui-dashboard-minimal)

## D1. Dashboard は T14 とは独立した mini FastAPI app (別プロセス) として動作させる

### 判断
`src/erre_sandbox/ui/dashboard/` は独立した FastAPI app を持ち、
`python -m erre_sandbox.ui.dashboard` で localhost:8001 (default) に起動する。
T14 gateway が将来同居を希望する場合は、`create_app()` factory を import すれば
可能だが、本タスクでは独立運用を既定とする。

### 根拠
- T14 未完成の間も T18 単体で検証・回帰できる
- optional タスクであり、T14 の実装工数を圧迫しない
- 同居を選択する余地は `create_app()` で残されている

### 却下した代替案
- **T14 同居必須**: T14 実装待ちで T18 着手できなくなる
- **完全に別パッケージに分離**: 過剰、`ui/` 層の既定方針で十分

---

## D2. UI 側メッセージは discriminated union (UiMessage) として型定義する

### 判断
Server → Client の WS メッセージを Pydantic discriminated union として定義:

- `SnapshotMsg` (kind=`snapshot`): 接続直後の全 state
- `DeltaMsg` (kind=`delta`): envelope 1 件受信ごとの差分
- `AlertMsg` (kind=`alert`): threshold 逸脱時の警告

`ControlEnvelope` をそのまま流すのではなく、UI 固有のレイヤーを挟む。

### 根拠
- schemas.py `ControlEnvelope` と同じ discriminated union パターンを踏襲、思想の一貫性
- threshold alert は envelope と性質が異なるメッセージなので型分離が素直
- 将来、summary / reset / config 等のメッセージを追加する時、union に追記するだけ

### 却下した代替案
- **ControlEnvelope をそのまま流す**: alert を後付けで混ぜる時に整理が必要
- **文字列 JSON で判別**: 型安全性なし、discriminator 解決を手動で書く必要

---

## D3. Metrics 集計と threshold 判定は server 側 state に一元化する

### 判断
`MetricsAggregator` と `ThresholdEvaluator` を server 側に置き、
`DashboardState` が envelope stream を消費して metrics/alerts を生成する。
Client は受信した delta/alert を表示するだけ (計算しない)。

### 根拠
- 複数 client が接続しても state が一貫する (server は 1 ソース)
- 純関数的な unit test が書ける (TestClient 経由の統合テスト不要)
- Threshold 判定ロジックを 1 箇所で保守できる

### 却下した代替案
- **Client 側集計**: 複数 viewer で計算が重複、切断で状態ロスト
- **DB 永続化**: 過設計 (in-memory rolling buffer で十分と要件で明言)

---

## D4. HTML / JS / CSS は Python 定数 (`html.py`) に埋め込み、static/ ディレクトリを作らない

### 判断
`src/erre_sandbox/ui/dashboard/html.py` に `HTML_TEMPLATE: str` 定数を置き、
FastAPI の `/dashboard` route はそれを `HTMLResponse` で返す。

### 根拠
- モジュール単体で配布可能、`StaticFiles` mount の設定が不要
- テストで HTML 内容を文字列 diff 可能
- 編集時の syntax highlight は弱まるが、HTML の複雑度は低いため許容

### 却下した代替案
- **`static/` ディレクトリ + `StaticFiles` mount**: パス解決が面倒、単体モジュール性が落ちる
- **Jinja2 テンプレ**: 新規依存、要件で排除済
- **React / Vue build**: 新規依存、要件で排除済

### 運用ルール
- HTML 編集は `html.py` の `HTML_TEMPLATE` 定数を直接書き換え
- JS は同 `HTML_TEMPLATE` 内の `<script>` に埋め込み (最小限)
- Web Components は 1 個のみ採用 (`<ep-envelope-row>` 的な行単位コンポーネント)、
  3 パネル全体は plain `<div>` で記述

---

## D5. Stub generator は fixtures/control_envelope を決定論的に循環する

### 判断
`src/erre_sandbox/ui/dashboard/stub.py` の `StubEnvelopeGenerator` は、
`fixtures/control_envelope/*.json` から読み込んだ 7 種を循環し、
seed 固定で latency ノイズ (±10ms) を加えて stream 生成する。

### 根拠
- T14 未完成でも UI 挙動を視覚確認できる
- 決定論的 (seed 指定で同一列) なので unit test で完全再現可能
- 既存 fixtures を再利用するため、ControlEnvelope Pydantic で parse 可能性が担保

### 却下した代替案
- **毎回ランダム生成**: テスト困難、回帰不能
- **合成した envelope を作る**: fixtures との乖離リスク、二重管理

---

## D6. 閾値判定は warming-up (最初 5 件) をスキップする

### 判断
`ThresholdEvaluator` は envelope stream の最初の 5 件は alert を発信しない
(warming-up 期間として扱う)。6 件目以降で `MetricsAggregator` の出力が
`M2_THRESHOLDS` を超えた時のみ alert 発信。

### 根拠
- サンプル数が少ない段階では p50/p95 が意味をなさない
- 接続直後の noise で false positive を出すと UI がノイジー
- 5 件は経験則、`WARMING_UP_COUNT = 5` として decisions で定数化

### 却下した代替案
- **常時判定**: 初期 false positive 多発、UI 体験悪化
- **100 件以上を warming-up とする**: 開発中の検証が遅くなる、視認性低下

---

## D7. `ui/dashboard/` は `schemas.py` と `integration/` に依存、他モジュールは禁止

### 判断
`src/erre_sandbox/ui/dashboard/` 内の Python ファイルは、
`erre_sandbox.schemas` と `erre_sandbox.integration` のみを import してよい。
`cognition`, `memory`, `world`, `inference` は禁止。

### 根拠
- `architecture-rules` の `ui/` 層規則 (schemas.py のみ) に `integration/` を追加
- integration/ は本質的に UI が消費する契約層なので、依存対象として妥当
- MVP の dashboard は観測専用で、cognition/memory の内部を直接触る必要がない
  (全て WS 経由)

### 却下した代替案
- **world/ や cognition/ を import**: architecture-rules 違反、疎結合の原則崩れ
- **schemas.py のみに絞る**: integration の Thresholds / SessionPhase が使えない → 不便

### 実装時の確認
```bash
# 依存方向違反の検査
grep -rE "from erre_sandbox\.(cognition|memory|world|inference)" \
  src/erre_sandbox/ui/dashboard/
# 何も出なければ OK
```

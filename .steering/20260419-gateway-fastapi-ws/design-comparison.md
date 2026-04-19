# 設計案比較 — T14 gateway-fastapi-ws

## v1 (初回案) の要旨

**`Session` クラス + `session.py` 分離型**。Session インスタンスが
`SessionPhase` enum を保持し、`asyncio.TaskGroup` で内部に 3 タスク
(handshake / recv / send) を抱える。Idle 判定は別 watchdog タスクが
`time.monotonic` 差分を 1 秒ごとに polling。Fan-out は単一 broadcaster タスクが
registry 経由で全 session の `Session.enqueue()` を呼ぶ。テストは
`test_session.py` (Session クラス単体) と `test_gateway.py` (TestClient 経由) の
2 ファイル分離、合計 ~1200 行。

## v2 (再生成案) の要旨

**Session クラス不在、WS ハンドラ関数 `ws_observe` そのものがセッション**。
状態機械の 3 フェーズは try/except の境界として関数の線形制御フローに埋め込む。
Idle timeout は `asyncio.timeout(IDLE_DISCONNECT_S)` を `ws.receive_text()` ごとに
ネストすることで watchdog タスクを排除。Handshake timeout も `asyncio.timeout` で
統一。Registry は `dict[str, Queue]` の薄いラッパ (state 機械なし)。
`session.py` を作らず `gateway.py` 1 ファイルに集約、~850 行。テストは
関数単体層 + TestClient 統合層の 2 層を 1 ファイルで。

## 主要な差異

| 観点 | v1 | v2 | 注釈 |
|---|---|---|---|
| **Session の表現** | `Session(ws, id, runtime)` クラス、`SessionPhase` 属性を保持 | WS ハンドラ関数 `ws_observe` のローカル変数と try/except 境界 | v2 は "session" を一級オブジェクトと見ない |
| **ファイル分離** | gateway.py + session.py | gateway.py のみ | v2 は責務が密結合なので分けない方が自然 |
| **Idle 監視** | 別 watchdog Task + `time.monotonic()` polling | `asyncio.timeout(IDLE_DISCONNECT_S)` を receive ごとにネスト | v2 の方がタイマー管理を OS/async 側に委譲できる |
| **Handshake timeout** | `asyncio.wait_for(recv, 5)` | `async with asyncio.timeout(5)` | v2 は 3.11+ の native コンテキストマネージャ |
| **Fan-out 戦略** | 単一 broadcaster → 各 Session の `enqueue` メソッド経由 | 単一 broadcaster → Registry が queue 集合に直接 put | 本質は同じ、v2 は Session 呼び出しの間接層を省く |
| **Registry** | `SessionRegistry` クラス、内部に dict + iter_active() | `Registry` (dict ラッパ)、`fan_out()` + `len()` のみ | v2 の方が責務が軽い |
| **phase enum 使用** | Session.phase で能動的に使う | protocol.py の定義は残すが gateway.py では使用しない | v2 はコード内に状態を持たない (try/except 境界が状態) |
| **テスト分離** | test_session + test_gateway の 2 ファイル | test_gateway 1 ファイル (関数単体 + TestClient の 2 層) | v2 は mock WS で関数単体テストできる |
| **変更規模** | ~1200 行 (4 新規ファイル) | ~850 行 (2 新規ファイル) | v2 は 30% 小さい |
| **Error path の網羅** | Session.run() の except\* で handle | 関数全体の try/except 階層で handle | どちらも 6 種の ErrorMsg.code に対応可 |
| **テスト速度** | test_session が速い (mock)、test_gateway は遅め | 関数単体層が速い、TestClient 層が遅め | 差は小さい |
| **読みやすさ** | Session クラスに州を集約、各メソッドは短い | ハンドラ関数 1 本を上から読めば session ライフサイクル全てが見える | v2 は制御フロー追跡が 1 関数で済む |

## 評価

### v1 の長所
1. **Session オブジェクトの inspectability**: デバッグ時に `registry.iter_active()` で
   各 session の phase / queue 状態を完全に観察できる。
2. **拡張容易**: 新機能 (例: per-session メトリクス、session 単位の認証) を
   追加する時、Session クラスにフィールド / メソッドを足すだけで済む。
3. **テスト隔離**: Session クラス単体テストは mock WS だけで関数呼び出しを検証でき、
   FastAPI ランタイムを起動しないで済む範囲が広い。

### v1 の短所
1. **タスク・状態の爆発**: Session 1 つにつき 3 (+ watchdog で 4) タスク × 複数接続で
   asyncio タスク数が比例的に増える。idle 判定 polling は 1Hz でも N 接続分 CPU を使う。
2. **状態機械の二重表現**: try/except の制御フローと `SessionPhase` enum 属性が
   同じ情報を 2 箇所で保持し、同期がズレるリスク。
3. **コード量**: Session クラスの setup/teardown、registry が Session を扱うための
   型付け、2 ファイル分離の import オーバヘッドが重なる。
4. **テストコードも二重**: Session 単体と TestClient 経由で同じシナリオを 2 回書きがち。

### v2 の長所
1. **制御フロー = 状態機械**: phase 遷移を enum で明示せず、try/except 境界と
   関数の構造で表現。2 箇所同期の必要なし。
2. **`asyncio.timeout` ネイティブ活用**: Python 3.11+ の native コンテキスト管理。
   watchdog タスクと `time.monotonic` polling を排除、コード量とオーバヘッド両方削減。
3. **コード量が 30% 小さい**: ~850 行 vs ~1200 行。保守対象が減る。
4. **WS ハンドラ 1 関数を読めば session が分かる**: 新規参加者の読解コストが下がる。
5. **テストも 1 ファイルに集約**: 関数単体層 (速い) + TestClient 層 (遅い) を
   同じファイルに並べることで、"関数 vs 統合" の対応を視覚的に追える。
6. **MVP 範囲に合う**: Session に拡張機能を詰め込みたくなるのは M4-M7 以降。
   MVP では Session の責務は限定的なのでクラス化オーバーキル。

### v2 の短所
1. **inspectability 低下**: session 個別の phase を外から観察できない
   (registry は queue だけ持つ)。デバッグでは `_send_loop` / `_recv_loop` の
   タスク名で追う必要がある。将来メトリクスを足す時、v2 から v1 的な Session 型への
   リファクタが必要になる可能性。
2. **関数が長くなりがち**: ハンドラ関数に全 phase を詰め込むため、ネストが深くなる
   傾向 (try/except/finally が 3 層)。可読性維持のために `_send_loop` / `_recv_loop` を
   別関数に切るルールを自分に課す必要あり (v2 は既にそうしている)。
3. **`asyncio.timeout` ネスト時の挙動理解**: 3.11+ native でも、TaskGroup 内の
   task に timeout をネストする場合の CancelledError 伝播を正確に理解する必要あり。
   エッジケースで挙動が直感に反する可能性 (テストで吸収する)。
4. **`fast_timeouts` fixture の難しさ**: `HANDSHAKE_TIMEOUT_S` をテストで短縮する時、
   v1 は Session の `__init__` 引数で渡せるが、v2 は module-level 定数を参照するので
   `monkeypatch` か、gateway.py 内で定数を都度参照する実装制約が必要。

## 推奨案

**採用: v2 (再生成案)**

### 理由

1. **関数 = 状態機械の表現力**: `ws_observe` 関数を上から下に読めば AWAITING →
   ACTIVE → CLOSING の全 path が追える。`SessionPhase` enum を値として保持する
   必要がない。二重表現リスクがなくなる。
2. **`asyncio.timeout` が idle + handshake で統一できる**: v1 の watchdog タスクと
   `wait_for` の混在は認知負荷。v2 は 1 つのパターン (コンテキストマネージャ) に
   統一されるため、error-handling Skill の「crash-loud + 限定 fallback」の思想とも整合する。
3. **30% コード量削減**: `Session` クラスと `session.py` の分離、およびクラスを
   使う事に伴う型付けオーバヘッドが消える。MVP の responsibility に見合ったサイズ。
4. **MVP 範囲が決定打**: Session 単位で持ちたい state (phase 以外に、認証情報・
   per-client metric・subscription filter) は M4-M7 以降で初めて現れる。v2 からの
   v1 方向へのリファクタは可能であり、早期最適化の罠を回避する。
5. **asyncio 3.11+ ネイティブ使用の一貫性**: T13 で asyncio.TaskGroup を初めて
   導入した流れを v2 が継承 (`asyncio.timeout` は同年代の native 追加)。
   プロジェクト全体で Python 3.11 の async 機能を活用する方針に合う。
6. **v1 の長所は補完可能**:
   - inspectability は `Registry.debug_snapshot()` メソッド (queue サイズ / session_id /
     作成時刻) を 20 行程度で足せば同等以上に
   - 拡張容易性は将来 M4+ で必要になった時に Session クラス化する余地を残す

### v2 採用時の補強 (v1 から取り入れるエッセンス)

- `Registry.debug_snapshot() -> list[dict]` を足して inspectability を確保
- ハンドラ関数のネストが深くなりすぎないよう、v2 design §1.1 で示した構造
  (phase ごとに `# ---- Phase N: ... ----` コメント + `return` で早期終了) を
  実装時にも厳守する
- `fast_timeouts` fixture は `monkeypatch.setattr(protocol, "HANDSHAKE_TIMEOUT_S", 0.2)` で
  実装する (gateway.py 内では `from . import protocol` して `protocol.HANDSHAKE_TIMEOUT_S`
  で参照することで、monkeypatch が効くようにする)

### 採用プロセス履歴予定

- 初回案 (design-v1.md) と再生成案 (design.md = v2) を比較
- 採用: **v2**
- 根拠: 関数 = 状態機械の表現力、`asyncio.timeout` 統一、30% コード量削減、
  MVP 範囲に見合ったサイズ、Python 3.11 ネイティブ機能活用。
  v1 の inspectability は Registry.debug_snapshot() で、拡張容易性は将来の
  Session クラス化で、それぞれ補完可能。

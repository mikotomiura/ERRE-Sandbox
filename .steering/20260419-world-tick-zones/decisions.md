# 設計判断の記録 — T13 world-tick-zones

実装中に確定した非自明な設計判断と根拠。`decisions.md` は将来「なぜこう書いたか」を
説明するための記録。

## D1: 単一コルーチン + heapq スケジューラ (vs TaskGroup 3 タスク)

**判断**: `asyncio.TaskGroup` で物理 / 認知 / heartbeat を別タスクに分離する v1 案を
`/reimagine` で破棄し、`WorldRuntime.run()` 単一コルーチンで絶対時刻 due_at の
ヒープキューを回す v2 を採用。

**根拠**:
- **時間ドリフトなし**: `asyncio.sleep(1/30)` 30 Hz ループは 1 秒あたり数 ms の遅延を
  累積する。絶対時刻 `sleep_until(due_at)` 方式にすれば、前回遅延後も `due_at += period`
  で次の目標時刻が固定されるため、長時間実行 (M7 12 時間) でも周期性が崩れない。
  M10-11 の評価フレームワーク (Ripley K / Lomb-Scargle) の精度と直結する。
- **状態競合ゼロ**: 単一コルーチン設計により、`_agents` dict / `_envelopes` queue /
  `AgentRuntime.kinematics` が決して並行 mutation されない。ロック不要。
- **拡張容易**: M4 反省ループ・M7 永続化スナップショットを `_schedule(period, handler)`
  1 行で追加できる。TaskGroup 方式だと `create_task` の分岐を増やすため変更が大きい。

**根拠の参照元**: `design-comparison.md` §評価, `docs/architecture.md` §1 / §3

## D2: Voronoi 最近傍ゾーン (vs 矩形 AABB)

**判断**: 5 ゾーンを `ZONE_CENTERS` の代表点 1 個だけで表現し、
`locate_zone(x, y, z) = argmin_z ||(x,z) - center(z).xz||^2` の最近傍で一意分割する。
矩形 (AABB) + `ZoneNotFoundError` 例外パターンは不採用。

**根拠**:
- **境界ケース分岐ゼロ**: エージェントが世界の外に行っても最近傍ゾーンに自動吸着
  するため、壁や境界の if 文が消える。MASTER-PLAN R8 の「MVP は立方体 + 色マテリアルで
  許容、壁なし」前提と整合する。
- **調整が直感的**: ゾーンレイアウトを変えたい時、矩形 4 隅 (x_min/x_max/z_min/z_max) を
  動かすより代表点 1 個を動かす方が心理的コストが低い。
- **計算コスト**: O(5) の Euclidean 二乗距離、30Hz × 8 agent でも µs オーダで無視できる。

**トレードオフ**: 将来「入れない部屋」「狭い通路」を表現したくなった時は別機構が必要。
MVP 範囲では不要なので許容。

## D3: Clock ABC + `sleep_until(due_at)` (vs Protocol + `sleep(dt)`)

**判断**: クロック抽象は `abc.ABC` で `RealClock` / `ManualClock` の 2 実装。メソッドは
`monotonic()` と `sleep_until(due_at)` の 2 つに絞る。`typing.Protocol` は採用しない。

**根拠**:
- **絶対時刻 API**: anti-drift 設計のため `sleep_until(absolute)` が自然。`sleep(delta)` は
  スケジューラ側で `due_at - now` を引き算する必要があり、その計算時点で時間が進むと
  ドリフトが再発する。
- **ABC の isinstance 判定**: ログや debug 出力で「このランタイムは ManualClock」と
  判別したいケースに備える。Protocol では isinstance が必要になる都度 `runtime_checkable`
  を付けるノイズが増える。
- **ManualClock.advance(dt)** は `heapq` でソート済み waiters を一括解放する純同期メソッド。
  テストで `clock.advance(5.0)` → `await _pump(N)` のパターンが最小コードで書ける。

## D4: `asyncio.gather(return_exceptions=True)` 一元化 (code review HIGH #2 対応)

**判断**: `_step_one` 内で `except Exception` を catch せず、`asyncio.gather(return_exceptions=True)`
に例外処理を一任する。code review で指摘された二重例外ハンドリングを削除。

**根拠**:
- **二重ラップは冗長**: `_step_one` の try/except は `gather(return_exceptions=True)` が
  既に提供する契約を再実装しており、将来の保守者を混乱させる。
- **単一責任**: ログ出力は `_consume_result` に集約 (`isinstance(res, BaseException)` 分岐)。
- **例外種別の揃い**: `gather(return_exceptions=True)` は `CancelledError` を含む
  `BaseException` も結果リストに混ぜるため、`Exception` だけを catch する v1 版より
  堅牢。

## D5: ZoneTransitionEvent.from_zone は物理 tick 更新前に捕捉 (code review HIGH #1 対応)

**判断**: `_on_physics_tick` で `rt.state.position` を `model_copy` で更新する**前**に
`prev_zone = rt.state.position.zone` を捕捉しておき、`ZoneTransitionEvent.from_zone` に
渡す。

**根拠**:
- **initial 実装のバグ**: code review 前の実装では `model_copy` 後の
  `rt.state.position.zone` を `from_zone` に使っていたため、`from_zone == to_zone == new_zone`
  となり、遷移元情報が失われていた。
- **テストで再発防止**: `test_zone_crossing_enqueues_zone_transition_observation` で
  `transitions[0].from_zone is Zone.PERIPATOS` を明示的に assert することで回帰を防ぐ。

## D6: snap 時も `locate_zone` で zone 再計算 (code review MEDIUM #1 対応)

**判断**: `step_kinematics` が destination に snap する時、`dest.zone` をそのまま採用するのを
やめ、`locate_zone(dest.x, dest.y, dest.z)` で zone を再計算した Position を作る。

**根拠**:
- **Defense in depth**: `MoveMsg.target.zone` が呼び出し側で実座標と不整合に設定された
  場合 (例: LLM 出力のミス / persona YAML のタイプ)、以後の zone 判定が全て狂う。
  Voronoi 側で zone を正とすることで内部整合性を保つ。
- **interpolate 側 (line 82-86) と揃う**: 補間中の位置は既に `locate_zone` で再計算
  していた。snap のみ例外にする理由はない。

## D7: Unbounded `asyncio.Queue` + 2 面 API (vs bounded + back-pressure)

**判断**: `_envelopes: asyncio.Queue[ControlEnvelope]` を `maxsize=0` (unbounded) で作り、
T14 向けに `recv_envelope()` (blocking) と `drain_envelopes()` (sync drain) の 2 面 API を
提供する。

**根拠**:
- **MVP 規模で back-pressure 不要**: 5-8 agent × 30Hz × ~100B envelope = 毎秒 ~24 KB。
  T14 の WS 送信が数秒遅延しても memory blow-up の範疇にならない。
- **両 API 両立の低コスト**: unbounded Queue で両方提供できるため、T14 実装時に
  どちらを使うかを後で選べる。`maxsize=N` への差し替えは 1 行で可能、将来 back-pressure
  を足したくなった時の工事コストが軽い。

## D8: `_agents` の single-threaded 前提を docstring に明記 (code review MEDIUM #2 対応)

**判断**: `register_agent()` docstring に「Must be called before `run()` or from within
a handler on the same event-loop task」と明記。

**根拠**:
- **将来の誤用防止**: 別タスクから `register_agent` を呼ぶと `_agents` dict の mutation が
  scheduler の `for rt in self._agents.values()` と競合しうる。
- **ロック追加の代わりの文書化**: 正しいロックを入れるより「契約を明示する」方が単純で、
  MVP 範囲では十分。将来マルチタスク登録が必要になったら、その時にロックを導入する。

## D9: テストの pump 回数 = 時間進度と handler 数の積 + 余裕

**判断**: `_pump(1500)` のような高い yield 数を使うのは許容する (実行時間は 0.15s 以内)。
`_pump_until_stable` ヘルパも用意したが、単純な固定回数でも十分速いため併用。

**根拠**:
- **ManualClock のセマンティクス**: `advance(5.0)` で 5 秒進めると、5 × 30 Hz = 150
  物理 + 5 heartbeat = 155 イベントが due になる。スケジューラは 1 イベント ≈ 2-3
  `sleep(0)` yield で進むため、500-1500 yield が必要。
- **テスト時間は許容範囲**: test suite 全体 248 passed が 0.58s なので、高い pump 数でも
  実害なし。
- **可読性**: 「advance(5) の後に pump(1500)」は、advance の量と pump 量の大体の比率
  (10:3000) を一貫させれば読みやすい。`_pump_until_stable` は将来の最適化余地として残す。

# 設計案比較 — T13 world-tick-zones

## v1 (初回案) の要旨

`asyncio.TaskGroup` で **物理 / 認知 / heartbeat の 3 つのコルーチン** を並列に走らせ、
相互に独立した `asyncio.sleep(dt)` ループを回す。**ゾーンは矩形 AABB** の集合で表現し、
**`Clock` Protocol** で抽象化して本番/テスト切替。Envelope は
**bounded `asyncio.Queue` + back-pressure (`put` ブロック)** で T14 に受け渡し、
単純な `drain_envelopes()` も提供。認知 tick 内のエージェント step は逐次 (M7 まで gather 導入しない)。

## v2 (再生成案) の要旨

**単一コルーチンの heapq スケジューラ** で 30Hz / 10s / 1Hz の 3 周期を
絶対時刻イベントとして管理。各周期は `sleep_until(due_at)` で**時間ドリフト排除**。
**ゾーンは Voronoi 最近傍セントロイド**で、5 座標だけで全空間を分割し
`ZoneNotFoundError` を発生させない。認知 tick では
**`asyncio.gather(return_exceptions=True)` で N エージェントを同時並走**。
Clock は **ABC (RealClock / ManualClock)**。Envelope は **unbounded Queue**
(MVP 規模で back-pressure は不要と判断)、`recv_envelope()` と `drain_envelopes()` の 2 面。

## 主要な差異

| 観点 | v1 | v2 | 注釈 |
|---|---|---|---|
| **並行モデル** | TaskGroup 3 タスク | 単一コルーチン + heapq | v2 は「状態競合の余地をそもそも作らない」設計 |
| **時間精度** | `asyncio.sleep(dt)` で累積ドリフト | `sleep_until(abs)` でドリフト無 | 長時間シミュレーション (12h) で v1 は数秒〜数分ずれる可能性 |
| **認知 N 並列** | 逐次 (M7 まで直列) | `gather(return_exceptions=True)` で最初から並列 | 5-8 agent × LLM 2 秒の場合、v1 は 10-16 秒 / v2 は 2-3 秒 |
| **ゾーン判定** | 矩形 AABB + `ZoneNotFoundError` | Voronoi 最近傍 (例外なし) | v2 は壁・境界ケースの if 文ゼロ、世界外脱出の扱いも自動 |
| **Clock 抽象** | `typing.Protocol` | `abc.ABC` (RealClock / ManualClock) | v2 は isinstance 判定可・mypy strict で軽い |
| **Envelope 境界** | bounded Queue + back-pressure | unbounded + `recv`/`drain` 2 面 | v2 は T14 が async iter / drain のどちらも選べる |
| **新周期タスク追加** | TaskGroup に `create_task` 追加 | `schedule(period, handler)` 1 行 | M4 反省ループ / M7 永続化追加時に v2 が簡単 |
| **変更規模** | ~1120 行 (src 590 + test 530) | ~1095 行 (src 565 + test 530) | ほぼ同等 |
| **テスト決定論** | FakeClock + Protocol | ManualClock.advance() で時間ジャンプ | どちらも可。v2 の heapq は「次の due_at まで advance」で 1 tick 単位の再現が簡単 |
| **依存** | 標準ライブラリのみ | `heapq` / `abc` / `dataclasses.replace` | 両案とも GPL リスクなし |

## 評価

### v1 の長所
1. **マルチタスク分離が直感的**: 物理 / 認知 / heartbeat が別関数に完全に閉じており、
   1 つのタスクのバグが他を壊しにくい (独立した `while True` ループ)。
2. **back-pressure で暴走防止**: 万一 T14 の WS 送信が詰まった時に
   memory blow-up を未然に防げる (理論的な堅牢性)。
3. **既存コードからの飛躍が小さい**: asyncio.TaskGroup は T12 までの世界観の
   自然な延長。コードレビュアーにとっても読みやすい。

### v1 の短所
1. **時間ドリフト**: 30Hz の `asyncio.sleep(1/30)` は OS スケジューリング + await
   オーバヘッドで 1 秒あたり数 ms 遅れる。12h 実行すると物理 tick 回数が
   理想値から 0.5-2% ずれる。評価フレームワークの周期性測定 (§層 1 Ripley K
   / Lomb-Scargle periodogram) に影響する可能性。
2. **タスク間状態共有のロックが必要になる潜在性**: 物理 tick が kinematics を
   mutate している間に認知 tick が読み取ると race。現状 Python GIL で
   部分的に守られているが、dict の中身 mutation が同じ key で重なるとバグ源。
3. **back-pressure の MVP オーバーキル**: 5-8 agent × 30Hz × 100B envelope
   = 毎秒 24 KB。bounded Queue の複雑性 (`await put()` での cognition
   スタックブロック) の割に実効性が低い。
4. **認知の逐次処理が M7 まで残る**: 5 agent × LLM 2 秒 = 10 秒ブロック。
   10 秒周期の cognition tick が「ブロック時間 ≈ 周期」に近づくと次 tick を
   食いつぶす可能性。

### v2 の長所
1. **時間ドリフトなし**: 絶対時刻 due_at を維持するため、long-running で
   正確な周期性が出る。評価フレームワークとの親和性が高い。
2. **状態競合ゼロ**: 単一コルーチン設計により、agents dict / kinematics /
   envelope queue が決して並行 mutation されない。ロック不要。
3. **認知 N 並列を最初から**: `asyncio.gather` で 5-8 agent の LLM を同時発火。
   MVP から M7 まで性能スケール。
4. **Voronoi の簡潔性**: `ZoneNotFoundError` / AABB 境界チェック / y_range 判定が
   すべて消える。50 行は短くなる。エージェントが「世界の外」に行っても
   最近傍ゾーンに自動吸着するので壁を作らなくていい。
5. **拡張容易**: M4 反省ループ・M7 永続化スナップショットを `schedule()` 1 行で追加。
   既存のタスク分割を壊さない。
6. **決定論テスト**: `ManualClock.advance(dt)` 1 呼び出しで「その dt 区間で発火する
   すべてのハンドラ」が順序保証付きで完遂する。

### v2 の短所
1. **単一コルーチン故、handler が例外を握り潰すと loop が止まる**: try/except Exception を
   スケジューラ側に書く必要があり、そこで logger.exception 漏れがあると debug 困難。
   (v1 も handler 内部で吸収する必要はあるが、TaskGroup の CancelledError まわりの
   セマンティクスで救われる場合がある)
2. **heapq の seq tie-breaker 実装のバグリスク**: 同一 due_at の複数 event で
   FIFO を保つには order=True + seq フィールドが必要。これを忘れると
   unstable な実行順になりうる。
3. **Voronoi だと物理的な「入れない部屋」が作れない**: 将来 study 内部だけの
   狭いスペースや壁を表現したくなった時、Voronoi では表現不可。
   ただし MVP 範囲では不要 (MASTER-PLAN R8 に準拠)。
4. **unbounded queue の暴走リスク**: T14 実装が壊れた/遅延した場合に
   envelope が無限に溜まる。MVP で 30 分 × 数百 MB は許容範囲内だが
   production 検収時はモニタリングが必要。
5. **`gather(return_exceptions=True)` の受け流しパターンの認知的複雑性**:
   「戻り値が `CycleResult | BaseException`」という union を扱う
   `_consume_result` が必要。v1 の逐次 try/except より行数は減るが読解負荷は増す。

## 推奨案

**採用: v2 (再生成案)**

### 理由

1. **時間ドリフト解消は長期シミュレーションで効く**: M7 の 12 時間安定運転、
   M10-11 の評価フレームワーク (Ripley K / Lomb-Scargle periodogram)
   の精度に直結する。MVP 段階で正しく設計しておくと、後で評価データを
   取り直さなくて済む。
2. **状態競合の余地をそもそも作らない設計**: 単一コルーチンという制約が
   「ロック不要」「dict mutation 時の原子性不要」を構造で保証する。
   v1 の TaskGroup では「潜在的 race をコードレビューで見抜く」運用コストが
   かかり続ける。
3. **認知 N 並列を最初から持つ**: 5 agent から始まり M4 で 3 体同時対話、
   M7 で 5-8 体まで増える計画。認知の並列化は 3 体時点ですでに必要。
   v1 の「M7 まで逐次、そこで gather に書き換える」は 2 回のコスト
   (今書く + 後で書き換える)。v2 は 1 回。
4. **Voronoi が MVP に合う**: 壁や入室判定なしで 5 ゾーンを一意に分割できる
   シンプルさ。MASTER-PLAN R8 で「Godot は立方体 + 色マテリアルで許容」と
   されており、物理的な壁がない MVP の前提と matching する。
5. **拡張容易性 (M4/M7 視点)**: `schedule(period, handler)` 1 行で反省ループ・
   永続化スナップショットを追加できる設計は、今後の追加タスクで 3-5 回効く
   利点が見込める。
6. **v1 の長所は補完可能**: 「タスク分離の読みやすさ」はハンドラ関数を
   `_on_physics_tick` / `_on_cognition_tick` / `_on_heartbeat_tick` と
   分離することで同等に実現。「back-pressure による堅牢性」は T14 実装時に
   bounded queue への差し替えで対応可能 (v2 の unbounded は `asyncio.Queue` の
   デフォルトなので、後から `maxsize=N` に変更するのは 1 行)。

### v2 採用時の補強 (v1 のエッセンスを取り込む)

以下は v2 に吸収して design.md を微修正する:

- **ハンドラ例外隔離の明示**: `run()` のメインループで `try: await ev.handler()
  except Exception: logger.exception(...)` を明記 (v1 の long-lived task の
  isolation 思想を引き継ぐ)
- **Queue maxsize の将来差し替え余地**: docstring で「T14 実装時に
  maxsize を設定する余地を残す」と明記

これらは既に v2 design.md の本文で部分的に記載済みのため、Step 6 で
採用確定する際に末尾に履歴を追記するだけで良い。

### 採用プロセス履歴予定

- 初回案 (design-v1.md) と再生成案 (design.md = v2) を比較
- 採用: **v2**
- 根拠: 時間ドリフト排除・状態競合ゼロ・認知並列化・Voronoi の簡潔さ・
  拡張容易性の 5 点で v2 が優位。v1 のマルチタスク分離の読みやすさは
  v2 でもハンドラ関数分離で等価に実現できる。back-pressure は MVP で
  オーバーキル (T14 実装時に maxsize 設定に差し替え可能)。

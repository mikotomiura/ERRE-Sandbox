# 設計案比較 — m4-multi-agent-orchestrator

## v1 (初回案) の要旨

`bootstrap()` に if/else 分岐を入れ、`cfg.agents` が空なら従来の Kant 1 体を
直接 register、非空なら loop。`InMemoryDialogScheduler` は `src/erre_sandbox/world/`
に置き、`schedule_initiate` が envelope を **返す** だけで caller が put する
責任を持つ。WorldRuntime に inject は可能だが **自動発火は行わない** 保守路線
(テストと後続タスクが explicit に呼ぶ前提)。

## v2 (再生成案) の要旨

`BootConfig.__post_init__` で `agents` 空時に default 1-Kant spec を詰める
ことで、`bootstrap()` から分岐を追放し `for spec in cfg.agents:` 1 本道化。
`InMemoryDialogScheduler` は `src/erre_sandbox/integration/` に置き、
**`envelope_sink: Callable[[ControlEnvelope], None]` を内包** — admit したら
scheduler 自身が sink を呼ぶので caller に put 責任が残らない。WorldRuntime
の `_on_cognition_tick` 末尾で `scheduler.tick(world_tick, views)` を呼び、
proximity gate を自走させる (M4 live 検証で追加結線が不要に)。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| **bootstrap 分岐** | `if cfg.agents: loop else: Kant` | `__post_init__` で詰めて 1 本道 |
| **Scheduler 配置** | `world/dialog.py` | `integration/dialog.py` |
| **envelope 流し方** | caller が返り値を put | scheduler 自身が sink 経由で put |
| **自動発火** | なし (explicit only) | `_on_cognition_tick` 末尾で `.tick()` |
| **AgentView 抽出** | 未定義 (AgentRuntime 直渡し) | 明示的な NamedTuple projection |
| **Determinism** | RNG inject 未言及 | 明示的に RNG inject (テストで固定) |
| **live 検証の結線** | 追加実装必要 | そのまま走る (runtime が発火する) |
| **Protocol 違反リスク** | 低 | 低 (admission logic は Protocol 3 methods 準拠) |
| **test 本数** | unit 10 + smoke 1 | unit 15 + smoke 1 + CLI 1 + BootConfig 2 |
| **変更ファイル数** | 5 + 新 2 | 5 + 新 3 (live-checklist.md 追加) |
| **risk: double-put** | 高 (caller 経路で発生しうる) | 低 (sink 一本化) |
| **risk: M2 back-compat 壊す** | 低 (bootstrap 分岐で維持) | 低 (BootConfig デフォルト経由で維持) |

## 評価

### v1 の長所
- bootstrap 変更が分かりやすい (if/else が直球)
- scheduler の責務が狭い (return envelope のみ、副作用なし)
- テストが envelope 戻り値を assert しやすい

### v1 の短所
- caller が envelope put を忘れる / 重複 put する拡散リスク
- 自動発火なしだと "実装した" と "動いている" の乖離が大きい (live 検証時に
  追加配線が必要と判明する)
- scheduler を world/ に置くと cognition / world / gateway のどこからも
  距離があり、import 方向がねじれる可能性
- BootConfig が空 agents で意味が変わる (API の invariant が弱い)

### v2 の長所
- bootstrap が **分岐なしの 1 本道** で読みやすい・テストしやすい
- envelope sink 一本化で put 重複 / 忘却が構造的に発生しない
- `_on_cognition_tick` hook により live 検証で追加結線不要 (merge 直後に
  G-GEAR で起動すれば proximity 発火が動く)
- integration/ 層に住むことで multi-agent orchestration の住所が明確化
- AgentView projection で scheduler が AgentRuntime の内部構造を知らない

### v2 の短所
- `__post_init__` での frozen dataclass 書き換えは慣用句だが学習コストあり
- scheduler が副作用を持つ (sink 呼び出し) ので unit test で mock sink 必要
- RNG inject の extra param が増える

## 推奨案

**v2 を採用 (ハイブリッド要素なし)**。

### 根拠

1. **live 検証の "最後の 1 cm" を先に閉じる**  
   v1 は M4 #6 merge 後に「scheduler が動かない」と気付いてから追加 PR を
   作る必要がある可能性が高い。v2 は最初から end-to-end で動くように組み、
   G-GEAR での検証ステップを最小化する。これは MASTER-PLAN の "live 検証
   のコスト = 最大リスク" 原則と整合。

2. **envelope 経路の単一化**  
   M4 #4 で確立した "全 envelope は `runtime._envelopes` queue に集約" 原則
   を dialog でも貫く。v1 の return 経由は caller がこの原則を破る入口になる。

3. **bootstrap の読みやすさ**  
   M2 の bootstrap は既に長い (245 行)。ここに if/else で分岐を足すと可読性
   が落ちる。`__post_init__` で詰め切れば bootstrap 本体は短く保てる。

4. **AgentView projection の副産物**  
   AgentView は M5 の ERRE mode FSM や M9 の agent telemetry でも再利用でき
   る汎用的 projection。先行投資として価値が高い。

5. **Contract 尊重**  
   DialogScheduler Protocol (foundation #1 で凍結) を壊さず、extensions は
   Protocol 外の拡張メソッドとして追加する方針は v1/v2 共通だが、v2 のほう
   が Protocol メソッドの呼び出し場所が一箇所に集中してレビューしやすい。

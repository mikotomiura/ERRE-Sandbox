# Decisions — m4-multi-agent-orchestrator

## D1. `/reimagine` 適用
v1 (bootstrap if/else + world/ 配置 + return-based envelope + auto-fire なし)
→ v2 (`__post_init__` + integration/ 配置 + sink-based envelope +
`_on_cognition_tick` auto-fire) を採用。詳細 `design-comparison.md`。

## D2. BootConfig.__post_init__ で default を詰める
- **判断**: `BootConfig.agents` が空 tuple の場合、`__post_init__` が
  `(AgentSpec(kant, peripatos),)` を `object.__setattr__` 経由で詰める
- **理由**:
  1. `bootstrap()` 本体から if/else 分岐を排除、N-agent 一本道
  2. M2 back-compat (「引数なしで default 1-Kant walker」) は振る舞い
     レベルで保持、内部実装は M4 #1 契約 (空 tuple → 1-Kant fallback) を
     「config レベル fallback」として具体化
- **トレードオフ**: `frozen=True` dataclass の書き換えは慣用句だが
  学習コストあり。`object.__setattr__` には型チェッカが警告しない

## D3. DialogScheduler は integration/ 層に配置
- **判断**: `src/erre_sandbox/integration/dialog.py` に置く
- **理由**:
  1. scheduler の責務は multi-agent envelope routing (admission + sink)、
     これは integration 層 (gateway と同類) の住人
  2. world/ は 1 agent 物理、cognition/ は 1 agent 認知、dialog は
     N agent 間の契約管理なので層が違う
  3. dialog.py は schemas のみ import、integration の forbidden list
     (world / cognition / memory / inference / ui) に違反しない

## D4. envelope_sink をコンストラクタで inject、scheduler 自身が put
- **判断**: `InMemoryDialogScheduler(envelope_sink: Callable[[env], None])`
  を受け取り、admit / close した envelope を自身で sink 経由で流す
- **理由**:
  1. M4 #4 で確立した "全 envelope は `runtime._envelopes` queue に集約"
     原則を dialog にも継承
  2. caller が戻り値を put する方式は忘却 / 重複 put の拡散リスク
  3. Protocol の return 契約は維持しつつ (admit を binary に伝える)
     実際の delivery path は sink に一本化

## D5. dialog の cooldown は global tick ベース、per-agent counter ではない
- **判断**: `world_tick - last_close_tick[pair_key]` で cooldown を管理
- **理由**: reflection の cooldown は per-agent だが、dialog は **ペア**
  の context なので pair_key (`frozenset({a, b})`) で global tick との
  差分を取る方が自然。N² 空間の pair dict は M4 規模 (3 agent → 3 pair)
  で問題なし

## D6. Reflective zones = {peripatos, chashitsu, agora, garden}
- **判断**: study は dialog admission から除外、他 4 zone は許可
- **理由**: persona-erre skill / 文化設定で study は "私的 deep work 空間"、
  会話による割り込みは不適切。agora / garden / peripatos / chashitsu は
  会話が自然な場

## D7. AgentView projection (scheduler は AgentRuntime を知らない)
- **判断**: `AgentView = NamedTuple(agent_id, zone, tick)` を定義、
  WorldRuntime が `_agent_views()` で projection して scheduler に渡す
- **理由**:
  1. scheduler が kinematics / pending observations / persona / cognition
     cycle 内部を触らないことを型レベルで保証
  2. M5 で ERRE mode FSM が agent projection を拡張する際、NamedTuple に
     field 追加するだけでよい (Rust の extensible record と同等の設計)

## D8. RNG inject で auto-fire を決定化
- **判断**: `InMemoryDialogScheduler(rng: Random | None = None)`、None なら
  `Random()` (current time seed)
- **理由**: AUTO_FIRE_PROB_PER_TICK = 0.25 を厳密テストするため RNG を
  stub できるように。`r.random = lambda: 0.0` で強制 admit、0.99 で強制
  skip
- **トレードオフ**: rng を持ち回る手間が増えるが、deterministic test の
  価値 >> 手間

## D9. WorldRuntime の dialog hook 失敗を握り潰す
- **判断**: `_run_dialog_tick()` を try/except Exception + logger.exception
- **理由**: scheduler のバグが cognition tick loop を止めないように。
  dialog 自動発火は optional feature なので、壊れても 1-agent walker は
  動き続けるべき (cognition 原則と同じ)

## D10. DialogInitiateMsg に dialog_id を足さない (foundation 尊重)
- **判断**: `DialogInitiateMsg` のシェイプ (initiator / target / zone /
  tick のみ) は不変。dialog_id は scheduler 内部で allocate、
  `get_dialog_id(a, b)` で参照
- **理由**:
  1. M4 #1 で fixtures 全 10 件 + golden 3 件が凍結済、schema 変更の
     コスト大
  2. dialog_id が wire 上必要なのは `DialogTurnMsg` / `DialogCloseMsg`
     側で、こちらには含まれている。initiate は "intent only" 契約で
     問題ない

## D11. live 検証は別タスクで実施
- **判断**: 本 PR は unit + integration まで。G-GEAR live (3 avatar /
  60s / fps / dialog trace) は `.steering/20260420-m4-acceptance-live/`
  を別タスクで作る。本 PR の `live-checklist.md` に手順残置
- **理由**: MacBook では G-GEAR + Godot の両機連携が不可。本 PR を
  unit で閉じ、live は user が G-GEAR で走らせる

## D12. `--personas-dir` CLI option も追加
- **判断**: `--personas-dir personas` (default `personas`) を CLI に追加
- **理由**: fixtures ディレクトリを使うテスト、将来の `/etc/...` 配置を
  見据えて。既存 `BootConfig.personas_dir` と 1:1 対応

## D13. `_load_kant_persona` / `_build_kant_initial_state` を rename
- **判断**: `_load_persona_yaml(dir, persona_id)` /
  `_build_initial_state(spec, persona)` に rename (破壊的)
- **理由**: 1-Kant 固定でなくなったため旧名は実態と乖離。
  `_` prefix のため外部影響なし、test 側は全て書き換え済

## D14. Zone → 初期 ERRE mode マップの集中化
- **判断**: `_ZONE_TO_DEFAULT_ERRE_MODE: Final[dict[Zone, ERREModeName]]`
  を bootstrap.py に置き、全 5 zone を網羅 (peripatos → PERIPATETIC /
  chashitsu → CHASHITSU / study → DEEP_WORK / agora → SHALLOW /
  garden → PERIPATETIC)
- **理由**: 以前は Kant 固定で peripatos+PERIPATETIC だけ決め打ちだった
  が、M4 #6 で 3 agent が異なる zone に spawn するため全 5 zone を
  decision table 化
- **将来**: M5 の ERRE mode FSM が zone 遷移時の mode 変化を管理する際、
  この表を拡張して "zone 入出時の遷移規則" に昇格予定

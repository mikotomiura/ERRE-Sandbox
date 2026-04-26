# Pre-Plan Research — M8 Scaling Bottleneck Profiling

> 2026-04-26 MacBook で実施。`tasklist.md` の「準備」セクション 5 項目を Explore agent
> で網羅的に調査し、Plan mode + Opus + /reimagine で `design.md` の 3 metric 定義を
> 起こすときに必要な事実を集約。**コード変更ゼロ、Read-only**。
>
> Plan mode 開始時、本ファイルを最初に Read してから design.md を書く。

## 1. `integration/dialog.py` の pair enumeration

### 発見
- **位置**: `dialog.py:315-328` の `_iter_colocated_pairs` (tasklist の L292-305 は
  古い行番号)。`sorted_agents[i+1:]` で nested iteration → C(N,2) 爆発
- **N≤3 アサート**: `dialog.py:120` の `_last_close_tick` dict コメントで
  "Bounded by C(N, 2) for N agents — M4 targets N≤3 so this cannot grow beyond a few entries"
- **scheduler tick フロー**: `dialog.py:232-254` で `_iter_colocated_pairs(agents)` →
  各対について zone check → cooldown check → 確率 filter → auto-fire
  → tick 当たり判定回数が **O(N²)**
- **記録経路**: `record_turn()` (`dialog.py:175-203`) が `turn_sink` callback で
  sqlite `dialog_turns` table に永続化 (M8 L6-D1)。`_open[dialog_id].turns` list
  にも append

### 3 metric への含意
- **dialog pair saturation**: 4th agent 追加で +3 対 (3 → 6)。観測可能性の飽和は
  **対の数ではなく、各対が carry する情報エントロピー** (同 3 対の repeat firings
  vs 新対出現) に依存
- **observer fatigue**: scheduler `tick()` が cognition tick (~10s) で実行。
  N=3 なら 3 pair check/tick、N=4 なら 6 pair check/tick。UI dialog bubble 表示
  負荷が倍加
- **zone 滞留**: pair enumeration は **zone 一致が前提**。zone spatial entropy が
  低いと常に C(N,2) 火の手 → zone transition 頻度と zone 別 dwell time の Gini
  係数で測定可

### Plan mode で Q&A すべき設計判断
1. "dialog pair saturation" は (a) 同時開放 dialog 数か / (b) 24h window の unique
   pair か / (c) per-pair turn count entropy か → decisions.md で明示必須
2. 閾値超過の sign signal: zone transition 頻度? dialog initiate rate? log に
   既に存在する signal か?

## 2. `world/tick.py` の並列 tick 実装

### 発見
- **asyncio.gather 位置**: `tick.py:836-841` で cognition tick の per-agent
  `_step_one`、`tick.py:939` で `_drive_dialog_turns`。両方 `return_exceptions=True`
- **tick 周期** (`tick.py:280-282`):
  - `DEFAULT_COGNITION_PERIOD_S` = 10.0 秒 (per-agent)
  - `DEFAULT_PHYSICS_HZ` = 30.0 Hz (world clock tick)
  - `DEFAULT_HEARTBEAT_PERIOD_S` = 1.0 秒
- **dialog scheduler tick**: cognition tick の直後 `_run_dialog_tick`
  (`tick.py:846-870`)
- **agent 数依存性**: `_step_one` は全 agent に並列実行 (`async for rt in runtimes`)。
  semaphore なし → N=4 で `OLLAMA_NUM_PARALLEL=4` に同期、N≥5 で queue 待ち
- **WorldRuntime メソッド** (抜粋):
  - `apply_affinity_delta()` L455- (M8 L6-D1)
  - `layout_snapshot()` L512-
  - `transition_to_q_and_a()` / `transition_to_evaluation()` L377-411 (M8 D3 FSM)
  - `register_agent()` L415-、`inject_observation()` L430-

### 3 metric への含意
- **observer fatigue**: cognition 10s 周期だが dialog は per-tick。N=3 で
  ~7.5 dialog/min、N=4 で ~15 dialog/min。UI が frame 毎 update なら widget
  refresh overhead 倍加
- **zone 滞留**: physics tick (30Hz) が agent position update。`ZoneTransitionEvent`
  は zone 境界 cross moment に emit。滞留時間 Gini = `world_tick - zone_entry_tick`
  histogram から計算
- **dialog pair saturation**: N=4 で 4 agent 同時 LLM token 生成 → VRAM linear
  increase → turn generation latency spike → dialog timeout (`TIMEOUT_TICKS=6`)
  increase

### Plan mode で Q&A すべき設計判断
1. 3 metric の計測間隔: 10s cognition tick? 1s heartbeat? per-turn? log の
   どこから timestamp を引くか明示
2. zone "flat 化" の定義: Gini < 0.5? entropy < log(n_zones)? 閾値案 3 本確定

## 3. L6 ADR D2 の全文 (採用方針 + A2-f / A3-d 交叉)

### 発見
`.steering/20260424-steering-scaling-lora/decisions.md` D2 (本リポジトリ既読):

- **採用方針**: "3 維持 + scaling トリガー metric の定義" — **量先行ではなく
  metric-first**
- **3 metric 候補** (本 spike 受け入れ条件 source):
  1. dialog pair saturation
  2. observer fatigue
  3. zone 滞留分布の flat 化
- **A2-f との交叉**: "user を 4 体目扱い (D3 と交叉)" → D3 (`session_phase` model)
  で autonomous run と Q&A epoch を分離、metric count から **user 発話除外**
- **D2 は M8 spike 単位で 1 つ存在**: 本 `m8-scaling-bottleneck-profiling` 自身が
  D2 の M8 precondition

### 3 metric への含意
- 量先行ではなく **観測限界を metric 化して closure conditions に** という
  パラダイム。観測者の認知資源 (UI 帯域 / 注視持続) を metric 化する点が新規

### Plan mode で Q&A すべき設計判断
1. metric threshold の candidate 値: decisions.md には「3 本提案」のみで値未記載
   (例: saturation > 0.85? fatigue > 0.7? Gini < 0.3?)
2. D3 Q&A epoch との結合: user interaction 時の対話を metric に include/exclude
   する場合分けの明示

## 4. architecture-rules + llm-inference Skill

### architecture-rules
- **レイヤー依存方向**: `schemas.py` ← すべてが参照。inference/memory は schemas
  のみ。cognition は inference/memory/schemas/erre。world は cognition/schemas のみ
- **dialog.py の N 依存解消**: architecture-rules には **explicit な policy なし**。
  L138 フロー図では dialog scheduler は integration/ (world/cognition/ui の上位)
- **`_iter_colocated_pairs` の O(N²)**: 「削除」ではなく「M9 で parameterize」が
  L121-123 コメントの方向 (LRU dict / stale prune)。**M8 spike では解決対象外**
  (本 spike は判定層のみ追加)

### llm-inference
- **`OLLAMA_NUM_PARALLEL=4`**: L45 で明示。N≤4 agents で待機なし、N≥5 で逐次化
- **VRAM 予算詳細** (L66-76):
  ```
  ベースモデル重み (Q5_K_M)      ~5.5 GB
  KV キャッシュ (q8_0, 8並列)     ~5-6 GB
  RadixAttention 共有 prefix       -30% (KV)
  CUDA context                    ~2 GB
  ─────────────────────────────────────
  合計                            ~13 GB / 16 GB
  ```
  → N=4 まで「余裕」の根拠は VRAM 75%。N>4 で KV cache のみで budget 超過

### 3 metric への含意
- **observer fatigue ←→ VRAM budget**: N=4 が cognition tick 並列 gather 上限。
  N=5+ で Ollama token generation queueing → UI heartbeat の token arrival
  latency 観察 → fatigue は **compute resource constraint の downstream
  manifestation**
- **dialog pair saturation ←→ architecture capacity**: C(N,2) CPU cost は無視可、
  各 pair の turn generation latency が N linear → dialog open lifetime extend →
  timeout reap rate 低下 → stale dialog accumulation

### Plan mode で Q&A すべき設計判断
1. N=4 を "余裕ある上限" として assert できるか: 次 live run で VRAM peak +
   Ollama token latency profile し、数値ベース "N=4 max / N=5 でqueueing start" を
   decisions に記録
2. fatigue の operationalization: Ollama response latency 分布? UI frame drop?
   dialog turn response time の percentile?

## 5. m8-episodic-log-pipeline (PR #88 merge 済) の log 構造

### 発見
- **PR #88 merge 済** (2026-04-24)。scope を `dialog_turn` のみに縮小 (v2)
- **log persistence**:
  - `MemoryStore.add_dialog_turn_sync()` (`store.py:830-834`): turn を sqlite
    `dialog_turns` table に insert
  - `dialog.py:175-203` の `record_turn()` で `turn_sink` callback 発火
- **`iter_dialog_turns` 現 signature** (`store.py:836-873`):
  ```python
  def iter_dialog_turns(
      self,
      *,
      persona: str | None = None,
      since: datetime | None = None,
  ) -> Iterator[dict[str, object]]:
  ```
  → **R3 H3 で指摘された "全件 Python ロード filter" 問題**: `since` 引数あるが
  `limit` 無し、cognition cycle の `_fetch_recent_peer_turns` (R3 H3) は
  `list(self._store.iter_dialog_turns())` で全件ロード後 Python filter
- **envelope schema** (`schemas.py:858-871`):
  - DialogTurnMsg: dialog_id / turn_index / speaker / addressee / utterance /
    tick / timestamp
  - ReasoningTraceMsg / ReflectionEventMsg は v2 で削除
- **3 metric で使う field**:
  - self_repetition_rate: speaker_persona_id + utterance (trigram jaccard)
  - cross_persona_echo_rate: speaker_persona_id + utterance across dialogs
  - bias_fired_rate: 別 `bias_events` table (baseline-quality-metric spike)
- **`MemoryEntry(kind=DIALOG)`**: sqlite schema には `dialog_turns` table
  (sqlite-only、YAML schema には記載なし)

### 3 metric への含意
- **dialog pair saturation**: `SELECT COUNT(DISTINCT dialog_id) / (N*(N-1)/2) FROM
  dialog_turns WHERE created_at >= <window>` で飽和度。**historical turn density**
  で測定 (live open count ではなく)
- **observer fatigue**: `SELECT COUNT(*) FROM dialog_turns WHERE turn_index >
  budget/2 GROUP BY dialog_id` で予算内完結 dialog 率。turn count 分布の tail が
  fat なら fatigue sign
- **zone 滞留**: `dialog_turns` に zone column **無し**。zone info は別に
  agent_snapshot を query するか、turn 生成時に agent.position を denormalize 必要

### Plan mode で Q&A すべき設計判断
1. zone 滞留の log source: dialog_turns に zone 無し → zone transition event を
   別 query するか、agent position snapshot を per-turn で persist すべきか?
   (本 spike scope か別 spike か明示)
2. metric 計算の time window: 最後の 24h? entire run? N=3 3-5 run のうち、
   metric を per-run average か run 横断 aggregate か → run 定義 (duration / N)
   明示

## Plan mode で /reimagine が必要な 3 軸

### 軸 1: 3 metric の operationalization
現在 D2 / requirement.md は概念レベル (saturation / fatigue / Gini)。**数式なし**。

**/reimagine action**: 3 本の compute function を pseudocode で decisions.md に記載。
入力: (dialog_turns rows / agent positions timeline / bias_events)。出力: float。例:

```
saturation = unique_pairs_in_window / max_possible_pairs(N)
fatigue = mean(turn_count per dialog) / dialog_turn_budget
zone_gini = gini(hours_per_zone per agent)
```

### 軸 2: 閾値候補の推定
baseline-quality-metric spike (M8 D1 後半) との data dependency。

**/reimagine action** (要件):
1. M8 phase 1 (本 spike の前行程) で N=3 live 3-5 runs を G-GEAR で実施
2. 各 run で 3 metric compute → mean / variance / 5th-95th percentile
3. threshold candidate: `(mean + 1.5×σ)` を各 metric に apply → decisions に記録
4. M9 go/no-go: "いずれかの metric が threshold exceed したら +1 persona を起票"

### 軸 3: D3 (session_phase model) との metric scope 分離
D2 採用 ("3 維持 + metric-first") は **autonomous run に対する判定**。D3 で
Q&A epoch を後付けする場合、user interaction が metric に reflect されるか。

**/reimagine action**:
1. 3 metric は `session_phase == AUTONOMOUS` 期間のみ計算
2. `Q_AND_A` epoch の dialog_turns は metric 計算から **除外**
3. decisions.md に "D3 boundary: autonomous metric vs Q&A ground truth" 1 段落
4. M8 phase 1 live run は全て `autonomous_only` (session_phase 固定) で確認

## Plan mode 開始時の確認項目 (Opus + /reimagine)

1. ✓ `design.md` § 1-4 の factual snapshot を confirm (新規 base model / VRAM
   変更がないか)
2. ✓ `decisions.md` の 3 ADR が 5 節 (現状 / 選択肢 / 採用 / 根拠 / 次アクション)
   構造を hold
3. ✓ 3 metric を **pseudocode with field names** で明示 (「観察可能性」から逆算)
4. ✓ 閾値案 3 本の computation root を decisions に attach (phase 1 live data
   依存性明記)
5. ✓ D3 との metric scope boundary を 1 段落追加 (autonomous vs Q&A 計算分離)

## 関連リンク

- 親 ADR: `.steering/20260424-steering-scaling-lora/decisions.md` D2
- 上流 spike (merge 済): `.steering/20260425-m8-episodic-log-pipeline/`
- 関連 Skill: `.claude/skills/architecture-rules/SKILL.md`、
  `.claude/skills/llm-inference/SKILL.md`
- 参考実装: `src/erre_sandbox/integration/dialog.py:315-328` (pair enumeration)、
  `src/erre_sandbox/world/tick.py:836-841` (cognition gather)、
  `src/erre_sandbox/memory/store.py:836-873` (iter_dialog_turns)

# 技術設計書

## 1. アーキテクチャ概要

### 現状実装スナップショット (last verified 2026-04-28)

> 本節は実装と一致している事実のみを記す。未実装・将来計画は §1 全体図と §2 表で
> ``[planned]`` ラベル付きで区別する。docs drift を避けるため、main の HEAD が動いた
> 時点で本節の verified 日付を更新する運用とする (codex addendum D5 + 「現状 snapshot」
> 提案による)。

- **G-GEAR OS**: Windows native (旧 docs の Linux / Win+WSL2 表記は研究計画段階の想定。実環境は Win native)
- **推論 (実)**: Ollama 上の `qwen3:8b` (GGUF Q5_K_M, ~5.2GB)。SGLang は M7 移行検討、vLLM は M9 (LoRA) 計画
- **埋め込み (実)**: `nomic-embed-text` (768d) — `src/erre_sandbox/memory/embedding.py:43-44` で `DEFAULT_MODEL` / `DEFAULT_DIM` 定義
- **WebSocket route (実)**: `/ws/observe` — `src/erre_sandbox/integration/gateway.py:732` で `app.add_api_websocket_route`。`/stream` は記録上の旧 path 案で実装されていない
- **Godot (実)**: 4.6.x (MIT)。`/opt/homebrew/bin/godot` 4.6.2.stable.official で headless boot 済 (PR #111 F4 検証)
- **Contracts レイヤー (実)**: `src/erre_sandbox/contracts/` (PR #111 で導入、F5)。`schemas.py` と並ぶ ui-allowable boundary

### 全体図 (現状 + planned 混在表記)

```
┌─── G-GEAR (Windows native, RTX 5060 Ti 16GB) ─────────────────────┐
│ [Inference Layer]                                                   │
│   Ollama (現状) / SGLang (M7+ 計画) / vLLM (M9+ LoRA)              │
│   base model: qwen3:8b (GGUF Q5_K_M)                               │
│   RadixAttention × 3 persona × prefix KV 共有 [planned: SGLang 移行で]│
│   (将来) LoRA per persona via vLLM --enable-lora                    │
│                                                                     │
│ [Simulation Layer]                                                  │
│   asyncio tick loop @ 30Hz world physics, 0.1Hz agent cognition    │
│   PIANO モジュール (memory, social, goal, action, speech)           │
│                                                                     │
│ [Memory Layer]                                                      │
│   sqlite-vec (.db 単一ファイル, MIT)                                │
│   + nomic-embed-text (768d) [現状] / Ruri-v3-30m [候補]            │
│   Per-agent スコープ + shared world スコープ                        │
│                                                                     │
│ [Contracts Layer] (2026-04-28 codex F5)                             │
│   Pydantic config models (M2_THRESHOLDS 等)                         │
│   ui / integration / evidence など複数層が schemas.py と並んで参照  │
│                                                                     │
│ [Gateway]                                                           │
│   FastAPI + uvicorn + websockets                                    │
│   ws://g-gear.local:8000/ws/observe                                 │
└─────────────────────────────────────────────────────────────────────┘
                          ↕ WebSocket (JSON / msgpack)
┌─── MacBook Air M4 (macOS, arm64) ──────────────────────────────────┐
│ [Orchestrator]                                                      │
│   Python 3.11 + asyncio client                                      │
│   ERRE DSL interpreter (shu/ha/ri, peripatos, chashitsu FSM)       │
│                                                                     │
│ [Viz]                                                               │
│   Godot 4.6 (MIT) 3D viewer                                         │
│   Streamlit / FastAPI + HTMX dashboard [planned]                    │
│                                                                     │
│ [Research Tools]                                                    │
│   Jupyter notebooks (replay, metric computation)                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 設計思想
- 特定のアーキテクチャパターン (Clean Architecture 等) には縛られない
- 必要に応じて改善し、破壊と再構築を恐れない
- 判断基準はシンプルさとコストゼロ

## 2. 技術スタック

| レイヤー | 技術 | バージョン | 選定理由 |
|---|---|---|---|
| 言語 | Python | 3.11 | asyncio 成熟、LLM エコシステム最大 |
| パッケージ管理 | uv (Astral) | 最新 | env・lock・Python 管理を一元化、MIT/Apache |
| Lint/Format | ruff | 最新 | lint + format 一元化、MIT |
| テスト | pytest + pytest-asyncio | 最新 | 非同期テスト対応 |
| Web フレームワーク | FastAPI + uvicorn | 最新 | 高速、Pydantic ネイティブ、WebSocket 対応 |
| スキーマ検証 | Pydantic v2 | 最新 | AgentState 等の型安全な定義 |
| LLM 推論 (本番) | SGLang | 最新 | RadixAttention でマルチエージェント最高スループット |
| LLM 推論 (開発) | Ollama | 最新 | 簡便運用、MIT |
| LLM 推論 (将来) | vLLM | 最新 | LoRA 動的切替 (--enable-lora) |
| ベースモデル | Qwen3-8B / Llama-3.1-Swallow-8B | Q5_K_M | 16GB VRAM に収まる日本語強モデル |
| ベクトル DB | sqlite-vec | 最新 | 単一ファイル、~500MB RAM、MIT |
| 埋め込み (現状) | nomic-embed-text | 768d | Ollama 経由で実装済 (`memory/embedding.py:43-44`)。日本語精度を要する場合は Ruri-v3-30m / multilingual-e5-small が候補 [planned]|
| 3D エンジン | Godot 4.6 | 4.6.2 | MIT、NavMesh・Skeletal animation 完備 (旧 docs の 4.4 表記を実態に更新) |
| ダッシュボード | Streamlit / FastAPI + HTMX | [planned] | ブラウザから直接可視化、現状は ui/dashboard/ 内 server-side aggregation のみ実装 |
| 研究ツール | Jupyter | 最新 | リプレイ・指標計算 |
| ドキュメント | MkDocs Material + mkdocstrings | 最新 | JA/EN 併記対応 |
| CI | GitHub Actions + pre-commit | 最新 | `.github/workflows/ci.yml` で `uv sync --frozen --all-groups` → ruff check / ruff format --check / mypy src / pytest -m "not godot" を lint / typecheck / test の 3 並列 jobs で実行。`.pre-commit-config.yaml` で commit 時にも ruff を自動実行 (uv.lock 固定の SSoT 構成) |

## 3. レイヤー構成

### Inference Layer (G-GEAR)
- **責務**: LLM 推論の実行、ペルソナ切り替え
- **主要コンポーネント**:
  - SGLang server: RadixAttention で共有 prefix KV を再利用
  - Ollama adapter: 開発時の簡便な推論バックエンド
  - ペルソナ管理: インコンテキスト (Phase 1) → LoRA (Phase 2)
- **設定パラメータ**: `OLLAMA_NUM_PARALLEL=4`, `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`

### Simulation Layer (G-GEAR)
- **責務**: ワールド物理、エージェント認知サイクルの実行
- **主要コンポーネント**:
  - asyncio tick loop: 30Hz (物理) / 0.1Hz (認知)
  - PIANO モジュール: memory, social, goal, action, speech の5並列認知モジュール
  - CoALA 認知サイクル: Observe → Appraise → Update State → Retrieve → Plan → Act → Speak → Reflect?
    (M4: Reflect 工程は `Reflector` collaborator に委譲、policy で発火)
  - ERRE モード FSM: peripatetic / chashitsu / zazen / shu_kata / ha_deviate / ri_create / deep_work / shallow

### Memory Layer (G-GEAR)
- **責務**: エージェント記憶の永続化と検索
- **主要コンポーネント**:
  - sqlite-vec: ベクトル埋め込み格納
  - 4種記憶: Episodic / Semantic / Procedural / Relational
  - 二層スコープ: per-agent (top-8) + world (top-3)
  - 減衰関数: `strength = importance * exp(-λ*days) * (1 + recall_count*0.2)`

### Evidence Layer (G-GEAR, post-hoc)
- **責務**: 永続化済み run データから観測 metric を pure-function で計算し、
  M9 比較や scaling トリガー判定に使う JSON / TSV を出力する
- **主要コンポーネント**:
  - `evidence/metrics.py` (M8 baseline quality): self_repetition_rate /
    cross_persona_echo_rate / bias_fired_rate。CLI: `erre-sandbox baseline-metrics`
  - `evidence/scaling_metrics.py` (M8 scaling spike, L6 ADR D2 precondition):
    pair_information_gain (bits/turn) / late_turn_fraction (ratio) /
    zone_kl_from_uniform (bits)。CLI: `erre-sandbox scaling-metrics`
- **observability-triggered scaling** (L6 ADR D2): 量先行 (4th persona を
  入れて困るか見る) を捨て、metric が解析的上限の % を割った瞬間に M9 +1
  persona 起票を判断する。閾値は σ-based heuristic ではなく `log2(C(N,2))`
  / `log2(n_zones)` の % で表現することで N に依存しない次元無し閾値とする
  (decisions.md D4 参照)。`var/scaling_alert.log` に違反時 1 行 TSV を append
- **入力**: sqlite `dialog_turns` (M1/M2) + 任意の probe NDJSON journal (M3)。
  `--journal` 省略時は M3 = null で graceful degradation
- **依存方向**: schemas / memory / cognition (constants only)。world / integration /
  ui には依存しない

### Gateway (G-GEAR)
- **責務**: MacBook 側との通信
- **主要コンポーネント**:
  - FastAPI + uvicorn + websockets (BSD-3)
  - ControlEnvelope スキーマ + kind フィールドでメッセージ多重化
  - Pydantic v2 によるスキーマ検証
- **M4 multi-agent routing** (`schema_version=0.2.0-m4`):
  - `_SERVER_CAPABILITIES` は 10 kinds (M2 7 種 + `dialog_initiate` / `dialog_turn` / `dialog_close`)
  - 接続時に `/ws/observe?subscribe=<agents>` でクライアントが購読対象を申告できる。未指定 / 空 / `*` は broadcast = 既存 M2 挙動。カンマ区切りで `persona_id` 複数指定可能、スキーマは無変更 (URL レイヤーで表現)
  - `Registry` は session ごとに `frozenset[str] | None` を保持し、`_envelope_target_agents(env)` で算出した envelope の routing 対象と突合してフィルタ。グローバル envelope (`world_tick` / `error` / `dialog_close` / server `handshake`) は購読に関係なく全 session 配信
  - routing マトリクス: agent_update / speech / move / animation → 単一 agent_id / dialog_initiate → (initiator, target) / dialog_turn → (speaker, addressee) / dialog_close → broadcast (participants を gateway で追跡しない設計判断、UI cleanup 用)
  - DoS 対策: `MAX_SUBSCRIBE_RAW_LENGTH` / `MAX_SUBSCRIBE_ITEMS=32` / `MAX_SUBSCRIBE_ID_LENGTH=64` / slug 正規表現 (`[A-Za-z0-9_-]+`) により制御文字・ログインジェクション・パス区切りを拒否
- **起動方式**:
  - **Production (MVP 以降)**: `python -m erre_sandbox` (または `erre-sandbox` コマンド)。
    `src/erre_sandbox/bootstrap.py::bootstrap()` が `MemoryStore` + `EmbeddingClient` +
    `OllamaChatClient` + `CognitionCycle` + `WorldRuntime` を構築し、
    `make_app(runtime=world_runtime)` で gateway を inject して uvicorn と対等 supervise する
  - **Debug-only**: `python -m erre_sandbox.integration.gateway` 単体起動は uvicorn factory
    mode で `_NullRuntime` を注入する。`recv_envelope()` は永久 sleep するため envelope は
    **ゼロ件** 配信 — `/health` / WS コネクション契約の検証用途のみ。production では使わない
  - `/health` の `active_sessions` counter は MacBook 側から 1Hz で probe して Godot 接続の silent failure を検出する
    (runbook: `.steering/20260419-m2-acceptance/session-counter-runbook.md`)
- **Inference エンドポイント解釈 (MVP 段階)**:
  - MVP M2 では独立した `inference/server.py` を立てず、**gateway 8000 番を通じて
    cognition 結果が WS envelope 経由で配信される** pragmatic 運用
  - MASTER-PLAN §4.4 #1「inference server listen」はこの gateway 配信を指す
  - M7 `inference-sglang-migration` で推論 (SGLang) と gateway を分離する設計へ移行予定

### Orchestrator (MacBook Air M4)
- **責務**: シミュレーション制御、ERRE DSL 解釈
- **主要コンポーネント**:
  - asyncio WebSocket client
  - ERRE DSL interpreter: shu/ha/ri、peripatos、chashitsu の状態機械

### Composition Root (G-GEAR, `bootstrap.py` + `__main__.py`)
- **責務**: N-agent オーケストレータ構築。M4 #6 `m4-multi-agent-orchestrator` で multi-agent 化
- **主要コンポーネント**:
  - `BootConfig.__post_init__`: `agents` 空時に `(AgentSpec(kant, peripatos),)` の 1 本道 default を詰め、`bootstrap()` 本体から分岐を追放
  - `_load_persona_yaml(dir, persona_id)` + `_build_initial_state(spec, persona)` で persona YAML → AgentState を生成。zone → ERREMode の default マップは `erre_sandbox.erre.ZONE_TO_DEFAULT_ERRE_MODE` (M5 `m5-erre-mode-fsm` で `erre/` パッケージへ移動)。runtime 遷移は `DefaultERREModePolicy` (同 package、後続の `m5-world-zone-triggers` で wire)
  - `CLI --personas kant,nietzsche,rikyu`: 各 persona の `preferred_zones[0]` を initial_zone に採用
  - `InMemoryDialogScheduler` (integration 層) を構築、`envelope_sink=runtime.inject_envelope` で配線
  - `WorldRuntime.attach_dialog_scheduler(scheduler)` で scheduler を runtime に bind
  - **M5 orchestrator-integration** (`schema_version=0.3.0-m5`):
    - `DefaultERREModePolicy()` を instantiate し `CognitionCycle(erre_policy=...)` に
      渡すことで ERRE mode FSM を活性化
    - `_load_persona_registry(cfg)` で `{persona_id: PersonaSpec}` を構築し、
      `OllamaDialogTurnGenerator(llm, personas=registry)` に注入。
      `WorldRuntime.attach_dialog_generator(generator)` で wire
    - 過渡期 rollback 用に用意した `--disable-erre-fsm` / `--disable-dialog-turn` /
      `--disable-mode-sampling` flag + `bootstrap._ZERO_MODE_DELTAS` は
      `v0.3.0-m5` 付与後に `m5-cleanup-rollback-flags` で除去済
      (`CognitionCycle.erre_sampling_deltas` DI スロットのみテスト分離性のため残置)

### Viz (MacBook Air M4)
- **責務**: 3D 描画、ダッシュボード
- **主要コンポーネント**:
  - Godot 4.4: 3D ビューア、スキンメッシュアバター
  - Streamlit / HTMX: Memory Stream・AgentState・対話ログのタイムライン

## 4. 主要コンポーネント

### AgentState (Pydantic v2 スキーマ)
- **責務**: エージェントの全状態を単一オブジェクトで管理
- **構成**: Biography / Traits (Big Five + wabi, ma_sense, shuhari_stage) / Physical (fatigue, focus, stress, hunger, location) / Emotion (Russell circumplex + Plutchik + OCC) / ERREMode / Relationship / goals
- **インターフェース**: `dump_for_prompt()` で LLM コンテキスト用に文字列化
- **永続化**: SQLite `agent_states` テーブル (JSON カラム)、毎 tick スナップショット

### Memory Stream
- **責務**: Park et al. (2023) 式の記憶ストリーム + ERRE 拡張
- **依存先**: sqlite-vec, 埋め込みモデル
- **インターフェース**: `add(observation, importance)`, `retrieve(query, k)`, `reflect(threshold)`
- **ERRE 拡張**: peripatos/chashitsu 入室時に閾値未満でも自由連想型内省を発火
- **M4 semantic layer** (`schema_version=0.2.0-m4`):
  - `semantic_memory` テーブルに `origin_reflection_id TEXT` 列を追加 (nullable)、起動時に `MemoryStore.create_schema()` が既存 DB へ idempotent に `ALTER TABLE ADD COLUMN` を適用
  - `MemoryStore.upsert_semantic(record: SemanticMemoryRecord)` — 同 id で idempotent 置換。embedding 空許容 (vec0 には書かない、recall 不可にする)
  - `MemoryStore.recall_semantic(agent_id, query_embedding, *, k) -> list[(SemanticMemoryRecord, distance)]` — agent スコープ KNN、L2 距離昇順
  - reflection → semantic 経路: cognition cycle が `ReflectionEvent` から `SemanticMemoryRecord` を組み立て `upsert_semantic` を呼ぶ (本体は `m4-cognition-reflection` タスクで実装)

### ControlEnvelope
- **責務**: G-GEAR ↔ MacBook 間の通信プロトコル
- **構成**: `kind` フィールドでメッセージ種別を識別
- **送信データ**: `{agent_id, position, rotation, animation, speech_bubble}` (30Hz)
- **M4 拡張** (`schema_version=0.2.0-m4`): `dialog_initiate` / `dialog_turn` / `dialog_close` variant を追加。3 体間対話の開始・1 ターン・終了を ControlEnvelope 上で運ぶ。`DialogScheduler` (schemas.py §7.5 Protocol) が具象実装のインタフェース
- **M4 dialog scheduler** (`integration/dialog.py`, `m4-multi-agent-orchestrator`):
  - `InMemoryDialogScheduler` が Protocol の具象実装。admission control + cooldown + timeout close を in-memory で管理
  - `envelope_sink: Callable[[ControlEnvelope], None]` を内包し admit / close 時に自身で sink 経由 envelope を流す (caller に put 責任を残さない)
  - `tick(world_tick, agents: Sequence[AgentView])` が proximity-based auto-fire を駆動: 同 reflective zone (peripatos/chashitsu/agora/garden) に 2+ agent + cooldown 満了 + RNG < AUTO_FIRE_PROB_PER_TICK (0.25) で `schedule_initiate` を内部実行
  - `WorldRuntime._on_cognition_tick` 末尾で `_run_dialog_tick()` が scheduler に AgentView projection を渡して回す。RNG は inject 可能 (テストで固定)
  - `AgentView = NamedTuple(agent_id, zone, tick)` のみ渡すので scheduler は AgentRuntime の内部構造を知らない
- **M5 dialog turn driver** (`world/tick.py::_drive_dialog_turns`, `m5-orchestrator-integration`):
  - `WorldRuntime` が `_run_dialog_tick()` の直後に `await self._drive_dialog_turns(world_tick)` を呼ぶ (`enable_dialog_turn=True` 時のみ)
  - `scheduler.iter_open_dialogs()` で open dialog を列挙 (Protocol に追加、orchestration 専用)。各 dialog ごとに:
    1. `transcript = scheduler.transcript_of(did)` で `turn_index = len(transcript)` 導出
    2. speaker alternation: `turn_index % 2 == 0` => initiator、else target
    3. `turn_index >= speaker.cognitive.dialog_turn_budget` で `close_dialog(reason="exhausted")`
    4. 以外なら `generator.generate_turn(...)` を `asyncio.gather(return_exceptions=True)` で並列実行
    5. 返った `DialogTurnMsg` を `scheduler.record_turn + runtime.inject_envelope` で emit / `None` は timeout 経路に任せる

### M4 Foundation Primitives (`schema_version=0.2.0-m4`)
- **`AgentSpec`** (schemas.py §3): bootstrap 時の minimal agent 宣言 (`persona_id` + `initial_zone`)。`BootConfig.agents: tuple[AgentSpec, ...]` で N 体起動に拡張する
- **`ReflectionEvent`** (schemas.py §6): cognition cycle が発火する reflection 1 回分のスナップショット。発火条件の決定は `m4-cognition-reflection` で
- **`SemanticMemoryRecord`** (schemas.py §6): reflection から蒸留された長期意味記憶 1 行。sqlite-vec schema 詳細は `m4-memory-semantic-layer` で
- **`DialogScheduler` Protocol** (schemas.py §7.5): turn-taking / backpressure / timeout の具象実装は `m4-multi-agent-orchestrator` で

## 5. データフロー

### フロー 1: 通常の認知サイクル (10秒ごと)
1. Simulation Layer がエージェントの現在位置・環境を観察データとして生成
2. **ERRE mode FSM** (M5 `m5-world-zone-triggers`): `CognitionCycle` に注入された `ERREModeTransitionPolicy` が観察列を評価し、必要なら `AgentState.erre` を更新 (同 tick 内の sampling に反映)。`m5-orchestrator-integration` 以降、`DefaultERREModePolicy` が composition root で instantiate される (`--disable-erre-fsm` で `None` に戻せる)
3. Memory Layer から関連記憶を検索 (per-agent top-8 + world top-3)
4. Working Memory (LLM context) に system prompt + AgentState + 記憶 + 観察を注入
5. Inference Layer が LLM 推論を実行 (更新後の ERRE モードに応じたサンプリング。`--disable-mode-sampling` 時は delta を zero table で上書きして persona base に戻す)
6. 推論結果から行動・発話を抽出、AgentState を更新
7. Memory Layer に新しい観察・重要度スコアを書き込み
8. Gateway 経由で WebSocket にエージェント状態を送信
9. `WorldRuntime._on_cognition_tick` 末尾で `_drive_dialog_turns` が open dialog を並列処理し、`DialogTurnMsg` を emit (M5 `m5-orchestrator-integration`)
10. MacBook 側の Godot が 3D シーンを更新

### フロー 2: 反省 (Reflection)
1. importance 合計 > 150、または peripatos/chashitsu 入室がトリガー
2. 直近の記憶群から「高次の洞察」を LLM で生成
3. 洞察を Semantic memory に書き込み
4. AgentState の emotion・goals を更新

#### M4 実装 (`m4-cognition-reflection`, `schema_version=0.2.0-m4`)
CognitionCycle は `Reflector` collaborator (`src/erre_sandbox/cognition/reflection.py`)
を 1 tick の末尾で呼び出し、以下の 3 源どれかが満たされると 1 reflection を発火:
- `ReflectionPolicy.importance_threshold` (default 1.5) — per-tick importance 合計
- zone 入室 (peripatos / chashitsu) — `ZoneTransitionEvent.to_zone`
- `tick_interval` (default 10) — Reflector 内 per-agent counter。`tick % N` では
  なく counter なので、M4+ multi-agent で agent ごとに tick がずれても正しく発火

発火時は `MemoryStore.list_by_agent(kind=EPISODIC, limit=window)` で直近 N 件を
取り出し、reflection 専用 prompt (`build_reflection_messages`) で LLM に短い自然文
要約を生成させる。要約を `embed_document` で埋め込み、`SemanticMemoryRecord`
(origin_reflection_id を付与) として `upsert_semantic` で永続化し、
`CycleResult.reflection_event: ReflectionEvent | None` に載せて返す。

LLM / embedding outage は Reflector 内で catch し `reflection_event=None` を返す
(action 選択の `llm_fell_back` とは独立)。embedding 失敗時は vec0 には書かず
semantic_memory に row だけ作る (検索対象外; m4-memory-semantic-layer D7 と整合)。

### フロー 3: リプレイ
1. Jupyter notebook から SQLite スナップショットを読み込み
2. 任意 tick の AgentState・記憶状態を復元
3. 4層評価指標を算出

## 6. 外部システム連携

| システム | 連携方式 | 認証 | 失敗時の挙動 |
|---|---|---|---|
| SGLang server | HTTP API | なし (LAN 内) | Ollama にフォールバック |
| Ollama | HTTP API | なし (localhost) | エラーログ + リトライ |
| Godot 4.4 | WebSocket | なし (LAN 内) | 接続切断時に自動再接続 |
| HuggingFace Hub | HTTPS | API token | LoRA/デモの公開のみ、推論には不要 |
| OSF (事前登録) | Web UI | アカウント | 手動操作、システム連携なし |

## 7. 設計上の制約とトレードオフ

### 採用しなかった選択肢

| 候補 | 不採用理由 |
|---|---|
| MLA (Multi-Head Latent Attention) / DeepSeek 系 | 既存モデルへの後付け不可。Llama-Swallow の日本語強度を失う。GQA + KV q8_0 で VRAM 問題は解決済み |
| Adaptive FT / 状態重み焼込み LoRA | 状態×ペルソナの組合せ爆発。MVP 段階での premature optimization。RadixAttention で state tag コストは実質ゼロ |
| gRPC | Python 内部通信では boilerplate コストが合わない。多言語クライアントが必要になるまで導入しない |
| ZeroMQ | >10kHz の状態配信が必要になった段階で検討 |
| Blender (bpy) | GPL-2+ の viral 性。import bpy する全コードが GPL 派生物になり、Apache/MIT と矛盾 |
| クラウド LLM API | コストゼロ制約に反する。ローカル推論で完結させる |

### 許容する技術的負債
- MVP 段階ではインコンテキストペルソナのみ (LoRA は M9 以降)
- 認証なし (LAN 内前提)
- ダッシュボードは Streamlit の最小実装から開始
- Godot シーンは最小限のアセットから段階的に拡充

### VRAM 予算試算 (理論値、M1 末に実測値で差し替え予定)

| 項目 | 使用量 |
|---|---|
| ベースモデル重み (Qwen3-8B Q5_K_M) | ~5.5 GB |
| KV キャッシュ (q8_0, 8並列 x 4K トークン) | ~5-6 GB |
| RadixAttention 共有 prefix 節約 | -30% (KV 部分) |
| CUDA コンテキスト・アクティベーション | ~2 GB |
| **合計** | **~13 GB (16 GB に収まる)** |

注: context 8K に上げる場合は並列を 6 に絞る。

## 8. 拡張ポイント

| 拡張 | トリガー条件 | 変更箇所 |
|---|---|---|
| LoRA ペルソナ | M9 以降、プロンプトペルソナの限界が見えたとき | inference/ に vLLM adapter 追加 |
| Qdrant + bge-m3 | 記憶 10 万件超でパフォーマンス劣化時 | memory/ のバックエンド差し替え |
| gRPC 通信 | Unity など非 Python クライアント接続時 | gateway/ に gRPC サーバー追加 |
| ZeroMQ | 状態配信 >10kHz 必要時 | gateway/ の transport 差し替え |
| MoE 日本語モデル | 16GB 帯で安定した MoE が登場時 | inference/ のモデル設定変更 |

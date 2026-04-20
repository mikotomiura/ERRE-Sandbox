# m4-gateway-multi-agent-stream

## 背景

M4 planning (`.steering/20260420-m4-planning/`) で確定したサブタスク #4。
Axis A (Multiplicity) + Axis C (Sociality) の infra 側。`m4-contracts-freeze`
(PR #43 merged) と独立に並列実行可能で、Critical Path (#3→#5→#6) を押さない。

### 既存状態 (M2 T14 時点)

- `src/erre_sandbox/integration/gateway.py`:
  - FastAPI + WebSocket `/ws/observe` 1 つ。session phase は関数の制御フロー
    (AWAITING_HANDSHAKE → ACTIVE → CLOSING)
  - `Registry.fan_out(env)`: **全 session に全 envelope をブロードキャスト**
  - `_SERVER_CAPABILITIES`: 7 kinds (`handshake`, `agent_update`, `speech`,
    `move`, `animation`, `world_tick`, `error`) — **M4 の dialog_* 3 種が欠落**
  - per-agent routing / subscription mechanism なし
- `src/erre_sandbox/world/tick.py`:
  - `WorldRuntime.register_agent(state, persona)` で N-agent を管理
  - 認知・移動 envelopes はすべて `_envelopes` キューに混在、
    `recv_envelope()` で FIFO 取り出し
  - 各 envelope は `agent_id` フィールドを持つ (agent_update / speech / move /
    animation) — discriminator には無いが routing キーとして使える
- M4 foundation で `DialogInitiateMsg` / `DialogTurnMsg` / `DialogCloseMsg`
  が ControlEnvelope union に追加済 (ただし Dialog* は `initiator_agent_id` /
  `target_agent_id` / `speaker_id` / `addressee_id` など複数の agent フィールドを持つ)

### M4 で必要な振る舞い

- MacBook Godot が 3 avatar (Kant / Nietzsche / Rikyu) を同時表示するとき、
  既存の fan-out は動く (すべてブロードキャストで届く) が、以下の課題:
  1. 1 クライアントが特定の agent だけを subscribe したい時 (debug / monitor)
     の手段がない
  2. dialog_* envelope が capabilities に含まれず、クライアントが
     「自分が扱える」と宣言しても gateway 側が通さない可能性
  3. 将来的に MVP 同時 10 viewer で N agent = 10 のとき、帯域が
     O(N × M) になる (現状仕様、最適化余地)

### スコープ判断 (要 /reimagine)

planning design.md §「per-agent gateway routing 方式」は
「broadcast filter vs explicit subscription」を本タスクで決めると明記。
v1 (ブロードキャスト継続) と v2 (server-side subscription) の比較が必要。

## ゴール

- dialog_* 3 kinds が capabilities に含まれ、クライアントが自然に受信できる
- クライアントが handshake 時に subscribe したい agent_id を指定できる経路が
  確立される (詳細は design.md で決定)
- N 同時 WS client が異なる agent 購読で動作することが
  integration test で検証される
- ControlEnvelope variant discrimination が dialog_* 含めて正しく通る

## スコープ

### 含むもの

- `src/erre_sandbox/integration/gateway.py`:
  - `_SERVER_CAPABILITIES` に `dialog_initiate` / `dialog_turn` /
    `dialog_close` を追加 (10 kinds)
  - per-session agent_id 購読フィルタ (詳細は design.md で選定)
  - `Registry` の fan_out ロジック拡張 (フィルタ適用)
  - Dialog* envelope の agent_id 抽出ヘルパー
    (`initiator_agent_id` / `target_agent_id` / `speaker_id` /
    `addressee_id` / `dialog_id` の routing 対象選定)
- `src/erre_sandbox/integration/protocol.py` (必要なら):
  - 新 routing に関する操作定数 (e.g. subscribe token 長さ等、あれば)
- `tests/test_integration/test_multi_agent_stream.py` 新規:
  - N (= 3) WS client が異なる agent_id で接続、broadcast が期待通りに分岐
  - DialogTurnMsg を runtime から流し、dialog 関与 agent の subscriber に届く
  - 無指定 (subscribe=["*"] 相当) で全 envelope 受信
  - 無関係 agent の subscriber に届かない
  - ControlEnvelope discriminator が dialog_* で正しく動く
  - handshake の capabilities に dialog_* が含まれる
  - 既存 single-client broadcast test (test_gateway.py) 継続 PASS
- `docs/architecture.md §Gateway`:
  - multi-agent routing 方式、capability 10 種への拡張、dialog plumbing を追記

### 含まないもの (個別タスク / 後続)

- `DialogScheduler` の具体実装 (turn-taking policy / backpressure) →
  `m4-multi-agent-orchestrator` (#6)
- reflection 発火 / semantic memory 側ロジック → #3 (merged) / #5
- Godot 側での `dialog_initiate_received` 等 signal の消費 (描画連携) → #6
- 認証・認可 (LAN-only 前提) → 本タスクでも追加しない
- バージョニング互換性の複数版 (client v0.1.0-m2 と server 0.2.0-m4 の併存) →
  foundation で schema_mismatch で reject する既存挙動を維持、拡張しない

## 受け入れ条件

- [ ] `_SERVER_CAPABILITIES` が `dialog_initiate` / `dialog_turn` /
      `dialog_close` を含む 10 kinds になっている
- [ ] 3 WS client が異なる `subscribe` 指定で接続し、対応する agent_id の
      envelope のみを受信する integration test が PASS
- [ ] `DialogTurnMsg` を runtime 経由で流すと、`speaker_id` と
      `addressee_id` いずれかを購読している client が受信する
- [ ] `HandshakeMsg` の未サブスクライブ (wildcard or 空) クライアントは
      既存ブロードキャスト動作を維持 (後方互換)
- [ ] 既存 `tests/test_integration/` 全件 PASS (regression なし)
- [ ] `uv run pytest` 全件 PASS (baseline 407 → ≥ 413)
- [ ] `ruff check` / `ruff format --check` クリーン
- [ ] `code-reviewer` HIGH ゼロ
- [ ] `security-checker` HIGH/MEDIUM ゼロ
      (subscribe フィルタは DoS / 他 agent データ漏洩の観点で確認)
- [ ] `docs/architecture.md §Gateway` 更新

## 関連ドキュメント

- `.steering/20260420-m4-planning/design.md` §m4-gateway-multi-agent-stream
- `.steering/20260419-gateway-fastapi-ws/design.md` (T14 の元設計)
- `.steering/20260419-m2-integration-e2e/decisions.md` D3 (protocol 分離)
- `docs/architecture.md §Gateway`
- `src/erre_sandbox/integration/gateway.py` / `protocol.py`
- `src/erre_sandbox/world/tick.py` (envelope 出口)
- `.claude/skills/architecture-rules/SKILL.md`
- `.claude/skills/test-standards/SKILL.md`

## 運用メモ

- 破壊と構築 (`/reimagine`) 適用: **Yes**
- 理由: planning design.md が「per-agent routing 方式 (broadcast filter vs
  explicit subscription) は #4 で決定」と明記している。
  複数の実装案 (v1: broadcast + client-side filter、v2: handshake で
  subscribed_agents 宣言、v3: URL path `/ws/observe/{agent_id}`) があり、
  確証バイアスなしに比較する価値が高い。memory `feedback_reimagine_trigger.md` 規定対象。

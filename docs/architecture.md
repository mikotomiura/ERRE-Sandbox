# 技術設計書

## 1. アーキテクチャ概要

### 全体図

```
┌─── G-GEAR (Linux / Win+WSL2, RTX 5060 Ti 16GB) ───────────────────┐
│ [Inference Layer]                                                   │
│   SGLang server (本番) / Ollama (開発)                              │
│   1 base model (Qwen3-8B or Llama-3.1-Swallow-8B, Q5_K_M)         │
│   RadixAttention × 8-10 persona × prefix KV 共有                   │
│   (将来) LoRA per persona via vLLM --enable-lora                    │
│                                                                     │
│ [Simulation Layer]                                                  │
│   asyncio tick loop @ 30Hz world physics, 0.1Hz agent cognition    │
│   PIANO モジュール (memory, social, goal, action, speech)           │
│                                                                     │
│ [Memory Layer]                                                      │
│   sqlite-vec (.db 単一ファイル, MIT)                                │
│   + multilingual-e5-small (384d) or Ruri-v3-30m                    │
│   Per-agent スコープ + shared world スコープ                        │
│                                                                     │
│ [Gateway]                                                           │
│   FastAPI + uvicorn + websockets                                    │
│   ws://g-gear.local:8000/stream                                     │
└─────────────────────────────────────────────────────────────────────┘
                          ↕ WebSocket (JSON / msgpack)
┌─── MacBook Air M4 (macOS, arm64) ──────────────────────────────────┐
│ [Orchestrator]                                                      │
│   Python 3.11 + asyncio client                                      │
│   ERRE DSL interpreter (shu/ha/ri, peripatos, chashitsu FSM)       │
│                                                                     │
│ [Viz]                                                               │
│   Godot 4.4 (MIT) 3D viewer                                        │
│   Streamlit / FastAPI + HTMX dashboard                              │
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
| 埋め込み | multilingual-e5-small (384d) / Ruri-v3-30m | 最新 | 日本語優勢なら Ruri、JA/EN 均衡なら e5 |
| 3D エンジン | Godot 4.4 | 4.4 | MIT、NavMesh・Skeletal animation 完備 |
| ダッシュボード | Streamlit / FastAPI + HTMX | 最新 | ブラウザから直接可視化 |
| 研究ツール | Jupyter | 最新 | リプレイ・指標計算 |
| ドキュメント | MkDocs Material + mkdocstrings | 最新 | JA/EN 併記対応 |
| CI | GitHub Actions | - | uv sync --frozen → ruff → pytest |

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
  - CoALA 認知サイクル: Observe → Appraise → Update State → Retrieve → Reflect? → Plan → Act → Speak
  - ERRE モード FSM: peripatetic / chashitsu / zazen / shu_kata / ha_deviate / ri_create / deep_work / shallow

### Memory Layer (G-GEAR)
- **責務**: エージェント記憶の永続化と検索
- **主要コンポーネント**:
  - sqlite-vec: ベクトル埋め込み格納
  - 4種記憶: Episodic / Semantic / Procedural / Relational
  - 二層スコープ: per-agent (top-8) + world (top-3)
  - 減衰関数: `strength = importance * exp(-λ*days) * (1 + recall_count*0.2)`

### Gateway (G-GEAR)
- **責務**: MacBook 側との通信
- **主要コンポーネント**:
  - FastAPI + uvicorn + websockets (BSD-3)
  - ControlEnvelope スキーマ + kind フィールドでメッセージ多重化
  - Pydantic v2 によるスキーマ検証
- **起動方式と `_NullRuntime` 注意**:
  - `python -m erre_sandbox.integration.gateway` 単体起動は **debug-only default**。
    内部で `_NullRuntime` (class in `src/erre_sandbox/integration/gateway.py`) が注入され、
    `recv_envelope()` は永久に sleep するため Avatar / WorldTick 等の envelope は **ゼロ件** 配信される
  - **Production 起動は `make_app(runtime=world_runtime)` で real `WorldRuntime` を inject 必須**
  - 1 コマンドで persona loading → CognitionCycle → WorldRuntime → Gateway を連鎖起動する
    full-stack orchestrator は M4 `gateway-multi-agent-stream` タスクで整備予定
  - `/health` の `active_sessions` counter は MacBook 側から 1Hz で probe して Godot 接続の silent failure を検出する
    (runbook: `.steering/20260419-m2-acceptance/session-counter-runbook.md`)

### Orchestrator (MacBook Air M4)
- **責務**: シミュレーション制御、ERRE DSL 解釈
- **主要コンポーネント**:
  - asyncio WebSocket client
  - ERRE DSL interpreter: shu/ha/ri、peripatos、chashitsu の状態機械

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

### ControlEnvelope
- **責務**: G-GEAR ↔ MacBook 間の通信プロトコル
- **構成**: `kind` フィールドでメッセージ種別を識別
- **送信データ**: `{agent_id, position, rotation, animation, speech_bubble}` (30Hz)

## 5. データフロー

### フロー 1: 通常の認知サイクル (10秒ごと)
1. Simulation Layer がエージェントの現在位置・環境を観察データとして生成
2. Memory Layer から関連記憶を検索 (per-agent top-8 + world top-3)
3. Working Memory (LLM context) に system prompt + AgentState + 記憶 + 観察を注入
4. Inference Layer が LLM 推論を実行 (ERRE モードに応じたサンプリングパラメータ)
5. 推論結果から行動・発話を抽出、AgentState を更新
6. Memory Layer に新しい観察・重要度スコアを書き込み
7. Gateway 経由で WebSocket にエージェント状態を送信
8. MacBook 側の Godot が 3D シーンを更新

### フロー 2: 反省 (Reflection)
1. importance 合計 > 150、または peripatos/chashitsu 入室がトリガー
2. 直近の記憶群から「高次の洞察」を LLM で生成
3. 洞察を Semantic memory に書き込み
4. AgentState の emotion・goals を更新

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

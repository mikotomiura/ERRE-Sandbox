# Architecture Rules — モジュール配置の判断フロー

## どこに書くか迷ったときの決め木

```
新しいコードを書こうとしている
    │
    ├─ Pydantic の BaseModel 定義 (AgentState, ControlEnvelope 等)?
    │   → schemas.py に追記 (新ファイルは作らない)
    │
    ├─ LLM への HTTP リクエスト / SGLang / Ollama との通信?
    │   → src/erre_sandbox/inference/
    │       - 新しい LLM バックエンド    → [backend_name]_adapter.py
    │       - FastAPI エンドポイント     → server.py に追記
    │
    ├─ sqlite-vec への読み書き / 埋め込みモデルの呼び出し / 記憶スコアリング?
    │   → src/erre_sandbox/memory/
    │       - DB 操作全般               → store.py
    │       - 埋め込みモデル管理         → embedding.py
    │       - 検索・ランキング           → retrieval.py
    │
    ├─ CoALA 認知サイクル / 反省 / 行動計画 / PIANO モジュール?
    │   → src/erre_sandbox/cognition/
    │       - Observe→Act ループ         → cycle.py
    │       - 反省・内省 (Reflection)    → reflection.py
    │       - 行動計画 (Planning)        → planning.py
    │       - PIANO 並列モジュール       → piano.py
    │
    ├─ tick ループ / ゾーン管理 / 物理演算 (位置・衝突)?
    │   → src/erre_sandbox/world/
    │       - asyncio tick loop          → tick.py
    │       - ゾーン (peripatos/chashitsu 等) → zones.py
    │       - 簡易物理                  → physics.py
    │
    ├─ WebSocket クライアント / Godot 連携 / Streamlit ダッシュボード?
    │   → src/erre_sandbox/ui/
    │       - WebSocket クライアント    → ws_client.py
    │       - ダッシュボード            → dashboard.py
    │       - Godot ブリッジ            → godot_bridge.py
    │
    ├─ ERRE パイプライン (Extract/Reverify/Reimplement/Express)?
    │   → src/erre_sandbox/erre/
    │       - 史料→認知構造抽出        → extract.py
    │       - 脳科学的再検証           → reverify.py
    │       - CoALA 準拠実装           → reimplement.py
    │       - 3D 表現制御              → express.py
    │
    └─ テストコード?
        → tests/ の src/ ミラー構造に配置
            src/erre_sandbox/memory/retrieval.py
            → tests/test_memory/test_retrieval.py
```

---

## 判断例

### 「LLM に向けて記憶を検索してプロンプトを組み立てるコード」はどこ?

→ `cognition/cycle.py`

reasoning: 記憶検索 (`memory/`) と LLM 呼び出し (`inference/`) の両方を呼ぶのは
**認知サイクル** の責務。`cognition/` だけが両方に依存できる。

### 「Ruri-v3-30m モデルをロードしてベクトルを計算するコード」はどこ?

→ `memory/embedding.py`

reasoning: 埋め込みモデルは記憶システムの一部。`inference/` ではない。
（`inference/` はユーザー向け LLM 推論専用）

### 「エージェントの現在位置を Godot に 30Hz で送信するコード」はどこ?

→ `world/tick.py` で状態を生成し、`ui/godot_bridge.py` が WebSocket 送信

reasoning: 状態の更新は `world/` の責務。送信処理は `ui/` の責務。
ただし `world/` が `ui/` を import するのは禁止なので、
`world/` はキューに入れて `ui/` が取り出す設計にする。

### 「AgentState の ERRE モードに応じて temperature を変えるロジック」はどこ?

→ `inference/server.py` (または `inference/` 内の generate 関数)

reasoning: サンプリングパラメータは LLM 推論の設定。
`ERREMode.sampling_overrides` を読んで temperature を調整するのは `inference/` が行う。
`cognition/` は「どのモードか」を知っているが、「その temperature は何か」は知らなくてよい。

---

## インポートの依存方向チェックコマンド

```bash
# ui/ が inference/ を直接 import していないか
grep -rn "from erre_sandbox.inference" src/erre_sandbox/ui/
grep -rn "from erre_sandbox.memory"    src/erre_sandbox/ui/
grep -rn "from erre_sandbox.cognition" src/erre_sandbox/ui/
grep -rn "from erre_sandbox.world"     src/erre_sandbox/ui/

# schemas.py が他モジュールを import していないか
grep -n "from erre_sandbox\." src/erre_sandbox/schemas.py

# GPL ライブラリが混入していないか
grep -rn "import bpy"  src/erre_sandbox/
grep -rn "import openai"  src/erre_sandbox/
grep -rn "from anthropic" src/erre_sandbox/
```

# Python Standards — パターン集

ERRE-Sandbox 固有の頻出パターン。新しいコードを書く時に参照。

---

## パターン 1: 型エイリアスによる数値制約

```python
from pydantic import confloat, conint

# 型エイリアスで意図を明示
Score = conint(ge=0, le=100)        # 0〜100 の整数スコア (fatigue, focus など)
Unit  = confloat(ge=-1.0, le=1.0)   # -1.0〜1.0 の実数単位 (valence, arousal など)

class Physical(BaseModel):
    fatigue: Score = 20
    focus: Score = 70
    valence: Unit = 0.0             # Russell circumplex
```

**なぜ**: `confloat(ge=-1.0, le=1.0)` を毎回書くと冗長でバリデーション条件が散在する。
エイリアスにすることで「物理量の意味」が型名に現れる。

---

## パターン 2: dump_for_prompt() — LLM コンテキスト文字列化

すべての AgentState 系モデルに `dump_for_prompt()` を実装し、LLM への注入形式を一箇所に集約。

```python
class AgentState(BaseModel):
    bio: Biography
    physical: Physical = Field(default_factory=Physical)
    emotion: Emotion = Field(default_factory=Emotion)
    erre: ERREMode = Field(default_factory=ERREMode)
    tick: int = 0

    def dump_for_prompt(self) -> str:
        """Serialize state for LLM context injection.
        
        Returns a compact, human-readable string optimized for token efficiency.
        """
        return (
            f"[{self.bio.name} | tick={self.tick}]\n"
            f"mode={self.erre.mode} dmn={self.erre.dmn_bias:+.1f}\n"
            f"fatigue={self.physical.fatigue} focus={self.physical.focus} "
            f"loc={self.physical.location}\n"
            f"emotion={self.emotion.plutchik} "
            f"v={self.emotion.valence:+.2f} a={self.emotion.arousal:+.2f}"
        )
```

**なぜ**: LLM コンテキストは token 数が制限される。`model_dump()` は冗長すぎる。
`dump_for_prompt()` はプロジェクト全体の共通インターフェースとして機能させる。

---

## パターン 3: Literal 型で状態機械の値を制約

```python
from typing import Literal

class ERREMode(BaseModel):
    mode: Literal[
        "peripatetic", "chashitsu", "zazen",
        "shu_kata", "ha_deviate", "ri_create",
        "deep_work", "shallow"
    ] = "deep_work"
    dmn_bias: Unit = 0.0
    sampling_overrides: dict[str, float] = {}  # {"temperature": 0.3, "top_p": 0.05}

class Physical(BaseModel):
    location: Literal[
        "study", "peripatos", "chashitsu", "agora", "garden"
    ] = "study"
```

**なぜ**: str だと無効な状態値でもエラーにならない。Literal は IDE の補完も効く。
ERRE モードのサンプリングパラメータ変更は必ず `sampling_overrides` 経由で集約する。

---

## パターン 4: asyncio — tick loop と認知サイクル

```python
import asyncio
from collections.abc import AsyncGenerator

# ✅ tick ループの基本構造
async def world_tick_loop(hz: float = 30.0) -> None:
    """World physics tick at specified Hz."""
    interval = 1.0 / hz
    while True:
        await tick_physics()
        await asyncio.sleep(interval)

async def cognition_loop(hz: float = 0.1) -> None:
    """Agent cognition cycle at 0.1 Hz (every 10 seconds)."""
    interval = 1.0 / hz
    while True:
        await asyncio.gather(*[agent.run_cycle() for agent in agents])
        await asyncio.sleep(interval)

# ✅ 並列起動
async def main() -> None:
    await asyncio.gather(
        world_tick_loop(hz=30.0),
        cognition_loop(hz=0.1),
    )
```

**なぜ**: 物理ループ (30Hz) と認知ループ (0.1Hz) は独立したタスクとして走らせる。
`asyncio.gather()` で並列化し、どちらかが落ちたとき分離してデバッグできる。

---

## パターン 5: WebSocket — ControlEnvelope

```python
from pydantic import BaseModel
from typing import Literal, Any

class ControlEnvelope(BaseModel):
    kind: Literal[
        "agent_state", "agent_move", "speech_bubble",
        "mode_change", "ping", "pong"
    ]
    agent_id: str
    payload: dict[str, Any]
    tick: int

# 送信側 (G-GEAR)
async def emit_agent_state(ws: WebSocket, state: AgentState) -> None:
    envelope = ControlEnvelope(
        kind="agent_state",
        agent_id=state.bio.name,
        payload={
            "position": state.physical.location,
            "animation": _mode_to_animation(state.erre.mode),
        },
        tick=state.tick,
    )
    await ws.send_text(envelope.model_dump_json())
```

**なぜ**: `kind` フィールドで全メッセージ種別を多重化する設計。
Pydantic v2 の `model_dump_json()` で直接 JSON 文字列を得られるため `json.dumps()` 不要。

---

## パターン 6: sqlite-vec — 記憶スコアリング関数

```python
import math
from datetime import datetime

def compute_memory_strength(
    importance: float,
    days_since: float,
    recall_count: int,
    decay_lambda: float = 0.1,
) -> float:
    """Ebbinghaus-inspired memory strength.
    
    Formula: importance × exp(-λ × days) × (1 + recall_count × 0.2)
    """
    recency = math.exp(-decay_lambda * days_since)
    recall_bonus = 1.0 + recall_count * 0.2
    return importance * recency * recall_bonus
```

**なぜ**: Park et al. (2023) の式をそのまま Python 関数にする。
純粋関数なので単体テストが書きやすく、sqlite-vec の UDF としても登録できる。

---

## パターン 7: 埋め込みプレフィックス — 必ず CI テストを書く

sqlite-vec + multilingual-e5-small / Ruri-v3-30m ではプレフィックスが必須。
**プレフィックスなしは 5〜15 ポイントの recall 劣化を招く** (JMTEB 実測)。

```python
# ✅ 正しいプレフィックス使用
QUERY_PREFIX  = "検索クエリ: "   # Ruri 系
DOC_PREFIX    = "検索文書: "     # Ruri 系
# または
QUERY_PREFIX  = "query: "        # multilingual-e5 系
DOC_PREFIX    = "passage: "      # multilingual-e5 系

def embed_query(text: str) -> list[float]:
    return model.encode(QUERY_PREFIX + text).tolist()

def embed_document(text: str) -> list[float]:
    return model.encode(DOC_PREFIX + text).tolist()
```

```python
# ❌ 悪い例 — プレフィックスなし
def embed_query(text: str) -> list[float]:
    return model.encode(text).tolist()   # recall が劣化する
```

**CI テスト (必須)**:

```python
# tests/test_memory/test_embedding_prefix.py
def test_query_prefix_is_set() -> None:
    assert embed_query("test").prefix == QUERY_PREFIX  # 実装依存の確認方法に変更

def test_query_doc_distance_with_prefix() -> None:
    """Semantic similarity must be higher with correct prefix."""
    q = embed_query("アリストテレスの歩行習慣")
    d_match = embed_document("ペリパトス学派は歩きながら議論した")
    d_mismatch = embed_document("量子コンピューターの計算速度")
    sim_match = cosine_similarity(q, d_match)
    sim_mismatch = cosine_similarity(q, d_mismatch)
    assert sim_match > sim_mismatch + 0.3
```

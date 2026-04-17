---
name: python-standards
description: >
  Python 3.11 のコーディング規約を適用する。src/erre_sandbox/ 配下の
  .py ファイルを書く・修正する・レビューする時に必須参照。
  asyncio を使った非同期コードを書く時、Pydantic v2 の BaseModel を定義する時、
  FastAPI エンドポイントを実装する時、schemas.py を変更する時に自動召喚される。
  snake_case/PascalCase の命名、型ヒント必須、ruff format/lint 準拠、
  f-string 優先、from __future__ import annotations 使用が強制される。
  ファイル命名: ollama_adapter.py, ws_client.py など snake_case .py ファイル全般。
allowed-tools: Read, Edit, Glob, Grep, Bash(ruff *)
---

# Python Standards

## このスキルの目的

Python 3.11 + asyncio + Pydantic v2 + FastAPI を使う ERRE-Sandbox において、
一貫したコーディング規約を維持する。特に asyncio の正しい使い方と
型安全性は、マルチエージェントシミュレーションの安定稼働に直結する。

## 適用範囲

### 適用するもの
- `src/erre_sandbox/` 配下のすべての `.py` ファイル
- `tests/` 配下のテストコード
- `pyproject.toml` の ruff 設定

### 適用しないもの
- `godot_project/` 内の GDScript (`.gd`) — Godot 規約に従う
- Jupyter notebook (`.ipynb`) — 探索的コードは適用外

## 主要なルール

### ルール 1: 型ヒントは必須

すべての関数・メソッドに引数と戻り値の型ヒントを付与する。
`from __future__ import annotations` でファイル先頭に遅延評価を有効化。

```python
# ✅ 良い例
from __future__ import annotations

async def retrieve(query: str, k: int = 8) -> list[MemoryEntry]:
    ...
```

```python
# ❌ 悪い例
async def retrieve(query, k=8):
    ...
```

### ルール 2: asyncio — ブロッキング I/O を避ける

同期的な I/O (ファイル読み込み、DB アクセス、HTTP) は `asyncio.to_thread()` か
専用の async ライブラリを使う。`time.sleep()` は `asyncio.sleep()` に置き換える。

```python
# ✅ 良い例
import asyncio

async def load_corpus(path: str) -> str:
    return await asyncio.to_thread(_read_file_sync, path)

async def wait_for_inference() -> None:
    await asyncio.sleep(0.1)
```

```python
# ❌ 悪い例
def load_corpus(path: str) -> str:
    with open(path) as f:           # ブロッキング
        return f.read()

import time
time.sleep(0.1)                     # asyncio ループをブロック
```

### ルール 3: Pydantic v2 — BaseModel 活用

エージェント状態・通信プロトコル・設定はすべて `BaseModel` で定義。
`model_validator` / `field_validator` で制約を付与し、`dump_for_prompt()` で
LLM コンテキスト用文字列化メソッドを実装。

```python
# ✅ 良い例
from pydantic import BaseModel, field_validator

class AgentState(BaseModel):
    agent_id: str
    fatigue: float = 0.0

    @field_validator("fatigue")
    @classmethod
    def clamp_fatigue(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    def dump_for_prompt(self) -> str:
        return f"Agent {self.agent_id}: fatigue={self.fatigue:.2f}"
```

```python
# ❌ 悪い例
class AgentState:
    def __init__(self, agent_id, fatigue=0.0):
        self.agent_id = agent_id
        self.fatigue = fatigue   # バリデーションなし
```

### ルール 4: 命名規則

| 対象 | 規則 | 例 |
|---|---|---|
| 変数・関数 | snake_case | `agent_state`, `dump_for_prompt()` |
| クラス | PascalCase | `AgentState`, `MemoryStream` |
| 定数 | UPPER_SNAKE_CASE | `DEFAULT_TEMPERATURE`, `MAX_AGENTS` |
| ファイル・モジュール | snake_case | `ollama_adapter.py`, `ws_client.py` |

### ルール 5: 文字列フォーマット

`f-string` を既定とする。`%` 形式・`.format()` は新規コードで使わない。

```python
# ✅ 良い例
label = f"Agent {agent_id}: step={tick_count}"
```

```python
# ❌ 悪い例
label = "Agent %s: step=%d" % (agent_id, tick_count)
label = "Agent {}: step={}".format(agent_id, tick_count)
```

### ルール 6: インポート順序 (ruff 準拠)

1. 標準ライブラリ
2. サードパーティ
3. ローカル (`erre_sandbox.*`)

各グループは空行で区切り、グループ内はアルファベット順。`ruff` が自動整形。

```python
# ✅ 良い例
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import BaseModel

from erre_sandbox.schemas import AgentState
```

### ルール 7: コメント方針

- **書くべき時**: ロジックが自明でない、認知科学論文への参照、ERRE 独自設計の理由
- **書かないとき**: 型ヒントやメソッド名で意図が明確な場合
- **docstring**: 英語、Google スタイル。公開 API には必ず付ける

```python
# ✅ 良い例
# Park et al. (2023) Eq.3: importance × recency × relevance の積
score = importance * recency * relevance
```

```python
# ❌ 悪い例
# スコアを計算する
score = importance * recency * relevance
```

## チェックリスト

このルールに従っているか確認:

- [ ] すべての関数に型ヒントが付いているか
- [ ] ファイル先頭に `from __future__ import annotations` があるか
- [ ] ブロッキング I/O を asyncio ループ内で直接呼んでいないか
- [ ] Pydantic v2 `BaseModel` で状態・スキーマを定義しているか
- [ ] 命名規則 (snake_case / PascalCase / UPPER_SNAKE_CASE) を守っているか
- [ ] 文字列フォーマットに f-string を使っているか
- [ ] `ruff check` と `ruff format --check` が通るか

## 補足資料

- `patterns.md` — asyncio + Pydantic v2 のよく使うパターン集

## 関連する他の Skill

- `test-standards` — テストコードでも同じ規約が適用される
- `error-handling` — asyncio のエラーハンドリングパターン
- `architecture-rules` — インポート依存方向の制約

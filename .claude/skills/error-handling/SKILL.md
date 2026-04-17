---
name: error-handling
description: >
  asyncio を使ったエラーハンドリングとリトライ戦略。
  inference/ や memory/ や cognition/ のコードを書く・修正する時に必須参照。
  SGLang → Ollama フォールバックを実装する時、WebSocket の再接続ロジックを書く時、
  LLM 推論タイムアウトを処理する時、sqlite-vec の DB エラーを扱う時、
  asyncio.gather() で並列タスクの一部が失敗した場合の処理を書く時に自動召喚される。
  ollama_adapter.py / sglang_adapter.py / ws_client.py / store.py を変更する時は
  必ずこの Skill を参照すること。
allowed-tools: Read, Edit, Glob, Grep
---

# Error Handling

## このスキルの目的

ERRE-Sandbox は 30Hz の tick ループと 0.1Hz の認知ループを並列で走らせる。
どちらかのエラーで全体がクラッシュしないよう、エラーの種類ごとに
「無視・リトライ・フォールバック・停止」を使い分ける。
特に LLM 推論と WebSocket 通信は「外部システムの不安定性」を前提に設計する。

## エラーの分類と対応方針

| 種類 | 例 | 対応 |
|---|---|---|
| 一時的エラー | LLM タイムアウト、DB ロック競合 | 指数バックオフでリトライ |
| フォールバック可能 | SGLang 応答なし | Ollama にフォールバック |
| 接続断 | WebSocket 切断 | 自動再接続 |
| データ破損 | Pydantic ValidationError | ログ + デフォルト値で継続 |
| 致命的エラー | DB 書き込み失敗 (全エージェント) | ログ + シミュレーション停止 |

## ルール 1: LLM 推論 — SGLang → Ollama フォールバック

```python
# ✅ 良い例
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

async def generate(prompt: str, **kwargs: Any) -> dict[str, Any]:
    """LLM inference with automatic SGLang → Ollama fallback."""
    try:
        return await _sglang_generate(prompt, **kwargs)
    except (TimeoutError, ConnectionRefusedError, OSError) as e:
        logger.warning("SGLang unavailable (%s), falling back to Ollama", e)
        return await _ollama_generate(prompt, **kwargs)
```

```python
# ❌ 悪い例 — フォールバックなし
async def generate(prompt: str, **kwargs: Any) -> dict[str, Any]:
    return await _sglang_generate(prompt, **kwargs)  # SGLang が落ちたら即クラッシュ
```

## ルール 2: 指数バックオフ付きリトライ

一時的なエラー（タイムアウト、DB ロック）にはリトライを使う。
**上限回数と最大遅延を必ず設定する**（無限ループ防止）。

```python
# ✅ 良い例
import asyncio

async def retry_async(
    coro_fn,
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs,
):
    """Retry with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return await coro_fn(*args, **kwargs)
        except (TimeoutError, OSError) as e:
            if attempt == max_attempts - 1:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                "Attempt %d/%d failed: %s. Retrying in %.1fs",
                attempt + 1, max_attempts, e, delay
            )
            await asyncio.sleep(delay)

# 使用例
result = await retry_async(_ollama_generate, prompt, max_attempts=3)
```

## ルール 3: WebSocket — 自動再接続

Godot (MacBook) と G-GEAR の WebSocket 接続は一時切断が起こり得る。
切断イベントを検知して自動再接続する。

```python
# ✅ 良い例
import websockets
import asyncio

async def ws_client_with_reconnect(uri: str) -> None:
    """WebSocket client with automatic reconnect."""
    while True:
        try:
            async with websockets.connect(uri) as ws:
                logger.info("WebSocket connected: %s", uri)
                await handle_ws_messages(ws)
        except (websockets.ConnectionClosed, OSError) as e:
            logger.warning("WebSocket disconnected: %s. Reconnecting in 5s", e)
            await asyncio.sleep(5.0)
```

## ルール 4: asyncio.gather — 一部失敗を許容

認知サイクルでは複数エージェントを並列実行する。1体の失敗で全体を止めない。

```python
# ✅ 良い例
results = await asyncio.gather(
    *[agent.run_cycle() for agent in agents],
    return_exceptions=True,   # 例外を結果として受け取る
)

for agent, result in zip(agents, results):
    if isinstance(result, Exception):
        logger.error("Agent %s cycle failed: %s", agent.bio.name, result)
        # 失敗したエージェントはスキップしてシミュレーション継続
    else:
        await process_result(agent, result)
```

```python
# ❌ 悪い例 — 1体失敗で全体停止
results = await asyncio.gather(
    *[agent.run_cycle() for agent in agents],
    # return_exceptions=False (デフォルト) → 最初の例外でギャザー全体が止まる
)
```

## ルール 5: Pydantic ValidationError の扱い

LLM の出力を Pydantic でパース失敗した場合、ログを残してデフォルト値で継続。
**LLM 出力は常に不正である可能性を前提とする。**

```python
# ✅ 良い例
from pydantic import ValidationError

def parse_llm_action(raw: dict) -> AgentAction:
    try:
        return AgentAction.model_validate(raw)
    except ValidationError as e:
        logger.warning(
            "Failed to parse LLM action (using idle default): %s\nRaw: %s",
            e, raw
        )
        return AgentAction(type="idle")  # デフォルトにフォールバック
```

## ルール 6: ログレベルの使い分け

```python
# DEBUG — 開発時の詳細情報 (本番ではオフ)
logger.debug("Tick %d: retrieved %d memories", tick, len(memories))

# INFO — 正常動作の記録
logger.info("Agent %s entered peripatetic mode", agent_id)

# WARNING — 想定内の異常 (リトライ可能、フォールバック済み)
logger.warning("SGLang timeout, fell back to Ollama for agent %s", agent_id)

# ERROR — 想定外の異常 (回復できない個別エラー)
logger.error("Agent %s cognition cycle failed: %s", agent_id, exc)

# CRITICAL — システム全体への影響 (シミュレーション停止レベル)
logger.critical("DB write failed for all agents, stopping simulation")
```

## チェックリスト

- [ ] LLM 推論に SGLang → Ollama フォールバックがあるか
- [ ] リトライに `max_attempts` と `max_delay` の上限を設定しているか
- [ ] WebSocket クライアントに自動再接続ループがあるか
- [ ] `asyncio.gather()` に `return_exceptions=True` が付いているか
- [ ] LLM 出力の Pydantic パース失敗時にデフォルト値でフォールバックしているか
- [ ] ログレベルが意図通り (DEBUG/INFO/WARNING/ERROR/CRITICAL) か

## 補足資料

- `examples.md` — inference アダプタの完全実装例と ws_client の再接続パターン

## 関連する他の Skill

- `python-standards` — asyncio の基本ルール
- `architecture-rules` — inference/ → schemas.py のみ依存の制約
- `llm-inference` — サーバー構成・VRAM 管理
- `persona-erre` — サンプリングオーバーライド表・ペルソナ YAML
- `godot-gdscript` — Godot 側の WebSocket 再接続パターン

# Error Handling — 実装例集

---

## 例 1: inference アダプタ — SGLang → Ollama フォールバック完全版

```python
# src/erre_sandbox/inference/ollama_adapter.py
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:8b-q5_K_M"
OLLAMA_TIMEOUT = 60.0  # seconds


async def generate(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    top_p: float = 0.9,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate via Ollama with timeout."""
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "top_p": top_p, **kwargs},
            },
        )
        response.raise_for_status()
        return response.json()
```

```python
# src/erre_sandbox/inference/sglang_adapter.py
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SGLANG_BASE_URL = "http://g-gear.local:30000"
SGLANG_TIMEOUT = 30.0


async def generate(
    prompt: str,
    temperature: float = 0.7,
    top_p: float = 0.9,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate via SGLang server."""
    async with httpx.AsyncClient(timeout=SGLANG_TIMEOUT) as client:
        response = await client.post(
            f"{SGLANG_BASE_URL}/generate",
            json={"text": prompt, "sampling_params": {
                "temperature": temperature, "top_p": top_p, **kwargs
            }},
        )
        response.raise_for_status()
        return response.json()
```

```python
# src/erre_sandbox/inference/server.py — フォールバックロジック
from __future__ import annotations

import logging
from typing import Any

from erre_sandbox.inference import ollama_adapter, sglang_adapter
from erre_sandbox.schemas import ERREMode

logger = logging.getLogger(__name__)


async def generate_with_fallback(
    prompt: str,
    erre_mode: ERREMode,
    base_temperature: float = 0.7,
    base_top_p: float = 0.9,
) -> dict[str, Any]:
    """Generate with ERRE mode sampling overrides and SGLang→Ollama fallback."""
    # ERRE モードのサンプリングパラメータを適用
    temperature = base_temperature + erre_mode.sampling_overrides.get("temperature", 0.0)
    top_p = base_top_p + erre_mode.sampling_overrides.get("top_p", 0.0)
    temperature = max(0.01, min(2.0, temperature))  # クランプ
    top_p = max(0.01, min(1.0, top_p))

    try:
        return await sglang_adapter.generate(
            prompt, temperature=temperature, top_p=top_p
        )
    except (TimeoutError, ConnectionRefusedError, OSError) as e:
        logger.warning("SGLang unavailable (%s), falling back to Ollama", type(e).__name__)
        return await ollama_adapter.generate(
            prompt, temperature=temperature, top_p=top_p
        )
```

---

## 例 2: WebSocket クライアント — 自動再接続

```python
# src/erre_sandbox/ui/ws_client.py
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import websockets
from websockets.exceptions import ConnectionClosed

from erre_sandbox.schemas import ControlEnvelope

logger = logging.getLogger(__name__)

GATEWAY_URI = "ws://g-gear.local:8000/stream"
RECONNECT_DELAY = 5.0  # seconds


async def receive_agent_states(
    uri: str = GATEWAY_URI,
) -> AsyncIterator[ControlEnvelope]:
    """Yield ControlEnvelope messages, reconnecting on disconnect."""
    while True:
        try:
            async with websockets.connect(uri) as ws:
                logger.info("WebSocket connected: %s", uri)
                async for raw_message in ws:
                    try:
                        envelope = ControlEnvelope.model_validate_json(raw_message)
                        yield envelope
                    except Exception as e:
                        logger.warning("Malformed envelope ignored: %s", e)

        except (ConnectionClosed, OSError, ConnectionRefusedError) as e:
            logger.warning(
                "WebSocket disconnected (%s). Reconnecting in %.1fs",
                type(e).__name__, RECONNECT_DELAY
            )
            await asyncio.sleep(RECONNECT_DELAY)
```

---

## 例 3: 認知サイクル — gather + return_exceptions

```python
# src/erre_sandbox/cognition/cycle.py
from __future__ import annotations

import asyncio
import logging
from typing import Any

from erre_sandbox.schemas import AgentState

logger = logging.getLogger(__name__)


async def run_all_cycles(agents: list[AgentState]) -> list[AgentState | None]:
    """Run cognition cycles for all agents in parallel.
    
    Returns list where None indicates a failed agent cycle.
    """
    results = await asyncio.gather(
        *[_run_single_cycle(agent) for agent in agents],
        return_exceptions=True,
    )

    updated_states: list[AgentState | None] = []
    for agent, result in zip(agents, results):
        if isinstance(result, Exception):
            logger.error(
                "Agent %s cycle failed (skipping): %s",
                agent.bio.name, result,
                exc_info=result,
            )
            updated_states.append(None)  # 失敗したエージェントは None
        else:
            updated_states.append(result)

    return updated_states
```

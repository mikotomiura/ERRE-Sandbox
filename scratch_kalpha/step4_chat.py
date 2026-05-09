"""K-α Step 4 — chat round trip with/without mock LoRA (CS-9 identity).

Identity hypothesis: mock LoRA has B=0 (identity transform), so WITH and
WITHOUT adapter outputs should be substantially similar (temperature noise
acceptable, but no vocabulary/style/length blow-up).

Run from WSL2:
    cd /root/erre-sandbox && uv run python /mnt/c/ERRE-Sand_Box/scratch_kalpha/step4_chat.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "/root/erre-sandbox/src")

from erre_sandbox.inference.ollama_adapter import ChatMessage
from erre_sandbox.inference.sampling import compose_sampling
from erre_sandbox.inference.sglang_adapter import (
    LoRAAdapterRef,
    SGLangChatClient,
    SGLangUnavailableError,
)
from erre_sandbox.schemas import SamplingBase, SamplingDelta


async def _ensure_loaded(llm: SGLangChatClient, ref: LoRAAdapterRef) -> None:
    """Load adapter; if server already has it (HTTP 400 on re-load), unload + retry."""
    try:
        await llm.load_adapter(ref)
    except SGLangUnavailableError as exc:
        if "HTTP 400" not in str(exc):
            raise
        await llm.unload_adapter(ref.adapter_name)
        await llm.load_adapter(ref)


async def main() -> int:
    async with SGLangChatClient(endpoint="http://127.0.0.1:30000") as llm:
        ref = LoRAAdapterRef(
            adapter_name="mock_kant_r8",
            weight_path=Path("/root/erre-sandbox/checkpoints/mock_kant_r8"),
            rank=8,
            is_mock=True,
        )
        await _ensure_loaded(llm, ref)

        sampling = compose_sampling(
            SamplingBase(temperature=0.6, top_p=0.85, repeat_penalty=1.12),
            SamplingDelta(),
        )
        prompt = [
            ChatMessage(role="system", content="You are Immanuel Kant."),
            ChatMessage(
                role="user", content="Describe today's walk in two sentences."
            ),
        ]
        with_adapter = await llm.chat(
            prompt, sampling=sampling, adapter="mock_kant_r8"
        )
        without_adapter = await llm.chat(prompt, sampling=sampling)

        print("=== WITH MOCK ADAPTER ===")
        print(f"finish_reason: {with_adapter.finish_reason}")
        print(f"eval_count:    {with_adapter.eval_count}")
        print(f"content (180): {with_adapter.content[:180]}")
        print()
        print("=== WITHOUT ADAPTER ===")
        print(f"finish_reason: {without_adapter.finish_reason}")
        print(f"eval_count:    {without_adapter.eval_count}")
        print(f"content (180): {without_adapter.content[:180]}")
        print()
        print("=== IDENTITY HEURISTICS ===")
        len_w = len(with_adapter.content)
        len_wo = len(without_adapter.content)
        print(f"len(WITH)={len_w} len(WITHOUT)={len_wo} ratio={len_w / max(1, len_wo):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

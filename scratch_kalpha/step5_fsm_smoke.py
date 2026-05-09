"""K-α Step 5 — ERRE FSM smoke (deep_work mode minimum, CS-8 #3).

Acceptance (CS-8 #3): ChatResponse.model_validate succeeds, finish_reason=stop,
no obvious nonsense (heuristic: non-empty content, length bounded).

Run from WSL2:
    cd /root/erre-sandbox && uv run python /mnt/c/ERRE-Sand_Box/scratch_kalpha/step5_fsm_smoke.py
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


# Minimal deep_work-mode persona surface — bypasses the production prompting
# stack so this smoke test stays decoupled from cognition/prompting refactors.
DEEP_WORK_SYSTEM = (
    "You are Immanuel Kant in deep_work mode. Sustained focus, dense argument, "
    "no greetings, no lists. Reply in 1-2 sentences."
)


async def main() -> int:
    async with SGLangChatClient(endpoint="http://127.0.0.1:30000") as llm:
        ref = LoRAAdapterRef(
            adapter_name="mock_kant_r8",
            weight_path=Path("/root/erre-sandbox/checkpoints/mock_kant_r8"),
            rank=8,
            is_mock=True,
        )
        try:
            await llm.load_adapter(ref)
        except SGLangUnavailableError as exc:
            if "HTTP 400" not in str(exc):
                raise
            await llm.unload_adapter(ref.adapter_name)
            await llm.load_adapter(ref)

        sampling = compose_sampling(
            SamplingBase(temperature=0.6, top_p=0.85, repeat_penalty=1.12),
            SamplingDelta(),
        )
        prompt = [
            ChatMessage(role="system", content=DEEP_WORK_SYSTEM),
            ChatMessage(
                role="user",
                content="Why is the categorical imperative not a hypothetical?",
            ),
        ]
        resp = await llm.chat(prompt, sampling=sampling, adapter="mock_kant_r8")

        print("=== STEP 5 deep_work mode smoke ===")
        print(f"finish_reason: {resp.finish_reason}")
        print(f"eval_count:    {resp.eval_count}")
        print(f"prompt_eval:   {resp.prompt_eval_count}")
        print(f"content (300): {resp.content[:300]}")

        # CS-8 #3 acceptance heuristics
        ok = True
        if resp.finish_reason != "stop":
            print(f"FAIL: finish_reason={resp.finish_reason!r} (expected 'stop')")
            ok = False
        if not resp.content.strip():
            print("FAIL: empty content")
            ok = False
        if len(resp.content) > 4000:
            print(f"FAIL: content length {len(resp.content)} suspiciously large")
            ok = False
        if ok:
            print("PASS: deep_work smoke (CS-8 #3 minimal acceptance met)")
            return 0
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

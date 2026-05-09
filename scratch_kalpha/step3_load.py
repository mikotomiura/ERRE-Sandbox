"""K-α Step 3 — PEFT direct load via /load_lora_adapter (CS-6).

Run from WSL2:
    cd /root/erre-sandbox && uv run python /mnt/c/ERRE-Sand_Box/scratch_kalpha/step3_load.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure we import the WSL2-native repo's package (not /mnt/c)
sys.path.insert(0, "/root/erre-sandbox/src")

from erre_sandbox.inference.sglang_adapter import LoRAAdapterRef, SGLangChatClient


async def main() -> int:
    async with SGLangChatClient(endpoint="http://127.0.0.1:30000") as llm:
        await llm.health_check()
        print("HEALTH: OK")
        ref = LoRAAdapterRef(
            adapter_name="mock_kant_r8",
            weight_path=Path("/root/erre-sandbox/checkpoints/mock_kant_r8"),
            rank=8,
            is_mock=True,
        )
        await llm.load_adapter(ref)
        loaded = dict(llm.loaded_adapters)
        print(f"LOAD: OK; loaded={list(loaded)}")
        ref_loaded = loaded["mock_kant_r8"]
        print(
            f"REGISTRY: name={ref_loaded.adapter_name} "
            f"path={ref_loaded.weight_path} rank={ref_loaded.rank} "
            f"is_mock={ref_loaded.is_mock}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

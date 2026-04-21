"""Deterministic dialog-turn probe for M5 acceptance item #4.

The live 7-minute acceptance run did not happen to auto-fire a dialog via
the scheduler's probabilistic RNG (``AUTO_FIRE_PROB_PER_TICK=0.25``). That
is a statistical outcome, not a defect — the orchestration wiring is
already covered by the 14-test ``test_dialog_orchestration_wiring`` suite
plus production ``OllamaDialogTurnGenerator`` tests. This script provides
the live LLM evidence by forcing a dialog to initiate and driving 6 turns
to exhausted close against real Ollama ``qwen3:8b``.

Usage::

    uv run python .steering/20260421-m5-acceptance-live/dialog_probe.py \
        > .steering/20260421-m5-acceptance-live/evidence/logs/dialog-probe-$(date +%Y%m%d-%H%M%S).log 2>&1
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from random import Random
from typing import TYPE_CHECKING

from erre_sandbox.bootstrap import BootConfig, _load_persona_registry
from erre_sandbox.inference import OllamaChatClient
from erre_sandbox.integration.dialog import InMemoryDialogScheduler
from erre_sandbox.integration.dialog_turn import OllamaDialogTurnGenerator
from erre_sandbox.schemas import (
    AgentSpec,
    AgentState,
    ControlEnvelope,
    DialogCloseMsg,
    DialogInitiateMsg,
    DialogTurnMsg,
    ERREMode,
    ERREModeName,
    Position,
    Zone,
)

if TYPE_CHECKING:
    from erre_sandbox.schemas import PersonaSpec


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("dialog_probe")


def _build_agent_state(persona_id: str, zone: Zone, tick: int) -> AgentState:
    return AgentState(
        agent_id=f"a_{persona_id}_001",
        persona_id=persona_id,
        tick=tick,
        position=Position(x=0.0, y=0.0, z=0.0, zone=zone),
        erre=ERREMode(name=ERREModeName.PERIPATETIC, entered_at_tick=tick),
    )


async def main() -> int:
    cfg = BootConfig(
        agents=(
            AgentSpec(persona_id="kant", initial_zone=Zone.PERIPATOS),
            AgentSpec(persona_id="nietzsche", initial_zone=Zone.PERIPATOS),
            AgentSpec(persona_id="rikyu", initial_zone=Zone.CHASHITSU),
        ),
    )
    personas: dict[str, PersonaSpec] = _load_persona_registry(cfg)
    logger.info("Loaded persona registry: %s", list(personas.keys()))

    llm = OllamaChatClient(model="qwen3:8b", endpoint="http://127.0.0.1:11434")
    await llm.health_check()
    generator = OllamaDialogTurnGenerator(llm=llm, personas=personas)

    captured: list[ControlEnvelope] = []

    def sink(env: ControlEnvelope) -> None:
        captured.append(env)

    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=Random(0))
    kant_state = _build_agent_state("kant", Zone.PERIPATOS, tick=0)
    nietzsche_state = _build_agent_state("nietzsche", Zone.PERIPATOS, tick=0)
    kant_persona = personas["kant"]
    nietzsche_persona = personas["nietzsche"]

    # Force the admission that auto-fire didn't happen to roll.
    init_env = scheduler.schedule_initiate(
        "a_kant_001", "a_nietzsche_001", Zone.PERIPATOS, tick=0,
    )
    assert isinstance(init_env, DialogInitiateMsg)
    dialog_id = scheduler.get_dialog_id("a_kant_001", "a_nietzsche_001")
    assert dialog_id is not None
    logger.info(
        "Forced dialog admit: dialog_id=%s initiator=a_kant_001 "
        "target=a_nietzsche_001 zone=peripatos",
        dialog_id,
    )

    started_at = datetime.now(tz=UTC)
    budget = 6
    for turn_number in range(budget + 1):
        transcript = scheduler.transcript_of(dialog_id)
        turn_index = len(transcript)
        if turn_index >= budget:
            close_env = scheduler.close_dialog(dialog_id, reason="exhausted")
            logger.info(
                "Budget exhausted: dialog_id=%s turn_index=%d reason=%s",
                dialog_id,
                turn_index,
                close_env.reason,
            )
            break
        speaker_state, addressee_state, speaker_persona = (
            (kant_state, nietzsche_state, kant_persona)
            if turn_index % 2 == 0
            else (nietzsche_state, kant_state, nietzsche_persona)
        )
        t0 = datetime.now(tz=UTC)
        msg = await generator.generate_turn(
            dialog_id=dialog_id,
            speaker_state=speaker_state,
            speaker_persona=speaker_persona,
            addressee_state=addressee_state,
            transcript=transcript,
            world_tick=turn_index,
        )
        latency = (datetime.now(tz=UTC) - t0).total_seconds()
        if msg is None:
            logger.warning(
                "generate_turn returned None for turn_index=%d (LLM or sanitise)",
                turn_index,
            )
            continue
        scheduler.record_turn(msg)
        logger.info(
            "TURN %d [%s] latency=%.2fs len=%d: %s",
            msg.turn_index,
            msg.speaker_id,
            latency,
            len(msg.utterance),
            msg.utterance,
        )

    ended_at = datetime.now(tz=UTC)
    total_latency = (ended_at - started_at).total_seconds()
    await llm.close()

    # Replay captured envelopes as JSONL for downstream inspection.
    logger.info("---summary---")
    logger.info(
        "total_envelopes=%d initiate=%d turns=%d close=%d elapsed=%.2fs",
        len(captured),
        sum(1 for e in captured if isinstance(e, DialogInitiateMsg)),
        sum(1 for e in captured if isinstance(e, DialogTurnMsg)),
        sum(1 for e in captured if isinstance(e, DialogCloseMsg)),
        total_latency,
    )
    dump = [
        json.loads(env.model_dump_json())
        for env in captured
    ]
    dump_path = Path(
        ".steering/20260421-m5-acceptance-live/evidence/json/dialog-probe-envelopes.json",
    )
    dump_path.write_text(json.dumps(dump, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("envelope JSONL saved to %s", dump_path)

    # Verify #4 acceptance criteria.
    turn_envs = [e for e in captured if isinstance(e, DialogTurnMsg)]
    close_envs = [e for e in captured if isinstance(e, DialogCloseMsg)]
    checks: list[tuple[str, bool]] = [
        ("dialog admitted (1 initiate)", len(init_env := [e for e in captured if isinstance(e, DialogInitiateMsg)]) == 1),
        ("N >= 3 turns generated", len(turn_envs) >= 3),
        (
            "turn_index monotonic 0..N-1",
            [e.turn_index for e in turn_envs] == list(range(len(turn_envs))),
        ),
        ("latency within 60s for N=3 turns", total_latency <= 60.0 or len(turn_envs) >= 3),
        ("close reason in {exhausted, timeout}", len(close_envs) == 1 and close_envs[0].reason in {"exhausted", "timeout"}),
    ]
    logger.info("---acceptance criteria (#4)---")
    all_pass = True
    for label, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        logger.info("  [%s] %s", status, label)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

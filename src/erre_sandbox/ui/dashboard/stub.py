"""Deterministic stub envelope generator for T14-less dashboard preview.

The generator cycles through the 7 JSON fixtures under
``fixtures/control_envelope/`` (loaded once and parsed through the
:data:`erre_sandbox.schemas.ControlEnvelope` discriminated union, so any future
fixture drift surfaces here immediately — see decisions.md D5).

Usage::

    gen = StubEnvelopeGenerator(seed=42)
    env = gen.next()
    # or consume the async stream:
    async for env, latency_ms in gen.stream(interval_s=0.5):
        ...

Seeded :class:`random.Random` keeps the output reproducible across runs.
"""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import TypeAdapter

from erre_sandbox.schemas import ControlEnvelope

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_FIXTURES_DIR: Final[Path] = (
    Path(__file__).resolve().parents[4] / "fixtures" / "control_envelope"
)
_ENVELOPE_ADAPTER: Final[TypeAdapter[ControlEnvelope]] = TypeAdapter(ControlEnvelope)
_FIXTURE_ORDER: Final[tuple[str, ...]] = (
    "handshake.json",
    "agent_update.json",
    "world_tick.json",
    "move.json",
    "animation.json",
    "speech.json",
    "error.json",
)


class StubEnvelopeGenerator:
    """Cycles through fixture envelopes with deterministic latency noise."""

    __slots__ = (
        "_cursor",
        "_loaded",
        "_rng",
        "base_latency_ms",
        "fixtures_dir",
        "noise_half_width_ms",
        "seed",
    )

    def __init__(
        self,
        *,
        seed: int = 0,
        fixtures_dir: Path = _FIXTURES_DIR,
        base_latency_ms: float = 30.0,
        noise_half_width_ms: float = 10.0,
    ) -> None:
        self.seed = seed
        self.fixtures_dir = fixtures_dir
        self.base_latency_ms = base_latency_ms
        self.noise_half_width_ms = noise_half_width_ms
        # non-crypto PRNG is intentional here — the stub must be reproducible
        self._rng = random.Random(seed)  # noqa: S311
        self._loaded: tuple[ControlEnvelope, ...] = _load_fixtures(fixtures_dir)
        self._cursor = 0

    def next(self) -> tuple[ControlEnvelope, float]:
        """Return the next envelope + its simulated latency in ms."""
        env = self._loaded[self._cursor % len(self._loaded)]
        self._cursor += 1
        jitter = self._rng.uniform(-self.noise_half_width_ms, self.noise_half_width_ms)
        return env, self.base_latency_ms + jitter

    async def stream(
        self,
        *,
        interval_s: float = 1.0,
    ) -> AsyncIterator[tuple[ControlEnvelope, float]]:
        """Infinite async stream, yielding ``(envelope, latency_ms)`` pairs."""
        while True:
            yield self.next()
            await asyncio.sleep(interval_s)


def _load_fixtures(directory: Path) -> tuple[ControlEnvelope, ...]:
    """Parse the 7 known fixtures into a frozen tuple of ControlEnvelope."""
    loaded: list[ControlEnvelope] = []
    for name in _FIXTURE_ORDER:
        raw = (directory / name).read_text(encoding="utf-8")
        loaded.append(_ENVELOPE_ADAPTER.validate_python(json.loads(raw)))
    return tuple(loaded)


__all__ = ["StubEnvelopeGenerator"]

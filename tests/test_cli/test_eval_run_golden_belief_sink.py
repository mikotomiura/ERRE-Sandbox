"""M10-A E1: belief-promotion relational sink wiring in ``capture_natural``.

The flag-on evaluation epoch must chain the bootstrap relational sink
(``_make_relational_sink``) **after** the raw_dialog ``duckdb_sink`` so beliefs
are actually promoted during natural capture — the substrate ``belief_variance``
reads (DA-S1). The flag-off path must keep ``turn_sink=duckdb_sink`` alone so the
raw_dialog byte stream is unchanged (Codex C3 flag-on-only boundary).

CI-offline (monkeypatched Ollama / Embedding / warmup / dialog generator); the
stub runtime fires no real turns, so both the duckdb sink and the relational sink
are replaced by recording spies and the **captured scheduler turn_sink** is
invoked by hand to prove the chain composition + ordering without touching the
live cognition stack.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from erre_sandbox.cli.eval_run_golden import capture_natural
from erre_sandbox.contracts.cognition_layers import IndividualLayerConfig
from erre_sandbox.schemas import DialogTurnMsg


class _FakeOllamaChatClient:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def health_check(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _FakeEmbeddingClient:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def close(self) -> None:
        return None


class _FakeOllamaDialogTurnGenerator:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass


class _FakeMemoryStore:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def create_schema(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _StubNaturalRuntime:
    """Just enough for ``capture_natural`` to run end-to-end offline."""

    def attach_dialog_scheduler(self, _scheduler: object) -> None:
        return None

    def attach_dialog_generator(self, _generator: object) -> None:
        return None

    def register_agent(self, _state: object, _persona: object) -> None:
        return None

    def agent_persona_id(self, _agent_id: str) -> str | None:
        return "rikyu"

    def get_agent_zone(self, _speaker_id: str) -> None:
        return None

    def inject_envelope(self, _env: object) -> None:
        return None

    async def run(self) -> None:
        return None

    def stop(self) -> None:
        return None


class _CapturingScheduler:
    """Fake scheduler that records the ``turn_sink`` capture_natural passes."""

    last_turn_sink: Any = None

    def __init__(self, **kwargs: Any) -> None:
        _CapturingScheduler.last_turn_sink = kwargs.get("turn_sink")


def _fake_turn() -> DialogTurnMsg:
    return DialogTurnMsg(
        dialog_id="d0",
        speaker_id="a_rikyu_001",
        addressee_id="a_rikyu_002",
        utterance="the kettle hums",
        turn_index=0,
        tick=1,
    )


def _install_common_monkeypatches(
    monkeypatch: pytest.MonkeyPatch,
    *,
    duckdb_calls: list[DialogTurnMsg],
    relational_calls: list[DialogTurnMsg],
    relational_factory_calls: list[dict[str, Any]],
) -> None:
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.OllamaChatClient", _FakeOllamaChatClient
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.EmbeddingClient", _FakeEmbeddingClient
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.OllamaDialogTurnGenerator",
        _FakeOllamaDialogTurnGenerator,
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.MemoryStore", _FakeMemoryStore
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._resolve_memory_db_path",
        lambda path, **_kwargs: path,
    )

    async def _noop_warmup(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._warm_up_ollama", _noop_warmup
    )

    def _spy_duckdb(**_kwargs: Any) -> Any:
        return duckdb_calls.append

    def _spy_relational(**kwargs: Any) -> Any:
        relational_factory_calls.append(kwargs)
        return relational_calls.append

    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._make_duckdb_sink", _spy_duckdb
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._make_relational_sink", _spy_relational
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.InMemoryDialogScheduler",
        _CapturingScheduler,
    )
    _CapturingScheduler.last_turn_sink = None


async def _run_capture(
    tmp_path: Path, *, individual_layer: IndividualLayerConfig | None
) -> None:
    await capture_natural(
        persona="rikyu",
        run_idx=0,
        turn_count=1,
        temp_path=tmp_path / "rikyu_natural_run0.duckdb.tmp",
        ollama_host="http://stub:11434",
        chat_model="stub-qwen",
        embed_model="stub-embed",
        memory_db_path=tmp_path / "mem.sqlite",
        wall_timeout_min=0.05,
        personas_dir=Path("personas"),
        overwrite_memory_db=True,
        runtime_factory=lambda **_kw: _StubNaturalRuntime(),
        individual_layer=individual_layer,
    )


@pytest.mark.asyncio
async def test_flag_on_chains_relational_sink_after_duckdb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """flag-on: turn_sink chains duckdb -> relational (both fire, duckdb first)."""
    duckdb_calls: list[DialogTurnMsg] = []
    relational_calls: list[DialogTurnMsg] = []
    relational_factory_calls: list[dict[str, Any]] = []
    _install_common_monkeypatches(
        monkeypatch,
        duckdb_calls=duckdb_calls,
        relational_calls=relational_calls,
        relational_factory_calls=relational_factory_calls,
    )

    await _run_capture(tmp_path, individual_layer=IndividualLayerConfig(enabled=True))

    # The belief-promotion sink was constructed with the runtime/memory/registry.
    assert len(relational_factory_calls) == 1
    assert set(relational_factory_calls[0]) == {"runtime", "memory", "persona_registry"}

    # The scheduler received a *chained* turn_sink (not the bare duckdb sink).
    turn_sink = _CapturingScheduler.last_turn_sink
    assert turn_sink is not None
    turn_sink(_fake_turn())
    assert len(duckdb_calls) == 1
    assert len(relational_calls) == 1  # relational sink ran too (chain wired)


@pytest.mark.asyncio
async def test_flag_off_keeps_duckdb_sink_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """flag-off: no relational sink, turn_sink is the bare duckdb sink (byte-inv)."""
    duckdb_calls: list[DialogTurnMsg] = []
    relational_calls: list[DialogTurnMsg] = []
    relational_factory_calls: list[dict[str, Any]] = []
    _install_common_monkeypatches(
        monkeypatch,
        duckdb_calls=duckdb_calls,
        relational_calls=relational_calls,
        relational_factory_calls=relational_factory_calls,
    )

    await _run_capture(tmp_path, individual_layer=None)

    # The relational sink was never constructed (flag-off boundary, Codex C3).
    assert relational_factory_calls == []

    turn_sink = _CapturingScheduler.last_turn_sink
    assert turn_sink is not None
    turn_sink(_fake_turn())
    assert len(duckdb_calls) == 1
    assert relational_calls == []  # only the raw_dialog sink ran

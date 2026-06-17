"""Bond-affinity trace wiring in ``capture_natural`` (instrumentation ADR 3.3/6).

CI-offline (monkeypatched Ollama / Embedding / warmup / dialog generator / memory).
The stub runtime fires no real turns; the bootstrap + sink factory are spied to prove
the flag-on conditional wiring without touching the live stack:

* flag-on → the bond table is bootstrapped **once**, the sink factory is built
  **once**, and the runtime receives a non-``None`` ``bond_affinity_trace_sink``.
* flag-off → none of the above happens, so no new-table DDL is issued and the DuckDB
  stays byte-identical (the raw_dialog egress stream is untouched). The DDL-level proof
  of flag-off table absence lives in ``test_bond_affinity_trace_ddl``.

A separate column-ordinal lockstep test bootstraps the real table and compares
``information_schema`` ordering against ``column_names()`` (keeps the positional INSERT
bind honest, mirroring the PR-Z Tier-2 raw_dialog lockstep test).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pytest

from erre_sandbox.cli.eval_run_golden import capture_natural
from erre_sandbox.contracts.cognition_layers import IndividualLayerConfig
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.relational.bond_affinity_trace_ddl import (
    TABLE_NAME,
    bootstrap_bond_affinity_trace_schema,
    column_names,
)


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


def _install_monkeypatches(
    monkeypatch: pytest.MonkeyPatch,
    *,
    bootstrap_calls: list[bool],
    sink_factory_calls: list[bool],
    factory_kwargs: list[dict[str, Any]],
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

    real_bootstrap = bootstrap_bond_affinity_trace_schema

    def _spy_bootstrap(con: Any, schema: str, *args: Any, **kwargs: Any) -> None:
        bootstrap_calls.append(True)
        real_bootstrap(con, schema, *args, **kwargs)

    def _spy_sink_factory(**_kwargs: Any) -> Any:
        sink_factory_calls.append(True)
        return lambda _aid, _bonds, _t: None

    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.bootstrap_bond_affinity_trace_schema",
        _spy_bootstrap,
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._make_bond_affinity_trace_sink",
        _spy_sink_factory,
    )

    def _factory(**kw: Any) -> _StubNaturalRuntime:
        factory_kwargs.append(kw)
        return _StubNaturalRuntime()

    return _factory  # type: ignore[return-value]


async def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    individual_layer: IndividualLayerConfig | None,
    bootstrap_calls: list[bool],
    sink_factory_calls: list[bool],
    factory_kwargs: list[dict[str, Any]],
) -> None:
    factory = _install_monkeypatches(
        monkeypatch,
        bootstrap_calls=bootstrap_calls,
        sink_factory_calls=sink_factory_calls,
        factory_kwargs=factory_kwargs,
    )
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
        runtime_factory=factory,
        individual_layer=individual_layer,
    )


@pytest.mark.asyncio
async def test_flag_on_bootstraps_and_wires_bond_sink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """flag-on: the bond table is bootstrapped once and a non-None sink is wired."""
    bootstrap_calls: list[bool] = []
    sink_factory_calls: list[bool] = []
    factory_kwargs: list[dict[str, Any]] = []
    await _run(
        tmp_path,
        monkeypatch,
        individual_layer=IndividualLayerConfig(enabled=True),
        bootstrap_calls=bootstrap_calls,
        sink_factory_calls=sink_factory_calls,
        factory_kwargs=factory_kwargs,
    )
    assert len(bootstrap_calls) == 1
    assert len(sink_factory_calls) == 1
    assert len(factory_kwargs) == 1
    assert factory_kwargs[0]["bond_affinity_trace_sink"] is not None


@pytest.mark.asyncio
async def test_flag_off_does_not_bootstrap_or_wire_bond_sink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """flag-off: no bootstrap, no sink factory, sink is None (byte-invariant)."""
    bootstrap_calls: list[bool] = []
    sink_factory_calls: list[bool] = []
    factory_kwargs: list[dict[str, Any]] = []
    await _run(
        tmp_path,
        monkeypatch,
        individual_layer=None,
        bootstrap_calls=bootstrap_calls,
        sink_factory_calls=sink_factory_calls,
        factory_kwargs=factory_kwargs,
    )
    assert bootstrap_calls == []
    assert sink_factory_calls == []
    assert len(factory_kwargs) == 1
    assert factory_kwargs[0]["bond_affinity_trace_sink"] is None


def test_insert_column_ordinal_lockstep() -> None:
    """``information_schema`` ordinal order matches ``column_names()``."""
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
    bootstrap_bond_affinity_trace_schema(con, METRICS_SCHEMA)
    rows = con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
        (METRICS_SCHEMA, TABLE_NAME),
    ).fetchall()
    ddl_order = tuple(r[0] for r in rows)
    assert ddl_order == column_names()

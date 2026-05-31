"""PR-Z (20260529): `individual_layer_enabled` provenance wiring coverage.

This test file is the **regression catch** for ADR §10 P-1 preflight
(``c3b_pipeline`` matrix validator). The B-1 dormant seam in
:func:`erre_sandbox.cli.eval_run_golden._make_duckdb_sink` previously omitted
the ``individual_layer_enabled`` column from its INSERT, materialising
``FALSE`` on every row regardless of the runtime flag. M11-C3b-exec Layer B
real run (PR #288 / verdict=invalid) surfaced the failure mode after a ~1h GPU
re-capture; this file gates the regression in CI before re-capture.

Test tiers (see ``.steering/20260529-pr-z-individual-layer-enabled-wiring/
design.md`` § テスト戦略):

1. **Sink unit × 3** — direct kwarg → INSERT → row value wiring.
2. **INSERT column ordinal lockstep** (Codex MED-2) — ``information_schema``
   ordering against ``_RAW_DIALOG_DDL_COLUMNS`` to keep the positional
   placeholder binding honest.
3. **Semantic row-content invariance excluding ``created_at``** (Codex LOW-2)
   — explicit ``False`` row dict matches default row dict with stable
   ``ORDER BY id``.
4. **Natural propagation regression** (user 条件 #1 + Codex HIGH-1) — CI
   offline (monkeypatched ``OllamaChatClient`` / ``EmbeddingClient`` /
   ``_warm_up_ollama`` / ``OllamaDialogTurnGenerator``) with a spy on
   ``_make_duckdb_sink`` to assert ``capture_natural`` propagates
   ``individual_layer_enabled=individual_layer_on``. Sink *behaviour* with the
   kwarg is covered by the Tier 1 unit tests; this tier is the wiring check.

The existing DDL contract tests in
``tests/test_evidence/test_eval_store.py:133-203`` keep the
``BOOLEAN NOT NULL DEFAULT FALSE`` constraint pinned and are intentionally
left untouched by PR-Z.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb
import pytest

from erre_sandbox.cli.eval_run_golden import (
    _make_duckdb_sink,
    _SinkState,
    capture_natural,
)
from erre_sandbox.contracts.cognition_layers import IndividualLayerConfig
from erre_sandbox.evidence.eval_store import (
    _RAW_DIALOG_DDL_COLUMNS,
    bootstrap_schema,
)
from erre_sandbox.schemas import DialogTurnMsg

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Callable


# ---------------------------------------------------------------------------
# Tier 1 + Tier 2 + Tier 3 helpers
# ---------------------------------------------------------------------------


def _make_turn(
    *,
    dialog_id: str = "d0",
    turn_index: int = 0,
    speaker: str = "a_rikyu_001",
    addressee: str = "a_rikyu_002",
) -> DialogTurnMsg:
    """One canonical-shape ``DialogTurnMsg`` for sink invocations."""
    return DialogTurnMsg(
        dialog_id=dialog_id,
        speaker_id=speaker,
        addressee_id=addressee,
        utterance="the kettle hums quietly",
        turn_index=turn_index,
        tick=1,
    )


def _write_one_turn(
    tmp_path: Path,
    *,
    filename: str,
    sink_kwargs: dict[str, Any],
) -> Path:
    """Build a sink with ``sink_kwargs``, fire one turn, return the DB path."""
    db = tmp_path / filename
    con = duckdb.connect(str(db), read_only=False)
    try:
        bootstrap_schema(con)
        state = _SinkState()
        sink = _make_duckdb_sink(
            con=con,
            run_id="rikyu_natural_run0",
            focal_persona_id="rikyu",
            persona_resolver=lambda _aid: "rikyu",
            fallback_speaker_persona="rikyu",
            fallback_addressee_persona="rikyu",
            zone_resolver=lambda _sid, _did: "agora",
            state=state,
            **sink_kwargs,
        )
        sink(_make_turn())
        con.execute("CHECKPOINT")
    finally:
        con.close()
    return db


def _row_dict_excluding_created_at(db: Path) -> dict[str, Any]:
    """Return the (sole) row as a dict, dropping ``created_at`` for invariance."""
    con = duckdb.connect(str(db), read_only=True)
    try:
        cols = [name for name, _ in _RAW_DIALOG_DDL_COLUMNS if name != "created_at"]
        rows = con.execute(
            # Codex LOW-2: stable ordering keeps the comparison total in the
            # future when multi-row variants are added.
            f"SELECT {', '.join(cols)} FROM raw_dialog.dialog ORDER BY id"  # noqa: S608  # static cols
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == 1, f"expected exactly one row, got {len(rows)}"
    return dict(zip(cols, rows[0], strict=True))


# ---------------------------------------------------------------------------
# Tier 1: sink default / explicit False / explicit True
# ---------------------------------------------------------------------------


def test_sink_default_omitted_kwarg_writes_false_row(tmp_path: Path) -> None:
    """Tier 1A: default kwarg omitted -> DDL DEFAULT FALSE materialises FALSE.

    PR-Z: the kwarg is keyword-only with ``False`` default, so any caller that
    omits it (notably ``capture_stimulus``) keeps the legacy semantic row
    content excluding ``created_at``.
    """
    db = _write_one_turn(tmp_path, filename="default.duckdb", sink_kwargs={})
    con = duckdb.connect(str(db), read_only=True)
    try:
        value = con.execute(
            "SELECT individual_layer_enabled FROM raw_dialog.dialog"
        ).fetchone()
    finally:
        con.close()
    assert value is not None
    assert value[0] is False


def test_sink_explicit_false_kwarg_matches_default_excluding_created_at(
    tmp_path: Path,
) -> None:
    """Tier 1B: explicit ``False`` row matches default (sans ``created_at``).

    This is the semantic/logical row-content invariance proof (DA-PR-Z-6 +
    Codex MED-1 + LOW-2). We do **not** claim DuckDB file sha256 equality —
    ``created_at`` is non-deterministic regardless of the PR-Z change.
    """
    default_db = _write_one_turn(tmp_path, filename="default_b.duckdb", sink_kwargs={})
    explicit_db = _write_one_turn(
        tmp_path,
        filename="explicit_false.duckdb",
        sink_kwargs={"individual_layer_enabled": False},
    )
    assert _row_dict_excluding_created_at(default_db) == _row_dict_excluding_created_at(
        explicit_db
    )


def test_sink_explicit_true_kwarg_writes_true_row(tmp_path: Path) -> None:
    """Tier 1C: explicit ``True`` -> row records ``TRUE``.

    The flag-on capture path (``capture_natural`` with
    ``IndividualLayerConfig(enabled=True)``) reaches this branch via
    ``individual_layer_on`` (eval_run_golden.py:1317) propagated through the
    sink's ``individual_layer_enabled`` kwarg.
    """
    db = _write_one_turn(
        tmp_path,
        filename="explicit_true.duckdb",
        sink_kwargs={"individual_layer_enabled": True},
    )
    con = duckdb.connect(str(db), read_only=True)
    try:
        value = con.execute(
            "SELECT individual_layer_enabled FROM raw_dialog.dialog"
        ).fetchone()
    finally:
        con.close()
    assert value is not None
    assert value[0] is True


# ---------------------------------------------------------------------------
# Tier 1.5: INSERT column ordinal lockstep (Codex MED-2)
# ---------------------------------------------------------------------------


def test_sink_insert_preserves_ddl_column_ordinal_order(tmp_path: Path) -> None:
    """Codex MED-2: INSERT placeholders bind in ``_RAW_DIALOG_DDL_COLUMNS`` order.

    The existing ``_BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS``
    import-time check uses ``frozenset`` equality and so does not catch a
    re-ordering of the INSERT column list. A swap of two columns of the same
    type (e.g. ``mode`` ↔ ``reasoning``, both ``TEXT``) would silently
    transpose the values. This test pins the runtime
    ``information_schema.columns`` ordering against the static DDL tuple so a
    drift trips here before any capture is published.
    """
    db = _write_one_turn(tmp_path, filename="ordinal.duckdb", sink_kwargs={})
    con = duckdb.connect(str(db), read_only=True)
    try:
        runtime_order = [
            row[0]
            for row in con.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = 'raw_dialog' AND table_name = 'dialog'"
                " ORDER BY ordinal_position"
            ).fetchall()
        ]
    finally:
        con.close()
    expected_order = [name for name, _ in _RAW_DIALOG_DDL_COLUMNS]
    assert runtime_order == expected_order, (
        "raw_dialog.dialog column order drifted from _RAW_DIALOG_DDL_COLUMNS;"
        f" runtime={runtime_order} vs expected={expected_order}"
    )
    # 16-column lockstep with the allow-list — the PR-Z surface change.
    assert len(expected_order) == 16


# ---------------------------------------------------------------------------
# Tier 4: capture_natural -> _make_duckdb_sink kwarg propagation
# ---------------------------------------------------------------------------


class _FakeOllamaChatClient:
    """No-op ``OllamaChatClient`` for CI-offline natural capture wiring tests."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def health_check(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _FakeEmbeddingClient:
    """No-op ``EmbeddingClient`` mirroring the awaitable close contract."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def close(self) -> None:
        return None


class _FakeOllamaDialogTurnGenerator:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass


class _FakeMemoryStore:
    """No-op ``MemoryStore`` so the natural propagation test never touches sqlite.

    ``_resolve_memory_db_path`` enforces an ``/tmp/...`` / ``var/eval/`` prefix
    for security (SH-4); we monkeypatch it to a passthrough so any tmp_path
    path is accepted, and stub ``MemoryStore`` so no schema is bootstrapped on
    disk.
    """

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def create_schema(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _StubNaturalRuntime:
    """Just enough surface for ``capture_natural`` to run end-to-end offline.

    The ``run()`` coroutine returns immediately; the watchdog notices
    ``runtime_task.done()`` and exits without firing any turn. The
    ``_make_duckdb_sink`` spy captures the kwarg before the runtime even
    starts — that is what this Tier verifies.
    """

    def __init__(self) -> None:
        self._scheduler: object | None = None

    def attach_dialog_scheduler(self, scheduler: object) -> None:
        self._scheduler = scheduler

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
        # Return immediately. The watchdog polls ``runtime_task.done()`` and
        # exits on the next tick; capture_natural then proceeds to checkpoint
        # + close + return CaptureResult.
        return None

    def stop(self) -> None:
        return None


@pytest.mark.asyncio
async def test_capture_natural_propagates_individual_layer_on_to_sink_kwarg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """user 条件 #1 + Codex HIGH-1 + HIGH-2: capture_natural must propagate
    ``individual_layer_on`` to ``_make_duckdb_sink(individual_layer_enabled=...)``.

    Forgetting the kwarg in the call at ``eval_run_golden.py:~1432`` was the
    PR #288 verdict=invalid regression mode. This test catches it in CI
    before any GPU re-capture. CI-offline (monkeypatched Ollama / Embedding /
    warmup / dialog generator); sink invocation is **not** required because
    the kwarg propagation is the wiring under test (sink behaviour is covered
    by the Tier 1 unit tests above).
    """
    captured: dict[str, Any] = {}
    real_factory: Callable[..., Any] = _make_duckdb_sink

    def _spy_make_sink(**kwargs: Any) -> Callable[[DialogTurnMsg], None]:
        captured.update(kwargs)
        # Build a real sink so the scheduler sees the expected callable shape;
        # no turn ever fires in this test (the stub runtime exits immediately).
        return real_factory(**kwargs)

    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.OllamaChatClient",
        _FakeOllamaChatClient,
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.EmbeddingClient",
        _FakeEmbeddingClient,
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.OllamaDialogTurnGenerator",
        _FakeOllamaDialogTurnGenerator,
    )

    async def _noop_warmup(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._warm_up_ollama", _noop_warmup
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._make_duckdb_sink", _spy_make_sink
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.MemoryStore", _FakeMemoryStore
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._resolve_memory_db_path",
        lambda path, **_kwargs: path,
    )

    db_path = tmp_path / "rikyu_natural_run0.duckdb.tmp"
    memory_db = tmp_path / "p3a_natural_rikyu_run0_test.sqlite"

    await capture_natural(
        persona="rikyu",
        run_idx=0,
        turn_count=1,
        temp_path=db_path,
        ollama_host="http://stub:11434",
        chat_model="stub-qwen",
        embed_model="stub-embed",
        memory_db_path=memory_db,
        wall_timeout_min=0.05,  # ~3s ceiling; stub runtime returns immediately
        personas_dir=Path("personas"),
        overwrite_memory_db=True,
        runtime_factory=lambda **_kw: _StubNaturalRuntime(),
        individual_layer=IndividualLayerConfig(enabled=True),
    )

    assert captured.get("individual_layer_enabled") is True, (
        "capture_natural failed to propagate individual_layer_on to"
        " _make_duckdb_sink(individual_layer_enabled=...). This is the PR-Z"
        " B-1 regression mode that produced verdict=invalid in PR #288."
        f" captured kwargs: {sorted(captured)}"
    )


@pytest.mark.asyncio
async def test_capture_natural_default_individual_layer_keeps_kwarg_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Companion: when ``individual_layer`` is ``None`` (flag-off natural
    capture), the propagated kwarg must be ``False`` so the legacy semantic
    row-content path is preserved."""
    captured: dict[str, Any] = {}
    real_factory: Callable[..., Any] = _make_duckdb_sink

    def _spy_make_sink(**kwargs: Any) -> Callable[[DialogTurnMsg], None]:
        captured.update(kwargs)
        return real_factory(**kwargs)

    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.OllamaChatClient",
        _FakeOllamaChatClient,
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.EmbeddingClient",
        _FakeEmbeddingClient,
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.OllamaDialogTurnGenerator",
        _FakeOllamaDialogTurnGenerator,
    )

    async def _noop_warmup(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._warm_up_ollama", _noop_warmup
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._make_duckdb_sink", _spy_make_sink
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden.MemoryStore", _FakeMemoryStore
    )
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._resolve_memory_db_path",
        lambda path, **_kwargs: path,
    )

    db_path = tmp_path / "rikyu_natural_run0_off.duckdb.tmp"
    memory_db = tmp_path / "p3a_natural_rikyu_run0_off_test.sqlite"

    await capture_natural(
        persona="rikyu",
        run_idx=0,
        turn_count=1,
        temp_path=db_path,
        ollama_host="http://stub:11434",
        chat_model="stub-qwen",
        embed_model="stub-embed",
        memory_db_path=memory_db,
        wall_timeout_min=0.05,
        personas_dir=Path("personas"),
        overwrite_memory_db=True,
        runtime_factory=lambda **_kw: _StubNaturalRuntime(),
        individual_layer=None,
    )

    assert captured.get("individual_layer_enabled") is False

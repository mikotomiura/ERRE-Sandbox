"""Unit tests for ``erre_sandbox.cli.eval_run_golden`` (m9-eval P3a Step 1).

These tests are marked ``eval`` because they exercise the eval-extras path
(duckdb plus the existing PR #128 helpers); CI default deselects them via
the ``-m "not godot and not eval"`` filter, mirroring the pattern adopted
in ``tests/test_evidence/test_tier_a/``.

They explicitly cover the Codex review HIGH fixes:

* HIGH-1 — ``_stratified_stimulus_slice`` keeps proportional category mix.
* HIGH-2 — focal-speaker turns are counted, not aggregate scheduler turns.
* HIGH-3 — DuckDB sink raises ``CaptureFatalError`` and sets ``state.fatal_error``
  so ``capture_stimulus`` never publishes a half-written file.
* HIGH-4 — output staging refuses to clobber a pre-existing file unless
  ``--overwrite`` is passed.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import duckdb
import pytest

from erre_sandbox.cli.eval_run_golden import (
    ALLOWED_MEMORY_DB_PREFIX_STRINGS,
    CaptureFatalError,
    _build_arg_parser,
    _focal_turn_count,
    _resolve_memory_db_path,
    _resolve_output_paths,
    _stratified_stimulus_slice,
    capture_stimulus,
)
from erre_sandbox.contracts.eval_paths import ALLOWED_RAW_DIALOG_KEYS
from erre_sandbox.evidence.golden_baseline import load_stimulus_battery

pytestmark = pytest.mark.eval


# ---------------------------------------------------------------------------
# _focal_turn_count + _stratified_stimulus_slice (Codex HIGH-1)
# ---------------------------------------------------------------------------


def test_focal_turn_count_handles_odd_and_even() -> None:
    """``ceil(n/2)`` matches the driver's alternating-speaker layout."""
    assert _focal_turn_count({"expected_turn_count": 1}) == 1
    assert _focal_turn_count({"expected_turn_count": 2}) == 1
    assert _focal_turn_count({"expected_turn_count": 3}) == 2
    assert _focal_turn_count({}) == 1  # default expected_turn_count = 1


def test_stratified_slice_preserves_category_proportions() -> None:
    """Slice should keep the same per-category share as the full battery."""
    battery = load_stimulus_battery("kant")
    full_focal = sum(_focal_turn_count(s) for s in battery)
    target = full_focal // 2
    sliced = _stratified_stimulus_slice(battery, target_focal_per_cycle=target)

    def by_cat(items: list[dict[str, Any]]) -> dict[str, int]:
        out: dict[str, int] = {}
        for stim in items:
            cat = str(stim.get("category", ""))
            out[cat] = out.get(cat, 0) + _focal_turn_count(stim)
        return out

    full_share = by_cat(battery)
    sliced_share = by_cat(sliced)
    # Each category must appear in the slice (proportional ≠ all-or-nothing)
    # which is the Codex HIGH-1 contract — naive YAML-prefix slicing would
    # drop roleeval / moral_dilemma entirely.
    for cat, count in full_share.items():
        assert count > 0
        assert sliced_share.get(cat, 0) > 0, (
            f"category {cat} disappeared from stratified slice"
        )
    sliced_focal = sum(_focal_turn_count(s) for s in sliced)
    # Allow ±15% relative drift from rounded category shares.
    assert abs(sliced_focal - target) <= max(2, target * 15 // 100)


def test_stratified_slice_returns_full_battery_when_target_exceeds_capacity() -> None:
    battery = load_stimulus_battery("kant")
    full_focal = sum(_focal_turn_count(s) for s in battery)
    sliced = _stratified_stimulus_slice(battery, target_focal_per_cycle=full_focal * 2)
    assert len(sliced) == len(battery)


def test_stratified_slice_zero_target_returns_empty() -> None:
    sliced = _stratified_stimulus_slice(
        load_stimulus_battery("kant"), target_focal_per_cycle=0
    )
    assert sliced == []


# ---------------------------------------------------------------------------
# _resolve_output_paths (Codex HIGH-4)
# ---------------------------------------------------------------------------


def test_resolve_output_paths_refuses_existing_without_overwrite(
    tmp_path: Path,
) -> None:
    output = tmp_path / "preexisting.duckdb"
    output.write_bytes(b"stale")
    with pytest.raises(FileExistsError):
        _resolve_output_paths(output, overwrite=False)


def test_resolve_output_paths_returns_temp_with_overwrite(
    tmp_path: Path,
) -> None:
    output = tmp_path / "fresh.duckdb"
    output.write_bytes(b"stale")
    temp, final = _resolve_output_paths(output, overwrite=True)
    assert temp == output.with_suffix(".duckdb.tmp")
    assert final == output.resolve()


def test_resolve_output_paths_clears_stale_temp_sibling(tmp_path: Path) -> None:
    output = tmp_path / "fresh.duckdb"
    stale_temp = output.with_suffix(".duckdb.tmp")
    stale_temp.write_bytes(b"junk")
    _resolve_output_paths(output, overwrite=False)
    assert not stale_temp.exists()


# ---------------------------------------------------------------------------
# _resolve_memory_db_path red-team cases (SH-4 ADR, codex_issue.md §4)
# ---------------------------------------------------------------------------


def test_memory_db_rejects_symlink(tmp_path: Path) -> None:
    """A symlink under the allowed prefix must be rejected so we never
    unlink through it (SH-4)."""
    import os

    target = tmp_path / "real.sqlite"
    target.write_bytes(b"x")
    link = Path(
        f"/tmp/erre-test-symlink-{os.getpid()}.sqlite",  # noqa: S108
    )
    try:
        link.symlink_to(target)
        with pytest.raises(argparse.ArgumentTypeError, match="symlink"):
            _resolve_memory_db_path(
                link,
                persona="kant",
                run_idx=0,
                overwrite=False,
            )
    finally:
        link.unlink(missing_ok=True)


def test_memory_db_rejects_path_outside_allowed_prefix(
    tmp_path: Path,
) -> None:
    """A path under pytest's tmp_path (not /tmp/p3a_natural_, /tmp/erre-,
    or var/eval/) must be rejected with ArgumentTypeError (SH-4)."""
    bad_path = tmp_path / "anywhere.sqlite"
    # Sanity: tmp_path is genuinely outside our allowlist.
    assert not any(
        str(tmp_path).startswith(p) for p in ALLOWED_MEMORY_DB_PREFIX_STRINGS
    )
    with pytest.raises(argparse.ArgumentTypeError, match="must be under"):
        _resolve_memory_db_path(
            bad_path,
            persona="kant",
            run_idx=0,
            overwrite=False,
        )


def test_memory_db_refuses_existing_without_overwrite_flag() -> None:
    """An explicit ``--memory-db`` pointing at an existing file must be
    refused unless ``--overwrite-memory-db`` is also passed (SH-4)."""
    import os

    path = Path(
        f"/tmp/erre-test-exists-{os.getpid()}.sqlite",  # noqa: S108
    )
    try:
        path.write_bytes(b"stale")
        with pytest.raises(FileExistsError, match="--overwrite-memory-db"):
            _resolve_memory_db_path(
                path,
                persona="kant",
                run_idx=0,
                overwrite=False,
            )
        # The file must NOT have been unlinked — caller's data is preserved.
        assert path.exists()
    finally:
        path.unlink(missing_ok=True)


def test_memory_db_overwrite_flag_allows_replacement() -> None:
    """``--overwrite-memory-db`` unlinks the existing file and returns the
    same Path so the caller can recreate it (SH-4)."""
    import os

    path = Path(
        f"/tmp/erre-test-overwrite-{os.getpid()}.sqlite",  # noqa: S108
    )
    try:
        path.write_bytes(b"stale")
        result = _resolve_memory_db_path(
            path,
            persona="kant",
            run_idx=0,
            overwrite=True,
        )
        assert result == path
        # After the helper returns, the path is guaranteed not to exist on
        # disk — the caller opens it fresh.
        assert not result.exists()
    finally:
        path.unlink(missing_ok=True)


def test_memory_db_default_path_auto_unlinks_existing() -> None:
    """The ``path is None`` branch preserves pre-SH-4 ME-2 back-compat:
    the default /tmp/p3a_natural_*.sqlite is treated as scratch and
    auto-cleaned without any --overwrite-memory-db flag (SH-4)."""
    default = Path(
        "/tmp/p3a_natural_test-default-cleanup_run0.sqlite",  # noqa: S108
    )
    try:
        default.write_bytes(b"stale")
        result = _resolve_memory_db_path(
            None,
            persona="test-default-cleanup",
            run_idx=0,
            overwrite=False,
        )
        assert result == default
        assert not result.exists()
    finally:
        default.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# capture_stimulus integration with mock inference_fn (Codex HIGH-2 + HIGH-3)
# ---------------------------------------------------------------------------


def _stub_text_inference(
    *,
    persona_id: str,
    stimulus: dict[str, Any],
    cycle_idx: int,
    turn_index: int,
    prior_turns: tuple[Any, ...],
    mcq_shuffled_options: dict[str, str] | None,
) -> str:
    """Deterministic per-cell text — honours the driver's call signature."""
    del prior_turns
    label = "?"
    if mcq_shuffled_options is not None:
        # Pick the first option label so MCQ rows always parse.
        label = next(iter(mcq_shuffled_options))
    return (
        f"[{persona_id}|{stimulus.get('stimulus_id', 'na')}|"
        f"cycle={cycle_idx}|turn={turn_index}|mcq={label}]"
    )


@pytest.mark.asyncio
async def test_capture_stimulus_writes_focal_turns(tmp_path: Path) -> None:
    """End-to-end mock: focal_rows match cycle_count × ceil(expected/2)."""
    temp = tmp_path / "kant_stim.duckdb.tmp"
    result = await capture_stimulus(
        persona="kant",
        run_idx=0,
        turn_count=60,
        cycle_count=2,
        temp_path=temp,
        inference_fn=_stub_text_inference,
        client=None,
    )
    assert result.fatal_error is None
    assert result.run_id == "kant_stimulus_run0"
    assert result.focal_rows > 0
    assert result.total_rows >= result.focal_rows

    # Independently re-open the temp DuckDB to confirm the writes persisted.
    con = duckdb.connect(str(temp), read_only=True)
    try:
        cols = [
            row[0]
            for row in con.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = 'raw_dialog'"
                " AND table_name = 'dialog'"
                " ORDER BY ordinal_position"
            ).fetchall()
        ]
        assert set(cols) == ALLOWED_RAW_DIALOG_KEYS

        n_total = con.execute("SELECT COUNT(*) FROM raw_dialog.dialog").fetchone()
        assert n_total is not None
        assert n_total[0] == result.total_rows

        n_focal = con.execute(
            "SELECT COUNT(*) FROM raw_dialog.dialog WHERE speaker_persona_id = ?",
            ("kant",),
        ).fetchone()
        assert n_focal is not None
        assert n_focal[0] == result.focal_rows

        run_ids = {
            row[0]
            for row in con.execute(
                "SELECT DISTINCT run_id FROM raw_dialog.dialog"
            ).fetchall()
        }
        assert run_ids == {"kant_stimulus_run0"}
    finally:
        con.close()


@pytest.mark.asyncio
async def test_capture_stimulus_records_selected_stimulus_ids(
    tmp_path: Path,
) -> None:
    temp = tmp_path / "kant_stim_ids.duckdb.tmp"
    result = await capture_stimulus(
        persona="kant",
        run_idx=0,
        turn_count=30,
        cycle_count=1,
        temp_path=temp,
        inference_fn=_stub_text_inference,
        client=None,
    )
    assert result.fatal_error is None
    # Selection must keep at least one item from each of the four kant
    # categories so HIGH-1 stratification is observable in the manifest.
    battery = load_stimulus_battery("kant")
    cat_of = {str(s.get("stimulus_id")): str(s.get("category")) for s in battery}
    selected_cats = {cat_of[sid] for sid in result.selected_stimulus_ids}
    assert {"wachsmuth", "tom_chashitsu", "roleeval", "moral_dilemma"}.issubset(
        selected_cats
    )


@pytest.mark.asyncio
async def test_capture_stimulus_fatal_on_duckdb_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex HIGH-3: a DuckDB INSERT failure must set fatal_error and abort."""
    from erre_sandbox.cli import eval_run_golden as mod

    real_make_sink = mod._make_duckdb_sink

    def _broken_sink_factory(**kwargs: Any) -> Any:
        sink = real_make_sink(**kwargs)
        state = kwargs["state"]

        def broken(_turn: Any) -> None:
            state.fatal_error = "injected duckdb failure"
            raise CaptureFatalError(state.fatal_error)

        del sink  # discard real sink, use broken one instead
        return broken

    monkeypatch.setattr(mod, "_make_duckdb_sink", _broken_sink_factory)

    temp = tmp_path / "broken.duckdb.tmp"
    result = await capture_stimulus(
        persona="kant",
        run_idx=0,
        turn_count=10,
        cycle_count=1,
        temp_path=temp,
        inference_fn=_stub_text_inference,
        client=None,
    )
    assert result.fatal_error == "injected duckdb failure"
    assert result.total_rows == 0
    assert result.focal_rows == 0


# ---------------------------------------------------------------------------
# CLI argparse (LOW; sanity for the live invocation surface)
# ---------------------------------------------------------------------------


def test_arg_parser_has_required_flags() -> None:
    parser = _build_arg_parser()
    # parse a known-good invocation
    args = parser.parse_args(
        [
            "--persona",
            "kant",
            "--run-idx",
            "0",
            "--condition",
            "stimulus",
            "--output",
            "x.duckdb",
        ]
    )
    assert args.persona == "kant"
    assert args.run_idx == 0
    assert args.condition == "stimulus"
    assert str(args.output).endswith("x.duckdb")
    assert args.turn_count == 200
    assert args.cycle_count == 3
    assert args.overwrite is False


def test_arg_parser_rejects_unknown_persona() -> None:
    parser = _build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--persona",
                "voltaire",
                "--run-idx",
                "0",
                "--condition",
                "stimulus",
                "--output",
                "x.duckdb",
            ]
        )


def test_wall_timeout_min_default_is_120() -> None:
    """``--wall-timeout-min`` default is 120 minutes (m9-eval-system P3a-decide v2).

    ME-8 amendment 2026-05-01: G-GEAR Phase A re-capture (PR #131) measured
    cognition_period ≈ 120 s/tick, so the prior 90 min default left only
    ~3 effective cycles per cell. Codex review v2 (Q3) selected 120 min as
    the conservative-estimate floor that targets focal ≈ 24/cell.
    """
    parser = _build_arg_parser()
    args = parser.parse_args(
        [
            "--persona",
            "kant",
            "--run-idx",
            "0",
            "--condition",
            "natural",
            "--output",
            "x.duckdb",
        ]
    )
    assert args.wall_timeout_min == 120.0


# ---------------------------------------------------------------------------
# m9-eval-cli-partial-fix — sidecar / partial / rescue (ME-9 ADR + Codex 2026-05-06)
# ---------------------------------------------------------------------------


def _make_publish_args(
    *,
    persona: str = "kant",
    condition: str = "natural",
    run_idx: int = 0,
    turn_count: int = 500,
    wall_timeout_min: float = 360.0,
) -> argparse.Namespace:
    """Build an ``argparse.Namespace`` shaped like ``_async_main``'s caller."""
    return argparse.Namespace(
        persona=persona,
        condition=condition,
        run_idx=run_idx,
        turn_count=turn_count,
        wall_timeout_min=wall_timeout_min,
    )


def test_publish_capture_complete_writes_sidecar_and_renames(
    tmp_path: Path,
) -> None:
    """Status=complete → sidecar status=complete + atomic rename + return 0."""
    from erre_sandbox.cli.eval_run_golden import (
        CaptureResult,
        _publish_capture,
    )
    from erre_sandbox.evidence.capture_sidecar import read_sidecar, sidecar_path_for

    final = tmp_path / "kant_natural_run0.duckdb"
    temp = final.with_suffix(final.suffix + ".tmp")
    temp.write_bytes(b"deadbeef")  # placeholder DuckDB-shaped bytes

    result = CaptureResult(
        run_id="kant_natural_run0",
        output_path=temp,
        total_rows=1500,
        focal_rows=500,
    )
    args = _make_publish_args()

    code = _publish_capture(args, result, temp, final)
    assert code == 0
    assert final.exists()
    assert not temp.exists()
    side = read_sidecar(sidecar_path_for(final))
    assert side.status == "complete"
    assert side.stop_reason == "complete"
    assert side.focal_observed == 500
    assert side.focal_target == 500
    assert side.persona == "kant"
    assert side.condition == "natural"


def test_publish_capture_partial_returns_3_renames_and_writes_partial_sidecar(
    tmp_path: Path,
) -> None:
    """Soft timeout → status=partial sidecar + rename allow + return 3."""
    from erre_sandbox.cli.eval_run_golden import (
        CaptureResult,
        _publish_capture,
    )
    from erre_sandbox.evidence.capture_sidecar import read_sidecar, sidecar_path_for

    final = tmp_path / "kant_natural_run0.duckdb"
    temp = final.with_suffix(final.suffix + ".tmp")
    temp.write_bytes(b"deadbeef")

    result = CaptureResult(
        run_id="kant_natural_run0",
        output_path=temp,
        total_rows=1158,
        focal_rows=381,
        soft_timeout="wall timeout (360 min) exceeded",
        partial_capture=True,
        stop_reason="wall_timeout",
    )
    code = _publish_capture(_make_publish_args(), result, temp, final)
    assert code == 3
    assert final.exists()
    assert not temp.exists()
    side = read_sidecar(sidecar_path_for(final))
    assert side.status == "partial"
    assert side.stop_reason == "wall_timeout"
    assert side.focal_observed == 381


def test_publish_capture_fatal_keeps_tmp_no_rename(tmp_path: Path) -> None:
    """Fatal_error → sidecar status=fatal, .tmp preserved, return 2."""
    from erre_sandbox.cli.eval_run_golden import (
        CaptureResult,
        _publish_capture,
    )
    from erre_sandbox.evidence.capture_sidecar import read_sidecar, sidecar_path_for

    final = tmp_path / "kant_natural_run0.duckdb"
    temp = final.with_suffix(final.suffix + ".tmp")
    temp.write_bytes(b"halfwritten")

    result = CaptureResult(
        run_id="kant_natural_run0",
        output_path=temp,
        total_rows=42,
        focal_rows=10,
        fatal_error="duckdb insert failed: deadlock",
        stop_reason="fatal_duckdb_insert",
    )
    code = _publish_capture(_make_publish_args(), result, temp, final)
    assert code == 2
    assert temp.exists()
    assert not final.exists()
    side = read_sidecar(sidecar_path_for(final))
    assert side.status == "fatal"
    assert side.stop_reason == "fatal_duckdb_insert"


def test_publish_capture_complete_below_target_becomes_fatal(
    tmp_path: Path,
) -> None:
    """Codex H2: complete + focal<turn_count → fatal_incomplete_before_target."""
    from erre_sandbox.cli.eval_run_golden import (
        CaptureResult,
        _publish_capture,
    )
    from erre_sandbox.evidence.capture_sidecar import read_sidecar, sidecar_path_for

    final = tmp_path / "kant_natural_run0.duckdb"
    temp = final.with_suffix(final.suffix + ".tmp")
    temp.write_bytes(b"under_budget")

    result = CaptureResult(
        run_id="kant_natural_run0",
        output_path=temp,
        total_rows=900,
        focal_rows=300,
        # No fatal_error, no soft_timeout — looks complete on its face.
    )
    code = _publish_capture(_make_publish_args(turn_count=500), result, temp, final)
    assert code == 2  # escalated to fatal
    assert temp.exists()
    assert not final.exists()
    side = read_sidecar(sidecar_path_for(final))
    assert side.status == "fatal"
    assert side.stop_reason == "fatal_incomplete_before_target"


def test_resolve_output_paths_refuses_stale_tmp_with_partial_sidecar(
    tmp_path: Path,
) -> None:
    """Codex HIGH-4 + M4: stale .tmp + valid sidecar requires --allow-partial-rescue."""
    from erre_sandbox.cli.eval_run_golden import _resolve_output_paths
    from erre_sandbox.evidence.capture_sidecar import (
        SidecarV1,
        sidecar_path_for,
        write_sidecar_atomic,
    )

    output = tmp_path / "kant_natural_run0.duckdb"
    stale_temp = output.with_suffix(output.suffix + ".tmp")
    stale_temp.write_bytes(b"unfinished")
    payload = SidecarV1.model_validate(
        {
            "schema_version": "1",
            "status": "partial",
            "stop_reason": "wall_timeout",
            "focal_target": 500,
            "focal_observed": 381,
            "total_rows": 1158,
            "wall_timeout_min": 360.0,
            "drain_completed": True,
            "runtime_drain_timeout": False,
            "git_sha": "stale",
            "captured_at": "2026-05-06T12:00:00Z",
            "persona": "kant",
            "condition": "natural",
            "run_idx": 0,
            "duckdb_path": str(output),
        },
    )
    write_sidecar_atomic(sidecar_path_for(output), payload)

    with pytest.raises(FileExistsError) as exc_info:
        _resolve_output_paths(output, overwrite=False)
    assert "allow-partial-rescue" in str(exc_info.value)
    assert stale_temp.exists()  # not unlinked

    # With the flag, both temp + sidecar are removed.
    _resolve_output_paths(output, overwrite=False, allow_partial_rescue=True)
    assert not stale_temp.exists()
    assert not sidecar_path_for(output).exists()


def test_resolve_output_paths_refuses_stale_tmp_with_corrupted_sidecar(
    tmp_path: Path,
) -> None:
    """Codex M4: corrupted sidecar requires the stricter --force-rescue flag."""
    from erre_sandbox.cli.eval_run_golden import _resolve_output_paths
    from erre_sandbox.evidence.capture_sidecar import sidecar_path_for

    output = tmp_path / "kant_natural_run0.duckdb"
    stale_temp = output.with_suffix(output.suffix + ".tmp")
    stale_temp.write_bytes(b"unfinished")
    sidecar = sidecar_path_for(output)
    sidecar.write_text("{this is not valid json", encoding="utf-8")

    # --allow-partial-rescue is NOT enough.
    with pytest.raises(FileExistsError) as exc_info:
        _resolve_output_paths(
            output,
            overwrite=False,
            allow_partial_rescue=True,
        )
    assert "force-rescue" in str(exc_info.value)
    assert stale_temp.exists()

    # --force-rescue does the job.
    _resolve_output_paths(output, overwrite=False, force_rescue=True)
    assert not stale_temp.exists()
    assert not sidecar.exists()


def test_capture_natural_runtime_task_exception_becomes_fatal() -> None:
    """Codex H2: an exception inside ``runtime.run()`` must surface as fatal.

    The previous implementation re-raised through ``asyncio.wait_for`` and
    dropped the trace on the floor, so the capture appeared complete with
    no sidecar trail. The new finally block converts it via
    :meth:`_SinkState.set_fatal`.
    """
    from erre_sandbox.cli.eval_run_golden import _derive_stop_reason, _SinkState

    state = _SinkState()
    state.drain_completed = False
    state.set_fatal("runtime_task raised: RuntimeError('boom')")
    assert state.fatal_error is not None
    assert _derive_stop_reason(state) == "fatal_runtime_exception"


def test_sink_state_set_soft_timeout_after_fatal_raises() -> None:
    """fatal-precedence policy: soft timeout must refuse once fatal landed.

    Code reviewer 2026-05-06 MEDIUM: this is the core invariant of
    :class:`_SinkState`; a regression silently allows wall budget to mask
    a fatal capture and publish status=partial.
    """
    from erre_sandbox.cli.eval_run_golden import _SinkState

    state = _SinkState()
    state.set_fatal("duckdb insert failed: deadlock")
    with pytest.raises(AssertionError):
        state.set_soft_timeout("wall timeout (360 min) exceeded")
    # State stays consistent: fatal preserved, soft_timeout untouched.
    assert state.fatal_error == "duckdb insert failed: deadlock"
    assert state.soft_timeout is None


def test_sink_state_drain_timeout_after_wall_escalates_to_fatal() -> None:
    """Codex Q1: wall timeout + drain timeout → fatal precedence wins.

    Mirrors the ``capture_natural`` finally block: the watchdog records a
    soft_timeout, then ``runtime.stop()`` + ``wait_for(...)`` raises
    ``TimeoutError`` which sets ``fatal_error`` even though
    ``soft_timeout`` is already non-None. ``_resolve_publish_outcome``
    must then publish ``status=fatal`` (refuse rename, return 2).
    """
    from erre_sandbox.cli.eval_run_golden import (
        CaptureResult,
        _resolve_publish_outcome,
        _SinkState,
    )

    state = _SinkState()
    state.set_soft_timeout("wall timeout (360 min) exceeded")
    state.drain_completed = False
    state.runtime_drain_timeout = True
    # Simulate the drain finally calling set_fatal: ``set_fatal`` writes
    # ``fatal_error`` regardless of soft_timeout (fatal precedence).
    state.set_fatal("runtime drain exceeded 60.0s")
    assert state.fatal_error is not None
    assert state.soft_timeout is not None  # both fields preserved

    result = CaptureResult(
        run_id="kant_natural_run0",
        output_path=Path("/tmp/kant_natural_run0.duckdb.tmp"),  # noqa: S108
        total_rows=42,
        focal_rows=10,
        fatal_error=state.fatal_error,
        soft_timeout=state.soft_timeout,
        partial_capture=False,
        stop_reason="fatal_drain_timeout",
        drain_completed=False,
        runtime_drain_timeout=True,
    )
    status, stop_reason = _resolve_publish_outcome(result, focal_target=500)
    assert status == "fatal"
    assert stop_reason == "fatal_drain_timeout"

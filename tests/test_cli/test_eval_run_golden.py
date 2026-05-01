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

from pathlib import Path
from typing import Any

import duckdb
import pytest

from erre_sandbox.cli.eval_run_golden import (
    CaptureFatalError,
    _build_arg_parser,
    _focal_turn_count,
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

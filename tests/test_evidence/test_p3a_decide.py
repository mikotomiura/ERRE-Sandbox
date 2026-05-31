"""Unit tests for the pure aggregation/verdict helpers in scripts/p3a_decide.py.

The script itself is exercised end-to-end during the P3a-decide finalization
session against real DuckDB pilots. These tests cover the lightweight
aggregation logic that drives the ME-4 ratio Edit, since the verdict branch
selection is decision-critical.

Codex P3a-finalize HIGH-1/HIGH-2/HIGH-3 reflected: tests now exercise
target-extrapolated widths (not raw), the validation gate (rejecting
partial / errored / under-sampled cells), and a synthetic DuckDB end-to-end
path so the integration surface is exercised on a Mac without G-GEAR data.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import duckdb
import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "p3a_decide.py"


@pytest.fixture(scope="module")
def p3a_decide():
    spec = importlib.util.spec_from_file_location("scripts_p3a_decide", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_block(
    persona: str,
    condition: str,
    burrows_width: float | None,
    mattr_width: float | None,
    n: int = 30,
) -> dict:
    metrics: dict = {}
    if burrows_width is not None:
        metrics["burrows_delta_per_utterance"] = {
            "point": 0.5,
            "lo": 0.5 - burrows_width / 2,
            "hi": 0.5 + burrows_width / 2,
            "width": burrows_width,
            "n": n,
            "n_resamples": 2000,
            "method": "percentile",
        }
    if mattr_width is not None:
        metrics["mattr_per_utterance"] = {
            "point": 0.7,
            "lo": 0.7 - mattr_width / 2,
            "hi": 0.7 + mattr_width / 2,
            "width": mattr_width,
            "n": n,
            "n_resamples": 2000,
            "method": "percentile",
        }
    return {
        "persona_id": persona,
        "condition": condition,
        "n_utterances": n,
        "metrics": metrics,
    }


def _six_clean_blocks(
    *,
    stim_burrows: float = 0.20,
    stim_mattr: float = 0.10,
    nat_burrows: float = 0.50,
    nat_mattr: float = 0.40,
    stim_n: int = 198,
    nat_n: int = 30,
) -> list[dict]:
    return [
        _make_block("kant", "stimulus", stim_burrows, stim_mattr, n=stim_n),
        _make_block("nietzsche", "stimulus", stim_burrows, stim_mattr, n=stim_n),
        _make_block("rikyu", "stimulus", stim_burrows, stim_mattr, n=stim_n),
        _make_block("kant", "natural", nat_burrows, nat_mattr, n=nat_n),
        _make_block("nietzsche", "natural", nat_burrows, nat_mattr, n=nat_n),
        _make_block("rikyu", "natural", nat_burrows, nat_mattr, n=nat_n),
    ]


def test_pilot_path_uses_persona_and_condition(p3a_decide):
    assert p3a_decide._pilot_path("kant", "natural").name == "kant_natural_run0.duckdb"
    assert (
        p3a_decide._pilot_path("rikyu", "stimulus").name == "rikyu_stimulus_run0.duckdb"
    )


def test_normalize_width_scales_with_sqrt_ratio(p3a_decide):
    # n=30 → n_target=300 ⇒ width * sqrt(30/300) = width * sqrt(0.1)
    out = p3a_decide._normalize_width(1.0, n=30, n_target=300)
    assert out == pytest.approx(math.sqrt(0.1))
    # n=200 → n_target=200 ⇒ identity
    assert p3a_decide._normalize_width(0.5, n=200, n_target=200) == pytest.approx(0.5)


def test_per_sample_variability_scales_with_sqrt_n(p3a_decide):
    assert p3a_decide._per_sample_variability(0.5, n=4) == pytest.approx(1.0)
    assert math.isnan(p3a_decide._per_sample_variability(0.5, n=0))


def test_mean_widths_emits_three_views(p3a_decide):
    blocks = _six_clean_blocks()
    summary = p3a_decide._mean_widths_by_condition(blocks)
    stim = summary["stimulus"]["burrows_delta_per_utterance"]
    assert stim["mean_width"] == pytest.approx(0.20)
    # per-sample variability = width * sqrt(n) → 0.20 * sqrt(198)
    assert stim["mean_per_sample_variability"] == pytest.approx(0.20 * math.sqrt(198))
    # extrapolated width = width * sqrt(n / n_target) → 0.20 * sqrt(198/200)
    assert stim["mean_extrapolated_width"] == pytest.approx(0.20 * math.sqrt(198 / 200))
    assert stim["n_target"] == 200
    nat = summary["natural"]["burrows_delta_per_utterance"]
    assert nat["n_target"] == 300
    assert nat["mean_extrapolated_width"] == pytest.approx(0.50 * math.sqrt(30 / 300))


def test_ratio_summary_within_tolerance_uses_extrapolated_widths(p3a_decide):
    # Construct widths so the extrapolated ratio is within 10% but raw is not.
    # stim raw=0.20 n=200 → extrap = 0.20
    # nat raw=0.21 * sqrt(300/30) = 0.21 * sqrt(10) ≈ 0.6641 → extrap = 0.21
    # → extrap ratio nat/stim ≈ 1.05 (within 10% tolerance).
    blocks = _six_clean_blocks(
        stim_burrows=0.20,
        stim_mattr=0.20,
        stim_n=200,
        nat_burrows=0.21 * math.sqrt(10),
        nat_mattr=0.21 * math.sqrt(10),
        nat_n=30,
    )
    summary = p3a_decide._mean_widths_by_condition(blocks)
    out = p3a_decide._ratio_summary(summary, validation_errors=[])
    assert out["verdict"] == "within_tolerance_default_200_300_maintainable"
    assert out["verdict_method"] == "target_extrapolated_width_ratio"
    # The raw ratio should be ~3.32 (sqrt(10) * 1.05) — explicit non-decision input.
    raw_ratio = out["raw_descriptive_only"]["ratio_natural_over_stimulus"]
    assert raw_ratio is not None
    assert raw_ratio > 3.0


def test_ratio_summary_natural_wider_at_target_flags_alternative(p3a_decide):
    # nat extrapolated width is 2x stimulus extrapolated → > 10% tolerance.
    # Use widths that give extrapolated nat = 2x extrapolated stim.
    # stim n=200, raw=0.20 → extrap=0.20. nat n=30, want extrap=0.40 → raw=0.40*sqrt(10)
    blocks = _six_clean_blocks(
        stim_burrows=0.20,
        stim_mattr=0.20,
        stim_n=200,
        nat_burrows=0.40 * math.sqrt(10),
        nat_mattr=0.40 * math.sqrt(10),
        nat_n=30,
    )
    summary = p3a_decide._mean_widths_by_condition(blocks)
    out = p3a_decide._ratio_summary(summary, validation_errors=[])
    assert out["verdict"] == "natural_wider_at_target_alternative_recommended"


def test_ratio_summary_stimulus_wider_at_target_flags_alternative(p3a_decide):
    # stim extrap=0.40, nat extrap=0.20 → nat/stim = 0.5 → stimulus wider.
    blocks = _six_clean_blocks(
        stim_burrows=0.40,
        stim_mattr=0.40,
        stim_n=200,
        nat_burrows=0.20 * math.sqrt(10),
        nat_mattr=0.20 * math.sqrt(10),
        nat_n=30,
    )
    summary = p3a_decide._mean_widths_by_condition(blocks)
    out = p3a_decide._ratio_summary(summary, validation_errors=[])
    assert out["verdict"] == "stimulus_wider_at_target_alternative_recommended"


def test_ratio_summary_skipped_when_validation_errors_present(p3a_decide):
    out = p3a_decide._ratio_summary(
        {"stimulus": {}, "natural": {}},
        validation_errors=["cell (rikyu, natural) absent"],
    )
    assert "skipped" in out
    assert out["validation_errors"] == ["cell (rikyu, natural) absent"]
    assert "verdict" not in out


def test_validate_cells_for_ratio_clean_six_returns_no_errors(p3a_decide):
    blocks = _six_clean_blocks()
    out = p3a_decide._validate_cells_for_ratio(blocks)
    assert out == {"errors": [], "warnings": []}


def test_validate_cells_for_ratio_flags_missing_cell(p3a_decide):
    blocks = _six_clean_blocks()
    blocks.pop()  # remove rikyu natural
    out = p3a_decide._validate_cells_for_ratio(blocks)
    assert any("rikyu" in e and "natural" in e and "absent" in e for e in out["errors"])


def test_validate_cells_for_ratio_flags_errored_cell(p3a_decide):
    blocks = _six_clean_blocks()
    blocks[0] = {
        "persona_id": "kant",
        "condition": "stimulus",
        "error": "BoomError: kaboom",
    }
    out = p3a_decide._validate_cells_for_ratio(blocks)
    assert any(
        "kant" in e and "stimulus" in e and "errored" in e for e in out["errors"]
    )


def test_validate_cells_for_ratio_flags_under_sampled_cell(p3a_decide):
    # natural floor is 25; stimulus floor is 150
    blocks = _six_clean_blocks(stim_n=120)  # below stimulus floor
    out = p3a_decide._validate_cells_for_ratio(blocks)
    assert any("under-sampled" in e and "stimulus" in e for e in out["errors"])


def test_validate_cells_for_ratio_flags_missing_metric(p3a_decide):
    # Drop MATTR from one cell (kant; not a known limitation → real error).
    blocks = _six_clean_blocks()
    del blocks[0]["metrics"]["mattr_per_utterance"]
    out = p3a_decide._validate_cells_for_ratio(blocks)
    assert any(
        "kant" in e and "mattr" in e and "missing required metric" in e
        for e in out["errors"]
    )


def test_validate_cells_for_ratio_flags_unexpected_persona(p3a_decide):
    blocks = _six_clean_blocks()
    blocks.append(_make_block("aristotle", "natural", 0.5, 0.5, n=30))
    out = p3a_decide._validate_cells_for_ratio(blocks)
    assert any("unexpected cell tag" in e for e in out["errors"])


def test_validate_routes_rikyu_burrows_to_warnings_not_errors(p3a_decide):
    """Codex HIGH-3 vs HIGH-2 reconciliation: rikyu Burrows missing is a
    documented library limitation (Japanese tokenizer absent) so the gate
    must route it to ``warnings`` rather than blocking the ratio verdict.
    """
    blocks = _six_clean_blocks()
    # Drop Burrows from both rikyu cells (mirrors real Mac run output).
    for block in blocks:
        if block["persona_id"] == "rikyu":
            del block["metrics"]["burrows_delta_per_utterance"]
    out = p3a_decide._validate_cells_for_ratio(blocks)
    assert out["errors"] == []
    assert len(out["warnings"]) == 2
    assert all("rikyu" in w and "burrows" in w for w in out["warnings"])
    assert all("BurrowsTokenizationUnsupportedError" in w for w in out["warnings"])


def _build_synthetic_pilot(
    path: Path,
    persona: str,
    n_focal: int,
    *,
    interlocutors: tuple[str, ...] = (),
) -> None:
    """Build a minimal raw_dialog.dialog table with the focal speaker rows.

    The script reads via ``SELECT utterance FROM raw_dialog.dialog WHERE
    speaker_persona_id = ?``. We populate ``n_focal`` rows for the focal
    persona plus a few rows for other interlocutors so the SELECT filters
    them out — exercising the WHERE clause path.
    """
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE SCHEMA raw_dialog")
        con.execute(
            "CREATE TABLE raw_dialog.dialog ("
            "tick INTEGER, dialog_id INTEGER, turn_index INTEGER, "
            "speaker_persona_id VARCHAR, utterance VARCHAR)"
        )
        rows: list[tuple[int, int, int, str, str]] = [
            (
                i // 6,
                i // 6,
                i % 6,
                persona,
                f"focal utterance #{i} from {persona}",
            )
            for i in range(n_focal)
        ]
        rows.extend(
            (j, j, 99, other, f"interlocutor utterance #{j} from {other}")
            for j, other in enumerate(interlocutors)
        )
        con.executemany(
            "INSERT INTO raw_dialog.dialog VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        con.close()


def test_end_to_end_against_synthetic_pilots(p3a_decide, tmp_path, monkeypatch):
    """End-to-end exercise: build 6 minimal DuckDB cells, run main(), assert
    JSON schema and that the validation gate accepts the synthetic data.

    Codex MEDIUM-3: the lightweight unit tests cover aggregation/verdict but
    not the integration glue (DuckDB read, focal SELECT, payload write).
    """
    pilot_dir = tmp_path / "pilot"
    pilot_dir.mkdir()
    out_path = pilot_dir / "_p3a_decide.json"

    monkeypatch.setattr(p3a_decide, "_PILOT_DIR", pilot_dir)
    monkeypatch.setattr(p3a_decide, "_OUT_PATH", out_path)
    # Skip the real Burrows path (no reference corpus available in tmp_path);
    # we patch the helpers to return canned per-utterance values so the
    # bootstrap CI executes against deterministic data.
    monkeypatch.setattr(
        p3a_decide,
        "_per_utterance_burrows",
        lambda _persona, utterances: [0.4 + 0.01 * i for i in range(len(utterances))],
    )
    monkeypatch.setattr(
        p3a_decide,
        "compute_mattr",
        lambda _utt: 0.6,  # constant per-utterance MATTR
    )

    # Build 6 cells with floor-respecting focal counts.
    for persona in ("kant", "nietzsche", "rikyu"):
        _build_synthetic_pilot(
            pilot_dir / f"{persona}_stimulus_run0.duckdb",
            persona,
            n_focal=160,
            interlocutors=("nietzsche", "kant"),
        )
        _build_synthetic_pilot(
            pilot_dir / f"{persona}_natural_run0.duckdb",
            persona,
            n_focal=30,
            interlocutors=("nietzsche", "kant"),
        )

    rc = p3a_decide.main()
    assert rc == 0, "expected success when 6 valid cells are present"
    assert out_path.is_file()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "p3a_decide/v3"
    assert payload["scope"] == "stimulus_and_natural"
    assert payload["validation_errors"] == []
    assert len(payload["cells"]) == 6
    assert "ratio_summary" in payload
    assert payload["ratio_summary"]["verdict_method"] == (
        "target_extrapolated_width_ratio"
    )
    assert payload["ratio_summary"]["n_target_by_condition"] == {
        "stimulus": 200,
        "natural": 300,
    }
    assert "raw_descriptive_only" in payload["ratio_summary"]
    assert "proxy_metrics" in payload
    assert payload["proxy_metrics"]["computed_lightweight"] == [
        "burrows_delta_per_utterance",
        "mattr_per_utterance",
    ]
    assert payload["proxy_metrics"]["deferred_to_p4"] == ["vendi_score", "big5_icc"]


def test_main_returns_3_when_validation_fails(p3a_decide, tmp_path, monkeypatch):
    """A cell missing or under-sampled must surface as exit code 3."""
    pilot_dir = tmp_path / "pilot"
    pilot_dir.mkdir()
    out_path = pilot_dir / "_p3a_decide.json"

    monkeypatch.setattr(p3a_decide, "_PILOT_DIR", pilot_dir)
    monkeypatch.setattr(p3a_decide, "_OUT_PATH", out_path)
    monkeypatch.setattr(
        p3a_decide,
        "_per_utterance_burrows",
        lambda _persona, utterances: [0.4 for _ in utterances],
    )
    monkeypatch.setattr(p3a_decide, "compute_mattr", lambda _utt: 0.6)

    # Build only 5 cells (rikyu_natural absent on disk → preflight returns 2,
    # but we want to exercise the validation gate, so build all 6 but make
    # one under-sampled).
    for persona in ("kant", "nietzsche", "rikyu"):
        _build_synthetic_pilot(
            pilot_dir / f"{persona}_stimulus_run0.duckdb",
            persona,
            n_focal=160,
        )
        # rikyu_natural under-sampled below floor 25
        n = 10 if persona == "rikyu" else 30
        _build_synthetic_pilot(
            pilot_dir / f"{persona}_natural_run0.duckdb",
            persona,
            n_focal=n,
        )

    rc = p3a_decide.main()
    assert rc == 3
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["validation_errors"]
    assert "skipped" in payload["ratio_summary"]
    assert any(
        "rikyu" in e and "natural" in e and "under-sampled" in e
        for e in payload["validation_errors"]
    )

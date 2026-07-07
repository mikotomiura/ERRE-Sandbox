"""ECL B — Issue 005 tests: annotation side-file schema + bank golden replay.

Issue ``loop/20260708-m13-b-code-impl/issues/005-annotation-golden.md`` of the
FROZEN ADR ``.steering/20260707-m13-b-impl-design/design-final.md`` (§I4 raw-row
annotation / §I5 bank golden = small committed replay fixture, cross-platform).
Ollama-free throughout (D-10 mock-only) — this module never opens a live
Ollama connection; ``scripts.ecl_bank_capture`` is exercised directly.

Scope guard (§I9/§I4, mirrors ``test_ecl_bank_driver.py`` /
``test_ecl_bank_fixtures.py``): this module tests *construction*, never
measurement. It never asserts ``H(zone|ctx)`` / distinct-zone counts /
diversity / divergence over the annotation rows — only schema, byte-identity,
and completion.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.ecl_bank_capture import (
    BANK_GOLDEN_MANIFEST_VERSION,
    capture,
    verify,
)

from erre_sandbox.integration.embodied.bank import (
    BANK_ANNOTATION_SCHEMA_VERSION,
    BANK_K_GOLDEN,
    BANK_M_GOLDEN,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN_DIR = _REPO_ROOT / "experiments" / "20260708-m13-b-bank" / "artifacts"
_ANNOTATION_ROW_KEYS = frozenset(
    {
        "frozen_ctx_id",
        "condition",
        "mc_index",
        "pre_bias_destination_zone",
        "resolved_from",
    }
)


def _read_committed() -> tuple[dict[str, object], str, str]:
    manifest = json.loads((_GOLDEN_DIR / "manifest.json").read_text(encoding="utf-8"))
    records_text = (_GOLDEN_DIR / "bank_records.jsonl").read_text(encoding="utf-8")
    annotation_text = (_GOLDEN_DIR / "bank_annotation.jsonl").read_text(
        encoding="utf-8"
    )
    return manifest, records_text, annotation_text


# --------------------------------------------------------------------------- #
# I5-G1 — annotation side-file schema (closed set exactly, opaque, no aggregate)
# --------------------------------------------------------------------------- #


def test_bank_annotation_side_file_schema() -> None:
    """Every committed annotation row's key set is the §I4 closed set exactly.

    No extra field (no ``H`` / count / diversity / divergence key), and the
    manifest carries the annotation schema version — never a per-row field
    (the schema version is a bundle-level pin, not part of the raw-row shape)."""
    manifest, _records_text, annotation_text = _read_committed()
    rows = [json.loads(line) for line in annotation_text.splitlines() if line.strip()]
    assert rows, "committed annotation side-file must be non-empty"
    for row in rows:
        assert set(row) == _ANNOTATION_ROW_KEYS, row
        assert row["condition"] in ("on", "off")
        assert isinstance(row["mc_index"], int)
        assert row["mc_index"] >= 0
        assert row["resolved_from"] == "pre_bias_direct_parse"

    assert manifest["annotation_schema_version"] == BANK_ANNOTATION_SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# I5-G2 — committed bank records replay to a byte-identical bundle (Ollama-free)
# --------------------------------------------------------------------------- #


async def test_bank_golden_replay_checksum() -> None:
    """The committed bank golden replays from records alone — no live LLM.

    ``scripts.ecl_bank_capture.verify`` reconstructs the K frozen contexts from
    the committed ``bank_records.jsonl`` alone (no provenance pass, no chat
    call) and re-drives the bake-out M-loop through a **replay**-mode
    ``BankRecordReplayClient`` — this is the reproduction contract itself
    (``inner_invocations == 0``), not merely a schema check."""
    ok = await verify(_GOLDEN_DIR)
    assert ok is True


# --------------------------------------------------------------------------- #
# I5-G3 — categorical byte stability (zone-pick) + 6-decimal float quantisation
# --------------------------------------------------------------------------- #


def test_bank_golden_categorical_byte_stable() -> None:
    """Zone-pick is categorical (a ``Zone`` enum string) — byte-stable by
    construction; sampling floats are 6-decimal quantised (cross-platform
    ``libm``-drift absorber, ``feedback_golden_crossplatform_float_drift``)."""
    _manifest, records_text, _annotation_text = _read_committed()
    rows = [json.loads(line) for line in records_text.splitlines() if line.strip()]
    assert rows

    for row in rows:
        zone = row["pre_bias_destination_zone"]
        assert zone is None or isinstance(zone, str)
        sampling = row["sampling"]
        for key in ("temperature", "top_p", "repeat_penalty"):
            value = sampling[key]
            assert isinstance(value, (int, float))
            assert round(float(value), 6) == value, (
                f"{key} not 6-decimal quantised: {value!r}"
            )

    # Re-parsing + re-canonicalising every committed row (public round-trip via
    # scripts.ecl_bank_capture's record (de)serialisers) reproduces the exact
    # committed bytes — the categorical/quantised fields round-trip with no
    # drift. Covered end-to-end (record → replay → re-render byte identity) by
    # ``test_bank_golden_replay_checksum``; this test isolates the field-level
    # invariant only.


# --------------------------------------------------------------------------- #
# I5-G4 — mock construction verification run (K x M x 2, call cap respected)
# --------------------------------------------------------------------------- #


async def test_bank_construction_run_mock() -> None:
    """A fresh mock construction run completes K×M×2 without exception and
    respects the §I4 ``2·M·K`` call cap — Ollama-free (D-10)."""
    rendered = await capture(seed=0, m_draws=BANK_M_GOLDEN, k_contexts=BANK_K_GOLDEN)
    assert set(rendered) == {
        "bank_records.jsonl",
        "bank_annotation.jsonl",
        "manifest.json",
    }

    manifest = json.loads(rendered["manifest.json"])
    assert manifest["bank_golden_manifest_version"] == BANK_GOLDEN_MANIFEST_VERSION
    assert manifest["call_cap"]["actual"] == 2 * BANK_M_GOLDEN * BANK_K_GOLDEN
    assert manifest["call_cap"]["actual"] <= manifest["call_cap"]["cap"]

    record_rows = [
        json.loads(line)
        for line in rendered["bank_records.jsonl"].splitlines()
        if line.strip()
    ]
    assert len(record_rows) == 2 * BANK_M_GOLDEN * BANK_K_GOLDEN

    annotation_rows = [
        json.loads(line)
        for line in rendered["bank_annotation.jsonl"].splitlines()
        if line.strip()
    ]
    assert len(annotation_rows) == len(record_rows)
    for row in annotation_rows:
        assert set(row) == _ANNOTATION_ROW_KEYS


# --------------------------------------------------------------------------- #
# I5-G5 — repro.sh exits 0 (subprocess, one-command Ollama-free reproduction)
# --------------------------------------------------------------------------- #


def test_bank_golden_repro_script_exits_zero() -> None:
    """``repro.sh``'s underlying CLI invocation exits 0 (Ollama-free)."""
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell, test-only
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "ecl_bank_capture.py"),
            "--verify",
            "--artifact-dir",
            str(_GOLDEN_DIR),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

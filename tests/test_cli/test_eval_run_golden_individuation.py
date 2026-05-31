"""CLI ``--compute-individuation`` seam coverage (M10-0 individuation PR-2).

Asserts the byte-invariance seam: flag-off never runs the individuation pass
(call-site gate + getattr guard, DA-M10I-14) and leaves the published .duckdb
byte-identical with no sidecar; flag-on writes the JSON sidecar via a read-only
pass that does not mutate the .duckdb; and a failing pass writes an *error*
sidecar without downgrading the capture return code (Must-Fix-4).
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb

from erre_sandbox.cli.eval_run_golden import CaptureResult, _publish_capture
from erre_sandbox.evidence.eval_store import bootstrap_schema
from erre_sandbox.evidence.individuation.layer1 import stub_embedding_provider
from erre_sandbox.evidence.individuation.report import individuation_sidecar_path_for

if TYPE_CHECKING:
    import pytest

_DIALOG_COLS = (
    "id",
    "run_id",
    "dialog_id",
    "tick",
    "turn_index",
    "speaker_agent_id",
    "speaker_persona_id",
    "addressee_agent_id",
    "addressee_persona_id",
    "utterance",
    "mode",
    "zone",
    "reasoning",
    "epoch_phase",
    "individual_layer_enabled",
    "created_at",
)


def _args(
    *, compute_individuation: bool | None, personas_dir: Path
) -> argparse.Namespace:
    ns = argparse.Namespace(
        persona="kant",
        condition="natural",
        run_idx=0,
        turn_count=2,
        wall_timeout_min=360.0,
        personas_dir=personas_dir,
    )
    if compute_individuation is not None:
        ns.compute_individuation = compute_individuation
    return ns


def _real_duckdb_temp(tmp_path: Path) -> tuple[Path, Path]:
    """Build a real DuckDB at <final>.tmp with a couple of raw_dialog rows."""
    final = tmp_path / "kant_natural_run0.duckdb"
    temp = final.with_suffix(final.suffix + ".tmp")
    con = duckdb.connect(str(temp), read_only=False)
    bootstrap_schema(con)
    cols = ", ".join(_DIALOG_COLS)
    ph = ", ".join("?" for _ in _DIALOG_COLS)
    from datetime import UTC, datetime

    for i in range(3):
        row: dict[str, Any] = {
            "id": f"r{i}",
            "run_id": "kant_natural_run0",
            "dialog_id": "d0",
            "tick": i,
            "turn_index": 0,
            "speaker_agent_id": "a_kant_001",
            "speaker_persona_id": "kant",
            "addressee_agent_id": "a_x",
            "addressee_persona_id": "x",
            "utterance": f"utterance number {i}",
            "mode": "",
            "zone": "study",
            "reasoning": "",
            "epoch_phase": "autonomous",
            "individual_layer_enabled": False,
            "created_at": datetime.now(UTC),
        }
        con.execute(
            f"INSERT INTO raw_dialog.dialog ({cols}) VALUES ({ph})",  # noqa: S608  # static cols
            [row[c] for c in _DIALOG_COLS],
        )
    con.execute("CHECKPOINT")
    con.close()
    return temp, final


def _complete_result(temp: Path) -> CaptureResult:
    return CaptureResult(
        run_id="kant_natural_run0",
        output_path=temp,
        total_rows=3,
        focal_rows=2,  # == turn_count -> complete
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_flag_off_skips_pass_and_keeps_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    temp, final = _real_duckdb_temp(tmp_path)
    pre_sha = _sha(temp)
    called: list[bool] = []
    monkeypatch.setattr(
        "erre_sandbox.cli.eval_run_golden._run_individuation_sidecar",
        lambda *_a, **_k: called.append(True),
    )
    # Namespace WITHOUT the attribute at all — exercises the getattr guard.
    code = _publish_capture(
        _args(compute_individuation=None, personas_dir=tmp_path),
        _complete_result(temp),
        temp,
        final,
    )
    assert code == 0
    assert not called  # pass never invoked
    assert not individuation_sidecar_path_for(final).exists()
    assert _sha(final) == pre_sha  # byte-for-byte unchanged


def test_flag_on_writes_sidecar_without_mutating_duckdb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "erre_sandbox.evidence.individuation.layer1.default_embedding_provider",
        stub_embedding_provider,
    )
    temp, final = _real_duckdb_temp(tmp_path)
    pre_sha = _sha(temp)
    code = _publish_capture(
        _args(compute_individuation=True, personas_dir=tmp_path),
        _complete_result(temp),
        temp,
        final,
    )
    assert code == 0
    sidecar = individuation_sidecar_path_for(final)
    assert sidecar.exists()
    assert _sha(final) == pre_sha  # read-only pass did not mutate the file


def test_flag_on_failure_writes_error_sidecar_and_keeps_rc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "erre_sandbox.evidence.individuation.layer1.default_embedding_provider",
        stub_embedding_provider,
    )

    def _boom(*_a: object, **_k: object) -> list[object]:
        msg = "individuation boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        "erre_sandbox.evidence.individuation.runner.compute_individuation", _boom
    )
    temp, final = _real_duckdb_temp(tmp_path)
    code = _publish_capture(
        _args(compute_individuation=True, personas_dir=tmp_path),
        _complete_result(temp),
        temp,
        final,
    )
    assert code == 0  # capture rc preserved
    import json

    sidecar = individuation_sidecar_path_for(final)
    assert sidecar.exists()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["status"] == "error"
    assert payload["error_type"] == "RuntimeError"

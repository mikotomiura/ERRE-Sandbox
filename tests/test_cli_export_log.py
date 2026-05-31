"""Unit tests for ``erre-sandbox export-log`` (M8 L6-D1).

Exercises the CLI end-to-end against a real sqlite file on disk so the
``run()`` path (``MemoryStore`` creation + ``iter_dialog_turns`` + JSONL
write) is covered as one integration.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from erre_sandbox.__main__ import cli
from erre_sandbox.memory import MemoryStore
from erre_sandbox.schemas import DialogTurnMsg


def _seed_db(db_path: Path) -> None:
    """Populate ``db_path`` with three Kant + one Rikyū dialog turns."""
    store = MemoryStore(db_path=db_path)
    store.create_schema()
    for i in range(3):
        store.add_dialog_turn_sync(
            DialogTurnMsg(
                tick=10 + i,
                dialog_id="d_kant_nietzsche_0001",
                speaker_id="a_kant_001",
                addressee_id="a_nietzsche_001",
                utterance=f"turn-{i}",
                turn_index=i,
            ),
            speaker_persona_id="kant",
            addressee_persona_id="nietzsche",
        )
    store.add_dialog_turn_sync(
        DialogTurnMsg(
            tick=20,
            dialog_id="d_rikyu_nietzsche_0001",
            speaker_id="a_rikyu_001",
            addressee_id="a_nietzsche_001",
            utterance="wabi",
            turn_index=0,
        ),
        speaker_persona_id="rikyu",
        addressee_persona_id="nietzsche",
    )


def test_export_log_help_lists_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli(["export-log", "--help"])
    # argparse exits 0 on --help.
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "dialog_turns" in out or "JSONL" in out


def test_export_log_writes_jsonl_to_file(tmp_path: Path) -> None:
    db = tmp_path / "kant.db"
    _seed_db(db)
    out = tmp_path / "log.jsonl"

    rc = cli(["export-log", "--db", str(db), "--out", str(out)])
    assert rc == 0

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4
    rows = [json.loads(line) for line in lines]
    assert [r["turn_index"] for r in rows if r["speaker_persona_id"] == "kant"] == [
        0,
        1,
        2,
    ]
    assert any(r["speaker_persona_id"] == "rikyu" for r in rows)


def test_export_log_filters_by_persona(tmp_path: Path) -> None:
    db = tmp_path / "kant.db"
    _seed_db(db)
    out = tmp_path / "kant_only.jsonl"

    rc = cli(
        [
            "export-log",
            "--db",
            str(db),
            "--persona",
            "kant",
            "--out",
            str(out),
        ],
    )
    assert rc == 0
    rows = [
        json.loads(line)
        for line in out.read_text(encoding="utf-8").strip().splitlines()
    ]
    assert len(rows) == 3
    assert {r["speaker_persona_id"] for r in rows} == {"kant"}


def test_export_log_empty_db_writes_empty_file(tmp_path: Path) -> None:
    """Fresh DB (no seed) should produce an empty JSONL file, exit 0."""
    db = tmp_path / "empty.db"
    out = tmp_path / "empty.jsonl"
    rc = cli(["export-log", "--db", str(db), "--out", str(out)])
    assert rc == 0
    assert out.read_text(encoding="utf-8") == ""


def test_export_log_since_filter_drops_past_rows(tmp_path: Path) -> None:
    db = tmp_path / "kant.db"
    _seed_db(db)
    out = tmp_path / "future.jsonl"

    future = (datetime.now(tz=UTC) + timedelta(hours=1)).isoformat()
    rc = cli(
        [
            "export-log",
            "--db",
            str(db),
            "--since",
            future,
            "--out",
            str(out),
        ],
    )
    assert rc == 0
    assert out.read_text(encoding="utf-8") == ""

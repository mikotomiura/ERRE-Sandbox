"""Unit tests for ``erre-sandbox baseline-metrics`` (M8).

Covers the three user-visible paths:

* ``--help`` prints the sub-command description without errors
* aggregating a seeded DB and writing JSON to a file produces the stable shape
* pointing at a non-existent DB exits with a non-zero code
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from erre_sandbox.__main__ import cli
from erre_sandbox.memory import MemoryStore
from erre_sandbox.schemas import DialogTurnMsg


def _seed_db(db_path: Path) -> None:
    store = MemoryStore(db_path=db_path)
    store.create_schema()
    for i in range(3):
        store.add_dialog_turn_sync(
            DialogTurnMsg(
                tick=10 + i,
                dialog_id="d0",
                speaker_id="a_kant_001",
                addressee_id="a_rikyu_001",
                utterance=f"kant turn number {i}",
                turn_index=i,
            ),
            speaker_persona_id="kant",
            addressee_persona_id="rikyu",
        )
    store.add_bias_event_sync(
        tick=11,
        agent_id="a_kant_001",
        persona_id="kant",
        from_zone="agora",
        to_zone="peripatos",
        bias_p=0.2,
    )


def test_baseline_metrics_help_prints_description(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli(["baseline-metrics", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    # argparse prints the sub-command description — check a stable token.
    assert "baseline" in out.lower()


def test_baseline_metrics_writes_json_file(tmp_path: Path) -> None:
    db_path = tmp_path / "run.db"
    out_path = tmp_path / "baseline.json"
    _seed_db(db_path)

    rc = cli(
        [
            "baseline-metrics",
            "--run-db",
            str(db_path),
            "--out",
            str(out_path),
        ],
    )
    assert rc == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "baseline_metrics_v1"
    assert payload["turn_count"] == 3
    assert payload["bias_event_count"] == 1
    # affinity_trajectory remains null — decisions D1 guarantee.
    assert payload["affinity_trajectory"] is None


def test_baseline_metrics_missing_db_exits_nonzero(tmp_path: Path) -> None:
    rc = cli(
        [
            "baseline-metrics",
            "--run-db",
            str(tmp_path / "nope.db"),
            "--out",
            "-",
        ],
    )
    assert rc == 2

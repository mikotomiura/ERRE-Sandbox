"""CLI smoke + ``--check`` exit-code tests for ``source-index``.

Verifies the sub-command is fully wired into ``__main__`` (dispatch) and
that ``--check`` returns 0 on a fresh artifact and non-zero on drift /
absence — the CI freshness gate for the committed index.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from erre_sandbox.__main__ import cli

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONAS_DIR = REPO_ROOT / "personas"
COMMITTED_OUT = REPO_ROOT / "data" / "corpus_index"


def test_help_smoke() -> None:
    with pytest.raises(SystemExit) as exc:
        cli(["source-index", "--help"])
    assert exc.value.code == 0


def test_committed_index_is_current() -> None:
    rc = cli(
        [
            "source-index",
            "--persona",
            "kant",
            "--personas-dir",
            str(PERSONAS_DIR),
            "--out-dir",
            str(COMMITTED_OUT),
            "--check",
        ],
    )
    assert rc == 0


def test_generate_then_check_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "idx"
    base = [
        "source-index",
        "--persona",
        "kant",
        "--personas-dir",
        str(PERSONAS_DIR),
        "--out-dir",
        str(out),
    ]
    assert cli(base) == 0
    assert (out / "kant" / "INDEX.md").is_file()
    assert (out / "kant" / "index.json").is_file()
    assert cli([*base, "--check"]) == 0


def test_check_fails_on_drift(tmp_path: Path) -> None:
    out = tmp_path / "idx"
    base = [
        "source-index",
        "--persona",
        "kant",
        "--personas-dir",
        str(PERSONAS_DIR),
        "--out-dir",
        str(out),
    ]
    assert cli(base) == 0
    (out / "kant" / "index.json").write_text("tampered\n", encoding="utf-8")
    assert cli([*base, "--check"]) != 0


def test_persona_id_traversal_is_rejected(tmp_path: Path) -> None:
    rc = cli(
        [
            "source-index",
            "--persona",
            "../../etc/passwd",
            "--personas-dir",
            str(PERSONAS_DIR),
            "--out-dir",
            str(tmp_path / "idx"),
        ],
    )
    assert rc == 2
    # The malicious path must not have been created.
    assert not (tmp_path / "idx").exists()


def test_check_fails_when_absent(tmp_path: Path) -> None:
    out = tmp_path / "missing"
    rc = cli(
        [
            "source-index",
            "--persona",
            "kant",
            "--personas-dir",
            str(PERSONAS_DIR),
            "--out-dir",
            str(out),
            "--check",
        ],
    )
    assert rc != 0

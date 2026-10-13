"""Guard the split of the suite into the ordinary and the closed-chain CI legs.

CI runs pytest twice per OS: ``--closed-chains=exclude`` and
``--closed-chains=only`` (``.github/workflows/ci.yml``, matrix ``chains``).
The directory list behind the option lives in ``tests/conftest.py``
(``CLOSED_CHAIN_DIRS``) and is the one place that decides which tests leave the
ordinary leg. This module checks three things about it
(.steering/20261013-ci-closed-chain-split/decisions.md CC-1, CC-6):

* **B — tied to the seals.** The list is re-derived from the committed seals
  (``experiments/*/manifest*.json`` and ``experiments/*/results/
  driver_mutation.json``) without reading the list itself, and the two must be
  equal. A newly sealed directory left off the list, or a live directory put on
  it, turns the ordinary leg red.
* **C — a partition, per file.** For every test file under ``tests/``, exactly
  one of the two legs keeps it, judged with the hook's own function over the
  file and all of its ancestor directories, so a nested file wrongly skipped by
  both legs cannot hide behind a correct top-level verdict (Codex HIGH-1).
* **D — the hook is wired.** Real pytest subprocesses: the ``only`` leg
  collects exactly the listed directories' files, the ``exclude`` leg collects
  none of them, and a small temporary tree with a nested package collects the
  expected node ids in every mode.

The sealed directories' bytes are never touched here; their own manifest and
certificate tests check those.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from tests.conftest import CLOSED_CHAIN_DIRS, CLOSED_CHAIN_MODES, closed_chain_ignored

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
TESTS_ROOT: Final = REPO_ROOT / "tests"
EXPERIMENTS: Final = REPO_ROOT / "experiments"
CONFTEST: Final = TESTS_ROOT / "conftest.py"
PYPROJECT: Final = REPO_ROOT / "pyproject.toml"

# Directories that must stay in the ordinary leg whatever the seals say: this
# guard itself, and the paper-03 G1 replay-verify witnesses.
ALWAYS_ORDINARY: Final[frozenset[str]] = frozenset(
    {"test_architecture", "test_integration"}
)


def _sealed_manifest_dirs() -> set[str]:
    """Top-level test dirs named by ``tests/<dir>/...`` keys of the manifests.

    The early manifests are flat ``{path: sha256}`` maps; the later ones keep
    the map under ``files``. Both are normalised before reading the keys.
    """
    found: set[str] = set()
    manifests = sorted(EXPERIMENTS.glob("*/manifest*.json"))
    assert manifests, "no experiments/*/manifest*.json found"
    for manifest in manifests:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        entries = data["files"] if isinstance(data.get("files"), dict) else data
        for key in entries:
            if not key.startswith("tests/"):
                continue
            parts = key.split("/")
            assert len(parts) >= 3, (
                f"{manifest}: sealed test path {key!r} is not inside a "
                f"top-level test directory; the directory-level split cannot "
                f"express it"
            )
            found.add(parts[1])
    return found


def _driver_certificates() -> dict[str, dict[str, str]]:
    """Map each certified driver test dir to its certificate's ``tests/*`` keys.

    The certificate keys omit the directory (``tests/conftest.py`` means the
    driver's own test dir), so the dir is named from the one top-level
    ``*_driver.py`` key: ``skill_lever_driver.py`` -> ``test_skill_lever_driver``.
    """
    found: dict[str, dict[str, str]] = {}
    certificates = sorted(EXPERIMENTS.glob("*/results/driver_mutation.json"))
    assert certificates, "no experiments/*/results/driver_mutation.json found"
    for certificate in certificates:
        target = json.loads(certificate.read_text(encoding="utf-8"))["target_sha256"]
        drivers = [k for k in target if "/" not in k and k.endswith("_driver.py")]
        assert len(drivers) == 1, (
            f"{certificate}: expected exactly one top-level *_driver.py key, "
            f"found {drivers!r}"
        )
        directory = "test_" + drivers[0].removesuffix(".py")
        assert directory not in found, f"{directory} certified twice"
        found[directory] = {k: v for k, v in target.items() if k.startswith("tests/")}
    return found


def _test_files() -> list[Path]:
    files = [
        path
        for path in TESTS_ROOT.rglob("test_*.py")
        if "__pycache__" not in path.parts
    ]
    assert len(files) > 100, f"suspiciously few test files: {len(files)}"
    return files


def _kept(path: Path, mode: str) -> bool:
    """Whether directory traversal in ``mode`` reaches ``path``.

    Traversal stops at the first ignored ancestor, so the file and every
    directory between it and ``tests/`` must be left alone.
    """
    relative = path.relative_to(TESTS_ROOT)
    candidates = [
        TESTS_ROOT.joinpath(*relative.parts[:n])
        for n in range(1, len(relative.parts) + 1)
    ]
    return all(closed_chain_ignored(c, mode) is None for c in candidates)


def _collect(
    args: list[str], cwd: Path = REPO_ROOT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            *args,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _node_ids(stdout: str) -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in stdout.splitlines()
        if "::" in line and not line.startswith(("SKIPPED", "="))
    }


# --- B: tied to the seals ---------------------------------------------------


def test_closed_chain_dirs_are_exactly_the_sealed_test_dirs() -> None:
    derived = _sealed_manifest_dirs() | set(_driver_certificates())
    assert derived == set(CLOSED_CHAIN_DIRS), (
        f"tests/conftest.py CLOSED_CHAIN_DIRS no longer matches the seals.\n"
        f"  sealed but not listed: {sorted(derived - CLOSED_CHAIN_DIRS)}\n"
        f"  listed but not sealed: {sorted(CLOSED_CHAIN_DIRS - derived)}\n"
        f"Add a newly sealed directory to the list; never list a live one."
    )


def test_driver_certificates_name_the_files_of_their_mapped_dir() -> None:
    """The ``*_driver.py`` naming rule must land on the dir the cert describes."""
    for directory, entries in _driver_certificates().items():
        on_disk = {p.name for p in (TESTS_ROOT / directory).glob("*.py")}
        certified = {key.removeprefix("tests/") for key in entries}
        assert certified == on_disk, (
            f"{directory}: certificate lists {sorted(certified)}, the directory "
            f"holds {sorted(on_disk)}"
        )


def test_closed_chain_dirs_exist_and_spare_the_ordinary_guards() -> None:
    for directory in CLOSED_CHAIN_DIRS:
        assert any((TESTS_ROOT / directory).glob("test_*.py")), (
            f"tests/{directory} is listed but holds no test_*.py"
        )
    assert not (CLOSED_CHAIN_DIRS & ALWAYS_ORDINARY), (
        f"{sorted(CLOSED_CHAIN_DIRS & ALWAYS_ORDINARY)} must stay in the "
        f"ordinary leg (this guard / the paper-03 G1 witnesses)"
    )


# --- C: a partition, per file ------------------------------------------------


def test_every_test_file_is_kept_by_exactly_one_leg() -> None:
    for path in _test_files():
        top = path.relative_to(TESTS_ROOT).parts[0]
        kept_exclude, kept_only = _kept(path, "exclude"), _kept(path, "only")
        assert kept_exclude != kept_only, (
            f"{path.relative_to(REPO_ROOT)} is kept by "
            f"{'both legs' if kept_exclude else 'neither leg'}"
        )
        assert kept_only == (top in CLOSED_CHAIN_DIRS), path


@pytest.mark.parametrize("mode", CLOSED_CHAIN_MODES)
def test_tests_root_and_outside_paths_are_never_skipped(mode: str) -> None:
    for path in (TESTS_ROOT, REPO_ROOT, REPO_ROOT / "scripts" / "x.py", PYPROJECT):
        assert closed_chain_ignored(path, mode) is None, (mode, path)


def test_include_mode_skips_nothing() -> None:
    """The default leaves the suite whole (plain ``pytest``, the mutation checks)."""
    for path in _test_files():
        assert closed_chain_ignored(path, "include") is None, path
        assert closed_chain_ignored(path.parent, "include") is None, path


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown --closed-chains mode"):
        closed_chain_ignored(TESTS_ROOT, "all")


# --- D: the hook is wired ----------------------------------------------------


def test_only_leg_collects_exactly_the_listed_dirs() -> None:
    result = _collect(["--closed-chains=only"])
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    collected_dirs = {node.split("/")[1] for node in _node_ids(result.stdout)}
    assert collected_dirs == set(CLOSED_CHAIN_DIRS), (
        f"--closed-chains=only collected {sorted(collected_dirs)}"
    )


def test_exclude_leg_collects_none_of_the_listed_dirs() -> None:
    """With everything else ignored, ``exclude`` finds nothing; ``include`` does.

    The ``include`` run is the witness that the ``--ignore`` set alone leaves
    tests to find, so exit 5 under ``exclude`` comes from the hook.
    """
    others = sorted(
        p.relative_to(REPO_ROOT).as_posix()
        for p in TESTS_ROOT.iterdir()
        if p.name not in CLOSED_CHAIN_DIRS
        and p.name not in {"__init__.py", "conftest.py"}
    )
    ignores = [f"--ignore={other}" for other in others]
    excluded = _collect([*ignores, "--closed-chains=exclude"])
    assert excluded.returncode == pytest.ExitCode.NO_TESTS_COLLECTED, (
        f"exit {excluded.returncode}:\n{excluded.stdout}\n{excluded.stderr}"
    )
    included = _collect(ignores)
    assert included.returncode == 0, f"{included.stdout}\n{included.stderr}"
    assert {n.split("/")[1] for n in _node_ids(included.stdout)} == set(
        CLOSED_CHAIN_DIRS
    )


def test_hook_partitions_a_tree_with_a_nested_package(tmp_path: Path) -> None:
    """The real conftest and pyproject, on a tree with every shape that matters.

    A listed dir, a live package nested two deep, and a file at the top of
    ``tests/``: each mode must collect exactly the expected node ids.
    """
    tests = tmp_path / "tests"
    closed = next(iter(sorted(CLOSED_CHAIN_DIRS)))
    layout = {
        f"{closed}/test_sealed.py": "def test_sealed():\n    pass\n",
        "test_live/test_tier/test_nested.py": "def test_nested():\n    pass\n",
        "test_top.py": "def test_top():\n    pass\n",
    }
    for relative, body in layout.items():
        target = tests / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    for package in (
        tests,
        tests / closed,
        tests / "test_live",
        tests / "test_live" / "test_tier",
    ):
        (package / "__init__.py").write_text("", encoding="utf-8")
    shutil.copyfile(CONFTEST, tests / "conftest.py")
    shutil.copyfile(PYPROJECT, tmp_path / "pyproject.toml")

    sealed = f"tests/{closed}/test_sealed.py::test_sealed"
    live = {
        "tests/test_live/test_tier/test_nested.py::test_nested",
        "tests/test_top.py::test_top",
    }
    expected = {"include": live | {sealed}, "exclude": live, "only": {sealed}}
    for mode, ids in expected.items():
        result = _collect(
            [f"--rootdir={tmp_path}", f"--closed-chains={mode}"], cwd=tmp_path
        )
        assert result.returncode == 0, f"{mode}: {result.stdout}\n{result.stderr}"
        assert _node_ids(result.stdout) == ids, (mode, result.stdout)

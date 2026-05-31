"""Contamination + isolation invariants for the source navigator.

The navigator is a compile-time evidence-audit tool. Its output must never
feed M9-eval / LoRA training, and the runtime cognition graph must never
import it.

Note (Codex MED-2): ``assert_no_metrics_leak`` is a *row-key* allow-list
guard — it stops a navigator-shaped row from riding a training-egress
payload. It does not, by itself, stop someone pointing a training loader at
``data/corpus_index``; the static grep tests below cover that path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from erre_sandbox.contracts.eval_paths import (
    EvaluationContaminationError,
    assert_no_metrics_leak,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = REPO_ROOT / "src" / "erre_sandbox"


def _src_files(*relative_dirs: str) -> list[Path]:
    files: list[Path] = []
    for rel in relative_dirs:
        files.extend((_SRC_ROOT / rel).rglob("*.py"))
    return files


def test_navigator_shaped_row_rejected_by_metrics_leak_guard() -> None:
    # Navigator field names are not on ALLOWED_RAW_DIALOG_KEYS, so the
    # existing egress guard rejects them out of the box.
    navigator_keys = [
        "source_key",
        "document_id",
        "mechanism",
        "body_absent_reason",
    ]
    with pytest.raises(EvaluationContaminationError):
        assert_no_metrics_leak(navigator_keys, context="source_navigator red-team")


def test_runtime_packages_do_not_import_source_navigator() -> None:
    offenders: list[tuple[Path, int, str]] = []
    for path in _src_files(
        "cognition",
        "memory",
        "world",
        "integration",
        "inference",
        "ui",
    ):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.lstrip()
            if "source_navigator" in stripped and stripped.startswith(
                ("from erre_sandbox", "import erre_sandbox"),
            ):
                offenders.append((path.relative_to(REPO_ROOT), lineno, stripped))
    assert not offenders, (
        "runtime packages must not import source_navigator (runtime non-connection);"
        " offenders:\n" + "\n".join(f"  {p}:{ln}: {text}" for p, ln, text in offenders)
    )


def test_training_and_export_paths_do_not_read_corpus_index() -> None:
    targets: list[Path] = [
        *_src_files("training"),
        _SRC_ROOT / "cli" / "export_log.py",
        _SRC_ROOT / "evidence" / "eval_store.py",
    ]
    offenders: list[tuple[Path, int, str]] = []
    for path in targets:
        if not path.is_file():
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "corpus_index" in line:
                offenders.append((path.relative_to(REPO_ROOT), lineno, line.strip()))
    assert not offenders, (
        "training/export paths must not read data/corpus_index; offenders:\n"
        + "\n".join(f"  {p}:{ln}: {text}" for p, ln, text in offenders)
    )

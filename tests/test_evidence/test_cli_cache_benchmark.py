"""CLI smoke + ``--check`` gate tests for ``cache-benchmark`` (M10-0 A5).

Verifies the sub-command is wired into ``__main__``, that the committed
baseline is current (the CI freshness gate, Codex MF3), that generation is
deterministic, and that the baseline carries the synthetic-TTFT provenance
(Codex MF2 / CH1). All write paths use tmp overrides so the repo artefact is
never touched (Codex MF4).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from erre_sandbox.__main__ import cli

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONAS_DIR = REPO_ROOT / "personas"
COMMITTED_BASELINE = REPO_ROOT / "data" / "bench" / "cache_benchmark_baseline.json"


def _tmp_args(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "cache-benchmark",
        "--personas-dir",
        str(PERSONAS_DIR),
        "--baseline-path",
        str(tmp_path / "baseline.json"),
        "--trace-db",
        str(tmp_path / "bench.duckdb"),
        *extra,
    ]


def test_help_smoke() -> None:
    with pytest.raises(SystemExit) as exc:
        cli(["cache-benchmark", "--help"])
    assert exc.value.code == 0


def test_committed_baseline_is_current() -> None:
    # Codex MF3: the committed baseline must match a fresh recompute, so a
    # prompt-template change that desyncs it fails in CI (pytest = pre-push).
    rc = cli(
        [
            "cache-benchmark",
            "--personas-dir",
            str(PERSONAS_DIR),
            "--baseline-path",
            str(COMMITTED_BASELINE),
            "--check",
        ],
    )
    assert rc == 0


def test_generate_then_check_roundtrip(tmp_path: Path) -> None:
    base = _tmp_args(tmp_path)
    assert cli(base) == 0
    assert (tmp_path / "baseline.json").is_file()
    assert (tmp_path / "bench.duckdb").is_file()
    assert cli([*base, "--check"]) == 0


def test_generation_is_deterministic(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    assert (
        cli(
            [
                "cache-benchmark",
                "--personas-dir",
                str(PERSONAS_DIR),
                "--baseline-path",
                str(a),
                "--no-trace",
            ],
        )
        == 0
    )
    assert (
        cli(
            [
                "cache-benchmark",
                "--personas-dir",
                str(PERSONAS_DIR),
                "--baseline-path",
                str(b),
                "--no-trace",
            ],
        )
        == 0
    )
    assert a.read_text("utf-8") == b.read_text("utf-8")


def test_baseline_carries_synthetic_ttft_provenance(tmp_path: Path) -> None:
    # Codex MF2 / CH1: synthetic TTFT IS in the baseline (A5 includes TTFT),
    # marked live_ttft_verified=false rather than excluded from the artefact.
    assert cli(_tmp_args(tmp_path, "--no-trace")) == 0
    payload = json.loads((tmp_path / "baseline.json").read_text("utf-8"))
    assert payload["ttft_source"] == "synthetic"
    assert payload["live_ttft_verified"] is False
    assert payload["kv_hit_proxy_basis"] == "shared_prefix_tokens/system_prompt_tokens"
    for case in payload["cases"]:
        assert case["ttft_p50"] >= 0.0
        assert case["ttft_p95"] >= case["ttft_p50"]
        assert 0.0 <= case["kv_hit_proxy"] <= 1.0
        assert len(case["prefix_hash"]) == 64


def test_check_fails_on_drift(tmp_path: Path) -> None:
    base = _tmp_args(tmp_path)
    assert cli(base) == 0
    (tmp_path / "baseline.json").write_text("tampered\n", encoding="utf-8")
    assert cli([*base, "--check"]) != 0


def test_check_fails_when_absent(tmp_path: Path) -> None:
    assert cli([*_tmp_args(tmp_path), "--check"]) != 0


def test_flag_on_case_preserves_system_and_bounds_user_growth() -> None:
    """M10-B HIGH-3: the +swm case keeps the SYSTEM prompt byte-identical to the
    base case (so the cache prefix is protected) and grows the USER prompt by a
    bounded amount. ``kv_hit_proxy`` / synthetic TTFT are deliberately *not* the
    go/no-go assertions (they pass trivially); system equality + token delta are
    (DA-M10B-4)."""
    from erre_sandbox.cli.cache_benchmark import (
        _build_case,
        _build_swm_case,
        _swm_fixture_entries,
    )
    from erre_sandbox.evidence.cache_benchmark.compute import (
        count_proxy_tokens,
        prefix_hash,
    )
    from erre_sandbox.evidence.cache_benchmark.policy import (
        TokenCountSource,
    )

    entries = _swm_fixture_entries()
    src = TokenCountSource.PROXY_WHITESPACE_RE
    for pid in ("kant", "nietzsche", "rikyu"):
        base = _build_case(PERSONAS_DIR, pid)
        swm = _build_swm_case(PERSONAS_DIR, pid, entries)
        # SYSTEM prompt byte-identical → shared RadixAttention prefix intact.
        assert swm.system_prompt == base.system_prompt
        assert prefix_hash(swm.shared_prefix, token_count_source=src) == prefix_hash(
            base.shared_prefix,
            token_count_source=src,
        )
        # USER prompt grew (the SWM was injected) but within the +200 bound.
        delta = count_proxy_tokens(swm.user_prompt) - count_proxy_tokens(
            base.user_prompt,
        )
        assert 0 < delta <= 200


def test_committed_baseline_contains_swm_cases() -> None:
    """The committed baseline carries a flag-on case per persona (DA-M10B-4)."""
    payload = json.loads(COMMITTED_BASELINE.read_text("utf-8"))
    case_ids = {c["case_id"] for c in payload["cases"]}
    for pid in ("kant", "nietzsche", "rikyu"):
        assert pid in case_ids
        assert f"{pid}+swm" in case_ids


def test_persona_traversal_rejected(tmp_path: Path) -> None:
    rc = cli(
        [
            "cache-benchmark",
            "--personas",
            "../../etc/passwd",
            "--personas-dir",
            str(PERSONAS_DIR),
            "--baseline-path",
            str(tmp_path / "baseline.json"),
            "--no-trace",
        ],
    )
    assert rc == 2
    assert not (tmp_path / "baseline.json").exists()

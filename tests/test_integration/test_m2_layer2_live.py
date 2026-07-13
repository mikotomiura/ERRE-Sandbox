"""M2 Layer2 (self-other mirror-sim) live-run golden — Issue 003 (K3).

Ollama-free existence-check + replay-verify test suite over the committed,
real-qwen3-baked golden ``tests/fixtures/m2_layer2_live_golden/`` (N=3
a_kant/a_nietzsche/a_rikyu, horizon=12, ``self_other_enabled=True``).

Acceptance is **non-semantic boolean only** (Codex HIGH-1, pre-register
§Axis B / decisions.md): structural segment existence, decode-ability,
decision count, and replay byte-parity. This module never computes an
effect-magnitude / delta / divergence / score — every assertion below is a
boolean existence / set-equality / count / byte-identity check, never a
"how much" measurement (over-read boundary, Codex HIGH-1).

* ``test_self_other_segment_structural_presence`` (MEDIUM-1) — per
  ``(agent_id, agent_tick)``: ``agent_tick == 0`` carries no self-other
  framing for any agent; ``agent_tick >= 1`` carries the framing for every
  agent with an observed-agent set exactly ``sorted(all_agent_ids) -
  {observer}`` and no self-line.
* ``test_all_calls_decodable_and_count`` — every recorded call decodes via
  the R3 decoder (``scripts/m4_society_live_capture.py``,
  ``society_recorded_calls_from_jsonl``), total decision count == 36 (3
  agents x 12 ticks, 12 ticks each), and every decision's ``plan`` is a
  structurally-parsed non-empty ``dict`` (content not evaluated).
* ``test_layer2_golden_replay_byte_parity`` — the script's ``verify()``
  Ollama-free replay of the committed bundle returns ``True`` (which itself
  asserts every replay client's ``inner_invocations == 0`` internally).
* ``test_layer2_golden_self_other_enabled_pin`` (MEDIUM-3) — the committed
  manifest's ``env_pins["self_other_enabled"]`` is the ``bool`` ``True``
  (never a truthy non-bool).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

from erre_sandbox.integration.embodied.society import _SELF_OTHER_FRAMING

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN_DIR = _REPO_ROOT / "tests" / "fixtures" / "m2_layer2_live_golden"
_M4_SCRIPT = _REPO_ROOT / "scripts" / "m4_society_live_capture.py"


def _load_m4_module() -> Any:
    """Load ``scripts/m4_society_live_capture.py`` via importlib (design-final
    idiom, mirrors ``test_m4_society_live.py``'s ``_load_m4_module`` — the
    script lives outside the ``erre_sandbox`` package, so it is a file-path
    load rather than a package import). A distinct ``sys.modules`` key from
    the sibling test module's loader avoids any cross-test-module aliasing."""
    spec = importlib.util.spec_from_file_location(
        "scripts_m4_society_live_capture_k3", _M4_SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_m4 = _load_m4_module()


def _manifest() -> dict[str, Any]:
    return json.loads((_GOLDEN_DIR / "manifest.json").read_text(encoding="utf-8"))


def _decisions_text() -> str:
    return (_GOLDEN_DIR / "decisions.jsonl").read_text(encoding="utf-8")


def _decision_rows() -> list[dict[str, Any]]:
    return [json.loads(line) for line in _decisions_text().splitlines() if line.strip()]


_OBSERVED_LINE_RE = re.compile(r"^- (a_\w+):", re.MULTILINE)


def _observed_agent_ids(user_prompt: str) -> set[str] | None:
    """Structural existence only: return the set of observed ``agent_id``s in
    the self-other segment, or ``None`` if the framing is absent. Never reads
    the segment's ``zone=`` / ``moved_toward=`` / ``said=`` content — those
    are effect-magnitude territory (out of scope, HIGH-1)."""
    idx = user_prompt.find(_SELF_OTHER_FRAMING)
    if idx == -1:
        return None
    segment = user_prompt[idx + len(_SELF_OTHER_FRAMING) :]
    return set(_OBSERVED_LINE_RE.findall(segment))


# --------------------------------------------------------------------------- #
# MEDIUM-1 — self-other segment structural presence (boolean existence only).
# --------------------------------------------------------------------------- #


def test_self_other_segment_structural_presence() -> None:
    rows = _decision_rows()
    all_agent_ids = sorted({row["agent_id"] for row in rows})
    assert all_agent_ids, "fixture precondition: at least one decision row"

    for row in rows:
        observer = row["agent_id"]
        decision = row["decision"]
        agent_tick = decision["agent_tick"]
        user_prompt = decision["call"]["user_prompt"]
        observed = _observed_agent_ids(user_prompt)

        if agent_tick == 0:
            assert observed is None, (
                f"{observer} agent_tick=0 unexpectedly carries self-other framing"
            )
            continue

        assert observed is not None, (
            f"{observer} agent_tick={agent_tick} missing self-other framing"
        )
        expected = set(all_agent_ids) - {observer}
        assert observed == expected, (
            f"{observer} agent_tick={agent_tick} observed set {observed} != "
            f"expected {expected}"
        )
        assert observer not in observed, (
            f"{observer} agent_tick={agent_tick} self-line leaked into observed set"
        )


# --------------------------------------------------------------------------- #
# R3 decode + count (structural parse only, no content evaluation).
# --------------------------------------------------------------------------- #


def test_all_calls_decodable_and_count() -> None:
    rows = _decision_rows()
    manifest = _manifest()
    all_agent_ids = tuple(sorted(manifest["run"]["agent_ids"]))
    n_cognition_ticks = manifest["run"]["cognition_ticks"]

    decoded = _m4.society_recorded_calls_from_jsonl(
        _decisions_text(), expected_agent_ids=all_agent_ids
    )
    assert set(decoded) == set(all_agent_ids)

    total_decoded = sum(len(calls) for calls in decoded.values())
    assert len(rows) == total_decoded
    assert total_decoded == len(all_agent_ids) * n_cognition_ticks

    for agent_id in all_agent_ids:
        ticks = sorted(
            row["decision"]["agent_tick"] for row in rows if row["agent_id"] == agent_id
        )
        assert ticks == list(range(n_cognition_ticks))

    for row in rows:
        plan = row["decision"]["plan"]
        agent_tick = row["decision"]["agent_tick"]
        assert isinstance(plan, dict)
        assert plan, f"empty plan for {row['agent_id']} agent_tick={agent_tick}"


# --------------------------------------------------------------------------- #
# Replay byte-parity (verify() asserts inner_invocations == 0 internally).
# --------------------------------------------------------------------------- #


async def test_layer2_golden_replay_byte_parity() -> None:
    ok = await _m4.verify(_GOLDEN_DIR)
    assert ok is True


# --------------------------------------------------------------------------- #
# MEDIUM-3 — self_other_enabled env-pin is the bool True, never a truthy
# non-bool.
# --------------------------------------------------------------------------- #


def test_layer2_golden_self_other_enabled_pin() -> None:
    manifest = _manifest()
    assert manifest["env_pins"]["self_other_enabled"] is True


def test_m4_layer2_off_golden_has_no_self_other_key() -> None:
    """Codex MEDIUM (cross-review): the committed M4 (Layer2-off) golden's
    ``env_pins`` carries **no** ``self_other_enabled`` key at all — the direct
    byte-identity witness of the *absence == Layer2-off* invariant on the real
    committed artifact (``--verify`` reads absence as ``False``)."""
    m4_manifest = json.loads(
        (
            _REPO_ROOT
            / "tests"
            / "fixtures"
            / "m4_society_live_golden"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert "self_other_enabled" not in m4_manifest["env_pins"]

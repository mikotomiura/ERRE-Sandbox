"""T16 godot-ws-client: guard against drift between Python and GDScript.

``schemas.py`` §7 owns the source-of-truth for the seven ControlEnvelope
``kind`` literals. The Godot-side ``EnvelopeRouter.gd`` hand-codes the same
set in a ``match`` block. Without this test, a schema change on the Python
side can silently leave GDScript stale — Contract-First requires both sides
to stay in lockstep.

This test extracts both sets and asserts set equality. It runs in pure
Python (no Godot required), so it is cheap and always-on in CI.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

from erre_sandbox.schemas import ControlEnvelope

REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTER_GD = REPO_ROOT / "godot_project" / "scripts" / "EnvelopeRouter.gd"

_ROUTER_MATCH_KEY_RE = re.compile(r'^\s*"([a-z_]+)"\s*:\s*$', re.MULTILINE)
# Limit kind extraction to the body of ``on_envelope_received`` so future
# Dictionary literals or additional match blocks elsewhere in the file cannot
# contaminate the set.
_ROUTER_DISPATCH_RE = re.compile(
    r"func\s+on_envelope_received\b[\s\S]*?(?=\nfunc\s|\Z)",
    re.MULTILINE,
)


def _python_kinds() -> set[str]:
    """Extract ``kind`` literals from the Pydantic discriminated union.

    ``ControlEnvelope`` is ``Annotated[Union[...], Field(discriminator="kind")]``.
    Walking the annotation gives the constituent classes, each of which
    carries its ``kind`` literal as the default of the ``kind`` model field.
    """
    annotated_args = get_args(ControlEnvelope)
    union_type = annotated_args[0]
    classes = get_args(union_type)
    return {cls.model_fields["kind"].default for cls in classes}


def _gdscript_kinds() -> set[str]:
    """Scan ``EnvelopeRouter.on_envelope_received`` for match-arm kind strings.

    The router is expected to list each kind as a ``"kind_name":`` line
    (lowercase snake_case) inside ``on_envelope_received``. We scope the
    extraction to that function's body so unrelated string-keyed literals
    elsewhere in the file cannot produce false positives.
    """
    source = ROUTER_GD.read_text(encoding="utf-8")
    dispatch_match = _ROUTER_DISPATCH_RE.search(source)
    if dispatch_match is None:
        msg = "EnvelopeRouter.gd lacks an ``on_envelope_received`` function body."
        raise AssertionError(msg)
    return set(_ROUTER_MATCH_KEY_RE.findall(dispatch_match.group(0)))


def test_envelope_kinds_match_between_schemas_and_router() -> None:
    """Python §7 and GDScript ``EnvelopeRouter.gd`` must declare the same kinds.

    Until ``EnvelopeRouter.gd`` is created, this test fails with
    ``FileNotFoundError`` — that is the TDD red state captured during T16
    Step E-1.
    """
    python_side = _python_kinds()
    gdscript_side = _gdscript_kinds()
    missing_in_gdscript = python_side - gdscript_side
    missing_in_python = gdscript_side - python_side
    assert python_side == gdscript_side, (
        f"ControlEnvelope kind drift detected.\n"
        f"  python-only: {sorted(missing_in_gdscript)}\n"
        f"  gdscript-only: {sorted(missing_in_python)}\n"
        f"Update EnvelopeRouter.gd so its match block covers exactly the "
        f"seven Python kinds."
    )


_EXPECTED_KINDS: frozenset[str] = frozenset(
    {
        # M2 (T05 schemas-freeze)
        "handshake",
        "agent_update",
        "speech",
        "move",
        "animation",
        "world_tick",
        "error",
        # M4 foundation (dialog_* variants added by m4-contracts-freeze)
        "dialog_initiate",
        "dialog_turn",
        "dialog_close",
    },
)


def test_python_side_covers_expected_kinds() -> None:
    """Sanity check that §7 still declares exactly the expected set of kinds.

    If this test fails, the Pydantic union changed shape — review
    ``schemas.py §7``, the README in ``fixtures/control_envelope/``, and
    ``_EXPECTED_KINDS`` above together, and bump ``SCHEMA_VERSION`` if the
    change is intentional.
    """
    assert _python_kinds() == _EXPECTED_KINDS

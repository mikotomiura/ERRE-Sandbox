"""Unit tests for the ERRE mode sampling delta table (M5).

Covers three concerns that are easy to drift if only reviewed visually:

* **Value parity with persona-erre skill**: every ``ERREModeName`` has a
  ``SamplingDelta`` whose numeric fields match the canonical table in
  ``.claude/skills/persona-erre/SKILL.md`` §ルール 2 exactly. The skill is
  the source of truth — this test locks it into code so any future edit to
  either side surfaces immediately.
* **Clamp safety**: a round-trip through :func:`compose_sampling` with
  extreme :class:`SamplingBase` values never produces an out-of-range
  :class:`ResolvedSampling`. Guarantees that the clamp in
  ``inference/sampling.py`` always catches any post-addition violation,
  even under worst-case persona defaults.
* **Immutability of the public mapping**: callers cannot accidentally
  (or maliciously) rebind entries. The table is a module-level constant
  that should behave like one.

The sampling table is pure data + one module-level mapping, so tests
construct fixtures inline without conftest fixtures.
"""

from __future__ import annotations

import pytest

from erre_sandbox.erre.sampling_table import SAMPLING_DELTA_BY_MODE
from erre_sandbox.inference.sampling import compose_sampling
from erre_sandbox.schemas import ERREModeName, SamplingBase, SamplingDelta

# ---------------------------------------------------------------------------
# Canonical values from .claude/skills/persona-erre/SKILL.md §ルール 2.
# Kept as a triple-tuple (temperature, top_p, repeat_penalty) so the test
# table reads like the skill's Markdown table. Any drift → immediate diff.
# ---------------------------------------------------------------------------

_EXPECTED: dict[ERREModeName, tuple[float, float, float]] = {
    ERREModeName.PERIPATETIC: (0.3, 0.05, -0.1),
    ERREModeName.CHASHITSU: (-0.2, -0.05, 0.1),
    ERREModeName.ZAZEN: (-0.3, -0.1, 0.0),
    ERREModeName.SHU_KATA: (-0.2, -0.05, 0.2),
    ERREModeName.HA_DEVIATE: (0.1, 0.05, -0.1),
    ERREModeName.RI_CREATE: (0.2, 0.1, -0.2),
    ERREModeName.DEEP_WORK: (0.0, 0.0, 0.0),
    ERREModeName.SHALLOW: (-0.1, -0.05, 0.0),
}


def test_all_eight_modes_present() -> None:
    """Every ``ERREModeName`` enum member has a delta entry.

    Catches the case where a new mode is added to the enum but nobody
    updates the table — FSM transitions to that mode would otherwise
    raise ``KeyError`` in :meth:`_maybe_apply_erre_fsm`.
    """
    assert set(SAMPLING_DELTA_BY_MODE) == set(ERREModeName)


@pytest.mark.parametrize(
    ("mode", "expected"),
    list(_EXPECTED.items()),
    ids=lambda m: m.value if isinstance(m, ERREModeName) else str(m),
)
def test_delta_values_match_skill_table(
    mode: ERREModeName,
    expected: tuple[float, float, float],
) -> None:
    delta = SAMPLING_DELTA_BY_MODE[mode]
    exp_temp, exp_top_p, exp_rp = expected
    assert delta.temperature == pytest.approx(exp_temp)
    assert delta.top_p == pytest.approx(exp_top_p)
    assert delta.repeat_penalty == pytest.approx(exp_rp)


def test_deep_work_is_zero_delta() -> None:
    """DEEP_WORK leaves the persona's base sampling untouched.

    Documents the intent separately from the parametrized table: the
    "no-op mode" is a first-class semantic, not an accident of all-zero
    table values.
    """
    delta = SAMPLING_DELTA_BY_MODE[ERREModeName.DEEP_WORK]
    assert delta == SamplingDelta()


@pytest.mark.parametrize("mode", list(ERREModeName), ids=lambda m: m.value)
@pytest.mark.parametrize(
    "base",
    [
        # Extreme highs — would overflow top_p/temperature/repeat_penalty
        # if the clamp were broken. ``top_p=1.0`` is the ``_Unit`` max, and
        # ``repeat_penalty=2.0`` is the ``SamplingBase`` max.
        SamplingBase(temperature=2.0, top_p=1.0, repeat_penalty=2.0),
        # Extreme lows — temperature/top_p float above the min; delta with
        # a negative component could push them below the ``ResolvedSampling``
        # range without the clamp. ``SamplingBase`` accepts ``temperature=0.0``
        # (ge=0.0) but ``ResolvedSampling`` requires ``>= 0.01``, so the clamp
        # is what keeps this valid; the assert below locks that invariant.
        SamplingBase(temperature=0.0, top_p=0.01, repeat_penalty=0.5),
        # Persona-realistic default (kant.yaml uses near these values).
        SamplingBase(temperature=0.6, top_p=0.85, repeat_penalty=1.12),
    ],
    ids=["extreme_high", "extreme_low", "persona_typical"],
)
def test_compose_clamp_does_not_violate_ranges_for_any_mode(
    mode: ERREModeName,
    base: SamplingBase,
) -> None:
    """compose_sampling must always return a valid ResolvedSampling.

    Pydantic field validation on :class:`ResolvedSampling` would raise if
    any component landed out of range after ``base + delta`` — this is
    the worst-case regression guard for the whole table.
    """
    resolved = compose_sampling(base, SAMPLING_DELTA_BY_MODE[mode])
    # ResolvedSampling has frozen=True + extra="forbid"; successful
    # construction already proves all three fields satisfy the field
    # constraints (ge/le). The explicit asserts document the contract.
    assert 0.01 <= resolved.temperature <= 2.0
    assert 0.01 <= resolved.top_p <= 1.0
    assert 0.5 <= resolved.repeat_penalty <= 2.0


def test_mapping_is_read_only() -> None:
    """External callers cannot mutate the public table in place.

    ``MappingProxyType`` (or equivalent read-only wrapper) raises
    ``TypeError`` on item assignment; a plain ``dict`` would silently
    accept it and corrupt the global table for every subsequent FSM
    transition.
    """
    with pytest.raises(TypeError):
        SAMPLING_DELTA_BY_MODE[ERREModeName.PERIPATETIC] = SamplingDelta()  # type: ignore[index]


@pytest.mark.parametrize("mode", list(ERREModeName), ids=lambda m: m.value)
def test_each_delta_satisfies_field_constraints(mode: ERREModeName) -> None:
    """Every delta's fields fit within ``SamplingDelta``'s declared range.

    ``SamplingDelta`` has ``ge=-1.0, le=1.0`` on each of its three fields.
    This test is redundant with Pydantic validation at table construction
    but serves as an explicit spec: we intentionally stay well inside
    ``[-1.0, 1.0]`` so no single delta can saturate the clamp on its own.
    """
    delta = SAMPLING_DELTA_BY_MODE[mode]
    for value in (delta.temperature, delta.top_p, delta.repeat_penalty):
        assert -1.0 <= value <= 1.0

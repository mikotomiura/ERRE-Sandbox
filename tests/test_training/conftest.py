"""Shared fixtures for the training-layer test suite (m9-c-spike Phase I).

Implements an in-memory :class:`RawTrainingRelation`-conformant dataclass
so the gate tests can fabricate every CS-3 hard-fail scenario without
booting DuckDB. Using a pure-Python mock here is deliberate (Plan
agent's recommendation was a synthetic DuckDB fixture, but the
``_DuckDBRawTrainingRelation`` constructor enforces an allow-list
lockstep against ``ALLOWED_RAW_DIALOG_KEYS`` — adding the
``individual_layer_enabled`` column to a synthetic DB would require
modifying that allow-list, which is the B-1 follow-up PR's scope, not
this PR). The Protocol mock keeps the gate's contract surface
exercised exhaustively while leaving the production-data lockstep
check untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from erre_sandbox.contracts.eval_paths import RAW_DIALOG_SCHEMA

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


@dataclass
class FakeRawTrainingRelation:
    """In-memory :class:`RawTrainingRelation` for gate tests.

    Conforms to the Protocol surface (``schema_name`` / ``columns`` /
    ``row_count`` / ``iter_rows``) without invoking the DuckDB-side
    column-vs-allowlist enforcement. Tests parametrise three knobs:

    * ``columns`` — controls whether ``individual_layer_enabled`` is
      "exposed" by the schema. Setting it to a tuple that excludes the
      column triggers the :class:`BlockerNotResolvedError` branch.
    * ``rows`` — the row dicts iterated. Each row is a plain
      ``dict[str, object]`` so tests can plant ``epoch_phase=evaluation``,
      ``individual_layer_enabled=True``, or empty utterances at will.
    * ``schema_name`` — defaults to :data:`RAW_DIALOG_SCHEMA`; tests
      should leave this alone unless they are exercising a future
      multi-schema scenario.
    """

    columns: tuple[str, ...]
    rows: list[Mapping[str, object]] = field(default_factory=list)
    schema_name_override: str | None = None

    @property
    def schema_name(self) -> str:
        return self.schema_name_override or RAW_DIALOG_SCHEMA

    def row_count(self) -> int:
        return len(self.rows)

    def iter_rows(self) -> Iterator[Mapping[str, object]]:
        yield from self.rows


_BASE_COLUMNS_WITHOUT_LAYER: tuple[str, ...] = (
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
    "created_at",
)


def make_relation(
    rows: list[Mapping[str, object]],
    *,
    with_individual_layer_column: bool = True,
) -> FakeRawTrainingRelation:
    """Build a :class:`FakeRawTrainingRelation` for a gate-test scenario.

    Args:
        rows: Row dicts to iterate. Each must be a Mapping with at
            minimum the columns the test is exercising.
        with_individual_layer_column: When ``True`` (default), the
            relation reports ``individual_layer_enabled`` in its
            ``columns`` tuple — i.e. the post-B-1 state. When ``False``,
            the column is absent — i.e. the current production state
            and the trigger for :class:`BlockerNotResolvedError`.
    """
    columns = _BASE_COLUMNS_WITHOUT_LAYER
    if with_individual_layer_column:
        columns = (*columns, "individual_layer_enabled")
    return FakeRawTrainingRelation(columns=columns, rows=rows)


def make_kant_row(
    *,
    utterance: str = "I shall walk the Linden-Allee at fifteen-thirty.",
    epoch_phase: str = "autonomous",
    individual_layer_enabled: bool | None = False,
    addressee_persona_id: str | None = "miura",
) -> dict[str, object]:
    """Construct a Kant raw_dialog row dict matching the allow-list shape.

    Defaults are chosen so every row is a "clean" training example;
    tests override individual fields to plant contamination.

    Setting ``individual_layer_enabled=None`` omits the key entirely
    (used together with ``with_individual_layer_column=False`` to
    fabricate the pre-B-1 schema state).
    """
    row: dict[str, object] = {
        "id": "kant-row-1",
        "run_id": "run-x",
        "dialog_id": "dlg-1",
        "tick": 0,
        "turn_index": 0,
        "speaker_agent_id": "agent-kant",
        "speaker_persona_id": "kant",
        "addressee_agent_id": "agent-miura" if addressee_persona_id else None,
        "addressee_persona_id": addressee_persona_id,
        "utterance": utterance,
        "mode": "shu_kata",
        "zone": "peripatos",
        "reasoning": "",
        "epoch_phase": epoch_phase,
        "created_at": "2026-05-08T15:30:00Z",
    }
    if individual_layer_enabled is not None:
        row["individual_layer_enabled"] = individual_layer_enabled
    return row

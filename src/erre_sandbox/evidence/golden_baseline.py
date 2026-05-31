"""External golden-baseline driver for m9-eval-system P2c.

This module owns nothing inside :class:`InMemoryDialogScheduler`; it
drives the scheduler exclusively through the public API
(``schedule_initiate`` / ``record_turn`` / ``close_dialog``). When the
70-stimulus battery × 3-cycle phase is running, the scheduler is held in
``golden_baseline_mode=True`` so the natural-dialog cooldown / timeout /
zone restrictions do not interfere. The driver flips
``scheduler.golden_baseline_mode`` back to ``False`` between phases via
:meth:`GoldenBaselineDriver.enable_natural_phase`, so a single scheduler
instance covers both the stimulus phase and the 300-turn natural-dialog
phase of one golden run.

Responsibilities:

* :func:`derive_seed` — process-stable ``uint64`` per-run seed derived
  via ``hashlib.blake2b`` (Python's salted
  ``hash()`` is not reproducible across processes).
* :func:`shuffled_mcq_order` — per-cell deterministic shuffle of the
  ``A/B/C/D`` MCQ option keys using ``numpy.random.Generator(PCG64)``
  seeded by ``blake2b(seed_root | stimulus_id)`` (ME-7 §1).
* :class:`GoldenBaselineDriver` — orchestrates one persona's full
  battery: opens / drives / closes one dialog per stimulus, alternating
  the speaker on multi-turn stimuli, and records MCQ scoring outcomes
  with the ME-7 scoring protocol (cycle 1 only primary, source_grade
  ``legend`` excluded, ``category_subscore_eligible=False`` excluded).
* :func:`build_seed_manifest` / :func:`write_seed_manifest` —
  reproducible ``golden/seeds.json`` generation, runnable as
  ``python -m erre_sandbox.evidence.golden_baseline``.

Refs:
    - ``golden/stimulus/_schema.yaml`` (single-source-of-truth schema)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import yaml

from erre_sandbox.schemas import DialogTurnMsg, Zone

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from erre_sandbox.integration.dialog import InMemoryDialogScheduler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

# `Path(__file__).parents[3]` resolves to the repository root:
#   parents[0] = .../src/erre_sandbox/evidence/
#   parents[1] = .../src/erre_sandbox/
#   parents[2] = .../src/
#   parents[3] = repository root
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
GOLDEN_DIR: Final[Path] = _REPO_ROOT / "golden"
STIMULUS_DIR: Final[Path] = GOLDEN_DIR / "stimulus"
SEEDS_PATH: Final[Path] = GOLDEN_DIR / "seeds.json"

DEFAULT_SALT: Final[str] = "m9-eval-v1"
"""Salt prefix mixed into every blake2b seed digest (ME-5).

Bumping this constant is a breaking change to the seed manifest; the
schema version on :func:`build_seed_manifest` should be bumped in
lockstep so a stale ``golden/seeds.json`` is rejected by
:func:`assert_seed_manifest_consistent`.
"""
DEFAULT_PERSONAS: Final[tuple[str, ...]] = ("kant", "nietzsche", "rikyu")
DEFAULT_RUN_COUNT: Final[int] = 5
DEFAULT_CYCLE_COUNT: Final[int] = 3
DEFAULT_INTERLOCUTOR_ID: Final[str] = "interlocutor"

SEED_MANIFEST_SCHEMA_VERSION: Final[str] = "0.1.0-m9eval-p2c"

# Default zone used when a stimulus omits ``expected_zone``. None of the
# 210 curated items omit it, but the driver tolerates absence by
# routing to STUDY (golden_baseline_mode bypasses the zone guard).
_FALLBACK_ZONE: Final[Zone] = Zone.STUDY

_MCQ_LABELS: Final[tuple[str, str, str, str]] = ("A", "B", "C", "D")

_ZONE_BY_NAME: Final[dict[str, Zone]] = {
    "peripatos": Zone.PERIPATOS,
    "chashitsu": Zone.CHASHITSU,
    "agora": Zone.AGORA,
    "garden": Zone.GARDEN,
    "study": Zone.STUDY,
}


# ---------------------------------------------------------------------------
# Seed derivation (ME-5)
# ---------------------------------------------------------------------------


def derive_seed(persona_id: str, run_idx: int, salt: str = DEFAULT_SALT) -> int:
    """Process-stable ``uint64`` seed for ``(salt, persona_id, run_idx)``.

    This was elevated from ``hash((persona_id, run_idx, salt))``
    because Python's salted ``hash()`` is not reproducible across
    processes (``PYTHONHASHSEED``). Using ``blake2b(digest_size=8)`` gives
    a deterministic 64-bit integer that the Mac master and the G-GEAR
    runner agree on, which is verified by ``test_seed_manifest_stable``.
    """
    key = f"{salt}|{persona_id}|{run_idx}".encode()
    digest = hashlib.blake2b(key, digest_size=8).digest()
    return int.from_bytes(digest, "big")


def _per_cell_seed(seed_root: int, stimulus_id: str) -> int:
    """Sub-derive a per-stimulus seed for MCQ option shuffling."""
    key = f"{seed_root}|{stimulus_id}".encode()
    digest = hashlib.blake2b(key, digest_size=8).digest()
    return int.from_bytes(digest, "big")


def shuffled_mcq_order(seed_root: int, stimulus_id: str) -> list[str]:
    """Return ``['A','B','C','D']`` permuted deterministically for the cell.

    The permutation is derived from
    ``blake2b(f"{seed_root}|{stimulus_id}").digest()[:8]`` fed into
    ``numpy.random.PCG64``. Calling with the same arguments always
    produces the same order; calling with a different ``stimulus_id``
    or a different ``seed_root`` yields an independent stream
    (verified by ``test_mcq_seeded_shuffle_deterministic``).

    The returned list reads as: position ``i`` holds the **raw** option
    label that should be presented as the new label ``_MCQ_LABELS[i]``
    to the agent. To recover the post-shuffle label of the raw correct
    option, use :func:`_post_shuffle_label`.
    """
    rng = np.random.Generator(np.random.PCG64(_per_cell_seed(seed_root, stimulus_id)))
    order = list(_MCQ_LABELS)
    rng.shuffle(order)
    return order


def _post_shuffle_label(raw_label: str, shuffled_order: list[str]) -> str:
    """Map the raw correct option to its label in the post-shuffle layout."""
    return _MCQ_LABELS[shuffled_order.index(raw_label)]


def shuffled_mcq_options(
    raw_options: dict[str, str], shuffled_order: list[str]
) -> dict[str, str]:
    """Apply ``shuffled_order`` to ``raw_options`` to build the agent-facing dict.

    Position ``i`` of ``shuffled_order`` names the raw option that
    should be displayed as ``_MCQ_LABELS[i]`` to the agent.
    """
    return {
        new_label: raw_options[raw_label]
        for new_label, raw_label in zip(_MCQ_LABELS, shuffled_order, strict=True)
    }


# ---------------------------------------------------------------------------
# Outcome dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCQOutcome:
    """Per-cell MCQ scoring record produced by the driver.

    ``scored=False`` means the row is excluded from primary accuracy by
    one of the ME-7 §2 protocol clauses (not scored ≠ wrong); the
    aggregator should drop these from the per-item Δ accuracy mean.
    ``response_option=None`` means the agent's reply did not start with
    a recognised ``A/B/C/D`` letter — when ``scored=True`` that counts
    as ``is_correct=False`` (off-format penalty), so refusal / verbose
    answers are treated as incorrect rather than excluded.
    """

    stimulus_id: str
    cycle_idx: int
    shuffled_order: tuple[str, ...]
    correct_option_raw: str
    correct_option_post_shuffle: str
    response_option: str | None
    is_correct: bool | None
    scored: bool
    scored_excluded_reason: str | None


@dataclass(frozen=True)
class StimulusOutcome:
    """Per-stimulus driver outcome (MCQ or non-MCQ)."""

    stimulus_id: str
    category: str
    cycle_idx: int
    dialog_id: str
    turn_count: int
    mcq: MCQOutcome | None


# ---------------------------------------------------------------------------
# Stimulus loaders (LOW-2: synthetic 4th persona is isolated to test fixtures)
# ---------------------------------------------------------------------------


def load_stimulus_battery(
    persona_id: str, *, root: Path = STIMULUS_DIR
) -> list[dict[str, Any]]:
    """Load production golden stimulus YAML for one persona.

    Only ``kant`` / ``nietzsche`` / ``rikyu`` are reachable through this
    function. The synthetic 4th persona MCQ fixture
    lives under ``tests/fixtures/`` and must be loaded via
    :func:`load_synthetic_fixture` so it cannot accidentally feed the
    scoring pipeline.
    """
    if persona_id not in DEFAULT_PERSONAS:
        raise ValueError(
            f"persona_id={persona_id!r} is not part of the production "
            f"battery (allowed: {DEFAULT_PERSONAS}). The synthetic 4th "
            f"persona fixture is loaded only via load_synthetic_fixture()."
        )
    return _load_stimuli(root / f"{persona_id}.yaml")


def load_synthetic_fixture(path: Path) -> list[dict[str, Any]]:
    """Load synthetic 4th-persona MCQ fixture (LOW-2 isolation contract)."""
    return _load_stimuli(path)


def _load_stimuli(path: Path) -> list[dict[str, Any]]:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise TypeError(f"{path}: root must parse to a mapping")
    stimuli = parsed.get("stimuli")
    if not isinstance(stimuli, list):
        raise TypeError(f"{path}: missing or non-list 'stimuli' field")
    return stimuli


def _zone_from_str(zone_str: str | None) -> Zone:
    if zone_str is None:
        return _FALLBACK_ZONE
    try:
        return _ZONE_BY_NAME[zone_str]
    except KeyError as exc:
        raise ValueError(f"Unknown expected_zone={zone_str!r}") from exc


# ---------------------------------------------------------------------------
# Scoring protocol helpers (ME-7 §2)
# ---------------------------------------------------------------------------


def _scoring_exclude_reason(stimulus: dict[str, Any], cycle_idx: int) -> str | None:
    """Return the exclusion reason string, or ``None`` when the cell is scored.

    The ME-7 §2 clauses are evaluated in priority order so the
    diagnostic surface tells the analyst which protocol rule fired
    first (cycle gating dominates the rest because cycle 2/3 reach
    those checks repeatedly anyway).
    """
    if cycle_idx != 1:
        return "cycle_not_first"
    if stimulus.get("source_grade") == "legend":
        return "legend_source_grade"
    if stimulus.get("category_subscore_eligible") is False:
        return "category_subscore_excluded"
    return None


def _parse_response_option(reply: str) -> str | None:
    """Best-effort A/B/C/D parser — first non-whitespace upper letter wins."""
    head = reply.lstrip()
    if not head:
        return None
    first = head[0].upper()
    return first if first in _MCQ_LABELS else None


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


@dataclass
class GoldenBaselineDriver:
    """Drive a golden-baseline run for one persona via the public scheduler API.

    The driver is single-persona on purpose — multi-persona runs use
    fresh ``GoldenBaselineDriver`` instances seeded from
    :func:`derive_seed` so their RNG streams stay independent.
    """

    scheduler: InMemoryDialogScheduler
    inference_fn: Callable[..., str]
    seed_root: int
    cycle_count: int = DEFAULT_CYCLE_COUNT
    interlocutor_id: str = DEFAULT_INTERLOCUTOR_ID
    _tick_cursor: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.scheduler.golden_baseline_mode:
            raise ValueError(
                "GoldenBaselineDriver requires "
                "scheduler.golden_baseline_mode=True at construction time"
            )
        if self.cycle_count < 1:
            raise ValueError(f"cycle_count must be >=1, got {self.cycle_count}")

    @property
    def tick_cursor(self) -> int:
        """Read-only view of the next tick the driver will allocate."""
        return self._tick_cursor

    def enable_natural_phase(self) -> None:
        """Flip the scheduler back to natural-dialog rules between phases."""
        self.scheduler.golden_baseline_mode = False

    def run_persona(
        self,
        persona_id: str,
        *,
        stimuli: list[dict[str, Any]] | None = None,
    ) -> list[StimulusOutcome]:
        """Drive ``stimuli`` × ``cycle_count`` for ``persona_id``.

        When ``stimuli`` is ``None`` the production battery for the
        given persona is loaded from ``golden/stimulus/<persona>.yaml``.
        Test callers can pass a synthetic list to control battery size
        without touching the production YAML.
        """
        battery = stimuli if stimuli is not None else load_stimulus_battery(persona_id)
        return [
            self.run_stimulus(persona_id, stimulus, cycle_idx)
            for cycle_idx in range(1, self.cycle_count + 1)
            for stimulus in battery
        ]

    def run_stimulus(
        self,
        persona_id: str,
        stimulus: dict[str, Any],
        cycle_idx: int,
    ) -> StimulusOutcome:
        """Open → drive turns → close one stimulus dialog using public API."""
        zone = _zone_from_str(stimulus.get("expected_zone"))
        expected_turn_count = int(stimulus.get("expected_turn_count", 1))
        if expected_turn_count < 1:
            raise ValueError(
                f"stimulus {stimulus.get('stimulus_id')!r}: "
                f"expected_turn_count must be >=1, got {expected_turn_count}"
            )

        mcq_shuffled_options: dict[str, str] | None = None
        shuffled_order: list[str] | None = None
        raw_options = stimulus.get("options")
        if stimulus.get("category") == "roleeval" and isinstance(raw_options, dict):
            shuffled_order = shuffled_mcq_order(
                self.seed_root, str(stimulus.get("stimulus_id", ""))
            )
            mcq_shuffled_options = shuffled_mcq_options(raw_options, shuffled_order)

        open_tick = self._allocate_tick()
        admitted = self.scheduler.schedule_initiate(
            persona_id, self.interlocutor_id, zone, open_tick
        )
        if admitted is None:
            raise RuntimeError(
                f"scheduler refused initiate for stimulus "
                f"{stimulus.get('stimulus_id')!r} at tick={open_tick}; "
                "check golden_baseline_mode is True and the prior "
                "dialog closed"
            )
        dialog_id = self.scheduler.get_dialog_id(persona_id, self.interlocutor_id)
        if dialog_id is None:
            raise RuntimeError(
                "scheduler admitted initiate but get_dialog_id returned None"
            )

        prior_turns: list[DialogTurnMsg] = []
        for turn_index in range(expected_turn_count):
            turn_tick = self._allocate_tick()
            speaker_id, addressee_id = (
                (persona_id, self.interlocutor_id)
                if turn_index % 2 == 0
                else (self.interlocutor_id, persona_id)
            )
            utterance = self.inference_fn(
                persona_id=persona_id,
                stimulus=stimulus,
                cycle_idx=cycle_idx,
                turn_index=turn_index,
                prior_turns=tuple(prior_turns),
                mcq_shuffled_options=mcq_shuffled_options,
            )
            turn = DialogTurnMsg(
                tick=turn_tick,
                dialog_id=dialog_id,
                speaker_id=speaker_id,
                addressee_id=addressee_id,
                utterance=utterance,
                turn_index=turn_index,
            )
            self.scheduler.record_turn(turn)
            prior_turns.append(turn)

        close_tick = self._allocate_tick()
        self.scheduler.close_dialog(dialog_id, "completed", tick=close_tick)

        mcq_outcome = self._maybe_score_mcq(
            stimulus, cycle_idx, prior_turns, shuffled_order
        )
        return StimulusOutcome(
            stimulus_id=str(stimulus.get("stimulus_id")),
            category=str(stimulus.get("category")),
            cycle_idx=cycle_idx,
            dialog_id=dialog_id,
            turn_count=expected_turn_count,
            mcq=mcq_outcome,
        )

    def _allocate_tick(self) -> int:
        tick = self._tick_cursor
        self._tick_cursor += 1
        return tick

    def _maybe_score_mcq(
        self,
        stimulus: dict[str, Any],
        cycle_idx: int,
        turns: list[DialogTurnMsg],
        shuffled_order: list[str] | None,
    ) -> MCQOutcome | None:
        if stimulus.get("category") != "roleeval":
            return None
        if shuffled_order is None:
            # No options dict on a roleeval stimulus: schema gate would have
            # caught this in P2a contract test, so it is a programming error.
            raise ValueError(
                f"roleeval stimulus {stimulus.get('stimulus_id')!r} has "
                "no options dict; cannot score"
            )

        stimulus_id = str(stimulus.get("stimulus_id", ""))
        correct_raw = str(stimulus.get("correct_option", ""))
        if correct_raw not in _MCQ_LABELS:
            raise ValueError(
                f"{stimulus_id!r}: correct_option must be A/B/C/D, got {correct_raw!r}"
            )
        post_shuffle_label = _post_shuffle_label(correct_raw, shuffled_order)
        # The persona under evaluation speaks first (turn_index=0); the MCQ
        # default ``expected_turn_count: 1`` so this is always the agent's
        # answer.
        persona_reply = turns[0].utterance if turns else ""
        response_option = _parse_response_option(persona_reply)

        exclude_reason = _scoring_exclude_reason(stimulus, cycle_idx)
        if exclude_reason is not None:
            return MCQOutcome(
                stimulus_id=stimulus_id,
                cycle_idx=cycle_idx,
                shuffled_order=tuple(shuffled_order),
                correct_option_raw=correct_raw,
                correct_option_post_shuffle=post_shuffle_label,
                response_option=response_option,
                is_correct=None,
                scored=False,
                scored_excluded_reason=exclude_reason,
            )

        is_correct = response_option == post_shuffle_label
        return MCQOutcome(
            stimulus_id=stimulus_id,
            cycle_idx=cycle_idx,
            shuffled_order=tuple(shuffled_order),
            correct_option_raw=correct_raw,
            correct_option_post_shuffle=post_shuffle_label,
            response_option=response_option,
            is_correct=is_correct,
            scored=True,
            scored_excluded_reason=None,
        )


# ---------------------------------------------------------------------------
# Seed manifest (golden/seeds.json)
# ---------------------------------------------------------------------------


def build_seed_manifest(
    *,
    personas: Iterable[str] = DEFAULT_PERSONAS,
    run_count: int = DEFAULT_RUN_COUNT,
    salt: str = DEFAULT_SALT,
) -> dict[str, Any]:
    """Compose the canonical seed manifest committed at ``golden/seeds.json``."""
    persona_list = list(personas)
    seeds: list[dict[str, Any]] = [
        {
            "persona_id": persona_id,
            "run_idx": run_idx,
            "seed": derive_seed(persona_id, run_idx, salt),
        }
        for persona_id in persona_list
        for run_idx in range(run_count)
    ]
    return {
        "schema_version": SEED_MANIFEST_SCHEMA_VERSION,
        "salt": salt,
        "personas": persona_list,
        "run_count": run_count,
        "seeds": seeds,
    }


def write_seed_manifest(path: Path = SEEDS_PATH) -> dict[str, Any]:
    """Write :func:`build_seed_manifest` output to ``path`` (sorted, ASCII)."""
    manifest = build_seed_manifest()
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_seed_manifest(path: Path = SEEDS_PATH) -> dict[str, Any]:
    """Read the committed seed manifest from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def assert_seed_manifest_consistent(manifest: dict[str, Any]) -> None:
    """Verify each row's ``seed`` matches a fresh :func:`derive_seed` call.

    Raises :class:`AssertionError` on first divergence so the offending
    ``(persona_id, run_idx)`` is easy to locate. Used both by the test
    suite (``test_seed_manifest_stable``) and as a runtime guard before
    a golden run consumes the manifest.
    """
    salt = manifest["salt"]
    for row in manifest["seeds"]:
        expected = derive_seed(row["persona_id"], row["run_idx"], salt)
        if expected != row["seed"]:
            raise AssertionError(
                f"seed manifest mismatch at "
                f"persona_id={row['persona_id']!r} run_idx={row['run_idx']}: "
                f"committed={row['seed']} vs derive_seed={expected}"
            )


def main() -> None:
    """Entry: ``python -m erre_sandbox.evidence.golden_baseline``."""
    manifest = write_seed_manifest()
    logger.info(
        "wrote %d seeds (%d personas × %d runs) to %s",
        len(manifest["seeds"]),
        len(manifest["personas"]),
        manifest["run_count"],
        SEEDS_PATH,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()


__all__ = [
    "DEFAULT_CYCLE_COUNT",
    "DEFAULT_INTERLOCUTOR_ID",
    "DEFAULT_PERSONAS",
    "DEFAULT_RUN_COUNT",
    "DEFAULT_SALT",
    "GOLDEN_DIR",
    "SEEDS_PATH",
    "SEED_MANIFEST_SCHEMA_VERSION",
    "STIMULUS_DIR",
    "GoldenBaselineDriver",
    "MCQOutcome",
    "StimulusOutcome",
    "assert_seed_manifest_consistent",
    "build_seed_manifest",
    "derive_seed",
    "load_seed_manifest",
    "load_stimulus_battery",
    "load_synthetic_fixture",
    "shuffled_mcq_options",
    "shuffled_mcq_order",
    "write_seed_manifest",
]

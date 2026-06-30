"""Loaders for the frozen M13-ES4 task battery + reference data (§6 / §2.2b).

Reads the four ``data/*.yaml`` files (AUT, RAT, curated common-uses, adversarial
labeled set) into frozen dataclasses and validates them against the structural
contract in ``data/_schema.yaml`` (sizes, id uniqueness, enum membership). The
data files are a **frozen pre-registration**: items are not added/removed after a
result. ``numpy``/stdlib + ``yaml`` only; no LLM, no inference backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import yaml

from erre_sandbox.evidence.es4_actuator import constants as _c

if TYPE_CHECKING:
    from collections.abc import Mapping

_DATA_DIR: Final[Path] = Path(__file__).resolve().parent / "data"
SCHEMA_VERSION: Final[str] = "0.1.0-m13es4"
"""Battery data schema version (pinned in ``data/_schema.yaml`` and the test).
Independent of the wire ``erre_sandbox.schemas.SCHEMA_VERSION`` — these are
verdict-side battery files, not Godot-bridge wire types."""

AUT_PROMPT_PLACEHOLDER: Final[str] = "{object}"


@dataclass(frozen=True)
class AutItem:
    """One Alternate Uses Task object (divergent primary)."""

    object_id: str
    object: str
    stratum: str  # "classic" | "novel"


@dataclass(frozen=True)
class AutBattery:
    """The frozen 16-object AUT battery + prompt template."""

    prompt_template: str
    items: tuple[AutItem, ...]

    def prompt_for(self, item: AutItem) -> str:
        """The frozen AUT prompt for ``item`` (single ``{object}`` substitution)."""
        return self.prompt_template.replace(AUT_PROMPT_PLACEHOLDER, item.object)


@dataclass(frozen=True)
class RatItem:
    """One Remote Associates Test triple (convergent supporting)."""

    item_id: str
    cues: tuple[str, str, str]
    answer: str


@dataclass(frozen=True)
class RatBattery:
    """The frozen 16-item RAT battery."""

    items: tuple[RatItem, ...]


@dataclass(frozen=True)
class AdversarialItem:
    """One labeled string for the scorer/judge AUC gate (§3)."""

    text: str
    object: str
    label: str  # "appropriate" | "inappropriate"
    category: str


_ADV_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "good",
        "garbage",
        "word_salad",
        "plausible_off_task",
        "common_use_only",
        "object_mismatch",
        "metaphor_only",
    }
)
_APPROPRIATE_CATEGORIES: Final[frozenset[str]] = frozenset({"good", "common_use_only"})


def _read_yaml(name: str) -> dict[str, Any]:
    parsed = yaml.safe_load((_DATA_DIR / name).read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise TypeError(f"{name}: expected a mapping at root, got {type(parsed)}")
    if parsed.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"{name}: schema_version {parsed.get('schema_version')!r} != "
            f"{SCHEMA_VERSION!r}"
        )
    return parsed


def load_aut_battery() -> AutBattery:
    """Load + validate the AUT battery (16 = 8 classic + 8 novel, unique ids)."""
    raw = _read_yaml("aut_battery.yaml")
    template = str(raw["prompt_template"])
    if AUT_PROMPT_PLACEHOLDER not in template:
        raise ValueError(f"aut prompt_template missing {AUT_PROMPT_PLACEHOLDER!r}")
    items = tuple(
        AutItem(
            object_id=str(it["object_id"]),
            object=str(it["object"]),
            stratum=str(it["stratum"]),
        )
        for it in raw["items"]
    )
    _validate_aut(items)
    return AutBattery(prompt_template=template, items=items)


def _validate_aut(items: tuple[AutItem, ...]) -> None:
    if len(items) != _c.N_AUT:
        raise ValueError(f"AUT count {len(items)} != N_AUT {_c.N_AUT}")
    ids = [it.object_id for it in items]
    if len(set(ids)) != len(ids):
        raise ValueError("AUT object_id values are not unique")
    classic = sum(1 for it in items if it.stratum == "classic")
    novel = sum(1 for it in items if it.stratum == "novel")
    if classic != _c.N_AUT_CLASSIC or novel != _c.N_AUT_NOVEL:
        raise ValueError(
            f"AUT strata classic={classic}/novel={novel} != "
            f"{_c.N_AUT_CLASSIC}/{_c.N_AUT_NOVEL}"
        )
    for it in items:
        if it.stratum not in {"classic", "novel"}:
            raise ValueError(f"AUT {it.object_id}: bad stratum {it.stratum!r}")


def load_rat_battery() -> RatBattery:
    """Load + validate the RAT battery (16 triples, unique ids, 3 cues each)."""
    raw = _read_yaml("rat_battery.yaml")
    items: list[RatItem] = []
    for it in raw["items"]:
        cues = tuple(str(c) for c in it["cues"])
        if len(cues) != 3:  # noqa: PLR2004 — RAT is exactly a 3-cue triple
            raise ValueError(f"RAT {it['item_id']}: expected 3 cues, got {len(cues)}")
        items.append(
            RatItem(
                item_id=str(it["item_id"]),
                cues=(cues[0], cues[1], cues[2]),
                answer=str(it["answer"]),
            )
        )
    if len(items) != _c.N_RAT:
        raise ValueError(f"RAT count {len(items)} != N_RAT {_c.N_RAT}")
    if len({it.item_id for it in items}) != len(items):
        raise ValueError("RAT item_id values are not unique")
    return RatBattery(items=tuple(items))


def load_common_uses() -> dict[str, tuple[str, ...]]:
    """Load + validate the curated common-use anchor (object_id → N_CURATED uses).

    Keys must match the AUT ``object_id`` set exactly, and each object must carry
    exactly ``N_CURATED`` curated uses (the frozen human rarity anchor, §2.2b
    step 1).
    """
    raw = _read_yaml("common_uses.yaml")
    objects: Mapping[str, Any] = raw["objects"]
    out: dict[str, tuple[str, ...]] = {}
    for object_id, uses in objects.items():
        tup = tuple(str(u) for u in uses)
        if len(tup) != _c.N_CURATED:
            raise ValueError(
                f"common_uses[{object_id}] has {len(tup)} != N_CURATED {_c.N_CURATED}"
            )
        out[str(object_id)] = tup
    aut_ids = {it.object_id for it in load_aut_battery().items}
    if set(out) != aut_ids:
        missing = aut_ids - set(out)
        extra = set(out) - aut_ids
        raise ValueError(
            f"common_uses keys != AUT object ids (missing={sorted(missing)}, "
            f"extra={sorted(extra)})"
        )
    return out


def load_adversarial_labeled() -> tuple[AdversarialItem, ...]:
    """Load + validate the frozen adversarial labeled set (§3, ≥120 strings)."""
    raw = _read_yaml("adversarial_labeled.yaml")
    items = tuple(
        AdversarialItem(
            text=str(it["text"]),
            object=str(it["object"]),
            label=str(it["label"]),
            category=str(it["category"]),
        )
        for it in raw["items"]
    )
    for it in items:
        if it.category not in _ADV_CATEGORIES:
            raise ValueError(f"adversarial: bad category {it.category!r}")
        expected = (
            "appropriate" if it.category in _APPROPRIATE_CATEGORIES else "inappropriate"
        )
        if it.label != expected:
            raise ValueError(
                f"adversarial {it.category!r}: label {it.label!r} != {expected!r}"
            )
    n_pos = sum(1 for it in items if it.label == "appropriate")
    n_neg = sum(1 for it in items if it.label == "inappropriate")
    if n_pos == 0 or n_neg == 0:
        raise ValueError("adversarial set needs both classes for an AUC")
    return items


__all__ = [
    "AUT_PROMPT_PLACEHOLDER",
    "SCHEMA_VERSION",
    "AdversarialItem",
    "AutBattery",
    "AutItem",
    "RatBattery",
    "RatItem",
    "load_adversarial_labeled",
    "load_aut_battery",
    "load_common_uses",
    "load_rat_battery",
]

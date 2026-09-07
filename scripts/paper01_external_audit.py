"""Frozen §9 pre-registration for the paper01 G1 external audit (Loop I-002).

The **single source of truth** for every external-audit value
``.steering/20260907-paper01-g1-external-audit/design-final.md`` froze
*before* any adapter / scoring / verdict code runs (forking-paths seal,
mirroring :mod:`erre_sandbox.evidence.es4_actuator.constants`). This module
holds only the module-level ``Final`` constants and the deterministic
``experiments/20260907-paper01-g1/config.json`` writer -- the adapter,
scoring, and verdict logic are out of scope for I-002 and land in I-003+.

Two invariants this module exists to make mechanically checkable
(design-final.md §7, Opus MEDIUM-11 "eliminate tautological ACs"):

1. The five floor/bootstrap thresholds shared with the frozen internal ES-4
   apparatus (``AUC_FLOOR`` / ``REF_DEDUP`` / ``N_R_MIN`` / ``N_R_MAX`` /
   ``CI_ALPHA`` / ``N_RESAMPLES``) are **read through**
   ``erre_sandbox.evidence.es4_actuator.constants`` at call time, never
   copied into a module-level literal here. No top-level assignment in this
   file may carry ``0.8`` / ``0.9`` / ``0.1`` / ``10000`` / ``30`` / ``8`` as
   a literal RHS -- ``tests/test_paper01_g1/test_preregistration.py`` walks
   the AST to enforce it, then monkeypatches the source module and checks
   the read-through actually moves.
2. :func:`collect_preregistration` never caches -- every value is looked up
   from the owning module attribute (``_c.AUC_FLOOR``, the bare
   ``ANCHOR_DRAWS`` global, ...) inside the function body, so a
   ``monkeypatch.setattr`` on this module or on
   ``erre_sandbox.evidence.es4_actuator.constants`` is visible in the very
   next call. That is what lets the AC tests be non-tautological instead of
   "a dict asserts its own fields".

Future note (I-005 scope, not built here): this module will grow a
two-path import helper (ERRE-Sandbox ``src`` layout vs. a standalone
paper-repo layout) once the adapter needs to run outside this repository;
I-002 only needs the straight
``from erre_sandbox.evidence.es4_actuator import constants`` import to
exist.

Claim boundary (design-final.md §0.1 / §8): the external candidate ladder
is named ``X0``..``X6`` (no ``X4``) because it is **not** a 1:1 restaging of
the internal ``C0``..``C6`` menu -- the anchor provenance differs (LLM
self-generation vs. a human rater-common pool), so a curated-only external
variant would just duplicate ``X0`` (see the comment above
``CANDIDATE_LADDER`` below).
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import math
import re
import sys
import urllib.error
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator import controls
from erre_sandbox.evidence.es4_actuator.battery import AdversarialItem

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from types import ModuleType

# --- two-path import helper (design-final.md §7, DA-6) --------------------


def resolve_sibling_script(package_qualname: str, flat_name: str) -> ModuleType:
    """Import one frozen sibling script under either layout this tooling runs in.

    - ERRE-Sandbox layout: importable as ``scripts.<flat_name>`` because the
      repository root sits on ``sys.path`` (``scripts/`` is a namespace
      package -- no ``scripts/__init__.py``).
    - paper-repo layout: ``paper01_fetch_sources.py`` and
      ``es4_scorer_diag.py`` sit flat in ``analysis/scripts/`` with no
      enclosing package, so ``scripts.<flat_name>`` never resolves there.
      ``package_qualname`` failing with :class:`ModuleNotFoundError` falls
      back to a flat ``import <flat_name>`` with *this file's own
      directory* pushed onto ``sys.path`` -- the sibling script is always
      co-located with this file in both layouts, so that fallback resolves
      in a real paper-repo checkout exactly as it does here.
    """
    try:
        return importlib.import_module(package_qualname)
    except ModuleNotFoundError:
        this_dir = str(Path(__file__).resolve().parent)
        if this_dir not in sys.path:
            sys.path.insert(0, this_dir)
        return importlib.import_module(flat_name)


_fetch = resolve_sibling_script(
    "scripts.paper01_fetch_sources", "paper01_fetch_sources"
)
_diag = resolve_sibling_script("scripts.es4_scorer_diag", "es4_scorer_diag")

# --- paths ---------------------------------------------------------------

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EXPERIMENT_DIR: Final[Path] = REPO_ROOT / "experiments" / "20260907-paper01-g1"
SEED_PATH: Final[Path] = EXPERIMENT_DIR / "SEED"
CONFIG_PATH: Final[Path] = EXPERIMENT_DIR / "config.json"
ENV_MD_PATH: Final[Path] = EXPERIMENT_DIR / "env.md"
SOURCE_AUDIT_PATH: Final[Path] = EXPERIMENT_DIR / "data" / "source-audit.json"
CAMBRIDGE_RAW_DIR: Final[Path] = EXPERIMENT_DIR / "data" / "raw"
CAMBRIDGE_FILENAMES: Final[dict[str, str]] = {
    "bowl": "bowl AUT dataset.xlsx",
    "paperclip": "paperclip AUT dataset.xlsx",
}
RESULTS_DIR: Final[Path] = EXPERIMENT_DIR / "results"
EXTERNAL_AUDIT_PATH: Final[Path] = RESULTS_DIR / "external-audit.json"

# --- external-only constants (design-final.md §9, this ADR) --------------

MIN_CLASS_N: Final[int] = 16
"""Gold-class floor a corpus's good/common pool must clear (observation-
independent -- it does not depend on any measured count)."""

ANCHOR_DRAWS: Final[int] = 200
"""B: seeded random draws from the dedup'd anchor pool for ARM-A/ARM-C/ARM-D
(Opus HIGH-5: B=50 left the 5-95 percentile tails unstable at ~2 draws
each)."""

EXT_A2_MIN_SUPPORT: Final[int] = 2
"""ARM-C's A2 high-frequency-support minimum. **Not** the external
counterpart of the internal ``REF_FREQ_MIN`` (a fraction of held-out
generations) -- this is a raw occurrence-count floor over the fixed
``split0`` pool, a structurally different quantity (Opus MEDIUM-2)."""

SEED: Final[int] = 20260907
"""Master seed for every draw in this audit. Must equal the contents of
``experiments/20260907-paper01-g1/SEED`` and the ``PYTHONHASHSEED`` the
operator exports before running I-003+ (design-final.md §8: jaccard-family
candidates do not bit-reproduce without a fixed hash seed)."""

DRAW_AGGREGATION_THRESHOLD: Final[float] = 0.5
"""§5.1: a candidate is eligible/engaged/collapsed iff the *proportion* of
draws whose own per-draw boolean is True is >= this threshold. Never a
marginal median of ``AUC_full`` / ``AUC_LAO`` taken separately -- see
:func:`aggregate_draws`."""

BOOTSTRAP_SCOPE_OPTIONS: Final[tuple[str, ...]] = ("median_draw", "all_draws")
"""The two possible bootstrap-CI scopes; ``BOOTSTRAP_APPLIES_TO`` freezes
which one this audit uses (§5.2)."""

BOOTSTRAP_APPLIES_TO: Final[str] = "median_draw"
"""§5.2: the 90% bootstrap CI (stratified by object x class,
``N_RESAMPLES`` resamples) is computed **only** for the median draw, never
re-run over all ``ANCHOR_DRAWS`` draws."""

VERDICT_ARM_KEY: Final[str] = "ARM-A"
"""The one arm whose median-draw result feeds the §6 judgment rule; every
other arm (B/C/D/X) and both negative controls are sensitivity/diagnostic
only."""

VERDICT_ENUM: Final[tuple[str, ...]] = (
    "PASS",
    "NO_VALID_SCORER",
    "INVALID_TASK_BATTERY",
    "INCONCLUSIVE_UNDERPOWERED",
)
"""§6 verdict language -- exactly these four words. ``source_unavailable``
is a Gate-0 *incomplete status* (Codex HIGH-4), never a verdict, and is
deliberately absent from this tuple."""

# --- corpora (design-final.md §3.1, SHA-256 pinned) -----------------------

CAMBRIDGE_BASE: Final[str] = (
    "https://raw.githubusercontent.com/ghydsgaaa/Cambridge-AUT-dataset/main/data/"
)
OCSAI_BASE: Final[str] = (
    "https://raw.githubusercontent.com/massivetexts/ocsai/main/data/ocsai1/"
)


@dataclasses.dataclass(frozen=True, slots=True)
class CorpusFile:
    """One pinned external-audit source file (design-final.md §3.1)."""

    corpus: str
    identifier: str
    uri: str
    sha256: str
    fmt: str


CORPORA: Final[tuple[CorpusFile, ...]] = (
    CorpusFile(
        corpus="cambridge",
        identifier="bowl",
        uri=CAMBRIDGE_BASE + "bowl%20AUT%20dataset.xlsx",
        sha256="f8caa57cdebe1d8f19257c88e56c5346415f5289897efaa10f4150508341ac2d",
        fmt="xlsx",
    ),
    CorpusFile(
        corpus="cambridge",
        identifier="paperclip",
        uri=CAMBRIDGE_BASE + "paperclip%20AUT%20dataset.xlsx",
        sha256="69e75792d0caa20363bf49a5dd57bbac731f2a19159a6b04753b0617999d7a96",
        fmt="xlsx",
    ),
    CorpusFile(
        corpus="ocsai",
        identifier="train",
        uri=OCSAI_BASE + "finetune-gt_main2_prepared_train.jsonl",
        sha256="7b2ed8fb8a1b3c98dbb86428c222c5806870ab73a280d6e664aee137bf05ddfd",
        fmt="jsonl",
    ),
    CorpusFile(
        corpus="ocsai",
        identifier="val",
        uri=OCSAI_BASE + "finetune-gt_main2_prepared_val.jsonl",
        sha256="a40bc78a5275ad274baeac7f410f7c1beb37e7913b138f5ef5fcfee8e15ccd9b",
        fmt="jsonl",
    ),
    CorpusFile(
        corpus="ocsai",
        identifier="test",
        uri=OCSAI_BASE + "finetune-gt_main2_prepared_test.jsonl",
        sha256="bab9bf8fc28c27113a7d4d55e8f718edbad02214d14d53d98e8c78f07b3a4068",
        fmt="jsonl",
    ),
)

OCSAI_CONCAT_ORDER: Final[tuple[str, ...]] = ("train", "val", "test")
"""Fixed concatenation order; the resulting 0-origin row index is the
canonical scan order for greedy dedupe and SPLIT-BLOCK/SPLIT-PARITY."""

# --- normalisation (design-final.md §3.2, pinned identical to reference.py)

_WS_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


def normalise(text: str) -> str:
    """External-audit text normaliser (design-final.md §3.2, frozen).

    Byte-for-byte the same transform as the internal
    ``erre_sandbox.evidence.es4_actuator.reference._normalise`` --
    ``test_normalise_matches_internal_reference_normalise`` pins the two
    outputs identical so a duplicated-but-diverged copy cannot silently
    drift the near-dup / high-frequency logic.
    """
    return _WS_RE.sub(" ", text.strip().lower())


NORMALISE: Final[Callable[[str], str]] = normalise

NORMALISE_DEFINITION: Final[str] = "re.sub(r'\\s+', ' ', s.strip().lower())"
"""Human-readable form of :data:`NORMALISE` for ``config.json`` (a function
object is not JSON-serialisable)."""

# --- gold binarisation (design-final.md §3.3) ------------------------------

CAMBRIDGE_COMMON_RATING: Final[float] = 1.0
CAMBRIDGE_GOOD_MIN_RATING: Final[float] = 3.0
CAMBRIDGE_EXCLUDE_RULE: Final[str] = (
    "a 0 among rated values, or a 2, or a band-crossing mix,"
    " or a missing Responses cell"
)

OCSAI_COMMON_SCORE: Final[int] = 10
OCSAI_GOOD_MIN_SCORE: Final[int] = 40
OCSAI_EXCLUDE_RULE: Final[str] = "encoded score 11-39"

# --- object sets (design-final.md §3.5, Codex HIGH-2) ----------------------

OCSAI_PRIMARY_OBJECTS: Final[tuple[str, ...]] = (
    "backpack",
    "ball",
    "book",
    "bottle",
    "box",
    "brick",
    "fork",
    "hat",
    "knife",
    "lightbulb",
    "pants",
    "paperclip",
    "pencil",
    "rope",
    "shoe",
    "shovel",
    "sock",
    "spoon",
    "table",
    "tire",
    "toothbrush",
)
"""All 21 distinct Ocsai objects, frozen sorted order -- matches
``experiments/20260907-paper01-g1/data/source-audit.json``
``ocsai.by_object`` keys (Gate 0 measured), pinned by
``test_preregistration_matches_gate0_counts``."""

OCSAI_SENSITIVITY_OBJECTS: Final[tuple[str, ...]] = (
    "brick",
    "paperclip",
    "bottle",
    "shoe",
)
"""The 4 Ocsai objects that overlap the internal apparatus's object set."""

CAMBRIDGE_OBJECTS: Final[tuple[str, ...]] = ("bowl", "paperclip")

# --- splits (design-final.md §3.4, Opus HIGH-7: both frozen) ---------------


@dataclasses.dataclass(frozen=True, slots=True)
class SplitScheme:
    """One pre-registered participant split (design-final.md §3.4)."""

    key: str
    role: str
    definition: str


SPLIT_SCHEMES: Final[tuple[SplitScheme, ...]] = (
    SplitScheme(
        key="SPLIT-BLOCK",
        role="primary",
        definition=(
            "Cambridge: id ascending, first half = split0 / second half ="
            " split1. Ocsai: OCSAI_CONCAT_ORDER row index, first half /"
            " second half. Minimises participant leakage if rows are"
            " participant-contiguous."
        ),
    ),
    SplitScheme(
        key="SPLIT-PARITY",
        role="sensitivity",
        definition=(
            "Cambridge: int(id) % 2. Ocsai: OCSAI_CONCAT_ORDER row-index"
            " parity. The original design; reported alongside SPLIT-BLOCK"
            " because which split is correct is not knowable without"
            " participant IDs (neither corpus has them)."
        ),
    ),
)

# --- anchor arms (design-final.md §4.1/§4.2) --------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class Arm:
    """One pre-registered anchor arm or negative/positive control."""

    key: str
    role: str
    scope: str
    definition: str


ARMS: Final[tuple[Arm, ...]] = (
    Arm(
        key="ARM-A",
        role="verdict",
        scope="all",
        definition=(
            "split0 gold-common pool, frozen-scan-order greedy dedupe"
            " (cosine >= REF_DEDUP), k = min(N_R_MAX, |pool|) seeded"
            " uniform-without-replacement draws, B = ANCHOR_DRAWS. Median"
            " draw feeds the §6 verdict."
        ),
    ),
    Arm(
        key="ARM-B",
        role="sensitivity",
        scope="all",
        definition="Same dedup'd pool, all items, no cap on reference size.",
    ),
    Arm(
        key="ARM-C",
        role="sensitivity",
        scope="ocsai_only",
        definition=(
            "(A1 union A2) dedup'd to k items. A2 = items with occurrence"
            " count >= EXT_A2_MIN_SUPPORT in the same split0 pool. Closest"
            " external analog of the internal recipe's composition."
        ),
    ),
    Arm(
        key="ARM-D",
        role="sensitivity",
        scope="all",
        definition=(
            "Same dedup'd pool, the k items nearest the pool centroid"
            " (deterministic, no draw). Matches typicality to the internal"
            " curated anchor (Opus MEDIUM-12)."
        ),
    ),
    Arm(
        key="ARM-X",
        role="sensitivity",
        scope="paperclip_only",
        definition=(
            "Source-crossed: anchor pool = Cambridge split0 gold-common,"
            " gold = Ocsai paperclip good/common. The only arm where anchor"
            " provenance is genuinely independent of the scored gold"
            " (Codex HIGH-1)."
        ),
    ),
)

NEGATIVE_CONTROLS: Final[tuple[Arm, ...]] = (
    Arm(
        key="NC-1",
        role="control",
        scope="all",
        definition=(
            "Object o is scored against a *different* object o' 's split0"
            " common pool; o' is picked by a deterministic cyclic shift of"
            " OCSAI_PRIMARY_OBJECTS / CAMBRIDGE_OBJECTS. Breaks"
            " object-correspondence while keeping same-population"
            " provenance -- the ARM-A vs. NC-1 contrast is what separates"
            " H_anchor from H_pop (design-final.md §4.2)."
        ),
    ),
    Arm(
        key="NC-2",
        role="control",
        scope="all",
        definition=(
            "Object o is scored against its own split0 *good* pool"
            " (instead of common). A positive control: if ARM-A's"
            " discrimination direction is real, NC-2 should flip it."
        ),
    ),
)

# --- candidate ladder (design-final.md §9) ----------------------------------
#
# NOTE: there is no "X4". design-final.md §0.1: the internal ladder's C4
# ("curated-only reference") exists because the internal C0 anchor is the
# generation model's own high-frequency ideas, so a curated-only variant
# probes a materially different regime. Externally, ARM-A's anchor is
# *already* the rater-common pool (the internal-curated analogue) -- there
# is no model-self-generated second stage to strip out. A separate
# "curated-only" external candidate would therefore just duplicate X0, not
# add a regime. C4 is dropped, not renumbered; the remaining internal
# candidates C0/C1/C2/C3(x3)/C5/C6 map onto X0/X1/X2/X3a-c/X5/X6 in order.


@dataclasses.dataclass(frozen=True, slots=True)
class Candidate:
    """One pre-registered scorer candidate on the external ladder."""

    key: str
    family: str
    description: str
    internal_analog: str


CANDIDATE_LADDER: Final[tuple[Candidate, ...]] = (
    Candidate(
        key="X0",
        family="embedding",
        description="MPNet (all-mpnet-base-v2) 1-max cos rarity, full R",
        internal_analog="C0-mpnet-max-full",
    ),
    Candidate(
        key="X1",
        family="embedding",
        description="MPNet (all-mpnet-base-v2) 1-mean cos rarity, full R",
        internal_analog="C1-mpnet-mean-full",
    ),
    Candidate(
        key="X2",
        family="embedding",
        description="X0 residualised on idea character length",
        internal_analog="C2-lenctrl",
    ),
    Candidate(
        key="X3a",
        family="embedding",
        description="MiniLM (all-MiniLM-L6-v2) 1-max cos rarity, full R",
        internal_analog="C3-MiniLM-max-full",
    ),
    Candidate(
        key="X3b",
        family="embedding",
        description="e5-small-v2 1-max cos rarity, full R",
        internal_analog="C3-e5-small-max-full",
    ),
    Candidate(
        key="X3c",
        family="embedding",
        description="bge-small-en-v1.5 1-max cos rarity, full R",
        internal_analog="C3-bge-small-max-full",
    ),
    Candidate(
        key="X5",
        family="lexical",
        description="lexical 1-max token-Jaccard novelty, full R",
        internal_analog="C5-jaccard-full",
    ),
    Candidate(
        key="X6",
        family="lexical",
        description="TF-IDF mean token rarity vs. reference corpus",
        internal_analog="C6-tfidf-selfrarity",
    ),
)

EMBEDDING_FAMILY_EXT: Final[tuple[str, ...]] = tuple(
    c.key for c in CANDIDATE_LADDER if c.family == "embedding"
)
"""The primary-verdict candidate family: the first 6 (X5/X6 are lexical,
never eligible for the §6 judgment)."""

# --- §5.1 draw aggregation / §4.1 draw sizing --------------------------------


def aggregate_draws(flags: Sequence[bool]) -> bool:
    """§5.1: candidate-level boolean = proportion of True draws >= threshold.

    Each draw's own boolean (``eligible_b`` / ``engaged_b`` /
    ``collapsed_b``) is decided first; this aggregates *those booleans*, not
    a marginal median of the underlying continuous statistic -- the
    alternative design-final.md §5.1 explicitly rejects.
    """
    if not flags:
        return False
    true_count = sum(1 for flag in flags if flag)
    return (true_count / len(flags)) >= DRAW_AGGREGATION_THRESHOLD


def draw_size(pool_size: int) -> int:
    """``k = min(N_R_MAX, |pool|)`` (design-final.md §4.1, Codex HIGH-3)."""
    return min(_c.N_R_MAX, pool_size)


def draws_effective(pool_size: int) -> int:
    """Distinct draws actually possible for a pool of ``pool_size``.

    When ``|pool| < N_R_MAX`` the draw is the whole pool every time (only
    one arrangement exists), so ``draws_effective`` is 1 regardless of
    ``ANCHOR_DRAWS``; otherwise every one of the ``ANCHOR_DRAWS`` seeded
    draws can differ.
    """
    return ANCHOR_DRAWS if pool_size >= _c.N_R_MAX else 1


# --- collection / config.json --------------------------------------------


def collect_preregistration() -> dict[str, Any]:
    """Collect every frozen §9 value by reading module attributes *now*.

    Deliberately non-cached: every value below is read from its owning
    attribute at call time (``_c.AUC_FLOOR``, the bare ``ANCHOR_DRAWS``
    module global, ...), never a value baked in at import time. This is
    what makes ``monkeypatch.setattr`` on this module or on
    ``erre_sandbox.evidence.es4_actuator.constants`` visible in the very
    next call -- the mechanism ``test_preregistration_constants_match_config``
    and ``test_thresholds_are_imported_not_redefined`` use to prove the
    freeze is a real read-through, not a tautological self-comparison
    (design-final.md §7, Opus MEDIUM-11).
    """
    return {
        "seed": SEED,
        "min_class_n": MIN_CLASS_N,
        "anchor_draws": ANCHOR_DRAWS,
        "ext_a2_min_support": EXT_A2_MIN_SUPPORT,
        "draw_aggregation_threshold": DRAW_AGGREGATION_THRESHOLD,
        "bootstrap_applies_to": BOOTSTRAP_APPLIES_TO,
        "thresholds": {
            "auc_floor": _c.AUC_FLOOR,
            "ref_dedup": _c.REF_DEDUP,
            "n_r_min": _c.N_R_MIN,
            "n_r_max": _c.N_R_MAX,
            "ci_alpha": _c.CI_ALPHA,
            "n_resamples": _c.N_RESAMPLES,
        },
        "corpora": [dataclasses.asdict(corpus) for corpus in CORPORA],
        "ocsai_concat_order": list(OCSAI_CONCAT_ORDER),
        "normalise_definition": NORMALISE_DEFINITION,
        "binarisation": {
            "cambridge": {
                "common_rating": CAMBRIDGE_COMMON_RATING,
                "good_min_rating": CAMBRIDGE_GOOD_MIN_RATING,
                "exclude": CAMBRIDGE_EXCLUDE_RULE,
            },
            "ocsai": {
                "common_score": OCSAI_COMMON_SCORE,
                "good_min_score": OCSAI_GOOD_MIN_SCORE,
                "exclude": OCSAI_EXCLUDE_RULE,
            },
        },
        "objects": {
            "ocsai_primary": list(OCSAI_PRIMARY_OBJECTS),
            "ocsai_sensitivity": list(OCSAI_SENSITIVITY_OBJECTS),
            "cambridge": list(CAMBRIDGE_OBJECTS),
        },
        "split_schemes": [dataclasses.asdict(split) for split in SPLIT_SCHEMES],
        "arms": [dataclasses.asdict(arm) for arm in ARMS],
        "verdict_arm": VERDICT_ARM_KEY,
        "negative_controls": [
            dataclasses.asdict(control) for control in NEGATIVE_CONTROLS
        ],
        "candidate_ladder": [
            dataclasses.asdict(candidate) for candidate in CANDIDATE_LADDER
        ],
        "embedding_family_ext": list(EMBEDDING_FAMILY_EXT),
        "verdict_enum": list(VERDICT_ENUM),
    }


def config_matches_preregistration(config: Mapping[str, Any]) -> bool:
    """True iff a loaded ``config.json`` still equals the live constants.

    Calls :func:`collect_preregistration` fresh on every invocation, so this
    is the one comparison both the round-trip test and the
    monkeypatch-mismatch test exercise -- there is no separate "expected"
    dict that could itself drift from the constants unnoticed.
    """
    return dict(config) == collect_preregistration()


def write_config(path: Path = CONFIG_PATH) -> None:
    """Write ``config.json`` deterministically: no wall-clock, sorted keys.

    ``sort_keys=True`` + fixed ``indent`` make two independent runs
    byte-identical (I-008's reproducibility requirement) as long as the
    frozen constants above have not changed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        collect_preregistration(), indent=2, sort_keys=True, ensure_ascii=False
    )
    path.write_text(payload + "\n", encoding="utf-8")


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Read back a previously written ``config.json``."""
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


# --- SEED file --------------------------------------------------------------


def write_seed_file(path: Path = SEED_PATH) -> None:
    """Write the master seed as plain decimal text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{SEED}\n", encoding="utf-8")


def load_seed_file(path: Path = SEED_PATH) -> int:
    """Read back the master seed written by :func:`write_seed_file`."""
    return int(path.read_text(encoding="utf-8").strip())


# --- env.md -------------------------------------------------------------

ENV_MD_TEXT: Final[str] = """# 実行環境 (paper01 G1 外部監査)

## Python / パッケージ管理

- Python 3.11 (`pyproject.toml` `requires-python = ">=3.11,<3.12"`)
- 依存は `uv.lock` を SSOT として固定 (`uv sync --frozen`)。CI 既定は
  extras 無しで走る。I-002 (本モジュール) は stdlib のみで完結し、
  encoder は一切ロードしない。

## 二経路 (Windows / WSL2)

- Windows: `.venv/Scripts/python.exe`
- WSL2 / Linux: `.venv/bin/python`
- **本監査は CPU のみで完結する** (Gate 1 実測、2026-09-07)。encoder 4 種は
  HF キャッシュから `HF_HUB_OFFLINE=1` で load でき、GPU も sglang の
  phase-flip も不要。WSL2 GPU 経路は使わない。
- cross-platform float drift (libm 1-ULP) はあるため、JSON へ emit する
  float は量子化した上で照合する
  (`feedback_golden_crossplatform_float_drift.md` の教訓を踏襲)。

## encoder (I-003 以降で使用、本 issue では未使用)

`[eval]` extras で導入される `sentence-transformers==3.4.1` 経由:

- `sentence-transformers/all-mpnet-base-v2` (incumbent, X0/X1/X2)
- `sentence-transformers/all-MiniLM-L6-v2` (X3a)
- `intfloat/e5-small-v2` (X3b)
- `BAAI/bge-small-en-v1.5` (X3c)

CI は `[eval]` extras を入れない。判定規則の test はすべて encoder
非依存 (§7)。

## PYTHONHASHSEED

`SEED` ファイル (= `experiments/20260907-paper01-g1/SEED`) の値
(`20260907`) を `PYTHONHASHSEED` にも設定してから I-003 以降の実走を
起動すること:

```bash
export PYTHONHASHSEED=20260907
```

```powershell
$env:PYTHONHASHSEED = "20260907"
```

固定しない場合、jaccard 系候補 (X5) の集合演算がプロセスをまたいで
bit 再現しない (design-final.md §8)。
"""


def write_env_md(path: Path = ENV_MD_PATH) -> None:
    """Write the static environment note (no network / no measurement)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ENV_MD_TEXT, encoding="utf-8")


# --- §6 decision rule (Loop I-003, encoder-independent pure logic) --------
#
# design-final.md §6 is the single source of truth for this section; the
# pseudocode there is transcribed literally into ``decide_external`` below.
# Two failure modes Opus TASK-PRE HIGH-2 found in the naive first draft
# (design-final.md §6 bullet list, DA-G1-10 / DA-G1-11) are the reason this
# is its own reviewed block instead of an inline one-liner:
#
# 1. ``not engaged(c) => auc_lao == auc_full >= floor => not collapsed(c)``
#    holds identically, so a naive rule that computes ``collapsed`` over the
#    *full* eligible set ``E`` (not the engaged subset ``E2``) can never
#    reach ``NO_VALID_SCORER`` once a single eligible, zero-potency
#    (``audit_not_engaged``) candidate exists -- that candidate is eligible,
#    never engaged, and therefore never collapsed, which blocks the
#    ``collapsed == E`` equality forever.
# 2. Restricting both ``engaged`` and ``collapsed`` to be computed *within*
#    the same ``E2`` (this module never computes a ``collapsed``-over-``E``
#    quantity) closes that hole: a zero-potency candidate is simply absent
#    from ``E2``, so it cannot block ``collapsed == E2`` from becoming true
#    for the *other* (truly engaged) candidates.


@dataclasses.dataclass(frozen=True, slots=True)
class CandidateExternalReport:
    """One scored candidate's §5.1 draw-level and §5.2 bootstrap summary.

    Encoder-independent by construction: every field here is a plain value
    the (out-of-scope-for-I-003) adapter/statistics layer would compute --
    this dataclass is what lets ``decide_external`` and its tests never
    import an encoder.

    ``eligible_flags`` / ``engaged_flags`` are the per-draw §5.1 booleans
    (``aggregate_draws`` turns each into the candidate-level boolean).
    ``collapsed_flags`` is the per-draw §5.1 ``collapsed_b`` sequence used
    only for the *reported* "collapsed draw share" diagnostic (§5.1's
    ``mean_b(collapsed_b)``) -- ``decide_external`` itself never reads it;
    the §6 verdict's ``collapsed`` set is decided from the §5.2 bootstrap CI
    on the median draw instead (``auc_lao_ci_lower`` / ``auc_lao_ci_upper``).
    ``audit_not_engaged`` mirrors DA-G1-11's per-candidate marker (``not
    engaged(c)``); it is carried here for downstream reporting only and is
    never promoted to verdict vocabulary (S3 boundary).
    """

    key: str
    family: str
    eligible_flags: tuple[bool, ...]
    engaged_flags: tuple[bool, ...]
    collapsed_flags: tuple[bool, ...]
    auc_lao_ci_lower: float
    auc_lao_ci_upper: float
    potency_at_median_draw: float
    auc_full_at_median_draw: float
    auc_lao_at_median_draw: float
    drop_at_median_draw: float
    audit_not_engaged: bool


@dataclasses.dataclass(frozen=True, slots=True)
class ExternalVerdict:
    """The §6 total verdict plus every set it was derived from.

    ``eligible`` / ``engaged`` / ``survivors`` / ``collapsed`` are candidate
    ``key`` tuples in :data:`EMBEDDING_FAMILY_EXT` declared order (never
    input order), so two calls over the same logical candidate set are
    byte-comparable regardless of the order ``reports`` was passed in.
    """

    verdict: str
    collapse_reproduced: bool
    eligible: tuple[str, ...]
    engaged: tuple[str, ...]
    survivors: tuple[str, ...]
    collapsed: tuple[str, ...]
    reason: str
    auc_floor: float
    min_class_n: int


def _decision_reason(
    verdict: str,
    *,
    class_sizes: Mapping[str, int],
    min_class_n: int,
    eligible: Sequence[CandidateExternalReport],
    engaged: Sequence[CandidateExternalReport],
    survivors: Sequence[CandidateExternalReport],
    collapsed: Sequence[CandidateExternalReport],
) -> str:
    """Human-readable justification for one :func:`decide_external` call."""
    if verdict == "INVALID_TASK_BATTERY":
        deficient = sorted(k for k, n in class_sizes.items() if n < min_class_n)
        if deficient:
            classes = ", ".join(deficient)
            return f"gold class below MIN_CLASS_N={min_class_n}: {classes}"
        if not eligible:
            return (
                "no candidate is eligible: AUC_full is below floor on the"
                " majority of draws for every candidate"
            )
        return (
            "every eligible candidate is audit_not_engaged (potency=0 on the"
            " majority of draws); the LAO apparatus never activated"
        )
    if verdict == "PASS":
        keys = ", ".join(r.key for r in survivors)
        return f"{len(survivors)} survivor(s) with CI_lower(AUC_LAO) >= floor: {keys}"
    if verdict == "NO_VALID_SCORER":
        keys = ", ".join(r.key for r in collapsed)
        return f"all {len(engaged)} engaged candidate(s) collapsed under LAO: {keys}"
    return (
        f"{len(engaged)} engaged candidate(s), no survivor, {len(collapsed)} fully"
        " collapsed -- the remainder's CI straddles the floor"
    )


def decide_external(
    reports: Sequence[CandidateExternalReport],
    *,
    class_sizes: Mapping[str, int],
) -> ExternalVerdict:
    """§6 total decision rule -- transcribed literally from design-final.md.

    ``AUC_FLOOR`` is read from ``erre_sandbox.evidence.es4_actuator.
    constants`` *inside this call* (never baked in at import time), so a
    ``monkeypatch.setattr(_c, "AUC_FLOOR", ...)`` before the call moves the
    verdict -- design-final.md §6's explicit non-tautology requirement.

    ``reports`` outside :data:`EMBEDDING_FAMILY_EXT` (the lexical ``X5`` /
    ``X6`` candidates) never enter ``E`` and therefore can never move the
    verdict, satisfying design-final.md §6's "X5/X6 は判定に一切影響しない".
    """
    floor = _c.AUC_FLOOR
    min_class_n = MIN_CLASS_N

    by_key = {r.key: r for r in reports}
    # mutation target (4): EMBEDDING_FAMILY_EXT への限定 -- the *sole* gate that
    # keeps X5/X6 (lexical) out of E; by_key above is deliberately unfiltered
    # so this is the only line responsible for the restriction (no redundant
    # second filter to silently keep a mutation here a no-op).
    family = [by_key[key] for key in EMBEDDING_FAMILY_EXT if key in by_key]

    # mutation target (1): eligible 判定 -- E
    eligible = [r for r in family if aggregate_draws(r.eligible_flags)]
    # mutation target (2): engaged 判定 -- E2 (subset of E)
    engaged = [r for r in eligible if aggregate_draws(r.engaged_flags)]
    # mutation target (5): CI 跨ぎ判定 (survivor side) -- CI_lower(AUC_LAO) >= floor
    survivors = [r for r in engaged if r.auc_lao_ci_lower >= floor]
    # mutation target (3): collapsed 判定 -- CI_upper(AUC_LAO) < floor, over E2 only
    collapsed = [r for r in engaged if r.auc_lao_ci_upper < floor]

    class_deficient = any(n < min_class_n for n in class_sizes.values())

    if class_deficient or not eligible or not engaged:
        verdict = "INVALID_TASK_BATTERY"
    elif survivors:
        verdict = "PASS"
    elif len(collapsed) == len(engaged):
        verdict = "NO_VALID_SCORER"
    else:
        verdict = "INCONCLUSIVE_UNDERPOWERED"

    reason = _decision_reason(
        verdict,
        class_sizes=class_sizes,
        min_class_n=min_class_n,
        eligible=eligible,
        engaged=engaged,
        survivors=survivors,
        collapsed=collapsed,
    )

    return ExternalVerdict(
        verdict=verdict,
        collapse_reproduced=verdict == "NO_VALID_SCORER",
        eligible=tuple(r.key for r in eligible),
        engaged=tuple(r.key for r in engaged),
        survivors=tuple(r.key for r in survivors),
        collapsed=tuple(r.key for r in collapsed),
        reason=reason,
        auc_floor=floor,
        min_class_n=min_class_n,
    )


# --- §5 statistics (Loop I-004, encoder-independent) ----------------------
#
# design-final.md §1 / §5 is the single source of truth for this section.
# Every function below is encoder-independent by construction: they consume
# already-scored ``float`` arrays (rarity scores, membership similarities,
# per-item labels/objects) -- never text, never an embedding model. The
# adapter that produces those arrays from raw corpora is out of scope here
# (I-005+). Object-internal AUC is always delegated to the **frozen**
# ``controls.auc`` (design-final.md §7: "frozen apparatus ... 無改変") --
# nothing in this section reimplements Mann-Whitney tie handling.


def auc_stratified(
    scores: Sequence[float], labels: Sequence[int], objects: Sequence[str]
) -> float:
    """§1 primary estimand: within-object AUC weighted by object class counts.

    ``AUC_strat(s) = sum_o w(o)*AUC_o(s) / sum_o w(o)``, ``w(o) = n_good(o) *
    n_common(o)``, restricted to objects with ``n_good(o) >= 1`` and
    ``n_common(o) >= 1`` -- an object missing either class contributes
    weight 0 and is excluded from both the numerator and the denominator
    (design-final.md §1, Opus HIGH-4: the internal pooled AUC is "almost
    entirely a between-object statistic" once objects are this unbalanced).

    Each object's internal AUC is computed by :func:`controls.auc` --
    frozen, never reimplemented, so tie handling stays exactly the
    apparatus's own.

    Returns ``0.5`` when no object clears both class minimums (no
    information), matching ``controls.auc``'s own single-class convention
    rather than raising.
    """
    scores_arr = np.asarray(scores, dtype=float)
    labels_arr = np.asarray(labels, dtype=int)
    objects_arr = np.asarray(objects, dtype=object)

    weighted_sum = 0.0
    weight_total = 0.0
    for obj in dict.fromkeys(objects_arr.tolist()):
        mask = objects_arr == obj
        obj_labels = labels_arr[mask]
        n_good = int((obj_labels == 1).sum())
        n_common = int((obj_labels == 0).sum())
        if n_good == 0 or n_common == 0:
            continue
        weight = n_good * n_common
        obj_auc = controls.auc(scores_arr[mask].tolist(), obj_labels.tolist())
        weighted_sum += weight * obj_auc
        weight_total += weight

    if weight_total == 0.0:
        return 0.5
    return weighted_sum / weight_total


# --- §5.1 draw-level booleans / candidate aggregation ----------------------


@dataclasses.dataclass(frozen=True, slots=True)
class DrawResult:
    """One anchor draw's §5.1 continuous statistics for one candidate."""

    auc_full: float
    auc_lao: float
    potency: float

    @property
    def drop(self) -> float:
        """``AUC_strat(full) - AUC_strat(LAO)`` for this draw (design-final.md §1)."""
        return self.auc_full - self.auc_lao


def is_draw_eligible(auc_full: float, *, floor: float | None = None) -> bool:
    """§5.1 ``eligible_b``: this draw's ``AUC_strat(full)`` clears the floor.

    ``floor`` defaults to ``erre_sandbox.evidence.es4_actuator.
    constants.AUC_FLOOR``, read at call time (never cached at import time).
    """
    threshold = _c.AUC_FLOOR if floor is None else floor
    return auc_full >= threshold


def is_draw_engaged(potency: float) -> bool:
    """§5.1 ``engaged_b``: the LAO audit actually fired on this draw."""
    return potency > 0.0


def is_draw_collapsed(
    *, eligible: bool, engaged: bool, auc_lao: float, floor: float | None = None
) -> bool:
    """§5.1 ``collapsed_b``: eligible AND engaged AND ``AUC_strat(LAO) < floor``."""
    threshold = _c.AUC_FLOOR if floor is None else floor
    return eligible and engaged and auc_lao < threshold


def draw_flags(
    draws: Sequence[DrawResult], *, floor: float | None = None
) -> tuple[tuple[bool, ...], tuple[bool, ...], tuple[bool, ...]]:
    """Per-draw ``(eligible_b, engaged_b, collapsed_b)`` tuples aligned to ``draws``.

    §5.1's three booleans, decided independently for each draw.
    """
    eligible_flags = tuple(is_draw_eligible(d.auc_full, floor=floor) for d in draws)
    engaged_flags = tuple(is_draw_engaged(d.potency) for d in draws)
    collapsed_flags = tuple(
        is_draw_collapsed(eligible=e, engaged=g, auc_lao=d.auc_lao, floor=floor)
        for e, g, d in zip(eligible_flags, engaged_flags, draws, strict=True)
    )
    return eligible_flags, engaged_flags, collapsed_flags


def median_draw_index(drops: Sequence[float]) -> int:
    """Index of the draw whose ``drop`` equals the median (design-final.md §5.2).

    Deterministic lower-side tie-break for an even-length sequence: sorted
    by ``(value, original index)``, the returned index is the element at
    rank ``(n - 1) // 2`` -- the standard middle element for odd ``n``, and
    the *lower* of the two middle elements for even ``n``. This is the one
    draw the §5.2 bootstrap and §5.3 permutation test are computed on; no
    other draw ever feeds either.
    """
    if not drops:
        msg = "median_draw_index requires at least one draw"
        raise ValueError(msg)
    order = sorted(range(len(drops)), key=lambda i: (drops[i], i))
    return order[(len(order) - 1) // 2]


@dataclasses.dataclass(frozen=True, slots=True)
class DrawAggregate:
    """§5.1 candidate-level aggregate over a candidate's anchor draws."""

    eligible: bool
    engaged: bool
    collapsed: bool
    collapsed_draw_share: float
    median_drop: float
    drop_p5: float
    drop_p95: float
    median_draw_index: int


def aggregate_candidate_draws(
    draws: Sequence[DrawResult], *, floor: float | None = None
) -> DrawAggregate:
    """§5.1: decide each draw's booleans first, then aggregate the booleans.

    Never a marginal median of ``AUC_full`` / ``AUC_LAO`` taken separately
    -- design-final.md §5.1 explicitly rejects that design because it can
    judge a ``(full, LAO)`` combination that no single draw ever produced.
    The candidate-level ``eligible`` / ``engaged`` / ``collapsed`` booleans
    always come from :func:`aggregate_draws` (proportion of True draws
    ``>= DRAW_AGGREGATION_THRESHOLD``) over the per-draw booleans computed
    by :func:`draw_flags`. ``collapsed_draw_share`` / ``median_drop`` /
    ``drop_p5`` / ``drop_p95`` are the §5.1 reporting statistics -- display
    only, never inputs to the booleans above.
    """
    if not draws:
        msg = "aggregate_candidate_draws requires at least one draw"
        raise ValueError(msg)

    eligible_flags, engaged_flags, collapsed_flags = draw_flags(draws, floor=floor)
    drops = [d.drop for d in draws]

    return DrawAggregate(
        eligible=aggregate_draws(eligible_flags),
        engaged=aggregate_draws(engaged_flags),
        collapsed=aggregate_draws(collapsed_flags),
        collapsed_draw_share=float(np.mean(collapsed_flags)),
        median_drop=float(np.median(drops)),
        drop_p5=float(np.percentile(drops, 5)),
        drop_p95=float(np.percentile(drops, 95)),
        median_draw_index=median_draw_index(drops),
    )


# --- §5.2 bootstrap (stratified by object x class) --------------------------


def bootstrap_resample_indices(
    labels: Sequence[int], objects: Sequence[str], rng: np.random.Generator
) -> list[int]:
    """§5.2: one resample's item indices, stratified by ``(object x class)``.

    Within every ``(object, label)`` stratum, draws ``len(stratum)`` indices
    with replacement from that stratum only -- never across objects, never
    across classes. This is what keeps every object's ``n_good`` /
    ``n_common`` (and therefore :func:`auc_stratified`'s per-object weight
    ``w(o)``) identical across every resample; only *which* items land in
    each slot varies (design-final.md §5.2, Opus fact-check #3: the
    bootstrap procedure had never been pre-registered).
    """
    labels_arr = np.asarray(labels)
    objects_arr = np.asarray(objects, dtype=object)
    resampled: list[int] = []
    for obj in dict.fromkeys(objects_arr.tolist()):
        for cls in (0, 1):
            stratum = np.flatnonzero((objects_arr == obj) & (labels_arr == cls))
            if stratum.size == 0:
                continue
            draw = rng.integers(0, stratum.size, size=stratum.size)
            resampled.extend(int(i) for i in stratum[draw])
    return resampled


@dataclasses.dataclass(frozen=True, slots=True)
class BootstrapDropResult:
    """§5.2 bootstrap CI outputs for one candidate's median draw."""

    auc_full_ci: tuple[float, float]
    auc_lao_ci: tuple[float, float]
    drop_ci: tuple[float, float]
    p_drop_le_zero: float


def bootstrap_stratified_drop(
    scores_full: Sequence[float],
    scores_lao: Sequence[float],
    labels: Sequence[int],
    objects: Sequence[str],
    *,
    seed: int,
) -> BootstrapDropResult:
    """§5.2: stratified (object x class) bootstrap of AUC_strat(full/LAO)/drop.

    Applies to a single draw's items only -- callers pass the median draw
    (design-final.md §5.2 ``BOOTSTRAP_APPLIES_TO``), never loop this over
    every anchor draw. ``N_RESAMPLES`` / ``CI_ALPHA`` are read from
    ``erre_sandbox.evidence.es4_actuator.constants`` *inside this call*,
    never cached, so a test can ``monkeypatch.setattr(_c, "N_RESAMPLES",
    ...)`` to keep the resample count small without touching this
    function's signature. RNG is caller-seeded
    (``np.random.default_rng(seed)``) so two calls with the same ``seed``
    reproduce bit-identically and different seeds diverge.
    """
    n_resamples = _c.N_RESAMPLES
    alpha = _c.CI_ALPHA
    full_list = list(scores_full)
    lao_list = list(scores_lao)
    labels_list = list(labels)
    objects_list = list(objects)

    rng = np.random.default_rng(seed)
    full_draws = np.empty(n_resamples, dtype=float)
    lao_draws = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        idx = bootstrap_resample_indices(labels_list, objects_list, rng)
        resample_labels = [labels_list[j] for j in idx]
        resample_objects = [objects_list[j] for j in idx]
        full_draws[i] = auc_stratified(
            [full_list[j] for j in idx], resample_labels, resample_objects
        )
        lao_draws[i] = auc_stratified(
            [lao_list[j] for j in idx], resample_labels, resample_objects
        )
    drop_draws = full_draws - lao_draws

    lower_q = alpha / 2.0
    upper_q = 1.0 - lower_q
    return BootstrapDropResult(
        auc_full_ci=(
            float(np.quantile(full_draws, lower_q)),
            float(np.quantile(full_draws, upper_q)),
        ),
        auc_lao_ci=(
            float(np.quantile(lao_draws, lower_q)),
            float(np.quantile(lao_draws, upper_q)),
        ),
        drop_ci=(
            float(np.quantile(drop_draws, lower_q)),
            float(np.quantile(drop_draws, upper_q)),
        ),
        p_drop_le_zero=float(np.mean(drop_draws <= 0.0)),
    )


# --- §5.3 permutation p (exploratory, out of the draw loop) -----------------


def permutation_p_stratified(
    scores: Sequence[float],
    labels: Sequence[int],
    objects: Sequence[str],
    *,
    seed: int,
) -> float:
    """§5.3 exploratory label-shuffle permutation p for ``AUC_strat(full)``.

    **Never feeds the §6 verdict** (design-final.md §5.3) -- descriptive
    only. Deliberately **not** looped per anchor draw: ``scripts/
    es4_scorer_diag.py``'s ``gold_good_vs_common`` already burns
    ``N_RESAMPLES`` (10000) permutations per call, each recomputing AUC
    through ``controls.auc``'s Python tie-ranking loop; at 200 draws x 8
    candidates x 2 corpora x 2 statistics (full/LAO) that would run many
    hours. Callers invoke this exactly once per ``corpus x candidate x
    arm``, on the representative median draw (see
    :func:`build_candidate_report`) -- never inside the per-draw loop that
    decides eligible/engaged/collapsed.
    """
    observed = auc_stratified(scores, labels, objects)
    n_resamples = _c.N_RESAMPLES
    rng = np.random.default_rng(seed)
    labels_arr = np.asarray(labels)
    scores_list = list(scores)
    objects_list = list(objects)

    null = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        shuffled = rng.permutation(labels_arr).tolist()
        null[i] = auc_stratified(scores_list, shuffled, objects_list)
    return float((1.0 + np.sum(null >= observed)) / (n_resamples + 1.0))


# --- §5.4 five-tuple (orientation frozen) -----------------------------------


def auc_membership(membership: Sequence[float], labels: Sequence[int]) -> float:
    """§5.4 ``AUC_membership = auc(1 - m, label_good)`` -- orientation frozen.

    ``membership`` (``m``) is each item's max similarity to the anchor
    pool: higher ``m`` means "closer to a curated reference", i.e. more
    common-like. Flipping the sign (``1 - m``) aligns the direction with
    every rarity candidate on the ladder (higher score = more good/novel).
    Passing ``m`` unflipped silently inverts the discrimination direction
    (design-final.md §5.4, Opus HIGH-9).
    """
    flipped = [1.0 - m for m in membership]
    return controls.auc(flipped, labels)


@dataclasses.dataclass(frozen=True, slots=True)
class PotencyResult:
    """§5.4 ``potency`` and per-class near-dup rate (report-only)."""

    potency: float
    near_dup_good: float
    near_dup_common: float


def potency_and_near_dup(
    max_similarity: Sequence[float],
    labels: Sequence[int],
    *,
    ref_dedup: float | None = None,
) -> PotencyResult:
    """§5.4: ``potency`` and per-class near-dup rate over the anchor pool.

    ``potency = |{x : max_r sim(x,r) >= REF_DEDUP}| / |scored items|``;
    ``near_dup_good`` / ``near_dup_common`` are the same fraction restricted
    to each gold class. ``ref_dedup`` defaults to
    ``erre_sandbox.evidence.es4_actuator.constants.REF_DEDUP``, read at
    call time (never cached).
    """
    threshold = _c.REF_DEDUP if ref_dedup is None else ref_dedup
    sims = np.asarray(max_similarity, dtype=float)
    labels_arr = np.asarray(labels, dtype=int)
    if sims.size == 0:
        return PotencyResult(0.0, 0.0, 0.0)

    near_dup = sims >= threshold
    potency_value = float(near_dup.mean())
    good_mask = labels_arr == 1
    common_mask = labels_arr == 0
    near_dup_good = float(near_dup[good_mask].mean()) if good_mask.any() else 0.0
    near_dup_common = float(near_dup[common_mask].mean()) if common_mask.any() else 0.0
    return PotencyResult(potency_value, near_dup_good, near_dup_common)


def mean_dropped_anchor_fraction(
    dropped_counts: Sequence[int], reference_sizes: Sequence[int]
) -> float:
    """§5.4 additional report: mean over items of anchors-dropped-by-LAO / |R_o|.

    Reporting-only (Opus MEDIUM-3); never feeds §6's verdict. Callers pass
    the per-item LAO bookkeeping (which anchors were dropped for which
    item) -- computing that bookkeeping is the adapter's job (I-005+), this
    function only aggregates already-counted values.
    """
    counts = np.asarray(dropped_counts, dtype=float)
    sizes = np.asarray(reference_sizes, dtype=float)
    if counts.size == 0:
        return 0.0
    with np.errstate(divide="ignore", invalid="ignore"):
        fractions = np.where(sizes > 0, counts / sizes, 0.0)
    return float(np.mean(fractions))


# --- candidate-report integration (feeds decide_external unmodified) -------


@dataclasses.dataclass(frozen=True, slots=True)
class DrawItems:
    """One anchor draw's item-level §5 inputs for one candidate.

    The adapter/encoder layer (out of I-004 scope, lands in I-005+) scores
    each item's ``rarity`` against this draw's full anchor set
    (``scores_full``) and its leave-anchor-out variant (``scores_lao``),
    shares the same ``labels`` (1=good/0=common) and ``objects`` (the
    item's ``object_id``) across both, and reports this draw's already
    computed ``potency``. This module only consumes these arrays.
    """

    scores_full: tuple[float, ...]
    scores_lao: tuple[float, ...]
    labels: tuple[int, ...]
    objects: tuple[str, ...]
    potency: float


def draw_result_from_items(items: DrawItems) -> DrawResult:
    """Compute one draw's §5.1 continuous statistics from its item arrays."""
    return DrawResult(
        auc_full=auc_stratified(items.scores_full, items.labels, items.objects),
        auc_lao=auc_stratified(items.scores_lao, items.labels, items.objects),
        potency=items.potency,
    )


@dataclasses.dataclass(frozen=True, slots=True)
class CandidateStatisticalSummary:
    """§5's full external-audit statistical summary for one candidate.

    ``report`` is exactly what feeds :func:`decide_external` (I-003's
    frozen interface, unmodified by this issue). ``bootstrap`` carries the
    §5.2 outputs that have no field on :class:`CandidateExternalReport`
    (the ``AUC_strat_full`` CI and ``P(drop <= 0)``) -- reporting-only, per
    design-final.md §5.2/§5.4. ``permutation_p`` is the §5.3 representative
    permutation p-value (exploratory only, never fed into
    ``decide_external``).

    ``aggregate`` carries §5.1's *required* reporting statistics -- the
    collapsed-draw share, ``median_b(drop)`` and the 5-95 percentile band
    over draws. These are genuine across-draw summaries, unlike the
    ``*_at_median_draw`` fields on ``report``, which are the single
    median-by-drop draw's values. The two can disagree, because the
    median draw is picked by ``drop``: on Cambridge SPLIT-PARITY, X0 has
    ``auc_full_at_median_draw`` 0.8156 while only 32.5% of draws clear
    the floor. Distinct names stop that being read as ``median_b(.)``.
    """

    report: CandidateExternalReport
    aggregate: DrawAggregate
    bootstrap: BootstrapDropResult
    permutation_p: float
    median_draw_index: int


def build_candidate_report(
    key: str,
    family: str,
    draws: Sequence[DrawItems],
    *,
    bootstrap_seed: int,
    permutation_seed: int,
) -> CandidateStatisticalSummary:
    """Assemble one candidate's full §5 statistical summary from its draws.

    ``draws`` is the per-anchor-draw sequence already scored elsewhere (the
    adapter/encoder layer, out of I-004 scope) -- each :class:`DrawItems`
    holds one draw's item-level arrays plus that draw's already-computed
    ``potency``.

    §5.1's draw booleans are decided per draw (:func:`draw_flags`), then
    aggregated by :func:`aggregate_draws` (proportion >= threshold), never
    a marginal median of the continuous statistics.

    §5.2's bootstrap and §5.3's permutation test are each computed
    **once**, on the single median-drop draw (design-final.md §5.2/§5.3) --
    this function calls :func:`bootstrap_stratified_drop` and
    :func:`permutation_p_stratified` by their bare module-level names (not
    an injected parameter), so a test can ``monkeypatch.setattr`` either
    one on this module and observe the call count directly, independent of
    how many draws are passed in.
    """
    if not draws:
        msg = "build_candidate_report requires at least one draw"
        raise ValueError(msg)

    results = [draw_result_from_items(items) for items in draws]
    eligible_flags, engaged_flags, collapsed_flags = draw_flags(results)
    drops = [r.drop for r in results]
    idx = median_draw_index(drops)
    median_items = draws[idx]
    median_result = results[idx]

    bootstrap = bootstrap_stratified_drop(
        scores_full=median_items.scores_full,
        scores_lao=median_items.scores_lao,
        labels=median_items.labels,
        objects=median_items.objects,
        seed=bootstrap_seed,
    )
    perm_p = permutation_p_stratified(
        median_items.scores_full,
        median_items.labels,
        median_items.objects,
        seed=permutation_seed,
    )

    report = CandidateExternalReport(
        key=key,
        family=family,
        eligible_flags=eligible_flags,
        engaged_flags=engaged_flags,
        collapsed_flags=collapsed_flags,
        auc_lao_ci_lower=bootstrap.auc_lao_ci[0],
        auc_lao_ci_upper=bootstrap.auc_lao_ci[1],
        potency_at_median_draw=median_result.potency,
        auc_full_at_median_draw=median_result.auc_full,
        auc_lao_at_median_draw=median_result.auc_lao,
        drop_at_median_draw=median_result.drop,
        audit_not_engaged=not aggregate_draws(engaged_flags),
    )
    return CandidateStatisticalSummary(
        report=report,
        aggregate=aggregate_candidate_draws(results),
        bootstrap=bootstrap,
        permutation_p=perm_p,
        median_draw_index=idx,
    )


# --- Cambridge adapter (Loop I-005) -----------------------------------------
#
# design-final.md §3 / §4 is the single source of truth for this section.
# Reuses (never modifies) two frozen sibling scripts via
# :func:`resolve_sibling_script`:
#
# * ``paper01_fetch_sources`` (I-001) -- ``load_cambridge_table`` (the
#   stdlib ``.xlsx`` reader) and ``cambridge_gold_label`` (§3.3 gold
#   binarisation).
# * ``es4_scorer_diag`` (frozen, S4 boundary) -- ``make_encoder`` /
#   ``embed_map`` / ``embed_rarity`` / ``jaccard_rarity`` / ``build_idf`` /
#   ``tfidf_rarity`` / ``_length_controlled`` / ``Candidate``.


@dataclasses.dataclass(frozen=True, slots=True)
class CambridgeRow:
    """One Cambridge-AUT-dataset row surviving gold binarisation (§3.3).

    ``category`` already uses the :class:`AdversarialItem`-compatible
    vocabulary (``"good"`` / ``"common_use_only"``) so
    :func:`to_adversarial_items` is a pure reshape, never a remap.
    """

    row_id: int
    object: str
    text: str
    category: str


def load_cambridge_rows(object_key: str, data: bytes) -> tuple[CambridgeRow, ...]:
    """Parse one Cambridge ``.xlsx`` file's bytes into gold-binarised rows.

    Reuses ``paper01_fetch_sources.load_cambridge_table`` (I-001) for the
    raw parse and ``paper01_fetch_sources.cambridge_gold_label`` (I-001,
    §3.3) for binarisation -- neither is reimplemented here. A row is
    dropped when binarisation excludes it (a 0 among rated values, a 2, a
    band-crossing mix, a missing ``Responses`` cell) or its ``id`` cell is
    not numeric.
    """
    header, body = _fetch.load_cambridge_table(data)
    id_idx = header.index("id")
    responses_idx = header.index("Responses")
    rater_idxs = [header.index(f"rater{n}") for n in (1, 2, 3) if f"rater{n}" in header]

    rows: list[CambridgeRow] = []
    for raw in body:
        label = _fetch.cambridge_gold_label(
            raw, responses_idx=responses_idx, rater_idxs=rater_idxs
        )
        if label is None:
            continue
        id_raw = raw[id_idx] if id_idx < len(raw) else ""
        try:
            row_id = int(float(id_raw))
        except ValueError:
            continue
        category = "good" if label == "good" else "common_use_only"
        rows.append(
            CambridgeRow(
                row_id=row_id,
                object=object_key,
                text=normalise(raw[responses_idx]),
                category=category,
            )
        )
    return tuple(rows)


def cambridge_id_diagnostics(rows: Sequence[CambridgeRow]) -> dict[str, Any]:
    """§3.4 (Opus LOW-6): ``id`` type / contiguity / row-order bookkeeping.

    Recorded per object as a ``source-audit.json``-style item in the
    result JSON, never used to change behaviour.
    """
    ids = [r.row_id for r in rows]
    if not ids:
        return {
            "n": 0,
            "min_id": None,
            "max_id": None,
            "distinct_ids": 0,
            "sorted_as_read_order": True,
            "contiguous_run": False,
        }
    distinct = len(set(ids))
    return {
        "n": len(ids),
        "min_id": min(ids),
        "max_id": max(ids),
        "distinct_ids": distinct,
        "sorted_as_read_order": ids == sorted(ids),
        "contiguous_run": (max(ids) - min(ids) + 1) == distinct,
    }


def split_cambridge_rows(
    rows: Sequence[CambridgeRow], scheme: str
) -> tuple[tuple[CambridgeRow, ...], tuple[CambridgeRow, ...]]:
    """§3.4: partition ``rows`` into ``(split0, split1)``.

    ``SPLIT-BLOCK`` (primary): ``id`` ascending, first half / second half.
    ``SPLIT-PARITY`` (sensitivity): ``id`` even / odd. Both are pre-
    registered and reported (design-final.md §3.4, Opus HIGH-7).
    """
    if scheme == "SPLIT-BLOCK":
        ordered = sorted(rows, key=lambda r: r.row_id)
        mid = len(ordered) // 2
        return tuple(ordered[:mid]), tuple(ordered[mid:])
    if scheme == "SPLIT-PARITY":
        split0 = tuple(r for r in rows if r.row_id % 2 == 0)
        split1 = tuple(r for r in rows if r.row_id % 2 == 1)
        return split0, split1
    msg = f"unknown split scheme {scheme!r}"
    raise ValueError(msg)


def frozen_scan_order(rows: Sequence[CambridgeRow]) -> tuple[CambridgeRow, ...]:
    """§4.1: the frozen greedy-dedupe scan order (``id`` ascending)."""
    return tuple(sorted(rows, key=lambda r: r.row_id))


def pool_by_category(
    rows: Sequence[CambridgeRow], category: str
) -> tuple[CambridgeRow, ...]:
    """The frozen-scan-order (``id`` ascending) subset of ``rows``.

    ``category`` is ``"good"`` or ``"common_use_only"``.
    """
    return frozen_scan_order([r for r in rows if r.category == category])


def to_adversarial_items(rows: Sequence[CambridgeRow]) -> tuple[AdversarialItem, ...]:
    """AdversarialItem-shaped view of ``rows``.

    ``.object`` is stamped with the same object-id string used as the
    anchor dict key throughout this module (design-final.md §7, Opus
    LOW-2 / AC 005-16): a mismatch here would silently zero every rarity
    (``ref_by_object.get(object_id)`` misses -> ``0.0`` -> AUC 0.5), so
    every caller that builds an anchor dict keys it with exactly the
    string this function stamps.
    """
    return tuple(
        AdversarialItem(
            text=r.text, object=r.object, label="appropriate", category=r.category
        )
        for r in rows
    )


# --- §4.1 pool construction: greedy dedupe / centroid / seeded draws -------


def greedy_dedupe_indices(embeddings: np.ndarray, *, cap: int) -> list[int]:
    """§4.1 frozen-scan-order greedy near-dup merge (cosine >= ``REF_DEDUP``).

    ``embeddings`` must already be unit-normalised and in the caller's
    frozen scan order (``id`` ascending); the result is a subsequence of
    that order, capped at ``cap`` entries (``ARM-B`` passes
    ``cap=len(pool)`` for the uncapped variant, ``ARM-A``/``ARM-D`` pass
    ``N_R_MAX``).
    """
    kept: list[int] = []
    for i in range(embeddings.shape[0]):
        if len(kept) >= cap:
            break
        if not kept:
            kept.append(i)
            continue
        cos = embeddings[i] @ embeddings[np.asarray(kept)].T
        if float(cos.max()) < _c.REF_DEDUP:
            kept.append(i)
    return kept


def centroid_nearest_indices(embeddings: np.ndarray, k: int) -> list[int]:
    """§4.1 ARM-D: the ``k`` items nearest the pool centroid (deterministic)."""
    if embeddings.shape[0] == 0 or k <= 0:
        return []
    centroid = embeddings.mean(axis=0)
    norm = float(np.linalg.norm(centroid))
    if norm > 0.0:
        centroid = centroid / norm
    sims = embeddings @ centroid
    order = np.argsort(-sims, kind="stable")
    return order[: min(k, embeddings.shape[0])].tolist()


def derive_seed(*parts: object) -> int:
    """A deterministic non-negative seed folding the master :data:`SEED`.

    Folds in arbitrary key parts (object / corpus / arm / draw role, ...).
    Two calls with the same ``SEED`` and the same ``parts`` always agree;
    changing either changes the derived seed (AC 005-9's "different global
    seed -> different draws").
    """
    h = hashlib.blake2b(digest_size=8)
    h.update(str(SEED).encode("utf-8"))
    for part in parts:
        h.update(b"\x00")
        h.update(str(part).encode("utf-8"))
    return int.from_bytes(h.digest(), "big") & ((1 << 63) - 1)


def anchor_draw_indices(
    pool_size: int, k: int, *, seed: int, draw_index: int
) -> np.ndarray:
    """One seeded without-replacement draw of ``k`` indices from ``range(pool_size)``.

    §4.1 ARM-A. Deterministic given ``(seed, draw_index)``.
    """
    rng = np.random.default_rng((seed, draw_index))
    return rng.choice(pool_size, size=k, replace=False)


def nc1_partner_object(objects: Sequence[str], object_key: str) -> str:
    """§4.2 NC-1: ``object -> object'`` via a deterministic cyclic shift.

    shift=1 of the frozen ``objects`` order.
    """
    ordered = list(objects)
    idx = ordered.index(object_key)
    return ordered[(idx + 1) % len(ordered)]


# --- §5.4 encoders / candidate ladder ---------------------------------------

_EMBEDDING_MODEL_IDS: Final[dict[str, str]] = {
    "mpnet": "sentence-transformers/all-mpnet-base-v2",
    "MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
    "e5-small-v2": "intfloat/e5-small-v2",
    "bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
}

_CANDIDATE_ENCODER_KEY: Final[dict[str, str]] = {
    "X0": "mpnet",
    "X1": "mpnet",
    "X2": "mpnet",
    "X3a": "MiniLM-L6-v2",
    "X3b": "e5-small-v2",
    "X3c": "bge-small-en-v1.5",
}

_CANDIDATE_AGG: Final[dict[str, str]] = {
    "X0": "max",
    "X1": "mean",
    "X2": "max",
    "X3a": "max",
    "X3b": "max",
    "X3c": "max",
}


def build_available_encoders() -> dict[str, Callable[[Sequence[str]], np.ndarray]]:
    """Build every offline-cached encoder in :data:`_EMBEDDING_MODEL_IDS`.

    Reuses ``es4_scorer_diag.make_encoder`` (frozen, unmodified); a model
    missing from the local HF cache is silently absent from the result
    (graceful skip, matching the internal apparatus's own behaviour).
    """
    out: dict[str, Callable[[Sequence[str]], np.ndarray]] = {}
    for key, model_id in _EMBEDDING_MODEL_IDS.items():
        encoder = _diag.make_encoder(model_id)
        if encoder is not None:
            out[key] = encoder
    return out


def embed_all_texts(
    rows_by_object: Mapping[str, Sequence[CambridgeRow]],
    encoders: Mapping[str, Callable[[Sequence[str]], np.ndarray]],
) -> dict[str, dict[str, np.ndarray]]:
    """``encoder_key -> {normalised text: unit vector}``, merged across every object.

    A text is embedded exactly once regardless of which object references
    it -- required for NC-1's cross-object anchor swap (design-final.md
    §4.2): the anchor dict for object ``o`` holds object ``o'``'s texts,
    and those texts must resolve in the same vmap used to embed ``o``'s
    own scored items.
    """
    all_texts = sorted({r.text for rows in rows_by_object.values() for r in rows})
    return {
        enc_key: _diag.embed_map(encoder, all_texts)
        for enc_key, encoder in encoders.items()
    }


def build_object_idf(rows: Sequence[CambridgeRow]) -> tuple[dict[str, float], float]:
    """X6's per-object IDF background corpus.

    Built once from the object's full split0 pool and reused for every
    draw/arm -- X6 (``tfidf_rarity``) has no reference-conditioned
    similarity concept at all (its frozen signature does not even accept a
    reference set), so it is anchor/draw-independent by construction.
    """
    corpus = [r.text for r in rows]
    idf = _diag.build_idf(corpus)
    default_idf = math.log((len(corpus) + 1) / 1.0) + 1.0 if corpus else 1.0
    return idf, default_idf


def make_embed_candidate(
    key: str,
    description: str,
    vmap: Mapping[str, np.ndarray],
    anchor_texts_by_object: Mapping[str, Sequence[str]],
    *,
    agg: str,
) -> Any:
    """One embedding-rarity :class:`es4_scorer_diag.Candidate`, object-keyed.

    Mirrors ``es4_scorer_diag._make_embed_candidate``'s
    ``ref_emb.get(object_id)`` lookup pattern (design-final.md §7, Opus
    LOW-2): a scored item whose ``object_id`` is not a key of
    ``anchor_texts_by_object`` silently gets rarity ``0.0`` rather than
    raising -- AC 005-16 pins the two key sets identical.
    """
    ref_by_object: dict[str, np.ndarray] = {}
    for obj, texts in anchor_texts_by_object.items():
        rows_emb = [vmap[t] for t in texts if t in vmap]
        ref_by_object[obj] = (
            np.asarray(rows_emb, dtype=float) if rows_emb else np.zeros((0, 0))
        )

    def rarity(object_id: str, text: str, *, leave_anchor_out: bool) -> float:
        ref = ref_by_object.get(object_id)
        vec = vmap.get(text)
        if ref is None or ref.size == 0 or vec is None:
            return 0.0
        return _diag.embed_rarity(vec, ref, leave_anchor_out=leave_anchor_out, agg=agg)

    return _diag.Candidate(key, description, rarity)


def make_jaccard_candidate(
    key: str, description: str, anchor_texts_by_object: Mapping[str, Sequence[str]]
) -> Any:
    """X5: object-keyed lexical Jaccard-novelty candidate."""

    def rarity(object_id: str, text: str, *, leave_anchor_out: bool) -> float:
        ref_texts = anchor_texts_by_object.get(object_id, ())
        return _diag.jaccard_rarity(text, ref_texts, drop_dup=leave_anchor_out)

    return _diag.Candidate(key, description, rarity)


def make_tfidf_candidate(
    key: str,
    description: str,
    idf_by_object: Mapping[str, tuple[Mapping[str, float], float]],
) -> Any:
    """X6: object-keyed TF-IDF self-rarity candidate.

    Anchor-independent; ``leave_anchor_out`` has no effect, matching the
    frozen internal C6.
    """

    def rarity(object_id: str, text: str, *, leave_anchor_out: bool) -> float:  # noqa: ARG001
        entry = idf_by_object.get(object_id)
        if entry is None:
            return 0.0
        idf, default_idf = entry
        return _diag.tfidf_rarity(text, idf, default_idf)

    return _diag.Candidate(key, description, rarity)


def embed_max_similarity_by_object(
    vmap: Mapping[str, np.ndarray],
    anchor_texts_by_object: Mapping[str, Sequence[str]],
    rows: Sequence[CambridgeRow],
) -> np.ndarray:
    """§5.4 ``m``: each row's max cosine similarity to its own object's anchor set.

    Object-keyed, same alignment contract as :func:`make_embed_candidate`.
    """
    ref_by_object: dict[str, np.ndarray] = {}
    for obj, texts in anchor_texts_by_object.items():
        rows_emb = [vmap[t] for t in texts if t in vmap]
        ref_by_object[obj] = (
            np.asarray(rows_emb, dtype=float) if rows_emb else np.zeros((0, 0))
        )
    out = np.zeros(len(rows), dtype=float)
    for i, r in enumerate(rows):
        ref = ref_by_object.get(r.object)
        vec = vmap.get(r.text)
        if ref is None or ref.size == 0 or vec is None:
            continue
        out[i] = 1.0 - _diag.embed_rarity(vec, ref, leave_anchor_out=False, agg="max")
    return out


def jaccard_max_similarity_by_object(
    anchor_texts_by_object: Mapping[str, Sequence[str]], rows: Sequence[CambridgeRow]
) -> np.ndarray:
    """§5.4 ``m`` for X5.

    Each row's max token-Jaccard similarity to its own object's anchor set.
    """
    out = np.zeros(len(rows), dtype=float)
    for i, r in enumerate(rows):
        ref_texts = anchor_texts_by_object.get(r.object, ())
        out[i] = 1.0 - _diag.jaccard_rarity(r.text, ref_texts, drop_dup=False)
    return out


def score_rows_for_draw(
    rows: Sequence[CambridgeRow],
    *,
    anchor_texts_by_object: Mapping[str, Sequence[str]],
    vmaps: Mapping[str, Mapping[str, np.ndarray]],
    idf_by_object: Mapping[str, tuple[Mapping[str, float], float]],
) -> dict[str, DrawItems]:
    """Score every row for every candidate, for one arm/draw's anchor sets.

    ``rows`` (any mix of objects) may span multiple objects at once
    (design-final.md §1's primary estimand pools every object into one
    within-object-weighted AUC); alignment between a row and its anchor
    set is entirely via ``row.object`` used as the key into
    ``anchor_texts_by_object`` (AC 005-16). Returns one :class:`DrawItems`
    per candidate whose encoder is available; a candidate whose encoder
    could not be loaded offline is simply absent from the result.
    """
    labels = tuple(1 if r.category == "good" else 0 for r in rows)
    objects = tuple(r.object for r in rows)
    gold_items = to_adversarial_items(rows)

    out: dict[str, DrawItems] = {}
    for cand in CANDIDATE_LADDER:
        key = cand.key
        if key in _CANDIDATE_ENCODER_KEY:
            enc_key = _CANDIDATE_ENCODER_KEY[key]
            vmap = vmaps.get(enc_key)
            if vmap is None:
                continue
            if key == "X2":
                base = make_embed_candidate(
                    "X0", "base for X2", vmap, anchor_texts_by_object, agg="max"
                )
                built = _diag._length_controlled(base, gold_items)  # noqa: SLF001
            else:
                built = make_embed_candidate(
                    key, key, vmap, anchor_texts_by_object, agg=_CANDIDATE_AGG[key]
                )
            max_sim = embed_max_similarity_by_object(vmap, anchor_texts_by_object, rows)
        elif key == "X5":
            built = make_jaccard_candidate(key, "lexical", anchor_texts_by_object)
            max_sim = jaccard_max_similarity_by_object(anchor_texts_by_object, rows)
        else:  # X6
            built = make_tfidf_candidate(key, "lexical", idf_by_object)
            max_sim = np.zeros(len(rows), dtype=float)

        scores_full = tuple(
            built.rarity(r.object, r.text, leave_anchor_out=False) for r in rows
        )
        scores_lao = tuple(
            built.rarity(r.object, r.text, leave_anchor_out=True) for r in rows
        )
        potency = potency_and_near_dup(max_sim.tolist(), list(labels)).potency

        out[key] = DrawItems(
            scores_full=scores_full,
            scores_lao=scores_lao,
            labels=labels,
            objects=objects,
            potency=potency,
        )
    return out


# --- per-object-per-split context (pool + dedupe + idf) ---------------------


@dataclasses.dataclass(frozen=True, slots=True)
class ObjectSplitContext:
    """One object's §3.4/§4.1 pool-construction state for one split scheme."""

    object_key: str
    split0: tuple[CambridgeRow, ...]
    split1: tuple[CambridgeRow, ...]
    common_pool: tuple[CambridgeRow, ...]
    good_pool: tuple[CambridgeRow, ...]
    dedup_common_pool: tuple[CambridgeRow, ...]
    dedup_good_pool: tuple[CambridgeRow, ...]
    dropped: bool
    idf: dict[str, float]
    default_idf: float


def build_object_split_context(
    object_key: str,
    rows: Sequence[CambridgeRow],
    scheme: str,
    mpnet_vmap: Mapping[str, np.ndarray],
) -> ObjectSplitContext:
    """Assemble one object's split0/split1 partition and dedup'd pools.

    Includes the drop decision (AC 005-11: ``|R_o| < N_R_MIN``) and X6 IDF.
    """
    split0, split1 = split_cambridge_rows(rows, scheme)
    common_pool = pool_by_category(split0, "common_use_only")
    good_pool = pool_by_category(split0, "good")

    def _dedup(pool: Sequence[CambridgeRow]) -> tuple[CambridgeRow, ...]:
        if not pool:
            return ()
        emb = np.asarray([mpnet_vmap[r.text] for r in pool], dtype=float)
        idx = greedy_dedupe_indices(emb, cap=len(pool))
        return tuple(pool[i] for i in idx)

    dedup_common = _dedup(common_pool)
    dedup_good = _dedup(good_pool)
    idf, default_idf = build_object_idf(split0)
    return ObjectSplitContext(
        object_key=object_key,
        split0=split0,
        split1=split1,
        common_pool=common_pool,
        good_pool=good_pool,
        dedup_common_pool=dedup_common,
        dedup_good_pool=dedup_good,
        dropped=len(dedup_common) < _c.N_R_MIN,
        idf=idf,
        default_idf=default_idf,
    )


def arm_a_draw_texts(
    ctx: ObjectSplitContext, draw_index: int, *, corpus: str, scheme: str
) -> tuple[str, ...]:
    """§4.1 ARM-A: one seeded draw of ``k = min(N_R_MAX, |pool|)`` texts."""
    pool = ctx.dedup_common_pool
    k = draw_size(len(pool))
    if k == 0:
        return ()
    seed = derive_seed(corpus, ctx.object_key, scheme, "ARM-A")
    idx = anchor_draw_indices(len(pool), k, seed=seed, draw_index=draw_index)
    return tuple(pool[i].text for i in idx)


def arm_b_texts(ctx: ObjectSplitContext) -> tuple[str, ...]:
    """§4.1 ARM-B: the whole dedup'd pool, uncapped."""
    return tuple(r.text for r in ctx.dedup_common_pool)


def arm_d_texts(
    ctx: ObjectSplitContext, mpnet_vmap: Mapping[str, np.ndarray]
) -> tuple[str, ...]:
    """§4.1 ARM-D: the ``k`` items nearest the pool centroid (deterministic)."""
    pool = ctx.dedup_common_pool
    k = draw_size(len(pool))
    if k == 0:
        return ()
    emb = np.asarray([mpnet_vmap[r.text] for r in pool], dtype=float)
    idx = centroid_nearest_indices(emb, k)
    return tuple(pool[i].text for i in idx)


def nc1_texts(
    partner_ctx: ObjectSplitContext, *, corpus: str, scheme: str
) -> tuple[str, ...]:
    """§4.2 NC-1: one seeded draw from the *partner* object's dedup'd common pool.

    A single representative draw, not the full ANCHOR_DRAWS sweep --
    NC-1/NC-2 are report-only diagnostics, design-final.md §4.2.
    """
    pool = partner_ctx.dedup_common_pool
    k = draw_size(len(pool))
    if k == 0:
        return ()
    seed = derive_seed(corpus, partner_ctx.object_key, scheme, "NC-1")
    idx = anchor_draw_indices(len(pool), k, seed=seed, draw_index=0)
    return tuple(pool[i].text for i in idx)


def nc2_texts(ctx: ObjectSplitContext, *, corpus: str, scheme: str) -> tuple[str, ...]:
    """§4.2 NC-2: one seeded draw from this object's own dedup'd *good* pool."""
    pool = ctx.dedup_good_pool
    k = draw_size(len(pool))
    if k == 0:
        return ()
    seed = derive_seed(corpus, ctx.object_key, scheme, "NC-2")
    idx = anchor_draw_indices(len(pool), k, seed=seed, draw_index=0)
    return tuple(pool[i].text for i in idx)


def cambridge_class_sizes(contexts: Sequence[ObjectSplitContext]) -> dict[str, int]:
    """§6 ``class_sizes``: pooled split1 gold-class counts across ``contexts``."""
    good = sum(1 for ctx in contexts for r in ctx.split1 if r.category == "good")
    common = sum(
        1 for ctx in contexts for r in ctx.split1 if r.category == "common_use_only"
    )
    return {"good": good, "common": common}


def _quantize_json(value: Any) -> Any:
    """Round every float leaf to 6 decimals before JSON serialisation.

    ``feedback_golden_crossplatform_float_drift``: cross-platform libm
    1-ULP drift must not leak into the committed artifact.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {k: _quantize_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_quantize_json(v) for v in value]
    return value


# --- Cambridge orchestration (one split scheme, then both) -----------------


def run_cambridge_split(
    rows_by_object: Mapping[str, Sequence[CambridgeRow]],
    scheme: str,
    vmaps: Mapping[str, Mapping[str, np.ndarray]],
    *,
    corpus: str = "cambridge",
    objects: Sequence[str] = CAMBRIDGE_OBJECTS,
) -> dict[str, Any]:
    """One SPLIT-BLOCK or SPLIT-PARITY pass over one corpus's object battery.

    ARM-A (200 draws, feeds the §6 verdict for the embedding family) plus
    ARM-B / ARM-D / NC-1 / NC-2 (single-draw, report-only -- design-final.md
    §DA-G1-23: bootstrap is reserved for ARM-A x EMBEDDING_FAMILY_EXT x
    split only).

    ``objects`` defaults to :data:`CAMBRIDGE_OBJECTS` (bowl + paperclip) so
    every pre-I-006 call site is byte-identical; Loop I-006 passes
    :data:`OCSAI_PRIMARY_OBJECTS` / :data:`OCSAI_SENSITIVITY_OBJECTS`
    instead to reuse this whole orchestration for the Ocsai corpus
    (design-final.md "Cambridge adapter ... をできる限り一般化して再利用する") --
    this is the only edit Loop I-006 makes inside the Cambridge section
    itself; everything else it needs is additive, below.
    """
    mpnet_vmap = vmaps.get("mpnet", {})
    contexts = {
        obj: build_object_split_context(obj, rows_by_object[obj], scheme, mpnet_vmap)
        for obj in objects
    }
    dropped_objects = [o for o in objects if contexts[o].dropped]
    active_objects = [o for o in objects if o not in dropped_objects]
    all_scored_rows = tuple(r for o in active_objects for r in contexts[o].split1)
    class_sizes = cambridge_class_sizes([contexts[o] for o in active_objects])
    idf_by_object = {
        o: (contexts[o].idf, contexts[o].default_idf) for o in active_objects
    }

    # --- ARM-A: ANCHOR_DRAWS seeded draws, every candidate ------------------
    draws_per_candidate: dict[str, list[DrawItems]] = {
        c.key: [] for c in CANDIDATE_LADDER
    }
    for b in range(ANCHOR_DRAWS):
        anchor_texts_by_object = {
            o: arm_a_draw_texts(contexts[o], b, corpus=corpus, scheme=scheme)
            for o in active_objects
        }
        scored = score_rows_for_draw(
            all_scored_rows,
            anchor_texts_by_object=anchor_texts_by_object,
            vmaps=vmaps,
            idf_by_object=idf_by_object,
        )
        for key, items in scored.items():
            draws_per_candidate[key].append(items)

    candidates_out: dict[str, Any] = {}
    reports_for_verdict: list[CandidateExternalReport] = []
    for cand in CANDIDATE_LADDER:
        draws = draws_per_candidate.get(cand.key, [])
        if not draws:
            candidates_out[cand.key] = {"available": False}
            continue
        # mutation target (I-005 new): restricting the *bootstrapped, verdict-
        # eligible* path to EMBEDDING_FAMILY_EXT (DA-G1-23) -- X5/X6 (and any
        # candidate outside this set) only ever get the cheap aggregate below.
        if cand.key in EMBEDDING_FAMILY_EXT:
            summary = build_candidate_report(
                cand.key,
                cand.family,
                draws,
                bootstrap_seed=derive_seed(corpus, scheme, cand.key, "bootstrap"),
                permutation_seed=derive_seed(corpus, scheme, cand.key, "permutation"),
            )
            reports_for_verdict.append(summary.report)
            candidates_out[cand.key] = {
                "available": True,
                "bootstrapped": True,
                "report": dataclasses.asdict(summary.report),
                "aggregate": dataclasses.asdict(summary.aggregate),
                "bootstrap": dataclasses.asdict(summary.bootstrap),
                "permutation_p": summary.permutation_p,
                "median_draw_index": summary.median_draw_index,
            }
        else:
            results = [draw_result_from_items(d) for d in draws]
            agg = aggregate_candidate_draws(results)
            candidates_out[cand.key] = {
                "available": True,
                "bootstrapped": False,
                "aggregate": dataclasses.asdict(agg),
            }

    verdict = decide_external(reports_for_verdict, class_sizes=class_sizes)

    # --- ARM-B / ARM-D / NC-1 / NC-2: single-draw, report-only -------------
    def _single_arm(
        anchor_texts_by_object: Mapping[str, Sequence[str]],
    ) -> dict[str, Any]:
        rows = tuple(r for o in anchor_texts_by_object for r in contexts[o].split1)
        scored = score_rows_for_draw(
            rows,
            anchor_texts_by_object=anchor_texts_by_object,
            vmaps=vmaps,
            idf_by_object=idf_by_object,
        )
        return {
            key: dataclasses.asdict(
                aggregate_candidate_draws([draw_result_from_items(items)])
            )
            for key, items in scored.items()
        }

    arm_b_anchor = {o: arm_b_texts(contexts[o]) for o in active_objects}
    arm_d_anchor = {o: arm_d_texts(contexts[o], mpnet_vmap) for o in active_objects}
    nc1_anchor: dict[str, tuple[str, ...]] = {}
    for o in active_objects:
        partner = nc1_partner_object(objects, o)
        if partner in active_objects:
            nc1_anchor[o] = nc1_texts(contexts[partner], corpus=corpus, scheme=scheme)
    nc2_anchor = {
        o: nc2_texts(contexts[o], corpus=corpus, scheme=scheme) for o in active_objects
    }

    sensitivity = {
        "ARM-B": _single_arm(arm_b_anchor),
        "ARM-D": _single_arm(arm_d_anchor),
    }
    negative_controls = {
        "NC-1": _single_arm(nc1_anchor) if nc1_anchor else {},
        "NC-2": _single_arm(nc2_anchor),
    }

    return {
        "scheme": scheme,
        "dropped_objects": dropped_objects,
        "active_objects": active_objects,
        "class_sizes": class_sizes,
        "pool_sizes": {
            o: {
                "common_raw": len(contexts[o].common_pool),
                "common_dedup": len(contexts[o].dedup_common_pool),
                "good_raw": len(contexts[o].good_pool),
                "good_dedup": len(contexts[o].dedup_good_pool),
                "draw_k": draw_size(len(contexts[o].dedup_common_pool)),
                "draws_effective": draws_effective(len(contexts[o].dedup_common_pool)),
            }
            for o in objects
        },
        "candidates": candidates_out,
        "verdict": dataclasses.asdict(verdict),
        "sensitivity": sensitivity,
        "negative_controls": negative_controls,
    }


def load_cambridge_raw_bytes(raw_dir: Path = CAMBRIDGE_RAW_DIR) -> dict[str, bytes]:
    """Read the two already-fetched (I-001) Cambridge ``.xlsx`` files."""
    return {
        obj: (raw_dir / filename).read_bytes()
        for obj, filename in CAMBRIDGE_FILENAMES.items()
    }


def run_cambridge_audit(
    raw_bytes_by_object: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    """End-to-end Cambridge audit: xlsx -> gold binarisation -> both verdicts.

    Every float leaf is 6-decimal quantized before return (no wall-clock
    is ever written).
    """
    raw = (
        raw_bytes_by_object
        if raw_bytes_by_object is not None
        else load_cambridge_raw_bytes()
    )
    rows_by_object = {obj: load_cambridge_rows(obj, data) for obj, data in raw.items()}

    encoders = build_available_encoders()
    if not encoders:
        msg = "no embedding encoder available offline; cannot score the external audit"
        raise RuntimeError(msg)
    vmaps = embed_all_texts(rows_by_object, encoders)

    splits = {
        scheme.key: run_cambridge_split(rows_by_object, scheme.key, vmaps)
        for scheme in SPLIT_SCHEMES
    }

    result: dict[str, Any] = {
        "corpus": "cambridge",
        "source_audit": {
            obj: cambridge_id_diagnostics(rows) for obj, rows in rows_by_object.items()
        },
        "encoders_available": sorted(encoders),
        "primary_split": "SPLIT-BLOCK",
        "splits": splits,
    }
    return _quantize_json(result)


def write_cambridge_audit(path: Path = EXTERNAL_AUDIT_PATH) -> dict[str, Any]:
    """Run :func:`run_cambridge_audit` and write it to ``path`` deterministically."""
    result = run_cambridge_audit()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return result


# --- Ocsai adapter (Loop I-006) ---------------------------------------------
#
# design-final.md §3 / §4 is the single source of truth for this section.
# Reuses the Cambridge adapter's row/pool/arm machinery wherever the two
# corpora share structure ("Cambridge adapter ... をできる限り一般化して
# 再利用する"):
#
# * Ocsai rows are stamped into the *same* :class:`CambridgeRow` dataclass
#   (``row_id`` here holds the 0-origin concatenated-scan-order index,
#   design-final.md §3.1/§3.4/DA-G1-14, not a spreadsheet ``id`` cell).
#   That is what lets :func:`split_cambridge_rows`, :func:`frozen_scan_order`,
#   :func:`pool_by_category`, :func:`build_object_split_context`,
#   :func:`arm_a_draw_texts`, :func:`arm_b_texts`, :func:`arm_d_texts`,
#   :func:`nc1_texts`, :func:`nc2_texts`, :func:`nc1_partner_object`,
#   :func:`score_rows_for_draw`, :func:`cambridge_class_sizes`, and (via the
#   ``objects`` parameter added to :func:`run_cambridge_split` above -- the
#   *only* edit this issue makes inside the Cambridge section itself) the
#   entire ARM-A/B/D/NC-1/NC-2/§6-verdict orchestration run over Ocsai data
#   completely unmodified.
# * Genuinely Ocsai-only, and therefore new below: the jsonl parse/concat
#   (§3.1/§3.2), the per-object gold-class-insufficiency reporting gate
#   (§3.5), ARM-C (§4.1, the (A1 union A2) recipe analog, AC 006-4), and
#   the paperclip-only source-crossed ARM-X (§4.2, Codex HIGH-1, AC 006-8).

_OCSAI_GOOD_CATEGORY: Final[str] = "good"
_OCSAI_COMMON_CATEGORY: Final[str] = "common_use_only"


def parse_ocsai_records(
    splits_data: Mapping[str, bytes],
) -> tuple[tuple[int, str, str, int], ...]:
    r"""Parse every Ocsai record across the fixed OCSAI_CONCAT_ORDER.

    Concatenation order is ``train`` -> ``val`` -> ``test``
    (design-final.md §3.1, DA-G1-14). Returns ``(row_index, object,
    response, score)`` tuples. ``row_index``
    is a 0-origin index assigned only to records whose JSON line and AUT
    prompt template parse successfully (reusing
    ``paper01_fetch_sources.parse_ocsai_prompt`` unmodified), counted over
    the *entire* concatenated stream in :data:`OCSAI_CONCAT_ORDER` order --
    the canonical scan order design-final.md §3.1/§3.4 use for
    SPLIT-BLOCK/SPLIT-PARITY and greedy dedupe. A line that fails to parse
    (bad JSON or template mismatch) does not consume an index; in the real,
    pinned data ``EXPECTED_OCSAI_PARSE_FAILURES == 0``
    (``paper01_fetch_sources.py``), so this convention is never actually
    exercised in production -- it only matters for making synthetic-jsonl
    unit tests unambiguous.

    ``OCSAI_CONCAT_ORDER`` is read from the module global on every call
    (never cached), so a ``monkeypatch.setattr(mod, "OCSAI_CONCAT_ORDER",
    ...)`` moves this function's output on the very next call.
    """
    out: list[tuple[int, str, str, int]] = []
    idx = 0
    # mutation target (1): OCSAI_CONCAT_ORDER の並び順 -- the sole gate that
    # fixes train -> val -> test as the canonical scan order.
    for split_name in OCSAI_CONCAT_ORDER:
        raw = splits_data[split_name]
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            parsed = _fetch.parse_ocsai_prompt(
                obj.get("prompt", ""), obj.get("completion", "")
            )
            if parsed is None:
                continue
            object_name, response, score = parsed
            out.append((idx, object_name, response, score))
            idx += 1
    return tuple(out)


def load_ocsai_rows(splits_data: Mapping[str, bytes]) -> tuple[CambridgeRow, ...]:
    """Parse + gold-binarise every Ocsai record into :class:`CambridgeRow`.

    Reuses ``parse_ocsai_prompt`` (via :func:`parse_ocsai_records`) and
    ``paper01_fetch_sources.ocsai_gold_label`` (I-001, unmodified, §3.3:
    encoded ``== 10`` -> common, ``>= 40`` -> good, ``11-39`` excluded). A
    row stamped here reuses the Cambridge dataclass verbatim: ``row_id`` =
    the concatenated scan-order index (:func:`parse_ocsai_records`),
    ``object``/``text`` normalised the same way :func:`load_cambridge_rows`
    normalises the response cell.
    """
    rows: list[CambridgeRow] = []
    for idx, object_name, response, score in parse_ocsai_records(splits_data):
        label = _fetch.ocsai_gold_label(score)
        if label is None:
            continue
        category = _OCSAI_GOOD_CATEGORY if label == "good" else _OCSAI_COMMON_CATEGORY
        rows.append(
            CambridgeRow(
                row_id=idx,
                object=normalise(object_name),
                text=normalise(response),
                category=category,
            )
        )
    return tuple(rows)


# --- §3.5 per-object drop gate, second half ("gold クラス不足") -------------
#
# build_object_split_context.dropped already covers the "|R_o| < N_R_MIN"
# half of design-final.md §3.5's drop condition. This covers the other half.


def object_has_both_gold_classes(ctx: ObjectSplitContext) -> bool:
    """The object's ``split1`` scored pool has >= 1 item in *both* gold classes.

    An object failing this check contributes weight 0 to every draw's
    ``auc_stratified`` call regardless (:func:`auc_stratified` already
    skips any object missing a class), so this gate never changes a
    verdict number -- it only turns a silent zero-weight into an explicit,
    counted, reported exclusion (AC 006-7).
    """
    n_good = sum(1 for r in ctx.split1 if r.category == _OCSAI_GOOD_CATEGORY)
    n_common = sum(1 for r in ctx.split1 if r.category == _OCSAI_COMMON_CATEGORY)
    # mutation target (6): the gold-class half of the object-exclusion gate.
    return n_good >= 1 and n_common >= 1


# --- §4.1 ARM-C (Ocsai only): the (A1 union A2) recipe analog ---------------


def ocsai_high_frequency_texts(
    split0_rows: Sequence[CambridgeRow], *, min_support: int = EXT_A2_MIN_SUPPORT
) -> tuple[str, ...]:
    """§4.1 ARM-C's A2: normalised texts occurring >= ``min_support`` times.

    Counted across the object's *entire* ``split0`` pool (every category,
    not just common) -- the external analog of the internal recipe's
    second, generation-frequency anchor stage (issue 006 background: Ocsai
    has a frequency structure Cambridge lacks). Frozen scan order (first-
    occurrence order within ``split0``), duplicates collapsed. Returns
    ``()`` when no text in ``split0`` clears ``min_support`` -- AC 006-4's
    "A2 missing support" case.
    """
    texts_in_order = [r.text for r in split0_rows]
    counts = Counter(texts_in_order)
    seen: set[str] = set()
    out: list[str] = []
    for text in texts_in_order:
        # mutation target (3): EXT_A2_MIN_SUPPORT boundary (>= 2, not > 2 / >= 1).
        if counts[text] >= min_support and text not in seen:
            seen.add(text)
            out.append(text)
    return tuple(out)


def arm_c_texts(
    ctx: ObjectSplitContext,
    mpnet_vmap: Mapping[str, np.ndarray],
    *,
    min_support: int = EXT_A2_MIN_SUPPORT,
) -> tuple[tuple[str, ...], bool]:
    """§4.1 ARM-C: ``(A1 union A2)`` dedup'd to ``k = min(N_R_MAX, |pool|)``.

    A1 = the object's ``split0`` common-pool texts (:attr:`ObjectSplitContext.
    dedup_common_pool`, the same source :func:`arm_a_draw_texts`/
    :func:`arm_b_texts` draw from). A2 = :func:`ocsai_high_frequency_texts`
    over the object's *whole* ``split0`` (can introduce texts A1 never
    contains, since A1 is common-only and A2 is not). Returns ``(texts,
    a2_missing_support)``; ``a2_missing_support`` is ``True`` (AC 006-4)
    when A2 is empty for this object -- recorded as a diagnostic, never
    silently folded into "ARM-C == ARM-A".
    """
    a1_texts = [r.text for r in ctx.dedup_common_pool]
    a2_texts = list(ocsai_high_frequency_texts(ctx.split0, min_support=min_support))
    seen: set[str] = set()
    union_ordered: list[str] = []
    for text in [*a1_texts, *a2_texts]:
        if text not in seen:
            seen.add(text)
            union_ordered.append(text)
    a2_missing_support = len(a2_texts) == 0
    if not union_ordered:
        return (), a2_missing_support
    embeddings = np.asarray([mpnet_vmap[t] for t in union_ordered], dtype=float)
    k = draw_size(len(union_ordered))
    idx = greedy_dedupe_indices(embeddings, cap=k)
    return tuple(union_ordered[i] for i in idx), a2_missing_support


# --- §4.2 ARM-X (paperclip only, source-crossed) ----------------------------


def arm_x_scored_candidates(
    cambridge_paperclip_rows: Sequence[CambridgeRow],
    ocsai_paperclip_ctx: ObjectSplitContext,
    scheme: str,
    vmaps: Mapping[str, Mapping[str, np.ndarray]],
) -> dict[str, Any]:
    """§4.2 ARM-X: anchor = Cambridge paperclip, gold/scored = Ocsai paperclip.

    The only arm where anchor provenance is genuinely independent of the
    scored gold (Codex HIGH-1). Report-only: never bootstrapped, never
    enters :func:`decide_external`'s ``reports`` (AC 006-9).

    ``vmaps`` must already embed *both* corpora's paperclip texts under the
    same encoders (the caller merges both rows sets through
    :func:`embed_all_texts` before calling here) -- embedding is a pure
    per-text function, so batching both corpora's texts together before
    encoding produces vectors identical to encoding each separately.
    """
    # mutation target (4): anchor source -- this must stay Cambridge, never
    # ocsai_paperclip_ctx. build_object_split_context on the *Cambridge*
    # rows, then arm_b_texts (the whole dedup'd pool, uncapped) is the
    # anchor; scoring happens against ocsai_paperclip_ctx.split1 (Ocsai's
    # own gold), never Cambridge's.
    cambridge_ctx = build_object_split_context(
        "paperclip", cambridge_paperclip_rows, scheme, vmaps.get("mpnet", {})
    )
    anchor_texts_by_object = {"paperclip": arm_b_texts(cambridge_ctx)}
    idf_by_object = {
        "paperclip": (ocsai_paperclip_ctx.idf, ocsai_paperclip_ctx.default_idf)
    }
    scored = score_rows_for_draw(
        ocsai_paperclip_ctx.split1,
        anchor_texts_by_object=anchor_texts_by_object,
        vmaps=vmaps,
        idf_by_object=idf_by_object,
    )
    return {
        key: dataclasses.asdict(
            aggregate_candidate_draws([draw_result_from_items(items)])
        )
        for key, items in scored.items()
    }


# --- Ocsai per-split orchestration ------------------------------------------


def run_ocsai_split(
    rows_by_object: Mapping[str, Sequence[CambridgeRow]],
    scheme: str,
    vmaps: Mapping[str, Mapping[str, np.ndarray]],
    *,
    corpus: str = "ocsai",
    objects: Sequence[str] = OCSAI_PRIMARY_OBJECTS,
    cambridge_paperclip_rows: Sequence[CambridgeRow] = (),
    arm_x_vmaps: Mapping[str, Mapping[str, np.ndarray]] | None = None,
) -> dict[str, Any]:
    """One SPLIT-BLOCK or SPLIT-PARITY pass over Ocsai.

    Delegates ARM-A (verdict) / ARM-B / ARM-D / NC-1 / NC-2 / the §6
    decision to :func:`run_cambridge_split` wholesale (via its ``objects``
    parameter). Adds ARM-C (:func:`arm_c_texts`) and, ``paperclip``-only,
    ARM-X (:func:`arm_x_scored_candidates`); also re-surfaces
    ``active_objects``/``dropped_objects`` after applying
    :func:`object_has_both_gold_classes` on top of ``run_cambridge_split``'s
    own pool-size gate (AC 006-7) -- this never changes the verdict
    ``run_cambridge_split`` returns (zero-weight objects already do not
    move ``auc_stratified``), it only makes the exclusion explicit and
    counted.
    """
    base = run_cambridge_split(
        rows_by_object, scheme, vmaps, corpus=corpus, objects=objects
    )

    mpnet_vmap = vmaps.get("mpnet", {})
    active = base["active_objects"]
    contexts = {
        obj: build_object_split_context(obj, rows_by_object[obj], scheme, mpnet_vmap)
        for obj in active
    }
    idf_by_object = {o: (contexts[o].idf, contexts[o].default_idf) for o in active}

    gold_deficient = sorted(
        o for o in active if not object_has_both_gold_classes(contexts[o])
    )
    final_active = [o for o in active if o not in gold_deficient]
    all_dropped = sorted({*base["dropped_objects"], *gold_deficient})

    # --- ARM-C ---------------------------------------------------------
    arm_c_pools = {o: arm_c_texts(contexts[o], mpnet_vmap) for o in final_active}
    a2_missing_support = sorted(
        o for o, (_texts, missing) in arm_c_pools.items() if missing
    )
    arm_c_anchor = {o: texts for o, (texts, _missing) in arm_c_pools.items()}
    arm_c_rows = tuple(r for o in arm_c_anchor for r in contexts[o].split1)
    arm_c_scored = score_rows_for_draw(
        arm_c_rows,
        anchor_texts_by_object=arm_c_anchor,
        vmaps=vmaps,
        idf_by_object=idf_by_object,
    )
    arm_c_report = {
        key: dataclasses.asdict(
            aggregate_candidate_draws([draw_result_from_items(items)])
        )
        for key, items in arm_c_scored.items()
    }

    result: dict[str, Any] = dict(base)
    result["active_objects"] = final_active
    result["dropped_objects"] = all_dropped
    result["dropped_object_count"] = len(all_dropped)
    result["gold_class_deficient_objects"] = gold_deficient
    # mutation target (5): reports_for_verdict / decide_external (inside
    # `base`, computed by run_cambridge_split) must never see arm_c_report --
    # ARM-C is attached to the *result* dict only, after the verdict above
    # is already frozen inside `base["verdict"]`.
    result["arm_c"] = {
        "candidates": arm_c_report,
        "a2_missing_support_objects": a2_missing_support,
    }

    # --- ARM-X (paperclip only, source-crossed) -------------------------
    if (
        "paperclip" in final_active
        and cambridge_paperclip_rows
        and arm_x_vmaps is not None
    ):
        result["arm_x"] = arm_x_scored_candidates(
            cambridge_paperclip_rows, contexts["paperclip"], scheme, arm_x_vmaps
        )
    else:
        result["arm_x"] = {}

    return result


# --- Ocsai end-to-end orchestration ------------------------------------------


def load_ocsai_raw_bytes() -> dict[str, bytes] | None:
    """Fetch the three Ocsai splits in memory (never written to the repo).

    Reuses ``paper01_fetch_sources._fetch_ocsai_splits`` (I-001) verbatim.
    Returns ``None`` -- never raises -- on any network/IO failure, matching
    ``paper01_fetch_sources._audit_ocsai``'s own catch set, so the caller
    can record ``source_unavailable`` and still report the Cambridge
    verdict (design-final.md §6, Codex HIGH-4; issue 006 Stop Conditions:
    Ocsai unreachable is explicitly not a stop condition).
    """
    try:
        return _fetch._fetch_ocsai_splits()  # noqa: SLF001
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def run_ocsai_audit(
    cambridge_rows_by_object: Mapping[str, Sequence[CambridgeRow]] | None = None,
    ocsai_splits_data: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    """End-to-end Ocsai audit: jsonl -> gold binarisation -> verdict (§3/§4).

    ``ocsai_splits_data`` defaults to a live fetch via
    :func:`load_ocsai_raw_bytes`; unreachable there (``None``) makes this
    return ``{"corpus": "ocsai", "status": "source_unavailable"}`` -- never
    a §6 :data:`VERDICT_ENUM` member, never raises, so the caller's
    Cambridge verdict is unaffected (AC 006-6). ``cambridge_rows_by_object``
    supplies ARM-X's Cambridge paperclip anchor (§4.2); omitted, ARM-X is
    simply empty in every split (report-only, never a stop condition).

    Both split schemes and both object batteries
    (:data:`OCSAI_PRIMARY_OBJECTS` -- verdict-bearing -- and
    :data:`OCSAI_SENSITIVITY_OBJECTS`, report-only, design-final.md §3.5)
    are run and returned.
    """
    splits_data = (
        ocsai_splits_data if ocsai_splits_data is not None else load_ocsai_raw_bytes()
    )
    if splits_data is None:
        return {"corpus": "ocsai", "status": "source_unavailable"}

    rows = load_ocsai_rows(splits_data)
    rows_by_object: dict[str, tuple[CambridgeRow, ...]] = {
        obj: tuple(r for r in rows if r.object == obj) for obj in OCSAI_PRIMARY_OBJECTS
    }

    encoders = build_available_encoders()
    if not encoders:
        msg = "no embedding encoder available offline; cannot score the external audit"
        raise RuntimeError(msg)
    vmaps = embed_all_texts(rows_by_object, encoders)

    cambridge_paperclip_rows: tuple[CambridgeRow, ...] = (
        tuple(cambridge_rows_by_object.get("paperclip", ()))
        if cambridge_rows_by_object is not None
        else ()
    )

    splits: dict[str, Any] = {}
    sensitivity_splits: dict[str, Any] = {}
    for scheme in SPLIT_SCHEMES:
        arm_x_vmaps: dict[str, dict[str, np.ndarray]] | None = None
        if cambridge_paperclip_rows:
            ocsai_paperclip_rows = rows_by_object.get("paperclip", ())
            combined = {"paperclip": cambridge_paperclip_rows + ocsai_paperclip_rows}
            arm_x_vmaps = embed_all_texts(combined, encoders)
        splits[scheme.key] = run_ocsai_split(
            rows_by_object,
            scheme.key,
            vmaps,
            objects=OCSAI_PRIMARY_OBJECTS,
            cambridge_paperclip_rows=cambridge_paperclip_rows,
            arm_x_vmaps=arm_x_vmaps,
        )
        sensitivity_splits[scheme.key] = run_ocsai_split(
            rows_by_object,
            scheme.key,
            vmaps,
            objects=OCSAI_SENSITIVITY_OBJECTS,
            cambridge_paperclip_rows=cambridge_paperclip_rows,
            arm_x_vmaps=arm_x_vmaps,
        )

    result: dict[str, Any] = {
        "corpus": "ocsai",
        "status": "ok",
        "encoders_available": sorted(encoders),
        "primary_split": "SPLIT-BLOCK",
        "object_battery_primary": list(OCSAI_PRIMARY_OBJECTS),
        "object_battery_sensitivity": list(OCSAI_SENSITIVITY_OBJECTS),
        "splits": splits,
        "sensitivity_object_battery_splits": sensitivity_splits,
    }
    return _quantize_json(result)


# --- combined, corpus-keyed output (design-final.md §6/DA-G1-12) -----------


def run_external_audit() -> dict[str, Any]:
    """Both corpora, corpus-keyed, with **no combined verdict**.

    design-final.md §6/DA-G1-12: "統合 verdict は作らない" (Codex HIGH-4).
    Cambridge's own verdict is entirely unaffected by Ocsai's availability
    (AC 006-6); each corpus's ``verdict``/``status`` is read independently
    by callers. Cambridge's own :func:`run_cambridge_audit` output is
    embedded unmodified -- its own tests already pin that shape.
    """
    cambridge_raw = load_cambridge_raw_bytes()
    cambridge_rows_by_object = {
        obj: load_cambridge_rows(obj, data) for obj, data in cambridge_raw.items()
    }
    return {
        "cambridge": run_cambridge_audit(cambridge_raw),
        "ocsai": run_ocsai_audit(cambridge_rows_by_object),
    }


def write_external_audit(path: Path = EXTERNAL_AUDIT_PATH) -> dict[str, Any]:
    """Run :func:`run_external_audit` and write it to ``path`` deterministically.

    Not wired into :func:`main` by this issue (I-007 owns ``main``/
    ``--fidelity``) -- callers invoke this directly when they want the
    corpus-keyed persisted artifact.
    """
    result = run_external_audit()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return result


# --- orchestration -----------------------------------------------------


def main() -> int:
    """Write ``SEED``, ``config.json``, and ``env.md``; return exit code 0."""
    write_seed_file()
    write_config()
    write_env_md()
    sys.stdout.write(
        f"[paper01-external-audit] wrote {SEED_PATH}, {CONFIG_PATH}, {ENV_MD_PATH}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

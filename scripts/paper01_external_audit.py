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
import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator import controls

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

# --- paths ---------------------------------------------------------------

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EXPERIMENT_DIR: Final[Path] = REPO_ROOT / "experiments" / "20260907-paper01-g1"
SEED_PATH: Final[Path] = EXPERIMENT_DIR / "SEED"
CONFIG_PATH: Final[Path] = EXPERIMENT_DIR / "config.json"
ENV_MD_PATH: Final[Path] = EXPERIMENT_DIR / "env.md"
SOURCE_AUDIT_PATH: Final[Path] = EXPERIMENT_DIR / "data" / "source-audit.json"

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
    potency_median: float
    auc_full_median: float
    auc_lao_median: float
    drop_median: float
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
    """

    report: CandidateExternalReport
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
        potency_median=median_result.potency,
        auc_full_median=median_result.auc_full,
        auc_lao_median=median_result.auc_lao,
        drop_median=median_result.drop,
        audit_not_engaged=not aggregate_draws(engaged_flags),
    )
    return CandidateStatisticalSummary(
        report=report,
        bootstrap=bootstrap,
        permutation_p=perm_p,
        median_draw_index=idx,
    )


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

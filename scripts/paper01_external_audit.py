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

from erre_sandbox.evidence.es4_actuator import constants as _c

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
- I-003 以降で encoder を使う実走は WSL2 GPU 経由が既定
  (`reference_g_gear_gpu_training_via_wsl.md`)。cross-platform float drift
  (libm 1-ULP) があるため、量子化した上で照合する
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

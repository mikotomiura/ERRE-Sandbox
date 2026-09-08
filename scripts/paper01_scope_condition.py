"""Frozen §9 pre-registration for the paper01 scope-condition measurement (Loop I-001).

The **single source of truth** for every value
``.steering/20260908-paper01-scope-condition/design-final.md`` froze *before*
any sparsification / Δ-decomposition / Stage 1 / Stage 2 / verdict code runs
(forking-paths seal, mirroring :mod:`scripts.paper01_external_audit` -- the
G1 external audit this task builds on top of). This module holds only the
module-level ``Final`` constants, the deterministic
``experiments/20260908-paper01-scope-condition/config.json`` writer, and the
frozen **field-only** contracts for the six result dataclasses every
downstream issue (I-002..I-006) imports -- the sparsification, Δ-decomposition,
Stage 1 deflation test, ``decide_scope()`` verdict logic, and τ* calibration
are out of scope for I-001 and land in later issues.

Two invariants this module exists to make mechanically checkable
(design-final.md §7, mirroring the G1 ADR's "eliminate tautological ACs"
discipline):

1. The eight floor/bootstrap/draw thresholds shared with the frozen internal
   ES-4 apparatus and the frozen G1 external audit (``AUC_FLOOR`` /
   ``REF_DEDUP`` / ``N_R_MIN`` / ``N_R_MAX`` from
   :mod:`erre_sandbox.evidence.es4_actuator.constants`; ``CI_ALPHA`` /
   ``N_RESAMPLES`` also from that module; ``MIN_CLASS_N`` / ``ANCHOR_DRAWS``
   from :mod:`scripts.paper01_external_audit`) are **read through** those
   owning modules at call time, never copied into a module-level literal
   here. ``tests/test_paper01_scope/test_preregistration.py`` proves the
   read-through is live (not a value baked in at import time) by
   ``monkeypatch.setattr``-ing the *owning* module's attribute and observing
   :func:`collect_preregistration` move in the very next call (design-final.md
   §7 Test Plan: identity/value-match + monkeypatch, not an AST scan).
2. :func:`collect_preregistration` never caches -- every value is looked up
   from the owning module attribute inside the function body, so a
   ``monkeypatch.setattr`` on this module, on
   :mod:`erre_sandbox.evidence.es4_actuator.constants`, or on
   :mod:`scripts.paper01_external_audit` is visible immediately. That is what
   lets ``test_config_mismatch_is_detected`` (AC 001-3) be non-tautological.

This ADR reuses the G1 external audit's two-path import helper
(``resolve_sibling_script``) rather than redefining it (design-final.md §6
"実装制約": the frozen apparatus and ``scripts/paper01_external_audit.py`` are
imported, never edited). Bootstrapping ``paper01_external_audit`` itself needs
one inlined two-path attempt (the helper cannot resolve the module that
defines it before that module is imported); every subsequent sibling import
(``es4_scorer_diag``) goes through ``_g1.resolve_sibling_script`` so the
two-path logic is written exactly once, in G1's module.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import sys
import unittest.mock
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from types import ModuleType

# --- two-path import bootstrap (design-final.md §6, reuses G1's helper) ----


def _import_paper01_external_audit() -> ModuleType:
    """Import the frozen G1 sibling script under either layout this runs in.

    Mirrors ``paper01_external_audit.resolve_sibling_script`` byte-for-byte
    (same two-path fallback: package-qualified import first, flat import with
    this file's own directory pushed onto ``sys.path`` second) because that
    helper lives *inside* the very module this function is bootstrapping --
    it cannot be called before it is imported. Every import after this one
    (``es4_scorer_diag``) goes through ``_g1.resolve_sibling_script`` instead
    of repeating this pattern, so the two-path logic is written exactly once
    at the source (G1's module) and reused everywhere else.
    """
    try:
        return importlib.import_module("scripts.paper01_external_audit")
    except ModuleNotFoundError:
        this_dir = str(Path(__file__).resolve().parent)
        if this_dir not in sys.path:
            sys.path.insert(0, this_dir)
        return importlib.import_module("paper01_external_audit")


_g1: Final[ModuleType] = _import_paper01_external_audit()
"""The frozen G1 external-audit module (design-final.md §9 table: ``CI_ALPHA``
/ ``N_RESAMPLES`` / ``MIN_CLASS_N`` / ``ANCHOR_DRAWS`` provenance). Imported,
never edited (S3 boundary)."""

_diag: Final[ModuleType] = _g1.resolve_sibling_script(
    "scripts.es4_scorer_diag", "es4_scorer_diag"
)
"""The frozen ES-4 scorer-diagnostic sibling script, resolved through G1's
own two-path helper (not a new one). AC 001-6 reads
``_diag.load_adversarial_labeled()`` from here -- the sealed internal gold,
never a hardcoded restatement of its shape."""

_c: Final[ModuleType] = importlib.import_module(
    "erre_sandbox.evidence.es4_actuator.constants"
)
"""The frozen ES-4 actuator constants module (design-final.md §9 table:
``AUC_FLOOR`` / ``REF_DEDUP`` / ``N_R_MIN`` / ``N_R_MAX`` / ``CI_ALPHA`` /
``N_RESAMPLES`` provenance)."""

# --- paths -------------------------------------------------------------

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EXPERIMENT_DIR: Final[Path] = (
    REPO_ROOT / "experiments" / "20260908-paper01-scope-condition"
)
SEED_PATH: Final[Path] = EXPERIMENT_DIR / "SEED"
CONFIG_PATH: Final[Path] = EXPERIMENT_DIR / "config.json"
ENV_MD_PATH: Final[Path] = EXPERIMENT_DIR / "env.md"
DATA_MD_PATH: Final[Path] = EXPERIMENT_DIR / "data.md"
RESULTS_DIR: Final[Path] = EXPERIMENT_DIR / "results"
"""Downstream issues' output directory (e.g. I-007's ``results/scope.json``,
this issue's own ``results/mutation-log.md``). Not populated by I-001 beyond
the mutation log."""

# --- this-ADR-specific frozen constants (design-final.md §9) ---------------

SEED: Final[int] = 20260908
"""Master seed for every draw in this measurement. Must equal the contents
of ``experiments/20260908-paper01-scope-condition/SEED`` and the
``PYTHONHASHSEED`` the operator exports before running I-002+ (mirrors G1's
own jaccard-family / hash-seed discipline)."""

TAU_GRID: Final[tuple[float, ...]] = (
    0.90,
    0.85,
    0.80,
    0.75,
    0.70,
    0.65,
    0.60,
    0.55,
    0.50,
    0.45,
    0.40,
)
"""§2.4 τ ladder (frozen, descending). τ* is calibrated by I-006 as
``argmin_tau |rho_ext(tau) - rho_int(primary)|`` over exactly this grid, ties
broken to the larger τ. The full ladder -- not just τ* -- is what the §3
Stage 2 main table reports (MEDIUM-3: no single-point-only claim)."""

STAGE1_REPLICATES: Final[int] = 500
"""§3 Stage 1: number of seeded resample-without-replacement replicates
(``R``) of the Ocsai gold shrunk to the internal C0 shape."""

STAGE1_DRAW_INDEX: Final[int] = 0
"""§3 Stage 1 (Codex HIGH-5, outcome-independence): the anchor is fixed to
ARM-A's ``draw_index = 0`` for the main deflation test. The median-by-drop
draw is an outcome-selected draw and is never used for the primary test --
only as a reported sensitivity."""

STAGE1_INTERNAL_GOOD_COUNTS: Final[tuple[int, ...]] = (
    3,
    3,
    1,
    3,
    1,
    1,
    0,
    1,
    2,
    3,
    1,
    3,
    1,
    1,
    1,
    0,
)
"""§3 Stage 1: the sealed internal gold's per-object ``good``-category count
multiset (sum 25 = the internal C0 pooled gold's valid-pair count, length 16
= the AUT battery's object count). This is the *measured shape* of
``_diag.load_adversarial_labeled()`` -- ``test_stage1_internal_shape_matches_
sealed_gold`` (AC 001-6) reads the sealed gold independently and cross-checks
this frozen multiset against it, rather than asserting only against itself."""

STAGE1_INTERNAL_DROP_REF: Final[float] = 0.2350
"""§3 Stage 1 acceptance band centre: the internal C0 pooled
``AUC_full - AUC_LAO`` drop, read off the sealed
``experiments/20260701-es4-scorer-diag/diagnostic.json`` (untouched, S3).
Deflation is supported iff a replicate's 5-95 percentile drop band contains
this value."""

STAGE1_OUTCOME_ENUM: Final[tuple[str, ...]] = (
    "DEFLATION_SUPPORTED",
    "DEFLATION_REJECTED",
    "INCONCLUSIVE",
)
"""§3 Stage 1 (Codex TASK-PRE HIGH-3 / DA-SC-19, **pre-registration amendment**):
the three-state outcome vocabulary the §3 Stage 1 table (design-final.md:165)
already froze but the original :class:`Stage1Result` contract could not
express. ``"INCONCLUSIVE"`` is the frozen "X0 が replicate の過半で
eligible でない" row -- when the primary candidate is not ``eligible`` in a
majority of replicates, the band cannot be trusted and the outcome must be
recorded as *undetermined*, never silently folded into
``"DEFLATION_REJECTED"``. This is registered in
:func:`collect_preregistration` (``"stage1_outcome_enum"``) exactly like
:data:`SCOPE_VERDICT_ENUM`, so ``config.json`` carries it too -- amending a
frozen pre-registration artifact is itself an event this module records
(DA-SC-19), not a silent addition."""

DELTA_TS_CANDIDATES: Final[tuple[str, ...]] = ("X0", "X3a", "X3b", "X3c", "C0", "C4")
"""§1 Stage 0 scope: the pure max-cos candidates for which
``T(x) = 1 - rarity_full(x)`` / ``S(x) = 1 - rarity_LAO(x)`` decompose
cleanly. X1 (mean-agg) and X2 (length-controlled) are excluded (HIGH-2) --
never added back without a superseding ADR."""

DELTA_MATERIAL_EPS: Final[float] = 0.01
"""§4 F4 (mechanism-absent) threshold: Stage 0 reports "no material
difference" iff ``abs(delta_int - delta_ext) < DELTA_MATERIAL_EPS``."""

FAIL_PRECEDENCE: Final[tuple[str, ...]] = (
    "F4",
    "F1",
    "F2",
    "F3",
    "F5",
    "F6",
    "F7",
)
"""§4 pre-registered, total, deterministic fail-branch priority order. When
multiple branches are simultaneously reached, the primary reported reason is
the first one in this tuple that applies."""

SCOPE_VERDICT_ENUM: Final[tuple[str, ...]] = ("WRITE", "DO_NOT_WRITE")
"""§5 exit-table language (B-G1-10, not renegotiable): ``"WRITE"`` iff Stage 1
rejects deflation *and* Stage 2 supports condition C with no F1-F7 hit;
``"DO_NOT_WRITE"`` otherwise (folded into paper 03's methods/limitations
instead)."""

# --- collection / config.json ------------------------------------------


def collect_preregistration() -> dict[str, Any]:
    """Collect every frozen §9 value by reading module attributes *now*.

    Deliberately non-cached: every value below is read from its owning
    attribute at call time (``_c.AUC_FLOOR``, ``_g1.MIN_CLASS_N``, the bare
    module globals declared above, ...), never a value baked in at import
    time. This is what makes a ``monkeypatch.setattr`` on this module, on
    ``erre_sandbox.evidence.es4_actuator.constants``, or on
    ``scripts.paper01_external_audit`` visible in the very next call --
    the mechanism ``test_shared_constants_are_imported_not_redefined`` and
    ``test_config_mismatch_is_detected`` use to prove the freeze is a real
    read-through, not a tautological self-comparison.
    """
    return {
        "seed": SEED,
        "tau_grid": list(TAU_GRID),
        "stage1_replicates": STAGE1_REPLICATES,
        "stage1_draw_index": STAGE1_DRAW_INDEX,
        "stage1_internal_good_counts": list(STAGE1_INTERNAL_GOOD_COUNTS),
        "stage1_internal_drop_ref": STAGE1_INTERNAL_DROP_REF,
        "stage1_outcome_enum": list(STAGE1_OUTCOME_ENUM),
        "delta_ts_candidates": list(DELTA_TS_CANDIDATES),
        "delta_material_eps": DELTA_MATERIAL_EPS,
        "fail_precedence": list(FAIL_PRECEDENCE),
        "scope_verdict_enum": list(SCOPE_VERDICT_ENUM),
        "thresholds": {
            "auc_floor": _c.AUC_FLOOR,
            "ref_dedup": _c.REF_DEDUP,
            "n_r_min": _c.N_R_MIN,
            "n_r_max": _c.N_R_MAX,
            "ci_alpha": _c.CI_ALPHA,
            "n_resamples": _c.N_RESAMPLES,
            "min_class_n": _g1.MIN_CLASS_N,
            "anchor_draws": _g1.ANCHOR_DRAWS,
        },
    }


def config_matches_preregistration(config: Mapping[str, Any]) -> bool:
    """True iff a loaded ``config.json`` still equals the live constants.

    Calls :func:`collect_preregistration` fresh on every invocation, so this
    is the one comparison both the round-trip test (AC 001-2) and the
    monkeypatch-mismatch test (AC 001-3) exercise -- there is no separate
    "expected" dict that could itself drift from the constants unnoticed.
    """
    return dict(config) == collect_preregistration()


def write_config(path: Path = CONFIG_PATH) -> None:
    """Write ``config.json`` deterministically: no wall-clock, sorted keys.

    ``sort_keys=True`` + fixed ``indent`` make two independent runs
    byte-identical (D2's reproducibility requirement) as long as the frozen
    constants above have not changed.
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


# --- SEED file -----------------------------------------------------------


def write_seed_file(path: Path = SEED_PATH) -> None:
    """Write the master seed as plain decimal text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{SEED}\n", encoding="utf-8")


def load_seed_file(path: Path = SEED_PATH) -> int:
    """Read back the master seed written by :func:`write_seed_file`."""
    return int(path.read_text(encoding="utf-8").strip())


# --- env.md ----------------------------------------------------------------

ENV_MD_TEXT: Final[str] = """# 実行環境 (paper01 scope condition)

## Python / パッケージ管理

- Python 3.11 (`pyproject.toml` `requires-python = ">=3.11,<3.12"`)
- 依存は `uv.lock` を SSOT として固定 (`uv sync --frozen`)。CI 既定は
  extras 無しで走る。I-001 (本モジュール) は stdlib のみで完結し、
  encoder は一切ロードしない。

## 二経路 (Windows / WSL2)

- Windows: `.venv/Scripts/python.exe`
- WSL2 / Linux: `.venv/bin/python`
- 本測定は G1 と同様 **CPU のみで完結する見込み** (I-002 以降で encoder を
  使う段になった時点で改めて確認する)。cross-platform float drift
  (libm 1-ULP) はあるため、JSON へ emit する float は量子化した上で照合する
  (`feedback_golden_crossplatform_float_drift.md` の教訓を踏襲)。

## 入力データ (G1 の再利用、新規取得なし)

本タスクは `experiments/20260907-paper01-g1/data/` の入力を再利用する。
SHA-256 pin と再取得手順は `data.md` を参照。

## PYTHONHASHSEED

`SEED` ファイル (= `experiments/20260908-paper01-scope-condition/SEED`) の値
(`20260908`) を `PYTHONHASHSEED` にも設定してから I-002 以降の実走を
起動すること:

```bash
export PYTHONHASHSEED=20260908
```

```powershell
$env:PYTHONHASHSEED = "20260908"
```

固定しない場合、集合演算を含む候補の結果がプロセスをまたいで bit 再現しない
(G1 design-final.md §8 と同じ理由)。
"""


def write_env_md(path: Path = ENV_MD_PATH) -> None:
    """Write the static environment note (no network / no measurement)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ENV_MD_TEXT, encoding="utf-8")


# --- shared result dataclass contracts (design-final.md §9, I-001 scope) ---
#
# Frozen contracts only: field names + types, no computation. Downstream
# issues (I-002 populates InternalReference; I-003 populates
# DeltaDecomposition; I-004 populates Stage1Result; I-005 populates
# ScopeVerdict; I-006 populates CellResult / TauCalibration) import these
# dataclasses from this module rather than redeclaring them, so a field
# rename here is the single point of truth every downstream issue shares.


@dataclasses.dataclass(frozen=True, slots=True)
class DeltaDecomposition:
    """Stage 0 Δ=T−S decomposition for one ``(source, candidate)`` pair.

    design-final.md §1/§3 Stage 0. Frozen contract only -- I-003 fills the
    values. ``source`` distinguishes internal (``"internal_c0"`` /
    ``"internal_c4"``) from external (e.g. ``"external_ocsai_arm_a"`` /
    ``"external_cambridge_arm_a"``); ``candidate`` is one of the six
    :data:`DELTA_TS_CANDIDATES` members. ``s_common_minus_s_good`` is the
    MEDIUM-1 label-stratified residual-coverage gap; ``rho`` is the §2.1
    reference-set proxy placed alongside T/S/Δ for the same pair.
    """

    source: str
    candidate: str
    n_good: int
    n_common: int
    mean_t_good: float
    mean_t_common: float
    mean_s_good: float
    mean_s_common: float
    mean_delta_good: float
    mean_delta_common: float
    s_common_minus_s_good: float
    rho: float


@dataclasses.dataclass(frozen=True, slots=True)
class Stage1Result:
    """Stage 1 deflation-test outcome for one ``DELTA_TS_CANDIDATES`` member.

    design-final.md §3 Stage 1. Frozen contract only -- I-004 fills the
    values. ``drop_p5``/``drop_p95`` are the 5-95 percentile bounds of the
    :data:`STAGE1_REPLICATES` seeded pooled-AUC-drop replicates;
    ``eligible_fraction`` is the share of replicates whose
    ``AUC_strat(full)`` cleared ``AUC_FLOOR``.

    **Three-state outcome (Codex TASK-PRE HIGH-3 / DA-SC-19, pre-registration
    amendment)**: ``stage1_outcome`` is the **load-bearing** field -- one of
    :data:`STAGE1_OUTCOME_ENUM`. It is the frozen §3 table's third row
    ("X0 が replicate の過半で eligible でない" -> "判定不能") made
    representable: when ``eligible_fraction <= 0.5`` the outcome **must** be
    ``"INCONCLUSIVE"``, never silently folded into ``"DEFLATION_REJECTED"``.
    ``deflation_supported: bool`` is **retained, not removed** -- it is a
    **derived mirror** of ``stage1_outcome == "DEFLATION_SUPPORTED"``, kept
    for the callers that only need the binary read. **`not
    deflation_supported` must never be used to derive the right to report
    "書く" (``ScopeVerdict.verdict == "WRITE"``, design-final.md §5)** -- that
    right may only be derived from ``stage1_outcome ==
    "DEFLATION_REJECTED"``. Both ``"INCONCLUSIVE"`` and
    ``"DEFLATION_REJECTED"`` produce ``deflation_supported = False``; only
    ``stage1_outcome`` distinguishes them. I-005's ``decide_scope()`` is
    where this rule is enforced in logic; this dataclass only makes the
    distinction representable.

    The remaining new fields are secondary/diagnostic, reported alongside
    the primary pooled-AUC band (design-final.md §3 Stage 1, "副" rows):
    ``drop_p5_eligible``/``drop_p95_eligible``/``median_drop_eligible`` are
    the same band restricted to ``eligible`` replicates only (the §3 table's
    third-row remedy: "eligible な replicate に限った帯を副として報告");
    ``drop_p5_strat``/``drop_p95_strat``/``median_drop_strat`` are the
    stratified-statistic counterpart of the pooled band (issue 004 Scope
    In); ``n_objects_pool_short``/``pool_short_objects`` surface -- never
    silently drop -- objects whose replicate-construction pool ran short;
    ``median_draw_drop``/``median_draw_outcome`` are the DA-SC-6/DA-SC-12
    median-by-drop-draw sensitivity check -- an **outcome-selected** draw,
    so ``median_draw_outcome`` must **never** be used as the primary
    verdict input (only ``stage1_outcome``, anchored at
    :data:`STAGE1_DRAW_INDEX`, may be).
    """

    candidate: str
    n_replicates: int
    drop_p5: float
    drop_p95: float
    median_drop: float
    eligible_fraction: float
    deflation_supported: bool
    stage1_outcome: str
    drop_p5_eligible: float
    drop_p95_eligible: float
    median_drop_eligible: float
    drop_p5_strat: float
    drop_p95_strat: float
    median_drop_strat: float
    n_objects_pool_short: int
    pool_short_objects: tuple[str, ...]
    median_draw_drop: float
    median_draw_outcome: str

    def __post_init__(self) -> None:
        """Reject artifacts whose mirror disagrees with the load-bearing field.

        Codex TASK-POST MEDIUM-2. ``deflation_supported`` is documented as a
        *derived mirror* of ``stage1_outcome == "DEFLATION_SUPPORTED"``, but the
        dataclass previously accepted any combination, so a hand-built
        ``Stage1Result(stage1_outcome="DEFLATION_REJECTED",
        deflation_supported=True)`` was constructible. On a pre-registered
        instrument that is not a harmless inconsistency: the two fields feed
        different readers (``decide_scope()`` reads the enum, simpler callers
        read the bool), so a disagreeing artifact would let the same replicate
        argue both ways. Validate at construction rather than trusting every
        producer to stay consistent.
        """
        if self.stage1_outcome not in STAGE1_OUTCOME_ENUM:
            raise ValueError(
                f"stage1_outcome {self.stage1_outcome!r} is not one of "
                f"{STAGE1_OUTCOME_ENUM!r}"
            )
        if self.median_draw_outcome not in STAGE1_OUTCOME_ENUM:
            raise ValueError(
                f"median_draw_outcome {self.median_draw_outcome!r} is not one of "
                f"{STAGE1_OUTCOME_ENUM!r}"
            )
        mirror = self.stage1_outcome == "DEFLATION_SUPPORTED"
        if self.deflation_supported != mirror:
            raise ValueError(
                "deflation_supported must mirror "
                'stage1_outcome == "DEFLATION_SUPPORTED" '
                f"(got stage1_outcome={self.stage1_outcome!r}, "
                f"deflation_supported={self.deflation_supported!r})"
            )


@dataclasses.dataclass(frozen=True, slots=True)
class CellResult:
    """One Stage 2 ``(τ, k)`` leader-clustering cell's decide_external outcome.

    design-final.md §3 Stage 2. Frozen contract only -- I-006 fills the
    values. ``tau``/``k_target`` place the cell in the 2x2 grid
    (τ ∈ {0.90, τ*} x k ∈ {30, k*}); ``k_effective`` is
    ``min(k_target, n_leaders)`` after (uncapped) leader clustering.
    ``active_objects`` is the DA-SC-3 4-cell-common-intersection object set
    actually scored; ``object_weights`` is the per-object weight LOW-2
    requires be surfaced (Ocsai brick-weight-concentration diagnostic).
    """

    tau: float
    k_target: int
    k_effective: int
    n_leaders: int
    corpus: str
    split_scheme: str
    verdict: str
    active_objects: tuple[str, ...]
    object_weights: Mapping[str, float]


@dataclasses.dataclass(frozen=True, slots=True)
class InternalReference:
    """ρ_int primary (C4 raw) / secondary (C0 dedup'd) reference geometry.

    One AUT object, design-final.md §2.3.
    Frozen contract only -- I-006 fills the values.
    (Codex TASK-PRE HIGH-5 owner fix: the low-level ρ function is I-002's,
    but wiring ``ρ_int``/``k*`` through this dataclass is I-006's.)
    ``rho_primary_c4`` is the C4-raw-curated reference
    set's nearest-neighbour mean cosine (the primary ρ_int basis -- "what
    the actually-collapsed scorer saw"); ``rho_secondary_c0`` is the same
    quantity over ``construct_all_references``'s dedup'd ``R_object`` (the
    mandatory cross-check, §2.3).
    """

    object_id: str
    rho_primary_c4: float
    rho_secondary_c0: float
    n_refs_primary_c4: int
    n_refs_secondary_c0: int


@dataclasses.dataclass(frozen=True, slots=True)
class TauCalibration:
    """τ* calibration of the external anchor-pool geometry vs. ρ_int(primary).

    Over the frozen :data:`TAU_GRID` (design-final.md §2.4). Frozen contract
    only -- I-006 fills the values. ``rho_by_tau`` is index-aligned with
    :data:`TAU_GRID` (never a float-keyed mapping, to avoid float-equality
    lookup hazards); ``tau_star`` is
    ``argmin_tau |rho_by_tau[i] - rho_int_primary|`` with ties broken to the
    larger τ (design-final.md §2.4). ``k_star`` is the internal C4
    per-object median ``|R_o|``. ``single_point_dependent`` records
    MEDIUM-3's robustness check -- whether the τ* verdict fails to reproduce
    at either :data:`TAU_GRID` neighbour of τ*.
    """

    rho_int_primary: float
    rho_by_tau: tuple[float, ...]
    tau_star: float
    k_star: int
    single_point_dependent: bool


@dataclasses.dataclass(frozen=True, slots=True)
class ScopeVerdict:
    """The overall §3/§4/§5 scope-condition verdict (B-G1-10 binding).

    design-final.md. Frozen contract only -- I-005 fills the values.
    ``verdict`` is one of :data:`SCOPE_VERDICT_ENUM` (``"WRITE"`` iff Stage 1
    rejects deflation *and* Stage 2 supports condition C with no F1-F7 hit;
    ``"DO_NOT_WRITE"`` otherwise, per §5's exit table). ``fail_reason`` is
    the :data:`FAIL_PRECEDENCE`-ordered primary reason when multiple fail
    branches are simultaneously reached (``None`` when C is supported).
    ``deflation_supported`` mirrors Stage 1's early-exit branch (§4: a
    deflation-supported Stage 1 forces ``"DO_NOT_WRITE"`` regardless of
    Stage 2, never re-derived from ``fail_reason``).
    ``condition_c_supported`` is the raw §3 four-condition conjunction
    before :data:`FAIL_PRECEDENCE` is applied. ``t_confound_note_required``
    (Codex TASK-PRE HIGH-4 / DA-SC-17, additive field -- the other five
    fields above and ``notes`` keep their frozen names, never renamed) is
    True iff Stage 0's §1 T/S asymmetry check (DA-SC-10, HIGH-3-revised)
    found the internal collapse to be primarily T-driven while condition C
    is nonetheless supported -- it forces the write-up to carry the
    mandatory "T 由来交絡" caveat DA-SC-10 requires instead of silently
    folding to "特定できない".
    """

    verdict: str
    deflation_supported: bool
    condition_c_supported: bool
    single_point_dependent: bool
    fail_reason: str | None
    notes: tuple[str, ...]
    t_confound_note_required: bool


# ---------------------------------------------------------------------------
# I-002: sparsification layer (leader clustering / rho)
# ---------------------------------------------------------------------------


def leader_cluster_indices(
    embeddings: np.ndarray, *, cap: int, radius: float
) -> list[int]:
    """Frozen-scan-order greedy leader clustering at an arbitrary ``radius``.

    design-final.md §3 Stage 2: "半径 τ の greedy leader 法" -- "凍結走査順に、
    既存代表すべてから ``cos < τ`` の項目を新代表として採用する". This is the
    *threshold-parameterised* twin of
    :func:`scripts.paper01_external_audit.greedy_dedupe_indices` -- the same
    scan / accept predicate, with the frozen ``_c.REF_DEDUP`` module constant
    replaced by the caller-supplied ``radius`` argument. ``embeddings`` must
    already be unit-normalised and in the caller's frozen scan order; the
    result is a subsequence of that order, capped at ``cap`` entries (the cap
    check happens before the current item is even compared against the kept
    set, exactly as in ``greedy_dedupe_indices``).

    **Fidelity pin (a)** (design-final.md §6, this issue's Goal): calling
    this with ``radius=REF_DEDUP`` must return **exactly** the same index
    list as ``greedy_dedupe_indices(embeddings, cap=cap)`` for the same
    input -- proven by
    ``test_leader_cluster_matches_greedy_dedupe_at_ref_dedup``. This equality
    is **only** pin (a): it does **not** by itself reconstruct ARM-A's full
    *cell* pipeline (dedupe -> cap -> seeded draw) or reproduce ARM-A's
    reported numbers -- that is fidelity pin (b), owned by I-006 (Codex
    HIGH-4; see this issue's Background section and design-final.md §3
    Stage 2 / §6).
    """
    kept: list[int] = []
    for i in range(embeddings.shape[0]):
        if len(kept) >= cap:
            break
        if not kept:
            kept.append(i)
            continue
        cos = embeddings[i] @ embeddings[np.asarray(kept)].T
        if float(cos.max()) < radius:
            kept.append(i)
    return kept


def reference_redundancy(embeddings: np.ndarray) -> float:
    """§2.1 ``rho(R_o) = mean_r max_{r' != r} cos(r, r')``.

    The mean nearest-neighbour cosine similarity within one object's
    reference set -- design-final.md §2.2's "冗長性は「隣がどれだけ詰まって
    いるか」の中心傾向" (a central-tendency statistic, deliberately not the
    single maximum pairwise cosine over the whole set: see
    ``test_rho_is_not_max_pairwise``, AC 002-8).

    **rho is a proxy for S, not its algebraic counterpart** (design-final.md
    §2.1, Codex HIGH-1/MEDIUM-1 -- reflected verbatim here per this issue's
    Background section): rho is an anchor-anchor quantity, S is an
    item-anchor quantity. Never describe the relationship as "代数的に対応"
    ("algebraically corresponds") anywhere this function is documented or
    used -- the correspondence is only shown descriptively, by placing rho
    alongside the measured Stage 0 S values (I-003's job), never derived
    from rho by formula.

    ``embeddings`` must already be unit-normalised, shape ``(n, d)``.
    Degenerate case (design-final.md §2.1, Codex TASK-PRE LOW-1 -- **frozen**
    input to I-006's tau* calibration): when ``|R_o| < 2`` there is no
    ``r' != r`` to maximise over, so this returns the frozen value ``0.0``
    rather than raising or returning NaN.
    """
    n = embeddings.shape[0]
    if n < 2:  # noqa: PLR2004 — nearest-neighbour pair arity, not magic
        return 0.0
    sims = embeddings @ embeddings.T
    np.fill_diagonal(sims, -np.inf)
    return float(sims.max(axis=1).mean())


def corpus_redundancy(by_object: Mapping[str, np.ndarray]) -> float:
    """§2.1 ``rho(corpus)``: the unweighted mean of ``reference_redundancy``.

    design-final.md §2.1: "物体横断の単純平均 (物体重みで加重しない。重み集中
    を持ち込まないため)" -- deliberately *not* weighted by each object's
    ``|R_o|`` (AC 002-9: an object with a large reference set must not
    dominate the corpus-level figure the way Ocsai's brick-weight
    concentration dominates the object-weighted AUC statistics elsewhere in
    this ADR, design-final.md §8 Limitations item 6).

    ``by_object`` maps each object id to its (unit-normalised) reference
    embeddings, e.g. the post-``leader_cluster_indices`` survivor set at a
    given ``(tau, k)`` cell. Returns ``0.0`` for an empty mapping.
    """
    if not by_object:
        return 0.0
    values = [reference_redundancy(emb) for emb in by_object.values()]
    return float(sum(values) / len(values))


# ---------------------------------------------------------------------------
# I-003: Stage 0 -- Delta = T - S decomposition
# ---------------------------------------------------------------------------

_T_S_ATTRIBUTION_TOLERANCE: Final[float] = 0.1
"""design-final.md §3 "主に由来" 判定: 比 ``|T_int-T_ext| / |S_int-S_ext|`` が
``1.0 ± この値`` (= [0.9, 1.1]) のとき :func:`delta_attribution` は ``"both"``
を返す。境界含む (inclusive) -- 1.0±0.1 の両端そのものが「両方」側に倒れる。"""


def _engaged_flags(
    max_sim_full: tuple[float, ...],
) -> tuple[float, ...]:
    """Item-level "engaged" predicate, owned by :mod:`paper01_external_audit`.

    design-final.md §3 Stage 0: T/S/Δ are reported "engaged 項目上" only.
    **Codex TASK-PRE HIGH-1 (binding)**: the item-level flag is
    ``_g1.near_dup_flags_from_similarity(max_sim_full, ref_dedup=_c.REF_DEDUP)``
    used verbatim -- :func:`_g1.potency_and_near_dup` only returns the
    *aggregate* near-dup rate (its own docstring says so), so reimplementing
    the ``>=`` comparison here would silently fork the predicate from the one
    G1's own ``score_rows_for_draw`` uses to compute ``potency``. AC 003-5
    pins that this selects the *same item set* as
    :func:`_g1.potency_and_near_dup`'s internal ``near_dup`` mask.
    """
    return tuple(
        _g1.near_dup_flags_from_similarity(max_sim_full, ref_dedup=_c.REF_DEDUP)
    )


def _engaged_class_means(
    values: tuple[float, ...], labels: tuple[int, ...]
) -> tuple[float, float]:
    """``(mean_good, mean_common)`` over already-engaged-filtered rows.

    Fail-open on an empty class: returns ``0.0`` rather than raising or
    producing ``NaN`` -- the same convention
    :func:`scripts.paper01_external_audit.potency_and_near_dup` uses for its
    per-class near-dup rate (``if good_mask.any() else 0.0``). AC 003-6
    requires a one-sided input (only ``good`` or only ``common`` engaged
    items) not to break.
    """
    good = [v for v, label in zip(values, labels, strict=True) if label == 1]
    common = [v for v, label in zip(values, labels, strict=True) if label == 0]
    mean_good = float(sum(good) / len(good)) if good else 0.0
    mean_common = float(sum(common) / len(common)) if common else 0.0
    return mean_good, mean_common


def split_delta(
    scores_full: tuple[float, ...],
    scores_lao: tuple[float, ...],
    labels: tuple[int, ...],
    max_sim_full: tuple[float, ...],
    *,
    source: str,
    candidate: str,
    rho: float,
) -> DeltaDecomposition:
    """design-final.md §1/§3 Stage 0: ``T = 1-rarity_full``, ``S = 1-rarity_LAO``.

    ``Δ(x) = T(x) - S(x) = rarity_LAO(x) - rarity_full(x)`` (§1, algebraic
    identity -- computed here as ``T - S``, never re-derived as ``S - T``).
    ``scores_full``/``scores_lao`` are the *rarity* values a candidate's
    ``Candidate.rarity(...)`` already produced (e.g. via
    :func:`scripts.paper01_external_audit.score_rows_for_draw`'s
    ``DrawItems.scores_full``/``.scores_lao``) -- this function performs no
    embedding lookups of its own (design-final.md §1: "追加の埋め込みなしに
    得られる").

    **Scope gate (HIGH-2 / DA-SC-9, binding)**: only raises applies to pure
    max-cos candidates. ``candidate`` must be a member of
    :data:`DELTA_TS_CANDIDATES` (``X0, X3a, X3b, X3c, C0, C4``) -- X1
    (``agg="mean"``) does not decompose into ``T - S`` at all (Codex HIGH-2),
    and X2 (length-controlled) cancels to ``Δ(X2) ≡ Δ(X0)`` but cannot
    recover ``T``/``S`` individually (DA-SC-9's own refinement). Passing
    either raises :class:`ValueError` rather than silently producing a
    meaningless decomposition (AC 003-4).

    **Empty-survivor semantics (Codex MEDIUM-2, frozen)**: when LAO leaves no
    surviving anchor for an item, the upstream candidate's ``rarity(...,
    leave_anchor_out=True)`` call (:func:`es4_scorer_diag.embed_rarity`)
    returns ``0.0`` by its own frozen contract ("everything is a near-dup =>
    maximally common => rarity 0"). This function inherits that semantics
    unchanged: ``S(x) = 1 - scores_lao[x]`` is then exactly ``1.0`` -- the
    "fully covered" reading, not a special-cased branch here.

    Only **engaged** items (:func:`_engaged_flags`) contribute to the
    reported means; each engaged item is further split good/common
    (``labels``: 1=good, 0=common) via :func:`_engaged_class_means`.
    ``s_common_minus_s_good`` (MEDIUM-1) is the residual-coverage gap between
    the two classes' engaged means.
    """
    if candidate not in DELTA_TS_CANDIDATES:
        msg = (
            f"split_delta: candidate {candidate!r} is not one of the pure "
            f"max-cos DELTA_TS_CANDIDATES {DELTA_TS_CANDIDATES!r} "
            "(design-final.md §1 HIGH-2 / DA-SC-9: X1 (mean-agg) does not "
            "decompose into T-S, and X2 (length-controlled) cannot recover "
            "T/S individually even though Delta(X2) == Delta(X0) -- both "
            "are excluded by construction and never accepted here)"
        )
        raise ValueError(msg)

    n = len(scores_full)
    if not (len(scores_lao) == n and len(labels) == n and len(max_sim_full) == n):
        msg = (
            "split_delta: scores_full/scores_lao/labels/max_sim_full must "
            "share one length (one row per scored item)"
        )
        raise ValueError(msg)

    engaged = _engaged_flags(max_sim_full)

    t_vals: list[float] = []
    s_vals: list[float] = []
    delta_vals: list[float] = []
    engaged_labels: list[int] = []
    for full, lao, label, flag in zip(
        scores_full, scores_lao, labels, engaged, strict=True
    ):
        if flag != 1.0:
            continue
        t = 1.0 - full
        s = 1.0 - lao
        t_vals.append(t)
        s_vals.append(s)
        delta_vals.append(t - s)
        engaged_labels.append(label)

    t_vals_t = tuple(t_vals)
    s_vals_t = tuple(s_vals)
    delta_vals_t = tuple(delta_vals)
    engaged_labels_t = tuple(engaged_labels)

    mean_t_good, mean_t_common = _engaged_class_means(t_vals_t, engaged_labels_t)
    mean_s_good, mean_s_common = _engaged_class_means(s_vals_t, engaged_labels_t)
    mean_delta_good, mean_delta_common = _engaged_class_means(
        delta_vals_t, engaged_labels_t
    )

    n_good = sum(1 for label in engaged_labels_t if label == 1)
    n_common = sum(1 for label in engaged_labels_t if label == 0)

    return DeltaDecomposition(
        source=source,
        candidate=candidate,
        n_good=n_good,
        n_common=n_common,
        mean_t_good=mean_t_good,
        mean_t_common=mean_t_common,
        mean_s_good=mean_s_good,
        mean_s_common=mean_s_common,
        mean_delta_good=mean_delta_good,
        mean_delta_common=mean_delta_common,
        s_common_minus_s_good=mean_s_common - mean_s_good,
        rho=rho,
    )


def delta_is_material(delta_int: float, delta_ext: float) -> bool:
    """design-final.md §4 F4: True iff internal/external Δ differ materially.

    ``abs(delta_int - delta_ext) >= DELTA_MATERIAL_EPS`` -- the boundary
    value itself (exactly ``DELTA_MATERIAL_EPS``) counts as material: §3
    defines "材料差が無い" ("no material difference", F4) with a strict
    ``<``, so this function (the positive predicate) uses ``>=`` at the same
    threshold, never re-derived as ``not (... < eps)`` written differently
    (AC 003-9 pins the boundary side).
    """
    return abs(delta_int - delta_ext) >= DELTA_MATERIAL_EPS


def delta_attribution(t_int: float, s_int: float, t_ext: float, s_ext: float) -> str:
    """design-final.md §3 Stage 0 "主に由来" 事前登録判定 -- ``"T"``/``"S"``/``"both"``.

    ``|T_int - T_ext| > |S_int - S_ext|`` -> ``"T"``; the reverse -> ``"S"``;
    a ratio within ``1.0 ± `` :data:`_T_S_ATTRIBUTION_TOLERANCE` (i.e.
    ``[0.9, 1.1]``, inclusive both ends) -> ``"both"``. The "both" band is
    checked *before* the strict T/S comparison, so a ratio landing exactly on
    either boundary reads as ``"both"`` rather than falling through to the
    strict inequality. When both deltas are exactly ``0.0`` the ratio is
    undefined (``0/0``) and this also reads as ``"both"`` (no signal either
    way is the most conservative reading, consistent with the inclusive
    band). All three branches are reachable from disjoint, non-tautological
    fixtures (AC 003-8).
    """
    delta_t = abs(t_int - t_ext)
    delta_s = abs(s_int - s_ext)
    if delta_t == 0.0 and delta_s == 0.0:
        return "both"
    if delta_s != 0.0:
        ratio = delta_t / delta_s
        lo = 1.0 - _T_S_ATTRIBUTION_TOLERANCE
        hi = 1.0 + _T_S_ATTRIBUTION_TOLERANCE
        if lo <= ratio <= hi:
            return "both"
    return "T" if delta_t > delta_s else "S"


# ---------------------------------------------------------------------------
# I-004: Stage 1 -- deflation test
# ---------------------------------------------------------------------------

_STAGE1_ELIGIBLE_FRACTION_FLOOR: Final[float] = 0.5
"""design-final.md §3 Stage 1 / Codex TASK-PRE HIGH-3 / DA-SC-19: a replicate
band is only trustworthy when *more than half* its replicates are
``eligible``. ``eligible_fraction`` at exactly this floor still counts as
"the majority is not eligible" (design-final.md:165's "X0 が replicate の
過半で eligible でない") -- a named constant instead of an inline literal so
:func:`stage1_outcome`'s boundary predicate is a single line to mutate and
test, never a bare magic number."""


def _stage1_seed(
    seed: int, corpus: str, scheme: str, replicate_index: int, *extra: object
) -> int:
    """Fold this call's own ``seed`` through the frozen :func:`_g1.derive_seed`.

    ``derive_seed`` always mixes in G1's own frozen module ``SEED`` first;
    passing this function's ``seed`` argument as the leading part on top of
    that (never re-hashed by hand -- the frozen apparatus's own hashing is
    reused unmodified, design-final.md §6) is what makes ``internal_shaped_
    replicates``'s own ``seed`` parameter load-bearing (AC 004-3: same seed
    -> same extraction, a different seed -> a different one) -- reading only
    ``_g1.SEED`` would not vary with it. The remaining parts mirror the
    issue's own ``derive_seed("stage1", corpus, scheme, replicate_index)``
    call literally (Codex TASK-PRE MEDIUM-2: ``corpus``/``scheme`` are
    explicit arguments here too, never inferred from a module global);
    ``extra`` differentiates the good/common draws *within* one replicate
    for the same object, and different objects from each other, which the
    issue's four-part call alone cannot (every object in the same replicate
    would otherwise share one seed).
    """
    return _g1.derive_seed(seed, "stage1", corpus, scheme, replicate_index, *extra)


@dataclasses.dataclass(frozen=True, slots=True)
class ObjectGoldPool:
    """One active object's already-labelled item-index pools for Stage 1.

    design-final.md §3 Stage 1. This issue's own contract (not one of the
    six I-001-frozen dataclasses): ``good_item_indices`` / ``common_item_
    indices`` are, in the caller's frozen scan order, positions into the
    *shared* item ordering a companion :class:`~scripts.paper01_external_
    audit.DrawItems`'s ``labels`` / ``objects`` arrays use (the adapter/
    encoder layer that produces those arrays and this pool mapping is out
    of I-004's scope, lands in I-007) -- :func:`internal_shaped_replicates`
    only ever draws *indices*, never touches a score or an embedding.
    ``object_weight`` is ``n_good * n_common`` for this object, the same §1
    weight :func:`~scripts.paper01_external_audit.object_class_weights`
    reports -- used only to order objects for the cyclic
    :data:`STAGE1_INTERNAL_GOOD_COUNTS` assignment (design-final.md §3:
    "object_weight 降順の active 物体へ巡回割当"), never fed into any AUC
    computation.
    """

    object_key: str
    object_weight: float
    good_item_indices: tuple[int, ...]
    common_item_indices: tuple[int, ...]


def _stage1_object_order(contexts: Mapping[str, ObjectGoldPool]) -> list[str]:
    """Active objects ordered by ``object_weight`` descending.

    design-final.md §3, ties broken by object key ascending -- fully
    deterministic regardless of ``contexts``'s own iteration/insertion
    order (a plain ``dict`` does not sort itself).
    """
    return sorted(contexts, key=lambda key: (-contexts[key].object_weight, key))


def _stage1_good_counts(contexts: Mapping[str, ObjectGoldPool]) -> dict[str, int]:
    """Cyclic assignment of :data:`STAGE1_INTERNAL_GOOD_COUNTS` to objects.

    design-final.md §3: the weight-ordered active object at position ``i``
    (0-based, in :func:`_stage1_object_order`) gets
    ``STAGE1_INTERNAL_GOOD_COUNTS[i % len(STAGE1_INTERNAL_GOOD_COUNTS)]`` --
    wrapping around ("巡回割当") once there are more active objects than the
    16-entry internal multiset.
    """
    order = _stage1_object_order(contexts)
    n = len(STAGE1_INTERNAL_GOOD_COUNTS)
    return {obj: STAGE1_INTERNAL_GOOD_COUNTS[i % n] for i, obj in enumerate(order)}


def _stage1_pool_short_objects(
    contexts: Mapping[str, ObjectGoldPool], good_counts: Mapping[str, int]
) -> tuple[str, ...]:
    """Objects whose good or common pool cannot satisfy its assigned count.

    design-final.md §3 Stage 1, Codex TASK-PRE MEDIUM-2 ("プールが足りない
    物体の扱いを明示凍結する。無音で減らさない"): sorted for determinism.
    Structural -- depends only on pool sizes vs. the per-object assigned
    count, so it is identical for every replicate one
    :func:`internal_shaped_replicates` call produces.
    """
    short = [
        obj
        for obj, pool in contexts.items()
        if len(pool.common_item_indices) < 1
        or len(pool.good_item_indices) < good_counts[obj]
    ]
    return tuple(sorted(short))


@dataclasses.dataclass(frozen=True, slots=True)
class GoldSubset:
    """One Stage 1 replicate's internal-shaped item-index subset.

    design-final.md §3 Stage 1. This issue's own contract:
    ``item_indices`` are positions into the same shared item ordering
    :class:`ObjectGoldPool`'s pools index into -- exactly one "common"
    index per active object plus that object's cyclically assigned
    :data:`STAGE1_INTERNAL_GOOD_COUNTS` share of "good" indices (fewer,
    for a :data:`pool_short_objects` member), drawn seeded-without-
    replacement by :func:`internal_shaped_replicates`. ``pool_short_
    objects`` is structural (the same every replicate one ``internal_
    shaped_replicates`` call produces, because it only depends on pool
    sizes vs. the assigned per-object count, never on which items were
    drawn) -- :func:`stage1_drop_distribution` reads it once, off the
    first replicate, to populate :class:`Stage1Result`.
    """

    replicate_index: int
    item_indices: tuple[int, ...]
    pool_short_objects: tuple[str, ...]


def internal_shaped_replicates(
    contexts: Mapping[str, ObjectGoldPool],
    *,
    replicates: int,
    corpus: str,
    scheme: str,
    seed: int,
) -> list[GoldSubset]:
    """Shrink an external gold pool to the internal C0 shape (this issue's Goal).

    design-final.md §3 Stage 1: "Ocsai の gold を内部と同じ形へ縮小: 物体
    あたり common 1 件 + good は... 巡回割当した件数だけ seeded 復元なし
    抽出". Each of ``replicates`` independently draws (without replacement
    *within* that replicate only -- resampling *across* replicates is what
    makes this a bootstrap-style distribution) exactly one common index and
    that object's assigned share of good indices from every active object
    in :func:`_stage1_object_order`, via the frozen
    :func:`~scripts.paper01_external_audit.anchor_draw_indices` -- never a
    hand-rolled RNG call (AC 004-4's spy checks this).

    **Anchor (Codex HIGH-5 / DA-SC-12, outcome-independence)**: every draw
    passes ``draw_index=`` :data:`STAGE1_DRAW_INDEX` literally, never a
    value derived from an observed statistic (e.g. the superseded
    "median-by-drop draw", DA-SC-6) -- only ``seed`` (folded per replicate/
    object/good-or-common via :func:`_stage1_seed`) varies the draw, so the
    anchor choice itself can never depend on outcome.

    An object short of its assigned count (either pool) still gets a
    best-effort draw of whatever is available (never raises, never
    silently vanishes from the replicate) and is recorded in every
    returned :class:`GoldSubset`'s ``pool_short_objects``
    (:func:`_stage1_pool_short_objects`) -- "無音で減らさない".
    """
    order = _stage1_object_order(contexts)
    good_counts = _stage1_good_counts(contexts)
    pool_short_objects = _stage1_pool_short_objects(contexts, good_counts)

    out: list[GoldSubset] = []
    for r in range(replicates):
        item_indices: list[int] = []
        for obj in order:
            pool = contexts[obj]
            need_good = min(good_counts[obj], len(pool.good_item_indices))
            need_common = min(1, len(pool.common_item_indices))

            if need_good > 0:
                good_seed = _stage1_seed(seed, corpus, scheme, r, obj, "good")
                drawn_good = _g1.anchor_draw_indices(
                    len(pool.good_item_indices),
                    need_good,
                    seed=good_seed,
                    draw_index=STAGE1_DRAW_INDEX,
                )
                item_indices.extend(
                    pool.good_item_indices[i] for i in drawn_good.tolist()
                )

            if need_common > 0:
                common_seed = _stage1_seed(seed, corpus, scheme, r, obj, "common")
                drawn_common = _g1.anchor_draw_indices(
                    len(pool.common_item_indices),
                    need_common,
                    seed=common_seed,
                    draw_index=STAGE1_DRAW_INDEX,
                )
                item_indices.extend(
                    pool.common_item_indices[i] for i in drawn_common.tolist()
                )

        out.append(
            GoldSubset(
                replicate_index=r,
                item_indices=tuple(item_indices),
                pool_short_objects=pool_short_objects,
            )
        )
    return out


def same_object_pair_share(counts_by_object: Mapping[str, tuple[int, int]]) -> float:
    """Diagnostic (AC 004-2): same-object share of every pooled good x common pair.

    design-final.md §3 Stage 1 shrinks Ocsai to "物体あたり common 1 件" --
    ``counts_by_object`` maps each active object to its own ``(n_good,
    n_common)`` pair count. If every good item were pooled against every
    common item *across* objects (a flat cross-product, never what
    :func:`~scripts.paper01_external_audit.auc_stratified` itself computes
    -- that function never forms cross-object pairs at all), the fraction
    that happen to share an object is ``sum(n_good*n_common per object) /
    (total_good * total_common)``. With exactly one common item per object
    this reduces to ``1 / n_active_objects`` regardless of the good counts,
    the same structural reason the sealed internal C0 gold (16 objects, one
    common category slot's worth of weight per object) reports 6.25% =
    1/16 -- this function never hardcodes that reduction, only the raw
    pair-counting definition, so a shape that stops being "one common per
    object" would show up here as a genuine divergence.
    """
    same = sum(n_good * n_common for n_good, n_common in counts_by_object.values())
    total_good = sum(n_good for n_good, _ in counts_by_object.values())
    total_common = sum(n_common for _, n_common in counts_by_object.values())
    total = total_good * total_common
    if total == 0:
        return 0.0
    return same / total


def _stage1_auc_unweighted_by_object(
    scores: list[float], labels: list[int], objects: list[str]
) -> float:
    """Layer-stratified (object-unweighted) AUC -- the §3 Stage 1 "副" statistic.

    design-final.md §3 Stage 1: "統計量は内部と同じ pooled AUC を主、層別を
    副として両方出す". Unlike
    :func:`~scripts.paper01_external_audit.auc_stratified` (the *primary*
    statistic, weighted by each object's ``n_good * n_common``), this is
    the plain unweighted mean of every active object's own within-object
    AUC -- computed by the frozen
    :func:`~scripts.paper01_external_audit.controls.auc` (never
    reimplemented), mirroring :func:`~scripts.paper01_scope_condition.
    corpus_redundancy`'s "物体重みで加重しない" discipline (design-final.md
    §2.1) so this secondary/diagnostic figure cannot be dominated by a
    single high-weight object the way the primary pooled statistic can be
    (design-final.md §8 Limitations, the Ocsai brick-weight-concentration
    diagnostic). Returns ``0.5`` (uninformative, matching ``controls.auc``'s
    own single-class convention) when no object clears both class minimums.
    """
    scores_arr = np.asarray(scores, dtype=float)
    labels_arr = np.asarray(labels, dtype=int)
    objects_arr = np.asarray(objects, dtype=object)

    per_object_aucs: list[float] = []
    for obj in dict.fromkeys(objects_arr.tolist()):
        mask = objects_arr == obj
        obj_labels = labels_arr[mask]
        if (obj_labels == 1).sum() == 0 or (obj_labels == 0).sum() == 0:
            continue
        per_object_aucs.append(
            _g1.controls.auc(scores_arr[mask].tolist(), obj_labels.tolist())
        )
    if not per_object_aucs:
        return 0.5
    return float(sum(per_object_aucs) / len(per_object_aucs))


def stage1_outcome(
    band: tuple[float, float], reference_drop: float, eligible_fraction: float
) -> str:
    """§3 Stage 1 three-state verdict (Codex TASK-PRE HIGH-3 / DA-SC-19).

    This issue's core. Total over its whole declared input space -- always
    one of :data:`STAGE1_OUTCOME_ENUM`, never raises.

    design-final.md:165's frozen table, in this priority order:

    1. ``eligible_fraction <=`` :data:`_STAGE1_ELIGIBLE_FRACTION_FLOOR` ->
       ``"INCONCLUSIVE"`` ("X0 が replicate の過半で eligible でない" ->
       "判定不能"). Checked *first* and unconditionally: an ineligible
       majority makes the band untrustworthy regardless of what it
       contains, so this branch must never be reachable only when the band
       check below happens to disagree.
    2. Otherwise, ``band`` (``(drop_p5, drop_p95)``) containing
       ``reference_drop`` on a **closed** interval (Codex TASK-PRE
       MEDIUM-3: a boundary-equal ``reference_drop`` counts as *inside* --
       ``"DEFLATION_SUPPORTED"``, frozen and pinned by a boundary test) ->
       ``"DEFLATION_SUPPORTED"``.
    3. Otherwise -> ``"DEFLATION_REJECTED"``.

    **``"INCONCLUSIVE"`` is never folded into ``"DEFLATION_REJECTED"``**
    (this issue's Background: folding would silently move
    design-final.md:251's exit table onto the "書く" branch) -- the three
    branches above are mutually exclusive and jointly exhaustive by
    construction (an ``if``/``elif``/``else`` chain, never a set of
    independent booleans that could all be false).
    """
    if eligible_fraction <= _STAGE1_ELIGIBLE_FRACTION_FLOOR:
        return "INCONCLUSIVE"
    band_low, band_high = band
    if band_low <= reference_drop <= band_high:
        return "DEFLATION_SUPPORTED"
    return "DEFLATION_REJECTED"


def stage1_deflation_supported(
    band: tuple[float, float], reference_drop: float, eligible_fraction: float
) -> bool:
    """Derived mirror of ``stage1_outcome(...) == "DEFLATION_SUPPORTED"``.

    design-final.md §3 Stage 1 / Codex TASK-PRE HIGH-3: never re-derives the
    condition independently -- a single source of truth for "is deflation
    supported" so the two can never silently drift apart.
    """
    return (
        stage1_outcome(band, reference_drop, eligible_fraction) == "DEFLATION_SUPPORTED"
    )


def stage1_drop_distribution(
    draw_items: _g1.DrawItems,
    subsets: list[GoldSubset],
    *,
    candidate: str,
    reference_drop: float = STAGE1_INTERNAL_DROP_REF,
) -> Stage1Result:
    """Aggregate §3 Stage 1 statistics over R seeded replicates (this issue's Goal).

    ``draw_items`` holds one candidate's full corpus item arrays
    (``scores_full`` / ``scores_lao`` / ``labels`` / ``objects``), already
    scored against the frozen :data:`STAGE1_DRAW_INDEX` anchor by the
    out-of-scope-for-I-004 adapter/encoder layer (lands in I-007) --
    this function only ever *subsets* those arrays by each
    :class:`GoldSubset.item_indices`, delegating every AUC computation to
    the frozen :func:`~scripts.paper01_external_audit.auc_stratified`
    (pooled, primary) / :func:`_stage1_auc_unweighted_by_object`
    (layer-stratified, secondary/"副") -- never reimplementing either
    (AC 004-6: passing a single subset covering *every* item must reproduce
    exactly what calling ``auc_stratified`` directly on the same arrays
    gives).

    Eligibility (``eligible_fraction``, per-replicate) reuses the frozen
    :func:`~scripts.paper01_external_audit.is_draw_eligible` (``AUC_strat
    (full) >= AUC_FLOOR``, floor read through
    ``erre_sandbox.evidence.es4_actuator.constants`` inside that call, live
    -- never cached here). The eligible-limited band
    (``drop_p5_eligible``/``drop_p95_eligible``/``median_drop_eligible``,
    design-final.md:165's "副" remedy row) falls back to the pooled band
    when *no* replicate is eligible, rather than raising -- that
    degenerate case is already what routes :func:`stage1_outcome` to
    ``"INCONCLUSIVE"`` via ``eligible_fraction == 0.0``, so the fallback
    value is never read as a trustworthy band.

    The median-by-drop-draw sensitivity (``median_draw_drop`` /
    ``median_draw_outcome``, DA-SC-6/DA-SC-12) is computed from the frozen
    :func:`~scripts.paper01_external_audit.median_draw_index` (never
    reimplemented) applied to *this candidate's* R replicate drops --
    entirely independent of the primary ``band``/``stage1_outcome`` above,
    so it can never feed the primary verdict (AC 004-5).
    """
    if not subsets:
        msg = "stage1_drop_distribution requires at least one replicate subset"
        raise ValueError(msg)

    scores_full = np.asarray(draw_items.scores_full, dtype=float)
    scores_lao = np.asarray(draw_items.scores_lao, dtype=float)
    labels = np.asarray(draw_items.labels, dtype=int)
    objects = np.asarray(draw_items.objects, dtype=object)

    drops_pooled: list[float] = []
    drops_strat: list[float] = []
    eligible_flags: list[bool] = []

    for subset in subsets:
        idx = np.asarray(subset.item_indices, dtype=int)
        sub_labels = labels[idx].tolist()
        sub_objects = objects[idx].tolist()

        auc_full = _g1.auc_stratified(
            scores_full[idx].tolist(), sub_labels, sub_objects
        )
        auc_lao = _g1.auc_stratified(scores_lao[idx].tolist(), sub_labels, sub_objects)
        drops_pooled.append(auc_full - auc_lao)
        eligible_flags.append(_g1.is_draw_eligible(auc_full))

        strat_full = _stage1_auc_unweighted_by_object(
            scores_full[idx].tolist(), sub_labels, sub_objects
        )
        strat_lao = _stage1_auc_unweighted_by_object(
            scores_lao[idx].tolist(), sub_labels, sub_objects
        )
        drops_strat.append(strat_full - strat_lao)

    drops_arr = np.asarray(drops_pooled, dtype=float)
    strat_arr = np.asarray(drops_strat, dtype=float)
    eligible_arr = np.asarray(eligible_flags, dtype=bool)

    drop_p5 = float(np.percentile(drops_arr, 5))
    drop_p95 = float(np.percentile(drops_arr, 95))
    median_drop = float(np.median(drops_arr))
    eligible_fraction = float(eligible_arr.mean())

    if eligible_arr.any():
        eligible_drops = drops_arr[eligible_arr]
        drop_p5_eligible = float(np.percentile(eligible_drops, 5))
        drop_p95_eligible = float(np.percentile(eligible_drops, 95))
        median_drop_eligible = float(np.median(eligible_drops))
    else:
        drop_p5_eligible = drop_p5
        drop_p95_eligible = drop_p95
        median_drop_eligible = median_drop

    drop_p5_strat = float(np.percentile(strat_arr, 5))
    drop_p95_strat = float(np.percentile(strat_arr, 95))
    median_drop_strat = float(np.median(strat_arr))

    band = (drop_p5, drop_p95)
    outcome = stage1_outcome(band, reference_drop, eligible_fraction)
    supported = stage1_deflation_supported(band, reference_drop, eligible_fraction)

    median_idx = _g1.median_draw_index(drops_pooled)
    median_draw_drop = float(drops_pooled[median_idx])
    median_draw_eligible_fraction = 1.0 if eligible_flags[median_idx] else 0.0
    median_draw_outcome = stage1_outcome(
        (median_draw_drop, median_draw_drop),
        reference_drop,
        median_draw_eligible_fraction,
    )

    pool_short_objects = subsets[0].pool_short_objects

    return Stage1Result(
        candidate=candidate,
        n_replicates=len(subsets),
        drop_p5=drop_p5,
        drop_p95=drop_p95,
        median_drop=median_drop,
        eligible_fraction=eligible_fraction,
        deflation_supported=supported,
        stage1_outcome=outcome,
        drop_p5_eligible=drop_p5_eligible,
        drop_p95_eligible=drop_p95_eligible,
        median_drop_eligible=median_drop_eligible,
        drop_p5_strat=drop_p5_strat,
        drop_p95_strat=drop_p95_strat,
        median_drop_strat=median_drop_strat,
        n_objects_pool_short=len(pool_short_objects),
        pool_short_objects=pool_short_objects,
        median_draw_drop=median_draw_drop,
        median_draw_outcome=median_draw_outcome,
    )


# ---------------------------------------------------------------------------
# I-005: decision rule -- decide_scope()
# ---------------------------------------------------------------------------

_STAGE0_INTERNAL_SOURCE: Final[str] = "internal_c4"
_STAGE0_INTERNAL_CANDIDATE: Final[str] = "C4"
_STAGE0_EXTERNAL_SOURCE: Final[str] = "external_ocsai_arm_a"
_STAGE0_EXTERNAL_CANDIDATE: Final[str] = "X0"
"""design-final.md §2.3/§3 Stage 0 basis this issue's F4 / T-confound checks
read: the *primary* internal reference geometry is C4-raw ("実際に崩落した
スコアラが見た参照集合", §2.3), matched against the external primary
candidate X0 (Ocsai's ARM-A, "内部 incumbent と同じ encoder", §3 Stage 1).
Neither §1 nor §4 pins a scalar Delta_int/Delta_ext formula beyond the
:data:`DELTA_MATERIAL_EPS` threshold itself -- this (source, candidate)
pairing and the good/common averaging in :func:`_stage0_t_s_delta` below are
I-005's own documented reading of that gap, not a restatement of a frozen
number."""

_F2_OBJECT_LOSS_RATIO: Final[float] = 0.5
"""§4 F2 threshold: "τ* 適用後の4セル共通active物体が ARM-A active の
半数未満" -- a named constant instead of an inline literal so the F2
predicate below never compares against a bare magic number."""

_F1_TO_F6: Final[tuple[str, ...]] = ("F1", "F2", "F3", "F4", "F5", "F6")
"""§3 condition 4 ("F1-F6 のいずれにも該当しない"): deliberately excludes
F7 -- the single-point-dependence check is already condition 3
(``both_splits_robust`` below), never double-counted here."""


@dataclasses.dataclass(frozen=True, slots=True)
class SplitCells:
    """One Ocsai split scheme's Stage 2 wiring, bundled for :func:`decide_scope`.

    Plumbing introduced by I-005 to carry one split's ARM-A / ARM-S
    :class:`CellResult` verdicts and I-006's :class:`TauCalibration` (whose
    ``single_point_dependent`` is the §2.4 MEDIUM-3 robustness check --
    condition 3 / F7) through a single positional argument. This is *not*
    new verdict vocabulary (DA-SC-17 constrains :class:`ScopeVerdict`'s field
    names, not :func:`decide_scope`'s private input shape) -- every field
    here is an instance of one of the six already-frozen dataclasses.
    """

    arm_a: CellResult
    arm_s: CellResult
    tau_calibration: TauCalibration


def _stage0_row(
    stage0: tuple[DeltaDecomposition, ...], *, source: str, candidate: str
) -> DeltaDecomposition | None:
    """First :class:`DeltaDecomposition` matching ``(source, candidate)``.

    Returns ``None`` if Stage 0 never reported that pair.
    """
    for row in stage0:
        if row.source == source and row.candidate == candidate:
            return row
    return None


def _stage0_t_s_delta(
    stage0: tuple[DeltaDecomposition, ...], *, source: str, candidate: str
) -> tuple[float, float, float]:
    """``(T, S, Delta)`` for one Stage 0 row, averaged across good/common.

    A missing row defaults to ``(0.0, 0.0, 0.0)`` -- **fail-closed** in the
    same direction DA-SC-19 chose for Stage 1's three-state amendment:
    absent Stage 0 data reads as "no material difference" (§4 F4) and "not
    T-driven" rather than raising, so :func:`decide_scope` stays total over
    this issue's whole input space (AC 005-1) instead of only the cases a
    caller happened to populate.
    """
    row = _stage0_row(stage0, source=source, candidate=candidate)
    if row is None:
        return 0.0, 0.0, 0.0
    t = (row.mean_t_good + row.mean_t_common) / 2.0
    s = (row.mean_s_good + row.mean_s_common) / 2.0
    delta = (row.mean_delta_good + row.mean_delta_common) / 2.0
    return t, s, delta


def decide_scope(
    stage0: tuple[DeltaDecomposition, ...],
    stage1: Stage1Result,
    cells: Mapping[str, SplitCells],
    *,
    cambridge: CellResult,
) -> ScopeVerdict:
    """§3-§5 total, deterministic scope verdict (this issue's Goal).

    ``cells`` maps each Ocsai split-scheme key ("SPLIT-BLOCK" /
    "SPLIT-PARITY", :data:`scripts.paper01_external_audit.SPLIT_SCHEMES`) to
    that split's :class:`SplitCells`; ``cambridge`` is the single Cambridge
    ARM-S :class:`CellResult` design-final.md §4 F5 reads (Cambridge
    contributes no ARM-A comparison -- it is report-only + non-contradiction
    only, §0 / §8 item 7).

    **Never derives the right to write from ``not
    stage1.deflation_supported``** (this issue's core, Codex TASK-PRE HIGH-3
    / DA-SC-19): the write gate below reads only
    ``stage1.stage1_outcome == "DEFLATION_REJECTED"``, so an
    ``"INCONCLUSIVE"`` Stage 1 -- which also has ``deflation_supported ==
    False`` -- can never produce ``"WRITE"``.

    ``condition_c_supported`` is the raw §3 four-condition conjunction,
    computed independently of Stage 1 (never re-derived from ``fail_reason``
    or from Stage 1's outcome) -- a deflation-supported Stage 1 forces
    ``verdict == "DO_NOT_WRITE"`` (§4: "Stage 1 が deflation を支持した場合
    は、Stage 2 の結果に関わらず「書かない」枝が確定する") without
    retroactively flipping ``condition_c_supported`` itself, so
    ``test_deflation_overrides_stage2`` (AC 005-5) can observe the two
    fields disagree.
    """
    cond1_by_split: dict[str, bool] = {
        split_key: (
            split_cells.arm_s.verdict == "NO_VALID_SCORER"
            and split_cells.arm_a.verdict == "PASS"
        )
        for split_key, split_cells in cells.items()
    }
    # Codex TASK-POST MEDIUM-1 (fail-closed): design-final.md §3 Stage 2 condition 2
    # requires *both* Ocsai splits. ``cli_scope()`` already exits 1 when one is
    # missing, but the verdict function must not depend on its caller for that --
    # a hand-assembled ``cells`` holding only one split would otherwise satisfy
    # ``all(...)`` vacuously and read as "both splits agree".
    # Membership is checked against the frozen scheme list, never a literal here.
    required_splits = {scheme.key for scheme in _g1.SPLIT_SCHEMES}
    all_splits_present = set(cond1_by_split) == required_splits
    both_splits_supported = all_splits_present and all(cond1_by_split.values())
    split_disagreement = len(set(cond1_by_split.values())) > 1

    robust_by_split: dict[str, bool] = {
        split_key: not split_cells.tau_calibration.single_point_dependent
        for split_key, split_cells in cells.items()
    }
    both_splits_robust = bool(robust_by_split) and all(robust_by_split.values())
    single_point_dependent = any(
        cond1_by_split.get(split_key, False) and not is_robust
        for split_key, is_robust in robust_by_split.items()
    )

    rho_unreachable = any(
        bool(split_cells.tau_calibration.rho_by_tau)
        and split_cells.tau_calibration.rho_by_tau[-1]
        > split_cells.tau_calibration.rho_int_primary
        for split_cells in cells.values()
    )
    object_loss = any(
        len(split_cells.arm_s.active_objects)
        < len(split_cells.arm_a.active_objects) * _F2_OBJECT_LOSS_RATIO
        for split_cells in cells.values()
    )
    audit_inactive = any(
        split_cells.arm_s.verdict == "INVALID_TASK_BATTERY"
        for split_cells in cells.values()
    )
    cambridge_contradiction = cambridge.verdict == "PASS"

    t_int, s_int, delta_int = _stage0_t_s_delta(
        stage0,
        source=_STAGE0_INTERNAL_SOURCE,
        candidate=_STAGE0_INTERNAL_CANDIDATE,
    )
    t_ext, s_ext, delta_ext = _stage0_t_s_delta(
        stage0,
        source=_STAGE0_EXTERNAL_SOURCE,
        candidate=_STAGE0_EXTERNAL_CANDIDATE,
    )
    # Opus TASK-POST MEDIUM-2: single source of truth for the F4 boundary --
    # never re-derive ``abs(...) < DELTA_MATERIAL_EPS`` inline, so a change to
    # the boundary semantics propagates here too.
    no_material_delta = not delta_is_material(delta_int, delta_ext)
    t_driven = abs(t_int - t_ext) > abs(s_int - s_ext)

    fail_flags: dict[str, bool] = {
        "F1": rho_unreachable,
        "F2": object_loss,
        "F3": audit_inactive,
        "F4": no_material_delta,
        "F5": cambridge_contradiction,
        "F6": split_disagreement,
        "F7": single_point_dependent,
    }
    fail_reason = next((f for f in FAIL_PRECEDENCE if fail_flags[f]), None)

    condition_c_supported = (
        both_splits_supported
        and both_splits_robust
        and not any(fail_flags[f] for f in _F1_TO_F6)
    )

    write_eligible = stage1.stage1_outcome == "DEFLATION_REJECTED"
    verdict = "WRITE" if (write_eligible and condition_c_supported) else "DO_NOT_WRITE"

    t_confound_note_required = t_driven and condition_c_supported

    notes: tuple[str, ...] = (
        (f"primary fail branch: {fail_reason}",) if fail_reason is not None else ()
    )

    return ScopeVerdict(
        verdict=verdict,
        deflation_supported=stage1.deflation_supported,
        condition_c_supported=condition_c_supported,
        single_point_dependent=single_point_dependent,
        fail_reason=fail_reason,
        notes=notes,
        t_confound_note_required=t_confound_note_required,
    )


# ---------------------------------------------------------------------------
# I-006: tau* calibration / cell wiring / CLI
# ---------------------------------------------------------------------------


# --- CellAnchors: one AUT object's leader-clustered draws (I-006 internal) -


@dataclasses.dataclass(frozen=True, slots=True)
class CellAnchors:
    """One AUT object's ``(tau, k)`` cell anchor draws -- pre-scoring geometry.

    I-006's own internal type (not one of the six I-001-frozen contracts;
    Codex TASK-PRE LOW-2 permits this since I-007 only ever reads the
    on-disk ``results/scope.json`` shape :func:`run_scope` freezes below,
    never this in-process dataclass). :func:`build_cell` produces one of
    these per ``(object, tau, k)`` before any
    :func:`~scripts.paper01_external_audit.decide_external` scoring
    happens; :func:`score_cell` (also I-006) turns a *mapping* of these
    (one per active object) into the frozen :class:`CellResult`.

    ``draw_texts_by_draw`` has length
    :data:`scripts.paper01_external_audit.ANCHOR_DRAWS` -- entry ``b`` is
    the texts :func:`~scripts.paper01_external_audit.anchor_draw_indices`
    drew for ``draw_index=b``. **Fidelity pin (b)**: at ``tau=REF_DEDUP,
    cap=N_R_MAX`` this is index-for-index identical to what
    :func:`~scripts.paper01_external_audit.arm_a_draw_texts` returns when
    called once per ``b`` (``test_cell_pipeline_order_is_dedupe_then_cap_
    then_draw`` pins the geometry; ``test_dense_cell_reproduces_g1_arm_a``
    pins the scored result this feeds).
    """

    object_key: str
    tau: float
    k_target: int
    k_effective: int
    n_pool: int
    n_leaders: int
    draw_texts_by_draw: tuple[tuple[str, ...], ...]


def build_cell(
    ctx: _g1.ObjectSplitContext,
    pool_embeddings: Mapping[str, np.ndarray],
    *,
    tau: float,
    cap: int,
    corpus: str,
    scheme: str,
) -> CellAnchors:
    """design-final.md §3 Stage 2's frozen per-object cell pipeline.

    This issue's Goal (Codex HIGH-4). ``ctx`` is one
    :class:`scripts.paper01_external_audit.ObjectSplitContext` (reused,
    never rebuilt -- ``ctx.common_pool`` is the *raw*, un-deduped split0
    gold-common pool in frozen scan order).

    **Pipeline order (AC 006-2, spy-pinned, never reordered)**:

    1. ``pool`` = ``ctx.common_pool`` -- raw, **not** ``ctx.dedup_common_
       pool`` (that is already deduped at the fixed ``REF_DEDUP``, not this
       cell's own ``tau``).
    2. ``leaders`` = :func:`leader_cluster_indices` at ``radius=tau,
       cap=len(pool)`` -- **uncapped** (dedupe first, at the whole pool's
       size, never at ``cap``).
    3. ``k_eff`` = ``min(cap, len(leaders))`` -- capped only *after* step 2.
    4. ``draws`` -- one
       :func:`~scripts.paper01_external_audit.anchor_draw_indices` call per
       ``b in range(scripts.paper01_external_audit.ANCHOR_DRAWS)``, seeded
       via ``_g1.derive_seed(corpus, ctx.object_key, scheme, "ARM-A")`` --
       the **same** seed tag
       :func:`~scripts.paper01_external_audit.arm_a_draw_texts` uses,
       literally, for *every* cell (this generalises ARM-A's own recipe
       rather than forking it -- what makes fidelity pin (b) an exact
       reduction at ``tau=REF_DEDUP, cap=N_R_MAX`` instead of a
       coincidence).

    ``pool_embeddings`` maps each pool text to its unit-normalised
    embedding (the caller's own ``vmap``) -- this function performs no
    embedding of its own.

    An empty ``ctx.common_pool`` (or a ``0``-``k_eff`` cell) reports
    ``draw_texts_by_draw`` as :data:`~scripts.paper01_external_audit.
    ANCHOR_DRAWS` empty tuples, mirroring
    :func:`~scripts.paper01_external_audit.arm_a_draw_texts`'s own
    ``k == 0`` short-circuit (never raises).
    """
    pool = ctx.common_pool
    n_pool = len(pool)
    if n_pool == 0:
        return CellAnchors(
            object_key=ctx.object_key,
            tau=tau,
            k_target=cap,
            k_effective=0,
            n_pool=0,
            n_leaders=0,
            draw_texts_by_draw=tuple(() for _ in range(_g1.ANCHOR_DRAWS)),
        )

    emb = np.asarray([pool_embeddings[r.text] for r in pool], dtype=float)
    leader_idx = leader_cluster_indices(emb, radius=tau, cap=n_pool)
    leaders = tuple(pool[i] for i in leader_idx)
    n_leaders = len(leaders)
    k_eff = min(cap, n_leaders)

    if k_eff == 0:
        draws: tuple[tuple[str, ...], ...] = tuple(() for _ in range(_g1.ANCHOR_DRAWS))
    else:
        seed = _g1.derive_seed(corpus, ctx.object_key, scheme, "ARM-A")
        draws = tuple(
            tuple(
                leaders[i].text
                for i in _g1.anchor_draw_indices(
                    n_leaders, k_eff, seed=seed, draw_index=b
                ).tolist()
            )
            for b in range(_g1.ANCHOR_DRAWS)
        )

    return CellAnchors(
        object_key=ctx.object_key,
        tau=tau,
        k_target=cap,
        k_effective=k_eff,
        n_pool=n_pool,
        n_leaders=n_leaders,
        draw_texts_by_draw=draws,
    )


# --- InternalReference: rho_int / k* (Codex HIGH-1 / TASK-PRE HIGH-5) ------


def internal_reference_per_object(
    mpnet: Callable[[Sequence[str]], np.ndarray],
    *,
    run_dir: Path | None = None,
) -> tuple[InternalReference, ...]:
    """design-final.md §2.3: one :class:`InternalReference` row per AUT object.

    **Reuses (never rebuilds) the frozen fidelity-pin contexts** (this
    issue's Scope In): ``_g1._c4_fidelity_context(mpnet)`` for the
    *primary* basis (raw curated, un-deduped -- Codex HIGH-1: "実際に C4
    スコアラが見た集合") and ``_g1._c0_fidelity_context(mpnet, run_dir)`` for
    the mandatory *secondary* cross-check
    (``construct_all_references``'s dedup'd ``R_object``). Neither context
    is reconstructed here -- only its already-embedded ``vmap`` and
    per-object text lists are read.

    ``rho_primary_c4`` / ``rho_secondary_c0`` are each object's
    :func:`reference_redundancy` over its own reference embeddings (the
    *per-object* row :class:`InternalReference`'s own frozen docstring
    documents -- never the corpus-level :func:`corpus_redundancy`, which
    :func:`internal_rho_and_k` computes from *this* function's output
    instead). ``n_refs_primary_c4`` / ``n_refs_secondary_c0`` are the
    corresponding raw reference-set sizes (``|R_o|``).

    Raises :class:`FileNotFoundError` (propagated from
    ``_c0_fidelity_context``, never swallowed) when ``run_dir``'s sealed
    Phase A artifact is missing -- callers that only need the primary (C4)
    basis should catch this or use :func:`internal_reference_c4_only`.
    """
    run_dir = _g1.PHASE_A_RUN_DIR if run_dir is None else run_dir
    _, vmap_c4, curated = _g1._c4_fidelity_context(mpnet)  # noqa: SLF001
    _, vmap_c0, full_ref_texts = _g1._c0_fidelity_context(  # noqa: SLF001
        mpnet, run_dir
    )

    objects = sorted(set(curated) | set(full_ref_texts))
    out: list[InternalReference] = []
    for obj in objects:
        c4_texts = tuple(curated.get(obj, []))
        c0_texts = tuple(full_ref_texts.get(obj, []))
        c4_emb = np.asarray([vmap_c4[t] for t in c4_texts], dtype=float)
        c0_emb = np.asarray([vmap_c0[t] for t in c0_texts], dtype=float)
        out.append(
            InternalReference(
                object_id=obj,
                rho_primary_c4=reference_redundancy(c4_emb),
                rho_secondary_c0=reference_redundancy(c0_emb),
                n_refs_primary_c4=len(c4_texts),
                n_refs_secondary_c0=len(c0_texts),
            )
        )
    return tuple(out)


def internal_reference_c4_only(
    mpnet: Callable[[Sequence[str]], np.ndarray],
) -> tuple[InternalReference, ...]:
    """The primary-only (C4) half of :func:`internal_reference_per_object`.

    Never touches ``_c0_fidelity_context`` (so never raises
    :class:`FileNotFoundError` for a missing Phase A artifact) -- each row's
    ``rho_secondary_c0`` / ``n_refs_secondary_c0`` are the frozen ``0.0`` /
    ``0`` defaults :func:`reference_redundancy` itself uses for an empty
    reference set (design-final.md §2.1, Codex TASK-PRE LOW-1), never a
    fabricated non-zero value.
    """
    _, vmap_c4, curated = _g1._c4_fidelity_context(mpnet)  # noqa: SLF001
    out: list[InternalReference] = []
    for obj in sorted(curated):
        c4_texts = tuple(curated.get(obj, []))
        c4_emb = np.asarray([vmap_c4[t] for t in c4_texts], dtype=float)
        out.append(
            InternalReference(
                object_id=obj,
                rho_primary_c4=reference_redundancy(c4_emb),
                rho_secondary_c0=0.0,
                n_refs_primary_c4=len(c4_texts),
                n_refs_secondary_c0=0,
            )
        )
    return tuple(out)


def internal_rho_and_k(
    references: tuple[InternalReference, ...],
) -> tuple[float, float, int]:
    """design-final.md §2.1/§2.3/§2.4 corpus-level ``(rho_int, k_star)``.

    Aggregated from :func:`internal_reference_per_object`'s (or
    :func:`internal_reference_c4_only`'s) per-object rows.
    ``rho_int_primary`` / ``rho_int_secondary`` are each the **unweighted**
    mean of ``rho_primary_c4`` / ``rho_secondary_c0`` across every row
    (§2.1: "物体横断の単純平均 (物体重みで加重しない)"), mirroring
    :func:`corpus_redundancy`'s own convention exactly -- never re-derived
    with a different weighting here. ``k_star`` is the **median** of
    ``n_refs_primary_c4`` across every row (§2.4: "内部 C4 の物体あたり
    |R_o| の中央値").

    Pure aggregation -- no encoder, no I/O -- so it is exercised directly
    by ``test_rho_int_uses_raw_curated_not_deduped`` /
    ``test_rho_int_reports_both_bases`` without touching
    :func:`internal_reference_per_object`'s ``mpnet``-dependent half.

    Returns ``(0.0, 0.0, 0)`` for an empty ``references`` (fail-closed, the
    same convention :func:`_stage0_t_s_delta` uses for a missing row).
    """
    if not references:
        return 0.0, 0.0, 0
    rho_primary = float(sum(r.rho_primary_c4 for r in references) / len(references))
    rho_secondary = float(sum(r.rho_secondary_c0 for r in references) / len(references))
    k_star = int(np.median([r.n_refs_primary_c4 for r in references]))
    return rho_primary, rho_secondary, k_star


# --- tau* calibration (design-final.md §2.4, Codex MEDIUM-3) ---------------


def adjacent_tau_indices(tau_star_index: int) -> tuple[int, ...]:
    """The :data:`TAU_GRID` neighbour index/indices of ``tau_star_index``.

    design-final.md §2.4 MEDIUM-3's robustness check needs "τ* の隣接 1 段
    (上または下)". One neighbour at either grid edge, two in the interior
    (AC 006-7: never drops the sole neighbour at an edge, never reports a
    nonexistent one past it).
    """
    n = len(TAU_GRID)
    out: list[int] = []
    if tau_star_index > 0:
        out.append(tau_star_index - 1)
    if tau_star_index < n - 1:
        out.append(tau_star_index + 1)
    return tuple(out)


def calibrate_tau(
    rho_ext_by_tau: tuple[float, ...],
    rho_int_primary: float,
    *,
    k_star: int,
) -> TauCalibration:
    """design-final.md §2.4: ``tau* = argmin_tau |rho_ext(tau) - rho_int|``.

    Over the frozen :data:`TAU_GRID`, ties broken to the **larger** tau
    (Codex requirement, AC 006-5). ``rho_ext_by_tau`` must be index-aligned
    with :data:`TAU_GRID` (never a float-keyed mapping --
    :class:`TauCalibration`'s own frozen docstring); raises
    :class:`ValueError` otherwise (fail loud, never silently pad or
    truncate).

    ``single_point_dependent`` is returned ``False`` here -- this function
    is pure external-anchor-pool *geometry* and has no verdict to compare a
    neighbour against (design-final.md §2.4's robustness *check* needs each
    neighbour tau's *scored* :class:`~scripts.paper01_external_audit.
    ExternalVerdict`, which only exists after :func:`score_cell` runs on
    the neighbour(s) :func:`adjacent_tau_indices` names).
    :func:`run_scope`'s caller is what finalises this field, via
    ``dataclasses.replace``, once it has scored those neighbour cell(s).
    """
    if len(rho_ext_by_tau) != len(TAU_GRID):
        msg = (
            "calibrate_tau: rho_ext_by_tau must be index-aligned with "
            f"TAU_GRID (len {len(TAU_GRID)}), got len {len(rho_ext_by_tau)}"
        )
        raise ValueError(msg)

    best_index = 0
    best_gap = abs(rho_ext_by_tau[0] - rho_int_primary)
    for i in range(1, len(TAU_GRID)):
        gap = abs(rho_ext_by_tau[i] - rho_int_primary)
        # tie -> larger tau: TAU_GRID is descending, so a *strict* `<` here
        # (never `<=`) keeps the first (largest-tau) index seen on a tie.
        # mutation target: `<=` would flip the tie-break to the smaller tau.
        if gap < best_gap:
            best_gap = gap
            best_index = i

    tau_star = TAU_GRID[best_index]
    return TauCalibration(
        rho_int_primary=rho_int_primary,
        rho_by_tau=tuple(rho_ext_by_tau),
        tau_star=tau_star,
        k_star=k_star,
        single_point_dependent=False,
    )


def external_rho_by_tau(
    contexts: Mapping[str, _g1.ObjectSplitContext],
    pool_embeddings: Mapping[str, np.ndarray],
    active_objects: Sequence[str],
    *,
    tau_grid: tuple[float, ...] = TAU_GRID,
) -> tuple[float, ...]:
    """design-final.md §2.4: corpus-level ρ_ext(τ) for every τ in ``tau_grid``.

    The external anchor-pool geometry :func:`calibrate_tau` compares
    against ``rho_int_primary``. For each τ, each active object's
    ``ctx.common_pool`` is leader-
    clustered at that τ via the **same** :func:`leader_cluster_indices`
    :func:`build_cell` uses (never re-dedup'd through
    :func:`~scripts.paper01_external_audit.greedy_dedupe_indices`), and
    :func:`corpus_redundancy` is taken over the resulting per-object leader
    embeddings. ``contexts`` values are
    :class:`scripts.paper01_external_audit.ObjectSplitContext` instances.
    Index-aligned with ``tau_grid`` (never a float-keyed mapping, per
    :class:`TauCalibration`'s own frozen docstring).
    """
    out: list[float] = []
    for tau in tau_grid:
        by_object: dict[str, np.ndarray] = {}
        for obj in active_objects:
            pool = contexts[obj].common_pool
            if not pool:
                continue
            emb = np.asarray([pool_embeddings[r.text] for r in pool], dtype=float)
            leader_idx = leader_cluster_indices(emb, radius=tau, cap=len(pool))
            by_object[obj] = emb[np.asarray(leader_idx, dtype=int)]
        out.append(corpus_redundancy(by_object))
    return tuple(out)


# --- common active object intersection (DA-SC-3 / Codex MEDIUM-4) ----------


def active_objects_for_cell(
    cells_by_object: Mapping[str, CellAnchors],
) -> tuple[str, ...]:
    """design-final.md §3 Stage 2: the objects *this one cell* can score.

    ``n_leaders >= N_R_MIN`` (mirrors
    :attr:`~scripts.paper01_external_audit.ObjectSplitContext.dropped`'s
    own gate, generalised from the fixed ``REF_DEDUP`` pool size to this
    cell's own ``tau``-clustered ``n_leaders`` -- at ``tau=REF_DEDUP`` the
    two gates coincide exactly, since :func:`build_cell`'s ``n_leaders``
    there equals ``len(ctx.dedup_common_pool)``). Sorted for determinism.
    """
    return tuple(
        sorted(
            obj
            for obj, anchors in cells_by_object.items()
            if anchors.n_leaders >= _c.N_R_MIN
        )
    )


def common_active_objects(cells: Mapping[str, Sequence[str]]) -> list[str]:
    """design-final.md §3 Stage 2 DA-SC-3: intersection of every cell's active set.

    Codex MEDIUM-4: purely structural -- never looks at
    ``decide_external``'s verdict or object identity beyond set
    membership. ``cells`` maps a cell label (e.g. ``"tau=0.90,k=30"``) to that cell's
    own :func:`active_objects_for_cell` result. Returns ``[]`` for an empty
    ``cells`` mapping (fail-closed, never "everything is active" by a
    vacuous ``all()``) -- sorted for determinism.
    """
    if not cells:
        return []
    sets = [set(objs) for objs in cells.values()]
    common = set.intersection(*sets)
    return sorted(common)


# --- cell scoring: CellAnchors -> decide_external's CellResult -------------


def score_cell(
    cells_by_object: Mapping[str, CellAnchors],
    contexts: Mapping[str, _g1.ObjectSplitContext],
    active_objects: Sequence[str],
    vmaps: Mapping[str, Mapping[str, np.ndarray]],
    *,
    tau: float,
    k_target: int,
    corpus: str,
    scheme: str,
) -> CellResult:
    """design-final.md §3 Stage 2 step 5: score one already-built cell.

    Runs the frozen
    :func:`~scripts.paper01_external_audit.decide_external`.
    **``active_objects`` is a required, explicit parameter -- never
    recomputed from ``cells_by_object`` inside this function** (Codex
    MEDIUM-4 / AC 006-8): the caller (:func:`run_scope`'s upstream
    orchestration) is responsible for first computing
    :func:`common_active_objects` across all four cells of a split and
    passing *that* intersection here, so every cell of the same split is
    scored over the identical object set --
    ``test_all_cells_score_the_intersection`` spies
    ``scripts.paper01_external_audit.score_rows_for_draw``'s ``rows``
    argument to confirm this function never widens ``active_objects`` back
    out to its own ``cells_by_object`` keys.

    Delegates every statistic to the frozen apparatus -- one
    :func:`~scripts.paper01_external_audit.score_rows_for_draw` call per
    ``b in range(ANCHOR_DRAWS)``,
    :func:`~scripts.paper01_external_audit.build_candidate_report` per
    :data:`~scripts.paper01_external_audit.EMBEDDING_FAMILY_EXT` candidate,
    then :func:`~scripts.paper01_external_audit.decide_external` once --
    never reimplementing any of the three (this issue's Goal:
    **fidelity pin (b)** is exactly this function reducing to G1's own
    ARM-A wiring at ``tau=REF_DEDUP, k_target=N_R_MAX``).

    ``object_weights`` (LOW-2, mandatory) is each active object's
    :func:`~scripts.paper01_external_audit.object_class_weights`
    ``weight_share`` -- never recomputed by a different formula.
    """
    active = tuple(active_objects)
    rows = tuple(r for obj in active for r in contexts[obj].split1)
    class_sizes = _g1.cambridge_class_sizes([contexts[o] for o in active])
    idf_by_object = {o: (contexts[o].idf, contexts[o].default_idf) for o in active}

    draws_per_candidate: dict[str, list[_g1.DrawItems]] = {
        cand.key: [] for cand in _g1.CANDIDATE_LADDER
    }
    for b in range(_g1.ANCHOR_DRAWS):
        anchor_texts_by_object = {
            o: cells_by_object[o].draw_texts_by_draw[b] for o in active
        }
        scored = _g1.score_rows_for_draw(
            rows,
            anchor_texts_by_object=anchor_texts_by_object,
            vmaps=vmaps,
            idf_by_object=idf_by_object,
        )
        for key, items in scored.items():
            draws_per_candidate[key].append(items)

    reports: list[_g1.CandidateExternalReport] = []
    for cand in _g1.CANDIDATE_LADDER:
        if cand.key not in _g1.EMBEDDING_FAMILY_EXT:
            continue
        draws = draws_per_candidate.get(cand.key, [])
        if not draws:
            continue
        summary = _g1.build_candidate_report(
            cand.key,
            cand.family,
            draws,
            bootstrap_seed=_g1.derive_seed(corpus, scheme, cand.key, "bootstrap"),
            permutation_seed=_g1.derive_seed(corpus, scheme, cand.key, "permutation"),
        )
        reports.append(summary.report)

    verdict = _g1.decide_external(reports, class_sizes=class_sizes)

    weights_raw = _g1.object_class_weights([contexts[o] for o in active])
    object_weights = {o: float(weights_raw[o]["weight_share"]) for o in active}

    if active:
        n_leaders_median = int(
            np.median([cells_by_object[o].n_leaders for o in active])
        )
        k_eff_median = int(np.median([cells_by_object[o].k_effective for o in active]))
    else:
        n_leaders_median = 0
        k_eff_median = 0

    return CellResult(
        tau=tau,
        k_target=k_target,
        k_effective=k_eff_median,
        n_leaders=n_leaders_median,
        corpus=corpus,
        split_scheme=scheme,
        verdict=verdict.verdict,
        active_objects=tuple(sorted(active)),
        object_weights=object_weights,
    )


# --- run_scope(): Stage 0/1/2 assembly + results/scope.json ----------------


def run_scope(
    *,
    stage0: tuple[DeltaDecomposition, ...],
    stage1: Stage1Result,
    cells: Mapping[str, SplitCells],
    cambridge: CellResult,
    internal_references: tuple[InternalReference, ...],
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Assemble + write design-final.md §3's Stage 0/1/2 + ScopeVerdict.

    This issue's Goal: "``run_scope()`` -- Stage 0/1/2 を配線し
    results/scope.json を書く". **This is the assembly/serialisation half
    of Stage 0/1/2 wiring, not
    the encoder/data-fetch half** (issue 006 Scope Out: 実走・run.sh は
    I-007). Every argument here is already-computed -- ``stage0`` from
    :func:`split_delta` calls, ``stage1`` from
    :func:`stage1_drop_distribution`, ``cells`` / ``cambridge`` from
    :func:`score_cell` (fed by :func:`build_cell` /
    :func:`common_active_objects` / :func:`calibrate_tau`),
    ``internal_references`` from :func:`internal_reference_per_object`.
    This satisfies blockers.md ブロッカー 2's requirement: calling
    :func:`decide_scope` here (not re-implementing its logic) is what pins
    that I-003/I-004/I-006's *real* outputs -- not just hand-built test
    fixtures -- can flow through I-005's frozen ``cells``/``stage0``/
    ``stage1``/``cambridge`` shapes end to end.

    ``results/scope.json``'s **frozen on-disk shape** (I-007 reads this
    exactly; Codex TASK-PRE LOW-2/MEDIUM-4 confirmed here):

    .. code-block:: text

        {
          "stage0": [ {..DeltaDecomposition fields..}, ... ],
          "stage1": {..Stage1Result fields..},
          "stage2": {
            "cells": {split_key: {"arm_a": {..CellResult..},
                                   "arm_s": {..CellResult..},
                                   "tau_calibration": {..TauCalibration..}}},
            "cambridge": {..CellResult..},
            "internal_references": [ {..InternalReference..}, ... ]
          },
          "verdict": {..ScopeVerdict fields..}
        }

    Every float leaf is 6-decimal quantised via
    ``scripts.paper01_external_audit._quantize_json`` before writing
    (never a raw ``model_dump_json``-style embed --
    ``feedback_golden_crossplatform_float_drift``'s "projection 境界で
    再量子化必須"), and the file is written with ``sort_keys=True`` for a
    byte-identical two-run reproduction (design-final.md §7).
    """
    out_path = (RESULTS_DIR / "scope.json") if out_path is None else out_path

    verdict = decide_scope(stage0, stage1, cells, cambridge=cambridge)

    payload: dict[str, Any] = {
        "stage0": [dataclasses.asdict(row) for row in stage0],
        "stage1": dataclasses.asdict(stage1),
        "stage2": {
            "cells": {
                split_key: {
                    "arm_a": dataclasses.asdict(split_cells.arm_a),
                    "arm_s": dataclasses.asdict(split_cells.arm_s),
                    "tau_calibration": dataclasses.asdict(split_cells.tau_calibration),
                }
                for split_key, split_cells in cells.items()
            },
            "cambridge": dataclasses.asdict(cambridge),
            "internal_references": [
                dataclasses.asdict(ref) for ref in internal_references
            ],
        },
        "verdict": dataclasses.asdict(verdict),
    }
    quantized = _g1._quantize_json(payload)  # noqa: SLF001

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(quantized, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return quantized


# --- CLI (real-data actions; issue 006 TASK-PRE MEDIUM-4) -------------------


def _load_mpnet_or_none() -> Callable[[Sequence[str]], np.ndarray] | None:
    """Best-effort MPNet loader for the CLI actions below.

    ``None`` (never raises) when the model/extras are unavailable offline,
    mirroring :func:`~scripts.paper01_external_audit.run_fidelity`'s own
    guard.
    """
    return _diag.make_encoder("sentence-transformers/all-mpnet-base-v2")


@dataclasses.dataclass(frozen=True, slots=True)
class _OcsaiGather:
    """CLI-only, in-process bundle of one real Ocsai split's gathered inputs.

    Never written to disk, never a frozen §9 contract -- shared by the
    ``--stage0`` / ``--stage1`` / ``--stage2`` / ``--scope`` CLI actions
    below so the real network fetch + multi-encoder embedding pass happens
    once per invocation regardless of how many of those actions ran.
    """

    scheme: str
    contexts: Mapping[str, _g1.ObjectSplitContext]
    vmaps: Mapping[str, Mapping[str, np.ndarray]]
    encoders: Mapping[str, Callable[[Sequence[str]], np.ndarray]]
    active_objects: tuple[str, ...]


def _gather_ocsai(scheme: str) -> _OcsaiGather | None:
    """Best-effort real Ocsai fetch + multi-encoder embed for one split.

    ``None`` (never raises) when the network fetch or any pre-registered
    encoder is unavailable offline -- every CLI action below treats that as
    "cannot run for real here", reports ``source_unavailable``, and exits
    non-zero rather than writing a partial/misleading result (design-
    final.md §6's own "encoder が 1 つでも取得できなければ verdict を発行せず"
    discipline, generalised here to every real-data CLI action, not only
    ``decide_external``).
    """
    splits_data = _g1.load_ocsai_raw_bytes()
    if splits_data is None:
        return None
    try:
        encoders = _g1.build_available_encoders()
    except _g1.MissingEncoderError:
        return None

    rows = _g1.load_ocsai_rows(splits_data)
    rows_by_object = {
        obj: tuple(r for r in rows if r.object == obj)
        for obj in _g1.OCSAI_PRIMARY_OBJECTS
    }
    vmaps = _g1.embed_all_texts(rows_by_object, encoders)
    mpnet_vmap = vmaps.get("mpnet", {})
    contexts = {
        obj: _g1.build_object_split_context(
            obj, rows_by_object[obj], scheme, mpnet_vmap
        )
        for obj in _g1.OCSAI_PRIMARY_OBJECTS
    }
    active = tuple(
        sorted(
            obj
            for obj in _g1.OCSAI_PRIMARY_OBJECTS
            if not contexts[obj].dropped
            and _g1.object_has_both_gold_classes(contexts[obj])
        )
    )
    return _OcsaiGather(
        scheme=scheme,
        contexts=contexts,
        vmaps=vmaps,
        encoders=encoders,
        active_objects=active,
    )


def cli_calibrate(out_path: Path | None = None) -> int:
    """``--calibrate``: compute + write §2.3's internal ρ_int/k*.

    This issue's Scope In (``internal_rho_and_k`` /
    :class:`InternalReference` ownership, Codex TASK-PRE HIGH-5).
    Real end-to-end τ* calibration additionally needs a fetched external
    corpus (:func:`external_rho_by_tau`) -- that full cross-corpus assembly
    is ``--stage2`` below / ultimately I-007's ``run.sh`` (issue 006 Scope
    Out: 実走). This action computes and persists the *internal* half on
    its own, which needs only the sealed internal curated references + one
    encoder (never the Phase A generations -- uses
    :func:`internal_reference_c4_only`, never raises
    :class:`FileNotFoundError`).

    Returns ``1`` (never raises) when the encoder is unavailable offline.
    """
    out_path = (
        (RESULTS_DIR / "internal_reference.json") if out_path is None else out_path
    )
    mpnet = _load_mpnet_or_none()
    if mpnet is None:
        sys.stderr.write(
            "[paper01-scope] --calibrate: MPNet encoder unavailable offline\n"
        )
        return 1

    references = internal_reference_c4_only(mpnet)
    rho_primary, rho_secondary, k_star = internal_rho_and_k(references)
    payload = {
        "rho_int_primary": rho_primary,
        "rho_int_secondary": rho_secondary,
        "k_star": k_star,
        "references": [dataclasses.asdict(r) for r in references],
    }
    quantized = _g1._quantize_json(payload)  # noqa: SLF001
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(quantized, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(f"[paper01-scope] wrote {out_path}\n")
    return 0


def cli_stage2(out_path: Path | None = None) -> int:
    """``--stage2``: real Ocsai SPLIT-BLOCK ARM-A + ARM-S cells.

    Gathers Ocsai (:func:`_gather_ocsai`), the internal ρ_int/k* basis
    (:func:`internal_reference_c4_only` / :func:`internal_rho_and_k`), the
    external ρ_ext(τ) ladder (:func:`external_rho_by_tau`), calibrates τ*
    (:func:`calibrate_tau`), then builds + scores the ARM-A
    (``tau=REF_DEDUP, k=N_R_MAX``) and ARM-S (``tau=tau_star, k=k_star``)
    cells (:func:`build_cell` / :func:`score_cell`). Writes ``stage2.json``
    on success; on any missing prerequisite, writes
    ``{"status": "source_unavailable"}`` and returns ``1`` rather than a
    partial/misleading cell.
    """
    out_path = (RESULTS_DIR / "stage2.json") if out_path is None else out_path
    scheme = "SPLIT-BLOCK"
    corpus = "ocsai"

    gather = _gather_ocsai(scheme)
    mpnet = _load_mpnet_or_none()
    if gather is None or mpnet is None:
        _write_unavailable(out_path, stage="stage2")
        sys.stderr.write("[paper01-scope] --stage2: source unavailable\n")
        return 1

    references = internal_reference_c4_only(mpnet)
    rho_primary, _rho_secondary, k_star = internal_rho_and_k(references)
    rho_ext_by_tau = external_rho_by_tau(
        gather.contexts, gather.vmaps.get("mpnet", {}), gather.active_objects
    )
    tau_cal = calibrate_tau(rho_ext_by_tau, rho_primary, k_star=k_star)

    def _cell(tau: float, cap: int) -> CellResult:
        cells_by_object = {
            obj: build_cell(
                gather.contexts[obj],
                gather.vmaps.get("mpnet", {}),
                tau=tau,
                cap=cap,
                corpus=corpus,
                scheme=scheme,
            )
            for obj in gather.active_objects
        }
        active = active_objects_for_cell(cells_by_object)
        return score_cell(
            cells_by_object,
            gather.contexts,
            active,
            gather.vmaps,
            tau=tau,
            k_target=cap,
            corpus=corpus,
            scheme=scheme,
        )

    arm_a = _cell(_c.REF_DEDUP, _c.N_R_MAX)
    arm_s = _cell(tau_cal.tau_star, k_star)

    payload = {
        "arm_a": dataclasses.asdict(arm_a),
        "arm_s": dataclasses.asdict(arm_s),
        "tau_calibration": dataclasses.asdict(tau_cal),
    }
    quantized = _g1._quantize_json(payload)  # noqa: SLF001
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(quantized, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(f"[paper01-scope] wrote {out_path}\n")
    return 0


def cli_stage0(out_path: Path | None = None) -> int:
    """``--stage0``: real internal-C4-vs-external-Ocsai-ARM-A Δ rows.

    Internal row: :func:`~scripts.paper01_external_audit._c4_fidelity_
    context`'s candidate scored (``leave_anchor_out`` both ways) against
    the sealed 41-item internal gold pair (never re-embeds). External row:
    the gathered Ocsai ARM-A cell's ``draw_index=0`` anchor set (the same
    draw :data:`STAGE1_DRAW_INDEX` fixes for Stage 1, Codex HIGH-5's
    outcome-independence) scored via
    :func:`~scripts.paper01_external_audit.score_rows_for_draw`. Writes
    ``stage0.json`` (a 1-or-2-row list, never fabricating an absent row) on
    partial success; ``source_unavailable`` + exit 1 only when *neither*
    row could be computed.
    """
    out_path = (RESULTS_DIR / "stage0.json") if out_path is None else out_path
    rows: list[DeltaDecomposition] = []

    mpnet = _load_mpnet_or_none()
    if mpnet is not None:
        candidate, _vmap, curated = _g1._c4_fidelity_context(mpnet)  # noqa: SLF001
        gold_pair = _g1.fidelity_gold_pair()
        scores_full = tuple(
            candidate.rarity(g.object, g.text, leave_anchor_out=False)
            for g in gold_pair
        )
        scores_lao = tuple(
            candidate.rarity(g.object, g.text, leave_anchor_out=True) for g in gold_pair
        )
        labels = tuple(1 if g.category == "good" else 0 for g in gold_pair)
        max_sim_full = tuple(1.0 - s for s in scores_full)
        references = internal_reference_c4_only(mpnet)
        rho_primary, _rho_secondary, _k_star = internal_rho_and_k(references)
        rows.append(
            split_delta(
                scores_full,
                scores_lao,
                labels,
                max_sim_full,
                source=_STAGE0_INTERNAL_SOURCE,
                candidate=_STAGE0_INTERNAL_CANDIDATE,
                rho=rho_primary,
            )
        )
        del curated  # only vmap/candidate needed above

    scheme = "SPLIT-BLOCK"
    corpus = "ocsai"
    gather = _gather_ocsai(scheme)
    if gather is not None:
        cells_by_object = {
            obj: build_cell(
                gather.contexts[obj],
                gather.vmaps.get("mpnet", {}),
                tau=_c.REF_DEDUP,
                cap=_c.N_R_MAX,
                corpus=corpus,
                scheme=scheme,
            )
            for obj in gather.active_objects
        }
        active = active_objects_for_cell(cells_by_object)
        rows_all = tuple(r for obj in active for r in gather.contexts[obj].split1)
        idf_by_object = {
            o: (gather.contexts[o].idf, gather.contexts[o].default_idf) for o in active
        }
        anchor_texts_by_object = {
            o: cells_by_object[o].draw_texts_by_draw[STAGE1_DRAW_INDEX] for o in active
        }
        scored = _g1.score_rows_for_draw(
            rows_all,
            anchor_texts_by_object=anchor_texts_by_object,
            vmaps=gather.vmaps,
            idf_by_object=idf_by_object,
        )
        x0 = scored.get("X0")
        rho_ext = (
            corpus_redundancy(
                {
                    o: np.asarray(
                        [
                            gather.vmaps.get("mpnet", {})[t]
                            for t in anchor_texts_by_object[o]
                        ],
                        dtype=float,
                    )
                    for o in active
                    if anchor_texts_by_object[o]
                }
            )
            if active
            else 0.0
        )
        if x0 is not None:
            max_sim_full = tuple(1.0 - s for s in x0.scores_full)
            rows.append(
                split_delta(
                    x0.scores_full,
                    x0.scores_lao,
                    x0.labels,
                    max_sim_full,
                    source=_STAGE0_EXTERNAL_SOURCE,
                    candidate=_STAGE0_EXTERNAL_CANDIDATE,
                    rho=rho_ext,
                )
            )

    if not rows:
        _write_unavailable(out_path, stage="stage0")
        sys.stderr.write("[paper01-scope] --stage0: source unavailable\n")
        return 1

    payload = [dataclasses.asdict(row) for row in rows]
    quantized = _g1._quantize_json(payload)  # noqa: SLF001
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(quantized, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(f"[paper01-scope] wrote {out_path}\n")
    return 0


def cli_stage1(out_path: Path | None = None) -> int:
    """``--stage1``: real Ocsai-shrunk-to-internal-shape deflation test.

    Candidate X0 (design-final.md §3 Stage 1). Builds each active object's
    :class:`ObjectGoldPool` from the gathered
    Ocsai ``split1`` rows (good/common item indices into the same flat row
    ordering :func:`internal_shaped_replicates` draws from), then calls
    :func:`internal_shaped_replicates` (``STAGE1_REPLICATES`` seeded draws)
    and :func:`stage1_drop_distribution` against the ARM-A
    ``draw_index=STAGE1_DRAW_INDEX`` cell's scored :class:`DrawItems` for
    X0 -- never a hand-rolled resample, never a different anchor draw.
    Writes ``stage1.json`` on success; ``source_unavailable`` + exit 1
    otherwise.
    """
    out_path = (RESULTS_DIR / "stage1.json") if out_path is None else out_path
    scheme = "SPLIT-BLOCK"
    corpus = "ocsai"
    gather = _gather_ocsai(scheme)
    if gather is None:
        _write_unavailable(out_path, stage="stage1")
        sys.stderr.write("[paper01-scope] --stage1: source unavailable\n")
        return 1

    cells_by_object = {
        obj: build_cell(
            gather.contexts[obj],
            gather.vmaps.get("mpnet", {}),
            tau=_c.REF_DEDUP,
            cap=_c.N_R_MAX,
            corpus=corpus,
            scheme=scheme,
        )
        for obj in gather.active_objects
    }
    active = active_objects_for_cell(cells_by_object)
    if not active:
        _write_unavailable(out_path, stage="stage1")
        sys.stderr.write("[paper01-scope] --stage1: no active objects\n")
        return 1

    rows_all = tuple(r for obj in active for r in gather.contexts[obj].split1)
    idf_by_object = {
        o: (gather.contexts[o].idf, gather.contexts[o].default_idf) for o in active
    }
    anchor_texts_by_object = {
        o: cells_by_object[o].draw_texts_by_draw[STAGE1_DRAW_INDEX] for o in active
    }
    scored = _g1.score_rows_for_draw(
        rows_all,
        anchor_texts_by_object=anchor_texts_by_object,
        vmaps=gather.vmaps,
        idf_by_object=idf_by_object,
    )
    x0 = scored.get("X0")
    if x0 is None:
        _write_unavailable(out_path, stage="stage1")
        sys.stderr.write("[paper01-scope] --stage1: X0 unavailable\n")
        return 1

    offset = 0
    contexts_pools: dict[str, ObjectGoldPool] = {}
    for obj in active:
        n = len(gather.contexts[obj].split1)
        good_idx = tuple(
            offset + i
            for i, r in enumerate(gather.contexts[obj].split1)
            if r.category == "good"
        )
        common_idx = tuple(
            offset + i
            for i, r in enumerate(gather.contexts[obj].split1)
            if r.category == "common_use_only"
        )
        contexts_pools[obj] = ObjectGoldPool(
            object_key=obj,
            object_weight=float(len(good_idx) * len(common_idx)),
            good_item_indices=good_idx,
            common_item_indices=common_idx,
        )
        offset += n

    subsets = internal_shaped_replicates(
        contexts_pools,
        replicates=STAGE1_REPLICATES,
        corpus=corpus,
        scheme=scheme,
        seed=SEED,
    )
    result = stage1_drop_distribution(x0, subsets, candidate="X0")

    payload = dataclasses.asdict(result)
    quantized = _g1._quantize_json(payload)  # noqa: SLF001
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(quantized, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(f"[paper01-scope] wrote {out_path}\n")
    return 0


def cli_scope(out_path: Path | None = None) -> int:
    """``--scope``: real end-to-end §3-§5 scope-verdict assembly (Loop I-007).

    I-006 reserved this flag's body ("real Cambridge cell wiring lands in
    I-007's run.sh") -- this is that body. Gathers both Ocsai split schemes
    (:func:`_gather_ocsai`, once each), the internal ρ_int/k* basis
    (:func:`internal_reference_per_object`, falling back to
    :func:`internal_reference_c4_only` when the sealed Phase A artifact is
    missing -- mirrors :func:`cli_calibrate`'s own C4-only fallback),
    Cambridge's single ARM-S non-contradiction check
    (:func:`_gather_cambridge` / :func:`_score_cambridge_arm_s`), builds
    every split's full Stage 2 2x2 cell grid (:func:`build_split_cells`),
    and each split's Stage 0/Stage 1 rows -- then calls the frozen
    :func:`run_scope` (never re-derives its verdict independently).

    On any missing prerequisite (encoder / Cambridge / either Ocsai split
    unavailable), writes ``{"status": "source_unavailable"}`` and returns
    ``1`` -- DA-SC-5 / issue AC 007-4 ("Ocsai 到達不能なら verdict を出さず
    exit != 0"), never a partial/misleading ``results/scope.json``. This
    action needs a live Ocsai fetch (never available in an offline/no-
    network environment) -- see ``tests/test_paper01_scope/
    test_scope_cli_wiring.py`` for the synthetic-data proof that this
    wiring *completes* once its prerequisites are met (this issue's own
    boundary: "実データが無い環境では... 落ちるのは可。ただしデータが揃えば
    完走することを... unit-test して示す").
    """
    resolved = (RESULTS_DIR / "scope.json") if out_path is None else out_path

    mpnet = _load_mpnet_or_none()
    if mpnet is None:
        _write_unavailable(resolved, stage="scope")
        sys.stderr.write("[paper01-scope] --scope: MPNet encoder unavailable offline\n")
        return 1

    cambridge_gather = _gather_cambridge()
    if cambridge_gather is None:
        _write_unavailable(resolved, stage="scope")
        sys.stderr.write("[paper01-scope] --scope: Cambridge source unavailable\n")
        return 1

    try:
        references = internal_reference_per_object(mpnet)
    except FileNotFoundError:
        references = internal_reference_c4_only(mpnet)
    rho_primary, _rho_secondary, k_star = internal_rho_and_k(references)

    cells: dict[str, SplitCells] = {}
    stage0_rows: list[DeltaDecomposition] = [
        _stage0_internal_row(mpnet, rho_int_primary=rho_primary)
    ]
    stage1_result: Stage1Result | None = None
    cambridge_cell: CellResult | None = None

    for scheme_def in _g1.SPLIT_SCHEMES:
        scheme = scheme_def.key
        gather = _gather_ocsai(scheme)
        if gather is None:
            _write_unavailable(resolved, stage="scope")
            sys.stderr.write(
                f"[paper01-scope] --scope: Ocsai {scheme} source unavailable\n"
            )
            return 1

        split_cells, dense_k_max = build_split_cells(
            gather, rho_int_primary=rho_primary, k_star=k_star, corpus="ocsai"
        )
        cells[scheme] = split_cells

        if scheme == "SPLIT-BLOCK":
            external_row = _stage0_external_row(gather, dense_k_max)
            if external_row is not None:
                stage0_rows.append(external_row)
            stage1_result = _stage1_result(gather, dense_k_max)
            cambridge_cell = _score_cambridge_arm_s(
                cambridge_gather, split_cells.tau_calibration
            )

    if stage1_result is None or cambridge_cell is None:
        _write_unavailable(resolved, stage="scope")
        sys.stderr.write(
            "[paper01-scope] --scope: Stage 1 / Cambridge could not be "
            "scored (no active objects on the primary SPLIT-BLOCK split)\n"
        )
        return 1

    run_scope(
        stage0=tuple(stage0_rows),
        stage1=stage1_result,
        cells=cells,
        cambridge=cambridge_cell,
        internal_references=references,
        out_path=resolved,
    )
    sys.stdout.write(f"[paper01-scope] wrote {resolved}\n")
    return 0


def _write_unavailable(out_path: Path, *, stage: str) -> None:
    """Shared ``source_unavailable`` writer for the CLI actions above."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"status": "source_unavailable", "stage": stage}
    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# I-007 はこのファイルの CLI 分岐のみ
# ---------------------------------------------------------------------------
#
# design-final.md §6's fidelity pin (b)+(c) body (I-006 only reserved the
# ``--fidelity`` parser stub, TASK-PRE MEDIUM-4) and the real Cambridge
# cell wiring `cli_scope` (above, I-006's own CLI section) needed but did
# not build (I-006 Scope Out: "実走"). Every real-data action below shares
# the same discipline as the I-006 CLI actions immediately above: return
# (never raise) on a missing prerequisite, quantise every float leaf
# through ``_g1._quantize_json`` before any JSON write, and delegate every
# statistic to the frozen apparatus (:mod:`scripts.paper01_external_audit`)
# -- nothing here re-derives a number that module (or this module's own
# I-002..I-006 sections) already computes.
#
# **Boundary (this session, I-007a)**: this section only ever *builds* the
# wiring; it never runs it end-to-end against the real Ocsai/Cambridge
# corpora (no network fetch happens in this repo checkout -- see
# ``tests/test_paper01_scope/test_scope_cli_wiring.py`` for the
# synthetic-data proof that it completes once its prerequisites are met).


# --- fidelity pin (b): cell(tau=REF_DEDUP, k=N_R_MAX) reproduces G1 ARM-A --

G1_ARM_A_EXPECTED_AUC_FULL: Final[float] = 0.863122
G1_ARM_A_EXPECTED_AUC_LAO: Final[float] = 0.839575
G1_ARM_A_EXPECTED_POTENCY: Final[float] = 0.375293
G1_ARM_A_EXPECTED_CELL_VERDICT: Final[str] = "PASS"
G1_ARM_A_EXPECTED_OVERALL_VERDICT: Final[str] = "PASS"
G1_ARM_A_EXPECTED_SURVIVORS: Final[tuple[str, ...]] = ("X3a", "X3b", "X3c")
"""design-final.md §6 fidelity pin (b) (Codex HIGH-4, AC 006-1/blockers.md
ブロッカー3): the frozen G1 Ocsai SPLIT-BLOCK ARM-A committed values,
candidate X3b. These are the *comparison targets*, never recomputed here --
the same sealed numbers
``tests/test_paper01_scope/test_cells.py::test_dense_cell_reproduces_
g1_arm_a`` (I-006's own real-data test for this exact pin, gated
``ERRE_RUN_REAL_MPNET_TESTS=1``) asserts against. This module keeps its own
copy so the production ``--fidelity`` CLI action can compare without
importing a test module."""

G1_ARM_A_TOLERANCE: Final[float] = 1e-6
"""Matches ``test_dense_cell_reproduces_g1_arm_a``'s own
``pytest.approx(..., abs=1e-6)`` tolerance -- kept as a named constant so a
mutant loosening it is a one-line, greppable target."""


@dataclasses.dataclass(frozen=True, slots=True)
class ArmAFidelityResult:
    """One real measurement of fidelity pin (b).

    This issue's own internal type (not a §9 frozen contract -- mirrors
    :class:`CellAnchors`'s own I-006 precedent of a non-contract in-process
    dataclass, Codex TASK-PRE LOW-2's rationale: I-007 only ever reads this
    in the CLI action that produces it, never persists it to disk).
    """

    auc_full_at_median_draw: float
    auc_lao_at_median_draw: float
    potency_at_median_draw: float
    cell_verdict: str
    overall_verdict: str
    survivors: tuple[str, ...]


def measure_g1_arm_a_fidelity(gather: _OcsaiGather) -> ArmAFidelityResult:
    """design-final.md §6 fidelity pin (b): this issue's cell pipeline vs. G1.

    Compares ``cell(tau=REF_DEDUP, k=N_R_MAX)`` against G1's committed
    Ocsai SPLIT-BLOCK ARM-A numbers. Built entirely from :func:`build_cell`
    / :func:`score_cell` -- the
    *generalised* I-006 pipeline -- never G1's own ``run_ocsai_split``
    called directly. Spies on ``_g1.score_rows_for_draw`` (patches it with
    a wrapper that still calls the real function; never mutates its
    behaviour) purely to recover X3b's per-draw items for
    :func:`~scripts.paper01_external_audit.build_candidate_report`'s
    ``*_at_median_draw`` statistics, which :func:`score_cell`'s own
    :class:`CellResult` return does not carry (only the final verdict +
    object weights). This mirrors ``tests/test_paper01_scope/test_cells.py
    ::test_dense_cell_reproduces_g1_arm_a`` (I-006's own pre-registered
    real-data test for this exact pin) line for line, so production and
    test can never quietly diverge.
    """
    scheme = gather.scheme
    corpus = "ocsai"
    cells_by_object = {
        obj: build_cell(
            gather.contexts[obj],
            gather.vmaps.get("mpnet", {}),
            tau=_c.REF_DEDUP,
            cap=_c.N_R_MAX,
            corpus=corpus,
            scheme=scheme,
        )
        for obj in gather.active_objects
    }
    active = active_objects_for_cell(cells_by_object)

    captured_draws: dict[str, list[Any]] = {c.key: [] for c in _g1.CANDIDATE_LADDER}
    real_score = _g1.score_rows_for_draw

    def _score_spy(*args: object, **kwargs: object) -> dict[str, Any]:
        scored = real_score(*args, **kwargs)
        for key, items in scored.items():
            captured_draws[key].append(items)
        return scored

    with unittest.mock.patch.object(_g1, "score_rows_for_draw", side_effect=_score_spy):
        cell_result = score_cell(
            cells_by_object,
            gather.contexts,
            active,
            gather.vmaps,
            tau=_c.REF_DEDUP,
            k_target=_c.N_R_MAX,
            corpus=corpus,
            scheme=scheme,
        )

    x3b_summary = _g1.build_candidate_report(
        "X3b",
        "embedding",
        captured_draws["X3b"],
        bootstrap_seed=_g1.derive_seed(corpus, scheme, "X3b", "bootstrap"),
        permutation_seed=_g1.derive_seed(corpus, scheme, "X3b", "permutation"),
    )

    class_sizes = _g1.cambridge_class_sizes([gather.contexts[o] for o in active])
    reports = []
    for cand in _g1.CANDIDATE_LADDER:
        if cand.key not in _g1.EMBEDDING_FAMILY_EXT or not captured_draws[cand.key]:
            continue
        summary = _g1.build_candidate_report(
            cand.key,
            cand.family,
            captured_draws[cand.key],
            bootstrap_seed=_g1.derive_seed(corpus, scheme, cand.key, "bootstrap"),
            permutation_seed=_g1.derive_seed(corpus, scheme, cand.key, "permutation"),
        )
        reports.append(summary.report)
    overall_verdict = _g1.decide_external(reports, class_sizes=class_sizes)

    return ArmAFidelityResult(
        auc_full_at_median_draw=x3b_summary.report.auc_full_at_median_draw,
        auc_lao_at_median_draw=x3b_summary.report.auc_lao_at_median_draw,
        potency_at_median_draw=x3b_summary.report.potency_at_median_draw,
        cell_verdict=cell_result.verdict,
        overall_verdict=overall_verdict.verdict,
        survivors=overall_verdict.survivors,
    )


def g1_arm_a_fidelity_matches(result: ArmAFidelityResult) -> bool:
    """design-final.md §6 fidelity pin (b)'s exact-match criterion.

    Mirrors :func:`~scripts.paper01_external_audit.
    fidelity_candidate_matches`'s own discipline (a named boundary
    predicate, never an inline literal comparison scattered across call
    sites) -- every component must match within
    :data:`G1_ARM_A_TOLERANCE`, and the verdict/survivor fields must match
    exactly.

    mutation targets: (a) any component dropped from the conjunction, (b)
    the conjunction relaxed to a disjunction, (c) :data:`G1_ARM_A_TOLERANCE`
    loosened.
    """
    return (
        abs(result.auc_full_at_median_draw - G1_ARM_A_EXPECTED_AUC_FULL)
        < G1_ARM_A_TOLERANCE
        and abs(result.auc_lao_at_median_draw - G1_ARM_A_EXPECTED_AUC_LAO)
        < G1_ARM_A_TOLERANCE
        and abs(result.potency_at_median_draw - G1_ARM_A_EXPECTED_POTENCY)
        < G1_ARM_A_TOLERANCE
        and result.cell_verdict == G1_ARM_A_EXPECTED_CELL_VERDICT
        and result.overall_verdict == G1_ARM_A_EXPECTED_OVERALL_VERDICT
        and result.survivors == G1_ARM_A_EXPECTED_SURVIVORS
    )


# --- --fidelity: pin (b) + pin (c), data-unavailable vs. mismatch --------

FIDELITY_EXIT_OK: Final[int] = 0
FIDELITY_EXIT_MISMATCH: Final[int] = 1
FIDELITY_EXIT_SOURCE_UNAVAILABLE: Final[int] = 2
"""This issue's own binding instruction (orchestrator, 2026-09-08): "デー
タが無い」と「不一致」を混同せず、別々の exit code / メッセージで区別する".
:data:`FIDELITY_EXIT_MISMATCH` means a pin *ran* and its measured value
disagrees with its frozen §6 target -- mirrors G1's own ``--fidelity``
(:func:`scripts.paper01_external_audit.main`)'s "不一致で exit != 0"
convention. :data:`FIDELITY_EXIT_SOURCE_UNAVAILABLE` means a pin could not
run at all (missing encoder / sealed Phase A artifact / an offline Ocsai
fetch) -- "we could not check" is not the same claim as "we checked and it
disagrees", even though a caller that only tests ``exit_code != 0`` still
sees a failure either way (never silently exit 0 for a skipped pin). A
mismatch takes priority over an unavailable pin when both occur in the same
invocation (:func:`cli_fidelity` surfaces the stronger signal first)."""


def cli_fidelity() -> int:
    """``--fidelity``: design-final.md §6's fidelity pin (b) + (c).

    Body reserved for I-007 by I-006 (issue 006 TASK-PRE MEDIUM-4). Runs
    two independent pins and returns a combined exit code (never conflates
    "could not run" with "ran and disagreed" -- see
    :data:`FIDELITY_EXIT_MISMATCH` / :data:`FIDELITY_EXIT_SOURCE_UNAVAILABLE`):

    - **pin (c)** (internal, C0 heavy + C4 fast): delegates entirely to the
      frozen G1 apparatus's own :func:`~scripts.paper01_external_audit.
      run_fidelity` (never reimplemented) -- design-final.md §9's
      ``C0=0.9900/0.7550`` / ``C4=0.9950/0.7050`` values are *its*
      ``C0_EXPECTED_AUC_*`` / ``C4_EXPECTED_AUC_*`` module constants, read
      through, never copied. ``RuntimeError`` (encoder unavailable) and
      ``FileNotFoundError`` (sealed Phase A artifact missing) are both
      "source unavailable", never a mismatch.
    - **pin (b)** (external, ``cell(tau=REF_DEDUP, k=N_R_MAX)`` reproduces
      G1 ARM-A): :func:`measure_g1_arm_a_fidelity`, gated on a real Ocsai
      fetch + all four sentence-transformer encoders
      (:func:`_gather_ocsai`; ``None`` is "source unavailable").
    """
    mismatch = False
    unavailable = False

    try:
        c_result = _g1.run_fidelity()
    except (RuntimeError, FileNotFoundError) as exc:
        unavailable = True
        sys.stderr.write(
            "[paper01-scope] --fidelity: pin (c) internal fidelity source "
            f"unavailable ({exc})\n"
        )
    else:
        if not c_result["all_match"]:
            mismatch = True
            sys.stderr.write(
                "[paper01-scope] --fidelity: pin (c) MISMATCH -- "
                f"c0.matches={c_result['c0']['matches']} "
                f"c4.matches={c_result['c4']['matches']}\n"
            )
        else:
            sys.stdout.write("[paper01-scope] --fidelity: pin (c) internal OK\n")

    gather = _gather_ocsai("SPLIT-BLOCK")
    if gather is None:
        unavailable = True
        sys.stderr.write(
            "[paper01-scope] --fidelity: pin (b) source unavailable "
            "(Ocsai fetch or an encoder is missing offline)\n"
        )
    else:
        b_result = measure_g1_arm_a_fidelity(gather)
        if not g1_arm_a_fidelity_matches(b_result):
            mismatch = True
            sys.stderr.write(
                "[paper01-scope] --fidelity: pin (b) MISMATCH -- "
                f"auc_full={b_result.auc_full_at_median_draw} "
                f"auc_lao={b_result.auc_lao_at_median_draw} "
                f"potency={b_result.potency_at_median_draw} "
                f"cell_verdict={b_result.cell_verdict} "
                f"overall_verdict={b_result.overall_verdict} "
                f"survivors={b_result.survivors}\n"
            )
        else:
            sys.stdout.write("[paper01-scope] --fidelity: pin (b) G1 ARM-A OK\n")

    if mismatch:
        return FIDELITY_EXIT_MISMATCH
    if unavailable:
        return FIDELITY_EXIT_SOURCE_UNAVAILABLE
    return FIDELITY_EXIT_OK


# --- Cambridge gather (single, SPLIT-BLOCK-only, §4 F5 non-contradiction) -


@dataclasses.dataclass(frozen=True, slots=True)
class _CambridgeGather:
    """CLI-only, in-process bundle of Cambridge's gathered inputs.

    Mirrors :class:`_OcsaiGather` (I-006) but SPLIT-BLOCK only --
    design-final.md's single non-primary Cambridge check (§0/§8 item 7:
    "報告 + 非矛盾のみ"). This issue's own design choice: the single
    Cambridge ARM-S cell is scored at the SPLIT-BLOCK split's τ*/k*
    (never SPLIT-PARITY's, never an average of the two) -- design-final.md
    does not pin which split backs it, so this reuses the same
    "SPLIT-BLOCK is primary" convention every other single-scheme CLI
    action in this file (:func:`cli_stage0` / :func:`cli_stage1`) already
    follows, and :data:`~scripts.paper01_external_audit.SPLIT_SCHEMES`'s
    own ``role="primary"`` / :func:`~scripts.paper01_external_audit.
    run_cambridge_audit`'s ``"primary_split": "SPLIT-BLOCK"`` convention.
    """

    contexts: Mapping[str, _g1.ObjectSplitContext]
    vmaps: Mapping[str, Mapping[str, np.ndarray]]
    active_objects: tuple[str, ...]


def _gather_cambridge() -> _CambridgeGather | None:
    """Best-effort real Cambridge embed, SPLIT-BLOCK only.

    Mirrors :func:`_gather_ocsai`'s discipline (``None``, never raises, on
    any missing prerequisite). ``_g1.load_cambridge_raw_bytes`` reads the
    two already-fetched (G1) local ``.xlsx`` files -- no network fetch of
    its own: this issue's boundary forbids *fetching* Ocsai/Cambridge, not
    reading what a prior task already fetched to disk
    (``.steering/20260908-paper01-scope-condition/blockers.md`` ブロッカー4's
    own inventory: "Cambridge データはある").
    """
    try:
        raw = _g1.load_cambridge_raw_bytes()
    except FileNotFoundError:
        return None
    rows_by_object = {
        obj: _g1.load_cambridge_rows(obj, data) for obj, data in raw.items()
    }
    try:
        encoders = _g1.build_available_encoders()
    except _g1.MissingEncoderError:
        return None
    vmaps = _g1.embed_all_texts(rows_by_object, encoders)
    mpnet_vmap = vmaps.get("mpnet", {})
    scheme = "SPLIT-BLOCK"
    contexts = {
        obj: _g1.build_object_split_context(
            obj, rows_by_object[obj], scheme, mpnet_vmap
        )
        for obj in _g1.CAMBRIDGE_OBJECTS
    }
    active = tuple(
        sorted(
            obj
            for obj in _g1.CAMBRIDGE_OBJECTS
            if not contexts[obj].dropped
            and _g1.object_has_both_gold_classes(contexts[obj])
        )
    )
    return _CambridgeGather(contexts=contexts, vmaps=vmaps, active_objects=active)


def _score_cambridge_arm_s(
    cambridge: _CambridgeGather,
    tau_calibration: TauCalibration,
    *,
    corpus: str = "cambridge",
) -> CellResult:
    """Score Cambridge's single ARM-S cell (design-final.md §4 F5).

    At the primary (SPLIT-BLOCK) split's already-calibrated τ*/k* -- see
    :class:`_CambridgeGather`'s own docstring for why SPLIT-BLOCK. Built
    from :func:`build_cell` / :func:`score_cell` (never a hand-rolled
    scoring pass).
    """
    scheme = "SPLIT-BLOCK"
    cells_by_object = {
        obj: build_cell(
            cambridge.contexts[obj],
            cambridge.vmaps.get("mpnet", {}),
            tau=tau_calibration.tau_star,
            cap=tau_calibration.k_star,
            corpus=corpus,
            scheme=scheme,
        )
        for obj in cambridge.active_objects
    }
    active = active_objects_for_cell(cells_by_object)
    return score_cell(
        cells_by_object,
        cambridge.contexts,
        active,
        cambridge.vmaps,
        tau=tau_calibration.tau_star,
        k_target=tau_calibration.k_star,
        corpus=corpus,
        scheme=scheme,
    )


# --- one Ocsai split's full Stage 2 2x2 grid (DA-SC-3 + MEDIUM-3) --------


def build_split_cells(
    gather: _OcsaiGather,
    *,
    rho_int_primary: float,
    k_star: int,
    corpus: str = "ocsai",
) -> tuple[SplitCells, dict[str, CellAnchors]]:
    """Wire one Ocsai split's full Stage 2 2x2 cell grid into :class:`SplitCells`.

    design-final.md §3 Stage 2 (DA-SC-3's 4-cell common-active-object
    intersection + §2.4 MEDIUM-3's τ*-neighbour single-point-dependence
    check) -- I-006's own Scope In stopped at :func:`build_cell` /
    :func:`score_cell` / :func:`active_objects_for_cell` /
    :func:`common_active_objects` as individually-callable primitives; this
    issue's Goal is wiring them into one split's full grid.

    Builds all four ``(tau, k)`` grid corners via :func:`build_cell` --
    ``(REF_DEDUP, N_R_MAX)`` = ARM-A, ``(REF_DEDUP, k_star)``,
    ``(tau_star, N_R_MAX)``, ``(tau_star, k_star)`` = ARM-S -- over
    ``gather.active_objects``, computes their DA-SC-3 common-active-object
    intersection (:func:`common_active_objects`), then scores only the two
    diagonal cells (:func:`score_cell`) over that shared intersection -- the
    two off-diagonal corners exist only to constrain the intersection
    (design-final.md §3's 2x2 table: only the diagonal feeds
    :func:`decide_scope`).

    ``single_point_dependent`` (MEDIUM-3, §2.4) is finalised here (never by
    :func:`calibrate_tau` itself -- its own docstring defers this to
    ``run_scope``'s caller): additionally scores ARM-S-shaped cells
    (``tau=neighbour, cap=k_star``, same common-active intersection) at
    every :func:`adjacent_tau_indices` neighbour of τ* -- ``True`` iff
    condition 1 (``verdict(ARM-S)=="NO_VALID_SCORER" and
    verdict(ARM-A)=="PASS"``) holds at τ* but fails at *every* neighbour
    tried (§2.4: "τ* の隣接1段(上または下)でも同じ verdict が出ること";
    "単点だけで成立した場合は... 「特定できない」に倒す" -- so this flag is
    only meaningful, and only ever set ``True``, when condition 1 holds at
    τ* itself; the neighbour cells reuse the *same* common-active
    intersection as the primary grid, this issue's own documented choice
    since design-final.md does not pin whether the neighbour check gets its
    own intersection).

    Returns ``(SplitCells, arm_a_cells_by_object)`` -- the second element is
    the raw ARM-A :class:`CellAnchors` mapping (never returned by
    :func:`score_cell`'s own :class:`CellResult`), which this split's
    Stage 0 external row and Stage 1 anchor draw (:data:`STAGE1_DRAW_INDEX`)
    both need and would otherwise have to rebuild a second time.
    """
    scheme = gather.scheme
    rho_ext_by_tau = external_rho_by_tau(
        gather.contexts, gather.vmaps.get("mpnet", {}), gather.active_objects
    )
    tau_cal_raw = calibrate_tau(rho_ext_by_tau, rho_int_primary, k_star=k_star)
    tau_star = tau_cal_raw.tau_star

    def _corner_cells(tau: float, cap: int) -> dict[str, CellAnchors]:
        return {
            obj: build_cell(
                gather.contexts[obj],
                gather.vmaps.get("mpnet", {}),
                tau=tau,
                cap=cap,
                corpus=corpus,
                scheme=scheme,
            )
            for obj in gather.active_objects
        }

    dense_k_max = _corner_cells(_c.REF_DEDUP, _c.N_R_MAX)
    dense_k_star = _corner_cells(_c.REF_DEDUP, k_star)
    sparse_k_max = _corner_cells(tau_star, _c.N_R_MAX)
    sparse_k_star = _corner_cells(tau_star, k_star)

    active_by_corner = {
        "dense_k_max": active_objects_for_cell(dense_k_max),
        "dense_k_star": active_objects_for_cell(dense_k_star),
        "sparse_k_max": active_objects_for_cell(sparse_k_max),
        "sparse_k_star": active_objects_for_cell(sparse_k_star),
    }
    common = tuple(common_active_objects(active_by_corner))

    arm_a = score_cell(
        dense_k_max,
        gather.contexts,
        common,
        gather.vmaps,
        tau=_c.REF_DEDUP,
        k_target=_c.N_R_MAX,
        corpus=corpus,
        scheme=scheme,
    )
    arm_s = score_cell(
        sparse_k_star,
        gather.contexts,
        common,
        gather.vmaps,
        tau=tau_star,
        k_target=k_star,
        corpus=corpus,
        scheme=scheme,
    )

    condition1_at_star = arm_s.verdict == "NO_VALID_SCORER" and arm_a.verdict == "PASS"
    single_point_dependent = False
    if condition1_at_star:
        tau_star_index = TAU_GRID.index(tau_star)
        neighbour_holds = False
        for idx in adjacent_tau_indices(tau_star_index):
            neighbour_tau = TAU_GRID[idx]
            neighbour_cells = _corner_cells(neighbour_tau, k_star)
            neighbour_arm_s = score_cell(
                neighbour_cells,
                gather.contexts,
                common,
                gather.vmaps,
                tau=neighbour_tau,
                k_target=k_star,
                corpus=corpus,
                scheme=scheme,
            )
            if neighbour_arm_s.verdict == "NO_VALID_SCORER":
                neighbour_holds = True
                break
        single_point_dependent = not neighbour_holds

    tau_cal = dataclasses.replace(
        tau_cal_raw, single_point_dependent=single_point_dependent
    )

    return SplitCells(arm_a=arm_a, arm_s=arm_s, tau_calibration=tau_cal), dense_k_max


# --- SPLIT-BLOCK-only Stage 0 external row / Stage 1 (reuse the ARM-A cell)


def _stage0_internal_row(
    mpnet: Callable[[Sequence[str]], np.ndarray], *, rho_int_primary: float
) -> DeltaDecomposition:
    """The Stage 0 internal (C4) row.

    Mirrors :func:`cli_stage0`'s own internal branch (I-006) exactly, so
    ``--scope`` need not shell out to a second ``--stage0`` invocation
    (which would also compute an external row this function does not need
    -- :func:`_stage0_external_row` below reuses ``--scope``'s own
    SPLIT-BLOCK grid instead of re-fetching Ocsai a second time).
    """
    candidate, _vmap, curated = _g1._c4_fidelity_context(mpnet)  # noqa: SLF001
    gold_pair = _g1.fidelity_gold_pair()
    scores_full = tuple(
        candidate.rarity(g.object, g.text, leave_anchor_out=False) for g in gold_pair
    )
    scores_lao = tuple(
        candidate.rarity(g.object, g.text, leave_anchor_out=True) for g in gold_pair
    )
    labels = tuple(1 if g.category == "good" else 0 for g in gold_pair)
    max_sim_full = tuple(1.0 - s for s in scores_full)
    del curated  # only the candidate closure is needed above
    return split_delta(
        scores_full,
        scores_lao,
        labels,
        max_sim_full,
        source=_STAGE0_INTERNAL_SOURCE,
        candidate=_STAGE0_INTERNAL_CANDIDATE,
        rho=rho_int_primary,
    )


def _stage0_external_row(
    gather: _OcsaiGather, dense_k_max: Mapping[str, CellAnchors]
) -> DeltaDecomposition | None:
    """The Stage 0 external (Ocsai SPLIT-BLOCK ARM-A, X0) row.

    Mirrors :func:`cli_stage0`'s own external branch (I-006), reusing the
    ARM-A cell :func:`build_split_cells` already built (never re-fetching /
    re-clustering). Returns ``None`` when X0 was not scored for any active
    object (mirrors :func:`cli_stage0`'s own ``if x0 is not None:`` guard).
    """
    active = active_objects_for_cell(dense_k_max)
    if not active:
        return None
    rows_all = tuple(r for obj in active for r in gather.contexts[obj].split1)
    idf_by_object = {
        o: (gather.contexts[o].idf, gather.contexts[o].default_idf) for o in active
    }
    anchor_texts_by_object = {
        o: dense_k_max[o].draw_texts_by_draw[STAGE1_DRAW_INDEX] for o in active
    }
    scored = _g1.score_rows_for_draw(
        rows_all,
        anchor_texts_by_object=anchor_texts_by_object,
        vmaps=gather.vmaps,
        idf_by_object=idf_by_object,
    )
    x0 = scored.get("X0")
    if x0 is None:
        return None
    rho_ext = corpus_redundancy(
        {
            o: np.asarray(
                [gather.vmaps.get("mpnet", {})[t] for t in anchor_texts_by_object[o]],
                dtype=float,
            )
            for o in active
            if anchor_texts_by_object[o]
        }
    )
    max_sim_full = tuple(1.0 - s for s in x0.scores_full)
    return split_delta(
        x0.scores_full,
        x0.scores_lao,
        x0.labels,
        max_sim_full,
        source=_STAGE0_EXTERNAL_SOURCE,
        candidate=_STAGE0_EXTERNAL_CANDIDATE,
        rho=rho_ext,
    )


def _stage1_result(
    gather: _OcsaiGather, dense_k_max: Mapping[str, CellAnchors]
) -> Stage1Result | None:
    """The Stage 1 deflation-test result for candidate X0.

    Mirrors :func:`cli_stage1` (I-006) exactly, reusing the ARM-A cell
    :func:`build_split_cells` already built. Returns ``None`` when X0 could
    not be scored (mirrors :func:`cli_stage1`'s own guards).
    """
    active = active_objects_for_cell(dense_k_max)
    if not active:
        return None
    rows_all = tuple(r for obj in active for r in gather.contexts[obj].split1)
    idf_by_object = {
        o: (gather.contexts[o].idf, gather.contexts[o].default_idf) for o in active
    }
    anchor_texts_by_object = {
        o: dense_k_max[o].draw_texts_by_draw[STAGE1_DRAW_INDEX] for o in active
    }
    scored = _g1.score_rows_for_draw(
        rows_all,
        anchor_texts_by_object=anchor_texts_by_object,
        vmaps=gather.vmaps,
        idf_by_object=idf_by_object,
    )
    x0 = scored.get("X0")
    if x0 is None:
        return None

    offset = 0
    contexts_pools: dict[str, ObjectGoldPool] = {}
    for obj in active:
        n = len(gather.contexts[obj].split1)
        good_idx = tuple(
            offset + i
            for i, r in enumerate(gather.contexts[obj].split1)
            if r.category == "good"
        )
        common_idx = tuple(
            offset + i
            for i, r in enumerate(gather.contexts[obj].split1)
            if r.category == "common_use_only"
        )
        contexts_pools[obj] = ObjectGoldPool(
            object_key=obj,
            object_weight=float(len(good_idx) * len(common_idx)),
            good_item_indices=good_idx,
            common_item_indices=common_idx,
        )
        offset += n

    subsets = internal_shaped_replicates(
        contexts_pools,
        replicates=STAGE1_REPLICATES,
        corpus="ocsai",
        scheme=gather.scheme,
        seed=SEED,
    )
    return stage1_drop_distribution(x0, subsets, candidate="X0")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point (Loop I-006 + I-007's ``--fidelity``/``--scope`` bodies).

    Flags may combine; each one set runs at most once, in the order
    calibrate -> stage0 -> stage1 -> stage2 -> scope -> fidelity. Every
    real-data action reports ``source_unavailable`` (never a fabricated
    result) and returns a non-zero exit code when its prerequisites are not
    met -- the overall exit code is the maximum of every action run
    (``--fidelity`` additionally distinguishes a mismatch
    (:data:`FIDELITY_EXIT_MISMATCH`) from a source-unavailable pin
    (:data:`FIDELITY_EXIT_SOURCE_UNAVAILABLE`), both non-zero).
    """
    parser = argparse.ArgumentParser(description="paper01 scope-condition CLI")
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="compute + write the §2.3 internal rho_int/k* basis",
    )
    parser.add_argument(
        "--stage0",
        action="store_true",
        help="compute + write the §1/§3 Stage 0 Delta=T-S rows",
    )
    parser.add_argument(
        "--stage1",
        action="store_true",
        help="run the §3 Stage 1 deflation test for candidate X0",
    )
    parser.add_argument(
        "--stage2",
        action="store_true",
        help="build + score the Ocsai SPLIT-BLOCK ARM-A/ARM-S cells",
    )
    parser.add_argument(
        "--scope",
        action="store_true",
        help="run the full §3-§5 scope verdict (reserved: see --scope-out)",
    )
    parser.add_argument(
        "--scope-out",
        type=Path,
        default=None,
        help="output path for results/scope.json (default: results/scope.json)",
    )
    parser.add_argument(
        "--fidelity",
        action="store_true",
        help=(
            "run the §6 fidelity pin (b)+(c); exit 1 on mismatch, exit 2 "
            "on source-unavailable (never conflated)"
        ),
    )
    args = parser.parse_args(argv)

    exit_code = 0
    if args.calibrate:
        exit_code = max(exit_code, cli_calibrate())
    if args.stage0:
        exit_code = max(exit_code, cli_stage0())
    if args.stage1:
        exit_code = max(exit_code, cli_stage1())
    if args.stage2:
        exit_code = max(exit_code, cli_stage2())
    if args.scope:
        exit_code = max(exit_code, cli_scope(out_path=args.scope_out))
    if args.fidelity:
        exit_code = max(exit_code, cli_fidelity())

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

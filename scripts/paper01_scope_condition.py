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

import dataclasses
import importlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Mapping
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


# ---------------------------------------------------------------------------
# I-004: Stage 1 -- deflation test
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# I-005: decision rule -- decide_scope()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# I-006: tau* calibration / cell wiring / CLI
# ---------------------------------------------------------------------------

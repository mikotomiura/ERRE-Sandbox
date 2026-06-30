"""Pin the M13-ES4 frozen §5 constants to the ADR table verbatim.

Every threshold was fixed **before** any verdict result
(``.steering/20260630-m13-es4-adr/design-final.md`` §5, user-ratified
pre-registration). This is the forking-paths regression pin: a constant changes
only by a deliberate edit that also updates this expected table (which requires a
superseding ADR). Verdict values are **not** pinned here.
"""

from __future__ import annotations

from pathlib import Path

from erre_sandbox.bootstrap import _load_persona_yaml
from erre_sandbox.erre.locomotion_sampling import DEFAULT_LOCO_GAIN_T
from erre_sandbox.evidence.es3_locomotion import constants as _es3
from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.schemas import SCHEMA_VERSION

_PERSONAS_DIR = Path(__file__).resolve().parents[2] / "personas"


def test_actuator_gains_verbatim() -> None:
    assert _c.LOCO_GAIN_T == 0.3
    assert _c.LOCO_GAIN_P == 0.0  # ES-4 temperature-only actuator (Codex HIGH-1)
    assert _c.LOCO_GAIN_T == DEFAULT_LOCO_GAIN_T  # inherited ES-3 scale
    assert _c.TEMP_MIN == 0.01
    assert _c.TEMP_MAX == 2.0


def test_condition_bands_verbatim() -> None:
    assert _c.LAMBDA_A0 == 0.0
    assert _c.LAMBDA_BAND_A1 == (0.4, 0.6)
    assert _c.LAMBDA_BAND_A2 == (0.85, 1.0)
    assert _c.F_TEMP_DELTA == 0.8


def test_battery_sizes_verbatim() -> None:
    assert _c.N_AUT == 16
    assert _c.N_AUT_CLASSIC == 8
    assert _c.N_AUT_NOVEL == 8
    assert _c.N_RAT == 16
    assert _c.MIN_VALID_AUT == 12
    assert _c.MIN_VALID_RAT == 8


def test_seed_counts_verbatim() -> None:
    assert _c.N_SEED_PHASE0 == 10
    assert _c.N_SEED_PHASE1 == 20


def test_scoring_constants_verbatim() -> None:
    assert _c.K_IDEAS == 5
    assert _c.MIN_VALID_IDEAS_FOR_DQ == 2
    assert _c.IDEA_MIN_TOK == 3
    assert _c.IDEA_MAX_TOK == 40
    assert _c.DISTINCT_TOKEN_RATIO_MIN == 0.4
    assert _c.NGRAM_LOOP_N == 3
    assert _c.NUM_PREDICT_AUT == 384
    assert _c.NUM_PREDICT_RAT == 32


def test_reference_recipe_constants_verbatim() -> None:
    assert _c.N_CURATED == 10
    assert _c.REF_SEEDS == 50
    assert _c.REF_FREQ_MIN == 0.20
    assert _c.REF_DEDUP == 0.90
    assert _c.N_R_MIN == 8
    assert _c.N_R_MAX == 30
    assert _c.REF_TEMP == 0.7


def test_verdict_thresholds_verbatim() -> None:
    assert _c.MDE_CLUSTER_D == 0.40
    assert _c.POWER == 0.80
    assert _c.ALPHA_ONE_SIDED == 0.05
    assert _c.PROJECTED_CLUSTER_MAX == 48
    assert _c.DQ_FLOOR_STD_CI_LOWER == 0.20
    assert _c.DQ_FLOOR_RAW == 0.02
    assert _c.AUC_FLOOR == 0.80
    assert _c.DELTA_EQUIV == 0.15
    assert _c.GARBAGE_RATE_CEILING == 0.30
    assert _c.EMPTY_PARSE_FAIL_CEILING == 0.05
    assert _c.CROSS_COND_DIVERGENCE_MAX == 0.30


def test_bootstrap_and_budget_constants_verbatim() -> None:
    assert _c.CI_ALPHA == 0.10
    assert _c.N_RESAMPLES == 10000
    assert _c.PHASE0_GPU_HOUR_CAP == 8.0
    assert _c.PHASE1_GPU_HOUR_CAP == 30.0


def test_item_gate_constants_verbatim() -> None:
    assert _c.AUT_MIN_IDEAS_BASE == 2
    assert _c.AUT_MIN_TRIAL_FRAC == 0.70
    assert _c.PARSE_SUCCESS_MIN == 0.90
    assert _c.RAT_ACC_MIN == 0.10
    assert _c.RAT_ACC_MAX == 0.90


def test_persona_roster_pinned_to_es3_and_real_yaml() -> None:
    """Roster is the blind ES-3 roster, mirrored from the real persona YAML."""
    assert [pid for pid, _ in _c.PERSONA_ROSTER] == ["kant", "nietzsche", "rikyu"]
    assert _c.N_PERSONA == 3
    assert _c.PERSONA_ROSTER == _es3.PERSONA_ROSTER
    for persona_id, base in _c.PERSONA_ROSTER:
        spec = _load_persona_yaml(_PERSONAS_DIR, persona_id)
        assert base == spec.default_sampling, persona_id


def test_cluster_count_matches_power_ceiling() -> None:
    """48 = N_PERSONA × N_AUT, the effective-N for cluster-level power (HIGH-8)."""
    assert _c.N_PERSONA * _c.N_AUT == _c.PROJECTED_CLUSTER_MAX


def test_wire_schema_version_unchanged() -> None:
    """ES-4 is verdict-side only (no Godot-bridge / BaseModel wire change), so the
    wire SCHEMA_VERSION is NOT bumped (Session-1 design decision)."""
    assert SCHEMA_VERSION == "0.11.0-m13es3"

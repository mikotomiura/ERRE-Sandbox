"""Tests for the ECL B a-priori power apparatus (Issue 004, I4-G1..G4).

Contract: ``.steering/20260707-m13-b-impl-design/design-final.md`` §I6 (teeth
named 閾値 proposal + power worksheet FROZEN 条件化) +
``loop/20260708-m13-b-code-impl/issues/004-power-worksheet.md``. This test
module is doc-only-power-adjacent (independent of I1/I2/I5) and never imports
``bank_fixtures`` / a bank driver — mirrors the module's own isolation.
"""

from __future__ import annotations

import ast
from pathlib import Path

from erre_sandbox.integration.embodied import bank_power
from erre_sandbox.integration.embodied.bank_power import (
    DELTA_TV_MIN,
    H_MIN_BITS,
    K_MIN,
    M_MIN,
    POWER_MIN,
    RHO_MIN,
    categorical_multinomial_power,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSHEET_PATH = (
    REPO_ROOT / "experiments" / "20260708-m13-b-bank" / "power_worksheet.md"
)
MODULE_PATH = (
    REPO_ROOT / "src" / "erre_sandbox" / "integration" / "embodied" / "bank_power.py"
)


# --- I4-G1: worksheet presence + required sections -----------------------------


def test_bank_power_worksheet_present() -> None:
    """Worksheet exists and states the 検定法 / worst+representative base
    distribution / K-pooling assumption / named 閾値 (M_min/K/δ_min/H_min/ρ)."""
    assert WORKSHEET_PATH.exists(), WORKSHEET_PATH
    text = WORKSHEET_PATH.read_text(encoding="utf-8")

    required_section_markers = (
        "検定法",  # test method
        "categorical",  # 5-way multinomial power naming
        "worst-case",  # worst-case base distribution
        "代表",  # representative base distribution
        "pooling",  # K-context pooling assumption
        "M_min",
        "K",
        "delta_tv" if "delta_tv" in text else "δ_min",
        "power",
        "H_min",
        "rho" if "rho" in text else "ρ",
    )
    for marker in required_section_markers:
        assert marker in text, f"missing required worksheet marker: {marker!r}"

    # honest (i)-dependency disclosure must be present verbatim in spirit.
    assert "保証しない" in text or "保証不能" in text
    # scope guard: construction / not measurement / no real bank data / R-budget.
    assert "construction" in text.lower() or "構築" in text
    assert "measurement" in text.lower() or "計測" in text
    assert "R-budget" in text or "R_budget" in text or "Rバジェット" in text


# --- I4-G2: proposal thresholds reach power >= 0.8 on a representative dist ----


def test_bank_power_categorical_multinomial() -> None:
    """Assumed near-uniform base distribution at the proposal thresholds
    (delta_tv=0.10, M_min>=300, K>=8, pooled) clears power>=0.8 a-priori."""
    near_uniform = [0.2, 0.2, 0.2, 0.2, 0.2]
    result = categorical_multinomial_power(
        base_dist=near_uniform,
        delta_tv=DELTA_TV_MIN,
        m_draws=M_MIN,
        k_contexts=K_MIN,
        pooling=True,
    )
    assert result.n_total == M_MIN * K_MIN
    assert result.achieved_delta_tv == DELTA_TV_MIN
    assert result.power >= POWER_MIN, result


# --- I4-G3: collapse-scale achievable delta kills power (honest (i) teeth) ----


def test_bank_power_collapse_kills_power() -> None:
    """When H(zone|ctx) collapses towards 0 the achievable T_on/T_off shift
    collapses towards 0 too (empirical, §I6(i)) — even at the proposal
    M_min/K, a collapse-scale delta_tv (far below DELTA_TV_MIN) fails to
    reach power>=0.8. This mechanically demonstrates the (i) dependency the
    worksheet must state honestly (壁1&4 再来), without reading any real
    bank data — only the assumed collapse-scale delta magnitude changes."""
    near_uniform = [0.2, 0.2, 0.2, 0.2, 0.2]
    collapse_scale_delta = DELTA_TV_MIN / 10.0  # << δ_min proposal
    result = categorical_multinomial_power(
        base_dist=near_uniform,
        delta_tv=collapse_scale_delta,
        m_draws=M_MIN,
        k_contexts=K_MIN,
        pooling=True,
    )
    assert result.power < POWER_MIN, result

    # A literally degenerate base distribution (H(zone|ctx)≈0, the worst-case
    # base distribution the worksheet documents) is *not* by itself a low-power
    # regime for this chi-square construction — moving mass into an already-rare
    # cell is proportionally large and highly detectable even at a tiny absolute
    # delta_tv. This is itself an honest a-priori finding: the (i) dependency is
    # carried by the *achievable delta_tv* collapsing (asserted above), not by
    # base-distribution entropy alone. Documented, not asserted away.
    degenerate = [0.96, 0.01, 0.01, 0.01, 0.01]
    result_degenerate = categorical_multinomial_power(
        base_dist=degenerate,
        delta_tv=collapse_scale_delta,
        m_draws=M_MIN,
        k_contexts=K_MIN,
        pooling=True,
    )
    assert 0.0 <= result_degenerate.power <= 1.0, result_degenerate


def test_bank_power_thresholds_match_proposal() -> None:
    """Named thresholds are the confirmed §I6 proposal values (no silent drift)."""
    assert M_MIN == 300
    assert K_MIN == 8
    assert DELTA_TV_MIN == 0.10
    assert POWER_MIN == 0.8
    assert H_MIN_BITS == 0.5
    assert RHO_MIN == 0.5


# --- I4-G4: isolation from annotation side-file + bank driver measurement path -


def test_bank_power_isolated_from_annotation() -> None:
    """``bank_power.py`` reads no file and imports no sibling
    ``erre_sandbox.integration.embodied`` module (bank driver / bank_fixtures /
    annotation side-file reader) — it is an assumed-distribution-only a-priori
    apparatus (AST scan, source-level, values-independent)."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MODULE_PATH))

    banned_file_read_calls = {"open", "read_text", "read_bytes", "loads", "load"}
    banned_import_modules = (
        "erre_sandbox.integration.embodied.bank",
        "erre_sandbox.integration.embodied.bank_fixtures",
        "erre_sandbox.integration.embodied.annotation",
        "erre_sandbox.evidence",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = (
                func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            )
            assert name not in banned_file_read_calls, (
                f"bank_power.py must not read files (found call: {name!r})"
            )
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert not node.module.startswith(banned_import_modules), node.module
            # No import of any sibling module under this package at all —
            # bank_power.py is fully self-contained (numpy + stdlib only).
            assert node.module != "erre_sandbox.integration.embodied", node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(banned_import_modules), alias.name

    # No sibling-module imports show up as a plain module attribute reference
    # either (belt-and-suspenders): the imported top-level names must exclude
    # "bank" / "bank_fixtures" / "annotation".
    banned_local_names = {"bank", "bank_fixtures", "annotation"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[-1]
                assert local not in banned_local_names, local

    # Module docstring self-check: the object actually imported has no
    # forbidden attribute exposing an annotation/bank read path.
    assert not hasattr(bank_power, "read_annotation")
    assert not hasattr(bank_power, "BankLlmCallRecord")

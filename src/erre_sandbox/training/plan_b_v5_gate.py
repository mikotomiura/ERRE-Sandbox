"""Plan B v5 (β corpus rebalance) supplemental hard gate.

This module is the **β rebalance (adoption case A1) addition** on top of
the existing corpus gate in :mod:`erre_sandbox.training.plan_b_gate`.
The existing 4-axis gate (``de_en_mass>=0.60`` / ``de_mass>=0.30`` /
``n_eff>=1500`` / ``top_5_pct_weight_share<=0.35``) is **unchanged**
— this module adds three additional **hard
floors** required for the β corpus rebalance retrain
(``kant_r8_v5_rebal``) to be ADOPT-eligible:

* ``de_en_mass >= 0.85`` (現 ``kant_r8_v4`` baseline 0.6010 から +0.25pt)
* ``ja_mass <= 0.10`` (現 v4 baseline 0.389 から −0.29pt、ja silent
  gradient sink を解消する主目標)
* ``de_mass >= 0.40`` (現 v4 baseline 0.385 から +0.015pt、僅増)

Threshold rationale:

`kant_r8_v4` の `weight-audit.json` で ``per_language_weighted_mass`` が
**de 38.5% / en 21.6% / ja 38.9% / mixed 1.0%** であり、weighted gradient
の **38.9% が verdict 不可視の日本語** に向かっていた (eval shard で ja は
``n=21/18`` で 100-utterance window 取れず)。root cause を
**H4 trilingual capacity competition (ja silent sink)** + **H5 style
register mismatch** と特定し、
``_LANG_FACTORS["ja"]`` を 0.2 → 0.05 (採用案 A1) に下げる方針を確定。

v5 retrain の corpus build 後の audit で上記 3 hard floor をすべて満たす
ことが ADOPT の前提。本 module は ``train_kant_lora.py`` の
``--plan-b-gate-v5`` CLI flag から呼ばれ、3 floor のいずれかが fail した
場合に ``V5_GATE_FAIL_EXIT_CODE=9`` で exit する。

**既存 corpus gate との関係**:

`plan_b_gate.audit_corpus()` を変更しないことで、(a) thresholds 不変
方針を守り、(b) nietzsche / rikyu の Plan B retrain でも既存 gate を共有
可能、(c) 本 v5 gate は kant β corpus rebalance 限定の追加 hard floor と
して独立に管理される。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final

# ---------------------------------------------------------------------------
# Preregistered thresholds (must not move post-hoc)
# ---------------------------------------------------------------------------

DE_EN_MASS_MIN_V5: Final[float] = 0.85
"""β rebalance で達成すべき de+en 合計 weighted mass の下限.

v4 baseline 0.6010 から +0.25pt。`_LANG_FACTORS["ja"]` 0.2 → 0.05 の
変更で ja が floor (`WEIGHT_CLAMP_MIN=0.1`) に大量 clamp され、de_en
が 0.86-0.88 まで相対浮上する見込み。
"""

JA_MASS_MAX_V5: Final[float] = 0.10
"""β rebalance で達成すべき ja weighted mass の上限.

v4 baseline 0.389 から −0.29pt。ja silent gradient sink (H4 dominant
仮説) を解消する主目標。`_LANG_FACTORS["ja"]=0.05` で線形寄与
0.0175 と最小、ja example の relative weight は v4 (0.2 → raw ~0.34)
より大幅に下がる。

**補足**: 当初は「ja example
の大半が WEIGHT_CLAMP_MIN=0.1 floor に clamp される」と記述したが、
実 math では他項 (length / monolog / marker) が下支えするため raw
weight は ~0.28-0.40 程度に留まり floor には届かない。A1 単独で
ja_mass<=0.10 達成できる math 上の保証は無く、本 hard floor は
empirical 検証 (dry-run audit) によって gating される設計に変更。
未達なら A2 (corpus drop) / A6 (hybrid) への pivot が必要。
"""

DE_MASS_MIN_V5: Final[float] = 0.40
"""β rebalance で達成すべき de weighted mass の下限.

v4 baseline 0.385 から +0.015pt の僅増。ja が下がった分 de が相対浮上
で 0.42-0.44 になる見込み。`DE_EN_MASS_MIN_V5=0.85` だけだと en が
独り占めする corner case を防ぐ guard。
"""

V5_GATE_FAIL_EXIT_CODE: Final[int] = 9
"""v5 gate fail 時の exit code.

既存 ``plan_b_gate.GATE_FAIL_EXIT_CODE=8`` (既存 gate fail) と
区別するため独立 code を採用。本 exit code が出る場合の next step は
A1 hyperparam が target を満たせなかったことを意味し、A2 / A6
hybrid 等の別 hyperparam 案を検討する。
"""

V5_GATE_SCHEMA_VERSION: Final[int] = 1
"""``plan-b-corpus-gate-v5.json`` の schema version."""


def audit_corpus_v5(
    weight_audit: dict[str, Any],
    *,
    weight_audit_path: str,
    merge_sha: str,
    de_en_mass_min: float = DE_EN_MASS_MIN_V5,
    ja_mass_max: float = JA_MASS_MAX_V5,
    de_mass_min: float = DE_MASS_MIN_V5,
) -> dict[str, Any]:
    """Apply the 3-axis β rebalance hard gate to a parsed weight-audit.

    Pure function — IO / argparse plumbing lives in the
    ``train_kant_lora._pre_training_audit`` consumer. Returns the gate-
    verdict dict to be serialised as ``plan-b-corpus-gate-v5.json``
    alongside the existing ``plan-b-corpus-gate.json``.

    Threshold kwargs are retained on the pure function so unit tests can
    exercise boundary behaviour without monkey-patching module-level
    constants — mirroring the kwargs pattern of
    :func:`erre_sandbox.training.plan_b_gate.audit_corpus`. The production
    consumer (``--plan-b-gate-v5`` flag) binds the module-level constants;
    no CLI flag exposes the thresholds for post-hoc adjustment
    (preregistered gates must not be movable post-hoc).

    Args:
        weight_audit: Parsed ``weight-audit.json`` dict from
            :func:`erre_sandbox.training.weighting.emit_weight_audit`.
            Must contain ``per_language_weighted_mass`` with keys ``de``,
            ``en``, ``ja`` (``mixed`` is ignored).
        weight_audit_path: Filesystem path the parsed audit came from
            (recorded in the output dict for traceability).
        merge_sha: Git SHA / merge identifier (recorded in the output).
        de_en_mass_min: Lower bound on combined de+en weighted mass
            (defaults to module constant; tests may override).
        ja_mass_max: Upper bound on ja weighted mass (defaults to module
            constant; tests may override).
        de_mass_min: Lower bound on de weighted mass (defaults to module
            constant; tests may override).

    Returns:
        Verdict dict matching the v5 gate schema:

        .. code-block:: json

            {
              "schema_version": 1,
              "v5_gate": "pass" | "fail",
              "thresholds": {"de_en_mass_min": ..., "ja_mass_max": ...,
                              "de_mass_min": ...},
              "achieved": {"de_en_mass": ..., "de_mass": ..., "en_mass": ...,
                           "ja_mass": ...},
              "failed_axes": ["de_en_mass_v5" | "ja_mass_v5" | "de_mass_v5"],
              "weight_audit_path": ...,
              "merge_sha": ...,
              "captured_at_utc": "2026-..."
            }
    """
    lang_mass_obj = weight_audit.get("per_language_weighted_mass", {})
    if not isinstance(lang_mass_obj, dict):
        lang_mass_obj = {}
    de_mass = float(lang_mass_obj.get("de", 0.0))
    en_mass = float(lang_mass_obj.get("en", 0.0))
    ja_mass = float(lang_mass_obj.get("ja", 1.0))
    de_en_mass = de_mass + en_mass

    failed_axes: list[str] = []
    if de_en_mass < de_en_mass_min:
        failed_axes.append("de_en_mass_v5")
    if ja_mass > ja_mass_max:
        failed_axes.append("ja_mass_v5")
    if de_mass < de_mass_min:
        failed_axes.append("de_mass_v5")

    return {
        "schema_version": V5_GATE_SCHEMA_VERSION,
        "v5_gate": "pass" if not failed_axes else "fail",
        "thresholds": {
            "de_en_mass_min": de_en_mass_min,
            "ja_mass_max": ja_mass_max,
            "de_mass_min": de_mass_min,
        },
        "achieved": {
            "de_en_mass": de_en_mass,
            "de_mass": de_mass,
            "en_mass": en_mass,
            "ja_mass": ja_mass,
        },
        "failed_axes": failed_axes,
        "weight_audit_path": weight_audit_path,
        "merge_sha": merge_sha,
        "captured_at_utc": datetime.now(UTC).isoformat(),
    }


__all__ = [
    "DE_EN_MASS_MIN_V5",
    "DE_MASS_MIN_V5",
    "JA_MASS_MAX_V5",
    "V5_GATE_FAIL_EXIT_CODE",
    "V5_GATE_SCHEMA_VERSION",
    "audit_corpus_v5",
]

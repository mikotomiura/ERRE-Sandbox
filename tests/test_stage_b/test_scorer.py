"""Stage B scorer (prereg §3–§6) の合成対照と判定 rule の test.

実モデルは使わない。個体は選択の件数を直接指定して作る (手で計算できる形)。
lever 記録の C_lever は scorer でなく手計算の literal で書く
(fixture が checker を写さない)。

prereg §4 の power 定義は ~0.5 で頭打ち (decisions DB-1) なので、PASS / NO_GO の
分岐を通す test では ``mod.power`` を R ごとの固定値に差し替える。power 模擬
そのものは別の test で実物を検査する。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scripts import stage_b_scorer as mod

K = 10
# B1 certification の照合相手は scorer の実ファイル (checker の関数を経由しない)
SCORER_SHA256 = hashlib.sha256(Path(mod.__file__).read_bytes()).hexdigest()
R_MAX = 8
PROBES = (
    mod.Probe("t0", ("opt_a", "opt_b", "opt_c", "opt_d"), "opt_a", "opt_b"),
    mod.Probe("t1", ("opt_b", "opt_a", "opt_d", "opt_c"), "opt_a", "opt_b"),
    mod.Probe("t2", ("opt_c", "opt_d", "opt_a", "opt_b"), "opt_c", "opt_d"),
    mod.Probe("t3", ("opt_d", "opt_c", "opt_b", "opt_a"), "opt_c", "opt_d"),
)
SIGS = {
    "t0": ("rain", "dusk", "paired"),
    "t1": ("rain", "noon", "alone"),
    "t2": ("clear", "dawn", "paired"),
    "t3": ("clear", "dusk", "alone"),
}
DEV = frozenset({("rain", "dawn", "alone"), ("clear", "noon", "paired")})
ORDER = tuple(p.probe_id for p in PROBES)

Counts = tuple[int, int, int]  # (g_A 件数, g_B 件数, ⊥ 件数) per probe; 残りは other


def _other(p: mod.Probe) -> str:
    return next(o for o in p.omega if o not in (p.g_a, p.g_b))


def ind(
    ind_id: str, stream: str, rep: int, counts: Counts, seed: int | None = None
) -> mod.Individual:
    n_a, n_b, n_bot = counts
    assert n_a + n_b + n_bot <= K
    choices = {
        p.probe_id: tuple(
            [p.g_a] * n_a
            + [p.g_b] * n_b
            + [None] * n_bot
            + [_other(p)] * (K - n_a - n_b - n_bot)
        )
        for p in PROBES
    }
    return mod.Individual(
        ind_id, stream, rep, seed if seed is not None else 1000 + rep, ORDER, choices
    )


def group(prefix: str, stream: str, counts: list[Counts], start: int = 0) -> list:
    return [ind(f"{prefix}{n}", stream, start + n, c) for n, c in enumerate(counts)]


def mirror(counts: list[Counts]) -> list[Counts]:
    return [(b, a, bot) for a, b, bot in counts]


# D = r^A − r^B: .8 .7 .9 .6 → C = .75、完全分離 p = 1/70
DI_A: list[Counts] = [(9, 1, 0), (8, 1, 0), (9, 0, 0), (8, 2, 0)]
# lever: D = .7 .6 .6 .8 → C_lever = .675、δ_min = .3375
LEVER_A: list[Counts] = [(8, 1, 0), (8, 2, 0), (7, 1, 0), (9, 1, 0)]
LEVER_C = 0.675
NULL8: list[Counts] = [(5, 5, 0)] * 8


def di_from(a: list[Counts], b: list[Counts]) -> list[mod.Individual]:
    return group("a", "A", a) + group("b", "B", b, start=len(a))


def ablation_from(di: list[mod.Individual], counts: list[Counts]) -> list:
    return [
        ind(i.ind_id, i.stream, i.replicate, c, seed=i.seed)
        for i, c in zip(di, counts, strict=True)
    ]


def write_records(
    tmp_path: Path,
    lever_a: list[Counts] = LEVER_A,
    lever_c: float = LEVER_C,
    *,
    b_pre: bool = True,
    r_max: int = R_MAX,
    tag: str = "",
    certified: bool = True,
) -> mod.RecordPaths:
    lever = group("l", "A", lever_a) + group("m", "B", mirror(lever_a), start=4)
    lever_path = tmp_path / f"lever{tag}.json"
    lever_path.write_text(
        json.dumps(
            {
                "C_lever": lever_c,
                "individuals": [mod.individual_to_json(i) for i in lever],
            }
        ),
        encoding="utf-8",
    )
    bpre = tmp_path / f"bpre{tag}.json"
    bpre.write_text(json.dumps({"b_pre_established": b_pre}), encoding="utf-8")
    appr = tmp_path / f"approval{tag}.json"
    appr.write_text(json.dumps({"R_max": r_max}), encoding="utf-8")
    cert = tmp_path / f"b1_cert{tag}.json"
    cert.write_text(
        json.dumps(
            {
                "all_killed": certified,
                "target_sha256": {"stage_b_scorer.py": SCORER_SHA256},
            }
        ),
        encoding="utf-8",
    )
    return mod.RecordPaths(lever_path, bpre, appr, cert)


def data_from(
    di: list[mod.Individual],
    abl: list[mod.Individual],
    ci: list[mod.Individual] | None = None,
    snapshot_text: str = "条件: rain / dawn / alone → 行動: opt_a (成功 3 / 失敗 0)",
    preconditions: tuple[tuple[str, ...], ...] = (("rain", "dawn", "alone"),),
) -> mod.StageBData:
    if ci is None:
        ci = group("c", "A", NULL8)
    return mod.StageBData(
        probes=PROBES,
        probe_signatures=SIGS,
        dev_signatures=DEV,
        di=tuple(di),
        di_ablation=tuple(abl),
        ci=tuple(ci),
        snapshots=(mod.Snapshot("a0", preconditions, snapshot_text),),
        probe_prompts=("状況: 天候=rain。行動名だけを答えよ: opt_a、opt_b",),
    )


@pytest.fixture
def stub_power(monkeypatch: pytest.MonkeyPatch):
    """lever 十分性 (plan_r) と実現 power を固定値に (DB-1 の頭打ちを迂回)."""

    def install(lever: float = 0.95, realized: float = 0.95) -> None:
        def fake_plan(*_args: Any) -> int | None:
            return mod.R_MIN if lever >= mod.POWER_TARGET else None

        def fake_power(*_args: Any) -> float:
            return realized

        monkeypatch.setattr(mod, "plan_r", fake_plan)
        monkeypatch.setattr(mod, "power", fake_power)

    return install


def run(data: mod.StageBData, records: mod.RecordPaths) -> dict[str, Any]:
    out = mod.evaluate(data, records, n_power_sims=50)
    assert out["verdict"] in mod.VERDICTS
    return out


def good_di() -> list[mod.Individual]:
    return di_from(DI_A, mirror(DI_A))


def null_ablation(di: list[mod.Individual]) -> list[mod.Individual]:
    return ablation_from(di, [(5, 5, 0), (4, 5, 0), (5, 4, 0), (5, 5, 0)] * 2)


# ------------------------------------------------------------ estimand


def test_rates_count_bottom_in_denominator_only() -> None:
    """⊥ (None と Ω_q 外) は分母に入り、整合にも other にも数えない (§6 m6)."""
    p = PROBES[0]
    x = mod.Individual(
        "x",
        "A",
        0,
        0,
        ("t0",),
        {"t0": ("opt_a",) * 4 + ("opt_b",) * 2 + (None,) * 2 + ("zzz",) + ("opt_c",)},
    )
    r = mod.rates(mod.category_counts(x, [p]))
    assert r.tolist() == pytest.approx([0.4, 0.2, 0.1, 0.3])


def test_unequal_k_is_rejected() -> None:
    x = mod.Individual("x", "A", 0, 0, ORDER, {"t0": ("opt_a",), "t1": ("opt_a",) * 2})
    with pytest.raises(ValueError, match="K must be equal"):
        mod.category_counts(x, PROBES[:2])


def test_contrast_matches_definition() -> None:
    di = good_di()
    d, is_a = mod.unit_scores(di, PROBES)
    s = np.where(is_a, d, -d)
    c, c_a, c_b = mod.contrast(d, is_a)
    assert c_a == pytest.approx(float(np.mean(s[is_a])))
    assert c_b == pytest.approx(float(np.mean(s[~is_a])))
    assert c == pytest.approx((c_a + c_b) / 2)
    assert c == pytest.approx(0.75)


def test_alignment_direction_positive_control() -> None:
    """A 個体が g_A 寄り・B 個体が g_B 寄り → C > 0 (§6 m2: 整合対応の反転を kill)."""
    d, is_a = mod.unit_scores(good_di(), PROBES)
    assert d[is_a].tolist() == pytest.approx([0.8, 0.7, 0.9, 0.6])
    assert mod.contrast(d, is_a)[0] > 0


# ---------------------------------------------------------------- tests


def test_perm_p_exact_includes_observed() -> None:
    """完全分離 R=4 → p = 1/70 (観測割当を分子・分母に含む、§6 m12)."""
    d, is_a = mod.unit_scores(good_di(), PROBES)
    assert mod.perm_p(d, is_a) == pytest.approx(1 / 70)


def test_anti_aligned_is_one_sided_not_significant() -> None:
    """経験と逆向き (C < 0) は片側検定で有意にならない (§6 m4: |C| を kill)."""
    di = di_from(mirror(DI_A), DI_A)
    d, is_a = mod.unit_scores(di, PROBES)
    c, _, _ = mod.contrast(d, is_a)
    assert c == pytest.approx(-0.75)
    assert mod.perm_p(d, is_a) == pytest.approx(1.0)


def test_n1_false_positive_rate_matches_alpha() -> None:
    """(n1) 効果 0 の置換偽陽性率 = 0.05 ± 0.01.

    10^4 回模擬、R = 5 で離散 α = 12/252。
    """
    rng = np.random.default_rng(7)
    is_a = np.array([True] * 5 + [False] * 5)
    hits = sum(mod.perm_p(rng.normal(size=10), is_a) < mod.ALPHA for _ in range(10_000))
    assert 0.04 <= hits / 10_000 <= 0.06


# n2: 個体ごとの変位 ±.9 / ∓.3 が stream 内で混在。
# D = .9 −.3 .9 −.3 | −.9 .3 −.9 .3 → C = .3
N2_A: list[Counts] = [(9, 0, 0), (3, 6, 0), (9, 0, 0), (3, 6, 0)]
N2_B: list[Counts] = [(0, 9, 0), (6, 3, 0), (0, 9, 0), (6, 3, 0)]


def test_n2_individual_displacement_unrelated_to_stream() -> None:
    """(n2) M11-C3b 型: 個体の変位は大きいが方向が stream と無関係.

    個体単位の置換 p は大きい (§6 m1)。
    """
    di = di_from(N2_A, N2_B)
    d, is_a = mod.unit_scores(di, PROBES)
    assert mod.contrast(d, is_a)[0] == pytest.approx(0.3)
    assert mod.perm_p(*mod.permutation_units(di, PROBES, is_a)) == pytest.approx(
        14 / 70
    )


def test_signflip_exact() -> None:
    assert mod.signflip_p(np.full(8, 0.1)) == pytest.approx(1 / 256)
    d = np.array([1.4, 1.4, -0.1, -0.4, 1.4, 1.4, -0.1, -0.4])
    assert mod.signflip_p(d) == pytest.approx(16 / 256)


def test_pseudo_labels_are_fixed_permutation_halves() -> None:
    ci = group("c", "A", NULL8)
    is_a = mod.pseudo_labels(ci)
    perm = np.random.default_rng(20260926).permutation(8)
    assert sorted(np.flatnonzero(is_a).tolist()) == sorted(perm[:4].tolist())
    shuffled = list(reversed(ci))
    assert mod.pseudo_labels(shuffled)[::-1].tolist() == is_a.tolist()


def test_bottom_bound() -> None:
    r_bot = np.array([0.3, 0.3, 0.3, 0.3, 0.0, 0.1, 0.0, 0.1])
    is_a = np.array([True] * 4 + [False] * 4)
    assert mod.bottom_bound(r_bot, is_a) == pytest.approx(0.25)


# ----------------------------------------------------------------- power


def test_inject_moves_mass_within_simplex() -> None:
    p = np.array([[[0.02, 0.9, 0.05, 0.03]], [[0.9, 0.02, 0.05, 0.03]]])
    out = mod.inject(mod.symmetrize(p), np.array([True, False]), 0.6)
    assert out[0, 0].tolist() == pytest.approx([0.76, 0.16, 0.05, 0.03])
    assert out[1, 0].tolist() == pytest.approx([0.16, 0.76, 0.05, 0.03])
    clamp = mod.inject(np.array([[[0.1, 0.1, 0.5, 0.3]]]), np.array([True]), 0.6)
    assert clamp[0, 0].tolist() == pytest.approx([0.2, 0.0, 0.5, 0.3])


def test_simulated_individuals_stay_in_simplex() -> None:
    """(§6 m15) 模擬の率は常に simplex 内 (s への直接加算は simplex を出る)."""
    pool = np.tile(np.array([0.97, 0.01, 0.01, 0.01]), (6, 4, 1))
    rng = np.random.default_rng(3)
    for _ in range(50):
        r, is_a = mod.simulate_once(pool, 4, K, 0.8, rng)
        assert is_a.sum() == 4
        assert np.all(r >= 0)
        assert np.all(r <= 1)
        assert r.sum(axis=1) == pytest.approx(np.ones(8))


def test_power_ceiling_under_prereg_definition() -> None:
    """decisions DB-1: 効果 = δ_min を植えて Ĉ ≥ δ_min を問う → power ~0.5 で頭打ち."""
    pool = np.tile(np.array([0.4, 0.4, 0.15, 0.05]), (16, 12, 1))
    for r in (4, 8):
        assert 0.35 <= mod.power(pool, r, 50, 0.2, n_sims=300) <= 0.65


def test_power_is_zero_without_room_to_move() -> None:
    """g_A / g_B に質量が無ければ注入できず、PASS 条件は通らない."""
    pool = np.tile(np.array([0.0, 0.0, 0.9, 0.1]), (8, 4, 1))
    assert mod.power(pool, 4, K, 0.2, n_sims=50) == 0.0


def test_power_default_sims_is_prereg_value() -> None:
    assert mod.N_POWER_SIMS == 10_000
    assert mod.ALPHA == 0.05
    assert mod.POWER_TARGET == 0.8


def test_core_pass_positive_control_sampled() -> None:
    """陽性対照 (合成・sample 抽出): 個体の揺らぎ (TV ~0.1) の上で大きな δ を検出."""
    rng = np.random.default_rng(11)
    rows = []
    is_a = np.array([True] * 6 + [False] * 6)
    for a in is_a:
        jitter = rng.uniform(-0.1, 0.1)
        p = (
            [0.7 + jitter, 0.1, 0.15 - jitter, 0.05]
            if a
            else [0.1, 0.7 + jitter, 0.15 - jitter, 0.05]
        )
        rows.append(rng.multinomial(40, p) / 40)
    assert mod.core_pass(np.array(rows), is_a, 0.3)


# --------------------------------------------------------------- verdict


def test_positive_control_passes(tmp_path: Path, stub_power) -> None:
    stub_power()
    di = good_di()
    out = run(data_from(di, null_ablation(di)), write_records(tmp_path))
    assert out["verdict"] == mod.VERDICT_PASS
    assert out["delta_min"] == pytest.approx(LEVER_C / 2)


def test_n1_no_effect_is_not_pass(tmp_path: Path, stub_power) -> None:
    stub_power()
    di = di_from(NULL8[:4], NULL8[4:])
    out = run(data_from(di, null_ablation(di)), write_records(tmp_path))
    assert out["verdict"] == mod.VERDICT_ABSENT


def test_n2_random_direction_is_not_pass(tmp_path: Path, stub_power) -> None:
    """(n2) δ_min が小さく ablation も通っても、個体単位の置換で PASS しない (§6 m1)."""
    stub_power()
    di = di_from(N2_A, N2_B)
    # s を一様に .2 下げる: s = .9 −.3 .9 −.3 → .7 −.5 .7 −.5 (両 stream)
    abl = ablation_from(
        di,
        [
            *[(7, 0, 0), (2, 7, 0), (7, 0, 0), (2, 7, 0)],
            *[(0, 7, 0), (7, 2, 0), (0, 7, 0), (7, 2, 0)],
        ],
    )
    lever = [(3, 0, 0)] * 4  # D .3 → C_lever .3、δ_min .15
    out = run(data_from(di, abl), write_records(tmp_path, lever, 0.3))
    assert out["delta_min"] == pytest.approx(0.15)
    assert out["C"] >= out["delta_min"]
    assert out["pass_conditions"]["both_components"] is True
    assert out["pass_conditions"]["ablation_point"] is True
    assert out["pass_conditions"]["ablation_paired"] is True
    assert out["pass_conditions"]["di_permutation"] is False
    assert out["verdict"] == mod.VERDICT_ABSENT


def test_n3_one_sided_effect_is_not_pass(tmp_path: Path, stub_power) -> None:
    """(n3) C_A > 0・C_B = 0 で平均 C は δ_min を超える → PASS しない (§6 m5)."""
    stub_power()
    a: list[Counts] = [(9, 0, 0), (8, 0, 0), (9, 0, 0), (8, 0, 0)]
    b: list[Counts] = [(5, 4, 0), (4, 5, 0), (5, 4, 0), (4, 5, 0)]
    di = di_from(a, b)
    abl = ablation_from(
        di,
        [
            *[(6, 0, 0), (5, 0, 0), (6, 0, 0), (5, 0, 0)],
            *[(4, 0, 0), (4, 2, 0), (4, 0, 0), (4, 2, 0)],
        ],
    )
    out = run(data_from(di, abl), write_records(tmp_path))
    assert out["C_A"] == pytest.approx(0.85)
    assert out["C_B"] == pytest.approx(0.0)
    assert out["C"] >= out["delta_min"]
    assert out["pass_conditions"]["both_components"] is False
    assert out["verdict"] == mod.VERDICT_ABSENT


def test_n4_leaked_snapshot_is_invalid_scorer(tmp_path: Path, stub_power) -> None:
    """(n4) probe signature と一致する precondition → INVALID_SCORER (§6 m14)."""
    stub_power()
    di = good_di()
    data = data_from(di, null_ablation(di), preconditions=(("rain", "dusk", "paired"),))
    out = run(data, write_records(tmp_path))
    assert out["verdict"] == mod.VERDICT_INVALID_SCORER
    assert out["reasons"] == ["non_leakage_integrity"]


@pytest.mark.parametrize(
    "text",
    [
        "条件: rain / dusk / paired → 行動: opt_a",  # probe signature
        "t2 を覚えておく",  # probe id
        "stream_a の個体",  # stream id
        "個体 A の記録",  # bare stream id
    ],
)
def test_integrity_forbidden_strings(text: str) -> None:
    di = good_di()
    assert mod.integrity_violations(
        data_from(di, null_ablation(di), snapshot_text=text)
    )


def test_integrity_rejects_unseen_precondition() -> None:
    di = good_di()
    data = data_from(di, null_ablation(di), preconditions=(("wind", "dawn", "alone"),))
    assert mod.integrity_violations(data)


def test_integrity_clean_draft_has_no_violation() -> None:
    di = good_di()
    assert mod.integrity_violations(data_from(di, null_ablation(di))) == []


def test_ci_separation_is_invalid_scorer(tmp_path: Path, stub_power) -> None:
    """CI 陰性対照が疑似ラベルで分離 → INVALID_SCORER (§6 m8)."""
    stub_power()
    ci = group("c", "A", NULL8)
    is_a = mod.pseudo_labels(ci)
    sep = [(9, 1, 0) if a else (1, 9, 0) for a in is_a]
    ci = [ind(f"c{n}", "A", n, c) for n, c in enumerate(sep)]
    di = good_di()
    out = run(data_from(di, null_ablation(di), ci=ci), write_records(tmp_path))
    assert out["ci_pseudo_p"] < mod.ALPHA
    assert out["verdict"] == mod.VERDICT_INVALID_SCORER
    assert out["reasons"] == ["ci_negative_control_separates"]


def test_delta_min_is_read_from_lever_record(tmp_path: Path, stub_power) -> None:
    """権威ファイル (lever 記録) を変えると判定が変わる (§6 m7)."""
    stub_power()
    weak: list[Counts] = [(5, 0, 0), (4, 0, 0), (5, 0, 0), (4, 0, 0)]  # D .5 .4 → C .45
    di = di_from(weak, mirror(weak))
    abl = null_ablation(di)
    strong = [(10, 0, 0)] * 4  # C_lever 1.0 → δ_min .5
    base = run(data_from(di, abl), write_records(tmp_path, tag="1"))
    moved = run(data_from(di, abl), write_records(tmp_path, strong, 1.0, tag="2"))
    assert base["verdict"] == mod.VERDICT_PASS
    assert moved["delta_min"] == pytest.approx(0.5)
    assert moved["verdict"] == mod.VERDICT_ABSENT


def test_c_below_delta_min_is_not_pass(tmp_path: Path, stub_power) -> None:
    """p < 0.05・両成分 > 0・ablation 成立でも C < δ_min なら PASS しない (§6 m9)."""
    stub_power()
    weak: list[Counts] = [(5, 0, 0), (4, 0, 0), (5, 0, 0), (4, 0, 0)]
    di = di_from(weak, mirror(weak))
    out = run(
        data_from(di, null_ablation(di)), write_records(tmp_path, [(10, 0, 0)] * 4, 1.0)
    )
    assert out["pass_conditions"] == {
        "di_permutation": True,
        "delta_min": False,
        "both_components": True,
        "ablation_point": True,
        "ablation_paired": True,
    }
    assert out["verdict"] == mod.VERDICT_ABSENT


def test_lever_record_inconsistent_is_invalid_scorer(
    tmp_path: Path, stub_power
) -> None:
    stub_power()
    di = good_di()
    out = run(data_from(di, null_ablation(di)), write_records(tmp_path, lever_c=0.5))
    assert out["verdict"] == mod.VERDICT_INVALID_SCORER
    assert out["reasons"] == ["lever_record_inconsistent"]


def test_bottom_gap_in_di_is_invalid_battery(tmp_path: Path, stub_power) -> None:
    """b_DI ≥ δ_min/2 → INVALID_TASK_BATTERY (§6 m10)."""
    stub_power()
    a: list[Counts] = [(6, 1, 3), (5, 1, 3), (6, 0, 3), (5, 2, 3)]
    di = di_from(a, mirror(DI_A))
    out = run(data_from(di, null_ablation(di)), write_records(tmp_path))
    assert out["b_di"] == pytest.approx(0.3)
    assert out["verdict"] == mod.VERDICT_INVALID_BATTERY
    assert out["reasons"] == ["bottom_bound"]


def test_bottom_gap_in_lever_is_invalid_battery(tmp_path: Path, stub_power) -> None:
    stub_power()
    di = good_di()
    lever = group("l", "A", [(7, 0, 3)] * 4) + group("m", "B", [(0, 7, 0)] * 4, start=4)
    records = write_records(tmp_path)
    records.lever_record.write_text(
        json.dumps(
            {"C_lever": 0.7, "individuals": [mod.individual_to_json(i) for i in lever]}
        ),
        encoding="utf-8",
    )
    out = run(data_from(di, null_ablation(di)), records)
    assert out["b_lever"] == pytest.approx(0.3)
    assert out["verdict"] == mod.VERDICT_INVALID_BATTERY


def test_weak_lever_is_invalid_battery(tmp_path: Path, stub_power) -> None:
    stub_power(lever=0.5)
    di = good_di()
    out = run(data_from(di, null_ablation(di)), write_records(tmp_path))
    assert out["verdict"] == mod.VERDICT_INVALID_BATTERY
    assert out["reasons"] == ["lever_insufficient"]


def test_b_pre_not_established_is_invalid_battery(tmp_path: Path, stub_power) -> None:
    stub_power()
    di = good_di()
    out = run(data_from(di, null_ablation(di)), write_records(tmp_path, b_pre=False))
    assert out["reasons"] == ["b_pre_not_established"]


def test_missing_b_pre_record_is_not_established(tmp_path: Path) -> None:
    assert mod.load_b_pre(tmp_path / "absent.json") is False


def test_ablation_retaining_effect_is_not_pass(tmp_path: Path, stub_power) -> None:
    """Skill を外しても効果が残る → PASS しない (§6 m3)."""
    stub_power()
    di = good_di()
    out = run(
        data_from(di, ablation_from(di, DI_A + mirror(DI_A))), write_records(tmp_path)
    )
    assert out["C_abl"] == pytest.approx(out["C"])
    assert out["verdict"] == mod.VERDICT_ABSENT


def test_ablation_point_estimate_required(tmp_path: Path, stub_power) -> None:
    """paired 検定は通るが C_abl > C/2 → PASS しない (§6 m13 点推定)."""
    stub_power()
    di = good_di()
    # s を一様に .1 下げる: A は D − .1、B は D + .1
    abl = ablation_from(
        di,
        [
            *[(8, 1, 0), (7, 1, 0), (8, 0, 0), (7, 2, 0)],
            *[(1, 8, 0), (1, 7, 0), (0, 8, 0), (2, 7, 0)],
        ],
    )
    out = run(data_from(di, abl), write_records(tmp_path))
    assert out["paired_p"] < mod.ALPHA
    assert out["C_abl"] == pytest.approx(0.65)
    assert out["verdict"] == mod.VERDICT_ABSENT


def test_ablation_paired_test_required(tmp_path: Path, stub_power) -> None:
    """C_abl ≤ C/2 だが paired 差の符号反転 p ≥ 0.05 → PASS しない (§6 m13 paired)."""
    stub_power()
    di = good_di()
    # s_abl = [-.6, -.7, 1.0, 1.0] (両 stream) → d = [1.4, 1.4, -.1, -.4] × 2
    abl = ablation_from(
        di,
        [
            *[(2, 8, 0), (1, 8, 0), (10, 0, 0), (10, 0, 0)],
            *[(8, 2, 0), (8, 1, 0), (0, 10, 0), (0, 10, 0)],
        ],
    )
    out = run(data_from(di, abl), write_records(tmp_path))
    assert out["C_abl"] == pytest.approx(0.175)
    assert out["paired_p"] == pytest.approx(16 / 256)
    assert out["verdict"] == mod.VERDICT_ABSENT


def test_ablation_with_other_seed_is_invalid(tmp_path: Path, stub_power) -> None:
    """ablation は同じ decoding seed の paired でなければならない (§6 m13 unpaired)."""
    stub_power()
    di = good_di()
    abl = [replace(i, seed=i.seed + 1) for i in null_ablation(di)]
    out = run(data_from(di, abl), write_records(tmp_path))
    assert out["verdict"] == mod.VERDICT_INVALID_SCORER
    assert out["reasons"] == ["ablation_not_paired"]


def test_ablation_with_other_probe_order_is_invalid() -> None:
    di = good_di()
    abl = [replace(i, probe_order=tuple(reversed(ORDER))) for i in null_ablation(di)]
    assert mod.ablation_pairing_violations(di, abl)


def test_low_realized_power_is_inconclusive(tmp_path: Path, stub_power) -> None:
    """PASS でなく実現 power < 0.8 → INCONCLUSIVE_UNDERPOWERED (§6 m11)."""
    stub_power(realized=0.3)
    di = di_from(NULL8[:4], NULL8[4:])
    out = run(data_from(di, null_ablation(di)), write_records(tmp_path))
    assert out["realized_power"] == pytest.approx(0.3)
    assert out["verdict"] == mod.VERDICT_UNDERPOWERED


def test_high_realized_power_is_absent(tmp_path: Path, stub_power) -> None:
    stub_power(realized=0.9)
    di = di_from(NULL8[:4], NULL8[4:])
    out = run(data_from(di, null_ablation(di)), write_records(tmp_path))
    assert out["verdict"] == mod.VERDICT_ABSENT


def test_anti_aligned_is_not_pass(tmp_path: Path, stub_power) -> None:
    stub_power()
    di = di_from(mirror(DI_A), DI_A)
    out = run(data_from(di, null_ablation(di)), write_records(tmp_path))
    assert out["C"] == pytest.approx(-0.75)
    assert out["verdict"] == mod.VERDICT_ABSENT


def test_literal_prereg_power_blocks_lever(tmp_path: Path) -> None:
    """decisions DB-1: 実物の power では lever 十分性が満たせず INVALID_TASK_BATTERY."""
    di = good_di()
    out = mod.evaluate(data_from(di, null_ablation(di)), write_records(tmp_path), 200)
    assert out["lever_planned_r"] is None
    assert out["verdict"] == mod.VERDICT_INVALID_BATTERY
    assert out["reasons"] == ["lever_insufficient"]


def test_internal_sanity_gate_passes() -> None:
    assert mod.internal_sanity_gate() is True


@pytest.mark.parametrize(
    ("kwargs", "body"),
    [
        ({"certified": False}, None),
        ({}, {"all_killed": True, "target_sha256": {"stage_b_scorer.py": "0" * 64}}),
        ({}, "not json"),
    ],
)
def test_b1_certification_is_required(
    tmp_path: Path, stub_power, kwargs: dict[str, Any], body: object
) -> None:
    """§5-1: B1 の §6 検査記録が無い・不合格・別版の scorer → INVALID_SCORER."""
    stub_power()
    records = write_records(tmp_path, **kwargs)
    if body is not None:
        text = body if isinstance(body, str) else json.dumps(body)
        records.b1_certification.write_text(text, encoding="utf-8")
    di = good_di()
    out = run(data_from(di, null_ablation(di)), records)
    assert out["verdict"] == mod.VERDICT_INVALID_SCORER
    assert out["reasons"] == ["b1_certification_missing_or_failed"]


def test_k_mismatch_is_invalid_scorer(tmp_path: Path, stub_power) -> None:
    stub_power()
    di = good_di()
    x = di[0]
    short = {q: v[:5] for q, v in x.choices.items()}
    ci = [
        replace(c, choices=short) if n == 0 else c
        for n, c in enumerate(group("c", "A", NULL8))
    ]
    out = run(data_from(di, null_ablation(di), ci=ci), write_records(tmp_path))
    assert out["verdict"] == mod.VERDICT_INVALID_SCORER
    assert out["reasons"] == ["k_or_r_inconsistent"]


def test_unbalanced_di_is_invalid_scorer(tmp_path: Path, stub_power) -> None:
    """DI は各 stream R (≥ 4) 個体。R/R でない → INVALID_SCORER."""
    stub_power()
    di = di_from([*DI_A, (9, 1, 0)], mirror(DI_A))
    abl = ablation_from(di, [(5, 5, 0)] * 9)
    out = run(data_from(di, abl), write_records(tmp_path))
    assert out["reasons"] == ["k_or_r_inconsistent"]


def test_plan_r_is_none_under_prereg_ceiling() -> None:
    pool = np.tile(np.array([0.4, 0.4, 0.15, 0.05]), (8, 4, 1))
    assert mod.plan_r(pool, K, 0.2, 5, n_sims=50) is None

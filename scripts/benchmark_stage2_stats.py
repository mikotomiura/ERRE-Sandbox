"""判別性 gate 段 2 — 区間・判定表・split-half・帯・感度・R の選定・予算 (CPU のみ)。

規則の SSOT は ``experiments/20261126-benchmark-stage2-discriminability/prereg.md``
(第 1 段 PILOT-FROZEN)。本 module の定数はその写しで、食い違えば prereg が正しい。

- 凍結 dir と ``scripts/`` の 4 battery は import だけにする (書き換えない)。
- 区間: 有界な独立な単位の平均に対する、固定 λ の格子の混合 betting e-value の反転。
  size は有界と独立だけから定理で守る (prereg §D)。
- 次のタスクの判別性 scorer・pilot gate は本 module を import して certify する。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Final

import numpy as np
from scripts import benchmark_stage1_reanalysis as s1

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# ------------------------------------------------------------ 凍結の定数 (prereg の写し)

ALPHA: Final[float] = 0.05  # family-wise
DELTA_MIN: Final[float] = 0.10  # DU-9
EQUIV: Final[float] = 0.10  # 同等域 ±0.10 (DU-9)
POWER: Final[float] = 0.8
PLAN_GAP: Final[float] = 2.0 * DELTA_MIN  # 計画の形: 1 対が 2Δ_min 離れる
N_LAMBDA: Final[int] = 12
LAMBDA_TOP: Final[float] = 0.98
LAMBDA_RATIO: Final[float] = 0.7
# λ = c / (m − lo)。c は幾何級数 0.98 · 0.7^j (j = 0..11)。c < 1 なので各因子は正。
LAMBDA_C: Final[np.ndarray] = LAMBDA_TOP * LAMBDA_RATIO ** np.arange(N_LAMBDA)
FLOOR_BAND: Final[tuple[float, float]] = (-0.10, 0.10)
CEILING_BAND: Final[tuple[float, float]] = (0.90, 1.0)
TAU: Final[float] = 0.30  # 各 battery の凍結値 (族内の ⊥ 率の差の上限 τ/4 に使う)
MIN_ENTRANTS: Final[int] = 3
R_PILOT: Final[int] = 12
SIGMA_UP_LEVEL: Final[float] = 0.95
N_SPIKE: Final[int] = 2000
SPIKE_SEED: Final[int] = 20261126
CALIB_TOL: Final[float] = 0.01
FAMILY_FALSE_REJECT: Final[float] = 0.01  # MC の採否の誤棄却の族の率
BUDGET_SECONDS: Final[int] = 3 * 3600  # 1 モデルあたり (8B 換算、DU-6/7)
BISECT_ITERS: Final[int] = 60
QUANT: Final[int] = 12  # 値の同一視の桁 (単位の値は有理数。浮動小数の誤差だけを潰す)

VERDICT_INVALID: Final[str] = "INVALID"
VERDICT_NOT_COMPUTED: Final[str] = "not_computed"
VERDICT_NOT_QUALIFIED: Final[str] = "NOT_QUALIFIED"
VERDICT_ESTABLISHED: Final[str] = "ESTABLISHED"  # (1)
VERDICT_NEGATIVE: Final[str] = "CALIBRATED_NEGATIVE"  # (2)
# (2) で、報告集合が pilot の入場集合より小さいとき (DU-13、attack-me R3)
VERDICT_NEGATIVE_SUBSET: Final[str] = "CALIBRATED_NEGATIVE_ON_SUBSET"
VERDICT_INCONCLUSIVE: Final[str] = "INCONCLUSIVE"  # (3)

GATE_GO: Final[str] = "GO"
GATE_STOP_POWER: Final[str] = "STOP_POWER"
GATE_HELD_COST: Final[str] = "HELD_COST"


@dataclass(frozen=True)
class BatterySpec:
    """battery ごとの、段 2 の割付 (prereg §C・§E・§G)."""

    name: str
    cycle: int  # 表示位置の 1 巡の r の数 (check_position_balance)
    units_per_rep: int  # 1 replicate の独立な単位の数
    calls_per_rep: int  # 1 replicate の本走の呼び出し (対照 arm を含む)
    sec_per_call: Fraction  # 段 1 の秒の表 (qwen3:8b 換算)
    pilot_r0: int
    main_r0: int
    main_r_cap: int | None  # seed の名前空間からくる R の上限 (なしは None)

    @property
    def r_step(self) -> int:
        """R の候補の刻み = split-half の 2 block。"""
        return 2 * self.cycle

    def sec_per_rep(self) -> Fraction:
        return self.calls_per_rep * self.sec_per_call


SPECS: Final[dict[str, BatterySpec]] = {
    "v2": BatterySpec("v2", 4, 60, 300, s1.SEC_PER_CALL["v2"], 1000, 2000, None),
    "v3": BatterySpec("v3", 4, 30, 270, s1.SEC_PER_CALL["v3"], 1200, 3000, None),
    "G": BatterySpec("G", 3, 16, 96, s1.SEC_PER_CALL["G"], 24, 60, 36),
    "O_time": BatterySpec(
        "O_time", 3, 12, 48, s1.SEC_PER_CALL["O_time"], 312, 324, 672
    ),
}
BATTERIES: Final[tuple[str, ...]] = ("v2", "v3", "G", "O_time")
# 使用済みの r の範囲 (段 1 と旧 chain。名前空間は battery の sample_seed が分ける)
USED_R: Final[dict[str, tuple[range, ...]]] = {
    "v2": (range(4),),
    "v3": (range(8),),
    "G": (range(18), range(50, 56)),
    "O_time": (range(288), range(300, 306)),
}


# ------------------------------------------------------------ betting e-value と区間


def support(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """1 次元の値の列を (値, 数) にする。浮動小数の誤差だけを QUANT 桁で潰す."""
    vals, counts = np.unique(
        np.round(np.asarray(x, dtype=float), QUANT), return_counts=True
    )
    return vals, counts.astype(float)


def _logmeanexp(a: np.ndarray) -> np.ndarray:
    mx = np.max(a, axis=-1, keepdims=True)
    return (mx + np.log(np.mean(np.exp(a - mx), axis=-1, keepdims=True)))[..., 0]


def log_e_lower(
    values: np.ndarray, counts: np.ndarray, m: float, lo: float
) -> np.ndarray:
    """帰無 「平均 ≤ m」 に対する混合 e-value の log。値は lo 以上 (lo < m)。

    因子 = 1 + λ_j (x − m)、λ_j = c_j / (m − lo)。counts は (V,) か (N, V)。
    """
    if not m > lo:
        msg = "m must exceed the lower bound of the support"
        raise ValueError(msg)
    if np.any(values < lo - 1e-12):
        msg = "values below the declared lower bound"
        raise ValueError(msg)
    lam = LAMBDA_C / (m - lo)
    terms = np.log1p(np.outer(values - m, lam))  # (V, 12)
    logw = np.asarray(counts, dtype=float) @ terms  # (..., 12)
    return _logmeanexp(logw)


def log_e_upper(
    values: np.ndarray, counts: np.ndarray, m: float, hi: float
) -> np.ndarray:
    """帰無 「平均 ≥ m」 (値は hi 以下)。−x の下側の検定に写す."""
    return log_e_lower(-values[::-1], np.asarray(counts)[..., ::-1], -m, -hi)


def rejects_lower(x: np.ndarray, m: float, lo: float, level: float) -> bool:
    """「平均 ≤ m」 を水準 level で棄却する (= 下限 ≥ m)."""
    v, c = support(x)
    return bool(log_e_lower(v, c, m, lo) >= math.log(1.0 / level))


def rejects_upper(x: np.ndarray, m: float, hi: float, level: float) -> bool:
    """「平均 ≥ m」 を水準 level で棄却する (= 上限 ≤ m)."""
    v, c = support(x)
    return bool(log_e_upper(v, c, m, hi) >= math.log(1.0 / level))


def lower_bound(x: np.ndarray, lo: float, hi: float, level: float) -> float:
    """片側の下限 L = inf{m : E(m) < 1/level}。E は m について非増加 (prereg §D).

    E(m) ≥ 1/level の m が無ければ lo を返す。
    """
    v, c = support(x)
    thr = math.log(1.0 / level)
    a, b = lo, hi
    if float(log_e_lower(v, c, lo + (hi - lo) * 1e-12, lo)) < thr:
        return lo
    for _ in range(BISECT_ITERS):
        mid = (a + b) / 2.0
        if float(log_e_lower(v, c, mid, lo)) >= thr:
            a = mid
        else:
            b = mid
    return a


def upper_bound(x: np.ndarray, lo: float, hi: float, level: float) -> float:
    return -lower_bound(-np.asarray(x, dtype=float), -hi, -lo, level)


# ------------------------------------------------------------ 判定表 (battery ごと)


def ordered_pairs(n_models: int) -> list[tuple[int, int]]:
    return [(a, b) for a in range(n_models) for b in range(n_models) if a != b]


def n_tests(entrants: Mapping[str, int]) -> int:
    """K = 資格を通った battery × モデル対 × 2 方向 (prereg §D)."""
    return sum(m * (m - 1) for m in entrants.values() if m >= MIN_ENTRANTS)


def classify(
    est: np.ndarray,
    rep: np.ndarray,
    equiv: np.ndarray,
    concentrated: np.ndarray,
) -> np.ndarray:
    """判定表 §F の 4〜6 (入場 ≥ 3 の後)。

    est・rep・equiv は (..., P) の真偽 (順序対ごと)、concentrated は (...)。
    - (1): est ∧ rep の順序対があり、集中でない。
    - (2): 全順序対で equiv (下限 ≥ −EQUIV。両方向で区間が同等域の内)。
    - (3): それ以外。
    """
    est = np.asarray(est, dtype=bool)
    ok1 = np.any(est & np.asarray(rep, dtype=bool), axis=-1) & ~np.asarray(
        concentrated, dtype=bool
    )
    ok2 = np.all(np.asarray(equiv, dtype=bool), axis=-1)
    out = np.full(ok1.shape, VERDICT_INCONCLUSIVE, dtype=object)
    out[ok2 & ~ok1] = VERDICT_NEGATIVE
    out[ok1] = VERDICT_ESTABLISHED
    return out


def half_labels(spec: BatterySpec, r_list: Sequence[int]) -> np.ndarray:
    """単位ごとの半分 (0/1)。位置の 1 巡を block にし、block の偶奇で割る (§E)."""
    r0 = r_list[0]
    return np.array(
        [
            ((r - r0) // spec.cycle) % 2
            for r in r_list
            for _ in range(spec.units_per_rep)
        ],
        dtype=int,
    )


def check_r_range(spec: BatterySpec, r_list: Sequence[int], *, main: bool) -> list[str]:
    """R の範囲の機械検査: 連続・始点が 1 巡の倍数・R が 2 巡の倍数・上限・旧記録と交わらない."""
    out = []
    r_list = list(r_list)
    if not r_list or r_list != list(range(r_list[0], r_list[0] + len(r_list))):
        return [f"{spec.name}: r list is empty or not contiguous"]
    if r_list[0] % spec.cycle:
        out.append(f"{spec.name}: r0 is not a multiple of the position cycle")
    step = (
        spec.r_step if main else spec.cycle
    )  # split-half は本走だけ。pilot は位置の 1 巡
    if len(r_list) % step:
        out.append(f"{spec.name}: R is not a multiple of {step}")
    if main:
        if r_list[0] != spec.main_r0:
            out.append(f"{spec.name}: main r0 differs from the registered value")
        if spec.main_r_cap is not None and len(r_list) > spec.main_r_cap:
            out.append(f"{spec.name}: R exceeds the seed-namespace cap")
    elif r_list != list(range(spec.pilot_r0, spec.pilot_r0 + R_PILOT)):
        out.append(f"{spec.name}: pilot r range differs from the registered value")
    used = set().union(*(set(x) for x in USED_R[spec.name]))
    if used & set(r_list):
        out.append(f"{spec.name}: r range overlaps used records")
    return out


@dataclass(frozen=True)
class BatteryDecision:
    verdict: str
    established: tuple[tuple[int, int], ...]
    sensitivity_ok: tuple[tuple[int, int], ...]
    lower_bounds: dict[str, float]
    concentration: str | None
    model_c: tuple[float, ...]
    n_excluded: int = (
        0  # pilot の入場集合から本走の報告集合で外れた本数 (§F、Codex r4 HIGH-3)
    )


def concentration(units: np.ndarray, sum_m: int) -> str | None:
    """全モデルの C の同時区間 (各側 α / (2 ΣM)) が同じ帯に入れば、その帯の名 (§E).

    区間が帯に入る ⟺ 帯の端での片側検定が棄却する (E の単調性)。検定の形で判定する。
    """
    level = ALPHA / (2 * sum_m)
    floor = all(
        rejects_lower(u, FLOOR_BAND[0], -1.0, level)
        and rejects_upper(u, FLOOR_BAND[1], 1.0, level)
        for u in units
    )
    if floor:
        return "floor"
    ceil = all(rejects_lower(u, CEILING_BAND[0], -1.0, level) for u in units)
    return "ceiling" if ceil else None


def _worst_units(counts: np.ndarray, sign: float) -> np.ndarray:
    """(t, f, n) の単位ごとの数から、対の外のセルを sign に割り当てた単位の値."""
    t, f, n = counts[:, 0], counts[:, 1], counts[:, 2]
    return (t - f + sign * (n - t - f)) / n


def decide_battery(
    units: np.ndarray,
    k_tests: int,
    sum_m: int,
    halves: np.ndarray,
    *,
    cell_counts: np.ndarray | None = None,
    invalid: bool = False,
    not_computed: bool = False,
    n_entered: int,
) -> BatteryDecision:
    """1 battery の判定 (§F)。units は (M, n) の入場モデルの単位の値 ([−1, 1]).

    cell_counts は (M, n, 3) の (target, foil, 全セル)。感度条件 (§B) に使う。
    n_entered は pilot の入場集合の本数 (必須、Codex r4 HIGH-3)。報告集合 (units の M) が
    それより小さい (2) は CALIBRATED_NEGATIVE_ON_SUBSET にする (§F)。K と ΣM は入場集合から
    決まる (§E・§F) ので、K ≥ n_entered (n_entered − 1)・ΣM ≥ n_entered を検査する。
    """
    if n_entered < 0 or (
        n_entered >= MIN_ENTRANTS
        and (k_tests < n_entered * (n_entered - 1) or sum_m < n_entered)
    ):
        raise ValueError("K・ΣM が入場集合の本数と整合しない")
    if invalid:
        return BatteryDecision(VERDICT_INVALID, (), (), {}, None, ())
    if not_computed:
        return BatteryDecision(VERDICT_NOT_COMPUTED, (), (), {}, None, ())
    units = np.asarray(units, dtype=float)
    n_models = units.shape[0]
    if n_models > n_entered:
        raise ValueError("報告集合は入場集合の部分集合")
    n_excl = n_entered - n_models
    model_c = tuple(float(u.mean()) for u in units)
    if n_models < MIN_ENTRANTS:
        return BatteryDecision(VERDICT_NOT_QUALIFIED, (), (), {}, None, model_c, n_excl)
    level = ALPHA / k_tests
    pairs = ordered_pairs(n_models)
    est, rep, equiv, lbs = [], [], [], {}
    for a, b in pairs:
        d = units[a] - units[b]
        lb = lower_bound(d, -2.0, 2.0, level)
        lbs[f"{a}-{b}"] = lb
        est.append(rejects_lower(d, DELTA_MIN, -2.0, level))
        equiv.append(rejects_lower(d, -EQUIV, -2.0, level))
        rep.append(all(d[halves == h].mean() > DELTA_MIN for h in (0, 1)))
    conc = concentration(units, sum_m)
    verdict = str(
        classify(
            np.array(est), np.array(rep), np.array(equiv), np.array(conc is not None)
        )
    )
    if verdict == VERDICT_NEGATIVE and n_excl > 0:
        verdict = VERDICT_NEGATIVE_SUBSET
    established = tuple(p for p, e, r in zip(pairs, est, rep, strict=True) if e and r)
    if verdict != VERDICT_ESTABLISHED:
        established = ()
    sens = []
    if cell_counts is not None:
        for a, b in established:
            d = _worst_units(cell_counts[a], -1.0) - _worst_units(cell_counts[b], 1.0)
            if rejects_lower(d, DELTA_MIN, -2.0, level):
                sens.append((a, b))
    return BatteryDecision(
        verdict, established, tuple(sens), lbs, conc, model_c, n_excl
    )


def replicate_lower_bounds(
    units: np.ndarray, units_per_rep: int, k_tests: int
) -> dict[str, float]:
    """v2・v3 の副次の記述 (判定に使わない、DU-13): 単位を replicate の平均にした対差の下限.

    units は (M, n) で、単位の順は r が外側 (n = R × units_per_rep)。
    """
    reps = np.asarray(units, dtype=float).reshape(units.shape[0], -1, units_per_rep)
    rep_c = reps.mean(axis=2)
    level = ALPHA / k_tests
    return {
        f"{a}-{b}": lower_bound(rep_c[a] - rep_c[b], -2.0, 2.0, level)
        for a, b in ordered_pairs(rep_c.shape[0])
    }


# ------------------------------------------------------------ 資格 (§A)

REASON_LOOKUP: Final[str] = "lookup_not_established"
REASON_PARSE: Final[str] = "parse"
REASON_KNOW: Final[str] = "know"
REASON_CONTROL: Final[str] = "length_format_control"
REASON_ENVELOPE: Final[str] = "masked_envelope"
ENTERED: Final[str] = "entered"


@dataclass(frozen=True)
class ModelPilot:
    """1 モデル × 1 battery の pilot の資格の材料 (pilot gate が凍結の関数で計算して渡す).

    ⊥ は率でなく arm 別の数 (分子) と arm あたりの呼び出しの数 (分母) で渡す。率の浮動小数点の差は
    境界 (族内差 = 3/40 ちょうど) で厳密な ``<`` を誤るので、判定は整数の分数で行う (Codex r4 HIGH-1)。
    """

    lookup_ok: bool  # O_time の M0 (凍結の PASS の規則)。全 battery で共通
    bot_counts: tuple[int, ...]  # arm 別の ⊥ の数 (v2 は C0 を含む 5 arm、ほかは 4 arm)
    bot_n: int  # arm あたりの pilot の呼び出しの数
    know_ok: bool | None = None  # G のみ
    control_counts: tuple[int, ...] | None = (
        None  # v3 の L arm 別の ⊥ の数 (分母は bot_n)
    )
    envelope_ok: bool | None = (
        None  # G・O_time の masked (凍結の STOP (envelope) の部分)
    )


# 族を成す arm の組 (arm の並び = lever の 2 族 × 2 本。v2 の 5 本目 C0 は族を持たない)
FAMILY_ARMS: Final[tuple[tuple[int, int], ...]] = ((0, 1), (2, 3))
BOT_MAX_FR: Final = Fraction(1, 5)
BOT_FAMILY_GAP_FR: Final = Fraction(3, 40)  # τ/4 = 0.075
ENVELOPE_MARGIN_FR: Final = Fraction(1, 20)


# battery ごとの arm の数 (並び = 凍結の battery の arm の順。v2 は ALL_ARMS で C0 が 5 本目、v3・G は
# LEVER_ARMS / JUDGE_ARMS、O_time は (AB, BA, CD, DC)。族は FAMILY_ARMS の (0, 1)・(2, 3))
N_ARMS: Final[dict[str, int]] = {"v2": 5, "v3": 4, "G": 4, "O_time": 4}


def parse_rule(bot_counts: Sequence[int], n: int) -> tuple[bool, Fraction]:
    """§A.3 の parse の規則と §F-3 の envelope を arm 別の数で正確に当てる (整数の分数で比較).

    返り値: (規則を通るか, 本走の各 arm の ⊥ 率の上限 min(1/5, pilot の最大 + 1/20))。
    見取り図 (benchmark_stage2_sim) も pilot gate もこの関数だけを使う。
    """
    if n <= 0 or len(bot_counts) < 4:
        raise ValueError("bot_counts は 4 arm 以上・n は正")
    rates = [Fraction(int(x), n) for x in bot_counts]
    top = max(rates)
    gap = max(abs(rates[a] - rates[b]) for a, b in FAMILY_ARMS)
    ok = top <= BOT_MAX_FR and gap < BOT_FAMILY_GAP_FR
    return ok, min(BOT_MAX_FR, top + ENVELOPE_MARGIN_FR)


def envelope_exceeded(main_counts: Sequence[int], main_n: int, env: Fraction) -> bool:
    """§F-3: 本走のどれかの arm の ⊥ 率が envelope (parse_rule の 2 つ目) を超えるか (整数の分数で比較).

    「超える」は厳密な ``>`` (k / n = env ちょうどは残す)。見取り図も scorer もこの関数だけを使う。
    """
    if main_n <= 0:
        raise ValueError("main_n は正")
    return any(Fraction(int(k), main_n) > env for k in main_counts)


def qualify(battery: str, mp: ModelPilot) -> str:
    """§A の順に当て、最初に落ちた理由 (通れば ENTERED)."""
    if not mp.lookup_ok:
        return REASON_LOOKUP
    if len(mp.bot_counts) != N_ARMS[battery]:
        raise ValueError(f"{battery} の arm の数は {N_ARMS[battery]}")
    if not parse_rule(mp.bot_counts, mp.bot_n)[0]:
        return REASON_PARSE
    if battery == "G" and not mp.know_ok:
        return REASON_KNOW
    if battery == "v3" and not (
        mp.control_counts is not None
        and max(Fraction(int(k), mp.bot_n) for k in mp.control_counts) <= BOT_MAX_FR
    ):
        return REASON_CONTROL
    if battery in ("G", "O_time") and not mp.envelope_ok:
        return REASON_ENVELOPE
    return ENTERED


# ------------------------------------------------------------ R の選定 (spike-in、§G-4)


def sigma_up_ratio(df: int = R_PILOT - 1) -> float:
    """σ_up / σ̂ = sqrt(df / χ²_{1−0.95, df}) (段 1 の χ² の上側限界と同じ式)."""
    return math.sqrt(df / s1.chi2_ppf(1.0 - SIGMA_UP_LEVEL, df))


def binom_accept_max(n: int, p: float, family: int) -> int:
    """P(X > x) ≤ FAMILY_FALSE_REJECT / family を満たす最小の x (X ~ Bin(n, p))."""
    target = FAMILY_FALSE_REJECT / family
    pmf = math.exp(n * math.log1p(-p))
    cdf = pmf
    x = 0
    while 1.0 - cdf > target:
        pmf *= (n - x) / (x + 1) * p / (1.0 - p)
        x += 1
        cdf += pmf
    return x


def r_candidates(spec: BatterySpec) -> list[int]:
    """R の候補: r_step の倍数で、名前空間の上限と、単独の予算の上限まで."""
    cap_budget = int(Fraction(BUDGET_SECONDS) / spec.sec_per_rep())
    cap = cap_budget if spec.main_r_cap is None else min(cap_budget, spec.main_r_cap)
    return list(range(spec.r_step, cap + 1, spec.r_step))


def strata(spec: BatterySpec, r_list: Sequence[int]) -> np.ndarray:
    """単位ごとの回転の層 (単位の順は r が外側、§C)。層 = (単位の中の位置, 回転)."""
    upr = spec.units_per_rep
    per_rot = upr // _items_per_rep(spec)
    out = []
    for r in r_list:
        for idx in range(upr):
            item = idx // per_rot
            out.append(item * spec.cycle + (r + _rot_index(spec, item)) % spec.cycle)
    return np.array(out, dtype=int)


def _items_per_rep(spec: BatterySpec) -> int:
    """回転が項目ごとに決まる項目の数 (v2・v3 = probe 6、G = 族 × つ組 16、O_time = 族 × 部屋 12)."""
    return {"v2": 6, "v3": 6, "G": 16, "O_time": 12}[spec.name]


def _rot_index(spec: BatterySpec, item: int) -> int:
    """表示の回転 (r + j) の j。v2・v3 は probe 番号、G はつ組 j、O_time は部屋 i."""
    if spec.name in ("v2", "v3"):
        return item
    if spec.name == "G":
        return item % 8
    return item % 6


@dataclass(frozen=True)
class SpikeRow:
    r: int
    power: float  # 2 方向の小さい方
    power_by_direction: tuple[float, float]
    size_rejects: int  # 2 方向の大きい方
    size_accept_max: int
    calibration_err: float  # 4 行 (2 目標 × 2 方向) の実現平均と目標の差の最大
    # 順: (方向 +, 目標 0.20)・(+, 0.10)・(−, 0.20)・(−, 0.10)
    shifts: tuple[float, float, float, float]
    ok: bool
    realized_means: tuple[float, float, float, float] = (
        math.nan,
    ) * 4  # shifts と同じ順
    rejects_by_direction: tuple[int, int] = (0, 0)
    power_mcse: float = math.nan
    sd_after_clip: float = (
        math.nan
    )  # 方向 +・目標 0.20 の x の標準偏差の平均 (clip の後)
    sd_before_inflation: float = math.nan  # 項目ごとに中心化した pilot の残差の標準偏差
    # 記述 (判定に使わない): 指定の一対 (最大分散の対) の対差 0 で、両方向の下限 ≥ −EQUIV の率。
    # battery の (2) の率ではない (それは spike_negative_all、Codex r4 MEDIUM-2)
    p_pair_equiv_at_zero: float | None = None


def expected_clipped_mean(
    resid: np.ndarray, st_p: np.ndarray, st_m: np.ndarray, b: float
) -> float:
    """層ごとの復元抽出で x = clip(b + e, −2, 2) の期待平均 (本走の層の重み)."""
    total = 0.0
    for s in np.unique(st_m):
        pool = resid[st_p == s]
        total += float(np.sum(st_m == s)) * float(np.clip(b + pool, -2.0, 2.0).mean())
    return total / st_m.size


def solve_shift(
    resid: np.ndarray, st_p: np.ndarray, st_m: np.ndarray, target: float
) -> float | None:
    """期待平均が target になる b (二分法。b について非減少)。届かなければ None."""
    lo, hi = -4.0, 4.0
    if not (
        expected_clipped_mean(resid, st_p, st_m, lo)
        <= target
        <= expected_clipped_mean(resid, st_p, st_m, hi)
    ):
        return None
    for _ in range(BISECT_ITERS):
        mid = (lo + hi) / 2.0
        if expected_clipped_mean(resid, st_p, st_m, mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def spike_power(
    spec: BatterySpec,
    pilot_diff: np.ndarray,
    k_tests: int,
    r_main: int,
    rng: np.random.Generator,
    n_sims: int = N_SPIKE,
) -> SpikeRow:
    """最大分散の対の pilot の対差 (両方向) を中心化・膨張し、層ごとに復元抽出して OC を出す.

    各方向・各目標 (0.20 = power、0.10 = size) について、clip の後の期待平均が目標に
    一致する移動 b を先に解く (Codex r1 HIGH-3)。
    """
    pilot_r = list(range(spec.pilot_r0, spec.pilot_r0 + R_PILOT))
    main_r = list(range(spec.main_r0, spec.main_r0 + r_main))
    # 抽出の単位 = 項目 (回転をまたいでプール、DU-13)。層の id // 1 巡 = 項目の番号
    st_p = strata(spec, pilot_r) // spec.cycle
    st_m = strata(spec, main_r) // spec.cycle
    halves = half_labels(spec, main_r)
    level = ALPHA / k_tests
    thr = math.log(1.0 / level)
    acc = binom_accept_max(n_sims, level, 2)
    resids = []
    shifts: list[float | None] = []
    for sign in (1.0, -1.0):
        d = sign * pilot_diff
        # 中心化は項目ごと (項目の間の平均の違いを残差に残さない、DU-13)
        item_mean = np.array([d[st_p == it].mean() for it in st_p])
        e = (d - item_mean) * sigma_up_ratio()
        resids.append(e)
        shifts += [
            solve_shift(e, st_p, st_m, PLAN_GAP),
            solve_shift(e, st_p, st_m, DELTA_MIN),
        ]
    if any(b is None for b in shifts):
        return SpikeRow(
            r_main, 0.0, (0.0, 0.0), 0, acc, math.inf, (math.nan,) * 4, False
        )
    b_zero = solve_shift(resids[0], st_p, st_m, 0.0)
    bs = [float(b) for b in shifts if b is not None]
    idx = np.empty(st_m.size, dtype=int)
    pools = {s: np.flatnonzero(st_p == s) for s in np.unique(st_m)}
    wheres = {s: np.flatnonzero(st_m == s) for s in pools}
    hits = [0, 0]
    rejects = [0, 0]
    sums = [0.0, 0.0, 0.0, 0.0]
    sd_sum = 0.0
    equiv_zero = 0
    for _ in range(n_sims):
        for s, pool in pools.items():
            idx[wheres[s]] = pool[rng.integers(0, pool.size, wheres[s].size)]
        if b_zero is not None:
            # 記述 (判定に使わない): 対差 0 の世界で、この対の両方向の下限が −EQUIV 以上になる率
            x0 = np.clip(b_zero + resids[0][idx], -2.0, 2.0)
            v0, c0 = support(x0)
            vn, cn = support(-x0)
            equiv_zero += bool(
                log_e_lower(v0, c0, -EQUIV, -2.0) >= thr
                and log_e_lower(vn, cn, -EQUIV, -2.0) >= thr
            )
        for di, e in enumerate(resids):
            for ti in (0, 1):
                x = np.clip(bs[2 * di + ti] + e[idx], -2.0, 2.0)
                sums[2 * di + ti] += float(x.mean())
                if di == 0 and ti == 0:
                    sd_sum += float(x.std(ddof=1))
                v, c = support(x)
                rej = bool(log_e_lower(v, c, DELTA_MIN, -2.0) >= thr)
                if ti == 0:
                    rep = all(x[halves == h].mean() > DELTA_MIN for h in (0, 1))
                    hits[di] += rej and rep
                else:
                    rejects[di] += rej
    by_dir = (hits[0] / n_sims, hits[1] / n_sims)
    targets = (PLAN_GAP, DELTA_MIN, PLAN_GAP, DELTA_MIN)
    calib = max(abs(sm / n_sims - t) for sm, t in zip(sums, targets, strict=True))
    power = min(by_dir)
    mcse = math.sqrt(power * (1.0 - power) / n_sims)
    # power の判定に MC の誤差の余裕を入れる: P̂ − 2·MCSE ≥ 0.8 (DU-13、attack-me R3)
    ok = power - 2.0 * mcse >= POWER and max(rejects) <= acc and calib <= CALIB_TOL
    realized = [sm / n_sims for sm in sums]
    return SpikeRow(
        r_main,
        power,
        by_dir,
        max(rejects),
        acc,
        calib,
        (bs[0], bs[1], bs[2], bs[3]),
        ok,
        (realized[0], realized[1], realized[2], realized[3]),
        (rejects[0], rejects[1]),
        mcse,
        sd_sum / n_sims,
        float(np.std(resids[0], ddof=1)) / sigma_up_ratio(),
        equiv_zero / n_sims if b_zero is not None else None,
    )


def spike_negative_all(
    spec: BatterySpec,
    pilot_units: np.ndarray,
    k_tests: int,
    r_main: int,
    rng: np.random.Generator,
    n_sims: int = N_SPIKE,
) -> float:
    """記述 (判定に使わない、DU-13・Codex r4 MEDIUM-2): 全モデル同点の注入での P((2)).

    pilot_units は (M, n) の入場モデルの pilot の単位の値。各モデルを項目ごとに中心化して
    (全モデルの真の C を等しくする) spike_power と同じ係数で膨張し、**全モデルで同じ単位の
    添字**を項目の中から復元抽出する (モデル間の単位の対応を保つ)。報告集合の全順序対で
    E(−EQUIV) ≥ K/α、かつどの対も Δ_min の検定で棄却されない率を返す (split-half と集中は見ない。
    classify の (2) より厳しく数える保守側の記述)。
    """
    pilot_r = list(range(spec.pilot_r0, spec.pilot_r0 + R_PILOT))
    main_r = list(range(spec.main_r0, spec.main_r0 + r_main))
    st_p = strata(spec, pilot_r) // spec.cycle
    st_m = strata(spec, main_r) // spec.cycle
    units = np.asarray(pilot_units, dtype=float)
    m = units.shape[0]
    resid = np.empty_like(units)
    for i in range(m):
        item_mean = np.array([units[i][st_p == it].mean() for it in st_p])
        resid[i] = (units[i] - item_mean) * sigma_up_ratio()
    thr = math.log(k_tests / ALPHA)
    pools = {s: np.flatnonzero(st_p == s) for s in np.unique(st_m)}
    wheres = {s: np.flatnonzero(st_m == s) for s in pools}
    idx = np.empty(st_m.size, dtype=int)
    hits = 0
    for _ in range(n_sims):
        for s, pool in pools.items():
            idx[wheres[s]] = pool[rng.integers(0, pool.size, wheres[s].size)]
        ok = True
        for a, b in ordered_pairs(m):
            d = np.clip(resid[a][idx] - resid[b][idx], -2.0, 2.0)
            v, c = support(d)
            if (
                log_e_lower(v, c, -EQUIV, -2.0) < thr
                or log_e_lower(v, c, DELTA_MIN, -2.0) >= thr
            ):
                ok = False
                break
        hits += ok
    return hits / n_sims


def worst_pair(pilot_units: np.ndarray) -> tuple[int, int]:
    """Pilot の対差の標本分散が最大の対 (同点は番号の若い順)。計画の対 (最小 power の保証ではない)."""
    best, arg = -1.0, (0, 1)
    m = pilot_units.shape[0]
    for a in range(m):
        for b in range(a + 1, m):
            v = float(np.var(pilot_units[a] - pilot_units[b], ddof=1))
            if v > best + 1e-15:
                best, arg = v, (a, b)
    return arg


def select_r(
    spec: BatterySpec, pilot_units: np.ndarray, k_tests: int
) -> tuple[int | None, list[SpikeRow]]:
    """候補を小さい順に当て、最初に OC を満たす R (無ければ None = STOP (power))."""
    a, b = worst_pair(pilot_units)
    diff = pilot_units[a] - pilot_units[b]
    rng = np.random.default_rng(SPIKE_SEED)
    rows = []
    for r in r_candidates(spec):
        row = spike_power(spec, diff, k_tests, r, rng)
        rows.append(row)
        if row.ok:
            return r, rows
    return None, rows


def binom_upper(k: int, n: int, conf: float = 0.95) -> float:
    """二項の片側 conf の上限 (Clopper-Pearson、k = 0 でも読める)。二分法で正確に解く."""
    if k >= n:
        return 1.0
    target = 1.0 - conf
    lo, hi = k / n, 1.0
    for _ in range(BISECT_ITERS):
        p = (lo + hi) / 2.0
        # P(X ≤ k | p) を log 空間で
        terms = [
            math.lgamma(n + 1)
            - math.lgamma(i + 1)
            - math.lgamma(n - i + 1)
            + i * math.log(p)
            + (n - i) * math.log1p(-p)
            for i in range(k + 1)
        ]
        mx = max(terms)
        cdf = math.exp(mx) * sum(math.exp(t - mx) for t in terms)
        if cdf > target:
            lo = p
        else:
            hi = p
    return (lo + hi) / 2.0


def budget(r_by_battery: Mapping[str, int]) -> dict[str, str]:
    """費用 (8B 換算) の安い順に累計 BUDGET_SECONDS まで GO、超えれば HELD_COST (§G-5)."""
    cost = {n: r * SPECS[n].sec_per_rep() for n, r in r_by_battery.items()}
    out = {}
    cum = Fraction(0)
    for n in sorted(cost, key=lambda k: (cost[k], k)):
        if cum + cost[n] <= BUDGET_SECONDS:
            cum += cost[n]
            out[n] = GATE_GO
        else:
            out[n] = GATE_HELD_COST
    return out

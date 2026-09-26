"""developmental substrate Stage B — 符号付き対比 C の scorer と判定 rule.

事前登録 = ``experiments/20260926-developmental-substrate-stage-b/prereg.md`` (凍結、sha256
``ba7b16a5…``)。本モジュールは prereg §3 (estimand と検定)・§4 (δ_min・⊥ 上界・power 模擬)・
§5 (評価順の判定 rule) をそのまま実装する。§6 の合成対照と変異試験は
``tests/test_stage_b/`` と ``scripts/stage_b_mutation_check.py`` が担う。

用語 (prereg §3):

* 個体 i の X 整合率 r_i^X = (全 probe × K sample のうち g_X(q) を選んだ割合)。
  ⊥ (None または Ω_q 外) は分母に含め、どちらの整合選択肢にも数えない。
* D_i = r_i^A − r_i^B。個体スコア s_i は A 個体で D_i、B 個体で −D_i。
* C_A = mean_{i∈A} s_i、C_B = mean_{j∈B} s_j、C = (C_A + C_B)/2。
* 置換の単位は個体 (stream ラベルの全割当を列挙)。

δ_min は lever 記録 (B2 の成果物) から読む。リテラルで持たない (prereg §6 m7)。
計算は CPU・numpy のみ。生成テキストの採点・自由文 embedding は使わない。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

ALPHA: Final[float] = 0.05  # prereg §3
POWER_TARGET: Final[float] = 0.8  # prereg §4
R_MIN: Final[int] = 4  # prereg §3: min p = 1/70 < α
N_POWER_SIMS: Final[int] = 10_000  # prereg §4
EXACT_PERM_LIMIT: Final[int] = 1_000_000  # prereg §3
N_RANDOM_PERM: Final[int] = 100_000  # prereg §3
MAX_SIGNFLIP_UNITS: Final[int] = 24  # 2^24 列挙が現実的な上限 (prereg §5-3 は全列挙)
PSEUDO_LABEL_SEED: Final[int] = 20260926  # prereg §5-1
POWER_SIM_SEED: Final[int] = 20260926
TIE_TOL: Final[float] = 1e-12

STREAM_A: Final[str] = "A"
STREAM_B: Final[str] = "B"

# prereg §8 / docs/research-positioning.md §8 の 5 語のみ
VERDICT_INVALID_SCORER: Final[str] = "INVALID_SCORER"
VERDICT_INVALID_BATTERY: Final[str] = "INVALID_TASK_BATTERY"
VERDICT_PASS: Final[str] = "PASS"  # noqa: S105 — verdict label, not a secret
VERDICT_UNDERPOWERED: Final[str] = "INCONCLUSIVE_UNDERPOWERED"
VERDICT_ABSENT: Final[str] = "NO_GO_EFFECT_ABSENT"
VERDICTS: Final[tuple[str, ...]] = (
    VERDICT_INVALID_SCORER,
    VERDICT_INVALID_BATTERY,
    VERDICT_PASS,
    VERDICT_UNDERPOWERED,
    VERDICT_ABSENT,
)

# 選択の 4 区分 (power 模擬と整合率で共通)
GA: Final[int] = 0
GB: Final[int] = 1
OTHER: Final[int] = 2
BOT: Final[int] = 3

# stream id の表記 (prereg §2.2: 状態・prompt に出してはならない)
DEFAULT_STREAM_TOKENS: Final[tuple[str, ...]] = (
    "stream_a",
    "stream_b",
    "stream a",
    "stream b",
    "stream-a",
    "stream-b",
)
_BARE_STREAM_ID = re.compile(r"(?<![A-Za-z0-9_])[AB](?![A-Za-z0-9_])")


# --------------------------------------------------------------------- data


@dataclass(frozen=True)
class Probe:
    """held-out probe q: 列挙済み選択肢 Ω_q と事前固定の整合選択肢 g_A(q) ≠ g_B(q)."""

    probe_id: str
    omega: tuple[str, ...]
    g_a: str
    g_b: str

    def __post_init__(self) -> None:
        if self.g_a == self.g_b:
            msg = f"{self.probe_id}: g_A == g_B"
            raise ValueError(msg)
        if self.g_a not in self.omega or self.g_b not in self.omega:
            msg = f"{self.probe_id}: g_A / g_B must be in Ω_q"
            raise ValueError(msg)


@dataclass(frozen=True)
class Individual:
    """1 個体の probe 応答。choices[q] は K 個の選択 (None = ⊥)."""

    ind_id: str
    stream: str
    replicate: int
    seed: int
    probe_order: tuple[str, ...]
    choices: Mapping[str, tuple[str | None, ...]]


@dataclass(frozen=True)
class Snapshot:
    """発達終了時の外部 Skill 状態 (integrity 検査に要る部分だけ)."""

    ind_id: str
    preconditions: tuple[tuple[str, ...], ...]
    text: str


@dataclass(frozen=True)
class StageBData:
    """B3 の 1 回分の観測 (DI・DI ablation・CI セルと、integrity 検査の対象)."""

    probes: tuple[Probe, ...]
    probe_signatures: Mapping[str, tuple[str, ...]]
    dev_signatures: frozenset[tuple[str, ...]]
    di: tuple[Individual, ...]
    di_ablation: tuple[Individual, ...]
    ci: tuple[Individual, ...]
    snapshots: tuple[Snapshot, ...]
    probe_prompts: tuple[str, ...]
    stream_tokens: tuple[str, ...] = DEFAULT_STREAM_TOKENS


@dataclass(frozen=True)
class RecordPaths:
    """判定が読む権威ファイル。値を引数 default に置かない."""

    lever_record: Path
    b_pre_record: Path
    approval_record: Path
    b1_certification: Path


# ------------------------------------------------------------- estimand


def signature_text(sig: Sequence[str]) -> str:
    """precondition / probe signature の正準表記 (renderer と integrity 検査で共通)."""
    return " / ".join(sig)


def category_counts(ind: Individual, probes: Sequence[Probe]) -> np.ndarray:
    """(Q, 4) の区分件数 [g_A, g_B, other, ⊥]。全 probe で K が揃うことを要求する."""
    out = np.zeros((len(probes), 4), dtype=np.int64)
    ks: set[int] = set()
    for qi, probe in enumerate(probes):
        samples = ind.choices[probe.probe_id]
        ks.add(len(samples))
        for c in samples:
            if c is None or c not in probe.omega:
                out[qi, BOT] += 1
            elif c == probe.g_a:
                out[qi, GA] += 1
            elif c == probe.g_b:
                out[qi, GB] += 1
            else:
                out[qi, OTHER] += 1
    if len(ks) != 1 or 0 in ks:
        msg = f"{ind.ind_id}: K must be equal (>0) across probes, got {sorted(ks)}"
        raise ValueError(msg)
    return out


def rates(counts: np.ndarray) -> np.ndarray:
    """(…, Q, 4) の件数 → (…, 4) の率。⊥ は分母に含める (prereg §3)."""
    total = counts.sum(axis=(-2, -1), keepdims=False)
    return counts.sum(axis=-2) / np.asarray(total)[..., None]


def unit_scores(
    inds: Sequence[Individual], probes: Sequence[Probe]
) -> tuple[np.ndarray, np.ndarray]:
    """置換単位 = 個体 (prereg §3)。D_i = r^A − r^B と A 所属 mask を返す."""
    r = np.array([rates(category_counts(i, probes)) for i in inds])
    d = r[:, GA] - r[:, GB]
    is_a = np.array([i.stream == STREAM_A for i in inds])
    return d, is_a


def permutation_units(
    inds: Sequence[Individual], probes: Sequence[Probe], is_a: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """置換検定の単位 = 個体 (prereg §3)。sample を単位にしない (§6 m1)."""
    d, _ = unit_scores(inds, probes)
    return d, is_a


def bottom_rates(inds: Sequence[Individual], probes: Sequence[Probe]) -> np.ndarray:
    return np.array([rates(category_counts(i, probes))[BOT] for i in inds])


def contrast(d: np.ndarray, is_a: np.ndarray) -> tuple[float, float, float]:
    """(C, C_A, C_B)。s_i = D_i (A) / −D_i (B)."""
    c_a = float(np.mean(d[is_a]))
    c_b = float(-np.mean(d[~is_a]))
    return (c_a + c_b) / 2.0, c_a, c_b


# ----------------------------------------------------------------- tests


@lru_cache(maxsize=16)
def _assignment_masks(n: int, n_a: int) -> np.ndarray:
    """全割当 (観測割当を含む) の bool mask (C(n, n_a) × n)."""
    total = math.comb(n, n_a)
    masks = np.zeros((total, n), dtype=bool)
    for row, idx in enumerate(combinations(range(n), n_a)):
        masks[row, list(idx)] = True
    masks.setflags(write=False)
    return masks


def _contrast_of_masks(d: np.ndarray, masks: np.ndarray) -> np.ndarray:
    n_a = int(masks[0].sum())
    n_b = d.size - n_a
    sum_a = masks.astype(np.float64) @ d
    return (sum_a / n_a - (float(d.sum()) - sum_a) / n_b) / 2.0


def perm_p(
    d: np.ndarray, is_a: np.ndarray, rng: np.random.Generator | None = None
) -> float:
    """片側 p = #{割当: C_perm ≥ C_obs} / 総数 (観測割当を分子・分母に含む、prereg §3)."""
    n = int(d.size)
    n_a = int(is_a.sum())
    c_obs = contrast(d, is_a)[0]
    total = math.comb(n, n_a)
    if total <= EXACT_PERM_LIMIT:
        stats = _contrast_of_masks(d, _assignment_masks(n, n_a))
        count = int(np.count_nonzero(stats >= c_obs - TIE_TOL))
        return count / total
    gen = rng if rng is not None else np.random.default_rng(PSEUDO_LABEL_SEED)
    b = 0
    done = 0
    while done < N_RANDOM_PERM:
        m = min(10_000, N_RANDOM_PERM - done)
        order = np.argsort(gen.random((m, n)), axis=1)
        masks = np.zeros((m, n), dtype=bool)
        np.put_along_axis(masks, order[:, :n_a], values=True, axis=1)
        b += int(np.count_nonzero(_contrast_of_masks(d, masks) >= c_obs - TIE_TOL))
        done += m
    return (b + 1) / (N_RANDOM_PERM + 1)


def signflip_p(d: np.ndarray) -> float:
    """paired 差 d_i の平均 > 0 を個体単位の符号反転全列挙で (片側、観測を含む)."""
    n = int(d.size)
    if n > MAX_SIGNFLIP_UNITS:
        msg = f"sign-flip enumeration over {n} units is not supported"
        raise ValueError(msg)
    obs = float(np.mean(d))
    total = 1 << n
    bits = np.arange(n, dtype=np.int64)
    count = 0
    step = 1 << 16
    for start in range(0, total, step):
        ints = np.arange(start, min(start + step, total), dtype=np.int64)
        signs = 1.0 - 2.0 * ((ints[:, None] >> bits) & 1)
        count += int(np.count_nonzero(signs @ d / n >= obs - TIE_TOL))
    return count / total


def bottom_bound(r_bot: np.ndarray, is_a: np.ndarray) -> float:
    """b_X = max over 成分 of |stream 間の平均 ⊥ 率の差| (prereg §4).

    成分 C_A (A 個体の s) と C_B (B 個体の s) のどちらについても、⊥ が片側 stream に偏ったとき
    動きうる量は両 stream の平均 ⊥ 率の差で抑えられる。両成分で同じ値になる。
    """
    gap_a = abs(float(np.mean(r_bot[is_a])) - float(np.mean(r_bot[~is_a])))
    gap_b = abs(float(np.mean(r_bot[~is_a])) - float(np.mean(r_bot[is_a])))
    return max(gap_a, gap_b)


def pseudo_labels(inds: Sequence[Individual]) -> np.ndarray:
    """CI 陰性対照の疑似ラベル (prereg §5-1)。replicate 番号の順列を 1 回、前半 = 疑似 A."""
    order = sorted(range(len(inds)), key=lambda i: inds[i].replicate)
    perm = np.random.default_rng(PSEUDO_LABEL_SEED).permutation(len(inds))
    is_a = np.zeros(len(inds), dtype=bool)
    half = len(inds) // 2
    for rank in perm[:half]:
        is_a[order[int(rank)]] = True
    return is_a


# ---------------------------------------------------------------- power


def plugin_probs(inds: Sequence[Individual], probes: Sequence[Probe]) -> np.ndarray:
    """(n, Q, 4) の plug-in 分布 p_iq (Ω_q ∪ {⊥} を 4 区分に畳む)."""
    return np.array(
        [(c := category_counts(i, probes)) / c.sum(axis=1, keepdims=True) for i in inds]
    )


def symmetrize(p: np.ndarray) -> np.ndarray:
    """p'(g_A) = p'(g_B) = (p(g_A) + p(g_B))/2。他と ⊥ はそのまま (prereg §4-1)."""
    out = p.copy()
    mid = (p[..., GA] + p[..., GB]) / 2.0
    out[..., GA] = mid
    out[..., GB] = mid
    return out


def inject(p_sym: np.ndarray, is_a: np.ndarray, delta_min: float) -> np.ndarray:
    """A 群は g_B→g_A、B 群は g_A→g_B へ min(δ_min/2, 残量) の質量を移す (prereg §4-3)."""
    out = p_sym.copy()
    half = delta_min / 2.0
    move_a = np.minimum(half, out[is_a, :, GB])
    out[is_a, :, GA] += move_a
    out[is_a, :, GB] -= move_a
    move_b = np.minimum(half, out[~is_a, :, GA])
    out[~is_a, :, GB] += move_b
    out[~is_a, :, GA] -= move_b
    return out


def simulate_once(
    pool: np.ndarray, r: int, k: int, delta_min: float, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """1 回の模擬: 2R 個体を復元抽出 → R/R 割当 → 対称化 → 注入 → 多項抽出 (prereg §4)."""
    idx = rng.integers(0, pool.shape[0], size=2 * r)
    is_a = np.zeros(2 * r, dtype=bool)
    is_a[rng.permutation(2 * r)[:r]] = True
    p = inject(symmetrize(pool[idx]), is_a, delta_min)
    counts = rng.multinomial(k, p)
    return rates(counts), is_a


def core_pass(sim_rates: np.ndarray, is_a: np.ndarray, delta_min: float) -> bool:
    """§5-3 の PASS 条件から ablation を除いたもの (⊥ 上界を含む)."""
    d = sim_rates[:, GA] - sim_rates[:, GB]
    c, c_a, c_b = contrast(d, is_a)
    return (
        perm_p(d, is_a) < ALPHA
        and c >= delta_min
        and c_a > 0
        and c_b > 0
        and bottom_bound(sim_rates[:, BOT], is_a) < delta_min / 2.0
    )


def power(
    pool: np.ndarray,
    r: int,
    k: int,
    delta_min: float,
    n_sims: int = N_POWER_SIMS,
    seed: int = POWER_SIM_SEED,
) -> float:
    """power(δ_min; R) = 模擬の通過率 (prereg §4)."""
    rng = np.random.default_rng(seed)
    passed = 0
    for _ in range(n_sims):
        sim_rates, is_a = simulate_once(pool, r, k, delta_min, rng)
        passed += core_pass(sim_rates, is_a, delta_min)
    return passed / n_sims


def plan_r(
    pool: np.ndarray, k: int, delta_min: float, r_max: int, n_sims: int = N_POWER_SIMS
) -> int | None:
    """power ≥ 0.8 を満たす最小の R (≥ 4)。R_max までに無ければ None (prereg §4 計画 power)."""
    for r in range(R_MIN, r_max + 1):
        if power(pool, r, k, delta_min, n_sims) >= POWER_TARGET:
            return r
    return None


# ------------------------------------------------------------- integrity


def integrity_violations(data: StageBData) -> list[str]:
    """prereg §2.2 非漏洩 contract の機械検査。違反の説明を返す (空 = 違反なし)."""
    out: list[str] = []
    probe_sigs = set(data.probe_signatures.values())
    for snap in data.snapshots:
        for pre in snap.preconditions:
            if pre in probe_sigs:
                out.append(
                    f"{snap.ind_id}: precondition equals a probe signature {pre}"
                )
            elif pre not in data.dev_signatures:
                out.append(f"{snap.ind_id}: precondition not seen in development {pre}")
    # probe prompt は状況の記述を含まざるを得ないので、signature の文字列禁止は状態側だけ。
    # answer key (signature → g_X の対応) と probe id と stream id は両方で禁止する。
    ids = [p.probe_id for p in data.probes]
    keys = [
        f"{signature_text(data.probe_signatures[p.probe_id])} → {g}"
        for p in data.probes
        for g in (p.g_a, p.g_b)
    ]
    state_forbidden = ids + keys + [signature_text(s) for s in probe_sigs]
    texts = [(f"snapshot {s.ind_id}", s.text, state_forbidden) for s in data.snapshots]
    texts += [
        (f"probe prompt {n}", t, ids + keys) for n, t in enumerate(data.probe_prompts)
    ]
    for where, text, forbidden in texts:
        low = text.lower()
        out.extend(f"{where}: contains {tok!r}" for tok in forbidden if tok in text)
        out.extend(
            f"{where}: contains stream token {tok!r}"
            for tok in data.stream_tokens
            if tok in low
        )
        if _BARE_STREAM_ID.search(text):
            out.append(f"{where}: contains a bare stream id")
    return out


def ablation_pairing_violations(
    di: Sequence[Individual], abl: Sequence[Individual]
) -> list[str]:
    """paired ablation の前提: 同じ個体・同じ seed・同じ probe 順序 (prereg §5-3)."""
    out: list[str] = []
    by_id = {i.ind_id: i for i in abl}
    if len(by_id) != len(abl) or set(by_id) != {i.ind_id for i in di}:
        out.append("ablation individuals do not match DI individuals one-to-one")
        return out
    for ind in di:
        twin = by_id[ind.ind_id]
        if twin.seed != ind.seed:
            out.append(f"{ind.ind_id}: ablation decoding seed differs")
        if twin.probe_order != ind.probe_order:
            out.append(f"{ind.ind_id}: ablation probe order differs")
        if twin.stream != ind.stream:
            out.append(f"{ind.ind_id}: ablation stream differs")
    return out


def paired_ablation(
    di: Sequence[Individual], abl: Sequence[Individual], probes: Sequence[Probe]
) -> dict[str, float]:
    """C_abl と paired 差 d_i = s_i − s_i^abl の符号反転 p (prereg §5-3)."""
    by_id = {i.ind_id: i for i in abl}
    twins = [by_id[i.ind_id] for i in di]
    d, is_a = unit_scores(di, probes)
    d_abl, _ = unit_scores(twins, probes)
    sign = np.where(is_a, 1.0, -1.0)
    diff = sign * d - sign * d_abl
    return {
        "C_abl": contrast(d_abl, is_a)[0],
        "paired_mean": float(np.mean(diff)),
        "paired_p": signflip_p(diff),
    }


# --------------------------------------------------------- synthetic gate


def internal_sanity_gate() -> bool:
    """実行時の最小 sanity check (estimand と exact 置換の自己診断).

    prereg §5-1「B1 の合成データ検査 (§6) に落ちる」の本体は B1 certification 記録
    (``load_b1_certification``) で判定する。本関数はその補助で、§6 全体の代わりではない。

    陽性: A 個体は g_A 寄り・B 個体は g_B 寄り → C > 0 かつ p = 1/70。
    陰性: 同一分布 (D が全個体で等しい) → C = 0 かつ p = 1。
    """
    d_pos = np.array([0.6, 0.5, 0.7, 0.55, -0.6, -0.5, -0.65, -0.45])
    d_zero = np.full(8, 0.1)
    is_a = np.array([True] * 4 + [False] * 4)
    c_pos, ca_pos, cb_pos = contrast(d_pos, is_a)
    c_zero = contrast(d_zero, is_a)[0]
    return (
        c_pos > 0
        and ca_pos > 0
        and cb_pos > 0
        and abs(perm_p(d_pos, is_a) - 1 / 70) < TIE_TOL
        and abs(c_zero) < TIE_TOL
        and abs(perm_p(d_zero, is_a) - 1.0) < TIE_TOL
    )


# ------------------------------------------------------------- records


def _individual_from_json(obj: Mapping[str, Any]) -> Individual:
    return Individual(
        ind_id=str(obj["ind_id"]),
        stream=str(obj["stream"]),
        replicate=int(obj["replicate"]),
        seed=int(obj["seed"]),
        probe_order=tuple(obj["probe_order"]),
        choices={q: tuple(v) for q, v in obj["choices"].items()},
    )


def individual_to_json(ind: Individual) -> dict[str, Any]:
    return {
        "ind_id": ind.ind_id,
        "stream": ind.stream,
        "replicate": ind.replicate,
        "seed": ind.seed,
        "probe_order": list(ind.probe_order),
        "choices": {q: list(v) for q, v in ind.choices.items()},
    }


def load_lever(path: Path, probes: Sequence[Probe]) -> dict[str, Any]:
    """lever 記録 (B2) を読み、C_lever を再計算して記録値と照合する.

    δ_min = C_lever / 2 はこの記録からだけ得る (prereg §4、§6 m7)。
    """
    obj = json.loads(path.read_text(encoding="utf-8"))
    inds = [_individual_from_json(o) for o in obj["individuals"]]
    d, is_a = unit_scores(inds, probes)
    c, c_a, c_b = contrast(d, is_a)
    recorded = float(obj["C_lever"])
    lever_p = perm_p(*permutation_units(inds, probes, is_a))
    return {
        "individuals": inds,
        "C_lever": c,
        "C_A": c_a,
        "C_B": c_b,
        "p": lever_p,
        "b_lever": bottom_bound(bottom_rates(inds, probes), is_a),
        "consistent": abs(recorded - c) < 1e-9,
        "delta_min": recorded / 2.0,
    }


def load_b_pre(path: Path) -> bool:
    """B-pre 結果 (``scripts/stage_b_pre.py`` の results.json)。読めない = 不成立."""
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return obj.get("b_pre_established") is True


def load_b1_certification(path: Path) -> bool:
    """B1 の §6 検査記録 (``scripts/stage_b_mutation_check.py`` の出力)。読めない = 不合格.

    全変異が KILLED (理由照合込み) で、記録された scorer の sha256 が現在の scorer と一致すること。
    """
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        certified = obj["target_sha256"]["stage_b_scorer.py"]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return obj.get("all_killed") is True and certified == _scorer_sha256()


def _scorer_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def sample_size_violations(
    data: StageBData, lever: Sequence[Individual], probes: Sequence[Probe]
) -> list[str]:
    """K は全セル共通、DI は各 stream R (≥ 4) 個体 (prereg §2.1 / §3)."""
    out: list[str] = []
    ks: set[int] = set()
    for cell in (data.di, data.di_ablation, data.ci, lever):
        for i in cell:
            ks.add(int(category_counts(i, probes).sum(axis=1)[0]))
    if len(ks) != 1:
        out.append(f"K differs across cells: {sorted(ks)}")
    n_a = sum(i.stream == STREAM_A for i in data.di)
    n_b = sum(i.stream == STREAM_B for i in data.di)
    if n_a != n_b or n_a < R_MIN or n_a + n_b != len(data.di):
        out.append(f"DI is not R/R with R >= {R_MIN}: A={n_a}, B={n_b}")
    return out


def load_r_max(path: Path) -> int:
    obj = json.loads(path.read_text(encoding="utf-8"))
    return int(obj["R_max"])


# -------------------------------------------------------------- verdict


def evaluate(
    data: StageBData, records: RecordPaths, n_power_sims: int = N_POWER_SIMS
) -> dict[str, Any]:
    """prereg §5 の評価順で verdict を返す (最初に当たったもの)."""
    probes = data.probes
    report: dict[str, Any] = {"reasons": []}

    def done(verdict: str, reason: str) -> dict[str, Any]:
        report["reasons"].append(reason)
        report["verdict"] = verdict
        return report

    # ---- 1. INVALID_SCORER
    if not load_b1_certification(records.b1_certification):
        return done(VERDICT_INVALID_SCORER, "b1_certification_missing_or_failed")
    if not internal_sanity_gate():
        return done(VERDICT_INVALID_SCORER, "internal_sanity_gate_failed")
    violations = integrity_violations(data)
    report["integrity_violations"] = violations
    if violations:
        return done(VERDICT_INVALID_SCORER, "non_leakage_integrity")
    pairing = ablation_pairing_violations(data.di, data.di_ablation)
    report["ablation_pairing_violations"] = pairing
    if pairing:
        return done(VERDICT_INVALID_SCORER, "ablation_not_paired")
    ci_p = perm_p(*permutation_units(data.ci, probes, pseudo_labels(data.ci)))
    report["ci_pseudo_p"] = ci_p
    if ci_p < ALPHA:
        return done(VERDICT_INVALID_SCORER, "ci_negative_control_separates")
    lever = load_lever(records.lever_record, probes)
    if not lever["consistent"]:
        return done(VERDICT_INVALID_SCORER, "lever_record_inconsistent")
    sizes = sample_size_violations(data, lever["individuals"], probes)
    report["sample_size_violations"] = sizes
    if sizes:
        return done(VERDICT_INVALID_SCORER, "k_or_r_inconsistent")

    # ---- 2. INVALID_TASK_BATTERY
    delta_min = lever["delta_min"]
    report["delta_min"] = delta_min
    if not load_b_pre(records.b_pre_record):
        return done(VERDICT_INVALID_BATTERY, "b_pre_not_established")
    r_max = load_r_max(records.approval_record)
    k = int(category_counts(data.di[0], probes).sum(axis=1)[0])
    lever_pool = plugin_probs(lever["individuals"], probes)
    # 「R ≤ R_max で power ≥ 0.8 を達成できる」= 4..R_max で最小の R を探す (prereg §4)
    lever_r = plan_r(lever_pool, k, delta_min, r_max, n_power_sims)
    report.update(
        C_lever=lever["C_lever"],
        lever_p=lever["p"],
        lever_planned_r=lever_r,
    )
    lever_ok = (
        lever["p"] < ALPHA
        and lever["C_A"] > 0
        and lever["C_B"] > 0
        and lever_r is not None
    )
    if not lever_ok:
        return done(VERDICT_INVALID_BATTERY, "lever_insufficient")
    d_di, is_a = unit_scores(data.di, probes)
    b_di = bottom_bound(bottom_rates(data.di, probes), is_a)
    report.update(b_lever=lever["b_lever"], b_di=b_di)
    if lever["b_lever"] >= delta_min / 2.0 or b_di >= delta_min / 2.0:
        return done(VERDICT_INVALID_BATTERY, "bottom_bound")

    # ---- 3. PASS
    c, c_a, c_b = contrast(d_di, is_a)
    di_p = perm_p(*permutation_units(data.di, probes, is_a))
    abl = paired_ablation(data.di, data.di_ablation, probes)
    report.update(C=c, C_A=c_a, C_B=c_b, di_p=di_p, **abl)
    passed = [
        ("di_permutation", di_p < ALPHA),
        ("delta_min", c >= delta_min),
        ("both_components", c_a > 0 and c_b > 0),
        ("ablation_point", abl["C_abl"] <= c / 2.0),
        ("ablation_paired", abl["paired_p"] < ALPHA),
    ]
    report["pass_conditions"] = dict(passed)
    if all(ok for _, ok in passed):
        return done(VERDICT_PASS, "all_pass_conditions")

    # ---- 4 / 5. power で振り分け (PASS の判定には使わない)
    r = int(is_a.sum())
    realized = power(plugin_probs(data.ci, probes), r, k, delta_min, n_power_sims)
    report["realized_power"] = realized
    if realized < POWER_TARGET:
        return done(VERDICT_UNDERPOWERED, "realized_power_below_target")
    return done(VERDICT_ABSENT, "pass_condition_failed_with_power")

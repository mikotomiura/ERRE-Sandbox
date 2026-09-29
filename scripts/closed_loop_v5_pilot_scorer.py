"""閉ループ v5 前段 — 較正 pilot の記録の検証と挙動の測定 (pilot prereg §3・§4).

判定 (verdict) は出さない。pilot の記録は v5 の verdict に使わない。出すのは次だけ:

* status: ``computed`` / ``invalid`` (schema・要求条件・schedule・再 parse・連鎖 replay の違反) /
  ``not_computed`` (欠け・transport 失敗)。``computed`` 以外では測定量を出さず、写像も計算しない。
* 候補 M ∈ {4, 6, 8} の窓 (step < 12M) ごと・軸ごとの測定量 (``measure``、user 裁定 DP-4)。
  定義は v5 模擬 (``closed_loop_v5_sim``) の経験的混合方策の意味論に合わせる。
  - ⊥ gate: 世界別の ⊥ 率 (窓内の全ステップ) の最大 > 0.2 の軸は、その M で不採用。
  - 「前回」= その (世界, r, signature) の直近の ⊥ でない応答。初訪 = 前回が無い訪問。
  - 以下の率は、未成功の signature で、今回の応答が表示中の Ω_dev に入るものだけを数える
    (⊥ と Ω 外は別の率として模擬に入る)。
  - 再訪の分類: 描画した prompt が今回と同一の以前の訪問があり、その応答 (⊥ でない直近) が表示中の Ω_dev にあれば
    「同一 prompt」(その応答と比べる、s_same・記述)。それ以外は「prompt 変化」(模擬の分岐 3 と同じ)。
  - ŝ_changed: prompt 変化の再訪で、前回の label が表示中の Ω_dev にあるもの → 前回と同じ label の率。
  - ε̂: 表示中の選択肢に試行済みが 1 つ以上あり、未試行も残る訪問 → 未試行を選んだ率。
  - λ̂_dev = max(0, (h_sw − h0) / (1 − h0))。h0 = 同 weather の成功行が無い初訪で規則に当たった率、
    h_sw = 同 weather の成功行が 1 本以上ある初訪で規則に当たった率。
  - base = 同 weather の成功行が無い初訪の、Ω_dev (正準順) 上の label 割合 (+0.5 の加算平滑化)。
  - Ω 外率: 未成功の signature での ⊥ でない応答のうち、表示中の Ω_dev に無いものの率 (世界別)。
  - 数える単位は (prompt_sha256, seed) で畳む (4 世界が seed を共有するので、同一 prompt の重複は 1 回の抽選)。
    代表は call_index の最初の 1 件。世界別の ⊥・Ω 外は畳まない。
* 挙動の率 (ŝ_changed・ε̂ など) の保守限界 (user 裁定 DP-5): 畳んだ呼び出し単位の Wilson 95% と、
  (世界, r) cluster 単位の Wilson 95% の外側。n = 0 のとき下限 0・上限 1。
* ⊥ と Ω 外の上限 (模擬の nuisance、DC-4) は、世界別の呼び出し単位 Wilson 95% 上限の最大。
  世界別の cluster は 4 個しかなく、cluster 単位の上限は ⊥ が 0 件でも 0.49 になり、⊥ gate (0.2) を通る v5 が
  原理的に無くなるため (DC-9)。
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from scripts import closed_loop_battery as v4
from scripts import closed_loop_v5_battery as bat
from scripts.skill_lever_scorer import (
    BOT_MAX,
    messages_sha256,
    parse_choice,
    request_meta,
)
from scripts.stage_b_battery import WEATHER

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

STATUS_COMPUTED: Final[str] = "computed"
STATUS_INVALID: Final[str] = "invalid"
STATUS_NOT_COMPUTED: Final[str] = "not_computed"
Z95: Final[float] = 1.959964
BASE_SMOOTH: Final[float] = 0.5


# ---------------------------------------------------------------- records


@dataclass(frozen=True)
class Record:
    """1 回の呼び出し。raw = None は transport 失敗 (再送 3 回後も失敗、⊥ ではない)。成否は記録しない."""

    call_index: int
    axis: str
    world: str
    replicate: int
    step: int
    seed: int
    prompt_sha256: str
    raw: str | None
    parsed: str | None

    def key(self) -> bat.PilotKey:
        return bat.PilotKey(self.axis, self.world, self.replicate, self.step)


class RecordError(ValueError):
    """記録の schema 違反."""


_FIELDS: Final[frozenset[str]] = frozenset(Record.__dataclass_fields__)
_INT: Final[tuple[str, ...]] = ("call_index", "replicate", "step", "seed")
_STR: Final[tuple[str, ...]] = ("axis", "world", "prompt_sha256")
_OPT_STR: Final[tuple[str, ...]] = ("raw", "parsed")


def record_from_json(obj: object) -> Record:
    """厳密に読む: 欄の過不足・型違い (coercion しない) は RecordError."""
    if not isinstance(obj, dict) or set(obj) != _FIELDS:
        msg = f"record fields must be exactly {sorted(_FIELDS)}"
        raise RecordError(msg)
    for f in _INT:
        if type(obj[f]) is not int:
            msg = f"{f} must be int"
            raise RecordError(msg)
    for f in _STR:
        if type(obj[f]) is not str:
            msg = f"{f} must be str"
            raise RecordError(msg)
    for f in _OPT_STR:
        if obj[f] is not None and type(obj[f]) is not str:
            msg = f"{f} must be str or null"
            raise RecordError(msg)
    return Record(**{f: obj[f] for f in _FIELDS})


def load_records(lines: Sequence[str]) -> list[Record]:
    out = []
    for n, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError as exc:
            msg = f"line {n}: not JSON"
            raise RecordError(msg) from exc
        out.append(record_from_json(obj))
    return out


# ---------------------------------------------------------------- 検証


def schedule_violations(records: Sequence[Record]) -> list[str]:
    """記録が凍結 plan の接頭辞 (行順 = call_index = plan の位置)、key・seed が一致、transport 失敗で止まる."""
    full = bat.pilot_plan()
    if [x.call_index for x in records] != list(range(len(records))):
        return [
            "records are not 0..n-1 in file order (not a prefix of the frozen plan)"
        ]
    if len(records) > len(full):
        return ["more records than the frozen plan"]
    out: list[str] = []
    for rec in records:
        if rec.key() != full[rec.call_index]:
            out.append(f"call {rec.call_index}: key differs from the frozen plan")
            continue
        want = bat.pilot_seed(rec.replicate, rec.step)
        if rec.seed != want:
            out.append(f"call {rec.call_index}: seed {rec.seed} != {want}")
    failed = [x.call_index for x in records if x.raw is None]
    if failed and failed[0] != records[-1].call_index:
        out.append("records continue after a transport failure")
    return out


def parse_violations(records: Sequence[Record]) -> list[str]:
    out = []
    for rec in records:
        want = None if rec.raw is None else parse_choice(rec.raw)
        if rec.parsed != want:
            out.append(f"call {rec.call_index}: recorded parse differs from re-parse")
    return out


def _chains(records: Sequence[Record]) -> dict[tuple[str, str, int], list[Record]]:
    out: dict[tuple[str, str, int], list[Record]] = defaultdict(list)
    for rec in sorted(records, key=lambda x: x.call_index):
        out[(rec.axis, rec.world, rec.replicate)].append(rec)
    return out


def chain_violations(records: Sequence[Record]) -> list[str]:
    """連鎖 replay: 記録した行動・世界の規則・軸の renderer から prompt を再構成し、sha を照合する."""
    out: list[str] = []
    for (axis, world, r), recs in sorted(_chains(records).items()):
        state = v4.EMPTY_STATE
        for n, rec in enumerate(recs):
            if rec.step != n:
                out.append(f"{axis} {world} r={r}: steps are not 0..n-1")
                break
            msgs = bat.loop_messages(state, world, r, n, axis)
            if rec.prompt_sha256 != messages_sha256(msgs):
                out.append(
                    f"{axis} {world} r={r} t={n}: prompt differs from the chain replay"
                )
                break
            state = v4.update(state, world, v4.loop_signature(r, n), rec.parsed)
    return out


# ---------------------------------------------------------------- 測定


def wilson(k: float, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson の 95% 区間 (下限, 上限)。n = 0 は (0, 1)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    den = 1.0 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(max(0.0, p * (1.0 - p)) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


@dataclass
class Tally:
    """0/1 の集計。(prompt_sha256, seed) の重複は call_index の最初の 1 件だけ数える.

    保守限界 (user 裁定 DP-5) は 2 通りの区間の外側をとる:
    (a) 畳んだ呼び出し単位の Wilson、(b) 非空の (世界, r) cluster の数を n・cluster 率の平均を p とする Wilson。
    """

    seen: set[tuple[str, int]] = field(default_factory=set)
    k: int = 0
    n: int = 0
    clusters: dict[tuple[str, int], list[int]] = field(default_factory=dict)

    def add(self, rec: Record, hit: bool) -> None:
        key = (rec.prompt_sha256, rec.seed)
        if key in self.seen:
            return
        self.seen.add(key)
        self.n += 1
        self.k += int(hit)
        c = self.clusters.setdefault((rec.world, rec.replicate), [0, 0])
        c[0] += int(hit)
        c[1] += 1

    def bounds(self) -> tuple[float, float]:
        lo_a, hi_a = wilson(self.k, self.n)
        rates = [k / n for k, n in self.clusters.values()]
        n_c = len(rates)
        lo_b, hi_b = wilson(sum(rates), n_c) if n_c else (0.0, 1.0)
        return min(lo_a, lo_b), max(hi_a, hi_b)

    def summary(self) -> dict[str, Any]:
        lo, hi = self.bounds()
        return {
            "k": self.k,
            "n": self.n,
            "clusters": len(self.clusters),
            "rate": self.k / self.n if self.n else None,
            "lo": lo,
            "hi": hi,
        }


def _tallies(names: Sequence[str]) -> dict[str, Tally]:
    return {x: Tally() for x in names}


@dataclass
class AxisCounts:
    bottom: dict[str, Tally] = field(
        default_factory=lambda: _tallies(v4.WORLDS)
    )  # 世界別 ⊥ (全ステップ)
    oov: dict[str, Tally] = field(
        default_factory=lambda: _tallies(v4.WORLDS)
    )  # 世界別 Ω 外
    s_changed: Tally = field(default_factory=Tally)
    s_same: Tally = field(
        default_factory=Tally
    )  # 記述 (同一 prompt の以前の訪問がある再訪)
    eps: Tally = field(default_factory=Tally)
    rho: Tally = field(
        default_factory=Tally
    )  # 記述 (未試行を選ばなかった訪問で前回と同じ)
    eta: Tally = field(
        default_factory=Tally
    )  # 記述 (未試行を選んだ訪問で規則に当たった)
    h0: Tally = field(default_factory=Tally)
    h_sw: Tally = field(default_factory=Tally)
    base: dict[str, dict[str, int]] = field(
        default_factory=lambda: {
            wt: dict.fromkeys(v4.dev_omega(wt), 0) for wt in WEATHER
        }
    )
    base_seen: set[tuple[str, int]] = field(default_factory=set)


def count_axis(records: Sequence[Record], axis: str, t_max: int) -> AxisCounts:
    """1 軸の記録のうち step < t_max を集計する (連鎖は検証済みであること)."""
    c = AxisCounts()
    # 重複 (同じ prompt・seed) の代表 = call_index の最初の 1 件。世界別の ⊥・Ω 外は重複を畳まない
    rep: dict[tuple[str, int], int] = {}
    for x in sorted(records, key=lambda x: x.call_index):
        if x.axis == axis and x.step < t_max:
            rep.setdefault((x.prompt_sha256, x.seed), x.call_index)
    for (ax, world, r), recs in sorted(_chains(records).items()):
        if ax != axis:
            continue
        table = v4.rule(world)
        state = v4.EMPTY_STATE
        last: dict[Any, str] = {}
        by_sha: dict[Any, dict[str, str]] = defaultdict(
            dict
        )  # sig → prompt sha → その prompt での直近の応答
        for rec in recs:
            t = rec.step
            if t >= t_max:
                break
            sig = v4.loop_signature(r, t)
            opts = bat.dev_options(axis, r, t)
            cur = rec.parsed
            c.bottom[world].add(rec, cur is None)
            first = rep[(rec.prompt_sha256, rec.seed)] == rec.call_index
            if sig not in state.succeeded and cur is not None:
                c.oov[world].add(rec, cur not in opts)
                if cur in opts and first:
                    hit = cur == table[sig[0]]
                    if sig not in last:
                        n_sw = sum(1 for s in state.succeeded if s[0] == sig[0])
                        if n_sw:
                            c.h_sw.add(rec, hit)
                        else:
                            c.h0.add(rec, hit)
                            key = (rec.prompt_sha256, rec.seed)
                            if key not in c.base_seen:
                                c.base_seen.add(key)
                                c.base[sig[0]][cur] += 1
                    elif by_sha[sig].get(rec.prompt_sha256) in opts:
                        # 同一 prompt の以前の訪問があり、その応答が表示中 (B は 4 周ごとに回転の位相が戻る)。
                        # 以前の応答が Ω 外なら模擬と同じく「prompt 変化」に落とす (Codex 2 回目 HIGH)
                        same = by_sha[sig][rec.prompt_sha256]
                        c.s_same.add(rec, cur == same)
                    elif last[sig] in opts:
                        c.s_changed.add(rec, cur == last[sig])
                    tried = [o for o in opts if (sig, o) in state.tried]
                    if tried and len(tried) < len(opts):
                        untried = cur not in tried
                        c.eps.add(rec, untried)
                        if untried:
                            c.eta.add(rec, hit)
                        else:
                            c.rho.add(rec, cur == last.get(sig))
            if cur is not None:
                last[sig] = cur
                by_sha[sig][rec.prompt_sha256] = cur
            state = v4.update(state, world, sig, cur)
    return c


def base_probs(c: AxisCounts) -> dict[str, dict[str, float]]:
    out = {}
    for wt in WEATHER:
        counts = c.base[wt]
        tot = sum(counts.values()) + BASE_SMOOTH * len(counts)
        out[wt] = {a: (counts[a] + BASE_SMOOTH) / tot for a in v4.dev_omega(wt)}
    return out


def lam_dev(c: AxisCounts) -> float | None:
    """λ̂_dev = max(0, (h_sw − h0) / (1 − h0))。どちらかの n が 0、または h0 = 1 なら None."""
    if c.h0.n == 0 or c.h_sw.n == 0:
        return None
    h0 = c.h0.k / c.h0.n
    if h0 >= 1.0:
        return None
    return max(0.0, (c.h_sw.k / c.h_sw.n - h0) / (1.0 - h0))


def measure_window(records: Sequence[Record], m: int) -> dict[str, dict[str, Any]]:
    """候補 M の窓 (step < 12M) での軸ごとの測定量."""
    out: dict[str, dict[str, Any]] = {}
    for axis in bat.AXES:
        c = count_axis(records, axis, bat.N_DEV * m)
        world_bot = {w: x.k / x.n for w, x in c.bottom.items()}
        out[axis] = {
            "world_bottom_rates": world_bot,
            "bottom_max": max(world_bot.values()),
            "rejected_bottom": max(world_bot.values()) > BOT_MAX,
            "bottom_hi": max(wilson(x.k, x.n)[1] for x in c.bottom.values()),
            "oov_hi": max(wilson(x.k, x.n)[1] for x in c.oov.values()),
            "world_bottom": {w: x.summary() for w, x in c.bottom.items()},
            "world_oov": {w: x.summary() for w, x in c.oov.items()},
            "s_changed": c.s_changed.summary(),
            "s_same": c.s_same.summary(),
            "eps": c.eps.summary(),
            "rho": c.rho.summary(),
            "eta": c.eta.summary(),
            "h0": c.h0.summary(),
            "h_sw": c.h_sw.summary(),
            "lam_dev": lam_dev(c),
            "base": base_probs(c),
            "base_counts": c.base,
        }
    return out


def measure(records: Sequence[Record]) -> dict[str, dict[str, dict[str, Any]]]:
    """候補 M ごと (キーは文字列の M) の測定量."""
    return {str(m): measure_window(records, m) for m in bat.M_WINDOWS}


# ---------------------------------------------------------------- 入口


def validate(
    records: Sequence[Record], meta: Mapping[str, Any]
) -> tuple[str, list[str]]:
    """(status, reasons)。computed 以外は測定しない."""
    if bat.battery_violations():
        return STATUS_INVALID, ["battery_checks"]
    if dict(meta) != request_meta():
        return STATUS_INVALID, ["request_meta_mismatch"]
    if schedule_violations(records):
        return STATUS_INVALID, ["schedule"]
    if parse_violations(records):
        return STATUS_INVALID, ["parse"]
    if chain_violations(records):
        return STATUS_INVALID, ["chain_replay"]
    if any(x.raw is None for x in records):
        return STATUS_NOT_COMPUTED, ["transport_failure"]
    if len(records) < bat.n_pilot_calls():
        return STATUS_NOT_COMPUTED, ["incomplete"]
    return STATUS_COMPUTED, []


def evaluate_records(lines: Sequence[str], meta_text: str) -> dict[str, Any]:
    """JSONL の行と meta の JSON テキストから検証と測定を行う."""
    try:
        records = load_records(lines)
        meta = json.loads(meta_text)
    except ValueError as exc:  # RecordError を含む
        return {
            "status": STATUS_INVALID,
            "reasons": ["record_schema"],
            "error": str(exc),
        }
    if not isinstance(meta, dict):
        return {
            "status": STATUS_INVALID,
            "reasons": ["record_schema"],
            "error": "meta must be an object",
        }
    status, reasons = validate(records, meta)
    report: dict[str, Any] = {"status": status, "reasons": reasons}
    if status == STATUS_COMPUTED:
        report["measures"] = measure(records)
    return report

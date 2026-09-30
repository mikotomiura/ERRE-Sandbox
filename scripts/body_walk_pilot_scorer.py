"""探索を身体側へ (b) — 較正 pilot の記録の検証と挙動の測定 (pilot prereg §3・§4).

判定 (verdict) は出さない。pilot の記録は本登録の verdict に使わない。出すのは次だけ:

* status: ``computed`` / ``invalid`` (schema・要求条件と実行環境・schedule・再 parse・連鎖 replay の違反) /
  ``not_computed`` (ループ部分の欠け・transport 失敗)。``computed`` 以外では測定量を出さず、写像も計算しない。
  replay 部分の欠けや失敗は止めない (決定性の n に出る)。
* 候補 M ∈ {4, 6, 8} の窓 (step < 12M) ごとの測定量 (``measure``)。定義は模擬 (``body_walk_sim``) の
  経験的混合方策の意味論に合わせる (v5 の定義を 1 腕で)。
  - ⊥ gate: 世界別の ⊥ 率 (窓内の全ステップ) の最大 > 0.2 なら、その M で審査しない。
  - 「前回」= その (世界, r, signature) の直近の ⊥ でない応答。初訪 = 前回が無い訪問。
  - 以下の率は、未成功の signature で、今回の応答が表示中の Ω_dev に入るものだけを数える
    (⊥ と Ω 外は別の率として模擬に入る)。
  - 再訪の分類: 描画した prompt が今回と **完全一致** する以前の訪問があり、その応答 (⊥ でない直近) が表示中の
    Ω_dev にあれば「同一 prompt」(その応答と比べる、ŝ_same)。それ以外で前回が表示中にあれば「prompt 変化」(ŝ_changed)。
  - λ̂_dev = max(0, (h_sw − h0) / (1 − h0))。h0 = 同 weather の成功行が無い初訪で規則に当たった率、
    h_sw = 同 weather の成功行が 1 本以上ある初訪で規則に当たった率。
  - base = 同 weather の成功行が無い初訪の、Ω_dev (正準順) 上の label 割合 (+0.5 の加算平滑化)。label 別の Tally も持つ。
  - 低事前 label: 各 weather で平滑化後の点推定が最小の label (同値は正準順の先) と、その生の数の保守下限。
  - Ω 外率: 未成功の signature での ⊥ でない応答のうち、表示中の Ω_dev に無いものの率 (世界別)。
* 畳み方 (Codex MEDIUM-2・DC-3): 4 世界が seed を共有するので、ŝ_same・ŝ_changed・base・h0・h_sw は
  (prompt_sha256, seed) の最初の 1 件 (call_index 順) に畳む。世界別の ⊥・Ω 外は畳まない。
* 保守限界 (v5 DP-5): 挙動の率は、畳んだ呼び出し単位の Wilson 95% と (世界, r) cluster 単位の Wilson 95% の外側。
  n = 0 は (0, 1)。⊥ と Ω 外の上限は、世界別の呼び出し単位 Wilson 95% 上限の最大 (v5 DC-9)。
* 経験点の入力 (``chains``): 窓 M の終状態 = r block × 世界の成功集合 (開発 signature 順の bool) と ⊥ 数。
* 決定性 (記述): run 内で (prompt_sha256, seed) が同一のループ呼び出し群の raw 一致率と、登録 replay の raw 一致率。
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from scripts import body_walk_battery as bat
from scripts import closed_loop_battery as v4
from scripts.closed_loop_v5_pilot_scorer import wilson
from scripts.skill_lever_scorer import BOT_MAX, messages_sha256, parse_choice
from scripts.stage_b_battery import WEATHER, dev_signatures

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

STATUS_COMPUTED: Final[str] = "computed"
STATUS_INVALID: Final[str] = "invalid"
STATUS_NOT_COMPUTED: Final[str] = "not_computed"
BASE_SMOOTH: Final[float] = 0.5
DEVS: Final = dev_signatures()


# ---------------------------------------------------------------- records


@dataclass(frozen=True)
class Record:
    """1 回の呼び出し。raw = None は transport 失敗 (再送後も失敗、⊥ ではない)。成否は記録しない."""

    call_index: int
    phase: str
    world: str
    replicate: int
    step: int
    seed: int
    prompt_sha256: str
    raw: str | None
    parsed: str | None

    def key(self) -> bat.PilotKey:
        return bat.PilotKey(self.phase, self.world, self.replicate, self.step)


class RecordError(ValueError):
    """記録の schema 違反."""


_FIELDS: Final[frozenset[str]] = frozenset(Record.__dataclass_fields__)
_INT: Final[tuple[str, ...]] = ("call_index", "replicate", "step", "seed")
_STR: Final[tuple[str, ...]] = ("phase", "world", "prompt_sha256")
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


def _loops(records: Sequence[Record]) -> list[Record]:
    return [x for x in records if x.phase == bat.PHASE_LOOP]


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


def _chains(records: Sequence[Record]) -> dict[tuple[str, int], list[Record]]:
    out: dict[tuple[str, int], list[Record]] = defaultdict(list)
    for rec in sorted(_loops(records), key=lambda x: x.call_index):
        out[(rec.world, rec.replicate)].append(rec)
    return out


def chain_violations(records: Sequence[Record]) -> list[str]:
    """連鎖 replay: 記録した行動・世界の規則・R1 から prompt を再構成し、sha を照合する.

    replay の記録は、元のループ呼び出しと同じ prompt でなければならない。
    """
    out: list[str] = []
    for (world, r), recs in sorted(_chains(records).items()):
        state = v4.EMPTY_STATE
        for n, rec in enumerate(recs):
            if rec.step != n:
                out.append(f"{world} r={r}: steps are not 0..n-1")
                break
            msgs = bat.loop_messages(state, world, r, n)
            if rec.prompt_sha256 != messages_sha256(msgs):
                out.append(f"{world} r={r} t={n}: prompt differs from the chain replay")
                break
            state = v4.update(state, world, v4.loop_signature(r, n), rec.parsed)
    by_key = {(x.world, x.replicate, x.step): x for x in _loops(records)}
    for rec in records:
        if rec.phase != bat.PHASE_REPLAY:
            continue
        orig = by_key.get((rec.world, rec.replicate, rec.step))
        if orig is None or orig.prompt_sha256 != rec.prompt_sha256:
            out.append(
                f"call {rec.call_index}: replay prompt differs from the original"
            )
    return out


# ---------------------------------------------------------------- 測定


@dataclass
class Tally:
    """0/1 の集計。畳む Tally は (prompt_sha256, seed) の最初の 1 件だけ数える (呼び出し側が代表を渡す).

    保守限界 (v5 DP-5) は 2 通りの区間の外側をとる:
    (a) 呼び出し単位の Wilson、(b) 非空の (世界, r) cluster の数を n・cluster 率の平均を p とする Wilson。
    """

    k: int = 0
    n: int = 0
    clusters: dict[tuple[str, int], list[int]] = field(default_factory=dict)

    def add(self, rec: Record, hit: bool) -> None:
        self.n += 1
        self.k += int(hit)
        c = self.clusters.setdefault((rec.world, rec.replicate), [0, 0])
        c[0] += int(hit)
        c[1] += 1

    def call_bounds(self) -> tuple[float, float]:
        return wilson(self.k, self.n)

    def bounds(self) -> tuple[float, float]:
        lo_a, hi_a = self.call_bounds()
        rates = [k / n for k, n in self.clusters.values()]
        lo_b, hi_b = wilson(sum(rates), len(rates)) if rates else (0.0, 1.0)
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
class Counts:
    bottom: dict[str, Tally] = field(default_factory=lambda: _tallies(v4.WORLDS))
    oov: dict[str, Tally] = field(default_factory=lambda: _tallies(v4.WORLDS))
    s_same: Tally = field(default_factory=Tally)
    s_changed: Tally = field(default_factory=Tally)
    h0: Tally = field(default_factory=Tally)
    h_sw: Tally = field(default_factory=Tally)
    base: dict[str, dict[str, Tally]] = field(
        default_factory=lambda: {wt: _tallies(v4.dev_omega(wt)) for wt in WEATHER}
    )


def count_window(records: Sequence[Record], t_max: int) -> Counts:
    """ループ段の記録のうち step < t_max を集計する (連鎖は検証済みであること)."""
    c = Counts()
    rep: dict[tuple[str, int], int] = {}
    for x in sorted(_loops(records), key=lambda x: x.call_index):
        if x.step < t_max:
            rep.setdefault((x.prompt_sha256, x.seed), x.call_index)
    for (world, r), recs in sorted(_chains(records).items()):
        table = v4.rule(world)
        state = v4.EMPTY_STATE
        last: dict[Any, str] = {}
        by_sha: dict[Any, dict[str, str]] = defaultdict(dict)
        for rec in recs:
            t = rec.step
            if t >= t_max:
                break
            sig = v4.loop_signature(r, t)
            opts = bat.dev_options(r, t)
            cur = rec.parsed
            first = rep[(rec.prompt_sha256, rec.seed)] == rec.call_index
            c.bottom[world].add(rec, cur is None)  # 世界別の ⊥・Ω 外は畳まない
            if sig not in state.succeeded and cur is not None:
                c.oov[world].add(rec, cur not in opts)
                if cur in opts and first:
                    if sig not in last:
                        hit = cur == table[sig[0]]
                        if any(s[0] == sig[0] for s in state.succeeded):
                            c.h_sw.add(rec, hit)
                        else:
                            c.h0.add(rec, hit)
                            for a, tally in c.base[sig[0]].items():
                                tally.add(rec, cur == a)
                    elif by_sha[sig].get(rec.prompt_sha256) in opts:
                        c.s_same.add(rec, cur == by_sha[sig][rec.prompt_sha256])
                    elif last[sig] in opts:
                        c.s_changed.add(rec, cur == last[sig])
            if cur is not None:
                last[sig] = cur
                by_sha[sig][rec.prompt_sha256] = cur
            state = v4.update(state, world, sig, cur)
    return c


def base_probs(c: Counts) -> dict[str, dict[str, float]]:
    """初訪の label 割合 (+0.5 の加算平滑化、Ω_dev の正準順)."""
    out = {}
    for wt in WEATHER:
        tallies = c.base[wt]
        n = next(iter(tallies.values())).n
        tot = n + BASE_SMOOTH * len(tallies)
        out[wt] = {a: (tallies[a].k + BASE_SMOOTH) / tot for a in v4.dev_omega(wt)}
    return out


def low_prior(c: Counts) -> dict[str, dict[str, Any]]:
    """各 weather の低事前 label = 平滑化後の点推定が最小 (同値は正準順の先) と、その生の数の保守限界."""
    probs = base_probs(c)
    out = {}
    for wt in WEATHER:
        label = min(v4.dev_omega(wt), key=lambda a: probs[wt][a])
        tally = c.base[wt][label]
        lo, hi = tally.bounds()
        out[wt] = {"label": label, "point": probs[wt][label], "lo": lo, "hi": hi}
    return out


def lam_dev(c: Counts) -> float | None:
    """λ̂_dev = max(0, (h_sw − h0) / (1 − h0))。どちらかの n が 0、または h0 = 1 なら None."""
    if c.h0.n == 0 or c.h_sw.n == 0:
        return None
    h0 = c.h0.k / c.h0.n
    if h0 >= 1.0:
        return None
    return max(0.0, (c.h_sw.k / c.h_sw.n - h0) / (1.0 - h0))


def measure_window(records: Sequence[Record], m: int) -> dict[str, Any]:
    """候補 M の窓 (step < 12M) での測定量."""
    c = count_window(records, bat.N_DEV * m)
    world_bot = {w: x.k / x.n for w, x in c.bottom.items()}
    return {
        "world_bottom_rates": world_bot,
        "bottom_max": max(world_bot.values()),
        "rejected_bottom": max(world_bot.values()) > BOT_MAX,
        "bottom_hi": max(x.call_bounds()[1] for x in c.bottom.values()),
        "oov_hi": max(x.call_bounds()[1] for x in c.oov.values()),
        "world_bottom": {w: x.summary() for w, x in c.bottom.items()},
        "world_oov": {w: x.summary() for w, x in c.oov.items()},
        "s_same": c.s_same.summary(),
        "s_changed": c.s_changed.summary(),
        "h0": c.h0.summary(),
        "h_sw": c.h_sw.summary(),
        "lam_dev": lam_dev(c),
        "base": base_probs(c),
        "base_labels": {
            wt: {a: x.summary() for a, x in tallies.items()}
            for wt, tallies in c.base.items()
        },
        "low_prior": low_prior(c),
    }


def chains(records: Sequence[Record], m: int) -> dict[str, Any]:
    """窓 M の終状態 (経験点の入力): succ[b][w] = 開発 signature 順の 0/1、bot[b][w] = ⊥ 数.

    b は ``PILOT_R`` の順、w は ``v4.WORLDS`` の順。
    """
    t_max = bat.N_DEV * m
    by = _chains(records)
    succ = []
    bot = []
    for r in bat.PILOT_R:
        row_s = []
        row_b = []
        for w in v4.WORLDS:
            state = v4.EMPTY_STATE
            n_bot = 0
            for rec in by[(w, r)]:
                if rec.step >= t_max:
                    break
                n_bot += rec.parsed is None
                state = v4.update(state, w, v4.loop_signature(r, rec.step), rec.parsed)
            row_s.append([int(s in state.succeeded) for s in DEVS])
            row_b.append(n_bot)
        succ.append(row_s)
        bot.append(row_b)
    return {"steps": t_max, "succ": succ, "bot": bot}


def determinism(records: Sequence[Record]) -> dict[str, Any]:
    """決定性 (記述): (i) ループ段で (prompt, seed) が同一の群の raw 一致率、(ii) 登録 replay の raw 一致率.

    どちらかが 1.0 未満なら、本登録は相殺を「期待値で 0」と書く (v4 と同じ)。transport 失敗は数えない。
    """
    groups: dict[tuple[str, int], list[str]] = defaultdict(list)
    for rec in _loops(records):
        if rec.raw is not None:
            groups[(rec.prompt_sha256, rec.seed)].append(rec.raw)
    multi = [g for g in groups.values() if len(g) > 1]
    in_run = sum(len(set(g)) == 1 for g in multi) / len(multi) if multi else None
    by_key = {(x.world, x.replicate, x.step): x for x in _loops(records)}
    rep = [
        by_key[(x.world, x.replicate, x.step)].raw == x.raw
        for x in records
        if x.phase == bat.PHASE_REPLAY and x.raw is not None
    ]
    replay = sum(rep) / len(rep) if rep else None
    rates = [x for x in (in_run, replay) if x is not None]
    return {
        "in_run_groups": len(multi),
        "in_run_identical_rate": in_run,
        "replay_n": len(rep),
        "replay_identical_rate": replay,
        "exact_cancellation": bool(rates) and all(x == 1.0 for x in rates),
    }


def measure(records: Sequence[Record]) -> dict[str, dict[str, Any]]:
    """候補 M ごと (キーは文字列の M) の測定量."""
    return {str(m): measure_window(records, m) for m in bat.M_WINDOWS}


# ---------------------------------------------------------------- 入口


def meta_violations(meta: Mapping[str, Any]) -> list[str]:
    """要求条件・実行環境は、key の集合・値・型まで一致しなければならない (Codex 2 回目 MEDIUM).

    ``False == 0`` や ``4096 == 4096.0`` を通さない (記録と同じく型の coercion をしない)。
    """
    want = bat.request_meta_walk()
    if set(meta) != set(want):
        return ["request meta keys differ"]
    return [
        f"request meta {k} = {meta[k]!r} (want {v!r})"
        for k, v in want.items()
        if type(meta[k]) is not type(v) or meta[k] != v
    ]


def validate(
    records: Sequence[Record], meta: Mapping[str, Any]
) -> tuple[str, list[str]]:
    """(status, reasons)。computed 以外は測定しない."""
    if bat.battery_violations():
        return STATUS_INVALID, ["battery_checks"]
    if meta_violations(meta):
        return STATUS_INVALID, ["request_meta_mismatch"]
    if schedule_violations(records):
        return STATUS_INVALID, ["schedule"]
    if parse_violations(records):
        return STATUS_INVALID, ["parse"]
    if chain_violations(records):
        return STATUS_INVALID, ["chain_replay"]
    loops = _loops(records)
    if any(x.raw is None for x in loops):
        return STATUS_NOT_COMPUTED, ["transport_failure"]
    if len(loops) < bat.n_loop_calls():
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
        report["chains"] = {str(m): chains(records, m) for m in bat.M_WINDOWS}
        report["determinism"] = determinism(records)
    return report

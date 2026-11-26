"""判別性 gate 段 2 — 呼び出しの計画 (純関数) と、本登録の r の列の上の battery 検査.

規則の SSOT は ``experiments/20261126-benchmark-stage2-discriminability/prereg.md`` (第 1 段 PILOT-FROZEN)。
設計 = ``.steering/20261126-benchmark-stage2-driver/design-final.md`` (案 B: 計画と実行を分ける、DD-1)。

* 本 module は 4 battery の凍結の関数 (r を個別に受ける renderer・seed・表示順) だけを呼び、
  stage (pilot・main・replay) の全呼び出しを ``CallSpec`` として §G.1・§H の順に列挙する。
  driver (``benchmark_stage2_driver``) は battery を知らず、``CallSpec`` を body にして送るだけ。
* scorer と pilot gate は記録の照合を本 module に頼らない: 凍結の ``expected_sample``
  (各 battery の scorer・pilot gate) で seed と prompt の sha を独立に再計算する。
* §C の「作り直す battery 検査」(``battery_checks``): 凍結の検査関数は r ∈ [0, R) を仮定するので、
  r を受ける凍結の関数 (v2・v3 = ``layout``、G・O_time = ``entry_order``・``option_order`` ほか) を
  **始点 r0 だけずらした関数に一時的に差し替えて**、凍結の検査のコードそのものを本登録の r の列で評価する
  (述語を書き写さない)。r の固定値・seed の名前空間・prompt の byte 予算を持つ検査だけを本登録の r の列で書き直す。
* 凍結物 (4 battery・実験 dir・stats) は import だけにする。
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Final

from scripts import benchmark_stage2_stats as st
from scripts import generalization_probe_battery as gbat
from scripts import generalization_probe_pilot_gate as gpg
from scripts import o_time_probe_battery as obat
from scripts import o_time_probe_pilot_gate as opg
from scripts import o_time_probe_scorer as osc
from scripts import skill_experience_battery as v3bat
from scripts import skill_experience_scorer as v3sc
from scripts import skill_lever_battery as v2bat

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence

# ------------------------------------------------------------ 実行条件 (prereg §A.1)

# §A.1 の表の順 (pilot・本走のモデルの順、§H)
MODELS: Final[tuple[str, ...]] = (
    "qwen3:1.7b",
    "qwen3:4b-q4_K_M",
    "qwen3:8b",
    "qwen3:14b",
    "llama3.1:8b",
    "gemma2:9b",
)
REPLAY_MODEL: Final[str] = "qwen3:8b"
THINK: Final[bool] = False
TOP_K: Final[int] = 20  # DM-9 (全モデル・全 stage で明示)
# 各 battery の凍結値 (4 battery で同じことを ``frozen_decode_problems`` が検査する)
DECODE: Final[dict[str, float | int]] = {
    "temperature": v2bat.TEMPERATURE,
    "top_p": v2bat.TOP_P,
    "top_k": TOP_K,
    "repeat_penalty": v2bat.REPEAT_PENALTY,
    "num_ctx": v2bat.NUM_CTX,
    "num_predict": v2bat.NUM_PREDICT,
}
OPTION_KEYS: Final[frozenset[str]] = frozenset({*DECODE, "seed"})
BODY_KEYS: Final[frozenset[str]] = frozenset(
    {"model", "messages", "stream", "think", "options"}
)

STAGE_PILOT: Final[str] = "pilot"
STAGE_MAIN: Final[str] = "main"
STAGE_REPLAY: Final[str] = "replay"

# 呼び出しの目的 (記録の分類。判定に使うのは lever だけ)
P_LEVER: Final[str] = "lever"  # v2・v3 の判定 arm、G・O_time の lever arm
P_C0: Final[str] = "c0"
P_CONTROL: Final[str] = "control"  # v3 の L arm
P_MASKED: Final[str] = "masked"
P_M0: Final[str] = "m0"
P_KNOW: Final[str] = "know"

# §C の r の範囲 (pilot の lever arm は stats の SPECS の pilot_r0 から R_PILOT 個)
PILOT_AUX_R: Final[int] = (
    6  # G の masked・O_time の masked・M0 (凍結の pilot と同じ規模、DM-10)
)
PILOT_AUX_R0: Final[dict[str, int]] = {"G": 24, "O_time": 312}
REPLAY_R: Final[int] = 0  # qwen3:8b の旧 prompt・seed の再生 (G・O_time の r 0)


def frozen_decode_problems() -> list[str]:
    """4 battery の凍結の decode が同じ値であること (DECODE は v2 の値で書いた)."""
    out = []
    for name, mod in (("v3", v3bat), ("G", gbat), ("O_time", obat)):
        for attr in (
            "TEMPERATURE",
            "TOP_P",
            "REPEAT_PENALTY",
            "NUM_CTX",
            "NUM_PREDICT",
        ):
            base = mod if name != "v3" else v2bat  # v3 は v2 の定数を使う
            if getattr(base, attr) != getattr(v2bat, attr):
                out.append(f"{name}: {attr} differs from v2")
    for mod in (v2bat, gbat, obat):
        if mod.THINK is not THINK:
            out.append(f"{mod.__name__}: THINK differs")
    return out


# ------------------------------------------------------------ 呼び出しの仕様


@dataclass(frozen=True)
class CallSpec:
    """1 呼び出し (モデルに依らない)。messages は (role, content) の組の列."""

    battery: str
    purpose: str
    arm: str  # 記録の腕名 (G・O_time の masked は M_*、M0 は P_*、G の KNOW は KNOW)
    encoding: str | None  # O_time の書き方 (他は None)
    replicate: int
    probe_id: str
    k: int
    seed: int
    messages: tuple[tuple[str, str], ...]

    def messages_list(self) -> list[dict[str, str]]:
        return [{"role": r, "content": c} for r, c in self.messages]

    def key(self) -> tuple[str, str, str | None, int, str, int]:
        return (
            self.battery,
            self.arm,
            self.encoding,
            self.replicate,
            self.probe_id,
            self.k,
        )


def _msgs(messages: Sequence[Mapping[str, str]]) -> tuple[tuple[str, str], ...]:
    if any(set(m) != {"role", "content"} for m in messages):
        msg = "messages must have exactly role and content"
        raise ValueError(msg)
    return tuple((m["role"], m["content"]) for m in messages)


def options_for(seed: int) -> dict[str, Any]:
    return {**DECODE, "seed": seed}


def body_for(spec: CallSpec, model: str) -> dict[str, Any]:
    """送る body (driver は本関数の値をそのまま送り、送信前に照合する)."""
    return {
        "model": model,
        "messages": spec.messages_list(),
        "stream": False,
        "think": THINK,
        "options": options_for(spec.seed),
    }


# ------------------------------------------------------------ v2・v3 (seed = v2 の sample_seed)


def _v2_block_arms(
    arms: Sequence[str], r: int, qi: int, k_count: int, k: int
) -> tuple[str, ...]:
    """凍結の v2 の順: (r, probe, k) の block ごとに arm を block mod 4 だけ巡回 (block は r から数える)."""
    block = (r * len(v2bat.lever_probes()) + qi) * k_count + k
    shift = block % len(arms)
    return tuple(arms[shift:]) + tuple(arms[:shift])


def v2_calls(r_list: Sequence[int]) -> tuple[CallSpec, ...]:
    """C0 を全部先に、次に (r, probe, k) の block ごとに lever 4 arm (凍結の本走と同じ構成と順)."""
    k_count = 10  # 凍結の FROZEN_K (skill_lever_scorer)
    probes = v2bat.lever_probes()
    out: list[CallSpec] = []

    def spec(arm: str, purpose: str, r: int, qi: int, k: int) -> CallSpec:
        lay = v2bat.layout(r)
        return CallSpec(
            "v2",
            purpose,
            arm,
            None,
            r,
            probes[qi].probe_id,
            k,
            v2bat.sample_seed(r, qi, k),
            _msgs(v2bat.render_messages(arm, probes[qi], lay)),
        )

    for r in r_list:
        for qi in range(len(probes)):
            for k in range(k_count):
                out.append(spec(v2bat.ARM_C0, P_C0, r, qi, k))
    for r in r_list:
        for qi in range(len(probes)):
            for k in range(k_count):
                for arm in _v2_block_arms(v2bat.LEVER_ARMS, r, qi, k_count, k):
                    out.append(spec(arm, P_LEVER, r, qi, k))
    return tuple(out)


def v3_calls(r_list: Sequence[int]) -> tuple[CallSpec, ...]:
    """C0 を全部先に、次に block ごとに状態 8 arm を ``block_arm_order(call_block)`` の順 (凍結)."""
    k_count = v3sc.FROZEN_K
    probes = v2bat.lever_probes()
    out: list[CallSpec] = []

    def spec(arm: str, r: int, qi: int, k: int) -> CallSpec:
        purpose = (
            P_C0
            if arm == v3bat.ARM_C0
            else P_LEVER
            if arm in v3bat.JUDGE_ARMS
            else P_CONTROL
        )
        return CallSpec(
            "v3",
            purpose,
            arm,
            None,
            r,
            probes[qi].probe_id,
            k,
            v2bat.sample_seed(r, qi, k),
            _msgs(v3bat.render_messages(arm, probes[qi], v2bat.layout(r))),
        )

    for r in r_list:
        for qi in range(len(probes)):
            for k in range(k_count):
                out.append(spec(v3bat.ARM_C0, r, qi, k))
    for r in r_list:
        for qi in range(len(probes)):
            for k in range(k_count):
                for arm in v3sc.block_arm_order(v3sc.call_block(r, qi, k)):
                    out.append(spec(arm, r, qi, k))
    return tuple(out)


# ------------------------------------------------------------ G

_G_MASKED_OF: Final[dict[str, str]] = {lever: m for m, lever in gpg.MASKED_ARMS.items()}


def g_unit_calls(r_list: Sequence[int], *, masked: bool) -> tuple[CallSpec, ...]:
    """凍結の順: r → 族 → つ組 j → probe → k → 族内の 2 arm。masked は pilot の名前空間・M_* の腕名."""
    out: list[CallSpec] = []
    for r in r_list:
        for fi, family in enumerate(gbat.FAMILIES):
            ns = f"pilot_fam{fi}" if masked else f"fam{fi}"
            for j in range(gbat.N_TRIPLES):
                for p in gbat.triple_probes(j):
                    for k in range(1):  # 凍結の FROZEN_K = PILOT_K = 1
                        for arm in family:
                            out.append(
                                CallSpec(
                                    "G",
                                    P_MASKED if masked else P_LEVER,
                                    _G_MASKED_OF[arm] if masked else arm,
                                    None,
                                    r,
                                    p.probe_id,
                                    k,
                                    gbat.sample_seed(ns, r, p.triple, k),
                                    _msgs(
                                        gbat.render_messages(arm, p, r, masked=masked)
                                    ),
                                )
                            )
    return tuple(out)


def g_know_calls() -> tuple[CallSpec, ...]:
    """KNOW (36 key × 3 試行)。r を持たない (replicate = 0、seed は旧 pilot と同じ、§C)."""
    return tuple(
        CallSpec(
            "G",
            P_KNOW,
            gpg.ARM_KNOW,
            None,
            0,
            gpg.know_probe_id(i),
            k,
            gbat.sample_seed("know", 0, i, k),
            _msgs(gbat.render_know_messages(i, k)),
        )
        for i in range(len(gbat.all_keys()))
        for k in range(gbat.KNOW_K)
    )


# ------------------------------------------------------------ O_time

_O_MASKED_OF: Final[dict[str, str]] = {lever: m for m, lever in opg.MASKED_ARMS.items()}
_O_M0_OF: Final[dict[str, str]] = {lever: m for m, lever in opg.M0_ARMS.items()}


def _o_unit_specs(unit: obat.Unit, mode: str) -> list[CallSpec]:
    """単位の 4 呼び出し (``bat.unit_calls`` の順)。K = 1 (凍結の FROZEN_K = PILOT_K)."""
    ns = f"fam{unit.family}" if mode == "main" else f"{mode}_fam{unit.family}"
    names: dict[str, Callable[[str], str]] = {
        "main": str,
        "masked": _O_MASKED_OF.__getitem__,
        "m0": _O_M0_OF.__getitem__,
    }
    name = names[mode]
    purpose = {"main": P_LEVER, "masked": P_MASKED, "m0": P_M0}[mode]
    return [
        CallSpec(
            "O_time",
            purpose,
            name(arm),
            enc,
            unit.replicate,
            osc.probe_id(unit.room),
            0,
            obat.sample_seed(ns, unit.replicate, unit.room, 0),
            _msgs(obat.render_messages(arm, enc, unit, mode)),
        )
        for arm, enc in obat.unit_calls(unit)
    ]


def _o_units(r_list: Sequence[int]) -> list[obat.Unit]:
    """凍結の単位の順 (r, 族, 部屋)."""
    return [
        obat.Unit(fi, i, r)
        for r in r_list
        for fi in range(len(obat.FAMILIES))
        for i in range(obat.N_ROOMS)
    ]


def o_lever_calls(r_list: Sequence[int]) -> tuple[CallSpec, ...]:
    return tuple(c for u in _o_units(r_list) for c in _o_unit_specs(u, "main"))


def o_aux_calls(r_list: Sequence[int]) -> tuple[CallSpec, ...]:
    """凍結の旧 pilot の順: 単位ごとに masked の 4 → M0 の 4."""
    out: list[CallSpec] = []
    for u in _o_units(r_list):
        out += _o_unit_specs(u, "masked")
        out += _o_unit_specs(u, "m0")
    return tuple(out)


# ------------------------------------------------------------ stage の列挙


def pilot_lever_r(battery: str) -> list[int]:
    r0 = st.SPECS[battery].pilot_r0
    return list(range(r0, r0 + st.R_PILOT))


def pilot_aux_r(battery: str) -> list[int]:
    r0 = PILOT_AUX_R0[battery]
    return list(range(r0, r0 + PILOT_AUX_R))


def main_r(battery: str, r_count: int) -> list[int]:
    r0 = st.SPECS[battery].main_r0
    return list(range(r0, r0 + r_count))


@lru_cache(maxsize=8)
def pilot_calls(battery: str) -> tuple[CallSpec, ...]:
    """§G.1 の 1 モデル・1 battery の腕 (表の行の順)."""
    if battery == "v2":
        return v2_calls(pilot_lever_r("v2"))
    if battery == "v3":
        return v3_calls(pilot_lever_r("v3"))
    if battery == "G":
        return (
            g_unit_calls(pilot_lever_r("G"), masked=False)
            + g_unit_calls(pilot_aux_r("G"), masked=True)
            + g_know_calls()
        )
    if battery == "O_time":
        return o_lever_calls(pilot_lever_r("O_time")) + o_aux_calls(
            pilot_aux_r("O_time")
        )
    msg = f"unknown battery {battery!r}"
    raise ValueError(msg)


def main_calls(battery: str, r_count: int) -> tuple[CallSpec, ...]:
    """本走の腕 (凍結の本走と同じ構成、§G-5): v2 = lever + C0、v3 = judge + L + C0、G・O_time = lever."""
    rs = main_r(battery, r_count)
    problems = st.check_r_range(st.SPECS[battery], rs, main=True)
    if problems:
        raise ValueError("; ".join(problems))
    if battery == "v2":
        return v2_calls(rs)
    if battery == "v3":
        return v3_calls(rs)
    if battery == "G":
        return g_unit_calls(rs, masked=False)
    if battery == "O_time":
        return o_lever_calls(rs)
    msg = f"unknown battery {battery!r}"
    raise ValueError(msg)


@lru_cache(maxsize=2)
def replay_calls(battery: str) -> tuple[CallSpec, ...]:
    """qwen3:8b の旧 prompt・seed の再生 (G の r 0 = 96、O_time の r 0 = 48、§C)。判定に数えない."""
    if battery == "G":
        return g_unit_calls([REPLAY_R], masked=False)
    if battery == "O_time":
        return o_lever_calls([REPLAY_R])
    msg = f"no replay for {battery!r}"
    raise ValueError(msg)


@dataclass(frozen=True)
class Segment:
    """(stage, battery, model) の 1 区切り。driver の記録・再実行・時間切れの単位."""

    stage: str
    battery: str
    model: str
    calls: tuple[CallSpec, ...]

    @property
    def name(self) -> str:
        return f"{self.stage}/{self.battery}/{self.model}"


def pilot_plan() -> tuple[Segment, ...]:
    """§H: モデルは §A.1 の表の順、各モデルの中は v2 → v3 → G → O_time。最後に再生 (G → O_time)."""
    segs = [
        Segment(STAGE_PILOT, b, m, pilot_calls(b)) for m in MODELS for b in st.BATTERIES
    ]
    segs += [
        Segment(STAGE_REPLAY, b, REPLAY_MODEL, replay_calls(b)) for b in ("G", "O_time")
    ]
    return tuple(segs)


def main_order(r_by_battery: Mapping[str, int]) -> list[str]:
    """GO の battery を費用 (8B 換算) の安い順 (同点は名前の順、``st.budget`` と同じ鍵)."""
    cost = {b: r * st.SPECS[b].sec_per_rep() for b, r in r_by_battery.items()}
    return sorted(cost, key=lambda b: (cost[b], b))


def main_plan(
    r_by_battery: Mapping[str, int],
    models_by_battery: Mapping[str, Sequence[str]] | None = None,
) -> tuple[Segment, ...]:
    """§H: GO の battery を安い順に、各 battery の中はモデルを §A.1 の表の順.

    ``models_by_battery`` (pilot の入場集合、gate.json) を渡せば、その battery の入場モデルだけを回す。
    """
    return tuple(
        Segment(STAGE_MAIN, b, m, main_calls(b, r_by_battery[b]))
        for b in main_order(r_by_battery)
        for m in MODELS
        if models_by_battery is None or m in models_by_battery[b]
    )


def _canonical(obj: object) -> bytes:
    return json.dumps(
        obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def messages_sha256(messages: Sequence[Mapping[str, str]]) -> str:
    """4 battery の凍結の ``messages_sha256`` と同じ式 (ensure_ascii=False・sort_keys)."""
    blob = json.dumps(list(messages), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def segment_digest(seg: Segment) -> str:
    """区切りの全呼び出しの (key・seed・messages の sha・options) の digest (meta に記録する)."""
    rows = [
        [*spec.key(), spec.purpose, spec.seed, messages_sha256(spec.messages_list())]
        for spec in seg.calls
    ]
    return hashlib.sha256(
        _canonical(
            {
                "stage": seg.stage,
                "battery": seg.battery,
                "model": seg.model,
                "think": THINK,
                "decode": DECODE,
                "calls": rows,
            }
        )
    ).hexdigest()


def plan_digest(segments: Sequence[Segment]) -> str:
    return hashlib.sha256(
        _canonical([[s.name, segment_digest(s)] for s in segments])
    ).hexdigest()


# ------------------------------------------------------------ §C の battery 検査 (r の列の上)


@contextlib.contextmanager
def _shifted(battery: str, r0: int) -> Iterator[None]:
    """r を受ける凍結の関数を ``f(..., r0 + r)`` に一時的に差し替える (凍結の検査のコードを r の列で評価する).

    v2・v3: r は ``v2bat.layout`` だけを通る (``Layout.replicate`` を含む)。G: ``entry_order``・``option_order``・
    ``selection_entry_order``。O_time: ``entry_order``・``m0_order``・``option_order`` (``Unit.replicate`` はこの 3 つと
    seed だけに使われ、seed は ``seed_problems`` で別に見る)。
    """
    if battery in ("v2", "v3"):
        targets: list[tuple[Any, str]] = [(v2bat, "layout")]
    elif battery == "G":
        targets = [
            (gbat, "entry_order"),
            (gbat, "option_order"),
            (gbat, "selection_entry_order"),
        ]
    elif battery == "O_time":
        targets = [(obat, "entry_order"), (obat, "m0_order"), (obat, "option_order")]
    else:
        msg = f"unknown battery {battery!r}"
        raise ValueError(msg)
    saved = [(mod, name, getattr(mod, name)) for mod, name in targets]
    try:
        for mod, name, orig in saved:
            setattr(mod, name, _shift_fn(orig, r0))
        yield
    finally:
        for mod, name, orig in saved:
            setattr(mod, name, orig)


def _shift_fn(orig: Callable[..., Any], r0: int) -> Callable[..., Any]:
    def shifted(*args: Any) -> Any:
        *head, r = args
        return orig(*head, r0 + r)

    return shifted


def _contiguous(r_list: Sequence[int]) -> tuple[int, int]:
    rs = list(r_list)
    if not rs or rs != list(range(rs[0], rs[0] + len(rs))):
        msg = "r list must be non-empty and contiguous"
        raise ValueError(msg)
    return rs[0], len(rs)


def _tag(r0: int, problems: Sequence[str]) -> list[str]:
    """ずらした検査の違反文に始点を付ける (違反文の r は始点からの番号)."""
    return [f"[r0={r0}] {p}" for p in problems]


def v2_report(r_list: Sequence[int]) -> dict[str, list[str]]:
    """``skill_lever_battery.battery_report`` の全項目を r の列で (凍結の検査を差し替えた r で評価)."""
    r0, n = _contiguous(r_list)
    with _shifted("v2", r0):
        rep = v2bat.battery_report(n)
    return {
        k: _tag(r0, v) for k, v in rep.items() if isinstance(v, list) and k != "actions"
    }


def v3_report(r_list: Sequence[int]) -> dict[str, list[str]]:
    r0, n = _contiguous(r_list)
    with _shifted("v3", r0):
        rep = v3bat.battery_report(n)
    return {k: _tag(r0, v) for k, v in rep.items() if isinstance(v, list)}


_G_R_CHECKS: Final[tuple[str, ...]] = (
    "triple_prompts_differ_only_in_key",
    "probe_keys_absent",
    "non_leakage",
    "position_balance",
    "shared_within_family",
    "selection_layout_separate",
)
_G_FIXED_CHECKS: Final[tuple[str, ...]] = (
    "label_frequency",
    "state_tables",
    "dev_design",
    "triples",
    "pointed",
    "surface_overlap",
    "know_balance",
)


def g_report(
    r_list: Sequence[int], *, masked_r: Sequence[int] = ()
) -> dict[str, list[str]]:
    """``generalization_probe_battery.battery_report`` の項目を r の列で.

    r を持たない項目は凍結の関数をそのまま。r の列を回す項目は差し替えた r で凍結の関数を。
    ``prompt_budget`` は r の列そのもので (凍結は R_MAX = 24 に固定)、``masked_states`` は本登録の masked の r の列で
    (凍結は r = 50 の 1 点)、``seed_namespaces`` は ``seed_problems`` で見る。
    """
    r0, n = _contiguous(r_list)
    out: dict[str, list[str]] = {
        name: list(getattr(gbat, f"check_{name}")()) for name in _G_FIXED_CHECKS
    }
    with _shifted("G", r0):
        for name in _G_R_CHECKS:
            out[name] = _tag(r0, getattr(gbat, f"check_{name}")(n))
        out["prompt_budget"] = _tag(r0, gbat.check_prompt_budget(n))
    out["masked_states"] = g_masked_states(masked_r) if masked_r else []
    return out


def g_masked_states(
    r_list: Sequence[int], triples: Sequence[int] | None = None
) -> list[str]:
    """凍結の ``check_masked_states`` の述語を、本登録の masked の r の列 (と全つ組) で.

    凍結は (つ組 0, r = PILOT_R0) の 1 点だけを見る。triples = (0,) と r = [PILOT_R0] で凍結と同値 (test)。
    """
    out = []
    keys = {s.key for s in gbat.dev_situations()} | {
        p.situation.key for p in gbat.probes()
    }
    js = range(gbat.N_TRIPLES) if triples is None else triples
    for arm in gbat.LEVER_ARMS:
        for r in r_list:
            for j in js:
                order = gbat.entry_order(gbat.ARM_FAMILY[arm], j, r)
                masked = gbat.render_state(arm, order, masked=True)
                plain = gbat.render_state(arm, order)
                if any(k in masked for k in keys):
                    out.append(f"{arm}: masked state contains a key")
                stripped = plain
                for s in gbat.dev_situations():
                    stripped = stripped.replace(f"{s.key} /", f"{gbat.MASK} /")
                if stripped != masked:
                    out.append(f"{arm}: masked state differs beyond the key column")
    return sorted(set(out))


_O_R_CHECKS: Final[tuple[str, ...]] = (
    "layer1",
    "layer2",
    "non_leakage",
    "position_balance",
)
_O_FIXED_CHECKS: Final[tuple[str, ...]] = (
    "vocabulary",
    "rules",
    "state_tables",
    "multiset",
    "tags",
)


def o_report(
    r_list: Sequence[int], *, aux_r: Sequence[int] = ()
) -> dict[str, list[str]]:
    """``o_time_probe_battery.battery_report`` の項目を r の列で (``g_report`` と同じ方針).

    ``prompt_budget`` は lru_cache を通さずに r の列で計算する。``masked_states``・``m0_states`` は本登録の
    masked・M0 の r の列で (凍結は r 300–305)。
    """
    r0, n = _contiguous(r_list)
    out: dict[str, list[str]] = {
        name: list(getattr(obat, f"check_{name}")()) for name in _O_FIXED_CHECKS
    }
    with _shifted("O_time", r0):
        for name in _O_R_CHECKS:
            out[name] = _tag(r0, getattr(obat, f"check_{name}")(n))
        worst = obat.worst_prompt_bytes.__wrapped__(n)
    budget = []
    if worst > obat.MAX_PROMPT_BYTES:
        budget.append(f"prompt of {worst} bytes exceeds {obat.MAX_PROMPT_BYTES}")
    if (
        obat.MAX_PROMPT_BYTES + obat.CHAT_TEMPLATE_OVERHEAD + obat.NUM_PREDICT
        > obat.NUM_CTX
    ):
        budget.append("num_ctx does not cover the prompt budget")
    out["prompt_budget"] = _tag(r0, budget)
    units = _o_units(aux_r)
    out["masked_states"] = o_masked_states(units) if units else []
    out["m0_states"] = o_m0_states(units) if units else []
    return out


def o_masked_states(units: Sequence[obat.Unit]) -> list[str]:
    """凍結の ``check_masked_states`` の述語を、与えた単位で (凍結は ``pilot_units()``)."""
    out = []
    for u in units:
        a, b = obat.FAMILIES[u.family]
        for enc in obat.ENCODINGS:
            texts = set()
            for arm in (a, b):
                masked = obat.render_state(arm, enc, u, "masked")
                plain = obat.render_state(arm, enc, u)
                if any(obat.TAGS[enc][d] in masked for d in obat.DAYS):
                    out.append(f"{arm}/{enc} {u}: masked state shows a tag digit")
                if (
                    obat.mask_digits(plain).replace(
                        obat.DIGIT_PLACEHOLDER, obat.MASK_DIGIT
                    )
                    != masked
                ):
                    out.append(
                        f"{arm}/{enc} {u}: masked state differs beyond the tag digits"
                    )
                texts.add(
                    obat.normalized_messages(
                        obat.render_messages(arm, enc, u, "masked"), str
                    )
                )
            if len(texts) != 1:
                out.append(f"{a}/{b} {enc} {u}: masked prompts differ between the arms")
    return sorted(set(out))


def o_m0_states(units: Sequence[obat.Unit]) -> list[str]:
    """凍結の ``check_m0_states`` の述語を、与えた単位で."""
    out = []
    for u in units:
        a, b = obat.FAMILIES[u.family]
        for enc in obat.ENCODINGS:
            stripped = set()
            for arm in (a, b):
                text = obat.render_state(arm, enc, u, "m0")
                lines = text.split("\n")[1:]
                if len(lines) != obat.N_ROOMS:
                    out.append(
                        f"{arm}/{enc} {u}: M0 state does not have one row per room"
                    )
                want = {
                    obat.render_row(
                        obat.tag(enc, 2), room, *obat.state_table(arm)[2][room]
                    )
                    for room in obat.ROOMS
                }
                if set(lines) != want:
                    out.append(f"{arm}/{enc} {u}: M0 rows are not the newer-day rows")
                for act in obat.ACTIONS:
                    text = text.replace(act, "<L>")
                stripped.add(text)
            if len(stripped) != 1:
                out.append(f"{a}/{b} {enc} {u}: M0 states differ beyond labels")
    return sorted(set(out))


# ---- seed の名前空間の分離 (旧・pilot・本走の seed の集合が交わらない、§C)


# 使用済みの seed の集合 (旧 chain と段 1。名前空間ごと)
def _used_seed_sets(battery: str) -> dict[str, set[int]]:
    if battery in ("v2", "v3"):
        r_used = st.USED_R[battery][0]
        k_count = 10 if battery == "v2" else v3sc.FROZEN_K
        return {
            "old": {
                v2bat.sample_seed(r, qi, k)
                for r in r_used
                for qi in range(len(v2bat.lever_probes()))
                for k in range(k_count)
            }
        }
    if battery == "G":
        old_main = {
            gbat.sample_seed(f"fam{fi}", r, j, 0)
            for fi in range(2)
            for r in st.USED_R["G"][0]
            for j in range(gbat.N_TRIPLES)
        }
        old_pilot = {
            gbat.sample_seed(f"pilot_fam{fi}", r, j, 0)
            for fi in range(2)
            for r in st.USED_R["G"][1]
            for j in range(gbat.N_TRIPLES)
        }
        return {"old_main": old_main, "old_pilot": old_pilot}
    old_main = {
        obat.sample_seed(f"fam{u.family}", u.replicate, u.room, 0)
        for u in _o_units(st.USED_R["O_time"][0])
    }
    old_pilot = {
        obat.sample_seed(f"{mode}_fam{u.family}", u.replicate, u.room, 0)
        for mode in ("masked", "m0")
        for u in _o_units(st.USED_R["O_time"][1])
    }
    return {"old_main": old_main, "old_pilot": old_pilot}


def seed_problems(
    battery: str, stage_calls: Mapping[str, Sequence[CallSpec]]
) -> list[str]:
    """stage (pilot・main) の seed の集合が、旧の seed とも、互いとも交わらない (KNOW は旧 pilot の再生なので除く)."""
    out: list[str] = []
    used = _used_seed_sets(battery)
    sets: dict[str, set[int]] = {}
    for name, calls in stage_calls.items():
        for c in calls:
            if c.purpose == P_KNOW:
                continue
            sets.setdefault(f"{name}/{c.purpose}", set()).add(c.seed)
    # 同じ stage の中で seed を共有してよいのは同じ seed の単位だけ: 目的が違えば交わらない
    names = sorted(sets)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            same_stage_lever_control = a.split("/")[0] == b.split("/")[0] and {
                a.split("/")[1],
                b.split("/")[1],
            } <= {P_LEVER, P_C0, P_CONTROL}
            # v2・v3 は C0・L arm が lever と seed を共有する (凍結の設計、arm 間で同じ seed)
            if same_stage_lever_control and battery in ("v2", "v3"):
                continue
            if sets[a] & sets[b]:
                out.append(f"{battery}: seeds of {a} and {b} overlap")
    for uname, useeds in used.items():
        for name in names:
            if useeds & sets[name]:
                out.append(f"{battery}: seeds of {name} overlap the used {uname}")
    return out


def cross_battery_seed_problems(
    stage_calls: Mapping[str, Mapping[str, Sequence[CallSpec]]],
) -> list[str]:
    """v2 と v3 は同じ ``sample_seed`` を使うので、段 2 の r の範囲が交わらないこと (§C)."""
    a = {c.seed for calls in stage_calls["v2"].values() for c in calls}
    b = {c.seed for calls in stage_calls["v3"].values() for c in calls}
    return ["v2 and v3 stage-2 seeds overlap"] if a & b else []


def prompt_budget_problems(calls: Sequence[CallSpec]) -> list[str]:
    """送る全 prompt の byte 数 ≤ 凍結の上限 (token ≤ UTF-8 byte) で、上限 + template + 出力が num_ctx の内."""
    out = []
    worst = max(sum(len(c.encode("utf-8")) for _, c in s.messages) for s in calls)
    if worst > v2bat.MAX_PROMPT_BYTES:
        out.append(f"prompt of {worst} bytes exceeds {v2bat.MAX_PROMPT_BYTES}")
    if (
        v2bat.MAX_PROMPT_BYTES + v2bat.CHAT_TEMPLATE_OVERHEAD + v2bat.NUM_PREDICT
        > v2bat.NUM_CTX
    ):
        out.append("num_ctx does not cover the prompt budget")
    return out


def battery_checks(
    battery: str, main_r_count: int | None = None
) -> dict[str, list[str]]:
    """§C の作り直す検査 (pilot の r の列と、与えれば本走の r の列)。値が全部空なら合格.

    項目名は ``<stage>:<凍結の項目>``。stage の r の範囲 (``st.check_r_range``)・seed の名前空間・
    送る prompt の byte 予算を加える。
    """
    spec = st.SPECS[battery]
    rep: dict[str, list[str]] = {}
    lists: dict[str, list[int]] = {"pilot": pilot_lever_r(battery)}
    if main_r_count is not None:
        lists["main"] = main_r(battery, main_r_count)
    for stage, rs in lists.items():
        rep[f"{stage}:r_range"] = st.check_r_range(spec, rs, main=stage == "main")
        if battery == "v2":
            sub = v2_report(rs)
        elif battery == "v3":
            sub = v3_report(rs)
        elif battery == "G":
            sub = g_report(rs, masked_r=pilot_aux_r("G") if stage == "pilot" else ())
        else:
            sub = o_report(rs, aux_r=pilot_aux_r("O_time") if stage == "pilot" else ())
        rep.update({f"{stage}:{k}": v for k, v in sub.items()})
    if battery in PILOT_AUX_R0:
        aux = pilot_aux_r(battery)
        rep["pilot_aux:r_range"] = (
            []
            if aux[0] % spec.cycle == 0 and len(aux) % spec.cycle == 0
            else [f"{battery}: masked r range is not a whole number of position cycles"]
        )
        if battery == "G":
            rep["pilot_aux:position_balance"] = g_report(aux)["position_balance"]
        else:
            rep["pilot_aux:position_balance"] = o_report(aux)["position_balance"]
    stage_calls: dict[str, tuple[CallSpec, ...]] = {"pilot": pilot_calls(battery)}
    if main_r_count is not None:
        stage_calls["main"] = main_calls(battery, main_r_count)
    rep["seed_namespaces"] = seed_problems(battery, stage_calls)
    rep["prompt_budget_sent"] = prompt_budget_problems(
        [c for calls in stage_calls.values() for c in calls]
    )
    return rep


def violations(report: Mapping[str, Sequence[str]]) -> list[str]:
    return [f"{k}: {v}" for k, vs in report.items() for v in vs]

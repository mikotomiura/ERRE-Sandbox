"""判別性 gate 段 2 — 記録の独立な読み手 (Codex r1 H1・H6、decisions DD-4).

規則の SSOT は ``experiments/20261126-benchmark-stage2-discriminability/prereg.md`` (第 1 段 PILOT-FROZEN)。

* 読むのは ``<run>/<stage>/segments.json`` が ``completed`` と確定した区切りの ``adopted_attempt`` の
  ``records.jsonl``・``meta.json`` だけ。bytes の sha を状態表と照合する (以前の attempt に戻らない・補完しない)。
* 期待する呼び出しは ``benchmark_stage2_plan`` を使わずに列挙する (DD-1: driver と同じ誤りを共有しない)。
  key の集合は各 battery の凍結の grid の形を本登録の r の列 (§C) に置き、順は凍結の順の関数
  (v3 = ``call_rank``、O_time = ``unit_calls``、G = ``triple_probes``) で並べる。
  seed と prompt の sha は凍結の ``expected_sample`` / ``expected`` で行ごとに再計算する。
  区切りの digest も独立に再計算し、状態表・meta の値 (plan が作ったもの) と照合する。
* 生の応答は凍結の parse で読み直す (G の KNOW は ``parse_class``)。記録に parse の欄は無い。
* 分類 (§G.2-1・2、§F-1・2)
  - **STOP (records)** (``violations``): 状態表・meta・schema・重複・範囲外・順・seed・prompt・digest の違反。
  - **not_computed**: 区切りが completed でない (通信・時間切れ・未着手)、または正しい行の単なる欠け。
  - **invalid_meta**: driver が区切りの開始時に digest・template の違いを見た (そのモデルを INVALID)。
  - **invalid_version**: Ollama の版の違い (run の全モデルを INVALID)。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Final

from scripts import benchmark_stage2_stats as st
from scripts import generalization_probe_battery as gbat
from scripts import generalization_probe_pilot_gate as gpg
from scripts import generalization_probe_scorer as gsc
from scripts import o_time_probe_battery as obat
from scripts import o_time_probe_pilot_gate as opg
from scripts import o_time_probe_scorer as osc
from scripts import skill_experience_battery as v3bat
from scripts import skill_experience_scorer as v3sc
from scripts import skill_lever_battery as v2bat
from scripts import skill_lever_scorer as v2sc

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable, Mapping, Sequence

# ------------------------------------------------------------ 本登録の値 (prereg の写し。plan・driver から読まない)

MODELS: Final[tuple[str, ...]] = (  # §A.1 の表の順
    "qwen3:1.7b",
    "qwen3:4b-q4_K_M",
    "qwen3:8b",
    "qwen3:14b",
    "llama3.1:8b",
    "gemma2:9b",
)
REPLAY_MODEL: Final[str] = "qwen3:8b"
REPLAY_BATTERIES: Final[tuple[str, ...]] = ("G", "O_time")
STAGE_PILOT: Final[str] = "pilot"
STAGE_MAIN: Final[str] = "main"
STAGE_REPLAY: Final[str] = "replay"

# §C の r の範囲
PILOT_LEVER_R: Final[dict[str, range]] = {
    "v2": range(1000, 1012),
    "v3": range(1200, 1212),
    "G": range(24, 36),
    "O_time": range(312, 324),
}
PILOT_AUX_R: Final[dict[str, range]] = {"G": range(24, 30), "O_time": range(312, 318)}
MAIN_R0: Final[dict[str, int]] = {"v2": 2000, "v3": 3000, "G": 60, "O_time": 324}
REPLAY_R: Final[range] = range(1)

# §A.1 の実行条件 (decode は各 battery の凍結値、top_k 20 は DM-9)
EXPECTED_REQUEST: Final[dict[str, Any]] = {
    "think": False,
    "stream": False,
    "options_without_seed": {
        "temperature": v2bat.TEMPERATURE,
        "top_p": v2bat.TOP_P,
        "top_k": 20,
        "repeat_penalty": v2bat.REPEAT_PENALTY,
        "num_ctx": v2bat.NUM_CTX,
        "num_predict": v2bat.NUM_PREDICT,
    },
}

# 記録の 1 行の欄 (driver の RECORD_KEYS と同じ集合であることは test で結ぶ)
_INT: Final[tuple[str, ...]] = (
    "attempt",
    "call_index",
    "replicate",
    "k",
    "seed",
    "n_sends",
)
_STR: Final[tuple[str, ...]] = (
    "stage",
    "battery",
    "model",
    "purpose",
    "arm",
    "probe_id",
    "prompt_sha256",
    "raw",
    "response_model",
)
_OPT_STR: Final[tuple[str, ...]] = ("encoding", "done_reason")
_OPT_INT: Final[tuple[str, ...]] = ("prompt_eval_count", "eval_count")
ROW_KEYS: Final[frozenset[str]] = frozenset(_INT + _STR + _OPT_STR + _OPT_INT)
MAX_SENDS: Final[int] = 4  # 初回 + 再送 3 回 (§H)
MAX_ATTEMPTS: Final[int] = 2

# 区切りの状態 (driver の segments.json の値)
S_COMPLETED: Final[str] = "completed"
S_TRANSPORT: Final[str] = "not_computed_transport"
S_TIMEOUT: Final[str] = "not_computed_timeout"
S_NOT_STARTED: Final[str] = "not_started"
S_INVALID_META: Final[str] = "invalid_meta"
S_INVALID_VERSION: Final[str] = "invalid_version"
DRIVER_STATUSES: Final[frozenset[str]] = frozenset(
    {
        S_COMPLETED,
        S_TRANSPORT,
        S_TIMEOUT,
        S_NOT_STARTED,
        S_INVALID_META,
        S_INVALID_VERSION,
    }
)
# 読み手の分類
R_OK: Final[str] = "ok"
R_NOT_COMPUTED: Final[str] = "not_computed"
R_INVALID_META: Final[str] = "invalid_meta"
R_INVALID_VERSION: Final[str] = "invalid_version"

P_LEVER, P_C0, P_CONTROL, P_MASKED, P_M0, P_KNOW = (
    "lever",
    "c0",
    "control",
    "masked",
    "m0",
    "know",
)

# 記録の key = (arm, encoding, replicate, probe_id, k)
Key = tuple[str, str | None, int, str, int]


# ------------------------------------------------------------ 期待する呼び出し (plan に頼らない列挙)


@dataclass(frozen=True)
class Expected:
    key: Key
    purpose: str
    seed: int
    prompt_sha256: str
    parse: Callable[[str], str | None]


_V2_QI: Final[dict[str, int]] = {
    p.probe_id: i for i, p in enumerate(v2bat.lever_probes())
}
_G_PROBE: Final[dict[str, gbat.Probe]] = {p.probe_id: p for p in gbat.probes()}
_O_MASKED: Final[dict[str, str]] = dict(opg.MASKED_ARMS)
_O_M0: Final[dict[str, str]] = dict(opg.M0_ARMS)


def _v2_rank(arm: str, r: int, qi: int, k: int) -> tuple[int, int, int]:
    """凍結の v2 の順: C0 が先、次に (r, probe, k) の block ごとに lever 4 arm を block mod 4 だけ巡回."""
    block = (r * len(v2bat.lever_probes()) + qi) * v2sc.FROZEN_K + k
    if arm == v2bat.ARM_C0:
        return (0, block, 0)
    pos = (v2bat.LEVER_ARMS.index(arm) - block % len(v2bat.LEVER_ARMS)) % len(
        v2bat.LEVER_ARMS
    )
    return (1, block, pos)


def _v2_expected(rs: Sequence[int]) -> list[Expected]:
    grid = [
        (arm, r, p.probe_id, k)
        for arm in v2bat.ALL_ARMS
        for r in rs
        for p in v2bat.lever_probes()
        for k in range(v2sc.FROZEN_K)
    ]
    grid.sort(key=lambda x: _v2_rank(x[0], x[1], _V2_QI[x[2]], x[3]))
    out = []
    for arm, r, pid, k in grid:
        seed, sha = v2sc.expected_sample(arm, r, _V2_QI[pid], k)
        purpose = P_C0 if arm == v2bat.ARM_C0 else P_LEVER
        out.append(
            Expected((arm, None, r, pid, k), purpose, seed, sha, v2sc.parse_choice)
        )
    return out


def _v3_expected(rs: Sequence[int]) -> list[Expected]:
    grid = [
        (arm, r, p.probe_id, k)
        for arm in v3bat.ALL_ARMS
        for r in rs
        for p in v2bat.lever_probes()
        for k in range(v3sc.FROZEN_K)
    ]
    grid.sort(key=lambda x: v3sc.call_rank(x[0], x[1], _V2_QI[x[2]], x[3]))
    out = []
    for arm, r, pid, k in grid:
        seed, sha = v3sc.expected_sample(arm, r, _V2_QI[pid], k)
        purpose = (
            P_C0
            if arm == v3bat.ARM_C0
            else P_CONTROL
            if arm in v3bat.CONTROL_ARMS
            else P_LEVER
        )
        out.append(
            Expected((arm, None, r, pid, k), purpose, seed, sha, v3sc.parse_choice)
        )
    return out


def _g_rank(lever: str, r: int, pid: str) -> tuple[int, int, int, int, int]:
    """凍結の G の順: r → 族 → つ組 → つ組の中の probe → 族内の arm."""
    probe = _G_PROBE[pid]
    fi = gbat.ARM_FAMILY[lever]
    qi = [p.probe_id for p in gbat.triple_probes(probe.triple)].index(pid)
    return (r, fi, probe.triple, qi, gbat.FAMILIES[fi].index(lever))


def _g_lever_expected(rs: Sequence[int]) -> list[Expected]:
    grid = [
        (arm, r, p.probe_id)
        for arm in gbat.LEVER_ARMS
        for r in rs
        for p in gbat.probes()
    ]
    grid.sort(key=lambda x: _g_rank(x[0], x[1], x[2]))
    out = []
    for arm, r, pid in grid:
        seed, sha = gsc.expected_sample(arm, r, _G_PROBE[pid], 0)
        out.append(
            Expected((arm, None, r, pid, 0), P_LEVER, seed, sha, gsc.parse_choice)
        )
    return out


def _g_masked_expected(rs: Sequence[int]) -> list[Expected]:
    grid = [
        (arm, r, p.probe_id)
        for arm in gpg.MASKED_ARMS
        for r in rs
        for p in gbat.probes()
    ]
    grid.sort(key=lambda x: _g_rank(gpg.MASKED_ARMS[x[0]], x[1], x[2]))
    out = []
    for arm, r, pid in grid:
        seed, sha = gpg.expected(arm, r, pid, 0)
        out.append(
            Expected((arm, None, r, pid, 0), P_MASKED, seed, sha, gsc.parse_choice)
        )
    return out


def _g_know_expected() -> list[Expected]:
    out = []
    for i in range(len(gbat.all_keys())):
        for k in range(gbat.KNOW_K):
            pid = gpg.know_probe_id(i)
            seed, sha = gpg.expected(gpg.ARM_KNOW, 0, pid, k)
            out.append(
                Expected(
                    (gpg.ARM_KNOW, None, 0, pid, k), P_KNOW, seed, sha, gpg.parse_class
                )
            )
    return out


def _o_units(rs: Sequence[int]) -> list[obat.Unit]:
    return [
        obat.Unit(fi, i, r)
        for r in rs
        for fi in range(len(obat.FAMILIES))
        for i in range(obat.N_ROOMS)
    ]


def _o_lever_expected(rs: Sequence[int]) -> list[Expected]:
    out = []
    for u in _o_units(rs):
        for arm, enc in obat.unit_calls(u):
            seed, sha = osc.expected_sample(arm, enc, u, 0)
            key = (arm, enc, u.replicate, osc.probe_id(u.room), 0)
            out.append(Expected(key, P_LEVER, seed, sha, osc.parse_choice))
    return out


def _o_aux_expected(rs: Sequence[int]) -> list[Expected]:
    """凍結の旧 pilot の順: 単位ごとに masked の 4 → M0 の 4."""
    masked_of = {lever: m for m, lever in _O_MASKED.items()}
    m0_of = {lever: m for m, lever in _O_M0.items()}
    out = []
    for u in _o_units(rs):
        for names, purpose in ((masked_of, P_MASKED), (m0_of, P_M0)):
            for lever, enc in obat.unit_calls(u):
                arm = names[lever]
                pid = osc.probe_id(u.room)
                seed, sha = opg.expected(arm, enc, u.replicate, pid, 0)
                out.append(
                    Expected(
                        (arm, enc, u.replicate, pid, 0),
                        purpose,
                        seed,
                        sha,
                        osc.parse_choice,
                    )
                )
    return out


@lru_cache(maxsize=16)
def expected_calls(
    stage: str, battery: str, r_count: int | None = None
) -> tuple[Expected, ...]:
    """(stage, battery) の期待する呼び出し (順どおり)。main は r_count が要る."""
    return tuple(_expected_calls(stage, battery, r_count))


def _expected_calls(stage: str, battery: str, r_count: int | None) -> list[Expected]:
    if stage == STAGE_PILOT:
        rs = PILOT_LEVER_R[battery]
        if battery == "v2":
            return _v2_expected(rs)
        if battery == "v3":
            return _v3_expected(rs)
        if battery == "G":
            return (
                _g_lever_expected(rs)
                + _g_masked_expected(PILOT_AUX_R["G"])
                + _g_know_expected()
            )
        if battery == "O_time":
            return _o_lever_expected(rs) + _o_aux_expected(PILOT_AUX_R["O_time"])
    if stage == STAGE_REPLAY:
        if battery == "G":
            return _g_lever_expected(REPLAY_R)
        if battery == "O_time":
            return _o_lever_expected(REPLAY_R)
    if stage == STAGE_MAIN and r_count is not None:
        rs = range(MAIN_R0[battery], MAIN_R0[battery] + r_count)
        fn = {
            "v2": _v2_expected,
            "v3": _v3_expected,
            "G": _g_lever_expected,
            "O_time": _o_lever_expected,
        }[battery]
        return fn(rs)
    msg = f"no expected calls for {stage}/{battery}"
    raise ValueError(msg)


def expected_order(
    stage: str,
    models: Sequence[str] = MODELS,
    r_by_battery: Mapping[str, int] | None = None,
    models_by_battery: Mapping[str, Sequence[str]] | None = None,
) -> list[tuple[str, str, str]]:
    """状態表の区切りの順 (§H)。pilot = モデル → battery、最後に再生。main = 費用の安い順 → モデル."""
    if stage == STAGE_PILOT:
        out = [(STAGE_PILOT, b, m) for m in models for b in st.BATTERIES]
        if REPLAY_MODEL in models:
            out += [(STAGE_REPLAY, b, REPLAY_MODEL) for b in REPLAY_BATTERIES]
        return out
    if stage == STAGE_MAIN and r_by_battery is not None:
        cost = {b: r * st.SPECS[b].sec_per_rep() for b, r in r_by_battery.items()}
        order = sorted(cost, key=lambda b: (cost[b], b))
        return [
            (STAGE_MAIN, b, m)
            for b in order
            for m in MODELS
            if m in (models if models_by_battery is None else models_by_battery[b])
        ]
    msg = f"no expected order for {stage}"
    raise ValueError(msg)


# ------------------------------------------------------------ digest の独立な再計算


def _canonical(obj: object) -> bytes:
    return json.dumps(
        obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def segment_digest(
    stage: str, battery: str, model: str, calls: Sequence[Expected]
) -> str:
    """区切りの (key・目的・seed・prompt の sha・decode) の digest (状態表・meta の値と照合する)."""
    rows = [
        [
            battery,
            e.key[0],
            e.key[1],
            e.key[2],
            e.key[3],
            e.key[4],
            e.purpose,
            e.seed,
            e.prompt_sha256,
        ]
        for e in calls
    ]
    obj = {
        "stage": stage,
        "battery": battery,
        "model": model,
        "think": EXPECTED_REQUEST["think"],
        "decode": EXPECTED_REQUEST["options_without_seed"],
        "calls": rows,
    }
    return hashlib.sha256(_canonical(obj)).hexdigest()


def plan_digest(named: Sequence[tuple[str, str]]) -> str:
    return hashlib.sha256(_canonical([list(x) for x in named])).hexdigest()


def seg_name(stage: str, battery: str, model: str) -> str:
    return f"{stage}/{battery}/{model}"


def model_dirname(model: str) -> str:
    return model.replace(":", "_")


# ------------------------------------------------------------ 読み


@dataclass(frozen=True)
class Row:
    key: Key
    purpose: str
    raw: str
    parsed: str | None
    call_index: int
    seed: int
    prompt_sha256: str
    prompt_eval_count: int | None


@dataclass
class SegmentRead:
    stage: str
    battery: str
    model: str
    status: str  # R_OK / R_NOT_COMPUTED / R_INVALID_META / R_INVALID_VERSION
    reason: str | None = None
    driver_status: str | None = None
    rows: list[Row] = field(default_factory=list)
    meta: dict[str, Any] | None = None
    records_sha256: str | None = None
    meta_sha256: str | None = None
    adopted_attempt: int | None = None

    @property
    def name(self) -> str:
        return seg_name(self.stage, self.battery, self.model)

    def parsed(self) -> dict[Key, str | None]:
        return {r.key: r.parsed for r in self.rows}


@dataclass
class RunRead:
    stage: str
    segments: dict[str, SegmentRead]
    violations: list[str]
    inputs: dict[str, Any]

    @property
    def stop(self) -> bool:
        return bool(self.violations)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_int(x: object) -> bool:
    return type(x) is int


def _row_schema(obj: object) -> str | None:
    if not isinstance(obj, dict) or set(obj) != ROW_KEYS:
        return "row keys differ"
    for f in _INT:
        if not _is_int(obj[f]):
            return f"{f} is not int"
    for f in _STR:
        if type(obj[f]) is not str:
            return f"{f} is not str"
    for f in _OPT_STR:
        if obj[f] is not None and type(obj[f]) is not str:
            return f"{f} is not str or null"
    for f in _OPT_INT:
        if obj[f] is not None and not _is_int(obj[f]):
            return f"{f} is not int or null"
    return None


def _same(got: object, want: object) -> bool:
    """JSON の値として型まで一致 (bool と int、float と int を区別)."""
    if type(got) is not type(want):
        return False
    if isinstance(want, dict):
        assert isinstance(got, dict)
        return set(got) == set(want) and all(_same(got[k], want[k]) for k in want)
    if isinstance(want, list):
        assert isinstance(got, list)
        return len(got) == len(want) and all(
            _same(a, b) for a, b in zip(got, want, strict=True)
        )
    return got == want


def meta_violations(
    meta: object,
    stage: str,
    battery: str,
    model: str,
    attempt: int,
    n_calls: int,
    seg_digest: str,
    reference: Mapping[str, Any],
) -> list[str]:
    """completed の区切りの meta.json: 区切り・attempt・版・digest・template・request が登録どおり."""
    if not isinstance(meta, dict):
        return ["meta is not an object"]
    out = []
    want = {
        "stage": stage,
        "battery": battery,
        "model": model,
        "attempt": attempt,
        "n_calls": n_calls,
        "segment_digest": seg_digest,
        "request": EXPECTED_REQUEST,
        "ollama_version": reference.get("ollama_version"),
    }
    for k, v in want.items():
        if k not in meta or not _same(meta[k], v):
            out.append(f"meta {k} differs")
    ref = reference.get("models", {}).get(model, {})
    template = meta.get("template")
    if not isinstance(template, str):
        out.append("meta template is not a string")
    elif _sha(template.encode("utf-8")) != meta.get("template_sha256"):
        out.append("meta template_sha256 is not the sha of the template")
    for k in ("model_digest", "template_sha256"):
        if not isinstance(ref, dict) or meta.get(k) != ref.get(k):
            out.append(f"meta {k} differs from models.json")
    return out


def _read_completed(
    root: pathlib.Path,
    sr: SegmentRead,
    entry: Mapping[str, Any],
    calls: Sequence[Expected],
    seg_digest: str,
    reference: Mapping[str, Any],
    run_stage: str,
) -> list[str]:
    """completed の区切りを読み、STOP (records) の違反を返す (欠けだけなら sr を not_computed にする)."""
    name = sr.name
    attempt = entry.get("adopted_attempt")
    if not _is_int(attempt) or not 1 <= attempt <= MAX_ATTEMPTS:
        return [f"{name}: adopted_attempt is not 1 or 2"]
    if entry.get("attempts_run") != attempt:
        return [f"{name}: adopted_attempt is not the last attempt"]
    base = root if sr.stage == run_stage else root / sr.stage
    adir = base / sr.battery / model_dirname(sr.model) / f"attempt-{attempt}"
    try:
        rec_bytes = (adir / "records.jsonl").read_bytes()
        meta_bytes = (adir / "meta.json").read_bytes()
    except OSError as exc:
        return [f"{name}: cannot read adopted attempt ({type(exc).__name__})"]
    out = []
    if _sha(rec_bytes) != entry.get("records_sha256"):
        out.append(f"{name}: records sha differs from segments.json")
    if _sha(meta_bytes) != entry.get("meta_sha256"):
        out.append(f"{name}: meta sha differs from segments.json")
    try:
        meta = json.loads(meta_bytes.decode("utf-8"))
    except ValueError:
        return [*out, f"{name}: meta is not JSON"]
    out += [
        f"{name}: {v}"
        for v in meta_violations(
            meta,
            sr.stage,
            sr.battery,
            sr.model,
            attempt,
            len(calls),
            seg_digest,
            reference,
        )
    ]
    try:
        text = rec_bytes.decode("ascii")
    except UnicodeDecodeError:
        return [*out, f"{name}: records are not ASCII"]
    lines = text.split("\n")  # LF だけで割る (U+2028 は escape 済み)
    if lines[-1] != "":
        return [*out, f"{name}: records do not end with LF"]
    by_key = {e.key: e for e in calls}
    order = {e.key: i for i, e in enumerate(calls)}
    seen: set[Key] = set()
    ranks: list[int] = []
    rows: list[Row] = []
    for i, line in enumerate(lines[:-1]):
        try:
            obj = json.loads(line)
        except ValueError:
            out.append(f"{name}: line {i} is not JSON")
            continue
        bad = _row_schema(obj)
        if bad:
            out.append(f"{name}: line {i}: {bad}")
            continue
        key: Key = (
            obj["arm"],
            obj["encoding"],
            obj["replicate"],
            obj["probe_id"],
            obj["k"],
        )
        ident = {
            "stage": sr.stage,
            "battery": sr.battery,
            "model": sr.model,
            "attempt": attempt,
            "call_index": i,
            "response_model": sr.model,
        }
        if any(obj[k] != v for k, v in ident.items()):
            out.append(
                f"{name}: line {i}: stage/battery/model/attempt/call_index/response_model differ"
            )
        if key in seen:
            out.append(f"{name}: duplicate key {key}")
            continue
        seen.add(key)
        exp = by_key.get(key)
        if exp is None:
            out.append(f"{name}: key outside the registered grid {key}")
            continue
        ranks.append(order[key])
        if obj["purpose"] != exp.purpose:
            out.append(f"{name}: {key}: purpose differs")
        if obj["seed"] != exp.seed:
            out.append(f"{name}: {key}: seed differs from the frozen schedule")
        if obj["prompt_sha256"] != exp.prompt_sha256:
            out.append(f"{name}: {key}: prompt differs from the frozen renderer")
        if not 1 <= obj["n_sends"] <= MAX_SENDS:
            out.append(f"{name}: {key}: n_sends out of range")
        rows.append(
            Row(
                key,
                exp.purpose,
                obj["raw"],
                exp.parse(obj["raw"]),
                i,
                obj["seed"],
                obj["prompt_sha256"],
                obj["prompt_eval_count"],
            )
        )
    if ranks != sorted(ranks):
        out.append(f"{name}: call order differs from the frozen order")
    if out:
        return out
    sr.rows = rows
    sr.meta = meta
    sr.records_sha256 = _sha(rec_bytes)
    sr.meta_sha256 = _sha(meta_bytes)
    sr.adopted_attempt = attempt
    if len(seen) < len(calls):
        sr.status = R_NOT_COMPUTED
        sr.reason = f"{len(calls) - len(seen)} rows missing"
        sr.rows = []
    return []


def read_run(
    run_dir: pathlib.Path,
    stage: str,
    reference: Mapping[str, Any],
    *,
    models: Sequence[str] = MODELS,
    r_by_battery: Mapping[str, int] | None = None,
    models_by_battery: Mapping[str, Sequence[str]] | None = None,
) -> RunRead:
    """``<run>/<stage>`` を読む。STOP (records) の違反は ``violations`` に (例外にしない)."""
    root = run_dir / stage
    inputs: dict[str, Any] = {}
    try:
        table_bytes = (root / "segments.json").read_bytes()
        table = json.loads(table_bytes.decode("utf-8"))
    except (OSError, ValueError) as exc:
        return RunRead(
            stage, {}, [f"segments.json unreadable ({type(exc).__name__})"], inputs
        )
    inputs["segments_json_sha256"] = _sha(table_bytes)
    order = expected_order(stage, models, r_by_battery, models_by_battery)
    names = [seg_name(*x) for x in order]
    violations: list[str] = []
    if not isinstance(table, dict) or table.get("run_stage") != stage:
        return RunRead(stage, {}, ["segments.json run_stage differs"], inputs)
    if table.get("expected_ollama_version") != reference.get("ollama_version"):
        violations.append(
            "segments.json expected_ollama_version differs from models.json"
        )
    if table.get("order") != names:
        return RunRead(
            stage, {}, [*violations, "segments.json order differs from §H"], inputs
        )
    entries = table.get("segments")
    if not isinstance(entries, dict) or set(entries) != set(names):
        return RunRead(
            stage, {}, [*violations, "segments.json segments differ from §H"], inputs
        )
    digests = []
    segs: dict[str, SegmentRead] = {}
    for (s, b, m), name in zip(order, names, strict=True):
        calls = expected_calls(
            s, b, None if r_by_battery is None else r_by_battery.get(b)
        )
        dig = segment_digest(s, b, m, calls)
        digests.append((name, dig))
        entry = entries[name]
        sr = SegmentRead(s, b, m, R_NOT_COMPUTED)
        segs[name] = sr
        if not isinstance(entry, dict) or entry.get("status") not in DRIVER_STATUSES:
            violations.append(f"{name}: unknown status")
            continue
        sr.driver_status = entry["status"]
        sr.reason = entry.get("reason")
        if entry.get("segment_digest") != dig or entry.get("n_calls") != len(calls):
            violations.append(
                f"{name}: segment digest differs from the frozen schedule"
            )
            continue
        if entry["status"] != S_COMPLETED:
            if entry.get("adopted_attempt") is not None:
                violations.append(f"{name}: adopted_attempt on a non-completed segment")
            sr.status = {
                S_INVALID_META: R_INVALID_META,
                S_INVALID_VERSION: R_INVALID_VERSION,
            }.get(entry["status"], R_NOT_COMPUTED)
            continue
        sr.status = R_OK
        violations += _read_completed(root, sr, entry, calls, dig, reference, stage)
    if table.get("plan_digest") != plan_digest(digests):
        violations.append("segments.json plan_digest differs from the frozen schedule")
    statuses = {sr.status for sr in segs.values()}
    if R_INVALID_VERSION in statuses and statuses != {R_INVALID_VERSION}:
        violations.append("invalid_version on some segments only (§A.1: the whole run)")
    inputs["segments"] = {
        n: {"records_sha256": sr.records_sha256, "meta_sha256": sr.meta_sha256}
        for n, sr in segs.items()
        if sr.status == R_OK
    }
    return RunRead(stage, segs, sorted(set(violations)), inputs)


# ------------------------------------------------------------ 凍結の Sample への写し (集計用。添字だけを付け替える)


def g_samples(rows: Sequence[Row], r_shift: int = 0) -> list[gsc.Sample]:
    """G の凍結の ``Sample`` (parse は読み手が凍結の関数でしたもの)。replicate は集計用に r_shift だけずらす."""
    return [
        gsc.Sample(
            row.call_index,
            row.key[0],
            row.key[2] + (r_shift if row.key[0] != gpg.ARM_KNOW else 0),
            row.key[3],
            row.key[4],
            row.seed,
            row.prompt_sha256,
            row.raw,
            row.parsed,
        )
        for row in rows
    ]


def o_samples(rows: Sequence[Row], r_shift: int = 0) -> list[osc.Sample]:
    return [
        osc.Sample(
            row.call_index,
            row.key[0],
            str(row.key[1]),
            row.key[2] + r_shift,
            row.key[3],
            row.key[4],
            row.seed,
            row.prompt_sha256,
            row.raw,
            row.parsed,
        )
        for row in rows
    ]


def unit_choices(
    battery: str, rows: Sequence[Row]
) -> dict[tuple[Any, ...], str | None]:
    """``benchmark_stage2_units`` の key の形 (v2・v3・G = (arm, r, probe, k)、O_time = (arm, enc, r, probe, k))."""
    if battery == "O_time":
        return {r.key: r.parsed for r in rows}
    return {(r.key[0], r.key[2], r.key[3], r.key[4]): r.parsed for r in rows}


def load_reference(path: pathlib.Path) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    return json.loads(data.decode("utf-8")), _sha(data)

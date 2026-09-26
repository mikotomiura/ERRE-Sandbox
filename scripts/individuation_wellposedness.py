"""個性化 door 条件① — weight-space の seed floor を事前登録 rule で判定する spike.

事前登録 = ``experiments/20260926-individuation-metric-wellposedness/prereg.md``。
本スクリプトは起動時に prereg の sha256 を観測して results.json に書く (封印値を
引数 default に置かない)。

計算は CPU・numpy のみ。safetensors は依存を増やさず header を直接 parse する。
LoRA の ΔW = s·B·A (d_out×d_in) は実体化せず、r×r の積の trace で内積を取る:

* raw:   ⟨ΔWa, ΔWb⟩_F = s_a s_b · tr((Baᵀ Bb)(Ab Aaᵀ))
* Gram:  ⟨Ga, Gb⟩_F   = ‖ΔWaᵀ ΔWb‖_F²
                     = s_a² s_b² · tr((Bbᵀ Ba)(Aa Aaᵀ)(Baᵀ Bb)(Ab Abᵀ))   (G = ΔW ΔWᵀ)

ノルムが 0 の module の cosine は UNDEFINED (None) で、数値に畳まない。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Final

import numpy as np

EXP_REL: Final[str] = "experiments/20260926-individuation-metric-wellposedness"
PREREG_REL: Final[str] = f"{EXP_REL}/prereg.md"
LORA_ROOT: Final[str] = "data/lora/m9-c-adopt-v2"
SEEDS: Final[tuple[int, ...]] = (42, 43, 44)
MODULE_TYPES: Final[tuple[str, ...]] = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
)
H2_THRESHOLD: Final[float] = 0.5  # prereg §5: ‖Ĝa−Ĝb‖ < ‖Ĝa−0‖ ⇔ cos_G > 0.5
H2_RHO_THRESHOLD: Final[float] = 1.0  # prereg §5: ‖Ga−Gb‖ < mean(‖Ga‖, ‖Gb‖)
N_LAYERS: Final[int] = 36
_CONFIG_KEYS: Final[tuple[str, ...]] = (
    "r",
    "lora_alpha",
    "use_rslora",
    "rank_pattern",
    "alpha_pattern",
)
NULL_PERCENTILE: Final[float] = 99.0  # prereg §4
SELF_TOL: Final[float] = 1e-6  # prereg §5 G0-b

VERDICT_PASS: Final[str] = "PASS"  # noqa: S105 — verdict label, not a secret
VERDICT_ABSENT: Final[str] = "NO_GO_EFFECT_ABSENT"
VERDICT_UNDERPOWERED: Final[str] = "INCONCLUSIVE_UNDERPOWERED"
VERDICT_INVALID: Final[str] = "INVALID_SCORER"

_KEY_RE = re.compile(
    r"layers\.(\d+)\.(self_attn|mlp)\.([a-z_]+_proj)\.lora_([AB])\.weight$",
)
_PARENT: Final[dict[str, str]] = {
    "q_proj": "self_attn",
    "k_proj": "self_attn",
    "v_proj": "self_attn",
    "o_proj": "self_attn",
    "gate_proj": "mlp",
}
MOCK_TYPES: Final[tuple[str, ...]] = ("q_proj", "k_proj", "v_proj", "o_proj")
_DTYPES: Final[dict[str, type[np.generic]]] = {
    "F32": np.float32,
    "F16": np.float16,
    "F64": np.float64,
}

ModuleKey = tuple[int, str]


@dataclass(frozen=True)
class Module:
    """One LoRA module: ΔW = scale · B · A (float64)."""

    a: np.ndarray  # r × d_in
    b: np.ndarray  # d_out × r
    scale: float


Adapter = dict[ModuleKey, Module]


# --------------------------------------------------------------------------- IO


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_sha256(path: Path) -> str | None:
    """sha256, or None when the file is missing or unreadable (never raises)."""
    try:
        return sha256_file(path)
    except OSError:
        return None


def read_safetensors(path: Path) -> dict[str, np.ndarray]:
    """Parse a .safetensors file with numpy only (F32/F16/F64/BF16)."""
    raw = path.read_bytes()
    (header_len,) = struct.unpack("<Q", raw[:8])
    header = json.loads(raw[8 : 8 + header_len])
    base = 8 + header_len
    out: dict[str, np.ndarray] = {}
    for name, spec in header.items():
        if name == "__metadata__":
            continue
        start, end = spec["data_offsets"]
        buf = raw[base + start : base + end]
        dtype = spec["dtype"]
        if dtype == "BF16":
            u16 = np.frombuffer(buf, dtype=np.uint16).astype(np.uint32)
            arr = (u16 << 16).view(np.float32)
        elif dtype in _DTYPES:
            arr = np.frombuffer(buf, dtype=_DTYPES[dtype])
        else:
            msg = f"unsupported dtype {dtype!r} in {path}"
            raise ValueError(msg)
        out[name] = arr.reshape(spec["shape"]).astype(np.float64)
    return out


def adapter_scale(config_path: Path) -> float:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    r = int(cfg["r"])
    alpha = float(cfg["lora_alpha"])
    if cfg.get("use_rslora"):
        return alpha / float(np.sqrt(r))
    return alpha / r


def load_adapter(weights: Path) -> Adapter:
    scale = adapter_scale(weights.parent / "adapter_config.json")
    tensors = read_safetensors(weights)
    parts: dict[ModuleKey, dict[str, np.ndarray]] = {}
    for name, arr in tensors.items():
        m = _KEY_RE.search(name)
        if m is None:
            continue
        parent, mtype = m.group(2), m.group(3)
        if _PARENT.get(mtype) != parent:
            msg = f"unexpected module position {name!r} in {weights}"
            raise ValueError(msg)
        parts.setdefault((int(m.group(1)), mtype), {})[m.group(4)] = arr
    return {k: Module(a=v["A"], b=v["B"], scale=scale) for k, v in parts.items()}


# ---------------------------------------------------------------------- metrics


def raw_inner(x: Module, y: Module) -> float:
    return x.scale * y.scale * float(np.trace((x.b.T @ y.b) @ (y.a @ x.a.T)))


def gram_inner(x: Module, y: Module) -> float:
    bxy = x.b.T @ y.b  # r × r
    return (x.scale * y.scale) ** 2 * float(
        np.trace(bxy.T @ (x.a @ x.a.T) @ bxy @ (y.a @ y.a.T)),
    )


def _cosine(inner: float, nx: float, ny: float) -> float | None:
    if nx <= 0.0 or ny <= 0.0:
        return None  # UNDEFINED — never folded into a number
    return inner / float(np.sqrt(nx * ny))


def cos_gram(x: Module, y: Module) -> float | None:
    return _cosine(gram_inner(x, y), gram_inner(x, x), gram_inner(y, y))


def cos_raw(x: Module, y: Module) -> float | None:
    return _cosine(raw_inner(x, y), raw_inner(x, x), raw_inner(y, y))


def rho_raw(x: Module, y: Module) -> float | None:
    """‖ΔWx − ΔWy‖ / mean(‖ΔWx‖, ‖ΔWy‖) (descriptive only)."""
    nx, ny = raw_inner(x, x), raw_inner(y, y)
    mean = (np.sqrt(max(nx, 0.0)) + np.sqrt(max(ny, 0.0))) / 2.0
    if mean <= 0.0:
        return None
    diff2 = max(nx + ny - 2.0 * raw_inner(x, y), 0.0)
    return float(np.sqrt(diff2) / mean)


def rho_gram(x: Module, y: Module) -> float | None:
    """‖Gx − Gy‖_F / mean(‖Gx‖_F, ‖Gy‖_F) — unnormalised, so norm gaps count."""
    nx, ny = gram_inner(x, x), gram_inner(y, y)
    mean = (np.sqrt(max(nx, 0.0)) + np.sqrt(max(ny, 0.0))) / 2.0
    if nx <= 0.0 or ny <= 0.0:
        return None
    diff2 = max(nx + ny - 2.0 * gram_inner(x, y), 0.0)
    return float(np.sqrt(diff2) / mean)


def matched_cos_gram(x: Adapter, y: Adapter) -> dict[ModuleKey, float | None]:
    return {k: cos_gram(x[k], y[k]) for k in sorted(x.keys() & y.keys())}


def shift_null_cos_gram(x: Adapter, y: Adapter) -> list[float | None]:
    """N-shift: same module type, layer l of x vs layer l' != l of y."""
    keys = sorted(x.keys() & y.keys())
    return [
        cos_gram(x[kx], y[ky])
        for kx in keys
        for ky in keys
        if kx[1] == ky[1] and kx[0] != ky[0]
    ]


def median_or_none(values: list[float | None]) -> float | None:
    """Median over defined values; None if any value is UNDEFINED or empty."""
    if not values or any(v is None for v in values):
        return None
    return float(np.median(np.asarray(values, dtype=np.float64)))


def percentile_or_none(values: list[float | None], q: float) -> float | None:
    if not values or any(v is None for v in values):
        return None
    arr = np.asarray(values, dtype=np.float64)
    return float(np.percentile(arr, q, method="linear"))


# ---------------------------------------------------------------------- verdict


@dataclass(frozen=True)
class PairStat:
    median_cos_gram: float | None
    null_p99: float | None
    median_rho_gram: float | None = None


def h1_holds(pairs: list[PairStat]) -> bool:
    return bool(pairs) and all(
        p.median_cos_gram is not None
        and p.null_p99 is not None
        and p.median_cos_gram > p.null_p99
        for p in pairs
    )


def h2_holds(pairs: list[PairStat]) -> bool:
    return bool(pairs) and all(
        p.median_cos_gram is not None
        and p.median_cos_gram > H2_THRESHOLD
        and p.median_rho_gram is not None
        and p.median_rho_gram < H2_RHO_THRESHOLD
        for p in pairs
    )


def decide(*, g0: dict[str, bool], pairs: list[PairStat]) -> str:
    """Apply prereg §5.

    G0 fail → INVALID_SCORER; H1 ∧ H2 → PASS; H2 ∧ ¬H1 (the layer-shift
    null cannot discriminate) → INCONCLUSIVE_UNDERPOWERED; otherwise
    NO_GO_EFFECT_ABSENT.
    """
    if not g0 or not all(g0.values()):
        return VERDICT_INVALID
    h1, h2 = h1_holds(pairs), h2_holds(pairs)
    if h1 and h2:
        return VERDICT_PASS
    if h2:
        return VERDICT_UNDERPOWERED
    return VERDICT_ABSENT


# ------------------------------------------------------------------ diagnostics


def a_drift_stats(adapter: Adapter) -> dict[str, float]:
    """D0: deviation of A from kaiming-uniform init (bound 1/√d_in)."""
    row_ratio: list[float] = []
    over_bound: list[float] = []
    offdiag: list[float] = []
    for mod in adapter.values():
        d_in = mod.a.shape[1]
        bound = 1.0 / np.sqrt(d_in)
        expected_row = np.sqrt(d_in * bound**2 / 3.0)
        row_ratio.extend((np.linalg.norm(mod.a, axis=1) / expected_row).tolist())
        over_bound.append(float(np.mean(np.abs(mod.a) > bound)))
        aat = mod.a @ mod.a.T
        diag = np.abs(np.diag(aat))
        off = np.abs(aat - np.diag(np.diag(aat)))
        r = aat.shape[0]
        offdiag.append(float(off.sum() / (r * (r - 1)) / diag.mean()))
    return {
        "a_row_norm_ratio_median": float(np.median(row_ratio)),
        "a_frac_over_init_bound_median": float(np.median(over_bound)),
        "aat_offdiag_to_diag_median": float(np.median(offdiag)),
    }


def _r6(x: float | None) -> float | None:
    return None if x is None else round(float(x), 6)


def pair_report(x: Adapter, y: Adapter) -> dict[str, object]:
    matched = matched_cos_gram(x, y)
    null = shift_null_cos_gram(x, y)
    keys = sorted(matched)
    by_type: dict[str, float | None] = {}
    for t in MODULE_TYPES:
        vals = [matched[k] for k in keys if k[1] == t]
        if vals:
            by_type[t] = _r6(median_or_none(vals))
    raw = [cos_raw(x[k], y[k]) for k in keys]
    rho = [rho_raw(x[k], y[k]) for k in keys]
    rho_g = [rho_gram(x[k], y[k]) for k in keys]
    norms = [
        float(np.sqrt(max(raw_inner(ad[k], ad[k]), 0.0))) for ad in (x, y) for k in keys
    ]
    return {
        "n_modules": len(keys),
        "n_null": len(null),
        "median_cos_gram": _r6(median_or_none(list(matched.values()))),
        "median_rho_gram": _r6(median_or_none(rho_g)),
        "null_p99_cos_gram": _r6(percentile_or_none(null, NULL_PERCENTILE)),
        "null_median_cos_gram": _r6(median_or_none(null)),
        "median_cos_gram_by_type": by_type,
        "descriptive_median_cos_raw": _r6(median_or_none(raw)),
        "descriptive_median_rho_raw": _r6(median_or_none(rho)),
        "descriptive_min_delta_w_fro": _r6(min(norms) if norms else None),
        "descriptive_median_delta_w_fro": _r6(median_or_none(list(norms))),
    }


def _stat(rep: dict[str, object]) -> PairStat:
    m, p, g = rep["median_cos_gram"], rep["null_p99_cos_gram"], rep["median_rho_gram"]
    return PairStat(
        median_cos_gram=m if isinstance(m, float) else None,
        null_p99=p if isinstance(p, float) else None,
        median_rho_gram=g if isinstance(g, float) else None,
    )


def expected_keys(types: tuple[str, ...] = MODULE_TYPES) -> set[ModuleKey]:
    return {(layer, t) for layer in range(N_LAYERS) for t in types}


def config_signature(weights: Path) -> dict[str, object]:
    cfg = json.loads((weights.parent / "adapter_config.json").read_text("utf-8"))
    sig: dict[str, object] = {k: cfg.get(k) for k in _CONFIG_KEYS}
    sig["target_modules"] = sorted(cfg.get("target_modules") or [])
    return sig


def shapes_match(x: Adapter, y: Adapter) -> bool:
    return x.keys() == y.keys() and all(
        x[k].a.shape == y[k].a.shape and x[k].b.shape == y[k].b.shape for k in x
    )


# ------------------------------------------------------------------------- main


def run(repo: Path) -> dict[str, object]:
    prereg = repo / PREREG_REL
    inputs = {
        f"seed{s}": repo
        / LORA_ROOT
        / f"kant_constrained_mlp_gate_seed{s}_v1/adapter_model.safetensors"
        for s in SEEDS
    }
    inputs["positive_ckpt1000_seed42"] = (
        repo
        / LORA_ROOT
        / "kant_constrained_mlp_gate_seed42_v1"
        / "checkpoint-1000/adapter_model.safetensors"
    )
    inputs["negative_mock"] = (
        repo / "checkpoints/mock_kant_r8/adapter_model.safetensors"
    )

    g0: dict[str, bool] = {}
    missing = [k for k, p in inputs.items() if not p.is_file()]
    result: dict[str, object] = {
        "prereg_path": PREREG_REL,
        "prereg_sha256": sha256_file(prereg),
        "inputs": {
            k: {
                "path": p.relative_to(repo).as_posix(),
                "sha256": safe_sha256(p),
            }
            for k, p in inputs.items()
        },
    }
    if missing:
        g0["G0_a_inputs_and_shapes"] = False
        result["g0"] = g0
        result["missing_inputs"] = missing
        result["verdict"] = decide(g0=g0, pairs=[])
        return result

    try:
        adapters = {k: load_adapter(p) for k, p in inputs.items()}
        trained = [f"seed{s}" for s in SEEDS] + ["positive_ckpt1000_seed42"]
        sigs = [config_signature(inputs[k]) for k in trained]
    except (OSError, KeyError, ValueError, TypeError, struct.error) as exc:
        g0["G0_a_inputs_and_shapes"] = False
        result["g0"] = g0
        result["load_error"] = f"{type(exc).__name__}: {exc}"
        result["verdict"] = decide(g0=g0, pairs=[])
        return result
    seeds = [adapters[f"seed{s}"] for s in SEEDS]

    ref = seeds[0]
    g0["G0_a_inputs_and_shapes"] = (
        set(ref) == expected_keys()
        and all(shapes_match(adapters[k], ref) for k in trained)
        and all(sig == sigs[0] for sig in sigs)
        and sigs[0]["target_modules"] == sorted(MODULE_TYPES)
    )
    result["config_signature"] = sigs[0]
    if not g0["G0_a_inputs_and_shapes"]:
        # prereg §5: G0 fail → H1/H2 are not evaluated.
        result["g0"] = g0
        result["verdict"] = decide(g0=g0, pairs=[])
        return result

    self_cos = [c for ad in seeds for c in matched_cos_gram(ad, ad).values()]
    g0["G0_b_self_pair_is_one"] = all(
        c is not None and abs(c - 1.0) <= SELF_TOL for c in self_cos
    )

    mock = adapters["negative_mock"]
    mock_norms = [raw_inner(m, m) for m in mock.values()]
    mock_cos = [cos_gram(m, m) for m in mock.values()]
    g0["G0_c_mock_is_undefined"] = (
        set(mock) == expected_keys(MOCK_TYPES)
        and all(n == 0.0 for n in mock_norms)
        and all(c is None for c in mock_cos)
    )

    pos = pair_report(adapters["positive_ckpt1000_seed42"], adapters["seed42"])
    pos_stat = _stat(pos)
    g0["G0_d_positive_control_detects"] = (
        pos_stat.median_cos_gram is not None
        and pos_stat.null_p99 is not None
        and pos_stat.median_cos_gram > pos_stat.null_p99
    )

    pairs: dict[str, dict[str, object]] = {}
    stats: list[PairStat] = []
    for (i, a), (j, b) in combinations(list(zip(SEEDS, seeds, strict=True)), 2):
        rep = pair_report(a, b)
        pairs[f"{i}-{j}"] = rep
        stats.append(_stat(rep))

    result.update(
        {
            "g0": g0,
            "positive_control": pos,
            "pairs": pairs,
            "h1": h1_holds(stats),
            "h2": h2_holds(stats),
            "h2_threshold": H2_THRESHOLD,
            "h2_rho_threshold": H2_RHO_THRESHOLD,
            "null_percentile": NULL_PERCENTILE,
            "verdict": decide(g0=g0, pairs=stats),
            "descriptive_d0_a_drift": {
                f"seed{s}": {k: _r6(v) for k, v in a_drift_stats(ad).items()}
                for s, ad in zip(SEEDS, seeds, strict=True)
            },
        },
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    out = args.out or repo / EXP_REL / "results" / "results.json"
    result = run(repo)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = json.dumps({"verdict": result["verdict"], "out": str(out)})
    sys.stdout.write(summary + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

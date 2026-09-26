"""Tests for the individuation door condition-1 spike (synthetic matrices only).

The real LoRA adapters are gitignored (author machine only), so CI checks the
metric code on synthetic low-rank updates with known answers:

* positive control — shared B, independent random A: output-side Gram cosine
  is high while the raw ΔW cosine is near zero (the seed-gauge mechanism the
  prereg is built on);
* negative control — independent B and A: Gram cosine near the r/d baseline;
* ΔW ≡ 0 — cosine is UNDEFINED (None) and never folds into a number;
* the decision rule, including boundary and precedence cases.
"""

from __future__ import annotations

import json
import struct
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import individuation_wellposedness as mod

if TYPE_CHECKING:
    from pathlib import Path

R = 4
D_OUT = 64
D_IN = 256


def _rand_a(rng: np.random.Generator, d_in: int = D_IN) -> np.ndarray:
    bound = 1.0 / np.sqrt(d_in)
    return rng.uniform(-bound, bound, size=(R, d_in))


def _mod(b: np.ndarray, a: np.ndarray, scale: float = 2.0) -> mod.Module:
    return mod.Module(a=a, b=b, scale=scale)


def _dense(m: mod.Module) -> np.ndarray:
    return m.scale * m.b @ m.a


# ------------------------------------------------------------------ metrics


def test_inner_products_match_dense() -> None:
    rng = np.random.default_rng(0)
    x = _mod(rng.normal(size=(D_OUT, R)), _rand_a(rng))
    y = _mod(rng.normal(size=(D_OUT, R)), _rand_a(rng), scale=0.5)
    wx, wy = _dense(x), _dense(y)
    assert mod.raw_inner(x, y) == pytest.approx(float(np.sum(wx * wy)), rel=1e-9)
    gx, gy = wx @ wx.T, wy @ wy.T
    assert mod.gram_inner(x, y) == pytest.approx(float(np.sum(gx * gy)), rel=1e-9)


def test_shared_b_random_a_is_high_gram_low_raw() -> None:
    rng = np.random.default_rng(1)
    b = rng.normal(size=(D_OUT, R))
    x = _mod(b, _rand_a(rng, 4096))
    y = _mod(b, _rand_a(rng, 4096))
    cg, cr = mod.cos_gram(x, y), mod.cos_raw(x, y)
    assert cg is not None
    assert cr is not None
    assert cg > 0.9
    assert abs(cr) < 0.1


def test_independent_updates_are_near_baseline() -> None:
    rng = np.random.default_rng(2)
    vals = []
    for _ in range(20):
        x = _mod(rng.normal(size=(D_OUT, R)), _rand_a(rng))
        y = _mod(rng.normal(size=(D_OUT, R)), _rand_a(rng))
        c = mod.cos_gram(x, y)
        assert c is not None
        vals.append(c)
    # G ∝ rank-R PSD; independent → cos_G concentrates well below the 0.5 rule.
    assert float(np.median(vals)) < 0.3


def test_zero_update_is_undefined_not_a_number() -> None:
    rng = np.random.default_rng(3)
    zero = _mod(np.zeros((D_OUT, R)), _rand_a(rng))
    other = _mod(rng.normal(size=(D_OUT, R)), _rand_a(rng))
    assert mod.cos_gram(zero, zero) is None
    assert mod.cos_gram(zero, other) is None
    assert mod.cos_raw(zero, other) is None
    assert mod.rho_raw(zero, zero) is None
    assert mod.median_or_none([0.9, None]) is None
    assert mod.percentile_or_none([], 99.0) is None


def test_self_pair_is_one_and_scale_invariant() -> None:
    rng = np.random.default_rng(4)
    x = _mod(rng.normal(size=(D_OUT, R)), _rand_a(rng))
    x_scaled = _mod(x.b * 7.0, x.a, scale=x.scale)
    assert mod.cos_gram(x, x) == pytest.approx(1.0, abs=1e-12)
    assert mod.cos_gram(x, x_scaled) == pytest.approx(1.0, abs=1e-12)
    assert mod.rho_raw(x, x) == pytest.approx(0.0, abs=1e-6)


def test_shift_null_excludes_matched_layers() -> None:
    rng = np.random.default_rng(5)
    ad = {
        (layer, t): _mod(rng.normal(size=(D_OUT, R)), _rand_a(rng))
        for layer in range(3)
        for t in ("q_proj", "k_proj")
    }
    null = mod.shift_null_cos_gram(ad, ad)
    # 2 types × 3 layers × 2 other layers; self-pairs (=1.0) must not appear.
    assert len(null) == 12
    assert all(v is not None and v < 0.999 for v in null)


# ----------------------------------------------------------------- decision


def _g0(ok: bool = True) -> dict[str, bool]:  # noqa: FBT001, FBT002
    return {"a": True, "b": ok}


def _pairs(
    *meds: float | None,
    null: float = 0.1,
    rho: float | None = 0.5,
) -> list[mod.PairStat]:
    return [
        mod.PairStat(median_cos_gram=m, null_p99=null, median_rho_gram=rho)
        for m in meds
    ]


def test_decide_pass() -> None:
    assert mod.decide(g0=_g0(), pairs=_pairs(0.8, 0.7, 0.6)) == mod.VERDICT_PASS


def test_decide_h2_fail_one_pair() -> None:
    assert mod.decide(g0=_g0(), pairs=_pairs(0.8, 0.7, 0.4)) == mod.VERDICT_ABSENT


def test_decide_h2_boundary_is_strict() -> None:
    assert mod.decide(g0=_g0(), pairs=_pairs(0.8, 0.5, 0.9)) == mod.VERDICT_ABSENT


def test_decide_h2_without_h1_is_underpowered() -> None:
    pairs = _pairs(0.8, 0.7, 0.6, null=0.75)
    assert not mod.h1_holds(pairs)
    assert mod.h2_holds(pairs)
    assert mod.decide(g0=_g0(), pairs=pairs) == mod.VERDICT_UNDERPOWERED


def test_decide_h1_boundary_is_strict() -> None:
    pairs = _pairs(0.8, 0.7, 0.6, null=0.6)
    assert not mod.h1_holds(pairs)


def test_decide_rho_gram_gates_h2() -> None:
    assert mod.decide(g0=_g0(), pairs=_pairs(0.8, 0.7, 0.6, rho=1.0)) == (
        mod.VERDICT_ABSENT
    )
    assert mod.decide(g0=_g0(), pairs=_pairs(0.8, 0.7, 0.6, rho=None)) == (
        mod.VERDICT_ABSENT
    )


def test_rho_gram_sees_norm_gap_that_cosine_hides() -> None:
    rng = np.random.default_rng(6)
    x = _mod(rng.normal(size=(D_OUT, R)), _rand_a(rng))
    big = _mod(x.b * 3.0, x.a, scale=x.scale)
    assert mod.cos_gram(x, big) == pytest.approx(1.0, abs=1e-12)
    rho = mod.rho_gram(x, big)
    assert rho is not None
    assert rho > 1.0


def test_decide_undefined_median_is_not_pass() -> None:
    assert mod.decide(g0=_g0(), pairs=_pairs(0.8, None, 0.9)) == mod.VERDICT_ABSENT


def test_decide_g0_precedence() -> None:
    assert mod.decide(g0=_g0(ok=False), pairs=_pairs(0.9, 0.9, 0.9)) == (
        mod.VERDICT_INVALID
    )
    assert mod.decide(g0={}, pairs=_pairs(0.9, 0.9, 0.9)) == mod.VERDICT_INVALID


def test_decide_empty_pairs_is_not_pass() -> None:
    assert mod.decide(g0=_g0(), pairs=[]) == mod.VERDICT_ABSENT
    # Each hypothesis must refuse vacuous truth on its own (not only via decide).
    assert mod.h1_holds([]) is False
    assert mod.h2_holds([]) is False


# --------------------------------------------------------------- IO + run()


def _write_safetensors(path: Path, tensors: dict[str, np.ndarray], dtype: str) -> None:
    header: dict[str, object] = {}
    blobs: list[bytes] = []
    offset = 0
    for name, arr in tensors.items():
        if dtype == "BF16":
            u32 = np.ascontiguousarray(arr, dtype=np.float32).view(np.uint32)
            blob = (u32 >> 16).astype(np.uint16).tobytes()
        else:
            blob = np.ascontiguousarray(arr, dtype=np.float32).tobytes()
        header[name] = {
            "dtype": dtype,
            "shape": list(arr.shape),
            "data_offsets": [offset, offset + len(blob)],
        }
        blobs.append(blob)
        offset += len(blob)
    hdr = json.dumps(header).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<Q", len(hdr)) + hdr + b"".join(blobs))
    (path.parent / "adapter_config.json").write_text(
        json.dumps(
            {
                "r": R,
                "lora_alpha": 2 * R,
                "use_rslora": False,
                "rank_pattern": {},
                "alpha_pattern": {},
                "target_modules": list(reversed(mod.MODULE_TYPES)),
            },
        ),
        encoding="utf-8",
    )


def _key(layer: int, t: str, ab: str) -> str:
    part = "mlp" if t == "gate_proj" else "self_attn"
    return f"base_model.model.model.layers.{layer}.{part}.{t}.lora_{ab}.weight"


def _fake_adapter(
    rng: np.random.Generator,
    bs: dict[tuple[int, str], np.ndarray],
    *,
    zero_b: bool = False,
) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for (layer, t), b in bs.items():
        out[_key(layer, t, "A")] = _rand_a(rng).astype(np.float32)
        out[_key(layer, t, "B")] = (np.zeros_like(b) if zero_b else b).astype(
            np.float32,
        )
    return out


def _fake_repo(tmp_path: Path, *, shared: bool, n_layers: int = 36) -> Path:
    rng = np.random.default_rng(10)
    keys = [(layer, t) for layer in range(n_layers) for t in mod.MODULE_TYPES]

    def fresh_bs() -> dict[tuple[int, str], np.ndarray]:
        return {k: rng.normal(size=(D_OUT, R)) for k in keys}

    common = fresh_bs()
    root = tmp_path / mod.LORA_ROOT
    for s in mod.SEEDS:
        bs = common if shared else fresh_bs()
        noisy = {k: v + 0.1 * rng.normal(size=v.shape) for k, v in bs.items()}
        _write_safetensors(
            root / f"kant_constrained_mlp_gate_seed{s}_v1/adapter_model.safetensors",
            _fake_adapter(rng, noisy),
            "BF16",
        )
    # Positive control must share A with the seed-42 final adapter to mirror a
    # training trajectory; reuse the seed-42 tensors with a perturbed B.
    final42 = mod.read_safetensors(
        root / "kant_constrained_mlp_gate_seed42_v1/adapter_model.safetensors",
    )
    ckpt = {
        k: (v + 0.05 * rng.normal(size=v.shape) if "lora_B" in k else v)
        for k, v in final42.items()
    }
    _write_safetensors(
        root
        / "kant_constrained_mlp_gate_seed42_v1"
        / "checkpoint-1000/adapter_model.safetensors",
        ckpt,
        "F32",
    )
    mock_bs = {
        (layer, t): np.zeros((D_OUT, R)) for layer in range(36) for t in mod.MOCK_TYPES
    }
    _write_safetensors(
        tmp_path / "checkpoints/mock_kant_r8/adapter_model.safetensors",
        _fake_adapter(rng, mock_bs, zero_b=True),
        "F32",
    )
    prereg = tmp_path / mod.PREREG_REL
    prereg.parent.mkdir(parents=True, exist_ok=True)
    prereg.write_text("prereg v1\n", encoding="utf-8")
    return tmp_path


def test_bf16_roundtrip(tmp_path: Path) -> None:
    arr = np.array([[1.0, -2.5], [0.15625, 3.0]], dtype=np.float32)
    p = tmp_path / "x/adapter_model.safetensors"
    _write_safetensors(p, {"t": arr}, "BF16")
    got = mod.read_safetensors(p)["t"]
    np.testing.assert_allclose(got, arr, rtol=1e-2)


def test_run_shared_structure_passes(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, shared=True)
    res = mod.run(repo)
    assert all(res["g0"].values()), res["g0"]
    assert res["verdict"] == mod.VERDICT_PASS


def test_run_independent_seeds_are_absent(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, shared=False)
    res = mod.run(repo)
    assert all(res["g0"].values()), res["g0"]
    assert res["h1"] is False
    assert res["verdict"] == mod.VERDICT_ABSENT


def test_run_missing_input_is_invalid(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, shared=True)
    (repo / "checkpoints/mock_kant_r8/adapter_model.safetensors").unlink()
    res = mod.run(repo)
    assert res["verdict"] == mod.VERDICT_INVALID


def test_run_nonzero_mock_is_invalid(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, shared=True)
    rng = np.random.default_rng(99)
    _write_safetensors(
        repo / "checkpoints/mock_kant_r8/adapter_model.safetensors",
        _fake_adapter(rng, {(0, "q_proj"): rng.normal(size=(D_OUT, R))}),
        "F32",
    )
    res = mod.run(repo)
    assert res["g0"]["G0_c_mock_is_undefined"] is False
    assert res["verdict"] == mod.VERDICT_INVALID


def test_run_config_mismatch_is_invalid(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, shared=True)
    cfg_path = (
        repo / mod.LORA_ROOT / "kant_constrained_mlp_gate_seed43_v1/adapter_config.json"
    )
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["lora_alpha"] = 99
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    res = mod.run(repo)
    assert res["g0"]["G0_a_inputs_and_shapes"] is False
    assert res["verdict"] == mod.VERDICT_INVALID


def test_run_malformed_adapter_is_invalid_not_crash(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, shared=True)
    rng = np.random.default_rng(7)
    only_a = {_key(0, "q_proj", "A"): _rand_a(rng).astype(np.float32)}
    _write_safetensors(
        repo
        / mod.LORA_ROOT
        / "kant_constrained_mlp_gate_seed44_v1/adapter_model.safetensors",
        only_a,
        "F32",
    )
    res = mod.run(repo)
    assert "load_error" in res
    assert res["verdict"] == mod.VERDICT_INVALID


def test_run_consistently_missing_layer_is_invalid(tmp_path: Path) -> None:
    # Every trained adapter lacks layer 35: seeds agree with each other, but the
    # module set is not the prereg's 36 × 5, so G0-a must fail.
    repo = _fake_repo(tmp_path, shared=True, n_layers=35)
    res = mod.run(repo)
    assert res["g0"]["G0_a_inputs_and_shapes"] is False
    assert res["verdict"] == mod.VERDICT_INVALID


def test_run_subset_mock_is_invalid(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, shared=True)
    rng = np.random.default_rng(11)
    _write_safetensors(
        repo / "checkpoints/mock_kant_r8/adapter_model.safetensors",
        _fake_adapter(rng, {(0, "q_proj"): np.zeros((D_OUT, R))}, zero_b=True),
        "F32",
    )
    res = mod.run(repo)
    assert res["g0"]["G0_c_mock_is_undefined"] is False
    assert res["verdict"] == mod.VERDICT_INVALID


def test_run_truncated_file_is_invalid_not_crash(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, shared=True)
    target = (
        repo
        / mod.LORA_ROOT
        / "kant_constrained_mlp_gate_seed43_v1/adapter_model.safetensors"
    )
    target.write_bytes(b"")
    res = mod.run(repo)
    assert "load_error" in res
    assert res["verdict"] == mod.VERDICT_INVALID


def test_run_wrong_parent_module_is_invalid(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, shared=True)
    path = (
        repo
        / mod.LORA_ROOT
        / "kant_constrained_mlp_gate_seed44_v1/adapter_model.safetensors"
    )
    tensors = mod.read_safetensors(path)
    moved = {
        k.replace("self_attn.q_proj", "mlp.q_proj") if ".layers.0." in k else k: v
        for k, v in tensors.items()
    }
    _write_safetensors(path, moved, "F32")
    res = mod.run(repo)
    assert res["verdict"] == mod.VERDICT_INVALID


def test_run_g0a_fail_short_circuits(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, shared=True, n_layers=35)
    res = mod.run(repo)
    assert "pairs" not in res
    assert "h1" not in res


def test_run_observes_prereg_hash(tmp_path: Path) -> None:
    repo = _fake_repo(tmp_path, shared=True)
    before = mod.run(repo)["prereg_sha256"]
    (repo / mod.PREREG_REL).write_text("prereg v2\n", encoding="utf-8")
    after = mod.run(repo)["prereg_sha256"]
    assert before != after
    assert after == mod.sha256_file(repo / mod.PREREG_REL)

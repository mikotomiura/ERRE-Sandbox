"""Tests for the Ocsai adapter in scripts/paper01_external_audit.py (Loop I-006).

design-final.md §3 / §4 / §7 is the single source of truth for the
procedures under test. Per the issue's Test Plan:

* The adapter is unit-tested with **synthetic jsonl** / hand-built
  :class:`~scripts.paper01_external_audit.CambridgeRow` sequences and a
  tiny deterministic *stub* embedding closure (pure numpy/hash, no ML
  model) -- never ``sentence_transformers``. CI runs with no ``[eval]``
  extras.
* The real-jsonl end-to-end path is ``@pytest.mark.eval`` +
  ``pytest.importorskip("sentence_transformers")``.
* 006-5 / 006-9 are pushed through ``run_ocsai_split`` (the real
  production orchestration), never asserted against a hand-built
  dataclass's own fields.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import paper01_external_audit as mod

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# =============================================================================
# shared synthetic-jsonl helpers (006-1 / 006-2 / 006-3)
# =============================================================================


def _ocsai_line(obj: str, response: str, score: int) -> str:
    prompt = f"AUT Prompt:{obj}\nResponse:{response}\nScore:\n"
    return json.dumps({"prompt": prompt, "completion": str(score)})


def _ocsai_bytes(records: Sequence[tuple[str, str, int]]) -> bytes:
    return ("\n".join(_ocsai_line(o, r, s) for o, r, s in records) + "\n").encode(
        "utf-8"
    )


# =============================================================================
# shared synthetic-row / stub-encoder helpers (006-4..9), mirroring
# test_external_audit.py's own synthetic_cambridge fixture style
# =============================================================================

_FAKE_ENCODER_DIM = 16
_FAKE_ENCODER_HALF = _FAKE_ENCODER_DIM // 2


def _fake_encoder(texts: Sequence[str]) -> np.ndarray:
    """Deterministic 16-dim stub embedding (pure numpy/hash, no ML model).

    A "good" text's vector lives entirely in the first half of the
    dimensions, a "common" text's entirely in the second half -- clean
    cross-class discrimination for ``auc_stratified``. Within a class, each
    distinct text gets an independent hash-seeded random direction, so a
    class's items stay distinct after greedy dedupe.
    """
    out = np.zeros((len(texts), _FAKE_ENCODER_DIM), dtype=float)
    for i, t in enumerate(texts):
        rng = np.random.default_rng(abs(hash(t)) % (2**32))
        vec = rng.normal(size=_FAKE_ENCODER_HALF)
        vec = vec / np.linalg.norm(vec)
        if "good" in t:
            out[i, :_FAKE_ENCODER_HALF] = vec
        else:
            out[i, _FAKE_ENCODER_HALF:] = vec
    return out


def _synthetic_rows(
    object_key: str,
    *,
    n_good: int,
    n_common: int,
    id_offset: int = 0,
    text_prefix: str | None = None,
) -> tuple[mod.CambridgeRow, ...]:
    """Interleaved ids so both classes land in both SPLIT-BLOCK halves.

    ``text_prefix`` (default: ``object_key``) lets two corpora share the
    same ``.object`` key (required for scoring alignment) while producing
    *literally distinct* text strings -- needed wherever a test must tell
    "Cambridge's own paperclip texts" apart from "Ocsai's own paperclip
    texts" (AC 006-8).
    """
    prefix = object_key if text_prefix is None else text_prefix
    rows: list[mod.CambridgeRow] = []
    row_id = id_offset
    gi = ci = 0
    total = n_good + n_common
    for k in range(total):
        take_good = gi < n_good and (k % 2 == 0 or ci >= n_common)
        if take_good:
            rows.append(
                mod.CambridgeRow(
                    row_id=row_id,
                    object=object_key,
                    text=f"{prefix} good idea {gi}",
                    category="good",
                )
            )
            gi += 1
        else:
            rows.append(
                mod.CambridgeRow(
                    row_id=row_id,
                    object=object_key,
                    text=f"{prefix} common idea {ci}",
                    category="common_use_only",
                )
            )
            ci += 1
        row_id += 1
    return tuple(rows)


def _rows_common_then_good(
    object_key: str, *, n_common: int, n_good: int, id_offset: int = 0
) -> tuple[mod.CambridgeRow, ...]:
    """All common items at the low row_ids, good items at the high row_ids --
    guarantees the good items land in SPLIT-BLOCK's split1 (second half),
    unlike :func:`_synthetic_rows`'s interleave which biases a small
    ``n_good`` toward split0. Used for the exact gold-class-gate boundary
    (AC 006-7): a single good item that must survive in the *scored* pool.
    """
    rows: list[mod.CambridgeRow] = []
    row_id = id_offset
    for i in range(n_common):
        rows.append(
            mod.CambridgeRow(
                row_id=row_id,
                object=object_key,
                text=f"{object_key} common idea {i}",
                category="common_use_only",
            )
        )
        row_id += 1
    for i in range(n_good):
        rows.append(
            mod.CambridgeRow(
                row_id=row_id,
                object=object_key,
                text=f"{object_key} good idea {i}",
                category="good",
            )
        )
        row_id += 1
    return tuple(rows)


def _vmaps_for(
    *row_groups: Sequence[mod.CambridgeRow],
) -> dict[str, dict[str, np.ndarray]]:
    all_texts = sorted({r.text for rows in row_groups for r in rows})
    vmap = dict(zip(all_texts, _fake_encoder(all_texts), strict=True))
    return dict.fromkeys(
        ("mpnet", "MiniLM-L6-v2", "e5-small-v2", "bge-small-en-v1.5"), vmap
    )


def _fixed_bootstrap(ci_lower: float, ci_upper: float):
    def _fake(
        *,
        scores_full: Sequence[float],
        scores_lao: Sequence[float],
        labels: Sequence[int],
        objects: Sequence[str],
        seed: int,
    ) -> mod.BootstrapDropResult:
        del scores_full, scores_lao, labels, objects, seed
        return mod.BootstrapDropResult(
            auc_full_ci=(0.0, 1.0),
            auc_lao_ci=(ci_lower, ci_upper),
            drop_ci=(0.0, 0.0),
            p_drop_le_zero=0.5,
        )

    return _fake


def _fake_permutation(
    scores: Sequence[float], labels: Sequence[int], objects: Sequence[str], *, seed: int
) -> float:
    del scores, labels, objects, seed
    return 0.5


# =============================================================================
# 006-1: fixed train -> val -> test concatenation order
# =============================================================================


def test_ocsai_concat_order_is_fixed(monkeypatch: pytest.MonkeyPatch) -> None:
    """train -> val -> test concatenation is fixed and deterministic; the
    resulting 0-origin row_index reflects that order. Reversing
    OCSAI_CONCAT_ORDER changes which records land at which index (kills a
    mutant that swaps the concatenation order -- mutation target 1).
    """
    splits_data = {
        "train": _ocsai_bytes([("brick", f"train idea {i}", 10) for i in range(3)]),
        "val": _ocsai_bytes([("brick", f"val idea {i}", 10) for i in range(2)]),
        "test": _ocsai_bytes([("brick", f"test idea {i}", 10) for i in range(4)]),
    }

    records_1 = mod.parse_ocsai_records(splits_data)
    records_2 = mod.parse_ocsai_records(splits_data)
    assert records_1 == records_2  # deterministic

    assert [r[0] for r in records_1] == list(range(9))
    assert [r[2] for r in records_1[:3]] == [f"train idea {i}" for i in range(3)]
    assert [r[2] for r in records_1[3:5]] == [f"val idea {i}" for i in range(2)]
    assert [r[2] for r in records_1[5:9]] == [f"test idea {i}" for i in range(4)]

    monkeypatch.setattr(mod, "OCSAI_CONCAT_ORDER", ("test", "val", "train"))
    reversed_records = mod.parse_ocsai_records(splits_data)
    assert [r[2] for r in reversed_records[:4]] == [f"test idea {i}" for i in range(4)]
    assert reversed_records != records_1


# =============================================================================
# 006-2: prompt parsing separates object / response correctly
# =============================================================================


def test_ocsai_prompt_parsing() -> None:
    splits_data = {
        "train": _ocsai_bytes(
            [
                ("paperclip", "hold papers together", 25),  # excluded band
                ("paperclip", "make a wire sculpture", 45),  # good
            ]
        ),
        "val": b"",
        "test": b"",
    }
    rows = mod.load_ocsai_rows(splits_data)
    assert len(rows) == 1
    row = rows[0]
    assert row.object == "paperclip"
    assert row.text == "make a wire sculpture"
    assert row.category == "good"


# =============================================================================
# 006-3: binarisation bands, boundary-exact (10 / 11 / 39 / 40)
# =============================================================================


def test_ocsai_binarisation_bands() -> None:
    records = [
        ("brick", "resp 9", 9),
        ("brick", "resp 10", 10),
        ("brick", "resp 11", 11),
        ("brick", "resp 39", 39),
        ("brick", "resp 40", 40),
    ]
    splits_data = {"train": _ocsai_bytes(records), "val": b"", "test": b""}
    rows = mod.load_ocsai_rows(splits_data)
    by_text = {r.text: r.category for r in rows}

    # below the 10-50 pre-registered scale: never real data, but must not be
    # silently absorbed into "common" by a <= 10 boundary mutant.
    assert "resp 9" not in by_text
    assert by_text["resp 10"] == "common_use_only"
    assert "resp 11" not in by_text
    assert "resp 39" not in by_text
    assert by_text["resp 40"] == "good"


# =============================================================================
# 006-4: ARM-C A2 missing-support is recorded, boundary-exact
# =============================================================================


def test_arm_c_missing_support_is_recorded() -> None:
    def _vec(seed: int, dim: int = 16) -> np.ndarray:
        rng = np.random.default_rng(seed)
        v = rng.normal(size=dim)
        return v / np.linalg.norm(v)

    # "brick": 20 rows, all common, every text distinct (support == 1 each)
    # -> split0 (first 10 by row_id) has no text repeated >= 2 times -> A2 empty
    brick_rows: list[mod.CambridgeRow] = []
    vmap: dict[str, np.ndarray] = {}
    for i in range(20):
        text = f"brick idea {i}"
        vmap[text] = _vec(i)
        brick_rows.append(
            mod.CambridgeRow(
                row_id=i, object="brick", text=text, category="common_use_only"
            )
        )
    brick_ctx = mod.build_object_split_context(
        "brick", tuple(brick_rows), "SPLIT-BLOCK", vmap
    )
    assert mod.ocsai_high_frequency_texts(brick_ctx.split0) == ()
    texts_a, missing_a = mod.arm_c_texts(brick_ctx, vmap)
    assert missing_a is True
    # falls back to A1 (the dedup'd common pool) alone
    assert set(texts_a) == {r.text for r in brick_ctx.dedup_common_pool}

    # "paperclip": row_id 0 and 1 share a normalised text (support == 2,
    # the exact EXT_A2_MIN_SUPPORT boundary) and both land in split0 (first
    # half of 20 rows) -> A2 non-empty
    paperclip_rows: list[mod.CambridgeRow] = []
    dup_text = "paperclip idea 0"
    for i in range(20):
        text = dup_text if i in (0, 1) else f"paperclip idea {i}"
        vmap[text] = _vec(100 + i)
        paperclip_rows.append(
            mod.CambridgeRow(
                row_id=i, object="paperclip", text=text, category="common_use_only"
            )
        )
    paperclip_ctx = mod.build_object_split_context(
        "paperclip", tuple(paperclip_rows), "SPLIT-BLOCK", vmap
    )
    a2 = mod.ocsai_high_frequency_texts(paperclip_ctx.split0)
    assert dup_text in a2
    texts_b, missing_b = mod.arm_c_texts(paperclip_ctx, vmap)
    assert missing_b is False
    assert dup_text in texts_b

    # exact boundary: support of 1 does not count (kills a >= 1 / > 2 mutant)
    assert (
        mod.ocsai_high_frequency_texts(paperclip_ctx.split0, min_support=3) == ()
    )  # no text repeats 3x
    assert dup_text in mod.ocsai_high_frequency_texts(
        paperclip_ctx.split0, min_support=2
    )


# =============================================================================
# TASK-POST HIGH-1: ARM-C's report now shares the five-tuple + auc_full/lao/
# potency the Cambridge-side arms already get via _single_draw_report_map
# =============================================================================


def test_arm_c_report_includes_five_tuple_and_auc_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ARM-C used to build its own inline ``dataclasses.asdict(aggregate_
    candidate_draws(...))`` dict (only the §5.1 aggregate survived); it now
    goes through the same :func:`_single_draw_candidate_report` shared with
    ARM-B/D/X/NC-1/NC-2, so the same fields must be present here too."""
    monkeypatch.setattr(mod, "ANCHOR_DRAWS", 4)
    monkeypatch.setattr(mod, "bootstrap_stratified_drop", _fixed_bootstrap(0.85, 0.95))
    monkeypatch.setattr(mod, "permutation_p_stratified", _fake_permutation)

    rows = _rows_common_then_good("brick", n_common=20, n_good=20)
    rows_by_object = {"brick": rows}
    vmaps = _vmaps_for(rows)

    result = mod.run_ocsai_split(
        rows_by_object, "SPLIT-BLOCK", vmaps, objects=("brick",)
    )

    arm_c_candidates = result["arm_c"]["candidates"]
    assert set(arm_c_candidates) >= set(mod.EMBEDDING_FAMILY_EXT)
    for key in mod.EMBEDDING_FAMILY_EXT:
        entry = arm_c_candidates[key]
        for field in (
            "auc_full",
            "auc_lao",
            "potency",
            "near_dup_good",
            "near_dup_common",
            "auc_membership",
            "dropped_anchor_fraction",
        ):
            assert field in entry
        # never the NC-2-only reversal marker
        assert "direction_reversed" not in entry


# =============================================================================
# 006-5: verdict comes from ARM-A only (ARM-B/C/D never move it)
# =============================================================================


def test_verdict_comes_from_arm_a_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "ANCHOR_DRAWS", 4)
    monkeypatch.setattr(mod, "bootstrap_stratified_drop", _fixed_bootstrap(0.85, 0.95))
    monkeypatch.setattr(mod, "permutation_p_stratified", _fake_permutation)

    rows = _synthetic_rows("brick", n_good=20, n_common=20)
    rows_by_object = {"brick": rows}
    vmaps = _vmaps_for(rows)

    baseline = mod.run_ocsai_split(
        rows_by_object, "SPLIT-BLOCK", vmaps, objects=("brick",)
    )

    # absolute oracle (not just baseline-vs-degraded relative equality):
    # run_ocsai_split's verdict must be *exactly* what the untouched
    # run_cambridge_split call inside it produces -- nothing computed after
    # that call (ARM-C included) may ever overwrite it. A mutation that
    # unconditionally forces some verdict onto both the baseline and the
    # degraded call below would slip past a baseline-vs-degraded-only check
    # (both sides would agree on the same wrong constant); comparing against
    # this independent oracle call catches it.
    reference = mod.run_cambridge_split(
        rows_by_object, "SPLIT-BLOCK", vmaps, corpus="ocsai", objects=("brick",)
    )
    assert baseline["verdict"] == reference["verdict"]
    assert baseline["candidates"] == reference["candidates"]

    monkeypatch.setattr(mod, "arm_b_texts", lambda ctx: ())  # noqa: ARG005
    monkeypatch.setattr(mod, "arm_d_texts", lambda ctx, mpnet_vmap: ())  # noqa: ARG005
    monkeypatch.setattr(mod, "arm_c_texts", lambda ctx, mpnet_vmap, **kw: ((), True))  # noqa: ARG005
    degraded = mod.run_ocsai_split(
        rows_by_object, "SPLIT-BLOCK", vmaps, objects=("brick",)
    )

    assert degraded["verdict"] == baseline["verdict"]
    assert degraded["verdict"] == reference["verdict"]
    assert degraded["candidates"] == baseline["candidates"]
    assert degraded["sensitivity"] != baseline["sensitivity"]
    assert degraded["arm_c"] != baseline["arm_c"]


# =============================================================================
# 006-6: source_unavailable does not block Cambridge's verdict
# =============================================================================


def test_partial_corpus_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ocsai unreachable -> {"status": "source_unavailable"}, never a
    VERDICT_ENUM member, and it never blocks the (independently computed)
    Cambridge verdict inside run_external_audit."""
    monkeypatch.setattr(mod, "load_ocsai_raw_bytes", lambda: None)

    ocsai_result = mod.run_ocsai_audit()
    assert ocsai_result == {"corpus": "ocsai", "status": "source_unavailable"}
    assert ocsai_result["status"] not in mod.VERDICT_ENUM

    monkeypatch.setattr(
        mod, "load_cambridge_raw_bytes", lambda: {"bowl": b"", "paperclip": b""}
    )
    monkeypatch.setattr(mod, "load_cambridge_rows", lambda obj, data: ())  # noqa: ARG005
    fake_cambridge = {
        "corpus": "cambridge",
        "splits": {"SPLIT-BLOCK": {"verdict": {"verdict": "PASS"}}},
    }
    monkeypatch.setattr(mod, "run_cambridge_audit", lambda raw=None: fake_cambridge)  # noqa: ARG005

    combined = mod.run_external_audit()
    assert combined["cambridge"] == fake_cambridge
    assert combined["ocsai"]["status"] == "source_unavailable"


# =============================================================================
# 006-7: dropped objects (both gates: pool-size and gold-class) are surfaced
# =============================================================================


def test_dropped_objects_are_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "ANCHOR_DRAWS", 4)
    monkeypatch.setattr(mod, "bootstrap_stratified_drop", _fixed_bootstrap(0.85, 0.95))
    monkeypatch.setattr(mod, "permutation_p_stratified", _fake_permutation)

    healthy = _synthetic_rows("healthy", n_good=20, n_common=20, id_offset=0)
    toosmall = _synthetic_rows("toosmall", n_good=2, n_common=2, id_offset=1000)
    goldpoor = _synthetic_rows("goldpoor", n_good=0, n_common=40, id_offset=2000)
    # boundary: exactly 1 good item, placed at the high row_ids so it lands
    # in split1 (the scored pool) -- the minimum that must survive the gate
    boundarygood = _rows_common_then_good(
        "boundarygood", n_common=39, n_good=1, id_offset=3000
    )
    # the other half of the gold-class conjunction: split1 has good items
    # but zero common items (all common rows are confined to split0, where
    # the pool-size gate is satisfied on its own -- so only the gold-class
    # gate's `n_common >= 1` half can be responsible for dropping this one)
    commonpoor = _rows_common_then_good(
        "commonpoor", n_common=20, n_good=20, id_offset=4000
    )

    rows_by_object = {
        "healthy": healthy,
        "toosmall": toosmall,
        "goldpoor": goldpoor,
        "boundarygood": boundarygood,
        "commonpoor": commonpoor,
    }
    objects = tuple(rows_by_object)
    vmaps = _vmaps_for(healthy, toosmall, goldpoor, boundarygood, commonpoor)

    result = mod.run_ocsai_split(rows_by_object, "SPLIT-BLOCK", vmaps, objects=objects)

    assert set(result["dropped_objects"]) == {"toosmall", "goldpoor", "commonpoor"}
    assert result["dropped_object_count"] == 3
    assert set(result["active_objects"]) == {"healthy", "boundarygood"}
    # "toosmall" is dropped by the pool-size gate, before the gold-class
    # gate is even evaluated -- it must not double up in this list.
    assert set(result["gold_class_deficient_objects"]) == {"goldpoor", "commonpoor"}


# =============================================================================
# 006-8: ARM-X is genuinely source-crossed (Cambridge anchor x Ocsai gold)
# =============================================================================


def test_arm_x_is_source_crossed(monkeypatch: pytest.MonkeyPatch) -> None:
    cambridge_rows = _synthetic_rows(
        "paperclip",
        n_good=10,
        n_common=20,
        id_offset=0,
        text_prefix="cambridge paperclip",
    )
    ocsai_rows = _synthetic_rows(
        "paperclip",
        n_good=10,
        n_common=20,
        id_offset=1000,
        text_prefix="ocsai paperclip",
    )
    vmaps = _vmaps_for(cambridge_rows, ocsai_rows)
    vmap = vmaps["mpnet"]

    ocsai_ctx = mod.build_object_split_context(
        "paperclip", ocsai_rows, "SPLIT-BLOCK", vmap
    )

    # Spy on build_object_split_context to capture exactly which rows feed
    # the anchor-pool construction inside arm_x_scored_candidates. This is
    # AUC-independent (unlike comparing the returned aggregate dicts: this
    # stub encoder gives good/common items clean half-space separation, so
    # X0's *ranking* -- and therefore any AUC-derived aggregate -- can
    # coincidentally come out identical regardless of which anchor set was
    # used; only the raw call arguments prove the source, unambiguously).
    captured_rows: list[tuple[mod.CambridgeRow, ...]] = []
    real_build_ctx = mod.build_object_split_context

    def _spy(
        object_key: str,
        rows: Sequence[mod.CambridgeRow],
        scheme: str,
        mpnet_vmap: Mapping[str, np.ndarray],
    ) -> mod.ObjectSplitContext:
        captured_rows.append(tuple(rows))
        return real_build_ctx(object_key, rows, scheme, mpnet_vmap)

    monkeypatch.setattr(mod, "build_object_split_context", _spy)

    result = mod.arm_x_scored_candidates(
        cambridge_rows, ocsai_ctx, "SPLIT-BLOCK", vmaps
    )
    assert set(result) >= set(mod.EMBEDDING_FAMILY_EXT)
    for key in mod.EMBEDDING_FAMILY_EXT:
        assert "median_drop" in result[key]
        # TASK-POST HIGH-1: ARM-X now shares _single_draw_candidate_report
        # with every other single-draw arm, so it carries the same fields.
        for field in (
            "auc_full",
            "auc_lao",
            "potency",
            "near_dup_good",
            "near_dup_common",
            "auc_membership",
            "dropped_anchor_fraction",
        ):
            assert field in result[key]

    # mutation target 4: the anchor-construction call must have used exactly
    # cambridge_rows -- never ocsai_rows, and never a bypass that skips the
    # call altogether (a mutant that aliases the anchor ctx straight to
    # ocsai_paperclip_ctx never calls build_object_split_context for the
    # anchor at all, so captured_rows stays empty -- also a failure here).
    assert captured_rows == [cambridge_rows]
    assert captured_rows[0] != ocsai_rows


# =============================================================================
# 006-9: ARM-X never drives the verdict
# =============================================================================


def test_arm_x_does_not_drive_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "ANCHOR_DRAWS", 4)
    monkeypatch.setattr(mod, "bootstrap_stratified_drop", _fixed_bootstrap(0.85, 0.95))
    monkeypatch.setattr(mod, "permutation_p_stratified", _fake_permutation)

    ocsai_rows = _synthetic_rows("paperclip", n_good=20, n_common=20, id_offset=0)
    cambridge_rows = _synthetic_rows(
        "paperclip", n_good=10, n_common=20, id_offset=1000
    )
    rows_by_object = {"paperclip": ocsai_rows}
    vmaps = _vmaps_for(ocsai_rows, cambridge_rows)

    baseline = mod.run_ocsai_split(
        rows_by_object,
        "SPLIT-BLOCK",
        vmaps,
        objects=("paperclip",),
        cambridge_paperclip_rows=cambridge_rows,
        arm_x_vmaps=vmaps,
    )
    assert baseline["arm_x"] != {}

    degraded = mod.run_ocsai_split(
        rows_by_object,
        "SPLIT-BLOCK",
        vmaps,
        objects=("paperclip",),
        cambridge_paperclip_rows=(),
        arm_x_vmaps=None,
    )
    assert degraded["arm_x"] == {}
    assert degraded["verdict"] == baseline["verdict"]
    assert degraded["candidates"] == baseline["candidates"]


# =============================================================================
# real jsonl end-to-end (eval marker, extras-only, network-only)
# =============================================================================


@pytest.mark.eval
def test_ocsai_end_to_end_real_jsonl(monkeypatch: pytest.MonkeyPatch) -> None:
    """A small (small-ANCHOR_DRAWS) real Ocsai jsonl -> verdict smoke test.

    Skips when ``[eval]`` extras (``sentence_transformers``) are
    unavailable, or when Ocsai itself is unreachable from this
    environment. Wires in the real Cambridge paperclip pool for ARM-X when
    the raw ``.xlsx`` files are present locally (I-001 fetch).
    """
    pytest.importorskip("sentence_transformers")
    monkeypatch.setattr(mod, "ANCHOR_DRAWS", 2)

    cambridge_rows_by_object = None
    bowl_path = mod.CAMBRIDGE_RAW_DIR / "bowl AUT dataset.xlsx"
    paperclip_path = mod.CAMBRIDGE_RAW_DIR / "paperclip AUT dataset.xlsx"
    if bowl_path.exists() and paperclip_path.exists():
        raw = {
            "bowl": bowl_path.read_bytes(),
            "paperclip": paperclip_path.read_bytes(),
        }
        cambridge_rows_by_object = {
            obj: mod.load_cambridge_rows(obj, data) for obj, data in raw.items()
        }

    result = mod.run_ocsai_audit(cambridge_rows_by_object)
    if result.get("status") == "source_unavailable":
        pytest.skip("Ocsai source unreachable in this environment")

    assert result["corpus"] == "ocsai"
    for scheme_key in ("SPLIT-BLOCK", "SPLIT-PARITY"):
        assert scheme_key in result["splits"]
        assert result["splits"][scheme_key]["verdict"]["verdict"] in mod.VERDICT_ENUM
        assert "arm_c" in result["splits"][scheme_key]
        assert "arm_x" in result["splits"][scheme_key]

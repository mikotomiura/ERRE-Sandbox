"""論文 02 Phase 0 pilot — 禁止 P-1〜P-4 が *装置として* 効いているかの検査.

設計 = ``.steering/20260912-paper02-phase0/design-final.md``。

この test の設計上の要点は 2 つある:

1. **負例は必ず判定関数を通す。** fixture を構築するだけの assert は何も
   検査していない (``feedback_witness_needs_mutation_testing``)。
2. **陽性対照を置く。** import 検査器の陽性対照は既存の
   ``scripts/ecl_bank_cproper_capture.py`` — これは実際に ``bank_scorer`` を
   import している。検査器が「cproper=陽性 / pilot=陰性」の **両方** を
   言えなければ、その検査器は壊れている (DA-P0-2)。

Ollama は不要 (M-loop の chat seam に決定的な mock を注入する)。
"""

from __future__ import annotations

import importlib
import math
import sys
from pathlib import Path
from typing import Any

import pytest
from scripts import paper02_phase0_pilot as pilot

from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.schemas import Zone

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PILOT_SOURCE = _REPO_ROOT / "scripts" / "paper02_phase0_pilot.py"
_CPROPER_SOURCE = _REPO_ROOT / "scripts" / "ecl_bank_cproper_capture.py"
_EXPERIMENT_DIR = _REPO_ROOT / "experiments" / "20260912-paper02-phase0"


def _plan_json(zone: str | None) -> str:
    zone_field = f'"{zone}"' if zone is not None else "null"
    return (
        '{"thought": "t", "utterance": "u", '
        f'"destination_zone": {zone_field}, "animation": "walk"}}'
    )


# --------------------------------------------------------------------------- #
# G1 — 実行時 import guard
# --------------------------------------------------------------------------- #


def _purge_scorer() -> dict[str, Any]:
    saved = {k: v for k, v in sys.modules.items() if pilot.SCORER_NEEDLE in k}
    for key in saved:
        del sys.modules[key]
    return saved


def test_g1_guard_blocks_a_scorer_import() -> None:
    # 負例 (scorer の import) を guard に **通して** raise することを見る。
    saved = _purge_scorer()
    try:
        uninstall = pilot.install_scorer_import_guard()
        try:
            with pytest.raises(pilot.ScorerImportError):
                importlib.import_module(pilot.SCORER_MODULE)
        finally:
            uninstall()
    finally:
        sys.modules.update(saved)


def test_g1_guard_allows_unrelated_imports() -> None:
    # guard が「何でも raise する」壊れ方をしていないことの対照。
    saved = _purge_scorer()
    try:
        uninstall = pilot.install_scorer_import_guard()
        try:
            assert importlib.import_module("json") is not None
        finally:
            uninstall()
    finally:
        sys.modules.update(saved)


def test_g1_guard_refuses_to_install_when_scorer_is_already_imported() -> None:
    # sys.modules cache は finder を迂回するので、後から挿しても遅い。
    saved = _purge_scorer()
    try:
        importlib.import_module(pilot.SCORER_MODULE)
        with pytest.raises(pilot.ScorerImportError):
            pilot.install_scorer_import_guard()
    finally:
        sys.modules.update(saved)


def test_g1_guard_is_removed_by_its_uninstall_callable() -> None:
    saved = _purge_scorer()
    try:
        before = len(sys.meta_path)
        uninstall = pilot.install_scorer_import_guard()
        assert len(sys.meta_path) == before + 1
        uninstall()
        assert len(sys.meta_path) == before
    finally:
        sys.modules.update(saved)


# --------------------------------------------------------------------------- #
# G2 / G2b — 静的 AST 検査 (陽性対照つき)
# --------------------------------------------------------------------------- #


def test_g2_positive_control_cproper_source_does_import_the_scorer() -> None:
    # 陽性対照。ここが空になる検査器は恒真であり、陰性判定に意味がない。
    assert pilot.scorer_import_source_hits(_CPROPER_SOURCE)


def test_g2_positive_control_detects_the_plain_import_form(tmp_path: Path) -> None:
    # cproper は ``from ... import`` 形なので、``import x.y.bank_scorer`` の枝は
    # cproper だけでは覆えない。mutation 実験でこの穴が実際に見つかった
    # (2026-09-12、M3 が生き残った)。合成した陽性対照で両方の枝を塞ぐ。
    for source in (
        "import erre_sandbox.integration.embodied.bank_scorer",
        "import erre_sandbox.integration.embodied.bank_scorer as s",
    ):
        probe = tmp_path / "probe.py"
        probe.write_text(source, encoding="utf-8")
        assert pilot.scorer_import_source_hits(probe), source


def test_g2_pilot_source_does_not_import_the_scorer() -> None:
    assert pilot.scorer_import_source_hits(_PILOT_SOURCE) == ()


def test_g2b_positive_control_detects_a_dynamic_import_mechanism(
    tmp_path: Path,
) -> None:
    # 合成した陽性対照を **同じ関数に通す**。
    for source in (
        "import importlib\n",
        "from importlib import import_module\n",
        "x = __import__('json')\n",
        "exec('import json')\n",
    ):
        probe = tmp_path / "probe.py"
        probe.write_text(source, encoding="utf-8")
        assert pilot.dynamic_import_source_hits(probe), source


def test_g2b_pilot_source_has_no_dynamic_import_mechanism() -> None:
    assert pilot.dynamic_import_source_hits(_PILOT_SOURCE) == ()


# --------------------------------------------------------------------------- #
# G3 — 実行時 (推移的) import 検査 (陽性対照つき)
# --------------------------------------------------------------------------- #


def test_g3_positive_control_cproper_pulls_the_scorer_at_runtime() -> None:
    # 陽性対照。固定値を返す壊れ方をした検査器はここで落ちる。
    assert pilot.imports_scorer_at_runtime(pilot.CPROPER_MODULE) is True


def test_g3_pilot_does_not_pull_the_scorer_at_runtime() -> None:
    assert pilot.imports_scorer_at_runtime(pilot.PILOT_MODULE) is False


# --------------------------------------------------------------------------- #
# G4 — verdict-blind gate (負例をすべて判定関数に通す)
# --------------------------------------------------------------------------- #


def _wellformed(role: str = "primary") -> dict[str, Any]:
    payload: dict[str, Any] = dict.fromkeys(pilot.ALLOWED_KEYS[role], "x")
    payload.update(
        {
            "model": "llama3.1:8b",
            "gpu_total_mib": 16311,
            "n_draws": 96,
            "latency_ms_mean": 1234.5,
            "think_false_accepted": True,
        }
    )
    return payload


def test_g4_accepts_a_wellformed_payload() -> None:
    pilot.assert_verdict_blind(_wellformed(), role="primary")


def test_g4_rejects_a_nested_mapping() -> None:
    payload = _wellformed()
    payload["model"] = {"nested": 1}
    with pytest.raises(pilot.VerdictBlindError, match="flatness"):
        pilot.assert_verdict_blind(payload, role="primary")


def test_g4_rejects_a_non_scalar_value() -> None:
    # per-draw の配列を書こうとした瞬間に落ちる = 内訳が表現不能。
    payload = _wellformed()
    payload["latency_ms_mean"] = [1.0, 2.0, 3.0]
    with pytest.raises(pilot.VerdictBlindError, match="non-scalar"):
        pilot.assert_verdict_blind(payload, role="primary")


def test_g4_rejects_a_non_finite_float() -> None:
    payload = _wellformed()
    payload["latency_ms_mean"] = math.nan
    with pytest.raises(pilot.VerdictBlindError, match="non-finite"):
        pilot.assert_verdict_blind(payload, role="primary")


def test_g4_rejects_an_extra_key() -> None:
    payload = _wellformed()
    payload["rho_hat"] = 1.0
    with pytest.raises(pilot.VerdictBlindError, match="key set mismatch"):
        pilot.assert_verdict_blind(payload, role="primary")


def test_g4_rejects_a_per_context_breakdown_key() -> None:
    payload = _wellformed()
    payload["per_context_none_rate"] = 0.1
    with pytest.raises(pilot.VerdictBlindError, match="key set mismatch"):
        pilot.assert_verdict_blind(payload, role="primary")


def test_g4_rejects_a_missing_key() -> None:
    payload = _wellformed()
    del payload["latency_ms_p95"]
    with pytest.raises(pilot.VerdictBlindError, match="key set mismatch"):
        pilot.assert_verdict_blind(payload, role="primary")


def test_g4_rejects_a_zone_name_hidden_in_a_string_value() -> None:
    payload = _wellformed()
    payload["gpu_name"] = "walked to the garden"
    with pytest.raises(pilot.VerdictBlindError, match="forbidden token"):
        pilot.assert_verdict_blind(payload, role="primary")


def test_g4_rejects_an_unknown_role() -> None:
    with pytest.raises(pilot.VerdictBlindError, match="unknown role"):
        pilot.assert_verdict_blind(_wellformed(), role="nonsense")


def test_g4_reference_role_must_not_carry_parse_keys() -> None:
    # Codex HIGH-3: qwen3 は Phase 3 の control そのものなので、
    # parse 挙動を出すと R5 の予備結果を覗くことになる。
    assert "plan_parse_band" not in pilot.ALLOWED_KEYS["reference"]
    assert "zone_present_band" not in pilot.ALLOWED_KEYS["reference"]
    pilot.assert_verdict_blind(_wellformed("reference"), role="reference")

    leaky = _wellformed("reference")
    leaky["plan_parse_band"] = "gte_0.8"
    with pytest.raises(pilot.VerdictBlindError, match="key set mismatch"):
        pilot.assert_verdict_blind(leaky, role="reference")


# --------------------------------------------------------------------------- #
# G5 — 情報消去
# --------------------------------------------------------------------------- #


def test_g5_pilot_draw_carries_exactly_two_boolean_fields() -> None:
    # Codex MEDIUM-1: 不変性 test だけだと、負例間で値が変わらないフィールドを
    # 足しても落ちない。フィールド集合そのものを literal と突き合わせる。
    import dataclasses

    actual = {f.name for f in dataclasses.fields(pilot.PilotDraw)}
    assert actual == {"plan_parsed", "zone_present"}


def test_g5_projection_erases_zone_identity() -> None:
    # zone が違うだけの応答は **同一に** 射影される = zone 同一性が消えている。
    projections = {pilot.project_response(_plan_json(zone.value)) for zone in Zone}
    assert len(projections) == 1
    assert next(iter(projections)) == pilot.PilotDraw(
        plan_parsed=True, zone_present=True
    )


def test_g5_projection_separates_null_zone_from_parse_failure() -> None:
    # Codex MEDIUM-2: BankLlmCallRecord は両方 None に潰すので自前 parse で分ける。
    assert pilot.project_response(_plan_json(None)) == pilot.PilotDraw(
        plan_parsed=True, zone_present=False
    )
    assert pilot.project_response("not json at all") == pilot.PilotDraw(
        plan_parsed=False, zone_present=False
    )


def test_g5_pooled_bands_cannot_see_context_or_arm() -> None:
    # pooled_bands の引数型には ctx も条件も zone 名も無い。
    draws = [pilot.PilotDraw(plan_parsed=True, zone_present=True)] * 9
    draws.append(pilot.PilotDraw(plan_parsed=False, zone_present=False))
    assert pilot.pooled_bands(draws) == ("gte_0.8", "gte_0.8")


def test_bands_do_not_sit_on_the_r4_threshold() -> None:
    # DA-P0-10: 上位 ADR の R4 は pooled none_rate > 0.5。
    # バンド境界を 0.5 に置かないことで、バンド値が閾値と直接一致しない。
    assert pilot.BAND_LOW != 0.5
    assert pilot.BAND_HIGH != 0.5
    assert pilot.rate_band(0.49) == pilot.rate_band(0.51)


# --------------------------------------------------------------------------- #
# G6 — 成果物ツリー走査
# --------------------------------------------------------------------------- #


_EXPECTED_ARTIFACT_LEAK_TOKENS = (
    "study",
    "peripatos",
    "chashitsu",
    "agora",
    "garden",
    "raw_response",
    "pre_bias_destination_zone",
    "frozen_ctx_id",
    "mc_index",
)

_EXPECTED_FORBIDDEN_TOKENS = (
    "rho",
    "power",
    "permutation",
    "entropy",
    "t_on",
    "t_off",
    "tv_bar",
    "tv_pool",
    "verdict",
    "per_context",
    "per_ctx",
    "condition",
    "histogram",
    "by_zone",
    "study",
    "peripatos",
    "chashitsu",
    "agora",
    "garden",
)


def test_token_sets_match_the_frozen_literals() -> None:
    # **literal と突き合わせる。** 生きている tuple を走査するだけの test は
    # tuple から 1 語落とす mutation を素通りさせる (2026-09-12、M17-M20 が
    # 生き残った)。集合そのものを凍結して、変更が必ず diff に出るようにする。
    assert pilot.ARTIFACT_LEAK_TOKENS == _EXPECTED_ARTIFACT_LEAK_TOKENS
    assert pilot.FORBIDDEN_TOKENS == _EXPECTED_FORBIDDEN_TOKENS


def test_g6_positive_control_flags_every_leak_token() -> None:
    for token in _EXPECTED_ARTIFACT_LEAK_TOKENS:
        assert pilot.forbidden_token_hits(
            f"prefix {token} suffix", pilot.ARTIFACT_LEAK_TOKENS
        ) == (token,), token


def test_g4_positive_control_flags_every_forbidden_token() -> None:
    for token in _EXPECTED_FORBIDDEN_TOKENS:
        assert token in pilot.forbidden_token_hits(f"prefix {token} suffix"), token


def test_g6_tree_scanner_flags_a_dirty_tree(tmp_path: Path) -> None:
    # 走査器そのものの陽性対照。これが無いと「常に空を返す」改変が
    # 素通りする (2026-09-12、M22 が生き残った) — 本物のツリーは綺麗なので。
    (tmp_path / "results").mkdir()
    (tmp_path / "clean.md").write_text("判定は計算しない", encoding="utf-8")
    assert pilot.artifact_tree_leak_hits(tmp_path) == ()

    (tmp_path / "results" / "leaked.json").write_text(
        '{"raw_response": "walked to the garden"}', encoding="utf-8"
    )
    hits = pilot.artifact_tree_leak_hits(tmp_path)
    assert hits
    assert all(hit.startswith("results/leaked.json: ") for hit in hits)


def test_g6_tree_scanner_treats_unreadable_files_as_violations(
    tmp_path: Path,
) -> None:
    (tmp_path / "blob.bin").write_bytes(b"\xff\xfe\x00\x01")
    hits = pilot.artifact_tree_leak_hits(tmp_path)
    assert hits == ("blob.bin: <unreadable-as-utf8>",)


def test_g6_scanner_allows_prose_that_describes_the_blinding() -> None:
    # G6 が守るのは「データを貼らないこと」であって語彙ではない。
    assert (
        pilot.forbidden_token_hits(
            "判定 (verdict) は計算しない", pilot.ARTIFACT_LEAK_TOKENS
        )
        == ()
    )


def test_g6_experiment_tree_is_leak_free() -> None:
    assert _EXPERIMENT_DIR.is_dir(), "Phase 0 の experiments ディレクトリが無い"
    assert pilot.artifact_tree_leak_hits(_EXPERIMENT_DIR) == ()


# --------------------------------------------------------------------------- #
# I-1 — 射影が LLM の seam で起きていること (Codex HIGH-1 の witness)
# --------------------------------------------------------------------------- #


class _ZoneMockChat:
    """毎回違う zone を返す決定的 mock。"""

    def __init__(self) -> None:
        self.calls = 0
        self._cycle = [z.value for z in Zone] + [None]

    async def chat(self, *_args: Any, **_kwargs: Any) -> ChatResponse:
        content = _plan_json(self._cycle[self.calls % len(self._cycle)])
        self.calls += 1
        return ChatResponse(
            content=content, model="phase0-mock", eval_count=1, total_duration_ms=0.0
        )

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_i1_projection_scrubs_the_response_before_the_mloop_sees_it() -> None:
    # M-loop が組み立てる record に draw 情報が 1 ビットも入らないことの witness。
    client = pilot._ProjectingChatClient(_ZoneMockChat(), collect_parse=True)
    seen = []
    for _ in range(len(Zone) + 1):
        response = await client.chat((), sampling=pilot._PROBE_SAMPLING, think=False)
        seen.append(response.content)
    assert set(seen) == {pilot._SCRUBBED_RESPONSE}
    for zone in Zone:
        assert zone.value not in pilot._SCRUBBED_RESPONSE
    # 射影側には parse の内訳が残っている (捨てているのは zone 同一性)。
    assert len(client.draws) == len(Zone) + 1


@pytest.mark.asyncio
async def test_i1_reference_role_never_builds_a_pilot_draw() -> None:
    # collect_parse=False では parse 率が系のどこにも生じない (Codex HIGH-3)。
    client = pilot._ProjectingChatClient(_ZoneMockChat(), collect_parse=False)
    for _ in range(5):
        await client.chat((), sampling=pilot._PROBE_SAMPLING, think=False)
    assert client.draws == ()
    assert client.calls == 5


@pytest.mark.asyncio
async def test_i1_latencies_are_sorted_so_call_order_is_not_carried() -> None:
    client = pilot._ProjectingChatClient(_ZoneMockChat(), collect_parse=True)
    for _ in range(6):
        await client.chat((), sampling=pilot._PROBE_SAMPLING, think=False)
    latencies = client.latencies_ms_sorted
    assert list(latencies) == sorted(latencies)


# --------------------------------------------------------------------------- #
# end-to-end (Ollama-free) — payload が gate を通ること
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_pilot_end_to_end_emits_a_verdict_blind_payload() -> None:
    payload = await pilot.run_pilot(
        model="mock-model",
        role="primary",
        m_draws=2,
        k_contexts=2,
        inner_chat=_ZoneMockChat(),
    )
    pilot.assert_verdict_blind(payload, role="primary")
    assert payload["n_draws"] == 2 * 2 * 2
    assert payload["plan_parse_band"] in {"lt_0.2", "0.2_to_0.8", "gte_0.8"}
    # 実数の parse 率はどこにも無い。
    assert "plan_parse_rate" not in payload
    assert "none_rate" not in payload


@pytest.mark.asyncio
async def test_pilot_reference_role_omits_the_parse_bands() -> None:
    payload = await pilot.run_pilot(
        model="mock-model",
        role="reference",
        m_draws=2,
        k_contexts=2,
        inner_chat=_ZoneMockChat(),
    )
    pilot.assert_verdict_blind(payload, role="reference")
    assert "plan_parse_band" not in payload
    assert "zone_present_band" not in payload

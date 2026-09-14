"""``scripts/paper02_run_arms.py`` — 論文 02 前向き 2 アーム実走 driver のテスト.

このテストが守っているのは 3 つである。

1. **封印フィールドが観測由来であること。** 値が CLI 引数や literal から来ていると、
   ``verify_seal.py`` との一致は「著者が封印値を正しく打った」ことしか示さない。
   各フィールドを壊して落ちることを実測する
   (``feedback_witness_needs_mutation_testing``)。
2. **``bank_checksum`` が「消費した凍結 bank」であって「産出した records」でないこと。**
   雛形 ``ecl_bank_cproper_capture.py`` は manifest 直下の同じパスに別の量を書いており、
   複製するとそれが実走の後にしか分からない形で壊れる。
3. **spend の前に止まること。** 封印と食い違う実走は pre-registered として提示できない。
   ``--capture`` は draw を 1 つも取らずに終了しなければならない。

陽性対照を必ず添える: 落ちるだけの検査は恒真でありうるので、封印どおりの入力が
**通る** ことも同時に実測する
(``feedback_negative_fixture_must_not_be_self_referential``)。
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "paper02_run_arms.py"


@pytest.fixture(scope="module")
def driver() -> Any:
    spec = importlib.util.spec_from_file_location("paper02_run_arms", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["paper02_run_arms"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# 合成 fixture — 封印にも凍結 bank にも依存せず、契約の形だけを再現する
# --------------------------------------------------------------------------- #

_PLAN = {
    "thought": "t",
    "utterance": "u",
    "destination_zone": "study",
    "animation": "walk",
}
_SAMPLING_ON = {"temperature": 0.82, "top_p": 0.94, "repeat_penalty": 1.0}
_SAMPLING_OFF = {"temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.0}


def _bank_rows(*, k: int, m: int) -> list[dict[str, Any]]:
    return [
        {
            "frozen_ctx_id": f"ctx-{i}",
            "condition": condition,
            "mc_index": mc,
            "system_prompt": f"sys-{i}",
            "user_prompt": f"usr-{i}",
            "sampling": _SAMPLING_ON if condition == "on" else _SAMPLING_OFF,
            "raw_response": json.dumps(_PLAN),
            "pre_bias_destination_zone": "study",
        }
        for i in range(k)
        for condition in ("on", "off")
        for mc in range(m)
    ]


@pytest.fixture
def bank_path(tmp_path: Path, driver: Any) -> Path:
    path = tmp_path / "bank_records.jsonl"
    text = "".join(
        f"{driver.handoff.canonical_dumps(row)}\n" for row in _bank_rows(k=2, m=2)
    )
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


@pytest.fixture
def sealed(driver: Any, bank_path: Path) -> dict[str, Any]:
    """合成 bank と**一致する**封印 spec (= 陽性対照)。"""
    bank = driver.load_frozen_bank(bank_path)
    return {
        "thresholds": {"note": "…", "alpha": 0.05},
        "environment": {
            "ollama_version": "0.32.12",
            "python": "3.11.15",
            "uv_lock_sha256": "a" * 64,
        },
        "context_bank": {
            "bank_checksum": bank.checksum,
            "context_ids": bank.context_ids,
        },
        "arms": {
            "control": {"model": "qwen3:8b", "model_digest": "5" * 64, "think": False},
            "primary": {
                "model": "llama3.1:8b",
                "model_digest": "4" * 64,
                "think": False,
            },
        },
    }


def _observation(driver: Any) -> Any:
    return driver.OllamaObservation(
        version="0.32.12",
        digests={"qwen3:8b": "5" * 64, "llama3.1:8b": "4" * 64},
    )


def _problems(driver: Any, sealed: dict[str, Any], bank: Any, **over: Any) -> list[str]:
    kwargs: dict[str, Any] = {
        "spec": sealed,
        "arm": "primary",
        "observed": _observation(driver),
        "uv_lock": "a" * 64,
        "python_version": "3.11.15",
        "bank": bank,
    }
    kwargs.update(over)
    return driver.preflight_problems(**kwargs)


class _StubChat:
    """M-loop の chat client スタブ。live 経路は変えない。"""

    def __init__(self, *, model: str = "llama3.1:8b") -> None:
        self.model = model
        self.seen_think: list[Any] = []

    async def chat(
        self,
        messages: Any,  # noqa: ARG002
        *,
        sampling: Any,  # noqa: ARG002
        model: Any = None,  # noqa: ARG002
        options: Any = None,  # noqa: ARG002
        think: Any = None,
    ) -> Any:
        from erre_sandbox.inference.ollama_adapter import ChatResponse

        self.seen_think.append(think)
        return ChatResponse(
            content=json.dumps(_PLAN),
            model=self.model,
            eval_count=1,
            total_duration_ms=0.0,
        )

    async def close(self) -> None:
        return None


def _capture(driver: Any, sealed: dict[str, Any], bank: Any, **over: Any) -> Any:
    kwargs: dict[str, Any] = {
        "arm": "primary",
        "spec": sealed,
        "seal_hash": "0" * 64,
        "bank": bank,
        "m_draws": 2,
        "seed": 20260708,
        "uv_lock": "a" * 64,
        "python_version": "3.11.15",
        "observed": _observation(driver),
        "inner_chat": _StubChat(),
    }
    kwargs.update(over)
    return asyncio.run(driver.capture(**kwargs))


def _manifest_of(rendered: dict[str, str]) -> dict[str, Any]:
    return json.loads(rendered["run-manifest.json"])


def _capture_to(driver: Any, sealed: dict[str, Any], bank: Any, out: Path) -> None:
    rendered, _ = _capture(driver, sealed, bank)
    driver._write(out, rendered)


def _seal_manifest(directory: Path) -> tuple[Path, str]:
    body = {"schema": "x", "files": {"a": {"sha256": "1" * 64}}}
    canonical = json.dumps(body, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    path = directory / "SEAL-MANIFEST.json"
    path.write_text(
        json.dumps({**body, "self_sha256": digest}, indent=2), encoding="utf-8"
    )
    return path, digest


# --------------------------------------------------------------------------- #
# 陽性対照 — 落ちるだけの検査は恒真でありうる
# --------------------------------------------------------------------------- #


def test_preflight_passes_when_observation_matches_seal(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    bank = driver.load_frozen_bank(bank_path)
    assert _problems(driver, sealed, bank) == []


def test_preflight_passes_for_both_arms(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    bank = driver.load_frozen_bank(bank_path)
    for arm in ("control", "primary"):
        assert _problems(driver, sealed, bank, arm=arm) == [], arm


# --------------------------------------------------------------------------- #
# 変異 — 封印 6 項目が **各々** 落ちること
# --------------------------------------------------------------------------- #


def test_mutation_backend_version(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    bank = driver.load_frozen_bank(bank_path)
    observed = driver.OllamaObservation(
        version="0.33.0", digests=_observation(driver).digests
    )
    problems = _problems(driver, sealed, bank, observed=observed)
    assert any("ollama_version" in p for p in problems), problems


def test_mutation_model_digest(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    bank = driver.load_frozen_bank(bank_path)
    observed = driver.OllamaObservation(
        version="0.32.12",
        digests={"qwen3:8b": "5" * 64, "llama3.1:8b": "0" * 64},
    )
    problems = _problems(driver, sealed, bank, observed=observed)
    assert any("model_digest" in p for p in problems), problems


def test_mutation_model_absent_from_backend(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    bank = driver.load_frozen_bank(bank_path)
    observed = driver.OllamaObservation(
        version="0.32.12", digests={"qwen3:8b": "5" * 64}
    )
    problems = _problems(driver, sealed, bank, observed=observed)
    assert any("model_digest" in p for p in problems), problems


def test_mutation_uv_lock(driver: Any, sealed: dict[str, Any], bank_path: Path) -> None:
    bank = driver.load_frozen_bank(bank_path)
    problems = _problems(driver, sealed, bank, uv_lock="b" * 64)
    assert any("uv_lock_sha256" in p for p in problems), problems


def test_mutation_python(driver: Any, sealed: dict[str, Any], bank_path: Path) -> None:
    bank = driver.load_frozen_bank(bank_path)
    problems = _problems(driver, sealed, bank, python_version="3.12.0")
    assert any("python" in p for p in problems), problems


def test_mutation_substituted_bank(
    driver: Any, sealed: dict[str, Any], tmp_path: Path
) -> None:
    """凍結 bank を差し替えると落ちる.

    封印の not_minor_deviations = "substituting the frozen context bank"。
    """
    other = tmp_path / "other.jsonl"
    rows = _bank_rows(k=2, m=2)
    rows[0]["raw_response"] = json.dumps({**_PLAN, "thought": "tampered"})
    other.write_text(
        "".join(f"{driver.handoff.canonical_dumps(r)}\n" for r in rows),
        encoding="utf-8",
        newline="\n",
    )
    problems = _problems(driver, sealed, driver.load_frozen_bank(other))
    assert any("bank_checksum" in p for p in problems), problems


def test_mutation_sliced_bank_is_a_different_bank(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    """K を削るのは「規模が小さい」でなく「別の bank」である."""
    sliced = driver.load_frozen_bank(bank_path, k_contexts=1)
    problems = _problems(driver, sealed, sliced)
    assert any("bank_checksum" in p for p in problems), problems
    assert any("context_ids" in p for p in problems), problems
    assert any("別物" in p for p in problems), problems


def test_mutation_unknown_arm(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    bank = driver.load_frozen_bank(bank_path)
    problems = _problems(driver, sealed, bank, arm="attacker")
    assert problems
    assert "未知のアーム" in problems[0]


def test_load_frozen_bank_refuses_more_contexts_than_it_has(
    driver: Any, bank_path: Path
) -> None:
    with pytest.raises(SystemExit, match="context を"):
        driver.load_frozen_bank(bank_path, k_contexts=99)


# --------------------------------------------------------------------------- #
# bank_checksum の意味論 — 本 driver 最大の罠
# --------------------------------------------------------------------------- #


def test_bank_checksum_is_the_consumed_bank_not_the_produced_records(
    driver: Any, bank_path: Path
) -> None:
    """manifest の ``bank_checksum`` は消費した bank。産出 records は別パスに入る。

    雛形 ``ecl_bank_cproper_capture.py`` は同じパスに産出 records のハッシュを
    書いている。同じにすると封印比較が構造的に不可能になる。
    """
    bank = driver.load_frozen_bank(bank_path)
    # 産出 records は別モデルの別応答である。
    rows = _bank_rows(k=2, m=2)
    for row in rows:
        row["raw_response"] = json.dumps({**_PLAN, "utterance": "different model"})
    produced = driver._records_from_jsonl(
        "".join(f"{driver.handoff.canonical_dumps(r)}\n" for r in rows)
    )

    produced_checksum = driver.bank_checksum(produced)
    assert produced_checksum != bank.checksum

    manifest = driver.build_run_manifest(
        arm="primary",
        seal_hash="0" * 64,
        bank=bank,
        records=produced,
        records_jsonl="".join(
            f"{driver.handoff.canonical_dumps(driver._bank_record_to_dict(r))}\n"
            for r in produced
        ),
        annotation_jsonl="",
        m_draws=2,
        k_contexts=2,
        seed=20260708,
        env_pins={"model": "llama3.1:8b"},
        sub_sealed_scale=True,
    )
    # 封印比較対象は消費した bank。
    assert manifest["bank_checksum"] == bank.checksum
    assert manifest["bank_checksum"] != produced_checksum
    # 産出 records は別のパスに、別の量として入る。
    assert manifest["artifacts"]["run_records.jsonl"]["sha256"] != bank.checksum


def test_frozen_bank_checksum_reproduces_the_completed_run(driver: Any) -> None:
    """完了済 run の bank を読むと、その manifest が記録した checksum が再現する。

    合成 fixture ではなく実物を使う唯一のテスト。封印 ``context_bank.bank_checksum``
    がこの量であることの根拠になる。
    """
    artifacts = _REPO_ROOT / "experiments" / "20260710-m13-c-proper" / "artifacts"
    bank_file = artifacts / "bank_records.jsonl"
    manifest_file = artifacts / "manifest.json"
    if not bank_file.is_file() or not manifest_file.is_file():
        pytest.skip("完了済 run の成果物が無い")
    recorded = json.loads(manifest_file.read_text(encoding="utf-8"))["bank_checksum"]
    assert driver.load_frozen_bank(bank_file).checksum == recorded


# --------------------------------------------------------------------------- #
# 観測由来であること — 封印値や spec から書き写していない
# --------------------------------------------------------------------------- #


def test_think_is_observed_not_restated(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    """``env_pins.think`` は apparatus が実際に渡した値である。"""
    rendered, _ = _capture(driver, sealed, driver.load_frozen_bank(bank_path))
    pins = _manifest_of(rendered)["env_pins"]
    assert pins["think"] is False
    assert pins["model"] == "llama3.1:8b"
    assert pins["model_digest"] == "4" * 64
    assert pins["ollama_version"] == "0.32.12"


def test_think_in_manifest_equals_what_the_apparatus_passed(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    """manifest の ``think`` を **観測値そのもの** に束縛する.

    ``is False`` を確かめるだけでは、定数を書いても観測しても同じく通る (恒真)。
    spy が実際に見た値と manifest の値を突き合わせる。
    """
    stub = _StubChat()
    rendered, _ = _capture(
        driver, sealed, driver.load_frozen_bank(bank_path), inner_chat=stub
    )
    assert stub.seen_think, "apparatus が think を 1 度も渡していない"
    assert set(stub.seen_think) == {False}
    assert _manifest_of(rendered)["env_pins"]["think"] == stub.seen_think[0]


def test_model_in_manifest_comes_from_the_response_not_the_spec(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    """応答が名乗ったモデルが manifest に載る (spec から書き写さない).

    spec は ``llama3.1:8b`` と言っているのに応答は別のモデルを名乗る状況を作る。
    """
    rendered, _ = _capture(
        driver,
        sealed,
        driver.load_frozen_bank(bank_path),
        inner_chat=_StubChat(model="mutant:1b"),
    )
    pins = _manifest_of(rendered)["env_pins"]
    assert pins["model"] == "mutant:1b"
    # tags に無いモデルなので digest は観測できない。埋めずにそう書く。
    assert pins["model_digest"] == "unobserved"


def test_ollama_version_in_manifest_comes_from_the_observation(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    """封印値と違う版を観測したらその版が載る (封印値を書き写さない)."""
    drifted = driver.OllamaObservation(
        version="0.99.0", digests=_observation(driver).digests
    )
    rendered, _ = _capture(
        driver, sealed, driver.load_frozen_bank(bank_path), observed=drifted
    )
    pins = _manifest_of(rendered)["env_pins"]
    assert pins["ollama_version"] == "0.99.0"
    assert pins["ollama_version"] != sealed["environment"]["ollama_version"]


def test_lockfile_and_python_in_manifest_come_from_the_observation(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    """``uv_lock_sha256`` / ``python`` も観測値が載る (封印から書き写さない)."""
    rendered, _ = _capture(
        driver,
        sealed,
        driver.load_frozen_bank(bank_path),
        uv_lock="c" * 64,
        python_version="3.12.7",
    )
    pins = _manifest_of(rendered)["env_pins"]
    assert pins["uv_lock_sha256"] == "c" * 64
    assert pins["uv_lock_sha256"] != sealed["environment"]["uv_lock_sha256"]
    assert pins["python"] == "3.12.7"
    assert pins["python"] != sealed["environment"]["python"]


def test_spy_rejects_mixed_think_regimes(driver: Any) -> None:
    spy = driver.ThinkAndModelSpy(inner=_StubChat())
    spy.think_values = {False, True}
    with pytest.raises(SystemExit, match="単一の think 相"):
        spy.observed_think()


def test_spy_rejects_mixed_models(driver: Any) -> None:
    spy = driver.ThinkAndModelSpy(inner=_StubChat())
    spy.models = {"a", "b"}
    with pytest.raises(SystemExit, match="単一のモデル"):
        spy.observed_model()


# --------------------------------------------------------------------------- #
# m_draws / k_contexts / context_ids は産出物・消費物から数える
# --------------------------------------------------------------------------- #


def test_run_scale_is_counted_from_the_artifacts(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    bank = driver.load_frozen_bank(bank_path)
    rendered, metrics = _capture(driver, sealed, bank, m_draws=3)
    manifest = _manifest_of(rendered)
    assert manifest["run"]["m_draws"] == 3
    assert manifest["run"]["k_contexts"] == 2
    assert manifest["run"]["context_ids"] == bank.context_ids
    # 封印未満は自己申告される (保証ではなく申告)。
    assert manifest["sub_sealed_scale"] is True
    assert metrics["llm_calls"] == 2 * 3 * 2


async def _drifted_mloop_think_none(
    *, llm: Any, frozen_contexts: Any, m_draws: int
) -> Any:
    """``run_bank_mloop`` が think を強制しなくなった世界を再現する.

    捏造ではなく、spy が存在する理由そのものである。定数を書いていれば封印と
    一致する ``False`` が黙って載り、観測していれば ``None`` が載って
    ``verify_seal`` が落とす。
    """
    from erre_sandbox.integration.embodied.bank import run_bank_mloop

    original = llm.chat

    async def without_think(messages: Any, **kwargs: Any) -> Any:
        kwargs["think"] = None
        return await original(messages, **kwargs)

    llm.chat = without_think  # type: ignore[method-assign]
    return await run_bank_mloop(
        llm=llm, frozen_contexts=frozen_contexts, m_draws=m_draws
    )


def test_think_is_not_restated_when_the_apparatus_stops_forcing_it(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apparatus が think を落としたら manifest にもそれが載る (定数を書かない)."""
    monkeypatch.setattr(driver, "run_bank_mloop", _drifted_mloop_think_none)
    rendered, _ = _capture(driver, sealed, driver.load_frozen_bank(bank_path))
    assert _manifest_of(rendered)["env_pins"]["think"] is None


async def _under_producing_mloop(
    *, llm: Any, frozen_contexts: Any, m_draws: int
) -> Any:
    """要求より少ない draw しか返さない apparatus を再現する."""
    from erre_sandbox.integration.embodied.bank import run_bank_mloop

    produced = await run_bank_mloop(
        llm=llm, frozen_contexts=frozen_contexts, m_draws=m_draws
    )
    keep = m_draws - 1
    return tuple(r for r in produced if r.mc_index < keep)


def test_m_draws_is_counted_not_copied_from_the_argument(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """要求と産出が食い違ったら、manifest には **産出** が載る.

    引数を書き写すと、少なく出た run が「300 draw 走った」と名乗れてしまう。
    封印はその主張を検査できない (引数は manifest に現れないため)。
    """
    monkeypatch.setattr(driver, "run_bank_mloop", _under_producing_mloop)
    rendered, _ = _capture(
        driver, sealed, driver.load_frozen_bank(bank_path), m_draws=3
    )
    assert _manifest_of(rendered)["run"]["m_draws"] == 2, (
        "要求 3 に対し産出 2 が載るべき"
    )


async def _context_dropping_mloop(
    *, llm: Any, frozen_contexts: Any, m_draws: int
) -> Any:
    """1 つの context をまるごと落とす apparatus を再現する."""
    from erre_sandbox.integration.embodied.bank import run_bank_mloop

    produced = await run_bank_mloop(
        llm=llm, frozen_contexts=frozen_contexts, m_draws=m_draws
    )
    dropped = frozen_contexts[-1].frozen_ctx_id
    return tuple(r for r in produced if r.frozen_ctx_id != dropped)


def test_produced_contexts_must_match_the_consumed_bank(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """context が落ちたら内部矛盾した manifest を出さずに停止する.

    ``run.context_ids`` は消費した bank から、``run.k_contexts`` は産出物から
    来る。黙って通すと両者が食い違った manifest が出る。
    """
    monkeypatch.setattr(driver, "run_bank_mloop", _context_dropping_mloop)
    with pytest.raises(driver.CaptureAbortedError, match="消費した bank と食い違う"):
        _capture(driver, sealed, driver.load_frozen_bank(bank_path))


def test_uneven_cells_are_refused(driver: Any) -> None:
    rows = _bank_rows(k=1, m=2)
    records = driver._records_from_jsonl(
        "".join(f"{driver.handoff.canonical_dumps(r)}\n" for r in rows[:-1])
    )
    with pytest.raises(SystemExit, match="draw 数が不揃い"):
        driver._observed_m_draws(records)


# --------------------------------------------------------------------------- #
# sealed_manifest_sha256 — 記録値を読まずに再計算する
# --------------------------------------------------------------------------- #


def test_manifest_names_the_seal(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    """run manifest は封印を **名指し** する.

    ``verify_seal.py`` は ``sealed_manifest_sha256`` が無い manifest を
    「封印を名指ししていない」として落とす。欠落は skip ではなく失敗である。
    """
    rendered, _ = _capture(
        driver, sealed, driver.load_frozen_bank(bank_path), seal_hash="7" * 64
    )
    manifest = _manifest_of(rendered)
    assert manifest["sealed_manifest_sha256"] == "7" * 64
    assert manifest["arm"] == "primary"


def test_sealed_manifest_hash_recomputed(driver: Any, tmp_path: Path) -> None:
    path, digest = _seal_manifest(tmp_path)
    assert driver.sealed_manifest_sha256(path) == digest


def test_sealed_manifest_hash_rejects_internally_broken_seal(
    driver: Any, tmp_path: Path
) -> None:
    """記録値を読むだけなら通ってしまう改竄が、再計算では落ちる。"""
    path, _ = _seal_manifest(tmp_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"]["a"]["sha256"] = "9" * 64  # 本体だけ書き換える
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with pytest.raises(SystemExit, match="自己ハッシュが不整合"):
        driver.sealed_manifest_sha256(path)


def test_sealed_manifest_hash_matches_the_real_seal(driver: Any) -> None:
    """実物の封印に当てる (無ければ skip)。"""
    path = (
        _REPO_ROOT.parent
        / "ERRE-Papers"
        / "collapsed-decision-space"
        / "seal"
        / "SEAL-MANIFEST.json"
    )
    if not path.is_file():
        pytest.skip("論文 repo が無い")
    recorded = json.loads(path.read_text(encoding="utf-8"))["self_sha256"]
    assert driver.sealed_manifest_sha256(path) == recorded


# --------------------------------------------------------------------------- #
# capture → verify の往復と整合ゲート
# --------------------------------------------------------------------------- #


def test_verify_round_trip(
    driver: Any, sealed: dict[str, Any], bank_path: Path, tmp_path: Path
) -> None:
    out = tmp_path / "primary"
    _capture_to(driver, sealed, driver.load_frozen_bank(bank_path), out)
    assert asyncio.run(driver.verify(out, arm="primary")) == driver.VERIFY_SUB_SEALED
    verdict = json.loads((out / "run-verdict.json").read_text(encoding="utf-8"))
    # 封印未満なので INCONCLUSIVE。**それでよい** — ここで検証しているのは
    # 統計ではなく harness である。
    assert verdict["verdict"] == "INCONCLUSIVE"
    assert "thresholds" in verdict


def test_verify_refuses_to_score_a_tampered_bundle(
    driver: Any, sealed: dict[str, Any], bank_path: Path, tmp_path: Path
) -> None:
    """行キーを保ったまま zone だけ書き換える改竄を、整合ゲートが止める。"""
    out = tmp_path / "primary"
    _capture_to(driver, sealed, driver.load_frozen_bank(bank_path), out)
    annotation = out / "run_annotation.jsonl"
    rows = [
        json.loads(line) for line in annotation.read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["pre_bias_destination_zone"] = "garden"
    annotation.write_text(
        "".join(f"{driver.handoff.canonical_dumps(r)}\n" for r in rows),
        encoding="utf-8",
        newline="\n",
    )
    assert asyncio.run(driver.verify(out, arm="primary")) == driver.VERIFY_FAIL
    assert not (out / "run-verdict.json").exists()


def test_verify_replay_touches_no_live_llm(
    driver: Any, sealed: dict[str, Any], bank_path: Path, tmp_path: Path, capsys: Any
) -> None:
    out = tmp_path / "primary"
    _capture_to(driver, sealed, driver.load_frozen_bank(bank_path), out)
    asyncio.run(driver.verify(out, arm="primary"))
    captured = capsys.readouterr().out
    assert "replay が byte 一致" in captured
    assert "live LLM に触れた" not in captured


# --------------------------------------------------------------------------- #
# observe_ollama — 観測が HTTP から来ていること
# --------------------------------------------------------------------------- #


def test_observe_ollama_reads_version_and_digests(driver: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.32.12"})
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "llama3.1:8b", "digest": "4" * 64}]},
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="http://stub", transport=httpx.MockTransport(handler)
    )
    observed = asyncio.run(driver.observe_ollama("http://stub", client=client))
    asyncio.run(client.aclose())
    assert observed.version == "0.32.12"
    assert observed.digests == {"llama3.1:8b": "4" * 64}


# --------------------------------------------------------------------------- #
# capture は事前ゲートを skip できない
# --------------------------------------------------------------------------- #


def _paper_repo_with(spec: dict[str, Any], root: Path) -> Path:
    (root / "seal").mkdir(parents=True, exist_ok=True)
    (root / "seal" / "arm-spec.json").write_text(json.dumps(spec), encoding="utf-8")
    _seal_manifest(root / "seal")
    return root


def _patch_observers(driver: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_observe(_endpoint: str, *, _client: Any = None) -> Any:
        return _observation(driver)

    monkeypatch.setattr(driver, "observe_ollama", fake_observe)
    monkeypatch.setattr(driver, "observe_uv_lock_sha256", lambda _p: "a" * 64)
    monkeypatch.setattr(driver, "observe_python", lambda: "3.11.15")


def test_capture_aborts_before_any_draw_when_seal_mismatches(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """封印と食い違うとき ``--capture`` は draw を 1 つも取らずに終了する。"""
    broken = copy.deepcopy(sealed)
    broken["environment"]["ollama_version"] = "0.99.0"  # 版が食い違う
    paper_repo = _paper_repo_with(broken, tmp_path / "paper")
    _patch_observers(driver, monkeypatch)

    called: list[int] = []

    async def must_not_run(**_kwargs: Any) -> Any:
        called.append(1)
        raise AssertionError("draw を取ってはならない")

    monkeypatch.setattr(driver, "capture", must_not_run)

    code = driver.main(
        [
            "--capture",
            "--arm",
            "primary",
            "--paper-repo",
            str(paper_repo),
            "--bank",
            str(bank_path),
            "--k-contexts",
            "2",
            "--m-draws",
            "2",
            "--out-root",
            str(tmp_path / "out"),
        ]
    )
    assert code == 1
    assert called == []
    assert not (tmp_path / "out").exists()


def test_preflight_mode_returns_zero_when_matching(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper_repo = _paper_repo_with(sealed, tmp_path / "paper")
    _patch_observers(driver, monkeypatch)
    code = driver.main(
        [
            "--preflight",
            "--arm",
            "primary",
            "--paper-repo",
            str(paper_repo),
            "--bank",
            str(bank_path),
            "--k-contexts",
            "2",
        ]
    )
    assert code == 0


def test_arm_is_required_and_never_inferred(driver: Any) -> None:
    """``--arm`` を必須にする理由は封印検査器と同じである。"""
    with pytest.raises(SystemExit):
        driver.main(["--capture"])


# --------------------------------------------------------------------------- #
# Codex independent review (2026-09-14) の指摘に対する回帰ケース
# --------------------------------------------------------------------------- #


def test_verify_refuses_annotation_tampered_with_matching_sha256(
    driver: Any, sealed: dict[str, Any], bank_path: Path, tmp_path: Path
) -> None:
    """Codex HIGH-1: sha256 も揃えた annotation 改竄が通ってはならない.

    manifest の sha256 照合だけでは、zone を書き換えたうえで manifest 側も
    揃える改竄が抜ける (行キーは保たれるので行整合も通る)。annotation を
    replay した records から再導出することで閉じる。
    """
    out = tmp_path / "primary"
    _capture_to(driver, sealed, driver.load_frozen_bank(bank_path), out)
    assert asyncio.run(driver.verify(out, arm="primary")) == driver.VERIFY_SUB_SEALED
    assert (out / "run-verdict.json").exists()

    annotation = out / "run_annotation.jsonl"
    rows = [
        json.loads(line) for line in annotation.read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["pre_bias_destination_zone"] = "garden"
    tampered = "".join(f"{driver.handoff.canonical_dumps(r)}\n" for r in rows)
    annotation.write_text(tampered, encoding="utf-8", newline="\n")

    # manifest の sha256 も揃える (「検査器に渡した != 検査が走った」の型)
    manifest_path = out / "run-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["run_annotation.jsonl"]["sha256"] = hashlib.sha256(
        tampered.encode("utf-8")
    ).hexdigest()
    manifest_path.write_text(
        driver.handoff.canonical_dumps(manifest) + "\n", encoding="utf-8", newline="\n"
    )

    assert asyncio.run(driver.verify(out, arm="primary")) == driver.VERIFY_FAIL
    # 落ちた bundle の古い verdict を残さない
    assert not (out / "run-verdict.json").exists()


def test_verify_requires_the_arm_to_match_the_bundle(
    driver: Any, sealed: dict[str, Any], bank_path: Path, tmp_path: Path
) -> None:
    """Codex MEDIUM-7: control の bundle を primary として検証しても通らない."""
    out = tmp_path / "primary"
    _capture_to(driver, sealed, driver.load_frozen_bank(bank_path), out)
    assert asyncio.run(driver.verify(out, arm="primary")) == driver.VERIFY_SUB_SEALED
    assert asyncio.run(driver.verify(out, arm="control")) == driver.VERIFY_FAIL


def test_capture_uses_the_endpoint_it_observed(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex HIGH-3: draw は観測したのと同じ endpoint に飛ぶ.

    観測だけを --endpoint に向け draw を default に投げると、preflight した
    Ollama と実際に答えた Ollama が別物でも manifest は preflight 側を名乗れる。
    """
    seen: list[str | None] = []
    seen_timeouts: list[float | None] = []

    class _Recording(_StubChat):
        def __init__(
            self,
            *,
            model: str = "llama3.1:8b",
            endpoint: str | None = None,
            timeout: float | None = None,
        ) -> None:
            super().__init__(model=model)
            seen.append(endpoint)
            seen_timeouts.append(timeout)

    monkeypatch.setattr(driver, "OllamaChatClient", _Recording)
    bank = driver.load_frozen_bank(bank_path)
    asyncio.run(
        driver.capture(
            arm="primary",
            spec=sealed,
            seal_hash="0" * 64,
            bank=bank,
            m_draws=2,
            seed=20260708,
            uv_lock="a" * 64,
            python_version="3.11.15",
            observed=_observation(driver),
            endpoint="http://observed-host:11434",
        )
    )
    assert seen == ["http://observed-host:11434"]
    # 既定 60 秒では 2.5 時間の連続実行を生き延びない (code-reviewer H1)
    assert seen_timeouts == [driver._CHAT_TIMEOUT_SECONDS]


def test_capture_stops_if_the_backend_moves_mid_run(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    """実走中に ollama が自動更新されたら、その run は封印を名乗れない (DA-P3B-36)."""

    async def moved(_endpoint: str) -> Any:
        return driver.OllamaObservation(
            version="0.33.0", digests=_observation(driver).digests
        )

    with pytest.raises(driver.CaptureAbortedError, match="版が変わった"):
        _capture(driver, sealed, driver.load_frozen_bank(bank_path), reobserve=moved)


def test_capture_stops_if_the_digest_moves_mid_run(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    async def repulled(_endpoint: str) -> Any:
        return driver.OllamaObservation(
            version="0.32.12",
            digests={"qwen3:8b": "5" * 64, "llama3.1:8b": "9" * 64},
        )

    with pytest.raises(driver.CaptureAbortedError, match="digest が変わった"):
        _capture(driver, sealed, driver.load_frozen_bank(bank_path), reobserve=repulled)


def test_preflight_catches_seed_and_scale_before_any_draw(
    driver: Any, sealed: dict[str, Any], bank_path: Path
) -> None:
    """Codex MEDIUM-6: seed / M の食い違いも draw 0 の時点で出る.

    どちらも manifest に現れてから verify_seal が落とすが、それは実走の後である。
    """
    spec = copy.deepcopy(sealed)
    spec["sampling"] = {"seed": 20260708, "m_draws": 300, "k_contexts": 8}
    bank = driver.load_frozen_bank(bank_path)

    assert _problems(driver, spec, bank, seed=20260708, m_draws=300) == []

    wrong_seed = _problems(driver, spec, bank, seed=12345, m_draws=300)
    assert any("seed" in p for p in wrong_seed), wrong_seed

    wrong_m = _problems(driver, spec, bank, seed=20260708, m_draws=299)
    assert any("m_draws" in p for p in wrong_m), wrong_m


def test_capture_refuses_seal_mismatch_without_explicit_smoke(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """封印と食い違ったまま走れる唯一の道は --smoke の明示 opt-in である."""
    broken = copy.deepcopy(sealed)
    broken["environment"]["ollama_version"] = "0.99.0"
    paper_repo = _paper_repo_with(broken, tmp_path / "paper")
    _patch_observers(driver, monkeypatch)

    ran: list[int] = []

    async def spy_capture(**_kwargs: Any) -> Any:
        ran.append(1)
        raise AssertionError("ここには来ない想定")

    monkeypatch.setattr(driver, "capture", spy_capture)

    argv = [
        "--capture",
        "--arm",
        "primary",
        "--paper-repo",
        str(paper_repo),
        "--bank",
        str(bank_path),
        "--k-contexts",
        "2",
        "--m-draws",
        "2",
        "--out-root",
        str(tmp_path / "out"),
    ]
    assert driver.main(argv) == 1
    assert ran == []
    # --smoke を明示すると capture まで進む (ここでは spy が止める)
    with pytest.raises(AssertionError, match="ここには来ない想定"):
        driver.main([*argv, "--smoke"])
    assert ran == [1]


def test_driver_provenance_records_its_own_identity(driver: Any) -> None:
    """Codex LOW-8: driver は封印の外にある。何が書いたかを sidecar に残す."""
    provenance = driver.driver_provenance()
    assert provenance["path"] == "paper02_run_arms.py"
    assert len(provenance["sha256"]) == 64
    actual = hashlib.sha256(_SCRIPT_PATH.read_bytes()).hexdigest()
    assert provenance["sha256"] == actual
    assert "git_head" in provenance
    assert "git_dirty" in provenance


def test_sealed_seal_check_is_invoked_and_can_fail(driver: Any, tmp_path: Path) -> None:
    """Codex HIGH-2: 封印検査器を複製せず呼ぶ。exit code をそのまま受ける."""
    paper_repo = tmp_path / "paper"
    scripts = paper_repo / "analysis" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "verify_seal.py").write_text(
        "import sys\nprint('[seal] FAIL synthetic')\nsys.exit(1)\n", encoding="utf-8"
    )
    ok = driver.run_sealed_seal_check(
        paper_repo=paper_repo,
        manifest_path=tmp_path / "m.json",
        verdict_path=tmp_path / "v.json",
        arm="primary",
    )
    assert ok == driver._SEAL_FAILED

    (scripts / "verify_seal.py").write_text(
        "print('[seal] OK synthetic')\n", encoding="utf-8"
    )
    assert (
        driver.run_sealed_seal_check(
            paper_repo=paper_repo,
            manifest_path=tmp_path / "m.json",
            verdict_path=tmp_path / "v.json",
            arm="primary",
        )
        == driver._SEAL_OK
    )


def test_sealed_seal_check_absent_checker_reports_not_run(
    driver: Any, tmp_path: Path
) -> None:
    """検査器が無いときに「通った」と言わない (code-reviewer H3).

    以前はここで ``True`` を返しており、``--paper-repo`` の打ち間違いや WSL からの
    実行で**封印検査が無言で消えて exit 0** になっていた。3 値にして
    「実行できなかった」を独立に表す。
    """
    outcome = driver.run_sealed_seal_check(
        paper_repo=tmp_path / "nowhere",
        manifest_path=tmp_path / "m.json",
        verdict_path=tmp_path / "v.json",
        arm="primary",
    )
    assert outcome == driver._SEAL_NOT_RUN
    assert outcome != driver._SEAL_OK


# --------------------------------------------------------------------------- #
# code-reviewer (Opus, 2026-09-14) の HIGH に対する回帰ケース
# --------------------------------------------------------------------------- #


@pytest.fixture
def sealed_scale_bundle(driver: Any, tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """**封印規模** (M=300 / K=8) の合成 bundle を作る.

    `sub_sealed_scale` を手で書き換えて封印規模を装うテストは、H4 の修正
    (記録された M/K から再計算して照合する) が正しく弾く。本物の規模で作る。
    合成 stub なので 0.2 秒で終わる。
    """
    rows = _bank_rows(k=8, m=300)
    bank_file = tmp_path / "sealed-bank.jsonl"
    bank_file.write_text(
        "".join(f"{driver.handoff.canonical_dumps(r)}\n" for r in rows),
        encoding="utf-8",
        newline="\n",
    )
    bank = driver.load_frozen_bank(bank_file)
    spec = {
        "environment": {
            "ollama_version": "0.32.12",
            "python": "3.11.15",
            "uv_lock_sha256": "a" * 64,
        },
        "context_bank": {
            "bank_checksum": bank.checksum,
            "context_ids": bank.context_ids,
        },
        "arms": {
            "primary": {
                "model": "llama3.1:8b",
                "model_digest": "4" * 64,
                "think": False,
            }
        },
    }
    rendered, _ = _capture(driver, spec, bank, m_draws=300)
    out = tmp_path / "sealed-primary"
    driver._write(out, rendered)
    assert json.loads(rendered["run-manifest.json"])["sub_sealed_scale"] is False
    return out, {"bank_file": bank_file, "spec": spec}


class _StubClientFactory(_StubChat):
    """``OllamaChatClient`` の差し替え。**クラス属性も持たせる** —

    ``main`` は ``OllamaChatClient.DEFAULT_ENDPOINT`` を argparse の default に
    使うので、単なる lambda に差し替えると argparse が壊れる。
    """

    DEFAULT_ENDPOINT = "http://127.0.0.1:11434"

    def __init__(self, **_kwargs: Any) -> None:
        super().__init__()


def _fake_seal_checker(paper_repo: Path, *, passes: bool) -> None:
    scripts = paper_repo / "analysis" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    body = (
        "print('[seal] OK synthetic')\n"
        if passes
        else "import sys\nprint('[seal] FAIL synthetic')\nsys.exit(1)\n"
    )
    (scripts / "verify_seal.py").write_text(body, encoding="utf-8")


def test_h3_unreachable_paper_repo_is_not_counted_as_passing(
    driver: Any, sealed_scale_bundle: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    """封印検査器に届かなかったことを「通った」に数えない (H3).

    以前は `--paper-repo` が存在しないと検査ブロックごと消え、**メッセージすら
    出ずに** exit 0 になっていた。WSL 側で verify を回す / パスを打ち間違える、で
    起きる。
    """
    out, _ = sealed_scale_bundle
    code = asyncio.run(
        driver.verify(out, arm="primary", paper_repo=tmp_path / "nowhere")
    )
    assert code == driver.VERIFY_FAIL
    # 落ちた bundle の verdict を緑の名前で残さない (M8)
    assert not (out / "run-verdict.json").exists()
    assert (out / "run-verdict.DEVIATION.json").exists()


def test_h3_positive_control_sealed_scale_bundle_can_pass(
    driver: Any, sealed_scale_bundle: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    """陽性対照: 封印検査が通れば封印規模 bundle は exit 0 になる."""
    out, _ = sealed_scale_bundle
    paper_repo = tmp_path / "paper-ok"
    _fake_seal_checker(paper_repo, passes=True)
    code = asyncio.run(driver.verify(out, arm="primary", paper_repo=paper_repo))
    assert code == driver.VERIFY_OK
    assert (out / "run-verdict.json").exists()


def test_h3_failing_seal_check_fails_a_sealed_scale_bundle(
    driver: Any, sealed_scale_bundle: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    out, _ = sealed_scale_bundle
    paper_repo = tmp_path / "paper-bad"
    _fake_seal_checker(paper_repo, passes=False)
    code = asyncio.run(driver.verify(out, arm="primary", paper_repo=paper_repo))
    assert code == driver.VERIFY_FAIL


def test_h4_sub_sealed_flag_cannot_swallow_a_seal_failure(
    driver: Any, sealed_scale_bundle: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    """`sub_sealed_scale` を 1 行足して封印検査の失敗を握り潰せない (H4).

    以前は判定対象の manifest 自身からこのフラグを読み、真なら `[verify] OK` /
    exit 0 だった。**記録された M/K から再計算して照合する**ことで閉じる。
    """
    out, _ = sealed_scale_bundle
    manifest_path = out / "run-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["sub_sealed_scale"] is False
    manifest["sub_sealed_scale"] = True  # 攻撃: 1 行で握り潰す
    manifest_path.write_text(
        driver.handoff.canonical_dumps(manifest) + "\n", encoding="utf-8", newline="\n"
    )

    paper_repo = tmp_path / "paper-bad"
    _fake_seal_checker(paper_repo, passes=False)
    code = asyncio.run(driver.verify(out, arm="primary", paper_repo=paper_repo))
    assert code == driver.VERIFY_FAIL


def test_h4_sub_sealed_bundle_never_exits_zero(
    driver: Any, sealed: dict[str, Any], bank_path: Path, tmp_path: Path
) -> None:
    """封印規模でない bundle は exit 0 にならない (H4).

    整合が取れていても「前向き結果である」とは読ませない。
    """
    out = tmp_path / "primary"
    _capture_to(driver, sealed, driver.load_frozen_bank(bank_path), out)
    paper_repo = tmp_path / "paper-ok"
    _fake_seal_checker(paper_repo, passes=True)
    code = asyncio.run(driver.verify(out, arm="primary", paper_repo=paper_repo))
    assert code == driver.VERIFY_SUB_SEALED
    assert code != driver.VERIFY_OK


class _FlakyChat(_StubChat):
    """最初の N 回だけ transport 失敗を出すスタブ."""

    def __init__(self, *, fail_times: int, message: str) -> None:
        super().__init__()
        self.fail_times = fail_times
        self.message = message
        self.attempts = 0

    async def chat(self, messages: Any, **kwargs: Any) -> Any:
        from erre_sandbox.inference.ollama_adapter import OllamaUnavailableError

        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise OllamaUnavailableError(self.message)
        return await super().chat(messages, **kwargs)


def test_h1_transport_failure_is_retried_not_fatal(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """transport 失敗 1 回で 2.5 時間が全損しない (H1).

    `run_bank_mloop` は `llm.chat` を try していないので、retry が無いと
    4,800 回中 1 回の timeout で traceback + 成果物ゼロになる。
    """
    monkeypatch.setattr(driver.asyncio, "sleep", _no_sleep)
    flaky = _FlakyChat(fail_times=2, message="Ollama /api/chat timeout after 300.0s")
    rendered, metrics = _capture(
        driver, sealed, driver.load_frozen_bank(bank_path), inner_chat=flaky
    )
    assert metrics["transport_retries"] == 2
    assert metrics["transport_retry_reasons"], "理由を残さない retry は記録でない"
    assert _manifest_of(rendered)["run"]["m_draws"] == 2


async def _no_sleep(_seconds: float) -> None:
    return None


def test_h1_content_failure_is_never_retried(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """内容の失敗は retry しない — 見た応答を捨てて引き直すのは応答の選択である.

    transport 失敗は「要求が答えられなかった」なので引き直しても estimand は
    汚れない。内容の失敗で引き直すと汚れる。この境界が retry の設計の核である。
    """
    from erre_sandbox.inference.ollama_adapter import OllamaUnavailableError

    monkeypatch.setattr(driver.asyncio, "sleep", _no_sleep)
    flaky = _FlakyChat(fail_times=1, message="Ollama /api/chat returned non-JSON")
    with pytest.raises(OllamaUnavailableError, match="non-JSON"):
        _capture(driver, sealed, driver.load_frozen_bank(bank_path), inner_chat=flaky)
    assert flaky.attempts == 1, "内容の失敗を引き直してはならない"


def test_h1_retries_are_bounded(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """retry は有界である (無限に粘って 5 時間を溶かさない)."""
    from erre_sandbox.inference.ollama_adapter import OllamaUnavailableError

    monkeypatch.setattr(driver.asyncio, "sleep", _no_sleep)
    flaky = _FlakyChat(fail_times=99, message="Ollama /api/chat unreachable")
    with pytest.raises(OllamaUnavailableError, match="unreachable"):
        _capture(driver, sealed, driver.load_frozen_bank(bank_path), inner_chat=flaky)
    assert flaky.attempts == driver._TRANSPORT_RETRIES + 1


def test_h1_partial_records_are_flushed_as_they_arrive(
    driver: Any, sealed: dict[str, Any], bank_path: Path, tmp_path: Path
) -> None:
    """応答は届くたび追記される — 途中で落ちても raw が 1 バイトも残らない事態を避ける.

    部分データは `_observed_m_draws` が完全なセルを要求するので採点できず、
    チェリーピックには使えない。
    """
    partial = tmp_path / "run_records.partial.jsonl"
    _capture(
        driver,
        sealed,
        driver.load_frozen_bank(bank_path),
        partial_path=partial,
    )
    lines = [
        json.loads(line)
        for line in partial.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 2 * 2 * 2  # 2 条件 × 2 context × 2 draws
    assert lines[0]["call_index"] == 1
    assert "content" in lines[0]


def test_h2_aborted_run_quarantines_its_raw_data(
    driver: Any, sealed: dict[str, Any], bank_path: Path, tmp_path: Path
) -> None:
    """実走後ガードが生データを道連れにしない (H2).

    版ドリフトは正しく停止するが、以前は 2.5 時間分の raw が診断材料ごと消えた。
    """

    async def moved(_endpoint: str) -> Any:
        return driver.OllamaObservation(
            version="0.33.0", digests=_observation(driver).digests
        )

    bank = driver.load_frozen_bank(bank_path)
    with pytest.raises(driver.CaptureAbortedError) as excinfo:
        _capture(driver, sealed, bank, reobserve=moved)
    # 例外が records を携えている = 呼び出し側が隔離保存できる
    assert len(excinfo.value.records) == 2 * 2 * 2

    out = tmp_path / "aborted"
    driver._write_quarantine(out, excinfo.value)
    assert (out / "run_records.quarantine.jsonl").exists()
    assert "版が変わった" in (out / "quarantine-reason.txt").read_text(encoding="utf-8")
    # **bundle と誤認されるものは書かない**
    assert not (out / "run-manifest.json").exists()
    assert not (out / "run_annotation.jsonl").exists()


def test_h5_attempts_are_appended_not_overwritten(driver: Any, tmp_path: Path) -> None:
    """試行の痕跡は append-only である (H5).

    落ちた後に走らせ直すのは自然な対応だが、成果物は上書きされるので最終 bundle は
    一発目と区別できなくなる。ここに残る行だけが「何回目か」を知っている。
    """
    attempts = tmp_path / "attempts.jsonl"
    driver._append_attempt(attempts, {"event": "start", "n": 1})
    driver._append_attempt(attempts, {"event": "aborted", "n": 1})
    driver._append_attempt(attempts, {"event": "start", "n": 2})
    rows = [
        json.loads(line)
        for line in attempts.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [r["event"] for r in rows] == ["start", "aborted", "start"]
    assert all("recorded_at" in r for r in rows)


# --------------------------------------------------------------------------- #
# MEDIUM への回帰ケース
# --------------------------------------------------------------------------- #


def test_m1_recorded_seed_is_load_bearing(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """採点は manifest が記録した seed を使う (M1).

    定数を使うと、封印の seed 照合は「記録の一致」しか示さず、解析が実際に何を
    使ったかとは独立になる。
    """
    out = tmp_path / "primary"
    _capture_to(driver, sealed, driver.load_frozen_bank(bank_path), out)
    manifest = json.loads((out / "run-manifest.json").read_text(encoding="utf-8"))
    recorded_seed = manifest["run"]["seed"]

    seen: list[int] = []
    original = driver.score_bank_annotation

    def spy(**kwargs: Any) -> Any:
        seen.append(kwargs["seed"])
        return original(**kwargs)

    monkeypatch.setattr(driver, "score_bank_annotation", spy)
    asyncio.run(driver.verify(out, arm="primary"))
    assert seen == [recorded_seed]


def test_m2_bank_checksum_is_rederived_from_the_bank_at_verify(
    driver: Any, sealed: dict[str, Any], bank_path: Path, tmp_path: Path
) -> None:
    """`--bank` を渡すと消費した凍結 bank を独立に突き合わせる (M2)."""
    out = tmp_path / "primary"
    _capture_to(driver, sealed, driver.load_frozen_bank(bank_path), out)

    # 陽性対照: 正しい bank なら通る (sub-sealed なので 2)
    code = asyncio.run(driver.verify(out, arm="primary", bank_path=bank_path))
    assert code == driver.VERIFY_SUB_SEALED

    # 別の bank を渡すと落ちる
    other = tmp_path / "other.jsonl"
    rows = _bank_rows(k=2, m=2)
    rows[0]["raw_response"] = json.dumps({**_PLAN, "thought": "tampered"})
    other.write_text(
        "".join(f"{driver.handoff.canonical_dumps(r)}\n" for r in rows),
        encoding="utf-8",
        newline="\n",
    )
    assert (
        asyncio.run(driver.verify(out, arm="primary", bank_path=other))
        == driver.VERIFY_FAIL
    )


def test_m5_capture_refuses_to_overwrite_without_force(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """空でない出力先へ黙って上書きしない (M5).

    smoke と本番の default 出力先が同じなので、古い run-verdict.json が残ると
    手で検査器へ渡したときに組み合わせがずれる。
    """
    paper_repo = _paper_repo_with(sealed, tmp_path / "paper")
    _patch_observers(driver, monkeypatch)
    out = tmp_path / "out"
    out.mkdir()
    (out / "run-verdict.json").write_text("{}", encoding="utf-8")

    argv = [
        "--capture",
        "--arm",
        "primary",
        "--paper-repo",
        str(paper_repo),
        "--bank",
        str(bank_path),
        "--k-contexts",
        "2",
        "--m-draws",
        "2",
        "--smoke",
        "--artifact-dir",
        str(out),
    ]
    assert driver.main(argv) == 1
    # --force を明示すれば進む (ここでは stub で実走を差し替える)
    monkeypatch.setattr(driver, "OllamaChatClient", _StubClientFactory)
    assert driver.main([*argv, "--force"]) == 0
    # 古い verdict は残らない
    assert not (out / "run-verdict.json").exists()


def test_m6_end_to_end_main_capture_then_verify(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**実走で実際に通る経路**にテストを当てる (M6).

    これまで `main --capture` の書き出しと `main --verify` 全体は一度も呼ばれて
    いなかった。5 時間後に初めて実行される行が未検査だった。
    """
    paper_repo = _paper_repo_with(sealed, tmp_path / "paper")
    _patch_observers(driver, monkeypatch)
    monkeypatch.setattr(driver, "OllamaChatClient", _StubClientFactory)
    out = tmp_path / "out"

    common = [
        "--arm",
        "primary",
        "--paper-repo",
        str(paper_repo),
        "--bank",
        str(bank_path),
        "--k-contexts",
        "2",
    ]
    assert (
        driver.main(
            [
                "--capture",
                *common,
                "--m-draws",
                "2",
                "--smoke",
                "--artifact-dir",
                str(out),
            ]
        )
        == 0
    )
    for name in (
        "run-manifest.json",
        "run_records.jsonl",
        "run_annotation.jsonl",
        "run-metrics.json",
        "attempts.jsonl",
    ):
        assert (out / name).exists(), name

    # 封印規模でない bundle なので exit 2 (前向き結果ではない)
    assert driver.main(["--verify", *common, "--artifact-dir", str(out)]) == 2
    assert (out / "run-verdict.json").exists()


def test_m7_preflight_result_is_recorded_in_the_sidecar(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """draw 0 の時点で何が分かっていたかを成果物に残す (M7)."""
    broken = copy.deepcopy(sealed)
    broken["environment"]["ollama_version"] = "0.99.0"
    paper_repo = _paper_repo_with(broken, tmp_path / "paper")
    _patch_observers(driver, monkeypatch)
    monkeypatch.setattr(driver, "OllamaChatClient", _StubClientFactory)
    out = tmp_path / "out"

    assert (
        driver.main(
            [
                "--capture",
                "--arm",
                "primary",
                "--paper-repo",
                str(paper_repo),
                "--bank",
                str(bank_path),
                "--k-contexts",
                "2",
                "--m-draws",
                "2",
                "--smoke",
                "--artifact-dir",
                str(out),
            ]
        )
        == 0
    )
    metrics = json.loads((out / "run-metrics.json").read_text(encoding="utf-8"))
    assert metrics["smoke"] is True
    assert metrics["requested_m_draws"] == 2
    assert any("ollama_version" in p for p in metrics["preflight_problems"])
    assert metrics["driver_provenance"]["path"] == "paper02_run_arms.py"


def test_l2_cost_ceiling_is_enforced_live(driver: Any) -> None:
    """呼び出し上限は live に効く (事後集計では発火しえない — L2)."""
    spy = driver.ThinkAndModelSpy(inner=_StubChat(), call_cap=1)
    asyncio.run(spy.chat([], sampling=None, think=False))
    with pytest.raises(RuntimeError, match="呼び出し上限"):
        asyncio.run(spy.chat([], sampling=None, think=False))


def test_l1_unreadable_bundle_fails_cleanly(driver: Any, tmp_path: Path) -> None:
    """壊れた bundle は traceback でなく `[verify] FAIL` で落ちる (L1)."""
    out = tmp_path / "broken"
    out.mkdir()
    (out / "run-manifest.json").write_text("{not json", encoding="utf-8")
    assert asyncio.run(driver.verify(out, arm="primary")) == driver.VERIFY_FAIL


def test_l4_malformed_tags_response_is_refused(driver: Any) -> None:
    """`/api/tags` が digest を欠いたら traceback でなく明示的に停止する (L4)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.32.12"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "llama3.1:8b"}]})
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="http://stub", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(SystemExit, match="name/digest"):
        asyncio.run(driver.observe_ollama("http://stub", client=client))
    asyncio.run(client.aclose())


def test_h4_flag_that_understates_the_scale_also_fails(
    driver: Any, sealed: dict[str, Any], bank_path: Path, tmp_path: Path
) -> None:
    """自己申告と再計算の食い違いは、**どちら向きでも**落ちる (H4).

    逆向き (封印規模でないのに「封印規模だ」と名乗る) だけを見ていると、
    照合そのものを外しても気づけない。
    """
    out = tmp_path / "primary"
    _capture_to(driver, sealed, driver.load_frozen_bank(bank_path), out)
    manifest_path = out / "run-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["sub_sealed_scale"] is True  # M=2 なので本来は真
    manifest["sub_sealed_scale"] = False  # 攻撃: 封印規模だと名乗る
    manifest_path.write_text(
        driver.handoff.canonical_dumps(manifest) + "\n", encoding="utf-8", newline="\n"
    )

    paper_repo = tmp_path / "paper-ok"
    _fake_seal_checker(paper_repo, passes=True)
    code = asyncio.run(driver.verify(out, arm="primary", paper_repo=paper_repo))
    # 照合が無ければ SUB_SEALED (2) で済んでしまう。照合があるので FAIL (1)。
    assert code == driver.VERIFY_FAIL


def test_m1_a_non_default_seed_is_the_one_the_scorer_uses(
    driver: Any,
    sealed: dict[str, Any],
    bank_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """既定値と**違う** seed で記録すると、採点もその seed を使う (M1).

    既定値と一致する seed だけで確かめると、定数へ退行しても気づけない。
    """
    out = tmp_path / "primary"
    rendered, _ = _capture(
        driver, sealed, driver.load_frozen_bank(bank_path), seed=12345
    )
    driver._write(out, rendered)
    assert json.loads(rendered["run-manifest.json"])["run"]["seed"] == 12345
    assert driver.POWER_SEED_DEFAULT != 12345

    seen: list[int] = []
    original = driver.score_bank_annotation

    def spy(**kwargs: Any) -> Any:
        seen.append(kwargs["seed"])
        return original(**kwargs)

    monkeypatch.setattr(driver, "score_bank_annotation", spy)
    asyncio.run(driver.verify(out, arm="primary"))
    assert seen == [12345]


def test_m1_missing_seed_is_an_error_not_a_default(
    driver: Any, sealed: dict[str, Any], bank_path: Path, tmp_path: Path
) -> None:
    """seed が無い manifest は既定値で採点せず落ちる."""
    out = tmp_path / "primary"
    _capture_to(driver, sealed, driver.load_frozen_bank(bank_path), out)
    manifest_path = out / "run-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["run"]["seed"]
    manifest_path.write_text(
        driver.handoff.canonical_dumps(manifest) + "\n", encoding="utf-8", newline="\n"
    )
    assert asyncio.run(driver.verify(out, arm="primary")) == driver.VERIFY_FAIL

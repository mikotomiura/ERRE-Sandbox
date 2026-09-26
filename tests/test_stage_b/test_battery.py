"""battery ドラフト (未凍結) の非漏洩・同型・カウンターバランス・配置順の機械検査."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from scripts import stage_b_battery as mod
from scripts.stage_b_scorer import STREAM_A, STREAM_B, signature_text

if TYPE_CHECKING:
    import pytest


def test_draft_passes_all_checks() -> None:
    report = mod.battery_report()
    assert report["frozen"] is False
    for key in ("non_leakage", "isomorphism", "counterbalance", "placement_order"):
        assert report[key] == [], key


def test_probe_signatures_are_held_out_but_share_rule_feature() -> None:
    dev = set(mod.dev_signatures())
    probes = mod.probe_signatures()
    assert len(probes) == len(set(probes)) == 6
    assert not dev & set(probes)
    dev_weather = {s[0] for s in dev}
    assert all(s[0] in dev_weather for s in probes)


def test_alignment_comes_from_rule_tables() -> None:
    for probe, sig in mod.probes():
        assert probe.g_a == mod.rule(STREAM_A)[sig[0]]
        assert probe.g_b == mod.rule(STREAM_B)[sig[0]]
        assert probe.g_b == mod.SIGMA[probe.g_a]


def test_outcomes_follow_rule_table_only() -> None:
    for stream in (STREAM_A, STREAM_B):
        table = mod.rule(stream)
        for ep in mod.dev_stream(stream):
            assert ep.success == (ep.action == table[ep.signature[0]])


def test_probe_prompt_names_situation_but_no_key() -> None:
    probe, sig = mod.probes()[0]
    text = mod.render_probe_prompt(probe, sig)
    assert all(v in text for v in sig)
    assert probe.probe_id not in text
    assert f"{signature_text(sig)} →" not in text


def test_leaked_probe_signature_in_state_is_detected() -> None:
    probe_sig = mod.probe_signatures()[0]
    leak = mod.SkillEntry(probe_sig, ("read_book",), 1, 0, ("ep999",))
    states = {"dev_A": [*mod.skill_state(mod.dev_stream(STREAM_A)), leak]}
    assert mod.check_non_leakage(states)


def test_stream_id_in_state_is_detected() -> None:
    ents = mod.skill_state(mod.dev_stream(STREAM_A))
    tagged = [replace(ents[0], actions=("stream_a",))]
    assert mod.check_non_leakage({"dev_A": tagged})


def test_label_keyed_placement_is_detected() -> None:
    """DA-12: 配置順を行動 label で決めると stream 間で位置がずれる."""

    def by_label(entries):
        return sorted(entries, key=lambda e: (signature_text(e.signature), e.actions))

    assert mod.check_placement_order(by_label)


def test_insertion_order_placement_is_isomorphic() -> None:
    assert mod.check_placement_order() == []


def test_broken_mirror_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    real = mod.dev_stream

    def skewed(stream: str) -> list[mod.Episode]:
        eps = real(stream)
        if stream == STREAM_B:
            eps[0] = replace(eps[0], success=not eps[0].success)
        return eps

    monkeypatch.setattr(mod, "dev_stream", skewed)
    assert mod.check_isomorphism()


def test_uncounterbalanced_options_are_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = mod.probes()

    def a_first() -> list:
        return [(replace(p, omega=(p.g_a, p.g_b, *p.omega[2:])), s) for p, s in real]

    monkeypatch.setattr(mod, "probes", a_first)
    assert mod.check_counterbalance()


def test_omega_is_sigma_closed_and_labels_equal_length() -> None:
    for probe, _ in mod.probes():
        assert {mod.SIGMA[o] for o in probe.omega} == set(probe.omega)
    assert len({len(a) for a in mod.ACTIONS}) == 1


def test_lever_state_covers_dev_signatures_only() -> None:
    for stream in (STREAM_A, STREAM_B):
        sigs = {e.signature for e in mod.lever_state(stream)}
        assert sigs == set(mod.dev_signatures())

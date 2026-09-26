"""developmental substrate Stage B — battery ドラフトと非漏洩・同型の機械検査 (B1、未凍結).

prereg §2.1〜§2.3 の構成要件を満たす battery の **ドラフト** を定義し、それを機械的に検査する。
battery (probe bank Q・規則表・Ω_q・g_A/g_B・renderer) の凍結は B2 実行許可の前 (prereg §4
one-shot calibration) であり、本モジュールの値は凍結値ではない。設計メモ =
``experiments/20260926-developmental-substrate-stage-b/battery-design.md``。

構成:

* 状況 = 3 つの離散特徴 (weather × time × company) の signature。規則を担う特徴 f = weather。
* 行動 = 閉じた primitive 6 種。A / B の規則表は label 置換 σ (3 つの互換) で鏡像。
  label は全て 9 文字 (σ の下で文の長さが変わらない)。
* 発達 signature 12 個 / held-out probe signature 6 個 (互いに素、probe は f を共有するが
  signature 全体は新しい)。g_X(q) = 規則表 X の weather → 行動。
* Skill エントリの prompt 内配置順は signature の正準表記 → 初出 episode 順で決め、行動 label に
  依存させない (DA-12、lost-in-the-middle の位置効果を stream 間で同型にする)。
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import TYPE_CHECKING, Final

from scripts.stage_b_scorer import (
    STREAM_A,
    STREAM_B,
    Probe,
    Snapshot,
    StageBData,
    integrity_violations,
    signature_text,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

WEATHER: Final[tuple[str, ...]] = ("rain", "clear", "wind")
TIME: Final[tuple[str, ...]] = ("dawn", "noon", "dusk")
COMPANY: Final[tuple[str, ...]] = ("alone", "paired")
ACTIONS: Final[tuple[str, ...]] = (
    "read_book",
    "sit_quiet",
    "walk_path",
    "talk_peer",
    "tend_moss",
    "rest_eyes",
)
# 規則表 A: weather → 成功する行動。B = σ ∘ A。
RULE_A: Final[dict[str, str]] = {
    "rain": "read_book",
    "clear": "walk_path",
    "wind": "tend_moss",
}
SIGMA: Final[dict[str, str]] = {
    "read_book": "sit_quiet",
    "sit_quiet": "read_book",
    "walk_path": "talk_peer",
    "talk_peer": "walk_path",
    "tend_moss": "rest_eyes",
    "rest_eyes": "tend_moss",
}
# held-out: 各 weather で (time, company) の 2 組を probe に回す
HELD_OUT: Final[dict[str, tuple[tuple[str, str], ...]]] = {
    "rain": (("dusk", "paired"), ("noon", "alone")),
    "clear": (("dawn", "paired"), ("dusk", "alone")),
    "wind": (("noon", "paired"), ("dawn", "alone")),
}
ATTEMPTS_PER_SIGNATURE: Final[int] = 3

Signature = tuple[str, str, str]


def rule(stream: str) -> dict[str, str]:
    if stream == STREAM_A:
        return dict(RULE_A)
    if stream == STREAM_B:
        return {w: SIGMA[a] for w, a in RULE_A.items()}
    msg = f"unknown stream {stream!r}"
    raise ValueError(msg)


def all_signatures() -> list[Signature]:
    return [(w, t, c) for w, t, c in product(WEATHER, TIME, COMPANY)]


def probe_signatures() -> list[Signature]:
    return [(w, t, c) for w in WEATHER for t, c in HELD_OUT[w]]


def dev_signatures() -> list[Signature]:
    held = set(probe_signatures())
    return [s for s in all_signatures() if s not in held]


# ------------------------------------------------------------------ probes


def probes() -> list[tuple[Probe, Signature]]:
    """Ω_q = {g_A, g_B, x, σ(x)} (x = 次の weather の A 規則行動)。Ω_q は σ で閉じる.

    g_A 先頭と g_B 先頭を交互にする (カウンターバランス)。distractor も同じ向きで並べる。
    """
    a, b = rule(STREAM_A), rule(STREAM_B)
    out: list[tuple[Probe, Signature]] = []
    for n, sig in enumerate(probe_signatures()):
        w = sig[0]
        x = RULE_A[WEATHER[(WEATHER.index(w) + 1) % len(WEATHER)]]
        if n % 2 == 0:
            head, distract = [a[w], b[w]], [x, SIGMA[x]]
        else:
            head, distract = [b[w], a[w]], [SIGMA[x], x]
        probe = Probe(
            probe_id=f"q{n:02d}",
            omega=(*head, *distract),
            g_a=a[w],
            g_b=b[w],
        )
        out.append((probe, sig))
    return out


def render_probe_prompt(probe: Probe, sig: Signature) -> str:
    options = "、".join(probe.omega)
    return (
        f"状況: 天候={sig[0]}、時刻={sig[1]}、同伴={sig[2]}。\n"
        f"次の行動から 1 つだけ選び、行動名だけを答えよ: {options}"
    )


# ---------------------------------------------------------------- episodes


@dataclass(frozen=True)
class Episode:
    ep_id: str
    signature: Signature
    action: str
    success: bool


def attempt_schedule() -> list[tuple[Signature, str]]:
    """stream A の試行列 (固定)。各 dev signature で 規則行動・σ 行動・他規則行動 を順に試す."""
    out: list[tuple[Signature, str]] = []
    for sig in dev_signatures():
        w = sig[0]
        other = RULE_A[WEATHER[(WEATHER.index(w) + 1) % len(WEATHER)]]
        out.extend((sig, act) for act in (RULE_A[w], SIGMA[RULE_A[w]], other))
    return out


def dev_stream(stream: str) -> list[Episode]:
    """B の試行列は A の σ 像。結果は規則表で決まる (LLM・judge が決めない)."""
    table = rule(stream)
    mapper: Callable[[str], str] = (
        (lambda x: x) if stream == STREAM_A else (lambda x: SIGMA[x])
    )
    return [
        Episode(f"ep{n:03d}", sig, mapper(act), mapper(act) == table[sig[0]])
        for n, (sig, act) in enumerate(attempt_schedule())
    ]


def render_episode(ep: Episode) -> str:
    result = "成功" if ep.success else "失敗"
    return f"[{ep.ep_id}] {signature_text(ep.signature)} で {ep.action} → {result}"


# ------------------------------------------------------------ Skill state


@dataclass(frozen=True)
class SkillEntry:
    signature: Signature
    actions: tuple[str, ...]
    successes: int
    failures: int
    provenance: tuple[str, ...]


def skill_state(episodes: Sequence[Episode]) -> list[SkillEntry]:
    """発達中に出現した signature ごと・行動ごとのエントリ (ドラフト。昇格則は B3 の実装 ADR)."""
    acc: dict[tuple[Signature, str], list[Episode]] = {}
    for ep in episodes:
        acc.setdefault((ep.signature, ep.action), []).append(ep)
    entries = [
        SkillEntry(
            signature=sig,
            actions=(act,),
            successes=sum(e.success for e in eps),
            failures=sum(not e.success for e in eps),
            provenance=tuple(e.ep_id for e in eps),
        )
        for (sig, act), eps in acc.items()
    ]
    return order_entries(entries)


def order_entries(entries: Sequence[SkillEntry]) -> list[SkillEntry]:
    """DA-12: 配置順は signature の正準表記 → 初出 episode。行動 label を鍵にしない."""
    return sorted(entries, key=lambda e: (signature_text(e.signature), e.provenance[0]))


def lever_state(stream: str) -> list[SkillEntry]:
    """B2 lever の人手 Skill ドラフト: 発達 signature に対する規則として書く (prereg §2.2)."""
    table = rule(stream)
    entries = [
        SkillEntry(sig, (table[sig[0]],), 3, 0, (f"lever{n:03d}",))
        for n, sig in enumerate(dev_signatures())
    ]
    return order_entries(entries)


def render_state(entries: Sequence[SkillEntry]) -> str:
    return "\n".join(
        f"条件: {signature_text(e.signature)} → 行動: {' > '.join(e.actions)}"
        f" (成功 {e.successes} / 失敗 {e.failures})"
        for e in entries
    )


# ----------------------------------------------------------------- checks


def swap_text(text: str) -> str:
    """σ を文字列に適用 (label は互いに部分文字列にならない 9 文字)."""
    out = []
    i = 0
    while i < len(text):
        for label, image in SIGMA.items():
            if text.startswith(label, i):
                out.append(image)
                i += len(label)
                break
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def check_non_leakage(
    states: Mapping[str, Sequence[SkillEntry]] | None = None,
) -> list[str]:
    """prereg §2.2 を scorer と同じ integrity 検査で (状態 + probe prompt)."""
    problems: list[str] = []
    pairs = probes()
    probe_sigs = {p.probe_id: sig for p, sig in pairs}
    if set(dev_signatures()) & set(probe_sigs.values()):
        problems.append("probe signature appears in development")
    if len(set(probe_sigs.values())) != len(pairs):
        problems.append("probe signatures are not distinct")
    if states is None:
        states = {
            "dev_A": skill_state(dev_stream(STREAM_A)),
            "dev_B": skill_state(dev_stream(STREAM_B)),
            "lever_A": lever_state(STREAM_A),
            "lever_B": lever_state(STREAM_B),
        }
    data = StageBData(
        probes=tuple(p for p, _ in pairs),
        probe_signatures=probe_sigs,
        dev_signatures=frozenset(dev_signatures()),
        di=(),
        di_ablation=(),
        ci=(),
        snapshots=tuple(
            Snapshot(
                ind_id=name,
                preconditions=tuple(e.signature for e in ents),
                text=render_state(ents),
            )
            for name, ents in states.items()
        ),
        probe_prompts=tuple(render_probe_prompt(p, s) for p, s in pairs),
    )
    problems.extend(integrity_violations(data))
    return problems


def check_isomorphism() -> list[str]:
    """prereg §2.3: A と B は σ による label 置換で一致し、episode 数・順序・長さが同じ."""
    problems: list[str] = []
    ea, eb = dev_stream(STREAM_A), dev_stream(STREAM_B)
    if len(ea) != len(eb):
        problems.append("episode counts differ")
    for x, y in zip(ea, eb, strict=False):
        if (x.ep_id, x.signature, x.success) != (y.ep_id, y.signature, y.success):
            problems.append(f"{x.ep_id}: structure differs")
        if SIGMA[x.action] != y.action:
            problems.append(f"{x.ep_id}: B action is not σ(A action)")
        ra, rb = render_episode(x), render_episode(y)
        if len(ra) != len(rb) or swap_text(ra) != rb:
            problems.append(f"{x.ep_id}: rendered text is not σ-isomorphic")
    if {a for a in ACTIONS} != set(SIGMA) or any(SIGMA[SIGMA[a]] != a for a in SIGMA):
        problems.append("σ is not an involution on ACTIONS")
    if len({len(a) for a in ACTIONS}) != 1:
        problems.append("action labels differ in length")
    return problems


def check_counterbalance() -> list[str]:
    """g_A 先頭と g_B 先頭の probe を同数に、Ω_q を σ で閉じる (prereg §2.3)."""
    problems = [
        f"{p.probe_id}: Ω_q is not closed under σ"
        for p, _ in probes()
        if {SIGMA[o] for o in p.omega} != set(p.omega)
    ]
    heads = [p.omega[0] for p, _ in probes()]
    first_a = sum(h == p.g_a for h, (p, _) in zip(heads, probes(), strict=True))
    first_b = sum(h == p.g_b for h, (p, _) in zip(heads, probes(), strict=True))
    if first_a != first_b:
        problems.append(f"g_A first {first_a} != g_B first {first_b}")
    return problems


def check_placement_order(
    order: Callable[[Sequence[SkillEntry]], list[SkillEntry]] = order_entries,
) -> list[str]:
    """DA-12: Skill エントリの配置順が stream 間で同型 (σ 像の配置 = 配置の σ 像)."""
    problems: list[str] = []
    for make in (
        lambda s: skill_state(dev_stream(s)),
        lambda s: lever_state(s),
    ):
        ents_a = order(make(STREAM_A))
        ents_b = order(make(STREAM_B))
        sig_a = [(e.signature, e.provenance) for e in ents_a]
        sig_b = [(e.signature, e.provenance) for e in ents_b]
        if sig_a != sig_b:
            problems.append("entry placement order differs between streams")
        if swap_text(render_state(ents_a)) != render_state(ents_b):
            problems.append("rendered state is not σ-isomorphic")
    return problems


def battery_report() -> dict[str, object]:
    return {
        "frozen": False,
        "n_dev_signatures": len(dev_signatures()),
        "n_probes": len(probes()),
        "n_episodes_per_stream": len(dev_stream(STREAM_A)),
        "non_leakage": check_non_leakage(),
        "isomorphism": check_isomorphism(),
        "counterbalance": check_counterbalance(),
        "placement_order": check_placement_order(),
    }

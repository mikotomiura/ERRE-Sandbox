"""候補 G (汎化 probe) の事前登録 — battery・曝露・aggregator・layout・renderer と機械検査.

事前登録 = ``experiments/20261001-generalization-probe-pilot/prereg.md``。
設計の正本 = ``.steering/20261001-integrated-divergence-scoping/design-final.md`` §5 (FROZEN) と
``.steering/20261001-generalization-probe-prereg/design-final.md``。

世界 (prereg §2):

* 状況 = 生き物 (key) × 場所 (2 値) × 同伴 (2 値)。潜在 = 生き物の分類 (bird / fish / insect)。
  分類名は本走の prompt に出さない。
* arm の規則は分類 → 行動。``A`` = 正準の対応、``A_rot`` = A ∘ next (bird→fish→insect→bird)、
  ``B`` = σ ∘ A、``B_rot`` = σ ∘ A_rot。族 = {A, A_rot}・{B, B_rot}。
* dev の状況 12 = 場所 × 同伴の 4 組 × 3 分類。各 (組, 分類) にちょうど 1 つの dev key。
* probe は 8 つ組 × 3 = 24。つ組 j は組 j mod 4 を共有し、分類ごとに 1 つの probe key を持つ。
  probe key は dev にも状態にも出ない。
* 曝露: 環境が各 dev 状況で族の 3 行動を各 3 回試した観察 (状況・行動・成否) を、族で共通の固定 schedule で
  与える。aggregator は成功だけを固定の文言の行に記録する。研究者は規則を書かない。

選択肢 Ω (prereg §2.3、Codex HIGH-1): 族の 3 label (分類に依らない)。表示順は族の正準順を (r + j) mod 3 だけ
巡回し、つ組の 3 probe と族内の 2 arm で共有する。したがって、つ組の 3 probe の prompt は probe key だけが違う
(``check_triple_prompts_differ_only_in_key``)。probe key に依らない方策は C の期待値が厳密に 0 になる。

単位 (prereg §2.5): (族 f, つ組 j, replicate r)。単位ごとに状態の行順を引き、decoding seed は族内の 2 arm で共有、
単位の間では共有しない。R が 3 の倍数なら、各 (族, つ組) で各 label が各表示位置に同数回来る。
probe key の選定 (``generalization_probe_key_selection.py``) は、本走と別の行順 (``selection_entry_order``) を使う。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Final

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

# ---------------------------------------------------------------- 語彙 (凍結)

CLASSES: Final[tuple[str, ...]] = ("bird", "fish", "insect")
# dev key: DEV_KEYS[c][i] は組 i (COMBOS[i]) の dev 状況の key
DEV_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "bird": ("sparrow", "heron", "pigeon", "magpie"),
    "fish": ("trout", "carp", "herring", "sardine"),
    "insect": ("beetle", "hornet", "locust", "mosquito"),
}
# probe key: PROBE_KEYS[c][j] はつ組 j の分類 c の key。pool から、字面の写し方の fixture を釣り合わせる
# 決定的な探索で選んだ (scripts/generalization_probe_key_selection.py、選定用の行順・seed 20261001。
# モデルの出力は見ていない)
PROBE_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "bird": (
        "falcon",
        "ostrich",
        "hawk",
        "stork",
        "canary",
        "penguin",
        "eagle",
        "robin",
    ),
    "fish": (
        "halibut",
        "salmon",
        "guppy",
        "marlin",
        "tuna",
        "barracuda",
        "anchovy",
        "minnow",
    ),
    "insect": (
        "mantis",
        "cicada",
        "flea",
        "weevil",
        "midge",
        "earwig",
        "wasp",
        "aphid",
    ),
}
PLACES: Final[tuple[str, ...]] = ("library", "workshop")
COMPANY: Final[tuple[str, ...]] = ("solo", "pair")
COMBOS: Final[tuple[tuple[str, str], ...]] = tuple(
    (p, c) for p in PLACES for c in COMPANY
)

# 行動 label (新語彙・分類に中立)。族 A は ACTIONS_A、族 B は σ 像の ACTIONS_B を使う
ACTIONS_A: Final[tuple[str, ...]] = ("sort_cards", "fold_linen", "stack_cups")
ACTIONS_B: Final[tuple[str, ...]] = ("wind_clock", "count_keys", "tidy_shelf")
ACTIONS: Final[tuple[str, ...]] = (*ACTIONS_A, *ACTIONS_B)
SIGMA: Final[dict[str, str]] = {
    **dict(zip(ACTIONS_A, ACTIONS_B, strict=True)),
    **dict(zip(ACTIONS_B, ACTIONS_A, strict=True)),
}

ARM_A: Final[str] = "A"
ARM_A_ROT: Final[str] = "A_rot"
ARM_B: Final[str] = "B"
ARM_B_ROT: Final[str] = "B_rot"
LEVER_ARMS: Final[tuple[str, ...]] = (ARM_A, ARM_A_ROT, ARM_B, ARM_B_ROT)
FAMILIES: Final[tuple[tuple[str, str], ...]] = ((ARM_A, ARM_A_ROT), (ARM_B, ARM_B_ROT))
FOIL: Final[dict[str, str]] = {
    ARM_A: ARM_A_ROT,
    ARM_A_ROT: ARM_A,
    ARM_B: ARM_B_ROT,
    ARM_B_ROT: ARM_B,
}
ARM_FAMILY: Final[dict[str, int]] = {
    a: fi for fi, fam in enumerate(FAMILIES) for a in fam
}

N_TRIPLES: Final[int] = 8
N_POSITIONS: Final[int] = 3  # Ω = 族の 3 label
TRIALS_PER_ACTION: Final[int] = 3  # 曝露: 各 dev 状況で各行動を 3 回試す

# ---- 凍結する実行条件 (v2 と同じ着座。prereg §4)
MODEL: Final[str] = "qwen3:8b"
THINK: Final[bool] = False
TEMPERATURE: Final[float] = 0.7
TOP_P: Final[float] = 0.8
REPEAT_PENALTY: Final[float] = 1.0
NUM_CTX: Final[int] = 4096
NUM_PREDICT: Final[int] = 32
CHAT_TEMPLATE_OVERHEAD: Final[int] = 64
MAX_PROMPT_BYTES: Final[int] = 3000  # token 数 ≤ UTF-8 byte 数 (byte-level BPE)

SEED_BASE: Final[int] = 20261001
LAYOUT_SEED: Final[int] = 20261001
SELECTION_LAYOUT_SEED: Final[int] = (
    20261002  # probe key の選定だけに使う行順 (本走と別、Codex HIGH-4)
)
R_MAX: Final[int] = 24  # 本走の r は [0, R_MAX)
PILOT_R0: Final[int] = 50  # null pilot の r は [PILOT_R0, PILOT_R0 + PILOT_R)
PILOT_R: Final[int] = 6  # 表示の回転 (r + j) mod 3 の各層に 2 単位 (Codex MEDIUM-7)
KNOW_K: Final[int] = 3  # 知識確認の試行数 (正答の位置を 3 位置で一巡させる)
# seed の名前空間 g (prereg §2.5): 本走の族 A / 族 B、pilot の masked 族 A / B、知識確認
SEED_NS: Final[dict[str, int]] = {
    "fam0": 0,
    "fam1": 1,
    "pilot_fam0": 3,
    "pilot_fam1": 4,
    "know": 6,
}

SYSTEM_PROMPT: Final[str] = (
    "あなたは与えられた状況で、示された行動の中から 1 つを選ぶ。"
)
STATE_HEADER: Final[str] = "これまでの経験の記録:"
MASK: Final[str] = "不明"  # null pilot の masked 状態で key の欄に置く語
KNOW_SYSTEM_PROMPT: Final[str] = (
    "あなたは与えられた生き物の分類を、示された選択肢から 1 つ選ぶ。"
)
KEY_PLACEHOLDER: Final[str] = "<KEY>"


def next_class(c: str) -> str:
    return CLASSES[(CLASSES.index(c) + 1) % len(CLASSES)]


def rule(arm: str) -> dict[str, str]:
    """arm の規則表 分類 → 行動."""
    if arm == ARM_A:
        return dict(zip(CLASSES, ACTIONS_A, strict=True))
    if arm == ARM_A_ROT:
        base = rule(ARM_A)
        return {c: base[next_class(c)] for c in CLASSES}
    if arm == ARM_B:
        return {c: SIGMA[a] for c, a in rule(ARM_A).items()}
    if arm == ARM_B_ROT:
        return {c: SIGMA[a] for c, a in rule(ARM_A_ROT).items()}
    msg = f"arm {arm!r} has no rule table"
    raise ValueError(msg)


def family_actions(fi: int) -> tuple[str, ...]:
    """族 fi の 3 label の正準順 (= Ω の正準順)."""
    return ACTIONS_A if fi == 0 else ACTIONS_B


# ------------------------------------------------------------------ 状況


@dataclass(frozen=True)
class Situation:
    key: str
    place: str
    company: str

    @property
    def latent(self) -> str:
        return key_class(self.key)


def key_class(key: str) -> str:
    for c in CLASSES:
        if key in DEV_KEYS[c] or key in PROBE_KEYS[c]:
            return c
    msg = f"unknown key {key!r}"
    raise KeyError(msg)


@lru_cache(maxsize=1)
def dev_situations() -> tuple[Situation, ...]:
    """dev の状況 12 (正準順 = 組 i, 分類 c の順)."""
    return tuple(
        Situation(DEV_KEYS[c][i], *COMBOS[i])
        for i in range(len(COMBOS))
        for c in CLASSES
    )


@dataclass(frozen=True)
class Probe:
    """held-out probe: つ組 j・分類 c。4 arm が指す選択肢 (相異なる)."""

    probe_id: str
    index: int  # 0..23 (= 3j + 分類番号)
    triple: int
    situation: Situation
    pointed: Mapping[str, str]  # arm → その arm の規則が指す選択肢


@lru_cache(maxsize=1)
def probes() -> tuple[Probe, ...]:
    out = []
    for j in range(N_TRIPLES):
        place, company = COMBOS[j % len(COMBOS)]
        for ci, c in enumerate(CLASSES):
            sit = Situation(PROBE_KEYS[c][j], place, company)
            pointed = {a: rule(a)[c] for a in LEVER_ARMS}
            idx = 3 * j + ci
            out.append(Probe(f"q{idx:02d}", idx, j, sit, pointed))
    return tuple(out)


def triple_probes(j: int) -> tuple[Probe, ...]:
    return tuple(p for p in probes() if p.triple == j)


# ------------------------------------------------------- 曝露と aggregator


@dataclass(frozen=True)
class Observation:
    situation: Situation
    action: str
    success: bool


def exposure_schedule(fi: int) -> tuple[tuple[Situation, str], ...]:
    """族 fi の固定の試行 schedule (族内の 2 arm で共通): dev 状況ごとに族の 3 行動を各 TRIALS_PER_ACTION 回."""
    return tuple(
        (sit, act)
        for sit in dev_situations()
        for act in family_actions(fi)
        for _ in range(TRIALS_PER_ACTION)
    )


def observe(arm: str) -> tuple[Observation, ...]:
    """環境 (arm の世界の規則) が試行に成否を付けた観察列."""
    table = rule(arm)
    return tuple(
        Observation(sit, act, act == table[sit.latent])
        for sit, act in exposure_schedule(ARM_FAMILY[arm])
    )


def aggregate(observations: Iterable[Observation]) -> dict[Situation, tuple[str, int]]:
    """決定的な aggregator: (状況, 行動) ごとに数え、失敗の無い成功だけを記録する. 状況 → (行動, 成功数)."""
    succ: Counter[tuple[Situation, str]] = Counter()
    fail: Counter[tuple[Situation, str]] = Counter()
    for ob in observations:
        (succ if ob.success else fail)[(ob.situation, ob.action)] += 1
    out: dict[Situation, tuple[str, int]] = {}
    for (sit, act), n in succ.items():
        if fail[(sit, act)] == 0:
            if sit in out:
                msg = f"two success rows for {sit}"
                raise ValueError(msg)
            out[sit] = (act, n)
    return out


@lru_cache(maxsize=8)
def state_table(arm: str) -> dict[Situation, tuple[str, int]]:
    return aggregate(observe(arm))


# ------------------------------------------------------------------ layout


@dataclass(frozen=True)
class Unit:
    family: int
    triple: int
    replicate: int


def units(r_count: int) -> tuple[Unit, ...]:
    return tuple(
        Unit(fi, j, r)
        for r in range(r_count)
        for fi in range(len(FAMILIES))
        for j in range(N_TRIPLES)
    )


def _permutation(seed: int, fi: int, j: int, r: int) -> tuple[Situation, ...]:
    devs = dev_situations()
    perm = np.random.default_rng([seed, fi, j, r]).permutation(len(devs))
    return tuple(devs[int(i)] for i in perm)


@lru_cache(maxsize=4096)
def entry_order(fi: int, j: int, r: int) -> tuple[Situation, ...]:
    """本走 / pilot の単位 (fi, j, r) の状態の行順 (族内の 2 arm と、つ組の 3 probe で共有)."""
    return _permutation(LAYOUT_SEED, fi, j, r)


@lru_cache(maxsize=4096)
def selection_entry_order(fi: int, j: int, r: int) -> tuple[Situation, ...]:
    """probe key の選定だけに使う行順 (本走と別の seed。本走の行順を選定に使わない)."""
    return _permutation(SELECTION_LAYOUT_SEED, fi, j, r)


def option_order(fi: int, j: int, r: int) -> tuple[str, ...]:
    """Ω の表示順 = 族の正準順を (r + j) mod 3 だけ巡回 (つ組の 3 probe・族内の 2 arm で共有、分類に依らない)."""
    om = family_actions(fi)
    shift = (r + j) % N_POSITIONS
    return om[shift:] + om[:shift]


def sample_seed(namespace: str, r: int, slot: int, k: int) -> int:
    """decoding seed。namespace が違えば交わらない.

    lever / masked の腕の slot はつ組番号 j (prompt_slot): 族内の 2 arm とつ組の 3 probe で seed を共有する
    (Codex 2 回目 HIGH-1。seed が分類を運ばない)。知識確認の slot は key 番号。
    """
    if not 0 <= slot < 100 or not 0 <= k < 100 or not 0 <= r < 100:
        msg = "seed index out of range"
        raise ValueError(msg)
    return SEED_BASE + 1_000_000 * SEED_NS[namespace] + 10_000 * r + 100 * slot + k


# ---------------------------------------------------------------- renderer


def situation_row(sit: Situation, *, masked: bool = False) -> str:
    key = MASK if masked else sit.key
    return f"{key} / {sit.place} / {sit.company}"


def render_state(arm: str, order: Sequence[Situation], *, masked: bool = False) -> str:
    table = state_table(arm)
    lines = []
    for sit in order:
        act, n = table[sit]
        lines.append(
            f"条件: {situation_row(sit, masked=masked)} → 行動: {act} (成功 {n} / 失敗 0)"
        )
    return "\n".join([STATE_HEADER, *lines])


def render_probe(sit: Situation, options: Sequence[str]) -> str:
    return (
        f"状況: 生き物={sit.key}、場所={sit.place}、同伴={sit.company}。\n"
        f"次の行動から 1 つだけ選び、行動名だけを答えよ: {'、'.join(options)}"
    )


def render_messages(
    arm: str, probe: Probe, r: int, *, masked: bool = False
) -> list[dict[str, str]]:
    """Ollama /api/chat に渡す messages。masked は null pilot の状態 (key の欄を「不明」に)."""
    fi = ARM_FAMILY[arm]
    order = entry_order(fi, probe.triple, r)
    probe_text = render_probe(probe.situation, option_order(fi, probe.triple, r))
    user = f"{render_state(arm, order, masked=masked)}\n\n{probe_text}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def all_keys() -> tuple[str, ...]:
    """知識確認の対象 (dev 12 + probe 24) の正準順."""
    return tuple(
        [DEV_KEYS[c][i] for i in range(len(COMBOS)) for c in CLASSES]
        + [p.situation.key for p in probes()]
    )


def know_options(key_index: int, k: int) -> tuple[str, ...]:
    """key i の試行 k の選択肢。正答の分類が位置 (i + k) mod 3 に来る (3 試行で 3 位置を一巡、Codex HIGH-2)."""
    truth = key_class(all_keys()[key_index])
    others = [c for c in CLASSES if c != truth]
    pos = (key_index + k) % len(CLASSES)
    return tuple(others[:pos] + [truth] + others[pos:])


def render_know_messages(key_index: int, k: int) -> list[dict[str, str]]:
    key = all_keys()[key_index]
    options = "、".join(know_options(key_index, k))
    return [
        {"role": "system", "content": KNOW_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"生き物: {key}\n次の分類から 1 つだけ選び、分類名だけを答えよ: {options}",
        },
    ]


def prompt_bytes(messages: Sequence[Mapping[str, str]]) -> int:
    return sum(len(m["content"].encode("utf-8")) for m in messages)


# ------------------------------------------------------------------ 機械検査


def char_ngrams(word: str, n: int = 4) -> set[str]:
    return {word[i : i + n] for i in range(len(word) - n + 1)}


def frequency_vector_invariant(
    labels_a: Sequence[str], labels_b: Sequence[str]
) -> bool:
    """族内 2 状態の label 頻度ベクトルが一致するか (回転に対する不変性、ADR §5.1 の (x, x, y) の反例を落とす)."""
    return Counter(labels_a) == Counter(labels_b)


def check_label_frequency() -> list[str]:
    out = []
    for a, b in FAMILIES:
        la = [act for act, _ in state_table(a).values()]
        lb = [act for act, _ in state_table(b).values()]
        if not frequency_vector_invariant(la, lb):
            out.append(f"label frequency differs within family {a}/{b}")
        if sorted(Counter(la).values()) != [4, 4, 4]:
            out.append(f"label frequency of {a} is not 4/4/4")
    return out


def check_state_tables() -> list[str]:
    """aggregator の出力: 各 dev 状況にちょうど 1 行、行動 = 世界の規則、成功数 = 試行回数."""
    out = []
    for arm in LEVER_ARMS:
        table = state_table(arm)
        if set(table) != set(dev_situations()):
            out.append(f"{arm}: state rows do not cover the dev situations exactly")
            continue
        for sit, (act, n) in table.items():
            if act != rule(arm)[sit.latent] or n != TRIALS_PER_ACTION:
                out.append(f"{arm}: row {sit.key} disagrees with the world rule")
    for a, b in FAMILIES:
        if exposure_schedule(ARM_FAMILY[a]) != exposure_schedule(ARM_FAMILY[b]):
            out.append(f"exposure schedule differs within family {a}/{b}")
    return out


def check_dev_design() -> list[str]:
    """各 (組, 分類) にちょうど 1 つの dev 状況 (どの probe から見ても一致の型ごとに各分類 1 行)."""
    cells = Counter(((s.place, s.company), s.latent) for s in dev_situations())
    out = []
    if len(cells) != len(COMBOS) * len(CLASSES) or set(cells.values()) != {1}:
        out.append("dev situations are not one per (combo, class)")
    keys = [s.key for s in dev_situations()]
    if len(set(keys)) != len(keys):
        out.append("dev keys are not unique")
    return out


def check_triples() -> list[str]:
    out = []
    combo_use: Counter[tuple[str, str]] = Counter()
    for j in range(N_TRIPLES):
        tp = triple_probes(j)
        if sorted(p.situation.latent for p in tp) != sorted(CLASSES):
            out.append(f"triple {j} does not have one probe per class")
        combos = {(p.situation.place, p.situation.company) for p in tp}
        if len(combos) != 1:
            out.append(f"triple {j} does not share its distractors")
        combo_use.update(combos)
    if set(combo_use.values()) != {N_TRIPLES // len(COMBOS)}:
        out.append("combos are not used equally by the triples")
    return out


def check_pointed() -> list[str]:
    """4 arm が指す選択肢は相異なり、各 arm の指す選択肢は自分の族の Ω にある."""
    out = []
    for p in probes():
        if len(set(p.pointed.values())) != len(LEVER_ARMS):
            out.append(f"{p.probe_id}: pointed options are not distinct")
        for arm in LEVER_ARMS:
            if p.pointed[arm] not in family_actions(ARM_FAMILY[arm]):
                out.append(f"{p.probe_id}: {arm} points outside its family's options")
    return out


def check_triple_prompts_differ_only_in_key(r_count: int) -> list[str]:
    """つ組の 3 probe の prompt は、probe key を置き換えると一致する (key に依らない方策の C = 0 の前提)."""
    out = []
    for arm in LEVER_ARMS:
        for j in range(N_TRIPLES):
            for r in range(r_count):
                texts = set()
                for p in triple_probes(j):
                    user = render_messages(arm, p, r)[1]["content"]
                    texts.add(
                        user.replace(
                            f"生き物={p.situation.key}、", f"生き物={KEY_PLACEHOLDER}、"
                        )
                    )
                if len(texts) != 1:
                    out.append(
                        f"{arm} triple {j} r{r}: prompts differ beyond the probe key"
                    )
    return out


def check_probe_keys_absent(r_count: int) -> list[str]:
    """probe key は dev に無く、どの状態にも現れない。dev key は probe 文に現れない."""
    out = []
    dev_keys = {s.key for s in dev_situations()}
    probe_keys = {p.situation.key for p in probes()}
    if dev_keys & probe_keys:
        out.append("a probe key is also a dev key")
    states = {
        render_state(arm, entry_order(ARM_FAMILY[arm], j, r)).lower()
        for arm in LEVER_ARMS
        for j in range(N_TRIPLES)
        for r in range(r_count)
    }
    for state in states:
        out.extend(
            f"probe key {key!r} appears in a state"
            for key in probe_keys
            if key in state
        )
    for p in probes():
        text = render_probe(p.situation, family_actions(0)).lower()
        out.extend(
            f"dev key {key!r} appears in probe {p.probe_id}"
            for key in dev_keys
            if key in text
        )
    return sorted(set(out))


def state_vocabulary() -> tuple[str, ...]:
    """状態と probe 文に出る ASCII の語 (key 以外)."""
    return (*ACTIONS, *PLACES, *COMPANY)


def check_surface_overlap() -> list[str]:
    """probe key は dev key・label・distractor のどれとも文字 4-gram を共有しない (字面の写しの経路を閉じる)."""
    out = []
    state_words = [s.key for s in dev_situations()] + list(state_vocabulary())
    grams = set().union(*(char_ngrams(w) for w in state_words))
    for p in probes():
        key = p.situation.key
        shared = char_ngrams(key) & grams
        if shared:
            out.append(f"probe key {key!r} shares 4-grams {sorted(shared)}")
        out.extend(
            f"probe key {key!r} is a substring relation of {w!r}"
            for w in state_words
            if key in w or w in key
        )
    return out


def _ascii_words(text: str) -> list[str]:
    word: list[str] = []
    out = []
    for ch in text:
        if ch.isascii() and (ch.isalnum() or ch == "_"):
            word.append(ch)
        elif word:
            out.append("".join(word))
            word = []
    if word:
        out.append("".join(word))
    return out


def check_non_leakage(r_count: int) -> list[str]:
    """本走の prompt に分類名・arm 名・probe id を入れない."""
    out = []
    tokens = {t.lower() for t in (*CLASSES, *LEVER_ARMS, "rot")}
    for arm in LEVER_ARMS:
        for p in probes():
            for r in range(r_count):
                text = "\n".join(m["content"] for m in render_messages(arm, p, r))
                leaked = tokens & set(_ascii_words(text.lower()))
                out.extend(
                    f"{arm}/{p.probe_id}/r{r}: token {tok!r} leaks" for tok in leaked
                )
                if p.probe_id in text:
                    out.append(f"{arm}/{p.probe_id}: probe id leaks")
    return sorted(set(out))


def check_position_balance(r_count: int) -> list[str]:
    """R が 3 の倍数で、各 (族, つ組) で各 label が各表示位置に R/3 回来る."""
    if r_count % N_POSITIONS:
        return [f"R = {r_count} is not a multiple of {N_POSITIONS}"]
    out = []
    for fi in range(len(FAMILIES)):
        for j in range(N_TRIPLES):
            seen: Counter[tuple[str, int]] = Counter()
            for r in range(r_count):
                for pos, opt in enumerate(option_order(fi, j, r)):
                    seen[(opt, pos)] += 1
            if (
                set(seen.values()) != {r_count // N_POSITIONS}
                or len(seen) != N_POSITIONS**2
            ):
                out.append(f"family {fi} triple {j}: option positions are not balanced")
    return out


def _strip_labels(text: str) -> str:
    for act in ACTIONS:
        text = text.replace(act, "<L>")
    return text


def check_shared_within_family(r_count: int) -> list[str]:
    """族内の 2 arm は、同じ単位で状態の行順・選択肢の順が同じで、状態は label だけが違う."""
    out = []
    for a, b in FAMILIES:
        for p in probes():
            for r in range(r_count):
                ma = render_messages(a, p, r)[1]["content"]
                mb = render_messages(b, p, r)[1]["content"]
                if _strip_labels(ma) != _strip_labels(mb):
                    out.append(
                        f"{a}/{b} {p.probe_id} r{r}: prompts differ beyond labels"
                    )
                if ma.split("\n\n")[1] != mb.split("\n\n")[1]:
                    out.append(f"{a}/{b} {p.probe_id} r{r}: probe parts differ")
    return sorted(set(out))


def check_prompt_budget(r_max: int) -> list[str]:
    out = []
    worst = max(
        prompt_bytes(render_messages(arm, p, r, masked=masked))
        for arm in LEVER_ARMS
        for p in probes()
        for r in range(r_max)
        for masked in (False, True)
    )
    if worst > MAX_PROMPT_BYTES:
        out.append(f"prompt of {worst} bytes exceeds {MAX_PROMPT_BYTES}")
    if MAX_PROMPT_BYTES + CHAT_TEMPLATE_OVERHEAD + NUM_PREDICT > NUM_CTX:
        out.append("num_ctx does not cover the prompt budget")
    return out


def check_masked_states() -> list[str]:
    """null pilot の masked 状態は key を含まず、label と distractor は本走の状態と同じ."""
    out = []
    keys = {s.key for s in dev_situations()} | {p.situation.key for p in probes()}
    for arm in LEVER_ARMS:
        order = entry_order(ARM_FAMILY[arm], 0, PILOT_R0)
        masked = render_state(arm, order, masked=True)
        plain = render_state(arm, order)
        if any(k in masked for k in keys):
            out.append(f"{arm}: masked state contains a key")
        stripped = plain
        for s in dev_situations():
            stripped = stripped.replace(f"{s.key} /", f"{MASK} /")
        if stripped != masked:
            out.append(f"{arm}: masked state differs beyond the key column")
    return out


def check_selection_layout_separate(r_count: int) -> list[str]:
    """probe key の選定に使う行順は本走の行順と別 (同じ単位で 1 つも一致しない)."""
    same = [
        (fi, j, r)
        for fi in range(len(FAMILIES))
        for j in range(N_TRIPLES)
        for r in range(max(r_count, R_MAX))
        if entry_order(fi, j, r) == selection_entry_order(fi, j, r)
    ]
    return ["selection layouts coincide with the main-run layouts"] if same else []


def check_know_balance() -> list[str]:
    """知識確認: 各 key で、正答が 3 試行で 3 位置を一巡する (先頭固定・末尾固定の方策が通らない)."""
    out = []
    for i, key in enumerate(all_keys()):
        truth = key_class(key)
        positions = sorted(know_options(i, k).index(truth) for k in range(KNOW_K))
        if positions != list(range(len(CLASSES))):
            out.append(f"knowledge check: answer positions of {key!r} are not balanced")
    return out


def check_seed_namespaces(r_count: int) -> list[str]:
    """本走 (r < R)・pilot (r ∈ [PILOT_R0, PILOT_R0+PILOT_R))・知識確認の seed は交わらない."""
    out = []
    if r_count > R_MAX or PILOT_R0 < R_MAX:
        out.append("main replicates overlap the pilot replicates")
    main = {
        sample_seed(ns, r, p.triple, 0)
        for ns in ("fam0", "fam1")
        for r in range(r_count)
        for p in probes()
    }
    pilot = {
        sample_seed(ns, r, p.triple, 0)
        for ns in ("pilot_fam0", "pilot_fam1")
        for r in range(PILOT_R0, PILOT_R0 + PILOT_R)
        for p in probes()
    }
    know = {
        sample_seed("know", 0, i, k)
        for i in range(len(all_keys()))
        for k in range(KNOW_K)
    }
    if main & pilot or main & know or pilot & know:
        out.append("seed namespaces overlap")
    return out


def battery_report(r_count: int) -> dict[str, list[str]]:
    return {
        "label_frequency": check_label_frequency(),
        "state_tables": check_state_tables(),
        "dev_design": check_dev_design(),
        "triples": check_triples(),
        "pointed": check_pointed(),
        "triple_prompts_differ_only_in_key": check_triple_prompts_differ_only_in_key(
            r_count
        ),
        "probe_keys_absent": check_probe_keys_absent(r_count),
        "surface_overlap": check_surface_overlap(),
        "non_leakage": check_non_leakage(r_count),
        "position_balance": check_position_balance(r_count),
        "shared_within_family": check_shared_within_family(r_count),
        "prompt_budget": check_prompt_budget(R_MAX),
        "masked_states": check_masked_states(),
        "selection_layout_separate": check_selection_layout_separate(r_count),
        "know_balance": check_know_balance(),
        "seed_namespaces": check_seed_namespaces(r_count),
    }


def battery_violations(r_count: int) -> list[str]:
    return [f"{k}: {v}" for k, vs in battery_report(r_count).items() for v in vs]

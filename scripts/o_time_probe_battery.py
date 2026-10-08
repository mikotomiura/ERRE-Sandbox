"""候補 O_time (時期の評価) の事前登録 — battery・曝露・日ごとの aggregator・並び・renderer と機械検査.

事前登録 = ``experiments/20261008-o-time-probe-pilot/prereg.md``。
設計の正本 = ``.steering/20261008-next-candidate-scoping/design-final.md`` §5.4 (FROZEN) と
``.steering/20261008-o-time-prereg/design-final.md``。

世界 (prereg §2):

* 部屋 (状況) 6 つ。族 0 の規則 A・B は label 3 語 (L0)、族 1 の規則 C・D は別の 3 語 (L1) の上にある。
  A(x) = L0[i mod 3]、B(x) = L0[(i + 1) mod 3] (C・D も同じ形で L1)。全部屋で 2 つの規則は違う行動を指す。
* arm = 規則の列。族 0 = ``AB`` (1 日目に A、2 日目に B)・``BA``、族 1 = ``CD``・``DC``。現在 (2 日目の後) の規則は 2 日目の規則。
* 曝露: 環境が 2 日にわたり、各日に各部屋で族の 3 行動を各 3 回試させる。決定的な aggregator が、日ごとに、
  その日の中で失敗の無い成功だけを行にする (各日の各部屋に 1 行)。族の 2 状態の (部屋, label) の多重集合は同じで、
  違うのは各行の日付の札だけ。

日付の札 (時期の担い手、prereg §2.3): 書き方 ``asc`` (古い日 = 「1 日目」・新しい日 = 「2 日目」) と ``ago``
(古い日 = 「2 日前」・新しい日 = 「1 日前」)。

単位 (prereg §2.4): u = (族 f, 部屋 x, r)。単位に 4 呼び出し (2 arm × 2 書き方) を置き、行の並び・Ω の表示順・seed を共有する。

* 定理 1 (層 1): 同じ書き方の 2 arm は、札の数字を伏せると prompt が一致する (``check_layer1``)。
* 定理 2 (層 2): 札の後ろの語 (目 / 前) を伏せると、``ago`` の fwd arm の prompt は ``asc`` の bwd arm と一致し、
  ``ago`` の bwd arm は ``asc`` の fwd arm と一致する (``check_layer2``)。
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Final

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

# ---------------------------------------------------------------- 語彙 (凍結)

ROOMS: Final[tuple[str, ...]] = (
    "crimson",
    "violet",
    "amber",
    "cobalt",
    "ivory",
    "olive",
)
LABELS: Final[tuple[tuple[str, ...], ...]] = (
    ("ring_bell", "open_gate", "fill_jar"),  # 族 0 (規則 A・B)
    ("trim_wick", "seal_crate", "hang_rope"),  # 族 1 (規則 C・D)
)
ACTIONS: Final[tuple[str, ...]] = (*LABELS[0], *LABELS[1])
# 既存の battery の語 (4-gram を共有しないことを機械検査する。G・v2〜v5・Stage B)
PRIOR_VOCAB: Final[tuple[str, ...]] = (
    "sort_cards",
    "fold_linen",
    "stack_cups",
    "wind_clock",
    "count_keys",
    "tidy_shelf",
    "read_book",
    "sit_quiet",
    "walk_path",
    "talk_peer",
    "tend_moss",
    "rest_eyes",
    "wash_cups",
    "fold_mats",
)

ARM_AB: Final[str] = "AB"
ARM_BA: Final[str] = "BA"
ARM_CD: Final[str] = "CD"
ARM_DC: Final[str] = "DC"
LEVER_ARMS: Final[tuple[str, ...]] = (ARM_AB, ARM_BA, ARM_CD, ARM_DC)
FAMILIES: Final[tuple[tuple[str, str], ...]] = ((ARM_AB, ARM_BA), (ARM_CD, ARM_DC))
ARM_FAMILY: Final[dict[str, int]] = {
    a: fi for fi, fam in enumerate(FAMILIES) for a in fam
}
FWD: Final[tuple[str, ...]] = (ARM_AB, ARM_CD)  # 1 日目の規則 = 族の第 1 の規則 (A・C)
DIRECTIONS: Final[tuple[str, ...]] = ("fwd", "bwd")
FOIL: Final[dict[str, str]] = {
    ARM_AB: ARM_BA,
    ARM_BA: ARM_AB,
    ARM_CD: ARM_DC,
    ARM_DC: ARM_CD,
}

DAYS: Final[tuple[int, ...]] = (1, 2)  # 1 = 古い日、2 = 新しい日
ENCODINGS: Final[tuple[str, ...]] = ("asc", "ago")
TAGS: Final[dict[str, dict[int, str]]] = {
    "asc": {1: "1 日目", 2: "2 日目"},
    "ago": {1: "2 日前", 2: "1 日前"},
}
SUFFIX: Final[dict[str, str]] = {"asc": "目", "ago": "前"}
MASK_DIGIT: Final[str] = "?"
DIGIT_PLACEHOLDER: Final[str] = "<D>"
SUFFIX_PLACEHOLDER: Final[str] = "<S>"

N_ROOMS: Final[int] = len(ROOMS)
N_POSITIONS: Final[int] = 3  # Ω = 族の 3 label
TRIALS_PER_ACTION: Final[int] = 3

# ---- 凍結する実行条件 (G・v2 と同じ着座。prereg §4)
MODEL: Final[str] = "qwen3:8b"
THINK: Final[bool] = False
TEMPERATURE: Final[float] = 0.7
TOP_P: Final[float] = 0.8
REPEAT_PENALTY: Final[float] = 1.0
NUM_CTX: Final[int] = 4096
NUM_PREDICT: Final[int] = 32
CHAT_TEMPLATE_OVERHEAD: Final[int] = 64
MAX_PROMPT_BYTES: Final[int] = 3000  # token 数 ≤ UTF-8 byte 数 (byte-level BPE)

SEED_BASE: Final[int] = 20261008
LAYOUT_SEED: Final[int] = 20261008
M0_LAYOUT_SEED: Final[int] = 20261009
R_MAX: Final[int] = 288  # 本走の r は [0, R_MAX) (候補の最大。user 裁定 DU-2)
PILOT_R0: Final[int] = 300  # null pilot の r は [PILOT_R0, PILOT_R0 + PILOT_R)
PILOT_R: Final[int] = 6  # 表示の回転 (r + i) mod 3 の各層に 2 単位
# seed の名前空間 g (prereg §2.4): 本走の族 0 / 1、pilot の masked 族 0 / 1、pilot の M0 族 0 / 1
SEED_NS: Final[dict[str, int]] = {
    "fam0": 0,
    "fam1": 1,
    "masked_fam0": 3,
    "masked_fam1": 4,
    "m0_fam0": 5,
    "m0_fam1": 6,
}
MODES: Final[tuple[str, ...]] = ("main", "masked", "m0")

SYSTEM_PROMPT: Final[str] = (
    "あなたは与えられた状況で、示された行動の中から 1 つを選ぶ。"
)
STATE_HEADER: Final[str] = "これまでの経験の記録:"


def family_actions(fi: int) -> tuple[str, ...]:
    """族 fi の 3 label の正準順 (= Ω の正準順)."""
    return LABELS[fi]


def first_rule_label(fi: int, i: int) -> str:
    """族 fi の第 1 の規則 (A・C) が部屋 i で指す label."""
    return LABELS[fi][i % 3]


def second_rule_label(fi: int, i: int) -> str:
    """族 fi の第 2 の規則 (B・D) が部屋 i で指す label."""
    return LABELS[fi][(i + 1) % 3]


def third_label(fi: int, i: int) -> str:
    """部屋 i の記録に現れない族 fi の label (Ω の残り 1 つ)."""
    return LABELS[fi][(i + 2) % 3]


def direction(arm: str) -> str:
    return "fwd" if arm in FWD else "bwd"


def rule_on_day(arm: str, day: int) -> dict[str, str]:
    """arm の世界で、日 day に成功する行動 (部屋 → label)."""
    fi = ARM_FAMILY[arm]
    first = (day == 1) == (arm in FWD)
    pick = first_rule_label if first else second_rule_label
    return {room: pick(fi, i) for i, room in enumerate(ROOMS)}


def pointed(arm: str, i: int) -> tuple[str, str]:
    """(w, foil) = (新しい日の規則の行動, 古い日の規則の行動)."""
    room = ROOMS[i]
    return rule_on_day(arm, 2)[room], rule_on_day(arm, 1)[room]


# ------------------------------------------------------- 曝露と aggregator


@dataclass(frozen=True)
class Observation:
    day: int
    room: str
    action: str
    success: bool


def exposure_schedule(fi: int) -> tuple[tuple[int, str, str], ...]:
    """族 fi の固定の試行 schedule (族内の 2 arm で共通): 日ごと・部屋ごとに族の 3 行動を各 TRIALS_PER_ACTION 回."""
    return tuple(
        (day, room, act)
        for day in DAYS
        for room in ROOMS
        for act in family_actions(fi)
        for _ in range(TRIALS_PER_ACTION)
    )


def observe(arm: str) -> tuple[Observation, ...]:
    """環境 (arm の世界のその日の規則) が試行に成否を付けた観察列."""
    return tuple(
        Observation(day, room, act, act == rule_on_day(arm, day)[room])
        for day, room, act in exposure_schedule(ARM_FAMILY[arm])
    )


def aggregate(
    observations: Iterable[Observation],
) -> dict[int, dict[str, tuple[str, int]]]:
    """決定的な aggregator: 日ごとに (部屋, 行動) を数え、その日の中で失敗の無い成功だけを行にする.

    日 → 部屋 → (行動, 成功数)。日をまたいで数えない。
    """
    succ: Counter[tuple[int, str, str]] = Counter()
    fail: Counter[tuple[int, str, str]] = Counter()
    for ob in observations:
        (succ if ob.success else fail)[(ob.day, ob.room, ob.action)] += 1
    out: dict[int, dict[str, tuple[str, int]]] = {}
    for (day, room, act), n in succ.items():
        if fail[(day, room, act)] == 0:
            rows = out.setdefault(day, {})
            if room in rows:
                msg = f"two success rows for day {day} room {room}"
                raise ValueError(msg)
            rows[room] = (act, n)
    return out


@lru_cache(maxsize=8)
def state_table(arm: str) -> dict[int, dict[str, tuple[str, int]]]:
    return aggregate(observe(arm))


def row_day(arm: str, room: str, label: str) -> int:
    """arm の状態で、(部屋, label) の行が記録された日."""
    days = [d for d, rows in state_table(arm).items() if rows[room][0] == label]
    if len(days) != 1:
        msg = f"{arm}: ({room}, {label}) is not recorded on exactly one day"
        raise ValueError(msg)
    return days[0]


# ------------------------------------------------------------------ 単位と並び


@dataclass(frozen=True)
class Unit:
    family: int
    room: int  # 部屋の番号 i
    replicate: int


def units(r_count: int) -> tuple[Unit, ...]:
    """本走の単位 (r, 族, 部屋 の順)."""
    return tuple(
        Unit(fi, i, r)
        for r in range(r_count)
        for fi in range(len(FAMILIES))
        for i in range(N_ROOMS)
    )


def row_slots(fi: int) -> tuple[tuple[str, str], ...]:
    """族 fi の 12 行の slot = (部屋, label)。並びはこの slot を並べ替える (2 arm で共有)."""
    return tuple(
        (room, lab)
        for i, room in enumerate(ROOMS)
        for lab in (first_rule_label(fi, i), second_rule_label(fi, i))
    )


@lru_cache(maxsize=8192)
def entry_order(fi: int, i: int, r: int) -> tuple[tuple[str, str], ...]:
    """単位 (fi, i, r) の状態の行の並び (2 arm × 2 書き方の 4 呼び出しで共有)."""
    slots = row_slots(fi)
    perm = np.random.default_rng([LAYOUT_SEED, fi, i, r]).permutation(len(slots))
    return tuple(slots[int(k)] for k in perm)


@lru_cache(maxsize=8192)
def m0_order(fi: int, i: int, r: int) -> tuple[str, ...]:
    """M0 の陽性対照の部屋の並び (新しい日の行だけ。4 呼び出しで共有)."""
    perm = np.random.default_rng([M0_LAYOUT_SEED, fi, i, r]).permutation(N_ROOMS)
    return tuple(ROOMS[int(k)] for k in perm)


def option_order(fi: int, i: int, r: int) -> tuple[str, ...]:
    """Ω の表示順 = 族の正準順を (r + i) mod 3 だけ巡回 (単位の 4 呼び出しで共有)."""
    om = family_actions(fi)
    shift = (r + i) % N_POSITIONS
    return om[shift:] + om[:shift]


def sample_seed(namespace: str, r: int, i: int, k: int) -> int:
    """decoding seed。namespace が違えば交わらない。単位の 4 呼び出しで共有する."""
    if not 0 <= i < 100 or not 0 <= k < 100 or not 0 <= r < 1000:
        msg = "seed index out of range"
        raise ValueError(msg)
    return SEED_BASE + 10_000_000 * SEED_NS[namespace] + 10_000 * r + 100 * i + k


# ---------------------------------------------------------------- renderer


def tag(enc: str, day: int, *, masked: bool = False) -> str:
    text = TAGS[enc][day]
    if masked:
        return MASK_DIGIT + text[1:]
    return text


def render_row(tag_text: str, room: str, label: str, n: int) -> str:
    return f"[{tag_text}] 条件: {room} の部屋 → 行動: {label} (成功 {n} / 失敗 0)"


def render_state(arm: str, enc: str, unit: Unit, mode: str = "main") -> str:
    """状態のテキスト。mode = main (本走) / masked (札の数字を伏せる) / m0 (新しい日の行だけ)."""
    fi = ARM_FAMILY[arm]
    table = state_table(arm)
    lines = []
    if mode == "m0":
        for room in m0_order(fi, unit.room, unit.replicate):
            act, n = table[2][room]
            lines.append(render_row(tag(enc, 2), room, act, n))
    else:
        for room, lab in entry_order(fi, unit.room, unit.replicate):
            day = row_day(arm, room, lab)
            act, n = table[day][room]
            lines.append(
                render_row(tag(enc, day, masked=mode == "masked"), room, act, n)
            )
    return "\n".join([STATE_HEADER, *lines])


def render_probe(room: str, options: Sequence[str]) -> str:
    return (
        f"今の状況: {room} の部屋。\n"
        f"次の行動から 1 つだけ選び、行動名だけを答えよ: {'、'.join(options)}"
    )


def render_messages(
    arm: str, enc: str, unit: Unit, mode: str = "main"
) -> list[dict[str, str]]:
    """Ollama /api/chat に渡す messages."""
    fi = ARM_FAMILY[arm]
    if fi != unit.family:
        msg = f"arm {arm} is not in family {unit.family}"
        raise ValueError(msg)
    probe = render_probe(ROOMS[unit.room], option_order(fi, unit.room, unit.replicate))
    user = f"{render_state(arm, enc, unit, mode)}\n\n{probe}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def unit_calls(unit: Unit) -> tuple[tuple[str, str], ...]:
    """単位の 4 呼び出し (arm, 書き方)."""
    return tuple((arm, enc) for arm in FAMILIES[unit.family] for enc in ENCODINGS)


def prompt_bytes(messages: Sequence[Mapping[str, str]]) -> int:
    return sum(len(m["content"].encode("utf-8")) for m in messages)


def mask_digits(text: str) -> str:
    """札の数字を placeholder にする (定理 1 の前提の検査用)."""
    for enc in ENCODINGS:
        for day in DAYS:
            text = text.replace(
                f"[{TAGS[enc][day]}]", f"[{DIGIT_PLACEHOLDER}{TAGS[enc][day][1:]}]"
            )
    return text


def mask_suffix(text: str) -> str:
    """札の後ろの語 (目 / 前) を placeholder にする (定理 2 の前提の検査用)."""
    for enc in ENCODINGS:
        for day in DAYS:
            t = TAGS[enc][day]
            text = text.replace(f"[{t}]", f"[{t[:-1]}{SUFFIX_PLACEHOLDER}]")
    return text


# ------------------------------------------------------------------ 機械検査


def char_ngrams(word: str, n: int = 4) -> set[str]:
    return {word[i : i + n] for i in range(len(word) - n + 1)}


def check_vocabulary() -> list[str]:
    """部屋と label は互いに・既存の語と 4-gram を共有せず、数字を含まない."""
    out = []
    words = [*ROOMS, *ACTIONS]
    for a in range(len(words)):
        for b in range(a + 1, len(words)):
            shared = char_ngrams(words[a]) & char_ngrams(words[b])
            if shared:
                out.append(
                    f"{words[a]!r} and {words[b]!r} share 4-grams {sorted(shared)}"
                )
    prior = set().union(*(char_ngrams(w) for w in PRIOR_VOCAB))
    for w in words:
        if char_ngrams(w) & prior:
            out.append(f"{w!r} shares 4-grams with a prior battery")
        if any(ch.isdigit() for ch in w):
            out.append(f"{w!r} contains a digit")
    if len(set(words)) != len(words):
        out.append("rooms and labels are not unique")
    return out


def check_rules() -> list[str]:
    """全部屋で 2 つの規則は違う行動を指し、各規則で各 label がちょうど 2 部屋."""
    out = []
    for fi in range(len(FAMILIES)):
        firsts = [first_rule_label(fi, i) for i in range(N_ROOMS)]
        seconds = [second_rule_label(fi, i) for i in range(N_ROOMS)]
        if any(a == b for a, b in zip(firsts, seconds, strict=True)):
            out.append(f"family {fi}: the two rules agree on a room")
        for labels in (firsts, seconds):
            if sorted(Counter(labels).values()) != [2, 2, 2]:
                out.append(f"family {fi}: a rule does not use each label twice")
    for arm in LEVER_ARMS:
        for i in range(N_ROOMS):
            w, foil = pointed(arm, i)
            if w == foil or third_label(ARM_FAMILY[arm], i) in (w, foil):
                out.append(
                    f"{arm} room {i}: w, foil and the third label are not distinct"
                )
    return out


def check_state_tables() -> list[str]:
    """aggregator の出力: 各日の各部屋にちょうど 1 行、行動 = その日の規則、成功数 = 試行回数."""
    out = []
    for arm in LEVER_ARMS:
        table = state_table(arm)
        if set(table) != set(DAYS):
            out.append(f"{arm}: state rows do not cover the days exactly")
            continue
        for day in DAYS:
            if set(table[day]) != set(ROOMS):
                out.append(f"{arm}: day {day} rows do not cover the rooms exactly")
                continue
            for room, (act, n) in table[day].items():
                if act != rule_on_day(arm, day)[room] or n != TRIALS_PER_ACTION:
                    out.append(
                        f"{arm}: day {day} row {room} disagrees with the world rule"
                    )
    for a, b in FAMILIES:
        if exposure_schedule(ARM_FAMILY[a]) != exposure_schedule(ARM_FAMILY[b]):
            out.append(f"exposure schedule differs within family {a}/{b}")
    return out


def check_multiset() -> list[str]:
    """族の 2 状態の (部屋, label) の多重集合は同じで、各日の label の頻度は 2/2/2."""
    out = []
    for a, b in FAMILIES:
        ms = []
        for arm in (a, b):
            table = state_table(arm)
            ms.append(
                Counter(
                    (room, act) for d in DAYS for room, (act, _) in table[d].items()
                )
            )
            for d in DAYS:
                freq = Counter(act for act, _ in table[d].values())
                if sorted(freq.values()) != [2, 2, 2]:
                    out.append(f"{arm}: day {d} label frequency is not 2/2/2")
        if ms[0] != ms[1]:
            out.append(f"(room, label) multiset differs within family {a}/{b}")
    return out


def check_tags() -> list[str]:
    """札: 書き方の中で 2 日の札は数字だけが違い、書き方の間では後ろの語だけが違う。asc は新しい日が大きい数、ago は小さい数."""
    out = []
    for enc in ENCODINGS:
        t1, t2 = TAGS[enc][1], TAGS[enc][2]
        if t1[1:] != t2[1:] or t1[0] == t2[0] or t1[-1] != SUFFIX[enc]:
            out.append(f"{enc}: the two day tags differ beyond the digit")
    if (
        TAGS["asc"][1][:-1] != TAGS["ago"][2][:-1]
        or TAGS["asc"][2][:-1] != TAGS["ago"][1][:-1]
    ):
        out.append("asc and ago differ beyond the suffix and the digit order")
    if not (
        TAGS["asc"][2][0] > TAGS["asc"][1][0] and TAGS["ago"][2][0] < TAGS["ago"][1][0]
    ):
        out.append("the digit order is not reversed between asc and ago")
    return out


def normalized_messages(
    messages: Sequence[Mapping[str, str]], fn: Callable[[str], str]
) -> str:
    """messages 全体 (件数・role・各 content・欄の集合) を、content に fn を当てて 1 つの文字列にする.

    定理 1・2 の前提の検査は、user の文面だけでなく system・role・追加のメッセージを含む prompt 全体を比べる
    (Codex HIGH-1: system にだけ書き方に依る指示を足す変更を見逃さないため)。
    """
    return json.dumps(
        [{**dict(m), "content": fn(m["content"])} for m in messages],
        ensure_ascii=False,
        sort_keys=True,
    )


def check_layer1(r_count: int) -> list[str]:
    """定理 1 の前提: 同じ書き方の 2 arm は、札の数字を伏せると prompt 全体が一致する."""
    out = []
    for u in units(r_count):
        a, b = FAMILIES[u.family]
        for enc in ENCODINGS:
            ma = normalized_messages(render_messages(a, enc, u), mask_digits)
            mb = normalized_messages(render_messages(b, enc, u), mask_digits)
            if ma != mb:
                out.append(f"{a}/{b} {enc} {u}: prompts differ beyond the tag digits")
    return sorted(set(out))


def check_layer2(r_count: int) -> list[str]:
    """定理 2 の前提: 後ろの語を伏せると、prompt 全体で ago の fwd arm = asc の bwd arm、ago の bwd arm = asc の fwd arm."""
    out = []
    for u in units(r_count):
        fwd, bwd = FAMILIES[u.family]
        for x, y in ((fwd, bwd), (bwd, fwd)):
            mx = normalized_messages(render_messages(x, "ago", u), mask_suffix)
            my = normalized_messages(render_messages(y, "asc", u), mask_suffix)
            if mx != my:
                out.append(f"{u}: ago/{x} differs from asc/{y} beyond the suffix")
    return sorted(set(out))


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
    """prompt に arm 名・規則名・書き方の名・向きの名を入れない (ASCII の語は部屋と label と札の数字だけ)."""
    out = []
    allowed = {*ROOMS, *ACTIONS, "1", "2", "3", "0"}
    for u in units(r_count):
        for arm, enc in unit_calls(u):
            for mode in MODES:
                text = "\n".join(
                    m["content"] for m in render_messages(arm, enc, u, mode)
                )
                extra = set(_ascii_words(text)) - allowed
                out.extend(f"{arm}/{enc}/{mode} {u}: token {t!r} leaks" for t in extra)
    return sorted(set(out))


def check_position_balance(r_count: int) -> list[str]:
    """R が 3 の倍数で、各 (族, 部屋) で各 label が各表示位置に R/3 回来る."""
    if r_count % N_POSITIONS:
        return [f"R = {r_count} is not a multiple of {N_POSITIONS}"]
    out = []
    for fi in range(len(FAMILIES)):
        for i in range(N_ROOMS):
            seen: Counter[tuple[str, int]] = Counter()
            for r in range(r_count):
                for pos, opt in enumerate(option_order(fi, i, r)):
                    seen[(opt, pos)] += 1
            if (
                set(seen.values()) != {r_count // N_POSITIONS}
                or len(seen) != N_POSITIONS**2
            ):
                out.append(f"family {fi} room {i}: option positions are not balanced")
    return out


@lru_cache(maxsize=8)
def worst_prompt_bytes(r_max: int) -> int:
    """r < r_max の本走・masked・M0 の全 prompt の最大 byte 数 (重いので r_max ごとに 1 回)."""
    return max(
        prompt_bytes(render_messages(arm, enc, u, mode))
        for u in units(r_max)
        for arm, enc in unit_calls(u)
        for mode in MODES
    )


def check_prompt_budget(r_max: int) -> list[str]:
    out = []
    worst = worst_prompt_bytes(r_max)
    if worst > MAX_PROMPT_BYTES:
        out.append(f"prompt of {worst} bytes exceeds {MAX_PROMPT_BYTES}")
    if MAX_PROMPT_BYTES + CHAT_TEMPLATE_OVERHEAD + NUM_PREDICT > NUM_CTX:
        out.append("num_ctx does not cover the prompt budget")
    return out


def pilot_units() -> tuple[Unit, ...]:
    return tuple(
        Unit(fi, i, r)
        for r in range(PILOT_R0, PILOT_R0 + PILOT_R)
        for fi in range(len(FAMILIES))
        for i in range(N_ROOMS)
    )


def check_masked_states() -> list[str]:
    """masked: 本走の状態の札の数字だけを伏せたもの。同じ書き方の 2 arm の prompt は同一."""
    out = []
    for u in pilot_units():
        a, b = FAMILIES[u.family]
        for enc in ENCODINGS:
            texts = set()
            for arm in (a, b):
                masked = render_state(arm, enc, u, "masked")
                plain = render_state(arm, enc, u)
                if any(TAGS[enc][d] in masked for d in DAYS):
                    out.append(f"{arm}/{enc} {u}: masked state shows a tag digit")
                if mask_digits(plain).replace(DIGIT_PLACEHOLDER, MASK_DIGIT) != masked:
                    out.append(
                        f"{arm}/{enc} {u}: masked state differs beyond the tag digits"
                    )
                texts.add(
                    normalized_messages(render_messages(arm, enc, u, "masked"), str)
                )
            if len(texts) != 1:
                out.append(f"{a}/{b} {enc} {u}: masked prompts differ between the arms")
    return sorted(set(out))


def check_m0_states() -> list[str]:
    """M0: 新しい日の行だけ (各部屋 1 行、札 = 新しい日)。同じ書き方の 2 arm は label だけが違う."""
    out = []
    for u in pilot_units():
        a, b = FAMILIES[u.family]
        for enc in ENCODINGS:
            stripped = set()
            for arm in (a, b):
                text = render_state(arm, enc, u, "m0")
                lines = text.split("\n")[1:]
                if len(lines) != N_ROOMS:
                    out.append(
                        f"{arm}/{enc} {u}: M0 state does not have one row per room"
                    )
                want = {
                    render_row(tag(enc, 2), room, *state_table(arm)[2][room])
                    for room in ROOMS
                }
                if set(lines) != want:
                    out.append(f"{arm}/{enc} {u}: M0 rows are not the newer-day rows")
                for act in ACTIONS:
                    text = text.replace(act, "<L>")
                stripped.add(text)
            if len(stripped) != 1:
                out.append(f"{a}/{b} {enc} {u}: M0 states differ beyond labels")
    return sorted(set(out))


def check_seed_namespaces(r_count: int) -> list[str]:
    """本走 (r < R)・pilot masked・pilot M0 の seed は交わらない."""
    out = []
    if r_count > R_MAX or PILOT_R0 < R_MAX:
        out.append("main replicates overlap the pilot replicates")
    main = {
        sample_seed(f"fam{u.family}", u.replicate, u.room, 0) for u in units(r_count)
    }
    masked = {
        sample_seed(f"masked_fam{u.family}", u.replicate, u.room, 0)
        for u in pilot_units()
    }
    m0 = {
        sample_seed(f"m0_fam{u.family}", u.replicate, u.room, 0) for u in pilot_units()
    }
    if main & masked or main & m0 or masked & m0:
        out.append("seed namespaces overlap")
    if len(main) != len(units(r_count)) or len(masked) != len(pilot_units()):
        out.append("seeds are shared between units")
    return out


def battery_report(r_count: int) -> dict[str, list[str]]:
    return {
        "vocabulary": check_vocabulary(),
        "rules": check_rules(),
        "state_tables": check_state_tables(),
        "multiset": check_multiset(),
        "tags": check_tags(),
        "layer1": check_layer1(r_count),
        "layer2": check_layer2(r_count),
        "non_leakage": check_non_leakage(r_count),
        "position_balance": check_position_balance(r_count),
        "prompt_budget": check_prompt_budget(R_MAX),
        "masked_states": check_masked_states(),
        "m0_states": check_m0_states(),
        "seed_namespaces": check_seed_namespaces(r_count),
    }


def battery_violations(r_count: int) -> list[str]:
    return [f"{k}: {v}" for k, vs in battery_report(r_count).items() for v in vs]

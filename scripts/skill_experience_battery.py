"""経験由来 Skill pilot — 合成経験の成否集計状態・renderer と機械検査 (prereg v3).

事前登録 = ``experiments/20260926-experience-skill-pilot/prereg.md``。凍結 v2 battery
(``scripts/skill_lever_battery.py``) の probe・layout (π_r と Ω_q の巡回)・decoding seed・実行条件・
probe 部 renderer をそのまま import し、**状態だけ** を置き換える (v2 からの 1 変数)。

状態 (prereg v3 §2):

* 試行列: 発達 signature (weather w) ごとに正準順 [A(w), σA(w), A(next w)] (族 A)、
  族 B はその σ 像 [σA(w), A(w), σA(next w)]。各試行 3 回・決定的。
* 成否 = arm の規則表 (v2 と同じ ``rule``)。1 行 = (signature, 行動) の集計で、
  「成功 3 / 失敗 0」または「成功 0 / 失敗 3」。36 行。成功行の文面は v2 lever 行と同一。
* block 順 = π_r (v2 の ``layout(r).entry_order``)。block 内の順は正準順を (r + j) mod 3 だけ巡回
  (j = π_r で並べた後の描画順 index)。各 r の中で成功行の位置が 4/4/4 に均衡する。
* 族 {A, A_rot} / {B, B_rot} の 2 状態は、成否欄以外が byte 一致する (``check_family_identity``)。

長さ・形式の陽性対照 (L_*、user 裁定): 判定 arm の状態から **失敗行の label だけ** を語彙外の
filler に置き換える。byte 長・行数・成否欄の配置・巡回は判定 arm と同一で、選択肢 Ω_q に出る label は
成功行にしか現れない (v2 の rule lookup を v3 の枠で測る)。

arm 名は prompt・状態に出さない (非漏洩、``check_non_leakage``)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from scripts import skill_lever_battery as v2
from scripts.stage_b_battery import ACTIONS, RULE_A, SIGMA, WEATHER, dev_signatures
from scripts.stage_b_scorer import (
    Probe,
    Snapshot,
    StageBData,
    integrity_violations,
    signature_text,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from scripts.stage_b_battery import Signature

ARM_A: Final[str] = v2.ARM_A
ARM_A_ROT: Final[str] = v2.ARM_A_ROT
ARM_B: Final[str] = v2.ARM_B
ARM_B_ROT: Final[str] = v2.ARM_B_ROT
ARM_C0: Final[str] = v2.ARM_C0
JUDGE_ARMS: Final[tuple[str, ...]] = v2.LEVER_ARMS
CONTROL_ARMS: Final[tuple[str, ...]] = ("L_A", "L_A_rot", "L_B", "L_B_rot")
# 対照 arm が指す選択肢・foil は、対応する判定 arm と同じ (状態の失敗行 label だけが違う)
POINTS_AS: Final[dict[str, str]] = {
    **{a: a for a in JUDGE_ARMS},
    **dict(zip(CONTROL_ARMS, JUDGE_ARMS, strict=True)),
}
STATE_ARMS: Final[tuple[str, ...]] = (*JUDGE_ARMS, *CONTROL_ARMS)
ALL_ARMS: Final[tuple[str, ...]] = (*STATE_ARMS, ARM_C0)
JUDGE_FAMILIES: Final[tuple[tuple[str, str], ...]] = v2.FAMILIES
CONTROL_FAMILIES: Final[tuple[tuple[str, str], ...]] = (
    ("L_A", "L_A_rot"),
    ("L_B", "L_B_rot"),
)

R_MAX: Final[int] = 12  # user 裁定 (v2 と同じ)
K_MAX: Final[int] = 20
N_BLOCK: Final[int] = 3  # 1 signature あたりの試行行動数
ATTEMPTS: Final[int] = 3  # 1 試行あたりの回数
OUTCOME_SUCCESS: Final[str] = f"成功 {ATTEMPTS} / 失敗 0"
OUTCOME_FAILURE: Final[str] = f"成功 0 / 失敗 {ATTEMPTS}"
OUTCOME_MASK: Final[str] = "*"
# 対照の filler: 9 文字 (6 語彙と同じ長さ)・語彙外・parse で ⊥
FILLERS: Final[tuple[str, str]] = ("wash_cups", "fold_mats")
STATE_HEADER: Final[str] = v2.STATE_HEADER
SYSTEM_PROMPT: Final[str] = v2.SYSTEM_PROMPT


def _next_weather(w: str) -> str:
    return WEATHER[(WEATHER.index(w) + 1) % len(WEATHER)]


def rule(arm: str) -> dict[str, str]:
    """State arm の規則表 weather → 成功する行動 (対照は対応する判定 arm と同じ)."""
    return v2.rule(POINTS_AS[arm])


def family_of(arm: str) -> str:
    """'A' (A / A_rot / L_A / L_A_rot) または 'B'."""
    return "A" if POINTS_AS[arm] in (ARM_A, ARM_A_ROT) else "B"


def trial_actions(arm: str, w: str) -> tuple[str, ...]:
    """Weather w の発達 signature で試行する行動の正準順 (族内で共有)."""
    canon = (RULE_A[w], SIGMA[RULE_A[w]], RULE_A[_next_weather(w)])
    if family_of(arm) == "A":
        return canon
    return tuple(SIGMA[a] for a in canon)


# ------------------------------------------------------------------ state


@dataclass(frozen=True)
class Row:
    """状態の 1 行 = (signature, 行動) の集計."""

    signature: Signature
    action: str  # 描画する label (対照の失敗行は filler)
    tried: str  # 試行した行動 (対照でも語彙内)
    success: bool
    block: int  # 描画順の block index j
    position: int  # block 内の描画位置 (0..2)


def block_shift(r: int, j: int) -> int:
    return (r + j) % N_BLOCK


def state_rows(arm: str, lay: v2.Layout) -> list[Row]:
    table = rule(arm)
    control = arm in CONTROL_ARMS
    rows: list[Row] = []
    for j, sig in enumerate(lay.entry_order):
        canon = trial_actions(arm, sig[0])
        failed = [a for a in canon if a != table[sig[0]]]
        shift = block_shift(lay.replicate, j)
        for pos, act in enumerate(canon[shift:] + canon[:shift]):
            ok = act == table[sig[0]]
            label = act if ok or not control else FILLERS[failed.index(act)]
            rows.append(Row(sig, label, act, ok, j, pos))
    return rows


def render_row(row: Row) -> str:
    outcome = OUTCOME_SUCCESS if row.success else OUTCOME_FAILURE
    return f"条件: {signature_text(row.signature)} → 行動: {row.action} ({outcome})"


def render_state(arm: str, lay: v2.Layout) -> str:
    return "\n".join([STATE_HEADER, *(render_row(x) for x in state_rows(arm, lay))])


def mask_outcomes(text: str) -> str:
    """成否欄を消した正準形 (族内の byte 一致検査に使う)."""
    return text.replace(OUTCOME_SUCCESS, OUTCOME_MASK).replace(
        OUTCOME_FAILURE, OUTCOME_MASK
    )


def render_messages(
    arm: str, probe: v2.LeverProbe, lay: v2.Layout
) -> list[dict[str, str]]:
    """Ollama /api/chat に渡す messages。C0 は状態ブロックを持たない (v2 と同じ probe 部)."""
    probe_text = v2.render_probe(probe, lay)
    user = probe_text if arm == ARM_C0 else f"{render_state(arm, lay)}\n\n{probe_text}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def prompt_bytes(messages: Sequence[Mapping[str, str]]) -> int:
    return v2.prompt_bytes(messages)


def max_prompt_bytes(r_count: int = R_MAX) -> int:
    return max(
        prompt_bytes(render_messages(arm, p, v2.layout(r)))
        for r in range(r_count)
        for p in v2.lever_probes()
        for arm in ALL_ARMS
    )


# ------------------------------------------------------------------ checks


def check_family_identity(r_count: int) -> list[str]:
    """判定族の 2 状態は、成否欄を消すと byte 一致する (outcome-blind 方策の相殺条件)."""
    problems: list[str] = []
    for r in range(r_count):
        lay = v2.layout(r)
        for a, b in JUDGE_FAMILIES:
            if mask_outcomes(render_state(a, lay)) != mask_outcomes(
                render_state(b, lay)
            ):
                problems.append(f"r={r} {a}/{b}: states differ outside outcomes")
            if render_state(a, lay) == render_state(b, lay):
                problems.append(f"r={r} {a}/{b}: states are identical")
    return problems


def check_outcome_balance(r_count: int) -> list[str]:
    """全 state arm で成功 12 行 / 失敗 24 行、各 r の中で成功行の block 内位置が 4/4/4."""
    problems: list[str] = []
    n_sig = len(dev_signatures())
    for r in range(r_count):
        lay = v2.layout(r)
        for arm in STATE_ARMS:
            rows = state_rows(arm, lay)
            succ = [x for x in rows if x.success]
            if len(rows) != N_BLOCK * n_sig or len(succ) != n_sig:
                problems.append(
                    f"r={r} {arm}: outcome frequency is not {n_sig}/{2 * n_sig}"
                )
            counts = [sum(x.position == k for x in succ) for k in range(N_BLOCK)]
            if len(set(counts)) != 1:
                problems.append(f"r={r} {arm}: success positions unbalanced {counts}")
            for j in range(n_sig):
                if sum(x.success for x in rows if x.block == j) != 1:
                    problems.append(f"r={r} {arm}: block {j} lacks one success row")
    return problems


def check_trial_sharing(r_count: int) -> list[str]:
    """族内 (対照を含む) で試行した行動・signature・描画位置の列が一致し、成否だけが違う."""
    problems: list[str] = []
    for r in range(r_count):
        lay = v2.layout(r)
        for fam in ("A", "B"):
            arms = [a for a in STATE_ARMS if family_of(a) == fam]
            seqs = {
                a: [
                    (x.signature, x.tried, x.block, x.position)
                    for x in state_rows(a, lay)
                ]
                for a in arms
            }
            if len({tuple(v) for v in seqs.values()}) != 1:
                problems.append(f"r={r} family {fam}: trial sequences differ")
    return problems


def check_control_construction(r_count: int) -> list[str]:
    """対照 = 判定 arm の状態の失敗行 label だけを filler に置き換えたもの (byte 長も一致)."""
    problems: list[str] = []
    vocab = set(ACTIONS)
    if set(FILLERS) & vocab or len(set(FILLERS)) != len(FILLERS):
        problems.append("fillers overlap the action vocabulary")
    if any(len(f) != len(ACTIONS[0]) for f in (*FILLERS, *ACTIONS)):
        problems.append("fillers and actions differ in length")
    for r in range(r_count):
        lay = v2.layout(r)
        for ctl, judge in zip(CONTROL_ARMS, JUDGE_ARMS, strict=True):
            rc, rj = state_rows(ctl, lay), state_rows(judge, lay)
            for xc, xj in zip(rc, rj, strict=True):
                same = (xc.signature, xc.success, xc.tried) == (
                    xj.signature,
                    xj.success,
                    xj.tried,
                )
                if not same:
                    problems.append(f"r={r} {ctl}: row differs from {judge}")
                    break
                want_filler = not xj.success
                if want_filler != (xc.action in FILLERS) or (
                    xj.success and xc.action != xj.action
                ):
                    problems.append(f"r={r} {ctl}: labels are not the filler swap")
                    break
            sc, sj = render_state(ctl, lay), render_state(judge, lay)
            if len(sc.encode("utf-8")) != len(sj.encode("utf-8")):
                problems.append(f"r={r} {ctl}: byte length differs from {judge}")
            if any(a in sc for a in vocab if a not in set(rule(ctl).values())):
                problems.append(f"r={r} {ctl}: a non-rule vocabulary label appears")
    return problems


def check_control_family(r_count: int) -> list[str]:
    """対照族は v2 型: label 多重集合・signature 順・byte 長が一致する."""
    problems: list[str] = []
    for r in range(r_count):
        lay = v2.layout(r)
        for a, b in CONTROL_FAMILIES:
            ra, rb = state_rows(a, lay), state_rows(b, lay)
            if sorted(x.action for x in ra) != sorted(x.action for x in rb):
                problems.append(f"r={r} {a}/{b}: label multisets differ")
            if [x.signature for x in ra] != [x.signature for x in rb]:
                problems.append(f"r={r} {a}/{b}: signature orders differ")
            if len(render_state(a, lay)) != len(render_state(b, lay)):
                problems.append(f"r={r} {a}/{b}: state lengths differ")
    return problems


def check_shared_layout(r_count: int) -> list[str]:
    """同じ r の中で、全 arm の probe 部分 (状況・選択肢の順) が一致する."""
    problems: list[str] = []
    for r in range(r_count):
        lay = v2.layout(r)
        for p in v2.lever_probes():
            tails = {
                arm: render_messages(arm, p, lay)[1]["content"].rsplit("\n\n", 1)[-1]
                for arm in ALL_ARMS
            }
            if len(set(tails.values())) != 1:
                problems.append(f"r={r} {p.probe_id}: probe part differs across arms")
    return problems


def check_prompt_budget(r_count: int = R_MAX) -> list[str]:
    """描画 prompt が切り詰められえないことの静的保証 (token ≤ UTF-8 byte、v2 と同じ上限)."""
    problems: list[str] = []
    if v2.MAX_PROMPT_BYTES + v2.CHAT_TEMPLATE_OVERHEAD + v2.NUM_PREDICT > v2.NUM_CTX:
        problems.append("byte budget does not fit num_ctx")
    n = max_prompt_bytes(r_count)
    if n > v2.MAX_PROMPT_BYTES:
        problems.append(f"max prompt {n} bytes > {v2.MAX_PROMPT_BYTES}")
    return problems


def check_non_leakage(r_count: int) -> list[str]:
    """v2 と同じ integrity 検査 (``stage_b_scorer.integrity_violations``) + arm 名."""
    ps = v2.lever_probes()
    probe_sets = (
        tuple(
            Probe(p.probe_id, p.omega, p.pointed[ARM_A], p.pointed[ARM_B]) for p in ps
        ),
        tuple(
            Probe(p.probe_id, p.omega, p.pointed[ARM_A_ROT], p.pointed[ARM_B_ROT])
            for p in ps
        ),
    )
    problems: list[str] = []
    for probe_set in probe_sets:
        snapshots = []
        prompts = []
        for r in range(r_count):
            lay = v2.layout(r)
            for arm in STATE_ARMS:
                snapshots.append(
                    Snapshot(
                        ind_id=f"r{r}-{arm}",
                        preconditions=tuple(x.signature for x in state_rows(arm, lay)),
                        text=render_state(arm, lay),
                    )
                )
            for p in ps:
                prompts.extend(
                    render_messages(arm, p, lay)[1]["content"] for arm in ALL_ARMS
                )
        data = StageBData(
            probes=probe_set,
            probe_signatures={p.probe_id: p.signature for p in ps},
            dev_signatures=frozenset(dev_signatures()),
            di=(),
            di_ablation=(),
            ci=(),
            snapshots=tuple(snapshots),
            probe_prompts=tuple(prompts),
        )
        problems.extend(integrity_violations(data))
    arm_tokens = ("a_rot", "b_rot", "c0", "arm", "l_a", "l_b")
    for r in range(r_count):
        lay = v2.layout(r)
        for p in ps:
            for arm in ALL_ARMS:
                low = render_messages(arm, p, lay)[1]["content"].lower()
                problems.extend(
                    f"r={r} {arm}: prompt contains {tok!r}"
                    for tok in arm_tokens
                    if tok in low
                )
    return sorted(set(problems))


def battery_report(r_count: int) -> dict[str, object]:
    return {
        "n_probes": len(v2.lever_probes()),
        "n_state_rows": N_BLOCK * len(dev_signatures()),
        "max_prompt_bytes": max_prompt_bytes(r_count),
        "pointed_bijection": v2.check_pointed_bijection(),
        "position_balance": v2.check_position_balance(r_count),
        "family_identity": check_family_identity(r_count),
        "outcome_balance": check_outcome_balance(r_count),
        "trial_sharing": check_trial_sharing(r_count),
        "control_construction": check_control_construction(r_count),
        "control_family": check_control_family(r_count),
        "shared_layout": check_shared_layout(r_count),
        "non_leakage": check_non_leakage(r_count),
        "prompt_budget": check_prompt_budget(max(r_count, R_MAX)),
    }

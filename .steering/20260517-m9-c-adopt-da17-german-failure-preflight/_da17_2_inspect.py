"""DA17-2 ad-hoc reproducibility script (本 ADR で commit、再現性 / PR-5 再利用のため).

LoRA-on と no-LoRA の v4 verdict shard から ドイツ語 utterance を
同一 stimulus_id (dialog_id の `:<chapter>:<stimulus>` 部分) で paired
sample し、qualitative inspection 用に side-by-side 出力する。

Codex review MEDIUM-4 反映: stimulus_key 一致だけでなく
(stimulus_key, tick, turn_index) の tick mismatch 件数を出力して
0 件であることを assert/記録する。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import duckdb
from langdetect import DetectorFactory, detect_langs

# Windows console (cp932) で UTF-8 utterance を出力するため
sys.stdout.reconfigure(encoding="utf-8")

DetectorFactory.seed = 0  # compute_burrows_delta.py:67 と同 seed
THRESH = 0.85  # compute_burrows_delta.py と同 threshold

REPO = Path(__file__).resolve().parents[2]
LORA_SHARD = REPO / "data/eval/m9-c-adopt-plan-b-verdict-v4/kant_r8v4_run0_stim.duckdb"
NOLORA_SHARD = REPO / "data/eval/m9-c-adopt-plan-b-verdict-v4/kant_planb_nolora_run0_stim.duckdb"


def stimulus_key(dialog_id: str) -> str:
    """dialog_id `kant_r8_run0_pilot:c0:dilemma_kant_01` -> `c0:dilemma_kant_01`."""
    parts = dialog_id.split(":", 1)
    return parts[1] if len(parts) > 1 else dialog_id


def load_de_kant(shard: Path):
    con = duckdb.connect(str(shard), read_only=True)
    rows = con.execute(
        "SELECT dialog_id, tick, turn_index, utterance "
        "FROM raw_dialog.dialog "
        "WHERE speaker_persona_id='kant' "
        "ORDER BY dialog_id, tick, turn_index"
    ).fetchall()
    con.close()
    de_rows = []
    for dialog_id, tick, turn_index, utt in rows:
        if not utt or len(utt.strip()) < 5:
            continue
        try:
            langs = detect_langs(utt)
        except Exception:
            continue
        if not langs:
            continue
        top = langs[0]
        if top.lang == "de" and top.prob >= THRESH:
            de_rows.append((dialog_id, stimulus_key(dialog_id), tick, turn_index, utt))
    return de_rows


lora_de = load_de_kant(LORA_SHARD)
nolora_de = load_de_kant(NOLORA_SHARD)
print(f"LoRA-on de utterances: {len(lora_de)}")
print(f"no-LoRA de utterances: {len(nolora_de)}")

# 同 stimulus_key で pairing (各 stimulus_key で 1 件目を採用)
# MEDIUM-4 反映: tick / turn_index mismatch 件数を audit
nolora_idx: dict[str, tuple[str, int, int, str]] = {}
for did, sk, t, ti, u in nolora_de:
    nolora_idx.setdefault(sk, (did, t, ti, u))

paired = []
tick_mismatch = 0
turn_idx_mismatch = 0
seen_sk: set[str] = set()
for did, sk, t, ti, lu in lora_de:
    if sk in seen_sk:
        continue
    if sk in nolora_idx:
        nu_did, nu_t, nu_ti, nu_u = nolora_idx[sk]
        if nu_t != t:
            tick_mismatch += 1
        if nu_ti != ti:
            turn_idx_mismatch += 1
        paired.append((sk, did, nu_did, t, nu_t, lu, nu_u))
        seen_sk.add(sk)

print(f"Paired (same stimulus_key): {len(paired)}")
print(f"tick mismatch within pairs: {tick_mismatch} / {len(paired)}")
print(f"turn_index mismatch within pairs: {turn_idx_mismatch} / {len(paired)}")

random.seed(42)
sample = random.sample(paired, min(10, len(paired)))
for i, (sk, did_l, did_n, t_l, t_n, lu, nu) in enumerate(sample, 1):
    print(f"\n=== sample {i} | stimulus={sk} ===")
    print(f"[no-LoRA  tick={t_n}]  {nu}")
    print(f"[LoRA-on  tick={t_l}]  {lu}")

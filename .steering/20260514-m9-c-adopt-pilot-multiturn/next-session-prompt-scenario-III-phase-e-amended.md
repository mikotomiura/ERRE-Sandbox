# Next-session handoff prompt — Phase E A-6 amended path (Scenario III 採用時)

**作成**: 2026-05-14 (採取後 Scenario III 確定時に commit)
**前提**: m9-c-adopt-pilot-multiturn investigation PR (DA-13 ADR、本 PR) で
**Scenario III (mixed)** が verdict 確定。両因子寄与認定 → multi-turn protocol +
retrain v2 を combine する amended Phase E A-6。
**branch**: 新規 `feature/m9-c-adopt-phase-e-a6-amended` を main から切る。

---

```
M9-C-adopt の **Phase E A-6 amended path** を実行する。
m9-c-adopt-pilot-multiturn investigation PR (DA-13 ADR Scenario III) で
methodology confound と LoRA failure の **両者** が部分寄与と判定 →
multi-turn protocol + retrain v2 を combine した amended Phase E A-6 を実行。

## 目的 (本セッション内で完遂)
1. **DA-9 retrain v2 spec amendment**: stimulus prompt diversity 改善 +
   min_examples 3000 + rank=8 fixed (Scenario II と同) + multi-turn dialog
   training data 比率を上げる (Phase B では single-turn 的 utterance が
   training data の majority)
2. retrain v2 (本 spec で kant) → Phase E A-6 multi-turn full Tier B 採取
   (`tier_b_pilot.py` `--multi-turn-max 6` で full battery 採取)
3. DA-1 4 軸 intersection 再評価 → ADOPT-CHANGES / ADOPT 確定
4. nietzsche / rikyu に同 spec 展開 (Phase C)

## 最初に必ず Read する file (内面化必須)
1. `.steering/20260513-m9-c-adopt/decisions.md` DA-9 + DA-12 + **DA-13** (Scenario III verdict)
2. `.steering/20260514-m9-c-adopt-pilot-multiturn/da1-matrix-multiturn-kant.json`
3. `.steering/20260514-m9-c-adopt-pilot-multiturn/report.md` (Scenario III 寄与の root cause analysis)
4. M9-eval P3 stimulus 拡張 reference

## scope
- DA-9 retrain v2 spec の **amendment**:
  - min_examples 1000 → 3000
  - rank=8 fixed
  - **multi-turn dialog training data 比率を上げる** (新規)
  - stimulus prompt diversity 改善
- training v2 amended (kant only first)
- Phase E A-6 multi-turn full Tier B 採取 + DA-1 4 軸 再評価

## NOT in scope (本セッション)
- nietzsche / rikyu の amended retrain v2 (kant ADOPT 後)
- Phase D
```

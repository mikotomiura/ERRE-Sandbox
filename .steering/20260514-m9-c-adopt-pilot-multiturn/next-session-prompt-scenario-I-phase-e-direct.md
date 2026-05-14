# Next-session handoff prompt — Phase E A-6 direct path (Scenario I 採用時)

**作成**: 2026-05-14 (採取後 Scenario I 確定時に commit)
**前提**: m9-c-adopt-pilot-multiturn investigation PR (DA-13 ADR、本 PR) で
**Scenario I (reversal confirmed)** が verdict 確定。methodology confound が
direction failure の主要因と認定 → retrain v2 をスキップして Phase E A-6
multi-turn full Tier B に直行する。
**branch**: 新規 `feature/m9-c-adopt-phase-e-a6-direct` を main から切る。

---

```
M9-C-adopt の **Phase E A-6 direct path** を実行する。
m9-c-adopt-pilot-multiturn investigation PR (DA-13 ADR Scenario I) で
multi-turn pilot data が baseline と direction align することを empirical 確認、
retrain v2 を skip して **rank=8 既存 archive** を Phase E full 7500-turn
multi-turn Tier B 採取で再評価する。

## 目的 (本セッション内で完遂)
1. rank=8 既存 archive (`data/lora/m9-c-adopt/archive/rank_8/kant/`) を
   `data/lora/m9-c-adopt/kant_r8_real/` に **production placement** + manifest
   backfill (`is_mock=false`)
2. Phase E A-6 multi-turn full Tier B 採取 (3 persona × 5 run × 500 turn = 7500
   turn、~6-8h G-GEAR overnight)
3. DA-1 4 軸 intersection を full Tier B data で再評価、ADOPT-CHANGES /
   ADOPT 確定

## 最初に必ず Read する file (内面化必須)
1. `.steering/20260513-m9-c-adopt/decisions.md` DA-1 / DA-9 / DA-12 / **DA-13** (Scenario I verdict)
2. `.steering/20260514-m9-c-adopt-pilot-multiturn/da1-matrix-multiturn-kant.json`
3. `.steering/20260514-m9-c-adopt-pilot-multiturn/report.md`
4. `scripts/m9-c-adopt/tier_b_pilot.py` (multi-turn 拡張済、Phase E でも再利用)
5. `scripts/m9-c-adopt/da1_matrix_multiturn.py` (full Tier B でも再利用)

## scope
- (Phase E A-6 設計詳細は `.steering/20260513-m9-c-adopt/design-final.md` A-6 参照)
- nietzsche / rikyu の同 protocol full Tier B も含む (3 persona × 5 run × 500 turn)
- production placement: `kant_r8_real` (rank=8 carry-over from DA-12 provisional)
- Phase D (`MultiBackendChatClient`) は Phase E 完了後

## NOT in scope (本セッション)
- Phase D live path 統合
- production loader `_validate_adapter_manifest()` (Phase F)
- FSM smoke 24 cell (Phase E 後段)
- training v2 (DA-13 Scenario I で skip 確定)
```

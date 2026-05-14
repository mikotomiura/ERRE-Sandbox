# Next-session handoff prompt — retrain v2 path (Scenario II 採用時)

**作成**: 2026-05-14 (採取後 Scenario II 確定時に commit、本 PR で採用された後続経路)
**前提**: m9-c-adopt-pilot-multiturn investigation PR (DA-13 ADR、本 PR) で
**Scenario II (literal) + Backend Confound Discovery (interpretation)** が
verdict 確定。DA-12 "direction failure" は実は backend confound (Ollama vs
SGLang で Vendi +2.14 / Burrows +5.39) が dominant、LoRA 自体の Vendi/Burrows
への寄与は near-zero (±0.05〜+0.45)。Phase E A-6 を fire する前に、**proper
SGLang-on-base baseline** で評価できる新 LoRA を retrain する必要。
**branch**: 新規 `feature/m9-c-adopt-retrain-v2` を main から切る。

---

```
M9-C-adopt の **retrain v2 path** を実行する。
m9-c-adopt-pilot-multiturn investigation PR (DA-13 ADR Scenario II) で
multi-turn pilot data でも direction failure が再現、LoRA が IPIP self-report
neutral midpoint を実質 shift しない (本来の LoRA failure) と判定 →
DA-9 retrain v2 spec で再 training する。

## 目的 (本セッション内で完遂)
1. **min_examples 1000 → 3000** (DA-3 MEDIUM-6 BIG5-CHAT 1/30 規模に近づける)
2. **rank=8 固定** (provisional carry-over)
3. **stimulus prompt diversity 改善** (M9-eval P3 で新規 prompt 群追加 OR
   per-turn token length / persona 自己言及比率 / 対話 vs 独白比率 を
   training data 側で diversify)
4. retrain 後 multi-turn pilot 再採取 + DA-1 4 軸 intersection で再評価
5. ADOPT 判定なら Phase E A-6、direction failure 再現なら Phase E direct
   (Scenario IV path 移行)

## 最初に必ず Read する file (内面化必須)
1. `.steering/20260513-m9-c-adopt/decisions.md` DA-9 (retrain v2 spec) +
   **DA-13** (Scenario II verdict)
2. `.steering/20260514-m9-c-adopt-pilot-multiturn/da1-matrix-multiturn-kant.json`
3. M9-C-spike `decisions.md` CS-3 (operational SLO 1000 examples) +
   training script `training/train_kant_lora.py` の generic 化
4. M9-eval P3 stimulus 拡張の reference (`golden/stimulus/kant.yaml` +
   `_schema.yaml`)

## scope
- training v2 (kant only first):
  - source: M9-eval P3+ extended stimulus 採取 (~3000 turn target)
  - rank=8 fixed
  - peft / unsloth どちらかは PR #163 K-β 同 setup で固定 (PEFT)
  - `data/lora/m9-c-adopt-v2/kant_r8_v2/` に出力
- multi-turn pilot 再採取 (本 PR 拡張済 driver `tier_b_pilot.py --multi-turn-max 6` 再利用)
- DA-1 4 軸 intersection 再評価 → ADOPT-CHANGES / ADOPT 確定 OR Scenario IV
  fallback

## ⚠ 重要: DA-9 retrain v2 spec amendment (backend confound 発見後の必須変更)

本 PR の最大の empirical 発見: **direction failure 主因 = backend confound
(Ollama vs SGLang)、NOT LoRA failure**。これに対応する spec amendment:

### 1. **baseline backend を SGLang-on-base に変更** (必須)
- 旧 spec: Ollama qwen3:8b baseline と比較
- **新 spec**: **no-LoRA SGLang base model multi-turn (同 protocol)** と比較
- 既存 artefact `tier-b-pilot-multiturn-kant-nolora-{vendi,burrows,icc}.json`
  (本 PR で採取済) を retrain v2 評価の baseline reference として再利用
- Ollama baseline は historical reference として残すが primary judgment には
  使わない

### 2. **DA-1 thresholds の re-calibration が必要**
- 本 PR multi-turn LoRA-on の Vendi/Burrows は no-LoRA SGLang baseline と
  near-equivalent (LoRA effect ≈ ±0.5)
- 旧 DA-1 thresholds (Cohen's d > 0.3 vs baseline) を SGLang baseline 基準で
  再評価する必要、おそらく **effect size 期待値を緩める** 必要
- または **persona-discriminative signal を training data 側で強化** することで
  effect size を底上げする

### 3. **training data の persona-discriminative signal 強化**
- 旧 spec: min_examples 1000 (operational SLO)
- **新 spec**: min_examples 3000 + 以下の diversity 向上策:
  - per-turn token length 分布の均質化 (現状 short utterance に偏る可能性)
  - persona 自己言及比率 up (現状の training data に Kant 様 style がどれだけ
    含まれるかを measure し、3000-example time に explicit に bias)
  - 対話 vs 独白比率の調整
  - stimulus prompt diversity 改善 (M9-eval P3 新規 prompt 群追加)

### 4. **retrain 後の再評価 protocol**
- multi-turn pilot 再採取 (`tier_b_pilot.py --multi-turn-max 6 --rank 8` で
  retrain LoRA を pin して採取)
- 比較: retrain LoRA-on multi-turn SGLang vs no-LoRA SGLang baseline (本 PR
  artefact)
- 期待 direction: Vendi reduction (LoRA-on < no-LoRA SGLang)、Burrows reduction
  (LoRA-on < no-LoRA SGLang)、ICC(A,1) increase

## NOT in scope (本セッション)
- nietzsche / rikyu の retrain v2 (Phase C)
- Phase D (`MultiBackendChatClient`)
- Phase E A-6 (retrain v2 ADOPT 後)
```

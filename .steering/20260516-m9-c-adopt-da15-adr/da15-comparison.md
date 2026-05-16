# DA-15 V1 vs V2 comparison — hybrid 候補抽出

> **生成**: main agent (V1) と Task tool Plan subagent (V2) が独立に生成した
> draft を diff。V1 anchor leak を構造的に避けるための subagent dispatch は
> `decisions.md` DI-2 に記録。

## 1. 結論レベル

| 項目 | V1 | V2 | 同/異 |
|---|---|---|---|
| 採用案 | Plan A → Plan B → Plan C sequential | Plan A → Plan B sequential、Plan C は Phase E migrate | **異** — V2 のほうが scope narrowing が strict |
| Plan C 評価 | "sequential 最後の fallback" として残す | "DA-15 scope 外、Phase E A-6 へ移管" | **異** — V2 が明示的に Phase E へ defer |
| HIGH-3 グレーゾーン解釈 | Plan A は HIGH-3 grey-zone (Codex に投げる) | Plan A は pre-authorised (DA-14 spec で literal 認証済) | **異** — V2 が決定打を提示 |
| cheapest first 経済合理性 | OK | OK | 同 |
| Plan A の Burrows 限界 | 暗黙 | 明示 (Burrows は kernel-swap で動かない) | **異** — V2 のほうが厳密 |
| Plan B が C1-C4 を address する範囲 | C1 のみ (de mass 補強) と限定 | C1 + C2 + C3 + C4 すべて部分 address (≥60 token, monolog, marker-dense filter) | **異** — V2 のほうが包括的 |

## 2. 各 Plan の数値見積差分

### Plan A (Vendi kernel swap)

| 項目 | V1 | V2 | 採用 |
|---|---|---|---|
| compute 見積 | ~15-30min | 1-2h (download + 3-kernel rescoring + bootstrap CI) | **V2** (実 download + bootstrap を含めると 1-2h が現実的) |
| predicted Vendi d 改善幅 | -0.3 to -0.7 | -0.3 to -1.2 (multilingual-e5)、-0.2 to -0.6 (philosophy BERT) | **V2** (multilingual encoder のほうが上限期待が広い、kernel diversity を細分化) |
| code change scope | "embedding model 引数追加" 一般 | `vendi.py:294-322` `_load_default_kernel` hardcode + `compute_baseline_vendi.py:188` の 2 ファイル ~50 LOC | **V2** (具体的 file 行番号特定) |
| HIGH-3 grey-zone | Open question (Codex に投げる) | Pre-authorised (DA-14 spec の `vendi_fail_but_others_pass → ESCALATE_DA15_vendi_kernel_swap`) | **V2** (V1 は DA-14 spec 読み込み不足) |
| Plan A 単独 kant ADOPT 可能性 | 暗黙、Burrows も pass 必要と想定 | 明示: Vendi-swapped pass + ICC pass = 2-of-3 で **kant ADOPT 充足** | **V2** (DA-14 quorum_rule.kant = "2_of_3_primary" の正確な解釈) |

### Plan B (Candidate C targeted hybrid)

| 項目 | V1 | V2 | 採用 |
|---|---|---|---|
| compute 見積 | ~22h | ~25h | **V2** (shard generation + recapture を separated 計算) |
| B-1 vs B-2 分解 | あり (cheap filter vs expensive collector) | なし (一体で ~25h) | **V1 補完** — Step 0 feasibility scan の結果を **V2 に B-1/B-2 sub-option として追加** すべき |
| C1-C4 address | C1 のみ (V1 が C2-C4 を見落とした) | C1, C2, C3, C4 すべて部分 address | **V2** |
| Burrows 改善予測 | 0.43% → 5% を線形外挿で 0.4d 程度 | +1 to +4 pp、5% 達成は CI lower > 0 にかかる | **V2** (より conservative) |
| 不到達 risk | mentioned | 明示: "fundamental capacity ceiling at rank=8" 可能性で double-fail risk | **V2** |

### Plan C (Longer / rank拡大)

| 項目 | V1 | V2 | 採用 |
|---|---|---|---|
| 採用判断 | sequential 最後の選択肢 | DA-15 scope 外、Phase E A-6 へ migrate | **V2** (overfit signal が longer training を contraindicate) |
| max_steps=8000 vs rank=16 分解 | 一括 | 分解、前者は overfit 加速、後者は VRAM risk 別 | **V2** |
| predicted Vendi d | -0.1 to -0.4 (V1) | -0.1 to +0.2 (max_steps=8000) / -0.3 to -0.8 (rank=16) | **V2** (overfit を考慮して max_steps の predicted を悪化させる) |
| compute envelope | 32-48h (V1)、48-64h 上限保守見積 | 20-32h (V2)、rank=16 で VRAM 12 GB margin 超過 risk | **V2** (DI-7 の wall time 16h を線形外挿) |

## 3. V1 と V2 で共通する重要 finding

- DA-14 thresholds は **不変** (HIGH-3 遵守)
- Plan A → Plan B sequential が cheapest-first で経済合理
- Plan C は entry point として不適 (overfit signal, capacity 仮説の弱い evidence)
- ICC + throughput はすでに PASS、Vendi+Burrows の magnitude が gating

## 4. V2 にあって V1 になかった重要 finding

1. **DA-14 spec の `ai_decision_protocol` が Plan A を pre-authorise している**
   (`vendi_fail_but_others_pass → ESCALATE_DA15_vendi_kernel_swap`)。これにより
   HIGH-3 グレーゾーンが大幅に縮小、Plan A は "metric methodology shift" として
   pre-blessed と解釈可能。
2. **`vendi.py:294` の `_load_default_kernel` が MPNet を hardcode** している
   ため、Plan A は parameterisation の code change が必要 (~50 LOC)。
3. **Plan A 単独で kant 2-of-3 quorum 充足可能** (Vendi-swapped + ICC = 2)。
   Burrows の +0.43% (5% target 未達) のまま kant ADOPT が成立する経路。
4. **eval_loss step 2000=0.166 → final=0.180** の mild overfit が Plan C-
   longer-training を強く contraindicate (V1 は overfit を Open question 化)。
5. **Plan B の C1-C4 address は実は包括的** — ≥60 token filter で C2、
   monolog stimuli で C3、marker-dense filter で C4 を partial address。V1 の
   "C1 のみ" 評価は under-counting。
6. **6 つの Open Questions (OQ-1 ~ OQ-6)** を Codex 向けに pre-structured。

## 5. V1 にあって V2 になかった重要 finding

1. **Plan B-1 (cheap filter) vs B-2 (expensive collector) 分解** — Step 0
   feasibility scan で確認した「de-focused monolog generator 未実装」と「natural
   shard 2-turn de pair が 40-60 examples しかない」を踏まえると、B-1 単独で
   250+ 集まらず、**B-2 が事実上必須**。これは V2 の ~25h 見積もりに織り込まれて
   いるが、明示分解がない。
2. **HIGH-3 self-review checklist (本 draft 用)** が V1 に inline 提示されて
   いた。これは ADR 末尾固定の手順を draft 段階で先取り。

## 6. Hybrid 候補抽出

### Hybrid H-α: V2 sequential + Plan B parallel pre-staging

**V2 の Plan A → B sequential 採用**を core にしつつ、Plan A 走行中の dead
time (~1-2h) を使って **Plan B の driver code を pre-stage**:

- Plan A 走行中 (rescore = ~30-60min): `scripts/m9-c-adopt/de_focused_monolog_collector.py` (B-2) の skeleton と group-aware split の拡張を並行実装
- Plan A 結果出てから判断:
  - Plan A pass → B pre-stage は merge せず別 PR で保留 (将来の Phase E で再利用可)
  - Plan A fail → B-2 collector を即起動、~3h G-GEAR で de-focused shards 採取
- **利点**: Plan A 失敗時の startup 時間を ~1.5h 短縮
- **欠点**: Plan A pass 時の pre-stage code が waste。ただし driver code は将来再利用可能なので sunk cost 小

### Hybrid H-β: V2 sequential + Plan B-1 (cheap filter) を同 PR で同梱

Plan A 採用 PR に **Plan B-1 cheap filter (dataset.py の `where language == "de"`
filter + DI-3 cap 解除)** を merged 状態で同梱。Plan A 失敗時に即 retrain
trigger 可能。

- **利点**: Plan A → Plan B-1 escalation が分単位、~16h training で済む
- **欠点**: Plan B-1 単独で de monolog 250+ 集まらない可能性大 (Step 0 finding
  通り、natural shard 2-turn de pair ~40-60 examples)。B-1 を passable と
  誤認すると Plan B-2 へのさらなる escalation が必要になり、PR チェーンが
  伸びる
- **判断**: B-1 単独では不十分な可能性が高いため、H-α (parallel pre-staging)
  のほうが経済合理。**H-α 採用候補**

### Hybrid H-γ: V2 そのまま (sequential 純粋形)

Plan A だけを実装 PR にし、結果を見てから Plan B PR を起票 (driver も含めて
全部その時から)。**最も clean だが時間ロス**。

- **利点**: scope creep ゼロ、ADR/PR 1-to-1
- **欠点**: Plan A 失敗時に + 1.5h driver 実装の dead time が発生

## 7. 最終採用案

**V2 の Plan A → Plan B sequential を core 採用** + **H-α (Plan B driver の
pre-staging を Plan A 走行中の dead time に並行) を operational tactic として
追加**。

理由:
- V2 のほうが DA-14 spec の正確な解釈、code-level discovery、quorum 解釈で
  V1 より strict かつ accurate
- V1 の B-1/B-2 分解は V2 の Plan B 議論に sub-spec として継承する
- H-α は V1/V2 どちらも明示しなかったが、両方の制約を踏まえると最も economic
- Plan C は Phase E A-6 へ migrate (V2 の判断採用)

**確定:** Codex review prompt にはこの H-α 込みの最終案を提示し、HIGH-3
grey-zone (OQ-1) と Plan A 単独 kant ADOPT 妥当性 (OQ-6) を最優先検証項目と
する。

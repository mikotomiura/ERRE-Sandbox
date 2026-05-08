# m9-c-spike — design comparison (v1 vs v2 → hybrid v3 候補)

> v1 (`m9-c-spike-design-v1.md`): infrastructure-first / Kant 1 persona / P3
> 完了待ちで full spike
> v2 (`m9-c-spike-design-v2.md`): fail-fast (mock-LoRA infra proof) +
> diversification (3 persona batch)
>
> 本書は両案を 8 軸で比較し hybrid v3 を提示する。Codex review が起爆。最終
> 解は `m9-c-spike-design-final.md` に記述。

## 軸別比較

### 軸 1. data dependency

| 軸 | v1 | v2 | hybrid v3 |
|---|---|---|---|
| Phase α (infra proof) | 該当なし、P3 待ち | mock-LoRA で 即実行可 | **mock-LoRA で 即実行 (v2 採用)** |
| Phase β (real training) | P3 完了 → Kant 1 persona | P3 完了 → 3 persona batch | **P3 完了 → Kant 1 persona (v1 採用)** |

**v3 selection**: **mock-LoRA Phase α を採用** (data-blocked 時 hedge、本 PR
scope 内で deliverable 1-4 早期 ship 可)。Phase β は Kant 1 persona に戻す
(M9-B 第3の道 ADR continuity)。

### 軸 2. persona scope

| | v1 | v2 | v3 |
|---|---|---|---|
| spike 対象 persona | Kant 1 | Kant + Nietzsche + Rikyū 3 | **Kant 1 (v1)** |
| 3 persona の検討 | M9-C-adopt | 本 spike 内で前倒し | **M9-C-adopt territory に defer** |

**v3 selection**: **Kant 1 persona** 維持 (v1)。M9-B 第3の道 ADR の "bounded,
non-authoritative single-persona Kant LoRA spike" 文言を逐語守る。3 persona
batch は M9-C-adopt 範囲。

### 軸 3. adapter rank

| | v1 | v2 | v3 |
|---|---|---|---|
| rank | rank=8 | rank=4 (multi-persona trade-off) | **rank=8 (v1)** |
| M9-C-adopt 統一 spike との continuity | 整合 | 不整合 | **整合 (v3=v1)** |

**v3 selection**: **rank=8 維持**。M9-C-adopt の "rank=8 統一 spike" と
continuity 確保、本 spike の結果が M9-C-adopt の比較基準として直接使える。

### 軸 4. infrastructure proof timing

| | v1 | v2 | v3 |
|---|---|---|---|
| DB3 fallback 判定材料の早期取得 | P3 完了後 (~weeks) | mock で 即可 | **mock で 即可 (v2)** |
| 早期 unblock value | 低 | 高 | **高** |

**v3 selection**: **mock-LoRA Phase α 採用 (v2)**。Codex P4a 経験で証明された
「**早期検出 = 大幅手戻り防止**」原則。SGLang adapter 機能不全が判明したら
即 vLLM 別タスク fire 可能。

### 軸 5. mock-LoRA の risk

| 観点 | v2 / v3 (mock 採用) |
|---|---|
| SGLang format 拒否リスク | PEFT random-init weight が `/load_lora_adapter` 受付形式に合わない可能性 (Codex 確認必須) |
| quality 誤認リスク | mock を production で誤起動 → DB9 quorum で 100% 排除 (Tier B Vendi で異常 score 検出) |
| infra proof 妥当性 | mock weight でも load/unload mechanism / latency / N=3 同時 / FSM regression は real と同じ → infra proof 成立 |

**v3 selection**: 採用。mock-LoRA を **`tools/spike/` 隔離** (production
`src/` に置かない、誤運用リスク削減)。

### 軸 6. M9-B 第3の道 ADR との整合

| 軸 | v1 | v2 | v3 |
|---|---|---|---|
| ADR 文言 (single-persona Kant) | 完全整合 | 逸脱 (3 persona) | **整合 (v3=v1)** |
| ADR 修正必要性 | 不要 | 必要 (scope 拡張) | **不要** |

**v3 selection**: ADR 整合維持。Phase α (mock-LoRA) は ADR 文言を超えないが、
新規 ADR (CS-N) で本 spike 内 phase 化を justify する必要 (scope 拡張ではなく
phase 内訳)。

### 軸 7. 工数

| | v1 | v2 | v3 |
|---|---|---|---|
| 推定 | 8h | 12h | **11h** (v1 8h + Phase α mock 3h) |
| 早期 unblock value | 低 | 高 | **高** |

**v3 selection**: 11h、Phase α 3h は data-independent で **本 PR 内**または
次セッション初期で完結可、その時点で DB3 fallback 判定材料を確定可能。

### 軸 8. Codex review で v3 を challenge する点

下記を `codex-review-prompt-m9-c-spike.md` に明記:

1. **mock-LoRA の SGLang format compatibility**: random-init or HF hub borrow
   weight で `/load_lora_adapter` 受付するか
2. **rank=8 vs rank=4 の persona expressivity gap**: prior art 2024-2026 で
   何 rank が adequate
3. **adapter swap latency 500ms threshold の妥当性**: 操作上の閾値根拠
4. **N=3 同時 request collapse 検出 protocol**: throughput / latency p99 /
   queue depth 何を測るか
5. **PEFT safetensors → SGLang weight format conversion**: undocumented なら
   自前 conversion script 必要、その妥当性
6. **gradient_checkpointing 採用**: VRAM 9.7-10.2GB を 7.5-8GB に下げる
   trade-off (training time +20-30%)
7. **VRAM headroom 5.8GB の妥当性**: CUDA fragmentation / long-context
   generation で実用上 sufficient か
8. **training data minimum**: P3 完了後 Kant ~2500 turn で sufficient か、
   prior art 確認
9. **dual-machine workflow**: training (HF Transformers) と serving (SGLang)
   が同 G-GEAR 上で run、adapter format 共有が clean か
10. **DB3 fallback 条件 trigger**: >500ms latency / N=3 collapse / FSM
    regression のうち単一 trigger で fallback fire するか、複合か

## v3 hybrid summary (one-paragraph)

**m9-c-spike v3 = Phase α (mock-LoRA infrastructure proof、data-independent、
即実行可、本 PR scope 内 or 次セッション初期で完結) + Phase β (P3 golden
baseline 完了 trigger で Kant 1 persona rank=8 PEFT QLoRA NF4 real training、
SGLang `--enable-lora` + `/load_lora_adapter` 経由で adapter swap latency /
N=3 throughput / FSM regression 実測、DB3 fallback 判定材料生成)**。M9-B
第3の道 ADR (single-persona Kant) と continuity 維持、3 persona batch は
M9-C-adopt territory に defer、rank=8 で M9-C-adopt 統一 spike と continuity。
工数 ~11h (v1 8h + Phase α 3h)。

## 採否判定 matrix

| 軸 | v1 採否 | v2 採否 | v3 採否 |
|---|---|---|---|
| Phase α (mock-LoRA infra proof) | ✗ なし | ✓ あり (v3 と同) | ✓ |
| Phase β persona | ✓ Kant 1 (v3 と同) | ✗ 3 persona (scope 拡張) | ✓ |
| Phase β rank | ✓ rank=8 (v3 と同) | ✗ rank=4 (M9-C-adopt 不整合) | ✓ |
| M9-B 第3の道 ADR 整合 | ✓ 整合 (v3 と同) | ✗ 逸脱 | ✓ |
| 早期 unblock value (Phase α) | ✗ なし | ✓ あり (v3 と同) | ✓ |
| mock 隔離 (`tools/spike/`) | 該当なし | 不明 | ✓ 明示隔離 |
| 工数 | 8h | 12h (v3 11h と近接) | 11h |
| ADR 修正必要性 | 不要 | 必要 | 不要 (新規 CS-N で phase 化 justify) |

v3 が全軸で「最良の選択」を吸収。

## v3 で残す未解決 (Codex 反映後 design-final.md に確定)

- mock-LoRA の SGLang format compatibility 確認結果
- rank=8 で persona-conditional adaptation prior art literature
- adapter swap latency threshold 500ms の literature/operations 根拠
- VRAM 予算実測の必要性 (G-GEAR 実走時に確定)
- dual-machine workflow の adapter format conversion path
- DB3 fallback 条件 (single vs composite trigger)

## v3 effort estimate

| Sub-step | 推定 |
|---|---|
| Phase A: scaffold + requirement.md (済) | 30min |
| Phase B: design-v1.md (済) | 1h |
| Phase C: /reimagine v2 + comparison.md (本書、済) | 1h |
| Phase D: Codex review prompt + execution + 反映 | 1.5h |
| Phase E: design-final + decisions.md ADR | 1h |
| Phase F: tasklist + blockers 整備 | 30min |
| **本セッション合計** | **~5.5h** |
| Phase G: pyproject.toml [training] extras | 30min |
| Phase H: sglang_adapter.py + tests | 2-3h |
| Phase I: mock-LoRA build script + training/ module + prompt builder + dataset + train script + tests | 4h (Phase α 含む、+1h vs v1) |
| Phase J α: G-GEAR mock-LoRA infra proof (data 不要) | 2h |
| Phase J β: G-GEAR real training (P3 完了後): Kant rank=8 PEFT QLoRA + adapter load + latency 実測 | 4-6h |
| Phase K: adapter swap runbook (DB8) + PR | 1h |
| **次セッション以降合計** | **~14-16h** (3 セッション、v1 10-14h より +20%) |

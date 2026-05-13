# 設計案比較 — m9-c-adopt Phase A (v1 / v2 / v3 hybrid)

> `design.md` (v1: 3 persona simultaneous 1 PR + SGLang-only + 4 rank
> sweep) と `design-v2-reimagine.md` (Reim-1: vLLM first-class +
> Reim-2: rank sweep 縮減 + Reim-3: stage gate) を 8 軸で比較し、
> hybrid v3 (採用) の根拠を示す。最終的な hybrid v3 は Codex HIGH 反映後
> に `design-final.md` で fix する。本 file は Codex review 前の **初期
> hybrid 候補** を記述する。

---

## 比較軸一覧

| # | 軸 | v1 (default) | v2 (reimagine) | v3 hybrid (本 plan 候補) |
|---|---|---|---|---|
| 1 | backend 採用順序 | SGLang only + Ollama fallback | SGLang + vLLM + Ollama (3 backend cascade) | SGLang only + Ollama fallback (DB3 re-arm trigger 経由で vLLM 復活) |
| 2 | fallback 戦略 | Ollama degraded (adapter なし) | vLLM secondary → Ollama tertiary | Ollama degraded (v1 維持) |
| 3 | rank sweep 方式 | full sweep {4, 8, 16, 32} | hypothesis-confirm {8, 16} | 部分 sweep {4, 8, 16} (rank=32 除外、VRAM risk 回避) |
| 4 | multi-persona init 方式 | sequential 3 persona, 1 PR | stage gate 3 PR (Reim-3) | sequential 3 persona, 1 PR (user 判断、v1 維持) |
| 5 | Tier B 統合方式 | framework のみ確定、threshold は P4b で empirical pin | 同じ | framework のみ確定 + provisional threshold pin (d≥0.3 / ICC≥0.6 / Burrows≥10% reduce、Codex に問う) |
| 6 | production loader hard block 範囲 | warn → block (CS-9 amendment) | warn → block (両 backend で適用) | warn → block (v1 維持) |
| 7 | VRAM budget | 3 pinned (~8.8GB peak) | 3 pinned + vLLM dual stack (~13GB peak) | 3 pinned (v1 維持) |
| 8 | scope creep risk | 中 (1 PR で 8 topic) | 大 (3 backend dual stack + stage gate) | 中 (v1 + 部分 sweep で v2 の cost 削減のみ取り込む) |

---

## 軸ごとの詳細

### 軸 1: backend 採用順序

- **v1**: SGLang を primary、Ollama を degraded fallback (adapter なし)。
  spike CS-1 / CS-8 amendment で SGLang Linux execution boundary +
  adapter swap 8ms が実証済、DB3 NON-FIRE 確定なので single-vendor
  risk を accept できる前提。
- **v2**: vLLM v0.15+ を first-class secondary に追加し、3 backend
  cascade (SGLang → vLLM → Ollama)。SGLang fragmentation behavior
  (P-LoRA / ServerlessLoRA prior art で documented) が未測のため
  proactive fallback。
- **v3 hybrid**: **v1 採用**。理由:
  - 本 PR scope tight 優先 (Phase A は設計のみ、実装 Phase B-G で
    backend を増やすと PR 数 / 検証 surface 倍増)
  - DB3 re-arm trigger (SGLang launch fail 3 連続 OR adapter load
    p99 > 500ms 24h sustained OR Tier B quorum 0-of-3) で vLLM
    migration を別 PR で扱える
  - spike 実測 (8ms / 60x margin / CS-7 NON-FIRE) が SGLang を
    operational-ready と支持

### 軸 2: fallback 戦略

- **v1**: SGLang unreachable → Ollama 自動 degrade、`degraded_to_ollama=
  True` flag を `CycleResult` に記録。adapter なし (base qwen3:8b)、
  persona system prompt のみで継続。
- **v2**: SGLang fail → vLLM secondary に switch (adapter 維持可能)、
  vLLM も fail → Ollama tertiary (adapter なし)。
- **v3 hybrid**: **v1 採用** (軸 1 と整合)。ただし Codex に "vLLM を
  late-binding option として保持できるか" を MEDIUM finding で問う
  (DA-2 re-open 条件として記録)。

### 軸 3: rank sweep 方式

- **v1**: rank ∈ {4, 8, 16, 32} の sequential sweep、24h compute、
  Tier B Vendi saturate floor + ICC ≥ 0.6 + throughput floor の
  3 軸 intersection で採用 rank 決定。棄却 rank は archival。
- **v2**: rank=8 hypothesis-confirm + rank=16 単点、10h compute、
  rank=4 / rank=32 は scope 外。
- **v3 hybrid**: **部分 sweep {4, 8, 16}** (3 値、18h compute):
  - rank=32 を **除外** (VRAM headroom 7.3GB を圧迫、CS-4 budget
    超過リスク、cost-benefit poor)
  - rank=4 / 8 / 16 は LoRA Land / P-Tailor で common practice 範囲、
    literature と比較可能性保持
  - 採用基準は v1 と同じ 3 軸 intersection
  - empirical sweep で CS-5 closure を保ちつつ compute 25% 削減
  - 6h 削減により Phase B → C の overall roadmap が早期化

### 軸 4: multi-persona init 方式

- **v1**: 3 persona (kant/nietzsche/rikyu) を 1 PR で sequential 訓練、
  同 1 PR で adopt 判定。
- **v2 (Reim-3)**: 3 persona を stage gate 3 PR に分割、各 persona で
  1 week soak。
- **v3 hybrid**: **v1 採用** (user 判断確定)。理由:
  - user が事前に "1 PR で 3 persona 同時 adopt 判定" を選択
  - stage gate は roadmap delay (~10-12 week) + PR overhead 大、
    M9-D 着手の遅延
  - early-warning の attribution 困難性は monitor + audit log で
    mitigate 可能 (DA-6 audit log)

### 軸 5: Tier B 統合方式

- **v1**: framework のみ確定 (DB9 quorum + ME-14 BootstrapPair)、
  empirical threshold (Vendi effect size / ICC / Burrows reduction%)
  は P4b 完了後の DA-11+ で pin。
- **v2**: 同じ。
- **v3 hybrid**: **provisional threshold pin** を提案、Codex に
  HIGH/MEDIUM 判定を求める。pin 値:
  - Vendi effect size (Cohen's d) ≥ 0.3 (literature small shoulder)
  - Big5 ICC(C,k) ≥ 0.6 (ME-11 fallback shoulder、ME-14 primary 適用)
  - Burrows Δ reduction ≥ 10% (Burrows 1987 / Eder 2016 で 5-15% が
    discriminative shoulder)
  - rikyu Burrows N/A 時は 2-of-2 fallback (DA-8)
  - marginal pass (0.3 ≤ d < 0.5 / 0.6 ≤ ICC < 0.7) は ADOPT-WITH-CHANGES
    (DA-9 retrain path)
  - 理由: A-8 verdict を本 PR で出すなら threshold が必要、provisional
    pin で operational に進め、P4b 完了後に DA-11+ で final tighten

### 軸 6: production loader hard block 範囲

- **v1**: `inference/server.py` の `load_adapter()` で `weight_path
  NOT IN data/lora/m9-c-adopt/` OR `is_mock=True` → `ProductionLoaderRejectError`。
- **v2**: 同じ ruleを SGLang / vLLM 両 backend に適用 (backend-agnostic
  validator)。
- **v3 hybrid**: **v1 採用** (軸 1 と整合)。vLLM が後で first-class
  になる場合は DA-6 re-open。

### 軸 7: VRAM budget

- **v1**: 3 adapter pinned + base ~8.7GB + adapter 3 × 30MB = ~8.8GB
  peak、headroom ~7GB。
- **v2**: SGLang + vLLM dual stack で VRAM ~13GB peak、headroom 3GB
  (rank=8 想定)。rank=16 で peak が 16GB 近接の可能性、operational
  ではない。
- **v3 hybrid**: **v1 採用** (軸 1 と整合)。rank=32 を sweep から除外
  することで rank=16 採用時の VRAM peak headroom を保つ (軸 3 と整合)。

### 軸 8: scope creep risk

- **v1**: 8 topic × 1 PR + 設計のみで Phase A は 3-4h、Phase B-G ~6 week。
- **v2**: 3 backend dual stack + 3 PR stage gate で Phase A 自体は
  同じだが Phase B-G が ~10-12 week + PR 数 3 倍、Codex review 回数
  3 倍。
- **v3 hybrid**: **v1 + 部分 sweep のみ採用**、v2 の cost-saving 部分
  (rank=32 除外) のみ取り込み、scope creep を最小化。

---

## 採用 hybrid v3 (Codex review 前の初期候補)

**3 persona simultaneous 1 PR + SGLang-only + 3 rank sweep
({4, 8, 16}) + provisional Tier B threshold pin**

| 構成要素 | 採用 | 出典 |
|---|---|---|
| backend 採用 | SGLang only + Ollama fallback | v1 |
| rank sweep 範囲 | rank ∈ {4, 8, 16} (rank=32 除外) | v2 Reim-2 の部分採用 |
| multi-persona init | sequential 3 persona, 1 PR | v1 (user 判断) |
| Tier B threshold | provisional pin (d≥0.3, ICC≥0.6, Burrows≥10%) | hybrid (Codex 判定待ち) |
| production loader | hard block + audit log | v1 |
| FSM smoke | 24 cell (8 mode × 3 persona) | v1 |
| ADR 数 | DA-1..DA-10 | v1 |

**hybrid v3 の compute budget**: rank sweep 18h (v2 cost-saving 採用)、
Phase E Tier B 29h、合計 G-GEAR 実走 ~47h (overnight × 5-6 night)。
v1 default 24h + 29h = 53h より 6h (10%) 削減、scope は v1 と等価。

**Codex review で確認したい点**:

1. **rank=32 除外の妥当性** (HIGH/MEDIUM 判定): VRAM headroom 圧迫
   リスクと cost-benefit poor の判断が literature shoulder と整合か
2. **provisional Tier B threshold pin** (HIGH/MEDIUM 判定): d≥0.3 /
   ICC≥0.6 / Burrows≥10% reduce が persona-discriminative shoulder
   として operational か、P4b empirical pin まで defer すべきか
3. **vLLM late-binding 保持** (MEDIUM): SGLang single-vendor risk を
   accept する判断が DB3 re-arm trigger だけで十分か、本 PR で vLLM
   path skeleton を残す価値があるか
4. **rikyu Burrows N/A の 2-of-2 fallback** (MEDIUM): persona ごとに
   quorum 数を変えるのは structural anomaly、tokenizer 実装を hard
   blocker 化すべきか

---

## 軸ごとの risk summary

| 軸 | v3 hybrid 採用 risk | mitigation |
|---|---|---|
| 1. backend | SGLang single-vendor risk | DA-2 re-open 条件 + DB3 re-arm trigger |
| 2. fallback | Ollama degraded で adapter なし | Phase G で soak 観察、user-facing flag |
| 3. rank sweep | rank=32 を見ない (CS-5 留保) | DA-1 re-open 条件で rank=32 追加 sweep 可能 |
| 4. multi-persona | 3 persona 同時で blast radius | audit log + bootstrap order monitor |
| 5. Tier B threshold | provisional pin が strict すぎる | DA-9 marginal pass = ADOPT-WITH-CHANGES |
| 6. production loader | spike code path bypass で誤運用 | DA-6 re-open 条件 + audit log |
| 7. VRAM budget | rank=16 で peak ~9.5GB headroom 6.5GB | Phase B 早期 OOM monitor |
| 8. scope creep | 8 topic 1 PR で reviewer 負担 | PR description で HIGH 反映マッピング表 + Mac master review 待ち |

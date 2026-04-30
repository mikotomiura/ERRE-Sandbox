# Tasklist — M9-B LoRA Execution Plan

## このファイルについて

M9-B 自身の closure tasklist + 後続 3 タスク (M9-eval-system / M9-C-spike / M9-C-adopt) の
**implementation tasklist** を dependency 順 + 工数 (S/M/L) + 先決 ADR 付きで整理。

工数: S = 1 セッション以内, M = 1-2 セッション, L = 2+ セッション

## Phase A: M9-B closure (本タスク内)

### 設計成果物
- [x] requirement.md 確定 [先決: なし] [S]
- [x] research-evaluation-metrics.md (J0 文献調査) [先決: なし] [S]
- [x] design-v1.md (Claude 初回案) [先決: requirement] [S]
- [x] design-v2.md (/reimagine 再生成案、v2-B 評価基盤先行) [先決: v1] [S]
- [x] design-comparison.md (v1/v2/hybrid 比較) [先決: v1, v2] [S]
- [x] codex-review-prompt.md 起草 [先決: comparison] [S]
- [x] codex exec 実行 + codex-review.md verbatim 保存 [先決: prompt] [S]
- [x] design-final.md (v3 hybrid: HIGH 4 + 第 3 の道) [先決: codex review] [S]
- [x] decisions.md (DB1-DB10 ADR、5 要素) [先決: design-final] [S]
- [x] blockers.md (LOW + 不確実性記録) [先決: decisions] [S]
- [x] tasklist.md (本ファイル、handoff 用) [先決: 全成果物] [S]

### 後続タスク scaffold 起こし
- [ ] `.steering/[YYYYMMDD]-m9-eval-system/` scaffold 作成 [S] [先決: tasklist]
- [ ] `.steering/[YYYYMMDD]-m9-c-spike/` scaffold 作成 [S] [先決: tasklist]
- [ ] `.steering/[YYYYMMDD]-m9-c-adopt/` scaffold 作成 (M9-eval-system 完了後でも可) [S]

### 検証
- [ ] `git diff src/ godot_project/` が空であることを確認 [S]
- [ ] design-final.md を /clear 後 Read で独立に理解可能か self-review [S]
- [ ] 受け入れ条件 9 項目を requirement.md と照合 [S]

### コミット
- [ ] feature branch 切る (`docs/m9-b-lora-execution-plan`) [S] [先決: 検証]
- [ ] 全 .md commit + PR 作成 [S]
- [ ] PR description に codex-review.md リンク + DB1-DB10 サマリ [S]

---

## Phase B: M9-eval-system (新タスク, M9-B 後)

**前提**: DB1-DB10 を読み込み、design-final.md の Tier 構造に従って実装。

### Tier 0: Parquet pipeline 基盤
- [ ] raw_dialog/ schema 実装 (metric-free table) [M] [先決 ADR: DB5]
- [ ] metrics/ sidecar schema 実装 (tier/metric_name/value) [M] [DB5]
- [ ] training-view contract 実装 (`evaluation_epoch=false` only loader) [M] [DB5/DB6]
- [ ] partition 構造 + writer / reader [M] [DB5/DB6]
- [ ] migration: 既存 episodic_log / dialog_turn を新 schema に変換 [L] [DB5]

### Tier A: per-turn metric (cheap)
- [ ] LIWC license 評価 + alternative decision (Empath/spaCy/custom) 確定 [先決: DB10、blockers.md] [M]
- [ ] LIWC or alternative dictionary 統合 [M] [DB10]
- [ ] Burrows' Delta to thinker reference 実装 (per-language) [M] [DB10、blockers.md]
- [ ] Burrows reference corpus 整備 (Kant Critique / Nietzsche Zarathustra / Rikyu Nampōroku) [L] [DB10]
- [ ] MATTR (streaming) [S] [DB10]
- [ ] semantic novelty (MPNet sentence embedding distance) [M] [DB10]
- [ ] persona_contradiction_rate (NLI head) [M] [DB10]
- [ ] Tier A pipeline 統合 (per-turn ~50ms 目標) [M] [全 Tier A]

### Tier B: per-100-turn metric (medium)
- [ ] Vendi Score (semantic kernel、200-turn rolling window) [M] [DB10]
- [ ] IPIP-NEO-120 questionnaire administration via local 7B-Q4 [M] [DB10]
- [ ] Big5 stability ICC (across-mode) [M] [DB10]
- [ ] Tier B scheduling (per-100-turn trigger) [S] [DB6]

### golden baseline 採取
- [ ] golden baseline run 設計 (3 persona × 5 run × 500 turn) [M] [DB10]
- [ ] baseline 採取実行 + persistent 保存 [L]
- [ ] baseline curve 分析 (N=3 漸近線、blockers.md "観測点") [M]

### golden set 整備
- [ ] golden set technical spec 起草 (100/persona seed) [S] [DB10]
- [ ] Kant 100 reference utterances 抽出 (Critique 等) [L]
- [ ] Nietzsche 100 reference utterances 抽出 (Zarathustra 等) [L]
- [ ] Rikyu 100 reference utterances 抽出 (Nampōroku 等) [L]

### Tier C: per-session offline metric (expensive)
- [ ] judge LLM 選定 (Prometheus 2 vs Qwen2.5-72B) [M] [DB10、blockers.md]
- [ ] judge bias mitigation runbook 起草 [M] [blockers.md]
- [ ] Prometheus 2 rubric assessment 実装 (CharacterBench 6-aspect) [L] [DB10]
- [ ] G-Eval logit-weighted scoring 実装 (Wachsmuth Toulmin) [L] [DB10]
- [ ] FANToM-adapted ToM probe (chashitsu info-asymmetric pair) [L] [DB10]
- [ ] ROSCOE on reasoning trace [M] [DB10]
- [ ] nightly batch slot を autonomous loop に組込 [M] [DB6]

### eval pipeline 自動化
- [ ] persona-conditional gate 実装 (DB9 quorum logic 前提) [M] [DB9]
- [ ] dashboard 構築 (Tier A-C metric 可視化) [L]
- [ ] synthetic 4th persona test fixture 追加 [S] [DB7、LOW-1]

### M9-eval-system 完了確認
- [ ] golden baseline 採取完了
- [ ] Tier A 全実装、Tier B Vendi+ICC 実装完了 (DB9 sub-metric 3 個揃う)
- [ ] design-final.md「数値 gate サマリ」の `eval ready` 条件達成

---

## Phase C: M9-C-spike (新タスク, **M9-eval-system と並行**)

**前提**: codex review final note の第 3 の道。bounded, non-authoritative single-persona spike。
adoption 判断は M9-eval-system 完成後の post-spike re-eval で行う。

### SGLang LoRA runtime 動作確認
- [ ] SGLang `--enable-lora` + `--max-loras N` + `--max-lora-rank R` 起動 [M] [DB3]
- [ ] dummy adapter で `/load_lora_adapter` REST endpoint 動作確認 [S] [DB3]
- [ ] adapter unload / reload 動作確認 [S] [DB3]
- [ ] SGLang LoRA documentation 実装と差分 (codex cited docs) [S] [DB3]

### Kant LoRA 学習 spike
- [ ] training environment 整備 (HF Transformers + PEFT、暫定 DB2) [M] [DB1/DB2]
- [ ] Kant dialog_turn を training data として抽出 (`evaluation_epoch=false` のみ) [S] [DB5]
- [ ] QLoRA NF4 + rank=8 で Kant LoRA 学習 (1 epoch) [M] [DB1]
- [ ] adapter を SGLang format に変換 [S]
- [ ] SGLang に load + inference 動作確認 [S] [DB3]

### 実測値採取
- [ ] adapter swap latency 実測 (Kant ↔ base) [S] [DB3 re-open 条件]
- [ ] cold start latency 実測 [S] [DB3]
- [ ] N=3 同時 request throughput 実測 (mock 3 persona、Kant adapter のみ実物) [M] [DB3 re-open 条件]
- [ ] M5 resonance / ERRE FSM が SGLang LoRA 経路で regression していないか確認 [M] [DB3]

### vLLM fallback 判断
- [ ] DB3 re-open 条件 (latency >500ms / throughput collapse / regression) を実測値で判定 [S]
- [ ] vLLM fallback fire 条件成立 → vLLM migration plan 起草 (別タスク) [M、条件分岐]
- [ ] 条件未成立 → SGLang continued、runbook 起草へ [S]

### runbook 起草
- [ ] adapter swap runbook (DB8) を実測値込みで起草 [M] [DB8]

### M9-C-spike 完了確認
- [ ] SGLang LoRA endpoint 全動作確認
- [ ] Kant adapter spike 学習 + load + inference 動作
- [ ] adapter swap latency / throughput / regression measure 完了
- [ ] **non-authoritative 明文化**: spike 結果のみで adoption しないことを文書化
- [ ] M9-C-spike が「明らかに人間目視で改善」した場合の judgment protocol を blockers.md に追記

---

## Phase D: M9-C-adopt (M9-eval-system + M9-C-spike + 評価系 ready 達成後)

**前提**: 以下すべてが揃ってから着手:
1. M9-eval-system 完了 (golden baseline + Tier B 実装)
2. M9-C-spike 完了 (SGLang LoRA runtime 動作確認 + Kant spike)
3. DB4 trigger 条件成立 (`floor AND (coverage 300/persona OR plateau OR timebox)`)

### Library 最終選定
- [ ] PEFT vs unsloth spike (rank=8、Kant) [M] [DB2]
- [ ] 学習速度 / 品質 / SGLang 互換性で選定 [S] [DB2]

### 3 persona LoRA 展開
- [ ] Nietzsche LoRA 学習 [M] [DB1/DB2]
- [ ] Rikyu LoRA 学習 [M] [DB1/DB2]
- [ ] 3 adapter を SGLang に同時 load (`--max-loras 3`) [S] [DB3/DB8]

### 双方向 drift gate 実装
- [ ] bootstrap CI 計算 (Tier B sub-metric 3 個) [M] [DB9]
- [ ] 2-of-3 quorum logic 実装 [M] [DB9]
- [ ] defensive canary (即時 rollback) 実装 [S] [DB9]
- [ ] adoption gate (initial floor / subsequent quorum / 3-fail discard) 実装 [M] [DB9]
- [ ] auto rollback mechanism 実装 [M] [DB9]

### LoRA 効果評価
- [ ] pre-LoRA baseline (M9-eval-system 採取済) と post-LoRA を比較 [M]
- [ ] Tier A-C 全 layer での比較レポート [M]
- [ ] persona-conditional gate (DB10) で adoption 判定 [S] [DB10]

### M9 milestone 完了確認
- [ ] 3 persona LoRA adapter が SGLang で運用可能
- [ ] 双方向 drift gate が機能
- [ ] adoption / rollback decision が文書化
- [ ] M10 (N=4 拡張 / agora 主体) への handoff 文書化

### 専門家 review 準備 (M9-C-adopt 直前)
- [ ] 3 persona × 1 専門家 selection [L] [blockers.md]
- [ ] 報酬 / 公開的位置づけ確定 [S]
- [ ] qualitative review session 実施 [M]

---

## Cross-cutting / 並行運用

### memory 更新
- [ ] M9-B closure 時に MEMORY.md に entry 追加 (project_m9_b_merged.md 仮称) [S]
- [ ] codex review HIGH 4 件反映の記録 [S]
- [ ] 第 3 の道採用の記録 [S]

### docs 更新
- [ ] docs/architecture.md に LoRA / serving section 追加 (DB3 SGLang-first) [M] [M9-eval-system 後]
- [ ] docs/development-guidelines.md に evaluation_epoch 運用ルール追記 [S] [DB6]
- [ ] CLAUDE.md / AGENTS.md は変更なし (本タスクは docs only)

### Plan→Clear→Execute ハンドオフ
- [ ] M9-B 完了 commit 後、context 使用率確認 [S]
- [ ] >30% なら次セッション開始時に design-final.md + decisions.md を Read してから着手 [S]

---

## 依存関係グラフ (高レベル)

```
M9-B (本タスク, plan only)
  ├ requirement → research → design-v1 → design-v2 → comparison → codex review → final/decisions/blockers/tasklist
  └ scaffold 3 後続タスク

  ↓

M9-eval-system  ←─並行─→  M9-C-spike (bounded, non-authoritative)
  (Tier 0/A/B/C/D 実装 +              (SGLang LoRA runtime 動作確認 +
   golden baseline +                   Kant spike + 実測値採取 +
   golden set + dashboard)             vLLM fallback 判断)

       ↓                                    ↓
       └──────────────┬─────────────────────┘
                      ↓
                M9-C-adopt
              (前提: 評価系 ready + spike 完了 + DB4 trigger 成立)
              (3 persona LoRA + 双方向 drift gate + adoption 判定)

                      ↓
                      M10 (N=4 / agora 主体)
```

## 想定 timeline (solo cadence)

| Phase | 工数推定 | calendar |
|---|---|---|
| M9-B | 0.5 セッション (ほぼ完了) | done |
| M9-eval-system | 4-6 セッション | ~2 weeks |
| M9-C-spike | 2-3 セッション (並行) | ~1 week (M9-eval-system overlap) |
| M9-C-adopt | 3-4 セッション | ~1.5 weeks |
| **M9 total** | **9-13 セッション** | **~4 weeks** |

(参考: 当初の M9-C 直行案は 2-3 セッション想定だった。評価基盤先行 + spike 並行で 3-5 倍延伸、
ただし empirical foundation を確保)

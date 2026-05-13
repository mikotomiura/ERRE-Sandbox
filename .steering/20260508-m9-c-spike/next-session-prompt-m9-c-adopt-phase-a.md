# Next-session handoff prompt — M9-C-adopt Phase A (design scaffold only)

**作成**: 2026-05-13 (PR #163 merge 直後、Phase K-β real-train 完遂)
**前提**: M9-C-spike 完遂 (PR #162 impl + #163 real-train + DB3 NON-FIRE 確定)
**用途**: 新セッション (Plan mode + Opus、~3-4h、GPU 不要) の最初の prompt として貼り付け
**本セッションは M9-C-adopt の requirement / design / decisions ADR を起草するのみ。code 変更ゼロ、PR は `.steering/` + `docs/` のみ**

---

```
M9-C-adopt の **Phase A (設計のみ)** を起こす。M9-C-spike (K-α + K-β) が PR #162/#163
で完遂し、DB3 fallback NON-FIRE 確定 + SGLang-first 採用 + adapter swap latency 8ms
(60x margin) + bench CS-7 4 trigger 全 NON-FIRE が empirical 実証された。
本セッションは **設計** に専念する。GPU を使わない、コードを書かない、テストを走らせない。
deliverable は `.steering/[YYYYMMDD]-m9-c-adopt/` 一式と `docs/` の adopt-scope ADR。

## 直近完了状態 (2026-05-13 時点)

- main HEAD = c1e118c (Merge PR #163)
- M9-C-spike 全 PR merged:
  - #154/#155 (K-α mock infrastructure proof、Linux execution boundary 確定)
  - #160 (M9-eval Phase B+C 30 cell golden baseline、kant 5022 examples 含む)
  - #161 (.gitattributes LF 強制)
  - #162 (train_kant_lora inner loop + argparse CLI 実装)
  - #163 (Phase K-β real train + 5 condition latency + 2 baseline bench + DB3 NON-FIRE)
- artefacts:
  - WSL2 venv に peft 0.19.1 / bitsandbytes 0.49.2 / accelerate 1.13.0 install 済 (B-3 解消)
  - `/root/erre-sandbox/checkpoints/kant_r8_real/` に real Kant LoRA adapter (rank=8、30.7MB)
  - `data/eval/spike/m9-c-spike-bench/{k-beta-swap-latency,single_lora,no_lora}.jsonl`
  - `docs/runbooks/m9-c-adapter-swap-runbook.md` (DB8 完成)
- decisions.md CS-3 / CS-7 / CS-8 amendment 2026-05-13 で実測値全 verbatim 反映済

## Phase A scope (本セッション)

### deliverables

1. `.steering/[YYYYMMDD]-m9-c-adopt/requirement.md` (5 項目: 背景 / ゴール / scope / scope 外 / 受入条件)
2. `.steering/[YYYYMMDD]-m9-c-adopt/design.md` (v1 案 + /reimagine v2 案 + comparison) ※ Plan mode + /reimagine 必須
3. `.steering/[YYYYMMDD]-m9-c-adopt/codex-review-prompt.md` (Codex `gpt-5.5 xhigh` independent review 依頼)
4. `.steering/[YYYYMMDD]-m9-c-adopt/codex-review.md` (Codex 出力 verbatim 保存)
5. `.steering/[YYYYMMDD]-m9-c-adopt/design-final.md` (Codex HIGH/MEDIUM 反映後の最終案)
6. `.steering/[YYYYMMDD]-m9-c-adopt/decisions.md` (DA-1..DA-N ADR、各 5 要素: 決定 / 根拠 / 棄却 / 影響 / re-open 条件)
7. `.steering/[YYYYMMDD]-m9-c-adopt/blockers.md` (hard / soft / defer / uncertainty 4 区分)
8. `.steering/[YYYYMMDD]-m9-c-adopt/tasklist.md` (Phase A-Z までの roadmap)

### NOT in scope (本セッション)

- code 変更 (src/erre_sandbox/ / scripts/ / tests/ 等への commit は禁止)
- 訓練の kick
- SGLang server の launch / stop (前セッションで起動した server が残っている場合は手を出さない)
- M9-B / M9-eval-system の追加調査 (本セッションは adopt-scope に閉じる)

## 設計対象 (design.md / decisions.md でカバーすべき topic)

### A-1: rank sweep 範囲 (CS-5 / D-2 / U-1 trigger)

- rank ∈ {4, 8, 16, 32} の sweep。本 spike は rank=8 continuity hypothesis、universal
  adequacy 主張せず — adopt で empirical 確認
- 評価軸: Tier B Vendi / Big5 ICC で persona-discriminative か?
- compute budget: 4 rank × 3 persona × 2h = 24h (G-GEAR overnight × 3)
- 採用 rank の決定基準: TBD (本セッションで決める)

### A-2: 3 persona expansion (D-3 trigger)

- Nietzsche / Rikyū の LoRA adapter 生成
- kant 同様に M9-eval Phase B+C golden baseline (5 cell × 500 turn) から訓練データ抽出
- persona 間の system prompt 差別化 (persona-erre Skill 参照、existing personas/*.yaml)
- 訓練順序: kant → nietzsche → rikyu の sequential か parallel か (single GPU で sequential 必須)

### A-3: live inference path 統合 (D-5 trigger)

- 現状: live inference は `src/erre_sandbox/inference/ollama_adapter.py` 経由
- adopt 後: SGLang `SGLangChatClient` を `inference/server.py` に組み込む
- 切替方式: feature flag / parallel rollout / hard switch のどれを選ぶか
- fallback: SGLang 利用不可時に Ollama に degrade する path

### A-4: multi_lora_3 bench (K-β defer 項目、CS-7 third baseline)

- mock_nietzsche_r8 / mock_rikyu_r8 を `tools/spike/build_mock_lora.py` で生成
- 3 adapter を pinned で SGLang load
- bench_serving で N=3 multi-LoRA 条件 (single_lora + no_lora との対比)
- CS-7 4 trigger 再確認 — multi-LoRA 下でも NON-FIRE か?

### A-5: M5 resonance / ERRE FSM smoke (K-β defer 項目)

- 8 mode (peripatetic/chashitsu/zazen/shu_kata/ha_deviate/ri_create/deep_work/shallow) の
  AnimationTree state machine が SGLang LoRA 経路で regression していないか確認
- K-α `scratch_kalpha/step5_fsm_smoke.py` パターン踏襲
- 実 adapter (kant_r8_real) で FSM が正常遷移するか

### A-6: Tier B empirical validation (CS-5 / U-1 closure)

- kant_r8_real の出力を Tier B Vendi / Big5 ICC にかけ、baseline (no LoRA) と比較
- 試料: stimulus 500 turn × 5 run = 2500 turn (B-2-stim 規模) で十分か?
- 持続時間: 1 turn ~14s (CS-7 bench から推定) × 2500 = ~10h、可能か?
- 採取 protocol: K-β の SGLang launch + adapter load + serialized inference loop
- 評価指標: Tier B (Vendi score、Big5 stability ICC、IPIP-NEO trait scores)

### A-7: production safety

- mock-LoRA が production loader に misroute するリスクの hard block (CS-9 amendment 候補)
- adapter pinning policy (どの adapter を常時 pinned するか、メモリと latency tradeoff)
- model checksum 検証 (adapter_model.safetensors の md5 を server-side で確認?)

### A-8: 採用判定基準 (DA-N で formal 化)

- Tier B Vendi / Big5 ICC で persona-discriminative threshold は何か (CS-5 amendment 候補)
- bench_serving で 3 persona 同時運用の throughput floor は (CS-7 amendment 候補)
- adapter swap latency P99 ceiling は (CS-8 amendment 候補)
- DB3 vLLM fallback re-arm の閾値は

## 設計プロセス (CLAUDE.md 厳守)

### Step 1: 既存資料を読む

- M9-C-spike steering: `.steering/20260508-m9-c-spike/` 全ファイル
- 特に decisions.md (CS-1..CS-9 + 3 amendment) と blockers.md (D-1..D-6)
- M9-B 設計: `.steering/20260430-m9-b-lora-execution-plan/design-final.md` (DB1-DB11)
- M9-eval-system: `.steering/20260430-m9-eval-system/` (ME-1..ME-15、Tier A/B/C)
- 既存 K-β runbook: `docs/runbooks/m9-c-adapter-swap-runbook.md`

### Step 2: Plan mode + /reimagine (CLAUDE.md 必須)

- Plan mode に入る (Shift+Tab 2回)
- 初回 design v1 を起草
- `/reimagine` で初回案を意図的に破棄し、ゼロから v2 を再生成
- comparison.md で 8 軸比較 (e.g. 採用順序 / fallback 戦略 / multi-persona init / Tier B 統合方式 / production loader / VRAM budget / 安全性 / scope creep risk)
- hybrid v3 を採用候補

### Step 3: Codex independent review

- `.steering/[YYYYMMDD]-m9-c-adopt/codex-review-prompt.md` に依頼書 + prior art links + 報告フォーマット (HIGH/MEDIUM/LOW)
- `cat <prompt-file> | codex exec --skip-git-repo-check` で起動 (token budget は `.codex/budget.json` 確認)
- 出力を `codex-review.md` に verbatim 保存 (要約禁止)
- HIGH は必ず反映、MEDIUM は判断記録、LOW は持ち越し可

### Step 4: design-final + decisions ADR

- HIGH 反映後の最終案を `design-final.md` に
- decisions.md に DA-1..DA-N、各 5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)
- blockers.md に hard/soft/defer/uncertainty 区分

### Step 5: tasklist + commit + PR

- tasklist.md に Phase A-Z の roadmap (Phase A は本セッション、Phase B 以降は別 PR)
- branch: `feature/m9-c-adopt-design`
- commit: `feat(adopt): m9-c-adopt — Phase A design scaffold (DA-1..DA-N ADR)`
- PR description に Codex review link、HIGH 反映マッピング表

## 注意

- main 直 push 禁止 / 50% 超セッション継続禁止 (`/smart-compact`)
- GPL を `src/erre_sandbox/` に import 禁止
- 本セッションは **code 変更ゼロ**、`.steering/` + `docs/` のみ
- SGLang server (`/root/erre-sandbox/`) が起動中の場合は手を出さない、別タスクで停止
- Plan mode 外で設計判断を確定しない (CLAUDE.md)
- 高難度設計で `/reimagine` を省略しない (CLAUDE.md)
- Codex token budget 超過時は `.codex/budget.json` で warn が出る (`daily_token_budget`)

## 完了条件 (本セッション)

### scaffold
- [ ] `.steering/[YYYYMMDD]-m9-c-adopt/` 作成 (`mkdir -p` + `cp _template/`)
- [ ] requirement.md 5 項目 (背景 / ゴール / scope / scope 外 / 受入条件)

### design
- [ ] design.md v1 (initial 案)
- [ ] design.md v2 (/reimagine で再生成)
- [ ] design.md comparison (8 軸)
- [ ] design-final.md (Codex HIGH 反映後)

### Codex review
- [ ] codex-review-prompt.md 起票
- [ ] codex-review.md verbatim 保存
- [ ] Codex Verdict 取得 (期待: ADOPT-WITH-CHANGES)

### ADR + tracking
- [ ] decisions.md に DA-1..DA-N (各 5 要素)
- [ ] blockers.md に hard/soft/defer/uncertainty
- [ ] tasklist.md に Phase A-Z roadmap

### PR
- [ ] branch `feature/m9-c-adopt-design` で PR 起票
- [ ] 本 PR は **設計のみ**、code 変更ゼロを PR description で明示
- [ ] Mac master review 待ち
- [ ] Phase B 以降の next-session-prompt を起草 (本 PR には含めない、別 PR で)

## 参照

- M9-C-spike 設計: `.steering/20260508-m9-c-spike/decisions.md` (CS-1〜CS-9 + 3 amendment 2026-05-13)
- M9-C-spike blocker: `.steering/20260508-m9-c-spike/blockers.md` (D-1..D-6、特に D-2 / D-3 / D-5)
- M9-B 設計: `.steering/20260430-m9-b-lora-execution-plan/design-final.md` (DB1-DB11)
- M9-eval-system: `.steering/20260430-m9-eval-system/` (Tier A/B/C、ME-1..ME-15)
- DB8 runbook: `docs/runbooks/m9-c-adapter-swap-runbook.md`
- K-β real-train PR: #163 (実測 verbatim 保存)
- 実装 PR: #162 (train_kant_lora CLI + inner loop)
- K-α report: `.steering/20260508-m9-c-spike/k-alpha-report.md`
- Codex 連携: `.codex/agents/*.toml` / `.codex/budget.json` / `.codex/config.toml`
- persona spec: `personas/kant.yaml` / `personas/nietzsche.yaml` / `personas/rikyu.yaml`

まず `.steering/20260508-m9-c-spike/` 全ファイルを読み、design context を完全に内面化した上で
Plan mode に入る。/reimagine を必ず発動して構造的バイアスを除く。
```

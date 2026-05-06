# Blockers & Deferred Items — m9-eval-system

## defer 方針

Codex `gpt-5.5 xhigh` review LOW finding および本タスクで即決できない判断事項を defer。
defer 期限と reopen 条件を明示。M9-B 親タスクの blockers (`.steering/20260430-m9-b-lora-execution-plan/blockers.md`)
とは scope を分離し、本タスク固有の項目のみここに記録。

## Codex LOW findings

### LOW-1: RoleEval wording — Kant-only か persona-specific か (Codex LOW-1)

- **finding**: design.md §Hybrid baseline の stimulus battery で
  "RoleEval-adapted Kant biographical MCQ: 10" と書かれているが、stimulus YAML は
  per persona (`golden/stimulus/{kant,nietzsche,rikyu}.yaml`) で、Nietzsche / Rikyu の
  MCQ が Kant biographical のままだと意味が成り立たない
- **検討した 3 案**:
  - **option A**: 各 persona に対し biographical MCQ を 10 問ずつ起草 (Nietzsche
    biographical MCQ / Rikyu 茶の湯 MCQ)
  - **option B**: Kant biographical MCQ は Kant のみで実施、他 2 persona は別の
    floor diagnostic (Wachsmuth Toulmin に振り替え) で 70 turn 構成は維持
  - **option C**: RoleEval を全廃し Wachsmuth/ToM/dilemma の 60 stimulus × 3.5 巡で
    210 turn を構成
- **status**: **closed (2026-05-01、Option A 採用)**
- **判断根拠**: Claude の trade-off 分析 (4 軸 dimension / CI 交絡 / Rikyū 実現性 /
  ME-1 で吸収) を Codex `gpt-5.5` independent review (`codex-review-low1.md`、109,448 tokens)
  が "Adopt Option A" verdict で支持。Option B は per-persona stimulus mass 違いで
  Vendi/Burrows の persona 横比較を交絡、Option C は persona-factuality 軸を消す。
  Option D (共通 philosophical attribution MCQ) は Codex LOW-1 で不採用 (RoleEval の
  role knowledge 目的とずれる)
- **Codex MEDIUM 5 件 + LOW 2 件補強** (詳細は `codex-review-low1.md` verbatim、
  反映先 ADR は `decisions.md` ME-7):
  - MEDIUM-1: design.md wording を "persona-specific biographical / thought-history MCQ"
    に変更、score は "within-persona floor diagnostic" 明記、cross-persona absolute
    accuracy を DB9 比較指標にしない
  - MEDIUM-2: 各 MCQ に `source_ref` / `source_grade: fact|secondary|legend` /
    `category` / `ambiguity_note` 必須化、scored accuracy は fact / strong secondary
    のみ、legend は stimulus 投入はするが factuality score 除外
  - MEDIUM-3: ME-1 base control は per-item で測り、`per_item_delta` と persona 内
    summary に留め persona 間 ranking には使わない (psychometric equating 未実施のため)
  - MEDIUM-4: 10 問のカテゴリ均等化 (chronology 2 / works 2 / practice 2 /
    relationships 2 / material-term 2)、`present_in_persona_prompt: true|false` 持たせ
    A-D forced choice、option order seeded shuffle、same-type plausible distractors
  - MEDIUM-5: 3 巡反復で MCQ は cycle 1 のみ primary scoring、cycle 2/3 は stimulus
    として流すが scoring exclude (or stem variant + option shuffle)
  - LOW-2: synthetic 4th persona 用 MCQ は `tests/fixtures` のみ、`fictional: true,
    scored: false` で本番 `golden/stimulus/` から分離

## 本タスクで決められない判断事項

### LIWC license 評価 (M9-B blockers から継承、本タスクで close 候補)

- **issue**: M9-B `blockers.md` の "LIWC 商用 license の最終可否判定"
- **本タスクでの決着**: **Option D 採用** (LIWC 全廃、Big5 を IPIP-NEO 自己申告に
  一本化、Empath は Tier A diagnostic のみ) を `design.md` で確定済
- **defer 先**: 本タスク P0a で M9-B blockers.md を Edit して "Option D 採用" 記載
  → 該当項目 close
- **reopen 条件**: ME-1 fallback fire により LIWC 検討が再浮上した場合のみ
- **status**: P0a で close 予定 (本セッション or 次セッション)

### Burrows corpus license (Cambridge Edition / Kaufmann translation 等)

- **issue**: ME-6 で reference corpus に英訳・独訳を含めることを採択したが、現代
  edition は royalty / re-distribution restriction の可能性
- **暫定方針** (ME-6 で確定):
  - public domain edition (Akademie-Ausgabe Kant 独 / KGW Nietzsche 独) を一次採用
  - 英訳は **license 確認後** に追加採否判断、確認できなければ独原典単独で運用
- **defer 先**: P1b (reference corpus 整備時)
- **reopen 条件**: Cambridge / Kaufmann が re-distribution restriction で使えない →
  独原典単独で運用 (英訳経路 fallback)
- **status**: P1b で **PD-only 路線確定** (2026-05-01)。英訳経路は本セッションでは
  扱わず、独原典単独 (Akademie-Ausgabe Wikisource 経路) + Project Gutenberg
  Kröner-tradition (KGW Colli/Montinari は editorial copyright 回避) +
  日本古典 (利休道歌 5 verses) で commit。Cambridge / Kaufmann edition は
  下記 "Burrows reference corpus — English translations defer" で independent
  に re-open 候補

### Burrows reference corpus — English translations defer (2026-05-01 P1b 開設)

- **issue**: ME-6 で en 経路 (Cambridge Edition Kant / Kaufmann Nietzsche) も
  reference に含める設計だったが、両者とも under copyright で本セッション中の
  re-distribution は不可と判定。
- **暫定方針** (P1b 完了、commit せず defer):
  - en 経路は本タスクでは reference 化しない (provenance.yaml に未登録、loader は
    `load_reference("kant", "en")` で `ReferenceCorpusMissingError`)
  - 独原典のみで Burrows 経路を回し、対話が英語に流れた場合は
    `BurrowsLanguageMismatchError` で明示 fail (silent fallback 禁止)
  - 自動翻訳系 (機械翻訳済みの training-distillation コーパス) は stylometric
    比較対象として不適切 (translator stylistic signature が混入) のため候補外
- **defer 先**:
  - **第 1 候補**: PD edition の英訳が判明した場合 (例: Cambridge 古い edition で
    PD と確認 / Project Gutenberg の旧訳) は本 entry を re-open し
    `_provenance.yaml` 追加 + vectors.json 再 build
  - **第 2 候補**: 後続タスク m9-eval-corpus で en 経路を独立検討
- **reopen 条件**: Kant / Nietzsche の英訳 PD edition が確認 / 入手された時点
- **status**: defer (本セッションでは扱わない)

### Burrows reference corpus — toy-scale corpus expansion (2026-05-01 P1b 開設)

- **issue**: P1b は **toy reference 路線** で commit (Kant 2656 words / Nietzsche
  12002 words / Rikyu 122 tokens)。ME-6 の "5K-word chunk stability test" は
  Nietzsche のみ実検証 (2 chunk Spearman ρ ≥ 0.8 PASS) で、Kant / Rikyu は
  explicit skip + reopen 条件 documented。
- **暫定方針** (P1b 完了、commit 済):
  - Nietzsche: 12K で 2× 5K chunk 確保、ρ=1.0 観測 PASS
  - Kant: 2.6K (5K 未達) で skip、reopen 条件 = Akademie-Ausgabe Bd. VIII
    全文 (~50K-100K words) 取り込み
  - Rikyu: 122 tokens (極小) で skip、reopen 条件 = 青空文庫の利休関連作品 /
    国文大観 OCR / ja.wikisource djvu OCR pipeline 経由で ~5K-10K tokens
    確保
- **defer 先**: 後続タスク `m9-eval-corpus` (本タスクから独立化)
- **reopen 条件**:
  - Kant 全文取り込み (license PD のため block 無し、技術 effort のみ)
  - Rikyu 大規模 PD 古典資料 acquisition path 確立
- **status**: defer (本タスクでは toy 路線で完結)

### Burrows Delta multi-lang reference の閾値 (M9-B blockers から継承)

- **本タスクでの決着**: ME-6 ADR で 50K 固定閾値を **棄却**、5K-word chunk stability
  test (Spearman ρ ≥ 0.8) に置換
- **defer 先**: P1b 完了時に corpus QC test 実行で確定
- **reopen 条件**: chunk stability test で rank instability 検出
- **status**: ME-6 ADR で方針確定、empirical 確認は P1b

### Judge bias mitigation runbook (M9-B blockers から継承)

- **issue**: Prometheus 2 / G-Eval bias mitigation 手順
- **暫定方針** (M9-B 既出):
  - position-swap averaging
  - length normalization
  - two local judges for close calls
  - human spot checks
  - CI over repeated runs
- **defer 先**: P6 (Tier C nightly infra) 実装時に runbook 起草
- **reopen 条件**: judge LLM の選択が確定 (Prometheus 2 8x7B vs Qwen2.5-72B 等)
- **status**: P6 着手時、本タスクでは無 unblock

## ME-1 conditional re-open watch (Big5 fallback fire watch)

ME-1 ADR で IPIP-NEO fallback の発火条件を明文化したが、判定 timing が **golden
baseline 採取後** (P5 完了時)。発火した場合の child ADR 作成を本 blockers で track:

- **trigger**: golden baseline 採取後の Big5 ICC 計測で ≥2/3 personas が ICC < 0.6
  または lower CI < 0.5
- **trigger 検出**: P5 完了直後の自動チェック (`evidence/tier_b/big5_icc.py`)
- **fire 時の action**: BIG5-CHAT regression head 実装 ADR を別途起票 (ME-1 child)
- **status**: monitor (P5 完了まで no-op)

## ME-4 ratio re-confirm watch

- **trigger**: P3a 完了 → P3a-decide で ratio 確定 → ME-4 ADR Edit
- **status**: P3a 完了まで monitor

## reopen トリガ一覧 (本タスク内 checklist)

| 項目 | reopen 条件 | trigger 場所 |
|---|---|---|
| LOW-1 RoleEval wording | option A/B/C 確定 | P2a stimulus 起草 |
| Burrows corpus license (independent) | Cambridge / Kaufmann PD edition 確認 | m9-eval-corpus |
| Burrows en translations defer | PD 英訳 edition 入手 | m9-eval-corpus / 後続 |
| Burrows toy-scale expansion | Akademie-Ausgabe 全文 / 利休関連 PD 大規模 | m9-eval-corpus |
| Burrows chunk stability (Nietzsche) | rank instability 検出 (現状 ρ=1.0 PASS) | golden baseline 採取後 |
| Judge bias runbook | judge LLM 選択確定 | P6 Tier C |
| ME-1 Big5 fallback | ≥2/3 ICC < 0.6 in golden | P5 completion |
| ME-4 ratio confirm | P3a CI width 測定 | P3a-decide |

## active incident: Phase 2 run0 wall-timeout (2026-05-06)

### incident 概要

P3 production 採取の Phase 2 run0 (3-parallel: kant + nietzsche + rikyu, natural
condition, `--wall-timeout-min 360`) が 3 cell 全て wall budget で FAILED 終了。
focal=381/390/399 で target 500 の 76-80% prefix で censored。Claude 単独の
事前 empirical 推計 (3-parallel contention 1.5x) が崩れ、実測 2.0x+ contention
だった。

| cell | wall (s/h) | focal | total | rc |
|---|---|---|---|---|
| kant | 21636 / 6.01h | 381 | 1158 | 2 |
| nietzsche | 21632 / 6.01h | 390 | 1169 | 2 |
| rikyu | 21609 / 6.00h | 399 | 1182 | 2 |

empirical: focal/hour = 63.5 / 64.9 / 66.5 (≈65/h)、3-parallel contention 2.0x+。

### Codex `gpt-5.5 xhigh` independent review (2026-05-06)

`codex-review-phase2-run0-timeout.md` (verbatim、281,778 tokens、4 HIGH / 3
MEDIUM / Verdict: revise)。Claude 単独案の HIGH 級欠陥を 4 件切出し:

- **HIGH-H1**: Claude 案 480 min budget は不足 (`65*8*0.85=442`、500 未達)。
  **600 min が最低ライン**、run1 を 600 min single で再校正必須
- **HIGH-H2**: run0 partial の `width × sqrt(n / n_target)` 補正適用は不適切。
  381/390/399 は random missing ではなく **wall-time prefix censoring**
  (76-80% 先頭)、後半 20-24% の memory growth / fatigue / prompt-length 変化を
  系統的に欠落。primary 5 runs matrix から外し、500 focal で run0 再採取
- **HIGH-H3**: Claude 案の return 0 + canonical filename publish は HIGH-6
  contract「partial captures cannot masquerade as complete」違反。
  **return code 3 (partial_publish) 新設** + `<output>.capture.json` sidecar
  (status / target / observed / wall_timeout / git_sha) + audit gate
  (`status==complete && focal>=target`) 必須
- **HIGH-H4**: `.tmp` rescue は graceful fatal path 限定、SIGKILL/OOM では
  Python `finally` 不到達で消失あり得る。次回同一 output 起動で `.tmp` は
  先頭 `unlink()` される。**rescue 前に `.tmp` + `.tmp.wal` 存在 + DuckDB
  read 可を verify 必須**、salvage-first 禁止 → fix-first 寄り

MEDIUM (詳細 `codex-review-phase2-run0-timeout.md`):
- M1: timeout 後の in-flight turn drop あり、partial manifest に `stop_reason`
  / `drain_completed` / `runtime_drain_timeout` 必須
- M2: IPIP-NEO 100 は本タスクの golden に未配置 (P4 territory)、natural と
  stimulus は run_id 別なので natural partial は stimulus に影響しない理解は正
- M3: **`eval_audit` CLI が main に未実装** (G-GEAR launch prompt は要求)。
  CLI fix と同 PR or 別 PR で audit CLI 新設、または `scripts/p3a_summary.py`
  拡張で `focal >= 500` + sidecar status 検査

### 確定アクション (ME-9 ADR で確定、本 incident block 期間中)

1. **G-GEAR rescue verify** — `*.tmp` + `*.tmp.wal` 存在 + read 可確認
2. **CLI fix + audit CLI PR** (Phase B、別セッションで `/start-task
   m9-eval-cli-partial-fix` 等で新規 task 化)
3. **run1 calibration** — 600 min single (kant のみ 1 cell)、120/240/360/480 min
   時点で focal/total/sqlite/Ollama latency 記録
4. **run2-4 budget 確定** — calibration 結果で確定後 3-parallel × 2-3 overnight
5. **run0 再採取** — 500 focal target、partial は `data/eval/partial/` 隔離
   保存 (primary に昇格しない)

### status

- **本タスク内 reopen 不要**: ME-9 ADR で確定、CLI fix は別タスクに切り出し
- **defer 先**: `m9-eval-cli-partial-fix` (新規予定)、CLI fix 完了後
  本 incident は close
- **track condition**: G-GEAR rescue 結果 (`.tmp` 救出可否) と CLI fix PR merge
  完了の 2 条件で incident close

## 設計上の不確実性 (記録のみ、defer ではない)

### Tier B の effective sample size (Codex HIGH-2 補強として)

- DB9 の Tier B per-100-turn metric は 500 turn / 100 = 5 window/run × 5 run = 25
  window/persona しか無く、bootstrap CI が広い (Codex HIGH-2 evidence)
- 反復: P5 で実際の CI 数値を観測、persona-discriminative かを判定
- 不適切なら DB9 sub-metric を Tier A 系に入れ替え検討 (M9-B `blockers.md` の
  "Tier B sub-metric 3 個の選定妥当性" 項目と整合)

### sentinel test の coverage 完全性 (Codex HIGH-1 補強として)

- HIGH-1 で sentinel-based 動的契約を導入したが、未来の caller (例 Rust/Go tooling)
  が増えた時に sentinel test scope が網羅できるかは継続課題
- 反復: 新規 training egress path が追加される PR で sentinel test に caller 追加を
  PR review checklist 化 (P0b で codex hooks に追加検討)

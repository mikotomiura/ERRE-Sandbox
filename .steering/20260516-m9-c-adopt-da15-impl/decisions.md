# 重要な設計判断 — m9-c-adopt DA-15 Phase 1 implementation

> 本 file は本 PR 内の session-local decisions を記録する。
> 横断的 ADR (DA-1 ~ DA-15) は `.steering/20260513-m9-c-adopt/decisions.md`
> を参照 (DA-15 は ADR PR で append 済、本 PR では追加しない)。

## D-1: Calibration corpus 出所

- **判断日時**: 2026-05-16
- **背景**: Codex HIGH-2 calibration panel mandate には Kant + Heidegger
  control text 各 100 文の test corpus が必要。spec は「邦訳 + 英訳」を
  想定。
- **選択肢**:
  - A: Aozora Bunko / Project Gutenberg などの public-domain 邦訳/英訳
       コーパスを download (license clean、ただし手動 curate が必要)
  - B: 既存 kant_*.duckdb から persona 出力を Kant 文として抽出、
       Heidegger 関連 stimuli を control として manual curate
  - C: 著名な philosophy commentary corpus (有料 license) を購入
- **採用**: **B + small public-domain supplement** (Aozora 由来の Kant /
  Heidegger 短訳文を補完素材として利用、license clean)
- **理由**:
  1. duckdb の Kant persona 出力は modeled by Qwen3-8B + LoRA / no-LoRA で、
     style は Kant Critique の系統を継いでいる (DA-11 で stylometric
     fingerprint を確認済)。calibration の目的は「encoder が Kant-style と
     non-Kant-style を分離できるか」なので、modeled output で実用上十分。
  2. control の Heidegger は public-domain には完全な邦訳はないが、
     20 世紀以前の philosopher (e.g. Hegel, Nietzsche of Aozora) を control
     として代替可能。本 calibration は "Kant-style ≠ random philosopher" を
     確認する性質なので、特定 philosopher にこだわらず "Kant-style ≠ other
     19c German philosopher" で十分。
  3. 完全 license clean: Aozora 邦訳 = PD、Wikipedia article 直接転載 = CC-
     BY-SA (license honor 付きで attribution)。
- **トレードオフ**:
  - B-only だと "Qwen3-8B が生成した Kant-style" が真の Kant-style と
     乖離している可能性。これは ME-1 / DB10 Option D の honest framing で
     既に許容済 (modeled persona は近似)。本 calibration の文脈で許容範囲。
- **影響範囲**: calibration corpus は `data/calibration/kant_heidegger_
  corpus.json` に固定、license honor を corpus metadata に記載。

## D-2: Encoder + revision pre-registration (rescore 実施前 mandatory)

- **判断日時**: 2026-05-16 (rescore 実行前に固定、commit SHA は本 commit
  自身が pre-registration 記録)
- **背景**: Codex HIGH-1 反映で「primary gating encoders の pre-registration」
  が rescore 前 mandatory。HF model id + revision SHA + transformers /
  sentence-transformers version + commit SHA を本 D-2 に固定する。
- **primary candidate encoders** (calibration AUC ≥ 0.75 pass が前提):

  | encoder | HF model id | HF revision SHA | sentence-transformers ver | transformers ver |
  |---|---|---|---|---|
  | E5-large | `intfloat/multilingual-e5-large` | `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3` | 3.4.1 | 4.57.6 |
  | BGE-M3 | `BAAI/bge-m3` | `5617a9f61b028005a4858fdac845db406aefb181` | 3.4.1 | 4.57.6 |
  | (regression) MPNet | `sentence-transformers/all-mpnet-base-v2` | `e8c3b32edf5434bc2275fc9bab85f82640a19130` | 3.4.1 | 4.57.6 |

  *HF revision SHA は 2026-05-16 時点の `HfApi.repo_info(repo).sha` 値。
  HuggingFace Hub の commit 単位で再現性を担保する。*

- **採用**: 上記 3 encoder を pre-registration、primary gate は E5-large +
  BGE-M3 (calibration AUC ≥ 0.75 pass が前提)。MPNet は **regression
  baseline** として併報告 (DA-14 fail を historical record として保持)。
- **トレードオフ**: HF revision pin により reproducibility 担保。万一 HF Hub
  上で commit が消えた場合 (rare) はローカルキャッシュ
  (`~/.cache/huggingface/hub/`) から再 hydrate 可能。
- **影響範囲**: `da15-verdict-kant.json` の "preregistration" field に本 D-2
  の内容を埋め込む (encoder name + revision SHA + library versions)。
- **environment**:
  - Python: 3.11
  - sentence-transformers: 3.4.1
  - transformers: 4.57.6
  - huggingface_hub: (本 commit 時の lock)
- **commit SHA**: 本 commit (D-2 pre-registration を含む commit) の HEAD を
  rescore 実行前 anchor として記録。rescore script は出力 JSON にこの
  commit SHA を埋め込む。

## D-3: Exploratory encoders は ADOPT 不寄与

- **判断日時**: 2026-05-16
- **背景**: Codex HIGH-1 で「philosophy-domain BERT 等の exploratory encoders
  は ADOPT 寄与不可」が mandate。
- **採用**: 本 PR では exploratory encoder は **使わない**。primary gate は
  E5-large + BGE-M3 のみ。philosophy-domain BERT の prior art 確認は
  blockers.md (将来 work) として記録。
- **影響範囲**: rescore script は exploratory encoder を accept しない
  (CLI 引数の choices で primary 3 + lexical-5gram に制限)。

## D-α-FAIL: Plan A は kant について REJECT (実測 verdict)

- **判断日時**: 2026-05-16 (rescore + verdict aggregation 後)
- **背景**: ADR D-1 の rollback 計画 (`design.md` `## ロールバック計画`) に
  従い、Plan A failure を D-α-FAIL として固定する。
- **実測結果**:

  | encoder | calibration AUC | natural d | lang-bal d | length-bal d | eligible |
  |---|---|---|---|---|---|
  | multilingual-e5-large | 0.8865 (PASS) | -0.1567 | -0.1754 | -0.4454 | **no** |
  | BAAI/bge-m3 | 0.9055 (PASS) | +0.2286 | +0.1456 | -0.2655 | **no** |
  | (regression) MPNet | 0.8960 (PASS) | -0.1788 | -0.3368 | -0.7268 | **no** |

  両 candidate primary encoder (E5-large + BGE-M3) が calibration gate を
  pass したものの、rescore で `cohens_d ≤ -0.5 + diff CI upper < 0` の
  DA-14 threshold を **standard / language-balanced / length-balanced
  bootstrap いずれも未達**。MPNet regression baseline は DA-14 verdict
  数値 (cohens_d=-0.1788) を完全に再現。

- **判定**: kant ADOPT 不成立 (primary axes passed = 1 of 3、quorum 2-of-3
  未達)。
- **next step**: Phase 2 (Plan B = Candidate C targeted hybrid retrain) を
  別 PR で起票 (ADR D-1 の Plan A → Plan B sequential 経路)。

- **non-gating observation** (Phase 2 設計 input):
  - **MPNet within-de d = -0.80** (point gate clear、CI gate fail) は LoRA が
    German 内で diversity を下げている兆候。
  - **E5-large within-en d = -0.58** (point gate clear、CI gate fail) も同様
    の per-language signal を示唆。
  - **BGE-M3 は natural d 符号が反転** (+0.23)。Codex HIGH-2 が警告した
    retrieval-encoder artefact の可能性。
  - 結論: 「LoRA は per-language slice で persona-style diversity を下げる
    効果があるが、global mixed-language 6-window bootstrap では bootstrap
    sampling variance が大きすぎて統計的有意性が出ない」という仮説と整合。

- **Hybrid H-α の扱い**: 本 ADR D-1 で「Plan A 走行中に Plan B driver を
  別 branch で pre-stage」と決めた経路 (Codex MEDIUM-3 反映) は本セッション
  では着手しなかった。Phase 2 起票時に H-α 是非を再検討する (Plan A 結果
  確定後の Phase 2 design セッションで判断)。

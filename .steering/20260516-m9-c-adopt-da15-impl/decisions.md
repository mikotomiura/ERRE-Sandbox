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

- **判断日時**: TBD (rescore 実行前に固定)
- **背景**: Codex HIGH-1 反映で「primary gating encoders の pre-registration」
  が rescore 前 mandatory。HF model id + revision SHA + transformers /
  sentence-transformers version + commit SHA を本 D-2 に固定する。
- **primary candidate encoders** (calibration AUC ≥ 0.75 pass が前提):

  | encoder | HF model id | HF revision SHA | sentence-transformers ver | transformers ver |
  |---|---|---|---|---|
  | E5-large | `intfloat/multilingual-e5-large` | TBD (pinned commit) | 3.4.1 | 4.57.6 |
  | BGE-M3 | `BAAI/bge-m3` | TBD (pinned commit) | 3.4.1 | 4.57.6 |
  | (regression) MPNet | `sentence-transformers/all-mpnet-base-v2` | TBD (pinned commit) | 3.4.1 | 4.57.6 |

- **採用**: 上記 3 encoder を pre-registration、primary gate は E5-large +
  BGE-M3 (calibration AUC ≥ 0.75 が前提)。MPNet は **regression baseline**
  として併報告 (DA-14 fail を historical record)。
- **トレードオフ**: HF revision pin により reproducibility 担保、ただし
  download 失敗時は対応 commit を decisions.md に retroactive 記録する
  (本 PR commit history で trace 可能)。
- **影響範囲**: `da15-verdict-kant.json` の "preregistration" field に本 D-2
  の内容を埋め込む。
- **commit SHA**: TBD (本 D-2 commit 後、rescore 実行直前の HEAD を記録)

## D-3: Exploratory encoders は ADOPT 不寄与

- **判断日時**: 2026-05-16
- **背景**: Codex HIGH-1 で「philosophy-domain BERT 等の exploratory encoders
  は ADOPT 寄与不可」が mandate。
- **採用**: 本 PR では exploratory encoder は **使わない**。primary gate は
  E5-large + BGE-M3 のみ。philosophy-domain BERT の prior art 確認は
  blockers.md (将来 work) として記録。
- **影響範囲**: rescore script は exploratory encoder を accept しない
  (CLI 引数の choices で primary 3 + lexical-5gram に制限)。

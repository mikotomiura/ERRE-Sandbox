# /cross-review 統合結果 (TASK-POST) — M13 B 反復 bank

## 対象
- 範囲: `ec3979f..HEAD` (feat/m13-b-bank) / 29 ファイル +5311 / 全新規 organ 無改変 / CI 緑 SHA: 1d3a60b
  (ALL CHECKS PASSED 3487 passed)
- 二者: code-reviewer(Opus) = `code-reviewer-review.md` / Codex(gpt-5.5, v0.141.0) = `codex-taskpost-review.md`
  (verbatim)。**注**: Codex は read-only sandbox で pytest 実行不可 (pydantic_core DLL access denied) = static
  解析のみ。

## 一致点 (両者指摘 = 高確度・最優先)
- **[HIGH] replay determinism が未整列 `frozen_contexts` で破れる** (`bank.py:259` iterate 入力順 / `:285`
  返却は `bank_sort_key` sort / `bank_records_to_recorded_calls` は「records=call order」仮定)。入力が
  `(ctx-b, ctx-a)` だと record stream と再実行 call order がずれ silent に別 context の raw_response 割当。
  code-reviewer=MEDIUM / Codex=HIGH → **統合 HIGH**。修正: `run_bank_mloop` を `sorted(frozen_contexts,
  key=frozen_ctx_id)` で iterate。

## 統合 HIGH (最終 merge 前に必ず反映)
- **H1 spend guard の穴 (Codex HIGH + code-reviewer MEDIUM)**: `_bank_spend_guard.py` が (a) `import
  collections as c; c.Counter()` の **alias 非追跡** (`:128`) / (b) `{row["pre_bias_destination_zone"] for row
  in rows}` の **subscript-key zone 参照非検出** (`:139`) / (c) `*, m_draws=...` の **keyword-only default 非
  検査** (`:216`)。さらに (d) **scan 対象に annotation を読む `test_ecl_bank_golden.py` が非含** (`_BANK_AGG_
  FILES`)。§I4 construction≠measurement の機械保証穴 → 塞ぐ。
- **H2 replay determinism (上記一致点)**: `run_bank_mloop` を sorted iterate に。
- **H3 M-loop think=False 非強制 (code-reviewer HIGH)**: `bank.py:268` は `llm.chat(messages, sampling=)` を
  think 無指定。provenance (`bank_fixtures.py:382` ThinkOffChatClient) と非対称。mock-only は素通りだが C-proper
  で real qwen3 → think=None → 既定 thinking ON → sampling regime が provenance と食い違う (`reference_qwen3_
  ollama_gotchas` / ECL v0 think=False load-bearing と衝突)。修正: M-loop も think=False を forward + assert test。
- **H4 created_at 非 pin → bake cross-platform 非決定 (Codex HIGH)**: `bank_fixtures.py:238` MemoryEntry は
  `created_at` を pin せず `default_factory=_utc_now`。retriever `(-strength, created_at, id)` (retrieval.py:250)
  で 2 mirror memory の created_at が同一 microsecond で tie すると id 順、tie しなければ created_at 順に
  **フリップ** = clock 分解能依存の platform 差。`env.md` の「libm float 非在→risk≈0」はこの動的 timestamp
  channel を見落とし。修正: created_at を fixed 定数で pin + env.md 訂正 + bake 決定性 test。

## 統合 MEDIUM (decisions.md に採否記録、cheap なら反映)
- **M1 golden verify が annotation↔records 対応非検証 (Codex)**: 個別 sha 一致すれば row ずれても通る。opaque
  維持のまま row-by-row の `(frozen_ctx_id,condition,mc_index)` 整合を verify に追加 → **反映** (cheap、opaque 維持)。
- **M2 T3 desk-audit sign-off 未記入 (Codex)**: TASK-POST 判断を merge 前記録にするなら空欄で残さない → 本
  /cross-review の結果で sign-off 欄を「二者レビュー通過、stimulus 判定は criterion 1-3 充足で substrate
  enrichment と暫定判定、最終 user 裁定へ」と記録 → **反映**。
- **M3 continuity self-scan が narrower guard 格下げ (code-reviewer)**: divergence 識別子 allowlist 除外 helper
  で full guard 回復可 → **defer 可** (honest 記載済)、decisions に記録。

## 統合 LOW (defer 可)
- **L1 bank_power base_dist validation (Codex)**: 負値/長さ1 で numpy error 余地 → cheap なら反映、defer 可。
- **L2 §I1 字面「retriever 非呼出」vs 実装 (store preload) 乖離 (code-reviewer)**: honest deviation 妥当。
  decisions.md に一行明記。
- **L3 replay placeholder inert (code-reviewer)**: 現状維持可。

## 良かった点 (両者)
- HIGH-1 (zone bias off + pre-bias readout) / HIGH-2 (BankLlmCallRecord ⊥ EclDecisionRecord、AST 二重担保) の
  反映が構造的に正しい。spend guard の精密 set-over-zones 判定。power apparatus の隔離。I6-G3 honest 解釈妥当。
  GPL/cloud API/evidence import 混入なし。

## 反映方針
- **H1-H4 を merge 前に必ず反映** (subagent で修正 → 独立検証 → 再 pre-push)。M1/M2 も cheap ゆえ反映。M3/L
  は decisions 記録 + defer。
- 反映後、再 /cross-review は不要 (HIGH は明確な contract-fidelity/determinism 修正、再レビュー閾値未満)。ただし
  修正 diff は独立再検証 + フル pre-push 緑を必須ゲートとする。

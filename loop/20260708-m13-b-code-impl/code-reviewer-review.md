# code-reviewer(Opus) review — M13 B 反復 bank 統合 diff (ec3979f..HEAD, TASK-POST)

> Loop TASK-POST /cross-review の code-reviewer 側。範囲 = ec3979f..feat/m13-b-bank (29 ファイル +5311、
> 全新規 organ 無改変)。full dump でなく要点を記録。

## 全体評価
契約 §I0-§I11 への忠実度が非常に高い。construction≠measurement 境界は AST guard + import allowlist +
annotation-opaque + human desk-audit の多層で機械保証。Codex 事実誤認 HIGH-1/HIGH-2/HIGH-4 は正しく反映。
organ 無改変確認。ただし bake-out M-loop が think=False を強制しておらず C-proper で load-bearing 前提が
silently 崩れる latent HIGH が 1 件。

## HIGH（必須対応）
- **bank.py:269 — bake-out M-loop が think=False 非強制（provenance pass と非対称）**。`run_bank_mloop` は
  `llm.chat(messages, sampling=sampling)` を think 無指定で呼ぶが、provenance pass (`bank_fixtures.py:382`) は
  `live.ThinkOffChatClient` で think=False 強制。凍結 prompt は think-off 生成なのに M 回 replay する M-loop は
  think-off でない。mock-only B test (D-10) は素通り、C-proper で real qwen3 → think=None → 既定 thinking ON →
  B lever が測る zone-marginal の sampling regime が provenance と食い違う。`reference_qwen3_ollama_gotchas`
  (think=false 必須) / ECL v0 (think=False load-bearing) と正面衝突。
  - 修正: `run_bank_mloop` 内で inner を ThinkOffChatClient で包む or chat() に think=False を渡し、think=False
    が chat() に届くことを assert する test 追加 (現 `_CyclingChat` は think を記録するが assert していない)。

## MEDIUM（採否記録）
- **bank.py:261 — replay 正当性が frozen_ctx_id ソート済み入力に暗黙依存**。M-loop は入力順 iterate だが返り値は
  `bank_sort_key` ソート。unsorted-input replay で silent mismatch。capture/verify は常にソート済みを渡すため
  golden は安全だが API 境界で未防御。修正: `run_bank_mloop` を `sorted(..., key=frozen_ctx_id)` で iterate。
- **_bank_spend_guard.py:149 — dict-subscript zone ヒストグラムが aggregation guard 網外**。`tally[zone]=...+1` で
  H もどき合成可。ADR §I4 の列挙 (Counter/set/numpy 等) 限定ゆえ契約違反でなく annotation-opaque + human
  desk-audit が backstop。修正: desk-audit doc に「dict-subscript zone 集計」を human gate チェック項目追記 (低コスト)。
- **test_ecl_bank_continuity.py:519 — continuity test self-scan が narrower guard に格下げ**。AC 識別子が
  "divergence" を含むため full guard でなく aggregation guard のみで self-scan (honest NOTE 記載済)。妥当だが
  この module だけ evidence/spdm/floor self-guard が外れる。修正: allowlist 除外して full guard を回すヘルパ (defer 可)。

## LOW（任意）
- **bank_fixtures.py:329 — §I1 字面「retriever 非呼出」vs 実装 (store preload → 実 retriever surface) の乖離**。
  honest deviation として妥当 (criterion 1 優先、§I2.2 別監査と整合)。ADR §I2.2「1×K」表記 vs 実装 2 condition×K。
  I6-G3 test は literal 1 に縛らず honest。提案: ADR 字面と実挙動差を decisions.md に一行明記。
- **bank.py:294 — replay placeholder (eval_count=0 等) が将来 manifest 混入時 provenance 誤読の余地**。現状 .content
  のみ再parse で問題なし。現状維持可。

## 良かった点
- BankLlmCallRecord の EclDecisionRecord 分離 (HIGH-2) が二重担保 (8-field 閉集合 + AST で EclDecisionRecord 出現禁止)。
- zone bias 交絡除去 (HIGH-1) が構造的 (pre-bias 直読 + provenance で bias_fired is None both draw + M-loop は
  CognitionCycle 非構築で `_bias_target_zone` 発火経路が無い。「pin off」でなく「発火経路が無い」を正確に区別)。
- spend guard の精度 (set-over-zones を `_references_zone` で限定、prompt-set dedup を通す positive/negative 両 test)。
  import allowlist は prefix 境界安全 (live が live_v1 を誤許可しない)。
- a-priori power apparatus の隔離が正しい (file I/O ゼロ・assumed dist のみ・sibling/evidence 非 import・numpy 自己完結)。
- determinism/cross-platform (categorical zone float 非感応、6桁量子化、verify は committed records のみから chat ゼロ)。

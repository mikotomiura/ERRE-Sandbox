**HIGH**
- §I4 / HIGH-4 の spend guard に抜けがあります。[_bank_spend_guard.py](C:/ERRE-Sand_Box/tests/test_integration/_bank_spend_guard.py:128) は `math/collections/itertools` の alias を追跡しないため、`import collections as c; c.Counter(...)` が通ります。また [_bank_spend_guard.py](C:/ERRE-Sand_Box/tests/test_integration/_bank_spend_guard.py:139) は `row["pre_bias_destination_zone"]` のような subscript key を zone 参照として検出しないため、`{row["pre_bias_destination_zone"] for row in rows}` が通ります。さらに [_bank_spend_guard.py](C:/ERRE-Sand_Box/tests/test_integration/_bank_spend_guard.py:216) は keyword-only defaults を見ておらず、実 API の `*, m_draws=...` が no-adaptive-topup 検査外です。construction≠measurement の機械保証として merge 前に塞ぐべきです。

- spend guard の適用範囲が不足しています。[_test_ecl_bank_spend_guard.py_](C:/ERRE-Sand_Box/tests/test_integration/test_ecl_bank_spend_guard.py:48) の `_BANK_AGG_FILES` は core 2 files + capture script のみで、annotation を実際に読む [test_ecl_bank_golden.py](C:/ERRE-Sand_Box/tests/test_integration/test_ecl_bank_golden.py:68) は scan 対象外です。ここに `len({row["pre_bias_destination_zone"] ...})` を追加しても guard が検出しません。§I4 の「B 側 test に暗黙集計を置けない」契約に穴があります。

- §I5 record→replay determinism が未整列 `frozen_contexts` で破れます。[bank.py](C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/bank.py:259) は入力順で `chat()` しますが、返却は [bank.py](C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/bank.py:285) で `bank_sort_key` 順に sort します。[bank_records_to_recorded_calls](C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/bank.py:300) は「records は call order」と仮定し、既存 [RecordReplayChatClient](C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/loop.py:216) は prompt/sampling を照合せず順に response を返すだけです。入力が `(ctx-b, ctx-a)` だと record stream と再実行 call order がずれ、silent に別 context の raw response を割り当て得ます。

- cross-platform byte 一致の analytical closure は現状弱いです。[bank_fixtures.py](C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/bank_fixtures.py:236) の `MemoryEntry.model_validate` は `created_at` を pin しておらず、[schemas.py](C:/ERRE-Sand_Box/src/erre_sandbox/schemas.py:884) の `default_factory=_utc_now` に落ちます。retriever は [retrieval.py](C:/ERRE-Sand_Box/src/erre_sandbox/memory/retrieval.py:316) で strength/created_at/id により順序化するため、再 bake 時の時計解像度や同点状態で frozen prompt の memory order が変わる余地があります。[env.md](C:/ERRE-Sand_Box/experiments/20260708-m13-b-bank/env.md:14) の「libm float 非在なので risk≈0」はこの動的 timestamp channel を見落としています。

**MEDIUM**
- golden verify は annotation と replayed records の対応を検証していません。[ecl_bank_capture.py](C:/ERRE-Sand_Box/scripts/ecl_bank_capture.py:551) で committed annotation を読み、[ecl_bank_capture.py](C:/ERRE-Sand_Box/scripts/ecl_bank_capture.py:578) でそのまま re-render します。`bank_records.jsonl` と `bank_annotation.jsonl` の `frozen_ctx_id/condition/mc_index/pre_bias_destination_zone` がずれていても、個別 sha が一致すれば通ります。opaque は維持しつつ row-by-row equality は検証できます。

- T3 materiality の criterion 4 は mechanism としては honest ですが、[t3_materiality_desk_audit.md](C:/ERRE-Sand_Box/experiments/20260708-m13-b-bank/t3_materiality_desk_audit.md:63) の sign-off 欄が未記入です。TASK-POST の判断を merge 前記録にするなら、ここは「未記入」のまま残さない方がよいです。

**LOW**
- [bank_power.py](C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/bank_power.py:199) は `base_dist` の positive sum しか検証しません。負値や長さ 1 の入力で numpy 側のエラー、または `achieved_delta_tv` と実際の alt 分布がずれるケースがあります。apparatus 用途では大きくないですが、入力 validation を足すと安全です。

**良かった点**
- HIGH-1/HIGH-2 の反映は概ね正しいです。`ERRE_ZONE_BIAS_P=0` pin + pre-bias `parse_llm_plan(raw).destination_zone` readout は [bank.py](C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/bank.py:255) と [bank.py](C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/bank.py:268) に明確です。`BankLlmCallRecord` も [bank.py](C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/bank.py:157) で EclDecisionRecord から分離されています。
- I6-G3 の「provenance は per-context 固定・非ゼロ・K 比例」という解釈は妥当です。M-loop retrieve-count=0 との構造対比という §I5 の意図は満たしています。
- GPL / cloud LLM API / evidence/spdm/runningness の import 混入は、対象 core files では見当たりません。
- power apparatus は assumed distribution only で、real bank data 非依存の境界が明確です。

検証: `git diff --check ec3979f..HEAD` は問題なし。pytest は read-only 環境で `pydantic_core` DLL import が Access denied になり実行できませんでした。

**Verdict: Revise**

HIGH は merge 前に直すべきです。全緑・WSL byte 一致の前提は否認しませんが、binding の letter から見ると M2 event-log checksum と per-agent RNG に実コード上の逸脱があります。

**HIGH**
1. M2 handoff が whole event/decision log checksum を公開していない  
[M2 result は `event_log_checksum` を持つ](</C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/society.py:772>)のに、M2 manifest の `replay_checksum` は [geometry-only の `result.checksum`](</C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/handoff.py:882>) のままです。`render_society_golden()` も [event_log_checksum を manifest/artifact に渡していません](</C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/handoff.py:1005>)。テストも [geometry-only checksum を pin](</C:/ERRE-Sand_Box/tests/test_integration/test_m2_society.py:1347>) しています。  
これだと §M4.4 の「geometry + dialog + affinity + memory + pair + self_other + decisions 全体 checksum」が cross-machine handoff の権威値にならず、dialog が実発火していても [committed golden artifact では whole social event log を検証できません](</C:/ERRE-Sand_Box/tests/test_integration/test_m2_society.py:1459>)。M2 manifest に `event_log_checksum` を追加するか、M2 schema では `replay_checksum` を whole checksum にして `geometry_checksum` を別 field に分けるべきです。

2. per-agent named substream 契約に対し、CSDG noise / bias RNG が共有 state のまま  
`society.py` は単一 `CognitionCycle` に [共有 `Random(seed)`](</C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/society.py:899>) を渡しています。その RNG は `CognitionCycle` 内で [physical update](</C:/ERRE-Sand_Box/src/erre_sandbox/cognition/cycle.py:552>)、[LLM delta update](</C:/ERRE-Sand_Box/src/erre_sandbox/cognition/cycle.py:821>)、[zone bias RNG](</C:/ERRE-Sand_Box/src/erre_sandbox/cognition/cycle.py:480>) に共有されます。実際の noise は [state.py の `_noise(rng, ...)`](</C:/ERRE-Sand_Box/src/erre_sandbox/cognition/state.py:114>) で消費されます。  
sorted scheduler なので登録順 permutation は安定しますが、agent A の RNG 消費が agent B の後続 noise/bias をずらすため、§M4.2/§M6 の per-agent named substream と、付託論点 5 の bias/state leak 観点では不十分です。ECL move の `EclRecordMode.substream(agent_id, "micro")` は [per-agent 化済み](</C:/ERRE-Sand_Box/src/erre_sandbox/cognition/embodiment.py:154>)ですが、CSDG/bias までは覆っていません。

**MEDIUM**
1. `event_log_checksum()` が rows / decisions を canonical sort していない  
pair/dialog/affinity/memory は sort されていますが、geometry は [`ecl_trace_checksum(rows)` に入力順のまま委譲](</C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/society.py:621>)し、既存 `ecl_trace_checksum` も [rows sequence をそのまま投影](</C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/loop.py:392>)します。decisions も [各 agent の sequence 順そのまま](</C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/society.py:649>)です。現 driver の producer order は deterministic ですが、§M4.4 の「全順序 key sort 後 SHA-256」「checksum 入力は final canonical projection のみ」の letter とはズレます。

2. memory mutation log が run-local ではなく agent_id-local  
`_collect_memory_mutations()` は [agent_id IN (...) だけで episodic_memory を読む](</C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/society.py:715>)ため、fresh store でない場合に既存 episodic rows が event log に混入します。`MemoryStore.add()` は [id primary key へ plain INSERT](</C:/ERRE-Sand_Box/src/erre_sandbox/memory/store.py:397>)なので、同じ deterministic id が残る store では衝突もします。tests は fresh `:memory:` なので通りますが、`run_society_loop()` の public surface はその前提を強制していません。

3. spend guard は docstring 除外としては有効だが、string-keyed output は見ない  
guard は [identifier position だけを scan](</C:/ERRE-Sand_Box/tests/test_integration/test_m2_society_spend_guard.py:241>)しており、docstring/comment 除外は Codex HIGH-1 反映として妥当です。ただし `{"verdict": ...}` のような executable output key は `ast.Constant` なので検出しません。現 `society.py` に floor/verdict/scorer 計算混入は見当たりませんが、「verdict/scorer object の生成」まで machine guarantee と言うには抜け穴があります。

**LOW**
1. record-mode dialog は現状 deterministic だが hook 依存が脆い  
`society.py` は既存 hook を [逐次 driver から呼ぶ](</C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/society.py:1015>)設計で、生成器は [LLM ゼロの deterministic template](</C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/society.py:390>)なので現状は construction として honest です。ただし `_drive_dialog_turns()` 内部は [asyncio.gather](</C:/ERRE-Sand_Box/src/erre_sandbox/world/tick.py:1569>)なので、将来 generator が await/side-effect を持つと record-mode の逐次契約が崩れやすいです。

**問題なし / 事実確認**
construction≠measurement の production 混入、GPL/cloud API import、Layer2 payload 前倒しは見当たりません。`affinity_deltas == ()` は [known-empty と明記](</C:/ERRE-Sand_Box/src/erre_sandbox/integration/embodied/society.py:767>)されており honest です。legacy/M2 handoff の二経路分離と `TYPE_CHECKING` Protocol 分離も方向性は健全です。`git diff --check` は clean でした。

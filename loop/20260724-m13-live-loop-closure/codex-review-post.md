# Codex TASK-POST cross-review（verbatim 抜粋） — M13 live 双方向ループ閉包

> gpt-5.5 / xhigh。sandbox shell 1312 ゆえ統合 diff を一次資料にレビュー。完全 verbatim（sandbox error ログ含む）は
> `.steering/20260724-m13-live-loop-closure/codex-review-post.md`（gitignore）。以下は review 本体（ANSI 除去）。

前提: ローカル Skill 読み込みは sandbox 起動エラーで失敗したため、提示された統合 diff のみを基準にレビューしています。

[HIGH] W-live が firing summary の測定情報を再 emit している:  
`wiring_reachability_summary()` が `sign_inversion_witness_tick_count` と `firing_summary_detail` を返しています。これは「correlation-id の seam 到達性のみ」という HIGH-2 binding を越え、特に `firing_summary_detail` は nested に `verdict` や測定系キーを持つ可能性があります。トップレベル `verdict=None` でも、詳細を verbatim で返すと measurement 非再入を破ります。  
推奨対応: W-live 出力から `firing_summary_detail` と sign-inversion 系集計を外し、`firing_summary["per_tick"]` を coverage 判定にだけ使う。返すなら seam boolean と plain count に限定。

[HIGH] `emitted_envelope` が correlation-id 到達性ではなく同 tick の共起になっている:  
`emitted_envelope` は `tick_trace.envelope_count > 0` だけで真になります。correlation-id は outbound schema に載せない設計なので、同じ tick に偶然 envelope が出た場合や複数 perturbation が同 tick に drain された場合、各 correlation-id が outbound seam に到達したように見えます。これは「reachability is not causation」の意図に反して、per-correlation の到達主張を強く見せます。  
推奨対応: 名前を `same_tick_envelope_observed` などに落とすか、tick-level adjunct として分離し、`all_seams_reached` の構成要素にしない。

[MEDIUM] `no_double_send` witness が MoveMsg 限定で HIGH-1 の証明として弱い:  
実装本体では `inject_envelope` を呼んでおらず、outbound owner は `WorldRuntime._consume_result` に保たれて見えます。一方で witness は `move_envelope_count` と caller supplied の `broadcast_move_count` だけを比較するため、`SpeechMsg` / `DialogTurnMsg` / `ErrorMsg` などの二重送出を検出できません。  
推奨対応: 全 envelope 数、または serialized envelope identity の multiset で `result.envelopes` と実際に drain/broadcast されたものを比較する。

[MEDIUM] `target_agent_id` 未検証のまま単一 agent に inject している:  
`run_live_loop_capture()` は sink から drain した全 `WorldPerturbationMsg` を `world.inject_observation(handle.agent_id, obs)` に渡しますが、`obs.agent_id` は `msg.target_agent_id` です。`target_agent_id != handle.agent_id` の frame が入ると、別 agent 宛ての PerceptionEvent が handle agent の pending に混入します。schema コメントでは gateway/loop wiring で検証すると書かれているため、ここが未閉包です。  
推奨対応: drain 後に `msg.target_agent_id == handle.agent_id` を検証し、不一致は drop/error ledger に分ける。将来 multi-agent 化するなら agent 別 queue にする。

総合判定: **Adopt-with-changes**。  
配線方針と HIGH-1 の実装経路自体は概ね妥当ですが、W-live witness の出力が binding より強く読めるため、merge 前に honest/reachability 表現を絞るべきです。

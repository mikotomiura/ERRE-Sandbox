# TASK-POST cross-review synthesis — M13 M2 Layer1 実コード統合 diff

> 統合 diff = `origin/main..feat/m13-m2-layer1`（6 commits、3863 insertions / 12 files）。
> 前提 = 統合フル pre-push 4 段 ALL CHECKS PASSED（3580 passed / 66 skipped / 0 failed）+ DG-2 WSL byte 一致実測 PASS。

## 二者レビュー

### code-reviewer（Opus）= **LGTM（HIGH なし、merge 可）**
binding 逸脱・determinism 抜け穴・over-read・measurement 混入なしを確認。全文 = `code-reviewer-review.md`（本ファイルに要点統合）。
- **MEDIUM-A**: `handoff.py` の M2 society 関数群（`render_society_golden`/`build_society_envelope_stream`/
  `build_society_decisions_stream`/`project_society_agent_to_ecl_result`）が §M8 spend guard の走査対象外
  （guard は society.py + test のみ）。現状 handoff は measurement import ゼロ・純 serialization ゆえ実害なし
  だが、将来 drift を機械検出できない。→ guard 拡張 or scope 境界明記。
- **LOW-1**: discovery guard の `_CHECKSUM_PATH_FUNCS`/`_CHECKSUM_PATH_METHODS` がハードコード tuple、
  網羅性未検証（checksum 寄与 helper 追加時の登録漏れを無言素通り）。完全性チェック追加提案。
- **LOW-2**: `_collect_memory_mutations`/`_harvest_pair_events` の private 越境（SLF001）= 内部変更時 silent break 結合。
- **LOW-3**: per-agent Plane2 共有 CognitionCycle の非リーク前提を直接 assert する cross-agent 非リーク test 提案。
- **良かった点**: created_at tick 由来 / uuid4 封鎖 / 6 桁量子化 / §B4 5 点網羅 / handoff 2 経路 clean /
  Protocol 型で循環回避 / spend guard 厳密（負例 witness）/ Layer2 seam honest（self_other null のみ、payload 未記述）。

### Codex（gpt-5.5、xhigh）= **degrade（Windows sandbox 障害で最終 verdict 未 emit）**
- **degrade 理由**: Codex の pwsh exec が Windows sandbox で `CreateProcessAsUserW failed: 1312` → node_repl MCP に
  fallback してレビュー ~90% まで進行するも、**最終 structured verdict を stdout に emit せず終了（stdout 0 バイト）**。
  narration は `codex-taskpost-review.err.md` に verbatim 保存。memory `feedback_codex_chatgpt_usage_limit` 型
  degrade = honest 記録 + code-reviewer を primary、observable concern を fold-in。
- **observable concern（narration から、2 回言及）= MEDIUM-B**: event-log checksum / M2 handoff decisions stream の
  **per-agent decisions（Plane2）が入力 sequence 順に append され、checksum 関数自体は明示 sort しない**。
  現 driver は tick 順 append ゆえ安定（permutation test でも registration-order 不変を担保）だが、checksum
  関数の「全順序 key で sort」契約文言とは差がある = 残リスク（driver 規律依存であって関数内強制でない）。
- その他 narration: society.py は契約どおり逐次 scheduler + per-pair RNG、over-read guard docstring 明示、
  handoff は TYPE_CHECKING Protocol で legacy/M2 二経路分離を確認（否認・事実誤認 HIGH なし）。

## 統合判定
- **HIGH: なし**（両者とも binding 逸脱・measurement 混入・over-read を検出せず）。
- **MEDIUM 2 件を反映**（下記）。**LOW 4 件は follow-up として記録**（defer 可、decisions.md/blockers.md）。

## 反映（HIGH なしだが MEDIUM は crown-jewel invariant ゆえ閉じる）
- **MEDIUM-A（反映）**: spend guard を handoff.py の M2 society 関数にも拡張（denylist import + 集計/分布生成
  非在を機械検出）。measurement 非再入は本タスクの核 invariant ゆえ文書化でなく閉じる。
- **MEDIUM-B（反映）**: event_log_checksum / decisions stream で per-agent Plane2 decisions を全順序 key で
  **明示 sort**（driver append 規律への暗黙依存を関数内強制へ格上げ）。**golden byte が変わらないこと**を
  検証してから反映（現 append 順が既に決定的ゆえ sort 後も同一のはず、変われば golden 再 bake + WSL 再実測）。
- **LOW-1..3（follow-up）**: discovery guard 完全性チェック / private 越境の public seam 化 / cross-agent 非リーク
  test。Layer2 mirror-sim impl-design or 別 cleanup issue で対処。blockers.md に記録。

# Codex TASK-PRE review — M13 Phase 1 sealed live run の issue 分解 + 事前登録

あなたは ERRE-Sandbox の independent reviewer (gpt-5.5/xhigh)。Loop Engineering の **TASK-PRE ゲート** =
grill+issue-slicing 直後、実装ループ前の第二意見。**実コード変更はまだ無い** (issue 計画のみ)。

## コンテキスト

- M13 arc = live LLM 認知が 3D embodiment substrate 上で履歴依存移動を駆動する統合器官 (ECL) を **建設**する。
  measurement (structural-floor/landscape verdict) は **holding 不可侵** (再入は costed superseding ADR +
  escalation ratchet 経由のみ)。
- **forward primary ADR FROZEN = 候補 A (sealed live run、単一 live agent)**。organ は実装・hardening 済だが
  **一度も real LLM と接触していない** → real qwen3:8b で一度封印実走 (first-contact) → captured real Plane2 →
  Ollama-free deterministic replay-verify。**construction validation であって measurement verdict でない**。
- 本タスク (Phase 1) = この sealed live run を実装。

## レビュー対象 (repo を読んで fact-check せよ)

- FROZEN ADR: `.steering/20260706-m13-forward-primary/design-final.md` (§FROZEN binding a-e、O1-O5、Done=
  O1∧O2∧O3a∧O3b) + `.steering/20260706-m13-forward-primary/decisions.md`
- grill 成果物: `loop/20260706-ecl-v0-live-run/grill-goals.md` (D-1..8、named test)
- issue 群: `loop/20260706-ecl-v0-live-run/issues/001-004.md`
- decisions: `.steering/20260706-ecl-v0-live-run/decisions.md` (D-1..8)
- コード: `src/erre_sandbox/integration/embodied/loop.py` (RecordReplayChatClient record mode / run_ecl_loop /
  ecl_trace_checksum) / `src/erre_sandbox/inference/ollama_adapter.py` (OllamaChatClient.chat, think) /
  `src/erre_sandbox/cognition/cycle.py` (chat 呼出が think を渡すか) /
  `src/erre_sandbox/integration/embodied/handoff.py` (write_golden/serializer/canonical rules) /
  `scripts/ecl_v0_golden.py` (replay-verify 構造)

## 特に見てほしい論点

1. **issue 独立性・依存の正しさ**: 001(apparatus)→002(replay-verify)→003(sealed run、MANUAL)→004(finalize) の
   依存は正しいか。002 を synthetic golden テンプレで先行実装し 004 で live artifact へ差替える分割は健全か。
   003 を人手 sealed gate (loop-watchdog 外) にするのは妥当か。
2. **ThinkOffChatClient (Codex HIGH-1 由来) の設計**: cycle が `chat(...,sampling=...)` で think を渡さない
   (`cycle.py`) ゆえ wrapper で think=False 強制する方針は正しいか。wrapper を
   `RecordReplayChatClient(inner=ThinkOffChatClient(OllamaChatClient))` の順で噛ませるのは、record 側の
   `OllamaUnavailableError` 捕捉 (loop.py の record mode) と競合しないか。**重要**。
3. **事前登録の tune-to-pass 封鎖**: D-1..8 (N=32/persona=kant/embedding=mock/O5≥1/O3a-O3b/…) と O1-O5 は
   sealed run 前に固定され、後から結果に合わせて緩められない形か。O5=「≥1 tick parsed-action」は first-contact の
   存在証明として妥当か (全 tick 要求や成功率閾値でない理由も含め)。O4/O5 が Done gate でなく annotation の分離は
   保たれているか。
4. **embedding=mock の妥当性**: live capture で retrieval embedding を constant-vector mock のままにし action LLM
   のみ live にする (D-4) で「organ が real engine と接触」claim は閉じるか、それとも real embedding 必須の穴が
   あるか。
5. **cross-platform O3a/O3b の射程**: 6桁量子化は float drift のみ。raw response.content 等 non-float は固定入力
   再利用で一致 (Codex HIGH-2 既反映)。committed live artifact の WSL byte 一致を I3 手動実測に置くのは十分か。
   envelope_provenance の embedded JSON float 量子化漏れの穴はないか。
6. **measurement 非再入 (holding)**: 001-004 のいずれかが evidence/spdm/runningness を import する / floor/
   landscape/verdict を計算・出力する経路がないか。sealed live run が measurement-line 再入を隠していないか。
7. **事実誤認**: repo 実状 (loop.py record mode の OllamaUnavailableError 処理、chat signature、golden embedding
   mock、handoff serializer) と issue/ADR 記述に齟齬がないか。

## 報告フォーマット

HIGH / MEDIUM / LOW で分類、**根拠 (ファイル・行)** + **推奨修正**。末尾に **Verdict: Adopt / Adopt-with-changes /
Revise / Block**。**事実誤認は HIGH で切り出す**。issue 計画の健全性と binding 制約遵守に集中 (style 指摘不要)。

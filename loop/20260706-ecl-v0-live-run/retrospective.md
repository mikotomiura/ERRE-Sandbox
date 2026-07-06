# retrospective — M13 Phase 1 sealed live run (first-contact)

## 結果 = GO (construction validated)
ECL v0 organ を real qwen3:8b で N=32 封印実走 (arc 初の first-contact)。**Done=O1∧O2∧O3a∧O3b HOLDS** +
O5=32/32 + O4 非縮退 → organ が real LLM で substrate を end-to-end 駆動し cross-platform に deterministic replay。
replay_checksum = `a528d5472c3fc1b939ab151e0bdb8089a23a8b5ae39b7b7961aeed91d94cc249`。

## Loop Engineering 6 軸分岐の適用実績
- 軸1 (grill 被覆): No (fork なし) → issue 直行。
- 軸2 (実行モード): 001/002/004 = subagent (fresh context) autonomous、003 = 人手 sealed gate (live Ollama 一発)。
- 軸3 (verify_level): 001/002/004 = recheck (独立再実行で自己申告を客観打消)。
- 軸4 (並行/直列): 依存 I1→I3→I4 で直列。
- 軸5 (sealed verdict): **GO** (Stop / construction 妥当性 branch は非発火)。
- 軸6 (cross-platform): WSL byte 一致 pass (drift なし)。
- Plan は条件付き entry = 非発火 (fork/Stop/branch なし、frozen contract 写経で完了)。

## うまくいったこと
- **think=False (ThinkOffChatClient、Codex Phase0 HIGH-1) が load-bearing と実証**: 全 32 tick が parseable
  (llm_status==ok)。wrapper 無しなら qwen3 が `<think>` に budget を食い O5==0 だった可能性大。事前検出が効いた。
- **cross-platform WSL 実測**を push 前に実施 (`uv pip install .` で WSL venv 構築 → Linux replay = Windows
  checksum byte 一致)。CI 事後追従を回避 (feedback_golden_crossplatform_float_drift)。
- TASK-POST Codex HIGH-1 (manifest 未検証の穴) を PR 前に閉じ、manifest byte-identical 再現を実測確認。
- subagent (fresh context) 逐次 + 各 attempt の独立 recheck で長セッションの判断劣化を回避。

## 学び
- sealed run は「人手 gate」だが G-GEAR 実行機上なら orchestrator が直接 CLI 実行できる (loop-watchdog の
  autonomous 対象外という非対称は正しく、実行自体は容易)。
- O5 を hard green gate にしなかった (annotation) 判断 (Codex TASK-PRE HIGH-2) が、結果的に O5=32/32 でも
  「tune-to-pass していない」ことを担保。実際は縮退せず GO。
- verify() が manifest 自体を検証していなかった穴 (TASK-POST HIGH-1) は、artifact SHA/checksum の「参照元」で
  ある manifest が未検証だと gate が vacuous になりうる好例。reproduction 契約は全 artifact に及ぶ。

## 次
次 primary = 候補 B (N体化) or C (measurement gate、R-budget=arc-wide 1 消費) を別 ADR で。arc-close 却下・
holding 継続。within-zone measurability は verdict 非昇格の preserved asset のまま。

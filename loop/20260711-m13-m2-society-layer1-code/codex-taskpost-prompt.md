# Codex TASK-POST independent review 依頼 — M13 M2 Layer1 実コード統合 diff

あなたは gpt-5.5（xhigh）として、ERRE-Sandbox の M2 Layer1（N体 determinism、GATING）実コード統合 diff を
independent review する。**read-only**（コード変更しない）。日本語で報告。

## レビュー対象
- ブランチ: `feat/m13-m2-layer1`（origin/main より 6 commits ahead）。統合 diff = `git diff origin/main..HEAD`。
- 主要変更: `src/erre_sandbox/integration/embodied/society.py`（新規 1061 行、N体決定的 driver）/
  `world/tick.py`（§B4 sorted 化 + step_cognition_once seam）/ `integration/embodied/handoff.py`（M2 schema
  additive）/ `integration/dialog.py`（rng_for_pair 注入）/ `godot_project/scripts/dev/EclReplayPlayer.gd` /
  tests（test_m2_society.py / test_m2_society_spend_guard.py / test_tick_b4_determinism.py）/
  `tests/fixtures/m2_society_golden/`。

## binding 契約（正典、逸脱がないか照合）
- FROZEN ADR: `.steering/20260711-m13-m2-impl-design/design-final.md`（§M3 配置 Placement-1 / §M4 record-mode
  逐次 sorted scheduler + per-agent/per-pair named substream + §B4 侵入経路 sorted 化 + versioned event/decision
  log 全体 checksum + discovery guard / §M5 Layer2 seam のみ / §M6 two-plane N体拡張 / §M7 handoff 2 経路 byte
  契約 / §M8 spend ast-guard / §M9 acceptance test 凍結）+ decisions.md DA-M2IMPL-1..8 + codex-review.md
  （前回 HIGH 4 反映点）。
- 実コード session の判断: `.steering/20260711-m13-m2-society-layer1-code/decisions.md`（DG-1..6）。

## 最重要レビュー付託論点（HIGH/MEDIUM/LOW で報告）
1. **construction≠measurement の letter 遵守**: society.py / test に floor/verdict/scorer/landscape/divergence/
   H(zone)/count/分布生成 が混入していないか。§M8 spend guard（test_m2_society_spend_guard.py）が
   executable AST 限定・docstring 除外で有効か、抜け穴がないか。checksum が metric/floor に化けていないか。
   **over-read（N体 emergence を substrate 否定/floor 確立へ昇格、firing⇔detectability 混同）がないか**。
2. **N体 determinism 契約が §B4 侵入経路を漏れなく閉じるか**: tick.py の separation/proximity/values() sorted 化、
   society の per-agent/per-pair named substream（pair_key = canonical JSON array）、discovery guard
   （permutation → 同一 checksum、裸非 sorted iteration 非在、DB ORDER BY、canonical key sort）。**残存非決定源**
   がないか（特に I4 で発見・修正した uuid4 dialog_id 混入のような latent 非決定が他に無いか）。
3. **dialog 配線の妥当性（DG-6）**: record-mode driver が world の既存 hook（_run_dialog_tick/_drive_dialog_turns）
   を逐次呼ぶ設計は健全か。utterance = 決定的テンプレート（LLM call ゼロ）は construction として妥当か、
   それとも over-claim（「N体対話」の実質）か。dialog.py の rng_for_pair 注入が既存呼出元を byte 不変に保つか。
4. **affinity 恒常空の honest 性**: affinity_deltas が常に空（唯一の呼出元 bootstrap.py が Allowed 外）で
   schema-present。これは honest known-empty か、それとも「N体社会決定性」の over-claim か。
5. **per-agent Plane2 keyed 化の設計**: shared CognitionCycle を society 側 _AgentKeyedChatClient router で
   "activate before step" して per-agent record/replay。sequential ゆえ active agent 一意の前提は堅牢か。
   agent 間で状態リーク（memory/relational/bias）がないか。
6. **handoff 2 経路二分（HIGH-2）**: legacy path（run_ecl_loop + 既存 golden 完全 byte unchanged）と M2 path
   （新 schema N=1 canonical-equivalent）が原理矛盾なく分離されているか。handoff が society を実行時 import
   せず Protocol 型で分離した設計は健全か。n1_canonical_equivalent が observation factory ラベル差を明示注入で
   吸収した（"m2 society forage step"）のは over-read でないか。
7. **凍結 apparatus・holding 非干渉**: run_ecl_loop 無改変（N=1 legacy byte 不変）/ evidence・bank・organ
   committed golden 無改変 / reasoning-trace door 保全 / R-budget 未消費（measurement 非再入）。GPL・クラウド
   API 制約適合。**Layer2 内部 HOW の前倒し（引っ張り禁止）がないか**（seam slot 予約 self_other_observation_
   input は null のみか、payload 具体 schema を書いていないか）。

## 報告フォーマット
- **Verdict**: Adopt-as-is / Adopt-with-changes / Revise
- **HIGH**（merge 前に必ず反映）/ **MEDIUM**（判断）/ **LOW**（defer 可）を各々列挙。各項目に file:line と根拠。
- 事実誤認があれば明示（前回同様、実コード照合で否認できる主張は事実誤認 HIGH に）。
- 全緑（3580 passed、WSL byte 一致実測 PASS）は前提。verdict/floor の混入や determinism の抜け穴、over-read、
  binding 逸脱を主眼に。

# retrospective — M13 Layer2 ミラー・シム real 封印実走 validate

## 成果（construction、measurement でない）
M2 Layer2（ミラー・シム、PR #77）を **real qwen3:8b で初封印実走し validate**。self_other_enabled を
society_live 収録 harness + m4_society_live_capture CLI に **additive thread**し、Layer2-on sealed golden を bake。
self-other segment が real prompt に **構造完全に注入**され LLM が応答することを record→replay-verify +
**Win/WSL byte-parity** で validate。**R-budget=0、floor/verdict/scorer/magnitude/divergence 非 emit**。

## Loop（per-issue subagent: 実装 Sonnet / review Opus / 検証 Haiku）
- K1（society_live seam）→ K2（script CLI + env_pins 永続 + verify auto-detect）→【real run bake】→ K3（existence + replay test）。
- 各 issue = Sonnet 実装 → Haiku test-runner 独立 recheck（自己申告を客観 exit code で打消し）→ Opus code-review。

## 決定的（Codex 二段）
- **pre-register Codex（material HIGH-1）**: 「think=False 縮退の有無を acceptance/見送り の gating にすると
  covert scorer 化」→ user 裁定で反映。**acceptance = 非意味論 boolean のみ**、縮退/collapse は non-gating memo
  （semantic uptake not assessed）。MEDIUM-1（構造 boolean existence）/ MEDIUM-2（env_pins は True 時のみ）/
  MEDIUM-3（type fail-closed）/ MEDIUM-4（WSL parity 明示比較）/ LOW-1..3 反映。
- **TASK-POST cross-review**: code-reviewer(Opus)=Approve/HIGH・MEDIUM なし、Codex(gpt-5.5)=最終 merge 止める
  HIGH なし。Codex MEDIUM-1（helper pop-on-False + M4 golden no-key test）+ LOW-2（findings 語彙）反映。

## honest outcome（over-read guard）
(1) self-other 注入: tick0 全 framing 不在 / tick 1..11 全 observer framing 有り + observed set == 他 agent 全体。
(2) LLM 応答: 36/36 decode + 構造 parse。(3) Windows byte-parity PASS（inner_invocations=0）。(4) WSL byte-parity
Win==Linux。rendering collapse（M4 finding）= non-gating memo（artifact observation、effect 未評価）。
→ **(A) construction validate GO**（wiring が real で発火）。(C) multi-zone rendering fix は deferred。

## 教訓
- **helper single-seam 化**（Opus MEDIUM）で live-Ollama 経路（CI 未到達）の書込みロジックを mock 経由で CI カバー。
- **env_pins additive witness の pop-on-False**（Codex TASK-POST MEDIUM）で「absence == Layer2-off」invariant を
  reused/stale dict に対しても堅牢化 + committed M4 golden の no-key を artifact test で直接固定。
- **over-read 境界の二段防御**: existence-check は agent_id 集合のみ抽出（zone/moved_toward/said の中身を読まない）、
  honest memo は artifact observation に限定（effect 主張しない）。

## Board
K1 done / K2 done / K3 done / real-run done（非 Loop human-run spend）。統合フル CI 緑（3706 passed）。

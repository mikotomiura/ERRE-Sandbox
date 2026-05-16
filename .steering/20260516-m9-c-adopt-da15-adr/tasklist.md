# タスクリスト — DA-15 ADR

## 準備
- [x] DA-14 verdict (`da14-verdict-v2-kant.json`) と DI-5/DI-7/D-1 を Read
- [x] retrain v2 design-final.md §1 (C1-C4) と §2.3 (Candidate C spec) を Read
- [x] DA-1 ~ DA-14 横断 ADR を Read (特に DA-14 spec の `ai_decision_protocol`)
- [x] `da1-thresholds-recalibrated.json` を Read
- [x] Step 0 feasibility scan: `scripts/m9-c-adopt/` Glob, `dataset.py` / `weighting.py` の Grep
- [x] Plan agent で workflow validation 取得

## ADR 起草
- [x] V1 draft (main agent) を `da15-draft-v1.md` に書く
- [x] V2 draft (Task tool subagent 経由、V1 隠蔽) を `da15-draft-v2.md` に書く
- [x] V1 vs V2 を `da15-comparison.md` で diff、hybrid 候補 (H-α) 抽出
- [x] `requirement.md` 確定
- [x] `design.md` sketch (Plan A 実装 scope + Plan B contingent scope) 確定
- [x] `blockers.md` (HIGH-3 self-review checklist + defer 項目) 確定

## Codex independent review
- [x] `codex-review-prompt.md` 起草 (HIGH-3 違反検出を最優先項目で明記)
- [x] `cat ... | codex exec --skip-git-repo-check` で起動
- [x] `codex-review.md` verbatim 保存 (37 行、Verdict ADOPT-WITH-CHANGES)
- [x] HIGH 指摘 (HIGH-1 / HIGH-2) を decisions.md D-2 / design.md / DA-15
      append にすべて反映
- [x] MEDIUM 3 件 + LOW 1 件すべて反映 (defer ゼロ、blockers.md に反映表記入)

## ADR 確定 (DA-15 append)
- [x] `decisions.md` (session-local) に DI-1 / DI-2 / D-1 / D-2 を記入
- [x] `.steering/20260513-m9-c-adopt/decisions.md` 末尾に **DA-15** を
      immutable append
- [x] `git diff main -- .steering/20260513-m9-c-adopt/decisions.md` で DA-15
      append 部分のみが diff (DA-1〜DA-14 不変、hard check PASS)

## handoff
- [x] `next-session-prompt-FINAL-impl.md` を起票 (Phase 1 Plan A 実装手順 +
      `.steering/20260516-m9-c-adopt-da15-impl/` 起票指示 + calibration panel
      mandate + named limitation mandate)

## commit + push + PR
- [ ] 5 標準 file + 中間 draft (v1/v2/comparison/codex-review*) + cross-cutting
      decisions.md DA-15 append を全部 commit (Conventional Commits、
      `docs(adopt): ...`)
- [ ] `git push -u origin feature/m9-c-adopt-da15-adr`
- [ ] `gh pr create` (title: `docs(adopt): m9-c-adopt — DA-15 ADR (retrain v2
      REJECT escalation)`、body で `codex-review.md` を link 参照)
- [ ] PR URL を返す

## 検証 (gh pr view 後)
- [ ] PR description に Plan A → Plan B sequential / Hybrid H-α / Plan C →
      Phase E migrate の要約あり
- [ ] PR description で `codex-review.md` link あり、HIGH 指摘の数を明記

## 次セッションへ持ち越し (本 PR 外)
- [ ] DA-15 Phase 1 implementation (`.steering/20260516-m9-c-adopt-da15-impl/`
      で `/start-task`)
- [ ] DA-15 trace.HEAD への本 PR merge SHA 埋め込み (別 chore PR)
- [ ] `da1_matrix_multiturn.py` の no-LoRA SGLang baseline 切替 (Phase 1
      implementation PR と同梱)

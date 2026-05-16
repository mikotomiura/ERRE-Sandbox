# M9-C-adopt DA-15 ADR — retrain v2 REJECT 受け escalation 設計

## 背景

`feature/m9-c-adopt-retrain-v2-train-execution` (PR #176、merged) で実行した kant
retrain v2 が、DA-14 thresholds に対し **REJECT** verdict (`.steering/20260515-
m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json`):

- primary axes pass: **1 / 3** (ICC のみ、2-of-3 quorum 未達)
- Vendi semantic Cohen's d = **-0.18** (target ≤ -0.5 fail、ただし **方向は反転**:
  prior LoRA r=8 で +1.39 wrong → v2 で -0.13 correct)
- Burrows reduction = +0.43% (target ≥ 5% fail、わずかに後退)
- ICC(A,1) = 0.913 ✅ / throughput 98.8% ✅
- pre-training audit 唯一の soft warning: de+en weighted mass = 0.489 (target 0.60)

DA-14 thresholds の **post-hoc movement は HIGH-3 で禁止** (CLAUDE.md /
[da14-verdict-v2-kant.json](../20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json))。
よって次の escalation path を ADR D-15 で確定する必要がある。

retrain v2 の方向性は正しい (Vendi reversed) が magnitude 不足という empirical
状態を踏まえ、3 案を equal-footing で trade-off 比較し、cheapest first の経済
合理性で sequential escalation を組む。

## ゴール

`.steering/20260513-m9-c-adopt/decisions.md` に **DA-15** を append し、以下を
確定する:

- Plan A (Vendi kernel swap) / Plan B (Candidate C targeted hybrid) / Plan C
  (Longer training / rank拡大) の trade-off matrix (predicted effect / risk /
  compute / reversibility)
- 採用案 (or hybrid) と re-open / escalate 条件
- HIGH-3 (DA-14 threshold immutability) を遵守したことの self-review

実装は **別 PR** で行う。本 PR は ADR + design sketch + handoff prompt のみ。

## スコープ

### 含むもの

- `.steering/20260516-m9-c-adopt-da15-adr/` 直下の 5 標準 file
- `.steering/20260513-m9-c-adopt/decisions.md` への DA-15 immutable append
- /reimagine による V1 / V2 (V2 は Task tool subagent 経由で独立生成) + comparison
- Codex independent review (`codex-review-prompt.md` / `codex-review.md`)
- 採用案 implementation の design sketch (`design.md` 内)
- 次セッション handoff prompt (`next-session-prompt-FINAL-impl.md`)
- HIGH-3 self-review checklist (`blockers.md` 内)
- commit + push + `gh pr create`

### 含まないもの

- 採用案の実装 (別 PR、handoff prompt で次セッションへ)
- `.steering/20260516-m9-c-adopt-da15-impl/` の作成 (次セッションの
  `/start-task` で行う)
- nietzsche / rikyu の retrain (kant ADOPT 後の Phase C)
- Phase E A-6 (kant ADOPT 後)
- `scripts/m9-c-adopt/da1_matrix_multiturn.py` の comparator 修正 (別 PR)
- DA-15 trace.HEAD への本 PR merge SHA 埋め込み (本 PR merge 後の別 chore PR、
  DA-14 convention 踏襲)

## 受け入れ条件

- [ ] `feature/m9-c-adopt-da15-adr` branch が main 派生で存在
- [ ] 5 標準 file (req/design/decisions/tasklist/blockers) が本 dir に存在
- [ ] `da15-draft-v1.md` (main agent) と `da15-draft-v2.md` (Task tool subagent
      独立生成) が両方存在し、decisions.md DI-2 でそれを明記
- [ ] `da15-comparison.md` で V1/V2 diff + hybrid 候補抽出
- [ ] `codex-review.md` verbatim 保存、HIGH 反映が ADR D-15 / decisions.md に記録
- [ ] `.steering/20260513-m9-c-adopt/decisions.md` 末尾に DA-15 append (DA-14 は
      不変)
- [ ] DA-15 D-2 で採用案 (or hybrid) が trade-off 数値見積込みで確定
- [ ] HIGH-3 self-review checklist が blockers.md にあり全 ✓
- [ ] `next-session-prompt-FINAL-impl.md` が起票され次セッションが
      `da15-impl/` 起票から始められる
- [ ] `gh pr create` 完了、PR description で `codex-review.md` を link 参照

## 関連ドキュメント

- `.steering/20260515-m9-c-adopt-retrain-v2-verdict/decisions.md` D-1 (REJECT 根拠)
- `.steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json`
- `.steering/20260514-m9-c-adopt-retrain-v2-impl/decisions.md` DI-1〜DI-4 (実装経緯)
- `.steering/20260514-m9-c-adopt-retrain-v2-design/design-final.md` (retrain v2 設計意図)
- `.steering/20260513-m9-c-adopt/decisions.md` DA-1〜DA-14 (横断 ADR 流れ)
- `.steering/20260514-m9-c-adopt-retrain-v2-design/da1-thresholds-recalibrated.json`
- CLAUDE.md (Codex independent review 起動規範)

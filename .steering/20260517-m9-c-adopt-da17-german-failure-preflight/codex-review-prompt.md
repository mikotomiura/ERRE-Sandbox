# Codex independent review prompt — DA-17 ADR (ドイツ語失敗 preflight)

**用途**: WSL2 経由で `codex exec --skip-git-repo-check -c model_reasoning_effort=xhigh` に渡す依頼書。出力は `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/codex-review.md` に verbatim 保存。

**Codex CLI 401 が再発する場合**: PR description で「Codex review は user 再認証後に follow-up で実施」と defer 明示 (PR-4 #189 と同 pattern)。

---

```
あなたは ERRE-Sandbox プロジェクトの independent code reviewer です。
本 PR (DA-17 ADR、m9-c-adopt Plan B kant ドイツ語失敗 preflight) を
review し、結果を **日本語** で HIGH / MEDIUM / LOW の 3 段階で報告
してください。実装は不要、forensic 妥当性と論理一貫性の review のみ。

## 本 ADR の position

- doc-only PR (src/ 変更ゼロ、retrain ゼロ)
- 続 PR-5 (β corpus rebalance) の起票根拠を確定する preflight ADR
- root cause 仮説 5 案 (H1-H5) + `/reimagine` 別案 (Plan subagent
  zero-base 再生成) + 最終採用 hybrid を decisions.md DA17-1〜DA17-7
  に記録

## 必須参照 file

1. `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/requirement.md`
2. `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/design.md`
3. `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/decisions.md`
   (DA17-1〜DA17-7 全件)
4. `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/next-session-prompt-FINAL-pr5-corpus-rebalance.md`
5. `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-verdict-plan-b-kant-v4.md`
   (前提 verdict)
6. `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜
   DA16-4 (順序判断 + WeightedTrainer fix + thresholds 不変)
7. `data/lora/m9-c-adopt-v2/kant_r8_v4/{train_metadata,weight-audit,plan-b-corpus-gate}.json`
8. `personas/kant.yaml` + `scripts/m9-c-adopt/tier_b_pilot.py` (prompt
   構造同一性検証の対象)
9. `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/next-session-prompt-FINAL-pr5-rank16-spike-reject.md`
   (DEFERRED 注記が正しく追加されたか確認)

## 主要 review 観点

### A. forensic evidence の妥当性 (DA17-1〜DA17-5)

- DA17-1 の v3 v4 within-language d 8 cell table は 8 個の rescore
  JSON から verbatim 抽出済か? 数値乖離 / typo / signed の誤りはないか?
- DA17-2 の paired sample 10 件は langdetect で正しく filter 済か
  (threshold 0.85、`DetectorFactory.seed=0`)? stimulus_id pairing は
  正しいか?
- DA17-3 の Burrows reduction% 計算式は正しいか?
  `(no-LoRA - LoRA) / no-LoRA * 100` で signed が一致するか?
- DA17-4 の `audit_de_en_mass=0.6010` / `per_language_weighted_mass`
  数値は `weight-audit.json` と verbatim 一致か?
- DA17-5 の prompt 同一性検証は `tier_b_pilot.py:482, 577` の引用が
  正しいか? 私が見逃している inter-condition 差はないか?

### B. root cause 仮説 (DA17-6) の論理一貫性

- H1〜H5 各仮説の evidence-for / evidence-against に factual error は
  ないか?
- H4 (trilingual capacity competition、ja silent sink) を dominant
  仮説として採用した根拠は妥当か? 他の dominant 候補 (例: 別の
  hypothesis、`weight-audit.json` 内に未利用の field) を見落として
  いないか?
- H5 (style register mismatch) を DA17-2 paired sample から articulate
  した結論は qualitative 観察の伸ばしすぎ (over-interpretation) では
  ないか? sample 10 件は統計的に sufficient か?

### C. `/reimagine` 別案統合 (DA17-7) の妥当性

- Plan subagent 別案で提案された H6 / H7 / H8 を本 ADR が正しく
  取り込んだか? 本 ADR の H1-H5 numbering との衝突回避 (H6/H7/H8 は
  別案 numbering の延長) は明示されたか?
- 最終採用 hybrid (β 単独 + H8 pre-check) は両案の長所を取捨選択した
  整合性のある decision か?
- β 単独 vs β + ε 併用の causal isolation 議論は妥当か? PR-5 で
  contribution 切り分けを優先する選択は正当化されているか?

### D. PR-5 scope 選定 (DA17-7) の妥当性

- 5 候補 (α/β/γ/δ/ε) の envelope + 検証 H + 失敗 pivot table は
  factual に正しいか?
- β を採用、α を defer する根拠 ("ja silent sink を mask する risk")
  は説得力があるか? α 採用派の counter-argument を articulate できる
  範囲で取り込んだか?
- ε / γ / δ の defer reason は十分か? 各 defer は将来 revival 可能化
  されているか?
- 「H8 pre-check mandatory」の論拠は妥当か? 30min × 3 seed spike は
  GPU envelope に対して reasonable か?

### E. 不変条件遵守 (CLAUDE.md / DA16-4)

- DA-14 thresholds 不変 (DA16-4 binding) を本 ADR でも維持しているか?
  thresholds 緩和提案が submerged にされていないか?
- WeightedTrainer fix (PR-2 `.mean()` reduce) は frozen として正しく
  treat されているか?
- nietzsche / rikyu Plan B 展開 blocked が維持されているか?
- 既存 prompt `next-session-prompt-FINAL-pr5-rank16-spike-reject.md`
  に DEFERRED 注記が正しく追加されたか (delete されていないか)?
- Plan mode + `/reimagine` 適用が decisions.md DA17-7 で明示されたか?

### F. PR-5 next-session prompt の完全性

- `next-session-prompt-FINAL-pr5-corpus-rebalance.md` の手順は
  reproducible か? H8 pre-check の 3 seed 値 / β corpus hyperparam の
  目標値 / retrain envelope / verdict pipeline は全て明示されたか?
- pivot tree (β success / failure 4 通り) は将来判断時に十分な情報
  を持っているか?

## 報告フォーマット (verbatim)

```
# DA-17 ADR Codex Review (HIGH / MEDIUM / LOW)

## HIGH (必ず反映、merge 前に修正)
- [HIGH-1] 観点 A〜F のどれか + 該当 file:section + 修正提案
- [HIGH-2] ...

## MEDIUM (採否判断、decisions.md に記録)
- [MEDIUM-1] ...
- [MEDIUM-2] ...

## LOW (defer 可、blockers.md に記録)
- [LOW-1] ...

## verdict
- ADOPT-AS-IS / ADOPT-WITH-CHANGES / REJECT のどれか
- 主要理由 (1-2 文)
```

各指摘は file:line / decisions.md DA17-N 等の具体的 anchor を必ず
含めてください。曖昧な指摘 ("もう少し詳しく" 等) は避け、修正案を
具体的に提示してください。
```

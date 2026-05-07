## Verdict
- Adopt-with-changes
- prompt 起票前に HIGH 3 件を反映すれば、採用案の骨格は維持可能。

## HIGH (実装前必反映)

### H1. stimulus 500 focal が現 command では到達不能
- 該当箇所: `.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md:54`, `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:157`, `src/erre_sandbox/cli/eval_run_golden.py:616`, `src/erre_sandbox/cli/eval_run_golden.py:830`, `src/erre_sandbox/cli/eval_run_golden.py:1481`
- 問題: v1 流用の `--turn-count 500 --cycle-count 3` は stimulus battery が oversampling しないため focal=500 に届かない。read-only pure-function check では kant/nietzsche/rikyu とも total focal=264。PR #140 後は `focal_rows < args.turn_count` が fatal になるので Phase B stimulus 全 cell が fail する。
- 推奨: v2 prompt で stimulus の `cycle_count` を 6 以上に変更する。`--turn-count 500 --cycle-count 6` は focal≈504 で audit target 500 を満たす。3-cycle 固定が必要なら target を 264 に下げる判断が必要だが、これは P3 spec 変更扱い。

### H2. run1 `--turn-count 1000` は 600 min endpoint を潰す
- 該当箇所: `.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md:47`, `src/erre_sandbox/cli/eval_run_golden.py:1101`, `src/erre_sandbox/cli/eval_run_golden.py:1146`
- 問題: single rate 期待値 1.87/min なら 600 min で focal≈1122。`--turn-count 1000` だと 600 min cell が約535 minで early stop し、最重要の 600 min wall sample が取れない。
- 推奨: calibration only で `--turn-count 1500` 以上、保守的には `2000`。120/240/360/480/600 wall cells は return code 3 を正常な calibration partial として扱い、production audit と混ぜない。

### H3. calibration と production の audit/rsync を混ぜない
- 該当箇所: `.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md:61`, `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:212`, `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:250`, `src/erre_sandbox/cli/eval_audit.py:92`
- 問題: design は「全30 cell + 5 calibration cell」を batch audit としているが、calibration は意図的 partial が混ざる。さらに v1 rsync は DuckDB だけを copy しており、PR #140 後に必須の `.capture.json` が Mac 側で欠けると audit return 4 になる。
- 推奨: calibration output は `data/eval/calibration/run1/` 等へ隔離。production は `data/eval/golden/` の run0..4 のみを exact glob/list で audit。rsync receipt は DuckDB と `.duckdb.capture.json` の md5 を両方含める。

## MEDIUM (採否は実装側判断、ただし decisions.md に記録)

### M1. 5 wall sequential は ME-9 の “single 600 min cell” から実質変更
- 該当箇所: `.steering/20260430-m9-eval-system/decisions.md:587`, `.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md:13`
- 問題: ADR は 1 cell 600 min + intermediate samples。5 cell sweep は実用的だが、同一 memory growth の時系列ではない。
- 推奨: decisions.md に「CLI snapshot 未実装のため endpoint sweep で代替」と明記。

### M2. stimulus smoke の wall 設計は CLI 上 no-op
- 該当箇所: `src/erre_sandbox/cli/eval_run_golden.py:958`, `src/erre_sandbox/cli/eval_run_golden.py:1313`, `.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md:45`
- 問題: `--wall-timeout-min` は natural 用で、stimulus には watchdog も return 3 path もない。smoke は sidecar complete/fatal path の確認に留まる。
- 推奨: prompt では「stimulus wall flag は安全弁ではない」と書き、必要なら外側の shell/PowerShell timeout を使う。

### M3. `contention_factor=1.76` は固定仮定として扱う
- 該当箇所: `.steering/20260507-m9-eval-phase2-run1-calibration-prompt/design.md:69`
- 問題: run1 n=5 single samples からは single-rate variance は出せるが、contention factor 自体は再推定できない。
- 推奨: factor は fixed assumption、run1 CI は single-rate の説明統計として出す。

## LOW (持ち越し可、blockers.md に記録)

### L1. `.gitignore` に calibration/partial DuckDB の明示 ignore がない
- 該当箇所: `.gitignore:75`, `.gitignore:91`
- 問題: `data/eval/partial/` と新規 calibration dir を使うなら DuckDB 誤 commit 対策が未定義。
- 推奨: prompt で `git add` 対象を明示するか、別タスクで ignore 追加。

## 5 questions への回答

### Q1: A + descriptive CI
`contention_factor=1.76` は fixed assumption。run1 n=5 では single-rate の 95% CI は出せるが、parallel contention の CI ではない。C は厳密だが ADR 改訂・追加 wall cost のため MEDIUM 記録で十分。

### Q2: fact-check 結果 + 推奨
`COOLDOWN_TICKS_EVAL=5` は `src/erre_sandbox/integration/dialog.py:96` にあり、natural capture は `eval_natural_mode=True` を渡している (`eval_run_golden.py:1115`)。`git log -S` では導入 commit `c6d6409` 以降、値のコード変更は見当たらない。systematic bias は低い。

### Q3: grep 結果 + 推奨
capture/audit は run_idx=100 を受けられる。制約は主に production manifest 側で、`golden/seeds.json` は run0..4、CLI help も「0..4 per design」。Tier B/C 実装はまだ見当たらず、`scripts/p3a_decide.py` の `_RUN_IDX=0` は pilot 専用。コード変更より、calibration dir 隔離 + production exact glob が推奨。

### Q4: A + caveat
`wall=60 turn=50` でよいが、CLI の wall flag は stimulus には効かない。turn=50 は local calculation で focal=51 になり publish target は満たす。外部 timeout を使うなら 60 min で十分。

### Q5: C
ME-9 re-open trigger に当たるなら、default は停止して Codex review/child ADR。720 min 強行は「re-open 条件」を空文化する。D は review 後の暫定運用案としてなら可。

## Out-of-scope notes

- CLI 修正は不要とは言い切れない。特に stimulus 500 focal を 3-cycle のまま満たしたいなら oversampling 実装が必要。
- `uv run` は read-only sandbox の cache 初期化で失敗したため未使用。テストは実行していない。
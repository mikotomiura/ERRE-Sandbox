## Verdict
- Adopt-with-changes
- 案 A' の方向性は妥当だが、audit gate と complete 判定の 2 点は実装前に固めないと partial/fatal の誤採用余地が残る。

## HIGH (実装前必反映)

### H1. audit が sidecar と DuckDB の同一 run 性を検証していない
- 該当箇所: `.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:156`
- 問題: 現 audit 案は `total_rows` と focal count だけを照合する。別 cell の sidecar が隣に置かれても、偶然 `total_rows` / `focal_observed` が一致すれば PASS し得る。
- 推奨: `raw_dialog.dialog.run_id` を `SELECT DISTINCT run_id` で取得し、`f"{persona}_{condition}_run{run_idx}"` と一致することを return 5 条件に追加する。`duckdb_path` は rsync 後に絶対 path が変わり得るため補助情報扱いでよい。

### H2. complete 判定が focal target 到達を必須にしていない
- 該当箇所: `src/erre_sandbox/cli/eval_run_golden.py:989`, `src/erre_sandbox/cli/eval_run_golden.py:1190`
- 問題: `runtime_task.done()` が target 前に起きた場合、`fatal_error` / `soft_timeout` が無ければ complete branch に落ち得る。task exception も `wait_for(runtime_task)` で再 raise され、sidecar を残さず落ちる可能性がある。
- 推奨: `_async_main` の complete branch は `result.focal_rows >= args.turn_count` を必須条件にする。未達なら `status=fatal`, `stop_reason="fatal_incomplete_before_target"`, return 2。`runtime_task` の exception は捕捉して `fatal_error` に変換する。

## MEDIUM (採否は実装側判断、ただし decisions.md に記録)

### M1. `_SinkState` の Pydantic validator は assignment を保証しない
- 該当箇所: `.steering/20260506-m9-eval-cli-partial-fix/design.md:12`
- 問題: `_SinkState` は mutable state で、`fatal_error` / `soft_timeout` は生成後に代入される。通常 dataclass では `@model_validator` は効かず、Pydantic dataclass でも assignment validation を明示しないと不十分。
- 推奨: 平の dataclass + `set_fatal()` / `set_soft_timeout()` helper で runtime assertion する方が既存パターンに合う。Pydantic にするなら `pydantic.dataclasses.dataclass(config=ConfigDict(validate_assignment=True))` まで必要。

### M2. drain grace は 60s 推奨、ただし drain timeout は fatal 維持
- 該当箇所: `src/erre_sandbox/cli/eval_run_golden.py:135`
- 問題: cognition tick が約 120s なので 30s は false fatal を増やす可能性がある。P3 全体の増分は小さい。
- 推奨: `_RUNTIME_DRAIN_GRACE_S = 60.0` を検討。`runtime_drain_timeout=True` は記録するが、checkpoint/close 完了が保証できないため partial publish にはしない。

### M3. audit の direct DuckDB は許容だが、report 出力の安全弁が欲しい
- 該当箇所: `.steering/20260506-m9-eval-cli-partial-fix/design.md:16`
- 問題: audit は training egress ではないので `connect_training_view()` 強制は不要。ただし `--report-json` を training 配下へ誤出力する防御は別問題。
- 推奨: `connect_analysis_view()` か evidence helper に COUNT ロジックを寄せる。`--report-json` は atomic write、batch exit code 優先順位、training-ish path への警告または refuse を定義する。

### M4. 壊れた sidecar の rescue は専用 force が安全
- 該当箇所: `.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:122`
- 問題: sidecar が存在するが validation 不能な場合、`--allow-partial-rescue` だけで unlink できると unknown state を消せる。
- 推奨: validation 失敗時は `--force-rescue` を別途要求する。最低でも status unknown を stderr に明示する。

## LOW (持ち越し可、blockers.md に記録)

### L1. `selected_stimulus_ids` は planned list と明記
- 該当箇所: `src/erre_sandbox/cli/eval_run_golden.py:688`
- 推奨: 現 field は replay 用の planned list と定義する。実消費 subset が必要になったら別 field を追加する。

### L2. sidecar 細部の enum/nullable 方針を固定
- 該当箇所: `.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md:75`
- 推奨: `stop_reason` は Literal 風に固定し、`wall_timeout_min` は natural では CLI 値、stimulus では `None` または未使用値のどちらかを decisions.md に記録する。

### L3. `assert_never` は Literal helper がある場合のみ有効
- 該当箇所: `.steering/20260506-m9-eval-cli-partial-fix/design.md:42`
- 推奨: bool 分岐に直接 `assert_never` は効きにくい。`CaptureStatus = Literal["complete","partial","fatal"]` を作るなら `match` + `assert_never` が有効。

## 5 questions への回答

### Q1: 60s 推奨 / drain timeout fatal 維持
30s 維持は HIGH ではないが MEDIUM 懸念。60s に上げる費用は小さく、false fatal を減らす。drain incomplete を partial publish するのは checkpoint/close 保証が弱いので採用しない。

### Q2: A + 明文化で十分
M9-B の `event_log` 追加が additive なら `extra="allow"` が最小コスト。semantics を変える場合だけ major version を導入する。C は現時点では重い。

### Q3: MEDIUM
HIGH ではない。audit は training egress ではなく COUNT のみなので direct read-only DuckDB は許容。ただし `--report-json` の出力先安全弁と batch exit code は定義するべき。

### Q4: (a) 全 N 個
現 `selected_stimulus_ids` は stratified slice の再現性用として全 planned list がよい。観測済み subset は audit 用に必要化した時点で別 field。

### Q5: B 推奨、ただし HIGH ではない
壊れた sidecar は unknown state なので `--force-rescue` を別 flag にするのが安全。A は運用コスト低いが、今回の「silent 破棄を防ぐ」主旨とは少し弱い。

## Out-of-scope notes
- HIGH-2 sample-size correction は再採用しない方針でよい。
- Phase 2 run1 calibration 自体は本タスク外。
- read-only review のため、ファイル編集とテスト実行はしていない。
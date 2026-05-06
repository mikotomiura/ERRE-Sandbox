codex
[HIGH] H1: 480 min budget の安全率計算が逆で、再 timeout リスクが高い
- 根拠: empirical 65 focal/hour なら 480 min は `65*8=520` で +4% だけ。15% 劣化を見込むなら `65*8*0.85=442` で target 500 未達。540 min でも `65*9*0.85=497` で境界、600 min が最低ライン。G-GEAR prompt も 360 min 未達を既知 hazard としている [g-gear-p3-launch-prompt.md](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:255>)。
- リスク: run1-4 も同じく 6-9h で止まり、partial だけが増える。線形外挿の 2 度目の失敗になる。
- 推奨アクション: run1 は 600 min で 3-parallel 1 本だけ再校正。120/240/360/480 min 時点の focal, total, sqlite row count, Ollama latency を記録し、run2-4 の budget をそこで確定。

[HIGH] H2: run0 partial を通常 sample として採用するのは不適切
- 根拠: `width * sqrt(n/n_target)` は `CI_width ∝ 1/sqrt(n)` 近似で、コード上も iid/sample-mean 近似と明記されている [scripts/p3a_decide.py](</Users/johnd/ERRE-Sand Box/scripts/p3a_decide.py:360>)。今回の 381/390/399 はランダム欠測ではなく wall-time censoring による先頭 76-80% prefix。
- リスク: 後半 20-24% の memory growth / fatigue / prompt-length 変化を系統的に落とし、自然条件の late-run signal を過小評価する。
- 推奨アクション: run0 は `partial/censored` diagnostic として救出可。ただし primary の 5 runs matrix には入れず、run0 を 500 focal で再採取する。時間制約で使う場合も sidecar manifest に `partial_capture=true`, `focal_target=500`, `focal_observed` を残し、primary/secondary 解析を分ける。

[HIGH] H3: CLI fix 案は partial masquerade 防止 contract をまだ満たしていない
- 根拠: 現 CLI doc は HIGH-6 として「partial captures cannot masquerade as complete」を明記 [eval_run_golden.py](</Users/johnd/ERRE-Sand Box/src/erre_sandbox/cli/eval_run_golden.py:36>)。現実装は fatal 時に rename を拒否し return 2 [eval_run_golden.py](</Users/johnd/ERRE-Sand Box/src/erre_sandbox/cli/eval_run_golden.py:1176>)。Claude 案の return 0 + canonical filename publish は launch/audit 側が成功扱いしやすい。
- リスク: `kant_natural_run0.duckdb` が見た目上 complete と区別不能になり、後段 audit/analytics/training egress が誤採用する。
- 推奨アクション: return code `3 = partial_publish` を新設。DB だけでなく `<output>.capture.json` などの sidecar に status, target, observed, wall_timeout, git sha を永続化。canonical final path へ置くなら audit は `status == complete && focal >= target` を必須条件にする。

[HIGH] H4: `.tmp` rescue は graceful fatal path 限定で、salvage-first の前提には弱い
- 根拠: wall timeout path は `finally` 後に `write_with_checkpoint(con)` を無条件実行する [eval_run_golden.py](</Users/johnd/ERRE-Sand Box/src/erre_sandbox/cli/eval_run_golden.py:998>)。DuckDB docs でも `CHECKPOINT` は WAL を DB file に同期する仕様。DuckDB CLI close も persistent DB を checkpoint/close し WAL を統合すると説明している。  
  Sources: https://duckdb.org/docs/lts/sql/statements/checkpoint , https://duckdb.org/docs/current/clients/cli/overview.html
- リスク: SIGKILL/OOM では Python `finally` に入らず checkpoint されない。さらに次回同じ output で起動すると stale `.tmp` は先頭で unlink される [eval_run_golden.py](</Users/johnd/ERRE-Sand Box/src/erre_sandbox/cli/eval_run_golden.py:611>)。
- 推奨アクション: run0 は G-GEAR 上で `*.duckdb.tmp` と `*.duckdb.tmp.wal` の有無を確認し、DuckDB で read/count できることを検証してから rescue。CLI fix 前に run1 を投げる salvage-first は避け、hybrid/fix-first 寄りにする。

[MEDIUM] M1: INSERT 中断 race は主リスクではないが、timeout 後の in-flight turn drop は明示すべき
- 根拠: sink は同期 closure で `con.execute()` 後に counter increment する [eval_run_golden.py](</Users/johnd/ERRE-Sand Box/src/erre_sandbox/cli/eval_run_golden.py:436>)。`record_turn()` も同期的に sink を呼ぶ [dialog.py](</Users/johnd/ERRE-Sand Box/src/erre_sandbox/integration/dialog.py:254>)。async cancellation は `con.execute()` の途中では割り込まない。
- リスク: timeout 後に LLM 生成済みだが未記録の turn が落ちるため、partial の末尾境界が運用依存になる。
- 推奨アクション: partial manifest に `stop_reason=wall_timeout`, `drain_completed`, `runtime_drain_timeout` を入れる。count は DB 再読込で検証する。

[MEDIUM] M2: IPIP-NEO/Big5 coverage は今回の natural row 数からは判断できない
- 根拠: local `golden/stimulus/*.yaml` は 70 items/persona、カテゴリは wachsmuth/tom_chashitsu/roleeval/moral_dilemma で、IPIP-NEO 100 battery は見当たらない。Big5 ICC は ME-4 でも P4 territory とされている [decisions.md](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/decisions.md:211>)。
- リスク: natural partial の 1158-1182 rows を根拠に IPIP/Big5 準備完了と誤認する。
- 推奨アクション: stimulus と natural は run_id が別なので natural partial は既存 stimulus には影響しない、という理解は正しい。ただし IPIP-NEO 100 の coverage は P4 側で別 audit を作る。

[MEDIUM] M3: `eval_audit` が現 main に存在せず、Phase 2 検証手順が未実装
- 根拠: G-GEAR prompt は `python -m erre_sandbox.cli.eval_audit` を要求 [g-gear-p3-launch-prompt.md](</Users/johnd/ERRE-Sand Box/.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:161>)。しかし `src/erre_sandbox/cli/` に `eval_audit.py` はない。
- リスク: partial publish を機械的に弾く最後の gate が存在しない。
- 推奨アクション: CLI fix と同時に audit CLI を追加するか、最低限 `scripts/p3a_summary.py` を phase2/golden 対応に拡張して `focal >= 500` と partial sidecar を検査する。

Verdict: **revise (HIGH 反映必須)**.  
`.tmp` rescue 自体は graceful return code 2 なら有望。ただし run0 を正規 sample に昇格、480 min で続行、return 0 partial publish の 3 点はそのまま進めない方がいいです。
hook: Stop
hook: Stop Completed
2026-05-06T12:43:11.149005Z ERROR codex_core::session: failed to record rollout items: thread 019dfd4b-9be9-7a11-8c36-6763c47d9044 not found
tokens used
281,778

# 設計判断 — security-hardening-pre-m10

Codex 12th review (`codex-12th-review-source.md`) 5 件への対応設計。
PR #161 (`.gitattributes`) で §6 LOW は事前 close 済。

---

## SH-0 — `/reimagine` 代替プロセス (meta-ADR)

- **判断日時**: 2026-05-13
- **背景**: CLAUDE.md 「Plan 内 /reimagine 必須」は高難度設計でゼロから再生成案
  との比較を要求する。本タスクは複数案ありうる §2 / §5 を含むので形式上は
  /reimagine 対象。
- **選択肢**:
  - **A**: 承認済み plan 上に /reimagine skill を改めて起動し、v2 案を生成・比較
  - **B**: Plan mode 内で Plan agent が 3 token option / 3 queue split option を
    enumerate し、AskUserQuestion でユーザーが back-compat token / cap=8 を
    明示選択した時点で「破壊と構築」の構造的要件は満たされた、と判定
  - **C**: /reimagine skill を再起動するが、user choice を制約として伝えて差分
    案のみ生成
- **採用**: **B**
- **理由**:
  - Plan agent prompt で「§2 token (file vs env vs cli-arg) / §5 queue split
    (1-q vs 2-q vs 3-q) を必ず複数案として識別」と指示済 → 単発バイアス排除済
  - ユーザーは AskUserQuestion で token rollout 3 option + cap 3 option を提示
    された上で `back-compat` / `8` を選択 → bias-free な人間判断介入が成立
  - 同一 design に対する /reimagine 再起動は user choice と矛盾する代替案を
    生む構造、コンテキスト消費 vs 追加価値の trade-off で正当化困難
- **トレードオフ**: 「Plan mode 内 /reimagine 形式」を厳密遵守していない (rule
  letter の違反、spirit は遵守)。代替プロセスの empirical 検証は本タスク
  Codex 13th review が担う (第三者性で closure)
- **影響範囲**: 本タスクの設計プロセスのみ。`feedback_reimagine_trigger.md`
  memory rule の将来適用には影響なし (高難度設計のデフォルトは依然 /reimagine
  起動)
- **見直しタイミング**: Codex 13th review で「Plan agent enumeration では
  alternative coverage 不足」と判明した場合、design-final.md 確定前に
  /reimagine skill 起動

---

## SH-1 — Hook + CI shell-bypass defense

- **判断日時**: 2026-05-13
- **背景**: `codex_issue.md` §1 HIGH。`.codex/hooks.json:28-39` matcher が
  `apply_patch|Edit|Write` のみ、`exec_command` 経由の shell 書き込みが
  `.steering` completeness guard / banned import check を通過する。
- **選択肢**:
  - **A**: hook matcher 拡張のみ (`exec_command|Bash` 追加)
  - **B**: CI grep gate 追加のみ (`policy-grep-gate` job)
  - **C**: hook + CI の両層
- **採用**: **C**
- **理由**:
  - hook 単独 (A) は `apply_patch` 偽装で素通り、bypass risk が残る
  - CI 単独 (B) は feedback latency が遅い (PR push 後)、IDE 内即時 deny の
    UX を失う
  - 両層 (C) は既存 `eval-egress-grep-gate` (`ci.yml:83-137`) が同型パターン
    として validated、defense-in-depth 完成
- **トレードオフ**: 開発時の hook 誤検知 (false positive) リスク増。red-team
  test 5 ケースで pattern 妥当性を担保
- **影響範囲**: `.codex/hooks/` + `.github/workflows/ci.yml` + 新規
  `tests/test_codex_hooks/`
- **見直しタイミング**: red-team test で誤検知率 >5% に達した場合、または CI
  grep gate が M9-eval / m9-c-spike 系の正当なツール使用を ブロックした場合

---

## SH-2 — WebSocket 3-layer auth (token + Origin + cap)

- **判断日時**: 2026-05-13
- **背景**: `codex_issue.md` §2 MEDIUM。`__main__.py:73-74` / `bootstrap.py:70-71`
  default `0.0.0.0:8000`、`integration/gateway.py:501-652` `ws_observe()` に
  認証 / Origin / session cap いずれもなし。Mac↔G-GEAR LAN rsync workflow は
  LAN 内前提だが、共有 Wi-Fi 誤公開時の blast radius が無制限。
- **選択肢** (Plan agent enumeration + AskUserQuestion):
  - **A. Token rollout: back-compat 優先** (`require_token=False` default、
    Godot patch を別 PR、enforce は後続)
  - **B. Token rollout: 同一 PR 強制** (P4 で Godot WS client patch も含める)
  - **C. Token rollout: Godot 免除 list** (loopback の Godot は token 不要)
- **採用**: **A** (ユーザー選択、2026-05-13 AskUserQuestion)
- **理由**:
  - A は blast radius 最小 (Godot 未パッチでも continue)、PR 単位の独立性高い
  - B は Godot patch を blocker 化、本 PR scope 拡大 + Godot live test 必要で
    工数 +5h
  - C は認証ロジック分岐増、`SH-2` の "3 layer independent" 原則を破る
- **トレードオフ**: A 採用で token 機構は **存在するが強制しない** 初期状態、
  別 PR で `require_token=True` default 化が必要。記録: `tasklist.md` に
  follow-up task 起票
- **追加判断**:
  - **`MAX_ACTIVE_SESSIONS = 8`** (Mac+G-GEAR Godot + curl + slack + M10 per-persona
    UI × 3、4 では tight、16 は memory waste で却下、AskUserQuestion 結果)
  - **Token storage**: file `var/secrets/ws_token` primary + env `ERRE_WS_TOKEN`
    fallback + explicit `--ws-token` arg は test のみ (`ps -E` leak 回避)
  - **Origin allowlist**: 空 list ⇒ check disabled (Godot native WS empty
    Origin 対応)、`host=0.0.0.0` + empty origin + `require_token=False` は
    startup error で誤公開予防
- **棄却**:
  - mTLS (運用負荷過大、cert rotate 必要)
  - cookie auth (Godot native WS が cookie 非対応)
  - `127.0.0.1` 強制 (Mac↔G-GEAR LAN rsync workflow 実害、memory
    `feedback_crlf_canonical_for_md5.md`)
- **影響範囲**: `__main__.py` / `bootstrap.py` / `integration/gateway.py` /
  `integration/protocol.py` / `docs/architecture.md` / `README.md` /
  `docs/development-guidelines.md` / `tests/test_integration/test_gateway.py`
- **見直しタイミング**:
  - Godot 4.4 WS client が token 対応した時点で `require_token=True` default
    化の follow-up PR
  - `MAX_ACTIVE_SESSIONS=8` が M11 で不足判明した場合、cap 値 reopen
  - LAN 外公開要件が発生した場合 (M14+? OSF 公開時)、mTLS 検討

---

## SH-3 — Codex network split

- **判断日時**: 2026-05-13
- **背景**: `codex_issue.md` §3 MEDIUM。`.codex/config.toml:4` `web_search = "live"`
  + L10 `[sandbox_workspace_write] network_access = true` の同居で、prompt
  injection 経由の外送リスク。
- **選択肢**:
  - **A**: 両方 off (`web_search` も `network_access` も false)
  - **B**: 両方 on 維持 (現状、Codex finding 無視)
  - **C**: 分離 (`web_search` 維持 + `network_access` off)
- **採用**: **C**
- **理由**:
  - A は web_search の empirical 実利を失う (memory `project_m9_b_plan_pr.md`:
    Codex web search が SGLang v0.3+ multi-LoRA を発見、Claude solo の stale
    認識を補正した実績あり)
  - B は Codex finding を無視、研究方針「クラウド送信なし」と矛盾
  - C は workspace_write sandbox 内の外送 (prompt injection 経由の
    `curl payload` 等) を構造的に閉じつつ、研究利便を保護
- **トレードオフ**: workspace_write 中の `pip install` / `git push` 系も
  network off になる → 明示 opt-in 運用 (per-session ユーザー承認)
- **影響範囲**: `.codex/config.toml` + `AGENTS.md` + `.agents/skills/erre-workflow/`
- **見直しタイミング**: workspace_write 中の network 必要性が高頻度化した場合、
  per-task allowlist (e.g. `pip` のみ許可) を検討

---

## SH-4 — eval CLI `--memory-db` path guard

- **判断日時**: 2026-05-13
- **背景**: `codex_issue.md` §4 MEDIUM/LOW。`cli/eval_run_golden.py:1029-1030`
  が `memory_db_path.unlink()` を unconditional に実行、symlink follow / 任意
  prefix / overwrite 同意なしの 3 重リスク。
- **選択肢**:
  - **A**: symlink reject + prefix allowlist + `--overwrite-memory-db` flag (3 in 1)
  - **B**: hash-suffix unique path で衝突回避 (削除自体を不要化)
  - **C**: 削除前 interactive confirm
- **採用**: **A**
- **理由**:
  - 既存 `cli/eval_run_golden.py:1269-1292` の `--overwrite` / `--allow-partial-rescue`
    / `--force-rescue` 3-flag パターンと整合、運用学習コスト最小
  - B は test 再現性 loss (hash が run ごとに変わる)
  - C は CLI 非対話運用 (Mac↔G-GEAR rsync の autonomous loop) と矛盾
- **トレードオフ**: ユーザーは `--memory-db <path>` を渡すとき、原則
  `--overwrite-memory-db` も付ける必要 (back-compat 維持のため default path は
  `/tmp/p3a_natural_*` のまま、user 指定時のみ厳格化)
- **影響範囲**: `cli/eval_run_golden.py` + `tests/test_cli/test_eval_run_golden.py`
- **見直しタイミング**: `var/eval/` directory が標準運用化した場合 (M9-C-spike
  Phase G-J 等)、default path 自体を `var/eval/` 配下に移行検討

---

## SH-5 — Runtime envelope queue 2-split

- **判断日時**: 2026-05-13
- **背景**: `codex_issue.md` §5 LOW。`world/tick.py:386` `_envelopes =
  asyncio.Queue()` が unbounded、`_consume_result` 失敗時に memory grow
  しうる。既存 TODO (`tick.py:382-385` D7 ADR 参照) で `maxsize=10_000`
  予定済。
- **選択肢** (Plan agent enumeration):
  - **A. 単一 queue**: `maxsize=1024` + drop-oldest
  - **B. 2-queue (heartbeat + main)**: heartbeat coalesce + main bounded
  - **C. 3-queue (heartbeat + dialog + error)**: priority 完全分離
- **採用**: **B**
- **理由**:
  - A は dialog/error 欠落リスク (heartbeat の高頻度で push されると dialog が
    drop される可能性)、ERRE の dialog turn は研究 primary signal なので失えない
  - C は実装複雑度高、`recv_envelope` の 3-way race-merge 性能劣化
  - B は gateway L208-258 `Registry.fan_out` の既存 drop-oldest + ErrorMsg
    warning パターンと同型、heartbeat は coalesce 安全 (latest-wins、`maxsize=1`)
- **詳細**:
  - `_heartbeat_envelopes` (maxsize=1): drain 旧 → push 新 (coalesce)
  - `_envelopes` (maxsize=1024): drop-oldest + `ErrorMsg "runtime_backlog_overflow"`
    を warning として混入 (`schemas.py:44` `SCHEMA_VERSION` 不変 で M9 baseline 保護)
  - `recv_envelope`: 2-queue race-merge、`_envelopes` を main 優先
- **棄却**: priority queue (`_consume_result` 性能劣化)、coalesce 全 envelope
  (dialog 順序破壊)、prometheus counter 新設 (本タスク範囲外、別タスク化)
- **影響範囲**: `world/tick.py` (~80 行) + `tests/test_world/test_runtime_lifecycle.py`
  (+2 ケース)
- **見直しタイミング**:
  - dialog/error が 1024 を恒常的に超える運用が発覚した場合、main queue 拡大
  - heartbeat 以外にも coalesce 安全な envelope type が発生した場合、
    `_heartbeat_envelopes` を `_coalesce_envelopes` にリネーム + 種別追加

---

## SH-summary

- 本 ADR **6 件** (SH-0 meta + SH-1〜SH-5 本体) で Codex 12th review §1〜§5 を
  全 close 設計
- §6 LOW は事前 PR #161 で close 済
- M9 baseline 不可侵 (`data/eval/golden/` / `src/erre_sandbox/evidence/` / `schemas.py:44`
  `SCHEMA_VERSION`) は全 ADR で明示的に保護
- 棄却理由は **運用文脈との衝突** (LAN rsync / web_search empirical / Godot 4.4
  WS spec) を中心に明示、盲目的 Codex 反映を避けた構造
- 次ステップ: design-final.md 確定 (v1 を昇格) → P1 (§3 Codex network) 着手 →
  ... → P6 Codex 13th review で closure

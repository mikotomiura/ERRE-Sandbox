# 次セッション開始プロンプト (PR #170 merge 後)

以下をコピペして **PR #170 merge 確認後** に新規 conversation で投入する。
`/clear` 直後の cold-start 起点を想定した self-contained 版。

---

```
ERRE-Sandbox の `security-hardening-pre-m10` follow-up を実行する。

前回 PR #170 (`feat(security): security-hardening-pre-m10 P0-P3 partial
(HIGH§1/§2 deferred)`) で P0-P3 (SH-3/SH-4/SH-5) を消化した。本セッションは
**M10-0 着手の go/no-go gate** である SH-1 (Codex hook + CI shell-bypass) と
SH-2 (WS auth) を実装する。

## まず実行する確認 (順序通り)

1. `git status --short && git log --oneline -5` で branch state 確認:
   - branch = `main`
   - HEAD に `feat(security): security-hardening-pre-m10 P0-P3 partial (#170)`
     相当の merge commit が含まれること
   - working tree が clean (untracked file は `idea_judgement.md` /
     `idea_judgement_2.md` / `data/eval/golden/_checksums_mac_received.txt`
     程度のみ許容、それ以外あれば停止)
2. `git fetch origin && git pull --rebase origin main` で最新同期、
   conflict 出たら停止して報告
3. `gh pr view 170 --json state` で PR #170 が `MERGED` であることを確認
4. 残った `origin/feature/security-hardening-pre-m10` branch の削除確認
   (`git branch -r | grep security-hardening-pre-m10` が空 or 1 件のみ)

## まず Read する必須ファイル (順序通り)

1. `.steering/20260513-security-hardening-pre-m10/decisions.md` ←
   特に **SH-1 ADR** と **SH-2 ADR** を完全に内面化 (本 task でゼロから
   設計しない、既存 ADR をそのまま実装)
2. `.steering/20260513-security-hardening-pre-m10/design-final.md` ←
   "Status (2026-05-15 closure)" section で P4 / P5 が **DEFERRED** と
   marking されている範囲を確認
3. `.steering/20260513-security-hardening-pre-m10/blockers.md` ←
   "M10-0 着手の go/no-go gate" section で残作業 §1 (SH-1) + §2 (SH-2)
   の工数 (合計 ~8h) と follow-up task scaffold 手順
4. `.steering/20260513-security-hardening-pre-m10/tasklist.md` の
   **P4 / P5 section** ← 本 task の実装 sub-task はそのまま transcribe
5. `.steering/20260513-security-hardening-pre-m10/codex-review.md` ←
   MEDIUM finding (test coverage gaps / observability) で本 task で
   対応するもの:
   - overflow observability: `logger.warning(...)` を `runtime_backlog_overflow`
     warning と同時に出す (in-band + out-of-band 二重化)
   - test coverage: TOCTOU race / maxsize boundary / mixed-ready recv 等の
     追加 test
6. `/Users/johnd/.claude/plans/agile-chasing-sifakis.md` (承認済 plan、§1 + §2
   section)

## 実装ターゲット: P4 (SH-2 WS auth, ~5h) + P5 (SH-1 hook+CI, ~3h)

### Step 1: 作業ディレクトリ scaffold (新規 task)

`/start-task security-hardening-pre-m10-followup` を実行し、以下 5 file を
template から生成:

- `.steering/<YYYYMMDD>-security-hardening-pre-m10-followup/requirement.md`
  ← M10-0 着手 gate の文脈 + PR #170 を Refs 引用
- `.steering/<YYYYMMDD>-security-hardening-pre-m10-followup/design.md`
  ← PR #170 の `decisions.md` SH-1 / SH-2 を copy + linkback
- `.steering/<YYYYMMDD>-security-hardening-pre-m10-followup/tasklist.md`
  ← PR #170 `tasklist.md` の P4 / P5 section を migrate + Codex 13th
    MEDIUM 反映タスクを追加
- `.steering/<YYYYMMDD>-security-hardening-pre-m10-followup/decisions.md`
  ← SH-1 / SH-2 ADR を verbatim 引用 (本 task では新 ADR を立てない、
    既存 ADR をそのまま実装)
- `.steering/<YYYYMMDD>-security-hardening-pre-m10-followup/blockers.md`
  ← 空 (実装中に発覚したものを記録)

branch 名: `feature/security-hardening-pre-m10-followup`

### Step 2: P4 — SH-2 WS auth (~5h)

PR #170 `tasklist.md` の **P4a / P4b / P4c / P4d** をそのまま実行:

- **P4a (protocol + Registry)**:
  - `integration/protocol.py:52` 近傍 — `DEFAULT_ALLOWED_ORIGINS` +
    `MAX_ACTIVE_SESSIONS=8` constant 追加 (~10 行)
  - `integration/protocol.py` — `SessionCapExceededError` exception 追加
  - `integration/gateway.py:194-202` — `Registry.add()` を `reserve_slot()`
    / `release_slot()` pair に置換 (~20 行)、cap 超過時
    `SessionCapExceededError` raise
- **P4b (bootstrap + CLI)**:
  - `bootstrap.py:70-71` `BootConfig` — `ws_token` / `require_token` /
    `allowed_origins` / `max_sessions` field 追加
  - `bootstrap.py` — `_resolve_ws_token()` helper (file → env → None)
  - `__main__.py:73-74` — `--ws-token` / `--require-token` /
    `--allowed-origins` / `--max-sessions` flag 追加
  - `host=0.0.0.0` + empty origin + `require_token=False` の startup
    error 実装
- **P4c (gateway integration)**:
  - `integration/gateway.py:518-552` — `accept()` 前に Origin/token/cap
    check 挿入 (subscribe parse error path L532-543 と同型)、close code
    1008 (policy) / 1013 (try-again-later)
  - `finally` で `registry.release_slot(session_id)` 確実呼出
- **P4d (test + doc)**:
  - `tests/test_integration/test_gateway.py` — 6 ケース追加
  - `docs/architecture.md:330` — 認証ポリシー更新
  - `docs/development-guidelines.md` — token rotate 運用ノート
  - `README.md` — `var/secrets/` provisioning 手順 (`mkdir -p var/secrets
    && chmod 700 var/secrets`)
  - Mac↔G-GEAR LAN smoke は手動 (`require_token=False` 確認、
    `decisions.md` に手順記録)
  - **follow-up task 起票**: `feat/ws-token-enforce` (`require_token=True`
    default 化、Godot WS client patch 後) — 本 task では実装しない
- commit: `feat(ws): shared-token + Origin + session cap (SH-2)`

### Step 3: P5 — SH-1 hook + CI shell-bypass (~3h)

PR #170 `tasklist.md` の **P5** をそのまま実行:

- `.codex/hooks.json:28-39` — matcher を
  `apply_patch|Edit|Write|exec_command|Bash` に拡張
- `.codex/hooks/pre_tool_use_policy.py` — `shell_write_targets(command)`
  helper 追加 (sed/echo/tee/python-c/heredoc deny pattern)
- `.codex/hooks/pre_tool_use_policy.py` — shell 経路で `.steering`
  completeness guard 発火
- `.github/workflows/ci.yml` — `policy-grep-gate` job 追加
  (banned import + ruff T201 backstop + `.steering` completeness)
- `tests/test_codex_hooks/__init__.py` + `test_shell_bypass_policy.py`
  5 ケース
- hook smoke: `echo '{"tool":"exec_command","tool_input":{"command":"sed
  -i s/x/y/ src/erre_sandbox/x.py"}}' | uv run python
  .codex/hooks/pre_tool_use_policy.py` → exit 2 + deny message
- commit: `feat(codex): hook + CI shell-bypass guard (SH-1)`

### Step 4: Codex 13th MEDIUM 反映 (~1h、本 task に同梱)

PR #170 review の MEDIUM 2 件で本 task 対応のもの:

- **MEDIUM (observability)**: `world/tick.py` `_enqueue_with_drop_oldest`
  で in-band ErrorMsg warning に加え `logger.warning(...)` も出す
  (SRE 観測強化)
- **MEDIUM (test coverage)**: `tests/test_world/` に以下追加:
  - maxsize-1 / maxsize / maxsize+1 boundary
  - repeated overflow で `_envelope_overflow_count` が monotonic
  - `_consume_result` 経由の overflow (`inject_envelope` だけでなく)
- **MEDIUM (test coverage SH-4)**: `tests/test_cli/test_eval_run_golden.py`
  に TOCTOU race regression (実用上 impossible なら docstring で
  documented と明記)

commit: `feat(observability+tests): SH-5 logger.warning + SH-4/SH-5 coverage`

### Step 5: P6 — Codex 14th independent review (~2h)

PR #170 と同じ pattern:

1. `.steering/<TASK>/codex-review-prompt.md` 起草 (P4 / P5 / MEDIUM 反映を
   scope に、4 commits 一括 review)
2. `cat codex-review-prompt.md | codex exec --skip-git-repo-check` 実行
3. 出力を `codex-review.md` に **verbatim 保存** (`.codex/budget.json`
   history を更新)
4. HIGH 全件: 実装に反映、commit/PR description にも明記
5. MEDIUM: `decisions.md` に採否を ADR addendum 形式で記録
6. LOW: `blockers.md` に defer 可、理由明記
7. HIGH/MEDIUM 反映 commit (必要に応じ複数 commit)

### Step 6: P7 — Closure + PR 起票

- `uv run ruff check src tests && uv run ruff format --check src tests &&
  uv run mypy src` 緑
- `uv run pytest -q -m "not godot and not eval and not spike and not
  training and not inference"` 緑
- 重点 test: gateway / world / cli / codex_hooks 全緑
- M9 baseline 不可侵検証: `git diff main..HEAD -- data/eval/golden
  src/erre_sandbox/evidence` 空
- `SCHEMA_VERSION = "0.10.0-m7h"` 不変
- PR 起票: title = `feat(security): security-hardening-pre-m10-followup
  (SH-1 + SH-2 + MEDIUM 反映)`、description で
  - 親 PR #170 を Refs
  - `codex-review.md` (Codex 14th) link
  - M10-0 着手 gate の解除を明示

## 制約 (絶対に守る)

- `data/eval/golden/` / `src/erre_sandbox/evidence/` への変更ゼロ
  (`git diff main..HEAD -- data/eval/golden src/erre_sandbox/evidence`
   が必ず空)
- `src/erre_sandbox/schemas.py:44` `SCHEMA_VERSION = "0.10.0-m7h"` 不変
- 新規 envelope type 追加 **禁止** (`ErrorMsg` の code に新 string 値を
  入れるのは可、Literal/Enum 拡張は不可)
- WS auth は **`require_token=False` default** (Mac↔G-GEAR LAN rsync
  保護、`feat/ws-token-enforce` で `True` 化は別 task)
- `host=0.0.0.0` 据置 (LAN 開発を壊さない、SH-2 ADR 通り)
- branch を main に直接 push しない (作業 branch 経由 + PR)
- `idea_judgement.md` / `idea_judgement_2.md` を本 task の commit に
  含めない (ユーザー方針)

## 想定工数

| Phase | 内容 | Hours |
|---|---|---|
| Step 1 | scaffold | 0.5 |
| Step 2 | P4 SH-2 WS auth | 5 |
| Step 3 | P5 SH-1 hook+CI | 3 |
| Step 4 | MEDIUM 反映 (observability + coverage) | 1 |
| Step 5 | P6 Codex 14th review | 2 |
| Step 6 | P7 closure + PR 起票 | 1 |
| **Total** | | **~12.5h** (2-3 working days) |

## 進捗報告フォーマット

各 Step 完了時に以下を 1 メッセージで報告:

- 変更ファイル + 行数
- 新規 test ケース名 + PASS 確認
- 既存テスト回帰の有無 (pytest 全 1379 件の差分)
- ruff / mypy / format 状態
- commit hash + 本文の主要 bullet
- 次 Step への移行可否

Step 5 (Codex 14th review) は **完了通知 + budget update + verdict**
を必ず報告 (verbatim 引用は不要、`codex-review.md` を Refs)。

## やらないこと

- Codex 13th の LOW finding 再対応 (ADOPT 済、追加変更なし)
- `feat/ws-token-enforce` (`require_token=True` default 化) — 本 task の
  follow-up として **別 task** で実装
- M10-0 task scaffold (本 follow-up task の close 後、且つ Codex 14th が
  green verdict を出した後)
- `idea_judgement.md` / `idea_judgement_2.md` の処理
- `next-session-prompt.md` (P2 時点起票、stale 確定) の更新 — 本 task close
  時に削除 (`git rm` で本 task の commit に含める)

タスク開始。
```

---

## このプロンプトの根拠

- **self-contained**: PR #170 merge 確認 / 既存 ADR (SH-1 + SH-2) 利用 / 各
  Step の sub-task / 制約 / 報告フォーマットをすべて embed
- **Plan mode skip 妥当**: SH-1 / SH-2 ADR は PR #170 の `decisions.md` で
  確定済 (Codex 12th + Codex 13th 両方で fact-check 済)、本 task は実装のみ
- **/reimagine skip 妥当**: SH-1 (3-layer hook + CI) / SH-2 (3-layer token +
  Origin + cap) ともに ADR で代替案 enumerate 済、再実行は context waste
- **Step 4 で MEDIUM 同梱**: PR #170 description で「follow-up task で対応」と
  明記した MEDIUM 2 件をここで closure する
- **M10-0 gate 解除を明示**: 本 task の close = M10-0 着手の前提条件達成、
  PR description に `blockers.md` の go/no-go gate 解除を書く
- **`feat/ws-token-enforce` 別 task 化**: `require_token=True` default 化は
  Godot WS client patch との依存があるので本 task に含めず、明示的に別 task
- **untracked clean-up タイミング**: `idea_judgement` 系は本 task 範囲外、
  `next-session-prompt.md` (P2 時点) のみ本 task で `git rm`

ファイル `next-session-prompt-followup.md` は本 task close 時 (PR #170 が
merge される直前 or 直後) に commit する。本 task の commit にはまだ含めない。

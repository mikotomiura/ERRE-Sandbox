# Codex review — security-hardening-pre-m10 (P0+P1+P2+P3, pre-push)

あなたは `feature/security-hardening-pre-m10` branch の **4 commits 一括** を
独立 review する立場。本 branch は **未 push** で、本 review の verdict が
push & PR 作成の最終 gate になる。M10-0 着手前の hardening スプリントなので、
**M9 baseline (`data/eval/golden/` 30 cells + `SCHEMA_VERSION` + `evidence/`)
の不可侵性** が最重要制約。

## 1. Background (essential context — 内面化必須)

### 1.1 タスク位置付け

- task: `security-hardening-pre-m10` (Path A: 独立 hardening タスク)
- 起源: Codex 12th review `codex_issue.md` の HIGH-1 / MEDIUM-2/3/4 / LOW-5/6
  の 6 finding のうち、§6 LOW (`.gitattributes`) は PR #161 で trivial close、
  残 5 件 (§1 hook bypass HIGH-1 / §2 0.0.0.0 / §3 web_search live / §4 path
  guard / §5 queue) を本 task で hardening
- ADR: SH-0 (meta-process) / SH-1 (§1) / SH-2 (§2) / SH-3 (§3) / SH-4 (§4) /
  SH-5 (§5) — design-final.md と decisions.md で定義
- 本 review 対象: **P0 + P1 + P2 + P3 の 4 commits** (P4/P5 は本 task 範囲外、
  P6 = この review)

### 1.2 commit 構造 (verbatim git log)

```
9061173 feat(world): bounded envelope queue + warning (SH-5)         ← P3
609037c feat(cli): eval --memory-db symlink+prefix+overwrite guard (SH-4)  ← P2
ad00499 chore(codex): network_access=false split (SH-3)              ← P1
f5295b5 docs(security): security-hardening-pre-m10 P0 scaffold (SH-0〜SH-5 ADR)  ← P0
```

- diff stat: 16 files, +1397 / -31
- M9 baseline 確認済: `git diff main..HEAD -- data/eval/golden src/erre_sandbox/evidence` = **empty**
- SCHEMA_VERSION 確認済: `src/erre_sandbox/schemas.py:44` = `"0.10.0-m7h"` 不変

### 1.3 各 commit の概要

| Commit | ADR | 内容 | 行数 |
|---|---|---|---|
| `f5295b5` (P0) | SH-0〜SH-5 ADR | docs scaffold (requirement / design / design-final / decisions / tasklist / blockers / codex-12th-review-source.md) + AGENTS.md / .agents/skills 微修正 | +941 docs / 0 src |
| `ad00499` (P1) | SH-3 | `.codex/config.toml` の `network_access` を `[sandbox_workspace_write]` table に分離、`web_search = "live"` 維持の根拠コメント追加 | +9 / -2 |
| `609037c` (P2) | SH-4 | `src/erre_sandbox/cli/eval_run_golden.py` の `--memory-db` に symlink + path prefix + overwrite guard を追加 + 5 unit test | +134 / -1 src, +117 / -0 test |
| `9061173` (P3) | SH-5 | `src/erre_sandbox/world/tick.py` の unbounded queue を 2-queue split (heartbeat coalesce + main drop-oldest + ErrorMsg warning) + 2 unit test + protocol.py docstring 整合 | +159 / -22 |

### 1.4 設計上の重要決定 (decisions.md verbatim 参照)

- **SH-3**: `web_search = "live"` 維持。理由: memory `project_m9_b_plan_pr.md`
  で Codex web_search が SGLang v0.3+ multi-LoRA support を発見し、Claude solo
  の stale 認識を補正した empirical 実績あり。`sandbox_workspace_write.network_access`
  と decoupled feature
- **SH-4**: `realpath` ベースの path prefix check + `os.path.lexists()` での
  symlink early detection + overwrite blocking (`--allow-overwrite` flag で
  opt-in)
- **SH-5**: 3 案 enumerate (1-queue / 2-queue / 3-queue) で 2-queue 採用。
  heartbeat (maxsize=1, coalesce / latest-wins) + main (maxsize=1024,
  drop-oldest + ErrorMsg "runtime_backlog_overflow")。`gateway.Registry.fan_out`
  の同型パターンを再利用 + tick.py 内に私的 `_make_runtime_error` を定義
  (world → integration の逆向き依存を回避)

## 2. レビュー対象成果物 (必ず Read してから review)

### 2.1 各 commit の diff を確認

```bash
# 全 4 commit の統合 diff (16 files, +1397/-31)
git log main..HEAD --oneline
git diff main..HEAD --stat
git show f5295b5  # P0
git show ad00499  # P1
git show 609037c  # P2
git show 9061173  # P3
```

### 2.2 設計判断 / ADR

- `.steering/20260513-security-hardening-pre-m10/design-final.md` — 確定版設計
- `.steering/20260513-security-hardening-pre-m10/decisions.md` — **SH-0〜SH-5 ADR 本体**
- `.steering/20260513-security-hardening-pre-m10/requirement.md`
- `.steering/20260513-security-hardening-pre-m10/tasklist.md`
- `.steering/20260513-security-hardening-pre-m10/blockers.md`
- `.steering/20260513-security-hardening-pre-m10/codex-12th-review-source.md` —
  本 task の起源 (Codex 12th の指摘 6 件)

### 2.3 実装ファイル

- `src/erre_sandbox/world/tick.py` (P3)
- `src/erre_sandbox/integration/protocol.py` (P3 docstring 整合)
- `src/erre_sandbox/integration/gateway.py:208-261` (P3 が同型パターンとして
  再利用した reference — **触っていない**、整合性確認用)
- `src/erre_sandbox/cli/eval_run_golden.py` (P2)
- `src/erre_sandbox/schemas.py:1126-1131` `ErrorMsg` 定義 — **不変**、整合性確認用
- `.codex/config.toml` (P1)
- `AGENTS.md` / `.agents/skills/erre-workflow/SKILL.md` (P0 微修正)

### 2.4 テストファイル

- `tests/test_world/test_runtime_lifecycle.py` (P3 新 2 ケース)
- `tests/test_world/test_tick.py` (P3 既存 1 ケース mechanical 調整)
- `tests/test_cli/test_eval_run_golden.py` (P2 新 5 ケース)
- `tests/test_integration/test_gateway.py:193-211` — P3 が雛形にした test
  (整合性確認用、変更なし)

## 3. 不変条件 (実装ですでに確認済 — fact-check してほしい)

以下は Claude 側で検証済だが、Codex が独立に fact-check してほしい:

1. **`data/eval/golden/` 30 cells**: `git diff main..HEAD -- data/eval/golden`
   が empty
2. **`src/erre_sandbox/evidence/`**: 同上 empty
3. **`SCHEMA_VERSION = "0.10.0-m7h"`** (`schemas.py:44`) 不変
4. **`ErrorMsg` の field 構造** (`schemas.py:1126-1131`) 不変、`code: str`
   なので新値 `"runtime_backlog_overflow"` は schema migration 不要
5. **新規 envelope type 追加なし** (Literal/Enum 拡張なし)
6. **architecture-rules**: `world → integration` の逆向き import 追加なし
   (`tick.py` から `gateway._make_error` を import せず、`_make_runtime_error`
   を `tick.py` 内に私的定義)
7. **CI 全緑**: pytest 1378 passed / 32 skipped / 52 deselected (markers)、
   ruff + mypy + format clean

これらが本当に成立しているか、独立に grep / git log / ls で fact-check すること。
**memory `project_pr159_m10_0_design_draft_merged.md` の W-6 (Codex 独立
file/dir fact-check が Claude solo の path 引用ミスを構造的に閉じる) の
empirical 実績を踏襲**。

## 4. レビュー軸 — 各 finding に ADOPT / MODIFY / REJECT を返答すること

以下の axis 全てを review し、各 finding を HIGH / MEDIUM / LOW で marking。

### HIGH (push & PR 作成前に必ず反映必須)

**HIGH-1 (SH-5 recv_envelope race-merge correctness)**:
`tick.py` `recv_envelope` の `asyncio.wait(FIRST_COMPLETED)` + main 優先 +
pending task cancel + `contextlib.suppress(CancelledError)` が、以下の
edge case で正しく動くか fact-check:

1. 両 task が同時に done になった場合 (`main_task in done` で main 優先 →
   pending side は空 set だが、両方 done なら片方は `done` に入っており
   `pending` には入らない。`if main_task in done` で main を return、hb 側の
   既に done な task は **cancel されず result が捨てられる**。これは intentional?)
2. main が先に done で hb が pending、cancel → hb 側に envelope が enqueue
   されていた race で hb_task の result が取り出されないまま捨てられる risk
3. `BaseException` 経路で両 task を cancel するが、その後の `await` がない
   ため、cancelled task の `__del__` が "Task was destroyed but is pending"
   warning を出す可能性
4. Python 3.11+ asyncio.Queue.get() の cancellation safety が `pyproject.toml`
   の `requires-python` で実際に保証されているか

実証: `pyproject.toml` の `requires-python` 行を grep + `recv_envelope`
の cancellation セマンティクスを CPython source (asyncio/queues.py) と
照合してください。

**HIGH-2 (SH-5 drop-oldest semantics と既存テスト契約の整合)**:
P3 で `drain_envelopes` の順序を **heartbeat → main** に変更した。元 Plan は
main → heartbeat の順だったが、`test_drain_is_fifo` (test_tick.py:514) と
`test_heartbeat_emits_world_tick_msgs_periodically` (test_tick.py:481) で
判明した既存契約に合わせて訂正。同時に test_heartbeat の
`len(heartbeats) == 5` を `== 1` に mechanical 調整。

質問:
- この変更で `recv_envelope` の semantics (main 優先) と `drain_envelopes`
  の semantics (heartbeat 優先) が **逆向き** になり、consumer 側が同じ
  runtime を両 method で使うと観測順序が異なる。これは intentional な
  trade-off か、bug か?
- `test_heartbeat_emits_world_tick_msgs_periodically` の元の assertion (5
  個) は「heartbeat の発火回数を gateway 経由で観測可能にする」契約だった
  可能性。1 個に折り畳むことで、観測契約が破壊されていないか?
- runtime 外部からの heartbeat 発火回数の観測手段 (counter / event log /
  metric) が今後必要になるか?

**HIGH-3 (SH-4 path prefix guard の bypass surface)**:
`cli/eval_run_golden.py` の `--memory-db` symlink + prefix + overwrite guard
について:
- `realpath` で symlink を解決した後の prefix check は、TOCTOU race で
  bypass される risk があるか? (check → write の間で symlink 入れ替え)
- macOS の case-insensitive filesystem で `realpath` の case 折り畳みが
  prefix check と一致するか? (`/tmp/X.db` vs `/tmp/x.db`)
- Windows path separator (`\` vs `/`) で fail-open する risk があるか?
- `--allow-overwrite` flag が opt-in だが、CI workflow / Makefile / shell
  alias で誤って auto-set される risk surface は?

実証: `tests/test_cli/test_eval_run_golden.py` の 5 ケースが上記 edge case
を網羅しているか確認。不足があれば追加 test ケース提案。

**HIGH-4 (SH-3 web_search live と network_access=false の整合)**:
`web_search = "live"` を維持する一方で `sandbox_workspace_write.network_access
= false` を split する設計判断。

- Codex CLI の内部実装で `web_search` が `sandbox_workspace_write` の
  network policy を bypass している前提が、Codex 内部仕様で恒久的に保証
  されているか? 仕様変更で `web_search` が `network_access=false` に隠れる
  regression risk は?
- `web_search` 経由で取得した URL の content を local file に書き出す経路
  (e.g. curl 経由ではなく Codex tool で fetch して file write) は
  `network_access=false` で blocked されるか?
- 本 split が **defense-in-depth** として有効か、それとも見かけの security
  posture を高めただけで実質効果がないか?

実証: `.codex/config.toml` 周辺の Codex CLI 仕様 (web_search の sandbox
boundary) を web_search 自身で確認してください (これは meta level の
fact-check で問題なし、本 prompt の場合 web_search が許可されています)。

### MEDIUM (本 task または P4/P5 で対応、PR description で defer 可)

各 commit について以下の axis を review:

- **MEDIUM (test coverage)**: P2 の 5 test ケース / P3 の 2 test ケース で、
  overflow boundary (maxsize-1, maxsize, maxsize+1)、empty / single / full
  state transition、concurrent put/get の race が十分網羅されているか
- **MEDIUM (logging granularity)**: P3 の `logger.debug(...)` / `logger.warning(...)`
  の log level 選択が SRE 観点で適切か。`runtime_backlog_overflow` は
  warning として上がるべきか info か
- **MEDIUM (ADR completeness)**: SH-0〜SH-5 ADR が、後続 P4/P5 着手時に
  context として self-contained か。特に SH-5 ADR が 1-queue/2-queue/3-queue
  3 案の trade-off を明示しているか
- **MEDIUM (docstring)**: P3 の `recv_envelope` / `drain_envelopes` /
  `_enqueue_with_drop_oldest` docstring が SH-5 ADR の意図 (heartbeat
  latest-wins の rationale) を runtime 読み手に伝えているか
- **MEDIUM (codex-12th-review-source.md)**: P0 で起こした
  `codex-12th-review-source.md` (本 task の起源 6 finding) が、本 P6
  review で defer / dropped と判定された finding を明示しているか

### LOW (defer 可、blockers.md 持ち越し可)

- **LOW (commit message)**: 4 commits の message が CLAUDE.md の Conventional
  Commits 規約 (feat/chore/docs scope) と整合か
- **LOW (idempotency)**: P3 の `_enqueue_with_drop_oldest` を同一 envelope で
  複数回呼んでも `_envelope_overflow_count` が conservative に増えるか
- **LOW (typing)**: `recv_envelope` 戻り値 `ControlEnvelope` が union type で
  Pyright/mypy narrow される際の inference 安定性
- **LOW (naming consistency)**: `_envelopes` vs `_heartbeat_envelopes` の
  非対称 naming (片方は前置詞付き) が将来 N-queue 拡張で破綻するか

### 構造的観点 (axis 全体に対する meta question)

- **META-1**: 本 task `security-hardening-pre-m10` は M10-0 着手前の **完全な**
  hardening と謳っているが、P4 (§2 WS auth) / P5 (§1 hook+CI) を defer
  したまま M10-0 に進む判断は妥当か? Codex 13th review が gate になる
  認識で正しいか? (push & PR 作成は本 review の verdict 待ち)
- **META-2**: 本 review prompt が context として渡している情報量で十分か、
  追加で Read すべき file があるか
- **META-3**: 本 task の `next-session-prompt.md` (untracked、本 commit に
  含まれず) と本 review verdict の整合が取れているか

## 5. 報告フォーマット

以下の structure で返答してください:

### 5.1 Executive verdict

選択肢:
- **ADOPT** — 4 commits をそのまま push & PR 化して良い
- **ADOPT-WITH-CHANGES** — 提示する HIGH finding を反映した上で push & PR 化
- **REVISE** — HIGH finding が複数あり、本 review を repeat する必要あり
- **REJECT** — 構造的に設計をやり直す必要あり

### 5.2 各 finding を 1 entry / 1 finding で

```
## HIGH-1: <短いタイトル>
Verdict: ADOPT / MODIFY / REJECT
Severity: HIGH / MEDIUM / LOW
File:Line: src/erre_sandbox/world/tick.py:701-732
要旨: <2-3 行で問題>
証拠: <grep / file content / external spec の引用>
推奨対応: <具体的な change instruction、必要なら diff>
```

### 5.3 META question への返答

META-1 / META-2 / META-3 に各 1 段落で。

### 5.4 fact-check sheet

§3 の不変条件 7 項目について、Codex 独立 grep / git log / ls 結果を
verbatim で返答 (W-6 の踏襲)。

## 6. 制約

- **fabrication 禁止**: file path / line number / 引用は必ず実機 grep / Read
  で確認。memory or inference で書かない (HIGH-5 PR #159 で Claude solo の
  path 引用ミスを Codex が補正した empirical 教訓を踏襲)
- **budget**: `.codex/budget.json` の `per_invocation_max=200K` を **目安**
  として、 overrun は warn policy なので 250-280K まで許容 (Codex 6th /
  Codex 12th と同等規模を想定)
- **report 形式**: 上記 §5 の structure で markdown
- **token economy**: HIGH 5 件以上切出 + META 3 件 + fact-check 7 項目を
  最低 deliverable とする

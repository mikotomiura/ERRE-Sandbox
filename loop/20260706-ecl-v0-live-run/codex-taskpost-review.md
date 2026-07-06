Reading prompt from stdin...
OpenAI Codex v0.141.0
--------
workdir: C:\ERRE-Sand_Box
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR]
reasoning effort: xhigh
reasoning summaries: none
session id: 019f3756-7caa-79e2-b4d2-f1f79d10f7a8
--------
user
# Codex TASK-POST cross-review — M13 Phase 1 sealed live run 統合 diff

Loop Engineering の **TASK-POST ゲート** (全 issue 緑 + 統合 CI 緑後、最終 merge 前)。ブランチ
`feat/ecl-v0-live-run` (main からの統合 diff) をレビューせよ。

## タスク概要
ECL v0 organ (live LLM 認知 × 3D embodiment substrate 統合器官) を **real qwen3:8b で一度封印実走**
(first-contact) し、captured Plane2 → Ollama-free deterministic replay-verify。**construction validation で
あって measurement verdict でない** (floor/landscape/verdict 非出力、measurement 非再入 holding 不可侵)。
sealed run 結果 = **GO** (O1 完走 / O2 replay 再現 / O3a-b cross-platform WSL byte 一致 / O5=32/32 / O4 非縮退)。

## レビュー対象 (統合 diff = main..feat/ecl-v0-live-run)
`git diff main..feat/ecl-v0-live-run -- src/ scripts/ tests/` の 4 ファイル (1326 行追加):
- `src/erre_sandbox/integration/embodied/live.py` — ThinkOffChatClient + run_live_capture + protocol 定数 +
  env-pin/observables overlay
- `scripts/ecl_v0_live_capture.py` — --capture (live) / --verify (Ollama-free replay-verify)
- `tests/test_integration/test_ecl_live_capture.py` — I1 apparatus test
- `tests/test_integration/test_ecl_live_golden.py` — I4 replay-verify test (live artifact = experiments/.../artifacts)
committed live artifact = `experiments/20260706-ecl-v0-live-capture/artifacts/{manifest,decisions,ecl_trace,
envelope_stream}` + env.md。

## 参照 (binding)
- FROZEN ADR: `.steering/20260706-m13-forward-primary/design-final.md` (§FROZEN、O1-O5、Done=O1∧O2∧O3a∧O3b)
- decisions: `.steering/20260706-ecl-v0-live-run/decisions.md` (D-1..8)
- TASK-PRE 反映済 (Codex): HIGH-1 ThinkOffChatClient / HIGH-2 O5 annotation 非 green-gate / MEDIUM-2 O3b env_pins
  再利用 / MEDIUM-3 O5 refinement。

## 特に見てほしい
1. **binding 遵守**: 既存 seam (loop.py/cycle.py/world/tick.py/handoff.py/ecl_v0_golden.py) 無改変か。
   measurement 非再入 (evidence/spdm/runningness 非 import、floor/landscape/verdict 非計算) は守られているか。
2. **ThinkOffChatClient**: think=False 強制転送が正しいか。inner 例外伝播 (OllamaUnavailableError) が record mode
   捕捉と競合しないか。
3. **cross-platform determinism**: verify の re-render が committed manifest env_pins/run を再利用し fresh capture
   drift を避けているか。6桁量子化の射程 (raw content 非 float は固定入力再利用) は正しいか。
4. **tune-to-pass 封鎖**: O5 が hard green gate でなく annotation (hard_gate=False)、O5==0 は branch outcome か。
   protocol 定数が sealed run 前固定か。
5. **correctness bug**: replay-verify の determinism 穴、env-pin 記録漏れ、async/リソース (store/embedding close)
   の扱い。
6. **事実誤認**は HIGH で切り出す。

## 報告
HIGH/MEDIUM/LOW + 根拠 (ファイル・行) + 推奨修正。末尾に **Verdict: Adopt / Adopt-with-changes / Revise /
Block**。doc/style 微細指摘不要、correctness + binding に集中。

deprecated: `[features].codex_hooks` is deprecated. Use `[features].hooks` instead.
Enable it with `--enable hooks` or `[features].hooks` in config.toml. See https://developers.openai.com/codex/config-basic#feature-flags for details.
2026-07-06T12:10:46.329394Z ERROR rmcp::transport::worker: worker quit with fatal: Transport channel closed, when AuthRequired(AuthRequiredError { www_authenticate_header: "Bearer resource_metadata=\"https://mcp.slack.com/.well-known/oauth-protected-resource\"" })
hook: SessionStart
hook: SessionStart Failed
hook: UserPromptSubmit
hook: UserPromptSubmit Failed
codex
`erre-workflow` とレビュー用 Skill を先に読み、TASK-POST の拘束条件に沿って diff を確認します。実装はせず、correctness と binding の逸脱に絞って見ます。
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Raw C:\\ERRE-Sand_Box\\.agents\\skills\\source-command-review-changes\\SKILL.md" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Raw C:\\Users\\johnd\\.codex\\plugins\\cache\\openai-bundled\\..\\..\\..\\..\\..\\ERRE-Sand_Box\\.agents\\skills\\erre-workflow\\SKILL.md" in C:\ERRE-Sand_Box
 succeeded in 286ms:
---
name: "source-command-review-changes"
description: "逶ｴ霑代・ git 螟画峩繧貞､夊ｧ堤噪縺ｫ繝ｬ繝薙Η繝ｼ縺吶ｋ縲Ｄode-reviewer 縺ｨ security-checker 繧・襍ｷ蜍輔＠縲∫ｵ先棡繧堤ｵｱ蜷医＠縺ｦ蝣ｱ蜻翫☆繧九ゅさ繝溘ャ繝亥燕縲￣R 菴懈・蜑阪↓螳溯｡後☆繧九・
---

# source-command-review-changes

Use this skill when the user asks to run the migrated source command `review-changes`.

## Command Template

# /review-changes

## 迴ｾ蝨ｨ縺ｮ迥ｶ豕・
$SHELL_PREPROCESS: git status --short 2>/dev/null || echo "(git 邂｡逅・､・"

## 螟画峩邨ｱ險・
$SHELL_PREPROCESS: git diff --stat HEAD 2>/dev/null || echo "(螟画峩縺ｪ縺・"

## 螳溯｡後ヵ繝ｭ繝ｼ

### Step 1: 螟画峩縺ｮ譛臥┌遒ｺ隱・
荳願ｨ倥・蜍慕噪繝・・繧ｿ縺九ｉ螟画峩繧堤｢ｺ隱阪ょ､画峩縺後↑縺・ｴ蜷医・荳ｭ譁ｭ:

> 縲悟､画峩縺後≠繧翫∪縺帙ｓ縲ゅΞ繝薙Η繝ｼ蟇ｾ雎｡縺後↑縺・◆繧∫ｵゆｺ・＠縺ｾ縺吶ゅ・
### Step 2: code-reviewer 縺ｮ襍ｷ蜍・
`code-reviewer` 繧ｵ繝悶お繝ｼ繧ｸ繧ｧ繝ｳ繝医ｒ襍ｷ蜍・

> Task: code-reviewer 縺ｧ逶ｴ霑代・ git diff 繧偵Ξ繝薙Η繝ｼ縲・IGH/MEDIUM 縺ｮ謖・遭繧貞━蜈育噪縺ｫ縲・
### Step 3: security-checker 縺ｮ襍ｷ蜍・
螟夜Κ蜈･蜉帙ｒ謇ｱ縺・､画峩繧・∬ｪ崎ｨｼ/隱榊庄縺ｫ髢｢繧上ｋ螟画峩縺後≠繧句ｴ蜷医～security-checker` 繧定ｵｷ蜍・

> Task: security-checker 縺ｧ螟画峩蜀・ｮｹ縺ｮ繧ｻ繧ｭ繝･繝ｪ繝・ぅ繝ｪ繧ｹ繧ｯ繧定ｪｿ譟ｻ縲・
### Step 4: 邨先棡縺ｮ邨ｱ蜷・
荳｡繧ｨ繝ｼ繧ｸ繧ｧ繝ｳ繝医°繧峨・繝ｬ繝昴・繝医ｒ邨ｱ蜷医＠縲∽ｻ･荳九・蠖｢蠑上〒陦ｨ遉ｺ:

```markdown
## 螟画峩繝ｬ繝薙Η繝ｼ邨先棡

### 螟画峩讎りｦ・- 螟画峩繝輔ぃ繧､繝ｫ謨ｰ: N
- 霑ｽ蜉陦梧焚: +N
- 蜑企勁陦梧焚: -N

### CRITICAL/HIGH・亥ｿ・亥ｯｾ蠢懶ｼ・[邨ｱ蜷医＠縺滓欠鞫肋

### MEDIUM・域耳螂ｨ蟇ｾ蠢懶ｼ・[邨ｱ蜷医＠縺滓欠鞫肋

### LOW・井ｻｻ諢丞ｯｾ蠢懶ｼ・[邨ｱ蜷医＠縺滓欠鞫肋

### 濶ｯ縺九▲縺溽せ
[code-reviewer 縺瑚ｩ穂ｾ｡縺励◆轤ｹ]
```

### Step 5: 繝ｦ繝ｼ繧ｶ繝ｼ縺ｸ縺ｮ謠先｡・
- CRITICAL/HIGH 縺後≠繧後・: 縲後％繧後ｉ繧剃ｿｮ豁｣縺励※縺九ｉ commit 縺励※縺上□縺輔＞縲・- 縺ｪ縺代ｌ縺ｰ: 縲慶ommit 縺励※蝠城｡後≠繧翫∪縺帙ｓ縲・
## 蛻ｶ邏・
- 蜈ｨ繝ｬ繝昴・繝医ｒ逕溘〒豬√＆縺ｪ縺・ｼ育ｵｱ蜷医・隕∫ｴ・☆繧具ｼ・- 驥崎ｦ√↑謖・遭繧定ｦ玖誠縺ｨ縺輔↑縺・- 縲悟撫鬘後↑縺励阪〒邨ゅｏ繧峨○繧句ｴ蜷医ｂ逅・罰繧定ｿｰ縺ｹ繧・

2026-07-06T12:11:01.900916Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.3 seconds
Output:
Get-Content : パス 'C:\Users\ERRE-Sand_Box\.agents\skills\erre-workflow\SKILL.md' が存在しないため検出できません。
発生場所 行:2 文字:1
+ Get-Content -Raw C:\Users\johnd\.codex\plugins\cache\openai-bundled\. ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\Users\ERRE-S...rkflow\SKILL.md:String) [Get-Content], ItemNotFoundEx 
   ception
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetContentCommand
 

 exited 1 in 306ms:
Get-Content : パス 'C:\Users\ERRE-Sand_Box\.agents\skills\erre-workflow\SKILL.md' が存在しないため検出できません。
発生場所 行:2 文字:1
+ Get-Content -Raw C:\Users\johnd\.codex\plugins\cache\openai-bundled\. ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\Users\ERRE-S...rkflow\SKILL.md:String) [Get-Content], ItemNotFoundEx 
   ception
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetContentCommand
 

codex
片方の Skill はローカルパス指定が誤っていたので読み直します。`source-command-review-changes` は文字化けしていますが、レビュー専用サブエージェントを起動する手順が中心の内容でした。
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-Content -Raw -Encoding UTF8 C:\\ERRE-Sand_Box\\.agents\\skills\\erre-workflow\\SKILL.md" in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-Content -Raw -Encoding UTF8 C:\\ERRE-Sand_Box\\.agents\\skills\\source-command-review-changes\\SKILL.md" in C:\ERRE-Sand_Box
 succeeded in 250ms:
---
name: erre-workflow
description: >
  ERRE-Sandbox task workflow for Codex. Use when starting, designing, implementing,
  reviewing, or finishing repository work; when the user mentions /start-task,
  /add-feature, /fix-bug, /refactor, /reimagine, /review-changes, or /finish-task;
  or when .steering records, Codex setup, task plans, or implementation handoffs are needed.
---

# ERRE Workflow

This is the Codex-native replacement for the Claude slash-command workflow. Claude command
files in `.claude/commands/` are reference material only; Codex should execute the workflow
through normal tool use, `.steering/` records, skills, hooks, and custom agents.

## Quick Start

1. Read `AGENTS.md`, `docs/development-guidelines.md`, and the relevant domain skill.
2. Create or update `.steering/YYYYMMDD-task-name/` before implementation work:
   `requirement.md`, `design.md`, and `tasklist.md` are required.
3. For design-heavy work, keep implementation paused until a plan is accepted. If the task
   has multiple plausible designs, perform a reimagine pass before editing source files.
4. Implement in small steps, updating `tasklist.md` as work completes.
5. Verify with focused checks first, then the documented full checks when feasible.
6. Finish by reviewing the diff and recording any decisions or limitations.

Use subagents only when the user explicitly asks for delegation or parallel agent work.
When they do, prefer the project-scoped agents in `.codex/agents/`.

## Task Start

Create `.steering/YYYYMMDD-task-name/` with:

- `requirement.md`: background, goal, scope, out of scope, acceptance criteria.
- `design.md`: approach, changed areas, compatibility, test strategy, rollback.
- `tasklist.md`: checkboxes at roughly 30-minute granularity.
- `decisions.md`: only for meaningful tradeoffs or policy choices.
- `blockers.md`: only when blocked or carrying deferred risk.

Use the current local date in `YYYYMMDD`. Prefer a short kebab-case task name.

## Implementation Flows

- **Feature**: read existing patterns, document the design, implement narrowly, add tests or
  verification proportional to risk, update docs when behavior changes.
- **Bug fix**: reproduce or explain the failure, record root cause, add or identify a
  regression check when feasible, then make the smallest defensible fix.
- **Refactor**: establish current checks first, preserve behavior, change in small steps,
  and avoid mixing feature or bug-fix work into the same task.

For source edits under `src/erre_sandbox/`, always consider:

- `architecture-rules` for layer direction and GPL/cloud API constraints.
- `python-standards` for Python style.
- `error-handling` when async, retry, timeout, WebSocket, sqlite, or LLM fallback behavior changes.
- `test-standards` when adding or changing tests.

## Reimagine

Use this for architecture, public interfaces, difficult bugs, and designs with multiple
credible approaches:

1. Save the first plan as `design-v1.md`.
2. Re-read only `requirement.md` and produce a fresh alternative in `design.md`.
3. Compare the two in `design-comparison.md`.
4. Choose v1, v2, or a hybrid and record the reason in `decisions.md`.

Do not use reimagine after implementation has already created side effects that would need
manual rollback.

## Network Access Policy

The `.codex/config.toml` workspace_write sandbox defaults to `network_access = false`
(SH-3 ADR, 2026-05-13). Codex `web_search = "live"` is decoupled and stays enabled —
queries leave the box, but repo contents do not.

Do NOT toggle `network_access = true` without explicit per-session user approval.
If a task genuinely needs egress (e.g. `uv sync` for a fresh dependency), surface
the need to the user first and request a one-shot override via `--config
sandbox_workspace_write.network_access=true`. Do not commit a `true` value into
`.codex/config.toml`. See `AGENTS.md` "Network access policy" section.

## Review And Finish

Before final delivery:

- Run focused checks for touched areas.
- Run `uv run ruff check src tests`, `uv run ruff format --check src tests`,
  `uv run mypy src`, and `uv run pytest` when feasible.
- Review `git diff` for unrelated changes and do not revert user work.
- Update `tasklist.md` and `design.md` with what actually happened.
- Mention skipped checks or residual risk in the final response.

Do not commit unless the user asks. If committing, use `git-workflow`.


 succeeded in 242ms:
---
name: "source-command-review-changes"
description: "直近の git 変更を多角的にレビューする。code-reviewer と security-checker を 起動し、結果を統合して報告する。コミット前、PR 作成前に実行する。"
---

# source-command-review-changes

Use this skill when the user asks to run the migrated source command `review-changes`.

## Command Template

# /review-changes

## 現在の状況

$SHELL_PREPROCESS: git status --short 2>/dev/null || echo "(git 管理外)"

## 変更統計

$SHELL_PREPROCESS: git diff --stat HEAD 2>/dev/null || echo "(変更なし)"

## 実行フロー

### Step 1: 変更の有無確認

上記の動的データから変更を確認。変更がない場合は中断:

> 「変更がありません。レビュー対象がないため終了します。」

### Step 2: code-reviewer の起動

`code-reviewer` サブエージェントを起動:

> Task: code-reviewer で直近の git diff をレビュー。HIGH/MEDIUM の指摘を優先的に。

### Step 3: security-checker の起動

外部入力を扱う変更や、認証/認可に関わる変更がある場合、`security-checker` を起動:

> Task: security-checker で変更内容のセキュリティリスクを調査。

### Step 4: 結果の統合

両エージェントからのレポートを統合し、以下の形式で表示:

```markdown
## 変更レビュー結果

### 変更概要
- 変更ファイル数: N
- 追加行数: +N
- 削除行数: -N

### CRITICAL/HIGH（必須対応）
[統合した指摘]

### MEDIUM（推奨対応）
[統合した指摘]

### LOW（任意対応）
[統合した指摘]

### 良かった点
[code-reviewer が評価した点]
```

### Step 5: ユーザーへの提案

- CRITICAL/HIGH があれば: 「これらを修正してから commit してください」
- なければ: 「commit して問題ありません」

## 制約

- 全レポートを生で流さない（統合・要約する）
- 重要な指摘を見落とさない
- 「問題なし」で終わらせる場合も理由を述べる


codex
まず diff の実体と現在の作業ツリーを確認します。レビュー対象は `main..feat/ecl-v0-live-run` に固定し、作業ツリーの未コミット差分とは混ぜません。
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short --branch' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff --stat main..feat/ecl-v0-live-run -- src/ scripts/ tests/' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff --name-status main..feat/ecl-v0-live-run -- src/ scripts/ tests/' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git branch --show-current' in C:\ERRE-Sand_Box
 succeeded in 288ms:
## feat/ecl-v0-live-run
?? experiments/20260630-es4-phase0/sglang.log
?? loop/20260706-ecl-v0-live-run/codex-taskpost-prompt.md
?? loop/20260706-ecl-v0-live-run/codex-taskpost-review.md
warning: unable to access 'C:\Users\johnd/.config/git/ignore': Permission denied
warning: unable to access 'C:\Users\johnd/.config/git/ignore': Permission denied

 succeeded in 312ms:
A	scripts/ecl_v0_live_capture.py
A	src/erre_sandbox/integration/embodied/live.py
A	tests/test_integration/test_ecl_live_capture.py
A	tests/test_integration/test_ecl_live_golden.py

 succeeded in 340ms:
 scripts/ecl_v0_live_capture.py                  | 330 ++++++++++++++++++++
 src/erre_sandbox/integration/embodied/live.py   | 315 +++++++++++++++++++
 tests/test_integration/test_ecl_live_capture.py | 395 ++++++++++++++++++++++++
 tests/test_integration/test_ecl_live_golden.py  | 286 +++++++++++++++++
 4 files changed, 1326 insertions(+)

 succeeded in 328ms:
feat/ecl-v0-live-run

codex
diff は対象どおり 4 ファイル追加だけです。次に binding の frozen 条件と実装ファイルを行番号付きで読み、仕様違反と deterministic replay の穴を探します。
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-Content -Raw -Encoding UTF8 .steering\\20260706-ecl-v0-live-run\\decisions.md" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-Content -Raw -Encoding UTF8 .steering\\20260706-m13-forward-primary\\design-final.md" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content src'"\\erre_sandbox\\integration\\embodied\\live.py | ForEach-Object { "'$i++; '"'{0,5}: {1}' -f "'$i, $_ }' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content scripts'"\\ecl_v0_live_capture.py | ForEach-Object { "'$i++; '"'{0,5}: {1}' -f "'$i, $_ }' in C:\ERRE-Sand_Box
 succeeded in 286ms:
# decisions — M13 Phase 1 sealed live run (grill 確定、D-1..8)

すべて FROZEN ADR 設計意図内の実装レベル決定 (ユーザー付託不要、軸1=No)。形式 = 決定 / 理由 / 却下案。

## D-1: sealed run horizon N_cognition = 32
- **決定**: N_cognition=32 (physics 20/cognition = 640 physics row)。sealed run 前固定、run 後 tune 禁止。
- **理由**: golden の 8 より長尺で「longer horizon 安定完走」を construction 観測、committed artifact も過大でない。
- **却下**: N=8 (golden と同=長尺観測にならない) / N=100+ (artifact 肥大、measurement 的分布誘惑)。

## D-2: persona = kant, 単一 agent
- **決定**: golden と同じ kant persona、単一 agent。
- **理由**: 最小・golden との差分最小。単一 agent は ADR scope (N体化は holding)。
- **却下**: 複数 persona (N体化=B、後置)。

## D-3: sampling = live cycle resolved を verbatim 記録 (think のみ False 強制)
- **決定**: manual sampling override せず、cycle が persona+ERRE mode から compose した ResolvedSampling を
  decisions.jsonl に verbatim 記録。think のみ ThinkOffChatClient で False 強制。
- **理由**: organ の live 挙動をそのまま capture (minimal reality surface)。sampling を弄ると first-contact が
  人工的になる。
- **却下**: 固定 sampling 注入 (organ の実挙動でない)。

## D-4: embedding = constant-vector mock (real nomic-embed-text 不使用)
- **決定**: live capture も `_offline_embedding` 相当の constant-vector mock。live なのは action LLM chat のみ。
- **理由**: ADR §DA-FWD-2 minimal reality surface = real は action LLM の決定のみ。real embedding は非決定源+
  cross-platform drift+replay 記録拡張を招き construction claim を強めない。retrieval は実 memory 蓄積+実
  centroid 幾何で走り履歴依存 channel は生きる (類似度だけ mock)。
- **却下**: real nomic-embed-text (superseding milestone、minimal reality surface の拡張)。

## D-5: O5 = parsed-history-dependent-action、count 記録 (annotation、FROZEN O5 の refinement)
- **決定**: O5 = `llm_status=="ok"` ∧ `plan is not None` ∧ MoveMsg `resolved_from=="memory_centroid"` の成立 tick
  を **count 記録** (annotation)。first-contact の存在証明として ≥1 を GO 条件とするが、**hard green gate に
  しない** — O5==0 は test 失敗でなく construction 妥当性 branch (軸5、人手判断、Execution Result 記録)。
- **理由**: first-contact は存在証明 (real plan が real 履歴依存 move を駆動した ≥1 例)。全 tick 要求は real LLM の
  unparseable 揺れで tune-to-pass 誘発、分布要求は measurement。**O5 を autonomous green gate にすると loop が O5 へ
  tune-to-pass する** (Codex TASK-PRE HIGH-2) → annotation + 人手 branch に。
- **FROZEN との差分 (Codex TASK-PRE MEDIUM-3 = D-5 refinement を明示)**: FROZEN O5 (design-final §事前登録) は
  `plan≠None` ∧ MoveMsg が **parsed `destination_zone` 由来**。本 D-5 は `resolved_from=="memory_centroid"` まで
  要求 = 「parsed zone が **履歴依存** move を駆動」の強化。intent = 履歴依存 move 実証ゆえ test 名を
  `test_live_golden_parsed_history_dependent_action` に寄せ、この強化を refinement として明記 (FROZEN 逸脱でなく
  construction intent 内の厳密化)。
- **却下**: 全 tick ok 要求 (脆い+tune 誘発) / 成功率閾値 (measurement 的) / O5 を hard green gate (tune-to-pass)。

## D-6: O3a/O3b cross-platform = CI replay-verify (platform 非依存) + I3 手動 WSL byte 一致
- **決定**: (a) CI test = committed artifact→replay checksum 一致+inner_invocations==0 (O3a) / raw Plane2→
  artifact re-render SHA 一致 (O3b)。(b) cross-platform equality は I3 で WSL Linux vs Windows byte 一致を手動実測
  (env.md 記録)。
- **理由**: 6桁量子化は float drift のみ (Codex HIGH-2)。raw content 等 non-float は固定入力再利用で一致。live
  再 capture の cross-platform byte 一致は非要求 (live LLM 出力は cross-machine 非決定)。PR #55 golden と同手順。
- **却下**: cross-platform live 再 capture の byte 一致要求 (再現不能、Codex HIGH-2 で否定)。

## D-7: harness = 新規 script (synthetic golden 無改変)
- **決定**: 新規 `scripts/ecl_v0_live_capture.py`。`ecl_v0_golden.py` (synthetic) は無改変温存。
- **理由**: synthetic golden は fast CI determinism 単体 guard として別用途。live capture は construction evidence。
- **却下**: ecl_v0_golden.py 拡張 (用途混同、CI hot path 汚染)。

## D-8: committed live artifact = experiments/、verify test = tests/
- **決定**: artifact は `experiments/20260706-ecl-v0-live-capture/artifacts/` に committed。replay-verify test は
  tests/ 配下 (CI lint/type 網羅) が experiments の artifact を読む。
- **理由**: sealed run は experiment (reproducibility-discipline)。experiments/ script は CI lint 対象外ゆえ検証
  logic を tests/ に置く。pytest は experiments のファイルを読める。
- **却下**: artifact を tests/fixtures/ (sealed run の実験 provenance を失う、ADR §DA-FWD-3)。


 succeeded in 345ms:
    1: """ECL v0 live-capture apparatus 窶・Issue 001 (loop/20260706-ecl-v0-live-run).
    2: 
    3: Builds the *apparatus* for a real-``qwen3:8b`` (Ollama) record-mode sealed run
    4: of the Embodied Cognition Loop v0 organ (FROZEN ADR
    5: ``.steering/20260706-m13-forward-primary/design-final.md`` ﾂｧFROZEN binding
    6: a-e, ﾂｧ莠句燕逋ｻ骭ｲ). The actual live capture is Issue 003; this module is
    7: Ollama-free and fully testable with a mock inner chat client.
    8: 
    9: Two pieces this module owns, neither of which the existing seam owns:
   10: 
   11: * :class:`ThinkOffChatClient` 窶・a driver-local wrapper that forces
   12:   ``think=False`` on every ``chat`` call regardless of what the caller passed
   13:   (Codex TASK-PRE HIGH-1). ``cognition.cycle.CognitionCycle`` calls
   14:   ``llm.chat(..., sampling=...)`` without ever setting ``think``, and
   15:   :class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient` only emits
   16:   the wire-level ``think`` key when it is not ``None`` 窶・so without this
   17:   wrapper qwen3:8b spends its response budget on ``<think>`` reasoning and
   18:   returns empty ``content``, and every action-LLM call fails to parse. The
   19:   wrapper closes that gap **without touching** ``cognition/cycle.py``.
   20: * :func:`run_live_capture` 窶・dependency-injects an ``inner_chat`` (real
   21:   ``OllamaChatClient`` in Issue 003, a mock in this module's tests), wraps it
   22:   in :class:`ThinkOffChatClient` then
   23:   :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient` in
   24:   *record* mode, and drives
   25:   :func:`~erre_sandbox.integration.embodied.loop.run_ecl_loop` 窶・the existing
   26:   Issue 004 harness, imported and called, never modified.
   27: 
   28: Pre-registered protocol constants (D-1/D-2/D-4/D-5, sealed-run-before fixed,
   29: tune-to-pass closed): :data:`LIVE_N_COGNITION_TICKS` / :data:`LIVE_PERSONA_ID`
   30: / :data:`LIVE_EMBEDDING_MODE` / :data:`LIVE_O5_MIN_TICKS`.
   31: 
   32: Manifest env-pin + observables overlay (Codex TASK-PRE HIGH-1):
   33: ``handoff.build_manifest`` carries no ``observables`` field, so this module
   34: supplies :func:`build_live_env_pins` (qwen3 digest / Ollama version / VRAM /
   35: uv.lock hash / ``think:false`` / resolved sampling, merged into the manifest's
   36: ``env_pins`` block *without* touching ``handoff.py``) and
   37: :func:`build_live_manifest_overlay` / :func:`attach_live_observables` (the
   38: O1-O5 pre-registration, ``done_formula`` and ``o5_min_ticks``, attached as a
   39: sealed-run-before constant ``observables`` block on top of the manifest dict
   40: ``handoff.build_manifest`` returns).
   41: 
   42: Scope guard (design-final.md ﾂｧ隲也せ4/ﾂｧ隲也せ5, binding, mirrors ``loop.py`` /
   43: ``handoff.py``). This is a *construction* apparatus, **NOT a measurement
   44: line 窶・final judgement 縺ｯ holding**. It imports no ``evidence`` / ``spdm`` /
   45: ``runningness`` machinery and computes/emits no floor / landscape / final
   46: judgement statistic. O4/O5 are pre-registered *annotation* text only in this
   47: module (Issue 001 scope); the actual per-tick counting (if ever computed) is a
   48: non-gate boolean count, never a measurement-line statistic (ﾂｧ莠句燕逋ｻ骭ｲ).
   49: """
   50: 
   51: from __future__ import annotations
   52: 
   53: from typing import TYPE_CHECKING, Any, Final
   54: 
   55: from erre_sandbox.cognition.embodiment import K_ECL
   56: from erre_sandbox.integration.embodied import handoff
   57: from erre_sandbox.integration.embodied.loop import (
   58:     DEFAULT_PHYSICS_TICKS_PER_COGNITION,
   59:     RecordReplayChatClient,
   60:     run_ecl_loop,
   61: )
   62: 
   63: if TYPE_CHECKING:
   64:     from collections.abc import Callable, Sequence
   65:     from datetime import datetime
   66: 
   67:     from erre_sandbox.cognition.reflection import Reflector
   68:     from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse
   69:     from erre_sandbox.inference.sampling import ResolvedSampling
   70:     from erre_sandbox.integration.embodied.loop import EclRunResult
   71:     from erre_sandbox.memory import EmbeddingClient, MemoryStore
   72:     from erre_sandbox.schemas import AgentState, Observation, PersonaSpec
   73: 
   74: # --------------------------------------------------------------------------- #
   75: # Pre-registered protocol constants (D-1/D-2/D-4/D-5, sealed-run-before fixed)
   76: # --------------------------------------------------------------------------- #
   77: 
   78: LIVE_N_COGNITION_TICKS: Final[int] = 32
   79: """Sealed live run horizon (D-1): 32 cognition ticks (640 physics rows at the
   80: default 20 physics-ticks-per-cognition), longer than the 8-tick synthetic
   81: golden to construction-observe a longer-horizon completion. Fixed before the
   82: sealed run; run-after tuning is a Stop condition (ﾂｧ莠句燕逋ｻ骭ｲ tune-to-pass
   83: closure)."""
   84: 
   85: LIVE_PERSONA_ID: Final[str] = "kant"
   86: """Sealed live run persona (D-2): the golden's persona, single agent (D-2)."""
   87: 
   88: LIVE_EMBEDDING_MODE: Final[str] = "mock"
   89: """Sealed live run embedding source (D-4): a constant-vector mock (the same
   90: family as ``scripts.ecl_v0_golden._offline_embedding``), never real
   91: ``nomic-embed-text``. Only the action-LLM chat call is live (minimal reality
   92: surface, ADR ﾂｧDA-FWD-2)."""
   93: 
   94: LIVE_O5_MIN_TICKS: Final[int] = 1
   95: """Minimum tick count for the O5 parsed-history-dependent-action annotation
   96: (D-5): ``llm_status=="ok"`` and ``plan is not None`` and the MoveMsg
   97: ``resolved_from=="memory_centroid"`` on at least this many ticks is the
   98: first-contact existence proof. **Not a hard green gate** 窶・D-5 records O5 as a
   99: count annotation with a human-judgement construction-validity branch, not an
  100: autonomous pass/fail (Codex TASK-PRE HIGH-2: an autonomous gate on O5 would
  101: tune-to-pass the loop toward it)."""
  102: 
  103: LIVE_DONE_FORMULA: Final[str] = "O1竏ｧO2竏ｧO3a竏ｧO3b"
  104: """The FROZEN reproducibility-Done formula (design-final.md ﾂｧ莠句燕逋ｻ骭ｲ): a
  105: conjunction of the four reproducibility observables. O4/O5 are
  106: channel-exercise annotations, not part of this formula."""
  107: 
  108: # --------------------------------------------------------------------------- #
  109: # ThinkOffChatClient 窶・force think=False without touching cognition/cycle.py
  110: # --------------------------------------------------------------------------- #
  111: 
  112: 
  113: class ThinkOffChatClient:
  114:     """Wraps an inner chat client and forces ``think=False`` (Codex HIGH-1).
  115: 
  116:     Duck-typed to the same ``chat`` keyword surface
  117:     :class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient.chat`
  118:     exposes (and that :class:`~erre_sandbox.cognition.CognitionCycle` calls),
  119:     so it stands in transparently as the ``inner`` of a
  120:     :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`.
  121: 
  122:     ``messages`` / ``sampling`` / ``model`` / ``options`` are forwarded
  123:     unchanged; only ``think`` is overridden 窶・whatever the caller passed (in
  124:     practice always ``None``, since ``cognition/cycle.py`` never sets it) is
  125:     replaced with ``False`` before the inner client is called. The inner
  126:     client's :class:`~erre_sandbox.inference.ollama_adapter.ChatResponse` (or a
  127:     raised
  128:     :class:`~erre_sandbox.inference.ollama_adapter.OllamaUnavailableError`) is
  129:     returned/propagated verbatim.
  130:     """
  131: 
  132:     def __init__(self, inner: Any) -> None:
  133:         self._inner = inner
  134: 
  135:     async def chat(
  136:         self,
  137:         messages: Sequence[ChatMessage],
  138:         *,
  139:         sampling: ResolvedSampling,
  140:         model: str | None = None,
  141:         options: dict[str, Any] | None = None,
  142:         think: bool | None = None,  # noqa: ARG002 窶・always overridden below
  143:     ) -> ChatResponse:
  144:         return await self._inner.chat(
  145:             messages,
  146:             sampling=sampling,
  147:             model=model,
  148:             options=options,
  149:             think=False,
  150:         )
  151: 
  152: 
  153: # --------------------------------------------------------------------------- #
  154: # Live capture harness (record mode only; replay reuses loop.replay_client_from)
  155: # --------------------------------------------------------------------------- #
  156: 
  157: 
  158: async def run_live_capture(
  159:     *,
  160:     inner_chat: Any,
  161:     store: MemoryStore,
  162:     embedding: EmbeddingClient,
  163:     run_id: str,
  164:     agent_state: AgentState,
  165:     persona: PersonaSpec,
  166:     retrieval_now: datetime,
  167:     base_ts: datetime,
  168:     seed: int = 0,
  169:     n_cognition_ticks: int = LIVE_N_COGNITION_TICKS,
  170:     physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
  171:     k_ecl: int = K_ECL,
  172:     reflector: Reflector | None = None,
  173:     observation_factory: Callable[[int], Sequence[Observation]] | None = None,
  174: ) -> EclRunResult:
  175:     """Drive one record-mode ECL v0 run through ``inner_chat`` (real or mock).
  176: 
  177:     Wraps ``inner_chat`` in :class:`ThinkOffChatClient` (forces ``think=False``)
  178:     then in a record-mode
  179:     :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`, and
  180:     hands both plus every other argument to the existing
  181:     :func:`~erre_sandbox.integration.embodied.loop.run_ecl_loop` driver
  182:     **unmodified**. ``store`` / ``embedding`` are dependency-injected so this
  183:     function never constructs its own Ollama or sqlite-vec connection 窶・a live
  184:     caller (Issue 003) wires a real ``OllamaChatClient``; the tests in this
  185:     module wire a mock.
  186:     """
  187:     think_off = ThinkOffChatClient(inner_chat)
  188:     llm = RecordReplayChatClient(inner=think_off)
  189:     return await run_ecl_loop(
  190:         run_id=run_id,
  191:         store=store,
  192:         embedding=embedding,
  193:         llm=llm,
  194:         agent_state=agent_state,
  195:         persona=persona,
  196:         retrieval_now=retrieval_now,
  197:         base_ts=base_ts,
  198:         seed=seed,
  199:         n_cognition_ticks=n_cognition_ticks,
  200:         physics_ticks_per_cognition=physics_ticks_per_cognition,
  201:         k_ecl=k_ecl,
  202:         reflector=reflector,
  203:         observation_factory=observation_factory,
  204:     )
  205: 
  206: 
  207: # --------------------------------------------------------------------------- #
  208: # Manifest env-pin + observables overlay (handoff.py untouched, overlay lives here)
  209: # --------------------------------------------------------------------------- #
  210: 
  211: 
  212: def build_live_env_pins(
  213:     *,
  214:     qwen3_model_digest: str,
  215:     ollama_version: str,
  216:     vram_gb: float,
  217:     uv_lock_sha256: str,
  218:     resolved_sampling: ResolvedSampling,
  219:     base_env_pins: dict[str, Any] | None = None,
  220: ) -> dict[str, Any]:
  221:     """Merge the live-capture env pins onto ``handoff.capture_env_pins()``.
  222: 
  223:     Adds the fields the sealed live run must pin beyond the synthetic golden's
  224:     ``env_pins`` (python/packages/godot/ERRE_ZONE_BIAS_P): the qwen3 model
  225:     digest actually pulled, the Ollama server version, available VRAM, the
  226:     ``uv.lock`` hash (reproducibility-discipline), the forced ``think=False``
  227:     flag (D-5/Codex HIGH-1), and the cycle's live-resolved sampling verbatim
  228:     (D-3: sampling is captured, never manually overridden). ``base_env_pins``
  229:     defaults to a fresh :func:`~...handoff.capture_env_pins` snapshot so a
  230:     caller can also pass a frozen snapshot for reproducible tests.
  231:     """
  232:     pins: dict[str, Any] = dict(
  233:         base_env_pins if base_env_pins is not None else handoff.capture_env_pins()
  234:     )
  235:     pins["qwen3_model_digest"] = qwen3_model_digest
  236:     pins["ollama_version"] = ollama_version
  237:     pins["vram_gb"] = vram_gb
  238:     pins["uv_lock_sha256"] = uv_lock_sha256
  239:     pins["think"] = False
  240:     pins["resolved_sampling"] = resolved_sampling.model_dump(mode="json")
  241:     return pins
  242: 
  243: 
  244: LIVE_OBSERVABLES: Final[dict[str, Any]] = {
  245:     "O1": (
  246:         "N cognition ticks x M physics ticks completed against a live Ollama "
  247:         "qwen3:8b with no exception (full completion)"
  248:     ),
  249:     "O2": (
  250:         "replaying from the captured decisions alone reproduces a "
  251:         "byte-identical ecl_trace_checksum with inner_invocations==0"
  252:     ),
  253:     "O3a": (
  254:         "the same committed decisions.jsonl replays to the same checksum "
  255:         "with inner_invocations==0 on both WSL Linux (glibc) and Windows (UCRT)"
  256:     ),
  257:     "O3b": (
  258:         "the same raw Plane 2 re-renders the full artifact set to the same "
  259:         "SHA-256 set on both platforms (6-decimal float quantisation absorbs "
  260:         "libm drift)"
  261:     ),
  262:     "O4": (
  263:         "non-degeneracy: a pure boolean count (never a divergence/floor "
  264:         "statistic) of whether the LLM chose >1 distinct destination zone "
  265:         "and/or the resolver produced >1 distinct move target across the run "
  266:         "(annotation, not a Done gate)"
  267:     ),
  268:     "O5": (
  269:         "parsed-history-dependent-action count (D-5 refinement, annotation, "
  270:         "not a hard green gate): the tick count where llm_status=='ok' and "
  271:         "plan is not None and the MoveMsg resolved_from=='memory_centroid'; "
  272:         f">= {LIVE_O5_MIN_TICKS} tick is the first-contact existence proof"
  273:     ),
  274:     "done_formula": LIVE_DONE_FORMULA,
  275:     "o5_min_ticks": LIVE_O5_MIN_TICKS,
  276: }
  277: """Sealed-run-before constant observables pre-registration (tune-to-pass
  278: closure, Codex TASK-PRE HIGH-1): the O1-O5 definitions design-final.md
  279: ﾂｧ莠句燕逋ｻ骭ｲ fixes, plus the FROZEN ``done_formula`` and the D-5
  280: ``o5_min_ticks`` threshold. Frozen at import time (not derived from any run
  281: outcome), so a sealed run cannot retroactively redefine what it is judged
  282: against."""
  283: 
  284: 
  285: def build_live_manifest_overlay() -> dict[str, Any]:
  286:     """Return the sealed-run-before ``observables`` overlay block (a fresh copy)."""
  287:     return dict(LIVE_OBSERVABLES)
  288: 
  289: 
  290: def attach_live_observables(manifest: dict[str, Any]) -> dict[str, Any]:
  291:     """Return ``manifest`` with the ``observables`` overlay attached (non-mutating).
  292: 
  293:     ``handoff.build_manifest`` (untouched) has no ``observables`` field; this
  294:     function is the live-capture-side seam that adds it on top of the dict
  295:     ``build_manifest`` returns, so ``handoff.py`` never needs to know about the
  296:     live-capture pre-registration.
  297:     """
  298:     overlaid = dict(manifest)
  299:     overlaid["observables"] = build_live_manifest_overlay()
  300:     return overlaid
  301: 
  302: 
  303: __all__ = [
  304:     "LIVE_DONE_FORMULA",
  305:     "LIVE_EMBEDDING_MODE",
  306:     "LIVE_N_COGNITION_TICKS",
  307:     "LIVE_O5_MIN_TICKS",
  308:     "LIVE_OBSERVABLES",
  309:     "LIVE_PERSONA_ID",
  310:     "ThinkOffChatClient",
  311:     "attach_live_observables",
  312:     "build_live_env_pins",
  313:     "build_live_manifest_overlay",
  314:     "run_live_capture",
  315: ]

 succeeded in 359ms:
# FROZEN ADR — M13 forward primary = sealed live run (単一 live agent、候補 A)

> **status = FROZEN (2026-07-06、G-GEAR、user 裁定 ratify = AskUserQuestion「A で確定」)。doc-only。**
> process = Plan + /reimagine (v1 [3-way menu 演繹] 意図的破棄 → 独立 v2 [first-contact 必要条件 framing] 再生成
> → 独立収束確認 → hybrid [v2 spine + v1 graft]) + Codex independent review (gpt-5.5/xhigh、**Verdict=
> Adopt-with-changes、事実誤認 HIGH なし**、5 findings 全反映)。**本ファイルが Phase 1 fresh session の Read 対象**
> (Plan→Clear→Execute ハンドオフ)。**measurement 非再入 = holding 不可侵** (sealed live run は construction
> validation であって measurement verdict でない)。
> 中心の問い = 「hardening 済 substrate に対し、**最も情報量が高く最も後悔の小さい単一の次の行為**は何か」。
> v2 が中心命題「organ はまだ real engine と一度も接触していない」に到達 (requirement.md のみから独立再設計)。

## 3-way steelman 表 (v1 graft — decisions.md 明示用)

| 候補 | steelman | 裁定 |
|---|---|---|
| **A = sealed live run (単一 live agent)** | 未接触の organ を real qwen3:8b で一度封印実走 → captured real Plane2 → Ollama-free deterministic replay-verify。construction validation。arc 直接 payoff + N体化前 de-risk | **採用** (B/C の論理的前件、最小・holding 保全・VoI 最大) |
| **B = N体化 (multi live agents)** | 複数 live agent を substrate 上で。仮説のフル形に近い | **後置** (A の GO を前提にすべき。hardening ADR = B-1/B-3 確実発火 + slice 肥大 + measurement 誘惑増) |
| **C = measurement 再入 (costed gate)** | escalation ratchet (R-budget=arc-wide 1) 消費で floor/landscape 再測 | **却下 (holding 保全)** (live-validation 前に希少 R-budget 消費は VoI 最劣、estimand は live substrate 前提) |

**分岐の掛け合わせ**: measurement 再入? → **No** (C 却下、holding) × substrate live 安定? → **未検証**
(A 先、B/C は A の GO 前提) → **A に収束**。

## 中心命題 — 「organ はまだ real engine と一度も接触していない」

これまでに substrate に対して行われたのは 2 種類だけ:
- (a) **捏造 LLM** の determinism 配管 (golden の hand-built recorded calls = 架空の LLMPlan JSON を replay)。
- (b) **no-LLM** の frozen substrate (evidence/running、read-only)。

**一度も行われていない唯一のこと = live engine で鍵を回す** (real qwen3:8b → parse → LLMPlan → embodiment
resolver → MoveMsg → kinematics → trace の全経路が、本物のモデルを相手に閉じ、かつ再現するか)。

→ この観点では forward primary は「3 択から選ぶ」問題ではない。**first-contact live capture は B (N体化) と
C (measurement) の両方が構造的に前提とする必要条件**である。B は「単一 live agent が real LLM で substrate を
駆動する」状態を前提にし、C の measurement estimand は「live-validated substrate」があって初めて意味を持つ。
**メニューは畳まれる**: 未接触の organ の上で N体化 (B) も measurement (C) も論理的に先走り。**A は 3 択の 1 番
でなく、2 と 3 の論理的前件**。

**measurement 非再入 (holding)**: C は costed superseding ADR + escalation ratchet (R-budget = arc-wide 1) 経由
のみ。live-validation 前に希少 R-budget を焼くのは VoI 最劣 → **C 却下、holding 保全**。B は A の GO 後 → 後置。

**「前件」の限定 (Codex LOW-1 反映)**: A が B/C の論理的前件というのは **M13 forward の live-substrate estimand
に対して**の限定。no-LLM substrate の再測定 (C) 自体は論理的には live-validation なしでも可能 — ただし価値が
低く holding binding に反するゆえ却下、という構造。「A なしに C が論理的に不可能」ではない。

## 最小リアリティ表面 (minimal reality surface) の原理

「organ が real LLM と接触した」と言えるために **real でなければならない最小の表面は何か** から embedding を導く:
- real でなければ意味が閉じないのは **action LLM call** (認知の意思決定そのもの)。
- それ以外を real にするのは意味を強めず**非決定性を増やすだけ**。retrieval embedding を real Ollama
  (nomic-embed-text) にすると、(i) 追加の非決定源、(ii) embedding の cross-platform float drift、(iii) replay の
  ための embedding 記録拡張、を招く。
- → **embedding は golden の constant-vector mock を維持**。live なのは action LLM の決定のみ。retrieval は
  実 memory 蓄積 + 実 centroid 幾何で走り (履歴依存 channel は生きる)、類似度だけ mock。real embedding は
  「minimal reality surface の拡張」= superseding milestone。

## sealed live capture を「実験」として置く (reproducibility-discipline)

sealed live run は run 日付・env pin・1 コマンド再現を持つ **experiment** そのもの。ゆえ reproducibility-discipline
skill の規約 `experiments/<YYYYMMDD>-<exp-name>/` に置く (単なる tests/fixtures でなく):

```
experiments/20260707-ecl-v0-live-capture/   (日付は Phase 1 実走日)
  ├── run.sh                 # G-GEAR で live capture を 1 コマンド起動 (Ollama 必須)
  ├── repro.sh               # committed artifact から Ollama-free replay-verify (Mac/CI 再現)
  ├── env.md                 # Ollama version / qwen3:8b digest / VRAM / uv.lock hash / seed
  ├── ollama.log             # 実走ログ (forensic)
  └── artifacts/
       ├── manifest.json / decisions.jsonl / ecl_trace.jsonl / envelope_stream.jsonl  (captured)
```

CI が読む replay-verify test は **committed artifacts** を experiments/ から (または薄い copy を
tests/fixtures/ecl_v0_live/ に) 読み Ollama-free で検証。既存 synthetic golden (`tests/fixtures/ecl_v0_golden/`)
は **fast な CI determinism 単体 guard** として温存 — 用途が違う (捏造だが最小・高速の回帰 fixture vs 本物の
construction evidence)。両者を混同すると (a) 重い live fixture が CI hot path に載る or (b) 本物の live evidence
を失う。

## 実装アプローチ (v2)

1. **live capture driver (新規 script)**: `RecordReplayChatClient(inner=ThinkOffChatClient(OllamaChatClient(
   model="qwen3:8b")))` を record mode で `run_ecl_loop` に注入。captured `EclRunResult` の decisions/trace を
   `handoff.write_golden` 相当で experiments/artifacts へ serialize (6桁量子化)。既存 `loop.py`/`cycle.py`/
   `world` は無改変。
2. **`think=False` の適用経路を driver-local wrapper で閉じる (Codex HIGH-1 反映)**: `CognitionCycle` は
   `chat(..., sampling=sampling)` のみ呼び **`think` を渡さない** (`cycle.py:695`)。ゆえ
   `RecordReplayChatClient` は `think=None` を転送し、`OllamaChatClient` は `think is not None` の時だけ body に
   出す (`ollama_adapter.py:255`) → qwen3 default が `<think>` に budget を食い **空 content → parse 失敗**の穴。
   → **新規 `ThinkOffChatClient` (driver-local、`inner.chat(..., think=False)` を強制する薄い wrapper) を
   `RecordReplayChatClient(inner=...)` の内側に噛ませる**。cycle 無改変で think=False を注入。
   manifest/ollama.log に `think:false` を残し、**request capture test** (wrapper が think=False を渡すことを
   pin) を追加。([[reference_qwen3_ollama_gotchas]]: think=false 必須 + 言語ヒント必須)。
3. **env pin**: sampling (temperature/top_p/repeat_penalty)・persona・seed・n_cognition_ticks・qwen3:8b digest・
   Ollama version・VRAM・uv.lock hash を manifest/env.md に固定。
4. **長めの horizon**: golden の N=8 は最小回帰用。live capture は organ を意味ある長さで exercise する N
   (例 32) を **sealed 前に pre-register** (measurement でなく「longer horizon で安定完走するか」の construction 観測)。
5. **Ollama-free replay-verify**: committed decisions のみから replay → `ecl_trace_checksum` byte 一致 +
   `inner_invocations == 0`。既存 `scripts/ecl_v0_golden.py --verify` 構造を写経。
6. **cross-platform**: captured artifact は既存 canonical rules (6桁量子化) 適用済 → WSL Linux で byte 一致実測。

## 事前登録 (pre-registered observables、tune-to-pass 封鎖)

sealed run 前に固定 (Phase 1 で run)。**reproducibility Done (gate) と channel-exercise annotation (非 gate) を
分離** (Codex MEDIUM-1 反映):

**reproducibility Done gate (これだけが Done):**
- **O1 完走**: N cognition × M physics tick を live Ollama 相手に例外なく完走。
- **O2 再現**: captured decisions のみ replay → checksum byte 一致 + `inner_invocations==0`。
- **O3 cross-platform (Codex HIGH-2 反映で分割)**: 6桁量子化の射程は **float drift のみ**。raw
  `response.content` 等 non-float bytes は「固定入力の再利用」ゆえ一致する — cross-platform live **再 capture** の
  byte 一致は**要求しない** (live LLM 出力は cross-machine で非決定、再現不能)。ゆえ 2 分割:
  - **O3a**: 同一 committed `decisions.jsonl` から WSL Linux (glibc) / Windows (UCRT) で **replay checksum 一致 +
    inner_invocations==0**。
  - **O3b**: 同一 raw Plane2 を入力に **full artifact re-render SHA が cross-platform 一致** (6桁量子化が float
    drift を吸収)。

**Done** = **O1 ∧ O2 ∧ O3a ∧ O3b**。

**channel-exercise annotation (非 Done gate、construction 妥当性の記述):**
- **O4 非縮退 (純記述 boolean、measurement 禁止)**: 「LLM が N tick で distinct zone を >1 選んだか」「move
  target が >1 distinct か」の **boolean counting のみ**。**divergence/floor/landscape 統計を一切計算しない**
  (O4 が measurement へ drift する穴を定義レベルで封鎖)。**Done gate に入れない** — O4 false は失敗でなく
  construction follow-up。
- **O5 parsed-action path (Codex MEDIUM-2 反映)**: first-contact claim (real qwen3 → parse → LLMPlan →
  resolver → MoveMsg) が閉じたことを観測する。**pre-register 全 tick (or 最低 1 tick) で `llm_status=="ok"` ∧
  `plan is not None` ∧ MoveMsg が parsed `destination_zone` 由来**。unparseable-only でも O2 replay checksum は
  成立してしまう (`test_ecl_loop.py:436`) ゆえ、これが無いと「organ が real engine と接触」claim が空洞化する。
  **unparseable-only は Stop でなく construction branch** (think=False 経路 HIGH-1 と対で効く)。

**Stop** = replay 非決定 / crash → superseding hardening ADR (cross-platform 量子化と同型の determinism 漏れを疑う)。
**verdict** = **なし**。floor/landscape/verdict 非出力、measurement 非再入 guard 維持。

**Phase 1 branch (Codex MEDIUM-1: 「verdict 分岐」を改名、O4/O5 は annotation)**:
- ✅ **Done (O1∧O2∧O3a∧O3b)** + O5 parsed-action + O4 非縮退 → **GO (construction validated)** → 次 = B or C を別 ADR。
- ⚠️ replay 非決定/crash (O2/O3 fail) → **Stop → superseding hardening**。
- ⚠️ O5 unparseable-only / O4 縮退 (zone 無変化/無移動) → **construction 妥当性 branch** (think=False 経路 or
  policy grammar/persona 側、measurement 非再入)。reproducibility Done は満たしても organ が channel 未 exercise。

## 変更対象ファイル (Phase 1 想定)

- 新規: `experiments/<date>-ecl-v0-live-capture/{run.sh, repro.sh, env.md, artifacts/*}`。
- 新規: live capture driver script (experiments/ 配下 or `scripts/`)。
- 新規: `tests/` に Ollama-free replay-verify test (committed artifact 読取)。
- 既存 `loop.py`/`cycle.py`/`world/tick.py`/`handoff.py` は**無改変** (harness が既存 seam/serializer を駆動)。
- doc: ADR + `docs/research-positioning.md` §8 + `docs/experiment-tracking.md` 追記。

## 既存パターンとの整合性

- reproducibility-discipline: `experiments/<date>/` + run.sh/repro.sh + seed/lockfile pin。
- `scripts/ecl_v0_golden.py` の replay-verify + `handoff` serializer 再利用 (record mode の inner を差替えるだけ)。
- cross-platform 量子化 = 既存 `_q`/`canonical_dumps` (改修不要)。

## テスト戦略

- live capture の replay-verify (Ollama-free、CI)。cross-platform WSL byte 一致 (手動 gate)。
- measurement 非再入 guard (import/identifier、既存 pattern)。
- synthetic golden の既存 CI determinism test は無改変で温存。

## リスク

- real qwen3:8b の応答が parser 不通過頻度高 → α hardening の raised/unparseable fallback で堅牢 (対応済)。
  ただし全 tick unparseable だと O5 false = channel 未 exercise → think=False 経路 (HIGH-1) が最重要 mitigation。
- O4 縮退 → construction は valid だが channel 未 exercise → policy/persona branch (measurement でない)。
- experiments/ 配下 script が CI 対象外ゆえ lint/type から漏れる → replay-verify test 本体は tests/ に置き CI 網羅。

## Codex independent review 反映 (gpt-5.5/xhigh、Verdict=Adopt-with-changes、事実誤認 HIGH なし)

`codex-review.md` verbatim 保存 (tokens 151,802)。5 findings 全反映:
- **HIGH-1** think=False 経路が cycle 無 pass ゆえ閉じない → **driver-local `ThinkOffChatClient` wrapper** +
  think:false pin + request capture test (実装アプローチ 2)。**最重要** (放置で空 content→parse 全失敗)。
- **HIGH-2** O3 の cross-platform 根拠が 6桁量子化に寄りすぎ (raw content は非 float・固定入力再利用で一致) →
  **O3a (replay checksum cross-platform) / O3b (artifact re-render SHA) に分割**、live 再 capture の byte 一致は
  非要求。
- **MEDIUM-1** O4 が非 gate なのに GO 条件に見える → **reproducibility Done (O1∧O2∧O3a∧O3b) と channel-exercise
  annotation (O4/O5) を分離**、「verdict 分岐」→「Phase 1 branch」改名。
- **MEDIUM-2** first-contact の parse→LLMPlan 成功が観測量に無い → **O5 parsed-action path** 追加、unparseable-only
  は Stop でなく construction branch。
- **LOW-1** 「A は C の論理的前件」が強すぎ → **live-substrate estimand に限定**。

Fact-check confirmations: chat signature 一致 / golden embedding mock + replay-only / measurement 非再入 guard =
全て Codex が repo 実読で確認。

## 設計判断の履歴

- 初回案 (design-v1.md、3-way menu 演繹 + load-bearing channel 論 + tests/fixtures 配置) と再生成案
  (v2、first-contact 必要条件 framing + minimal reality surface + experiments/ 配置) を独立比較
  (`design-comparison.md`)。
- **両案が独立に A / embedding=mock / 単一 sealed run / verdict なし / Done=O1∧O2∧O3 に収束** = 方向頑健性の証拠。
- **採用 = hybrid (v2 spine + v1 graft)**: v2 の first-contact framing・minimal reality surface・experiments/ 配置・
  O4 measurement-drift 封鎖・qwen3 env pin を骨に、v1 の 3-way steelman 表 + verdict 分岐木を接ぐ。
- Codex Adopt-with-changes → HIGH2/MEDIUM2/LOW1 全反映。
- **採用 = 候補 A (sealed live run) を FROZEN** (user 裁定 ratify、AskUserQuestion「A で確定」、2026-07-06)。

---

## §FROZEN (user 裁定 ratify 済 = 2026-07-06)

**採用** = M13 forward primary = **候補 A (sealed live run、単一 live agent)**。B (N体化) は A の GO 後に別 ADR
で後置、C (measurement 再入) は holding 保全で却下 (R-budget=arc-wide 1 未消費)。HOW = record-mode live capture
(`ThinkOffChatClient` wrapper 経由 qwen3:8b) → captured real Plane2 → Ollama-free deterministic replay-verify、
embedding mock 維持、experiments/ 実験配置、事前登録 O1-O5 (Done=O1∧O2∧O3a∧O3b、O4/O5=channel annotation、
verdict なし)。reimagine v1/v2 独立収束 + hybrid + **Codex Verdict=Adopt-with-changes → HIGH2/MEDIUM2/LOW1
全反映後 freeze**。

- **FROZEN**: 2026-07-06、G-GEAR、user 裁定 (ratify、AskUserQuestion)。doc-only (実コード・sealed run なし)。
- **binding (変更は superseding ADR)**:
  (a) 候補選定 (A 採用 / B 後置 / C holding 却下)、
  (b) HOW の核 (record-mode live capture + Ollama-free replay-verify + embedding mock 維持 + experiments/ 配置)、
  (c) `think=False` を driver-local `ThinkOffChatClient` wrapper で注入 (cycle 無改変、Codex HIGH-1)、
  (d) 事前登録 O1-O5 と Done⇔annotation 分離 (Codex HIGH-2/MEDIUM-1/MEDIUM-2)、tune-to-pass 封鎖、
  (e) construction validation であって measurement verdict でない (floor/landscape/verdict 非出力、holding 不可侵)。
- **裁定後の実行許可**: `docs/research-positioning.md` §8 反映 (doc-only) + memory 更新 + doc-only PR
  (作業ブランチ→main、pre-push CI parity 4 段 pass 後)。
- **次工程 (別タスク、Phase 1) = Loop Engineering で sealed live run 実装**: grilling→issue-slicing skill 実起動
  → 想定縦スライス (I1 live-capture harness+ThinkOffChatClient / I2 sealed protocol+env pin / I3 sealed run+
  committed artifact / I4 Ollama-free replay-verify test+cross-platform O3a/O3b) → TASK-PRE Codex → subagent
  逐次/並列 dispatch → test-runner→loop-watchdog → 全 slice 緑+統合 CI 緑 → TASK-POST /cross-review → PR。
  next-session-prompt (`next-session-prompt-phase1.md`) 参照。**本 ADR は方向決定 + 技術契約 pre-register のみ
  (doc-only、実コード・sealed run は Phase 1)**。

## scope 境界 / 不可侵

- doc-only (新規実装・sealed run・apparatus 変更なし)。docs/research-positioning §8 反映 = doc-only PR。
- 凍結 ADR (ecl-v0-impl-design §7 / determinism-hardening / construction-scoping / arc-close 再検討 §3.4/§4 /
  arc-disposition / substrate-scoping / running-substrate / memseam / 中核命題 close / ES-4 disposition) 不可侵。
  逸脱は別 superseding ADR。
- 凍結 apparatus (`evidence/**`)・verdict-record・forensic.json read-only。measurement-line 再入は holding
  (costed superseding ADR + escalation ratchet R-budget=arc-wide 1 経由のみ、本 ADR で bypass しない)。
- cross-platform determinism (6桁量子化 + WSL byte 一致実測) / live Ollama 非必須依存 / 日本語 / main 直 push 禁止。
- Plan 承認 ≠ 技術契約確定 (user 裁定で確定)。設計再開は別 superseding ADR を要する。


 succeeded in 362ms:
    1: #!/usr/bin/env python
    2: """ECL v0 live-capture CLI 窶・Issue 001 apparatus (real run is Issue 003).
    3: 
    4: Thin CLI over :func:`erre_sandbox.integration.embodied.live.run_live_capture`:
    5: ``--capture`` builds a real
    6: :class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient` (the only live
    7: piece, D-4) plus a constant-vector mock embedding (D-4: real ``nomic-embed-text``
    8: is out of scope, minimal reality surface is the action-LLM chat call alone),
    9: drives one record-mode ECL v0 run through
   10: :func:`~erre_sandbox.integration.embodied.live.run_live_capture`, and writes the
   11: four handoff artifacts (``manifest.json`` with the live env-pin + observables
   12: overlay, ``ecl_trace.jsonl``, ``decisions.jsonl``, ``envelope_stream.jsonl``)
   13: into ``--out-dir`` (default ``experiments/20260706-ecl-v0-live-capture/artifacts``,
   14: D-8).
   15: 
   16: This module constructs the sealed-run inputs (persona/agent state = the golden
   17: Kant fixture, D-2) but does **not** perform the sealed run itself 窶・actually
   18: invoking ``--capture`` against a live Ollama, committing the resulting
   19: artifacts, and the cross-platform (WSL) byte-equality check are Issue 003.
   20: Import of this module has no side effects (no live connection opened at
   21: import time); a bare ``python scripts/ecl_v0_live_capture.py --capture`` is the
   22: only path that touches a live Ollama.
   23: 
   24: ``--verify`` (Issue 002, ``loop/20260706-ecl-v0-live-run/issues/002-replay-verify-apparatus.md``)
   25: is the companion **Ollama-free** replay-verify apparatus: it reproduces a
   26: committed artifact bundle's ``ecl_trace_checksum`` from ``decisions.jsonl``
   27: alone (:func:`verify`'s O3a step, ``inner_invocations == 0``) and re-renders
   28: the full artifact set from the same raw Plane 2 to check every per-artifact
   29: SHA-256 (O3b). Design-copied from ``scripts/ecl_v0_golden.py``'s ``verify``
   30: (D-7: copied, not imported, so that script stays untouched). Critically, the
   31: re-render step reuses the **committed manifest's** ``env_pins`` and ``run``
   32: block rather than a fresh :func:`~erre_sandbox.integration.embodied.handoff.build_manifest`
   33: capture (Codex TASK-PRE MEDIUM-2): a fresh capture snapshots the *current*
   34: machine's python/package versions and drifts the manifest bytes across
   35: runners, which is not what a reproduction check should assert.
   36: 
   37: Scope guard (design-final.md ﾂｧ隲也せ4, binding, mirrors ``scripts/ecl_v0_golden.py``
   38: / ``live.py``). This is a *construction* apparatus, **NOT a measurement line**.
   39: It imports no ``evidence`` / ``spdm`` / ``runningness`` machinery and
   40: computes/emits no floor / landscape / verdict statistic.
   41: """
   42: 
   43: from __future__ import annotations
   44: 
   45: import argparse
   46: import asyncio
   47: import hashlib
   48: import json
   49: import sys
   50: from datetime import UTC, datetime
   51: from pathlib import Path
   52: from typing import TYPE_CHECKING
   53: 
   54: import httpx
   55: 
   56: from erre_sandbox.integration.embodied import handoff
   57: from erre_sandbox.integration.embodied.live import (
   58:     LIVE_N_COGNITION_TICKS,
   59:     attach_live_observables,
   60:     build_live_env_pins,
   61:     run_live_capture,
   62: )
   63: from erre_sandbox.integration.embodied.loop import (
   64:     DEFAULT_PHYSICS_TICKS_PER_COGNITION,
   65:     RecordReplayChatClient,
   66:     run_ecl_loop,
   67: )
   68: from erre_sandbox.memory import EmbeddingClient, MemoryStore
   69: 
   70: if TYPE_CHECKING:
   71:     from collections.abc import Sequence
   72: 
   73:     from erre_sandbox.integration.embodied.loop import EclRunResult
   74: 
   75: _REPO_ROOT = Path(__file__).resolve().parent.parent
   76: _DEFAULT_OUT_DIR = (
   77:     _REPO_ROOT / "experiments" / "20260706-ecl-v0-live-capture" / "artifacts"
   78: )
   79: _DEFAULT_RUN_ID = "ecl-v0-live-capture"
   80: 
   81: 
   82: def _mock_embedding() -> EmbeddingClient:
   83:     """A constant-vector embedding 窶・deterministic and Ollama-free (D-4).
   84: 
   85:     Independent of ``scripts.ecl_v0_golden._offline_embedding`` (D-7: the two
   86:     scripts stay decoupled) but structurally identical: only the action-LLM
   87:     chat call is live in a live-capture run.
   88:     """
   89:     vec = [0.01] * EmbeddingClient.DEFAULT_DIM
   90: 
   91:     def handler(request: httpx.Request) -> httpx.Response:
   92:         body = json.loads(request.content)
   93:         inputs = body.get("input") or []
   94:         count = len(inputs) if isinstance(inputs, list) else 1
   95:         return httpx.Response(httpx.codes.OK, json={"embeddings": [vec] * count})
   96: 
   97:     return EmbeddingClient(
   98:         client=httpx.AsyncClient(
   99:             base_url=EmbeddingClient.DEFAULT_ENDPOINT,
  100:             transport=httpx.MockTransport(handler),
  101:         )
  102:     )
  103: 
  104: 
  105: async def capture(
  106:     *,
  107:     run_id: str,
  108:     seed: int,
  109:     n_cognition_ticks: int,
  110:     physics_ticks_per_cognition: int,
  111:     qwen3_model_digest: str,
  112:     ollama_version: str,
  113:     vram_gb: float,
  114:     uv_lock_sha256: str,
  115: ) -> tuple[EclRunResult, dict[str, str]]:
  116:     """Drive one live-capture run and render the four handoff artifacts.
  117: 
  118:     Builds a real ``OllamaChatClient`` (the sole live piece) and a mock
  119:     embedding (D-4), runs :func:`run_live_capture`, then renders the artifacts
  120:     via ``handoff``'s existing serialisers plus the live env-pin +
  121:     observables overlay this module owns. Does not write anything to disk 窶・    the caller (``main``) does that, so this function is unit-testable without
  122:     touching a filesystem.
  123:     """
  124:     # Imported lazily so a plain ``import`` of this module (e.g. from tests)
  125:     # never requires ``httpx``-level Ollama reachability.
  126:     from erre_sandbox.inference.ollama_adapter import OllamaChatClient
  127: 
  128:     now = datetime.now(UTC)
  129:     inner = OllamaChatClient()
  130:     embedding = _mock_embedding()
  131:     store = MemoryStore(db_path=":memory:")
  132:     store.create_schema()
  133:     try:
  134:         result = await run_live_capture(
  135:             inner_chat=inner,
  136:             store=store,
  137:             embedding=embedding,
  138:             run_id=run_id,
  139:             agent_state=handoff.golden_agent_state(),
  140:             persona=handoff.golden_persona(),
  141:             retrieval_now=now,
  142:             base_ts=now,
  143:             seed=seed,
  144:             n_cognition_ticks=n_cognition_ticks,
  145:             physics_ticks_per_cognition=physics_ticks_per_cognition,
  146:         )
  147:     finally:
  148:         await inner.close()
  149:         await embedding.close()
  150:         await store.close()
  151: 
  152:     resolved_sampling = result.decisions[0].call.sampling
  153:     env_pins = build_live_env_pins(
  154:         qwen3_model_digest=qwen3_model_digest,
  155:         ollama_version=ollama_version,
  156:         vram_gb=vram_gb,
  157:         uv_lock_sha256=uv_lock_sha256,
  158:         resolved_sampling=resolved_sampling,
  159:     )
  160:     run_config = {
  161:         "seed": seed,
  162:         "physics_ticks_per_cognition": physics_ticks_per_cognition,
  163:         "k_ecl": handoff.K_ECL,
  164:         "base_ts": now.isoformat(),
  165:         "retrieval_now": now.isoformat(),
  166:     }
  167:     rendered = handoff.render_golden(result, run_config=run_config, env_pins=env_pins)
  168:     manifest = json.loads(rendered["manifest.json"])
  169:     rendered["manifest.json"] = handoff.canonical_dumps(attach_live_observables(manifest)) + "\n"
  170:     return result, rendered
  171: 
  172: 
  173: def _write(out_dir: Path, rendered: dict[str, str]) -> None:
  174:     out_dir.mkdir(parents=True, exist_ok=True)
  175:     for filename, text in rendered.items():
  176:         (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")
  177: 
  178: 
  179: async def verify(artifact_dir: Path) -> bool:
  180:     """Ollama-free replay-verify of a committed live-capture artifact bundle.
  181: 
  182:     Issue 002 apparatus (design-copied from ``scripts/ecl_v0_golden.py``'s
  183:     ``verify``, D-7 窶・copied, not imported, so that script stays untouched):
  184: 
  185:     1. **O3a** 窶・replay from the committed ``decisions.jsonl`` *alone*
  186:        (``inner_invocations == 0``) reproduces the committed manifest's
  187:        ``replay_checksum`` byte-for-byte.
  188:     2. **O3b** 窶・re-rendering the full artifact set from the same replayed
  189:        result reproduces every per-artifact SHA-256. The re-render reuses the
  190:        **committed manifest's** ``env_pins``/``run`` block (Codex TASK-PRE
  191:        MEDIUM-2), never a fresh ``handoff.build_manifest(env_pins=None)``
  192:        capture (which would snapshot the *current* machine and drift the
  193:        manifest bytes across runners).
  194: 
  195:     Ollama-free: the LLM is the recorded Plane 2 (replay only) and the
  196:     embedding is the constant-vector mock, exactly as ``capture`` uses when
  197:     building the live artifact in the first place. This function computes no
  198:     floor / landscape / verdict / divergence statistic (measurement-line
  199:     non-re-entry, design ﾂｧ隲也せ4) 窶・it is a byte-equality reproduction check.
  200:     """
  201:     manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
  202:     decisions_text = (artifact_dir / "decisions.jsonl").read_text(encoding="utf-8")
  203:     trace_text = (artifact_dir / "ecl_trace.jsonl").read_text(encoding="utf-8")
  204:     envelope_text = (artifact_dir / "envelope_stream.jsonl").read_text(encoding="utf-8")
  205:     run_config = manifest["run"]
  206: 
  207:     ok = True
  208:     recorded = handoff.recorded_calls_from_jsonl(decisions_text)
  209: 
  210:     store = MemoryStore(db_path=":memory:")
  211:     store.create_schema()
  212:     embedding = _mock_embedding()
  213:     llm = RecordReplayChatClient(recorded=recorded)
  214:     try:
  215:         result = await run_ecl_loop(
  216:             run_id=run_config["run_id"],
  217:             store=store,
  218:             embedding=embedding,
  219:             llm=llm,
  220:             agent_state=handoff.golden_agent_state(),
  221:             persona=handoff.golden_persona(),
  222:             retrieval_now=datetime.fromisoformat(run_config["retrieval_now"]),
  223:             base_ts=datetime.fromisoformat(run_config["base_ts"]),
  224:             seed=run_config["seed"],
  225:             n_cognition_ticks=run_config["cognition_ticks"],
  226:             physics_ticks_per_cognition=run_config["physics_ticks_per_cognition"],
  227:             k_ecl=run_config["k_ecl"],
  228:         )
  229:     finally:
  230:         await embedding.close()
  231:         await store.close()
  232: 
  233:     # O3a 窶・inner_invocations == 0 + replay checksum byte-match.
  234:     if llm.inner_invocations != 0:
  235:         ok = False
  236:         print(f"[verify] FAIL replay touched a live LLM ({llm.inner_invocations} calls)")
  237:     if result.checksum != manifest["replay_checksum"]:
  238:         ok = False
  239:         print(
  240:             f"[verify] FAIL replay checksum {result.checksum} != "
  241:             f"manifest {manifest['replay_checksum']}"
  242:         )
  243:     else:
  244:         print(f"[verify] OK replay checksum {result.checksum}")
  245: 
  246:     # O3b 窶・re-render (committed env_pins/run reused) 竊・per-artifact SHA-256.
  247:     rendered = handoff.render_golden(
  248:         result, run_config=run_config, env_pins=manifest["env_pins"]
  249:     )
  250:     artifacts = {
  251:         "ecl_trace.jsonl": trace_text,
  252:         "decisions.jsonl": decisions_text,
  253:         "envelope_stream.jsonl": envelope_text,
  254:     }
  255:     for name, committed_text in artifacts.items():
  256:         expected = manifest["artifacts"][name]["sha256"]
  257:         actual = hashlib.sha256(rendered[name].encode("utf-8")).hexdigest()
  258:         if actual != expected:
  259:             ok = False
  260:             print(f"[verify] FAIL {name} sha256 {actual} != {expected}")
  261:         elif rendered[name] != committed_text:  # pragma: no cover - defensive
  262:             ok = False
  263:             print(f"[verify] FAIL {name} byte mismatch despite matching sha256")
  264: 
  265:     envelopes = handoff.validate_envelope_stream(envelope_text)
  266:     print(f"[verify] OK {len(envelopes)} envelopes schema-conformant")
  267: 
  268:     print("[verify] LIVE ARTIFACT OK" if ok else "[verify] LIVE ARTIFACT MISMATCH")
  269:     return ok
  270: 
  271: 
  272: def main(argv: Sequence[str] | None = None) -> int:
  273:     parser = argparse.ArgumentParser(description="ECL v0 live-capture (Issue 001/002 apparatus)")
  274:     group = parser.add_mutually_exclusive_group(required=True)
  275:     group.add_argument(
  276:         "--capture",
  277:         action="store_true",
  278:         help="drive one record-mode run against a live Ollama and write artifacts",
  279:     )
  280:     group.add_argument(
  281:         "--verify",
  282:         action="store_true",
  283:         help="Ollama-free replay-verify a committed artifact bundle (Issue 002)",
  284:     )
  285:     parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
  286:     parser.add_argument(
  287:         "--artifact-dir",
  288:         type=Path,
  289:         default=_DEFAULT_OUT_DIR,
  290:         help="artifact bundle to replay-verify (--verify only)",
  291:     )
  292:     parser.add_argument("--run-id", default=_DEFAULT_RUN_ID)
  293:     parser.add_argument("--seed", type=int, default=0)
  294:     parser.add_argument("--n-cognition-ticks", type=int, default=LIVE_N_COGNITION_TICKS)
  295:     parser.add_argument(
  296:         "--physics-ticks-per-cognition",
  297:         type=int,
  298:         default=DEFAULT_PHYSICS_TICKS_PER_COGNITION,
  299:     )
  300:     parser.add_argument("--qwen3-model-digest", default="unknown")
  301:     parser.add_argument("--ollama-version", default="unknown")
  302:     parser.add_argument("--vram-gb", type=float, default=0.0)
  303:     parser.add_argument("--uv-lock-sha256", default="unknown")
  304:     args = parser.parse_args(argv)
  305: 
  306:     if args.verify:
  307:         ok = asyncio.run(verify(args.artifact_dir))
  308:         return 0 if ok else 1
  309: 
  310:     result, rendered = asyncio.run(
  311:         capture(
  312:             run_id=args.run_id,
  313:             seed=args.seed,
  314:             n_cognition_ticks=args.n_cognition_ticks,
  315:             physics_ticks_per_cognition=args.physics_ticks_per_cognition,
  316:             qwen3_model_digest=args.qwen3_model_digest,
  317:             ollama_version=args.ollama_version,
  318:             vram_gb=args.vram_gb,
  319:             uv_lock_sha256=args.uv_lock_sha256,
  320:         )
  321:     )
  322:     _write(args.out_dir, rendered)
  323:     print(f"[capture] wrote {len(rendered)} artifacts to {args.out_dir}")
  324:     print(f"[capture] replay_checksum = {result.checksum}")
  325:     return 0
  326: 
  327: 
  328: if __name__ == "__main__":
  329:     sys.exit(main())

codex
binding 上の大枠は、既存 seam 無改変・measurement 非再入・O4/O5 annotation 分離が中心です。ここから tests と committed artifact の使い方を照合します。
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "git diff --name-status main..feat/ecl-v0-live-run -- src\\erre_sandbox\\integration\\embodied\\loop.py src\\erre_sandbox\\cognition\\cycle.py src\\erre_sandbox\\world\\tick.py src\\erre_sandbox\\integration\\embodied\\handoff.py scripts\\ecl_v0_golden.py" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-ChildItem -Recurse experiments\\20260706-ecl-v0-live-capture | Select-Object FullName,Length" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content tests'"\\test_integration\\test_ecl_live_golden.py | ForEach-Object { "'$i++; '"'{0,5}: {1}' -f "'$i, $_ }' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content tests'"\\test_integration\\test_ecl_live_capture.py | ForEach-Object { "'$i++; '"'{0,5}: {1}' -f "'$i, $_ }' in C:\ERRE-Sand_Box
 succeeded in 289ms:
 succeeded in 346ms:
    1: """ECL v0 live-capture apparatus tests (M13, Issue 001).
    2: 
    3: The apparatus (``integration/embodied/live.py``) is Ollama-free and testable
    4: end-to-end with a mock inner chat client 窶・the actual live Ollama capture is
    5: Issue 003. These tests pin:
    6: 
    7: * **I1-G1/I1-G2** :class:`~erre_sandbox.integration.embodied.live.ThinkOffChatClient`
    8:   forces ``think=False`` and forwards everything else unchanged.
    9: * **I1-G3/I1-G4** :func:`~erre_sandbox.integration.embodied.live.run_live_capture`
   10:   records with a mock inner and replays byte-identically from the captured
   11:   decisions alone (``inner_invocations == 0``).
   12: * **I2-G1** pre-registered protocol constants (D-1/D-2/D-4/D-5).
   13: * **I2-G2** the live env-pin helper populates the manifest with qwen3
   14:   digest / Ollama version / VRAM / uv.lock hash / ``think:false`` / resolved
   15:   sampling.
   16: * **I2-G3** the manifest observables overlay pre-registers O1-O5 +
   17:   ``done_formula`` + ``o5_min_ticks`` as sealed-run-before constants.
   18: * **I2-G4** measurement-line non-re-entry (import / output-identifier guard,
   19:   mirrors the existing ``loop.py`` / ``handoff.py`` guards).
   20: """
   21: 
   22: from __future__ import annotations
   23: 
   24: import ast
   25: import json
   26: from dataclasses import dataclass, field
   27: from datetime import UTC, datetime
   28: from pathlib import Path
   29: from typing import TYPE_CHECKING, Any
   30: 
   31: import httpx
   32: 
   33: from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse
   34: from erre_sandbox.inference.sampling import ResolvedSampling
   35: from erre_sandbox.integration.embodied import handoff
   36: from erre_sandbox.integration.embodied import live as ecl_live
   37: from erre_sandbox.integration.embodied.live import (
   38:     LIVE_DONE_FORMULA,
   39:     LIVE_EMBEDDING_MODE,
   40:     LIVE_N_COGNITION_TICKS,
   41:     LIVE_O5_MIN_TICKS,
   42:     LIVE_PERSONA_ID,
   43:     ThinkOffChatClient,
   44:     attach_live_observables,
   45:     build_live_env_pins,
   46:     run_live_capture,
   47: )
   48: from erre_sandbox.integration.embodied.loop import (
   49:     replay_client_from,
   50:     run_ecl_loop,
   51: )
   52: from erre_sandbox.memory import EmbeddingClient, MemoryStore
   53: 
   54: if TYPE_CHECKING:
   55:     from collections.abc import Callable, Sequence
   56: 
   57:     from erre_sandbox.schemas import AgentState, PersonaSpec
   58: 
   59: _FIXED = datetime(2026, 1, 1, tzinfo=UTC)
   60: _PLAN_JSON = json.dumps(
   61:     {
   62:         "thought": "walk the peripatos",
   63:         "utterance": "謨｣豁ｩ縺ｸ",
   64:         "destination_zone": "peripatos",
   65:         "animation": "walk",
   66:     }
   67: )
   68: _SAMPLING = ResolvedSampling(temperature=0.7, top_p=0.9, repeat_penalty=1.1)
   69: 
   70: 
   71: def _embed_client() -> EmbeddingClient:
   72:     def handler(request: httpx.Request) -> httpx.Response:
   73:         body = json.loads(request.content)
   74:         inputs = body.get("input") or []
   75:         count = len(inputs) if isinstance(inputs, list) else 1
   76:         vec = [0.01] * EmbeddingClient.DEFAULT_DIM
   77:         return httpx.Response(httpx.codes.OK, json={"embeddings": [vec] * count})
   78: 
   79:     return EmbeddingClient(
   80:         client=httpx.AsyncClient(
   81:             base_url=EmbeddingClient.DEFAULT_ENDPOINT,
   82:             transport=httpx.MockTransport(handler),
   83:         )
   84:     )
   85: 
   86: 
   87: @dataclass
   88: class _RequestCapturingInner:
   89:     """Mock inner chat client that records the exact kwargs it was called with."""
   90: 
   91:     content: str = _PLAN_JSON
   92:     calls: list[dict[str, Any]] = field(default_factory=list)
   93: 
   94:     async def chat(
   95:         self,
   96:         messages: Sequence[ChatMessage],
   97:         *,
   98:         sampling: ResolvedSampling,
   99:         model: str | None = None,
  100:         options: dict[str, Any] | None = None,
  101:         think: bool | None = None,
  102:     ) -> ChatResponse:
  103:         self.calls.append(
  104:             {
  105:                 "messages": messages,
  106:                 "sampling": sampling,
  107:                 "model": model,
  108:                 "options": options,
  109:                 "think": think,
  110:             }
  111:         )
  112:         return ChatResponse(
  113:             content=self.content,
  114:             model="qwen3:8b",
  115:             eval_count=1,
  116:             total_duration_ms=0.0,
  117:         )
  118: 
  119: 
  120: # --------------------------------------------------------------------------- #
  121: # I1-G1 窶・ThinkOffChatClient forces think=False
  122: # --------------------------------------------------------------------------- #
  123: 
  124: 
  125: async def test_think_off_chat_client_forces_think_false() -> None:
  126:     inner = _RequestCapturingInner()
  127:     client = ThinkOffChatClient(inner)
  128:     messages = [ChatMessage(role="user", content="hello")]
  129: 
  130:     await client.chat(messages, sampling=_SAMPLING, think=None)
  131:     await client.chat(messages, sampling=_SAMPLING, think=True)
  132: 
  133:     assert len(inner.calls) == 2
  134:     assert inner.calls[0]["think"] is False
  135:     assert inner.calls[1]["think"] is False
  136: 
  137: 
  138: # --------------------------------------------------------------------------- #
  139: # I1-G2 窶・passthrough of everything else + ChatResponse passthrough
  140: # --------------------------------------------------------------------------- #
  141: 
  142: 
  143: async def test_think_off_chat_client_passthrough() -> None:
  144:     inner = _RequestCapturingInner(content="verbatim response")
  145:     client = ThinkOffChatClient(inner)
  146:     messages = [
  147:         ChatMessage(role="system", content="sys"),
  148:         ChatMessage(role="user", content="usr"),
  149:     ]
  150:     options = {"num_predict": 128}
  151: 
  152:     response = await client.chat(
  153:         messages, sampling=_SAMPLING, model="qwen3:8b", options=options, think=None
  154:     )
  155: 
  156:     call = inner.calls[0]
  157:     assert call["messages"] is messages
  158:     assert call["sampling"] is _SAMPLING
  159:     assert call["model"] == "qwen3:8b"
  160:     assert call["options"] is options
  161:     assert response.content == "verbatim response"
  162:     assert response.model == "qwen3:8b"
  163: 
  164: 
  165: # --------------------------------------------------------------------------- #
  166: # I1-G3 窶・harness records with a mock inner (live-independent)
  167: # --------------------------------------------------------------------------- #
  168: 
  169: 
  170: async def _capture(
  171:     make_agent_state: Callable[..., AgentState],
  172:     make_persona_spec: Callable[..., PersonaSpec],
  173:     *,
  174:     inner: Any | None = None,
  175:     n_cognition_ticks: int = 4,
  176: ) -> Any:
  177:     inner = inner or _RequestCapturingInner()
  178:     store = MemoryStore(db_path=":memory:")
  179:     store.create_schema()
  180:     embedding = _embed_client()
  181:     try:
  182:         return await run_live_capture(
  183:             inner_chat=inner,
  184:             store=store,
  185:             embedding=embedding,
  186:             run_id="r-live",
  187:             agent_state=make_agent_state(),
  188:             persona=make_persona_spec(),
  189:             retrieval_now=_FIXED,
  190:             base_ts=_FIXED,
  191:             n_cognition_ticks=n_cognition_ticks,
  192:         )
  193:     finally:
  194:         await embedding.close()
  195:         await store.close()
  196: 
  197: 
  198: async def test_live_capture_harness_records_with_mock_inner(
  199:     make_agent_state: Callable[..., AgentState],
  200:     make_persona_spec: Callable[..., PersonaSpec],
  201: ) -> None:
  202:     inner = _RequestCapturingInner()
  203:     result = await _capture(make_agent_state, make_persona_spec, inner=inner)
  204: 
  205:     assert result.rows, "live capture produced no trace rows"
  206:     assert len(result.decisions) == 4
  207:     for decision in result.decisions:
  208:         assert decision.plan is not None
  209:         assert decision.llm_status == "ok"
  210:         assert decision.call.raw_response == _PLAN_JSON
  211:     assert result.checksum
  212:     # The mock inner actually saw every action-LLM call, each forced think=False
  213:     # by the ThinkOffChatClient the harness wraps it in.
  214:     assert len(inner.calls) == 4
  215:     assert all(call["think"] is False for call in inner.calls)
  216: 
  217: 
  218: # --------------------------------------------------------------------------- #
  219: # I1-G4 窶・replay-from-decisions roundtrip (byte-identical, no live LLM)
  220: # --------------------------------------------------------------------------- #
  221: 
  222: 
  223: async def test_live_capture_replay_roundtrip_mock(
  224:     make_agent_state: Callable[..., AgentState],
  225:     make_persona_spec: Callable[..., PersonaSpec],
  226: ) -> None:
  227:     recorded = await _capture(make_agent_state, make_persona_spec)
  228: 
  229:     replay_llm = replay_client_from(recorded)
  230:     store = MemoryStore(db_path=":memory:")
  231:     store.create_schema()
  232:     embedding = _embed_client()
  233:     try:
  234:         replayed = await run_ecl_loop(
  235:             run_id="r-live",
  236:             store=store,
  237:             embedding=embedding,
  238:             llm=replay_llm,
  239:             agent_state=make_agent_state(),
  240:             persona=make_persona_spec(),
  241:             retrieval_now=_FIXED,
  242:             base_ts=_FIXED,
  243:             n_cognition_ticks=4,
  244:         )
  245:     finally:
  246:         await embedding.close()
  247:         await store.close()
  248: 
  249:     assert replay_llm.inner_invocations == 0
  250:     assert replayed.checksum == recorded.checksum
  251: 
  252: 
  253: # --------------------------------------------------------------------------- #
  254: # I2-G1 窶・pre-registered protocol constants
  255: # --------------------------------------------------------------------------- #
  256: 
  257: 
  258: def test_live_capture_protocol_constants() -> None:
  259:     assert LIVE_N_COGNITION_TICKS == 32
  260:     assert LIVE_PERSONA_ID == "kant"
  261:     assert LIVE_EMBEDDING_MODE == "mock"
  262:     assert LIVE_O5_MIN_TICKS == 1
  263:     assert LIVE_DONE_FORMULA == "O1竏ｧO2竏ｧO3a竏ｧO3b"
  264: 
  265: 
  266: # --------------------------------------------------------------------------- #
  267: # I2-G2 窶・manifest env pins (qwen3 digest / Ollama version / VRAM / uv.lock /
  268: # think:false / resolved sampling)
  269: # --------------------------------------------------------------------------- #
  270: 
  271: 
  272: async def test_live_manifest_pins_env(
  273:     make_agent_state: Callable[..., AgentState],
  274:     make_persona_spec: Callable[..., PersonaSpec],
  275: ) -> None:
  276:     result = await _capture(make_agent_state, make_persona_spec)
  277:     resolved_sampling = result.decisions[0].call.sampling
  278: 
  279:     env_pins = build_live_env_pins(
  280:         qwen3_model_digest="sha256:deadbeef",
  281:         ollama_version="0.5.1",
  282:         vram_gb=16.0,
  283:         uv_lock_sha256="abc123",
  284:         resolved_sampling=resolved_sampling,
  285:         base_env_pins={"python": "3.11.9", "packages": {}, "godot": "4.6"},
  286:     )
  287:     trace_jsonl = handoff.trace_rows_to_jsonl(result.rows)
  288:     decisions_jsonl = handoff.decisions_to_jsonl(result.decisions)
  289:     envelope_jsonl = handoff.envelope_stream_to_jsonl(
  290:         handoff.build_envelope_stream(result)
  291:     )
  292:     manifest = handoff.build_manifest(
  293:         result,
  294:         run_config=handoff.golden_run_config(),
  295:         trace_jsonl=trace_jsonl,
  296:         decisions_jsonl=decisions_jsonl,
  297:         envelope_jsonl=envelope_jsonl,
  298:         env_pins=env_pins,
  299:     )
  300: 
  301:     pins = manifest["env_pins"]
  302:     assert pins["qwen3_model_digest"] == "sha256:deadbeef"
  303:     assert pins["ollama_version"] == "0.5.1"
  304:     assert pins["vram_gb"] == 16.0
  305:     assert pins["uv_lock_sha256"] == "abc123"
  306:     assert pins["think"] is False
  307:     pinned_sampling = pins["resolved_sampling"]
  308:     assert pinned_sampling["temperature"] == resolved_sampling.temperature
  309:     assert pinned_sampling["top_p"] == resolved_sampling.top_p
  310:     assert pinned_sampling["repeat_penalty"] == resolved_sampling.repeat_penalty
  311: 
  312: 
  313: # --------------------------------------------------------------------------- #
  314: # I2-G3 窶・manifest observables overlay pre-registers O1-O5 (tune-to-pass closed)
  315: # --------------------------------------------------------------------------- #
  316: 
  317: 
  318: async def test_live_manifest_observables_preregistered(
  319:     make_agent_state: Callable[..., AgentState],
  320:     make_persona_spec: Callable[..., PersonaSpec],
  321: ) -> None:
  322:     result = await _capture(make_agent_state, make_persona_spec)
  323:     trace_jsonl = handoff.trace_rows_to_jsonl(result.rows)
  324:     decisions_jsonl = handoff.decisions_to_jsonl(result.decisions)
  325:     envelope_jsonl = handoff.envelope_stream_to_jsonl(
  326:         handoff.build_envelope_stream(result)
  327:     )
  328:     manifest = handoff.build_manifest(
  329:         result,
  330:         run_config=handoff.golden_run_config(),
  331:         trace_jsonl=trace_jsonl,
  332:         decisions_jsonl=decisions_jsonl,
  333:         envelope_jsonl=envelope_jsonl,
  334:     )
  335: 
  336:     overlaid = attach_live_observables(manifest)
  337: 
  338:     observables = overlaid["observables"]
  339:     for key in ("O1", "O2", "O3a", "O3b", "O4", "O5"):
  340:         assert key in observables
  341:         assert isinstance(observables[key], str)
  342:         assert observables[key]
  343:     assert observables["done_formula"] == "O1竏ｧO2竏ｧO3a竏ｧO3b"
  344:     assert observables["o5_min_ticks"] == 1
  345:     # Non-mutating: the original manifest dict is untouched.
  346:     assert "observables" not in manifest
  347: 
  348: 
  349: # --------------------------------------------------------------------------- #
  350: # I2-G4 窶・measurement-line non-re-entry (import / output guard)
  351: # --------------------------------------------------------------------------- #
  352: 
  353: 
  354: _LIVE_TREE = ast.parse(Path(ecl_live.__file__).read_text(encoding="utf-8"))
  355: 
  356: 
  357: def _assert_no_measurement_imports(tree: ast.Module) -> None:
  358:     banned_prefix = ("erre_sandbox.evidence",)
  359:     banned_sub = ("spdm", "runningness")
  360:     for node in ast.walk(tree):
  361:         if isinstance(node, ast.ImportFrom) and node.module is not None:
  362:             assert not node.module.startswith(banned_prefix), node.module
  363:             assert not any(s in node.module for s in banned_sub), node.module
  364:         if isinstance(node, ast.Import):
  365:             for alias in node.names:
  366:                 assert not alias.name.startswith(banned_prefix), alias.name
  367:                 assert not any(s in alias.name for s in banned_sub), alias.name
  368: 
  369: 
  370: def _stored_names(node: ast.AST) -> list[str]:
  371:     if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
  372:         return [node.id]
  373:     if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
  374:         return [node.target.id]
  375:     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
  376:         return [node.name]
  377:     if isinstance(node, ast.arg):
  378:         return [node.arg]
  379:     return []
  380: 
  381: 
  382: def _assert_no_measurement_output_identifiers(tree: ast.Module) -> None:
  383:     banned_ident = ("floor", "landscape", "verdict", "jaccard", "divergence", "r_min")
  384:     for node in ast.walk(tree):
  385:         for name in _stored_names(node):
  386:             low = name.lower()
  387:             assert not any(tok in low for tok in banned_ident), name
  388: 
  389: 
  390: def test_live_capture_measurement_guard() -> None:
  391:     """``live.py`` imports no measurement machinery and defines no floor /
  392:     landscape / verdict output identifier (design ﾂｧ隲也せ4, mirrors the
  393:     ``loop.py`` / ``handoff.py`` guards)."""
  394:     _assert_no_measurement_imports(_LIVE_TREE)
  395:     _assert_no_measurement_output_identifiers(_LIVE_TREE)

 succeeded in 376ms:

FullName                                                                                  Length
--------                                                                                  ------
C:\ERRE-Sand_Box\experiments\20260706-ecl-v0-live-capture\artifacts                             
C:\ERRE-Sand_Box\experiments\20260706-ecl-v0-live-capture\env.md                          3209  
C:\ERRE-Sand_Box\experiments\20260706-ecl-v0-live-capture\ollama.log                      266   
C:\ERRE-Sand_Box\experiments\20260706-ecl-v0-live-capture\repro.sh                        1843  
C:\ERRE-Sand_Box\experiments\20260706-ecl-v0-live-capture\run.sh                          556   
C:\ERRE-Sand_Box\experiments\20260706-ecl-v0-live-capture\artifacts\decisions.jsonl       224143
C:\ERRE-Sand_Box\experiments\20260706-ecl-v0-live-capture\artifacts\ecl_trace.jsonl       370969
C:\ERRE-Sand_Box\experiments\20260706-ecl-v0-live-capture\artifacts\envelope_stream.jsonl 24271 
C:\ERRE-Sand_Box\experiments\20260706-ecl-v0-live-capture\artifacts\manifest.json         4770  



 succeeded in 391ms:
    1: """ECL v0 Ollama-free live-capture replay-verify apparatus 窶・Issue 002
    2: (``loop/20260706-ecl-v0-live-run/issues/002-replay-verify-apparatus.md``,
    3: ``.steering/20260706-ecl-v0-live-run/decisions.md`` D-5/D-6/D-8).
    4: 
    5: Builds the apparatus that replay-verifies a *committed* ECL v0 embodiment
    6: artifact **without Ollama**: replaying the recorded Plane 2
    7: (``decisions.jsonl``) reproduces the committed ``manifest.json``'s
    8: ``ecl_trace_checksum`` byte-for-byte (O3a), and re-rendering the full
    9: artifact set from the same replayed result reproduces every per-artifact
   10: SHA-256 (O3b). O5 (D-5 refinement) is an **annotation** count, never a hard
   11: green gate (Codex TASK-PRE HIGH-2 窶・an autonomous O5 gate would tune-to-pass
   12: the loop toward it).
   13: 
   14: Issue 003's committed live artifact (``experiments/20260706-ecl-v0-live-capture/
   15: artifacts/``) does not exist yet, so this module runs against the existing
   16: synthetic golden (``tests/fixtures/ecl_v0_golden/``) as a template 窶・the
   17: fixture path is the single module constant :data:`_GOLDEN_DIR`; Issue 004
   18: swaps it to the live artifact directory in one line, and every test below is
   19: written against the *committed manifest's* run config (never module-level
   20: golden constants) so it generalises unchanged to a run with a different tick
   21: count / seed / clock (D-1: the live run is 32 ticks, not the golden's 8).
   22: 
   23: Scope guard (design-final.md ﾂｧ隲也せ4, binding, mirrors ``test_ecl_handoff.py``).
   24: This is a *construction* apparatus, **NOT a measurement line**. It imports no
   25: ``evidence`` / ``spdm`` / ``runningness`` machinery and computes/emits no
   26: floor / landscape / verdict / divergence statistic 窶・:func:`test_live_golden_measurement_guard` pins this by AST-scanning both this
   27: module and ``scripts/ecl_v0_live_capture.py``'s ``--verify`` apparatus.
   28: """
   29: 
   30: from __future__ import annotations
   31: 
   32: import ast
   33: import hashlib
   34: import json
   35: from datetime import datetime
   36: from pathlib import Path
   37: from typing import TYPE_CHECKING
   38: 
   39: import httpx
   40: 
   41: from erre_sandbox.integration.embodied import handoff
   42: from erre_sandbox.integration.embodied.live import LIVE_O5_MIN_TICKS
   43: from erre_sandbox.integration.embodied.loop import RecordReplayChatClient, run_ecl_loop
   44: from erre_sandbox.memory import EmbeddingClient, MemoryStore
   45: 
   46: if TYPE_CHECKING:
   47:     from collections.abc import Sequence
   48: 
   49:     from erre_sandbox.integration.embodied.loop import EclRunResult, RecordedLlmCall
   50: 
   51: # The single fixture-path switch (Issue 004 repoints this at
   52: # ``experiments/20260706-ecl-v0-live-capture/artifacts`` once the sealed live
   53: # run is committed).
   54: _GOLDEN_DIR = (
   55:     Path(__file__).resolve().parents[2]
   56:     / "experiments"
   57:     / "20260706-ecl-v0-live-capture"
   58:     / "artifacts"
   59: )
   60: 
   61: 
   62: def _mock_embedding() -> EmbeddingClient:
   63:     """Constant-vector embedding (Ollama-free, mirrors ``ecl_v0_golden.py``)."""
   64:     vec = [handoff.GOLDEN_EMBED_VALUE] * EmbeddingClient.DEFAULT_DIM
   65: 
   66:     def handler(request: httpx.Request) -> httpx.Response:
   67:         body = json.loads(request.content)
   68:         inputs = body.get("input") or []
   69:         count = len(inputs) if isinstance(inputs, list) else 1
   70:         return httpx.Response(httpx.codes.OK, json={"embeddings": [vec] * count})
   71: 
   72:     return EmbeddingClient(
   73:         client=httpx.AsyncClient(
   74:             base_url=EmbeddingClient.DEFAULT_ENDPOINT,
   75:             transport=httpx.MockTransport(handler),
   76:         )
   77:     )
   78: 
   79: 
   80: async def _replay_from_manifest(
   81:     recorded: Sequence[RecordedLlmCall], run_config: dict[str, object]
   82: ) -> tuple[EclRunResult, RecordReplayChatClient]:
   83:     """Reconstruct + drive a run from committed decisions + the manifest's run config.
   84: 
   85:     Uses the golden persona/agent-state fixture (D-2: the sealed live run uses
   86:     the same single kant persona/agent as the synthetic golden 窶・both
   87:     ``scripts/ecl_v0_golden.py`` and ``scripts/ecl_v0_live_capture.py`` build
   88:     their agent from ``handoff.golden_agent_state()``/``golden_persona()``) but
   89:     drives ``run_ecl_loop`` with the **committed manifest's** seed / tick count
   90:     / clocks 窶・never a module-level golden constant 窶・so this helper
   91:     generalises unchanged once Issue 004 repoints :data:`_GOLDEN_DIR` at a live
   92:     artifact with a different run config (D-1: 32 ticks, not 8).
   93:     """
   94:     store = MemoryStore(db_path=":memory:")
   95:     store.create_schema()
   96:     embedding = _mock_embedding()
   97:     llm = RecordReplayChatClient(recorded=recorded)
   98:     try:
   99:         result = await run_ecl_loop(
  100:             run_id=str(run_config["run_id"]),
  101:             store=store,
  102:             embedding=embedding,
  103:             llm=llm,
  104:             agent_state=handoff.golden_agent_state(),
  105:             persona=handoff.golden_persona(),
  106:             retrieval_now=datetime.fromisoformat(str(run_config["retrieval_now"])),
  107:             base_ts=datetime.fromisoformat(str(run_config["base_ts"])),
  108:             seed=int(run_config["seed"]),  # type: ignore[arg-type]
  109:             n_cognition_ticks=int(run_config["cognition_ticks"]),  # type: ignore[arg-type]
  110:             physics_ticks_per_cognition=int(  # type: ignore[arg-type]
  111:                 run_config["physics_ticks_per_cognition"]
  112:             ),
  113:             k_ecl=int(run_config["k_ecl"]),  # type: ignore[arg-type]
  114:         )
  115:     finally:
  116:         await embedding.close()
  117:         await store.close()
  118:     return result, llm
  119: 
  120: 
  121: def _read_committed() -> tuple[dict[str, object], str, str, str]:
  122:     """Read the committed manifest + the three data artifacts as text."""
  123:     manifest = json.loads((_GOLDEN_DIR / "manifest.json").read_text(encoding="utf-8"))
  124:     decisions_text = (_GOLDEN_DIR / "decisions.jsonl").read_text(encoding="utf-8")
  125:     trace_text = (_GOLDEN_DIR / "ecl_trace.jsonl").read_text(encoding="utf-8")
  126:     envelope_text = (_GOLDEN_DIR / "envelope_stream.jsonl").read_text(encoding="utf-8")
  127:     return manifest, decisions_text, trace_text, envelope_text
  128: 
  129: 
  130: # --------------------------------------------------------------------------- #
  131: # I4-G1 / O3a 窶・committed decisions alone replay to a byte-identical checksum
  132: # --------------------------------------------------------------------------- #
  133: 
  134: 
  135: async def test_live_golden_replay_checksum_matches() -> None:
  136:     manifest, decisions_text, _trace_text, _envelope_text = _read_committed()
  137:     recorded = handoff.recorded_calls_from_jsonl(decisions_text)
  138: 
  139:     result, llm = await _replay_from_manifest(recorded, manifest["run"])  # type: ignore[arg-type]
  140: 
  141:     assert llm.inner_invocations == 0, (
  142:         "O3a: replaying the committed decisions must never touch a live LLM"
  143:     )
  144:     assert result.checksum == manifest["replay_checksum"], (
  145:         "O3a: replay-only reconstruction must reproduce the committed "
  146:         "manifest's replay_checksum byte-for-byte"
  147:     )
  148: 
  149: 
  150: # --------------------------------------------------------------------------- #
  151: # I4-G2 / O3b 窶・same raw Plane 2 re-renders the artifact set to the same SHA
  152: # --------------------------------------------------------------------------- #
  153: 
  154: 
  155: async def test_live_golden_artifact_rerender_sha() -> None:
  156:     manifest, decisions_text, trace_text, envelope_text = _read_committed()
  157:     recorded = handoff.recorded_calls_from_jsonl(decisions_text)
  158: 
  159:     result, _llm = await _replay_from_manifest(recorded, manifest["run"])  # type: ignore[arg-type]
  160: 
  161:     # Codex TASK-PRE MEDIUM-2: re-render reusing the COMMITTED manifest's
  162:     # env_pins/run block 窶・never a fresh handoff.render_golden(env_pins=None,
  163:     # run_config=None) capture, which would snapshot *this* machine's
  164:     # python/package versions and drift manifest bytes across runners.
  165:     rendered = handoff.render_golden(
  166:         result,
  167:         run_config=manifest["run"],  # type: ignore[arg-type]
  168:         env_pins=manifest["env_pins"],  # type: ignore[arg-type]
  169:     )
  170: 
  171:     committed = {
  172:         "ecl_trace.jsonl": trace_text,
  173:         "decisions.jsonl": decisions_text,
  174:         "envelope_stream.jsonl": envelope_text,
  175:     }
  176:     artifacts = manifest["artifacts"]
  177:     assert isinstance(artifacts, dict)
  178:     for name, committed_text in committed.items():
  179:         expected_sha = artifacts[name]["sha256"]
  180:         actual_sha = hashlib.sha256(rendered[name].encode("utf-8")).hexdigest()
  181:         assert actual_sha == expected_sha, f"{name} sha256 mismatch"
  182:         # Byte-identical, not merely hash-identical (a stronger reproduction
  183:         # witness than SHA-256 equality alone).
  184:         assert rendered[name] == committed_text, f"{name} byte mismatch"
  185: 
  186: 
  187: # --------------------------------------------------------------------------- #
  188: # I4-G3 / O5 窶・parsed-history-dependent-action count (annotation, not a gate)
  189: # --------------------------------------------------------------------------- #
  190: 
  191: 
  192: def test_live_golden_parsed_history_dependent_action(tmp_path: Path) -> None:
  193:     """Count + record O5 ticks 窶・a construction-validity annotation, never a
  194:     hard green/red condition (D-5, Codex TASK-PRE HIGH-2).
  195: 
  196:     O5 = ``llm_status == "ok"`` and ``plan is not None`` and the MoveMsg
  197:     ``resolved_from == "memory_centroid"``: the tick is judged to have parsed a
  198:     real plan that drove a history-dependent move. ``count == 0`` on this
  199:     synthetic golden template would be a valid recorded outcome (a
  200:     construction-validity branch for human judgement, Execution Result), not a
  201:     test failure 窶・so this test asserts only that the recording mechanism ran
  202:     and persisted a well-formed non-negative count, never ``count >=
  203:     LIVE_O5_MIN_TICKS``.
  204:     """
  205:     _manifest, decisions_text, _trace_text, _envelope_text = _read_committed()
  206:     decisions = [
  207:         json.loads(line) for line in decisions_text.splitlines() if line.strip()
  208:     ]
  209: 
  210:     count = sum(
  211:         1
  212:         for d in decisions
  213:         if d["llm_status"] == "ok"
  214:         and d["plan"] is not None
  215:         and d["move_decision"] is not None
  216:         and d["move_decision"]["resolved_from"] == "memory_centroid"
  217:     )
  218: 
  219:     annotation = {
  220:         "o5_parsed_history_dependent_action_count": count,
  221:         "o5_min_ticks_first_contact_threshold": LIVE_O5_MIN_TICKS,
  222:         "hard_gate": False,
  223:         "note": (
  224:             "annotation only (D-5); count>=threshold is a human-judgement "
  225:             "construction-validity branch, not an autonomous pass/fail"
  226:         ),
  227:     }
  228:     annotation_path = tmp_path / "o5_annotation.json"
  229:     annotation_path.write_text(json.dumps(annotation), encoding="utf-8")
  230: 
  231:     recorded_annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
  232:     o5_count = recorded_annotation["o5_parsed_history_dependent_action_count"]
  233:     assert isinstance(o5_count, int)
  234:     assert o5_count >= 0
  235:     assert recorded_annotation["hard_gate"] is False
  236: 
  237: 
  238: # --------------------------------------------------------------------------- #
  239: # I4-G4 窶・measurement-line non-re-entry guard
  240: # --------------------------------------------------------------------------- #
  241: 
  242: _THIS_FILE = Path(__file__)
  243: _LIVE_CAPTURE_FILE = (
  244:     Path(__file__).resolve().parents[2] / "scripts" / "ecl_v0_live_capture.py"
  245: )
  246: 
  247: _BANNED_IMPORT_PREFIX = ("erre_sandbox.evidence",)
  248: _BANNED_IMPORT_SUB = ("spdm", "runningness")
  249: _BANNED_IDENTIFIER = ("floor", "landscape", "verdict", "jaccard", "divergence", "r_min")
  250: 
  251: 
  252: def _assert_no_measurement_surface(tree: ast.Module) -> None:
  253:     """Mirror ``test_ecl_handoff.py``'s guards: no measurement import/identifier."""
  254:     for node in ast.walk(tree):
  255:         if isinstance(node, ast.ImportFrom) and node.module is not None:
  256:             assert not node.module.startswith(_BANNED_IMPORT_PREFIX), node.module
  257:             assert not any(s in node.module for s in _BANNED_IMPORT_SUB), node.module
  258:         if isinstance(node, ast.Import):
  259:             for alias in node.names:
  260:                 assert not alias.name.startswith(_BANNED_IMPORT_PREFIX), alias.name
  261:                 assert not any(s in alias.name for s in _BANNED_IMPORT_SUB), alias.name
  262:         names: list[str] = []
  263:         if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
  264:             names.append(node.id)
  265:         elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
  266:             names.append(node.target.id)
  267:         elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
  268:             names.append(node.name)
  269:         elif isinstance(node, ast.arg):
  270:             names.append(node.arg)
  271:         for name in names:
  272:             low = name.lower()
  273:             assert not any(tok in low for tok in _BANNED_IDENTIFIER), name
  274: 
  275: 
  276: def test_live_golden_measurement_guard() -> None:
  277:     """The replay-verify apparatus computes/emits no floor/landscape/verdict.
  278: 
  279:     Scans both this test module and ``scripts/ecl_v0_live_capture.py`` (the
  280:     ``--verify`` CLI apparatus it exercises indirectly via ``repro.sh``) 窶・the
  281:     same identifier-level guard ``test_ecl_handoff.py`` applies to
  282:     ``handoff.py`` (design ﾂｧ隲也せ4 non-re-entry, holding intact)."""
  283:     for path in (_THIS_FILE, _LIVE_CAPTURE_FILE):
  284:         tree = ast.parse(path.read_text(encoding="utf-8"))
  285:         _assert_no_measurement_surface(tree)

codex
追加ファイルは seam 追加に収まっており、既存 `loop/cycle/world/tick/handoff/ecl_v0_golden` の diff はありません。次は既存 serializer/replay の契約を読んで、追加 verify が本当に同じ bytes を検証しているか確認します。
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"def render_golden|def build_manifest|def recorded_calls_from_jsonl|def validate_envelope_stream|GOLDEN_EMBED_VALUE|K_ECL|def golden_run_config\" src\\erre_sandbox\\integration\\embodied\\handoff.py" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"class RecordReplayChatClient|async def run_ecl_loop|def replay_client_from|inner_invocations|recorded\" src\\erre_sandbox\\integration\\embodied\\loop.py" in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"def chat|think|OllamaUnavailableError|class OllamaChatClient\" src\\erre_sandbox\\inference\\ollama_adapter.py" in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"class ResolvedSampling|model_dump\" src\\erre_sandbox\\inference\\sampling.py src\\erre_sandbox\\schemas.py" in C:\ERRE-Sand_Box
 succeeded in 262ms:
11:  response), and returns it verbatim. In *replay* mode it injects the recorded
120:      returned ``None``); recorded like ``ok`` (content present) because replay
132:    """The recorded call's outcome tag.
137:    *not* tagged here — it is recorded as ``ok`` (content present) and the
156:class RecordReplayChatClient:
157:    """Duck-typed chat client that records live calls or replays recorded ones.
164:    * **Record** — ``inner`` set, ``recorded=None``: each ``chat`` delegates to the
166:    * **Replay** — ``recorded`` set, ``inner=None``: each ``chat`` returns the next
167:      recorded response in order and **never touches an LLM** (``inner_invocations``
175:        recorded: Sequence[RecordedLlmCall] | None = None,
179:            list(recorded) if recorded is not None else None
183:        self._inner_invocations = 0
187:        """``True`` in replay mode (recorded responses injected, no LLM called)."""
201:    def inner_invocations(self) -> int:
203:        return self._inner_invocations
220:                    "the recorded Plane 2 is shorter than the replay run's demand"
227:            # served in [before, after), so the raised call must be recorded as
233:                    "ECL replay: re-raising the recorded OllamaUnavailableError "
236:            # ``ok`` / ``unparseable``: re-inject the recorded content; the cycle
240:                    "ECL replay: non-raised recorded call has no response — "
241:                    "the recorded Plane 2 is malformed"
248:        self._inner_invocations += 1
442:        """The recorded Plane 2 to seed a replay run (AC4: ``decisions`` alone)."""
446:def replay_client_from(result: EclRunResult) -> RecordReplayChatClient:
447:    """Build a replay adapter from a prior run's recorded decisions (AC4).
449:    The replay run driven with this client re-injects the recorded responses and
450:    never calls an LLM (``inner_invocations == 0``), reconstructing the state — and
453:    return RecordReplayChatClient(recorded=result.replay_calls())
495:async def run_ecl_loop(

 succeeded in 292ms:
112:class OllamaUnavailableError(RuntimeError):
128:class OllamaChatClient:
189:    async def chat(
196:        think: bool | None = None,
212:            think: Top-level Ollama payload flag controlling thinking-model
218:                budget on <think> tokens and returns empty content
223:            OllamaUnavailableError: When the request cannot be delivered, the
227:        body = self._build_body(messages, sampling, model, options, think)
241:        think: bool | None,  # noqa: FBT001 — private helper; public ``chat`` makes it kw-only
255:        # Guarded: only emit ``think`` when the caller explicitly opted in.
258:        # thinking on every tick.
259:        if think is not None:
260:            body["think"] = think
264:        """Verify Ollama is reachable. Raise ``OllamaUnavailableError`` if not.
274:            raise OllamaUnavailableError(
278:            raise OllamaUnavailableError(
282:            raise OllamaUnavailableError(
290:            raise OllamaUnavailableError(
294:            raise OllamaUnavailableError(
299:            raise OllamaUnavailableError(
307:            raise OllamaUnavailableError(
312:            raise OllamaUnavailableError(
324:            raise OllamaUnavailableError(
343:            raise OllamaUnavailableError(
354:    "OllamaUnavailableError",

 succeeded in 319ms:
49:from erre_sandbox.cognition.embodiment import K_ECL
175:GOLDEN_EMBED_VALUE: Final[float] = 0.01
518:def recorded_calls_from_jsonl(text: str) -> list[RecordedLlmCall]:
585:def validate_envelope_stream(text: str) -> list[ControlEnvelope]:
629:def golden_run_config() -> dict[str, Any]:
639:        "k_ecl": K_ECL,
645:def build_manifest(
728:def render_golden(
785:    "GOLDEN_EMBED_VALUE",

 succeeded in 288ms:
src\erre_sandbox\inference\sampling.py:39:class ResolvedSampling(BaseModel):

hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$start=500;$end=780;$i=0; Get-Content src'"\\erre_sandbox\\integration\\embodied\\handoff.py | ForEach-Object { "'$i++; if($i -ge $start -and $i -le $end){ '"'{0,5}: {1}' -f "'$i, $_ }}' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$start=150;$end=275;$i=0; Get-Content src'"\\erre_sandbox\\integration\\embodied\\loop.py | ForEach-Object { "'$i++; if($i -ge $start -and $i -le $end){ '"'{0,5}: {1}' -f "'$i, $_ }}' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$start=430;$end=590;$i=0; Get-Content src'"\\erre_sandbox\\integration\\embodied\\loop.py | ForEach-Object { "'$i++; if($i -ge $start -and $i -le $end){ '"'{0,5}: {1}' -f "'$i, $_ }}' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$start=185;$end=265;$i=0; Get-Content src'"\\erre_sandbox\\inference\\ollama_adapter.py | ForEach-Object { "'$i++; if($i -ge $start -and $i -le $end){ '"'{0,5}: {1}' -f "'$i, $_ }}' in C:\ERRE-Sand_Box
 succeeded in 309ms:
  150: 
  151: 
  152: class EclReplayError(RuntimeError):
  153:     """Replay stream is exhausted or a record-mode client has no inner backend."""
  154: 
  155: 
  156: class RecordReplayChatClient:
  157:     """Duck-typed chat client that records live calls or replays recorded ones.
  158: 
  159:     Structurally matches the keyword surface of
  160:     :class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient.chat` that
  161:     :class:`~erre_sandbox.cognition.CognitionCycle` calls, so it can stand in for
  162:     the real client without the cycle importing this class.
  163: 
  164:     * **Record** 窶・``inner`` set, ``recorded=None``: each ``chat`` delegates to the
  165:       inner client once, captures the call, and returns the real response.
  166:     * **Replay** 窶・``recorded`` set, ``inner=None``: each ``chat`` returns the next
  167:       recorded response in order and **never touches an LLM** (``inner_invocations``
  168:       stays 0 窶・the AC4 witness).
  169:     """
  170: 
  171:     def __init__(
  172:         self,
  173:         *,
  174:         inner: Any | None = None,
  175:         recorded: Sequence[RecordedLlmCall] | None = None,
  176:     ) -> None:
  177:         self._inner = inner
  178:         self._replay: list[RecordedLlmCall] | None = (
  179:             list(recorded) if recorded is not None else None
  180:         )
  181:         self._used: list[RecordedLlmCall] = []
  182:         self._replay_index = 0
  183:         self._inner_invocations = 0
  184: 
  185:     @property
  186:     def is_replay(self) -> bool:
  187:         """``True`` in replay mode (recorded responses injected, no LLM called)."""
  188:         return self._replay is not None
  189: 
  190:     @property
  191:     def used(self) -> tuple[RecordedLlmCall, ...]:
  192:         """The calls actually served, in order 窶・one per cognition tick.
  193: 
  194:         Uniform across modes: the captured calls in record mode, the injected
  195:         calls in replay mode, so the driver correlates ``used[t]`` with cognition
  196:         tick ``t`` either way.
  197:         """
  198:         return tuple(self._used)
  199: 
  200:     @property
  201:     def inner_invocations(self) -> int:
  202:         """How many times a real (inner) LLM was called 窶・0 in replay mode (AC4)."""
  203:         return self._inner_invocations
  204: 
  205:     async def chat(
  206:         self,
  207:         messages: Sequence[ChatMessage],
  208:         *,
  209:         sampling: ResolvedSampling,
  210:         model: str | None = None,
  211:         options: dict[str, Any] | None = None,
  212:         think: bool | None = None,
  213:     ) -> ChatResponse:
  214:         system_prompt = next((m.content for m in messages if m.role == "system"), "")
  215:         user_prompt = next((m.content for m in messages if m.role == "user"), "")
  216:         if self._replay is not None:
  217:             if self._replay_index >= len(self._replay):
  218:                 msg = (
  219:                     f"ECL replay exhausted after {self._replay_index} calls; "
  220:                     "the recorded Plane 2 is shorter than the replay run's demand"
  221:                 )
  222:                 raise EclReplayError(msg)
  223:             call = self._replay[self._replay_index]
  224:             # Advance the stream (index + ``_used``) BEFORE any re-raise so a
  225:             # ``raised`` call still leaves the replay stream tick-aligned for the
  226:             # next tick (Codex M-2): the driver correlates a tick with the calls
  227:             # served in [before, after), so the raised call must be recorded as
  228:             # served even though it re-raises.
  229:             self._replay_index += 1
  230:             self._used.append(call)
  231:             if call.outcome == "raised":
  232:                 raise OllamaUnavailableError(
  233:                     "ECL replay: re-raising the recorded OllamaUnavailableError "
  234:                     "so the cognition fallback fires as it did on record"
  235:                 )
  236:             # ``ok`` / ``unparseable``: re-inject the recorded content; the cycle
  237:             # re-parses it and reconstructs the same decision (move or fallback).
  238:             if call.response is None:  # pragma: no cover 窶・schema invariant
  239:                 msg = (
  240:                     "ECL replay: non-raised recorded call has no response 窶・"
  241:                     "the recorded Plane 2 is malformed"
  242:                 )
  243:                 raise EclReplayError(msg)
  244:             return call.response
  245:         if self._inner is None:
  246:             msg = "record-mode RecordReplayChatClient needs an inner chat client"
  247:             raise EclReplayError(msg)
  248:         self._inner_invocations += 1
  249:         try:
  250:             response = await self._inner.chat(
  251:                 messages,
  252:                 sampling=sampling,
  253:                 model=model,
  254:                 options=options,
  255:                 think=think,
  256:             )
  257:         except OllamaUnavailableError:
  258:             # Record the failure as a ``raised`` (response-less) call and keep
  259:             # ``_used`` tick-aligned, THEN re-raise so the cognition cycle takes
  260:             # its fallback branch (design ﾂｧ3.2 / Codex HIGH-1). Replaying this
  261:             # call re-raises the same exception and reproduces the fallback.
  262:             self._used.append(
  263:                 RecordedLlmCall(
  264:                     system_prompt=system_prompt,
  265:                     user_prompt=user_prompt,
  266:                     sampling=sampling,
  267:                     response=None,
  268:                     outcome="raised",
  269:                 )
  270:             )
  271:             raise
  272:         call = RecordedLlmCall(
  273:             system_prompt=system_prompt,
  274:             user_prompt=user_prompt,
  275:             sampling=sampling,

 succeeded in 330ms:
  430: @dataclass(frozen=True, slots=True)
  431: class EclRunResult:
  432:     """Outcome of one :func:`run_ecl_loop` drive."""
  433: 
  434:     run_id: str
  435:     rows: tuple[EclTraceRow, ...]
  436:     decisions: tuple[EclDecisionRecord, ...]
  437:     checksum: str
  438: 
  439:     def replay_calls(self) -> tuple[RecordedLlmCall, ...]:
  440:         """The recorded Plane 2 to seed a replay run (AC4: ``decisions`` alone)."""
  441:         return tuple(d.call for d in self.decisions)
  442: 
  443: 
  444: def replay_client_from(result: EclRunResult) -> RecordReplayChatClient:
  445:     """Build a replay adapter from a prior run's recorded decisions (AC4).
  446: 
  447:     The replay run driven with this client re-injects the recorded responses and
  448:     never calls an LLM (``inner_invocations == 0``), reconstructing the state 窶・and
  449:     hence the :func:`ecl_trace_checksum` 窶・from the Plane 2 record alone.
  450:     """
  451:     return RecordReplayChatClient(recorded=result.replay_calls())
  452: 
  453: 
  454: # --------------------------------------------------------------------------- #
  455: # Driver
  456: # --------------------------------------------------------------------------- #
  457: 
  458: 
  459: @dataclass(slots=True)
  460: class _SinkContext:
  461:     """Mutable per-window context the trace-sink closure reads (driver writes)."""
  462: 
  463:     agent_tick: int = 0
  464:     move: EclDestination | None = None
  465: 
  466: 
  467: def _default_observation_factory(
  468:     agent_id: str,
  469: ) -> Callable[[int], Sequence[Observation]]:
  470:     """One deterministic perception per tick so located memories accumulate.
  471: 
  472:     Each cognition tick's observation is written (ECL record mode) as an episodic
  473:     memory *at the agent's current position*; as the agent transits, those
  474:     formation locations spread, so the strength-weighted centroid the resolver
  475:     reads becomes history-dependent (grill G-5).
  476:     """
  477: 
  478:     def factory(agent_tick: int) -> Sequence[Observation]:
  479:         return [
  480:             PerceptionEvent(
  481:                 tick=agent_tick,
  482:                 agent_id=agent_id,
  483:                 modality="sight",
  484:                 source_zone=Zone.STUDY,
  485:                 content=f"ecl v0 forage step {agent_tick}",
  486:                 intensity=0.4,
  487:             )
  488:         ]
  489: 
  490:     return factory
  491: 
  492: 
  493: async def run_ecl_loop(
  494:     *,
  495:     run_id: str,
  496:     store: MemoryStore,
  497:     embedding: EmbeddingClient,
  498:     llm: RecordReplayChatClient,
  499:     agent_state: AgentState,
  500:     persona: PersonaSpec,
  501:     retrieval_now: datetime,
  502:     base_ts: datetime,
  503:     seed: int = 0,
  504:     n_cognition_ticks: int = GOLDEN_COGNITION_TICKS,
  505:     physics_ticks_per_cognition: int = DEFAULT_PHYSICS_TICKS_PER_COGNITION,
  506:     k_ecl: int = K_ECL,
  507:     reflector: Reflector | None = None,
  508:     observation_factory: Callable[[int], Sequence[Observation]] | None = None,
  509: ) -> EclRunResult:
  510:     """Drive the I3 live seam deterministically for one embodied agent.
  511: 
  512:     Constructs the frozen determinism handles (:class:`EclRecordMode` with a fixed
  513:     ``retrieval_now`` / ``base_ts``, a seeded ``Random`` for the cycle, a
  514:     ``now_factory``-pinned :class:`Retriever`) and a live
  515:     :class:`~erre_sandbox.cognition.CognitionCycle` +
  516:     :class:`~erre_sandbox.world.WorldRuntime` **without modifying either**, then
  517:     steps ``n_cognition_ticks`` cognition ticks 窶・each followed by
  518:     ``physics_ticks_per_cognition`` 30 Hz physics ticks 窶・while an
  519:     ``ecl_trace_sink`` closure assembles the :class:`EclTraceRow` stream. Returns
  520:     the rows, the per-tick :class:`EclDecisionRecord` Plane 2 provenance, and the
  521:     :func:`ecl_trace_checksum`.
  522: 
  523:     ``llm`` is the record/replay adapter; ``store`` / ``embedding`` are injected so
  524:     the harness never depends on a live Ollama. The single-agent restriction is a
  525:     v0 scope choice (grill G-5); the log slots carry ``order_slot`` for
  526:     forward-compatible multi-agent runs.
  527:     """
  528:     agent_id = agent_state.agent_id
  529:     ecl_mode = EclRecordMode(
  530:         run_id=run_id,
  531:         retrieval_now=retrieval_now,
  532:         base_ts=base_ts,
  533:         k_ecl=k_ecl,
  534:         reflection_disabled=True,
  535:     )
  536:     retriever = Retriever(store, embedding, now_factory=retrieval_now)
  537:     # Plane 2 bias capture: the cycle pushes one BiasFiredEvent per resample. The
  538:     # slot is cleared before each cognition step so a decision records only its own
  539:     # tick's event (``None`` when the resample did not fire).
  540:     bias_slot: list[BiasFiredEvent] = []
  541:     cycle = CognitionCycle(
  542:         retriever=retriever,
  543:         store=store,
  544:         embedding=embedding,
  545:         # RecordReplayChatClient structurally matches the ``chat`` surface the cycle
  546:         # calls; the concrete annotation is ``OllamaChatClient`` so we duck-type.
  547:         llm=cast("Any", llm),
  548:         rng=Random(seed),  # noqa: S311 窶・determinism seed, not cryptographic
  549:         ecl_mode=ecl_mode,
  550:         bias_sink=bias_slot.append,
  551:         reflector=reflector,
  552:     )
  553:     clock = ManualClock(start=0.0)
  554:     ctx = _SinkContext()
  555:     order_slot = sorted([agent_id]).index(agent_id)
  556: 
  557:     rows: list[EclTraceRow] = []
  558: 
  559:     def sink(
  560:         sink_agent_id: str,
  561:         physics_tick_index: int,
  562:         x: float,
  563:         y: float,
  564:         z: float,
  565:         yaw: float,
  566:         pitch: float,
  567:         zone: Zone,
  568:     ) -> None:
  569:         md = ctx.move
  570:         rows.append(
  571:             EclTraceRow(
  572:                 run_id=run_id,
  573:                 agent_id=sink_agent_id,
  574:                 physics_tick_index=physics_tick_index,
  575:                 agent_tick=ctx.agent_tick,
  576:                 order_slot=order_slot,
  577:                 x=x,
  578:                 y=y,
  579:                 z=z,
  580:                 yaw=yaw,
  581:                 pitch=pitch,
  582:                 zone=zone,
  583:                 resolved_from=md.resolved_from if md is not None else None,
  584:                 move_centroid=md.centroid if md is not None else None,
  585:                 move_provenance=md.provenance if md is not None else None,
  586:                 move_jitter=md.jitter if md is not None else None,
  587:                 move_pre_clamp=md.pre_clamp if md is not None else None,
  588:                 move_post_clamp=md.post_clamp if md is not None else None,
  589:                 move_clamp_fired=md.clamp_fired if md is not None else None,
  590:             )

 succeeded in 370ms:
  500:                 "post_clamp": list(move.post_clamp),
  501:                 "clamp_fired": move.clamp_fired,
  502:             }
  503:             if move is not None
  504:             else None
  505:         ),
  506:         "envelope_provenance": [
  507:             _quantize_embedded_json(env) for env in decision.envelope_provenance
  508:         ],
  509:     }
  510: 
  511: 
  512: def decisions_to_jsonl(decisions: Sequence[EclDecisionRecord]) -> str:
  513:     """Serialise the Plane 2 decision set as canonical JSONL."""
  514:     return _jsonl([decision_to_dict(d) for d in decisions])
  515: 
  516: 
  517: def recorded_calls_from_jsonl(text: str) -> list[RecordedLlmCall]:
  518:     """Reconstruct the replay stream from committed ``decisions.jsonl`` alone.
  519: 
  520:     This is the cross-machine reproducibility contract (AC2): a consumer that
  521:     only has ``decisions.jsonl`` can rebuild the recorded Plane 2 and replay the
  522:     run to the exact same :func:`~...loop.ecl_trace_checksum`.
  523:     """
  524:     return [
  525:         _recorded_call_from_dict(json.loads(line)["call"]) for line in _nonempty(text)
  526:     ]
  527: 
  528: 
  529: # --------------------------------------------------------------------------- #
  530: # envelope_stream.jsonl (converter: decisions 竊・ordered ControlEnvelope replay)
  531: # --------------------------------------------------------------------------- #
  532: 
  533: 
  534: def build_envelope_stream(result: EclRunResult) -> list[dict[str, Any]]:
  535:     """Convert the run's recorded envelopes into an ordered replay stream (AC3).
  536: 
  537:     For each cognition tick's :class:`EclDecisionRecord`, the recorded envelope
  538:     provenance is re-validated through the ``ControlEnvelope`` discriminated
  539:     union (schema conformance), the Godot-replayable kinds
  540:     (:data:`ENVELOPE_STREAM_KINDS`) are kept, and each is wrapped with its
  541:     ``order_slot`` / ``agent_tick`` / within-tick ``seq``. The list is sorted by
  542:     ``(order_slot, agent_tick, seq)`` so replay order is deterministic and
  543:     forward-compatible with multi-agent runs (single agent 竊・``order_slot`` 0).
  544: 
  545:     ``order_slot`` is the frozen ``sorted(agent_id)`` index of each envelope's own
  546:     ``agent_id`` (design ﾂｧ隲也せ6), derived per-envelope from a slot map over the
  547:     run's agents 窶・not the first row's slot 窶・so a future multi-agent run
  548:     interleaves correctly (Codex TASK-POST LOW). Empty runs yield an empty stream.
  549:     """
  550:     slot_by_agent = {
  551:         agent_id: slot
  552:         for slot, agent_id in enumerate(sorted({r.agent_id for r in result.rows}))
  553:     }
  554:     entries: list[dict[str, Any]] = []
  555:     for decision in result.decisions:
  556:         seq = 0
  557:         for env_json in decision.envelope_provenance:
  558:             raw = json.loads(env_json)
  559:             if raw.get("kind") not in ENVELOPE_STREAM_KINDS:
  560:                 continue
  561:             # Re-validate through the discriminated union (AC3 conformance) then
  562:             # re-dump canonically so the stream carries a schema-clean envelope.
  563:             envelope = _CONTROL_ENVELOPE_ADAPTER.validate_python(raw)
  564:             entries.append(
  565:                 {
  566:                     "order_slot": slot_by_agent.get(raw.get("agent_id", ""), 0),
  567:                     "agent_tick": decision.agent_tick,
  568:                     "seq": seq,
  569:                     "envelope": _CONTROL_ENVELOPE_ADAPTER.dump_python(
  570:                         envelope, mode="json"
  571:                     ),
  572:                 }
  573:             )
  574:             seq += 1
  575:     entries.sort(key=lambda e: (e["order_slot"], e["agent_tick"], e["seq"]))
  576:     return entries
  577: 
  578: 
  579: def envelope_stream_to_jsonl(entries: Sequence[dict[str, Any]]) -> str:
  580:     """Serialise the converter's envelope stream as canonical JSONL."""
  581:     return _jsonl(list(entries))
  582: 
  583: 
  584: def validate_envelope_stream(text: str) -> list[ControlEnvelope]:
  585:     """Parse committed ``envelope_stream.jsonl`` and validate each envelope.
  586: 
  587:     Returns the validated :class:`ControlEnvelope` objects in file order; raises
  588:     if any wrapped envelope is not schema-conformant (AC3).
  589:     """
  590:     envelopes: list[ControlEnvelope] = []
  591:     for line in _nonempty(text):
  592:         wrapper = json.loads(line)
  593:         envelopes.append(_CONTROL_ENVELOPE_ADAPTER.validate_python(wrapper["envelope"]))
  594:     return envelopes
  595: 
  596: 
  597: # --------------------------------------------------------------------------- #
  598: # manifest.json
  599: # --------------------------------------------------------------------------- #
  600: 
  601: 
  602: def capture_env_pins() -> dict[str, Any]:
  603:     """Snapshot the runtime env for the manifest (provenance, not determinism).
  604: 
  605:     Records interpreter + key package versions and ``ERRE_ZONE_BIAS_P`` (pinned
  606:     so a future consumer re-runs under the same bias regime 窶・bias is
  607:     non-firing for preferred-zone destinations but an un-pinned env var is an
  608:     un-pinned non-determinism source, design ﾂｧ隲也せ5 / Codex).
  609:     """
  610:     packages: dict[str, str] = {}
  611:     for name in ("pydantic", "httpx"):
  612:         try:
  613:             packages[name] = metadata.version(name)
  614:         except metadata.PackageNotFoundError:  # pragma: no cover - env-dependent
  615:             packages[name] = "unknown"
  616:     return {
  617:         "python": f"{sys.version_info.major}.{sys.version_info.minor}"
  618:         f".{sys.version_info.micro}",
  619:         "packages": packages,
  620:         "godot": "4.6 (consumer; not required to generate)",
  621:         # Fallback mirrors ``CognitionCycle.__init__``'s
  622:         # ``os.environ.get("ERRE_ZONE_BIAS_P", "0.2")`` default so an unset env
  623:         # records the value the run actually used (Codex TASK-POST MEDIUM-2).
  624:         "ERRE_ZONE_BIAS_P": os.environ.get("ERRE_ZONE_BIAS_P", "0.2"),
  625:     }
  626: 
  627: 
  628: def golden_run_config() -> dict[str, Any]:
  629:     """The golden run's input config for the manifest ``run`` block.
  630: 
  631:     Explicit so :func:`build_manifest` records the *actual* run inputs rather
  632:     than reading module globals 窶・a non-golden caller passes its own config and
  633:     gets honest provenance (Codex TASK-POST MEDIUM-2).
  634:     """
  635:     return {
  636:         "seed": GOLDEN_SEED,
  637:         "physics_ticks_per_cognition": GOLDEN_PHYSICS_TICKS_PER_COGNITION,
  638:         "k_ecl": K_ECL,
  639:         "base_ts": GOLDEN_TS.isoformat(),
  640:         "retrieval_now": GOLDEN_TS.isoformat(),
  641:     }
  642: 
  643: 
  644: def build_manifest(
  645:     result: EclRunResult,
  646:     *,
  647:     run_config: dict[str, Any],
  648:     trace_jsonl: str,
  649:     decisions_jsonl: str,
  650:     envelope_jsonl: str,
  651:     env_pins: dict[str, Any] | None = None,
  652: ) -> dict[str, Any]:
  653:     """Assemble the ``manifest.json`` dict 窶・the AC1 pin surface (design ﾂｧ隲也せ5).
  654: 
  655:     ``result`` supplies the derived run metadata (agent_ids / tick counts) + the
  656:     authoritative ``replay_checksum`` (``ecl_trace_checksum``); ``run_config``
  657:     supplies the run *inputs* (seed / physics_ticks_per_cognition / k_ecl /
  658:     clocks) so the provenance reflects the actual run, not module globals (Codex
  659:     TASK-POST MEDIUM-2). The three ``*_jsonl`` strings supply the per-artifact
  660:     SHA-256 integrity hashes; all convention/checklist pins are module constants
  661:     so they are stable across bakes; ``env_pins`` defaults to a fresh snapshot.
  662:     """
  663:     agent_ids = sorted({r.agent_id for r in result.rows})
  664:     world_tick_count = max((r.physics_tick_index for r in result.rows), default=-1) + 1
  665:     cognition_ticks = len({r.agent_tick for r in result.rows})
  666:     return {
  667:         "manifest_version": MANIFEST_SCHEMA_VERSION,
  668:         "schema_version": SCHEMA_VERSION,
  669:         "run": {
  670:             "run_id": result.run_id,
  671:             "seed": run_config["seed"],
  672:             "agent_ids": agent_ids,
  673:             "world_tick_count": world_tick_count,
  674:             "cognition_ticks": cognition_ticks,
  675:             "physics_ticks_per_cognition": run_config["physics_ticks_per_cognition"],
  676:             "k_ecl": run_config["k_ecl"],
  677:             "base_ts": run_config["base_ts"],
  678:             "retrieval_now": run_config["retrieval_now"],
  679:         },
  680:         "coordinate_convention": COORDINATE_CONVENTION,
  681:         "tick_mapping": TICK_MAPPING,
  682:         "determinism_checklist": list(DETERMINISM_CHECKLIST),
  683:         "canonical_json_rules": CANONICAL_JSON_RULES,
  684:         "env_pins": env_pins if env_pins is not None else capture_env_pins(),
  685:         "artifacts": {
  686:             "ecl_trace.jsonl": {"sha256": _sha256(trace_jsonl)},
  687:             "decisions.jsonl": {"sha256": _sha256(decisions_jsonl)},
  688:             "envelope_stream.jsonl": {"sha256": _sha256(envelope_jsonl)},
  689:         },
  690:         "replay_checksum": result.checksum,
  691:         "replay_checksum_algorithm": "sha256",
  692:         # Derived from CANONICAL_JSON_RULES rather than a hardcoded literal so the
  693:         # advertised checksum canonicalisation can never drift from the rules the
  694:         # module actually applies (CR-M1). The checksum canonicalisation is exactly
  695:         # these five keys (sort_keys + compact separators + ensure_ascii=False +
  696:         # allow_nan=False + float_quantize_decimals, the last absorbing
  697:         # cross-platform libm drift); float_repr / newline are JSONL-shape rules,
  698:         # not part of the checksum contract, so they stay out.
  699:         "replay_checksum_json_rules": {
  700:             k: CANONICAL_JSON_RULES[k]
  701:             for k in (
  702:                 "sort_keys",
  703:                 "separators",
  704:                 "ensure_ascii",
  705:                 "allow_nan",
  706:                 "float_quantize_decimals",
  707:             )
  708:         },
  709:         "expected_envelope_ordering": "sort ascending by (order_slot, agent_tick, seq)",
  710:         "envelope_stream_kinds": list(ENVELOPE_STREAM_KINDS),
  711:         "godot_headless_command": GODOT_HEADLESS_COMMAND,
  712:     }
  713: 
  714: 
  715: # --------------------------------------------------------------------------- #
  716: # Golden artifact bundle
  717: # --------------------------------------------------------------------------- #
  718: 
  719: GOLDEN_FILENAMES: Final[tuple[str, ...]] = (
  720:     "manifest.json",
  721:     "ecl_trace.jsonl",
  722:     "decisions.jsonl",
  723:     "envelope_stream.jsonl",
  724: )
  725: 
  726: 
  727: def render_golden(
  728:     result: EclRunResult,
  729:     *,
  730:     run_config: dict[str, Any] | None = None,
  731:     env_pins: dict[str, Any] | None = None,
  732: ) -> dict[str, str]:
  733:     """Render the four handoff artifacts as ``{filename: text}`` (pure).
  734: 
  735:     Deterministic given ``result`` (and ``run_config`` / ``env_pins`` for
  736:     ``manifest.json``): the caller writes the strings, or diffs them against the
  737:     committed golden. ``run_config`` defaults to :func:`golden_run_config`.
  738:     """
  739:     trace_jsonl = trace_rows_to_jsonl(result.rows)
  740:     decisions_jsonl = decisions_to_jsonl(result.decisions)
  741:     envelope_jsonl = envelope_stream_to_jsonl(build_envelope_stream(result))
  742:     manifest = build_manifest(
  743:         result,
  744:         run_config=run_config if run_config is not None else golden_run_config(),
  745:         trace_jsonl=trace_jsonl,
  746:         decisions_jsonl=decisions_jsonl,
  747:         envelope_jsonl=envelope_jsonl,
  748:         env_pins=env_pins,
  749:     )
  750:     return {
  751:         "manifest.json": canonical_dumps(manifest) + "\n",
  752:         "ecl_trace.jsonl": trace_jsonl,
  753:         "decisions.jsonl": decisions_jsonl,
  754:         "envelope_stream.jsonl": envelope_jsonl,
  755:     }
  756: 
  757: 
  758: def write_golden(
  759:     result: EclRunResult,
  760:     out_dir: Path,
  761:     *,
  762:     run_config: dict[str, Any] | None = None,
  763:     env_pins: dict[str, Any] | None = None,
  764: ) -> None:
  765:     """Write the four handoff artifacts into ``out_dir`` (the only side-effect)."""
  766:     out_dir.mkdir(parents=True, exist_ok=True)
  767:     rendered = render_golden(result, run_config=run_config, env_pins=env_pins)
  768:     for filename, text in rendered.items():
  769:         (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")
  770: 
  771: 
  772: def _nonempty(text: str) -> list[str]:
  773:     return [line for line in text.splitlines() if line.strip()]
  774: 
  775: 
  776: __all__ = [
  777:     "CANONICAL_FLOAT_DECIMALS",
  778:     "CANONICAL_JSON_RULES",
  779:     "COORDINATE_CONVENTION",
  780:     "DETERMINISM_CHECKLIST",

 succeeded in 296ms:
  185:     # ------------------------------------------------------------------
  186:     # Public API
  187:     # ------------------------------------------------------------------
  188: 
  189:     async def chat(
  190:         self,
  191:         messages: Sequence[ChatMessage],
  192:         *,
  193:         sampling: ResolvedSampling,
  194:         model: str | None = None,
  195:         options: dict[str, Any] | None = None,
  196:         think: bool | None = None,
  197:     ) -> ChatResponse:
  198:         """Send a chat completion and return a normalised :class:`ChatResponse`.
  199: 
  200:         Args:
  201:             messages: Role-tagged messages; Ollama accepts system/user/assistant.
  202:             sampling: Pre-composed sampling (see
  203:                 :func:`erre_sandbox.inference.sampling.compose_sampling`).
  204:                 Requiring this type in the signature makes it impossible to
  205:                 forget ERRE delta composition or the clamp.
  206:             model: One-shot override of :attr:`DEFAULT_MODEL` for this call.
  207:             options: Extra Ollama ``options`` keys (``num_ctx``, ``num_predict``,
  208:                 ``stop``, 窶ｦ) passed through as-is. The sampling values
  209:                 (``temperature`` / ``top_p`` / ``repeat_penalty``) are applied
  210:                 **after** these, so a caller cannot accidentally override the
  211:                 clamped sampling.
  212:             think: Top-level Ollama payload flag controlling thinking-model
  213:                 reasoning on models like qwen3. ``None`` (default) omits the
  214:                 key entirely, preserving the M2 wire shape for existing
  215:                 callers (``cognition.cycle`` / ``Reflector``). ``False``
  216:                 suppresses hidden reasoning 窶・required for dialog_turn
  217:                 generation on qwen3:8b where the default spends the response
  218:                 budget on <think> tokens and returns empty content
  219:                 (validated in the M5 LLM spike).
  220:                 Must be set at the body top level, not inside ``options``.
  221: 
  222:         Raises:
  223:             OllamaUnavailableError: When the request cannot be delivered, the
  224:                 server responds non-2xx, or the payload cannot be parsed as a
  225:                 :class:`ChatResponse`.
  226:         """
  227:         body = self._build_body(messages, sampling, model, options, think)
  228:         payload = await self._post(body)
  229:         return self._parse(payload)
  230: 
  231:     # ------------------------------------------------------------------
  232:     # Internals
  233:     # ------------------------------------------------------------------
  234: 
  235:     def _build_body(
  236:         self,
  237:         messages: Sequence[ChatMessage],
  238:         sampling: ResolvedSampling,
  239:         model: str | None,
  240:         options: dict[str, Any] | None,
  241:         think: bool | None,  # noqa: FBT001 窶・private helper; public ``chat`` makes it kw-only
  242:     ) -> dict[str, Any]:
  243:         merged_options: dict[str, Any] = dict(options or {})
  244:         # Sampling is authoritative 窶・intentionally overwrite any caller-supplied
  245:         # duplicates so T12 cannot silently regress the clamp (design.md ﾂｧ2.2).
  246:         merged_options["temperature"] = sampling.temperature
  247:         merged_options["top_p"] = sampling.top_p
  248:         merged_options["repeat_penalty"] = sampling.repeat_penalty
  249:         body: dict[str, Any] = {
  250:             "model": model or self.model,
  251:             "messages": [m.model_dump() for m in messages],
  252:             "stream": False,
  253:             "options": merged_options,
  254:         }
  255:         # Guarded: only emit ``think`` when the caller explicitly opted in.
  256:         # ``None`` default preserves the pre-M5 wire shape for cognition /
  257:         # reflection paths, which would otherwise silently suppress qwen3
  258:         # thinking on every tick.
  259:         if think is not None:
  260:             body["think"] = think
  261:         return body
  262: 
  263:     async def health_check(self) -> None:
  264:         """Verify Ollama is reachable. Raise ``OllamaUnavailableError`` if not.
  265: 

hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$start=270;$end=430;$i=0; Get-Content src'"\\erre_sandbox\\integration\\embodied\\loop.py | ForEach-Object { "'$i++; if($i -ge $start -and $i -le $end){ '"'{0,5}: {1}' -f "'$i, $_ }}' in C:\ERRE-Sand_Box
 succeeded in 268ms:
  270:             )
  271:             raise
  272:         call = RecordedLlmCall(
  273:             system_prompt=system_prompt,
  274:             user_prompt=user_prompt,
  275:             sampling=sampling,
  276:             response=response,
  277:             outcome="ok",
  278:         )
  279:         self._used.append(call)
  280:         return response
  281: 
  282: 
  283: # --------------------------------------------------------------------------- #
  284: # Plane 2 窶・per-cognition-tick decision record (full LLM provenance)
  285: # --------------------------------------------------------------------------- #
  286: 
  287: 
  288: @dataclass(frozen=True, slots=True)
  289: class EclDecisionRecord:
  290:     """One cognition tick's Plane 2 record 窶・full action-LLM provenance (ﾂｧ隲也せ3).
  291: 
  292:     Carries the closed record set: the post-processed full :class:`LLMPlan`
  293:     (re-parsed from the raw response), the schema version, the fallback status,
  294:     the ``_bias_target_zone`` resample event (``None`` when it did not fire), the
  295:     move-decision provenance (:class:`EclDestination`), the emitted envelope
  296:     provenance, and the underlying :class:`RecordedLlmCall` (prompt / sampling /
  297:     raw response). Replaying ``[d.call for d in decisions]`` reconstructs the run
  298:     with no fresh LLM 窶・the AC4 completeness witness.
  299:     """
  300: 
  301:     agent_tick: int
  302:     call: RecordedLlmCall
  303:     plan: LLMPlan | None
  304:     plan_schema_version: str
  305:     llm_fell_back: bool
  306:     llm_status: str
  307:     bias_fired: BiasFiredEvent | None
  308:     move_decision: EclDestination | None
  309:     envelope_provenance: tuple[str, ...]
  310: 
  311: 
  312: # --------------------------------------------------------------------------- #
  313: # Trace row + replay checksum (frozen design-copy of stub.TraceRow / trace_checksum)
  314: # --------------------------------------------------------------------------- #
  315: 
  316: 
  317: @dataclass(frozen=True, slots=True)
  318: class EclTraceRow:
  319:     """One physics tick of one agent's embodiment trace, with move provenance.
  320: 
  321:     Kinematic fields (``x``/``y``/``z``/``yaw``/``pitch``/``zone``) come from the
  322:     world seam's ``ecl_trace_sink`` primitives; the axis fields the closure binds
  323:     (``run_id`` / ``agent_tick`` / ``order_slot``, distinct from the 30 Hz
  324:     ``physics_tick_index``) satisfy AC3's forward-compatible log slots. The
  325:     ``move_*`` fields join in the driving cognition tick's
  326:     :class:`EclDestination` candidate-selection trail (``None`` on a window whose
  327:     plan did not move), so the trace records the frozen transform's *inputs* 窶・    never an absolute-target replay 窶・and the continuity gate's causal ablation
  328:     actually bites (design ﾂｧ隲也せ4). Design-copied from
  329:     ``evidence.d0_substrate.stub.TraceRow`` (copied, not imported).
  330:     """
  331: 
  332:     run_id: str
  333:     agent_id: str
  334:     physics_tick_index: int
  335:     agent_tick: int
  336:     order_slot: int
  337:     x: float
  338:     y: float
  339:     z: float
  340:     yaw: float
  341:     pitch: float
  342:     zone: Zone
  343:     resolved_from: str | None
  344:     move_centroid: tuple[float, float] | None
  345:     move_provenance: tuple[str, ...] | None
  346:     move_jitter: tuple[float, float] | None
  347:     move_pre_clamp: tuple[float, float] | None
  348:     move_post_clamp: tuple[float, float] | None
  349:     move_clamp_fired: bool | None
  350: 
  351: 
  352: # The 6-decimal float quantisation ``handoff.CANONICAL_FLOAT_DECIMALS`` advertises.
  353: # Inlined (not imported) because ``handoff`` imports ``loop`` 窶・sharing a helper
  354: # would create an import cycle; ``test_ecl_trace_checksum_canonical_rules`` pins
  355: # that this value matches ``handoff.CANONICAL_JSON_RULES`` so it cannot drift.
  356: _TRACE_FLOAT_DECIMALS: Final[int] = 6
  357: 
  358: 
  359: def _q(value: float) -> float:
  360:     """Quantise one float to :data:`_TRACE_FLOAT_DECIMALS` decimals (platform-safe)."""
  361:     return round(value, _TRACE_FLOAT_DECIMALS)
  362: 
  363: 
  364: def _pair_or_none(value: tuple[float, float] | None) -> list[float] | None:
  365:     return [_q(value[0]), _q(value[1])] if value is not None else None
  366: 
  367: 
  368: def ecl_trace_checksum(rows: Sequence[EclTraceRow]) -> str:
  369:     """SHA-256 over the canonical-serialised trace 窶・the replay checksum (ﾂｧ隲也せ3).
  370: 
  371:     Design-copied from ``evidence.d0_substrate.stub.trace_checksum`` (copied, not
  372:     imported): a stable JSON projection so a byte-identical re-run yields a
  373:     byte-identical digest. This proves *reproducibility*; it is not a metric,
  374:     floor, or verdict (measurement-line non-re-entry, design ﾂｧ隲也せ4).
  375: 
  376:     The ``json.dumps`` canonicalisation matches ``handoff.CANONICAL_JSON_RULES``
  377:     exactly (``sort_keys=True`` + compact ``separators`` + ``ensure_ascii=False`` +
  378:     ``allow_nan=False`` + 6-decimal float quantisation) so a consumer recomputing
  379:     the digest under the advertised rules gets the same bytes (Codex MEDIUM-1).
  380:     Every float in the projection is rounded to 6 decimals (``_q``) 窶・the same
  381:     quantisation ``handoff.canonical_dumps`` applies via ``_quantize_floats`` 窶・    which absorbs the sub-ULP cross-platform ``libm`` drift (frozen ``disc_jitter``
  382:     ``cos``/``sin``, max abs 8.88e-16) that would otherwise diverge the golden
  383:     checksum between Windows (UCRT) and Linux (glibc/CI). ``handoff.canonical_dumps``
  384:     is not imported: ``handoff`` imports ``loop``, so the rules are inlined here to
  385:     avoid the cycle, and ``test_ecl_trace_checksum_canonical_rules`` pins that the
  386:     two inlined copies produce identical digests so they cannot drift (CR-M2). A
  387:     non-finite float raises (``allow_nan=False``) 窶・a Stop condition, not a
  388:     silently-hashed value (design ﾂｧ隲也せ3).
  389:     """
  390:     canonical = [
  391:         {
  392:             "run_id": r.run_id,
  393:             "agent_id": r.agent_id,
  394:             "physics_tick_index": r.physics_tick_index,
  395:             "agent_tick": r.agent_tick,
  396:             "order_slot": r.order_slot,
  397:             "x": _q(r.x),
  398:             "y": _q(r.y),
  399:             "z": _q(r.z),
  400:             "yaw": _q(r.yaw),
  401:             "pitch": _q(r.pitch),
  402:             "zone": r.zone.value,
  403:             "resolved_from": r.resolved_from,
  404:             "move_centroid": _pair_or_none(r.move_centroid),
  405:             "move_provenance": (
  406:                 list(r.move_provenance) if r.move_provenance is not None else None
  407:             ),
  408:             "move_jitter": _pair_or_none(r.move_jitter),
  409:             "move_pre_clamp": _pair_or_none(r.move_pre_clamp),
  410:             "move_post_clamp": _pair_or_none(r.move_post_clamp),
  411:             "move_clamp_fired": r.move_clamp_fired,
  412:         }
  413:         for r in rows
  414:     ]
  415:     blob = json.dumps(
  416:         canonical,
  417:         sort_keys=True,
  418:         separators=(",", ":"),
  419:         ensure_ascii=False,
  420:         allow_nan=False,
  421:     ).encode("utf-8")
  422:     return hashlib.sha256(blob).hexdigest()
  423: 
  424: 
  425: # --------------------------------------------------------------------------- #
  426: # Run result
  427: # --------------------------------------------------------------------------- #
  428: 
  429: 
  430: @dataclass(frozen=True, slots=True)

hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$start=590;$end=700;$i=0; Get-Content src'"\\erre_sandbox\\integration\\embodied\\loop.py | ForEach-Object { "'$i++; if($i -ge $start -and $i -le $end){ '"'{0,5}: {1}' -f "'$i, $_ }}' in C:\ERRE-Sand_Box
 succeeded in 262ms:
  590:             )
  591:         )
  592: 
  593:     world = WorldRuntime(
  594:         cycle=cycle,
  595:         clock=clock,
  596:         physics_hz=30.0,
  597:         ecl_trace_sink=sink,
  598:     )
  599:     world.register_agent(agent_state, persona)
  600:     # ``_agents`` / ``_step_one`` / ``_consume_result`` are the world seam's cognition
  601:     # driver (Issue 003 owns them). The harness drives them directly rather than the
  602:     # phase-wheel ``_on_cognition_tick`` so every cognition tick fires unconditionally
  603:     # and the CycleResult (move provenance / envelopes) is captured 窶・no cycle/world
  604:     # edit, purely reading the public CycleResult the step returns.
  605:     rt = world._agents[agent_id]  # noqa: SLF001 窶・driving the I3 seam (sanctioned)
  606: 
  607:     obs_factory = observation_factory or _default_observation_factory(agent_id)
  608:     decisions: list[EclDecisionRecord] = []
  609: 
  610:     for agent_tick in range(n_cognition_ticks):
  611:         ctx.agent_tick = agent_tick
  612:         bias_slot.clear()
  613:         for obs in obs_factory(agent_tick):
  614:             world.inject_observation(agent_id, obs)
  615:         # Correlate this cognition tick with the LLM call(s) it served by the
  616:         # before/after ``used`` count, never a positional ``used[agent_tick]``
  617:         # (Codex M-2): a ``raised`` call is appended before it re-raises, so the
  618:         # stream stays tick-aligned but is no longer 1:1 with a positional index.
  619:         # Reflection is disabled in record mode, so each cognition tick issues
  620:         # exactly one action-LLM call (ok / unparseable / raised).
  621:         used_before = len(llm.used)
  622:         result = await world._step_one(rt)  # noqa: SLF001 窶・I3 seam driver
  623:         world._consume_result(rt, result)  # noqa: SLF001 窶・wires MoveMsg 竊・kinematics
  624:         ctx.move = result.ecl_destination
  625:         served = llm.used[used_before:]
  626:         if len(served) != 1:
  627:             msg = (
  628:                 f"ECL cognition tick {agent_tick} served {len(served)} action-LLM "
  629:                 "calls; expected exactly 1 (reflection disabled in record mode)"
  630:             )
  631:             raise EclReplayError(msg)
  632:         decisions.append(
  633:             _build_decision(
  634:                 agent_tick=agent_tick,
  635:                 call=served[0],
  636:                 result=result,
  637:                 bias_fired=bias_slot[0] if bias_slot else None,
  638:             )
  639:         )
  640:         for _ in range(physics_ticks_per_cognition):
  641:             await world._on_physics_tick()  # noqa: SLF001 窶・I3 seam driver
  642: 
  643:     frozen_rows = tuple(rows)
  644:     return EclRunResult(
  645:         run_id=run_id,
  646:         rows=frozen_rows,
  647:         decisions=tuple(decisions),
  648:         checksum=ecl_trace_checksum(frozen_rows),
  649:     )
  650: 
  651: 
  652: def _build_decision(
  653:     *,
  654:     agent_tick: int,
  655:     call: RecordedLlmCall,
  656:     result: CycleResult,
  657:     bias_fired: BiasFiredEvent | None,
  658: ) -> EclDecisionRecord:
  659:     """Assemble one tick's Plane 2 record from the served call + CycleResult."""
  660:     if call.outcome == "raised":
  661:         # A raised (OllamaUnavailableError) call is response-less: skip parsing
  662:         # entirely (``raw_response`` is ``""``) and record it as the ``raised``
  663:         # fallback branch (Codex HIGH-2). ``result.llm_fell_back`` is already True.
  664:         plan = None
  665:         llm_status = "raised"
  666:     else:
  667:         plan = parse_llm_plan(call.raw_response)
  668:         llm_status = "ok" if not result.llm_fell_back else "fell_back"
  669:         if plan is None:
  670:             llm_status = "unparseable"
  671:     envelope_provenance = tuple(env.model_dump_json() for env in result.envelopes)
  672:     return EclDecisionRecord(
  673:         agent_tick=agent_tick,
  674:         call=call,
  675:         plan=plan,
  676:         plan_schema_version=SCHEMA_VERSION,
  677:         llm_fell_back=result.llm_fell_back,
  678:         llm_status=llm_status,
  679:         bias_fired=bias_fired,
  680:         move_decision=result.ecl_destination,
  681:         envelope_provenance=envelope_provenance,
  682:     )
  683: 
  684: 
  685: __all__ = [
  686:     "DEFAULT_PHYSICS_TICKS_PER_COGNITION",
  687:     "GOLDEN_COGNITION_TICKS",
  688:     "EclDecisionRecord",
  689:     "EclReplayError",
  690:     "EclRunResult",
  691:     "EclTraceRow",
  692:     "RecordReplayChatClient",
  693:     "RecordedLlmCall",
  694:     "ecl_trace_checksum",
  695:     "replay_client_from",
  696:     "run_ecl_loop",
  697: ]

codex
現時点で一つ大きい穴が見えています: capture 時は manifest に observables overlay を足していますが、verify 側は manifest 自体を re-render 比較していません。committed artifact 全体の O3b として成立しているかを、artifact 実体でも確認します。
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Raw experiments\\20260706-ecl-v0-live-capture\\repro.sh" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Raw experiments\\20260706-ecl-v0-live-capture\\run.sh" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Raw experiments\\20260706-ecl-v0-live-capture\\artifacts\\manifest.json" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-Content -Raw -Encoding UTF8 experiments\\20260706-ecl-v0-live-capture\\env.md" in C:\ERRE-Sand_Box
 succeeded in 286ms:
#!/usr/bin/env bash
# ECL v0 sealed live run (Issue 003) 窶・first-contact capture on G-GEAR.
# Requires live Ollama (qwen3:8b). One-shot sealed run; artifacts/ is committed.
# Replay/CI reproduction is Ollama-free via repro.sh (D-4).
set -euo pipefail
cd "$(dirname "$0")/../.."

python scripts/ecl_v0_live_capture.py --capture \
  --run-id ecl-v0-live-capture --seed 0 \
  --n-cognition-ticks 32 --physics-ticks-per-cognition 20 \
  --qwen3-model-digest 500a1f067a9f7826 \
  --ollama-version 0.31.1 \
  --vram-gb 16 \
  --uv-lock-sha256 9cc70f9dc5d61f6c


 succeeded in 311ms:
# env — ECL v0 sealed live run (Issue 003, first-contact)

## 実行環境 (G-GEAR)
- machine: G-GEAR (Windows 11、本作業ディレクトリ = 実行機)
- OS: Windows 11 (bake side = UCRT libm)
- Ollama: 0.31.1 (http://127.0.0.1:11434)
- model: qwen3:8b (digest 500a1f067a9f7826、5.2 GB)、**think=False** (ThinkOffChatClient wrapper、Codex HIGH-1)
- embedding: constant-vector mock (D-4、minimal reality surface = live は action LLM chat のみ、real
  nomic-embed-text 不使用)
- VRAM: 16 GB
- uv.lock sha256 (先頭): 9cc70f9dc5d61f6c
- 日時: 2026-07-06 20:51-20:53 JST

## 事前登録 protocol (sealed run 前固定、tune-to-pass 封鎖)
- N_cognition=32 (D-1) / persona=kant, 単一 agent (D-2) / seed=0 / physics 20/cognition = 640 physics row
- sampling = live cycle resolved を verbatim 記録 (D-3、think のみ False)
- 観測量 O1-O5、Done=O1∧O2∧O3a∧O3b (manifest observables overlay に pre-registered)

## 結果 (verdict = GO、construction validated)
| 観測量 | 結果 |
|---|---|
| **O1 完走** | ✅ 32 cognition × 20 physics = 640 row、例外なく完走 (exit 0) |
| **O2 replay 再現** | ✅ committed decisions のみ replay → checksum byte 一致 + inner_invocations==0 |
| **O3a cross-platform** | ✅ **WSL Linux (glibc) replay = Windows (UCRT) checksum** `a528d547…` byte 一致 (libm cos/sin drift を 6桁量子化が吸収) |
| **O3b cross-platform** | ✅ 同一 raw Plane2 → artifact re-render SHA が Linux/Windows 一致 |
| **Done=O1∧O2∧O3a∧O3b** | ✅ **HOLDS** |
| O5 parsed-history-dependent-action (annotation、非 gate) | **32/32 tick** で `llm_status==ok` ∧ `plan≠None` ∧ MoveMsg `resolved_from==memory_centroid` (first-contact 存在証明が ≥1 を大きく超過。think=False が load-bearing = 全 tick parseable) |
| O4 非縮退 (annotation、非 gate) | distinct destination_zone = 2 ({peripatos:28, study:4})、distinct move target = 32 (全 tick 相異) |

replay_checksum (authoritative) = `a528d5472c3fc1b939ab151e0bdb8089a23a8b5ae39b7b7961aeed91d94cc249`

## cross-platform 実測手順 (feedback_golden_crossplatform_float_drift)
1. Windows で `bash experiments/20260706-ecl-v0-live-capture/run.sh` → artifacts/ を bake (UCRT)。
2. WSL Linux venv (`uv pip install .`、glibc) で
   `python scripts/ecl_v0_live_capture.py --verify --artifact-dir experiments/20260706-ecl-v0-live-capture/artifacts`
   → replay checksum が Windows-baked と byte 一致 = **cross-platform hold 実測確認済**。
3. CI (GitHub Actions Linux) は Issue 004 の `test_ecl_live_golden.py` が committed live artifact を replay-verify
   (Ollama-free) するため、Linux CI 自体も cross-platform gate。

## 判定 (軸5 = GO)
Done (O1∧O2∧O3a∧O3b) HOLDS + O5=32/32 + O4 非縮退 → **GO (construction validated)**。ECL v0 organ が real
qwen3:8b で substrate を end-to-end 駆動し、captured Plane2 のみで cross-platform に deterministic replay。
**construction validation であって measurement verdict でない** (floor/landscape/verdict 非出力、holding 不可侵)。
次 primary = 候補 B (N体化) or C (measurement gate) を別 ADR で (arc-close 却下・holding 継続)。


 succeeded in 336ms:
{"artifacts":{"decisions.jsonl":{"sha256":"8bb7f9a31567520b574d425f5ccb6df90fe25ca912481b2d9650ac731c707e8b"},"ecl_trace.jsonl":{"sha256":"5c166b99ee93f57e56cc364023fa03d1c3c7dcd9fc80f941ccfaca952137931a"},"envelope_stream.jsonl":{"sha256":"14651129cdd112c2eee93f3bff31ef319079f484d5b00f06c0f3a510a45c8d96"}},"canonical_json_rules":{"allow_nan":false,"ensure_ascii":false,"float_quantize_decimals":6,"float_repr":"python repr (shortest round-trip IEEE-754 double)","newline":"\\n (one JSON object per line, trailing newline)","separators":[",",":"],"sort_keys":true},"coordinate_convention":{"ground_plane":"XZ","pitch":"radians (0.0 level)","units":"meters","up_axis":"Y","yaw":"atan2(dz, dx)"},"determinism_checklist":["Plane 1 pinned: fixed retrieval clock, tick-derived memory id/ts, named RNG substreams (random.Random(str) 竊・sha512 seed, PYTHONHASHSEED-independent)","Plane 2 pinned: every action-LLM call recorded; replay injects recorded responses and calls no LLM (inner_invocations == 0)","reflection disabled in record mode (second LLM non-determinism source closed)","retrieval tie-break total order (-strength, created_at, id); k_world=0; mark_recalled=False","envelope sent_at pinned to the record-mode clock","ERRE_ZONE_BIAS_P pinned via env_pins (bias non-firing but pinned to close an un-pinned non-determinism source)","authoritative reproducibility digest = ecl_trace_checksum over EclTraceRow (design ﾂｧ隲也せ3); NOT a metric/floor/verdict. It canonicalises under the same rules as CANONICAL_JSON_RULES (sort_keys + compact separators + ensure_ascii=False + allow_nan=False + 6-decimal float quantisation), so a consumer recomputing the digest under the advertised rules gets identical bytes; a non-finite trace raises (allow_nan=False) 窶・a Stop condition, not a silently-hashed value","cross-platform libm float drift is absorbed by quantising every emitted float to 6 decimals (round is platform-independent), not silently tolerated"],"env_pins":{"ERRE_ZONE_BIAS_P":"0.2","godot":"4.6 (consumer; not required to generate)","ollama_version":"0.31.1","packages":{"httpx":"0.28.1","pydantic":"2.13.2"},"python":"3.11.15","qwen3_model_digest":"500a1f067a9f7826","resolved_sampling":{"repeat_penalty":1.0,"temperature":0.7,"top_p":0.9},"think":false,"uv_lock_sha256":"9cc70f9dc5d61f6c","vram_gb":16.0},"envelope_stream_kinds":["speech","move","animation"],"expected_envelope_ordering":"sort ascending by (order_slot, agent_tick, seq)","godot_headless_command":"godot --headless --path godot_project --script res://scripts/dev/EclReplayPlayer.gd -- --manifest=<abs>/manifest.json --stream=<abs>/envelope_stream.jsonl","manifest_version":"ecl-v0-handoff-2","observables":{"O1":"N cognition ticks x M physics ticks completed against a live Ollama qwen3:8b with no exception (full completion)","O2":"replaying from the captured decisions alone reproduces a byte-identical ecl_trace_checksum with inner_invocations==0","O3a":"the same committed decisions.jsonl replays to the same checksum with inner_invocations==0 on both WSL Linux (glibc) and Windows (UCRT)","O3b":"the same raw Plane 2 re-renders the full artifact set to the same SHA-256 set on both platforms (6-decimal float quantisation absorbs libm drift)","O4":"non-degeneracy: a pure boolean count (never a divergence/floor statistic) of whether the LLM chose >1 distinct destination zone and/or the resolver produced >1 distinct move target across the run (annotation, not a Done gate)","O5":"parsed-history-dependent-action count (D-5 refinement, annotation, not a hard green gate): the tick count where llm_status=='ok' and plan is not None and the MoveMsg resolved_from=='memory_centroid'; >= 1 tick is the first-contact existence proof","done_formula":"O1竏ｧO2竏ｧO3a竏ｧO3b","o5_min_ticks":1},"replay_checksum":"a528d5472c3fc1b939ab151e0bdb8089a23a8b5ae39b7b7961aeed91d94cc249","replay_checksum_algorithm":"sha256","replay_checksum_json_rules":{"allow_nan":false,"ensure_ascii":false,"float_quantize_decimals":6,"separators":[",",":"],"sort_keys":true},"run":{"agent_ids":["a_kant_001"],"base_ts":"2026-07-06T11:51:25.585518+00:00","cognition_ticks":32,"k_ecl":8,"physics_ticks_per_cognition":20,"retrieval_now":"2026-07-06T11:51:25.585518+00:00","run_id":"ecl-v0-live-capture","seed":0,"world_tick_count":640},"schema_version":"0.11.0-m13es3","tick_mapping":{"agent_tick":"cognition counter (one CognitionCycle.step per tick); physics_ticks_per_cognition physics ticks per cognition window","axis_separation":"physics_tick_index and agent_tick are distinct axes; a MoveMsg target is recorded on the agent_tick axis, kinematics on the physics_tick_index axis","physics_tick_index":"30 Hz world clock; ecl_trace_sink fires after step_kinematics on each _on_physics_tick (Codex MEDIUM-2)"}}


 succeeded in 365ms:
#!/usr/bin/env bash
# ECL v0 live-capture 窶・1-command Ollama-free replay-verify (Issue 002,
# loop/20260706-ecl-v0-live-run/issues/002-replay-verify-apparatus.md, I4-G5).
#
# This apparatus reproduces a committed artifact bundle's ecl_trace_checksum
# from decisions.jsonl alone (O3a, inner_invocations == 0) and re-renders the
# full artifact set from the same replayed result to check every per-artifact
# SHA-256 (O3b) 窶・see scripts/ecl_v0_live_capture.py's `verify()`.
#
# Issue 003 (sealed live run) / Issue 004 (final swap) will populate
# experiments/20260706-ecl-v0-live-capture/artifacts/ with the committed
# sealed-run artifact. Until that lands this script falls back to the
# synthetic golden template (tests/fixtures/ecl_v0_golden/), so the
# 1-command contract exists today and exits 0 (Issue 002 scope).
#
# Usage:
#   bash experiments/20260706-ecl-v0-live-capture/repro.sh [artifact_dir]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEFAULT_ARTIFACT_DIR="${REPO_ROOT}/experiments/20260706-ecl-v0-live-capture/artifacts"
TEMPLATE_ARTIFACT_DIR="${REPO_ROOT}/tests/fixtures/ecl_v0_golden"

ARTIFACT_DIR="${1:-${DEFAULT_ARTIFACT_DIR}}"

if [ ! -f "${ARTIFACT_DIR}/manifest.json" ]; then
  echo "[repro] no committed live artifact at ${ARTIFACT_DIR} yet (Issue 003/004)"
  echo "[repro] falling back to the synthetic golden template: ${TEMPLATE_ARTIFACT_DIR}"
  ARTIFACT_DIR="${TEMPLATE_ARTIFACT_DIR}"
fi

if [ -x "${REPO_ROOT}/.venv/Scripts/python.exe" ]; then
  PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
elif [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python"
else
  PYTHON="python3"
fi

echo "[repro] Ollama-free replay-verify: ${ARTIFACT_DIR}"
"${PYTHON}" "${REPO_ROOT}/scripts/ecl_v0_live_capture.py" --verify --artifact-dir "${ARTIFACT_DIR}"


hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
from pathlib import Path
text = Path('src/erre_sandbox/integration/embodied/live.py').read_text(encoding='utf-8')
for line in text.splitlines():
    if 'LIVE_DONE_FORMULA' in line and '=' in line:
        print(ascii(line))
manifest = Path('experiments/20260706-ecl-v0-live-capture/artifacts/manifest.json').read_text(encoding='utf-8')
idx = manifest.index('done_formula')
print(ascii(manifest[idx:idx+80]))
'@ | python -" in C:\ERRE-Sand_Box
 succeeded in 287ms:
'LIVE_DONE_FORMULA: Final[str] = "O1\u2227O2\u2227O3a\u2227O3b"'
'done_formula":"O1\u2227O2\u2227O3a\u2227O3b","o5_min_ticks":1},"replay_checksum":"a528d5472c3fc'

hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
from pathlib import Path
for path in ['src/erre_sandbox/integration/embodied/live.py','scripts/ecl_v0_live_capture.py','tests/test_integration/test_ecl_live_capture.py','tests/test_integration/test_ecl_live_golden.py']:
    text = Path(path).read_text(encoding='utf-8')
    print(path, 'replacement?', '\\ufffd' in text, 'moji_count', text.count('竏'), text.count('窶'))
'@ | python -" in C:\ERRE-Sand_Box
 succeeded in 274ms:
src/erre_sandbox/integration/embodied/live.py replacement? False moji_count 0 0
scripts/ecl_v0_live_capture.py replacement? False moji_count 0 0
tests/test_integration/test_ecl_live_capture.py replacement? False moji_count 0 0
tests/test_integration/test_ecl_live_golden.py replacement? False moji_count 0 0

codex
PowerShell 表示の文字化けに見えた `∧` などは UTF-8 上は正常でした。次に focused tests を実行して、レビュー指摘が実行失敗とは別の仕様穴かを切り分けます。
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'uv run pytest tests/test_integration/test_ecl_live_capture.py tests/test_integration/test_ecl_live_golden.py' in C:\ERRE-Sand_Box
2026-07-06T12:13:25.587577Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.3 seconds
Output:
error: Failed to initialize cache at `C:\Users\johnd\AppData\Local\uv\cache`
  Caused by: failed to open file `C:\Users\johnd\AppData\Local\uv\cache\sdists-v9\.git`: アクセスが拒否されました。 (os error 5)

 exited 1 in 329ms:
error: Failed to initialize cache at `C:\Users\johnd\AppData\Local\uv\cache`
  Caused by: failed to open file `C:\Users\johnd\AppData\Local\uv\cache\sdists-v9\.git`: アクセスが拒否されました。 (os error 5)

codex
`uv run` はユーザー領域の uv cache 権限で止まりました。ネットワークや権限変更はできないので、既存 `.venv` の Python があればそちらで同じ focused tests を回します。
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Test-Path .venv\\Scripts\\python.exe) { .\\.venv\\Scripts\\python.exe -m pytest tests\\test_integration\\test_ecl_live_capture.py tests\\test_integration\\test_ecl_live_golden.py } else { python -m pytest tests\\test_integration\\test_ecl_live_capture.py tests\\test_integration\\test_ecl_live_golden.py }" in C:\ERRE-Sand_Box
2026-07-06T12:13:32.300712Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.5 seconds
Output:
ImportError while loading conftest 'C:\ERRE-Sand_Box\tests\conftest.py'.
tests\conftest.py:16: in <module>
    from erre_sandbox.schemas import (
src\erre_sandbox\__init__.py:10: in <module>
    from erre_sandbox.schemas import (
src\erre_sandbox\schemas.py:35: in <module>
    from pydantic import BaseModel, ConfigDict, Field
.venv\Lib\site-packages\pydantic\__init__.py:5: in <module>
    ???
.venv\Lib\site-packages\pydantic\_migration.py:4: in <module>
    ???
.venv\Lib\site-packages\pydantic\warnings.py:5: in <module>
    ???
.venv\Lib\site-packages\pydantic\version.py:7: in <module>
    ???
.venv\Lib\site-packages\pydantic_core\__init__.py:8: in <module>
    ???
E   ImportError: DLL load failed while importing _pydantic_core: アクセスが拒否されました。

 exited 1 in 484ms:
ImportError while loading conftest 'C:\ERRE-Sand_Box\tests\conftest.py'.
tests\conftest.py:16: in <module>
    from erre_sandbox.schemas import (
src\erre_sandbox\__init__.py:10: in <module>
    from erre_sandbox.schemas import (
src\erre_sandbox\schemas.py:35: in <module>
    from pydantic import BaseModel, ConfigDict, Field
.venv\Lib\site-packages\pydantic\__init__.py:5: in <module>
    ???
.venv\Lib\site-packages\pydantic\_migration.py:4: in <module>
    ???
.venv\Lib\site-packages\pydantic\warnings.py:5: in <module>
    ???
.venv\Lib\site-packages\pydantic\version.py:7: in <module>
    ???
.venv\Lib\site-packages\pydantic_core\__init__.py:8: in <module>
    ???
E   ImportError: DLL load failed while importing _pydantic_core: アクセスが拒否されました。

hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff --check main..feat/ecl-v0-live-run -- src/ scripts/ tests/' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"hard_gate|o5|O5|parsed|memory_centroid|distinct|destination_zone|GO|construction\" src\\erre_sandbox\\integration\\embodied\\live.py scripts\\ecl_v0_live_capture.py tests\\test_integration\\test_ecl_live_capture.py tests\\test_integration\\test_ecl_live_golden.py" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"evidence|spdm|runningness|floor|landscape|verdict|jaccard|divergence|r_min\" src\\erre_sandbox\\integration\\embodied\\live.py scripts\\ecl_v0_live_capture.py tests\\test_integration\\test_ecl_live_capture.py tests\\test_integration\\test_ecl_live_golden.py" in C:\ERRE-Sand_Box
hook: PreToolUse
 succeeded in 287ms:
 succeeded in 305ms:
tests\test_integration\test_ecl_live_capture.py:16:* **I2-G3** the manifest observables overlay pre-registers O1-O5 +
tests\test_integration\test_ecl_live_capture.py:17:  ``done_formula`` + ``o5_min_ticks`` as sealed-run-before constants.
tests\test_integration\test_ecl_live_capture.py:41:    LIVE_O5_MIN_TICKS,
tests\test_integration\test_ecl_live_capture.py:64:        "destination_zone": "peripatos",
tests\test_integration\test_ecl_live_capture.py:262:    assert LIVE_O5_MIN_TICKS == 1
tests\test_integration\test_ecl_live_capture.py:314:# I2-G3 — manifest observables overlay pre-registers O1-O5 (tune-to-pass closed)
tests\test_integration\test_ecl_live_capture.py:339:    for key in ("O1", "O2", "O3a", "O3b", "O4", "O5"):
tests\test_integration\test_ecl_live_capture.py:344:    assert observables["o5_min_ticks"] == 1
tests\test_integration\test_ecl_live_golden.py:10:SHA-256 (O3b). O5 (D-5 refinement) is an **annotation** count, never a hard
tests\test_integration\test_ecl_live_golden.py:11:green gate (Codex TASK-PRE HIGH-2 — an autonomous O5 gate would tune-to-pass
tests\test_integration\test_ecl_live_golden.py:17:fixture path is the single module constant :data:`_GOLDEN_DIR`; Issue 004
tests\test_integration\test_ecl_live_golden.py:24:This is a *construction* apparatus, **NOT a measurement line**. It imports no
tests\test_integration\test_ecl_live_golden.py:43:from erre_sandbox.integration.embodied.live import LIVE_O5_MIN_TICKS
tests\test_integration\test_ecl_live_golden.py:55:_GOLDEN_DIR = (
tests\test_integration\test_ecl_live_golden.py:65:    vec = [handoff.GOLDEN_EMBED_VALUE] * EmbeddingClient.DEFAULT_DIM
tests\test_integration\test_ecl_live_golden.py:92:    generalises unchanged once Issue 004 repoints :data:`_GOLDEN_DIR` at a live
tests\test_integration\test_ecl_live_golden.py:124:    manifest = json.loads((_GOLDEN_DIR / "manifest.json").read_text(encoding="utf-8"))
tests\test_integration\test_ecl_live_golden.py:125:    decisions_text = (_GOLDEN_DIR / "decisions.jsonl").read_text(encoding="utf-8")
tests\test_integration\test_ecl_live_golden.py:126:    trace_text = (_GOLDEN_DIR / "ecl_trace.jsonl").read_text(encoding="utf-8")
tests\test_integration\test_ecl_live_golden.py:127:    envelope_text = (_GOLDEN_DIR / "envelope_stream.jsonl").read_text(encoding="utf-8")
tests\test_integration\test_ecl_live_golden.py:146:        "O3a: replay-only reconstruction must reproduce the committed "
tests\test_integration\test_ecl_live_golden.py:189:# I4-G3 / O5 — parsed-history-dependent-action count (annotation, not a gate)
tests\test_integration\test_ecl_live_golden.py:193:def test_live_golden_parsed_history_dependent_action(tmp_path: Path) -> None:
tests\test_integration\test_ecl_live_golden.py:194:    """Count + record O5 ticks — a construction-validity annotation, never a
tests\test_integration\test_ecl_live_golden.py:197:    O5 = ``llm_status == "ok"`` and ``plan is not None`` and the MoveMsg
tests\test_integration\test_ecl_live_golden.py:198:    ``resolved_from == "memory_centroid"``: the tick is judged to have parsed a
tests\test_integration\test_ecl_live_golden.py:201:    construction-validity branch for human judgement, Execution Result), not a
tests\test_integration\test_ecl_live_golden.py:204:    LIVE_O5_MIN_TICKS``.
tests\test_integration\test_ecl_live_golden.py:217:        and d["move_decision"]["resolved_from"] == "memory_centroid"
tests\test_integration\test_ecl_live_golden.py:221:        "o5_parsed_history_dependent_action_count": count,
tests\test_integration\test_ecl_live_golden.py:222:        "o5_min_ticks_first_contact_threshold": LIVE_O5_MIN_TICKS,
tests\test_integration\test_ecl_live_golden.py:223:        "hard_gate": False,
tests\test_integration\test_ecl_live_golden.py:226:            "construction-validity branch, not an autonomous pass/fail"
tests\test_integration\test_ecl_live_golden.py:229:    annotation_path = tmp_path / "o5_annotation.json"
tests\test_integration\test_ecl_live_golden.py:233:    o5_count = recorded_annotation["o5_parsed_history_dependent_action_count"]
tests\test_integration\test_ecl_live_golden.py:234:    assert isinstance(o5_count, int)
tests\test_integration\test_ecl_live_golden.py:235:    assert o5_count >= 0
tests\test_integration\test_ecl_live_golden.py:236:    assert recorded_annotation["hard_gate"] is False
scripts\ecl_v0_live_capture.py:38:/ ``live.py``). This is a *construction* apparatus, **NOT a measurement line**.
src\erre_sandbox\integration\embodied\live.py:30:/ :data:`LIVE_EMBEDDING_MODE` / :data:`LIVE_O5_MIN_TICKS`.
src\erre_sandbox\integration\embodied\live.py:38:O1-O5 pre-registration, ``done_formula`` and ``o5_min_ticks``, attached as a
src\erre_sandbox\integration\embodied\live.py:43:``handoff.py``). This is a *construction* apparatus, **NOT a measurement
src\erre_sandbox\integration\embodied\live.py:46:judgement statistic. O4/O5 are pre-registered *annotation* text only in this
src\erre_sandbox\integration\embodied\live.py:81:golden to construction-observe a longer-horizon completion. Fixed before the
src\erre_sandbox\integration\embodied\live.py:94:LIVE_O5_MIN_TICKS: Final[int] = 1
src\erre_sandbox\integration\embodied\live.py:95:"""Minimum tick count for the O5 parsed-history-dependent-action annotation
src\erre_sandbox\integration\embodied\live.py:97:``resolved_from=="memory_centroid"`` on at least this many ticks is the
src\erre_sandbox\integration\embodied\live.py:98:first-contact existence proof. **Not a hard green gate** — D-5 records O5 as a
src\erre_sandbox\integration\embodied\live.py:99:count annotation with a human-judgement construction-validity branch, not an
src\erre_sandbox\integration\embodied\live.py:100:autonomous pass/fail (Codex TASK-PRE HIGH-2: an autonomous gate on O5 would
src\erre_sandbox\integration\embodied\live.py:105:conjunction of the four reproducibility observables. O4/O5 are
src\erre_sandbox\integration\embodied\live.py:264:        "statistic) of whether the LLM chose >1 distinct destination zone "
src\erre_sandbox\integration\embodied\live.py:265:        "and/or the resolver produced >1 distinct move target across the run "
src\erre_sandbox\integration\embodied\live.py:268:    "O5": (
src\erre_sandbox\integration\embodied\live.py:269:        "parsed-history-dependent-action count (D-5 refinement, annotation, "
src\erre_sandbox\integration\embodied\live.py:271:        "plan is not None and the MoveMsg resolved_from=='memory_centroid'; "
src\erre_sandbox\integration\embodied\live.py:272:        f">= {LIVE_O5_MIN_TICKS} tick is the first-contact existence proof"
src\erre_sandbox\integration\embodied\live.py:275:    "o5_min_ticks": LIVE_O5_MIN_TICKS,
src\erre_sandbox\integration\embodied\live.py:278:closure, Codex TASK-PRE HIGH-1): the O1-O5 definitions design-final.md
src\erre_sandbox\integration\embodied\live.py:280:``o5_min_ticks`` threshold. Frozen at import time (not derived from any run
src\erre_sandbox\integration\embodied\live.py:307:    "LIVE_O5_MIN_TICKS",

 succeeded in 331ms:
tests\test_integration\test_ecl_live_golden.py:25:``evidence`` / ``spdm`` / ``runningness`` machinery and computes/emits no
tests\test_integration\test_ecl_live_golden.py:26:floor / landscape / verdict / divergence statistic —
tests\test_integration\test_ecl_live_golden.py:248:_BANNED_IMPORT_PREFIX = ("erre_sandbox.evidence",)
tests\test_integration\test_ecl_live_golden.py:249:_BANNED_IMPORT_SUB = ("spdm", "runningness")
tests\test_integration\test_ecl_live_golden.py:250:_BANNED_IDENTIFIER = ("floor", "landscape", "verdict", "jaccard", "divergence", "r_min")
tests\test_integration\test_ecl_live_golden.py:278:    """The replay-verify apparatus computes/emits no floor/landscape/verdict.
tests\test_integration\test_ecl_live_capture.py:358:    banned_prefix = ("erre_sandbox.evidence",)
tests\test_integration\test_ecl_live_capture.py:359:    banned_sub = ("spdm", "runningness")
tests\test_integration\test_ecl_live_capture.py:383:    banned_ident = ("floor", "landscape", "verdict", "jaccard", "divergence", "r_min")
tests\test_integration\test_ecl_live_capture.py:391:    """``live.py`` imports no measurement machinery and defines no floor /
tests\test_integration\test_ecl_live_capture.py:392:    landscape / verdict output identifier (design §論点4, mirrors the
scripts\ecl_v0_live_capture.py:39:It imports no ``evidence`` / ``spdm`` / ``runningness`` machinery and
scripts\ecl_v0_live_capture.py:40:computes/emits no floor / landscape / verdict statistic.
scripts\ecl_v0_live_capture.py:199:    floor / landscape / verdict / divergence statistic (measurement-line
src\erre_sandbox\integration\embodied\live.py:44:line — final judgement は holding**. It imports no ``evidence`` / ``spdm`` /
src\erre_sandbox\integration\embodied\live.py:45:``runningness`` machinery and computes/emits no floor / landscape / final
src\erre_sandbox\integration\embodied\live.py:263:        "non-degeneracy: a pure boolean count (never a divergence/floor "

hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff --numstat main..feat/ecl-v0-live-run -- src/ scripts/ tests/' in C:\ERRE-Sand_Box
 succeeded in 237ms:
330	0	scripts/ecl_v0_live_capture.py
315	0	src/erre_sandbox/integration/embodied/live.py
395	0	tests/test_integration/test_ecl_live_capture.py
286	0	tests/test_integration/test_ecl_live_golden.py

codex
追加された production file は `src/erre_sandbox/` 配下なので、依存方向と GPL/cloud API 禁止の project Skill も確認します。review なので変更はしませんが、import 境界の事実確認に使います。
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-Content -Raw -Encoding UTF8 C:\\ERRE-Sand_Box\\.agents\\skills\\architecture-rules\\SKILL.md" in C:\ERRE-Sand_Box
 succeeded in 246ms:
---
name: architecture-rules
description: >
  レイヤー依存方向・インポート制約・GPL/クラウド API 禁止ルール。
  src/erre_sandbox/ 配下に新しいファイルを追加する・インポートを変更する・
  新しい依存ライブラリを追加する時に必須参照。
  schemas.py / inference/ / memory/ / cognition/ / world/ / ui/ / erre/
  のどのモジュールにコードを置くか判断する時、
  import 文が依存方向に違反していないか確認する時、
  pip install / uv add でライブラリを追加する時に自動召喚される。
  GPL ライブラリ (bpy 等) を src/erre_sandbox/ に import する禁止も含む。
---

# Architecture Rules

## このスキルの目的

ERRE-Sandbox のアーキテクチャは 2 拠点 (G-GEAR + MacBook) × 5 レイヤー構成。
インポートの依存方向を守ることで、将来のバックエンド差し替え (Qdrant、gRPC 等) を
最小の変更で実現できるようにする。また、GPL ライブラリとクラウド API の混入を防ぐ。

## レイヤー依存方向（絶対厳守）

```
world/ → cognition/ → inference/
                    → memory/
                          ↓
ui/ ──────────→ schemas.py ← (全モジュールが参照)
```

| モジュール | 依存先 | 依存禁止 |
|---|---|---|
| `schemas.py` | なし (最下層) | すべての src モジュール |
| `inference/` | `schemas.py` のみ | `memory/`, `cognition/`, `world/`, `ui/` |
| `memory/` | `schemas.py` のみ | `inference/`, `cognition/`, `world/`, `ui/` |
| `cognition/` | `inference/`, `memory/`, `schemas.py`, `erre/` | `world/`, `ui/` |
| `world/` | `cognition/`, `schemas.py` | `ui/`, `erre/` |
| `ui/` | `schemas.py` のみ | `inference/`, `memory/`, `cognition/`, `world/` |
| `erre/` | `schemas.py`, `inference/`, `memory/` | `cognition/`, `world/`, `ui/` |

### 依存方向の確認方法

```bash
# ui/ が inference/ を import していないか確認
grep -r "from erre_sandbox.inference" src/erre_sandbox/ui/
grep -r "from erre_sandbox.memory"    src/erre_sandbox/ui/

# schemas.py が他モジュールを import していないか確認
grep "from erre_sandbox\." src/erre_sandbox/schemas.py
```

## 絶対禁止ルール

### 禁止 1: GPL ライブラリを src/erre_sandbox/ に import

Blender の `bpy` は GPL-2+ のため、import するコードが GPL 派生物になる。
Apache-2.0 OR MIT デュアルライセンスと矛盾するため **絶対に混入させない**。

```python
# ❌ 絶対禁止
import bpy                          # GPL viral — Apache/MIT と矛盾
from bpy.types import Object        # 同上
```

将来 Blender 連携が必要になった場合 → `erre-sandbox-blender/` を別パッケージ (GPL-3) で分離。

### 禁止 2: クラウド LLM API を必須依存にする

OpenAI / Anthropic / Google の API は予算ゼロ制約に反する。

```python
# ❌ 禁止
import openai                       # 有料 API
from anthropic import Anthropic     # 有料 API
```

ローカル推論 (SGLang / Ollama / llama.cpp) のみ使用。

### 禁止 3: ui/ から inference/ / memory/ を直接 import

UI は WebSocket 経由で G-GEAR と通信する。Python の import で直接呼ばない。

```python
# ❌ 禁止 — ui/ から memory/ を直接呼ぶ
from erre_sandbox.memory.store import MemoryStore  # ui/ 内に書いてはいけない

# ✅ 正しい — WebSocket 経由
from erre_sandbox.schemas import ControlEnvelope   # スキーマのみ OK
```

### 禁止 4: schemas.py から他の src モジュールを import

`schemas.py` は最下層。循環参照を防ぐために依存なしを厳守。

```python
# ❌ 禁止
from erre_sandbox.memory.store import MemoryStore  # schemas.py 内に書いてはいけない

# ✅ 正しい — 型ヒントのみなら TYPE_CHECKING で遅延
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from erre_sandbox.memory.store import MemoryStore
```

## 新しいファイルの配置判断フロー

```
新しい .py ファイルを作る
    │
    ├─ LLM 推論関連?           → inference/
    ├─ 記憶・検索・埋め込み?   → memory/
    ├─ 認知サイクル・反省?     → cognition/
    ├─ ワールド・物理・ゾーン? → world/
    ├─ WebSocket クライアント・Godot 連携? → ui/
    ├─ ERRE パイプライン DSL?  → erre/
    └─ Pydantic スキーマ定義?  → schemas.py に追記 (ファイルは作らない)
```

## 依存ライブラリ追加の基準

新しいライブラリを `uv add` する前に全項目確認:

- [ ] 既存の依存で代替できないか?
- [ ] ライセンスは Apache-2.0 / MIT / BSD と互換か? (**GPL は本体に入れない**)
- [ ] メンテナンスが活発か? (直近 6 ヶ月以内にリリースがあるか)
- [ ] セキュリティ脆弱性はないか?
- [ ] 予算ゼロに抵触しないか? (有料 SaaS の必須依存は不可)

## チェックリスト

- [ ] 新しいファイルが正しいレイヤー (`inference/`, `memory/` 等) に置かれているか
- [ ] インポートが依存方向に違反していないか (`grep` で確認)
- [ ] `schemas.py` から他の src モジュールを import していないか
- [ ] `ui/` から `inference/` や `memory/` を直接 import していないか
- [ ] GPL ライブラリが `src/erre_sandbox/` に入っていないか
- [ ] クラウド LLM API が必須依存になっていないか
- [ ] 新しい依存のライセンスが Apache-2.0/MIT/BSD と互換か

## 補足資料

- `decision-tree.md` — 「どのモジュールに書くべきか」の判断フロー詳細版

## 関連する他の Skill

- `python-standards` — インポート順序・相対 vs 絶対インポートのルール
- `implementation-workflow` — Step B (既存パターン調査) でこの Skill を参照
- `llm-inference` — inference/ 内のモデル設定と VRAM 管理
- `persona-erre` — ペルソナ YAML 設計と ERRE モード定義
- `godot-gdscript` — Godot シーン・GDScript のコーディング規約と WebSocket 通信
- `blender-pipeline` — Blender アセットパイプラインの GPL 分離の具体的手順


codex
レビュー対象は async resource close と pytest 側も含むので、該当する project standards も確認してから最終判断に入ります。
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-Content -Raw -Encoding UTF8 C:\\ERRE-Sand_Box\\.agents\\skills\\test-standards\\SKILL.md" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-Content -Raw -Encoding UTF8 C:\\ERRE-Sand_Box\\.agents\\skills\\python-standards\\SKILL.md" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-Content -Raw -Encoding UTF8 C:\\ERRE-Sand_Box\\.agents\\skills\\error-handling\\SKILL.md" in C:\ERRE-Sand_Box
 succeeded in 265ms:
---
name: error-handling
description: >
  asyncio を使ったエラーハンドリングとリトライ戦略。
  inference/ や memory/ や cognition/ のコードを書く・修正する時に必須参照。
  SGLang → Ollama フォールバックを実装する時、WebSocket の再接続ロジックを書く時、
  LLM 推論タイムアウトを処理する時、sqlite-vec の DB エラーを扱う時、
  asyncio.gather() で並列タスクの一部が失敗した場合の処理を書く時に自動召喚される。
  ollama_adapter.py / sglang_adapter.py / ws_client.py / store.py を変更する時は
  必ずこの Skill を参照すること。
---

# Error Handling

## このスキルの目的

ERRE-Sandbox は 30Hz の tick ループと 0.1Hz の認知ループを並列で走らせる。
どちらかのエラーで全体がクラッシュしないよう、エラーの種類ごとに
「無視・リトライ・フォールバック・停止」を使い分ける。
特に LLM 推論と WebSocket 通信は「外部システムの不安定性」を前提に設計する。

## エラーの分類と対応方針

| 種類 | 例 | 対応 |
|---|---|---|
| 一時的エラー | LLM タイムアウト、DB ロック競合 | 指数バックオフでリトライ |
| フォールバック可能 | SGLang 応答なし | Ollama にフォールバック |
| 接続断 | WebSocket 切断 | 自動再接続 |
| データ破損 | Pydantic ValidationError | ログ + デフォルト値で継続 |
| 致命的エラー | DB 書き込み失敗 (全エージェント) | ログ + シミュレーション停止 |

## ルール 1: LLM 推論 — SGLang → Ollama フォールバック

```python
# ✅ 良い例
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

async def generate(prompt: str, **kwargs: Any) -> dict[str, Any]:
    """LLM inference with automatic SGLang → Ollama fallback."""
    try:
        return await _sglang_generate(prompt, **kwargs)
    except (TimeoutError, ConnectionRefusedError, OSError) as e:
        logger.warning("SGLang unavailable (%s), falling back to Ollama", e)
        return await _ollama_generate(prompt, **kwargs)
```

```python
# ❌ 悪い例 — フォールバックなし
async def generate(prompt: str, **kwargs: Any) -> dict[str, Any]:
    return await _sglang_generate(prompt, **kwargs)  # SGLang が落ちたら即クラッシュ
```

## ルール 2: 指数バックオフ付きリトライ

一時的なエラー（タイムアウト、DB ロック）にはリトライを使う。
**上限回数と最大遅延を必ず設定する**（無限ループ防止）。

```python
# ✅ 良い例
import asyncio

async def retry_async(
    coro_fn,
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs,
):
    """Retry with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return await coro_fn(*args, **kwargs)
        except (TimeoutError, OSError) as e:
            if attempt == max_attempts - 1:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                "Attempt %d/%d failed: %s. Retrying in %.1fs",
                attempt + 1, max_attempts, e, delay
            )
            await asyncio.sleep(delay)

# 使用例
result = await retry_async(_ollama_generate, prompt, max_attempts=3)
```

## ルール 3: WebSocket — 自動再接続

Godot (MacBook) と G-GEAR の WebSocket 接続は一時切断が起こり得る。
切断イベントを検知して自動再接続する。

```python
# ✅ 良い例
import websockets
import asyncio

async def ws_client_with_reconnect(uri: str) -> None:
    """WebSocket client with automatic reconnect."""
    while True:
        try:
            async with websockets.connect(uri) as ws:
                logger.info("WebSocket connected: %s", uri)
                await handle_ws_messages(ws)
        except (websockets.ConnectionClosed, OSError) as e:
            logger.warning("WebSocket disconnected: %s. Reconnecting in 5s", e)
            await asyncio.sleep(5.0)
```

## ルール 4: asyncio.gather — 一部失敗を許容

認知サイクルでは複数エージェントを並列実行する。1体の失敗で全体を止めない。

```python
# ✅ 良い例
results = await asyncio.gather(
    *[agent.run_cycle() for agent in agents],
    return_exceptions=True,   # 例外を結果として受け取る
)

for agent, result in zip(agents, results):
    if isinstance(result, Exception):
        logger.error("Agent %s cycle failed: %s", agent.bio.name, result)
        # 失敗したエージェントはスキップしてシミュレーション継続
    else:
        await process_result(agent, result)
```

```python
# ❌ 悪い例 — 1体失敗で全体停止
results = await asyncio.gather(
    *[agent.run_cycle() for agent in agents],
    # return_exceptions=False (デフォルト) → 最初の例外でギャザー全体が止まる
)
```

## ルール 5: Pydantic ValidationError の扱い

LLM の出力を Pydantic でパース失敗した場合、ログを残してデフォルト値で継続。
**LLM 出力は常に不正である可能性を前提とする。**

```python
# ✅ 良い例
from pydantic import ValidationError

def parse_llm_action(raw: dict) -> AgentAction:
    try:
        return AgentAction.model_validate(raw)
    except ValidationError as e:
        logger.warning(
            "Failed to parse LLM action (using idle default): %s\nRaw: %s",
            e, raw
        )
        return AgentAction(type="idle")  # デフォルトにフォールバック
```

## ルール 6: ログレベルの使い分け

```python
# DEBUG — 開発時の詳細情報 (本番ではオフ)
logger.debug("Tick %d: retrieved %d memories", tick, len(memories))

# INFO — 正常動作の記録
logger.info("Agent %s entered peripatetic mode", agent_id)

# WARNING — 想定内の異常 (リトライ可能、フォールバック済み)
logger.warning("SGLang timeout, fell back to Ollama for agent %s", agent_id)

# ERROR — 想定外の異常 (回復できない個別エラー)
logger.error("Agent %s cognition cycle failed: %s", agent_id, exc)

# CRITICAL — システム全体への影響 (シミュレーション停止レベル)
logger.critical("DB write failed for all agents, stopping simulation")
```

## チェックリスト

- [ ] LLM 推論に SGLang → Ollama フォールバックがあるか
- [ ] リトライに `max_attempts` と `max_delay` の上限を設定しているか
- [ ] WebSocket クライアントに自動再接続ループがあるか
- [ ] `asyncio.gather()` に `return_exceptions=True` が付いているか
- [ ] LLM 出力の Pydantic パース失敗時にデフォルト値でフォールバックしているか
- [ ] ログレベルが意図通り (DEBUG/INFO/WARNING/ERROR/CRITICAL) か

## 補足資料

- `examples.md` — inference アダプタの完全実装例と ws_client の再接続パターン

## 関連する他の Skill

- `python-standards` — asyncio の基本ルール
- `architecture-rules` — inference/ → schemas.py のみ依存の制約
- `llm-inference` — サーバー構成・VRAM 管理
- `persona-erre` — サンプリングオーバーライド表・ペルソナ YAML
- `godot-gdscript` — Godot 側の WebSocket 再接続パターン


 succeeded in 294ms:
---
name: test-standards
description: >
  pytest + pytest-asyncio を使ったテスト設計と実装の基準。
  tests/test_*.py ファイルを書く・修正する・追加する時に必須参照。
  test_schemas.py / test_memory/ / test_cognition/ / test_inference/ /
  test_world/ にテストを追加する時、conftest.py を変更する時、
  CI (uv sync --frozen → ruff → pytest) を設定する時に自動召喚される。
  @pytest.mark.asyncio の使い方、AgentState ファクトリフィクスチャ、
  sqlite-vec 一時 DB、LLM モック戦略、埋め込みプレフィックス検証テスト、
  TDD 適用範囲 (スキーマ検証・記憶検索・ERRE 状態遷移が対象) を定義する。
  ファイル命名: test_schemas.py, test_reflection.py など test_ prefix の .py ファイル全般。
---

# Test Standards

## このスキルの目的

ERRE-Sandbox のテストは「非決定論的な LLM 出力に依存しないロジックを確実に検証する」ことが目的。
特に、記憶検索スコアリング・Pydantic スキーマバリデーション・ERRE モード状態遷移・
埋め込みプレフィックス正確性は回帰リスクが高く、テストなしの変更は禁止。

## 適用範囲

### 適用するもの
- `tests/` 配下のすべての `test_*.py`
- `tests/conftest.py` のフィクスチャ定義

### 適用しないもの
- LLM 推論の出力内容 (非決定論的) — 統合テストでのみ実際の Ollama を使用可
- Godot シーンの描画テスト
- 探索的プロトタイピング段階のコード

## 主要なルール

### ルール 1: ディレクトリ構造は src/ のミラー

```
src/erre_sandbox/memory/retrieval.py  →  tests/test_memory/test_retrieval.py
src/erre_sandbox/cognition/cycle.py   →  tests/test_cognition/test_cycle.py
src/erre_sandbox/schemas.py           →  tests/test_schemas.py
```

新しいモジュールを追加したら、同時に対応テストファイルを作る。

### ルール 2: 非同期テストは @pytest.mark.asyncio

```python
# ✅ 良い例
import pytest
from erre_sandbox.memory.retrieval import retrieve

@pytest.mark.asyncio
async def test_retrieve_returns_top_k() -> None:
    results = await retrieve(query="散歩", k=3)
    assert len(results) <= 3
```

```python
# ❌ 悪い例
def test_retrieve_returns_top_k() -> None:
    import asyncio
    results = asyncio.run(retrieve(query="散歩", k=3))  # asyncio.run は nest できない
    assert len(results) <= 3
```

`pyproject.toml` に以下を追加して全テストを asyncio モードにする:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### ルール 3: conftest.py に共通フィクスチャを集約

```python
# tests/conftest.py
import pytest
import sqlite3
from erre_sandbox.schemas import AgentState, Biography, Physical

@pytest.fixture
def agent_state_kant() -> AgentState:
    """Factory: Kant persona in default state."""
    return AgentState(
        bio=Biography(
            name="Immanuel Kant",
            era="1724-1804",
            primary_corpus_refs=["kuehn2001"],
            cognitive_habits=["15:30±5min walk", "nasal breathing only"],
        )
    )

@pytest.fixture
def tmp_sqlite_db(tmp_path):
    """Temporary sqlite-vec DB for memory tests."""
    db_path = tmp_path / "test_erre.db"
    conn = sqlite3.connect(str(db_path))
    # sqlite-vec 拡張をロード
    conn.enable_load_extension(True)
    conn.execute("SELECT load_extension('sqlite_vec')")
    yield conn
    conn.close()
```

### ルール 4: TDD 適用範囲

**必ず TDD で書くもの (テストを先に書く)**:
- `schemas.py` のバリデーション制約
- `memory/retrieval.py` の検索スコアリングロジック
- ERRE モード状態遷移 (peripatos → DMN bias 変化など)
- 埋め込みプレフィックス検証

**TDD を適用しないもの**:
- LLM 出力に依存するテスト (非決定論的)
- Godot シーンの描画
- 探索的プロトタイピング段階

### ルール 5: LLM 推論を伴うテストはモック分離

単体テストでは LLM を呼ばない。統合テストでのみ実際の Ollama を使用。

```python
# ✅ 良い例 — 単体テストでモック
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_cognition_cycle_calls_llm(agent_state_kant) -> None:
    mock_response = {"action": "walk", "speech": "Gut morgen."}
    with patch("erre_sandbox.inference.ollama_adapter.generate",
               AsyncMock(return_value=mock_response)):
        result = await run_cognition_cycle(agent_state_kant)
    assert result.action == "walk"
```

```python
# ✅ 良い例 — 統合テスト (Ollama 必要、CI では @pytest.mark.integration でスキップ可)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_cycle_with_ollama(agent_state_kant) -> None:
    result = await run_cognition_cycle(agent_state_kant)
    assert result.action is not None
```

### ルール 6: 埋め込みプレフィックス検証テスト（CI 必須）

プレフィックスのミスマッチは 5〜15 ポイントの recall 劣化を招く。
**このテストを削除・無効化してはならない**。

```python
# tests/test_memory/test_embedding_prefix.py
import pytest
from erre_sandbox.memory.embedding import embed_query, embed_document
from erre_sandbox.memory.embedding import QUERY_PREFIX, DOC_PREFIX
import numpy as np

def cosine_sim(a: list[float], b: list[float]) -> float:
    a_, b_ = np.array(a), np.array(b)
    return float(np.dot(a_, b_) / (np.linalg.norm(a_) * np.linalg.norm(b_)))

def test_query_and_doc_prefix_are_different() -> None:
    """Query and document prefixes must be distinct."""
    assert QUERY_PREFIX != DOC_PREFIX

def test_semantic_similarity_with_correct_prefix() -> None:
    """Relevant doc must score higher than irrelevant doc."""
    q = embed_query("アリストテレスの歩行習慣について")
    d_relevant = embed_document("ペリパトス学派は歩きながら議論した")
    d_irrelevant = embed_document("量子コンピューターの計算速度")
    assert cosine_sim(q, d_relevant) > cosine_sim(q, d_irrelevant) + 0.3
```

### ルール 7: memory_strength の単体テスト

```python
# tests/test_memory/test_retrieval.py
from erre_sandbox.memory.retrieval import compute_memory_strength

def test_memory_decays_over_time() -> None:
    """Strength must decrease as days increase."""
    s_fresh = compute_memory_strength(importance=8.0, days_since=0.0, recall_count=0)
    s_old   = compute_memory_strength(importance=8.0, days_since=30.0, recall_count=0)
    assert s_fresh > s_old

def test_recall_increases_strength() -> None:
    """Recall count bonus must increase strength."""
    s_no_recall  = compute_memory_strength(importance=5.0, days_since=1.0, recall_count=0)
    s_recalled   = compute_memory_strength(importance=5.0, days_since=1.0, recall_count=5)
    assert s_recalled > s_no_recall
```

## チェックリスト

- [ ] テストファイルが `tests/test_[module]/test_[file].py` の構造を守っているか
- [ ] 非同期テストに `@pytest.mark.asyncio` が付いているか
- [ ] 共通フィクスチャが `conftest.py` に集約されているか
- [ ] LLM 推論を単体テストでモックしているか
- [ ] 埋め込みプレフィックステストが `tests/test_memory/test_embedding_prefix.py` にあるか
- [ ] `pytest` が通るか (`uv run pytest`)
- [ ] `ruff check tests/` が通るか

## 補足資料

- `examples.md` — conftest.py の全フィクスチャ例と統合テストの書き方

## 関連する他の Skill

- `python-standards` — テストコードでも同じ Python 規約が適用される
- `implementation-workflow` — Step F (テストと検証) でこの Skill を参照


 succeeded in 317ms:
---
name: python-standards
description: >
  Python 3.11 のコーディング規約を適用する。src/erre_sandbox/ 配下の
  .py ファイルを書く・修正する・レビューする時に必須参照。
  asyncio を使った非同期コードを書く時、Pydantic v2 の BaseModel を定義する時、
  FastAPI エンドポイントを実装する時、schemas.py を変更する時に自動召喚される。
  snake_case/PascalCase の命名、型ヒント必須、ruff format/lint 準拠、
  f-string 優先、from __future__ import annotations 使用が強制される。
  ファイル命名: ollama_adapter.py, ws_client.py など snake_case .py ファイル全般。
---

# Python Standards

## このスキルの目的

Python 3.11 + asyncio + Pydantic v2 + FastAPI を使う ERRE-Sandbox において、
一貫したコーディング規約を維持する。特に asyncio の正しい使い方と
型安全性は、マルチエージェントシミュレーションの安定稼働に直結する。

## 適用範囲

### 適用するもの
- `src/erre_sandbox/` 配下のすべての `.py` ファイル
- `tests/` 配下のテストコード
- `pyproject.toml` の ruff 設定

### 適用しないもの
- `godot_project/` 内の GDScript (`.gd`) — Godot 規約に従う
- Jupyter notebook (`.ipynb`) — 探索的コードは適用外

## 主要なルール

### ルール 1: 型ヒントは必須

すべての関数・メソッドに引数と戻り値の型ヒントを付与する。
`from __future__ import annotations` でファイル先頭に遅延評価を有効化。

```python
# ✅ 良い例
from __future__ import annotations

async def retrieve(query: str, k: int = 8) -> list[MemoryEntry]:
    ...
```

```python
# ❌ 悪い例
async def retrieve(query, k=8):
    ...
```

### ルール 2: asyncio — ブロッキング I/O を避ける

同期的な I/O (ファイル読み込み、DB アクセス、HTTP) は `asyncio.to_thread()` か
専用の async ライブラリを使う。`time.sleep()` は `asyncio.sleep()` に置き換える。

```python
# ✅ 良い例
import asyncio

async def load_corpus(path: str) -> str:
    return await asyncio.to_thread(_read_file_sync, path)

async def wait_for_inference() -> None:
    await asyncio.sleep(0.1)
```

```python
# ❌ 悪い例
def load_corpus(path: str) -> str:
    with open(path) as f:           # ブロッキング
        return f.read()

import time
time.sleep(0.1)                     # asyncio ループをブロック
```

### ルール 3: Pydantic v2 — BaseModel 活用

エージェント状態・通信プロトコル・設定はすべて `BaseModel` で定義。
`model_validator` / `field_validator` で制約を付与し、`dump_for_prompt()` で
LLM コンテキスト用文字列化メソッドを実装。

```python
# ✅ 良い例
from pydantic import BaseModel, field_validator

class AgentState(BaseModel):
    agent_id: str
    fatigue: float = 0.0

    @field_validator("fatigue")
    @classmethod
    def clamp_fatigue(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    def dump_for_prompt(self) -> str:
        return f"Agent {self.agent_id}: fatigue={self.fatigue:.2f}"
```

```python
# ❌ 悪い例
class AgentState:
    def __init__(self, agent_id, fatigue=0.0):
        self.agent_id = agent_id
        self.fatigue = fatigue   # バリデーションなし
```

### ルール 4: 命名規則

| 対象 | 規則 | 例 |
|---|---|---|
| 変数・関数 | snake_case | `agent_state`, `dump_for_prompt()` |
| クラス | PascalCase | `AgentState`, `MemoryStream` |
| 定数 | UPPER_SNAKE_CASE | `DEFAULT_TEMPERATURE`, `MAX_AGENTS` |
| ファイル・モジュール | snake_case | `ollama_adapter.py`, `ws_client.py` |

### ルール 5: 文字列フォーマット

`f-string` を既定とする。`%` 形式・`.format()` は新規コードで使わない。

```python
# ✅ 良い例
label = f"Agent {agent_id}: step={tick_count}"
```

```python
# ❌ 悪い例
label = "Agent %s: step=%d" % (agent_id, tick_count)
label = "Agent {}: step={}".format(agent_id, tick_count)
```

### ルール 6: インポート順序 (ruff 準拠)

1. 標準ライブラリ
2. サードパーティ
3. ローカル (`erre_sandbox.*`)

各グループは空行で区切り、グループ内はアルファベット順。`ruff` が自動整形。

```python
# ✅ 良い例
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import BaseModel

from erre_sandbox.schemas import AgentState
```

### ルール 7: コメント方針

- **書くべき時**: ロジックが自明でない、認知科学論文への参照、ERRE 独自設計の理由
- **書かないとき**: 型ヒントやメソッド名で意図が明確な場合
- **docstring**: 英語、Google スタイル。公開 API には必ず付ける

```python
# ✅ 良い例
# Park et al. (2023) Eq.3: importance × recency × relevance の積
score = importance * recency * relevance
```

```python
# ❌ 悪い例
# スコアを計算する
score = importance * recency * relevance
```

## チェックリスト

このルールに従っているか確認:

- [ ] すべての関数に型ヒントが付いているか
- [ ] ファイル先頭に `from __future__ import annotations` があるか
- [ ] ブロッキング I/O を asyncio ループ内で直接呼んでいないか
- [ ] Pydantic v2 `BaseModel` で状態・スキーマを定義しているか
- [ ] 命名規則 (snake_case / PascalCase / UPPER_SNAKE_CASE) を守っているか
- [ ] 文字列フォーマットに f-string を使っているか
- [ ] `ruff check` と `ruff format --check` が通るか

## 補足資料

- `patterns.md` — asyncio + Pydantic v2 のよく使うパターン集

## 関連する他の Skill

- `test-standards` — テストコードでも同じ規約が適用される
- `error-handling` — asyncio のエラーハンドリングパターン
- `architecture-rules` — インポート依存方向の制約
- `godot-gdscript` — godot_project/ 内の GDScript 規約 (Python とは別体系)


hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "asyncio_mode|pytest" pyproject.toml' in C:\ERRE-Sand_Box
 succeeded in 229ms:
113:    "pytest>=8,<9",
114:    "pytest-asyncio>=0.24,<1",
187:    # pytest で assert を使うため
252:# + pytest importorskip)。 langdetect は既に PR-18 で eval extras に追加済 (line 60)。
284:# pytest
286:[tool.pytest.ini_options]
288:asyncio_mode = "auto"
300:    # pytest-asyncio 0.26.x は function-scope の event loop teardown 後に
304:    # しない) に下げる。pytest-asyncio >= 0.27 に上がったら本行は撤去。
305:    "default::pytest.PytestUnraisableExceptionWarning",

hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"class MoveMsg|resolved_from|ecl_destination|move_decision|envelopes\" src\\erre_sandbox\\schemas.py src\\erre_sandbox\\cognition src\\erre_sandbox\\world" in C:\ERRE-Sand_Box
 succeeded in 244ms:
src\erre_sandbox\schemas.py:1193:class MoveMsg(_EnvelopeBase):
src\erre_sandbox\world\tick.py:16:on ``_agents`` / ``_envelopes``) and lets a :class:`ManualClock` reproduce
src\erre_sandbox\world\tick.py:618:        # envelopes go to a bounded main queue (maxsize=1024) with drop-oldest
src\erre_sandbox\world\tick.py:623:        self._heartbeat_envelopes: asyncio.Queue[ControlEnvelope] = asyncio.Queue(
src\erre_sandbox\world\tick.py:626:        self._envelopes: asyncio.Queue[ControlEnvelope] = asyncio.Queue(maxsize=1024)
src\erre_sandbox\world\tick.py:953:        (``_envelopes``) is prioritised over heartbeat
src\erre_sandbox\world\tick.py:954:        (``_heartbeat_envelopes``) when both are ready, so dialog and error
src\erre_sandbox\world\tick.py:955:        envelopes never starve under a heartbeat-heavy load. When the race
src\erre_sandbox\world\tick.py:962:        main_task = asyncio.create_task(self._envelopes.get())
src\erre_sandbox\world\tick.py:963:        hb_task = asyncio.create_task(self._heartbeat_envelopes.get())
src\erre_sandbox\world\tick.py:1000:            self._heartbeat_envelopes.put_nowait(env)
src\erre_sandbox\world\tick.py:1002:    def drain_envelopes(self) -> list[ControlEnvelope]:
src\erre_sandbox\world\tick.py:1003:        """Non-blocking drain of all currently queued envelopes.
src\erre_sandbox\world\tick.py:1013:        while not self._heartbeat_envelopes.empty():
src\erre_sandbox\world\tick.py:1014:            out.append(self._heartbeat_envelopes.get_nowait())
src\erre_sandbox\world\tick.py:1015:        while not self._envelopes.empty():
src\erre_sandbox\world\tick.py:1016:            out.append(self._envelopes.get_nowait())
src\erre_sandbox\world\tick.py:1024:        if self._envelopes.maxsize > 0 and self._envelopes.full():
src\erre_sandbox\world\tick.py:1025:            while self._envelopes.qsize() > max(self._envelopes.maxsize - 2, 0):
src\erre_sandbox\world\tick.py:1027:                    self._envelopes.get_nowait()
src\erre_sandbox\world\tick.py:1034:                    f"runtime _envelopes full (maxsize="
src\erre_sandbox\world\tick.py:1035:                    f"{self._envelopes.maxsize}); "
src\erre_sandbox\world\tick.py:1047:                self._envelopes.maxsize,
src\erre_sandbox\world\tick.py:1050:                self._envelopes.put_nowait(warning)
src\erre_sandbox\world\tick.py:1054:            self._envelopes.put_nowait(env)
src\erre_sandbox\world\tick.py:1462:        observation buffer. Dialog envelopes are delivered through the
src\erre_sandbox\world\tick.py:1649:            self._heartbeat_envelopes.put_nowait(env)
src\erre_sandbox\world\tick.py:1655:                self._heartbeat_envelopes.get_nowait()
src\erre_sandbox\world\tick.py:1656:            self._heartbeat_envelopes.put_nowait(env)
src\erre_sandbox\world\tick.py:1736:        for env in res.envelopes:
src\erre_sandbox\world\tick.py:1740:                # point. CognitionCycle._build_envelopes emits this shape when
src\erre_sandbox\cognition\embodiment.py:111:    absolute target. ``resolved_from`` is ``"spawn"`` on the history-independent
src\erre_sandbox\cognition\embodiment.py:117:    resolved_from: Literal["memory_centroid", "spawn"]
src\erre_sandbox\cognition\embodiment.py:149:    move_decision_sink: Callable[[EclDestination], None] | None = None
src\erre_sandbox\cognition\embodiment.py:260:            resolved_from="spawn",
src\erre_sandbox\cognition\embodiment.py:281:        resolved_from="memory_centroid",
src\erre_sandbox\cognition\cycle.py:15:  ``AgentUpdate`` / ``Move`` / ``Speech`` / ``Animation`` envelopes.
src\erre_sandbox\cognition\cycle.py:259:    metric — without it, callers would have to diff ``envelopes`` to infer
src\erre_sandbox\cognition\cycle.py:266:    envelopes: list[ControlEnvelope] = Field(default_factory=list)
src\erre_sandbox\cognition\cycle.py:371:    ecl_destination: EclDestination | None = None
src\erre_sandbox\cognition\cycle.py:379:    ``pre_clamp`` / ``post_clamp`` / ``resolved_from``) behind the emitted MoveMsg
src\erre_sandbox\cognition\cycle.py:841:        # Step 9: assemble the post-tick state + envelopes. The M13-ES3 live
src\erre_sandbox\cognition\cycle.py:859:        # non-moving tick — ``_build_envelopes`` then takes the byte-identical zone-only
src\erre_sandbox\cognition\cycle.py:861:        ecl_destination = await self._resolve_ecl_move(new_state, plan)
src\erre_sandbox\cognition\cycle.py:862:        envelopes = self._build_envelopes(
src\erre_sandbox\cognition\cycle.py:868:            ecl_destination=ecl_destination,
src\erre_sandbox\cognition\cycle.py:887:            envelopes=envelopes,
src\erre_sandbox\cognition\cycle.py:898:        envelopes = self._pin_envelope_clock(envelopes)
src\erre_sandbox\cognition\cycle.py:912:            envelopes=envelopes,
src\erre_sandbox\cognition\cycle.py:925:            ecl_destination=ecl_destination,
src\erre_sandbox\cognition\cycle.py:1179:        envelopes: list[ControlEnvelope],
src\erre_sandbox\cognition\cycle.py:1188:        trigger, emitting a ``ReflectionEventMsg`` over *envelopes* when it fires.
src\erre_sandbox\cognition\cycle.py:1229:            envelopes.append(
src\erre_sandbox\cognition\cycle.py:1319:        Cognitive is carried over, no Speech/Move/Animation envelopes.
src\erre_sandbox\cognition\cycle.py:1353:        envelopes: list[ControlEnvelope] = [
src\erre_sandbox\cognition\cycle.py:1362:            envelopes = self._pin_envelope_clock(envelopes)
src\erre_sandbox\cognition\cycle.py:1365:            envelopes=envelopes,
src\erre_sandbox\cognition\cycle.py:1397:        ecl_destination = await resolve_destination(
src\erre_sandbox\cognition\cycle.py:1406:        if ecl_mode.move_decision_sink is not None:
src\erre_sandbox\cognition\cycle.py:1407:            ecl_mode.move_decision_sink(ecl_destination)
src\erre_sandbox\cognition\cycle.py:1408:        return ecl_destination
src\erre_sandbox\cognition\cycle.py:1412:        envelopes: list[ControlEnvelope],
src\erre_sandbox\cognition\cycle.py:1416:        Flag-off (``ecl_mode is None``) returns ``envelopes`` unchanged, so the live
src\erre_sandbox\cognition\cycle.py:1434:            return envelopes
src\erre_sandbox\cognition\cycle.py:1437:        for env in envelopes:
src\erre_sandbox\cognition\cycle.py:1464:    def _build_envelopes(
src\erre_sandbox\cognition\cycle.py:1472:        ecl_destination: EclDestination | None = None,
src\erre_sandbox\cognition\cycle.py:1474:        envelopes: list[ControlEnvelope] = [
src\erre_sandbox\cognition\cycle.py:1478:            envelopes.append(
src\erre_sandbox\cognition\cycle.py:1487:            if ecl_destination is not None:
src\erre_sandbox\cognition\cycle.py:1493:                target = ecl_destination.target
src\erre_sandbox\cognition\cycle.py:1502:            envelopes.append(
src\erre_sandbox\cognition\cycle.py:1514:            envelopes.append(
src\erre_sandbox\cognition\cycle.py:1555:            envelopes.append(
src\erre_sandbox\cognition\cycle.py:1558:        return envelopes

hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"EclDestination|resolved_from|memory_centroid|MoveMsg\" src\\erre_sandbox\\cognition\\embodiment.py src\\erre_sandbox\\cognition\\cycle.py src\\erre_sandbox\\world\\*.py" in C:\ERRE-Sand_Box
2026-07-06T12:14:39.280636Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.2 seconds
Output:
src\erre_sandbox\cognition\embodiment.py:104:class EclDestination:
src\erre_sandbox\cognition\embodiment.py:111:    absolute target. ``resolved_from`` is ``"spawn"`` on the history-independent
src\erre_sandbox\cognition\embodiment.py:117:    resolved_from: Literal["memory_centroid", "spawn"]
src\erre_sandbox\cognition\embodiment.py:140:    the only non-primitive it references is :class:`EclDestination`, a
src\erre_sandbox\cognition\embodiment.py:149:    move_decision_sink: Callable[[EclDestination], None] | None = None
src\erre_sandbox\cognition\embodiment.py:228:) -> EclDestination:
src\erre_sandbox\cognition\embodiment.py:258:        return EclDestination(
src\erre_sandbox\cognition\embodiment.py:260:            resolved_from="spawn",
src\erre_sandbox\cognition\embodiment.py:279:    return EclDestination(
src\erre_sandbox\cognition\embodiment.py:281:        resolved_from="memory_centroid",
src\erre_sandbox\cognition\embodiment.py:293:    "EclDestination",
src\erre_sandbox\cognition\cycle.py:40:# ``resolve_destination`` is called at runtime; ``EclDestination`` is a Pydantic field
src\erre_sandbox\cognition\cycle.py:43:from erre_sandbox.cognition.embodiment import EclDestination, resolve_destination
src\erre_sandbox\cognition\cycle.py:120:    MoveMsg,
src\erre_sandbox\cognition\cycle.py:187:    ``move_t`` = 1 when the agent commits to a zone change this tick (a MoveMsg
src\erre_sandbox\cognition\cycle.py:371:    ecl_destination: EclDestination | None = None
src\erre_sandbox\cognition\cycle.py:376:    :class:`~erre_sandbox.cognition.embodiment.EclDestination` returned by
src\erre_sandbox\cognition\cycle.py:379:    ``pre_clamp`` / ``post_clamp`` / ``resolved_from``) behind the emitted MoveMsg
src\erre_sandbox\cognition\cycle.py:504:        # Plane 1 and route the MoveMsg target through ``resolve_destination`` (design
src\erre_sandbox\cognition\cycle.py:858:        # history-dependent coordinate before the MoveMsg is built (``None`` flag-off /
src\erre_sandbox\cognition\cycle.py:1380:    ) -> EclDestination | None:
src\erre_sandbox\cognition\cycle.py:1381:        """Resolve the ECL history-dependent MoveMsg target (Issue 003, record mode).
src\erre_sandbox\cognition\cycle.py:1385:        zone-only MoveMsg. When active, reads the agent's own top-K memories
src\erre_sandbox\cognition\cycle.py:1472:        ecl_destination: EclDestination | None = None,
src\erre_sandbox\cognition\cycle.py:1503:                MoveMsg(
rg: src\erre_sandbox\world\*.py: ファイル名、ディレクトリ名、またはボリューム ラベルの構文が間違っています。 (os error 123)

 exited 1 in 236ms:
src\erre_sandbox\cognition\embodiment.py:104:class EclDestination:
src\erre_sandbox\cognition\embodiment.py:111:    absolute target. ``resolved_from`` is ``"spawn"`` on the history-independent
src\erre_sandbox\cognition\embodiment.py:117:    resolved_from: Literal["memory_centroid", "spawn"]
src\erre_sandbox\cognition\embodiment.py:140:    the only non-primitive it references is :class:`EclDestination`, a
src\erre_sandbox\cognition\embodiment.py:149:    move_decision_sink: Callable[[EclDestination], None] | None = None
src\erre_sandbox\cognition\embodiment.py:228:) -> EclDestination:
src\erre_sandbox\cognition\embodiment.py:258:        return EclDestination(
src\erre_sandbox\cognition\embodiment.py:260:            resolved_from="spawn",
src\erre_sandbox\cognition\embodiment.py:279:    return EclDestination(
src\erre_sandbox\cognition\embodiment.py:281:        resolved_from="memory_centroid",
src\erre_sandbox\cognition\embodiment.py:293:    "EclDestination",
src\erre_sandbox\cognition\cycle.py:40:# ``resolve_destination`` is called at runtime; ``EclDestination`` is a Pydantic field
src\erre_sandbox\cognition\cycle.py:43:from erre_sandbox.cognition.embodiment import EclDestination, resolve_destination
src\erre_sandbox\cognition\cycle.py:120:    MoveMsg,
src\erre_sandbox\cognition\cycle.py:187:    ``move_t`` = 1 when the agent commits to a zone change this tick (a MoveMsg
src\erre_sandbox\cognition\cycle.py:371:    ecl_destination: EclDestination | None = None
src\erre_sandbox\cognition\cycle.py:376:    :class:`~erre_sandbox.cognition.embodiment.EclDestination` returned by
src\erre_sandbox\cognition\cycle.py:379:    ``pre_clamp`` / ``post_clamp`` / ``resolved_from``) behind the emitted MoveMsg
src\erre_sandbox\cognition\cycle.py:504:        # Plane 1 and route the MoveMsg target through ``resolve_destination`` (design
src\erre_sandbox\cognition\cycle.py:858:        # history-dependent coordinate before the MoveMsg is built (``None`` flag-off /
src\erre_sandbox\cognition\cycle.py:1380:    ) -> EclDestination | None:
src\erre_sandbox\cognition\cycle.py:1381:        """Resolve the ECL history-dependent MoveMsg target (Issue 003, record mode).
src\erre_sandbox\cognition\cycle.py:1385:        zone-only MoveMsg. When active, reads the agent's own top-K memories
src\erre_sandbox\cognition\cycle.py:1472:        ecl_destination: EclDestination | None = None,
src\erre_sandbox\cognition\cycle.py:1503:                MoveMsg(
rg: src\erre_sandbox\world\*.py: ファイル名、ディレクトリ名、またはボリューム ラベルの構文が間違っています。 (os error 123)

codex
O5 は `move_decision` 由来で数えていますが、既存 cycle の設計上その `EclDestination` が MoveMsg の target に流れる構造です。ここは追加の問題にはしません。
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$start=1370;$end=1525;$i=0; Get-Content src'"\\erre_sandbox\\cognition\\cycle.py | ForEach-Object { "'$i++; if($i -ge $start -and $i -le $end){ '"'{0,5}: {1}' -f "'$i, $_ }}' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$start=1185;$end=1225;$i=0; Get-Content src'"\\erre_sandbox\\schemas.py | ForEach-Object { "'$i++; if($i -ge $start -and $i -le $end){ '"'{0,5}: {1}' -f "'$i, $_ }}' in C:\ERRE-Sand_Box
 succeeded in 287ms:
 1370:             world_model_saturation=world_model_saturation,
 1371:             world_model_hint_engagement=world_model_hint_engagement,
 1372:         )
 1373: 
 1374:     async def _resolve_ecl_move(
 1375:         self,
 1376:         new_state: AgentState,
 1377:         plan: LLMPlan,
 1378:     ) -> EclDestination | None:
 1379:         """Resolve the ECL history-dependent MoveMsg target (Issue 003, record mode).
 1380: 
 1381:         Returns ``None`` flag-off (``ecl_mode is None``) or when the plan does not move
 1382:         (``destination_zone is None``) 窶・the caller then builds the byte-identical
 1383:         zone-only MoveMsg. When active, reads the agent's own top-K memories
 1384:         (``k_world=0`` / ``mark_recalled=False``, frozen in the resolver) via
 1385:         ``self._retriever`` and folds their strength-weighted centroid + jitter into the
 1386:         target (policy grammar freeze, design ﾂｧ隲也せ2). The resolved provenance is pushed
 1387:         to the record mode's optional move-decision sink and also surfaced on
 1388:         ``CycleResult`` so the I4 harness assembles Plane 1 from the logged candidate
 1389:         selection (centroid / memory ids / jitter / clamp), never an absolute-target
 1390:         replay (design ﾂｧ隲也せ3/ﾂｧ隲也せ4).
 1391:         """
 1392:         ecl_mode = self._ecl_mode
 1393:         if ecl_mode is None or plan.destination_zone is None:
 1394:             return None
 1395:         ecl_destination = await resolve_destination(
 1396:             self._retriever,
 1397:             agent_id=new_state.agent_id,
 1398:             query=_ECL_FORAGE_QUERY,
 1399:             here=new_state.position,
 1400:             destination_zone=plan.destination_zone,
 1401:             micro_rng=ecl_mode.substream(new_state.agent_id, "micro"),
 1402:             k_ecl=ecl_mode.k_ecl,
 1403:         )
 1404:         if ecl_mode.move_decision_sink is not None:
 1405:             ecl_mode.move_decision_sink(ecl_destination)
 1406:         return ecl_destination
 1407: 
 1408:     def _pin_envelope_clock(
 1409:         self,
 1410:         envelopes: list[ControlEnvelope],
 1411:     ) -> list[ControlEnvelope]:
 1412:         """Pin every envelope's clock fields to the record-mode clock (Issue 003).
 1413: 
 1414:         Flag-off (``ecl_mode is None``) returns ``envelopes`` unchanged, so the live
 1415:         path keeps the wall-clock default factory and stays byte-invariant. In record
 1416:         mode each envelope's ``sent_at`` is re-stamped to the fixed ``retrieval_now``
 1417:         so Plane 1 is deterministic (design ﾂｧ隲也せ3).
 1418: 
 1419:         Nested ``_utc_now`` snapshot fields also leak wall-clock into the committed
 1420:         ``decisions.jsonl`` artifact (via ``envelope_provenance``), making a re-bake
 1421:         non-deterministic (Codex HIGH-1, B-5 / W). So in record mode this also pins
 1422:         the two nested clocks to the same ``retrieval_now``:
 1423: 
 1424:         * :class:`AgentUpdateMsg` 窶・``agent_state.wall_clock``;
 1425:         * :class:`ReasoningTraceMsg` 窶・``trace.created_at``.
 1426: 
 1427:         All other envelope kinds carry only the top-level ``sent_at`` and are pinned
 1428:         as before.
 1429:         """
 1430:         ecl_mode = self._ecl_mode
 1431:         if ecl_mode is None:
 1432:             return envelopes
 1433:         pinned = ecl_mode.retrieval_now
 1434:         result: list[ControlEnvelope] = []
 1435:         for env in envelopes:
 1436:             if isinstance(env, AgentUpdateMsg):
 1437:                 result.append(
 1438:                     env.model_copy(
 1439:                         update={
 1440:                             "sent_at": pinned,
 1441:                             "agent_state": env.agent_state.model_copy(
 1442:                                 update={"wall_clock": pinned}
 1443:                             ),
 1444:                         }
 1445:                     )
 1446:                 )
 1447:             elif isinstance(env, ReasoningTraceMsg):
 1448:                 result.append(
 1449:                     env.model_copy(
 1450:                         update={
 1451:                             "sent_at": pinned,
 1452:                             "trace": env.trace.model_copy(
 1453:                                 update={"created_at": pinned}
 1454:                             ),
 1455:                         }
 1456:                     )
 1457:                 )
 1458:             else:
 1459:                 result.append(env.model_copy(update={"sent_at": pinned}))
 1460:         return result
 1461: 
 1462:     def _build_envelopes(
 1463:         self,
 1464:         new_state: AgentState,
 1465:         plan: LLMPlan,
 1466:         *,
 1467:         persona: PersonaSpec,
 1468:         observations: Sequence[Observation] = (),
 1469:         memories: Sequence[RankedMemory] = (),
 1470:         ecl_destination: EclDestination | None = None,
 1471:     ) -> list[ControlEnvelope]:
 1472:         envelopes: list[ControlEnvelope] = [
 1473:             AgentUpdateMsg(tick=new_state.tick, agent_state=new_state),
 1474:         ]
 1475:         if plan.utterance:
 1476:             envelopes.append(
 1477:                 SpeechMsg(
 1478:                     tick=new_state.tick,
 1479:                     agent_id=new_state.agent_id,
 1480:                     utterance=plan.utterance,
 1481:                     zone=new_state.position.zone,
 1482:                 ),
 1483:             )
 1484:         if plan.destination_zone is not None:
 1485:             if ecl_destination is not None:
 1486:                 # ECL v0 (Issue 003): the LLM chose *which* zone; history chose *where*
 1487:                 # in it. ``resolve_destination`` already produced a concrete,
 1488:                 # ``locate_zone``-consistent coordinate, so the world layer's
 1489:                 # zone-only 竊・spawn resolution (``tick.py`` ``default_spawn`` branch)
 1490:                 # never fires and the agent transits continuously (design ﾂｧ隲也せ1).
 1491:                 target = ecl_destination.target
 1492:             else:
 1493:                 # Flag-off / live path (byte-identical to pre-ECL): coordinates are
 1494:                 # carried over verbatim; the Godot side (T17) performs spatial
 1495:                 # interpolation via Tween based on the Zone boundary, so we only hand
 1496:                 # over the semantic destination.
 1497:                 target = new_state.position.model_copy(
 1498:                     update={"zone": plan.destination_zone},
 1499:                 )
 1500:             envelopes.append(
 1501:                 MoveMsg(
 1502:                     tick=new_state.tick,
 1503:                     agent_id=new_state.agent_id,
 1504:                     target=target,
 1505:                     speed=(
 1506:                         self.DEFAULT_DESTINATION_SPEED
 1507:                         * persona.behavior_profile.movement_speed_factor
 1508:                     ),
 1509:                 ),
 1510:             )
 1511:         if plan.animation:
 1512:             envelopes.append(
 1513:                 AnimationMsg(
 1514:                     tick=new_state.tick,
 1515:                     agent_id=new_state.agent_id,
 1516:                     animation_name=plan.animation,
 1517:                 ),
 1518:             )
 1519:         # M7ﾎｳ D3+D4: structured rationale carries the observation / memory
 1520:         # provenance and an affinity hint so the xAI panel can show *why*
 1521:         # the agent decided this way. Even when the LLM did not fill any
 1522:         # rationale field, the trace is emitted whenever at least one of
 1523:         # the M7ﾎｳ provenance lists is non-empty *or* there is a recent
 1524:         # bond 窶・otherwise downstream consumers would lose the affinity
 1525:         # signal entirely on quiet ticks.

 succeeded in 261ms:
 1185:     kind: Literal["speech"] = "speech"
 1186:     agent_id: str
 1187:     utterance: str
 1188:     zone: Zone
 1189:     emotion: PlutchikDimension | None = None
 1190: 
 1191: 
 1192: class MoveMsg(_EnvelopeBase):
 1193:     """Locomotion intent for an agent (G-GEAR 竊・MacBook 竊・Godot nav)."""
 1194: 
 1195:     kind: Literal["move"] = "move"
 1196:     agent_id: str
 1197:     target: Position
 1198:     speed: float = Field(..., ge=0.0, description="Metres per second.")
 1199: 
 1200: 
 1201: class AnimationMsg(_EnvelopeBase):
 1202:     """Animation state change (walk / idle / sit_seiza / bow 窶ｦ)."""
 1203: 
 1204:     kind: Literal["animation"] = "animation"
 1205:     agent_id: str
 1206:     animation_name: str
 1207:     loop: bool = False
 1208: 
 1209: 
 1210: class WorldTickMsg(_EnvelopeBase):
 1211:     """Global clock pulse (G-GEAR 竊・MacBook, heartbeat)."""
 1212: 
 1213:     kind: Literal["world_tick"] = "world_tick"
 1214:     wall_clock: datetime = Field(default_factory=_utc_now)
 1215:     active_agents: int = Field(..., ge=0)
 1216: 
 1217: 
 1218: class ErrorMsg(_EnvelopeBase):
 1219:     """Structured error for observability."""
 1220: 
 1221:     kind: Literal["error"] = "error"
 1222:     code: str
 1223:     detail: str
 1224: 
 1225: 

codex
`ThinkOffChatClient` の経路は、`RecordReplayChatClient` の record mode が `think=None` を渡しても内側で `False` に潰すので、qwen3 の `<think>` 問題は閉じています。次に live model pin と env pin 周りを確認します。
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$start=120;$end=188;$i=0; Get-Content src'"\\erre_sandbox\\inference\\ollama_adapter.py | ForEach-Object { "'$i++; if($i -ge $start -and $i -le $end){ '"'{0,5}: {1}' -f "'$i, $_ }}' in C:\ERRE-Sand_Box
 succeeded in 262ms:
  120:     """
  121: 
  122: 
  123: # ---------------------------------------------------------------------------
  124: # Client
  125: # ---------------------------------------------------------------------------
  126: 
  127: 
  128: class OllamaChatClient:
  129:     """Asynchronous client for Ollama's ``/api/chat`` endpoint.
  130: 
  131:     Typical use::
  132: 
  133:         async with OllamaChatClient() as llm:
  134:             resp = await llm.chat(
  135:                 [
  136:                     ChatMessage(role="system", content=persona_prompt),
  137:                     ChatMessage(role="user", content=observation),
  138:                 ],
  139:                 sampling=compose_sampling(
  140:                     persona.default_sampling,
  141:                     agent.erre.sampling_overrides,
  142:                 ),
  143:                 options={"num_predict": 256},
  144:             )
  145:             print(resp.content)
  146: 
  147:     The client takes an optional :class:`httpx.AsyncClient` so tests can inject
  148:     an :class:`httpx.MockTransport` and production code can share a long-lived
  149:     connection pool. When the ``client`` argument is ``None`` the adapter
  150:     constructs and owns its own client (closed on ``async with`` exit).
  151:     """
  152: 
  153:     DEFAULT_MODEL: ClassVar[str] = DEFAULT_CHAT_MODEL
  154:     DEFAULT_ENDPOINT: ClassVar[str] = "http://127.0.0.1:11434"
  155:     DEFAULT_TIMEOUT_SECONDS: ClassVar[float] = 60.0
  156:     CHAT_PATH: ClassVar[str] = "/api/chat"
  157: 
  158:     def __init__(
  159:         self,
  160:         *,
  161:         model: str | None = None,
  162:         endpoint: str | None = None,
  163:         timeout: float | None = None,
  164:         client: httpx.AsyncClient | None = None,
  165:     ) -> None:
  166:         self.model = model or self.DEFAULT_MODEL
  167:         self.endpoint = (endpoint or self.DEFAULT_ENDPOINT).rstrip("/")
  168:         self._timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT_SECONDS
  169:         self._client: httpx.AsyncClient = client or httpx.AsyncClient(
  170:             base_url=self.endpoint,
  171:             timeout=self._timeout,
  172:         )
  173:         self._owns_client = client is None
  174: 
  175:     async def __aenter__(self) -> Self:
  176:         return self
  177: 
  178:     async def __aexit__(self, *_exc_info: object) -> None:
  179:         await self.close()
  180: 
  181:     async def close(self) -> None:
  182:         if self._owns_client and not self._client.is_closed:
  183:             await self._client.aclose()
  184: 
  185:     # ------------------------------------------------------------------
  186:     # Public API
  187:     # ------------------------------------------------------------------
  188: 

codex
`OllamaChatClient()` の default model に依存しており、実行 artifact の manifest には digest と version は残っています。ここは sealed run 実行値と整合しています。
hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"DEFAULT_CHAT_MODEL\" src\\erre_sandbox" in C:\ERRE-Sand_Box
 succeeded in 236ms:
src\erre_sandbox\inference\__init__.py:15:* :data:`DEFAULT_CHAT_MODEL` — Ollama model tag pulled during T09
src\erre_sandbox\inference\__init__.py:30:    DEFAULT_CHAT_MODEL,
src\erre_sandbox\inference\__init__.py:47:    "DEFAULT_CHAT_MODEL",
src\erre_sandbox\inference\ollama_adapter.py:37:DEFAULT_CHAT_MODEL: Final[str] = "qwen3:8b"
src\erre_sandbox\inference\ollama_adapter.py:153:    DEFAULT_MODEL: ClassVar[str] = DEFAULT_CHAT_MODEL
src\erre_sandbox\inference\ollama_adapter.py:350:    "DEFAULT_CHAT_MODEL",

hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"OllamaUnavailableError|llm.chat|parse_llm_plan|llm_fell_back\" src\\erre_sandbox\\cognition\\cycle.py" in C:\ERRE-Sand_Box
 succeeded in 231ms:
56:from erre_sandbox.cognition.parse import parse_llm_plan
100:    OllamaUnavailableError,
258:    ``llm_fell_back`` is the explicit flag the T14 gateway will surface as a
269:    llm_fell_back: bool = False
695:            resp = await self._llm.chat(
702:        except OllamaUnavailableError as exc:
734:        plan = parse_llm_plan(resp.content)
915:            llm_fell_back=False,
1085:        except (OllamaUnavailableError, EmbeddingUnavailableError) as exc:
1368:            llm_fell_back=True,

hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$start=675;$end=750;$i=0; Get-Content src'"\\erre_sandbox\\cognition\\cycle.py | ForEach-Object { "'$i++; if($i -ge $start -and $i -le $end){ '"'{0,5}: {1}' -f "'$i, $_ }}' in C:\ERRE-Sand_Box
 succeeded in 271ms:
  675:         # locomotion channel composes bit-identically to the pre-ES3 path.
  676:         sampling = compose_sampling(
  677:             persona.default_sampling,
  678:             agent_state.erre.sampling_overrides,
  679:             locomotion_delta(
  680:                 agent_state.locomotion,
  681:                 gain_t=DEFAULT_LOCO_GAIN_T,
  682:                 gain_p=DEFAULT_LOCO_GAIN_P,
  683:             ),
  684:         )
  685:         system_prompt = build_system_prompt(persona, agent_state)
  686:         user_prompt = build_user_prompt(
  687:             observations,
  688:             memories,
  689:             world_model_entries=world_model_entries,
  690:             world_model_update_enabled=flag_on,
  691:         )
  692:         try:
  693:             resp = await self._llm.chat(
  694:                 [
  695:                     ChatMessage(role="system", content=system_prompt),
  696:                     ChatMessage(role="user", content=user_prompt),
  697:                 ],
  698:                 sampling=sampling,
  699:             )
  700:         except OllamaUnavailableError as exc:
  701:             logger.warning(
  702:                 "LLM unavailable for agent %s: %s 窶・continuing current action",
  703:                 agent_state.agent_id,
  704:                 exc,
  705:             )
  706:             return self._fallback(
  707:                 agent_state,
  708:                 new_memory_ids=new_memory_ids,
  709:                 reflection_triggered=reflection_triggered,
  710:                 new_physical=new_physical,
  711:                 world_model_runtime=reconciled,
  712:                 belief_classes=belief_classes,
  713:                 world_model_evidence=world_model_evidence,
  714:                 world_model_saturation=world_model_saturation,
  715:                 # Engagement instrument (Codex HIGH-1): this fallback returns before
  716:                 # step 7.5, so record a ``not_emitted`` disposition with a non-``ok``
  717:                 # ``llm_status`` to keep the per-(agent, tick) census complete. The
  718:                 # loader excludes non-``ok`` ticks from the eligible population, so the
  719:                 # fallback is provenance only 窶・out of the emission-rate denominator,
  720:                 # never an unrecorded gap. ``None`` flag-off (陬懷ｼｷ ﾂｧ4).
  721:                 world_model_hint_engagement=(
  722:                     build_not_emitted_disposition(
  723:                         llm_status=LLM_STATUS_UNAVAILABLE,
  724:                         exposed_entry_count=len(exposed_citations),
  725:                     )
  726:                     if flag_on
  727:                     else None
  728:                 ),
  729:             )
  730: 
  731:         # Step 7: parse the LLM plan (malformed 竊・same fallback branch).
  732:         plan = parse_llm_plan(resp.content)
  733:         if plan is None:
  734:             logger.warning(
  735:                 "LLM returned unparseable plan for agent %s (len=%d) 窶・fallback",
  736:                 agent_state.agent_id,
  737:                 len(resp.content),
  738:             )
  739:             return self._fallback(
  740:                 agent_state,
  741:                 new_memory_ids=new_memory_ids,
  742:                 reflection_triggered=reflection_triggered,
  743:                 new_physical=new_physical,
  744:                 world_model_runtime=reconciled,
  745:                 belief_classes=belief_classes,
  746:                 world_model_evidence=world_model_evidence,
  747:                 world_model_saturation=world_model_saturation,
  748:                 # Engagement instrument (Codex HIGH-1): unparseable plan also returns
  749:                 # before step 7.5 窶・record ``not_emitted`` with an ``unparseable``
  750:                 # status to keep the census complete (provenance only; excluded from

codex
`main..feat` の指定対象では src/scripts/tests は 4 ファイルだけでしたが、実際のブランチには experiments の committed artifact もあります。レビュー判断に影響する manifest/env の事実だけ確認し、コード指摘は指定 4 ファイル中心で返します。
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff --name-status main..feat/ecl-v0-live-run -- experiments/' in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff --stat main..feat/ecl-v0-live-run -- experiments/' in C:\ERRE-Sand_Box
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content experiments'"\\20260706-ecl-v0-live-capture\\env.md | ForEach-Object { "'$i++; '"'{0,5}: {1}' -f "'$i, $_ }' in C:\ERRE-Sand_Box
 succeeded in 273ms:
A	experiments/20260706-ecl-v0-live-capture/artifacts/decisions.jsonl
A	experiments/20260706-ecl-v0-live-capture/artifacts/ecl_trace.jsonl
A	experiments/20260706-ecl-v0-live-capture/artifacts/envelope_stream.jsonl
A	experiments/20260706-ecl-v0-live-capture/artifacts/manifest.json
A	experiments/20260706-ecl-v0-live-capture/env.md
A	experiments/20260706-ecl-v0-live-capture/ollama.log
A	experiments/20260706-ecl-v0-live-capture/repro.sh
A	experiments/20260706-ecl-v0-live-capture/run.sh

 succeeded in 296ms:
 .../artifacts/decisions.jsonl                      |  32 ++
 .../artifacts/ecl_trace.jsonl                      | 640 +++++++++++++++++++++
 .../artifacts/envelope_stream.jsonl                |  96 ++++
 .../artifacts/manifest.json                        |   1 +
 experiments/20260706-ecl-v0-live-capture/env.md    |  44 ++
 .../20260706-ecl-v0-live-capture/ollama.log        |   3 +
 experiments/20260706-ecl-v0-live-capture/repro.sh  |  42 ++
 experiments/20260706-ecl-v0-live-capture/run.sh    |  14 +
 8 files changed, 872 insertions(+)

 succeeded in 252ms:
    1: # env 窶・ECL v0 sealed live run (Issue 003, first-contact)
    2: 
    3: ## 螳溯｡檎腸蠅・(G-GEAR)
    4: - machine: G-GEAR (Windows 11縲∵悽菴懈･ｭ繝・ぅ繝ｬ繧ｯ繝医Μ = 螳溯｡梧ｩ・
    5: - OS: Windows 11 (bake side = UCRT libm)
    6: - Ollama: 0.31.1 (http://127.0.0.1:11434)
    7: - model: qwen3:8b (digest 500a1f067a9f7826縲・.2 GB)縲・*think=False** (ThinkOffChatClient wrapper縲，odex HIGH-1)
    8: - embedding: constant-vector mock (D-4縲［inimal reality surface = live 縺ｯ action LLM chat 縺ｮ縺ｿ縲〉eal
    9:   nomic-embed-text 荳堺ｽｿ逕ｨ)
   10: - VRAM: 16 GB
   11: - uv.lock sha256 (蜈磯ｭ): 9cc70f9dc5d61f6c
   12: - 譌･譎・ 2026-07-06 20:51-20:53 JST
   13: 
   14: ## 莠句燕逋ｻ骭ｲ protocol (sealed run 蜑榊崋螳壹》une-to-pass 蟆・事)
   15: - N_cognition=32 (D-1) / persona=kant, 蜊倅ｸ agent (D-2) / seed=0 / physics 20/cognition = 640 physics row
   16: - sampling = live cycle resolved 繧・verbatim 險倬鹸 (D-3縲》hink 縺ｮ縺ｿ False)
   17: - 隕ｳ貂ｬ驥・O1-O5縲．one=O1竏ｧO2竏ｧO3a竏ｧO3b (manifest observables overlay 縺ｫ pre-registered)
   18: 
   19: ## 邨先棡 (verdict = GO縲…onstruction validated)
   20: | 隕ｳ貂ｬ驥・| 邨先棡 |
   21: |---|---|
   22: | **O1 螳瑚ｵｰ** | 笨・32 cognition ﾃ・20 physics = 640 row縲∽ｾ句､悶↑縺丞ｮ瑚ｵｰ (exit 0) |
   23: | **O2 replay 蜀咲樟** | 笨・committed decisions 縺ｮ縺ｿ replay 竊・checksum byte 荳閾ｴ + inner_invocations==0 |
   24: | **O3a cross-platform** | 笨・**WSL Linux (glibc) replay = Windows (UCRT) checksum** `a528d547窶ｦ` byte 荳閾ｴ (libm cos/sin drift 繧・6譯・㍼蟄仙喧縺悟精蜿・ |
   25: | **O3b cross-platform** | 笨・蜷御ｸ raw Plane2 竊・artifact re-render SHA 縺・Linux/Windows 荳閾ｴ |
   26: | **Done=O1竏ｧO2竏ｧO3a竏ｧO3b** | 笨・**HOLDS** |
   27: | O5 parsed-history-dependent-action (annotation縲・撼 gate) | **32/32 tick** 縺ｧ `llm_status==ok` 竏ｧ `plan竕None` 竏ｧ MoveMsg `resolved_from==memory_centroid` (first-contact 蟄伜惠險ｼ譏弱′ 竕･1 繧貞､ｧ縺阪￥雜・℃縲Ｕhink=False 縺・load-bearing = 蜈ｨ tick parseable) |
   28: | O4 髱樒ｸｮ騾 (annotation縲・撼 gate) | distinct destination_zone = 2 ({peripatos:28, study:4})縲‥istinct move target = 32 (蜈ｨ tick 逶ｸ逡ｰ) |
   29: 
   30: replay_checksum (authoritative) = `a528d5472c3fc1b939ab151e0bdb8089a23a8b5ae39b7b7961aeed91d94cc249`
   31: 
   32: ## cross-platform 螳滓ｸｬ謇矩・(feedback_golden_crossplatform_float_drift)
   33: 1. Windows 縺ｧ `bash experiments/20260706-ecl-v0-live-capture/run.sh` 竊・artifacts/ 繧・bake (UCRT)縲・2. WSL Linux venv (`uv pip install .`縲“libc) 縺ｧ
   34:    `python scripts/ecl_v0_live_capture.py --verify --artifact-dir experiments/20260706-ecl-v0-live-capture/artifacts`
   35:    竊・replay checksum 縺・Windows-baked 縺ｨ byte 荳閾ｴ = **cross-platform hold 螳滓ｸｬ遒ｺ隱肴ｸ・*縲・3. CI (GitHub Actions Linux) 縺ｯ Issue 004 縺ｮ `test_ecl_live_golden.py` 縺・committed live artifact 繧・replay-verify
   36:    (Ollama-free) 縺吶ｋ縺溘ａ縲´inux CI 閾ｪ菴薙ｂ cross-platform gate縲・
   37: ## 蛻､螳・(霆ｸ5 = GO)
   38: Done (O1竏ｧO2竏ｧO3a竏ｧO3b) HOLDS + O5=32/32 + O4 髱樒ｸｮ騾 竊・**GO (construction validated)**縲・CL v0 organ 縺・real
   39: qwen3:8b 縺ｧ substrate 繧・end-to-end 鬧・虚縺励…aptured Plane2 縺ｮ縺ｿ縺ｧ cross-platform 縺ｫ deterministic replay縲・**construction validation 縺ｧ縺ゅ▲縺ｦ measurement verdict 縺ｧ縺ｪ縺・* (floor/landscape/verdict 髱槫・蜉帙”olding 荳榊庄萓ｵ)縲・谺｡ primary = 蛟呵｣・B (N菴灘喧) or C (measurement gate) 繧貞挨 ADR 縺ｧ (arc-close 蜊ｴ荳九・holding 邯咏ｶ・縲・

hook: PreToolUse
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
import json
from pathlib import Path
s=set()
for line in Path('experiments/20260706-ecl-v0-live-capture/artifacts/decisions.jsonl').read_text(encoding='utf-8').splitlines():
    d=json.loads(line)
    s.add(json.dumps(d['call']['sampling'], sort_keys=True))
print(len(s))
for item in sorted(s): print(item)
'@ | python -" in C:\ERRE-Sand_Box
 succeeded in 291ms:
1
{"repeat_penalty": 1.0, "temperature": 0.7, "top_p": 0.9}

codex
focused pytest は環境 DLL 権限で実行できませんでした。静的には `git diff --check` は通っており、以降は実行不能を残リスクとして扱います。
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Failed
hook: PreToolUse Failed
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Test-Path .venv\\Scripts\\ruff.exe) { .\\.venv\\Scripts\\ruff.exe format --check src\\erre_sandbox\\integration\\embodied\\live.py scripts\\ecl_v0_live_capture.py tests\\test_integration\\test_ecl_live_capture.py tests\\test_integration\\test_ecl_live_golden.py } else { ruff format --check src\\erre_sandbox\\integration\\embodied\\live.py scripts\\ecl_v0_live_capture.py tests\\test_integration\\test_ecl_live_capture.py tests\\test_integration\\test_ecl_live_golden.py }" in C:\ERRE-Sand_Box
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Test-Path .venv\\Scripts\\ruff.exe) { .\\.venv\\Scripts\\ruff.exe check src\\erre_sandbox\\integration\\embodied\\live.py scripts\\ecl_v0_live_capture.py tests\\test_integration\\test_ecl_live_capture.py tests\\test_integration\\test_ecl_live_golden.py } else { ruff check src\\erre_sandbox\\integration\\embodied\\live.py scripts\\ecl_v0_live_capture.py tests\\test_integration\\test_ecl_live_capture.py tests\\test_integration\\test_ecl_live_golden.py }" in C:\ERRE-Sand_Box
2026-07-06T12:16:42.382754Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.3 seconds
Output:
プログラム 'ruff.exe' の実行に失敗しました: Access is denied発生場所 行:2 文字:41
+ ... ruff.exe) { .\.venv\Scripts\ruff.exe check src\erre_sandbox\integrati ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~。
発生場所 行:2 文字:41
+ ... ruff.exe) { .\.venv\Scripts\ruff.exe check src\erre_sandbox\integrati ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ResourceUnavailable: (:) [], ApplicationFailedException
    + FullyQualifiedErrorId : NativeCommandFailed
 

 exited 1 in 336ms:
プログラム 'ruff.exe' の実行に失敗しました: Access is denied発生場所 行:2 文字:41
+ ... ruff.exe) { .\.venv\Scripts\ruff.exe check src\erre_sandbox\integrati ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~。
発生場所 行:2 文字:41
+ ... ruff.exe) { .\.venv\Scripts\ruff.exe check src\erre_sandbox\integrati ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ResourceUnavailable: (:) [], ApplicationFailedException
    + FullyQualifiedErrorId : NativeCommandFailed
 

2026-07-06T12:16:42.388361Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.3 seconds
Output:
プログラム 'ruff.exe' の実行に失敗しました: Access is denied発生場所 行:2 文字:41
+ ... ruff.exe) { .\.venv\Scripts\ruff.exe format --check src\erre_sandbox\ ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~。
発生場所 行:2 文字:41
+ ... ruff.exe) { .\.venv\Scripts\ruff.exe format --check src\erre_sandbox\ ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ResourceUnavailable: (:) [], ApplicationFailedException
    + FullyQualifiedErrorId : NativeCommandFailed
 

 exited 1 in 342ms:
プログラム 'ruff.exe' の実行に失敗しました: Access is denied発生場所 行:2 文字:41
+ ... ruff.exe) { .\.venv\Scripts\ruff.exe format --check src\erre_sandbox\ ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~。
発生場所 行:2 文字:41
+ ... ruff.exe) { .\.venv\Scripts\ruff.exe format --check src\erre_sandbox\ ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ResourceUnavailable: (:) [], ApplicationFailedException
    + FullyQualifiedErrorId : NativeCommandFailed
 

codex
**HIGH**
- [scripts/ecl_v0_live_capture.py](C:/ERRE-Sand_Box/scripts/ecl_v0_live_capture.py:247) and [tests/test_ecl_live_golden.py](C:/ERRE-Sand_Box/tests/test_integration/test_ecl_live_golden.py:155): O3b does not verify the full artifact set. `capture()` writes `manifest.json` after `attach_live_observables()` at [line 169](C:/ERRE-Sand_Box/scripts/ecl_v0_live_capture.py:169), but `verify()` only compares `ecl_trace.jsonl`, `decisions.jsonl`, and `envelope_stream.jsonl`. A drifted or stale committed `manifest.json`, including `env_pins` or the sealed observables overlay, can pass replay-verify.  
  Recommended fix: re-render `manifest.json` with committed `run`/`env_pins`, apply `attach_live_observables()`, and byte-compare it with committed `manifest.json`. Add the same assertion to `test_live_golden_artifact_rerender_sha`.

**MEDIUM**
- [scripts/ecl_v0_live_capture.py](C:/ERRE-Sand_Box/scripts/ecl_v0_live_capture.py:129): live capture relies on `OllamaChatClient()`’s default model rather than pinning the protocol model locally. Today that default is `qwen3:8b`, but the sealed-run apparatus itself does not enforce it, while `run.sh` and manifest metadata can still claim qwen3.  
  Recommended fix: add a live protocol constant such as `LIVE_MODEL = "qwen3:8b"`, instantiate `OllamaChatClient(model=LIVE_MODEL)`, and record the model tag in `env_pins`.

**Checks**
- Existing seam binding: no diff to `loop.py`, `cycle.py`, `world/tick.py`, `handoff.py`, or `ecl_v0_golden.py`.
- Measurement non-reentry: no evidence/spdm/runningness imports in reviewed code; no floor/landscape/verdict calculation path found.
- ThinkOffChatClient path: `think=False` is forced correctly and `OllamaUnavailableError` propagation remains compatible with record-mode capture.
- I could not run pytest/ruff locally: `uv` cache, `.venv` DLL, and `ruff.exe` all hit access-denied errors in this environment.

Verdict: **Adopt-with-changes**
hook: Stop
hook: Stop Failed
tokens used
120,435
**HIGH**
- [scripts/ecl_v0_live_capture.py](C:/ERRE-Sand_Box/scripts/ecl_v0_live_capture.py:247) and [tests/test_ecl_live_golden.py](C:/ERRE-Sand_Box/tests/test_integration/test_ecl_live_golden.py:155): O3b does not verify the full artifact set. `capture()` writes `manifest.json` after `attach_live_observables()` at [line 169](C:/ERRE-Sand_Box/scripts/ecl_v0_live_capture.py:169), but `verify()` only compares `ecl_trace.jsonl`, `decisions.jsonl`, and `envelope_stream.jsonl`. A drifted or stale committed `manifest.json`, including `env_pins` or the sealed observables overlay, can pass replay-verify.  
  Recommended fix: re-render `manifest.json` with committed `run`/`env_pins`, apply `attach_live_observables()`, and byte-compare it with committed `manifest.json`. Add the same assertion to `test_live_golden_artifact_rerender_sha`.

**MEDIUM**
- [scripts/ecl_v0_live_capture.py](C:/ERRE-Sand_Box/scripts/ecl_v0_live_capture.py:129): live capture relies on `OllamaChatClient()`’s default model rather than pinning the protocol model locally. Today that default is `qwen3:8b`, but the sealed-run apparatus itself does not enforce it, while `run.sh` and manifest metadata can still claim qwen3.  
  Recommended fix: add a live protocol constant such as `LIVE_MODEL = "qwen3:8b"`, instantiate `OllamaChatClient(model=LIVE_MODEL)`, and record the model tag in `env_pins`.

**Checks**
- Existing seam binding: no diff to `loop.py`, `cycle.py`, `world/tick.py`, `handoff.py`, or `ecl_v0_golden.py`.
- Measurement non-reentry: no evidence/spdm/runningness imports in reviewed code; no floor/landscape/verdict calculation path found.
- ThinkOffChatClient path: `think=False` is forced correctly and `OllamaUnavailableError` propagation remains compatible with record-mode capture.
- I could not run pytest/ruff locally: `uv` cache, `.venv` DLL, and `ruff.exe` all hit access-denied errors in this environment.

Verdict: **Adopt-with-changes**

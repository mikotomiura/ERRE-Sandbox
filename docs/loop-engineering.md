# Loop Engineering — 単一 SSOT

## 目的
短い・検証可能・記録可能な issue 単位ループで、有界自律実行 (/goal) を
worktree 隔離のもと安全に回す。人が目視できる監視ファイルを中核に置く。

## 基本単位
- task        : 1 つのまとまった開発目標 (例: add-user-auth)。1 retrospective に対応。
- issue       : task を割った vertical slice。1 issue = 1 worktree = 1 PR 候補。
- loop        : 1 issue に対する attempt の列 (execute → verify → done/stop)。
- goal        : /goal による 1 セッションの有界自律実行 (executor)。
- checkpoint  : events.jsonl の 1 状態遷移行 (attempt_start / test_fail / issue_done 等)。
- retrospective: task 完了時の学習記録 (次ループへの入力)。

## 原則
1. **1 issue = 1 worktree = 1 PR 候補**。issue は vertical slice で切る (縦に薄く貫く)。
2. **/goal は executor でありセッションにつき 1 回**。完了判定は fast model が
   トランスクリプト基準で行い、テストを独立実行しない → 「done」は自己申告。
   だから **客観検証 (exit code) を events.jsonl に別記録**し、重要 issue は
   watchdog が独立再実行する。
3. **grill を goal の前段に置く**。要件を adaptive に詰めてから issue 化・実行する。
4. **worktree 隔離**。共有する監視ファイルは main checkout の絶対パス 1 か所に集約。
   worktree 内 `.steering` に書くと他端末から見えない。

## Done Condition (issue 完了の条件・すべて満たす)
- [ ] Acceptance Criteria を全項目充足 (AC↔test マッピングで対応 test が緑)
- [ ] test / typecheck / lint がすべて緑 (pin 済み verify コマンドの exit 0)
- [ ] Execution Result に summary を記載 (PR 本文になる)
- [ ] 未解決事項・既知の制約を明記
- [ ] PR 説明 (背景・変更点・検証方法) を用意

## Stop Condition (即時停止し人にエスカレートする条件・いずれか)
- 要件が曖昧 (AC を確定できない)
- scope 外の変更が必要になった (Allowed Files を超える)
- 同一 failure が連続 (同一 fingerprint の反復)
- 原因不明 (前進の見込みが立たない)
- security に関わる判断が必要
- 新規依存の追加が必要

## Budget 方針
- `max_attempts`           : 1 issue あたりの attempt 上限 (既定 6)。
- `no_progress_threshold`  : 同一 fingerprint がこの回数連続したら停止 (既定 4)。
- `token_ceiling`          : task 全体の token 上限 (既定 2,000,000)。
- `parallel`               : 同時 worktree 数 (既定 3)。
- **no-progress fingerprint**: `sha1(失敗test id + error種別 + file:line)`。
  同一 fingerprint が連続すると loop-guard.sh が数え、budget 内でも停止する。

## Events 語彙 (events.jsonl の event 値・全 10 種)
`attempt_start` | `test_pass` | `test_fail` | `typecheck_fail` | `lint_fail` |
`no_progress_stop` | `scope_violation` | `blocked` | `issue_done` | `abandoned`
1 状態遷移 = 1 行 append (worker が main checkout の絶対パスへ)。board は書かない。

## Board 状態機械
`queued(⏳) → running(🔄) → verifying → review → done(✅)` / 逸脱 `blocked(⛔)` / 断念 `abandoned`。
board は events を issue ごとに畳んだ (最終 event 優先) 表示。単一書き手 (dashboard 端末) のみ再描画。

## パス規約 (この repo の正・canonical README からの意図的逸脱)
Loop の管理ファイルは研究 steering (`.steering/`) と混在させず、専用のトップ階層
`loop/` に集約する。canonical README-loop-engineering.md §2.1/§2.2 は `.steering/`
配下を例示するが、本 repo は運用容易性のため以下を **SSOT の正** とし、下流 phase
(L2–L7) はこの規約を README の例より優先する。逸脱根拠は
`.steering/<loop-integration-task>/decisions.md` に記録。

- テンプレ (固定):
  - `loop/_templates/loop-config.json`
  - `loop/_templates/loop-issue.md`
  - `loop/_templates/loop-retrospective.md`
- タスク実行時 runtime (main checkout の絶対パス 1 か所に集約):
  - `loop/[YYYYMMDD]-[task]/_loop-config.json`
  - `loop/[YYYYMMDD]-[task]/_loop-events.jsonl`   (append 専用)
  - `loop/[YYYYMMDD]-[task]/_loop-board.md`        (単一書き手)
  - `loop/[YYYYMMDD]-[task]/issues/00X.md`
  - `loop/[YYYYMMDD]-[task]/retrospective.md`

worktree からは main checkout の絶対パスで `loop/[task]/_loop-events.jsonl` に append
する (集約先が `.steering` でなく `loop/` になるだけで、worktree 可視性の設計理由は不変)。

<!-- loop:codex:begin -->
## Codex ゲート (任意・タスク境界のみ)

> 本 repo の Codex 連携は canonical `README-loop-engineering.md` が前提とする
> `.claude/skills/codex-consult`/`codex-review` bridge skill や `/cross-review` command
> ではなく、CLAUDE.md 記載の **直接 CLI 手順** (`codex exec --skip-git-repo-check` 直呼び)
> で実在する (`.codex/config.toml` / `.codex/budget.json` / `.codex/agents/*.toml` /
> `.agents/skills/erre-workflow/SKILL.md`)。以下は canonical の 2 ゲート構成を、この
> 実体に合わせて直接 CLI 手順へ読み替えたもの (DA-LOOP-1 伝播 (b)、
> `.steering/20260701-loop-engineering-integration/decisions.md` 参照)。

| 高度 | 担当 | model | 頻度 | 権限 |
|---|---|---|---|---|
| issue ループ内 (毎 attempt) | `loop-guard.sh` / `loop-watchdog` | script / Haiku | 高頻度・安価 | 監視・停止のみ |
| **タスク境界 (前)** | Codex CLI 直呼び (TASK-PRE) | gpt-5.5 / xhigh | task 毎 1 回 | read-only |
| **タスク境界 (後)** | Codex CLI 直呼び (TASK-POST) + code-reviewer 突き合わせ | gpt-5.5 ∥ Opus | task 毎 1 回 | read-only |

コスト根拠: マルチエージェント構成はトークンを ~15x 消費しうるため、Codex は issue 単位でなく
**task 単位で 2 ゲートに固定**する。issue 内の意味判断は Haiku watchdog (安価) が担う。

### TASK-PRE: issue 独立性の第二意見 (Codex CLI 直呼び, read-only)

grill → to-issues で issue が確定した**直後**、`loop-issue` による実行を始める**前**に
1 回だけ実行する。

1. issue 一覧の公開可能な最小抜粋 (各 issue の Goal / Scope In-Out / Allowed Files /
   Dependencies / AC↔test) を人が整形し、`.steering/[YYYYMMDD]-[task]/codex-review-prompt.md`
   に依頼内容として書く (機密/proprietary 情報を含めないこと。本 repo に secrets-filter.sh は
   無いため、フィルタは人手で徹底する)。設問を固定する:
   - これらの issue は**本当に独立/並列化可能**か。隠れた共有状態・暗黙の順序依存は無いか。
   - 抜けている**エッジケース**は何か。
   - **順序ハザード** (先行 merge が後続の前提を壊す、schema/API の破壊的変更順) は無いか。
   - vertical slice の切り方に、後で衝突する分割はないか。
2. `cat .steering/[YYYYMMDD]-[task]/codex-review-prompt.md | codex exec --skip-git-repo-check`
   で実行する (CLAUDE.md 記載の標準手順)。`.codex/budget.json` の `daily_token_budget` を
   超過する見込みなら呼ばない (CLAUDE.md「呼ばない場面」節)。
3. 出力を `.steering/[YYYYMMDD]-[task]/_codex-preplan.md` に **verbatim 保存**する。
4. **これは助言**。採否は人が決める。盲点は issue/Dependencies に反映し、誤検知 (Codex は
   文脈の半分しか持たない) は却下理由を preplan に併記する。
5. Codex CLI 疎通不能 (auth expire 等、`feedback_codex_auth_long_session_expiry` memory 参照)
   の場合は「Codex 呼び出し失敗」を preplan に記録し、人手レビューのみで進める
   (静かに失敗させない)。

TASK-POST (統合 diff の二者レビュー) は **`/cross-review` command** が担う
(`.claude/commands/cross-review.md` が手順 SSOT)。`loop-issue.md` の同マーカ節はそれを呼ぶ薄い
ポインタ。`/cross-review` は code-reviewer(Opus) と Codex(gpt-5.5, `codex exec` 直呼び) の二者
レビューを統合 diff に行い、Codex への secrets 非パイプ・budget 承認・read-only sandbox・
疎通不能/budget 超過時の code-reviewer 単独 degrade を command 内で扱う (SSOT 二重定義回避のため
本ファイルには複製しない)。
<!-- loop:codex:end -->

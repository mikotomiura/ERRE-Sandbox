# security-hardening-pre-m10

`codex_issue.md` (2026-05-12 Codex 12th review、PR #161 で §6 LOW のみ trivial 消化済)
の HIGH-1 / MEDIUM-2 / MEDIUM-3 / MEDIUM-4 / LOW-5 を統合した、M10 公開前の
defense-in-depth ハードニングタスク。

## 背景

Codex 12th review が「ランタイム本体に即時悪用できる HIGH は無いが、運用ガードと
LAN 境界に強めの改善余地」と判定 (`codex_issue.md`)。実害の証拠も累積:

- **2026-05-09 / 2026-05-13** Phase B audit json で CRLF 由来の md5 mismatch
  (PR #161 で `.gitattributes` 投入し §6 close)
- **§1 HIGH (hook shell bypass)**: Codex hook (`apply_patch|Edit|Write` matcher のみ)
  と CI gate (`.github/workflows/ci.yml` eval-egress-grep-gate のみ) の **defense
  layer が同型に欠落**、`exec_command` 経由の `sed -i` / `tee` / `python -c` /
  redirect で禁止 import (`openai` / `anthropic` / `bpy`) や `.steering` skip が
  両層を通過する
- **§2 MEDIUM (WebSocket `0.0.0.0` default + no auth)**: `__main__.py` /
  `bootstrap.py` / `integration/gateway.py` で LAN 公開 default 無認証、Mac↔G-GEAR
  rsync workflow は LAN 内前提なので `127.0.0.1` 強制は実害だが、token + Origin
  + active session cap は不可逆破綻防止に必要
- **§3 MEDIUM (Codex network)**: `.codex/config.toml` の `web_search = "live"` +
  `[sandbox_workspace_write] network_access = true` の同居。web_search 実利
  (memory `project_m9_b_plan_pr.md`: SGLang v0.3+ multi-LoRA 発見) と
  workspace write 時の外送リスクは分離可能
- **§4 MEDIUM/LOW (`--memory-db` unlink)**: `cli/eval_run_golden.py` が任意 path を
  unlink、symlink follow 余地、誤指定で sqlite 消滅可能
- **§5 LOW (queue unbounded)**: `world/tick.py` `_envelopes` `asyncio.Queue()`
  maxsize なし、長時間運用で memory 増加が観測困難

M10 (Individual layer activation) で WebSocket 経路は UI client 増 + agent 多重化で
blast radius 拡大が確定。**M10 着手前に基盤強化** が筋。

## ゴール

`codex_issue.md` §1 / §2 / §3 / §4 / §5 の 5 件について、**Plan mode + `/reimagine`
+ Codex 13th independent review** で代替設計を確定し、本体・hook・CI・運用設定の
3 層で defense-in-depth を完成させる。M10-0 source_navigator scaffold への前提条件
を整える。

## スコープ

### 含むもの

- **§1 HIGH**: `.codex/hooks/pre_tool_use_policy.py` の matcher に exec_command 系
  を追加 + shell 内書き込みパターン deny + CI grep gate に同等規律
- **§2 MEDIUM**: WebSocket gateway の **shared token + Origin check + max sessions
  cap** (Mac↔G-GEAR LAN 運用との互換性維持、`0.0.0.0` default 据置)
- **§3 MEDIUM**: `.codex/config.toml` の `[sandbox_workspace_write] network_access`
  を false に下げ、`web_search = "live"` は維持 (部分採用)
- **§4 MEDIUM/LOW**: `eval_run_golden.py --memory-db` の symlink reject +
  `--overwrite-memory-db` flag 必須化 + allowed prefix (`var/eval/` / `/tmp/erre-*`)
- **§5 LOW**: `world/tick.py` envelope queue に bounded queue + overflow metrics
  counter (drop は heartbeat 系のみ、dialog/error/reasoning は別 queue 維持)

### 含まないもの

- M9-eval Phase 2 P6 (Tier C systemd) / Phase 3 Closure → 別 milestone
- M9-B LoRA training execution → 別 milestone
- M9-C-spike Phase G-J → 別 milestone
- M10-0 source_navigator scaffold (`idea_judgement.md`) → 別タスク (本タスク完了後)
- WebSocket default を `127.0.0.1` に変更する案 → Mac↔G-GEAR LAN rsync 実害
  (memory `feedback_crlf_canonical_for_md5.md`) のため不採用方針
- web_search 完全 off → SGLang v0.3+ multi-LoRA 発見実績 (memory
  `project_m9_b_plan_pr.md`) のため不採用方針
- M9-eval golden baseline 30 cells (PR #160 merged) への影響 → **完全に触らない**

## 受け入れ条件

- [ ] **§1**: hook + CI の両層で shell 書き込み bypass が blocked、red-team test
      (`sed -i`, `tee`, `python -c "...write..."`, `cat > src/erre_sandbox/x.py`)
      で禁止 import / `.steering` skip が 100% 検出
- [ ] **§2**: WebSocket gateway が `X-Erre-Token` ヘッダなしで `/ws/observe`
      reject、Origin 不一致 reject、Registry max session cap (default 4) 超過時
      handshake reject、Mac↔G-GEAR LAN rsync workflow が token 付きで継続動作
- [ ] **§3**: `.codex/config.toml` で `network_access = false` (workspace write 時
      外送 off)、`web_search = "live"` は維持、AGENTS.md に「network 有効化が
      必要な作業は明示承認」運用ノート追記
- [ ] **§4**: `eval_run_golden.py` が `--overwrite-memory-db` なしで既存ファイルを
      unlink しない、symlink 拒否、prefix 違反で argparse error、`tests/test_cli/
      test_eval_run_golden.py` に red-team ケース 3 件追加
- [ ] **§5**: `world/tick.py` `_envelopes` が bounded (default 1024)、overflow
      時 metrics counter increment + warning envelope、dialog/error/reasoning は
      別 queue で欠落不可、既存 `tests/test_world/` 緑
- [ ] **CI**: `uv run ruff check src tests` / `uv run mypy src` / `uv run pytest -q`
      全緑、red-team test 全 PASS
- [ ] **設計品質**: Plan mode + `/reimagine` で初回案破棄、Codex 13th `gpt-5.5
      xhigh` independent review HIGH/MEDIUM 全反映
- [ ] **記録**: `decisions.md` に 5 件分 ADR (`SH-1` 〜 `SH-5`)、`.steering/`
      レビュー資産 (codex-review-prompt + codex-review verbatim) 配置
- [ ] **M9 baseline 不可侵**: `git diff main..` で `data/eval/golden/` / 既存
      `src/erre_sandbox/evidence/` への変更が 0

## 関連ドキュメント

- `codex_issue.md` (2026-05-12 Codex 12th review、本タスクで `.steering/` 配下に
  `codex-12th-review-source.md` として移管)
- `docs/architecture.md` §LAN 公開 / WebSocket gateway
- `docs/development-guidelines.md` §security / hook
- memory `feedback_crlf_canonical_for_md5.md` (LAN rsync canonical)
- memory `project_m9_b_plan_pr.md` (web_search 実利の empirical 証拠)
- memory `project_pr159_m10_0_design_draft_merged.md` (M10-0 phasing context)
- PR #161 (`fix/m9-eval-json-lf-normalization`、`codex_issue.md` §6 LOW close 済)

## 運用メモ

- **破壊と構築 (/reimagine) 適用**: **Yes**
- **理由**: §1 (hook + CI どちらを first defense にするか) / §2 (token 方式 vs
  Origin allowlist vs mTLS) / §3 (network_access partition の粒度) / §5
  (queue 分割の境界) で複数案ありうる設計、運用文脈 (Mac↔G-GEAR LAN rsync /
  web_search 実利) と衝突する単発案を構造的に排除する必要。CLAUDE.md「高難度設計
  で `/reimagine` を省略しない」に該当
- **Codex 13th independent review**: 必須 (`codex_issue.md` の原著者である Codex
  自身に「Claude の代替設計が原 finding の意図を loss なく解決しているか」を
  closure 評価させる、第三者性確保)

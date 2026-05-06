# m9-eval-cli-partial-fix

> **Source spec**: `.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`
> (ME-9 ADR の hand-off。本 requirement はその実装側 task 起票で、spec を
> verbatim 取り込まず **意図と受け入れ条件のみ** を要約する。詳細仕様は spec を直参照)

## 背景

Phase 2 run0 で 3 cell が wall=360 min で FAILED (focal=381/390/399 prefix
censored)。Codex `gpt-5.5 xhigh` 6 回目 review が Claude 単独案の HIGH 4 件を
切出した (`codex-review-phase2-run0-timeout.md` verbatim)。HIGH の核は

1. **HIGH-3** (partial masquerade contract): 現 `_SinkState.fatal_error` を流用
   して wall timeout を報告すると "fatal" 概念に partial 結果が混入し、後段の
   `eval_run_master_runner` の return 2 ガードと矛盾する。
2. **M3** (`eval_audit` CLI 未実装): G-GEAR launch prompt は audit gate を要求
   しているが本体に未実装で、partial / complete を機械判定する手段が無い。
3. **HIGH-4** (stale `.tmp` rescue): 自動 unlink は partial を silently 破棄
   する危険があり、sidecar 存在下では明示 flag を要求すべき。
4. **HIGH-2** で sample-size correction 自体は別 ADR 案で破綻 (本タスクで再採用
   しない) → 残るは contract 層と audit gate の整備。

ME-9 ADR でこれらを (a) `eval_run_golden.py` の `soft_timeout` 分離 + sidecar
unconditional write + return-code 体系再設計、(b) `eval_audit.py` 新設 (single
+ batch)、(c) stale-rescue safety gate (`--allow-partial-rescue`) の 3 系統で
吸収することが確定済み (本タスクは実装フェーズ)。

## ゴール

ME-9 ADR の実装を完了し、Phase 2 run1 calibration 着手のための前提
(partial を機械的に区別できる CLI contract + audit gate) を整備する。
具体的には以下が満たされた状態:

- `eval_run_golden.py` が wall timeout 時に **partial** として明示的に publish
  でき、fatal とは別 return code で分離されている
- 全 capture が `<output>.capture.json` sidecar を **unconditional** で残す
- `eval_audit` CLI で `--duckdb` 単発 / `--duckdb-glob` batch の双方を機械判定可能
- stale `.tmp` の自動 unlink は sidecar が存在する場合 `--allow-partial-rescue`
  なしでは refuse される
- 既存 `test_eval_run_golden.py` の rewrite 範囲が PR description に明示され、
  新規 unit 7-9 件 (CLI fix + audit) が追加され、**test suite 全 PASS**
- PR merge 後 `g-gear-p3-launch-prompt.md` が新 contract (wall budget +
  run1 calibration step + audit step) で更新されている

## スコープ

### 含むもの

- `src/erre_sandbox/cli/eval_run_golden.py` の改修
  (`_SinkState.soft_timeout` 新設 / `_watchdog` 修正 / `CaptureResult` 拡張 /
  sidecar `.capture.json` atomic write / return-code 体系 / stale-tmp safety gate)
- `src/erre_sandbox/cli/eval_audit.py` 新設 (single-cell + batch + JSON report)
- `tests/cli/test_eval_run_golden.py` の rewrite + 新規 unit
- `tests/cli/test_eval_audit.py` 新設
- 既存 caller (`eval_run_master_runner` 等) の return-code ハンドリング更新
- `g-gear-p3-launch-prompt.md` の launch 手順更新
- Codex `gpt-5.5 xhigh` independent review (実装着手前) と
  `codex-review-cli-fix.md` verbatim 保存

### 含まないもの

- HIGH-2 sample-size correction (ME-9 ADR で defer 確定、本タスク再採用しない)
- Phase 2 run1 の実走 (本タスクは CLI / audit 整備のみ、実走は別タスク)
- vLLM / SGLang LoRA 関連の改修 (M9-B 系統)
- `eval_audit` の policy 拡張 (例: per-persona threshold) は M9 後に持ち越し
- `eval_run_master_runner` の本格 refactor (return-code ハンドリング最小修正のみ)

## 受け入れ条件

- [ ] `eval_run_golden.py` が ME-9 ADR の spec 通りに改修されている
  (soft_timeout 分離、sidecar unconditional write、return code 0/2/3、
  stale-tmp safety gate)
- [ ] `eval_audit.py` が新設され、single (return 0/4/5/6) + batch (JSON report)
  双方をサポートする
- [ ] sidecar `.capture.json` schema は spec の v1 (schema_version="1") で
  atomic temp+rename で書かれる
- [ ] 新規 unit test が CLI fix 5 件 + audit 7 件以上で全 PASS
- [ ] 既存 `test_eval_run_golden.py` の rewrite 範囲が PR description に明示
- [ ] `pytest -q` 全 PASS、`ruff check` / `ruff format --check` / `mypy` 全 PASS
- [ ] Codex `gpt-5.5 xhigh` independent review を **着手前** に実施し、
  `codex-review-cli-fix.md` verbatim 保存。HIGH 全反映、MEDIUM 採否を
  `decisions.md` に記録、LOW は `blockers.md` 持ち越し可
- [ ] `g-gear-p3-launch-prompt.md` を新 contract で更新
- [ ] PR description で `cli-fix-and-audit-design.md` および
  `codex-review-cli-fix.md` をリンク参照

## 関連ドキュメント

- spec hand-off: `.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`
- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
- incident: `.steering/20260430-m9-eval-system/blockers.md` "active incident:
  Phase 2 run0 wall-timeout (2026-05-06)"
- Codex review (incident): `.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.md`
- 関連メモリ: `project_m9_eval_phase2_run0_incident.md`
- docs: `docs/architecture.md` (CLI / eval 層)、
  `docs/development-guidelines.md` (CLI return-code 規約)

## 運用メモ

- 破壊と構築 (`/reimagine`) 適用: **Yes (必須)**
- 理由: CLAUDE.md 高難度判定の 3 条件すべてに該当
  - **公開 API / 外部 contract 変更**: return-code 体系 (0/2/3 + audit 0/4/5/6)
    と sidecar schema は他 CLI / launch prompt から参照される外部 contract
  - **難バグ寄りの設計判断**: partial vs fatal の境界、drain timeout の扱い、
    stale-tmp rescue の安全弁 など、解釈ミスでサイレント破損を生む領域
  - **複数案ありうる設計**: 案 A (soft_timeout 分離 + sidecar、ME-9 ADR の
    現案) と案 B (lifecycle hook で contract layer を抽出する別構造)
    を Plan mode 内で並べて比較する
- 着手前 Codex `gpt-5.5 xhigh` independent review **必須**: HIGH 全反映後に実装着手

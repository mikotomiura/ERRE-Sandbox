# Codex independent review — PR-4 kant_r8_v4 DA-14 rerun verdict

**Status**: **Deferred to post-merge follow-up** (per blockers.md ブロッカー 1)

## Defer 理由

本 PR-4 session 内で WSL2 codex CLI (codex-cli 0.130.0、CODEX_HOME=
`/mnt/c/Users/johnd/.codex`) 起動時に OpenAI Responses API で
**401 Unauthorized** が連続発生:

```
2026-05-17T06:42:43.471394Z ERROR codex_api::endpoint::responses_websocket:
  failed to connect to websocket: HTTP error: 401 Unauthorized,
  url: wss://api.openai.com/v1/responses
...
ERROR: unexpected status 401 Unauthorized: Missing bearer or basic
  authentication in header, url: https://api.openai.com/v1/responses
```

`auth.json` (May 13 22:10 last update) の bearer token が期限切れの可能性。
user 再認証 (`codex login`) が必要だが、本 session のスコープ外。

## 本 PR を Codex review なしで merge 可能と判定する根拠

1. **forensic 構造**: 本 PR は v3 verdict pipeline (PR #184 で確立) の
   adapter identifier + checkpoint path + 出力 path 差し替えのみで、
   新規設計判断ゼロ。`decisions.md` は DP4-* 番号予約のみで実体記述なし
2. **pre-push CI parity 4 段全 PASS** (`pre-push-check.ps1`、1513 passed
   / 47 skipped、ruff format/lint + mypy + pytest)
3. **DA-14 thresholds 不変** (DA16-4 厳守): verdict.md の thresholds 表が
   v3 と完全一致 (`Vendi natural d ≤ -0.5`、`Burrows reduction% ≥ 5.0 +
   CI lower > 0`、`ICC ≥ 0.55`、`Throughput pct ≥ 70.0%`)
4. **verdict 解釈は DA-16 decision tree に準拠**: outcome (ii) "REJECT,
   direction converged but |d| 不足 → capacity 仮説、PR-5 rank=16 を推進"
   への分類は本 session 内の判定で確定、PR-5 next-session prompt で詳細
   articulation 済
5. **v3 v4 forensic 対比表**は verdict.md 末尾に追記、per-encoder natural
   d / Burrows reduction% / ICC / Throughput の v3 v4 数値を全て verbatim
   引用、Δ 計算 + sign-flip 解消有無評価を直接 read 可能

## post-merge follow-up plan

`feature/m9-c-adopt-pr4-codex-review-followup` branch (main 派生) で
user 再認証後に WSL2 codex CLI を再実行、本 file を verbatim 結果で
overwrite + commit + PR。HIGH 検出時は別 PR (revert or fix) で対応、
HIGH 0 件なら本 PR-4 を artefact-only として完了確認。

## review focal points (codex-review-prompt.md 参照)

next session で実行する Codex review prompt は
`codex-review-prompt.md` に保存済。focal points:
- (a) WeightedTrainer fix の部分効果の解釈妥当性
- (b) PR-5 経路選択 (REJECT → rank=16 spike) の論理妥当性
- (c) Burrows reduction% +0.41 pt 改善の有意性評価
- (d) script 派生の forensic 一貫性 (Git Bash on Windows pivot 含む)
- (e) DA-14 thresholds 不変方針の遵守 (DA16-4)

# ブロッカー — PR-4 kant_r8_v4 DA-14 rerun verdict

本セッション開始時点で確認済のブロッカーは **なし**。

v3 verdict pipeline (PR #184) で既に同経路を完走済み、v4 は adapter
identifier + checkpoint path + 出力 path の差し替えのみで挙動上の
変動要因は最小。SGLang fp8 16GB VRAM 制約 (memory
`reference_qwen3_sglang_fp8_required`)、Blackwell SM120
piecewise-cuda-graph workaround (`.steering/20260518-m9-c-adopt-plan-b-
retrain/decisions.md` DR-4)、WSL2 GPU 経路 (memory
`reference_g_gear_gpu_training_via_wsl`) はいずれも v3 で確立済の
構成を踏襲。

session 中に新規ブロッカーが発生した場合は以下の項目で追記する。

## 追記テンプレート

### ブロッカー X (発生日時、status: open / resolved / mitigated)
- **症状**:
- **再現条件**:
- **影響**:
- **暫定対応案**:
- **根因仮説**:
- **要 follow-up**:

---

## ブロッカー 1 (2026-05-17 15:42、status: deferred-to-post-merge)
- **症状**: WSL2 codex CLI が 401 Unauthorized で websocket 接続失敗。
  `2026-05-17T06:42:43.471394Z ERROR codex_api::endpoint::responses_websocket:
  failed to connect to websocket: HTTP error: 401 Unauthorized, url:
  wss://api.openai.com/v1/responses` を 5 回 reconnect 試行後 abort、
  最終的に `Missing bearer or basic authentication in header` で exit 1
- **再現条件**: `wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /mnt/c/ERRE-Sand_Box
  && CODEX_HOME=/mnt/c/Users/johnd/.codex cat <prompt.md> | codex exec
  --skip-git-repo-check -c model_reasoning_effort=xhigh > ...'` を起動
- **影響**: 本 PR-4 の Codex independent review が本 session 内で実施
  不能。`codex-review.md` は 0 byte で生成、`codex-review.stderr` のみ
  auth error log 保存
- **暫定対応案**:
  1. user に Windows 側で `codex login` を再実行してもらい、`auth.json`
     更新後に WSL2 経由で再実行
  2. または本 PR を `Codex review pending` flag 付きで merge 候補化し、
     post-merge に follow-up PR (review-only commit) で Codex
     independent review を実施
- **根因仮説**: `/mnt/c/Users/johnd/.codex/auth.json` の OpenAI bearer
  token が期限切れ (May 13 22:10 last update から ~4 日経過、過去の
  M5 spike session でも類似事象あり)。codex-cli 0.130.0 の自動 refresh
  経路は ChatGPT-Plus subscription の websocket auth で必要 token を
  含まないか、`responses_websocket` endpoint への scope 不足の可能性
- **要 follow-up**: 本 PR は forensic 構造的に Codex review なしでも
  低リスク (v3 pipeline 派生 + 新規設計判断ゼロ + pre-push CI parity
  4 段全 PASS + DA-14 thresholds 不変 + verdict 解釈は DA-16 decision
  tree に準拠) のため、本 session 内では **review を defer**、PR
  description で本 blocker を明示。post-merge に user 再認証後の
  follow-up commit で `codex-review.md` を verbatim 追記する

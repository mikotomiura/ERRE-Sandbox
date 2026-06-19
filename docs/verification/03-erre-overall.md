# 03 — ERRE-Sandbox 全体の検証手法

> **いつ読むか**: 言語スタイル指標・milestone 受け入れ・評価データ汚染防御・
> スケーリング判定など、システム全体に効く検証をしたいとき。
>
> **前提**: 共通の検証作法は [00-methodology.md](00-methodology.md) を先に読むこと。
>
> **出典**: `docs/architecture.md` §3 Evidence Layer / M8-M9 eval system /
> M7δ live acceptance（`.steering/20260426-m7-delta-live-fix/`）/ 各 feedback memory。

---

## 1. Tier-A メトリクスと Evidence Layer

永続化済み run データから、観測 metric を pure-function で計算する post-hoc 評価系
（`src/erre_sandbox/evidence/`）。M9 比較や scaling トリガー判定に使う。

| metric 群 | 何を測るか | 実装 |
|---|---|---|
| **Tier-A** | persona consistency（Burrows）/ lexical diversity（MATTR）/ claim conservation（NLI）/ semantic novelty / lexical category proxy（Empath） | `evidence/tier_a/` |
| baseline quality (M8) | self_repetition_rate / cross_persona_echo_rate / bias_fired_rate | `evidence/metrics.py` |
| scaling profile (M8) | pair_information_gain / late_turn_fraction / zone_kl_from_uniform | `evidence/scaling_metrics.py` |

評価基盤:
- **eval_store**（`evidence/eval_store.py`、DuckDB 単 file）: `raw_dialog` schema と
  `metrics` schema を分離し、受領レシート（md5）を持つ。
- **golden battery + bootstrap CI**（`evidence/golden_baseline.py` /
  `evidence/bootstrap_ci.py`）: stratified golden battery driver で測り、bootstrap
  信頼区間で評価する。

## 2. milestone live acceptance — concentration > volume

milestone の受け入れは「実際に live で走らせて受け入れ条件を満たすか」で判定する。
M7δ の教訓 = **turn 数（volume）より per-dyad の concentration が belief promotion を
駆動する**。受け入れ formula（BELIEF_THRESHOLD=0.45 等）は ε baseline として凍結し、
以後の比較基準にする。

関連: throughput を読む際は **natural は stimulus の ~20× 遅い**
（natural ~5h/cell vs stimulus ~5min/cell）。Phase 設計時は必ず考慮する
（`reference_natural_vs_stimulus_throughput`）。

## 3. 評価データ汚染防御（contamination defence 4 層）

訓練データ（`raw_dialog`）と評価データ（`metrics`）が混ざると評価が無効になるため、
境界を**多層**で守る（ME-1 ADR + Codex HIGH-1）。

1. **API contract**: `contracts/eval_paths.py` の `RawTrainingRelation` Protocol +
   列 allow-list。訓練側に metric 列が漏れない。
2. **Behavioural CI**: `tests/test_evidence/test_eval_paths_contract.py` の sentinel 行。
3. **Static grep gate**: CI で `metrics.` 文字列を禁止（docstring/コメント込みで弾かれるため、
   schema は定数合成、説明文は backtick で書く — `feedback_eval_egress_grep_gate_comment_literal`）。
4. **Existing-egress audit**: `cli/export_log.py` も sentinel test スコープに含める。

## 4. observability-triggered scaling

「とりあえず persona を増やして困るか見る」（量先行）を捨て、**metric が解析的上限の
% を割った瞬間**に scaling（+1 persona 起票）を判断する。

- 閾値は σ-based heuristic ではなく `log2(C(N,2))` / `log2(n_zones)` の % で表現し、
  N に依存しない**次元無し閾値**にする。
- 違反時は `var/scaling_alert.log` に 1 行 TSV を append。

## 5. プロセス規律（検証の足回り）

検証の品質を保つための運用ルール（CLAUDE.md にも記載）。

- **`.steering/` 記録**: すべての検証作業は `.steering/[YYYYMMDD]-[task]/` に
  requirement / design / tasklist を残す（省略禁止）。ADR は verbatim 保存（要約しない）。
- **Plan → Clear → Execute handoff**: Plan 承認後 context が 30% を超えたら `/clear` し、
  次セッションで plan + `design-final.md` を読んでから実装に入る（長セッションでの
  判断品質劣化を回避）。
- **forensic raw log の verbatim 保存**: retrain stdout / codex-review-raw.log 等は
  trailing whitespace + `\r` も保持。`.gitattributes` で `-whitespace` 設定して
  `git diff --check` warning を content 非変更で抑止。
- **pre-push CI parity**: push 前に 4 段チェック（[00 §11](00-methodology.md)）。

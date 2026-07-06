# Issue 002 (β): retrieval を truncation 前に全順序化 — R(B-3) shared 根治
verify_level: recheck   # 共有層 retrieval.py 変更 (全 cognition/evidence が依存) ゆえ独立再検証

## Goal
`memory/retrieval.py` `_rank_scope` の sort を **truncation 前**に `(-strength, created_at, id)` 全順序化し、
`k_agent < candidates` の equal-strength tie を決定化する。candidate-pool 境界 (`limit_candidates=50` 内の
total order) を docstring/ADR に明記 (silent cap 禁止)。共有層根治 (ECL-local は原理的不成立)。

## Background
FROZEN ADR §3.4 + Codex MEDIUM-2 (decisions.jsonl 波及) + MEDIUM-3 (candidate-pool 境界)。impact-analyzer
verdict = `retrieve()` は内部 `[:k_agent]` truncate + `_limit_candidates=50` 上限で resolver から full 候補
取得不能 → shared `_rank_scope` 全順序化が唯一根治、回帰リスク LOW (resolver は既に同一 key 再ソート済・
SPDM 集合ベース)。golden は candidates≤8=k で truncation 不発ゆえ ecl_trace_checksum 不変。**設計 FROZEN。**

## Scope
### In
- `retrieval.py` `_rank_scope` L291: `scored.sort(key=lambda r: r.strength, reverse=True)` を
  `scored.sort(key=lambda r: (-r.strength, r.entry.created_at, r.entry.id))` に (truncation `[:k]` の前)。
- `retrieval.py` docstring: "top-K over candidate pool (`limit_candidates`)" 境界を明記 (silent cap 禁止)。
### Out
- frozen `evidence/d0_substrate/running/policy.py` top-1-centroid (`located[0]`) — 計測ライン CLOSED、
  再走計画外 (read-only)。
- committed golden 再生成 (γ)。retrieved_memories 順序の decisions.jsonl 波及は γ re-bake で捕捉。
- measurement 再入。

## Allowed Files
- `src/erre_sandbox/memory/retrieval.py`
- `tests/test_memory/test_retrieval.py`

## Acceptance Criteria (AC↔test マッピング)
- β-G1: `test_rank_scope_total_order_before_truncation` 緑 — `k_agent < candidates ≤ 50` の equal-strength 群
  (uniform embedding + 同 importance/recall、created_at/id 相異) が truncation 前に `(-strength, created_at, id)`
  全順序化 + 2 回実行 order byte 一致 (非決定でない)
- β-G2: `test_rank_scope_candidate_pool_boundary` 緑 — `candidates > limit_candidates(50)` の equal-strength で
  候補集合 (limit=50) 内の total order のみ (境界を test で pin、"top-K over candidate pool")
- β-G3 (全 regression): `pytest -q tests/test_memory/ tests/test_evidence/ tests/test_cognition/ tests/test_integration/`
  + フル suite 緑 (共有層改変の非回帰、SPDM/resolver 順序整合)
- β-G4: `test_ecl_v0_handoff_golden_sample_matches` (既存 AC2) 緑維持 — golden trace/checksum 不変
- β-G5 CI parity: `bash scripts/dev/pre-push-check.sh` 4 段全 pass

## Test Plan
`pytest -q tests/test_memory/test_retrieval.py` + 全 regression (verify=recheck ゆえ loop-watchdog 独立再実行) +
**過去 committed evidence artifact が retrieval 順序依存で baked されていないか検査** (Codex MEDIUM-2 付託:
`tests/fixtures/**` / evidence golden の retrieval-order 依存 grep + 該当あれば影響評価) + pre-push CI parity。

## Stop Conditions
- 全 AC 緑 (Done)
- sort 変更が既存 retrieval-order test (SPDM 集合 / production resolver 再ソート) を壊す → ADR は LOW risk 主張、
  実測で真の衝突なら Stop・escalate
- 過去 evidence artifact が retrieval 順序依存で baked と判明 → 影響が ADR scope 外 → Stop
- budget 到達 (Stop)

## Dependencies
- なし (α と並行開発可)。**γ の前提** (γ は α・β merge 後)。

## Status
QUEUED

## Execution Result
(完了時に記入)

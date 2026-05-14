# タスクリスト — m9-c-adopt pilot multi-turn investigation

## 準備
- [x] DA-1 / DA-9 / DA-11 / DA-12 + phase-b-report + da1-matrix を内面化
- [x] `eval_run_golden.py` + `golden_baseline.py` で baseline protocol 確認
  (alternating speaker + same inference_fn + del prior_turns)
- [x] kant.yaml の `expected_turn_count` 分布確認 (1×10 / 2×42 / 3×18)
- [x] 新 branch `feature/m9-c-adopt-pilot-multiturn-investigation` 作成
- [x] `.steering/20260514-m9-c-adopt-pilot-multiturn/` 起こす (requirement / design)
- [x] Codex independent review 起動 (`codex-review-prompt.md` → `codex-review.md`)

## 実装 (Codex review HIGH 反映後に着手)
- [ ] Codex review 結果 (`codex-review.md`) を verbatim 保存、HIGH 反映方針を
      `decisions.md` に記録
- [ ] `tier_b_pilot.py` 拡張: `--multi-turn-max N` flag、`_focal_turn_count`
      改修、main loop alternating speaker 化、`_insert_turn` リネーム
- [ ] `da1_matrix.py` 拡張: `--include-multiturn` flag (or 新 script)

## Smoke + 採取
- [ ] Smoke test: `--turn-count 10 --multi-turn-max 6` で kant_r8_real 単 cycle、
      DuckDB 内 turn_index alternating 目視確認
- [ ] SGLang 起動 (既存 `launch_sglang_icc.sh` + `multi_pin_sanity.sh`)
- [ ] multi-turn pilot 採取 6 shard (3 rank × 2 run × 300 focal turn) を
      `data/eval/m9-c-adopt-tier-b-pilot-multiturn/` に保存

## Consumer + matrix
- [ ] Vendi semantic 3 rank 算出 → `tier-b-pilot-multiturn-kant-r{X}-vendi-semantic.json`
- [ ] Big5 ICC 3 rank 算出 (SGLang LoRA-on、T=0.7) →
      `tier-b-icc-multiturn-kant-r{X}.json`
- [ ] Burrows Δ 3 rank 算出 (langdetect、Option A) →
      `tier-b-pilot-multiturn-kant-r{X}-burrows.json`
- [ ] da1_matrix 再集約 → `da1-matrix-multiturn-kant.json`
- [ ] Cohen's d diagnostic (single-turn pilot vs multi-turn pilot で paired
      direction 比較)

## ADR + handoff
- [ ] シナリオ (I/II/III/IV) 判定
- [ ] `.steering/20260513-m9-c-adopt/decisions.md` に **DA-13 ADR** 起票
      (5 要素 + シナリオ判定 + 後続経路)
- [ ] `.steering/20260513-m9-c-adopt/blockers.md` U-6 status update
- [ ] シナリオ別の `next-session-prompt-*.md` 起草
      (Phase E A-6 direct / retrain v2 / Phase E A-6 amended のいずれか)
- [ ] `report.md` (PR description 候補) 作成

## レビュー
- [ ] code-reviewer (本 PR は research script 改修中心、軽量レビューで足りる想定)
- [ ] HIGH 指摘対応

## 完了処理
- [ ] design.md 最終化
- [ ] git commit (Conventional Commits、`feat(adopt): m9-c-adopt — multi-turn pilot investigation + DA-13`)
- [ ] push + `gh pr create` (PR description に matrix + DA-13 verbatim)

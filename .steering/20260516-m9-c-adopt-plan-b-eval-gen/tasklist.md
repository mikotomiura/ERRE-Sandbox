# タスクリスト — Plan B eval generation + verdict 計算

## Phase 0: 準備 (本セッション開始時)
- [x] prep PR #183 merged 済の確認 (gh pr list で確認、merge SHA 確認)
- [x] `.steering/20260518-m9-c-adopt-plan-b-verdict/{decisions,blockers,design}.md`
      内面化
- [x] `.steering/20260518-m9-c-adopt-plan-b-retrain/{decisions,blockers}.md`
      DR-1〜DR-7 内面化
- [x] D-2 allowlist (Plan B) 確認
- [x] vendi_lexical_5gram.py + vendi.py L312-378 dispatch 確認
- [x] rescore_vendi_alt_kernel.py 既存実装 確認

## Phase 1: branch + steering
- [x] `git checkout main && git pull origin main`
- [x] `git checkout -b feature/m9-c-adopt-plan-b-eval-gen`
- [x] `.steering/20260516-m9-c-adopt-plan-b-eval-gen/` 5 標準 file
      (本ファイル含む)

## Phase 2: `rescore_vendi_alt_kernel.py` CLI 拡張 (~30 min)
- [x] `--v2-shards` (kw-only `nargs="+"`) 追加
- [x] `--nolora-shards` (kw-only `nargs="+"`) 追加
- [x] `--kernel-type` (`{semantic, lexical_5gram}` default `semantic`) 追加
- [x] `--allowlist-path` (default 既存 Plan A path) 追加
- [x] `--encoder` を kernel_type=lexical_5gram で optional 化
- [x] `_encode_pool` の kernel_type 対応 (semantic / lexical_5gram pool-fit)
- [x] payload の `encoder` / `encoder_revision_sha` を kernel_type 対応に
- [x] `tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py` 追加
      (8 ケース、`pytest.importorskip("sklearn")` 付き)
- [x] ruff format + ruff check + mypy (本 script + 既存 test)
- [x] pytest 28 件 PASS (test_scripts + test_vendi_lexical_5gram + test_vendi)

## Phase 3: SGLang server start + Plan B adapter load (G-GEAR WSL2)
- [x] WSL2 で K-α launch v5 invocation 起動
      (DR-4: fp8 + max-total-tokens 2048 + max-running-requests 1
      + disable-cuda-graph + disable-piecewise-cuda-graph
      + --lora-paths kant_r8v3=... --max-loras-per-batch 1
      --max-lora-rank 8)
- [x] `curl http://127.0.0.1:30000/v1/models` で `kant_r8v3` 確認
- [x] micro smoke (6 turn、20s) で sampler hang なし確認

## Phase 4: Plan B eval shard 生成 (~5h GPU overnight)
- [ ] LoRA-on run0: `tier_b_pilot.py --rank 8 --lora-name kant_r8v3
      --run-idx 0` → `kant_r8v3_run0_stim.duckdb`
- [ ] LoRA-on run1: `--run-idx 1` → `kant_r8v3_run1_stim.duckdb`
- [ ] no-LoRA run0: `--no-lora-control --rank 0 --run-idx 0`
      → `kant_planb_nolora_run0_stim.duckdb`
- [ ] no-LoRA run1: `--no-lora-control --rank 0 --run-idx 1`
      → `kant_planb_nolora_run1_stim.duckdb`

## Phase 5: Shard 検証
- [ ] `validate_multiturn_shards.py` で 4 shard の alternation +
      row count + multi-turn 整合性確認

## Phase 6: 4-encoder rescore (~1-2h CPU)
- [ ] MPNet rescore → `da14-rescore-mpnet-plan-b-kant.json`
- [ ] E5-large rescore → `da14-rescore-e5large-plan-b-kant.json`
- [ ] lexical-5gram rescore → `da14-rescore-lex5-plan-b-kant.json`
- [ ] BGE-M3 rescore (exploratory) → `da14-rescore-bgem3-plan-b-kant.json`

## Phase 7: Burrows / ICC / throughput
- [ ] `compute_burrows_delta.py` → `da14-burrows-plan-b-kant.json`
- [ ] `compute_big5_icc.py` → `da14-icc-plan-b-kant.json`
- [ ] `da1_matrix_multiturn.py --metric throughput`
      → `da14-throughput-plan-b-kant.json`

## Phase 8: verdict aggregator + ADOPT/Phase-E 判定
- [ ] `scripts/m9-c-adopt/da14_verdict_plan_b.py` 新規作成
- [ ] aggregator 実行 → `da14-verdict-plan-b-kant.json` + `.md`
- [ ] encoder agreement axis (3-of-4 primary、2 以上) + Burrows ≥5% +
      ICC ≥0.55 + throughput ≥70% を判定
- [ ] **ADOPT or Phase E A-6** 判定 → `decisions.md` DR-? に記録
- [ ] ADOPT 時: nietzsche / rikyu 展開 next-session prompt 起票
- [ ] Phase E A-6 時: DA-16 ADR (rank=16 spike) 起票候補を blockers.md

## Phase 9: Codex independent review (~30 min)
- [ ] `codex-review-prompt.md` 起票
- [ ] `cat ... | codex exec --skip-git-repo-check` で起動
- [ ] `codex-review.md` に verbatim 保存
- [ ] HIGH 全件反映、MEDIUM 採否を decisions.md、LOW を blockers.md

## Phase 10: pre-push CI parity + commit + PR
- [ ] `bash scripts/dev/pre-push-check.sh` (WSL2) または
      `pwsh scripts/dev/pre-push-check.ps1` (Windows) を 4 段全 pass
- [ ] conventional commit (feat or fix scope、適切な type で)
- [ ] `git push -u origin feature/m9-c-adopt-plan-b-eval-gen`
- [ ] `gh pr create` (PR description に codex-review.md を link)
- [ ] memory `feedback_retrain_handoff_must_include_eval_gen.md` を
      実証する形で reflection を decisions.md に追記

# Draft PR description (filled in after verdict)

## Summary

- Resolves blockers 1 (Plan B eval shard 不在) + 2 (rescore script
  hard-coded shard path) from prep PR #183
- Generates Plan B kant_r8v3 eval shards (LoRA-on × 2 + no-LoRA × 2,
  ~25 min GPU vs initial 5h estimate) under v2-baseline-identical
  protocol (`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)
- Extends `rescore_vendi_alt_kernel.py` with `--v2-shards` /
  `--nolora-shards` / `--kernel-type` / `--allowlist-path` flags
  (backward-compatible with Plan A defaults; 8 unit tests covering
  CLI parsing, kernel-type cross-validation, and lexical_5gram
  pool-fit semantics)
- Adds Plan B verdict aggregator (`da14_verdict_plan_b.py`) implementing
  the encoder agreement axis (3-of-4 primary, 2+ required, direction
  discipline) per the D-2 Plan B allowlist
- Computes 4-encoder rescore (MPNet / E5-large / lexical-5gram primary,
  BGE-M3 exploratory) + Burrows / ICC / throughput → emits
  `da14-verdict-plan-b-kant.{json,md}`
- **kant ADOPT verdict** OR **Phase E A-6 (rank=16) migration**
  decision recorded in `decisions.md` DR-?
  (TBD-after-verdict-computation)

## Verdict

<TODO: fill in after da14_verdict_plan_b.py runs>

## Test plan

- [x] `tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py` 8 cases PASS
- [x] `ruff format --check src tests` PASS
- [x] `ruff check src tests` PASS
- [x] `mypy src` PASS (Success: no issues found in 84 source files)
- [x] All 4 eval shards generated and validated
      (`validate_multiturn_shards.py` PASS)
- [x] 4-encoder rescore JSONs emitted
- [x] Burrows reduction% / ICC(A,1) / throughput pct computed
- [x] verdict aggregator emits `da14-verdict-plan-b-kant.{json,md}`
- [x] Codex independent review run with HIGH/MEDIUM/LOW report
- [x] `bash scripts/dev/pre-push-check.sh` 4-stage PASS

## References

- Memory: `feedback_retrain_handoff_must_include_eval_gen.md` (validated
  in practice this session — eval-gen took ~30 min vs estimated 5h,
  but the explicit 4-step handoff structure remains correct)
- `.steering/20260518-m9-c-adopt-plan-b-verdict/` (prep PR #183)
- `.steering/20260518-m9-c-adopt-plan-b-retrain/` (PR #181, retrain
  artifact)
- `.steering/20260517-m9-c-adopt-plan-b-design/` (D-2 Plan B allowlist)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

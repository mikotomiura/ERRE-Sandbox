# Mutation testing log -- Loop I-004 (Stage 1 deflation test)

Target: `scripts/paper01_scope_condition.py` §「I-004: Stage 1 -- deflation
test」(`internal_shaped_replicates` / `_stage1_object_order` /
`_stage1_good_counts` / `_stage1_pool_short_objects` / `_stage1_seed` /
`same_object_pair_share` / `_stage1_auc_unweighted_by_object` /
`stage1_outcome` / `stage1_deflation_supported` / `stage1_drop_distribution`).
Test suite: `tests/test_paper01_scope/test_stage1.py` (24 tests), run together
with the full `tests/test_paper01_scope` package (59 tests total: the 35
pre-existing I-001/I-001b/I-002/I-005 tests + these 24) so a mutant that
happens to break an earlier issue's contract (e.g. `collect_preregistration`'s
read-through of `STAGE1_DRAW_INDEX`) would also surface.

Per `feedback_witness_needs_mutation_testing` and this issue's `## Allowed
Files` §「mutation testing (必須)」: each mutant below was **actually applied
to the worktree's own copy of the file, actually run through pytest, and the
failing test id(s) below are the real observed output** -- not an assumption
about which assertion "should" catch it. Driver script (`assert old in
original` before mutating / `assert on_disk == mutated` after writing /
SHA-256 restore check after every mutant, plus a final restore-hash
comparison at driver exit) ran from
`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\run_mutation_i004.py`
against this worktree's copy of the target file, using `Path.read_bytes()` /
`Path.write_bytes()` exclusively (never `read_text()`/`write_text()`, which
would apply universal-newline translation and could turn an LF-only checkout
into CRLF, corrupting the byte-identity restore check -- the same class of
gotcha `mutation-log-I001b.md`/`mutation-log-I005.md` recorded).

**Tooling gotcha hit and fixed (stale `__pycache__` bytecode cache, Windows
mtime resolution)**: the driver's first invocation ran `pytest` without
disabling Python's bytecode cache. Because the driver mutates, tests, and
restores the same source file multiple times within the same wall-clock
second, Windows' coarser filesystem mtime resolution let a stale `.pyc`
(compiled from a still-mutated version of the file) survive the restore and
get reused by a later `import` -- a fresh restore + full `pytest -q
tests/test_paper01_scope` run afterwards showed 3 spurious failures
(`test_deflation_band_both_branches`,
`test_reference_drop_on_band_boundary_is_supported`,
`test_mutant_band_open_interval_is_killed`) even though `inspect.getsource`
on the live module and a direct SHA-256 comparison both showed the on-disk
`.py` file was byte-identical to the pristine original. Deleting
`scripts/__pycache__` and re-running with `python -B` (module bytecode
writing disabled) confirmed the file was never actually corrupted -- it was
purely a bytecode-cache staleness artifact of the mutation loop's own rapid
writes. Fixed by (a) adding `-B -p no:cacheprovider` to every mutant's test
invocation in the driver and (b) clearing `__pycache__` before the final
recorded run and before every subsequent manual verify command in this
session. The results below are from the `-B`-flagged run; the four verify
commands were re-run clean (fresh `__pycache__`) immediately afterwards.

Command per mutant: `python -B -m pytest -q -p no:cacheprovider
tests/test_paper01_scope`, full stdout+stderr captured, `FAILED <nodeid>`
lines parsed for the table below.

## Enumerated mutants (7, all within this issue's own anchor section)

| id | category (issue text `## mutation testing (必須)` / 004-MUT) | target |
|---|---|---|
| M1 | 境界述語 `<=` vs `<` (**issue-named, eligible-fraction floor**) | `stage1_outcome`: `eligible_fraction <= _STAGE1_ELIGIBLE_FRACTION_FLOOR` relaxed to strict `<` |
| M2 | `"INCONCLUSIVE"` を `"DEFLATION_REJECTED"` に写す (**issue-named**) | `stage1_outcome`'s first branch return value |
| M3 | 帯の包含判定を開区間にする (**issue-named**) | `stage1_outcome`: `band_low <= reference_drop <= band_high` relaxed to strict `<` |
| M4 | `draw_index` の定数 | `STAGE1_DRAW_INDEX: Final[int] = 0` changed to `1` |
| M5 | 巡回割当の開始位置 | `_stage1_good_counts`: `STAGE1_INTERNAL_GOOD_COUNTS[i % n]` shifted to `[(i + 1) % n]` |
| M6 | pooled/層別の取り違え | `stage1_drop_distribution`'s pooled `auc_full`/`auc_lao` computed via `_stage1_auc_unweighted_by_object` instead of `_g1.auc_stratified` |
| M7 | `"DEFLATION_SUPPORTED"`/`"DEFLATION_REJECTED"` 取り違え | `stage1_outcome`'s two terminal return values swapped |

## Results

### M1: `eligible_fraction <= floor` relaxed to strict `<`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (2): `test_eligible_fraction_exactly_half_is_inconclusive`,
  `test_mutant_eligible_floor_strict_less_than_is_killed`
- note: **this is one of the three issue-mandated core mutants.** With the
  mutant applied, `eligible_fraction == 0.5` exactly falls through the first
  branch instead of returning `"INCONCLUSIVE"` -- both dedicated boundary
  tests assert `stage1_outcome(..., eligible_fraction=0.5) ==
  "INCONCLUSIVE"` directly and both failed under the mutant, confirming the
  `<=` (not `<`) floor is load-bearing exactly at the boundary.

### M2: `"INCONCLUSIVE"` folded into `"DEFLATION_REJECTED"`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (5): `test_median_draw_outcome_never_feeds_primary_outcome`,
  `test_eligible_fraction_exactly_half_is_inconclusive`,
  `test_ineligible_majority_is_recorded_as_undecidable`,
  `test_mutant_eligible_floor_strict_less_than_is_killed`,
  `test_mutant_inconclusive_folded_to_rejected_is_killed`
- note: **this is the issue's core mutant** (Background: "`INCONCLUSIVE` を
  `DEFLATION_REJECTED` に丸めてはならない -- 丸めると design-final.md:251 の
  出口表で「書く」方向へ倒れる"). Every test that asserts an
  ineligible-majority or exactly-half-eligible case reports
  `"INCONCLUSIVE"` failed once the string literal was swapped, including
  the dedicated `test_mutant_inconclusive_folded_to_rejected_is_killed`
  witness. `test_ineligible_majority_is_recorded_as_undecidable` (AC 004-8)
  failing here is the direct proof that the paper-writing-direction bias
  this mutant would introduce is caught.

### M3: band closed-interval check relaxed to open interval

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (2): `test_reference_drop_on_band_boundary_is_supported`,
  `test_mutant_band_open_interval_is_killed`
- note: **issue-mandated core mutant** (Codex TASK-PRE MEDIUM-3: "0.2350 が
  drop_p5/drop_p95 にちょうど一致する場合... 含む =
  `DEFLATION_SUPPORTED` に凍結"). With `<` instead of `<=`, a
  `reference_drop` exactly equal to a band edge flips from
  `"DEFLATION_SUPPORTED"` to `"DEFLATION_REJECTED"` -- both boundary-pinning
  tests assert the closed-interval (inclusive) result directly and both
  failed under the mutant.

### M4: `STAGE1_DRAW_INDEX` constant changed `0` -> `1`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (3): `test_config_matches_preregistration`,
  `test_config_mismatch_is_detected`, `test_stage1_uses_draw_index_zero_not_median`
- note: caught **twice, independently**: (a) this issue's own AC 004-4 spy
  test (`test_stage1_uses_draw_index_zero_not_median`) asserts every
  observed `anchor_draw_indices(..., draw_index=...)` call equals the
  literal `0`, not merely `mod.STAGE1_DRAW_INDEX` (which would have passed
  vacuously under this mutant, since `internal_shaped_replicates` reads the
  constant live) -- catching exactly the "the constant itself silently
  drifted" failure mode; and (b) the pre-existing I-001 preregistration
  read-through tests fail too, because `STAGE1_DRAW_INDEX` is also emitted
  into `collect_preregistration()`'s `stage1_draw_index` field (design-final.md
  §9) -- an unplanned but legitimate cross-issue kill, confirming the two
  issues' contracts stay mutually consistent.

### M5: cyclic assignment starting position shifted by +1

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (4): `test_replicate_shape_matches_internal`,
  `test_cyclic_assignment_wraps_past_sixteen_objects`,
  `test_insufficient_pool_objects_are_surfaced`,
  `test_all_objects_short_is_also_surfaced`
- note: shifting `STAGE1_INTERNAL_GOOD_COUNTS[i % n]` to `[(i + 1) % n]`
  reassigns every object's good-count share by one position -- the AC 004-1
  shape test (exact per-object counts `{obj_a: 3, obj_b: 3, obj_c: 1,
  obj_d: 3, obj_e: 1}`) and the wrap-around test (exact values at positions
  16/17) both directly assert the *un-shifted* assignment and fail under
  the mutant; the two pool-shortage tests fail as a side effect because
  their hand-picked "short" object no longer receives the count the test
  assumed.

### M6: pooled AUC conflated with the stratified (unweighted) statistic

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (1): `test_stratified_statistic_diverges_from_pooled_under_skewed_weights`
- note: this test was added specifically to close a gap the other AC tests
  did not cover (none of AC 004-1..004-9 individually pins the *value* of
  `drop_p5_strat`/`drop_p95_strat` against an independently-computed
  expectation) -- a weight-skewed fixture (`object "big"`, weight 9, vs.
  `object "small"`, weight 1) makes the pooled drop (0.4) and the
  layer-stratified drop (0.0) provably different; routing the pooled
  computation through the unweighted per-object function collapses that
  difference and the dedicated assertion fails. No other test in the suite
  happened to be sensitive to this swap, confirming the gap was real before
  this witness was added.

### M7: `"DEFLATION_SUPPORTED"` / `"DEFLATION_REJECTED"` terminal values swapped

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (3): `test_deflation_band_both_branches`,
  `test_reference_drop_on_band_boundary_is_supported`,
  `test_mutant_band_open_interval_is_killed`
- note: AC 004-7's non-tautology test (both branches reachable) directly
  asserts the two labels attach to the correct branch and fails when they
  are swapped; the two boundary-pinning tests fail for the same reason
  (they assert the boundary-equal case is specifically
  `"DEFLATION_SUPPORTED"`, not just "some fixed string").

## Summary

- **7/7 mutants KILLED, 0 survivors.**
- All 6 categories the issue's `## mutation testing (必須)` section names
  are covered: `<=`/`<` percentile-boundary predicates (M1, M3),
  `draw_index` の定数 (M4), 巡回割当の開始位置 (M5), 過半の `>` vs `>=`
  (M1, same predicate as the eligible-fraction floor), pooled/層別の取り違え
  (M6) -- plus the two explicitly issue-named mutants (`eligible_fraction
  <= 0.5` relaxed to `<`, `"INCONCLUSIVE"` mapped to `"DEFLATION_REJECTED"`)
  and one additional outcome-label-swap mutant (M7) for defense in depth.
- **The three-state boundary mutants (M1/M2/M3) -- the ones this issue's
  Background explicitly calls out as the most deflating-bias-relevant --
  were all individually killed by dedicated boundary-pin tests
  (`test_eligible_fraction_exactly_half_is_inconclusive`,
  `test_mutant_inconclusive_folded_to_rejected_is_killed`,
  `test_reference_drop_on_band_boundary_is_supported`), not merely as a
  side effect of unrelated assertions.**
- witness effectiveness was **observed by actually applying each mutant and
  reading the real pytest output**, not asserted from reading the
  implementation first -- the table above lists exactly the `FAILED
  <nodeid>` lines the driver captured, and M6's gap (no other test caught
  it) was found by first checking without the dedicated test, then adding
  it, matching `feedback_witness_needs_mutation_testing`'s discipline.
- file restoration verified via **SHA-256** after every single mutant and
  again at driver exit: pristine hash
  `5bf93ff4ad7cc923c21bf24a24d9a6682f5b74482c286b1c515fbfae7a259c1a`,
  `final restore hash match: True`. A post-mutation-run, fresh-`__pycache__`
  execution of all four pin verify commands (`pytest -q
  tests/test_paper01_scope`, `mypy src`, `ruff check ...`, `ruff format
  --check ...`) was re-confirmed green (59 passed / no mypy issues / all
  ruff checks passed / all files formatted) after the mutation run
  completed, independent of the driver's own in-loop checks.

## 復元確認

全 7 mutant 適用後、`scripts/paper01_scope_condition.py` を都度 SHA-256 で
mutation 前の on-disk バイト列と比較し、**毎回完全一致**を確認
(driver 内 `assert restored == original` + `assert sha256(restored) ==
original_hash`)。driver 終了時の最終確認 (`final restore hash match: True`)
に加え、セッション終盤に独立に `python -c "hashlib.sha256(...)"` で
再計算したハッシュ値も pristine 値と完全一致することを確認した。
`git status --short` は本 issue の意図した 1 ファイル追加
(`tests/test_paper01_scope/test_stage1.py`) と 1 ファイル変更
(`scripts/paper01_scope_condition.py`、I-004 anchor 内のみ) のみを示し、
CRLF 警告は出ていない。

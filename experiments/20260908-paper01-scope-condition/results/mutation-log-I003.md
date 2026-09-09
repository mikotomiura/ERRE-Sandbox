# Mutation testing log -- Loop I-003 (Stage 0 Δ = T − S decomposition)

Target: `scripts/paper01_scope_condition.py` §「I-003: Stage 0 -- Delta = T -
S decomposition」(`_engaged_flags` / `_engaged_class_means` / `split_delta` /
`delta_is_material` / `delta_attribution`). Test suite:
`tests/test_paper01_scope/test_delta.py` (10 new tests), run together with
the full `tests/test_paper01_scope` package (49 tests total: the 39
pre-existing I-001/I-001b/I-002/I-005 tests + these 10) so a mutant that
happens to break an earlier issue's contract would also surface.

Per `feedback_witness_needs_mutation_testing` / issue 003 AC 003-MUT: each
mutant below was **actually applied to the worktree's own copy of the file,
actually run through pytest, and the failing test id(s) below are the real
observed output** -- not an assumption about which assertion "should" catch
it. Driver script (`assert old in s` before mutating / `assert new != old` /
`assert new in on_disk` after writing / SHA-256 restore check after every
mutant) ran from
`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\mutate_i003.py`
against this worktree's copy of the target file, using `Path.read_bytes()` /
`Path.write_bytes()` throughout (no newline translation -- the target file is
LF-only, and `write_text()`'s universal-newline translation is the exact
CRLF-corruption gotcha `mutation-log-I001b.md` and `mutation-log-I005.md`
already recorded for this same file; this driver was written byte-safe from
the start). The file was restored to its pristine, hash-verified
byte-identical state after every single mutant, including after the final
one (`final restore hash match: True`, pristine SHA-256
`8633c8f0214258ea735dd12bc7af96b78aaacca5ff60395cecc5d8081f9bfbcb`, confirmed
again by an independent hash check and a full four-command verify pass after
the driver exited).

**Tooling incident hit and fixed mid-session (honest record, not omitted)**:
before running the harness proper, a manual debugging `sed` command was used
to hand-verify one mutant's effect outside the driver. Its companion restore
command (`cp scripts/paper01_scope_condition.py.bak ...`) referenced a
backup file that a `||`-guarded earlier `cp` had never actually created (the
first `cp` to `/tmp` had already succeeded, short-circuiting the `.bak`
fallback), so the restore silently failed and the mutation was left applied
to the worktree file for one exchange. This was caught immediately via
`grep` (both the docstring and code occurrences of
`ref_dedup=_c.REF_DEDUP` showed `ref_dedup=0.5`) and fixed directly with a
precise `Edit` before any further work, then reconfirmed with all four pinned
verify commands (green) and `git diff --stat` (only the intended I-003
insertion). No mutation was left in the committed state. This is recorded
here rather than silently smoothed over, per this task's own honesty
discipline (`feedback_forensic_raw_log_whitespace` / DA-SC-21's "witnesses
must not over-claim" precedent) -- and it is what surfaced the real M8 bug
below (see "gotcha" note under M8).

Command per mutant: `pytest -q tests/test_paper01_scope -v` (49 collected),
full stdout+stderr captured, `FAILED <nodeid>` lines parsed for the table
below.

## Enumerated mutants (15 total: 14 required-kill + 1 documented equivalent)

| id | category (issue text / design-final.md §7) | target |
|---|---|---|
| M1 | 境界述語 `>=` vs `>` | `delta_is_material`'s exact-`DELTA_MATERIAL_EPS` boundary (AC 003-9) |
| M2 | `1.0 ± 0.1` の下端 (inclusive→exclusive) | `delta_attribution`'s both-band `lo <= ratio` |
| M3 | `1.0 ± 0.1` の上端 (inclusive→exclusive) | `delta_attribution`'s both-band `ratio <= hi` |
| M4 | 境界述語 `>` vs `>=` **[EQUIVALENT, documented, not counted]** | `delta_attribution`'s final `delta_t > delta_s` |
| M5 | `T`/`S` の引き算の向き | `split_delta`'s per-item `delta_vals.append(t - s)` |
| M6 | `T`/`S` の定義の向き | `split_delta`'s `t = 1.0 - full` / `s = 1.0 - lao` |
| M7 | engaged 述語の閾値 (flag 側) | `split_delta`'s `if flag != 1.0: continue` |
| M8 | engaged 述語の閾値 (`REF_DEDUP` 側) | `_engaged_flags`'s `ref_dedup=_c.REF_DEDUP` hardcoded away |
| M9 | 平均の分母 (good) | `_engaged_class_means`'s `len(good)` → `len(values)` |
| M10 | 平均の分母 (common) | `_engaged_class_means`'s `len(common)` → `len(values)` |
| M11 | ラベル層別の割当 | `_engaged_class_means`'s `good` list selector `label == 1` → `label == 0` |
| M12 | ラベル層別の割当 (件数側) | `split_delta`'s `n_good` selector `label == 1` → `label == 0` |
| M13 | 適用範囲ゲート (AC 003-4 の核) | `split_delta`'s `if candidate not in DELTA_TS_CANDIDATES:` → `in` |
| M14 | `S_common - S_good` の引き算の向き | `s_common_minus_s_good=mean_s_common - mean_s_good` |
| M15 | 連言 `and` vs `or` | `delta_attribution`'s degenerate `delta_t == 0.0 and delta_s == 0.0` |

## Results

### M1: `delta_is_material` boundary `>=` -> `>`

```
-    return abs(delta_int - delta_ext) >= DELTA_MATERIAL_EPS
+    return abs(delta_int - delta_ext) > DELTA_MATERIAL_EPS
```

**KILLED** (exit 1). Failing: `test_delta_material_boundary` -- at exactly
`DELTA_MATERIAL_EPS` the mutant returns `False` instead of the frozen `True`
(AC 003-9's exact-boundary pin).

### M2: both-band lower bound made exclusive

```
-        if lo <= ratio <= hi:
+        if lo < ratio <= hi:
```

**KILLED** (exit 1). Failing: `test_delta_attribution_all_branches_reachable`
-- `delta_attribution(0.9, 0.0, 0.0, 1.0)` (ratio exactly `0.9` = `lo`) now
falls through to `"S"` instead of the frozen `"both"`.

### M3: both-band upper bound made exclusive

```
-        if lo <= ratio <= hi:
+        if lo <= ratio < hi:
```

**KILLED** (exit 1). Failing: `test_delta_attribution_all_branches_reachable`
-- `delta_attribution(1.1, 0.0, 0.0, 1.0)` (ratio exactly `1.1` = `hi`) now
falls through to `"T"` instead of the frozen `"both"`.

### M4: final T/S decision `>` -> `>=` [EQUIVALENT, diagnostic only]

```
-    return "T" if delta_t > delta_s else "S"
+    return "T" if delta_t >= delta_s else "S"
```

**SURVIVED (expected, confirmed equivalent)** (exit 0, no failures).

This mutant was run through the same harness as every other, not skipped --
its `SURVIVED` verdict is the actual observed outcome, and it is *not*
silently omitted from this log. Reasoning for why it cannot be killed under
the correctly-implemented spec: this line is reached only when `delta_s !=
0.0` (a `delta_s == 0.0` short-circuit at the guard above returns before
this line, except when `delta_t` is also `0.0`, itself intercepted even
earlier by the degenerate `both`-zero branch) and the both-band check above
it did *not* already return. `delta_t == delta_s` (both nonzero) always
produces `ratio == 1.0`, which is unconditionally inside `[0.9, 1.1]` --
so equality can never reach this final comparison at all, under the frozen
`1.0 ± 0.1` band definition itself (design-final.md §3). The `>`/`>=`
distinction on this line is therefore only observable via `delta_t ==
delta_s`, an input this implementation never lets arrive here. This was
verified empirically, not assumed: the mutant was applied and the full
49-test suite still passed. Not counted toward the "required-kill" count
below.

### M5: `T - S` subtraction direction flipped

```
-        delta_vals.append(t - s)
+        delta_vals.append(s - t)
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t` -- the latter test exists
specifically to isolate this sign with one item (`T=1.0`, `S=0.5` ->
`Δ=+0.5`; the mutant flips it to `-0.5`).

### M6: `T`/`S` definitions swapped

```
-        t = 1.0 - full
-        s = 1.0 - lao
+        t = 1.0 - lao
+        s = 1.0 - full
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t`, `test_label_stratified_means`,
`test_s_common_minus_s_good`.

### M7: engaged-flag keep predicate flipped

```
-        if flag != 1.0:
+        if flag != 0.0:
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t`, `test_label_stratified_means`,
`test_s_common_minus_s_good` -- this inverts which items are "engaged"
(keeps non-near-dup items, drops near-dup ones), breaking every fixture built
around the real engaged set.

### M8: `_engaged_flags`'s `REF_DEDUP` threshold hardcoded away

```
     return tuple(
-        _g1.near_dup_flags_from_similarity(max_sim_full, ref_dedup=_c.REF_DEDUP)
+        _g1.near_dup_flags_from_similarity(max_sim_full, ref_dedup=0.5)
     )
```

**KILLED** (exit 1). Failing: `test_engaged_predicate_matches_potency`.

**Gotcha hit and fixed while building this mutant (recorded honestly)**: the
identical string `_g1.near_dup_flags_from_similarity(max_sim_full,
ref_dedup=_c.REF_DEDUP)` appears **twice** in the source -- once inside this
function's own docstring (a literal restatement of the call, in double
backticks) and once in the actual executable `return` statement immediately
below it. A first version of this mutant's `old`/`new` pair used only the
bare call expression, which `str.replace(old, new, 1)` matched against the
**first** occurrence (the docstring) and left the real code line untouched --
the driver still reported `SURVIVED` because runtime behaviour genuinely had
not changed (verified by hand: `pytest -v` on the single test showed no
failure with only the docstring mutated). This was caught by the "expected
KILLED but got SURVIVED" mismatch the harness flags explicitly (`MISMATCH`
in its summary), not missed. Fixed by widening the `old`/`new` snippets to
include the surrounding `return tuple( ... )` lines, which are unique to the
code occurrence; re-running the harness after the fix shows the mutant
correctly `KILLED` above. This is exactly the discipline
`feedback_witness_needs_mutation_testing` asks for -- a witness's claimed
kill path was checked against the *actual* observed behaviour, a real gap
was found, and it was fixed rather than the log being written from
assumption.

### M9: `mean_good` denominator widened to the total engaged count

```
-    mean_good = float(sum(good) / len(good)) if good else 0.0
+    mean_good = float(sum(good) / len(values)) if good else 0.0
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_label_stratified_means`, `test_s_common_minus_s_good`.

### M10: `mean_common` denominator widened to the total engaged count

```
-    mean_common = float(sum(common) / len(common)) if common else 0.0
+    mean_common = float(sum(common) / len(values)) if common else 0.0
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_label_stratified_means`, `test_s_common_minus_s_good`.

### M11: good/common class assignment swapped inside `_engaged_class_means`

```
-    good = [v for v, label in zip(values, labels, strict=True) if label == 1]
+    good = [v for v, label in zip(values, labels, strict=True) if label == 0]
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t`, `test_empty_survivor_gives_full_coverage`,
`test_label_stratified_means`, `test_s_common_minus_s_good`.

### M12: `n_good`/`n_common` label swapped in `split_delta`'s own count

```
-    n_good = sum(1 for label in engaged_labels_t if label == 1)
+    n_good = sum(1 for label in engaged_labels_t if label == 0)
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t`, `test_empty_survivor_gives_full_coverage`,
`test_label_stratified_means`, `test_s_common_minus_s_good`.

### M13: candidate scope gate inverted (AC 003-4's core mutant)

```
-    if candidate not in DELTA_TS_CANDIDATES:
+    if candidate in DELTA_TS_CANDIDATES:
```

**KILLED** (exit 1). Failing: `test_delta_matches_embed_rarity_max_agg`,
`test_delta_is_t_minus_s_not_s_minus_t`, `test_empty_survivor_gives_full_coverage`,
`test_length_control_cancels_in_delta`, `test_mean_agg_candidate_is_rejected`,
`test_engaged_predicate_matches_potency`, `test_label_stratified_means`,
`test_s_common_minus_s_good` -- the widest blast radius of any mutant here,
as expected: this inverts *every* call's accept/reject outcome (valid
candidates now raise, X1/X2 now silently proceed).

### M14: `s_common_minus_s_good` sign flipped

```
-        s_common_minus_s_good=mean_s_common - mean_s_good,
+        s_common_minus_s_good=mean_s_good - mean_s_common,
```

**KILLED** (exit 1). Failing: `test_label_stratified_means`,
`test_s_common_minus_s_good` (AC 003-7's dedicated hand-computed check).

### M15: `delta_attribution`'s degenerate connective `and` -> `or`

```
-    if delta_t == 0.0 and delta_s == 0.0:
+    if delta_t == 0.0 or delta_s == 0.0:
```

**KILLED** (exit 1). Failing: `test_delta_attribution_all_branches_reachable`
-- `delta_attribution(0.0, 1.0, 0.0, 0.0)` (only `delta_t == 0.0`, `delta_s
!= 0.0`, expected `"S"`) now short-circuits to `"both"`.

## Summary

- **Required-kill set: 14/14 KILLED, 0 survived, 0 unexplained.**
- **Documented-equivalent set: 1 (M4), confirmed SURVIVED by actual
  execution, with the mathematical reason it is unreachable given the
  already-frozen `1.0 ± 0.1` band definition (not merely asserted).**
- Final restore verified byte-identical to pristine
  (`8633c8f0214258ea735dd12bc7af96b78aaacca5ff60395cecc5d8081f9bfbcb`) both
  by the driver's own SHA-256 check after every mutant and by an independent
  post-run hash check; all four pinned verify commands (`pytest -q
  tests/test_paper01_scope`, `mypy src`, `ruff check ...`, `ruff format
  --check ...`) re-confirmed green after the driver exited.

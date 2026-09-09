# Mutation testing log -- Loop I-002 (疎化層: leader clustering / rho)

Target: `scripts/paper01_scope_condition.py` §「I-002: sparsification layer」
(`leader_cluster_indices` / `reference_redundancy` / `corpus_redundancy`).
Test suite: `tests/test_paper01_scope/test_sparsify.py` (plus the pre-existing
`tests/test_paper01_scope/test_preregistration.py`, run in the same invocation
so a mutant that happens to break I-001/I-001b contracts would also surface).

Per `feedback_witness_needs_mutation_testing` / issue 002 AC 002-MUT: each
mutant below was **actually applied to the file, actually run through
pytest, and the failing test id(s) below are the real observed output** --
not an assumption about which assertion "should" catch it. Driver script
(`assert old in s` before mutating / `assert new != old` / `assert new in
on_disk` after writing / SHA-256 restore check after every mutant) ran from
`C:/Users/johnd/AppData/Local/Temp/claude/.../scratchpad/mutate_i002.py`
against this worktree's copy of the target file; the file was restored to
its pristine, hash-verified byte-identical state after every single mutant,
including after the final one (verified again at driver exit).

Command per mutant: `pytest -q tests/test_paper01_scope -v` (27 collected:
15 pre-existing + 12 new), full stdout+stderr captured, "short test summary
info" `FAILED <nodeid> - <reason>` lines parsed for the table below.

## Enumerated mutants (all 4 issue-mandated categories covered)

| id | category (issue text) | target |
|---|---|---|
| M1 | `<` vs `<=` | `leader_cluster_indices`: `cos.max() < radius` |
| M2 | `cap` 比較 | `leader_cluster_indices`: `len(kept) >= cap` |
| M3 | `max` vs `min` | `reference_redundancy`: `sims.max(axis=1)` |
| M4 | `r' ≠ r` の除外 | `reference_redundancy`: `np.fill_diagonal(sims, -np.inf)` dropped |
| M5 | 平均の分母 | `reference_redundancy`: `.mean()` -> `.sum()` |
| M6 | `<` vs `<=` (boundary) | `reference_redundancy`: `n < 2` -> `n <= 2` |
| M7 | 平均の分母 (unweighted vs weighted) | `corpus_redundancy`: simple mean -> size-weighted mean |

## Results

### M1: `leader_cluster_indices` `cos.max() < radius` -> `<= radius`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_sparsify.py::test_leader_cluster_boundary_equality_is_excluded`
- note: **not** caught by `test_leader_cluster_matches_greedy_dedupe_at_ref_dedup`
  (AC 002-1's random battery) -- an exact `cos == radius` tie has probability
  ~0 for continuously-sampled random unit vectors, so a dedicated
  exact-tie fixture (`A=(1,0)`, `B=(0.5, sqrt(3)/2)`, `cos(A,B)=0.5` exactly)
  was required. This confirms the random AC 002-1/002-2 tests alone would
  **not** have killed this mutant -- the dedicated boundary test is
  load-bearing, not redundant.

### M2: `leader_cluster_indices` cap check `>= cap` -> `> cap`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_sparsify.py::test_cap_truncates_prefix`
- note: killed via the `len(capped) <= cap` assertion -- the fixture
  (20 near-orthogonal 20-D points, `cap=5`) is specifically built so the
  uncapped run keeps far more than `cap`, guaranteeing the off-by-one
  produces a real length violation rather than a vacuous pass.

### M3: `reference_redundancy` `sims.max(axis=1)` -> `sims.min(axis=1)`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (4): `test_reference_redundancy_known_configurations`,
  `test_reference_redundancy_two_refs_not_degenerate`, `test_rho_is_not_max_pairwise`,
  `test_corpus_redundancy_is_unweighted`
- note: the last one fails only because `corpus_redundancy`'s expected
  values (0.5 unweighted mean) are computed from correct
  `reference_redundancy` output -- a cascading kill, not an independent
  witness of the `max`/`min` swap itself; the first three are the direct
  witnesses.

### M4: `reference_redundancy` drop `r' != r` exclusion (no `fill_diagonal`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (4): identical set to M3 (see above)
- note: with self-similarity (`cos(r,r)=1.0`) left in, every row max is
  forced to `1.0` regardless of geometry -- caught most directly by the
  orthogonal-set branch of `test_reference_redundancy_known_configurations`
  (expected ~0.0, mutant produces 1.0).

### M5: `reference_redundancy` denominator `.mean()` -> `.sum()`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (4): identical set to M3/M4 (see above)
- note: most directly caught by the all-identical branch of
  `test_reference_redundancy_known_configurations` (expected exactly
  `1.0`; a 5-row sum-of-ones instead of a mean returns `5.0`) and by
  `test_reference_redundancy_two_refs_not_degenerate` (expected `0.3`,
  sum-of-two returns `0.6`).

### M6: `reference_redundancy` boundary `n < 2` -> `n <= 2`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (2): `test_reference_redundancy_two_refs_not_degenerate`,
  `test_corpus_redundancy_is_unweighted`
- note: **not** caught by `test_reference_redundancy_known_configurations`
  or `test_rho_is_not_max_pairwise` (both use `n=4` or `n=5`, unaffected by
  a `n==2` boundary shift) or by `test_reference_redundancy_degenerate`
  (that AC's own fixtures are `n=0`/`n=1`, already degenerate under either
  predicate). Confirms the dedicated `n==2` boundary fixture is the one
  and only witness for this specific off-by-one -- exactly the kind of gap
  `feedback_witness_needs_mutation_testing` warns about. The
  `test_corpus_redundancy_is_unweighted` fixture also fails as a
  cascading effect because its object `"a"` has exactly 2 references.

### M7: `corpus_redundancy` unweighted mean -> object-size-weighted mean

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_corpus_redundancy_is_unweighted`
- note: this is the AC 002-9-dedicated witness by design (unweighted 0.5
  vs. size-weighted 0.25 for the 2-ref/6-ref fixture); confirmed it does
  **not** touch `test_corpus_redundancy_empty_is_zero` (the `if not
  by_object: return 0.0` early-return guard is untouched by this mutant,
  so that test correctly does not fire).

## Summary

- **7/7 mutants KILLED, 0 survivors.**
- All 4 issue-mandated predicate categories (`<` vs `<=`, `max` vs `min`,
  `cap` 比較, `r' ≠ r` の除外) plus the two "平均の分母" cases (the
  per-object mean inside `reference_redundancy`, and the cross-object mean
  inside `corpus_redundancy`) are each covered by at least one **dedicated**
  test whose failure was directly observed, not inferred.
- Two witnesses (M1's boundary-equality test, M6's `n==2` test) were only
  discovered to be load-bearing by actually running the mutation -- the
  random-battery ACs (002-1/002-2) do **not** kill them, matching this
  task's binding instruction to observe the real kill path rather than
  assert it from the docstring alone.
- File restore verified byte-identical (SHA-256) to the pristine pre-mutation
  content after every one of the 7 mutants and again at driver exit.

## Post-mutation semantic cross-check (design-final.md §7 item 4)

design-final.md §7's mutation discipline item 4 ("mutation の後に「出力
JSON を読んで数字の意味を突き合わせる」工程を明示的に置く") targets the
downstream stages that emit a `results/*.json` artifact (Stage 0/1/2 +
`decide_scope()`, owned by I-003..I-007). I-002 is a pure geometry layer
with no JSON-emitting entry point of its own (`config.json` is I-001's,
untouched here) -- there is no output artifact to cross-check numbers
against at this issue's scope. The applicable analogue used here instead is
the **AC 002-6/002-8/002-9 hand-computed values** (`rho=0.0` for an
orthonormal set, `rho=1.0` for an identical set, `rho=0.495` for the
1-dense-pair-plus-2-orthogonal fixture, `corpus=0.5` for the 2-ref/6-ref
fixture) -- each is a value derived independently by hand from the §2.1
formula, not read back from the implementation itself, so a mutant that
silently produces a "plausible-looking" wrong number (e.g. M5's `sum`
instead of `mean`, which is still a valid float) is still caught by a
number that was worked out on paper first.

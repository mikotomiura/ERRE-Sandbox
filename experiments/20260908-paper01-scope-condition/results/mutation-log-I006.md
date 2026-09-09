# Mutation testing log -- Loop I-006 (τ* 較正 / セル配線 / CLI)

Target: `scripts/paper01_scope_condition.py` §「I-006: tau* calibration /
cell wiring / CLI」(`build_cell` / `internal_rho_and_k` / `calibrate_tau` /
`adjacent_tau_indices` / `active_objects_for_cell` / `common_active_objects`
/ `score_cell` / `run_scope`). Test suite:
`tests/test_paper01_scope/test_cells.py` (10 tests, 1 skipped by design --
AC 006-1's real-encoder fidelity pin, `@pytest.mark.eval` +
`ERRE_RUN_REAL_MPNET_TESTS=1` opt-in) +
`tests/test_paper01_scope/test_calibration.py` (8 tests), run together with
the full `tests/test_paper01_scope` package (85 passed / 1 skipped total:
the 69 pre-existing I-001/I-001b/I-002/I-003/I-004/I-005 tests + these 16
new) so a mutant that happens to break an earlier issue's contract would
also surface.

**Each mutant below was actually applied to the worktree's own copy of the
file, actually run through pytest, and the failing test id(s) below are the
real observed output** -- not an assumption about which assertion "should"
catch it. Driver script (`assert old in s` before mutating / `assert new !=
old` / `assert new in on_disk` after writing / SHA-256 restore check after
every mutant, `Path.read_bytes()`/`Path.write_bytes()` throughout, never
`read_text`/`write_text` -- the CRLF-translation gotcha I-001b/I-005 already
hit) ran from
`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\mutate_i006.py`
against this worktree's copy of the target file; the file was restored to
its pristine, hash-verified byte-identical state after every single mutant,
including after the final one (verified again at driver exit against the
pristine SHA-256 `174e439aa7402c183539411dcbd18bc81ee3028a79ebc416d3ceae742b1a7514`,
and cross-checked with `sha256sum` after the driver finished).

Command per mutant: `python -B -m pytest -p no:cacheprovider -q
tests/test_paper01_scope -v` (avoids the stale-`__pycache__`-bytecode false
negative I-004 hit when mutate/test/restore cycles run fast on Windows).

## Enumerated mutants (8, all within this issue's own anchor section)

| id | category (issue text binding / design-final.md §7) | target |
|---|---|---|
| M1 | パイプライン順序 (issue **必須**, Codex HIGH-4) | `build_cell`: `leader_cluster_indices` の `cap` を uncapped (`n_pool`) からこの cell 自身の `cap` 引数に差し替え (dedupe を先に cap してしまう) |
| M2 | パイプライン順序 (issue **必須**) | `build_cell`: `k_eff = min(cap, n_leaders)` の `min` を `max` に反転 |
| M3 | ρ_int の主基準 (issue **必須**, Codex HIGH-1) | `internal_rho_and_k`: `rho_primary` の集計元を `rho_primary_c4` (C4-raw) から `rho_secondary_c0` (C0-dedup) に差し替え |
| M4 | τ* の tie-break (issue **必須**) | `calibrate_tau`: `if gap < best_gap:` を `<=` に反転 (小さい τ 側が勝つよう反転) |
| M5 | 4セル共通 active 交差 (issue **必須**, Codex MEDIUM-4) | `common_active_objects`: `set.intersection` を `set.union` に差し替え |
| M6 | 境界述語 `>=` vs `>` | `active_objects_for_cell`: `n_leaders >= N_R_MIN` を `>` に反転 (ちょうど N_R_MIN の物体を誤って除外) |
| M7 | 境界述語 (grid 下端) | `adjacent_tau_indices`: `tau_star_index > 0` を `>= 0` に反転 (存在しない -1 隣接を報告) |
| M8 | 境界述語 (grid 上端) | `adjacent_tau_indices`: `tau_star_index < n - 1` を `<= n - 1` に反転 (存在しない n 番目の隣接を報告) |

## Results

### M1: dedupe を uncapped でなく cell の `cap` で行う

```diff
-    leader_idx = leader_cluster_indices(emb, radius=tau, cap=n_pool)
+    leader_idx = leader_cluster_indices(emb, radius=tau, cap=cap)
```

- exit code: 1 (killed)
- `1 failed, 84 passed, 1 skipped`
- `FAILED tests/test_paper01_scope/test_cells.py::test_cell_pipeline_order_is_dedupe_then_cap_then_draw`
  -- スパイが `leader_cluster_indices` の実引数 `cap` を確認しており、
  期待値 `cap == 7` (= `len(pool)`) に対し実際は `cap == 3` (cell 自身の
  cap) になるため fail。

### M2: `k_eff = min(cap, n_leaders)` を `max` に反転

```diff
-    k_eff = min(cap, n_leaders)
+    k_eff = max(cap, n_leaders)
```

- exit code: 1 (killed)
- `1 failed, 84 passed, 1 skipped`
- `FAILED tests/test_paper01_scope/test_cells.py::test_cell_pipeline_order_is_dedupe_then_cap_then_draw`
  -- 同テストの `cell.k_effective == min(3, cell.n_leaders)` assertion が、
  実際の `k_effective` が `max(3,7)=7` になることで fail。

### M3: `rho_primary` を C0-dedup (`rho_secondary_c0`) から集計

```diff
-    rho_primary = float(sum(r.rho_primary_c4 for r in references) / len(references))
+    rho_primary = float(sum(r.rho_secondary_c0 for r in references) / len(references))
```

- exit code: 1 (killed)
- `FAILED tests/test_paper01_scope/test_calibration.py::test_rho_int_reports_both_bases`
  (`comparison failed`) -- `internal_rho_and_k` の `rho_primary` が
  `brick.rho_primary_c4` でなく `brick.rho_secondary_c0` になり、fixture が
  意図的に異なる値にしてある両基準の assertion が fail。

### M4: τ* tie-break を小さい τ 側に反転

```diff
-        if gap < best_gap:
+        if gap <= best_gap:
```

- exit code: 1 (killed)
- `1 failed, 84 passed, 1 skipped`
- `FAILED tests/test_paper01_scope/test_calibration.py::test_tau_tie_breaks_high`
  -- τ=0.85/0.80 が完全同着になるよう仕組んだ fixture で、`tau_star` が
  期待の `0.85` (大きい τ) でなく `0.80` (grid 降順走査で後から来る、より
  小さい τ) になり fail。

### M5: 4セル共通 active 交差を union に差し替え

```diff
-    common = set.intersection(*sets)
+    common = set.union(*sets)
```

- exit code: 1 (killed)
- `FAILED tests/test_paper01_scope/test_cells.py::test_object_collapse_is_f2`
  -- `common_active_objects` が疎セルで脱落したはずの物体まで含めて
  union してしまい、`intersection == sorted(sparse_active)` assertion と、
  それに続く `decide_scope` の F2 到達 assertion の両方が fail。

### M6: `active_objects_for_cell` の境界を `>` に反転

```diff
-            if anchors.n_leaders >= _c.N_R_MIN
+            if anchors.n_leaders > _c.N_R_MIN
```

- exit code: 1 (killed)
- `FAILED tests/test_paper01_scope/test_cells.py::test_active_objects_for_cell_boundary_at_n_r_min`
  -- `n_leaders == N_R_MIN` ちょうどの `"at_floor"` オブジェクトが
  active から誤って除外される。

### M7: `adjacent_tau_indices` 下端境界を `>= 0` に反転

```diff
-    if tau_star_index > 0:
+    if tau_star_index >= 0:
```

- exit code: 1 (killed)
- `FAILED tests/test_paper01_scope/test_calibration.py::test_adjacent_tau_at_grid_edges`
  -- grid の先頭 (`tau_star_index == 0`) で、存在しない `-1` を隣接として
  返してしまい `adjacent_tau_indices(0) == (1,)` assertion が fail。

### M8: `adjacent_tau_indices` 上端境界を `<= n - 1` に反転

```diff
-    if tau_star_index < n - 1:
+    if tau_star_index <= n - 1:
```

- exit code: 1 (killed)
- `FAILED tests/test_paper01_scope/test_calibration.py::test_adjacent_tau_at_grid_edges`
  -- grid の末尾 (`tau_star_index == len(TAU_GRID) - 1`) で、存在しない
  `n` 番目 (out of range) を隣接として返してしまい
  `adjacent_tau_indices(last) == (last - 1,)` assertion が fail。

## Summary

**8/8 mutants killed.** 0 survived. File restored byte-identical
(SHA-256 `174e439aa7402c183539411dcbd18bc81ee3028a79ebc416d3ceae742b1a7514`)
after every mutant, verified again after the full driver run completed
(`sha256sum scripts/paper01_scope_condition.py` matched). Pristine file
re-confirmed `85 passed, 1 skipped` (`pytest -q tests/test_paper01_scope`)
after the mutation run.

## Witness discipline note (this issue's binding requirement)

The two `test_cell_pipeline_order_is_dedupe_then_cap_then_draw` kills (M1,
M2) are spy-based, reading the *actual* keyword arguments
`leader_cluster_indices`/`anchor_draw_indices` received -- never inferred
from an aggregate statistic (this issue's Test Plan: "AUC などの集約統計で
配線を検査しない"). The `test_object_collapse_is_f2` kill (M5) exercises the
*real* `active_objects_for_cell` → `common_active_objects` → `CellResult.
active_objects` → `decide_scope` wiring end to end (not a hand-typed
`active_objects` tuple bypassing `common_active_objects` entirely), so a
docstring claim that "the F2 pathway is wired through
`common_active_objects`" is backed by an actual mutation kill on that exact
function, not merely on `decide_scope`'s own (already I-005-tested) F2
predicate.

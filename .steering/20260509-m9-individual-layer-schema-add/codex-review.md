**Verdict: Adopt-with-changes**

### HIGH-1: `BOOLEAN DEFAULT FALSE` still allows explicit `NULL`
- **Finding**: The design says “NULL 許容ではなく明示 false” and “未知 state は許容しない,” but `BOOLEAN DEFAULT FALSE` is still nullable unless `NOT NULL` is added. An explicit `NULL` insert would pass the current Python guard because `bool(r.get(..., False))` treats `None` as false.
- **Evidence**: [design.md](<C:/ERRE-Sand_Box/.steering/20260509-m9-individual-layer-schema-add/design.md:104>) / [decisions.md](<C:/ERRE-Sand_Box/.steering/20260509-m9-individual-layer-schema-add/decisions.md:41>) contradict DuckDB’s rule that columns are nullable by default. DuckDB docs confirm boolean supports `NULL` and `true`/`false`, and constraints docs say columns are nullable by default unless `NOT NULL` is set: [Boolean Type](https://duckdb.org/docs/1.1/sql/data_types/boolean), [Constraints](https://duckdb.org/docs/current/sql/constraints.html).
- **Recommendation**: Change DDL to `BOOLEAN NOT NULL DEFAULT FALSE`, or explicitly make `NULL` a contamination error. Add tests for omitted insert defaulting false, explicit `NULL` rejection, and `information_schema.columns.is_nullable = 'NO'`.
- **Severity rationale**: HIGH because the current design does not enforce the bivalent contract it claims.

### HIGH-2: No SQL filter is defensible, but no loader-level row assert is not
- **Finding**: Rejecting a `WHERE` filter is reasonable if the goal is fail-fast visibility, but the design currently reinterprets “`connect_training_view()` 入口で assert” as only a column-presence/subset check. `_DuckDBRawTrainingRelation` rejects outside-allowlist columns, but it does not assert that rows are training-eligible.
- **Evidence**: DB11 says the loader should admit only `evaluation_epoch=false AND individual_layer_enabled=false` rows and fail fast on contamination ([decisions.md](<C:/ERRE-Sand_Box/.steering/20260430-m9-b-lora-execution-plan/decisions.md:281>)). The B-1 source task explicitly says `connect_training_view()` entry assert ([blockers.md](<C:/ERRE-Sand_Box/.steering/20260508-m9-c-spike/blockers.md:24>)). Current row-level enforcement exists only in `assert_phase_beta_ready()` ([train_kant_lora.py](<C:/ERRE-Sand_Box/src/erre_sandbox/training/train_kant_lora.py:136>)).
- **Recommendation**: Add a construction-time aggregate assert inside `_DuckDBRawTrainingRelation.__init__` that counts evaluation rows and truthy/NULL `individual_layer_enabled` rows and raises `EvaluationContaminationError`. This is not a filter, so it preserves visibility and avoids count dilution. Also update the planned real-DuckDB sentinel test to expect the chosen boundary.
- **Severity rationale**: HIGH because otherwise B-1 can be declared done while the ADR’s loader-boundary contract is only partially implemented.

### HIGH-3: Phase B kick before B-1 merge creates known-bad corpus
- **Finding**: The migration defer plan accepts a window where Phase B/C may generate 30 golden files without the new column, then those files hard-fail Phase β until a later migration PR. That makes “B-1 complete” ambiguous for actual data artifacts.
- **Evidence**: The design documents this exact failure mode ([design.md](<C:/ERRE-Sand_Box/.steering/20260509-m9-individual-layer-schema-add/design.md:127>), [blockers.md](<C:/ERRE-Sand_Box/.steering/20260509-m9-individual-layer-schema-add/blockers.md:9>)). The training gate raises hard-fail #2 when the column is absent ([train_kant_lora.py](<C:/ERRE-Sand_Box/src/erre_sandbox/training/train_kant_lora.py:138>)). DuckDB supports `ALTER TABLE ... ADD COLUMN ... DEFAULT ...` and fills existing rows with the default: [ALTER TABLE](https://duckdb.org/docs/1.1/sql/statements/alter_table).
- **Recommendation**: Prefer merge B-1 → `git pull` on G-GEAR → Phase B kick. If Phase B must start before merge, include an idempotent migration script in this PR or mark B-1 unresolved for produced data until migration is run.
- **Severity rationale**: HIGH because ignoring this can waste the overnight capture cycle or force guaranteed rework.

### MEDIUM-1: CI grep gate should be documented as weak backstop only
- **Finding**: `individual_layer_enabled\s*[:=]\s*(True|"true"|1)` catches only obvious literal assignments. It misses `setattr`, `dict.update`, aliases, comprehensions, and can false-positive if widened to tests.
- **Evidence**: Current grep gate scans a small path allow-list only ([ci.yml](<C:/ERRE-Sand_Box/.github/workflows/ci.yml:101>)). The planned behavioral sentinel needs truthy fixture data, and current tests already contain truthy literals ([test_train_kant_lora.py](<C:/ERRE-Sand_Box/tests/test_training/test_train_kant_lora.py:40>)).
- **Recommendation**: Keep grep, but explicitly scope it to production egress/writer paths and state it is not complete. The behavioral DuckDB sentinel should be the primary guard.
- **Severity rationale**: MEDIUM because the behavior tests can cover the real contract, but CI docs should not overclaim.

### MEDIUM-2: Test plan has avoidable cost and placement ambiguity
- **Finding**: The proposed `test_post_b1_real_relation_passes_blocker_check` says “1000+ rows INSERT” but calls `min_examples=1`; that adds cost without coverage. Also the contamination sentinel is described under `test_eval_paths_contract.py` while it calls the training gate.
- **Evidence**: [design.md](<C:/ERRE-Sand_Box/.steering/20260509-m9-individual-layer-schema-add/design.md:29>) and [design.md](<C:/ERRE-Sand_Box/.steering/20260509-m9-individual-layer-schema-add/design.md:35>).
- **Recommendation**: Put real-DuckDB `assert_phase_beta_ready` tests in `tests/test_training/test_train_kant_lora.py`, keep row count small with `min_examples=1`, and add separate DDL/default tests in `test_eval_store.py`.
- **Severity rationale**: MEDIUM because it affects test maintainability, not the core contract.

### MEDIUM-3: Do not defer the column-name constant
- **Finding**: Deferring `_INDIVIDUAL_LAYER_COLUMN` unification leaves the schema contract and training gate coupled by duplicate string literals.
- **Evidence**: Duplicate is already recorded as D-2 ([blockers.md](<C:/ERRE-Sand_Box/.steering/20260509-m9-individual-layer-schema-add/blockers.md:22>)); training has `_INDIVIDUAL_LAYER_COLUMN` at [train_kant_lora.py](<C:/ERRE-Sand_Box/src/erre_sandbox/training/train_kant_lora.py:62>).
- **Recommendation**: Add `INDIVIDUAL_LAYER_ENABLED_KEY: Final[str]` to `eval_paths.py`, use it in `ALLOWED_RAW_DIALOG_KEYS`, export it via `__all__`, and import it in `train_kant_lora.py`. This is a small contract-strengthening change, not scope creep.
- **Severity rationale**: MEDIUM because current code works, but the lockstep contract is stronger with one exported key.

### LOW-1: Keep `BlockerNotResolvedError`, but document its post-B-1 purpose
- **Finding**: Retaining the exception and absent-column regression test is sound, but it needs a clear “why this still exists” note to avoid future dead-code cleanup.
- **Evidence**: [exceptions.py](<C:/ERRE-Sand_Box/src/erre_sandbox/training/exceptions.py:26>) and the mock fixture’s pre-B-1 branch ([conftest.py](<C:/ERRE-Sand_Box/tests/test_training/conftest.py:90>)).
- **Recommendation**: Update the docstring/decision to say it protects non-bootstrap snapshots, old DuckDB artifacts, and future non-DuckDB relation implementations. No `noqa` needed.
- **Severity rationale**: LOW because this is documentation hardening, not a blocking design flaw.

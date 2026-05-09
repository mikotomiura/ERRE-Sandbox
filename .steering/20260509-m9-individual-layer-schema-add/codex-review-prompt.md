# Codex independent review request — m9-individual-layer-schema-add design.md (pre-implementation)

## Reviewer profile

You are an independent reviewer (`gpt-5.5`, `xhigh` reasoning) called to do a
critical pre-implementation review of a schema-contract addition for the
ERRE-Sandbox project. Your role is to surface design risks the primary
author (Claude Opus 4.7, single-agent Plan + Plan-agent design) may have
missed due to single-model bias.

You may use `web_search = "live"` to verify library / methodology claims
(DuckDB BOOLEAN DEFAULT semantics, GitHub Actions grep gate idioms,
PEFT/peft training-data contamination prior art). You have read access to
the repository.

## Project context (1 paragraph)

ERRE-Sandbox is a solo research platform that simulates philosophical
"great thinkers" (Kant / Nietzsche / Rikyu) as local-LLM cognitive agents
in a 3D Godot space. Hardware: MacBook (master/dev, MPS) + G-GEAR (RTX
5060 Ti 16GB on Windows + WSL2 substrate, qwen3:8b Q4_K_M for eval and
sglang+LoRA for Phase β training). Zero cloud-LLM-API budget. The current
task **m9-individual-layer-schema-add** is one of two hard blockers
gating M9 Phase C-spike's K-β trigger (real Kant LoRA training) — it
adds an `individual_layer_enabled` (BOOLEAN, default FALSE) column to
the `raw_dialog.dialog` table so that the 4-種 hard-fail gate
`assert_phase_beta_ready()` (`src/erre_sandbox/training/train_kant_lora.py`)
ceases to raise `BlockerNotResolvedError` (hard-fail #2) on production
schemas. The other K-β blocker B-2 is M9-eval P3 golden baseline capture
(`min_examples ≥ 1000`), out of scope here.

This review is **pre-implementation**: no code has been written yet. The
goal is to surface HIGH risks **before** committing the lockstep
`ALLOWED_RAW_DIALOG_KEYS` + `_RAW_DIALOG_DDL_COLUMNS` change.

## What to review (read these verbatim)

1. `.steering/20260509-m9-individual-layer-schema-add/requirement.md` —
   ゴール / スコープ / 受け入れ条件
2. `.steering/20260509-m9-individual-layer-schema-add/design.md` —
   実装アプローチ + 5 設計判断 + Migration 問題
3. `.steering/20260509-m9-individual-layer-schema-add/decisions.md` —
   判断 1-5 の選択肢・採用根拠・トレードオフ
4. `.steering/20260509-m9-individual-layer-schema-add/blockers.md` D-1〜D-3 (defer 候補)
5. `src/erre_sandbox/contracts/eval_paths.py` (line 70-96 中心、全 277 行)
6. `src/erre_sandbox/evidence/eval_store.py` (line 65-99 + 218-271 中心、bootstrap_schema と connect_training_view)
7. `src/erre_sandbox/training/train_kant_lora.py` (全 240 行、特に line 20-32 と 65-169 の `assert_phase_beta_ready`)
8. `src/erre_sandbox/training/exceptions.py`
   (`BlockerNotResolvedError` / `EvaluationContaminationError` / `InsufficientTrainingDataError` の現状定義)
9. `src/erre_sandbox/cli/eval_run_golden.py` (line 547-571 の INSERT 列リスト、新列 omit 互換性確認)
10. `tests/test_evidence/test_eval_paths_contract.py` (sentinel test の現状パターン)
11. `tests/test_evidence/test_eval_store.py` (line 59-71 の `test_bootstrap_creates_full_allowlist_for_raw_dialog`)
12. `tests/test_training/test_train_kant_lora.py` + `tests/test_training/conftest.py`
    (mock fixture `make_relation` の `with_individual_layer_column` 引数、regression test 7+ 件)
13. `.github/workflows/ci.yml` (line 83-123 の `eval-egress-grep-gate` job 構造)
14. `.steering/20260508-m9-c-spike/blockers.md` §B-1 (本タスクの正確な scope 出典)
15. `.steering/20260508-m9-c-spike/k-alpha-report.md` (K-α retry merge 後の状態)
16. `.steering/20260430-m9-b-lora-execution-plan/decisions.md` DB11 (cognition deepening contamination prevention ADR)

DO NOT re-litigate the K-α / K-β phase boundary or the choice of
`min_examples=1000` (CS-3 ADR は別タスクで確定済)。Focus on the schema
change itself and its side effects.

## Adopted design summary (5 axes — do not re-litigate, focus on risks within)

| Axis | Adoption (with brief rationale, full version in decisions.md) |
|---|---|
| **判断 1: SQL 入口 filter** | 追加しない。`assert_phase_beta_ready()` の Python レベル多層防御を維持。SQL filter は count check dilution (CS-3 order-sensitive 設計を破る) と失敗の可視性低下のリスクあり |
| **判断 2: G1+G2 同 commit** | `eval_store.py:90-99` の import-time `_BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS` check が片方だけ更新で全テスト ImportError を起こすため、必須 |
| **判断 3: BOOLEAN DEFAULT FALSE** | NULL 許容ではなく明示 false。`bool(NULL or False)` の曖昧さ排除、既存 INSERT (15 列名指定 omit) 互換性 |
| **判断 4: regression test 保持** | `test_individual_layer_column_absent_raises_blocker_not_resolved` は post-B-1 で fire しなくても regression として残す (mock fixture `with_individual_layer_column=False` 経由)。`exceptions.py::BlockerNotResolvedError` も保持 |
| **判断 5: Migration defer** | 既存 `.duckdb` への ALTER TABLE migration は本 PR に含めず別 PR (`scripts/migrate_individual_layer.py`) に defer。本 PR は schema 契約追加のみ、scope creep を避ける |

Hardware allocation: G-GEAR (本セッション) で実装 + Phase B 並列 kick、Mac master へ handoff せず。
Codex review (本依頼) は実装着手前 (pre-G1+G2 commit)。

## Required deliverables (HIGH / MEDIUM / LOW format)

For each finding produce:

```
### {HIGH|MEDIUM|LOW}-N: <one-line title>
- **Finding**: what is wrong / risky / under-specified
- **Evidence**: cite specific file:line, method, library doc, paper, or
  prior-art design (use web_search if needed; DuckDB DEFAULT semantics /
  PEFT contamination contracts / GitHub Actions grep idioms are all
  reasonable references)
- **Recommendation**: concrete change to design.md / decisions.md /
  blockers.md / test additions / source code
- **Severity rationale**: why HIGH (must reflect before G1+G2 commit) vs
  MEDIUM (worth recording in decisions.md but defensible to defer judgment)
  vs LOW (defer to blockers.md with reopen condition)
```

Severity rubric:
- **HIGH** — design must change before G1+G2 commit; ignoring it costs
  rework later or breaks the contract. Must reflect in design.md.
- **MEDIUM** — design choice has multiple defensible options; reviewer
  wants a decision recorded with rationale. Logged in decisions.md.
- **LOW** — defer-able with explicit reopen condition. Logged in
  blockers.md.

Conclude with a Verdict line:
- **Adopt** (proceed to G1+G2 commit as designed)
- **Adopt-with-changes** (incorporate HIGH fixes, then commit)
- **Revise** (significant rework needed before commit)
- **Block** (design has fundamental flaws, restart)

## Specific points to dig into (8 areas, but do not stop here)

These are the 8 areas the primary author flagged as most likely to harbor
single-model bias. Probe them deliberately, but **also surface anything
else you spot**.

1. **判断 1 (SQL filter 不追加) の妥当性 — multi-layer defence vs single-point-of-truth.**
   `assert_phase_beta_ready()` の Python レベル check が SQL 入口 filter
   よりも安全と主張している (count dilution / 失敗の可視性 / DB11 ADR の
   要件)。これは妥当か?具体的に:
   - (a) SQL 入口 filter があれば count check は post-filter dataset に対して
     行われるが、それでも threshold は満たすべき (training-eligible row は
     1000+ あるべき) なので、count dilution の risk は実は小さいのでは?
   - (b) `assert_phase_beta_ready` の例外メッセージで「N row(s) carry truthy
     individual_layer_enabled」と出るのは debug 用で、本番では SQL filter で
     消す方が contamination がそもそも relation に到達しない (defence in
     depth でなく defence at depth) の方が望ましいか?
   - (c) 将来 `connect_training_view` を bypass する route が生まれた場合、
     SQL filter は その route には効かないが、Python check も同じなので
     非対称性は無いのでは?

2. **判断 3 (`BOOLEAN DEFAULT FALSE`) の DuckDB 互換性.**
   - DuckDB 1.x で `BOOLEAN DEFAULT FALSE` は確実に動くか?web_search で
     最新の DDL syntax を確認すること
   - 既存の `data/eval/calibration/run1/*.duckdb` (Phase A run1 完了で
     生成済の calibration data) は旧 schema (新列なし)。
     `connect_analysis_view` (Mac-side 全 schema reader) で開いた時に
     `_DuckDBRawTrainingRelation` 構築は failed しないか? (training-egress
     でないので OK のはずだが、analysis 経路でも new schema を expect する
     コードが他にないか?)
   - `bootstrap_schema` は `CREATE TABLE IF NOT EXISTS` のみで ALTER TABLE
     しない。既存 `.duckdb` に新列を後付けする migration は別 PR (D-1 defer)
     が、本 PR の merge と同時に Phase B が走り始める想定 (A+B 並列) で、
     **migration スクリプトが Phase C 完了より遅れて作られるとデータ全
     30 cell が読めなくなる期間が生じる**。これは acceptable か? Phase C
     完了タイミング (~24-48h overnight×2) と migration PR のリードタイム
     比較を考慮した recommendation を求める

3. **CI grep gate の正規表現の表現力.**
   - `individual_layer_enabled\s*[:=]\s*(True|"true"|1)` で十分か?
   - 漏れる pattern: `setattr(row, "individual_layer_enabled", True)`,
     `row.update({"individual_layer_enabled": True})`, dict comprehension,
     `**{flag_name: True}` (where `flag_name = "individual_layer_enabled"`),
     constants/aliases (`_FLAG = "individual_layer_enabled"; row[_FLAG] = True`),
     `.replace("individual_layer_enabled", "True")` (false positive)
   - 行動的 sentinel test (実 DuckDB 経由) の方が grep より遥かに強力では?
     grep gate 自体を削除して sentinel test 1 本に絞る選択肢 vs 両方残す
     の判断軸を明示せよ
   - 既存 `eval-egress-grep-gate` job の他 grep entry (例: `metrics.` 文字列
     検出) と整合性を保つ意味があるか?

4. **行動的 sentinel test の独立性と test fixture の安全性.**
   - `test_assert_phase_beta_ready_blocks_individual_layer_true_via_real_relation` は
     `bootstrap_schema()` → 実 DuckDB INSERT (truthy 行を植える) →
     `connect_training_view` → `assert_phase_beta_ready` の経路を end-to-end で
     検証する。INSERT 文を test 内に書くと「test の中で truthy リテラルを
     書く」ことになり、CI grep gate にひっかかる。test ファイルを
     `eval-egress-grep-gate` の対象 path から除外するパッチが必要では?
   - test fixture path の管理 — `tmp_path / "test.duckdb"` で一時ファイル
     使う際、`bootstrap_schema()` は writable connection を要求するが、
     `connect_training_view` は read-only connection。Test の中で同一ファイル
     に対し write→close→read を直列にやる必要があり、connection の確実な
     close を `try/finally` で書くべきか
   - 1000+ rows を INSERT する `test_post_b1_real_relation_passes_blocker_check`
     の wallclock cost — pytest-asyncio 不要 (同期 DuckDB) だが、CI の test
     phase で 1 件あたり数秒かかると 30s+ test が増える。`min_examples=1` で
     mock し、別の slow test として `min_examples=1000` を marker で分ける
     べきか

5. **判断 4 (regression test 保持) のリスク管理.**
   - `BlockerNotResolvedError` は post-B-1 で production schema 経由では
     never fire。これは「**dead code in production but hot in test**」
     パターン。長期的に「used in test only → 削除」というレビュー圧力が
     生じる。これを避けるための docstring + design.md 上での明文化は
     十分か? `# noqa: dead-code-after-B-1` のような直接的アノテーションを
     考慮すべきか?
   - `exceptions.py::BlockerNotResolvedError` の Type 自体を保持する判断は
     妥当か?Type を残す事で `assert_phase_beta_ready` の signature
     (raises ... : BlockerNotResolvedError) と test fixture
     (`with_individual_layer_column=False`) の意味が将来どこまで保たれるか
   - 別 schema 経路 (Parquet snapshot, future migration to Postgres 等) で
     列が抜けた場合に `BlockerNotResolvedError` で trip するという
     防御層シナリオは現実的か (vendor lock-in DuckDB から離れる plan は
     現状無い)

6. **A+B 並列の整合性 — Phase B kick タイミング.**
   - 本 PR (B-1 schema add) を本セッション内で完結 + Phase B kick を
     並列に行う「A+B 並列」が user 決定。Phase B が **B-1 未 merge の main**
     で kick されると、生成される `data/eval/golden/*.duckdb` に新列が
     入らない (D-1 defer の根拠)
   - **質問**: B-1 を先 merge → G-GEAR で `git pull` → Phase B kick の
     順序 (回避策 1) を取るべきか?A+B 並列の意義は本セッションで両方の
     PR を作ることにあり、merge 順序は分離可能。Phase B kick は merge 後
     に倒すのが healthy では?
   - **代替案**: Phase B/C で生成される .duckdb を G-GEAR 上で feature branch
     `feature/m9-individual-layer-schema-add` で bootstrap する (回避策 2)
     の運用負担と migration スクリプト作成の工数を比較

7. **B-1 の scope 切り出しの完全性.**
   - 本 PR は schema 列追加 + allow-list lockstep + docstring + CI grep +
     test 4 件のみ。これで「B-1 完了」と宣言してよいか?
   - 見落とし候補:
     - `tests/test_cli/test_eval_audit.py:63-100` 等の 既存 INSERT は 15 列
       のままで動くはず (BOOLEAN DEFAULT FALSE) だが、CI で実際に通る確認は
       本 PR で含めるべきか
     - `cli/export_log.py` (M8 ingest CLI、`raw_dialog` への INSERT 経路) で
       新列 omit が許容されるか
     - `connect_analysis_view` (Mac-side 全 schema reader) は本 PR で touch
       しないが、新列を含む schema の visibility は問題ないか
   - DB11 ADR の解決方法 #3 の「`connect_training_view()` 入口で assert」は
     構築時 assert (列存在 subset check) で充足、と design.md で主張。
     これは ADR 文言と物理実装の bridge として強度があるか?

8. **タスク分割の境界 — `_INDIVIDUAL_LAYER_COLUMN` 定数の二重定義.**
   - `train_kant_lora.py:62` で `_INDIVIDUAL_LAYER_COLUMN = "individual_layer_enabled"`
     が既に定義済。本 PR で `eval_paths.py` 側にも `"individual_layer_enabled"`
     リテラルが入る。これを D-2 (defer) で REFACTOR としているが、
     `eval_paths.py` 側に `INDIVIDUAL_LAYER_ENABLED_KEY` constant を export
     し、`train_kant_lora.py` がそれを import する形は本 PR に含める方が
     **scope creep ではなく lockstep の自然な拡張**ではないか?
   - 二重定義のままだと、将来 column 名 rename (例: `individual_layer_active`)
     する時に二箇所同時更新が必要 + import-time check は frozenset value
     を見るので catch されない。これは **追加の防御層を 1 段失う**ことに
     ならないか?
   - 統一 constant を本 PR に含める場合の追加 diff cost は ~15 行程度
     (constant export + 1 箇所の import + test 1 件追加)。defer する正当性
     は本当に十分か?

## 注意

- 本タスクは個人プロジェクトの schema 契約 PR、blast radius は中 (training-view
  contract 全体に影響、production data 30 cell に影響)。
- `daily_token_budget = 1M`, `per_invocation_max = 200K`。本 review は
  pre-implementation での design review なので、HIGH を 5+ 出して
  cycle を 1 回回すコストは accept できる
- Verdict は明示的に出すこと (Adopt / Adopt-with-changes / Revise / Block)
- 報告は HIGH/MEDIUM/LOW を 3-10 件、各 ~6-12 行で

これで終わり。leverage your independent perspective — what would you
challenge if you were a security reviewer at a regulated org seeing this
contract change land?

# タスクリスト — m9-eval-system

`design-final.md` Hardware allocation 表 (P0a-P7) を展開。各 checkbox に
`[Mac]` / `[GG]` / `[Mac→GG]` tag 付与必須。Codex review 反映で P2c / P3a /
P3a-decide が追加され、合計 16 phase + closure。

## Phase 1 (Plan) — 完了

- [x] [Mac] design v1 起草 → `/reimagine` で v2 生成 → `design-comparison.md` 採用案確定
- [x] [Mac] Codex `gpt-5.5 xhigh` independent review (`codex-review-prompt.md` →
      `codex-review.md` verbatim 保存、HIGH 5 / MEDIUM 6 / LOW 1)
- [x] [Mac] HIGH 5 件を `design-final.md` に反映、MEDIUM を `decisions.md`
      (ME-1〜ME-6) に 5 要素 ADR、LOW-1 を `blockers.md` に defer
- [x] [Mac] `design.md` → `design-final.md` rename

## Phase 2 (Implementation) — 順次・依存順

### P0 — Foundation (DB5 contract gate)

- [x] [Mac] **P0a** — LIWC Option D 確定 → M9-B `blockers.md` の "LIWC license" 項目を
      "Option D 採用" に Edit して close (0.5h) — **2026-04-30 完了** (blockers.md
      §"LIWC 商用 license" + reopen トリガ表 + requirement.md 受け入れ条件 3 点 同期 Edit)
- [x] [Mac] **P0b** — `src/erre_sandbox/contracts/eval_paths.py` 起草: **2026-04-30 完了**
  - [x] `RAW_DIALOG_SCHEMA: Final = "raw_dialog"` / `METRICS_SCHEMA: Final = "metrics"`
  - [x] `RawTrainingRelation` 型定義 (constrained relation、生 connection 不返却) —
        `runtime_checkable Protocol`、`schema_name`/`columns`/`row_count`/`iter_rows` のみ公開
  - [x] `EvaluationContaminationError` exception + `assert_no_metrics_leak` /
        `assert_no_sentinel_leak` 純 helper、`ALLOWED_RAW_DIALOG_KEYS` /
        `FORBIDDEN_METRIC_KEY_PATTERNS` allow/deny list
  - [x] **最小 P0b skeleton** `src/erre_sandbox/evidence/eval_store.py` —
        `connect_training_view(path) -> RawTrainingRelation` のみ実装
        (read_only=True 強制 + 物理 schema introspect で allow-list 違反を construction 時 raise)。
        schema bootstrap / `connect_analysis_view` / `export_raw_only_snapshot` は P0c
  - [x] `tests/test_evidence/test_eval_paths_contract.py` 全 14 ケース PASS:
    - [x] sentinel "M9_EVAL_SENTINEL_LEAK_*" rows fixture (raw_dialog + metrics 両方に
          シードして red-team 化)
    - [x] `connect_training_view()` の columns/iter_rows/row_count/protocol 適合
    - [x] poisoned `metric_burrows_delta` 列で construction が raise
    - [x] missing table で construction が raise
    - [x] relation が `execute`/`sql`/`query`/`cursor`/`conn`/`connection` を public
          attr として持たない (constrained facade 検証)
    - [x] `assert_no_metrics_leak` / `assert_no_sentinel_leak` の正常系・異常系
    - [x] 既存 `cli/export_log.py` egress: 出力 JSONL 全行が ALLOWED_RAW_DIALOG_KEYS 部分集合、
          metric prefix 0 件 (LEAK_SENTINEL 値が utterance に混入してもスキーマ汚染なし)
  - [x] `pyproject.toml` に `duckdb>=1.1,<2` を core deps として追加 (eval extras 隔離は
        sentence-transformers / scipy / ollama / empath / arch の方針維持)
  - [x] `.github/workflows/ci.yml` に **eval-egress-grep-gate** job 追加 (補強層、
        training-egress allow-list = `cli/export_log.py` + `evidence/eval_store.py`、
        `"metrics.` / `'metrics.` のリテラル参照を fail させる、ローカル検証 PASS)
  - [x] フル test suite 1078 passed / 29 skipped / 14 deselected、mypy 0、ruff/format clean
- [x] [Mac] **P0c** — `src/erre_sandbox/evidence/eval_store.py` 拡張: **2026-04-30 完了**
  - [x] `bootstrap_schema(con)` — `raw_dialog.dialog` (15 列、`ALLOWED_RAW_DIALOG_KEYS`
        と module-load-time lockstep) + `metrics.tier_{a,b,c}` を CREATE IF NOT EXISTS で
        idempotent 化、3 回連呼でも raise しない
  - [x] `connect_training_view()` は P0b で skeleton 済 (本セッションは内部 helper を
        module-level `_inspect_raw_dialog_columns()` にリファクタ、SLF001 解消)
  - [x] `AnalysisView` + `connect_analysis_view(db_path)` — Mac 側 full read エントリ、
        `read_only=True` 強制、`__enter__` / `__exit__` 対応 (`Self` 戻り値)
  - [x] `export_raw_only_snapshot(src, out)` — `raw_dialog` のみ Parquet 出力、
        single-quote 含む path を ValueError、metric prefix を defence-in-depth で再検証
  - [x] `write_with_checkpoint(con)` — `CHECKPOINT` + `con.close()` (ME-2 step 1)
  - [x] `atomic_temp_rename(temp, final)` — `Path.replace` + same-fs `st_dev` 検証
        (ME-2 step 4)、cross-fs は OSError
  - [x] `tests/test_evidence/test_eval_store.py` 12 ケース全 PASS:
    - [x] bootstrap full allowlist / 3 metric tier / idempotency / training view zero rows
    - [x] analysis view metrics SELECT / context manager
    - [x] read_only enforcement (training view 内部 conn 経路 + analysis view 経路)
    - [x] export_raw_only_snapshot subset cols / no leak sentinel / quote rejection
    - [x] CHECKPOINT + atomic_temp_rename round-trip / overwrite existing target
  - [x] フル test suite 1090 passed / 29 skipped / 14 deselected (前回 1078 → +12 新テスト
        のみ追加、既存回帰なし)、mypy 0、ruff/format clean、grep gate 緑

### P1 — Tier A 5 metric (sub-module 構造)

- [x] [Mac] **P1a** — `src/erre_sandbox/evidence/tier_a/` 起草: **2026-05-01 完了**
  - [x] `__init__.py` — public re-export (`compute_burrows_delta` /
        `compute_mattr` / `compute_nli_contradiction` /
        `compute_semantic_novelty` / `compute_empath_proxy` +
        `BurrowsReference` / `BurrowsLanguageMismatchError`)
  - [x] `burrows.py` — **z-scored function-word L1 (Manhattan)** 距離
        (Codex HIGH-5)。`BurrowsReference` frozen dataclass、per-language
        tag、`preprocessed_tokens` 経路で P1b の `ja` tokenizer 不在に
        対応、`std<=0` の word は L1 sum から drop、empty / no-counted
        は `nan` 返却 (M8 ``compute_*`` 契約と整合)
  - [x] `mattr.py` — Moving Average Type-Token Ratio (window 100)、
        text < window で plain TTR fallback、empty で `None`
  - [x] `nli.py` — DeBERTa-v3-base-mnli zero-shot 既定 loader を
        lazy import、unit test は `scorer` callable 注入で stub 化
  - [x] `novelty.py` — MPNet embedding を lazy import、aggregation は
        numpy のみで pure。`encoder` callable 注入で stub 化、prior
        centroid が ゼロベクトル化した場合は distance=1.0 fallback
  - [x] `empath_proxy.py` — Empath secondary diagnostic (Big5 claim 不使用)、
        `analyzer` callable 注入で stub 化
  - [x] `tests/test_evidence/test_tier_a/` 5 metric ごとに synthetic +
        4th persona heldout (38 unit test 全 PASS):
    - [x] `test_burrows.py` — 13 ケース (zero delta / NaN edge / std=0
          skip / preprocessed_tokens / language mismatch / unsupported
          language / persona-discriminative Kant↔Nietzsche / DB7 LOW-1
          synthetic 4th)
    - [x] `test_mattr.py` — 8 ケース (empty None / short fallback /
          repetition / novelty / window=10 vs 100 / window<1 raises /
          DEFAULT_WINDOW=100 不変 / persona-discriminative)
    - [x] `test_nli.py` — 5 ケース (empty None / 定数 scorer mean /
          mixed scorer / 空 scorer None / persona-discriminative)
    - [x] `test_novelty.py` — 7 ケース (<2 None / identical=0 /
          orthogonal=1.0 / antipodal centroid fallback / 空 encoder
          None / wrong shape raises / cyclic vs diverse)
    - [x] `test_empath_proxy.py` — 5 ケース (empty / passthrough /
          analyzer 空 dict / Big5 axis 注入禁止 / persona-discriminative)
  - [x] `pyproject.toml` — `[project.optional-dependencies] eval` に
        scipy / sentence-transformers / ollama / empath / arch を追加、
        pytest `markers` に `eval` 登録、mypy override に
        `transformers / sentence_transformers / empath / ollama / arch / scipy`
        を `ignore_missing_imports`
  - [x] `.github/workflows/ci.yml` の test job を `-m "not godot and not eval"`
        に切替 (CI default は `--all-groups` のみ install、heavy ML
        deps は extras に隔離されているため eval-marked test は default
        skip)
  - [x] フル test suite 1128 passed / 29 skipped / 14 deselected
        (前回 1090 → +38 新テスト、既存回帰なし)、mypy 0、ruff/format
        clean、eval-egress-grep-gate 緑
- [x] [Mac] **P1b** — reference corpus 整備: **2026-05-01 完了** (toy reference 路線、PD-only)
  - [x] `evidence/reference_corpus/_provenance.yaml` 5 entries
        (Kant de / Nietzsche de / Rikyu ja / synthetic_4th de+ja)、ME-6
        必須キー (source/edition/translator/year/public_domain/
        retrieval_url/retrieval_date/corpus_path/approx_tokens/
        corpus_too_small_for_chunk_qc/notes) を全エントリで埋め、
        public_domain=true を契約 test 化
  - [x] Kant 独原典 (Wikisource Akademie-Ausgabe Bd. VIII "Was ist
        Aufklärung?", 2656 words, PD verbatim、`raw/kant_de.txt`)
  - [x] Nietzsche 独原典 (Project Gutenberg eBook 7205 "Also sprach
        Zarathustra" Kröner-tradition PD edition, 12002 words 切出、
        `raw/nietzsche_de.txt`)。**KGW (Colli/Montinari) 採用せず** ME-6
        license precaution として PD edition 限定
  - [x] Rikyu 日 (Wikipedia 利休道歌 article verbatim 5 道歌、122
        tokens、`raw/rikyu_ja.txt`)。利休百首 / 南方録 / 徒然草 /
        方丈記 は ja.wikisource djvu index 構造で raw API 不可、本
        セッションでは 5 verbatim 道歌で toy reference 化
  - [x] **英訳経路 (Cambridge Edition Kant / Kaufmann Nietzsche) は
        本セッションでは扱わず** blockers.md "Burrows reference corpus —
        English translations defer" reopen 条件付きで defer
  - [x] synthetic 4th persona function-word vector (de + ja の 2 言語、
        profile_freq = background mean、DB7 LOW-1)
  - [x] `function_words.py` — DE 49 entries (articles/pronouns/
        conjunctions/prepositions、stylo R 系) + JA 23 particles
        (格助詞/副助詞/接続助詞/古典助動詞)
  - [x] `_build_vectors.py` — 決定的 stdlib-only build (Python 3.11
        statistics.pstdev + Counter)、background は per-language pooled
        chunks (de: 500-token / ja: 30-token) で mean+std 算出、
        `python -m erre_sandbox.evidence.reference_corpus._build_vectors`
        で再現可能、`vectors.json` を commit
  - [x] `loader.py` — `load_reference(persona_id, language) ->
        BurrowsReference` + `available_personas()` + provenance
        contract (未登録 pair は ReferenceCorpusMissingError)、
        `lru_cache` で multi-test 経路 keep
  - [x] `tests/test_evidence/test_tier_a/test_burrows_corpus_qc.py`
        16 ケース (14 pass / 2 documented skip):
    - [x] schema gate (provenance YAML 必須キー / public_domain=true /
          available_personas round-trip / 未登録 pair raise / cross-lang
          raise)
    - [x] synthetic_4th profile == background_mean (de + ja 両方、
          DB7 LOW-1)
    - [x] persona-discriminative on 800-token excerpts (Kant text closer
          to Kant ref than Nietzsche ref、vice versa) on real PD corpus
    - [x] Rikyu via preprocessed_tokens path → finite Δ (ja pipeline
          end-to-end without SudachiPy、tokenisation gap 確認)
    - [x] **ME-6 5K-word chunk stability test** (Nietzsche 12002 words →
          2× 5000-word chunks → 3-persona Δ vector の Spearman ρ ≥ 0.8、
          stdlib only 実装で eval extras 不要)
    - [x] Kant 2656 / Rikyu 122 token は ME-6 floor 未達のため explicit
          skip + reopen reason (m9-eval-corpus 後送)
    - [x] de background_std 全 49 word > 0 を契約 test
    - [x] BACKGROUND_CHUNK_DE=500 sentinel 化 (build と test の lockstep)
  - [x] フル test suite 1142 passed / 31 skipped / 14 deselected
        (前回 1128 → +14 新テスト、既存回帰なし)、mypy src 0、
        ruff/format clean、eval-egress-grep-gate 緑

### P2 — Stimulus + Orchestrator + Driver

- [x] [Mac] **P2a** — `golden/stimulus/{kant,nietzsche,rikyu}.yaml` 起草: **2026-05-01 完了**
  - [x] **LOW-1 RoleEval wording 決着** — Codex `gpt-5.5` 2026-05-01 review
        (`codex-review-low1.md`, 109,448 tokens) verdict "Adopt Option A"、Claude
        trade-off 4 軸分析と一致。Codex MEDIUM 5 + LOW 2 を ME-7 ADR と
        `_schema.yaml` に取り込み (mcq schema 11 field、within-persona floor
        diagnostic、cycle 1 only scoring、source_grade=legend は scoring exclude)
  - [x] `golden/stimulus/_schema.yaml` 起草 (single-source-of-truth、14 contract
        assertions、Pydantic 化は P2c で実施)
  - [x] Wachsmuth Toulmin 30 stimulus × 3 persona (claim 8 / data 6 / warrant 8 /
        backing 4 / qualifier 2 / rebuttal 2)
  - [x] ToM info-asymmetric 20 stimulus × 3 persona (first 8 / second 8 /
        recursive_third_order 4)
  - [x] RoleEval-adapted persona-specific MCQ 10 stimulus × 3 persona
        (chronology 2 / works 2 / practice 2 / relationships 2 / material_term 2
        の 5 種均等化、A-D forced choice、source_ref / source_grade /
        category_subscore_eligible / present_in_persona_prompt 必須)
        - Kant: source_grade=fact 8, secondary 2, legend 0 (全 scoring eligible)
        - Nietzsche: source_grade=fact 10 (全 scoring eligible)
        - Rikyū: source_grade=fact 7, secondary 1, legend 2 (待庵設計者・躙口
          発明者は伝承で eligible=false、scored 8/10)
  - [x] persona-conditional moral dilemma 10 stimulus × 3 persona
        (Kant: CI 5 + duty/inclination 3 + shared 2、
         Nietzsche: master/slave 3 + eternal recurrence 3 + will to power 2 + shared 2、
         Rikyū: wabi_calibration 4 + authority_inversion 3 + ma_silence 1 + shared 2)
  - [x] 計 70 stimulus × 3 persona = **210 stimulus 確定** (3 巡 = 630 turn 投入分)
  - [x] `tests/test_evidence/test_golden_stimulus_schema.py` 46 contract test 全 PASS
        (14 assertions × 3 personas + schema 検証 + prompt 非空検証)
  - [x] `blockers.md` LOW-1 closed (Option A 採用 + Codex 補強要約)
  - [x] `design-final.md` MEDIUM-1 wording 修正 (Kant biographical →
        persona-specific biographical / thought-history MCQ, within-persona floor
        diagnostic 明記)
  - [x] `decisions.md` ME-7 新 ADR 追加 (Option A 採択 + MCQ schema +
        scoring protocol + 4 件棄却理由 + 4 件 re-open 条件、ME-summary を
        6→7 件に update)
  - [x] `.codex/budget.json` 2026-05-01 invocation 記録 (109,448 tokens、
        per_invocation_max=200K 内、policy_action=ok)
- [x] [Mac] **P2b** — `src/erre_sandbox/integration/dialog.py` minimum patch:
      **2026-05-01 完了**
  - [x] `golden_baseline_mode: bool = False` keyword-only 引数を `__init__` に
        追加、public attribute として保持 (driver は phase 間で flip)
  - [x] **3 箇所 bypass** (golden_baseline_mode=True 時のみ):
    - `schedule_initiate` の `_REFLECTIVE_ZONES` チェック (Zone.STUDY 許容、
      Kant Wachsmuth/RoleEval / Nietzsche aphoristic burst / Rikyū wabi 議論等)
    - `schedule_initiate` の cooldown チェック (70 stimulus × 3 巡で同じ
      persona pair を 30 tick 待たずに反復可能)
    - `_close_timed_out` 全体 (driver が close_dialog を明示呼び出すため
      timeout race を回避)
  - [x] **保持される invariant** (両 mode 共通):
    - `initiator_id == target_id` は両 mode で reject (programming error)
    - 既に open な pair の二重 open は両 mode で reject (`pair_to_id` 衝突)
  - [x] default False で既存全テスト pass (test_dialog 関連 70 件、回帰なし)
  - [x] `tests/test_integration/test_dialog_golden_baseline_mode.py` 10 件全 PASS
        (default behaviour / zone bypass / cooldown bypass / timeout suppression /
        invariant 保持 / runtime toggle の 6 シナリオ)
- [x] [Mac] **P2c** — `src/erre_sandbox/evidence/golden_baseline.py` 起草 (Codex HIGH-4、3h):
      **2026-05-01 完了**
  - [x] `GoldenBaselineDriver` dataclass (公開 API `schedule_initiate` /
        `record_turn` / `close_dialog` のみ使用、`golden_baseline_mode=True`
        を構築時に強制、`enable_natural_phase()` で phase 切替、内部 tick
        cursor で多 stimulus を non-overlapping に配置)
  - [x] `derive_seed()` blake2b digest_size=8 → uint64 (ME-5 verbatim)、
        `_per_cell_seed()` + `shuffled_mcq_order()` (PCG64) で MCQ option
        seeded shuffle (ME-7 §1)
  - [x] `golden/seeds.json` (15 seed = 5 run × 3 persona) 生成 + commit、
        `assert_seed_manifest_consistent()` で Mac/G-GEAR 同値性 runtime guard
  - [x] `tests/fixtures/synthetic_4th_mcq.yaml` (DB7 LOW-1 / Codex LOW-2
        isolation、3 MCQ × `fictional: true, scored: false`、production
        `golden/stimulus/` から完全分離)
  - [x] `tests/test_evidence/test_golden_baseline.py` 23 ケース全 PASS:
    - [x] derive_seed verbatim formula / determinism / uint64 range
          (3 ケース)
    - [x] seed manifest committed file matches Python / round-trip /
          run_count 引数 / canonical sentinel value (4 ケース)
    - [x] MCQ seeded shuffle determinism / per-cell independence /
          seed_root divergence / option remap text preservation (4 ケース)
    - [x] synthetic 4th isolation: production loader rejects unknown
          persona / fixture loadable only via helper / fixture is outside
          production golden dir (3 ケース)
    - [x] driver requires golden_baseline_mode=True at construction
          (1 ケース)
    - [x] **`test_one_stimulus_cycle_dryrun`** synthetic 1 stimulus +
          mock LLM で full schedule → record × 2 → close cycle (1 ケース)
    - [x] **`test_70_stimulus_battery_drives_cleanly_through_three_cycles`**
          実 kant.yaml 70 stim × 3 cycle = 210 dialog 全 close、
          `scheduler.open_count == 0`、MCQ outcome は roleeval 10 × 3 = 30
          (1 ケース)
    - [x] natural phase toggle (`enable_natural_phase` で
          `golden_baseline_mode=False` 復帰) (1 ケース)
    - [x] **`test_cycle_1_only_scoring_excludes_repeats`** cycle 1
          scored / cycle 2-3 excluded with `cycle_not_first` (1 ケース)
    - [x] legend source_grade exclusion / category_subscore_eligible=False
          exclusion / off-format reply は scored=True is_correct=False /
          perfect mock yields correct post-shuffle label (4 ケース)
  - [x] フル test suite **1221 passed** / 31 skipped / 14 deselected
        (前回 1198 → +23 新テスト、既存回帰なし)、mypy src 0、ruff/format
        clean、eval-egress-grep-gate 緑

### P3 — Pilot then Golden Baseline (Codex HIGH-3 順序修正)

- [x] [GG] **P3a** — Pilot run **stimulus 200 + natural (≤30) × 3 persona** isolated 採取
      (fresh scheduler/store/seed、carry-over 防止、**完了 2026-05-01**、wall ~35 min)
      - **CLI 起草** (Step 1): commit `3e511e1` の `cli/eval_run_golden.py` で
        Codex `gpt-5.5 xhigh` review HIGH 6 件 (stratified slice / focal-turn budget /
        fail-fast sink / staged-rename / seeded RNG / drain timeout) を全反映、
        12 mock test PASS — 本セッションで実機検証
      - **採取側 wall budget reality**: stimulus は 200 focal を 2-3 min で完走、
        natural は M5/M6 runtime の "初動 burst → 以降停止" 挙動で 13 min 内に
        focal 0-6 (詳細は P3a-decide で別途 root-cause analyze、現状の dialog
        scheduler の admit 回路に gating bug の可能性)
      - **Codex HIGH 6 全反映実機検証**: stimulus 3 cell で
        focal_rows=198 / dialogs=168 / atomic_temp_rename 全成功 / fatal_error なし
      - **Mac → Windows OS シフト**: 設計 4090 24GB → 実機 RTX 5060 Ti 16GB +
        qwen3:8b Q4_K_M (5.2GB tag) で VRAM 余裕、Ollama 0.22.0
  - [x] stimulus 主体 (200 stimulus focal × 3 persona): **3 cell 全完走、各 focal=198 / total=342 / dialogs=168 / median utterance ~28-68 chars**
        - kant_stimulus_run0:      focal=198 / total=342 / dialogs=168 / wall ~2 min / median 68 chars / max 199
        - nietzsche_stimulus_run0: focal=198 / total=342 / dialogs=168 / wall ~3 min (concurrent w/ kant_natural) / median 45 chars / max 163
        - rikyu_stimulus_run0:     focal=198 / total=342 / dialogs=168 / wall ~3.5 min (concurrent w/ kant_natural) / median 28 chars / max 597
  - [x] 自然対話 主体 (target 30 focal × 3 persona、--wall-timeout-min 90 で並列): **partial**
        - kant_natural_run0:      focal=6 / total=12 / dialogs=2 / wall ~13 min (kill — 0 progress past initial burst)
        - nietzsche_natural_run0: focal=0 / total=0 / dialogs=0 / wall ~13 min (starved — 0 admissions)
        - rikyu_natural_run0:     focal=6 / total=18 / dialogs=3 / wall ~13 min (kill — 0 progress past initial burst)
        - **判断**: Mac 側 P3a-decide で M5/M6 dialog scheduler の admit 回路を
          inspect、`AUTO_FIRE_PROB_PER_TICK 0.25 + COOLDOWN_TICKS 30 + cognition_period_s
          7-18s` の組合せが期待した turn 量を生まない原因を特定。bootstrap CI 計算は
          stimulus side のみで実施可、natural side は次 G-GEAR セッションで再採取
  - [ ] [GG→Mac] 両形式の DuckDB を Mac へ rsync (CHECKPOINT + temp+rename + read_only=True、ME-2)
        — **本 PR では skip**、user が手動 rsync を後日実施 (`data/eval/pilot/_rsync_receipt.txt` placeholder commit)
        — Mac 側 atomic rename + acceptance + read_only 開封確認は P3a-decide セッションで実施
- [ ] [Mac] **P3a-decide** — bootstrap CI width 比較で ratio 確定 (本来 1h、実際は
      gating bug fix 込みで 4-6h、natural 再採取後に二度目の Mac セッションで
      最終 close):
  - [x] **2026-05-01 Mac セッション (本セッション)**:
    - [x] M5/M6 natural runtime gating bug の root-cause analysis 完了:
          `personas/{nietzsche,rikyu}.yaml` preferred_zones に AGORA 不在 +
          `ERRE_ZONE_BIAS_P=0.2` default で 53% per-tick zone drift →
          `_iter_colocated_pairs` 0 pair → admit 停止
    - [x] `.steering/20260430-m9-eval-system/design-natural-gating-fix.md` 起草
          (Plan + /reimagine 4 案比較 + 採用判断)
    - [x] 修正実装: `InMemoryDialogScheduler.eval_natural_mode: bool = False` flag、
          `_iter_all_distinct_pairs` ヘルパ追加、両 flag 同時 True を reject
    - [x] `cli/eval_run_golden.py:capture_natural` で `eval_natural_mode=True` opt-in
    - [x] `tests/test_integration/test_dialog_eval_natural_mode.py` 12 件
          (Red→Green 転換 + 5 invariant + 構築時 reject) 全 PASS
    - [x] **Codex `gpt-5.5 xhigh` independent review** 完了
          (`codex-review-prompt-natural-gating.md` → `codex-review-natural-gating.md`、
          76,961 tokens、Verdict: **ship**、HIGH=0 MEDIUM=0 LOW=2 全反映)
    - [x] 既存 1221 PASS 維持 (full suite **1248 passed** = 1221 + 12 new + 15
          bootstrap_ci tests)
    - [x] `src/erre_sandbox/evidence/bootstrap_ci.py` drafted (P5 prep を前倒し):
          `bootstrap_ci()` percentile + `hierarchical_bootstrap_ci()` cluster+block
          (Codex HIGH-2 の AR(1) 想定、N(0,1) 解析解 ± 5% / AR(1) 合成データで
          iid vs block CI width 差を assert)
    - [x] `tests/test_evidence/test_bootstrap_ci.py` 15 件全 PASS
    - [x] `scripts/p3a_decide.py` drafted: stimulus 3 cell の Burrows Delta + MATTR
          + (eval extras 任意で) NLI / novelty / Empath を CI 計算、
          `data/eval/pilot/_p3a_decide.json` 出力。**rsync 待ち**で missing files
          を検出した場合 exit 2 + ME-2 protocol 案内
    - [x] `decisions.md` ME-4 ADR partial update + 新規 ME-8 ADR 追加
    - [x] `g-gear-p3a-rerun-prompt.md` 起草 (次 G-GEAR セッション用、re-capture
          手順 + 期待値 + DB rsync protocol)
  - [x] **2026-05-01 Mac セッション v2 (本 P3a-decide v2 セッション)**:
    - [x] G-GEAR Phase A 失敗レポート (`g-gear-phase-a-failure.md`、PR #131) を Read、
          empirical cognition_period ≈ 120 s/tick を確定
    - [x] design v1 §2 で △ 補助棄却した仮説 B (cooldown × cognition_period の wall
          換算) を ◎ 主因に再格上げ確定
    - [x] `design-natural-gating-fix-v2.md` 起草 (G-GEAR 5 案 + Mac /reimagine 3 案 =
          8 案比較、α+β ハイブリッド採用、ζ/θ/ι 棄却理由明記)
    - [x] Codex `gpt-5.5 xhigh` independent review v2 完了
          (`codex-review-prompt-natural-gating-v2.md` → `codex-review-natural-gating-v2.md`
          145,717 tokens、Verdict: revise)
    - [x] HIGH-1 (wall default 不整合) / HIGH-2 (既存 cooldown test rewrite) /
          MEDIUM-1 (ME-8 explicit amendment) / MEDIUM-2 (conservative estimate
          primary 化) / Q5 (sentinel test 削除) / Q6 (eval cadence calibration
          命名) すべて反映
    - [x] 修正実装: `InMemoryDialogScheduler.COOLDOWN_TICKS_EVAL: ClassVar[int] = 5` +
          `_effective_cooldown()` helper、`schedule_initiate` / `tick()` の cooldown
          check 経由化。`_DEFAULT_WALL_TIMEOUT_MIN`: 90.0 → 120.0
    - [x] test rewrite 2 件 (`test_eval_natural_mode_uses_reduced_cooldown` /
          `test_eval_natural_mode_sustains_admission_after_initial_burst`) +
          新規 4 件 (`test_effective_cooldown_returns_eval_value_when_flag_true` /
          `test_effective_cooldown_returns_live_value_when_flag_false` /
          `test_live_mode_cooldown_unchanged_via_tick` / 
          `test_wall_timeout_min_default_is_120`) 全 PASS
    - [x] full suite **1251 passed** / 31 skipped / 27 deselected (baseline 1248 から
          default CI に +3、CLI test 1 件は eval marker で deselect)
    - [x] `decisions.md` ME-8 amendment 2026-05-01 ブロック追加 (二度目の partial
          update、explicit amendment with PR #131 empirical data)
    - [x] `g-gear-p3a-rerun-prompt-v2.md` 起草 (Phase A 期待値桁再校正、wall 120 min)
    - [x] `.codex/budget.json` 145,717 tokens 記録 (per_invocation_max=200K 内)
  - [ ] **next G-GEAR セッション v2** (rerun-prompt-v2.md を貼り付けて起動):
    - [x] fix v2 適用版 (`COOLDOWN_TICKS_EVAL=5` + wall default 120) で natural
          3 cell 再々採取 (focal>=25 target、Phase A 単独 sanity → Phase B 3 並列)
          — PR #133 で完了 (kant=30/90/15、nietzsche=30/90/15、rikyu=30/84/14)
    - [x] DuckDB rsync via `/tmp/p3a_rsync_v2/` snapshot + ME-2 protocol
          — 2026-05-05 G-GEAR HTTP server (192.168.3.85:8765) 経由で 6 snapshot
          pull + md5 6/6 一致確認 + atomic rename 完了
  - [x] **2026-05-05 Mac セッション (P3a-finalize、本 update で段階 (2) close)**:
    - [x] `scripts/p3a_decide.py` を v1 (stimulus_only) → v3 (stimulus_and_natural
          + target-extrapolated verdict + validation gate + known-limitation
          warning routing) に拡張 (16 unit test + 1 synthetic DuckDB E2E test 追加)
    - [x] **Codex `gpt-5.5 xhigh` independent review** 完了
          (`codex-review-prompt-p3a-finalize.md` → `codex-review-p3a-finalize.md`、
          80,837 tokens、Verdict: **block**、HIGH 3 / MEDIUM 4 / LOW 4 全反映)
    - [x] HIGH-1 (sample-size-confounded raw ratio): target-extrapolated widths
          (`width × sqrt(n / n_target)`、n_target_stim=200, n_target_nat=300) で
          verdict 計算するよう書き換え。raw / per-sample-variability / extrapolated
          の 3 view を payload に同居、verdict は extrapolated 一択
    - [x] HIGH-2 (Rikyu silent abort): `BurrowsTokenizationUnsupportedError` を
          `_per_utterance_burrows()` で per-utterance catch、cell 全体 error 化を
          回避。real run で発覚した「Rikyu Burrows 完全 skip」シナリオは
          `_KNOWN_LIMITATIONS` 経由で validation **warning** routing (errors では
          ない) → ratio は (kant, nietzsche) で算出可能、MATTR は 3/3 persona
    - [x] HIGH-3 (validation gate): `_validate_cells_for_ratio()` で 6 cell 全揃 /
          no errors / focal floor (stim>=150, nat>=25) / required metric 全揃を
          enforce、違反時は ratio 抑止 + exit 3
    - [x] MEDIUM 4 件 + LOW 4 件すべて反映 (proxy_metrics block / `_try_optional_metric`
          broad except / synthetic E2E test / partial cell rejection / 等)
    - [x] `uv run python scripts/p3a_decide.py` 実行 → `_p3a_decide.json` 生成
          (schema p3a_decide/v3、validation_errors=[]、validation_warnings=2)
    - [x] **empirical 実測値**:
          - Burrows Delta extrap: stim=6.09 / nat=2.49 / **ratio=0.41** (n_cells=2)
          - MATTR extrap: stim=0.0131 / nat=0.0130 / **ratio=0.992** (n_cells=3)
          - combined extrap ratio: 0.41 (Burrows scale-dominant、方向性は両 metric 一致)
          - **verdict**: `stimulus_wider_at_target_alternative_recommended`
    - [x] **ME-4 ADR partial update #3** (2 段階 close → 3 段階 partial close に
          再構造化、Vendi + Big5 ICC が P4 territory のため): ratio default 200/300
          を **暫定維持** + P4 / m9-eval-corpus tokenizer / DB9 quorum の 3 つの
          re-open 条件を明示。生 source `_p3a_decide.json` を verbatim 参照
    - [ ] M9-B `blockers.md` の "Hybrid baseline 比率 200/300" 項目を close
          (現状 M9-B blockers.md には該当項目なし。本セッションでは追加せず、
          ratio 確定時に M9-B 側へ通知 / 必要なら起票)
    - **段階 (3) 移行**: P4 完了後に Vendi + Big5 ICC を含む full ratio を再算出、
      ME-4 ADR partial update #4 (段階 (3) close) で最終確定する。tasklist は
      P4 phase (P4a / P4b) のチェックリストで受け継ぐ。
- [ ] [GG] **P3** — Golden baseline 採取 (3 persona × 5 run × 500 turn、確定 ratio 投入、
      ~24h wall × overnight×2):
  - [ ] qwen3:8b FP16 ~16GB / RTX 4090 24GB
  - [ ] 採取後 CHECKPOINT → temp+rename → rsync to Mac (ME-2)
- [ ] [Mac→GG] **P3-validate** — `python -m erre_sandbox.cli.eval_audit` で
      3 persona × 5 run × 500 turn = 7500 turn 完全性確認

### P4 — Tier B 3 metric (post-hoc)

- [ ] [Mac] **P4a** — `src/erre_sandbox/evidence/tier_b/` 起草 (CPU + 7B-Q4 借用、5h):
  - [ ] `vendi.py` — Vendi Score (semantic kernel)
  - [ ] `ipip_neo.py` — IPIP-NEO 短縮版 agentic loop (deterministic temperature=0)
    - [ ] acquiescence index / straight-line / reverse-keyed diagnostic (ME-1)
    - [ ] base model control measurement (persona prompt 無し 1 run)
  - [ ] `big5_icc.py` — Big5 stability ICC (across run × mode)
    - [ ] ME-1 fallback trigger 自動チェック (≥2/3 ICC <0.6 OR lower CI <0.5)
  - [ ] `tests/test_evidence/test_tier_b/` (3 metric)
- [ ] [GG] **P4b** — Tier B 後付け実行 (採取済 raw_dialog から、2h):
  - [ ] G-GEAR 上で 7B-Q4 + IPIP-NEO loop 実行
  - [ ] metrics schema へ投入完了

### P5 — Bootstrap CI (DB9 quorum prep)

- [ ] [Mac] **P5** — `src/erre_sandbox/evidence/bootstrap_ci.py` 起草
      (Codex HIGH-2、3h):
  - [x] hierarchical bootstrap: outer cluster (run) + inner block (circular block / 500-turn)
        — 2026-05-08 P5 hardening PR で完了 (`hierarchical_bootstrap_ci`)
  - [x] block length 自動推定 (autocorrelation 経由) + sensitivity grid
        — 2026-05-08 P5 hardening PR で完了 (`estimate_block_length` Politis-White-inspired
        + `auto_block=True` flag)
  - [x] Tier B per-100-turn は cluster-only resample (effective sample size 25
        window/persona と report 明示)
        — 2026-05-08 P5 hardening PR で完了 (`cluster_only=True` flag、method
        label `hierarchical-cluster-only` で identification 可能)
  - [ ] 3 sub-metric (Vendi / Big5 ICC / Burrows Delta) の CI 計算 ready
        (P4a Tier B 実装後に統合確認)
  - [x] `tests/test_evidence/test_bootstrap_ci.py`:
    - [x] N(0,1) n=500 既知分布で 95% CI 解析解 ± 5%
          — 既存 `test_bootstrap_ci_iid_normal_within_analytic_bound`
    - [x] **AR(1) 合成 turn metric** で iid vs block CI width 差を assert
          — 既存 `test_hierarchical_bootstrap_widens_ci_on_ar1_correlation`
    - [x] block length auto-estimation: white noise → ~1、AR(1) → 拡大、max_block 尊重
          — 2026-05-08 P5 hardening PR (6 新規 tests)
    - [x] cluster_only mode + cluster_only overrides auto_block
          — 2026-05-08 P5 hardening PR
    - [ ] Vendi orthogonal one-hot で score=N (P4a Tier B 実装後)
    - [ ] Big5 ICC 同一回答列で 1.0 収束 (P4a Tier B 実装後)
- [ ] [Mac] **P5-trigger** — ME-1 fallback トリガ確認:
  - [ ] ≥2/3 personas で ICC < 0.6 OR lower CI < 0.5 の場合、
        BIG5-CHAT regression head 実装 ADR を `decisions.md` に child 起票

### P6 — Tier C nightly (parallel from P0 onward)

- [ ] [Mac→GG] **P6** — Tier C systemd unit + judge LLM client (4h):
  - [ ] `src/erre_sandbox/evidence/tier_c/{prometheus,geval,bias_mitigation}.py`
  - [ ] `infra/systemd/erre-eval-tier-c.{service,timer}`:
    - [ ] `flock -n -x /var/run/erre-eval-tier-c.lock` で全 command を enclose (ME-3)
    - [ ] `Persistent=false` 明示 (ME-3)
    - [ ] `nvidia-smi --query-gpu=memory.free` preflight (free<14GB なら exit 75)
  - [ ] autonomous loop に `flock -s` 共有 lock 追加 (ME-3 integrate)
  - [ ] `journalctl --user -u erre-eval-tier-c` で skip 履歴可視
  - [ ] judge bias mitigation runbook 起草 (M9-B blockers から継承、本タスクで close)

## Phase 3 — Closure

- [ ] [Mac] CI gate 全緑 (sentinel test / grep gate / contract snapshot 不変)
- [ ] [Mac] DB9 sub-metric 3 個 (Vendi / Big5 ICC / Burrows Delta) の bootstrap CI
      数値が `evidence/eval_store.py` から取得可能を確認
- [ ] [Mac] requirement.md 受け入れ条件 9 件全 [x] 化
- [ ] [Mac] `git diff` scope 整合確認 (Tier 0/A/B/C 一部 + golden 採取コードのみ、
      LoRA training / M9-C-spike 混入無し)
- [ ] [Mac] 単一 commit で scaffold + design + 実装 + 採取 をまとめて commit
      (ユーザー指示) → PR 作成
- [ ] [Mac] PR description で `codex-review.md` をリンク参照、HIGH 5 件反映状況を明記

## Risk monitor (本セッション以降に watch)

- ME-1 fire watch: P5 完了直後判定
- ME-4 ratio confirm: P3a-decide 時に ADR 更新
- LOW-1 RoleEval wording: P2a 着手時に option A/B/C 確定
- Burrows corpus license: P1b 着手時に edition 採否
- Tier B sub-metric discriminative 確認: golden baseline 採取後

## Hours estimate (本タスク総量)

| Phase | Owner | Hours |
|---|---|---|
| Phase 1 (完了) | Claude | 5 |
| P0a-P0c | Claude (Mac) | 4 |
| P1a-P1b | Claude (Mac) | 8 |
| P2a-P2c | Claude (Mac) | 9 |
| P3a + P3a-decide | Operator (GG) + Claude (Mac) | 7-9 |
| P3 (golden baseline) | Operator (GG) | ~24h wall (overnight×2) |
| P3-validate | Mac→GG | 1 |
| P4a-P4b | Claude (Mac) + Operator (GG) | 7 |
| P5 + P5-trigger | Claude (Mac) | 3-4 |
| P6 | Claude (Mac→GG) | 4 |
| Closure | Claude (Mac) | 2 |
| **Total** | | **~50-55h Claude work + ~32h G-GEAR wall** |

solo cadence で **3-4 calendar weeks**、M9 milestone delay は M9-B 計画の
1→4 タスク化で既に bounded。

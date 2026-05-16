# 設計 — Plan B eval generation + verdict 計算

## 0. Framing

prep PR #183 で記録された blocker 1 (Plan B eval shard 不在) + blocker 2
(`rescore_vendi_alt_kernel.py` の shard path hard-coded) を解消し、
DA-14 thresholds 不変のまま encoder agreement axis (3-of-4 primary のうち
2 以上要件) で kant ADOPT / Phase E A-6 (rank=16 spike) を判定する。

retrain artifact (`data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500/`、
eval_loss=0.18259、step 1500 best) を SGLang LoRA adapter として load、
v2 baseline と **同 protocol** で stim eval を採取し apples-to-apples 比較
を成立させる。

## 1. 実装アプローチ

### 1.1 Step 0: branch + steering

1. `git checkout main && git pull origin main`
2. `git checkout -b feature/m9-c-adopt-plan-b-eval-gen`
3. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/` 5 標準 file 起票

### 1.2 Step 1: `rescore_vendi_alt_kernel.py` CLI 拡張 (~30 min)

**変更内容** (`scripts/m9-c-adopt/rescore_vendi_alt_kernel.py`):

1. `--v2-shards` (kw-only `nargs="+"` Path、default `_V2_SHARDS`)
2. `--nolora-shards` (kw-only `nargs="+"` Path、default `_NOLORA_SHARDS`)
3. `--kernel-type` (`{semantic, lexical_5gram}` default `semantic`)
4. `--encoder` を kernel_type=lexical_5gram で optional 化
   (lexical_5gram は encoder 非依存、ただし allowlist 引き当てのため
   "lexical_5gram" を allowlist key として受ける)
5. `_encode_pool` を kernel_type 対応に拡張:
   - semantic: 従来通り (SentenceTransformer + L2 norm)
   - lexical_5gram: `TfidfVectorizer(analyzer="char_wb",
     ngram_range=(5,5), lowercase=True, norm="l2", sublinear_tf=False)`
     を全 pool (v2 + no-LoRA を merge) で fit、各 condition を
     transform して unit-normalized TF-IDF dense matrix を返す
6. payload の `encoder` フィールドは kernel_type=lexical_5gram 時
   `"lexical_5gram"` を記録 (allowlist key と一致)、`encoder_revision_sha`
   は `"n/a"` (allowlist 通り)
7. **D-2 allowlist は Plan B 用** (`.steering/20260517-m9-c-adopt-plan-b-
   design/d2-encoder-allowlist-plan-b.json`) を参照:
   - `_D2_ALLOWLIST_PATH` を CLI flag `--allowlist-path` で override 可能化
     (default は既存 Plan A path、Plan B 用は明示指定)

**テスト** (`tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py`):

- CLI parsing test: `--v2-shards a.duckdb b.duckdb --nolora-shards
  c.duckdb --kernel-type lexical_5gram` の args 解釈
- backward-compat: flag 省略時 default が `_V2_SHARDS` / `_NOLORA_SHARDS`
- kernel-type validation: invalid value で `SystemExit`
- lexical_5gram path: `_encode_pool` が `make_tfidf_5gram_cosine_kernel`
  と整合する unit-normalized vectors を返すこと
  (importorskip("sklearn") guard、3 点セット遵守)

### 1.3 Step 2: SGLang server start + Plan B adapter load (G-GEAR WSL2)

K-α launch v5 invocation (DR-4 確定):

```bash
PYTHONUTF8=1 python -m sglang.launch_server \
    --model-path Qwen/Qwen3-8B \
    --host 0.0.0.0 --port 30000 \
    --quantization fp8 \
    --mem-fraction-static 0.85 \
    --max-total-tokens 2048 \
    --max-running-requests 1 \
    --disable-cuda-graph \
    --disable-piecewise-cuda-graph \
    --lora-paths kant_r8v3=/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500 \
    --max-loras-per-batch 1 \
    --max-lora-rank 8
```

**起動 verification**:
- `curl http://127.0.0.1:30000/v1/models` で adapter `kant_r8v3` が
  list されること
- micro smoke (~3 net、~60s) で sampler argmax kernel が deadlock しない
  こと (DR-4 教訓)

### 1.4 Step 3: Plan B eval shard 生成 (~5h GPU overnight)

**LoRA-on run × 2** (~1.5h × 2 = 3h):
```bash
python scripts/m9-c-adopt/tier_b_pilot.py \
    --persona kant --rank 8 --run-idx 0 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --lora-name kant_r8v3 \
    --output data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run0_stim.duckdb

python scripts/m9-c-adopt/tier_b_pilot.py \
    --persona kant --rank 8 --run-idx 1 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --lora-name kant_r8v3 \
    --output data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run1_stim.duckdb
```

**no-LoRA control run × 2** (~1h × 2 = 2h):
```bash
python scripts/m9-c-adopt/tier_b_pilot.py \
    --persona kant --no-lora-control --rank 0 --run-idx 0 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --output data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb

python scripts/m9-c-adopt/tier_b_pilot.py \
    --persona kant --no-lora-control --rank 0 --run-idx 1 \
    --turn-count 300 --cycle-count 6 --multi-turn-max 6 \
    --sglang-host http://127.0.0.1:30000 \
    --output data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb
```

**stimulus protocol** は v2 baseline (PR #160 era) と完全に同一
(`--turn-count 300 --cycle-count 6 --multi-turn-max 6`)。

### 1.5 Step 4: Shard 検証

```bash
python scripts/m9-c-adopt/validate_multiturn_shards.py \
    data/eval/m9-c-adopt-plan-b-verdict/*.duckdb
```

検証項目:
- alternation: focal speaker (kant) と stimulus speaker の交互性
- row count: 期待 turn 数 (~1800 turn = 300 turn × 6 cycle) との一致
- multi-turn 整合性: cycle 内で multi-turn-max=6 以内に収まっているか

### 1.6 Step 5: 4-encoder rescore (~1-2h CPU)

D-2 allowlist (Plan B) を `--allowlist-path` で指定:

```bash
# MPNet (primary)
python scripts/m9-c-adopt/rescore_vendi_alt_kernel.py \
    --encoder sentence-transformers/all-mpnet-base-v2 \
    --kernel-type semantic \
    --allowlist-path .steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json \
    --v2-shards data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run0_stim.duckdb \
                data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run1_stim.duckdb \
    --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run0_stim.duckdb \
                    data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run1_stim.duckdb \
    --output .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-mpnet-plan-b-kant.json

# E5-large (primary) — same with encoder swap + output suffix=e5large
# lexical-5gram (primary) — --encoder lexical_5gram --kernel-type lexical_5gram
# BGE-M3 (exploratory) — encoder swap + output suffix=bgem3
```

### 1.7 Step 6: Burrows / ICC / throughput

```bash
# Burrows reduction% (encoder 非依存)
python scripts/m9-c-adopt/compute_burrows_delta.py \
    --v2-shards data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run{0,1}_stim.duckdb \
    --nolora-shards data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run{0,1}_stim.duckdb \
    --output .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-burrows-plan-b-kant.json

# ICC(A,1) cross-recompute (Big-5 absolute agreement)
python scripts/m9-c-adopt/compute_big5_icc.py \
    --v2-shards ... --nolora-shards ... \
    --output .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-icc-plan-b-kant.json

# throughput pct of baseline
python scripts/m9-c-adopt/da1_matrix_multiturn.py \
    --shards ... --metric throughput \
    --output .steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-throughput-plan-b-kant.json
```

(各 script の正確な CLI は実装時に確認、現状 design ベース)

### 1.8 Step 7: verdict aggregator

新規 `scripts/m9-c-adopt/da14_verdict_plan_b.py` を起こす:

```python
# 入力: 4 rescore JSON + Burrows + ICC + throughput JSON
# 出力: da14-verdict-plan-b-kant.json + da14-verdict-plan-b-kant.md

def evaluate_encoder_agreement(rescores: list[dict]) -> dict:
    """3 primary (MPNet/E5-large/lexical-5gram) のうち 2 以上で
    natural_d <= -0.5 AND ci_upper < 0 AND lang_balanced_d <= -0.5
    AND length_balanced_d <= -0.5 AND 符号一致 (3 とも negative)."""
    ...

def evaluate_burrows(burrows: dict) -> bool:
    """reduction% >= 5 point AND ci_lower > 0."""
    ...

def evaluate_icc(icc: dict) -> bool:
    """ICC(A,1) >= 0.55."""
    ...

def evaluate_throughput(throughput: dict) -> bool:
    """throughput pct of baseline >= 70%."""
    ...

def aggregate_verdict(...) -> Literal["ADOPT", "PHASE_E_A6"]:
    """全 axis pass → ADOPT、1 axis でも fail → PHASE_E_A6."""
```

### 1.9 Step 8: kant ADOPT or Phase E A-6 判定 + decisions.md 記録

- 全 gate pass → `DR-1: kant Plan B ADOPT` を decisions.md に記録、
  次 PR (nietzsche/rikyu 展開) 用 next-session prompt 起票
- 1 axis fail → `DR-1: kant Plan B REJECT → Phase E A-6 (rank=16) 移行`、
  DA-16 ADR 起票候補を blockers.md に記録

### 1.10 Step 9: Codex independent review

`.steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review-prompt.md`
を起票し、以下を依頼:

- 4-encoder rescore JSON の整合性確認 (allowlist revision SHA 一致、
  CI bound 計算の正当性)
- verdict aggregator のロジック (encoder agreement axis の 3-of-4 計算、
  CI gate の境界条件)
- ADOPT/REJECT 判定の root cause assessment (どの axis が決定的だったか)
- HIGH/MEDIUM/LOW 形式で報告依頼

`cat .steering/<task>/codex-review-prompt.md | codex exec
--skip-git-repo-check` で起動、出力を `codex-review.md` に verbatim 保存。

### 1.11 Step 10: pre-push CI parity + commit + PR

```bash
# WSL2
bash scripts/dev/pre-push-check.sh
# 4 段 (ruff format --check / ruff check / mypy src / pytest -q) 全 pass で push 可
```

## 2. 変更対象

### 修正するファイル

- `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py` — CLI flag 拡張
  (`--v2-shards` / `--nolora-shards` / `--kernel-type` / `--allowlist-path`)
  + `_encode_pool` の kernel_type 対応 (semantic / lexical_5gram)

### 新規作成するファイル

- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/{requirement,design,
  tasklist,decisions,blockers}.md`
- `tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py`
- `scripts/m9-c-adopt/da14_verdict_plan_b.py`
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-{mpnet,
  e5large,lex5,bgem3}-plan-b-kant.json`
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-{burrows,icc,
  throughput}-plan-b-kant.json`
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.
  {json,md}`
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review-prompt.md`
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/codex-review.md`

### Track 化するファイル (generated, ~MB scale)

- `data/eval/m9-c-adopt-plan-b-verdict/kant_r8v3_run{0,1}_stim.duckdb`
- `data/eval/m9-c-adopt-plan-b-verdict/kant_planb_nolora_run{0,1}_stim.duckdb`

(DV-3 の forensic JSON only ポリシー類似だが、eval shard は再生成不可
コスト ~5h GPU で valuable artefact のため commit。サイズは既存 v2 shards
と同等 ~10 MB × 4 = ~40 MB スケールを想定、超過時は LFS 検討)

## 3. 影響範囲

- `rescore_vendi_alt_kernel.py` の既存 invocation (Plan A) は default
  値で完全 backward-compat、PR #179 / DA-15 既存 JSON 再生成は不要
- 新 directory `data/eval/m9-c-adopt-plan-b-verdict/` (Plan A / v2
  artifact に副作用なし)
- D-2 allowlist (Plan B) は本 PR では参照のみ、改訂しない

## 4. 既存パターンとの整合性

- forensic JSON commit、adapter binary は git 外 (PR #181 / #183 で同パターン)
- D-2 allowlist (Plan B) は PR #179 design で固定済、revision_sha 厳守
- vendi_lexical_5gram.py + `_load_default_kernel(kernel_type='lexical_5gram')`
  dispatch は PR #181 で merged 済、本 PR では consumer 側 (rescore script)
  を改修するのみ
- pre-push CI parity check (memory `feedback_pre_push_ci_parity.md`) を厳守

## 5. テスト戦略

- `tests/test_scripts/test_rescore_vendi_alt_kernel_cli.py` で CLI 拡張
  の 4 ケース (parsing / backward-compat / kernel-type validation /
  lexical_5gram path) を unit test
- lexical_5gram path には `pytest.importorskip("sklearn")` を必ず付与
  (extras-only 3 点セット、CLAUDE.md 禁止事項)
- 既存 `tests/test_evidence/test_vendi_lexical_5gram.py` (PR #181 で merged
  済) との整合性確認
- pre-push CI parity check (ruff format --check / ruff check / mypy src
  / pytest -q) を commit 前に必ず実行

## 6. ロールバック計画

- branch revert で全 artifact が消える (`feature/m9-c-adopt-plan-b-eval-gen`
  は main 派生で独立)
- ADOPT 判定後に新発見が出た場合、本 PR の verdict JSON を reference
  artefact として残し、新 PR で再評価
- Phase E A-6 移行判定後、DA-16 ADR (rank=16 spike) を別 PR で起票、
  本 PR の verdict は reference として保持

## 7. 設計判断 (本 PR 固有、decisions.md に記録予定)

- **DE-1**: lexical_5gram の rescore 内 dispatch は **pool-fit** semantics
  (v2 + no-LoRA 全 utterance を merge して TfidfVectorizer.fit、各 condition
  を transform して unit-normalized matrix → 既存 `_vendi_from_unit_
  embeddings` slicing pattern を流用) を採用。理由: (1) apples-to-apples
  IDF basis を両 condition で共有、(2) bootstrap iteration ごとの refit
  cost を回避 (~250s per encoder 削減)、(3) `make_tfidf_5gram_cosine_
  kernel` の per-window-fit semantics とは数値が一致しないが、DA-14
  rescore 設計は「全 pool で encode → window slice」が前提
  (semantic path も同様)

- **DE-2**: verdict aggregator script 名は `da14_verdict_plan_b.py`
  (新規) を採用。`da15_verdict.py` (Plan A) と並列存在させ、Plan A/B の
  axis 計算ロジックの差分を明示化 (encoder agreement axis 3-of-4 は
  Plan B 固有)

- **DE-3**: eval shard を `data/eval/m9-c-adopt-plan-b-verdict/`
  以下に commit (forensic JSON only ポリシー DV-3 の例外)。理由:
  re-generate cost ~5h GPU、artefact サイズ ~40 MB スケールは git で
  許容範囲、LFS 不要

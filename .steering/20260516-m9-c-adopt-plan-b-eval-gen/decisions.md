# 重要な設計判断 — Plan B eval generation + verdict 計算

> 本 file は本セッション固有の session-local decisions を記録する。
> 横断 ADR は `.steering/20260513-m9-c-adopt/decisions.md`、
> Plan B verdict prep は `.steering/20260518-m9-c-adopt-plan-b-verdict/
> decisions.md` DV-1〜DV-3、retrain prep は
> `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-1〜DR-7
> を参照。

## DE-1: lexical_5gram rescore は **pool-fit** TF-IDF (per-window-fit ではない)

- **判断日時**: 2026-05-17
- **背景**: Plan B D-2 primary の lexical_5gram は
  `vendi_lexical_5gram.make_tfidf_5gram_cosine_kernel` で **per-window-fit**
  semantics (TF-IDF を window 内で fit、外部 corpus と独立) を提供する。
  しかし `rescore_vendi_alt_kernel.py` の DA-15 設計は「全 pool で encode
  once → window slice」が前提 (semantic path も同様)。
- **選択肢**:
  - A: per-window-fit (production semantics 完全一致、bootstrap iteration
    ごとに TfidfVectorizer.fit_transform、~250s overhead per encoder)
  - B: pool-fit (TfidfVectorizer.fit_transform を v2+no-LoRA merged pool
    で一回実行、各 condition を transform して unit-normalized 行列 →
    既存 `_vendi_from_unit_embeddings` slicing pattern に流用)
- **採用**: B
- **理由**:
  1. **Apples-to-apples IDF basis**: 両 condition が同じ TF-IDF 重み付け
     空間で評価される。per-window-fit は window ごとに IDF basis が
     変動し、condition 間比較で artefact を生む可能性
  2. **bootstrap efficiency**: 2000 standard + 500 balanced × 3 strata =
     ~5000 iteration の TfidfVectorizer.fit_transform を回避
  3. **既存 semantic path との整合性**: MPNet/E5/BGE-M3 も全 pool で
     encode once → window slice (Plan A から不変)
- **トレードオフ**:
  - **DE-1 caveat**: pool-fit は `vendi_lexical_5gram.make_tfidf_5gram_
    cosine_kernel` の production 採取時 semantics と一致しない (per-
    window-fit)。Production `compute_vendi` 経由の score とは数値が
    異なる可能性あり。Codex review で MEDIUM 指摘の余地あり。
  - **Plan B kant shards は ~equal mass** (n_v2 ≈ n_nolora) で pool-fit
    の Simpson's-style artefact は低リスク。nietzsche / rikyu 展開時に
    asymmetric shards になる場合は再評価
- **影響範囲**: `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py::
  _encode_pools_lexical_5gram`、`tests/test_scripts/test_rescore_vendi_
  alt_kernel_cli.py::test_encode_pools_lexical_5gram_pool_fit_vs_per_
  window_fit` で pool-fit vs per-window-fit の非一致を明文化
- **見直しタイミング**: nietzsche / rikyu の Plan B 展開で shards が
  asymmetric になる場合、または Codex MEDIUM 指摘で pool-fit semantics
  の妥当性に疑義が出た場合

## DE-2: verdict aggregator は新規 `da14_verdict_plan_b.py` (Plan A 用 `da15_verdict.py` と並列存在)

- **判断日時**: 2026-05-17
- **背景**: Plan A 用 `da15_verdict.py` は「per-encoder eligibility +
  quorum 2-of-3 axes」の Plan A 固有ロジック。Plan B の encoder agreement
  axis (3-of-4 primary、2+ required、direction discipline) は別ロジック
  なので、`da15_verdict.py` を拡張すると Plan A/B の責務が混じる。
- **選択肢**:
  - A: `da15_verdict.py` に `--plan {A,B}` flag を追加し dispatch
  - B: 新規 `da14_verdict_plan_b.py` を起こし、Plan A は既存維持
- **採用**: B
- **理由**:
  1. Plan A は既に merged 済、追加 flag で既存 invocation を壊さない
     方が safer
  2. Plan B の encoder agreement axis は **Plan B 固有** の design
     decision (allowlist の `encoder_agreement_axis` block)。 Plan C
     以降で別 axis 設計が来た場合、aggregator は plan ごとに別 script
     にした方が読みやすい
  3. diff 最小化 — `da15_verdict.py` は変更不要、Plan A 既存 JSON 再
     生成も不要
- **トレードオフ**: 2 script の重複ロジック (load JSON、threshold 適用)
  が ~50 行発生。共通化は別 PR で commit 候補
- **影響範囲**: `scripts/m9-c-adopt/da14_verdict_plan_b.py` 新規。
  既存 `da15_verdict.py` 不変。
- **見直しタイミング**: Plan C 設計時に common library
  (`m9_c_adopt_verdict_lib.py`) を抽出するか判断

## DE-3: Plan B eval shards (`data/eval/m9-c-adopt-plan-b-verdict/`) は git で commit (DV-3 例外)

- **判断日時**: 2026-05-17
- **背景**: prep PR #183 の DV-3 は「adapter binary は git 外、forensic
  JSON のみ commit」とした。Plan B eval shards は ~10 MB × 4 = ~40 MB
  スケールで、再生成コストは **~30 min GPU** (本セッション実測、
  当初 5h 想定を大幅短縮)。
- **選択肢**:
  - A: git で commit (本 PR scope に含める、verdict reproducibility ↑)
  - B: .gitignore で除外 (re-generation 前提、git size 増 -)
  - C: HuggingFace Hub に push (binary は別 store、forensic JSON のみ
    git に)
- **採用**: A
- **理由**:
  1. ~40 MB は git で許容範囲 (LFS 不要、`data/eval/` には既に v2 baseline
     shards が ~80 MB commit 済の前例)
  2. verdict JSON が指す shards が repo 内にあると future reader が
     再現確認できる (rescore_vendi_alt_kernel.py を新 shards で再実行
     して数値を replay 可能)
  3. ~30 min 再生成は **GPU 占有** で軽くないコスト、artefact reuse の
     価値が高い
- **トレードオフ**: ~40 MB の git repo size 増。LFS 移行は将来課題。
- **影響範囲**: `data/eval/m9-c-adopt-plan-b-verdict/*.duckdb` 4 個を
  本 PR で commit。
- **見直しタイミング**: nietzsche / rikyu の Plan B 展開で shards が
  ~150 MB スケールになる場合、LFS 移行を検討

## DE-4: ICC は LoRA-on single-condition のみ計算 (no-LoRA ICC は computation skip)

- **判断日時**: 2026-05-17
- **背景**: DA-14 ICC(A,1) gate は **LoRA-on の Big-5 一貫性 ≥ 0.55** を
  要求する (kernel-independent axis)。`compute_big5_icc.py` は SGLang 推論
  ~30 min/condition を要する。v2 baseline での kant_r8v2 ICC は 0.91 で
  gate (0.55) を大きく上回り、Plan B retrain で同 Big-5 scoring 方法を
  使う限り 0.55 を下回る可能性は理論上低い。
- **選択肢**:
  - A: LoRA-on + no-LoRA 両方計算 (full apples-to-apples、+~30 min GPU)
  - B: LoRA-on のみ計算 (gate 評価に必要な値のみ、no-LoRA ICC は
    documented as out-of-scope of the gate)
  - C: v2 baseline ICC (0.91) を proxy で使う (computation skip、
    Plan B 数値は未検証)
- **採用**: B
- **理由**:
  1. DA-14 gate は **LoRA-on ICC ≥ 0.55** であり、no-LoRA ICC は gate
     入力でない (DA-15 verdict structure を踏襲)
  2. v2 verdict の `run_phase_3_4.sh` も LoRA-on ICC のみ計算した
     (`compute_big5_icc.py` 呼び出しは 1 回のみ)
  3. SGLang は本セッションで kant_r8v3 adapter を load 済、追加
     setup 不要
- **トレードオフ**:
  - no-LoRA Big-5 一貫性は本 PR で測定されない。ただし Plan B 設計で
    no-LoRA control の ICC は gate 寄与しないので実害なし
  - Codex review で MEDIUM 指摘の余地あり: "両 condition の ICC を
    並列報告すべき"。本 PR では gate-relevant 数値に絞る
- **影響範囲**: `scripts/m9-c-adopt/run_plan_b_post_eval.sh` Step 4 で
  `compute_big5_icc.py` は LoRA-on の 1 回のみ呼ぶ
- **見直しタイミング**: Codex MEDIUM 指摘で no-LoRA ICC 要求が出た
  場合、別 PR で `compute_big5_icc.py` を追加実行 (~30 min)

## DR-1: kant Plan B verdict = **PHASE_E_A6** (REJECT) → DA-16 ADR (rank=16 spike) 起票候補

- **判断日時**: 2026-05-17
- **背景**: Plan B retrain (kant_r8_v3、eval_loss=0.18259、best step 1500)
  に対し本 PR で eval shard 採取 + 4-encoder rescore + Burrows + ICC +
  throughput を実施。`da14-verdict-plan-b-kant.json` の結果:

  | axis | result | gate | comment |
  |---|---|---|---|
  | Encoder agreement | **FAIL** | 3-of-4 primary, 2+ | 0/3 primaries pass all 3 axes; direction discipline FAIL (MPNet −, E5/lex5 +) |
  | Burrows reduction% | **FAIL** | ≥5pt + CI lower>0 | −1.95% (LoRA-on Burrows 114.71 > no-LoRA 112.52) |
  | ICC(A,1) | PASS | ≥0.55 | 0.9083 |
  | Throughput pct | PASS | ≥70% | 99.17% |

  Per-encoder natural d:
  - MPNet: −0.5264 (negative direction, but std_pass=False due to CI)
  - E5-large: **+0.4781** (opposite sign — retrain shifted Vendi
    semantic ↑, not ↓)
  - lexical_5gram: +0.1805 (opposite sign)
  - BGE-M3 (exploratory): +0.3317

- **採用**: kant ADOPT を REJECT、Phase E A-6 (rank=16 spike) 移行を確定。
  DA-16 ADR を別 PR で起票し、rank=16 hypothesis (capacity expansion)
  vs corpus tuning (training signal 不足) vs WeightedTrainer Blocker 2
  (sample weight collapse、retrain blockers.md ブロッカー 2) の影響を
  切り分ける spike を設計する。

- **REJECT 根因仮説**:
  1. **WeightedTrainer sample weight collapse** (retrain Blocker 2、
     batch_size=1 で weight が数学的に相殺): DA-14 weighting (de monolog
     優先) が training 中に効いていなかった可能性。eval_loss は下がる
     (general loss objective) が DA-14 axis (style/diversity gate) は
     改善しない結果と整合
  2. **rank=8 capacity 不足**: kant の Burrows/style 信号は de
     monolog にしかなく、rank=8 では capacity が足りない可能性。
     rank=16 で再 retrain が次のステップ (Phase E A-6)
  3. **encoder direction disagreement**: MPNet 負・E5/lex5 正は
     "Plan B retrain が一部の encoder で persona shift を逆方向に
     誘発" を示唆。retrain corpus の de_monolog (Akademie-Ausgabe)
     が persona style を **MPNet 視点では強化、E5/lex5 視点では
     dilute** している可能性。DA-16 spike 設計時に corpus 分析が必要

- **影響範囲**:
  - 本 PR 完了後、nietzsche / rikyu の Plan B 展開を **保留** (kant
    で gate clear できない以上、他 persona も同様にコケる確率高い)
  - DA-16 ADR で rank=16 spike を別 PR で起票
  - WeightedTrainer Blocker 2 修正を別 PR で **優先** (retrain
    blockers.md ブロッカー 2 の暫定対応案 (a) `compute_loss` 内で
    weights.sum() 割り戻しを止める)

- **見直しタイミング**:
  - DA-16 spike (rank=16 retrain) の verdict が出た時
  - WeightedTrainer Blocker 2 修正後の retrain verdict が出た時
  - 上記 2 軸両方が試行された後、Plan A (encoder swap-only)
    との比較で「rank 拡大 vs weighting 修正」のどちらが効くか確定

## DE-5: Throughput axis は eval-sequence.log から rate を parse (shard metadata に rate 列なし)

- **判断日時**: 2026-05-17
- **背景**: 当初 `aggregate_plan_b_axes.py` は shard の
  `raw_dialog.metadata` テーブルから `pilot_rate_focal_per_s` を読む
  設計だったが、shard 検証で **metadata テーブル自体が存在しない** ことが
  判明 (`raw_dialog.dialog` + `main.pilot_state` のみ)。pilot_state には
  rate 情報が無い。
- **選択肢**:
  - A: `tier_b_pilot.py` を改修して shard に rate を保存 (`metadata`
    テーブル追加、~50 行 diff、本 PR scope 拡大)
  - B: eval-sequence.log を parse して `pilot done ... elapsed=X.X min
    completed=N` から rate を逆算
  - C: throughput axis を本 PR では skip して documented as
    "carried from v2 baseline"
- **採用**: B
- **理由**:
  1. `tier_b_pilot.py` 改修は本 PR scope 外 (eval generation は scope
     1.2 step 1 で固定済、driver 改修なし)
  2. eval-sequence.log の `pilot done` 行は安定 format (本セッションで
     生成された行を直接 inspect 済、4 run 全てで一致)
  3. throughput pct は cross-condition 比較で意味を持つ。log parse は
     forensic JSON の domain 拡張に過ぎず、verdict reproducibility は
     保たれる
- **トレードオフ**: log file format 変更で aggregator が壊れるリスク
  あり (`_shard_focal_rate_from_log` は脆い文字列 split)。`tier_b_pilot.
  py` の log format を変える別 PR が出たら本 aggregator も追従が必要
- **影響範囲**: `aggregate_plan_b_axes.py::_shard_focal_rate_from_log`、
  `aggregate_plan_b_axes.py::main` の throughput section
- **見直しタイミング**: `tier_b_pilot.py` の log format が変わったとき

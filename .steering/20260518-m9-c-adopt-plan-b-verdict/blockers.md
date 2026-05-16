# ブロッカー記録

## ブロッカー 1: Plan B eval shards (kant_r8v3_run*_stim.duckdb) が存在しない (SESSION-START BLOCKER)

- **発生日時**: 2026-05-16 (本セッション開始時に判明)
- **症状**:
  - next-session-prompt-FINAL-verdict.md は「DA-14 rerun verdict 計算 (~2h)」
    を要求するが、その入力となる Plan B eval shards が repository 内に存在しない:
    - `data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/kant_r8v2_run{0,1}_stim.duckdb`
      は **v2 baseline (existing)**
    - `data/eval/m9-c-adopt-tier-b-pilot-multiturn/kant_nolora_run{0,1}_stim.duckdb`
      は **no-LoRA SGLang baseline (existing)**
    - **Plan B LoRA-on shards** (`kant_r8v3_run*_stim.duckdb` 相当) は **未生成**
  - PR #181 の retrain artifact (`data/lora/m9-c-adopt-v2/kant_r8_v3/`) は
    LoRA adapter のみ生成、eval generation は scope 外
  - `data/eval/m9-c-adopt-plan-b/kant_de_monolog_run{0,1,2}.duckdb` は
    Plan B 用 **training corpus** (de monolog collector の出力) であり、
    DA-14 rescore の入力 shard 形式とは別
- **試したこと**:
  1. `Glob data/eval/**/*r8v3*.duckdb` → no files found
  2. `Glob data/eval/**/*planb*.duckdb` → no files found
  3. `Glob data/eval/m9-c-adopt-plan-b-verdict/**/*.duckdb` → no files found
  4. `rescore_vendi_alt_kernel.py` 確認 → hard-coded `_V2_SHARDS` /
     `_NOLORA_SHARDS` パスのみで Plan B shard を accept する仕組みなし
- **原因**:
  - next-session-prompt は retrain 完走後に **暗黙の前提** として eval
    shard 生成 (SGLang inference run) を必要とするが、prompt 内に
    "kant_r8_v3 で stim eval を採取する" step が明記されていない
  - retrain (model 学習) と eval generation (推論で stim 応答を採取) は
    別工程であり、retrain だけでは verdict 計算は走れない
  - 本セッションの ~2-2.5h envelope は **eval generation 抜き** で
    rescore + verdict computation のみを想定していたと推定される
- **暫定対応 (本 PR scope 候補)**:
  - 候補 (a): 本セッションで Plan B eval shards を生成する (~2-3h GPU 占有
    + Vendi/Burrows/ICC ~1h)。session envelope を **5-6h** に拡大、
    user 承認が必要
  - 候補 (b): 本セッションは branch 作成 + steering 文書化 + 次セッション用
    handoff prompt 整備に scope 限定。eval shard 生成 + verdict は別 PR/
    別セッションで分離 (本セッション ~30 min)。**本 PR の優先採用案**
  - 候補 (c): 既存 v2 rescore JSON (`.steering/20260516-m9-c-adopt-da15-impl/
    da15-rescore-*-kant.json`) を直接使い、Plan B retrain は eval_loss
    トラジェクトリの **proxy 評価** のみで verdict 判定 (recommend しない、
    DA-14 thresholds は v2 baseline で REJECT 確定済のため Plan B verdict
    の意味がなくなる)
- **解決方法**: candidate (b) を採用。本 PR の scope を以下に絞る:
  1. branch + steering 文書化
  2. retrain artifact 検証 + best checkpoint 確認 (step 1500、eval_loss=0.1826)
  3. lexical_5gram dispatch 検証 (vendi.py + vendi_lexical_5gram.py、merged 済)
  4. blocker 1 (本ブロッカー) の明文化 + 次セッション handoff prompt 整備
  5. retrain artifact の commit (untracked → tracked)
- **教訓**:
  - retrain handoff prompt には **必ず eval generation step を明示** する
    (LoRA adapter 作成 → SGLang serve → stim 推論 → shard 採取 → rescore)
  - "verdict 計算" を 1 step として書くと、その前段の eval generation が
    sunk cost として埋もれる。次回 handoff から「eval shard 生成 (~2-3h)」
    + 「verdict 計算 (~2h)」を 2 step に分けて record する

## ブロッカー 2: rescore_vendi_alt_kernel.py の shard path が hard-coded (Plan B 移行への壁)

- **発生日時**: 2026-05-16 (blocker 1 調査中に派生発見)
- **症状**:
  - `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py` の `_V2_SHARDS` /
    `_NOLORA_SHARDS` は module-level constant の Path tuple
  - Plan B shard 経路を受け付ける CLI flag (例: `--lora-shards` /
    `--baseline-shards`) が無い
  - 既存 script そのままでは Plan B verdict を計算できない、
    next-session で **script 改修** + **新規 shard 生成** の両方が必要
- **試したこと**:
  1. `rescore_vendi_alt_kernel.py` 冒頭の `_V2_SHARDS` / `_NOLORA_SHARDS`
     定数を確認
  2. argparse 部の CLI flag を確認 → shard path 入力なし、encoder と
     output しか CLI で受けない
- **原因**:
  - DA-15 Plan A 設計時に「v2 baseline 固定」を hard-code、Plan B のような
    別 LoRA artifact での再評価が想定されていなかった
- **暫定対応 (本 PR scope 外、次セッションへ繰り越し)**:
  - 候補 (a): `--v2-shards` / `--nolora-shards` を kw-only CLI flag で追加、
    default は既存 hard-coded path (backward-compat)
  - 候補 (b): 新 script `da14_rerun_plan_b.py` を起こし、Plan B shard
    path を最初から CLI で受ける設計
- **優先度判断のタイミング**: 次セッションで eval shard 生成 + verdict
  に着手する直前。`rescore_vendi_alt_kernel.py` の改修コストは
  ~30 min (CLI flag 追加 + test)、新 script は ~2h なので候補 (a) 推奨
- **教訓**:
  - DA-14/DA-15 系列の "rescore" script は **artifact-agnostic** に
    書くべき。固定 path を module constant に置くと、retrain ごとに
    別 fork が必要になる

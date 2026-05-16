# 重要な設計判断 — Plan B verdict prep (eval shard 不在の判明)

> 本 file は本セッション固有の session-local decisions を記録する。
> 横断 ADR は `.steering/20260513-m9-c-adopt/decisions.md`、
> retrain prep 判断は `.steering/20260518-m9-c-adopt-plan-b-retrain/
> decisions.md` DR-1〜DR-7 を参照。

## DV-1: 本セッション scope を「prep + blocker 文書化」に縮減 (eval generation は別 PR)

- **判断日時**: 2026-05-16
- **背景**: next-session-prompt-FINAL-verdict.md の「DA-14 rerun verdict
  計算 (~2h)」を実行しようとした結果、Plan B eval shards
  (`kant_r8v3_run*_stim.duckdb`) が repo 内に **未生成** と判明。retrain
  artifact (`data/lora/m9-c-adopt-v2/kant_r8_v3/`) は LoRA adapter のみで、
  inference run 結果は含まない。verdict 計算には新規 eval generation
  (SGLang + adapter 推論で stim 応答採取、~2-3h GPU 占有) が前提
  (blockers.md ブロッカー 1)。
- **選択肢**:
  - A: 本セッションで eval shard 生成 + verdict を一気に走らせる
    (session envelope を 5-6h に拡大、user 承認が必要)
  - B: 本セッションは prep + 文書化に絞り、eval generation + verdict は
    新 PR `feature/m9-c-adopt-plan-b-eval-gen` に分離
  - C: 既存 v2 rescore を proxy 流用 (recommend しない、retrain 効果を
    測定できない)
- **採用**: B
- **理由**:
  1. 本 PR の **検証可能な成果**: retrain artifact 確定 + best checkpoint
     特定 + lexical_5gram dispatch 検証 + blocker 明文化
  2. eval generation は GPU-bound で session envelope を著しく超過する。
     overnight job として別 PR に分離する方が観察可能性が高い
     (retrain 自体も overnight で完走、PR #181 と同パターン)
  3. blocker 1 (eval shard 不在) を repository 内に formal に記録する
     ことで、future reader が同じ罠に陥らない
  4. retrain artifact (kant_r8_v3 best checkpoint) は本 PR で track 化
     し、次 PR で safely 参照できる
- **トレードオフ**: 「verdict 判定」自体は次セッションへ繰り越し。
  ADOPT/REJECT の **結論** は本 PR では出ない。代わりに eval generation
  + rescore script 改修 (blocker 2) の handoff prompt を整備する。
- **影響範囲**:
  - 本 PR scope: retrain artifact track 化 + steering 5 file + handoff
    prompt
  - 次 PR scope: `rescore_vendi_alt_kernel.py` の CLI flag 拡張 (blocker 2)
    + Plan B eval shard 生成 + 4-encoder rescore + Burrows/ICC/throughput
    + verdict 判定
- **見直しタイミング**: 次 PR (eval generation) 完了後、本 PR で記録した
  blocker / decisions に反映漏れがないか cross-check

## DV-2: retrain best checkpoint = step 1500 (eval_loss=0.18259、v2 envelope 上端、EarlyStoppingCallback が step 1750 で fire)

- **判断日時**: 2026-05-16
- **背景**: `data/lora/m9-c-adopt-v2/kant_r8_v3/train_metadata.json` 確認:
  - `eval_loss=0.18258875` (final)
  - `train_loss=2.099` (final)
  - `realised_examples=5772`、`max_steps=2500`
  - `weighted=true`、`training_executed=true`
  - shard_stats: golden natural ×5 + golden stimulus ×5 + plan-b
    de_monolog ×3 = 13 shards、persona_examples 合計 ~5742
  - `metadata.audit_*`: n_eff=4358.4、top_5_pct=0.1249、de+en=0.6010、
    de=0.3854 (gate PASS、`plan-b-corpus-gate-final.json` と一致)
  - peak_vram=10.83 GB (16 GB VRAM の 67%、DR-5/DR-6 patch 効果で v2 の
    98% から大幅圧縮)
  - `checkpoint-1500/trainer_state.json`: `best_global_step=1500`、
    `best_metric=0.18258875`、`best_model_checkpoint=
    .../kant_r8_v3/checkpoint-1500`、`early_stopping_patience_counter=1`
  - retrain log tail: `train_kant_lora (weighted) completed: persona=kant
    rank=8 quant=nf4 realised=5772 synthetic_n=500 peak_vram=10.09GB
    train_loss=2.099 eval_loss=0.18258875` (2026-05-16 19:02 JST、
    PID 387 不在で確認)
  - eval_loss trajectory: 250→0.2582 → 500→0.2161 → 750→0.1965 →
    1000→0.1897 → 1250→0.1845 → 1500→0.1826 → 1750→0.1813 (log line 3821)
- **選択肢**:
  - A: best_metric の保守的解釈で step 1500 を採用 (HF Trainer 公式)
  - B: 最終 eval (step 1750、0.1813) を「true best」として採用 (改善幅
    0.0013 < 0.005 で early stopping が起動した checkpoint)
- **採用**: A
- **理由**:
  1. `trainer_state.json` の `best_model_checkpoint` が公式 contract、
     `data/lora/m9-c-adopt-v2/kant_r8_v3/` root dir の adapter も
     `checkpoint-1500/` と同 weight (load_best_model_at_end semantics)
  2. step 1500 → step 1750 の改善幅 0.0013 は EarlyStoppingCallback の
     `early_stopping_threshold=0.005` を下回り、HF の規約では
     "non-improvement" 扱い。verdict 計算側でも同じ閾値判定を踏襲する
  3. step 1750 checkpoint は disk に保存されていない (`save_steps=500`
     のため step 1500 と step 2000 のみ保存対象、step 2000 は早期停止で
     未到達)
- **トレードオフ**: 0.0013 の改善を捨てるため、verdict 計算側で
  marginal な signal loss 可能性。ただし DA-14 threshold (d≤-0.5) は
  この粒度では効かないので実害なし
- **影響範囲**: Plan B eval generation でも `checkpoint-1500/` を
  adapter として load、verdict 計算の baseline 検証用 input は固定

## DV-4: Windows 上の symlink test 3 件に skip mechanism を追加 (pre-push CI parity 達成のため)

- **判断日時**: 2026-05-16
- **背景**: pre-push-check.sh 実行で 3 件 fail:
  - `test_memory_db_rejects_symlink`
  - `test_memory_db_default_path_rejects_broken_symlink`
  - `test_memory_db_explicit_path_rejects_broken_symlink`
  原因: Windows で `Path.symlink_to()` が `OSError [WinError 1314]
  クライアントは要求された特権を保有していません` を raise。Windows は
  既定で symlink 作成に admin / dev mode が必要。CI (ubuntu-latest) では
  pass する pre-existing 問題。
- **選択肢**:
  - A: 既存 `test_build_mock_lora.py:51-61` のパターンを踏襲し、3 件に
    `try/except (OSError, NotImplementedError) → pytest.skip` を追加
  - B: `@pytest.mark.skipif(sys.platform == "win32", ...)` で marker
    による platform skip
  - C: Windows 上でも symlink を作れるよう dev mode を有効化する手順を
    `docs/development-guidelines.md` に追加
- **採用**: A
- **理由**:
  1. 既存パターン (`test_build_mock_lora.py`) と統一、reader の認知負荷
     最小
  2. WSL / FAT32 / NFS など symlink 非対応 FS でも safely skip できる
     (platform marker より broad)
  3. test 自体の semantics は不変、Linux / macOS では従来通り PASS
- **トレードオフ**:
  - Windows local 環境では本 test の symlink guard が **検証されない**。
    CI (Linux) で実証されるので security 観点では実害なし
- **影響範囲**: `tests/test_cli/test_eval_run_golden.py` のみ。本 PR
  scope を最小範囲で広げる代わりに、CLAUDE.md pre-push CI parity rule
  (memory `feedback_pre_push_ci_parity.md`) を本 PR で違反せずに済む。
- **見直しタイミング**: Windows native test environment を本格 setup
  する時 (dev mode + symlink privilege)、本 skip を削除して symlink test
  も Windows で走らせる

## DV-3: retrain artifact 群を本 PR で track 化 (commit) する範囲

- **判断日時**: 2026-05-16
- **背景**: `data/lora/m9-c-adopt-v2/kant_r8_v3/` には複数の untracked
  ファイルが存在:
  - LoRA artifact 本体 (adapter_model.safetensors、adapter_config.json、
    tokenizer files) — **2 GB スケール**
  - train_metadata.json、weight-audit.json、plan-b-corpus-gate.json
    (1 KB スケール、forensic evidence)
  - checkpoint-1000/、checkpoint-1500/ (各 50 MB スケール、
    optimizer state + scheduler state を含む)
- **選択肢**:
  - A: 全 artifact (2 GB + checkpoints) を git に commit
  - B: forensic JSON のみ commit (~10 KB)、adapter は別の artifact store
    (HuggingFace Hub / S3 / shared filesystem) に push
  - C: forensic JSON のみ commit + adapter は LFS で別管理
- **採用**: B
- **理由**:
  1. adapter は **2 GB スケール** で git に commit するのは適切でない
     (PR #181 でも同様の判断、`feature/m9-c-adopt-plan-b-retrain` には
     adapter を含めなかった)
  2. forensic JSON (train_metadata / weight-audit / corpus-gate) は
     1 KB 程度で blockchain 性が高く、本 PR で track 化する価値あり
  3. adapter 自体は **local disk + WSL2 経由で次 PR の eval generator が
     load する** ため、git 経由のシェアリングは不要
- **トレードオフ**: adapter のシェア性は git 外、別 PR の作業者は
  G-GEAR の local disk か HuggingFace Hub 経由で取得する必要がある。
  ただし Plan B は個人開発のため共有問題は実害なし。
- **影響範囲**: 本 PR で commit する artifact:
  - `data/lora/m9-c-adopt-v2/kant_r8_v3/train_metadata.json`
  - `data/lora/m9-c-adopt-v2/kant_r8_v3/weight-audit.json` (既存)
  - `data/lora/m9-c-adopt-v2/kant_r8_v3/plan-b-corpus-gate.json` (既存)
  - `data/lora/m9-c-adopt-v2/kant_r8_v3/adapter_config.json` (~1 KB)
  - 上記以外 (safetensors、tokenizer、checkpoints) は .gitignore で除外
    (既存パターン踏襲)

# 設計 — Plan B verdict (eval generation pre-flight + 計算)

## 0. Framing

next-session-prompt-FINAL-verdict.md の元想定は「retrain artifact が出来た
直後に DA-14 rerun verdict を走らせる (~2h)」だったが、本セッション開始時に
**Plan B eval shards (`kant_r8v3_run*_stim.duckdb`) が未生成** であることが
判明 (blockers.md ブロッカー 1)。retrain は LoRA adapter (`kant_r8_v3/`) を
生成しただけで、その adapter で stim 推論して shard 採取する工程が
prompt から漏れていた。

decisions.md DV-1 に基づき、本 PR scope は **prep + blocker 文書化** に
縮減する。eval generation + verdict 計算は次 PR
`feature/m9-c-adopt-plan-b-eval-gen` に分離。

## 1. 実装アプローチ

### 1.1 本 PR scope (prep)

1. `feature/m9-c-adopt-plan-b-verdict` branch を main (HEAD `7f944dc`、
   PR #182 merged) から分岐
2. `.steering/20260518-m9-c-adopt-plan-b-verdict/` 5 file 起票
   (requirement / design / tasklist / decisions / blockers)
3. retrain artifact の forensic JSON を track 化 (`train_metadata.json`、
   `adapter_config.json`、既存 weight-audit / corpus-gate は既存パス確認)
4. 次セッション handoff prompt
   (`next-session-prompt-FINAL-eval-gen-plus-verdict.md`) を作成し、
   eval generation + verdict + Codex review の手順を明示

### 1.2 次 PR scope (本 PR で先行設計、実装は別 PR)

1. **rescore_vendi_alt_kernel.py 改修** (blocker 2):
   - `--v2-shards` / `--nolora-shards` kw-only flag 追加、default は
     既存 hard-coded path (backward-compat)
   - argparse + module-level constant の整合性確保
2. **Plan B eval shard 生成** (`tier_b_pilot.py` 再利用):
   - SGLang server を WSL2 で起動、kant_r8_v3 adapter を load
     (`--lora-paths` で multi-pin: kant_r8v3 のみ)
   - LoRA-on run: `--rank 8 --multi-turn-max 6 --turn-count 300
     --cycle-count 6` × 2 run (`run0`、`run1`) → 2 shards、~1.5h × 2
   - no-LoRA control: `--no-lora-control --rank 0 --multi-turn-max 6
     --turn-count 300 --cycle-count 6` × 2 run → 2 shards、~1h × 2
   - 計 4 shards、~5h GPU 占有 (G-GEAR overnight)
3. **4-encoder rescore**: `rescore_vendi_alt_kernel.py` を改修済み版で
   MPNet / E5-large / lexical-5gram / BGE-M3 各々で実行 (~1h × 4 = 4h
   CPU、ただし embedding pre-compute で並列化可能)
4. **Burrows / ICC / throughput**:
   - `compute_burrows_delta.py` で Burrows reduction%
   - `compute_big5_icc.py` で ICC(A,1) cross-recompute
   - `da1_matrix_multiturn.py` で throughput pct of baseline
5. **encoder agreement axis 評価**:
   - 4-encoder の `da14-rescore-{encoder}-plan-b-kant.json` を集約
   - 3 primary (MPNet / E5-large / lexical-5gram) のうち 2 以上で
     natural d ≤ -0.5 AND CI upper < 0 AND lang-balanced d ≤ -0.5 AND
     length-balanced d ≤ -0.5 AND 符号一致 (3 とも negative)
   - 1 axis でも fail → Phase E A-6 (rank=16) 移行候補
6. **verdict aggregator**: 新規 `da14_verdict_plan_b.py` (or `da15_verdict.py`
   を Plan B 対応に拡張) で `da14-verdict-plan-b-kant.json` +
   `da14-verdict-plan-b-kant.md` を emit
7. **Codex independent review** (~30 min):
   `.steering/<task>/codex-review-prompt.md` 作成 →
   `cat ... | codex exec --skip-git-repo-check`
8. **Pre-push CI parity check** (必須、CLAUDE.md 禁止事項):
   `bash scripts/dev/pre-push-check.sh` 4 段全 pass
9. **commit + push + `gh pr create`**

## 2. 変更対象 (本 PR)

### 修正するファイル
- `tests/test_cli/test_eval_run_golden.py` — Windows 上の symlink test 3 件
  に `try/except (OSError, NotImplementedError) → pytest.skip` を追加
  (test_build_mock_lora.py L57-59 の既存パターン踏襲、pre-push-check.sh
  実行時に local 環境差分で fail していた pre-existing 問題を CI parity の
  ため吸収)

### 新規作成するファイル
- `.steering/20260518-m9-c-adopt-plan-b-verdict/requirement.md`
- `.steering/20260518-m9-c-adopt-plan-b-verdict/design.md` (本 file)
- `.steering/20260518-m9-c-adopt-plan-b-verdict/tasklist.md`
- `.steering/20260518-m9-c-adopt-plan-b-verdict/decisions.md`
- `.steering/20260518-m9-c-adopt-plan-b-verdict/blockers.md`
- `.steering/20260518-m9-c-adopt-plan-b-verdict/next-session-prompt-FINAL-eval-gen-plus-verdict.md`

### Track 化するファイル (untracked → tracked)
- `data/lora/m9-c-adopt-v2/kant_r8_v3/train_metadata.json` (forensic)
- `data/lora/m9-c-adopt-v2/kant_r8_v3/adapter_config.json` (forensic)
- `data/lora/m9-c-adopt-v2/kant_r8_v3/plan-b-corpus-gate.json` (forensic、
  既に存在)
- `data/lora/m9-c-adopt-v2/kant_r8_v3/weight-audit.json` (forensic、
  既に存在)

### .gitignore で除外する範囲 (既存パターン踏襲)
- `data/lora/m9-c-adopt-v2/kant_r8_v3/adapter_model.safetensors` (~30 MB)
- `data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-*/`
- `data/lora/m9-c-adopt-v2/kant_r8_v3/tokenizer*` (HF 規約のため別 PR で
  ignore policy 整理)

## 3. 影響範囲

- 既存 source code 変更なし (本 PR は documentation + artifact tracking
  のみ)
- 次 PR で `rescore_vendi_alt_kernel.py` を改修 (kw-only CLI flag 追加、
  default backward-compat)
- 次 PR で Plan B eval shards を `data/eval/m9-c-adopt-plan-b-verdict/`
  以下に生成 (新 directory、既存 v2 / Plan A artifact に副作用なし)

## 4. 既存パターンとの整合性

- forensic JSON のみ commit (PR #181 で同パターン、adapter binary は
  git 外)
- D-2 allowlist (Plan B) は `.steering/20260517-m9-c-adopt-plan-b-design/
  d2-encoder-allowlist-plan-b.json` で固定済、本 PR では参照のみ
- vendi_lexical_5gram.py は PR #181 (merge SHA `f68ac63`) で merged 済、
  `_load_default_kernel(kernel_type="lexical_5gram")` dispatch も wired up

## 5. テスト戦略

- 本 PR は documentation + artifact tracking のため、unit test 追加なし
- 次 PR で `rescore_vendi_alt_kernel.py` CLI flag 改修 test を追加
- pre-push-check.sh 4 段 (ruff format --check / ruff check / mypy src /
  pytest -q) を本 PR commit 前に必ず実行 (CLAUDE.md 禁止事項)

## 6. ロールバック計画

- 本 PR は documentation のみ。revert は steering directory 削除 +
  artifact JSON un-track のみで完結
- 次 PR (eval generation + verdict) は別 branch、本 PR とは独立して
  ロールバック可能

## 7. 次セッション handoff (eval generation + verdict)

詳細は `next-session-prompt-FINAL-eval-gen-plus-verdict.md` を参照。
本 file の §1.2 の 9 step が骨子。

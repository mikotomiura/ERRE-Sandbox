# Next-session 開始プロンプト — PR-3 kant_r8_v4 retrain (kant Plan B PHASE_E_A6 第 2 段)

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)

**前提**:
- PR-2 (WeightedTrainer `.mean()` reduce fix、本セッションで作成された
  `feature/m9-c-adopt-pr2-weighted-trainer-fix` 由来 PR) が merged 済
  (`.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/decisions.md`
  DP2-1〜DP2-3 で実装方針確定)
- `compute_weighted_causal_lm_loss` の reduce 式が `.mean()` に置き換わり、
  batch=1 + grad_accum 経路で DA-14 weighting が gradient に乗る state
- v3 retrain (`kant_r8_v3` adapter) は HuggingFace Hub に残置、forensic
  再現性のため deprecate しない
- DA-16 ADR DA16-2 トレードオフ: v3 と v4 の train_loss scale + 学習軌道
  は **直接比較不能**、eval_loss は **比較可能** (eval `sample_weight=1.0`
  + eval batch=1 で新旧式数値一致)
- DA-14 thresholds (Vendi natural d ≤ −0.5、Burrows ≥ 5pt + CI lower > 0、
  ICC ≥ 0.55、Throughput pct ≥ 70%) は不変 (DA16-4 で確定)

**branch**: 新規 `feature/m9-c-adopt-pr3-kant-r8-v4-retrain` を **main** から切る
**scope**: kant_r8_v4 retrain 実行 (~3h GPU) + forensic JSON commit (adapter
binary は HuggingFace Hub 経由で別 storage に push、git には forensic
`train_metadata.json` のみ commit)、~5h envelope (retrain ~3h + upload +
docs ~2h)
**Plan mode 任意**: 本 PR は retrain 実行 + artifact handling のみで新たな
設計判断なし。retrain 中の不測の事象 (eval_loss 上昇 等) が発生した場合
のみ Plan mode + /reimagine

---

```
m9-c-adopt PR-3 (kant_r8_v4 retrain) を実行する。DA-16 ADR + PR-2 で
WeightedTrainer `.mean()` reduce 修正が確定済 (`compute_weighted_
causal_lm_loss` が batch=1 で weight 効果を gradient に乗せる state)。
本 PR は retrain artifact 生成のみ、新たな数式変更はない。

## 目的 (本セッション、~5h envelope)

1. `feature/m9-c-adopt-pr3-kant-r8-v4-retrain` branch (main 派生) 作成
2. `/start-task` で `.steering/<YYYYMMDD>-m9-c-adopt-pr3-kant-r8-v4-retrain/`
   5 標準 file を template から起票
3. retrain 起動 (WSL2 経由、memory `reference_g_gear_gpu_training_via_
   wsl.md` で確認):
   ```bash
   wsl -d Ubuntu -- bash -c "
   cd /mnt/c/ERRE-Sand_Box
   PYTHONPATH=/mnt/c/ERRE-Sand_Box/src \
   PYTHONUTF8=1 \
   PLAN_B_MERGE_SHA=$(git rev-parse HEAD) \
   /root/erre-sandbox/.venv/bin/python -m erre_sandbox.training.train_kant_lora \
       --duckdb-glob '/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_*.duckdb \
                      /mnt/c/ERRE-Sand_Box/data/eval/m9-c-adopt-plan-b/kant_de_monolog_run*.duckdb' \
       --output-dir /mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v4 \
       --rank 8 --max-steps 2500 --eval-steps 250 \
       --weighted --plan-b-gate --lang-stratified-split -v
   " > .steering/<task>/retrain-stdout.log 2>&1
   ```
   (`--output-dir` の `kant_r8_v3` → `kant_r8_v4` だけが変更点。他フラグは
   v3 と完全同一で因果切り分けが clean)
4. retrain 完走確認 (~3h、step pace ~4 s/it 想定):
   - [ ] best step eval_loss が initial (`pre-train eval_loss=2.51` 程度)
         から有意に下がっている (v3 best `eval_loss=0.18259` を v4 と
         直接比較 OK、新旧式が eval 上数値一致するため)
   - [ ] `train_metadata.json` の WeightedTrainer 採用 flag + grad_accum
         settings が DR-5 と一致
   - [ ] retrain-stdout.log に CUDA OOM / NaN loss / sample weight error
         が出ていない
5. HuggingFace Hub に v4 adapter push:
   - `huggingface-cli upload mikotomiura/erre-kant-r8-v4-loraadapter
     /mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v4`
   - public/private 設定は v3 と揃える (private 想定)
   - v3 adapter は **deprecate しない** (forensic 再現性)
6. forensic JSON のみ git commit (binary は git 外、
   `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DV-3
   方針):
   - `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json` を commit
   - `*.safetensors` / `*.bin` / `optimizer.pt` 等は `.gitignore` で除外
     (既に除外されているはず、確認のみ)
7. Codex independent review (WSL2 経由):
   - 焦点は (a) retrain 完走の forensic 健全性、(b) v3 v4 trajectory 差分
     の妥当性、(c) eval_loss 比較が threshold 整合か
8. 続 PR-4 (DA-14 rerun verdict) 用 next-session prompt を起票
9. commit + push + `gh pr create --base main`

## NOT in scope (本 PR-3)

- DA-14 rerun verdict 計算 (別 PR-4 scope、`scripts/m9-c-adopt/
  run_plan_b_post_eval.sh` で eval shard 採取 + rescore + verdict)
- rank=16 spike (別 PR-5 scope、PR-4 REJECT 時のみ)
- nietzsche / rikyu Plan B 展開 (PR-4 ADOPT 後の別 ADR)
- `compute_weighted_causal_lm_loss` の数式再変更 (DA16-2 で確定済)
- thresholds 緩和 (DA16-4 で凍結確定)

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/decisions.md`
   DP2-1〜DP2-3 (実装決定の trace)
2. `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜DA16-4
   (本 PR 系列の上位 ADR)
3. `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-5 / DR-6
   / DR-7 (v3 retrain の WeightedTrainer 採用 + grad_accum / step pace
   実測値、本 PR で trajectory 比較の reference)
4. `.steering/20260518-m9-c-adopt-plan-b-retrain/design.md` L62-72
   (v3 invocation verbatim、本 PR は `kant_r8_v3` → `kant_r8_v4` のみ
   差し替え)
5. `src/erre_sandbox/training/train_kant_lora.py` argparse section
   (L1889 開始、CLI flag の解釈確認)
6. memory `reference_g_gear_gpu_training_via_wsl.md` (WSL2 / venv パス /
   PYTHONPATH 必須)
7. memory `feedback_pre_push_ci_parity.md` (push 前 4 段 check 必須、
   doc-only でも skip 禁止)
8. memory `project_plan_b_kant_phase_e_a6.md` (DA-16 採用候補 A の PR
   分割 graph + 進捗)
9. CLAUDE.md 「禁止事項」「Codex との連携」「Pre-push CI parity」

## 留意点 (HIGH 違反防止)

- **DA16-4 thresholds 不変宣言の厳守**: retrain の eval_loss が borderline
  でも threshold 移動禁止。v4 verdict は v3 と同じ gate で評価する
- **v3 adapter を deprecate しない**: HuggingFace Hub の `mikotomiura/
  erre-kant-r8-v3-loraadapter` は forensic 再現性のため残置。本 PR は
  v4 を **追加** するのみで v3 削除なし
- **eval_loss 比較は新旧式数値一致のため OK** (DA16-2 + Codex HIGH-1):
  eval examples は `sample_weight=1.0` (`train_kant_lora.py:761-765`)
  + eval batch=1 (`per_device_eval_batch_size=1`、DR-6) で `(l[0]*1.0)/1.0
  = (l[0]*1.0).mean() = l[0]`。v3 best `eval_loss=0.18259` と v4 best
  eval_loss を直接比較してよい
- **train_loss scale + 学習軌道の v3 v4 直接比較は禁止** (DA16-2 トレードオフ):
  step pace + best step 位置 + train_loss absolute value は新式で weight
  が gradient に乗るため変動する。v4 内部の収束確認のみで使う
- **forensic JSON は git commit、binary は HuggingFace に push**
  (`.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DV-3 方針)
- **WSL2 PYTHONPATH 必須**: `/mnt/c/ERRE-Sand_Box/src` を export しないと
  package import が壊れる (memory `reference_g_gear_gpu_training_via_
  wsl.md`)
- **PLAN_B_MERGE_SHA 設定**: `train_metadata.json` の commit SHA 埋め込み
  経路 (L1243)、forensic 再現性のため必須
- **CUDA OOM 監視**: retrain 中に OOM が発生したら DR-4 (SGLang inference
  と training は別 process、training serving は不要) を確認、`--max-
  total-tokens` の干渉なし。NF4 + rank=8 で VRAM 98% (DI-7 実測)
- **Pre-push CI parity check 抜きでの push 禁止** (CLAUDE.md 禁止事項)、
  retrain artifact 追加分も含めて 4 段 pass

## 完了条件

- [ ] `feature/m9-c-adopt-pr3-kant-r8-v4-retrain` branch (main 派生) 作成
- [ ] `.steering/<YYYYMMDD>-m9-c-adopt-pr3-kant-r8-v4-retrain/` 5 標準 file
      を template から起票
- [ ] retrain 完走 (~3h)、best step eval_loss が v3 `0.18259` ± rel_tol で
      意味のある収束を示す
- [ ] `train_metadata.json` を git commit (binary は除外)
- [ ] HuggingFace Hub に `mikotomiura/erre-kant-r8-v4-loraadapter` upload
- [ ] `pre-push-check.sh|.ps1` 4 段全 pass
- [ ] Codex independent review **WSL2 経由で起動**、`codex-review.md`
      verbatim 保存、HIGH 反映
- [ ] 続 PR-4 (DA-14 rerun verdict) 用 next-session prompt 起票
- [ ] commit + push + `gh pr create --base main`
- [ ] memory `project_plan_b_kant_phase_e_a6.md` を PR-3 merge 後 update
```

---

**実施推奨タイミング**: PR-2 merge 直後、~1 週間以内。PR-3 完走で PR-4
(DA-14 rerun verdict、~3h) を起動できる。nietzsche / rikyu Plan B 展開
は PR-4 verdict ADOPT 待ちで継続保留。

**本 PR-3 を本セッションで先回り起動した場合**: user 認可
(2026-05-17 session) に基づき、PR-2 merge を待たず同 session 内で
retrain を background 実行可能。完走後は本 prompt の Step 4 以降
(forensic JSON commit + HF push + Codex review + PR-4 prompt) を別
session か継続 session で実施する。

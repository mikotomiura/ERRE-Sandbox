# Next-session 開始プロンプト — PR-3 kant_r8_v4 forensic JSON commit (HF push 後送り)

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)

**前提**:
- PR #187 (PR-2 WeightedTrainer `.mean()` reduce、`feature/m9-c-adopt-pr2-weighted-trainer-fix`) が **merged 済** であることが PR-3 起票の precondition。merge されていない場合は本 prompt 実行前に PR #187 を merge する
- **kant_r8_v4 retrain は 2026-05-17 セッションで先回り実行済**:
  - 出力: `data/lora/m9-c-adopt-v2/kant_r8_v4/` (adapter_model.safetensors 30.7 MB + train_metadata.json + checkpoint-2000 (best) + checkpoint-2500 (final) + plan-b-corpus-gate.json + weight-audit.json + tokenizer.json + chat_template.jinja)
  - **best**: `eval_loss=0.18046` @ step 2000 (v3 best 0.18259 @ step 1500 から **−0.00213 改善**、Codex HIGH-1 反映で eval_loss は v3 v4 間で直接比較可能)
  - peak VRAM: 10.09 GB、wall-clock: 2h52m
- 本 PR-3 は **forensic JSON commit + Codex review** のみ。**HuggingFace Hub upload は PR-4 verdict ADOPT 確定後に実施** (REJECT 時の無駄 upload 回避 + HF Hub repo organisation を ADOPT 版に集中させるため)
- v4 adapter binary は **local + git 外で持ち続ける** (PR-4 verdict 計算は local path で adapter を load して実行)

**branch**: 新規 `feature/m9-c-adopt-pr3-kant-r8-v4-retrain` を **main** から切る
**scope**: forensic JSON commit + Codex review + PR-4 prompt 起票 (~1h envelope)
**Plan mode 任意**: artifact handling のみで新たな設計判断なし

---

```
m9-c-adopt PR-3 (kant_r8_v4 forensic JSON commit) を実行する。
kant_r8_v4 retrain は前セッション (2026-05-17) で実行済、本 PR は
forensic 数値のみ main に取り込む。HuggingFace Hub upload は PR-4
verdict ADOPT 確定後に PR-5 内で実施する (REJECT 時の無駄 upload
回避)。

## 目的 (本セッション、~1h envelope)

1. PR #187 (PR-2) merge 確認:
   `gh pr view 187 --json mergedAt,state` で mergedAt が non-null
   かつ state=MERGED であることを確認。未 merge なら user に確認
2. `feature/m9-c-adopt-pr3-kant-r8-v4-retrain` branch (main 派生) 作成
3. `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/` を 5 標準
   file (template から) で起票:
   - requirement.md: 「PR-2 retrain artifact の forensic JSON を main
     に取り込む。binary 本体は local + git 外で持ち続け、HF Hub upload
     は PR-4 verdict ADOPT 確定後の PR-5 で実施」
   - design.md: forensic JSON commit 対象 / 除外対象 + .gitignore
     pattern + PR-4 で adapter を local path 経由で load する経路
   - decisions.md: **DP3-1 (HF Hub upload を verdict ADOPT 後に後送り)**
     を主要設計判断として記録:
     - **背景**: v3 adapter は REJECT 後も HF Hub に残置されたが、
       v4 で同じ pattern を踏襲する必要はない。v3 は当時の workflow
       で push したのが結果的に baseline 比較用に役立っているだけ
     - **選択肢 A** (本採用): PR-3 で forensic JSON のみ commit、
       PR-4 ADOPT 後の PR-5 で HF Hub push (REJECT 時は push skip)
     - **選択肢 B**: PR-3 で HF Hub push 先行 (REJECT 時に repo 削除
       か rename が必要、HF Hub repo organisation が散らかる)
     - **採用理由**: (i) verdict 結果に依存しない artifact (forensic JSON)
       は早期 commit、(ii) verdict 結果に依存する公開行為 (HF push)
       は確定後、(iii) REJECT 時の cleanup コストゼロ、(iv) v3 baseline
       残置は別件、forensic 再現性は local + git で十分
     - **トレードオフ**: PR-4 verdict 計算は local path 経由で adapter
       を load する必要あり (HF Hub からの自動 download が使えない)。
       `data/lora/m9-c-adopt-v2/kant_r8_v4/` が PR-4 session マシン
       (本セッションでは G-GEAR) に存在する必要あり
     - **見直しタイミング**: PR-4 verdict ADOPT で PR-5 を起票するとき、
       本 DP3-1 で確定した「ADOPT 後 push」方針を再確認
   - tasklist.md: 下記 step 4-8 を checkbox 化
   - blockers.md: 該当なしで起票
4. **forensic JSON のみ git commit** (binary は git 外、
   `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DV-3
   方針):
   - commit 対象:
     - `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json`
     - `data/lora/m9-c-adopt-v2/kant_r8_v4/plan-b-corpus-gate.json`
     - `data/lora/m9-c-adopt-v2/kant_r8_v4/weight-audit.json`
     - `data/lora/m9-c-adopt-v2/kant_r8_v4/adapter_config.json`
     - `data/lora/m9-c-adopt-v2/kant_r8_v4/README.md`
   - 除外対象 (`.gitignore` で pattern 確認、不足あれば追加):
     - `adapter_model.safetensors` (30.7 MB)
     - `tokenizer.json` (11 MB)、`tokenizer_config.json`、`chat_template.jinja`
     - `optimizer.pt`、`rng_state.pth`、`scheduler.pt`、`training_args.bin`
     - `checkpoint-*/` directory 全部 (binary 全 file)
   - push 前に `git diff --cached --stat` で commit size を確認、
     合計 ~50 KB 以下が想定 (5 JSON + README で軽い)
5. Codex independent review (WSL2 経由、~10 min):
   - 焦点:
     (a) forensic 一貫性 — train_metadata.json の数値 (best_step=2000,
        eval_loss=0.18046, peak_vram_bytes=10.83e9, weighted=true) が
        v3 と同じ schema で記録されているか
     (b) v3 v4 eval_loss 直接比較の妥当性 — `sample_weight=1.0` +
        eval batch=1 の前提が train_metadata.json + checkpoint-2000
        の trainer_state.json に矛盾なく現れているか
     (c) **HF push 後送り判断 (DP3-1) の妥当性** — REJECT 時の cleanup
        コスト + ADOPT 後の push timing で「verdict 計算で adapter
        参照が必要な PR-4 が local path 依存になる」リスクが妥当か
     (d) .gitignore で binary 除外が機械的に効いているか、commit
        size が想定範囲か
   - prompt: `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/
     codex-review-prompt.md` に記述、WSL2 経路は PR-2 と同じ
6. 続 PR-4 (DA-14 rerun verdict) 用 next-session prompt を起票:
   - `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/next-
     session-prompt-FINAL-pr4-da14-rerun-verdict.md`
   - scope: `scripts/m9-c-adopt/run_plan_b_post_eval.sh` を v4 adapter
     で再実行 (~30 min eval shard 採取) → 4-encoder rescore (MPNet/
     E5/lex5/BGE-M3) → `aggregate_plan_b_axes.py` → `da14-verdict-
     plan-b-kant-v4.json` + `.md` 生成 (~3h envelope)
   - **重要な留意**: v4 adapter を **local path 経由で load**
     (`data/lora/m9-c-adopt-v2/kant_r8_v4/`)、HF Hub から自動 download
     しない (DP3-1 で push 後送り)。PR-4 session マシン (G-GEAR 想定)
     に同 path で adapter が存在することが前提
   - **PR-5 用 conditional prompt も同 file 内に併記**: PR-4 verdict =
     ADOPT なら PR-5 = HF Hub push (DP3-1 後送り分の実施)、PR-4 verdict
     = REJECT なら PR-5 = rank=16 spike retrain (HF push skip、別 adapter
     生成へ pivot)
7. pre-push CI parity check (\`scripts/dev/pre-push-check.ps1\`) 4 段全 pass
8. commit + push + \`gh pr create --base main\`
9. memory `project_plan_b_kant_phase_e_a6.md` を PR-3 push で update:
   - PR #xxx (PR-3) を「v4 forensic JSON commit、HF push は ADOPT 後
     PR-5 へ後送り (DP3-1)」と反映
   - 次は PR-4 verdict、PR-5 は ADOPT/REJECT で分岐

## NOT in scope (本 PR-3)

- **HuggingFace Hub upload** (DP3-1 で PR-4 ADOPT 後の PR-5 に後送り)
- kant_r8_v4 retrain の **再実行** (既にローカル、再実行で forensic
  連続性が壊れる)
- DA-14 rerun verdict 計算 (PR-4 scope)
- rank=16 spike (PR-5 (REJECT 経路) scope)
- nietzsche / rikyu Plan B 展開 (PR-4 ADOPT 後の別 ADR)

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/decisions.md`
   DP2-1 〜 DP2-5
2. `.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/next-session-
   prompt-FINAL-pr3-kant-r8-v4-retrain.md` (前身、HF push 先行版 — DP3-1
   で方針変更したので本 file が **採用版**、前身は historical reference)
3. `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜DA16-4
4. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1
   (kant Plan B v3 verdict REJECT) + DV-3 (forensic JSON のみ commit
   方針)
5. `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json` (本 PR で
   commit する main artifact)
6. `data/lora/m9-c-adopt-v2/kant_r8_v3/train_metadata.json` (v3 forensic、
   schema 整合性 reference)
7. memory `project_plan_b_kant_phase_e_a6.md`
8. memory `feedback_pre_push_ci_parity.md`
9. memory `feedback_batch_integration_over_per_session_sync.md`
10. CLAUDE.md 「禁止事項」「Codex との連携」「Pre-push CI parity」

## 留意点 (HIGH 違反防止)

- **v4 retrain は再実行しない**: ローカル adapter は PR-2 (`.mean()`
  reduce) 適用後の文脈で生成された authoritative artifact。再実行で
  異なる seed 軌道に乗ると forensic 連続性が壊れる
- **HF Hub に v4 を push しない (本 PR scope では)**: DP3-1 で verdict
  ADOPT 後の PR-5 に後送り。本 PR で push してしまうと REJECT 時に
  repo 削除 or rename の cleanup が必要になり、HF Hub repo organisation
  が散らかる
- **v3 adapter (HF Hub `mikotomiura/erre-kant-r8-v3-loraadapter`)
  を delete しない**: 既存の forensic 残置、PR-4 verdict 計算で v3
  baseline 参照に使う可能性あり (HF Hub からの自動 download path)
- **binary を絶対 commit しない**: adapter_model.safetensors (30.7 MB) +
  tokenizer.json (11 MB) + optimizer.pt + checkpoint-* 全除外。push 前に
  `git diff --cached --stat` で確認、想定 commit size ~50 KB 以下
- **v3 v4 eval_loss 直接比較は OK** (DA-16 codex review HIGH-1 反映):
  eval examples は `sample_weight=1.0` + eval batch=1 で旧式と新式が
  数値一致、v3 0.18259 と v4 0.18046 の差 −0.00213 は意味のある
  metric
- **train_loss + 学習軌道の v3 v4 直接比較は禁止** (DA16-2 トレードオフ):
  step pace + best step 位置 + train_loss absolute value は新式で
  weight が gradient に乗るぶん scale が変動する。v4 best_step=2000
  vs v3 best_step=1500 の差は「収束遅れ」ではなく「weighted gradient
  で更に signal 抽出できた」と解釈する
- **Pre-push CI parity check 抜きでの push 禁止** (CLAUDE.md 禁止事項)

## 完了条件

- [ ] PR #187 (PR-2) merged 済確認 (gh pr view)
- [ ] `feature/m9-c-adopt-pr3-kant-r8-v4-retrain` branch (main 派生) 作成
- [ ] `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/` 5 標準 file
      起票 (**DP3-1: HF push 後送り** が main 設計判断)
- [ ] forensic JSON 5 file を git commit (train_metadata + plan-b-gate
      + weight-audit + adapter_config + README、計 ~50 KB)
- [ ] `.gitignore` で binary 除外確認 (`adapter_model.safetensors` /
      `checkpoint-*` / `tokenizer.json` 等)
- [ ] Codex independent review WSL2 経由、`codex-review.md` verbatim 保存、
      HIGH 反映、特に DP3-1 の妥当性 (REJECT 時 cleanup vs PR-4 local
      path 依存リスク) を verify
- [ ] PR-4 (DA-14 rerun verdict) + PR-5 conditional (ADOPT→HF push /
      REJECT→rank=16) 用 next-session prompt 起票
- [ ] `pre-push-check.ps1` 4 段全 pass
- [ ] commit + push + `gh pr create --base main`
- [ ] memory `project_plan_b_kant_phase_e_a6.md` を PR-3 push で update
```

---

**実施推奨タイミング**: PR #187 (PR-2) merge 直後、~1 週間以内。PR-3
完了で PR-4 (DA-14 rerun verdict、~3h) を起動できる。

**本 prompt の方針変更 (前身 → 本版)**:

| | 前身 (`-kant-r8-v4-retrain`) | 本版 (`-artifact-only`、user feedback 反映) |
|---|---|---|
| PR-3 scope | retrain 実行 + HF push + forensic commit | **forensic commit のみ** |
| envelope | ~5h (retrain ~3h + upload + docs) | **~1h** |
| HF Hub push | PR-3 内 | **PR-4 ADOPT 後の PR-5 に後送り** |
| PR-5 scope | rank=16 spike (REJECT 時のみ) | **PR-4 ADOPT → HF push / REJECT → rank=16 で分岐** |

**user feedback (2026-05-17 セッション)**: 「verdict で ADOPT に判定が出てから
の HuggingFace のほうが良いのでは？」→ DP3-1 として ADR 化、PR-5 を verdict
分岐型に再定義 (ADOPT→HF push, REJECT→rank=16 retrain)。

**PR 分割 graph (本 user feedback 反映後)**:

```
DA-16 ADR (PR #186 merged)
  └→ PR-2 (.mean() reduce、PR #187 open)
       └→ PR-3 (v4 forensic JSON commit、HF push なし) ← 本 prompt
            └→ PR-4 (DA-14 rerun verdict、local path で adapter load)
                 ├→ ADOPT → PR-5 (HF Hub push、DP3-1 後送り分を実施)
                 │            → nietzsche / rikyu Plan B 展開 (別 ADR)
                 └→ REJECT → PR-5 (rank=16 spike retrain、HF push skip)
```

**v3 → v4 forensic 比較 (PR-3 PR description で再掲)**:

| | v3 (Blocker 2 未修正、PR #181) | v4 (`.mean()` reduce、PR-2) |
|---|---|---|
| best eval_loss | 0.18259 | **0.18046** |
| best step | 1500 | **2000** |
| peak VRAM | 16 GB の 98% (DI-7) | **10.09 GB** |
| wall-clock | 16h19m (v2) / 2h47m (v3 patched) | **2h52m** |
| adapter (HF Hub) | `erre-kant-r8-v3-loraadapter` (push 済、baseline 用) | **未 push** (PR-5 ADOPT 経路で実施) |
| retrain branch | feature/m9-c-adopt-plan-b-retrain | feature/m9-c-adopt-pr3-kant-r8-v4-retrain |

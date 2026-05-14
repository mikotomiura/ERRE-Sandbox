# Next-session handoff prompt — M9-C-adopt Phase B 第 4 セッション (Big5 ICC consumer + Burrows 言語処理 + semantic Vendi + DA-1 final + PR 起票)

**作成**: 2026-05-14 (Phase B 第 3 セッション完了後)
**前提**: 第 3 セッションで DA-11 scope narrowing 適用、SGLang LoRA pilot driver
新規実装、3 rank × 2 run × 300 turn = 1800 turn pilot 採取完了、Vendi
lexical-5gram baseline 算出、CS-7 per-rank single_lora bench (rank=4/8/16)
完了。Big5 ICC + Burrows + semantic Vendi は本 ADR (DA-11) で第 4 セッション
へ defer。
**用途**: 新セッション最初の prompt として貼り付け。本セッションは
**Step 5d (Big5 ICC consumer + per-rank metric + bootstrap CI) → Burrows
言語処理判断 → semantic Vendi 再算出 → DA-1 4 軸 intersection で final
採用 rank 確定 → Step 6 (conditional rank=32) → Step 7 (報告 + PR 起票)**
を実施。
**branch**: `feature/m9-c-adopt-phase-b-rank-sweep` (origin push 済、第 3
セッション commit ある)

---

```
M9-C-adopt の **Phase B 第 4 セッション** を実行する。第 3 セッション
(2026-05-14) で DA-11 scope narrowing 適用、SGLang LoRA Tier B pilot
driver 新規実装 (`scripts/m9-c-adopt/tier_b_pilot.py`)、3 rank × 2 run ×
300 turn = 1800 turn pilot 採取 (`data/eval/m9-c-adopt-tier-b-pilot/
kant_r{4,8,16}_run{0,1}_stim.duckdb` 6 shard)、Vendi lexical-5gram baseline
算出 (`tier-b-baseline-kant.md` + `tier-b-baseline-kant-vendi-lexical.json`、
point=75.77 / CI=[75.19, 76.37])、CS-7 per-rank single_lora bench
(`data/eval/m9-c-adopt-bench/single_lora-r{4,8,16}.jsonl`) を完遂した。
本セッションは **Big5 ICC consumer 実装 → per-rank Big5 ICC + Burrows Δ +
semantic Vendi 再算出 → DA-1 4 軸 intersection で final 採用 rank 確定 →
Step 6 (conditional rank=32 tail-sweep) → Step 7 (採用 rank 確定 + 報告 +
PR 起票)** を実施する。

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260513-m9-c-adopt/decisions.md` DA-11 (Phase B 第 3 セッション
   scope narrowing 根拠 + 第 4 セッション scope) + DA-1 (4 軸 intersection
   採用基準) + DA-9 (marginal pass retrain path)
2. `.steering/20260513-m9-c-adopt/tier-b-baseline-kant.md` (Vendi lexical
   結果 + Big5 ICC + Burrows defer 内容)
3. `.steering/20260513-m9-c-adopt/tier-b-baseline-kant-vendi-lexical.json`
   (Vendi point + CI + per-window detail)
4. `.steering/20260513-m9-c-adopt/phase-b-progress.md` (第 3 セッション完了
   サマリ)
5. `data/eval/m9-c-adopt-tier-b-pilot/kant_r{4,8,16}_run{0,1}_stim.duckdb`
   (6 shard、epoch_phase=evaluation)
6. `data/eval/m9-c-adopt-bench/single_lora-r{4,8,16}.jsonl` (per-rank bench)
7. `scripts/m9-c-adopt/tier_b_pilot.py` (pilot driver、SGLang LoRA routing)
8. `scripts/m9-c-adopt/compute_baseline_vendi.py` (Vendi consumer、--kernel
   semantic / lexical-5gram switch)
9. `scripts/m9-c-adopt/bench_per_rank.sh` (CS-7 per-rank bench wrapper)

## Phase B 第 4 セッション残 Scope

### 1. Big5 ICC consumer 実装 + 計算 (~25-35h compute、本 session 全体)

#### 1a: consumer script 起草 (~2h Mac master)

新規 script: `scripts/m9-c-adopt/compute_big5_icc.py`

機能:
- shards (DuckDB) を読み込み、per-window utterance を抽出
- `administer_ipip_neo(responder)` で per-window Big5Scores 算出
- `compute_big5_icc(big5_per_window)` で ICC(C,k) primary + ICC(A,1)
  diagnostic + bootstrap 95% CI (cluster_only=True、ME-14)
- responder 切替:
  - `--responder ollama --ollama-host http://localhost:11434
    --ollama-model qwen3:8b --ollama-think false` (no-LoRA baseline)
  - `--responder sglang --sglang-host http://localhost:30000
    --sglang-adapter kant_r{X}_real` (LoRA-on per-rank)
- per-window context conditioning: **none** (Salecha et al. 2024 anti-demand-
  characteristics 設計に従い、過去 window の context を IPIP 投与時に入れない)
- 出力: JSON (Vendi consumer と同 format)、`tier-b-icc-kant-{responder-id}.json`

#### 1b: no-LoRA baseline ICC 計算 (~9h Ollama compute)

5 shard × 5 window × 50 IPIP question + 5 decoy = 1375 inference per shard
= 6,875 total. Ollama qwen3:8b @ ~3-5s/inf = 6-10h.

```bash
# Mac master 側で Ollama qwen3:8b を確認 (think=false モード)
python scripts/m9-c-adopt/compute_big5_icc.py \
  --persona kant --shards-glob "data/eval/golden/kant_stimulus_run*.duckdb" \
  --responder ollama --ollama-host http://localhost:11434 \
  --ollama-model qwen3:8b --ollama-think false \
  --window-size 100 \
  --output .steering/20260513-m9-c-adopt/tier-b-baseline-kant-icc.json
```

DA-1 軸 2 thresholds: ICC(C,k) ≥ 0.6 point + CI lower ≥ 0.6.

#### 1c: per-rank LoRA-on ICC 計算 (~10h SGLang compute)

3 rank × 2 run × 5 window × 50 IPIP = 1500 inference per rank-run.
SGLang fp8 @ ~0.7s/inf = ~17 min per cell × 6 cells = ~1.7h SGLang compute
(faster than Ollama because pilot 採取 でも 1.5 turn/s 出ていた).

ただし SGLang は **同時に 1 adapter 投与 only** で IPIP 50 question を打つ
方が安全 (multi-pin で同時投与すると adapter ルーティング bias の可能性)。

```bash
# rank=4 LoRA-on ICC
python scripts/m9-c-adopt/compute_big5_icc.py \
  --persona kant \
  --shards-glob "data/eval/m9-c-adopt-tier-b-pilot/kant_r4_run*_stim.duckdb" \
  --responder sglang --sglang-host http://localhost:30000 \
  --sglang-adapter kant_r4_real --window-size 100 \
  --output .steering/20260513-m9-c-adopt/tier-b-icc-kant-r4.json
# 同様に rank=8, rank=16
```

### 2. Burrows Δ 言語処理判断 + 算出 (~30min 設計 + ~2h compute)

#### 2a: 3 案から選定

DA-11 で defer した 3 案:
- **Option A**: 言語自動判定 (e.g. `langdetect`) で per-utterance routing、
  de は existing kant_de reference / en は skip / ja は skip ("limitation"
  扱い)
- **Option B**: Cambridge Edition Kant English vendoring (M9-eval-system
  `m9-eval-corpus-kant-en` 別 PR を blocker 化、Phase B 第 4 セッション
  着手前に解消必要)
- **Option C**: kant baseline で Burrows N/A 扱い (rikyu と同 pattern、
  DA-8 2-of-2 fallback を kant にも適用)

推奨: **Option A** (Phase B 第 4 セッション内で完遂可能、Option B は別 PR
依存で遅延、Option C は DA-8 quorum 規則の意味を kant でも weakening する)

#### 2b: Option A 採択時の実装

- `langdetect` を `pyproject.toml [eval]` extras に追加
- `scripts/m9-c-adopt/compute_burrows_delta.py` 新規:
  - per-utterance language detect → de のみ filter
  - `compute_burrows_delta(utt, kant_de_reference, language="de")` per
    utterance
  - per-window mean → bootstrap CI (cluster_only=True)
- DA-1 軸 3 threshold: Burrows Δ reduction ≥ 10% point + CI lower > 0
- documented limitation: en/ja utterances dropped (~60% of corpus)、effective
  sample size CI 開広報告

### 3. Vendi semantic kernel 再算出 (~30min Mac post-hoc)

Mac master 側で [eval] extras + sentence-transformers MPNet cache 整備、
本 session で実装済の `compute_baseline_vendi.py` を再利用:

```bash
# baseline (no-LoRA) semantic
python scripts/m9-c-adopt/compute_baseline_vendi.py \
  --persona kant --condition stimulus \
  --shards-glob "data/eval/golden/kant_stimulus_run*.duckdb" \
  --kernel semantic --window-size 100 \
  --output .steering/20260513-m9-c-adopt/tier-b-baseline-kant-vendi-semantic.json

# per-rank LoRA-on semantic
for r in 4 8 16; do
  python scripts/m9-c-adopt/compute_baseline_vendi.py \
    --persona kant \
    --shards-glob "data/eval/m9-c-adopt-tier-b-pilot/kant_r${r}_run*_stim.duckdb" \
    --kernel semantic --window-size 100 \
    --output .steering/20260513-m9-c-adopt/tier-b-pilot-kant-r${r}-vendi-semantic.json
done
```

### 4. DA-1 4 軸 intersection で final 採用 rank 確定

各 rank の point + CI lower + direction 比較 matrix:

| rank | Vendi semantic | ICC(C,k) | Burrows Δ red | throughput tok/s | DA-1 PASS |
|------|---|---|---|---|---|
| no-LoRA baseline | (point, CI) | (point, CI) | N/A | (PR #163 K-β 値) | -- |
| 4 | (point, CI, direction) | (point, CI) | (point, CI, direction) | (測定値) | ✓/✗ |
| 8 | ... | ... | ... | ... | ✓/✗ |
| 16 | ... | ... | ... | ... | ✓/✗ |

判定:
- **3 軸全達成の smallest rank** が確定 → DA-1 4 軸 PASS、ADOPT
- **1+ 軸が CI lower 未達 + point 達成**: DA-9 marginal pass retrain path
  (別 PR `feature/m9-c-adopt-retrain-v2` で min_examples 1000→3000)
- **3 軸とも未達**: REJECT、CS-5 / DB3 re-arm 検討

### 5. Step 6 (conditional): rank=32 tail-sweep

fire 条件 (DA-1 HIGH-1):
- rank=16 throughput PASS かつ Vendi/ICC/Burrows いずれか未達
- rank=8 → 16 で effect size delta > 0.5

fire 時:
- CS-1 launch arg amendment v2: `--max-lora-rank 32`
- rank=32 training (G-GEAR overnight ~3h)
- archive + manifest (`--allow-tail-sweep` flag)
- pilot Tier B 600 turn 採取 + metric 算出
- DA-1 再評価で rank=16 vs rank=32 比較

### 6. Step 7: 採用 rank 確定 + 報告 + commit/PR

- 採用 rank 確定 (e.g. `kant_adopted_rank = 8` or 16)
- `decisions.md` に **DA-12 (採用 rank 確定 ADR)** 起草:
  - rank × metric 実測 matrix
  - 採用 rank の根拠 (4 軸 intersection 結果)
  - tail-sweep 実施有無 + 結果
- `data/lora/m9-c-adopt/kant_r{adopted}_real/` を production 採用配置
  (archive 内 same rank を copy、`is_mock=false`、`training_git_sha=<HEAD>`)
- `tasklist.md` Phase B 完了 mark
- `blockers.md` 更新 (H-1 解消、S-3 amendment、rank=32 実施有無)
- `phase-b-progress.md` Final state へ書き換え
- `phase-b-report.md` 起票 (新規):
  - rank × metric 実測 table
  - 採用 rank + 根拠
  - VRAM 実測 peak (training: rank=4 10.51GB / rank=16 10.14GB metadata、
    nvidia-smi sustained ~14016MiB / serving: fp8 ~10.86GB peak)
  - blockers.md status 変動
  - Phase C 着手前 dependency
- commit: `feat(adopt): m9-c-adopt — Phase B kant rank sweep 完遂 + 採用 rank={X}`
- `gh pr create`:
  - PR description に rank × metric matrix + DA-1 採用根拠 + tail-sweep
    実施有無 + sha256 + VRAM peak + 「next-session-prompt-phase-c.md は
    別 PR」明記
- Mac master review 待ち
- Phase C `next-session-prompt-phase-c.md` 起草 (本 PR scope 外、別 PR で)

## NOT in scope (本セッション)

- nietzsche / rikyu の training (Phase C scope、別 PR)
- `MultiBackendChatClient` 実装 / live path 統合 (Phase D scope)
- multi_lora_3 real-after stress bench (Phase D/E scope)
- FSM smoke 24 cell (Phase E scope)
- Tier B **full** 7500 turn (Phase E scope、本セッションは pilot 1800 turn
  既に完了)
- production loader / verdict report (Phase F scope)

## 注意 (incident 教訓 + 既知の落とし穴、第 4 セッション amendment)

- **Big5 ICC compute は ~25-35h レンジ**: Mac master + remote G-GEAR
  split 推奨 (Mac で no-LoRA baseline、G-GEAR で per-rank LoRA-on)
- **IPIP-50 administering の context 設計**: Salecha et al. 2024
  anti-demand-characteristics に従い、過去 window context は責任を持って
  入れない (single-shot administering)。`ipip_neo.administer_ipip_neo` は
  既にこの想定で書かれている
- **SGLang LoRA-on responder 実装**: pilot driver と同 SGLang HTTP API、
  ただし `enable_thinking=False` を chat_template_kwargs に必ず指定
- **Burrows langdetect 精度**: 短い utterance (~50 char) で誤判定し得る、
  threshold (e.g. confidence > 0.8) を設けて低確度は drop 推奨
- **MPNet model download**: Mac master 側で初回 ~440MB DL 必要、HF token
  または直接 sentence-transformers cache 持ち込み
- **3 rank pilot shards は本 session で揃い済**: `data/eval/m9-c-adopt-tier-b-pilot/`
  6 shard、再採取不要
- main 直 push 禁止 / 50% 超セッション継続禁止 (`/smart-compact`)
- GPL を `src/erre_sandbox/` に import 禁止
- 本セッションは **kant のみ scope**、3 persona expansion は Phase C 別 PR

## 完了条件 (本セッション = AC-1 PASS)

### Big5 ICC + Burrows + semantic Vendi
- [ ] Big5 ICC consumer 実装 + commit
- [ ] no-LoRA baseline ICC(C,k) 算出 (CI lower ≥ 0.6 確認)
- [ ] per-rank LoRA-on ICC × 3 rank 算出
- [ ] Burrows 3 案から選定 + 算出 (Option A 推奨)
- [ ] semantic Vendi 再算出 (no-LoRA + per-rank、Mac post-hoc)

### DA-1 final + tracking
- [ ] DA-1 4 軸 intersection で kant の final rank 確定
- [ ] `data/lora/m9-c-adopt/kant_r{X}_real/` を production 採用配置
- [ ] `decisions.md` DA-12 (採用 rank 確定 ADR) 起票
- [ ] `tasklist.md` Phase B チェック完了 mark
- [ ] `blockers.md` H-1 解消、S-3 amendment 完了
- [ ] `phase-b-progress.md` Final state
- [ ] `phase-b-report.md` 起票

### PR
- [ ] branch `feature/m9-c-adopt-phase-b-rank-sweep` で PR 起票
- [ ] PR description に rank × metric matrix + DA-1 採用根拠 + tail-sweep
  実施有無 + sha256 + VRAM peak
- [ ] Mac master review 待ち
- [ ] Phase C `next-session-prompt-phase-c.md` 起草 (別 PR で起票)

## 参照

- 第 3 セッション handoff (前 prompt): `.steering/20260513-m9-c-adopt/next-session-prompt-phase-b-3.md`
- in-flight state: `.steering/20260513-m9-c-adopt/phase-b-progress.md`
- ADR: `.steering/20260513-m9-c-adopt/decisions.md` (DA-1 / DA-8 / DA-9 /
  DA-11)
- blockers: `.steering/20260513-m9-c-adopt/blockers.md`
- tasklist: `.steering/20260513-m9-c-adopt/tasklist.md`
- DB8 runbook: `docs/runbooks/m9-c-adapter-swap-runbook.md`
- Tier B framework: `src/erre_sandbox/evidence/tier_b/` (vendi/big5_icc/ipip_neo)
- Burrows: `src/erre_sandbox/evidence/tier_a/burrows.py` + `reference_corpus/`
- bootstrap CI: `src/erre_sandbox/evidence/bootstrap_ci.py`
- pilot driver: `scripts/m9-c-adopt/tier_b_pilot.py` (本 session で新規)
- baseline Vendi consumer: `scripts/m9-c-adopt/compute_baseline_vendi.py` (本 session で新規)
- per-rank bench: `scripts/m9-c-adopt/bench_per_rank.sh` (本 session で新規)
- 既存 K-β bench: `data/eval/spike/m9-c-spike-bench/single_lora.jsonl`
  (rank=8 baseline、no_lora baseline 24.25 tok/s threshold)
- Codex review HIGH-1 引用 (rank sweep literature):
  - LoRA Land (https://arxiv.org/abs/2405.00732)
  - PLORA (https://openreview.net/pdf?id=azsnOWy9MZ)
  - P-React (https://aclanthology.org/2025.findings-acl.328.pdf)

まず **`decisions.md` DA-11** + **`tier-b-baseline-kant.md`** を完全に
内面化し、Phase B 第 3 セッション scope narrowing の理由 + 第 4 セッション
で完遂する scope を理解した上で、Step 1a (Big5 ICC consumer 実装) から
着手する。Big5 ICC compute (~9h Ollama + ~2h SGLang) は Mac master + G-GEAR
split で並列実行する。コンテキスト使用率 50% 超で `/smart-compact` で区切る。

なお、本セッションが完了すれば PR が起票され、Phase C (3 persona expansion)
着手準備に入る。
```

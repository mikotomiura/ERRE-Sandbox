# G-GEAR セッション用プロンプト v2 — m9-eval-system P3 Golden baseline 採取

> このファイルは Mac セッション (2026-05-07、PR #140 merge 直後) で起草。
> G-GEAR (Windows / RTX 5060 Ti 16GB / Ollama 0.22.0) で `/clear` 後に
> 全文をコピペして送る前提。Mac → G-GEAR の sync は user が事前に
> `git fetch && git checkout main && git pull --ff-only` で完了している想定
> (main = `0304ea3` 以降、PR #140 merged)。
>
> v1 (`g-gear-p3-launch-prompt.md`) は **Phase 2 run0 wall-timeout incident
> (2026-05-06、focal=381/390/399 prefix censored)** を起こした legacy
> reference。本 v2 は ME-9 ADR (`decisions.md`) と PR #140 の新 contract
> (sidecar v1 + return code 0/2/3 + `eval_audit` CLI) に整合し、**run1
> calibration を先行**して empirical wall budget を確定してから run2-4 を
> 採取する。

## 0. 前提と目標

### 0.1 main 状態

```text
main = 0304ea3 以降 (PR #140 merged)
- src/erre_sandbox/cli/eval_run_golden.py: soft_timeout 分離 + return 0/2/3
- src/erre_sandbox/cli/eval_audit.py: audit gate CLI
- src/erre_sandbox/evidence/capture_sidecar.py: SidecarV1 (extra=allow)
- _RUNTIME_DRAIN_GRACE_S = 60.0 (PR #140 で 30→60 raise 済)
```

### 0.2 採取対象

- 3 persona (kant / nietzsche / rikyu) × 2 condition (stimulus / natural) ×
  5 run (run_idx 0..4) = **30 cell** (production)
- + kant only × 5 wall calibration cell (run_idx 100..104) = **5 cell** (run1
  calibration)
- 合計 **35 cell**

### 0.3 焦点 turn target

- 500 / cell (P3a pilot は 30、P3 production は 500)
- focal_target=500 が PR #140 audit gate の必須条件 (return 0 = complete +
  focal_observed >= 500)

### 0.4 wall 予算 (empirical 起点)

- pilot single-cell natural: **1.87 focal/min** (`data/eval/pilot/_summary.json`)
- run0 3-parallel contended: **1.06 focal/min** (`blockers.md` active incident)
- contention factor ≈ **1.76×** (固定仮定、run1 では再推定しない)
- run2-4 default wall budget = **600 min**、§Phase A 結果次第で +120 min 拡張

### 0.5 run1 calibration の制約 (ME-9 ADR より)

- **kant のみ 1 persona** で実行 (3-parallel しない)
- ADR 文言「single 600 min cell + intermediate samples」に対し、本 v2 は
  **CLI snapshot 未実装のため endpoint sweep (5 wall sequential) で代替**
  (`decisions.md` ME-9 / 本タスク M1 採用)

## まず Read (この順、G-GEAR 着手時)

1. `.steering/20260430-m9-eval-system/decisions.md`
   - **ME-2** (rsync protocol、CHECKPOINT + temp+rename、md5 照合)
   - **ME-9** (CLI fix + run1 calibration、本 v2 の権威 source)
2. `.steering/20260506-m9-eval-cli-partial-fix/decisions.md`
   - 案 A' 採用根拠 (`_SinkState.set_fatal()` / `set_soft_timeout()` 関数の意図)
3. `.steering/20260507-m9-eval-phase2-run1-calibration-prompt/decisions.md`
   - 本 v2 の Codex review HIGH 3 / MEDIUM 3 反映の経緯
4. `src/erre_sandbox/cli/eval_run_golden.py` (新 CLI 入口、特に
   `_DEFAULT_WALL_TIMEOUT_MIN=120.0` / `_RUNTIME_DRAIN_GRACE_S=60.0` の
   constant 値と `--allow-partial-rescue` / `--force-rescue` flag)
5. `src/erre_sandbox/cli/eval_audit.py` (audit gate、return 0/4/5/6)

## Pre-condition

```bash
cd ~/ERRE-Sand\ Box
git fetch origin
git checkout main && git pull --ff-only origin main
# main = 0304ea3 以降を確認:
git log -1 --pretty='%h %s'
# → 0304ea3 以降の merge

# テスト pass 確認 (P3 採取に着手する前の sanity)
uv run pytest tests/ -q -m eval | tail -5
# → 31 passed (PR #140 で +2 from MEDIUM-CR1/CR2)

# Ollama daemon 稼働 + qwen3:8b Q4_K_M + nomic-embed-text 確認
ollama list | grep -E "qwen3:8b|nomic-embed-text"
# → 両方 present、qwen3:8b は Q4_K_M (~5.2GB) の想定

# 出力ディレクトリ作成 (calibration を production と隔離、Codex H3 反映)
mkdir -p data/eval/calibration/run1/
mkdir -p data/eval/partial/
mkdir -p data/eval/golden/
```

## Phase 0 — pre-flight smoke test (~30 min)

PR #140 で実装した sidecar + return code 3 path が動くか sanity-check。
**stimulus condition** で実行 (natural の wall watchdog は §Phase A で検証
される)。

注意: `--wall-timeout-min` flag は **natural condition 専用** で stimulus には
効かない (`eval_run_golden.py:958` で `partial_capture=False` ハードコード)。
stimulus に外部 timeout を効かせたい場合は shell `timeout 60m uv run ...` を
併用する。

```bash
# kant_stimulus 50 turn dry run
timeout 60m uv run python -m erre_sandbox.cli.eval_run_golden \
  --persona kant --run-idx 0 --condition stimulus \
  --turn-count 50 --cycle-count 1 \
  --output /tmp/p3_smoke_kant_stimulus.duckdb --overwrite
# 期待: focal=51 (= ceil(50×ceil/2) 程度)、return code 0、
#       /tmp/p3_smoke_kant_stimulus.duckdb.capture.json が status=complete

# sidecar 検証
cat /tmp/p3_smoke_kant_stimulus.duckdb.capture.json | jq '.status, .focal_observed, .stop_reason'
# → "complete", 51 (前後), "complete"

# audit 単発検証
uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb /tmp/p3_smoke_kant_stimulus.duckdb --focal-target 50
# → return 0 = audit PASS

# 失敗時: PR #140 が壊れている疑いあり、Mac へ報告して停止
```

## Phase A — run1 calibration (kant only × 5 wall sequential、~30h)

ME-9 ADR の run1 calibration を **kant 1 persona × 5 wall endpoint** で実行
(M1 採用、CLI snapshot 未実装のため endpoint sweep で代替)。各 cell を
**wall-limited stop** させるため `--turn-count 2000` で early stop を抑制 (Codex
H2 反映、`--turn-count 1000` だと 600 min cell が 535 min で stop してしまう)。

run_idx は production 域 (0..4) と分離するため **100..104 を専用域**として使う。
`raw_dialog.dialog.run_id` は `kant_natural_run100` 形式になる。

### A.1 5 cell sequential 実行

```bash
# 各 cell を sequential 実行 (kant only、3-parallel しない)
for IDX_WALL in "100:120" "101:240" "102:360" "103:480" "104:600"; do
  RUN=$(echo $IDX_WALL | cut -d: -f1)
  WALL=$(echo $IDX_WALL | cut -d: -f2)
  echo "=== run_idx=$RUN wall=$WALL min ==="
  uv run python -m erre_sandbox.cli.eval_run_golden \
    --persona kant --run-idx "$RUN" --condition natural \
    --turn-count 2000 --wall-timeout-min "$WALL" \
    --memory-db "/tmp/p3_calibration_kant_run${RUN}.sqlite" \
    --output "data/eval/calibration/run1/kant_natural_run${RUN}.duckdb"
  # return 3 (partial、wall timeout) を期待
done
# 累計 wall = 120+240+360+480+600 = 1800 min ≈ 30h、overnight×2 で完結
```

### A.2 各 cell の sidecar 検証 (cell 完了後すぐ)

```bash
for RUN in 100 101 102 103 104; do
  P="data/eval/calibration/run1/kant_natural_run${RUN}.duckdb"
  echo "=== $P ==="
  cat "${P}.capture.json" | jq '.status, .focal_observed, .stop_reason, .wall_timeout_min'
  # 期待: "partial", <focal>, "wall_timeout", <wall>
done
```

### A.3 calibration audit (--allow-partial)

```bash
# calibration cell は意図的 partial、--allow-partial で全 PASS を期待
uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/calibration/run1/*.duckdb' \
  --focal-target 1 \
  --allow-partial \
  --report-json data/eval/calibration/run1/_audit.json
# focal_target=1 は audit が focal>=1 で PASS、calibration では実質 sanity
# 全 5 cell return 0 を期待 (run_id 整合性 + sidecar consistency)
```

### A.4 期待値 table (1.87 focal/min single-rate 仮定)

| run_idx | wall (min) | expected focal | sidecar status |
|---|---|---|---|
| 100 | 120 | 224 ± 15% (190-258) | partial |
| 101 | 240 | 449 ± 15% (382-516) | partial |
| 102 | 360 | 673 ± 15% (572-774) | partial |
| 103 | 480 | 898 ± 15% (763-1033) | partial |
| 104 | 600 | 1122 ± 15% (954-1290) | partial (turn-count=2000 で early stop しない) |

実観測値が ±15% を大きく外れる場合は **§Phase A 結果解析** (下記) で
計算する `focal_per_min_observed` を使って run2-4 wall budget を再決定する。

## Phase A 結果解析 (Mac 側、~30 min)

5 cell の sidecar から `focal_per_min` の single-rate を算出し、F-1+F-4 数式で
run2-4 (3-parallel) の wall budget を確定する。

### B.1 数式

```text
focal_per_min_single   = mean(focal_observed[i] / wall_timeout_min[i])  for i in 100..104
contention_factor      = 1.76 (FIXED ASSUMPTION、pilot single 1.87 / run0 parallel 1.06)
                          # 本タスクで再推定しない (Codex M3 採用)
focal_per_min_parallel = focal_per_min_single / contention_factor
safety_factor          = 0.85
wall_budget_min        = ceil(500 / focal_per_min_parallel / safety_factor)
                          # 切上げて 60 の倍数に丸める (運用簡略化)
```

### B.2 95% CI (single-rate のみ、Codex M3)

```bash
# Mac で sidecar を read、focal_per_min array を出す
python3 -c "
import json, statistics, glob
paths = sorted(glob.glob('data/eval/calibration/run1/kant_natural_run10*.duckdb.capture.json'))
rates = []
for p in paths:
    s = json.load(open(p))
    rate = s['focal_observed'] / s['wall_timeout_min']
    rates.append(rate)
    print(f'{p}: focal={s[\"focal_observed\"]} wall={s[\"wall_timeout_min\"]} rate={rate:.3f}/min')
print('---')
print(f'n={len(rates)} mean={statistics.mean(rates):.3f}')
print(f'stdev={statistics.stdev(rates):.3f}')
print(f'95% CI ≈ mean ± 2.776*stdev/sqrt(n) (t-dist df=4)')
"
```

### B.3 run2-4 wall budget の決定

| observed focal_per_min_single | parallel (×1.76 補正) | wall_budget_min (target=500、safety=0.85) |
|---|---|---|
| 2.10 | 1.193 | 493 → **480 min** で運用 |
| 1.87 | 1.063 | 553 → **600 min** で運用 (default) |
| 1.50 | 0.852 | 691 → **720 min** で運用 |
| 1.20 | 0.682 | 863 → **900 min** で運用 (要検討) |
| 0.92 | 0.523 | 1126 → **ME-9 re-open trigger** (§ブロッカー予測 C 案へ) |

## Phase B — stimulus 全 15 cell (~3-5h)

stimulus は battery 駆動 (cognition memory 不要)、parallel に弱い contention。
3 persona × 5 run = 15 cell、sequential 実行で十分速い。

**重要 (Codex H1 反映)**: `--cycle-count 6` を指定すること。`cycle-count=3` だと
battery 駆動で focal=264 となり、PR #140 audit gate で **fatal_incomplete_before_target**
として fatal 化する。`cycle-count=6` で focal≈504 を確保する。

```bash
for RUN in 0 1 2 3 4; do
  for P in kant nietzsche rikyu; do
    timeout 90m uv run python -m erre_sandbox.cli.eval_run_golden \
      --persona "$P" --run-idx "$RUN" --condition stimulus \
      --turn-count 500 --cycle-count 6 \
      --output "data/eval/golden/${P}_stimulus_run${RUN}.duckdb"
    # 期待: return 0 (complete)、focal≈504、wall ~75 min
  done
done
```

audit (production の stimulus サブセットのみ):

```bash
uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/golden/*_stimulus_run*.duckdb' \
  --focal-target 500 \
  --report-json data/eval/golden/_audit_stimulus.json
# 全 15 cell return 0 を期待。fail なら当該 cell 再採取。
```

## Phase C — natural 全 15 cell + run0 再採取 (~24-48h、wall budget 次第)

§Phase A で確定した wall budget を使う。default は 600 min。3-parallel で
contention factor ≈ 1.76 を仮定するが、§Phase A の observed が大きく異なる場合は
再決定する。

### C.1 各 run の 3-parallel 実行

```bash
WALL=600  # §Phase A から確定。observed が低ければ 720/900 等に拡張。
for RUN in 0 1 2 3 4; do
  echo "=== natural 3-parallel run_idx=$RUN wall=$WALL min ==="
  for P in kant nietzsche rikyu; do
    uv run python -m erre_sandbox.cli.eval_run_golden \
      --persona "$P" --run-idx "$RUN" --condition natural \
      --turn-count 500 --wall-timeout-min "$WALL" \
      --memory-db "/tmp/p3_natural_${P}_run${RUN}.sqlite" \
      --output "data/eval/golden/${P}_natural_run${RUN}.duckdb" &
  done
  wait
  # 全 3 cell return 0 を期待。run0 の partial 再採取は別途。
done
```

### C.2 kant drain timeout fallback

pilot Phase B で kant が parallel で drain timeout を踏んだ実績あり (PR #140 で
`_RUNTIME_DRAIN_GRACE_S=60.0` に raise したが、念のため fallback 維持)。
3-parallel で kant が return 2 (fatal) を返したら sequential 再実行:

```bash
RUN=0  # 該当 run_idx
uv run python -m erre_sandbox.cli.eval_run_golden \
  --persona kant --run-idx "$RUN" --condition natural \
  --turn-count 500 --wall-timeout-min "$WALL" \
  --memory-db "/tmp/p3_natural_kant_run${RUN}.sqlite" \
  --output "data/eval/golden/kant_natural_run${RUN}.duckdb" --overwrite
```

### C.3 run0 partial の再採取 (§Phase 2 run0 incident 由来)

旧 v1 で実行した run0 (focal=381/390/399 partial) を再採取。`--allow-partial-rescue`
flag が必要 (sidecar 同居の `.tmp` を unlink するため、PR #140 H4 反映)。

```bash
# 旧 run0 partial が data/eval/golden/ に残っている場合は data/eval/partial/ へ移動
mkdir -p data/eval/partial/
for P in kant nietzsche rikyu; do
  if [ -f "data/eval/golden/${P}_natural_run0.duckdb.tmp" ]; then
    mv "data/eval/golden/${P}_natural_run0.duckdb.tmp" "data/eval/partial/"
    mv "data/eval/golden/${P}_natural_run0.duckdb.capture.json" "data/eval/partial/" 2>/dev/null || true
  fi
done

# 再採取 (3-parallel)
WALL=600
for P in kant nietzsche rikyu; do
  uv run python -m erre_sandbox.cli.eval_run_golden \
    --persona "$P" --run-idx 0 --condition natural \
    --turn-count 500 --wall-timeout-min "$WALL" \
    --memory-db "/tmp/p3_natural_${P}_run0.sqlite" \
    --output "data/eval/golden/${P}_natural_run0.duckdb" \
    --overwrite &
done
wait
```

## Phase D — eval_audit batch + rsync (~30 min)

### D.1 production audit (calibration とは exact glob 分離、Codex H3)

```bash
# production = run_idx 0..4 のみ exact glob、calibration を混ぜない
uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/golden/*_run[0-4].duckdb' \
  --focal-target 500 \
  --report-json data/eval/golden/_audit.json
# overall_exit_code=0 を期待。fail cell は再採取。

# calibration 別 audit (--allow-partial で diagnostic PASS)
uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/calibration/run1/*.duckdb' \
  --focal-target 1 \
  --allow-partial \
  --report-json data/eval/calibration/run1/_audit.json
```

### D.2 CHECKPOINT + sidecar md5 receipt (Codex H3 反映)

```bash
mkdir -p /tmp/p3_rsync/
cd "$HOME/ERRE-Sand Box"

# production (30 cell) と calibration (5 cell) を別 dir で snapshot
# DuckDB と .duckdb.capture.json の両方を copy (sidecar 必須)
for f in data/eval/golden/*_run[0-4].duckdb; do
  bn=$(basename "$f")
  uv run python -c "
import duckdb
con = duckdb.connect('$f')
con.execute('CHECKPOINT')
con.close()
"
  cp "$f" "/tmp/p3_rsync/${bn}.snapshot.duckdb"
  cp "${f}.capture.json" "/tmp/p3_rsync/${bn}.snapshot.duckdb.capture.json"
done

for f in data/eval/calibration/run1/*.duckdb; do
  bn=$(basename "$f")
  uv run python -c "
import duckdb
con = duckdb.connect('$f')
con.execute('CHECKPOINT')
con.close()
"
  cp "$f" "/tmp/p3_rsync/calibration_${bn}.snapshot.duckdb"
  cp "${f}.capture.json" "/tmp/p3_rsync/calibration_${bn}.snapshot.duckdb.capture.json"
done

# md5 receipt: DuckDB と sidecar の両方 (Codex H3)
cd /tmp/p3_rsync/
md5 -r *.snapshot.duckdb *.duckdb.capture.json > _checksums.txt

# data/eval/golden/_rsync_receipt.txt を起草 (P3a と同形式に sidecar 追記)
# - host_name / os / gpu / ollama_version
# - production 30 cell + calibration 5 cell の focal/total/dialog 行
# - md5 hash (DuckDB 35 行 + sidecar 35 行 = 70 行)
# - §Phase A 結果解析サマリ (focal_per_min_single mean/CI/run2-4 wall_budget)
# - Mac side rename + audit + p3_decide 手順 (next Mac セッション)
```

### D.3 HTTP server で Mac へ pull (P3a-finalize 2026-05-05 で validated)

```bash
# G-GEAR (admin PowerShell):
#   New-NetFirewallRule -DisplayName "claude-p3-rsync" -Direction Inbound \
#     -Protocol TCP -LocalPort 8765 -Action Allow \
#     -Program "C:\Users\johnd\AppData\Local\Programs\Python\Python311\python.exe"

# G-GEAR (作業 shell):
cd /tmp/p3_rsync/
python -m http.server 8765
# → Mac で curl -fOSs http://<G-GEAR-IP>:8765/<file>.snapshot.duckdb および .capture.json

# Mac 側受信後の md5 検証:
#   cd ~/ERRE-Sand\ Box/data/eval/golden/
#   md5 -r *.snapshot.duckdb *.duckdb.capture.json | diff - /tmp/p3_rsync/_checksums.txt
```

## Phase E — PR 作成 (~10 min)

```bash
git checkout -b feature/m9-eval-p3-golden-v2
git add data/eval/golden/ data/eval/calibration/run1/ data/eval/partial/
# .gitignore に DuckDB が追加されている場合は git add -f
git commit -m "$(cat <<'EOF'
feat(eval): m9 — P3 golden baseline 採取 + run1 calibration 完了

- run1 calibration (kant only × 5 wall sequential、run_idx=100..104) で
  focal_per_min_single = X.XX (95% CI [X.XX, X.XX]) を実測
- contention factor 1.76 (固定仮定) で run2-4 wall budget = XXX min を確定
- production 30 cell (3 persona × 5 run × 2 condition) を採取
- run0 partial (incident 由来) を data/eval/partial/ へ隔離 + 再採取
- eval_audit batch で全 cell return 0 確認、sidecar md5 receipt 同梱

Refs: .steering/20260430-m9-eval-system/decisions.md ME-9
Refs: .steering/20260507-m9-eval-phase2-run1-calibration-prompt/decisions.md
Refs: PR #140 (CLI fix + sidecar + audit gate)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin feature/m9-eval-p3-golden-v2
gh pr create --title "feat(eval): m9 — P3 golden baseline + run1 calibration" \
  --body "## Summary
- run1 calibration kant only × 5 wall sequential で focal/min 確定
- production 30 cell + calibration 5 cell rsync receipt 同梱
- run0 partial 隔離 + 再採取済

## Test plan
- [x] PR #140 の eval_audit batch return 0
- [x] sidecar md5 receipt 検証
- [ ] Mac 側で p3_decide.py 再実行 (次セッション)

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

## ブロッカー予測 + fallback

### B-1. run1 calibration で observed focal/min が ME-9 re-open trigger に該当 (≤55/h ≈ 0.92/min または ≥80/h ≈ 1.33/min)

**default 対応**: **C 案 (Codex review 起動 + child ADR 起票)** で停止。
720 min 強行 (旧案 A) は ME-9 re-open trigger を空文化するため禁止 (Codex
2026-05-07 review Q5 採用)。

```bash
# 該当時の手順:
# 1. G-GEAR で停止、Mac へ報告
# 2. Mac で `/start-task m9-eval-cooldown-readjust-adr` を起票
# 3. Codex `gpt-5.5 xhigh` review で再評価
# 4. ADR 確定後、本 v2 prompt の §Phase A から再実行
```

### B-2. kant drain timeout (3-parallel で再現)

PR #140 で `_RUNTIME_DRAIN_GRACE_S = 60.0` に raise 済だが、それでも timeout
する場合 §Phase C.2 の sequential fallback を実行。

### B-3. stimulus cell の audit fail (focal<504)

cycle_count=6 で focal≈504 を期待するが、battery slice の round-off で 500 を
わずかに下回る可能性。その場合は cycle_count=7 で再採取:

```bash
timeout 100m uv run python -m erre_sandbox.cli.eval_run_golden \
  --persona "$P" --run-idx "$RUN" --condition stimulus \
  --turn-count 500 --cycle-count 7 \
  --output "data/eval/golden/${P}_stimulus_run${RUN}.duckdb" --overwrite
```

### B-4. sidecar 欠損 / 破損 (rsync 後)

audit return 4 (missing sidecar) → G-GEAR の `data/eval/golden/*.capture.json`
を Mac へ追加 rsync。
audit return 5 (mismatch / 破損) → Mac で sidecar を read して `--force-rescue`
で `.tmp` 削除、G-GEAR で再採取。

### B-5. calibration cell 自体が fatal で停止 (DuckDB INSERT 失敗等)

return 2 (fatal) で `.tmp` が残る、`--allow-partial-rescue` ではなく
`--force-rescue` または手動 cleanup:

```bash
ls data/eval/calibration/run1/*.tmp
# 手動で .tmp と .capture.json を消して再採取 (ADR 違反ではない、calibration は
# diagnostic 専用)
```

### B-6. 累計 wall が予算超過 (run1 calibration 30h + production 24-48h)

§Phase A を **kant の 480 min cell (run_idx=103) までで cut off**、500 focal
endpoint は run0 incident 観測値 (380-400) で代替する option もある (要 Mac
判断)。

## 関連参照

- 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
- 本 v2 の design + Codex review 反映: `.steering/20260507-m9-eval-phase2-run1-calibration-prompt/decisions.md`
- 旧 v1 prompt (legacy reference): `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md`
- 前 PR (CLI fix): PR #140、main = `0304ea3`
- run0 incident: `.steering/20260430-m9-eval-system/blockers.md` "active incident"
- pilot empirical: `data/eval/pilot/_summary.json` / `_p3a_decide.json`
- Codex review (本 v2 起票前): `.steering/20260507-m9-eval-phase2-run1-calibration-prompt/codex-review-run1-calibration.md`

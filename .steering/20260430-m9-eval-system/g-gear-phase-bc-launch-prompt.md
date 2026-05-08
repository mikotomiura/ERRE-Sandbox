# G-GEAR セッション用プロンプト — m9-eval Phase B + C 採取 (Phase A 完了後)

> 本書は G-GEAR セッションで `/clear` 後に投げる self-contained prompt。
> Phase A run1 calibration が完了済 (5/5 cells、PR #151 で main へ merge) で、
> 確定値 (`wall_budget=600 min`、`contention_factor=1.502`、saturation curve)
> を base に Phase B (stimulus 15 cell) と Phase C (natural 15 cell +
> run0 partial 再採取) を実行する。
>
> **作成**: 2026-05-08 (Mac セッション、PR #151 起票時)
> **対象**: G-GEAR セッション (RTX 5060 Ti 16GB、qwen3:8b Q4_K_M)
> **想定所要**: Phase B ~3-5h + Phase C ~24-48h overnight×2
> **前提**: PR #151 merged で main = `<未確定、merge 後 commit hash 確認>`

## まず Read (この順、G-GEAR 着手時)

1. `.steering/20260430-m9-eval-system/decisions.md` ME-9 Amendment 2026-05-07
   + Amendment 2026-05-08 (trigger zone と確定値)
2. `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md` §Phase B /
   §Phase C / §Phase D / §Phase E (本書は v2 の Phase A 部分を skip した
   subset、v2 の Phase B+ をそのまま base とする)
3. `.steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md` (lock-step
   update 2026-05-08)
4. 本書 (G-GEAR で実行する手順)

## Phase A 完了済の確定値 (本セッション scope 外、参考値)

| 項目 | 値 |
|---|---|
| focal_per_min_single mean | 1.5870 (95% CI [1.5527, 1.6213]) |
| saturation curve | 1.625 → 1.596 → 1.592 → 1.571 → 1.552 (単調減少) |
| wall-aligned contention factor | 1.502 (v2 §B.3 default 1.76 より −14.7%) |
| **run2-4 wall_budget** | **600 min** (確定、§B.3 default 採用) |
| 3-parallel rate estimate | 1.057 /min (= 1.587 / 1.502) |

## Phase B — stimulus 全 15 cell (~3-5h)

v2 §Phase B 通り。`--cycle-count 6` を必ず指定 (PR #140 反映、cycle-count=3
だと focal=264 で fatal_incomplete_before_target に hit する)。

```bash
cd "$ERRE_SAND_BOX_PATH"  # G-GEAR 側で WSL/PowerShell 用にパス調整
mkdir -p data/eval/golden/  # production output dir、calibration とは glob 分離

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

audit (stimulus subset only):

```bash
uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/golden/*_stimulus_run*.duckdb' \
  --focal-target 500 \
  --report-json data/eval/golden/_audit_stimulus.json
# 全 15 cell return 0 を期待。fail なら当該 cell 再採取。
```

### B.fail. fatal_incomplete_before_target が出た場合

PR #140 の audit gate が `cycle-count=3` で fire するのを `cycle-count=6` で
回避する。それでも 1 cell でも fail したら:

1. 当該 cell の sidecar を inspect (`*.duckdb.capture.json` の `focal_observed`)
2. `--cycle-count 7` または `--turn-count 600` に上げて当該 cell のみ再採取
3. 解決しなければ Mac へ報告 (audit gate の再判定が必要かも)

## Phase C — natural 全 15 cell × wall=600 min × 3-parallel (~24-48h)

§B.3 wall_budget 確定 = **600 min** (Phase A 完了で確定)。3-parallel
contention factor 1.502 は run0 360 min との wall-aligned 比較で確定。

### C.1 各 run の 3-parallel 実行

```bash
WALL=600  # Phase A 確定値、固定
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
  # 全 3 cell return 0 を期待。run0 の partial 再採取は別途 §C.3。
done
```

run 1 周 = 600 min ≈ 10h、5 run × 10h = 50h … 想定 24-48h は wall_budget が
効率次第で短縮されるケース。**overnight×2 で完結予定**。

### C.2 kant drain timeout fallback

pilot Phase B で kant が parallel で drain timeout を踏んだ実績あり (PR #140
で `_RUNTIME_DRAIN_GRACE_S=60.0` に raise 済)。3-parallel で kant が return 2
(fatal) を返したら sequential 再実行:

```bash
RUN=0  # 該当 run_idx
uv run python -m erre_sandbox.cli.eval_run_golden \
  --persona kant --run-idx "$RUN" --condition natural \
  --turn-count 500 --wall-timeout-min "$WALL" \
  --memory-db "/tmp/p3_natural_kant_run${RUN}.sqlite" \
  --output "data/eval/golden/kant_natural_run${RUN}.duckdb" --overwrite
```

### C.3 run0 partial の再採取 (`--allow-partial-rescue`)

旧 v1 で実行した run0 (focal=381/390/399 partial、ME-9 incident 由来) を再採取。
PR #140 H4 反映で `--allow-partial-rescue` flag が必要 (sidecar 同居の `.tmp`
を unlink するため)。

```bash
# 旧 run0 partial が data/eval/golden/ に残っている場合は data/eval/partial/ へ移動
mkdir -p data/eval/partial/
for P in kant nietzsche rikyu; do
  if [ -f "data/eval/golden/${P}_natural_run0.duckdb.tmp" ]; then
    mv "data/eval/golden/${P}_natural_run0.duckdb"* data/eval/partial/
  fi
done

# 再採取
RUN=0
for P in kant nietzsche rikyu; do
  uv run python -m erre_sandbox.cli.eval_run_golden \
    --persona "$P" --run-idx "$RUN" --condition natural \
    --turn-count 500 --wall-timeout-min "$WALL" \
    --memory-db "/tmp/p3_natural_${P}_run${RUN}_rescue.sqlite" \
    --output "data/eval/golden/${P}_natural_run${RUN}.duckdb" \
    --allow-partial-rescue &
done
wait
```

### C.4 production audit (calibration と exact glob 分離、Codex H3)

```bash
# natural 15 cell のみ audit
uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/golden/*_natural_run*.duckdb' \
  --focal-target 500 \
  --report-json data/eval/golden/_audit_natural.json
# 全 15 cell return 0 を期待
```

### C.5 ME-9 trigger zone monitor (3-parallel context、Amendment 2026-05-08)

3-parallel observation の rate basis:

| central zone (3-parallel) | trigger zone (3-parallel) |
|---|---|
| 0.92-1.20 /min (= 55-72 /h) | < 0.55-0.92 /min OR > 1.20-1.33 /min (= < 33-55 /h or > 72-80 /h) |

各 cell 完了後、sidecar から `focal_observed / wall_timeout_min` を計算:

```bash
for FILE in data/eval/golden/*_natural_run*.duckdb.capture.json; do
  python3 -c "
import json, sys
d = json.load(open('$FILE'))
rate = d['focal_observed'] / d['wall_timeout_min']  # /min
hr = rate * 60  # /h
status = 'OK' if 0.92 <= rate <= 1.20 else ('TRIGGER_LOW' if rate < 0.92 else 'TRIGGER_HIGH')
print(f\"{d.get('persona','?'):<10} run{d.get('run_idx','?'):<3} rate={rate:.3f}/min ({hr:.1f}/h) {status}\")
"
done
```

trigger zone に該当 cell が出たら **G-GEAR 側で正規 STOP**、Mac へ sidecar
+ duckdb を rsync して Codex review 起動 (本来 Phase A で確定しているが、
parallel context の wall=600 min × 3-parallel での再現性は production で
初めて empirical 確認するため warning 維持)。

## Phase D — eval_audit batch + rsync (~30 min)

v2 §Phase D 通り、**calibration と production を exact glob 分離** (Codex H3
反映):

```bash
# 既に C.4 で natural、Phase B で stimulus は audit 済
# 統合 audit (calibration は除外)
uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/golden/*.duckdb' \
  --focal-target 500 \
  --report-json data/eval/golden/_audit_all.json
# stimulus 15 + natural 15 = 30 cell return 0 を期待
```

CHECKPOINT + sidecar md5 receipt (Codex H3 反映、ME-2 protocol):

```bash
# CHECKPOINT で WAL を main file に flush
for FILE in data/eval/golden/*.duckdb; do
  uv run python -c "
import duckdb
con = duckdb.connect('$FILE', read_only=False)
con.execute('CHECKPOINT')
con.close()
"
done

# md5 receipt 生成
cd data/eval/golden/
md5sum -b *.duckdb *.duckdb.capture.json > _checksums_p3_full.txt
ls -la _checksums_p3_full.txt
# 期待: 60 行 (30 duckdb + 30 sidecar)
```

HTTP server で Mac へ pull (P3a-finalize 2026-05-05 で validated):

```bash
# G-GEAR 側で HTTP server 起動 (Phase A と同じ pattern)
cd data/eval/golden/
python3 -m http.server 8765 &
HTTP_PID=$!
echo "HTTP server PID=$HTTP_PID, port=8765, serve from $(pwd)"

# Mac セッション側で:
#   curl -fOSs http://192.168.3.85:8765/_checksums_p3_full.txt
#   for FILE in [filename...]; do curl -fOSs http://192.168.3.85:8765/$FILE; done
#   md5 -r ... > _checksums_mac_received.txt
#   diff <(sort _checksums_p3_full.txt) <(sort _checksums_mac_received.txt)
# Mac の md5 10/10 一致を G-GEAR Claude に報告 → HTTP server 停止
#   Stop-Process -Id $HTTP_PID -Force  (PowerShell)
```

## Phase E — PR 作成 (~10 min)

v2 §Phase E 通り。本セッションの成果は `data/eval/golden/_checksums_p3_full.txt`
+ ADR amendment (実測値反映、ME-9 Amendment 2026-05-08 への follow-up):

```bash
git checkout -b feature/m9-eval-p3-golden-baseline-complete
git add data/eval/golden/_checksums_p3_full.txt \
  .steering/20260430-m9-eval-system/decisions.md
# duckdb 本体は .gitignore で除外、receipt のみ commit
git commit -m "$(cat <<'EOF'
feat(eval): m9 — Phase B + C 完了 (30 cells golden baseline + run0 rescue)

Phase B (stimulus 15) + Phase C (natural 15、3-parallel × wall=600 min) +
run0 partial 再採取 全完了。production data 30 cell が DB9 quorum 採用判定の
golden baseline として ready。

[実測値 / observed contention / wall sufficiency / drain stability を本文に]

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin feature/m9-eval-p3-golden-baseline-complete
gh pr create --title "feat(eval): m9 — Phase B + C 完了 (30 cells golden baseline)" \
  --body "[実測値 + audit json link + rsync md5 verification を本文に]"
```

## Test plan (本セッション完了条件)

- [ ] Phase B: stimulus 15 cell 全 return 0 (audit_stimulus.json で全 PASS)
- [ ] Phase C: natural 15 cell 全 return 0 (audit_natural.json で全 PASS)
- [ ] run0 partial 再採取完了 (3 cell、focal>=500 で complete status)
- [ ] ME-9 trigger zone monitor で 3-parallel rate が central zone 内
      (実測 ≈1.057/min、許容 0.92-1.20)
- [ ] 全 30 cell の sidecar `status=complete`
- [ ] CHECKPOINT 完了、md5 receipt 60 行生成
- [ ] Mac との rsync md5 60/60 一致

## ブロッカー予測 + fallback

### B-1. Phase C で 3-parallel rate が trigger zone に該当

central zone 0.92-1.20 /min の lower trigger 0.55-0.92 /min に該当した場合:
- contention factor が **>1.502** で wall=600 が不足 → **wall=720 に拡張**
  して run X+1 から再開
- ADR (`decisions.md` ME-9 Amendment 2026-05-08) に「wall=600 不足」を記録、
  Mac へ報告

upper trigger > 1.20 /min は contention 軽減 (saturation 早く飽和) で possible
だが unlikely。出たら正規 STOP + Codex review。

### B-2. kant drain timeout 再発

§C.2 fallback で sequential 再実行。`drain_completed=false` の場合は drain
grace を 90s に raise する別タスク化を検討。

### B-3. stimulus cell の audit fail (focal<504、cycle_count=6 でも)

該当 cell のみ `--cycle-count 7` で再採取。それでも focal<500 なら
`--turn-count 600` に拡張。それでも失敗なら Mac へ報告 (PR #140 audit gate 修正
necessary かも)。

### B-4. sidecar 欠損 / 破損 (rsync 後)

Mac 側で `.duckdb.capture.json` 欠損は G-GEAR 側で個別に再生成 (sidecar 単体
再 commit 可能、ME-2 protocol 範囲)。

### B-5. natural cell が fatal (DuckDB INSERT 失敗等)

該当 cell の memory-db (`/tmp/p3_natural_*_run*.sqlite`) を unlink して
`--overwrite` で再採取。3 連続 fatal なら G-GEAR の RAM/disk pressure を確認。

### B-6. 累計 wall が予算超過 (Phase B 5h + Phase C 50h+ で >55h)

wall_budget=600 で run 1 周 10h、5 周で 50h は理論上限。Phase A の 1.502
contention factor 確定で run 1 周 ~9-10h と予測。**overnight×2 + 半日**
で完結見込み、超過したら Phase C を 2 batch (run 0-2 / run 3-4) に分割。

## 関連参照

- `.steering/20260430-m9-eval-system/decisions.md` ME-9 Amendment 2026-05-07
  + Amendment 2026-05-08 (確定値の出典)
- `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md` (本書の
  base、§Phase B / §Phase C / §Phase D / §Phase E をそのまま参照可能)
- `.steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md`
  (Codex 9 回目 review 経緯と採用判断)
- `data/eval/calibration/run1/_checksums_run1_full.txt` (Phase A receipt、
  PR #151 merged で main 取込み)
- ME-2 ADR (rsync protocol、CHECKPOINT + md5 receipt)
- DB9 quorum (M9-B `decisions.md`): 本 prompt が完了して production data 30
  cell が ready になり、Tier B (Vendi / Big5 ICC / Burrows Δ) DB9 quorum 採用
  判定の前提が揃う

## 次セッション以降 (Phase B + C 完了後)

- M9-eval P3a-decide.py の Mac 側再実行 (production 30 cell + calibration 5
  cell 経由で target ratio Burrows / MATTR 確定、ME-4 stage 3 close 候補)
- M9-eval P4a Tier B (PR #148 merged) を golden baseline data に対して実走
  (Vendi sensitivity panel + IPIP-50 + Big5 ICC × 3 persona × 25 windows)
- M9-eval P6 Tier C judge LLM (Prometheus 2 8×7B、systemd unit) 着手
- M9-C-spike (PR #149 scaffold merged) Phase β real Kant training trigger
  (`m9-individual-layer-schema-add` 完了 + 本 P3 baseline 完了の 2 hard
  blocker 解消後)

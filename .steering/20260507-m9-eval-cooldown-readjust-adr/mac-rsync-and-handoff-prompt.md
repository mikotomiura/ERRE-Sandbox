# Mac セッション用プロンプト — m9-eval Phase A run1 calibration 受領 + Phase B/C 準備

> このファイルは G-GEAR セッション (2026-05-08 22:16) で起草。Mac で `/clear` 後に
> 全文をコピペして送る前提。G-GEAR は run1 calibration 5 cell 全完了し、
> ME-9 Amendment 適用後の saturation model + wall-aligned contention factor が
> empirical 確定済 (rsync 待ち)。

## まず確認

```bash
cd ~/ERRE-Sand\ Box
git fetch origin
git checkout main && git pull --ff-only origin main
git log -1 --pretty='%h %s'
# 期待: ab3206d Merge pull request #142 from ... me9-trigger-amendment
# (新コミットあれば最新まで pull)

# G-GEAR HTTP server が稼働中であることを確認
# G-GEAR Wi-Fi IP = 192.168.3.85, port 8765, serve 元 = data/eval/calibration/run1/
curl -fsS http://192.168.3.85:8765/_checksums_run1_full.txt
# 期待: 10 行 (5 duckdb + 5 sidecar の md5)
```

## G-GEAR からの rsync (HTTP pull)

```bash
cd ~/ERRE-Sand\ Box
mkdir -p data/eval/calibration/run1/

GGEAR_HOST="192.168.3.85:8765"
TARGET_DIR="data/eval/calibration/run1"

# 1. md5 receipt 先取り
curl -fOSs "http://${GGEAR_HOST}/_checksums_run1_full.txt"
mv _checksums_run1_full.txt "${TARGET_DIR}/"

# 2. 10 ファイル pull (5 duckdb + 5 sidecar)
for RUN in 100 101 102 103 104; do
  for EXT in duckdb duckdb.capture.json; do
    F="kant_natural_run${RUN}.${EXT}"
    curl -fOSs "http://${GGEAR_HOST}/${F}"
    mv "${F}" "${TARGET_DIR}/"
    echo "pulled: ${F}"
  done
done

# 3. md5 verification (Mac の md5 -r は GNU md5sum と同じ <hash> <space> <file> 形式)
cd "${TARGET_DIR}"
md5 -r kant_natural_run10[0-4].duckdb kant_natural_run10[0-4].duckdb.capture.json \
  | sed 's| | *|' \
  > _checksums_mac_received.txt

diff <(sort _checksums_run1_full.txt) <(sort _checksums_mac_received.txt)
# 出力なし = OK (10/10 hash 一致)
# 不一致なら G-GEAR Claude に報告して再送
```

> **注記**: G-GEAR では `md5sum -b` 風の `*` 区切りで保存されている。
> Mac の `md5 -r` 出力は ` ` 区切りなので `sed` で `*` に正規化してから diff。
> あるいは:
> ```bash
> # alt: --ignore-trailing-space や --strip-trailing-cr を使う
> md5 -q kant_natural_run100.duckdb
> # と _checksums_run1_full.txt の対応行 hash を個別比較
> ```

## Phase A 結果 (G-GEAR から確定済の数値)

### 5-cell summary

| run_idx | wall (min) | focal | total_rows | rate (/min) | rate (/h) |
|---:|---:|---:|---:|---:|---:|
| 100 | 120 | 195 | 582 | 1.625 | 97.50 |
| 101 | 240 | 383 | 1,156 | 1.596 | 95.75 |
| 102 | 360 | 573 | 1,723 | 1.592 | 95.50 |
| 103 | 480 | 754 | 2,270 | 1.571 | 94.25 |
| 104 | 600 | 931 | 2,816 | 1.552 | 93.10 |

### 統計

```
n = 5
focal_per_min_single mean   = 1.5870 /min  (95.22 /h)
stdev                        = 0.0276 /min
95% CI (t-dist, df=4)       = [1.5527, 1.6213] /min  ≈ [93.16, 97.28] /h
```

→ **全 5 cell が ME-9 Amendment single calibration central zone (1.55-1.87/min) 内**、
  saturation curve が単調減少 (1.625 → 1.552) で漸近線へ収束。

### Contention factor wall-aligned 再校正 (Codex 9th review HIGH 3)

```
run102 single 360min      = 1.592 /min   (wall-matched comparison)
run0 3-parallel 360min    = 1.06  /min   (incident reference)
contention_factor (1.502) = 1.592 / 1.06
```

→ §B.3 default 仮定 1.76× より **−14.7% 狭い** = 3-parallel contention は事前推計より軽い。

### run2-4 wall budget

```
parallel rate estimate    = 1.587 / 1.502 = 1.057 /min
wall_budget_raw           = ceil(500 / (1.057 × 0.85)) = 557 min
rounded to 60-multiple    = 600 min
```

→ **§B.3 default 600 min を採用確定**。run2-4 を 600 min wall_budget で 3-parallel 採取 OK。

## Mac でのタスク

### 1. ME-9 Amendment + Phase A 結果を `decisions.md` に追記

`.steering/20260430-m9-eval-system/decisions.md` の ME-9 Amendment ブロックに、
本セッションで確定した以下を追記:

- **Phase A run1 calibration 完了** (2026-05-08 18:49、kant only × 5 wall sequential)
- **5-cell empirical rates table** (上記)
- **focal_per_min_single mean = 1.587 (95% CI [1.553, 1.621])**
- **wall-aligned contention factor = 1.502** (run102/run0_360min)
- **§B.3 wall_budget 確定 = 600 min for run2-4**

`.steering/20260507-m9-eval-cooldown-readjust-adr/` の 5 ファイル (本タスク) も
finalize:
- `decisions.md`: amendment 適用済
- `tasklist.md`: Phase A 完了 check + Phase B/C 計画 link
- `blockers.md`: Monitor false-positive STOP 経緯と Resume 手順を記録

### 2. p3a_decide / G-GEAR で得られた duckdb の sanity inspect

```bash
cd ~/ERRE-Sand\ Box
uv run python -c "
import duckdb
for r in [100, 101, 102, 103, 104]:
    p = f'data/eval/calibration/run1/kant_natural_run{r}.duckdb'
    c = duckdb.connect(p, read_only=True)
    cnt = c.execute('SELECT COUNT(*) FROM raw_dialog').fetchone()[0]
    focal_cnt = c.execute(\"SELECT COUNT(*) FROM raw_dialog WHERE turn_kind='focal'\").fetchone()[0]
    persona = c.execute('SELECT DISTINCT persona FROM raw_dialog').fetchone()[0]
    print(f'run{r}: total={cnt} focal={focal_cnt} persona={persona}')
    c.close()
"
# 期待: sidecar の total_rows / focal_observed と一致
```

### 3. PR 作成 (Phase A 完了 + ME-9 Amendment 補強)

```bash
git checkout -b feature/m9-eval-phase-a-run1-complete
git add data/eval/calibration/run1/ \
  .steering/20260430-m9-eval-system/decisions.md \
  .steering/20260507-m9-eval-cooldown-readjust-adr/
git commit -m "$(cat <<'EOF'
feat(eval): m9 — Phase A run1 calibration 完了 (5/5 cells, saturation confirmed)

- run100..104 (kant only × 5 wall sequential, run_idx 100..104)
- 全 5 cell が single calibration central zone 内 (rate 1.625 → 1.552 saturation)
- focal_per_min_single mean = 1.587 (95% CI [1.553, 1.621])
- wall-aligned contention factor (run102 vs run0 360min) = 1.502
- §B.3 wall_budget 確定 = 600 min for run2-4 production
- Monitor false-positive (count 4 でなく 5 が真) を blockers.md に記録

Refs: .steering/20260430-m9-eval-system/decisions.md ME-9 Amendment 2026-05-07
Refs: .steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin feature/m9-eval-phase-a-run1-complete
gh pr create --title "feat(eval): m9 — Phase A run1 calibration 完了 (5/5 cells)" \
  --body "$(cat <<'EOF'
## Summary
- run1 calibration kant only × 5 wall (120/240/360/480/600) sequential 完了
- 全 5 cell が ME-9 Amendment single calibration central zone (1.55-1.87/min) 内
- Saturation curve 単調減少 (1.625 → 1.552)、漸近線へ収束
- focal_per_min_single mean=1.587 (95% CI [1.553, 1.621]、stdev=0.0276)
- contention factor wall-aligned = 1.502 (run102/run0_360parallel、§B.3 default 1.76 より -14.7%)
- run2-4 wall_budget 確定 = **600 min** for production 3-parallel

## Test plan
- [x] 5 sidecar すべて status=partial / stop_reason=wall_timeout / drain_completed=true
- [x] G-GEAR md5 receipt vs Mac 受信 hash 10/10 一致
- [x] DuckDB read_only inspect で sidecar total/focal と整合
- [ ] Phase B (stimulus 全 15 cell) 開始は次セッション

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 4. 次セッション (Phase B + C 採取) の launch prompt 起草

`.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md` の §Phase B / §Phase C
を base に、確定値 (wall_budget=600, contention_factor=1.502) を反映した
**Phase B+C 起動プロンプト** (G-GEAR 投入用) を新規作成:

- §Phase B (stimulus 15 cell × cycle_count=6, ~3-5h)
- §Phase C (natural 15 cell × wall=600 min × 3-parallel, ~24-48h overnight×2)
- run0 partial 再採取 (§C.3、`--allow-partial-rescue` 必要)
- ME-9 Amendment 適用後の trigger zone (3-parallel: <0.55-0.92/min or >1.20-1.33/min)

## ファイル参照

- `.steering/20260430-m9-eval-system/decisions.md` (ME-9 Amendment + Phase A 確定値)
- `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md` (Phase B/C 経路)
- `.steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md` (Codex 9th review 経緯)
- `data/eval/calibration/run1/_checksums_run1_full.txt` (rsync receipt)

## G-GEAR HTTP server 停止 (Mac 受信完了後)

```bash
# Mac 側で md5 diff が空 (=10/10 一致) を確認したら、G-GEAR Claude に報告。
# G-GEAR Claude が PowerShell で:
#   Stop-Process -Id 6860, 13672 -Force
# でサーバー停止。
```

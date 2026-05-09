# Next-session handoff prompt — Phase C kick (REVISED, multi-session)

**作成**: 2026-05-09 (Phase C kick aborted 後の re-strategy、判断 9 反映)
**前 handoff**: `next-session-prompt-phase-c.md` (timing 仮定誤り、用済み)
**前セッション失敗成果**: kant_natural_run0 が 89.5 min で 438 行 (focal_target=500 未到達)、`timeout 90m` で kill。Phase B 5 min/cell は stimulus 限定の特性、natural は ~5h/cell (実測 ~5 dialog 行/min × focal_target 1500 行 ≈ 5h)
**用途**: 新セッション (G-GEAR、Auto mode 推奨、Opus、overnight 推奨) の最初の prompt として貼り付け

---

```
m9-individual-layer-schema-add Phase C (natural 15 cell) を多セッション分割で採取する。
判断 9 (decisions.md) と B-2-C blocker (blockers.md) を必ず先に読むこと。

## 環境 (判断 8 維持、判断 9 で wall budget のみ補正)

- G-GEAR、Windows native、`PYTHONUTF8=1`、Git Bash
- WSL2 から Ollama 不通のため Windows native 必須 (判断 8)
- sequential 実行 (3-parallel は GPU contention overhead 不明、判断 9 で採用見送り)
- `--turn-count 500` 維持 (B/C parity を破壊しない)
- shell timeout: `timeout 360m` (6h、CLI `--wall-timeout-min 600` の 60% safety margin)
- 1 cell 想定: 3-5h
- 1 セッション想定: 3-5 cell (overnight)
- Phase C 完了総量: 15 cell ≈ 4-5 セッション

## セッション分割 (推奨)

| セッション | scope | 想定 wall |
|---|---|---|
| C-1 (本セッション) | run0 × 3 persona = 3 cell + cleanup | 12-15h |
| C-2 | run1 × 3 persona = 3 cell | 12-15h |
| C-3 | run2 × 3 persona = 3 cell | 12-15h |
| C-4 | run3 × 3 persona = 3 cell | 12-15h |
| C-5 | run4 × 3 persona = 3 cell + Phase E PR | 12-15h |

各セッションは独立して再 kick 可能。本ファイルの「最初にやること」セクションで current state を判定する。

## 最初にやること (毎セッション共通、state 判定)

### 1. 前提確認 (4 つ)

```bash
# (a) main HEAD と branch
git log -1 --oneline
git branch --show-current   # feature/m9-eval-phase-b-stimulus-baseline で OK (Phase B 受け branch を継続使用)

# (b) GPU idle
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
# 期待: 5% 未満 / 1-2 GB used (Ollama daemon のみ)

# (c) Ollama daemon と model 揃い
curl -s http://localhost:11434/api/version
ollama list | grep -E "qwen3:8b|nomic-embed-text"

# (d) 直前セッションが残した orphan python が無い
powershell -NoProfile -Command "Get-Process | Where-Object {\$_.ProcessName -match 'python|uv'} | Select-Object Id,ProcessName,StartTime"
# 期待: empty (もし残っていれば Stop-Process で kill)
```

### 2. Phase B/C 進捗判定 (どの run まで完了済か)

```bash
# Phase B (stimulus): 不変、15 cell complete 前提
ls -1 data/eval/golden/*_stimulus_run*.duckdb 2>/dev/null | wc -l  # 期待: 15
ls -1 data/eval/golden/_audit_stimulus.json _checksums_phase_b.txt 2>/dev/null

# Phase C (natural): どの run まで生成済か
for R in 0 1 2 3 4; do
  N=$(ls -1 data/eval/golden/*_natural_run${R}.duckdb 2>/dev/null | grep -v '\.tmp' | wc -l)
  echo "run${R}: ${N}/3"
done
# 各 run が 3/3 なら次の run へ、0/3 なら本セッションで kick
```

### 3. 既存 partial cleanup (新規 kick 前に必須、判断 9 採用方針)

```bash
# 部分採取 .tmp は削除して fresh kick (継承すると dialog continuity が壊れる)
rm -f data/eval/golden/*_natural_run*.duckdb.tmp
rm -f data/eval/golden/*_natural_run*.duckdb.tmp.wal
rm -f /tmp/p3_natural_*_run*.sqlite

# data/eval/partial/ の旧 5/6 .tmp は判断 9 で defer 削除 (B/C parity 比較で baseline 品質を満たさず)
# 削除しないが本セッションでも参照しない
```

### 4. 本セッションで採取する run を決定

```bash
# 上の (2) で判定した最小未完了 run (例: run0 が 0/3 なら RUN_TO_KICK=0)
RUN_TO_KICK=0   # ← 本セッション分の値に変更
echo "本セッションで採取: run${RUN_TO_KICK} × 3 persona = 3 cell"
```

### 5. Phase C bg kick (sequential、~12-15h、判断 9 wall budget 改訂)

`.claude` Bash tool の `run_in_background=true` で bg kick。Monitor は per-cell START/END + ALL DONE + 主要 error signature を grep で拾う。

```bash
export PYTHONUTF8=1
WALL=600    # CLI inner wall budget (10h)
LOG=.steering/20260509-m9-individual-layer-schema-add/phase-c-runlog-run${RUN_TO_KICK}.txt
echo "=== START Phase C run${RUN_TO_KICK} kick at $(date -Is) ===" | tee "$LOG"
for P in kant nietzsche rikyu; do
  echo "=== natural ${P} run${RUN_TO_KICK} START $(date -Is) ===" | tee -a "$LOG"
  timeout 360m uv run python -m erre_sandbox.cli.eval_run_golden \
    --persona "${P}" --run-idx "${RUN_TO_KICK}" --condition natural \
    --turn-count 500 --wall-timeout-min "$WALL" \
    --memory-db "/tmp/p3_natural_${P}_run${RUN_TO_KICK}.sqlite" \
    --output "data/eval/golden/${P}_natural_run${RUN_TO_KICK}.duckdb" \
    2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
  echo "=== natural ${P} run${RUN_TO_KICK} END $(date -Is) rc=${rc} ===" | tee -a "$LOG"
done
echo "=== ALL DONE run${RUN_TO_KICK} at $(date -Is) ===" | tee -a "$LOG"
```

**重要 (前セッションの教訓)**:
- TaskStop で bg shell を kill しても **`timeout 360m` 配下の python 子プロセスは独立で動き続ける**。途中 abort する場合は `tasklist | grep python` + `Stop-Process -Force` で確実に kill すること
- `timeout 360m` は CLI `--wall-timeout-min 600` (= 10h) の 60% で、6h を超えても CLI 側の wall budget でまだ余裕あり (ただし shell の hard cap が先に効く)
- 1 cell が 6h を超えた場合は判断 9 の rate 仮定 (~5 行/min) が外れている可能性 → 直ちに kill して runlog を観察、原因 (Ollama 不調 / model swap 競合 / DB I/O ボトルネック) を診断

### 6. 本セッション分の audit (run 単位)

```bash
PYTHONUTF8=1 uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob "data/eval/golden/*_natural_run${RUN_TO_KICK}.duckdb" \
  --focal-target 500 \
  --report-json "data/eval/golden/_audit_natural_run${RUN_TO_KICK}.json"
ls -1 data/eval/golden/*_natural_run${RUN_TO_KICK}.duckdb | wc -l   # 期待: 3
```

期待: 3/3 complete、partial=0、fail=0。1 cell でも partial の場合は **その cell のみ削除して再 kick** (本セッション内で再試行可、ただし wall 残量を確認)。

### 7. セッション末 commit (run 単位、PR は最終セッションでまとめて)

```bash
# 本セッション分の per-run audit + runlog を commit (PR は run4 完了後)
git add data/eval/golden/_audit_natural_run${RUN_TO_KICK}.json \
        .steering/20260509-m9-individual-layer-schema-add/phase-c-runlog-run${RUN_TO_KICK}.txt \
        .steering/20260509-m9-individual-layer-schema-add/tasklist.md
git commit -m "feat(eval): m9 — Phase C run${RUN_TO_KICK} 採取完了 (3 cells natural)"
git push origin feature/m9-eval-phase-b-stimulus-baseline
```

## 最終セッション (run4 完了時) で実行する Phase E

run4 の audit が 3/3 complete + 全 5 run × 3 persona = 15 natural cell が `data/eval/golden/` に揃ったら、`g-gear-phase-bc-launch-prompt.md §Phase E` 通りに統合:

```bash
# 統合 audit (30 cell = stimulus 15 + natural 15)
PYTHONUTF8=1 uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/golden/*.duckdb' \
  --focal-target 500 \
  --report-json data/eval/golden/_audit_all.json

# CHECKPOINT + md5 receipt (30 duckdb + 30 sidecar + 1 audit_all = 61 行)
for FILE in data/eval/golden/*.duckdb; do
  PYTHONUTF8=1 uv run python -c "
import duckdb
con = duckdb.connect('$FILE', read_only=False)
con.execute('CHECKPOINT')
con.close()
"
done
( cd data/eval/golden/ && md5sum -b *.duckdb *.duckdb.capture.json _audit_all.json > _checksums_p3_full.txt )
wc -l data/eval/golden/_checksums_p3_full.txt   # 期待: 61

# 統合 feature ブランチ + PR
git checkout -b feature/m9-eval-p3-golden-baseline-complete
git add data/eval/golden/_checksums_p3_full.txt \
        data/eval/golden/_audit_all.json \
        data/eval/golden/_audit_natural*.json \
        .steering/20260509-m9-individual-layer-schema-add/phase-c-runlog-run*.txt \
        .steering/20260509-m9-individual-layer-schema-add/tasklist.md \
        .steering/20260509-m9-individual-layer-schema-add/decisions.md \
        .steering/20260509-m9-individual-layer-schema-add/blockers.md
git commit -m "feat(eval): m9 — Phase B + C 完了 (30 cells golden baseline)"
git push -u origin feature/m9-eval-p3-golden-baseline-complete
gh pr create --title "feat(eval): m9 — Phase B + C 完了 (30 cells golden baseline)" \
  --body "<HEREDOC: ME-9 Amendment + 判断 8 + 判断 9 + audit 30/30 + checksum 61 行>"
```

## 注意

- main 直 push 禁止 / 50% 超セッション継続禁止 (`/smart-compact`)
- GPL を `src/erre_sandbox/` に import 禁止
- Phase C kick 中は GPU 占有 → 並列で別 GPU タスクを起動しない (judgment 9 で sequential 確定)
- Native Windows + `PYTHONUTF8=1` を必ず指定 (cp932 codepage で em-dash crash)
- bg shell の TaskStop は **python 子プロセスを kill しない** ことが判明 → 途中 abort 時は `tasklist /v | grep python` + `Stop-Process -Force` で確実に kill すること
- partial .tmp の rescue は不採用 (判断 9)、必ず削除して fresh kick

## 参照

- 判断 8: `.steering/20260509-m9-individual-layer-schema-add/decisions.md` 判断 8 (Windows native 転換)
- 判断 9: 同 decisions.md 判断 9 (Phase C wall budget 改訂)
- B-2-C blocker: `.steering/20260509-m9-individual-layer-schema-add/blockers.md` (本ブロッカーの解消が本 multi-session の goal)
- ME-9 Amendment: `.steering/20260430-m9-eval-system/decisions.md` (公式 launch prompt の確定値)
- 失敗 runlog: `.steering/20260509-m9-individual-layer-schema-add/phase-c-runlog.txt` (kant 89.5min + nietzsche orphan 89min)

## 完了条件 (Phase C 全体、最終セッション末で確認)

- [ ] data/eval/golden/ に natural 15 cell 全揃い
- [ ] `_audit_natural_run{0..4}.json` 各 3/3 PASS、計 15/15 PASS
- [ ] `_audit_all.json` で 30/30 PASS
- [ ] CHECKPOINT 完了、`_checksums_p3_full.txt` 61 行
- [ ] `feature/m9-eval-p3-golden-baseline-complete` で 30 cell 統合 PR 作成
- [ ] Mac rsync md5 61/61 一致確認 (memory `feedback_batch_integration_over_per_session_sync` 通り、PR merge 後で OK)

## 前セッション (Phase C kick 失敗、2026-05-09) 実測値

- Phase C kick 開始: 2026-05-09T18:04:44+09:00
- kant_natural_run0 END: 2026-05-09T19:34:45+09:00 (rc=124, `timeout 90m` 到達)
- nietzsche_natural_run0: orphan で 21:04 まで継続走行 (TaskStop が python 子プロセスに届かず)
- kant 採取: `raw_dialog.dialog` 438 行 / focal_target=500 未到達 / status=partial
- 観測 throughput: ~5 dialog 行/min (Phase B stimulus の ~100 focal/min と桁違い)
- 結論: natural は ~5h/cell が実測値、handoff prompt の 5-10 min/cell は誤り
- 本セッションでの commit: `feature/m9-eval-phase-b-stimulus-baseline` に decisions/blockers/tasklist/runlog/handoff の 5 ファイルを追加 (Phase C 採取物 0 件、PR なし)
```

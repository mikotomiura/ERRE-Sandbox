# Next-session handoff prompt — Phase C kick (post Phase B complete)

**作成**: 2026-05-09 (Phase B 完了後の context-rotation 想定で pre-stage)
**前セッション成果**: Phase B 15 stimulus cells 全 PASS、`feature/m9-eval-phase-b-stimulus-baseline` で receipt + audit json commit + origin push 済 (commit `2812285`、Mac fetch は git 経由、HTTP server 不要、.duckdb 本体は Phase C 完了の統合 PR まで G-GEAR 保持)
**用途**: 新セッション (G-GEAR、Auto mode 推奨、Opus) の最初の prompt として貼り付け

---

```
m9-individual-layer-schema-add Phase B (stimulus 15 cell) を 2026-05-09 に完了。
本セッションは G-GEAR で Phase C (natural 15 cell, ~24-48h overnight×2) を
WSL2 ではなく **Windows native** で bg kick し、完了確認 + commit + Mac rsync
まで進めるセッション。

## 実行環境の選択 (Phase B で確定)

Phase B kick で **WSL2 NAT mode から Windows 側 Ollama (127.0.0.1:11434) に
到達不能** が判明 (Ollama bind が 127.0.0.1 only、WSL2 から見える Windows host
gateway 172.28.96.1 では Ollama listening なし)。Windows native + `PYTHONUTF8=1`
+ Git Bash の GNU `timeout` で実行する pattern を Phase B で確立、Phase C も
同じ環境で実行する。WSL2 networking 修正 (Ollama bind 0.0.0.0 + firewall 開放)
は invasive なので回避。

## 直近完了状態 (前セッション、Phase B)

- Phase B 15 stimulus cells 全 audit PASS (`_audit_stimulus.json` で全 complete)
- `feature/m9-eval-phase-b-stimulus-baseline` で receipt + audit json を commit + push
- Mac rsync md5 31/31 一致確認済 (HTTP server 経由、port 8765)
- B-2 K-β trigger 状態のうち Phase B 分は解消、Phase C 分が残存

## 次タスク: Phase C kick (G-GEAR、最優先、~24-48h overnight×2)

`g-gear-phase-bc-launch-prompt.md §Phase C` の手順をベースに、Windows native +
sequential 実行で kick (3-parallel は **しない**、Phase B で 5 min/cell の高速化が
確認されたため sequential でも overnight 1 晩で完了見込み)。

## 最初にやること

### 1. 前提確認 (3 つ)

```bash
# (a) main HEAD が Phase B receipt commit 後の HEAD (or main で Phase C 用ブランチ作成可能か)
git log -1 --oneline

# (b) GPU idle で kick 可能か
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
# 期待: 5% 未満 / 1-2 GB used (Ollama daemon のみ)

# (c) Ollama daemon が live、qwen3:8b と nomic-embed-text が pull 済
curl -s http://localhost:11434/api/version
ollama list | grep -E "qwen3:8b|nomic-embed-text"
```

### 2. data/eval/golden/ に Phase B の 15 stimulus + sidecar が残っているか確認

```bash
ls -1 data/eval/golden/*_stimulus_run*.duckdb | wc -l  # 期待: 15
ls -1 data/eval/golden/*_stimulus_run*.duckdb.capture.json | wc -l  # 期待: 15
ls -1 data/eval/golden/_audit_stimulus.json _checksums_phase_b.txt
```

(natural は本セッションで生成、stimulus は Phase B で生成済を保持)

### 3. Phase C bg kick (Windows native、~24-48h)

`g-gear-phase-bc-launch-prompt.md §C.1` ベース。3-parallel は **しない** (Phase B
の 5 min/cell から推測すると natural も sequential で 1 cell ~5-10 min × 15 =
~75-150 min = ~1.5-3h で完了見込み、3-parallel の wall=600 min は overengineering)。

```bash
# Bash tool の run_in_background=true で実行
export PYTHONUTF8=1
WALL=600  # ME-9 Amendment 確定値、natural の wall budget は 600 min を維持
echo "=== START Phase C kick at $(date -Is) ==="
for RUN in 0 1 2 3 4; do
  for P in kant nietzsche rikyu; do
    echo "=== natural ${P} run${RUN} START $(date -Is) ==="
    timeout 90m uv run python -m erre_sandbox.cli.eval_run_golden \
      --persona "${P}" --run-idx "${RUN}" --condition natural \
      --turn-count 500 --wall-timeout-min "$WALL" \
      --memory-db "/tmp/p3_natural_${P}_run${RUN}.sqlite" \
      --output "data/eval/golden/${P}_natural_run${RUN}.duckdb"
    rc=$?
    echo "=== natural ${P} run${RUN} END $(date -Is) rc=${rc} ==="
  done
done
echo "=== ALL DONE at $(date -Is) ==="
```

### 4. 完了確認 (audit、natural 単独)

```bash
PYTHONUTF8=1 uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/golden/*_natural_run*.duckdb' \
  --focal-target 500 \
  --report-json data/eval/golden/_audit_natural.json
ls -1 data/eval/golden/*_natural_run*.duckdb | wc -l  # 期待: 15
```

### 5. Phase E PR 作成 (`g-gear-phase-bc-launch-prompt.md §Phase E` 通り)

stimulus 15 (Phase B) + natural 15 (Phase C) = **30 cell まとめて統合 PR** を起票:

```bash
# Phase D の統合 audit
PYTHONUTF8=1 uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/golden/*.duckdb' \
  --focal-target 500 \
  --report-json data/eval/golden/_audit_all.json

# CHECKPOINT + md5 receipt (30 duckdb + 30 sidecar + 1 audit_all.json = 61 行)
for FILE in data/eval/golden/*.duckdb; do
  PYTHONUTF8=1 uv run python -c "
import duckdb
con = duckdb.connect('$FILE', read_only=False)
con.execute('CHECKPOINT')
con.close()
"
done
cd data/eval/golden/
md5sum -b *.duckdb *.duckdb.capture.json _audit_all.json > _checksums_p3_full.txt
cd -

# 統合 feature ブランチで commit (Phase B branch を rebase or 新規)
git checkout -b feature/m9-eval-p3-golden-baseline-complete
git add data/eval/golden/_checksums_p3_full.txt \
        data/eval/golden/_audit_all.json
git commit -m "feat(eval): m9 — Phase B + C 完了 (30 cells golden baseline)"
git push -u origin feature/m9-eval-p3-golden-baseline-complete
gh pr create --title "feat(eval): m9 — Phase B + C 完了 (30 cells golden baseline)" \
  --body "..."
```

### 6. ME-9 trigger zone monitor (sequential context、Amendment 2026-05-08 §C.5)

3-parallel は使わないので、`g-gear-phase-bc-launch-prompt.md §C.5` の rate
formula は **sequential context で再評価**。Phase B では 504 focal_observed /
~5 min wall = ~100 focal/min、これは 3-parallel の central zone 0.92-1.20/min と
桁違い (sequential rate は contention factor が無いため)。trigger zone monitor は
sequential では skip 可、3-parallel に切り替える場合のみ復活。

## 参照すべき memory / docs

- `MEMORY.md` (auto-loaded)
- `.claude/memory/reference_g_gear_host.md` — WSL2 配置 + Ollama 起動 + uv 環境
- `.steering/20260430-m9-eval-system/g-gear-phase-bc-launch-prompt.md` — Phase B/C 公式手順
  (本セッションは sequential + Windows native へ deviate、§C.1 を読み替え)
- `.steering/20260430-m9-eval-system/decisions.md` ME-9 Amendment 2026-05-08 — 確定値
- `.steering/20260509-m9-individual-layer-schema-add/decisions.md` 判断 8 — Phase C kick 別セッション defer
- `.steering/20260509-m9-individual-layer-schema-add/blockers.md` D-1 — 不要 (PR-A merge 後 kick)

## 注意

- main 直 push 禁止 / 50% 超セッション継続禁止 (`/smart-compact`)
- GPL を `src/erre_sandbox/` に import 禁止
- Phase C kick 中は GPU 占有 → 並列で別 GPU タスクを起動しない
- `--allow-partial-rescue` は **Phase B では不要、Phase C run0 partial rescue で必要** な場合あり
  (Phase B 退避済の `data/eval/partial/{kant,nietzsche,rikyu}_natural_run0.duckdb.tmp`
   からの rescue は本セッションでは新規 kick で代替、partial rescue は不要)
- Native Windows + `PYTHONUTF8=1` を必ず指定 (cp932 codepage で em-dash crash する)

## 完了条件 (本セッション)

- [ ] data/eval/golden/ に natural 15 cell + sidecar 全揃い (Phase B の 15 stimulus を残したまま)
- [ ] `_audit_natural.json` で全 15 PASS
- [ ] `_audit_all.json` で 30/30 PASS
- [ ] CHECKPOINT 完了、`_checksums_p3_full.txt` 生成 (61 行)
- [ ] `feature/m9-eval-p3-golden-baseline-complete` で 30 cell まとめて push + PR 作成
- [ ] Mac rsync md5 61/61 一致確認 (HTTP server port 8765)

## 前セッション (Phase B) 実測値

- Phase B 開始: 2026-05-09T12:49:58+09:00
- Phase B 終了: 2026-05-09T14:10:31+09:00
- Phase B 合計 wall: **80.5 min** (1h 20min 33s)
- 各 cell wall: **~5 min/cell** (range 5-6 min、handoff 想定 75 min/cell から 15× 短縮)
- focal_observed: **全 15 cell で 504** (focal_target=500、+4 over-shoot は cycle-count=6 の自然な結果)
- audit PASS rate: **15/15 complete** (partial=0, missing_sidecar=0, mismatch=0, fail=0, overall_exit_code=0)
- commit: `2812285 feat(eval): m9 — Phase B 完了 (15 stimulus cells golden baseline)`
- branch: `feature/m9-eval-phase-b-stimulus-baseline` (origin push 済)
- DDL 確認: 全 cell が B-1 schema (16 cols incl. `individual_layer_enabled BOOLEAN NOT NULL DEFAULT FALSE`、 default `CAST('f' AS BOOLEAN)`)、全行 `individual_layer_enabled=FALSE`
- 主要転換: WSL2 NAT mode から Windows 側 Ollama (127.0.0.1:11434) 不通 → Windows native + `PYTHONUTF8=1` + Git Bash GNU `timeout` で kick (詳細は判断 8 参照)
```

# G-GEAR セッション用プロンプト — m9-eval-system P3 Golden baseline 採取

> このファイルは Mac セッション (2026-05-05、PR #134 merge 直後) で起草。
> G-GEAR (Windows / RTX 5060 Ti 16GB / Ollama 0.22.0) で `/clear` 後に
> 全文をコピペして送る前提。Mac → G-GEAR の sync は user が事前に
> `git fetch && git checkout main && git pull --ff-only` で完了している想定
> (main = `7f3dd57` 以降、PR #134 merged)。
>
> 直前 G-GEAR セッションは **P3a 自然 re-capture (PR #133)** で stimulus + natural
> 6 cell を pilot 採取済。Mac 側 PR #134 で `scripts/p3a_decide.py` v3 拡張 +
> Codex HIGH 3 / MEDIUM 4 反映 + ratio 暫定維持 (200/300 default、3 re-open
> 条件付き) が確定。本セッションは **P3 production 採取** (3 persona × 5 run ×
> 500 turn、確定 ratio 投入) を実行する。

---

## 本セッションで実行すること

タスク `20260430-m9-eval-system` Phase **P3 — Golden baseline 採取** を G-GEAR で
実行する。

- **対象 cell 数**: 3 persona (kant / nietzsche / rikyu) × 2 condition (stimulus /
  natural) × 5 run (run_idx 0..4) = **30 cell**
- **focal turn target**: 500/cell (P3a pilot は 30、P3 は本番 production)
- **wall 予算**: 設計上 24h × overnight×2 = 48h、実機ベースは下記 §empirical 工数
  推計を参照
- **品質ゲート**: 各 cell で `eval_audit` 経由の row 数完全性確認、MD5
  receipt 経由の Mac 転送

## まず Read (この順)

1. `.steering/20260430-m9-eval-system/decisions.md`
   - **ME-2** (rsync protocol、CHECKPOINT + temp+rename、md5 照合)
   - **ME-4** (Hybrid baseline ratio、200/300 暫定維持、3-stage partial close
     構造、stage 2 close 完了。L122 以降、特に "2026-05-05 partial update #3"
     ブロック)
   - **ME-5** (RNG seed、blake2b 経由の uint64 stable seed → `derive_seed`)
   - **ME-8** (`COOLDOWN_TICKS_EVAL=5` + wall default 120、eval cadence
     calibration 概念)
2. `.steering/20260430-m9-eval-system/tasklist.md` lines 381-386
   (P3 entry + P3-validate)
3. `data/eval/pilot/_summary.json` + `data/eval/pilot/_p3a_decide.json`
   (pilot 6 cell の empirical 実測値、特に focal_rows/total_rows/dialog_count
   と target-extrapolated CI width)
4. `src/erre_sandbox/cli/eval_run_golden.py` (CLI 入口、`--persona / --run-idx /
   --condition / --turn-count / --cycle-count / --wall-timeout-min` を熟読)
5. `src/erre_sandbox/evidence/golden_baseline.py` の
   `assert_seed_manifest_consistent()` (Mac/G-GEAR 同値性 runtime guard)

## Pre-condition

```bash
cd ~/ERRE-Sand\ Box
git fetch origin
git checkout main && git pull --ff-only origin main
# main = 7f3dd57 以降を確認:
git log -1 --pretty='%h %s'
# → 7f3dd57 Merge pull request #134 ... または以降の merge

# テスト pass 確認 (P3 採取に着手する前の sanity)
uv run pytest tests/test_evidence/ -q  # 224 passed + p3a_decide 17 passed = 241 程度

# Ollama daemon 稼働 + qwen3:8b Q4_K_M + nomic-embed-text 確認
ollama list | grep -E "qwen3:8b|nomic-embed-text"
# → 両方 present、qwen3:8b は Q4_K_M (~5.2GB) の想定
```

## empirical 工数推計 (P3a pilot 実測からの線形外挿)

P3a pilot (`_rsync_receipt.txt` empirical):
- natural single cell: 30 focal turn / wall ~16 min (P3a-fix-v2 cooldown=5 適用後)
- natural 3-cell parallel: 22 min wall で 3 cell (kant の drain timeout 例外あり)
- stimulus single cell: 198 focal turn / wall は明示記載なし (推定 30-40 min)

P3 production への線形外挿 (caveat: 線形外挿は cognition memory 蓄積効果を
無視している、実機で再校正が必要):
- natural 500-turn cell (single): 30 turn 16 min × (500/30) ≈ **267 min ≈ 4.5h**
- natural 500-turn cell (3-persona parallel): 22 min × (500/30) ≈ 367 min ≈ **6h**
- stimulus 500-turn cell (single): pilot 200-turn を 30-40 min 想定 → 500 turn ≈
  75-100 min ≈ **1.5h**

**全 30 cell の最楽観シーケンス** (3-persona parallel × condition × run):
- natural: 5 run × 6h = **30h**
- stimulus: 5 run × 1.5h × 3-persona-parallel ≈ 5 × 30 min = **2.5h**
- 合計 ~32.5h、24h × 2 night の予算内に収まる見込み

**保守的シーケンス** (single-cell 直列、kant drain timeout 回避):
- natural: 15 cell × 4.5h = 67.5h → 2 night では収まらず

→ **3-persona parallel を default、kant drain timeout が再発したら sequential
fallback** を推奨。pilot で kant Phase B parallel が timeout した事例
(`_rsync_receipt.txt` L28-30) があるので、最初の 1 run で 3-persona parallel が
成立するか確認するのが先決。

## 推奨実行プラン

### Phase 0 — Pre-flight sanity (15 min)

```bash
# kant_natural run0 のみ wall=60 min budget で 50-turn dry run
uv run python -m erre_sandbox.cli.eval_run_golden \
    --persona kant --run-idx 0 --condition natural \
    --turn-count 50 --wall-timeout-min 60 \
    --output /tmp/p3_dryrun_kant_natural.duckdb --overwrite
# 期待: focal=50, wall<30 min。問題なければ Phase 1 進行
# 期待値外れ (focal<30 / wall>30 min) なら停止 → Mac へ報告
```

### Phase 1 — stimulus 全 15 cell (3-persona parallel × 5 run、~3-5h)

stimulus は cognition memory 不要 (battery 駆動)、parallel に弱い contention。

run_idx を 0 → 4 まで 5 round。各 round で 3 persona を **順次** 実行
(stimulus は parallel しなくても十分速いはず):

```bash
for RUN in 0 1 2 3 4; do
  for P in kant nietzsche rikyu; do
    uv run python -m erre_sandbox.cli.eval_run_golden \
      --persona "$P" --run-idx "$RUN" --condition stimulus \
      --turn-count 500 --cycle-count 3 \
      --output "data/eval/golden/${P}_stimulus_run${RUN}.duckdb"
  done
done
```

### Phase 2 — natural 全 15 cell (3-persona parallel × 5 run、~24-30h)

natural は cognition tick + reflection で重い、parallel で総 throughput 向上の
実績あり (pilot Phase B、kant 例外あり)。

各 run で **3 persona を tmux pane / 別 shell で同時起動**:

```bash
# 例: run_idx=0 を 3 並列起動 (tmux 推奨)
RUN=0
for P in kant nietzsche rikyu; do
  uv run python -m erre_sandbox.cli.eval_run_golden \
    --persona "$P" --run-idx "$RUN" --condition natural \
    --turn-count 500 --wall-timeout-min 360 \
    --memory-db "/tmp/p3_natural_${P}_run${RUN}.sqlite" \
    --output "data/eval/golden/${P}_natural_run${RUN}.duckdb" &
done
wait  # 3 並列完了待ち、kant drain timeout 出たら sequential fallback
```

**kant drain timeout fallback**: pilot Phase B 同様 kant が parallel で
timeout したら、kant のみ sequential に再実行 (他 2 persona は parallel 成功
していればその DuckDB は再採取不要):

```bash
# kant が parallel で timeout した run の sequential 再採取
RUN=0
uv run python -m erre_sandbox.cli.eval_run_golden \
  --persona kant --run-idx "$RUN" --condition natural \
  --turn-count 500 --wall-timeout-min 360 \
  --memory-db "/tmp/p3_natural_kant_run${RUN}.sqlite" \
  --output "data/eval/golden/kant_natural_run${RUN}.duckdb" --overwrite
```

### Phase 3 — eval_audit 完全性確認 (15 min、各 cell)

```bash
# 全 30 cell に対し row 数完全性確認 (3 persona × 5 run × 500 turn = 7500 focal)
uv run python -m erre_sandbox.cli.eval_audit \
  --golden-dir data/eval/golden \
  --expected-personas kant nietzsche rikyu \
  --expected-runs 0 1 2 3 4 \
  --expected-conditions stimulus natural \
  --min-focal-per-cell 500 \
  --report data/eval/golden/_audit.json
# 全 cell focal>=500、total>=focal、dialog_count > 0 を期待
# 失敗時は当該 cell を再採取
```

### Phase 4 — Mac へ rsync (ME-2 protocol、~5 min)

```bash
# CHECKPOINT を全 30 file に対し
mkdir -p /tmp/p3_rsync/
for f in data/eval/golden/*.duckdb; do
  bn=$(basename "$f")
  uv run python -c "
import duckdb
con = duckdb.connect('$f')
con.execute('CHECKPOINT')
con.close()
"
  cp "$f" "/tmp/p3_rsync/${bn}.snapshot.duckdb"
done

# md5 receipt
cd /tmp/p3_rsync/
md5 -r *.snapshot.duckdb > _checksums.txt

# data/eval/golden/_rsync_receipt.txt を起草 (P3a と同形式)
# - host_name / os / gpu / ollama_version
# - 各 cell の focal/total/dialog 行
# - md5 hash 30 行
# - Mac side rename + audit + p3_decide 手順 (next Mac セッション)

# HTTP server で Mac へ pull (P3a-finalize 2026-05-05 で validated パターン)
# G-GEAR (admin PowerShell):
#   New-NetFirewallRule -DisplayName "claude-p3-rsync" -Direction Inbound \
#     -Protocol TCP -LocalPort 8765 -Action Allow \
#     -Program "C:\Users\johnd\AppData\Local\Programs\Python\Python311\python.exe"
# G-GEAR (作業 shell):
#   cd /tmp/p3_rsync && python -m http.server 8765
#   # G-GEAR LAN IP を確認: ipconfig | findstr IPv4
#   # 2026-05-05 P3a-finalize 時は 192.168.3.85 だった (DHCP 環境次第で変動可)
# Mac (別セッション、<G-GEAR-IP> は ipconfig の値で置換):
#   for p in <30 file 名前>; do
#     curl -fOSs --connect-timeout 5 \
#       "http://<G-GEAR-IP>:8765/${p}.snapshot.duckdb"
#   done
# 完了後:
#   Remove-NetFirewallRule -DisplayName "claude-p3-rsync"
```

## Phase 5 — PR 作成 (Mac → main、~10 min)

G-GEAR 側で採取完了後:

```bash
git checkout -b feat/m9-eval-p3-golden
git add data/eval/golden/_rsync_receipt.txt data/eval/golden/_audit.json
# .duckdb は .gitignore で除外済 (data/eval/pilot/ と同方針、data/eval/golden/
# も .gitignore に追加が必要なら別途対応)
git commit -m "feat(eval): m9-eval-p3 — Golden baseline 30 cell 採取完了"
git push -u origin feat/m9-eval-p3-golden
gh pr create --base main --head feat/m9-eval-p3-golden \
  --title "feat(eval): m9-eval-p3 — Golden baseline 採取 (3 persona × 5 run × 500 turn)" \
  --body "..."  # PR #133 同形式、empirical 工数 + 失敗 cell 報告 + audit OK
```

## .gitignore 確認

`data/eval/golden/*.duckdb` が gitignored か確認、必要なら追加:

```bash
grep -E "data/eval/(pilot|golden)" .gitignore
# data/eval/pilot/*.duckdb は既存 (PR #133 で確認済)
# data/eval/golden/*.duckdb が無ければ追加 commit が必要
```

## 期待値とブロッカー予測

### 期待値

- 全 30 cell focal>=500、total>=focal × 1.5 程度 (interlocutor 寄与含)
- natural cell の dialog_count: pilot 比例で 500/30 × 14-15 ≈ **230-250 dialogs/cell**
- stimulus cell の dialog_count: pilot 比例で 500/200 × 168 ≈ **420 dialogs/cell**
- audit JSON で全 cell PASS

### ブロッカー予測 (発生確率順)

1. **natural parallel kant drain timeout** (~50% 確率): pilot 既知。fallback は
   kant のみ sequential 再採取。
2. **Ollama queue contention で per-tick latency 延長** (~30% 確率): 3-persona
   parallel で qwen3:8b が共有されるため、wall=360 min でも focal=500 に届かない
   ケース。対処: 該当 cell の `--wall-timeout-min` を 480 に拡張して再採取。
3. **memory db corruption** (~5%): natural cell の sqlite が異常終了で破損。
   対処: `--memory-db` を新規パスに切り替えて再採取。
4. **disk full** (~5%): G-GEAR 側 Ollama cache + 30 DuckDB (1MB × 30) +
   /tmp/p3_natural_*.sqlite (~50MB × 15) で ~2GB 程度、現実的でない。
5. **VRAM OOM** (~1%): qwen3:8b Q4_K_M 5.2GB / RTX 5060 Ti 16GB なので余裕。

## 失敗時の Mac との交信

各 night session 末尾に以下を Mac に報告:
- 完了 cell 数 / 30
- 失敗 cell があれば persona+run+condition+原因+試した対処
- empirical wall/cell の actual vs 予測 (線形外挿の校正用)
- 翌 night の継続計画

## post-採取 Mac セッション (本 prompt の対象外、次々セッション)

- `data/eval/golden/_rsync_receipt.txt` 受領、md5 30/30 一致確認
- atomic rename `*.snapshot.duckdb` → `*.duckdb`
- `python -m erre_sandbox.cli.eval_audit` で Mac 側完全性再確認
- Tier B 3 metric (Vendi / IPIP-NEO / Big5 ICC) を採取済 raw_dialog から計算
  (P4a が要、本 prompt の対象外)
- Tier B 結果 → ME-4 ADR partial update #4 で stage 3 close

## 参照

- P3a-finalize PR #134 (`7f3dd57` 親コミット): script v3 + Codex HIGH 3 反映
- P3a-decide v2 PR #131-#133: gating fix + natural re-capture
- ME-4 ADR (`decisions.md` L122 以降、特に "2026-05-05 partial update #3" ブロック)
- P3a-decide JSON: `data/eval/pilot/_p3a_decide.json`
- empirical wall: `data/eval/pilot/_rsync_receipt.txt`

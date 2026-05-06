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

> ## ⚠️ 2026-05-06 追記 — Phase 2 run0 incident で本 prompt は SUPERSEDED
>
> 2026-05-06 の Phase 2 run0 (3-parallel natural、wall=360 min) は 3 cell 全て
> wall budget で FAILED 終了 (focal=381/390/399、prefix censoring)。Codex
> `gpt-5.5 xhigh` 6 回目 review が Claude 単独案の HIGH 4 件を切出
> (`codex-review-phase2-run0-timeout.md` verbatim)。
>
> **本 prompt の §Phase 2 採取と §ブロッカー予測 item 2 は不正確** (wall=360 を
> 既定値、480 へ拡張で対応可と記載) のため、現状では **そのまま使わない**。
> 正しい運用は ME-9 ADR (`decisions.md`) と `cli-fix-and-audit-design.md` を
> 参照:
>
> 1. **CLI fix + `eval_audit` CLI** を別タスク (`m9-eval-cli-partial-fix`) で
>    実装・merge してから本 launch を再開
> 2. CLI fix merge 後、まず **run1 を 600 min single calibration** (kant のみ
>    1 cell、3-parallel でない 1-only)、120/240/360/480 min で focal/total
>    を sample。これで run2-4 の wall budget を empirical 確定
> 3. run0 partial は **primary 5 runs matrix から外す**、`data/eval/partial/`
>    隔離 + `partial_capture=true` sidecar 付き diagnostic 専用
> 4. run0 を 500 focal で **再採取**、CLI fix の return code 0 を audit gate
>    の必須条件に
>
> 本 prompt 全体の改訂は CLI fix PR merge 後の Mac セッションで実施
> (`g-gear-p3-launch-prompt-v2.md` 起票予定)。
>
> ## 🛠 2026-05-06 追記 #2 — Phase 3 audit セクションは本 PR で更新済
>
> `m9-eval-cli-partial-fix` PR は `eval_audit` CLI を新設し、`eval_run_golden`
> の return code 体系 (0/2/3) と sidecar `<output>.duckdb.capture.json` v1
> を実装した。本 prompt §Phase 3 のコマンド例とフラグは新 contract に書き換え
> 済 (旧 `--golden-dir` / `--expected-personas` 等は廃止、`--duckdb-glob` +
> `--focal-target` + `--report-json` の 3 flag に集約)。Phase 1 / Phase 2 採取
> 部分の wall budget / parallel 戦略の改訂は v2 prompt で扱う。

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

### Phase 3 — eval_audit 完全性確認 (10 min、batch mode)

`m9-eval-cli-partial-fix` (ME-9 ADR、CLI fix PR 適用後) で実装された
`eval_audit` CLI は以下を機械検証する:

- **sidecar `<output>.duckdb.capture.json` の存在** (return 4 = legacy 互換区別)
- **DuckDB row 数 vs sidecar の整合性** (return 5 = `total_rows` /
  `focal_observed` mismatch)
- **同一 run 性** (return 5 = `SELECT DISTINCT run_id` が
  `f"{persona}_{condition}_run{run_idx}"` と不一致、Codex H1 反映)
- **status × focal_target** (return 0 = PASS、return 6 = incomplete または
  partial without `--allow-partial`)

```bash
# 全 30 cell batch audit (新 contract)
uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/golden/*_run*.duckdb' \
  --focal-target 500 \
  --report-json data/eval/golden/_audit.json
# overall_exit_code = max(single-cell exit code) を返す。
# 0 → 全 cell PASS、再採取不要
# 4 → どこかに sidecar 欠損 (legacy 経由?)、当該 cell を再採取
# 5 → row count / run_id mismatch、当該 cell を再採取
# 6 → focal<500 または partial 残り、当該 cell を `--wall-timeout-min` 拡張で再採取
```

**partial cell の diagnostic mode**:

```bash
# Phase 2 run0 incident のような partial 群を別運用したい場合
uv run python -m erre_sandbox.cli.eval_audit \
  --duckdb-glob 'data/eval/partial/*_run0.duckdb' \
  --focal-target 500 \
  --allow-partial \
  --report-json data/eval/partial/_audit.json
# partial を return 0 として通すが primary 5-runs matrix からは外す。
# `data/eval/partial/` 隔離の運用は ME-9 ADR どおり。
```

`eval_run_golden` 側の return code 体系 (新):

| code | 意味 | rename | sidecar |
|---|---|---|---|
| 0 | complete (focal_target 到達) | allow | status=complete |
| 2 | fatal (DuckDB INSERT / Ollama / drain timeout / runtime exception / focal 未達) | refuse | status=fatal |
| 3 | partial (wall timeout、focal < target) | allow | status=partial |
| 130 | Ctrl-C | (現状維持) | (現状維持) |

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
2. **Ollama queue contention で per-tick latency 延長** (~~30%~~ **2026-05-06
   実測 100% 発生**): 3-persona parallel で qwen3:8b が共有されるため、
   wall=360 min でも focal=500 に届かない (run0 で 3/3 cell が focal=381-399
   prefix censoring)。**~~480 拡張~~ も Codex H1 で計算根拠が破綻** (`65*8*0.85=442`
   < 500)、**600 min 最低ライン**。対処は ME-9 ADR の通り CLI fix + run1
   calibration → run2-4 budget empirical 確定の 3 段で進める。
   詳細: `decisions.md` ME-9 / `blockers.md` "active incident: Phase 2 run0
   wall-timeout (2026-05-06)" / `cli-fix-and-audit-design.md`
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

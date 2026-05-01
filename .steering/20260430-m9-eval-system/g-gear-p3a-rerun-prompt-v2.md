# G-GEAR セッション用プロンプト v2 — m9-eval-p3a-decide v2 後の natural 再々採取

> このファイルは Mac セッション (2026-05-01 P3a-decide v2) 末尾で起草。
> G-GEAR (Windows / RTX 5060 Ti 16GB / Ollama 0.22.0) で /clear 後に
> 全文をコピペして送る前提。Mac → G-GEAR の sync は user が事前に
> `git fetch && git checkout main && git pull` で完了している想定。
> v1 (`g-gear-p3a-rerun-prompt.md`) の **後続**で、v1 fix (zone bypass) は
> ship 済 / 機能した一方、v1 の Phase A 採取で別の dominant gate
> (cooldown × cognition_period の wall 換算) が露呈した PR #131 の対応。

---

タスク 20260430-m9-eval-system Phase P3a (natural のみ再々採取) を G-GEAR で
実行する。Mac セッション (2026-05-01) で **fix v2** (cooldown × cognition_period
の dominant gate を `COOLDOWN_TICKS_EVAL=5` で解消、wall default 90→120 min) が
完了 (PR `feature/m9-eval-p3a-decide-v2` で commit、ME-8 amendment、Codex
gpt-5.5 xhigh review HIGH 2 / MEDIUM 2 / LOW 1 全反映)。本セッションは fix v2
版で natural 3 cell を採取し、ratio 確定の data 収集を完成させる。

# 前 G-GEAR セッション (2026-05-01) の Phase A 失敗根拠

PR #131 G-GEAR Phase A 単独 sanity (kant_natural、wall 10 min):
- focal=6 / total=18 / dialogs=3 (gating fix の半分は機能、Nietzsche starve 解消)
- tick=1-5 内で 18 utterances 発生、tick=5 以降 8 min 0 admit
- empirical: 600 s wall で max(world_tick)=5 → cognition_period ≈ **120 s/tick**
- 実効 cooldown = COOLDOWN_TICKS=30 × 120 s = **60 min wall** ⇒ 10 min wall 内
  再 admit 物理的不可能

→ design v1 §2 で「△ 補助」棄却した仮説 B を ◎ 主因に再格上げ確定。

# 前 Mac セッション (2026-05-01 fix v2) の到達点

- **`COOLDOWN_TICKS_EVAL: ClassVar[int] = 5`** を `InMemoryDialogScheduler` に追加、
  `_effective_cooldown()` helper 経由で eval mode のみ cooldown 短縮 (live mode
  COOLDOWN_TICKS=30 は完全不変)
- **`_DEFAULT_WALL_TIMEOUT_MIN`**: 90.0 → **120.0 min** に拡張 (Codex Q3 verdict
  反映、conservative estimate で focal=24/cell 下限確保)
- ME-8 ADR を **二度目の partial-update** (2026-05-01 amendment block):
  re-open 条件発火を明記、eval mode 固有の "eval cadence calibration" 概念を
  確定 (live natural cadence と区別)
- test rewrite 2 件 (`test_eval_natural_mode_uses_reduced_cooldown` /
  `test_eval_natural_mode_sustains_admission_after_initial_burst` を
  `COOLDOWN_TICKS_EVAL` 参照に書き換え) + 新規 4 件 (helper 2 + live behavior 1 +
  CLI default 1)、full suite **1251 passed / 31 skipped / 27 deselected**
  (baseline 1248 から default CI に +3、CLI test 1 件は eval marker で deselect)
- Codex `gpt-5.5 xhigh` independent review v2: HIGH=2 / MEDIUM=2 / LOW=1、
  Verdict: revise → 全反映後 ship 相当。HIGH-1 (wall default 不整合) と
  HIGH-2 (既存 cooldown test rewrite) は本 PR の改訂で解消、MEDIUM-1
  (ME-8 explicit amendment) / MEDIUM-2 (conservative estimate primary 化) は
  design-v2.md / decisions.md ME-8 amendment block で記載

# 本セッションで実行すること

**fix v2 適用版で natural 3 cell を採取して Mac へ rsync する**。stimulus は
PR #129 採取済 (focal=198 で完走) を引き継ぐので再採取しない。

# まず Read (この順)

1. `.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md`
   (5 + 3 案比較 + α+β 採用 + Codex review 反映)
2. `.steering/20260430-m9-eval-system/decisions.md` ME-8 amendment 2026-05-01
   (cooldown × cognition_period、`COOLDOWN_TICKS_EVAL=5`、wall default 120 min、
   eval cadence calibration 概念)
3. `.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md`
   (verbatim、Verdict: revise、HIGH/MEDIUM/LOW + Q1-Q8)
4. `.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md` (PR #131 失敗
   レポート、empirical cognition_period 120 s/tick の根拠)
5. `src/erre_sandbox/integration/dialog.py:89-115` (`COOLDOWN_TICKS` /
   `COOLDOWN_TICKS_EVAL` 定数 + docstring) と `:395-410` (`_effective_cooldown()`)
6. `src/erre_sandbox/cli/eval_run_golden.py:122-135` (`_DEFAULT_WALL_TIMEOUT_MIN`
   = 120.0 + docstring)

# Pre-condition

```bash
cd ~/ERRE-Sand\ Box
git fetch origin
git checkout main && git pull --ff-only origin main   # fix v2 が main 入りした想定
# あるいは feature ブランチの場合:
# git checkout feature/m9-eval-p3a-decide-v2 && git pull
git log --oneline -5  # ME-8 amendment 2026-05-01 fix v2 が含まれることを確認

uv sync --all-extras
nvidia-smi
ollama list  # qwen3:8b と nomic-embed-text:latest 存在確認

# 前回 Phase A の .tmp file は保持ならアーカイブ、削除してもよい
ls -lh data/eval/pilot/*_natural_*.duckdb*
mkdir -p data/eval/pilot/_phase_a_archive
mv data/eval/pilot/*_natural_*.duckdb* data/eval/pilot/_phase_a_archive/ 2>/dev/null || true
mv data/eval/pilot/*_natural_*.log data/eval/pilot/_phase_a_archive/ 2>/dev/null || true

# stimulus は無傷 (PR #129)
ls -lh data/eval/pilot/*_stimulus_*.duckdb   # 3 file あるはず

rm -f /tmp/p3a_natural_*.sqlite

# 修正 Confirm (4 新規 + 2 rewrite すべて pass)
uv run pytest tests/test_integration/test_dialog_eval_natural_mode.py -q
# → 15 passed (12 既存 + 3 新規) を確認
uv run pytest tests/test_cli/test_eval_run_golden.py::test_wall_timeout_min_default_is_120 -q
# → 1 passed を確認
```

# 採取手順

## Phase A: 単独セルで wall=120 min sanity (fix v2 効果確認)

並列前に 1 cell 単独で 120 min 走らせて effect を確認する:

```bash
uv run python -m erre_sandbox.cli.eval_run_golden \
  --persona kant --condition natural --run-idx 0 \
  --turn-count 30 --wall-timeout-min 120 \
  --output data/eval/pilot/kant_natural_run0.duckdb \
  --overwrite 2>&1 | tee data/eval/pilot/kant_natural_run0.log
```

**Conservative estimate 期待値** (design-v2.md §5.1 反映):
- focal_rows: 25-35 (target=30、conservative 下限 24/cell)
- total_rows: ~75-105 (focal + interlocutor 混合)
- dialog_count: ~12-20 (cycle ~5 × 3 pair で散発)
- wall: 90-120 min (cognition_period 120 s/tick × ~5 cycle)
- max(world_tick): 50+ (cooldown=5 ticks × ~10 cycles 進行)

**Phase A guard** (`focal<25` 判定):
- focal>=25 → Phase B (3 cell parallel) に進む
- focal<25 → **stop** + Mac セッション (P3a-decide v3 起こす可能性) へ報告
  - decisions.md ME-8 amendment §re-open 条件 1 項目目発火: 別 dominant gate
    (prob 0.25 variance / 推論 deadlock / world_tick 進行停止) を再特定

**diagnostic log** (Phase A 失敗時に手動確認):
```bash
# tick 進行確認
grep "world_tick" data/eval/pilot/kant_natural_run0.log | tail -20
# admit / close cycle 確認
grep -E "DialogInitiate|DialogClose" data/eval/pilot/kant_natural_run0.log | wc -l
# inter-arrival
sqlite3 data/eval/pilot/kant_natural_run0.duckdb \
  "SELECT created_at FROM dialog ORDER BY created_at LIMIT 30;" 2>/dev/null \
  || duckdb data/eval/pilot/kant_natural_run0.duckdb \
       "SELECT created_at FROM dialog ORDER BY created_at LIMIT 30;"
```

## Phase B: 3 cell parallel 採取 (Phase A guard pass 後)

```bash
parallel --line-buffer --jobs 3 ::: \
  "uv run python -m erre_sandbox.cli.eval_run_golden \
     --persona kant --condition natural --run-idx 0 \
     --turn-count 30 --wall-timeout-min 120 \
     --output data/eval/pilot/kant_natural_run0.duckdb --overwrite \
     2>&1 | tee data/eval/pilot/kant_natural_run0.log" \
  "uv run python -m erre_sandbox.cli.eval_run_golden \
     --persona nietzsche --condition natural --run-idx 0 \
     --turn-count 30 --wall-timeout-min 120 \
     --output data/eval/pilot/nietzsche_natural_run0.duckdb --overwrite \
     2>&1 | tee data/eval/pilot/nietzsche_natural_run0.log" \
  "uv run python -m erre_sandbox.cli.eval_run_golden \
     --persona rikyu --condition natural --run-idx 0 \
     --turn-count 30 --wall-timeout-min 120 \
     --output data/eval/pilot/rikyu_natural_run0.duckdb --overwrite \
     2>&1 | tee data/eval/pilot/rikyu_natural_run0.log"
```

**期待値** (3 並列、Phase A の単独値が下振れする可能性込み):
- 各 cell focal=25-35 / total=~75-105 / dialogs=~12-20
- total wall: 90-150 min (Ollama 内 queueing で単独より遅化、starvation は無いはず)
- 3 cell 全て `fatal_error` なし

`parallel` が無ければ tmux 3 pane で起動。`OLLAMA_NUM_PARALLEL=2` で OOM 抑制
の余地あり。

## 完走確認 + summary 再生成

```bash
ls -lh data/eval/pilot/*_natural_*.duckdb       # 3 file 揃ってる
uv run python scripts/p3a_summary.py            # _summary.json 再生成
git diff data/eval/pilot/_summary.json          # natural 3 cell が focal>=25 を確認
```

**ガード**: focal=0 や focal<25 (=Phase A guard と同) なら gating bug 残存 or
別 dominant gate。stop → Mac セッションへ報告 + duckdb 保持。

# Mac へ rsync (ME-2 protocol、v1 と同手順)

```bash
mkdir -p /tmp/p3a_rsync_v2
for f in data/eval/pilot/*_natural_*.duckdb; do
  cp "$f" "/tmp/p3a_rsync_v2/$(basename $f).snapshot.duckdb"
done
md5sum /tmp/p3a_rsync_v2/*.duckdb > /tmp/p3a_rsync_v2/_checksums.txt
ls -lh /tmp/p3a_rsync_v2/

# stimulus も再 rsync (Mac には現在ない)
for f in data/eval/pilot/*_stimulus_*.duckdb; do
  cp "$f" "/tmp/p3a_rsync_v2/$(basename $f).snapshot.duckdb"
done
md5sum /tmp/p3a_rsync_v2/*.duckdb > /tmp/p3a_rsync_v2/_checksums.txt

rsync -av /tmp/p3a_rsync_v2/ <MAC_HOST>:~/ERRE-Sand_Box/data/eval/pilot/
# user_email mmiura.network@gmail.com から MAC_HOST を確認
```

# 完走後の commit + PR

```bash
cat > data/eval/pilot/_rsync_receipt.txt <<EOF
# P3a-decide v2 rerun rsync receipt
status: completed — natural re-capture after fix v2 (cooldown × cognition_period)
rsync_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
mac_destination: ~/ERRE-Sand_Box/data/eval/pilot/

# Capture host
host_name: G-GEAR
os: Windows 11 Home
gpu: NVIDIA RTX 5060 Ti 16GB
ollama_version: 0.22.0
ollama_models: qwen3:8b (Q4_K_M, 5.2GB), nomic-embed-text:latest

# Files transferred (checksums match _checksums.txt)
$(cat /tmp/p3a_rsync_v2/_checksums.txt)

# Fix verification (post fix v2)
prior_phase_a:  kant=6/18/3 (cooldown gated), wall 10 min sanity timeout
post_fix_v2:    kant=~30, nietzsche=~30, rikyu=~30 (COOLDOWN_TICKS_EVAL=5, wall 120 min)
empirical_cognition_period: ~120 s/tick (qwen3:8b Q4_K_M on RTX 5060 Ti)
EOF

git add data/eval/pilot/_summary.json data/eval/pilot/_rsync_receipt.txt
git commit -m "data(eval): m9-eval-p3a natural re-capture after fix v2 (cooldown × cognition_period)"
gh pr create --title "data(eval): m9-eval-p3a natural re-capture v2 (post fix v2)" --body "..."
```

# 想定 hazard

- **wall 120 min × 3 並列 = 6h overnight 採取に伸び得る**: Ollama internal
  queueing で 1 modelあたり serial、3 cell 並列でも実質 wall は 120-180 min 想定。
  6h 超に達した場合、`OLLAMA_NUM_PARALLEL=2` で OOM 圧抑える + 1 cell 逐次運用 (ι 案)
  検討 (decisions.md ME-8 amendment §re-open 条件 3 項目目)
- **prob 0.25 variance での下振れ**: conservative estimate で focal=24/cell が
  下限、運悪く 16-20 で着地する cell があり得る。Phase B で 1 cell が <25 でも
  他 2 cell が >=25 なら Mac で部分 ratio 計算可
- **Phase A guard 再発火**: もし fix v2 後も focal<25 なら、別 dominant gate (γ
  prob 上げ / ζ wall-time cooldown / 推論 deadlock 等) を Mac セッションで切出
- **Windows cp932 codec**: 前回観測した
  `tests/test_architecture/test_layer_dependencies.py` 事象は本タスクに無関係、
  `-m "not godot and not eval"` で deselect 済

# 守るべき制約 (CLAUDE.md 由来)

- main 直 push 禁止、`feature/m9-eval-p3a-natural-recapture-v2` で作業
- planning purity: 本セッションは **採取のみ**、コード変更しない
  (fix v2 は前 Mac セッションで完了済、本セッションは run + rsync)
- 50% ルール、context 50% 超で /smart-compact

# 完了条件

- [ ] Phase A 単独 sanity で focal>=25 達成 (= fix v2 effective 確認)
- [ ] Phase B 3 persona × natural cell すべて focal_rows >= 25 で完走
- [ ] `_summary.json` に修正後の数値が反映 + commit
- [ ] DuckDB rsync 完了 + `_rsync_receipt.txt` 更新
- [ ] PR 作成 + Mac セッション (P3a-decide finalization) への hand-off note

# Hand-off to Mac

採取 + rsync 完了後、Mac セッションで以下を run して ratio 確定:

```bash
# Mac 側
uv run python scripts/p3a_decide.py
# → data/eval/pilot/_p3a_decide.json 出力
# → ME-4 ADR を実測値で二度目の Edit (元 ratio 200/300 vs alternative の
#   bootstrap CI width 比較)
```

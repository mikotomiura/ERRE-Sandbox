# G-GEAR セッション用プロンプト — m9-eval-system P3a-decide 後の natural 再採取

> このファイルは Mac セッション (2026-05-01 P3a-decide) 末尾で起草。
> G-GEAR (Windows / RTX 5060 Ti 16GB / Ollama 0.22.0) で /clear 後に
> 全文をコピペして送る前提。Mac → G-GEAR の sync は user が事前に
> `git fetch && git checkout main && git pull` で完了している想定。

---

タスク 20260430-m9-eval-system Phase P3a (natural のみ再採取) を G-GEAR で
実行する。前セッション (Mac, 2026-05-01) で **M5/M6 natural runtime gating
bug** の root-cause analysis + fix が完了 (`feature/m9-eval-p3a-decide` ブランチ
で commit、ME-8 ADR、Codex Verdict: ship)。本セッションは修正版で natural
3 cell を再採取し、ratio 確定の data 収集を完成させる。

# 前セッション (Mac, 2026-05-01) の到達点

- M5/M6 natural runtime gating bug の **root-cause** = LLM-driven `destination_zone`
  + `personas/{nietzsche,rikyu}.yaml` の `preferred_zones` に AGORA 不在 +
  `ERRE_ZONE_BIAS_P=0.2` default → 53% per-tick zone drift →
  `_iter_colocated_pairs` が 0 pair → 初動 burst 後 admit 完全停止
- 修正: `InMemoryDialogScheduler.eval_natural_mode: bool = False` flag を追加。
  True で zone-equality / reflective-zone 制約を bypass、cooldown / probability /
  timeout / self-reject / double-open-reject の invariant は両 mode で active のまま
- `cli/eval_run_golden.py:capture_natural` で `eval_natural_mode=True` を opt-in
- 12 unit test (Red→Green 転換 + 5 invariant + 構築時 reject) 全 PASS、
  既存 1221 PASS は default False で完全互換 (full suite 1248 PASS)
- Codex `gpt-5.5 xhigh` independent review: HIGH=0 / MEDIUM=0 / LOW=2、
  両 LOW (両 flag reject + docstring "ordered" → "unordered") は反映済、
  Verdict: **ship**
- `bootstrap_ci.py` (P5 prep を前倒し) + `scripts/p3a_decide.py` も Mac で起草、
  rsync 完了後に Mac セッションで run

# 本セッションで実行すること

**natural 3 cell を再採取して Mac へ rsync する。stimulus は既に focal=198 で完走済
なので再採取しない**。

# まず Read (この順)

1. `.steering/20260430-m9-eval-system/design-natural-gating-fix.md`
   - 仮説 4 件 + reimagine 代案 4 案 + 採用判断
2. `.steering/20260430-m9-eval-system/decisions.md` ME-4 (partial-update) + ME-8 (新規)
3. `.steering/20260430-m9-eval-system/tasklist.md` §P3a + §P3a-decide
4. `.steering/20260430-m9-eval-system/codex-review-natural-gating.md` (Codex verbatim、
   Verdict: ship、LOW-1/LOW-2 反映済)
5. `src/erre_sandbox/integration/dialog.py:79-200` (`InMemoryDialogScheduler` の新 flag
   と invariant コメント)
6. `src/erre_sandbox/cli/eval_run_golden.py:920-960` (`capture_natural` の scheduler
   構築箇所、`eval_natural_mode=True` opt-in)
7. `data/eval/pilot/_summary.json` (前回 stimulus 3 cell の baseline 数値、natural は
   focal=0/6/6 で stalled の記録)

# Pre-condition

```bash
cd ~/ERRE-Sand\ Box
git fetch origin
git checkout main && git pull --ff-only origin main   # gating fix が main 入りした想定
# あるいは feature ブランチの場合:
# git checkout feature/m9-eval-p3a-decide && git pull
git log --oneline -5  # ME-8 ADR fix が含まれることを確認

uv sync --all-extras   # eval extras 含む heavy ML deps
nvidia-smi             # VRAM 余裕確認 (qwen3:8b Q4_K_M で ~5.5GB)
ollama list            # qwen3:8b と nomic-embed-text:latest 存在確認

# 既存 stimulus duckdb は保持
ls -lh data/eval/pilot/*_stimulus_*.duckdb   # 3 file あるはず

# 既存 natural duckdb は **削除** (前回 partial データを混入させない)
rm -f data/eval/pilot/*_natural_*.duckdb data/eval/pilot/*_natural_*.duckdb.tmp
rm -f /tmp/p3a_natural_*.sqlite

# 修正 Confirm
uv run pytest tests/test_integration/test_dialog_eval_natural_mode.py -q
# → 12 passed を確認
```

# 採取手順

## 単独セルで wall-clock の baseline を取る (修正効果の sanity check)

並列を始める前に、**1 cell だけ単独で 5-10 min 走らせて修正効果を確認する**:

```bash
uv run python -m erre_sandbox.cli.eval_run_golden \
  --persona kant --condition natural --run-idx 0 \
  --turn-count 30 --wall-timeout-min 10 \
  --output data/eval/pilot/kant_natural_run0.duckdb \
  --overwrite
```

**期待値** (修正後):
- focal_rows: 30 (target 完走) ※ 30 turn で打ち切り
- total_rows: ~90 (focal + interlocutor の混合)
- dialog_count: ~5-15 (cooldown=30 tick × admit prob=0.25 で散発的に admit)
- wall: 5-8 min 程度

**修正前との比較**:
- 修正前 kant: focal=6 / total=12 / dialogs=2 (8 min wall, 0 progress past initial burst)
- 修正後 kant: focal=30 / total=~90 / dialogs=~10 (5-8 min wall) **が達成できれば fix 有効**

達成できない場合は **次の手順に進まず Mac セッションへ報告**。fix が不完全か、
別の gating bug が併発している可能性 (decisions.md ME-8 §re-open 条件参照)。

## 並列で 3 cell 採取

baseline 確認 OK なら 3 persona × natural を **並列で** 採取:

```bash
mkdir -p data/eval/pilot
parallel --line-buffer --jobs 3 ::: \
  "uv run python -m erre_sandbox.cli.eval_run_golden \
     --persona kant --condition natural --run-idx 0 \
     --turn-count 30 --wall-timeout-min 60 \
     --output data/eval/pilot/kant_natural_run0.duckdb --overwrite" \
  "uv run python -m erre_sandbox.cli.eval_run_golden \
     --persona nietzsche --condition natural --run-idx 0 \
     --turn-count 30 --wall-timeout-min 60 \
     --output data/eval/pilot/nietzsche_natural_run0.duckdb --overwrite" \
  "uv run python -m erre_sandbox.cli.eval_run_golden \
     --persona rikyu --condition natural --run-idx 0 \
     --turn-count 30 --wall-timeout-min 60 \
     --output data/eval/pilot/rikyu_natural_run0.duckdb --overwrite"
```

**期待値** (3 並列):
- 各 cell の focal=30 / total=~90 / dialogs=~5-15
- total wall: 30-60 min (Ollama 内の queueing で単独より遅い、starvation は無いはず)
- 3 cell 全て ``fatal_error`` なし

`parallel` が無ければ tmux 3 pane で起動。Ollama 0.22.0 は内部 queue で 1
モデルあたり 1 並列なので、cognition + dialog turn の総コール量で wall は
左右される。

## 完走確認 + summary 再生成

```bash
ls -lh data/eval/pilot/*_natural_*.duckdb       # 3 file 揃ってる
uv run python scripts/p3a_summary.py            # _summary.json を再生成
git diff data/eval/pilot/_summary.json          # natural 3 cell が focal=30 になることを確認
```

**ガード**: focal=0 や focal<10 なら gating bug が再発している。stop して
Mac セッションへ報告 + duckdb を **保持** (rsync しない、deletion しない)。

# Mac へ rsync (ME-2 protocol)

完走確認 OK なら手動 rsync を実行:

```bash
# G-GEAR 側
mkdir -p /tmp/p3a_rsync
for f in data/eval/pilot/*_natural_*.duckdb; do
  cp "$f" "/tmp/p3a_rsync/$(basename $f).snapshot.duckdb"
done
md5sum /tmp/p3a_rsync/*.duckdb > /tmp/p3a_rsync/_checksums.txt
ls -lh /tmp/p3a_rsync/

# stimulus も再 rsync (Mac には現在ない、_summary.json 経由のみ)
for f in data/eval/pilot/*_stimulus_*.duckdb; do
  cp "$f" "/tmp/p3a_rsync/$(basename $f).snapshot.duckdb"
done
md5sum /tmp/p3a_rsync/*.duckdb > /tmp/p3a_rsync/_checksums.txt

# rsync to Mac (user supplies MAC_HOST)
rsync -av /tmp/p3a_rsync/ <MAC_HOST>:~/ERRE-Sand_Box/data/eval/pilot/
# user_email mmiura.network@gmail.com から MAC_HOST を確認
```

# 完走後の commit + PR

```bash
# _summary.json と _rsync_receipt.txt のみ commit (.duckdb は .gitignore)
# rsync 完了後の receipt も書き直し:
cat > data/eval/pilot/_rsync_receipt.txt <<EOF
# P3a-decide rerun rsync receipt
status: completed — natural re-capture after eval_natural_mode fix
rsync_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
mac_destination: ~/ERRE-Sand_Box/data/eval/pilot/

# Capture host
host_name: G-GEAR
os: Windows 11 Home
gpu: NVIDIA RTX 5060 Ti 16GB
ollama_version: 0.22.0
ollama_models: qwen3:8b (Q4_K_M, 5.2GB), nomic-embed-text:latest

# Files transferred (checksums match _checksums.txt)
$(cat /tmp/p3a_rsync/_checksums.txt)

# Fix verification
prior_state: kant=6/12 (gated), nietzsche=0/0 (starved), rikyu=6/18 (gated)
post_fix:    kant=30/~90, nietzsche=30/~90, rikyu=30/~90 (eval_natural_mode=True)
EOF

git add data/eval/pilot/_summary.json data/eval/pilot/_rsync_receipt.txt
git commit -m "data(eval): m9-eval-p3a natural re-capture after gating fix"
gh pr create --title "data(eval): m9-eval-p3a natural re-capture (post gating fix)" --body "..."
```

# 想定 hazard

- **Ollama OOM**: qwen3:8b で 3 並列 cognition + 3 並列 dialog turn が同時発火すると
  16GB VRAM 圧迫の可能性。`OLLAMA_NUM_PARALLEL=2` を環境変数で抑えて再起動
- **Windows 副次 fail**: 前回観測した cp932 codec エラー
  (`tests/test_architecture/test_layer_dependencies.py`) は本タスクで無関係なので
  `-m "not godot and not eval"` で deselect
- **rsync host name**: user の Mac の hostname を session 開始時に聞く
- **modeling 想定外の長時間化**: cooldown=30 tick × cognition_period=10s = 5 min 単位
  で admit が散発する設計。focal 30 達成に 30-60 min 必要は織り込み済

# 守るべき制約 (CLAUDE.md 由来)

- main 直 push 禁止、`feature/m9-eval-p3a-natural-recapture` で作業
- planning purity: 本セッションは **採取のみ**、コード変更は **しない**
  (gating fix は前 Mac セッションで完了済、本セッションは run + rsync)
- 50% ルール、context 50% 超で /smart-compact

# 完了条件

- [ ] 3 persona × natural cell すべて focal_rows >= 25 で完走
- [ ] `_summary.json` に修正後の数値が反映 + commit
- [ ] DuckDB rsync 完了 + `_rsync_receipt.txt` 更新
- [ ] PR 作成 + Mac セッション (P3a-decide finalization) への hand-off note

# Hand-off to Mac

採取 + rsync 完了後、Mac セッションで以下を run して ratio 確定:

```bash
# Mac 側
uv run python scripts/p3a_decide.py
# → data/eval/pilot/_p3a_decide.json 出力
# → ME-4 ADR を実測値で二度目の Edit
```

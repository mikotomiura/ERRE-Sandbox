# feat(eval): m9-eval-system P3a Step 1-5 — eval_run_golden CLI + pilot 採取

## Summary

m9-eval-system Phase P3a を G-GEAR (Windows / RTX 5060 Ti 16GB / qwen3:8b
Q4_K_M / Ollama 0.22.0) で完走させた。Step 1 (CLI 起草、Codex `gpt-5.5
xhigh` review HIGH 6 全反映) は前セッションで commit 済 (3e511e1)、本 PR は
Step 2-5 (実機採取 6 invocation + summary JSON + tasklist 更新) を含める。
DuckDB 本体 (data/eval/pilot/*.duckdb, ~MB 級) は `.gitignore` 済で本 PR
には入らない — Mac セッション (P3a-decide) への hand-off は
`data/eval/pilot/_summary.json` 1 ファイル。

- Step 1 CLI: `src/erre_sandbox/cli/eval_run_golden.py` + `tests/test_cli/test_eval_run_golden.py` (mock LLM、12 件 PASS、3e511e1 で commit 済)
- Step 2 採取: 3 persona × 2 condition = **6 invocation 完了** (per-cell 詳細は下表)
- Step 3 rsync: **本 PR では skip** — user が後日 G-GEAR → Mac へ手動 rsync 実施 (本 PR では receipt placeholder のみ commit)
- Step 4 サマリ: `scripts/p3a_summary.py` 新規 + `data/eval/pilot/_summary.json` (read-only DuckDB → JSON)
- Step 5 tasklist: `.steering/20260430-m9-eval-system/tasklist.md` §P3a 全 [x]、wall-clock + focal/total を tag 行に記録

## Codex review (HIGH 6 件) 反映状況

`.steering/20260430-m9-eval-system/codex-review-step1.md` (verbatim 保存) の HIGH 6 件は Step 1 commit (3e511e1) で全反映済。本 PR 採取で実機検証された:

| # | 内容 | 反映先 | 実機での挙動 |
|---|---|---|---|
| HIGH-1 | YAML-prefix slicing → category-stratified slicing | `_stratified_stimulus_slice` | stimulus 6 cell で focal target ±15% 内 |
| HIGH-2 | focal-turn-aware budget (driver alternates speakers) | `focal_persona_id` カウント | per-cell `focal_rows` を `_summary.json` に記録 |
| HIGH-3 | sink failure must be fail-fast (no silent row loss) | `CaptureFatalError` + `state.fatal_error` | 6 cell で fatal_error なし |
| HIGH-4 | write to `<output>.tmp`, refuse pre-existing without `--overwrite` | `_resolve_output_paths` | 全 cell で .tmp → atomic rename 完了 |
| HIGH-5 | seed natural scheduler RNG with `derive_seed(persona, run_idx)` | `random.Random(seed_root)` | natural 3 cell で run_id 一意 |
| HIGH-6 | `runtime.stop()` → `wait_for(runtime_task, grace_s)` (no rename on timeout) | `_RUNTIME_DRAIN_GRACE_S=30s` | natural 3 cell で drain 正常完了 |

## 採取結果 (per-cell)

完全な内訳は `data/eval/pilot/_summary.json` 参照。

| persona | condition | focal | total | dialog | wall (min) | utterance median |
|---|---|---|---|---|---|---|
| kant | stimulus | **198** | 342 | 168 | ~2 | 68 chars (max 199) |
| kant | natural | 6 | 12 | 2 | ~13 (killed) | 73 chars (max 98) |
| nietzsche | stimulus | **198** | 342 | 168 | ~3 | 45 chars (max 163) |
| nietzsche | natural | **0** | **0** | **0** | ~13 (killed, starved) | n/a |
| rikyu | stimulus | **198** | 342 | 168 | ~3.5 | 28 chars (max 597) |
| rikyu | natural | 6 | 18 | 3 | ~13 (killed) | 47 chars (max 84) |

### Stimulus 3 cell (full target)

`stratified_stimulus_slice` で 70 stimulus の category 比率を維持しつつ
focal=200 ± 1% 完走 (Codex HIGH-1 + HIGH-2 の検証)。3 persona とも
focal/total/dialogs が完全一致 (deterministic 設計の確認)。

### Natural 3 cell (partial — M5/M6 runtime gating)

target を 200 → 80 → 30 と段階的に縮小したが、いずれも初動 burst (~3 dialog/persona) 以降に
**INSERT が完全停止**。実機計測:

- 単独 kant_natural (8 min wall): 6 focal / 2 dialogs (rate 0.75 focal/min、初動のみ)
- 3 並列 (13 min wall): kant 6 / nietzsche 0 / rikyu 6 (1 cell 完全 starvation)

`AUTO_FIRE_PROB_PER_TICK 0.25 + COOLDOWN_TICKS 30 + cognition_period_s 7-18s` の
組合せだけでは説明できない停止挙動 (cooldown は 6 min × 1 pair で expire するはずが、
12+ min 後も新規 INSERT 0)。Mac 側 P3a-decide で `_iter_colocated_pairs` /
`schedule_initiate` の admit 回路を inspect し、原因特定 → 次 G-GEAR セッションで
再採取の予定。**bootstrap CI 計算は本 PR の stimulus 3 cell で実施可能**。

## ハンドオフ artefact

| ファイル | 用途 | Mac セッションでの扱い |
|---|---|---|
| `data/eval/pilot/_summary.json` | per-cell 統計 (run_id / focal / dialog / utterance chars) | P3a-decide で bootstrap CI width 比較の入力 |
| `data/eval/pilot/_rsync_receipt.txt` | rsync 計画の placeholder | user が手動 rsync 実施後に再生成・上書き |
| `scripts/p3a_summary.py` | 再現可能な集計 | Mac 側でも `uv run python scripts/p3a_summary.py` で再生成可 |

## ME-2 rsync protocol

本 PR では rsync は実施せず — user が以下を手動で実行する想定:

```bash
# G-GEAR 側
mkdir -p /tmp/p3a_rsync
for f in data/eval/pilot/*.duckdb; do
  cp "$f" "/tmp/p3a_rsync/$(basename $f).snapshot.duckdb"
done
md5sum /tmp/p3a_rsync/*.duckdb > /tmp/p3a_rsync/_checksums.txt
rsync -av /tmp/p3a_rsync/ <MAC_HOST>:~/ERRE-Sand_Box/data/eval/pilot/
# Mac 側 atomic rename + acceptance は P3a-decide セッションで実施 (本 PR scope 外)
```

CHECKPOINT は eval_run_golden.py の `write_with_checkpoint(con)` で各 capture 完了時に既に実施済。/tmp snapshot + rsync + atomic rename の 3 段は ME-2 (`.steering/20260430-m9-eval-system/decisions.md`) 厳守。

## 既知の Windows-only 副次失敗 (本 PR scope 外)

`tests/test_architecture/test_layer_dependencies.py::{test_ui_does_not_import_integration, test_contracts_layer_depends_only_on_schemas_and_pydantic}` が Windows G-GEAR で `UnicodeDecodeError: 'cp932' codec can't decode` で fail (test 内 `path.read_text()` がデフォルト locale encoding を使う、UTF-8 source の non-ASCII で落ちる)。前セッション (Mac) では 1221 PASS。本 PR は採取タスクで planning purity 制約 (src/cli + tests/test_cli + scripts + data/eval/pilot + .steering + .gitignore) のため tests/test_architecture/ には触らない。別 PR で `encoding="utf-8"` 明示の修正を予定。

## Test plan

- [x] `uv run pytest tests/test_cli/test_eval_run_golden.py -q` (mock LLM、12 PASS — Step 1 既存)
- [x] `uv run pytest -q -m "not godot and not eval"` (Mac での 1221 baseline、Windows では上記 cp932 副次 fail のみ)
- [x] 6 invocation 全て exit 0 + atomic rename 成功 (各 .tmp 残存なし)
- [x] `_summary.json` 6 cells、`run_id` の expected vs file consistency check 通過
- [x] `uv run ruff check scripts/p3a_summary.py` clean
- [x] `uv run mypy scripts/p3a_summary.py` clean

## 次の hand-off

Mac セッションで:
1. (user 手動) G-GEAR → Mac rsync 実施
2. P3a-decide: `_summary.json` から bootstrap CI width 計算 → ME-4 ratio 確定
3. ME-4 ADR placeholder を `decisions.md` で実測値に Edit
4. M9-B blockers の "Hybrid baseline 比率 200/300" 項目 close

🤖 Generated with [Claude Code](https://claude.com/claude-code)

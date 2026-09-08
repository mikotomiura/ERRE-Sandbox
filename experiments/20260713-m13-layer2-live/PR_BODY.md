## 概要（construction であって measurement でない）

M2 Layer2（ミラー・シム = self-other functional analog、PR #77 MERGED）を **real qwen3:8b で初めて封印実走し
validate** する construction タスク。`self_other_enabled` を society_live 収録 harness + `m4_society_live_capture`
CLI に **additive thread** し、Layer2-on sealed golden を bake。self-other segment が real prompt に構造完全に
注入され LLM が応答することを **record→replay-verify + Win/WSL byte-parity** で validate。

**性質**: 実 qwen3:8b の **capture spend** はあるが **measurement spend でない**（R-budget=0、
floor/verdict/scorer/**magnitude/divergence** 非計算・非 emit、holding 不可侵、measurement-line CLOSE 不変、
reasoning-trace door 保全）。**acceptance = 非意味論 boolean のみ**（Codex pre-register HIGH-1）。

## 変更（additive、既存 Layer2-off path byte-identical）

- **K1** `society_live.py`: `run_society_live_capture` に keyword-only `self_other_enabled: bool = False`
  （→ `run_society_loop` へ pass、society.py は無改変）+ 純ヘルパ `apply_self_other_env_pin`（True 時のみ書込・
  False で除去、single seam）。
- **K2** `m4_society_live_capture.py`: `--self-other`（capture-only）+ env_pins 永続 + `verify()` が committed
  manifest から auto-detect（present 時 `type(v) is bool` fail-closed）+ silent-off guard。
- **K3** `test_m2_layer2_live.py`（新規、Ollama-free existence-check）+ `test_m4_society_replay.py`（m2_layer2 Godot
  parametrize）+ `test_m4_society_live.py`（K1/K2 unit test）。
- **golden** `tests/fixtures/m2_layer2_live_golden/`（real qwen3:8b、N=3 kant/nietzsche/rikyu、think=False、
  seed=0、horizon=12、self_other_enabled=True）。

## honest outcome（over-read guard、非意味論 boolean / byte）

| # | 契約 | 結果 |
|---|---|---|
| (1) | self-other 注入の構造的存在 | **PASS** — tick0 全 framing 不在 / tick 1..11 全 observer framing 有り + observed set == `sorted(all_agents)-{observer}` + 自己行なし |
| (2) | real LLM 応答 | **PASS** — 36/36 decode + 構造 parse |
| (3) | record→replay byte-parity（Win） | **PASS** — inner_invocations=0、checksum 一致 |
| (4) | WSL cross-platform byte-parity | **PASS** — Win==Linux |

**rendering collapse 診断**（M4 finding 再確認、non-gating memo）: この artifact では authored `destination_zone`
が 5 zone label を含んだ（semantic uptake / effect は未評価）が、segment 内 `zone=` は peripatos に collapse
（memory_centroid）。→ multi-zone rendering fix は **別 scoping で deferred**。

**結論（over-read 禁止）**: Layer2-on sealed construction が byte-identically に replay され（Win==Linux）、
self-other segment は全 window≥1 で構造完全に genuine に注入され LLM は parseable plan を 36/36 で返した。
**semantic effect（他者観察が行動をどれだけ変えたか）は measured でない**。

## 検証
- pre-push 4 段 ALL PASS（ruff format --check / ruff check / mypy src / pytest -q = **3706 passed, 52 skipped**）。
- Windows + WSL の `--verify` で checksum Win==Linux 実測。
- 再現: `experiments/20260713-m13-layer2-live/run.sh`。

## レビュー
- **pre-register Codex**（gpt-5.5/xhigh）: material HIGH-1 検出 → user 裁定で反映（acceptance 非意味論化）+
  MEDIUM-1..4 / LOW-1..3。
- **TASK-POST cross-review**: code-reviewer(Opus) = **Approve / HIGH・MEDIUM なし**、Codex(gpt-5.5) = **最終 merge
  を止める HIGH なし**。Codex MEDIUM-1（helper pop-on-False + M4 golden no-key test）+ LOW-2（findings 語彙）反映。

Refs: `.steering/20260713-m13-layer2-mirror-sim-live-run/`（design / decisions / codex-review / findings）

🤖 Generated with [Claude Code](https://claude.com/claude-code)

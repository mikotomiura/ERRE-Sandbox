# notes — developmental substrate Stage B (B-pre + B1)

- 事前登録: `prereg.md` (凍結 = PR #119、sha256 `ba7b16a5…`。結果 JSON の `prereg_sha256` に観測値)
- B-pre: `scripts/stage_b_pre.py`、再計算 = `bash experiments/20260926-developmental-substrate-stage-b/run.sh`
  (2 回計算して byte 一致)。結果 = `results/b_pre/results.json`
- B1 scorer: `scripts/stage_b_scorer.py` (prereg §3–§5)。test = `tests/test_stage_b/`
  (合成の陽性対照・陰性対照 n1〜n4・判定 rule)
- B1 変異試験: `uv run python scripts/stage_b_mutation_check.py --out results/b1_mutation.json`
  (m1〜m15、Codex 反映の mc1〜mc4、B-pre rule の mb1〜mb7。落ちた test が意図した判定行のものかを照合)
- battery ドラフト (未凍結): `scripts/stage_b_battery.py`、設計メモ `battery-design.md`
- ADR / 判断記録はローカル `.steering/20260926-stage-b-pre-b1/` (decisions DB-1 = prereg §4 power 定義の頭打ち)

## 結果 (2026-09-26)

- **B1**: scorer と判定 rule を実装。変異 31/31 KILLED (`results/b1_mutation.json`、理由照合込み)。
  - 発見: prereg §4 の power 模擬は効果をちょうど δ_min 植えて Ĉ ≥ δ_min を問うため、power が ~0.5 で頭打ちになる
    (`test_power_ceiling_under_prereg_definition`)。literal に適用すると lever 十分性 (power ≥ 0.8) は到達不能。
- **B-pre**: 入力の zone=None (330/4800、parse 不能 / 行先なし) は §7 に扱いが無く、分布を見る前に 1 カテゴリ ⊥ として
  数えると決めた (§7 の 150 / 150 を保つ読み)。結果 = **両条件で不成立** (off: between 中央値 0.0533 ≤ 床 0.1267、
  on: 0.0567 ≤ 0.0600) → verdict **INVALID_TASK_BATTERY**。prereg §7 の停止条件により Stage B は停止し、B2 / B3 は
  起動しない。
- claim 境界: この bank で閉集合選択が文脈の内容に応じて split-half の床を超えて動くことが観測されない、まで。
  経験から育つ外部状態が選択を動かせないことの証拠ではない (prereg §7 / §8)。

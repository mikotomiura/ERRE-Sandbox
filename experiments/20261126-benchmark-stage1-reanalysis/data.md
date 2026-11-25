# data

- 入力: 凍結した 4 つの chain の既存記録 (read-only)。path と sha256 は rules.md §1 の表を参照する。
  - v2 (`20260926-skill-lever-pilot`)・v3 (`20260926-experience-skill-pilot`)・G (`20261001-generalization-probe-pilot`)・O_time (`20261008-o-time-probe-pilot`)。
  - 本走の記録と results.json。G と O_time は pilot の記録 (masked の null の記述用) も読む。
- 出力: `results/stage1.json` (run.sh が生成する)・`results/report.md` (集計後に書く)。
- 用途の限定: rules.md §0。段 1 で見た記録は、段 2 の確認データにしない。

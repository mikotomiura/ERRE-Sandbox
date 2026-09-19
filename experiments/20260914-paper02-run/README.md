# 論文 02 前向き 2 アームの実走記録 (2026-09-14)

driver = `scripts/paper02_run_arms.py` (`--capture --arm control|primary`)。作業記録 = `.steering/20260914-paper02-prospective-run/`
(中断と再走の判断は `decisions.md` DA-PR-3)。

| ファイル | 中身 | 追跡 |
|---|---|---|
| `artifacts/*/run_records.jsonl` | draw ごとの prompt・sampling・`raw_response`・読み出し (4,800 行) | しない。論文 repo の `data/prospective/` に byte のまま出荷済み (正本) |
| `artifacts/*/run_annotation.jsonl` | scorer が読んだ annotation (4,800 行) | しない。同上 |
| `artifacts/*/run_records.partial.jsonl` | driver が呼び出しごとに追記した記録。`call_index` (1〜4,800)・`observed_at` (呼び出し時刻)・`model`・`content`。`content` は `run_records.jsonl` の `raw_response` と行ごとに一致する (2026-09-19 に 4,800/4,800 を確認) | する。**draw ごとの呼び出し時刻と呼び出し順を持つ唯一の記録** (records 本体には時刻が無い) |
| `artifacts/control/run_records.partial.attempt1-interrupted.jsonl` | control の attempt 1 の途中記録。41 行と、途中で切れた最終行 (NUL 594 bytes) | する。外から止められた attempt 1 の証跡 (DA-PR-3)。attempt 1 は verdict を産出していない |
| `artifacts/*/attempts.jsonl` | driver の append-only な試行記録 (start / captured)。control は start が 2 行 | する |
| `artifacts/*/run-manifest.json` | 環境の pin と成果物の digest。論文 repo の `data/prospective/*/run-manifest.json` と byte 一致 | する |
| `artifacts/*/run-verdict.json`・`run-metrics.json` | scorer の verdict と実行の計量 | する |
| `*-capture.log`・`*-capture.err.log` | driver の標準出力・標準エラー (CRLF のまま。`.gitattributes` の `experiments/**/*.log -text`) | する |

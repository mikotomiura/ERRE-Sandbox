# 実行環境

- Python 3.11、`uv.lock` で固定。追加依存なし (numpy のみ)。
- 第 1 段の凍結までは、実モデル・GPU を使っていない。
- マシン: G-GEAR (Windows native、16 論理コア)。見取り図・certification は CPU のみ。長い計算は `Start-Process -WindowStyle Hidden` の
  detached process で走らせた。

## fixture 表 (`results/fixture_table.json`)

- `uv run python scripts/o_time_probe_fixtures.py --out experiments/20261008-o-time-probe-pilot/results/fixture_table.json`
- 本走の並び・書き方の対の上で R ∈ {96, 192, 288} (DU-2 の後に作り直した)。登録 29 方策のすべてで C = 0 (厳密)。gate を通る。

## 見取り図 (`results/sketch.json`)

- `uv run python scripts/o_time_probe_sim.py --out <path> --workers 7` を 2 回、detached process で並列に走らせ、出力の byte 一致を確かめてから
  `results/sketch.json` に置く (2 回分の出力とログは手元に残し、repo には入れない。内容は `sketch.json` と同じ)。
- 点ごとに乱数の流れが独立 (seed・R・目標・形・攪乱点から決まる) なので、worker の数と並列の順は結果に影響しない。
- `target_sha256` は起動時に読んだ、certification と同じ 6 ファイルの sha256。manifest が現在のコードとの一致と、選定の再計算を照合する。
- 1 回目 (2026-10-08 02:40〜05:16、候補 {24, 48, 72, 96}、当初の条件 4): 2 回で byte 一致 (sha256 `8438182e…`)。条件 4 だけが全候補で不合格で door-close
  (prereg §7.1 の逸脱の記録 1)。出力は手元に残し、repo には入れない。
- 回し直し (2026-10-08 11:59〜17:01、候補 {96, 192, 288}、DU-2・DU-3・Codex の反映の後、7 worker × 2 本): 2 回で byte 一致
  (sha256 `888007f545cf1d7eeafe4e34356031c613c0fe481987d62a5e5450a4e8f41cd0`)、`target_sha256` は現在のコードと一致。選定 = R_MAIN 288。
  模擬の較正のずれは最大 0.0009。出力は手元に残し、repo には入れない (下の 3 回目と行は同じ)。
- 3 回目 (2026-10-08 22:17〜2026-10-09 03:31、Codex 2 回目の反映で sim の docstring を直した後、7 worker × 2 本、certification と並行): 2 回で byte 一致
  (sha256 `c3f942c3b1938469022fa6fff823141e4ef570a7d64e976d510cc06813256186`)、`target_sha256` は現在のコードと一致。2 回目の出力と比べて
  `target_sha256` 以外の欄 (行・選定・sweep・境目・params) はすべて同じ (乱数の流れはコードの docstring に依らない)。選定 = R_MAIN 288。
  この出力を `results/sketch.json` に置いた (LF、CR 0)。

## 変異試験の certification (`results/certification.json`)

- `uv run python scripts/o_time_probe_mutation_check.py --out experiments/20261008-o-time-probe-pilot/results/certification.json`
  (detached で起動)。
- 経緯: Codex review 1 回目 (2026-10-08、Revise) の反映の後、変異 238 個と meta-test 2 件で回した (2026-10-08 12:00〜14:36、見取り図の回し直しと並行)。
  238 / 238 KILLED。新しく足した・直した変異 21 個は、本番の前に `--only` で先に回して全 KILLED を確かめた。
- Codex review 2 回目 (2026-10-08、Approve-with-changes) の反映で manifest・test・harness が変わったので回し直した
  (2026-10-08 22:29〜2026-10-09 02:04、見取り図の 3 回目と並行)。変異 245 個 (manifest に mm57〜mm63 を足し、mm22〜mm24 の anchor を直した。
  この 10 個は本番の前に `--only` で先に回して全 KILLED を確かめた)。**245 / 245 KILLED**、meta-test 2 件とも登録どおりに落ちた
  (FAILED_AS_EXPECTED)、対象 6 ファイルが sha256 で原状復帰。
- manifest の `certification_violations` は `[]` (コード・test・harness・manifest 検査の sha256、登録変異と期待診断、meta-test の契約)。

## 第 1 段の凍結 (2026-10-09、user 裁定 DP-1)

- prereg の status を `**PILOT-FROZEN**` にして、`uv run python scripts/o_time_probe_manifest.py --write --stage pilot` → `manifest.json`
  (23 ファイル = prereg・SEED・run.sh・results の JSON 3 つ・scripts 9 本 (`stage_b_scorer.py` を含む)・tests 8 本。sha256 `1dd6b6affac11a7d67fab55be1084a10eea05d142702fdf205c55dc55ac6f035`、LF・CR 0)。
- `--verify --stage pilot` → `MANIFEST OK (stage pilot)`・exit 0。
- 他の manifest 6 本 (G の `--stage main`・v5・v4・v2・v3・body_walk) の `--verify` は開始時と同じ出力 (body_walk は設計どおり door-close)。
  G の封印ファイル (`manifest_main.json` の 34 ファイル) と `src/` は変えていない。
- env.md・data.md は封印の対象に入れていない (記録の追記のため)。

## driver の certification (`results/driver_certification.json`、2026-10-12)

- driver・変異 harness・driver の test (`scripts/o_time_probe_driver.py`・`scripts/o_time_probe_driver_mutation_check.py`・
  `tests/test_o_time_probe/test_driver.py`) は、候補 G の driver 一式を写して O_time の構造で書き直した (G の scripts は import しない)。
  設計と採否は `.steering/20261012-o-time-probe-driver/` (ローカル、/reimagine はハイブリッド = DOT-1)。実モデル・GPU は使っていない
  (test は偽の Ollama だけ)。
- `uv run python scripts/o_time_probe_driver_mutation_check.py --out experiments/20261008-o-time-probe-pilot/results/driver_certification.json --workers 4`
  (`PYTHONUTF8=1`、`Start-Process -WindowStyle Hidden` の detached で起動)。harness は変異を repo の外の複製ツリーにだけ当て、
  4 つの複製で並列に回す (repo の driver は書き換えない)。
- 経緯: 書き直した・足した変異 25 個を先に `--only` で回して全 KILLED を確かめた。Codex review 1 回目 (gpt-6-astra / xhigh、
  Approve-with-changes、HIGH 0・MEDIUM 1・LOW 0、323,035 tokens) の MEDIUM-1 (実行中に test・harness が変わったときの終了コード) を
  反映してから本番を回した (2026-10-12 19:13〜19:53、約 40 分)。
- **232 / 232 KILLED**、meta-test 3 件とも登録どおりに落ちた (FAILED_AS_EXPECTED)、repo の driver が開始時と同じ bytes、実行中に test と
  harness が変わっていない。`manifest.driver_certification_violations` は `[]`。`--verify --stage pilot` は `MANIFEST OK (stage pilot)` のまま。
- null pilot (GPU) は未実行 (別の user 裁定)。

## null pilot (GPU、`results/pilot/`、2026-10-12、user 裁定 DOT-7)

- 実行機 = G-GEAR (Windows 11、RTX 5060 Ti 16 GB)、Ollama 0.32.12 (Windows native)、`qwen3:8b` (digest `500a1f06…b8b41`)。
  起動前の確認 (driver の docstring の 5 点) は起動の前と run.sh の前の 2 回とも合格。
- 起動: PowerShell で `PYTHONUTF8=1`・`PYTHONHASHSEED=20261008` (SEED) を入れ、`Start-Process -WindowStyle Hidden` で
  `uv run python scripts/o_time_probe_driver.py --stage pilot` (detached、2026-10-12 21:29:38 JST)。
- driver: `started_at` 2026-10-12T12:29:42Z → `finished_at` 12:31:53Z (約 2 分 11 秒)、`exit_reason=completed`。
  576 呼び出し・再送 0・`n_finish_length` 0、provenance の `status` = null (`not_computed` でない)・`anomalies` []・`published` true・
  `pinned_changed` []・`read_back_problems` []。`git_dirty` true は固定ファイル外の未追跡 (`jote-submit/` 等) による。
  `driver_sha256` `ea0a24fe…`・`records_sha256` `29935540…`・`meta_sha256` `dce13c0e…`。
  observed (開始と終わりで同じ) = model_digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`・
  ollama_version `0.32.12`・template_sha256 `ae370d884f108d16e7cc8fd5259ebc5773a0afa6e078b11f4ed7e39a27e0dfc4`。
- `bash experiments/20261008-o-time-probe-pilot/run.sh pilot` (Git Bash): `MANIFEST OK (stage pilot)` →
  `[run.sh] pilot: repeat byte-identical` → exit 0。
- `results/pilot/gate.json` の判定 (verbatim): `"decision": "GO"`・`"R": 288`・`"reasons": ["spike-in OC passed"]`・`"status": "computed"`。
  M0 = `"verdict": "PASS"` (`"passed": true`、72 単位)。envelope: `"masked_max_bottom": 0.0`。
  OC: `"checks": {"calibrated": true, "power_no_go": true, "power_pass": true, "size_no_go": true, "size_pass": true}`・`"ok": true`。
- 記述 (判定に使わない): masked の不一致率 0.0208・masked の null の C −0.0069・M0 の C 0.976・記録に無い行動の率 masked 0.0278 / M0 0.0174。
- pilot の記録は本走の verdict に使わない (prereg §8.1)。第 2 段の凍結 (§9.3) と本走は、それぞれ別の user 裁定。

## 第 2 段の凍結 (`manifest_main.json`、2026-10-12、CPU のみ)

- 認可: user 裁定 ONP-4 (2026-10-12、AskUserQuestion。`.steering/20261012-o-time-probe-null-pilot/decisions.md`)。範囲は第 2 段の凍結
  (prereg §9.3) まで。本走 (§9.4) は含まない (さらに別の user 裁定)。記録は `.steering/20261012-o-time-probe-stage2-freeze/` (ローカル)。
- 開始の前 (main = c11719a、PR #154): `--verify --stage pilot` = `MANIFEST OK (stage pilot)`・`driver_certification_violations` = `[]`・
  第 2 段の照合の予行 (`--verify --stage main`) は `cannot read …/manifest_main.json` と `NOT FROZEN: prereg: status is not FROZEN …` の 2 点だけ。
  封印の対象 32 ファイル (`FROZEN_FILES` 23 + `MAIN_EVIDENCE` 9) の作業木の bytes が HEAD の blob と同じ
  (`git hash-object --no-filters` = `git rev-parse HEAD:<path>`)・`results/pilot/gate.json` の CR 0。`manifest_main.json`・`results/run/` なし。
- 変更: prereg の status 行 (3 行目) だけ。新しい行 = `- status: **FROZEN** (2026-10-12、user 裁定 ONP-4。第 2 段の封印 = 確認実験。第 1 段 PILOT-FROZEN は 2026-10-09、DP-1)`。
  本文の他の行は第 1 段のまま。status 行を除いた本文の sha256 (`prereg_body_sha256` = `2a4b1ab7…436d851f`) は第 1 段の `manifest.json` の値と同じ。
  status 行を変えた後の予行は `cannot read …/manifest_main.json` の 1 点だけ (`--write` は凍結条件を照合しないので、書く前に確かめた)。
- `PYTHONUTF8=1 PYTHONHASHSEED=20261008 uv run python scripts/o_time_probe_manifest.py --write --stage main` →
  `wrote experiments/20261008-o-time-probe-pilot/manifest_main.json (32 files)`。
  `manifest_main.json` の sha256 = `4677cc8e09c0b42a5b51596992619f58600d2659621c615d5be7b592d8a90d38` (3,965 bytes・LF・CR 0)。
  内訳 = 第 1 段の対象 23 + 足した証拠 (`MAIN_EVIDENCE`) 9。第 1 段の対象のうち prereg 以外の 22 ファイルの sha256 は第 1 段の値と同じ。
  prereg は FROZEN の版の全文 (`b659600f…bbf59c85`)。足した証拠のうち `manifest.json` = `1dd6b6af…5ac6f035`・
  `results/pilot/gate.json` = `347ca80c…afb6311f`。
- `--verify --stage main` → `MANIFEST OK (stage main)`・exit 0。= 第 1 段の封印・pilot の判定の再計算 (GO・R 288・masked の最大 ⊥ 率・observed)・
  入力の sha256・provenance の 3 項目・driver の certification・status = FROZEN が全て通った (prereg §9.3 の 1)。
- 注意 (設計どおり): status 行を変えた後は、`--verify --stage pilot` (と `run.sh pilot`) は
  `MISMATCH: experiments/20261008-o-time-probe-pilot/prereg.md: sha256 differs from the frozen manifest` → `MANIFEST MISMATCH (1)` で止まる (exit 1)。
  第 1 段の `manifest.json` は prereg の全文の sha256 を持ち、第 2 段の照合 (`stage1_seal_violations`) だけが prereg を `prereg_body_sha256` で比べる。
  pilot の判定の再計算は第 2 段の照合 (`pilot_gate_violations`) が担う。以後の照合は `--stage main` で行う。
- 本走 (GPU、`results/run/`) は下の節 (user 裁定 OS2-5)。

## 本走 (GPU、`results/run/`、2026-10-13、user 裁定 OS2-5)

- 認可: user 裁定 OS2-5 (2026-10-13、AskUserQuestion。`.steering/20261012-o-time-probe-stage2-freeze/decisions.md`)。範囲は開始前の確認 →
  `--stage main` の起動の予行 → 本走 (prereg §9.4、13,824 呼び出し) → `run.sh main` の判定 → 記録まで。記録は
  `.steering/20261013-o-time-probe-main-run/` (ローカル)。
- 実行環境: main = 2ee2a79 (PR #155、第 2 段 FROZEN)。G-GEAR (Windows 11、RTX 5060 Ti 16 GB、起動前の使用 1,284 MiB・3%、他の長時間の job なし)。
  Ollama 0.32.12 (Windows native)・`qwen3:8b` (500a1f067a9f)。pilot と同じ実行環境 (prereg §9.4 の 1)。
- 開始の前: `--verify --stage main` = `MANIFEST OK (stage main)`・`driver_certification_violations` = `[]`・封印の対象 33 ファイル
  (`FROZEN_FILES` + `MAIN_EVIDENCE` の 32 + `manifest_main.json`) の作業木の bytes = HEAD の blob・gate.json と manifest_main.json の CR 0・
  固定ファイルに未 commit の変更なし・`results/run/` なし。起動の前の確認 (driver の docstring の 5 点): 1〜4 は全て exit 0 で出力が空
  (`[][]`・`[]`)。5 は運用 (本走の間に Python の install・update をしていない)。
- 起動の予行 (GPU なし・実の Ollama に触れない・tmp の dir、約 2 分 20 秒): driver をその bytes のまま `__main__` として実行し (`--stage` を渡さず
  argparse で止めて、門と `_PinnedFinder` だけを入れる)、`launch_problems("main")` = `[]`・`executed_problems("main", …)` = `[]`。
  `stage_from_gate` の段は plan 13,824 (AB / BA / CD / DC 各 3,456)・`reference_observed` = gate.json の `observed`・その予定表の
  `schedule_violations` (gate の observed) = `[]` (作るだけで run しない)。`httpx.MockTransport` の偽の Ollama (答え = `I choose <表示の先頭の label>.`)
  から取った偽の observed で `main_stage(tmp, 288, 偽の observed)` の全 run → `completed`・`published` true・`anomalies` []・`n_resends` 0・
  13,824 行 (6 label 各 2,304)。run の後の `executed_problems("main", …)` = `[]`・実の `results/run/` なし。
- 起動 (PowerShell、同じ process の中で続けて): `$env:PYTHONUTF8 = "1"`・`$env:PYTHONHASHSEED = (Get-Content …/SEED).Trim()` (= 20261008) の後に
  `Start-Process -WindowStyle Hidden -PassThru -WorkingDirectory C:/ERRE-Sand_Box -FilePath uv -ArgumentList 'run','python','scripts/o_time_probe_driver.py','--stage','main'`
  (stdout・stderr は手元の log へ)。起動 2026-10-13 01:34:54 +09:00 (PID 14108、`uv`)。
- 所要: driver の `started_at` 16:35:02.156 UTC 〜 `finished_at` 18:40:27.160 UTC = **約 2 時間 5 分** (13,824 呼び出し、平均 約 1.8 呼び出し / 秒)。
  見込み (pilot の 約 4.4 呼び出し / 秒から約 50〜55 分) より遅い。1,000 呼び出しあたり約 5〜16 分とぶれた (GPU の他の利用の有無は未確認)。
  stdout は `[driver] 100 calls` 〜 `[driver] 13800 calls` と `[driver] exit_reason=completed`、stderr は空。
- transport 失敗 2 回 (`attempts.jsonl`): call_index 6086 (17:19:04 UTC) と 7339 (17:38:20 UTC)、ともに `HTTP 500`・attempt 0。
  どちらも同じ body (同じ seed) の再送 1 回で解けた (prereg §4 の再送の範囲内。raw = null の行なし)。
- provenance (`provenance.json`): `exit_reason` = `completed`・`status` = null (`not_computed` ではない)・`error` = null・`anomalies` = []・
  `n_sent` 13,826・`n_records` 13,824・`response_models` = `["qwen3:8b"]`・`n_resends` = 2・`n_finish_length` = 0・`pinned_changed` = []・
  `manifest_problems_at_publication` = []・`read_back_problems` = []・`published` = true・`git_head` = 2ee2a79。
  `driver_sha256` = `ea0a24fed13e641ac472426216956e880f11d8806d9c94c6d16318028113e5d9`・
  `records_sha256` = `26a18bcd9e179dd4d7f049865b2a024050bdf270f15a65c4c2adb8e9665eb972`・
  `meta_sha256` = `dce13c0e79e9bc38e62983f8e4bc88c3eac3c670efb1290d65b0254b3d8fb6f5` は現在のファイルと一致。`git_dirty` = true は固定ファイル外の未追跡
  (`jote-submit/` 等) による。
- observed (`meta.json`。provenance の開始と終了も同じ): `model_digest` = `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`・
  `ollama_version` = `0.32.12`・`template_sha256` = `ae370d884f108d16e7cc8fd5259ebc5773a0afa6e078b11f4ed7e39a27e0dfc4`。pilot (gate.json の
  `observed`) と同じ (prereg §4)。meta.json の bytes は pilot の meta.json と同じ (sha256 `dce13c0e…`)。
- ⊥ (記述、判定ではない): lever 4 arm とも 0 / 3,456 (率 0.0)。上限 min(0.2, 0.0 + 0.05) = 0.05 (prereg §8.3) の内。
- 判定の前に起動の前の確認 1〜4 をもう一度 (全て exit 0・出力が空・`[][]`・`[]`)。
- `bash experiments/20261008-o-time-probe-pilot/run.sh main` (Git Bash): `MANIFEST OK (stage main)` → `[run.sh] main: repeat byte-identical` → exit 0。
  `results/run/results.json` (608 bytes・LF・CR 0、sha256 `156c64affadc6a7e962b321bad8cd218941895e7543d3eb1d95f0a7dc618e274`)。
- 判定 (verbatim): `"verdict": "NO_GO_EFFECT_ABSENT"`・`"status": "computed"`・`"reasons": ["decided"]`・`"n_units": 3456`・
  `"C": 0.10496238425925926`・`"log_e_minus": 485.4140264628137`・`"log_e_plus": -138.83059635329838`・`"bottom_max": 0.05`・
  `"lever_bottom_rates": {"AB": 0.0, "BA": 0.0, "CD": 0.0, "DC": 0.0}`。
  成分 (向き × 書き方の標本平均): `"bwd_ago": 0.19849537037037038`・`"bwd_asc": 0.10185185185185185`・`"fwd_ago": 0.12760416666666666`・
  `"fwd_asc": -0.008101851851851851`。
  記述 (判定に使わない): `"C_ago": 0.16304976851851852`・`"C_asc": 0.046875`・`"other_rate": 0.03464988425925926`・`"log_e_zero": 196.9486631376363`。
- 読み (prereg §11 の上限まで): この battery・この schedule での、現在の規則の向きの平均の対比 E[C] は τ = 0.30 未満 (E⁻ ≥ 1/α)。
  時期の評価の不在・選択分布の差全体の否定・`ago` の難しさによる NO_GO の排除・M1 全体の close は言わない。`log_e_zero` (記述) から
  「τ 未満の正の効果」とも読まない (§5.1)。打ち止め (c) (§0) では、M1 の 2 候補のうち O_time が `NO_GO_EFFECT_ABSENT`。候補 O の
  事前登録は別の user 裁定による。

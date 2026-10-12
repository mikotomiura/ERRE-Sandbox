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

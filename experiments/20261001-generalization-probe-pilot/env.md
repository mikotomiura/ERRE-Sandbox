# 実行環境

- Python 3.11、`uv.lock` で固定。追加依存なし (numpy のみ)。
- 実モデル・GPU は使っていない。null pilot・本走・driver は起こしていない (prereg の冒頭)。
- マシン: G-GEAR (Windows native、16 論理コア、CPU のみ)。長い計算は `Start-Process -WindowStyle Hidden` の detached process で走らせた。

## probe key の選定 (`results/key_selection.json`)

- `uv run python scripts/generalization_probe_key_selection.py --out experiments/20261001-generalization-probe-pilot/results/key_selection.json`
- 選定用の行順 (seed 20261002、本走と別) の上で、R ∈ {6, 12, 18} と字面の方策 66 種。所要 約 3 分。max |C| = 0.0208。
  割り当ては battery の `PROBE_KEYS` と一致 (test と manifest が照合)。

## fixture 表 (`results/fixture_table.json`)

- `uv run python scripts/generalization_probe_fixtures.py --out experiments/20261001-generalization-probe-pilot/results/fixture_table.json`
- 本走の行順の上で R ∈ {6, 12, 18}。gate を通る (最大 |C| = 0.0469 / 0.0391 / 0.0417)。key を見ない方策は全 R で厳密に 0。

## 見取り図 (`results/sketch.json`)

- `uv run python scripts/generalization_probe_sim.py --out <path>` を 2 回、detached process で並列に走らせ、出力の byte 一致を確かめてから
  `results/sketch.json` に置いた (2 回分の出力とログは手元に残し、repo には入れない。内容は `sketch.json` と同じ)。
- `target_sha256` は起動時に読んだ、certification と同じ 6 ファイルの sha256。manifest が現在のコードとの一致と、選定の再計算を照合する。

## 変異試験の certification (`results/certification.json`)

- `uv run python scripts/generalization_probe_mutation_check.py --out experiments/20261001-generalization-probe-pilot/results/certification.json`
  (detached で起動)。
- 経緯 (Codex review 1 回目の前の設計):
  - 1 回目: 82 / 84 KILLED。mx02 と mx08 が SURVIVED (test の穴)。test を直して回し直し、84 / 84 KILLED。
- Codex review 1 回目の反映の後 (Ω・知識確認・2 段の凍結など): 変異 109 個と meta-test 2 件で回し直した (結果は下に追記する)。
  - 1 回目 (109 変異): 108 / 109 KILLED。ms36 (CLI が pilot の GO を確かめない) が SURVIVED。STOP の gate の例が R = None で、R の型の確認だけで
    GO でないと決まっていた (test の穴)。decision だけが STOP の gate に直した。
- Codex review 2 回目の反映の後 (seed をつ組で共有・manifest の再計算・driver の契約など): 変異 127 個 (manifest の判定行 14 個を含む) と
  meta-test 2 件で回し直し、**127 / 127 KILLED**、meta-test 成立、対象 6 ファイルが sha256 で原状復帰 (2026-10-02)。
- Codex review 3 回目の反映の後 (変異と meta-test が期待した test で実際に落ちたことの照合・provenance の 3 項目・見取り図の sweep と率の再検査):
  変異 155 個 (manifest の判定行 42 個を含む) と meta-test 2 件で回し直し、**155 / 155 KILLED**、meta-test 成立、対象 6 ファイルが sha256 で
  原状復帰 (2026-10-02 06:06〜06:43)。開発用に manifest の 42 個だけを先に回し、42 / 42 KILLED を確かめてから本番を回した。
- Codex review 4 回目の反映の後 (登録 MUTANTS・META_CASES の形の検証・JSON の真偽値): 変異 162 個 (manifest の判定行 49 個を含む) と
  meta-test 2 件で回し直し、**162 / 162 KILLED**、meta-test 成立、対象 6 ファイルが sha256 で原状復帰 (2026-10-02 12:19〜)。
  新しい変異 (mm40〜mm49) は先に開発用に回して 10 / 10 KILLED を確かめた。

## 改行 (封印の前に LF にそろえた)

- `results/fixture_table.json`・`key_selection.json`・`sketch.json` は、書き出した script が Windows のテキストモードで書いたので CRLF だった。
  repo の `.gitattributes` は `*.json` を LF に固定するので、commit される正本は LF。封印 (`manifest.json`) の sha256 が checkout 後のファイルと
  一致するよう、第 1 段の封印の前に 3 つを LF に直した (JSON として読んだ内容は同じことを確かめた)。結び付きの検査は JSON を読んで比べるので影響しない。

## driver の certification (`results/driver_certification.json`、2026-10-02)

- driver = `scripts/generalization_probe_driver.py` (pilot と本走を同じ経路で持つ)。test = `tests/test_generalization_probe/test_driver.py`
  (偽の Ollama のみ、実モデル・GPU は使っていない)。harness = `scripts/generalization_probe_driver_mutation_check.py`。
- `uv run python scripts/generalization_probe_driver_mutation_check.py --out experiments/20261001-generalization-probe-pilot/results/driver_certification.json`
  (detached で起動、1 回 約 55 分)。設計と採否は `.steering/20261002-generalization-probe-driver/` (ローカル)。
- 経緯:
  - 開発用の 1 回目 (132 変異): 132 / 132 KILLED・meta-test 3 件成立。
  - Codex review 1 回目 (HIGH 2・MEDIUM 2・LOW 2) と code-reviewer の反映の後 (149 変異): 148 / 149。q5 (起動拒否を外す) が SURVIVED。
    反映で足した autouse の封鎖 (実の transport を作ると例外) が、変異の経路を `main` の例外処理で止めていた (test の穴)。test を直し、
    `--only q5` で KILLED を確かめてから回し直した。certification は書かれていない (全 KILLED のときだけ書く)。
  - 回し直し: 149 / 149 KILLED・meta-test 3 件成立。その後の code-reviewer の再レビュー (HIGH 0・MEDIUM 1・LOW 5) を反映した
    (等価の分類の取り消し・pinned を起動の検査の前に取る・照合に落ちた記録を退ける・読めないファイル・teardown の節・読み戻しの後の比較)。
    この certification は driver・test が変わるので消した。
  - 最終: 変異 155 と meta-test 3 件 (新しい 6 変異は先に `--only` で KILLED を確かめた)。**155 / 155 KILLED**・meta-test 3 件成立
    (予定表の事前検査・送る直前の照合・公開前の読み戻しを潰すと、期待した test が全て落ちる)・driver が sha256 で原状復帰・実行中に
    test と harness が変わっていない。`manifest.driver_certification_violations` が `[]` を返す (test で pin)。
- 第 1 段の封印 (`manifest.json`) は変えていない: `--verify --stage pilot` は `MANIFEST OK (stage pilot)` のまま。
- Codex の再 review (2026-10-02、反映の差分、Verdict Revise・HIGH 1・MEDIUM 2・LOW 1) の反映の後に回し直した (2026-10-02〜03)。
  設計と採否は `.steering/20261002-generalization-probe-driver-rereview/` (ローカル)。
  - 実行したコードの同定: driver は起動時に bytes を 1 回だけ読み、実行中のモジュールの code object がその bytes のコンパイル結果で
    あることを確かめる。repo のモジュールは、起動のときだけ、1 回だけ読んだ bytes から実行する (pyc を使わない)。起動の検査の後に、
    その bytes を起動の検査の前のディスクと照合する。来歴の `driver_sha256` は、実行したプログラムのコンパイル元の bytes を指す。
  - transport 失敗の `status: not_computed` を、raw = null の行を書いた事実から決める (終了時の observed の取得中の中断でも残る)。
    manifest の照合の末尾行は LF だけで切る。
  - 変異の判定: 理由の文の無い変異は、期待 test の item の本体の節に、pytest が書き換えた assert の行があるときだけ KILLED に数える
    (NameError・TypeError・autouse の封鎖の `raise AssertionError`・setup / teardown の節は数えない)。変異 a6 を、未定義の名前で
    落ちる形から、本来の変異 (開始時の observed を流用する) に直した。
  - 回し直し 1 回目 (変異 173): 135 / 173 KILLED・WRONG_REASON 38・SURVIVED 0。38 件は、期待 test が `pytest.raises` の DID NOT RAISE
    や、外した検査の後段の例外で落ちていた (意図どおり)。実測した例外の文を理由として登録し (理由の文を持つ変異 14 → 50)、assert の
    式の中で例外が出ていた test 2 件 (u6・l22 の期待 test) を assert で落ちる形に直した。
  - 回し直し 2 回目: **173 / 173 KILLED**・meta-test 3 件成立・driver が sha256 で原状復帰・実行中に test と harness が変わっていない。
    `manifest.driver_certification_violations` が `[]`。`--verify --stage pilot` は `MANIFEST OK (stage pilot)` のまま。

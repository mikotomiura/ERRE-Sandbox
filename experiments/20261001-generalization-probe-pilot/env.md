# 実行環境

- Python 3.11、`uv.lock` で固定。追加依存なし (numpy のみ)。
- 第 1 段の凍結と driver の certification までは、実モデル・GPU を使っていない。実モデル・GPU を使ったのは null pilot (2026-10-05、下の節) だけで、
  本走は起こしていない。
- マシン: G-GEAR (Windows native、16 論理コア)。見取り図・certification は CPU のみ。null pilot は Windows native の Ollama (GPU)。
  長い計算は `Start-Process -WindowStyle Hidden` の detached process で走らせた。

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
- Codex の 3 回目の review (2026-10-03、再反映の差分、Verdict Revise・HIGH 0・MEDIUM 2・LOW 1) の反映の後に回し直した (2026-10-03)。
  設計と採否は `.steering/20261003-generalization-probe-driver-third-review/` (ローカル)。
  - 実行したコードの範囲: driver の最初の文で import の門を入れ、環境 (インタプリタと venv の prefix の下) と固定ファイルの外に所在がある
    コードを import させない (`scripts/` に置いた `numpy.py` 等)。`scripts` は `root/scripts` だけを探す名前空間として作り、
    `__init__.py` を実行しない。門より前に取り込まれたもの (sitecustomize 等) は、起動の検査の後の走査が拒否する。
  - 変異の判定: pytest の出力の文字列を正規表現で切るのをやめ、harness 自身を pytest の plugin として読み込ませ、失敗ごとの記録
    (関数名・parametrize の id・段・先頭が assert 文か・例外の chain の型と文とフレーム) で照合する。理由のある変異は、その item・段の、
    同じ 1 つの例外で、型・文・経由した driver の関数を照合する (別の parameter・段・例外を流用しない)。ループで入力を検査していた
    test は parametrize に開いた。certification の行に、照合した証拠の要約 (`witnessed_by`) を残す。
  - harness は各 run の前に `scripts/__pycache__` を消す (同じ長さの置換を同じ秒に書くと、前の変異の pyc で実行されうる。証拠の実測で発見)。
  - 変異 190 (門・名前空間・走査の 17 件を足した) と meta-test 3 件。1 回目: **190 / 190 KILLED**・meta-test 3 件成立 (約 75 分)。
    その後の code-reviewer・security-checker の反映 (証拠の要約から手元の path = OS のユーザー名とメモリの address を消す・docstring) で
    harness が変わったので回し直した。2 回目: **190 / 190 KILLED**・meta-test 3 件成立・driver が sha256 で原状復帰・実行中に test と
    harness が変わっていない (約 78 分)。`manifest.driver_certification_violations` が `[]`。`--verify --stage pilot` は
    `MANIFEST OK (stage pilot)` のまま。
- Codex の 4 回目の review (2026-10-03、3 回目の反映の差分、Verdict Revise・HIGH 2・MEDIUM 2・LOW 2) の反映の後に回し直した (2026-10-03)。
  設計と採否は `.steering/20261003-generalization-probe-driver-fourth-review/` (ローカル)。
  - manifest の照合を driver の process の中で行う: 子プロセス (門も固定ファイルの loader も無い) では、未追跡の `scripts/__init__.py` 等が
    実行されても照合の最後の行が変わらず、driver が受理していた。今は封印済みの manifest の `main` を run.sh と同じ引数で、門の下で呼ぶ。
  - **driver の起動の command が変わった**: run.sh と同じ `PYTHONHASHSEED` (= `SEED`) と `PYTHONUTF8=1` で起動する (違えば何も書かずに
    起動を拒否する)。PowerShell では
    `$env:PYTHONUTF8 = "1"; $env:PYTHONHASHSEED = (Get-Content experiments/20261001-generalization-probe-pilot/SEED).Trim()` の後に
    `uv run python scripts/generalization_probe_driver.py --stage pilot`。
  - `-E`・`-I` の起動は拒否する (Python が `PYTHONHASHSEED`・`PYTHONPATH` を読まないのに、`os.environ` には値が残るため)。
  - 起動時に site が実行しうるコード (`sitecustomize`・`usercustomize`・`PYTHONPATH` の entry・user site の `.pth`) は、実行されたか
    (import に失敗すると `sys.modules` に残らない) を問わず、所在が環境の外なら起動を拒否する。`PYTHONPATH` は名前に依らず見る
    (venv の `_virtualenv.pth` の `import _virtualenv` は、PYTHONPATH の同名の module を site の時点で実行しうる)。
    Debian・Ubuntu の system Python を base にした venv では、標準ライブラリの sitecustomize が `/etc` への link なので起動を拒否されうる
    (安全側。uv が入れた Python では起きない)。
  - 保証の範囲は driver の process。凍結 `run.sh` の判定の process (manifest の照合・機械判定・scorer) は門を持たず、封印済みの module が
    repo root を `sys.path` の先頭に入れるので、**run.sh の前に次を確かめる**:
    `git ls-files --others -- ':(glob)*.py' ':(glob)*/__init__.py' ':(glob)*.pyd' ':(glob)*.so' ':(glob)scripts/*.py'
    ':(glob)scripts/*/__init__.py' ':(glob)scripts/*.pyd' ':(glob)scripts/*.so'` が何も出さないこと (未追跡と ignored の両方を出す。
    `__init__.py` の無い dir は通常の module に優先しないので対象外)、`PYTHONPATH` が空であること。
  - 変異の判定: pytest が test の失敗 (exit 1) で最後まで走った run (session の終わりの記録がちょうど 1 つ) の記録だけを証拠に数える
    (それ以外は ABNORMAL_EXIT)。各 run に空の bytecode の置き場所を渡し書き込みも止める (前の変異の pyc で走らない。1 run 約 +10%)。
    `PYTEST_ADDOPTS`・`PYTEST_PLUGINS` は test の run に渡さない。証拠の要約は、実の tmp・home・ユーザー名を先に消す。
  - 変異 205 (process の中の照合・起動の前提・起動前の customization・境界条件の 15 件を足し、子プロセスの 2 件を置き換えた) と meta-test 3 件。
    1 回目: **205 / 205 KILLED**・meta-test 3 件成立 (約 100 分)。その後の code-reviewer・security-checker の反映 (PYTHONPATH の影・`-E`/`-I` の
    起動・SystemExit を畳む・user site・証拠の要約の消しすぎと ubuntu の `/tmp`) で driver・harness・test が変わったので、変異 5 件を足して回し直した。
    2 回目: 変異 210 と meta-test 3 件で **210 / 210 KILLED**・meta-test 3 件成立・driver が sha256 で原状復帰・実行中に test と harness が
    変わっていない (約 96 分)。`manifest.driver_certification_violations` が `[]`。`--verify --stage pilot` は `MANIFEST OK (stage pilot)` のまま。
- Codex の 5 回目の review (2026-10-03、4 回目の反映の差分、Verdict Revise・HIGH 1・MEDIUM 2・LOW 2) の反映の後に回し直した (2026-10-03〜04)。
  設計と採否は `.steering/20261003-generalization-probe-driver-fifth-review/` (ローカル)。起動の command は 4 回目から変わらない。
  - Windows の getpath がレジストリ (HKCU・HKLM の `SOFTWARE\Python\PythonCore\<winver>\PythonPath`) から検索パスに足す entry も、PYTHONPATH と
    同じく名前に依らず見る (venv でも常に足される子キーの値。キー自身の既定値は stdlib が見つからない起動でだけ使われるので、`sys.path` に
    あるときだけ)。この機械には python.org 版の 3.11 のキー自身の既定値があるが、使われていないので起動を止めない (確かめた)。
  - **run.sh の前の確認を広げた** (source の無い `.pyc`・Windows の `.pyw`・package の initializer `__init__.*` も import される):
    `git ls-files --others -- ':(glob)*.py' ':(glob)*.pyw' ':(glob)*.pyc' ':(glob)*.pyd' ':(glob)*.so' ':(glob)*/__init__.*'
    ':(glob)scripts/*.py' ':(glob)scripts/*.pyw' ':(glob)scripts/*.pyc' ':(glob)scripts/*.pyd' ':(glob)scripts/*.so' ':(glob)scripts/*/__init__.*'`
    が何も出さないこと、`PYTHONPATH` が空であること、Windows ではレジストリの `PythonPath` に子キーが無いこと
    (PowerShell: `foreach ($x in "HKCU:\Software\Python\PythonCore\3.11\PythonPath", "HKLM:\Software\Python\PythonCore\3.11\PythonPath")
    { if (Test-Path $x) { Get-ChildItem -LiteralPath $x } }` が何も出さない)。`__pycache__` の中の pyc (source が無ければ import されない) と、
    `__init__` の無い dir (通常の module に優先しない) は対象外。2026-10-04 の main で 3 つとも何も出さない。
  - 変異の判定: session の終わりの記録に、選ばれた item の数 (`--deselect` の後)・走りきった数・打ち切りの印を足し、`-x`・`--maxfail` で
    exit 1 のまま打ち切った run を証拠に数えない (ABNORMAL_EXIT)。証拠の要約: 実の tmp・home は path の要素の終わりでだけ置き換え、address は
    `` at 0x`` の後の 8 桁以上 (比較の値 `0xdead` 等は残す) と、pytest が `` at 0x`` ごと省いた残り。
  - 変異 223 (レジストリの 12 件・user site の接続 1 件を足した) と meta-test 3 件で **223 / 223 KILLED**・meta-test 3 件成立・driver が
    sha256 で原状復帰・実行中に test と harness が変わっていない (約 125 分)。`manifest.driver_certification_violations` が `[]`。
    `--verify --stage pilot` は `MANIFEST OK (stage pilot)` のまま。certification にユーザー名・メールアドレス・6 桁以上の address は 0 件。
- Codex の 6 回目 (最後) の review (2026-10-04、5 回目の反映の差分、Verdict Revise・HIGH 1・MEDIUM 1・LOW 3) の反映の後に回し直した。
  設計と採否は `.steering/20261004-generalization-probe-driver-sixth-review/` (ローカル)。起動の command は 4 回目から変わらない。
  - 所在は、Windows の拡張表記 (長い path の接頭辞の付いた形) のドライブと UNC の path を通常の表記に揃えてから比べる (前は、環境の中の dir を
    拡張表記で指す entry を環境の外として、正当な起動を止めた)。
  - この機械の起動の経路 (確かめた): venv の launcher (`.venv/Scripts/python.exe`) は、シェルに `PYTHONHOME` が無いとき、子に
    `PYTHONHOME` = base の Python の dir (pyvenv.cfg の home) を渡して base の python を起動し、venv は site が認識する。getpath は venv の
    分岐を通らず、executable の dir は `.venv/Scripts` (環境の中)。レジストリのキー自身の既定値は (`PYTHONHOME` があるので) 使われない。
  - **起動 (driver・run.sh) の前の確認を置き換えた** (repo root で。各 command が exit 0 で、出力が下のとおりであること。エラーを合格に数えない):
    1. 未追跡・ignored の import できるもの (Windows は拡張子の大文字小文字を区別しないので `icase`) が無い:
       `git ls-files --others -- ':(glob,icase)*.py' ':(glob,icase)*.pyw' ':(glob,icase)*.pyc' ':(glob,icase)*.pyd' ':(glob,icase)*.so'
       ':(glob,icase)*/__init__.*' ':(glob,icase)scripts/*.py' ':(glob,icase)scripts/*.pyw' ':(glob,icase)scripts/*.pyc'
       ':(glob,icase)scripts/*.pyd' ':(glob,icase)scripts/*.so' ':(glob,icase)scripts/*/__init__.*'` が何も出さない。
    2. repo root と `scripts` に link (reparse point) が無い (PowerShell):
       `Get-ChildItem -Force -LiteralPath ., scripts -ErrorAction Stop | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }`
       が何も出さない。
    3. 起動するシェルの `PYTHONPATH`・`PYTHONHOME` が未設定か空 (PowerShell: `"[$env:PYTHONPATH][$env:PYTHONHOME]"` が `[][]`)。
       Python の中で読まないこと (launcher が `PYTHONHOME` を入れる)。
    4. 同じ Python で読むレジストリの検索パスの子キーが無い (`sys.winver` と同じ registry view。`[]` を渡すのでキー自身の既定値は数えない):
       `uv run python -c "import sys; sys.path.insert(0, '.'); from scripts import generalization_probe_driver as d; print(d._registry_paths([]))"`
       が `[]`。
    5. pilot・本走の間に Python の install・update をしない (レジストリは起動の後に読み直すので、getpath から検査までの間に変わらないことが前提)。
  - 変異 230 (拡張表記の比べ方の 4 件・レジストリの値の扱いの 3 件を足し、証拠を専用の assert の文に結んだ) と meta-test 3 件で **230 / 230 KILLED**・
    meta-test 3 件成立・driver が sha256 で原状復帰・実行中に test と harness が変わっていない (約 113 分、2026-10-04 23:52〜10-05 01:45)。
    `manifest.driver_certification_violations` が `[]`。`--verify --stage pilot` は `MANIFEST OK (stage pilot)` のまま。certification に
    ユーザー名・メールアドレス・6 桁以上の address は 0 件 (`...` の後の 16 進は pytest が省いた sha256 の digest)。

## null pilot (`results/pilot/`、2026-10-05、GPU)

- 認可: user 裁定 DH-4 (2026-10-05、AskUserQuestion。`.steering/20261004-generalization-probe-driver-sixth-review/decisions.md`)。範囲は null pilot
  (prereg §8.1 の 684 呼び出し) と `run.sh pilot` の機械判定まで。第 2 段の凍結と本走は含まない。記録は `.steering/20261005-generalization-probe-null-pilot/` (ローカル)。
- 実行環境: main = 41e4077 (PR #147、driver は 230 / 230 KILLED で certify 済み)。GPU = NVIDIA GeForce RTX 5060 Ti (16 GB、起動前の使用 1.6 GB・1%、
  他の長時間の job なし)。Ollama 0.32.12 (Windows native)・`qwen3:8b`。
- 起動の前の確認 (上の 6 回目の節の 5 点): 1〜4 は全て exit 0 で出力が空 (`[][]`・`[]`)。5 は運用 (pilot の間に Python の install・update をしていない)。
  開始の前に `--verify --stage pilot` = `MANIFEST OK (stage pilot)`・`driver_certification_violations` = `[]`・固定ファイルに未 commit の変更なし・
  `results/pilot/` なし。
- 起動 (PowerShell、同じ process の中で続けて): `$env:PYTHONUTF8 = "1"`・`$env:PYTHONHASHSEED = (Get-Content …/SEED).Trim()` (= 20261001) の後に
  `Start-Process -WindowStyle Hidden -PassThru -WorkingDirectory C:/ERRE-Sand_Box -FilePath uv -ArgumentList 'run','python','scripts/generalization_probe_driver.py','--stage','pilot'`
  (stdout・stderr は手元の log へ)。起動 2026-10-05 11:57:34 +09:00。
- 所要: driver の `started_at` 02:57:47.627 UTC 〜 `finished_at` 03:00:25.987 UTC = **約 2 分 38 秒** (684 呼び出し、約 4.3 呼び出し / 秒。
  起動から `started_at` までの約 13 秒は起動の検査)。stdout は `[driver] 100 calls` 〜 `[driver] 600 calls` の 6 行と `[driver] exit_reason=completed`、
  stderr は空。
- provenance (`provenance.json`): `exit_reason` = `completed`・`status` = null (`not_computed` ではない)・`anomalies` = []・`n_sent` = `n_records` = 684・
  `n_resends` = 0・`n_finish_length` = 0・`pinned_changed` = []・`manifest_problems_at_publication` = []・`read_back_problems` = []・`published` = true・
  `driver_sha256`・`records_sha256`・`meta_sha256` は現在のファイルと一致。`git_dirty` = true は未追跡のファイル (手元の sketch の出力・
  書きかけの `results/pilot/` 等。`git status --porcelain` は未追跡を含む) による。固定ファイルの照合は `pinned_changed` と manifest が別に見ている。
- observed (`meta.json`。provenance の開始と終了も同じ): `model_digest` = `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`・
  `ollama_version` = `0.32.12`・`template_sha256` = `ae370d884f108d16e7cc8fd5259ebc5773a0afa6e078b11f4ed7e39a27e0dfc4`。
- 記録の記述 (判定ではない): KNOW 108・M_A / M_A_rot / M_B / M_B_rot 各 144。parse の ⊥ 0・`raw` = null 0・call_index は 0〜683 で一意・
  masked の replicate は 50〜55。`attempts.jsonl` は 684 行全てが `outcome` = `ok`・`done_reason` = `stop`。
- 機械判定: run.sh の前に起動の前の確認 1〜4 をもう一度 (全て空。run.sh を動かす Git Bash の `PYTHONPATH`・`PYTHONHOME` も空)。
  `bash experiments/20261001-generalization-probe-pilot/run.sh pilot` (12:00:55〜12:01:08 +09:00) → `MANIFEST OK (stage pilot)` →
  `[run.sh] pilot: repeat byte-identical`・exit 0。
- **`gate.json` の結論** (値は gate.json から写した): `"decision": "GO"`・`"R": 18`・`"reasons": ["spike-in OC passed"]`・`"status": "computed"`・
  `"knowledge_failures": []`・`"masked_bottom_rates"` = A / A_rot / B / B_rot とも 0.0・`"masked_max_bottom": 0.0`・`"null_C": 0.008680555555555556`。
  OC (R = 18、`"size_cap": 0.065`): `"checks"` = calibrated・power_no_go・power_pass・size_no_go・size_pass が全て true、`"ok": true`。
  `at_plant` (2τ) は pass 1.0・no_go 0.0 (`realized_C` 0.6002896412037038)、`at_tau` は pass 0.003・no_go 0.0025 (`realized_C` 0.29976475694444443)、
  `at_zero` は pass 0.0・no_go 1.0 (`direction` −1・`realized_C` 9.490740740740742e-05)。
- 本走への帰結 (prereg §8.3 の envelope): 本走の arm ごとの ⊥ 率の上限は min(0.2, 0.0 + 0.05) = **0.05**。pilot の記録は本走の verdict に使わない
  (prereg §8.1)。第 2 段の凍結 (prereg §9.3) と本走は、それぞれ別の user 裁定。
- 改行: `gate.json` は pilot_gate の script が Windows のテキストモードで書いたので、手元の作業木では CRLF だった (他の 4 ファイルは LF)。
  `.gitattributes` が `*.json` を LF に固定するので、commit される正本は LF。manifest は gate.json を JSON の値で照合し (入力の sha256 は
  records・meta・certification・見取り図で、どれも LF)、bytes は照合しない。第 2 段で `manifest_main.json` が gate.json の sha256 を封印するときは、
  checkout した LF の版から取る。

## 第 2 段の凍結 (`manifest_main.json`、2026-10-05、CPU のみ)

- 認可: user 裁定 DP-3 (2026-10-05、AskUserQuestion。`.steering/20261005-generalization-probe-null-pilot/decisions.md`)。範囲は第 2 段の凍結
  (prereg §9.3) まで。本走 (§9.4) は含まない (さらに別の user 裁定)。記録は `.steering/20261005-generalization-probe-stage2-freeze/` (ローカル)。
- 開始の前 (main = de7cbaa、PR #148): `--verify --stage pilot` = `MANIFEST OK (stage pilot)`・`driver_certification_violations` = `[]`・
  第 2 段の照合の予行 (`--verify --stage main`) は `cannot read …/manifest_main.json` と `NOT FROZEN: prereg: status is not FROZEN …` の 2 点だけ。
  封印の対象 34 ファイル (`FROZEN_FILES` + `MAIN_EVIDENCE`) の作業木の bytes が HEAD の blob と同じ (`git hash-object --no-filters` = `git rev-parse HEAD:<path>`)・
  `results/pilot/gate.json` の CR 0 (上の「改行」の注意を確かめた)。`results/run/` なし。
- 変更: prereg の status 行 (3 行目) だけ。新しい行 = `- status: **FROZEN** (2026-10-05、user 裁定 DP-3。第 2 段の封印 = 確認実験。第 1 段 PILOT-FROZEN は 2026-10-02、DU-4)`。
  本文の他の行 (§13 の「状態」の欄を含む) は第 1 段のまま (変えると第 1 段の封印の照合が落ちる)。status 行を除いた本文の sha256
  (`prereg_body_sha256` = `777df23b…5b109`) は第 1 段の `manifest.json` の値と同じ。
- `uv run python scripts/generalization_probe_manifest.py --write --stage main` → `wrote experiments/20261001-generalization-probe-pilot/manifest_main.json (34 files)`。
  `manifest_main.json` の sha256 = `5395d9ed63fe85c7f479737397b28d19a49fe588d96395d5d242964254a554ee` (4,484 bytes・LF・CR 0)。
  内訳 = 第 1 段の対象 25 + 足した証拠 (`MAIN_EVIDENCE`) 9。第 1 段の対象のうち prereg 以外の 24 ファイルの sha256 は第 1 段の値と同じ。
  prereg は FROZEN の版の全文 (`c9012360…78c4f6`)。足した証拠のうち
  `manifest.json` = `0d72b99c…048d0ad0`・`results/pilot/gate.json` = `28d4e258…7c612c939`。
- `PYTHONUTF8=1 PYTHONHASHSEED=20261001 uv run python scripts/generalization_probe_manifest.py --verify --stage main` → `MANIFEST OK (stage main)`・exit 0。
  = 第 1 段の封印・pilot の判定の再計算 (GO・R 18・masked の最大 ⊥ 率・observed)・入力の sha256・provenance の 3 項目・driver の certification・
  status = FROZEN が全て通った (prereg §9.3 の 1)。
- 注意 (設計どおり): status 行を変えた後は、`--verify --stage pilot` (と `run.sh pilot`) は
  `MISMATCH: …/prereg.md: sha256 differs from the frozen manifest` で止まる (exit 1)。第 1 段の `manifest.json` は prereg の全文の sha256 を持ち、
  第 2 段の照合 (`stage1_seal_violations`) だけが prereg を `prereg_body_sha256` (status 行を除く) で比べる。pilot の判定の再計算は第 2 段の照合
  (`pilot_gate_violations`) が担う。以後の照合は `--stage main` で行う。

# Issue 003 (I3): reproducibility — capture script + committed golden + W4 二層 fidelity anchor + Win/WSL byte-parity + arc-log
verify_level: recheck   # AC 直結（決定性 / cross-platform byte-parity）= 再現性 witness、独立再走対象

## Goal
traversal 実行の再現性を確立する: `--capture/--verify` script + **committed 決定論 golden**（Ollama-free）+
**W4**（geometry checksum + 6桁量子化〔provenance 文字列含む〕+ 二層 fidelity anchor）+ **Win/WSL byte-parity 実測** +
`docs/research-positioning.md §8` arc-log 追記。これで「traversal run が cross-platform に再現可能」を witness。

## Background
FROZEN ADR + design-final-ref.md。golden fixture 形 = `tests/fixtures/m4_society_live_golden/`・phase4b golden
（decisions/ecl_trace/envelope_stream/expected_placement/manifest）。script 骨格 =
`scripts/aha_phase4b_two_phase_live_capture.py`。6桁量子化 = `handoff._quantize_embedded_json`（provenance 生
serialized 文字列を projection 境界で再量子化、libm cos/sin drift 対策、`feedback_golden_crossplatform_float_drift`）。
WSL bake 環境 = `/root/erre-sandbox` venv（httpx==0.28.1 pin、`reference_g_gear_host`）。Codex MEDIUM-3（二層 anchor）反映。

## Scope
### In
- 新規 `scripts/aha_traversal_live_capture.py`（`--capture`/`--verify`、phase4b script 骨格踏襲、Ollama-free 決定論）。
- 新規 `tests/fixtures/aha_traversal_golden/`（decisions/ecl_trace/envelope_stream/expected_placement/manifest）bake。
  6桁量子化（emitted float + envelope_provenance 生 serialized 文字列も projection 境界で再量子化）。
- `test_traversal_live.py`（W4 部）:
  - `test_traversal_golden_matches`: committed golden を `--verify` で byte-identical（checksum 一致）。
  - `test_traversal_fidelity_anchor`: **A** = `run_two_phase_capture(knob=None)`≡baseline byte-parity（既存 test 流用/拡張）
    / **B** = traversal driver `knob=None` が同一 scripted plan/obs 下で **sampling fields 以外差分ゼロ**（差分許容
    フィールド allowlist、plan-source 差し替え・obs 注入・再量子化境界まで pin）。
- **Win/WSL byte-parity 実測**: WSL Ubuntu-22.04（`/root/erre-sandbox` venv）で golden 再 bake、checksum/placement
  byte 一致（`feedback_golden_crossplatform_float_drift` 手順、scratchpad script + `MSYS_NO_PATHCONV=1 wsl ...`）。
- `docs/research-positioning.md §8` arc-log に construction ログ 1 エントリ追記（tracked）。
### Out
- real qwen3+embedding sealed 実走（別 spend ratify）。
- effect/divergence/floor/aha proxy/verdict emit。organ 6ファイル改変。

## Allowed Files
- `scripts/aha_traversal_live_capture.py`（新規）
- `tests/fixtures/aha_traversal_golden/*`（新規、committed golden）
- `tests/test_integration/test_traversal_live.py`（I1/I2 から拡張、W4）
- `docs/research-positioning.md`（§8 arc-log 追記）
- **無改変厳守**: organ 6ファイル + `two_phase_live.py` + `handoff._quantize_embedded_json`（read-only 再利用）

## Acceptance Criteria（AC↔test）
- I3-G1 `test_traversal_golden_matches`: committed golden `--verify` byte-identical（checksum 一致）。
- I3-G2 `test_traversal_fidelity_anchor`: anchor A（knob=None≡baseline）+ anchor B（knob=None が sampling fields
  以外差分ゼロ、allowlist）。
- I3-G3（byte-parity 実測、開発者手順）: WSL Ubuntu-22.04 再 bake で checksum/placement byte 一致（Win==Linux）。
- I3-G4: `docs/research-positioning.md §8` arc-log 追記（construction ログ、over-read しない文面）。
- CI parity: `pwsh scripts/dev/pre-push-check.ps1` 4 段全緑（既存 v0/v1/m2/m4/phase4b golden 回帰ゼロ、PYTHONUTF8=1）。

## Test Plan
`pytest -q tests/test_integration/test_traversal_live.py` 全 W1-W4 + pre-push 4 段 + WSL byte-parity 実測。

## Stop Conditions
- 全 AC 緑（Done）。
- committed golden が Win/WSL で byte 不一致 → provenance 文字列を含む 6桁量子化の projection 境界漏れを塞ぐ
  （`feedback_golden_crossplatform_float_drift` §3、parse→量子化→再 dump）。
- fidelity anchor B の diff が sampling fields 外に出る → 複製 drift、driver を organ 挙動に一致させる（無改変で）。
- organ 改変を要する → Stop→superseding ADR。budget 到達 → Stop。

## Dependencies
- I1（traversal driver core）+ I2（firing witnesses、golden に firing 記録を含めるため）。

## Status
done (I3-G3 の WSL 再bake は blocker、下記参照)

## Execution Result

**Status: DONE（I3-G1/G2/G4 緑、I3-G3 は byte-parity-ready 状態で blocker 明示）**。

### 変更ファイル
- 新規 `scripts/aha_traversal_live_capture.py`（`--capture`/`--verify`、phase4b 骨格踏襲、Ollama-free）。
- 新規 `tests/fixtures/aha_traversal_golden/`（manifest.json / ecl_trace.jsonl / decisions.jsonl /
  envelope_stream.jsonl / traversal_firing_annotation.json、単一エージェント 4-artifact shape、
  `expected_placement.jsonl` は M2/M4 多エージェント配置専用の別 render 経路ゆえ非対象＝
  `render_golden`/ecl_v0_golden/phase4b と同じ shape）。
- `tests/test_integration/test_traversal_live.py`（W4 部、+4 test: golden_matches / fidelity_anchor_a /
  fidelity_anchor_b / diff helper、15 test に拡張）。
- `docs/research-positioning.md §8`（arc-log 1 entry 追記、I1-I3 通し）。

### golden checksum + 量子化 discipline
`replay_checksum = f80cc244ca0247154fb82afce6aa6488e8ffa35ba0be64c14563a999cebf410b`。
`handoff.render_golden`/`decisions_to_jsonl`/`canonical_dumps`（無改変・read-only）を通した結果、
**provenance 再量子化を通した**（`decision_to_dict` 内 `_quantize_embedded_json` が
`envelope_provenance` の生 serialized 文字列を projection 境界で自動再量子化、追加コードなし
= 既存 apparatus がそのまま適用）。in-memory shortcut は使わず `--verify` は committed
`decisions.jsonl` の JSONL テキストを `recorded_calls_from_jsonl` で再構築して replay（I2 review
LOW-4 の教訓を継承）。**honest 観察**: `TRAVERSAL_PHYSICS_TICKS_PER_COGNITION=2000`（I1 凍結値）×
5 tick = 10,000 物理行、`ecl_trace.jsonl` が **5.3MB**（既存 golden 群の 13-60 倍、m4_society が
最大既存 392KB）。物理ステップ数を減らせば小さくなるが、それは I1 の凍結 calibration 値を
成績合わせで緩めることになるため**しない**（tune-to-pass 禁止の帰結を honest に受け入れた）。

### W4 anchor A/B 結果
- **anchor A**（`run_two_phase_capture(knob=None)` ≡ `run_ecl_loop`、traversal 固有 seed/obs/scripted-client
  で再確認）: `test_traversal_fidelity_anchor_a_matches_run_ecl_loop` 緑（checksum + decisions_jsonl + rows
  の 3 点 byte-parity）。
- **anchor B**（knob-on vs knob=None の decision diff が sampling 3 field allowlist の外に漏れない）:
  `test_traversal_fidelity_anchor_b_knob_diff_confined_to_sampling` 緑。実装中に **run_id を on/off で
  分けていたバグ**（`EclRecordMode.substream` が `run_id` で jitter RNG をキー化するため、別 run_id は
  geometry checksum を偽陽性で崩す）を検出・修正 → 同一 run_id に統一して pass。leak 検出はゼロ、
  allowlist 内の実差分は非 vacuous に確認。

### Win/WSL byte-parity 実測（I3-G3、blocker を正直に報告）
**byte-parity-ready 状態は確立**: golden は M4/phase4b/ECL v0 と**同一**の量子化・serialization
パイプライン（`canonical_dumps` 6桁量子化 + `_quantize_embedded_json` provenance 再量子化）を
無改変で経由しており、これらが既に実測 Win/WSL byte-parity を通している discipline をそのまま
継承している（新規の量子化漏れ経路を導入していない）。
**実際の WSL 再bake試行は blocker で完了せず**: WSL Ubuntu-22.04 (`/root/erre-sandbox`) は到達可能
（venv 確認・httpx==0.28.1 pin 一致）だが、**`git log` 確認の結果 origin/main から 261 commit 遅れ**
（`206b24b` = m9-c-spike 時点、`integration/embodied/` package 自体が存在しない = M2/M4/phase4b/ECL v0
すべて未到達の古さ）。`git fetch` は `forced update` を報告（OSS 公開 cleanup による履歴書き換えの影響と
推定）。ファイルを個別コピーしようにも依存先パッケージ全体が欠落しており不可能と判明、コピー試行
（1 ファイル）を確認後 **削除して原状回復**（WSL 環境に一切の残留変更なし、`git status --porcelain`
で確認済）。WSL checkout を `git fetch`+reset で追従させる操作は破壊的かつ本タスクの権限外と判断し
実行しなかった。**成績合わせでこの検証を省略・偽装しない** — 正直な blocker として報告し、
Windows 側の byte-parity-ready 状態（量子化discipline適用済）を実質的 deliverable として land する。
次工程候補: main が WSL checkout の更新（fetch+reset、別途承認）を引き取るか、fresh WSL clone で
再bakeする developer procedure として持ち越す。

### arc-log 文面（over-read 確認）
`docs/research-positioning.md §8` に 1 entry 追記。「construction (scripted traversal harness で
二相 knob が traversal 自身が earn した λ>0 tick で embodied 発火する舞台を建てた) であって
emergent traversal でも aha 実在測定でもない」「firing ≈ 恒等式・符号確認のみ、over-read 禁止、
5 機序分離継承、door② UNMET・door CLOSED・R-budget=0・holding 不可侵」を明記。
verdict/effect/divergence/floor/aha proxy の主張は一切含まない。

### test 結果
- `pytest -v tests/test_integration/test_traversal_live.py`: **15 passed**（W1-W4 全部）。
- `pytest -q tests/test_integration/test_two_phase_live.py`: **20 passed**（既存回帰ゼロ）。
- `pytest -q tests/test_integration/ -k golden`: **41 passed**（既存 v0/m2/m4/phase4b golden 含め全緑）。
- **フル pre-push 相当**: `ruff format --check src tests` 緑（568 files）/ `ruff check src tests` 緑 /
  `mypy src` 緑（244 files）/ `pytest -q --ignore=tests/test_godot`: **3802 passed, 52 skipped**
  （skip は環境依存の既存条件、無関係）。
- script 自体（`scripts/aha_traversal_live_capture.py`）: ruff format/check 緑（`ERA001` 誤検知の
  divider コメントのみ言い回し修正）、`T201`(print) は既存 script 群（phase4b/ecl_v0_golden）と
  同じ pre-existing 状態（`scripts/` は pre-push-check.ps1 の対象外、`mypy scripts/*.py` 単独実行時の
  `import-untyped` も既存 script 群と同一の pre-existing 挙動、`mypy src` は無関係で緑）。

### organ 無改変
`git diff --stat` を organ 6ファイル + `two_phase_live.py` + `live_v1.py` + `live.py` +
`traversal_live.py`（I1/I2 成果物、I3 では touch せず）に対し実行、出力なし（空）。

### guard 遵守
effect/divergence/floor/aha proxy/verdict は一切 emit していない（`test_traversal_measurement_guard`
が `traversal_live.py` 全体を継続 AST スキャン、script/golden/arc-log にも同種主張なし）。
`traversal_firing_annotation.json` は non-gate side file（`verdict: null`、`hard_gate: false`）。
GPL import なし。think=false 継続。

### blocker
**I3-G3（WSL 再bake）のみ blocker**（上記参照、byte-parity-ready 状態は確立・実 WSL 実測は環境
staleness で未完）。他は全 AC 緑。organ 改変は不要だった。

### 追記（code-review MEDIUM 2 + LOW 2 反映、user 裁定 DA-9 — golden 5.1MB 受容 / WSL byte-parity は
ready-land + follow-up）
- **M-1 golden-match test の非 hermetic 修正**: `verify()` に `annotation_dir: Path | None = None`
  kwarg を追加（既定 = golden_dir、CLI `--verify` は従来通り golden 隣に書く）。
  `test_traversal_golden_matches` は `tmp_path` を渡すよう変更 + **committed golden の全ファイルを
  verify 前後で byte snapshot 比較**する assert を追加（cross-test 実行順依存のない自己完結 hermeticity
  witness）。加えて **`traversal_firing_annotation.json` の書き出しを plain `json.dumps(indent=2)` から
  `handoff.canonical_dumps`（6桁量子化 + sort_keys + compact）へ変更**し、committed side file 自体の
  float drift 経路も封鎖。CLI `--verify` で committed golden を再生成・確認（checksum 群不変を確認）。
- **M-2 arc-log known-limitation 明示**: `docs/research-positioning.md` arc-log entry に
  「Win/WSL byte-parity は同一量子化パイプライン継承で byte-parity-ready だが、WSL checkout の
  261-commit divergence（OSS cleanup 履歴 force-update 由来）により物理再bake は本タスク未実施
  （follow-up developer step、known-limitation）」を追記（over-read 追加なし、DA-9 disclosure 要求に整合）。
- **LOW-1 script を AST guard 対象に**: `test_traversal_measurement_guard` の走査タプルに
  `(_SCRIPT_SRC, False)` を追加（`scripts/aha_traversal_live_capture.py` も継続 AST スキャン対象）。
- **LOW-2 annotation を committed decisions replay 源に**: `verify()` の firing annotation 計算を
  fresh record run（`traversal_firing_summary`、内部で新規 `run_traversal_capture` を起こす）から、
  新設 `_committed_firing_annotation()`（`handoff.recorded_calls_from_jsonl` で得た **committed
  decisions を 2 回 spied replay**、phase4b `two_phase_firing()` と同型）へ変更。
  `record_knob_on_pinned` が **golden 自身の committed knob-on record** を直接 pin するようになった
  （実測: `record_knob_on_pinned=True` 継続、CLI 再実行で確認）。
- スキップ: LOW-3（K_ECL import 源統一）は値同一(8)ゆえ指示通り未対応。

**再検証**: `pytest -q tests/test_integration/test_traversal_live.py` = **15 passed**（維持）。
**hermeticity**: テスト内 byte-snapshot assert が pass（verify 前後で committed golden 全ファイル
byte-identical）+ 外形 `git status --porcelain tests/fixtures/aha_traversal_golden/` はテスト実行前後で
`?? tests/fixtures/aha_traversal_golden/`（未 track ディレクトリそのもの、テスト起因の変更ではない）
のみで不変（このディレクトリは main 側でまだ commit されていないため per-file diff は git 側では
検出不能 — commit 後の regression には in-test byte-snapshot が主たる保証）。
`pytest -q tests/test_integration -k golden` = 41 passed（既存 golden 回帰ゼロ）。
`ruff format --check` / `ruff check` / `mypy src`（対象、markdown除く）= 全緑。
organ 6ファイル + `two_phase_live.py` + `handoff.py` + `live_v1.py` + `live.py` +
`traversal_live.py` の `git diff --stat` = 空（無改変維持）。

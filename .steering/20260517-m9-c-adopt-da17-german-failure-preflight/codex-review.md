# DA-17 ADR Codex Review (HIGH / MEDIUM / LOW)

## HIGH (必ず反映、merge 前に修正)
- [HIGH-1] 観点 F: H8 pre-check 手順が seed/temperature noise を検証できない記述になっています。`next-session-prompt-FINAL-pr5-corpus-rebalance.md:21-23` は「stim shard 再生成は不要、bootstrap seed 変更」と読めますが、`decisions.md:810-813` は「再採取 + within-language d 再計算」です。bootstrap だけ変えても生成 seed noise は検証不能です。修正案: seed 0/100/1000 ごとに v4 LoRA-on と matched no-LoRA shard を再生成し、同一 stim YAML / sampling params で MPNet de within-language d を再計算する、と明記してください。
- [HIGH-2] 観点 F: H8 判定基準の `MPNet de Δ` が未定義です。`next-session-prompt-FINAL-pr5-corpus-rebalance.md:73-77` は Δ の基準が v3→v4 delta なのか、v4 LoRA-on vs no-LoRA の within-language d なのか曖昧です。修正案: 指標名を `mpnet_de_within_language_d` などに固定し、閾値と gray zone の扱いを明文化してください。
- [HIGH-3] PR position: doc-only PR と矛盾する tracked diff があります。`design.md:5-7` / `design.md:32-33` は doc-only・修正ファイルなしとしますが、現在の diff では `uv.lock:658` / `uv.lock:711` に `scikit-learn` 追加等の非 doc 変更があります。修正案: 本 PR から `uv.lock` を除外するか、別 dependency PR に分離してください。

## MEDIUM (採否判断、decisions.md に記録)
- [MEDIUM-1] 観点 B: H5 の qualitative 結論がやや強すぎます。`decisions.md:146-150` は `"Pflicht / Maxime / Sittlichkeit / unbedingter Befehl"` 等を頻出語として挙げますが、直前の 10 sample `decisions.md:102-142` には多くが出ていません。`decisions.md:584-586` の「10 件全てで register shift」も過剰です。修正案: 「sample 10 からの示唆」に弱め、H5 は定量 lexical/function-word audit 待ちと記録してください。
- [MEDIUM-2] 観点 B: H2 evidence-against に evidence-for が混入しています。`decisions.md:502-505` は「en に capacity が流れ、de が degrade」と H2/H4 と整合する説明であり、反証ではありません。修正案: evidence-for へ移すか、反証として成立する文に書き換えてください。
- [MEDIUM-3] 観点 C: hypothesis numbering collision が 1 箇所残っています。`decisions.md:872-879` の「H1 (ja silent sink)」は本 ADR の H1 ではなく subagent H1 / 本 ADR H4 です。修正案: `H4 (ja silent sink; subagent H1)` に置換してください。
- [MEDIUM-4] 観点 A: DA17-2 pairing は stimulus_key の 1 件目採用で、tick/turn_index 一致を保証していません。`_da17_2_inspect.py:63-76` と `decisions.md:92-96`。表示 sample は tick が一致していますが、script 上は invariant ではありません。修正案: `(stimulus_key, tick, turn_index)` join、または tick mismatch 件数を出力して 0 件確認を記録してください。

## LOW (defer 可、blockers.md に記録)
- [LOW-1] tasklist が実態に追随していません。`tasklist.md:9-47` は DA17-1〜DA17-7 / Codex review 起票が未完了のままですが、`decisions.md` と next prompt は作成済です。修正案: merge 前に checkbox を更新してください。
- [LOW-2] `_da17_2_inspect.py:1` は「commit せず」と書いていますが、`design.md:120-122` は再現性のため commit としています。修正案: docstring を「ad-hoc reproducibility script」に修正してください。

## verdict
- ADOPT-WITH-CHANGES
- DA17-1/DA17-3/DA17-4/DA17-5 の主要数値・file line claim は概ね根拠と一致します。ただし H8 pre-check の実行定義がこのままだと PR-5 の判断を誤るため、HIGH 修正後に merge 可能です。

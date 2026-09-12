# データ — 論文 02 Phase 0

## 入力

凍結 context bank **8 本** (`cproper-ctx-0` … `cproper-ctx-7`)。
`bank_fixtures.build_competing_cue_substrate` + `run_provenance_pass` で
**C-proper と同一手順・同一 id** で生成する。したがって LLM に渡る
`(system_prompt, user_prompt, sampling)` は Phase 3 実走と同じ形になり、
pilot の parse 実測が実走の予測として意味を持つ。

provenance pass は **決定的な mock** で駆動する (Ollama を消費しない)。
実 spend は M-loop の draw だけ。

## 出力 (`results/`)

`metrics-<role>-<model>.json` — **フラットなスカラのみ**。
ネストも配列も持たない。キー集合は driver の whitelist と完全一致する。

**保存しないもの**: 生応答 / 選ばれた zone / 引いた本数の内訳 /
`T_on`・`T_off` の別 / context ごとの何か。
これらは driver の型設計により **保存しない**のではなく **表現できない**
(`.steering/20260912-paper02-phase0/design-final.md` §1)。

## 版

- モデル digest / ollama version / uv.lock sha256 は
  `results/metrics-*.json` に実測値が入る (env.md に転記)。

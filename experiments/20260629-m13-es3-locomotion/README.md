# M13-ES3 — locomotion → sampling channel の verdict (backup / provenance)

> **このディレクトリは実験の再走環境ではない。** 追跡外だった 1 次成果物を
> **git 追跡下へ退避**し、来歴を固定するためのものである。

## 何が置いてあるか

| ファイル | 内容 |
|---|---|
| `data/raw/verdict-forensic.json` | ES-3 の**機械可読 verdict** (11,743 B)。`D_loco` / CI / 全 15 cell の breakdown / 64 walk-seed ごとの `D_loco^(b)` / ablation・positive control の実測値 |

**SHA-256** = `24c6d3ba479b17897ac99d32e91e60679a9cff5dc0896d49d0ba501120c385a2` (11,743 B)

このファイルは `.gitattributes` の `experiments/**/data/raw/** -text -whitespace` の被覆下にあり、
**checkout 時の eol 変換を受けない** (原本は CRLF を含む。1 byte でも変わると上の SHA-256 が壊れる)。

## なぜ退避したか

`D_loco = 0.0468` は **論文 02 (`02-powered-null`) が引用する唯一の実測値**でありながら、
原本が `.steering/20260629-m13-es3-impl/verdict-forensic.json` にあり、
`.gitignore:6` (`.steering/`) の配下で**この作業機にしか存在しなかった**。
`docs/publication-plan.md` §10 が「これは同期の問題ではなく **backup の問題**」として
残件に挙げていたもの (`.steering/20260911-paper03-two-plane-determinism/blockers.md` B-P03-5)。

2026-09-11 の user 裁定により、`experiments/` へ commit して追跡下に置いた
(`.steering/20260911-ci-selection-ssot/decisions.md` DA-CIS-4)。

## 数値 (`verdict-forensic.json` より)

| 指標 | 値 | gate | 判定 |
|---|---|---|---|
| `verdict` | `GO` | — | — |
| `D_loco` (pooled median a_s) | 0.04682681825722385 | — | — |
| `ci_lower` (per-walk-seed bootstrap, 90%) | 0.04529199663455194 | ≥ `amp_floor` 0.02 | PASS (2.3×) |
| `ci_upper` | 0.04681628791857268 | — | — |
| measurement-valid cells | 15 / 15 | ≥ 8 | PASS |
| headroom-valid fraction | 1.0 | ≥ 0.5 | PASS |
| valid walk-seeds | 64 | ≥ 32 | PASS |
| `ablation_bit_equal` (None path vs gain=0) | `true` (max abs diff 0.0) | ≤ ZERO_TOL | PASS (恒等性) |
| `zone_function_d_loco` (positive control) | 7.401486830834377e-17 | ≤ 1e-9 | PASS (分離) |
| `max_repeat_penalty_var` (within-cell) | 1.9721522630525295e-31 | ≤ ZERO_TOL | PASS (発散特異 invariant) |

## claim 境界 (不可侵 — この数値から読んでよいこと / いけないこと)

`verdict-forensic.json` の `caveats` フィールドに凍結されている内容の要約である。
**要約でなく原文が正典**なので、引用するときは JSON の `caveats` を読むこと。

- **GO が意味するのは「歩行 → sampling チャネルが因果・分離・恒等性消失の形で配線されており、
  ES-4 / 発散実測へ進む資格がある」ことだけ**である。
  **歩行 → 創造的発散そのものの検定ではない** (それには LLM power が要り、当時 defer された)
- `NO_GO` は progressive な所見 (チャネル再設計) であって反証ではない。
  `INCONCLUSIVE` (apparatus 不正 / within-cell λ spread なし / headroom 飽和 /
  valid walk-seed 不足) とは区別される
- **非トートロジー性は positive control で実証されている**: zone-function control で
  λ=h(z) を強制すると `zone_function_d_loco` が ~0 に崩壊する。
  つまり estimand は **0 を取りうる**ので、blind walk 上の `D_loco=0.0468` は
  構成的に保証された値ではなく、実在する within-cell の locomotion 信号である
- 計算は deterministic (numpy / stdlib のみ、GPU も LLM も不要) で、再走 byte-identical

## 来歴

- **凍結 ADR**: `.steering/20260629-m13-es3-adr/design-final.md` (ローカル、追跡外)
- **人間可読の verdict**: `.steering/20260629-m13-es3-impl/verdict-result.md` (ローカル、追跡外)。
  `verdict-forensic.json` と対で「正典」を構成する。**本退避には含めていない**
  (user 裁定の対象が JSON 1 ファイルだったため)。追跡下へ移すかは別途判断する
- **実装 PR**: #34
- **本文での参照**: `docs/research-positioning.md` (H3 連鎖) / `docs/arasuji.md` ②
- **論文側の移送先**: `paper/gather.ps1` が `02-powered-null/data/raw/es3-verdict-forensic.json`
  へコピーする。SHA-256 の突合は `pwsh paper/gather.ps1 -Verify`

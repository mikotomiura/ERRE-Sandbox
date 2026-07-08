# M13 B 反復 frozen-context bank — a-priori power worksheet

Issue 004（I4、`loop/20260708-m13-b-code-impl/issues/004-power-worksheet.md`）の成果物。
FROZEN ADR `.steering/20260707-m13-b-impl-design/design-final.md` §I6（teeth named 閾値の proposal
+ power worksheet FROZEN 条件化）を、装置（`src/erre_sandbox/integration/embodied/bank_power.py`）
の a-priori 数値で確定する doc。

## Scope guard（binding、不可侵）

- 本 worksheet と `bank_power.py` は **construction（装置 buildability の立証）であって
  measurement（実 bank data の検定）でない**。実 bank annotation を一切読まない・bank driver
  （`bank.py`/`bank_fixtures.py`）を import しない・R-budget を消費しない（両 named family
  = SPDM-landscape / live-channel-conformance の外、`.steering/20260707-forward-primary-post-v1/`
  参照）。
- 数値はすべて **assumed（仮定）distribution に対する a-priori 計算**。実 bank data に対する検定は
  C-proper AUTHORIZE 後のみ（本 issue の Out スコープ）。

## 検定法（test method）

**Categorical 5-way multinomial power**（ES-4 Phase 0 型の Monte-Carlo 検定に倣う、写経元 import は
せず design のみ踏襲）。使う統計量 = **Pearson chi-square goodness-of-fit statistic**
`sum((observed_count - expected_count)^2 / expected_count)`（5 zone、自由度 df=4）。

帰無仮説の棄却臨界値は解析的な chi-square 表ではなく **null 分布を直接 Monte-Carlo simulation
した経験分位点**（`_null_critical_value`、base_dist から `n_replicates` 回 multinomial を draw し
帰無統計量の `1 - ALPHA_SIGNIFICANCE`（=0.05）分位点を取る）で校正する。これにより **scipy 依存ゼロ**
（`bank_power.py` は numpy + stdlib のみ）。power は同じ临界値に対し、`delta_tv` だけ base_dist から
ずらした alternative distribution から draw した統計量が臨界値を超える割合（検出率）。

## 最悪・代表 base distribution（worst-case + 代表）

| 種別 | zone 分布（5-way） | H(zone\|ctx) [bit] | 意味 |
|---|---|---|---|
| **代表（near-uniform）** | `[0.2, 0.2, 0.2, 0.2, 0.2]` | 2.32（最大） | zone-pick が健全に分散している基準ケース |
| **worst-case（collapse）** | `[0.96, 0.01, 0.01, 0.01, 0.01]` | 0.24（≈0） | `think=False` の empirical zone-marginal
  collapse（壁1&4 で観測された近-uniform でない退化）を模した劣化ケース |

worst-case は「1 zone が支配的で残り 4 zone にほぼ質量が無い」形。§I6(i) の懸念（H(zone|ctx)≈0）を
literal に表現する分布として採用。

## K context の pooling 仮定

**pooling=True（採用、K contexts を単一 test に pool）**: K 個の frozen context の draw を合算し
`n_total = M_min * K` として単一 chi-square 検定を走らせる仮定。これは「K 個の凍結 context が同一
alternative shift 方向を共有する」という **楽観的仮定**（各 context 独立に別々の弱い shift しか
示さない場合は過大評価になり得る、honest 限界）。`categorical_multinomial_power(..., pooling=False)`
は保守側（`n_total = M_min` のみ、K による増幅なし）を計算可能にしている。本 worksheet の named 閾値
確定は **pooling=True**（proposal の意図通り、K が estimability を確保する側）。

## named 閾値（proposal → 確定値）

FROZEN ADR §I6 の proposal（non-binding）を、本 worksheet の a-priori 数値で **確定**する
（`bank_power.py` の `M_MIN`/`K_MIN`/`DELTA_TV_MIN`/`POWER_MIN`/`H_MIN_BITS`/`RHO_MIN` と一致、
乖離なし）:

| 閾値 | proposal（ADR §I6） | 確定値（本 worksheet） | 乖離 |
|---|---|---|---|
| M_min | ~300 draw/(ctx,condition) | **300** | なし |
| K | ~8 frozen context | **8** | なし |
| delta_tv（δ_min, TV distance） | ~0.10 | **0.10** | なし |
| power | ≥0.8 | **0.8** | なし |
| H_min | ~0.5 bit | **0.5** | なし |
| rho（ρ） | ~0.5 | **0.5** | なし |

### 導出（a-priori 数値、seed 固定・決定的）

`categorical_multinomial_power(base_dist=[0.2]*5, delta_tv=0.10, m_draws=300, k_contexts=8,
pooling=True)`（seed=20260708、n_replicates=4000）→ **power=1.0**（≥0.8 を十分に満たす、
`n_total=2400` は 5-way chi-square に対し δ=0.10 TV shift を検出するには余裕がある）。M_min=300/
K=8 の proposal は代表分布（near-uniform）に対しては十分 buildable であり、そのまま確定して問題ない
（tune-to-pass ではない — proposal 値をそのまま a-priori 検算しただけで下方修正の必要が生じなかった）。

## (i) H_min/ρ は empirical gate 目標であって B は保証しない（honest、最重要）

**H_min（≥0.5 bit）/ ρ（≥50% context が H≥H_min）は empirical gate 目標であり、`bank_power.py` も
B 反復 bank apparatus も達成を保証しない。** これは construction 側が制御できない **empirical
property**（実 qwen3:8b の `think=False` decoding が zone-marginal を collapse させるか否か）に
依存するため。

機械的デモ（`test_bank_power_collapse_kills_power`）: 代表分布 `[0.2]*5` のまま、`delta_tv` だけ
proposal の 1/10（0.01）に下げる — これは「H(zone|ctx)≈0 の collapse regime では T_on/T_off の
**実際に達成可能な** distributional shift も同じく縮小する」ことを模した a-priori 感度チェック。
proposal 通りの `M_min=300`/`K=8`/pooling=True でも **power は 0.8 を大きく下回る**（実測
power≈0.18、`bank_power.py` docstring 参照）。

**副次的 honest 発見**: worst-case な degenerate 分布 `[0.96,0.01,0.01,0.01,0.01]` に同じ
collapse-scale delta を適用すると、逆に power は高いまま（実測 power≈0.95）。これは既に極小な cell
へ質量を移すと **相対変化が大きく**なり chi-square 統計量が敏感に反応するため（絶対量は小さくても
検出されやすい）。∴ **(i) の依存は「base distribution の形」単体でなく「実際に達成可能な delta_tv が
どれだけ小さいか」に宿る**ことを本装置は a-priori に明らかにする。実 bank data が degenerate な
zone-marginal を示しても、それだけで power が死ぬとは限らない — 真に懸念すべきは
「T_on/T_off 間で **実際に動く量**（achievable delta_tv）が think=False 決定論的傾向でゼロに
近づくケース」であり、これは construction 側からは検証不能な empirical property のまま
（bank annotation を見て初めて判明、B は保証しない）。

**これが §C4.3 T4 の line-close 経路そのものである**: H_min 未達（= 実 bank annotation で
H(zone|ctx)≈0 が観測される）なら T1 line-close → 両 R-budget family exhaust → arc-close 自動執行。
本 worksheet はその依存関係を **doc-only で honest に可視化**するのみで、実 bank data を見て初めて
どちらに転ぶかが決まる（壁1&4 の再来リスクは構造的に排除できない）。

## Reproducibility（reproducibility-discipline 準拠）

- **Seed**: `POWER_SEED_DEFAULT = 20260708`（`bank_power.py`、issue 起票日、result-independent に
  事前固定）。
- **1 コマンド再現**: `python -m pytest -q tests/test_integration/test_ecl_bank_power.py`
  （全 assertion が本 worksheet の数値と一致することを検証する named test）。
- **依存**: numpy のみ（コア依存、extras 不要）。scipy 非依存（Monte-Carlo null 校正で代替、
  上記「検定法」参照）。
- **凍結 apparatus**: `bank_power.py` は本 issue のみが新規作成する独立 module。将来の変更は
  superseding ADR を要する（§I6 が binding）。

## Ratification gate（DA-BIMPL-6）

本 worksheet が確定した named 閾値（proposal と乖離なし）は、統合前に Codex/user の ratify を要する
（本 issue の Done は「装置 buildable + worksheet 存在」まで、閾値 ratify は統合ゲート、issue 仕様
「Ratification Gate」節参照）。

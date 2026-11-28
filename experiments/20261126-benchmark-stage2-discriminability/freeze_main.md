# 判別性 gate 段 2 — 第 2 段 (本走) の凍結の記録 (prereg §J・§L)

- 日付: 2026-11-28
- prereg は status 行しか変えられないので (第 1 段の封印)、§L の「状態」の列を第 2 段の時点で埋めた表はここに書く。
  本 file は `manifest_main.json` に pin しない記録 (判定に使わない)。
- 第 2 段の封印 = `manifest_main.json` (`scripts/benchmark_stage2_freeze.py --write` が書き、本走の入口
  `scripts/benchmark_stage2_manifest_main.py` が driver の送信前・scorer の判定前に照合する。DD-12 H2)。
- **本 file・第 2 段の凍結は GPU・本走・driver の実行を authorize しない** (本走は別の user 裁定)。

## §J の条件

| 条件 | 中身 | 根拠 |
|---|---|---|
| pilot が 1 battery 以上で GO | v2 GO (R 32)・v3 GO (R 80)・O_time GO (R 138)・G STOP_POWER。入場は各 6 モデル、K 120・ΣM 24 | `results/pilot/gate.json` (PR #163) |
| driver と判別性 scorer の certification が全 KILLED・meta-test 成立 | 証明書 `pre_main` を、本走の入口の照合 (manifest_main) を対象に足して作り直した。結果は下の「証明書」 | `experiments/20261126-benchmark-stage2-driver/results/driver_mutation.json` |
| 見取り図を certify した stats で再計算し byte 一致 | 一時 dir に再計算 (約 10 分) し `results/sketch.json`・`fixture_diffs.json` と byte 一致。記録する sha は再計算の出力のもの | `freeze --write` の検査 3 |
| fixture の差の再計算と claim の併記の規則 | `results/fixture_diffs_main.json` を段 2 の割付・pilot の gate の R で計算 (排他的作成・`--check` MATCH)。陽性対照を除く方策の対で \|ΔC\| > Δ_min (0.10) は **v3 で 15 対** (最大 \|C\| 1.0、例: nearest_neighbor_ignoring_weather と before_success の差 1.064)、v2・O_time は 0 対、G は本走に入らない。v3 で名指した対の claim には、この 15 対を常に併記する | `results/fixture_diffs_main.json` |
| 計測台の gate 6 点の表 | 下の表 | 本 file |
| review で HIGH 0 | 本タスクの実装: code-reviewer (Opus) r1 HIGH 1 → 反映 → r2 HIGH 0、Codex (gpt-6.2-astra/xhigh) 1 回で HIGH 7 → 全て反映 (反映の確認は code-reviewer r2)。prereg の第 1 段は Codex r1〜r4 + Claude reviewer (§N) | `.steering/20261128-benchmark-stage2-freeze/` (decisions DF-8・DF-9) |
| user の ratify | 第 2 段 FROZEN への status 行の変更 | user 裁定 (AskUserQuestion) |
| `manifest_main.json` が第 1 段の封印を照合 | 検査 2 (`manifest.json` の sha・13 ファイル・status 行を正規化した本文)。書き手は `manifest.json` が pilot の凍結の commit b626962 の版であることも確かめる | `scripts/benchmark_stage2_manifest_main.py` |

## §L 計測台の hard gate 6 点 (状態 = 第 2 段の凍結の時点)

| gate | 本登録での中身 | 成り立たないときの扱い | 状態 (第 2 段) |
|---|---|---|---|
| 0 閉じた chain の登録 | §0 | 重なりを分離できない battery は外す | 済 (第 1 段) |
| 1 certification | driver・判別性 scorer・pilot gate・stats・本走の入口の照合の変異試験。期待する診断文・meta-test・hash を固定する | 全 KILLED でなければ第 2 段を凍結しない | 済 (下の「証明書」) |
| 2 前提の監査 | 単位の独立・依存の構造・交換可能性は不要・弱い帰無・renderer の相殺条件・parse がモデルに依らない | 前提が崩れる battery・手法は外す | 済。相殺条件の r の列の上の検査 = `plan.battery_checks` を本走の実 R (v2 32・v3 80・O_time 138) で計算して全項目が空 (`manifest_main.json` の `battery_checks` に記録、driver が送信前に再計算して照合) |
| 3 雑音の根拠 + spike-in の OC | §G | OC が示せない battery は STOP (power) で外す | 済。pilot gate で G = STOP_POWER (本走から外す)、v2・v3・O_time = GO |
| 4 形の見取り図 + 枝ごとの size | §I | size を守れない枝は外す | 済。第 1 段で door-close でない・size 合格、第 2 段で certify した stats の再計算が byte 一致 |
| 5 bridge + Codex | §M・§I.3・§J・Codex review | HIGH が残る間は凍結しない。Δ_min を超える方策の対は claim に常に併記する | 済。fixture の差は v3 で 15 対 (claim に併記)、review は上の表のとおり HIGH 0 |

## 証明書 (gate 1)

- 証明書: `experiments/20261126-benchmark-stage2-driver/results/driver_mutation.json` (version `pre_main`、
  sha256 `5e5dde4a81e978961b820701577011ab4c1be3a47326b80a3c0c1d69a00815b7`)
- 結果: **KILLED 303 / 303**、SURVIVED 0、理由違い (WRONG_REASON 等) 0、対照 (無変異) 緑、meta-test ok、
  source restored (sha256 一致) True、実行中の test / harness の不変 True。2026-11-28 18:35 起動、複製ツリー × 4 worker。
- 対象 (`target_sha256`): `benchmark_stage2_{driver,plan,units,records,pilot_gate,stats,fixtures,scorer,manifest_main}.py`
  と harness 自身、witness の test の file 13 個 (`tests/test_benchmark_stage2_driver/`、conftest・main_tree を含む)。前の証明書 (248 個) に、
  本走の入口の照合 manifest_main を対象に足した 56 個 (m01〜m47・d64〜d68・c57〜c60) を加え、c28 を消した
  (読めない fixture は判定の前に拒むので経路が無い。c60 が代わりに捕まえる)。
- `manifest_main.json` は証明書の sha・対象と witness の sha の集合・`inputs_sha256` (pilot の `gate.json`) を照合する (検査 4〜6)。

## 段 2 の外の module (検査 9)

driver・scorer から import で届く `scripts/` の module のうち、証明書と第 1 段が束ねないもの 14 個
(`generalization_probe_{battery,fixtures,pilot_gate,scorer}`・`o_time_probe_{battery,fixtures,pilot_gate,scorer}`・
`skill_experience_{battery,scorer}`・`skill_lever_{battery,scorer}`・`stage_b_{battery,scorer}`) は、
それぞれ既存の chain の封印 (`experiments/*/manifest*.json`) の sha と一致することを書き手が確かめ、
`manifest_main.json` の `external_sha256` に記録した。

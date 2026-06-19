# 01 — SWM（主観世界モデル）系の検証手法

> **いつ読むか**: エージェントの主観世界モデル（SubjectiveWorldModel）、個体化、
> STM carry（短期記憶持ち越し）効果を測りたいとき。
>
> **前提**: 共通の検証作法は [00-methodology.md](00-methodology.md) を先に読むこと。
> 本章はそれを SWM ドメインに適用した具体手法。
>
> **出典**: III-a replay/live chain（`.steering/20260615-iiia-*` / `20260616-iiia-*`）/
> saturation・engagement chain（`.steering/20260605-*` / `20260606-*` / `20260607-*`）/
> individuation S-series（`.steering/20260603-m10a-*`）。

---

## 1. individuation distance machinery（個体化距離の三分）

同一 base から作られた複数個体が「base を保持しつつ個体として分離する」ことを測る
ための距離計算群。役割が異なる 3 指標を**混同せず分離**して使うのが要点。

| 指標 | 役割 | 性質 |
|---|---|---|
| `world_model_overlap_jaccard` | 個体間の主観世界モデルの重なり（real metric、M11-C3b S3 で実装） | self-pair は非 VALID / canonical set / empty union は degenerate / trace 専用 provenance hash |
| centroid 距離 | semantic embedding の重心ずれで個体化を測る | encoder agreement gate（[00 §10](00-methodology.md)）と併用 |
| Burrows delta | **base 保持専用**。multi-individual が同 base で同値を出すのが成功条件 | 個体化の指標ではない。個体化は上記 2 つで測る |

設計上の不可侵原則（architecture.md §9.3）: **Burrows = base 保持専用**。個体化は
semantic centroid / belief variance / NarrativeArc drift など別 sidecar 系で測る。
この役割分離を破ると「base が壊れたのか個体化したのか」が判別できなくなる。

## 2. 飽和 probe → engagement instrument → hint adoption verdict

「SWM のヒントがエージェントに採用されているか」を段階的に検証する state-machine 型手法。

1. **飽和 probe**: 効果が飽和（dormancy）しているかを測る。verdict=INCONCLUSIVE なら
   上流の engagement floor を疑う（飽和の前にそもそも関与が足りない）。
2. **engagement instrument**: 関与量（emission）を独立に測る計器を導入。
3. **hint adoption verdict**: emission（出した量）と adoption（採用された量）を**分離**して
   判定する。
   - 実績: emission 0.913（healthy）に対し adoption 0.299（< 0.50）→ verdict =
     STATE_B_ADOPTION_REJECTED。dominant gate = `rejected_not_displayed`。
4. **not_displayed forensic**: 採用されない原因を同一 tick join で細分。
   - 根因 = **render/key contract mismatch**（LLM が実表示 bare key `study` に対し
     axis-prefix 形 `env/study` を emit）。
   - 教訓: 関与の計器は「出力したか」だけでなく「契約どおりの形で表示系に届いたか」まで
     見ないと、健全な emission を adoption 失敗と取り違える。

二段階 freeze の型: **Gate 1（契約修復）** = provably-displayed の emitted 比 < θ ∧
emission ≥ θ_e、**Gate 2（科学的結果）** = adoption ≥ 0.50 or 新 dominant gate。
Gate 1 PASS ∧ Gate 2 未達 = 「介入は成功したがシステムはまだ healthy でない」と
honest に切り分ける。

## 3. III-a replay driver（決定論リプレイ） + live carry trajectory contrast

「壁①（carry over churn）= STM carry が後続軌跡を変えるか」を測る現状の中核手法。
**replay と live を対にする**のが本質。

### 3.1 deterministic replay（S≡0 基準）

deterministic replay driver は上流軌跡を固定再生する。carry が下流を変えても上流が
動かないため、replay 環境では separation S ≡ 0。これが「replay≠live gap」の基準線になる。
（U5→U9 chain で確立。U8 GPU N=3 = NON-SATURATED CONCLUSIVE。）

### 3.2 live carry trajectory contrast（paired ON/OFF）

同 seed の live を `stm_carry=True`（ON）/ `False`（OFF）で**別 run** 走らせ、
total-trajectory 効果を測る。replay は S≡0 なので live のみが S>0 を観測しうる。
指標は 4 層（[00 §2](00-methodology.md) の primary/diagnostic 分離を適用）:

| 層 | 役割 | gate |
|---|---|---|
| **M0** manipulation/fidelity | `stm_carry` が唯一の toggle / ON は carry opportunity 非ゼロ / OFF はゼロ / config hash・seed 一致 | validity 前提。未充足 = INVALID_MEASUREMENT |
| **M1** distal separation magnitude | carry **下流の** distal trajectory（behavior/world/action/cognitive）**のみ**で距離 S。treatment-internal 変数は除外（tautology 回避） | **primary（必要条件）**。GO = S(ON−OFF) ≫ S(null) |
| **M2** boundedness/safety | S が暴走しない ∧ carry 値が cap±0.15・値域[−1,1] 内 ∧ 非劣性 analog | **primary** |
| **M3** separation growth | cap 殺傷 prognosis（cap が増幅を bounded offset 化 → growth≈0）ゆえ | **diagnostic-only**（gate にしない） |

distance は §1 の individuation distance machinery（`world_model_overlap_jaccard` /
centroid）を**再利用**する（frozen 非接触、[00 §7](00-methodology.md)）。

### 3.3 claim 境界（厳守）

- M1 GO = 「行動変容が存在する」必要条件であって、**発散・核命題の確定ではない**。
- M1 FAIL = 「frozen cap・この指標下で検出可能な効果なし」であって、carry 効果一般の
  否定ではない（low power に免疫でない）。
- claim は M1/M2 の bounded separation まで。growth/発散は cap 殺傷 prognosis 下で
  diagnostic-only。**発散の科学 verdict は依然 Gate B**（[.idea/verification/forward-divergence-gate-b.md](../../.idea/verification/forward-divergence-gate-b.md)）であり本手法ではない。
- bounded envelope: kant / N=3 single-persona / N=21 / I=6 / qwen3:8b base。
  NON-SATURATED = retention 能力の否定ではない（DA-U7-5）。

## 4. versioned measurement / scorer

測定手法を改訂したときに過去の verdict と混線しないよう、measurement / scorer を
バージョン管理する（`.steering/20260613-versioned-measurement-adr/` /
`20260613-versioned-scorer-impl/` / `20260614-versioned-verdict-cli/`）。改訂版で
再測定する際は、どの version で出た数値かを verdict に必ず添える。

## 5. H2 conformance + density audit

個体化を本走する前に「測定器が原理的に対象を示せるか」を事前検証する gate 群。

- **H2 conformance**: (axis,key) 交差の mean|Δvalue| を frozen 指標とし、片側
  permutation（`p_high ≤ 0.05`）で値の差を検定。presence 差を直接スコアしない
  （self-defeating な ③ env-zone-presence を retire した教訓）。canonical な density
  閾値 D*（strong 12 / medium 12 / weak 20、persistence max-over-seeds、Bonferroni 補正）を
  pre-register する。
- **density audit**: per-owner の distinct-other 数 D_i を測り `min(D_i) ≥ D_target`
  を gate にする。escalation は scipy 非依存の自前 Clopper-Pearson 上側信頼限界で判定
  （cutoff D_min ≤ 8、ρ_upper を stdlib で再検算して一致確認）。

---

## 結了（方法論的教訓）— M11-C3b 個体化 chain

> 以下は現役ではない。**探索し ADOPT negative で打ち切った**手法。現役規律の由来を
> 辿るために残す（[00 §5 会計分離](00-methodology.md) の実践例）。

M11-C3b（rikyu ja 個体化 pilot）は Layer B real run まで完走したが、verdict = **REJECT**
（PR #290）で chain を **terminate**（PR #294）。

- **失敗の中身**: 両 primary encoder の direction collapse + Burrows base retention fail。
  root cause は eval_run_golden の INSERT が `individual_layer_enabled` 列を省略し
  provenance=False になって matrix を誤認していた配線バグ（16 列拡張で解消）。
- **そこから採用された現役規律**:
  - **測定器妥当性の事前検証**を gate 化（→ 上記 §5 H2 conformance / density audit、
    「測定器が対象を示せない」BLK-1 を本走前に弾く）。
  - terminate は「completion + ADOPT negative」として honest に記録し、reactivate は
    別 ADR + 4 重 guard 経由のみ（[.idea/verification/future-individuation-m12.md](../../.idea/verification/future-individuation-m12.md)）。
  - frozen §9（Δ_self_max / margin 1.5× / threshold 0.02 / encoder / lib pin / N=2）は
    不可侵として凍結（[00 §7](00-methodology.md)）。

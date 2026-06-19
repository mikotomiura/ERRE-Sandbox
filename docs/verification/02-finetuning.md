# 02 — Fine-Tuning（LoRA / 選好最適化）系の検証手法

> **いつ読むか**: LoRA 再学習（retrain）や選好最適化（preference optimization）の
> 妥当性を検証したいとき、retrain を起票する前のゲート設計を確認したいとき。
>
> **前提**: 共通の検証作法は [00-methodology.md](00-methodology.md) を先に読むこと。
>
> **出典**: Plan B kant chain（`.steering/2026051*-*` 〜 `2026052*-*`）/
> retrain handoff 系の feedback memory（`feedback_retrain_*` / `feedback_source_stock_precheck_*` /
> `feedback_retrain_entry_two_stage_gate`）。

LoRA 再学習は GPU 3h+ を消費する高コスト工程なので、「走らせる前に止める」gate が
検証の中心になる。

---

## 1. 現役: LoRA retrain 2 段 entry gate

retrain PR の最初の go/no-go は **2 段**で押さえる（bundle skip 不可）。

| Gate | 内容 | PASS 条件 |
|---|---|---|
| **Gate 1** | source 確定 | source URI + provenance + licence + leakage check が揃う |
| **Gate 2** | dry-run | `--dry-run` で hard floor（v5）と既存 gate（DA-14 等）が**同時** PASS |

この前段に **Gate 0（source 在庫 pre-check）** を置く。`--en-booster-source` のような
external-source flag が**存在すること ≠ 在庫があること**。retrain handoff prompt には
「source 在庫 audit（en_total > 0 を empirical に確認）」を Gate 1 の前に必ず入れる。

## 2. 現役: retrain handoff 4 工程の明示

retrain の handoff prompt は「**retrain → eval shard 生成 → rescore → verdict**」の
4 工程を必ず明示する。retrain 完了 ≠ verdict-ready であり、間に SGLang inference run
（eval shard 生成）が挟まる。この工程を省くと「学習したのに評価できない」状態に陥る。

## 3. 現役: extras-only 依存の 3 点セット

sentence-transformers / sklearn / torch / peft / sglang / trl 等の extras-only 依存を
新規 `src/` に import するときは、以下 3 点を**欠落させない**（[00 §11](00-methodology.md)）。

1. lazy import（モジュール top-level で import しない）
2. mypy `ignore_missing_imports` 追加
3. test で `pytest.importorskip("<dep>")`

## 4. 現役: 評価 gate の作法

- **encoder agreement direction gate**: 効果方向は単一 encoder に依存させず、
  per-encoder median 床比 + `direction_all_*` を課す（[00 §10](00-methodology.md)）。
  一つでも符号反転したら FAIL、緩和禁止。
- **Burrows = base retention 専用**: 選好最適化後も base スタイルが保持されているかを
  Burrows で確認する。Burrows を「個性を増やす」指標として使わない（[01 §1](01-swm.md) と同じ役割分離）。
- **KTO label weighting**（`rebind_to_kto_w_weight`）: KTO の label imbalance を、
  TRL 正準 band（trl 0.29.1 experimental.kto、Eq.(8)）で少数派を up-weight して補正。
  解消範囲は「weight 未設定のみ」で、縮退・binary floor・structural ceiling は別軸
  unresolved。**over-claim 禁止**（解消した範囲だけを主張する）。

## 5. 現役: 診断は binding 成果物を省略してはならない

既存 stock を使った安価な診断で gate が通っても、ADR で約束した新規生成工程を
省略してはならない。

- stock 診断の結果は `STOCK_DIAGNOSTIC_PASS` に留め、binding GO とは**分離**する。
- provenance tag + 比率を必ず付ける。fallback PASS のときは quality_tradeoff を明示。

---

## 結了（方法論的教訓）— Plan B kant Burrows 選好最適化

> 以下は現役ではない。**探索し ADOPT negative で打ち切った**手法。現役規律
> （§4 encoder direction gate、§5 binding 成果物省略禁止）の由来を辿るために残す。

Plan B kant は「Burrows 選好最適化で kant らしさを強化する」研究プログラムで、
最終的に研究プログラムとして **terminate**（PR #242 MERGED）した。

### 探索の経緯

| PR | 案 | 結果 |
|---|---|---|
| PR-16 | 案 A: KL on n-gram（λ=0.3） | ADOPT 不成立。Burrows row は +2.666pt の effective signal が出たが、Vendi diversity primary 3/3 negative と**同時達成不可**（inverted-U、peak λ=0.3） |
| PR-17〜PR-20 | 案 B: composite Burrows preference optimization（KTO） | 4 gate 全 FAIL → corpus 拡張 + rebind 2 段事前 binding |
| PR-21 | 案 B 本実行（KTO τ=1.0 single-seed） | **REJECT**。Burrows PASS + ICC 0.9375 + throughput PASS だが **encoder agreement FAIL**（e5large +0.4219 で符号反転、`direction_all_negative=False`） |

### なぜ ADOPT negative だったか

- **収束的失敗**: case A（KL）と case B（composite）が同一軸（**Vendi-Burrows
  simultaneity**）で失敗した。Burrows で個性を強めると diversity が落ちる、という
  構造的トレードオフ。
- **structural ceiling**: roundtrip 0.6122 < 0.80 soft floor。corpus を 1.81× に
  拡張しても +0.0pt、K 拡張ではむしろ 0.612→0.424 と悪化（corpus-independent な天井）。

### そこから採用された現役規律

- **encoder 符号反転 guard**（§4）= e5large の符号反転を緩和せず REJECT した判断が、
  以後すべての encoder agreement gate の標準になった。
- **all_pass 不使用 / n_neg ≥ 1 hard gate**（PR-24 GO criteria）= 「全部 pass」を
  GO 条件にすると弱い positive を拾うため、negative の存在を hard gate にする。
- terminate は「completion + 方法論 finding + ADOPT negative」として honest に記録し、
  disposition と forward research を会計分離（[00 §5](00-methodology.md)）。

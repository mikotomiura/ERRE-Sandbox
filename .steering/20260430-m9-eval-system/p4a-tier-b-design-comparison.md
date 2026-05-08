# P4a Tier B — design comparison (v1 vs v2 → hybrid v3 候補)

> v1 (`p4a-tier-b-design-v1.md`): infrastructure-first / minimum-cost
> v2 (`p4a-tier-b-design-v2.md`): psychometric-rigor-first / statistical-power
>
> 本書は両案を 5 question 軸で比較し、hybrid v3 を提示する。Codex review が
> 起爆。最終解は `p4a-tier-b-design-final.md` に記述。

## Question-by-question 比較

### Q1. Vendi Score kernel

| 軸 | v1 | v2 | hybrid v3 候補 |
|---|---|---|---|
| kernel | semantic MPNet (single) | semantic MPNet 0.7 + lexical 5-gram 0.3 | **hybrid kernel 採用 (v2)** |
| window size | 100 turn | 200 turn | **100 turn 維持 (v1、design-final 整合)** |
| sanity | direct one-hot ≈ N | lexical 成分で one-hot=N 担保 | hybrid のまま one-hot=N (lexical 成分で) |
| trade-off | 単純・低コスト、paraphrase 過敏 | spectrum stable、surface noise 緩和、window 数半減 | spectrum stable + window 数維持 |

**v3 selection**: kernel は v2 (hybrid)、window は v1 (100)。理由: window 200 化は
design-final.md (per-100-turn) を破壊する coast 高、hybrid kernel は per-window
内 spectrum stability を改善するので window 100 のままでも paraphrase 過敏問題
を緩和できる。

### Q2. IPIP-NEO 版

| 軸 | v1 | v2 | hybrid v3 候補 |
|---|---|---|---|
| 版 | Mini-IPIP-20 (Donnellan 2006) | IPIP-50 (Goldberg 1992) | **IPIP-50 採用 (v2)** (条件: 日本語 license clear) |
| call budget | 7,500 | 18,750 | 18,750 (G-GEAR overnight 並行で吸収) |
| α reliability | 0.6-0.7 marginal | 0.8+ stable | 0.8+ |
| 日本語訳 | 翻案要 (Mini-IPIP は日本語版確立薄) | Murakami 2002/2003 流用 | Murakami 2002/2003 (license 要確認) |

**v3 selection**: IPIP-50。理由: psychometric reliability (α 0.8+) は ME-1
fallback 判定 (ICC<0.6) の信頼性に直結。call budget +150% は **eval-only**
用途で問題にならない (live inference の話ではない)。

**defer 条件**: 日本語訳 license が clear できない場合は Mini-IPIP-20 fallback +
ADR で defer 理由明示。Codex prior art search で Murakami 2002/2003 公開状況
確認。

### Q3. Big5 ICC formula

| 軸 | v1 | v2 | hybrid v3 候補 |
|---|---|---|---|
| primary | ICC(2,k) consistency average | ICC(A,1) absolute agreement single | **ICC(2,k) consistency primary + ICC(A,1) absolute agreement diagnostic** |
| diagnostic | ICC(3,1) | ICC(2,k) consistency | ICC(A,1) + ICC(3,1) (両 surfaced) |
| ME-1 threshold | 0.6 / 0.5 そのまま | 切替で再評価必要 | 0.6 / 0.5 は ICC(2,k) primary に維持、ICC(A,1) は diagnostic threshold 別途 |

**v3 selection**: 両 surfaced。primary は v1 (ICC(2,k) consistency、ME-1 threshold
互換性)、diagnostic に v2 (ICC(A,1) absolute agreement) を追加。理由: drift
detection の意味論的に absolute agreement が筋という v2 の指摘は valid だが、
ME-1 threshold 0.6 は consistency ICC を念頭に Koo-Li 2016 から得たもので、
absolute agreement に流用すると threshold 妥当性が揺らぐ。両 surfaced で
construct validity と threshold 互換性の両立を狙う。

**ADR 候補**: ME-10 として「Big5 ICC は consistency primary + agreement diagnostic
両報告」を起票。Codex に「ICC(A,1) を primary にすべき」と明確に指摘されたら
v2 採用に切替。

### Q4. windowing × bootstrap

| 軸 | v1 | v2 | hybrid v3 候補 |
|---|---|---|---|
| window size | 100 turn | 200 turn | **100 turn (v1、design-final 整合)** |
| cluster 数 | 25 / persona | 12.5 / persona | 25 / persona |
| bootstrap | `cluster_only=True` | `cluster_only=False, auto_block=True` | **cluster_only primary + auto_block diagnostic 併載** |

**v3 selection**: cluster_only primary を維持 (PR #146 effective sample size 25
framing は Codex HIGH-2 で承諾済)。auto_block diagnostic を JSON 出力併載で
variance estimation の robustness を補強する。

**ADR 候補**: ME-11 として「Tier B bootstrap は cluster_only primary、auto_block
は diagnostic 併載」を起票。

### Q5. LIWC alternative honest framing

| v1 | v2 | hybrid v3 |
|---|---|---|
| DB10 Option D 通り全廃 | DB10 Option D 通り全廃 | **DB10 Option D 通り全廃 (一致)** |

差なし。Tier B 全 module 冒頭 docstring に honest framing 明示。

## v3 hybrid summary (one-paragraph)

**Tier B v3 = window 100 + hybrid Vendi kernel (semantic 0.7 + lexical 5-gram 0.3)
+ IPIP-50 (Goldberg 1992、Murakami 日本語版) + Big5 ICC は consistency ICC(2,k)
primary + absolute agreement ICC(A,1) diagnostic 両報告 + bootstrap cluster_only
primary + auto_block diagnostic 併載 + LIWC 全廃 (DB10 Option D)**。工数推定
~9-10h (v1 8h と v2 12h の中間)。

## 採否判定 matrix

| Question | v1 採否 | v2 採否 | v3 採否 |
|---|---|---|---|
| Q1 Vendi kernel | ✗ semantic single | ✓ hybrid (v3 と同) | ✓ |
| Q1 window | ✓ 100 (v3 と同) | ✗ 200 (design-final 破壊) | ✓ |
| Q2 IPIP-NEO | ✗ Mini-20 reliability marginal | ✓ IPIP-50 (v3 と同、要 license 確認) | ✓ |
| Q3 ICC primary | ✓ ICC(2,k) consistency (v3 と同) | ✗ ICC(A,1) は threshold 揺らぎ | ✓ |
| Q3 ICC diagnostic | ✗ ICC(3,1) のみ | ✓ ICC(A,1) も含める (v3 と同) | ✓ |
| Q4 bootstrap | ✓ cluster_only primary (v3 と同) | ✗ block primary は HIGH-2 承諾 framing 矛盾 | ✓ |
| Q4 auto_block | ✗ 採用せず | ✓ 採用 (v3 と同 diagnostic) | ✓ |
| Q5 LIWC | ✓ 全廃 | ✓ 全廃 | ✓ |

v3 が全項目で「最良の選択」を吸収。

## Codex review で v3 を challenge する点

下記を `codex-review-prompt-p4a.md` に明記:

1. **Vendi hybrid kernel の重み 0.7/0.3 の妥当性**: prior art (Friedman & Dieng 2023
   Section 4) で hybrid kernel の weight rationale はあるか
2. **window 100 turn が Vendi spectrum stability に sufficient か**: HIGH-3 が
   200-turn 最小と指摘した、100 で hybrid kernel なら mitigated と主張するが
   prior art empirical 確認
3. **IPIP-50 vs Mini-IPIP-20 の reliability gap が ICC fallback 判定に与える影響**:
   Mini-20 で α 0.6-0.7 → ICC ceiling も同程度 → ME-1 threshold 0.6 触れる
   リスク。IPIP-50 で α 0.8+ なら threshold 余裕度 up
4. **日本語 IPIP-50 (Murakami 2002/2003) の利用条件**: 商用 / 研究目的 / open
   など。defer 必要なら ADR で明示
5. **ICC(2,k) consistency と ICC(A,1) absolute agreement の併報告が drift
   detection 文脈で適切か**: どちらを ME-1 trigger に使うべきか
6. **per-window n=100 turn が ICC 計算に sufficient か**: rule-of-thumb (k items
   per dimension、n raters) と power analysis literature
7. **cluster_only と auto_block の両報告が JSON consumer 側で混乱を招かないか**:
   primary/diagnostic 区別の framing
8. **v3 は v1+v2 の hybrid だが、本質的な構造的バイアスを残していないか**:
   独立 reviewer (Codex) ならではの sanity check

## v3 で残す未解決 (Codex 反映後 design-final.md に確定)

- IPIP-50 日本語 license 確認結果次第で版 fallback 切替
- ICC primary/diagnostic 切替の最終判定 (Codex 推奨次第)
- Vendi hybrid kernel weight (0.7/0.3 vs prior-art alternative)
- per-window n=100 sufficiency の empirical/literature 確認

## v3 effort estimate

| Sub-step | 推定 |
|---|---|
| design-v1.md (済) | 30min |
| design-v2.md + comparison (本書、済) | 1h |
| Codex review prompt + execution + 反映 | 1.5h |
| design-final.md + decisions.md ADR | 30min |
| Implementation (3 file + tests + eval_store) | 4h (v1 3.5h + IPIP-50 +0.5h) |
| PR | 30min |
| **合計** | **~8.5-9h** (v1 8h、v2 12h の中間) |

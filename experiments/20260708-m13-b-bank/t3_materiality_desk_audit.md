# T3 materiality desk-audit — 反復 frozen-context bank

Issue 006 (I6) の成果物。FROZEN ADR `.steering/20260707-m13-b-impl-design/design-final.md`
§I7（T3 materiality desk-audit）の binding pre-register を doc 化したもの。**machine test 化
できない human judgement gate**（`test_bank_t3_desk_audit_present`、
`tests/test_integration/test_ecl_bank_continuity.py`）が検証するのは本 doc の **存在** と
**section 構成**のみ — criterion 4 の実際の判定（stimulus か substrate enrichment か）は
本 doc の sign-off 欄に人間が記入する。construction≠measurement: 本 doc は H(zone|ctx) /
floor / divergence を一切計算しない。

## 背景（REFUSED candidate との対比）

REFUSED candidate（親 ADR `.steering/20260707-m13-c-design/design-final.md` §C-design、
verdict=REFUSE_MEASUREMENT_LINE）= 単一 agent / frozen-context MC / N=32、**organic anchored
単一 context・1-sample**。反復 bank + lever は REFUSED candidate と同じ「frozen-context MC」を
含むため、これを「sampling 密度（M-sample）だけで materially different」と読む余地を残すと
letter 上危険（Codex HIGH-4、§B5.3）。本 desk-audit は「(a) M-sample（estimability 回復）」
だけでなく「(b) 基質改変（live 器官が enriched substrate から生成した凍結 context）」の両輪が
揃っていることを確認する場である。

## invariant 写像（(i)-(v)）

- **(i) estimand family** = zone 選択の温度感応（下流離散決定 bias）。**SPDM-landscape
  divergence でない**。反復 bank は `evidence/spdm` の二 arm retrieval-landscape divergence
  （arity=2）を一切計算せず、lever readout は単一 context の zone marginal entropy
  （arity=1）を志向する構造（B 自体は計算しない、§I2/§I4）。
- **(ii) data-generating channel** = enriched-substrate provenance の同一 live channel
  （bake-out は provenance pass が λ→sampling→LLM→zone を通す、`bank_fixtures.run_provenance_pass`
  → 未改変 `loop.run_ecl_loop`）。**es2_replay kernel でない**（壁1&4 の kernel とは別系統）。
- **(iii) 回避壁** = 壁2（純 categorical、embedding scorer 非使用）/ 壁3・壁5（landscape
  divergence/top-k/R0 anchor 非使用）を構造的に回避する。**壁1&4 は回避を試みるが §I1.5 で
  構造的に回避しきれない可能性を honest に明記する**（think=False の empirical collapse risk
  は B 単独では doc-only 保証不能、`project_m13_b_nbody_scoping.md` 参照）。
- **(iv) banned variants** = rung/quantize/relabel は同一 family でない。反復 bank の
  M-sample/K-context 密度を rung 的に刻む・quantize する・serial relabeling で再入資格を
  水増しする変種は本 candidate class に含まれない。
- **(v) tie→same-family** = B は divergence を一切非計算（raw row のみ、`BankAnnotationRow`
  の 5-field 閉集合、§I4）とすることで tie を封鎖する。B 自身が H/count/diversity を計算・
  主張しない限り、「sampling 密度だけで tie を超えた」という誤読の入口が構造的に塞がれている。

## criterion 1-3 の証跡

1. **canonical substrate inputs のみ編集**: lever は observation/persona/AgentState/
   memory-content を `model_validate` fixture 経由で編集し、**manual prompt string を
   手書きしない**（prompt は canonical builder `cognition.prompting.build_system_prompt`/
   `build_user_prompt` が organ 内部で render）。証跡 = `bank_fixtures.build_competing_cue_substrate`
   実装（`model_validate` 呼び出しのみ、手書き prompt 文字列なし）+
   `tests/test_integration/test_ecl_bank_fixtures.py::test_bank_cue_canonical_inputs_only`
   （I1-G2、AST scan で manual prompt substring / 直接 schema コンストラクタ呼出を禁止）+
   `test_ecl_bank_continuity.py::test_bank_provenance_retrieve_count_one`（I6-G3、canonical
   builder 経由の retrieve channel が非ゼロで実際に駆動していることの独立確認）。
2. **bank-only / M-density を materiality 根拠に使わない**（§B5.3 letter）: 本 desk-audit は
   materiality の根拠を invariant (ii) 基質改変に置き、M-sample の量そのものを根拠にしない。
   `BANK_M_GOLDEN`/`BANK_K_GOLDEN`（`bank.py`）は tiny pinned construction 定数であって
   powered 密度の主張ではない（§I5/§I6、C-proper 未 AUTHORIZE）。
3. **source-organic + bounded pre-result mutation**: `BANK_Z_COMP` / `BANK_NEUTRAL_ZONE` /
   `BANK_LAMBDA_CTX`（`bank_fixtures.py`）は forking-paths seal — fixture を collapse 観測後に
   切り直していない（結果非依存の pre-registration、`test_bank_cue_constants_literal_pin`
   I1-G1 が literal pin を保証）。cue の対称性は「可能な限り organic な context 起点に、
   result 非依存の bounded な cue 対称化を施す」設計であり、無制限な合成基質ではない
   （§I1.1 対称 affordance/zone_transition + 内容鏡映 memory、salience/distance/count は
   共有、zone 由来フィールドのみ差異）。

## criterion 4 — honest teeth（stimulus 判定 → T3 fail → line-close → arc-close）

**これが本 desk-audit の中核であり、tune-to-narrative の反対の honest close 出口である**:

> **stimulus 判定なら T3 fail**: user/reviewer が凍結 context を「substrate enrichment で
> なく measurement stimulus」と判定したら **T3 fail → 該 candidate 再入資格なし →
> line-close**（→ 両 family exhaust → arc-close 自動執行）。これは B が T3 を clear できない
> honest な close 出口であり、tune-to-narrative の反対である。

この判定は機械 test で代替できない（`test_bank_t3_desk_audit_present` は本 doc の *存在* と
*section 構成*のみを検証し、criterion 4 の実際の判定内容は検証しない）。判定は下記 sign-off 欄に
人間が記入する。

**honest tension（不可侵）**: 凍結 context は designer 構築の対称性ゆえ「substrate enrichment か
measurement stimulus か」の境界に立つ。provenance pass + criterion 1-3 で stimulus 化を緩和
するが、criterion 4 が「緩和しきれない場合の honest close」を保証する。claim を「基質が複数
zone を licensed に している」に厳密限定し、それ以上（「lever が (i) を保証する」等）を主張しない
（§I10 over-read guard）。

**stimulus 判定が下った場合の執行経路**（記録目的、判定自体はここでは行わない）:
1. T3 fail を本 doc の sign-off 欄に記録する。
2. 該当 candidate（反復 frozen-context bank + zone-pick-visible cue lever）は再入資格を失う
   （line-close）。
3. R-budget の 2 named family（SPDM-landscape SPENT + live-channel-conformance）のうち
   live-channel-conformance family も line-close となり、両 family exhaust に達する。
4. 両 family exhaust は arc-close を自動執行する（`.steering/20260707-m13-forward-primary-post-v1/design-final.md`
   の invariant 定義、serial-relabeling 封鎖）。

## claim 境界（over-read guard、§I10 の再掲）

主張してよいこと: 反復 frozen-context bank の HOW 技術契約を pre-register/実装したこと
（lever = zone-pick-visible cue enrichment、provenance pass、bake-out、continuity-gate 4 test、
spend ast-guard、determinism record-M、T3 materiality desk-audit）。

主張してはいけないこと:
- 「lever が (i) を保証する / H(zone|ctx) を上げる」（empirical gate、B は保証しない）
- 「B が measurement を実行した / floor を測った / divergence を示した」（construction、
  budget 未消費）
- 「provenance pass で live channel が zone を偏らせると示した」（未測定、第2リンク
  detectability は未立証）
- 「bank の H(zone|ctx) が organic live scene に一般化する」（designer 対称 cue は artificial
  licensed-zone stimulus であって organic entropy でない）

## user/reviewer sign-off

| 項目 | 記入 |
|---|---|
| 判定日 | （未記入） |
| 判定者 | （未記入） |
| criterion 1（canonical inputs only）| ☐ PASS ☐ FAIL |
| criterion 2（M-density 非根拠）| ☐ PASS ☐ FAIL |
| criterion 3（source-organic + bounded mutation）| ☐ PASS ☐ FAIL |
| criterion 4（stimulus 判定）| ☐ substrate enrichment（T3 PASS）☐ measurement stimulus（T3 FAIL → line-close）|
| 総合 verdict | （未記入、統合時 `/cross-review` で埋める） |
| コメント | （未記入） |

（未記入で可 — 統合時の `/cross-review` で埋める。CLAUDE.md「Codex との連携」節・
`.claude/skills/cross-review` 参照。）

# あらすじ (arasuji) — ERRE-Sandbox 研究の物語と現在地

> **この文書は何か**: 研究の「筋（あらすじ）」を正直に語り、各主張を **先行研究 `[n]`（`docs/references.md`）**
> と **リポジトリ内のファイル位置**に紐付けた **navigation map**。thesis の正典 SSOT は `docs/research-positioning.md`
> であり、本書はその物語版＋出典地図（付加価値をつけるための入口）。
> **重要な区別**（本書の背骨）: 「チャネルをつないだ（＝建設）」と「発散を実証した（＝計測）」は別物。
> **現状（2026-07-11 更新）**: 建設は到達（ECL v0/v1）。計測は §5.9 で **実際に再入して撃ち切り、arc
> measurement-line が CLOSE**（C-proper = valid FAIL、第2リンクは registered floor で detectable でない）。
> **閉じたのは計測ラインであって substrate 建設の大方針ではない**。以降の measurement 再入は上位 superseding ADR を要する。
> ※ `.steering/…` は gitignore のローカル ADR（tracked ではない）。`docs/ loop/ experiments/ src/` は tracked。

---

## 1. 一枚あらすじ（正直版）

ERRE-Sandbox は「歴史的偉人の認知習慣を local LLM エージェントとして 3D 空間に再実装し、**意図的非効率性**と
**身体的回帰**による知的創発を観察する」研究基盤。中核命題は「閉ループの創発 ＝ de-novo な path-dependent
**思考発散**」。

物語はこう進んだ:

1. **中核命題（記憶/認知ループ単独での発散）は CLOSE**（bounded-non-divergence、terminal）。記憶・意味の
   ループを回すだけでは de-novo な発散は立たなかった（Gate A FAIL 系）。
2. → **M13 arc へ pivot**: 「身体を持つ substrate（連続物理＋履歴依存記憶＋歩行）」を**建てて**、そこから
   発散の種を探す。着想の下敷きが **歩行 → DMN → 拡散的創造性・アハ体験**の先行研究 [1][6][11]。
3. **ES 系列で「発散の種のチャネル」を一つずつ検定** → **5 つの壁**（下記 §4）に当たる。要点:
   - **記憶再編ルート単独**での発散は **INCONCLUSIVE**（判定不能。壁1・壁4）。
   - **歩行→sampling** の**チャネルは存在（GO）**。ただし「歩行→発散」の検定ではない（壁ではないが未検定。ES-3）。
   - 発散の **structural floor は立たず**（NO_STRUCTURAL_FLOOR。壁3・壁5、R0 anchor collapse）。
4. → **「計測でなく建設」へさらに舵**: 分断していた **(A) ライブ LLM 認知** と **(B) frozen running-substrate**
   を一本の器官に統合する **Embodied Cognition Loop (ECL) v0** を建設。
5. **いま（2026-07）到達点**: ECL v0 organ が **初めて real qwen3:8b と接触して動き、決定論的に再現**した
   （first-contact **GO**、PR #54/#55/#56/#57）。**これは「土台が本物で再現する」の実証 = construction
   validation であって、「発散が起きた」の計測ではない**。発散の計測は **holding（保留）**のまま。

**一言で**: 「**発散を測れるだけの、本物で再現可能な身体的認知の器官**」を初めて動かした段階。発散そのものは
まだ問うていない（過去 5 回の計測は INCONCLUSIVE / 非発散だったので、土台を固めてから慎重に再入する規律）。

---

## 2. あなたの物語の「答え合わせ」（段 → 実際の verdict → 先行研究 → ファイル）

> あなたのまとめ:「SWM のみでは思考発散は難しい → 移動経路による発散が使えるのでは → Oppezzo の歩行→DMN
> →発散の先行研究がある → 身体的回帰だけでなく脳内の記憶再編で LLM でもできるのでは → 場所移動で記憶の動線を
> つなぎ、移動経路・評価機でもつないだ」

| あなたの段 | 実際の状態（正直） | 先行研究 | ファイル位置 |
|---|---|---|---|
| **① SWM（記憶/意味チャネル）単独では発散が難しい** | **INCONCLUSIVE**（難しい≒判定不能）。記憶再編単独チャネルは ill-posed（遷移分布 near-uniform ~1627/2256、argmax stability 0.187<0.5） | Memory Stream [2]、CoALA [3]、semantic-memory foraging [9] | `src/erre_sandbox/evidence/memory_recomp_conformance/`、`src/erre_sandbox/evidence/es2_replay/`、ADR: `.steering/20260702-m13-sub1-memseam-adr/`（local） |
| **② 移動経路による発散を使えるのでは** | **方向は採用済**。ただし現状「移動→発散」は**未検定**。ES-3 で**歩行→sampling のチャネル配線は GO**（D_loco=0.0468≥floor、非トートロジー）だが、これは**チャネルの存在**であって発散の検定ではない | 歩行→創造性 [1][6]、探索の一般化 [10] | `src/erre_sandbox/evidence/es3_locomotion/`、ADR: `.steering/20260629-m13-es3-adr/`・`…es3-impl/`（local）、`experiments/`（ES-3 run） |
| **③ Oppezzo の歩行→DMN 安定化→発散・アハ体験の先行研究** | **理論的動機（warrant）**であり系内実証ではない。プロジェクトは「身体性そのものの claim / 人間機構の再現主張はしない（warrant 止まり）」 | **Oppezzo & Schwartz 2014 [1]**、walking メタ分析 [6]、**DMN 因果 [11]** | `docs/references.md`（[1][6][11]）、`docs/literature/20260702-divergent-thinking-benchmarks.md`、`docs/research-positioning.md §1/§3/§7` |
| **④ 身体的回帰だけでなく脳内記憶再編で LLM でも** | **試した = memseam。結果 INCONCLUSIVE**（壁4）。「脳内記憶再編で発散」は立たなかった（判定保留） | Memory Stream [2]、foraging [9] | `src/erre_sandbox/evidence/memory_recomp_conformance/`、ADR local `…memseam-adr/` |
| **⑤ 場所移動で記憶の動線をつなぎ、移動経路・評価機でもつないだ** | **(a) 記憶動線（履歴依存 memory-centroid 幾何）と (b) 移動（連続物理）は「つないだ」＝ ECL v0 で建設完了。だが (c) 評価機（＝発散の計測機）は意図的に「つないでいない」＝ holding**。measurement 再入は costed gate + escalation ratchet（R-budget=arc 全体で 1 回）越しのみ・未消費 | Generative Agents [2]、Project Sid [4]（多体） | 器官: `src/erre_sandbox/integration/embodied/{loop.py,live.py,handoff.py}` ＋ `src/erre_sandbox/cognition/embodiment.py`。計測機（frozen・不可侵）: `src/erre_sandbox/evidence/**` |

**⑤ の核心的訂正**: 「評価機でもつないだ」だけは事実と異なる。**評価機（計測）はあえて切断したまま**が現在の規律。
つないだのは「動線」と「移動」（建設）。理由は §4（過去 5 回の計測失敗の反省）。

---

## 3. 中核概念と先行研究の地図（付加価値の入口）

| 概念 | 内容 | 先行研究 `[n]` | 系内の対応物 |
|---|---|---|---|
| **歩行 → 拡散的創造性** | 歩行が divergent thinking を高める（身体的回帰の中核） | **[1]** Oppezzo & Schwartz 2014、**[6]** Thabane メタ分析 2026 | ES-3（`evidence/es3_locomotion/`）、ERRE mode `peripatetic`（`personas/*.yaml`） |
| **DMN と創造の因果** | default mode network の電気生理と創造思考への因果的役割 | **[11]** Bartoli 2024 | ERRE mode（DMN/vagal tone の設計根拠、`.claude/skills/persona-erre/`） |
| **意味記憶の最適採餌** | 記憶探索を foraging として定式化（履歴依存 centroid の理論的根拠） | **[9]** Hills 2012 | `cognition/embodiment.py`（strength-weighted centroid）、`evidence/memory_recomp_conformance/` |
| **発散の計測手法** | 意味的距離で創造性を測る（将来 C で使う候補、要慎重） | **[7]** SemDis (Beaty)、**[8]** DAT (Olson)、**[10]** Wu 探索 | 計測ライン（holding）。`docs/literature/20260702-divergent-thinking-benchmarks.md` |
| **生成エージェント / 記憶ストリーム** | LLM エージェントの記憶・行動アーキ | **[2]** Generative Agents、**[3]** CoALA | `cognition/`（cycle/belief/narrative/reflection）、`memory/` |
| **多体シミュレーション** | 多エージェントの創発（候補 B の下敷き） | **[4]** Project Sid (PIANO) | 候補 B（N体化、未着手） |
| **文体差の計量** | Burrows Δ（過去の Plan B で使用、CLOSE 済） | **[5]** Burrows 2002 | `evidence/`（kant chain、CLOSED） |

---

## 4. これまでの「5 つの壁」— 何を学んだか（negative の資産）

| 壁 | 何を検定したか | verdict | ファイル / ADR(local) |
|---|---|---|---|
| **壁1** | ES-2 path-recombination（記憶の経路再結合で発散） | **INCONCLUSIVE**（遷移 near-uniform、真の low-power） | `evidence/es2_replay/`、`.steering/20260628-m13-es2-replay/` |
| **壁2** | ES-4 temperature actuator の on-task rarity 十分性 | **NO_VALID_SCORER**（embedding rarity が自己 anchor 循環で崩落） | `evidence/es4_actuator/`、`.steering/20260630-m13-es4-*`、`experiments/20260630-es4-phase0/` |
| **壁3** | D0 pack structural floor（静的 fixtures 上） | **NO_STRUCTURAL_FLOOR**（R*=R0、R1 gate が honest に floor 未達） | `evidence/d0_substrate/`、`.steering/20260701-m13-sub1-d0-pack/` |
| **壁4** | memory-recomposition seam（記憶再編チャネル単独） | **INCONCLUSIVE**（channel ill-posed、壁1 と同一 es2_replay kernel 由来） | `evidence/memory_recomp_conformance/`、`.steering/20260702-m13-sub1-memseam-adr/` |
| **壁5** | running substrate 上の D0a 再走（動的 trace） | **NO_STRUCTURAL_FLOOR_RUNNING**（R0 anchor collapse。terminal-anchored policy が zone 占有を収束させ D0→0） | `evidence/d0_substrate/running/`、`.steering/20260703-m13-running-substrate/` |

**学び**: (i) 記憶チャネル単独の発散計測は繰り返し **near-uniform / ill-posed** で low-power（壁1・4 は同根）。
(ii) 失敗は「基質の欠損」ではなく **readout × policy の estimand mismatch**（壁5 の R0 anchor collapse）。
(iii) だから **計測に踏み込む前に「本物で動く基質」を確立すべき**、という規律（holding + R-budget）に至った。
**arc-close は却下**（over-read guard の演繹）、within-zone measurability は verdict 非昇格の preserved asset。
（正典: `docs/research-positioning.md §8`、ADR local `.steering/20260703-m13-arc-disposition/`・`…arc-close-reconsideration/`）

---

## 4.5 なぜ「発散が出なかった」のか — 機序の正直な整理（誤読を防ぐ）

> よくある誤読を 3 つ、arc の実際の診断で正す。verdict は **INCONCLUSIVE（検出力問題＝判定保留）**であって、
> 「発散しない」も「記憶が貧弱」も**証明されていない**ことが大前提。

**誤読①「計算機/計算資源が足りなかった」→ 違う。** 実験は問題なく回った。未達の正体は統計的・機序的：
遷移分布が **near-uniform（ES-2 ~1635/2256、memseam ~1627/2256）**＋ **argmax stability 0.187<0.5** ＝
「測る対象が均一に潰れ、検出すべき信号が無かった」。＝資源不足でなく**信号/検出力**の問題。

**誤読②「記憶再編の思考が"低次元すぎる"から分散できなかった」→ arc の診断と食い違う。**
- 計測されたのは **near-uniform（高エントロピー/低 path-dependence）遷移**であって「低次元」ではない。
- 決定的なのは**壁5（arc-close 再検討）の診断**: 失敗は **(ii) substrate（記憶）欠損ではなく、(i) readout ×
  policy の estimand mismatch**。terminal-anchored な policy が **zone-level 占有を収束させ D_0→0** に潰しただけ。
- しかも **within-zone には measurable な構造が実在した（R1=0.769、強 PASS ＝ preserved asset）**。
- → 正確には「**記憶が低次元だから**」ではなく「**収束的 policy 下で readout が、実在した構造を均一へ潰し、
  検出できなかった**」。

**誤読③「発散には外部変調器が必要、と証明された」→ それは"仮説/理論枠付け"であって結論ではない。**
- 機序仮説: 記憶ループは平衡へ均一化しやすい（採餌 [9] は exploit 側）。そこへ **off-equilibrium な駆動**
  （別系統で GO 済の移動→sampling 信号）を注入し、**系を平衡から押し出し続けて検出可能な発散信号を作る**。
  理論的動機は Oppezzo [1]（歩行→拡散思考）/ Bartoli [11]（DMN 因果）。
- **外部変調器は「低次元を補う」ためではなく「均一化を破って"読める"信号を作る」ため**。壁5 の教訓（失敗は
  測り方＝readout×policy）に直接対応し、③の計測（C）は「読み方（estimand）を変える」こととセットで開く。

**正しい一行**: *記憶（脳）だけの系は収束的 policy 下で均一へ潰れ検出できなかった（判定保留、構造自体は zone 内で
実在）。そこへ移動→認知温度の身体ループを繋ぎ、平衡から押し出す駆動を入れて"読める発散"を作れるか、を①→②→③で
確かめにいく。*（①活性化＝ECL v1 / ②estimand 再設計 / ③計測 C）

---

## 5. 今回の到達点 — ECL v0 first-contact GO（2026-07）

**分断していた (A) ライブ LLM 認知 × (B) frozen running-substrate を一本の器官に統合し、初めて real LLM で動かした。**

- **建設したもの**: LLM の移動決定 → 履歴依存 memory-centroid 幾何（`cognition/embodiment.py`）→ 連続物理移動
  （`world/`）→ record/replay で決定論化（`integration/embodied/loop.py`）→ cross-machine handoff（`handoff.py`）。
- **今回の sealed live run（PR #57）**: real qwen3:8b で N=32 封印実走 →
  - **O1 完走** / **O2 replay 再現**（checksum byte 一致・LLM 非呼出）/ **O3a-b cross-platform**（WSL Linux＝Windows byte 一致）→ **Done HOLDS**。
  - **O5=32/32**（全 tick で本物の plan が履歴依存 move を駆動）/ **O4 非縮退**（zone 2・target 32）。
  - **決定的発見**: `think=False`（`ThinkOffChatClient`）が無いと qwen3 は `<think>` に budget を食い空応答→parse 全滅。事前検出が効いた。
- **ただし construction validation であって measurement verdict でない**（floor/landscape/verdict 非出力、
  AST guard で holding を機械保証）。
- ファイル: `src/erre_sandbox/integration/embodied/`、`scripts/ecl_v0_live_capture.py`、
  committed 実験: `experiments/20260706-ecl-v0-live-capture/`（run.sh/env.md/artifacts）、
  runtime: `loop/20260706-ecl-v0-live-run/`、memory: `project_m13_ecl_v0_live_run`。

---

## 5.9 measurement 再入と C-proper — 第2リンクを powered で測り、arc measurement-line が CLOSE（2026-07-11）

> §5 の後、§7 の 3 手ロードマップ（ECL v1 活性化 → 計測設計 ADR → 計測 C）を**実際に実行しきった**。
> 結論から: **計測ラインは honest に閉じた**（arc measurement-line CLOSE）。以下、顛末と**具体的な原因・反省**。

**手1 = ECL v1（活性化、construction）**: ES-3 の歩行→sampling チャネルをライブ器官に活性化（seeded
`LocomotionState`、organ src 改変ゼロ）。sealed run で **V4a=29/V4b=28**（歩行が実際に per-tick sampling を変調）＝
**第1リンク（λ→sampling）は live 器官で発火**を construction-validity で確認（PR #58/#59、holding 保全・計測でない）。

**手2 = 計測設計（C-design、2 回）**:
- **C-design #1 = REFUSE**（PR #61）: 単一 agent・1-sample では P(zone|ctx,T) が**推定不能**（estimability の死点）→
  measurement line を doc-only では立証不能 → REFUSE、budget 温存。
- **B（反復 frozen-context bank）を建設**（PR #64）: 同一凍結 context を M 回サンプルして P(zone|ctx,T) を**推定可能**に
  する基質（competing-cue substrate + M-sample）。#1 の死点を構造的に解消。
- **C-design #2 = AUTHORIZE_C_PROPER**（PR #65、user 裁定）: bank candidate が hard futility gate の validity+power を
  PASS（power worksheet で **near-uniform=power 1.0**、「near-uniform=低検出力」を反証）。ただし effect-absence 分岐は
  pre-spend では評価不能 → **その risk を C-proper の spend が全面負担**（Codex Verdict=Revise で honest 化）。

**手3 = C-proper（powered sealed run、実 spend R-budget=1、user ratify 2026-07-10）**（PR #66、main=356ab71）:
real qwen3:8b で **M=300·K=8（4800 draws）・think=False**、凍結 scorer（Codex HIGH 3+MEDIUM 3 を実走前反映）を
integrity 全 PASS 後に one-shot 適用。**verdict = `NO_CHANNEL_CONFORMANCE`（valid FAIL、effect-absent）**。

### 具体的な結果（3 層）

| 層 | 実測 | 意味 |
|---|---|---|
| 基質は健全 | rho=**1.0**（8/8 context で H(zone|ctx)=0.63–0.75 bit） | どの context でも複数 zone が選ばれ得る（collapse でない、壁1&4「near-uniform=低検出力」を**empirical 反証**） |
| 計測器は万全 | power=**1.0**（effective K'=8） | δ≥0.10 の効果があれば確実に検出できた |
| 効果が floor 未達 | tv_bar=**0.038** < δ_min=0.10、permutation **p=0.058** | 歩行の有無で zone 選択分布がほとんど動かない＝**第2リンク（sampling→zone）は registered floor で detectable でない** |

### 具体的な原因の正直な整理（誤読を防ぐ）

**確定した事実**: **第1リンク（歩行→sampling）は発火するが、第2リンク（sampling→zone 選択 bias）が pre-register 済
floor では検出できない**。かつ H=0.65 bit ＝ zone に spread は在る（決定論でない）——効果が弱いのは「spread が無い」
からでなく「**その spread が λ で動かない**」から。

**候補原因（いずれも C-proper データと整合的だが、C-proper は分離していない＝仮説）**:
1. **think トレードオフ仮説**: `think=False` は plan を出させるために必須（think=True → qwen3 が `<think>` に budget を
   食い空応答 → plan なし、ECL v0 で load-bearing 確定）。だが推論の迂回路（reasoning）こそ、小さな sampling 差が
   積み上がって別結論＝発散に化ける「面」。信頼性のため迂回路を潰す（think=False）と、**λ摂動が効く面も一緒に消える**
   可能性。**中核テーゼ（意図的非効率性＝推論迂回路こそ身体性が作用する面）そのものと響き合う、美しく苦いトレードオフ**。
   → **ただし C-proper は think=True の対照を取っていない（pre-register 通り think=False のみ）。しかも think=True は
   plan を出せないので、この装置内では反証不能**——zone 選択を測れる regime（think=False）が、まさにチャンネルが最も
   弱い regime、という構造的二律背反。「保証された plan」と「高い sampling→zone 感度」を同じ装置で同時に測れない。
2. **λ→温度ゲインが物理的に小さい**: locomotion_gains は gain_t=0.3、frozen λ=0.4 → Δtemp = **+0.12**（base 0.7 →
   0.82、top_p +0.04）。5-way categorical を TV 0.10 動かすには軽すぎる可能性。

**言えないこと（over-read guard §CB6、不可侵）**: ✗「think=False が効果を殺したと証明された」/✗「効果は存在しない」/
✗「live channel は zone を偏らせない／substrate 否定／H4 否定／中核命題 否定」/✗「λゲインが原因と特定した」。
言えるのは「**valid+powered な計測が、第2リンク detectability を registered floor（δ=0.10）で absent と measure した。
効果が実在するとしても、この装置では原理的に見えない位置にある**」まで。

### disposition と反省

- **arc measurement-line CLOSE（自動執行）**: valid FAIL → live-channel-conformance family bounded-close（R-budget=1
  消費）→ SPDM-landscape [SPENT] と両 family exhaust → arc §4.3 ratchet。**同一 candidate 再起票禁止（§D1.2）・
  反射的再走禁止（arc §1.4 D1-D3）**。「floor を下げて再走」は tune-to-pass ゆえ不可。
- **反省（process は正典として機能した）**: /reimagine（scorer 統計設計 v1 pooled 破棄 → v2 層別置換）→ Codex
  Verdict=Revise の HIGH（integrity seal / powered-scale 強制 / permutation p の Phipson–Smyth 保守補正）を**実走前に**
  全反映 → seal → **user spend 再確認** → one-shot。tune-to-pass 封鎖と forking-paths seal が最後まで守られた。
  **希少 budget を「実信号があるか未確認のまま」でなく、estimability を回復した bank 基質＋万全な検出力の下で撃った**
  ——結果は negative だが、**測り方（estimand）と検出力を最善にした上での negative** ＝壁1&4 の「low-power で判定不能」
  とは質が違う、**decisive な effect-absent**。negative の資産としては最も強い部類。
- **最重要の区別**: 閉じたのは **measurement ライン**であって、**substrate 建設の大方針（ECL 器官・situated 3D
  embodiment）ではない**（§5.1–5.2 letter、scope 分離）。C（計測）としての筋は bounded に閉じたが、建設側は開いている。

ファイル: 器官消費 scorer `src/erre_sandbox/integration/embodied/bank_scorer.py`、live capture
`scripts/ecl_bank_cproper_capture.py`、sealed 実験 `experiments/20260710-m13-c-proper/`（env.md + artifacts、
bank_checksum `5e991dd6…`）、ADR local `.steering/20260710-m13-c-proper/`（design-final §S/§S9、codex-review.md、
decisions.md）、memory `project_m13_c_proper`。

### forward disposition — 原因診断 + 計測再入 desk-audit（2026-07-11、doc-only・非 spend）

C-proper の後、「原因を突き止めて次の計測へ」という自然な欲求に対し、**doc-only の診断 + 再入 desk-audit** で方向を
出した（実 spend ゼロ）。結論 = **(B) 計測ライン CLOSE を維持し、建設側大方針へ pivot。reasoning-trace door は
「保全のみ」**。

- **なぜ「診断 → すぐ再計測」にしなかったか（決定的 letter）**: measurement の再入予算は seal で有界化されている
  ——named family はちょうど 2（SPDM-landscape / live-channel-conformance）で**両方使い切った**。かつ **§D0.2(D0-e)
  非反射条項**が「直前の FAIL への反応として新しい計測 family を起票する」経路を名指しで禁じる。本タスクはまさに
  その「直前 FAIL への反応」文脈ゆえ、ここで新計測を立てるのは反射経路そのもの。「floor を下げて / λ を上げて / M を
  増やして再走」は tune-to-pass・same-family rung で即却下。
- **reasoning-trace 候補（推論トレースの発散を測る）の審査**: user 着眼の 2 点セット — (a) `<think>` の二相
  マネジメント（plan 局面は抑制して actionable JSON を取り、trace 局面は `<think>` を捕捉）は Ollama+qwen3 で
  **技術的に有望**だが**必要条件にすぎない**。(b) 自由テキスト trace の発散を**非循環に**測る scorer が**致命的に
  欠けている**——embedding の novelty で測れば**壁2（ES-4 の自己 anchor 循環＝測れない）が再来**するだけで、死点が
  「zone が動かない」から「trace 発散が循環 scorer で測れない」へ**移動するだけ**。∴ 本文脈で計測再入は通らない。
- **door を殺さず保全**: reasoning-trace は将来の**非反射**候補として door を残す。開くには (1) 本 FAIL 文脈から
  分離した独立 forward ADR、(2) 非循環 trace-scorer の**先行**解決、(3) `<think>` 二相捕捉、の 3 条件が**すべて**要る。
  今は「開く」でなく「保全」——実 spend は更に別タスク + spend 再確認を要する。
- **process**: /reimagine（機序起点の初回案を意図破棄 → seal-letter 起点で独立再生成、両案が同じ結論に収束）+
  Codex independent review（**Adopt-with-changes、事実誤認 HIGH なし**、over-read を狭める MEDIUM/LOW を全反映）。
- **誤読しないための一行**: 閉じたのは**計測ライン**であって、substrate 建設の大方針でも reasoning-trace の可能性でも
  ない。効果が「無い」と決めたのでもない（「この装置では見えない位置にある」まで）。次は測るのでなく**建てる**
  （M2 N体 society / M3 endurance / M4 可視化 が pivot 先候補）。

ファイル: ADR local `.steering/20260711-m13-post-cproper-disposition/`（design-final / design-v1/v2/comparison /
codex-review.md verbatim / decisions.md）、memory `project_m13_post_cproper_disposition`、`research-positioning §8`。

---

## 6. 付加価値をつけるために — 読むべき文献 / 見るべきファイル

**(a) まず読むと物語が締まる先行研究（既登録）**
- **[1] Oppezzo & Schwartz 2014** / **[6] Thabane メタ分析**: 「歩行→発散」の実証的核。あなたの ② ③ の背骨。
- **[11] Bartoli 2024（DMN 因果）**: 「なぜ歩行が効くか（DMN 安定化）」の機序。③ の「DMN 安定化」主張の裏付け。
- **[9] Hills 2012（意味記憶の最適採餌）**: 履歴依存 centroid（記憶動線）の理論的正当化。⑤(a) の下敷き。
- **[7] SemDis / [8] DAT**: 将来 **計測（C）**で発散をどう測るかの候補手法。今読んでおくと C の設計が早い。
- 既存の読書カード: `docs/literature/20260702-divergent-thinking-benchmarks.md`（[7][8][9][10][11] を整理済）。

**(b) 追加で読むと良い方向（未登録＝要 `docs/references.md` 追記、`citation-ssot` skill で登録）**
- 「歩行 × DMN × アイデア生成」を **エージェント/計算モデル**で実装した先行研究（あれば ④ の LLM 化を強化）。
- creativity の **process 指標**（発散の「経路依存性」を測る手法）— 過去の near-uniform 低検出力（壁1・4）を
  越える estimand 設計のヒント。

**(c) 見るべき系内ファイル（物語を深めるコード/ADR）**
- 器官の実体: `src/erre_sandbox/cognition/embodiment.py`（記憶動線＝centroid 幾何）、
  `src/erre_sandbox/integration/embodied/loop.py`（two-plane determinism）。
- 歩行チャネル: `src/erre_sandbox/evidence/es3_locomotion/`（GO 済チャネル、ライブ未活性）。
- 計測ライン（holding、frozen・不可侵）: `src/erre_sandbox/evidence/{d0_substrate,memory_recomp_conformance,spdm}/`。
- 正典/意思決定: `docs/research-positioning.md`（thesis）、`docs/glossary.md`（peripatos/chashitsu/守破離 等）、
  local ADR 群 `.steering/2026*m13*`。

**(d) いま「つないでいない」ので伸ばせる余白**
- **移動経路チャネルのライブ活性化**（ES-3 の locomotion をライブ器官に載せる。construction、holding 保全）。
- **評価機（計測）の接続**（C。ただし R-budget=1 の costed gate、過去 low-power を越える設計が前提）。
- **多体化**（B。集団/組織レベルの発散、Project Sid [4] 系）。

---

## 7. 推奨する次の方向（recommendation）

> ✅ **確定済 (2026-07-07)**: 下記推奨は Plan mode + `/reimagine`（α×β 8 軸独立収束）+ Codex（Adopt-with-changes、
> 事実誤認 HIGH なし）を経て **ECL v1 ADR = FROZEN**（doc-only、`docs/research-positioning.md §8`）。実装は
> Phase 1（Loop Engineering、別セッション）。**holding 保全**（construction であって計測でない、R-budget 未消費）。
>
> 🏁 **実行済 (2026-07-11)**: 下記 3 手ロードマップは**すべて実行しきった** → §5.9 参照。手1 ECL v1（活性化・GO）→
> 手2 計測設計（C-design #1 REFUSE → B bank 建設 → C-design #2 AUTHORIZE）→ 手3 **計測 C-proper（実 spend、
> valid FAIL）→ arc measurement-line CLOSE**。**この §7 は歴史記述**（当時の推奨）。以降の方向は §5.9 の disposition
> ＝ **measurement は superseding ADR なしには再入せず、建設側の大方針へ**。

**採用 (FROZEN) = 「ECL v1: 移動経路→sampling チャネル（ES-3）をライブ器官に載せる」（construction 拡張、単一 agent）。**

> HOW（ADR 確定）: 既存 `agent_state` 引数経由で seeded `LocomotionState(lam=0.0)` を渡すだけ（**organ src 改変
> ゼロ**）。器官が自らの zone 移動決定（EMA λ）で sampling を変調する閉ループ。determinism は replay が sampling
> 無視・checksum が幾何のみゆえ**新非決定源ゼロ**。事前登録 = Done=V1∧V2∧V3a∧V3b + V4/V5 annotation（統計禁止・
> side file）、**verdict なし**（floor/landscape/verdict/D_loco 非出力、evidence 非 import、holding 不可侵）。

**理由（あなたの物語に最も忠実 × 方法論的に健全）**:
1. **物語直撃**: あなたの中心＝「移動経路による発散（Oppezzo [1][11]）」。ES-3 は既に**チャネル GO** だが
   ライブ器官では未活性。これを載せると、器官が実際に「歩いて sampling を変調する」= ③④⑤ を機構として instantiate。
2. **holding を守れる**: これは **construction（建設）**であって計測ではない（`ES-3 活性化 ≠ 計測 door`）。
   floor/landscape/verdict を出さない限り holding 不可侵・R-budget 未消費のまま進める。
3. **将来の計測（C）の成功率を上げる**: 過去の計測失敗（壁1・4）は**記憶チャネル単独が near-uniform で低検出力**
   だったこと。**移動チャネルは別系統の GO 済信号**。これを器官で実際に動かしてから計測すれば、
   「測る対象に実信号がある」状態で C に入れる＝希少な R-budget を無駄撃ちしない。

**却下した代替**:
- **C（計測へ直行）**: R-budget=arc 1 回を、実信号を器官で確認する前に使うのは VoI 最劣（過去 INCONCLUSIVE の
  再演リスク）。**移動チャネルを載せた後**に、near-uniform を越える estimand 設計とセットで開くべき。
- **B（N体化へ直行）**: 集団発散は魅力的だが、あなたの「移動経路→発散」の物語からは一歩遠い。単一 agent で
  移動チャネルを立ててからでも遅くない。

**推奨ロードマップ（3 手）**:
1. **ECL v1（今回の推奨）**: ES-3 locomotion をライブ器官に活性化 → 「歩行が sampling を変調する」を
   construction-validity（boolean/counting annotation）で確認（計測ではない）。
2. **計測設計 ADR（C の前段）**: 過去の near-uniform low-power を越える estimand を Plan+reimagine+Codex で設計。
   満たせないなら開かない（R-budget 温存）。
3. **計測（C）**: R-budget を 1 回消費して「移動経路→発散」を falsifiable に検定。

---

## 8. ファイル地図（navigation）

| 何を見たいか | 場所 |
|---|---|
| thesis の正典 | `docs/research-positioning.md`（特に §8 進捗ログ、§9 スコープ） |
| 用語（peripatos/chashitsu/守破離/DMN 等） | `docs/glossary.md` |
| 参考文献（[n] SSOT） | `docs/references.md` / 読書カード `docs/literature/` |
| **器官（ECL v0）本体** | `src/erre_sandbox/integration/embodied/{loop.py,live.py,handoff.py}` ＋ `cognition/embodiment.py` |
| 歩行チャネル（ES-3、GO・ライブ未活性） | `src/erre_sandbox/evidence/es3_locomotion/` |
| 計測ライン（holding・frozen・不可侵） | `src/erre_sandbox/evidence/**`（d0_substrate / memory_recomp_conformance / spdm / es2_replay / es4_actuator） |
| first-contact 実験（今回） | `experiments/20260706-ecl-v0-live-capture/`（run.sh / env.md / artifacts） |
| Loop Engineering runtime | `loop/20260706-ecl-v0-live-run/`（grill-goals / issues / board / retrospective） |
| 意思決定 ADR（local、gitignore） | `.steering/2026*m13*`（es1〜es4 / substrate / arc-disposition / arc-close / construction / ecl-*） |
| プロジェクト記憶（local） | `~/.claude/projects/…/memory/`（`project_m13_*` 群、MEMORY.md 索引） |

---

## 付記 — 誤読を避けるための一行

> **（2026-07 前半）**「動線・移動・（そして将来）評価機をつなぐ」のうち、動線と移動（建設）が繋がり、
> 『発散を測れる本物の器官が初めて動いた』（ECL v0/v1）。
> **（2026-07-11 更新）** その器官で評価機（計測）を実際に接続して撃った（C-proper）。結果は
> **『歩行→sampling は発火するが、sampling→zone 選択 bias は pre-register した floor では検出できない』**（valid FAIL）。
> これは『発散しない／substrate が無効』ではなく **『効果があるとしてもこの装置では原理的に見えない位置にある』**
> の意。計測ラインは honest に閉じ、**建設の大方針は開いたまま**。次に測るには新しい estimand と superseding ADR が要る。

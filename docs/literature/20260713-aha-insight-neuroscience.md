# 文献カード集: aha!/insight の神経科学 + 計算論的 insight-scoring / LLM-judge

> **サーベイ目的**: aha!/DMN-ECN forward roadmap（`project_aha_dmn_ecn_forward` /
> `.steering/20260713-aha-dmn-ecn-forward/`）の **Phase 1**。着想 = 「aha!（ひらめき）は DMN・ECN の
> 『黄金比』調合から生まれ、それを歩行 λ で調整できる」。この着想が突く gap = 既存 substrate（ERRE モード =
> DMN↔ECN スペクトル `erre/sampling_table.py` + 歩行 λ `erre/locomotion_sampling.py`）で λ が **発散一方向**であり、
> 生成↔評価の**二相交替（switch）が未結線**な点。本サーベイは機構鎖 **調合スイッチ(salience)→洞察マーカー(aSTG)→
> 報酬(reward)** ＋ dynamics / markers / 計算論的手法を落合フォーマットでカード化し、末尾 synthesis で
> 「**think=True reasoning trace から aha-proxy として *何を* 拾えば well-posed か**」を整理する（Phase 2 scoping ADR の入力）。
>
> 出典 SSOT = `docs/references.md`（本サーベイで [12]〜[24] を append）。索引 = `docs/literature/_index.md`。
> 前回サーベイ `20260702-divergent-thinking-benchmarks.md`（[7]-[11]）の続き。

---

## ⚠️ over-read guard（全カード・synthesis に優先する不可侵条項）

- 本サーベイは **doc-only**。**measurement を authorize しない**。R-budget=0 / holding / 凍結 measurement-line は
  door を明示的に開けるまで不変（`project_m13_post_cproper_disposition`）。
- **aha が「起きたか」を scorer で離散判定しない**。survey は door 再開条件「壁2 scorer 先行解決」の**前提整備**であって、
  door を開ける行為でも scorer を確定する行為でもない。
- 以下で「aha-proxy 候補」と書くものは、あくまで **Phase 2 scoping の検討対象の列挙**であり、採用・実装・判定ではない。
- 各カードの神経科学的知見は **ヒト脳の fMRI/EEG 現象**であり、自己回帰生成する LLM の推論トレースへの構造的類推は
  **実証的架橋が存在しない**（相関の対象・時間スケール・機序が根本的に異なる）。この非対称は synthesis で明示する。

---

# (a) salience network（前部島 + dACC）= DMN↔ECN 切替スイッチ

## 文献カード: 右前部島皮質による CEN↔DMN 切替の因果的実証

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [12] (docs/references.md)
- **key**: DOI:10.1073/pnas.0800005105

### 1. それはどんなもの?
3 つの独立 fMRI データセット（音楽イベント分節 N=18 / 視覚オドボール N=13 / 安静時 N=22）に Granger causality
analysis (GCA) を適用し、**右前部島皮質 (right fronto-insular cortex, rFIC)** が central-executive network (CEN) と
default-mode network (DMN) の切替において他の全ノードより高い net causal outflow を持つことを示した実証研究。

### 2. 先行研究と比べてどこがすごい?
先行 (Dosenbach 2006/2007) は FIC と ACC を明確に区別せず、Hodgson 2007 の損傷研究は因果の向きを未検証だった。本論文は
GCA + 潜時解析で「rFIC が先に活動し、CEN 賦活/DMN 抑制の因果的 outflow を持つ」ことを初めて定量提示した。

### 3. 技術や手法の肝はどこ?
2 変量ペアワイズ GCA + ブロックランダム化ブートストラップ (FDR p<0.05) + 活動開始潜時解析。「rFIC = causal outflow hub =
switch を先導するノード」という機能的位置づけ。**switch は連続的な因果的制御であって離散イベントではない**点が肝。

### 4. どうやって有効だと検証した?
異なる認知ドメイン（音楽・視覚オドボール・安静時）の 3 独立サンプルでクロスタスク的に頑健性を検証。

### 5. 議論はあるか?
GCA は相関ベースの推定で真の神経因果を直接証明しない（血管過程 vs 神経過程の分離も推定段階）。von Economo neurons による
高速伝達機序は推測段階。ACC 機能不全時の代替経路は未検証。

### 6. 次に読むべき論文は?
Goulden et al. (2014) *The salience network is responsible for switching between the DMN and CEN: replication from DCM*,
NeuroImage 99:180-190, DOI:10.1016/j.neuroimage.2014.05.052（別手法 Dynamic Causal Modeling による独立再現）。

---
## やり残し (1 行)
> switch が「いつ・何を trigger に」起きるか（何が "aha に値する" かの covert な内的 value 判定）は測っておらず、
> ここが ERRE の空白になりうる ← ただし LLM trace で threshold 化すると連続 process の離散化 = over-read。

---

## 文献カード: Saliency, switching, attention and control — 島皮質機能の統一ネットワークモデル

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [13] (docs/references.md)
- **key**: DOI:10.1007/s00429-010-0262-0

### 1. それはどんなもの?
前部島皮質 (AI) + 背側前帯状皮質 (dACC) からなる **salience network (SN)** が、サリエンス検出 → CEN/DMN 間の動的切替 →
運動系アクセス、という一連機構を担う統一モデルを提示する理論統合レビュー。

### 2. 先行研究と比べてどこがすごい?
Seeley et al. (2007) の SN 構造的定義と Sridharan et al. (2008) [12] の因果的スイッチ実証を統合し、構造的結合 (DTI)・
細胞基盤 (von Economo neurons)・臨床応用（不安障害/自閉症/統合失調症）まで橋渡しした網羅性。

### 3. 技術や手法の肝はどこ?
「ボトムアップのサリエンス検出 → 右 AI の causal outflow hub 機能 → ACC 結合による運動系アクセス」という多段時系列モデル
（刺激後 ~150ms の MMN 検出〜300-400ms の P3b）。GCA・機能的結合・DTI・細胞形態の複数証拠系列を統合。

### 4. どうやって有効だと検証した?
単独の新規実験ではなく、Sridharan (2008) の GCA、Taylor (2009)/Uddin (2010) の結合データ、Critchley/Craig の interoception
研究など既存複数系統を統合参照してモデルを裏付けるレビュー形式。

### 5. 議論はあるか?
著者ら自身が「ヒト島皮質の解剖学的結合はほとんど未解明」「前後島皮質間相互作用の時間力学は不明」「多くの機序は思弁的
(speculative)」と明記。GCA が 30-70ms スケールの精密な時間力学を捉えられない限界も認める。

### 6. 次に読むべき論文は?
Uddin L.Q. (2015) *Salience processing and insular cortical function and dysfunction*, Nature Reviews Neuroscience
16(1):55-61, DOI:10.1038/nrn3857（同著者による後続総括）。

---
## やり残し (1 行)
> 「調合スイッチ」の実体 = SN の切替タイミング/バランスという連続機構であり、ERRE の gap（λ に二相 switch 未結線）に
> 対する**構築ターゲット**（measurement でなく construction knob）としての定位を与える。

---

# (b) right aSTG（前部上側頭回）= aha 瞬間マーカー

## 文献カード: 洞察で言語問題を解くときの神経活動（RH aSTG gamma burst）

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [14] (docs/references.md)
- **key**: DOI:10.1371/journal.pbio.0020097

### 1. それはどんなもの?
Compound Remote Associate (CRA) 言語問題を fMRI (n=13) と EEG (n=19) の別実験で計測し、被験者の主観的 "insight(aha)"
vs "noninsight(analytic)" 自己申告で解を分類。insight 解でのみ **右半球前部上側頭回 (RH aSTG)** の fMRI 活性化と、
解答ボタン押下 **~300ms 前・右側頭電極 T8 の高周波ガンマバースト (~39Hz)** を検出した。

### 2. 先行研究と比べてどこがすごい?
それまで insight は突然性・自信度など主観報告のみで研究され神経基盤は未特定だった。本研究は同一問題セット内 (within-item)
で insight/noninsight を客観的脳指標に対応づけ、「解決の瞬間」に離散的神経マーカーを初めて示した。

### 3. 技術や手法の肝はどこ?
124 題の CRA + 解答直後の二値自己申告、fMRI と EEG の二重測定によるクロス検証、右 T8 vs 左相同 T7 の対照で右半球特異性を
統計的に担保。**判定が完全に主観的自己申告依存**である点が構造的な要（後述 over-read の核）。

### 4. どうやって有効だと検証した?
fMRI: cluster≥500mm³, t[12]>3.43, p<0.005（12/13 被験者で再現）。EEG: 解答前 −0.30〜−0.02s 窓で F[1,18]=4.61, p=0.046、
T8 単一電極 t[18]=3.48, p=0.003。直前の右後頭 alpha burst (~10Hz, PO8) は視覚ゲーティングと解釈。

### 5. 議論はあるか?
insight 判定が主観的自己申告依存で被験者間/試行間のブレを著者自身が認める。言語課題限定で非言語 insight への一般化は未検証。
RH aSTG 活性が出力・情動反応の副産物である可能性を完全排除できていない。

### 6. 次に読むべき論文は?
Kounios et al. (2006) 準備期神経活動 / Subramaniam et al. (2009) gamma burst 追試+気分効果 / Bowden & Jung-Beeman (2003)
CRA 規範データ。

---
## やり残し (1 行)
> 「解決イベント直前の burst マーカー」を LLM trace のトークン位置に機械的に写像して切り出す設計は、この論文の限界
> （insight/noninsight は主観依存・trial 間ブレ）をそのまま輸入し、M13 壁1&4 の第2リンク detectability circularity を aha 版で再演する。

---

## 文献カード: The Cognitive Neuroscience of Insight（10 年統合レビュー）

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [15] (docs/references.md)
- **key**: DOI:10.1146/annurev-psych-010213-115154

### 1. それはどんなもの?
insight を「心的表象の再構成により非自明な解釈を生む突然の理解」と定義し、過去 10 年の insight 神経科学 (fMRI/EEG/tDCS/
薬理) を「解決の瞬間」「解決前の準備状態」「個人差」「直接的脳刺激による促進」の 4 本柱で統合したレビュー。

### 2. 先行研究と比べてどこがすごい?
Jung-Beeman (2004) [14] 以降の単発知見を、解決の瞬間だけでなく解決 **"前" の準備状態 (preparation/resting-state)** まで
時間軸を延ばして統合。trait としての個人差、tDCS/薬理という因果操作研究まで射程に収め、相関→因果の橋渡しを明示。

### 3. 技術や手法の肝はどこ?
「insight を assume でなく isolate している研究のみ」「insight vs analytic を同一問題で比較する適切な統制」を選定基準とし、
gamma burst (~300ms 前・T8・~39Hz) を canonical evidence として位置づける。tDCS（右前頭側頭 anodal + 左 cathodal で
nine-dot 問題 0%→40%）を相関→因果の格上げ試行として提示。

### 4. どうやって有効だと検証した?
gamma burst は Jung-Beeman (2004) と Subramaniam (2009) の独立再現で支持。resting-state 右半球優位性は high-insight 個人の
trait として観察。tDCS で解決率を実験的に操作。

### 5. 議論はあるか?
神経画像・EEG は本質的に相関的。tDCS 研究は「答えより疑問を増やす」段階で、right 刺激/left 抑制どちらが効いたか未分離、
かつ解が真に insight 的か analytic かの区別が tDCS 側でされていない (measurement gap)。

### 6. 次に読むべき論文は?
Kounios et al. (2006) 準備期活動 / Subramaniam et al. (2009) / Metcalfe & Wiebe (1987) メタ認知的 warmth / Chi & Snyder
(2011, 2012) tDCS。

---
## やり残し (1 行)
> 「解決前の準備状態 (preparation)」という時間軸は、aha を「瞬間の離散マーカー」でなく **状態の連続的推移**として扱う
> 見方を与える → LLM trace でも「解の直前トークンの点」でなく「trace 全体の生成→評価の相構造」を見るべき、という synthesis の根拠。

---

# (c) reward network（VTA / 腹側線条体 / dopamine）と aha 情動

## 文献カード: 超高磁場 fMRI が捉えた Aha!-moment の報酬系相関

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [16] (docs/references.md)
- **key**: DOI:10.1002/hbm.24073

### 1. それはどんなもの?
ドイツ語版 RAT（遠隔連想課題）解決中に **7T 超高磁場 fMRI** を撮像し、Aha! 体験の情動的側面（解決時の安堵・喜び）を支える
皮質下ドーパミン報酬系（VTA/腹側被蓋野・NAcc/側坐核・尾状核）の関与を初めて実証した研究。

### 2. 先行研究と比べてどこがすごい?
従来の insight 研究は側頭葉・前頭前皮質など皮質の**認知的**側面が中心で情動側面が手薄だった。7T の高空間分解能
（voxel 1.5×1.5×1 mm³）で 3T では検出困難な小さな皮質下核 (VTA 等) の活動を捉えた。

### 3. 技術や手法の肝はどこ?
48 項目×4 ラン、被験者は解に確信した瞬間に即時ボタン押下し Aha!-moment のタイミングを捕捉。中央値分割で high/low insight
trial を分類。event 解析 + task 解析 + Dynamic Causal Modeling (DCM) で DLPFC-NAcc-海馬-VTA 間の有効結合を解析。

### 4. どうやって有効だと検証した?
event/task 解析とも cluster-level FWE 補正 p<.05（初期閾値 p<.001）、ROI t 検定。DCM で結合方向を推定するが**介入実験ではなく
真の因果証明ではない**。

### 5. 議論はあるか?
NAcc・VTA・海馬が relief/ease/joy の情動と記憶再固定（解の定着）に関与し「Aha! は報酬的処理パターンに従う」と解釈。限界 =
Aha! の時間発展を実験的に統制できていない、因果性は未実証（著者は TMS-fMRI 併用を今後の課題とする）。

### 6. 次に読むべき論文は?
下記 Oh et al. (2020) [17] / Chermahini & Hommel (2010, dopamine と発散思考) / Schwartenbeck et al. (2014, 中脳 dopamine が
結果望ましさの確実性を符号化)。

---
## やり残し (1 行)
> aha=快情動=報酬系という相関は示すが、「その報酬シグナルを RL 報酬として与える」段の well-posedness は未検証 →
> ERRE では「aha 後の内部代理シグナルを報酬に」という**動機付け**には使えるが、代理シグナル設計自体が scorer 設計に等しい。

---

## 文献カード: insight 関連の神経報酬シグナル（EEG、報酬感受性で変調）

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [17] (docs/references.md)
- **key**: DOI:10.1016/j.neuroimage.2020.116757

### 1. それはどんなもの?
アナグラム課題を解く際に高密度 EEG を計測し、insight 解（突然の aha）は non-insight 解（分析的）に比べ、主 insight 効果
（解答 ~500ms 前の前頭前野ガンマバースト）の**約 100ms 後**に別個のガンマバーストが眼窩前頭皮質 (OFC) 等の報酬関連領域から
生じることを発見。この追加バーストは **dispositional reward sensitivity が高い被験者でのみ**有意。

### 2. 先行研究と比べてどこがすごい?
Tik et al. (2018) [16] が fMRI で報酬系の関与を空間的に示したのに対し、本研究は EEG の高時間分解能で insight 効果と報酬効果を
**時間的に分離**した 2 つの独立成分として切り分け、かつ報酬感受性という個人差要因で信号の有無が変調される点が新規。

### 3. 技術や手法の肝はどこ?
高密度 EEG + 自己報告 (insight/analytic) + 時間周波数解析で I-A 効果と reward-sensitivity 効果を検定、信号源を OFC 等へ
source reconstruction。

### 4. どうやって有効だと検証した?
参加者ごとの dispositional reward sensitivity 質問紙スコアと二次ガンマバースト振幅の関連を検証、高 sensitivity 群でのみ有意
という形で I-A 効果とは独立な報酬関連効果であることを時間窓・トポグラフィ双方で分離。

### 5. 議論はあるか?
insight 関連報酬シグナルは探索・問題解決を強化する進化的適応機序の発現かもと提起。一方**アナグラム課題固有への一般化限界**、
相関的知見であり行動強化への直接効果は未証明。信号の有無が個人差で変わり**汎化しない**。

### 6. 次に読むべき論文は?
対の前段 = Tik et al. (2018) [16] / 報酬感受性の神経基盤 (SPSRQ/BAS 系、O'Doherty et al. reward-sensitivity fMRI)。

---
## やり残し (1 行)
> 「快シグナルを scorer として測る」と、何をもって aha 認定するかの基準自体が reward 信号になり循環する（第2リンク
> circularity の RL 版）→ RL 報酬設計は over-read 境界の内側での慎重な切り分けが要る（予算ゼロ制約下でも代理シグナル設計が本丸）。

---

# (d) DMN-ECN dynamics と insight（生成↔評価の二相・交替 = 「黄金比バランス」の実体）

## 文献カード: Creative Cognition and Brain Network Dynamics（レビュー）

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [18] (docs/references.md)
- **key**: DOI:10.1016/j.tics.2015.10.004

### 1. それはどんなもの?
創造的思考を支える脳の大規模ネットワーク動態のレビュー。中心主張 = 「DMN（生成・自己生成思考）と ECN（評価・実行制御）は
通常は反相関だが、**創造的認知課題中には協調する**」。

### 2. 先行研究と比べてどこがすごい?
従来 DMN と ECN は相互抑制的とされたが、本論文は両者が目標指向的・自己生成的思考を支える際には**協力する**枠組みへ転換。
「アイデア生成」と「アイデア評価」で異なるネットワーク動態が生じる段階性を強調。

### 3. 技術や手法の肝はどこ?
発散思考・詩作・音楽即興の fMRI 機能的結合/動的結合を横断統合。発散思考課題では PCC が早期に右前部島 (SN)、後期に右 DLPFC
(ECN) と結合する**時間差パターン**を提示。詩作課題では「生成期は DMN-ECN 負相関、修正期は正相関へシフト」という直接的な
**二相交替エビデンス**を引用。SN を DMN→ECN 切替の**仲介ノード**と解釈。

### 4. どうやって有効だと検証した?
一次研究ではなく統合レビュー（Beaty 2015 / Liu 2015 / Pinho 2015 の fMRI を横断統合）。

### 5. 議論はあるか?
DMN-ECN 協調は普遍的でなく課題の目標指向性の程度に依存、境界条件は未確定。「制御が多い/少ない」の二項対立から
「サブプロセスごとに異なる制御が要る」への転換を提案。

### 6. 次に読むべき論文は?
Beaty et al. (2015) *Default and executive network coupling supports creative idea production* (Sci Rep) / Ellamil et al.
(2012) *Evaluative and generative modes of thought* (NeuroImage, DOI:10.1016/j.neuroimage.2012.02.008)。

---
## やり残し (1 行)
> ERRE に欠けているのは単なる ECN 強度パラメータではなく、SN 相当の**切替タイミング機構**（生成期↔評価期の相 switch）で
> あることを示唆 → 構築ターゲットの解像度を「λ→発散」から「λ→二相 bias」へ上げる根拠。

---

## 文献カード: 脳機能結合からの個人創造能力の頑健予測（cpm）

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [19] (docs/references.md)
- **key**: DOI:10.1073/pnas.1713532115

### 1. それはどんなもの?
Connectome-based predictive modeling (cpm) により、脳機能結合パターンから個人の創造能力（発散思考スコア）を予測できることを
複数独立サンプル（米・墺・中、計 n≈660 超）で実証。

### 2. 先行研究と比べてどこがすごい?
単一領域・単一サンプルに留まっていた先行研究に対し、268 ROI の全脳結合行列を用いた予測モデルを **3 つの独立外部サンプル**で
汎化検証した点が新規。

### 3. 技術や手法の肝はどこ?
high-creative network の上位ノードは DMN（左 PCC）優位、次いで salience（左前部島）、frontoparietal ECN（右 DLPFC）。
理論的解釈 = 「DMN が生成、salience が有望案を同定し ECN へ転送、ECN が評価・洗練」という**三者分業モデル**。

### 4. どうやって有効だと検証した?
Leave-one-out CV 内部検証 r=0.30、外部検証（墺 r=0.35/0.28、統制課題では非有意=特異性確認、中国 resting-state r=0.13、
流動性知能とは無相関=創造性特異）。

### 5. 議論はあるか?
相関量は中程度 (r=0.13-0.35)、low-creative network は外部検証で不安定と明記。低創造性者は「固定化した意味連想が実行制御に
よって効果的に調整されない」と対比。

### 6. 次に読むべき論文は?
Shen et al. (2017) cpm 方法論原典 (Nat Protoc) / 本 repo 既収載 [11] Bartoli et al. (2024) *DMN electrophysiological
dynamics and causal role in creative thinking* (Brain, DOI:10.1093/brain/awae199、電気生理学的因果の直接検証)。

---
## やり残し (1 行)
> 「salience が有望案を同定し ECN へ転送」= 生成候補の中から**何を評価相へ渡すか**の選別機構。ERRE の C→D（idle
> recomposition→行動）設計における「選別 channel」の神経学的対応物 ← ただし移植は over-read（synthesis 参照）。

---

# (e) insight の EEG/fMRI markers（何が「計測可能な洞察代理」か）

## 文献カード: Deconstructing Insight — 洞察の下位過程の EEG 分離計測

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [20] (docs/references.md)
- **key**: DOI:10.1371/journal.pone.0001459

### 1. それはどんなもの?
洞察を単一の「insight か否か」二値でなく、下位過程 — impasse（行き詰まり）/ restructuring（表象再構造化）/ suddenness
（突然性）/ confidence（確信）— を **連続量（0-3 評定）として分解**し、それぞれに対応する EEG 相関を同定。課題は CRA。

### 2. 先行研究と比べてどこがすごい?
Jung-Beeman (2004) [14] 系が「Aha!/no-Aha!」の**二択強制選択**で分類したのに対し、restructuring・suddenness・confidence を
**4 段階連続評定**にし single-trial 解析。「insight 問題は必ず insight で解かれる」という暗黙前提を批判し、解の "insightful さ"
の程度に焦点を移した。

### 3. 技術や手法の肝はどこ?
32ch EEG + complex demodulation の time-frequency 解析、nonparametric cluster randomization。下位過程ごとに **異なる
ROI×周波数帯×時間窓の解離**: impasse→頭頂後頭 gamma / hint 後 re-solve→右側頭 upper alpha / restructuring 大→右前頭前野
alpha 減少 / suddenness→解答 1.5s 前の頭頂後頭 gamma。

### 4. どうやって有効だと検証した?
restructuring 評定と suddenness 評定の相関が負 (ρ=−0.39) = 「突然の解は意識的処理をほとんど伴わない」という解離を統計的に
確認。正誤・hint 利用成否という行動アンカーとの対比で EEG 特徴の妥当性を裏付け。

### 5. 議論はあるか?
insight-problem という枠組み自体が「これらは insight でしか解けない」を暗黙に置く点は完全には脱していない。**重要な欠落 =
本論文は "warmth"（解への接近感、Metcalfe & Wiebe 1987 系）を使っておらず**、尺度は restructuring/suddenness/confidence の
3 軸のみ（confidence は warmth の代替だが同一構成概念とは明言されない）。

### 6. 次に読むべき論文は?
Metcalfe & Wiebe (1987) feeling-of-warmth 原典 / 下記 Dietrich & Kanso (2010) [21] / Kounios & Beeman (2014) [15]。

---
## やり残し (1 行)
> **非対称な事実**: 「restructuring/suddenness/confidence の 3 軸なら神経的裏付けがある」が「warmth を測る scorer を作る根拠」は
> この文献からは得られない → 壁2（scorer 先行解決）で*どの*代理量に生物学的根拠があるかを選別する材料。

---

## 文献カード: creativity/insight の神経画像研究メタレビュー

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [21] (docs/references.md)
- **key**: DOI:10.1037/a0019749

### 1. それはどんなもの?
creativity 神経科学の meta-review。63 論文・72 実験を divergent thinking / artistic creativity / insight の 3 カテゴリに整理。

### 2. 先行研究と比べてどこがすごい?
個別研究の断片的知見を横断整理し「creativity は単一プロセス・単一脳部位に還元できない」と結論。右脳優位説・defocused
attention 説・低覚醒説を明示的に反証。

### 3. 技術や手法の肝はどこ?
narrative synthesis（一次データなし）。カテゴリ別の知見一貫性を評価 — 発散思考の EEG/fMRI 知見はバラバラ（前頭前野の
diffuse activation 止まり）だが、**insight 研究は ACC と前頭前野変化について相対的に一貫**と報告。

### 4. どうやって有効だと検証した?
一次実験でなくレビュー。多研究間のパターン一致・不一致の整理。

### 5. 議論はあるか?
creativity を単一構成概念として扱うことの妥当性に疑義を呈し、type 別（発散思考/芸術的創造性/洞察）への分解を提案 —
Sandkühler & Bhattacharya [20] の「insight を下位過程に分解」と粒度は違うが「洞察は単一現象でない」という方向性は一致。

### 6. 次に読むべき論文は?
2010 年以降の insight neuroimaging アップデート（Science Bulletin 系のレビュー等、書誌未確認・候補止まり）。

---
## やり残し (1 行)
> 「発散思考の神経相関はバラバラだが insight は相対的に一貫」= 計測代理として *insight* の方が *divergent thinking* より
> 分離可能性が高い、という survey レベルの示唆（ただし LLM trace への転用可能性は別問題 = over-read）。

---

# (f) 計算論的 insight/creativity 検出・LLM-judge 手法（+ reasoning trace の "aha moment"）

## 文献カード: Beyond Semantic Distance — LLM fine-tuning による発散思考自動採点 (Ocsai)

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [22] (docs/references.md)
- **key**: DOI:10.1016/j.tsc.2023.101356

### 1. それはどんなもの?
Alternate Uses Task (AUT) 応答の originality を、事前学習 LLM (T5 / GPT-3 系) を人間評定データで **fine-tuning** して自動採点
するシステム "Ocsai"。9 研究・~27,000 応答（重複除去後 20,202 件）の人間評定を統合した大規模データで学習・評価。

### 2. 先行研究と比べてどこがすごい?
従来の主流 (SemDis [7]) は意味距離による**教師なし**手法で r=.12〜.26 止まり。Ocsai は**教師あり fine-tuning** へ転換し
r=.76〜.81（最良 r=.813）を達成し、人間評定者間の相関上限 (r=.83〜.88) にほぼ到達。

### 3. 技術や手法の肝はどこ?
pretrain-and-finetune。T5 は text-to-text 形式で数値文字列を出力。**転移性検証** = 学習に含まれない 5 held-out プロンプトで
r=.63（意味距離手法が最も有利なはずの設定で逆転）。

### 4. どうやって有効だと検証した?
80-5-15 分割で Pearson 相関 + RMSE。学習データ量 1%〜100% の性能曲線（1%=160 件でも r=.31〜.48）で頑健性を確認。

### 5. 議論はあるか?
(a) LLM 埋め込みの教師なし意味距離はモデルサイズが大きいほど性能が**下がる**逆説的結果 → 意味距離モデル自体の上限を示唆。
(b) fine-tuned モデルの強さの理由は未解明（言語理解か、評定者集団固有の隠れパターン学習か）。(c) **重要**: chain-of-thought
説明は "hallucinated" でありうる — 「LLM の思考過程の説明は、実際にその通り選んだ保証はない」(Kojima et al. 2022 引用)。

### 6. 次に読むべき論文は?
Buczak et al. (2022) feature-engineering 教師あり比較 (DOI:10.1002/jocb.559) / Beaty & Johnson (2021) SemDis [7] /
Kojima et al. (2022) *LLMs are zero-shot reasoners* (arXiv:2205.11916)。

---
## やり残し (1 行)
> Ocsai が測るのは **response の originality（連続量、教師あり検証済み）**であって「trace 内の aha 瞬間の検出」ではない →
> 「aha-proxy scorer」と「originality scorer」を混同しないことが well-posedness の要（synthesis 参照）。

---

## 文献カード: DeepSeek-R1 — RL 推論トレース内に創発した "aha moment"（観察的命名）

- **日付**: 2026-07-13
- **トピック**: aha-insight-neuroscience
- **出典**: [23] (docs/references.md)
- **key**: arXiv:2501.12948（査読版: Nature 645(8081):633-638, DOI:10.1038/s41586-025-09422-z）

### 1. それはどんなもの?
人間注釈の reasoning 例やプロセス報酬モデルを使わず、rule-based 報酬（正誤+フォーマットのみ）だけの大規模 RL (GRPO) で LLM の
推論能力（self-verification・reflection・長い思考連鎖）を引き出せることを示した技術報告。純 RL の R1-Zero と、少量 cold-start
SFT+多段 RL の R1 の 2 系統。

### 2. 先行研究と比べてどこがすごい?
OpenAI o1 系列に匹敵する数学・コード・STEM 推論性能を、人間注釈 reasoning chain や MCTS なしのシンプルな RL のみで達成と主張。
SFT-first（reasoning 蒸留）に対し **RL-first でも高度な推論戦略が創発**することを示す。

### 3. 技術や手法の肝はどこ?
GRPO 大規模 RL、報酬は accuracy + format のみ（neural reward model を使わず reward hacking を回避）。学習過程で応答長と
self-reflection 頻度が自然増大する現象を §2.2.4 で報告し、**著者はこの現象自体を "aha moment" と命名**（モデルが "Wait, wait.
… That's an aha moment" のように一度立てた解法を "wait" で中断し再考する挙動）。

### 4. どうやって有効だと検証した?
定量面は AIME 2024 等の benchmark スコア。**"aha moment" 自体は数値的に検証された概念ではない** — 根拠は (a) 特定応答例の
抜粋提示という定性的観察、(b) Nature 版 Extended Data で "wait" 等の語の出現頻度が学習ステップ ~8,000 で急増する記述的統計、の 2 種のみ。
**形式的な分類器・検出閾値・報酬項は論文のどこにも存在しない**。

### 5. 議論はあるか?（over-read 論点の核）
著者自身が「これは我々**研究者**にとっての aha moment でもある（RL の力と美しさを目撃させる）」と明記 — "aha moment" は
**(i) モデルの訓練中行動の記述**であり同時に **(ii) 研究者自身の観察上の感嘆**という二重の意味で使われる純粋に観察的・物語的な
命名であって、well-posed な scorer や reward 項ではない。後続 Yang et al. (2025) [24] は self-reflection が RL の epoch 0 から
既に一部観測される反例を示し、**「aha = "wait" 等の reflection 語彙の出現」だけで定義することはできない**と over-read を明示批判。

### 6. 次に読むべき論文は?
Yang et al. (2025) *Understanding Aha Moments: from External Observations to Internal Mechanisms* (arXiv:2504.02956) [24]。

---
## やり残し (1 行)
> DeepSeek-R1 の "aha moment" 命名は **well-posedness（記述としては有効）と over-read risk（形式化した途端に崩れる）を単一の
> 実例で同時に例証**する → ERRE 側で scorer/報酬項に定式化した瞬間、C-proper の第2リンク circularity が再来する最重要 anchor。

---

# ⟐ synthesis: think=True reasoning trace から拾える well-posed aha-proxy の整理

> **位置づけ（不可侵）**: 以下は Phase 2 scoping ADR の**入力**であり、**judge/RL 設計の前提整理**にすぎない。
> measurement を authorize せず、aha を「起きた/起きない」で離散判定する scorer を確定もしない。判定・fork（construction-only か
> measurement door か）は Phase 2 で、door を開ける判断は **user 裁定**。

## S1. 機構鎖 → ERRE substrate 対応（何が構築ターゲットで、何が measurement か）

| 機構鎖 | 神経科学の実体 | ERRE 対応 | 種別 |
|---|---|---|---|
| 調合スイッチ (a) | SN (rFIC/dACC) の CEN↔DMN 因果的切替 [12][13] | λ に**未結線**の生成↔評価 switch | **construction ターゲット** |
| dynamics (d) | DMN↔ECN の二相交替・SN 仲介 [18][19] | λ を「発散一方向」から「二相 bias」へ上げる根拠 | **construction ターゲット** |
| 洞察マーカー (b) | RH aSTG ~300ms gamma burst [14][15] | trace 上の「解直前の点」 | **measurement（離散化は over-read）** |
| markers (e) | restructuring/suddenness/confidence の分離計測 [20][21] | trace 上の代理量候補 | **measurement（構成妥当性未検証）** |
| 報酬 (c) | VTA/NAcc/OFC の aha 報酬シグナル [16][17] | RL 報酬成分の**動機付け** | **measurement（well-posed 未確立）** |
| 計算論的 (f) | LLM-judge originality [22] / RL trace "aha" [23] | judge/scorer の設計原型 | **両義（下記 S3）** |

**要点**: 機構鎖の前半（switch/dynamics）は **construction knob** として well-motivated（λ↔二相 bias の建設は measurement を
要さない）。後半（marker/reward/scorer）は全て **measurement 領域**であり、凍結ラインの内側。

## S2. well-posed に「拾える」もの vs over-read になる「読み」

**well-posed（Phase 3 の "record→観察のみ・存在確認" と整合、scorer 化しない）**:
- think=True trace の **生成相↔評価相の二相構造**を*記述的に*観察する（dynamics [18] の二相交替が LLM trace に現れるかの
  存在確認）。← これは verdict でなく existence。
- 再考マーカー（"wait" 等）の**出現頻度統計**を*記述的に*見る [23]。ただし Yang et al. [24] の epoch-0 反例より、
  これ単体を「aha の達成」と**定義しない**。
- response の **originality** を連続量で採点する手法は教師あり検証済み [22] — ただしこれは「trace 内 aha 瞬間検出」とは**別物**。

**over-read（第2リンク detectability circularity の aha 版・凍結ライン再開に相当、Phase 1 では採らない）**:
- trace のどこかを「aha 瞬間」として**離散マーカーで機械的に切り出し**て測る（[14] の主観依存・trial 間ブレをそのまま輸入）。
- aha の**快シグナルを reward 項に formalize** する（[17] は個人差で信号有無が変わり汎化せず、基準自体が reward になり循環 [16]）。
- "wait" 語彙頻度 = aha と**定義**する（[24] が明示反証）。
- neural ROI 特異性（gamma burst / alpha 減少）を LLM の attention/logit 軌跡へ比喩写像する（構成妥当性の架橋ゼロ）。

## S3. 壁2（scorer 先行解決）に対する honest verdict

- **survey は「使える well-posed aha scorer」を手渡さない**。手渡すのは: ① 連続 originality の教師あり LLM-judge 方法論 [22]
  （ただし対象は response originality で aha-moment ではない）、② 生物学的裏付けのある分離可能な下位過程 3 軸
  （restructuring/suddenness/confidence [20]、ただし "warmth" は裏付けなし・**非対称**）、③ trace 内 aha が現状**観察的概念**で
  あり素朴な形式化は失敗するという実証 [23][24]。
- したがって **壁2 は survey 段では未解決**。「aha が trace に現れうる」ことの*存在*は Phase 3 で観察しうるが、それを*測る* scorer の
  well-posedness は本サーベイでは立たない。→ この事実は Phase 2 fork を **construction 寄り**に制約する材料（door を開けるなら、
  scorer は別文脈 from-scratch で「originality 型の連続・教師あり・外部 anchor」設計から始める必要があり、「aha 瞬間の離散検出」から
  始めてはならない）。

## S4. `<think>` トレードオフへの含意（Phase 2 の linchpin への申し送り）

- 二相（生成↔評価）は dynamics 文献 [18][19] が神経レベルで実在を示す現象。**think=True trace で二相が *観察可能な形* で現れるか**は
  Phase 3 の存在確認テーマ（over-read guard = 観察であって scoring でない）。
- 決定性（think=False = 全 sealed golden の前提）と二相可観測性（think=True）の両立は別 capture 体制が要る（roadmap Phase 2 (b)）。
  survey はこの体制の**設計要件**として「記述統計（相構造・再考頻度）を*非 verdict* で記録する」レベルに留めるべきことを支持する。

## S5. over-read guard（再掲・結語）

本サーベイは door の**前提整備**であって door を開けない。R-budget=0 / holding / measurement-line CLOSE は不変。
「aha-proxy 候補」は Phase 2 の検討対象の列挙であり、採用・実装・判定ではない。construction-only fallback
（λ↔二相 knob 建設、measurement 非再開）は各 phase で確保される。→ 次 = Phase 2 reasoning-trace door scoping ADR
（Plan mode + reimagine + Codex、doc-only、fork 判定、door 3 条件組立て。door を開ける判断は user 裁定）。

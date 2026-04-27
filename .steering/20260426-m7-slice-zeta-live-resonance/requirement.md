# M7 Slice ζ — Live Resonance (live検証 issue 集約 → 認知差分 + xAI + 環境演出)

## 背景

2026-04-21 / 04-22 / 04-26 の **3 回の live 検証** (G-GEAR / MacBook 観察) で、
ユーザー (mikotomiura) から **計 13 件の体感的違和感** が ERRE-Sandbox_issue
(1).docx に書き起こされた。これらは個別バグではなく **「3 体の偉人エージェント
が同じに見える」「世界が薄くて夜のまま」「reasoning と成長が見えない」** という
**ERRE のコア提案 (意図的非効率性 + 身体的回帰 + 認知の異質性)** が live で
体感されないという、**proposal-vs-experience ギャップ** の集約サインである。

M7-α〜ε は「関係性ループ (relational_memory ↔ semantic_memory ↔
belief_promotion)」と hygiene 集約に専念した結果、**backend は M7δ で 5/5
PASS** に達した一方、**Godot 視覚層と persona 機械化が背中合わせに遅延**
している。M9-LoRA に進む前に、この「見える差分・見える社会・見える成長」を
ζ slice として 1 回まとめて回収する必要がある。

これは新規機能 slice であり、ε (hygiene) とは scope が独立している。
ε は code review 中 (PR-ε-2 / 本ブランチ feat/m7-epoch-phase-filter)
であり、ζ は ε merge 後に着手する想定。

## live 検証 issue (source of truth)

`/Users/johnd/Downloads/ERRE-SandBox_issue (1).docx` 全 13 件を以下に整理。
カテゴリは事後分類であり、issue 本文の言い回しは保存する。

### A. ワールド/ビジュアル (5 件)

- A1 (04/26) **常に夜という感じ・気分的に良くないかも** → 太陽 / 時間の概念
- A2 (04/26) **のっぺりとした感じ・茶室など世界自体がすごい薄い感じ**
- A3 (04/21) **茶室など現在建てられているフォールドの建物をもう少し大きく
  + デザインも多様性を持たせる**
- A4 (04/22) **もう少し world を広くしたい**
- A5 (04/22) **agent 三人が一つのスポットに集結される時がある → 改善**

### B. agent 別の認知/行動差分 (3 件)

- B1 (04/22) **動きの種類が単純すぎる → agent 別で event/動きを別々に。
  違う生物としていくつもり**
- B2 (04/22) **Reasoning panel 内の行動指針はすべて統一されているのか？
  → agent 別で別々に**
- B3 (04/21) **mode 変換などで、それぞれの agent が脳内でどういった決定処理
  などを行なってシナプスでの行動を行なっているかの Reasoning が覗ける
  ように** → 認知プロセス可視化 (xAI) — B 軸に分類するが C 軸とも重なる

### C. xAI (認知プロセス可視化) と社会形成 (3 件)

- C1 (04/21) **イベントによる llm との連動における認知プロセスの具体化 +
  イベント数の増加・改善設計**
- C2 (04/21) **どこの箇所のフィールドでさまざまなイベントを与えているかなど
  の境界線**
- C3 (04/26) **生息している agent たちが会話したり、それぞれの agent らで
  生命活動を行なっている → 実際の本物としての社会形成**
- C4 (04/26) **ほかの agent たちの Reasoning パネルも見れるように**
- C5 (04/22) **MASTER-PLAN にあった三名での対話・反省・関係形成は具体的に
  設計できているのか、そこまでできていないように見えた**
- C6 (04/22) **LATEST REFLECTION 内の文字が英語なので日本語に**

### D. 成長メカニズム + 全体プラン (2 件)

- D1 (04/22) **具体的にどのようにして agent が成長していくのかなども具体的
  に。現在は全くわからない。xAI 化するのも良いのかも**
- D2 (04/22) **全体のプランを練る (どれぐらいデータを集めたら LoRA を適用
  するのか、agent を増やしていくのか、実際に agent と対話できるようにする
  か否か)**

### E. UX / 操作系 (1 件)

- E1 (04/21) **マウスなどで操作してから world 内を俯瞰して全体が見れたり、
  world を寄せてからもっと近くで見れるようにしたり、mode 変換**

### F. 追加 issue (2026-04-27 ζ-1 部分マージ後 live 観察、3 件)

ζ-1 の Godot 完結変更 (day/night / JP locale / agent selector / camera tune) を
適用した live 検証で **大まかな修正は確認済み** だが、以下 3 件が新たに浮上。
F1/F2 は B/C 軸の **次段階要求**、F3 は E1 とは別系統の viewport 問題。

- F1 (04/27) **agent たちが直接的に会話をしている様子を見たい** —
  既存 C3/C5 が「関係値・信念状態の表示」までだったのに対し、F1 は
  **「3 体が実際に喋っている (吹き出し / 字幕 / dialog stream の即時表示)」**
  という更に直接的な表現を求める。dialog_turn は M5 で動作しているが、Godot
  視覚層に **発話イベントそのものが出ていない** ことが体感ギャップの正体。
- F2 (04/27) **FPS のように完全に人間が歩行している形にしてほしい** —
  既存 B1 が「移動速度の persona 別差分」までだったのに対し、F2 は
  **「歩行アニメーション (walk cycle)・足音・体の上下動」** までを含む
  人間らしい歩行表現を求める。現状 `AgentController.gd` は linear tween で
  座標を補間するだけ、AnimationPlayer / AnimationTree 未接続。
- F3 (04/27) **world 画面自体がとても小さいので拡張してほしい** —
  添付スクリーンショット (`/Users/johnd/Desktop/スクリーンショット
  2026-04-25 17.32.40.png`) で 3D viewport が canvas 中央に小さく表示
  され、上下左右に黒余白が大きく残っている。既存 E1 (camera 操作) や
  A4 (world 物理サイズ拡張) とは別問題で、**Godot ウィンドウ / viewport
  / UI レイアウトの aspect / anchor 設計** が原因と推定。

## 根本原因 (調査済 — 偵察 3 並列 Explore agents による)

### 軸 A の根本原因
- A1: `godot_project/scenes/MainScene.tscn:12-17,41-46` で background_mode=1
  (SOLID COLOR) + 単一 DirectionalLight3D 固定。**day/night cycle 機構そのもの
  が未実装**。
- A2: `godot_project/scenes/zones/*.tscn` 全 zone が primitive box/cylinder。
  Blender .glb pipeline (`erre-sandbox-blender/`) が `assets/environment/`
  に到達していない (Chashitsu.tscn:4-8 のコメント "Blender-produced .glb
  supersedes when present")。AO/Fog/法線マップ全欠落。
- A3: 茶室 6×6m / 各 zone 18-30m 程度、primitive のみ・バリエーション皆無。
- A4: `WorldManager.gd:32-40` で `WORLD_SIZE_M=100`。Slice β で 60m → 100m
  拡張済だが live 観感としてまだ狭い。
- A5: `AgentController.gd:98-134` の `set_move_target` は linear tween のみ。
  agent 同士の collision avoidance / separation 一切なし。Python orchestrator
  が 3 体に対し近接 waypoint を発行すると同点 collapse する。

### 軸 B の根本原因
- B1: `cognition/cycle.py:695` で `DEFAULT_DESTINATION_SPEED=1.3` ハード
  コード、persona 別上書きなし。
- B2: ReasoningTrace に persona_id / personality 反映なし
  (`cognition/cycle.py:725-738`)。Godot ReasoningPanel がペルソナ識別を
  表示しないため、3 体 trace を文字内容でしか弁別できない。
- B3: `cognition/prompting.py:65-89` で `cognitive_habits` は LLM プロンプト
  のテキストにしか効かない。runtime 動作 (歩行リズム / バースト周期 / 休息
  時間 / 滞留時間) には全く反映されない。
- 共通: `world/tick.py:310` で **全 agent の cognition tick が 10 秒固定**。
  Nietzsche の 20-40 分バースト + 1-3 時間休息、Rikyu の 20 分 seiza は
  時間軸で表現できない。

### 軸 C の根本原因
- C1, C2: zone-trigger と event の境界線が UI に出ていない。
  `WorldRuntime` 内では zone enter/exit は signaling されているが、Godot 側で
  「いまどの zone・どの affordance がどの reasoning を起こしたか」が
  panel に紐付かない。
- C3, C5: dialog_turn / reflection / relational_memory / belief_promotion は
  M7δ で動作確認済 (run-02 5/5 PASS) だが Godot 視覚層が **数値・テキスト
  ともに未表示**。
- C4: `ReasoningPanel.gd:26` の `_focused_agent: String = ""` で **単一焦点
  設計**。multi-agent tab / split-view 未実装。SelectionManager は
  click-select のみで agent 切替 UI なし。
- C6: `ReasoningPanel.gd:91-120` でラベル文字列ハードコード英文。Godot
  `tr()` / .csv localization 機構そのものが未導入。

### 軸 D の根本原因
- D1: experience → behavior change の **観測 signal が未設計**。M8 で
  episodic_log + session_phase + baseline_metric は揃ったが、**「成長して
  いる」とユーザーが知覚できる UI/メトリック** がない。
- D2: M9-LoRA gate は MASTER-PLAN §11 に記載があるが、データ閾値・適用
  go/no-go・対話可能化の判断基準が **decision document として独立して
  いない**。

### 軸 E の根本原因
- E1: `CameraRig.gd:27-35,76-139` で 4 modes (OVERVIEW/FOLLOW_AGENT/
  MIND_PEEK/TOP_DOWN) 実装済。orbit_speed=0.006、pan_speed=12.0、
  zoom_speed=2.5 は **数値設定が控えめ** で応答性が鈍い。複合操作
  (shift+drag, ダブルクリックで focus 等) なし。

### 軸 F の根本原因 (推定 — 別タスクで偵察予定)
- F1: dialog_turn payload は M5 から WS 経由で届いているが、
  `godot_project/scripts/ReasoningPanel.gd` には反省 (LATEST REFLECTION) の
  単発表示はあるものの、**会話 stream / 吹き出し (Label3D over agent head) /
  即時 ticker 表示** が未実装。発話イベントの視覚化レイヤがない。
- F2: `godot_project/scripts/AgentController.gd` の `set_move_target` は
  Tween ベースの座標補間のみ。`AnimationPlayer` / `AnimationTree` が
  agent シーンに接続されておらず、**walk cycle / idle / talk のステート
  マシンそのものが未実装**。さらに `assets/characters/` に humanoid
  rigged mesh (.glb) も未配備で、現在 agent はおそらく primitive capsule
  または single mesh。
- F3: 推定原因 3 系統あり、要偵察:
  (a) Godot project 側 `display/window/size/viewport_width|viewport_height`
      の固定値 (project.godot)、
  (b) `ReasoningPanel` の Control anchor が SubViewport を圧迫、
  (c) `MainScene.tscn` の root が CanvasLayer + 黒背景 ColorRect で
      viewport を中央寄せしている可能性。
  いずれにせよ Godot UI レイアウト系で完結する変更で解決可能。

## ゴール (受け入れ条件と紐付け)

ζ は M7 の **後半 expansion slice** として、A〜E のうち **「live で体感が
変わる比較的低リスクな改善」を集約**し、D の戦略タスクは別文書 (M9 pre-plan)
に切り出す。**M9-LoRA に着手する前に live 体験の解像度を底上げする**
ことが第一目的。

ベースゴール:

1. **3 体が違う生物に見える** (B1+B2+B3) — 移動速度 / cognition 周期 /
   滞留時間 / Reasoning panel の persona 表示
2. **3 体が一箇所に collapse しない** (A5) — collision-avoidance / separation
3. **時間概念がある** (A1) — day/night cycle (1 cycle = 30-60 minute 程度)
4. **Reasoning panel が persona 切替できる** (C4) — agent selector UI
5. **LATEST REFLECTION が日本語** (C6) — ラベル翻訳
6. **3 名対話・反省・関係形成が UI に見える** (C3+C5) — 関係値 / 信念状態
   (trust/clash/curious/wary) を panel に表示
7. **(stretch)** world サイズ 100→160m、camera 感度調整、フォグ追加で
   のっぺり解消 (A2+A4+E1)
8. **D は ζ 外** で M9 pre-plan に切り出す

## スコープ

### 含むもの (ζ 本体)

- B 軸: persona ごとの `movement_speed_factor` / `cognition_period_s` /
  `dwell_time_s` フィールドを `PersonaSpec` に追加し runtime で効かせる
- B 軸: `ReasoningTrace` に `persona_id` を追加 (schema bump)
- A5: AgentController に簡易 separation force (近接 agent から離れる)
- A1: DirectionalLight3D を時間進行で回転、環境光と背景色を同期 (1 cycle =
  30 分程度、Godot 側で完結、backend には影響しない)
- C4: ReasoningPanel に agent タブまたはセレクタ追加 (3 体切替)
- C6: 英文ラベル → 日本語 (`tr()` または定数辞書)
- C3+C5: 関係値 / 信念状態を Reasoning panel に表示

### 含まないもの (defer)

- **D1+D2 (成長メカニズム + LoRA gate)** → 新タスク `m9-lora-pre-plan` に
  切り出し
- **A2+A3 (Blender .glb pipeline 完成)** → 別タスク
  `world-asset-blender-pipeline` に切り出し (アセット制作は ε と独立して
  時間がかかるため別線)
- **C1+C2 (event 境界線可視化の本体)** → ζ で signal だけ整え、UI 全実装は
  M10-11 evaluation layer
- **agent との対話 (D2 後半)** → M11 player-agent dialog 線
- **E1 (camera 操作の polish 全部)** → ζ で sensitivity だけ調整、複合操作
  追加は別 slice
- **A4 (world 拡張 100→160m)** → stretch、PR が肥らないよう Plan で
  決定
- **F1 (agent 同士の直接会話の視覚化)** → ζ-2 で persona_id wire は届くため、
  発話の **吹き出し (Label3D) / 字幕 ticker / dialog stream の panel 表示**
  本体は新タスク `dialog-visualization` に切り出し。dialog_turn payload の
  WS 経路だけ ζ-2 内で点検し、視覚層は別 slice。
- **F2 (FPS-style 歩行アニメーション)** → 新タスク
  `agent-locomotion-animation` に切り出し。AnimationTree state machine と
  humanoid rigged mesh のセットアップは Blender pipeline (A2/A3) と
  共依存になりがちなため `world-asset-blender-pipeline` と並走線で扱う。
- **F3 (world viewport の拡張)** → ζ-1 と独立した Godot UI レイアウト調査
  が必要。新タスク `godot-viewport-layout` に切り出し、root scene anchor /
  project window size / ReasoningPanel split ratio を 1 PR で見直す。

### スコープ外との境界

- ε は code review 中。**ζ は ε merge 後に main 上で着手**。schema 衝突を
  避けるため SCHEMA_VERSION bump は ε の 0.8.0-m7e の上に 0.9.0-m7z (仮)。
- Persona YAML は **stem 不変** (`personas/kant.yaml` 等) — フィールド追加
  のみ、後方互換 default を持つ。
- Godot 側で完結する変更 (day/night、selector UI、ラベル翻訳) は schema
  bump 不要。

## 受け入れ条件

- [ ] 3 体の移動速度・cognition 周期が persona 別 (live で目視可能な差)
- [ ] 3 体の Reasoning panel に persona_id / display_name / personality
  サマリが表示される
- [ ] 3 体が同一座標に同時 collapse しない (separation が効く)
- [ ] 30 分以上の live run で背景が朝→昼→夕→夜のサイクルを 1 周以上通る
- [ ] Reasoning panel が agent 切替 (タブ or セレクタ) で 3 体すべての trace
  を順次閲覧できる
- [ ] LATEST REFLECTION → 「最新の反省」など日本語表記 (5 ラベル以上)
- [ ] 関係値 / 信念状態が panel に何らかの形で見える (text or icon)
- [ ] 全 pytest pass、ruff/mypy clean、code-reviewer 0 HIGH
- [ ] live G-GEAR run-01-zeta で 5/5 acceptance gate 維持 (δ regression なし)
- [ ] **live 観で「3 体が違う生物に見える」とユーザーが体感できる** (定性)

## 関連ドキュメント

- 偵察結果: 本ファイル「根本原因」節 (3 並列 Explore agents による調査)
- M7δ: `.steering/20260426-m7-slice-delta/`
- M7ε: `.steering/20260426-m7-slice-epsilon/` (現行、code review 中)
- M7 differentiation pre-work: `.steering/20260424-m7-differentiation-observability/`
- M5 ERRE mode FSM + dialog turn: `.steering/20260421-m5-orchestrator-integration/`
- MASTER-PLAN: `.steering/20260418-implementation-plan/MASTER-PLAN.md` §5.1
- live 検証 issue 原本: `/Users/johnd/Downloads/ERRE-SandBox_issue (1).docx`

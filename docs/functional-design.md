# 機能設計書

## 1. プロジェクト概要

- **プロダクト名**: ERRE-Sandbox
- **正式名称**: Autonomous 3D Society Emerging from the Cognitive Habits of Great Thinkers
- **解決する課題**: 現行の LLM エージェント研究は「効率」「タスク達成」「人間水準の再現」を暗黙の目的関数としており、認知神経科学が示す「非効率・身体運動・注意の弛緩が高次認知を駆動する」知見が設計に反映されていない
- **ターゲットユーザー**:
  1. **ゲーム・エンタメ開発者** (最優先): 固定スクリプト NPC ではなく自律的に文化を築く「生きた村」を実現したいインディー開発者
  2. 認知科学・社会心理学研究者: 人間被験者実験の事前探索器具として
  3. 人文学研究者: ERRE の Extract/Reverify を史料読解の新手法として
  4. 教育者: 哲学概論・認知科学入門の講義教材として
- **コアバリュー**: 「意図的非効率性 (deliberate inefficiency)」と「身体的回帰 (embodied return)」を一級の設計プリミティブとして扱い、既存の生成エージェント社会が到達できない種類の知的創発を観察可能にする

## 2. コア機能一覧

### 機能 1: ERRE パイプライン

偉人の認知習慣をソフトウェアに翻訳する4段階プロセス。

#### 1a. Extract (認知構造抽出)
- **概要**: 一次史料と現代批判的伝記から、各偉人の認知習慣を観察可能な行動述語の集合として抽出
- **入力**: 一次史料テキスト (青空文庫・Gutenberg・archive.org、PD)、批判的伝記
- **出力**: `personas/*.yaml` (認知習慣リスト、事実/伝説フラグ付き)
- **振る舞い**: LLM 支援 + 研究者検証のハイブリッド。各項目に fact/legend フラグを必ず付与
- **エラー条件**: 史料不足時は伝説フラグを明示、一次史料なしのペルソナは作成不可

#### 1b. Reverify (脳科学的再検証)
- **概要**: 抽出された各習慣に対応する認知神経科学的機序を対応表として付与
- **入力**: Extract で得た認知習慣リスト
- **出力**: 習慣-機序対応表 (例: 歩行 → DMN 活性化、発散思考 +60%)
- **振る舞い**: 各習慣が人文的修辞ではなく神経・認知的機構への主張として扱えるよう検証
- **エラー条件**: 対応する認知科学的根拠が見つからない習慣は「未検証」フラグ付きで保持

#### 1c. Reimplement (ソフトウェア実装)
- **概要**: Reverify された機序を CoALA 公理系に対応させて実装
- **入力**: 習慣-機序対応表
- **出力**: エージェントの状態遷移規則、サンプリングパラメータ
- **振る舞い**:
  - 歩行時 (peripatetic): 温度 +0.3、top_p +0.05、反復ペナルティ -0.1 で発散的生成
  - 茶室/座禅時: 温度 -0.2、top_p -0.05 で収束的生成、重要度上位のみ検索
  - 守破離: shu=固定スクリプト、ha=逸脱報酬、ri=自己プログラム生成解禁

#### 1d. Express (3D社会としての表現)
- **概要**: エージェント状態を Godot 4 上の3D環境で描画
- **入力**: エージェント状態 (位置・回転・アニメーション・発話)
- **出力**: 3D シーン上のアバター動作、リアルタイムダッシュボード
- **振る舞い**: WebSocket 30Hz でエージェント状態を Godot に送信、5ゾーン (街区・庭園・茶室・書斎・歩行路) を描画

### 機能 2: エージェント認知サイクル

CoALA 準拠 + ERRE 拡張の認知ループ。

- **概要**: 各エージェントが 10 秒 (シミュレーション時間) ごとに認知サイクルを実行
- **入力**: 現在の観察 (環境・他エージェントの行動)、AgentState、記憶検索結果
- **出力**: 行動選択 (移動・発話・沈黙・反省)
- **振る舞い**: Observe → Appraise → Update State → Retrieve → Reflect? → Plan → Act → Speak
- **ERRE 独自拡張**: peripatos/chashitsu 入室時、importance 閾値未満でも温度を上げた自由連想型内省を発火 (DMN-inspired idle reflection window)
- **エラー条件**: LLM 推論タイムアウト時はデフォルト行動 (現在の行動を継続)

### 機能 3: 記憶システム (Memory & RAG)

sqlite-vec ベースの階層的記憶。

- **概要**: エージェントごとの長期記憶 + 共有ワールド記憶
- **入力**: 各 tick の観察・対話・反省結果
- **出力**: コンテキストに注入する記憶断片 (per-agent top-8 + world top-3)
- **振る舞い**:
  - 4種の記憶: Episodic (時刻付き観察)、Semantic (反省から蒸留)、Procedural (スキルライブラリ)、Relational (関係グラフ)
  - 減衰式: `strength = importance * exp(-λ*days) * (1 + recall_count*0.2)`
  - 反省トリガー: importance 合計 > 150、または peripatos/chashitsu 入室時
- **エラー条件**: 記憶数が上限を超えた場合、最低 strength の記憶を圧縮

### 機能 4: 3D 表現・可視化

Godot 4.4 による 3D レンダリングとダッシュボード。

- **概要**: エージェントの行動を 3D アバターとして可視化し、研究者向けダッシュボードを提供
- **入力**: WebSocket 経由のエージェント状態 JSON
- **出力**: 3D シーン、Memory Stream タイムライン、AgentState パネル、対話ログ
- **振る舞い**:
  - Godot 側: GDScript でシーン更新、スキンメッシュアバターのアニメーション (walking / sitting / bowing)
  - ダッシュボード: Streamlit または FastAPI + HTMX
  - リプレイ: SQLite スナップショットから任意時点を再現

### 機能 5: 評価フレームワーク (4層)

創発現象の定量的評価。

- **概要**: 空間・意味論・儀式・第三者評価の4層で創発を測定
- **層1 (空間的・行動的)**: Ripley K 関数、Lomb-Scargle periodogram、Kuramoto order parameter
- **層2 (意味論的・言語的)**: embedding ドリフト、個体間収束/発散、新語出現率、自己参照ネットワーク密度
- **層3 (儀式の形式的定義)**: 反復性 + 時空間規則性 + 集合性 + 非機能性 の AND 判定
- **層4 (第三者ブラインド評価)**: LLM-as-judge、人間評価者 ICC、ペルソナ固有創発
- **統計設計**: n >= 20 回の独立試行、3段階 ablation、Benjamini-Hochberg FDR 補正、OSF 事前登録

## 3. ユースケース

### UC-1: ゲーム開発者が自律 NPC 村を構築する (最優先)
- **アクター**: インディーゲーム開発者
- **前提条件**: Godot 4 プロジェクトが存在、消費者 GPU (16GB VRAM) を所有
- **トリガー**: 固定スクリプトではなく自律的に文化を築く NPC を実装したい
- **基本フロー**:
  1. ペルソナカード YAML を作成 (既存テンプレートをカスタマイズ)
  2. erre-sandbox を pip install し、FastAPI サーバーを起動
  3. Godot プロジェクトから WebSocket でエージェント状態を受信
  4. NPC が自律的に移動・対話・文化形成を行う
  5. 開発者はダッシュボードで挙動を観察・パラメータ調整
- **代替フロー**: Ursina (Python ネイティブ 3D) で小規模デモ
- **事後条件**: NPC が自律行動し、プレイヤー介入なしで独自の行動パターンを形成

### UC-2: 認知科学研究者が仮説を事前探索する
- **アクター**: 認知科学・社会心理学研究者
- **前提条件**: 介入パラメータ YAML を作成済み
- **トリガー**: 人間被験者実験の前に、非効率パラメータの効果を sandbox 内で因果推論したい
- **基本フロー**:
  1. 介入変数 (歩行頻度・沈黙時間・孤立条件) を YAML で定義
  2. ERRE on/off + ablation 条件で n >= 20 回シミュレーション実行
  3. 4層評価指標を自動算出
  4. 再現可能シードとともに結果を出力
- **事後条件**: 統計的に有意な差が検出された変数を人間実験の仮説として採用

### UC-3: 人文学研究者が史料を計算論的に再構成する
- **アクター**: 哲学史・日本思想史研究者
- **トリガー**: 偉人の認知習慣が対話・関係形成に与える効果を検証したい
- **基本フロー**:
  1. ERRE の Extract/Reverify を実行し、解釈仮説を計算論的に形式化
  2. エージェント行動ログと解釈の反証データを比較
- **事後条件**: 人文学的解釈に対する計算論的反証/支持データが得られる

### UC-4: 教育者が講義で偉人対話を体験させる
- **アクター**: 大学教員・学生
- **トリガー**: 哲学概論の授業でカントやニーチェの思考習慣を体験的に学ばせたい
- **基本フロー**:
  1. HuggingFace Space (CPU 無料枠) の Gradio デモにアクセス
  2. 偉人を選択し、対話を開始
  3. 認知モード (peripatetic/chashitsu) の切り替えを可視化
- **事後条件**: 学生が思考習慣の違いを体験的に理解

## 4. 機能要件

### 必須機能 (MVP)
- 1体のエージェントが歩行ループを実行し、記憶を読み書きし、Godot で描画される (M2)
- 3体のエージェントが対話・反省・関係形成を行う (M4)
  - **M4 実装完了項目** (`schema_version=0.2.0-m4`):
    - foundation primitives (`AgentSpec` / `ReflectionEvent` / `SemanticMemoryRecord` / `Dialog{Initiate,Turn,Close}Msg` / `DialogScheduler` Protocol) 凍結
    - Nietzsche / Rikyu persona YAML (sampling / zone rules で kant との差別化を機械保証)
    - `MemoryStore.upsert_semantic` / `recall_semantic` (sqlite-vec KNN、origin_reflection_id 列)
    - Gateway multi-agent routing (`?subscribe=` per-agent filter、DoS 対策 4 層)
    - Cognition reflection (Reflector collaborator、per-agent tick counter、LLM 要約 → embedding → semantic_memory)
    - Composition Root multi-agent bootstrap (`BootConfig.__post_init__` default、`--personas kant,nietzsche,rikyu` CLI)
    - `InMemoryDialogScheduler` (admission + cooldown + timeout + proximity auto-fire、envelope_sink 一元化)
  - **live 検証** (G-GEAR 必須、別タスク): 3-agent walking 30Hz / reflection persistence / dialog 1 往復 / Godot 描画
- ERRE モード (peripatos/chashitsu/zazen/shu/ha/ri) による認知状態切り替え (M5、計画 merged 2026-04-20 PR #53)
  - **M5 予定項目** (`schema_version=0.3.0-m5`、contract 凍結済み `m5-contracts-freeze`):
    - 静的 `_ZONE_TO_DEFAULT_ERRE_MODE` を event-driven `ERREModeTransitionPolicy` に置換、zone change / fatigue / shuhari を hook (G-GEAR)
    - `DialogTurnGenerator` で `dialog_initiate` 後の N ターンを LLM 生成、`dialog_turn_budget` で自動 close (`reason="exhausted"`) (G-GEAR)
    - Chashitsu / Zazen zone 最小シーン + BaseTerrain 下敷き + ERRE mode tint + Label3D dialog bubble を Godot に追加 **(MacBook 側実装完了: `m5-godot-zone-visuals`, design hybrid 採用)**
    - Contract-First + LLM Spike の hybrid (design: `.steering/20260420-m5-planning/design.md`)
- 5-8体が12時間シミュレーションを破綻なく実行 (M7)
- 4層評価フレームワークの実装と統計レポート出力 (M10-M11)

### オプション機能
- LoRA によるペルソナの永続的個性保持 (M9)
- HuggingFace Space 上の Gradio デモ
- MkDocs Material + mkdocstrings による JA/EN バイリンガルドキュメント

### 将来的な拡張
- MoE 日本語モデルへの移行 (16GB 帯で安定化した段階)
- Adaptive FT / 状態重み焼込み LoRA (v1.0 以降)
- Qdrant + bge-m3 へのベクトル DB スケールアップ
- gRPC 通信 (多言語クライアント必要時)
- Blender 連携 (別パッケージ erre-sandbox-blender/、GPL-3.0)

## 5. 非機能要件

### パフォーマンス
- **推論スループット**: Qwen3-8B Q5_K_M で 30+ tok/s (単体)、8並列時も破綻なし
- **VRAM 使用量**: ~13 GB (8並列 x 4K コンテキスト、RadixAttention で ~30% KV 節約)
- **ティックレート**: ワールド物理 30Hz、エージェント認知 0.1Hz (10秒間隔)
- **シミュレーション持続時間**: 12時間以上を破綻なく実行

### セキュリティ
- **認証方式**: LAN 内通信前提、認証なし (MVP)。外部公開時は FastAPI OAuth2 を追加
- **機密データの扱い**: エージェント状態・対話ログは SQLite ローカルファイルに保存、クラウド送信なし

### 可用性
- **想定稼働環境**: 個人研究用途、24/7 稼働は不要
- **障害復旧**: SQLite スナップショットから任意時点を復元可能

### ユーザビリティ
- **対応デバイス**: G-GEAR (Linux/WSL2) + MacBook Air M4 (macOS)
- **観察者インターフェース**: ブラウザ (Streamlit/HTMX)、Godot 3D ビューア

### ライセンス
- **本体**: Apache-2.0 OR MIT デュアルライセンス
- **Blender 依存**: GPL-3.0-or-later で別パッケージに分離
- **ドキュメント**: CC BY 4.0

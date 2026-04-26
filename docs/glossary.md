# ユビキタス言語定義

このプロジェクトで使用する用語を統一する。同じ概念を異なる言葉で呼ばないこと。
新しい概念を導入する際は必ずここに追加する。

## ドメイン用語

| 用語 (日本語) | 用語 (英語) | 定義 | 使用例 |
|---|---|---|---|
| ERRE フレームワーク | ERRE Framework | 偉人の認知習慣をソフトウェアに翻訳する4段階パイプライン: Extract → Reverify → Reimplement → Express | 「ERRE パイプラインを通してカントの散歩習慣を実装する」 |
| 認知習慣 | Cognitive Habit | 歴史的偉人が繰り返し行っていた思考・行動パターンで、認知神経科学的根拠を持つもの | 「カントの15:30の散歩は認知習慣として抽出される」 |
| 意図的非効率性 | Deliberate Inefficiency | タスク達成の効率を意図的に下げることで、発散的思考や創造性を促進する設計原理。DMN 活性化・productive failure に接続 | 「歩行モードでは意図的非効率性として温度を上げる」 |
| 身体的回帰 | Embodied Return | 抽象的思考から身体的行動 (歩行・座禅・茶) に戻ることで認知を再活性化する設計原理 | 「エージェントは2時間ごとに身体的回帰として peripatos に入る」 |
| 逍遥 / ペリパトス | Peripatos | アリストテレスのペリパトス学派に由来する歩行ゾーン。エージェントが歩きながら発散的思考を行う場所 | 「peripatos ゾーンでは DMN バイアスが高まる」 |
| 茶室 | Chashitsu | 利休の一期一会に由来する収束的思考ゾーン。注意を絞り込み、重要な記憶のみを検索する | 「chashitsu 入室時は温度 -0.2 で収束的生成」 |
| 守破離 | Shu-Ha-Ri | 日本の芸道における3段階のスキル獲得モデル。shu=型の遵守、ha=型からの逸脱、ri=型からの自由 | 「shu 段階では固定スクリプトのみ実行可能」 |
| 一期一会 | Ichigo-Ichie | 茶道の概念。一度きりの出会いとして各インタラクションを扱う。Relationship モデルの `ichigo_ichie_count` で計測 | 「茶室での対話は一期一会としてカウントされる」 |
| 間 | Ma | 日本文化における沈黙・余白の価値。エージェントの `ma_sense` 特性で沈黙への耐性を表現 | 「ma_sense が高いエージェントは対話中の沈黙を長く許容する�� |
| 侘寂 / 侘び | Wabi(-Sabi) | 不完全・簡素・未完成の中に美を見出す日本の美意識。エージェントの `wabi` 特性で不完全性への受容度を表現 | 「wabi が高いエージェントは不完全な解答でも満足する」 |
| 創発 | Emergence | エージェント個体の規則からは予測できない集団レベルの現象 (文化形成・儀式化等) | 「12時間シミュレーションで創発的な集会パターンが観察された」 |
| 儀式 | Ritual | 反復性 + 時空間規則性 + 集合性 + 非機能性 の4条件 AND 判定で操作的に定義される行動パターン | 「エージェントが毎朝同じ場所に集まる行動は儀式の候補」 |
| ペルソナドリフト | Persona Drift | 対話ターン数の増加に伴い、��ージェントの言動が初期設定から乖離する現象。外部 AgentState + 記憶 + LoRA の三重冗長で緩和 | 「50ターン以降のペルソナ一貫性スコアを監視する」 |
| observability-triggered scaling | Observability-triggered Scaling | agent 数を増やす判断を「量先行 (4 体目を入れて困るか見る)」ではなく「観測者の認知資源限界を 3 metric で測り、解析的上限の % を割った瞬間に +1 起票」に置き換える ADR D2 採用方針。M8 spike (`scaling-bottleneck-profiling`) で実装 | 「pair_information_gain が log2(C(N,2)) の 30% を割ったので observability-triggered scaling の trigger が立った」 |

## 技術用語

| ���語 | 英語表記 | 定義 | 関連用語 |
|---|---|---|---|
| AgentState | AgentState | Pydantic v2 で定義されるエージェントの全状態オブジェクト。Biography / Traits / Physical / Emotion / ERREMode / Relationship を含む | schemas.py |
| Memory Stream | Memory Stream | Park et al. (2023) 由来の時系列記憶ストリーム。観察に重要度スコアを付与し、recency + importance + relevance で検索 | sqlite-vec, 反省 |
| 反省 | Reflection | 直近の記憶群から高次の洞察を LLM で生成するプロセス。importance 合計 > 150 または peripatos/chashitsu 入室でトリガー | Memory Stream, Semantic memory |
| CoALA | CoALA | Cognitive Architectures for Language Agents (Sumers et al. 2023)。memory × action × decision procedure の公理系。ERRE-Sandbox の認知アーキテクチャの基盤 | 認知サイクル |
| PIANO | PIANO | Project Sid 由来の5並列認知モジュール: memory, social, goal, action, speech | CoALA, 認知サイクル |
| DMN バイアス | DMN Bias | Default Mode Network に着想を得た発散的思考パラメータ。+1.0 = 最大発散 (idle/peripatetic)、-1.0 = 最大集中 (focused) | ERREMode, 意図的非効率��� |
| RadixAttention | RadixAttention | SGLang の KV キャッシュ共有機構。共有 system prompt + ペルソナカードの prefix KV を再利用し、マルチエージェント推論のスループットを最大化 | SGLang, Inference Layer |
| sqlite-vec | sqlite-vec | SQLite のベクトル検索拡張。単一 .db ファイルで埋め込みベクトルの格納・検索を行う。MIT ライセンス | Memory Layer |
| ControlEnvelope | ControlEnvelope | G-GEAR ↔ MacBook 間の WebSocket 通信で使用する統一メッセージスキーマ。`kind` フィールドでメッセージ種別を識別 | Gateway, FastAPI |
| tick | Tick | シミュレーションの最小時間単位。物理は 30Hz (33ms)、認知は 0.1Hz (10秒) | world/tick.py |
| ゾーン | Zone | ワールド内の5つの空間区分: study (書斎)、peripatos (歩行路)、chashitsu (茶室)、agora (広場)、garden (庭園) | world/zones.py |
| pair_information_gain | Pair Information Gain | 観測者が次の dialog_turn の (speaker, addressee) ペアから得る相互情報量 (bits/turn)。`H(pair) - H(pair | history_k=3)` で計算。値↓ = 観測者が次の pair を予測できる = relational saturation。解析的上限 `log2(C(N,2))` | M8 scaling spike, observability-triggered scaling |
| late_turn_fraction | Late Turn Fraction | dialog_turn のうち turn_index が dialog_turn_budget の半分 (=3) を超えた割合 ∈ [0,1]。値↑ = dialog 後半偏向 = 観測者の注意が turn 序盤で枯れている proxy | M8 scaling spike |
| zone_kl_from_uniform | Zone KL from Uniform | 全 agent の zone 占有時間分布と uniform prior の KL divergence (bits)。値↑ = zone 偏向 = bias 効いている、値↓ = uniform 化 = bias 失効 = scaling trigger。解析的上限 `log2(n_zones)` | M8 scaling spike, observability-triggered scaling |

## 略語

| 略語 | 正式名称 | 意味 |
|---|---|---|
| ERRE | Extract → Reverify → Reimplement → Express | 偉人認知習慣のソフトウェア翻���パイプライン |
| DMN | Default Mode Network | 課題遂行時に代謝が下がる脳ネットワーク。創発的創造性と関連 |
| CoALA | Cognitive Architectures for Language Agents | LLM エージェントの認知アーキテクチャ公理系 |
| PIANO | (Project Sid 由来) | 5並列認知モジュール (memory, social, goal, action, speech) |
| RAG | Retrieval-Augmented Generation | 検索拡張生成。記憶検索 + LLM 生成の組み合わ�� |
| KV | Key-Value | LLM の注意機構におけるキー・バリューキャッシュ |
| VRAM | Video RAM | GPU のメモリ。RTX 5060 Ti は 16GB |
| GGUF | GPT-Generated Unified Format | llama.cpp の量子化モデルフォーマット |
| Q5_K_M | 5-bit K-quant Medium | GGUF の量子化レベル。F16 比 +0.020-0.035 perplexity |
| PD | Public Domain | パブリックドメイン。著作権が消滅したテキスト |
| OSF | Open Science Framework | 研究の事前登録プラットフォーム |
| FDR | False Discovery Rate | 多重比較補正 (Benjamini-Hochberg 法) |
| ICC | Intraclass Correlation Coefficient | 評価者間信頼性の指標 |
| MVP | Minimum Viable Product | 最小実行可能製品 |

## 禁止用語

混乱を招くため使用しない用語と、代わりに使うべき用語。

| 禁止 | 代替 | 理由 |
|---|---|---|
| AI キャラクター | エージェント (Agent) | 本プロジェクトのエージェントは認知アーキテクチャを持つ自律存在であり、「キャラクター」は受動的な印象を与える |
| NPC | エージェント (Agent) | ゲーム開発向けドキュメントで���NPCと対比して説明するが、本体のコード・ドキュメントでは「エージェント」を使用 |
| ボット | エージェント (Agent) | 同上 |
| チャットボット | エージェント (Agent) | 対話は認知サイクルの一部であり、チャットが主目的ではない |
| デ���タベース (曖昧) | sqlite-vec / Memory Layer / erre.db | 具体的にどの DB を指すか明示する |
| AI モデル (曖昧) | ベースモデル / LLM / Qwen3-8B 等の具体名 | どのモデルを指���か明示する |
| サー��ー (曖昧) | G-GEAR / SGLang server / FastAPI server | どのサーバーを指すか明示する |
| 効率的 | (文脈に応じて具体化) | 本プロジェクトは「意図的非効率性」を設計原理とするため、「効率的」を無批判に肯定語として使わない |

## 用語の追加・変更ルール

1. 新しい概念を導入する際は、まずここに追加してから実装する
2. コード内の変数名・クラス名はこの用語集の英語表記と一致させる
3. 既存用語の意味を変える場合は、変更履歴をコミットメッセージに残す
4. 論文引用に基づく用語には出典 (著者名 + 年) を定義に含める

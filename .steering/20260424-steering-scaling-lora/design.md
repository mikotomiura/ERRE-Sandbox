# Design — L6 ADR Roadmap (v2, post-reimagine)

> 本ファイルは /reimagine で v1 (`design-v1.md`) を退避したあと、
> requirement.md のみに立脚してゼロから再生成した案。
> v1 との比較は `design-comparison.md` を参照。

## 立脚点 — requirement.md の再読で拾った制約

1. ADR の目的は **M8+ の意思決定材料** (req.md 線 23)。現時点で architecture を確定することではない。
2. 構成: `decisions.md` = 3 ADR (各 ≤20 行、5 節)、`design.md` = **関連する調査結果** (req.md 線 23-24)。
3. 運用予算節は **書かない** (既記載 DRY、req.md 線 35-37)。
4. 各 ADR に **M8+ task の preconditions** が明示 (req.md 線 44)。
5. コード差分ゼロ (req.md 線 45)。

## v1 が見逃していた論点 (ゼロ生成で浮上)

- **design.md の役割誤認**: v1 は design.md を「ADR の書き方メタ」(50 行) に使っていた。requirement は「調査結果を書き下ろす」と明記しており、design.md は **substantive research repository** であるべき。
- **ADR の時制誤認**: v1 は "M8 で (c) hybrid LoRA 試作" のように *architecture を先取り commit* する採用を書いていた。M8+ の材料が目的なら、ADR は「先取り commit」ではなく「何を観測/測定したら commit 可能になるか」を書くべき。
- **選択肢の貧困**: v1 の (a)/(b)/(c) は tasklist.md の先入観を継承。ゼロ生成で (d)(e)(f) が複数見つかった (§3 参照)。
- **ADR 2 と ADR 3 の交叉**: "4th agent 追加" と "user を agent として扱う" は実質的に同じ interface の違う呼び名。v1 は両方を独立に書いていたが、v2 は交叉を明示して preconditions を共有化する。
- **User-IF の方法論的緊張**: v1 は interface 選定問題として扱ったが、本質は「自律創発を観察する研究姿勢と、実験者介入の矛盾」。ADR 3 は interface ではなく **方法論の位置付け** を決めるべき。

## §1 — 現状スナップショット (substantive facts)

### 推論スタック
- Base model: `qwen3:8b` (`src/erre_sandbox/inference/ollama_adapter.py:37`)。`llm-inference` Skill の想定 `qwen3:8b-q5_K_M` は Ollama registry に無かったため fallback (`.steering/20260418-model-pull-g-gear/decisions.md` D1 の経緯)。
- VRAM: ~13GB / 16GB on RTX 5060 Ti (`.claude/skills/llm-inference/SKILL.md` L68-76)。内訳: 重み 5.5GB + KV 5-6GB + CUDA 2GB。
- `OLLAMA_NUM_PARALLEL=4` (同 Skill L45) が並列推論の上限。N=4 agent まではキュー待ち無し、N≥5 で逐次化。
- LoRA 関連コードは 0 件 (grep 済)。M9 roadmap 行 (`.steering/20260418-implementation-plan/MASTER-PLAN.md:146`) に "vLLM + LoRA per persona、M4-M7 の ≥1000 turns/persona 対話ログで訓練" とのみ。

### Persona 分化機構
- YAML: `personas/kant.yaml` 等が Big Five + wabi/ma_sense + cognitive_habits + default_sampling を保持 (`persona-erre` Skill L28-62)。
- Prompt 合成: `cognition/prompting.py:65-89` が persona YAML + AgentState を system prompt に射影。RadixAttention 共有 prefix 最適化 (同 Skill L137-139)。
- ERRE mode サンプリングオーバーライド: 8 mode × (temp/top_p/repeat_penalty) で加算値を適用 (同 Skill L90-99)。

### Agent 数の制約
- ハードコード境界: `src/erre_sandbox/integration/dialog.py:113` コメント "M4 targets N≤3"。
- Dialog pair 列挙: `_iter_colocated_pairs` (`dialog.py:292-305`) は O(N²) で、同一 zone 内の agent 全対を (stable 順) 返す。N=3 → 3 pair、N=4 → 6 pair、N=5 → 10 pair。
- Tick 並列: `world/tick.py:668, 771` で `asyncio.gather(return_exceptions=True)`。semaphore なし。
- Dialog turn 予算: `Cognitive.dialog_turn_budget` (`schemas.py:360`)、`DialogTurnMsg.turn_index` (`schemas.py:795`)、M5 から dialog_close reason に "exhausted" あり (`schemas.py:855`)。

### WS/UI 層
- ControlEnvelope 11 variants (`schemas.py:858-871`): handshake / agent_update / speech / move / animation / world_tick / error / dialog_initiate / dialog_turn / reasoning_trace / reflection_event。
- user→agent 逆方向 channel は **存在しない** (全 11 variants が G-GEAR → MacBook の一方向 broadcast)。
- MIND_PEEK = `godot_project/scripts/ReasoningPanel.gd:1-6` (observability パネル、receive のみ)。
- DialogBubble = `godot_project/scripts/agents/DialogBubble.gd:14-57` (agent 発話の 3D ラベル、receive のみ)。

## §2 — 3 軸の選択肢 taxonomy (ゼロ生成で拡張)

### Axis 1 — LoRA による persona 分化

| ID | 選択肢 | 評価 |
|---|---|---|
| A1-a | prompt injection のみ維持 | 現状。RadixAttention で KV 共有し CPU/GPU コスト最小 |
| A1-b | persona ごとに LoRA adapter | M9 roadmap 済。1000 turns/persona の log が前提 |
| A1-c | 混合 (一部 persona のみ LoRA) | 非対称性が dialog scheduler と混乱。経年で不均衡が拡大 |
| A1-d | 継続事前学習 (全 persona まとめて 1 モデル微調整) | persona 分化は prompt に戻る、LoRA と排他ではない |
| A1-e | RAG (episodic memory から in-context 例示) | LoRA 不要、schema 変更最小、品質測定容易 |
| A1-f | instruction-tune (role-play fidelity 向上ベース) | LoRA の前段前処理、単独では分化効果が弱い |

**ゼロ生成の直感**: M8 の時点で A1-a/b/c/d/e/f のどれを採用するかは **データが無いと判断できない**。現 MVP は ~20 turns/persona で、M4-M7 live 終了時点でも不十分な可能性。ADR の役割は「M8 で計測すべき things」を列挙すること、architecture を先取りしないこと。

### Axis 2 — Agent scaling

| ID | 選択肢 | 評価 |
|---|---|---|
| A2-a | 4th persona 追加 (補完的人物) | pair は 3→6 に倍増、観察負荷も増 |
| A2-b | 3 のまま、session を長くして深掘り | 関係性の成熟度を縦に観察 |
| A2-c | 同 persona 複数インスタンス | 個体差検証、目的 (異質相互作用) から外れる |
| A2-d | 2 persona-set を切替 (古代 3 + 近代 3) | 実験デザインの variable、科学的 |
| A2-e | 1 入替 (現 3 から 1 人差替) | contrastive 強化、pair 総数不変 |
| A2-f | user/researcher を 4 体目として扱う | **Axis 3 と交叉**。interface 重複の疑い |

**ゼロ生成の直感**: 「N を増やすか」は誤った問い。正しい問いは「**何を観測したら scaling が研究目的に資すると判定できるか**」。現状 3 agent で観測可能性が頭打ちと判明してから scaling すべき。metric first、quantity last。

### Axis 3 — User-dialogue IF

| ID | 選択肢 | 評価 |
|---|---|---|
| A3-a | Godot text input → DialogTurnMsg + "user" agent | 既存 schema 最大利用、ただし user が常時観察 loop に混入 → 自律創発の観察が汚染 |
| A3-b | MIND_PEEK 経由 prompt injection | 不可視介入、再現性低下、debug 用に限定すべき |
| A3-c | 別 WS channel | schema 増殖、DRY 違反 |
| A3-d | 2-phase methodology: 自律 run と user-Q&A epoch を時間分離 | 観察純度を保ち、Q&A は post-run review として記録 |
| A3-e | 研究者 dashboard の pause-and-query mode | run 中の一時停止 + 質問、再開。科学的 but UI が重い |
| A3-f | post-M10 evaluation layer に繰越、M8 では書かない | 最小工数、"M8+ 材料" の役割を逸脱 |

**ゼロ生成の直感**: 本当の decision axis は **interface** ではなく **方法論の位置付け** — user interaction が "runtime observation" か "post-hoc evaluation" か。A3-d (2-phase) が研究姿勢と両立し、かつ既存 ControlEnvelope を session_phase flag で拡張するだけで済む。interface design は M8 で autonomous_run_complete イベントの後に Q&A epoch を起こす設計として詰める。

## §3 — M8 の共通 preconditions (3 ADR 共通)

3 軸は独立に見えて、M8 spike で共通して必要なものがある:

1. **Episodic log 吸い上げ pipeline** — LoRA 訓練 (A1) にも、scaling 判定 metric (A2) にも、Q&A epoch の ground truth (A3) にも必要。
2. **Baseline quality metric** — prompt-only での会話 fidelity、bias 発火頻度、affinity 推移曲線。A1 の LoRA 後比較基準、A2 の scaling トリガー判定基準。
3. **Session phase model** — autonomous / q-and-a / evaluation の 3 相を明示的に state として持つ。A3 の前提、A2 のスクリプト化観察にも使える。

v2 の design.md はこの "共通 preconditions" を明示する。ADR は各軸の決定を書くが、**3 ADR 末尾の「次アクション」で同じ 3 件を cross-reference する**ことで M8 task の起票粒度を「1 spike = 3 preconditions 同時達成」に収束させる。

## §4 — 方法論的緊張 (Axis 3 専用)

ERRE-Sandbox の研究姿勢は「偉人ペルソナの自律的認知習慣から社会創発を観察する」。user interaction は定義上 **介入** であり、autonomous claim と矛盾しうる。

緩和策: A3-d (2-phase) を採用し、autonomous run の内部に user 発話を混入させない。run 終了後の別 epoch で Q&A を記録。これにより:
- autonomous log: 介入なし、統計的主張の根拠
- Q&A log: 解釈補助、ペルソナ一貫性の post-hoc verification

この分離は M10-11 evaluation layer 設計とも整合 (MASTER-PLAN.md L146 付近の 4-layer eval と自然に接続)。

## §5 — MASTER-PLAN 更新提案

現状 M7 行と M9 行の間が空白。M8 を次のように追記:

```
| **M8** | 観察 → LoRA 判断の橋渡し spike | 
    `m8-episodic-log-pipeline`, `m8-baseline-quality-metric`, 
    `m8-session-phase-model`, `m8-scaling-bottleneck-profiling` | 
    L6 ADR 1/2/3 の preconditions を同時解決、M9 着手の go/no-go 判定材料 |
```

M9 行 (line ~146) には追記: "前提: L6 ADR1 の defer-and-measure 方針、M8 の baseline quality data".

## §6 — 実行フロー (v2)

### Step 0 — Skill 再確認
- `llm-inference` / `persona-erre` / `architecture-rules` を最新で Read
- `src/erre_sandbox/inference/ollama_adapter.py:37` で base model 名を再確認

### Step 1 — design.md (this file) を finalize
- §1-§5 は上記のまま、実行中に判明する新事実があれば追記

### Step 2 — decisions.md に 3 ADR を書く

**書式**: 5 節固定 (現状 / 選択肢 / 採用 / 根拠 / 次アクション)、各 ≤20 行。evidence は全て design.md の §1-§4 を参照。

**ADR 1 — LoRA による persona 分化 (defer-and-measure)**
- 現状: qwen3:8b + prompt injection、LoRA コード 0 件、M9 前提 ≥1000 turns/persona 未達
- 選択肢: A1-a/b/c/d/e/f (design.md §2 Axis 1 参照)
- 採用: **architecture 確定は M9 まで defer、M8 では baseline 計測と episodic log pipeline 整備のみ**
- 根拠: 現 MVP データ量不足、A1-b/c/d/e の比較は baseline 無しでは判断不能。A1-a を暫定継続するコスト小 (RadixAttention 効率)
- 次アクション: M8 spike `m8-episodic-log-pipeline` + `m8-baseline-quality-metric` を起票、M9 着手前に A1-a/b/c/d/e の比較評価を実施

**ADR 2 — Agent scaling (observability-triggered)**
- 現状: 3 agent hardcoded (dialog.py:113)、pair C(N,2) 爆発、N>4 で Ollama 逐次化 (OLLAMA_NUM_PARALLEL=4)
- 選択肢: A2-a/b/c/d/e/f (design.md §2 Axis 2 参照)
- 採用: **3 維持 + scaling トリガー metric の定義**、metric 閾値超過が観測されたら +1 (補完人物を contrastive 選定)
- 根拠: 量を先行させる理由がない。観察可能性の頭打ち (dialog pair saturation、observer fatigue、zone 滞留分布の flat 化等) が科学的トリガー。VRAM は N=4 まで余裕 (16-13=3GB)、bottleneck は Ollama 並列上限
- 次アクション: `m8-scaling-bottleneck-profiling` で metric 候補を 3 本提案、各閾値を live data で確定、超過確認後 M9 で +1 persona 候補リスト起票

**ADR 3 — User-dialogue IF (two-phase methodology)**
- 現状: ControlEnvelope 11 variants、user→agent channel 無し、MIND_PEEK/DialogBubble は観察専用
- 選択肢: A3-a/b/c/d/e/f (design.md §2 Axis 3 参照)
- 採用: **A3-d (2-phase methodology): autonomous run と user-Q&A epoch を session_phase flag で時間分離**、interface は Q&A epoch 内で既存 DialogTurnMsg 再利用
- 根拠: autonomous claim の汚染を回避 (design.md §4)、既存 schema 増殖せず session_phase の 1 フィールド追加のみ、M10-11 evaluation layer 設計と接続
- 次アクション: `m8-session-phase-model` で session_phase enum と epoch 遷移 API を設計、Q&A epoch 中の user 発話記録仕様を別 decisions に切り出す

### Step 3 — MASTER-PLAN.md 編集
- M8 行追加 (§5 のテンプレ通り)
- M9 行に前提追記

### Step 4 — Review + PR
- branch diff docs-only 確認 (`git diff --stat` が .md のみ)
- tasklist.md の暫定採用 (c/a/a) を v2 採用 (defer/observability/2-phase) に **修正**
- tasklist.md L14 の "gpt-oss:20b MoE" を `qwen3:8b` に修正
- `gh pr create`、title `docs(steering): L6 — scaling / LoRA / user-dialogue IF roadmap`
- body: v2 採用の骨子を 3 行で要約、design.md と decisions.md への link、親 D2 への Ref

## §7 — 変更対象ファイル一覧 (v2)

| Path | 変更種別 | 想定規模 |
|---|---|---|
| `.steering/20260424-steering-scaling-lora/design.md` | 本ファイル (v2 新規) | ~200 行 |
| `.steering/20260424-steering-scaling-lora/design-v1.md` | v1 退避 (完成済) | ~200 行 |
| `.steering/20260424-steering-scaling-lora/design-comparison.md` | 比較記録 (/reimagine Step 4) | ~50 行 |
| `.steering/20260424-steering-scaling-lora/decisions.md` | 新規 (3 ADR) | ~60 行 |
| `.steering/20260424-steering-scaling-lora/tasklist.md` | 既存編集 (採用の暫定→確定、base model 名修正) | 2-3 行差分 |
| `.steering/20260418-implementation-plan/MASTER-PLAN.md` | 既存編集 (M8 行追加、M9 前提追記) | ~6 行差分 |

## §8 — 検証

- `wc -l .steering/20260424-steering-scaling-lora/decisions.md` → 3 ADR × ≤20 行 + header で ~70-90 行
- 各 ADR が 5 節 (現状 / 選択肢 / 採用 / 根拠 / 次アクション) を持つ
- 各 ADR の「次アクション」が `m8-*` task 名を列挙 (M8 spike 起票の粒度)
- `git diff --stat origin/main...HEAD` が `.md` 拡張子のみ
- `grep -E '(llm-inference|persona-erre|architecture-rules)' decisions.md design.md` で 3 Skill 参照が残る

## §9 — Out of Scope (v2 でも維持)

- コード変更 (親 D2 制約)
- 運用予算節 (CLAUDE.md + architecture-rules 既記、DRY)
- M8 spike task そのものの起票 (preconditions 記述のみ、spike は次セッション)
- Slice γ / live-acceptance (別 task dir)

## 設計判断の履歴

- 初回案 (design-v1.md) と再生成案 (v2、本ファイル) を `design-comparison.md` で比較
- 採用: **v2**
- 根拠:
  - requirement.md 線 23-24 の明文指示 (design.md に調査結果を書き下ろす) に v1 は違反、v2 は準拠
  - ADR の目的が「M8+ 意思決定材料」なら、architecture 先取り commit は逆機能
  - 選択肢 taxonomy の (a-f) 拡張により将来データで覆される可能性が v1 の (a/b/c) より低い
  - ADR 2-3 交叉の明示が M8 spike 起票時の一本化効果を生む
- v1 と v2 の選択: /reimagine Step 5 の AskUserQuestion にて 2026-04-24 に確定

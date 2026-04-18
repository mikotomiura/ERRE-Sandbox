# 重要な設計判断

## 判断 1: 契約駆動 (Contract-First) を採用し、素直な時系列積み上げを破棄

- **判断日時**: 2026-04-18
- **背景**: 2 拠点 (G-GEAR / MacBook Air M4) で MVP を構築するにあたり、
  素直に時系列で積み上げると MacBook が前半ずっとアイドルになる上、
  `ControlEnvelope` 仕様を固めないまま両機が独立実装し末期に大幅手戻りする
  致命リスクがあった
- **選択肢**:
  - A: 素直な積み上げ (G-GEAR を完成させてから MacBook を着工)
  - B: 契約駆動 (schemas.py と JSON fixture を最初の 3 日で凍結、以降並列)
  - C: ハイブリッド (Contract 凍結を 1 日で強行、並列度をさらに上げる)
- **採用**: **B (契約駆動)**
- **理由**:
  - 2 拠点並列化で実働 10 日 (A なら 15-18 日相当)
  - ControlEnvelope 仕様ズレを構造的に防止、後半の手戻りゼロ
  - テストインフラ (tests/fixtures/) が Phase C で自然に構築される
- **トレードオフ**:
  - Contract 凍結中 (T05-T08) は MacBook 単独作業となり G-GEAR はモデル pull
    以外の人手作業が進まない
  - `personas/kant.yaml` の最小フィールドを Phase C で可視化する追加工数
- **影響範囲**: T05-T08 の工程順序、両機の作業分担ルール
- **見直しタイミング**: M4 着手前、Contract のスコープを見直す時

## 判断 2: MacBook Air M4 をマスター機とする

- **判断日時**: 2026-04-18
- **背景**: 2 拠点で Claude Code セッションが同時稼働した場合に、
  `.steering/` の編集競合や `/start-task` の起動場所が曖昧になるリスク
- **選択肢**:
  - A: G-GEAR マスター (LLM 推論の中心だから)
  - B: MacBook マスター (Claude Code CLI + Godot + PDF 閲覧)
  - C: 相互対等 (両方で自由に起動)
- **採用**: **B (MacBook マスター)**
- **理由**:
  - Claude Code CLI・Godot 編集・PDF 閲覧の GUI ワークフローが MacBook に集中
  - `.steering/_setup-progress.md` など共有ファイルの単独編集者を固定できる
  - G-GEAR は WSL2 の場合 GUI が弱く、Godot 編集には向かない
- **トレードオフ**:
  - 推論・記憶・認知系タスクは G-GEAR で `/start-task` する必要があり、
    起動場所のルール分離を覚えておく必要がある
- **影響範囲**: `/start-task` の起動先、Git ブランチ運用、`.steering/` 編集ルール
- **見直しタイミング**: G-GEAR が Linux デスクトップ GUI 付きになる、または
  remote 開発 (VS Code Remote) を導入する時

## 判断 3: PDF は pdftotext 化したテキストを主参照とする

- **判断日時**: 2026-04-18
- **背景**: `ERRE-Sandbox_v0.2.pdf` (21p) は `.gitignore` 対象だが
  プロジェクトルートに存在。Claude Code の Read ツールで直接扱える (pages
  パラメータ) が、context を大量消費する。一方 docs/ 5 ファイルは既に PDF
  の内容を分解反映済み
- **選択肢**:
  - A: PDF を直接 Read ツールで都度読む (poppler 不要)
  - B: MacBook に poppler を入れて `docs/_pdf_derived/erre-sandbox-v0.2.txt`
    を生成し、以後はテキストを参照
  - C: PDF 参照を完全に禁止し、docs/*.md のみを正とする
- **採用**: **B (pdftotext 化 + docs/*.md を日常の正)**
- **理由**:
  - docs/*.md を日常の正とすることで、設計判断の中央集約を維持
  - PDF 原文の確認が必要になった場合、テキスト版で章単位検索が効率的
  - 画像・図表が必要な場面では A (Read ツール pages) に切替可能
- **トレードオフ**:
  - MacBook に poppler をインストールする追加工数
  - `_pdf_derived/` と docs/*.md の差分を定期的に検知する必要
    (M2・M5 完了後にドリフト検知タスクを実施)
- **影響範囲**: T03 (pdf-extract-baseline)、PDF 参照ワークフロー全般
- **見直しタイミング**: docs/*.md と PDF のドリフトが頻発、または PDF が
  v0.3 以降に更新された時

## 判断 4: MVP のモデルを Qwen2.5-7B-Instruct Q5_K_M に仮決定

- **判断日時**: 2026-04-18
- **背景**: docs/architecture.md は「Qwen3-8B または Llama-3.1-Swallow-8B
  (Q5_K_M)」と明記。Qwen3 は 2026-04 時点で Ollama public registry に
  未登場のため、Qwen2.5 系で代替する
- **選択肢**:
  - A: Qwen2.5-7B-Instruct Q5_K_M (Ollama 公式、即 pull 可能)
  - B: Llama-3.1-Swallow-8B-Instruct-v0.3 Q5_K_M (HF GGUF → `ollama create`、手間あり)
  - C: Qwen3-8B (登場まで待機)
- **採用**: **A (Qwen2.5-7B-Instruct Q5_K_M)**
- **理由**:
  - Ollama 公式 registry から即 pull 可能
  - M1 末に VRAM 実測して B に切替する余地を残す
- **トレードオフ**:
  - Qwen3 のリリース後、パフォーマンス比較と切替判断が必要
  - Swallow 系の日本語強度を当面諦める
- **影響範囲**: T09 (model-pull-g-gear)、T11 (inference-ollama-adapter)
- **見直しタイミング**: M1 VRAM 実測時、Qwen3-8B の Ollama 登場時、
  日本語ペルソナのドリフトが顕著に出た時

## 判断 5: SGLang への移行を M7 以降に遅延

- **判断日時**: 2026-04-18
- **背景**: docs/architecture.md は「SGLang (本番) / Ollama (開発)」と明記。
  MVP (1 体) では RadixAttention の恩恵が小さい
- **選択肢**:
  - A: MVP から SGLang で構築 (最初から本番構成)
  - B: MVP は Ollama、M7 (5-8 体長時間) で SGLang に切替
  - C: 両方サポートし、環境変数で切替
- **採用**: **B (M7 で切替)**
- **理由**:
  - Ollama は開発時の簡便性が高く、MVP の検証コストが低い
  - SGLang の真価はマルチエージェント (8-10 体) でこそ発揮される
  - error-handling Skill の SGLang → Ollama フォールバックをそのまま活用
- **トレードオフ**: M7 で inference 層のリファクタが必要 (ただし adapter パターンで
  吸収可能)
- **影響範囲**: T11, M7 の `inference-sglang-migration` タスク
- **見直しタイミング**: M4 完了時 (3 体で Ollama 並列が破綻し始めたら前倒し)

## 判断 6: CSDG を参照資産として採用 (パターン移植方式)

- **判断日時**: 2026-04-18
- **背景**: 作者 (mikotomiura) が先行で作成した
  `github.com/mikotomiura/cognitive-state-diary-generator` (CSDG, MIT)
  が ERRE 思想と「意図的非効率」を既に実装済み。Pydantic v2 スキーマ
  (HumanCondition / CharacterState)、半数式状態遷移、3 層 Critic、
  2 層メモリなど ERRE-Sandbox と共通のロジックを備えている
- **選択肢**:
  - A: CSDG を Git サブモジュール / PyPI 依存として直接取り込む
  - B: パターン・式・ロジックを参考にリライトする (パターン移植)
  - C: CSDG を無視してゼロから実装
- **採用**: **B (パターン移植)**
- **理由**:
  - CSDG はクラウド LLM 前提 (Anthropic Claude / Google Gemini)、
    ERRE-Sandbox は予算ゼロ・ローカル推論必須 → A は不可
  - CSDG は単一キャラクター (三浦とこみ)、ERRE-Sandbox は複数ペルソナ並列
    (RadixAttention で prefix KV 共有) → API が根本的に異なる
  - CSDG の Express は日記テキスト、ERRE-Sandbox は 3D 可視化 (Godot)
    → 出力層が全く別物
  - しかし schemas / 状態遷移式 / Critic 評価 / 2 層メモリは共通ロジックが多く、
    C (ゼロ実装) は車輪の再発明で無駄
- **トレードオフ**:
  - CSDG のバグ修正やアップデートを自動追従できない
  - 逆に ERRE-Sandbox の独自要件 (複数ペルソナ・10 秒 tick・3D) に合わせて
    拡張する自由度は高い
- **影響範囲**: T05, T06, T10, T11, T12, M4 (reflection), M10-11 (評価)
- **見直しタイミング**: CSDG が大幅アップデートされ共通インフラ化の価値が出た場合 /
  ERRE-Sandbox 固有要件が増えて CSDG 参照の価値が薄れた場合

### 判断 6 の具体的な適用先

詳細は `MASTER-PLAN.md §付録 B` を参照。主な引き継ぎ:

- **式**: `base = prev * (1 - decay_rate) + event_impact * event_weight` (T12)
- **式**: Critic 合成 `L1*0.40 + L2*0.35 + L3*0.25` (M10-11)
- **構造**: `HumanCondition` 5 フィールド → `AgentState.Physical` (T05)
- **構造**: 2 層メモリ (ShortTerm window=3 + LongTerm beliefs≤10/themes≤5) (T10)
- **パターン**: evict→LLM extract による信念・テーマ蒸留 (M4)
- **パターン**: Veto 機構 + revision_instruction 二重注入 (M10-11)

# 認知深化 7-point 提案 - 妥当性判定 + phasing 設計

- **作成日**: 2026-05-08
- **状態**: 評価中 (G-GEAR run1 calibration 走行中、本タスクは触らない)
- **依頼者**: johnd / mikotomiura

## 背景

G-GEAR で M9-eval Phase 2 run1 calibration (kant 1 cell × 5 wall = 30h overnight×2) を
収集中。並行して、ユーザーが ERRE の認知層深化の 7 点提案を立案した。
提案は単なる schema 追加ではなく **「固定 persona の role-play」から「seed → 発達する
認知エンティティ」への思想転換** を含むため、M9-B LoRA / M9-eval / 既存の belief 系統 /
shuhari と複数の前提を変える可能性がある。

CLAUDE.md の規約 (architecture / 公開 API / 複数案ありうる設計) より、Plan mode 相当
の評価 + /reimagine + Codex independent review の 3 関門で判定する。

## 提案 (verbatim)

1. SubjectiveWorldModel schema 追加
2. prompt に subjective beliefs を注入
3. LLMPlan に world_model_update を追加
4. Python 側で安全に merge
5. NarrativeSelf を semantic memory から周期生成
6. DevelopmentState を導入
7. 偉人 persona を philosopher_seed にリファクタ

## 提案者からの structural 明確化 (2026-05-08 follow-up、判定の前提変更)

ユーザーから 3 点の補足が入った:

1. **「agent 自体に世界モデルを導入する」**
   → 提案 1 は memory layer ではなく **`AgentState` 第一級 property** として配置せよ
2. **「思想家自体のペルソナを導入するのではなく、それをベースとして置くだけにしておき、
   性格やペルソナは新しい個人にする」**
   → 提案 7 は「philosopher を捨てる」ではなく **二層分離**:
   - `philosopher_base` (継承、immutable、cognitive_habits + sampling、M9-B LoRA target)
   - `individual` (mutable、新規個体、personality + beliefs + narrative + development)
3. **「途中途中から成長していく過程を導入し、完全に人間として構築」**
   → 提案 5, 6 は **完全な developmental trajectory** を意図 (lifecycle 段階を持つ)

この明確化で 7 提案は「個別 schema 追加の集合」ではなく **二層アーキテクチャへの統一的
転換** に再解釈される。Claude 単独判定 (特に 6, 7) は反転する可能性が高い。

### 新しい architectural 解釈

```
agent = philosopher_base + individual

  philosopher_base (immutable inheritance):
    - cognitive_habits (Kant の歩行/執筆ルーチン等)
    - sampling param (temperature/top_p/repeat_penalty)
    - LoRA-trained 文体 (M9-B target)

  individual (mutable, per-agent, ここに 7 提案が住む):
    - SubjectiveWorldModel (= 1, AgentState 第一級 property)
    - subjective beliefs (env/concept/self/norm 注入 = 2)
    - bounded world_model_update (= 3 修正版)
    - safe-merge layer (= 4)
    - NarrativeSelf 周期蒸留 (= 5)
    - DevelopmentState lifecycle (= 6, individual 側にあるので shuhari と直交)
    - "新しい個人" としての存在 (= 7 の本意)
```

### M9 trunk への影響 (再評価)

二層分離なら M9 trunk は **無傷** で進められる:
- M9-B LoRA は `philosopher_base` の Kant 文体を学習 (現設計不変)
- M9-eval Burrows ratio は **base 保持 + 個体ばらつき** の分解測定ツール化
  (個体化が観測されれば creative emergence の direct evidence)
- Phase 2 baseline は invalidate されず、個体化計測の reference point になる

### 残る HIGH-stakes な未決問題

- 「完全に人間として」の **operational definition** が未定義 — scope 無限化リスク
  - discrete stages 何段?(3? 5? 10?)
  - 各段の cognitive 特性差を何で実装?(sampling? memory window? prompt 構造?)
  - 段間遷移 trigger: memory volume? narrative coherence? belief stability?
  - "完成" は何で判定?(あるいは死/置換が要るか?)
- `philosopher_base` と `individual` の **inheritance contract**: base の cognitive_habits は
  immutable か、individual が override 可能か? どこまで継承し、どこから個別化するか?
- LoRA adapter は **base layer 専用** か、それとも個体差も学習対象か?
  (後者なら M9-B 設計に影響)

## 哲学的位置づけ

ERRE プロジェクトの thesis (functional-design.md §1) は次の二項を含む:

- "歴史的偉人の **認知習慣** をローカル LLM エージェントとして再実装"
- "意図的非効率性と身体的回帰による **知的創発** を観察"

両者は緊張関係にある。前者は「再現」(static endpoint)、後者は「創発」(dynamic process)。
本 7-point 提案は明示的に後者の極へ重心を寄せるリファクタ案であり、project thesis の
解釈そのものを問う設計判断になる。

## 受け入れ条件 (この判定タスクの)

- 7 提案それぞれを ADOPT / MODIFY / DEFER / REJECT で判定する
- 各判定に **既存コードへの影響** + **M9-B LoRA / M9-eval への影響** + **代替案有無**
  の 3 軸で根拠を付ける
- ADOPT/MODIFY と判定したものについて、phasing (M9 内 / M10 / M11+) を割当てる
- 全体として M9 完了までブロックしない実行順序を提示する
- Codex independent review HIGH を全件反映、MEDIUM は採否を decisions.md に記録

## 既存資産との衝突点 (initial scan)

| 提案 | 既存コード | 衝突種別 |
|---|---|---|
| 1 SubjectiveWorldModel | `SemanticMemoryRecord.belief_kind` (M7δ) | 同一 axis 重複の可能性、統合設計必須 |
| 2 prompt injection | `_COMMON_PREFIX` (RadixAttention KV cache 前提) | prompt 構造変更が SGLang cache 戦略に波及 |
| 3 LLMPlan world_model_update | `cognition/parse.py:46` `LLMPlan(extra="forbid", frozen=True)` | schema versioning 必須、parse path への影響 |
| 4 safe merge | `cognition/belief.py` `maybe_promote_belief()` | 既存の threshold-based promote と同型 pattern、流用可 |
| 5 NarrativeSelf 周期生成 | M4 chashitsu reflection / semantic memory promote | reflection trigger と timing 衝突の可能性 |
| 6 DevelopmentState | `AgentState.Cognitive.shuhari_stage` (shu/ha/ri) | 直接重複、関係を明示しないと 2 系統並立 |
| 7 philosopher_seed | `personas/*.yaml` schema_version 0.10.0-m7h、 M9-B LoRA Kant target、M9-eval Burrows 固定 style 前提 | M9 trunk 全体の前提を変える、最大リスク |

## 非範囲 (この判定タスクで触らない)

- G-GEAR の run1 calibration 走行 (別軸、ME-9 ADR で running)
- M9-eval CLI 改修 (PR #140 で完了)
- M9-B LoRA execution 着手 (PR #127 計画は確定済、ただし提案 7 採用なら見直し)
- 実装着手 (本タスクは判定 + 設計のみ、実装は phasing 配下の後続タスクで)

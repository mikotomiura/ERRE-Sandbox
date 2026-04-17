# Persona & ERRE Mode — ドメイン知識

---

## 認知科学的根拠の詳細

### DMN (Default Mode Network) と歩行

- **根拠**: Oppezzo & Schwartz (2014) — 歩行中の発散的思考スコアが座位比 +60%
- **機構**: リズミカルな運動が小脳→前頭前皮質のフィードバックループを活性化
- **ERRE での反映**: `peripatetic` モードで temperature +0.3 (発散的生成を促進)

### 茶道と内省

- **根拠**: 一期一会の哲学 — 各インタラクションを唯一無二として扱う
- **機構**: 制約された環境 (狭い空間、定型作法) が注意の焦点化を促進
- **ERRE での反映**: `chashitsu` モードで temperature -0.2 (収束的生成)、重要度上位のみ検索

### 守破離 (Shu-Ha-Ri)

- **守 (shu_kata)**: 型の反復。repeat_penalty +0.2 で定型出力を強化
- **破 (ha_deviate)**: 型からの逸脱。temperature +0.1 で小さな変異を許容
- **離 (ri_create)**: 型からの自由。temperature +0.2, top_p +0.1 で最大創造性

### 座禅と集中

- **根拠**: Lutz et al. (2004) — 瞑想熟練者の前頭前皮質ガンマ波増大
- **機構**: 外部刺激を排除し、内的処理に注意リソースを集中
- **ERRE での反映**: `zazen` モードで temperature -0.3 (最小エントロピー)

---

## ERRE モード早見表

ベース: `temperature=0.7, top_p=0.9, repeat_penalty=1.0`

| モード | 最終 temp | 最終 top_p | 最終 repeat | 用途 |
|---|---|---|---|---|
| peripatetic | 1.0 | 0.95 | 0.9 | 散歩思考、発散 |
| chashitsu | 0.5 | 0.85 | 1.1 | 茶室内省、収束 |
| zazen | 0.4 | 0.80 | 1.0 | 座禅、最大収束 |
| shu_kata | 0.5 | 0.85 | 1.2 | 型の反復学習 |
| ha_deviate | 0.8 | 0.95 | 0.9 | 型からの逸脱 |
| ri_create | 0.9 | 1.0 | 0.8 | 自由創造 |
| deep_work | 0.7 | 0.90 | 1.0 | 書斎、通常作業 |
| shallow | 0.6 | 0.85 | 1.0 | 軽い処理 |

---

## 偉人追加テンプレート

```yaml
# personas/[name].yaml
name: "[フルネーム]"
era: "[生年-没年]"
primary_corpus_refs:
  - "[引用キー (author+year)]"
cognitive_habits:
  - description: "[観察可能な行動記述]"
    source: "[引用キー]"
    flag: fact          # fact | legend | speculative
    mechanism: "[認知神経科学的機序]"
personality_traits:
  # Big Five (0.0-1.0)
  openness: 0.0
  conscientiousness: 0.0
  extraversion: 0.0
  agreeableness: 0.0
  neuroticism: 0.0
  # ERRE 固有特性
  wabi: 0.0             # 不完全性への受容度
  ma_sense: 0.0         # 沈黙への耐性
  shuhari_stage: "shu"  # shu | ha | ri
preferred_zones:
  - study               # 5 ゾーンから選択
```

---

## ゾーン-モード対応表 (拡張版)

| ゾーン | デフォルトモード | 許可される遷移先 | 禁止遷移 |
|---|---|---|---|
| study | deep_work | shu_kata, ha_deviate, zazen | peripatetic (書斎で歩行しない) |
| peripatos | peripatetic | ri_create, shallow | zazen (歩行中に座禅しない) |
| chashitsu | chashitsu | zazen, shu_kata | peripatetic, shallow (茶室で散漫にならない) |
| agora | shallow | ha_deviate, ri_create | zazen (広場で座禅しない) |
| garden | ri_create | peripatetic, shallow | shu_kata (庭園で型の反復は不自然) |

**反省トリガー**: `importance_sum > 150` または `peripatos` / `chashitsu` 入室時。
閾値未満でも温度を上げた自由連想型内省を発火 (DMN-inspired idle reflection)。

---

## ペルソナデバッグ

### 症状: 応答が人物らしくない

```
1. personas/*.yaml の cognitive_habits が十分具体的か確認
   - ❌「散歩する」→ ✅「15:30±5min に 60-75min 歩行、会話なし」
2. system prompt に dump_for_prompt() の結果が含まれているか確認
3. サンプリングパラメータが ERRE モードに合っているか確認
   - peripatetic なのに temperature が低い → 発散思考が抑制されている
   - chashitsu なのに temperature が高い → 内省の収束ができていない
4. few-shot 例を追加して応答品質を改善
```

### 症状: ペルソナドリフト (50 ターン以降)

```
1. system prompt のペルソナ部分が十分長いか確認
2. AgentState の更新で personality_traits が変更されていないか確認
3. 記憶検索結果がペルソナと矛盾する内容を返していないか確認
4. Phase 2 (M9+) の LoRA 導入を検討
```

---

## RadixAttention prefix 設計

```
[共通 prefix — 全ペルソナで共有、KV キャッシュされる]
You are an agent in ERRE-Sandbox, a 3D society simulation.
Available zones: study (deep work), peripatos (walking), chashitsu (tea room),
agora (social), garden (creative).
Current simulation tick: {tick}
World state: {world_summary}

[ペルソナ固有部分 — ここから KV が分岐]
You are {persona.name} ({persona.era}).
Your cognitive habits:
{habits}

Current state:
{agent_state.dump_for_prompt()}

Respond in character. Act according to your cognitive habits.
```

共通 prefix を長くするほど RadixAttention の KV 再利用率が上がる。
ペルソナ固有部分は最小限にする。

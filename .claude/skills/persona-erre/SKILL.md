---
name: persona-erre
description: >
  ペルソナ YAML の設計・ERRE モード定義・サンプリングオーバーライド・system prompt テンプレート。
  personas/*.yaml を作成・変更する時、新しい偉人を追加する時、
  ERRE モード (peripatetic/chashitsu/zazen/shu_kata/ha_deviate/ri_create/deep_work/shallow)
  のパラメータを調整する時に必須参照���
  ERREMode / AgentState の schemas.py 定義を変更する時、
  認知科学的根拠 (DMN/vagal tone/守破離) の正確性を確認したい時に自動召喚される。
  推論バックエンドの構成は llm-inference Skill を参照。
  サンプリングパラメータの適用コード (クランプ含む) は error-handling Skill の examples.md を参照。
allowed-tools: Read, Grep, Glob
---

# Persona & ERRE Mode

## このスキルの目的

ERRE-Sandbox の中核ドメイン知識 — 偉人の認知習慣をどう構造化し、
ERRE モードでどうサンプリングパラメータに反映し、LLM に人格として注入するか。
このスキルは「何を推論するか」のドメイン知識に特化する。
「どう推論するか (サーバー構成・VRAM)」は llm-inference Skill に委譲する。

## ルール 1: ペルソナ YAML の構造

Phase 1 ではインコンテキストペルソナ (YAML → system prompt 注入) を使用。

```yaml
# ✅ 良い例 — personas/kant.yaml
name: Immanuel Kant
era: "1724-1804"
primary_corpus_refs:
  - kuehn2001
  - kant_kritik_1781
cognitive_habits:
  - description: "15:30±5min walk 60-75min"
    source: kuehn2001
    flag: fact         # fact | legend | speculative
    mechanism: "DMN activation during rhythmic locomotion"
  - description: "nasal breathing only during walk"
    source: kuehn2001
    flag: legend
    mechanism: "vagal tone modulation (speculative)"
personality_traits:
  conscientiousness: 0.9
  openness: 0.8
preferred_zones:
  - study
  - peripatos
```

```yaml
# ❌ 悪い例 — source / flag / mechanism がない
name: Kant
habits:
  - walks daily
  - reads books
```

### flag フィールドの意味

| flag | 意味 | 扱い |
|---|---|---|
| `fact` | 一次/二次史料で確認済み | そのまま実装 |
| `legend` | 広く知られるが史料の裏付けが弱い | 実装するが metadata に注記 |
| `speculative` | 認知科学的仮説に基づく推測 | 実装するが仮説であることを明示 |

## ルール 2: ERRE モード別サンプリングオ��バーライド

ベースパラメータ: `temperature=0.7, top_p=0.9, repeat_penalty=1.0`

オーバーライド値 (**加算値**、絶対値ではない):

| モード | temp | top_p | repeat_penalty | 認知科学的根拠 |
|---|---|---|---|---|
| `peripatetic` | +0.3 | +0.05 | -0.1 | DMN 活性化 → 発散思考 |
| `chashitsu` | -0.2 | -0.05 | +0.1 | 収束・内省、重要度上位のみ検索 |
| `zazen` | -0.3 | -0.1 | 0.0 | 最大収束、最小エントロピー |
| `shu_kata` | -0.2 | -0.05 | +0.2 | 反復学習、型の習得 |
| `ha_deviate` | +0.1 | +0.05 | -0.1 | 型からの逸脱 |
| `ri_create` | +0.2 | +0.1 | -0.2 | 自由生成、最大創造性 |
| `deep_work` | 0.0 | 0.0 | 0.0 | ベースパラメータのまま |
| `shallow` | -0.1 | -0.05 | 0.0 | 軽い処理、低リソース |

```python
# ✅ ERREMode.sampling_overrides 経由で定義
from erre_sandbox.schemas import ERREMode

mode = ERREMode(
    mode="peripatetic",
    dmn_bias=0.4,
    sampling_overrides={"temperature": 0.3, "top_p": 0.05, "repeat_penalty": -0.1},
)
```

```python
# ❌ ハードコードされたサンプリングパラメータ
if mode == "peripatetic":
    temperature = 1.0   # マジックナンバー
```

**適用コード (クランプ含む)**: `error-handling` Skill の `examples.md` 例 1
(`generate_with_fallback()`) を参照。ここにコードを重複させない。

## ルール 3: system prompt テンプレート

```python
# ��� ペルソナ YAML + AgentState から system prompt を組み立てる
def build_system_prompt(persona: dict, agent_state: AgentState) -> str:
    habits = "\n".join(
        f"- {h['description']} [{h['flag']}]" for h in persona["cognitive_habits"]
    )
    return (
        f"You are {persona['name']} ({persona['era']}).\n"
        f"Your cognitive habits:\n{habits}\n\n"
        f"Current state:\n{agent_state.dump_for_prompt()}\n\n"
        "Respond in character. Act according to your cognitive habits."
    )
```

**RadixAttention 最適化**: 複数ペルソナで共通の prefix (プロジェクト説明、ゾーン定義) を
system prompt の先頭に配置し、ペルソナ固有部分を後方に置く。
これにより SGLang が prefix KV キャッシュを共有できる。

## ルール 4: 新しい偉人を追加する手順

1. `personas/[name].yaml` を作成 (ルール 1 の構造に準拠)
2. `cognitive_habits` の各項目に `source` / `flag` / `mechanism` を必ず記入
3. `personality_traits` は Big Five の中から該当する特性を 0.0-1.0 で数値化
4. `preferred_zones` は 5 ゾーンから選択
5. `schemas.py` の `PersonaId` リテラル型に追加 (architecture-rules 参���)
6. system prompt でキャラクターが区別可能かテストで検証

## ルール 5: ゾーンと ERRE モードの対応

| ゾーン | デフォルト ERRE モード | 認知的意味 |
|---|---|---|
| study | deep_work | 集中的知的作業 |
| peripatos | peripatetic | 歩行による DMN 活性化 |
| chashitsu | chashitsu | 茶道的内省 |
| agora | shallow | 社会的交流、軽い会話 |
| garden | ri_create | 自然環境での自由創造 |

## チェックリスト

- [ ] ペルソナ YAML に source / flag / mechanism の 3 フィールドがあるか
- [ ] ERRE モード別のサンプリングオーバーライドが `ERREMode.sampling_overrides` 経由か
- [ ] system prompt にペルソナ習慣 + 現在の AgentState が含まれるか
- [ ] 共通 prefix がペルソナ固有部分より前に配置されているか (RadixAttention 最適化)
- [ ] 新しい偉人の `preferred_zones` が 5 ゾーンの中から選ばれているか
- [ ] `flag` が fact / legend / speculative のいずれかか

## 補足資料

- `domain-knowledge.md` — 認知科学的根拠の詳細、ERRE モード早見表、偉人追加テンプレート、ペルソナデバッグ

## 関連する他の Skill

- `llm-inference` — VRAM 管理、サーバー構成、RadixAttention の技術的設定
- `error-handling` — サンプリングパラメータの適用コード (generate_with_fallback)、フォールバック
- `python-standards` — Pydantic v2 スキーマ (ERREMode, AgentState) のコーディング規約
- `architecture-rules` — schemas.py への追記ルール

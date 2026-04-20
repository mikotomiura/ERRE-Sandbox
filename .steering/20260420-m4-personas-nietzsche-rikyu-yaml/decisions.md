# Decisions — m4-personas-nietzsche-rikyu-yaml

## D1. `/reimagine` 適用

### 判断
適用した (v1 → v2 の意図的再構築)。

### 履歴
1. `requirement.md` 記入後、`design.md` に v1 (哲学史トポス駆動) を記入
2. `design.md` を `design-v1.md` に退避
3. 意図的リセット宣言: 「v1 の "Zarathustra 山岳散策" / "茶の湯美学" を踏襲しない」
4. `requirement.md` のみを立脚点に v2 (身体制御-駆動 cognition) を生成
5. `design-comparison.md` で 2 案を 11 観点で比較
6. auto-mode 委任に基づき **v2 ベース + v1 canon 語彙ハイブリッド** を採用

### 根拠
memory `feedback_reimagine_scope.md` の明示的適用範囲。偉人ペルソナの
cognitive_habit / mechanism / sampling は設計選択であり、既存 canon
(Nietzsche = 力への意志、Rikyu = wabi-sabi) に引きずられると差別化不足と
ERRE 核心命題との乖離が後続タスクで露呈する。実際に v2 生成で以下が
明確になった:

- 3 体の peripatos 使用理由が分離 (Kant 定時 DMN / Nietzsche 病間バースト /
  Rikyu 露地 convergent)
- `mechanism` 記述が抽象語彙から観察事実 + 神経生理仮説の対へ格上げ
- sampling tuple が 3 体三角形に明確に配置される

---

## D2. 採用案: **v2 ベース + v1 canon 語彙ハイブリッド**

### 構成
- 全体構造 (`cognitive_habits` の軸、`mechanism` 記述方針、`preferred_zones`、
  `default_sampling`) = v2
- 1 行目 `description` と `display_name` は v1 の canon 語彙を一部残す
  (Zarathustra / Sils Maria / 待庵 / 躙り口 等)
- `primary_corpus_refs` = v2 の一次寄り資料 (overbeck1908、nampo_namporoku)
  を優先しつつ、LLM 世界知識に存在する二次資料 (kaufmann1974、safranski2002、
  kumakura1989、haga1978) も併記

### 理由
1. ERRE 核心命題 (身体的回帰 → cognition) との整合は v2 が強い
2. `mechanism` が神経生理学ベースになることで、後続 M5 以降の ERRE モード
   切替実装と persona の結合が自然 (persona = body → mode 結合の入力)
3. canon 語彙を `description` に残すと第三者可読性が回復し、
   LLM prompt 注入時の citation 可能性も上がる
4. 3 体 sampling tuple が互いに異なる (mechanical 保証は
   `test_sampling_triples_are_unique`)

---

## D3. Kant 専用テストファイルのリネーム (`test_personas.py` → `test_persona_kant.py`)

### 判断
既存の `tests/test_personas.py` を `tests/test_persona_kant.py` にリネーム。

### 理由
- `tests/test_personas/` パッケージを新設するため、Python モジュール名
  `tests.test_personas` が package と file で衝突 (pytest が import file
  mismatch で collect エラー)
- リネームなら内容変更ゼロで M2 の Kant regression 信号を完全に保持できる
- `test_persona_<name>.py` という命名は将来のペルソナ専用テスト (e.g.
  `test_persona_nietzsche.py`) のテンプレートとしても機能

### 代替案 (不採用)
- Kant 専用 assertion を `tests/test_personas/test_kant.py` に moved →
  git の diff 視認性が低下、rename より file-state 変更が大きい
- `tests/test_personas/` 側をパッケージでなくモジュールにする → 今後の
  persona-specific テスト追加で結局パッケージ化が必要になる

---

## D4. `default_sampling` の値設計

### 判断
- Kant (既存): `(0.60, 0.85, 1.12)` — deep_work 寄り、低エントロピー + 中抑制
- Nietzsche: `(0.85, 0.80, 0.95)` — ri_create バースト寄り、高温 + 低抑制
- Rikyu: `(0.45, 0.78, 1.25)` — chashitsu + zazen 寄り、最低温 + 最高抑制

### 理由
persona-erre skill の ERRE モード表に対する baseline 計算:

- base: `(temp=0.7, top_p=0.9, rp=1.0)`
- `peripatetic`: `(+0.3, +0.05, -0.1)` → `(1.0, 0.95, 0.9)` — Kant が寄る先
- `ri_create`: `(+0.2, +0.1, -0.2)` → `(0.9, 1.0, 0.8)` — Nietzsche が寄る先
- `chashitsu`: `(-0.2, -0.05, +0.1)` → `(0.5, 0.85, 1.1)` — Rikyu が寄る先
- `zazen`: `(-0.3, -0.1, 0.0)` → `(0.4, 0.8, 1.0)` — Rikyu がさらに寄れる点

3 体の `default_sampling` はそれぞれの dominant mode の方向へ既に寄せつつ、
`sampling_overrides` (ERREMode) で mode 遷移する余地を残す設計。
tuple の uniqueness は `test_sampling_triples_are_unique` で機械保証。

---

## D5. Nietzsche が `preferred_zones` から `agora` を除外する

### 判断
Nietzsche.preferred_zones = `[peripatos, study, garden]` (agora 除外)。

### 理由
Safranski (2002) ch. 7 の書簡分析で、1879 年 Basel 退職以降の Nietzsche が
意識的に公的社交から撤退していたことが確認されている。これは単なる病による
withdrawal ではなく "perspectival solitude" として自己治療的に採用された
戦略。`preferred_zones` に agora を含めると dialog scheduler が
Nietzsche を agora へ dispatch する確率が高まり、biographical fidelity
を損ねる。

### テスト
`test_nietzsche_avoids_agora` で mechanical 保証。

---

## D6. Rikyu が `preferred_zones` の先頭に `chashitsu` を置き、`peripatos` を除外

### 判断
Rikyu.preferred_zones = `[chashitsu, garden, study]` (peripatos 除外、
chashitsu 先頭)。

### 理由
- Rikyu の cognitive signature は chashitsu-centred (matsukaze /
  nijiri-guchi / seiza / 暗度) なので先頭は chashitsu
- 露地 (garden) の歩行は敷石で歩速を 0.5 Hz 以下に制御する convergent
  preparation walk。これは Kant の Linden-Allee の 60-75 分歩行で DMN
  活性化する peripatos とは役割が正反対
- peripatos を含めると dialog scheduler が Rikyu を peripatos 滞在させる
  可能性があり、persona の設計哲学 (sensory narrowing による convergent
  mode) と衝突する

### テスト
`test_rikyu_primary_zone_is_chashitsu` と `test_rikyu_excludes_peripatos`
で mechanical 保証。

---

## D7. `mechanism` 内の神経科学文献引用は `source` / `primary_corpus_refs` に
載せない

### 判断
`mechanism` 文中に現れる Pulvermüller 2005 / Charles 2013 / Bernardi 2006 /
Schubert 2005 / Jerath 2006 / Foster 2020 等の神経科学文献は、
`cognitive_habits[*].source` にも `primary_corpus_refs` にも載せない。

### 理由
- `source` フィールドの意味は「観察した習慣 (description) の伝記的・歴史的
  出典」。神経科学側の仮説裏付けはこの範疇外
- `primary_corpus_refs` は persona の伝記的一次-二次資料を列挙する枠。
  神経科学文献をここに混ぜると意味が劣化する
- 将来の自動 citation check で両者を区別できるよう、初期から分離する

### 将来の改善
M5 以降で `supplementary_refs: list[str]` フィールドを schema に追加し、
mechanism 内の neuroscience 引用を一元管理する案を検討。本タスクでは
schema 変更を避けるため見送る。

---

## 参照
- `requirement.md`
- `design.md` (v2 採用版、末尾に判断履歴)
- `design-v1.md` (退避された初回案)
- `design-comparison.md` (2 案詳細比較)
- memory `feedback_reimagine_scope.md`
- `.claude/skills/persona-erre/SKILL.md`
- `.steering/20260420-m4-planning/design.md`

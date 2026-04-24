# Empirical Prompt Tuning — 評価イテレーション記録

> 本 Skill の実評価ログは本ファイルに追記していく。
> フォーマットは SKILL.md 「提示フォーマット」節に準拠する。
> 本ファイルは **ランタイム品質保証の台帳** として機能する。

## 記録方針

- 1 評価対象ごとにセクションを作る（`## <対象名> — <YYYY-MM-DD> — tier: Full/Lite/Structural-only`）
- 各 iteration は SKILL.md の「提示フォーマット」に忠実に
- 収束後に「確定変更の diff 要約」を末尾に 3-5 行で添える（次回評価の差分起点になる）
- 途中で打ち切った場合も記録する（理由を明記。将来の参考になる）

---

## 【参考】想定イテレーション記録の雛形

実評価が走った際にこの形でセクションを追加する。以下は書き方の参考（架空データ）。

### `<skill-name>` — YYYY-MM-DD — tier: Lite

**対象**: `.claude/skills/<skill-name>/SKILL.md`
**シナリオ**:
1. (median) 〜
2. (edge-low) 〜

**要件チェックリスト**:
1. `[critical]` <項目 1> → 理由: <1 行>
2. `[critical]` <項目 2> → 理由: <1 行>
3. <項目 3>
4. <項目 4>
5. <項目 5>

**タグ比率チェック**: 5 項目中 critical 2 個 = 40%（20-40% 範囲内）✓

#### Iteration 0 — description/body 整合チェック

- description 記載: 〜
- body カバー範囲: 〜
- 乖离: 無し（or 「〜の乖離あり → iter 1 前に body に追加」）

#### Iteration 1

##### 変更点（前回差分）
- Iteration 0 で検出した〜を SKILL.md 冒頭に追記

##### 実行結果（シナリオ別）

| シナリオ | 成功/失敗 | 精度 | steps | duration | retries |
|---|---|---|---|---|---|
| median | ○ | 80% | 5 | 34s | 0 |
| edge-low | × | 60% | 9 | 48s | 1 |

##### 不明瞭点（今回新出）
- edge-low: `[critical]` 項目 2 が × — <落ちた理由 1 行>
- edge-low: <指針が無く実行者が裁量で判断した箇所>
- median: （新出なし）

##### 裁量補完（今回新出）
- edge-low: <補完内容>

##### 次の修正案
- edge-low で落ちた `[critical]` 2 に対応する判定文言を SKILL.md 「<節名>」に追加

（収束判定: 連続 0 回クリア / 停止まであと 2 回）

#### Iteration 2

...

#### 収束と確定変更

- 連続 2 iter で新規不明瞭点 0、精度改善 +3pt 以下 → 収束
- SKILL.md への確定変更:
  - 〜節に〜を追加
  - 〜のアンチパターンを追記

---

## 実評価ログ

### V (reflection Japanese hint) — 2026-04-24 — tier: Lite (truncated to 1 iter)

**対象**: `src/erre_sandbox/cognition/reflection.py::build_reflection_messages` lines 113-149、特に `_REFLECTION_LANG_HINT` (lines 77-89) の inject。M7 First PR の一部としてコミット済。

**シナリオ (median)**: Kant (persona_id="kant") / zone=study / ERRE=deep_work / tick=42 / episodic 3 件 (peripatos 歩行、Agora での Nietzsche 対話、chashitsu での茶体験)。

**要件チェックリスト** (5 項目中 critical 2 = 40%):

1. `[critical]` system に「日本語」or「Japanese」 → 理由: 無ければ英語応答で違和感残留
2. `[critical]` system に「記述せよ」(not「応答せよ」) → 理由: reflection は書かれた独白、dialog_turn と動詞区別
3. persona display_name + era 含有
4. 200 文字制約と no JSON 指示
5. 返り値が ChatMessage 2 件のリスト

#### Iteration 1

**実行結果**: tool_uses=1, duration_ms=35669

| シナリオ | 成功/失敗 | 精度 | steps | duration | retries |
|---|---|---|---|---|---|
| Kant/study/3-episodic | ○ | 100% (5/5) | 1 | 35.7s | 0 |

**成果物**: Kant 語調の日本語 reflection 146 文字、3 エピソードを「綜合」で束ね、
ドイツ語/ラテン語の鍵概念 3 箇所 (transzendentaler Idealismus, Ding an sich,
innere Anschauung) を括弧併記。

**不明瞭点 (新出)**:

- **英日バイリンガル混在**: system base が英語 + lang_hint だけ日本語。小型ローカル LLM で出力言語が揺れるリスク
- **「学術的・厳密・分析的な語彙」の日本語化基準が曖昧**
- **括弧併記の粒度基準が未規定**: 実行者は中心概念 2-3 個に自己制限
- **「newest first」の保証欠如**: user プロンプト主張と `list_by_agent` 実装の対応が text 上不透明
- **200 文字が日本語文字 or UTF-8 バイトか両義的**

**裁量補完 (新出)**:

- 括弧併記を中心概念 3 箇所に自己制限
- 3 エピソードを「綜合」動詞で束ねる構成
- Nietzsche 固有名をカタカナ化せず原綴維持
- ERRE mode / zone / tick のメタ情報を本文に出さず語調のみ反映

**次の修正案 (iter 2 / follow-up PR に繰越)**:

- (A) system base の英語部分を短く日本語に置換、bilingual lock を外す (小型 LLM 対応)
- (B) 括弧併記の粒度基準 1 文追加
- (C) "≤ 200 Japanese characters" に明記変更

**収束判定**: 1 iter で critical 2/2 ○、全 5/5 ○。SKILL の「連続 2 回クリア」基準は未達、context 予算上 1 iter で止めた運用判断。確定変更なし。

---

### A1 (personality inject) — 2026-04-24 — tier: Lite (truncated to 1 iter)

**対象**: `src/erre_sandbox/cognition/prompting.py::_format_persona_block` lines 65-88、personality inject 2 行 (Big Five + Aesthetic sensibility)。M7 First PR でコミット済。

**シナリオ (median)**: Kant vs Rikyū 比較、両者が同じ state (zone=chashitsu, erre_mode=chashitsu, tick=100) で action plan。Big Five + wabi/ma_sense の数値差が行動分岐に効くか確認。

**要件チェックリスト** (5 項目中 critical 2 = 40%):

1. `[critical]` Big Five 5 フィールド全部 → 理由: 1 つ欠けると差別化軸取りこぼし
2. `[critical]` wabi + ma_sense → 理由: 日本美学の ERRE 的差別化中核
3. 数値形式 (形容詞化を LLM に委任)
4. 既存フィールド regression なし
5. 行数増 ≤ 2

#### Iteration 1

**実行結果**: tool_uses=1, duration_ms=40715

| シナリオ | 成功/失敗 | 精度 | steps | duration | retries |
|---|---|---|---|---|---|
| Kant/Rikyū @ chashitsu | ○ | 100% (5/5) | 1 | 40.7s | 0 |

**成果物**: Kant の "体系化衝動で study へ戻る" vs Rikyū の "茶室に留まり沈黙を action 化" を数値差から読み取り生成。差別化は wabi (0.30 vs 0.95) + extraversion (0.25 vs 0.40) + ma_sense (0.50 vs 0.90) で明瞭。

**不明瞭点 (新出)**:

- **スケール基準欠如**: `[0,1]` のみで、0.5 が neutral か population mean か不明
- **Big Five vs 美学の優先順位**: 両軸衝突時の仲裁ルールなし
- **実質閾値**: 0.25 差は行動分岐に効く、0.10 差は LLM が無視する可能性
- **wabi / ma_sense の定義**: `Aesthetic sensibility:` ラベルだけで英語 LLM に文化的意味を伝えきれるか疑問
- **微差ノイズ**: neuroticism 0.20 vs 0.25 は差別化に寄与せず

**裁量補完 (新出)**:

- destination_zone="study" を cognitive_habits 未読で推定
- 「0.25 差=有意、0.10 差=無視」閾値は経験則 (プロンプト未記載)
- Rikyū の ma_sense=0.90 を「沈黙を action 化する正当化」と解釈 (文化的推論)

**次の修正案 (iter 2 / follow-up PR に繰越)**:

- (A) スケール注記 1 行: "values are normalised to [0,1]; 0.5 is neutral"
- (B) wabi / ma_sense 定義 gloss 1 行 (docs/glossary.md 参照)
- (C) Big Five vs 美学優先順位は意図的に LLM 裁量 (guideline 側で十分)

**収束判定**: 1 iter で critical 2/2 ○、全 5/5 ○。Lite truncated 運用判断。確定変更なし。

---

### Lite tier truncated の運用メモ (2026-04-24)

SKILL.md の Lite tier は「1 シナリオ × 2 iter 固定」だが、本セッションでは context
予算 (M7 First PR 作業中) の都合で **1 iter で止め** (Lite-Lite)、改善候補は
follow-up 機会に繰り越した。Red flags 表の「"不明瞭点ゼロが 1 回出たから終わり" 偶然な
こともある」を認識した上での運用判断。

**次回 Lite 評価を走らせる時は原則通り 2 iter 回すこと。** 今回のケースは critical 項目が
text-level で確実 ("日本語" 文字列が system に入ってるか / Big Five フィールド名が並んでる
か) なので 1 iter で判定可能性が高かった。意味論的曖昧さ (行動への影響度) を主眼にする
場合は必ず 2 iter 以上。

---

## メタ評価: `empirical-prompt-tuning` Skill 自身への適用履歴

本 Skill 自身には Phase H を適用できない（メタ循環）。代わりに `/reimagine` を
Skill ファイルに適用して description ⇔ body の乖離を検出する。その履歴を本節に残す。

フォーマット例:

### `/reimagine` 適用 — YYYY-MM-DD

- 退避先: `.claude/skills/empirical-prompt-tuning/empirical-prompt-tuning-v1.md`
- 再生成 subagent の出力: `empirical-prompt-tuning-v2.md`
- 比較結果（`empirical-prompt-tuning-comparison.md`）:
  - 原本のみ: 〜（→ description 昇格 or 削除判断）
  - v2 のみ: 〜（→ 原本に追加）
  - 両方あるが差異: 〜（→ description に明文化）
- 採用: v1 / v2 / hybrid
- 確定変更: 〜

（未実施）

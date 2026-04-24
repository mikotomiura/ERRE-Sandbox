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

（未実施。初回評価が走ったら本節にセクションを追加する）

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

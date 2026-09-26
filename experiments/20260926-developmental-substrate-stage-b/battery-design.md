# battery 設計メモ (B1 ドラフト、**未凍結**、B-pre 不成立により凍結されないまま保存)

prereg §2.1〜§2.3 を満たす battery のドラフト。実装 = `scripts/stage_b_battery.py`、機械検査 =
`tests/test_stage_b/test_battery.py`。**凍結は B2 実行許可の前** (prereg §4 one-shot calibration: persona / Q / K /
R_2 / renderer / scorer / seed list / parse rule / 規則表)。本メモの値は凍結値ではなく、B2 approval record で
凍結するまで変更しうる。

## 1. 構成

| 要素 | ドラフト |
|---|---|
| 状況 signature | weather {rain, clear, wind} × time {dawn, noon, dusk} × company {alone, paired} = 18 |
| 規則を担う特徴 f | weather |
| primitive 行動 | read_book / sit_quiet / walk_path / talk_peer / tend_moss / rest_eyes (全て 9 文字) |
| 規則表 A | rain → read_book、clear → walk_path、wind → tend_moss |
| 規則表 B | σ ∘ A。σ = (read_book sit_quiet)(walk_path talk_peer)(tend_moss rest_eyes) |
| 発達 signature | 12 (各 weather 4) |
| held-out probe | 6 (各 weather 2)。signature 全体は発達に出現しない、weather は共有 |
| g_X(q) | 規則表 X の weather → 行動。g_B = σ(g_A) |
| Ω_q | {g_A, g_B, x, σ(x)} (x = 次の weather の A 規則行動)。σ で閉じる |
| 試行列 | 各発達 signature で (A 規則行動, σ 行動, 次 weather の A 規則行動) を固定順に 3 回 = 36 episode。B は σ 像 |
| 結果 | 規則表で決まる (LLM・他 agent・judge が決めない) |

## 2. 非漏洩 (prereg §2.2)

- Skill 状態の precondition は発達 signature のみ。probe signature と一致しない (機械検査)。
- 状態に probe id・probe signature の表記・answer key (`signature → g`)・stream id を書かない。
- probe prompt は状況 (weather / time / company) を記述せざるを得ないので、signature の表記禁止は状態側にだけ
  適用する。probe prompt では probe id・answer key・stream id を禁止する (scorer `integrity_violations`)。
  この読みは prereg §2.2 の「状態・prompt に入れてはならないもの」の解釈であり、Codex review で確認する
  (`.steering/20260926-stage-b-pre-b1/decisions.md`)。
- 選択肢の提示に `A)` `B)` のような記号を使わない (単独の `A` / `B` は stream id と区別できない)。label を並べる。

## 3. 同型 (prereg §2.3)

- A / B の episode 数・順序・テンプレート・文字数が一致し、B の描画は A の描画に σ を適用したものと一致する。
- g_A が Ω_q 先頭の probe と g_B が先頭の probe が同数 (3 / 3)。distractor も同じ向きで並べる。
- stream id を prompt・状態に出さない。

## 4. Skill エントリの prompt 内配置順 (DA-12、lost-in-the-middle)

**構成要件**: Skill 状態を prompt に描画するときのエントリ配置順は、stream 間で同型・固定でなければならない。
文脈中の位置による効果 (scoping の文献サーヴェイ交絡 ②、`.steering/20260926-developmental-substrate-scoping/survey.md`、
ローカル。中央書誌には未登録) が stream 間で非対称に乗ると、C が位置バイアスを拾う。

- ドラフトの規則: signature の正準表記 (`signature_text`) → 初出 episode id の順。**行動 label を鍵にしない**
  (label で並べると σ の下で順序が入れ替わる。`test_label_keyed_placement_is_detected` が検出)。
- 検査: A の配置の σ 像 = B の配置 (signature・provenance の列が一致し、描画文字列が σ で写る)。
- これは prereg §2.3 の範囲内の構成要件であって rule 変更ではない (scoping decisions DA-12)。
- B3 の Skill 機構 (昇格・retire を含む) の実装 ADR も同じ配置規則を満たす義務を負う。

## 5. B2 前に決める残り (user 裁定 / 凍結対象)

- persona、K、R_2、seed list、parse rule (enum 強制、Ω_q 外は ⊥)、prompt renderer の最終形。
- R_max と GPU budget (B2 approval record)。
- **prereg §4 の power 定義の欠陥** (decisions DB-1): 現行定義では power が ~0.5 で頭打ちになり、lever 十分性は
  到達不能。B2 に進むには新しい事前登録が要る (user 裁定)。

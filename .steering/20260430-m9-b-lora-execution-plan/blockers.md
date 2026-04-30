# Blockers & Deferred Items — M9-B LoRA Execution Plan

## defer 方針

Codex review LOW finding および設計上 M9-B closure では即決できない判断事項を defer。
defer 期限と reopen 条件を明示。

## Codex LOW findings (defer)

### LOW-1: synthetic heldout 4th persona in eval tests
- **finding**: N=4 deferral acceptable, but eval pipeline may overfit to 3 personas
- **defer 先**: M9-eval-system (eval test fixture として synthetic 4th persona を含める)
- **reopen 条件**: eval pipeline test で synthetic 4th が機能不全
- **status**: DB7 で正式採用、defer は実装タイミングのみ

### LOW-2: LIWC OSS alternative honest framing
- **finding**: Empath/spaCy は LIWC 等価ではない、proxy として framing 必要
- **defer 先**: M9-eval-system (LIWC license 評価 + alternative decision tree 起草)
- **reopen 条件**: LIWC 商用 license が approve / OSS alternative が validation 通過
- **status**: DB10 で正式 framing 採用、license 最終決定は defer

## M9-B closure では決められない判断事項

### LIWC 商用 license の最終可否判定
- **issue**: LIWC-22 は商用 license、ERRE は zero-budget 制約
- **option A**: 商用 license 取得 (one-time fee 数百ドル)
- **option B**: Empath OSS 代用 (proxy、psycholinguistic depth は劣る)
- **option C**: spaCy ベースの custom dictionary 自作 (work cost 大)
- **option D**: stylometry (Burrows' Delta) のみで persona-fit を測り、Big-Five claim を諦める
- **defer 先**: M9-eval-system 着手前 (Tier A 実装の前提)
- **reopen 条件**: いずれかの option が確定

### Burrows' Delta multi-language strategy 詳細
- **issue**: Kant 独原典 vs 英訳 vs 日本語 dialog で idiolect 汚染
- **暫定方針** (DB10 で確定):
  - per-language で normalize
  - within-language reference corpora で比較
  - cross-language Burrows' Delta は使わない
  - Kant の場合: 独訳 reference + 英訳 reference を別 baseline として保持
- **defer 先**: M9-eval-system (reference corpus 整備時に詳細詰め)
- **reopen 条件**: dialog 言語が混在運用される (現状 EN/JA 混在の可能性)

### Prometheus 2 / G-Eval bias mitigation runbook
- **issue**: judge LLM bias literature (CALM 2024、Wataoka 2024 等) が示す
  position / verbosity / self-preference bias を mitigation する手順が必要
- **暫定方針** (codex Q4 反映):
  - position-swap averaging
  - length normalization
  - two local judges for close calls
  - human spot checks
  - CI over repeated runs
  - Prometheus / G-Eval 単独 gate にしない
- **defer 先**: M9-eval-system (Tier C 実装時に runbook 起草)
- **reopen 条件**: judge LLM の選択が確定 (Prometheus 2 8x7B vs Qwen2.5-72B 等)

### 専門家 qualitative review の人 selection
- **issue**: Tier D の expert review に Kant / Nietzsche / Rikyu 専門家の協力が必要
- **暫定方針**:
  - M9-C-adopt 直前で 3 persona × 1 専門家を確保
  - 連絡先 / 関係構築は別途
  - 報酬 / 公開的位置づけ (co-author 等) も決める
- **defer 先**: M9-C-adopt 直前
- **reopen 条件**: 評価系完成後に専門家 selection 開始

### Golden set 1000/persona publication-grade の timing
- **issue**: DB10 で 100/persona seed → 300 acceptance → 1000 publication staging を確定
- **defer 先**: 学術発表時期決定後
- **reopen 条件**: OSF 事前登録 / 投稿先決定

## 設計上の不確実性 (記録のみ)

### v1 棄却の機会コスト
- v1「LoRA ASAP」を棄却したことで、短期 deliverable が遅延
- M9 milestone の 2-3 倍延長 (M9-B / M9-eval-system / M9-C-spike / M9-C-adopt)
- ただし codex Q1 で「v1 cannot prove success because J5 is floor-only」と確認、棄却妥当
- **再評価条件**: M9-eval-system が予想以上に長期化 (>3 セッション) → M9-C-spike を
  evaluation の前倒し材料として強化

### M9-C-spike の adoption 判断 leakage リスク
- spike が「成功」した場合、評価系完成前に adoption 圧力が発生する可能性
- 暫定対策: spike 完了時に明示的に「non-authoritative」を文書化、評価系 gate 通過を要件化
- **対策強化条件**: M9-C-spike Kant が「明らかに人間目視で改善」した場合の判断 protocol を起草

### N=3 漸近線の未測定
- prompting + persona YAML 拡張で N=3 がどこまで divergence するか empirical 未測定
- DB4 plateau gate が fire するかどうか不明
- **観測点**: M9-eval-system Tier B 実装完了直後の 2-3 run で plateau curve を観察

### Tier B sub-metric 3 個の選定妥当性
- DB9 で `vendi_score` / `big5_stability_icc` / `burrows_delta_to_reference` を選定
- これら 3 個が persona discriminative か未検証
- **再評価条件**: M9-eval-system Tier B 実装完了後の golden baseline 採取で discriminative 確認、
  不適切なら sub-metric 入れ替え

## reopen トリガ一覧 (運用 checklist)

| 項目 | reopen 条件 | trigger 場所 |
|---|---|---|
| LIWC license | option A-D いずれか確定 | M9-eval-system 着手前 |
| Burrows multi-lang | dialog 言語混在運用 | M9-eval-system reference corpus |
| Judge bias runbook | judge LLM 確定 | M9-eval-system Tier C 実装 |
| 専門家 selection | 評価系完成 | M9-C-adopt 直前 |
| 1000/persona timing | 学術発表時期 | OSF 登録時 |
| v1 機会コスト再評価 | M9-eval-system >3 セッション | M9-eval-system 中盤 |
| M9-C-spike leakage | spike Kant 目視改善 | M9-C-spike 完了時 |
| N=3 plateau curve | Tier B 実装完了 | M9-eval-system Tier B 完了直後 |
| Tier B sub-metric 3 | golden baseline 採取 | M9-eval-system 終盤 |

# 重要な設計判断 — Plan B retrain prep + 採取 + kickoff

> 本 file は本セッション固有の session-local decisions を記録する。
> 横断 ADR は `.steering/20260513-m9-c-adopt/decisions.md`、Plan B design
> 判断は `.steering/20260517-m9-c-adopt-plan-b-design/decisions.md` DI-1〜DI-8
> を参照。

## DR-1: `_load_default_kernel` への kernel_type dispatch (既存 signature 互換性維持)

- **判断日時**: 2026-05-18
- **背景**: Plan B design DI-6 で「lexical-5gram 実装は next-session scope」
  と決まり、本セッションで `vendi.py:_load_default_kernel` を拡張する必要が
  生じた。既存 regression test
  `test_load_default_kernel_signature_accepts_encoder_name` は source 内に
  `encoder_name or _DEFAULT_ENCODER_MODEL_ID` 文字列があることを assert する。
- **選択肢**:
  - A: `_load_default_kernel(encoder_name=None, *, kernel_type="semantic")`
    として kwarg 追加、kernel_type==`"lexical_5gram"` で dispatch
  - B: 別関数 `_load_lexical_5gram_kernel()` を tier_b/vendi_lexical_5gram.py
    に置き、consumer 側 (da1_matrix_multiturn.py) で encoder_name に応じて
    dispatch
  - C: `_load_default_kernel` を高階化 (factory pattern)
- **採用**: A
- **理由**:
  1. Plan B design §1.5 で明文化された `vendi.py:_load_default_kernel(
     kernel_type=...) から dispatch` 方針に合致
  2. 既存 source 内の `encoder_name or _DEFAULT_ENCODER_MODEL_ID` 行を
     保持できる (regression test green-keep)
  3. kwarg-only にすることで positional callers (Plan A pipeline) を不変
     のまま、新 dispatch path を opt-in にできる
- **トレードオフ**: kernel_type に追加値 (例: byte-pair) を足す時に signature
  が肥大化するリスク。将来 3 以上に分岐するなら C (factory) を再考。
- **影響範囲**: vendi.py + vendi_lexical_5gram.py + 既存 test 不変、新規
  test 1 件追加。
- **見直しタイミング**: 次の Plan (C 等) で別 kernel family が追加される時。

## DR-2: 既存 `make_lexical_5gram_kernel` (Jaccard) と新 `vendi_lexical_5gram.py` (TF-IDF cosine) を共存

- **判断日時**: 2026-05-18
- **背景**: `vendi.py` には既に `make_lexical_5gram_kernel` (P4b sensitivity
  panel で使う Jaccard kernel) が実装されている。Plan B D-2 allowlist の
  `lexical_5gram` primary は char 5-gram **cosine** kernel と書かれている。
  Jaccard と cosine では数値性質が異なる (Jaccard は集合の overlap、cosine
  は TF-IDF weighting 込みの内積)。
- **選択肢**:
  - A: Jaccard を deprecate して cosine に統一
  - B: 別モジュール `vendi_lexical_5gram.py` に cosine を分離、Jaccard は
    P4b sensitivity panel 用に retain
- **採用**: B
- **理由**:
  1. P4b sensitivity panel は既存 baseline でレポート済み (`test_vendi_
     kernel_sensitivity_panel_shape_matches_weights` が依拠)
  2. d2-encoder-allowlist-plan-b.json の `implementation_module` が
     `erre_sandbox.evidence.tier_b.vendi_lexical_5gram` と明示 pre-register
     されている
  3. Plan A の P4b 連続性 (`hybrid-X-Y` kernel name) を破壊しない
- **トレードオフ**: 「lexical_5gram」という名前で 2 つの kernel が存在する
  混乱の余地。本 file で明示分離することで future reader が混乱しない。
- **影響範囲**: `make_lexical_5gram_kernel` (Jaccard) は P4b panel 専用、
  Plan B verdict 計算では使わない。`make_tfidf_5gram_cosine_kernel`
  (新) が Plan B D-2 primary。
- **見直しタイミング**: Plan B verdict 完了後、Jaccard を deprecate するか
  retain するか別 PR で再評価。

## DR-3: lexical-5gram の短入力 (char_wb 5-gram empty vocab) fallback は identity

- **判断日時**: 2026-05-18
- **背景**: `TfidfVectorizer(analyzer="char_wb", ngram_range=(5,5))` は全
  入力が 5 文字未満で edge-pad 後も 5-gram を産まない時に空 vocabulary で
  `ValueError("empty vocabulary")` を raise する。
- **選択肢**:
  - A: ValueError を propagate (caller 責任)
  - B: empty vocab を try/except で受け identity 行列を返す (no similarity
    signal とみなす)
  - C: zeros 行列を返す (`_check_kernel` の diagonal=1 assert で失格)
- **採用**: B
- **理由**:
  1. `compute_vendi` 経由で呼ばれた時に identity 行列なら score=N とみなされ
     る ("each item is fully distinct") のが意味的に整合
  2. 採取された focal turn は通常 ≥60 token (filter 済み) なので boundary
     case は test fixture でしか触れない
  3. C は `_check_kernel` で diagonal!=1 で失格になる
- **トレードオフ**: 「全 sample が短い → score=N で diversity 最大」は誤解
  招くが、Plan B では token>=60 filter があるので production では到達不能
- **影響範囲**: 新 test `test_short_inputs_below_5_chars_fallback_identity`
  でこの挙動を明文化、production では filter で除外される旨を docstring に記載

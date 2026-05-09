# 重要な設計判断 — m9-individual-layer-schema-add

> **Codex independent review (gpt-5.5 xhigh、2026-05-09)** 反映済 — Verdict: Adopt-with-changes
> HIGH 3 件 / MEDIUM 3 件 / LOW 1 件を `codex-review.md` から反映。判断 1, 3, 5 を更新、判断 6, 7 を新規追加。

## 判断 1: SQL `WHERE` filter は **追加しない**、ただし `_DuckDBRawTrainingRelation.__init__` に **構築時 aggregate row assert** を **追加** (Codex HIGH-2 反映)

- **判断日時**: 2026-05-09 (Plan + design.md 起票時) / 改訂 2026-05-09 (Codex HIGH-2 反映)
- **背景**: blockers.md §B-1 の解決方法 #3 「`connect_training_view()` 入口で assert」を、構築時 column-presence assert のみで充足するか、行レベル aggregate assert も追加するかが論点。Codex HIGH-2 は「現行の column-only assert は DB11 ADR の loader-boundary contract を partial にしか実装していない」と指摘
- **選択肢**:
  - A: `connect_training_view()` の SELECT に `WHERE epoch_phase != 'evaluation' AND individual_layer_enabled IS FALSE` を組み込む (count dilution / 失敗の可視性低下)
  - B: SQL filter なし、`assert_phase_beta_ready()` の Python レベル check のみ (現行)
  - **C (採用)**: SQL filter なし、`_DuckDBRawTrainingRelation.__init__` に **構築時 aggregate row assert** を追加 — `SELECT SUM(CASE WHEN LOWER(epoch_phase)='evaluation' THEN 1 ELSE 0 END), SUM(CASE WHEN individual_layer_enabled IS NOT FALSE THEN 1 ELSE 0 END) FROM raw_dialog.dialog` で集計し、いずれも >0 なら `EvaluationContaminationError` raise
- **採用**: **C (構築時 aggregate assert 追加)**
- **理由**:
  1. **DB11 ADR contract の完全実装**: ADR は「loader entry で fail-fast」を要求。column-presence のみだと部分実装
  2. **count dilution 回避**: SQL `WHERE` ではなく aggregate count なので row 数は変わらず、`assert_phase_beta_ready` の `min_examples` check も dilute されない
  3. **失敗の可視性維持**: Aggregate assert は明示的 raise でログに「N evaluation row(s) / M truthy_or_null individual_layer_enabled row(s)」を出す
  4. **多層防御の強化**: 構築時 (loader 層) + Python row scan (gate 層) で 2 段の防御
  5. **`iter_rows` を直接呼ぶ呼出し側** (test 等) も construction-time で保護される
- **トレードオフ**: `_DuckDBRawTrainingRelation.__init__` で 1 SQL aggregate query が増える (constant cost、DuckDB は full table scan で数 ms オーダー)
- **影響範囲**: `eval_store.py:157-176` (`_DuckDBRawTrainingRelation.__init__`)、新規統合 test 1 件 (truthy 行で fail-fast 確認)
- **見直しタイミング**: aggregate query が大規模 .duckdb (10M+ rows) で latency 問題化した場合 (現状は最大 7500 rows なので想定外)

## 判断 2: G1+G2 を **同 commit 必須** (allow-list と DDL の lockstep)

- **判断日時**: 2026-05-09 (設計時)
- **背景**: `eval_paths.py::ALLOWED_RAW_DIALOG_KEYS` (frozenset) と `eval_store.py::_RAW_DIALOG_DDL_COLUMNS` (tuple) を同期更新する必要がある
- **選択肢**:
  - A: G1 (allow-list) と G2 (DDL) を別 commit
  - **B (採用)**: G1+G2 を同 commit で push
- **採用**: **B (同 commit)**
- **理由**: `eval_store.py:90-99` の import-time check (`_BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS` で `EvaluationContaminationError` raise) があり、片方だけ commit すると import が爆発 → ほぼ全テストが ImportError で死ぬ。CI 緑を維持するために必須
- **トレードオフ**: なし (技術的必須条件)
- **影響範囲**: 本 PR の commit 戦略
- **見直しタイミング**: 該当 import-time check が将来削除された場合のみ (削除自体は非推奨)

## 判断 3: `BOOLEAN NOT NULL DEFAULT FALSE` (Codex HIGH-1 反映、当初の `BOOLEAN DEFAULT FALSE` から強化)

- **判断日時**: 2026-05-09 (設計時) / 改訂 2026-05-09 (Codex HIGH-1 反映)
- **背景**: 当初 `BOOLEAN DEFAULT FALSE` を採用したが、Codex HIGH-1 が「DuckDB columns are nullable by default unless `NOT NULL` is set」「explicit `NULL` insert は `bool(NULL or False) → False` で gate を pass する」と指摘。bivalent contract (false / true のみ) が破れる
- **選択肢**:
  - A: `("individual_layer_enabled", "BOOLEAN")` (NULL 許容、未指定で NULL)
  - B: `("individual_layer_enabled", "BOOLEAN DEFAULT FALSE")` (NULL 許容のまま、未指定で false)
  - **C (採用)**: `("individual_layer_enabled", "BOOLEAN NOT NULL DEFAULT FALSE")` (NULL 拒否 + 未指定で false)
- **採用**: **C (`BOOLEAN NOT NULL DEFAULT FALSE`)**
- **理由**:
  - A/B: `bool(NULL or False) → False` の曖昧さ。明示的 `NULL` insert で gate を pass する hole
  - C: NULL 物理的拒否 + DEFAULT で omit insert 互換 (`eval_run_golden.py:547` 等の 15 列 INSERT で omit でも明示 false) + bivalent contract 完全実装
  - DuckDB 1.x で `BOOLEAN NOT NULL DEFAULT FALSE` は標準 syntax ([DuckDB Constraints](https://duckdb.org/docs/current/sql/constraints.html))
  - HIGH-2 の構築時 aggregate assert と組合せて多層防御 (NOT NULL は INSERT 時、aggregate assert は connect 時)
- **トレードオフ**: NOT NULL を加えると、もし将来「未収集」状態を NULL で表現する必要が出た場合の柔軟性を失う。本列は M10-A で truthy を立てる前提で「未知」状態は無いため許容
- **影響範囲**: `_RAW_DIALOG_DDL_COLUMNS`、`bootstrap_schema()` 出力、既存 INSERT の互換性 (omit でも明示 false)、新規 test 2 件 (`is_nullable='NO'` 確認 + 明示 NULL insert 拒否)
- **見直しタイミング**: 「未収集」状態を表現する必要が出た場合のみ (現時点では想定なし)

## 判断 4: 既存 `test_individual_layer_column_absent_raises_blocker_not_resolved` を **保持** + `BlockerNotResolvedError` docstring 強化 (Codex LOW-1 反映)

- **判断日時**: 2026-05-09 (設計時) / 改訂 2026-05-09 (Codex LOW-1 反映)
- **背景**: B-1 完了で `BlockerNotResolvedError` が production schema 経由で never-fire になる。既存 test は意味を失う?
- **選択肢**:
  - A: 該当 test を削除 (post-B-1 で fire しないので意味がない)
  - **B (採用)**: 該当 test を **regression として保持** + `exceptions.py::BlockerNotResolvedError` docstring を「protects non-bootstrap snapshots, old DuckDB artifacts, future non-DuckDB relation implementations」と明文化
- **採用**: **B (保持 + docstring 強化)**
- **理由**:
  1. B-1 の巻き戻りや、別 schema 経路 (Parquet snapshot, future migration to Postgres 等) で列が抜けた場合の防御層
  2. `mock fixture make_relation(with_individual_layer_column=False)` 経由の意図的 trip でテスト網が hot
  3. `exceptions.py::BlockerNotResolvedError` の Type を残すことで `assert_phase_beta_ready` signature の安定 + 将来の dead-code レビュー圧力に対する明示的反論
- **トレードオフ**: docstring 上の「production schema では never fire — regression として残す」と但し書きを足すコストはあるが、無視できる
- **影響範囲**: `tests/test_training/test_train_kant_lora.py`、`tests/test_training/conftest.py` の `make_relation` fixture、`exceptions.py::BlockerNotResolvedError` docstring
- **見直しタイミング**: `RawTrainingRelation` Protocol の `columns` property が削除された場合のみ (Protocol 設計が変わる場合)

## 判断 5: Phase B kick を **PR-A merge 後に倒す** (Codex HIGH-3 反映、当初の Migration defer から方針転換)

- **判断日時**: 2026-05-09 (設計時) / 改訂 2026-05-09 (Codex HIGH-3 反映)
- **背景**: 当初は「A+B 並列で Phase B を B-1 未 merge 状態で kick → 30 cell に新列なし → 別 PR で migration スクリプト作成 (defer)」を採用。Codex HIGH-3 は「Phase B/C overnight 採取コストを考えると known-bad corpus を生成するのは無駄」「`ALTER TABLE … ADD COLUMN ... DEFAULT ...` でも復旧できるが、healthy な順序は B-1 先 merge」と指摘
- **選択肢**:
  - A: 本 PR に idempotent migration script (`scripts/migrate_individual_layer.py`) を含める (1 PR で完結、scope creep)
  - B: Phase B/C を B-1 未 merge 状態で kick → 別 PR で migration script (当初案、blockers.md D-1 として defer)
  - **C (採用)**: **PR-A を本セッション内で完結 → CI 緑 → main merge → G-GEAR で `git pull` → Phase B kick** の順序を推奨。Migration script は不要 (生成される .duckdb は新 schema で bootstrap されるため)
- **採用**: **C (PR-A merge 後に Phase B kick を倒す)**
- **理由**:
  1. **Phase B/C overnight cost (~24-48h) を無駄にしない**: B-1 未 merge で 30 cell 生成 → 後で migration → 不整合検出 cycle になる risk
  2. **「B-1 完了」の semantic clarity**: B-1 merge = blockers.md §B-1 解消 = 後続 .duckdb は全て新 schema、というシンプルな状態管理
  3. **Migration script の defer 不要**: blockers.md D-1 を「弱い fallback」として保持 (万一 PR-A merge 前に user が誤って Phase B kick した場合の rescue)
  4. **「A+B 並列」user 決定との整合**: 「並列」は本セッション内で **PR-A 作成** + **Phase B kick prompt 確認** の意。kick タイミング自体は user 判断 (Phase B kick は user 手動操作)
- **トレードオフ**: Phase B kick が PR-A merge を待つので、B-2 (Phase C 完了) の wallclock が ~半日遅れる可能性 (PR-A merge にかかる Mac master の review/merge 工数次第)。ただし Phase C overnight×2 の方が支配的 (~24-48h)、merge は ~30min なので blast radius 小
- **影響範囲**: 本 PR のハンドオフ (kick タイミングを user に明示)、blockers.md D-1 (弱化、削除はせず保持)
- **見直しタイミング**: PR-A merge にかかる時間 >= Phase C overnight cost になった場合のみ (現実的には起こらない)

## 判断 6: CI grep gate は **weak backstop only** として明文化 (Codex MEDIUM-1 反映、新規)

- **判断日時**: 2026-05-09 (Codex MEDIUM-1 反映)
- **背景**: `individual_layer_enabled\s*[:=]\s*(True\|"true"\|1)` の literal grep は `setattr` / `dict.update` / aliases / comprehensions / `**{flag_name: True}` を検出できない。primary guard とすると false sense of security
- **選択肢**:
  - A: CI grep gate を完全削除し、behavioral DuckDB sentinel test 1 本に絞る
  - B: CI grep gate を primary guard として保持 (false sense of security)
  - **C (採用)**: CI grep gate を保持しつつ「**weak backstop only**」と CI コメント + design.md でドキュメント化、behavioral DuckDB sentinel test を **primary guard** と位置付ける
- **採用**: **C (両方保持、weak backstop と明文化)**
- **理由**:
  1. CI grep は「明示的 truthy リテラル」を catch する低コスト早期警告 (`grep` は ~ms)
  2. behavioral sentinel test は完全だが pytest 実行までの latency あり (~秒)
  3. 既存 `eval-egress-grep-gate` job との整合性 (既存の `metrics.` literal grep も weak backstop)
- **トレードオフ**: ドキュメント化のコストはあるが、grep を残す価値の方が大きい
- **影響範囲**: `.github/workflows/ci.yml:83-123` のコメント、design.md の test 戦略節
- **見直しタイミング**: CI grep が false positive を頻発した場合 (test files を allow-list に入れる必要が出た場合等)

## 判断 7: `INDIVIDUAL_LAYER_ENABLED_KEY` 定数の二重定義解消を **本 PR に含める** (Codex MEDIUM-3 反映、新規、当初の defer から方針転換)

- **判断日時**: 2026-05-09 (Codex MEDIUM-3 反映)
- **背景**: `train_kant_lora.py:62` の `_INDIVIDUAL_LAYER_COLUMN: Final[str] = "individual_layer_enabled"` と、本 PR で追加する `eval_paths.py::ALLOWED_RAW_DIALOG_KEYS` の `"individual_layer_enabled"` リテラルが二重定義。当初は D-2 として defer していた
- **選択肢**:
  - A: D-2 として defer (本 PR の diff を最小に保つ)
  - **B (採用)**: 本 PR に含める — `INDIVIDUAL_LAYER_ENABLED_KEY: Final[str] = "individual_layer_enabled"` を `eval_paths.py` に追加、`__all__` で export、`ALLOWED_RAW_DIALOG_KEYS` 内で使用、`train_kant_lora.py` から import
- **採用**: **B (本 PR で定数統一)**
- **理由**:
  1. 二重定義のままだと将来 column rename (例: `individual_layer_active`) する時に二箇所同時更新が必要 + import-time check は frozenset value を見るので catch されない → **追加の防御層を 1 段失う**
  2. 統一 constant の追加 diff cost は ~15 行 (constant export + 1 箇所の import + test 1 件追加) — scope creep ではなく contract-strengthening
  3. lockstep の自然な拡張 (allow-list の文字列リテラルを全て constant 経由にする方向)
- **トレードオフ**: 本 PR の diff が +15 行増えるが、blast radius は最小 (`train_kant_lora.py` の private 定数を import 1 行に置き換えるだけ)
- **影響範囲**: `eval_paths.py` (export 追加)、`train_kant_lora.py` (import 追加 + private 定数削除)、blockers.md D-2 (削除)
- **見直しタイミング**: なし (本 PR で完結)

## 判断 8: Phase C kick を別セッションへ defer + Phase B 実行環境を Windows native へ転換 (2026-05-09 G-GEAR セッション、新規)

- **判断日時**: 2026-05-09 (Phase B kick セッション)
- **背景**: Phase B kick を `next-session-prompt.md` の WSL2 経由手順で開始したところ、kick 直後 ~30s で `Ollama /api/chat unreachable at http://127.0.0.1:11434` 連鎖失敗を観測。診断結果:
  - Windows Ollama は `127.0.0.1:11434` のみ bind (env `OLLAMA_HOST` unset)
  - WSL2 Ubuntu-22.04 は **NAT mode** (`networkingMode=mirrored` ではない)、default route via `172.28.96.1`
  - WSL2 から `127.0.0.1` / `host.docker.internal` / resolv.conf nameserver `10.255.255.254` 全て unreachable
  - handoff prompt の「`localhost:11434` で WSL2 から到達可能」前提が誤り
- **選択肢**:
  - A: WSL2 networking 修正 (Ollama bind 0.0.0.0 + Windows firewall 11434 inbound 開放 + WSL2 から `--ollama-host http://172.28.96.1:11434` 指定)
  - **B (採用)**: Phase B を **Windows native** で実行 (Phase B は SGLang/CUDA toolkit 不要、Ollama HTTP + DuckDB のみ → WSL2 必要性なし)、`PYTHONUTF8=1` 強制で cp932 codepage の em-dash crash 回避
  - C: Phase B を kick せずセッション終了
- **採用**: **B (Windows native + PYTHONUTF8=1 + Git Bash GNU `timeout`)**
- **理由**:
  1. **最小コスト fix**: Windows Ollama config / firewall を触らず、ネットワーク経路を 1 hop 削減
  2. **K-α retry の WSL2 依存とは別軸**: K-α は SGLang fp8 + CUDA toolkit が Linux 必須だったが、Phase B (Ollama HTTP) は OS 非依存
  3. **wallclock 大幅短縮**: WSL2 9P FS overhead 想定の 75 min/cell が native では **5 min/cell** に短縮、合計 80.5 min wall (handoff 想定 3-5h から 2-3× 速い)
  4. **副作用ゼロ**: 出力先は同じ `data/eval/golden/`、user-facing 成果物は不変
- **トレードオフ**: handoff prompt の WSL2 前提から deviate するが、`g-gear-phase-bc-launch-prompt.md` の本質 (採取手順) は変わらず Phase E PR 構造も同一
- **影響範囲**:
  - 本セッション Phase B kick: WSL2 → Windows native
  - 次セッション Phase C kick: 同じく Windows native (`next-session-prompt-phase-c.md` で明示)
  - Phase B 採取結果 (15 cell): focal=504, 80.5 min wall, B-1 schema 全 cell 反映
  - 判断 5 の前提 (PR-A merge 後 kick) は維持、kick タイミング自体に影響なし
- **追加判断 (Phase C defer)**: Phase C kick は本セッションで連続実施せず別セッションへ defer。理由:
  1. handoff prompt パターン踏襲 (overnight×2 occupancy + context 30% 超リスク)
  2. natural は `--wall-timeout-min 600` で stimulus と異なる lifecycle、Phase B の 5 min/cell が natural に general化するか未確認
  3. Mac 側で本 commit (2812285) を fetch して Phase B audit を独立確認する時間を確保
- **見直しタイミング**: WSL2 networking が `networkingMode=mirrored` に切り替わって 127.0.0.1 で Windows Ollama が見えるようになった場合 (WSL2 設定変更時)

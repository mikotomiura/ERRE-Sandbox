# Codex Independent Review Prompt — m9-eval-cli-partial-fix (案 A')

> **target model**: `gpt-5.5 xhigh`
> **mode**: read-only independent review、実装着手前
> **input**: 採用案 (案 A') の design + 5 specific questions
> **output 期待**: HIGH / MEDIUM / LOW 区分の指摘リスト + Verdict (Adopt / Adopt-with-changes / Reject)

---

## 0. Repository orientation

ERRE-Sandbox プロジェクト (Python 3.11 / FastAPI / DuckDB / sqlite-vec / Pydantic v2)。
- Working tree: `/Users/johnd/ERRE-Sand Box`
- Architecture: `docs/architecture.md` (CLI / eval / evidence / cognition / world 層)
- Layer rule: `cli/ → evidence/ → contracts/ + schemas.py`、 `evidence/` から
  `inference/cognition/world/ui/integration/erre/` への依存は禁止
- 関連 module:
  - `src/erre_sandbox/cli/eval_run_golden.py` (1229 行、本タスクで改修対象)
  - `src/erre_sandbox/evidence/eval_store.py` (atomic_temp_rename 提供、再利用)
  - `src/erre_sandbox/contracts/eval_paths.py` (4-layer contamination contract)
  - `src/erre_sandbox/schemas.py` (canonical wire contract)
  - `tests/test_cli/test_eval_run_golden.py` (既存テスト、stub_text_inference / broken-sink monkeypatch あり)

## 1. 背景: Phase 2 run0 incident と ME-9 ADR の確定方針

2026-05-06、M9-eval Phase 2 run0 で 3 cell が **wall=360 min** で FAILED
(focal=381/390/399 prefix censored)。Codex `gpt-5.5 xhigh` 6 回目 review
(`.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.md` verbatim)
が Claude 単独案の **HIGH 4 件** を切出し、ME-9 ADR
(`.steering/20260430-m9-eval-system/decisions.md` ME-9) で以下の方針が確定:

1. **HIGH-3 (partial masquerade contract)**: 現 `_SinkState.fatal_error` は
   wall timeout/drain timeout/Ollama 失敗/DuckDB INSERT 失敗 の **4 site** で
   同一 field に書き込み、partial と fatal が混在する。`soft_timeout` field 分離が必要。
2. **M3 (`eval_audit` CLI 未実装)**: G-GEAR launch prompt は audit gate を
   要求しているが本体に未実装。partial / complete を機械判定する手段が無い。
3. **HIGH-4 (stale `.tmp` rescue)**: 自動 unlink は partial を silently 破棄する
   危険。sidecar 存在下では明示 flag (`--allow-partial-rescue`) を要求すべき。
4. **HIGH-2 (sample-size correction)**: Phase 2 run0 の partial を救済する
   `width × sqrt(n / n_target)` の流用は破綻し、本タスクで再採用しない。

詳細 spec は `.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`
(spec section 1-6) verbatim を参照。本タスク (`m9-eval-cli-partial-fix`) は
その実装 task で、**Plan mode で 3 案比較 → 採用案 A' 確定** 済み。

## 2. 採用案: 案 A' (案 A + Pydantic model_validator inline)

### 2.1 構造的ポイント

- `_SinkState` (eval_run_golden.py:207-218) と `CaptureResult`
  (eval_run_golden.py:191-204) を **field 拡張** で改修 (新 module 抽出はしない)
- Pydantic v2 `@model_validator(mode="after")` で `fatal_error` と
  `soft_timeout` の **mutual exclusivity を型保証**
- sidecar I/O は新規 `src/erre_sandbox/evidence/capture_sidecar.py` に集約
  (約 80 LoC、`atomic_temp_rename` 再利用)
- `eval_audit.py` は **self-contained** で `duckdb.connect(..., read_only=True)`
  (training egress guard 経由しない、COUNT のみ)
- `_async_main` (eval_run_golden.py:1135-1200) の 3-armed if-elif
  (complete / partial / fatal) は許容 (publisher class への抽出はしない)

### 2.2 不採用案 (記録のみ、本 review では指摘不要だが文脈として)

- **案 B (CaptureLifecycle enum + CapturePublisher class 全抽出)**: state 数
  6 個 / 遷移 5 通りで YAGNI、+250 LoC の認知負荷増分が型保証 (案 A' で 15 行で
  達成済) の利得を上回らない
- **案 C-1 (DuckDB run_meta table)**: spec 1.4 sidecar schema 非互換
- **案 C-2 (event log + reducer)**: schema_version 跳ね上げで spec 起票やり直し

### 2.3 変更対象 (file:line + 方向性)

#### 修正
- `eval_run_golden.py:207-218` (`_SinkState`):
  `soft_timeout: str | None = None` 追加 + Pydantic `@model_validator(mode="after")`
  で `fatal_error` と mutually exclusive を assert (両方非 None で `ValueError`)
- `eval_run_golden.py:191-204` (`CaptureResult`):
  `soft_timeout / partial_capture / stop_reason / drain_completed /
   runtime_drain_timeout` 5 field 追加
- `eval_run_golden.py:978-996` (`_watchdog`):
  wall timeout 分岐 (line 992-994) を `state.soft_timeout = ...` に切替、
  `fatal_error` 触らず
- `eval_run_golden.py:1000-1010` (drain finally):
  現 `state.fatal_error or f"drain timeout"` の or-fold を
  `if not state.soft_timeout: state.fatal_error = ...` 条件付き上書きに修正
  (drain-timeout が wall-timeout を上書きする構造的バグの解消)
- `eval_run_golden.py:599-614` (`_resolve_output_paths`):
  `allow_partial_rescue: bool` 引数追加、stale `.tmp` + sidecar 同居時に
  `--allow-partial-rescue` 無しで `FileExistsError` raise
- `eval_run_golden.py:1034-` (`_build_arg_parser`):
  `--allow-partial-rescue` flag 追加
- `eval_run_golden.py:1135-1200` (`_async_main`):
  3 分岐 (complete / partial / fatal) で sidecar **unconditional write**、
  partial: rename allow + return 3、fatal: rename refuse + return 2、
  Ollama 早期 return 経路 (872-883) でも sidecar status=fatal を必ず書く
- `eval_run_golden.py:470` (DuckDB INSERT) / `:876` (Ollama 失敗):
  既存 `fatal_error` 書込みは現状維持 (wall timeout 経路だけ soft_timeout 化)

#### 新規
- `src/erre_sandbox/evidence/capture_sidecar.py` (約 80 LoC):
  - `SidecarV1` Pydantic model (spec 1.4 schema 準拠、`status: Literal["complete",
    "partial", "fatal"]` discriminated union 風)
  - `write_sidecar_atomic(path, payload)` (`atomic_temp_rename` 再利用)
  - `read_sidecar(path) -> SidecarV1`
- `src/erre_sandbox/cli/eval_audit.py` (約 250 LoC):
  - `main()` 単独 entry (既存 4 CLI と同形式)
  - argparse: `--duckdb` / `--duckdb-glob` / `--focal-target` / `--allow-partial`
    / `--report-json`
  - single-cell return 0 (PASS) / 4 (missing sidecar) / 5 (DB-sidecar mismatch)
    / 6 (incomplete or partial-without-flag)
  - batch: glob 展開 + JSON report atomic 書込
  - DuckDB は `duckdb.connect(str(path), read_only=True)` を self-contained 使用

### 2.4 spec 1.4 sidecar v1 schema (引用、変更しない)

```json
{
  "schema_version": "1",
  "status": "complete",         // complete | partial | fatal
  "stop_reason": "wall_timeout", // complete | wall_timeout | fatal_<reason>
  "focal_target": 500,
  "focal_observed": 381,
  "total_rows": 1158,
  "wall_timeout_min": 360,
  "drain_completed": true,
  "runtime_drain_timeout": false,
  "git_sha": "85e02ea",
  "captured_at": "2026-05-06T12:00:00Z",
  "persona": "kant",
  "condition": "natural",
  "run_idx": 0,
  "duckdb_path": "/data/eval/phase2/kant_natural_run0.duckdb"
}
```

### 2.5 return code 体系

| code | 意味 | rename | sidecar |
|---|---|---|---|
| 0 | complete (focal_target 到達) | allow | status=complete |
| 2 | fatal (DuckDB INSERT / Ollama / drain timeout) | refuse | status=fatal |
| 3 | partial (wall timeout、focal < target) | allow | status=partial |
| 130 | Ctrl-C | (現状維持) | (現状維持) |

audit CLI:
| code | 意味 |
|---|---|
| 0 | PASS (complete + focal>=target、または partial + `--allow-partial`) |
| 4 | missing sidecar (legacy 互換、後方互換性のため意図的に区別) |
| 5 | DB / sidecar mismatch (`total_rows` または focal カウントが食い違う) |
| 6 | incomplete (complete + focal<target) または partial without `--allow-partial` |

## 3. 投げる 5 個の specific questions (必須回答)

### Q1. drain timeout grace 30s の妥当性
`_RUNTIME_DRAIN_GRACE_S = 30.0` (eval_run_golden.py:135) は前回 review (HIGH-6)
で導入された値。本案では wall timeout 後の `runtime.stop()` → drain 待ちに
30s grace を維持するが、ERRE システムの cognition_period は 120s/tick で、
in-flight な `runtime.run()` の現 tick が 30s で完了する保証はない。

**問**: (a) 30s → 60s への引き上げは P3 cell 全体で +30s × N(cell) の wall
budget 増を呼ぶが、partial→fatal への昇格を構造的に減らす。(b) drain timeout
を separate field (`runtime_drain_timeout: bool`) で記録し fatal にしない選択肢
(= drain timeout は `partial + drain_incomplete=true` として publish) は実用的か。
本案では (a) 維持 / (b) 採用しない (drain timeout = fatal 維持) で進めるが、
構造的安全性の観点から MEDIUM 以上の懸念があるか。

### Q2. sidecar schema_version の forward compat 戦略
spec 1.4 は `"schema_version": "1"` 固定。M9-B 以降で `event_log` / `q_and_a_subset`
等の field 追加が必要になった場合の policy として:

**選択肢**:
- (A) Pydantic v2 で `model_config = ConfigDict(extra="allow")` + 古い audit が
  新 sidecar の追加 field を無視 (本案の暗黙想定)
- (B) `schema_version` 文字列で major/minor 分離 (`"1.0"` → `"1.1"`)、major 同一
  なら互換、major 異なれば audit が `return 4` (legacy 扱い) で reject
- (C) discriminated union で `Annotated[SidecarV1 | SidecarV2, Field(discriminator=
  "schema_version")]`、明示的に SDK 側で migration

**問**: 本案 (A 想定) は、運用上 audit 側の brittleness を生むか?
M9-B `event_log` 追加を想定した時、最も refactor cost が低い path はどれか。

### Q3. `eval_audit.py` の training egress guard 経由可否
本案では `evidence/eval_store.py:225` の `connect_training_view()` (training
egress guard 経由) を **使わず**、`eval_audit.py` 内で直接
`duckdb.connect(str(path), read_only=True)` を呼ぶ。理由は:

- audit は COUNT(*) のみで row content に触れない
- guard 経由は CLI の import path を深くし、test mock の負担が増える
- M9-B での audit 拡張時に guard が制約になる懸念

**問**: しかし audit 結果を accidentally training set に混ぜないという
**structural safety** として、guard 経由を強制するべきか。
特に `--report-json` の出力先がうっかり `data/eval/training/` 配下に書かれた場合
(例えば operator typo)、本案の self-contained は防御策ゼロ。
HIGH レベルの懸念か、それとも MEDIUM か。

### Q4. partial publish 時の `selected_stimulus_ids` の扱い
spec 1.4 の sidecar には `selected_stimulus_ids` 自体は含まれないが、
`CaptureResult.selected_stimulus_ids` (eval_run_golden.py:204) は stimulus
condition で stratified slice の id list を保持する。partial publish で
wall timeout した場合、planned list の **全 N 個** vs **実消費 subset** の
どちらを `selected_stimulus_ids` に入れるかの contract が spec に未定義。

**問**: (a) 全 N 個 (replay reproducibility のため) / (b) 実消費 subset (audit で
"何が観測されたか" を反映) / (c) 両方を別 field に持つ。
P3 audit gate での replay-completeness 検査と整合する選択はどれか。
本案では (a) 全 N 個 を採用予定だが、HIGH 以上の構造リスクがあるか。

### Q5. `--allow-partial-rescue` の安全装置強度
本案では stale `.tmp` + sidecar 同居時に `--allow-partial-rescue` 無しで
unlink を refuse する。しかし sidecar 自身が壊れている (Pydantic
validation error 等) 場合の挙動:

**選択肢**:
- (A) sidecar read 失敗 → `--allow-partial-rescue` で unlink 許可 (graceful
  degradation、本案の暗黙想定)
- (B) sidecar read 失敗 → 専用 flag `--force-rescue` を別途要求 (cardinality 増)
- (C) sidecar read 失敗 → operator manual recovery を強制 (CLI 側で何もしない、
  refuse error message のみ)

**問**: (A) は "壊れた sidecar = legacy 互換" 解釈で運用コストが低いが、partial
状態が壊れた sidecar に隠蔽される構造的リスクあり。本案 (A) で OK か、
HIGH 反映で (B) または (C) に切替すべきか。

## 4. その他、独立 review してほしい点

- `_SinkState.soft_timeout` を Pydantic dataclass にする / @model_validator
  使用は既存 dataclass パターン (eval_run_golden.py 全体は `@dataclass` で
  Pydantic を使っていない) との整合性を破るか。`pydantic.dataclasses.dataclass`
  に切り替える / 平の dataclass に runtime assertion を入れるどちらが適切か
- spec 1.4 schema の `wall_timeout_min` field は wall_timeout が起きなかった
  場合 (complete / fatal) に何を入れるか未定義。`None` か CLI 引数値か
- `_async_main` の 3-armed if-elif で **網羅性検査** (Mypy `assert_never`) を
  入れるべきか
- audit CLI の `--report-json` 出力先のデフォルト (Path.cwd() 直下の
  `audit-report.json` で OK か、`data/eval/audit/` を専用に切るか)
- eval_audit が `--allow-partial` を持つが `eval_run_golden` は
  `--allow-partial-rescue` (rescue 文脈)。flag 名衝突しないが命名統一すべきか

## 5. 報告フォーマット (必須)

以下の構造で出力してほしい:

```markdown
## Verdict
- [Adopt / Adopt-with-changes / Reject]
- 一文で判定理由

## HIGH (実装前必反映)
### H1. [タイトル]
- 該当箇所: file:line
- 問題: ...
- 推奨: ...

## MEDIUM (採否は実装側判断、ただし decisions.md に記録)
### M1. [タイトル]
...

## LOW (持ち越し可、blockers.md に記録)
### L1. [タイトル]
...

## 5 questions への回答
### Q1: [選択肢 + 理由]
### Q2: [選択肢 + 理由]
### Q3: [選択肢 + 理由]
### Q4: [選択肢 + 理由]
### Q5: [選択肢 + 理由]

## Out-of-scope notes
(本タスクで対応しないが将来課題として記録すべき点)
```

## 6. 守ってほしい制約

- **read-only**: file 編集はしない、テスト実行もしない
- **scope 厳守**: 本タスクは CLI fix + audit 整備のみ。Phase 2 run1 calibration
  自体や、HIGH-2 sample-size correction の再採用は scope 外
- **spec 1.4 verbatim 尊重**: sidecar schema を変えたい場合は MEDIUM 以下で
  記録し HIGH には昇格しない (spec 起票やり直しの cost は本タスクの minimal-
  change 期待を逸脱)
- **既存資産再利用優先**: `atomic_temp_rename` (eval_store.py:402) /
  `_stub_text_inference` (test_eval_run_golden.py:133) / broken-sink
  monkeypatch pattern (test_eval_run_golden.py:234) を新規実装で重複しない
- 出力は **markdown 単一ファイル** で 4000 語以内目安、verbatim 保存される

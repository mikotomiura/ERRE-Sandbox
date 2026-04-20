# Decisions — m2-functional-closure (T21)

本ドキュメントは T21 `m2-functional-closure` タスクで採用した設計判断と
その根拠を事後整合的に記録する (`/reimagine` 2 案比較結果と live 検証中の発見を集約)。

---

## D1. `bootstrap.py` + `__main__.py` の 2 ファイル構成 (ハイブリッド採択)

### 選択肢
- **v1**: 1 ファイル (`__main__.py`) に CLI shell + composition root を同居
- **v2**: 多段モジュール分割 (`bootstrap.py` / `config.py` / `personas/_loader.py` / `__main__.py` の 4 本)
- **採用 (ハイブリッド)**: `__main__.py` (CLI shell のみ ~20 行) + `bootstrap.py` (composition root + persona loader 内包) の 2 本

### 理由
- v1 は CLI parsing と async lifecycle が同居し、テストで `argv` を差し替える必要があり
  ユニットテスト観点で `bootstrap()` を純粋 async 関数として単体呼出ししたいニーズに反する。
- v2 は MVP 1-agent スコープで config / loader を独立モジュールにする justification が薄く、
  YAGNI 原則上オーバーエンジニアリング。M4 で 3-agent 拡張時に分割する判断で十分。
- ハイブリッドは **テスト容易性** (bootstrap を pure async で呼べる) と **最小ファイル数** を両立。

### How to apply (今後の判断)
- M4 `gateway-multi-agent-stream` で persona loader が 3 体ぶん差分を持つようになった時点で
  `personas/_loader.py` として独立させる。
- CLI オプションが複雑化 (argparse → click 等) する場合のみ `cli.py` に切り出す。

---

## D2. `WorldRuntime` を `bootstrap.py` で構築し `make_app(runtime=...)` に注入

### 選択肢
- 従来: `make_app()` が内部で `_NullRuntime` を default 注入 (test 用のみ動作可能)
- 採用: `bootstrap.py` が `WorldRuntime(clock=RealClock())` を構築し `make_app(runtime=runtime)` に渡す

### 理由
- `_NullRuntime` は uvicorn factory mode (`uvicorn --factory`) でのみ必要な testability hook であり、
  production 起動経路では常に real runtime を注入する設計が Clean Architecture に沿う。
- Constructor injection を活用することで mock 差替えが pytest で容易 (`test_bootstrap.py`)。

### 残す理由 (`_NullRuntime` を削除しない)
- uvicorn factory test / smoke test では app だけ作れる状態を保つ必要がある。
- `docs/architecture.md` §Gateway で「uvicorn factory test mode でのみ起動可能」と明記済。

---

## D3. bug fix 2 件 (live 検証中発見)

### Bug 1: `MemoryStore.create_schema()` 未呼出
- **症状**: orchestrator 起動後 cognition 初回 tick で
  `sqlite3.OperationalError: no such table: episodic_memory`。
- **原因**: `bootstrap.py` が `MemoryStore(db_path)` を instantiate した直後に
  `create_schema()` を呼ばなかった。`MemoryStore.__init__` は connection 確立のみで
  schema は caller の責務として明示的分離されている (単体テストで `:memory:` + 明示 schema 生成が可能)。
- **Fix**: `src/erre_sandbox/bootstrap.py` の `MemoryStore(...)` 直後に `memory.create_schema()`
  を追加 (`CREATE TABLE IF NOT EXISTS` 依存で idempotent)。

### Bug 2: `MoveMsg` zone resolve の往復不能
- **症状**: cognition は 10s で回るが `episodic_memory` が 0 件のまま成長しない。
  Agent が zone を跨がず observation が発生しない。
- **原因**: `cognition/cycle._build_envelopes` が `MoveMsg` target を
  「現在 agent の x/y/z を維持したまま zone フィールドだけ差し替え」て生成。
  `step_kinematics` は `locate_zone(dest.x, dest.y, dest.z)` で実座標から zone を再計算する
  ため、旧 zone が再決定され `zone_changed = None` になる → observation 未発生 → episodic_memory 不成長。
- **Fix**: `src/erre_sandbox/world/tick.py:_consume_result` で
  `locate_zone(tgt.x, tgt.y, tgt.z) ≠ tgt.zone` を検知したら `default_spawn(tgt.zone)` に
  座標を resolve (layer 越境を避け world 側で座標補正を完結させる)。
- **代替案との比較**:
  - cognition 側で正しい coord を計算させる案: cognition が world geometry を知る責務境界違反
  - MoveMsg spec に "target coord is canonical, zone is hint" を明記して world 側で resolve: 採用

### 根拠
- 両 fix は世界座標系の正統性を world 層に保持する原則に整合。
- テスト (59 既存テスト + 新規 `test_bootstrap.py`) が両 fix 適用後に全 PASS。
- live 検証で Kant が peripatos ↔ study を 10 往復 (episodic_memory COUNT=20)。

---

## D4. タグ名: `v0.1.0-m2` → `v0.1.1-m2` への繰上げ

### 判断
- MASTER-PLAN §4.4 当初計画: `v0.1.0-m2` (T20 時点で付与予定)
- T20 closeout 時点では GAP-1 未解消のため tag 付与を T21 後に延期
- T21 closeout で GAP-1 完全解消 + MVP 4 検収項目全 PASS → `v0.1.1-m2` で付与
  (`0.1.1` に minor bump するのは T20 → T21 間で bug fix + composition root 追加の意味的差分を反映)

### 参照
- タグコマンド: `git tag -a v0.1.1-m2 -m "ERRE-Sandbox MVP: 1-Kant walker full-stack (GAP-1 resolved)"`
- 付与済確認: `git tag | grep v0.1.1-m2` → 存在

---

## 参照
- design.md §1 (ハイブリッド採択の詳細)
- acceptance-evidence.md (live 検証 evidence)
- `.steering/20260419-m2-integration-e2e-execution/known-gaps.md` (GAP-1 解消宣言)
- PR #36 (bootstrap + __main__ 導入)
- PR #38 (T21 progress log)
- PR #39 (Godot walking evidence)
- PR #40 (README v0.1.1-m2 status)

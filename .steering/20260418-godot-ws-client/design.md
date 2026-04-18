# T16 godot-ws-client — 設計 (v2 再生成案)

## 実装アプローチ

### 中核アイデア: **Source の分離 × Router の同期ガード × シーン境界での fixture 隔離**

3 つの設計原則でゴール全体を再構成する:

1. **責務を 3 スクリプトに明確分離** (requirement.md スコープと完全一致):
   - `WebSocketClient.gd` = 純粋な WebSocket クライアント (接続 / 再接続 / raw パケット)
   - `EnvelopeRouter.gd` = `kind` 分岐 → **7 個の専用 signal** を emit
   - `AgentManager.gd` = Router の signal を connect、T16 ではログスタブ
2. **Fixture 再生を "別シーン境界" で隔離**:
   - Production: `scenes/MainScene.tscn` (WebSocketClient 経由の実接続)
   - Developer: `scenes/dev/FixtureHarness.tscn` (MainScene を instance した上に
     `FixturePlayer` を add し、WebSocketClient を disable する)
   - **fixture コードが production path に一切混入しない**
   - 起動方式は「どのシーンで起動するか」だけ。環境変数も cmdline 引数も不要
3. **Schema ↔ GDScript kind 同期ガード**:
   - 新設 `tests/test_envelope_kind_sync.py` で、`schemas.py` の 7 kind literal と
     `EnvelopeRouter.gd` の match 分岐キーの**集合一致を CI で強制**
   - schemas.py §7 が変わっても GDScript が黙って古くならない

### データフロー (production mode)

```
ws://g-gear.local:8000/stream
    ↓ WebSocketPeer.poll()
WebSocketClient.gd
    ↓ signal: envelope_received (Dictionary)
EnvelopeRouter.gd  (match envelope.kind)
    ├─ signal: handshake_received
    ├─ signal: agent_updated
    ├─ signal: speech_delivered
    ├─ signal: move_issued
    ├─ signal: animation_changed
    ├─ signal: world_ticked
    └─ signal: error_reported
         ↓ connect
AgentManager / WorldManager / SpeechBubbleContainer / DebugOverlay
```

### データフロー (developer fixture mode)

```
fixtures/control_envelope/*.json  (abs path から FileAccess で読む)
    ↓ FixturePlayer.gd (固定順序 + 0.5s 間隔)
    ↓ signal: envelope_received (Dictionary)
EnvelopeRouter.gd  (production と同じ)
    ↓ 7 signals ...
(production と同じ consumer 群)
```

**Router から下流は両モードで完全に同じ**。signal 配線が 1 箇所に集約されるため、
production/dev の挙動差を設計で防げる。

### 7 kind → 専用 signal 対応表

| envelope.kind | EnvelopeRouter signal | consumer (T16 時点) |
|---|---|---|
| handshake | handshake_received(payload) | DebugOverlay (print) |
| agent_update | agent_updated(agent_id, agent_state) | AgentManager (log) |
| speech | speech_delivered(agent_id, text) | AgentManager (log) |
| move | move_issued(agent_id, target, speed) | AgentManager (log) |
| animation | animation_changed(agent_id, name, loop) | AgentManager (log) |
| world_tick | world_ticked(wall_clock, tick) | WorldManager (log) |
| error | error_reported(code, detail) | WorldManager (push_error) |

未知 kind は Router 内で `push_warning("Unknown kind: %s" % kind)` し、signal を
emit しない (crash なし / 安全失敗)。

### 自動再接続 (WebSocketClient.gd)

`patterns.md §1` パターン踏襲:
- 定数 `RECONNECT_DELAY: float = 5.0`
- `_should_reconnect` フラグ + `_reconnect_timer` で `_process()` 内管理
- 接続成功/切断時に `connection_status_changed(bool)` signal を emit
- **切断検知後 5 秒経過 → 再接続を試行** のサイクルが headless で観測可能

### Fixture 分離の実装詳細

- `godot_project/scripts/dev/FixturePlayer.gd` — `dev/` 配下に隔離
- `godot_project/scenes/dev/FixtureHarness.tscn` — MainScene を instance し、
  FixturePlayer を子 Node として add。MainScene 内の WebSocketClient は
  `set_process(false)` で disable (起動時に FixtureHarness から指示)
- `FixturePlayer.gd` は `DEFAULT_PLAYLIST: PackedStringArray` として
  7 ファイル名を先頭に定数宣言。将来 YAML playlist 差し替え余地を残すが
  T16 スコープは固定順序のみ
- Fixture dir の絶対パスは `OS.get_cmdline_user_args()` から受け取る
  (Python テストからの注入点を単一化)
- 全 fixture 再生後、2 秒待って `get_tree().quit()` で headless 終了

### Schema 同期ガード (新設テスト)

`tests/test_envelope_kind_sync.py`:
```python
def test_envelope_kinds_match_between_schemas_and_router() -> None:
    python_kinds = _extract_kinds_from_schemas()  # schemas.py §7 からパース
    gdscript_kinds = _extract_kinds_from_router()  # EnvelopeRouter.gd を正規表現
    assert python_kinds == gdscript_kinds, (
        f"Drift detected: python={python_kinds}, gdscript={gdscript_kinds}"
    )
```

Python 側は `get_args(ControlEnvelope)` などで Literal を抽出 (TypeAdapter の
schema から読む方がロバスト)。GDScript 側は `EnvelopeRouter.gd` を正規表現で
`^\s*"(\w+)":\s*$` マッチし、match ブロック内のキーを拾う。

## 変更対象

### 新規作成するファイル

**Godot 側 (production)**:
- `godot_project/scripts/WebSocketClient.gd` (~100 行) — **WebSocket に特化**。
  fixture コードを一切持たない
- `godot_project/scripts/EnvelopeRouter.gd` (~80 行) — kind → signal 分岐のみ
- `godot_project/scripts/AgentManager.gd` (~50 行) — Router signals を connect
  してログ出力

**Godot 側 (developer)**:
- `godot_project/scripts/dev/FixturePlayer.gd` (~80 行) — 固定 playlist を順次
  再生
- `godot_project/scenes/dev/FixtureHarness.tscn` — MainScene を instance +
  FixturePlayer を子 Node

**Python 側 (tests)**:
- `tests/test_godot_ws_client.py` (~120 行) — Godot headless で FixtureHarness
  起動 → ログ検査
- `tests/test_envelope_kind_sync.py` (~60 行) — schemas.py ↔ EnvelopeRouter.gd
  の kind 集合一致をアサート
- `tests/conftest.py` (新規 or 既存に追記) — `_resolve_godot()` を
  `tests/test_godot_project.py` から移動して共通化

### 修正するファイル

- `godot_project/scenes/MainScene.tscn` — WebSocketClient ノードと AgentManager
  ノードに script attach (**Godot エディタ経由**で `load_steps` / `ext_resource`
  を安全に更新、手動テキスト編集禁止)
- `godot_project/scripts/WorldManager.gd` — `_ready()` に EnvelopeRouter signals
  (`world_ticked` / `error_reported`) の connect 行を追加
- `tests/test_godot_project.py` — `test_required_project_files_exist` に
  WebSocketClient.gd / EnvelopeRouter.gd / AgentManager.gd のアサーションを追加。
  `_resolve_godot()` は conftest.py へ移動

### 削除するファイル
- なし

### 変更なし (参照のみ)
- `fixtures/control_envelope/*.json` (7 ファイル)
- `src/erre_sandbox/schemas.py` §7 (kind 集合の source-of-truth)
- `.claude/skills/godot-gdscript/SKILL.md` / `patterns.md`

## 影響範囲

impact-analyzer 結果 + v2 固有の追加考察:

- **HIGH 局所 (v1/v2 共通)**: MainScene.tscn 手動編集リスク → Godot エディタ経由必須
- **MEDIUM → LOW (v2 改善)**: schemas.py ↔ GDScript kind の手動同期
  → **自動ガードテストで解消**
- **MEDIUM → LOW (v2 改善)**: fixture コード混入リスク
  → **別シーン境界で完全隔離**
- **LOW**: test_godot_project.py の既存テストは不破壊 (追加のみ、`_resolve_godot`
  の conftest.py 移動は import path 調整のみ)

## 既存パターンとの整合性

- **WorldManager.gd line 7-8 コメント** が T16 の道標 → EnvelopeRouter 経由で
  `_ready()` に signal connect を追加する形で実現
- **test_godot_project.py の 3 層パターン** (必須ファイル / Python 混入 /
  headless boot) → `test_godot_ws_client.py` で踏襲 + `_resolve_godot()` を
  conftest.py へ抽出
- **fixtures/control_envelope/README.md** line 52-71 の GDScript 例を
  `EnvelopeRouter.gd` のテンプレートとして使用
- **T08 test-schemas の 3 層契約ガード思想** を Godot クライアント側にも適用:
  - L1: EnvelopeRouter の kind dispatch (boundary)
  - L2: FixturePlayer の順序不変 + 7 kind 全送達 (meta-invariant)
  - L3: `test_envelope_kind_sync.py` で schemas.py との集合一致 (golden)
- **patterns.md §1** の WebSocket テンプレをそのまま WebSocketClient.gd の
  骨格として使用 (v2 で fixture 混入を排除したため、テンプレ準拠が自然に成立)
- **Autoload (singleton) は使わない**。各スクリプトを Node として MainScene 階層に
  配置し、signal で疎結合する。Autoload 化は将来 T19 E2E 段階で必要に応じて検討

## テスト戦略

### Godot headless 回帰 (`tests/test_godot_ws_client.py`)

- `_resolve_godot()` (conftest.py に移動) を再利用
- 起動パターン:
  `godot --headless --quit-after 60 godot_project/scenes/dev/FixtureHarness.tscn -- --fixture-dir=/abs/path/fixtures/control_envelope`
- assertions:
  1. **exit 0** で終了する
  2. **stdout に 7 kind 全てのシグナル発火ログ** が順序通り (`handshake_received`
     → `agent_updated` → `speech_delivered` → `move_issued` →
     `animation_changed` → `world_ticked` → `error_reported`)
  3. **"Unknown kind" warning が 0 件**
  4. FixturePlayer 終了メッセージ (`[FixturePlayer] playlist complete, quitting`)

### Schema 同期ガード (`tests/test_envelope_kind_sync.py`)

- Python 3.11 + Pydantic v2 で `ControlEnvelope` から Literal 集合抽出
- `EnvelopeRouter.gd` を regex パースして match ブロックのキー集合抽出
- 集合一致を assert。差分があれば diff を詳細表示

### 必須ファイル / Python 混入 (`tests/test_godot_project.py` 拡張)

- `test_required_project_files_exist` に以下を追加:
  - `godot_project/scripts/WebSocketClient.gd`
  - `godot_project/scripts/EnvelopeRouter.gd`
  - `godot_project/scripts/AgentManager.gd`
  - `godot_project/scripts/dev/FixturePlayer.gd`
  - `godot_project/scenes/dev/FixtureHarness.tscn`
- `test_godot_project_contains_no_python` は変更不要 (自動で新規 .py 混入を検知)

### TDD 適用範囲

- **TDD 適用**: `test_envelope_kind_sync.py` を**先に書く** (Router 実装前に
  フェイル状態で commit、Router 実装で pass させる)
- **TDD 非適用**: GDScript の描画・Godot ランタイム挙動は headless 統合テストで
  代替

### テスト実行順序
1. `test_envelope_kind_sync.py` (最速、Python のみ)
2. `test_godot_project.py` (既存 3 件 + 拡張アサーション、Godot 不要)
3. `test_godot_ws_client.py` (Godot headless 要、未 install は skip)

## 関連する Skill

- `godot-gdscript` — SKILL.md ルール 1-6、patterns.md §1/§4
- `error-handling` — WebSocket 再接続パターン (思想を GDScript に適用)
- `architecture-rules` — `godot_project/` に Python 不混入、`ui/` → `schemas.py`
  のみ依存 (今回 ui/ は触らない)
- `test-standards` — `tests/test_godot_ws_client.py` / `test_envelope_kind_sync.py`
  のフィクスチャ / skip 判断
- `git-workflow` — feat(godot): T16 ... + Refs: .steering/20260418-godot-ws-client/

## ロールバック計画

- T16 は T15 scaffold の上に新規ファイル追加が主体。問題時は以下で戻る:
  1. `git reset --hard origin/main` で T16 branch を破棄 (main は T15 完了状態)
  2. MainScene.tscn を誤編集した場合: `git checkout origin/main -- godot_project/scenes/MainScene.tscn`
  3. WorldManager.gd の signal 接続行は部分リバートで v1 scaffold 状態に戻せる
- 新設テスト (`test_envelope_kind_sync.py`) は独立ファイルのため、問題時は
  単独削除で元 CI 状態に戻る

## v2 設計の着眼点 (v1 の弱点への対処)

| v1 弱点 | v2 での対処 | 備考 |
|---|---|---|
| V1-W1 SRP 違反 (全部 WebSocketClient.gd) | **3 スクリプト完全分離** + fixture は別シーン | Client = 通信のみ / Router = 分岐のみ / Manager = 受け手のみ |
| V1-W2 fixture が production path 混入 | **シーン境界で隔離** (`scenes/dev/` + `scripts/dev/`) | production ビルドで `dev/` を除外可能 |
| V1-W3 AgentManager 書き直し懸念 | T17 で avatar instance を追加する際の signal connect 点を Router 経由に固定 | Router の signal 設計で境界を先に確定 |
| V1-W4 kind 同期点集中 | **新設 `test_envelope_kind_sync.py`** で CI ガード | schemas.py 変更時に GDScript drift を即検出 |
| V1-W5 requirement との不整合 (Router 削除) | **requirement.md の 3 スクリプト構成に完全準拠** | Router.gd を中核に据える |
| V1-W6 fixture playlist ハードコード | T16 では固定順でよいが、**定数 array として先頭に出す** | 将来 YAML playlist 差し替え容易 |
| V1-W7 env var + cmdline 二重サポート | **cmdline 引数のみ** (`--fixture-dir`) | Python テストから単一経路、シンプル |

## 次のステップ

1. ~~`design-comparison.md` を作成して v1 と v2 を並置~~ ✓
2. ~~ユーザーに採用案 (v1 / v2 / ハイブリッド) を確認~~ ✓
3. ~~採用案を design.md に確定~~ ✓ (本ファイルが確定版)
4. tasklist.md へ (Step D)

## 設計判断の履歴

- **2026-04-18**: 初回案 (design-v1.md) と再生成案 (v2) を `design-comparison.md`
  で並置比較
- **採用**: **v2 (再生成案) をフル採用**
- **根拠 (ユーザー判断)**:
  - requirement.md との整合性 (v1 は要件違反の Router 削除を含んでいた)
  - T17/M5/M9 への signal 契約基盤として Router の 7 専用 signal が長期投資になる
  - Contract-First 思想 (MASTER-PLAN §2.2) の延長として schema drift の
    CI ガード (`test_envelope_kind_sync.py`) を導入
  - 工数差 +0.3 d は requirement.md の 1.0 d 見積と一致し、v1 が隠蔽していた
    将来のリファクタ工数と相殺される
  - V1-W1/W2/W4/W5/W6 を構造で解消、ハイブリッドは v2 効果を部分的に損なうため
    非採用

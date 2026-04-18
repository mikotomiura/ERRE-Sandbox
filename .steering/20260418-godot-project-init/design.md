# 設計 — T15 godot-project-init (再生成案 v2)

## 実装アプローチ

T15 を **Scaffolded Handoff** として設計する。単に boot を通すのではなく、
patterns.md §2 の MainScene ノード階層を空スタブで配置し、
repository-structure.md §1 のディレクトリ構造を全てミラーして、
T16/T17/M5 が「階層に .gd を attach / zone を instance / アセットを追加」
するだけで進められる状態を作る。自動検証 (pytest) で Godot headless
boot を CI 可能にする。

v2 の 5 つの柱:

1. **MainScene は patterns.md §2 の階層を空スタブで事前配置**
   - ZoneManager / AgentManager / WebSocketClient / UILayer ノードを
     プレースホルダとして置く。T16/T17 は新規ノード追加ではなく
     既存ノードへの .gd attach で拡張できる
2. **repository-structure.md ミラーを完成**
   - `scenes/zones/` / `scripts/` / `assets/` を README.md で意図明示
     (空 dir + `.gitkeep` ではなく、各 dir に "この下に何が入るか" を
     Godot 開発者向けに書く README を置く)
3. **WorldManager.gd を最小実装として T15 で配置**
   - root スクリプト。boot 時に `print("[WorldManager] ready at tick 0")`
     + WebSocketClient node への参照を持つ形にし、T16 で接続配線だけ書き足せる
4. **pytest で Godot headless boot を自動検証** (Godot 未 install 環境では skip)
   - `tests/test_godot_project.py` 新設
   - `subprocess.run([godot, "--path", "godot_project", "--headless", "--quit"])`
5. **NOTICE に Godot ランタイム言及を追記** + `godot-gdscript/patterns.md`
   の 4.4 表記を 4.4-4.6 に緩和 (setup-macbook decisions で予告された同期)

## 変更対象

### 修正するファイル
- `.gitignore` — Godot キャッシュ除外
- `NOTICE` — Godot ランタイムへの言及 (ユーザー install、not bundled)
- `.claude/skills/godot-gdscript/patterns.md` — 4.4 表記を 4.4-4.6 に緩和 (setup-macbook decisions 予告分)

### 新規作成するファイル
- `godot_project/project.godot`
- `godot_project/icon.svg` (minimal hand-written SVG)
- `godot_project/scenes/MainScene.tscn`
- `godot_project/scenes/zones/README.md`
- `godot_project/scripts/WorldManager.gd` (boot 用最小実装)
- `godot_project/scripts/README.md`
- `godot_project/assets/README.md`
- `tests/test_godot_project.py`

### 削除するファイル
- なし

## `project.godot` (v2)

```ini
config_version=5

[application]
config/name="ERRE-Sandbox"
config/description="Autonomous 3D Society from the Cognitive Habits of Great Thinkers"
run/main_scene="res://scenes/MainScene.tscn"
config/features=PackedStringArray("4.4", "GL Compatibility")
config/icon="res://icon.svg"

[display]
window/size/viewport_width=1280
window/size/viewport_height=720

[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
```

理由: GL Compatibility renderer は Apple Silicon M4 統合 GPU で安定、
後で Forward+ への切替は可能 (renderer/rendering_method を上書きするだけ)。

## MainScene ノード階層 (v2)

```
MainScene (Node3D)               ← root, WorldManager.gd attached
├── Environment (WorldEnvironment)
│   └── DirectionalLight3D
├── Camera3D                      ← 仮位置 (peripatos 俯瞰想定)
├── ZoneManager (Node3D)          ← T17/M5 がゾーン .tscn を instance
├── AgentManager (Node3D)         ← T16 がエージェントを動的 add_child
├── WebSocketClient (Node)        ← T16 が WebSocketClient.gd を attach
└── UILayer (CanvasLayer)
    ├── SpeechBubbleContainer (Control)
    └── DebugOverlay (Label)      ← "ERRE-Sandbox T15 init" 表示
```

## `WorldManager.gd` (v2 最小実装)

```gdscript
## MainScene root script.
## Later phases wire WebSocketClient + AgentManager together here.
class_name WorldManager
extends Node3D


func _ready() -> void:
    print("[WorldManager] ERRE-Sandbox booted at tick 0")
    var debug_label: Label = $UILayer/DebugOverlay
    if debug_label:
        debug_label.text = "ERRE-Sandbox — T15 init (boot OK)"
```

T16 以降でこのファイルに WebSocketClient の接続・signal hookup を書き足していく。

## ディレクトリ構造と README

- `godot_project/scenes/` → MainScene.tscn
  - `zones/README.md`: 「T17 / M5 で Peripatos.tscn, Study.tscn, Chashitsu.tscn, Agora.tscn, Garden.tscn を配置。schemas.py の Zone enum と名前を一致させる」
- `godot_project/scripts/` → WorldManager.gd
  - `README.md`: 「命名規約 PascalCase.gd。AgentController.gd / WebSocketClient.gd を T16 で追加」
- `godot_project/assets/` → (空)
  - `README.md`: 「Blender で `.blend` を作成し、`.glb` にエクスポートして配置。GPL 由来アセットは別パッケージ (erre-sandbox-blender/) 経由でのみ。直接 bpy を使うコードは禁止」

README を各 dir に置くことで、空 dir 問題 (git の未 tracking) を解消しつつ、
Godot 開発者に即座に「何を置くか」の文脈を渡す。

## icon.svg (v2 最小実装)

手書きの 128x128 SVG。単色背景 + "E" (ERRE) の 3 本線。パブリックドメイン。
`<svg viewBox="0 0 128 128">` で 20 行以内。

## `.gitignore` 追加分 (v2)

```
# Godot cache (T15 godot-project-init)
godot_project/.godot/
godot_project/.import/
godot_project/*.import
godot_project/export_presets.cfg
```

## NOTICE 追記 (v2)

```
--- Godot runtime (not bundled, user-installed) ---

The `godot_project/` directory contains GDScript and scenes for use with
Godot Engine 4.x, an MIT-licensed open source game engine
(https://godotengine.org). Godot itself is not bundled with this
repository; users install it independently.
```

## 自動検証 (`tests/test_godot_project.py`)

```python
"""T15: validate that `godot_project/` boots headlessly in Godot 4.x."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GODOT_PROJECT = REPO_ROOT / "godot_project"
GODOT_BIN_MAC = Path("/Applications/Godot.app/Contents/MacOS/Godot")


def _resolve_godot() -> Path | None:
    if GODOT_BIN_MAC.exists():
        return GODOT_BIN_MAC
    found = shutil.which("godot")
    return Path(found) if found else None


def test_project_godot_exists() -> None:
    assert (GODOT_PROJECT / "project.godot").is_file()
    assert (GODOT_PROJECT / "scenes" / "MainScene.tscn").is_file()
    assert (GODOT_PROJECT / "icon.svg").is_file()


def test_godot_project_contains_no_python() -> None:
    """architecture-rules: godot_project/ must not contain Python files."""
    py_files = list(GODOT_PROJECT.rglob("*.py"))
    assert py_files == [], f"Python files found under godot_project/: {py_files}"


def test_godot_project_boots_headless() -> None:
    godot = _resolve_godot()
    if godot is None:
        pytest.skip("Godot not installed; install at /Applications/Godot.app")
    result = subprocess.run(
        [str(godot), "--path", str(GODOT_PROJECT), "--headless", "--quit"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (
        f"Godot headless boot failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
```

3 件のテストで (a) 最小ファイル存在、(b) Python ファイル不混入 (architecture-rules
強制)、(c) 実機 Godot による headless boot を自動化。Godot 未 install 環境では
skip して CI を壊さない。

## patterns.md の 4.6 対応同期

setup-macbook decisions が「Skill を 4.6 に更新する」方向性を予告していた。
T15 で該当箇所を修正:

- `patterns.md` の「Godot 4.4 の推奨パターン」を「Godot 4.4 / 4.6 の推奨パターン」
  に緩和 (API 互換のためコード変更不要、表記のみ)

これ以上の修正は T16 以降に譲る (4.6 固有機能の活用は T16/T17/M5 で検討)。

## 既存パターンとの整合性

- **architecture-rules**: `godot_project/` に Python 0 件 — `test_godot_project_contains_no_python` で強制
- **godot-gdscript SKILL.md ルール 4**: 5 ゾーン名 (study/peripatos/chashitsu/agora/garden) — README で明示
- **godot-gdscript SKILL.md ルール 6**: Python 禁止 — 上記テストで自動強制
- **blender-pipeline**: GPL 分離 — assets/README.md に明記
- **repository-structure.md §1**: `godot_project/` ツリー — v2 で完全ミラー
- **test-standards**: `tests/test_godot_project.py` は既存 `tests/` ミラー構造に従う

## テスト戦略

- **自動** (tests/test_godot_project.py):
  - ファイル存在 (project.godot / MainScene.tscn / icon.svg)
  - Python 混入 0 件
  - Godot headless boot (実機 Godot あれば pass、無ければ skip)
- **手動**: Godot エディタで開いて MainScene ノード階層が表示されること

## ロールバック計画

- 新規 `godot_project/` + .gitignore / NOTICE / patterns.md 小編集 + tests 1 件
- `git revert` で単独復元可能

## 懸念とその対処

| 懸念 | 対処 |
|---|---|
| `WorldManager.gd` の `@onready` / `get_node` を使うと boot 時に階層ミスで失敗 | `if debug_label:` ガードで fail-soft。print で boot ログを確実に残す |
| headless boot テストが timeout (60s) で CI を遅くする | 実運用で 1-2 秒程度。60s は安全マージン |
| SVG icon の手書き品質 | デザインは暫定。M4-M10 で正式ロゴ差し替え予定と README に記載 |
| Godot 4.4 vs 4.6 の微妙な API 差分 | patterns.md の表記を緩和しコード例は共通化。API 破壊的差分が見つかれば bug-fix PR |
| `.gitkeep` vs README の選択 | README は git-tracked で intent を明示できる。`.gitkeep` は無機質 |
| 空 assets/ の Blender アセット追加時のフロー | assets/README.md で「erre-sandbox-blender パッケージから glTF export してこの dir に置く」を明示 |
| `SpeechBubbleContainer (Control)` が CanvasLayer 直下で OK か | Godot 4.x は UI のルートを Control にする慣習。動作確認は T16 時に再評価 |

## 設計判断の履歴

- 初回案（design-v1.md）と再生成案（v2）を `design-comparison.md` で比較
- 採用: **v2（再生成案）**
- 根拠: requirement.md §ゴール「T16 godot-ws-client が WebSocketClient.gd を
  すぐ書き足せる配置」要求への直接応答。T06-T08 で確立した「実装 + Skill
  同期 + ドキュメント整合」パターンを継続 (setup-macbook decisions が予告した
  patterns.md の 4.6 同期を履行)。architecture-rules の Python 混入禁止を
  pytest で機械強制。0.5d 枠に scaffold は十分収まる。

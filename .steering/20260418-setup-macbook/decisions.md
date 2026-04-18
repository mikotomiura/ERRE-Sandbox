# 設計判断

## 判断 1: Godot を 4.6.2 で採用 (MASTER-PLAN の 4.4 指定から逸脱)

- **判断日時**: 2026-04-18
- **背景**: MASTER-PLAN §7.1 は `brew install --cask godot` で Godot 4.4 を
  指定していたが、2026-04 時点で brew cask が提供するのは 4.6.2 が最新安定版
- **選択肢**:
  - A: brew 経由 4.6.2 を受け入れる
  - B: 4.4 を別途 DL して手動インストール
  - C: 過去バージョンを維持するため brew pin を設定
- **採用**: **A (4.6.2)**
- **理由**:
  - Godot 4.x は minor バージョン間で後方互換。MVP で使う基本機能
    (WebSocket, Skeleton, AnimationPlayer) はすべて維持
  - brew 標準を外すとアップデート追従が手動になる
  - 後発の T15-T17 で godot-gdscript Skill を参照する際、skill 側が 4.4
    前提で書かれているなら、そちらを 4.6 に更新する方が筋が良い
- **トレードオフ**:
  - MASTER-PLAN §7.1 と docs/architecture.md の「Godot 4.4」記述との齟齬
  - チュートリアルや記事の 4.4 前提 UI 差分
- **影響範囲**: T15 (godot-project-init) で Renderer モード等の UI 差分、
  `.claude/skills/godot-gdscript/` の記述更新
- **見直しタイミング**: T15 で 4.6 固有の破壊的変更が発覚した場合

## 判断 2: `code` CLI を `/usr/local/bin/` ではなく `~/.local/bin/` にシンボリックリンク

- **判断日時**: 2026-04-18
- **背景**: VS Code の「Install 'code' command in PATH」は sudo を要求して
  `/usr/local/bin/code` にシンボリックリンクを作成する。同じ機能を sudo なしで
  実現したい
- **選択肢**:
  - A: VS Code UI の command palette で公式インストール (sudo 必要)
  - B: `~/.local/bin/code` へ手動 symlink (既に PATH に入っている)
  - C: PATH に App Bundle 内のパスを追加
- **採用**: **B**
- **理由**:
  - `~/.local/bin` は uv のインストール時に既に PATH 先頭に入っている
  - sudo を介さず冪等に作成できる
  - アンインストール時も symlink 削除のみで済む
- **トレードオフ**: VS Code のアップデートで symlink が切れる可能性 (ただし
  App Bundle 内のパスは安定)
- **影響範囲**: MacBook 側のシェル環境のみ
- **見直しタイミング**: symlink が切れた場合に再作成

## 判断 3: python.org 版 Python 3.11.9 を残したまま uv 管理の 3.11.15 を併設

- **判断日時**: 2026-04-18
- **背景**: MacBook には既に python.org 版 Python 3.11.9 が
  `/Library/Frameworks/Python.framework/` にインストール済み。uv は独自に
  3.11.15 を `~/.local/share/uv/python/` に入れる
- **選択肢**:
  - A: python.org 版を uninstall して uv 管理に一本化
  - B: 両方残し、プロジェクト内は uv が自動で 3.11.15 を選ぶ
  - C: python.org 版を uv の managed として登録
- **採用**: **B**
- **理由**:
  - 他の用途 (Jupyter, 他プロジェクト) で python.org 版が参照されている可能性
  - uv は `pyproject.toml` の `requires-python = "==3.11.*"` 等で自動選択
  - uninstall はリスクが高く、T02 のスコープ外
- **トレードオフ**: `python3` コマンドのデフォルトが python.org 版を指すため、
  `uv run` を使わない bare 実行で混乱する余地
- **影響範囲**: T04 以降の全 Python タスク。対処は `uv run` を徹底する
  (development-guidelines.md で既にルール化)
- **見直しタイミング**: python.org 版で明確な衝突が発生した時

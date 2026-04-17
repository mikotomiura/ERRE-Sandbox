---
name: architecture-rules
description: >
  レイヤー依存方向・インポート制約・GPL/クラウド API 禁止ルール。
  src/erre_sandbox/ 配下に新しいファイルを追加する・インポートを変更する・
  新しい依存ライブラリを追加する時に必須参照。
  schemas.py / inference/ / memory/ / cognition/ / world/ / ui/ / erre/
  のどのモジュールにコードを置くか判断する時、
  import 文が依存方向に違反していないか確認する時、
  pip install / uv add でライブラリを追加する時に自動召喚される。
  GPL ライブラリ (bpy 等) を src/erre_sandbox/ に import する禁止も含む。
allowed-tools: Read, Grep, Glob
---

# Architecture Rules

## このスキルの目的

ERRE-Sandbox のアーキテクチャは 2 拠点 (G-GEAR + MacBook) × 5 レイヤー構成。
インポートの依存方向を守ることで、将来のバックエンド差し替え (Qdrant、gRPC 等) を
最小の変更で実現できるようにする。また、GPL ライブラリとクラウド API の混入を防ぐ。

## レイヤー依存方向（絶対厳守）

```
world/ → cognition/ → inference/
                    → memory/
                          ↓
ui/ ──────────→ schemas.py ← (全モジュールが参照)
```

| モジュール | 依存先 | 依存禁止 |
|---|---|---|
| `schemas.py` | なし (最下層) | すべての src モジュール |
| `inference/` | `schemas.py` のみ | `memory/`, `cognition/`, `world/`, `ui/` |
| `memory/` | `schemas.py` のみ | `inference/`, `cognition/`, `world/`, `ui/` |
| `cognition/` | `inference/`, `memory/`, `schemas.py` | `world/`, `ui/` |
| `world/` | `cognition/`, `schemas.py` | `ui/` |
| `ui/` | `schemas.py` のみ | `inference/`, `memory/`, `cognition/`, `world/` |
| `erre/` | `schemas.py`, `inference/`, `memory/` | `world/`, `ui/` |

### 依存方向の確認方法

```bash
# ui/ が inference/ を import していないか確認
grep -r "from erre_sandbox.inference" src/erre_sandbox/ui/
grep -r "from erre_sandbox.memory"    src/erre_sandbox/ui/

# schemas.py が他モジュールを import していないか確認
grep "from erre_sandbox\." src/erre_sandbox/schemas.py
```

## 絶対禁止ルール

### 禁止 1: GPL ライブラリを src/erre_sandbox/ に import

Blender の `bpy` は GPL-2+ のため、import するコードが GPL 派生物になる。
Apache-2.0 OR MIT デュアルライセンスと矛盾するため **絶対に混入させない**。

```python
# ❌ 絶対禁止
import bpy                          # GPL viral — Apache/MIT と矛盾
from bpy.types import Object        # 同上
```

将来 Blender 連携が必要になった場合 → `erre-sandbox-blender/` を別パッケージ (GPL-3) で分離。

### 禁止 2: クラウド LLM API を必須依存にする

OpenAI / Anthropic / Google の API は予算ゼロ制約に反する。

```python
# ❌ 禁止
import openai                       # 有料 API
from anthropic import Anthropic     # 有料 API
```

ローカル推論 (SGLang / Ollama / llama.cpp) のみ使用。

### 禁止 3: ui/ から inference/ / memory/ を直接 import

UI は WebSocket 経由で G-GEAR と通信する。Python の import で直接呼ばない。

```python
# ❌ 禁止 — ui/ から memory/ を直接呼ぶ
from erre_sandbox.memory.store import MemoryStore  # ui/ 内に書いてはいけない

# ✅ 正しい — WebSocket 経由
from erre_sandbox.schemas import ControlEnvelope   # スキーマのみ OK
```

### 禁止 4: schemas.py から他の src モジュールを import

`schemas.py` は最下層。循環参照を防ぐために依存なしを厳守。

```python
# ❌ 禁止
from erre_sandbox.memory.store import MemoryStore  # schemas.py 内に書いてはいけない

# ✅ 正しい — 型ヒントのみなら TYPE_CHECKING で遅延
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from erre_sandbox.memory.store import MemoryStore
```

## 新しいファイルの配置判断フロー

```
新しい .py ファイルを作る
    │
    ├─ LLM 推論関連?           → inference/
    ├─ 記憶・検索・埋め込み?   → memory/
    ├─ 認知サイクル・反省?     → cognition/
    ├─ ワールド・物理・ゾーン? → world/
    ├─ WebSocket クライアント・Godot 連携? → ui/
    ├─ ERRE パイプライン DSL?  → erre/
    └─ Pydantic スキーマ定義?  → schemas.py に追記 (ファイルは作らない)
```

## 依存ライブラリ追加の基準

新しいライブラリを `uv add` する前に全項目確認:

- [ ] 既存の依存で代替できないか?
- [ ] ライセンスは Apache-2.0 / MIT / BSD と互換か? (**GPL は本体に入れない**)
- [ ] メンテナンスが活発か? (直近 6 ヶ月以内にリリースがあるか)
- [ ] セキュリティ脆弱性はないか?
- [ ] 予算ゼロに抵触しないか? (有料 SaaS の必須依存は不可)

## チェックリスト

- [ ] 新しいファイルが正しいレイヤー (`inference/`, `memory/` 等) に置かれているか
- [ ] インポートが依存方向に違反していないか (`grep` で確認)
- [ ] `schemas.py` から他の src モジュールを import していないか
- [ ] `ui/` から `inference/` や `memory/` を直接 import していないか
- [ ] GPL ライブラリが `src/erre_sandbox/` に入っていないか
- [ ] クラウド LLM API が必須依存になっていないか
- [ ] 新しい依存のライセンスが Apache-2.0/MIT/BSD と互換か

## 補足資料

- `decision-tree.md` — 「どのモジュールに書くべきか」の判断フロー詳細版

## 関連する他の Skill

- `python-standards` — インポート順序・相対 vs 絶対インポートのルール
- `implementation-workflow` — Step B (既存パターン調査) でこの Skill を参照
- `llm-inference` — inference/ 内のモデル設定と VRAM 管理
- `persona-erre` — ペルソナ YAML 設計と ERRE モード定義
- `godot-gdscript` — Godot シーン・GDScript のコーディング規約と WebSocket 通信
- `blender-pipeline` — Blender アセットパイプラインの GPL 分離の具体的手順

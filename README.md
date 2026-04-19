# ERRE-Sandbox

[日本語](#日本語) | [English](#english)

## English

ERRE-Sandbox is a research platform that re-implements the cognitive habits
of historical thinkers (Aristotle, Kant, Nietzsche, Rikyū, Dōgen, …) as
locally-hosted LLM agents inhabiting a shared 3D world. The system is
designed around two principles: **deliberate inefficiency** and **embodied
return**, used as first-class primitives to observe emergent intellectual
behavior.

### Status — MVP (v0.1.1-m2, 2026-04-20)

The functional MVP is complete: a **1-Kant walker** now boots via
`uv run erre-sandbox`, connects to local Ollama (`qwen3:8b` +
`nomic-embed-text`), runs a 10-second cognition cycle on a 30 Hz physics
tick, writes episodic memories to sqlite-vec, and streams its state to a
Godot 4.6 viewer over WebSocket.

- Demo recording: [evidence/godot-walking-20260420-003400.mp4](.steering/20260419-m2-functional-closure/evidence/godot-walking-20260420-003400.mp4)
  (515 KB, Kant avatar walking peripatos ↔ study)
- Full acceptance evidence for MASTER-PLAN §4.4: [acceptance-evidence.md](.steering/20260419-m2-functional-closure/acceptance-evidence.md)
- Release tags: `v0.1.0-m2` (contract-layer closeout) / `v0.1.1-m2` (MVP functional closeout)

Next milestone: **M4** — 3-agent expansion (Nietzsche / Rikyū) + reflection + semantic memory.

### Key components

- **Python 3.11 core** (`src/erre_sandbox/`): schemas, inference adapters
  (SGLang / Ollama), memory (sqlite-vec), CoALA-inspired cognition cycle,
  world tick loop.
- **Godot 4.4 frontend** (`godot_project/`): 3D visualization, rendered over
  a WebSocket bridge.
- **Personas** (`personas/*.yaml`): per-thinker habits, ERRE-mode
  sampling overrides, public-domain source references.

### Getting started

```bash
uv sync
uv run ruff check
uv run mypy src
uv run pytest
```

### Layout

See `docs/repository-structure.md` for the authoritative layout and
`docs/architecture.md` for the end-to-end data flow.

### License

Dual-licensed under **Apache-2.0 OR MIT** at the user's choice. See
`LICENSE`, `LICENSE-MIT`, and `NOTICE`. Any Blender-side integration lives
in a separately-packaged GPL-3.0 project to prevent license contamination.

---

## 日本語

ERRE-Sandbox は歴史的偉人 (アリストテレス、カント、ニーチェ、利休、道元ほか)
の認知習慣を、ローカル LLM で駆動される自律エージェント群として 3D 空間に
再実装する研究プラットフォームです。「意図的非効率性」と「身体的回帰」を
設計プリミティブとして、知的創発を観察します。

### 現在の状態 — MVP 完了 (v0.1.1-m2, 2026-04-20)

機能的 MVP 達成: `uv run erre-sandbox` で orchestrator を起動すると、
ローカル Ollama (`qwen3:8b` + `nomic-embed-text`) と接続、30 Hz 物理 tick +
10 秒 cognition サイクルで 1 体のカントが peripatos ↔ study を周遊し、
episodic memory を sqlite-vec に書き出し、WebSocket で Godot 4.6 ビューアに
状態を流し込みます。

- デモ録画: [evidence/godot-walking-20260420-003400.mp4](.steering/20260419-m2-functional-closure/evidence/godot-walking-20260420-003400.mp4)
  (515 KB、カント avatar が peripatos ↔ study を周遊する様子)
- MASTER-PLAN §4.4 の検収 evidence 全件: [acceptance-evidence.md](.steering/20260419-m2-functional-closure/acceptance-evidence.md)
- リリースタグ: `v0.1.0-m2` (contract layer 閉鎖) / `v0.1.1-m2` (MVP 機能完了)

次マイルストン: **M4** — 3 体拡張 (ニーチェ / 利休) + reflection + semantic memory。

### 主要コンポーネント

- **Python 3.11 コア** (`src/erre_sandbox/`): スキーマ、推論アダプタ
  (SGLang / Ollama)、記憶 (sqlite-vec)、CoALA 準拠認知サイクル、
  ワールド tick ループ。
- **Godot 4.4 フロントエンド** (`godot_project/`): 3D 可視化。WebSocket
  経由で Python 側と疎結合。
- **ペルソナ** (`personas/*.yaml`): 偉人ごとの認知習慣、ERRE モードの
  サンプリングオーバーライド、パブリックドメイン史料への参照。

### 開発の始め方

```bash
uv sync
uv run ruff check
uv run mypy src
uv run pytest
```

### ディレクトリ構成

正典は `docs/repository-structure.md`、全体のデータフローは
`docs/architecture.md` を参照してください。

### ライセンス

**Apache-2.0 OR MIT** のデュアルライセンス。利用者が選択できます。
`LICENSE` / `LICENSE-MIT` / `NOTICE` を参照。Blender 連携は GPL-3.0 の
別パッケージに完全分離することで、本体のライセンス汚染を防いでいます。

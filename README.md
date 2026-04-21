# ERRE-Sandbox

[日本語](#日本語) | [English](#english)

## English

ERRE-Sandbox is a research platform that re-implements the cognitive habits
of historical thinkers (Aristotle, Kant, Nietzsche, Rikyū, Dōgen, …) as
locally-hosted LLM agents inhabiting a shared 3D world. The system is
designed around two principles: **deliberate inefficiency** and **embodied
return**, used as first-class primitives to observe emergent intellectual
behavior.

### Status — M5 complete (v0.3.0-m5, 2026-04-21)

Three-agent society now ships with an event-driven ERRE-mode FSM,
LLM-generated multi-turn dialogs, and fully rendered zone visuals.
**Kant / Nietzsche / Rikyū** boot via
`uv run erre-sandbox --personas kant,nietzsche,rikyu`, each running a
10-second cognition cycle on top of a 30 Hz physics tick, reflecting
episodic memory into semantic memory (sqlite-vec, `origin_reflection_id`),
transitioning ERRE mode through `DefaultERREModePolicy` (zone change /
fatigue / shuhari hooks with live `SamplingDelta` application), exchanging
LLM-generated `dialog_turn` envelopes (`OllamaDialogTurnGenerator`,
`num_predict=120` / `think=False` / 160-char cap / Japanese unified output)
through the gateway (`schema_version=0.3.0-m5`, per-agent `?subscribe=`
routing), and streaming to a Godot 4.6 viewer that renders humanoid
avatars with ERRE mode tint, readable dialog bubbles, and four zone
scenes (`base_terrain` / `peripatos` / `chashitsu` / `zazen`).

- M5 live acceptance (7 items, all PASS on G-GEAR RTX 5060 Ti 16 GB):
  [.steering/20260421-m5-acceptance-live/acceptance.md](.steering/20260421-m5-acceptance-live/acceptance.md)
- M5 3-avatar MacBook recording: `.steering/20260421-m5-acceptance-live/evidence/recordings/erre-sandbox_demo.v3.mp4`
- M4 3-avatar 60 s Godot recording: `.steering/20260420-m4-acceptance-live/evidence/godot-3avatar-20260420-1625.mp4`
- M2 MVP demo (1-Kant walker): [.steering/20260419-m2-functional-closure/evidence/godot-walking-20260420-003400.mp4](.steering/20260419-m2-functional-closure/evidence/godot-walking-20260420-003400.mp4)
- Release tags: `v0.1.0-m2` (contract freeze) / `v0.1.1-m2` (1-agent MVP) / `v0.2.0-m4` (3-agent reflection + dialog) / `v0.3.0-m5` (ERRE FSM + LLM dialog + zone visuals)

Next milestone: **M6** — navmesh-based intra-zone pathing, preferred-zone
movement policies, additional personas (dogen / aristotle / thoreau, …),
and the remaining zone scenes (`agora` / `garden` / `study`).

### Key components

- **Python 3.11 core** (`src/erre_sandbox/`): schemas, inference adapters
  (SGLang / Ollama), memory (sqlite-vec + semantic layer), CoALA-inspired
  cognition cycle with `Reflector`, world tick loop, in-memory dialog
  scheduler with proximity-based auto-fire.
- **Godot 4.4 frontend** (`godot_project/`): 3D visualization, rendered over
  a WebSocket bridge.
- **Personas** (`personas/*.yaml`): per-thinker habits, ERRE-mode
  sampling overrides, public-domain source references. Current set:
  `kant.yaml`, `nietzsche.yaml`, `rikyu.yaml`.

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

### 現在の状態 — M5 完了 (v0.3.0-m5, 2026-04-21)

3 体エージェント社会に event-driven ERRE モード FSM / LLM 生成マルチターン
対話 / zone ビジュアルが揃いました。`uv run erre-sandbox --personas kant,nietzsche,rikyu`
で起動するとカント / ニーチェ / 利休がそれぞれ 30 Hz 物理 tick + 10 秒
cognition サイクルで動き、episodic memory を `Reflector` 経由で semantic
memory に蒸留 (sqlite-vec、`origin_reflection_id` 付き)、zone 変化・疲労・
守破離イベントで `DefaultERREModePolicy` が ERRE モードを遷移させ同時に
`SamplingDelta` を live 適用、`OllamaDialogTurnGenerator` が multi-turn
`dialog_turn` を LLM 生成 (`num_predict=120` / `think=False` / 160 char cap /
日本語統一出力) して gateway 経由で交換 (`schema_version=0.3.0-m5`、
per-agent `?subscribe=` routing)、WebSocket で Godot 4.6 ビューアに流し込み
humanoid avatar + ERRE mode tint + 読める dialog bubble + 4 zone シーン
(`base_terrain` / `peripatos` / `chashitsu` / `zazen`) で描画されます。

- M5 live 検収 (7 項目すべて PASS、G-GEAR RTX 5060 Ti 16 GB 実機):
  [.steering/20260421-m5-acceptance-live/acceptance.md](.steering/20260421-m5-acceptance-live/acceptance.md)
- M5 3 体 MacBook 録画: `.steering/20260421-m5-acceptance-live/evidence/recordings/erre-sandbox_demo.v3.mp4`
- M4 3-avatar 60 秒 Godot 録画: `.steering/20260420-m4-acceptance-live/evidence/godot-3avatar-20260420-1625.mp4`
- M2 MVP デモ (1 体カント): [.steering/20260419-m2-functional-closure/evidence/godot-walking-20260420-003400.mp4](.steering/20260419-m2-functional-closure/evidence/godot-walking-20260420-003400.mp4)
- リリースタグ: `v0.1.0-m2` (contract 凍結) / `v0.1.1-m2` (1 体 MVP) / `v0.2.0-m4` (3 体 reflection + dialog) / `v0.3.0-m5` (ERRE FSM + LLM dialog + zone visuals)

次マイルストン: **M6** — zone 内 navmesh パス生成、preferred_zone 移動ポリシー、
追加ペルソナ (dogen / aristotle / thoreau ほか)、残り zone シーン
(`agora` / `garden` / `study`) の実装。

### 主要コンポーネント

- **Python 3.11 コア** (`src/erre_sandbox/`): スキーマ、推論アダプタ
  (SGLang / Ollama)、記憶 (sqlite-vec + semantic layer)、`Reflector` を
  組み込んだ CoALA 準拠認知サイクル、ワールド tick ループ、proximity
  ベースの in-memory dialog scheduler。
- **Godot 4.4 フロントエンド** (`godot_project/`): 3D 可視化。WebSocket
  経由で Python 側と疎結合。
- **ペルソナ** (`personas/*.yaml`): 偉人ごとの認知習慣、ERRE モードの
  サンプリングオーバーライド、パブリックドメイン史料への参照。現行:
  `kant.yaml`, `nietzsche.yaml`, `rikyu.yaml`。

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

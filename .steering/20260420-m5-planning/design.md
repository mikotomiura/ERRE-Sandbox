# 設計 — M5 (ERRE mode FSM + dialog_turn LLM 生成 両輪)

採用案: **hybrid** (Contract-First 水平分解 + LLM Spike 先行)
比較過程: `design-v1.md` (初回案 A) → `design-comparison.md` (A/B/hybrid 比較) → 本ファイル

## 実装アプローチ

M4 で実証済の Contract-First 水平分解を M5 の 3 新軸 (Mode / Dialog / Visuals) に
再適用する。ただし schema freeze の前に、dialog_turn プロンプト品質の不確実性を
実機 LLM spike で経験的に解消してから contract 決定に反映する。

### 3 新軸

| Axis | 責務 | 主な層 |
|---|---|---|
| **M** (Mode) | 静的 `_ZONE_TO_DEFAULT_ERRE_MODE` を event-driven FSM に置換、sampling override を live で反映 | schemas / world / cognition / inference |
| **D** (Dialog) | dialog_initiate 後に LLM で turn を生成、record + emit + close 判定まで完走 | inference / cognition / integration/dialog / gateway |
| **V** (Visuals) | ERRE mode 視覚化 + dialog bubble を 30Hz 描画、`dialog_turn_received` consumer 実装 | godot_project/scripts & scenes |

### 依存グラフ

```
[m5-llm-spike]  (半日, throwaway, 知見のみ commit)
    │
    ▼
[m5-contracts-freeze]  (schema 0.3.0-m5, 0.5-1 日)
    │
    ├────────────┬──────────────┬──────────────┬──────────────┐
    ▼            ▼              ▼              ▼              ▼
m5-erre-     m5-erre-       m5-dialog-     m5-godot-      (並列 4 本)
mode-fsm     sampling-      turn-          zone-
             override-live  generator      visuals
    │                          │
    ▼                          │
m5-world-                      │
zone-triggers                  │
    │                          │
    └────────┬─────────────────┘
             ▼
[m5-orchestrator-integration]  (feature flag + wiring, 1 日)
             ▼
[m5-acceptance-live]  (7 項目 PASS, 0.5 日)
```

**Critical Path**: spike → contracts → erre-mode-fsm → world-zone-triggers →
orchestrator → acceptance ≒ **4-6 日** (spike 含む、並列 4 本が圧迫しない)。

## 変更対象

### 新規作成するファイル

- `src/erre_sandbox/erre/__init__.py` — パッケージ export
- `src/erre_sandbox/erre/fsm.py` — `ERREModeTransitionPolicy` 実装、event-driven 遷移
- `src/erre_sandbox/erre/sampling_table.py` — persona-erre Skill §ルール 2 の delta dict 化
- `src/erre_sandbox/integration/dialog_turn.py` — `DialogTurnGenerator` 実装
- `godot_project/scenes/zones/Chashitsu.tscn` — 茶室 zone (plane + 色違い material、MVP)
- `godot_project/scenes/zones/Zazen.tscn` — 座禅 zone (同上)
- `tests/test_erre/test_fsm.py` — 8 mode 全遷移 unit
- `tests/test_inference/test_sampling_table.py` — clamp 境界
- `tests/test_integration/test_dialog_turn.py` — initiate → N turn → close
- `tests/test_godot_chashitsu.py` / `tests/test_godot_zazen.py` — Godot fixture-gated

### 修正するファイル

- `src/erre_sandbox/schemas.py` — `SCHEMA_VERSION="0.3.0-m5"`、new field + Protocol 追加
- `src/erre_sandbox/integration/dialog.py` — scheduler に `should_take_turn` / `turn_index_of` 追加
- `src/erre_sandbox/cognition/prompting.py` — `build_dialog_system_prompt` / `build_dialog_user_prompt`
- `src/erre_sandbox/world/tick.py` — zone change 検出 → FSM hook
- `src/erre_sandbox/world/zones.py` — 境界 hysteresis (必要なら)
- `src/erre_sandbox/bootstrap.py` — FSM + TurnGenerator wiring
- `src/erre_sandbox/__main__.py` — feature flag 3 種
- `fixtures/control_envelope/*` — golden schema 再生成
- `tests/schema_golden/*` — golden JSON 更新
- `conftest.py` — `agent_state_factory` で `dialog_turn_budget` default
- `godot_project/scripts/AgentController.gd` — `set_erre_mode`, `show_dialog_bubble` 追加
- `godot_project/scripts/AgentManager.gd` — `EnvelopeRouter.dialog_turn_received` connect
- `godot_project/scenes/agents/AgentAvatar.tscn` — DialogBubble Label3D 追加
- `godot_project/scenes/MainScene.tscn` — zone node 追加のみ

## Schema 0.3.0-m5 追加内容

```python
SCHEMA_VERSION: Final[str] = "0.3.0-m5"

# §4 Cognitive に追加
class Cognitive(BaseModel):
    ...
    dialog_turn_budget: int = Field(
        default=6, ge=0,
        description="Remaining turns before the agent auto-closes its dialog.",
    )

# §7 DialogTurnMsg に追加
class DialogTurnMsg(_EnvelopeBase):
    kind: Literal["dialog_turn"] = "dialog_turn"
    dialog_id: str
    speaker_id: str
    addressee_id: str
    utterance: str
    turn_index: int = Field(..., ge=0)   # 新規

# §7 DialogCloseMsg.reason literal 拡張
class DialogCloseMsg(_EnvelopeBase):
    ...
    reason: Literal["completed", "interrupted", "timeout", "exhausted"]  # "exhausted" 追加

# §7.5 Protocol (interface-only、実装は後続 sub-task)
class ERREModeTransitionPolicy(Protocol):
    def next_mode(
        self, *,
        current: ERREModeName,
        zone: Zone,
        observations: Sequence[Observation],
        tick: int,
    ) -> ERREModeName | None: ...

class DialogTurnGenerator(Protocol):
    async def generate_turn(
        self, *,
        dialog_id: str,
        speaker_state: AgentState,
        speaker_persona: PersonaSpec,
        addressee_state: AgentState,
        transcript: Sequence[DialogTurnMsg],
        world_tick: int,
    ) -> DialogTurnMsg | None: ...
```

既存 fixture は `schema_version` のみ 0.3.0-m5 に replace (他 field は optional default 付き
なので wire 互換)。golden JSON は schema re-gen で更新。

## LLM プロンプト設計方針

spike で確定すべき 4 項目 → freeze で使用:

1. **max_tokens / utterance 長**: 160 chars hard cap (Reflector の `_MAX_SUMMARY_CHARS=500` と同じ truncate パターン、num_predict=80 を Ollama options に設定)
2. **停止語彙**: stage direction / JSON wrapping / names の混入を避ける stop tokens
3. **温度帯**: persona.default + ERRE delta、spike で 3 pair × 3 mode で subjective 評価
4. **turn_index 上限**: `dialog_turn_budget=6` を default、超過時 `reason="exhausted"` で close

**System prompt 構造** (RadixAttention 最適化のため persona block を先頭):
```
<_COMMON_PREFIX>
<persona block (既存 build_system_prompt の流用)>
<state tail>

You are now engaged in a dialog with <addressee.display_name>, another
historical figure in the same zone. Respond as a single utterance in your
own voice, <= 80 Japanese chars or 160 Latin chars. Do NOT include names,
quotation marks, stage directions, or JSON wrapping. Return ONLY the
utterance text.
```

**User prompt**:
```
Dialog so far (oldest → newest, <= 6 turns):
[a_kant_001] <turn 0 utterance>
[a_rikyu_001] <turn 1 utterance>
...

Current ERRE mode: <mode>. Zone: <zone>.
Your turn. Respond in one utterance.
```

**言語**: Kant=英、Rikyū=日、Nietzsche=独英混 (persona YAML の `display_name` +
traits 注入で自然に出る、M4 で実証済)。混合対話では各 agent の出力言語は自身のペルソナに従う。

**close 条件**: (1) `turn_index >= 6` → `reason="exhausted"`、(2) 既存 TIMEOUT_TICKS=6、
(3) 既存 interrupt。LLM が停止語彙を出しても reason は "exhausted" に正規化 (幻覚回避)。

## Godot 視覚化の実装粒度

- **bubble**: **Label3D + billboard** (既存 SpeechBubble 同パターン)、speaker 色枠で相手を示す、
  Tween fade in/out。AnimationPlayer は M6 へ deferral、CanvasLayer は採用しない
  (3D 位置情報を失うため)
- **ERRE mode tint**: `material.albedo_color` を mode ごとに色替え:
  - PERIPATETIC=淡黄 / CHASHITSU=淡緑 / ZAZEN=淡青 / DEEP_WORK=白 / SHALLOW=灰 /
    SHU_KATA=淡茶 / HA_DEVIATE=淡橙 / RI_CREATE=淡紫
- **zone scene**: MVP は plane + 色違い material (Chashitsu=木目色、Zazen=石畳色)
  で形だけ追加。詳細なライティングや装飾は M6 以降

## 既存パターンとの整合性

- `m4-contracts-freeze` の schema バージョン管理パターンを踏襲
- `Reflector.maybe_reflect` (`cognition/reflection.py:190`) を `DialogTurnGenerator` の
  LLM call + OllamaUnavailableError graceful fallback の手本として利用
- `compose_sampling()` (`inference/sampling.py:64`) を `ERREModeTransitionPolicy` 経由の
  delta 適用点として流用
- `build_system_prompt` / `build_user_prompt` (`cognition/prompting.py`) を dialog 用
  ビルダーの兄弟として配置
- `attach_dialog_scheduler` (`bootstrap.py`) を TurnGenerator wiring に拡張
- Godot `EnvelopeRouter.gd:26 dialog_turn_received` signal を既存のまま consumer 追加
- `test_godot_peripatos.py` パターンを `test_godot_chashitsu.py` / `test_godot_zazen.py` に複製

## テスト戦略

- **単体**: `test_erre/test_fsm.py` (zone entry / fatigue / manual / shuhari)、
  `test_inference/test_sampling_table.py` (全 8 mode delta、clamp 境界)
- **統合**: `test_integration/test_dialog_turn.py` (mocked LLM で initiate → 4 turn →
  exhausted close、deterministic RNG)、`test_bootstrap.py` 拡張 (FSM + generator wiring smoke)
- **回帰**: `uv run pytest -q` 全体で既存 525 test に 0 failures
- **live (G-GEAR + MacBook)**: acceptance 7 項目の evidence 収集

## Live Acceptance (7 項目、M4 同形式)

| # | 項目 | PASS 基準 | evidence |
|---|---|---|---|
| 1 | `/health` | `schema_version=0.3.0-m5` + HTTP 200 | `gateway-health-*.json` |
| 2 | 3-agent walking 60s | 各 agent の `agent_update` + `move` (M4 同等以上) | `cognition-ticks-*.log` |
| 3 | ERRE mode FSM | peripatos → chashitsu 遷移で `ERREModeShiftEvent` 発火 + `AgentState.erre.name` 更新 + 次 LLM call の temperature が delta 分変化 | `erre-transitions-*.log`, `sampling-trace-*.log` |
| 4 | dialog_turn LLM 生成 | peripatos で initiate 後 N≥3 turn が 60s 以内に LLM から生成 + `turn_index` 単調増加 + close reason が timeout/exhausted | `dialog-trace-*.log` |
| 5 | Godot dialog bubble | MacBook で `dialog_turn_received` 受信 → avatar 頭上に bubble 表示、30Hz 維持 | `godot-dialog-*.mp4` |
| 6 | Godot ERRE mode tint | mode 切替時に avatar material 色変化が目視可能 | `godot-mode-tint-*.mp4` |
| 7 | Reflection 回帰なし | M4 の reflection + semantic_memory が継続動作 (各 agent に row + origin_reflection_id 非 NULL) | `semantic-memory-dump-*.txt` |

PASS 後、main merge → `v0.3.0-m5` タグをユーザー確認の上で付与。

## 影響範囲

- **コード**: `src/erre_sandbox/` 配下で 新規 3 モジュール + 既存 7 ファイル修正
- **schema**: `0.2.0-m4` → `0.3.0-m5` (minor bump、additive、wire 互換)
- **DB**: 既存 `semantic_memory` テーブルは無変更 (M4 の `origin_reflection_id` 継続)。
  dialog history は M4 と同じく transient (memory 非永続、schema 変更なし)
- **Godot project**: 新規 zone 2 シーン + MainScene の node 追加 + 2 script の consumer 追加
- **テスト**: 新規 5 test ファイル、既存 conftest.py と fixture の default 更新
- **CI**: 既存 `uv sync --frozen → ruff → pytest` ワークフローを維持 (追加 dependency なし)

## ロールバック計画

- 各 sub-task は独立 PR で main に merge、段階的 revert 可
- 実行時 feature flag で M4 相当の挙動に戻せる:
  - `--disable-erre-fsm` → static zone map のまま
  - `--disable-dialog-turn` → initiate + timeout close のみ
  - `--disable-mode-sampling` → persona YAML の default sampling のみ
- schema は `0.3.0-m5` のまま (新 field は default 付き optional、flag OFF でも wire 互換)
- `v0.3.0-m5` タグは acceptance 全 PASS 確認後、ユーザー確認を経て付与
- 緊急時は `git revert` で sub-task merge をひっくり返す選択肢を残す

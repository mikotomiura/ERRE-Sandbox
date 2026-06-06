# M10-0 — Prompt Ordering Contract（`prompt-ordering-contract.md`）

> **WP7** / M10-0 PR-4 doc 成果物（markdown 仕様、no code）。
> **Source**: 実装 `src/erre_sandbox/cognition/prompting.py`（現行 main の prompt 組み立て）。
> **Status**: CONTRACT（M10-0 で freeze。順序変更は本 contract の改訂を要する）。

---

## §0. 目的

LLM prompt の **section 順序を契約として固定**する。順序は SGLang RadixAttention（M7+）の
**KV prefix cache 再利用**に対して load-bearing であり、共有 prefix を壊す並べ替えは cache hit 率を
破壊する。この contract は WP6 cache benchmark framework（prompt prefix hash + system/user token split +
KV hit proxy + TTFT p50/p95）が計測する**対象の規約**である。

⚠ WP6 cache benchmark（A5）自体は別 PR（`tasklist.md` PR-5）へ defer。本 doc は計測対象の **順序契約**のみを固定する。

---

## §1. 正準 ordering（実装 = `cognition/prompting.py`）

### system prompt（`build_system_prompt`、`"\n\n".join`）

| 順位 | section | 関数 | 変動性 | cache 上の役割 |
|---|---|---|---|---|
| 1 | `_COMMON_PREFIX` | `_COMMON_PREFIX`（module const） | **全 agent / 全 tick で不変** | **先頭固定**。persona 横断で KV cache 共有（RadixAttention） |
| 2 | persona block | `_format_persona_block` | persona ごと一定（tick 不変） | persona 単位の共有 prefix |
| 3 | state tail | `_format_state_tail` | **tick ごと変動**（zone / ERRE mode / physical / cognitive） | 末尾に置き、可変部を prefix から隔離 |

### user prompt（`build_user_prompt`）

| 順位 | section | 変動性 |
|---|---|---|
| 1 | `Recent observations:` + observation lines | tick ごと変動 |
| 2 | `Relevant memories:` + memory bullet list（strength 降順） | tick ごと変動 |
| 3 | `Held world-model entries:` + bounded top-K（M10-B、individual layer **on のみ**、salience 降順）。各行は `axis` と `key` を**別フィールド**で提示（`- axis=<axis> key=<key> value=±x.xx conf=x.xx`）し、結合 `[axis/key]` label は使わない（提示を権威 `visible_entry_citations` の bare (axis,key) contract と整合させ、hint の axis-prefix mismatch の**構造的誘因を除去**する＝STATE_B not_displayed 契約 fix、`20260606-hint-stateB-notdisplayed-adr`。LLM 実挙動の改善は GPU Gate 1 で別途検証）。**M10-C**: update channel on の時 各 entry 末尾に `cite=<belief id,...>`（per-entry 上限 2、`visible_entry_citations` と同一の表示集合） | tick / 個体ごと変動。flag off では **section ごと不在** |
| 4 | `RESPONSE_SCHEMA_HINT`（off）/ `RESPONSE_SCHEMA_HINT_WITH_UPDATE`（**M10-C** update channel on、`world_model_update_hint` フィールド追加） | 末尾固定。flag に応じ 2 値 |

⚠ M10-B（`feature/m10-b-swm-synthesis-prompt-injection`）で順位 3 を追加。individual layer が
**off の場合は section が一切出力されず**、M10-0 baseline と **byte 一致**（既存 caller と
`cache_benchmark:_build_case` を含む）。

⚠ **M10-C**（`feature/m10-c-world-model-update-hint`）で write-back channel を追加（`build_user_prompt`
の keyword `world_model_update_enabled`、individual layer **on のみ True**）。on の時だけ
(i) 順位 3 の Held entries に belief `cite=` を表示、(ii) 順位 4 を `RESPONSE_SCHEMA_HINT_WITH_UPDATE`
に差し替える。**off（default、既存 caller 全て）は byte 一致** = M10-B/M10-0 baseline と同一（案 A、
DA-M10C-3）。cited 検証の露出元は **Held entry に表示した belief id**（entry-local）であり、
**`format_memories` は変更しない**（recalled memory id は SWM 更新の権限根拠にしない。handoff の
「format_memories が memory-id 出力」要件は Codex HIGH-2 で supersede）。SYSTEM prompt（順位 1–3、
`_COMMON_PREFIX` / persona block / state tail）は M10-B/M10-C とも **byte 不変**（Individual state は
USER 側のみ）。

---

## §2. 契約条項（freeze）

1. **`_COMMON_PREFIX` は system prompt の先頭に置く**。前段に可変 token を差し込まない
   （prefix が agent ごとに分岐すると cache 共有が消失）。
2. **可変性の昇順で並べる**: 不変（共有 prefix）→ persona 単位 → tick 単位。これにより
   最長共有 prefix が確保される。
3. **user prompt 末尾は `RESPONSE_SCHEMA_HINT`（不変）**。observation/memory（可変）を schema hint の
   後ろに置かない。
4. `_COMMON_PREFIX` / persona block / `RESPONSE_SCHEMA_HINT` の **文面変更は cache 全 invalidation** を
   招くため、変更時は本 contract を改訂し、WP6 benchmark で TTFT / KV hit proxy の回帰を確認する（PR-5）。
5. ⚠ M10-0 individuation の `metrics.individuation` egress とは無関係（prompt は training/inference 経路、
   contamination contract は別系）。
6. **（M10-B）Individual layer state は USER prompt 側のみ**。`Held world-model entries` section は
   `Relevant memories` の直後・`RESPONSE_SCHEMA_HINT` の前に置き、SYSTEM prompt（共有 prefix）には
   一切混ぜない（RadixAttention 共有 prefix を persona 単位で保護）。off では section 不在 = byte 不変。
   `cache-benchmark` の `<persona>+swm` flag-on case が「SYSTEM byte 一致 + USER token 増分 ≤ 200」を回帰計測する。
7. **（M10-C）write-back channel も USER prompt 側のみ**。`world_model_update_enabled` on で
   (i) Held entries に belief `cite=`（per-entry ≤ 2）、(ii) 末尾を `RESPONSE_SCHEMA_HINT_WITH_UPDATE`
   に差し替える。両者とも SYSTEM prompt を 1 byte も変えない（cache prefix 保護）。**off（Held entry
   不在の base path）は byte 一致**（案 A、DA-M10C-3）。`<persona>+swm` case は M10-C で update channel
   on を表現し、現状 USER token 増分 **= +197（≤ 200）**、SYSTEM byte / prefix_hash は base case と一致
   （`--check` 回帰）。⚠ STATE_B not_displayed 契約 fix（`20260606-hint-stateB-notdisplayed-adr` /
   `20260607-hint-render-contract-alignment`）で Held entry render を `[axis/key]` 連結から
   `axis= key=` 別フィールドへ変更し、schema 指示を「shown entry の axis=/key= を完全一致コピー
   （prefix・combine 禁止）」へ明確化。これに伴い USER 増分が +191 → +197 に変化（ME-9 authority・
   `visible_entry_citations` の bare keying・cited⊆displayed は不変、提示のみ契約整合）。LLM の hint は
   candidate にすぎず、Python（`apply_world_model_update_hint`）が cited ⊆ 表示 belief id を検証してからのみ
   value を bounded nudge する（authority）。

---

## §3. M10-0 における status

- 順序契約は **freeze**（本 doc）。
- 計測（WP6 cache benchmark / A5）は **別 PR へ defer**（`tasklist.md` PR-5）。M10-0 close は WP6 完了後。

---

## 関連

- 実装: `src/erre_sandbox/cognition/prompting.py`
- `src/erre_sandbox/training/prompt_builder.py`（training-side prompt、別系）
- WP6 cache benchmark = PR-5（A5、本 contract の計測手段）

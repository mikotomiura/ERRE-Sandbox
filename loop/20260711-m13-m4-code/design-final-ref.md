# M4 impl-design ADR — HOW（Blender/Godot 技術契約）— design-final（SSOT）

> status: **FROZEN（2026-07-11、G-GEAR、user 裁定 ratify「FROZEN 承認（このまま）」）**。
> Codex Verdict=Adopt-with-changes（HIGH-1/2/3 は FROZEN 前反映済 §1.3/§3.4/§4、MEDIUM×4 §3.3/§5/§6、
> LOW×2 §1.3/§9、codex-review.md verbatim）。
> construction であって measurement でない。doc-only・非 spend・R-budget=0 不変。
> 正典パターン = scoping（PR #73 FROZEN）→【impl-design（本 ADR）】→ 実コード（Loop）。
> /reimagine 採用 = ハイブリッド（v2 spine + v1 段階移行 graft、design-comparison.md、user 裁定
> 2026-07-11）。本 ADR は **HOW（技術契約）まで**（実コード・sealed run・実 spend は一切なし）。

## §0. 前提（scoping FROZEN 継承、覆さない）

環境=geometry nodes / avatar=primitive / 消費=offline committed-golden 決定的再生 / 全景=dev-only
wrapper / replay role split（motion=`ecl_trace.jsonl`、speech·animation=`envelope_stream.jsonl`）/
配置権威=`contracts.geometry.ZONE_CENTERS`（SSOT）。この選定は再交渉しない（HOW を詰める）。

**決定性の中核方針（本 ADR の背骨、/reimagine 産物）**: 決定性 witness を **raw .glb byte
cross-machine 一致にしない**。geometry を seed-free 純関数に縛り、**量子化した witness**（.glb=構造
フィンガープリント、placement=canonical-JSONL 列）で担保する。handoff.py の landed 規律
（`CANONICAL_FLOAT_DECIMALS=6` で libm ULP drift 吸収、cross-platform byte 一致を WSL 実測）を
そのまま移植する。

---

## §1. geometry nodes ノードグラフ設計（HOW-1）

### §1.1 seed-free 決定的パラメトリック（binding）

各 zone の geometry nodes ツリーは **固定パラメータの純関数**とする。

- **禁止ノード**: `Distribute Points on Faces`（内部 random seed）、seed 未固定の `Random Value`、
  時間/フレーム依存入力。→ これらは cross-machine で頂点順序・座標を非決定化する。
- **許可**: 決定的プリミティブ（`Mesh Grid` / `Cube` / `Cylinder` / `Mesh Line`）、`Instance on
  Points`（点源は Grid/Mesh Line）、`Transform` / `Set Position`（`index`・固定数式駆動）、
  `Realize Instances`。植生/prop の "散らし" は Random でなく **index 駆動の決定的格子**で表現する。
- **理由**: geometry が固定パラメータの純関数なら、同一機/同一 Blender version で byte 一致
  （chashitsu idempotency 同型）、cross-machine 差は libm ULP に限局し §4 の構造 fp が吸収する。

### §1.2 段階移行（全面書換しない、v1 graft）

- **既存 `export_chashitsu.py` の primitive builder を「テンプレ」として残す**。geometry-nodes zone は
  zone ごとに増設し、各 `<zone>_v1.glb` が land するまで既存手書き .tscn primitive を fallback
  として残す（既存 `Chashitsu.tscn` の「.glb present なら supersede」コメントと整合）。
- chashitsu は本 spike で geometry-nodes 化しても、しなくてもよい（段階移行の裁量、issue 見積りで
  決める）。**「geometry nodes 化」は zone コンテンツ生成の適所拡張であって、chashitsu の bpy.ops
  primitive を即全廃する意味ではない**。

### §1.3 決定性契約（AC1 の witness = 二層、raw byte を cross-machine witness にしない）

1. **同一機 byte idempotency（開発者側、Blender 必須）**: `export_<zone>.py` を再走すると .glb が
   byte 一致（chashitsu と同型）。run.sh / 手順に記録（CI は Blender を持たないので CI gate にしない）。
2. **cross-machine 構造フィンガープリント（CI 側、Blender 不要）**: GPL 側 export script が
   `<zone>_v1.fingerprint.json` sidecar を canonical（handoff と同じ 6 桁量子化 + sort_keys +
   compact + allow_nan=False）で emit。内容 = `{mesh_count, total_vertex_count, bbox:{min:[x,y,z],
   max:[x,y,z]}, materials:[sorted names]}`。**純 Python（非 GPL、bpy 非依存）の GLB-JSON パーサ**が
   committed `.glb` の glTF-JSON chunk（accessor.count・accessor.min/max=POSITION bbox・material
   名）を読み、fp を再計算 → committed fingerprint と byte 一致を assert。
   - glTF は POSITION accessor の min/max を JSON header に持つので、**binary buffer を decode せず**
     bbox を取れる（軽量・純関数）。
   - 量子化ゆえ cross-machine ULP drift を吸収（raw .glb byte 比較の壁を回避、honest）。

   **HIGH-1 反映（Codex [FACT]）— accessor min/max は mesh-local bounds であって asset/world bbox
   でない**: glTF node は TRS/matrix transform を持てるので、accessor bounds を bbox witness にするには
   **export 契約で「全 mesh node の transform = identity（modifier + object transform を bake 済み、
   `export_apply=True` かつ object 原点正規化）」を binding にし、パーサは非 identity node transform を
   検出したら fail-closed**（エラーで停止、silent 通過禁止）。これで accessor-local bbox = asset bbox が
   保証される（zone 内容は §2 の通り原点中心・root は Godot .tscn 側で ZONE_CENTERS 配置ゆえ .glb 内は
   identity で自然）。fingerprint に per-node transform を含める代替もあるが、identity 強制の方が単純で
   fail-closed。

   **HIGH-2 反映（Codex）— pure JSON-header witness は圧縮/外部供給 geometry を禁止し fail-closed**:
   export 契約で `KHR_draco_mesh_compression` / `EXT_meshopt_compression` / external buffer URI /
   POSITION accessor without concrete bufferView（sparse-only）を **禁止**（GLB は自己完結ゆえ external
   buffer は元々不使用）。パーサはこれらの extension/external 参照を検出したら fail-closed（JSON header
   の min/max だけでは actual geometry witness にならない場合を silent に通さない）。

> **over-read guard**: 構造 fp は「見た目が同一」を保証しない（頂点数同一でも配置違いは検出漏れ）。
> bbox + material 名 + 頂点数の 3 点で緩和し、**fp は再現性 witness であって visual quality の
> metric/verdict でない**（floor/verdict/scorer/閾値/family comparison/aggregate metric に接続しない、
> Codex LOW-1、construction）。

---

## §2. .glb 粒度と BaseTerrain 合成（HOW-2）

- **粒度 = zone 単位 .glb・静的**（scoping 判断3 確定）。各 `<zone>_v1.glb` は **local content を
  原点 (0,0,0) 中心**に格納（建築 / prop / zone 局所 ground patch）。既存 `Chashitsu.tscn` が
  ローカル 30×30 Ground + Building を原点付近に置き root を 33.33,0,-33.33 に transform する現行構造と
  完全整合。
- **BaseTerrain = 共有 100 m 接地面を別に維持**（既存 `godot_project/scenes/zones/BaseTerrain.tscn`
  の `PlaneMesh.size`、`WORLD_SIZE_M=100` と sync）。zone .glb は full ground を含めない（z-fighting
  回避、二重接地防止）。BaseTerrain の .glb 化は不要（既存 primitive で足りる、defer 裁量）。
- **配置 = Godot 側 .tscn root transform = `ZONE_CENTERS[zone]`**（avatar でなく環境の配置に zone 中心を
  使う。avatar は §3 の通り絶対 trace 座標で動く）。
- **命名・配置**: staging = `erre-sandbox-blender/exports/<zone>_v1.glb`（git-ignored、chashitsu 先例）、
  Godot 消費 = `godot_project/assets/environment/<zone>_v1.glb`（committed data）+
  `<zone>_v1.fingerprint.json`（committed、§1.3）。zone ∈ {study, peripatos, chashitsu, agora, garden}。

---

## §3. dev viewer 具体 + replay role split 実装契約（HOW-3）

### §3.1 新規ファイル（EclReplayPlayer.gd 無改変 = 判断4 遵守）

- `godot_project/scripts/dev/SocietyReplayViewer.gd`（新規、dev-only）。
- `godot_project/scenes/dev/SocietyReplayScene.tscn`（新規、dev-only 全景 wrapper）。
- **production `MainScene.tscn` / WS graph（WorldManager/WebSocketClient/EnvelopeRouter/
  AgentManager）は無改変・非接触**。`EclReplayPlayer.gd`（envelope-only headless print）も無改変
  （別責務、判断4）。dev/README.md ルール（production は dev/ を import しない、boot path 分離）踏襲。

### §3.2 全景 = dev-only wrapper（既存 zone .tscn を read-only 参照して合成）

`SocietyReplayScene.tscn` は既存 `scenes/zones/*.tscn`（5 zone）+ `BaseTerrain.tscn` を **instance で
合成**（read-only 参照、zone .tscn は改変しない）+ N 体の primitive avatar（既存 `AgentAvatar.tscn`
系）を order_slot 順に配置。production MainScene とは別 boot path（dev/README.md 規約）。

### §3.3 replay role split（MEDIUM-2、誤実装防止の binding 実装契約）

- **motion/position 権威 = `ecl_trace.jsonl`**: 各 avatar（order_slot）を trace row の
  `(physics_tick_index, order_slot)` 系列の絶対座標 `(x, y, z)` + `yaw` に配置/補間。20 physics tick を
  時系列再生（interactive）または列 dump（headless）。**envelope_stream の move は「動機の記録」ゆえ
  位置権威にしない**（EclReplayPlayer が envelope の move を print するのと役割が異なる）。
- **speech/animation 駆動 = `envelope_stream.jsonl`**: `(order_slot, agent_tick, seq)` 順で speech
  ラベル（最小テキスト、リッチバブルは defer）/ animation 名を発火。agent_tick（cognition、4 tick）
  解像度。ENVELOPE_STREAM_KINDS = (speech, move, animation) のうち move は位置に使わず、speech/
  animation のみ駆動に使う。
- 座標規約 = manifest `coordinate_convention`（Y-up / XZ / m / yaw=atan2(dz,dx)）を assume。
- **MEDIUM-1 反映（Codex [FACT]）— `order_slot` は一意 key でなく安定順序の一部**: motion（physics_tick
  clock domain、20 tick）と speech·anim（agent_tick clock domain、4 tick）は **join しない**。両者は
  同一 avatar（`order_slot` で識別）に render されるが、**別 clock domain の独立系列**として再生する
  （motion は physics_tick で位置補間、speech·anim は agent_tick で発火）。`order_slot` 単独 join で
  両系列を突合する実装は禁止（誤実装防止）。

### §3.4 二モード

- **headless（CI 検証用）**: `SocietyReplayViewer.gd` を `--headless` で走らせ、per-(physics_tick_index,
  order_slot) の解決済み avatar transform + 発火 envelope kind 列を `--dump=<path>` に出力。§4 の byte
  比較に使う。scene 実体化は最小（transform 解決のみ、描画不要）。
  - **HIGH-3 反映（Codex）— Godot runtime float→str を cross-machine byte witness にしない**: motion
    権威 = `ecl_trace.jsonl`（既に 6 桁量子化 committed）ゆえ、viewer は位置を **再計算せず committed
    trace 値を pass-through で echo** する（Godot 側で float を再フォーマットしない = platform 差・
    丸め実装差を持ち込まない）。dump の canonical 化・byte 比較は **Python 側**（§4 の test が Godot
    dump を読み handoff の canonicalizer で正規化してから比較）で行い、Godot の string 表現そのものを
    witness byte にしない。envelope kind 列も committed envelope_stream の値を echo。
- **interactive（開発者観察用）**: `SocietyReplayScene.tscn` を通常起動し時系列再生。dev-only。

---

## §4. 決定的再生の検証法（HOW-4、AC2/AC3 の機械検証）

- **committed 期待列**: `tests/fixtures/m2_society_golden/expected_placement.jsonl`（新規、committed）=
  golden の `ecl_trace.jsonl` から導出した per-(physics_tick_index, order_slot) 解決位置列 +
  envelope_stream 由来の per-(order_slot, agent_tick, seq) 発火 kind 列を、handoff と同じ canonical
  規律（6 桁量子化 + sort_keys + compact）で serialize したもの。
- **検証 test**（Python、`tests/test_integration/test_m4_society_replay.py`、既存 `_godot_helpers.py`
  経由で Godot headless 起動）:
  - **AC2（causal wiring）**: viewer を headless 起動（`--manifest --trace --stream --dump=<tmp>`）→
    dump が「N avatar を order_slot 順に、trace 通りの位置で」解決していることを、期待列と byte 比較で
    確認。live WS/LLM 非接触（offline golden のみ）。
  - **AC3（再現性）**: 同一 golden で 2 回起動 → 2 dump が byte 一致（決定性）。かつ committed
    `expected_placement.jsonl` と byte 一致。
- **cross-platform（HIGH-3 反映）**: witness は **Godot runtime の float→str でなく committed trace 値の
  pass-through echo**（§3.4）。Python test が Godot dump を読み handoff の canonicalizer（6 桁量子化 +
  sort_keys + compact）で正規化してから `expected_placement.jsonl` と byte 比較する。placement 期待列は
  ecl_trace（既に量子化 committed）+ ZONE_CENTERS 由来の canonical 値から Python 側生成。platform-parity
  は Loop の pre-push で WSL byte 一致検証（feedback_golden_crossplatform_float_drift 踏襲）。
- **AC1**: §1.3 の fingerprint test（`tests/test_integration/test_m4_zone_glb_fingerprint.py`、
  committed .glb を純パーサで読み fp 再計算 → committed fingerprint と一致）。

> これらの checksum/列比較は **再現性 witness であって metric/floor/verdict でない**（handoff の
> `ecl_trace_checksum` と同格、construction）。

---

## §5. AC5 measurement-zero の機械 guard（HOW-5）

M2 `test_m2_society_spend_guard.py`（landed 先例）を踏襲/拡張。M4 の全新規コード
（`.py` export scripts + `.gd` viewer + 新規 test）が measurement 器官を **import も emit もしない**
ことを機械保証。

- **denylist（scoping HIGH-1 全幅、狭めない）**: `evidence`（evidence/**）, `spdm`, `runningness`,
  `floor`, `landscape`, `verdict`（`cli/*_verdict.py` 含む）, `scorer`, `bank_scorer` / `bank*.py`,
  `D_*` 統計, および aggregation surface（numpy/pandas/scipy/statistics/`Counter`/`groupby`/`math.log`）。
- **`.py`（Blender export scripts）**: `ast` guard（executable AST のみ走査、docstring/comment 非走査 =
  Codex HIGH-1 の自己 trip 回避）。import denylist + identifier ban + aggregation ban。**bpy import は
  許可**（GPL 側の正当依存、denylist 対象外。GPL 境界は §8 の SPDX guard で別管理）。
- **MEDIUM-2 反映（Codex）— denylist を guard 種別で分ける（false positive 抑制）**: `floor` /
  `divergence` / `verdict` / `scorer` は M2 同型の **identifier substring ban**（executable AST の
  Name/arg/def 位置）。`D_*`（統計）/ `bank*` / `landscape` / `evidence` / `spdm` / `runningness` は
  **import module path segment + CLI/artifact filename** を主軸に guard（identifier 全面禁止は
  `bank`/`landscape`/`D_` が普通の変数名と衝突し false positive が強いため）。`_measurement_guard.py`
  の hole-1/2/3（ImportFrom(erre_sandbox)→evidence / dynamic import 文字列 / dict-key·filename exact）を
  踏襲。
- **`.gd`（GDScript）**: Python `ast` で parse 不可 → **正規表現/テキスト scan**（denylist token の
  import/identifier/dict-key/`.json`·`.jsonl` filename としての非在）。M2 の handoff-scan と同型の
  belt-and-suspenders。
- **emit guard**: dump/artifact の dict key・出力ファイル名に denylist token が現れないこと
  （`_measurement_guard.py` の hole-3 = key/filename exact scan 相当）。
- **self-scan**: guard test 自身も denylist import を持たない（M2 の I6-G5 同型）。
- **負 fixture**: denylist import/identifier を仕込んだ合成 src が必ず trip すること（実効性 witness、
  M2 の `test_m2_society_*_catches_*` 同型）。
- 配置 = `tests/test_integration/test_m4_viz_measurement_guard.py`（+ 共有 guard helper が要れば
  `tests/test_integration/_m4_measurement_guard.py`、leading-underscore で非収集、`_measurement_guard.py`
  慣習踏襲）。

---

## §6. 配置権威座標 snapshot（HOW-6、live WS 非引込）

- **`scripts/export_zone_layout.py`（新規、純 Python・bpy 非依存・非 GPL）**: `contracts.geometry.
  ZONE_CENTERS` を import し `godot_project/assets/environment/zone_layout.json`（committed、canonical）
  を生成。内容 = `{zone: [x, y, z]}`（5 zone）+ `world_size_m`。live WS（`WorldLayoutMsg`）は引き込まない
  （scoping MEDIUM-1 FACT: WorldLayoutMsg は live 由来ゆえ offline spike 非対象）。
  **MEDIUM-4 反映（Codex）**: この tool は **`erre-sandbox-blender/` 配下に置かない**（非 GPL・
  ライセンス境界を曖昧にしない）。`scripts/`（本体 Apache/MIT 側）に配置。§1.3 の純 GLB-JSON パーサも
  同様に `tests/`（非 GPL）に置く。
- **drift 閉じ test**（`tests/test_integration/test_m4_zone_layout.py`）:
  - `zone_layout.json` の各値 == `ZONE_CENTERS`（純 Python assert）。
  - 各 `scenes/zones/<Zone>.tscn` の root transform 平行移動成分 == `ZONE_CENTERS[zone]`
    （.tscn を text parse）。
  - **MEDIUM-3 反映（Codex）— tolerance でなく 6 桁 canonical exact 比較**: `contracts.geometry` の
    `_ZONE_OFFSET = WORLD_SIZE_M/3 = 33.3333…` に対し既存 `.tscn` は手書き `33.33` で **実際に drift
    している**（`33.330000` ≠ `33.333333`）。drift test は 6 桁 canonical exact 比較にし、この既存
    divergence を検出 → **実装 Loop で .tscn 値を authority（33.333333…）へ是正**することを AC に含める
    （tolerance で silent に通さない。これが MEDIUM-1 FACT の drift を実際に閉じる意味）。
- avatar は §3.3 の通り **絶対 trace 座標**で動くので zone_layout を必要としない。zone_layout は
  **環境（.tscn root / .glb 配置）の権威 mirror** としてのみ機能。

---

## §7. Zazen 非 zone 扱い（HOW-7）

- `Zone` enum = 正確に 5（study/peripatos/chashitsu/agora/garden）。**Zazen は ERRE mode であって
  Zone でない**（`Zazen.tscn` は mode scene）。
- AC4「5 zone 網羅」は Zazen を **含めない**。geometry-nodes build 対象・`zone_layout.json`・
  fingerprint 対象は 5 zone のみ。dev viewer の zone 合成も 5 zone のみ（Zazen.tscn は参照しない）。
- test（§6 の zone_layout test）は enum 5 zone を厳密列挙し Zazen を含まないことを assert。

---

## §8. SPDX GPL header（HOW-8、Codex LOW-2 是正）

- **新規 Blender script（`erre-sandbox-blender/scripts/export_<zone>.py` 等）に SPDX header 必須**
  （blender-pipeline ルール3）:
  ```python
  # SPDX-License-Identifier: GPL-3.0-or-later
  # Copyright (c) 2026 ERRE-Sandbox Contributors
  #
  # This file is part of erre-sandbox-blender.
  # It is distributed under the terms of the GNU General Public License v3.0 or later.
  ```
- **既存 `export_chashitsu.py` の header 欠を是正**（docstring に License 記載はあるが SPDX 行が無い）→
  SPDX 行を追記（Loop で実施、本 ADR は方針確定）。
- **test**（`tests/test_architecture/` 追加 or 既存拡張）: `erre-sandbox-blender/**/*.py` の全ファイルが
  先頭付近に `SPDX-License-Identifier: GPL-3.0-or-later` を持つことを assert。純テキスト scan（bpy 不要）。
- `scripts/export_zone_layout.py` は **非 GPL**（bpy 非依存、本体 Apache/MIT）ゆえ SPDX GPL header
  対象外。zone .glb / fingerprint.json / zone_layout.json は **データ**（GPL コードでない）ゆえ Godot
  消費可。

---

## §9. issue 分割の見通し（HOW-9、後続 Loop の縦スライス目安）

本 ADR は HOW 確定まで。実装 Loop 着手時に issue-slicing で確定するが、目安（**LOW-2 反映（Codex）=
AC5/GPL boundary guard を最初の issue に置く**、その後 tooling → Blender exporter → Godot viewer →
golden 消費の順）:

| issue | 内容 | 主 AC |
|---|---|---|
| I1 | AC5 measurement-zero guard（.py AST + .gd text scan、§5）+ GPL/SPDX boundary guard（§8）+ 負 fixture + self-scan | AC5 |
| I2 | `export_zone_layout.py`（純、非 GPL）+ `zone_layout.json` + drift（6桁 exact、.tscn 是正含む）/Zazen-除外 test（§6/§7）+ 純 GLB-JSON パーサ helper（§1.3） | AC4 下地 |
| I3 | geometry-nodes zone build script（seed-free、§1、node transform=identity + 圧縮禁止 fail-closed）+ fingerprint sidecar（§1.3）+ SPDX header（§8、chashitsu 是正含む）+ 同一機 idempotency 手順 | AC1 |
| I4 | 残り zone の geometry-nodes build（段階移行、§1.2）+ committed .glb + fingerprint test（§4 AC1） | AC1 |
| I5 | `SocietyReplayViewer.gd` + `SocietyReplayScene.tscn`（新規、role split §3.3、trace pass-through echo §3.4、EclReplayPlayer 無改変） | AC2 |
| I6 | headless placement dump 検証 test（§4、Python canonicalizer 比較）+ 5 zone load boolean test | AC2/AC3/AC4 |

縦スライス（各 issue = 独立検証可能な 1 PR 候補）。横切り（層だけ分割）禁止。

---

## §10. acceptance（scoping §6 を実装レベルの test 名/検証手順へ、causal wiring/boolean/再現性 のみ）

| AC | 実装レベル検証（test 名 / 手順） | 種別 |
|---|---|---|
| **AC1 決定的 build** | (a) 同一機 idempotency = `export_<zone>.py` 再走 .glb byte 一致（開発者手順、Blender 必須、run.sh 記録）。(b) `test_m4_zone_glb_fingerprint.py` = committed .glb を純 GLB-JSON パーサで読み fp 再計算 → committed `<zone>_v1.fingerprint.json` と byte 一致（CI、Blender 不要） | 再現性 |
| **AC2 causal wiring** | `test_m4_society_replay.py::test_headless_dump_matches_expected` = viewer headless dump が N avatar を order_slot 順・trace 通り位置に解決（offline、live WS/LLM 非接触）、`expected_placement.jsonl` と byte 一致 | causal wiring |
| **AC3 再現性** | `test_m4_society_replay.py::test_dump_deterministic` = 同一 golden 2 回起動で dump byte 一致 | boolean 決定性 |
| **AC4 boolean 網羅** | `test_m4_zone_layout.py`（5 zone 厳密列挙 + Zazen 除外）+ `test_m4_society_replay.py` の scene 合成が 5 zone .tscn を load（各 .glb 対応） | boolean |
| **AC5 measurement 面ゼロ** | `test_m4_viz_measurement_guard.py` = 新規 .py（AST）+ .gd（text）が denylist 全幅を import/emit しない + 負 fixture trip + self-scan | boolean（非在） |

**いずれも floor/verdict でない**。「2 avatar が golden 通り move」は construction 現象で measured
convergence/divergence でない（golden は 2 体とも全 peripatos = fixture 性質、over-read 厳禁）。

---

## §11. 不可侵（binding）

- **construction ≠ measurement**: floor/verdict/scorer/landscape/D_*/divergence を作らない・測らない。
  R-budget=0 不変、holding 不可侵、over-read 禁止、firing⇔detectability 混同禁止、5 機序分離継承。
  fingerprint/placement checksum は再現性 witness であって metric でない。
- **GPL 分離**: bpy は `erre-sandbox-blender/`（GPL-3.0、SPDX header）のみ。`src/erre_sandbox/` に
  `import bpy` 絶対禁止。.glb/fingerprint/zone_layout はデータ（Godot 消費可）。Godot は GDScript のみ
  （`godot_project/` に Python 禁止）。クラウド LLM 必須依存禁止（offline、LLM 非接触）。
- **read-only**: golden fixtures / handoff.py / EclReplayPlayer.gd / society.py / organ / 凍結
  apparatus（evidence/**・bank*.py・committed golden）は read-only。改変が要れば superseding ADR。
  既存 zone .tscn は dev viewer から read-only 参照（改変しない、.glb land 時の supersede は Loop 裁量で
  別途）。
- **reasoning-trace door 保全のまま touch しない**。

## §12. 次工程

M4 実コード（Loop Engineering、§9 の issue 縦スライス → worktree `/loop-issue` → 各 attempt
test-runner→loop-watchdog → 全 issue 緑 + 統合 CI 緑 → TASK-POST `/cross-review` → merge）。
Layer2（ミラー・シム）mirror-sim impl-design ADR は別トラック併存（順序は user 裁定）。
</content>

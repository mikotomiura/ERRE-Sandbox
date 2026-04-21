# Blockers / 持ち越し事項 — m5-godot-zone-visuals

## LOW 優先度の持ち越し (code review)

### L-1: AgentController._body の BodyTinter 型キャスト

- **指摘元**: code-reviewer sub-agent MEDIUM #1 (2026-04-20)
- **現状**: `@onready var _body: MeshInstance3D = $Body` のまま、
  `apply_erre_mode` 内で `_body.has_method("apply_mode")` 経由で委譲
- **理想**: `_body as BodyTinter` でキャストして型安全に
- **持ち越し理由**: T16 judgement 4 の class_name cross-ref parse-order 問題に
  触れるリスクあり (BodyTinter を class_name で参照するケース)。preload で const
  bind してキャストする方法もあるが、現状 has_method ガード経由で動作しており
  実害なし
- **次アクション**: M6 で animation 等の新規 BodyTinter API が増えた時に再検討

### L-2: DialogBubble.show_for の duration_s < 0.6 エッジケース

- **指摘元**: code-reviewer sub-agent MEDIUM #2 (2026-04-20)
- **現状**: `sustain_s = max(duration_s - FADE_IN_SEC - FADE_OUT_SEC, 0.0)` で、
  `duration_s=0.1` を渡すと sustain=0 だが fade_in+fade_out で合計 0.6s 再生
- **理想**: `FADE_IN_SEC` / `FADE_OUT_SEC` も duration に比例スケール、または
  呼び出し元で `clamp(duration_s, 0.6, ...)`
- **持ち越し理由**: 現状 `DEFAULT_DIALOG_DURATION_SEC=4.0` 固定で呼ばれており、
  duration_s < 0.6 の経路は存在しない
- **次アクション**: Python 側から可変 duration を渡す経路ができた時点で修正

### L-3: tests/test_godot_{dialog_bubble,mode_tint}.py の harness_result fixture 重複

- **指摘元**: code-reviewer sub-agent LOW (2026-04-20)
- **現状**: 2 テストファイルで同一の `@pytest.fixture(scope="module")` を重複定義
- **理想**: `tests/conftest.py` に共有 fixture として抽出
- **持ち越し理由**: test_godot_peripatos.py / test_godot_ws_client.py でも
  ほぼ同一の fixture があり、リファクタは本 PR scope を超える
- **次アクション**: M6 以降で Godot fixture-gated test が 5 本以上になった時に
  conftest.py へ集約

### L-4: Chashitsu.tscn / Zazen.tscn の material に resource_local_to_scene 未設定

- **指摘元**: code-reviewer sub-agent LOW (2026-04-20)
- **現状**: 各 zone の material は scene 内で共有 (local_to_scene=false)
- **理想**: 将来 zone 材質を runtime で変える (例: 時刻ライティング) なら
  `resource_local_to_scene=true` に
- **持ち越し理由**: 現状 zone 材質を runtime で変更する要件なし
- **次アクション**: zone の dynamic tinting 要件が発生した時点で対応

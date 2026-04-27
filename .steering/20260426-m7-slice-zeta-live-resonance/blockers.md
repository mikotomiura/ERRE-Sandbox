# Blockers — M7 Slice ζ

## 既知ブロッカー

### B1. ε が code review 中
- **状態**: PR-ε-2 が本ブランチ `feat/m7-epoch-phase-filter` で進行 (commit
  14aa61f)。merge 待ち。
- **影響**: ζ で `SCHEMA_VERSION` を bump する場合、ε の 0.8.0-m7e の上に
  0.9.0-m7z にするため ε merge を待つ必要がある。Godot 側完結の変更
  (day/night, selector, i18n) は ε と独立に進められる。
- **対処**: ζ-A (schema bump あり) は ε merge 待ち、ζ-B (Godot 完結) は並行
  可能。Plan で 2-PR に分割するのが妥当。

### B2. Blender .glb pipeline 未到達 (A2/A3 関連)
- **状態**: `erre-sandbox-blender/` リポジトリは存在するが
  `godot_project/assets/environment/` に .glb 未配備。primitive のままで
  「のっぺり感」「茶室の薄さ」「建物の小ささ」は根本解消できない。
- **影響**: A2/A3 はアセット制作タスクで時間が読めない。ζ で抱えると PR が
  肥り、live 体感の改善が遅延する。
- **対処**: ζ scope 外 → 別タスク `world-asset-blender-pipeline` に切り出し。
  ζ では A1 (day/night) でのっぺり感の **照明側緩和** だけ拾う。

### B3. context 使用率
- **状態**: Plan mode に入る前に context 30% rule で `/clear` 判定が必要。
- **対処**: 偵察 + steering scaffold 完了時点で usage 確認、超過なら
  `/clear` → 次セッションで Plan ファイル + design-final.md を Read。

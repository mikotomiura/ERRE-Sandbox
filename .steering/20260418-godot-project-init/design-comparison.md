# T15 godot-project-init — 設計案比較

## v1（初回案）の要旨

MASTER-PLAN §7.3 の指示「Godot 4.4 起動 → .gitignore → project.godot コミット」に
忠実に従った **最小ブートアブル** 設計。MainScene は Label3D 1 つだけ、
GDScript なし、`scenes/zones/` や `scripts/` は作らない、自動検証なし。
T16 / T17 着手時にディレクトリや GDScript を追加する前提。

## v2（再生成案）の要旨

T15 を **Scaffolded Handoff** と再定義。patterns.md §2 の MainScene ノード階層
(ZoneManager / AgentManager / WebSocketClient / UILayer) を空スタブで事前配置し、
repository-structure.md のディレクトリを README で意図明示しながらミラー。
`WorldManager.gd` を boot 用最小実装として配置、`tests/test_godot_project.py` で
Godot headless boot を自動検証 (未 install 環境は skip)。NOTICE に Godot
ランタイム言及を追記、`patterns.md` の 4.4 表記を 4.4-4.6 に緩和して
setup-macbook decisions の予告同期を実施。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| 設計思想 | 最小ブートアブル (指示に忠実) | Scaffolded Handoff (T16/T17 即着手可能な足場) |
| MainScene 階層 | Node3D + Label3D のみ | patterns.md §2 完全準拠 (Environment/Camera/ZoneManager/AgentManager/WebSocketClient/UILayer) |
| ディレクトリ | `scenes/` のみ | `scenes/` + `scenes/zones/` + `scripts/` + `assets/` 全ミラー + 各 README |
| GDScript | なし | `WorldManager.gd` 最小実装 |
| 自動検証 | 手動のみ | pytest 3 件 (ファイル存在 / Python 混入禁止 / headless boot) |
| architecture-rules 強制 | なし | `test_godot_project_contains_no_python` で自動強制 |
| NOTICE 追記 | なし | Godot ランタイムの言及 (MIT, user-installed) |
| Skill 同期 | 見送り | `patterns.md` の 4.4 → 4.4-4.6 表記緩和 (setup-macbook decisions の予告履行) |
| 空 dir 問題 | 未解決 | README.md (git-tracked で intent 明示) |
| icon.svg | "手書き暫定 or pure white" と design に書くのみ | 具体的実装 (単色 + "E" 3 本線) |
| 変更規模 | ~4 ファイル | ~12 ファイル |
| T16/T17 の pick-up コスト | 高 (dir 追加・階層設計・boot ログ手動確認が毎回) | 低 (ノードに .gd attach + zone を instance するだけ) |
| drift 検知 | なし | Godot 更新や構造破壊を pytest で即検知 |
| repository-structure.md ミラー | 不完全 | 完全 |

## 評価（各案の長所・短所）

### v1 の長所
- 実装コストが最小 (4 ファイル程度)
- MASTER-PLAN §7.3 の指示に 1:1 で追従できる
- 余計な決断を避けてシンプル
- 後続タスクで柔軟に構造を決められる (fresh start)

### v1 の短所
- **T16 着手時にディレクトリ・ノード階層・GDScript 骨格を全て追加する必要**:
  patterns.md §2 が既に定義している階層なのに T15 で空にしておくのは
  「知識の消失」
- 自動検証がないため、将来 Godot のプロジェクト破壊や Python 混入に気付けない
- `scenes/zones/` / `scripts/` / `assets/` が未作成のため、T17 / M4 着手時に
  「どこに置くか」を毎回判断する必要 (repository-structure.md と実体の乖離)
- 空 dir 問題を回避するため README か .gitkeep が結局必要になる
- setup-macbook decisions が予告した「patterns.md の 4.6 対応」が棚上げ

### v2 の長所
- **requirement.md §ゴールの「T16 godot-ws-client が WebSocketClient.gd を
  すぐ書き足せる配置」要求に直接応答**: 既存 WebSocketClient ノードに .gd を
  attach するだけで T16 が進む
- **自動検証**で Python 混入禁止 (architecture-rules) を CI で強制。
  これは T15 の「境界」的性質に合致
- **repository-structure.md のミラー完成**で T15 以降、実体とドキュメントの
  乖離を心配する必要がない
- **README.md 配置**により空 dir 問題と意図明示を同時解決。Godot 開発者
  (T17 / M4 / 未来の新人) が「ここに何を置くか」を即座に理解可能
- **NOTICE + patterns.md 同期**で Phase C で確立した「Skill と実装を歩調
  合わせる」精神を継続 (T06 persona-erre 同期、T07 godot-gdscript 同期と
  同じパターン)
- **T15 が 0.5d 枠に十分収まる実装量**: scaffold は軽量、boot 自動検証は
  数十行の pytest

### v2 の短所
- ファイル数が 3 倍 (4 → 12)、レビュー負荷が増える
- MainScene 階層に「空スタブ」を配置する判断が不要 if T16/T17 で別の階層を
  選ぶ可能性がある (patterns.md §2 が絶対ではない)
- 自動 boot テストが timeout (60s) を持ち、CI 時間をわずかに増やす
- icon.svg の手書きが時間コストをわずかに追加 (20 行程度なので軽微)

## 推奨案

**v2 を採用** — 理由:

1. **requirement.md §ゴール明記の「T16 がすぐ書き足せる配置」**:
   これは「ノード階層も dir も事前に用意する」と読むのが自然。v1 の空
   MainScene + `scenes/` のみという構成ではこの要求を満たせない。

2. **T15 の 0.5d 枠に scaffolded 案が十分収まる**:
   増える 8 ファイルは README / 1 GDScript / 1 pytest / NOTICE 追記 /
   patterns.md 小編集。すべて軽量で、MainScene の階層スタブは 10-20 ノード
   の配置のみ。

3. **Phase C で確立したパターンを維持**:
   T06 persona-erre / T07 godot-gdscript (kind 同期) / T08 NOTICE (CSDG 帰属) と
   同じ「実装 + Skill 同期 + ドキュメント整合」の三点セットを T15 でも保つ。
   setup-macbook decisions が予告した「patterns.md の 4.6 対応」を履行する
   タイミングとして T15 が最適。

4. **自動検証の不可逆的価値**:
   v1 で自動検証を見送ると、後から足すコストは今と同じか上回る
   (Godot 依存の pytest 配線を別 PR で追加する手間)。T15 に含めるのが最も安い。

5. **architecture-rules の機械強制**:
   「`godot_project/` に Python を置かない」は repository-structure.md §6 の
   禁止パターン。v2 の `test_godot_project_contains_no_python` は T06-T08 の
   meta-test と同じ「rule を機械で守る」精神の延長で、contract-first 派生。

6. **patterns.md §2 階層を採用するリスクは低い**:
   patterns.md は既に T05 (schemas.py のノード連動) 設計時に議論済み。
   T16/T17 で別階層にしたくなる可能性は低く、なったとしても edit コストは小さい。

**ハイブリッド不採用の理由**:
v1 の「最小ブート」精神は受け入れ条件を満たすが、v2 の「scaffolded handoff」は
それを内包している (boot はテスト 1 で確認済)。部分採用すると「どの要素を省く
か」の判断が不明瞭になる。v2 全体の方が整合性が高い。

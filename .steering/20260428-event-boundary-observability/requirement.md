# Event boundary observability — どの zone でどの reasoning が発火したか

## 背景

live 検証 issue C1+C2:
- C1 (04/21) 「イベントによる llm との連動における認知プロセスの具体化
  + イベント数の増加・改善設計」
- C2 (04/21) 「どこの箇所のフィールドでさまざまなイベントを与えているか
  などの境界線」

ζ-2 で `ReasoningTrace.persona_id` + `RelationshipBond.latest_belief_kind`
が wire され、Godot panel に reasoning が表示。しかし**どの zone・どの
affordance・どの proximity event** が trigger かは UI で未結合。
`WorldRuntime` 内では observation discriminated union が signaling 済、
Godot 側で panel に紐付ける layer のみ欠落。

## ゴール

ReasoningPanel reasoning が「どの event/zone が起点か」を 1 行で示し、
user が live で「Kant peripatetic mode → Linden-Allee zone enter event
起因」のような因果を読める。

## スコープ

### 含むもの
- `ReasoningTrace.salient_observation_ids` (or 同等) を additive で追加
- `cognition/cycle.py` で trace 生成時に observation IDs を stamp
- Godot ReasoningPanel 「気づき」セクション拡張: observation kind icon
  + zone 名 + tick
- zone 境界線 (visual marker) を Godot world に薄く重ねる試作

### 含まないもの
- evaluation layer 本体 (M10-11)
- event 数の増強 (C1 後半)
- LLM prompt 側で observation IDs を消費する変更

## 受け入れ条件

- [ ] schema bump (additive) + golden 再 bake
- [ ] 新 field の wire 互換 test
- [ ] Godot panel が observation icon + zone を表示
- [ ] live G-GEAR で 3 体 reasoning が起点 zone と紐付く
- [ ] /reimagine v1+v2 並列で採用判断記録

## 関連ドキュメント

- ζ-2 の `latest_belief_kind` パターン (additive + default=None)
- MASTER-PLAN §12 (M10-11 evaluation layer)
- `.steering/20260426-m7-slice-zeta-live-resonance/decisions.md` D2

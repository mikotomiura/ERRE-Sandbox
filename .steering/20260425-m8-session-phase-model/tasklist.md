# Tasklist — M8 Session Phase Model

> L6 D3 precondition、~0.5d 見込 (schema + Protocol + test のみ、live 不要で
> MacBook 完走可能)。開始前に **Plan mode + /reimagine 必須** (session_phase の
> 所在と遷移 API の形に複数案ありうる、特に "evaluation phase は現段階で
> 骨格だけ作るか全く入れないか" は判断どころ)。

## 準備
- [ ] L6 ADR D3 と L6 design.md §4 を Read
- [ ] `architecture-rules` / `persona-erre` / `python-standards` Skill を Read
- [ ] 現 `schemas.py` の AgentState / BootConfig 構造を調査
- [ ] `ControlEnvelope` 11 variants の変動パターンを参考に schema_version bump
      前例を調査 (`.steering/20260420-m4-contracts-freeze/` 等)

## 設計 (decisions.md に記録)
- [ ] **Phase 1**: `SessionPhase` enum を Literal で定義 (`"autonomous" |
      "q_and_a" | "evaluation"`)
- [ ] **Phase 2**: session_phase の所在を AgentState vs BootConfig で決定
      - AgentState に持てば agent 別に phase が分岐可 (柔軟だが冗長)
      - BootConfig に持てば run 全体で単一 phase (単純)
      - 推奨: BootConfig (D3 採用の "時間分離" は run 単位の分割が自然)
- [ ] **Phase 3**: 遷移 API の Protocol 定義
      - `PhaseTransitioner` Protocol (transition_to(SessionPhase) 等)
      - 許可される遷移パス: autonomous → q_and_a → evaluation のみ (逆行不可)
- [ ] **Phase 4**: Q&A epoch 中の user 発話規約
      - DialogTurnMsg.speaker_id = "researcher" を使用
      - autonomous log export は speaker_id != "researcher" で filter
      - schemas.py の PersonaId Literal に "researcher" を追加するかを決定

## 実装
- [ ] `src/erre_sandbox/schemas.py` に SessionPhase enum 追加
- [ ] session_phase フィールドを決定した所在に追加
- [ ] schema_version を bump (現 `0.2.0-m4` → 次 `0.3.0-m8` 等、
      `.steering/20260420-m4-contracts-freeze/` の前例を踏襲)
- [ ] PhaseTransitioner Protocol を `src/erre_sandbox/integration/` 等に追加
- [ ] speaker_id = "researcher" を PersonaId Literal に追加 (Phase 4 で YES 決定時)

## テスト (MacBook で完走)
- [ ] 単体: SessionPhase enum の Literal 値が 3 つ
- [ ] 単体: 遷移 API が許可パスを受理、逆行を reject
- [ ] 単体: DialogTurnMsg.speaker_id の filter (researcher 除外) が動く
- [ ] schema migration test: 旧 version の fixture が新 schema でも読める

## レビュー
- [ ] `code-reviewer` で schemas.py 追記と Protocol をレビュー
- [ ] `impact-analyzer` で schema_version bump の呼び出し側影響 (特に gateway /
      cognition / world)

## ドキュメント
- [ ] `docs/architecture.md` に session_phase の図を追加 (3 相のタイムライン)
- [ ] `docs/glossary.md` に「session phase」「2-phase methodology」を追加

## 完了処理
- [ ] `design.md` 最終化、`decisions.md` に Phase 1-4 の決定を固定
- [ ] commit → PR (`feat(schemas): M8 session phase model`)
- [ ] merge 後、L6 D3 status を「session_phase 固定、Q&A epoch interface は
      Godot 側別 spike で実装」に更新

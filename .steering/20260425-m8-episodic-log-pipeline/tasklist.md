# Tasklist — M8 Episodic Log Pipeline

> L6 D1 precondition、~1d 見込 (半日 schema/CLI、半日 measure + 記録)。
> 開始前に **Plan mode + /reimagine 必須** (CLI 契約 / schema 変更 / export 形式に
> 複数案ありうる)。

## 準備
- [ ] L6 ADR D1 (`.steering/20260424-steering-scaling-lora/decisions.md`) を Read
- [ ] `architecture-rules` / `test-standards` Skill を Read
- [ ] 現状の log schema を `src/erre_sandbox/memory/store.py` で調査
- [ ] `file-finder` で persona_id が不足している log ポイントを特定

## 実装
- [ ] 全 3 event schema に `persona_id` / `session_id` が含まれていることを確認、
      不足していれば追加 (schema version bump)
- [ ] persona-scoped count の SQL サンプル集を `docs/_queries/` 等に配置
- [ ] `erre-sandbox export-log` CLI を `src/erre_sandbox/cli/export_log.py` に追加
      - JSONL 出力
      - Parquet 出力 (`pyarrow` 依存追加、architecture-rules と整合確認)
      - `--persona` filter / `--since` date filter
- [ ] gateway / sink で 3 event が全て記録されることを e2e でスモークテスト

## テスト
- [ ] 単体: schema version が bump されていれば migration テスト
- [ ] 単体: export CLI が JSONL / Parquet 両方を書けることを確認
- [ ] 統合: 10 turn のダミー session を流し、export レコード数が一致

## 測定 (M8 baseline)
- [ ] G-GEAR で 60-90s live run を 3 本、persona 別 turn count を計測
- [ ] `log-snapshot.md` に persona 別 count + 日次推移をグラフ 1 枚 + table 1 本で記録
- [ ] M9 前提 ≥1000 turns/persona までの距離を見積、「あと何 session 必要か」を記録

## レビュー
- [ ] `code-reviewer` で schema 変更と CLI をレビュー
- [ ] `impact-analyzer` で schema version bump の呼び出し側影響を確認

## ドキュメント
- [ ] `docs/architecture.md` の memory layer セクションに export CLI を追記 (必要なら)
- [ ] `docs/glossary.md` に「episodic log pipeline」を追加

## 完了処理
- [ ] `design.md` の最終化 (実装中に発覚した差分を反映)
- [ ] `decisions.md` 作成 (schema version bump の根拠、Parquet 採用根拠等)
- [ ] commit → PR (`feat(memory): M8 episodic log pipeline`)
- [ ] merge 後、L6 D1 の status を「baseline data 収集中」に更新

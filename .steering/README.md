# .steering/

このディレクトリは Claude Code との作業記録を保管します。

## 構造

```
.steering/
├── README.md              # このファイル
├── _setup-progress.md     # 環境構築の進捗記録
├── _template/             # 新規タスク用テンプレート
│   ├── requirement.md
│   ├── design.md
│   ├── tasklist.md
│   ├── blockers.md
│   └── decisions.md
└── [YYYYMMDD]-[task-name]/   # 各タスクの作業記録
    ├── requirement.md
    ├── design.md
    ├── tasklist.md
    ├── blockers.md (任意)
    └── decisions.md (任意)
```

## 新規タスクの開始

`/start-task` コマンドを使うと、自動的にディレクトリとテンプレートが配置されます。

## ファイルの役割

- **requirement.md** — 何をするか（背景、ゴール、受け入れ条件）
- **design.md** — どうやるか（アプローチ、変更対象、テスト戦略）
- **tasklist.md** — 具体的なタスクのチェックリスト
- **blockers.md** — 詰まったポイントとその解決方法（任意）
- **decisions.md** — 重要な設計判断とその根拠（任意）

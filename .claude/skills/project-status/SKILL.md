---
name: project-status
description: >
  プロジェクトの現在の状態をリアルタイムで取得する。
  作業を始める前・コンテキストが分からなくなった時・進捗を確認したい時・
  最近の変更を把握したい時に使う。git 状態・最近のコミット・
  構築フェーズの進捗 (.steering/_setup-progress.md)・未対応 TODO・
  変更ファイル統計を一括で取得する。セッション開始時の状況把握にも使える。
context: fork
agent: Explore
allowed-tools: Bash(git *), Bash(grep *), Bash(find *), Bash(wc *), Read
---

# Project Status

このスキルは現在のプロジェクト状態を動的に取得します。

## 現在の git 状態

!`git status --short`

## 最近のコミット (10 件)

!`git log --oneline -10 2>/dev/null || echo "(no commits yet)"`

## 現在のブランチ

!`git branch --show-current`

## 構築フェーズ進捗

!`grep -E "^\- \[" .steering/_setup-progress.md 2>/dev/null | head -20 || echo "(progress file not found)"`

## 未対応 TODO の数

!`grep -r "TODO\|FIXME\|HACK\|XXX" src/ tests/ 2>/dev/null | wc -l`

## 変更ファイルの統計 (直近コミットとの差分)

!`git diff --stat HEAD 2>/dev/null || echo "(no HEAD yet)"`

## 最近変更されたファイル (24 時間以内)

!`find src/ tests/ -name "*.py" -newer .git/index -mtime -1 2>/dev/null | head -10`

## Skills ディレクトリ

!`ls .claude/skills/ 2>/dev/null || echo "(no skills yet)"`

## あなたのタスク

上記の動的データを分析し、以下を報告してください:

1. **現状サマリ** — 現在のフェーズと進捗を 1-2 行で
2. **進行中の作業** — 未コミットの変更や直近の変更ファイルから何が進んでいるか
3. **注意すべき点** — 多数の未コミット変更、TODO の偏り、進捗ファイルとの乖離など
4. **推奨される次のアクション** — 何を優先すべきか (setup フェーズであればどのコマンドを次に実行すべきか)

レポートは簡潔に。詳細は必要に応じてユーザーが追加で質問する。

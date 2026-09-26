# 実行環境

- Python 3.11、`uv.lock` 固定。追加依存なし (numpy のみ。safetensors は header を直接 parse)。
- CPU のみ。GPU・ネットワーク・モデル forward を使わない。
- Windows (`.venv/Scripts/python.exe`) / WSL2・Linux (`.venv/bin/python`) の両経路。

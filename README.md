- `merge_bms_folders.py`: 複数の置き場フォルダに散らばった本体フォルダをマージする。

# 使い方
1. BeMusicSeeker(ﾏﾝﾊｯﾀﾝｶﾞｯﾌｪさんのfork版)で各移動元ディレクトリにてリネームしておく
2. pyproject.tomlの2つのタスクにおけるフォルダを適切に修正する
3. `uv run task dryrun`で動作確認する(移動や削除は行われない)
4. `uv run task execute`で実行する

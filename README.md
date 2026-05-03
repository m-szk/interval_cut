# interval_cut

`interval_cut.py` は、指定した間隔で動画を切り出し、画面が認識できる部分でトリミングしたあと、音声にフェードイン/アウト処理を適用して出力する Python スクリプトです。
音声を瞬間的にフェードイン/アウトさせることで動画をつなげたときの「ブツノイズ」防ぎます。

## 特徴

- 動画を `time` 秒ずつ切り出し
- 切り出した区間から黒画面検出を使って有効なフレームを判定
- 有効フレーム開始位置からトリミング
- 音声にフェード処理を適用
- 一時ファイルは処理後に削除される

## 必要環境

- Python 3
- `ffmpeg`
- `ffprobe`

`ffmpeg` と `ffprobe` はシステムにインストールされている必要があります。macOS の場合は Homebrew でインストールできます。

```sh
brew install ffmpeg
```

## 使い方

```sh
python interval_cut.py <video_path> <time> <step> [-o output_dir] [-s start] [-af audio_fade_duration] [-q] [-c] [-cf concat_fade_out] [--vcodec codec] [--crf value] [--acodec codec]
```

- `video_path` : 処理する動画ファイルのパス
- `time` : 切り出す長さ（秒）
- `step` : 切り出しを開始する間隔（秒）
- `-o, --output_dir` : 出力先ディレクトリ（省略時はカレントディレクトリ）
- `-s, --start` : 処理を開始する時間（秒、省略時は0.0）
- `-af, --audio_fade_duration` : 音声フェードの持続時間（秒、省略時は0.05）
- `-q, --quiet` : ffmpegのログ出力を抑制
- `-c, --concat` : すべての出力ファイルを1つのファイルに連結
- `-cf, --concat_fade_out` : 連結した動画の最後にフェードアウトを適用（秒、省略時は0.0）
- `--vcodec` : 出力動画に使うビデオコーデック（省略時は `libx264`）
- `--crf` : ビデオの品質を決める定数レートファクタ（0-51、値が小さいほど高品質、省略時は `23`）
- `--acodec` : 出力音声に使うオーディオコーデック（省略時は `aac`）

### 例

```sh
python interval_cut.py input.mp4 10 30 -o ./output
```

上記コマンドは、`input.mp4` を 10 秒ずつ切り出し、30 秒間隔で処理を開始して `./output` に出力します。

```sh
python interval_cut.py input.mp4 10 30 -o ./output -s 60 -f 0.1 -q -c
```

上記コマンドは、`input.mp4` を 60 秒から開始し、10 秒ずつ切り出し、30 秒間隔で処理を開始して `./output` に出力します。フェード持続時間を 0.1 秒に設定し、ログを抑制し、すべての出力を1つのファイルに連結します。

## 出力ファイル

出力ファイル名は元ファイル名に開始時間を付けた形式になります。

例: `input_0000.mp4`, `input_0030.mp4` など

`-c` オプションを指定した場合、すべての出力ファイルを連結したファイルも作成されます。

例: `input_concat.mp4`

## 注意

- 指定した出力ディレクトリが存在しない場合、スクリプトはエラーで終了します。
- 元動画の形式によっては `ffmpeg` の読み込みや処理に失敗する場合があります。

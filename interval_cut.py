import argparse
import os
import sys
import subprocess
import tempfile


BLACKDETECT_FILTER = 'blackdetect=d=0.0:pic_th=0.00'
TEMP_CUT_PREFIX = ".temp.cut."
TEMP_TRIM_PREFIX = ".temp.trim."
TEMP_CONCAT_PREFIX = ".temp.concat."
DEFAULT_AUDIO_FADE_DURATION = 0.05
FFMPEG_BASE_ARGS = ['ffmpeg', '-y', '-hide_banner', '-nostats']
FFPROBE_BASE_ARGS = ['ffprobe', '-v', 'error']


def build_ffmpeg_cmd(quiet=False):
    cmd = FFMPEG_BASE_ARGS.copy()
    if quiet:
        cmd += ['-loglevel', 'error']
    return cmd


def build_ffprobe_cmd(quiet=False):
    cmd = FFPROBE_BASE_ARGS.copy()
    if quiet:
        cmd = ['ffprobe', '-hide_banner', '-v', 'error']
    return cmd


def run_cmd(cmd, error_message, capture_output=False):
    try:
        if capture_output:
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"{error_message}: {e}")
        sys.exit(1)


def cut_video(input_path, video_start, video_time, output_path, quiet=False):
    """動画を指定した間隔でカット"""
    fast_ss = max(0, float(video_start) - 3.0)
    fine_ss = float(video_start) - fast_ss
    print(f"Cutting video: {input_path} from {video_start}s to {video_start + video_time}s -> {output_path}")
    ffmpeg_cmd = build_ffmpeg_cmd(quiet) + [
        '-ss', str(fast_ss),
        '-i', input_path,
        '-ss', str(fine_ss),
        '-t', str(video_time),
        '-c', 'copy', output_path]
    run_cmd(ffmpeg_cmd, f"Error cutting video {input_path} at {video_start} seconds")
    print(f"Created: {output_path}")


def validate_frames(input_path, quiet=False):
    """動画内の画面が認識できるフレームの開始・終了時間を検出"""
    print(f"Validating frames in: {input_path}")
    # blackdetect の出力は ffmpeg のログレベルに依存するため、quiet モードでも
    # ここでは行わない。検出結果を取得できないと処理が止まるため、出力を残す。
    cmd = build_ffmpeg_cmd(False) + ['-i', input_path, '-vf', BLACKDETECT_FILTER, '-an', '-f', 'null', '-']
    result = run_cmd(cmd, f"Error validating frames in {input_path}", capture_output=True)
    for line in result.stderr.split('\n'):
        if 'black_start' in line:
            video_start = line.split('black_start:')[1].split(' ')[0]
            video_end = line.split('black_end:')[1].split(' ')[0]
            print(f"Detected valid frames: start={video_start}s, end={video_end}s")
            return float(video_start), float(video_end)
    print(f"No valid frames detected in: {input_path}")
    duration = get_video_duration(input_path, quiet=quiet)
    print(f"Using entire clip as valid frame range: 0s to {duration}s")
    return 0.0, duration


def trim_video(input_path, output_path, quiet=False, vcodec='libx264', crf=23, acodec='aac'):
    """動画をトリミング"""
    # 動画内の画面が認識できるフレームでトリミング
    video_start, _ = validate_frames(input_path, quiet=quiet)
    print(f"Trimming video: {input_path} from frame {video_start} -> {output_path}")
    ffmpeg_cmd = build_ffmpeg_cmd(quiet) + [
        '-i', input_path,
        '-vf', f"trim=start={video_start},setpts=PTS-STARTPTS",
        '-af', f"atrim=start={video_start},asetpts=PTS-STARTPTS",
        '-c:v', vcodec,
        '-crf', str(crf),
        '-c:a', acodec,
        output_path
    ]
    run_cmd(ffmpeg_cmd, f"Error trimming video {input_path}")
    print(f"Trimmed video created: {output_path}")


def apply_audio_fade(input_path, output_path, fade_duration, quiet=False, acodec='aac'):
    """オーディオにフェードイン/アウトを適用"""
    video_duration = get_video_duration(input_path, quiet=quiet)
    fade_filter = f"afade=t=in:ss=0:d={fade_duration}, afade=t=out:st={video_duration-fade_duration}:d={fade_duration}"
    print(f"Applying audio fade: input={input_path}, output={output_path}, fade_duration={fade_duration}, video_duration={video_duration}")
    print(f"Using filter: {fade_filter}")
    ffmpeg_cmd = build_ffmpeg_cmd(quiet) + ['-i', input_path, '-af', fade_filter, '-c:v', 'copy', '-c:a', acodec, output_path]
    run_cmd(ffmpeg_cmd, f"Error applying audio effects to {input_path}")
    print(f"Applied audio fade successfully: {output_path}")


def concat_videos(input_paths, output_path, quiet=False):
    print(f"Concatenating videos: {input_paths} -> {output_path}")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tf:
        for path in input_paths:
            safe_path = os.path.abspath(path).replace("'", "'\\''")
            tf.write(f"file '{safe_path}'\n")
        
        temp_list_name = tf.name
    try:
        ffmpeg_cmd = build_ffmpeg_cmd(quiet) + ['-f', 'concat', '-safe', '0', '-i', temp_list_name, '-c', 'copy', output_path]
        run_cmd(ffmpeg_cmd, f"Error concatenating videos into {output_path}")
        print(f"Concatenated video created: {output_path}")
    finally:
        if os.path.exists(temp_list_name):
            os.remove(temp_list_name)


def fade_out_video(input_path, output_path, fade_duration, quiet=False, vcodec='libx264', crf=23, acodec='aac'):
    """動画にフェードアウトを適用"""
    video_duration = get_video_duration(input_path, quiet=quiet)
    video_fade_filter = f"fade=t=out:st={video_duration-fade_duration}:d={fade_duration}"
    audio_fade_filter = f"afade=t=out:st={video_duration-fade_duration}:d={fade_duration}"
    print(f"Applying video fade out: input={input_path}, output={output_path}, fade_duration={fade_duration}, video_duration={video_duration}")
    print(f"Using filter: {video_fade_filter}")
    ffmpeg_cmd = build_ffmpeg_cmd(quiet) + [
        '-i', input_path,
        '-vf', video_fade_filter,
        '-af', audio_fade_filter,
        '-c:v', vcodec,
        '-crf', str(crf),
        '-c:a', acodec,
        output_path
    ]
    run_cmd(ffmpeg_cmd, f"Error applying video fade out to {input_path}")
    print(f"Applied video fade out successfully: {output_path}")


def get_video_duration(video_path, quiet=False):
    """動画の長さを取得"""
    print(f"Getting duration for: {video_path}")
    cmd = build_ffprobe_cmd(quiet) + ['-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
    result = run_cmd(cmd, f"Error getting video duration for {video_path}", capture_output=True)
    duration = float(result.stdout)
    print(f"Video duration: {duration}s")
    return duration


def parse_arguments():
    """コマンドライン引数を解析"""
    parser = argparse.ArgumentParser(description='Video Interval Cut')
    parser.add_argument('video_path', help='Video file path')
    parser.add_argument('time', type=float, help='Cutout time (sec)')
    parser.add_argument('step', type=float, help='Cutout interval (sec)')
    parser.add_argument('-o', '--output_dir', help='Output directory', default='.')
    parser.add_argument('-s', '--start', type=float, default=0.0, help='Start time in seconds')
    parser.add_argument('-af', '--audio_fade_duration', type=float, default=DEFAULT_AUDIO_FADE_DURATION, help='Audio fade duration in seconds')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress ffmpeg logging output')
    parser.add_argument('-c', '--concat', action='store_true', help='Concatenate all output files into a single file')
    parser.add_argument('-cf', '--concat_fade_out', type=float, default=0.0, help='Apply fade out to the end of the concatenated video')
    parser.add_argument('--vcodec', type=str, default='libx264', help='Video codec')
    parser.add_argument('--crf', type=int, default=23, help='Constant Rate Factor for video quality')
    parser.add_argument('--acodec', type=str, default='aac', help='Audio codec')
    return parser.parse_args()


def validate_output_directory(output_dir):
    """出力ディレクトリの存在を確認"""
    if not os.path.isdir(output_dir):
        print(f"Output directory does not exist: {output_dir}")
        sys.exit(1)


def generate_output_temp_filename(video_path, output_dir, start):
    """出力ファイル名を生成"""
    base_name, ext = os.path.splitext(os.path.basename(video_path))
    return (
        os.path.join(output_dir, f"{base_name}_concat{ext}"),
        os.path.join(output_dir, f"{base_name}_{int(start):04d}{ext}"),
        f"{TEMP_CUT_PREFIX}{base_name}_{int(start)}{ext}",
        f"{TEMP_TRIM_PREFIX}{base_name}_{int(start)}{ext}",
        f"{TEMP_CONCAT_PREFIX}{base_name}_concat{ext}"
    )


def interval_cut_video(args):
    """動画を指定した間隔でカット"""
    start = max(0.0, args.start)
    duration = get_video_duration(args.video_path, quiet=args.quiet)
    out_files = []
    while start < duration:
        print()
        concat_file, out_file, temp_cut_file, temp_trim_file, temp_concat_file = generate_output_temp_filename(args.video_path, args.output_dir, start)
        with tempfile.TemporaryDirectory(dir=args.output_dir) as tmp_dir:
            temp_cut_path = os.path.join(tmp_dir, temp_cut_file)
            temp_trim_path = os.path.join(tmp_dir, temp_trim_file)

            cut_video(args.video_path, start, args.time, temp_cut_path, quiet=args.quiet)
            if args.audio_fade_duration > 0:
                trim_video(temp_cut_path, temp_trim_path, quiet=args.quiet, vcodec=args.vcodec, crf=args.crf, acodec=args.acodec)
                apply_audio_fade(temp_trim_path, out_file, args.audio_fade_duration, quiet=args.quiet, acodec=args.acodec)
            else:
                trim_video(temp_cut_path, out_file, quiet=args.quiet, vcodec=args.vcodec, crf=args.crf, acodec=args.acodec)

        out_files.append(out_file)

        start += args.step

    if args.concat:
        print()
        if args.concat_fade_out > 0:
            with tempfile.TemporaryDirectory(dir=args.output_dir) as tmp_dir:
                temp_cut_path = os.path.join(tmp_dir, temp_concat_file)
                concat_videos(out_files, temp_concat_file, quiet=args.quiet)
                fade_out_video(temp_concat_file, concat_file, args.concat_fade_out, quiet=args.quiet, vcodec=args.vcodec, crf=args.crf, acodec=args.acodec)
        else:
            concat_videos(out_files, concat_file, quiet=args.quiet)


def main():
    args = parse_arguments()
    validate_output_directory(args.output_dir)
    interval_cut_video(args)

if __name__ == "__main__":
    main()
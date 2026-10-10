"""将图片和视频合成为 Live Photo，并生成 .pvt 包。

未提供图片时，用系统 ffmpeg 从视频抽取封面。指定时间时使用该时刻的帧，
并忽略同时传入的图片。
"""

from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from makelive import save_live_photo_pair_as_pvt
except ImportError:
    print("错误：未找到 makelive 库。请先运行：pip install makelive", file=sys.stderr)
    sys.exit(1)


def parse_time(value: str) -> tuple[str, float]:
    """解析封面时间。返回 (去空白后的原始字符串, 秒数)。

    接受非负秒数、MM:SS[.frac]（秒 < 60，分钟不限）和 HH:MM:SS[.frac]
    （分、秒均 < 60）。非法输入抛出 ValueError。
    """
    text = value.strip()
    if not text:
        raise ValueError("无法解析时间：时间为空")

    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return text, float(text)

    hours_minutes_seconds = re.fullmatch(r"(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if hours_minutes_seconds:
        hours = int(hours_minutes_seconds.group(1))
        minutes = int(hours_minutes_seconds.group(2))
        seconds = float(hours_minutes_seconds.group(3))
        if minutes >= 60 or seconds >= 60:
            raise ValueError(f"无法解析时间：{text}")
        return text, hours * 3600 + minutes * 60 + seconds

    minutes_seconds = re.fullmatch(r"(\d+):(\d+(?:\.\d+)?)", text)
    if minutes_seconds:
        minutes = int(minutes_seconds.group(1))
        seconds = float(minutes_seconds.group(2))
        if seconds >= 60:
            raise ValueError(f"无法解析时间：{text}")
        return text, minutes * 60 + seconds

    raise ValueError(f"无法解析时间：{text}")


def default_output_path(video: Path) -> Path:
    """未指定 -o 时，输出到视频所在目录下的同名 .pvt。"""
    return video.parent / f"{video.stem}.pvt"


def _require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print(
            "错误：未找到 ffmpeg，请先安装并确保在 PATH 中（例如 brew install ffmpeg）",
            file=sys.stderr,
        )
        sys.exit(1)
    return ffmpeg


def probe_duration(video: Path) -> float | None:
    """用 ffprobe 读取时长。缺失或无法解析时返回 None，交给抽帧结果判断。"""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return None
    if not math.isfinite(duration) or duration < 0:
        return None
    return duration


def extract_cover_frame(video: Path, dest: Path, time: str | None) -> None:
    """抽取一帧 JPEG。time 为 None 时取解码后的第一帧，不传 -ss。"""
    ffmpeg = _require_ffmpeg()
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video),
    ]
    if time is not None:
        command.extend(["-ss", time])
    command.extend(["-frames:v", "1", "-q:v", "2", "-update", "1", str(dest)])
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        print(f"错误：提取封面失败：{exc}", file=sys.stderr)
        sys.exit(1)
    produced = dest.is_file() and dest.stat().st_size > 0
    if result.returncode != 0 or not produced:
        detail = result.stderr.strip() or "未生成图片"
        print(f"错误：提取封面失败：{detail}", file=sys.stderr)
        sys.exit(1)


def _move_pvt(src: Path, dest: Path) -> Path:
    """把生成的 .pvt 目录包移动到指定路径。路径相同时直接返回。"""
    src = src.expanduser().resolve()
    dest = dest.expanduser().resolve()
    if src == dest:
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        if dest.is_dir() and not dest.is_symlink():
            shutil.rmtree(dest)
        else:
            dest.unlink()
    shutil.move(src, dest)
    return dest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="将图片和视频合成为 Live Photo，并生成 .pvt 包。未提供图片时使用视频帧作为封面"
    )
    parser.add_argument(
        "-i",
        "--image",
        help="图片文件路径（支持 .jpg / .jpeg / .heic）。省略时使用视频第一帧",
    )
    parser.add_argument(
        "-t",
        "--time",
        metavar="TIME",
        help="用作封面的视频时间点（秒数、MM:SS 或 HH:MM:SS）。指定后忽略 -i",
    )
    parser.add_argument(
        "-v",
        "--video",
        required=True,
        help="视频文件路径（必须是 .mov 格式）",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="输出的 .pvt 文件路径（可选，默认为视频同目录下的同名 .pvt）",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    video_path = Path(args.video).expanduser().resolve()
    if not video_path.exists():
        print(f"错误：视频文件不存在：{video_path}", file=sys.stderr)
        sys.exit(1)
    if video_path.suffix.lower() != ".mov":
        print("警告：视频建议使用 .mov 格式，否则可能无法被 iOS 识别", file=sys.stderr)

    dest = (
        Path(args.output).expanduser().resolve()
        if args.output
        else default_output_path(video_path)
    )

    time_text: str | None = None
    if args.time is not None:
        try:
            time_text, seconds = parse_time(args.time)
        except ValueError as exc:
            print(f"错误：{exc}", file=sys.stderr)
            sys.exit(1)
        if args.image is not None:
            print(f"警告：已指定 --time，忽略图片：{args.image}", file=sys.stderr)
        duration = probe_duration(video_path)
        if duration is not None and seconds >= duration:
            print(
                f"错误：指定时间 {time_text} 超出视频时长（{duration:.3f} 秒）",
                file=sys.stderr,
            )
            sys.exit(1)

    # makelive 的 pvt_path 是目录，包名来自图片主名。先写到临时目录，再移动到最终路径，
    # 避免在用户图片旁留下中间包，也避免移动前覆盖无关 .pvt。
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        if time_text is not None:
            cover = tmp / f"{video_path.stem}.jpg"
            extract_cover_frame(video_path, cover, time_text)
            cover_label = f"视频 {time_text} 处的帧"
        elif args.image is not None:
            cover = Path(args.image).expanduser().resolve()
            if not cover.exists():
                print(f"错误：图片文件不存在：{cover}", file=sys.stderr)
                sys.exit(1)
            if cover.suffix.lower() not in (".jpg", ".jpeg", ".heic"):
                print("警告：图片建议使用 .jpg 或 .heic 格式", file=sys.stderr)
            cover_label = str(cover)
        else:
            cover = tmp / f"{video_path.stem}.jpg"
            extract_cover_frame(video_path, cover, None)
            cover_label = "视频第一帧"

        print("正在合成 Live Photo...")
        print(f"  封面：{cover_label}")
        print(f"  视频：{video_path}")
        print(f"  输出：{dest}")

        try:
            asset_id, pvt_path = save_live_photo_pair_as_pvt(
                str(cover),
                str(video_path),
                pvt_path=str(tmp),
            )
        except Exception as exc:
            print(f"合成失败：{exc}", file=sys.stderr)
            sys.exit(1)

        try:
            final_path = _move_pvt(Path(pvt_path), dest)
        except OSError as exc:
            print(f"移动输出失败：{exc}", file=sys.stderr)
            sys.exit(1)

    print("\n✅ 合成成功！")
    print(f"Asset ID: {asset_id}")
    print(f"生成的 .pvt 包: {final_path}")
    print("\n下一步：")
    print("1. 在 Finder 中找到该 .pvt 文件")
    print("2. 右键 -> 共享 -> 隔空投送，发送到你的 iPhone")
    print("3. iPhone 接收后会自动保存为 Live Photo")


if __name__ == "__main__":
    main()

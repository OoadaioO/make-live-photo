"""将指定图片和视频合成为 Live Photo，并生成 .pvt 包。"""

import argparse
import shutil
import sys
from pathlib import Path

try:
    from makelive import save_live_photo_pair_as_pvt
except ImportError:
    print("错误：未找到 makelive 库。请先运行：pip install makelive", file=sys.stderr)
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


def main():
    parser = argparse.ArgumentParser(
        description="将图片和视频合成为 Live Photo，并生成 .pvt 包"
    )
    parser.add_argument(
        "-i", "--image",
        required=True,
        help="图片文件路径（支持 .jpg / .jpeg / .heic）"
    )
    parser.add_argument(
        "-v", "--video",
        required=True,
        help="视频文件路径（必须是 .mov 格式）"
    )
    parser.add_argument(
        "-o", "--output",
        help="输出的 .pvt 文件路径（可选，默认自动生成）"
    )
    args = parser.parse_args()

    image_path = Path(args.image).expanduser().resolve()
    video_path = Path(args.video).expanduser().resolve()

    # 检查文件是否存在
    if not image_path.exists():
        print(f"错误：图片文件不存在：{image_path}", file=sys.stderr)
        sys.exit(1)
    if not video_path.exists():
        print(f"错误：视频文件不存在：{video_path}", file=sys.stderr)
        sys.exit(1)

    # 检查扩展名
    if image_path.suffix.lower() not in (".jpg", ".jpeg", ".heic"):
        print("警告：图片建议使用 .jpg 或 .heic 格式", file=sys.stderr)
    if video_path.suffix.lower() != ".mov":
        print("警告：视频建议使用 .mov 格式，否则可能无法被 iOS 识别", file=sys.stderr)

    print("正在合成 Live Photo...")
    print(f"  图片：{image_path}")
    print(f"  视频：{video_path}")

    try:
        # 调用 makelive 的 API：合成并保存为 .pvt 包
        asset_id, pvt_path = save_live_photo_pair_as_pvt(
            str(image_path),
            str(video_path)
        )
    except Exception as e:
        print(f"合成失败：{e}", file=sys.stderr)
        sys.exit(1)

    pvt_path = Path(pvt_path)

    # .pvt 是目录包，不能用 unlink()。输出路径与生成路径相同时不要删掉刚写好的结果。
    if args.output:
        try:
            pvt_path = _move_pvt(pvt_path, Path(args.output))
        except OSError as e:
            print(f"移动输出失败：{e}", file=sys.stderr)
            sys.exit(1)

    print("\n✅ 合成成功！")
    print(f"Asset ID: {asset_id}")
    print(f"生成的 .pvt 包: {pvt_path}")
    print("\n下一步：")
    print("1. 在 Finder 中找到该 .pvt 文件")
    print("2. 右键 -> 共享 -> 隔空投送，发送到你的 iPhone")
    print("3. iPhone 接收后会自动保存为 Live Photo")


if __name__ == "__main__":
    main()

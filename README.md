# make-live-photo

把一张图片和一段视频合成为 Apple **Live Photo**，并打包成 `.pvt` 文件。

生成的 `.pvt` 包可以直接通过 **隔空投送（AirDrop）** 发送到 iPhone，接收后会自动保存为 Live Photo，非常适合把安卓手机拍的图转成 iPhone 的实况照片。

## 功能

- 将 `.jpg` / `.jpeg` / `.heic` 图片 + `.mov` 视频合成 Live Photo
- 未提供图片时，用系统 `ffmpeg` 抽取视频第一帧作为封面
- 可用 `-t` 指定时间点的帧作为封面；指定后忽略 `-i`
- 自动打包为 iOS 识别的 `.pvt` 包
- 未指定 `-o` 时，输出到视频同目录、与视频同名的 `.pvt`
- 不修改原始图片与视频（由底层依赖完成，仅对副本操作）
- 命令行一键使用

## 系统要求

- macOS（推荐 10.15 及以上）
- Python 3.9+
- 从视频抽封面时需要系统已安装的 [`ffmpeg`](https://ffmpeg.org/)（`ffprobe` 可选，用于在抽帧前检查时间是否超出时长）。只提供图片和视频时不需要 `ffmpeg`

## 安装

本项目依赖 [makelive](https://github.com/RhetTbull/makelive)。安装本包时会一并安装它。上游曾提示 `makelive` 在个别环境下用 pip 解析依赖会失败。

在克隆下来的仓库目录中安装：

```bash
pip install .
```

也可以不克隆，直接从 Git 安装：

```bash
pip install git+https://github.com/OoadaioO/make-live-photo.git
```

## 使用

### 命令行

```bash
# 使用指定图片。未传 -o 时，输出到视频同目录的 clip.pvt
make-live-photo --image photo.jpg --video clip.mov

# 不传图片：用视频第一帧做封面
make-live-photo -v clip.mov

# 用指定时间的帧做封面（秒数或时分秒）。若同时传了 -i，图片会被忽略
make-live-photo -v clip.mov -t 1.5
make-live-photo -v clip.mov -t 00:00:01.5

# 自定义输出路径（-o 是可选的，不会自动补 .pvt）
make-live-photo -i photo.heic -v video.mov -o output.pvt

# 等价入口
python -m make_live_photo -i photo.jpg -v clip.mov
```

常用选项：

| 选项 | 说明 |
| --- | --- |
| `-i, --image` | 可选：图片路径（支持 `.jpg` / `.jpeg` / `.heic`）。省略时使用视频第一帧 |
| `-t, --time` | 可选：封面时间点（秒数、`MM:SS` 或 `HH:MM:SS`）。指定后忽略 `-i` |
| `-v, --video` | **必填**：视频路径（建议 `.mov`） |
| `-o, --output` | 可选：输出的 `.pvt` 路径。默认是视频目录下与视频同名的 `.pvt`，已存在则覆盖 |

### 快速开始

```bash
make-live-photo -v clip.mov
```

## 参数说明

- **图片**：静态照片，作为 Live Photo 静止画面。可省略，此时用视频第一帧
- **时间**：`-t 1.5`、`-t 90:00` 或 `-t 00:00:01.25`。指定后不再使用 `-i`，即使图片路径不存在也不会因此失败
- **视频**：时长通常较短的 `.mov` 片段，作为 Live Photo 的动效
- **输出**：`.pvt` 是 QuickTime 的压缩包格式，内含图片 + 视频 + 用于标识为 Live Photo 的元数据（Content Identifier）。抽出的封面只放进包内，不会另存到视频旁边

> 建议图片用 `.jpg` 或 `.heic`，视频用 `.mov`，否则可能无法被 iOS 正确识别。

## 传输到 iPhone

`.pvt` 文件无法被 Windows 直接打开，最佳传输方式是 **隔空投送**：

1. 在 Finder 中打开生成的 `.pvt` 文件
2. 右键 → **共享** → **隔空投送**，发送到你的 iPhone
3. iPhone 接收后会自动保存为 Live Photo

> 若使用其他传输方式（如 AirDrop 之外）可能导致元数据丢失，建议使用隔空投送。

## 常见问题

**Q：为什么一定要用 `.mov` 格式？**
A：Live Photo 要求视频必须是 Apple 能识别的 QuickTime 格式，`.mov` 是最稳妥的选择。

**Q：不传图片时提示找不到 ffmpeg？**
A：从视频抽封面依赖系统 `PATH` 中的 `ffmpeg`，例如 `brew install ffmpeg`。只传图片和视频时不会调用它。

**Q：原始图片/视频会被修改吗？**
A：底层库（`makelive`）在打包 `.pvt` 时只操作副本，不会改动原始文件。但请自行备份以防万一。

**Q：Live Photo 能用作动态壁纸吗？**
A：可能无法作为 Live Wallpaper 使用，这通常与视频格式/时长有关。

## 底层依赖

- 系统 `ffmpeg` — 仅在需要从视频抽取封面时使用，不随包分发
- [makelive](https://github.com/RhetTbull/makelive) — 负责写入元数据并把图 + 视频打包为 `.pvt`
  - 使用 Apple 的 Core Graphics / AV Foundation 框架修改文件元数据
  - 会重写部分元数据（如 EXIF/IPTC/XMP），核心图形顺序可能归一化
  - 详见 [makelive 文档](https://github.com/RhetTbull/makelive) 的注意事项

## 许可

MIT License，详见 [LICENSE](LICENSE)。

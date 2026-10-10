# make-live-photo

把一张图片和一段视频合成为 Apple **Live Photo**，并打包成 `.pvt` 文件。

生成的 `.pvt` 包可以直接通过 **隔空投送（AirDrop）** 发送到 iPhone，接收后会自动保存为 Live Photo，非常适合把安卓手机拍的图转成 iPhone 的实况照片。

## 功能

- 将 `.jpg` / `.jpeg` / `.heic` 图片 + `.mov` 视频合成 Live Photo
- 自动打包为 iOS 识别的 `.pvt` 压缩包
- 不修改原始图片与视频（由底层依赖完成，仅对副本操作）
- 命令行一键使用

## 系统要求

- macOS（推荐 10.15 及以上）
- Python 3.9+

## 安装

本项目依赖 [makelive](https://github.com/RhetTbull/makelive)。

> ⚠️ 注意：`makelive` 可能无法直接用 `pip` 安装（依赖冲突），推荐使用 `uv`。

```bash
# 方式一：使用 uv 安装（推荐）
curl -LsSf https://astral.sh/uv/install.sh | sh
uv install makelive

# 方式二：在项目内安装（需要先安装 uv）
uv venv
source .venv/bin/activate
uv pip install makelive

# 方式三：用 uvx 直接运行，无需安装
uvx makelive image.jpg video.mov
```

安装完成后，确保当前目录能导入 `makelive`：

```bash
python -c "import makelive; print('makelive OK')"
```

## 使用

### 命令行

```bash
# 基本用法
python make_live_photo.py --image photo.jpg --video video.mov

# 自定义输出路径（-o 是可选的）
python make_live_photo.py -i photo.heic -v video.mov -o output.pvt
```

常用选项：

| 选项 | 说明 |
| --- | --- |
| `-i, --image` | **必填**：图片路径（支持 `.jpg` / `.jpeg` / `.heic`） |
| `-v, --video` | **必填**：视频路径（必须是 `.mov` 格式） |
| `-o, --output` | 可选：输出的 `.pvt` 路径，默认自动命名 |

### 快速开始

```bash
python make-live-photo.py -i photo.jpg -v clip.mov
```

## 参数说明

- **图片**：静态照片，作为 Live Photo 静止画面
- **视频**：时长通常较短的 `.mov` 片段，作为 Live Photo 的动效
- **输出**：`.pvt` 是 QuickTime 的压缩包格式，内含图片 + 视频 + 用于标识为 Live Photo 的元数据（Content Identifier）

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

**Q：原始图片/视频会被修改吗？**
A：底层库（`makelive`）在打包 `.pvt` 时只操作副本，不会改动原始文件。但请自行备份以防万一。

**Q：Live Photo 能用作动态壁纸吗？**
A：可能无法作为 Live Wallpaper 使用，这通常与视频格式/时长有关。

## 底层依赖

- [makelive](https://github.com/RhetTbull/makelive) — 负责写入元数据并把图 + 视频打包为 `.pvt`
  - 使用 Apple 的 Core Graphics / AV Foundation 框架修改文件元数据
  - 会重写部分元数据（如 EXIF/IPTC/XMP），核心图形顺序可能归一化
  - 详见 [makelive 文档](https://github.com/RhetTbull/makelive) 的注意事项

## 许可

MIT License，详见 [LICENSE](LICENSE)。

"""封面抽帧、时间参数和默认输出路径的单元测试。不依赖真实媒体或 ffmpeg。"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from io import StringIO
from pathlib import Path
from unittest import mock

from make_live_photo.cli import default_output_path, main, parse_time


class TestParseTime(unittest.TestCase):
    def test_accepts_seconds_and_timestamps(self):
        cases = {
            "0": 0.0,
            "1.5": 1.5,
            "90:00": 5400.0,
            "00:00:01.25": 1.25,
            "1:02:03": 3723.0,
            "1:02": 62.0,
            "  1.5  ": 1.5,
        }
        for text, expected in cases.items():
            normalized, seconds = parse_time(text)
            self.assertEqual(normalized, text.strip())
            self.assertEqual(seconds, expected)

    def test_rejects_invalid_times(self):
        for text in ("-1", "abc", "1:60", "1:02:60", "", "   ", "1s", "+1.5"):
            with self.assertRaises(ValueError):
                parse_time(text)


class TestDefaultOutput(unittest.TestCase):
    def test_uses_video_directory_and_stem(self):
        self.assertEqual(
            default_output_path(Path("/tmp/videos/clip.mov")),
            Path("/tmp/videos/clip.pvt"),
        )
        self.assertEqual(
            default_output_path(Path("/tmp/videos/my.clip.MOV")),
            Path("/tmp/videos/my.clip.pvt"),
        )


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.video = self.root / "clip.mov"
        self.video.write_bytes(b"video")
        self.image = self.root / "photo.jpg"
        self.image.write_bytes(b"image")
        self.saved = {}
        self.commands = []
        self.lookups = []

    def tearDown(self):
        self.tmp.cleanup()

    def _save(self, image, video, pvt_path=None, asset_id=None):
        self.saved.update(image=image, video=video, pvt_path=pvt_path)
        package = Path(pvt_path) / f"{Path(image).stem}.pvt"
        package.mkdir()
        (package / "metadata.plist").write_text("ok", encoding="utf-8")
        return "ASSET-1", package

    def _which(self, name):
        self.lookups.append(name)
        if name in {"ffmpeg", "ffprobe"}:
            return f"/usr/bin/{name}"
        return None

    def _run(self, command, **kwargs):
        self.commands.append(command)
        if "ffprobe" in Path(command[0]).name:
            return subprocess.CompletedProcess(command, 0, "10.000\n", "")
        Path(command[-1]).write_bytes(b"jpeg")
        return subprocess.CompletedProcess(command, 0, "", "")

    def _invoke(self, argv, which=None, run=None, save=None):
        stdout, stderr = StringIO(), StringIO()
        with ExitStack() as stack:
            stack.enter_context(mock.patch("make_live_photo.cli.shutil.which", which or self._which))
            stack.enter_context(mock.patch("make_live_photo.cli.subprocess.run", run or self._run))
            stack.enter_context(
                mock.patch("make_live_photo.cli.save_live_photo_pair_as_pvt", save or self._save)
            )
            stack.enter_context(mock.patch("sys.stdout", stdout))
            stack.enter_context(mock.patch("sys.stderr", stderr))
            try:
                main(argv)
            except SystemExit as exc:
                return exc.code, stdout.getvalue(), stderr.getvalue()
        return None, stdout.getvalue(), stderr.getvalue()

    def test_image_and_video_do_not_call_ffmpeg(self):
        def which(name):
            raise AssertionError(f"不应查找 {name}")

        def run(*args, **kwargs):
            raise AssertionError("不应调用 ffmpeg")

        code, stdout, stderr = self._invoke(
            ["-i", str(self.image), "-v", str(self.video)],
            which=which,
            run=run,
        )
        self.assertIsNone(code)
        self.assertEqual(Path(self.saved["image"]), self.image.resolve())
        self.assertTrue((self.root / "clip.pvt").is_dir())
        self.assertFalse((self.root / "photo.pvt").exists())
        self.assertIn(str(self.image.resolve()), stdout)
        self.assertIn(str(self.root / "clip.pvt"), stdout)
        self.assertEqual(stderr, "")

    def test_custom_output_is_used_as_given(self):
        output = self.root / "nested" / "custom.pvt"
        code, stdout, stderr = self._invoke(
            ["-i", str(self.image), "-v", str(self.video), "-o", str(output)],
            which=lambda name: (_ for _ in ()).throw(AssertionError(name)),
            run=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("run")),
        )
        self.assertIsNone(code, stderr)
        self.assertTrue(output.is_dir())
        self.assertEqual((output / "metadata.plist").read_text(encoding="utf-8"), "ok")
        self.assertFalse((self.root / "clip.pvt").exists())
        self.assertIn(str(output.resolve()), stdout)

    def test_output_without_pvt_suffix_is_not_rewritten(self):
        output = self.root / "bundle"
        code, _, stderr = self._invoke(
            ["-i", str(self.image), "-v", str(self.video), "-o", str(output)]
        )
        self.assertIsNone(code, stderr)
        self.assertTrue(output.is_dir())
        self.assertFalse(Path(str(output) + ".pvt").exists())

    def test_first_frame_when_image_omitted(self):
        code, stdout, stderr = self._invoke(["-v", str(self.video)])
        self.assertIsNone(code, stderr)
        command = self.commands[0]
        self.assertNotIn("-ss", command)
        self.assertEqual(command[1:6], ["-hide_banner", "-loglevel", "error", "-y", "-i"])
        self.assertEqual(command[6], str(self.video.resolve()))
        self.assertEqual(command[7:-1], ["-frames:v", "1", "-q:v", "2", "-update", "1"])
        self.assertTrue(command[-1].endswith("/clip.jpg"))
        self.assertEqual(Path(self.saved["image"]).name, "clip.jpg")
        self.assertFalse(Path(self.saved["image"]).exists())
        self.assertTrue((self.root / "clip.pvt").is_dir())
        self.assertFalse((self.root / "clip.jpg").exists())
        self.assertNotIn("ffprobe", self.lookups)
        self.assertIn("视频第一帧", stdout)
        self.assertIn("ASSET-1", stdout)

    def test_time_ignores_missing_image_and_keeps_timestamp(self):
        missing = self.root / "missing.jpg"
        code, stdout, stderr = self._invoke(
            ["-i", str(missing), "-v", str(self.video), "-t", "  00:00:01.25  "]
        )
        self.assertIsNone(code, stderr)
        command = next(item for item in self.commands if "ffprobe" not in item[0])
        self.assertEqual(command[7:-1], ["-ss", "00:00:01.25", "-frames:v", "1", "-q:v", "2", "-update", "1"])
        self.assertNotEqual(Path(self.saved["image"]), missing)
        self.assertIn("警告：已指定 --time，忽略图片：", stderr)
        self.assertIn(str(missing), stderr)
        self.assertIn("视频 00:00:01.25 处的帧", stdout)
        self.assertTrue((self.root / "clip.pvt").is_dir())

    def test_time_beyond_duration_skips_makelive(self):
        def run(command, **kwargs):
            self.commands.append(command)
            self.assertIn("ffprobe", command[0])
            return subprocess.CompletedProcess(command, 0, "1.0\n", "")

        code, _, stderr = self._invoke(["-v", str(self.video), "-t", "1.5"], run=run)
        self.assertEqual(code, 1)
        self.assertIn("错误：指定时间 1.5 超出视频时长（1.000 秒）", stderr)
        self.assertEqual(self.saved, {})
        self.assertFalse(any("ffmpeg" in item[0] for item in self.commands))

    def test_time_equal_to_duration_is_rejected(self):
        def run(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, "1.5\n", "")

        code, _, stderr = self._invoke(["-v", str(self.video), "-t", "1.5"], run=run)
        self.assertEqual(code, 1)
        self.assertIn("超出视频时长", stderr)
        self.assertEqual(self.saved, {})

    def test_missing_ffprobe_skips_precheck(self):
        def which(name):
            self.lookups.append(name)
            return "/usr/bin/ffmpeg" if name == "ffmpeg" else None

        code, _, stderr = self._invoke(
            ["-v", str(self.video), "-t", "1.5"],
            which=which,
        )
        self.assertIsNone(code, stderr)
        self.assertIn("ffprobe", self.lookups)
        self.assertEqual(len(self.commands), 1)
        self.assertIn("ffmpeg", self.commands[0][0])
        self.assertNotIn("ffprobe", self.commands[0][0])
        self.assertTrue(self.saved)

    def test_missing_ffmpeg_when_extracting(self):
        code, _, stderr = self._invoke(
            ["-v", str(self.video)],
            which=lambda name: None,
        )
        self.assertEqual(code, 1)
        self.assertIn(
            "错误：未找到 ffmpeg，请先安装并确保在 PATH 中（例如 brew install ffmpeg）",
            stderr,
        )
        self.assertEqual(self.saved, {})

    def test_ffmpeg_failure(self):
        def run(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, "", "decoder error\n")

        code, _, stderr = self._invoke(["-v", str(self.video)], run=run)
        self.assertEqual(code, 1)
        self.assertIn("错误：提取封面失败：decoder error", stderr)
        self.assertEqual(self.saved, {})

    def test_empty_jpeg_is_failure(self):
        def run(command, **kwargs):
            Path(command[-1]).write_bytes(b"")
            return subprocess.CompletedProcess(command, 0, "", "")

        code, _, stderr = self._invoke(["-v", str(self.video)], run=run)
        self.assertEqual(code, 1)
        self.assertIn("错误：提取封面失败：未生成图片", stderr)
        self.assertEqual(self.saved, {})

    def test_missing_jpeg_is_failure(self):
        def run(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, "", "")

        code, _, stderr = self._invoke(["-v", str(self.video)], run=run)
        self.assertEqual(code, 1)
        self.assertIn("未生成图片", stderr)

    def test_missing_video(self):
        code, _, stderr = self._invoke(["-v", str(self.root / "absent.mov")])
        self.assertEqual(code, 1)
        self.assertIn("错误：视频文件不存在：", stderr)
        self.assertEqual(self.saved, {})

    def test_missing_image_without_time(self):
        code, _, stderr = self._invoke(
            ["-i", str(self.root / "absent.jpg"), "-v", str(self.video)]
        )
        self.assertEqual(code, 1)
        self.assertIn("错误：图片文件不存在：", stderr)
        self.assertEqual(self.saved, {})

    def test_invalid_time(self):
        code, _, stderr = self._invoke(["-v", str(self.video), "-t", "abc"])
        self.assertEqual(code, 1)
        self.assertIn("错误：无法解析时间：abc", stderr)
        self.assertEqual(self.saved, {})
        self.assertEqual(self.commands, [])

    def test_existing_output_is_replaced(self):
        dest = self.root / "clip.pvt"
        dest.mkdir()
        (dest / "old.txt").write_text("old", encoding="utf-8")
        code, _, stderr = self._invoke(["-v", str(self.video)])
        self.assertIsNone(code, stderr)
        self.assertFalse((dest / "old.txt").exists())
        self.assertEqual((dest / "metadata.plist").read_text(encoding="utf-8"), "ok")

    def test_symlink_video_outputs_next_to_real_file(self):
        real_dir = self.root / "real"
        real_dir.mkdir()
        real = real_dir / "clip.mov"
        real.write_bytes(b"video")
        link = self.root / "link.mov"
        link.symlink_to(real)
        code, _, stderr = self._invoke(["-i", str(self.image), "-v", str(link)])
        self.assertIsNone(code, stderr)
        self.assertTrue((real_dir / "clip.pvt").is_dir())
        self.assertFalse((self.root / "link.pvt").exists())

    def test_move_failure(self):
        blocker = self.root / "not-a-dir"
        blocker.write_text("x", encoding="utf-8")
        code, _, stderr = self._invoke(
            ["-i", str(self.image), "-v", str(self.video), "-o", str(blocker / "out.pvt")]
        )
        self.assertEqual(code, 1)
        self.assertIn("移动输出失败", stderr)
        self.assertFalse((blocker / "out.pvt").exists())

    def test_makelive_failure(self):
        def save(*args, **kwargs):
            raise RuntimeError("boom")

        code, _, stderr = self._invoke(
            ["-i", str(self.image), "-v", str(self.video)],
            save=save,
        )
        self.assertEqual(code, 1)
        self.assertIn("合成失败：boom", stderr)

    def test_non_mov_still_warns_but_image_extension_only_when_used(self):
        video = self.root / "clip.mp4"
        video.write_bytes(b"video")
        image = self.root / "photo.png"
        image.write_bytes(b"image")
        code, _, stderr = self._invoke(["-i", str(image), "-v", str(video)])
        self.assertIsNone(code)
        self.assertIn("警告：视频建议使用 .mov 格式", stderr)
        self.assertIn("警告：图片建议使用 .jpg 或 .heic 格式", stderr)

        stderr_time = self._invoke(
            ["-i", str(image), "-v", str(video), "-t", "0"]
        )[2]
        self.assertIn("忽略图片", stderr_time)
        self.assertNotIn("图片建议使用", stderr_time)


if __name__ == "__main__":
    unittest.main()

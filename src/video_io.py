"""Streaming video decode / encode via FFmpeg pipes. Frames are not loaded entirely into RAM."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

from src.media_probe import MediaInfo, ffmpeg_bin, probe_and_validate_video
from src.utils import LOGGER, CommandError


class VideoIOError(RuntimeError):
    pass


def _terminate(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@dataclass
class FramePacket:
    index: int
    image_bgr: np.ndarray
    timestamp_sec: float


class VideoFrameReader:
    """Decode frames as BGR24 using FFmpeg. Rotation metadata is applied by the decoder."""

    def __init__(
        self,
        path: str | Path,
        info: MediaInfo | None = None,
        start_sec: float = 0.0,
        end_sec: float | None = None,
    ):
        self.path = Path(path)
        self.info = info or probe_and_validate_video(self.path)
        if not self.info.decode_ok or not self.info.video:
            raise VideoIOError(self.info.decode_error or "영상을 열 수 없습니다.")
        self.width = int(self.info.display_width or self.info.video.width or 0)
        self.height = int(self.info.display_height or self.info.video.height or 0)
        if self.width <= 0 or self.height <= 0:
            raise VideoIOError("유효한 해상도를 읽지 못했습니다.")
        self.fps = float(self.info.avg_fps or self.info.fps or 25.0)
        self.start_sec = max(0.0, float(start_sec))
        self.end_sec = end_sec
        self.frame_bytes = self.width * self.height * 3
        self._proc: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> "VideoFrameReader":
        argv = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error"]
        if self.start_sec > 0:
            argv += ["-ss", f"{self.start_sec:.6f}"]
        argv += ["-i", str(self.path)]
        if self.end_sec is not None and self.end_sec > self.start_sec:
            argv += ["-t", f"{self.end_sec - self.start_sec:.6f}"]
        argv += [
            "-an",
            "-sn",
            "-pix_fmt",
            "bgr24",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
        self._proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._proc is None:
            return
        stderr = b""
        if self._proc.stderr:
            try:
                stderr = self._proc.stderr.read() or b""
            except OSError:
                stderr = b""
        _terminate(self._proc)
        code = self._proc.returncode
        self._proc = None
        if exc_type is None and code not in (0, None) and code != 0:
            LOGGER.warning("ffmpeg reader exit=%s stderr=%s", code, stderr[-500:])

    def frames(self) -> Iterator[FramePacket]:
        if self._proc is None or self._proc.stdout is None:
            raise VideoIOError("reader is not started")
        index = 0
        leftover = b""
        while True:
            chunk = self._proc.stdout.read(self.frame_bytes - len(leftover))
            if not chunk:
                break
            leftover += chunk
            if len(leftover) < self.frame_bytes:
                continue
            raw = leftover[: self.frame_bytes]
            leftover = leftover[self.frame_bytes :]
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((self.height, self.width, 3)).copy()
            ts = self.start_sec + (index / self.fps if self.fps > 0 else 0.0)
            yield FramePacket(index=index, image_bgr=frame, timestamp_sec=ts)
            index += 1


class VideoFrameWriter:
    """Encode BGR24 frames with FFmpeg. Always performs a real encode (never extension rename)."""

    def __init__(
        self,
        path: str | Path,
        width: int,
        height: int,
        fps: float,
        video_encoder: str = "libx264",
        pix_fmt: str = "yuv420p",
        extra_args: list[str] | None = None,
        lossless: bool = False,
        high_quality: bool = True,
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.width = int(width)
        self.height = int(height)
        self.fps = float(fps) if fps > 0 else 25.0
        self.video_encoder = video_encoder
        self.pix_fmt = pix_fmt
        self.extra_args = extra_args or []
        self.lossless = lossless
        self.high_quality = high_quality
        self.frames_written = 0
        self._proc: subprocess.Popen[bytes] | None = None

    def _quality_args(self) -> list[str]:
        enc = self.video_encoder
        if enc in {"libx264", "libx265", "h264_nvenc", "hevc_nvenc"}:
            if self.lossless:
                if "nvenc" in enc:
                    return ["-cq", "0", "-preset", "p7"]
                return ["-crf", "0", "-preset", "slow"]
            crf = "16" if self.high_quality else "20"
            return ["-crf", crf, "-preset", "medium"]
        if enc in {"libvpx-vp9", "libvpx"}:
            return ["-b:v", "0", "-crf", "28" if self.high_quality else "35"]
        if enc in {"libaom-av1", "libsvtav1"}:
            return ["-crf", "24" if self.high_quality else "32"]
        if enc == "gif":
            return []
        if enc in {"libwebp", "libwebp_anim"}:
            return ["-lossless", "1" if self.lossless else "0", "-quality", "90"]
        return ["-q:v", "3" if self.high_quality else "6"]

    def __enter__(self) -> "VideoFrameWriter":
        argv = [
            ffmpeg_bin(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{self.width}x{self.height}",
            "-r",
            f"{self.fps:.6f}",
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            self.video_encoder,
            *self._quality_args(),
            "-pix_fmt",
            self.pix_fmt,
            *self.extra_args,
            str(self.path),
        ]
        LOGGER.info("encoder argv: %s", argv)
        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return self

    def write(self, frame_bgr: np.ndarray) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise VideoIOError("writer is not started")
        if frame_bgr.shape[0] != self.height or frame_bgr.shape[1] != self.width:
            import cv2

            frame_bgr = cv2.resize(frame_bgr, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
        if frame_bgr.dtype != np.uint8:
            frame_bgr = np.clip(frame_bgr, 0, 255).astype(np.uint8)
        if frame_bgr.ndim == 2:
            import cv2

            frame_bgr = cv2.cvtColor(frame_bgr, cv2.COLOR_GRAY2BGR)
        try:
            self._proc.stdin.write(np.ascontiguousarray(frame_bgr).tobytes())
        except BrokenPipeError as exc:
            err = b""
            if self._proc.stderr:
                err = self._proc.stderr.read() or b""
            raise VideoIOError(f"인코더 파이프가 끊겼습니다: {err.decode('utf-8', 'ignore')}") from exc
        self.frames_written += 1

    def close(self) -> None:
        if self._proc is None:
            return
        stderr = b""
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            if self._proc.stderr:
                stderr = self._proc.stderr.read() or b""
            code = self._proc.wait(timeout=120)
        except Exception:
            _terminate(self._proc)
            raise
        finally:
            self._proc = None
        if code != 0:
            raise VideoIOError(
                f"FFmpeg 인코딩 실패 (exit {code}): {stderr.decode('utf-8', 'ignore')[-2000:]}"
            )

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            _terminate(self._proc)
            self._proc = None
            return
        self.close()


def extract_frame_at(path: str | Path, timestamp_sec: float, info: MediaInfo | None = None) -> np.ndarray:
    with VideoFrameReader(path, info=info, start_sec=max(0.0, timestamp_sec), end_sec=max(0.0, timestamp_sec) + 1.0 / 8.0) as reader:
        for packet in reader.frames():
            return packet.image_bgr
    # Fallback: grab the first frame from a slightly wider window
    with VideoFrameReader(path, info=info, start_sec=max(0.0, timestamp_sec - 0.05), end_sec=timestamp_sec + 0.5) as reader:
        for packet in reader.frames():
            return packet.image_bgr
    raise VideoIOError(f"{timestamp_sec:.3f}s 위치에서 프레임을 추출하지 못했습니다.")


def count_decoded_frames(path: str | Path, start_sec: float = 0.0, end_sec: float | None = None) -> int:
    count = 0
    with VideoFrameReader(path, start_sec=start_sec, end_sec=end_sec) as reader:
        for _ in reader.frames():
            count += 1
    return count

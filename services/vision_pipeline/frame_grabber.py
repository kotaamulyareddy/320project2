"""
Video frame grabber for camera stream ingestion.

Provides robust frame capture from various video sources (RTSP, HTTP, webcam)
with error handling, frame skipping, and quality optimization.
"""

import asyncio
import time
from typing import Optional, AsyncGenerator
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class FrameCaptureResult:
    """Result of frame capture operation."""

    frame_id: str
    frame: np.ndarray
    frame_number: int
    timestamp: float
    capture_time_ms: float
    width: int
    height: int
    success: bool
    error_message: Optional[str] = None


class FrameGrabber:
    """
    High-performance video frame grabber.

    Supports multiple input sources with configurable frame rates,
    quality settings, and error recovery mechanisms.
    """

    def __init__(
        self,
        source: str = "0",
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        frame_skip: int = 1,
        jpeg_quality: int = 85,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 5.0,
    ):
        """
        Initialize frame grabber.

        Args:
            source: Video source (webcam index, RTSP URL, HTTP URL, or file path)
            width: Target frame width
            height: Target frame height
            fps: Target frames per second
            frame_skip: Process every Nth frame (1 = all frames)
            jpeg_quality: JPEG compression quality (1-100)
            max_reconnect_attempts: Maximum reconnection attempts on failure
            reconnect_delay: Delay between reconnection attempts (seconds)
        """
        self.source = source
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_skip = frame_skip
        self.jpeg_quality = jpeg_quality
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay

        # OpenCV video capture
        self.cap: Optional[cv2.VideoCapture] = None

        # State tracking
        self.frame_count = 0
        self.last_frame_time = 0.0
        self.is_running = False
        self.reconnect_attempts = 0
        self._current_frame_number = 0

    async def start(self) -> None:
        """
        Start the frame grabber.

        Initializes video capture and prepares for frame grabbing.
        """
        if self.is_running:
            return

        self.is_running = True
        self.reconnect_attempts = 0

        await self._init_capture()

    async def stop(self) -> None:
        """
        Stop the frame grabber.

        Releases resources and cleans up.
        """
        self.is_running = False

        if self.cap:
            self.cap.release()
            self.cap = None

    async def _init_capture(self) -> None:
        """
        Initialize video capture with retry logic.

        Raises:
            RuntimeError: If capture initialization fails after retries
        """
        for attempt in range(self.max_reconnect_attempts):
            try:
                self.cap = cv2.VideoCapture(self.source)

                if not self.cap.isOpened():
                    raise RuntimeError(f"Cannot open video source: {self.source}")

                # Set capture properties
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap.set(cv2.CAP_PROP_FPS, self.fps)

                # Verify settings
                actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

                print(
                    f"Initialized video capture: {self.source} "
                    f"({actual_width}x{actual_height} @ {actual_fps:.1f} FPS)"
                )

                self.reconnect_attempts = 0
                return

            except Exception as e:
                self.reconnect_attempts += 1
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    raise RuntimeError(
                        f"Failed to initialize video capture after {self.max_reconnect_attempts} attempts: {e}"
                    )

                print(
                    f"Capture initialization failed (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}): {e}"
                )
                await asyncio.sleep(self.reconnect_delay)

    async def grab_frame(self) -> Optional[FrameCaptureResult]:
        """
        Grab a single frame from the video source.

        Returns:
            Frame capture result or None if no frame available
        """
        if not self.is_running or not self.cap:
            return None

        # Control frame rate
        current_time = time.time()
        frame_time = 1.0 / self.fps

        # Frame skipping logic
        if self.frame_count % self.frame_skip != 0:
            self.frame_count += 1
            return FrameCaptureResult(
                frame_id=f"skipped_{self.frame_count}",
                frame=None,  # type: ignore
                frame_number=self._current_frame_number,
                timestamp=current_time,
                capture_time_ms=0.0,
                width=0,
                height=0,
                success=False,
                error_message="Frame skipped",
            )

        # Check if we're due for next frame
        if current_time - self.last_frame_time < frame_time:
            await asyncio.sleep(0.001)  # Small delay to prevent busy waiting
            return None

        # Capture frame
        start_time = time.time()
        ret, frame = self.cap.read()

        if not ret or frame is None:
            # Try to reconnect
            await self._reconnect()
            return FrameCaptureResult(
                frame_id=f"failed_{self.frame_count}",
                frame=None,  # type: ignore
                frame_number=self._current_frame_number,
                timestamp=current_time,
                capture_time_ms=(time.time() - start_time) * 1000,
                width=0,
                height=0,
                success=False,
                error_message="Failed to capture frame",
            )

        # Update state
        self.last_frame_time = current_time
        self.frame_count += 1
        self._current_frame_number += 1

        # Process frame
        capture_time_ms = (time.time() - start_time) * 1000

        # Optionally compress frame (JPEG)
        # frame = self._compress_frame(frame)

        result = FrameCaptureResult(
            frame_id=f"frame_{self.frame_count}",
            frame=frame,
            frame_number=self._current_frame_number,
            timestamp=current_time,
            capture_time_ms=capture_time_ms,
            width=frame.shape[1],
            height=frame.shape[0],
            success=True,
        )

        return result

    async def _reconnect(self) -> None:
        """
        Attempt to reconnect to video source.

        Resets capture and re-initializes.
        """
        print(f"Attempting reconnection ({self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")

        if self.cap:
            self.cap.release()
            self.cap = None

        await asyncio.sleep(self.reconnect_delay)
        await self._init_capture()

    def _compress_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Compress frame to JPEG format.

        Args:
            frame: Input frame (BGR)

        Returns:
            Compressed frame as numpy array
        """
        _, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        return np.frombuffer(encoded.tobytes(), dtype=np.uint8)

    async def stream_frames(self) -> AsyncGenerator[FrameCaptureResult, None]:
        """
        Stream frames continuously from the video source.

        Yields:
            Frame capture results
        """
        await self.start()

        try:
            while self.is_running:
                frame_result = await self.grab_frame()
                if frame_result and frame_result.success:
                    yield frame_result
                elif frame_result and not frame_result.success:
                    # Log but continue for recoverable errors
                    print(f"Frame capture issue: {frame_result.error_message}")

        finally:
            await self.stop()

    def get_source_info(self) -> dict:
        """
        Get information about the video source.

        Returns:
            Dictionary with source information
        """
        if self.cap and self.cap.isOpened():
            return {
                "source": self.source,
                "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps": self.cap.get(cv2.CAP_PROP_FPS),
                "codec": int(self.cap.get(cv2.CAP_PROP_FOURCC)),
                "frame_count": self.cap.get(cv2.CAP_PROP_FRAME_COUNT),
                "is_color": self.cap.get(cv2.CAP_PROP_IS_COLOR) == 1,
            }
        else:
            return {
                "source": self.source,
                "status": "not_connected",
                "reconnect_attempts": self.reconnect_attempts,
            }

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


async def main():
    """
    Example usage of frame grabber.

    Demonstrates streaming frames from a video source.
    """
    # Example with default webcam
    async with FrameGrabber(source="0") as grabber:
        print("Frame grabber started")

        async for frame_result in grabber.stream_frames():
            if frame_result.success:
                print(
                    f"Captured frame {frame_result.frame_number}: "
                    f"({frame_result.width}x{frame_result.height}) "
                    f"in {frame_result.capture_time_ms:.2f}ms"
                )
                # Process frame here
                # processed = await process_frame(frame_result.frame)

                # Break after 10 frames for demo
                if frame_result.frame_number >= 9:
                    break
            else:
                print(f"Frame capture failed: {frame_result.error_message}")

    print("Frame grabber stopped")


if __name__ == "__main__":
    asyncio.run(main())
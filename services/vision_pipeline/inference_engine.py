"""
High-Performance Vision Inference Engine.

Provides asynchronous ONNX Runtime inference for video frame processing
with support for GPU acceleration, batch processing, and real-time
performance optimization.
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple, Any, AsyncGenerator
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from pydantic import BaseModel, Field, ValidationError
import onnxruntime as ort
import torch
from threading import Lock

from services.vision_pipeline.frame_grabber import FrameGrabber


@dataclass
class DetectionResult:
    """Detection result from model inference."""

    box: Tuple[float, float, float, float]  # (x_min, y_min, x_max, y_max)
    confidence: float
    class_id: int
    class_name: str
    inference_time_ms: float


@dataclass
class ProcessedFrame:
    """Processed frame with detections."""

    frame_id: str
    frame_number: int
    timestamp: float
    image: np.ndarray
    detections: List[DetectionResult]
    processing_time_ms: float
    is_anomaly: bool = False
    anomaly_score: float = 0.0


class DetectionModel:
    """ONNX model wrapper with performance optimizations."""

    def __init__(
        self,
        model_path: str,
        input_size: Tuple[int, int] = (640, 640),
        use_cuda: bool = False,
        num_threads: int = 0,
    ):
        self.model_path = model_path
        self.input_size = input_size
        self.use_cuda = use_cuda
        self.num_threads = num_threads if num_threads > 0 else None

        # Initialize ONNX Runtime
        self.providers = ["CUDAExecutionProvider"] if use_cuda else ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(
            model_path,
            providers=self.providers,
        )

        if self.num_threads:
            # Set number of threads for CPU provider
            sess_options = ort.SessionOptions()
            sess_options.intra_op_num_threads = self.num_threads
            sess_options.inter_op_num_threads = 1
            self.session = ort.InferenceSession(
                model_path,
                providers=self.providers,
                sess_options=sess_options,
            )

        # Get model information
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [output.name for output in self.session.get_outputs()]

    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocess frame for model inference.

        Args:
            frame: Input frame (H, W, C)

        Returns:
            Preprocessed frame ready for inference
        """
        # Resize to model input size
        if frame.shape[:2] != self.input_size:
            frame = cv2.resize(frame, self.input_size)

        # Convert BGR to RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Normalize to [0, 1]
        frame = frame.astype(np.float32) / 255.0

        # Transpose to CHW format (C, H, W)
        frame = np.transpose(frame, (2, 0, 1))

        # Add batch dimension
        frame = np.expand_dims(frame, axis=0)

        return frame

    def postprocess_outputs(
        self,
        outputs: List[np.ndarray],
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45,
    ) -> List[DetectionResult]:
        """
        Post-process model outputs to extract detections.

        Note: This is a generic implementation that assumes YOLO-like outputs.
        Adjust based on your specific model architecture.

        Args:
            outputs: Raw model outputs
            conf_threshold: Confidence threshold
            iou_threshold: IoU threshold for NMS

        Returns:
            List of detection results
        """
        detections = []

        # Example implementation for YOLO-like models
        # This assumes outputs[0] has shape [1, N, 85] (x, y, w, h, conf, class...)
        if len(outputs) > 0:
            output = outputs[0]  # Take first output

            # Reshape and filter by confidence
            if output.shape[2] >= 85:  # YOLO format
                # Extract box coordinates
                boxes = output[0, :, :4] * self.input_size  # Scale to original size
                confidences = output[0, :, 4]
                class_ids = output[0, :, 5:].argmax(axis=1)
                class_scores = output[0, :, 5:].max(axis=1)

                # Filter by confidence
                mask = confidences > conf_threshold
                if mask.any():
                    boxes = boxes[mask]
                    confidences = confidences[mask]
                    class_ids = class_ids[mask]
                    class_scores = class_scores[mask]

                    # Convert to normalized coordinates (0-1)
                    detections = [
                        DetectionResult(
                            box=(
                                boxes[i, 0] / self.input_size[0],
                                boxes[i, 1] / self.input_size[1],
                                boxes[i, 2] / self.input_size[0],
                                boxes[i, 1] / self.input_size[1],
                            ),
                            confidence=float(confidences[i]),
                            class_id=int(class_ids[i]),
                            class_name=f"class_{int(class_ids[i])}",  # Should be mapped from class names
                            inference_time_ms=0.0,  # Will be set by caller
                        )
                        for i in range(len(boxes))
                    ]

        return detections

    async def infer_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, List[DetectionResult]]:
        """
        Run inference on a single frame.

        Args:
            frame: Input frame (H, W, C)

        Returns:
            Tuple of (original_frame, detections)
        """
        start_time = time.time()

        # Preprocess
        input_frame = self.preprocess_frame(frame)

        # Run inference (blocking operation)
        loop = asyncio.get_event_loop()

        def run_inference():
            outputs = self.session.run(self.output_names, {self.input_name: input_frame})
            return outputs

        # Run in thread pool to avoid blocking event loop
        outputs = await loop.run_in_executor(None, run_inference)

        # Post-process
        detections = self.postprocess_outputs(outputs)

        # Update inference time in detections
        inference_time_ms = (time.time() - start_time) * 1000
        for detection in detections:
            detection.inference_time_ms = inference_time_ms

        return frame, detections


class InferencePipeline:
    """
    Asynchronous inference pipeline for video processing.

    Manages multiple inference requests, batching, and frame processing
    with support for backpressure handling.
    """

    def __init__(
        self,
        model_path: str,
        input_size: Tuple[int, int] = (640, 640),
        use_cuda: bool = False,
        num_threads: int = 0,
        batch_size: int = 1,
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45,
    ):
        self.model_path = model_path
        self.input_size = input_size
        self.use_cuda = use_cuda
        self.num_threads = num_threads
        self.batch_size = batch_size
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold

        # Initialize model
        self.model = DetectionModel(
            model_path=model_path,
            input_size=input_size,
            use_cuda=use_cuda,
            num_threads=num_threads,
        )

        # Request queue and processing
        self._request_queue: asyncio.Queue = asyncio.Queue(maxsize=batch_size * 2)
        self._results_queue: asyncio.Queue = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown = False

        # Thread pool for blocking operations
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def start(self) -> None:
        """Start the inference pipeline."""
        self._processing_task = asyncio.create_task(self._processing_loop())

    async def stop(self) -> None:
        """Stop the inference pipeline."""
        self._shutdown = True
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        self._executor.shutdown(wait=True)

    async def process_frame(
        self,
        frame_id: str,
        frame: np.ndarray,
        frame_number: int,
        timestamp: float,
    ) -> ProcessedFrame:
        """
        Process a single frame through the inference pipeline.

        Args:
            frame_id: Unique frame identifier
            frame: Input frame (H, W, C)
            frame_number: Frame number in sequence
            timestamp: Frame timestamp

        Returns:
            Processed frame with detections
        """
        # Add request to queue
        request = {
            "frame_id": frame_id,
            "frame": frame,
            "frame_number": frame_number,
            "timestamp": timestamp,
        }

        await self._request_queue.put(request)

        # Wait for result
        result = await self._results_queue.get()

        # Process audio if needed (would be integrated here)
        # audio_result = await self.process_audio(frame_id, timestamp)

        return result

    async def _processing_loop(self) -> None:
        """
        Main processing loop that handles inference requests.

        Collects frames in batches, processes them, and sends results.
        """
        batch = []
        batch_frame_ids = []

        while not self._shutdown:
            try:
                # Get request with timeout
                request = await asyncio.wait_for(
                    self._request_queue.get(),
                    timeout=0.1,
                )

                batch.append(request["frame"])
                batch_frame_ids.append(request["frame_id"])

                # Process batch if full
                if len(batch) >= self.batch_size:
                    await self._process_batch(batch, batch_frame_ids)
                    batch.clear()
                    batch_frame_ids.clear()

            except asyncio.TimeoutError:
                # Process remaining frames in batch
                if batch:
                    await self._process_batch(batch, batch_frame_ids)
                    batch.clear()
                    batch_frame_ids.clear()

            except Exception as e:
                print(f"Error in processing loop: {e}")
                batch.clear()
                batch_frame_ids.clear()

        # Process any remaining frames
        if batch:
            await self._process_batch(batch, batch_frame_ids)

    async def _process_batch(
        self,
        frames: List[np.ndarray],
        frame_ids: List[str],
    ) -> None:
        """
        Process a batch of frames.

        Args:
            frames: List of frames to process
            frame_ids: Corresponding frame IDs
        """
        start_time = time.time()

        # Stack frames for batched inference (if supported)
        if len(frames) > 1:
            # Simple batching - each frame separately for now
            # TODO: Implement true batch inference if model supports it
            processed_frames = []
            for i, (frame, frame_id) in enumerate(zip(frames, frame_ids)):
                original_frame, detections = await self.model.infer_frame(frame)
                processed_frame = ProcessedFrame(
                    frame_id=frame_id,
                    frame_number=i,
                    timestamp=time.time(),
                    image=original_frame,
                    detections=detections,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )
                processed_frames.append(processed_frame)
                await self._results_queue.put(processed_frame)
        else:
            # Single frame processing
            frame = frames[0]
            frame_id = frame_ids[0]
            original_frame, detections = await self.model.infer_frame(frame)
            processed_frame = ProcessedFrame(
                frame_id=frame_id,
                frame_number=0,
                timestamp=time.time(),
                image=original_frame,
                detections=detections,
                processing_time_ms=(time.time() - start_time) * 1000,
            )
            await self._results_queue.put(processed_frame)


class AsyncInferenceEngine:
    """
    Main interface for asynchronous video inference.

    Coordinates frame grabbing, inference, and result publishing.
    """

    def __init__(
        self,
        model_path: str,
        redis_url: str,
        use_cuda: bool = False,
        **kwargs,
    ):
        self.model_path = model_path
        self.redis_url = redis_url
        self.use_cuda = use_cuda
        self.kwargs = kwargs

        # Initialize components
        self.pipeline: Optional[InferencePipeline] = None
        self.frame_grabber: Optional[FrameGrabber] = None

    async def initialize(self) -> None:
        """Initialize all components."""
        self.pipeline = InferencePipeline(
            model_path=self.model_path,
            use_cuda=self.use_cuda,
            **self.kwargs,
        )
        await self.pipeline.start()

    async def shutdown(self) -> None:
        """Shutdown all components."""
        if self.pipeline:
            await self.pipeline.stop()

    async def process_video_stream(
        self,
        camera_id: str,
        stream_url: str = "0",
    ) -> AsyncGenerator[ProcessedFrame, None]:
        """
        Process a video stream continuously.

        Args:
            camera_id: Camera identifier
            stream_url: Video stream URL (RTSP, webcam, file path)

        Yields:
            Processed frames with detections
        """
        self.frame_grabber = FrameGrabber(stream_url)
        await self.frame_grabber.start()

        try:
            frame_number = 0
            while True:
                # Grab frame
                frame = await self.frame_grabber.grab_frame()
                if frame is None:
                    break

                # Process frame
                processed_frame = await self.pipeline.process_frame(
                    frame_id=f"{camera_id}_{frame_number}",
                    frame=frame,
                    frame_number=frame_number,
                    timestamp=time.time(),
                )

                yield processed_frame

                frame_number += 1

        finally:
            if self.frame_grabber:
                await self.frame_grabber.stop()

    async def process_frame_async(
        self,
        camera_id: str,
        frame: np.ndarray,
    ) -> ProcessedFrame:
        """
        Process a single frame asynchronously.

        Args:
            camera_id: Camera identifier
            frame: Input frame

        Returns:
            Processed frame with detections
        """
        return await self.pipeline.process_frame(
            frame_id=f"{camera_id}_{time.time()}",
            frame=frame,
            frame_number=0,
            timestamp=time.time(),
        )


async def main():
    """
    Example usage of the inference engine.

    Demonstrates processing a video stream and handling results.
    """
    # Initialize engine
    engine = AsyncInferenceEngine(
        model_path="yolov8n.onnx",
        redis_url="redis://localhost:6379",
        use_cuda=False,
        input_size=(640, 640),
        batch_size=1,
        conf_threshold=0.5,
    )

    await engine.initialize()

    # Process stream
    async for processed_frame in engine.process_video_stream(
        camera_id="test_camera",
        stream_url="0",  # Webcam
    ):
        print(f"Processed frame {processed_frame.frame_id}")
        print(f"  Detections: {len(processed_frame.detections)}")
        print(f"  Processing time: {processed_frame.processing_time_ms:.2f}ms")

        # Save result or publish to Redis
        # await publish_result(processed_frame)

    await engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
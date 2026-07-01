"""
Asynchronous Stream Processor Worker.

Consumes video inference events from Redis Streams, performs database persistence,
writes anomaly frames to S3/MinIO, and triggers real-time alerts.
"""

import asyncio
import json
import logging
import io
import uuid
from datetime import datetime, UTC

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from minio import Minio

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.analytics import DetectionEvent, FrameMetadata, Alert, AudioAnalysis
from app.schemas.analytics import (
    DetectionEventCreate, FrameMetadataCreate, AlertCreate,
)

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MinIO Client
s3_client = Minio(
    settings.S3_ENDPOINT_URL.replace("http://", "").replace("https://", ""),
    access_key=settings.S3_ACCESS_KEY,
    secret_key=settings.S3_SECRET_KEY,
    secure=settings.S3_SECURE,
)

async def store_frame_to_s3(frame_bytes: bytes, frame_id: str) -> str:
    """Store frame image bytes to MinIO/S3."""
    bucket = settings.S3_BUCKET_NAME
    object_name = f"anomaly/{frame_id}.jpg"

    # Ensure bucket exists
    if not s3_client.bucket_exists(bucket):
        s3_client.make_bucket(bucket)

    s3_client.put_object(
        bucket,
        object_name,
        data=io.BytesIO(frame_bytes),
        length=len(frame_bytes),
        content_type="image/jpeg",
    )
    return object_name

async def process_event(event_data: dict, session: AsyncSession) -> None:
    """
    Process a single detection/anomaly event.

    Args:
        event_data: Event payload from Redis
        session: SQLAlchemy DB session
    """
    frame_id = event_data.get("frame_id")
    camera_id = event_data.get("camera_id")

    # 1. Store frame metadata
    frame_meta = FrameMetadata(
        camera_id=camera_id,
        frame_number=event_data.get("frame_number", 0),
        timestamp=datetime.now(UTC),
        width=event_data.get("width", 640),
        height=event_data.get("height", 480),
        processing_time_ms=event_data.get("processing_time_ms", 0.0),
        inference_time_ms=event_data.get("inference_time_ms", 0.0),
        detection_count=len(event_data.get("detections", [])),
        is_anomaly=event_data.get("is_anomaly", False),
    )
    session.add(frame_meta)
    await session.flush()

    # 2. Store detections
    for det in event_data.get("detections", []):
        detection = DetectionEvent(
            camera_id=camera_id,
            frame_id=frame_meta.id,
            x_min=det["box"][0],
            y_min=det["box"][1],
            x_max=det["box"][2],
            y_max=det["box"][3],
            class_id=det["class_id"],
            class_name=det["class_name"],
            confidence=det["confidence"],
            model_name=det["model_name"],
            model_version=det["model_version"],
            inference_time_ms=det["inference_time_ms"],
        )
        session.add(detection)

    # 3. Store anomaly alert
    if event_data.get("is_anomaly", False):
        alert = Alert(
            camera_id=camera_id,
            frame_id=frame_meta.id,
            alert_type="anomaly_detected",
            severity="high",
            title="Anomaly Detected",
            message=f"Anomaly detected in frame {frame_meta.frame_number}",
        )
        session.add(alert)

    await session.commit()
    logger.info(f"Successfully processed event for frame {frame_id}")

async def run_worker() -> None:
    """Main worker loop consuming events from Redis Streams."""
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=False)
    stream_key = settings.RAW_FRAME_STREAM
    group_name = settings.STREAM_PROCESSOR_GROUP
    consumer_name = f"worker_{uuid.uuid4().hex}"

    # Create consumer group
    try:
        await redis_client.xgroup_create(stream_key, group_name, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise e

    logger.info(f"Worker {consumer_name} starting...")

    while True:
        # Read events
        events = await redis_client.xreadgroup(
            group_name, consumer_name, {stream_key: ">"}, count=10, block=1000
        )

        for _, messages in events:
            for message_id, message_content in messages:
                try:
                    data = json.loads(message_content[b"data"].decode("utf-8"))

                    async with async_session_factory() as session:
                        await process_event(data, session)

                    # Acknowledge event
                    await redis_client.xack(stream_key, group_name, message_id)
                except Exception as e:
                    logger.error(f"Error processing message {message_id}: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped")
"""
Celery Task Definitions.

Background tasks for maintenance, cleanup, and scheduled operations.
"""

import asyncio
from datetime import datetime, UTC, timedelta
from celery import shared_task

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.analytics import FrameMetadata, SystemTelemetry, Alert

import redis.asyncio as redis


@shared_task(bind=True, max_retries=3)
def cleanup_old_frames(self, days: int = 30):
    """
    Clean up old frame metadata and associated files.

    Args:
        days: Retention period in days
    """
    async def _cleanup():
        cutoff = datetime.now(UTC) - timedelta(days=days)

        async with async_session_factory() as session:
            # Find old frames marked as anomalies (keep anomalies longer)
            from sqlalchemy import select, delete
            old_frames = await session.execute(
                select(FrameMetadata).where(
                    FrameMetadata.timestamp < cutoff,
                    FrameMetadata.is_anomaly == False
                )
            )
            frames_to_delete = old_frames.scalars().all()

            deleted_count = 0
            for frame in frames_to_delete:
                # Delete from S3 if exists
                if frame.s3_key and frame.s3_bucket:
                    try:
                        from minio import Minio
                        s3_client = Minio(
                            settings.S3_ENDPOINT_URL.replace("http://", "").replace("https://", ""),
                            access_key=settings.S3_ACCESS_KEY,
                            secret_key=settings.S3_SECRET_KEY,
                            secure=settings.S3_SECURE,
                        )
                        s3_client.remove_object(frame.s3_bucket, frame.s3_key)
                    except Exception:
                        pass

                await session.delete(frame)
                deleted_count += 1

            await session.commit()
            return deleted_count

    try:
        return asyncio.run(_cleanup())
    except Exception as e:
        self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def purge_old_metrics(self, days: int = 90):
    """
    Purge old telemetry metrics.

    Args:
        days: Retention period in days
    """
    async def _purge():
        cutoff = datetime.now(UTC) - timedelta(days=days)

        async with async_session_factory() as session:
            from sqlalchemy import delete
            result = await session.execute(
                delete(SystemTelemetry).where(SystemTelemetry.timestamp < cutoff)
            )
            await session.commit()
            return result.rowcount

    try:
        return asyncio.run(_purge())
    except Exception as e:
        self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def cleanup_resolved_alerts(self, days: int = 30):
    """
    Clean up resolved alerts older than specified days.

    Args:
        days: Retention period in days
    """
    async def _cleanup():
        cutoff = datetime.now(UTC) - timedelta(days=days)

        async with async_session_factory() as session:
            from sqlalchemy import delete
            result = await session.execute(
                delete(Alert).where(
                    Alert.is_resolved == True,
                    Alert.resolved_at < cutoff
                )
            )
            await session.commit()
            return result.rowcount

    try:
        return asyncio.run(_cleanup())
    except Exception as e:
        self.retry(exc=e, countdown=60)


@shared_task
def publish_heartbeat_metrics(component: str, instance_id: str):
    """
    Publish heartbeat metrics to Redis for monitoring.

    Args:
        component: Component name
        instance_id: Instance identifier
    """
    async def _publish():
        r = redis.from_url(settings.REDIS_URL)
        try:
            metrics = {
                "component": component,
                "instance_id": instance_id,
                "metric_name": "heartbeat",
                "metric_value": 1,
                "metric_unit": "bool",
                "timestamp": datetime.now(UTC).isoformat(),
            }
            await r.xadd("stream:telemetry", {"data": str(metrics)})
        finally:
            await r.aclose()

    asyncio.run(_publish())


@shared_task
def process_video_batch(camera_id: str, frame_data_list: list):
    """
    Process a batch of video frames.

    Args:
        camera_id: Camera identifier
        frame_data_list: List of frame data dictionaries
    """
    # This would be called by the vision pipeline to offload
    # batch processing to workers
    async def _process():
        async with async_session_factory() as session:
            for frame_data in frame_data_list:
                # Process each frame
                pass

    asyncio.run(_process())


# Periodic task registration (called by Celery beat)
@shared_task
def periodic_health_check():
    """Periodic health check for all services."""
    async def _check():
        results = {}
        r = redis.from_url(settings.REDIS_URL)
        try:
            # Check Redis
            await r.ping()
            results["redis"] = "healthy"
        except Exception:
            results["redis"] = "unhealthy"
        finally:
            await r.aclose()

        # Check database
        try:
            async with async_session_factory() as session:
                await session.execute("SELECT 1")
            results["database"] = "healthy"
        except Exception:
            results["database"] = "unhealthy"

        return results

    return asyncio.run(_check())
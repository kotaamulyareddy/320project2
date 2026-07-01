"""
SQLAlchemy models for analytics and event data.

Defines database schema for storing detection events, anomalies,
frame metadata, and system telemetry.
"""

from datetime import datetime, UTC
from typing import Optional, List
from uuid import UUID

from sqlalchemy import String, Text, Float, Integer, Boolean, Index, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel, BaseModelSoftDelete


class Camera(BaseModel):
    """
    Camera/stream source configuration.

    Represents a video source (RTSP, webcam, file) that feeds
    into the analytics pipeline.
    """

    __tablename__ = "cameras"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="rtsp")
    # rtsp, http, file, webcam

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resolution_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Zone/ROI configuration as JSON
    zones_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    events: Mapped[List["DetectionEvent"]] = relationship(
        back_populates="camera", lazy="dynamic"
    )
    frames: Mapped[List["FrameMetadata"]] = relationship(
        back_populates="camera", lazy="dynamic"
    )

    __table_args__ = (
        Index("ix_cameras_is_active", "is_active"),
        Index("ix_cameras_source_type", "source_type"),
    )


class DetectionEvent(BaseModelSoftDelete):
    """
    Object detection event record.

    Stores bounding box coordinates, confidence scores, class labels,
    and associated metadata for each detection.
    """

    __tablename__ = "detection_events"

    camera_id: Mapped[UUID] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frame_id: Mapped[UUID] = mapped_column(
        ForeignKey("frame_metadata.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Detection coordinates (normalized 0-1 relative to frame)
    x_min: Mapped[float] = mapped_column(Float, nullable=False)
    y_min: Mapped[float] = mapped_column(Float, nullable=False)
    x_max: Mapped[float] = mapped_column(Float, nullable=False)
    y_max: Mapped[float] = mapped_column(Float, nullable=False)

    # Class info
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Detection metadata
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    inference_time_ms: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    camera: Mapped["Camera"] = relationship(back_populates="events")
    frame: Mapped["FrameMetadata"] = relationship(back_populates="detections")

    __table_args__ = (
        Index("ix_detection_events_camera_time", "camera_id", "created_at"),
        Index("ix_detection_events_class_conf", "class_id", "confidence"),
        Index("ix_detection_events_frame", "frame_id"),
    )


class FrameMetadata(BaseModelSoftDelete):
    """
    Metadata for processed video frames.

    Stores frame-level information including timestamps, processing
    metrics, and storage references.
    """

    __tablename__ = "frame_metadata"

    camera_id: Mapped[UUID] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Frame identification
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Storage reference
    s3_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    s3_bucket: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Frame properties
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="jpeg")

    # Processing metrics
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False)
    inference_time_ms: Mapped[float] = mapped_column(Float, nullable=False)
    detection_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    anomaly_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    camera: Mapped["Camera"] = relationship(back_populates="frames")
    detections: Mapped[List["DetectionEvent"]] = relationship(
        back_populates="frame", lazy="dynamic", cascade="all, delete-orphan"
    )
    audio_analysis: Mapped[Optional["AudioAnalysis"]] = relationship(
        back_populates="frame", uselist=False
    )

    __table_args__ = (
        Index("ix_frame_metadata_camera_time", "camera_id", "timestamp"),
        Index("ix_frame_metadata_anomaly", "is_anomaly", "timestamp"),
        Index("ix_frame_metadata_frame_num", "camera_id", "frame_number"),
    )


class AudioAnalysis(BaseModel):
    """
    Audio analysis results for multi-modal detection.

    Stores audio features and anomaly scores synchronized with video frames.
    """

    __tablename__ = "audio_analysis"

    frame_id: Mapped[UUID] = mapped_column(
        ForeignKey("frame_metadata.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Audio features
    mfcc_features: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    spectral_centroid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spectral_rolloff: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    zero_crossing_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rms_energy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Anomaly scoring
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Model metadata
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    inference_time_ms: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    frame: Mapped["FrameMetadata"] = relationship(back_populates="audio_analysis")

    __table_args__ = (
        Index("ix_audio_analysis_anomaly", "is_anomaly", "anomaly_score"),
    )


class SystemTelemetry(BaseModel):
    """
    System performance telemetry.

    Tracks pipeline latency, throughput, resource utilization,
    and error rates for monitoring and alerting.
    """

    __tablename__ = "system_telemetry"

    # Component identification
    component: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g., 'vision_pipeline', 'stream_processor', 'api_gateway'

    instance_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Metrics
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g., 'inference_latency_ms', 'frames_per_second', 'memory_usage_mb'

    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_unit: Mapped[str] = mapped_column(String(50), nullable=False)

    # Labels for Prometheus-style dimensions
    labels: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_telemetry_component_metric_time", "component", "metric_name", "timestamp"),
        Index("ix_telemetry_instance_time", "instance_id", "timestamp"),
    )


class Alert(BaseModelSoftDelete):
    """
    Alert/notification record for anomaly events.

    Tracks triggered alerts, their severity, acknowledgment status,
    and resolution.
    """

    __tablename__ = "alerts"

    camera_id: Mapped[UUID] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frame_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("frame_metadata.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g., 'object_detection', 'audio_anomaly', 'zone_breach', 'system_error'

    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    # critical, high, medium, low, info

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Alert metadata as JSON
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # State management
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_alerts_camera_severity_time", "camera_id", "severity", "created_at"),
        Index("ix_alerts_state_time", "is_acknowledged", "is_resolved", "created_at"),
    )
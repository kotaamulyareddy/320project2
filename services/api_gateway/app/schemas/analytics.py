"""
Pydantic schemas for API request/response validation.

Defines data contracts for analytics endpoints, WebSocket messages,
and internal service communication.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict


# =============================================================================
# Base Schemas
# =============================================================================

class CameraBase(BaseModel):
    """Base camera schema with common fields."""
    name: str = Field(..., min_length=1, max_length=255, description="Unique camera name")
    description: Optional[str] = Field(None, max_length=1000, description="Camera description")
    source_url: str = Field(..., max_length=500, description="Video source URL (RTSP, HTTP, file path, or device index)")
    source_type: Literal["rtsp", "http", "file", "webcam"] = Field("rtsp", description="Source type")
    fps: Optional[float] = Field(None, gt=0, le=120, description="Expected frames per second")
    resolution_width: Optional[int] = Field(None, gt=0, le=7680, description="Frame width in pixels")
    resolution_height: Optional[int] = Field(None, gt=0, le=4320, description="Frame height in pixels")
    zones_config: Optional[Dict[str, Any]] = Field(None, description="Zone/ROI configuration as JSON")


class CameraCreate(CameraBase):
    """Schema for creating a new camera."""
    pass


class CameraUpdate(BaseModel):
    """Schema for updating camera configuration."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    source_url: Optional[str] = Field(None, max_length=500)
    source_type: Optional[Literal["rtsp", "http", "file", "webcam"]] = None
    is_active: Optional[bool] = None
    fps: Optional[float] = Field(None, gt=0, le=120)
    resolution_width: Optional[int] = Field(None, gt=0, le=7680)
    resolution_height: Optional[int] = Field(None, gt=0, le=4320)
    zones_config: Optional[Dict[str, Any]] = None


class CameraResponse(CameraBase):
    """Schema for camera response."""
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Detection Event Schemas
# =============================================================================

class DetectionEventBase(BaseModel):
    """Base detection event schema."""
    x_min: float = Field(..., ge=0.0, le=1.0, description="Normalized left coordinate")
    y_min: float = Field(..., ge=0.0, le=1.0, description="Normalized top coordinate")
    x_max: float = Field(..., ge=0.0, le=1.0, description="Normalized right coordinate")
    y_max: float = Field(..., ge=0.0, le=1.0, description="Normalized bottom coordinate")
    class_id: int = Field(..., ge=0, description="Class index")
    class_name: str = Field(..., min_length=1, max_length=100, description="Class label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    model_name: str = Field(..., max_length=100)
    model_version: str = Field(..., max_length=50)
    inference_time_ms: float = Field(..., ge=0.0)

    @field_validator("x_max")
    @classmethod
    def validate_x_max(cls, v: float, info) -> float:
        if "x_min" in info.data and v <= info.data["x_min"]:
            raise ValueError("x_max must be greater than x_min")
        return v

    @field_validator("y_max")
    @classmethod
    def validate_y_max(cls, v: float, info) -> float:
        if "y_min" in info.data and v <= info.data["y_min"]:
            raise ValueError("y_max must be greater than y_min")
        return v


class DetectionEventCreate(DetectionEventBase):
    """Schema for creating a detection event."""
    camera_id: UUID
    frame_id: UUID


class DetectionEventResponse(DetectionEventBase):
    """Schema for detection event response."""
    id: UUID
    camera_id: UUID
    frame_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Frame Metadata Schemas
# =============================================================================

class FrameMetadataBase(BaseModel):
    """Base frame metadata schema."""
    frame_number: int = Field(..., ge=0)
    timestamp: datetime
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    format: str = Field("jpeg", max_length=20)
    processing_time_ms: float = Field(..., ge=0.0)
    inference_time_ms: float = Field(..., ge=0.0)
    detection_count: int = Field(0, ge=0)
    anomaly_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_anomaly: bool = False


class FrameMetadataCreate(FrameMetadataBase):
    """Schema for creating frame metadata."""
    camera_id: UUID
    s3_key: Optional[str] = None
    s3_bucket: Optional[str] = None


class FrameMetadataResponse(FrameMetadataBase):
    """Schema for frame metadata response."""
    id: UUID
    camera_id: UUID
    s3_key: Optional[str] = None
    s3_bucket: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Audio Analysis Schemas
# =============================================================================

class AudioAnalysisBase(BaseModel):
    """Base audio analysis schema."""
    mfcc_features: Optional[List[List[float]]] = None
    spectral_centroid: Optional[float] = None
    spectral_rolloff: Optional[float] = None
    zero_crossing_rate: Optional[float] = None
    rms_energy: Optional[float] = None
    anomaly_score: float = Field(0.0, ge=0.0, le=1.0)
    is_anomaly: bool = False
    model_name: str = Field(..., max_length=100)
    model_version: str = Field(..., max_length=50)
    inference_time_ms: float = Field(..., ge=0.0)


class AudioAnalysisCreate(AudioAnalysisBase):
    """Schema for creating audio analysis."""
    frame_id: UUID


class AudioAnalysisResponse(AudioAnalysisBase):
    """Schema for audio analysis response."""
    id: UUID
    frame_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Alert Schemas
# =============================================================================

class AlertBase(BaseModel):
    """Base alert schema."""
    alert_type: str = Field(..., max_length=50)
    severity: Literal["critical", "high", "medium", "low", "info"] = "info"
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = None


class AlertCreate(AlertBase):
    """Schema for creating an alert."""
    camera_id: UUID
    frame_id: Optional[UUID] = None


class AlertUpdate(BaseModel):
    """Schema for updating alert state."""
    is_acknowledged: Optional[bool] = None
    acknowledged_by: Optional[str] = None
    is_resolved: Optional[bool] = None
    resolved_by: Optional[str] = None


class AlertResponse(AlertBase):
    """Schema for alert response."""
    id: UUID
    camera_id: UUID
    frame_id: Optional[UUID] = None
    is_acknowledged: bool
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    is_resolved: bool
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# WebSocket Message Schemas
# =============================================================================

class WSMessageType(str):
    """WebSocket message type constants."""
    FRAME_METADATA = "frame_metadata"
    DETECTION_EVENT = "detection_event"
    AUDIO_ANALYSIS = "audio_analysis"
    ALERT = "alert"
    TELEMETRY = "telemetry"
    HEARTBEAT = "heartbeat"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    ERROR = "error"
    ACK = "ack"


class WSFrameMetadata(BaseModel):
    """WebSocket frame metadata payload."""
    type: Literal[WSMessageType.FRAME_METADATA] = WSMessageType.FRAME_METADATA
    camera_id: UUID
    frame_id: UUID
    frame_number: int
    timestamp: datetime
    width: int
    height: int
    detection_count: int
    anomaly_score: Optional[float] = None
    is_anomaly: bool = False
    processing_time_ms: float
    inference_time_ms: float


class WSDetectionEvent(BaseModel):
    """WebSocket detection event payload."""
    type: Literal[WSMessageType.DETECTION_EVENT] = WSMessageType.DETECTION_EVENT
    camera_id: UUID
    frame_id: UUID
    detection_id: UUID
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    class_id: int
    class_name: str
    confidence: float
    inference_time_ms: float


class WSAudioAnalysis(BaseModel):
    """WebSocket audio analysis payload."""
    type: Literal[WSMessageType.AUDIO_ANALYSIS] = WSMessageType.AUDIO_ANALYSIS
    camera_id: UUID
    frame_id: UUID
    anomaly_score: float
    is_anomaly: bool
    spectral_centroid: Optional[float] = None
    rms_energy: Optional[float] = None
    inference_time_ms: float


class WSAlert(BaseModel):
    """WebSocket alert payload."""
    type: Literal[WSMessageType.ALERT] = WSMessageType.ALERT
    alert_id: UUID
    camera_id: UUID
    frame_id: Optional[UUID] = None
    alert_type: str
    severity: str
    title: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime


class WSTelemetry(BaseModel):
    """WebSocket telemetry payload."""
    type: Literal[WSMessageType.TELEMETRY] = WSMessageType.TELEMETRY
    component: str
    instance_id: str
    metric_name: str
    metric_value: float
    metric_unit: str
    labels: Optional[Dict[str, Any]] = None
    timestamp: datetime


class WSHeartbeat(BaseModel):
    """WebSocket heartbeat payload."""
    type: Literal[WSMessageType.HEARTBEAT] = WSMessageType.HEARTBEAT
    timestamp: datetime
    server_time: datetime


class WSSubscribe(BaseModel):
    """WebSocket subscribe request."""
    type: Literal[WSMessageType.SUBSCRIBE] = WSMessageType.SUBSCRIBE
    camera_ids: List[UUID] = Field(default_factory=list)
    event_types: List[str] = Field(default_factory=list)


class WSUnsubscribe(BaseModel):
    """WebSocket unsubscribe request."""
    type: Literal[WSMessageType.UNSUBSCRIBE] = WSMessageType.UNSUBSCRIBE
    camera_ids: List[UUID] = Field(default_factory=list)
    event_types: List[str] = Field(default_factory=list)


class WSError(BaseModel):
    """WebSocket error response."""
    type: Literal[WSMessageType.ERROR] = WSMessageType.ERROR
    code: int
    message: str
    details: Optional[Dict[str, Any]] = None


class WSAck(BaseModel):
    """WebSocket acknowledgment."""
    type: Literal[WSMessageType.ACK] = WSMessageType.ACK
    request_id: Optional[str] = None
    status: str = "ok"


# Union type for all WebSocket messages
WSMessage = (
    WSFrameMetadata
    | WSDetectionEvent
    | WSAudioAnalysis
    | WSAlert
    | WSTelemetry
    | WSHeartbeat
    | WSSubscribe
    | WSUnsubscribe
    | WSError
    | WSAck
)


# =============================================================================
# Telemetry Schemas
# =============================================================================

class TelemetryPoint(BaseModel):
    """Single telemetry data point."""
    metric_name: str
    metric_value: float
    metric_unit: str
    labels: Optional[Dict[str, str]] = None
    timestamp: datetime


class TelemetryQuery(BaseModel):
    """Query parameters for telemetry retrieval."""
    component: Optional[str] = None
    metric_name: Optional[str] = None
    instance_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(1000, ge=1, le=10000)


class TelemetryResponse(BaseModel):
    """Telemetry query response."""
    data: List[TelemetryPoint]
    count: int
    component: Optional[str] = None
    metric_name: Optional[str] = None


# =============================================================================
# Pagination & Filtering
# =============================================================================

class PaginationParams(BaseModel):
    """Standard pagination parameters."""
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(cls, items: List[Any], total: int, params: PaginationParams) -> "PaginatedResponse":
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )


class CameraFilterParams(BaseModel):
    """Filter parameters for camera queries."""
    is_active: Optional[bool] = None
    source_type: Optional[str] = None
    search: Optional[str] = None


class DetectionFilterParams(BaseModel):
    """Filter parameters for detection queries."""
    camera_id: Optional[UUID] = None
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class AlertFilterParams(BaseModel):
    """Filter parameters for alert queries."""
    camera_id: Optional[UUID] = None
    alert_type: Optional[str] = None
    severity: Optional[str] = None
    is_acknowledged: Optional[bool] = None
    is_resolved: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
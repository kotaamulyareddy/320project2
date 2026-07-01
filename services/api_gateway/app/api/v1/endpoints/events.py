"""
Event Management Endpoints.

Provides access to detection events, frame metadata, and alerts.
"""

from typing import List, Optional
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.analytics import DetectionEvent, FrameMetadata, Alert, AudioAnalysis
from app.schemas.analytics import (
    DetectionEventResponse, DetectionFilterParams, PaginationParams,
    PaginatedResponse, FrameMetadataResponse, AlertResponse, AlertFilterParams,
    AudioAnalysisResponse,
)

router = APIRouter()


@router.get("/detections", response_model=PaginatedResponse[DetectionEventResponse], summary="List Detection Events")
async def list_detections(
    pagination: PaginationParams = Depends(),
    filters: DetectionFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[DetectionEventResponse]:
    """
    List detection events with pagination and filtering.

    Args:
        pagination: Pagination parameters
        filters: Filter parameters
        db: Database session

    Returns:
        Paginated list of detection events
    """
    query = select(DetectionEvent)

    # Apply filters
    if filters.camera_id:
        query = query.where(DetectionEvent.camera_id == filters.camera_id)
    if filters.class_id:
        query = query.where(DetectionEvent.class_id == filters.class_id)
    if filters.class_name:
        query = query.where(DetectionEvent.class_name.ilike(f"%{filters.class_name}%"))
    if filters.min_confidence:
        query = query.where(DetectionEvent.confidence >= filters.min_confidence)
    if filters.start_time:
        query = query.where(DetectionEvent.created_at >= filters.start_time)
    if filters.end_time:
        query = query.where(DetectionEvent.created_at <= filters.end_time)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.offset(pagination.offset).limit(pagination.page_size).order_by(DetectionEvent.created_at.desc())

    result = await db.execute(query)
    events = result.scalars().all()

    return PaginatedResponse.create(
        items=[DetectionEventResponse.model_validate(e) for e in events],
        total=total,
        params=pagination,
    )


@router.get("/detections/{event_id}", response_model=DetectionEventResponse, summary="Get Detection Event")
async def get_detection(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DetectionEventResponse:
    """
    Get a detection event by ID.

    Args:
        event_id: Detection event UUID
        db: Database session

    Returns:
        Detection event details

    Raises:
        HTTPException: If detection event not found
    """
    event = await db.get(DetectionEvent, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection event with id {event_id} not found"
        )
    return DetectionEventResponse.model_validate(event)


@router.get("/frames", response_model=PaginatedResponse[FrameMetadataResponse], summary="List Frames")
async def list_frames(
    pagination: PaginationParams = Depends(),
    camera_id: Optional[UUID] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[FrameMetadataResponse]:
    """
    List processed frames with pagination and filtering.

    Args:
        pagination: Pagination parameters
        camera_id: Filter by camera
        start_time: Filter by start time
        end_time: Filter by end time
        db: Database session

    Returns:
        Paginated list of frame metadata
    """
    query = select(FrameMetadata)

    if camera_id:
        query = query.where(FrameMetadata.camera_id == camera_id)
    if start_time:
        query = query.where(FrameMetadata.timestamp >= start_time)
    if end_time:
        query = query.where(FrameMetadata.timestamp <= end_time)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.offset(pagination.offset).limit(pagination.page_size).order_by(FrameMetadata.timestamp.desc())

    result = await db.execute(query)
    frames = result.scalars().all()

    return PaginatedResponse.create(
        items=[FrameMetadataResponse.model_validate(f) for f in frames],
        total=total,
        params=pagination,
    )


@router.get("/frames/{frame_id}", response_model=FrameMetadataResponse, summary="Get Frame")
async def get_frame(
    frame_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FrameMetadataResponse:
    """
    Get frame metadata by ID.

    Args:
        frame_id: Frame metadata UUID
        db: Database session

    Returns:
        Frame metadata details

    Raises:
        HTTPException: If frame not found
    """
    frame = await db.get(FrameMetadata, frame_id)
    if not frame:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frame with id {frame_id} not found"
        )
    return FrameMetadataResponse.model_validate(frame)


@router.get("/alerts", response_model=PaginatedResponse[AlertResponse], summary="List Alerts")
async def list_alerts(
    pagination: PaginationParams = Depends(),
    filters: AlertFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AlertResponse]:
    """
    List alerts with pagination and filtering.

    Args:
        pagination: Pagination parameters
        filters: Filter parameters
        db: Database session

    Returns:
        Paginated list of alerts
    """
    query = select(Alert)

    # Apply filters
    if filters.camera_id:
        query = query.where(Alert.camera_id == filters.camera_id)
    if filters.alert_type:
        query = query.where(Alert.alert_type == filters.alert_type)
    if filters.severity:
        query = query.where(Alert.severity == filters.severity)
    if filters.is_acknowledged is not None:
        query = query.where(Alert.is_acknowledged == filters.is_acknowledged)
    if filters.is_resolved is not None:
        query = query.where(Alert.is_resolved == filters.is_resolved)
    if filters.start_time:
        query = query.where(Alert.created_at >= filters.start_time)
    if filters.end_time:
        query = query.where(Alert.created_at <= filters.end_time)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.offset(pagination.offset).limit(pagination.page_size).order_by(Alert.created_at.desc())

    result = await db.execute(query)
    alerts = result.scalars().all()

    return PaginatedResponse.create(
        items=[AlertResponse.model_validate(a) for a in alerts],
        total=total,
        params=pagination,
    )


@router.get("/alerts/{alert_id}", response_model=AlertResponse, summary="Get Alert")
async def get_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """
    Get an alert by ID.

    Args:
        alert_id: Alert UUID
        db: Database session

    Returns:
        Alert details

    Raises:
        HTTPException: If alert not found
    """
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found"
        )
    return AlertResponse.model_validate(alert)


@router.patch("/alerts/{alert_id}", response_model=AlertResponse, summary="Update Alert")
async def update_alert(
    alert_id: UUID,
    update_data: dict = Body(None),
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """
    Update alert state (acknowledge/resolve).

    Args:
        alert_id: Alert UUID
        update_data: Fields to update (is_acknowledged, is_resolved, etc.)
        db: Database session

    Returns:
        Updated alert

    Raises:
        HTTPException: If alert not found
    """
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found"
        )

    if update_data:
        for field, value in update_data.items():
            if hasattr(alert, field):
                setattr(alert, field, value)

    await db.commit()
    await db.refresh(alert)
    return AlertResponse.model_validate(alert)


@router.get("/audio/{frame_id}", response_model=AudioAnalysisResponse, summary="Get Audio Analysis")
async def get_audio_analysis(
    frame_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AudioAnalysisResponse:
    """
    Get audio analysis results for a frame.

    Args:
        frame_id: Frame metadata UUID
        db: Database session

    Returns:
        Audio analysis details

    Raises:
        HTTPException: If audio analysis not found
    """
    audio = await db.execute(
        select(AudioAnalysis).where(AudioAnalysis.frame_id == frame_id)
    ).scalar_one_or_none()

    if not audio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio analysis for frame {frame_id} not found"
        )
    return AudioAnalysisResponse.model_validate(audio)
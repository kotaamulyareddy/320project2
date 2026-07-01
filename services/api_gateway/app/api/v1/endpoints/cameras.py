"""
Camera Management Endpoints.

Provides CRUD operations for camera/video source configuration.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.analytics import Camera
from app.schemas.analytics import (
    CameraCreate, CameraUpdate, CameraResponse,
    PaginationParams, PaginatedResponse, CameraFilterParams,
)

router = APIRouter()


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED, summary="Create Camera")
async def create_camera(
    camera_data: CameraCreate,
    db: AsyncSession = Depends(get_db),
) -> CameraResponse:
    """
    Create a new camera/video source.

    Args:
        camera_data: Camera configuration
        db: Database session

    Returns:
        Created camera with generated ID and timestamps

    Raises:
        HTTPException: If camera name already exists
    """
    # Check for duplicate name
    existing = await db.execute(
        select(Camera).where(Camera.name == camera_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Camera with name '{camera_data.name}' already exists"
        )

    camera = Camera(**camera_data.model_dump())
    db.add(camera)
    await db.commit()
    await db.refresh(camera)
    return CameraResponse.model_validate(camera)


@router.get("", response_model=PaginatedResponse[CameraResponse], summary="List Cameras")
async def list_cameras(
    pagination: PaginationParams = Depends(),
    filters: CameraFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CameraResponse]:
    """
    List cameras with pagination and filtering.

    Args:
        pagination: Pagination parameters
        filters: Filter parameters
        db: Database session

    Returns:
        Paginated list of cameras
    """
    query = select(Camera)

    # Apply filters
    if filters.is_active is not None:
        query = query.where(Camera.is_active == filters.is_active)
    if filters.source_type:
        query = query.where(Camera.source_type == filters.source_type)
    if filters.search:
        search_term = f"%{filters.search}%"
        query = query.where(
            or_(
                Camera.name.ilike(search_term),
                Camera.description.ilike(search_term),
                Camera.source_url.ilike(search_term),
            )
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.offset(pagination.offset).limit(pagination.page_size).order_by(Camera.created_at.desc())

    result = await db.execute(query)
    cameras = result.scalars().all()

    return PaginatedResponse.create(
        items=[CameraResponse.model_validate(c) for c in cameras],
        total=total,
        params=pagination,
    )


@router.get("/{camera_id}", response_model=CameraResponse, summary="Get Camera")
async def get_camera(
    camera_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CameraResponse:
    """
    Get a camera by ID.

    Args:
        camera_id: Camera UUID
        db: Database session

    Returns:
        Camera details

    Raises:
        HTTPException: If camera not found
    """
    camera = await db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found"
        )
    return CameraResponse.model_validate(camera)


@router.patch("/{camera_id}", response_model=CameraResponse, summary="Update Camera")
async def update_camera(
    camera_id: UUID,
    camera_data: CameraUpdate,
    db: AsyncSession = Depends(get_db),
) -> CameraResponse:
    """
    Update camera configuration.

    Args:
        camera_id: Camera UUID
        camera_data: Fields to update
        db: Database session

    Returns:
        Updated camera

    Raises:
        HTTPException: If camera not found or name conflicts
    """
    camera = await db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found"
        )

    # Check name uniqueness if changing
    if camera_data.name and camera_data.name != camera.name:
        existing = await db.execute(
            select(Camera).where(Camera.name == camera_data.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Camera with name '{camera_data.name}' already exists"
            )

    # Update fields
    update_data = camera_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(camera, field, value)

    await db.commit()
    await db.refresh(camera)
    return CameraResponse.model_validate(camera)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Camera")
async def delete_camera(
    camera_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Soft delete a camera (marks as inactive).

    Args:
        camera_id: Camera UUID
        db: Database session

    Raises:
        HTTPException: If camera not found
    """
    camera = await db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found"
        )

    camera.is_active = False
    await db.commit()


@router.post("/{camera_id}/activate", response_model=CameraResponse, summary="Activate Camera")
async def activate_camera(
    camera_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CameraResponse:
    """
    Activate a camera.

    Args:
        camera_id: Camera UUID
        db: Database session

    Returns:
        Updated camera

    Raises:
        HTTPException: If camera not found
    """
    camera = await db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with id {camera_id} not found"
        )

    camera.is_active = True
    await db.commit()
    await db.refresh(camera)
    return CameraResponse.model_validate(camera)
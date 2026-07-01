"""
Telemetry and Metrics Endpoints.

Provides access to system telemetry, performance metrics, and monitoring data.
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.analytics import SystemTelemetry
from app.schemas.analytics import (
    TelemetryQuery, TelemetryResponse, TelemetryPoint,
)

router = APIRouter()


@router.get("/points", response_model=TelemetryResponse, summary="Query Telemetry Points")
async def query_telemetry(
    component: Optional[str] = Query(None, description="Component name filter"),
    metric_name: Optional[str] = Query(None, description="Metric name filter"),
    instance_id: Optional[str] = Query(None, description="Instance ID filter"),
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of points to return"),
    db: AsyncSession = Depends(get_db),
) -> TelemetryResponse:
    """
    Query system telemetry points with filtering.

    Args:
        component: Filter by component name
        metric_name: Filter by metric name
        instance_id: Filter by instance ID
        start_time: Filter by start time
        end_time: Filter by end time
        limit: Maximum number of points to return
        db: Database session

    Returns:
        Telemetry points matching the filters
    """
    query = select(SystemTelemetry)

    # Apply filters
    if component:
        query = query.where(SystemTelemetry.component == component)
    if metric_name:
        query = query.where(SystemTelemetry.metric_name == metric_name)
    if instance_id:
        query = query.where(SystemTelemetry.instance_id == instance_id)
    if start_time:
        query = query.where(SystemTelemetry.timestamp >= start_time)
    if end_time:
        query = query.where(SystemTelemetry.timestamp <= end_time)

    # Apply ordering and limit
    query = query.order_by(SystemTelemetry.timestamp.desc()).limit(limit)

    result = await db.execute(query)
    points = result.scalars().all()

    # Convert to schema objects
    telemetry_points = []
    for point in points:
        telemetry_points.append(
            TelemetryPoint(
                metric_name=point.metric_name,
                metric_value=point.metric_value,
                metric_unit=point.metric_unit,
                labels=point.labels,
                timestamp=point.timestamp,
            )
        )

    return TelemetryResponse(
        data=telemetry_points,
        count=len(telemetry_points),
        component=component,
        metric_name=metric_name,
    )


@router.get("/components", response_model=List[str], summary="List Components")
async def list_components(db: AsyncSession = Depends(get_db)) -> List[str]:
    """
    Get list of all components that have reported telemetry.

    Args:
        db: Database session

    Returns:
        List of component names
    """
    result = await db.execute(
        select(func.distinct(SystemTelemetry.component))
    )
    components = result.scalars().all()
    return list(components)


@router.get("/instances/{component}", response_model=List[str], summary="List Instances")
async def list_instances(
    component: str,
    db: AsyncSession = Depends(get_db),
) -> List[str]:
    """
    Get list of all instances for a specific component.

    Args:
        component: Component name
        db: Database session

    Returns:
        List of instance IDs
    """
    result = await db.execute(
        select(func.distinct(SystemTelemetry.instance_id))
        .where(SystemTelemetry.component == component)
    )
    instances = result.scalars().all()
    return list(instances)
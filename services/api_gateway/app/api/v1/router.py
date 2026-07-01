"""
API v1 Router Configuration.

Aggregates all version 1 endpoints and mounts them under the
API version prefix.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import cameras, events, stream, telemetry, health

api_router = APIRouter()

# Health & System
api_router.include_router(health.router, prefix="/health", tags=["health"])

# Camera Management
api_router.include_router(cameras.router, prefix="/cameras", tags=["cameras"])

# Detection Events
api_router.include_router(events.router, prefix="/events", tags=["events"])

# Real-time WebSocket Stream
api_router.include_router(stream.router, prefix="/stream", tags=["stream"])

# Telemetry & Metrics
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
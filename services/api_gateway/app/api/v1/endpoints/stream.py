"""
WebSocket Streaming Endpoints.

Provides real-time WebSocket connections for broadcasting
frame metadata, detection events, and alerts to frontend clients.
Supports subscription filtering by camera and event type.
"""

import asyncio
import json
import uuid
from datetime import datetime, UTC
from typing import Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException, status
from fastapi.websockets import WebSocketState
import redis.asyncio as redis

from app.core.config import settings
from app.schemas.analytics import (
    WSMessage, WSMessageType, WSFrameMetadata, WSDetectionEvent,
    WSAudioAnalysis, WSAlert, WSTelemetry, WSHeartbeat,
    WSSubscribe, WSUnsubscribe, WSError, WSAck,
    UUID, ValidationError
)
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class ConnectionManager:
    """
    Manages active WebSocket connections with subscription support.

    Tracks connections, their subscriptions, and handles message broadcasting
    with backpressure handling and automatic cleanup of dead connections.
    """

    def __init__(self):
        # Active connections: websocket -> connection_info
        self.connections: Dict[WebSocket, Dict] = {}
        # Subscription index: camera_id -> set of websockets
        self.camera_subscriptions: Dict[UUID, Set[WebSocket]] = {}
        # Subscription index: event_type -> set of websockets
        self.event_type_subscriptions: Dict[str, Set[WebSocket]] = {}
        # Redis pubsub for cross-process message distribution
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize Redis connection and start background tasks."""
        self.redis_client = redis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
            decode_responses=True,
        )
        self.pubsub = self.redis_client.pubsub()
        # Subscribe to internal channels
        await self.pubsub.subscribe(
            "ws:frame_metadata",
            "ws:detection_events",
            "ws:audio_analysis",
            "ws:alerts",
            "ws:telemetry",
        )
        # Start Redis listener
        self._listener_task = asyncio.create_task(self._redis_listener())
        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def shutdown(self) -> None:
        """Cleanup connections and background tasks."""
        # Cancel background tasks
        for task in [self._listener_task, self._heartbeat_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close all WebSocket connections
        for ws in list(self.connections.keys()):
            try:
                await ws.close(code=1001, reason="Server shutting down")
            except Exception:
                pass

        # Cleanup Redis
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.aclose()

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance
            client_id: Unique client identifier
        """
        await websocket.accept()
        self.connections[websocket] = {
            "client_id": client_id,
            "connected_at": datetime.now(UTC),
            "camera_ids": set(),
            "event_types": set(),
            "last_heartbeat": datetime.now(UTC),
        }

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection and clean up subscriptions.

        Args:
            websocket: WebSocket to remove
        """
        info = self.connections.pop(websocket, None)
        if not info:
            return

        # Remove from camera subscriptions
        for cam_id in info.get("camera_ids", set()):
            subs = self.camera_subscriptions.get(cam_id, set())
            subs.discard(websocket)
            if not subs:
                self.camera_subscriptions.pop(cam_id, None)

        # Remove from event type subscriptions
        for evt_type in info.get("event_types", set()):
            subs = self.event_type_subscriptions.get(evt_type, set())
            subs.discard(websocket)
            if not subs:
                self.event_type_subscriptions.pop(evt_type, None)

    async def subscribe(self, websocket: WebSocket, camera_ids: List[UUID], event_types: List[str]) -> None:
        """
        Subscribe a connection to specific cameras and event types.

        Args:
            websocket: WebSocket to subscribe
            camera_ids: List of camera UUIDs to subscribe to
            event_types: List of event types to receive
        """
        info = self.connections.get(websocket)
        if not info:
            return

        # Add camera subscriptions
        for cam_id in camera_ids:
            info["camera_ids"].add(cam_id)
            if cam_id not in self.camera_subscriptions:
                self.camera_subscriptions[cam_id] = set()
            self.camera_subscriptions[cam_id].add(websocket)

        # Add event type subscriptions
        for evt_type in event_types:
            info["event_types"].add(evt_type)
            if evt_type not in self.event_type_subscriptions:
                self.event_type_subscriptions[evt_type] = set()
            self.event_type_subscriptions[evt_type].add(websocket)

    async def unsubscribe(self, websocket: WebSocket, camera_ids: List[UUID], event_types: List[str]) -> None:
        """
        Unsubscribe a connection from cameras and event types.

        Args:
            websocket: WebSocket to unsubscribe
            camera_ids: List of camera UUIDs to unsubscribe from
            event_types: List of event types to stop receiving
        """
        info = self.connections.get(websocket)
        if not info:
            return

        for cam_id in camera_ids:
            info["camera_ids"].discard(cam_id)
            subs = self.camera_subscriptions.get(cam_id, set())
            subs.discard(websocket)
            if not subs:
                self.camera_subscriptions.pop(cam_id, None)

        for evt_type in event_types:
            info["event_types"].discard(evt_type)
            subs = self.event_type_subscriptions.get(evt_type, set())
            subs.discard(websocket)
            if not subs:
                self.event_type_subscriptions.pop(evt_type, None)

    async def send_personal_message(self, websocket: WebSocket, message: WSMessage) -> bool:
        """
        Send a message to a specific WebSocket connection.

        Args:
            websocket: Target WebSocket
            message: Message to send

        Returns:
            True if sent successfully, False if connection is dead
        """
        if websocket.client_state != WebSocketState.CONNECTED:
            return False

        try:
            await websocket.send_text(message.model_dump_json())
            return True
        except Exception:
            return False

    async def broadcast_to_camera(self, camera_id: UUID, message: WSMessage) -> int:
        """
        Broadcast a message to all connections subscribed to a camera.

        Args:
            camera_id: Camera UUID
            message: Message to broadcast

        Returns:
            Number of connections the message was sent to
        """
        subscribers = self.camera_subscriptions.get(camera_id, set())
        if not subscribers:
            return 0

        sent = 0
        dead_connections = []

        for ws in subscribers:
            if await self.send_personal_message(ws, message):
                sent += 1
            else:
                dead_connections.append(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(ws)

        return sent

    async def broadcast_to_event_type(self, event_type: str, message: WSMessage) -> int:
        """
        Broadcast a message to all connections subscribed to an event type.

        Args:
            event_type: Event type string
            message: Message to broadcast

        Returns:
            Number of connections the message was sent to
        """
        subscribers = self.event_type_subscriptions.get(event_type, set())
        if not subscribers:
            return 0

        sent = 0
        dead_connections = []

        for ws in subscribers:
            if await self.send_personal_message(ws, message):
                sent += 1
            else:
                dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(ws)

        return sent

    async def broadcast_to_all(self, message: WSMessage) -> int:
        """
        Broadcast a message to all connected clients.

        Args:
            message: Message to broadcast

        Returns:
            Number of connections the message was sent to
        """
        sent = 0
        dead_connections = []

        for ws in list(self.connections.keys()):
            if await self.send_personal_message(ws, message):
                sent += 1
            else:
                dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(ws)

        return sent

    async def _redis_listener(self) -> None:
        """Background task listening for Redis pubsub messages."""
        if not self.pubsub:
            return

        try:
            async for message in self.pubsub.listen():
                if message["type"] != "message":
                    continue

                channel = message["channel"]
                data = message["data"]

                try:
                    payload = json.loads(data)
                    ws_message = self._parse_redis_message(channel, payload)
                    if ws_message:
                        await self._route_message(ws_message)
                except (json.JSONDecodeError, ValidationError) as e:
                    # Log error but continue
                    print(f"Failed to parse Redis message: {e}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Redis listener error: {e}")

    def _parse_redis_message(self, channel: str, payload: dict) -> Optional[WSMessage]:
        """Parse Redis pubsub message into WSMessage."""
        try:
            if channel == "ws:frame_metadata":
                return WSFrameMetadata(**payload)
            elif channel == "ws:detection_events":
                return WSDetectionEvent(**payload)
            elif channel == "ws:audio_analysis":
                return WSAudioAnalysis(**payload)
            elif channel == "ws:alerts":
                return WSAlert(**payload)
            elif channel == "ws:telemetry":
                return WSTelemetry(**payload)
        except ValidationError:
            pass
        return None

    async def _route_message(self, message: WSMessage) -> None:
        """Route incoming message to appropriate subscribers."""
        message_type = message.type

        if message_type == WSMessageType.FRAME_METADATA:
            await self.broadcast_to_camera(message.camera_id, message)
            await self.broadcast_to_event_type("frame_metadata", message)

        elif message_type == WSMessageType.DETECTION_EVENT:
            await self.broadcast_to_camera(message.camera_id, message)
            await self.broadcast_to_event_type("detection_event", message)

        elif message_type == WSMessageType.AUDIO_ANALYSIS:
            await self.broadcast_to_camera(message.camera_id, message)
            await self.broadcast_to_event_type("audio_analysis", message)

        elif message_type == WSMessageType.ALERT:
            await self.broadcast_to_camera(message.camera_id, message)
            await self.broadcast_to_event_type("alert", message)
            # Also broadcast to all for critical alerts
            if message.severity in ("critical", "high"):
                await self.broadcast_to_all(message)

        elif message_type == WSMessageType.TELEMETRY:
            await self.broadcast_to_event_type("telemetry", message)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to all connections."""
        while True:
            try:
                await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL)
                heartbeat = WSHeartbeat(
                    timestamp=datetime.now(UTC),
                    server_time=datetime.now(UTC),
                )
                await self.broadcast_to_all(heartbeat)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"Heartbeat error: {e}")


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str = Query(default_factory=lambda: str(uuid.uuid4())),
    camera_ids: Optional[str] = Query(None, description="Comma-separated camera UUIDs"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
) -> None:
    """
    Main WebSocket endpoint for real-time streaming.

    Query Parameters:
        client_id: Optional client identifier (auto-generated if not provided)
        camera_ids: Comma-separated list of camera UUIDs to subscribe to
        event_types: Comma-separated list of event types to receive
            (frame_metadata, detection_event, audio_analysis, alert, telemetry)

    Message Format:
        All messages are JSON with a 'type' field indicating the message type.
        See schemas.analytics.WSMessage for complete message definitions.

    Example Subscription:
        {"type": "subscribe", "camera_ids": ["uuid1", "uuid2"], "event_types": ["detection_event", "alert"]}
    """
    # Parse query parameters
    cam_ids = []
    if camera_ids:
        try:
            cam_ids = [UUID(cid.strip()) for cid in camera_ids.split(",") if cid.strip()]
        except ValueError:
            await websocket.close(code=4000, reason="Invalid camera_ids format")
            return

    evt_types = []
    if event_types:
        evt_types = [et.strip() for et in event_types.split(",") if et.strip()]

    # Connect
    await manager.connect(websocket, client_id)

    # Apply initial subscriptions
    if cam_ids or evt_types:
        await manager.subscribe(websocket, cam_ids, evt_types)

    # Send connection acknowledgment
    ack = WSAck(request_id=client_id, status="connected")
    await manager.send_personal_message(websocket, ack)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == WSMessageType.SUBSCRIBE:
                    subscribe_msg = WSSubscribe(**message)
                    await manager.subscribe(websocket, subscribe_msg.camera_ids, subscribe_msg.event_types)
                    ack = WSAck(request_id=message.get("request_id"), status="subscribed")
                    await manager.send_personal_message(websocket, ack)

                elif msg_type == WSMessageType.UNSUBSCRIBE:
                    unsubscribe_msg = WSUnsubscribe(**message)
                    await manager.unsubscribe(websocket, unsubscribe_msg.camera_ids, unsubscribe_msg.event_types)
                    ack = WSAck(request_id=message.get("request_id"), status="unsubscribed")
                    await manager.send_personal_message(websocket, ack)

                elif msg_type == WSMessageType.HEARTBEAT:
                    # Client heartbeat - update last activity
                    info = manager.connections.get(websocket)
                    if info:
                        info["last_heartbeat"] = datetime.now(UTC)
                    ack = WSAck(request_id=message.get("request_id"), status="pong")
                    await manager.send_personal_message(websocket, ack)

                else:
                    error = WSError(code=4000, message=f"Unknown message type: {msg_type}")
                    await manager.send_personal_message(websocket, error)

            except ValidationError as e:
                error = WSError(code=4000, message="Invalid message format", details={"errors": e.errors()})
                await manager.send_personal_message(websocket, error)
            except json.JSONDecodeError:
                error = WSError(code=4000, message="Invalid JSON")
                await manager.send_personal_message(websocket, error)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


@router.get("/stats", summary="WebSocket Connection Statistics")
async def websocket_stats() -> dict:
    """
    Get current WebSocket connection statistics.

    Returns:
        Connection counts, subscription counts, and uptime info.
    """
    total_connections = len(manager.connections)
    camera_subs = sum(len(s) for s in manager.camera_subscriptions.values())
    event_subs = sum(len(s) for s in manager.event_type_subscriptions.values())

    connections_info = []
    for ws, info in manager.connections.items():
        connections_info.append({
            "client_id": info["client_id"],
            "connected_at": info["connected_at"].isoformat(),
            "camera_subscriptions": len(info["camera_ids"]),
            "event_subscriptions": len(info["event_types"]),
        })

    return {
        "total_connections": total_connections,
        "total_camera_subscriptions": camera_subs,
        "total_event_subscriptions": event_subs,
        "unique_cameras_subscribed": len(manager.camera_subscriptions),
        "unique_event_types_subscribed": len(manager.event_type_subscriptions),
        "connections": connections_info,
    }


# Dependency to get connection manager
def get_connection_manager() -> ConnectionManager:
    return manager


# Startup/Shutdown handlers (to be registered in main.py)
async def startup_websocket() -> None:
    """Initialize WebSocket manager on application startup."""
    await manager.initialize()


async def shutdown_websocket() -> None:
    """Cleanup WebSocket manager on application shutdown."""
    await manager.shutdown()
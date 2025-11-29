"""
WebSocket connection manager for real-time status updates.

Provides:
- Connection management per user
- Broadcasting status updates to connected clients
- Automatic cleanup of disconnected clients
"""
import asyncio
import json
from datetime import datetime
from typing import Optional
from collections import defaultdict

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.log.logging import logger


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.

    Connections are organized by user_id to allow targeted messaging.
    """

    def __init__(self):
        # Map of user_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        # Map of WebSocket -> user_id for reverse lookup
        self._websocket_to_user: dict[WebSocket, str] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to register.
            user_id: The user ID associated with this connection.
        """
        await websocket.accept()

        async with self._lock:
            self._connections[user_id].add(websocket)
            self._websocket_to_user[websocket] = user_id

        logger.info(
            f"WebSocket connected for user {user_id}. "
            f"Total connections for user: {len(self._connections[user_id])}"
        )

        # Send welcome message
        await self._send_message(websocket, {
            "type": "connected",
            "message": "Connected to status updates",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove.
        """
        async with self._lock:
            user_id = self._websocket_to_user.pop(websocket, None)
            if user_id and websocket in self._connections[user_id]:
                self._connections[user_id].discard(websocket)

                # Clean up empty user entries
                if not self._connections[user_id]:
                    del self._connections[user_id]

                logger.info(f"WebSocket disconnected for user {user_id}")

    async def broadcast_to_user(
        self,
        user_id: str,
        message: dict
    ) -> int:
        """
        Send a message to all connections for a specific user.

        Args:
            user_id: The user ID to send to.
            message: The message to send.

        Returns:
            Number of connections that received the message.
        """
        async with self._lock:
            connections = self._connections.get(user_id, set()).copy()

        if not connections:
            return 0

        sent_count = 0
        disconnected = []

        for websocket in connections:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await self._send_message(websocket, message)
                    sent_count += 1
                else:
                    disconnected.append(websocket)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                disconnected.append(websocket)

        # Clean up disconnected sockets
        for ws in disconnected:
            await self.disconnect(ws)

        return sent_count

    async def send_status_update(
        self,
        user_id: str,
        application_id: str,
        status: str,
        job_count: Optional[int] = None,
        error_reason: Optional[str] = None
    ) -> int:
        """
        Send an application status update to a user.

        Args:
            user_id: The user ID to notify.
            application_id: The application ID that changed.
            status: The new status.
            job_count: Optional job count.
            error_reason: Optional error reason if failed.

        Returns:
            Number of connections notified.
        """
        message = {
            "type": "status_update",
            "application_id": application_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        if job_count is not None:
            message["job_count"] = job_count

        if error_reason:
            message["error_reason"] = error_reason

        return await self.broadcast_to_user(user_id, message)

    async def send_batch_update(
        self,
        user_id: str,
        batch_id: str,
        status: str,
        total: int,
        processed: int,
        failed: int
    ) -> int:
        """
        Send a batch processing update to a user.

        Args:
            user_id: The user ID to notify.
            batch_id: The batch ID.
            status: The batch status.
            total: Total items in batch.
            processed: Number of processed items.
            failed: Number of failed items.

        Returns:
            Number of connections notified.
        """
        message = {
            "type": "batch_update",
            "batch_id": batch_id,
            "status": status,
            "total": total,
            "processed": processed,
            "failed": failed,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        return await self.broadcast_to_user(user_id, message)

    async def _send_message(self, websocket: WebSocket, message: dict) -> None:
        """Send a JSON message through a WebSocket."""
        await websocket.send_json(message)

    def get_connection_count(self, user_id: Optional[str] = None) -> int:
        """
        Get the number of active connections.

        Args:
            user_id: Optional user ID to get count for specific user.

        Returns:
            Number of active connections.
        """
        if user_id:
            return len(self._connections.get(user_id, set()))
        return sum(len(conns) for conns in self._connections.values())

    def get_connected_users(self) -> list[str]:
        """Get list of user IDs with active connections."""
        return list(self._connections.keys())


# Global connection manager instance
ws_manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, user_id: str) -> None:
    """
    Handle a WebSocket connection lifecycle.

    Args:
        websocket: The WebSocket connection.
        user_id: The authenticated user ID.
    """
    await ws_manager.connect(websocket, user_id)

    try:
        while True:
            # Keep connection alive and handle incoming messages
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # Ping every 30 seconds
                )

                # Handle ping/pong for keepalive
                if data == "ping":
                    await websocket.send_text("pong")

            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(websocket)

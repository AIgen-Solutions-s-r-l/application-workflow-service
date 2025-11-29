"""
WebSocket router for real-time status updates.

Provides WebSocket endpoints for:
- Application status updates
- Batch processing progress
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from jose import jwt, JWTError

from app.core.config import settings
from app.core.websocket_manager import handle_websocket, ws_manager
from app.log.logging import logger

router = APIRouter(tags=["websocket"])


async def get_user_from_token(token: str) -> str:
    """
    Validate JWT token and extract user ID.

    Args:
        token: JWT token string.

    Returns:
        User ID from token.

    Raises:
        HTTPException: If token is invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        user_id = payload.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return str(user_id)
    except JWTError as e:
        logger.warning(f"WebSocket auth failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


@router.websocket("/ws/status")
async def websocket_status_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token")
):
    """
    WebSocket endpoint for real-time application status updates.

    Connect with: ws://host/ws/status?token=<jwt_token>

    Messages received:
    - {"type": "connected", "message": "...", "timestamp": "..."}
    - {"type": "status_update", "application_id": "...", "status": "...", "timestamp": "..."}
    - {"type": "batch_update", "batch_id": "...", "status": "...", "total": N, "processed": N, "failed": N}
    - {"type": "ping", "timestamp": "..."}

    Send "ping" to receive "pong" for keepalive.
    """
    try:
        user_id = await get_user_from_token(token)
    except HTTPException:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await handle_websocket(websocket, user_id)


@router.get(
    "/ws/stats",
    summary="WebSocket connection statistics",
    description="Get statistics about active WebSocket connections."
)
async def websocket_stats():
    """
    Get WebSocket connection statistics.

    Returns:
        Connection statistics including total connections and connected users.
    """
    return {
        "total_connections": ws_manager.get_connection_count(),
        "connected_users": len(ws_manager.get_connected_users())
    }

"""
WebSocket manager with Redis Pub/Sub.

Architecture:
  - Each authenticated user opens ONE WS connection to /ws/{user_id}
  - When a notification is created, notification_service publishes to the
    Redis channel "notifications:{user_id}"
  - The manager listens to that channel and forwards the payload to the active WebSocket

This works with multiple server instances (horizontal scaling)
because the pub/sub passes through Redis, not local memory.
"""
import json
import logging
from typing import Any

from fastapi import WebSocket

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

_connections: dict[str, WebSocket] = {}
CHANNEL_PREFIX = "notifications"


async def connect(user_id: str, websocket: WebSocket) -> None:
    await websocket.accept()
    _connections[user_id] = websocket
    logger.info("WS connect: user=%s  total=%d", user_id, len(_connections))


def disconnect(user_id: str) -> None:
    _connections.pop(user_id, None)
    logger.info("WS disconnect: user=%s  total=%d", user_id, len(_connections))


async def send_to_user(user_id: str, payload: dict[str, Any]) -> None:
    """Sends a JSON message to the user's active WS connection (if it exists)."""
    ws = _connections.get(user_id)
    if ws:
        try:
            await ws.send_json(payload)
        except Exception as exc:
            logger.warning("Error sending WS to user=%s: %s", user_id, exc)
            disconnect(user_id)


def channel_for(user_id: str) -> str:
    return f"{CHANNEL_PREFIX}:{user_id}"


async def publish(user_id: str, payload: dict[str, Any]) -> None:
    """Publishes an event to Redis. All workers that listen will receive it."""
    redis = await get_redis()
    await redis.publish(channel_for(user_id), json.dumps(payload))


async def listen_and_forward(user_id: str, websocket: WebSocket) -> None:
    """
    Subscribes to the user's Redis channel and forwards each message
    to the WebSocket until the connection is closed.
    """
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel_for(user_id))

    try:
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            try:
                data = json.loads(raw["data"])
                await websocket.send_json(data)
            except Exception as exc:
                logger.warning("Error forwarding WS message: %s", exc)
                break
    finally:
        await pubsub.unsubscribe(channel_for(user_id))
        await pubsub.aclose()

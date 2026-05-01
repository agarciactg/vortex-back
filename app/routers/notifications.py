import asyncio
import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationOut, NotificationsListOut, UnreadCountOut
from app.services import notification_service
from app.websockets import manager as ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "",
    response_model=NotificationsListOut,
    summary="List notifications",
    description=(
        "Returns the notifications of the authenticated user, "
        "ordered from most recent to oldest. "
        "Includes the unread_count to update the badge without another request."
    ),
)
async def list_notifications(
    only_unread: bool = Query(
        default=False,
        description="If True, returns only unread notifications",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total, unread_count = await notification_service.get_notifications(
        db=db,
        user_id=current_user.id,
        only_unread=only_unread,
        skip=skip,
        limit=limit,
    )
    return NotificationsListOut(
        items=[NotificationOut.model_validate(n) for n in items],
        total=total,
        unread_count=unread_count,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountOut,
    summary="Unread count",
    description=(
        "Lightweight endpoint for the navbar badge. "
        "The frontend calls it when it receives any event via WebSocket."
    ),
)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = await notification_service.get_unread_count(
        db=db, user_id=current_user.id
    )
    return UnreadCountOut(unread_count=count)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark notification as read",
    description="Marks a specific notification as read. Only the owner can do it.",
)
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = await notification_service.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    return NotificationOut.model_validate(notif)


@router.patch(
    "/read-all",
    summary="Mark all as read",
    description="Marks all unread notifications of the user as read.",
)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = await notification_service.mark_all_as_read(
        db=db, user_id=current_user.id
    )
    return {"updated": updated, "message": f"{updated} notifications marked as read."}


@router.websocket("/ws/{user_id}")
async def websocket_notifications(
    user_id: str,
    websocket: WebSocket,
    token: str = Query(..., description="JWT del usuario"),
):
    """
    Real-time notifications channel.

    Frontend connection:
        const ws = new WebSocket(
          `ws://localhost:8000/api/v1/notifications/ws/${userId}?token=${jwt}`
        )

    Received messages (JSON):
        {
          "id": "uuid",
          "ticket_id": "uuid",
          "type": "ticket_assigned" | "comment_added" | "status_changed",
          "message": "readable text",
          "created_at": "2024-01-15T10:30:00Z"
        }

    The server sends a ping every 30 s to keep the connection alive.
    """
    payload = decode_access_token(token)
    if not payload or payload.get("sub") != user_id:
        await websocket.close(code=4001, reason="Token inválido o no autorizado")
        return

    await ws_manager.connect(user_id, websocket)

    async def keep_alive():
        try:
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"type": "ping"})
        except Exception:
            pass

    ping_task = asyncio.create_task(keep_alive())

    try:
        await ws_manager.listen_and_forward(user_id, websocket)
    except WebSocketDisconnect:
        logger.info("WS disconnected: user=%s", user_id)
    except Exception as exc:
        logger.warning("WS error user=%s: %s", user_id, exc)
    finally:
        ping_task.cancel()
        ws_manager.disconnect(user_id)

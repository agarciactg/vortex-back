from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.models.notification import Notification, NotificationType
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.notification import WSNotificationPayload
from app.websockets import manager as ws_manager


async def _create_and_push(
    db: AsyncSession,
    *,
    user_id: str,
    ticket: Ticket,
    type_: NotificationType,
    message: str,
) -> None:
    notif = Notification(
        user_id=user_id,
        ticket_id=ticket.id,
        type=type_,
        message=message,
    )
    db.add(notif)
    await db.flush()
    await db.refresh(notif)

    payload = WSNotificationPayload(
        id=notif.id,
        ticket_id=ticket.id,
        type=type_,
        message=message,
        created_at=notif.created_at,
    ).model_dump(mode="json")

    await ws_manager.publish(user_id, payload)


async def notify_ticket_assigned(
    db: AsyncSession,
    ticket: Ticket,
    actor: User,
) -> None:
    if not ticket.assignee_id:
        return
    await _create_and_push(
        db,
        user_id=ticket.assignee_id,
        ticket=ticket,
        type_=NotificationType.TICKET_ASSIGNED,
        message=f"{actor.name} assigned you the ticket «{ticket.title}».",
    )


async def notify_status_changed(
    db: AsyncSession,
    ticket: Ticket,
    actor: User,
) -> None:
    STATUS_LABELS = {
        "open": "Open",
        "in_progress": "In progress",
        "in_review": "In review",
        "closed": "Closed",
    }
    label = STATUS_LABELS.get(ticket.status.value, ticket.status.value)
    message = f"{actor.name} changed the status of «{ticket.title}» to {label}."

    recipients = {ticket.author_id}
    if ticket.assignee_id:
        recipients.add(ticket.assignee_id)
    recipients.discard(actor.id)

    for user_id in recipients:
        await _create_and_push(
            db,
            user_id=user_id,
            ticket=ticket,
            type_=NotificationType.STATUS_CHANGED,
            message=message,
        )


async def notify_comment_added(
    db: AsyncSession,
    ticket: Ticket,
    actor: User,
) -> None:
    message = f"{actor.name} commented on «{ticket.title}»."
    recipients = {ticket.author_id}
    if ticket.assignee_id:
        recipients.add(ticket.assignee_id)
    recipients.discard(actor.id)

    for user_id in recipients:
        await _create_and_push(
            db,
            user_id=user_id,
            ticket=ticket,
            type_=NotificationType.COMMENT_ADDED,
            message=message,
        )


async def get_notifications(
    db: AsyncSession,
    user_id: str,
    only_unread: bool = False,
    skip: int = 0,
    limit: int = 30,
) -> tuple[list[Notification], int, int]:
    """Return (items, total, unread_count)."""
    base = select(Notification).where(Notification.user_id == user_id)
    count_base = select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id
    )
    if only_unread:
        base = base.where(Notification.is_read == False)
        count_base = count_base.where(Notification.is_read == False)

    base = base.order_by(Notification.created_at.desc())

    total_r = await db.execute(count_base)
    total = total_r.scalar_one()

    unread_r = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
    )
    unread_count = unread_r.scalar_one()

    result = await db.execute(base.offset(skip).limit(limit))
    items = list(result.scalars().all())
    return items, total, unread_count


async def get_unread_count(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
    )
    return result.scalar_one()


async def mark_as_read(
    db: AsyncSession,
    notification_id: str,
    user_id: str,
) -> Notification | None:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notif = result.scalar_one_or_none()
    if notif:
        notif.is_read = True
        await db.flush()
    return notif


async def mark_all_as_read(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True)
        .returning(Notification.id)
    )
    return len(result.all())

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.models.ticket import Ticket
from app.models.user import User

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/notifications"


@pytest.fixture
async def notification_for_a(
    db: AsyncSession, user_a: User, ticket_by_a: Ticket
) -> Notification:
    notif = Notification(
        user_id=user_a.id,
        ticket_id=ticket_by_a.id,
        type=NotificationType.TICKET_ASSIGNED,
        message="You were assigned a ticket",
        is_read=False,
    )
    db.add(notif)
    await db.flush()
    return notif


class TestListNotifications:
    async def test_returns_empty_when_none(self, client_a: AsyncClient):
        response = await client_a.get(BASE)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["unread_count"] == 0

    async def test_returns_user_notifications(
        self, client_a: AsyncClient, notification_for_a: Notification
    ):
        response = await client_a.get(BASE)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["unread_count"] == 1
        assert data["items"][0]["id"] == notification_for_a.id

    async def test_filter_only_unread(
        self, client_a: AsyncClient, notification_for_a: Notification
    ):
        response = await client_a.get(BASE, params={"only_unread": True})

        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_does_not_return_other_users_notifications(
        self, client_b: AsyncClient, notification_for_a: Notification
    ):
        response = await client_b.get(BASE)

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_requires_auth(self, client_unauth: AsyncClient):
        response = await client_unauth.get(BASE)
        assert response.status_code == 403


class TestUnreadCount:
    async def test_returns_zero_when_no_notifications(self, client_a: AsyncClient):
        response = await client_a.get(f"{BASE}/unread-count")

        assert response.status_code == 200
        assert response.json()["unread_count"] == 0

    async def test_returns_correct_count(
        self, client_a: AsyncClient, notification_for_a: Notification
    ):
        response = await client_a.get(f"{BASE}/unread-count")

        assert response.status_code == 200
        assert response.json()["unread_count"] == 1


class TestMarkAsRead:
    async def test_marks_notification_as_read(
        self, client_a: AsyncClient, notification_for_a: Notification
    ):
        response = await client_a.patch(
            f"{BASE}/{notification_for_a.id}/read"
        )

        assert response.status_code == 200
        assert response.json()["is_read"] is True

    async def test_unread_count_decreases_after_read(
        self,
        client_a: AsyncClient,
        notification_for_a: Notification,
    ):
        await client_a.patch(f"{BASE}/{notification_for_a.id}/read")
        response = await client_a.get(f"{BASE}/unread-count")

        assert response.json()["unread_count"] == 0

    async def test_cannot_mark_other_users_notification(
        self, client_b: AsyncClient, notification_for_a: Notification
    ):
        response = await client_b.patch(
            f"{BASE}/{notification_for_a.id}/read"
        )
        assert response.status_code == 404

    async def test_returns_404_for_unknown_id(self, client_a: AsyncClient):
        response = await client_a.patch(f"{BASE}/nonexistent-id/read")
        assert response.status_code == 404


class TestMarkAllRead:
    async def test_marks_all_as_read(
        self,
        client_a: AsyncClient,
        db: AsyncSession,
        user_a: User,
        ticket_by_a: Ticket,
    ):
        # Create 3 notifications
        for i in range(3):
            db.add(Notification(
                user_id=user_a.id,
                ticket_id=ticket_by_a.id,
                type=NotificationType.COMMENT_ADDED,
                message=f"Comment {i}",
                is_read=False,
            ))
        await db.flush()

        response = await client_a.patch(f"{BASE}/read-all")

        assert response.status_code == 200
        assert response.json()["updated"] == 3

        count_response = await client_a.get(f"{BASE}/unread-count")
        assert count_response.json()["unread_count"] == 0

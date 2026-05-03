import pytest

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket
from app.models.user import User

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/tickets"


class TestListTickets:
    async def test_returns_empty_list_initially(self, client_a: AsyncClient):
        response = await client_a.get(BASE)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_returns_created_ticket(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.get(BASE)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == ticket_by_a.id

    async def test_filter_by_status(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.get(BASE, params={"status": "closed"})

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_filter_by_priority(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.get(BASE, params={"priority": "high"})

        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_search_by_title(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.get(BASE, params={"search": "login"})

        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_search_no_match(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.get(BASE, params={"search": "zzznotfound"})

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_pagination_skip(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.get(BASE, params={"skip": 1, "limit": 10})

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_requires_auth(self, client_unauth: AsyncClient):
        response = await client_unauth.get(BASE)
        assert response.status_code == 403


class TestCreateTicket:
    async def test_creates_ticket_successfully(
        self, client_a: AsyncClient, user_a: User
    ):
        payload = {
            "title": "Implement dark mode",
            "description": "Add dark mode support to the dashboard",
            "priority": "medium",
        }
        response = await client_a.post(BASE, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Implement dark mode"
        assert data["status"] == "open"
        assert data["priority"] == "medium"
        assert data["author"]["id"] == user_a.id
        assert data["assignee"] is None

    async def test_creates_ticket_with_assignee(
        self, client_a: AsyncClient, user_a: User, user_b: User
    ):
        payload = {
            "title": "Fix the API rate limit",
            "priority": "high",
            "assignee_id": user_b.id,
        }
        response = await client_a.post(BASE, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["assignee"]["id"] == user_b.id

    async def test_title_too_short_returns_422(self, client_a: AsyncClient):
        response = await client_a.post(BASE, json={"title": "ab"})

        assert response.status_code == 422

    async def test_missing_title_returns_422(self, client_a: AsyncClient):
        response = await client_a.post(BASE, json={"priority": "low"})

        assert response.status_code == 422

    async def test_invalid_assignee_returns_422(self, client_a: AsyncClient):
        response = await client_a.post(
            BASE, json={"title": "Valid title", "assignee_id": "nonexistent-uuid"}
        )
        assert response.status_code == 422

    async def test_requires_auth(self, client_unauth: AsyncClient):
        response = await client_unauth.post(BASE, json={"title": "Some title"})
        assert response.status_code == 403


class TestGetTicket:
    async def test_returns_ticket_detail(
        self, client_a: AsyncClient, ticket_by_a: Ticket, user_a: User
    ):
        response = await client_a.get(f"{BASE}/{ticket_by_a.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == ticket_by_a.id
        assert data["title"] == ticket_by_a.title
        assert data["author"]["id"] == user_a.id

    async def test_returns_404_for_unknown_id(self, client_a: AsyncClient):
        response = await client_a.get(f"{BASE}/nonexistent-id")

        assert response.status_code == 404

    async def test_requires_auth(
        self, client_unauth: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_unauth.get(f"{BASE}/{ticket_by_a.id}")
        assert response.status_code == 403


class TestUpdateTicket:
    async def test_updates_title(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.patch(
            f"{BASE}/{ticket_by_a.id}",
            json={"title": "Updated title for the ticket"},
        )

        assert response.status_code == 200
        assert response.json()["title"] == "Updated title for the ticket"

    async def test_updates_priority(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.patch(
            f"{BASE}/{ticket_by_a.id}", json={"priority": "critical"}
        )

        assert response.status_code == 200
        assert response.json()["priority"] == "critical"

    async def test_partial_update_preserves_other_fields(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        original_title = ticket_by_a.title
        response = await client_a.patch(
            f"{BASE}/{ticket_by_a.id}", json={"priority": "low"}
        )

        assert response.status_code == 200
        assert response.json()["title"] == original_title

    async def test_returns_404_for_unknown_ticket(self, client_a: AsyncClient):
        response = await client_a.patch(
            f"{BASE}/nonexistent-id", json={"priority": "low"}
        )
        assert response.status_code == 404


class TestChangeStatus:
    async def test_changes_status_to_in_progress(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.patch(
            f"{BASE}/{ticket_by_a.id}/status",
            json={"status": "in_progress"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"

    async def test_changes_status_to_closed(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.patch(
            f"{BASE}/{ticket_by_a.id}/status", json={"status": "closed"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "closed"

    async def test_same_status_returns_ticket_unchanged(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.patch(
            f"{BASE}/{ticket_by_a.id}/status", json={"status": "open"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "open"

    async def test_invalid_status_returns_422(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.patch(
            f"{BASE}/{ticket_by_a.id}/status", json={"status": "flying"}
        )
        assert response.status_code == 422


class TestAssignTicket:
    async def test_assigns_ticket_to_user_b(
        self,
        client_a: AsyncClient,
        ticket_by_a: Ticket,
        user_b: User,
    ):
        response = await client_a.patch(
            f"{BASE}/{ticket_by_a.id}/assign",
            json={"assignee_id": user_b.id},
        )

        assert response.status_code == 200
        assert response.json()["assignee"]["id"] == user_b.id

    async def test_assign_nonexistent_user_returns_422(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.patch(
            f"{BASE}/{ticket_by_a.id}/assign",
            json={"assignee_id": "nonexistent-user-id"},
        )
        assert response.status_code == 422

    async def test_assign_nonexistent_ticket_returns_404(
        self, client_a: AsyncClient, user_b: User
    ):
        response = await client_a.patch(
            f"{BASE}/nonexistent-ticket/assign",
            json={"assignee_id": user_b.id},
        )
        assert response.status_code == 404


class TestDeleteTicket:
    async def test_author_can_delete_own_ticket(
        self, client_a: AsyncClient, ticket_by_a: Ticket
    ):
        response = await client_a.delete(f"{BASE}/{ticket_by_a.id}")

        assert response.status_code == 204

    async def test_non_author_cannot_delete_ticket(
        self,
        client_b: AsyncClient,
        ticket_by_a: Ticket,
    ):
        response = await client_b.delete(f"{BASE}/{ticket_by_a.id}")

        assert response.status_code == 403

    async def test_delete_nonexistent_ticket_returns_404(
        self, client_a: AsyncClient
    ):
        response = await client_a.delete(f"{BASE}/nonexistent-id")
        assert response.status_code == 404

    async def test_ticket_not_found_after_delete(
        self,
        client_a: AsyncClient,
        db: AsyncSession,
        ticket_by_a: Ticket,
    ):
        await client_a.delete(f"{BASE}/{ticket_by_a.id}")
        response = await client_a.get(f"{BASE}/{ticket_by_a.id}")
        assert response.status_code == 404

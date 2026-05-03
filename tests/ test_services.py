import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.user import User
from app.schemas.ticket import TicketCreate, TicketUpdate
from app.services import ticket_service, user_service

pytestmark = pytest.mark.asyncio


class TestTicketService:
    async def test_create_ticket(self, db: AsyncSession, user_a: User):
        data = TicketCreate(
            title="Service layer test ticket",
            description="Created directly via service",
            priority=TicketPriority.HIGH,
        )
        ticket = await ticket_service.create_ticket(db, data, author_id=user_a.id)

        assert ticket.id is not None
        assert ticket.title == "Service layer test ticket"
        assert ticket.author_id == user_a.id
        assert ticket.status == TicketStatus.OPEN
        assert ticket.priority == TicketPriority.HIGH

    async def test_get_ticket_by_id(self, db: AsyncSession, ticket_by_a: Ticket):
        found = await ticket_service.get_ticket_by_id(db, ticket_by_a.id)

        assert found is not None
        assert found.id == ticket_by_a.id

    async def test_get_ticket_by_id_not_found(self, db: AsyncSession):
        found = await ticket_service.get_ticket_by_id(db, "nonexistent")
        assert found is None

    async def test_list_tickets_filter_by_status(
        self, db: AsyncSession, user_a: User, ticket_by_a: Ticket
    ):
        tickets, total = await ticket_service.list_tickets(
            db, status=TicketStatus.OPEN
        )
        assert total >= 1
        assert all(t.status == TicketStatus.OPEN for t in tickets)

    async def test_list_tickets_filter_by_priority(
        self, db: AsyncSession, user_a: User, ticket_by_a: Ticket
    ):
        tickets, total = await ticket_service.list_tickets(
            db, priority=TicketPriority.HIGH
        )
        assert total >= 1
        assert all(t.priority == TicketPriority.HIGH for t in tickets)

    async def test_list_tickets_search(
        self, db: AsyncSession, ticket_by_a: Ticket
    ):
        tickets, total = await ticket_service.list_tickets(db, search="login bug")
        assert total >= 1

    async def test_update_ticket_title(
        self, db: AsyncSession, ticket_by_a: Ticket
    ):
        data = TicketUpdate(title="Updated title from service test")
        updated = await ticket_service.update_ticket(db, ticket_by_a, data)

        assert updated.title == "Updated title from service test"
        assert updated.description == ticket_by_a.description

    async def test_change_status(self, db: AsyncSession, ticket_by_a: Ticket):
        updated = await ticket_service.change_status(
            db, ticket_by_a, TicketStatus.IN_PROGRESS
        )
        assert updated.status == TicketStatus.IN_PROGRESS

    async def test_reassign_ticket(
        self, db: AsyncSession, ticket_by_a: Ticket, user_b: User
    ):
        updated = await ticket_service.reassign_ticket(db, ticket_by_a, user_b.id)
        assert updated.assignee_id == user_b.id

    async def test_delete_ticket(self, db: AsyncSession, user_a: User):
        data = TicketCreate(title="Ticket to delete", priority=TicketPriority.LOW)
        ticket = await ticket_service.create_ticket(db, data, author_id=user_a.id)
        ticket_id = ticket.id

        await ticket_service.delete_ticket(db, ticket)

        found = await ticket_service.get_ticket_by_id(db, ticket_id)
        assert found is None


class TestUserService:
    async def test_get_all_users(
        self, db: AsyncSession, user_a: User, user_b: User
    ):
        users, total = await user_service.get_all_users(db)

        assert total >= 2
        ids = [u.id for u in users]
        assert user_a.id in ids
        assert user_b.id in ids

    async def test_search_users_by_name(
        self, db: AsyncSession, user_a: User, user_b: User
    ):
        users, total = await user_service.get_all_users(db, search="Ana")

        assert total == 1
        assert users[0].id == user_a.id

    async def test_search_users_case_insensitive(
        self, db: AsyncSession, user_a: User
    ):
        users, total = await user_service.get_all_users(db, search="ANA")
        assert total >= 1

    async def test_get_user_by_id(self, db: AsyncSession, user_a: User):
        found = await user_service.get_user_by_id(db, user_a.id)

        assert found is not None
        assert found.id == user_a.id

    async def test_get_user_by_id_not_found(self, db: AsyncSession):
        found = await user_service.get_user_by_id(db, "nonexistent")
        assert found is None

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.schemas.ticket import TicketCreate, TicketUpdate

SORTABLE = {"created_at", "updated_at", "priority", "status", "title"}


def _base_query():
    """Base query with eager-loaded relationships (avoids N+1)."""
    return select(Ticket).options(
        selectinload(Ticket.author),
        selectinload(Ticket.assignee),
    )


async def get_tickets(
    db: AsyncSession,
    status: TicketStatus | None = None,
    priority: TicketPriority | None = None,
    assignee_id: str | None = None,
    author_id: str | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Ticket], int]:
    query = _base_query()
    count_query = select(func.count()).select_from(Ticket)

    filters = []
    if status:
        filters.append(Ticket.status == status)
    if priority:
        filters.append(Ticket.priority == priority)
    if assignee_id:
        filters.append(Ticket.assignee_id == assignee_id)
    if author_id:
        filters.append(Ticket.author_id == author_id)
    if search:
        pattern = f"%{search.lower()}%"
        from sqlalchemy import func as sqla_func
        filters.append(sqla_func.lower(Ticket.title).like(pattern))

    if filters:
        from sqlalchemy import and_
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    sort_col = sort_by if sort_by in SORTABLE else "created_at"
    col = getattr(Ticket, sort_col)
    query = query.order_by(col.desc() if sort_dir == "desc" else col.asc())

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.offset(skip).limit(limit))
    tickets = list(result.scalars().all())

    return tickets, total


async def get_ticket_by_id(db: AsyncSession, ticket_id: str) -> Ticket | None:
    result = await db.execute(_base_query().where(Ticket.id == ticket_id))
    return result.scalar_one_or_none()


async def create_ticket(db: AsyncSession, data: TicketCreate, author_id: str) -> Ticket:
    ticket = Ticket(
        title=data.title,
        description=data.description,
        priority=data.priority,
        assignee_id=data.assignee_id,
        author_id=author_id,
    )
    db.add(ticket)
    await db.flush()
    await db.refresh(ticket, ["author", "assignee"])
    return ticket


async def update_ticket(db: AsyncSession, ticket: Ticket, data: TicketUpdate) -> Ticket:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ticket, field, value)
    await db.flush()
    await db.refresh(ticket, ["author", "assignee"])
    return ticket


async def assign_ticket(db: AsyncSession, ticket: Ticket, assignee_id: str | None) -> Ticket:
    ticket.assignee_id = assignee_id
    await db.flush()
    await db.refresh(ticket, ["author", "assignee"])
    return ticket


async def change_ticket_status(db: AsyncSession, ticket: Ticket, status: TicketStatus) -> Ticket:
    ticket.status = status
    await db.flush()
    await db.refresh(ticket, ["author", "assignee"])
    return ticket


async def delete_ticket(db: AsyncSession, ticket: Ticket) -> None:
    await db.delete(ticket)
    await db.flush()

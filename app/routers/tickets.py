from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.ticket import TicketStatus, TicketPriority
from app.models.user import User
from app.schemas.ticket import (
    TicketCreate,
    TicketUpdate,
    TicketAssign,
    TicketStatusChange,
    TicketOut,
    TicketListOut,
)
from app.services import ticket_service

router = APIRouter()


@router.get(
    "",
    response_model=TicketListOut,
    summary="List tickets",
    description=(
        "Returns a paginated list of tickets. "
        "Supports filtering by status, priority, assignee, author and text search. "
        "Supports sorting by any field."
    ),
)
async def list_tickets(
    status: TicketStatus | None = Query(default=None, description="Filter by status"),
    priority: TicketPriority | None = Query(default=None, description="Filter by priority"),
    assignee_id: str | None = Query(default=None, description="Filter by assignee user ID"),
    author_id: str | None = Query(default=None, description="Filter by author user ID"),
    search: str | None = Query(default=None, min_length=1, max_length=200, description="Search in title"),
    sort_by: str = Query(default="created_at", description="Field to sort by"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort direction"),
    skip: int = Query(default=0, ge=0, description="Elements to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max elements to return"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    tickets, total = await ticket_service.get_tickets(
        db=db,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        author_id=author_id,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        skip=skip,
        limit=limit,
    )
    return TicketListOut(
        items=[TicketOut.model_validate(t) for t in tickets],
        total=total,
    )


@router.post(
    "",
    response_model=TicketOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create ticket",
    description="Creates a new ticket. The authenticated user becomes the author.",
)
async def create_ticket(
    data: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await ticket_service.create_ticket(db=db, data=data, author_id=current_user.id)
    await db.commit()
    return TicketOut.model_validate(ticket)


@router.get(
    "/{ticket_id}",
    response_model=TicketOut,
    summary="Ticket detail",
    description="Returns the full detail of a single ticket.",
)
async def get_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    return TicketOut.model_validate(ticket)


@router.patch(
    "/{ticket_id}",
    response_model=TicketOut,
    summary="Update ticket",
    description=(
        "Partially updates a ticket (title, description, priority, assignee). "
        "Only the author can edit."
    ),
)
async def update_ticket(
    ticket_id: str,
    data: TicketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    if ticket.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can edit this ticket.")

    ticket = await ticket_service.update_ticket(db=db, ticket=ticket, data=data)
    await db.commit()
    return TicketOut.model_validate(ticket)


@router.patch(
    "/{ticket_id}/assign",
    response_model=TicketOut,
    summary="Reassign ticket",
    description=(
        "Assigns or unassigns a ticket to a user. "
        "Send `assignee_id: null` to unassign. "
        "Only the author can reassign."
    ),
)
async def assign_ticket(
    ticket_id: str,
    data: TicketAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    if ticket.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can reassign this ticket.")

    ticket = await ticket_service.assign_ticket(db=db, ticket=ticket, assignee_id=data.assignee_id)
    await db.commit()
    return TicketOut.model_validate(ticket)


@router.patch(
    "/{ticket_id}/status",
    response_model=TicketOut,
    summary="Change status (Kanban drag & drop)",
    description=(
        "Updates only the status of a ticket. "
        "Both the author and the assignee can change the status."
    ),
)
async def change_status(
    ticket_id: str,
    data: TicketStatusChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    is_author = ticket.author_id == current_user.id
    is_assignee = ticket.assignee_id == current_user.id
    if not (is_author or is_assignee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the author or assignee can change the status.",
        )

    ticket = await ticket_service.change_ticket_status(db=db, ticket=ticket, status=data.status)
    await db.commit()
    return TicketOut.model_validate(ticket)


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete ticket",
    description="Permanently deletes a ticket. Only the author can delete it.",
)
async def delete_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    if ticket.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can delete this ticket.")

    await ticket_service.delete_ticket(db=db, ticket=ticket)
    await db.commit()

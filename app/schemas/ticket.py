from pydantic import BaseModel, Field
from datetime import datetime

from app.models.ticket import TicketStatus, TicketPriority
from app.schemas.user import UserSummary


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    priority: TicketPriority = TicketPriority.MEDIUM
    assignee_id: str | None = None


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    priority: TicketPriority | None = None
    assignee_id: str | None = None


class TicketAssign(BaseModel):
    assignee_id: str | None = Field(
        ...,
        description="User ID to assign the ticket to. Send null to unassign.",
    )


class TicketStatusChange(BaseModel):
    status: TicketStatus


class TicketOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    status: TicketStatus
    priority: TicketPriority
    author: UserSummary
    assignee: UserSummary | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketListOut(BaseModel):
    items: list[TicketOut]
    total: int

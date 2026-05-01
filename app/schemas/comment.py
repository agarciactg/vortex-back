from pydantic import BaseModel, Field
from datetime import datetime

from app.schemas.user import UserSummary


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class CommentOut(BaseModel):
    id: str
    content: str
    author: UserSummary
    ticket_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentListOut(BaseModel):
    items: list[CommentOut]
    total: int

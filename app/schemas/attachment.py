from pydantic import BaseModel
from datetime import datetime

from app.schemas.user import UserSummary


class AttachmentOut(BaseModel):
    id: str
    original_filename: str
    file_size: int
    content_type: str
    ticket_id: str
    uploader: UserSummary
    created_at: datetime

    model_config = {"from_attributes": True}


class AttachmentListOut(BaseModel):
    items: list[AttachmentOut]
    total: int

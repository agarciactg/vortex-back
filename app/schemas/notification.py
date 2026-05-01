from pydantic import BaseModel
from datetime import datetime
from app.models.notification import NotificationType


class NotificationOut(BaseModel):
    id: str
    ticket_id: str
    type: NotificationType
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationsListOut(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int


class UnreadCountOut(BaseModel):
    unread_count: int


class WSNotificationPayload(BaseModel):
    id: str
    ticket_id: str
    type: NotificationType
    message: str
    created_at: datetime

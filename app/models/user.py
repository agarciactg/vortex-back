import uuid

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    google_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    authored_tickets: Mapped[list["Ticket"]] = relationship("Ticket", foreign_keys="Ticket.author_id", back_populates="author")
    assigned_tickets: Mapped[list["Ticket"]] = relationship("Ticket", foreign_keys="Ticket.assignee_id", back_populates="assignee")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="author")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user")

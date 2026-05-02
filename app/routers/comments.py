from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentOut, CommentListOut
from app.services import comment_service, ticket_service, notification_service

router = APIRouter()


@router.get(
    "/{ticket_id}/comments",
    response_model=CommentListOut,
    summary="List comments",
    description="Returns comments of a ticket in chronological order (oldest first).",
)
async def list_comments(
    ticket_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    comments, total = await comment_service.get_comments_by_ticket(
        db=db, ticket_id=ticket_id, skip=skip, limit=limit
    )
    return CommentListOut(
        items=[CommentOut.model_validate(c) for c in comments],
        total=total,
    )


@router.post(
    "/{ticket_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add comment",
    description=(
        "Adds a comment to a ticket. "
        "Any authenticated user can comment. "
        "Triggers a notification to the author and assignee."
    ),
)
async def create_comment(
    ticket_id: str,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    comment = await comment_service.create_comment(
        db=db,
        data=data,
        ticket_id=ticket_id,
        author_id=current_user.id,
    )

    await notification_service.notify_comment_added(db=db, ticket=ticket, actor=current_user)

    await db.commit()
    return CommentOut.model_validate(comment)


@router.delete(
    "/{ticket_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete comment",
    description="Permanently deletes a comment. Only the comment's author can delete it.",
)
async def delete_comment(
    ticket_id: str,
    comment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await ticket_service.get_ticket_by_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    comment = await comment_service.get_comment_by_id(db=db, comment_id=comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
    if comment.ticket_id != ticket_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found in this ticket.")
    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the comment's author can delete it.",
        )

    await comment_service.delete_comment(db=db, comment=comment)
    await db.commit()

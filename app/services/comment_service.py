from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.schemas.comment import CommentCreate


def _base_query():
    """Base query with eager-loaded author (avoids N+1)."""
    return select(Comment).options(selectinload(Comment.author))


async def get_comments_by_ticket(
    db: AsyncSession,
    ticket_id: str,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Comment], int]:
    query = _base_query().where(Comment.ticket_id == ticket_id).order_by(Comment.created_at.asc())
    count_query = select(func.count()).select_from(Comment).where(Comment.ticket_id == ticket_id)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.offset(skip).limit(limit))
    comments = list(result.scalars().all())

    return comments, total


async def get_comment_by_id(db: AsyncSession, comment_id: str) -> Comment | None:
    result = await db.execute(_base_query().where(Comment.id == comment_id))
    return result.scalar_one_or_none()


async def create_comment(
    db: AsyncSession,
    data: CommentCreate,
    ticket_id: str,
    author_id: str,
) -> Comment:
    comment = Comment(
        content=data.content,
        ticket_id=ticket_id,
        author_id=author_id,
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    return await get_comment_by_id(db, comment.id)


async def delete_comment(db: AsyncSession, comment: Comment) -> None:
    await db.delete(comment)
    await db.flush()

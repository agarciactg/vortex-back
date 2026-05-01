from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.user import User


async def get_all_users(
    db: AsyncSession,
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[User], int]:
    """
    Returns (list_of_users, total).
    Supports search by name or email (case-insensitive).
    Mainly used for the ticket assignment selector.
    """
    query = select(User).order_by(User.name)
    count_query = select(func.count()).select_from(User)

    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(User.name).like(pattern)
            | func.lower(User.email).like(pattern)
        )
        count_query = count_query.where(
            func.lower(User.name).like(pattern)
            | func.lower(User.email).like(pattern)
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(query.offset(skip).limit(limit))
    users = list(result.scalars().all())

    return users, total


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

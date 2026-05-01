from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserOut, UsersListOut
from app.services import user_service

router = APIRouter()


@router.get(
    "",
    response_model=UsersListOut,
    summary="List users",
    description=(
        "Returns all users registered in the system. "
        "Mainly used for the ticket assignment selector. "
        "Supports search by name or email."
    ),
)
async def list_users(
    search: str | None = Query(
        default=None,
        description="Filter by name or email (case-insensitive)",
        min_length=1,
        max_length=100,
    ),
    skip: int = Query(default=0, ge=0, description="Elements to skip"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of elements to return"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    users, total = await user_service.get_all_users(
        db=db,
        search=search,
        skip=skip,
        limit=limit,
    )
    return UsersListOut(
        items=[UserOut.model_validate(u) for u in users],
        total=total,
    )


@router.get(
    "/me",
    response_model=UserOut,
    summary="My profile (alias)",
    description="Convenient alias of GET /auth/me. Returns the authenticated user.",
)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="User detail",
    description="Returns the public profile of a user by their ID.",
)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    user = await user_service.get_user_by_id(db=db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found.",
        )
    return UserOut.model_validate(user)

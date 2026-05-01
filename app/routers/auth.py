from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import TokenOut, UserOut
from app.services import auth_service

router = APIRouter()
bearer_scheme = HTTPBearer()


@router.get(
    "/google/login",
    summary="Start login with Google",
    description="Redirects to the Google OAuth 2.0 consent screen.",
    status_code=status.HTTP_302_FOUND,
)
async def google_login(
    state: str | None = Query(default=None, description="Opaque value to prevent CSRF"),
):
    url = auth_service.build_google_auth_url(state=state)
    return RedirectResponse(url=url)


@router.get(
    "/google/callback",
    response_model=TokenOut,
    summary="Google OAuth Callback",
    description=(
        "Google redirects here with a `code`. "
        "The backend exchanges it for a Google token, "
        "obtains the user profile, creates or updates it in the database "
        "and returns its own JWT."
    ),
)
async def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None, description="Error returned by Google"),
    db: AsyncSession = Depends(get_db),
):
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google rejected access: {error}",
        )

    try:
        token_data = await auth_service.exchange_code_for_token(code)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not exchange code with Google. Please try again.",
        )

    try:
        google_info = await auth_service.get_google_userinfo(token_data["access_token"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not obtain Google profile.",
        )

    user = await auth_service.upsert_user(db, google_info)
    access_token = create_access_token(subject=user.id)

    return TokenOut(
        access_token=access_token,
        user=UserOut.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserOut,
    summary="Profile of authenticated user",
    description="Requires Bearer token. Returns the user data in session.",
)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description=(
        "Adds the current token to the Redis blacklist. "
        "It expires automatically along with the token's TTL."
    ),
)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    _: User = Depends(get_current_user),
):
    token = credentials.credentials
    await auth_service.blacklist_token(token)

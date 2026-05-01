from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    avatar_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    """Compact version to embed within tickets and comments."""
    id: str
    name: str
    email: EmailStr
    avatar_url: str | None = None
 
    model_config = {"from_attributes": True}
 
 
class UsersListOut(BaseModel):
    items: list[UserOut]
    total: int


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    avatar_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

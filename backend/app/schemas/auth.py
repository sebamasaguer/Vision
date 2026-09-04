import uuid
from pydantic import BaseModel, EmailStr
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
class CurrentUserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    organization_id: uuid.UUID | None
    role_codes: list[str]
    permission_codes: list[str]

import uuid
from pydantic import BaseModel, EmailStr, Field
from app.schemas.common import ORMModel

class UserCreate(BaseModel):
    organization_id: uuid.UUID | None = None
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=10, max_length=128)
    role_codes: list[str] = Field(min_length=1)
class UserOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    email: EmailStr
    full_name: str
    is_active: bool
    role_codes: list[str] = []
class RoleOut(BaseModel):
    code: str
    name: str
    scope: str

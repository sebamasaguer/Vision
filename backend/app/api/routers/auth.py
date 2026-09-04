from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.api.deps import get_current_user, permission_codes, role_codes
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.access import User, Role
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Autenticación"])

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()).options(selectinload(User.roles).selectinload(Role.permissions)))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    return TokenResponse(access_token=create_access_token(str(user.id)))

@router.get("/me", response_model=CurrentUserResponse)
def me(user: User = Depends(get_current_user)):
    return CurrentUserResponse(id=user.id, email=user.email, full_name=user.full_name, organization_id=user.organization_id, role_codes=sorted(role_codes(user)), permission_codes=sorted(permission_codes(user)))

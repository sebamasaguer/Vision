import uuid
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.access import User, Role

bearer = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    user = db.scalar(select(User).where(User.id == user_id).options(selectinload(User.roles).selectinload(Role.permissions)))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo o inexistente")
    return user

def role_codes(user: User) -> set[str]:
    return {r.code for r in user.roles}

def permission_codes(user: User) -> set[str]:
    return {p.code for r in user.roles for p in r.permissions}

def is_superadmin(user: User) -> bool:
    return "SUPERADMIN" in role_codes(user)

def require_permission(code: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if is_superadmin(user) or code in permission_codes(user):
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permiso requerido: {code}")
    return checker

def ensure_org_access(user: User, organization_id: uuid.UUID):
    if not is_superadmin(user) and user.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Fuera del alcance de su organización")

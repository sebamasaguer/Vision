from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.api.deps import ensure_org_access, is_superadmin, require_permission
from app.core.security import hash_password
from app.db.session import get_db
from app.models.access import Role, User
from app.models.organization import Organization
from app.schemas.user import RoleOut, UserCreate, UserOut
from app.services.audit import add_audit

router = APIRouter(tags=["Usuarios"])

def serialize_user(user: User) -> UserOut:
    return UserOut(id=user.id, organization_id=user.organization_id, email=user.email, full_name=user.full_name, is_active=user.is_active, role_codes=sorted(r.code for r in user.roles))

@router.get("/roles", response_model=list[RoleOut])
def list_roles(user: User = Depends(require_permission("user.read")), db: Session = Depends(get_db)):
    roles = list(db.scalars(select(Role).order_by(Role.code)))
    if not is_superadmin(user): roles = [r for r in roles if r.code != "SUPERADMIN"]
    return [RoleOut(code=r.code, name=r.name, scope=r.scope) for r in roles]

@router.get("/users", response_model=list[UserOut])
def list_users(user: User = Depends(require_permission("user.read")), db: Session = Depends(get_db)):
    stmt = select(User).options(selectinload(User.roles)).order_by(User.full_name)
    if not is_superadmin(user): stmt = stmt.where(User.organization_id == user.organization_id)
    return [serialize_user(x) for x in db.scalars(stmt)]

@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, request: Request, actor: User = Depends(require_permission("user.manage")), db: Session = Depends(get_db)):
    organization_id = payload.organization_id if is_superadmin(actor) else actor.organization_id
    if organization_id is None: raise HTTPException(422, "Debe indicar organización para el usuario")
    ensure_org_access(actor, organization_id)
    if not db.get(Organization, organization_id): raise HTTPException(404, "Organización inexistente")
    if db.scalar(select(User).where(User.email == payload.email.lower())): raise HTTPException(409, "Email ya registrado")
    roles = list(db.scalars(select(Role).where(Role.code.in_(payload.role_codes))))
    if len(roles) != len(set(payload.role_codes)): raise HTTPException(422, "Uno o más roles no existen")
    if not is_superadmin(actor) and any(r.code == "SUPERADMIN" for r in roles): raise HTTPException(403, "No puede asignar SUPERADMIN")
    item = User(organization_id=organization_id, email=payload.email.lower(), full_name=payload.full_name.strip(), password_hash=hash_password(payload.password), roles=roles)
    db.add(item); db.flush(); add_audit(db, actor, "CREATE", "user", str(item.id), after={"email": item.email, "roles": payload.role_codes}, request=request, organization_id=organization_id); db.commit()
    return serialize_user(item)

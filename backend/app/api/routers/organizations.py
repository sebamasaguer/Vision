from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import ensure_org_access, get_current_user, is_superadmin, require_permission
from app.db.session import get_db
from app.models.access import User
from app.models.organization import Organization, Site, Plant, Sector
from app.schemas.organization import OrganizationCreate, OrganizationOut, SiteCreate, SiteOut, PlantCreate, PlantOut, SectorCreate, SectorOut
from app.services.audit import add_audit

router = APIRouter(tags=["Estructura"])

def commit_or_conflict(db: Session, message: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail=message)

@router.get("/organizations", response_model=list[OrganizationOut])
def list_organizations(user: User = Depends(require_permission("organization.read")), db: Session = Depends(get_db)):
    stmt = select(Organization).where(Organization.active.is_(True)).order_by(Organization.name)
    if not is_superadmin(user):
        stmt = stmt.where(Organization.id == user.organization_id)
    return list(db.scalars(stmt))

@router.post("/organizations", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_organization(payload: OrganizationCreate, request: Request, user: User = Depends(require_permission("organization.create")), db: Session = Depends(get_db)):
    item = Organization(code=payload.code.strip().upper(), name=payload.name.strip())
    db.add(item)
    try: db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Código de organización ya existente")
    add_audit(db, user, "CREATE", "organization", str(item.id), after={"code": item.code, "name": item.name}, request=request, organization_id=item.id)
    db.commit()
    return item

@router.get("/sites", response_model=list[SiteOut])
def list_sites(organization_id: str | None = None, user: User = Depends(require_permission("structure.read")), db: Session = Depends(get_db)):
    stmt = select(Site).where(Site.active.is_(True)).order_by(Site.name)
    if is_superadmin(user):
        if organization_id: stmt = stmt.where(Site.organization_id == organization_id)
    else:
        stmt = stmt.where(Site.organization_id == user.organization_id)
    return list(db.scalars(stmt))

@router.post("/sites", response_model=SiteOut, status_code=201)
def create_site(payload: SiteCreate, request: Request, user: User = Depends(require_permission("structure.manage")), db: Session = Depends(get_db)):
    ensure_org_access(user, payload.organization_id)
    if not db.get(Organization, payload.organization_id): raise HTTPException(404, "Organización inexistente")
    item = Site(organization_id=payload.organization_id, code=payload.code.strip().upper(), name=payload.name.strip(), address=payload.address)
    db.add(item)
    try: db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Código de establecimiento duplicado")
    add_audit(db, user, "CREATE", "site", str(item.id), after={"code": item.code, "name": item.name}, request=request, organization_id=item.organization_id)
    db.commit()
    return item

@router.get("/plants", response_model=list[PlantOut])
def list_plants(site_id: str | None = None, user: User = Depends(require_permission("structure.read")), db: Session = Depends(get_db)):
    stmt = select(Plant).where(Plant.active.is_(True)).order_by(Plant.name)
    if not is_superadmin(user): stmt = stmt.where(Plant.organization_id == user.organization_id)
    if site_id: stmt = stmt.where(Plant.site_id == site_id)
    return list(db.scalars(stmt))

@router.post("/plants", response_model=PlantOut, status_code=201)
def create_plant(payload: PlantCreate, request: Request, user: User = Depends(require_permission("structure.manage")), db: Session = Depends(get_db)):
    site = db.get(Site, payload.site_id)
    if not site: raise HTTPException(404, "Establecimiento inexistente")
    ensure_org_access(user, site.organization_id)
    item = Plant(organization_id=site.organization_id, site_id=site.id, code=payload.code.strip().upper(), name=payload.name.strip())
    db.add(item)
    try: db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Código de planta duplicado en el establecimiento")
    add_audit(db, user, "CREATE", "plant", str(item.id), after={"code": item.code, "name": item.name}, request=request, organization_id=item.organization_id)
    db.commit()
    return item

@router.get("/sectors", response_model=list[SectorOut])
def list_sectors(plant_id: str | None = None, user: User = Depends(require_permission("structure.read")), db: Session = Depends(get_db)):
    stmt = select(Sector).where(Sector.active.is_(True)).order_by(Sector.name)
    if not is_superadmin(user): stmt = stmt.where(Sector.organization_id == user.organization_id)
    if plant_id: stmt = stmt.where(Sector.plant_id == plant_id)
    return list(db.scalars(stmt))

@router.post("/sectors", response_model=SectorOut, status_code=201)
def create_sector(payload: SectorCreate, request: Request, user: User = Depends(require_permission("structure.manage")), db: Session = Depends(get_db)):
    plant = db.get(Plant, payload.plant_id)
    if not plant: raise HTTPException(404, "Planta inexistente")
    ensure_org_access(user, plant.organization_id)
    item = Sector(organization_id=plant.organization_id, site_id=plant.site_id, plant_id=plant.id, code=payload.code.strip().upper(), name=payload.name.strip(), description=payload.description)
    db.add(item)
    try: db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Código de sector duplicado en la planta")
    add_audit(db, user, "CREATE", "sector", str(item.id), after={"code": item.code, "name": item.name}, request=request, organization_id=item.organization_id)
    db.commit()
    return item

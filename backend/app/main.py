from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.config import settings
from app.db.session import SessionLocal
from app.api.routers import auth, organizations, users, audit, system, cameras, ppe, zones, vision, events, monitoring, analytics, ml

app = FastAPI(title=settings.app_name, version=settings.app_version, description="Plataforma de Higiene y Seguridad con IA — API v1")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router, prefix="/api/v1")
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(cameras.router, prefix="/api/v1")
app.include_router(ppe.router, prefix="/api/v1")
app.include_router(zones.router, prefix="/api/v1")
app.include_router(vision.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(monitoring.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(ml.router, prefix="/api/v1")

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "backend", "version": settings.app_version}

@app.get("/ready", tags=["Health"])
def ready():
    deps = {"postgres": "unknown", "redis": "unknown", "minio": "unknown"}
    try:
        with SessionLocal() as db: db.execute(text("SELECT 1"))
        deps["postgres"] = "ok"
    except Exception: deps["postgres"] = "error"
    try:
        from redis import Redis
        Redis.from_url(settings.redis_url, socket_timeout=1).ping(); deps["redis"] = "ok"
    except Exception: deps["redis"] = "degraded"
    try:
        from minio import Minio
        client = Minio(settings.minio_endpoint, access_key=settings.minio_access_key, secret_key=settings.minio_secret_key, secure=settings.minio_secure)
        client.bucket_exists(settings.minio_bucket_evidence); deps["minio"] = "ok"
    except Exception: deps["minio"] = "degraded"
    if deps["postgres"] != "ok": raise HTTPException(status_code=503, detail={"status": "not_ready", "dependencies": deps})
    status = "ready" if all(v == "ok" for v in deps.values()) else "degraded"
    return {"status": status, "dependencies": deps}

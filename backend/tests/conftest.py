import os
os.environ["DATABASE_URL"] = "sqlite:///./test_hysvision.db"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-123456"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "TestAdmin-12345!"
os.environ["CAMERA_CREDENTIAL_KEY"] = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.bootstrap import seed_access_control, seed_admin, seed_ppe_catalog, seed_vision_models

TEST_DB = "sqlite:///./test_hysvision.db"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

def override_get_db():
    db = TestingSession()
    try: yield db
    finally: db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    with TestingSession() as db:
        seed_access_control(db); seed_ppe_catalog(db); seed_admin(db); seed_vision_models(db)
    yield

@pytest.fixture
def client(): return TestClient(app)

@pytest.fixture
def admin_headers(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "TestAdmin-12345!"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

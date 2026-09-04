def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_auth_me(client, admin_headers):
    r = client.get("/api/v1/auth/me", headers=admin_headers)
    assert r.status_code == 200
    assert "SUPERADMIN" in r.json()["role_codes"]

def test_full_hierarchy(client, admin_headers):
    org = client.post("/api/v1/organizations", json={"code":"ACME", "name":"ACME Industrial"}, headers=admin_headers)
    assert org.status_code == 201
    org_id = org.json()["id"]
    site = client.post("/api/v1/sites", json={"organization_id":org_id,"code":"SALTA","name":"Establecimiento Salta","address":"Parque Industrial"}, headers=admin_headers)
    assert site.status_code == 201
    plant = client.post("/api/v1/plants", json={"site_id":site.json()["id"],"code":"P1","name":"Planta Principal"}, headers=admin_headers)
    assert plant.status_code == 201
    sector = client.post("/api/v1/sectors", json={"plant_id":plant.json()["id"],"code":"CARGA","name":"Carga y Descarga"}, headers=admin_headers)
    assert sector.status_code == 201
    summary = client.get("/api/v1/dashboard/foundation-summary", headers=admin_headers).json()
    assert summary == {"organizations":1,"sites":1,"plants":1,"sectors":1,"foundation_status":"OPERATIVO"}

def test_duplicate_org_rejected(client, admin_headers):
    payload={"code":"ACME","name":"ACME"}
    assert client.post("/api/v1/organizations", json=payload, headers=admin_headers).status_code == 201
    assert client.post("/api/v1/organizations", json=payload, headers=admin_headers).status_code == 409

def test_audit_created_for_organization(client, admin_headers):
    created = client.post("/api/v1/organizations", json={"code":"AUD","name":"Auditable"}, headers=admin_headers)
    assert created.status_code == 201
    logs = client.get("/api/v1/audit", headers=admin_headers)
    assert logs.status_code == 200
    assert any(x["entity_type"] == "organization" and x["action"] == "CREATE" for x in logs.json())


def test_duplicate_site_rejected(client, admin_headers):
    org = client.post("/api/v1/organizations", json={"code":"DUPS","name":"Duplicados"}, headers=admin_headers).json()
    payload={"organization_id":org["id"],"code":"CENTRAL","name":"Central"}
    assert client.post("/api/v1/sites", json=payload, headers=admin_headers).status_code == 201
    assert client.post("/api/v1/sites", json=payload, headers=admin_headers).status_code == 409

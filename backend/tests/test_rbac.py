def make_org(client, headers, code):
    return client.post("/api/v1/organizations", json={"code":code,"name":code}, headers=headers).json()

def test_tenant_user_cannot_cross_organization(client, admin_headers):
    org1 = make_org(client, admin_headers, "ORG1")
    org2 = make_org(client, admin_headers, "ORG2")
    create_user = client.post("/api/v1/users", json={
        "organization_id": org1["id"], "email":"empresa@org1.com", "full_name":"Admin Empresa",
        "password":"Password-Org1!", "role_codes":["ADMIN_EMPRESA"]
    }, headers=admin_headers)
    assert create_user.status_code == 201
    token = client.post("/api/v1/auth/login", json={"email":"empresa@org1.com","password":"Password-Org1!"}).json()["access_token"]
    headers={"Authorization":f"Bearer {token}"}
    visible = client.get("/api/v1/organizations", headers=headers)
    assert visible.status_code == 200 and [o["id"] for o in visible.json()] == [org1["id"]]
    forbidden = client.post("/api/v1/sites", json={"organization_id":org2["id"],"code":"X","name":"No permitido"}, headers=headers)
    assert forbidden.status_code == 403

def test_company_admin_cannot_create_organization(client, admin_headers):
    org = make_org(client, admin_headers, "ORG1")
    client.post("/api/v1/users", json={"organization_id":org["id"],"email":"admin@org.com","full_name":"Admin Org","password":"Password-Org!","role_codes":["ADMIN_EMPRESA"]}, headers=admin_headers)
    token=client.post("/api/v1/auth/login", json={"email":"admin@org.com","password":"Password-Org!"}).json()["access_token"]
    r=client.post("/api/v1/organizations", json={"code":"ORG2","name":"ORG2"}, headers={"Authorization":f"Bearer {token}"})
    assert r.status_code == 403

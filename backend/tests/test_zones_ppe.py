import uuid
from sqlalchemy import select

from app.models.safety import PPEType, Zone, ZonePPERule


def hierarchy_with_camera(client, headers, prefix="Z"):
    org = client.post("/api/v1/organizations", json={"code":f"{prefix}ORG","name":f"Org {prefix}"}, headers=headers).json()
    site = client.post("/api/v1/sites", json={"organization_id":org["id"],"code":"S1","name":"Site"}, headers=headers).json()
    plant = client.post("/api/v1/plants", json={"site_id":site["id"],"code":"P1","name":"Plant"}, headers=headers).json()
    sector = client.post("/api/v1/sectors", json={"plant_id":plant["id"],"code":"SEC","name":"Sector"}, headers=headers).json()
    cam = client.post("/api/v1/cameras", json={"sector_id":sector["id"],"code":"CAM1","name":"Demo","source_type":"DEMO_FILE","capture_fps":5}, headers=headers).json()
    return org, site, plant, sector, cam


def valid_polygon():
    return [{"x":0.10,"y":0.10},{"x":0.90,"y":0.10},{"x":0.85,"y":0.85},{"x":0.15,"y":0.80}]


def test_default_ppe_catalog_seeded(client, admin_headers):
    r = client.get("/api/v1/ppe", headers=admin_headers)
    assert r.status_code == 200
    codes = {x["code"] for x in r.json()}
    assert len(codes) >= 12
    assert {"HELMET","VEST","SAFETY_SHOES","GOGGLES","HARNESS"}.issubset(codes)


def test_custom_ppe_is_configurable_without_code_change(client, admin_headers):
    r = client.post("/api/v1/ppe", headers=admin_headers, json={
        "code":"WELDING_APRON","name":"Delantal de soldadura","criticality":"ALTA",
        "color":"#FFAA33","detector_class":"welding_apron","min_confidence":0.81
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["code"] == "WELDING_APRON" and body["min_confidence"] == 0.81


def test_duplicate_ppe_code_rejected(client, admin_headers):
    payload={"code":"CUSTOM","name":"EPP Custom"}
    assert client.post("/api/v1/ppe", headers=admin_headers, json=payload).status_code == 201
    assert client.post("/api/v1/ppe", headers=admin_headers, json=payload).status_code == 409


def test_zone_polygon_is_saved_normalized(client, admin_headers):
    *_, cam = hierarchy_with_camera(client, admin_headers, "NORM")
    r = client.post("/api/v1/zones", headers=admin_headers, json={
        "camera_id":cam["id"],"code":"A","name":"Ingreso general","polygon_points":valid_polygon()
    })
    assert r.status_code == 201, r.text
    body=r.json()
    assert body["camera_id"] == cam["id"]
    assert all(0 <= p["x"] <= 1 and 0 <= p["y"] <= 1 for p in body["polygon_points"])


def test_zone_rejects_less_than_three_points(client, admin_headers):
    *_, cam = hierarchy_with_camera(client, admin_headers, "SHORT")
    r=client.post("/api/v1/zones", headers=admin_headers, json={"camera_id":cam["id"],"code":"A","name":"Zona corta","polygon_points":[{"x":0.1,"y":0.1},{"x":0.9,"y":0.9}]})
    assert r.status_code == 422


def test_zone_rejects_out_of_range_point(client, admin_headers):
    *_, cam = hierarchy_with_camera(client, admin_headers, "OUT")
    points=valid_polygon(); points[1]["x"]=1.5
    r=client.post("/api/v1/zones", headers=admin_headers, json={"camera_id":cam["id"],"code":"A","name":"Zona inválida","polygon_points":points})
    assert r.status_code == 422


def test_zone_rejects_degenerate_polygon(client, admin_headers):
    *_, cam = hierarchy_with_camera(client, admin_headers, "LINE")
    points=[{"x":0.1,"y":0.1},{"x":0.2,"y":0.2},{"x":0.3,"y":0.3}]
    r=client.post("/api/v1/zones", headers=admin_headers, json={"camera_id":cam["id"],"code":"A","name":"Zona línea","polygon_points":points})
    assert r.status_code == 422


def test_rules_are_dynamic_by_zone(client, admin_headers):
    *_, cam = hierarchy_with_camera(client, admin_headers, "RULE")
    zone=client.post("/api/v1/zones", headers=admin_headers, json={"camera_id":cam["id"],"code":"A","name":"Zona A","polygon_points":valid_polygon()}).json()
    ppes=client.get("/api/v1/ppe", headers=admin_headers).json()
    helmet=next(x for x in ppes if x["code"]=="HELMET")
    harness=next(x for x in ppes if x["code"]=="HARNESS")
    payload={"rules":[
        {"ppe_type_id":helmet["id"],"requirement":"REQUIRED","severity":"ALTA"},
        {"ppe_type_id":harness["id"],"requirement":"OPTIONAL","severity":"CRITICA","min_confidence":0.88,"task":"Trabajo en altura"}
    ]}
    r=client.put(f"/api/v1/zones/{zone['id']}/rules",headers=admin_headers,json=payload)
    assert r.status_code == 200, r.text
    rows=r.json(); assert len(rows)==2
    assert next(x for x in rows if x["ppe_code"]=="HARNESS")["effective_min_confidence"] == 0.88


def test_rule_set_rejects_duplicate_ppe(client, admin_headers):
    *_, cam = hierarchy_with_camera(client, admin_headers, "DUPR")
    zone=client.post("/api/v1/zones",headers=admin_headers,json={"camera_id":cam["id"],"code":"A","name":"Zona A","polygon_points":valid_polygon()}).json()
    helmet=next(x for x in client.get("/api/v1/ppe",headers=admin_headers).json() if x["code"]=="HELMET")
    r=client.put(f"/api/v1/zones/{zone['id']}/rules",headers=admin_headers,json={"rules":[{"ppe_type_id":helmet["id"]},{"ppe_type_id":helmet["id"]}]})
    assert r.status_code == 422


def test_replacing_rules_is_idempotent(client, admin_headers):
    *_, cam = hierarchy_with_camera(client, admin_headers, "IDEM")
    zone=client.post("/api/v1/zones",headers=admin_headers,json={"camera_id":cam["id"],"code":"A","name":"Zona A","polygon_points":valid_polygon()}).json()
    helmet=next(x for x in client.get("/api/v1/ppe",headers=admin_headers).json() if x["code"]=="HELMET")
    payload={"rules":[{"ppe_type_id":helmet["id"],"requirement":"REQUIRED","severity":"ALTA"}]}
    assert client.put(f"/api/v1/zones/{zone['id']}/rules",headers=admin_headers,json=payload).status_code==200
    assert client.put(f"/api/v1/zones/{zone['id']}/rules",headers=admin_headers,json=payload).status_code==200
    assert len(client.get(f"/api/v1/zones/{zone['id']}/rules",headers=admin_headers).json())==1


def test_zone_soft_delete_disables_rules(client, admin_headers):
    *_, cam = hierarchy_with_camera(client, admin_headers, "DELZ")
    zone=client.post("/api/v1/zones",headers=admin_headers,json={"camera_id":cam["id"],"code":"A","name":"Zona A","polygon_points":valid_polygon()}).json()
    helmet=next(x for x in client.get("/api/v1/ppe",headers=admin_headers).json() if x["code"]=="HELMET")
    client.put(f"/api/v1/zones/{zone['id']}/rules",headers=admin_headers,json={"rules":[{"ppe_type_id":helmet["id"]}]})
    assert client.delete(f"/api/v1/zones/{zone['id']}",headers=admin_headers).status_code==204
    assert client.get(f"/api/v1/zones/{zone['id']}",headers=admin_headers).json()["active"] is False
    from tests.conftest import TestingSession
    with TestingSession() as db:
        rule=db.scalar(select(ZonePPERule).where(ZonePPERule.zone_id==uuid.UUID(zone["id"])))
        assert rule.active is False


def test_company_admin_can_manage_zone_but_not_global_ppe(client, admin_headers):
    org, site, plant, sector, cam = hierarchy_with_camera(client, admin_headers, "TEN")
    created=client.post("/api/v1/users",headers=admin_headers,json={
        "organization_id":org["id"],"email":"zoneadmin@example.com","full_name":"Zone Admin",
        "password":"Password-Zone1!","role_codes":["ADMIN_EMPRESA"]
    })
    assert created.status_code==201
    tok=client.post("/api/v1/auth/login",json={"email":"zoneadmin@example.com","password":"Password-Zone1!"}).json()["access_token"]
    h={"Authorization":f"Bearer {tok}"}
    assert client.post("/api/v1/zones",headers=h,json={"camera_id":cam["id"],"code":"A","name":"Zona A","polygon_points":valid_polygon()}).status_code==201
    assert client.post("/api/v1/ppe",headers=h,json={"code":"NOPE","name":"No permitido"}).status_code==403

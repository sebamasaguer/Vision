from sqlalchemy import select
from app.models.camera import Camera
from app.services.camera_crypto import decrypt_secret


def hierarchy(client, headers, code="CAM"):
    org = client.post("/api/v1/organizations", json={"code":f"{code}ORG","name":"Org Cameras"}, headers=headers).json()
    site = client.post("/api/v1/sites", json={"organization_id":org["id"],"code":"SITE","name":"Site"}, headers=headers).json()
    plant = client.post("/api/v1/plants", json={"site_id":site["id"],"code":"P1","name":"Plant"}, headers=headers).json()
    sector = client.post("/api/v1/sectors", json={"plant_id":plant["id"],"code":"SEC","name":"Sector"}, headers=headers).json()
    return org, site, plant, sector


def test_create_rtsp_camera_masks_credentials(client, admin_headers):
    _,_,_,sector = hierarchy(client, admin_headers)
    r = client.post("/api/v1/cameras", headers=admin_headers, json={
        "sector_id":sector["id"], "code":"CAM01", "name":"Ingreso",
        "source_type":"RTSP", "rtsp_url":"rtsp://10.0.0.50:554/Streaming/Channels/101",
        "username":"operator", "password":"super-secret", "capture_fps":4
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["rtsp_url_masked"] == "rtsp://10.0.0.50:554/Streaming/Channels/101"
    assert body["credentials_configured"] is True
    assert "password" not in body and "username" not in body


def test_camera_secret_is_encrypted_at_rest(client, admin_headers):
    _,_,_,sector = hierarchy(client, admin_headers, "ENC")
    r = client.post("/api/v1/cameras", headers=admin_headers, json={
        "sector_id":sector["id"], "code":"CAM02", "name":"Carga",
        "source_type":"RTSP", "rtsp_url":"rtsp://192.168.1.2/live", "username":"u", "password":"p"
    })
    assert r.status_code == 201
    from tests.conftest import TestingSession
    with TestingSession() as db:
        cam = db.scalar(select(Camera).where(Camera.code == "CAM02"))
        assert cam.source_url_encrypted != "rtsp://192.168.1.2/live"
        assert cam.password_encrypted != "p"
        assert decrypt_secret(cam.password_encrypted) == "p"


def test_demo_camera_does_not_require_rtsp(client, admin_headers):
    _,_,_,sector = hierarchy(client, admin_headers, "DEMO")
    r = client.post("/api/v1/cameras", headers=admin_headers, json={
        "sector_id":sector["id"], "code":"DEMO01", "name":"Demo Camera",
        "source_type":"DEMO_FILE", "capture_fps":3
    })
    assert r.status_code == 201
    assert r.json()["source_type"] == "DEMO_FILE"


def test_invalid_rtsp_rejected(client, admin_headers):
    _,_,_,sector = hierarchy(client, admin_headers, "BAD")
    r = client.post("/api/v1/cameras", headers=admin_headers, json={
        "sector_id":sector["id"], "code":"BAD01", "name":"Bad Cam",
        "source_type":"RTSP", "rtsp_url":"http://example.com/video"
    })
    assert r.status_code == 422


def test_camera_summary(client, admin_headers):
    _,_,_,sector = hierarchy(client, admin_headers, "SUM")
    client.post("/api/v1/cameras", headers=admin_headers, json={"sector_id":sector["id"],"code":"D1","name":"Demo One","source_type":"DEMO_FILE"})
    s = client.get("/api/v1/cameras/summary", headers=admin_headers)
    assert s.status_code == 200
    assert s.json()["total"] == 1 and s.json()["demo"] == 1


def test_camera_soft_deactivate(client, admin_headers):
    _,_,_,sector = hierarchy(client, admin_headers, "DEL")
    created = client.post("/api/v1/cameras", headers=admin_headers, json={"sector_id":sector["id"],"code":"D2","name":"Demo Two","source_type":"DEMO_FILE"}).json()
    r = client.delete(f"/api/v1/cameras/{created['id']}", headers=admin_headers)
    assert r.status_code == 204
    got = client.get(f"/api/v1/cameras/{created['id']}", headers=admin_headers).json()
    assert got["active"] is False

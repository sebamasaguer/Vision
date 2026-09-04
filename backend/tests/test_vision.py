import time
import numpy as np
from app.services.vision_runtime import IoUTracker, point_in_polygon, assign_zones, OpenCVHOGPersonDetector


def _structure_and_camera(client,headers):
    o=client.post('/api/v1/organizations',headers=headers,json={'code':'VORG','name':'Vision Org'}).json()
    s=client.post('/api/v1/sites',headers=headers,json={'organization_id':o['id'],'code':'S1','name':'Site'}).json()
    p=client.post('/api/v1/plants',headers=headers,json={'site_id':s['id'],'code':'P1','name':'Plant'}).json()
    sec=client.post('/api/v1/sectors',headers=headers,json={'plant_id':p['id'],'code':'SEC','name':'Sector'}).json()
    cam=client.post('/api/v1/cameras',headers=headers,json={'sector_id':sec['id'],'code':'CAMV','name':'Cam Vision','source_type':'DEMO_FILE','capture_fps':5}).json()
    return cam

def test_vision_model_and_camera_settings_exist(client,admin_headers):
    cam=_structure_and_camera(client,admin_headers)
    r=client.get('/api/v1/vision/cameras',headers=admin_headers); assert r.status_code==200
    row=next(x for x in r.json() if x['camera_id']==cam['id'])
    assert row['model']['code']=='OPENCV_HOG_PERSON_BASELINE'; assert row['model']['commercial_use'] is True; assert row['enabled'] is False

def test_enable_vision_updates_camera_setting(client,admin_headers):
    cam=_structure_and_camera(client,admin_headers)
    r=client.patch(f"/api/v1/vision/cameras/{cam['id']}/settings",headers=admin_headers,json={'enabled':True,'inference_fps':2.0,'min_confidence':0.6})
    assert r.status_code==200; assert r.json()['enabled'] is True; assert r.json()['inference_fps']==2.0

def test_runtime_waiting_without_engine_result(client,admin_headers):
    cam=_structure_and_camera(client,admin_headers)
    r=client.get(f"/api/v1/vision/cameras/{cam['id']}/runtime",headers=admin_headers)
    assert r.status_code==200; assert r.json()['persons']==0; assert r.json()['status']=='WAITING'

def test_iou_tracker_keeps_stable_id():
    t=IoUTracker(.2,2); a=t.update([{'bbox':[10,10,50,100],'confidence':.9}],now=1)[0]
    b=t.update([{'bbox':[14,12,50,100],'confidence':.91}],now=2)[0]
    assert a.id==b.id==1; assert b.age==2; assert b.missed==0

def test_iou_tracker_expires_missed_track():
    t=IoUTracker(.2,1); t.update([{'bbox':[1,1,10,20],'confidence':.8}],now=1); t.update([],now=2); t.update([],now=3)
    assert not t.tracks

def test_point_in_polygon_and_zone_assignment():
    pts=[{'x':.1,'y':.1},{'x':.9,'y':.1},{'x':.9,'y':.9},{'x':.1,'y':.9}]
    assert point_in_polygon(.5,.5,pts); assert not point_in_polygon(.95,.5,pts)
    class Z: id='z'; code='Z1'; name='Zona'; polygon_points=pts
    class T: bbox=[40,20,20,50]
    zones=assign_zones(T(),[Z()],100,100); assert zones and zones[0]['code']=='Z1'

def test_real_opencv_hog_detector_initializes_and_runs():
    det=OpenCVHOGPersonDetector(); frame=np.zeros((256,128,3),dtype=np.uint8); out=det.detect(frame,.55)
    assert isinstance(out,list)


def test_camera_ai_flag_syncs_vision_setting(client,admin_headers):
    cam=_structure_and_camera(client,admin_headers)
    r=client.patch(f"/api/v1/cameras/{cam['id']}",headers=admin_headers,json={'ai_enabled':True})
    assert r.status_code==200 and r.json()['ai_enabled'] is True
    settings=client.get(f"/api/v1/vision/cameras/{cam['id']}/settings",headers=admin_headers)
    assert settings.status_code==200 and settings.json()['enabled'] is True


def test_hardening_rejects_upper_band_false_positive():
    from app.services.vision_runtime import harden_person_detections
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    raw = [{'bbox':[223,59,92,185],'confidence':.75}]
    accepted, stats = harden_person_detections(raw, frame.shape)
    assert accepted == []
    assert stats['reasons']['upper_band'] == 1


def test_hardening_keeps_plausible_person_box():
    from app.services.vision_runtime import harden_person_detections
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    raw = [{'bbox':[425,198,169,338],'confidence':.74}]
    accepted, stats = harden_person_detections(raw, frame.shape)
    assert len(accepted) == 1
    assert stats['rejected'] == 0


def test_tracker_requires_temporal_confirmation():
    t = IoUTracker(.25, 4, min_hits_to_confirm=3)
    detection = {'bbox':[100,100,80,200],'confidence':.8}
    t.update([detection], now=1)
    assert len(t.confirmed_tracks()) == 0
    t.update([{'bbox':[102,101,80,200],'confidence':.82}], now=2)
    assert len(t.confirmed_tracks()) == 0
    t.update([{'bbox':[104,102,80,200],'confidence':.83}], now=3)
    confirmed = t.confirmed_tracks()
    assert len(confirmed) == 1 and confirmed[0].id == 1 and confirmed[0].hits == 3


def test_isolated_detection_never_becomes_confirmed_track():
    t = IoUTracker(.25, 1, min_hits_to_confirm=3)
    t.update([{'bbox':[100,100,80,200],'confidence':.8}], now=1)
    assert not t.confirmed_tracks()
    t.update([], now=2)
    t.update([], now=3)
    assert not t.tracks
    assert t.last_candidate_rejections == 1


def test_hardening_rejects_oversized_false_box():
    from app.services.vision_runtime import harden_person_detections
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    raw = [{'bbox':[168,53,252,487],'confidence':.62}]
    accepted, stats = harden_person_detections(raw, frame.shape)
    assert accepted == []
    assert stats['reasons']['area_too_large'] == 1


def test_vision_settings_expose_hardening_controls(client,admin_headers):
    cam=_structure_and_camera(client,admin_headers)
    r=client.get(f"/api/v1/vision/cameras/{cam['id']}/settings",headers=admin_headers)
    assert r.status_code==200
    body=r.json()
    assert body['tracker_min_hits_to_confirm']==3
    assert body['max_box_area_ratio']==0.18
    patched=client.patch(f"/api/v1/vision/cameras/{cam['id']}/settings",headers=admin_headers,json={'tracker_min_hits_to_confirm':4,'min_confidence':0.65})
    assert patched.status_code==200
    assert patched.json()['tracker_min_hits_to_confirm']==4
    assert patched.json()['min_confidence']==0.65

import numpy as np, cv2
from app.services.ppe_runtime import OpenCVSVMPPEDetector, body_regions


def _paint_positive(code):
    img=np.full((80,80,3),110,np.uint8)
    if code=='HELMET':
        cv2.ellipse(img,(40,40),(25,15),0,180,360,(0,220,255),-1); cv2.rectangle(img,(15,40),(65,47),(0,220,255),-1)
    elif code=='VEST':
        cv2.rectangle(img,(10,8),(70,72),(0,220,255),-1); cv2.line(img,(40,8),(40,72),(240,240,240),4)
    else:
        cv2.ellipse(img,(25,50),(20,10),0,0,360,(25,35,45),-1); cv2.ellipse(img,(58,50),(20,10),0,0,360,(25,35,45),-1)
    return img


def test_ppe_svm_models_load_and_run():
    d=OpenCVSVMPPEDetector()
    for code in ('HELMET','VEST','SAFETY_SHOES'):
        positive,conf=d.classify_region(code,_paint_positive(code))
        assert isinstance(positive,bool) and .5<=conf<=1


def test_ppe_states_are_bound_to_same_track_regions():
    d=OpenCVSVMPPEDetector(); frame=np.full((600,400,3),100,np.uint8); box=[100,60,160,480]
    regions=body_regions(box)
    # paint explicit helmet and vest inside their anatomical regions
    hx,hy,hw,hh=[int(v) for v in regions['HELMET']]; cv2.ellipse(frame,(hx+hw//2,hy+hh//2),(hw//3,hh//4),0,0,360,(0,220,255),-1)
    vx,vy,vw,vh=[int(v) for v in regions['VEST']]; cv2.rectangle(frame,(vx+10,vy+10),(vx+vw-10,vy+vh-10),(0,220,255),-1)
    out=d.inspect_track(frame,box,thresholds={'HELMET':.55,'VEST':.55,'SAFETY_SHOES':.99},visibility_ratio=.6)
    assert set(out)=={'HELMET','VEST','SAFETY_SHOES'}
    assert out['HELMET']['status'] in ('OK','INCIERTO')
    assert out['VEST']['status'] in ('OK','INCIERTO')


def test_safety_shoes_no_visible_when_person_is_cut_by_bottom():
    d=OpenCVSVMPPEDetector(); frame=np.full((300,300,3),100,np.uint8)
    out=d.inspect_track(frame,[80,80,120,220],thresholds={'HELMET':.7,'VEST':.7,'SAFETY_SHOES':.7},visibility_ratio=.7)
    assert out['SAFETY_SHOES']['status']=='NO_VISIBLE'


def test_no_visible_is_not_no_detectado():
    d=OpenCVSVMPPEDetector(); frame=np.full((200,200,3),100,np.uint8)
    out=d.inspect_track(frame,[50,120,100,100],visibility_ratio=.8)
    assert out['SAFETY_SHOES']['status']=='NO_VISIBLE'
    assert out['SAFETY_SHOES']['confidence'] is None


def test_vision_api_exposes_ppe_model_and_controls(client,admin_headers):
    o=client.post('/api/v1/organizations',headers=admin_headers,json={'code':'PPEORG','name':'PPE Org'}).json()
    si=client.post('/api/v1/sites',headers=admin_headers,json={'organization_id':o['id'],'code':'S','name':'Site'}).json()
    pl=client.post('/api/v1/plants',headers=admin_headers,json={'site_id':si['id'],'code':'P','name':'Plant'}).json()
    sec=client.post('/api/v1/sectors',headers=admin_headers,json={'plant_id':pl['id'],'code':'SEC','name':'Sector'}).json()
    cam=client.post('/api/v1/cameras',headers=admin_headers,json={'sector_id':sec['id'],'code':'PPECAM','name':'PPE Camera','source_type':'DEMO_FILE','capture_fps':5}).json()
    r=client.get(f"/api/v1/vision/cameras/{cam['id']}/settings",headers=admin_headers)
    assert r.status_code==200; body=r.json(); assert body['ppe_model']['code']=='PPE_REGION_SVM_BASELINE'; assert body['ppe_enabled'] is False
    p=client.patch(f"/api/v1/vision/cameras/{cam['id']}/settings",headers=admin_headers,json={'ppe_enabled':True,'ppe_min_visibility_ratio':.75})
    assert p.status_code==200 and p.json()['ppe_enabled'] is True and p.json()['ppe_min_visibility_ratio']==.75

import cv2, json
from pathlib import Path
from app.services.ppe_runtime import OpenCVSVMPPEDetector

QA_BOX=[425,198,169,338]

def main():
    path=Path('/demo/ppe_demo_person.mp4')
    if not path.exists(): path=Path('../demo/ppe_demo_person.mp4')
    cap=cv2.VideoCapture(str(path)); ppe=OpenCVSVMPPEDetector()
    samples=0; helmet_ok=0; vest_ok=0; shoes_nv=0; idx=0
    while True:
        ok,fr=cap.read()
        if not ok: break
        idx+=1
        if idx%15: continue
        samples+=1
        status=ppe.inspect_track(fr,QA_BOX,thresholds={'HELMET':.70,'VEST':.70,'SAFETY_SHOES':.70},visibility_ratio=.70,uncertainty_margin=.05)
        helmet_ok+=status['HELMET']['status']=='OK'; vest_ok+=status['VEST']['status']=='OK'; shoes_nv+=status['SAFETY_SHOES']['status']=='NO_VISIBLE'
    cap.release()
    result={'samples':samples,'helmet_ok':helmet_ok,'vest_ok':vest_ok,'shoes_no_visible':shoes_nv,'association':'fixed confirmed TRACK QA geometry'}
    print('[PPE-QA]',json.dumps(result,separators=(',',':')))
    if samples<5 or helmet_ok<samples*.7 or vest_ok<samples*.7 or shoes_nv<samples*.7: raise SystemExit(2)
    print('[PASS] EPP por regiones del mismo TRACK: HELMET/VEST OK y SAFETY_SHOES NO_VISIBLE cuando pies quedan fuera de encuadre.')
if __name__=='__main__': main()

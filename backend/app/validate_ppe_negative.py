import cv2, json
from pathlib import Path
from app.services.ppe_runtime import OpenCVSVMPPEDetector
QA_BOX=[425,198,169,338]

def main():
    path=Path('/demo/person_demo_pd.mp4')
    if not path.exists(): path=Path('../demo/person_demo_pd.mp4')
    cap=cv2.VideoCapture(str(path)); ppe=OpenCVSVMPPEDetector(); idx=0; samples=0; helmet_missing=0; vest_missing=0; shoes_nv=0
    while True:
        ok,fr=cap.read()
        if not ok: break
        idx+=1
        if idx%15: continue
        samples+=1; st=ppe.inspect_track(fr,QA_BOX,thresholds={'HELMET':.70,'VEST':.70,'SAFETY_SHOES':.70},visibility_ratio=.70,uncertainty_margin=.05)
        helmet_missing+=st['HELMET']['status']=='NO_DETECTADO'; vest_missing+=st['VEST']['status']=='NO_DETECTADO'; shoes_nv+=st['SAFETY_SHOES']['status']=='NO_VISIBLE'
    cap.release(); result={'samples':samples,'helmet_no_detectado':helmet_missing,'vest_no_detectado':vest_missing,'shoes_no_visible':shoes_nv}; print('[PPE-NEGATIVE]',json.dumps(result,separators=(',',':')))
    if samples<5 or helmet_missing<samples*.7 or vest_missing<samples*.7 or shoes_nv<samples*.7: raise SystemExit(2)
    print('[PASS] Negativo EPP: ausencia visible != NO_VISIBLE; pies fuera de encuadre permanecen NO_VISIBLE.')
if __name__=='__main__': main()

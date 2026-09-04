"""Offline real-video smoke for Block 9.

Does not create Safety Events. It is deliberately isolated from compliance so a model can be
checked on real footage before SHADOW/PRODUCTION deployment.
"""
import argparse, json, subprocess, tempfile
from pathlib import Path
import cv2

from app.services.ppe_runtime import create_ppe_detector
from app.services.vision_runtime import OpenCVHOGPersonDetector, apply_nms, harden_person_detections


def draw_label(img, text, xy, color):
    x,y=xy
    cv2.putText(img,text,(max(2,int(x)),max(18,int(y))),cv2.FONT_HERSHEY_SIMPLEX,.48,color,2,cv2.LINE_AA)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--backend',default='openvino_ir_ppe')
    ap.add_argument('--artifact-uri',default='bootstrap/intel-worker-safety/model.xml')
    ap.add_argument('--max-seconds',type=float,default=60.0)
    ap.add_argument('--sample-every',type=int,default=1)
    args=ap.parse_args()

    inp=Path(args.input); out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    if not inp.exists(): raise SystemExit(f'input inexistente: {inp}')
    # Runtime graph shape/output semantics are authoritative; do not force stale
    # registry dimensions into the OpenVINO bootstrap smoke test.
    ppe=create_ppe_detector(args.backend, {
        'default_threshold':0.35, 'helmet_threshold':0.57, 'vest_threshold':0.525
    }, args.artifact_uri)
    person=OpenCVHOGPersonDetector()
    cap=cv2.VideoCapture(str(inp))
    if not cap.isOpened(): raise SystemExit(f'no se pudo abrir video: {inp}')
    fps=float(cap.get(cv2.CAP_PROP_FPS) or 15.0); w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    max_frames=int(max(1,args.max_seconds*fps)); frame_idx=0
    temp=out.with_suffix('.temp.mp4')
    writer=cv2.VideoWriter(str(temp),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
    counts={'HELMET':0,'VEST':0,'PERSON':0,'frames':0,'frames_with_ppe':0,'track_checks':0}
    thresholds={'HELMET':.45,'VEST':.45,'SAFETY_SHOES':.70}
    while frame_idx<max_frames:
        ok,frame=cap.read()
        if not ok: break
        frame_idx+=1
        if args.sample_every>1 and frame_idx%args.sample_every:
            writer.write(frame); continue
        counts['frames']+=1
        # Full-frame PPE detections prove real-model execution even if HOG misses a person.
        full=[]
        if hasattr(ppe,'_detect_crop'):
            try: full=ppe._detect_crop(frame,threshold=.35)
            except TypeError: full=ppe._detect_crop(frame)
        if full: counts['frames_with_ppe']+=1
        for d in full:
            code=d['code']; counts[code]=counts.get(code,0)+1
            x,y,bw,bh=[int(round(v)) for v in d['bbox']]
            color=(70,220,160) if code=='HELMET' else (70,190,235)
            cv2.rectangle(frame,(x,y),(x+bw,y+bh),color,2)
            draw_label(frame,f"{code} {d['confidence']:.0%}",(x,y-5),color)
        raw=person.detect_raw(frame,.55)
        hardened,_=harden_person_detections(raw,frame.shape,min_box_area_ratio=.005,max_box_area_ratio=.70,min_height_ratio=.15,min_aspect_ratio=.20,max_aspect_ratio=1.15,top_band_reject_y_ratio=.02,top_band_reject_bottom_ratio=.20)
        people=apply_nms(hardened,.55,.35)
        counts['PERSON']+=len(people)
        for i,p in enumerate(people,1):
            x,y,bw,bh=[int(round(v)) for v in p['bbox']]
            cv2.rectangle(frame,(x,y),(x+bw,y+bh),(80,220,180),2)
            draw_label(frame,f"PERSON {p['confidence']:.0%}",(x,y-8),(80,220,180))
            try:
                status=ppe.inspect_track(frame,p['bbox'],thresholds=thresholds,visibility_ratio=.55,uncertainty_margin=.08)
                counts['track_checks']+=1
                line=[]
                for code in ('HELMET','VEST','SAFETY_SHOES'):
                    st=(status.get(code) or {}).get('status','N/A'); line.append(f'{code}:{st}')
                draw_label(frame,' | '.join(line),(x,y+bh+18),(220,220,220))
            except Exception as exc:
                draw_label(frame,f'PPE ERROR {str(exc)[:60]}',(x,y+bh+18),(60,80,230))
        writer.write(frame)
    cap.release();writer.release()
    # Browser-compatible H.264 evidence/result.
    cmd=['ffmpeg','-y','-loglevel','error','-i',str(temp),'-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p','-movflags','+faststart','-an',str(out)]
    try:
        subprocess.run(cmd,check=True)
        temp.unlink(missing_ok=True)
    except Exception:
        temp.replace(out)
    summary=out.with_suffix('.json')
    summary.write_text(json.dumps({'input':str(inp),'output':str(out),'backend':args.backend,'counts':counts},ensure_ascii=False,indent=2),encoding='utf-8')
    print('BLOCK9_REAL_VIDEO_OK '+json.dumps(counts,separators=(',',':')))
    print(f'OUTPUT={out}')
    print(f'SUMMARY={summary}')

if __name__=='__main__': main()

import argparse, hashlib, json, random, shutil
from pathlib import Path
import cv2


def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def extract(args):
    src=Path(args.input); out=Path(args.output); imgs=out/'images'; imgs.mkdir(parents=True,exist_ok=True)
    cap=cv2.VideoCapture(str(src))
    if not cap.isOpened(): raise SystemExit(f'No se pudo abrir {src}')
    fps=float(cap.get(cv2.CAP_PROP_FPS) or 25.0); every=max(1,int(round(fps*args.every_seconds)))
    idx=0; saved=0; hashes=set(); records=[]
    while True:
        ok,frame=cap.read()
        if not ok: break
        idx+=1
        if idx % every: continue
        okb,buf=cv2.imencode('.jpg',frame,[int(cv2.IMWRITE_JPEG_QUALITY),92])
        if not okb: continue
        digest=hashlib.sha256(buf.tobytes()).hexdigest()
        if digest in hashes: continue
        hashes.add(digest); saved+=1
        name=f'frame_{saved:06d}.jpg'; (imgs/name).write_bytes(buf.tobytes())
        records.append({'file':name,'source_frame':idx,'source_second':round(idx/fps,3),'sha256':digest})
        if args.max_images and saved>=args.max_images: break
    cap.release()
    manifest={'source':str(src),'fps':fps,'every_seconds':args.every_seconds,'images':saved,'records':records}
    (out/'EXTRACTION_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'BLOCK9_DATASET_EXTRACT_OK images={saved} output={out}')


def yolo_boxes(label_path,w,h,classes):
    anns=[]
    if not label_path.exists(): return anns
    for lineno,line in enumerate(label_path.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip(): continue
        parts=line.split()
        if len(parts)<5: raise ValueError(f'{label_path}:{lineno} etiqueta inválida')
        cls=int(parts[0]); xc,yc,bw,bh=map(float,parts[1:5])
        if cls<0 or cls>=len(classes): raise ValueError(f'{label_path}:{lineno} clase {cls} fuera de rango')
        x=max(0.0,(xc-bw/2)*w); y=max(0.0,(yc-bh/2)*h); ww=max(1.0,min(w-x,bw*w)); hh=max(1.0,min(h-y,bh*h))
        anns.append((cls,[x,y,ww,hh]))
    return anns


def build_coco(args):
    root=Path(args.source); images_dir=root/'images'; labels_dir=root/'labels'; out=Path(args.output)
    classes=[x.strip() for x in args.classes.split(',') if x.strip()]
    if not classes: raise SystemExit('Clases requeridas')
    files=sorted([p for p in images_dir.iterdir() if p.suffix.lower() in {'.jpg','.jpeg','.png','.bmp'}])
    if len(files)<3: raise SystemExit('Se requieren al menos 3 imágenes etiquetadas')
    missing=[p.name for p in files if not (labels_dir/(p.stem+'.txt')).exists()]
    if missing and not args.allow_empty: raise SystemExit(f'Faltan etiquetas para {len(missing)} imágenes; primera={missing[0]}')
    rng=random.Random(args.seed); rng.shuffle(files)
    n=len(files); n_test=max(1,round(n*args.test)); n_val=max(1,round(n*args.val)); n_train=n-n_val-n_test
    if n_train<1: n_train=1; n_val=max(1,n-2); n_test=n-n_train-n_val
    splits={'train2017':files[:n_train],'val2017':files[n_train:n_train+n_val],'test2017':files[n_train+n_val:]}
    ann_dir=out/'annotations'; ann_dir.mkdir(parents=True,exist_ok=True)
    categories=[{'id':i+1,'name':name,'supercategory':'PPE'} for i,name in enumerate(classes)]
    total_anns=0; split_counts={}
    for split,items in splits.items():
        sd=out/split; sd.mkdir(parents=True,exist_ok=True); images=[]; annotations=[]; aid=1
        for iid,p in enumerate(items,1):
            img=cv2.imread(str(p));
            if img is None: raise SystemExit(f'Imagen ilegible: {p}')
            h,w=img.shape[:2]; shutil.copy2(p,sd/p.name)
            images.append({'id':iid,'file_name':p.name,'width':w,'height':h})
            for cls,bbox in yolo_boxes(labels_dir/(p.stem+'.txt'),w,h,classes):
                annotations.append({'id':aid,'image_id':iid,'category_id':cls+1,'bbox':[round(x,3) for x in bbox],'area':round(bbox[2]*bbox[3],3),'iscrowd':0,'segmentation':[]}); aid+=1
        data={'info':{'description':'HYS Vision IA PPE Dataset','version':args.version},'licenses':[{'id':1,'name':args.license}], 'images':images,'annotations':annotations,'categories':categories}
        (ann_dir/f'instances_{split}.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        total_anns+=len(annotations); split_counts[split]=len(items)
    manifest_files=sorted([p for p in out.rglob('*') if p.is_file()])
    h=hashlib.sha256()
    for p in manifest_files:
        h.update(str(p.relative_to(out)).encode()); h.update(sha256_file(p).encode())
    manifest={'version':args.version,'license':args.license,'classes':classes,'image_count':n,'annotation_count':total_anns,'train_count':split_counts['train2017'],'val_count':split_counts['val2017'],'test_count':split_counts['test2017'],'manifest_sha256':h.hexdigest(),'format':'COCO','source_format':'YOLO-normalized'}
    (out/'DATASET_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('BLOCK9_DATASET_COCO_OK '+json.dumps(manifest,separators=(',',':')))


def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True)
    e=sp.add_parser('extract'); e.add_argument('--input',required=True); e.add_argument('--output',required=True); e.add_argument('--every-seconds',type=float,default=1.0); e.add_argument('--max-images',type=int,default=500); e.set_defaults(fn=extract)
    c=sp.add_parser('build-coco'); c.add_argument('--source',required=True); c.add_argument('--output',required=True); c.add_argument('--classes',default='HELMET,VEST,SAFETY_SHOES'); c.add_argument('--version',default='v0001'); c.add_argument('--license',default='PROPRIETARY-HYS'); c.add_argument('--val',type=float,default=.10); c.add_argument('--test',type=float,default=.10); c.add_argument('--seed',type=int,default=42); c.add_argument('--allow-empty',action='store_true'); c.set_defaults(fn=build_coco)
    a=ap.parse_args(); a.fn(a)

if __name__=='__main__': main()

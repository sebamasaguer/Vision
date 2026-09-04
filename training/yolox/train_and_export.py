import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path


def run(cmd, env=None, cwd=None):
    print('+',' '.join(map(str,cmd)),flush=True)
    subprocess.run(list(map(str,cmd)),check=True,env=env,cwd=cwd)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dataset',required=True,help='COCO root containing annotations/, train2017/, val2017/, test2017/')
    ap.add_argument('--run-id',required=True); ap.add_argument('--base',default='yolox_nano')
    ap.add_argument('--epochs',type=int,default=50); ap.add_argument('--img-size',type=int,default=416); ap.add_argument('--batch',type=int,default=8)
    ap.add_argument('--device',default='cuda'); ap.add_argument('--classes',default='HELMET,VEST,SAFETY_SHOES')
    ap.add_argument('--output-root',default='/models/hys'); ap.add_argument('--runs-root',default='/runs')
    args=ap.parse_args()
    if args.device.lower() not in {'cuda','gpu','0'}:
        raise SystemExit('YOLOX 0.3.0 training in this Block 9 image requires NVIDIA/CUDA. Use a CUDA host/Colab for training; inference remains CPU/ONNX.')
    try:
        import torch
        if not torch.cuda.is_available(): raise SystemExit('CUDA no disponible en trainer. El pipeline puede prepararse aquí y entrenarse luego en GPU/Colab.')
    except ImportError: raise SystemExit('PyTorch no disponible')
    coco=Path(args.dataset)
    for p in ['annotations/instances_train2017.json','annotations/instances_val2017.json','train2017','val2017']:
        if not (coco/p).exists(): raise SystemExit(f'Dataset COCO incompleto: {coco/p}')
    classes=[x.strip() for x in args.classes.split(',') if x.strip()]
    run_dir=Path(args.runs_root)/args.run_id; run_dir.mkdir(parents=True,exist_ok=True)
    out_dir=Path(args.output_root)/args.run_id; out_dir.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy(); env.update({
        'HYS_COCO_DIR':str(coco),'HYS_NUM_CLASSES':str(len(classes)),'HYS_IMAGE_SIZE':str(args.img_size),
        'HYS_EPOCHS':str(args.epochs),'HYS_EXPERIMENT':f'hys_ppe_{args.run_id}',
    })
    exp='/workspace/hys_ppe_exp.py'; root='/opt/YOLOX'
    started=time.time()
    run(['python','tools/train.py','-f',exp,'-d','1','-b',str(args.batch),'--fp16'],env=env,cwd=root)
    ckpt=Path(root)/'YOLOX_outputs'/f'hys_ppe_{args.run_id}'/'best_ckpt.pth'
    if not ckpt.exists(): raise SystemExit(f'Checkpoint no encontrado: {ckpt}')
    onnx=out_dir/f'HYS_PPE_{args.run_id}.onnx'
    run(['python','tools/export_onnx.py','-f',exp,'-c',str(ckpt),'--output-name',str(onnx),'--decode_in_inference','--no-onnxsim'],env=env,cwd=root)
    import hashlib
    h=hashlib.sha256(onnx.read_bytes()).hexdigest()
    manifest={'run_id':args.run_id,'base':args.base,'classes':classes,'epochs':args.epochs,'image_size':args.img_size,'batch':args.batch,'artifact':str(onnx),'sha256':h,'elapsed_seconds':round(time.time()-started,2),'training_stack':'YOLOX 0.3.0 Apache-2.0','ultralytics_used':False}
    (out_dir/'MODEL_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('BLOCK9_TRAIN_EXPORT_OK '+json.dumps(manifest,separators=(',',':')))

if __name__=='__main__': main()

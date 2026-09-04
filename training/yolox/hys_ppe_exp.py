import os
from yolox.exp import Exp as BaseExp

class Exp(BaseExp):
    def __init__(self):
        super().__init__()
        self.num_classes=int(os.environ.get('HYS_NUM_CLASSES','3'))
        self.depth=float(os.environ.get('HYS_DEPTH','0.33'))
        self.width=float(os.environ.get('HYS_WIDTH','0.25'))
        size=int(os.environ.get('HYS_IMAGE_SIZE','416'))
        self.input_size=(size,size); self.test_size=(size,size)
        self.random_size=(max(8,size//32-3), size//32+3)
        self.mosaic_scale=(0.5,1.5); self.mosaic_prob=.5; self.enable_mixup=False
        self.data_dir=os.environ['HYS_COCO_DIR']
        self.train_ann='instances_train2017.json'; self.val_ann='instances_val2017.json'; self.test_ann='instances_test2017.json'
        self.max_epoch=int(os.environ.get('HYS_EPOCHS','50'))
        self.warmup_epochs=min(5,max(1,self.max_epoch//10)); self.no_aug_epochs=min(15,max(1,self.max_epoch//10))
        self.data_num_workers=int(os.environ.get('HYS_WORKERS','4'))
        self.eval_interval=max(1,int(os.environ.get('HYS_EVAL_INTERVAL','5')))
        self.print_interval=10
        self.exp_name=os.environ.get('HYS_EXPERIMENT','hys_ppe_yolox_nano')

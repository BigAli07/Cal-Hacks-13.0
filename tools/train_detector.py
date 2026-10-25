"""Fine-tune a detector from local box-labelled data; no fabricated training results."""
import argparse
from pathlib import Path
from ultralytics import YOLO

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--model',default='yolov8n.pt')
    p.add_argument('--epochs',type=int,default=50)
    p.add_argument('--device',default='cpu')
    a=p.parse_args()
    if not a.data.is_file():p.error('Provide the converted dataset YAML')
    if a.epochs<1:p.error('epochs must be positive')
    model=YOLO(a.model)
    model.train(data=str(a.data.resolve()),epochs=a.epochs,imgsz=640,batch=8,device=a.device,
                seed=42,deterministic=True,project='runs',name='handheld',
                degrees=15,translate=.1,scale=.4,mosaic=.5,mixup=.1,close_mosaic=10)
    # Held-out real hand-occluded images still required; mixup is not a substitute.
    best=Path(model.trainer.best)
    print(f'Validate real held-out occluded clips before deploying {best}')
    YOLO(str(best)).val(data=str(a.data.resolve()),imgsz=640,device=a.device)

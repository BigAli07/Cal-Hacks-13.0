"""Add reproducible synthetic occluders to training images only. Keep validation real."""
import argparse
import random
from pathlib import Path
import cv2
import numpy as np


def augment(root, seed=42):
    rng=random.Random(seed); count=0
    for image_path in sorted((root/'images/train').glob('*')):
        if image_path.stem.endswith('_occluded'):continue
        label=root/'labels/train'/(image_path.stem+'.txt')
        if not label.exists():continue
        frame=cv2.imread(str(image_path))
        if frame is None:continue
        h,w=frame.shape[:2]
        lines=label.read_text().splitlines()
        if not lines:continue
        # Cover 15–35% of one annotated object's width. Preserve full-object boxes.
        _,cx,cy,bw,bh=map(float,rng.choice(lines).split())
        x1=int((cx-bw/2)*w);y1=int((cy-bh/2)*h)
        ow=max(1,int(bw*w*rng.uniform(.15,.35)));oh=max(1,int(bh*h*.8))
        ox=max(0,min(w-ow,x1+int(bw*w*rng.uniform(.1,.5))))
        oy=max(0,min(h-oh,y1+int(bh*h*.1)))
        frame[oy:oy+oh,ox:ox+ow]=np.array([rng.randrange(30,220) for _ in range(3)],dtype=np.uint8)
        out=image_path.with_name(image_path.stem+'_occluded.jpg')
        cv2.imwrite(str(out),frame)
        label.with_name(image_path.stem+'_occluded.txt').write_text('\n'.join(lines)+'\n')
        count+=1
    print(f'Created {count} synthetic training variants. These are not real-hand validation samples.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('dataset',type=Path)
    a=p.parse_args();augment(a.dataset)

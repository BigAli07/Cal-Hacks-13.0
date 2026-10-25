"""Capture checkerboard views with the same camera/resolution as the live demo."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--camera',type=int,default=0)
    p.add_argument('--columns',type=int,default=9,help='Inner corners, not squares')
    p.add_argument('--rows',type=int,default=6)
    p.add_argument('--square-m',type=float,required=True)
    p.add_argument('--width',type=int,default=640)
    p.add_argument('--height',type=int,default=480)
    p.add_argument('--output',type=Path,default=Path('calibration.json'))
    a=p.parse_args()
    if not 0<a.square_m<1 or min(a.columns,a.rows)<3: p.error('Invalid board geometry')
    obj=np.zeros((a.columns*a.rows,3),np.float32)
    obj[:,:2]=np.mgrid[0:a.columns,0:a.rows].T.reshape(-1,2)*a.square_m
    cap=cv2.VideoCapture(a.camera); cap.set(3,a.width); cap.set(4,a.height)
    objects=[]; images=[]; size=None
    print('SPACE: capture board. C: calibrate after >=15 varied views. Q: quit.')
    try:
        while True:
            ok,frame=cap.read()
            if not ok: raise RuntimeError('Camera unavailable')
            size=(frame.shape[1],frame.shape[0])
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            found,corners=cv2.findChessboardCornersSB(gray,(a.columns,a.rows))
            if found: cv2.drawChessboardCorners(frame,(a.columns,a.rows),corners,found)
            cv2.putText(frame,f'Views: {len(images)} | SPACE capture | C solve', (10,25),0,.6,(0,255,0),2)
            cv2.imshow('Calibration',frame); k=cv2.waitKey(1)&255
            if k==ord('q'): return
            if k==32 and found:
                if images and min(np.mean(np.linalg.norm(corners-x,axis=2)) for x in images)<15:
                    print('Move/tilt the board; this view is too similar.'); continue
                objects.append(obj.copy()); images.append(corners)
            if k==ord('c') and len(images)>=15: break
        rms,K,dist,_,_=cv2.calibrateCamera(objects,images,size,None,None)
        if rms>1.5: raise ValueError(f'RMS {rms:.2f}px too high; collect sharper, varied views.')
        a.output.write_text(json.dumps(dict(camera_matrix=K.tolist(),distortion=dist.flatten().tolist(),image_size=size,rms_px=rms,views=len(images)),indent=2))
        print(f'Saved {a.output}; RMS={rms:.3f}px. Validate against a ruler before use.')
    finally:
        cap.release(); cv2.destroyAllWindows()

if __name__=='__main__': main()

"""Current-frame detection with a second look at people holding small objects."""
from dataclasses import replace


def iou(a,b):
    intersection=max(0,min(a.x2,b.x2)-max(a.x1,b.x1))*max(0,min(a.y2,b.y2)-max(a.y1,b.y1))
    union=(a.x2-a.x1)*(a.y2-a.y1)+(b.x2-b.x1)*(b.y2-b.y1)-intersection
    return intersection/union if union>0 else 0


def detect_objects(model, frame, confidence, image_size, convert):
    result=model.predict(source=frame,conf=confidence,imgsz=image_size,verbose=False)[0]
    detections=convert(result)
    h,w=frame.shape[:2]
    # Crop the person region to increase pixels allocated to handheld objects.
    # No temporal carry-forward: hidden objects remain undetected.
    people=sorted([d for d in detections if d.label=='person'],key=lambda d:d.confidence,reverse=True)[:2]
    for person in people:
        x1=max(0,person.x1-20);x2=min(w,person.x2+20)
        y1=max(0,person.y1-20);y2=min(h,person.y2+20)
        if x2-x1<64 or y2-y1<64 or (x2-x1)*(y2-y1)>.85*w*h:continue
        crop_result=model.predict(source=frame[y1:y2,x1:x2],conf=confidence,imgsz=image_size,verbose=False)[0]
        for d in convert(crop_result):
            if d.label in ('drink can','tin can','bottle','cup'):
                detections.append(replace(d,x1=d.x1+x1,y1=d.y1+y1,x2=d.x2+x1,y2=d.y2+y1))
    kept=[]
    for d in sorted(detections,key=lambda d:d.confidence,reverse=True):
        if not any(d.label==k.label and iou(d,k)>.45 for k in kept):kept.append(d)
    return kept

"""Convert locally licensed ImageNet XML box annotations to YOLO detection data.
Mapping JSON: {"nXXXXXXXX": "drink can", ...}. Never turn image labels into boxes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import yaml


def convert(images, annotations, mapping, output):
    names=sorted(set(mapping.values()))
    if not names: raise ValueError('Class mapping is empty')
    count={'train':0,'val':0}; skipped=0
    for xml in sorted(annotations.rglob('*.xml')):
        tree=ET.parse(xml).getroot()
        w=float(tree.findtext('size/width','0')); h=float(tree.findtext('size/height','0'))
        if min(w,h)<=0: raise ValueError(f'Invalid image size: {xml}')
        # ImageNet filenames are synset-prefixed and unique; resolve exact stem only.
        matches=[p for p in images.rglob(xml.stem+'.*') if p.suffix.lower() in ('.jpeg','.jpg','.png')]
        if len(matches)!=1: skipped+=1; continue
        image=matches[0]; labels=[]
        for obj in tree.findall('object'):
            synset=obj.findtext('name')
            if synset not in mapping: continue
            b=obj.find('bndbox')
            if b is None: continue
            x1,y1,x2,y2=[float(b.findtext(k)) for k in ('xmin','ymin','xmax','ymax')]
            x1=max(0,x1-1);y1=max(0,y1-1);x2=min(w,x2);y2=min(h,y2)
            if x2<=x1 or y2<=y1: raise ValueError(f'Invalid box: {xml}')
            labels.append(f'{names.index(mapping[synset])} {(x1+x2)/2/w:.8f} {(y1+y2)/2/h:.8f} {(x2-x1)/w:.8f} {(y2-y1)/h:.8f}')
        if not labels: skipped+=1; continue
        # Content-hash split keeps duplicate images in the same split.
        digest=hashlib.sha256(image.read_bytes()).hexdigest()
        split='val' if int(digest[:8],16)%5==0 else 'train'
        image_dir=output/'images'/split; label_dir=output/'labels'/split
        image_dir.mkdir(parents=True,exist_ok=True);label_dir.mkdir(parents=True,exist_ok=True)
        destination=image_dir/(digest+image.suffix.lower())
        if destination.exists(): continue
        shutil.copy2(image,destination)
        (label_dir/(digest+'.txt')).write_text('\n'.join(labels)+'\n')
        count[split]+=1
    if min(count.values())==0: raise ValueError(f'Need train and validation examples; got {count}')
    (output/'data.yaml').write_text(yaml.safe_dump({'path':str(output.resolve()),'train':'images/train','val':'images/val','names':dict(enumerate(names))}))
    print(json.dumps({'converted':count,'skipped':skipped,'classes':names}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','annotations','mapping','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();convert(a.images,a.annotations,json.loads(a.mapping.read_text()),a.output)

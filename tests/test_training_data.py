import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import cv2
import numpy as np
import yaml
from prepare_imagenet import convert
from augment_occlusion import augment

def test_imagenet_boxes_split_before_augmentation(tmp_path):
    images=tmp_path/'images'; xml=tmp_path/'xml'; out=tmp_path/'dataset'
    images.mkdir();xml.mkdir()
    for i in range(30):
        cv2.imwrite(str(images/f'synset_{i}.jpg'),np.full((80,100,3),i*7,np.uint8))
        (xml/f'synset_{i}.xml').write_text('<annotation><size><width>100</width><height>80</height></size><object><name>verified_synset</name><bndbox><xmin>11</xmin><ymin>9</ymin><xmax>50</xmax><ymax>40</ymax></bndbox></object></annotation>')
    convert(images,xml,{'verified_synset':'drink can'},out)
    config=yaml.safe_load((out/'data.yaml').read_text())
    assert config['names']=={0:'drink can'}
    train=list((out/'labels/train').glob('*.txt')); val=list((out/'labels/val').glob('*.txt'))
    assert train and val
    assert not {p.stem for p in train}&{p.stem for p in val}
    first=train[0].read_text().split(); assert first[0]=='0'
    assert [float(x) for x in first[1:]]==[.3,.3,.4,.4]
    augment(out)
    assert len(list((out/'labels/train').glob('*.txt')))==len(train)*2
    assert len(list((out/'labels/val').glob('*.txt')))==len(val)

import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pi'))
from metric_depth import apply_depth


def scene():
    return {'frame':{'width_px':640,'height_px':480},'objects':[{'model_label':'can','box':[400,160,480,320]}],'checkpoints':{}}


def test_automatic_depth_without_height_or_fov():
    event=scene();apply_depth(event,np.full((480,640),2.0))
    obj=event['objects'][0]
    assert obj['distance_m']==2
    assert obj['distance_kind']=='optical_depth'
    assert obj['horizontal_angle_deg'] is None
    assert event['checkpoints']['object_distance']['estimated']==1


def test_angle_corrected_range_and_invalid_depth():
    event=scene();apply_depth(event,np.full((480,640),2.),fov=90)
    obj=event['objects'][0]
    assert obj['distance_m']==pytest.approx(2*np.sqrt(1+(120/320)**2))
    assert obj['distance_kind']=='slant_range'
    event=scene();apply_depth(event,np.full((480,640),np.nan))
    assert event['objects'][0]['distance_m'] is None
    with pytest.raises(ValueError): apply_depth(scene(),np.zeros((2,2)))


def test_inset_avoids_bbox_edges_and_flags_mixed_surfaces():
    depth=np.full((480,640),8.)
    depth[200:280,420:460]=1.
    event=scene();apply_depth(event,depth)
    assert event['objects'][0]['distance_m']==1.
    depth[200:240,420:460]=3.
    event=scene();apply_depth(event,depth)
    assert event['objects'][0]['depth_quality']=='mixed_surfaces'

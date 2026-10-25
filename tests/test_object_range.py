import copy
import sys
from pathlib import Path
import numpy as np
import cv2
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pi'))
from geometry import Calibration
from object_range import estimate_objects, validate_settings
from hardware_plugin import ScenePlugin
from camera_vision import build_output_event, Detection


def scene(box):
    return {'frame':{'width_px':640,'height_px':480},'objects':[{'box':box,'model_label':'can'}], 'checkpoints':{}}


def test_off_axis_range_and_distortion():
    K=np.array([[600.,0,320],[0,600,240],[0,0,1]])
    dist=np.array([.1,-.02,0,0,0])
    cal=Calibration({'camera_matrix':K.tolist(),'distortion':dist.tolist(),'image_size':[640,480],'rms_px':.2})
    # Symmetric y makes distorted vertical endpoints share the same x coordinate.
    xyz=np.array([[.3,-.1,1.5],[.3,.1,1.5]])
    p,_=cv2.projectPoints(xyz,np.zeros(3),np.zeros(3),K,dist);p=p.reshape(2,2)
    cx=p[0,0]
    event=scene([cx-20,p[0,1],cx+20,p[1,1]])
    estimate_objects(event,cal,{'heights_m':{'can':.2},'full_height_visible':True})
    result=event['objects'][0]
    assert result['optical_depth_m']==pytest.approx(1.5,abs=.001)
    assert result['distance_m']==pytest.approx(np.linalg.norm([.3,0,1.5]),abs=.001)
    assert result['horizontal_angle_deg']==pytest.approx(np.degrees(np.arctan2(.3,1.5)),abs=.02)


def test_range_rejects_missing_hidden_clipped_and_ambiguous():
    settings={'heights_m':{'can':.12},'horizontal_fov_deg':60,'full_height_visible':True}
    event=scene([300,200,340,280]);estimate_objects(event,settings=settings)
    assert event['objects'][0]['distance_m']>0
    for box,extra,expected in [([300,200,340,280],{'full_height_visible':False},'confirm_full_height_upright'),
                               ([300,0,340,280],{},'clipped_object'),([300,200,340,210],{},'box_too_small'),
                               ([300,200,340,280],{'horizontal_fov_deg':None},'needs_calibration_or_measured_fov')]:
        event=scene(box);estimate_objects(event,settings=settings|extra)
        assert event['objects'][0]['distance_m'] is None
        assert event['objects'][0]['distance_status']==expected
    event=scene([300,200,340,280]);event['objects']*=2
    estimate_objects(event,settings=settings)
    assert event['objects'][0]['distance_status']=='ambiguous_same_label_instances'
    for bad in [{'heights_m':{'can':float('nan')}},{'horizontal_fov_deg':180},{'full_height_visible':'true'}]:
        with pytest.raises(ValueError):validate_settings(bad)


def test_scene_no_navigation_and_plugin_isolation():
    event=build_output_event([Detection('can',.9,300,200,340,280)],{'left':0,'forward':.2,'right':0},640,480,.13,{},6,4,None)
    assert 'action' not in event
    plugin=ScenePlugin()
    class Adapter:
        def publish(self, scene):
            scene['objects'].clear()
            raise OSError('disconnected')
    plugin.adapter=Adapter()
    assert plugin.publish(event)['status']=='adapter_error'
    assert len(event['objects'])==1

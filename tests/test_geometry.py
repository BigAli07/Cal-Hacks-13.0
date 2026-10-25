import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pi'))
import cv2
import numpy as np
import pytest
from geometry import Calibration, marker_points, solve_marker, RangeEstimator
from haptics import channels_for, packet
from checkpoints import enrich

K=np.array([[800.,0,320],[0,800.,240],[0,0,1.]])
D=np.array([.08,-.03,.001,-.001,0.])

@pytest.mark.parametrize('t,r',[([0,0,.5],[3.0,.1,0]),([.2,.1,1.2],[2.8,.3,.2]),([-.3,-.1,1.5],[2.6,.2,0])])
def test_metric_pose_with_tilt_and_distortion(t,r):
    corners,_=cv2.projectPoints(marker_points(.05),np.array(r),np.array(t,dtype=float),K,D)
    result=solve_marker(corners,.05,K,D)
    assert result is not None
    assert result['distance_m']==pytest.approx(np.linalg.norm(t),rel=1e-4)
    assert result['optical_depth_m']==pytest.approx(t[2],rel=1e-4)
    assert result['horizontal_angle_deg']==pytest.approx(np.degrees(np.arctan2(t[0],t[2])),abs=.01)


def test_calibration_and_missing_measurement():
    c=Calibration(dict(camera_matrix=K.tolist(),distortion=D.tolist(),image_size=[640,480],rms_px=.3))
    with pytest.raises(ValueError):c.matrix(640,360)
    assert RangeEstimator().measure(np.zeros((480,640,3),np.uint8))['status']=='needs_calibration'
    assert RangeEstimator(c).measure(np.zeros((480,640,3),np.uint8))['markers']==[]
    assert solve_marker(np.zeros((4,2)),.05,K,D) is None


def test_three_channels_no_stale_or_unknown_range():
    assert channels_for([])==[0,0,0]
    assert channels_for([dict(distance_m=float('nan'),horizontal_angle_deg=0,status='measured_reference')])==[0,0,0]
    assert channels_for([dict(distance_m=.2,horizontal_angle_deg=-20,status='measured_reference')])==[255,0,0]
    assert packet([1,2,3])==b'P1,1,2,3\n'
    with pytest.raises(ValueError):packet([256,0,0])


def test_checkpoints_do_not_invent_detections_or_object_ranges():
    event={'objects':[]}
    enrich(event,{'status':'needs_calibration','markers':[]},'drink can',['person'])
    assert event['checkpoints']['detection']['status']=='unsupported_label'
    assert event['haptics']['channels']==[0,0,0]
    event={'objects':[{'model_label':'drink can','confidence':.8,'distance_m':None}]}
    enrich(event,{'status':'no_valid_marker','markers':[]},'drink can',['drink can'])
    assert event['checkpoints']['detection']['status']=='detected'
    assert event['objects'][0]['distance_m'] is None


def test_crop_detection_is_current_frame_and_deduplicated():
    from camera_vision import Detection
    from detection import detect_objects
    person=Detection('person',.9,50,50,250,450)
    can=Detection('drink can',.8,90,90,120,150)
    cropped=Detection('drink can',.85,60,60,90,120)
    class Model:
        def __init__(self):self.calls=0
        def predict(self,**kwargs):
            self.calls+=1
            return [[person,can] if self.calls==1 else [cropped]]
    model=Model()
    result=detect_objects(model,np.zeros((480,640,3),np.uint8),.2,640,lambda x:x)
    assert len([d for d in result if d.label=='drink can'])==1
    assert model.calls==2


def test_marker_detection_to_metric_range_end_to_end():
    dictionary=cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker=cv2.aruco.generateImageMarker(dictionary,0,300)
    r=np.array([np.pi-.2,0.,0.]); t=np.array([.04,.01,.5])
    corners,_=cv2.projectPoints(marker_points(.05),r,t,K,np.zeros(5))
    homography=cv2.getPerspectiveTransform(np.array([[0,0],[299,0],[299,299],[0,299]],np.float32),corners.reshape(4,2).astype(np.float32))
    frame=cv2.warpPerspective(marker,homography,(640,480),borderValue=255)
    calibration=Calibration(dict(camera_matrix=K.tolist(),distortion=[0]*5,image_size=[640,480],rms_px=.1))
    result=RangeEstimator(calibration,.05).measure(frame)
    assert result['status']=='measured_reference'
    assert result['markers'][0]['distance_m']==pytest.approx(np.linalg.norm(t),rel=.025)
    assert channels_for(result['markers'])[1]>0
    assert RangeEstimator(calibration,.05).measure(np.full((480,640),255,np.uint8))['markers']==[]

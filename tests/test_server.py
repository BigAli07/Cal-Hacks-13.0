import io
import sys
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pi'))
from web_server import create_app

class Stub:
    args=SimpleNamespace(model='test',target='drink can')
    ranger=SimpleNamespace(calibration=None,side=.05)
    def detect(self,frame,settings=None):return {'shape':list(frame.shape),'objects':[]}

def test_frame_api_and_live_page():
    client=create_app(Stub()).test_client()
    assert client.get('/').status_code==200
    assert b'CHECKPOINT 02' in client.get('/').data
    assert client.get('/health').json['calibrated'] is False
    assert client.post('/api/detect').status_code==400
    assert client.post('/api/detect',data={'frame':(io.BytesIO(b'bad'),'f.jpg')}).status_code==400
    _,buf=cv2.imencode('.jpg',np.zeros((48,64,3),np.uint8))
    response=client.post('/api/detect',data={'frame':(io.BytesIO(buf.tobytes()),'f.jpg')})
    assert response.json['shape']==[48,64,3]
    assert response.headers['Cache-Control']=='no-store'

def test_invalid_distance_settings_are_rejected():
    client=create_app(Stub()).test_client()
    _,buf=cv2.imencode('.jpg',np.zeros((48,64,3),np.uint8))
    for settings in ['[]','{"horizontal_fov_deg":180}','{"heights_m":{"person":-1}}']:
        response=client.post('/api/detect',data={'frame':(io.BytesIO(buf.tobytes()),'f.jpg'),'distance_settings':settings})
        assert response.status_code==400
    page=client.get('/').data
    assert b'actionCard' not in page and b'GUIDANCE' not in page

def test_reference_then_live_range_updates_through_http(monkeypatch):
    from threading import Lock
    import web_server
    from camera_vision import Detection
    from hardware_plugin import ScenePlugin
    from haptics import SerialBridge
    from geometry import RangeEstimator
    # Deterministic detector isolates real HTTP -> scene -> geometry -> JSON wiring.
    service=web_server.VisionService.__new__(web_server.VisionService)
    service.args=SimpleNamespace(confidence=.2,image_size=640,danger_area=.13,grid_columns=6,grid_rows=4,horizontal_fov_deg=None,target='can')
    service.lock=Lock();service.transport_lock=Lock()
    service.model=SimpleNamespace(names={0:'can'})
    service.obstacle_classes={'can'};service.spoken_names={}
    service.ranger=RangeEstimator();service.bridge=SerialBridge();service.plugin=ScenePlugin()
    box=[300,180,340,300]
    monkeypatch.setattr(web_server,'detect_objects',lambda *args:[Detection('can',.9,*box)])
    client=create_app(service).test_client()
    reference=client.post('/api/distance-reference',json={'width':640,'height':480,'box':box,'height_m':.12,'distance_m':.6})
    assert reference.status_code==200
    import json
    settings={'heights_m':{'can':.12},'full_height_visible':True,'horizontal_fov_deg':reference.json['horizontal_fov_deg']}
    _,buf=cv2.imencode('.jpg',np.zeros((480,640,3),np.uint8))
    def request_range():
        response=client.post('/api/detect',data={'frame':(io.BytesIO(buf.tobytes()),'f.jpg'),'distance_settings':json.dumps(settings)})
        assert response.status_code==200
        return response.json['objects'][0]['distance_m']
    import pytest
    assert request_range()==pytest.approx(.6)
    box[:]=[310,210,330,270]
    assert request_range()==pytest.approx(1.2)
    assert client.post('/api/distance-reference',json={}).status_code==400

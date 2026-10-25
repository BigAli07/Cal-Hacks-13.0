"""Same-frame metric depth inference; learned estimates, not range sensor readings."""
import base64
import math
import time
import cv2
import numpy as np

MODEL_ID = 'depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf'


class MetricDepth:
    def __init__(self, model_id=MODEL_ID):
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        self.torch = torch
        torch.set_num_threads(min(4, torch.get_num_threads()))
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = AutoModelForDepthEstimation.from_pretrained(model_id, use_safetensors=True).eval()
        if self.model.config.depth_estimation_type != 'metric':
            raise ValueError('A metric depth checkpoint is required; relative depth cannot provide metres.')
        self.model_id = model_id

    def predict(self, frame):
        start=time.monotonic()
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        inputs=self.processor(images=rgb,return_tensors='pt',size={'height':392,'width':392})
        with self.torch.inference_mode():
            raw=self.model(**inputs).predicted_depth
            depth=self.torch.nn.functional.interpolate(raw.unsqueeze(1),size=frame.shape[:2],mode='bilinear',align_corners=False)[0,0].cpu().numpy()
        return depth, round((time.monotonic()-start)*1000)


def apply_depth(event, depth, calibration=None, fov=None, latency_ms=0):
    """Sample inset boxes, avoiding boundaries; spread flags mixed surfaces.

    An inset box is not a segmentation mask. A hand/background can still dominate it.
    """
    width,height=event['frame']['width_px'],event['frame']['height_px']
    if depth.shape != (height,width):
        raise ValueError('Depth and detection frames must have identical dimensions.')
    matrix,distortion=None,None
    camera='unknown_intrinsics'
    if calibration:
        try:
            matrix=calibration.matrix(width,height);distortion=calibration.dist
            camera='calibrated_intrinsics'
        except ValueError:
            camera='calibration_resolution_mismatch'
    elif fov is not None and math.isfinite(fov) and 1<fov<179:
        focal=width/(2*math.tan(math.radians(fov)/2))
        matrix=np.array([[focal,0,width/2],[0,focal,height/2],[0,0,1]],float)
        distortion=np.zeros(5);camera='provided_fov'
    for index,obj in enumerate(event['objects']):
        # Discard every previous geometry result; never carry stale or manual range forward.
        obj.update(frame_object_id=index,distance_m=None,optical_depth_m=None,
                   horizontal_angle_deg=None,vertical_angle_deg=None,distance_status='depth_unavailable',
                   distance_method='metric_depth_indoor',distance_kind='optical_depth',
                   distance_reference='median visible surface in central box region',
                   distance_assumptions='Learned indoor estimate. Hands, background, reflections and unfamiliar scenes can bias depth.')
        x1,y1,x2,y2=map(float,obj['box'])
        if x2<=x1 or y2<=y1:continue
        xa=max(0,int(x1+.25*(x2-x1)));xb=min(width,int(x2-.25*(x2-x1)))
        ya=max(0,int(y1+.25*(y2-y1)));yb=min(height,int(y2-.25*(y2-y1)))
        if xb-xa<3 or yb-ya<3:continue
        region=depth[ya:yb,xa:xb]
        values=region[np.isfinite(region)&(region>.05)&(region<19.8)]
        if values.size<9 or values.size<region.size*.5:continue
        low,z,high=np.percentile(values,[20,50,80])
        obj.update(distance_m=float(z),optical_depth_m=float(z),distance_status='estimated_metric_depth',
                   depth_spread_m=float(high-low),depth_quality='mixed_surfaces' if (high-low)/z>.3 else 'consistent_patch',
                   depth_sample_box=[xa,ya,xb,yb],camera_geometry=camera)
        if matrix is not None:
            cx,cy=(xa+xb)/2,(ya+yb)/2
            ray=cv2.undistortPoints(np.array([[[cx,cy]]],float),matrix,distortion).reshape(2)
            x,y=ray*z
            obj.update(distance_m=float(np.linalg.norm([x,y,z])),distance_kind='slant_range',
                       horizontal_angle_deg=math.degrees(math.atan2(x,z)),vertical_angle_deg=math.degrees(math.atan2(y,z)),
                       position_m=[float(x),float(y),float(z)])
    valid=np.isfinite(depth)&(depth>.05)&(depth<19.8)
    visual=np.zeros(depth.shape,np.uint8)
    if valid.any():
        # Fixed 0–10 m scale: near=bright, far=dark, not per-frame normalization.
        visual[valid]=np.uint8(255*(1-np.clip(depth[valid]/10,0,1)))
    heat=cv2.applyColorMap(visual,cv2.COLORMAP_INFERNO);heat[~valid]=0
    heat=cv2.resize(heat,(320,max(1,round(height*320/width))))
    ok,jpg=cv2.imencode('.jpg',heat,[cv2.IMWRITE_JPEG_QUALITY,75])
    event['schema_version']='pulsepath.scene.v1'
    event['checkpoints']['object_distance']={
        'mode':'automatic_metric_depth','estimated':sum(o['distance_m'] is not None for o in event['objects']),
        'total':len(event['objects']),'model':MODEL_ID,'inference_ms':latency_ms,'camera_geometry':camera,
        'note':'Automatic learned estimates, not validated measurements. Unknown intrinsics report optical depth, not angle-corrected range.',
        'preview': 'data:image/jpeg;base64,'+base64.b64encode(jpg).decode() if ok else None}
    return event

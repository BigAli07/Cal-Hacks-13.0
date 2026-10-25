"""Metric range from a measured planar marker; never from a guessed class size."""
import json
import math
from pathlib import Path
import cv2
import numpy as np


def marker_points(side_m):
    if not math.isfinite(side_m) or not 0.005 <= side_m <= 1:
        raise ValueError('Marker side must be 0.005–1 metres.')
    s = side_m / 2
    return np.array([[-s,s,0],[s,s,0],[s,-s,0],[-s,-s,0]], np.float64)


class Calibration:
    def __init__(self, data):
        self.K = np.asarray(data['camera_matrix'], np.float64)
        self.dist = np.asarray(data['distortion'], np.float64)
        self.size = tuple(data['image_size'])
        self.rms = float(data['rms_px'])
        if (self.K.shape != (3,3) or self.dist.size not in (4,5,8,12,14)
            or len(self.size) != 2 or min(self.size) <= 0
            or not np.isfinite(self.K).all() or not np.isfinite(self.dist).all()
            or self.K[0,0] <= 0 or self.K[1,1] <= 0
            or not math.isfinite(self.rms) or not 0 <= self.rms <= 1.5):
            raise ValueError('Invalid calibration or RMS above 1.5 px; recalibrate.')

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text()))

    def matrix(self, width, height):
        # Exact resolution required: resizing/cropping can silently change intrinsics.
        if (width, height) != self.size:
            raise ValueError(f'Calibration expects {self.size[0]}x{self.size[1]}; got {width}x{height}.')
        return self.K


def solve_marker(corners, side_m, K, distortion):
    points = marker_points(side_m)
    corners = np.asarray(corners, np.float64).reshape(4,2)
    if not np.isfinite(corners).all():
        return None
    if min(np.linalg.norm(np.roll(corners,-1,axis=0)-corners,axis=1)) < 12:
        return None
    ok, rvecs, tvecs, _ = cv2.solvePnPGeneric(points, corners, K, distortion,
                                             flags=cv2.SOLVEPNP_IPPE_SQUARE)
    if not ok:
        return None
    candidates = []
    for r, t in zip(rvecs,tvecs):
        t = t.reshape(3)
        if not np.isfinite(t).all() or t[2] <= 0:
            continue
        projected,_ = cv2.projectPoints(points,r,t,K,distortion)
        error = float(np.sqrt(np.mean(np.sum((projected.reshape(4,2)-corners)**2,axis=1))))
        candidates.append((error,r,t))
    if not candidates:
        return None
    error,r,t = min(candidates,key=lambda x:x[0])
    if error > 2.0:
        return None
    rotation,_ = cv2.Rodrigues(r)
    tilt = math.degrees(math.acos(np.clip(abs(rotation[2,2]),0,1)))
    if tilt > 75:
        return None
    return dict(distance_m=float(np.linalg.norm(t)), optical_depth_m=float(t[2]),
                position_m=t.tolist(), horizontal_angle_deg=math.degrees(math.atan2(t[0],t[2])),
                vertical_angle_deg=math.degrees(math.atan2(t[1],t[2])),
                marker_tilt_deg=tilt, reprojection_error_px=error,
                method='calibrated_marker_pnp', reference='marker centre',
                status='measured_reference')


class RangeEstimator:
    def __init__(self, calibration=None, marker_side_m=0.05):
        marker_points(marker_side_m)
        self.calibration = calibration
        self.side = marker_side_m
        self.detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))

    def measure(self, frame):
        if self.calibration is None:
            return {'status':'needs_calibration', 'markers':[]}
        h,w = frame.shape[:2]
        try:
            K = self.calibration.matrix(w,h)
        except ValueError as e:
            return {'status':'resolution_mismatch','message':str(e),'markers':[]}
        corners,ids,_ = self.detector.detectMarkers(frame)
        measurements = []
        for c, marker_id in zip(corners, [] if ids is None else ids.flatten()):
            value = solve_marker(c,self.side,K,self.calibration.dist)
            if value:
                value.update(marker_id=int(marker_id),corners=c.reshape(4,2).tolist())
                measurements.append(value)
        return {'status':'measured_reference' if measurements else 'no_valid_marker',
                'markers':measurements,'calibration_rms_px':self.calibration.rms}

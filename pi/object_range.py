"""Metric estimates from measured height, not category-average dimensions."""
import math
from collections import Counter
import cv2
import numpy as np


def validate_settings(data):
    if not isinstance(data, dict):
        raise ValueError('Distance settings must be an object.')
    heights = data.get('heights_m', {})
    if not isinstance(heights, dict) or len(heights) > 100:
        raise ValueError('heights_m must map labels to measured heights in metres.')
    for label, height in heights.items():
        if not isinstance(label, str) or isinstance(height, bool) or not isinstance(height, (int, float)) or not math.isfinite(height) or not .005 <= height <= 5:
            raise ValueError('Measured heights must be between 0.005 and 5 metres.')
    fov = data.get('horizontal_fov_deg')
    if fov is not None and (isinstance(fov, bool) or not isinstance(fov, (int, float)) or not math.isfinite(fov) or not 1 < fov < 179):
        raise ValueError('Horizontal field of view must be between 1 and 179 degrees.')
    if not isinstance(data.get('full_height_visible', False), bool):
        raise ValueError('full_height_visible must be a boolean.')
    return data


def estimate_objects(event, calibration=None, settings=None):
    settings = validate_settings(settings or {})
    width, height = event['frame']['width_px'], event['frame']['height_px']
    counts = Counter(o['model_label'] for o in event['objects'])
    matrix, distortion, source, camera_error = None, None, None, None
    if calibration:
        try:
            matrix = calibration.matrix(width, height)
            distortion = calibration.dist
            source = 'calibrated_intrinsics'
        except ValueError:
            camera_error = 'calibration_resolution_mismatch'
    elif settings.get('horizontal_fov_deg'):
        focal = width / (2 * math.tan(math.radians(settings['horizontal_fov_deg']) / 2))
        matrix = np.array([[focal, 0, width/2], [0, focal, height/2], [0, 0, 1]], dtype=float)
        distortion = np.zeros(5)
        source = 'provided_fov_square_pixels_no_distortion'
    for i, obj in enumerate(event['objects']):
        obj.update(frame_object_id=i, distance_m=None, distance_status='needs_measured_height')
        known_height = settings.get('heights_m', {}).get(obj['model_label'])
        if known_height is None:
            continue
        reason = None
        x1,y1,x2,y2 = obj['box']
        if counts[obj['model_label']] > 1:
            reason = 'ambiguous_same_label_instances'
        elif not settings.get('full_height_visible'):
            reason = 'confirm_full_height_upright'
        elif camera_error:
            reason = camera_error
        elif matrix is None:
            reason = 'needs_calibration_or_measured_fov'
        elif x1 <= 1 or y1 <= 1 or x2 >= width-1 or y2 >= height-1:
            reason = 'clipped_object'
        elif y2-y1 < 20 or x2 <= x1:
            reason = 'box_too_small'
        if reason:
            obj['distance_status'] = reason
            continue
        cx,cy = (x1+x2)/2, (y1+y2)/2
        points = np.array([[[cx,y1]],[[cx,y2]],[[cx,cy]]], dtype=float)
        rays = cv2.undistortPoints(points, matrix, distortion).reshape(-1,2)
        span = rays[1,1]-rays[0,1]
        if not np.isfinite(rays).all() or span <= 0:
            obj['distance_status'] = 'invalid_geometry'
            continue
        z = known_height/span
        x,y = rays[2]*z
        obj.update(distance_m=float(np.linalg.norm([x,y,z])), distance_status='estimated_known_height',
                   optical_depth_m=float(z), horizontal_angle_deg=math.degrees(math.atan2(x,z)),
                   vertical_angle_deg=math.degrees(math.atan2(y,z)), position_m=[float(x),float(y),float(z)],
                   distance_method=source, measured_height_m=known_height,
                   distance_reference='approximate bounding-box centre',
                   distance_assumptions='Full height visible; upright parallel to image plane; top and bottom at same depth. Unknown pose or hidden edges can invalidate estimate.')
    event['schema_version'] = 'pulsepath.scene.v1'
    event['checkpoints']['object_distance'] = {'estimated':sum(o['distance_m'] is not None for o in event['objects']),
                                             'total':len(event['objects']), 'settings':settings}
    return event


def reference_fov(data):
    """Estimate focal length from one known-height, known-range reference.

    Assumes square pixels, centred principal point and negligible distortion.
    This is an approximate scale reference, not full lens calibration.
    """
    try:
        width, height = float(data['width']), float(data['height'])
        x1,y1,x2,y2 = map(float, data['box'])
        physical, distance = float(data['height_m']), float(data['distance_m'])
        values = [width,height,x1,y1,x2,y2,physical,distance]
        if not all(math.isfinite(v) for v in values):
            raise ValueError()
        if not (width>0 and height>0 and .005<=physical<=5 and 0<distance<=100):
            raise ValueError()
        if not (1<x1<x2<width-1 and 1<y1<y2<height-1 and y2-y1>=20):
            raise ValueError()
        dx,dy=(x1+x2-width)/2,(y1+y2-height)/2
        focal_squared=(distance*(y2-y1)/physical)**2-dx*dx-dy*dy
        if focal_squared<=0:
            raise ValueError()
        fov=math.degrees(2*math.atan(width/(2*math.sqrt(focal_squared))))
        validate_settings({'horizontal_fov_deg':fov})
        return {'horizontal_fov_deg':fov, 'method':'one_point_reference',
                'note':'Approximate scale only; keep camera, resolution, crop and zoom unchanged.'}
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError('Use a fully visible box at least 20 pixels tall, its measured height, and a positive ruler distance. Check units are metres.') from None

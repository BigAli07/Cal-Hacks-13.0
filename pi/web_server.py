"""Serve PulsePath computer vision to a phone browser.

The browser captures frames; this laptop performs inference. Frames are held
only in memory and are not saved by this server.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from threading import Lock
from geometry import Calibration, RangeEstimator
from checkpoints import enrich
from haptics import SerialBridge
from detection import detect_objects
import atexit
import json
from object_range import estimate_objects, validate_settings, reference_fov
from hardware_plugin import ScenePlugin
from metric_depth import MetricDepth, apply_depth

import cv2
import numpy as np
from flask import Flask, jsonify, render_template, request

from camera_vision import (
    DEFAULT_OBSTACLE_CONFIG,
    build_output_event,
    load_obstacle_config,
    score_zones,
    to_detections,
)

os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parent.parent / "models" / "huggingface"))
os.environ.setdefault(
    "YOLO_CONFIG_DIR", str(Path(__file__).resolve().parent / ".ultralytics")
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--confidence", type=float, default=0.35)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--grid-columns", type=int, default=6)
    parser.add_argument("--grid-rows", type=int, default=4)
    parser.add_argument("--danger-area", type=float, default=0.13)
    parser.add_argument("--horizontal-fov-deg", type=float, default=None)
    parser.add_argument("--obstacles", type=Path, default=DEFAULT_OBSTACLE_CONFIG)
    parser.add_argument('--calibration', type=Path)
    parser.add_argument('--marker-side-m', type=float, default=0.05)
    parser.add_argument('--target', default='drink can')
    parser.add_argument('--serial-port', help='auto or explicit device; omitted means preview only')
    parser.add_argument('--distance-mode', choices=['automatic','manual'], default='automatic')
    parser.add_argument('--hardware-plugin', help='Python module:factory implementing publish(scene) and close()')
    return parser.parse_args()


class VisionService:
    def __init__(self, args: argparse.Namespace) -> None:
        from ultralytics import YOLO, YOLOWorld

        if not 1 <= args.grid_columns <= 26 or args.grid_rows < 1:
            raise ValueError("Grid must have 1-26 columns and at least one row.")
        self.args = args
        (
            self.obstacle_classes,
            self.spoken_names,
            _,
            self.open_vocabulary_classes,
        ) = load_obstacle_config(args.obstacles)
        if "world" in Path(args.model).name.lower():
            self.model = YOLOWorld(args.model)
            self.model.set_classes(sorted(self.obstacle_classes))
        else:
            self.model = YOLO(args.model)
        self.depth_model = MetricDepth() if args.distance_mode == 'automatic' else None
        self.lock = Lock()
        self.ranger = RangeEstimator(Calibration.load(args.calibration) if args.calibration else None, args.marker_side_m)
        self.bridge = SerialBridge(args.serial_port)
        atexit.register(self.bridge.close)
        self.plugin = ScenePlugin(args.hardware_plugin)
        atexit.register(self.plugin.close)
        self.transport_lock = Lock()

    def detect(self, frame: np.ndarray, settings=None) -> dict:
        depth, depth_ms = None, 0
        with self.lock:
            if getattr(self, "depth_model", None) is not None:
                depth, depth_ms = self.depth_model.predict(frame)
            detections = [d for d in detect_objects(self.model, frame, self.args.confidence,
                          self.args.image_size, to_detections) if d.label in self.obstacle_classes]
        height, width = frame.shape[:2]
        scores = score_zones(detections, width, height)
        event = build_output_event(
            detections,
            scores,
            width,
            height,
            self.args.danger_area,
            self.spoken_names,
            self.args.grid_columns,
            self.args.grid_rows,
            self.args.horizontal_fov_deg,
        )
        labels = self.model.names.values() if isinstance(self.model.names,dict) else self.model.names
        enrich(event, self.ranger.measure(frame), self.args.target, labels)
        settings = dict(settings or {})
        if settings.get('horizontal_fov_deg') is None:
            settings['horizontal_fov_deg'] = self.args.horizontal_fov_deg
        if depth is not None:
            apply_depth(event, depth, self.ranger.calibration, settings.get('horizontal_fov_deg'), depth_ms)
        else:
            estimate_objects(event, self.ranger.calibration, settings)
        with self.transport_lock:
            self.bridge.send(event['haptics']['channels'])
            event['haptics']['connection'] = self.bridge.status
            event['checkpoints']['hardware'] = self.plugin.publish(event)
        return event


def create_app(service: VisionService) -> Flask:
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "web" / "templates"),
        static_folder=str(project_root / "web" / "static"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

    @app.after_request
    def privacy_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Permissions-Policy"] = "camera=(self)"
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify(status="ready", model=Path(service.args.model).name,
                       target=service.args.target, calibrated=service.ranger.calibration is not None,
                       marker_side_m=service.ranger.side, distance_mode=getattr(service.args, 'distance_mode', 'manual'))

    @app.post('/api/distance-reference')
    def distance_reference():
        try:
            return jsonify(reference_fov(request.get_json(silent=True) or {}))
        except ValueError as error:
            return jsonify(error=str(error)), 400

    @app.post("/api/detect")
    def detect():
        upload = request.files.get("frame")
        if upload is None:
            return jsonify(error="Missing JPEG field named 'frame'."), 400
        raw = upload.read()
        if not raw:
            return jsonify(error='The uploaded frame is empty.'), 400
        frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify(error="The uploaded frame is not a valid image."), 400
        try:
            settings = validate_settings(json.loads(request.form.get('distance_settings', '{}')))
        except (ValueError, TypeError) as error:
            return jsonify(error=str(error)), 400
        return jsonify(service.detect(frame, settings))

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="Frame is larger than 2 MB."), 413

    return app


def main() -> int:
    args = parse_args()
    print(f"Loading {args.model!r} once for browser inference...")
    service = VisionService(args)
    app = create_app(service)
    print(f"PulsePath web server: http://127.0.0.1:{args.port}")
    app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
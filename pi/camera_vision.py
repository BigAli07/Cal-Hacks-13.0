"""Live object detection and coarse obstacle-zone scoring.

This is a hackathon prototype, not a certified mobility aid. It reports visual
observations; it must not replace a cane, guide dog, or normal safety checks.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import yaml
from geometry import Calibration, RangeEstimator
from object_range import estimate_objects, validate_settings
from checkpoints import enrich
from detection import detect_objects
from metric_depth import MetricDepth, apply_depth
os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parent.parent / "models" / "huggingface"))

os.environ.setdefault(
    "YOLO_CONFIG_DIR", str(Path(__file__).resolve().parent / ".ultralytics")
)

import ultralytics
from ultralytics import YOLO, YOLOWorld


ZONE_NAMES = ("left", "forward", "right")
ZONE_COLORS = {
    "left": (255, 180, 30),
    "forward": (60, 220, 60),
    "right": (30, 180, 255),
}
DEFAULT_OBSTACLE_CONFIG = Path(__file__).resolve().parent / "data" / "obstacles.json"
DEFAULT_OUTPUT_FILE = Path(__file__).resolve().parent / "vision_output.jsonl"


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--camera",
        default="0",
        help="Camera index (0, 1, ...) or video-file path. Default: 0",
    )
    parser.add_argument(
        "--model",
        default="yolov8n.pt",
        help="Ultralytics model path/name. It downloads once on first use.",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "dshow", "msmf"),
        default="auto",
        help="Windows camera backend. Leave at auto unless camera opening fails.",
    )
    parser.add_argument("--confidence", type=float, default=0.35)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--grid-columns", type=int, default=6)
    parser.add_argument("--grid-rows", type=int, default=4)
    parser.add_argument(
        "--horizontal-fov-deg",
        type=float,
        default=None,
        help="Camera horizontal field of view from its specification.",
    )
    parser.add_argument(
        "--danger-area",
        type=float,
        default=0.13,
        help="Fraction of frame covered before an object is considered close.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Do not open a preview window; print JSON events only.",
    )
    parser.add_argument(
        "--obstacles",
        type=Path,
        default=DEFAULT_OBSTACLE_CONFIG,
        help="JSON obstacle-class configuration.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Append one machine-readable JSON event per line; use '-' to disable.",
    )
    parser.add_argument('--calibration', type=Path)
    parser.add_argument('--marker-side-m', type=float, default=0.05)
    parser.add_argument('--target', default='drink can')
    parser.add_argument('--distance-mode', choices=['automatic','manual'], default='automatic')
    parser.add_argument('--distance-settings', type=Path, help='JSON measured heights, FOV and visibility assumptions')
    return parser.parse_args()


def load_obstacle_config(
    path: Path,
) -> tuple[set[str], dict[str, str], Path, set[str]]:
    """Load our obstacle list and validate it against Ultralytics' COCO file."""
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    coco_file = (
        Path(ultralytics.__file__).resolve().parent / "cfg" / "datasets" / "coco8.yaml"
    )
    with coco_file.open("r", encoding="utf-8") as handle:
        dataset = yaml.safe_load(handle)

    raw_names = dataset["names"]
    dataset_names = set(raw_names.values() if isinstance(raw_names, dict) else raw_names)
    obstacle_classes = set(config["obstacle_classes"])
    open_vocabulary_classes = set(config.get("open_vocabulary_classes", []))
    unknown = obstacle_classes - dataset_names - open_vocabulary_classes
    if unknown:
        raise ValueError(
            "Obstacle classes are not present in the COCO data file: "
            + ", ".join(sorted(unknown))
        )
    return (
        obstacle_classes,
        dict(config.get("spoken_names", {})),
        coco_file,
        open_vocabulary_classes,
    )


def camera_source(value: str) -> int | str:
    try:
        return int(value)
    except ValueError:
        return value


def open_camera(
    source: int | str, width: int, height: int, backend: str = "auto"
) -> cv2.VideoCapture:
    backend_ids: list[int | None] = [None]
    if isinstance(source, int) and platform.system() == "Windows":
        if backend == "dshow":
            backend_ids = [cv2.CAP_DSHOW]
        elif backend == "msmf":
            backend_ids = [cv2.CAP_MSMF]
        else:
            backend_ids = [cv2.CAP_DSHOW, cv2.CAP_MSMF, None]

    for backend_id in backend_ids:
        capture = (
            cv2.VideoCapture(source)
            if backend_id is None
            else cv2.VideoCapture(source, backend_id)
        )
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if capture.isOpened():
            return capture
        capture.release()

    raise RuntimeError(
        f"Could not open camera {source!r}. Close apps using it, check Windows "
        "camera privacy settings, or try --camera 1."
    )


def to_detections(result) -> list[Detection]:
    detections: list[Detection] = []
    if result.boxes is None:
        return detections

    names = result.names
    for box in result.boxes:
        x1, y1, x2, y2 = (int(value) for value in box.xyxy[0].tolist())
        class_id = int(box.cls[0])
        detections.append(
            Detection(
                label=str(names[class_id]),
                confidence=float(box.conf[0]),
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
            )
        )
    return detections


def zone_for_x(x: float, frame_width: int) -> str:
    third = frame_width / 3
    if x < third:
        return "left"
    if x < third * 2:
        return "forward"
    return "right"


def grid_cell(
    x: float,
    y: float,
    frame_width: int,
    frame_height: int,
    columns: int,
    rows: int,
) -> str:
    column = min(columns - 1, max(0, int(x * columns / frame_width)))
    row = min(rows - 1, max(0, int(y * rows / frame_height)))
    return f"{chr(ord('A') + column)}{row + 1}"


def horizontal_angle_deg(x: float, frame_width: int, horizontal_fov: float | None):
    if horizontal_fov is None:
        return None
    focal_length_px = (frame_width / 2) / math.tan(math.radians(horizontal_fov / 2))
    return round(math.degrees(math.atan((x - frame_width / 2) / focal_length_px)), 2)


def risk_score(item: Detection, frame_width: int, frame_height: int) -> float:
    box_area = max(0, item.x2 - item.x1) * max(0, item.y2 - item.y1)
    area_ratio = box_area / float(frame_width * frame_height)
    bottom_ratio = min(1.0, item.y2 / frame_height)
    return area_ratio * (0.5 + bottom_ratio) * item.confidence


def proximity_label(score: float, danger_area: float) -> str:
    """Describe image occupancy without claiming a measured physical distance."""
    if score >= danger_area:
        return "close"
    if score >= danger_area * 0.4:
        return "nearby"
    return "visible"


def score_zones(
    detections: Iterable[Detection], frame_width: int, frame_height: int
) -> dict[str, float]:
    """Return a coarse visual occupancy score for each third of the image."""
    scores = {zone: 0.0 for zone in ZONE_NAMES}
    for item in detections:
        total_score = risk_score(item, frame_width, frame_height)
        box_width = max(1, item.x2 - item.x1)
        for index, zone in enumerate(ZONE_NAMES):
            zone_x1 = index * frame_width / 3
            zone_x2 = (index + 1) * frame_width / 3
            overlap = max(0.0, min(item.x2, zone_x2) - max(item.x1, zone_x1))
            scores[zone] += total_score * (overlap / box_width)
    return scores


def build_output_event(
    detections: list[Detection],
    scores: dict[str, float],
    frame_width: int,
    frame_height: int,
    danger_area: float,
    spoken_names: dict[str, str],
    grid_columns: int,
    grid_rows: int,
    horizontal_fov: float | None,
) -> dict:
    objects = []
    for item in detections:
        zone = zone_for_x(item.center_x, frame_width)
        score = risk_score(item, frame_width, frame_height)
        center_y = (item.y1 + item.y2) / 2
        box_area = max(0, item.x2 - item.x1) * max(0, item.y2 - item.y1)
        objects.append(
            {
                "name": spoken_names.get(item.label, item.label),
                "model_label": item.label,
                "confidence": round(item.confidence, 3),
                "zone": zone,
                "proximity": proximity_label(score, danger_area),
                "risk_score": round(score, 4),
                "box": [item.x1, item.y1, item.x2, item.y2],
                "center_px": [round(item.center_x), round(center_y)],
                "center_normalized": [
                    round(item.center_x / frame_width, 4),
                    round(center_y / frame_height, 4),
                ],
                "horizontal_angle_deg": horizontal_angle_deg(
                    item.center_x, frame_width, horizontal_fov
                ),
                "grid_cell": grid_cell(
                    item.center_x,
                    center_y,
                    frame_width,
                    frame_height,
                    grid_columns,
                    grid_rows,
                ),
                "apparent_frame_area_percent": round(
                    100 * box_area / (frame_width * frame_height), 2
                ),
                "distance_m": None,
                "distance_status": "requires depth sensor or camera calibration",
            }
        )

    location_words = {"left": "on the left", "forward": "ahead", "right": "on the right"}
    if objects:
        seen_text = ", ".join(
            f"{item['name']} {location_words[item['zone']]}" for item in objects[:4]
        )
        if len(objects) > 4:
            seen_text += f", plus {len(objects) - 4} more"
        scene = f"Seeing {seen_text}."
    else:
        scene = "No configured obstacles detected."

    return {
        "timestamp": round(time.time(), 3),
        "seeing": scene,
        "objects": objects,
        "frame": {
            "width_px": frame_width,
            "height_px": frame_height,
            "grid_columns": grid_columns,
            "grid_rows": grid_rows,
            "horizontal_fov_deg": horizontal_fov,
        },
        "zone_scores": {key: round(value, 4) for key, value in scores.items()},
    }


def emit_output(event: dict, output_file: Path) -> None:
    line = json.dumps(event, separators=(",", ":"))
    print(line, flush=True)
    if str(output_file) != "-":
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def draw_overlay(
    frame,
    detections: Iterable[Detection],
    scores: dict[str, float],
    grid_columns: int,
    grid_rows: int,
) -> None:
    height, width = frame.shape[:2]
    for column in range(1, grid_columns):
        x = round(column * width / grid_columns)
        cv2.line(frame, (x, 44), (x, height), (90, 90, 90), 1)
    for row in range(1, grid_rows):
        y = round(row * height / grid_rows)
        cv2.line(frame, (0, y), (width, y), (90, 90, 90), 1)
    for row in range(grid_rows):
        for column in range(grid_columns):
            label = f"{chr(ord('A') + column)}{row + 1}"
            x = round(column * width / grid_columns) + 5
            y = max(58, round(row * height / grid_rows) + 16)
            cv2.putText(
                frame,
                label,
                (x, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (150, 150, 150),
                1,
                cv2.LINE_AA,
            )

    for item in detections:
        zone = zone_for_x(item.center_x, width)
        center_y = (item.y1 + item.y2) / 2
        cell = grid_cell(
            item.center_x,
            center_y,
            width,
            height,
            grid_columns,
            grid_rows,
        )
        color = ZONE_COLORS[zone]
        cv2.rectangle(frame, (item.x1, item.y1), (item.x2, item.y2), color, 2)
        cv2.putText(
            frame,
            f"{item.label} {item.confidence:.0%} [{cell}]",
            (item.x1, max(22, item.y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    banner_color = (30, 180, 30)
    cv2.rectangle(frame, (0, 0), (width, 44), (20, 20, 20), -1)
    cv2.putText(
        frame,
        "LIVE VISION",
        (12, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        banner_color,
        2,
        cv2.LINE_AA,
    )
    score_text = "  ".join(f"{z}:{scores[z]:.3f}" for z in ZONE_NAMES)
    cv2.putText(
        frame,
        score_text,
        (10, height - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (235, 235, 235),
        1,
        cv2.LINE_AA,
    )


def main() -> int:
    args = parse_args()
    if not 1 <= args.grid_columns <= 26 or args.grid_rows < 1:
        raise ValueError("Grid must have 1-26 columns and at least one row.")
    if args.horizontal_fov_deg is not None and not 1 < args.horizontal_fov_deg < 179:
        raise ValueError("Horizontal FOV must be between 1 and 179 degrees.")
    source = camera_source(args.camera)
    obstacle_classes, spoken_names, coco_file, open_vocabulary_classes = (
        load_obstacle_config(args.obstacles)
    )
    print(
        f"Loaded {len(obstacle_classes)} obstacle classes from {coco_file}",
        file=sys.stderr,
    )
    print(f"Loading {args.model!r}...", file=sys.stderr)
    if "world" in Path(args.model).name.lower():
        model = YOLOWorld(args.model)
        model.set_classes(sorted(obstacle_classes))
        print(
            "Open-vocabulary classes enabled: "
            + ", ".join(sorted(open_vocabulary_classes)),
            file=sys.stderr,
        )
    else:
        model = YOLO(args.model)
        if open_vocabulary_classes:
            print(
                "Warning: the selected closed-set model cannot detect: "
                + ", ".join(sorted(open_vocabulary_classes)),
                file=sys.stderr,
            )
    capture = open_camera(source, args.width, args.height, args.backend)
    print(
        f"Camera ready. JSON events -> stdout and {args.output_file}. "
        "Press Q or Esc in the preview window to quit.",
        file=sys.stderr,
    )

    ranger = RangeEstimator(Calibration.load(args.calibration) if args.calibration else None, args.marker_side_m)
    settings = validate_settings(json.loads(args.distance_settings.read_text())) if args.distance_settings else {}
    depth_model = MetricDepth() if args.distance_mode == 'automatic' else None
    previous_event: tuple | None = None
    last_emit = 0.0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("The camera stopped returning frames.")

            detections = [d for d in detect_objects(model, frame, args.confidence,
                          args.image_size, to_detections) if d.label in obstacle_classes]
            height, width = frame.shape[:2]
            scores = score_zones(detections, width, height)
            output = build_output_event(
                detections,
                scores,
                width,
                height,
                args.danger_area,
                spoken_names,
                args.grid_columns,
                args.grid_rows,
                args.horizontal_fov_deg,
            )

            labels = model.names.values() if isinstance(model.names,dict) else model.names
            enrich(output, ranger.measure(frame), args.target, labels)
            if depth_model:
                depth, elapsed = depth_model.predict(frame)
                apply_depth(output, depth, ranger.calibration, args.horizontal_fov_deg, elapsed)
                output['checkpoints']['object_distance'].pop('preview', None)
            else:
                estimate_objects(output, ranger.calibration, settings)
            now = time.monotonic()
            event = (
                tuple(
                    sorted(
                        (item["model_label"], item["zone"], item["proximity"])
                        for item in output["objects"]
                    )
                ),
            )
            if event != previous_event or now - last_emit >= 0.2:
                emit_output(output, args.output_file)
                previous_event = event
                last_emit = now

            if not args.headless:
                draw_overlay(
                    frame,
                    detections,
                    scores,
                    args.grid_columns,
                    args.grid_rows,
                )
                for obj in output['objects']:
                    if obj['distance_m'] is not None:
                        cv2.putText(frame, f"~{obj['distance_m']:.2f} m {obj.get('distance_kind', 'range')}", (obj['box'][0], obj['box'][3]), cv2.FONT_HERSHEY_SIMPLEX, .6, (255,255,0), 2)
                status = output['checkpoints']['detection']['status']
                ranges = output['checkpoints']['distance']
                distance = f"{output['checkpoints']['object_distance']['estimated']}/{len(output['objects'])} estimated"
                cv2.putText(frame, f"CP1: {status} | CP2: {distance}", (10,70), cv2.FONT_HERSHEY_SIMPLEX, .5, (255,255,255), 1)
                cv2.imshow("PulsePath camera vision", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
    finally:
        capture.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
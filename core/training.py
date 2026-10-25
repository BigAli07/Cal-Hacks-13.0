"""Explicit training and untouched benchmark commands for LastPing."""
from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .detection import FEATURE_SCHEMA, baseline_score, extract_features, physics_search
from .orbit import get_orbit_track
from .simulation import SimulationConfig, simulate

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "lastping_model.joblib"
META_PATH = ARTIFACT_DIR / "model_metadata.json"
BENCHMARK_PATH = ARTIFACT_DIR / "benchmark.json"
GENERATOR_VERSION = "lastping-sim-v1"
SPLITS = {"train": [10_000, 10_499], "validation": [20_000, 20_159], "test": [30_000, 30_199]}


def _dataset(first: int, last: int, track):
    features, labels, base_scores, physics_scores = [], [], [], []
    runtime = {"baseline_s": 0.0, "physics_s": 0.0, "ml_feature_s": 0.0,
               "negative_interference_count": 0}
    for seed in range(first, last + 1):
        rng = np.random.default_rng(seed)
        present = bool(seed % 2)
        db = float(rng.uniform(-6.0, 5.0)) if present else -2.0
        preset = "intermittent_beacon" if present else "noise_only"
        config = SimulationConfig(preset=preset, seed=seed, signal_excess_db=db)
        observed, truth = simulate(config, track.time_s, track.doppler_hz, force_present=present, nuisance=True)
        if not present and truth.interference_present:
            runtime["negative_interference_count"] += 1
        t0 = time.perf_counter(); base = baseline_score(observed); runtime["baseline_s"] += time.perf_counter() - t0
        t0 = time.perf_counter(); physics = physics_search(observed); physics_elapsed = time.perf_counter() - t0
        runtime["physics_s"] += physics_elapsed
        t0 = time.perf_counter(); feature_row = extract_features(observed, physics); extract_elapsed = time.perf_counter() - t0
        runtime["ml_feature_s"] += physics_elapsed + extract_elapsed
        features.append(feature_row)
        labels.append(int(present))
        base_scores.append(base)
        physics_scores.append(physics.score)
    return np.asarray(features), np.asarray(labels), np.asarray(base_scores), np.asarray(physics_scores), runtime


def _far_threshold(scores: np.ndarray, labels: np.ndarray, target_far: float = 0.05) -> float:
    negatives = np.sort(scores[labels == 0])
    # Conservative empirical quantile; the searched-max physics score is calibrated here.
    index = int(np.ceil((1.0 - target_far) * len(negatives))) - 1
    return float(negatives[np.clip(index, 0, len(negatives) - 1)])


def train() -> dict:
    track = get_orbit_track()
    X_train, y_train, _, _, _ = _dataset(*SPLITS["train"], track)
    X_val, y_val, baseline_val, physics_val, _ = _dataset(*SPLITS["validation"], track)
    pipeline = Pipeline([("scaler", StandardScaler()), ("classifier", LogisticRegression(max_iter=1000, random_state=42))])
    pipeline.fit(X_train, y_train)
    ml_val = pipeline.predict_proba(X_val)[:, 1]
    thresholds = {
        "target_validation_false_alarm_rate": 0.05,
        "baseline": _far_threshold(baseline_val, y_val),
        "physics": _far_threshold(physics_val, y_val),
        "ml": _far_threshold(ml_val, y_val),
    }
    ARTIFACT_DIR.mkdir(exist_ok=True)
    joblib.dump({"pipeline": pipeline, "feature_schema": FEATURE_SCHEMA,
                 "generator_version": GENERATOR_VERSION}, MODEL_PATH)
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model_path": MODEL_PATH.name,
        "feature_schema": FEATURE_SCHEMA,
        "generator": {"version": GENERATOR_VERSION, "shape": [128, 192], "duration_s": 240.0,
                      "signal_excess_db_train_range": [-6.0, 5.0]},
        "splits": SPLITS,
        "counts": {"training": len(y_train), "validation": len(y_val)},
        "thresholds": thresholds,
        "versions": {"python": platform.python_version(), "scikit_learn": sklearn.__version__},
    }
    META_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def load_model():
    if not MODEL_PATH.exists() or not META_PATH.exists():
        return None, None
    try:
        metadata = json.loads(META_PATH.read_text(encoding="utf-8"))
        artifact = joblib.load(MODEL_PATH)
    except Exception:  # A corrupt/incompatible local artifact is an unavailable model.
        return None, None
    if (artifact.get("generator_version") != GENERATOR_VERSION
            or artifact.get("feature_schema") != FEATURE_SCHEMA
            or metadata.get("generator", {}).get("version") != GENERATOR_VERSION
            or metadata.get("feature_schema") != FEATURE_SCHEMA
            or "pipeline" not in artifact):
        return None, None
    return artifact["pipeline"], metadata


def saved_benchmark() -> dict:
    """Return saved historical measurements without running evaluation."""
    if not BENCHMARK_PATH.exists():
        return {"status": "unavailable", "measurement_status": "missing",
                "setup_instruction": "Run: python -m core.training benchmark"}
    try:
        result = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "unavailable", "measurement_status": "invalid",
                "setup_instruction": "Run: python -m core.training benchmark"}
    result["measurement_status"] = "historical_saved_artifact"
    result["artifact_path"] = str(BENCHMARK_PATH.relative_to(ROOT))
    return result


def _metrics(decisions: np.ndarray, labels: np.ndarray) -> dict:
    positives, negatives = labels == 1, labels == 0
    tp = int(np.sum(decisions & positives)); fp = int(np.sum(decisions & negatives))
    return {
        "recall": tp / int(np.sum(positives)), "recall_numerator": tp, "recall_denominator": int(np.sum(positives)),
        "false_alarm_rate": fp / int(np.sum(negatives)), "false_alarm_numerator": fp,
        "false_alarm_denominator": int(np.sum(negatives)),
    }


def benchmark() -> dict:
    model, metadata = load_model()
    if model is None:
        return {"status": "unavailable", "setup_instruction": "Run: python -m core.training train"}
    track = get_orbit_track()
    X, labels, baseline_scores, physics_scores, measured = _dataset(*SPLITS["test"], track)
    timings = {}
    baseline_decisions = baseline_scores >= metadata["thresholds"]["baseline"]; timings["baseline_total_s"] = measured["baseline_s"]
    physics_decisions = physics_scores >= metadata["thresholds"]["physics"]; timings["physics_total_s"] = measured["physics_s"]
    t0 = time.perf_counter(); ml_scores = model.predict_proba(X)[:, 1]; ml_decisions = ml_scores >= metadata["thresholds"]["ml"]; timings["ml_model_only_total_s"] = time.perf_counter() - t0
    timings["ml_including_features_total_s"] = measured["ml_feature_s"] + timings["ml_model_only_total_s"]
    n = len(labels)
    result = {
        "status": "ok", "created_utc": datetime.now(timezone.utc).isoformat(),
        "recording_duration_s": 240.0, "test_recordings": n,
        "signal_count": int(np.sum(labels)), "negative_count": int(np.sum(labels == 0)),
        "negative_interference_count": int(measured["negative_interference_count"]),
        "split_seed_ranges": SPLITS,
        "signal_excess_db_test_distribution": "uniform [-6, 5] dB for positive examples",
        "validation_target_false_alarm_rate": metadata["thresholds"]["target_validation_false_alarm_rate"],
        "thresholds_fixed_from_validation": metadata["thresholds"],
        "methods": {
            "baseline": {**_metrics(baseline_decisions, labels), "inference_runtime_total_s": timings["baseline_total_s"]},
            "physics": {**_metrics(physics_decisions, labels), "inference_runtime_total_s": timings["physics_total_s"]},
            "ml": {**_metrics(ml_decisions, labels), "inference_runtime_total_s": timings["ml_including_features_total_s"],
                   "model_only_runtime_total_s": timings["ml_model_only_total_s"]},
        },
        "runtime_note": "CPU wall time; recording duration is simulated and is not included as waiting time.",
        "orbit_provenance": track.provenance,
    }
    ARTIFACT_DIR.mkdir(exist_ok=True)
    BENCHMARK_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["train", "benchmark"])
    args = parser.parse_args()
    result = train() if args.action == "train" else benchmark()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()


"""Stable LastPing analysis and benchmark interface."""
from __future__ import annotations

import time
from dataclasses import asdict
import numpy as np

from .detection import FEATURE_SCHEMA, baseline_score, extract_features, physics_search
from .orbit import get_orbit_track
from .simulation import SimulationConfig, simulate
from .training import benchmark as _benchmark, load_model, saved_benchmark as _saved_benchmark
from .real_data import analyze_real


def _json_array(value):
    array = np.asarray(value)
    if np.issubdtype(array.dtype, np.floating):
        serializable = array.astype(object)
        serializable[~np.isfinite(array)] = None
        return serializable.tolist()
    return array.tolist()


def analyze(config) -> dict:
    """Run all available methods without exposing simulation truth to detectors."""
    observer = None
    if isinstance(config, dict):
        values = dict(config)
        observer = values.pop("observer", None)
        config = SimulationConfig(**values)
    if observer is not None:
        required = {"latitude_deg", "longitude_deg", "elevation_m"}
        if set(observer) != required:
            raise ValueError(f"observer must contain exactly: {sorted(required)}")
        if not -90 <= float(observer["latitude_deg"]) <= 90:
            raise ValueError("observer latitude_deg must be between -90 and 90")
        if not -180 <= float(observer["longitude_deg"]) <= 180:
            raise ValueError("observer longitude_deg must be between -180 and 180")
    orbit = get_orbit_track(n_times=config.n_time, duration_s=config.duration_s, observer=observer)
    observed, truth = simulate(config, orbit.time_s, orbit.doppler_hz)
    t0 = time.perf_counter(); baseline = baseline_score(observed); baseline_runtime = time.perf_counter() - t0
    t0 = time.perf_counter(); physics = physics_search(observed); physics_runtime = time.perf_counter() - t0
    model, metadata = load_model()
    if metadata:
        baseline_threshold = metadata["thresholds"]["baseline"]
        physics_threshold = metadata["thresholds"]["physics"]
    else:
        baseline_threshold = physics_threshold = None
    if model is None:
        ml_result = {"status": "unavailable", "score": None, "decision": None,
                     "setup_instruction": "Run: python -m core.training train"}
    else:
        ml_started = time.perf_counter()
        features = extract_features(observed, physics)
        t0 = time.perf_counter(); ml_score = float(model.predict_proba(features.reshape(1, -1))[0, 1]); model_runtime = time.perf_counter() - t0
        ml_runtime = time.perf_counter() - ml_started
        ml_result = {"status": "ok", "score": ml_score, "score_label": "synthetic-model score",
                     "decision": bool(ml_score >= metadata["thresholds"]["ml"]),
                     "threshold": metadata["thresholds"]["ml"], "runtime_s": ml_runtime,
                     "model_only_runtime_s": model_runtime,
                     "features": dict(zip(FEATURE_SCHEMA, features.tolist()))}
    actual = truth.actual_track_hz
    return {
        "status": "ok", "configuration": {**asdict(config), "observer": orbit.provenance["observer"]},
        "provenance": {"orbit": orbit.provenance,
                       "radio": {"kind": "simulated_power_spectrogram", "raw_iq": False,
                                 "signal_excess_db_definition": "10 log10(injected peak excess power / mean background power)"}},
        "recording_start_utc": orbit.recording_start_utc,
        "axes": {"time_s": _json_array(observed.time_s), "frequency_hz": _json_array(observed.frequency_hz)},
        "observed_power": _json_array(observed.power),
        "tracks": {"predicted_hz": _json_array(observed.predicted_doppler_hz),
                   "detected_hz": _json_array(physics.best_track_hz),
                   "ground_truth_hz": None if actual is None else _json_array(actual)},
        "orbit_geometry": {"range_rate_km_s": _json_array(orbit.range_rate_km_s),
                           "elevation_deg": _json_array(orbit.elevation_deg)},
        "methods": {
            "baseline": {"status": "ok", "score": baseline, "threshold": baseline_threshold,
                         "decision": None if baseline_threshold is None else bool(baseline >= baseline_threshold), "runtime_s": baseline_runtime},
            "physics": {"status": "ok", "score": physics.score, "threshold": physics_threshold,
                        "decision": None if physics_threshold is None else bool(physics.score >= physics_threshold),
                        "runtime_s": physics_runtime, "supported_fraction": physics.supported_fraction,
                        "persistence": physics.persistence, "best_frequency_offset_hz": physics.frequency_offset_hz,
                        "best_timing_offset_s": physics.timing_offset_s},
            "ml": ml_result,
        },
        "ground_truth": {"signal_present": truth.signal_present, "preset": truth.preset,
                         "signal_excess_db": truth.signal_excess_db,
                         "injected_frequency_offset_hz": truth.injected_frequency_offset_hz,
                         "injected_timing_offset_s": truth.injected_timing_offset_s,
                         "dropout_fraction": float(np.mean(truth.dropout_mask)),
                         "interference_present": truth.interference_present},
    }


def benchmark() -> dict:
    return _benchmark()


def saved_benchmark() -> dict:
    """Read the committed benchmark without rerunning or refreshing timings."""
    return _saved_benchmark()


def replay_real(recording=None, manifest=None) -> dict:
    """Run a validated archived real recording through the shared backend."""
    return analyze_real(recording=recording, manifest_source=manifest) if manifest is not None else analyze_real(recording=recording)


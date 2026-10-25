"""LastPing analysis engine.

This module is the backend handoff surface. The UI calls only ``analyze`` and
``benchmark``. Detector implementations must not receive hidden generation
parameters beyond the documented configuration keys.
"""

from __future__ import annotations

import time

import numpy as np

from .recordings import analyze_recording

PRESETS = (
    "strong_beacon",
    "faint_intermittent",
    "interference_only",
    "noise_only",
)

CONFIG_KEYS = (
    "observer_lat_deg",
    "observer_lon_deg",
    "preset",
    "signal_excess_db",
    "interference",
    "seed",
)

_N_TIME = 96
_N_FREQ = 192
_DURATION_S = 60.0
_FREQ_SPAN_HZ = 4000.0


def _validate_config(config: dict) -> dict:
    missing = [key for key in CONFIG_KEYS if key not in config]
    if missing:
        raise ValueError(f"Missing configuration keys: {', '.join(missing)}")

    preset = str(config["preset"])
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset '{preset}'. Expected one of: {', '.join(PRESETS)}")

    try:
        lat = float(config["observer_lat_deg"])
        lon = float(config["observer_lon_deg"])
        excess = float(config["signal_excess_db"])
        seed = int(config["seed"])
        interference = bool(config["interference"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Configuration values have invalid types.") from exc

    if not -90.0 <= lat <= 90.0:
        raise ValueError("observer_lat_deg must be between -90 and 90.")
    if not -180.0 <= lon <= 180.0:
        raise ValueError("observer_lon_deg must be between -180 and 180.")

    return {
        "observer_lat_deg": lat,
        "observer_lon_deg": lon,
        "preset": preset,
        "signal_excess_db": excess,
        "interference": interference,
        "seed": seed,
    }


def _placeholder_spectrum(cfg: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Deterministic placeholder waterfall so the interface can render.

    Not a scientific simulation. Codex should replace this generation path.
    """
    rng = np.random.default_rng(cfg["seed"])
    times_s = np.linspace(0.0, _DURATION_S, _N_TIME)
    freqs_hz = np.linspace(-_FREQ_SPAN_HZ, _FREQ_SPAN_HZ, _N_FREQ)
    power_db = rng.normal(-32.0, 3.2, size=(_N_TIME, _N_FREQ))

    # Mild structured noise so the heatmap is readable; not a detector output.
    freq_mesh = np.broadcast_to(freqs_hz, (_N_TIME, _N_FREQ))
    band = -0.015 * (freq_mesh / 100.0) ** 2
    power_db = power_db + band

    if cfg["interference"]:
        tone_idx = int((_N_FREQ * 0.72) % _N_FREQ)
        power_db[:, tone_idx : tone_idx + 3] += 6.5

    signal_present = cfg["preset"] in {"strong_beacon", "faint_intermittent"}
    gt_times = times_s.tolist() if signal_present else []
    gt_freqs: list[float] = []
    if signal_present:
        drift = 180.0 * np.sin(2.0 * np.pi * times_s / _DURATION_S)
        center = 250.0 if cfg["preset"] == "strong_beacon" else -120.0
        gt_freqs = (center + drift).tolist()
        # Paint a faint ridge for visual continuity; detectors remain pending.
        excess = max(cfg["signal_excess_db"], 0.0)
        visibility = 0.45 if cfg["preset"] == "faint_intermittent" else 1.0
        for i, (t, f0) in enumerate(zip(times_s, gt_freqs)):
            if cfg["preset"] == "faint_intermittent" and int(t) % 7 in {2, 3, 4}:
                continue
            j = int(np.clip(np.searchsorted(freqs_hz, f0), 1, _N_FREQ - 2))
            power_db[i, j - 1 : j + 2] += excess * visibility

    ground_truth = {
        "signal_present": bool(signal_present),
        "times_s": gt_times,
        "frequency_offsets_hz": gt_freqs,
    }
    return times_s, freqs_hz, power_db, ground_truth


def analyze(config: dict) -> dict:
    """Generate a JSON-compatible analysis payload.

    Placeholder mode returns deterministic arrays and pending detector results.
    Future modes: ``real_orbit_synthetic_radio``, ``synthetic_orbit_synthetic_radio``.
    """
    started = time.perf_counter()
    cfg = _validate_config(config)
    times_s, freqs_hz, power_db, ground_truth = _placeholder_spectrum(cfg)

    # Predicted track is empty until orbital geometry is implemented.
    prediction = {"times_s": [], "frequency_offsets_hz": []}

    runtime_ms = int((time.perf_counter() - started) * 1000)
    return {
        "mode": "placeholder",
        "provenance": {
            "radio": "simulated",
            "orbit": "unavailable",
            "orbit_detail": "Public orbital data is not loaded. Backend pending.",
            "cache": None,
            "model": "missing",
            "note": "Placeholder — backend pending",
        },
        "satellite": {
            "name": "Catalog object pending",
            "catalog_id": None,
            "orbit_epoch": None,
            "source": "placeholder",
        },
        "observation": {
            "time_utc": None,
            "observer_lat_deg": cfg["observer_lat_deg"],
            "observer_lon_deg": cfg["observer_lon_deg"],
            "preset": cfg["preset"],
            "seed": cfg["seed"],
        },
        "spectrum": {
            "times_s": times_s.tolist(),
            "frequency_offsets_hz": freqs_hz.tolist(),
            "power_db": np.asarray(power_db, dtype=float).tolist(),
        },
        "prediction": prediction,
        "detected_track": None,
        "results": {
            "threshold": {"status": "pending", "score": None},
            "physics": {"status": "pending", "score": None},
            "ml": {"status": "pending", "score": None},
        },
        "evidence": [],
        "runtime_ms": runtime_ms,
        "ground_truth": ground_truth,
    }


def benchmark() -> dict:
    """Return method comparison metadata.

    Placeholder: no measured performance. Do not train on UI reruns.
    """
    return {"status": "pending", "methods": [], "metadata": {}}

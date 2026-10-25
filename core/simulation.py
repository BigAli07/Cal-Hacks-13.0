"""Reproducible synthetic power-spectrogram generation."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class SimulationConfig:
    preset: str = "faint_intermittent"
    seed: int = 7
    signal_excess_db: float = -4.0
    interference: bool | None = None
    n_time: int = 128
    n_freq: int = 192
    duration_s: float = 240.0
    span_hz: float = 24_000.0


@dataclass(frozen=True)
class ObservedRecording:
    power: np.ndarray
    time_s: np.ndarray
    frequency_hz: np.ndarray
    predicted_doppler_hz: np.ndarray
    search_bounds: dict


@dataclass(frozen=True)
class GroundTruth:
    signal_present: bool
    actual_track_hz: np.ndarray | None
    dropout_mask: np.ndarray
    injected_frequency_offset_hz: float | None
    injected_timing_offset_s: float | None
    preset: str
    signal_excess_db: float | None
    interference_present: bool


PRESETS = {
    "strong_beacon": {"signal": True, "dropout": 0.08, "interference": False},
    "faint_intermittent": {"signal": True, "dropout": 0.58, "interference": False},
    "interference_only": {"signal": False, "dropout": 1.0, "interference": True},
    "noise_only": {"signal": False, "dropout": 1.0, "interference": False},
}

PRESET_ALIASES = {
    "weak_beacon": "faint_intermittent",
    "intermittent_beacon": "faint_intermittent",
    "beacon_with_interference": "strong_beacon",
}

PRESET_DEFAULT_STRENGTH_DB = {
    "strong_beacon": 5.0,
    "faint_intermittent": -4.0,
    "interference_only": -4.0,
    "noise_only": -4.0,
}


def _shift_track(time_s: np.ndarray, track: np.ndarray, timing_s: float) -> np.ndarray:
    return np.interp(time_s + timing_s, time_s, track, left=np.nan, right=np.nan)


def simulate(config: SimulationConfig, time_s: np.ndarray, predicted_doppler_hz: np.ndarray,
             force_present: bool | None = None, nuisance: bool = True) -> tuple[ObservedRecording, GroundTruth]:
    """Create observed data separately from reveal-only truth.

    ``signal_excess_db`` is injected peak excess power divided by mean background
    power, expressed as 10*log10(ratio); it is not measured receiver sensitivity.
    """
    preset = PRESET_ALIASES.get(config.preset, config.preset)
    if preset not in PRESETS:
        raise ValueError(f"unknown preset: {config.preset}")
    rng = np.random.default_rng(config.seed)
    spec = PRESETS[preset]
    present = spec["signal"] if force_present is None else force_present
    freq = np.linspace(-config.span_hz / 2, config.span_hz / 2, config.n_freq)
    background_scale = rng.uniform(0.86, 1.16, config.n_time)[:, None]
    power = rng.exponential(background_scale, (config.n_time, config.n_freq))
    offset_hz = float(rng.uniform(-650, 650)) if present else None
    timing_s = float(rng.uniform(-4, 4)) if present else None
    actual_track = None
    dropout = np.ones(config.n_time, dtype=bool)
    if present:
        actual_track = _shift_track(time_s, predicted_doppler_hz, timing_s) + offset_hz
        dropout_rate = spec["dropout"] if force_present is None else rng.uniform(0.12, 0.62)
        dropout = rng.random(config.n_time) < dropout_rate
        # Create clustered outages in addition to independent missing pulses.
        if nuisance and rng.random() < 0.55:
            start = int(rng.integers(8, config.n_time - 20))
            dropout[start:start + int(rng.integers(5, 18))] = True
        amplitude = 10.0 ** (config.signal_excess_db / 10.0)
        width_hz = rng.uniform(105.0, 190.0)
        for i, center in enumerate(actual_track):
            if not dropout[i] and np.isfinite(center):
                power[i] += amplitude * np.exp(-0.5 * ((freq - center) / width_hz) ** 2)

    add_interference = (spec["interference"] or (nuisance and rng.random() < 0.32)
                        if config.interference is None else config.interference)
    if add_interference:
        stationary_hz = rng.uniform(-8_500, 8_500)
        amp = rng.uniform(2.0, 7.0)
        width = rng.uniform(90, 260)
        on = rng.random(config.n_time) > rng.uniform(0.0, 0.3)
        power += on[:, None] * amp * np.exp(-0.5 * ((freq - stationary_hz) / width) ** 2)
    # Unrelated drifting interferer appears in both positive and negative examples.
    if nuisance and rng.random() < 0.36:
        start_hz = rng.uniform(-9_000, 9_000)
        slope = rng.uniform(-22, 22)
        unrelated = start_hz + slope * (time_s - time_s.mean())
        for i, center in enumerate(unrelated):
            power[i] += rng.uniform(0.8, 3.5) * np.exp(-0.5 * ((freq - center) / 180.0) ** 2)

    observed = ObservedRecording(
        power=power.astype(np.float32), time_s=np.asarray(time_s), frequency_hz=freq,
        predicted_doppler_hz=np.asarray(predicted_doppler_hz),
        search_bounds={"frequency_offset_hz": [-900.0, 900.0], "timing_offset_s": [-6.0, 6.0]},
    )
    truth = GroundTruth(present, actual_track, dropout, offset_hz, timing_s,
                        preset, config.signal_excess_db if present else None,
                        bool(add_interference))
    return observed, truth


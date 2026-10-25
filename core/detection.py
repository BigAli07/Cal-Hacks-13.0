"""Observation-only baseline, physics search, and ML feature extraction."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

FEATURE_SCHEMA = [
    "baseline_peak", "track_accumulation", "track_background_contrast",
    "supported_fraction", "persistence", "stationary_contrast",
]


@dataclass(frozen=True)
class PhysicsResult:
    score: float
    best_track_hz: np.ndarray
    frequency_offset_hz: float
    timing_offset_s: float
    supported_fraction: float
    persistence: float
    track_background_contrast: float
    stationary_contrast: float


def _normalized(power: np.ndarray) -> np.ndarray:
    median = np.median(power, axis=1, keepdims=True)
    mad = np.median(np.abs(power - median), axis=1, keepdims=True)
    return (power - median) / np.maximum(1.4826 * mad, 1e-5)


def baseline_score(observed) -> float:
    z = _normalized(observed.power)
    # Peak of a frequency-bin time average: simple signal-strength threshold.
    return float(np.max(np.mean(z, axis=0)))


def _candidate_track(observed, timing_s: float, frequency_hz: float) -> np.ndarray:
    return np.interp(observed.time_s + timing_s, observed.time_s,
                     observed.predicted_doppler_hz, left=np.nan, right=np.nan) + frequency_hz


def _sample_track(z: np.ndarray, freq: np.ndarray, track: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    idx = np.searchsorted(freq, track)
    valid = np.isfinite(track) & (idx >= 1) & (idx < len(freq) - 1)
    values = np.full(len(track), np.nan)
    rows = np.flatnonzero(valid)
    # Narrow three-bin neighborhood tolerates finite beacon width/grid mismatch.
    values[rows] = np.max(np.stack([z[rows, idx[rows] - 1], z[rows, idx[rows]], z[rows, idx[rows] + 1]]), axis=0)
    return values, valid


def physics_search(observed) -> PhysicsResult:
    z = _normalized(observed.power)
    f_lo, f_hi = observed.search_bounds["frequency_offset_hz"]
    t_lo, t_hi = observed.search_bounds["timing_offset_s"]
    frequency_offsets = np.linspace(f_lo, f_hi, 13)
    timing_offsets = np.linspace(t_lo, t_hi, 5)
    best = None
    for timing in timing_offsets:
        for offset in frequency_offsets:
            track = _candidate_track(observed, float(timing), float(offset))
            samples, valid = _sample_track(z, observed.frequency_hz, track)
            if not np.any(valid):
                continue
            finite = samples[valid]
            support = float(np.mean(valid))
            score = float(np.mean(np.clip(finite, -3, 12)) * np.sqrt(support))
            if best is None or score > best[0]:
                best = (score, track, float(offset), float(timing), support, finite)
    if best is None:
        return PhysicsResult(float("-inf"), np.full(len(observed.time_s), np.nan), 0, 0, 0, 0, 0, 0)
    score, track, offset, timing, support, finite = best
    persistence = float(np.mean(finite > 2.5))
    contrast = float(np.mean(finite) - np.median(z))
    stationary_strength = float(np.max(np.mean(z, axis=0)))
    stationary_contrast = float(score - stationary_strength)
    return PhysicsResult(score, track, offset, timing, support, persistence, contrast, stationary_contrast)


def extract_features(observed, physics: PhysicsResult | None = None) -> np.ndarray:
    physics = physics or physics_search(observed)
    return np.array([
        baseline_score(observed), physics.score, physics.track_background_contrast,
        physics.supported_fraction, physics.persistence, physics.stationary_contrast,
    ], dtype=float)


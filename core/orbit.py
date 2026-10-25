"""Orbit provenance and Doppler prediction for LastPing.

The sign convention is ``delta_f = -f0 * range_rate / c``: positive range
rate means the spacecraft is receding, and therefore produces negative
Doppler offset.
"""
from __future__ import annotations

import json
import time
from functools import lru_cache
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests
from skyfield.api import EarthSatellite, load, wgs84

C_M_S = 299_792_458.0
BEACON_HZ = 437_000_000.0
CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=CUBESAT&FORMAT=TLE"
DEFAULT_OBSERVER = {"latitude_deg": 37.8715, "longitude_deg": -122.2730, "elevation_m": 52.0}
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CACHE_TLE = DATA_DIR / "celestrak_cubesat.tle"
CACHE_META = DATA_DIR / "celestrak_cubesat_metadata.json"


@dataclass(frozen=True)
class OrbitTrack:
    time_s: np.ndarray
    doppler_hz: np.ndarray
    range_rate_km_s: np.ndarray
    elevation_deg: np.ndarray
    recording_start_utc: str
    provenance: dict


def doppler_offset_hz(range_rate_km_s: np.ndarray | float, carrier_hz: float = BEACON_HZ):
    """Return received-minus-nominal frequency in Hz for km/s range rate."""
    return -carrier_hz * np.asarray(range_rate_km_s) * 1000.0 / C_M_S


def _parse_tles(text: str) -> list[tuple[str, str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = []
    for i in range(len(lines) - 2):
        if lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
            result.append((lines[i], lines[i + 1], lines[i + 2]))
    return result


def fetch_celestrak_cache(timeout_s: float = 8.0, retries: int = 2) -> dict:
    """Fetch and cache the exact public CelesTrak CubeSat TLE response."""
    error = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(CELESTRAK_URL, timeout=timeout_s)
            response.raise_for_status()
            if not _parse_tles(response.text):
                raise ValueError("response contained no valid 3-line TLE records")
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            CACHE_TLE.write_text(response.text, encoding="utf-8")
            metadata = {
                "source_url": CELESTRAK_URL,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "response_file": CACHE_TLE.name,
            }
            CACHE_META.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            cached = globals().get("_default_track")
            if cached is not None:
                cached.cache_clear()
            observer_cached = globals().get("_observer_track")
            if observer_cached is not None:
                observer_cached.cache_clear()
            return metadata
        except (requests.RequestException, ValueError) as exc:
            error = exc
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"CelesTrak fetch failed after {retries + 1} attempts: {error}")


def _real_track(n_times: int, duration_s: float, observer_cfg: dict) -> OrbitTrack:
    text = CACHE_TLE.read_text(encoding="utf-8")
    cache_meta = json.loads(CACHE_META.read_text(encoding="utf-8"))
    candidates = _parse_tles(text)
    if not candidates:
        raise ValueError("cached CelesTrak response has no TLE records")
    ts = load.timescale(builtin=True)
    observer = wgs84.latlon(observer_cfg["latitude_deg"], observer_cfg["longitude_deg"],
                             elevation_m=observer_cfg["elevation_m"])
    retrieved = datetime.fromisoformat(cache_meta["retrieved_utc"].replace("Z", "+00:00"))
    start = retrieved - timedelta(hours=2)
    end = retrieved + timedelta(days=2)
    chosen = None
    culmination = None
    max_elevation = None
    for name, line1, line2 in candidates[:160]:
        satellite = EarthSatellite(line1, line2, name, ts)
        times, events = satellite.find_events(observer, ts.from_datetime(start), ts.from_datetime(end), altitude_degrees=10.0)
        for event_time, event in zip(times, events):
            if int(event) == 1:
                alt, _, _ = (satellite - observer).at(event_time).altaz()
                chosen, culmination, max_elevation = satellite, event_time.utc_datetime(), float(alt.degrees)
                break
        if chosen is not None:
            break
    if chosen is None or culmination is None:
        raise RuntimeError("no cached CubeSat pass above 10 degrees in the search window")

    recording_start = culmination - timedelta(seconds=duration_s / 2)
    seconds = np.linspace(0.0, duration_s, n_times)
    dts = [recording_start + timedelta(seconds=float(s)) for s in seconds]
    topocentric = (chosen - observer).at(ts.from_datetimes(dts))
    position = topocentric.position.km
    velocity = topocentric.velocity.km_per_s
    range_rate = np.sum(position * velocity, axis=0) / np.linalg.norm(position, axis=0)
    elevation, _, _ = topocentric.altaz()
    epoch = chosen.epoch.utc_datetime().isoformat()
    age_days = abs((recording_start - chosen.epoch.utc_datetime()).total_seconds()) / 86400.0
    selected_cache = dict(cache_meta)
    selected_cache.update({"selected_satellite_name": chosen.name,
                           "selected_catalog_id": str(chosen.model.satnum),
                           "selected_orbital_epoch_utc": epoch,
                           "selected_recording_start_utc": recording_start.isoformat()})
    if selected_cache != cache_meta:
        CACHE_META.write_text(json.dumps(selected_cache, indent=2), encoding="utf-8")
    provenance = {
        "kind": "real_public_orbital_elements",
        "provider": "CelesTrak",
        "source_url": cache_meta["source_url"],
        "retrieved_utc": cache_meta["retrieved_utc"],
        "satellite_name": chosen.name,
        "catalog_id": str(chosen.model.satnum),
        "orbital_epoch_utc": epoch,
        "recording_start_utc": recording_start.isoformat(),
        "tle_age_at_recording_days": age_days,
        "stale_warning": age_days > 14.0,
        "observer": observer_cfg,
        "maximum_segment_elevation_deg": max_elevation,
        "carrier_assumption_hz": BEACON_HZ,
    }
    return OrbitTrack(seconds, doppler_offset_hz(range_rate), range_rate, elevation.degrees,
                      recording_start.isoformat(), provenance)


def _synthetic_track(n_times: int, duration_s: float, observer_cfg: dict) -> OrbitTrack:
    seconds = np.linspace(0.0, duration_s, n_times)
    # An explicit, plausible LEO pass surrogate. It is not attributed to a real object.
    centered = (seconds - duration_s / 2) / (duration_s / 2)
    range_rate = 6.2 * np.tanh(1.5 * centered)
    elevation = 12.0 + 50.0 * np.cos(np.pi * centered / 2.0) ** 2
    start = datetime.now(timezone.utc).replace(microsecond=0)
    provenance = {
        "kind": "synthetic_orbit_fallback",
        "provider": None,
        "source_url": None,
        "retrieved_utc": None,
        "satellite_name": "Synthetic LEO pass (not a real satellite)",
        "catalog_id": None,
        "orbital_epoch_utc": None,
        "recording_start_utc": start.isoformat(),
        "tle_age_at_recording_days": None,
        "stale_warning": False,
        "observer": observer_cfg,
        "maximum_segment_elevation_deg": float(np.max(elevation)),
        "carrier_assumption_hz": BEACON_HZ,
    }
    return OrbitTrack(seconds, doppler_offset_hz(range_rate), range_rate, elevation,
                      start.isoformat(), provenance)


@lru_cache(maxsize=8)
def _default_track(n_times: int, duration_s: float) -> OrbitTrack:
    observer_cfg = dict(DEFAULT_OBSERVER)
    if CACHE_TLE.exists() and CACHE_META.exists():
        try:
            return _real_track(n_times, duration_s, observer_cfg)
        except (ValueError, RuntimeError, KeyError, OSError):
            pass
    return _synthetic_track(n_times, duration_s, observer_cfg)


@lru_cache(maxsize=16)
def _observer_track(n_times: int, duration_s: float, latitude_deg: float,
                    longitude_deg: float, elevation_m: float) -> OrbitTrack:
    observer_cfg = {"latitude_deg": latitude_deg, "longitude_deg": longitude_deg,
                    "elevation_m": elevation_m}
    if CACHE_TLE.exists() and CACHE_META.exists():
        try:
            return _real_track(n_times, duration_s, observer_cfg)
        except (ValueError, RuntimeError, KeyError, OSError):
            pass
    return _synthetic_track(n_times, duration_s, observer_cfg)


def get_orbit_track(n_times: int = 128, duration_s: float = 240.0,
                    observer: dict | None = None, allow_fetch: bool = False) -> OrbitTrack:
    """Return a real cached pass, otherwise a clearly labelled synthetic fallback."""
    observer_cfg = dict(DEFAULT_OBSERVER if observer is None else observer)
    if allow_fetch and (not CACHE_TLE.exists() or not CACHE_META.exists()):
        try:
            fetch_celestrak_cache()
        except RuntimeError:
            pass
    if observer is None:
        return _default_track(n_times, duration_s)
    return _observer_track(n_times, duration_s,
                           float(observer_cfg["latitude_deg"]),
                           float(observer_cfg["longitude_deg"]),
                           float(observer_cfg["elevation_m"]))


def provenance_json(track: OrbitTrack) -> dict:
    result = asdict(track)
    for key in ("time_s", "doppler_hz", "range_rate_km_s", "elevation_deg"):
        result.pop(key)
    return result


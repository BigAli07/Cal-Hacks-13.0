"""Real-recording loaders.

Synthetic generation stays in ``core.engine.analyze``. This module is the
stable file-backed interface documented in BACKEND_CONTRACT.md.
"""

from __future__ import annotations

import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy import signal

ALLOWED_FORMATS = ("wav_pcm", "iq_f32le", "iq_f32be", "npy_complex")
REQUIRED_METADATA = (
    "path",
    "format",
    "sample_rate_hz",
    "center_frequency_hz",
    "observer_lat_deg",
    "observer_lon_deg",
)

DEFAULT_MAX_DURATION_S = 120.0
MIN_SAMPLES = 32


@dataclass
class Recording:
    samples: np.ndarray  # complex128 baseband
    sample_rate_hz: float
    center_frequency_hz: float
    observer_lat_deg: float
    observer_lon_deg: float
    path: str
    format: str
    start_time_utc: str | None
    catalog_id: str | None
    satellite_name: str | None
    n_fft: int
    hop_length: int


def _require_metadata(metadata: dict) -> dict:
    if not isinstance(metadata, dict):
        raise ValueError("Recording metadata must be a dict.")
    missing = [key for key in REQUIRED_METADATA if key not in metadata]
    if missing:
        raise ValueError(f"Missing recording metadata keys: {', '.join(missing)}")

    fmt = str(metadata["format"])
    if fmt not in ALLOWED_FORMATS:
        raise ValueError(f"Unknown format '{fmt}'. Expected one of: {', '.join(ALLOWED_FORMATS)}")

    try:
        sample_rate_hz = float(metadata["sample_rate_hz"])
        center_frequency_hz = float(metadata["center_frequency_hz"])
        lat = float(metadata["observer_lat_deg"])
        lon = float(metadata["observer_lon_deg"])
        n_fft = int(metadata.get("n_fft", 256))
    except (TypeError, ValueError) as exc:
        raise ValueError("Recording metadata values have invalid types.") from exc

    hop = metadata.get("hop_length")
    hop_length = int(hop) if hop is not None else max(n_fft // 2, 1)
    max_duration = metadata.get("max_duration_s", DEFAULT_MAX_DURATION_S)
    max_duration_s = None if max_duration is None else float(max_duration)

    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive.")
    if n_fft < 16:
        raise ValueError("n_fft must be at least 16.")
    if hop_length < 1 or hop_length > n_fft:
        raise ValueError("hop_length must be in [1, n_fft].")
    if not -90.0 <= lat <= 90.0:
        raise ValueError("observer_lat_deg must be between -90 and 90.")
    if not -180.0 <= lon <= 180.0:
        raise ValueError("observer_lon_deg must be between -180 and 180.")

    iq_order = str(metadata.get("iq_order", "iq"))
    if iq_order not in {"iq", "qi"}:
        raise ValueError("iq_order must be 'iq' or 'qi'.")

    channel = int(metadata.get("channel", 0))
    start_time_utc = metadata.get("start_time_utc")
    if start_time_utc is not None:
        start_time_utc = str(start_time_utc)

    return {
        "path": str(metadata["path"]),
        "format": fmt,
        "sample_rate_hz": sample_rate_hz,
        "center_frequency_hz": center_frequency_hz,
        "observer_lat_deg": lat,
        "observer_lon_deg": lon,
        "start_time_utc": start_time_utc,
        "channel": channel,
        "iq_order": iq_order,
        "max_duration_s": max_duration_s,
        "n_fft": n_fft,
        "hop_length": hop_length,
        "catalog_id": None if metadata.get("catalog_id") is None else str(metadata["catalog_id"]),
        "satellite_name": None if metadata.get("satellite_name") is None else str(metadata["satellite_name"]),
    }


def _truncate(samples: np.ndarray, sample_rate_hz: float, max_duration_s: float | None) -> np.ndarray:
    if max_duration_s is None:
        return samples
    n_max = int(max_duration_s * sample_rate_hz)
    if n_max < MIN_SAMPLES:
        raise ValueError("max_duration_s is too short for analysis.")
    return samples[:n_max]


def _as_complex(i_samples: np.ndarray, q_samples: np.ndarray, iq_order: str) -> np.ndarray:
    if iq_order == "qi":
        i_samples, q_samples = q_samples, i_samples
    return np.asarray(i_samples, dtype=np.float64) + 1j * np.asarray(q_samples, dtype=np.float64)


def _real_to_analytic(real_samples: np.ndarray) -> np.ndarray:
    real_samples = np.asarray(real_samples, dtype=np.float64)
    return signal.hilbert(real_samples)


def _load_wav(meta: dict) -> np.ndarray:
    path = meta["path"]
    try:
        with wave.open(path, "rb") as wav:
            n_channels = wav.getnchannels()
            n_frames = wav.getnframes()
            sampwidth = wav.getsampwidth()
            raw = wav.readframes(n_frames)
            file_rate = wav.getframerate()
    except wave.Error as exc:
        raise ValueError(f"Unable to read WAV file: {path}") from exc

    if abs(file_rate - meta["sample_rate_hz"]) > 1.0:
        raise ValueError(
            f"WAV sample rate {file_rate} Hz does not match metadata sample_rate_hz "
            f"{meta['sample_rate_hz']} Hz."
        )
    if sampwidth not in {1, 2, 3, 4}:
        raise ValueError("Unsupported WAV sample width.")

    if sampwidth == 1:
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0
        data /= 128.0
    elif sampwidth == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif sampwidth == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        packed = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        triplet = packed.astype(np.int32)
        signed = triplet[:, 0] | (triplet[:, 1] << 8) | (triplet[:, 2] << 16)
        signed = np.where(signed >= 2**23, signed - 2**24, signed)
        data = signed.astype(np.float64) / 8388608.0

    if n_channels > 1:
        data = data.reshape(-1, n_channels)
        if n_channels >= 2:
            return _as_complex(data[:, 0], data[:, 1], meta["iq_order"])
        channel = meta["channel"]
        if channel < 0 or channel >= n_channels:
            raise ValueError("WAV channel index is out of range.")
        return _real_to_analytic(data[:, channel])
    return _real_to_analytic(data)


def _load_iq_f32(meta: dict) -> np.ndarray:
    endian = "<" if meta["format"] == "iq_f32le" else ">"
    raw = np.fromfile(meta["path"], dtype=np.dtype(f"{endian}f4"))
    if raw.size < 2:
        raise ValueError("IQ file is empty or truncated.")
    if raw.size % 2:
        raw = raw[:-1]
    i_samples = raw[0::2]
    q_samples = raw[1::2]
    return _as_complex(i_samples, q_samples, meta["iq_order"])


def _load_npy(meta: dict) -> np.ndarray:
    try:
        array = np.load(meta["path"])
    except (OSError, ValueError) as exc:
        raise ValueError(f"Unable to read npy recording: {meta['path']}") from exc
    array = np.asarray(array)
    if array.ndim != 1:
        raise ValueError("npy_complex recordings must be a 1-D array.")
    if np.iscomplexobj(array):
        return array.astype(np.complex128, copy=False)
    if array.ndim == 1:
        return _real_to_analytic(array)
    raise ValueError("npy recording must be complex or real 1-D samples.")


def load_recording(metadata: dict) -> Recording:
    """Load a local capture into complex baseband samples."""
    meta = _require_metadata(metadata)
    path = Path(meta["path"])
    if not path.is_file():
        raise FileNotFoundError(f"Recording not found: {path}")

    if meta["format"] == "wav_pcm":
        samples = _load_wav(meta)
    elif meta["format"] in {"iq_f32le", "iq_f32be"}:
        samples = _load_iq_f32(meta)
    else:
        samples = _load_npy(meta)

    samples = np.asarray(samples, dtype=np.complex128).reshape(-1)
    samples = _truncate(samples, meta["sample_rate_hz"], meta["max_duration_s"])
    if samples.size < MIN_SAMPLES:
        raise ValueError("Recording is too short for a waterfall.")

    return Recording(
        samples=samples,
        sample_rate_hz=meta["sample_rate_hz"],
        center_frequency_hz=meta["center_frequency_hz"],
        observer_lat_deg=meta["observer_lat_deg"],
        observer_lon_deg=meta["observer_lon_deg"],
        path=str(path),
        format=meta["format"],
        start_time_utc=meta["start_time_utc"],
        catalog_id=meta["catalog_id"],
        satellite_name=meta["satellite_name"],
        n_fft=meta["n_fft"],
        hop_length=meta["hop_length"],
    )


def spectrum_from_recording(
    recording: Recording,
    *,
    n_fft: int | None = None,
    hop_length: int | None = None,
) -> dict[str, Any]:
    """STFT waterfall: times in s, frequency offsets in Hz, relative power in dB."""
    n_fft = int(n_fft or recording.n_fft)
    hop_length = int(hop_length or recording.hop_length)
    noverlap = n_fft - hop_length
    if recording.samples.size < n_fft:
        raise ValueError("Recording is shorter than n_fft.")
    freqs, times, zxx = signal.stft(
        recording.samples,
        fs=recording.sample_rate_hz,
        window="hann",
        nperseg=n_fft,
        noverlap=noverlap,
        nfft=n_fft,
        return_onesided=False,
        boundary=None,
        padded=False,
    )
    if times.size == 0 or zxx.size == 0:
        raise ValueError("STFT produced an empty waterfall.")
    freqs = np.fft.fftshift(np.real(freqs))
    zxx = np.fft.fftshift(zxx, axes=0)
    mag = np.abs(zxx)
    power_db = 20.0 * np.log10(np.maximum(mag, 1e-12))
    power_db = power_db - float(np.median(power_db))
    # STFT returns [frequency, time]; contract is [time][frequency].
    power_db = np.transpose(power_db).astype(float)
    return {
        "times_s": np.asarray(times, dtype=float).tolist(),
        "frequency_offsets_hz": np.asarray(freqs, dtype=float).tolist(),
        "power_db": power_db.tolist(),
    }


def analyze_recording(metadata: dict) -> dict:
    """JSON payload with the same top-level keys as ``engine.analyze``."""
    started = time.perf_counter()
    recording = load_recording(metadata)
    spectrum = spectrum_from_recording(recording)
    runtime_ms = int((time.perf_counter() - started) * 1000)
    return {
        "mode": "synthetic_orbit_real_radio",
        "provenance": {
            "radio": "real",
            "orbit": "unavailable",
            "orbit_detail": "No public orbital data attached.",
            "cache": None,
            "model": "missing",
            "note": "Real samples loaded; detectors not verified on this file.",
            "path": recording.path,
            "format": recording.format,
            "center_frequency_hz": recording.center_frequency_hz,
            "sample_rate_hz": recording.sample_rate_hz,
        },
        "satellite": {
            "name": recording.satellite_name,
            "catalog_id": recording.catalog_id,
            "orbit_epoch": None,
            "source": None,
        },
        "observation": {
            "time_utc": recording.start_time_utc,
            "observer_lat_deg": recording.observer_lat_deg,
            "observer_lon_deg": recording.observer_lon_deg,
        },
        "spectrum": spectrum,
        "prediction": {"times_s": [], "frequency_offsets_hz": []},
        "detected_track": None,
        "results": {
            "threshold": {"status": "pending", "score": None},
            "physics": {"status": "pending", "score": None},
            "ml": {"status": "unavailable", "score": None},
        },
        "evidence": [],
        "runtime_ms": runtime_ms,
        "ground_truth": {
            "signal_present": False,
            "times_s": [],
            "frequency_offsets_hz": [],
        },
    }

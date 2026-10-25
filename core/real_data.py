"""Validated SatNOGS archived-recording replay for LastPing.

The supported real format is mono OGG/WAV audio produced by the SatNOGS 2.3
BPSK flowgraph. It is target-Doppler-corrected, shifted to a 12 kHz audio IF,
and stored as a real, lossy audio channel. It is not raw RF I/Q.
"""
from __future__ import annotations

import hashlib
import io
import json
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import get_window
from skyfield.api import EarthSatellite, load, wgs84

from .detection import FEATURE_SCHEMA
from .orbit import doppler_offset_hz
from .training import load_model

ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ROOT / "data" / "real"
BUNDLED_MANIFEST = REAL_DIR / "satnogs_6659851_manifest.json"


class RecordingValidationError(ValueError):
    """Raised when real observation data is incomplete or inconsistent."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _required(mapping: dict, path: str, keys: set[str]) -> None:
    missing = sorted(keys - set(mapping))
    if missing:
        raise RecordingValidationError(f"{path} is missing required fields: {', '.join(missing)}")


def load_manifest(source: str | Path | dict | bytes) -> tuple[dict, Path | None]:
    if isinstance(source, dict):
        manifest, base = dict(source), None
    elif isinstance(source, bytes):
        try:
            manifest, base = json.loads(source), None
        except json.JSONDecodeError as exc:
            raise RecordingValidationError(f"metadata JSON is invalid: {exc}") from exc
    else:
        path = Path(source)
        try:
            manifest, base = json.loads(path.read_text(encoding="utf-8")), path.parent
        except (OSError, json.JSONDecodeError) as exc:
            raise RecordingValidationError(f"could not read metadata manifest: {exc}") from exc
    _required(manifest, "manifest", {"schema", "observation_id", "observation_url", "recording_url",
              "recording_file", "recording_sha256", "acquisition_start_utc", "receiver",
              "recording_format", "transmitter", "scheduled_target", "candidate_catalog",
              "license", "attribution"})
    if manifest["schema"] != "lastping-real-recording-v1":
        raise RecordingValidationError("unsupported manifest schema; expected lastping-real-recording-v1")
    _required(manifest["receiver"], "receiver", {"latitude_deg", "longitude_deg", "elevation_m"})
    _required(manifest["recording_format"], "recording_format",
              {"decoded_sample_rate_hz", "channels", "audio_if_hz", "doppler_correction_applied"})
    _required(manifest["transmitter"], "transmitter", {"frequency_hz", "mode"})
    if not manifest["recording_format"]["doppler_correction_applied"]:
        raise RecordingValidationError("this importer requires documented target-Doppler-corrected BPSK audio")
    if not manifest["candidate_catalog"]:
        raise RecordingValidationError("candidate_catalog must contain at least one historical TLE")
    for i, candidate in enumerate(manifest["candidate_catalog"]):
        _required(candidate, f"candidate_catalog[{i}]", {"name", "catalog_id", "tle1", "tle2", "tle_source_url"})
    try:
        datetime.fromisoformat(manifest["acquisition_start_utc"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecordingValidationError("acquisition_start_utc must be ISO-8601 with timezone") from exc
    return manifest, base


def _recording_bytes(source: str | Path | bytes | None, manifest: dict, base: Path | None) -> tuple[bytes, str]:
    if source is None:
        if base is None:
            raise RecordingValidationError("recording bytes are required when metadata is uploaded")
        path = base / manifest["recording_file"]
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise RecordingValidationError(f"recording file is unavailable: {exc}") from exc
        label = str(path.relative_to(ROOT))
    elif isinstance(source, bytes):
        data, label = source, "uploaded recording"
    else:
        path = Path(source)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise RecordingValidationError(f"recording file is unavailable: {exc}") from exc
        label = str(path)
    digest = _sha256_bytes(data)
    if digest.lower() != str(manifest["recording_sha256"]).lower():
        raise RecordingValidationError(f"recording SHA-256 mismatch: expected {manifest['recording_sha256']}, got {digest}")
    return data, label


def _validate_original_metadata(manifest: dict, base: Path | None) -> str | None:
    """Cross-check the untouched SatNOGS API response when it is bundled."""
    metadata_file = manifest.get("metadata_file")
    expected_hash = manifest.get("metadata_sha256")
    if not metadata_file or base is None:
        return None
    if not expected_hash:
        raise RecordingValidationError("metadata_file requires metadata_sha256 and a file beside the manifest")
    path = base / metadata_file
    try:
        raw = path.read_bytes()
        original = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise RecordingValidationError(f"original observation metadata is unavailable or invalid: {exc}") from exc
    digest = _sha256_bytes(raw)
    if digest.lower() != str(expected_hash).lower():
        raise RecordingValidationError(f"observation metadata SHA-256 mismatch: expected {expected_hash}, got {digest}")
    checks = {
        "id": manifest["observation_id"],
        "start": manifest["acquisition_start_utc"],
        "station_lat": manifest["receiver"]["latitude_deg"],
        "station_lng": manifest["receiver"]["longitude_deg"],
        "station_alt": manifest["receiver"]["elevation_m"],
        "observation_frequency": manifest["transmitter"]["frequency_hz"],
        "tle1": manifest["scheduled_target"]["tle1"],
        "tle2": manifest["scheduled_target"]["tle2"],
    }
    mismatched = [key for key, expected in checks.items() if original.get(key) != expected]
    if mismatched:
        raise RecordingValidationError(f"manifest disagrees with original observation metadata: {', '.join(mismatched)}")
    return digest


def _spectrogram(data: bytes, manifest: dict, time_bin_s: float = 0.5,
                 nfft: int = 2048) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    started = time.perf_counter()
    stream = io.BytesIO(data)
    try:
        audio = sf.SoundFile(stream)
    except sf.SoundFileError as exc:
        raise RecordingValidationError(f"unsupported or corrupt OGG/WAV recording: {exc}") from exc
    expected_rate = int(manifest["recording_format"]["decoded_sample_rate_hz"])
    expected_channels = int(manifest["recording_format"]["channels"])
    if audio.samplerate != expected_rate:
        raise RecordingValidationError(f"sample rate mismatch: metadata {expected_rate} Hz, file {audio.samplerate} Hz")
    if audio.channels != expected_channels or audio.channels != 1:
        raise RecordingValidationError(f"expected one real audio channel, found {audio.channels}")
    if audio.frames < nfft:
        raise RecordingValidationError("recording is too short for the configured FFT")
    duration_s = audio.frames / audio.samplerate
    documented_duration = manifest.get("decoded_audio_duration_s")
    if documented_duration is not None and abs(duration_s - float(documented_duration)) > 0.02:
        raise RecordingValidationError("decoded duration does not match the manifest")

    samples_per_bin = int(round(time_bin_s * audio.samplerate))
    hop = nfft // 2
    window = get_window("hann", nfft, fftbins=True).astype(np.float32)
    window_energy = float(np.sum(window * window))
    rows, centers = [], []
    consumed = 0
    for block in audio.blocks(blocksize=samples_per_bin, dtype="float32", always_2d=False):
        block = np.asarray(block).reshape(-1)
        if len(block) < nfft:
            break
        frames = np.lib.stride_tricks.sliding_window_view(block, nfft)[::hop]
        fft = np.fft.rfft(frames * window, n=nfft, axis=1)
        psd = (np.abs(fft) ** 2) / (audio.samplerate * window_energy)
        if psd.shape[1] > 2:
            psd[:, 1:-1] *= 2.0
        rows.append(np.mean(psd, axis=0, dtype=np.float64))
        centers.append((consumed + len(block) / 2.0) / audio.samplerate)
        consumed += len(block)
    power = np.asarray(rows, dtype=np.float32)
    frequencies = np.fft.rfftfreq(nfft, 1.0 / audio.samplerate)
    info = {
        "decoded_sample_rate_hz": audio.samplerate,
        "decoded_channels": audio.channels,
        "decoded_frames": audio.frames,
        "decoded_duration_s": duration_s,
        "time_bin_s": time_bin_s,
        "fft_size": nfft,
        "fft_window": "Hann",
        "fft_overlap_fraction_within_bin": 0.5,
        "frequency_resolution_hz": audio.samplerate / nfft,
        "power_units": "relative normalized decoder amplitude squared per Hz; not calibrated RF power",
        "native_time_bins": len(rows),
        "native_frequency_bins": len(frequencies),
        "processing_runtime_s": time.perf_counter() - started,
    }
    return power, np.asarray(centers), frequencies, info


def _candidate_tracks(manifest: dict, time_s: np.ndarray) -> list[dict]:
    ts = load.timescale(builtin=True)
    start = datetime.fromisoformat(manifest["acquisition_start_utc"].replace("Z", "+00:00"))
    times = ts.from_datetimes([start + timedelta(seconds=float(value)) for value in time_s])
    receiver = manifest["receiver"]
    observer = wgs84.latlon(receiver["latitude_deg"], receiver["longitude_deg"],
                            elevation_m=receiver["elevation_m"])
    carrier = float(manifest["transmitter"]["frequency_hz"])
    target_cfg = manifest["scheduled_target"]
    target_sat = EarthSatellite(target_cfg["tle1"], target_cfg["tle2"], target_cfg["name"], ts)

    def geometry(satellite):
        topocentric = (satellite - observer).at(times)
        position = topocentric.position.km
        velocity = topocentric.velocity.km_per_s
        rate = np.sum(position * velocity, axis=0) / np.linalg.norm(position, axis=0)
        elevation, _, _ = topocentric.altaz()
        return doppler_offset_hz(rate, carrier), np.asarray(elevation.degrees)

    target_doppler, _ = geometry(target_sat)
    audio_if = float(manifest["recording_format"]["audio_if_hz"])
    result = []
    for candidate in manifest["candidate_catalog"]:
        satellite = EarthSatellite(candidate["tle1"], candidate["tle2"], candidate["name"], ts)
        doppler, elevation = geometry(satellite)
        # The receiver followed the scheduled target. Other candidates therefore
        # appear at the difference between their Doppler and the applied correction.
        audio_track = audio_if + doppler - target_doppler
        result.append({**candidate, "predicted_audio_hz": audio_track,
                       "rf_doppler_hz": doppler, "elevation_deg": elevation,
                       "tle_epoch_utc": satellite.epoch.utc_datetime().isoformat()})
    return result


def _normalize(power: np.ndarray) -> np.ndarray:
    log_power = 10.0 * np.log10(np.maximum(power, np.finfo(np.float32).tiny))
    median = np.median(log_power, axis=1, keepdims=True)
    mad = np.median(np.abs(log_power - median), axis=1, keepdims=True)
    return (log_power - median) / np.maximum(1.4826 * mad, 1e-4)


def _observed_ridge(z: np.ndarray, frequency_hz: np.ndarray, audio_if_hz: float) -> tuple[np.ndarray, np.ndarray]:
    # Fixed format-derived search region, independent of every candidate track.
    band = (frequency_hz >= audio_if_hz - 3500.0) & (frequency_hz <= audio_if_hz + 3500.0)
    band_freq = frequency_hz[band]
    weights = np.clip(z[:, band] - 1.5, 0.0, None)
    total = np.sum(weights, axis=1)
    ridge = np.full(z.shape[0], np.nan)
    supported = total > 8.0
    ridge[supported] = np.sum(weights[supported] * band_freq, axis=1) / total[supported]
    return ridge, supported


def _score_candidate(z: np.ndarray, time_s: np.ndarray, frequency_hz: np.ndarray,
                     candidate: dict, ridge: np.ndarray, ridge_supported: np.ndarray) -> dict:
    raw_track = np.asarray(candidate["predicted_audio_hz"])
    elevation = np.asarray(candidate["elevation_deg"])
    best = None
    half_band_hz = 850.0
    for timing_s in np.linspace(-2.0, 2.0, 5):
        shifted = np.interp(time_s + timing_s, time_s, raw_track, left=np.nan, right=np.nan)
        shifted_elevation = np.interp(time_s + timing_s, time_s, elevation, left=-90.0, right=-90.0)
        for offset_hz in np.linspace(-1500.0, 1500.0, 61):
            track = shifted + offset_hz
            valid = (np.isfinite(track) & (track - half_band_hz >= frequency_hz[0])
                     & (track + half_band_hz <= frequency_hz[-1]))
            row_evidence = np.full(len(time_s), np.nan)
            for row in np.flatnonzero(valid):
                mask = np.abs(frequency_hz - track[row]) <= half_band_hz
                row_evidence[row] = float(np.mean(z[row, mask]))
            finite = np.isfinite(row_evidence)
            support = float(np.mean(finite))
            score = float(np.mean(row_evidence[finite]) * np.sqrt(support)) if np.any(finite) else float("-inf")
            if best is None or score > best[0]:
                best = (score, track, offset_hz, timing_s, row_evidence, support, shifted_elevation)
    score, fitted, offset, timing, evidence, support, shifted_elevation = best
    visible = shifted_elevation > 0.0
    visibility_support = float(np.mean(visible))
    persistent = np.isfinite(evidence) & (evidence > 0.8)
    persistence = float(np.mean(persistent))
    compare = ridge_supported & np.isfinite(fitted) & visible
    residual = ridge[compare] - fitted[compare]
    return {
        "name": candidate["name"], "catalog_id": str(candidate["catalog_id"]),
        "tle_epoch_utc": candidate["tle_epoch_utc"], "tle_source_url": candidate["tle_source_url"],
        "score": score, "best_frequency_offset_hz": float(offset), "best_timing_offset_s": float(timing),
        "in_band_support": support, "above_horizon_support": visibility_support,
        "persistence": persistence,
        "ridge_residual_rms_hz": float(np.sqrt(np.mean(residual ** 2))) if len(residual) else None,
        "ridge_residual_median_hz": float(np.median(residual)) if len(residual) else None,
        "predicted_track_hz": raw_track, "fitted_template_hz": fitted,
        "elevation_deg": elevation, "row_evidence": evidence,
    }


def _serializable(value):
    if isinstance(value, np.ndarray):
        obj = value.astype(object)
        if np.issubdtype(value.dtype, np.floating):
            obj[~np.isfinite(value)] = None
        return obj.tolist()
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serializable(item) for item in value]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def analyze_real(recording: str | Path | bytes | None = None,
                 manifest_source: str | Path | dict | bytes = BUNDLED_MANIFEST) -> dict:
    """Run the real archived-recording replay end to end."""
    total_started = time.perf_counter()
    manifest, base = load_manifest(manifest_source)
    metadata_digest = _validate_original_metadata(manifest, base)
    raw, recording_label = _recording_bytes(recording, manifest, base)
    power, time_s, frequency_hz, processing = _spectrogram(raw, manifest)
    orbit_started = time.perf_counter()
    predicted = _candidate_tracks(manifest, time_s)
    orbit_runtime = time.perf_counter() - orbit_started
    z = _normalize(power)
    ridge, ridge_supported = _observed_ridge(z, frequency_hz,
                                             float(manifest["recording_format"]["audio_if_hz"]))
    scoring_started = time.perf_counter()
    candidates = [_score_candidate(z, time_s, frequency_hz, item, ridge, ridge_supported)
                  for item in predicted]
    candidates.sort(key=lambda item: (item["above_horizon_support"] > 0.0, item["score"]), reverse=True)
    scoring_runtime = time.perf_counter() - scoring_started

    baseline = float(np.max(np.mean(z, axis=0)))
    model, model_metadata = load_model()
    model_runtime = 0.0
    for candidate in candidates:
        features = np.array([
            baseline, candidate["score"], candidate["score"], candidate["in_band_support"],
            candidate["persistence"], candidate["score"] - baseline,
        ])
        if model is None:
            candidate["ml"] = {"status": "unavailable", "score": None,
                               "setup_instruction": "Run: python -m core.training train"}
        else:
            started = time.perf_counter()
            score = float(model.predict_proba(features.reshape(1, -1))[0, 1])
            model_runtime += time.perf_counter() - started
            candidate["ml"] = {"status": "experimental_uncalibrated", "score": score,
                               "score_label": "synthetic-model score",
                               "decision": None, "feature_schema": FEATURE_SCHEMA,
                               "training_domain": "synthetic only"}
        candidate["features"] = dict(zip(FEATURE_SCHEMA, features.tolist()))

    best = candidates[0]
    runner_up = candidates[1] if len(candidates) > 1 else None
    margin = best["score"] - runner_up["score"] if runner_up else None
    ridge_support = float(np.mean(ridge_supported))
    if best["above_horizon_support"] < 0.25 or ridge_support < 0.1:
        conclusion = "insufficient_evidence"
    elif margin is not None and margin < 0.35:
        conclusion = "ambiguous"
    else:
        conclusion = "candidate_match"
    scheduled_id = str(manifest["scheduled_target"]["catalog_id"])
    evaluation = {
        "scheduled_target_catalog_id": scheduled_id,
        "best_candidate_matches_schedule": best["catalog_id"] == scheduled_id,
        "independent_decoded_frame_count": manifest.get("positive_support", {}).get("decoded_frame_count"),
        "note": "The scheduled label and decoded-frame evidence are used only after ranking, not as detector features.",
    }
    result = {
        "status": "ok", "mode": "archived_real_recording",
        "conclusion": conclusion, "conclusion_label": conclusion.replace("_", " ").title(),
        "recording": {
            "label": "Archived real recording", "local_source": recording_label,
            "sha256": manifest["recording_sha256"], "observation_id": manifest["observation_id"],
            "metadata_sha256": metadata_digest or manifest.get("metadata_sha256"),
            "observation_url": manifest["observation_url"], "recording_url": manifest["recording_url"],
            "acquisition_start_utc": manifest["acquisition_start_utc"],
            "license": manifest["license"], "attribution": manifest["attribution"],
            "receiver": manifest["receiver"], "transmitter": manifest["transmitter"],
            "format": manifest["recording_format"], "known_limitations": manifest.get("known_limitations", []),
        },
        "signal_processing": processing,
        "axes": {"time_s": time_s, "audio_frequency_hz": frequency_hz},
        "observed_power": power,
        "observed_ridge_hz": ridge,
        "observed_ridge_support_fraction": ridge_support,
        "candidates": candidates,
        "best_candidate": {"name": best["name"], "catalog_id": best["catalog_id"],
                           "score": best["score"], "score_margin": margin},
        "methods": {
            "baseline": {"status": "measured_uncalibrated", "score": baseline, "decision": None},
            "physics": {"status": "measured_candidate_ranking", "score": best["score"],
                        "decision": conclusion, "best_candidate": best["name"]},
            "ml": best["ml"],
        },
        "calibration": {
            "real_thresholds_available": False,
            "synthetic_model_loaded": model is not None,
            "model_created_utc": None if model_metadata is None else model_metadata.get("created_utc"),
            "warning": "Synthetic thresholds and probabilities are not transferred to real RF decisions.",
        },
        "evaluation": evaluation,
        "timings": {"spectrogram_s": processing["processing_runtime_s"],
                    "orbit_prediction_s": orbit_runtime, "candidate_scoring_s": scoring_runtime,
                    "ml_model_only_s": model_runtime,
                    "total_processing_s": time.perf_counter() - total_started},
    }
    return _serializable(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a validated real SatNOGS recording")
    parser.add_argument("--manifest", default=str(BUNDLED_MANIFEST))
    parser.add_argument("--recording", default=None,
                        help="Recording path; omitted uses recording_file beside the manifest")
    parser.add_argument("--output", default=str(ROOT / "artifacts" / "real_replay.json"))
    args = parser.parse_args()
    result = analyze_real(args.recording, args.manifest)
    # Preserve all evidence tracks and metrics but avoid duplicating the 3 MB
    # numerical waterfall in the compact evaluation artifact.
    saved = {key: value for key, value in result.items() if key != "observed_power"}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(saved, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": result["status"], "conclusion": result["conclusion"],
                      "best_candidate": result["best_candidate"],
                      "evaluation": result["evaluation"], "timings": result["timings"],
                      "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()


import copy
import hashlib
import io
import json

import numpy as np
import pytest
import soundfile as sf

from core.real_data import (BUNDLED_MANIFEST, RecordingValidationError,
                            analyze_real, load_manifest)

REAL_DIR = BUNDLED_MANIFEST.parent
REAL_OGG = REAL_DIR / "satnogs_6659851_2022-10-26T04-12-41.ogg"


def _wav_bytes(samples: np.ndarray, sample_rate_hz: int) -> bytes:
    stream = io.BytesIO()
    sf.write(stream, samples, sample_rate_hz, format="WAV", subtype="PCM_16")
    return stream.getvalue()


def _manifest_for_bytes(data: bytes, *, filename: str = "converted.wav") -> dict:
    manifest, _ = load_manifest(BUNDLED_MANIFEST)
    converted = copy.deepcopy(manifest)
    converted["recording_file"] = filename
    converted["recording_sha256"] = hashlib.sha256(data).hexdigest()
    converted["recording_format"]["container"] = "WAV"
    converted["recording_format"]["codec"] = "PCM signed 16-bit little-endian"
    return converted


@pytest.fixture(scope="module")
def replay():
    return analyze_real()


@pytest.fixture(scope="module")
def converted_wav():
    samples, sample_rate_hz = sf.read(REAL_OGG, dtype="float32", always_2d=False)
    data = _wav_bytes(samples, sample_rate_hz)
    return data, _manifest_for_bytes(data)


def test_bundled_recording_is_validated_and_native_spectrogram_is_preserved(replay):
    assert replay["mode"] == "archived_real_recording"
    assert replay["recording"]["sha256"] == "c317e44ccddb890023a1b863c326fb856525902da3aeefa3355d566fe64aaf63"
    assert replay["recording"]["acquisition_start_utc"] == "2022-10-26T04:12:41Z"
    assert replay["signal_processing"]["decoded_sample_rate_hz"] == 48000
    assert replay["signal_processing"]["native_time_bins"] == 706
    assert replay["signal_processing"]["native_frequency_bins"] == 1025
    assert np.asarray(replay["observed_power"]).shape == (706, 1025)


def test_real_target_ranks_independently_above_historical_incorrect_candidates(replay):
    assert replay["conclusion"] == "candidate_match"
    assert replay["best_candidate"]["catalog_id"] == "39444"
    assert replay["evaluation"]["best_candidate_matches_schedule"] is True
    assert replay["evaluation"]["independent_decoded_frame_count"] == 53
    assert replay["candidates"][0]["above_horizon_support"] > 0.9
    assert all(candidate["above_horizon_support"] == 0 for candidate in replay["candidates"][1:])


def test_measured_ridge_prediction_and_fitted_template_are_separate(replay):
    best = replay["candidates"][0]
    ridge = np.asarray([np.nan if x is None else x for x in replay["observed_ridge_hz"]])
    predicted = np.asarray(best["predicted_track_hz"])
    fitted = np.asarray([np.nan if x is None else x for x in best["fitted_template_hz"]])
    assert not np.array_equal(predicted, fitted)
    finite = np.isfinite(ridge) & np.isfinite(fitted)
    assert not np.allclose(ridge[finite], fitted[finite])
    assert best["ridge_residual_rms_hz"] > 0


def test_real_ml_is_explicitly_synthetic_and_uncalibrated(replay):
    assert replay["methods"]["ml"]["status"] == "experimental_uncalibrated"
    assert replay["methods"]["ml"]["decision"] is None
    assert replay["calibration"]["real_thresholds_available"] is False
    assert "false_alarm_rate" not in replay["evaluation"]


def test_bad_hash_and_incomplete_metadata_are_rejected():
    manifest, _ = load_manifest(BUNDLED_MANIFEST)
    bad = copy.deepcopy(manifest)
    bad["recording_sha256"] = "0" * 64
    with pytest.raises(RecordingValidationError, match="SHA-256 mismatch"):
        analyze_real(manifest_source=bad, recording=b"not the recording")
    incomplete = json.dumps({"schema": "lastping-real-recording-v1"}).encode()
    with pytest.raises(RecordingValidationError, match="missing required fields"):
        load_manifest(incomplete)


def test_pcm_wav_derived_from_bundled_recording_runs_full_pipeline(converted_wav):
    data, manifest = converted_wav
    result = analyze_real(recording=data, manifest_source=manifest)
    assert result["recording"]["local_source"] == "uploaded recording"
    assert result["signal_processing"]["decoded_sample_rate_hz"] == 48000
    assert result["signal_processing"]["decoded_channels"] == 1
    assert result["best_candidate"]["catalog_id"] == "39444"
    assert result["conclusion"] == "candidate_match"


@pytest.mark.parametrize(
    ("samples", "sample_rate_hz", "error"),
    [
        (np.zeros(4096, dtype=np.float32), 44100, "sample rate mismatch"),
        (np.zeros((4096, 2), dtype=np.float32), 48000, "expected one real audio channel"),
    ],
)
def test_wav_sample_rate_and_channel_mismatches_are_rejected(samples, sample_rate_hz, error):
    data = _wav_bytes(samples, sample_rate_hz)
    manifest = _manifest_for_bytes(data, filename="malformed.wav")
    with pytest.raises(RecordingValidationError, match=error):
        analyze_real(recording=data, manifest_source=manifest)

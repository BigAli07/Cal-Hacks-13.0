import copy
import json

import numpy as np
import pytest

from core.real_data import (BUNDLED_MANIFEST, RecordingValidationError,
                            analyze_real, load_manifest)


@pytest.fixture(scope="module")
def replay():
    return analyze_real()


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

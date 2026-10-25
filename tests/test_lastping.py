import numpy as np
from unittest.mock import patch

from core.detection import physics_search
from core.engine import analyze, saved_benchmark
from core.orbit import BEACON_HZ, DEFAULT_OBSERVER, doppler_offset_hz, get_orbit_track
from core.simulation import PRESETS, SimulationConfig, simulate
from core.training import SPLITS


def test_doppler_sign_and_units():
    expected = -BEACON_HZ * 1_000.0 / 299_792_458.0
    assert np.isclose(doppler_offset_hz(1.0), expected)
    assert doppler_offset_hz(1.0) < 0


def test_dimensions_and_reproducibility():
    orbit = get_orbit_track()
    config = SimulationConfig(seed=123)
    first, truth1 = simulate(config, orbit.time_s, orbit.doppler_hz)
    second, truth2 = simulate(config, orbit.time_s, orbit.doppler_hz)
    assert first.power.shape == (128, 192)
    assert np.array_equal(first.power, second.power)
    assert np.array_equal(truth1.dropout_mask, truth2.dropout_mask)


def test_detector_only_accepts_observed_data_and_tracks_are_distinct():
    orbit = get_orbit_track()
    observed, truth = simulate(SimulationConfig(seed=91, signal_excess_db=5), orbit.time_s, orbit.doppler_hz)
    result = physics_search(observed)
    assert not hasattr(observed, "preset")
    assert not hasattr(observed, "signal_present")
    assert truth.actual_track_hz is not None
    assert not np.array_equal(result.best_track_hz, truth.actual_track_hz)


def test_dataset_splits_are_independent():
    ranges = [set(range(a, b + 1)) for a, b in SPLITS.values()]
    assert not (ranges[0] & ranges[1] or ranges[0] & ranges[2] or ranges[1] & ranges[2])


def test_seed_and_strength_change_observed_data():
    orbit = get_orbit_track()
    low, _ = simulate(SimulationConfig(seed=5, signal_excess_db=-6), orbit.time_s, orbit.doppler_hz)
    strong, _ = simulate(SimulationConfig(seed=5, signal_excess_db=6), orbit.time_s, orbit.doppler_hz)
    other_seed, _ = simulate(SimulationConfig(seed=6, signal_excess_db=-6), orbit.time_s, orbit.doppler_hz)
    assert not np.array_equal(low.power, strong.power)
    assert not np.array_equal(low.power, other_seed.power)


def test_missing_model_is_reported_without_invented_score():
    with patch("core.engine.load_model", return_value=(None, None)):
        result = analyze({"preset": "noise_only", "seed": 2, "signal_excess_db": -2})
    assert result["methods"]["ml"]["status"] == "unavailable"
    assert result["methods"]["ml"]["score"] is None
    assert "core.training train" in result["methods"]["ml"]["setup_instruction"]


def test_required_presets_run_and_interference_control_changes_data():
    assert set(PRESETS) == {"strong_beacon", "faint_intermittent", "interference_only", "noise_only"}
    orbit = get_orbit_track()
    for preset in PRESETS:
        observed, _ = simulate(SimulationConfig(preset=preset, seed=31), orbit.time_s, orbit.doppler_hz)
        assert observed.power.shape == (128, 192)
    clean, clean_truth = simulate(SimulationConfig(seed=31, interference=False), orbit.time_s, orbit.doppler_hz)
    interfered, interfered_truth = simulate(SimulationConfig(seed=31, interference=True), orbit.time_s, orbit.doppler_hz)
    assert not clean_truth.interference_present
    assert interfered_truth.interference_present
    assert not np.array_equal(clean.power, interfered.power)


def test_observer_coordinates_affect_orbit_and_are_reported():
    berkeley = get_orbit_track(observer=DEFAULT_OBSERVER)
    new_york = get_orbit_track(observer={"latitude_deg": 40.7128, "longitude_deg": -74.0060, "elevation_m": 10})
    assert berkeley.provenance["observer"] != new_york.provenance["observer"]
    assert not np.array_equal(berkeley.doppler_hz, new_york.doppler_hz)


def test_saved_benchmark_is_historical_and_does_not_rerun():
    result = saved_benchmark()
    assert result["status"] == "ok"
    assert result["measurement_status"] == "historical_saved_artifact"
    assert result["artifact_path"] == "artifacts/benchmark.json"


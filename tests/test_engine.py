import json
import unittest

from core.engine import CONFIG_KEYS, PRESETS, analyze, benchmark


class AnalyzeContractTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "observer_lat_deg": 37.7749,
            "observer_lon_deg": -122.4194,
            "preset": "faint_intermittent",
            "signal_excess_db": 6.0,
            "interference": False,
            "seed": 42,
        }

    def test_required_keys_and_json(self):
        payload = analyze(self.config)
        for key in (
            "mode",
            "provenance",
            "satellite",
            "observation",
            "spectrum",
            "prediction",
            "detected_track",
            "results",
            "evidence",
            "runtime_ms",
            "ground_truth",
        ):
            self.assertIn(key, payload)
        json.dumps(payload)
        spec = payload["spectrum"]
        power = spec["power_db"]
        self.assertEqual(len(power), len(spec["times_s"]))
        self.assertEqual(len(power[0]), len(spec["frequency_offsets_hz"]))
        self.assertEqual(payload["mode"], "placeholder")
        self.assertEqual(payload["provenance"]["radio"], "simulated")
        for method in ("threshold", "physics", "ml"):
            self.assertEqual(payload["results"][method]["status"], "pending")
            self.assertIsNone(payload["results"][method]["score"])
        self.assertIsNone(payload["detected_track"])

    def test_unknown_preset_raises(self):
        cfg = dict(self.config, preset="nope")
        with self.assertRaises(ValueError):
            analyze(cfg)

    def test_missing_key_raises(self):
        cfg = dict(self.config)
        del cfg["seed"]
        with self.assertRaises(ValueError):
            analyze(cfg)

    def test_presets_and_config_keys_unchanged(self):
        self.assertEqual(
            PRESETS,
            (
                "strong_beacon",
                "faint_intermittent",
                "interference_only",
                "noise_only",
            ),
        )
        self.assertEqual(
            CONFIG_KEYS,
            (
                "observer_lat_deg",
                "observer_lon_deg",
                "preset",
                "signal_excess_db",
                "interference",
                "seed",
            ),
        )

    def test_benchmark_pending(self):
        self.assertEqual(benchmark(), {"status": "pending", "methods": [], "metadata": {}})


if __name__ == "__main__":
    unittest.main()

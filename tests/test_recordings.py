import json
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from core.recordings import analyze_recording, load_recording, spectrum_from_recording


def _write_stereo_wav(path: Path, sample_rate: int, i: np.ndarray, q: np.ndarray) -> None:
    interleaved = np.empty(i.size * 2, dtype=np.int16)
    interleaved[0::2] = np.clip(i * 32767, -32767, 32767).astype(np.int16)
    interleaved[1::2] = np.clip(q * 32767, -32767, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(interleaved.tobytes())


def _tone_iq(n: int, sample_rate: float, freq_hz: float) -> tuple[np.ndarray, np.ndarray]:
    t = np.arange(n) / sample_rate
    tone = np.exp(2j * np.pi * freq_hz * t) * 0.2
    return np.real(tone), np.imag(tone)


class RecordingApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.sample_rate = 8000
        self.n = 2048
        i, q = _tone_iq(self.n, self.sample_rate, 250.0)
        self.wav_path = self.dir / "tone.wav"
        _write_stereo_wav(self.wav_path, self.sample_rate, i, q)
        self.iq_path = self.dir / "tone.iq"
        interleaved = np.empty(self.n * 2, dtype="<f4")
        interleaved[0::2] = i.astype("<f4")
        interleaved[1::2] = q.astype("<f4")
        interleaved.tofile(self.iq_path)
        self.npy_path = self.dir / "tone.npy"
        np.save(self.npy_path, i + 1j * q)
        self.base_meta = {
            "path": str(self.wav_path),
            "format": "wav_pcm",
            "sample_rate_hz": float(self.sample_rate),
            "center_frequency_hz": 145_800_000.0,
            "observer_lat_deg": 37.7749,
            "observer_lon_deg": -122.4194,
            "start_time_utc": "2024-01-01T00:00:00Z",
            "n_fft": 256,
            "hop_length": 128,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_wav_spectrum_shape(self):
        recording = load_recording(self.base_meta)
        spec = spectrum_from_recording(recording)
        power = np.asarray(spec["power_db"])
        self.assertEqual(power.ndim, 2)
        self.assertEqual(power.shape[0], len(spec["times_s"]))
        self.assertEqual(power.shape[1], len(spec["frequency_offsets_hz"]))
        self.assertTrue(np.isfinite(power).all())

    def test_analyze_recording_schema(self):
        payload = analyze_recording(self.base_meta)
        json.dumps(payload)
        self.assertEqual(payload["mode"], "synthetic_orbit_real_radio")
        self.assertEqual(payload["provenance"]["radio"], "real")
        self.assertEqual(payload["results"]["ml"]["status"], "unavailable")
        self.assertIsNone(payload["results"]["ml"]["score"])
        self.assertFalse(payload["ground_truth"]["signal_present"])
        self.assertEqual(payload["ground_truth"]["times_s"], [])
        self.assertIsNone(payload["detected_track"])

    def test_iq_and_npy_load(self):
        iq_meta = dict(self.base_meta, path=str(self.iq_path), format="iq_f32le")
        npy_meta = dict(self.base_meta, path=str(self.npy_path), format="npy_complex")
        self.assertGreater(load_recording(iq_meta).samples.size, 0)
        self.assertGreater(load_recording(npy_meta).samples.size, 0)

    def test_missing_file(self):
        meta = dict(self.base_meta, path=str(self.dir / "missing.wav"))
        with self.assertRaises(FileNotFoundError):
            load_recording(meta)

    def test_missing_metadata_key(self):
        meta = dict(self.base_meta)
        del meta["center_frequency_hz"]
        with self.assertRaises(ValueError):
            load_recording(meta)

    def test_generation_keys_are_not_required(self):
        payload = analyze_recording(self.base_meta)
        self.assertNotIn("preset", payload["observation"])


if __name__ == "__main__":
    unittest.main()

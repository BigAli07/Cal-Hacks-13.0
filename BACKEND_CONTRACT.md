# LastPing backend contract

This file is the integration surface for Cursor (UI) and the scientific backend.

- Cursor exclusively edits `app.py` and `.streamlit/config.toml`.
- Backend exclusively edits `core/`, `tests/`, artifacts, dependencies, and these docs.
- Contract changes belong here and in `BACKEND_STATUS.md`. Do not fork a second UI.

## 1. Synthetic API (stable, currently used by the UI)

The UI already calls these two functions. **Do not change names, required config keys, or top-level return keys.**

```python
from core.engine import analyze, benchmark

analyze(config: dict) -> dict
benchmark() -> dict
```

### 1.1 `analyze` input

Required keys (generation only; detectors must not receive hidden copies of these after a recording exists):

| Key | Type | Meaning |
| --- | --- | --- |
| `observer_lat_deg` | float | Geodetic latitude, degrees, `[-90, 90]` |
| `observer_lon_deg` | float | Geodetic longitude, degrees, `[-180, 180]` |
| `preset` | str | `strong_beacon` \| `faint_intermittent` \| `interference_only` \| `noise_only` |
| `signal_excess_db` | float | Injected excess for **synthetic generation only** |
| `interference` | bool | Extra interference tone in **synthetic generation only** |
| `seed` | int | Reproducible synthetic RNG seed |

Unknown keys are ignored. Missing or invalid values raise `ValueError`.

`analyze` must not accept a recording path. Real files use §2.

### 1.2 `analyze` output

JSON-compatible dict. Array units:

| Field | Unit / shape |
| --- | --- |
| `spectrum.times_s` | seconds from start of recording, length `T` |
| `spectrum.frequency_offsets_hz` | Hz relative to the analysis center, length `F` |
| `spectrum.power_db` | relative power, dB, shape `[T][F]` |
| `prediction.times_s` | seconds |
| `prediction.frequency_offsets_hz` | Hz, same length as prediction times |
| `detected_track` | `null` or the same two arrays as `prediction` |
| `ground_truth.*` | overlay only; never an input to detectors |
| `runtime_ms` | milliseconds, integer, or `null` |

Allowed `mode` values:

- `placeholder` — synthetic arrays, detectors not scientifically valid
- `real_orbit_synthetic_radio`
- `synthetic_orbit_synthetic_radio`
- `real_orbit_real_radio`
- `synthetic_orbit_real_radio`

Allowed `results.*.status` values: `pending` | `candidate` | `insufficient_evidence` | `unavailable`.

`results.*.score` is `null` or a JSON number. For ML it is a **synthetic-model score**, not a probability. `null` must not be displayed as `0`.

Provenance keys the UI already reads: `radio`, `orbit`, `cache`, `model`, `orbit_detail`, `note`.

For synthetic `analyze`, `provenance.radio` remains `"simulated"`.

Errors: `ValueError` with a human-readable message. The UI surfaces that string.

### 1.3 `benchmark` output

```json
{"status": "pending|ready|unavailable", "methods": [], "metadata": {}}
```

`methods` is a list of row dicts for a table. Do not fill rates until they are computed on held-out cases.

---

## 2. Real-recording API (new, UI not wired yet)

Use this for files captured outside the synthetic generator. Keep it separate so `analyze(config)` stays generation-only.

```python
from core.recordings import load_recording, spectrum_from_recording, analyze_recording
from core.engine import analyze_recording  # re-export
```

### 2.1 Function signatures

```python
load_recording(metadata: dict) -> Recording
spectrum_from_recording(recording: Recording, *, n_fft: int = 256, hop_length: int | None = None) -> dict
analyze_recording(metadata: dict) -> dict
```

`Recording` is an in-memory object (`core.recordings.Recording`). It is **not** JSON. The UI should call `analyze_recording` only.

### 2.2 Input metadata (`analyze_recording` / `load_recording`)

Required:

| Key | Type | Meaning |
| --- | --- | --- |
| `path` | str | Local filesystem path to the capture |
| `format` | str | See formats below |
| `sample_rate_hz` | float | Samples per second of the stored stream |
| `center_frequency_hz` | float | RF / IF center corresponding to 0 Hz offset |
| `observer_lat_deg` | float | Observer latitude, degrees |
| `observer_lon_deg` | float | Observer longitude, degrees |

Optional:

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `start_time_utc` | str \| null | `null` | ISO-8601 UTC start of the first sample |
| `channel` | int | `0` | WAV channel if the file is real-valued multi-channel |
| `iq_order` | str | `"iq"` | `"iq"` or `"qi"` for interleaved float IQ |
| `max_duration_s` | float \| null | `120` | Truncate long files; `null` = no cap |
| `n_fft` | int | `256` | STFT window |
| `hop_length` | int \| null | `n_fft // 2` | STFT hop |
| `catalog_id` | str \| null | `null` | NORAD / catalog id if known |
| `satellite_name` | str \| null | `null` | Display name if known |

Formats:

| `format` | File contents |
| --- | --- |
| `wav_pcm` | PCM WAV. Mono = real baseband. Stereo = I on channel 0, Q on channel 1 unless `iq_order` is `"qi"`. |
| `iq_f32le` | Raw interleaved float32 little-endian IQ |
| `iq_f32be` | Raw interleaved float32 big-endian IQ |
| `npy_complex` | `.npy` array of complex64/complex128 samples |

`signal_excess_db`, `preset`, `interference`, and `seed` are **not** valid here. Passing them is ignored (not used for detection).

### 2.3 Returned arrays, units, statuses

`analyze_recording` returns the **same top-level schema as `analyze`**.

Differences when a file loads successfully:

| Field | Real-recording behavior |
| --- | --- |
| `mode` | `synthetic_orbit_real_radio` until a public orbit is attached; then `real_orbit_real_radio` |
| `provenance.radio` | `"real"` |
| `provenance.orbit` | `"unavailable"` \| `"cached"` \| `"real"` \| `"synthetic"` |
| `provenance.model` | `"missing"` until a persisted classifier exists |
| `observation.time_utc` | `start_time_utc` or `null` |
| `spectrum.*` | STFT of the file, units as in §1.2 |
| `ground_truth.signal_present` | `false` |
| `ground_truth` track arrays | empty (unknown for real captures) |
| `results.*` | `pending` / `unavailable` until detectors are verified on actual files |

`power_db` is **relative**: each run subtracts the median bin power so color scale is comparable. It is not calibrated dBm.

### 2.4 Error behavior

| Condition | Exception | UI should |
| --- | --- | --- |
| Missing required metadata key | `ValueError` | Show message |
| Unknown `format` | `ValueError` | Show message |
| Path does not exist | `FileNotFoundError` | Show message |
| Empty / too-short file | `ValueError` | Show message |
| Unreadable WAV / npy | `ValueError` | Show message |
| Sample rate ≤ 0 | `ValueError` | Show message |

Do not return a partial spectrum on failure. Detectors are not invoked if load fails.

Orbit lookup failures must not crash a successful radio load: set `provenance.orbit` to `"unavailable"` and leave `prediction` empty.

### 2.5 Illustrative output (not measured data)

The JSON below is **illustrative only**. It is not a detection result and must not be copied into the UI as live science.

```json
{
  "mode": "synthetic_orbit_real_radio",
  "provenance": {
    "radio": "real",
    "orbit": "unavailable",
    "orbit_detail": "No public orbital data attached.",
    "cache": null,
    "model": "missing",
    "note": "Real samples loaded; detectors not verified on this file."
  },
  "satellite": {
    "name": null,
    "catalog_id": null,
    "orbit_epoch": null,
    "source": null
  },
  "observation": {
    "time_utc": "2024-01-01T00:00:00Z",
    "observer_lat_deg": 37.7749,
    "observer_lon_deg": -122.4194
  },
  "spectrum": {
    "times_s": [0.0, 0.01],
    "frequency_offsets_hz": [-1000.0, 0.0, 1000.0],
    "power_db": [[-3.1, 0.4, -2.8], [-2.9, 0.2, -3.0]]
  },
  "prediction": {"times_s": [], "frequency_offsets_hz": []},
  "detected_track": null,
  "results": {
    "threshold": {"status": "pending", "score": null},
    "physics": {"status": "pending", "score": null},
    "ml": {"status": "unavailable", "score": null}
  },
  "evidence": [],
  "runtime_ms": 12,
  "ground_truth": {
    "signal_present": false,
    "times_s": [],
    "frequency_offsets_hz": []
  }
}
```

---

## 3. Detector isolation (both APIs)

After a `spectrum` exists, threshold / physics / ML may receive only:

- `spectrum`
- `prediction` (may be empty)
- observer coordinates
- observation time
- satellite catalog fields if present

They must not receive `preset`, `signal_excess_db`, `interference`, `seed`, or `ground_truth`.

---

## 4. UI integration notes for Cursor

Current `app.py` should keep calling `analyze` + `benchmark` only.

To add real files later:

1. Collect the metadata table in §2.2 (file picker + sample rate + center frequency + observer).
2. Call `analyze_recording(metadata)` instead of `analyze(config)`.
3. Reuse the existing waterfall / cards / JSON download (same schema).
4. Set the provenance badge from `provenance.radio == "real"`.
5. Keep showing **Placeholder — backend pending** while `mode` is `placeholder` or while `results.*.status` is `pending` and detectors are unverified.
6. Never label ML output as a real-world probability.
7. Never display “Satellite recovered”.

Required UI fixes (backend will list extras in `BACKEND_STATUS.md` after Cursor lands file loading): none yet, because real-file controls are not in the UI.

---

## 5. Readiness rule

A feature may be marked **ready** in `BACKEND_STATUS.md` only after a command in that file has been run on **actual** recorded samples (not the synthetic `analyze` path and not a unit-test fixture presented as field data).

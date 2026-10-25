# LastPing backend handoff

Canonical API for Cursor integration is **`BACKEND_CONTRACT.md`**. Progress and runnable commands are in **`BACKEND_STATUS.md`**. Do not treat this file as the real-recording contract.

## File responsibilities

| File | Owner | Responsibility |
| --- | --- | --- |
| `app.py` | Interface (done) | Session state, controls, waterfall, method cards, evidence, benchmark, JSON download, empty/loading/error/missing-model states |
| `core/__init__.py` | Shared | Re-exports `analyze` and `benchmark` |
| `core/engine.py` | Backend (replace internals) | Generation + detectors. Keep the public functions and return shape |
| `requirements.txt` | Shared | Streamlit, NumPy, Plotly, Skyfield, requests, SciPy, scikit-learn |
| `.streamlit/config.toml` | Interface | Dark mission-control theme |
| `README.md` | Shared | Setup and startup |

Do not train a model inside Streamlit reruns. Training belongs in an explicit offline or `benchmark()` implementation that the UI calls once per button press.

## Startup command

```bash
source .venv/bin/activate
streamlit run app.py
```

## API contract

```python
analyze(config: dict) -> dict
benchmark() -> dict
```

`analyze` receives **only** these configuration keys. Detectors must not be given hidden generation parameters (no extra keys, no ground-truth leakage).

```
observer_lat_deg: float
observer_lon_deg: float
preset: one of strong_beacon | faint_intermittent | interference_only | noise_only
signal_excess_db: float
interference: bool
seed: int
```

These keys configure **generation**. After a recording exists, threshold / physics / ML functions should see the recording, observer geometry, and predicted Doppler — not the injected excess or the ground-truth arrays.

### `analyze` return value

JSON-compatible object:

```json
{
  "mode": "placeholder",
  "provenance": {},
  "satellite": {},
  "observation": {},
  "spectrum": {
    "times_s": [],
    "frequency_offsets_hz": [],
    "power_db": []
  },
  "prediction": {
    "times_s": [],
    "frequency_offsets_hz": []
  },
  "detected_track": null,
  "results": {
    "threshold": {"status": "pending", "score": null},
    "physics": {"status": "pending", "score": null},
    "ml": {"status": "pending", "score": null}
  },
  "evidence": [],
  "runtime_ms": null,
  "ground_truth": {
    "signal_present": false,
    "times_s": [],
    "frequency_offsets_hz": []
  }
}
```

- `power_db` shape is `[time][frequency]`.
- `detected_track`, when present, uses the same two arrays as `prediction`.
- Ground truth is for the “Reveal simulated ground truth” overlay only. Never feed it into detectors.

Allowed `results.*.status` values:

- `pending`
- `candidate`
- `insufficient_evidence`
- `unavailable`

The UI maps:

- `pending` + `score=null` → **Pending** (never 0% or a detection)
- `candidate` → **Candidate beacon**
- `insufficient_evidence` → **Insufficient evidence**
- `unavailable` → **Unavailable** (used for missing ML model)

Never return or display “Satellite recovered”.

Allowed future `mode` values:

- `real_orbit_synthetic_radio`
- `synthetic_orbit_synthetic_radio`

Until those are real, keep `mode` as `placeholder` so the banner **Placeholder — backend pending** remains.

Provenance keys the UI already reads:

- `radio`: `simulated` (recordings are simulated)
- `orbit`: `real` | `cached` | `synthetic` | `unavailable`
- `cache`, `model`, `orbit_detail`, `note`

### `benchmark` return value

Placeholder:

```json
{"status": "pending", "methods": [], "metadata": {}}
```

When implemented, `methods` should be a list of row dicts suitable for `st.dataframe`. Do not invent measured performance.

## Placeholder state (current)

`core/engine.py` currently:

- Validates the six config keys
- Builds a deterministic noise waterfall (`96 × 192`) from `seed` / preset / interference / excess
- Leaves `prediction` empty
- Sets `detected_track` to `null`
- Sets all three method results to `{status: "pending", score: null}`
- Leaves `evidence` empty
- Returns `benchmark()` as pending with no methods
- Marks `provenance.model` as `missing` and `orbit` as `unavailable`

This is enough for the interface. It is **not** a scientific result.

## Backend tasks remaining

1. Load public orbital data (Skyfield + network/cache via `requests`) when available; otherwise a documented synthetic orbit with `mode=synthetic_orbit_synthetic_radio`.
2. Replace placeholder spectrum generation with a physically motivated simulated recording (Doppler, intermittency, interference, noise).
3. Compute a predicted frequency track from observer location and orbit. Fill `prediction`.
4. Implement threshold detection using the recording only.
5. Implement physics-guided detection using the recording + predicted track, not ground truth.
6. Train a small classifier **offline**; persist it; load at analyze-time. If the file is absent, return ML `status=unavailable`, `score=null`.
7. Fill `evidence` with short factual strings (SNR-like metrics, track alignment, gaps). Do not overclaim.
8. Implement `benchmark()` on held-out simulated cases. Return real counts/rates only after they are computed.
9. Populate satellite name, catalog ID, orbit epoch, source, and observation UTC.
10. Keep runtime measurement.

## Interface behavior the backend can rely on

- Analyze is explicit. Control edits do not call `analyze` until the button is pressed.
- Reset clears `st.session_state.analysis` and `benchmark` and restores San Francisco defaults (37.7749, -122.4194).
- Ground-truth overlay is off by default.
- JSON download is the raw `analyze` payload.

## Actual Cursor contributions

Cursor implemented the empty-repo foundation in one pass:

- Streamlit mission-control UI in `app.py`
- Placeholder `analyze` / `benchmark` contract in `core/engine.py`
- Theme, requirements, README, and this handoff
- Dependency install and `streamlit run app.py` startup check

Cursor did **not** implement orbital propagation, real detectors, model training, or measured benchmarks.

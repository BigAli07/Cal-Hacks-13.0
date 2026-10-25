# Backend status

Last updated: 2026-10-25

Owner: scientific backend (`core/`, `tests/`, artifacts, this file, `BACKEND_CONTRACT.md`).
UI owner: Cursor (`app.py`, `.streamlit/config.toml` only).

## Ready vs not ready

| Capability | Status | Why |
| --- | --- | --- |
| Synthetic `analyze(config)` / `benchmark()` | **Interface-compatible, not scientifically ready** | Placeholder waterfall + pending detectors. UI can call it. |
| Real-recording load + STFT (`analyze_recording`) | **Implemented, not ready** | Executed only on **unit-test fixtures**, never on actual captured radio. |
| Public orbit / predicted Doppler | Not started | Prediction arrays still empty. |
| Threshold / physics / ML on real files | Not started | Status remains `pending` / ML `unavailable`. |
| `benchmark()` measured rates | Not started | Still `{status: "pending", methods: []}`. |

Nothing is marked **ready**. Ready requires a command below run on an actual recording path.

## What landed this pass

- `BACKEND_CONTRACT.md` — synthetic API frozen; real-recording API defined.
- `core/recordings.py` — `load_recording`, `spectrum_from_recording`, `analyze_recording`.
- `core/engine.py` — existing `analyze` / `benchmark` unchanged; re-exports `analyze_recording`.
- `tests/test_engine.py`, `tests/test_recordings.py`.
- `artifacts/README.md` — drop zone for real captures / TLE cache / models.
- `pytest` added to `requirements.txt`.

`analyze()` still returns `mode=placeholder`, `radio=simulated`, all detector scores `null`.

## Exact runnable commands

From the repo root (`/Users/big_ali07/CalHacks`):

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

Synthetic contract smoke:

```bash
source .venv/bin/activate
python - <<'PY'
from core.engine import analyze, benchmark
cfg = dict(
    observer_lat_deg=37.7749,
    observer_lon_deg=-122.4194,
    preset="faint_intermittent",
    signal_excess_db=6.0,
    interference=False,
    seed=42,
)
p = analyze(cfg)
assert p["mode"] == "placeholder"
assert p["spectrum"]["power_db"][0]
assert p["results"]["threshold"]["score"] is None
assert benchmark()["status"] == "pending"
print("synthetic_ok", len(p["spectrum"]["times_s"]), "x", len(p["spectrum"]["frequency_offsets_hz"]))
PY
```

Real-recording API smoke (fixture file, **not** actual field data):

```bash
source .venv/bin/activate
python -m pytest tests/test_recordings.py -q
```

When an actual capture exists (example only — replace the path):

```bash
source .venv/bin/activate
python - <<'PY'
from core.recordings import analyze_recording
payload = analyze_recording({
    "path": "artifacts/YOUR_CAPTURE.wav",
    "format": "wav_pcm",
    "sample_rate_hz": 48000,
    "center_frequency_hz": 145.8e6,
    "observer_lat_deg": 37.7749,
    "observer_lon_deg": -122.4194,
    "start_time_utc": None,
})
print(payload["mode"], payload["provenance"]["radio"], payload["spectrum"].keys())
print("shape", len(payload["spectrum"]["times_s"]), "x", len(payload["spectrum"]["frequency_offsets_hz"]))
PY
```

That last command has **not** been run on actual data.

## Execution log

| Command | Result |
| --- | --- |
| `python -m pytest tests/ -q` | 11 passed (2026-10-25) |
| Actual recording `analyze_recording(...)` | **Not run** — no field file in `artifacts/` |

## UI integration (Cursor)

Keep calling `analyze` + `benchmark`. Do not switch the Analyze button to `analyze_recording` until file + RF metadata controls exist.

Required UI fixes from backend: **none** this pass (`app.py` was not edited).

When wiring files, follow `BACKEND_CONTRACT.md` §4. Report schema mismatches here rather than changing the six synthetic config keys.

## Next backend work

1. Obtain or place an actual IQ/WAV capture under `artifacts/` and run `analyze_recording`.
2. Attach public orbit (Skyfield) when available; fill `prediction`.
3. Detectors on spectrum + prediction only (no generation keys, no ground truth).
4. Persist a small classifier offline; load or return ML `unavailable`.
5. Mark ready only after the actual-data command succeeds and detector outputs are inspected.

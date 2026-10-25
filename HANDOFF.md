# LastPing handoff

## Current state

The root-level LastPing application is complete and isolated from the existing
`pi/` vision project. `core.engine.replay_real(recording, manifest) -> dict`
validates and processes archived SatNOGS BPSK OGG/WAV data.
`core.engine.analyze(config) -> dict` runs simulation and
all available detectors. `core.engine.benchmark() -> dict` runs the fixed final
test evaluation. `core.engine.saved_benchmark() -> dict` reads the saved JSON
without recomputing it and marks timings as historical. Missing ML artifacts
return `status=unavailable`, `score=null`, and the exact training instruction.

Modules:

- `core/orbit.py`: CelesTrak caching, pass selection, Skyfield/SGP4 geometry.
- `core/simulation.py`: observed spectrum and separate reveal-only truth.
- `core/detection.py`: baseline, bounded template bank, features.
- `core/training.py`: explicit model training and untouched benchmark.
- `core/real_data.py`: real OGG/WAV validation, chunked PSD, historical orbit
  prediction, independent ridge extraction, candidate ranking, and real replay.
- `core/engine.py`: stable integration API.
- `app.py`: Cursor-owned Streamlit interface; only minimal backend wiring and
  accuracy fixes should be made here.

## Reproduce

```bash
.venv/bin/pip install -r requirements-lastping.txt
.venv/bin/python -m core.real_data
.venv/bin/python -m core.training train
.venv/bin/python -m core.training benchmark
.venv/bin/python -m pytest -q tests/test_lastping.py
.venv/bin/streamlit run app.py
```

The real replay uses SatNOGS observation 6659851 and its historical FUNCUBE-1
TLE. It ranks FUNCUBE-1 above three incorrect historical candidates without
passing the scheduled target label into ranking. The recording contains 53
independently published decoded-frame artifacts. The OGG is lossy,
Doppler-corrected mono audio—not raw I/Q—and real false-alarm rate is not
measured from this single positive pass.

The synthetic cache selects CUTE-1 (CO-55), NORAD 27844. Observer coordinates
are passed into Skyfield pass selection and preserved in results. The assumed
437 MHz radio experiment remains synthetic. Training used 500/160 independent
train/validation recordings; benchmark used 200 untouched recordings. See
`artifacts/benchmark.json` and `MODEL_CARD.md` for measured results.

## Contribution record

Cursor owns the application interface. Codex implemented and verified the
scientific core, artifacts, backend tests, provenance, and documentation, and
made only the minimal interface edits needed to pass observer/interference
controls, real upload/replay, evidence, and honest calibration labels. The
unrelated existing vision project was preserved. No STRF code or upload control
was added because real recording ingestion is outside this pass.


# Cursor status — LastPing integrated interface

Date: 2026-10-25

The earlier report that the Codex backend was unpublished is **obsolete**. This document describes the combined application on `cursor/lastping-integrated`.

## Publish

| Item | Value |
| --- | --- |
| Repository | https://github.com/BigAli07/Cal-Hacks-13.0 |
| Foundation | `origin/codex/lastping-backend-handoff` @ `a289776` |
| Integration branch | `cursor/lastping-integrated` |
| PR vs backend | opened after push; not merged |
| Previous UI PR | https://github.com/BigAli07/Cal-Hacks-13.0/pull/1 left **unmerged** |

`core/` was not replaced. Placeholder `engine.py` from `cursor/interface` is **not** on this branch.

## What the interface does now

Cursor restyled Codex’s working Streamlit app (`app.py` + `.streamlit/config.toml`) against the **published** API:

- `replay_real(recording=None, manifest=None)`
- `analyze(config)` with observer + presets `strong_beacon` / `faint_intermittent` / `interference_only` / `noise_only`
- `benchmark()` and `saved_benchmark()`

Capabilities kept:

- Bundled SatNOGS observation 6659851 (archived, not live)
- Upload OGG/WAV + `lastping-real-recording-v1` JSON manifest
- Separately labelled synthetic experiment
- Recording source, acquisition UTC, waterfall (real: audio Hz vs seconds; synthetic: Doppler offset kHz)
- Predicted candidate tracks, best fitted template, independent measured ridge
- Ranked evidence table
- Honest ML labels (`synthetic-model score`, uncalibrated on real RF)
- Analyze / Reset, stale-control warning, JSON downloads
- Historical saved benchmark expander
- `RecordingValidationError` and missing-model `setup_instruction`

Conclusion copy maps backend `candidate_match` → **Candidate beacon**; never “Satellite recovered”.

## Checks executed

### Implemented and verified

- Installed `requirements-lastping.txt` into `.venv`.
- `.venv/bin/python -m compileall -q app.py core`
- `.venv/bin/python -m pytest -q tests/test_lastping_app.py tests/test_lastping.py tests/test_real_data.py` → **18 passed** (46.56 s)
- AppTest: bundled replay ranks NORAD 39444; upload of the same OGG+manifest works; synthetic Analyze/Reset/stale warning; observer/interference reach `analyze`.
- Browser on `http://localhost:8502`:
  - Empty real mode waits for Analyze
  - Bundled Analyze: 706×1025 waterfall, FUNCUBE 1 / NORAD 39444, **Candidate beacon**, archived-not-live warning, uncalibrated ML caption, JSON download
  - Synthetic mode: CUTE-1 (CO-55) CelesTrak orbit, 128×192 waterfall, method scores, JSON download

### Implemented but unverified

- Arbitrary third-party OGG/WAV uploads (only the bundled pair was exercised in AppTest + browser bundled path)
- Manual train / live CelesTrak fetch / fresh `benchmark()` click in the browser this pass

### Missing or blocked (not Cursor UI defects)

- Full `pytest -q` collection errors in unrelated `pi/` vision tests (`ModuleNotFoundError: cv2`). LastPing tests pass.
- No live SDR. Real mode is archived replay only.
- Real-data ML remains `experimental_uncalibrated` by backend design.
- Backend PR [#2](https://github.com/BigAli07/Cal-Hacks-13.0/pull/2) is still unmerged (Codex/owner).

## Startup

```bash
cd Cal-Hacks-13.0
git checkout cursor/lastping-integrated
python3 -m venv .venv
.venv/bin/pip install -r requirements-lastping.txt
.venv/bin/streamlit run app.py
```

## Remaining blockers

None that prevent archived real replay or synthetic analysis through this interface.

Optional backend follow-ups (not changed here): real negative corpus, I/Q importer, live SDR.

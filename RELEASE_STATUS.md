# LastPing release status

Release verification date: 2026-10-25

Repository: `https://github.com/BigAli07/Cal-Hacks-13.0.git`

Branch: `cursor/lastping-integrated`

Publication status: **published**. GitHub contains the implementation commit
`c99276e01187d4f439048883d01ca843ef185789` and handoff commit
`cfb05a675df151d460ebf212959e2c878fd86f4c` on the integration branch.

Exact verified implementation revision:
`c99276e01187d4f439048883d01ca843ef185789`

The revision above contains the reproducible test requirements, scoped CI,
WAV compatibility tests, malformed WAV validation, and setup/provenance
documentation. This handoff document is a documentation-only follow-up to that
verified implementation revision.

## Commands and actual outcomes

```bash
.venv/bin/python -m pip install -r requirements-test.txt
```

Passed. Runtime requirements and pytest resolved in the verification virtual
environment.

```bash
.venv/bin/python -m compileall -q app.py core
```

Passed.

```bash
.venv/bin/python -c 'from core.training import load_model; model, metadata = load_model(); assert model is not None and metadata is not None; assert list(model.named_steps) == ["scaler", "classifier"]; assert metadata["counts"]["training"] == 500'
```

Passed. The committed scaler/classifier artifact and metadata loaded.

```bash
.venv/bin/python -m pytest -q tests/test_lastping_app.py tests/test_lastping.py tests/test_real_data.py
```

Passed: **22 tests**, with four Skyfield/NumPy deprecation warnings, in 19.44
seconds. This includes the full test-generated WAV replay and rejected 44.1 kHz
and stereo WAV cases.

```bash
.venv/bin/python -m core.real_data --output /tmp/lastping-release-real-replay.json
```

Passed: `candidate_match`; FUNCUBE 1 / 39444; score `6.8254372083`;
margin `4.1773315627`; total processing `3.5565` seconds. The strict JSON check
passed, the compact export omitted `observed_power`, the ML status was
`experimental_uncalibrated`, and real thresholds were unavailable as intended.

The same commands are encoded in `.github/workflows/lastping.yml`. Remote CI
completed successfully on handoff SHA `cfb05a675df151d460ebf212959e2c878fd86f4c`:

- Push run: `https://github.com/BigAli07/Cal-Hacks-13.0/actions/runs/40200784197`
  — **success**, one job completed in 1 minute 20 seconds.
- PR run: `https://github.com/BigAli07/Cal-Hacks-13.0/actions/runs/40200784335`
  — **success**, one job completed in 2 minutes 19 seconds.

Both runs passed checkout, Python 3.12 setup, libsndfile/runtime/test dependency
installation, compilation, saved-model loading, scoped tests, and compact
offline replay/strict JSON export. Informational annotations noted the GitHub
Actions Node.js 20 transition and the future `ubuntu-latest` image migration;
they did not fail the job.

## Supported demonstration claim

**Candidate-track analysis of one independently supported archived satellite
reception.**

The application may show the verified SatNOGS 6659851 replay, its provenance,
native spectrogram, independent measured ridge, historical candidate tracks,
FUNCUBE-1 ranking, exploratory synthetic-model score with its uncalibrated
label, and strict JSON export.

It must not claim live reception, satellite recovery, confirmed general
identification, calibrated receiver sensitivity, measured real recall, or
measured real false-alarm performance.

## Remaining limitations

- The real dataset contains one independently supported positive pass and no
  defensible real negative.
- Retained incorrect candidates are below the receiver horizon. A bounded
  SatNOGS search found above-horizon objects only on mismatched UHF channels;
  none was retained as an in-band control.
- The recording is lossy target-Doppler-corrected audio, not raw I/Q or
  calibrated power.
- The ML model is trained only on synthetic observations and is uncalibrated on
  real RF.
- WAV support is verified for the PCM-16 derivative of the same licensed OGG,
  not for arbitrary codecs or independent observations.
- The workflow currently uses `actions/checkout@v4` and
  `actions/setup-python@v5`; GitHub emitted an informational notice that their
  Node.js 20 implementations are being forced onto Node.js 24. A later
  maintenance update should adopt successor action versions when available.

## Presentation readiness

The archived-real workflow is ready for a presentation using the exact claim
above. Cursor's concurrent `1e122bc` commit reports the remaining interface
fixes as complete in `FINAL_UI_STATUS.md`, and the combined AppTests pass. No
known interface blocker remains, subject to Cursor's final visual acceptance.
This backend release did not modify Cursor-owned `app.py`, theme files, or
`FINAL_UI_STATUS.md`.

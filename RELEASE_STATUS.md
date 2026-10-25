# LastPing release status

Release verification date: 2026-10-25

Repository: `https://github.com/BigAli07/Cal-Hacks-13.0.git`

Branch: `cursor/lastping-integrated`

Publication status: **blocked before remote update**. The remote branch remains
at `1e122bc93ed17cbbb4161d1f60b1c707b0c61195`; the verified release commits are
preserved locally.

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

The same commands are encoded in `.github/workflows/lastping.yml`. Remote CI has
**not started** because GitHub rejected the workflow-file push. Local success is
not reported as remote CI success.

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
- Remote CI must complete before it is described as passing.
- Publishing is blocked by GitHub authentication scope. The active OAuth token
  has `gist`, `read:org`, and `repo`, but not `workflow`. Git rejected the push
  with `refusing to allow an OAuth App to create or update workflow
  .github/workflows/lastping.yml without workflow scope`; the connected GitHub
  integration independently returned HTTP 403 for the same workflow write.

## Presentation readiness

The archived-real workflow is ready for a presentation using the exact claim
above. Cursor's concurrent `1e122bc` commit reports the remaining interface
fixes as complete in `FINAL_UI_STATUS.md`, and the combined AppTests pass. No
known interface blocker remains, subject to Cursor's final visual acceptance.
This backend release did not modify Cursor-owned `app.py`, theme files, or
`FINAL_UI_STATUS.md`.

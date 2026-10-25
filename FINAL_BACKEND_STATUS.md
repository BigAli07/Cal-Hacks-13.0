# Final backend status — integrated LastPing

Updated: 2026-10-25

Repository: `https://github.com/BigAli07/Cal-Hacks-13.0.git`

Branch: `cursor/lastping-integrated`

Verified implementation revision: `c99276e01187d4f439048883d01ca843ef185789`

This status reflects fresh execution against the implementation revision above,
not results copied from `CODEX_STATUS.md`, `CURSOR_STATUS.md`, or earlier audit
documents. Cursor-owned `app.py`, theme files, and `FINAL_UI_STATUS.md` were not
modified by the backend release work.

## 1. Implemented and verified

### Reproducible setup and scoped CI

- `requirements-test.txt` includes `requirements-lastping.txt` and
  `pytest>=8,<10`. The documented command
  `.venv/bin/python -m pip install -r requirements-test.txt` completed locally;
  all requirements were satisfied in the verification environment.
- `.github/workflows/lastping.yml` uses Python 3.12, installs only libsndfile and
  LastPing test requirements, compiles `app.py` and `core/`, validates the saved
  model artifact, runs the three scoped LastPing test files, and performs a
  compact offline replay plus strict-JSON validation. It does not install
  OpenCV or collect the unrelated `pi/` suite.
- `README.md` documents separate runtime, test, replay/export, cache-refresh,
  training, and benchmark commands.

### Real recording import, metadata, and formats

- `core/real_data.py` validates the `lastping-real-recording-v1` manifest,
  recording SHA-256, bundled original SatNOGS metadata SHA-256, acquisition UTC,
  receiver coordinates, transmitter, historical TLEs, decoded sample rate,
  channel count, duration, and target-Doppler-corrected BPSK flag.
- The bundled OGG hash remains
  `c317e44ccddb890023a1b863c326fb856525902da3aeefa3355d566fe64aaf63`;
  the untouched observation JSON hash remains
  `e47c5a0ef8faeac94dd03fcd76d796a5a1811132b98adc7828edb8ac310246f0`.
- OGG and WAV are now both exercised. `tests/test_real_data.py` converts the
  licensed bundled OGG samples to a temporary mono 48 kHz PCM-16 WAV, updates a
  temporary manifest/hash, and runs the complete archived pipeline. It still
  ranks FUNCUBE 1 / 39444 and returns `candidate_match`. Separate generated WAVs
  with 44.1 kHz audio and two channels are rejected with the expected validation
  errors.
- The conversion procedure and CC BY-SA 4.0 provenance are documented in
  `data/real/README.md`. No duplicate WAV is committed, and the conversion is
  explicitly the same observation—not additional real evidence.

### Spectrogram and independent measurements

- `core/real_data.py::_spectrogram` computes the native `706 × 1025` PSD using
  a 2,048-point Hann FFT, 50% overlap within 0.5-second bins, and 23.4375 Hz
  frequency resolution. The result is not resized to the synthetic shape.
- `_observed_ridge` measures an energy-weighted ridge in a fixed ±3.5 kHz band
  around the documented 12 kHz audio IF and receives no candidate track.
- Tests freshly confirmed that the measured ridge, raw prediction, and searched
  fitted template are distinct.

### Historical orbit, receiver correction, and ranking

- Historical TLEs are evaluated with Skyfield/SGP4 at the 2022 acquisition
  timestamps and PE0SAT-32 coordinates. Doppler uses
  `delta_f = -f0 * range_rate / c` with tested sign and units.
- Candidate audio frequency is modeled as `audio IF + candidate RF Doppler -
  scheduled-target RF Doppler`, matching the target-tracking receiver. The
  scheduled identity is compared with the winner only after ranking and is not
  a detector feature.
- Fresh archived replay result: FUNCUBE 1 / 39444 ranked first with score
  `6.8254372083`, margin `4.1773315627`, −500 Hz fitted offset, 99.3% visibility
  support, and about 283.8 Hz ridge RMS residual. The three retained incorrect
  historical candidates are below the receiver horizon.

### Real-control acquisition and evaluation

- A bounded public SatNOGS search examined nearby observation IDs
  6659801–6659901: 101 observations, 55 unique non-target TLEs, and nine objects
  geometrically above PE0SAT-32's horizon during the positive recording. Every
  above-horizon object's documented observation frequency was UHF
  (435.310–437.676 MHz), not the recorded 145.935 MHz VHF channel.
- A separate SatNOGS query for BPSK observations from 03:30–05:00 UTC returned
  25 observations and nine unique non-target objects; none was above the
  receiver horizon during the positive replay.
- The closest available high-elevation case, YUBILEINY / 32953 from SatNOGS
  observation 6659858, was run once through a temporary augmented manifest. The
  unchanged pipeline kept FUNCUBE first at `6.825`; YUBILEINY scored `2.156`,
  had 99.3% visibility support, and 1,844 Hz ridge RMS residual. It was not
  retained because its documented transmitter was 435.3157 MHz, so treating it
  as an in-band VHF negative would be misleading.
- No observation was accepted as a real negative. SatNOGS `bad`, `failed`,
  `unknown`, or zero-frame metadata does not prove the absence of received
  energy. No identities, labels, thresholds, or evaluation cases were modified
  to manufacture a control.

### ML and synthetic evaluation

- The saved model is a scikit-learn `StandardScaler` plus
  `LogisticRegression`, trained on 500 synthetic observations. Its six inputs
  are derived from observed strength and searched-track evidence; schedule and
  simulation truth are not features.
- Train/validation/test seeds remain disjoint: 10000–10499, 20000–20159, and
  30000–30199. The committed model and metadata loaded successfully.
- The real replay returns status `experimental_uncalibrated`, score label
  `synthetic-model score`, decision `None`, and
  `real_thresholds_available: false`. The observed score of approximately 1.0
  is not a calibrated real probability.
- The fixed 200-case synthetic result remains baseline 9% recall / 7% FAR,
  physics 60% / 11%, and ML 60% / 8%. These are synthetic-only measurements.

### Interface contract, offline operation, and export

- `core.engine.replay_real`, `analyze`, `benchmark`, and `saved_benchmark`
  remain the stable interface used by Cursor's `app.py`.
- Fresh AppTests covered Analyze/Reset behavior, stale-state handling,
  observer/interference propagation, bundled replay, uploaded OGG plus manifest,
  missing uploads, and clearing previous results.
- Bundled replay and strict JSON export completed offline. The compact export
  omits `observed_power`, retained all candidate/method/calibration evidence,
  parsed with `allow_nan=False` semantics, and identified FUNCUBE 1 / 39444.

### Fresh release checks

```text
.venv/bin/python -m pip install -r requirements-test.txt
  PASS: runtime and pytest requirements resolved

.venv/bin/python -m compileall -q app.py core
  PASS

saved-model load/schema check
  PASS: scaler + classifier, training count 500

.venv/bin/python -m pytest -q tests/test_lastping_app.py tests/test_lastping.py tests/test_real_data.py
  PASS: 22 passed, 4 Skyfield/NumPy deprecation warnings, 19.44 s

.venv/bin/python -m core.real_data --output /tmp/lastping-release-real-replay.json
  PASS: candidate_match; 39444; score 6.8254372083; margin 4.1773315627;
        total processing 3.5565 s

strict JSON and calibration assertions
  PASS: no observed_power; experimental_uncalibrated; no real thresholds
```

## 2. Implemented but unverified

- The new GitHub Actions workflow passed the same commands locally but has not
  passed remotely. Publication is blocked because the active GitHub OAuth token
  has `repo` but not `workflow` scope; GitHub rejected the push before changing
  the remote branch. The connected GitHub integration also returned HTTP 403
  for the workflow-file write.
- The test requirements resolved in the existing clean worktree environment;
  the remote Python 3.12 CI run is the pending clean-run confirmation.
- WAV compatibility is verified for the test-generated PCM-16 derivative and
  validation failures above. Arbitrary third-party WAV codecs, manifests,
  receivers, and non-SatNOGS processing chains remain outside the contract.
- The saved model loaded and its fixed test benchmark was previously recomputed;
  training was not rerun because doing so would replace release artifacts.
- External SatNOGS availability was used for the bounded control search, but no
  new external recording was downloaded or admitted to the release dataset.

## 3. Missing or blocked

### Required limits for this release

- No licensed, documented real negative meeting the scientific labeling
  requirements was found within the bounded search.
- No incorrect satellite with both an appropriate historical TLE, above-horizon
  geometry, and a relevant 145.935 MHz signal hypothesis was found. The
  band-mismatched YUBILEINY evaluation is exploratory only and is not retained
  as an evaluation case.
- Therefore real recall, real false-alarm rate, general satellite
  identification, and recovery remain unmeasured. The supported demonstration
  claim is exactly: **“Candidate-track analysis of one independently supported
  archived satellite reception.”**
- Remote CI status is pending after push and must not be called passing until
  GitHub reports completion. At handoff, the workflow has not reached the remote
  repository and CI has not started.
- **Publication blocker:** `git push origin cursor/lastping-integrated` was
  rejected with `refusing to allow an OAuth App to create or update workflow
  .github/workflows/lastping.yml without workflow scope`. `gh auth status`
  reports scopes `gist`, `read:org`, and `repo`; `workflow` is absent. Remote
  remains at `1e122bc93ed17cbbb4161d1f60b1c707b0c61195`. The verified local
  commits are preserved and no force-push was attempted.

### Presentation readiness and ownership boundary

- The archived-real backend workflow is ready for presentation under the narrow
  claim above: replay, WAV/OGG validation, evidence extraction, ranking,
  calibration labels, offline operation, and JSON export pass locally.
- Cursor's concurrent `1e122bc` commit reports the interface fixes in
  `FINAL_UI_STATUS.md` as complete, and the combined AppTests pass. No known UI
  blocker remains; final visual acceptance remains Cursor's ownership. This
  backend release did not modify `app.py`, theme files, or the UI status file.

### Optional future work

- Live SDR, raw-I/Q ingestion, deployment, and production multi-user services
  are not required for this archived-real hackathon release.
- A licensed multi-pass, multi-station real positive/negative corpus and
  real-domain calibration are future requirements only if the project later
  makes generalized real-world ML or identification claims.

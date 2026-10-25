# Final backend status — integrated LastPing

Audit date: 2026-10-25

Repository: `https://github.com/BigAli07/Cal-Hacks-13.0.git`

Branch: `cursor/lastping-integrated`

Audited remote commit: `99008bf30012034206cb3511a08e8401087cf6f2`

This report is based on the current implementation and fresh commands run in a
clean integration worktree. `CODEX_STATUS.md` describes the earlier backend
handoff branch, and `CURSOR_STATUS.md` records the earlier integration commit
`9dc5c95`; they are useful history but are not evidence that the current commit
passed this audit. “Verified” below means inspected in code and exercised during
this audit unless explicitly identified as committed historical evidence. The
remote advanced during the audit from `7ec617d` to `99008bf`; inspection showed
that the intervening commit added only `FINAL_UI_STATUS.md` and did not change
the application, backend, tests, data, or artifacts covered by these checks.

## 1. Implemented and verified

### Real recording import and metadata validation

- **Code:** `core/real_data.py::load_manifest`, `_recording_bytes`,
  `_validate_original_metadata`, `_spectrogram`, and `analyze_real`; the stable
  entry point is `core/engine.py::replay_real`.
- **Contract:** `lastping-real-recording-v1` requires observation/source fields,
  acquisition UTC, receiver coordinates/elevation, decoded sample rate and
  channel count, audio IF, target-Doppler-correction flag, transmitter, scheduled
  target, and a non-empty historical-TLE candidate catalog. Input is mono OGG or
  WAV readable by libsndfile. The current importer deliberately rejects audio
  not documented as target-Doppler-corrected BPSK.
- **Evidence:** the bundled OGG SHA-256 is
  `c317e44ccddb890023a1b863c326fb856525902da3aeefa3355d566fe64aaf63`
  and the original SatNOGS JSON SHA-256 is
  `e47c5a0ef8faeac94dd03fcd76d796a5a1811132b98adc7828edb8ac310246f0`;
  both freshly matched `data/real/satnogs_6659851_manifest.json`. The untouched
  JSON is cross-checked against observation ID, start time, receiver location,
  transmitter frequency, and scheduled-target TLE. Fresh tests also rejected a
  bad recording hash and incomplete metadata.
- **Result:** SatNOGS observation 6659851 decoded as 16,934,208 mono samples at
  48 kHz (352.796 seconds). This is archived, lossy, target-corrected audio—not
  live reception, raw I/Q, or calibrated RF power.

### Spectrogram calculation

- **Code:** `core/real_data.py::_spectrogram` uses a 2,048-point Hann window,
  50% FFT overlap within 0.5-second aggregation bins, one-sided PSD scaling,
  and the recording's native 48 kHz sample rate.
- **Evidence:** `tests/test_real_data.py::test_bundled_recording_is_validated_and_native_spectrogram_is_preserved`
  passed freshly. The bundled recording produced a native `706 × 1025` power
  array with 23.4375 Hz frequency spacing; it was not resized to the synthetic
  `128 × 192` shape.

### Historical orbital predictions and Doppler correction

- **Code:** `core/real_data.py::_candidate_tracks` evaluates each historical TLE
  with Skyfield/SGP4 at the actual acquisition timestamps and PE0SAT-32
  coordinates. `core/orbit.py::doppler_offset_hz` implements
  `delta_f = -f0 * range_rate / c` with range rate converted from km/s to m/s.
- **Receiver correction:** because SatNOGS followed the scheduled target, each
  candidate audio prediction is `audio IF + candidate RF Doppler - scheduled
  target RF Doppler`. The scheduled target TLE is required to reconstruct the
  receiver correction; its catalog identity is not supplied to the scoring
  function.
- **Evidence:** the Doppler sign/unit test passed freshly. The replay used
  acquisition start `2022-10-26T04:12:41Z`, receiver 51.721268 N, 5.029 E at
  5 m, a 145.935 MHz carrier, 12 kHz audio IF, and the stored 2022 historical
  TLEs.

### Independent signal measurements

- **Code:** `core/real_data.py::_normalize` performs per-time-bin robust
  log-power normalization. `_observed_ridge` computes an energy-weighted ridge
  in a fixed ±3.5 kHz band around the documented audio IF. It receives no
  candidate track. `_score_candidate` separately searches each prediction over
  bounded timing (−2 to +2 seconds) and frequency (−1,500 to +1,500 Hz) offsets.
- **Evidence:** `tests/test_real_data.py::test_measured_ridge_prediction_and_fitted_template_are_separate`
  freshly confirmed that the predicted track, fitted template, and measured
  ridge are distinct and that the ridge residual is non-zero.

### Candidate ranking and incorrect-candidate comparisons

- **Code:** `core/real_data.py::_score_candidate` calculates normalized
  along-track evidence, in-band support, persistence, visibility support, and
  residuals to the independent ridge. `analyze_real` sorts first by whether a
  candidate has any above-horizon support and then by measured score. The
  scheduled catalog ID is compared with the winner only after ranking in the
  `evaluation` block.
- **Evidence:** the fresh offline replay returned `candidate_match`; FUNCUBE 1 /
  NORAD 39444 ranked first with score `6.8254372083`, margin `4.1773315627`,
  fitted offset −500 Hz, 99.3% above-horizon support, and approximately
  283.8 Hz RMS ridge residual. SatNOGS' 53 decoded frames are post-ranking
  positive support, not a detector input.
- **Incorrect comparisons:** OSCAR 11, AAUSAT CUBESAT 2, and OSCAR 7 use genuine
  historical TLEs retained from adjacent SatNOGS observations. All three are
  below PE0SAT-32's horizon during this recording. They exercise unsupported
  candidates but are not a strong real-world hard-negative set.

### ML training, inputs, artifacts, and calibration

- **Code:** `core/training.py` trains a scikit-learn `StandardScaler` plus
  `LogisticRegression`; `core/detection.py::FEATURE_SCHEMA` defines six
  observation-derived inputs: baseline peak, searched-track accumulation,
  track/background contrast, supported fraction, persistence, and stationary
  contrast. No schedule label, preset label, seed, injected offset, or ground
  truth enters the classifier.
- **Training/evaluation split:** 500 synthetic training seeds 10000–10499; 160
  validation seeds 20000–20159 used to fix thresholds at a target 5% empirical
  false-alarm rate; 200 test seeds 30000–30199 (100 signal, 100 negative) held
  out from threshold selection.
- **Artifacts:** `artifacts/lastping_model.joblib` loaded successfully and
  contained the `scaler` and `classifier` steps. Its feature schema matched
  `artifacts/model_metadata.json`. `artifacts/benchmark.json` is explicitly a
  saved historical measurement; ordinary UI reruns do not retrain or benchmark.
- **Real replay behavior:** real candidate features are derived from measured
  baseline/candidate evidence. The returned ML status is
  `experimental_uncalibrated`, its label is `synthetic-model score`, its
  decision is `None`, and no synthetic threshold is transferred to real RF.
  The real-data test for these constraints passed freshly.

### Synthetic experiments

- **Code:** `core/simulation.py` generates deterministic `128 × 192` power
  spectra for strong beacon, faint/intermittent beacon, interference-only, and
  noise-only presets. Ground truth is stored separately from `ObservedRecording`.
  `core/detection.py` performs the baseline, bounded physics search, and feature
  extraction; `core/engine.py::analyze` exposes their results.
- **Fresh benchmark:** a new benchmark was run against the saved model while
  redirecting output to `/tmp`, so committed artifacts were not changed. On 100
  positives and 100 negatives: baseline recall/FAR was 9%/7%; physics was
  60%/11%; ML was 60%/8%. These are synthetic-generator results, not real-world
  recall or false-alarm measurements.
- **Evidence:** fresh tests covered reproducibility, truth isolation, disjoint
  seed splits, all four presets, interference control, observer effects,
  missing-model behavior, and historical benchmark labeling.

### Interface/backend integration

- **Code:** `app.py` calls `replay_real`, `analyze`, `benchmark`, and
  `saved_benchmark` from `core/engine.py`. It displays the real waterfall,
  predicted tracks, fitted template, independent measured ridge, ranked table,
  method statuses, provenance, calibration warning, and processing/acquisition
  times. It labels the source “archived real (not live)” and clears stale real
  results before validating a new source.
- **Evidence:** five Streamlit AppTests passed freshly. They exercised Analyze
  gating, Reset, stale synthetic controls, observer/interference propagation,
  bundled real replay, upload of the bundled OGG plus manifest, missing-upload
  handling, and stale-result clearing. The backend/UI contract returned NORAD
  39444 for both bundled and uploaded copies.

### Offline operation and export

- **Code:** bundled real replay uses only checked-in recording, manifest,
  observation JSON, and historical TLEs. Synthetic analysis uses the checked-in
  CelesTrak cache; network access occurs only through the explicit refresh
  action. `app.py` excludes the large `observed_power` matrix from downloads and
  serializes the remaining evidence with `allow_nan=False`.
- **Evidence:** real and synthetic analysis were freshly run with
  `requests.get` mocked to fail on any call; network call count was zero. Both
  export payloads serialized as strict JSON. The real CLI wrote and reloaded a
  compact `/tmp` export with status `ok` and no `observed_power` key.

### Fresh checks executed for this audit

```text
.venv/bin/python -m compileall -q app.py core
  PASS

.venv/bin/python -m pytest -q tests/test_lastping_app.py tests/test_lastping.py tests/test_real_data.py
  PASS: 19 passed, 4 Skyfield/NumPy deprecation warnings, 16.17 s

.venv/bin/python -m core.real_data --output /tmp/lastping-current-audit-real.json
  PASS: candidate_match, NORAD 39444, score 6.8254372083,
        margin 4.1773315627, total processing 3.6448 s

core.training.benchmark() with BENCHMARK_PATH redirected to /tmp
  PASS: 200 synthetic cases; baseline 9%/7%, physics 60%/11%, ML 60%/8%

offline analyze/replay with requests.get mocked to raise
  PASS: zero network calls; real and synthetic strict-JSON exports serialized
```

## 2. Implemented but unverified

- **Advertised WAV path:** the uploader and libsndfile decoder accept `.wav`,
  and the same metadata/sample-rate/channel validation applies, but this audit
  and the committed tests used only the bundled OGG bytes. Arbitrary third-party
  OGG/WAV manifests and receiver pipelines are not validated.
- **Fresh installation:** `requirements-lastping.txt` had already been installed
  in this clean worktree's virtual environment. Dependency import and runtime
  compatibility were exercised, but this audit did not create another virtual
  environment or repeat a network package installation. Earlier status files
  report that installation; that is historical rather than new evidence here.
- **Training reproduction:** the committed model loaded and a fresh fixed-split
  benchmark ran, but the 500-example training command was not rerun because it
  would replace the committed model and metadata. Bit-for-bit retraining across
  platforms is therefore not asserted.
- **External-source revalidation:** local recording/API hashes and all internal
  cross-checks passed. The SatNOGS, flowgraph, and adjacent-observation URLs were
  not re-downloaded during this offline audit, so continued external
  availability was not tested.
- **Manual browser session:** interface behavior was freshly exercised with
  Streamlit AppTest, not a new manual browser session. The JSON payload itself
  was serialized and parsed, but the browser download event was not manually
  clicked in this audit.
- **Explicit CelesTrak refresh:** cached-orbit operation was verified; the
  optional network refresh action was intentionally not run.

## 3. Missing or blocked

### Concrete remaining work for a reliable archived-real hackathon prototype

1. **Make test setup reproducible.** `README.md` documents pytest commands, but
   `pytest` is absent from `requirements-lastping.txt`. Add a small development/
   test requirements file or document the extra install explicitly, then run a
   clean-clone CI job for the three LastPing test files.
2. **Resolve or narrow WAV support.** Add a licensed mono WAV fixture plus tests
   for a successful WAV import and sample-rate/channel/duration failures, or
   advertise only the OGG format that is actually exercised.
3. **Add hard archived controls before making stronger candidate-discrimination
   claims.** The only real pass is a positive and all three incorrect candidates
   are below the horizon. At least one licensed real negative and an
   above-horizon incorrect-candidate case are needed to test false matches. Until
   then, retain the current narrow “candidate match for one archived replay”
   wording and do not report real recall/FAR.
4. **Add CI for the scoped application.** There is no verified remote check for
   LastPing on the integration branch. A scoped job should install runtime plus
   test dependencies, validate artifact loading, run the 19 LastPing tests, and
   perform one compact offline replay/export.

### Blocked or unrelated checks

- A fresh full `.venv/bin/python -m pytest -q` stopped during collection with
  five `ModuleNotFoundError: cv2` errors in the unrelated `pi/` vision tests:
  `test_geometry.py`, `test_metric_depth.py`, `test_object_range.py`,
  `test_server.py`, and `test_training_data.py`. This does not indicate a
  LastPing failure; the scoped LastPing suite passed. Completing the repository-
  wide suite requires the separate vision dependency environment.
- No blocker was found for the bundled archived-real replay, candidate table,
  separately labelled synthetic experiment, or JSON export.

### Optional future work, not required for the present prototype

- Live SDR/receiver streaming, raw-I/Q import, STRF ingestion, job queues,
  authentication, and deployment are product extensions rather than blockers
  for the archived replay.
- A broader multi-pass, multi-station real corpus and real-domain model training/
  calibration are required only if the project later claims general real-world
  ML performance. The current synthetic-only, uncalibrated label is accurate.
- Orbit recovery or confirmed satellite identification is outside the verified
  scope; the current output is candidate evidence, not recovery proof.

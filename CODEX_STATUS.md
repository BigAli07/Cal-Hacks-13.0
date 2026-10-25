# Codex status: LastPing backend handoff

Status audited on 2026-10-25 in `/Users/big_ali07/Documents/ChatGPT/cal hacks`.

## Repository state

### Implemented and verified

- Dedicated branch: `codex/lastping-backend-handoff`.
- Repository: `https://github.com/BigAli07/Cal-Hacks-13.0.git`, configured as `origin` for fetch and push.
- Implementation preservation commit: `231aada` (`Preserve LastPing backend and validated replay`).
- Previously preserved handoff HEAD `465a0e61cadaaf7a86f5d81fec56ff0755680f57` remains in the branch ancestry unchanged.
- This status document is committed separately on the same branch; its commit is the branch `HEAD` after the handoff commit.
- Remote `main` was non-empty at `a8234cbb94059b866f11dcec688af50c98949b20` and initially contained only its independently created README. The remote history was fetched and non-destructively joined to the handoff branch in merge commit `72a9b5c3fa40c049427a2db8056e4b367b02da86`; both histories remain ancestors.
- The branch was pushed without force and independently verified with `git ls-remote` at `72a9b5c3fa40c049427a2db8056e4b367b02da86` before this final status update.
- Pull request [#2](https://github.com/BigAli07/Cal-Hacks-13.0/pull/2) is open from `codex/lastping-backend-handoff` into `main` and is intentionally unmerged.
- The local project history is based on commit `c6626a3`. The existing vision/haptics project in `pi/`, `web/`, `arduino/`, and its tests remains intact.
- Relevant LastPing files were reviewed and staged explicitly. `.venv`, dependency folders, ignored delivery ZIPs, `.DS_Store`, credentials, and environment files were not included.
- The 10,600,024-byte SatNOGS OGG is included because the observation data is documented as CC BY-SA 4.0. Its attribution and source are in `data/real/README.md` and `DATA_SOURCES.md`; its SHA-256 is `c317e44ccddb890023a1b863c326fb856525902da3aeefa3355d566fe64aaf63`.
- No required large file is stored separately. `deliverables/lastping-project.zip` remains ignored and is not part of the Git history.

### Implemented but unverified

- A clean-clone installation on another machine has not been run during this handoff.
- The saved classifier was not retrained during this handoff. Its loading, metadata, features, and fixed test benchmark were exercised.

### Missing or blocked

- No repository-publication blocker remains. Merge of PR #2 is deliberately left for human review.

## Contribution and ownership

### Implemented and verified

- Codex implemented and verified the scientific/backend modules in `core/`, the LastPing tests, model/evaluation artifacts, real-data provenance, and backend documentation.
- The existing repository's previously committed vision/haptics code was not modified by the LastPing implementation commit.

### Implemented but unverified

- `HANDOFF.md` attributes the Streamlit interface in `app.py` to Cursor and the backend integration/accuracy edits to Codex. Because all LastPing files were untracked before preservation, Git history cannot independently prove that split. `app.py` is therefore preserved as required integration work but is not claimed as exclusively Codex-authored.

### Missing or blocked

- Cursor's uncommitted work cannot be distinguished beyond the written handoff attribution because no LastPing base commit or remote comparison was available. No ambiguous file was discarded or arbitrarily split.

## Components

### Implemented and verified

- `app.py`: one Streamlit interface with archived-real replay and separately labelled synthetic experiment modes.
- `core/engine.py`: stable integration facade.
- `core/real_data.py`: manifest validation, OGG/WAV decoding, native spectrogram, historical orbit prediction, independently measured ridge, candidate ranking, exploratory synthetic-model scoring, and real conclusion.
- `core/orbit.py`: CelesTrak cache handling, pass selection, Skyfield/SGP4 geometry, and Doppler calculation.
- `core/simulation.py`: deterministic synthetic spectra and separate reveal-only ground truth.
- `core/detection.py`: signal-strength baseline, bounded physics template search, and observation-derived ML features.
- `core/training.py`: explicit synthetic training, validation-threshold selection, saved-model loading, and fixed benchmark.
- `artifacts/lastping_model.joblib`, `artifacts/model_metadata.json`, `artifacts/benchmark.json`, and `artifacts/real_replay.json`: reproducibility artifacts.
- `tests/test_lastping.py`, `tests/test_lastping_app.py`, and `tests/test_real_data.py`: backend, UI-contract, and archived-data tests.

### Implemented but unverified

- The optional network refresh of the CelesTrak cache was not exercised during this handoff; the checked-in cache was used.

### Missing or blocked

- There is no live SDR adapter, live receiver stream, raw-I/Q importer, STRF ingestion, production API server, authentication layer, job queue, or deployment configuration.

## Actual application flow

### Implemented and verified

1. In real mode, the user chooses the bundled observation or uploads an OGG/WAV file plus a JSON manifest and selects **Analyze recording**.
2. `core.engine.replay_real()` calls `core.real_data.analyze_real()`.
3. The manifest schema and required fields are validated. The recording SHA-256 is checked; bundled original SatNOGS metadata is also hash-checked and cross-checked against the manifest.
4. SoundFile decodes mono audio. A 2048-point Hann-window PSD is computed in 0.5-second bins at native dimensions; the bundled pass produces a 706 by 1025 array.
5. Historical TLEs are evaluated at actual acquisition timestamps and station coordinates. The receiver's scheduled-target Doppler correction is modeled explicitly.
6. A measured energy ridge is extracted independently of candidates. Candidate templates search bounded timing and frequency offsets and are ranked without using the scheduled target label as a detector feature.
7. The saved synthetic-only logistic model provides an explicitly uncalibrated exploratory score. It does not make the real-data conclusion.
8. The UI displays provenance, conclusion, waterfall, predicted tracks, best fitted template, measured ridge, candidate evidence, method cards, calibration warnings, timings, and downloadable JSON.
9. In synthetic mode, user controls feed `core.engine.analyze()`, which selects cached orbit geometry, simulates an observation, runs baseline/physics/ML methods, and returns results. Ground truth is retained separately and shown only when requested.

### Implemented but unverified

- Uploaded OGG/WAV processing is covered by Streamlit AppTest using the bundled recording bytes and manifest, but arbitrary third-party recordings have not been validated.

### Missing or blocked

- The UI does not receive or display a live radio stream. "Real" means replay of archived received audio.

## Recording contract and metadata

### Implemented and verified

- Supported containers: OGG/Vorbis and WAV readable by libsndfile through `soundfile`.
- Required signal layout: one real-valued mono channel. The decoded sample rate and channel count must match the manifest. The current importer specifically requires documented target-Doppler-corrected BPSK audio with an audio IF.
- Required top-level manifest fields: `schema`, `observation_id`, `observation_url`, `recording_url`, `recording_file`, `recording_sha256`, `acquisition_start_utc`, `receiver`, `recording_format`, `transmitter`, `scheduled_target`, `candidate_catalog`, `license`, and `attribution`.
- `schema` must be `lastping-real-recording-v1`.
- `receiver` requires latitude, longitude, and elevation. `recording_format` requires decoded sample rate, channels, audio IF, and Doppler-correction flag. `transmitter` requires frequency and mode. Every candidate requires name, catalog ID, TLE lines, and TLE source URL.
- The bundled data is archived real SatNOGS receiver audio plus real observation metadata and historical TLEs. It is lossy target-Doppler-corrected audio, not raw RF I/Q and not calibrated power.
- The CelesTrak cache contains real public orbital elements used by the synthetic experiment.
- Synthetic spectra, labels, injected signals, noise, and interference are generated locally. No live data source is present.
- The archived recording completed the full implemented pipeline and produced a ranked result.

### Implemented but unverified

- Only one independently supported real positive observation is bundled.

### Missing or blocked

- No verified real negative corpus or multi-pass, multi-station real evaluation set exists.

## ML model and evaluation

### Implemented and verified

- Model: scikit-learn `StandardScaler` followed by `LogisticRegression`.
- Six features: normalized peak strength, searched-track accumulation, track/background contrast, supported-bin fraction, persistence, and contrast against stationary interference.
- Training source: 500 synthetic recordings with seeds 10000-10499.
- Validation source: 160 independent synthetic recordings with seeds 20000-20159. Baseline, physics, and ML thresholds were fixed here for a target 5% empirical false-alarm rate.
- Test source: 200 untouched synthetic recordings with seeds 30000-30199: 100 positives and 100 negatives, including 32 stationary-interference negatives.
- Saved artifacts: trained pipeline in `artifacts/lastping_model.joblib`; schema, versions, splits, counts, and thresholds in `artifacts/model_metadata.json`; current fixed-test results in `artifacts/benchmark.json`.
- Current synthetic test results: baseline recall 9/100 and FAR 7/100; physics recall 60/100 and FAR 11/100; ML recall 60/100 and FAR 8/100.
- Current benchmark CPU totals: baseline 0.0768 s, physics 0.3038 s, and ML 0.3752 s including feature extraction; ML model-only time was 0.0022 s.
- Current archived replay result: `candidate_match`, FUNCUBE-1/NORAD 39444 ranked first, physics score 6.8254, margin 4.1773, fitted frequency offset -500 Hz, 99.3% above-horizon support, and 283.8 Hz ridge RMS residual. SatNOGS publishes 53 decoded frames independently supporting reception.
- Current archived replay processing: 3.6331 s total for 352.796 s of audio (0.3608 s spectrogram, 0.0078 s orbit prediction, 3.2462 s candidate scoring, 0.0025 s model-only scoring).

### Implemented but unverified

- Real-recording ML output is deliberately marked `experimental_uncalibrated`; no real-data threshold or probability interpretation is verified.
- CPU timing is machine-specific and is not a latency guarantee.

### Missing or blocked

- Real recall, real false-alarm rate, receiver sensitivity, cross-pass generalization, orbit recovery, and confirmed satellite identity are not established by one positive replay.

## Checks executed during this handoff

### Implemented and verified

- `.venv/bin/python -m pytest -q`: 36 passed, 4 Skyfield/NumPy deprecation warnings, 13.72 s.
- `.venv/bin/python -m core.real_data`: completed successfully and refreshed `artifacts/real_replay.json`.
- `.venv/bin/python -m core.training benchmark`: completed successfully on the fixed 200-recording test split and refreshed `artifacts/benchmark.json` without retraining.
- `.venv/bin/python -m compileall -q app.py core`: completed successfully.
- Recording and original metadata SHA-256 values matched the manifest.
- A repository scan found no common private-key, credential, token, password, or API-key patterns in the staged text files.

### Implemented but unverified

- Streamlit browser behavior was exercised by the committed AppTest suite, but a new manual browser session was not opened during this preservation handoff.

### Missing or blocked

- No repository CI workflow or completed PR check is currently verified.

## Commands

### Implemented and verified

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-lastping.txt
.venv/bin/python -m core.real_data
.venv/bin/python -m core.training benchmark
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app.py core
.venv/bin/streamlit run app.py
```

Training is intentionally explicit and overwrites the saved synthetic model/metadata before evaluation:

```bash
.venv/bin/python -m core.training train
.venv/bin/python -m core.training benchmark
```

### Implemented but unverified

- Fresh environment creation and dependency installation were not repeated during this handoff because the existing `.venv` was used.

### Missing or blocked

- There is no deployment command or production server command.

## Backend/UI contract and integration requirements

### Implemented and verified

- `core.engine.replay_real(recording=None, manifest=None) -> dict`: validates and processes the bundled or supplied archived recording. Uploaded recording bytes require uploaded manifest bytes/dict/path.
- `core.engine.analyze(config) -> dict`: runs one synthetic experiment. Supported presets are `strong_beacon`, `faint_intermittent`, `interference_only`, and `noise_only`; observer latitude/longitude/elevation are supplied in `config["observer"]`.
- `core.engine.benchmark() -> dict`: executes the fixed final synthetic benchmark.
- `core.engine.saved_benchmark() -> dict`: reads the committed historical benchmark without recomputation.
- Missing model artifacts return an explicit unavailable result and setup instruction rather than silently training.
- Streamlit expects the nested dictionaries currently returned by these functions, including `recording`, `axes`, `observed_power`, `observed_ridge_hz`, `candidates`, `methods`, `timings`, `orbit`, and synthetic `ground_truth` fields. Changes to names, array lengths, status labels, or nullable values require coordinated UI and test updates.
- NumPy arrays are converted to JSON-compatible lists at the real-data boundary. The full real `observed_power` array is intentionally excluded from the saved `artifacts/real_replay.json` CLI artifact to limit size, but is returned to the live UI.

### Implemented but unverified

- The contract is enforced by tests rather than a versioned JSON Schema or typed external API definition.

### Missing or blocked

- No network API contract, database schema, or multi-user state contract exists.

## Unfinished work and blockers, in priority order

### Missing or blocked

1. Review and merge PR [#2](https://github.com/BigAli07/Cal-Hacks-13.0/pull/2) when the repository owner is satisfied. This handoff intentionally does not merge it.
2. Reconcile `app.py` with any subsequent Cursor work before merging. Its written ownership is Cursor-attributed/ambiguous; the remote `main` inspected during this handoff contained no Cursor implementation to compare.
3. Build a licensed real corpus containing verified positives and negatives across passes, stations, receivers, satellites, and interference conditions; retrain/calibrate or remove the real ML score based on that evidence.
4. Add raw-I/Q or clearly specified receiver formats if required. The present real importer only supports documented target-Doppler-corrected mono audio.
5. Add live SDR/stream ingestion only if live operation is an actual product requirement.
6. Add remote CI and clean-clone reproducibility checks.

### Implemented but unverified

- None of these unfinished items has been started in this handoff.

# LastPing submission notes

Release: `787332358c99af318137b44d563f8d0c9bc31a65` on `cursor/lastping-integrated`  
Repository: https://github.com/BigAli07/Cal-Hacks-13.0.git

Claim this submission can support:

> We analyze a real archived satellite reception and compare its measured signal evidence with historical candidate satellite tracks.

## Problem and intended users

A weak satellite transmission can look like noise, and several catalogued satellites can be plausible at one receiver and time. LastPing is a local prototype for a reviewer who already has an archived reception and wants to see whether the measured spectrum agrees with historical orbital tracks.

The intended user is a technical judge or radio observer replaying one known observation offline. The app is not a live ground-station controller, a search tool for a lost satellite, or a calibrated identifier.

## Implemented processing flow

One Streamlit process serves two labelled modes. The submission demo uses only real replay.

1. The user leaves the source on **Bundled validated SatNOGS observation** and clicks **Analyze recording**. `replay_real()` validates the bundled OGG and manifest, including SHA-256.
2. SoundFile decodes the mono 48 kHz OGG. A 2048-point Hann PSD is formed in 0.5-second bins at the recording’s native size, 706 by 1025. No samples are invented for the 3.204 seconds missing from the scheduled observation.
3. Historical TLEs are evaluated at the acquisition timestamps and at PE0SAT-32. The receiver’s scheduled-target Doppler correction is modelled: candidate audio frequency is 12 kHz plus candidate RF Doppler minus that correction.
4. An energy ridge is extracted from the spectrum independently of the candidate templates. Each candidate then gets a bounded time and frequency search. The scheduled target name is not a detector feature.
5. A signal-strength baseline is reported as measured but uncalibrated. Physics ranking produces the real conclusion. The saved logistic regression adds an exploratory score and does not make that decision.
6. The page shows archived-not-live provenance, the waterfall, predicted tracks, the fitted template, the independent ridge, the ranked table, and a JSON download without the raw power grid.

The other mode, **Synthetic experiment**, simulates a spectrum with cached public orbital elements and an assumed 437 MHz carrier. It is separate from the archived recording and is not part of the judge walkthrough.

## Cursor and Codex

Codex built and checked the scientific backend: `core/`, the LastPing tests, the saved scaler and classifier, the real-recording manifest and provenance, and the release checks. That work includes spectrogram generation, historical Doppler geometry, independent ridge extraction, candidate ranking, and the rule that synthetic thresholds are not applied to this recording. The release commits on this branch are `c99276e` (reproducible checks), `cfb05a6` (release status), and `7873323` (recorded passing CI).

Cursor built the mission-control interface in `app.py` and `.streamlit/config.toml`, connected it to the published backend without replacing `core/`, and kept the real and synthetic modes visually distinct. Later interface commits on this branch cover the phone sidebar, waterfall spacing, empty-state copy, fixed score formatting, readable orbit labels, and the candidate-match / ambiguous wording. `1e122bc` is the interface fix included in this release. `FINAL_UI_STATUS.md` records the browser check of that interface.

Pull requests #1, #2, and #3 were still open when these notes were written. This submission does not merge them.

## Data attribution

The bundled reception is SatNOGS Network observation **6659851**, ground station **PE0SAT-32**.

- License: Creative Commons Attribution-ShareAlike 4.0.
- Observation: https://network.satnogs.org/observations/6659851/
- Licensing statement: https://network.satnogs.org/about/
- Files: `data/real/satnogs_6659851_2022-10-26T04-12-41.ogg`, `satnogs_6659851_observation.json`, and `satnogs_6659851_manifest.json`.
- Audio SHA-256: `c317e44ccddb890023a1b863c326fb856525902da3aeefa3355d566fe64aaf63`.
- Acquired `2022-10-26T04:12:41Z`. Transmitter: 145.935 MHz, BPSK, 1200 baud. Receiver: RTL-SDR serial 00001470, 2.048 MS/s, 42.1 dB gain, −1 ppm.

The OGG is the real-valued, lossy output of the SatNOGS BPSK flowgraph after target Doppler correction. LastPing does not redistribute that flowgraph’s source. The three comparison satellites use historical TLEs from adjacent SatNOGS records: AAUSAT CUBESAT 2 from 6659850, OSCAR 11 from 6659848, and OSCAR 7 from 6659856. Synthetic geometry, unused in this demo, comes from the cached CelesTrak cubesat GP elements.

## Verified tests and measured results

GitHub CI passed on the release branch:

- Push: https://github.com/BigAli07/Cal-Hacks-13.0/actions/runs/40200784197
- Pull request: https://github.com/BigAli07/Cal-Hacks-13.0/actions/runs/40200784335

`RELEASE_STATUS.md` records the local release check: compile of `app.py` and `core`, saved-model load (500 training examples; steps `scaler`, `classifier`), and **22 passed** tests in `tests/test_lastping_app.py`, `tests/test_lastping.py`, and `tests/test_real_data.py`. The WAV tests replay a temporary PCM-16 derivative of this same OGG and reject 44.1 kHz and stereo input. That WAV is not a second observation.

The release replay command returned `candidate_match` for FUNCUBE 1 / NORAD 39444, physics score `6.8254372083`, margin `4.1773315627`, and processing `3.5565 s`. The saved artifact and interface show the same ranking with the values a judge will see:

| Candidate | NORAD | Physics | Offset | Above horizon | Ridge RMS | Synthetic-model score |
| --- | --- | --- | --- | --- | --- | --- |
| FUNCUBE 1 | 39444 | 6.825 | −500 Hz | 0.993 | 283.8 Hz | 1.000, uncalibrated |
| AAUSAT CUBESAT 2 | 32788 | 2.648 | −1500 Hz | 0.000 | — | 0.977, uncalibrated |
| OSCAR 7 | 7530 | 2.028 | 1500 Hz | 0.000 | — | 0.272, uncalibrated |
| OSCAR 11 (UoSAT 2) | 14781 | 1.986 | 1200 Hz | 0.000 | — | 0.205, uncalibrated |

The ML status is `experimental_uncalibrated`. Real thresholds are unavailable. Acquisition duration is 352.796 s, distinct from processing time. SatNOGS lists 53 decoded frames for this observation; that fact supports the recording and is not fed to the ranker as a label.

On the separate synthetic test set in `MODEL_CARD.md`, 100 positive and 100 negative recordings gave baseline 9/100 recall and 7/100 false alarms, physics 60/100 and 11/100, and ML 60/100 and 8/100. Those figures are synthetic. They are not real-data accuracy.

## Remaining limitations

- One independently supported positive pass is included. There is no defensible real negative, so real recall and false-alarm rate are not measured.
- The three incorrect candidates are below the PE0SAT-32 horizon for this pass. They are not an in-band above-horizon control.
- The audio is lossy, target-Doppler-corrected, and single-channel. Amplitude is relative. It cannot support a claim about receiver sensitivity.
- The classifier saw only synthetic examples. A score of 1.000 on this recording is not certainty and is not a recovery probability.
- WAV coverage is the PCM-16 form of this licensed OGG, not an arbitrary codec or a new observation.
- There is no live SDR path. The demo must stay on archived replay.

# Final UI status — LastPing

Audit date: 2026-10-25  
Repository: https://github.com/BigAli07/Cal-Hacks-13.0  
Browser session served `fd52f2dd32f2b8555f91f072b92bd39a5719227e` (server started before the later commit; Watchdog is not installed, so it did not reload). During the audit, origin advanced to `7ec617dd5e75fc3a4552904b6cae1a14ff8113ba` (“Fix stale replay state and verify demo guide”): changing recording source, and starting Analyze, now clears `real_result` first. That commit was not re-rendered in the browser.  
`FINAL_BACKEND_STATUS.md`: **not on origin** (checked `main`, `cursor/interface`, `cursor/lastping-integrated`, `codex/lastping-backend-handoff`).

Read: `CURSOR_STATUS.md`, `CODEX_STATUS.md`, `HANDOFF.md`, `app.py`, `core/engine.py` contract (`replay_real`, `analyze`, `benchmark`, `saved_benchmark`). `core/` was not modified.

No detector card on this branch is a UI placeholder. Scores, tracks, and the candidate table come from those functions. The pre-Analyze real screen is an empty state, not a fake result.

## 1. Implemented and verified

Browser session: fresh tab at `http://localhost:8502` (process serving this branch’s `app.py`).

- Bundled real analysis: **Analyze recording** on “Bundled validated SatNOGS observation” produced archived-not-live badges, the uncalibrated-RF warning, **Candidate beacon**, FUNCUBE 1 / NORAD 39444, acquisition `2022-10-26T04:12:41Z`, station PE0SAT-32, 145.935 MHz BPSK, SHA-256, known limitations, waterfall **706 × 1025**, predicted tracks, best fitted template, independent measured ridge, ranked table (physics 6.825, offset −500 Hz, above-horizon 0.993), synthetic-model score **1.000** with the calibration sentence “Synthetic thresholds and probabilities are not transferred to real RF decisions.” Processing 3.740 s vs acquisition 352.796 s. **Download real-analysis JSON** was present. File bytes were not opened.
- Reset (real): cleared the waterfall and restored the “Select Analyze recording…” empty state.
- Upload controls: source “Upload recording and metadata” shows OGG/WAV and JSON uploaders. Analyze with neither file shows “Select both a supported OGG/WAV recording and its metadata JSON.”
- Successful upload of the bundled OGG + manifest was **not** completed in the browser (`DOM.setFileInputFiles` is denied). Re-run this audit: `pytest tests/test_lastping_app.py::test_supported_upload_replays_the_same_validated_recording` **passed** (NORAD 39444, `local_source == "uploaded recording"`).
- Synthetic mode: switching modes called `analyze` (result was empty). Badges “Radio: simulated” / orbit `real_public_orbital_elements`, CUTE-1 (CO-55) NORAD 27844 via CelesTrak, simulated-spectrogram note, waterfall **128 × 192**, predicted and detected tracks, ground-truth toggle off, scores 0.882 / 2.090 / synthetic-model score 0.611. **Download synthetic-analysis JSON** present.
- Stale synthetic result: seed 7 → 8 kept score 0.882 and showed “Controls have changed since this result was computed.”
- Reset controls: seed returned to 7 and the stale warning cleared (`false|7` in the page).
- Historical benchmark expander showed saved JSON including recall, with the caption that opening it does not rerun evaluation.
- Narrow viewport 390×844: with the sidebar still open, it covered the main column. After it collapsed, title, badges, CelesTrak summary, and a small heatmap were readable. Plot colorbar crowds the chart. The CelesTrak URL wraps mid-query.

Also re-run: `test_controls_wait_for_analysis_and_reset` passed (stale warning, reset).

## 2. Implemented but unverified

- Downloaded JSON contents (buttons only).
- Browser attach of a real OGG/manifest pair, and a malformed manifest (`RecordingValidationError` path).
- Reveal-ground-truth overlay in this browser session (toggle exists; default off).
- **Fetch/refresh public orbit cache**, **Train synthetic classifier**, and **Run synthetic benchmark** were not clicked. Missing-model copy was not shown because `artifacts/lastping_model.joblib` is present.
- `ambiguous` ranking label (mapped in code to “Insufficient evidence”; this replay was `candidate_match`).
- Provenance expander JSON body (summary fields were on the page; expander not opened).

## 3. Missing or blocked

- `FINAL_BACKEND_STATUS.md` is not in the repository.
- Live reception. Real mode is archived replay only.
- Real-data ML remains an uncalibrated synthetic-model score by backend contract. The UI must not treat 1.000 as a probability.
- Browser file-input automation cannot attach uploads. AppTest covers the bundled pair only.
- Unrelated `pi/` tests still need OpenCV. Not a LastPing UI defect.

## Controls tied to computation

| Control | Calls |
| --- | --- |
| Analyze recording (bundled) | `replay_real()` |
| Analyze recording (upload) | `replay_real(bytes, manifest bytes)` |
| Synthetic first view and Run analysis | `analyze(config)` with preset, seed, excess, interference, observer lat/lon/elevation |
| Saved benchmark expander | `saved_benchmark()` (artifact read) |
| Train / Run synthetic benchmark / Fetch cache | `train()`, `benchmark()`, `fetch_celestrak_cache()` — present, not exercised here |
| Reset | clears session results; does not invent scores |

## Concrete interface fixes (no new features)

1. At 390px the expanded sidebar covers the page. Collapse it by default under that width, or keep the collapse control visible before the content is hidden.
2. After collapse, the Plotly heatmap stays small and the colorbar overlaps the plot. Let the chart use the column width.
3. Upload mode’s empty message still tells the user to run the bundled SatNOGS observation. Say that both an OGG/WAV and a manifest are required.
4. Candidate table shows the uncalibrated ML score as `1` and the ridge RMS residual as a long float (`283.787…`). Format both to a fixed number of decimals and keep the uncalibrated label.
5. The synthetic orbit badge prints the raw kind `real_public_orbital_elements`. Show a short human label.
